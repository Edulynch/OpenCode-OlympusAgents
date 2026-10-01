[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$publicRoot = [Environment]::GetEnvironmentVariable('PUBLIC','Process')
if (-not $publicRoot) { throw 'BLOCKED_ISOLATION: Windows PUBLIC directory is unavailable for an out-of-profile fixture.' }
$tempRoot = Join-Path ([IO.Path]::GetFullPath($publicRoot)) 'opencode-olympus-qualification'
$approvedReceiptRoot = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode'
$runId = [guid]::NewGuid().ToString('N')
$run = Join-Path $tempRoot ('olympus-global-runtime-' + $runId)
$evidencePath = Join-Path $run 'evidence.json'
$receiptPath = Join-Path $approvedReceiptRoot ('olympus-global-runtime-' + $runId + '-recovery-receipt.json')
$script:forbiddenProfilePrefix = [IO.Path]::GetFullPath([Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)).TrimEnd([char[]]@('\','/'))
$utf8 = [Text.UTF8Encoding]::new($false)
$completed = $false
$exitCode = 0
$script:receipt = [ordered]@{ task_run_id=$runId; owner_marker="olympus-global-runtime:$runId"; processes=@() }
$script:evidence = [ordered]@{
    task_run_id = $runId
    started_at = (Get-Date).ToString('o')
    source_root = $source
    run_root = $run
    qualification = 'fresh child processes; preflight opencode debug paths in isolated HOME and four XDG roots; OpenCode OPENCODE_CONFIG_DIR is config-layer-only; clean fixture; owned standalone serve processes; GET /api/agent with fixture context'
    runtime_contract = [ordered]@{
        cli_version = $null
        agent_list_operation = 'GET /api/agent (OpenAPI agent.list); query directory is the location context'
        context_directory = $null
        context_load = 'first location-scoped API request initializes that location; verify from its response/logs'
        standalone_process = 'qualification-owned opencode serve PID; no managed-service discovery'
        home_resolution = 'HOME and USERPROFILE point to the isolated home before each new process starts; OPENCODE_TEST_HOME is not used'
        config_resolution = 'OPENCODE_CONFIG_DIR selects the config layer only for A; XDG_CONFIG_HOME/DATA_HOME/CACHE_HOME/STATE_HOME and HOME isolate the remaining global paths in both controls'
        path_isolation = 'opencode debug paths is run before installer/runtime discovery in fresh A and B environments; home/config/data/cache/state/tmp and optional log paths are checked against exact isolated roots and the real user-profile forbidden prefix'
    }
    cli = $null
    cli_version = $null
    expected_agent_ids = @()
    controls = [ordered]@{ A=$null; B=$null }
    path_isolation = 'NOT_RUN'
    real_profile_paths_observed = @()
    runtime_result = 'UNRESOLVED'
    classification = 'IN_PROGRESS'
    failure = $null
}

function Save-Evidence {
    if (Test-Path -LiteralPath $run -PathType Container) {
        $script:evidence.updated_at = (Get-Date).ToString('o')
        [IO.File]::WriteAllText($evidencePath, ($script:evidence | ConvertTo-Json -Depth 30), $utf8)
    }
}

function Save-Receipt {
    if (Test-Path -LiteralPath $run -PathType Container) {
        $script:receipt.updated_at = (Get-Date).ToString('o')
        [IO.File]::WriteAllText($receiptPath, ($script:receipt | ConvertTo-Json -Depth 30), $utf8)
    }
}

function Check([string]$Id, [bool]$Condition, [string]$Detail = '') {
    if (-not $Condition) {
        if ($Detail) { throw "$Id FAIL`n$Detail" }
        throw "$Id FAIL"
    }
    Write-Output "$Id PASS"
}

function Get-OpenCodeExecutable {
    $applications = @(Get-Command 'opencode.exe' -CommandType Application -ErrorAction SilentlyContinue)
    if ($applications.Count -gt 0) { return $applications[0].Source }

    $command = Get-Command opencode -ErrorAction Stop
    if ([IO.Path]::GetExtension($command.Source) -ieq '.ps1') {
        $wrapperRoot = Split-Path -Parent $command.Source
        $bundledExe = Join-Path $wrapperRoot 'node_modules/@opencode/cli/bin/opencode.exe'
        if (Test-Path -LiteralPath $bundledExe -PathType Leaf) { return $bundledExe }
    }
    if ($command.CommandType -eq [Management.Automation.CommandTypes]::Application -and
        [IO.Path]::GetExtension($command.Source) -ieq '.exe') { return $command.Source }
    throw 'OPENCODE_EXECUTABLE_UNRESOLVED: Could not resolve the actual OpenCode executable.'
}

function Set-IsolatedEnvironment(
    [Diagnostics.ProcessStartInfo]$StartInfo,
    [string]$Root,
    [string]$ConfigRoot,
    [string]$ControlName
) {
    $isolatedHome = Join-Path $Root 'home'
    $isolatedTemp = Join-Path $Root 'temp'
    $xdgConfig = Join-Path $Root 'xdg-config'
    $xdgData = Join-Path $Root 'xdg-data'
    $xdgCache = Join-Path $Root 'xdg-cache'
    $xdgState = Join-Path $Root 'xdg-state'
    $paths = @{
        HOME=$isolatedHome
        USERPROFILE=$isolatedHome
        HOMEDRIVE=[IO.Path]::GetPathRoot($isolatedHome).TrimEnd('\')
        HOMEPATH=$isolatedHome.Substring([IO.Path]::GetPathRoot($isolatedHome).TrimEnd('\').Length)
        APPDATA=(Join-Path $isolatedHome 'AppData/Roaming')
        LOCALAPPDATA=(Join-Path $isolatedHome 'AppData/Local')
        XDG_CONFIG_HOME=$xdgConfig
        XDG_DATA_HOME=$xdgData
        XDG_STATE_HOME=$xdgState
        XDG_CACHE_HOME=$xdgCache
        TMP=$isolatedTemp
        TEMP=$isolatedTemp
        OLYMPUS_GLOBAL_RUNTIME_RUN_ID=$runId
        OLYMPUS_GLOBAL_RUNTIME_CONTROL=$ControlName
    }
    foreach ($path in @($isolatedHome,$isolatedTemp,$paths.APPDATA,$paths.LOCALAPPDATA,
        $paths.XDG_CONFIG_HOME,$paths.XDG_DATA_HOME,$paths.XDG_STATE_HOME,$paths.XDG_CACHE_HOME)) {
        [IO.Directory]::CreateDirectory($path) | Out-Null
    }
    # Start from a clean process environment. OPENCODE_CONFIG_DIR selects a
    # config layer for Control A; only HOME and the four XDG roots isolate the
    # complete set of OpenCode global paths.
    $preserved = [ordered]@{}
    foreach ($key in @('PATH','SystemRoot','WINDIR','COMSPEC','PATHEXT')) {
        $value = [Environment]::GetEnvironmentVariable($key,'Process')
        if ($value) { $preserved[$key] = $value }
    }
    if (-not $preserved.Contains('PATH') -or -not $preserved.Contains('SystemRoot')) {
        throw 'ISOLATED_ENVIRONMENT_INVALID: PATH and SystemRoot are required to start OpenCode on Windows.'
    }
    $StartInfo.Environment.Clear()
    foreach ($key in $preserved.Keys) { $StartInfo.Environment[$key] = [string]$preserved[$key] }
    foreach ($key in $paths.Keys) { $StartInfo.Environment[$key] = [string]$paths[$key] }
    if ($ConfigRoot) { $StartInfo.Environment['OPENCODE_CONFIG_DIR'] = [IO.Path]::GetFullPath($ConfigRoot) }
    return [pscustomobject]@{
        home=[IO.Path]::GetFullPath($isolatedHome)
        userprofile=[IO.Path]::GetFullPath($isolatedHome)
        temp=[IO.Path]::GetFullPath($isolatedTemp)
        xdg_config_home=[IO.Path]::GetFullPath($xdgConfig)
        xdg_data_home=[IO.Path]::GetFullPath($xdgData)
        xdg_cache_home=[IO.Path]::GetFullPath($xdgCache)
        xdg_state_home=[IO.Path]::GetFullPath($xdgState)
        config_dir=$(if ($ConfigRoot) { [IO.Path]::GetFullPath($ConfigRoot) } else { $null })
    }
}

function Invoke-CapturedProcess(
    [string]$Executable,
    [string[]]$Arguments,
    [string]$WorkingDirectory,
    [string]$Root,
    [string]$ConfigRoot,
    [string]$ControlName,
    [int]$TimeoutMilliseconds = 90000
) {
    $startInfo = [Diagnostics.ProcessStartInfo]::new([IO.Path]::GetFullPath($Executable))
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.WorkingDirectory = [IO.Path]::GetFullPath($WorkingDirectory)
    foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add([string]$argument) }
    $environment = Set-IsolatedEnvironment $startInfo $Root $ConfigRoot $ControlName
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        [void]$process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutMilliseconds)) {
            $process.Refresh()
            $recordedStart = $process.StartTime.ToUniversalTime()
            $actual = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)" -ErrorAction SilentlyContinue
            if ($null -eq $actual -or [int]$actual.ProcessId -ne $process.Id -or
                [IO.Path]::GetFullPath([string]$actual.ExecutablePath) -ine [IO.Path]::GetFullPath($Executable) -or
                $process.StartTime.ToUniversalTime() -ne $recordedStart) {
                throw "PROCESS_CLEANUP_BLOCKED: Cannot safely identify timed-out $Executable PID $($process.Id)."
            }
            $process.Kill($false)
            $process.WaitForExit()
            throw "PROCESS_TIMEOUT: $Executable $($Arguments -join ' ')"
        }
        $process.WaitForExit()
        return [pscustomobject]@{
            ExitCode=$process.ExitCode
            Stdout=$stdoutTask.GetAwaiter().GetResult()
            Stderr=$stderrTask.GetAwaiter().GetResult()
            Environment=$environment
            Pid=$process.Id
        }
    } finally { $process.Dispose() }
}

function Get-ResolvedPaths([string]$Text) {
    $paths = [ordered]@{}
    foreach ($line in ($Text -split "`r?`n")) {
        $match = [regex]::Match([string]$line,'^\s*(?<name>[A-Za-z][A-Za-z0-9_-]*)\s{2,}(?<path>.+?)\s*$')
        if (-not $match.Success) { continue }
        $name = $match.Groups['name'].Value.ToLowerInvariant()
        $value = $match.Groups['path'].Value.Trim()
        if (-not [IO.Path]::IsPathFullyQualified($value)) { throw "OPENCODE_PATH_DISCOVERY_FAILED: $name is not an absolute path: $value" }
        if ($paths.Contains($name)) { throw "OPENCODE_PATH_DISCOVERY_FAILED: duplicate path entry $name." }
        $paths[$name] = [IO.Path]::GetFullPath($value)
    }
    return ,$paths
}

function Test-PathWithinRoot([string]$Path, [string]$Root) {
    $separators = [char[]]@([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar)
    $candidate = [IO.Path]::GetFullPath($Path).TrimEnd($separators)
    $base = [IO.Path]::GetFullPath($Root).TrimEnd($separators)
    return $candidate.Equals($base,[StringComparison]::OrdinalIgnoreCase) -or
        $candidate.StartsWith($base + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)
}

function Test-PathWithinAnyRoot([string]$Path, [string[]]$Roots) {
    foreach ($rootPath in $Roots) {
        if ($rootPath -and (Test-PathWithinRoot $Path $rootPath)) { return $true }
    }
    return $false
}

function Get-ProjectStatus([string]$Target) {
    $status = @(& git -C $Target status --porcelain --untracked-files=all 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "FIXTURE_GIT_STATUS_FAILED: $($status -join "`n")" }
    return ($status -join "`n").Trim()
}

function Get-TreeSnapshot([string]$Root) {
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) { return '<MISSING_ROOT>' }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\','/'))
    $prefix = $base + [IO.Path]::DirectorySeparatorChar
    return (@(Get-ChildItem -LiteralPath $base -Force -Recurse | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring($prefix.Length)
        if ($_.PSIsContainer) { $relative + ':DIRECTORY' }
        else { $relative + ':SHA256:' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    }) -join "`n")
}

function Get-ProfileLeaks([string]$Text) {
    # This one prefix is a forbidden-path sentinel. No files below the real
    # profile are enumerated or read by the qualification.
    $normalizedText = $Text.Replace('\\','\').Replace('/','\')
    $prefix = $script:forbiddenProfilePrefix.Replace('/','\').TrimEnd('\')
    if (-not $prefix) { throw 'FORBIDDEN_PROFILE_PREFIX_UNAVAILABLE' }
    $pattern = '(?i)' + [regex]::Escape($prefix) + '(?:\\[^\s"'',$;<>|]*)?'
    return @([regex]::Matches($normalizedText,$pattern) | ForEach-Object {
        $_.Value.TrimEnd([char[]]@('\','/','.',')',']','}'))
    } | Sort-Object -Unique)
}

function Start-ServerOutputCapture($Process) {
    $capture = [pscustomobject]@{
        stdout_reader=$Process.StandardOutput
        stderr_reader=$Process.StandardError
        stdout_pending=$null
        stderr_pending=$null
        stdout_lines=[System.Collections.Generic.List[string]]::new()
        stderr_lines=[System.Collections.Generic.List[string]]::new()
    }
    $capture.stdout_pending = $capture.stdout_reader.ReadLineAsync()
    $capture.stderr_pending = $capture.stderr_reader.ReadLineAsync()
    return $capture
}

function Update-ServerOutputCapture($Capture) {
    foreach ($streamName in @('stdout','stderr')) {
        $readerProperty = $streamName + '_reader'
        $pendingProperty = $streamName + '_pending'
        $linesProperty = $streamName + '_lines'
        while ($null -ne $Capture.$pendingProperty -and $Capture.$pendingProperty.IsCompleted) {
            $line = $Capture.$pendingProperty.GetAwaiter().GetResult()
            if ($null -eq $line) { $Capture.$pendingProperty = $null; break }
            $Capture.$linesProperty.Add([string]$line)
            $Capture.$pendingProperty = $Capture.$readerProperty.ReadLineAsync()
        }
    }
}

function Get-ServerOutputText($Capture) {
    Update-ServerOutputCapture $Capture
    return [pscustomobject]@{
        stdout=($Capture.stdout_lines -join "`n")
        stderr=($Capture.stderr_lines -join "`n")
    }
}

function Assert-ServerIsolation($Capture, $Control) {
    $output = Get-ServerOutputText $Capture
    $text = $output.stdout + "`n" + $output.stderr
    $profileLeaks = @(Get-ProfileLeaks $text)
    if ($profileLeaks.Count -gt 0) {
        $Control.real_profile_paths_observed = $profileLeaks
        throw ('OPENCODE_GLOBAL_ISOLATION_LEAK: server output referenced forbidden real-profile path(s): ' + ($profileLeaks -join ', '))
    }
}

function Get-AgentApiResponse(
    [Net.Http.HttpClient]$Client,
    [string]$RequestUri,
    [string]$Authorization,
    $Capture,
    $Control
) {
    $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Get,$RequestUri)
    $request.Headers.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Basic',$Authorization)
    $response = $null
    try {
        $responseTask = $Client.SendAsync($request)
        $deadline = [DateTime]::UtcNow.AddSeconds(30)
        while (-not $responseTask.IsCompleted -and [DateTime]::UtcNow -lt $deadline) {
            Assert-ServerIsolation $Capture $Control
            Start-Sleep -Milliseconds 50
        }
        if (-not $responseTask.IsCompleted) { throw 'AGENT_API_TIMEOUT: fixture-scoped GET /api/agent did not return in 30 seconds.' }
        $response = $responseTask.GetAwaiter().GetResult()
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $profileLeaks = @(Get-ProfileLeaks $body)
        if ($profileLeaks.Count -gt 0) {
            $Control.real_profile_paths_observed = @(@($Control.real_profile_paths_observed) + @($profileLeaks) | Sort-Object -Unique)
            throw ('OPENCODE_GLOBAL_ISOLATION_LEAK: API response referenced forbidden real-profile path(s): ' + ($profileLeaks -join ', '))
        }
        Start-Sleep -Milliseconds 250
        Assert-ServerIsolation $Capture $Control
        return [pscustomobject]@{ StatusCode=[int]$response.StatusCode; Text=$body }
    } finally {
        if ($null -ne $response) { $response.Dispose() }
        $request.Dispose()
    }
}

function Get-FreeLoopbackPort {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
    try { $listener.Start(); return ([Net.IPEndPoint]$listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

function Get-ServerIdentity($Process, $Record, [bool]$RequireListener = $true) {
    $Process.Refresh()
    if ($Process.HasExited) { throw "OWNED_SERVER_EXITED: PID $($Record.pid) exited before ownership validation." }
    $actual = Get-CimInstance Win32_Process -Filter "ProcessId = $($Record.pid)" -ErrorAction Stop
    if ($null -eq $actual -or [int]$actual.ProcessId -ne [int]$Record.pid) { throw 'OWNED_SERVER_IDENTITY_UNKNOWN: PID not present in Win32_Process.' }
    if ([IO.Path]::GetFullPath([string]$actual.ExecutablePath) -ine [IO.Path]::GetFullPath([string]$Record.executable)) {
        throw 'OWNED_SERVER_IDENTITY_MISMATCH: executable path changed.'
    }
    $actualStart = $Process.StartTime.ToUniversalTime().ToString('o')
    if ($actualStart -cne [string]$Record.process_start_utc) { throw 'OWNED_SERVER_IDENTITY_MISMATCH: process start time changed.' }
    if ([int]$actual.ParentProcessId -ne [int]$Record.parent_pid) { throw 'OWNED_SERVER_IDENTITY_MISMATCH: parent PID changed.' }
    if ([string]$actual.CommandLine -cne [string]$Record.command_line -or [string]$actual.CommandLine -notlike "*$($Record.command_marker)*") {
        throw 'OWNED_SERVER_IDENTITY_MISMATCH: exact serve arguments are absent from the command line.'
    }
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($Record.parent_pid)" -ErrorAction Stop
    if ($null -eq $parent -or [int]$parent.ProcessId -ne [int]$Record.parent_pid) { throw 'OWNED_SERVER_IDENTITY_MISMATCH: recorded parent PID is absent.' }
    $parentStart = if ($parent.CreationDate -is [DateTime]) {
        ([DateTime]$parent.CreationDate).ToUniversalTime()
    } else {
        [DateTimeOffset]::Parse([string]$parent.CreationDate,[Globalization.CultureInfo]::InvariantCulture).UtcDateTime
    }
    $recordedParentStart = [DateTimeOffset]::Parse([string]$Record.parent_start_utc,[Globalization.CultureInfo]::InvariantCulture).UtcDateTime
    if ([Math]::Abs(($parentStart - $recordedParentStart).TotalSeconds) -gt 1) { throw 'OWNED_SERVER_IDENTITY_MISMATCH: parent process start time changed.' }
    $listenerConnections = @()
    if ($RequireListener) {
        $listenerConnections = @(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort ([int]$Record.port) -State Listen -ErrorAction SilentlyContinue)
    }
    $listenerPids = @($listenerConnections | ForEach-Object { [int]$_.OwningProcess } | Sort-Object -Unique)
    if ($RequireListener -and ($listenerPids.Count -ne 1 -or $listenerPids[0] -ne [int]$Record.pid)) {
        throw "OWNED_SERVER_IDENTITY_MISMATCH: endpoint listener PID(s) '$($listenerPids -join ',')' do not match launched PID $($Record.pid)."
    }
    return [pscustomobject]@{ pid=[int]$actual.ProcessId; executable=[string]$actual.ExecutablePath; command_line=[string]$actual.CommandLine; listener_pid=$(if ($listenerPids.Count) { $listenerPids[0] } else { $null }); process_start_utc=$actualStart; parent_pid=[int]$parent.ProcessId; parent_start_utc=$parentStart.ToString('o') }
}

function Stop-OwnedServer($Process, $Record, $OutputCapture) {
    if ($null -eq $Process) { return [pscustomobject]@{ stdout=''; stderr=''; exit_code=$null } }
    $Process.Refresh()
    if (-not $Process.HasExited) {
        # Recheck exact PID, start time, executable, parent, command line and
        # unique endpoint immediately before stopping this owned server.
        $requireListener = $Record.Contains('listener_identity') -and ($null -ne $Record['listener_identity'])
        $identity = Get-ServerIdentity $Process $Record ([bool]$requireListener)
        $Record.cleanup_identity = $identity
        $Process.Kill($false)
        if (-not $Process.WaitForExit(15000)) { throw "OWNED_SERVER_CLEANUP_BLOCKED: exact PID $($Record.pid) did not exit after termination." }
    }
    $Process.WaitForExit()
    $Process.Refresh()
    $Record.exit_code = $Process.ExitCode
    $Record.stopped_at = (Get-Date).ToString('o')
    if ($null -ne $OutputCapture) {
        for ($attempt=0; $attempt -lt 100 -and ($null -ne $OutputCapture.stdout_pending -or $null -ne $OutputCapture.stderr_pending); $attempt++) {
            Update-ServerOutputCapture $OutputCapture
            if ($null -ne $OutputCapture.stdout_pending -or $null -ne $OutputCapture.stderr_pending) { Start-Sleep -Milliseconds 10 }
        }
        $collected = Get-ServerOutputText $OutputCapture
        $stdout = $collected.stdout
        $stderr = $collected.stderr
    } else { $stdout = ''; $stderr = '' }
    # `opencode serve` writes its generated Basic-auth password to stdout.
    # The qualification consumes it only in memory; retained logs redact it.
    $stdout = [regex]::Replace($stdout,'(?im)^(\s*server password\s+)\S+','$1<redacted>')
    $stdoutPath = [string]$Record.stdout_path
    $stderrPath = [string]$Record.stderr_path
    [IO.File]::WriteAllText($stdoutPath,$stdout,$utf8)
    [IO.File]::WriteAllText($stderrPath,$stderr,$utf8)
    $Record.stdout_sha256 = (Get-FileHash -LiteralPath $stdoutPath -Algorithm SHA256).Hash
    $Record.stderr_sha256 = (Get-FileHash -LiteralPath $stderrPath -Algorithm SHA256).Hash
    $Process.Dispose()
    Save-Receipt
    return [pscustomobject]@{ stdout=$stdout; stderr=$stderr; exit_code=$Record.exit_code }
}

function Initialize-Control([ValidateSet('A','B')][string]$Name, [string]$ControlRoot, [string]$IsolationRoot) {
    $fixture = Join-Path $ControlRoot 'trusted-fixture'
    $isolatedHome = Join-Path $IsolationRoot 'home'
    $isolatedTemp = Join-Path $IsolationRoot 'temp'
    $xdgConfig = Join-Path $IsolationRoot 'xdg-config'
    $xdgData = Join-Path $IsolationRoot 'xdg-data'
    $xdgCache = Join-Path $IsolationRoot 'xdg-cache'
    $xdgState = Join-Path $IsolationRoot 'xdg-state'
    $configRoot = if ($Name -eq 'A') { Join-Path $IsolationRoot 'explicit-opencode-config' } else { $null }
    $expectedConfigRoot = if ($Name -eq 'A') { [IO.Path]::GetFullPath($configRoot) } else { [IO.Path]::GetFullPath((Join-Path $xdgConfig 'opencode')) }
    $allowedRoots = @($IsolationRoot,$ControlRoot,$fixture,$isolatedHome,$isolatedTemp,$xdgConfig,$xdgData,$xdgCache,$xdgState,$expectedConfigRoot,
        (Join-Path $isolatedHome 'AppData/Roaming'),(Join-Path $isolatedHome 'AppData/Local'))
    foreach ($directory in @($ControlRoot,$IsolationRoot,$fixture,$isolatedHome,$isolatedTemp,$xdgConfig,$xdgData,$xdgCache,$xdgState,
        (Join-Path $isolatedHome 'AppData/Roaming'),(Join-Path $isolatedHome 'AppData/Local'),$expectedConfigRoot)) {
        [IO.Directory]::CreateDirectory($directory) | Out-Null
    }
    [IO.File]::WriteAllText((Join-Path $fixture 'README.md'),"Isolated global runtime discovery fixture ($Name).`n",$utf8)
    & git -C $fixture init --quiet
    if ($LASTEXITCODE -ne 0) { throw "FIXTURE_GIT_INIT_FAILED: control $Name" }
    $fixtureStatusBefore = Get-ProjectStatus $fixture
    $fixtureIsClean = (-not (Test-Path (Join-Path $fixture 'opencode.json')) -and
        -not (Test-Path (Join-Path $fixture 'opencode.jsonc')) -and
        -not (Test-Path (Join-Path $fixture '.opencode')) -and
        -not (Test-Path (Join-Path $fixture 'AGENTS.md')) -and
        -not (Test-Path (Join-Path $fixture 'CLAUDE.md')) -and
        -not (Test-Path (Join-Path $fixture 'CONTEXT.md')))
    $environment = [ordered]@{
        HOME=[IO.Path]::GetFullPath($isolatedHome)
        USERPROFILE=[IO.Path]::GetFullPath($isolatedHome)
        XDG_CONFIG_HOME=[IO.Path]::GetFullPath($xdgConfig)
        XDG_DATA_HOME=[IO.Path]::GetFullPath($xdgData)
        XDG_CACHE_HOME=[IO.Path]::GetFullPath($xdgCache)
        XDG_STATE_HOME=[IO.Path]::GetFullPath($xdgState)
        TEMP=[IO.Path]::GetFullPath($isolatedTemp)
        TMP=[IO.Path]::GetFullPath($isolatedTemp)
        isolation_root=[IO.Path]::GetFullPath($IsolationRoot)
        cwd=[IO.Path]::GetFullPath($fixture)
        effective_config_root=$expectedConfigRoot
        OPENCODE_CONFIG_DIR=$(if ($Name -eq 'A') { $expectedConfigRoot } else { $null })
    }
    $control = [ordered]@{
        control=$Name
        status='PRELAUNCH_PATH_CHECK'
        path_isolation='IN_PROGRESS'
        environment=$environment
        fixture_no_project_config=$fixtureIsClean
        installer_exit_code=$null
        installer_output=$null
        verifyonly_exit_code=$null
        fixture_no_project_local_olympus=$false
        runtime_process=$null
        endpoint=$null
        api_status=$null
        api_request=$null
        api_context_directory=$null
        api_response_text_first=$null
        api_response_text_lazy_load_probe=$null
        api_data_count_first=$null
        api_data_count_lazy_load_probe=$null
        api_agent_ids=@()
        api_agents=@()
        runtime_path_resolution=$null
        path_probe=$null
        path_isolation_failures=@()
        aegis_generated_resource=$null
        origin_probe_id=$null
        origin_probe_description=$null
        origin_probe_visible=$false
        minimal_probe_id=$null
        minimal_probe_description=$null
        minimal_probe_visible=$false
        real_profile_paths_observed=@()
        failure=$null
    }
    $script:evidence.controls[$Name] = $control
    Save-Evidence

    try {
        $pathProbe = Invoke-CapturedProcess $script:evidence.cli @('debug','paths') $fixture $IsolationRoot $configRoot $Name
        $pathProbeText = $pathProbe.Stdout + $pathProbe.Stderr
        $resolvedPaths = Get-ResolvedPaths $pathProbeText
        $expectedPaths = [ordered]@{
            home=[IO.Path]::GetFullPath($isolatedHome)
            config=$expectedConfigRoot
            data=[IO.Path]::GetFullPath((Join-Path $xdgData 'opencode'))
            cache=[IO.Path]::GetFullPath((Join-Path $xdgCache 'opencode'))
            state=[IO.Path]::GetFullPath((Join-Path $xdgState 'opencode'))
            tmp=[IO.Path]::GetFullPath((Join-Path $isolatedTemp 'opencode'))
            log=[IO.Path]::GetFullPath((Join-Path $xdgData 'opencode/log'))
            bin=[IO.Path]::GetFullPath((Join-Path $xdgCache 'opencode/bin'))
            repos=[IO.Path]::GetFullPath((Join-Path $xdgData 'opencode/repos'))
            db=[IO.Path]::GetFullPath((Join-Path $xdgData 'opencode/opencode.db'))
        }
        $failures = [System.Collections.Generic.List[string]]::new()
        if ($pathProbe.ExitCode -ne 0) { $failures.Add("opencode debug paths exit=$($pathProbe.ExitCode): $pathProbeText") }
        foreach ($nameRequired in @('home','config','data','cache','state','tmp')) {
            if (-not $resolvedPaths.Contains($nameRequired)) { $failures.Add("missing required OpenCode path '$nameRequired'"); continue }
            if (-not $resolvedPaths[$nameRequired].Equals($expectedPaths[$nameRequired],[StringComparison]::OrdinalIgnoreCase)) {
                $failures.Add("$nameRequired resolved '$($resolvedPaths[$nameRequired])'; expected isolated '$($expectedPaths[$nameRequired])'")
            }
        }
        foreach ($nameExpected in $expectedPaths.Keys) {
            if (-not $resolvedPaths.Contains($nameExpected)) { continue }
            if (-not $resolvedPaths[$nameExpected].Equals($expectedPaths[$nameExpected],[StringComparison]::OrdinalIgnoreCase)) {
                $failures.Add("$nameExpected resolved '$($resolvedPaths[$nameExpected])'; expected isolated '$($expectedPaths[$nameExpected])'")
            }
        }
        foreach ($nameResolved in $resolvedPaths.Keys) {
            if (-not (Test-PathWithinAnyRoot $resolvedPaths[$nameResolved] $allowedRoots)) {
                $failures.Add("$nameResolved resolved outside all isolated roots: '$($resolvedPaths[$nameResolved])'")
            }
        }
        $profileLeaks = [System.Collections.Generic.List[string]]::new()
        foreach ($nameResolved in $resolvedPaths.Keys) {
            if (Test-PathWithinRoot $resolvedPaths[$nameResolved] $script:forbiddenProfilePrefix) {
                $profileLeaks.Add("$nameResolved=$($resolvedPaths[$nameResolved])")
            }
        }
        foreach ($leak in (Get-ProfileLeaks $pathProbeText)) { $profileLeaks.Add("debug-path-output=$leak") }
        $profileLeaks = @($profileLeaks | Sort-Object -Unique)
        if ($profileLeaks.Count -gt 0) {
            $control.real_profile_paths_observed = $profileLeaks
            $failures.Add('OPENCODE_GLOBAL_ISOLATION_LEAK: ' + ($profileLeaks -join ', '))
        }
        $control.path_probe = [ordered]@{
            pid=$pathProbe.Pid
            exit_code=$pathProbe.ExitCode
            stdout=$pathProbe.Stdout.Trim()
            stderr=$pathProbe.Stderr.Trim()
        }
        $control.runtime_path_resolution = [ordered]@{
            paths=$resolvedPaths
            config_override_used=($Name -eq 'A')
            xdg_roots=[ordered]@{ config=$xdgConfig; data=$xdgData; cache=$xdgCache; state=$xdgState }
        }
        $control.path_isolation_failures = @($failures)
        if ($failures.Count -gt 0) {
            $control.path_isolation = 'FAIL'
            $control.status = 'BLOCKED_ISOLATION'
            $control.failure = $failures -join '; '
            $script:evidence.path_isolation = 'FAIL'
            $script:evidence.real_profile_paths_observed = $profileLeaks
            $script:evidence.classification = 'BLOCKED_ISOLATION'
            $script:evidence.failure = "Control $Name pre-launch path assertion failed: $($control.failure)"
            Save-Evidence
            throw $script:evidence.failure
        }
        $control.path_isolation = 'PASS'
        $control.status = 'PATH_ISOLATION_PASS'
        $script:evidence.runtime_contract.cli_version = $script:evidence.cli_version
        Save-Evidence
        Write-Host "GLOBAL_RUNTIME_$($Name)_PATH_ISOLATION: PASS"
    } catch {
        if ($control.path_isolation -ne 'FAIL') {
            $control.path_isolation = 'FAIL'
            $control.status = 'BLOCKED_ISOLATION'
            $control.path_isolation_failures = @($_.Exception.Message)
            $control.failure = $_.Exception.Message
            $script:evidence.path_isolation = 'FAIL'
            $script:evidence.classification = 'BLOCKED_ISOLATION'
            $script:evidence.failure = "Control $Name pre-launch path assertion failed: $($_.Exception.Message)"
            Save-Evidence
        }
        throw
    }

    return [pscustomobject]@{
        Name=$Name
        ControlRoot=$ControlRoot
        IsolationRoot=$IsolationRoot
        Fixture=$fixture
        IsolatedHome=$isolatedHome
        IsolatedTemp=$isolatedTemp
        XdgConfig=$xdgConfig
        XdgData=$xdgData
        XdgCache=$xdgCache
        XdgState=$xdgState
        ConfigRoot=$configRoot
        ExpectedConfigRoot=$expectedConfigRoot
        AllowedRoots=$allowedRoots
        FixtureStatusBefore=$fixtureStatusBefore
        Control=$control
    }
}

function Invoke-Control([pscustomobject]$Context, [string[]]$ExpectedAgentIds) {
    $Name = [string]$Context.Name
    $ControlRoot = [string]$Context.ControlRoot
    $IsolationRoot = [string]$Context.IsolationRoot
    $fixture = [string]$Context.Fixture
    $isolatedHome = [string]$Context.IsolatedHome
    $configRoot = $Context.ConfigRoot
    $expectedConfigRoot = [string]$Context.ExpectedConfigRoot
    $allowedRoots = [string[]]$Context.AllowedRoots
    $fixtureStatusBefore = [string]$Context.FixtureStatusBefore
    $control = $Context.Control
    $control.status = 'IN_PROGRESS'
    $script:evidence.controls[$Name] = $control
    Save-Evidence
    Check "GLOBAL_RUNTIME_$($Name)_CLEAN_PROJECT_FIXTURE" ([bool]$control.fixture_no_project_config)

    $installArguments = @('-NoLogo','-NoProfile','-File',$installer,'-SourceRoot',$source,'-Target',$fixture,
        '-Scope','global','-Harness','opencode')
    $install = Invoke-CapturedProcess $script:evidence.pwsh $installArguments $fixture $IsolationRoot $configRoot $Name
    $control.installer_exit_code = $install.ExitCode
    $control.installer_output = ($install.Stdout + $install.Stderr).Trim()
    Check "GLOBAL_RUNTIME_$($Name)_GLOBAL_INSTALL" ($install.ExitCode -eq 0 -and
        $control.installer_output -match 'OLYMPUS_GLOBAL_INSTALL: OPENCODE .* READY' -and
        (Test-Path -LiteralPath (Join-Path $expectedConfigRoot 'agents/kael.md') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $expectedConfigRoot 'olympus/orchestrator-install.json') -PathType Leaf)) $control.installer_output
    $installedAgentIds = @(Get-ChildItem -LiteralPath (Join-Path $expectedConfigRoot 'agents') -Filter '*.md' -File | ForEach-Object { $_.BaseName } | Sort-Object -Unique)
    $sourceAegisPath = Join-Path $source '.opencode/agents/aegis.md'
    $installedAegisPath = Join-Path $expectedConfigRoot 'agents/aegis.md'
    $aegisSourceHash = (Get-FileHash -LiteralPath $sourceAegisPath -Algorithm SHA256).Hash
    $aegisInstalledHash = if (Test-Path -LiteralPath $installedAegisPath -PathType Leaf) { (Get-FileHash -LiteralPath $installedAegisPath -Algorithm SHA256).Hash } else { $null }
    $aegisText = if ($aegisInstalledHash) { [IO.File]::ReadAllText($installedAegisPath) } else { '' }
    $control.aegis_generated_resource = [ordered]@{
        source_sha256=$aegisSourceHash
        installed_sha256=$aegisInstalledHash
        generated_marker=($aegisText -match 'GENERATED BY scripts/render_harnesses\.py')
        hidden=($aegisText -match '(?m)^hidden:\s*true\s*$')
        mode_subagent=($aegisText -match '(?m)^mode:\s*subagent\s*$')
        verified=($aegisInstalledHash -ceq $aegisSourceHash -and $aegisText -match 'GENERATED BY scripts/render_harnesses\.py' -and
            $aegisText -match '(?m)^hidden:\s*true\s*$' -and $aegisText -match '(?m)^mode:\s*subagent\s*$')
    }
    Check "GLOBAL_RUNTIME_$($Name)_ALL_GENERATED_AGENTS_INSTALLED" ($installedAgentIds.Count -eq 12 -and
        @($ExpectedAgentIds | Where-Object { $_ -notin $installedAgentIds }).Count -eq 0)
    Check "GLOBAL_RUNTIME_$($Name)_GENERATED_AEGIS_RESOURCE" ([bool]$control.aegis_generated_resource.verified)
    if ($Name -eq 'A') {
        Check 'GLOBAL_RUNTIME_A_COMPLETE_OPEN_CODE_LAYOUT' ((Test-Path (Join-Path $expectedConfigRoot 'agents/veyra.md')) -and
            (Test-Path (Join-Path $expectedConfigRoot 'commands/maintain.md')) -and
            (Test-Path (Join-Path $expectedConfigRoot 'plugins/olympus-activity/activity.ts')))
    }
    $control.fixture_no_project_local_olympus = (-not (Test-Path (Join-Path $fixture '.opencode')) -and
        -not (Test-Path (Join-Path $fixture 'opencode.json')) -and -not (Test-Path (Join-Path $fixture 'opencode.jsonc')) -and
        -not (Test-Path (Join-Path $fixture 'AGENTS.md')) -and -not (Test-Path (Join-Path $fixture 'CLAUDE.md')) -and
        -not (Test-Path (Join-Path $fixture 'CONTEXT.md')))
    Check "GLOBAL_RUNTIME_$($Name)_NO_PROJECT_LOCAL_FALLBACK" ([bool]$control.fixture_no_project_local_olympus)

    $globalSnapshotBeforeVerify = Get-TreeSnapshot $expectedConfigRoot
    $fixtureSnapshotBeforeVerify = Get-TreeSnapshot $fixture
    $verifyArguments = @('-NoLogo','-NoProfile','-File',$installer,'-SourceRoot',$source,'-Target',$fixture,
        '-Scope','global','-Harness','opencode','-VerifyOnly')
    $verify = Invoke-CapturedProcess $script:evidence.pwsh $verifyArguments $fixture $IsolationRoot $configRoot $Name
    $control.verifyonly_exit_code = $verify.ExitCode
    $globalSnapshotAfterVerify = Get-TreeSnapshot $expectedConfigRoot
    $fixtureSnapshotAfterVerify = Get-TreeSnapshot $fixture
    Check "GLOBAL_RUNTIME_$($Name)_VERIFYONLY_READ_ONLY" ($verify.ExitCode -eq 0 -and
        ($verify.Stdout + $verify.Stderr) -match 'OLYMPUS_GLOBAL_VERIFY: opencode' -and
        $globalSnapshotAfterVerify -ceq $globalSnapshotBeforeVerify -and
        $fixtureSnapshotAfterVerify -ceq $fixtureSnapshotBeforeVerify -and
        (Get-ProjectStatus $fixture) -ceq $fixtureStatusBefore -and
        $control.fixture_no_project_config)

    # This unique marker proves that this owned process consumed the control's
    # isolated global config. Its V2 `permission` field is the current documented
    # agent frontmatter contract; the fixture remains project-local-Olympus-free.
    $probeId = 'olympus-runtime-origin-' + $Name.ToLowerInvariant() + '-' + $runId.Substring(0,8)
    $probeDescription = "Isolated Olympus runtime origin marker $runId control $Name"
    $probeText = @"
---
description: "$probeDescription"
mode: primary
permission:
  read: allow
---
This temporary qualification-only agent proves which global config root the owned process loaded.
"@.TrimStart("`r","`n") + "`n"
    [IO.File]::WriteAllText((Join-Path $expectedConfigRoot ("agents/$probeId.md")),$probeText,$utf8)
    $control.origin_probe_id = $probeId
    $control.origin_probe_description = $probeDescription
    # A plain valid-format primary entry separates an upstream directory-loader
    # problem from malformed Olympus frontmatter in the generated role files.
    $minimalProbeId = 'olympus-runtime-minimal-' + $Name.ToLowerInvariant() + '-' + $runId.Substring(0,8)
    $minimalProbeDescription = "Minimal isolated OpenCode agent loader probe $runId control $Name"
    $minimalProbeText = @"
---
description: "$minimalProbeDescription"
mode: primary
model: "openai/gpt-6.1-sol#high"
---
Qualification-only minimal agent; never executed.
"@.TrimStart("`r","`n") + "`n"
    [IO.File]::WriteAllText((Join-Path $expectedConfigRoot ("agents/$minimalProbeId.md")),$minimalProbeText,$utf8)
    $control.minimal_probe_id = $minimalProbeId
    $control.minimal_probe_description = $minimalProbeDescription

    $port = Get-FreeLoopbackPort
    $endpoint = "http://127.0.0.1:$port"
    $serverArguments = @('serve','--hostname','127.0.0.1','--port',[string]$port,'--log-level','debug','--print-logs')
    $commandMarker = "serve --hostname 127.0.0.1 --port $port"
    $parent = Get-Process -Id $PID -ErrorAction Stop
    $parentStart = $parent.StartTime.ToUniversalTime().ToString('o')
    $stdoutPath = Join-Path $ControlRoot 'server.stdout.txt'
    $stderrPath = Join-Path $ControlRoot 'server.stderr.txt'
    $record = [ordered]@{
        task_run_id=$runId
        control=$Name
        owner_marker="olympus-global-runtime:$($runId):$($Name)"
        pid=$null
        process_start_utc=$null
        executable=[IO.Path]::GetFullPath($script:evidence.cli)
        arguments=$serverArguments
        command_marker=$commandMarker
        working_directory=[IO.Path]::GetFullPath($fixture)
        parent_pid=$PID
        parent_start_utc=$parentStart
        endpoint=$endpoint
        port=$port
        effective_config_directory=$expectedConfigRoot
        effective_home=$isolatedHome
        fixture_directory=[IO.Path]::GetFullPath($fixture)
        launch_environment=[ordered]@{}
        expected_result_path=$evidencePath
        stdout_path=$stdoutPath
        stderr_path=$stderrPath
        latest_progress_at=$null
        progress_counter=0
        status='PLANNED'
    }
    $script:receipt.processes = @($script:receipt.processes) + @($record)
    Save-Receipt
    $startInfo = [Diagnostics.ProcessStartInfo]::new($record.executable)
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.WorkingDirectory = $record.working_directory
    foreach ($argument in $serverArguments) { $startInfo.ArgumentList.Add([string]$argument) }
    $launchEnvironment = Set-IsolatedEnvironment $startInfo $IsolationRoot $configRoot $Name
    $record.launch_environment = [ordered]@{
        HOME=$launchEnvironment.home
        USERPROFILE=$launchEnvironment.userprofile
        OPENCODE_CONFIG_DIR=$launchEnvironment.config_dir
        XDG_CONFIG_HOME=$launchEnvironment.xdg_config_home
        XDG_DATA_HOME=$launchEnvironment.xdg_data_home
        XDG_CACHE_HOME=$launchEnvironment.xdg_cache_home
        XDG_STATE_HOME=$launchEnvironment.xdg_state_home
        TEMP=$launchEnvironment.temp
        TMP=$launchEnvironment.temp
        cwd=$startInfo.WorkingDirectory
        effective_config_root=$expectedConfigRoot
    }
    $serverPassword = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $startInfo.Environment['OPENCODE_SERVER_PASSWORD'] = $serverPassword
    $server = [Diagnostics.Process]::new()
    $server.StartInfo = $startInfo
    $serverStarted = $false
    $outputCapture = $null
    $controlFailure = $null
    $serverOutput = [pscustomobject]@{ stdout=''; stderr=''; exit_code=$null }
    try {
        [void]$server.Start()
        $serverStarted = $true
        $record.pid = $server.Id
        $record.process_start_utc = $server.StartTime.ToUniversalTime().ToString('o')
        $record.status = 'RUNNING'
        $serverArgumentsText = ($serverArguments -join ' ')
        $record.command_line = '"' + $record.executable + '" ' + $serverArgumentsText
        Save-Receipt
        $outputCapture = Start-ServerOutputCapture $server
        $deadline = [DateTime]::UtcNow.AddSeconds(45)
        $identity = $null
        while ([DateTime]::UtcNow -lt $deadline) {
            $server.Refresh()
            if ($server.HasExited) { throw "OWNED_SERVER_START_FAILED: PID $($server.Id) exited with code $($server.ExitCode)." }
            Assert-ServerIsolation $outputCapture $control
            try {
                $identity = Get-ServerIdentity $server $record
                break
            } catch {
                if ($_.Exception.Message -notmatch 'do not match launched PID') { throw }
                Start-Sleep -Milliseconds 200
            }
        }
        if ($null -eq $identity) { throw "OWNED_SERVER_START_TIMEOUT: listener not owned by PID $($record.pid) at $endpoint." }
        $record.status = 'ACTIVE_OWNED'
        $record.listener_identity = $identity
        $record.latest_progress_at = (Get-Date).ToString('o')
        $record.progress_counter = 1
        $record.progress_evidence = '127.0.0.1 listener owner PID matches recorded OpenCode serve PID'
        Save-Receipt
        $control.runtime_process = $record
        $control.endpoint = $endpoint

        $encodedDirectory = [Uri]::EscapeDataString([IO.Path]::GetFullPath($fixture))
        $requestUri = "$endpoint/api/agent?directory=$encodedDirectory"
        $control.api_request = "GET $requestUri"
        $authorization = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("opencode:$serverPassword"))
        $handler = [Net.Http.HttpClientHandler]::new()
        $handler.UseProxy = $false
        $httpClient = [Net.Http.HttpClient]::new($handler)
        $httpClient.Timeout = [TimeSpan]::FromSeconds(30)
        try {
            $firstResult = Get-AgentApiResponse $httpClient $requestUri $authorization $outputCapture $control
            $control.api_status = $firstResult.StatusCode
            $control.api_response_text_first = $firstResult.Text
            if ($firstResult.StatusCode -ne 200) { throw "AGENT_API_HTTP_FAILED: status=$($firstResult.StatusCode) response=$($firstResult.Text)" }
            $firstApi = ConvertFrom-Json -InputObject $firstResult.Text -AsHashtable -Depth 100
            if ($firstApi -isnot [System.Collections.IDictionary] -or -not $firstApi.Contains('data') -or -not $firstApi.Contains('location')) {
                throw 'AGENT_API_RESPONSE_INVALID: expected an object with location and data fields.'
            }
            $firstAgents = @($firstApi.data)
            $control.api_data_count_first = $firstAgents.Count
            $api = $firstApi
            $agents = $firstAgents

            if ($firstAgents.Count -eq 0) {
                # One explicit, read-only lazy-load diagnostic (not a retry loop):
                # a second request to the same owned process/context distinguishes
                # first-request lazy loading from a persistent empty global roster.
                $control.api_request_lazy_load_probe = "GET $requestUri"
                $lazyResult = Get-AgentApiResponse $httpClient $requestUri $authorization $outputCapture $control
                $control.api_response_text_lazy_load_probe = $lazyResult.Text
                if ($lazyResult.StatusCode -ne 200) { throw "AGENT_API_LAZY_LOAD_PROBE_FAILED: status=$($lazyResult.StatusCode) response=$($lazyResult.Text)" }
                $lazyApi = ConvertFrom-Json -InputObject $lazyResult.Text -AsHashtable -Depth 100
                if ($lazyApi -isnot [System.Collections.IDictionary] -or -not $lazyApi.Contains('data') -or -not $lazyApi.Contains('location')) {
                    throw 'AGENT_API_LAZY_LOAD_RESPONSE_INVALID: expected an object with location and data fields.'
                }
                $lazyAgents = @($lazyApi.data)
                $control.api_data_count_lazy_load_probe = $lazyAgents.Count
                $api = $lazyApi
                $agents = $lazyAgents
                $control.api_status = $lazyResult.StatusCode
            }
        } finally {
            $httpClient.Dispose()
        }
        $contextDirectory = [IO.Path]::GetFullPath([string]$api.location.directory)
        $control.api_context_directory = $contextDirectory
        if ($contextDirectory -ine [IO.Path]::GetFullPath($fixture)) {
            throw "AGENT_API_CONTEXT_MISMATCH: expected $fixture, response location is $contextDirectory."
        }
        $agents = @($api.data)
        $agentIds = @($agents | ForEach-Object {
            if ($_ -is [System.Collections.IDictionary]) {
                if ($_.Contains('id')) { [string]$_['id'] } elseif ($_.Contains('name')) { [string]$_['name'] }
            }
        } | Where-Object { $_ } | Sort-Object -Unique)
        $control.api_agents = @($agents | ForEach-Object {
            if ($_ -is [System.Collections.IDictionary]) {
                [ordered]@{
                    id=$(if ($_.Contains('id')) { [string]$_['id'] } elseif ($_.Contains('name')) { [string]$_['name'] } else { $null })
                    hidden=$(if ($_.Contains('hidden')) { [bool]$_['hidden'] } else { $null })
                    mode=$(if ($_.Contains('mode')) { [string]$_['mode'] } else { $null })
                    description=$(if ($_.Contains('description')) { [string]$_['description'] } else { $null })
                }
            }
        } | Where-Object { $_.id })
        $control.api_agent_ids = $agentIds
        $record.latest_progress_at = (Get-Date).ToString('o')
        $record.progress_counter = if ($null -ne $control.api_data_count_lazy_load_probe) { 3 } else { 2 }
        $record.progress_evidence = 'owned endpoint returned HTTP 200 for fixture-scoped GET /api/agent; an empty first result received exactly one documented lazy-load diagnostic request; response parsed after isolation guard'
        $record.api_request = $control.api_request
        $record.api_status = $control.api_status
        $record.api_context_directory = $contextDirectory
        $record.agent_ids = $agentIds
        $record.status = 'API_RESULT_COLLECTED'
        $afterQueryIdentity = Get-ServerIdentity $server $record
        if ($afterQueryIdentity.pid -ne $identity.pid -or $afterQueryIdentity.listener_pid -ne $identity.listener_pid) {
            throw 'AGENT_API_OWNERSHIP_MISMATCH: queried endpoint no longer belongs to the launched server PID.'
        }
        Save-Receipt
    } catch {
        $controlFailure = $_.Exception.Message
        $record.failure = $controlFailure
        Save-Receipt
    } finally {
        if (-not $serverStarted) {
            if ($null -ne $server) { $server.Dispose() }
        } elseif ($null -ne $server) {
            $serverOutput = Stop-OwnedServer $server $record $outputCapture
        }
    }

    $serverLogs = [IO.File]::ReadAllText($stderrPath) + "`n" + [IO.File]::ReadAllText($stdoutPath)
    $control.real_profile_paths_observed = @(@($control.real_profile_paths_observed) + @(Get-ProfileLeaks $serverLogs) | Sort-Object -Unique)
    if ($control.real_profile_paths_observed.Count -gt 0 -and
        $controlFailure -notmatch '^OPENCODE_GLOBAL_ISOLATION_LEAK:') {
        $controlFailure = 'OPENCODE_GLOBAL_ISOLATION_LEAK: ' + (@($control.real_profile_paths_observed | Sort-Object -Unique) -join ', ')
    }
    if ($controlFailure) {
        $control.status = 'FAILED'
        $control.failure = $controlFailure
        Save-Evidence
        $record.status = 'TERMINAL_COLLECTED'
        Save-Receipt
        Write-Output "CONTROL $Name FAIL: $controlFailure"
        return $control
    }
    $checkResults = [ordered]@{}
    $checkResults.process_is_owned = [bool]($record.pid -and $record.process_start_utc -and
        $record.endpoint -eq $endpoint -and $record.listener_identity.pid -eq $record.pid -and
        $record.listener_identity.listener_pid -eq $record.pid -and $control.api_status -eq 200)
    $checkResults.explicit_agent_request_context = [bool]($control.api_context_directory -ieq [IO.Path]::GetFullPath($fixture))
    $checkResults.no_real_profile_path_leaks = [bool](@($control.real_profile_paths_observed).Count -eq 0)
    $checkResults.global_paths_prelaunch_isolated = [bool]($control.path_isolation -eq 'PASS')
    $lowerIds = @($control.api_agent_ids | ForEach-Object { $_.ToLowerInvariant() })
    $probeAgent = @($agents | Where-Object {
        if ($_ -is [System.Collections.IDictionary]) {
            $agentId = if ($_.Contains('id')) { [string]$_['id'] } elseif ($_.Contains('name')) { [string]$_['name'] } else { '' }
            $agentId -ieq $probeId
        } else { $false }
    } | Select-Object -First 1)
    if ($probeAgent.Count -gt 0 -and [string]$probeAgent[0].description -ceq $probeDescription) { $control.origin_probe_visible = $true }
    $minimalAgent = @($agents | Where-Object {
        if ($_ -is [System.Collections.IDictionary]) {
            $agentId = if ($_.Contains('id')) { [string]$_['id'] } elseif ($_.Contains('name')) { [string]$_['name'] } else { '' }
            $agentId -ieq $minimalProbeId
        } else { $false }
    } | Select-Object -First 1)
    if ($minimalAgent.Count -gt 0 -and [string]$minimalAgent[0].description -ceq $minimalProbeDescription) { $control.minimal_probe_visible = $true }
    $checkResults.isolated_global_origin_marker = [bool]$control.origin_probe_visible
    $checkResults.roster_nonempty = [bool](@($control.api_agent_ids).Count -gt 0)
    $requiredVisibleIds = @($ExpectedAgentIds | Where-Object { $_ -ine 'aegis' })
    $missingIds = @($requiredVisibleIds | Where-Object { $_.ToLowerInvariant() -notin $lowerIds })
    $aegisApiRecords = @($control.api_agents | Where-Object { [string]$_.id -ieq 'aegis' })
    $aegisApiRepresentationValid = ($aegisApiRecords.Count -eq 0 -or [bool]$aegisApiRecords[0].hidden)
    $checkResults.aegis_generated_resource_correct = [bool]$control.aegis_generated_resource.verified
    $checkResults.aegis_hidden_or_not_listed = [bool]$aegisApiRepresentationValid
    $checkResults.expected_olympus_roster = [bool]($missingIds.Count -eq 0 -and $aegisApiRepresentationValid -and $control.aegis_generated_resource.verified)
    $checkResults.no_project_local_fallback = [bool]$control.fixture_no_project_local_olympus
    $checkResults.verifyonly_read_only = [bool]($control.verifyonly_exit_code -eq 0)
    $control.checks = $checkResults
    $failedChecks = @($checkResults.Keys | Where-Object { -not $checkResults[$_] })
    $control.status = if ($failedChecks.Count -eq 0) { 'PASS' } else { 'FAIL' }
    if ($failedChecks.Count -gt 0) {
        $control.failure = "Failed checks: $($failedChecks -join ', '); missing visible Olympus IDs=$($missingIds -join ','); marker=$probeId; minimal_marker=$minimalProbeId visible=$($control.minimal_probe_visible); first_count=$($control.api_data_count_first); lazy_count=$($control.api_data_count_lazy_load_probe); roster=$($control.api_agent_ids -join ','); aegis_api_count=$($aegisApiRecords.Count); aegis_resource_verified=$($control.aegis_generated_resource.verified)"
    }
    Write-Output "GLOBAL_RUNTIME_$($Name)_REAL_PROFILE_PATH_OBSERVATIONS: $(if (@($control.real_profile_paths_observed).Count -eq 0) { '0' } else { $control.real_profile_paths_observed -join ', ' })"
    $record.status = 'TERMINAL_COLLECTED'
    Save-Receipt
    Save-Evidence
    Write-Output "CONTROL $Name $($control.status): PID=$($record.pid); endpoint=$endpoint; cwd=$fixture; HOME=$isolatedHome; XDG_CONFIG_HOME=$($Context.XdgConfig); XDG_DATA_HOME=$($Context.XdgData); XDG_CACHE_HOME=$($Context.XdgCache); XDG_STATE_HOME=$($Context.XdgState); TEMP=$($Context.IsolatedTemp); TMP=$($Context.IsolatedTemp); OPENCODE_CONFIG_DIR=$(if ($Name -eq 'A') { $expectedConfigRoot } else { '<unset>' }); config_root=$expectedConfigRoot; roster=$($control.api_agent_ids -join ','); marker=$($control.origin_probe_visible)"
    return $control
}

function Invoke-ControlAndCollect([pscustomobject]$Context, [string[]]$ExpectedAgentIds) {
    # Invoke-Control emits human-readable Check/log lines as well as its result.
    # Capture the complete output, forward only text, and return only the control
    # dictionary so callers cannot mistake a log line for a result object.
    $output = @(Invoke-Control $Context $ExpectedAgentIds)
    $results = @($output | Where-Object { $_ -is [System.Collections.IDictionary] })
    foreach ($line in @($output | Where-Object { $_ -is [string] })) { Write-Host $line }
    if ($results.Count -ne 1) { throw "CONTROL_RESULT_COLLECTION_FAILED: expected one control result for $($Context.Name), found $($results.Count)." }
    return $results[0]
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: OpenCode global runtime qualification requires Windows.' }
    if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'POWERSHELL_UNQUALIFIED: Run this qualification under PowerShell 7.' }
    [IO.Directory]::CreateDirectory($tempRoot) | Out-Null
    [IO.Directory]::CreateDirectory($approvedReceiptRoot) | Out-Null
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $script:evidence.cli = Get-OpenCodeExecutable
    $script:evidence.pwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop).Source
    Save-Evidence

    $version = Invoke-CapturedProcess $script:evidence.cli @('--version') $run $run $null 'A'
    $script:evidence.cli_version = ($version.Stdout + $version.Stderr).Trim()
    Check 'GLOBAL_RUNTIME_OPENCODE_CLI_AVAILABLE' ($version.ExitCode -eq 0 -and $script:evidence.cli_version)

    $expectedAgentIds = @(Get-ChildItem -LiteralPath (Join-Path $source '.opencode/agents') -Filter '*.md' -File |
        Sort-Object Name | ForEach-Object { $_.BaseName })
    $script:evidence.expected_agent_ids = $expectedAgentIds
    Check 'GLOBAL_RUNTIME_EXPECTED_GENERATED_ROSTER' ($expectedAgentIds.Count -eq 12 -and
        @(@('kael','veyra','kovan','nox','aegis') | Where-Object { $_ -notin $expectedAgentIds }).Count -eq 0)

    $controlARoot = Join-Path $run 'control-A'
    [IO.Directory]::CreateDirectory($controlARoot) | Out-Null
    $sharedIsolationRoot = Join-Path $run 'shared-isolation-roots'
    [IO.Directory]::CreateDirectory($sharedIsolationRoot) | Out-Null
    $controlAContext = Initialize-Control 'A' $controlARoot $sharedIsolationRoot
    $controlBRoot = Join-Path $run 'control-B'
    [IO.Directory]::CreateDirectory($controlBRoot) | Out-Null
    $controlBContext = Initialize-Control 'B' $controlBRoot $sharedIsolationRoot
    $script:evidence.path_isolation = 'PASS'
    Save-Evidence

    $controlA = Invoke-ControlAndCollect $controlAContext $expectedAgentIds
    if ([string]$controlA.failure -match '^OPENCODE_GLOBAL_ISOLATION_LEAK:') {
        $script:evidence.path_isolation = 'FAIL'
        $script:evidence.real_profile_paths_observed = @($controlA.real_profile_paths_observed)
        $script:evidence.classification = 'BLOCKED_ISOLATION'
        $script:evidence.failure = [string]$controlA.failure
        Save-Evidence
        throw [string]$controlA.failure
    }

    # A is completely stopped and its result collected before the independent B.
    $controlB = Invoke-ControlAndCollect $controlBContext $expectedAgentIds

    if ([string]$controlB.failure -match '^OPENCODE_GLOBAL_ISOLATION_LEAK:') {
        $script:evidence.path_isolation = 'FAIL'
        $script:evidence.real_profile_paths_observed = @($controlB.real_profile_paths_observed)
        $script:evidence.classification = 'BLOCKED_ISOLATION'
        $script:evidence.failure = [string]$controlB.failure
        Save-Evidence
        throw [string]$controlB.failure
    }

    $aPass = $controlA.status -eq 'PASS'
    $bPass = $controlB.status -eq 'PASS'
    $requiredVisibleIds = @($expectedAgentIds | Where-Object { $_ -ine 'aegis' })
    $aLowerIds = @($controlA.api_agent_ids | ForEach-Object { ([string]$_).ToLowerInvariant() })
    $bLowerIds = @($controlB.api_agent_ids | ForEach-Object { ([string]$_).ToLowerInvariant() })
    $aMissingIds = @($requiredVisibleIds | Where-Object { $_.ToLowerInvariant() -notin $aLowerIds })
    $bMissingIds = @($requiredVisibleIds | Where-Object { $_.ToLowerInvariant() -notin $bLowerIds })
    $profileFreeBoth = (@($controlA.real_profile_paths_observed).Count -eq 0 -and @($controlB.real_profile_paths_observed).Count -eq 0)
    $apiContextValidBoth = ($controlA.api_status -eq 200 -and $controlB.api_status -eq 200 -and
        $controlA.api_context_directory -ieq [IO.Path]::GetFullPath($controlAContext.Fixture) -and
        $controlB.api_context_directory -ieq [IO.Path]::GetFullPath($controlBContext.Fixture))
    $reproducibleGlobalRosterGap = ($script:evidence.path_isolation -eq 'PASS' -and $profileFreeBoth -and
        $apiContextValidBoth -and $aMissingIds.Count -gt 0 -and $bMissingIds.Count -gt 0 -and
        -not $controlA.minimal_probe_visible -and -not $controlB.minimal_probe_visible)
    $script:evidence.runtime_result = if ($aPass -and $bPass) { 'SUPPORTED' }
        elseif ($reproducibleGlobalRosterGap) { 'GAP' }
        else { 'PARTIAL' }
    $script:evidence.classification = $script:evidence.runtime_result
    $script:evidence.failure = if ($aPass -and $bPass) { $null }
        else { "CONTROL_A=$($controlA.status): $($controlA.failure); CONTROL_B=$($controlB.status): $($controlB.failure)" }
    Save-Evidence
    $completed = $aPass -and $bPass
    Write-Output 'OPENCODE_GLOBAL_PATH_ISOLATION: PASS'
    if ($aPass -and $bPass) {
        Write-Output 'OPENCODE_GLOBAL_RUNTIME_DISCOVERY: SUPPORTED (A custom config layer plus isolated HOME and XDG roots; B true XDG global config with OPENCODE_CONFIG_DIR unset; dedicated owned server PIDs; GET /api/agent with clean fixture; no model execution)'
    } elseif ($reproducibleGlobalRosterGap) {
        Write-Output "OPENCODE_GLOBAL_RUNTIME_DISCOVERY: GAP (A missing=$($aMissingIds -join ','); B missing=$($bMissingIds -join ','); minimal probes absent; API context valid; no real-profile paths)"
        $exitCode = 1
    } else {
        Write-Output "OPENCODE_GLOBAL_RUNTIME_DISCOVERY: PARTIAL ($($script:evidence.classification))"
        $exitCode = 1
    }
    Write-Output "GLOBAL_RUNTIME_EVIDENCE: $run"
} catch {
    $script:evidence.failure = $_.Exception.Message
    if ($_.Exception.Message -match 'BLOCKED_ISOLATION|OPENCODE_GLOBAL_ISOLATION_LEAK') {
        $script:evidence.path_isolation = 'FAIL'
        $script:evidence.classification = 'BLOCKED_ISOLATION'
    } elseif ($script:evidence.classification -eq 'IN_PROGRESS') {
        $script:evidence.classification = if ($_.Exception.Message -match 'CONTROL_A|GLOBAL_RUNTIME_A_|CONTROL_A_FAILED') { 'CONTROL_A_FAILED' }
            elseif ($_.Exception.Message -match 'CONTROL_B|GLOBAL_RUNTIME_B_|CONTROL_B_FAILED') { 'CONTROL_A_PASS_CONTROL_B_FAILED' }
            else { 'FAILED' }
    }
    Save-Evidence
    Write-Output "OPENCODE_GLOBAL_PATH_ISOLATION: $($script:evidence.path_isolation)"
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output "GLOBAL_RUNTIME_EVIDENCE: $run"
    Write-Output "GLOBAL_RUNTIME_QUALIFICATION: $($script:evidence.classification)"
    exit 1
} finally {
    # Keep the validated evidence and redacted logs for review. Remove the
    # approved-temp recovery receipt only after every planned process is terminal or
    # never started; otherwise preserve it for safe reconciliation.
    if (Test-Path -LiteralPath $receiptPath) {
        $receiptState = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json -Depth 30
        $unresolvedProcesses = @($receiptState.processes | Where-Object { $_.status -notin @('PLANNED','TERMINAL_COLLECTED') })
        if ($unresolvedProcesses.Count -eq 0) { Remove-Item -LiteralPath $receiptPath -Force }
        else { Write-Output "RECOVERY_RECEIPT_RETAINED: $receiptPath" }
    }
}
exit $exitCode
