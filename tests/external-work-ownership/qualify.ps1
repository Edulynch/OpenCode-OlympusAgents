[CmdletBinding()]
param([switch]$StaticOnly)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
function Text([string]$path) { [IO.File]::ReadAllText((Join-Path $repo $path)) }
function Check([string]$name, [bool]$value) {
    if (-not $value) { throw "$name FAIL" }
    Write-Output "$name PASS"
}
function May-Detach([bool]$explicit, [bool]$durable) {
    if (-not $explicit) { return 'FOREGROUND' }
    if (-not $durable) { return 'BACKGROUND_HANDOFF_UNAVAILABLE' }
    return 'BACKGROUND_HANDOFF'
}
function Launch([string]$label, [int]$delay) {
    $status = Join-Path $fixture "$label.json"
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = (Get-Command pwsh -ErrorAction Stop).Source
    $info.UseShellExecute = $false
    $info.WorkingDirectory = $fixture
    foreach ($arg in @('-NoProfile','-File',$controller,'-Status',$status,'-Delay',$delay.ToString())) {
        $null = $info.ArgumentList.Add($arg)
    }
    $process = [Diagnostics.Process]::Start($info)
    if ($null -eq $process) { throw "Could not launch $label" }
    return [pscustomobject]@{ Label=$label; Process=$process; Status=$status; Started=[DateTimeOffset]::UtcNow }
}
function Join-And-Validate($unit) {
    if (-not $unit.Process.WaitForExit(30000)) { throw "$($unit.Label) controller timed out (PID $($unit.Process.Id))" }
    if ($unit.Process.ExitCode -ne 0) { throw "$($unit.Label) controller exit $($unit.Process.ExitCode)" }
    if (-not (Test-Path -LiteralPath $unit.Status -PathType Leaf)) { throw "$($unit.Label) status missing" }
    $data = [IO.File]::ReadAllText($unit.Status) | ConvertFrom-Json -DateKind String
    if ($data.pid -ne $unit.Process.Id -or $data.label -ne [IO.Path]::GetFileNameWithoutExtension($unit.Status) -or
        $data.outcome -ne 'PASS' -or -not $data.terminal -or -not $data.launched) {
        throw "$($unit.Label) invalid controller result"
    }
    return [pscustomobject]@{ Unit=$unit; Data=$data; Final=[DateTimeOffset]::UtcNow }
}
$units = [Collections.Generic.List[object]]::new()
try {
    $maintenance = Text '.opencode/agents/maintenance.md'
    $kael = Text '.opencode/agents/kael.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $command = Text '.opencode/commands/maintain.md'
    Check 'FOREGROUND_DEFAULT' ($maintenance -match '(?s)Default: foreground.*explicit user request' -and
        $maintenance -match 'Ambiguous wording means foreground' -and
        (May-Detach $false $true) -eq 'FOREGROUND')
    Check 'FOREGROUND_JOIN' ($maintenance -match 'WAIT / JOIN' -and $maintenance -match '(?s)track, WAIT / JOIN, collect, validate' -and
        $maintenance -match 'Do not finish\s+the turn while required work is running')
    Check 'EXPLICIT_BACKGROUND' ($maintenance -match '(?s)Only clear user intent.*permits Maintenance to finish' -and
        (May-Detach $true $true) -eq 'BACKGROUND_HANDOFF')
    Check 'DURABLE_HANDOFF' ($maintenance -match 'Before launch, ensure a durable tracking handoff' -and
        $maintenance -match 'PID/job ID' -and $maintenance -match 'safe read-only status and result commands')
    Check 'NO_FALSE_FOLLOWUP' ($maintenance -match 'not automatically send a follow-up' -and
        $kael -match 'no\s+automatic chat follow-up')
    Check 'NO_SILENT_DETACH' ($maintenance -match 'do not launch an unowned background' -and
        (May-Detach $true $false) -eq 'BACKGROUND_HANDOFF_UNAVAILABLE')
    Check 'PARALLEL_AND_NESTED' ($maintenance -match 'launch independent A/B/C concurrently' -and
        $maintenance -match 'controller may be the ownership boundary' -and
        $maintenance -match 'Recheck family membership' -and $maintenance -match 'session.inbox.list' -and
        $maintenance -match 'root response, idle root or IN PROGRESS update alone cannot substitute')
    Check 'ROUTING_BOUNDARY' ($command -match 'subagent: true' -and
        $maintenance -match 'do not spawn, call, or delegate to any child agent' -and
        $kael -match 'Kael → Maintenance remains DENIED')
    Check 'KAEL_HANDOFF' ($kael -match 'Maintenance \*\*turn\*\* has finished' -and
        $kael -match 'RUNNING IN BACKGROUND' -and $docs -match 'not “everything complete”')
    Check 'NO_NEW_REGISTRY' ($maintenance -match 'no global job registry or daemon' -and
        -not (Test-Path -LiteralPath (Join-Path $repo '.olympus/jobs.json')))
    $agents = Get-ChildItem (Join-Path $repo '.opencode/agents') -Filter '*.md'
    $agentText = ($agents | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"
    Check 'MODELS_AND_NO_LUNA_FAST' ($kael -match 'model: "openai/gpt-6-sol#high"' -and
        $maintenance -match 'model: openai/gpt-6-sol#high' -and
        (Text '.opencode/agents/sorin.md') -match 'model: openai/gpt-6-sol#xhigh' -and
        @(@('veyra','orin','kovan','nox','vera') | ForEach-Object {
            (Text ".opencode/agents/$_.md") -match 'model: "?openai/gpt-6-luna#max'
        }) -notcontains $false -and $agentText -notmatch 'gpt-6-luna#fast|luna.fast|luna-fast')
    Check 'CONCURRENCY_4_4' ($kael -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $kael -match 'fan out up to four useful children' -and $kael -match 'NORMAL is cost/context-aware')
    if ($StaticOnly) { Write-Output 'EXTERNAL WORK OWNERSHIP QUALIFICATION: PASS (static only)'; exit 0 }

    # Disposable process tests exercise real controller lifetimes, not an interactive agent.
    # No production repository or external session is touched; every launched PID is joined.
    $fixture = Join-Path ([IO.Path]::GetTempPath()) ('opencode/external-ownership-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($fixture) | Out-Null
    $controller = Join-Path $fixture 'controller.ps1'
    [IO.File]::WriteAllText($controller, @'
param([string]$Status, [int]$Delay)
$start = [DateTimeOffset]::UtcNow
Start-Sleep -Seconds $Delay
$result = @{ label = [IO.Path]::GetFileNameWithoutExtension($Status); pid = $PID;
    launched = $start.ToString('o'); terminal = [DateTimeOffset]::UtcNow.ToString('o'); outcome = 'PASS' }
[IO.File]::WriteAllText($Status, ($result | ConvertTo-Json -Compress))
'@)
    $submitted = [DateTimeOffset]::UtcNow
    $foreground = Launch 'foreground' 2; $units.Add($foreground)
    Check 'ORIGINAL_GAP_STILL_RUNNING' (-not $foreground.Process.WaitForExit(100))
    $fg = Join-And-Validate $foreground
    Check 'FOREGROUND_FINAL_AFTER_TERMINAL' ($fg.Final -ge [DateTimeOffset]::Parse($fg.Data.terminal) -and
        $fg.Unit.Started -ge $submitted)
    Write-Output "FOREGROUND: submit=$($submitted.ToString('o')) launch=$($fg.Data.launched) external terminal=$($fg.Data.terminal) Maintenance final(simulated)=$($fg.Final.ToString('o'))"

    # Background handoff happens while the process is still running. The test then
    # joins it so this qualification itself never leaves a detached process.
    $background = Launch 'background' 2; $units.Add($background)
    $handoff = [pscustomobject]@{
        PID=$background.Process.Id; Started=$background.Started.ToString('o');
        Command=$controller; WorkingDirectory=$fixture; ResultPath=$background.Status;
        StatusCommand="Get-Process -Id $($background.Process.Id) -ErrorAction SilentlyContinue";
        ResultCommand="Get-Content -LiteralPath '$($background.Status)' -Raw";
        Warning='This chat will not automatically send a follow-up when it finishes.'
    }
    $bgFinal = [DateTimeOffset]::UtcNow
    Check 'BACKGROUND_HANDOFF_WHILE_RUNNING' (-not $background.Process.HasExited -and
        $handoff.PID -eq $background.Process.Id -and $handoff.Started -and $handoff.Command -and
        $handoff.WorkingDirectory -and $handoff.ResultPath -and $handoff.StatusCommand -and
        $handoff.ResultCommand -and $handoff.Warning -match 'not automatically')
    $bg = Join-And-Validate $background
    Check 'BACKGROUND_TERMINAL_AFTER_HANDOFF' ($bgFinal -lt [DateTimeOffset]::Parse($bg.Data.terminal))
    Write-Output "BACKGROUND: launch=$($background.Started.ToString('o')) controller started=$($bg.Data.launched) Maintenance final(simulated)=$($bgFinal.ToString('o')) external terminal=$($bg.Data.terminal) tracking=PID $($handoff.PID), $($handoff.ResultPath)"
    Write-Output "BACKGROUND STATUS: $($handoff.StatusCommand)"
    Write-Output "BACKGROUND RESULT: $($handoff.ResultCommand)"

    $parallel = @('parallel-a','parallel-b','parallel-c' | ForEach-Object { Launch $_ 2 })
    foreach ($unit in $parallel) { $units.Add($unit) }
    $joined = @($parallel | ForEach-Object { Join-And-Validate $_ })
    $lastTerminal = @($joined | ForEach-Object { [DateTimeOffset]::Parse($_.Data.terminal) } | Sort-Object)[-1]
    $firstTerminal = @($joined | ForEach-Object { [DateTimeOffset]::Parse($_.Data.terminal) } | Sort-Object)[0]
    $lastLaunch = @($joined | ForEach-Object { [DateTimeOffset]::Parse($_.Data.launched) } | Sort-Object)[-1]
    $parallelFinal = [DateTimeOffset]::UtcNow
    Check 'PARALLEL_3_OVERLAP_AND_JOIN' ($joined.Count -eq 3 -and $lastLaunch -lt $firstTerminal -and
        $parallelFinal -ge $lastTerminal -and @($joined | Where-Object { $_.Unit.Process.HasExited }).Count -eq 3)
    Write-Output "PARALLEL: overlapping=3 last launch=$($lastLaunch.ToString('o')) first terminal=$($firstTerminal.ToString('o')) last terminal=$($lastTerminal.ToString('o')) Maintenance final(simulated)=$($parallelFinal.ToString('o'))"
    Check 'AMBIGUOUS_LONG_FOREGROUND' ((May-Detach $false $true) -eq 'FOREGROUND')
    Check 'UNAVAILABLE_BEFORE_LAUNCH' ((May-Detach $true $false) -eq 'BACKGROUND_HANDOFF_UNAVAILABLE')
    Write-Output "FIXTURE: $fixture"
    Write-Output 'EXTERNAL WORK OWNERSHIP QUALIFICATION: PASS (static + disposable process lifecycle; agent interaction not tested)'
    exit 0
} catch {
    Write-Output "EVIDENCE: $($_.Exception.Message)"
    Write-Output 'EXTERNAL WORK OWNERSHIP QUALIFICATION: FAIL'
    exit 1
} finally {
    foreach ($unit in $units) {
        if (-not $unit.Process.HasExited) {
            $unit.Process.Kill($true)
            $unit.Process.WaitForExit()
        }
        $unit.Process.Dispose()
    }
}
