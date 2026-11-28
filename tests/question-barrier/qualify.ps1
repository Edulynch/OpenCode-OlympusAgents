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
function Start-With-Known-Prerequisites([string[]]$missing, [string[]]$authorized,
                                      [bool]$hardDeny = $false) {
    # Synthetic task decisions, not observed model behavior or native consent.
    $pending = @($missing | Where-Object { $_ -notin $authorized })
    if ($hardDeny) { return [pscustomobject]@{ state='IMPOSSIBLE'; questions=0; writer=$false; items=@() } }
    if ($pending.Count -gt 0) {
        return [pscustomobject]@{ state='NEEDS_UPFRONT_DECISION'; questions=1; writer=$false; items=$pending }
    }
    [pscustomobject]@{ state='READY'; questions=0; writer=$true; items=@() }
}

try {
    $kael = Text '.opencode/agents/kael.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $ultra = Text '.opencode/commands/olympus.ultra.md'
    $performance = Text '.opencode/commands/olympus.performance.md'
    Check 'QB_COMMANDS_PRESERVE_QUESTION_AND_APPROVAL_GATES' (
        $ultra -match 'question' -and $ultra -match 'Do not.*bypass.*gates' -and
        $performance -match 'obtains approval for any concrete unsettled direction before implementation' -and
        $performance -match 'does not select `/olympus\.ultra`' -and
        (Text '.opencode/commands/olympus.performance-ultra.md') -match 'stop for approval of a concrete unsettled direction'
    )
    Check 'QB_STATIC_POLICY' ($kael -match 'Do not present a human QUESTION while any child launched for this task is\s+RUNNING' -and
        $kael -match 'First reconcile the existing family and consume each available' -and
        $kael -match '(?s)While a\s+human QUESTION is pending.*?do not launch children' -and
        $kael -match '(?s)group\s+it with the predictable decisions in Capability Preflight before launching\s+dependent children' -and
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

    $authorized = @('investigate','edit','test','correct','commit','push','update PR')
    $ready = Start-With-Known-Prerequisites $authorized $authorized
    $upfront = Start-With-Known-Prerequisites @('edit project config','choose contract','push','update PR') @('update PR')
    $denied = Start-With-Known-Prerequisites $authorized $authorized $true
    Check 'QB_KNOWN_PREREQUISITES_GROUPED_BEFORE_FANOUT' ($upfront.state -eq 'NEEDS_UPFRONT_DECISION' -and
        $upfront.questions -eq 1 -and -not $upfront.writer -and
        ($upfront.items -join ',') -eq 'edit project config,choose contract,push')
    Check 'QB_READY_REUSES_INITIAL_AUTHORITY_WITHOUT_MERGE_OR_RELEASE' ($ready.state -eq 'READY' -and
        $ready.questions -eq 0 -and $ready.writer -and
        $kael -match 'do not\s+ask again merely because the phase or worker changed' -and
        $kael -match 'Merge and release always require separate explicit\s+authority; never infer them from commit, push, or PR authority')
    Check 'QB_HARD_DENY_BEFORE_WRITER' ($denied.state -eq 'IMPOSSIBLE' -and
        -not $denied.writer -and $denied.questions -eq 0 -and
        $kael -match 'do not launch doomed dependent or writer work, attempt DENY, or switch to `build`')

    # One child blocked; the ready independent child finishes before the
    # grouped question. The dependent child cannot run across the barrier.
    $partial = New-Barrier @((New-Child 'TERMINAL' $false $true), (New-Child 'RUNNING' $true $false))
    $partialResult = Advance-Question $partial
    $partial.children[1].state = 'TERMINAL'
    $partial.children[1].resultPending = $false
    $partial.events.Add('independent-completed')
    $afterIndependent = Advance-Question $partial
    Check 'QB_PARTIAL_BLOCK_CONTINUES_INDEPENDENT_WORK_AND_RECONCILES' (
        $partialResult.state -eq 'DEFERRED' -and $afterIndependent.asked -and
        ($partial.events -join ',') -eq 'independent-completed,reconcile,consume,question' -and
        -not (Launch-Dependent $partial) -and
        $kael -match 'A blocked workstream does not block the entire mission while independent, authorized, useful work exists' -and
        $kael -match 'Do not start work the pending decision would inevitably invalidate')

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
