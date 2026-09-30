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

# Synthetic event model: no elapsed-time assumptions and no real agent/runtime call.
function Invoke-Maintain([string]$authorization, [string]$caller,
                        [string[]]$operations = @()) {
    $events = [Collections.Generic.List[string]]::new()
    $events.Add('AUTH_CHECK')
    $valid = ($caller -eq 'USER' -and $authorization -in @('CURRENT_EXPLICIT_MAINTAIN','DURABLE_CURRENT_RUN_AUTH'))
    $events.Add('SCOPE_DECISION')
    $decision = if ($valid) { 'ACCEPTED' } else { 'REJECTED' }
    if (-not $valid) {
        return [pscustomobject]@{ authorization='UNPROVEN'; decision=$decision; events=$events.ToArray() }
    }
    $events.Add('TRUSTED_CURRENT_AUTH')
    foreach ($operation in $operations) { $events.Add("EXPENSIVE_WORK_SENTINEL:$operation") }
    [pscustomobject]@{ authorization='VALID'; decision=$decision; events=$events.ToArray() }
}

function Permit-Operation([string[]]$authorizedScope, [string]$operation,
                          [bool]$specificHighImpactAuthorization) {
    if ($operation -notin $authorizedScope) { return 'DENIED_SCOPE_BROADENING' }
    if ($operation -in @('COMMIT','PUSH','FORCE_PUSH','RESET','DELETE_REF','PUBLISH') -and
        -not $specificHighImpactAuthorization) { return 'BLOCKED_HIGH_IMPACT' }
    'ALLOWED'
}

try {
    $core = Text 'olympus/policies/maintenance-plane.md'
    $aegis = Text '.opencode/agents/aegis.md'
    $command = Text '.opencode/commands/maintain.md'
    $kael = Text '.opencode/agents/kael.md'
    $aegisSource = Text 'olympus/harnesses/opencode/agent-prompts/aegis.md'
    $commandSource = Text 'olympus/harnesses/opencode/maintain.md'
    $kaelSource = Text 'olympus/harnesses/opencode/agent-prompts/kael.md'
    $canonicalPolicy = ($core -replace '\r\n?', "`n").Trim()
    $canonicalAegis = $aegis -replace '\r\n?', "`n"
    $canonicalCommand = $command -replace '\r\n?', "`n"
    $canonicalCommandSource = $commandSource -replace '\r\n?', "`n"

    Check 'CORE_AUTHORIZATION_IS_ONLY_ADMISSION_GATE' (
        $core -match 'The only admission rule is trusted authorization for this current Aegis run' -and
        $core -match 'Neither repository, target owner, path, branch, task wording, nor operation can\s+establish or defeat admission' -and
        $core -notmatch 'Aegis rejects.*user project|user-project.*OUT_OF_SCOPE.*Aegis')
    Check 'CORE_AUTH_CHECK_ORDER_AND_FAST_REJECTION' (
        $core.IndexOf('AUTH_CHECK → SCOPE_DECISION → WORK', [StringComparison]::Ordinal) -ge 0 -and
        $core -match 'Unproven authorization means REJECTED immediately' -and
        $aegis -match 'If neither current nor durable authorization is provable' -and
        $aegis -match 'report `MAINTENANCE_AUTH: UNPROVEN` and `AEGIS_SCOPE: REJECTED`' -and
        $aegis -match 'report `MAINTENANCE_AUTH: VALID` and `AEGIS_SCOPE: ACCEPTED`' -and
        $core -match 'Do not read the repository, search, inspect\s+paths, qualify, implement, run Git, or reconstruct historical checkpoints')
    Check 'CORE_TASK_SCOPE_AND_HIGH_IMPACT_RETAINED' (
        $core -match 'A task X never\s+authorizes unrelated Y' -and
        $core -match 'Commit, push, release, destructive changes, and other\s+high-impact effects require authorization specific and proportionate' -and
        $core -match 'Missing output is not failure or retry\s+permission')
    Check 'CORE_NORMAL_KAEL_OWNERSHIP_IS_SEPARATE' (
        $core -match 'This ownership rule protects the\s+normal Kael workflow; it is not an Aegis\s+admission criterion' -and
        $core -match 'Kael must not silently widen normal task scope,\s+invoke Aegis, or automatically recommend `/maintain`')
    Check 'OPENCODE_AEGIS_AND_COMMAND_DERIVE_CORE_POLICY' (
        $aegisSource.Contains('{{maintenance_plane_policy}}') -and
        $commandSource.Contains('{{maintenance_plane_policy}}') -and
        $canonicalAegis.Contains($canonicalPolicy) -and $canonicalCommand.Contains($canonicalPolicy))
    Check 'COMMAND_HAS_TRUSTED_CONTEXT_OUTSIDE_TASK_ARGUMENTS' (
        $canonicalCommandSource.StartsWith("---`n", [StringComparison]::Ordinal) -and
        $canonicalCommandSource.IndexOf('Trusted command context: the user explicitly invoked `/maintain` for this current run.', [StringComparison]::Ordinal) -lt
            $canonicalCommandSource.IndexOf('$ARGUMENTS', [StringComparison]::Ordinal) -and
        $canonicalCommandSource -match '(?m)^agent: aegis\s*$' -and $canonicalCommandSource -match '(?m)^subagent: true\s*$' -and
        $canonicalCommand.StartsWith("---`n", [StringComparison]::Ordinal) -and
        $command -match '(?m)^agent: aegis\s*$' -and $command -match '(?m)^subagent: true\s*$')

    $authIndex = $aegis.IndexOf('First perform the deterministic authorization check', [StringComparison]::Ordinal)
    $scopeIndex = $aegis.IndexOf('AEGIS_SCOPE: ACCEPTED', [StringComparison]::Ordinal)
    $workIndex = $aegis.IndexOf('## Git-administration fast path', [StringComparison]::Ordinal)
    Check 'OPENCODE_AUTH_SCOPE_WORK_ORDER' ($authIndex -ge 0 -and $scopeIndex -gt $authIndex -and $workIndex -gt $scopeIndex)
    Check 'KAEL_NORMAL_PROTECTION_DERIVES_FROM_CORE' (
        $kaelSource.Contains('{{normal_plane_ownership_protection}}') -and
        $kael -match 'This ownership rule protects the\s+normal Kael workflow' -and
        $kael -match 'not an Aegis\s+admission criterion' -and
        $kael -match 'Kael must not silently widen normal task scope')

    # A/B — current explicit invocation accepts in Olympus and user repositories.
    $olympus = Invoke-Maintain 'CURRENT_EXPLICIT_MAINTAIN' 'USER' @('EDIT_OLYMPUS_POLICY')
    $userProject = Invoke-Maintain 'CURRENT_EXPLICIT_MAINTAIN' 'USER' @('EDIT_USER_FILE')
    Check 'CASE_A_EXPLICIT_MAINTAIN_OLYMPUS_ACCEPTS' ($olympus.authorization -eq 'VALID' -and
        $olympus.decision -eq 'ACCEPTED' -and $olympus.events[0] -eq 'AUTH_CHECK' -and
        $olympus.events[1] -eq 'SCOPE_DECISION')
    Check 'CASE_B_EXPLICIT_MAINTAIN_USER_PROJECT_ACCEPTS' ($userProject.authorization -eq 'VALID' -and
        $userProject.decision -eq 'ACCEPTED' -and $userProject.events[-1] -eq 'EXPENSIVE_WORK_SENTINEL:EDIT_USER_FILE')

    # C/D — ordinary project edits and explicitly scoped Git operations are admitted.
    $ordinaryEdit = Invoke-Maintain 'CURRENT_EXPLICIT_MAINTAIN' 'USER' @('EDIT_SRC_FOO_TS')
    $gitTask = Invoke-Maintain 'CURRENT_EXPLICIT_MAINTAIN' 'USER' @('COMMIT','PUSH')
    Check 'CASE_C_EXPLICIT_ORDINARY_PROJECT_EDIT_ACCEPTS' ($ordinaryEdit.decision -eq 'ACCEPTED' -and
        $ordinaryEdit.events[-1] -eq 'EXPENSIVE_WORK_SENTINEL:EDIT_SRC_FOO_TS')
    Check 'CASE_D_EXPLICIT_GIT_SCOPE_ACCEPTS' ($gitTask.decision -eq 'ACCEPTED' -and
        $gitTask.events[-1] -eq 'EXPENSIVE_WORK_SENTINEL:PUSH')

    # E/H/K — absence of current/durable authorization, self-activation and arbitrary claims stop early.
    foreach ($case in @(
        [pscustomobject]@{ id='NO_MAINTAIN'; authorization='NONE'; caller='USER' },
        [pscustomobject]@{ id='AEGIS_SELF_ACTIVATION'; authorization='CURRENT_EXPLICIT_MAINTAIN'; caller='AEGIS_SELF' },
        [pscustomobject]@{ id='PROMPT_CLAIM'; authorization='PROMPT_CLAIM'; caller='USER' }
    )) {
        $rejected = Invoke-Maintain $case.authorization $case.caller @('SENTINEL')
        Check "CASE_$($case.id)_REJECTS_BEFORE_WORK" ($rejected.authorization -eq 'UNPROVEN' -and
            $rejected.decision -eq 'REJECTED' -and $rejected.events.Count -eq 2 -and
            $rejected.events[0] -eq 'AUTH_CHECK' -and $rejected.events[1] -eq 'SCOPE_DECISION')
    }

    # F/G — Kael and child agents are never authorized Aegis entry paths.
    foreach ($caller in @('KAEL','CHILD')) {
        $denied = Invoke-Maintain 'CURRENT_EXPLICIT_MAINTAIN' $caller @('SENTINEL')
        Check "CASE_${caller}_AEGIS_INVOCATION_DENIED" ($denied.decision -eq 'REJECTED' -and $denied.events.Count -eq 2)
    }

    # I/J — current-run durable auth accepts immediately; absent durable auth rejects without work.
    $checkpoint = Invoke-Maintain 'DURABLE_CURRENT_RUN_AUTH' 'USER' @('RESUME_SAME_TASK')
    $noCheckpointAuth = Invoke-Maintain 'NONE' 'USER' @('HISTORICAL_RECONSTRUCTION_SENTINEL')
    Check 'CASE_I_DURABLE_CURRENT_RUN_AUTH_ACCEPTS' ($checkpoint.authorization -eq 'VALID' -and
        $checkpoint.decision -eq 'ACCEPTED' -and $checkpoint.events[0] -eq 'AUTH_CHECK' -and
        $checkpoint.events[1] -eq 'SCOPE_DECISION')
    Check 'CASE_J_CHECKPOINT_WITHOUT_AUTH_REJECTS_IMMEDIATELY' ($noCheckpointAuth.decision -eq 'REJECTED' -and
        $noCheckpointAuth.events.Count -eq 2 -and $noCheckpointAuth.events -notcontains 'EXPENSIVE_WORK_SENTINEL:HISTORICAL_RECONSTRUCTION_SENTINEL')

    # L/M — explicit admission never broadens task scope or grants destructive effects.
    Check 'CASE_L_UNRELATED_SCOPE_BROADENING_BLOCKED' (
        (Permit-Operation @('EDIT_SRC_FOO_TS','RUN_FOO_TEST') 'CHANGE_GLOBAL_SETTINGS' $false) -eq 'DENIED_SCOPE_BROADENING')
    Check 'CASE_M_UNAUTHORIZED_HIGH_IMPACT_OPERATION_BLOCKED' (
        (Permit-Operation @('EDIT_SRC_FOO_TS') 'PUSH' $false) -eq 'DENIED_SCOPE_BROADENING' -and
        (Permit-Operation @('PUSH') 'PUSH' $false) -eq 'BLOCKED_HIGH_IMPACT' -and
        (Permit-Operation @('PUSH') 'PUSH' $true) -eq 'ALLOWED')

    # O — accepted and rejected flows both place work strictly after authorization and scope.
    foreach ($accepted in @($olympus,$userProject,$ordinaryEdit,$gitTask,$checkpoint)) {
        $work = [Array]::FindIndex([string[]]$accepted.events, [Predicate[string]]{ param($event) $event.StartsWith('EXPENSIVE_WORK_SENTINEL:', [StringComparison]::Ordinal) })
        Check 'EXPENSIVE_WORK_SENTINEL_AFTER_AUTH_AND_SCOPE' ($accepted.events[0] -eq 'AUTH_CHECK' -and
            $accepted.events[1] -eq 'SCOPE_DECISION' -and $work -gt 1)
    }

    Write-Output 'MAINTENANCE AUTHORIZATION / SCOPE QUALIFICATION: PASS (Core/adapter static contracts + deterministic synthetic cases; no live runtime claim)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'MAINTENANCE AUTHORIZATION / SCOPE QUALIFICATION: FAIL'
    exit 1
}
