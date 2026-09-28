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

function New-Barrier([object[]]$children, [bool]$questionPending = $false) {
    [pscustomobject]@{ children=@($children); questionPending=$questionPending; events=[Collections.Generic.List[string]]::new() }
}
function New-Child([string]$state, [bool]$resultPending, [bool]$consumed,
                   [bool]$deliveryPending = $false) {
    [pscustomobject]@{ state=$state; resultPending=$resultPending; consumed=$consumed;
        reconciled=$consumed; deliveryPending=$deliveryPending }
}
function Advance-Question($barrier) {
    if (@($barrier.children | Where-Object state -eq 'RUNNING').Count -gt 0 -or
        @($barrier.children | Where-Object resultPending).Count -gt 0 -or
        @($barrier.children | Where-Object deliveryPending).Count -gt 0) {
        return [pscustomobject]@{ asked=$false; state='DEFERRED'; reason='ORIGINAL_WORK_PENDING' }
    }
    if (@($barrier.children | Where-Object state -eq 'UNKNOWN').Count -gt 0) {
        return [pscustomobject]@{ asked=$false; state='COMPLETION_UNCONFIRMED'; reason='BARRIER_NOT_PROVEN_EMPTY' }
    }
    foreach ($child in @($barrier.children | Where-Object state -eq 'TERMINAL')) {
        if (-not $child.reconciled) {
            $child.reconciled = $true
            $barrier.events.Add('reconcile')
        }
        if (-not $child.consumed) {
            $child.consumed = $true
            $barrier.events.Add('consume')
        }
    }
    $barrier.events.Add('question')
    $barrier.questionPending = $true
    [pscustomobject]@{ asked=$true; state='QUESTION_PENDING'; reason='BARRIER_EMPTY' }
}
function Launch-Dependent($barrier) {
    if ($barrier.questionPending) { return $false }
    $true
}
function Start-With-Known-Prerequisite([bool]$decisionKnownRequired) {
    $events = [Collections.Generic.List[string]]::new()
    if ($decisionKnownRequired) { $events.Add('question') } else { $events.Add('fanout') }
    $events.ToArray()
}

try {
    $kael = Text '.opencode/agents/kael.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    Check 'QB_STATIC_POLICY' ($kael -match 'Do not present a human QUESTION while any child launched for this task is\s+RUNNING' -and
        $kael -match 'First reconcile the existing family and consume each available' -and
        $kael -match '(?s)While a\s+human QUESTION is pending.*?do not launch children' -and
        $kael -match '(?s)ask\s+that bounded question before launching dependent children' -and
        $docs -match 'Kael does not ask a human question while any task child is running')

    $running = New-Barrier @((New-Child 'RUNNING' $false $false))
    $runResult = Advance-Question $running
    Check 'QB_RUNNING_CHILD_DEFERRED' (-not $runResult.asked -and $runResult.state -eq 'DEFERRED' -and $running.events.Count -eq 0)

    $pending = New-Barrier @((New-Child 'TERMINAL' $true $false))
    $pendingResult = Advance-Question $pending
    Check 'QB_PENDING_RESULT_DEFERRED' (-not $pendingResult.asked -and $pendingResult.state -eq 'DEFERRED' -and $pending.events.Count -eq 0)

    $completionPending = New-Barrier @((New-Child 'TERMINAL' $false $true $true))
    $completionResult = Advance-Question $completionPending
    Check 'QB_UNCONSUMED_COMPLETION_DEFERRED' (-not $completionResult.asked -and
        $completionResult.state -eq 'DEFERRED' -and $completionPending.events.Count -eq 0)

    $unconsumed = New-Barrier @((New-Child 'TERMINAL' $false $false))
    $afterConsume = Advance-Question $unconsumed
    Check 'QB_TERMINAL_RESULT_RECONCILED_AND_CONSUMED_FIRST' ($afterConsume.asked -and $unconsumed.events.Count -eq 3 -and
        $unconsumed.events[0] -eq 'reconcile' -and $unconsumed.events[1] -eq 'consume' -and
        $unconsumed.events[2] -eq 'question' -and $unconsumed.children[0].reconciled -and
        $unconsumed.children[0].consumed)

    $empty = New-Barrier @()
    $emptyResult = Advance-Question $empty
    Check 'QB_EMPTY_BARRIER_ALLOWS_QUESTION' ($emptyResult.asked -and $emptyResult.state -eq 'QUESTION_PENDING' -and
        $empty.events.Count -eq 1 -and $empty.events[0] -eq 'question')
    Check 'QB_PENDING_QUESTION_BLOCKS_DEPENDENTS' (-not (Launch-Dependent $empty))

    $prerequisiteOrder = @(Start-With-Known-Prerequisite $true)
    Check 'QB_KNOWN_PREREQUISITE_BEFORE_FANOUT' ($prerequisiteOrder.Count -eq 1 -and
        $prerequisiteOrder[0] -eq 'question')

    $unknown = New-Barrier @((New-Child 'UNKNOWN' $false $false))
    $unknownResult = Advance-Question $unknown
    Check 'QB_UNKNOWN_NOT_EMPTY' ($unknownResult.state -eq 'COMPLETION_UNCONFIRMED' -and
        -not $unknownResult.asked -and $unknown.events.Count -eq 0)

    Write-Output 'RUNTIME_QUESTION_RACE: NOT AUTOMATED (this harness cannot reliably observe bounded live family completion and result consumption)'
    Write-Output 'QUESTION BARRIER QUALIFICATION: PASS (static contracts + deterministic event ordering; runtime race not tested)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'QUESTION BARRIER QUALIFICATION: FAIL'
    exit 1
}
