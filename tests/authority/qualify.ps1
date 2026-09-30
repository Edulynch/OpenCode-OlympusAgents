[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
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

function Is-OlympusOwned([string]$path, [string[]]$manifestPaths = @()) {
    $p = $path.Replace('\','/').TrimStart('/').ToLowerInvariant()
    $fixed = @('.opencode/agents/', '.opencode/commands/maintain.md',
        '.opencode/plugins/olympus-activity/', '.opencode/orchestrator-install.json',
        '.opencode/opencode.json', '.opencode/opencode.jsonc', '.codex/', 'CODEX.md',
        'olympus/', 'scripts/render_harnesses.py', 'opencode.jsonc', 'opencode.json')
    if (@($fixed | Where-Object { $p.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0) { return $true }
    foreach ($entry in $manifestPaths) {
        $declared = $entry.Replace('\','/').TrimStart('/').ToLowerInvariant()
        if ($p -eq $declared -or $p.StartsWith($declared.TrimEnd('/') + '/', [StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Decide([string]$agent, [string]$operation, [string]$path, [string]$normalScope,
                 [string]$repositoryRoot, $grant, [bool]$taskActive = $true,
                 [bool]$projectOwned = $true, [bool]$explicitProhibition = $false,
                 [string[]]$manifestPaths = @(), [string]$nativeDecision = 'ALLOW') {
    if ($explicitProhibition) { return [pscustomobject]@{ decision='DENY'; question=0; reason='USER_PROHIBITION' } }
    if (Is-OlympusOwned $path $manifestPaths) { return [pscustomobject]@{ decision='DENY'; question=0; reason='OLYMPUS_OWNED' } }
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
        $rules.Add([pscustomobject]@{ action=$m.Groups['action'].Value.Trim(); resource=$m.Groups['resource'].Value.Trim(); effect=$m.Groups['effect'].Value.Trim() })
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
        if (($rule.action -eq $action -or $rule.action -eq '*') -and (Matches-Glob $rule.resource $resource)) {
            $decision = $rule.effect.ToUpperInvariant()
        }
    }
    return $decision
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

try {
    $kael = Text '.opencode/agents/kael.md'
    $kovan = Text '.opencode/agents/kovan.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $configText = (Text 'opencode.jsonc') -replace '(?m)^\s*//.*(?:\r?\n|$)', ''
    $config = $configText | ConvertFrom-Json -Depth 100
    $nativeRules = Read-NativeRules $kovan @($config.permissions)
    $kaelNativeRules = Read-NativeRules $kael @($config.permissions)
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

    Check 'AUTH1_NORMAL_IN_SCOPE_NO_QUESTION' ($kael -match 'Normal in-scope project work proceeds directly when the effective native\s+permission is ALLOW' -and
        (Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null).decision -eq 'ALLOW' -and
        (Native-Decision $nativeRules 'edit' 'src/cart.ts') -eq 'ALLOW' -and
        (Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null).question -eq 0)

    $need = Decide 'kovan' $operation 'docs/release.md' 'src/**' $rootPath $null
    Check 'AUTH2_OUT_OF_SCOPE_NEED_AUTHORITY' ($need.decision -eq 'NEED_AUTHORITY' -and
        $kovan -match 'STATUS: NEED_AUTHORITY' -and $kovan -match 'OPERATION:' -and
        $kovan -match 'MINIMUM_SCOPE:' -and $kovan -match 'REPOSITORY_ROOT:' -and
        $kovan -match 'TASK_BLOCKED:')

    $approved = Decide 'kovan' $operation '.opencode/plugins/project-owned/index.ts' 'src/**' $rootPath $grant $true $true $false @() 'ASK'
    Check 'AUTH3_EXACT_SCOPE_NATIVE_ASK_GRANT' ($approved.decision -eq 'NATIVE_ASK' -and $approved.reason -eq 'EXACT_NATIVE_ASK_GRANT' -and
        $grant.agent -eq 'kovan' -and $grant.scope -ceq '.opencode/plugins/project-owned/**' -and
        $grant.repository_root -ceq $rootPath -and $grant.permission_mode -ceq 'NATIVE_ASK' -and
        $grant.lifetime -ceq 'current_task' -and $grant.task_id -ceq 'task-7')

    $sibling = Decide 'kovan' $operation '.opencode/plugins/sibling/index.ts' 'src/**' $rootPath $grant $true $true $false @() 'ASK'
    Check 'AUTH4_SIBLING_SCOPE_NEEDS_NEW_AUTHORITY' ($sibling.decision -eq 'NEED_AUTHORITY' -and
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

    foreach ($path in @('.opencode/agents/kovan.md','.opencode/commands/maintain.md',
        '.opencode/orchestrator-install.json','.opencode/opencode.json','.opencode/opencode.jsonc',
        '.codex/agents/kovan.toml','.codex/config.toml','CODEX.md','olympus/core/models.toml',
        'olympus/roles/kael.md','olympus/policies/authority.md','scripts/render_harnesses.py',
        'opencode.json','opencode.jsonc')) {
        Check ('AUTH9_NATIVE_DENY_' + ($path -replace '[^A-Za-z0-9]','_')) ((Native-Decision $nativeRules 'edit' $path) -eq 'DENY')
    }
    $normalAgents = @(Get-ChildItem -LiteralPath (Join-Path $root '.opencode/agents') -Filter '*.md' -File | Where-Object BaseName -ne 'aegis')
    $coreProtectionValid = @($normalAgents | Where-Object {
        $agentRules = Read-NativeRules ([IO.File]::ReadAllText($_.FullName)) @($config.permissions)
        @('olympus/core/models.toml','olympus/roles/kael.md','olympus/policies/authority.md',
          '.codex/config.toml','CODEX.md','scripts/render_harnesses.py' | Where-Object {
            (Native-Decision $agentRules 'edit' $_) -ne 'DENY'
        }).Count -gt 0
    }).Count -eq 0
    Check 'AUTH9_CORE_AND_GENERATOR_PROTECTED_FOR_NORMAL_AGENTS' $coreProtectionValid
    $managedPaths = @('opencode.jsonc', 'CODEX.md', '.opencode/orchestrator-install.json',
        '.codex/orchestrator-install.json')
    foreach ($surface in @('.opencode', '.codex')) {
        $managedPaths += @(Get-ChildItem -LiteralPath (Join-Path $root $surface) -File -Recurse | ForEach-Object {
            $_.FullName.Substring(([IO.Path]::GetFullPath($root).TrimEnd([char[]]@('\','/')).Length + 1)).Replace('\','/')
        })
    }
    Check 'AUTH9B_EVERY_INSTALLER_MANAGED_PATH_HAS_NATIVE_DENY' (@($managedPaths | Where-Object {
        (Native-Decision $nativeRules 'edit' $_) -ne 'DENY'
    }).Count -eq 0)

    $siblingRepoPath = 'C:\workspace\unrelated-sibling\src\cart.ts'
    $externalDecision = Native-Decision $nativeRules 'external_directory' $siblingRepoPath
    $kaelExternalDecision = Native-Decision $kaelNativeRules 'external_directory' $siblingRepoPath
    Check 'AUTH10_EXTERNAL_SIBLING_REQUIRES_ASK' ($externalDecision -eq 'ASK' -and $kaelExternalDecision -eq 'ASK' -and
        @($nativeRules | Where-Object { $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'allow' }).Count -eq 0)

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
        $kael -match 'Only veyra, orin, kovan, nox, vera, thales, atlas, argus, talos, and helios are valid child role IDs' -and
        $kael -match 'Kael → Aegis remains DENIED')

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

    $runtimeAgents = $null
    Push-Location $root
    try {
        $runtimeJson = (& opencode debug agents 2>$null | Out-String)
        $runtimeExit = $LASTEXITCODE
        if ($runtimeExit -eq 0) { $runtimeAgents = @($runtimeJson | ConvertFrom-Json -Depth 100) }
    } finally { Pop-Location }
    $effectiveKovan = @($runtimeAgents | Where-Object id -eq 'kovan')[0]
    Check 'AUTH14_OPENCODE_EFFECTIVE_RULES' ($null -ne $effectiveKovan -and
        @($effectiveKovan.permissions | Where-Object { $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'deny' }).Count -eq 0 -and
        @($effectiveKovan.permissions | Where-Object { $_.action -eq 'edit' -and $_.resource -eq '.opencode/plugins/**' -and $_.effect -eq 'ask' }).Count -eq 1 -and
        @($effectiveKovan.permissions | Where-Object { $_.action -eq 'edit' -and $_.resource -eq '.opencode/plugins/olympus-activity/**' -and $_.effect -eq 'deny' }).Count -eq 1 -and
        @($effectiveKovan.permissions | Where-Object { $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'ask' }).Count -gt 0 -and
        @($effectiveKovan.permissions | Where-Object { $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'allow' }).Count -eq 0)

    $normalizedDocs = $docs -replace '\s+', ' '
    $reportingPolicy = $normalizedDocs -match '(?is)TOOL_ATTEMPT.*?TOOL_EXECUTION.*?NATIVE_PERMISSION_UI.*?USER_CONFIRMED_EXTERNAL_OBSERVATION.*?NOT_OBSERVABLE.*?Tool success does not establish that ASK was\s+absent.*?tool failure/denial alone does not establish a human rejection'
    Check 'AUTH15_NATIVE_PERMISSION_OBSERVABILITY_POLICY' ($reportingPolicy -and
        $kael -match '(?is)TOOL_ATTEMPT.*?TOOL_EXECUTION.*?NATIVE_PERMISSION_UI.*?NATIVE_PERMISSION_DECISION.*?NOT_OBSERVABLE.*?Tool success does not prove ASK was absent.*?failed\s+or denied tool result does not by itself prove a human rejected.*?USER_CONFIRMED_EXTERNAL_OBSERVATION.*?external/manual evidence' -and
        $kovan -match '(?is)TOOL_ATTEMPT.*?TOOL_EXECUTION.*?NATIVE_PERMISSION_UI.*?NATIVE_PERMISSION_DECISION.*?NOT_OBSERVABLE.*?success never implies\s+`OBSERVED_NO_ASK`.*?USER_CONFIRMED_EXTERNAL_OBSERVATION')

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

    Write-Output 'NATIVE_AUTHORITY_ASK_RUNTIME: NOT ASSESSED BY STATIC QUALIFICATION (report interactive event evidence separately)'
    Write-Output 'AUTHORITY QUALIFICATION: PASS (static contracts, native/effective rules, and deterministic scope/approval cases; interactive outcome not asserted)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'AUTHORITY QUALIFICATION: FAIL'
    exit 1
}
