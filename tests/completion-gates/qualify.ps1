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
try {
    $kael = Text '.opencode/agents/kael.md'
    $maintenance = Text '.opencode/agents/maintenance.md'
    $command = Text '.opencode/commands/maintain.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    Check 'KAEL_JOIN' ($kael -match 'enumerate the required direct child' -and $kael -match 'consume each result' -and
        $kael -match 'Never declare final completion while a required direct child is non-terminal' -and
        $kael -match 'IN PROGRESS / waiting')
    Check 'MAINTENANCE_PARALLEL' ($maintenance -match 'Independent administrative work may run concurrently' -and
        $maintenance -match 'NOT Olympus subagent routing' -and $maintenance -match 'bounded,\s*task-appropriate')
    Check 'MAINTENANCE_JOIN' ($maintenance -match 'DEFINE the required units' -and
        $maintenance -match 'WAIT / JOIN every required session family' -and $maintenance -match 'COLLECT terminal' -and
        $maintenance -match 'Recheck family membership' -and $maintenance -match 'session.inbox.list')
    Check 'API_SEMANTICS' ($docs -match 'MESSAGE_COMPLETE, ROOT_IDLE and FAMILY_COMPLETE' -and
        $docs -match 'No native family-wide wait|no documented family-wide wait' -and $docs -match 'session/active' -and
        $docs -match 'CLI `opencode run` exit or a root assistant response is not a session-family completion signal')
    Check 'ROUTING_BOUNDARY' ($command -match 'subagent: true' -and $command -match 'Do not delegate' -and
        $maintenance -match 'Do not invoke normal Olympus workers' -and $maintenance -match 'only in response to the user.s explicit')
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
    Check 'PROGRESS_NOT_FINAL' ($kael -match 'Progress\s+messages must explicitly say IN PROGRESS / waiting' -and
        $maintenance -match 'IN PROGRESS progress update is allowed, but is not final success')
    $agents = Get-ChildItem (Join-Path $root '.opencode/agents') -Filter '*.md'
    $allAgentText = ($agents | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"
    Check 'NO_LUNA_FAST' ($allAgentText -notmatch 'gpt-6-luna#fast|luna.fast|luna-fast')
    $workersMatch = @(@('veyra','orin','kovan','nox','vera') | ForEach-Object { (Text ".opencode/agents/$_.md") -match 'model: "?openai/gpt-6-luna#max' }) -notcontains $false
    Check 'MODELS' ($kael -match 'model: "?openai/gpt-6-sol#high' -and
        $maintenance -match 'model: openai/gpt-6-sol#high' -and
        (Text '.opencode/agents/thales.md') -match 'model: openai/gpt-6-sol#xhigh' -and
        $workersMatch)
    Write-Output 'COMPLETION GATE QUALIFICATION: PASS (static + synthetic; live qualification separate)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'COMPLETION GATE QUALIFICATION: FAIL'
    exit 1
}
