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
    $aegis = Text '.opencode/agents/aegis.md'
    $kael = Text '.opencode/agents/kael.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $command = Text '.opencode/commands/maintain.md'
    Check 'AEGIS_FOREGROUND_ONLY' ($aegis -match 'Always foreground-owned' -and
        $aegis -match 'LAUNCH → TRACK → WAIT/JOIN → COLLECT → VALIDATE → FINALIZE' -and
        $aegis -match 'There is no detached terminal state' -and
        $aegis -notmatch '(?i)explicit background exception|background_handoff|explicit background handoff')
    Check 'BACKGROUND_REQUEST_STILL_OWNED' ($aegis -match '(?s)Even if the user asks to "run this in the background".*keep ownership and wait' -and
        $aegis -match 'No PID, status\s+file or manual polling handoff' -and
        $kael -match '(?s)If a user asked for background execution,\s+Aegis still waits' -and
        $docs -match 'Foreground/join is mandatory')
    Check 'LONG_RUNNING_AND_TERMINAL' ($aegis -match '(?s)Five, twenty or\s+thirty minutes.*do not authorize detaching' -and
        $aegis -match 'SUCCESS, PARTIAL, BLOCKED,\s+FAILED or TIMEOUT' -and
        $aegis -match 'do not launch: report\s+BLOCKED' -and
        $aegis -match 'Never silently leave required work active')
    Check 'HEADLESS_OBSERVABLE' ($aegis -match 'CreateNoWindow=true' -and
        $aegis -match 'without a\s+visible console or focus stealing' -and
        $aegis -match 'stdout, stderr, exit code and results' -and
        $aegis -match 'Prefer direct shell/tool execution')
    Check 'RESTART_OWNERSHIP_RECEIPT' ($aegis -match 'minimal task-scoped recovery receipt' -and $aegis -match 'unique task/run ID' -and
        $aegis -match 'PID and process start time' -and $aegis -match 'executable path' -and
        $aegis -match 'exact launch\s+arguments/command line' -and
        $aegis -match 'working directory' -and
        $aegis -match 'unambiguous task/run ownership marker where supported' -and
        $aegis -match 'parent PID and parent start time' -and $aegis -match 'expected result path' -and
        $aegis -match 'latest meaningful progress timestamp/counter' -and
        $aegis -match 'not a registry' -and $aegis -match 'remove it after validated result collection')
    Check 'ORPHAN_CLASSIFICATION_AND_SAFE_STOP' ($aegis -match 'ACTIVE only with meaningful progress evidence' -and
        $aegis -match 'STALLED only after no meaningful progress over a finite' -and
        $aegis -match 'ORPHANED only when Olympus/Aegis ownership is verified' -and
        $aegis -match '`Responding=True`' -and
        $aegis -match 'parent disappearance alone is not ownership or progress evidence' -and
        $aegis -match 'recheck the exact PID' -and
        $aegis -match 'never kill by process\s+name' -and
        $aegis -match 'forbids retry' -and $aegis -match 'Never retry while the original\s+process is alive')
    Check 'PARALLEL_CONTROLLER_AND_GATES' ($aegis -match 'launch independent A/B/C concurrently' -and
        $aegis -match 'controller may be the ownership boundary' -and
        $aegis -match 'Recheck family membership' -and $aegis -match 'session.inbox.list' -and
        $aegis -match 'root response, idle root or IN PROGRESS update alone cannot substitute')
    Check 'ROUTING_AND_KAEL' ($command -match 'subagent: true' -and
        $aegis -match 'do not spawn, call, or delegate to any child agent' -and
        $kael -match 'Kael → Aegis remains DENIED' -and
        $kael -match 'a completed Aegis\s+result is not a detached-work handoff' -and
        $kael -notmatch 'RUNNING IN BACKGROUND while the Aegis')
    Check 'NO_PERSISTENT_SYSTEM' ($aegis -match 'No global job registry, daemon or scheduled monitor' -and
        -not (Test-Path -LiteralPath (Join-Path $repo '.olympus/jobs.json')))
    $agents = Get-ChildItem (Join-Path $repo '.opencode/agents') -Filter '*.md'
    $agentText = ($agents | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"
    Check 'MODELS_AND_NO_LUNA_FAST' ($kael -match 'model: "openai/gpt-6.1-sol#high"' -and
        $aegis -match 'model: openai/gpt-6-luna#max' -and
        (Text '.opencode/agents/thales.md') -match 'model: openai/gpt-6.1-sol#xhigh' -and
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
    Write-Output "FOREGROUND: launch=$($fg.Data.launched) controller terminal=$($fg.Data.terminal) Aegis final(simulated)=$($fg.Final.ToString('o'))"

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
    Write-Output "PARALLEL: overlapping=3 last launch=$($lastLaunch.ToString('o')) first terminal=$($firstTerminal.ToString('o')) last terminal=$($lastTerminal.ToString('o')) Aegis final(simulated)=$($parallelFinal.ToString('o'))"
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
