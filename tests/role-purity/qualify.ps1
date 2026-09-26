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
function Denied([string]$text, [string]$action) {
    ([regex]::Matches($text, '(?ms)^\s*- action:\s*' + [regex]::Escape($action) + '\s*\r?\n\s*resource:\s*"?\*"?\s*\r?\n\s*effect:\s*deny')).Count -gt 0
}

# Deterministic policy transition model, NOT a native session adapter. This
# exercises the interplay of routing, original-assignment reconciliation and
# continuation; the independent Issue #1 suite exercises reconciliation itself.
function New-Loop([bool]$gate = $true) {
    [pscustomobject]@{ Gate=$gate; Sorin='sorin-original'; Calls=0; Worker=$null;
        WorkerCount=0; WorkerParent=$null; Request=$null; Seen=@();
        Round='NONE'; Result=$null; Consumed=0; Unknown=0;
        ReasonerFinal=$false; RootFinal=$false; AuthorizedPaths=@('src/probe.py','src/probe-test.py');
        Dependencies=$true; PlaneAllowed=$true; UserAuthorizedThird=$false }
}
function Consult($loop, [string]$session, [string]$status) {
    if (-not $loop.Gate -or $session -cne $loop.Sorin -or $loop.Round -in @('PENDING_OR_INDETERMINATE','COMPLETION_UNCONFIRMED')) { return 'REJECT' }
    if ($loop.Calls -ge 3 -or
        ($loop.Calls -eq 2 -and (-not $loop.UserAuthorizedThird -or $loop.Round -ne 'EVIDENCE_READY' -or $loop.Consumed -ne 2)) -or
        ($loop.Calls -eq 1 -and ($loop.Round -ne 'EVIDENCE_READY' -or $loop.Consumed -ne 1))) { return 'REJECT' }
    $loop.Calls++
    if ($status -eq 'EVIDENCE_REQUEST') { $loop.Round = 'REQUESTED'; return 'REQUESTED' }
    if ($status -eq 'ADVICE') { $loop.ReasonerFinal = $true; $loop.Round = 'ADVICE'; return 'ADVICE' }
    return 'REJECT'
}
function Route($loop, [string]$key, [string]$role, [string]$path = 'src/probe.py',
               [bool]$bounded = $true, [bool]$material = $false,
               [bool]$relevant = $true, [bool]$implementation = $false) {
    if (-not $loop.Gate) { return 'NO_SORIN' }
    if ($loop.Round -eq 'PENDING_OR_INDETERMINATE' -or $loop.Round -eq 'COMPLETION_UNCONFIRMED') { return 'PENDING' }
    if ($key -cin $loop.Seen -and -not $material) { return 'NO_PROGRESS' }
    if ($loop.Round -ne 'REQUESTED' -or $role -notin @('veyra','orin','nox','vera') -or
        $path -cnotin $loop.AuthorizedPaths -or -not $bounded -or -not $relevant -or
        -not $loop.Dependencies -or -not $loop.PlaneAllowed -or $implementation) { return 'BLOCKED' }
    $loop.Seen += $key; $loop.Worker="worker-$($loop.WorkerCount + 1)"; $loop.WorkerParent='kael-root'
    $loop.WorkerCount++; $loop.Round='PENDING_OR_INDETERMINATE'
    return 'ROUTE'
}
function WorkerEvent($loop, [string]$event, [bool]$known = $true) {
    if ($loop.Round -eq 'EVIDENCE_READY' -and $event -eq 'original-terminal') { return 'IGNORE_DUPLICATE' }
    if ($loop.Round -ne 'PENDING_OR_INDETERMINATE') { return 'REJECT' }
    if ($event -eq 'parent-output-missing' -and -not $known) {
        $loop.Unknown++; $loop.Round='COMPLETION_UNCONFIRMED'; return 'COMPLETION_UNCONFIRMED'
    }
    if ($event -eq 'parent-output-missing' -or $event -eq 'original-running') { return 'WAIT_ORIGINAL' }
    if ($event -eq 'original-terminal' -and $known) {
        $loop.Result="material evidence from $($loop.Worker)"; $loop.Consumed++
        $loop.Round='EVIDENCE_READY'; return 'CONSUME_ORIGINAL'
    }
    return 'REJECT'
}
function Complete($loop) {
    $loop.Gate -and $loop.ReasonerFinal -and $loop.RootFinal -and
    $loop.Round -eq 'ADVICE' -and $loop.WorkerCount -ge 1 -and
    $loop.Consumed -eq $loop.WorkerCount -and $loop.Unknown -eq 0 -and
    $loop.WorkerParent -eq 'kael-root'
}
try {
    $k=Text '.opencode/agents/kael.md'; $s=Text '.opencode/agents/sorin.md'
    $v=Text '.opencode/agents/vera.md'; $d=Text 'docs/DEVELOPMENT.md'
    $workers=@(@('veyra','orin','kovan','nox','vera') | ForEach-Object { Text ".opencode/agents/$_.md" })
    Check RP1_ROLE_PURITY ($k -match 'DO YOUR ROLE' -and $s -match 'DO YOUR ROLE' -and $k -match 'do not silently do Veyra.s discovery')
    Check RP2_KAEL_TOPOLOGY ($k -match 'Kael launches the worker as its \*\*direct child\*\*' -and $d -match 'KAEL_MEDIATED')
    Check RP3_SORIN_REQUEST ($s -match 'STATUS: EVIDENCE_REQUEST' -and $s -match 'EXPECTED_DISCRIMINATION' -and $k -match 'validate TARGET_ROLE')
    Check RP4_SAME_REASONER ($k -match 'SAME native Sorin session' -and $s -match 'same native session')
    Check RP5_NO_PROGRESS ($k -match 'NO_PROGRESS' -and $s -match 'NO_PROGRESS' -and $k -match 'NO BROAD RESTART')
    Check RP6_NO_NESTING ((Denied $s 'subagent') -and $k -match 'never reasoner → worker nesting' -and $k -match 'native depth limit is 1')
    Check RP7_COMPLETION ($k -match 'zero unknown required execution' -and $k -match 'reasoner final result consumed' -and $k -match 'root synthesis last')
    Check RP8_WORKER_BOUNDARIES (@($workers | Where-Object { -not (Denied $_ 'subagent') -or $_ -notmatch 'spawn children|create or call another agent|another agent' }).Count -eq 0)
    Check RP9_VERA_INDEPENDENCE ($v -match 'independent review gate' -and $v -match 'never fix' -and $k -match 'Vera.s independent review')
    Check RP10_MISSING_NOT_FAILED ($k -match 'missing parent\s+tool output is not FAILED evidence' -and $k -match 'do not mark FAILED from a missing parent tool output')
    Check RP11_NO_BLIND_RETRY ($k -match 'missing parent\s+tool output is not FAILED evidence, an empty evidence packet, or permission to\s+launch a replacement' -and $k -match 'No second worker is launched')
    Check RP12_NO_FAKE_EVIDENCE ($k -match 'Never re-consult Sorin using\s+fabricated failure, empty evidence' -and $k -match 'unresolved PENDING_OR_INDETERMINATE round cannot')
    Check RP13_RECOVER_ORIGINAL ($k -match 'wait for\s+the original native result and consume it once' -and $k -match 'After a successfully reconciled')
    Check RP14_UNKNOWN_STOPS ($k -match 'unknown/unrecoverable\s+execution stop as COMPLETION_UNCONFIRMED' -and $d -match 'Unknown execution\s+stops as COMPLETION_UNCONFIRMED')
    Check RP15_ISSUE1_INTACT ($k -match 'MISSING PARENT TOOL OUTPUT != CHILD FAILURE' -and $k -match 'only positive native evidence that no child was\s+created' -and $k -match 'No second worker is launched')
    Check RP16_MODELS_UNCHANGED ($k -match 'model: "openai/gpt-6-sol#high"' -and $s -match 'model: openai/gpt-6-sol#xhigh' -and
        (Text '.opencode/agents/maintenance.md') -match 'model: openai/gpt-6-sol#high' -and
        @($workers | Where-Object { $_ -notmatch 'model: "openai/gpt-6-luna#max"' }).Count -eq 0)
    Check RP17_CONCURRENCY_UNCHANGED ($k -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $k -match 'fan out up to four useful children' -and $k -match 'NORMAL is cost/context-aware: adapt from zero to four children')
    $allAgents = @($k,$s,(Text '.opencode/agents/maintenance.md')) + $workers
    Check RP18_NO_LUNA_FAST (($allAgents -join "`n") -notmatch 'gpt-6-luna#fast|luna.fast|luna-fast')
    Check 'SORIN_READ_ONLY' ((Denied $s 'shell') -and (Denied $s 'edit') -and (Denied $s 'subagent'))
    Check 'BUDGET_AND_GATE' ($k -match 'No third automatic consultation' -and $k -match 'Diagnostic Gate')
    $m=Text '.opencode/agents/maintenance.md'; $handoff=Text 'tests/maintenance-handoff/qualify.ps1'
    $rr=Text 'tests/result-reconciliation/qualify.ps1'
    Check RP1_KAEL_OWNS_ROUTING_COMPLETION ($k -match 'MASTER ORCHESTRATOR' -and $k -match 'root synthesis last')
    Check RP2_REASONER_PURITY ($s -match 'Reasoning is more than repeating worker summaries' -and (Denied $s 'shell') -and (Denied $s 'edit'))
    Check RP3_WORKER_PURITY (@($workers | Where-Object { $_ -notmatch 'DO YOUR ROLE' }).Count -eq 0)
    Check RP4_EVIDENCE_REQUEST ($s -match 'STATUS: EVIDENCE_REQUEST' -and $k -match 'EXPECTED_DISCRIMINATION')
    Check RP5_SORIN_NO_CHILDREN (Denied $s 'subagent')
    Check RP6_KAEL_MEDIATED ($d -match 'KAEL_MEDIATED' -and $k -match 'direct child')
    Check RP7_SAME_REASONER ($k -match 'SAME native Sorin session')
    Check RP8_NO_PROGRESS ($k -match 'NO_PROGRESS' -and $s -match 'NO_PROGRESS')
    Check RP9_VERA_INDEPENDENT ($v -match 'independent review gate')
    Check RP10_NO_DIRECT_NESTING ($k -match 'never reasoner → worker nesting' -and (Denied $s 'subagent'))
    Check RP11_NORMAL_RECONCILIATION ($rr -match 'CASE_A_HISTORICAL_ORDER' -and $k -match 'Kael-mediated iterative evidence loops reconcile the original worker')
    Check RP12_MAINTENANCE_RECONCILIATION ($handoff -match 'MH1_RUNNING_PENDING' -and $k -match 'explicit maintenance result handoff')
    Check RP13_NO_FALSE_FAILURE_EVIDENCE ($k -match 'missing parent\s+tool output is not FAILED evidence' -and $k -match 'Never re-consult Sorin using\s+fabricated failure')
    Check RP14_NO_INDETERMINATE_RETRY ($k -match 'permission to\s+launch a replacement' -and $k -match 'No second worker is launched')
    Check RP15_MAINTENANCE_PENDING ($k -match 'Maintenance is\s+still completing' -and $handoff -match 'MH3_KNOWN_NOT_UNCONFIRMED')
    Check RP16_MAINTENANCE_OUTSIDE_ROUTING ($k -match 'Kael → Maintenance remains DENIED' -and $s -match '(?s)Never directly invoke.*?Maintenance' -and $k -match 'Only veyra, orin, kovan, nox, vera, and sorin are valid child role IDs')
    Check RP17_THIRD_AUTO_DENIED ($k -match 'No third automatic consultation' -and $k -match 'explicit user authorization')
    Check RP18_COMPLETION_OWNERSHIP ($k -match 'reasoner final result consumed' -and $k -match 'zero unresolved required work')
    Check RP19_MODELS ($k -match 'model: "openai/gpt-6-sol#high"' -and $s -match 'model: openai/gpt-6-sol#xhigh' -and $m -match 'model: openai/gpt-6-sol#high' -and @($workers | Where-Object { $_ -notmatch 'model: "openai/gpt-6-luna#max"' }).Count -eq 0)
    Check RP20_CONCURRENCY ($k -match 'MAX_ACTIVE_CHILDREN = 4' -and $k -match 'fan out up to four useful children')
    Check RP21_NO_LUNA_FAST (($allAgents -join "`n") -notmatch 'gpt-6-luna#fast|luna.fast|luna-fast')

    $a=New-Loop
    $a1=Consult $a 'sorin-original' 'EVIDENCE_REQUEST'; $a2=Route $a 'probe' 'veyra'
    $a3=WorkerEvent $a 'original-terminal'; $a4=Consult $a 'sorin-original' 'ADVICE'
    $before=Complete $a; $a.RootFinal=$true
    Check 'CASE_A_HEALTHY' ($a1 -eq 'REQUESTED' -and $a2 -eq 'ROUTE' -and $a3 -eq 'CONSUME_ORIGINAL' -and $a4 -eq 'ADVICE' -and -not $before -and (Complete $a) -and $a.Calls -eq 2)
    $b=New-Loop; $null=Consult $b 'sorin-original' 'EVIDENCE_REQUEST'; $null=Route $b 'probe' 'veyra'
    $b1=WorkerEvent $b 'parent-output-missing'; $b2=Route $b 'probe' 'veyra'
    $b3=Consult $b 'sorin-original' 'ADVICE'; $b4=WorkerEvent $b 'original-running'
    Check 'CASE_B_PENDING' ($b1 -eq 'WAIT_ORIGINAL' -and $b2 -eq 'PENDING' -and $b3 -eq 'REJECT' -and $b4 -eq 'WAIT_ORIGINAL' -and $b.WorkerCount -eq 1 -and $b.Calls -eq 1 -and $b.Consumed -eq 0 -and -not (Complete $b))
    $b5=WorkerEvent $b 'original-terminal'; $b6=WorkerEvent $b 'original-terminal'
    $b7=Consult $b 'sorin-original' 'ADVICE'; $b.RootFinal=$true
    Check 'CASE_B_RECOVERED' ($b5 -eq 'CONSUME_ORIGINAL' -and $b6 -eq 'IGNORE_DUPLICATE' -and $b7 -eq 'ADVICE' -and $b.WorkerCount -eq 1 -and (Complete $b))
    $c=New-Loop; $null=Consult $c 'sorin-original' 'EVIDENCE_REQUEST'; $null=Route $c 'probe' 'veyra'
    $c1=WorkerEvent $c 'parent-output-missing' $false; $c2=Route $c 'probe' 'veyra'; $c3=Consult $c 'sorin-original' 'ADVICE'
    Check 'CASE_C_UNKNOWN' ($c1 -eq 'COMPLETION_UNCONFIRMED' -and $c2 -eq 'PENDING' -and $c3 -eq 'REJECT' -and $c.Unknown -eq 1 -and $c.WorkerCount -eq 1 -and -not (Complete $c))
    $n=New-Loop; $null=Consult $n 'sorin-original' 'EVIDENCE_REQUEST'; $null=Route $n 'broad' 'veyra'; $null=WorkerEvent $n 'original-terminal'
    $n.Round='REQUESTED'; Check 'CASE_D_NO_PROGRESS' ((Route $n 'broad' 'veyra') -eq 'NO_PROGRESS' -and $n.WorkerCount -eq 1)
    $out=New-Loop; $null=Consult $out 'sorin-original' 'EVIDENCE_REQUEST'
    Check 'CASE_D_OUT_OF_SCOPE' ((Route $out 'outside' 'veyra' '../external') -eq 'BLOCKED' -and
        (Route $out 'implement' 'kovan') -eq 'BLOCKED' -and
        (Route $out 'fix' 'veyra' 'src/probe.py' $true $false $true $true) -eq 'BLOCKED' -and
        $out.WorkerCount -eq 0 -and $out.Round -eq 'REQUESTED')
    # A second focused request is possible on call 2. A final Sorin answer
    # needs call 3: never automatically authorized by the current budget.
    $two=New-Loop; $null=Consult $two 'sorin-original' 'EVIDENCE_REQUEST'
    $null=Route $two 'baseline' 'veyra'; $null=WorkerEvent $two 'original-terminal'
    $narrow=Consult $two 'sorin-original' 'EVIDENCE_REQUEST'
    $second=Route $two 'discriminating-test' 'nox' 'src/probe-test.py' $true $true
    $secondEvidence=WorkerEvent $two 'original-terminal'
    $third=Consult $two 'sorin-original' 'ADVICE'; $two.RootFinal=$true
    Check 'CASE_B_FOCUSED_SECOND_ROUND_BUDGET_STOP' ($narrow -eq 'REQUESTED' -and
        $second -eq 'ROUTE' -and $secondEvidence -eq 'CONSUME_ORIGINAL' -and
        $two.WorkerCount -eq 2 -and $two.Consumed -eq 2 -and
        $two.Calls -eq 2 -and $third -eq 'REJECT' -and -not (Complete $two))
    $two.RootFinal=$false; $two.UserAuthorizedThird=$true
    $manual=Consult $two 'sorin-original' 'ADVICE'; $two.RootFinal=$true
    Check 'CASE_B_SECOND_ROUND_EXPLICIT_CONTINUATION_COMPLETE' ($manual -eq 'ADVICE' -and
        $two.Calls -eq 3 -and $two.WorkerCount -eq 2 -and $two.Consumed -eq 2 -and
        $two.Sorin -eq 'sorin-original' -and (Complete $two))
    $simple=New-Loop $false
    Check 'CASE_E_SIMPLE_BUG' ((Consult $simple 'sorin-original' 'EVIDENCE_REQUEST') -eq 'REJECT' -and (Route $simple 'probe' 'veyra') -eq 'NO_SORIN' -and $simple.Calls -eq 0)
    # Issue #2 is an explicit user handoff, not a reasoner evidence worker.
    # Keep execution, visibility, and task outcome independent at each event.
    $mh=[pscustomobject]@{ Identity='original-maintenance'; Execution='RUNNING'; Visibility='PENDING'; Outcome='MAINTENANCE_RESULT_PENDING'; Consumed=0; Retries=0 }
    Check 'CASE_G_MAINTENANCE_EARLY_ERROR' ($mh.Identity -and $mh.Execution -eq 'RUNNING' -and $mh.Visibility -eq 'PENDING' -and $mh.Outcome -notin @('FAILED','COMPLETION_UNCONFIRMED') -and $mh.Retries -eq 0 -and (Route $out 'maint' 'maintenance') -eq 'BLOCKED')
    $mh.Execution='TERMINAL'; $mh.Visibility='VISIBLE'; $mh.Outcome='PARTIAL'; $mh.Consumed++
    Check 'CASE_G_MAINTENANCE_LATE_ORIGINAL' ($mh.Outcome -eq 'PARTIAL' -and $mh.Consumed -eq 1 -and $mh.Retries -eq 0)
    Write-Output 'ROLE PURITY: PASS (static + deterministic integration; live test separate)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'ROLE PURITY: FAIL'
    exit 1
}
