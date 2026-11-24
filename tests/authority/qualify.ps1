[CmdletBinding()]
param([ValidateSet('Both','Offline','Runtime')][string]$QualificationSlice = 'Both')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$exactManagedCommandPaths = @(
    '.opencode/commands/olympus.ultra.md',
    '.opencode/commands/olympus.performance.md'
)
$expectedOlympusAgentIds = @('kael','veyra','orin','kovan','nox','vera','thales','atlas','argus','talos','helios')
$automationActionsV240 = @('automation_create','automation_list','automation_pause','automation_resume','automation_delete')
$protectedToolActionsV240 = @($automationActionsV240) + @('browser')
$newToolDenyAgentIds = @('kael','kovan','nox','orin','vera','veyra')
function Text([string]$path) { [IO.File]::ReadAllText((Join-Path $root $path)) }
function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}

function Covers([string]$scope, [string]$path) {
    $s = $scope.Replace('\','/').TrimEnd('/')
    $p = $path.Replace('\','/').TrimStart('/')
    if ($s.EndsWith('/**')) { return $p.StartsWith($s.Substring(0, $s.Length - 2), [StringComparison]::OrdinalIgnoreCase) }
    return $p.Equals($s, [StringComparison]::OrdinalIgnoreCase)
}

function Is-OlympusOwned([string]$path, [string[]]$manifestPaths = @(),
                         [bool]$canonicalSourceTarget = $false) {
    $p = $path.Replace('\','/').TrimStart('/').ToLowerInvariant()
    $fixed = @('.opencode/agents/',
        '.opencode/plugins/olympus-activity/', '.opencode/scripts/worktree-setup.ps1',
        '.opencode/orchestrator-install.json',
        '.opencode/opencode.json', '.opencode/opencode.jsonc', '.codex/', 'CODEX.md',
        'olympus/', 'scripts/render_harnesses.py', 'opencode.jsonc', 'opencode.json')
    if ($p -in $exactManagedCommandPaths) { return $true }
    # Canonical source is editable only when OlympusAgents is the proven task
    # target; installed runtime resources stay protected in every repository.
    $canonicalSource = $canonicalSourceTarget -and ($p.StartsWith('olympus/') -or $p -eq 'scripts/render_harnesses.py')
    if (-not $canonicalSource -and @($fixed | Where-Object { $p.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0) { return $true }
    foreach ($entry in $manifestPaths) {
        $declared = $entry.Replace('\','/').TrimStart('/').ToLowerInvariant()
        if ($p -eq $declared -or $p.StartsWith($declared.TrimEnd('/') + '/', [StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Decide([string]$agent, [string]$operation, [string]$path, [string]$normalScope,
                 [string]$repositoryRoot, $grant, [bool]$taskActive = $true,
                 [bool]$projectOwned = $true, [bool]$explicitProhibition = $false,
                 [string[]]$manifestPaths = @(), [string]$nativeDecision = 'ALLOW',
                 [bool]$canonicalSourceTarget = $false) {
    # nativeDecision models the effective rule outcome, not a tool attempt or host ASK event.
    # A null grant models omitted AUTHORITY_GRANT; normalScope is the validated assignment scope.
    if ($explicitProhibition) { return [pscustomobject]@{ decision='DENY'; question=0; reason='USER_PROHIBITION' } }
    if (Is-OlympusOwned $path $manifestPaths $canonicalSourceTarget) { return [pscustomobject]@{ decision='DENY'; question=0; reason='OLYMPUS_OWNED' } }
    if (-not $projectOwned) { return [pscustomobject]@{ decision='DENY'; question=0; reason='OWNERSHIP_UNPROVEN' } }
    $normal = Covers $normalScope $path
    $valid = $false
    if ($null -ne $grant) {
        $valid = $taskActive -and $grant.agent -ceq $agent -and $grant.operation -ceq $operation -and
            $grant.repository_root -ceq $repositoryRoot -and $grant.lifetime -ceq 'current_task' -and
            $grant.task_id -ceq 'task-7' -and $grant.permission_mode -in @('ALLOW','NATIVE_ASK') -and
            (Covers $grant.scope $path)
    }
    if ($normal -and $nativeDecision -eq 'ALLOW') {
        return [pscustomobject]@{ decision='ALLOW'; question=0; reason='NORMAL_SCOPE' }
    }
    if ($nativeDecision -eq 'DENY') { return [pscustomobject]@{ decision='DENY'; question=0; reason='NATIVE_DENY' } }
    if ($valid) {
        if ($grant.permission_mode -eq 'NATIVE_ASK' -and $nativeDecision -eq 'ASK') {
            return [pscustomobject]@{ decision='NATIVE_ASK'; question=0; reason='EXACT_NATIVE_ASK_GRANT' }
        }
        if ($grant.permission_mode -eq 'ALLOW' -and $nativeDecision -eq 'ALLOW') {
            return [pscustomobject]@{ decision='ALLOW'; question=0; reason='EXACT_ALLOW_GRANT' }
        }
        return [pscustomobject]@{ decision='DENY'; question=0; reason='GRANT_PERMISSION_MODE_MISMATCH' }
    }
    if ($null -ne $grant -and (-not $taskActive -or $grant.lifetime -ne 'current_task' -or $grant.task_id -ne 'task-7')) {
        return [pscustomobject]@{ decision='DENY'; question=0; reason='GRANT_EXPIRED_OR_WRONG_TASK' }
    }
    [pscustomobject]@{ decision='NEED_AUTHORITY'; question=0; reason='SCOPE_NOT_DELEGATED' }
}

function New-Grant([string]$agent, [string]$operation, [string]$scope, [string]$rootPath,
                    [string]$permissionMode = 'ALLOW', [string]$lifetime = 'current_task') {
    [pscustomobject]@{ agent=$agent; operation=$operation; scope=$scope; repository_root=$rootPath;
        permission_mode=$permissionMode; lifetime=$lifetime; task_id='task-7' }
}

function Synthetic-ToolFlow([string]$decision, [string]$nativeOutcome = 'NONE') {
    # Deterministic policy model only: it does not invoke OpenCode or assert that a UI appeared.
    if ($decision -eq 'ALLOW') {
        return [pscustomobject]@{ attempted=$true; pending=$false; executed=$true; continue=$true; question=0; fallback=$false; retry=$false }
    }
    if ($decision -eq 'NATIVE_ASK') {
        if ($nativeOutcome -eq 'APPROVE_ONCE') {
            return [pscustomobject]@{ attempted=$true; pending=$false; executed=$true; continue=$true; question=0; fallback=$false; retry=$false }
        }
        if ($nativeOutcome -in @('REJECT','CANCEL')) {
            return [pscustomobject]@{ attempted=$true; pending=$false; executed=$false; continue=$false; question=0; fallback=$false; retry=$false }
        }
        return [pscustomobject]@{ attempted=$true; pending=$true; executed=$false; continue=$false; question=0; fallback=$false; retry=$false }
    }
    [pscustomobject]@{ attempted=$false; pending=$false; executed=$false; continue=$false; question=0; fallback=$false; retry=$false }
}

function Classify-NewScope([string]$nativeDecision, [bool]$projectOwned = $true,
                           [bool]$explicitProhibition = $false, [bool]$roleAllowed = $true,
                           [bool]$destructive = $false) {
    if ($explicitProhibition -or -not $projectOwned -or -not $roleAllowed -or $destructive -or $nativeDecision -eq 'DENY') { return 'DENY' }
    if ($nativeDecision -eq 'ASK') { return 'NATIVE_ASK' }
    if ($nativeDecision -eq 'ALLOW') { return 'ALLOW' }
    'DENY'
}

function Read-NativeRules([string]$agentText, [object[]]$globalRules) {
    $header = [regex]::Match($agentText, '(?s)\A---\r?\n(.*?)\r?\n---').Groups[1].Value
    $rules = [Collections.Generic.List[object]]::new()
    foreach ($m in [regex]::Matches($header, '(?ms)^\s{2}- action:\s*(?<action>[^\r\n]+)\r?\n\s{4}resource:\s*"?(?<resource>[^"\r\n]+)"?\r?\n\s{4}effect:\s*(?<effect>allow|ask|deny)\s*$')) {
        $rules.Add([pscustomobject]@{ action=$m.Groups['action'].Value.Trim().Trim('"'); resource=$m.Groups['resource'].Value.Trim(); effect=$m.Groups['effect'].Value.Trim() })
    }
    return @($globalRules) + @($rules.ToArray())
}

function Matches-Glob([string]$pattern, [string]$resource) {
    $regex = [regex]::Escape($pattern).Replace('\*', '.*').Replace('\?', '.')
    return [regex]::IsMatch($resource, '^' + $regex + '$', [Text.RegularExpressions.RegexOptions]::IgnoreCase)
}

function Native-Decision([object[]]$rules, [string]$action, [string]$resource,
                         [bool]$explicitProhibition = $false) {
    if ($explicitProhibition) { return 'DENY' }
    $decision = 'ALLOW'
    # OpenCode permission patterns use last matching rule; agent rules follow and
    # take precedence over global configuration.
    foreach ($rule in $rules) {
        if ((Matches-Glob $rule.action $action) -and (Matches-Glob $rule.resource $resource)) {
            $decision = $rule.effect.ToUpperInvariant()
        }
    }
    return $decision
}

function Get-ExactRuleIndices([object[]]$rules, [string]$action, [string]$resource, [string]$effect) {
    $indices = [Collections.Generic.List[int]]::new()
    for ($i = 0; $i -lt $rules.Count; $i++) {
        $rule = $rules[$i]
        if ([string]$rule.action -ceq $action -and [string]$rule.resource -ceq $resource -and
            [string]$rule.effect -ceq $effect) {
            $indices.Add($i)
        }
    }
    return $indices.ToArray()
}

function Write-Decision([string]$nativeDecision, [string]$approval = 'NONE') {
    if ($nativeDecision -eq 'ALLOW') { return $true }
    if ($nativeDecision -eq 'DENY') { return $false }
    return $approval -eq 'APPROVE_ONCE'
}

function New-PermissionReport([bool]$attempted, [string]$execution, [string]$toolResult,
                              [string]$uiObservation = 'NOT_OBSERVABLE',
                              [string]$permissionDecision = 'NOT_OBSERVABLE',
                              [string]$externalObservation = 'NONE') {
    # Reporting records only supplied evidence; execution result never infers UI or human action.
    [pscustomobject]@{
        TOOL_ATTEMPT = $(if ($attempted) { 'ATTEMPTED' } else { 'NOT_ATTEMPTED' })
        TOOL_EXECUTION = $execution
        TOOL_RESULT = $toolResult
        NATIVE_PERMISSION_UI = $uiObservation
        NATIVE_PERMISSION_DECISION = $permissionDecision
        USER_CONFIRMED_EXTERNAL_OBSERVATION = $externalObservation
    }
}

function Compact-Evidence([string]$value) {
    if ([string]::IsNullOrWhiteSpace($value)) { return '<empty>' }
    $compact = ($value -replace '\s+', ' ').Trim()
    if ($compact.Length -gt 240) { $compact = $compact.Substring(0, 240) + '...' }
    return $compact
}

function Inspect-EffectiveRules([object]$runtimeExit, [string]$runtimeJson,
                                [string]$runtimeStderr = '', [string]$invocationError = '') {
    $failures = [Collections.Generic.List[string]]::new()
    $runtimeAgents = @()
    $olympusAgentMatches = @{}
    foreach ($agentId in $expectedOlympusAgentIds) {
        $olympusAgentMatches[$agentId] = [Collections.Generic.List[object]]::new()
    }
    $additionalAgentIds = [Collections.Generic.List[string]]::new()
    $runtimeJsonParseable = $false
    $runtimeJsonParseError = ''
    $runtimeJsonRootType = 'UNAVAILABLE'
    $runtimeJsonRootIsArray = $false
    try {
        $runtimeDocument = ConvertFrom-Json -InputObject $runtimeJson -Depth 100 -NoEnumerate -ErrorAction Stop
        $runtimeJsonParseable = $true
        if ($null -eq $runtimeDocument) {
            $runtimeJsonRootType = 'null'
        } else {
            $runtimeJsonRootType = $runtimeDocument.GetType().FullName
        }
        if ($runtimeDocument -is [array]) {
            $runtimeAgents = $runtimeDocument
            $runtimeJsonRootIsArray = $true
        }
    } catch {
        $runtimeJsonParseError = $_.Exception.Message
    }

    if (-not [string]::IsNullOrWhiteSpace($invocationError)) {
        $failures.Add('runtime_invocation_error=' + (Compact-Evidence $invocationError))
    }
    if ($null -eq $runtimeExit) {
        $failures.Add('runtime_exit=<unavailable>')
    } elseif ([int]$runtimeExit -ne 0) {
        $failures.Add("runtime_exit=$runtimeExit")
    }
    if (-not $runtimeJsonParseable) {
        $failures.Add('json_parseable=false; json_error=' + (Compact-Evidence $runtimeJsonParseError))
    } elseif (-not $runtimeJsonRootIsArray) {
        $failures.Add("json_root=$runtimeJsonRootType (expected array)")
    }

    $kaelMatches = [Collections.Generic.List[object]]::new()
    $kovanMatches = [Collections.Generic.List[object]]::new()
    if ($runtimeJsonRootIsArray) {
        foreach ($candidate in $runtimeAgents) {
            if ($null -eq $candidate) { continue }
            $idProperty = $candidate.PSObject.Properties['id']
            if ($null -eq $idProperty) { continue }
            $agentId = [string]$idProperty.Value
            if ($agentId -cin $expectedOlympusAgentIds) {
                $olympusAgentMatches[$agentId].Add($candidate)
            } else {
                $additionalAgentIds.Add($agentId)
            }
            if ($agentId -ceq 'kael') {
                $kaelMatches.Add($candidate)
            } elseif ($agentId -ceq 'kovan') {
                $kovanMatches.Add($candidate)
            }
        }
    }
    $rosterEvidence = [Collections.Generic.List[string]]::new()
    foreach ($agentId in $expectedOlympusAgentIds) {
        $count = $olympusAgentMatches[$agentId].Count
        $rosterEvidence.Add("${agentId}=$count")
        if ($count -eq 0) {
            $failures.Add("roster_${agentId}=missing (matches=0)")
        } elseif ($count -gt 1) {
            $failures.Add("roster_${agentId}=duplicated (matches=$count)")
        }
    }
    $kaelCount = $kaelMatches.Count
    $kovanCount = $kovanMatches.Count
    if ($kaelCount -eq 0) {
        $failures.Add('kael=missing (matches=0)')
    } elseif ($kaelCount -gt 1) {
        $failures.Add("kael=duplicated (matches=$kaelCount)")
    }
    if ($kovanCount -eq 0) {
        $failures.Add('kovan=missing (matches=0)')
    } elseif ($kovanCount -gt 1) {
        $failures.Add("kovan=duplicated (matches=$kovanCount)")
    }

    $toolDecisionEvidence = [Collections.Generic.List[string]]::new()
    $toolDecisionCount = 0
    $toolDenyCount = 0
    $toolResourceProbe = '__authority_tool_resource_probe__'
    foreach ($agentId in $expectedOlympusAgentIds) {
        if ($olympusAgentMatches[$agentId].Count -ne 1) { continue }
        $role = $olympusAgentMatches[$agentId][0]
        $rolePermissionsProperty = $role.PSObject.Properties['permissions']
        if ($null -eq $rolePermissionsProperty) {
            $failures.Add("${agentId}_permissions=missing")
            continue
        }
        $rolePermissions = @($rolePermissionsProperty.Value)
        foreach ($toolAction in $protectedToolActionsV240) {
            $decision = Native-Decision $rolePermissions $toolAction $toolResourceProbe
            $toolDecisionCount++
            $toolDecisionEvidence.Add("${agentId}/${toolAction}=$decision")
            if ($decision -eq 'DENY') {
                $toolDenyCount++
            } else {
                $failures.Add("${agentId}_${toolAction}_effective_decision=$decision (expected DENY)")
            }
        }
    }
    $toolPermissionEvidence = "tool_denies=$toolDenyCount/$($expectedOlympusAgentIds.Count * $protectedToolActionsV240.Count);tool_checks=$toolDecisionCount;additional_agent_ids=$($additionalAgentIds.Count);effective_tool_rules=$($toolDecisionEvidence -join ',')"

    $permissionEvidence = 'not evaluated'
    if ($kovanCount -eq 1) {
        # Index only after proving there is exactly one match.
        $effectiveKovan = $kovanMatches[0]
        $permissionsProperty = $effectiveKovan.PSObject.Properties['permissions']
        if ($null -eq $permissionsProperty) {
            $failures.Add('kovan_permissions=missing')
        } else {
            try {
                $permissions = @($permissionsProperty.Value)
                $taskEditPath = 'src/authority-runtime-probe.txt'
                $projectPluginPath = '.opencode/plugins/project-owned/authority-runtime-probe.ts'
                $activityPath = '.opencode/plugins/olympus-activity/activity.ts'
                $taskEditDecision = Native-Decision $permissions 'edit' $taskEditPath
                $pluginEditDecision = Native-Decision $permissions 'edit' $projectPluginPath
                $activityEditDecision = Native-Decision $permissions 'edit' $activityPath
                $taskEditRuleCount = @($permissions | Where-Object {
                    (Matches-Glob $_.action 'edit') -and (Matches-Glob $_.resource $taskEditPath)
                }).Count
                $editWildcardDeny = @($permissions | Where-Object {
                    $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'deny'
                }).Count
                $editPluginsAsk = @($permissions | Where-Object {
                    $_.action -eq 'edit' -and $_.resource -eq '.opencode/plugins/**' -and $_.effect -eq 'ask'
                }).Count
                $activityDeny = @($permissions | Where-Object {
                    $_.action -eq 'edit' -and $_.resource -eq '.opencode/plugins/olympus-activity/**' -and $_.effect -eq 'deny'
                }).Count
                $externalAsk = @($permissions | Where-Object {
                    $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'ask'
                }).Count
                $externalAllow = @($permissions | Where-Object {
                    $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'allow'
                }).Count
                $permissionEvidence = "task_edit=$taskEditDecision/$taskEditRuleCount rules, project_plugin_edit=$pluginEditDecision, activity_edit=$activityEditDecision, edit_*_deny=$editWildcardDeny/0, edit_plugins_ask=$editPluginsAsk/1, activity_deny=$activityDeny/1, external_ask=$externalAsk/inherited, external_allow=$externalAllow/0"
                if ($editWildcardDeny -ne 0 -or $editPluginsAsk -ne 1 -or $activityDeny -ne 1 -or
                    $externalAllow -ne 0 -or $taskEditDecision -ne 'ALLOW' -or $taskEditRuleCount -eq 0 -or
                    $pluginEditDecision -ne 'ASK' -or $activityEditDecision -ne 'DENY') {
                    $failures.Add('effective_permission_rules_mismatch (' + $permissionEvidence + ')')
                }
            } catch {
                $permissionEvidence = 'evaluation_error=' + (Compact-Evidence $_.Exception.Message)
                $failures.Add('effective_permission_rules_unreadable (' + $permissionEvidence + ')')
            }
        }
    }

    $commandDecisionEvidence = [Collections.Generic.List[string]]::new()
    foreach ($roleName in @('kael','kovan')) {
        if ($roleName -eq 'kael') { $roleMatches = $kaelMatches } else { $roleMatches = $kovanMatches }
        if ($roleMatches.Count -ne 1) { continue }
        $effectiveRole = $roleMatches[0]
        $permissionsProperty = $effectiveRole.PSObject.Properties['permissions']
        if ($null -eq $permissionsProperty) {
            $failures.Add("${roleName}_permissions=missing")
            continue
        }
        try {
            $permissions = @($permissionsProperty.Value)
            foreach ($path in $exactManagedCommandPaths) {
                $decision = Native-Decision $permissions 'edit' $path
                $commandDecisionEvidence.Add("${roleName}:$path=$decision")
                if ($decision -ne 'DENY') {
                    $failures.Add("${roleName}_managed_command_decision=${path}:$decision (expected DENY)")
                }
            }
            if ($roleName -eq 'kael') {
                $editWildcardDeny = @($permissions | Where-Object {
                    $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'deny'
                }).Count
                $shellWildcardDeny = @($permissions | Where-Object {
                    $_.action -eq 'shell' -and $_.resource -eq '*' -and $_.effect -eq 'deny'
                }).Count
                $rootProbeAllow = @($permissions | Where-Object {
                    $_.action -eq 'shell' -and $_.resource -eq 'git rev-parse --show-toplevel' -and $_.effect -eq 'allow'
                }).Count
                $otherShellAllows = @($permissions | Where-Object {
                    $_.action -eq 'shell' -and $_.effect -eq 'allow' -and $_.resource -ne 'git rev-parse --show-toplevel'
                }).Count
                $commandDecisionEvidence.Add("kael:edit_*_deny=$editWildcardDeny;shell_*_deny=$shellWildcardDeny;root_probe_allow=$rootProbeAllow;other_shell_allows=$otherShellAllows")
                if ($editWildcardDeny -lt 1 -or $shellWildcardDeny -lt 1 -or $rootProbeAllow -lt 1 -or
                    $otherShellAllows -ne 0) {
                    $failures.Add('kael_least_privilege_metadata_mismatch')
                }
                foreach ($command in @('git status --short','git branch --show-current','git diff --check','python scripts/check_docs.py')) {
                    $decision = Native-Decision $permissions 'shell' $command
                    $commandDecisionEvidence.Add("kael:shell:$command=$decision")
                    if ($decision -ne 'DENY') {
                        $failures.Add("kael_shell_not_denied=${command}:$decision")
                    }
                }

                $kaelSourceMetadata = Text 'olympus/harnesses/opencode/agent-metadata/kael.md'
                $kaelSourceRules = Read-NativeRules $kaelSourceMetadata @()
                $sourceSerenaDenyRules = @($kaelSourceRules | Where-Object {
                    $_.action -eq 'serena_*' -and $_.resource -eq '*' -and $_.effect -eq 'deny'
                })
                # Keep this rule in Native-Decision; discount it in category counts only when a later category rule controls it.
                $baselineAllowIndices = @(Get-ExactRuleIndices $permissions '*' '*' 'allow')
                $serenaDenyIndices = @(Get-ExactRuleIndices $permissions 'serena_*' '*' 'deny')
                $baselineAllowIndex = if ($baselineAllowIndices.Count -eq 1) { $baselineAllowIndices[0] } else { -1 }
                $serenaBaselineBeforeDeny = $baselineAllowIndex -ge 0 -and
                    $serenaDenyIndices.Count -gt 0 -and $baselineAllowIndex -lt $serenaDenyIndices[-1]
                $serenaNavigationActions = @(
                    'serena_get_symbols_overview','serena_find_symbol','serena_find_referencing_symbols',
                    'serena_find_implementations','serena_find_declaration','serena_get_diagnostics_for_file'
                )
                $serenaDeniedCount = 0
                $serenaDecisionFailures = [Collections.Generic.List[string]]::new()
                foreach ($action in $serenaNavigationActions) {
                    $decision = Native-Decision $permissions $action '*'
                    if ($decision -eq 'DENY') { $serenaDeniedCount++ }
                    else { $serenaDecisionFailures.Add("${action}=$decision") }
                }
                $serenaOverrideRules = [Collections.Generic.List[object]]::new()
                for ($i = 0; $i -lt $permissions.Count; $i++) {
                    $rule = $permissions[$i]
                    $matchesSerena = @($serenaNavigationActions | Where-Object {
                        Matches-Glob $rule.action $_
                    }).Count -gt 0
                    if ($matchesSerena -and $rule.effect -in @('allow','ask') -and
                        -not ($serenaBaselineBeforeDeny -and $i -eq $baselineAllowIndex)) {
                        $serenaOverrideRules.Add($rule)
                    }
                }
                $serenaDenyRules = @($permissions | Where-Object {
                    $rule = $_
                    @($serenaNavigationActions | Where-Object { Matches-Glob $rule.action $_ }).Count -gt 0 -and
                    $rule.effect -eq 'deny'
                })
                $commandDecisionEvidence.Add("kael:serena_nav_denied=$serenaDeniedCount/$($serenaNavigationActions.Count);source_deny=$($sourceSerenaDenyRules.Count);loaded_direct_deny=$($serenaDenyIndices.Count);base_allow_before_deny=$([int]$serenaBaselineBeforeDeny);deny_rules=$($serenaDenyRules.Count);allow_ask_rules=$($serenaOverrideRules.Count)")
                if ($serenaDeniedCount -ne $serenaNavigationActions.Count -or $sourceSerenaDenyRules.Count -ne 1 -or
                    $serenaDenyIndices.Count -eq 0 -or $serenaDenyRules.Count -eq 0 -or
                    $serenaOverrideRules.Count -ne 0) {
                    $failures.Add("kael_serena_effective_decision_mismatch=denied:$serenaDeniedCount/$($serenaNavigationActions.Count);source_deny:$($sourceSerenaDenyRules.Count);loaded_direct_deny:$($serenaDenyIndices.Count);base_allow_before_deny:$([int]$serenaBaselineBeforeDeny);deny_rules:$($serenaDenyRules.Count);allow_ask_rules:$($serenaOverrideRules.Count);non_deny:$($serenaDecisionFailures -join ',')")
                }

                $expectedSpecialists = @('veyra','orin','kovan','nox','vera','thales','atlas','argus','talos','helios')
                $subagentDenyIndices = @(Get-ExactRuleIndices $permissions 'subagent' '*' 'deny')
                $subagentBaselineBeforeDeny = $baselineAllowIndex -ge 0 -and
                    $subagentDenyIndices.Count -gt 0 -and $baselineAllowIndex -lt $subagentDenyIndices[-1]
                $specialistAllowRules = [Collections.Generic.List[object]]::new()
                for ($i = 0; $i -lt $permissions.Count; $i++) {
                    $rule = $permissions[$i]
                    if ((Matches-Glob $rule.action 'subagent') -and $rule.effect -eq 'allow' -and
                        -not ($subagentBaselineBeforeDeny -and $i -eq $baselineAllowIndex)) {
                        $specialistAllowRules.Add($rule)
                    }
                }
                $actualSpecialists = @($specialistAllowRules | ForEach-Object { [string]$_.resource })
                $expandedSpecialistRules = @($specialistAllowRules | Where-Object {
                    $_.action -cne 'subagent' -or $_.resource -notin $expectedSpecialists
                })
                $duplicateSpecialists = $actualSpecialists.Count - @($actualSpecialists | Sort-Object -Unique).Count
                $specialistDecisionFailures = [Collections.Generic.List[string]]::new()
                foreach ($specialist in $expectedSpecialists) {
                    $decision = Native-Decision $permissions 'subagent' $specialist
                    if ($decision -ne 'ALLOW') { $specialistDecisionFailures.Add("${specialist}=$decision") }
                }
                $unlistedSpecialistDecision = Native-Decision $permissions 'subagent' '__authority_unlisted_specialist__'
                $commandDecisionEvidence.Add("kael:subagent_allow_rules=$($specialistAllowRules.Count)/$($expectedSpecialists.Count);named_allow=$($expectedSpecialists.Count - $specialistDecisionFailures.Count)/$($expectedSpecialists.Count);expanded=$($expandedSpecialistRules.Count);duplicates=$duplicateSpecialists;base_allow_before_deny=$([int]$subagentBaselineBeforeDeny);unlisted=$unlistedSpecialistDecision")
                if ($specialistAllowRules.Count -ne $expectedSpecialists.Count -or
                    $expandedSpecialistRules.Count -ne 0 -or $duplicateSpecialists -ne 0 -or
                    $specialistDecisionFailures.Count -ne 0 -or $unlistedSpecialistDecision -ne 'DENY') {
                    $failures.Add("kael_subagent_allowlist_mismatch=rules:$($specialistAllowRules.Count)/$($expectedSpecialists.Count);expanded:$($expandedSpecialistRules.Count);duplicates:$duplicateSpecialists;base_allow_before_deny:$([int]$subagentBaselineBeforeDeny);unlisted:$unlistedSpecialistDecision;non_allow:$($specialistDecisionFailures -join ',')")
                }

                $sourceExternalRules = @($kaelSourceRules | Where-Object {
                    Matches-Glob $_.action 'external_directory'
                })
                $permissionConfigText = (Text 'olympus/harnesses/opencode/config.jsonc') -replace '(?m)^\s*//.*(?:\r?\n|$)', ''
                $permissionConfig = ConvertFrom-Json -InputObject $permissionConfigText -Depth 100 -ErrorAction Stop
                $expectedInheritedExternalRules = @($permissionConfig.permissions | Where-Object {
                    Matches-Glob $_.action 'external_directory'
                })
                $externalAskIndices = @(Get-ExactRuleIndices $permissions 'external_directory' '*' 'ask')
                $externalBaselineBeforeAsk = $baselineAllowIndex -ge 0 -and
                    $externalAskIndices.Count -gt 0 -and $baselineAllowIndex -lt $externalAskIndices[-1]
                $loadedExternalRuleList = [Collections.Generic.List[object]]::new()
                for ($i = 0; $i -lt $permissions.Count; $i++) {
                    $rule = $permissions[$i]
                    if ((Matches-Glob $rule.action 'external_directory') -and
                        -not ($externalBaselineBeforeAsk -and $i -eq $baselineAllowIndex)) {
                        $loadedExternalRuleList.Add($rule)
                    }
                }
                $loadedExternalRules = $loadedExternalRuleList.ToArray()
                $expectedExternalKeys = @($expectedInheritedExternalRules | ForEach-Object {
                    "$($_.action)|$($_.resource)|$($_.effect)"
                })
                $loadedExternalKeys = @($loadedExternalRules | ForEach-Object {
                    "$($_.action)|$($_.resource)|$($_.effect)"
                })
                $missingExternalRules = @($expectedExternalKeys | Where-Object { $_ -notin $loadedExternalKeys })
                $unexpectedExternalRules = @($loadedExternalKeys | Where-Object { $_ -notin $expectedExternalKeys })
                $loadedExternalAllows = @($loadedExternalRules | Where-Object { $_.effect -eq 'allow' })
                $externalDecision = if ($loadedExternalRules.Count -gt 0) {
                    Native-Decision $permissions 'external_directory' 'C:\fixture\external\authority-probe.txt'
                } else { 'NOT_OBSERVABLE' }
                $expectedExternalShape = $expectedInheritedExternalRules.Count -eq 1 -and
                    $expectedInheritedExternalRules[0].action -eq 'external_directory' -and
                    $expectedInheritedExternalRules[0].resource -eq '*' -and
                    $expectedInheritedExternalRules[0].effect -eq 'ask'
                $commandDecisionEvidence.Add("kael:external_directory=$externalDecision;source_agent_rules=$($sourceExternalRules.Count);inherited_rules=$($expectedInheritedExternalRules.Count);loaded_category_rules=$($loadedExternalRules.Count);missing=$($missingExternalRules.Count);unexpected=$($unexpectedExternalRules.Count);category_allow=$($loadedExternalAllows.Count);base_allow_before_ask=$([int]$externalBaselineBeforeAsk);read_question=NOT_ASSESSED")
                if ($sourceExternalRules.Count -ne 0) {
                    $failures.Add('kael_external_directory_mismatch=source_agent_rules=' + $sourceExternalRules.Count)
                } elseif (-not $expectedExternalShape) {
                    $failures.Add("kael_external_directory_inherited_source_mismatch=expected_one_wildcard_ask;rules=$($expectedExternalKeys -join ',')")
                } elseif ($loadedExternalRules.Count -eq 0) {
                    $failures.Add('kael_external_directory_not_observable=debug_agents_has_no_matching_rules;source_agent_rules=' + $sourceExternalRules.Count)
                } elseif ($externalDecision -ne 'ASK' -or $loadedExternalAllows.Count -ne 0 -or
                    $loadedExternalRules.Count -ne $expectedInheritedExternalRules.Count -or
                    $missingExternalRules.Count -ne 0 -or $unexpectedExternalRules.Count -ne 0) {
                    $failures.Add("kael_external_directory_mismatch=decision:$externalDecision;source_agent_rules:$($sourceExternalRules.Count);inherited_rules:$($expectedInheritedExternalRules.Count);loaded_category_rules:$($loadedExternalRules.Count);missing:$($missingExternalRules -join ',');unexpected:$($unexpectedExternalRules -join ',');category_allow:$($loadedExternalAllows.Count);base_allow_before_ask:$([int]$externalBaselineBeforeAsk)")
                }
            }
            $expectedControl = if ($roleName -eq 'kael') { 'DENY' } else { 'ASK' }
            $controls = @(
                '.opencode/commands/project-owned.md',
                '.opencode/commands/speckit.plan.md',
                ($exactManagedCommandPaths[0] + '.backup')
            )
            foreach ($path in $controls) {
                $decision = Native-Decision $permissions 'edit' $path
                $commandDecisionEvidence.Add("${roleName}:$path=$decision")
                if ($decision -ne $expectedControl) {
                    $failures.Add("${roleName}_unrelated_command_decision=${path}:$decision (expected $expectedControl)")
                }
            }
        } catch {
            $commandDecisionEvidence.Add("$roleName=evaluation_error")
            $failures.Add("${roleName}_command_permission_evaluation_error=" + (Compact-Evidence $_.Exception.Message))
        }
    }

    $runtimeExitEvidence = if ($null -eq $runtimeExit) { '<unavailable>' } else { [string]$runtimeExit }
    $failureEvidence = if ($failures.Count -eq 0) { 'none' } else { $failures -join ', ' }
    $evidence = "runtime_exit=$runtimeExitEvidence; json_parseable=$runtimeJsonParseable; json_root=$runtimeJsonRootType; olympus_roster=$($rosterEvidence -join ','); additional_agent_ids=$($additionalAgentIds.Count); kael_matches=$kaelCount; kovan_matches=$kovanCount; tool_permissions=$toolPermissionEvidence; permission_rules=$permissionEvidence; command_decisions=$($commandDecisionEvidence -join ','); stderr=$(Compact-Evidence $runtimeStderr); failures=$failureEvidence"
    [pscustomobject]@{ passed=($failures.Count -eq 0); evidence=$evidence }
}

function Test-AuthorityPathWithin([string]$Path, [string]$Base) {
    $separators = [char[]]@([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar)
    $candidate = [IO.Path]::GetFullPath($Path).TrimEnd($separators)
    $basePath = [IO.Path]::GetFullPath($Base).TrimEnd($separators)
    return $candidate.Equals($basePath,[StringComparison]::OrdinalIgnoreCase) -or
        $candidate.StartsWith($basePath + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)
}

function Assert-AuthorityNoReparsePoints([string]$Path, [switch]$Recursive) {
    $full = [IO.Path]::GetFullPath($Path)
    $volumeRoot = [IO.Path]::GetPathRoot($full)
    $parts = $full.Substring($volumeRoot.Length).Split(
        [char[]]@([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar),
        [StringSplitOptions]::RemoveEmptyEntries)
    $current = $volumeRoot
    foreach ($part in $parts) {
        $current = Join-Path $current $part
        if (-not (Test-Path -LiteralPath $current)) { continue }
        $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw ('AUTHORITY_FIXTURE_REPARSE_POINT: ' + $item.FullName)
        }
    }
    if ($Recursive -and (Test-Path -LiteralPath $full -PathType Container)) {
        foreach ($item in @(Get-ChildItem -LiteralPath $full -Force -Recurse -ErrorAction Stop)) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw ('AUTHORITY_FIXTURE_REPARSE_POINT: ' + $item.FullName)
            }
        }
    }
}

function Get-AuthorityPython311 {
    foreach ($name in @('python3.11','python3','python')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -eq $command) { continue }
        try {
            $probe = @(& $command.Source -B -c 'import json,sys; print(json.dumps({"executable":sys.executable,"version":list(sys.version_info[:3])}))' 2>$null)
            $probeExit = $LASTEXITCODE
            if ($probeExit -ne 0 -or $probe.Count -eq 0) { continue }
            $details = ($probe -join "`n") | ConvertFrom-Json -Depth 5 -ErrorAction Stop
            $version = @($details.version | ForEach-Object { [int]$_ })
            if ($version.Count -lt 2 -or $version[0] -lt 3 -or ($version[0] -eq 3 -and $version[1] -lt 11)) { continue }
            $executable = [IO.Path]::GetFullPath([string]$details.executable)
            if (Test-Path -LiteralPath $executable -PathType Leaf) { return $executable }
        } catch { }
    }
    throw 'AUTHORITY_RUNTIME_SETUP_FAILED: Python 3.11+ executable could not be resolved before process isolation.'
}

function Get-AuthorityOpenCodeExecutable {
    $applications = @(Get-Command 'opencode.exe' -CommandType Application -ErrorAction SilentlyContinue)
    if ($applications.Count -gt 0) { return [IO.Path]::GetFullPath($applications[0].Source) }

    $command = Get-Command opencode -ErrorAction Stop
    $wrapperRoot = Split-Path -Parent $command.Source
    if ([IO.Path]::GetExtension($command.Source) -in @('.ps1','.cmd','.bat')) {
        $bundledExe = Join-Path $wrapperRoot 'node_modules/@opencode/cli/bin/opencode.exe'
        if (Test-Path -LiteralPath $bundledExe -PathType Leaf) { return [IO.Path]::GetFullPath($bundledExe) }
    }
    if ($command.CommandType -eq [Management.Automation.CommandTypes]::Application -and
        [IO.Path]::GetExtension($command.Source) -ieq '.exe') { return [IO.Path]::GetFullPath($command.Source) }
    throw 'AUTHORITY_RUNTIME_CLI_UNRESOLVED: Could not resolve the real OpenCode executable.'
}

function Set-AuthorityChildEnvironment(
    [Diagnostics.ProcessStartInfo]$StartInfo,
    [string]$Root,
    [string]$MockBin = '',
    [switch]$MockBootstrap,
    [string]$GitConfig = '',
    [string]$GitTemplate = '',
    [string]$OpenCodePassword = ''
) {
    $homePath = Join-Path $Root 'home'
    $isolatedTemp = Join-Path $Root 'temp'
    $xdgConfig = Join-Path $Root 'xdg-config'
    $xdgData = Join-Path $Root 'xdg-data'
    $xdgCache = Join-Path $Root 'xdg-cache'
    $xdgState = Join-Path $Root 'xdg-state'
    $appData = Join-Path $homePath 'AppData/Roaming'
    $localAppData = Join-Path $homePath 'AppData/Local'
    foreach ($path in @($homePath,$isolatedTemp,$xdgConfig,$xdgData,$xdgCache,$xdgState,$appData,$localAppData)) {
        [IO.Directory]::CreateDirectory($path) | Out-Null
    }

    $preserved = [ordered]@{}
    foreach ($key in @('PATH','SystemRoot','WINDIR','COMSPEC','PATHEXT')) {
        $value = [Environment]::GetEnvironmentVariable($key,'Process')
        if (-not [string]::IsNullOrWhiteSpace($value)) { $preserved[$key] = $value }
    }
    if (-not $preserved.Contains('PATH') -or -not $preserved.Contains('SystemRoot')) {
        throw 'AUTHORITY_RUNTIME_ENVIRONMENT_INVALID: PATH and SystemRoot are required on Windows.'
    }

    $StartInfo.Environment.Clear()
    foreach ($key in $preserved.Keys) { $StartInfo.Environment[$key] = [string]$preserved[$key] }
    $drive = [IO.Path]::GetPathRoot($homePath).TrimEnd([char[]]@('\','/'))
    $StartInfo.Environment['HOME'] = [IO.Path]::GetFullPath($homePath)
    $StartInfo.Environment['USERPROFILE'] = [IO.Path]::GetFullPath($homePath)
    $StartInfo.Environment['HOMEDRIVE'] = $drive
    $StartInfo.Environment['HOMEPATH'] = $homePath.Substring($drive.Length)
    $StartInfo.Environment['APPDATA'] = [IO.Path]::GetFullPath($appData)
    $StartInfo.Environment['LOCALAPPDATA'] = [IO.Path]::GetFullPath($localAppData)
    $StartInfo.Environment['XDG_CONFIG_HOME'] = [IO.Path]::GetFullPath($xdgConfig)
    $StartInfo.Environment['XDG_DATA_HOME'] = [IO.Path]::GetFullPath($xdgData)
    $StartInfo.Environment['XDG_CACHE_HOME'] = [IO.Path]::GetFullPath($xdgCache)
    $StartInfo.Environment['XDG_STATE_HOME'] = [IO.Path]::GetFullPath($xdgState)
    $StartInfo.Environment['TEMP'] = [IO.Path]::GetFullPath($isolatedTemp)
    $StartInfo.Environment['TMP'] = [IO.Path]::GetFullPath($isolatedTemp)
    if ($MockBootstrap) {
        $StartInfo.Environment['PATH'] = [IO.Path]::GetFullPath($MockBin) + [IO.Path]::PathSeparator + [string]$preserved['PATH']
    }
    if ($GitConfig) {
        $StartInfo.Environment['GIT_CONFIG_NOSYSTEM'] = '1'
        $StartInfo.Environment['GIT_CONFIG_GLOBAL'] = [IO.Path]::GetFullPath($GitConfig)
    }
    if ($GitTemplate) { $StartInfo.Environment['GIT_TEMPLATE_DIR'] = [IO.Path]::GetFullPath($GitTemplate) }
    if (-not [string]::IsNullOrWhiteSpace($OpenCodePassword)) {
        $StartInfo.Environment['OPENCODE_PASSWORD'] = $OpenCodePassword
    }
}

function Invoke-AuthorityCapturedProcess(
    [string]$Executable,
    [string[]]$Arguments,
    [string]$WorkingDirectory,
    [string]$Root,
    [switch]$MockBootstrap,
    [string]$MockBin = '',
    [string]$GitConfig = '',
    [string]$GitTemplate = '',
    [string]$OpenCodePassword = ''
) {
    $startInfo = [Diagnostics.ProcessStartInfo]::new([IO.Path]::GetFullPath($Executable))
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.WorkingDirectory = [IO.Path]::GetFullPath($WorkingDirectory)
    foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add([string]$argument) }
    Set-AuthorityChildEnvironment $startInfo $Root $MockBin -MockBootstrap:$MockBootstrap -GitConfig $GitConfig -GitTemplate $GitTemplate `
        -OpenCodePassword $OpenCodePassword
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        [void]$process.Start()
        $startedUtc = $process.StartTime.ToUniversalTime()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(120000)) {
            try { $process.Kill($true) }
            catch {
                if (-not $process.HasExited) {
                    throw ('AUTHORITY_RUNTIME_PROCESS_CLEANUP_FAILED: timed-out process could not be killed (pid=' +
                        $process.Id + '; executable=' + $Executable + '; kill_error=' + (Compact-Evidence $_.Exception.Message) + ')')
                }
            }
            if (-not $process.HasExited -and -not $process.WaitForExit(30000)) {
                throw ('AUTHORITY_RUNTIME_PROCESS_CLEANUP_FAILED: timed-out process tree remained active after kill (pid=' +
                    $process.Id + '; executable=' + $Executable + ')')
            }
            throw ('AUTHORITY_RUNTIME_PROCESS_TIMEOUT: ' + $Executable + ' ' + ($Arguments -join ' '))
        }
        $process.WaitForExit()
        $completedUtc = $process.ExitTime.ToUniversalTime()
        return [pscustomobject]@{
            ExitCode=$process.ExitCode
            Stdout=$stdoutTask.GetAwaiter().GetResult()
            Stderr=$stderrTask.GetAwaiter().GetResult()
            Pid=$process.Id
            WorkingDirectory=$startInfo.WorkingDirectory
            StartedUtc=$startedUtc
            CompletedUtc=$completedUtc
        }
    } finally { $process.Dispose() }
}

function Assert-AuthorityNoOpenCodeChild([object]$Invocation, [string]$Executable) {
    try {
        $children = @(Get-CimInstance Win32_Process -Filter ("ParentProcessId = {0}" -f [int]$Invocation.Pid) -ErrorAction Stop)
    } catch {
        throw ('AUTHORITY_RUNTIME_CHILD_PROCESS_CHECK_FAILED: parent_pid=' + $Invocation.Pid +
            '; query_error=' + (Compact-Evidence $_.Exception.Message))
    }
    $expectedExecutable = [IO.Path]::GetFullPath($Executable)
    $lingering = [Collections.Generic.List[string]]::new()
    foreach ($child in $children) {
        if ([string]::IsNullOrWhiteSpace([string]$child.ExecutablePath)) {
            throw ('AUTHORITY_RUNTIME_CHILD_PROCESS_CHECK_FAILED: direct child path unavailable (parent_pid=' +
                $Invocation.Pid + '; child_pid=' + $child.ProcessId + ')')
        }
        $childExecutable = [IO.Path]::GetFullPath([string]$child.ExecutablePath)
        if (-not [string]::Equals($childExecutable,$expectedExecutable,[StringComparison]::OrdinalIgnoreCase)) { continue }
        if ($null -eq $child.CreationDate) {
            throw ('AUTHORITY_RUNTIME_CHILD_PROCESS_CHECK_FAILED: OpenCode child creation time unavailable (parent_pid=' +
                $Invocation.Pid + '; child_pid=' + $child.ProcessId + ')')
        }
        $childCreatedUtc = ([datetime]$child.CreationDate).ToUniversalTime()
        if ($childCreatedUtc -ge $Invocation.StartedUtc.AddSeconds(-1) -and
            $childCreatedUtc -le $Invocation.CompletedUtc.AddSeconds(1)) {
            $lingering.Add(([string]$child.ProcessId) + '@' + $childExecutable)
        }
    }
    if ($lingering.Count -gt 0) {
        throw ('AUTHORITY_RUNTIME_CHILD_PROCESS_REMAINS: parent_pid=' + $Invocation.Pid +
            '; children=' + ($lingering -join ', '))
    }
    Write-Output ('AUTHORITY_RUNTIME_CHILD_PROCESS_CHECK: PASS (parent_pid=' + $Invocation.Pid + '; direct_OpenCode_children=0)')
}

function Assert-AuthorityOwnedServer([object]$Server, [string]$RegistryPath) {
    if ($Server.Process.HasExited) {
        throw ('AUTHORITY_RUNTIME_SERVER_NOT_ALIVE: owned_pid=' + $Server.Process.Id + '; url=' + $Server.Url)
    }
    if (-not (Test-Path -LiteralPath $RegistryPath -PathType Leaf)) {
        throw ('AUTHORITY_RUNTIME_SERVER_REGISTRY_MISSING: ' + $RegistryPath)
    }
    try {
        $registry = [IO.File]::ReadAllText($RegistryPath) | ConvertFrom-Json -Depth 20 -ErrorAction Stop
    } catch {
        throw ('AUTHORITY_RUNTIME_SERVER_REGISTRY_INVALID: ' + (Compact-Evidence $_.Exception.Message))
    }
    $pidProperty = $registry.PSObject.Properties['pid']
    $urlProperty = $registry.PSObject.Properties['url']
    $versionProperty = $registry.PSObject.Properties['version']
    $passwordProperty = $registry.PSObject.Properties['password']
    if ($null -eq $pidProperty -or $null -eq $urlProperty -or $null -eq $versionProperty -or $null -eq $passwordProperty -or
        [int]$pidProperty.Value -ne [int]$Server.Process.Id -or
        -not [string]::Equals([string]$urlProperty.Value,[string]$Server.Url,[StringComparison]::OrdinalIgnoreCase) -or
        [string]::IsNullOrWhiteSpace([string]$versionProperty.Value) -or
        [string]::IsNullOrWhiteSpace([string]$passwordProperty.Value)) {
        throw ('AUTHORITY_RUNTIME_SERVER_REGISTRY_MISMATCH: expected_pid=' + $Server.Process.Id + '; expected_url=' + $Server.Url +
            '; registry_pid=' + $(if ($null -eq $pidProperty) { '<missing>' } else { [string]$pidProperty.Value }) +
            '; registry_url=' + $(if ($null -eq $urlProperty) { '<missing>' } else { [string]$urlProperty.Value }))
    }
    try {
        $ownedListeners = @(Get-NetTCPConnection -ErrorAction Stop | Where-Object {
            [int]$_.OwningProcess -eq [int]$Server.Process.Id -and
            $_.State -eq 'Listen' -and
            [string]::Equals([string]$_.LocalAddress,'127.0.0.1',[StringComparison]::OrdinalIgnoreCase) -and
            [int]$_.LocalPort -eq [int]$Server.Port
        })
    } catch {
        throw ('AUTHORITY_RUNTIME_SERVER_LISTENER_CHECK_FAILED: ' + (Compact-Evidence $_.Exception.Message))
    }
    if ($ownedListeners.Count -eq 0) {
        throw ('AUTHORITY_RUNTIME_SERVER_LISTENER_MISMATCH: expected_pid=' + $Server.Process.Id +
            '; expected_url=' + $Server.Url + '; expected_port=' + $Server.Port)
    }
    Write-Output ('AUTHORITY_RUNTIME_SERVER_REGISTRY: PASS (pid=' + $Server.Process.Id + '; url=' + $Server.Url + '; version/password=present)')
    Write-Output ('AUTHORITY_RUNTIME_SERVER_LISTENER: PASS (pid=' + $Server.Process.Id + '; address=127.0.0.1; port=' + $Server.Port + ')')
}

function Stop-AuthorityOwnedServer([object]$Server) {
    $process = $Server.Process
    $processId = [int]$process.Id
    $failures = [Collections.Generic.List[string]]::new()
    $processExited = $false
    $processExitCode = $null
    try {
        if (-not $process.HasExited) {
            try { $process.Kill($true) }
            catch {
                if (-not $process.HasExited) { $failures.Add('owned process-tree kill_error=' + (Compact-Evidence $_.Exception.Message)) }
            }
        }
        if (-not $process.WaitForExit(30000)) {
            $failures.Add('owned server process remained active after bounded wait')
        } elseif ($process.HasExited) {
            $processExited = $true
            $processExitCode = [int]$process.ExitCode
        } else { $failures.Add('owned server process exit could not be confirmed') }
    } catch { $failures.Add($_.Exception.Message) }

    $streamResults = [ordered]@{ readiness='not_started'; stdout='not_started'; stderr='not_started' }
    $streamsDrained = $true
    foreach ($stream in @(
        @{ Name='readiness'; Task=$Server.ReadinessTask },
        @{ Name='stdout'; Task=$Server.StdoutTailTask },
        @{ Name='stderr'; Task=$Server.StderrTask }
    )) {
        if ($null -eq $stream.Task) { continue }
        try {
            if (-not $stream.Task.Wait(10000)) {
                $streamResults[$stream.Name] = 'timeout'
                $streamsDrained = $false
                $failures.Add($stream.Name + ' stream did not close after process exit')
            } else {
                $null = $stream.Task.GetAwaiter().GetResult()
                $streamResults[$stream.Name] = 'drained'
            }
        } catch {
            $streamResults[$stream.Name] = 'error'
            $streamsDrained = $false
            $failures.Add($stream.Name + '_drain_error=' + (Compact-Evidence $_.Exception.Message))
        }
    }

    Write-Output ('AUTHORITY_RUNTIME_SERVER_STOP: pid=' + $processId + '; process_exited=' + $processExited +
        '; exit_code=' + $(if ($null -eq $processExitCode) { '<unavailable>' } else { [string]$processExitCode }) +
        '; readiness=' + $streamResults.readiness + '; stdout=' + $streamResults.stdout + '; stderr=' + $streamResults.stderr)
    try { $process.Dispose() } catch { $failures.Add('process_dispose_error=' + (Compact-Evidence $_.Exception.Message)) }
    if ($failures.Count -gt 0) {
        throw ('AUTHORITY_RUNTIME_SERVER_CLEANUP_FAILED: pid=' + $processId + '; failures=' + ($failures -join '; '))
    }
    Write-Output ('AUTHORITY_RUNTIME_SERVER_CLEANUP: PASS (owned_pid=' + $processId +
        '; process_exit_confirmed=YES; streams=drained)')
}

function Get-AuthorityResolvedPaths([string]$Text) {
    $paths = [ordered]@{}
    foreach ($line in ($Text -split "`r?`n")) {
        $match = [regex]::Match([string]$line,'^\s*(?<name>[A-Za-z][A-Za-z0-9_-]*)\s{2,}(?<path>.+?)\s*$')
        if (-not $match.Success) { continue }
        $name = $match.Groups['name'].Value.ToLowerInvariant()
        $value = $match.Groups['path'].Value.Trim()
        if (-not [IO.Path]::IsPathFullyQualified($value)) { throw "AUTHORITY_RUNTIME_PATHS_FAILED: $name is not an absolute path: $value" }
        if ($paths.Contains($name)) { throw "AUTHORITY_RUNTIME_PATHS_FAILED: duplicate path entry $name." }
        $paths[$name] = [IO.Path]::GetFullPath($value)
    }
    return ,$paths
}

function Invoke-IsolatedAuthorityRuntime {
    $qualificationBase = 'C:\Users\Public\olympus-authority-qualification'
    $fixtureId = [guid]::NewGuid().ToString('N')
    $fixtureRoot = Join-Path $qualificationBase $fixtureId
    $rootCreated = $false
    $primaryFailure = ''
    $cleanupFailure = ''
    $ownedServer = $null
    $serverCleanupFailed = $false
    try {
        if (-not (Test-Path -LiteralPath 'C:\Users\Public' -PathType Container)) {
            throw 'AUTHORITY_RUNTIME_SETUP_FAILED: C:\Users\Public is unavailable.'
        }
        Assert-AuthorityNoReparsePoints $qualificationBase
        [IO.Directory]::CreateDirectory($qualificationBase) | Out-Null
        Assert-AuthorityNoReparsePoints $qualificationBase
        if (Test-Path -LiteralPath $fixtureRoot) { throw 'AUTHORITY_RUNTIME_SETUP_FAILED: generated fixture ID already exists.' }
        [IO.Directory]::CreateDirectory($fixtureRoot) | Out-Null
        $rootCreated = $true
        Assert-AuthorityNoReparsePoints $fixtureRoot

        $sourceRoot = Join-Path $fixtureRoot 'source'
        $projectRoot = Join-Path $fixtureRoot 'project'
        $mockBin = Join-Path $fixtureRoot 'bootstrap-mock-bin'
        $homePath = Join-Path $fixtureRoot 'home'
        $isolatedTemp = Join-Path $fixtureRoot 'temp'
        $xdgConfig = Join-Path $fixtureRoot 'xdg-config'
        $xdgData = Join-Path $fixtureRoot 'xdg-data'
        $xdgCache = Join-Path $fixtureRoot 'xdg-cache'
        $xdgState = Join-Path $fixtureRoot 'xdg-state'
        $mockLog = Join-Path $fixtureRoot 'bootstrap-opencode.log'
        $gitTemplate = Join-Path $fixtureRoot 'empty-git-template'
        $gitConfig = Join-Path $fixtureRoot 'empty-gitconfig'
        foreach ($path in @($sourceRoot,$projectRoot,$mockBin,$gitTemplate)) { [IO.Directory]::CreateDirectory($path) | Out-Null }
        [IO.File]::WriteAllText($gitConfig,'', [Text.UTF8Encoding]::new($false))
        Assert-AuthorityNoReparsePoints $fixtureRoot -Recursive

        $canonicalSources = Join-Path $root 'olympus'
        $rendererSource = Join-Path $root 'scripts/render_harnesses.py'
        $bootstrapSource = Join-Path $root 'scripts/bootstrap.ps1'
        $writerLockSource = Join-Path $root 'scripts/target-writer-lock.ps1'
        $mockSource = Join-Path $root 'tests/release/fixtures/opencode.ps1'
        foreach ($sourcePath in @($canonicalSources,$rendererSource,$bootstrapSource,$writerLockSource,$mockSource)) {
            if (-not (Test-Path -LiteralPath $sourcePath)) { throw ('AUTHORITY_RUNTIME_SETUP_FAILED: required local source is missing: ' + $sourcePath) }
        }
        Copy-Item -LiteralPath $canonicalSources -Destination (Join-Path $sourceRoot 'olympus') -Recurse -Force -ErrorAction Stop
        $stagedScripts = Join-Path $sourceRoot 'scripts'
        [IO.Directory]::CreateDirectory($stagedScripts) | Out-Null
        Copy-Item -LiteralPath $rendererSource -Destination (Join-Path $stagedScripts 'render_harnesses.py') -Force -ErrorAction Stop
        Copy-Item -LiteralPath $bootstrapSource -Destination (Join-Path $stagedScripts 'bootstrap.ps1') -Force -ErrorAction Stop
        Copy-Item -LiteralPath $writerLockSource -Destination (Join-Path $stagedScripts 'target-writer-lock.ps1') -Force -ErrorAction Stop
        Copy-Item -LiteralPath $mockSource -Destination (Join-Path $mockBin 'opencode-fixture.ps1') -Force -ErrorAction Stop

        $pwsh = Join-Path $PSHOME 'pwsh.exe'
        if (-not (Test-Path -LiteralPath $pwsh -PathType Leaf)) { $pwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop).Source }
        $wrapper = "@echo off`r`n>>`"$mockLog`" echo %*`r`n`"$pwsh`" -NoProfile -File `"%~dp0opencode-fixture.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
        [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'),$wrapper,[Text.Encoding]::ASCII)
        Assert-AuthorityNoReparsePoints $fixtureRoot -Recursive

        $python = Get-AuthorityPython311
        $renderer = Join-Path $stagedScripts 'render_harnesses.py'
        $renderOutput = @(& $python -B $renderer render --harness opencode --root $sourceRoot 2>&1)
        $renderExit = [int]$LASTEXITCODE
        if ($renderExit -ne 0) {
            throw ('AUTHORITY_RUNTIME_RENDER_FAILED: exit=' + $renderExit + '; output=' + (Compact-Evidence ($renderOutput -join "`n")))
        }

        $gitCommand = Get-Command 'git.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $gitCommand) { throw 'AUTHORITY_RUNTIME_SETUP_FAILED: git.exe is unavailable.' }
        $gitResult = Invoke-AuthorityCapturedProcess $gitCommand.Source @('-C',$projectRoot,'init','--quiet') $projectRoot $fixtureRoot `
            -GitConfig $gitConfig -GitTemplate $gitTemplate
        if ($gitResult.ExitCode -ne 0) {
            throw ('AUTHORITY_RUNTIME_GIT_INIT_FAILED: exit=' + $gitResult.ExitCode + '; stderr=' + (Compact-Evidence $gitResult.Stderr))
        }

        $gitRootResult = Invoke-AuthorityCapturedProcess $gitCommand.Source @('-C',$projectRoot,'rev-parse','--show-toplevel') $projectRoot $fixtureRoot `
            -GitConfig $gitConfig -GitTemplate $gitTemplate
        if ($gitRootResult.ExitCode -ne 0 -or
            -not [string]::Equals([IO.Path]::GetFullPath($gitRootResult.Stdout.Trim()),[IO.Path]::GetFullPath($projectRoot),[StringComparison]::OrdinalIgnoreCase)) {
            throw ('AUTHORITY_RUNTIME_GIT_ROOT_FAILED: expected=' + $projectRoot + '; actual=' + (Compact-Evidence $gitRootResult.Stdout))
        }
        Assert-AuthorityNoReparsePoints $fixtureRoot -Recursive

        $bootstrap = Join-Path $stagedScripts 'bootstrap.ps1'
        $bootstrapResult = Invoke-AuthorityCapturedProcess $pwsh @('-NoProfile','-File',$bootstrap,'-Target',$projectRoot,'-Harness','opencode') `
            $projectRoot $fixtureRoot -MockBootstrap -MockBin $mockBin -GitConfig $gitConfig -GitTemplate $gitTemplate
        $stubCalls = @()
        if (Test-Path -LiteralPath $mockLog -PathType Leaf) { $stubCalls = @([IO.File]::ReadAllLines($mockLog)) }
        $mockConfigCalls = @($stubCalls | Where-Object { $_.Trim() -eq 'debug config' }).Count
        $mockAgentCalls = @($stubCalls | Where-Object { $_.Trim() -eq 'debug agents' }).Count
        if ($bootstrapResult.ExitCode -ne 0 -or $mockConfigCalls -ne 1 -or $mockAgentCalls -ne 1) {
            throw ('AUTHORITY_RUNTIME_BOOTSTRAP_FAILED: exit=' + $bootstrapResult.ExitCode + '; mock_calls=' + ($stubCalls -join ',') +
                '; output=' + (Compact-Evidence ($bootstrapResult.Stdout + "`n" + $bootstrapResult.Stderr)))
        }
        Write-Output ('AUTHORITY_RUNTIME_SETUP: PASS (renderer=local Python ' + $python + '; bootstrap=local source; project=' + $projectRoot +
            '; git_root=' + $projectRoot + '; mock_stub=' + (Join-Path $mockBin 'opencode.cmd') +
            '; mock_calls=' + ($stubCalls -join ',') + '; real_OpenCode_calls=0)')

        Assert-AuthorityNoReparsePoints $fixtureRoot -Recursive
        $expectedProjectConfig = [IO.Path]::GetFullPath((Join-Path $projectRoot 'opencode.jsonc'))
        if (-not (Test-Path -LiteralPath $expectedProjectConfig -PathType Leaf)) {
            throw ('AUTHORITY_RUNTIME_CONFIG_CONTEXT_FAILED: staged project config is missing: ' + $expectedProjectConfig)
        }
        $realOpenCode = Get-AuthorityOpenCodeExecutable
        Write-Output ('AUTHORITY_RUNTIME_FIXTURE: root=' + $fixtureRoot + '; source=' + $sourceRoot + '; project=' + $projectRoot +
            '; checkout_generated_agents_used=NO; checkout_opencode_tree_copied=NO; runtime_cli=' + $realOpenCode)

        $pathProbe = $null
        $pathInvocationError = ''
        try { $pathProbe = Invoke-AuthorityCapturedProcess $realOpenCode @('debug','paths') $projectRoot $fixtureRoot }
        catch { $pathInvocationError = $_.Exception.Message }
        if ($null -eq $pathProbe) {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug paths pid=<unavailable>; cwd=' + $projectRoot + '; exit=<unavailable>')
            throw ('AUTHORITY_RUNTIME_PATHS_FAILED: invocation_error=' + (Compact-Evidence $pathInvocationError))
        }
        Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug paths pid=' + $pathProbe.Pid + '; cwd=' + $pathProbe.WorkingDirectory + '; exit=' + $pathProbe.ExitCode)
        Assert-AuthorityNoOpenCodeChild $pathProbe $realOpenCode
        if ($pathProbe.ExitCode -ne 0) {
            throw ('AUTHORITY_RUNTIME_PATHS_FAILED: exit=' + $pathProbe.ExitCode + '; stderr=' + (Compact-Evidence $pathProbe.Stderr))
        }
        $resolvedPaths = Get-AuthorityResolvedPaths $pathProbe.Stdout
        $requiredPathRoots = [ordered]@{
            home=$homePath
            config=$xdgConfig
            data=$xdgData
            cache=$xdgCache
            state=$xdgState
            tmp=$isolatedTemp
        }
        foreach ($name in $requiredPathRoots.Keys) {
            if (-not $resolvedPaths.Contains($name)) { throw "AUTHORITY_RUNTIME_PATHS_FAILED: missing required path '$name'." }
            if (-not (Test-AuthorityPathWithin $resolvedPaths[$name] $requiredPathRoots[$name])) {
                throw ("AUTHORITY_RUNTIME_PATHS_FAILED: $name resolved outside its isolated root: " + $resolvedPaths[$name])
            }
        }
        $allIsolatedRoots = @($homePath,$projectRoot,$xdgConfig,$xdgData,$xdgCache,$xdgState,$isolatedTemp)
        foreach ($name in $resolvedPaths.Keys) {
            if (@($allIsolatedRoots | Where-Object { Test-AuthorityPathWithin $resolvedPaths[$name] $_ }).Count -eq 0) {
                throw ("AUTHORITY_RUNTIME_PATHS_FAILED: $name resolved outside fixture/isolation roots: " + $resolvedPaths[$name])
            }
        }
        Write-Output ('AUTHORITY_RUNTIME_PATHS: PASS (home=' + $resolvedPaths.home + '; config=' + $resolvedPaths.config +
            '; data=' + $resolvedPaths.data + '; cache=' + $resolvedPaths.cache + '; state=' + $resolvedPaths.state +
            '; tmp=' + $resolvedPaths.tmp + ')')

        $serverStartInfo = [Diagnostics.ProcessStartInfo]::new([IO.Path]::GetFullPath($realOpenCode))
        $serverStartInfo.UseShellExecute = $false
        $serverStartInfo.CreateNoWindow = $true
        $serverStartInfo.RedirectStandardOutput = $true
        $serverStartInfo.RedirectStandardError = $true
        $serverStartInfo.WorkingDirectory = [IO.Path]::GetFullPath($projectRoot)
        foreach ($argument in @('serve','--service','--hostname','127.0.0.1','--port','0')) {
            $serverStartInfo.ArgumentList.Add([string]$argument)
        }
        Set-AuthorityChildEnvironment $serverStartInfo $fixtureRoot
        $serverProcess = [Diagnostics.Process]::new()
        $serverProcess.StartInfo = $serverStartInfo
        $ownedServer = [pscustomobject]@{
            Process=$serverProcess
            Started=$false
            StartedUtc=$null
            ReadinessTask=$null
            StdoutTailTask=$null
            StderrTask=$null
            Url=$null
            Port=$null
            ReadinessLine=$null
        }
        [void]$serverProcess.Start()
        $ownedServer.Started = $true
        $ownedServer.StartedUtc = $serverProcess.StartTime.ToUniversalTime()
        $ownedServer.StderrTask = $serverProcess.StandardError.ReadToEndAsync()
        $ownedServer.ReadinessTask = $serverProcess.StandardOutput.ReadLineAsync()
        if (-not $ownedServer.ReadinessTask.Wait(30000)) {
            throw 'AUTHORITY_RUNTIME_SERVER_START_FAILED: readiness line timed out after 30 seconds.'
        }
        $ownedServer.ReadinessLine = $ownedServer.ReadinessTask.GetAwaiter().GetResult()
        $readinessMatch = [regex]::Match([string]$ownedServer.ReadinessLine,
            '^server listening on (?<url>http://127\.0\.0\.1:(?<port>[0-9]+))\s*$',
            [Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if (-not $readinessMatch.Success) {
            $startupStderr = if ($ownedServer.StderrTask.IsCompleted) { $ownedServer.StderrTask.GetAwaiter().GetResult() } else { '<still streaming>' }
            throw ('AUTHORITY_RUNTIME_SERVER_START_FAILED: unexpected readiness line=' +
                (Compact-Evidence ([string]$ownedServer.ReadinessLine)) + '; stderr=' + (Compact-Evidence $startupStderr))
        }
        $ownedServer.Port = [int]$readinessMatch.Groups['port'].Value
        $ownedServer.Url = $readinessMatch.Groups['url'].Value
        if ($ownedServer.Port -lt 1 -or $ownedServer.Port -gt 65535) {
            throw ('AUTHORITY_RUNTIME_SERVER_START_FAILED: invalid loopback port ' + $ownedServer.Port)
        }
        if ($serverProcess.HasExited) {
            $startupStderr = if ($ownedServer.StderrTask.IsCompleted) { $ownedServer.StderrTask.GetAwaiter().GetResult() } else { '<unavailable>' }
            throw ('AUTHORITY_RUNTIME_SERVER_START_FAILED: server exited after readiness; stderr=' + (Compact-Evidence $startupStderr))
        }
        $ownedServer.StdoutTailTask = $serverProcess.StandardOutput.ReadToEndAsync()
        Write-Output ('AUTHORITY_RUNTIME_SERVER: READY (pid=' + $serverProcess.Id + '; cwd=' + $serverStartInfo.WorkingDirectory +
            '; url=' + $ownedServer.Url + '; command=serve --service --hostname 127.0.0.1 --port 0)')
        $serviceRegistry = Join-Path (Join-Path $xdgState 'opencode') 'service.json'
        Assert-AuthorityOwnedServer $ownedServer $serviceRegistry

        $configProbe = $null
        $configInvocationError = ''
        try { $configProbe = Invoke-AuthorityCapturedProcess $realOpenCode @('debug','config') $projectRoot $fixtureRoot }
        catch { $configInvocationError = $_.Exception.Message }
        if ($null -eq $configProbe) {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug config pid=<unavailable>; cwd=' + $projectRoot + '; exit=<unavailable>')
            throw ('AUTHORITY_CONFIG_CONTEXT FAIL: opencode debug config invocation failed (runtime_exit=<unavailable>; stderr=<unavailable>; invocation_error=' +
                (Compact-Evidence $configInvocationError) + ')')
        }
        Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug config pid=' + $configProbe.Pid + '; cwd=' + $configProbe.WorkingDirectory + '; exit=' + $configProbe.ExitCode)
        Assert-AuthorityNoOpenCodeChild $configProbe $realOpenCode
        Assert-AuthorityOwnedServer $ownedServer $serviceRegistry
        if ($configProbe.ExitCode -ne 0) {
            throw ('AUTHORITY_CONFIG_CONTEXT FAIL: opencode debug config returned nonzero (runtime_exit=' +
                [string]$configProbe.ExitCode + '; stderr=' + (Compact-Evidence $configProbe.Stderr) +
                '; output=' + (Compact-Evidence $configProbe.Stdout) + ')')
        }
        try {
            $configDocument = ConvertFrom-Json -InputObject $configProbe.Stdout -Depth 100 -NoEnumerate -ErrorAction Stop
            if ($configDocument -isnot [array]) { throw 'debug config JSON root is not an array' }
            $configPaths = @($configDocument | ForEach-Object {
                if ($null -eq $_.path -or -not [string]$_.path) { throw 'config entry has no path' }
                if (-not [IO.Path]::IsPathFullyQualified([string]$_.path)) { throw ('config entry path is not absolute: ' + [string]$_.path) }
                [IO.Path]::GetFullPath([string]$_.path)
            })
        } catch {
            throw ('AUTHORITY_CONFIG_CONTEXT FAIL: opencode debug config returned invalid JSON or path (runtime_exit=0; json_error=' +
                (Compact-Evidence $_.Exception.Message) + '; stderr=' + (Compact-Evidence $configProbe.Stderr) +
                '; output=' + (Compact-Evidence $configProbe.Stdout) + ')')
        }
        $globalConfigRoot = Join-Path $xdgConfig 'opencode'
        $unexpectedConfigPaths = @($configPaths | Where-Object {
            -not (Test-AuthorityPathWithin $_ $projectRoot) -and -not (Test-AuthorityPathWithin $_ $globalConfigRoot)
        })
        $matchingProjectConfig = @($configPaths | Where-Object {
            [string]::Equals($_,$expectedProjectConfig,[StringComparison]::OrdinalIgnoreCase)
        })
        if ($matchingProjectConfig.Count -eq 0 -or $unexpectedConfigPaths.Count -gt 0) {
            throw ('AUTHORITY_CONFIG_CONTEXT FAIL: expected fixture config missing or unexpected external config loaded (expected=' +
                $expectedProjectConfig + '; discovered_paths=' + (Compact-Evidence ($configPaths -join ', ')) +
                '; unexpected_paths=' + (Compact-Evidence ($unexpectedConfigPaths -join ', ')) +
                '; stderr=' + (Compact-Evidence $configProbe.Stderr) + ')')
        }
        Write-Output ('AUTHORITY_CONFIG_CONTEXT: PASS (isolated project config matched=' + $expectedProjectConfig +
            '; allowed_global_config=' + $globalConfigRoot + '; discovered=' + (Compact-Evidence ($configPaths -join ', ')) + ')')

        Assert-AuthorityOwnedServer $ownedServer $serviceRegistry
        try {
            $integrationRegistration = [IO.File]::ReadAllText($serviceRegistry) | ConvertFrom-Json -Depth 20 -ErrorAction Stop
            $integrationPassword = [string]$integrationRegistration.password
        } catch {
            throw ('AUTHORITY_INTEGRATION_CONTEXT_FAILED: isolated service registration is invalid: ' +
                (Compact-Evidence $_.Exception.Message))
        }
        if ([string]::IsNullOrWhiteSpace($integrationPassword)) {
            throw 'AUTHORITY_INTEGRATION_CONTEXT_FAILED: isolated service registration has no password.'
        }
        $directoryHeader = 'x-opencode-directory:' + [Uri]::EscapeDataString($projectRoot)
        # This route verifies fixture context and response shape only; HTTP 200 is not plugin-readiness evidence.
        $integrationArguments = @('api','--server',$ownedServer.Url,'--header',$directoryHeader,'GET','/api/integration')
        $integrationProbe = $null
        $integrationInvocationError = ''
        try {
            $integrationProbe = Invoke-AuthorityCapturedProcess $realOpenCode $integrationArguments $projectRoot $fixtureRoot `
                -OpenCodePassword $integrationPassword
        } catch { $integrationInvocationError = $_.Exception.Message }
        $integrationPassword = $null
        if ($null -eq $integrationProbe) {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode api GET /api/integration pid=<unavailable>; cwd=' + $projectRoot + '; exit=<unavailable>')
            throw ('AUTHORITY_INTEGRATION_CONTEXT FAIL: invocation failed (invocation_error=' +
                (Compact-Evidence $integrationInvocationError) + ')')
        }
        Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode api GET /api/integration pid=' + $integrationProbe.Pid +
            '; cwd=' + $integrationProbe.WorkingDirectory + '; exit=' + $integrationProbe.ExitCode)
        Assert-AuthorityNoOpenCodeChild $integrationProbe $realOpenCode
        Assert-AuthorityOwnedServer $ownedServer $serviceRegistry
        if ($integrationProbe.ExitCode -ne 0) {
            throw ('AUTHORITY_INTEGRATION_CONTEXT FAIL: GET /api/integration returned nonzero (runtime_exit=' +
                [string]$integrationProbe.ExitCode + '; stderr=' + (Compact-Evidence $integrationProbe.Stderr) +
                '; output=' + (Compact-Evidence $integrationProbe.Stdout) + ')')
        }
        try {
            $integrationDocument = ConvertFrom-Json -InputObject $integrationProbe.Stdout -Depth 60 -NoEnumerate -ErrorAction Stop
            if ($null -eq $integrationDocument.location -or $null -eq $integrationDocument.location.directory) {
                throw 'response has no location.directory'
            }
            if ($integrationDocument.data -isnot [array]) { throw 'response data is not an integration array' }
            $effectiveLocation = [string]$integrationDocument.location.directory
            if (-not [IO.Path]::IsPathFullyQualified($effectiveLocation)) {
                throw ('effective location.directory is not absolute: ' + $effectiveLocation)
            }
            $effectiveLocation = [IO.Path]::GetFullPath($effectiveLocation)
        } catch {
            throw ('AUTHORITY_INTEGRATION_CONTEXT FAIL: GET /api/integration returned invalid context (json_error=' +
                (Compact-Evidence $_.Exception.Message) + '; stderr=' + (Compact-Evidence $integrationProbe.Stderr) +
                '; output=' + (Compact-Evidence $integrationProbe.Stdout) + ')')
        }
        if (-not [string]::Equals($effectiveLocation,[IO.Path]::GetFullPath($projectRoot),[StringComparison]::OrdinalIgnoreCase)) {
            throw ('AUTHORITY_INTEGRATION_CONTEXT FAIL: endpoint resolved an unexpected directory (expected=' +
                $projectRoot + '; actual=' + $effectiveLocation + ')')
        }
        Write-Output ('AUTHORITY_INTEGRATION_CONTEXT: PASS (endpoint=GET /api/integration; pid=' + $integrationProbe.Pid +
            '; effective_location=' + $effectiveLocation + '; data_items=' + $integrationDocument.data.Count + ')')

        $runtimeProbe = $null
        $runtimeInvocationError = ''
        try { $runtimeProbe = Invoke-AuthorityCapturedProcess $realOpenCode @('debug','agents') $projectRoot $fixtureRoot }
        catch { $runtimeInvocationError = $_.Exception.Message }
        if ($null -eq $runtimeProbe) {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug agents pid=<unavailable>; cwd=' + $projectRoot + '; exit=<unavailable>')
            $runtimeExit = $null
            $runtimeJson = ''
            $runtimeStderr = ''
        } else {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug agents pid=' + $runtimeProbe.Pid + '; cwd=' + $runtimeProbe.WorkingDirectory + '; exit=' + $runtimeProbe.ExitCode)
            Assert-AuthorityNoOpenCodeChild $runtimeProbe $realOpenCode
            Assert-AuthorityOwnedServer $ownedServer $serviceRegistry
            $runtimeExit = $runtimeProbe.ExitCode
            $runtimeJson = $runtimeProbe.Stdout
            $runtimeStderr = $runtimeProbe.Stderr
        }
        $runtimeInspection = Inspect-EffectiveRules $runtimeExit $runtimeJson $runtimeStderr $runtimeInvocationError
        Write-Output ('AUTH14_EVIDENCE: ' + $runtimeInspection.evidence)
        if (-not $runtimeInspection.passed) {
            throw ('AUTH14_OPENCODE_EFFECTIVE_RULES FAIL: ' + $runtimeInspection.evidence)
        }
        Write-Output 'AUTH14_OPENCODE_EFFECTIVE_RULES PASS'
    } catch {
        $primaryFailure = $_.Exception.Message
    } finally {
        if ($null -ne $ownedServer) {
            if ($ownedServer.Started) {
                try { Stop-AuthorityOwnedServer $ownedServer }
                catch {
                    $serverCleanupFailed = $true
                    $cleanupFailure = $_.Exception.Message
                    Write-Output ('AUTHORITY_RUNTIME_SERVER_CLEANUP: FAIL (' + $cleanupFailure + ')')
                }
            } else {
                try { $ownedServer.Process.Dispose() }
                catch {
                    $serverCleanupFailed = $true
                    $cleanupFailure = 'process_dispose_error=' + $_.Exception.Message
                    Write-Output ('AUTHORITY_RUNTIME_SERVER_CLEANUP: FAIL (' + $cleanupFailure + ')')
                }
            }
        }
        if ($rootCreated) {
            if ($serverCleanupFailed) {
                Write-Output ('AUTHORITY_RUNTIME_CLEANUP: FAIL (fixture retained because owned server cleanup failed: ' + $fixtureRoot + ')')
            } else {
                try {
                    $resolvedBase = [IO.Path]::GetFullPath($qualificationBase).TrimEnd([char[]]@('\','/'))
                    $resolvedTarget = [IO.Path]::GetFullPath($fixtureRoot)
                    if (-not [string]::Equals((Split-Path -Parent $resolvedTarget),$resolvedBase,[StringComparison]::OrdinalIgnoreCase) -or
                        -not [string]::Equals((Split-Path -Leaf $resolvedTarget),$fixtureId,[StringComparison]::OrdinalIgnoreCase) -or
                        -not (Test-AuthorityPathWithin $resolvedTarget $resolvedBase)) {
                        throw ('AUTHORITY_RUNTIME_CLEANUP_TARGET_INVALID: ' + $resolvedTarget)
                    }
                    Assert-AuthorityNoReparsePoints $resolvedTarget -Recursive
                    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force -ErrorAction Stop
                    if (Test-Path -LiteralPath $resolvedTarget) { throw ('fixture still exists after removal: ' + $resolvedTarget) }
                    Write-Output ('AUTHORITY_RUNTIME_CLEANUP: PASS (removed=' + $resolvedTarget + ')')
                } catch {
                    $cleanupFailure = $_.Exception.Message
                    Write-Output ('AUTHORITY_RUNTIME_CLEANUP: FAIL (' + $cleanupFailure + ')')
                }
            }
        }
    }
    if ($primaryFailure -or $cleanupFailure) {
        Write-Output 'AUTHORITY_RUNTIME_ISOLATION: FAIL'
        throw ('AUTHORITY_RUNTIME_ISOLATION FAIL: primary=' + $(if ($primaryFailure) { $primaryFailure } else { 'none' }) +
            '; cleanup=' + $(if ($cleanupFailure) { $cleanupFailure } else { 'PASS' }))
    }
    Write-Output 'AUTHORITY_RUNTIME_ISOLATION: PASS (clean process environments; isolated project config; owned loopback backend; setup stub separated; cleanup verified)'
}

try {
    if ($QualificationSlice -ne 'Runtime') {
    $kael = Text '.opencode/agents/kael.md'
    $kovan = Text '.opencode/agents/kovan.md'
    $kaelPromptSource = Text 'olympus/harnesses/opencode/agent-prompts/kael.md'
    $kovanPromptSource = Text 'olympus/harnesses/opencode/agent-prompts/kovan.md'
    $noxPromptSource = Text 'olympus/harnesses/opencode/agent-prompts/nox.md'
    $authorityPolicy = Text 'olympus/policies/authority.md'
    $kaelSourceMetadata = Text 'olympus/harnesses/opencode/agent-metadata/kael.md'
    $kovanSourceMetadata = Text 'olympus/harnesses/opencode/agent-metadata/kovan.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $configText = (Text 'opencode.jsonc') -replace '(?m)^\s*//.*(?:\r?\n|$)', ''
    $config = $configText | ConvertFrom-Json -Depth 100
    $nativeRules = Read-NativeRules $kovanSourceMetadata @($config.permissions)
    $kaelNativeRules = Read-NativeRules $kaelSourceMetadata @($config.permissions)
    $kaelSourceRules = Read-NativeRules $kaelSourceMetadata @()
    $minimalGlobalText = (Text 'olympus/harnesses/opencode/global-permissions.jsonc') -replace '(?m)^\s*//.*(?:\r?\n|$)', ''
    $minimalGlobal = $minimalGlobalText | ConvertFrom-Json -Depth 100
    $authoritySource = Text 'tests/authority/qualify.ps1'
    $harnessDocs = Text 'docs/HARNESSES.md'
    $rootPath = 'C:\fixture\project'
    $operation = 'WRITE_SCOPE:create-or-update'
    $grant = New-Grant 'kovan' $operation '.opencode/plugins/project-owned/**' $rootPath 'NATIVE_ASK'

    Check 'AUTH0_NATIVE_DEFAULTS_ASK_NOT_DENY' (@($config.permissions | Where-Object {
        $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'ask'
    }).Count -eq 1 -and @($config.permissions | Where-Object {
        $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'ask'
    }).Count -eq 1 -and @($config.permissions | Where-Object {
        $_.action -in @('edit','external_directory') -and $_.resource -eq '*' -and $_.effect -eq 'deny'
    }).Count -eq 0)

    Check 'AUTH0B_KOVAN_NO_BLANKET_EDIT_DENY' (@($nativeRules | Where-Object {
        $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'deny'
    }).Count -eq 0 -and @($nativeRules | Where-Object {
        $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'allow'
    }).Count -eq 1)

    $sourceToolRuleFailures = [Collections.Generic.List[string]]::new()
    $sourceToolDecisions = [Collections.Generic.List[string]]::new()
    $sourceToolDenyCount = 0
    foreach ($roleName in $expectedOlympusAgentIds) {
        $roleSourceRules = Read-NativeRules (Text ('olympus/harnesses/opencode/agent-metadata/' + $roleName + '.md')) @()
        $roleEffectiveRules = Read-NativeRules (Text ('olympus/harnesses/opencode/agent-metadata/' + $roleName + '.md')) @($config.permissions)
        $automationWildcardDenies = @($roleSourceRules | Where-Object {
            $_.action -ceq 'automation_*' -and $_.resource -ceq '*' -and $_.effect -ceq 'deny'
        }).Count
        $browserWildcardDenies = @($roleSourceRules | Where-Object {
            $_.action -ceq 'browser' -and $_.resource -ceq '*' -and $_.effect -ceq 'deny'
        }).Count
        $allActionWildcardDenies = @($roleSourceRules | Where-Object {
            $_.action -ceq '*' -and $_.resource -ceq '*' -and $_.effect -ceq 'deny'
        }).Count
        if ($roleName -cin $newToolDenyAgentIds) {
            if ($automationWildcardDenies -ne 1 -or $browserWildcardDenies -ne 1) {
                $sourceToolRuleFailures.Add("${roleName}:automation_*=$automationWildcardDenies;browser=$browserWildcardDenies")
            }
        } elseif ($allActionWildcardDenies -lt 1 -or $automationWildcardDenies -ne 0 -or $browserWildcardDenies -ne 0) {
            $sourceToolRuleFailures.Add("${roleName}:all_action_deny=$allActionWildcardDenies;redundant_automation=$automationWildcardDenies;redundant_browser=$browserWildcardDenies")
        }
        foreach ($toolAction in $protectedToolActionsV240) {
            $decision = Native-Decision $roleEffectiveRules $toolAction '__authority_tool_resource_probe__'
            $sourceToolDecisions.Add("${roleName}/${toolAction}=$decision")
            if ($decision -eq 'DENY') { $sourceToolDenyCount++ }
            else { $sourceToolRuleFailures.Add("${roleName}/${toolAction}=$decision") }
        }
    }
    Check 'AUTH0C_ALL_OLYMPUS_NATIVE_TOOL_ACTIONS_DENIED' (
        $sourceToolRuleFailures.Count -eq 0 -and
        $sourceToolDenyCount -eq ($expectedOlympusAgentIds.Count * $protectedToolActionsV240.Count) -and
        $sourceToolDecisions.Count -eq ($expectedOlympusAgentIds.Count * $protectedToolActionsV240.Count)
    )
    $kovanToolSourceRules = Read-NativeRules $kovanSourceMetadata @()
    $lateAutomationAllow = @($kovanToolSourceRules) + @([pscustomobject]@{ action='automation_create'; resource='*'; effect='allow' })
    $lateBrowserAllow = @($kovanToolSourceRules) + @([pscustomobject]@{ action='browser'; resource='*'; effect='allow' })
    Check 'AUTH0D_TOOL_DENIES_USE_LAST_MATCH_SEMANTICS' (
        (Native-Decision $kovanToolSourceRules 'automation_create' '__authority_tool_resource_probe__') -eq 'DENY' -and
        (Native-Decision $kovanToolSourceRules 'browser' '__authority_tool_resource_probe__') -eq 'DENY' -and
        (Native-Decision $lateAutomationAllow 'automation_create' '__authority_tool_resource_probe__') -eq 'ALLOW' -and
        (Native-Decision $lateBrowserAllow 'browser' '__authority_tool_resource_probe__') -eq 'ALLOW'
    )

    Check 'AUTH1_NORMAL_IN_SCOPE_NO_QUESTION' ($kael -match 'An assigned worker proceeds directly with its in-scope operation when the\s+effective native\s+permission is ALLOW\.' -and
        (Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null).decision -eq 'ALLOW' -and
        (Native-Decision $nativeRules 'edit' 'src/cart.ts') -eq 'ALLOW' -and
        (Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null).question -eq 0)

    $omittedGrantAllow = Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null $true $true $false @() 'ALLOW'
    $omittedGrantAsk = Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null $true $true $false @() 'ASK'
    $omittedGrantDeny = Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null $true $true $false @() 'DENY'
    $omittedGrantUnowned = Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null $true $false $false @() 'ALLOW'
    $omittedGrantOutOfScope = Decide 'kovan' $operation 'docs/release.md' 'src/**' $rootPath $null $true $true $false @() 'ALLOW'
    $omittedGrantProhibited = Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null $true $true $true @() 'ALLOW'
    Check 'AUTH1B_OMITTED_GRANT_ONLY_FOR_CONFIRMED_ALLOW_OWNED_IN_SCOPE_WORK' (
        $omittedGrantAllow.decision -eq 'ALLOW' -and $omittedGrantAsk.decision -eq 'NEED_AUTHORITY' -and
        $omittedGrantDeny.decision -eq 'DENY' -and $omittedGrantUnowned.decision -eq 'DENY' -and
        $omittedGrantOutOfScope.decision -eq 'NEED_AUTHORITY' -and $omittedGrantProhibited.decision -eq 'DENY' -and
        $kael -match '(?is)confirmed-ALLOW.*?AUTHORITY_GRANT.*?absent heading as `NONE`.*?effective native ALLOW.*?ownership evidence.*?WRITE_SCOPE.*?GIT_SCOPE.*?DO_NOT_TOUCH' -and
        $kovan -match '(?is)heading is\s+absent.*?CONTEXT.*?effective native ALLOW.*?ownership evidence.*?WRITE_SCOPE.*?GIT_SCOPE.*?DO_NOT_TOUCH' -and
        $kovan -match '(?is)exception never applies to\s+`NATIVE_ASK`.*?exact current-task grant')

    $need = Decide 'kovan' $operation 'docs/release.md' 'src/**' $rootPath $null
    Check 'AUTH2_OUT_OF_SCOPE_NEED_AUTHORITY' ($need.decision -eq 'NEED_AUTHORITY' -and
        $kovan -match 'STATUS: NEED_AUTHORITY' -and $kovan -match 'OPERATION:' -and
        $kovan -match 'MINIMUM_SCOPE:' -and $kovan -match 'REPOSITORY_ROOT:' -and
        $kovan -match 'TASK_BLOCKED:')

    $alternateSectionStart = $authorityPolicy.IndexOf('## Out-of-scope task result', [StringComparison]::Ordinal)
    $alternateDefinition = if ($alternateSectionStart -ge 0) { $authorityPolicy.Substring($alternateSectionStart) } else { '' }
    $alternateFields = @('STATUS: NEED_AUTHORITY','OPERATION:','MINIMUM_SCOPE:','REPOSITORY_ROOT:','REASON:','TASK_BLOCKED:')
    $alternateFieldOrderValid = $alternateDefinition.Length -gt 0
    $lastAlternateField = -1
    foreach ($field in $alternateFields) {
        $fieldIndex = $alternateDefinition.IndexOf($field, [StringComparison]::Ordinal)
        if ($fieldIndex -le $lastAlternateField) { $alternateFieldOrderValid = $false }
        $lastAlternateField = $fieldIndex
    }
    $normalizedAlternatePolicy = $alternateDefinition -replace '\s+', ' '
    Check 'AUTH2A_CANONICAL_ALTERNATE_SCOPE_RESULT' ($alternateFieldOrderValid -and
        $normalizedAlternatePolicy -match 'eligible to perform an otherwise legitimate operation.*?outside the current task.s assigned scope.*?operation must remain unattempted' -and
        $normalizedAlternatePolicy -match 'takes precedence over a normal or specialized result format only for that scope gap' -and
        $normalizedAlternatePolicy -match 'creates no authority, approval, retry, or permission to act' -and
        $normalizedAlternatePolicy -match 'native DENY.*?actual pending native ASK event.*?permission rejection/cancellation.*?unknown permission-UI observation' -and
        $normalizedAlternatePolicy -match 'effective native ASK rule.*?not a tool attempt or an actual native ASK event.*?return `NEED_AUTHORITY`' -and
        $normalizedAlternatePolicy -match 'correctly assigns the exact operation.*?actual pending native ASK event.*?not `NEED_AUTHORITY`' -and
        $normalizedAlternatePolicy -match 'does not widen, renew, or transfer a task scope or grant')

    $authorityWorkers = @('veyra','orin','nox','vera','atlas','argus','helios','talos','thales')
    $workerPromptSources = @{}
    foreach ($roleName in $authorityWorkers) {
        $workerPromptSources[$roleName] = Text ('olympus/harnesses/opencode/agent-prompts/' + $roleName + '.md')
    }
    $alternateResultClause = 'For an otherwise role-eligible operation/path outside this task''s exact assigned scope, use the distinct `STATUS: NEED_AUTHORITY` alternate result defined by the `Scope and Authority handoff` section only while the operation remains unattempted; it takes precedence over this normal/specialized result contract for this case only and is not a normal completion/failure status. It grants no authority or retry, does not replace native ASK/DENY/rejection, erase already-applied authorized effects, or apply to role, ownership, or user-prohibition blockers.'
    $workerClauseFailures = @($authorityWorkers | Where-Object {
        ($workerPromptSources[$_] -replace '\s+', ' ') -notmatch [regex]::Escape($alternateResultClause)
    })
    $handoffFields = @('STATUS: NEED_AUTHORITY','OPERATION','MINIMUM_SCOPE','REPOSITORY_ROOT','REASON','TASK_BLOCKED')
    $workerHandoffsValid = $true
    foreach ($roleName in $authorityWorkers) {
        $handoffSplit = $workerPromptSources[$roleName] -split '## Scope and Authority handoff',2
        $handoffBody = if ($handoffSplit.Count -gt 1) { ($handoffSplit[1] -split '\r?\n## ',2)[0] } else { '' }
        foreach ($field in $handoffFields) {
            if ($handoffBody -notmatch [regex]::Escape($field)) { $workerHandoffsValid = $false }
        }
    }
    $kovanSourceNormalized = $kovanPromptSource -replace '\s+', ' '
    $kovanAlternateClause = 'For an otherwise role-eligible operation/path outside this task''s exact assigned scope, use the existing five-field `STATUS: NEED_AUTHORITY` block in Write rules as a separate child result only while that operation remains unattempted. It takes precedence over this normal result contract for that case only and is not a normal completion/failure status. It grants no authority or retry, does not replace native ASK/DENY/rejection, erase already-applied authorized effects, or apply to role, ownership, user-prohibition, or destructive/high-impact blockers.'
    $kovanAlternateFieldsValid = @('STATUS: NEED_AUTHORITY','OPERATION:','MINIMUM_SCOPE:','REPOSITORY_ROOT:','REASON:','TASK_BLOCKED:') |
        Where-Object { $kovanPromptSource -notmatch [regex]::Escape($_) } | Measure-Object | Select-Object -ExpandProperty Count
    $specializedStatusContracts = @(
        @('veyra','STATUS: SUCCESS | PARTIAL | BLOCKED | FAILED'),
        @('orin','STATUS: SUCCESS | PARTIAL | BLOCKED | FAILED'),
        @('nox','STATUS: SUCCESS | PARTIAL | BLOCKED | FAILED'),
        @('vera','STATUS: SUCCESS | PARTIAL | BLOCKED | FAILED'),
        @('atlas','STATUS: PLAN','STATUS: EVIDENCE_REQUEST'),
        @('argus','STATUS: BUG_DIAGNOSIS','STATUS: EVIDENCE_REQUEST','STATUS: NOT_FUNCTIONAL_BUG'),
        @('helios','STATUS: OPTIMIZATION_PROPOSAL','STATUS: DO_NOT_OPTIMIZE','STATUS: EVIDENCE_REQUEST'),
        @('talos','STATUS: SECURITY_DIAGNOSIS','STATUS: EVIDENCE_REQUEST','STATUS: NOT_SECURITY_BUG'),
        @('thales','STATUS: EVIDENCE_REQUEST','STATUS: ADVICE | INCONCLUSIVE | BLOCKED')
    )
    $specializedStatusContractsValid = $true
    foreach ($contract in $specializedStatusContracts) {
        $roleName = $contract[0]
        foreach ($statusField in @($contract | Select-Object -Skip 1)) {
            if ($workerPromptSources[$roleName] -notmatch [regex]::Escape($statusField)) {
                $specializedStatusContractsValid = $false
            }
        }
    }
    Check 'AUTH2B_WORKER_RESULT_PRECEDENCE_AND_EXISTING_FORMATS' (
        $workerClauseFailures.Count -eq 0 -and
        $workerHandoffsValid -and
        $kovanAlternateFieldsValid -eq 0 -and
        $kovanSourceNormalized.Contains($kovanAlternateClause) -and
        $kovanPromptSource -match 'STATUS: NEED_AUTHORITY\s+OPERATION: exact capability and effect required' -and
        $kovanPromptSource -match 'STATUS: SUCCESS \| PARTIAL \| BLOCKED \| FAILED' -and
        $kovanPromptSource -notmatch '(?m)^STATUS: SUCCESS \| PARTIAL \| BLOCKED \| FAILED \| NEED_AUTHORITY\r?$' -and
        $specializedStatusContractsValid
    )

    $normalizedKaelPromptSource = $kaelPromptSource -replace '\s+', ' '
    Check 'AUTH2C_KAEL_RECONCILES_ALTERNATE_RESULT_WITHOUT_NEW_ROOT_STATE' (
        $normalizedKaelPromptSource -match 'consumes each original terminal task-child result once.*?including a `NEED_AUTHORITY` handoff' -and
        $normalizedKaelPromptSource -match 'validates its five exact fields, role eligibility, repository/ownership evidence, user constraints, and scope claim' -and
        $normalizedKaelPromptSource -match 'not a root result, completion state, or task-ledger status.*?leave this root interface and task-ledger status sets unchanged' -and
        $normalizedKaelPromptSource -match 'Allowed STATUS values are PENDING, RUNNING, SUCCESS, FAILED, BLOCKED, and CANCELLED\.' -and
        $kaelPromptSource -match '(?m)^STATUS: SUCCESS \| PARTIAL \| BLOCKED \| FAILED\r?$' -and
        $normalizedKaelPromptSource -match 'Do not ask when native ASK can obtain the exact required human consent'
    )

    $assignedAskPath = '.opencode/plugins/project-owned/index.ts'
    $assignedNativeRule = Native-Decision $nativeRules 'edit' $assignedAskPath
    $approved = Decide 'kovan' $operation $assignedAskPath 'src/**' $rootPath $grant $true $true $false @() $assignedNativeRule
    $assignedAskFlow = Synthetic-ToolFlow $approved.decision
    Check 'AUTH3_EXACT_SCOPE_NATIVE_ASK_GRANT' ($approved.decision -eq 'NATIVE_ASK' -and $approved.reason -eq 'EXACT_NATIVE_ASK_GRANT' -and
        $assignedNativeRule -eq 'ASK' -and $approved.decision -ne 'NEED_AUTHORITY' -and
        $assignedAskFlow.attempted -and $assignedAskFlow.pending -and -not $assignedAskFlow.executed -and
        $assignedAskFlow.question -eq 0 -and -not $assignedAskFlow.fallback -and -not $assignedAskFlow.retry -and
        $grant.agent -eq 'kovan' -and $grant.scope -ceq '.opencode/plugins/project-owned/**' -and
        $grant.repository_root -ceq $rootPath -and $grant.permission_mode -ceq 'NATIVE_ASK' -and
        $grant.lifetime -ceq 'current_task' -and $grant.task_id -ceq 'task-7')

    # Effective rule ASK is not a host event when the sibling scope is unassigned.
    $siblingPath = '.opencode/plugins/sibling/index.ts'
    $siblingNativeRule = Native-Decision $nativeRules 'edit' $siblingPath
    $sibling = Decide 'kovan' $operation $siblingPath 'src/**' $rootPath $grant $true $true $false @() $siblingNativeRule
    Check 'AUTH4_SIBLING_SCOPE_NEEDS_NEW_AUTHORITY' ($sibling.decision -eq 'NEED_AUTHORITY' -and
        $siblingNativeRule -eq 'ASK' -and $sibling.reason -eq 'SCOPE_NOT_DELEGATED' -and
        -not (Synthetic-ToolFlow $sibling.decision).attempted)

    $expired = Decide 'kovan' $operation '.opencode/plugins/foo/index.ts' 'src/**' $rootPath $grant $false
    Check 'AUTH5_CURRENT_TASK_EXPIRY' ($expired.decision -eq 'DENY' -and $expired.reason -eq 'GRANT_EXPIRED_OR_WRONG_TASK' -and
        $kael -match 'A grant expires with this task')

    $prohibited = Decide 'kovan' $operation '.opencode/plugins/project-owned/index.ts' 'src/**' $rootPath $grant $true $true $true
    Check 'AUTH6_EXPLICIT_PROHIBITION_DENY_NO_QUESTION' ($prohibited.decision -eq 'DENY' -and $prohibited.question -eq 0 -and
        -not (Synthetic-ToolFlow $prohibited.decision).attempted -and
        $kael -match '(?s)Explicit user prohibitions.*?override every other outcome' -and $kael -match 'do not modify \.opencode')

    $ownedByManifest = Decide 'kovan' $operation '.opencode/plugins/vendor/loader.ts' 'src/**' $rootPath $grant $true $true $false @('.opencode/plugins/vendor')
    Check 'AUTH7_OLYMPUS_OWNED_GRANT_UNAVAILABLE' ($ownedByManifest.decision -eq 'DENY' -and $ownedByManifest.question -eq 0 -and
        -not (Synthetic-ToolFlow $ownedByManifest.decision).attempted -and
        $kael -match '\.opencode/agents/\*\*' -and $kael -match 'Every manifest-declared\s+Olympus-managed resource is protected')

    $pluginResource = '.opencode/plugins/project-owned/index.ts'
    $pluginNative = Native-Decision $nativeRules 'edit' $pluginResource
    $protectedAdjacent = Native-Decision $nativeRules 'edit' '.opencode/commands/project-owned.md'
    $approvedWrite = Write-Decision $pluginNative 'APPROVE_ONCE'
    $rejectedWrite = Write-Decision $pluginNative 'REJECT'
    $pluginNotOwned = Decide 'kovan' $operation $pluginResource 'src/**' $rootPath $null $true $false
    Check 'AUTH8_PROJECT_PLUGIN_NATIVE_ASK_AND_ONE_SHOT' ($pluginNative -eq 'ASK' -and
        $protectedAdjacent -eq 'ASK' -and $approvedWrite -and -not $rejectedWrite -and
        $pluginNotOwned.decision -eq 'DENY' -and $approved.decision -eq 'NATIVE_ASK' -and
        $kovan -match '\.opencode/plugins/\*\*"\s+effect: ask' -and
        $kovan -match '\.opencode/\*\*"\s+effect: ask')

    $siblingPlugin = Native-Decision $nativeRules 'edit' '.opencode/plugins/sibling/index.ts'
    Check 'AUTH8B_ONE_SHOT_APPROVAL_NOT_SIBLING' ($siblingPlugin -eq 'ASK' -and
        -not (Write-Decision $siblingPlugin 'NONE') -and $approvedWrite)

    $activityPath = '.opencode/plugins/olympus-activity/activity.ts'
    $activity = Decide 'kovan' $operation $activityPath 'src/**' $rootPath $grant
    Check 'AUTH9_ACTIVITY_PLUGIN_DENIED' ($activity.decision -eq 'DENY' -and $activity.reason -eq 'OLYMPUS_OWNED' -and
        (Native-Decision $nativeRules 'edit' $activityPath) -eq 'DENY' -and
        $kael -match '\.opencode/plugins/olympus-activity/\*\*')

    foreach ($path in @('.opencode/agents/kovan.md',
        '.opencode/orchestrator-install.json','.opencode/opencode.json','.opencode/opencode.jsonc',
        '.codex/agents/kovan.toml','.codex/config.toml','CODEX.md',
        'opencode.json','opencode.jsonc')) {
        Check ('AUTH9_NATIVE_DENY_' + ($path -replace '[^A-Za-z0-9]','_')) ((Native-Decision $nativeRules 'edit' $path) -eq 'DENY')
    }

    # Kovan can maintain canonical source when task identity and WRITE_SCOPE are exact.
    # Kael's native edit DENY is independent of that task-level role boundary.
    $canonicalPath = 'olympus/core/models.toml'
    $canonicalDeniedWithoutIdentity = Decide 'kovan' $operation $canonicalPath 'olympus/core/**' $rootPath $null
    $canonicalDeniedWithoutScope = Decide 'kovan' $operation $canonicalPath 'src/**' $rootPath $null $true $true $false @() 'ALLOW' $true
    $canonicalAllowed = Decide 'kovan' $operation $canonicalPath 'olympus/core/**' $rootPath $null $true $true $false @() 'ALLOW' $true
    $canonicalNativeDenied = Decide 'kovan' $operation $canonicalPath 'olympus/core/**' $rootPath $null $true $true $false @() 'DENY' $true
    Check 'AUTH9_CANONICAL_SOURCE_REQUIRES_IDENTITY_SCOPE_AND_NATIVE_PERMISSION' (
        $canonicalDeniedWithoutIdentity.decision -eq 'DENY' -and
        $canonicalDeniedWithoutScope.decision -eq 'NEED_AUTHORITY' -and
        $canonicalAllowed.decision -eq 'ALLOW' -and
        $canonicalNativeDenied.decision -eq 'DENY' -and
        (Native-Decision $nativeRules 'edit' $canonicalPath) -eq 'ALLOW' -and
        (Native-Decision $kaelNativeRules 'edit' $canonicalPath) -eq 'DENY' -and
        $kael -match 'Canonical Olympus source is writable only when target repository'
    )
    $kaelRootProbe = Native-Decision $kaelNativeRules 'shell' 'git rev-parse --show-toplevel'
    $blockedKaelShell = @(
        'git status --short','git branch --show-current','git diff --check',
        'git diff --stat','python scripts/check_docs.py'
    ) | Where-Object {
        (Native-Decision $kaelNativeRules 'shell' $_) -ne 'DENY'
    }
    $kaelEditWildcardDeny = @($kaelNativeRules | Where-Object {
        $_.action -eq 'edit' -and $_.resource -ceq '*' -and $_.effect -eq 'deny'
    }).Count
    $kaelSerenaWildcardDeny = @($kaelSourceRules | Where-Object {
        $_.action -ceq 'serena_*' -and $_.resource -ceq '*' -and $_.effect -eq 'deny'
    }).Count
    Check 'AUTH9E_KAEL_NATIVE_ROOT_PROBE_ONLY' (
        $kaelRootProbe -eq 'ALLOW' -and @($blockedKaelShell).Count -eq 0
    )
    Check 'AUTH9F_KAEL_NATIVE_EDIT_DENIED' (
        $kaelEditWildcardDeny -eq 1 -and
        (Native-Decision $kaelNativeRules 'edit' 'src/cart.ts') -eq 'DENY' -and
        (Native-Decision $kaelNativeRules 'edit' $canonicalPath) -eq 'DENY'
    )
    Check 'AUTH9G_KAEL_SERENA_WILDCARD_DENY' ($kaelSerenaWildcardDeny -eq 1)
    Check 'AUTH9H_MINIMAL_GLOBAL_HAS_NO_SERENA_DEFAULT' (
        @($minimalGlobal.permissions | Where-Object { $_.action -like 'serena_*' }).Count -eq 0
    )

    # Read-only specialists retain native DENY for source and generated assets;
    # Kovan uses task authority for canonical source while Kael stays read-only.
    $readOnlyAgents = @(Get-ChildItem -LiteralPath (Join-Path $root '.opencode/agents') -Filter '*.md' -File |
        Where-Object { $_.BaseName -notin @('kael','kovan') })
    $coreProtectionValid = @($readOnlyAgents | Where-Object {
        $agentRules = Read-NativeRules ([IO.File]::ReadAllText($_.FullName)) @($config.permissions)
        @('olympus/core/models.toml','olympus/roles/kael.md','olympus/policies/authority.md',
          '.codex/config.toml','CODEX.md','scripts/render_harnesses.py' | Where-Object {
            (Native-Decision $agentRules 'edit' $_) -ne 'DENY'
        }).Count -gt 0
    }).Count -eq 0
    Check 'AUTH9_CORE_AND_GENERATOR_PROTECTED_FOR_READ_ONLY_SPECIALISTS' ($readOnlyAgents.Count -gt 0 -and $coreProtectionValid)
    # Match scripts/bootstrap.ps1:Get-GeneratedHarnessOutputs: agent files are
    # inventoried only in their dedicated directories, while other generated
    # destinations are explicit. Do not recurse whole adapter trees, where
    # unrelated project files such as SpecKit commands may also reside.
    $managedPaths = @('opencode.jsonc', '.opencode/orchestrator-install.json')
    $managedPaths += @(Get-ChildItem -LiteralPath (Join-Path $root '.opencode/agents') -Filter '*.md' -File -Recurse -Force | ForEach-Object {
        $_.FullName.Substring(([IO.Path]::GetFullPath($root).TrimEnd([char[]]@('\','/')).Length + 1)).Replace('\','/')
    })
    $managedPaths += @('.opencode/plugins/olympus-activity/activity.ts',
        '.opencode/plugins/olympus-activity/tui.tsx', '.opencode/scripts/worktree-setup.ps1')
    $managedPaths += $exactManagedCommandPaths
    # Verify Windows paths really became repository-relative forward-slash
    # paths; a malformed path must never make the DENY assertion meaningless.
    Check 'AUTH9B_WINDOWS_MANAGED_PATH_NORMALIZED' (
        '.opencode/scripts/worktree-setup.ps1' -in $managedPaths -and
        @($managedPaths | Where-Object { $_.Contains('\') }).Count -eq 0
    )
    $managedPathsWithoutDeny = @($managedPaths | Where-Object {
        (Native-Decision $nativeRules 'edit' $_) -ne 'DENY'
    })
    Check 'AUTH9B_EVERY_INSTALLER_MANAGED_PATH_HAS_NATIVE_DENY' ($managedPathsWithoutDeny.Count -eq 0)
    $specKitProjectCommand = '.opencode/commands/speckit.plan.md'
    $specKitPermission = Native-Decision $nativeRules 'edit' $specKitProjectCommand
    Check 'AUTH9B_FOREIGN_SPECKIT_EXCLUDED_AND_NATIVE_ASK' (
        $specKitProjectCommand -notin $managedPaths -and -not (Is-OlympusOwned $specKitProjectCommand) -and
        $specKitPermission -eq 'ASK' -and (Classify-NewScope $specKitPermission $true) -eq 'NATIVE_ASK'
    )
    $commandRuleFailures = [Collections.Generic.List[string]]::new()
    foreach ($path in $exactManagedCommandPaths) {
        $kaelExactDeny = @($kaelNativeRules | Where-Object {
            $_.action -eq 'edit' -and $_.resource -ceq $path -and $_.effect -eq 'deny'
        }).Count
        $kovanExactDeny = @($nativeRules | Where-Object {
            $_.action -eq 'edit' -and $_.resource -ceq $path -and $_.effect -eq 'deny'
        }).Count
        if ($kaelExactDeny -ne 1 -or $kovanExactDeny -ne 1 -or
            (Native-Decision $kaelNativeRules 'edit' $path) -ne 'DENY' -or
            (Native-Decision $nativeRules 'edit' $path) -ne 'DENY') {
            $commandRuleFailures.Add($path)
        }
    }
    $projectOwnedCommand = '.opencode/commands/project-owned.md'
    $commandPrefixNeighbor = $exactManagedCommandPaths[0] + '.backup'
    $unrelatedCommandControls = @($projectOwnedCommand, $specKitProjectCommand, $commandPrefixNeighbor)
    $unrelatedCommandControlMismatch = @($unrelatedCommandControls | Where-Object {
        (Is-OlympusOwned $_) -or
        (Native-Decision $kaelNativeRules 'edit' $_) -ne 'DENY' -or
        (Native-Decision $nativeRules 'edit' $_) -ne 'ASK'
    })
    Check 'AUTH9D_MANAGED_COMMANDS_EXACT_DENY_AND_UNRELATED_CONTROLS' (
        $commandRuleFailures.Count -eq 0 -and
        @($exactManagedCommandPaths | Where-Object { $_ -notin $managedPaths }).Count -eq 0 -and
        $unrelatedCommandControlMismatch.Count -eq 0
    )
    $missingAgentDenyRule = @($nativeRules | Where-Object {
        $_.action -eq 'edit' -and $_.resource -eq '.opencode/agents/**' -and $_.effect -eq 'deny'
    })
    $nativeRulesWithoutAgentDeny = @($nativeRules | Where-Object {
        -not ($_.action -eq 'edit' -and $_.resource -eq '.opencode/agents/**' -and $_.effect -eq 'deny')
    })
    $managedPathsWithoutAgentDeny = @($managedPaths | Where-Object {
        (Native-Decision $nativeRulesWithoutAgentDeny 'edit' $_) -ne 'DENY'
    })
    Check 'AUTH9B_NEGATIVE_CONTROL_MISSING_MANAGED_DENY_DETECTED' (
        $missingAgentDenyRule.Count -eq 1 -and '.opencode/agents/kovan.md' -in $managedPaths -and
        (Native-Decision $nativeRules 'edit' '.opencode/agents/kovan.md') -eq 'DENY' -and
        (Native-Decision $nativeRulesWithoutAgentDeny 'edit' '.opencode/agents/kovan.md') -ne 'DENY' -and
        '.opencode/agents/kovan.md' -in $managedPathsWithoutAgentDeny
    )
    Check 'AUTH9C_WORKTREE_HELPER_NATIVE_DENY_AND_OWNERSHIP' (
        (Native-Decision $nativeRules 'edit' '.opencode/scripts/worktree-setup.ps1') -eq 'DENY' -and
        (Is-OlympusOwned '.opencode/scripts/worktree-setup.ps1')
    )

    $siblingRepoPath = 'C:\workspace\unrelated-sibling\src\cart.ts'
    $externalDecision = Native-Decision $nativeRules 'external_directory' $siblingRepoPath
    $kaelExternalDecision = Native-Decision $kaelNativeRules 'external_directory' $siblingRepoPath
    Check 'AUTH10_EXTERNAL_SIBLING_REQUIRES_ASK' ($externalDecision -eq 'ASK' -and $kaelExternalDecision -eq 'ASK' -and
        @($nativeRules | Where-Object { $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'allow' }).Count -eq 0)

    # An agent-level wildcard ASK follows project rules and can silently
    # downgrade a user's specific DENY. Guard every installed agent against
    # that precedence regression, including read-only delegates.
    $prohibitedPattern = 'C:/fixture/prohibited/*'
    $prohibitedPath = 'C:/fixture/prohibited/deny-probe.txt'
    $explicitExternalDeny = [pscustomobject]@{
        action = 'external_directory'; resource = $prohibitedPattern; effect = 'deny'
    }
    $globalWithDeny = @($config.permissions) + @($explicitExternalDeny)
    $rolesThatOverrideDeny = [Collections.Generic.List[string]]::new()
    foreach ($role in @('kael', 'kovan', 'nox', 'orin', 'vera', 'veyra', 'thales')) {
        $roleRules = Read-NativeRules (Text ('.opencode/agents/' + $role + '.md')) $globalWithDeny
        if ((Native-Decision $roleRules 'external_directory' $prohibitedPath) -ne 'DENY') {
            $rolesThatOverrideDeny.Add($role)
        }
    }
    $unsafeWildcardAsk = [pscustomobject]@{
        action = 'external_directory'; resource = '*'; effect = 'ask'
    }
    Check 'AUTH10E_SPECIFIC_EXTERNAL_DENY_SURVIVES_AGENT_PRECEDENCE' (
        $rolesThatOverrideDeny.Count -eq 0 -and
        (Native-Decision (@($globalWithDeny) + @($unsafeWildcardAsk)) 'external_directory' $prohibitedPath) -eq 'ASK'
    )

    # V2 preserves rule order across configuration layers. A later project ASK
    # can still override an earlier global-user DENY. This predates PR #121 and
    # is not covered by removing agent-level wildcard rules.
    $globalUserSpecificDeny = @($explicitExternalDeny)
    $projectWildcardAsk = @($config.permissions | Where-Object {
        $_.action -eq 'external_directory' -and $_.resource -eq '*'
    })
    $globalThenProject = @($globalUserSpecificDeny) + @($projectWildcardAsk)
    $projectThenSpecificDeny = @($projectWildcardAsk) + @($explicitExternalDeny)
    Check 'AUTH10F_GLOBAL_DENY_BEFORE_PROJECT_ASK_LIMITATION' (
        $projectWildcardAsk.Count -eq 1 -and
        (Native-Decision $globalThenProject 'external_directory' $prohibitedPath) -eq 'ASK' -and
        (Native-Decision $projectThenSpecificDeny 'external_directory' $prohibitedPath) -eq 'DENY'
    )

    # A grant for one repository must never silently authorize the same relative
    # path in a sibling repository; an exact second grant can reach native ASK.
    $otherRoot = 'C:\fixture\other-project'
    $firstRootGrant = New-Grant 'kovan' $operation 'src/**' $rootPath 'NATIVE_ASK'
    $secondRootGrant = New-Grant 'kovan' $operation 'src/**' $otherRoot 'NATIVE_ASK'
    $crossRootAttempt = Decide 'kovan' $operation 'src/feature.ts' 'docs/**' $otherRoot $firstRootGrant $true $true $false @() 'ASK'
    $secondRootAttempt = Decide 'kovan' $operation 'src/feature.ts' 'docs/**' $otherRoot $secondRootGrant $true $true $false @() 'ASK'
    Check 'AUTH10C_MULTI_REPO_REQUIRES_SEPARATE_ROOT_AND_SCOPE' (
        $crossRootAttempt.decision -eq 'NEED_AUTHORITY' -and
        $secondRootAttempt.decision -eq 'NATIVE_ASK' -and
        $kael -match 'One repository''s WRITE_SCOPE never authorizes another root' -and
        $kovan -match 'Do not source-edit another repository' -and
        $docs -match 'a scope for one\s+root cannot grant access to another'
    )

    # External artifacts and hooks are distinct from source editing. Keeping
    # that distinction explicit prevents both false denials and silent widening.
    Check 'AUTH10D_EXTERNAL_EFFECTS_REQUIRE_EXACT_AUTHORITY' (
        $kael -match 'Non-source external operations' -and
        $kael -match 'separately\s+declared exact target, operation, effect' -and
        $kael -match 'Native DENY remains final' -and
        $kovan -match 'separately assigned non-source external effect' -and
        $docs -match 'Separately requested non-source external\s+effects' -and
        $kael -notmatch 'Master verifies every requested target is within the active repository'
    )

    Check 'AUTH10B_EXPLICIT_PROHIBITION_OVERRIDES_NATIVE_ASK' ((Native-Decision $nativeRules 'edit' $pluginResource $true) -eq 'DENY' -and
        -not (Write-Decision 'DENY' 'APPROVE_ONCE') -and $kael -match '(?s)Explicit user prohibitions.*?override every other outcome')

    $workerPaths = @('.opencode/agents/argus.md','.opencode/agents/atlas.md','.opencode/agents/helios.md',
        '.opencode/agents/kovan.md','.opencode/agents/nox.md','.opencode/agents/orin.md',
        '.opencode/agents/talos.md','.opencode/agents/thales.md','.opencode/agents/vera.md','.opencode/agents/veyra.md')
    $workerTexts = @($workerPaths | ForEach-Object { Text $_ })
    $directAskBlocked = @($workerPaths | Where-Object { $file = Text $_; $file -notmatch '(?s)action: question\s+resource: "?\*"?\s+effect: deny' }).Count -eq 0 -and
        @($workerTexts | Where-Object { $_ -notmatch 'Never ask the user' }).Count -eq 0
    Check 'AUTH10_CHILD_DIRECT_QUESTION_DENIED' $directAskBlocked

    $childSelfRoutes = @($workerPaths | Where-Object { $file = Text $_; $file -notmatch '(?s)action: subagent\s+resource: "?\*"?\s+effect: deny' }).Count
    Check 'AUTH11_CHILD_SELF_ESCALATION_DENIED' ($childSelfRoutes -eq 0 -and
        @($workerTexts | Where-Object { $_ -notmatch 'never (?:ask the user, grant|grant)\s+or infer your own authority' }).Count -eq 0 -and
        $kael -match 'Only veyra, orin, kovan, nox, vera, thales, atlas, argus, talos, and helios are valid child role IDs')

    $needs = @(
        [pscustomobject]@{ root=$rootPath; operation='WRITE_SCOPE'; scope='src/one/**' },
        [pscustomobject]@{ root=$rootPath; operation='WRITE_SCOPE'; scope='src/two/**' }
    )
    $compatible = @($needs | Where-Object { $_.root -ceq $rootPath -and $_.operation -ceq 'WRITE_SCOPE' }).Count -eq $needs.Count
    $questionCount = if ($compatible) { 1 } else { $needs.Count }
    $consolidationPolicy = $kael -match '(?s)If multiple needs share the same root and operation.*?consolidate them into one precise user QUESTION'
    $documentedPolicy = $docs -match '(?s)If no applicable native ASK exists.*?compatible needs may be consolidated into\s+one precise Kael QUESTION'
    Check 'AUTH12_COMPATIBLE_NEEDS_CONSOLIDATED' ($questionCount -eq 1 -and $consolidationPolicy -and $documentedPolicy)

    Check 'AUTH13_NATIVE_ASK_NO_DUPLICATE_QUESTION' ($kael -match 'do not send a duplicate Kael\s+QUESTION' -and
        $kovan -match 'Do not open QUESTION, demand textual\s+approval' -and
        $kael -match 'permission_mode: NATIVE_ASK' -and $docs -match 'Kael must not also send a duplicate QUESTION')

    $normalToolDecision = Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null
    $normalToolFlow = Synthetic-ToolFlow $normalToolDecision.decision
    Check 'AUTH16_ALLOW_TOOL_EXECUTES_WITHOUT_PREAUTH' ($normalToolDecision.decision -eq 'ALLOW' -and
        $normalToolFlow.attempted -and $normalToolFlow.executed -and $normalToolFlow.continue -and
        $normalToolFlow.question -eq 0 -and $kovan -match 'invoke the required tool\s+directly, without textual pre-authorization')

    $pendingFlow = Synthetic-ToolFlow $approved.decision
    Check 'AUTH17_NATIVE_ASK_ATTEMPT_NOT_BLOCKED' ($approved.decision -eq 'NATIVE_ASK' -and
        $pendingFlow.attempted -and $pendingFlow.pending -and -not $pendingFlow.executed -and
        $pendingFlow.question -eq 0 -and $kovan -match 'Do not open QUESTION, demand textual\s+approval, or report BLOCKED before that tool attempt')

    Check 'AUTH18_NATIVE_ASK_NO_KAEL_QUESTION' ($pendingFlow.question -eq 0 -and
        $kovan -match 'Never ask the user' -and
        $kael -match 'Do not ask when native ASK can obtain the exact required human\s+consent' -and
        $kael -match 'do not send a duplicate Kael\s+QUESTION')

    Check 'AUTH19_NATIVE_ASK_EXACT_SCOPE_AND_TASK_LIFETIME' ($grant.agent -ceq 'kovan' -and
        $grant.operation -ceq $operation -and $grant.scope -ceq '.opencode/plugins/project-owned/**' -and
        $grant.repository_root -ceq $rootPath -and $grant.permission_mode -ceq 'NATIVE_ASK' -and
        $grant.lifetime -ceq 'current_task' -and $grant.task_id -ceq 'task-7' -and
        $kael -match 'same exact scope in WRITE_SCOPE' -and $kael -match 'current task identity')

    $deniedFlow = Synthetic-ToolFlow 'NATIVE_ASK' 'REJECT'
    Check 'AUTH20_NATIVE_DENIAL_NO_FALLBACK_OR_BYPASS' ($deniedFlow.attempted -and
        -not $deniedFlow.pending -and -not $deniedFlow.executed -and -not $deniedFlow.continue -and
        -not $deniedFlow.fallback -and -not $deniedFlow.retry -and
        $kovan -match 'rejection/cancellation without\s+retry, fallback, or bypass')

    $approvedFlow = Synthetic-ToolFlow 'NATIVE_ASK' 'APPROVE_ONCE'
    Check 'AUTH21_NATIVE_APPROVAL_CONTINUES' ($approvedFlow.attempted -and $approvedFlow.executed -and
        $approvedFlow.continue -and -not $approvedFlow.fallback -and
        $kovan -match 'continue only if approved')

    $newScopeNeed = Decide 'kovan' $operation 'docs/release.md' 'src/**' $rootPath $null
    Check 'AUTH22_NEW_SCOPE_NEED_AUTHORITY_TO_KAEL' ($newScopeNeed.decision -eq 'NEED_AUTHORITY' -and
        -not (Synthetic-ToolFlow $newScopeNeed.decision).attempted -and
        $kovan -match '(?s)For otherwise legitimate project\s+work outside the assigned scope.*?STATUS: NEED_AUTHORITY' -and
        $kovan -match 'MINIMUM_SCOPE:' -and $kovan -match 'REPOSITORY_ROOT:')

    $newMinimumScope = '.opencode/plugins/authority-smoke/**'
    $newMode = Classify-NewScope (Native-Decision $nativeRules 'edit' '.opencode/plugins/authority-smoke/index.ts')
    $redelegated = New-Grant 'kovan' $operation $newMinimumScope $rootPath $newMode
    $redelegatedDecision = Decide 'kovan' $operation '.opencode/plugins/authority-smoke/index.ts' 'src/**' $rootPath $redelegated $true $true $false @() 'ASK'
    Check 'AUTH23_KAEL_REDELEGATES_NATIVE_ASK_NO_DUPLICATE_CONSENT' ($newMode -eq 'NATIVE_ASK' -and
        $redelegatedDecision.decision -eq 'NATIVE_ASK' -and $redelegated.scope -ceq $newMinimumScope -and
        $redelegated.permission_mode -ceq 'NATIVE_ASK' -and $redelegated.lifetime -ceq 'current_task' -and
        $redelegated.task_id -ceq 'task-7' -and
        $kael -match 'Kael may delegate only that task to the exact\s+agent' -and
        $kael -match 'Do not ask when native ASK can obtain the exact required human\s+consent')

    $ownedFlow = Synthetic-ToolFlow $ownedByManifest.decision
    Check 'AUTH24_OLYMPUS_OWNED_DENY_BEFORE_TOOL' ($ownedByManifest.decision -eq 'DENY' -and
        -not $ownedFlow.attempted -and $ownedByManifest.reason -eq 'OLYMPUS_OWNED')

    $prohibitionFlow = Synthetic-ToolFlow $prohibited.decision
    Check 'AUTH25_EXPLICIT_PROHIBITION_DENY_BEFORE_TOOL' ($prohibited.decision -eq 'DENY' -and
        -not $prohibitionFlow.attempted -and $prohibited.reason -eq 'USER_PROHIBITION' -and
        (Classify-NewScope 'ASK' $true $true) -eq 'DENY')

    $runtimeCommandDenies = @($exactManagedCommandPaths | ForEach-Object {
        [pscustomobject]@{ action='edit'; resource=$_; effect='deny' }
    })
    $runtimeAgentFixture = @(
        [pscustomobject]@{
            id='kael'
            permissions=@(
                [pscustomobject]@{ action='*'; resource='*'; effect='allow' }
                [pscustomobject]@{ action='automation_*'; resource='*'; effect='deny' }
                [pscustomobject]@{ action='browser'; resource='*'; effect='deny' }
                [pscustomobject]@{ action='shell'; resource='*'; effect='deny' }
                [pscustomobject]@{ action='shell'; resource='git rev-parse --show-toplevel'; effect='allow' }
                [pscustomobject]@{ action='serena_*'; resource='*'; effect='deny' }
                [pscustomobject]@{ action='edit'; resource='*'; effect='deny' }
                [pscustomobject]@{ action='subagent'; resource='*'; effect='deny' }
                [pscustomobject]@{ action='subagent'; resource='veyra'; effect='allow' }
                [pscustomobject]@{ action='subagent'; resource='orin'; effect='allow' }
                [pscustomobject]@{ action='subagent'; resource='kovan'; effect='allow' }
                [pscustomobject]@{ action='subagent'; resource='nox'; effect='allow' }
                [pscustomobject]@{ action='subagent'; resource='vera'; effect='allow' }
                [pscustomobject]@{ action='subagent'; resource='thales'; effect='allow' }
                [pscustomobject]@{ action='subagent'; resource='atlas'; effect='allow' }
                [pscustomobject]@{ action='subagent'; resource='argus'; effect='allow' }
                [pscustomobject]@{ action='subagent'; resource='talos'; effect='allow' }
                [pscustomobject]@{ action='subagent'; resource='helios'; effect='allow' }
                [pscustomobject]@{ action='external_directory'; resource='*'; effect='ask' }
            ) + $runtimeCommandDenies
        }
        [pscustomobject]@{
            id='kovan'
            permissions=@(
                [pscustomobject]@{ action='*'; resource='*'; effect='allow' }
                [pscustomobject]@{ action='automation_*'; resource='*'; effect='deny' }
                [pscustomobject]@{ action='browser'; resource='*'; effect='deny' }
                [pscustomobject]@{ action='edit'; resource='*'; effect='allow' }
                [pscustomobject]@{ action='edit'; resource='.opencode/**'; effect='ask' }
                [pscustomobject]@{ action='edit'; resource='.opencode/plugins/**'; effect='ask' }
                [pscustomobject]@{ action='edit'; resource='.opencode/plugins/olympus-activity/**'; effect='deny' }
            ) + $runtimeCommandDenies
        }
    )
    foreach ($roleName in @($expectedOlympusAgentIds | Where-Object { $_ -notin @('kael','kovan') })) {
        $rolePermissions = Read-NativeRules (Text ('olympus/harnesses/opencode/agent-metadata/' + $roleName + '.md')) @()
        $runtimeAgentFixture += [pscustomobject]@{ id=$roleName; permissions=@($rolePermissions) }
    }
    $runtimeAgentFixture += [pscustomobject]@{ id='opencode_builtin_fixture'; permissions=@() }
    $validRuntimeFixture = ConvertTo-Json -InputObject $runtimeAgentFixture -Compress -Depth 10
    $failedRuntimeProbe = Inspect-EffectiveRules 17 $validRuntimeFixture 'fixture runtime error'
    Check 'AUTH14_RUNTIME_COMMAND_FAILURE_HAS_EVIDENCE' (-not $failedRuntimeProbe.passed -and
        $failedRuntimeProbe.evidence -match 'runtime_exit=17' -and $failedRuntimeProbe.evidence -match 'stderr=fixture runtime error')
    $malformedRuntimeProbe = Inspect-EffectiveRules 0 '{malformed json'
    Check 'AUTH14_MALFORMED_JSON_HAS_EVIDENCE' (-not $malformedRuntimeProbe.passed -and
        $malformedRuntimeProbe.evidence -match 'json_parseable=False' -and $malformedRuntimeProbe.evidence -match 'json_error=')
    $missingKovanProbe = Inspect-EffectiveRules 0 '[]'
    Check 'AUTH14_MISSING_KOVAN_HAS_EVIDENCE' (-not $missingKovanProbe.passed -and
        $missingKovanProbe.evidence -match 'json_parseable=True' -and $missingKovanProbe.evidence -match 'kovan=missing')
    $duplicateKovanProbe = Inspect-EffectiveRules 0 '[{"id":"kovan","permissions":[]},{"id":"kovan","permissions":[]}]'
    Check 'AUTH14_DUPLICATE_KOVAN_HAS_EVIDENCE' (-not $duplicateKovanProbe.passed -and
        $duplicateKovanProbe.evidence -match 'kovan=duplicated \(matches=2\)')
    $missingNoxFixture = @($runtimeAgentFixture | Where-Object { $_.id -cne 'nox' })
    $missingNoxProbe = Inspect-EffectiveRules 0 (ConvertTo-Json -InputObject $missingNoxFixture -Compress -Depth 10)
    Check 'AUTH14_MISSING_EXPECTED_OLYMPUS_ID_REJECTED' (-not $missingNoxProbe.passed -and
        $missingNoxProbe.evidence -match 'roster_nox=missing \(matches=0\)')
    $duplicateNoxFixture = @($runtimeAgentFixture) + @($runtimeAgentFixture | Where-Object { $_.id -ceq 'nox' })
    $duplicateNoxProbe = Inspect-EffectiveRules 0 (ConvertTo-Json -InputObject $duplicateNoxFixture -Compress -Depth 10)
    Check 'AUTH14_DUPLICATE_EXPECTED_OLYMPUS_ID_REJECTED' (-not $duplicateNoxProbe.passed -and
        $duplicateNoxProbe.evidence -match 'roster_nox=duplicated \(matches=2\)')
    $singleKovanProbe = Inspect-EffectiveRules 0 $validRuntimeFixture
    Check 'AUTH14_SINGLE_KOVAN_EVALUATES_EFFECTIVE_RULES' ($singleKovanProbe.passed -and
        $singleKovanProbe.evidence -match 'olympus_roster=kael=1,veyra=1,orin=1,kovan=1,nox=1,vera=1,thales=1,atlas=1,argus=1,talos=1,helios=1' -and
        $singleKovanProbe.evidence -match 'tool_denies=66/66;tool_checks=66;additional_agent_ids=1' -and
        $singleKovanProbe.evidence -match 'kael_matches=1' -and $singleKovanProbe.evidence -match 'kovan_matches=1' -and
        $singleKovanProbe.evidence -match 'task_edit=ALLOW/2 rules, project_plugin_edit=ASK, activity_edit=DENY' -and
        $singleKovanProbe.evidence -match 'edit_plugins_ask=1/1' -and
        $singleKovanProbe.evidence -match 'serena_nav_denied=6/6;source_deny=1;loaded_direct_deny=1;base_allow_before_deny=1;deny_rules=1;allow_ask_rules=0' -and
        $singleKovanProbe.evidence -match 'subagent_allow_rules=10/10;named_allow=10/10;expanded=0;duplicates=0;base_allow_before_deny=1;unlisted=DENY' -and
        $singleKovanProbe.evidence -match 'external_directory=ASK;source_agent_rules=0;inherited_rules=1;loaded_category_rules=1;missing=0;unexpected=0;category_allow=0;base_allow_before_ask=1;read_question=NOT_ASSESSED' -and
        $singleKovanProbe.evidence -match 'kael:\.opencode/commands/olympus\.ultra\.md=DENY' -and
        $singleKovanProbe.evidence -match 'kovan:\.opencode/commands/project-owned\.md=ASK')
    $lateOverridePermissions = @($runtimeAgentFixture[0].permissions | Where-Object {
        -not ($_.action -ceq '*' -and $_.resource -ceq '*' -and $_.effect -ceq 'allow')
    }) + @([pscustomobject]@{ action='*'; resource='*'; effect='allow' })
    $lateOverrideRuntimeFixture = @(
        [pscustomobject]@{ id='kael'; permissions=$lateOverridePermissions }
        $runtimeAgentFixture[1]
    )
    $lateOverrideProbe = Inspect-EffectiveRules 0 (ConvertTo-Json -InputObject $lateOverrideRuntimeFixture -Compress -Depth 10)
    Check 'AUTH14_LATE_BASE_ALLOW_OVERRIDE_REJECTED' (-not $lateOverrideProbe.passed -and
        $lateOverrideProbe.evidence -match 'serena_nav_denied=0/6' -and
        $lateOverrideProbe.evidence -match 'subagent_allow_rules=11/10' -and
        $lateOverrideProbe.evidence -match 'unlisted=ALLOW' -and
        $lateOverrideProbe.evidence -match 'kael/automation_create=ALLOW' -and
        $lateOverrideProbe.evidence -match 'kael/browser=ALLOW' -and
        $lateOverrideProbe.evidence -match 'external_directory=ALLOW')
    $integrationRouteSource = [regex]::Match($authoritySource, '(?s)\$directoryHeader = .*?(?=\$runtimeProbe = \$null)').Value
    $normalizedQualificationDocs = ($docs + $harnessDocs) -replace '\s+', ' '
    Check 'AUTH14_INTEGRATION_ROUTE_IS_CONTEXT_ONLY' (
        $integrationRouteSource -match 'response shape only; HTTP 200 is not plugin-readiness evidence' -and
        $integrationRouteSource -match 'AUTHORITY_INTEGRATION_CONTEXT: PASS' -and
        $integrationRouteSource -notmatch 'AUTHORITY_PLUGIN_ACTIVATION|Start-Sleep|while\s*\(' -and
        $normalizedQualificationDocs -match 'a 200 may arrive before plugin activation completes.*?not a readiness signal.*?bounded internal wait.*?no polling loop or arbitrary sleep' -and
        $normalizedQualificationDocs -match '`AUTH14_OPENCODE_EFFECTIVE_RULES PASS`.*?all 11 Olympus IDs exactly once.*?effective DENY for all 66 checks.*?did not establish plugin activation/readiness'
    )
    $badPermissionProbe = Inspect-EffectiveRules 0 '[{"id":"kovan","permissions":[{"action":"edit","resource":"*","effect":"deny"}]}]'
    Check 'AUTH14_SINGLE_KOVAN_RULE_MISMATCH_FAILS' (-not $badPermissionProbe.passed -and
        $badPermissionProbe.evidence -match 'edit_\*_deny=1/0')
    }

    if ($QualificationSlice -ne 'Offline') {
        Invoke-IsolatedAuthorityRuntime
    }

    if ($QualificationSlice -ne 'Runtime') {
    $normalizedDocs = $docs -replace '\s+', ' '
    $reportingPolicy = $normalizedDocs -match '(?is)TOOL_ATTEMPT.*?TOOL_EXECUTION.*?NATIVE_PERMISSION_UI.*?USER_CONFIRMED_EXTERNAL_OBSERVATION.*?NOT_OBSERVABLE.*?Tool success does not establish that ASK was\s+absent.*?tool failure/denial alone does not establish a human rejection'
    $noxResultContract = ($noxPromptSource -split '## Required result contract',2)[1]
    $noxCommandResult = if ($noxResultContract) { ($noxResultContract -split 'TRACKED_SOURCE_INTEGRITY:',2)[0] } else { '' }
    $noxResultFields = @(
        'COMMANDS:','COMMAND: exact command','EXECUTED: YES | NO','RESULT: PASS | FAIL | BLOCKED',
        'EXIT_STATUS: value or unavailable','TOOL_ATTEMPT: ATTEMPTED | NOT_ATTEMPTED',
        'TOOL_EXECUTION: PENDING | SUCCESS | FAILED | NOT_EXECUTED | UNKNOWN','TOOL_RESULT: <direct tool result>',
        'NATIVE_PERMISSION_UI: OBSERVED_ASK | OBSERVED_NO_ASK | NOT_OBSERVABLE',
        'NATIVE_PERMISSION_DECISION: APPROVED | REJECTED | NOT_OBSERVABLE',
        'USER_CONFIRMED_EXTERNAL_OBSERVATION: USER_REPORTED: <concise faithful account> (only when supplied)'
    )
    $noxFieldsValid = $noxCommandResult.Length -gt 0
    foreach ($field in $noxResultFields) {
        if ($noxCommandResult -notmatch [regex]::Escape($field)) { $noxFieldsValid = $false }
    }
    if ($noxCommandResult -notmatch '(?s)COMMANDS:\s+- COMMAND: exact command\s+EXECUTED: YES \| NO\s+RESULT: PASS \| FAIL \| BLOCKED\s+EXIT_STATUS: value or unavailable\s+TOOL_ATTEMPT: ATTEMPTED \| NOT_ATTEMPTED' -or
        $noxPromptSource -match 'PERMISSION_PROMPT') { $noxFieldsValid = $false }
    Check 'AUTH15_NATIVE_PERMISSION_OBSERVABILITY_POLICY' ($reportingPolicy -and
        $kael -match '(?is)TOOL_ATTEMPT.*?TOOL_EXECUTION.*?NATIVE_PERMISSION_UI.*?NATIVE_PERMISSION_DECISION.*?NOT_OBSERVABLE.*?Tool success does not prove ASK was absent.*?failed\s+or denied tool result does not by itself prove a human rejected.*?USER_CONFIRMED_EXTERNAL_OBSERVATION.*?external/manual evidence' -and
        $kovan -match '(?is)TOOL_ATTEMPT.*?TOOL_EXECUTION.*?NATIVE_PERMISSION_UI.*?NATIVE_PERMISSION_DECISION.*?NOT_OBSERVABLE.*?success never implies\s+`OBSERVED_NO_ASK`.*?USER_CONFIRMED_EXTERNAL_OBSERVATION' -and
        $noxFieldsValid -and
        $noxResultContract -match '(?is)Tool success does not prove ASK was\s+absent.*?success never implies `OBSERVED_NO_ASK`.*?a tool failure or native\s+DENY does not prove human rejection.*?USER_REPORTED.*?does not replace an observable UI or\s+decision and grants no permission'
    )

    $uiHiddenSuccess = New-PermissionReport $true 'SUCCESS' 'write completed'
    Check 'AUTH26_PERMISSION_UI_UNOBSERVABLE' ($uiHiddenSuccess.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $uiHiddenSuccess.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE' -and $uiHiddenSuccess.TOOL_ATTEMPT -eq 'ATTEMPTED')

    $successNoAskInference = New-PermissionReport $true 'SUCCESS' 'write completed'
    Check 'AUTH27_SUCCESS_DOES_NOT_INFER_ASK_ABSENT' ($successNoAskInference.TOOL_EXECUTION -eq 'SUCCESS' -and
        $successNoAskInference.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $successNoAskInference.NATIVE_PERMISSION_UI -ne 'OBSERVED_NO_ASK' -and
        $successNoAskInference.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE')

    $failedNoHumanDecision = New-PermissionReport $true 'FAILED' 'tool returned a permission-related error'
    $deniedNoHumanDecision = New-PermissionReport $true 'NOT_EXECUTED' 'tool denied without an explicit human decision result'
    Check 'AUTH28_FAILURE_OR_DENIAL_DOES_NOT_INVENT_HUMAN_DECISION' ($failedNoHumanDecision.TOOL_EXECUTION -eq 'FAILED' -and
        $failedNoHumanDecision.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $failedNoHumanDecision.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE' -and
        $deniedNoHumanDecision.TOOL_EXECUTION -eq 'NOT_EXECUTED' -and
        $deniedNoHumanDecision.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $deniedNoHumanDecision.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE')

    $manualConfirmation = New-PermissionReport $true 'SUCCESS' 'write completed' 'NOT_OBSERVABLE' 'NOT_OBSERVABLE' `
        'USER_REPORTED: user saw the native prompt and approved it'
    Check 'AUTH29_LATER_USER_CONFIRMATION_IS_EXTERNAL_EVIDENCE' ($manualConfirmation.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $manualConfirmation.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE' -and
        $manualConfirmation.USER_CONFIRMED_EXTERNAL_OBSERVATION -match '^USER_REPORTED:' -and
        $manualConfirmation.USER_CONFIRMED_EXTERNAL_OBSERVATION -match 'saw the native prompt and approved')
    }

    Write-Output 'NATIVE_AUTHORITY_ASK_RUNTIME: NOT ASSESSED BY STATIC QUALIFICATION (report interactive event evidence separately)'
    if ($QualificationSlice -eq 'Runtime') {
        Write-Output 'AUTHORITY RUNTIME QUALIFICATION: PASS (effective OpenCode rules; native ASK UI/decision not assessed)'
    } elseif ($QualificationSlice -eq 'Offline') {
        Write-Output 'AUTHORITY OFFLINE QUALIFICATION: PASS (static contracts and deterministic scope/approval cases; OpenCode query not run)'
    } else {
        Write-Output 'AUTHORITY QUALIFICATION: PASS (static contracts, native/effective rules, and deterministic scope/approval cases; interactive outcome not asserted)'
    }
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'AUTHORITY QUALIFICATION: FAIL'
    exit 1
}
