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

# A deterministic interpretation of native evidence, not a runtime adapter.
# The assignment keeps only in-memory identity for the lifetime of this fixture.
function New-Assignment([string]$id, [bool]$writer) {
    [pscustomobject]@{ id=$id; writer=$writer; consumed=$false; consumedCount=0; retries=0 }
}
function Reconcile($assignment, [string]$event, [bool]$childKnown, [bool]$terminal,
                   [bool]$resultAvailable, [bool]$notStarted, [string]$outcome) {
    if ($notStarted) {
        # Only native positive pre-launch evidence may reach this branch.
        return [pscustomobject]@{ state='CONFIRMED_NOT_STARTED'; retryEligible=$true; action='RETRY_ELIGIBLE' }
    }
    if ($childKnown -and $terminal -and $resultAvailable) {
        if (-not $assignment.consumed) {
            $assignment.consumed = $true
            $assignment.consumedCount++
            $action = if ($outcome -eq 'succeeded') { 'CONSUME_ORIGINAL' } else { 'CONFIRMED_FAILURE' }
        } else { $action = 'IGNORE_DUPLICATE' }
        return [pscustomobject]@{ state='CONFIRMED_RESULT'; retryEligible=$false; action=$action }
    }
    if ($childKnown) {
        return [pscustomobject]@{ state='PENDING_OR_RUNNING'; retryEligible=$false; action='WAIT_ORIGINAL' }
    }
    [pscustomobject]@{ state='COMPLETION_UNCONFIRMED'; retryEligible=$false; action='NO_RETRY' }
}
try {
    $kael = Text '.opencode/agents/kael.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $gates = Text 'tests/completion-gates/qualify.ps1'
    Check 'RR1_MISSING_NOT_FAILURE' ($kael -match 'MISSING PARENT TOOL OUTPUT != CHILD FAILURE' -and
        $kael -match 'No tool output found for function call' -and $kael -match 'do not mark FAILED from a missing parent tool output')
    Check 'RR2_MISSING_NOT_NONEXECUTION' ($kael -match 'not proof that the\s+delegation failed, never started' -and
        $kael -match 'an absent output alone never does')
    Check 'RR3_NO_UNKNOWN_RETRY' ($kael -match 'Do not launch\s+an equivalent replacement' -and
        $kael -match 'indeterminate original execution is never permission')
    Check 'RR4_KNOWN_CHILD_OWNED' ($kael -match 'retain its ownership' -and $kael -match 'wait for its original native completion/result')
    Check 'RR5_LATE_RESULT' ($kael -match 'When it arrives, collect and validate that result')
    Check 'RR6_UNKNOWN_CHILD' ($kael -match 'COMPLETION_UNCONFIRMED' -and $kael -match 'cannot be identified or\s+recovered')
    Check 'RR7_NONEXECUTION_GATE' ($kael -match 'only positive native evidence that no child was\s+created' -and
        $kael -match 'Eligibility is\s+not an automatic retry')
    Check 'RR8_WRITER' ($kael -match 'side-effecting work' -and $kael -match 'Kovan edits' -and $kael -match 'Git/release')
    Check 'RR9_READ_ONLY' ($kael -match 'Even read-only duplicate investigation needs\s+confirmed non-execution or a deliberate later orchestration decision')
    Check 'RR10_ONCE' ($kael -match 'Consume\s+it once for its existing assignment/session identity' -and
        $kael -match 'delivered again, account for it without processing it as new work')
    Check 'RR11_EXISTING_GATES' ($kael -match 'A root response, CLI return,\s+or idle state alone does not establish family completion' -and
        $kael -match 'family membership, terminal results collected and validated, parent consumption' -and
        $kael -match 'empty required native inbox' -and $gates -match 'NESTED_FAMILY_AND_INBOX')
    Check 'RR12_NO_RUNTIME' ($kael -match 'Do not grant Kael shell/API access' -and
        $kael -match 'Do not.*polling' -and $kael -match 'Do not emulate another runtime or add a scheduler' -and
        $docs -match 'No poller, resolver or persistent dedupe state')
    $agents = Get-ChildItem (Join-Path $root '.opencode/agents') -Filter '*.md'
    $allAgentText = ($agents | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"
    $modelLines = @($agents | ForEach-Object { ([regex]::Match([IO.File]::ReadAllText($_.FullName), '(?m)^model:.*$')).Value })
    Check 'RR13_MODELS' ($modelLines.Count -eq 8 -and
        $kael -match 'model: "openai/gpt-6-sol#high"' -and
        (Text '.opencode/agents/thales.md') -match 'model: openai/gpt-6-sol#xhigh' -and
        (Text '.opencode/agents/maintenance.md') -match 'model: openai/gpt-6-sol#high' -and
        @(@('veyra','orin','kovan','nox','vera') | ForEach-Object { (Text ".opencode/agents/$_.md") -match 'model: "?openai/gpt-6-luna#max' }) -notcontains $false)
    Check 'RR14_CONCURRENCY' ($kael -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $kael -match 'FAST is an explicit user-selected latency-priority profile' -and
        $kael -match 'FAST never overrides writer ownership')
    Check 'RR15_NO_LUNA_FAST' ($allAgentText -notmatch 'gpt-6-luna#fast|luna.fast|luna-fast')
    Check 'NO_THALES_ON_ERROR' ($kael -match 'not by itself a reason to invoke Thales')
    Check 'PHASE3_INHERITS' ($kael -match 'Kael-mediated iterative evidence loops reconcile the original worker')

    # Historical Issue #1 event ORDERING only; no private trace/session data is embedded.
    # The underlying historical traces are not required or claimed as reproduced.
    $a = New-Assignment 'original-nox' $false
    $t1 = Reconcile $a 'parent-output-missing' $true $false $false $false ''
    $t2 = Reconcile $a 'child-still-running' $true $false $false $false ''
    $t3 = Reconcile $a 'original-terminal-result' $true $true $true $false 'succeeded'
    Check 'CASE_A_HISTORICAL_ORDER' ($t1.state -eq 'PENDING_OR_RUNNING' -and
        $t2.action -eq 'WAIT_ORIGINAL' -and -not $t1.retryEligible -and
        $t3.state -eq 'CONFIRMED_RESULT' -and $t3.action -eq 'CONSUME_ORIGINAL' -and
        $a.retries -eq 0 -and $a.consumedCount -eq 1)
    $b = New-Assignment 'unknown-child' $false
    $unknown = Reconcile $b 'parent-output-missing' $false $false $false $false ''
    Check 'CASE_B_UNKNOWN' ($unknown.state -eq 'COMPLETION_UNCONFIRMED' -and
        -not $unknown.retryEligible -and $b.retries -eq 0)
    $c = New-Assignment 'prelaunch-rejected' $false
    $rejected = Reconcile $c 'native-prelaunch-rejection' $false $false $false $true ''
    Check 'CASE_C_NOT_STARTED' ($rejected.state -eq 'CONFIRMED_NOT_STARTED' -and
        $rejected.retryEligible -and $rejected.action -eq 'RETRY_ELIGIBLE' -and $c.retries -eq 0)
    $d = New-Assignment 'writer-indeterminate' $true
    $writer = Reconcile $d 'parent-output-missing' $true $false $false $false ''
    Check 'CASE_D_WRITER' ($writer.action -eq 'WAIT_ORIGINAL' -and -not $writer.retryEligible -and $d.retries -eq 0)
    $again = Reconcile $a 'duplicate-original-result' $true $true $true $false 'succeeded'
    Check 'CASE_E_DUPLICATE' ($again.action -eq 'IGNORE_DUPLICATE' -and $a.consumedCount -eq 1)
    $f = New-Assignment 'failed-nox' $false
    $failure = Reconcile $f 'original-terminal-failure' $true $true $true $false 'failed'
    Check 'CASE_F_TERMINAL_FAILURE' ($failure.state -eq 'CONFIRMED_RESULT' -and
        $failure.action -eq 'CONFIRMED_FAILURE' -and $f.consumedCount -eq 1)
    Write-Output 'RESULT RECONCILIATION QUALIFICATION: PASS (static + synthetic; live control separate)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'RESULT RECONCILIATION QUALIFICATION: FAIL'
    exit 1
}
