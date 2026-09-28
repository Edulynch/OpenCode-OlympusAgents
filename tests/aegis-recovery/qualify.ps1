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

function New-Result([string]$id) {
    [pscustomobject]@{ id=$id; consumed=$false; consumedCount=0; outputAvailable=$false }
}
function Test-ExactOwnership($receipt, $process) {
    ($receipt.runId -and $receipt.runId -eq $process.runId -and
     $receipt.pid -eq $process.pid -and $receipt.startTime -eq $process.startTime -and
     $receipt.executable -eq $process.executable -and $receipt.commandLine -eq $process.commandLine -and
     $receipt.workingDirectory -eq $process.workingDirectory -and
     $receipt.parentPid -eq $process.parentPid -and $receipt.parentStartTime -eq $process.parentStartTime -and
     $receipt.ownerMarker -and $process.commandLine.Contains($receipt.ownerMarker))
}
function Reconcile-Result($assignment, [bool]$terminalResultAvailable, [string]$storedOutcome,
                          [DateTimeOffset]$metadataAt, [DateTimeOffset]$latestActivityAt,
                          [bool]$absentFromActive) {
    if ($terminalResultAvailable) {
        if ($assignment.consumed) { $action='IGNORE_DUPLICATE' }
        else { $assignment.consumed=$true; $assignment.consumedCount++; $action='CONSUME_ORIGINAL' }
        return [pscustomobject]@{ state='TERMINAL_COLLECTED_WORK'; outcome='FROM_RESULT'; action=$action; retry=$false }
    }
    if ((-not [string]::IsNullOrWhiteSpace($storedOutcome)) -and $latestActivityAt -gt $metadataAt) {
        return [pscustomobject]@{ state='STATE_INCONSISTENT_AFTER_RESTART'; outcome='UNRESOLVED'; action='RECONCILE_ORIGINAL'; retry=$false }
    }
    if ($absentFromActive) {
        return [pscustomobject]@{ state='ORPHAN_CANDIDATE'; outcome='UNRESOLVED'; action='RECONCILE_ORIGINAL'; retry=$false }
    }
    [pscustomobject]@{ state='LIVE_OWNED_WORK'; outcome='UNRESOLVED'; action='WAIT_ORIGINAL'; retry=$false }
}
function Classify-Process([bool]$owned, [bool]$progress, [bool]$noProgressWindow,
                          [bool]$parentGone, [bool]$resultRecoverable, [bool]$identityRechecked) {
    if (-not $owned) { return [pscustomobject]@{ state='UNKNOWN'; owned=$false; terminate=$false; retry=$false; cleanup='NONE' } }
    if ($progress) { return [pscustomobject]@{ state='ACTIVE'; owned=$true; terminate=$false; retry=$false; cleanup='WAIT' } }
    if (-not $noProgressWindow) { return [pscustomobject]@{ state='UNKNOWN'; owned=$true; terminate=$false; retry=$false; cleanup='OBSERVE_BOUNDEDLY' } }
    if ($resultRecoverable) { return [pscustomobject]@{ state='STALLED'; owned=$true; terminate=$false; retry=$false; cleanup='COLLECT_ORIGINAL_RESULT' } }
    if ($parentGone) {
        $safe = $identityRechecked
        return [pscustomobject]@{ state='ORPHANED'; owned=$true; terminate=$safe; retry=$false; cleanup=$(if ($safe) { 'TERMINATE_EXACT_IDENTITY' } else { 'RECHECK_EXACT_IDENTITY' }) }
    }
    $safe = $identityRechecked
    [pscustomobject]@{ state='STALLED'; owned=$true; terminate=$safe; retry=$false; cleanup=$(if ($safe) { 'TERMINATE_EXACT_IDENTITY' } else { 'RECHECK_EXACT_IDENTITY' }) }
}
function Revalidate-Gates([object[]]$gates, [string]$lostGate, $processState,
                          [bool]$exactTerminationRechecked, [bool]$cleanupCompleted,
                          [bool]$explicitAuthorization, [bool]$repeatSafe,
                          [bool]$duplicationRuledOut) {
    $ownedCleanup = ($processState.owned -and $processState.terminate -and
        $processState.state -in @('ORPHANED','STALLED') -and $exactTerminationRechecked -and $cleanupCompleted)
    $affected = @($gates | Where-Object { $_.id -eq $lostGate -and -not $_.collected -and -not $_.resultRecoverable })
    $eligible = @(); if ($ownedCleanup -and $affected.Count -eq 1) { $eligible = @($affected | ForEach-Object id) }
    $repeat = @(); if ($eligible.Count -eq 1 -and $explicitAuthorization -and $repeatSafe -and $duplicationRuledOut) { $repeat = @($eligible) }
    [pscustomobject]@{ eligible=$eligible; repeatEligible=$repeat; retryNow=$false }
}

try {
    $aegis = Text '.opencode/agents/aegis.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $kael = Text '.opencode/agents/kael.md'
    Check 'RECOVERY_STATIC_CHRONOLOGY' ($aegis -match 'later message,\s+tool, process-progress, or collected-result evidence outranks an older metadata' -and
        $aegis -match 'stored outcome predates later observable activity' -and
        $aegis -match 'LIVE_OWNED_WORK, TERMINAL_COLLECTED_WORK' -and
        $aegis -match 'ORPHAN_CANDIDATE, or\s+CONFIRMED_OWNED_ORPHAN' -and
        $aegis -match 'STATE_INCONSISTENT_AFTER_RESTART' -and $docs -match 'preserves chronological evidence')
    Check 'RECOVERY_ACTIVE_ABSENCE_NOT_COMPLETION' ($aegis -match '(?s)An absent active-session entry proves only absence from that endpoint.s current\s+list' -and
        $docs -match 'Absence from `/api/session/active` means only that the session is absent')
    Check 'RECOVERY_PROCESS_STATES' ($aegis -match 'ACTIVE only with meaningful progress evidence' -and
        $aegis -match 'STALLED only after no meaningful progress over a finite' -and
        $aegis -match 'ORPHANED only when Olympus/Aegis ownership is verified' -and
        $aegis -match 'otherwise UNKNOWN' -and $docs -match 'Classify each process as ACTIVE' -and
        $aegis -match '`Responding=True`' -and $aegis -match 'parent disappearance alone is not ownership or progress evidence')
    Check 'RECOVERY_OWNER_RECEIPT' ($aegis -match 'unique task/run ID' -and
        $aegis -match 'PID and process start time' -and
        $aegis -match 'executable path' -and $aegis -match 'exact launch\s+arguments/command line' -and
        $aegis -match 'working directory' -and $aegis -match 'unambiguous task/run ownership marker where supported' -and
        $aegis -match 'parent PID and parent start time' -and $aegis -match 'expected result path' -and
        $aegis -match 'latest meaningful progress timestamp/counter' -and
        $aegis -match 'not a registry' -and $aegis -match 'remove it after validated result collection')
    Check 'RECOVERY_NO_GENERIC_KILL' ($aegis -match 'never kill by process\s+name, generic pattern, or broad process-tree command' -and
        $aegis -match '(?s)recheck the exact PID,.*?ownership marker immediately')
    Check 'RECOVERY_TARGETED_REVALIDATION' ($aegis -match 'Mark only the\s+affected, lost, uncollected gate eligible for explicit revalidation' -and
        $aegis -match 'first search for the original output' -and $aegis -match 'duplication is ruled\s+out')
    Check 'RECOVERY_NO_MISSING_RETRY' ($aegis -match 'Missing output is not failure and is not permission to retry' -and
        $aegis -match 'consume the original result once' -and $kael -match 'MISSING PARENT TOOL OUTPUT != CHILD FAILURE')

    $metadataAt = [DateTimeOffset]::Parse('2026-09-28T10:00:00Z')
    $laterActivityAt = [DateTimeOffset]::Parse('2026-09-28T10:00:05Z')
    $stale = Reconcile-Result (New-Result 'stale-failed') $false 'failed' $metadataAt $laterActivityAt $false
    Check 'CASE_EARLY_FAILED_LATER_ACTIVITY' ($stale.state -eq 'STATE_INCONSISTENT_AFTER_RESTART' -and
        $stale.outcome -eq 'UNRESOLVED' -and -not $stale.retry)
    $staleSuccess = Reconcile-Result (New-Result 'stale-succeeded') $false 'succeeded' $metadataAt $laterActivityAt $true
    Check 'CASE_STALE_SUCCESS_LATER_ACTIVITY' ($staleSuccess.state -eq 'STATE_INCONSISTENT_AFTER_RESTART' -and
        $staleSuccess.outcome -eq 'UNRESOLVED' -and -not $staleSuccess.retry)
    $absent = Reconcile-Result (New-Result 'absent-active') $false 'succeeded' $metadataAt $metadataAt $true
    Check 'CASE_ABSENT_ACTIVE_NOT_COMPLETE' ($absent.state -eq 'ORPHAN_CANDIDATE' -and
        $absent.outcome -eq 'UNRESOLVED' -and -not $absent.retry)

    $receipt = [pscustomobject]@{ runId='aegis-run-01'; pid=4124; startTime='2026-09-28T10:00:00Z';
        executable='C:\Program Files\PowerShell\7\pwsh.exe'; commandLine='pwsh -File qualify.ps1 --aegis-run aegis-run-01';
        workingDirectory='C:\Temp\opencode\aegis-run-01'; ownerMarker='--aegis-run aegis-run-01';
        parentPid=3800; parentStartTime='2026-09-28T09:59:00Z'; expectedResultPath='C:\Temp\opencode\aegis-run-01\result.json' }
    $ownedProcess = [pscustomobject]@{ runId=$receipt.runId; pid=$receipt.pid; startTime=$receipt.startTime;
        executable=$receipt.executable; commandLine=$receipt.commandLine; workingDirectory=$receipt.workingDirectory;
        ownerMarker=$receipt.ownerMarker; parentPid=$receipt.parentPid; parentStartTime=$receipt.parentStartTime;
        responding=$true; parentGone=$false }
    $ownershipProven = Test-ExactOwnership $receipt $ownedProcess
    Check 'CASE_EXACT_PROCESS_OWNERSHIP' ($ownershipProven -and $receipt.ownerMarker -and
        $receipt.expectedResultPath -like '*result.json')

    $active = Classify-Process $ownershipProven $true $false $false $false $true
    Check 'CASE_OWNED_ACTIVE_NO_RETRY' ($active.state -eq 'ACTIVE' -and -not $active.terminate -and -not $active.retry)
    $unrelatedProcess = $ownedProcess.PSObject.Copy()
    $unrelatedProcess.runId = 'unrelated-run'
    $unrelatedOwned = Test-ExactOwnership $receipt $unrelatedProcess
    $unrelated = Classify-Process $unrelatedOwned $false $true $true $false $true
    Check 'CASE_UNRELATED_PROCESS_UNTOUCHED' (-not $unrelatedOwned -and $unrelated.state -eq 'UNKNOWN' -and
        -not $unrelated.terminate -and -not $unrelated.retry -and $unrelated.cleanup -eq 'NONE')
    $pidReuse = $ownedProcess.PSObject.Copy()
    $pidReuse.startTime = '2026-09-28T10:05:00Z'
    Check 'CASE_PID_REUSE_NOT_OWNED' (-not (Test-ExactOwnership $receipt $pidReuse))
    $respondingOnly = Classify-Process $ownershipProven $false $false $false $false $false
    Check 'CASE_RESPONDING_WITHOUT_PROGRESS_NOT_ACTIVE' ($respondingOnly.state -eq 'UNKNOWN' -and
        -not $respondingOnly.terminate -and -not $respondingOnly.retry)

    $ownedOrphan = Classify-Process $ownershipProven $false $true $true $false $true
    Check 'CASE_OWNED_STALLED_ORPHAN_SAFE_PATH' ($ownedOrphan.state -eq 'ORPHANED' -and
        $ownedOrphan.terminate -and $ownedOrphan.cleanup -eq 'TERMINATE_EXACT_IDENTITY' -and -not $ownedOrphan.retry)
    $identityMismatch = Classify-Process $ownershipProven $false $true $true $false $false
    Check 'CASE_ORPHAN_IDENTITY_RECHECK_REQUIRED' ($identityMismatch.state -eq 'ORPHANED' -and
        -not $identityMismatch.terminate -and $identityMismatch.cleanup -eq 'RECHECK_EXACT_IDENTITY')
    $ownedStalled = Classify-Process $ownershipProven $false $true $false $false $true
    Check 'CASE_OWNED_STALLED_BOUNDED_AND_RECHECKED' ($ownedStalled.state -eq 'STALLED' -and
        $ownedStalled.terminate -and $ownedStalled.cleanup -eq 'TERMINATE_EXACT_IDENTITY' -and -not $ownedStalled.retry)
    $stalledNotRechecked = Classify-Process $ownershipProven $false $true $false $false $false
    Check 'CASE_STALLED_RECHECK_REQUIRED' ($stalledNotRechecked.state -eq 'STALLED' -and
        -not $stalledNotRechecked.terminate -and $stalledNotRechecked.cleanup -eq 'RECHECK_EXACT_IDENTITY')
    $stalledWithOutput = Classify-Process $ownershipProven $false $true $true $true $false
    Check 'CASE_RECOVERABLE_RESULT_BEATS_CLEANUP' ($stalledWithOutput.state -eq 'STALLED' -and
        -not $stalledWithOutput.terminate -and $stalledWithOutput.cleanup -eq 'COLLECT_ORIGINAL_RESULT')

    $original = New-Result 'original'
    $collected = Reconcile-Result $original $true $true $metadataAt $laterActivityAt $true
    $duplicate = Reconcile-Result $original $true $true $metadataAt $laterActivityAt $true
    Check 'CASE_ORIGINAL_RESULT_CONSUMED_ONCE' ($collected.action -eq 'CONSUME_ORIGINAL' -and
        $duplicate.action -eq 'IGNORE_DUPLICATE' -and $original.consumedCount -eq 1)
    $gates = @(
        [pscustomobject]@{ id='routing'; collected=$true; resultRecoverable=$true },
        [pscustomobject]@{ id='test-a'; collected=$false; resultRecoverable=$false },
        [pscustomobject]@{ id='release'; collected=$true; resultRecoverable=$true }
    )
    $gateFlags = Revalidate-Gates $gates 'test-a' $ownedOrphan $true $true $false $false $false
    Check 'CASE_CLEANED_ORPHAN_TARGETS_ONLY_LOST_GATE' ($gateFlags.eligible.Count -eq 1 -and
        $gateFlags.eligible[0] -eq 'test-a' -and $gateFlags.repeatEligible.Count -eq 0 -and
        -not $gateFlags.retryNow)
    $unsafeRepeat = Revalidate-Gates $gates 'test-a' $ownedOrphan $true $true $true $false $false
    Check 'CASE_UNSAFE_OR_UNAUTHORIZED_REPEAT_BLOCKED' ($unsafeRepeat.eligible.Count -eq 1 -and
        $unsafeRepeat.repeatEligible.Count -eq 0 -and -not $unsafeRepeat.retryNow)
    $safeRepeat = Revalidate-Gates $gates 'test-a' $ownedOrphan $true $true $true $true $true
    Check 'CASE_EXPLICIT_SAFE_REVALIDATION_ONLY' ($safeRepeat.eligible.Count -eq 1 -and
        $safeRepeat.repeatEligible.Count -eq 1 -and $safeRepeat.repeatEligible[0] -eq 'test-a' -and
        -not $safeRepeat.retryNow)
    $terminalGate = Revalidate-Gates $gates 'routing' $ownedOrphan $true $true $true $true $true
    Check 'CASE_COLLECTED_GATE_NEVER_RERUN' ($terminalGate.eligible.Count -eq 0 -and $terminalGate.repeatEligible.Count -eq 0)
    $unrecheckedGate = Revalidate-Gates $gates 'test-a' $identityMismatch $false $false $true $true $true
    Check 'CASE_NO_REVALIDATION_WITHOUT_VERIFIED_CLEANUP' ($unrecheckedGate.eligible.Count -eq 0 -and
        $unrecheckedGate.repeatEligible.Count -eq 0)

    Write-Output 'AEGIS RECOVERY QUALIFICATION: PASS (static contract + synthetic evidence timelines; no real process termination)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'AEGIS RECOVERY QUALIFICATION: FAIL'
    exit 1
}
