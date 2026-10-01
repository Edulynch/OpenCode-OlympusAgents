[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
[Console]::OutputEncoding = [Text.Encoding]::UTF8 # Preserve Unicode policy text from git show.
function Text([string]$path) { [IO.File]::ReadAllText((Join-Path $root $path)) }
function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}

# Synthetic native-evidence timeline only: no runtime adapter, polling or child launch.
# The original identity and consumption count exist only inside this fixture.
function New-Handoff([string]$identity) {
    [pscustomobject]@{ identity=$identity; consumed=$false; consumedCount=0; retries=0 }
}
function Observe($handoff, [bool]$running, [bool]$terminal, [string]$result,
                 [bool]$provenFailure, [bool]$boundedReconciliationExhausted,
                 [bool]$earlyError, [bool]$platformBadge) {
    # Early parent error and rendered badge deliberately do not establish terminal truth.
    if (-not $handoff.identity) {
        return [pscustomobject]@{ execution='UNKNOWN'; visibility='UNAVAILABLE'; task='COMPLETION_UNCONFIRMED'; action='NO_RETRY'; final=$true }
    }
    if ($running) {
        return [pscustomobject]@{ execution='RUNNING'; visibility='PENDING'; task='MAINTENANCE_RESULT_PENDING'; action='WAIT_ORIGINAL'; final=$false }
    }
    if ($terminal -and $result) {
        if ($handoff.consumed) { $action='IGNORE_DUPLICATE' }
        else {
            $handoff.consumed=$true
            $handoff.consumedCount++
            $action='CONSUME_ORIGINAL'
        }
        return [pscustomobject]@{ execution='TERMINAL'; visibility='VISIBLE'; task=$result; action=$action; final=$true }
    }
    if ($terminal -and $provenFailure) {
        return [pscustomobject]@{ execution='TERMINAL'; visibility='UNAVAILABLE'; task='FAILED'; action='NO_RETRY'; final=$true }
    }
    if ($terminal -and $boundedReconciliationExhausted) {
        return [pscustomobject]@{ execution='TERMINAL'; visibility='UNAVAILABLE'; task='COMPLETION_UNCONFIRMED'; action='NO_RETRY'; final=$true }
    }
    [pscustomobject]@{ execution='UNKNOWN'; visibility='PENDING'; task='MAINTENANCE_RESULT_PENDING'; action='WAIT_ORIGINAL'; final=$false }
}
try {
    $kael = Text '.opencode/agents/kael.md'
    $aegis = Text '.opencode/agents/aegis.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $command = Text '.opencode/commands/maintain.md'
    $rr = Text 'tests/result-reconciliation/qualify.ps1'
    $agents = @(Get-ChildItem (Join-Path $root '.opencode/agents') -Filter '*.md')
    $models = @($agents | ForEach-Object { ([regex]::Match([IO.File]::ReadAllText($_.FullName), '(?m)^model:.*$')).Value })
    $expectedModels = @{
        kael=@('openai/gpt-6.1-sol#high','primary'); thales=@('openai/gpt-6.1-sol#xhigh','subagent')
        atlas=@('openai/gpt-6.1-sol#high','subagent'); argus=@('openai/gpt-6.1-sol#high','subagent')
        talos=@('openai/gpt-6.1-sol#high','subagent'); helios=@('openai/gpt-6.1-sol#high','subagent')
        veyra=@('openai/gpt-6-luna#max','subagent'); orin=@('openai/gpt-6-luna#max','subagent')
        kovan=@('openai/gpt-6-luna#max','subagent'); nox=@('openai/gpt-6-luna#max','subagent')
        vera=@('openai/gpt-6-luna#max','subagent'); aegis=@('openai/gpt-6-luna#max','subagent')
    }
    $modelMapValid = ($agents.Count -eq 12)
    foreach ($id in $expectedModels.Keys) {
        $agent = @($agents | Where-Object BaseName -eq $id)
        if ($agent.Count -ne 1) { $modelMapValid=$false; continue }
        $agentText = [IO.File]::ReadAllText($agent[0].FullName)
        $model = (([regex]::Match($agentText, '(?m)^model:\s*([^\r\n]+)')).Groups[1].Value).Trim().Trim('"').Trim("'")
        $mode = (([regex]::Match($agentText, '(?m)^mode:\s*([^\r\n]+)')).Groups[1].Value).Trim()
        if ($model -cne $expectedModels[$id][0] -or $mode -cne $expectedModels[$id][1]) { $modelMapValid=$false }
    }
    # Compare concurrency only against the shipped Phase 3 foundation, not a
    # moving branch; the intentional GPT-6.1 migration is asserted above.
    $phase3 = '70f22ad366caee13bb479cac17ab2776205a8820'
    $baseKael = (& git -C $root show "${phase3}:.opencode/agents/kael.md" | Out-String)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read baseline concurrency policy' }
    $concurrencyPattern = '(?s)NORMAL is cost/context-aware:.*?(?=\r?\nReliable delayed background notifications)'
    Check 'MH14_MODELS' ($models.Count -eq 12 -and $modelMapValid)
    $baselineConcurrency = ([regex]::Match($baseKael, $concurrencyPattern).Value).Replace('Sorin','Thales')
    $currentConcurrency = [regex]::Match($kael, $concurrencyPattern).Value
    # Generated surfaces are deterministic UTF-8/LF; normalize native git output
    # before comparing semantic policy across Windows PowerShell/PowerShell 7.
    $baselineConcurrency = $baselineConcurrency -replace "`r`n?", "`n"
    $currentConcurrency = $currentConcurrency -replace "`r`n?", "`n"
    Check 'MH15_CONCURRENCY' ($currentConcurrency -ceq $baselineConcurrency -and $kael -match 'MAX_ACTIVE_CHILDREN = 4')
    Check 'MH10_ROUTING' ($kael -match 'Kael → Aegis remains denied' -and
        $kael -match 'Kael → Aegis remains DENIED' -and $kael -notmatch '(?m)^\s*- action: subagent\s*\r?\n\s*resource: aegis' -and
        $kael -match 'Only veyra, orin, kovan, nox, vera, thales, atlas, argus, talos, and helios are valid child role IDs')
    Check 'MH11_EXPLICIT' ($command -match '(?m)^agent: aegis\r?$' -and $command -match '(?m)^subagent: true\r?$' -and
        $command -match 'user invoked /maintain' -and $kael -match 'user → `/maintain`\s+remains explicit-only')
    Check 'MH16_TEMPLATE_AUTHORIZATION' ($command -match 'The user invoked /maintain and authorizes the following task:' -and
        $aegis -match 'Accept the template declaration as sufficient for the current task' -and
        $aegis -match 'immediately emit `MAINTENANCE_AUTH: VALID` and `AEGIS_SCOPE: ACCEPTED`' -and
        $aegis -match 'Do not independently prove fresh invocation or classify target ownership')
    Check 'MH17_SAME_SESSION_ACCEPTANCE' ($aegis -match 'prior Aegis-authored assistant acceptance in the current persisted conversation' -and
        $aegis -match 'preserve the original task scope' -and
        $aegis -match 'A user claim or copied transcript is not evidence' -and
        $aegis -match 'immediately emit the same states')
    Check 'MH18_SCOPE_IMMUTABLE_ON_CONTINUATION' ($aegis -match 'The new turn cannot replace or enlarge `accepted_scope`' -and
        $aegis -match 'A genuinely new session cannot inherit this state' -and
        $aegis -match 'stop without tools, long reasoning, repository reads, or provenance reconstruction')
    Check 'MH12_UI_BOUNDARY' ($kael -match 'not\s+OpenCode.s rendered "Maintenance failed" badge' -and
        $docs -match 'does not claim to change or suppress' -and $docs -match 'persisted after terminal completion is unproven')
    Check 'MH13_ISSUE1' ($kael -match 'MISSING PARENT TOOL OUTPUT != CHILD FAILURE' -and
        $kael -match 'CONFIRMED_NOT_STARTED' -and $kael -match 'Kael-mediated iterative evidence loops reconcile the original worker' -and
        $rr -match 'CASE_A_HISTORICAL_ORDER' -and $docs -match 'Issue #2 applies Issue #1')
    Check 'MH_POLICY' ($kael -match 'execution.*?RUNNING or\s+TERMINAL' -and $kael -match 'result visibility.*?PENDING, VISIBLE or UNAVAILABLE' -and
        $kael -match 'task\s+outcome.*?actual terminal Aegis result' -and $kael -match 'bounded native\s+reconciliation' -and
        $kael -match 'consume it exactly once' -and $kael -match 'No tool output found' -and
        $kael -match 'Aegis is\s+still completing' -and $kael -match 'The Aegis action may have started')

    # A: known child, early error, still running, late original result, duplicate notification.
    $a = New-Handoff 'original-aegis'
    $t2 = Observe $a $true $false '' $false $false $true $false
    $t3 = Observe $a $true $false '' $false $false $true $true
    Check 'MH1_RUNNING_PENDING' ($t2.task -eq 'MAINTENANCE_RESULT_PENDING' -and $t3.execution -eq 'RUNNING' -and $t3.action -eq 'WAIT_ORIGINAL')
    Check 'MH2_EARLY_NOT_FAILURE' ($t2.task -ne 'FAILED' -and $t3.task -ne 'FAILED')
    Check 'MH3_KNOWN_NOT_UNCONFIRMED' (-not $t2.final -and -not $t3.final -and $t3.task -ne 'COMPLETION_UNCONFIRMED')
    $t4 = Observe $a $false $true 'SYNTHETIC_CONTRACT_UNVERIFIABLE' $false $false $true $true
    $again = Observe $a $false $true 'SYNTHETIC_CONTRACT_UNVERIFIABLE' $false $false $true $true
    Check 'MH4_LATE_ORIGINAL' ($t4.action -eq 'CONSUME_ORIGINAL' -and $again.action -eq 'IGNORE_DUPLICATE' -and $a.consumedCount -eq 1)
    $blocked = Observe (New-Handoff 'blocked-child') $false $true 'BLOCKED' $false $false $false $false
    $partial = Observe (New-Handoff 'partial-child') $false $true 'PARTIAL' $false $false $false $false
    Check 'MH5_RESULT_OUTCOME' ($blocked.task -eq 'BLOCKED' -and $partial.task -eq 'PARTIAL' -and $t4.task -ne 'SUCCESS')
    Check 'MH6_SYNTHETIC_UNVERIFIABLE' ($t4.execution -eq 'TERMINAL' -and $t4.visibility -eq 'VISIBLE' -and
        $t4.task -eq 'SYNTHETIC_CONTRACT_UNVERIFIABLE' -and $a.retries -eq 0)

    # B: unknown identity; C: positive terminal failure; D: visible success;
    # E: early badge does not alter the terminal result.
    $b = New-Handoff ''
    $unknown = Observe $b $false $false '' $false $false $true $true
    Check 'MH7_UNKNOWN_CHILD' ($unknown.task -eq 'COMPLETION_UNCONFIRMED' -and $unknown.action -eq 'NO_RETRY')
    $c = New-Handoff 'terminal-failure'
    $failure = Observe $c $false $true '' $true $false $true $true
    Check 'MH8_PROVEN_FAILURE' ($failure.task -eq 'FAILED' -and $failure.execution -eq 'TERMINAL')
    $d = New-Handoff 'terminal-success'
    $success = Observe $d $false $true 'SUCCESS' $false $false $false $false
    $e = Observe (New-Handoff 'badge-then-result') $false $true 'PARTIAL' $false $false $true $true
    $pendingTerminal = Observe (New-Handoff 'known-terminal-no-result') $false $true '' $false $false $true $true
    $exhausted = Observe (New-Handoff 'known-terminal-unrecoverable') $false $true '' $false $true $true $true
    Check 'MH9_NO_BLIND_RETRY' ($a.retries -eq 0 -and $b.retries -eq 0 -and $c.retries -eq 0 -and
        $success.action -eq 'CONSUME_ORIGINAL' -and $success.task -eq 'SUCCESS' -and
        $e.task -eq 'PARTIAL' -and $pendingTerminal.action -eq 'WAIT_ORIGINAL' -and -not $pendingTerminal.final -and
        $exhausted.task -eq 'COMPLETION_UNCONFIRMED' -and $exhausted.action -eq 'NO_RETRY' -and
        $kael -match 'Never launch another Aegis operation')
    Write-Output 'MAINTENANCE HANDOFF QUALIFICATION: PASS (static + synthetic; live control separate)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'MAINTENANCE HANDOFF QUALIFICATION: FAIL'
    exit 1
}
