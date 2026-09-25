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
function Launch([string]$label, [int]$delay) {
    $status = Join-Path $fixture "$label.json"
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = (Get-Command pwsh -ErrorAction Stop).Source
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.WorkingDirectory = $fixture
    foreach ($arg in @('-NoProfile','-NonInteractive','-File',$controller,'-Status',$status,'-Delay',$delay.ToString())) {
        $null = $info.ArgumentList.Add($arg)
    }
    $process = [Diagnostics.Process]::Start($info)
    if ($null -eq $process) { throw "Could not launch $label" }
    $unit = [pscustomobject]@{ Label=$label; Process=$process; Status=$status; Started=[DateTimeOffset]::UtcNow;
        Stdout=$process.StandardOutput.ReadToEndAsync(); Stderr=$process.StandardError.ReadToEndAsync() }
    $units.Add($unit)
    return $unit
}
function Join-And-Validate($unit) {
    if (-not $unit.Process.WaitForExit(35000)) { throw "$($unit.Label) controller timed out" }
    $stdout = $unit.Stdout.GetAwaiter().GetResult()
    $stderr = $unit.Stderr.GetAwaiter().GetResult()
    if ($unit.Process.ExitCode -ne 0) { throw "$($unit.Label) exit $($unit.Process.ExitCode): $stderr $stdout" }
    if (-not (Test-Path -LiteralPath $unit.Status -PathType Leaf)) { throw "$($unit.Label) result missing: $stderr" }
    $data = [IO.File]::ReadAllText($unit.Status) | ConvertFrom-Json -DateKind String
    if ($data.pid -ne $unit.Process.Id -or $data.label -ne $unit.Label -or
        $data.outcome -ne 'PASS' -or -not $data.terminal -or -not $data.launched -or
        $stdout.Trim() -ne "CONTROLLER TERMINAL $($unit.Label)" -or $stderr) {
        throw "$($unit.Label) invalid controller result/output: $stderr $stdout"
    }
    return [pscustomobject]@{ Unit=$unit; Data=$data; Final=[DateTimeOffset]::UtcNow;
        Stdout=$stdout; Stderr=$stderr }
}
$units = [Collections.Generic.List[object]]::new()
try {
    $maintenance = Text '.opencode/agents/maintenance.md'
    $kael = Text '.opencode/agents/kael.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $command = Text '.opencode/commands/maintain.md'
    Check 'FOREGROUND_ONLY' ($maintenance -match 'Always foreground-owned' -and
        $maintenance -match 'LAUNCH → TRACK → WAIT/JOIN → COLLECT → VALIDATE → FINALIZE' -and
        $maintenance -match 'There is no detached terminal state' -and
        $maintenance -notmatch '(?i)explicit background exception|background_handoff|explicit background handoff')
    Check 'BACKGROUND_REQUEST_STILL_OWNED' ($maintenance -match '(?s)Even if the user asks to "run this in the background".*keep ownership and wait' -and
        $maintenance -match 'No PID, status\s+file or manual polling handoff' -and
        $kael -match '(?s)If a user asked for background execution,\s+Maintenance still waits' -and
        $docs -match 'Foreground/join is mandatory')
    Check 'LONG_RUNNING_AND_TERMINAL' ($maintenance -match '(?s)Five, twenty or\s+thirty minutes.*do not authorize detaching' -and
        $maintenance -match 'SUCCESS, PARTIAL, BLOCKED,\s+FAILED or TIMEOUT' -and
        $maintenance -match 'do not launch: report\s+BLOCKED' -and
        $maintenance -match 'Never silently leave required work active')
    Check 'HEADLESS_OBSERVABLE' ($maintenance -match 'CreateNoWindow=true' -and
        $maintenance -match 'without a\s+visible console or focus stealing' -and
        $maintenance -match 'stdout, stderr, exit code and results' -and
        $maintenance -match 'Prefer direct shell/tool execution')
    Check 'PARALLEL_CONTROLLER_AND_GATES' ($maintenance -match 'launch independent A/B/C concurrently' -and
        $maintenance -match 'controller may be the ownership boundary' -and
        $maintenance -match 'Recheck family membership' -and $maintenance -match 'session.inbox.list' -and
        $maintenance -match 'root response, idle root or IN PROGRESS update alone cannot substitute')
    Check 'ROUTING_AND_KAEL' ($command -match 'subagent: true' -and
        $maintenance -match 'do not spawn, call, or delegate to any child agent' -and
        $kael -match 'Kael → Maintenance remains DENIED' -and
        $kael -match 'a completed Maintenance\s+result is not a detached-work handoff' -and
        $kael -notmatch 'RUNNING IN BACKGROUND while the Maintenance')
    Check 'NO_PERSISTENT_SYSTEM' ($maintenance -match 'No global job registry, daemon or scheduled monitor' -and
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

    # Disposable controller cases exercise real owned lifetimes, not an interactive agent.
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
Write-Output "CONTROLLER TERMINAL $($result.label)"
'@)
    $foreground = Launch 'foreground' 16
    Check 'ORIGINAL_GAP_STILL_RUNNING' (-not $foreground.Process.WaitForExit(100))
    $foreground.Process.Refresh()
    Check 'HEADLESS_FOREGROUND' ($foreground.Process.StartInfo.CreateNoWindow -and
        -not $foreground.Process.StartInfo.UseShellExecute -and $foreground.Process.MainWindowHandle -eq [IntPtr]::Zero)
    $fg = Join-And-Validate $foreground
    Check 'FOREGROUND_FINAL_AFTER_TERMINAL' ($fg.Final -ge [DateTimeOffset]::Parse($fg.Data.terminal) -and
        [DateTimeOffset]::Parse($fg.Data.launched) -ge $fg.Unit.Started.AddSeconds(-2))
    Write-Output "FOREGROUND: launch=$($fg.Data.launched) controller terminal=$($fg.Data.terminal) Maintenance final(simulated)=$($fg.Final.ToString('o'))"

    $parallel = @('parallel-a','parallel-b','parallel-c' | ForEach-Object { Launch $_ 3 })
    Check 'PARALLEL_HEADLESS' (@($parallel | Where-Object { $_.Process.StartInfo.CreateNoWindow -and
        $_.Process.MainWindowHandle -eq [IntPtr]::Zero }).Count -eq 3)
    $joined = @($parallel | ForEach-Object { Join-And-Validate $_ })
    $lastTerminal = @($joined | ForEach-Object { [DateTimeOffset]::Parse($_.Data.terminal) } | Sort-Object)[-1]
    $firstTerminal = @($joined | ForEach-Object { [DateTimeOffset]::Parse($_.Data.terminal) } | Sort-Object)[0]
    $lastLaunch = @($joined | ForEach-Object { [DateTimeOffset]::Parse($_.Data.launched) } | Sort-Object)[-1]
    $parallelFinal = [DateTimeOffset]::UtcNow
    Check 'PARALLEL_3_OVERLAP_AND_JOIN' ($joined.Count -eq 3 -and $lastLaunch -lt $firstTerminal -and
        $parallelFinal -ge $lastTerminal -and @($joined | Where-Object { $_.Unit.Process.HasExited }).Count -eq 3)
    Write-Output "PARALLEL: overlapping=3 last launch=$($lastLaunch.ToString('o')) first terminal=$($firstTerminal.ToString('o')) last terminal=$($lastTerminal.ToString('o')) Maintenance final(simulated)=$($parallelFinal.ToString('o'))"
    Write-Output 'VISIBLE WINDOWS OBSERVED: 0 (MainWindowHandle; desktop popup/focus not instrumented)'
    Write-Output 'EXTERNAL WORK OWNERSHIP QUALIFICATION: PASS (static + disposable foreground processes; interactive agent not tested)'
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
