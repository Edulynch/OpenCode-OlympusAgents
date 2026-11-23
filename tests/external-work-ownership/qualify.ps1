[CmdletBinding()]
param(
    [switch]$StaticOnly,
    [switch]$ProcessesOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($StaticOnly -and $ProcessesOnly) { throw 'StaticOnly and ProcessesOnly are mutually exclusive.' }
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
    if (-not $ProcessesOnly) {
    $kael = Text '.opencode/agents/kael.md'
    $nox = [regex]::Replace((Text '.opencode/agents/nox.md'), '\s+', ' ')
    $docs = Text 'docs/DEVELOPMENT.md'
    $lifecycle = [regex]::Replace((Text 'olympus/policies/result-lifecycle.md'), '\s+', ' ')
    $kaelSource = [regex]::Replace((Text 'olympus/harnesses/opencode/agent-prompts/kael.md'), '\s+', ' ')
    $kovanSource = [regex]::Replace((Text 'olympus/harnesses/opencode/agent-prompts/kovan.md'), '\s+', ' ')
    $noxSource = [regex]::Replace((Text 'olympus/harnesses/opencode/agent-prompts/nox.md'), '\s+', ' ')
    Check 'KAEL_FOREGROUND_OWNERSHIP' ($kael -match 'Kael owns every process, controller, build/test job, and native child session' -and
        $kael -match 'Keep the task pending from launch through tracking,\s*wait/join, collection, validation, and finalization' -and
        $kael -match 'background does not authorize detached work' -and
        $kael -match 'If that lifecycle is unavailable, use authorized\s+foreground execution when feasible or report BLOCKED before launch' -and
        $docs -match 'Keep the task open through tracking, wait/join,\s*collection, validation, and finalization' -and
        $docs -match 'Background requests do not authorize\s+detachment' -and
        $docs -match 'otherwise report BLOCKED without starting it')
    Check 'NATIVE_SCRIPT_WAIT_RESULT_INVARIANTS' (
        $lifecycle -match 'potentially slow, noninteractive command.*bounded native managed-background execution.*terminal result to the same session' -and
        $lifecycle -match 'use authorized foreground execution when feasible or report the blocker before launch; never detach' -and
        $lifecycle -match 'Deadline expiry is not proof of termination or success' -and
        $lifecycle -match 'completed.*tool status or missing exit code alone is not success' -and
        $lifecycle -match 'nonzero exit/failing command status fails the gate even when the shell tool completed' -and
        $lifecycle -match 'do not retry while it is active, unknown, or unreconciled' -and
        $kaelSource -match 'authorized worker should use a bounded native managed-background shell job.*delivered to that same session' -and
        $kovanSource -match 'one bounded native managed background shell execution.*resumes this same session' -and
        $kovanSource -match 'nonzero exit/failing command status fails the gate even when the shell tool completed' -and
        $noxSource -match 'one bounded native managed-background shell job.*resumes this same session' -and
        $noxSource -match 'nonzero exit/failing status fails the check even if shell execution completed' -and
        $noxSource -match 'Deadline expiry proves neither termination nor success')
    Check 'HOSTED_CI_EXACT_HEAD_WAIT' (
        $lifecycle -match 'at most one bounded, read-only monitor for the exact repository, pull request, and head' -and
        $lifecycle -match 'binding it to that head and using a provider-supported wait/watch only when its terminal result is reliably delivered to the same session' -and
        $lifecycle -match 'Failed, expired, unknown, unconfirmed, or changed-head evidence cannot support merge' -and
        $kaelSource -match 'at most one bounded, read-only Nox monitor for the exact repository, pull request, and head' -and
        $kaelSource -match 'wait/watch reliably delivers the terminal result to that same session and can bind monitoring to the assigned head' -and
        $kaelSource -match 'If a supported wait or delivery is unavailable, leave the gate pending' -and
        $noxSource -match 'at most one bounded, read-only, provider-supported wait/watch.*exact repository, pull request, and head Kael assigned' -and
        $noxSource -match 'terminal result reliably returns to this same session and the wait can bind to that assigned head' -and
        $noxSource -match 'Do not use web access, change credentials/configuration, spawn children, detach, or repeat model-level checks' -and
        $noxSource -match 'failed, expired, unknown, unconfirmed, or changed-head evidence is not a CI pass or basis for merge')
    Check 'EXPLICIT_SINGLE_BACKGROUND_WAIT_NOTICE' (
        $lifecycle -match 'when confirmed task-owned background work blocks progress and no ready independent work remains.*exactly one visible wait notice before the first yield of that continuous wait' -and
        $lifecycle -match 'Identify the background job, child, monitor, or specific awaited result.*what Kael will do when its original terminal result arrives' -and
        $lifecycle -match 'no user continuation is needed only when native delivery is confirmed to resume the owning session automatically' -and
        $lifecycle -match 'If identity, activity, result, or delivery is uncertain.*without claiming the work is running or promising automatic resumption' -and
        $lifecycle -match 'Do not repeat the notice on unchanged subsequent yields' -and
        $kaelSource -match 'Before Kael.s first yield.*confirmed task-owned background work.*no ready independent work remains, send exactly one visible IN PROGRESS / waiting notice' -and
        $kaelSource -match 'Say the user need not prompt.*only when native delivery is confirmed to resume this session automatically' -and
        $kaelSource -match 'Do not repeat the notice during unchanged subsequent yields' -and
        $kaelSource -match 'before the first yield of a continuous wait on confirmed background work send exactly one visible IN PROGRESS / waiting notice')
    Check 'EXPLICIT_FINAL_CLOSURE_NO_FALSE_CLOSE' (
        $lifecycle -match 'After all required work is terminal.*results are collected, validated, and consumed.*every required gate passes.*final response must unambiguously close this task' -and
        $lifecycle -match 'no task-owned agent, script, or CI monitor remains active, no result is uncollected, no requested step remains, and no action is needed' -and
        $lifecycle -match 'A known terminal failure with all work accounted for is final with errors, never success' -and
        $lifecycle -match 'Do not issue a terminal close while required work, a user/manual step, or a result is pending, or state is uncertain' -and
        $kaelSource -match 'TAREA COMPLETADA — NO QUEDA NADA EN ESPERA' -and
        $kaelSource -match 'TAREA FINALIZADA CON ERRORES — NO QUEDA NADA EN ESPERA' -and
        $kaelSource -match 'Explicitly say that no task-owned agent, script, or CI monitor remains active in the background, no result remains uncollected, no requested step remains, and no action is needed' -and
        $kaelSource -match 'Do not use either terminal close if any required work, user/manual step, or result remains pending, or activity/result state is uncertain')
    Check 'LIFECYCLE_AND_TERMINAL' ($kael -match 'Never declare final completion while a required direct child is non-terminal' -and
        $kael -match 'COMPLETION_UNCONFIRMED' -and $kael -match 'PARTIAL or\s+COMPLETION_UNCONFIRMED')
    Check 'NOX_PENDING_SHELL_RESUMPTION' (
        $nox -match 'original background job/shell ID.*execution is pending/running, that command has already started.*not a failure or permission to call shell again' -and
        $nox -match 'Preserve the exact original ID when exposed.*never retry, duplicate, or poll the command' -and
        $nox -match 'send only a progress update and yield so native completion can resume this same session' -and
        $nox -match 'match and consume that original execution.s terminal result once' -and
        $nox -match 'report output/exit only when exposed, otherwise report missing terminal evidence without retrying')
    Check 'PROCESS_OWNERSHIP' ($kael -match 'Missing output is\s+neither failure nor retry authorization' -and
        $kael -match 'never blindly duplicate it' -and
        $kael -match 'Cancellation or missing output alone does not prove non-execution' -and
        $kael -match 'If exact\s+process ownership or safe cleanup cannot be established,\s*stop and report\s+`COMPLETION_UNCONFIRMED`; do not attempt cleanup, recovery, or termination\s+against an uncertain target')
    Check 'PARALLEL_CONTROLLER_AND_GATES' ($kael -match 'waits for required native results or parent notifications' -and
        $kael -match 'consume each result' -and
        $kael -match 'An assistant\s+message or an idle root does not join background children')
    Check 'NO_PERSISTENT_SYSTEM' (-not (Test-Path -LiteralPath (Join-Path $repo '.olympus/jobs.json')))
    $agents = Get-ChildItem (Join-Path $repo '.opencode/agents') -Filter '*.md'
    $agentText = ($agents | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"
    Check 'MODELS_AND_NO_LUNA_FAST' ($kael -match 'model: "openai/gpt-6.2-sol#high"' -and
        (Text '.opencode/agents/thales.md') -match 'model: openai/gpt-6.2-sol#xhigh' -and
        @(@('veyra','orin','kovan','nox','vera') | ForEach-Object {
            (Text ".opencode/agents/$_.md") -match 'model: "?openai/gpt-6-luna#max'
        }) -notcontains $false -and $agentText -notmatch 'gpt-6-luna#fast|luna.fast|luna-fast')
    Check 'CONFIGURED_CEILING_AND_ADAPTIVE_DEFAULT' ($kael -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $kael -match 'NORMAL is cost/context-aware' -and
        (Text '.opencode/commands/olympus.ultra.md') -match 'Maximize useful, safe concurrency')
    }
    if ($StaticOnly) { Write-Output 'EXTERNAL WORK OWNERSHIP QUALIFICATION: PASS (static only)'; exit 0 }
    if (-not $StaticOnly) {

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
    Write-Output "FOREGROUND: launch=$($fg.Data.launched) controller terminal=$($fg.Data.terminal) Kael final(simulated)=$($fg.Final.ToString('o'))"

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
    Write-Output "PARALLEL: overlapping=3 last launch=$($lastLaunch.ToString('o')) first terminal=$($firstTerminal.ToString('o')) last terminal=$($lastTerminal.ToString('o')) Kael final(simulated)=$($parallelFinal.ToString('o'))"
    Write-Output 'VISIBLE WINDOWS OBSERVED: 0 (MainWindowHandle; desktop popup/focus not instrumented)'
    if ($ProcessesOnly) {
        Write-Output 'EXTERNAL WORK OWNERSHIP QUALIFICATION: PASS (disposable foreground processes; interactive agent not tested)'
    } else {
        Write-Output 'EXTERNAL WORK OWNERSHIP QUALIFICATION: PASS (static + disposable foreground processes; interactive agent not tested)'
    }
    }
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
