[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
function Text([string]$name) { [IO.File]::ReadAllText((Join-Path $root $name)) }
function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}

# Model the gate on observed native fields, not on CLI exit or root idle alone.
# The live session API must supply these fields; this fixture is not an interactive test.
function Gate($units) {
    $passes = 0
    $failures = 0
    $unknown = 0
    foreach ($unit in $units) {
        if (-not $unit.known -or -not $unit.terminal -or -not $unit.collected -or
            -not $unit.familyKnown -or -not $unit.inboxEmpty -or -not $unit.parentConsumed) {
            $unknown++
        } elseif ($unit.outcome -eq 'succeeded' -and $unit.validated) {
            $passes++
        } else {
            $failures++
        }
    }
    $state = if ($unknown -or $failures) { 'PARTIAL' } else { 'FINISHED' }
    [pscustomobject]@{ state=$state; passes=$passes; failures=$failures; unknown=$unknown }
}
function Child-ReportGate([string]$childState, [string]$reportState, [bool]$parentInterrupted,
                          [bool]$consumed, [bool]$validated, [string]$outcome) {
    $terminal = $childState -in @('completed', 'failed', 'cancelled')
    $reconciled = $terminal -and $reportState -eq 'final' -and $consumed
    [pscustomobject]@{
        writerOwned = -not $reconciled
        done = $reconciled -and $outcome -eq 'succeeded' -and $validated
        parentInterrupted = $parentInterrupted
        childCancelled = $childState -eq 'cancelled'
    }
}
try {
    $kael = Text '.opencode/agents/kael.md'
    $maintenancePolicy = Text 'olympus/policies/maintenance-context.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    Check 'KAEL_JOIN' ($kael -match 'enumerate the required direct child' -and $kael -match 'consume each result' -and
        $kael -match 'Never declare final completion while a required direct child is non-terminal' -and
        $kael -match 'IN PROGRESS / waiting')
    Check 'API_SEMANTICS' ($docs -match 'MESSAGE_COMPLETE, ROOT_IDLE and FAMILY_COMPLETE' -and
        $docs -match 'No native family-wide wait|no documented family-wide wait' -and $docs -match 'session/active' -and
        $docs -match 'CLI `opencode run` exit or a root assistant response is not a session-family completion signal')
    Check 'CONTEXTUAL_MAINTENANCE' ($maintenancePolicy -match 'Kael is the only root orchestrator' -and
        $maintenancePolicy -match 'There is no separate maintenance role, command' -and
        $maintenancePolicy -match 'canonical Olympus Core files' -and
        $maintenancePolicy -match 'independent project-identity evidence identifies OlympusAgents' -and
        $maintenancePolicy -match 'A directory name, a request mentioning Olympus, or an isolated matching file is not sufficient evidence' -and
        $maintenancePolicy -match 'If identity or target is unclear, do not perform dependent writes' -and
        $maintenancePolicy -match 'different user project' -and
        $maintenancePolicy -match 'do not reach into a separate OlympusAgents checkout' -and
        $maintenancePolicy -match 'manifest-owned files' -and
        $kael -match '## Identify the target repository' -and
        $kael -match '## Preserve the external-project boundary' -and
        $kael -match 'independent project-identity evidence identifies OlympusAgents' -and
        $kael -match 'do not perform dependent writes' -and
        $kael -match 'manifest-owned files')
    $good = [pscustomobject]@{known=$true; terminal=$true; collected=$true; familyKnown=$true; inboxEmpty=$true; parentConsumed=$true; outcome='succeeded'; validated=$true}
    $bad = [pscustomobject]@{known=$true; terminal=$true; collected=$true; familyKnown=$true; inboxEmpty=$true; parentConsumed=$true; outcome='failed'; validated=$false}
    $missing = [pscustomobject]@{known=$false; terminal=$false; collected=$false; familyKnown=$false; inboxEmpty=$false; parentConsumed=$false; outcome=''; validated=$false}
    $all = Gate @($good,$good)
    $mixed = Gate @($good,$bad,$missing)
    $early = Gate @($good,$missing)
    # Root process exit, root assistant response and idle alone are not fields in Gate.
    $rootExitedWithChildRunning = Gate @($good,($missing | Select-Object *))
    $uncollected = $good | Select-Object *; $uncollected.collected = $false
    $notConsumed = $good | Select-Object *; $notConsumed.parentConsumed = $false
    $nestedUnconfirmed = $good | Select-Object *; $nestedUnconfirmed.familyKnown = $false
    $queued = $good | Select-Object *; $queued.inboxEmpty = $false
    Check 'FAMILY_GATE_FIXTURE' ($all.state -eq 'FINISHED' -and $all.passes -eq 2 -and $early.state -eq 'PARTIAL')
    Check 'MIXED_AND_UNKNOWN_FIXTURE' ($mixed.state -eq 'PARTIAL' -and $mixed.passes -eq 1 -and $mixed.failures -eq 1 -and $mixed.unknown -eq 1)
    Check 'ROOT_EXIT_AND_RESPONSE_NOT_FAMILY' ($rootExitedWithChildRunning.state -eq 'PARTIAL' -and
        (Gate @($good,$uncollected)).state -eq 'PARTIAL' -and (Gate @($good,$notConsumed)).state -eq 'PARTIAL')
    Check 'NESTED_FAMILY_AND_INBOX' ((Gate @($good,$nestedUnconfirmed)).state -eq 'PARTIAL' -and
        (Gate @($good,$queued)).state -eq 'PARTIAL')
    # The gate owns completion obligations; TFR must not turn normal changes into
    # unconditional Nox/Vera fan-out. Keep critical and mandatory gates intact.
    $gate = [regex]::Match($kael, '(?ms)^## Completion gate\r?\n(?<body>.*?)(?=^## |\z)').Groups['body'].Value
    $core = Text 'olympus/policies/routing.md'
    $codexRoot = Text 'CODEX.md'
    $kaelSource = Text 'olympus/harnesses/opencode/agent-prompts/kael.md'
    Check 'TFR_NORMAL_GATE_CONDITIONAL' (
        $gate -match 'NORMAL CHANGE: one scoped implementer' -and
        $gate -match 'use Nox only when' -and $gate -match 'use Vera only when' -and
        $gate -match 'fast-path exclusion alone does\s+not require a separate tester or reviewer' -and
        $gate -notmatch 'NORMAL CHANGE:\s*implementer,\s*tester,\s*reviewer' -and
        $core -match 'Assign Nox only for distinct needed test/runtime validation' -and
        $kaelSource -match 'use Nox only when')
    Check 'TFR_MANDATORY_GATES_PRESERVED' (
        $gate -match 'CRITICAL CHANGE: researcher, architect, implementer, tester/reviewer' -and
        $gate -match 'mandatory project, CI,\s+runtime, migration, release, or critical-change gates remain required' -and
        $gate -match 'explicit user-requested independent review' -and
        $gate -match 'REQUIRED VALIDATION PASSED' -and
        $gate -match 'NO UNRESOLVED BLOCKING OR MATERIAL REVIEW FINDINGS')
    Check 'TFR_CODEX_NORMAL_GATE_PARITY' (
        $codexRoot -match 'For NORMAL CHANGE outside the fast path, use TFR' -and
        $codexRoot -match 'do not invoke Nox or Vera by default' -and
        $codexRoot -match 'Preserve mandatory independent validation or review' -and
        $codexRoot -match 'all reconciled required results')
    Check 'PROGRESS_NOT_FINAL' ($kael -match 'Progress\s+messages must explicitly say IN PROGRESS / waiting' -and
        $kael -match 'Never declare final completion while a required direct child is non-terminal')
    $nativeSessions = [regex]::Match($kaelSource, '(?ms)^## Native child sessions\r?\n(?<body>.*?)(?=^## |\z)').Groups['body'].Value
    $completionSource = [regex]::Match($kaelSource, '(?ms)^## Completion gate\r?\n(?<body>.*?)(?=^## |\z)').Groups['body'].Value
    Check 'NATIVE_BACKGROUND_SCHEMA_NEUTRAL' (
        $nativeSessions -match 'OpenCode 2\.3 and later always runs child sessions in\s+the background' -and
        $nativeSessions -match 'On earlier versions,\s+use background behavior only when the currently exposed schema provides it' -and
        $nativeSessions -notmatch 'background:\s*true' -and
        $completionSource -notmatch 'background:\s*true')
    Check 'RUNNING_PARTIAL_AND_PARENT_INTERRUPT' (
        $nativeSessions -match 'state="running".*?partial/progress report' -and
        $nativeSessions -match 'retain\s+writer ownership' -and
        $nativeSessions -match 'Interrupting the parent does not prove that a child or its shell work was\s+cancelled' -and
        $nativeSessions -match 'final report is collected,\s+validated, and consumed once')
    $child = [pscustomobject]@{
        sessionID='synthetic-original'; state='running'; report='partial'
        parentInterrupted=$false; consumed=$false; validated=$false; outcome=''
    }
    $partialReport = Child-ReportGate $child.state $child.report $child.parentInterrupted `
        $child.consumed $child.validated $child.outcome
    $child.state='completed'; $child.report='final'; $child.consumed=$true
    $child.validated=$true; $child.outcome='succeeded'
    $terminalReport = Child-ReportGate $child.state $child.report $child.parentInterrupted `
        $child.consumed $child.validated $child.outcome
    Check 'RUNNING_THEN_TERMINAL_ORIGINAL_REPORT' ($partialReport.writerOwned -and
        -not $partialReport.done -and -not $terminalReport.writerOwned -and
        $terminalReport.done -and $child.sessionID -eq 'synthetic-original')
    $interruptedParent = Child-ReportGate 'running' 'partial' $true $false $false ''
    Check 'PARENT_INTERRUPT_DOES_NOT_CANCEL_CHILD' ($interruptedParent.parentInterrupted -and
        -not $interruptedParent.childCancelled -and $interruptedParent.writerOwned -and
        -not $interruptedParent.done)
    $agents = Get-ChildItem (Join-Path $root '.opencode/agents') -Filter '*.md'
    $allAgentText = ($agents | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"
    Check 'NO_LUNA_FAST' ($allAgentText -notmatch 'gpt-6-luna#fast|luna.fast|luna-fast')
    $workersMatch = @(@('veyra','orin','kovan','nox','vera') | ForEach-Object { (Text ".opencode/agents/$_.md") -match 'model: "?openai/gpt-6-luna#max' }) -notcontains $false
    Check 'MODELS' ($kael -match 'model: "?openai/gpt-6.1-sol#high' -and
        (Text '.opencode/agents/thales.md') -match 'model: openai/gpt-6.1-sol#xhigh' -and
        $workersMatch)
    Write-Output 'COMPLETION GATE QUALIFICATION: PASS (static + synthetic; live qualification separate)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'COMPLETION GATE QUALIFICATION: FAIL'
    exit 1
}
