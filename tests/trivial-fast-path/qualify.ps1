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

function New-Task([hashtable]$overrides = @{}) {
    $task = @{
        Small = $true; SingleOperation = $true; SingleWriter = $true
        ScopeKnown = $true; OwnershipEstablished = $true
        ArchitectureNew = $false; RootCauseUnknown = $false; CrossSubsystem = $false
        Destructive = $false; HighRisk = $false; SecuritySensitive = $false
        ExplicitIndependentReview = $false; CheapAcceptance = $true
        MaterialValidationFailure = $false; ScopeExpanded = $false; ConflictOrDrift = $false
        NativeAsk = $false; NativePermissionEvent = $false; Approved = $false
        ToolSucceeded = $true; ToolSucceededAfterApproval = $true
        RequestedTargetWritten = $true; ExactScopeRespected = $true
        OlympusOwnedModified = $false; ObjectiveVerified = $true
        ExactBytesRequired = $false; ByteMatch = $true
        RetryStrategyDifferent = $false; OriginalResultReconciled = $true
    }
    foreach ($key in $overrides.Keys) { $task[$key] = $overrides[$key] }
    return $task
}

function Get-Plan($task) {
    $eligible = $task.Small -and $task.SingleOperation -and $task.SingleWriter -and
        $task.ScopeKnown -and $task.OwnershipEstablished -and
        -not $task.ArchitectureNew -and -not $task.RootCauseUnknown -and
        -not $task.CrossSubsystem -and -not $task.Destructive -and
        -not $task.HighRisk -and -not $task.SecuritySensitive -and
        -not $task.ExplicitIndependentReview -and $task.CheapAcceptance -and
        -not $task.MaterialValidationFailure -and -not $task.ScopeExpanded -and
        -not $task.ConflictOrDrift
    if ($eligible) {
        return [pscustomobject]@{
            FastPath = $true; ChildCount = 1; Roles = @('kovan')
            NormalAllowed = $false; IndependentReviewPreserved = $false
        }
    }
    [pscustomobject]@{
        FastPath = $false; ChildCount = 0; Roles = @()
        NormalAllowed = $true; IndependentReviewPreserved = [bool]$task.ExplicitIndependentReview
    }
}

function Invoke-FastPath($task) {
    $plan = Get-Plan $task
    if (-not $plan.FastPath) {
        return [pscustomobject]@{
            Status = 'EXITED_BEFORE_LAUNCH'; ChildCount = 0; Roles = @()
            Retries = 0; VerificationStages = 0; UnnecessaryVerificationStages = 0
            Acceptance = $false; PermissionAcceptance = $false; NormalAllowed = $true
        }
    }
    $permissionAccepted = -not $task.NativeAsk -or (
        $task.NativePermissionEvent -and $task.Approved -and $task.ToolSucceededAfterApproval)
    $bytesAccepted = -not $task.ExactBytesRequired -or $task.ByteMatch
    $accepted = $permissionAccepted -and $task.ToolSucceeded -and
        $task.RequestedTargetWritten -and $task.ExactScopeRespected -and
        -not $task.OlympusOwnedModified -and $task.ObjectiveVerified -and $bytesAccepted
    $materialFailure = -not $permissionAccepted -or -not $task.ToolSucceeded -or
        -not $task.RequestedTargetWritten -or -not $task.ExactScopeRespected -or
        $task.OlympusOwnedModified -or -not $task.ObjectiveVerified -or
        ($task.ExactBytesRequired -and -not $task.ByteMatch)
    $retryEligible = -not $accepted -and $materialFailure -and
        $task.OriginalResultReconciled -and $task.RetryStrategyDifferent
    [pscustomobject]@{
        Status = $(if ($accepted) { 'ACCEPTED' } elseif ($retryEligible) { 'MATERIAL_FAILURE_RETRY_JUSTIFIED' } else { 'STOP_OR_ESCALATE' })
        ChildCount = 1; Roles = @('kovan'); Retries = [int]$retryEligible
        VerificationStages = 1; UnnecessaryVerificationStages = 0
        Acceptance = $accepted; PermissionAcceptance = $permissionAccepted
        NormalAllowed = -not $accepted
    }
}

try {
    $kael = Text '.opencode/agents/kael.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $section = [regex]::Match($kael, '(?ms)^## Trivial task / authority fast path\r?\n(?<body>.*?)(?=^## |\z)').Groups['body'].Value

    Check 'FAST_POLICY_SPECIALIST_VALUE' ($section -match 'Specialist value must exceed orchestration cost' -and
        $section -match 'do not launch Veyra' -and $section -match 'do not launch Nox' -and
        $section -match 'do not launch Vera')
    Check 'FAST_POLICY_ELIGIBILITY' ($section -match 'one operation or a small' -and
        $section -match 'exact target/scope is known' -and $section -match 'ownership is\s+already sufficiently established' -and
        $section -match 'no new architecture' -and $section -match 'uncertain diagnosis/root cause' -and
        $section -match 'cross-cutting or\s+cross-subsystem' -and $section -match 'not destructive, high-risk, security-sensitive' -and
        $section -match 'explicit request for independent review' -and $section -match 'checked directly and cheaply')
    Check 'FAST_POLICY_NATIVE_ASK' ($section -match 'exact operation, `WRITE_SCOPE`, canonical\s+repository root' -and
        $section -match 'only the writer with the\s+exact `NATIVE_ASK` grant' -and
        $section -match 'rejection or\s+cancellation stops it without fallback' -and
        $section -match 'requested target was written within exact scope' -and
        $section -match 'no Olympus-owned\s+resource was modified')
    Check 'FAST_POLICY_PROPORTIONAL_ACCEPTANCE' ($section -match 'formatting such as a trailing newline as\s+irrelevant unless the user or task explicitly requires exact bytes' -and
        $section -match 'Derive\s+acceptance from the stated objective' -and
        $section -match 'Do not\s+require full-repository hashes, Git audits, or Olympus-wide revalidation')
    Check 'FAST_POLICY_RETRY_AND_EXIT' ($section -match 'Do not repeat a writer call' -and
        $section -match 'material acceptance criterion failed' -and
        $section -match 'a different bounded strategy is justified' -and
        $section -match 'material\s+validation failure' -and $section -match 'unknown root cause' -and
        $section -match 'security-sensitive behavior' -and $section -match 'conflict/drift' -and
        $section -match 'scope expansion' -and $section -match 'Reconcile the original\s+writer')
    Check 'FAST_POLICY_PERFORMANCE_METRICS' ($section -match 'not a wall-clock SLA' -and
        $section -match 'child count, role count, retries and\s+unnecessary verification stages' -and
        $docs -match 'not a seconds\s+SLA')
    Check 'FAST_POLICY_GENERIC' ($docs -match 'special-case project names' -and
        $section -match 'eligible write' -and $section -match 'actual objective')
    Check 'FAST_POLICY_TRIVIAL_COMPLETION_GATE' ($kael -match 'TRIVIAL FAST-PATH CHANGE: one scoped implementer plus lightweight direct Master Orchestrator validation' -and
        $kael -match 'no separate tester/reviewer unless the user requests review')

    # A small, deterministic write has exactly one writer child and no specialist stages.
    $single = Invoke-FastPath (New-Task)
    Check 'CASE1_SINGLE_TRIVIAL_WRITE_ONE_WRITER' ($single.Acceptance -and $single.ChildCount -eq 1 -and
        @($single.Roles).Count -eq 1 -and $single.Roles[0] -eq 'kovan' -and $single.Retries -eq 0 -and
        $single.VerificationStages -eq 1 -and $single.UnnecessaryVerificationStages -eq 0)

    # Native ASK has one writer; only the approved tool success and scoped target satisfy it.
    $nativeAsk = Invoke-FastPath (New-Task @{ NativeAsk=$true; NativePermissionEvent=$true; Approved=$true })
    Check 'CASE2_TRIVIAL_NATIVE_ASK_WRITER_ONLY' ($nativeAsk.Acceptance -and $nativeAsk.PermissionAcceptance -and
        $nativeAsk.ChildCount -eq 1 -and @($nativeAsk.Roles).Count -eq 1 -and
        $nativeAsk.Roles[0] -eq 'kovan' -and $nativeAsk.Retries -eq 0 -and
        $nativeAsk.VerificationStages -eq 1 -and $nativeAsk.UnnecessaryVerificationStages -eq 0)
    $nativeDenied = Invoke-FastPath (New-Task @{ NativeAsk=$true; NativePermissionEvent=$true; Approved=$false })
    Check 'CASE2B_NATIVE_ASK_DENIAL_STOPS' (-not $nativeDenied.Acceptance -and -not $nativeDenied.PermissionAcceptance -and
        $nativeDenied.Retries -eq 0)
    $authorityScopeFailure = Invoke-FastPath (New-Task @{
        NativeAsk=$true; NativePermissionEvent=$true; Approved=$true
        ToolSucceededAfterApproval=$false; RequestedTargetWritten=$false
        ExactScopeRespected=$false; OlympusOwnedModified=$true
    })
    Check 'CASE2C_AUTHORITY_ACCEPTANCE_GUARDS' (-not $authorityScopeFailure.Acceptance -and
        -not $authorityScopeFailure.PermissionAcceptance -and $authorityScopeFailure.Retries -eq 0)

    # Whitespace is irrelevant unless exact bytes are an explicit acceptance criterion.
    $newline = Invoke-FastPath (New-Task @{ NativeAsk=$true; NativePermissionEvent=$true; Approved=$true; ByteMatch=$false })
    Check 'CASE3_IRRELEVANT_NEWLINE_NO_RETRY' ($newline.Acceptance -and $newline.Retries -eq 0)
    $exactBytes = Invoke-FastPath (New-Task @{ ExactBytesRequired=$true; ByteMatch=$false; RetryStrategyDifferent=$true })
    Check 'CASE4_EXACT_BYTES_MISMATCH_MATERIAL' (-not $exactBytes.Acceptance -and
        $exactBytes.Retries -eq 1 -and $exactBytes.Status -eq 'MATERIAL_FAILURE_RETRY_JUSTIFIED')
    $noRetryWithoutNewStrategy = Invoke-FastPath (New-Task @{ ExactBytesRequired=$true; ByteMatch=$false })
    Check 'CASE4B_NO_UNJUSTIFIED_RETRY' (-not $noRetryWithoutNewStrategy.Acceptance -and $noRetryWithoutNewStrategy.Retries -eq 0)

    # Established ownership is reused; simple, observable success does not require Nox.
    $owned = Get-Plan (New-Task @{ OwnershipEstablished=$true })
    $direct = Invoke-FastPath (New-Task)
    Check 'CASE5_ESTABLISHED_OWNERSHIP_NO_VEYRA' ($owned.FastPath -and $owned.Roles -notcontains 'veyra')
    Check 'CASE6_DIRECT_WRITER_VERIFICATION_NO_NOX' ($direct.Acceptance -and
        $direct.Roles -notcontains 'nox' -and $direct.UnnecessaryVerificationStages -eq 0)

    # Material evidence and explicit exclusions return to normal orchestration.
    $materialFailure = Get-Plan (New-Task @{ MaterialValidationFailure=$true })
    $unknownCause = Get-Plan (New-Task @{ RootCauseUnknown=$true })
    $crossSubsystem = Get-Plan (New-Task @{ CrossSubsystem=$true })
    $destructive = Get-Plan (New-Task @{ Destructive=$true })
    $highRisk = Get-Plan (New-Task @{ HighRisk=$true })
    Check 'CASE7_MATERIAL_VALIDATION_FAILURE_EXITS' (-not $materialFailure.FastPath -and $materialFailure.NormalAllowed)
    $failedAfterWrite = Invoke-FastPath (New-Task @{ ObjectiveVerified=$false })
    Check 'CASE7B_MATERIAL_FAILURE_AFTER_WRITE_EXITS' (-not $failedAfterWrite.Acceptance -and
        $failedAfterWrite.Status -eq 'STOP_OR_ESCALATE' -and $failedAfterWrite.ChildCount -eq 1 -and
        $failedAfterWrite.Retries -eq 0 -and $failedAfterWrite.NormalAllowed)
    Check 'CASE8_UNKNOWN_ROOT_CAUSE_PROHIBITS_FAST_PATH' (-not $unknownCause.FastPath -and $unknownCause.NormalAllowed)
    Check 'CASE9_CROSS_SUBSYSTEM_NORMAL_ORCHESTRATION' (-not $crossSubsystem.FastPath -and $crossSubsystem.NormalAllowed)
    Check 'CASE10_DESTRUCTIVE_HIGH_RISK_PROHIBITED' (-not $destructive.FastPath -and -not $highRisk.FastPath)
    $security = Get-Plan (New-Task @{ SecuritySensitive=$true })
    Check 'CASE10B_SECURITY_SENSITIVE_PROHIBITED' (-not $security.FastPath)

    $reviewRequested = Get-Plan (New-Task @{ ExplicitIndependentReview=$true })
    Check 'CASE11_EXPLICIT_INDEPENDENT_REVIEW_PRESERVED' (-not $reviewRequested.FastPath -and
        $reviewRequested.NormalAllowed -and $reviewRequested.IndependentReviewPreserved)
    $expanded = Get-Plan (New-Task @{ ScopeExpanded=$true })
    Check 'CASE12_SCOPE_EXPANSION_EXITS_AND_RECONCILES' (-not $expanded.FastPath -and
        $expanded.NormalAllowed -and $section -match 'Reconcile the original\s+writer before starting dependent work' -and
        $section -match 'reclassify authority')
    $outOfScopeResult = Invoke-FastPath (New-Task @{ ExactScopeRespected=$false })
    Check 'CASE12B_OUT_OF_SCOPE_RESULT_STOPS_WITHOUT_RETRY' (-not $outOfScopeResult.Acceptance -and
        $outOfScopeResult.Status -eq 'STOP_OR_ESCALATE' -and $outOfScopeResult.Retries -eq 0)

    $uncertainOwnership = Get-Plan (New-Task @{ OwnershipEstablished=$false })
    $conflict = Get-Plan (New-Task @{ ConflictOrDrift=$true })
    Check 'CASE13_UNCERTAIN_OWNERSHIP_AND_DRIFT_PROHIBITED' (-not $uncertainOwnership.FastPath -and -not $conflict.FastPath)

    Write-Output 'TRIVIAL_AUTHORITY_FAST_PATH: PASS (static policy + deterministic synthetic cases; interactive routing not asserted)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'TRIVIAL_AUTHORITY_FAST_PATH: FAIL'
    exit 1
}
