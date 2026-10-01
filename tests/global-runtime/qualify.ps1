[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$tempRoot = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode'
$runId = [guid]::NewGuid().ToString('N')
$run = Join-Path $tempRoot ('olympus-global-runtime-' + $runId)
$evidencePath = Join-Path $run 'evidence.json'
$receiptPath = Join-Path $run 'recovery-receipt.json'
$utf8 = [Text.UTF8Encoding]::new($false)
$completed = $false
$exitCode = 0
$script:receipt = [ordered]@{ task_run_id=$runId; owner_marker="olympus-global-runtime:$runId"; processes=@() }
$script:evidence = [ordered]@{
    task_run_id = $runId
    started_at = (Get-Date).ToString('o')
    source_root = $source
    run_root = $run
    qualification = 'owned standalone OpenCode serve processes; direct GET /api/agent with directory context'
    cli = $null
    cli_version = $null
    expected_agent_ids = @()
    controls = [ordered]@{ A=$null; B=$null }
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
    $paths = @{
        HOME=$isolatedHome
        USERPROFILE=$isolatedHome
        HOMEDRIVE=[IO.Path]::GetPathRoot($isolatedHome).TrimEnd('\')
        HOMEPATH=$isolatedHome.Substring([IO.Path]::GetPathRoot($isolatedHome).TrimEnd('\').Length)
        APPDATA=(Join-Path $isolatedHome 'AppData/Roaming')
        LOCALAPPDATA=(Join-Path $isolatedHome 'AppData/Local')
        XDG_CONFIG_HOME=(Join-Path $isolatedHome '.config')
        XDG_DATA_HOME=(Join-Path $isolatedHome '.local/share')
        XDG_STATE_HOME=(Join-Path $isolatedHome '.local/state')
        XDG_CACHE_HOME=(Join-Path $isolatedHome '.cache')
        TMP=$isolatedTemp
        TEMP=$isolatedTemp
        OLYMPUS_GLOBAL_RUNTIME_RUN_ID=$runId
        OLYMPUS_GLOBAL_RUNTIME_CONTROL=$ControlName
    }
    foreach ($path in @($isolatedHome,$isolatedTemp,$paths.APPDATA,$paths.LOCALAPPDATA,$paths.XDG_CONFIG_HOME,
        $paths.XDG_DATA_HOME,$paths.XDG_STATE_HOME,$paths.XDG_CACHE_HOME)) {
        [IO.Directory]::CreateDirectory($path) | Out-Null
    }
    foreach ($key in @('OPENCODE_CONFIG_DIR','OPENCODE_DATA_DIR','OPENCODE_STATE_DIR','OPENCODE_CACHE_DIR',
        'OPENCODE_SERVER_PASSWORD','OPENCODE_SERVER_USERNAME')) {
        [void]$StartInfo.Environment.Remove($key)
    }
    foreach ($key in $paths.Keys) { $StartInfo.Environment[$key] = [string]$paths[$key] }
    if ($ConfigRoot) { $StartInfo.Environment['OPENCODE_CONFIG_DIR'] = [IO.Path]::GetFullPath($ConfigRoot) }
    return [pscustomobject]@{ home=$isolatedHome; temp=$isolatedTemp; config_dir=$ConfigRoot }
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

function Get-ConfigPath([string]$Text) {
    $matches = @($Text -split "`r?`n" | ForEach-Object {
        $match = [regex]::Match([string]$_, '^\s*config\s{2,}(?<path>.+?)\s*$')
        if ($match.Success) { [IO.Path]::GetFullPath($match.Groups['path'].Value.Trim()) }
    } | Where-Object { $_ })
    if ($matches.Count -ne 1) { throw "OPENCODE_PATH_DISCOVERY_FAILED: expected one absolute config path, found $($matches.Count).`n$Text" }
    return $matches[0]
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
    $normalizedText = $Text.Replace('\\','\').Replace('/','\')
    $actualProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    $knownFolders = @($actualProfile,
        [Environment]::GetFolderPath([Environment+SpecialFolder]::ApplicationData),
        [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) | Where-Object { $_ } | Sort-Object -Unique
    $leaks = [System.Collections.Generic.List[string]]::new()
    foreach ($rootPath in $knownFolders) {
        foreach ($relative in @('.opencode','.claude/skills','.agents/skills','.config/opencode',
            '.local/share/opencode','.local/state/opencode','.cache/opencode','.codex')) {
            $full = [IO.Path]::GetFullPath((Join-Path $rootPath $relative)).TrimEnd([char[]]@('\','/')).Replace('/','\')
            if ($normalizedText.IndexOf($full,[StringComparison]::OrdinalIgnoreCase) -ge 0) { $leaks.Add($full) }
        }
    }
    return @($leaks | Sort-Object -Unique)
}

function Get-FreeLoopbackPort {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
    try { $listener.Start(); return ([Net.IPEndPoint]$listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

function Get-ServerIdentity($Process, $Record) {
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
    if ([string]$actual.CommandLine -notlike "*$($Record.command_marker)*") {
        throw 'OWNED_SERVER_IDENTITY_MISMATCH: exact serve arguments are absent from the command line.'
    }
    $listenerConnections = @(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort ([int]$Record.port) -State Listen -ErrorAction SilentlyContinue)
    $listenerPids = @($listenerConnections | ForEach-Object { [int]$_.OwningProcess } | Sort-Object -Unique)
    if ($listenerPids.Count -ne 1 -or $listenerPids[0] -ne [int]$Record.pid) {
        throw "OWNED_SERVER_IDENTITY_MISMATCH: endpoint listener PID(s) '$($listenerPids -join ',')' do not match launched PID $($Record.pid)."
    }
    return [pscustomobject]@{ pid=[int]$actual.ProcessId; executable=[string]$actual.ExecutablePath; command_line=[string]$actual.CommandLine; listener_pid=$listenerPids[0]; process_start_utc=$actualStart }
}

function Stop-OwnedServer($Process, $Record, $StdoutTask, $StderrTask) {
    if ($null -eq $Process) { return [pscustomobject]@{ stdout=''; stderr=''; exit_code=$null } }
    $Process.Refresh()
    if (-not $Process.HasExited) {
        # Recheck exact PID, start time, executable, parent, command line and
        # unique endpoint immediately before stopping this owned server.
        $identity = Get-ServerIdentity $Process $Record
        $Record.cleanup_identity = $identity
        $Process.Kill($false)
        if (-not $Process.WaitForExit(15000)) { throw "OWNED_SERVER_CLEANUP_BLOCKED: exact PID $($Record.pid) did not exit after termination." }
    }
    $Process.WaitForExit()
    $Process.Refresh()
    $Record.exit_code = $Process.ExitCode
    $Record.stopped_at = (Get-Date).ToString('o')
    $stdout = $StdoutTask.GetAwaiter().GetResult()
    $stderr = $StderrTask.GetAwaiter().GetResult()
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

function Invoke-Control([ValidateSet('A','B')][string]$Name, [string]$ControlRoot, [string[]]$ExpectedAgentIds) {
    $fixture = Join-Path $ControlRoot 'trusted-fixture'
    $isolatedHome = Join-Path $ControlRoot 'home'
    $configRoot = if ($Name -eq 'A') { Join-Path $ControlRoot 'explicit-config' } else { $null }
    $expectedConfigRoot = if ($Name -eq 'A') { [IO.Path]::GetFullPath($configRoot) } else { [IO.Path]::GetFullPath((Join-Path $isolatedHome '.config/opencode')) }
    foreach ($directory in @($fixture,$isolatedHome,(Join-Path $ControlRoot 'temp'),
        (Join-Path $isolatedHome 'AppData/Roaming'),(Join-Path $isolatedHome 'AppData/Local'),(Join-Path $isolatedHome '.config'),
        (Join-Path $isolatedHome '.local/share'),(Join-Path $isolatedHome '.local/state'),(Join-Path $isolatedHome '.cache'))) {
        [IO.Directory]::CreateDirectory($directory) | Out-Null
    }
    if ($Name -eq 'A') {
        foreach ($directory in @((Join-Path $configRoot 'agents'),(Join-Path $configRoot 'commands'),(Join-Path $configRoot 'plugins'))) {
            [IO.Directory]::CreateDirectory($directory) | Out-Null
        }
        [IO.File]::WriteAllText((Join-Path $configRoot 'opencode.json'),'{}' + "`n",$utf8)
    }
    [IO.File]::WriteAllText((Join-Path $fixture 'README.md'),"Isolated global runtime discovery fixture ($Name).`n",$utf8)
    & git -C $fixture init --quiet
    if ($LASTEXITCODE -ne 0) { throw "FIXTURE_GIT_INIT_FAILED: control $Name" }
    $fixtureStatusBefore = Get-ProjectStatus $fixture
    $userConfigPath = if ($Name -eq 'A') { Join-Path $configRoot 'opencode.json' } else { $null }
    $userConfigHash = if ($userConfigPath) { (Get-FileHash -LiteralPath $userConfigPath -Algorithm SHA256).Hash } else { $null }

    $control = [ordered]@{
        control=$Name
        status='IN_PROGRESS'
        environment=[ordered]@{ home=$isolatedHome; config_directory=$expectedConfigRoot; fixture=$fixture; temp=(Join-Path $ControlRoot 'temp'); OPENCODE_CONFIG_DIR=$(if ($Name -eq 'A') { $expectedConfigRoot } else { $null }) }
        installer_exit_code=$null
        installer_output=$null
        verifyonly_exit_code=$null
        fixture_no_project_local_olympus=$false
        runtime_process=$null
        endpoint=$null
        api_status=$null
        api_request=$null
        api_context_directory=$null
        api_agent_ids=@()
        origin_probe_id=$null
        origin_probe_description=$null
        origin_probe_visible=$false
        real_profile_paths_observed=@()
        failure=$null
    }
    $script:evidence.controls[$Name] = $control
    Save-Evidence

    if ($Name -eq 'B') {
        $pathProbe = Invoke-CapturedProcess $script:evidence.cli @('debug','paths') $fixture $ControlRoot $null $Name
        Check 'GLOBAL_RUNTIME_B_ISOLATED_HOME_PATH_PROBE' ($pathProbe.ExitCode -eq 0)
        $resolvedByCli = Get-ConfigPath ($pathProbe.Stdout + $pathProbe.Stderr)
        $control.cli_resolved_config_directory = $resolvedByCli
        Check 'GLOBAL_RUNTIME_B_CLI_ROOTS_UNDER_ISOLATED_HOME' ($resolvedByCli -ieq $expectedConfigRoot) (
            "Expected isolated root $expectedConfigRoot but opencode debug paths resolved $resolvedByCli.`n$($pathProbe.Stdout)$($pathProbe.Stderr)")
    }

    $installArguments = @('-NoLogo','-NoProfile','-File',$installer,'-SourceRoot',$source,'-Target',$fixture,
        '-Scope','global','-Harness','opencode')
    $install = Invoke-CapturedProcess $script:evidence.pwsh $installArguments $fixture $ControlRoot $configRoot $Name
    $control.installer_exit_code = $install.ExitCode
    $control.installer_output = ($install.Stdout + $install.Stderr).Trim()
    Check "GLOBAL_RUNTIME_$($Name)_GLOBAL_INSTALL" ($install.ExitCode -eq 0 -and
        $control.installer_output -match 'OLYMPUS_GLOBAL_INSTALL: OPENCODE .* READY' -and
        (Test-Path -LiteralPath (Join-Path $expectedConfigRoot 'agents/kael.md') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $expectedConfigRoot 'olympus/orchestrator-install.json') -PathType Leaf)) $control.installer_output
    if ($Name -eq 'A') {
        Check 'GLOBAL_RUNTIME_A_COMPLETE_OPEN_CODE_LAYOUT' ((Test-Path (Join-Path $expectedConfigRoot 'agents/veyra.md')) -and
            (Test-Path (Join-Path $expectedConfigRoot 'commands/maintain.md')) -and
            (Test-Path (Join-Path $expectedConfigRoot 'plugins/olympus-activity/activity.ts')))
    }
    $control.fixture_no_project_local_olympus = (-not (Test-Path (Join-Path $fixture '.opencode')) -and
        -not (Test-Path (Join-Path $fixture 'opencode.jsonc')) -and -not (Test-Path (Join-Path $fixture '.codex')))
    Check "GLOBAL_RUNTIME_$($Name)_NO_PROJECT_LOCAL_FALLBACK" ([bool]$control.fixture_no_project_local_olympus)

    $globalSnapshotBeforeVerify = Get-TreeSnapshot $expectedConfigRoot
    $fixtureSnapshotBeforeVerify = Get-TreeSnapshot $fixture
    $verifyArguments = @('-NoLogo','-NoProfile','-File',$installer,'-SourceRoot',$source,'-Target',$fixture,
        '-Scope','global','-Harness','opencode','-VerifyOnly')
    $verify = Invoke-CapturedProcess $script:evidence.pwsh $verifyArguments $fixture $ControlRoot $configRoot $Name
    $control.verifyonly_exit_code = $verify.ExitCode
    $globalSnapshotAfterVerify = Get-TreeSnapshot $expectedConfigRoot
    $fixtureSnapshotAfterVerify = Get-TreeSnapshot $fixture
    Check "GLOBAL_RUNTIME_$($Name)_VERIFYONLY_READ_ONLY" ($verify.ExitCode -eq 0 -and
        ($verify.Stdout + $verify.Stderr) -match 'OLYMPUS_GLOBAL_VERIFY: opencode' -and
        $globalSnapshotAfterVerify -ceq $globalSnapshotBeforeVerify -and
        $fixtureSnapshotAfterVerify -ceq $fixtureSnapshotBeforeVerify -and
        (Get-ProjectStatus $fixture) -ceq $fixtureStatusBefore -and
        (-not $userConfigPath -or (Get-FileHash -LiteralPath $userConfigPath -Algorithm SHA256).Hash -ceq $userConfigHash))

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
    [void](Set-IsolatedEnvironment $startInfo $ControlRoot $configRoot $Name)
    $serverPassword = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $startInfo.Environment['OPENCODE_SERVER_PASSWORD'] = $serverPassword
    $server = [Diagnostics.Process]::new()
    $server.StartInfo = $startInfo
    $serverStarted = $false
    $stdoutTask = $null
    $stderrTask = $null
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
        $stdoutTask = $server.StandardOutput.ReadToEndAsync()
        $stderrTask = $server.StandardError.ReadToEndAsync()
        $deadline = [DateTime]::UtcNow.AddSeconds(45)
        $identity = $null
        while ([DateTime]::UtcNow -lt $deadline) {
            $server.Refresh()
            if ($server.HasExited) { throw "OWNED_SERVER_START_FAILED: PID $($server.Id) exited with code $($server.ExitCode)." }
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
        $httpRequest = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Get,$requestUri)
        $httpRequest.Headers.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Basic',$authorization)
        $response = $null
        $responseText = ''
        try {
            $response = $httpClient.SendAsync($httpRequest).GetAwaiter().GetResult()
            $control.api_status = [int]$response.StatusCode
            $responseText = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        } finally {
            if ($null -ne $response) { $response.Dispose() }
            $httpRequest.Dispose()
            $httpClient.Dispose()
        }
        if ($control.api_status -ne 200) { throw "AGENT_API_HTTP_FAILED: status=$($control.api_status) response=$responseText" }
        $api = ConvertFrom-Json -InputObject $responseText -AsHashtable -Depth 100
        if ($api -isnot [System.Collections.IDictionary] -or -not $api.Contains('data') -or -not $api.Contains('location')) {
            throw 'AGENT_API_RESPONSE_INVALID: expected an object with location and data fields.'
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
        $control.api_agent_ids = $agentIds
        $record.latest_progress_at = (Get-Date).ToString('o')
        $record.progress_counter = 2
        $record.progress_evidence = 'HTTP 200 GET /api/agent returned request location for fixture and parsed roster'
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
        } elseif ($server.HasExited -and $null -eq $stdoutTask) {
            $record.exit_code = $server.ExitCode
            $record.stopped_at = (Get-Date).ToString('o')
            [IO.File]::WriteAllText($stdoutPath,'',$utf8)
            [IO.File]::WriteAllText($stderrPath,'',$utf8)
            $serverOutput.exit_code = $server.ExitCode
            $server.Dispose()
            Save-Receipt
        } elseif ($null -ne $server) {
            $serverOutput = Stop-OwnedServer $server $record $stdoutTask $stderrTask
        }
    }

    $serverLogs = [IO.File]::ReadAllText($stderrPath)
    $control.real_profile_paths_observed = @(Get-ProfileLeaks ($serverLogs + "`n" + [IO.File]::ReadAllText($stdoutPath)))
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
    $lowerIds = @($control.api_agent_ids | ForEach-Object { $_.ToLowerInvariant() })
    $probeAgent = @($agents | Where-Object {
        if ($_ -is [System.Collections.IDictionary]) {
            $agentId = if ($_.Contains('id')) { [string]$_['id'] } elseif ($_.Contains('name')) { [string]$_['name'] } else { '' }
            $agentId -ieq $probeId
        } else { $false }
    } | Select-Object -First 1)
    if ($probeAgent.Count -gt 0 -and [string]$probeAgent[0].description -ceq $probeDescription) { $control.origin_probe_visible = $true }
    $checkResults.isolated_global_origin_marker = [bool]$control.origin_probe_visible
    $checkResults.roster_nonempty = [bool](@($control.api_agent_ids).Count -gt 0)
    $missingIds = @($ExpectedAgentIds | Where-Object { $_.ToLowerInvariant() -notin $lowerIds })
    $coreMissing = @(@('kael','veyra','kovan','nox','aegis') | Where-Object { $_ -notin $lowerIds })
    $checkResults.expected_olympus_roster = [bool]($missingIds.Count -eq 0 -and $coreMissing.Count -eq 0)
    $checkResults.no_project_local_fallback = [bool]$control.fixture_no_project_local_olympus
    $checkResults.verifyonly_read_only = [bool]($control.verifyonly_exit_code -eq 0)
    $control.checks = $checkResults
    $failedChecks = @($checkResults.Keys | Where-Object { -not $checkResults[$_] })
    $control.status = if ($failedChecks.Count -eq 0) { 'PASS' } else { 'FAIL' }
    if ($failedChecks.Count -gt 0) {
        $control.failure = "Failed checks: $($failedChecks -join ', '); missing Olympus IDs=$($missingIds -join ','); marker=$probeId; roster=$($control.api_agent_ids -join ',')"
    }
    Write-Output "GLOBAL_RUNTIME_$($Name)_REAL_PROFILE_PATH_OBSERVATIONS: $($control.real_profile_paths_observed -join ', ')"
    $record.status = 'TERMINAL_COLLECTED'
    Save-Receipt
    Save-Evidence
    Write-Output "CONTROL $Name $($control.status): PID=$($record.pid); endpoint=$endpoint; HOME=$isolatedHome; OPENCODE_CONFIG_DIR=$(if ($Name -eq 'A') { $expectedConfigRoot } else { '<unset; default global root>' }); global_root=$expectedConfigRoot; fixture=$fixture; roster=$($control.api_agent_ids -join ','); marker=$($control.origin_probe_visible)"
    return $control
}

function Invoke-ControlAndCollect([ValidateSet('A','B')][string]$Name, [string]$ControlRoot, [string[]]$ExpectedAgentIds) {
    # Invoke-Control emits human-readable Check/log lines as well as its result.
    # Capture the complete output, forward only text, and return only the control
    # dictionary so callers cannot mistake a log line for a result object.
    $output = @(Invoke-Control $Name $ControlRoot $ExpectedAgentIds)
    $results = @($output | Where-Object { $_ -is [System.Collections.IDictionary] })
    foreach ($line in @($output | Where-Object { $_ -is [string] })) { Write-Host $line }
    if ($results.Count -ne 1) { throw "CONTROL_RESULT_COLLECTION_FAILED: expected one control result for $Name, found $($results.Count)." }
    return $results[0]
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: OpenCode global runtime qualification requires Windows.' }
    if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'POWERSHELL_UNQUALIFIED: Run this qualification under PowerShell 7.' }
    [IO.Directory]::CreateDirectory($tempRoot) | Out-Null
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
    $controlA = Invoke-ControlAndCollect 'A' $controlARoot $expectedAgentIds

    # A is completely stopped, its response/config/logs have been collected,
    # and a V2-frontmatter marker has tested its loader before the independent B.
    $controlBRoot = Join-Path $run 'control-B'
    [IO.Directory]::CreateDirectory($controlBRoot) | Out-Null
    $controlB = Invoke-ControlAndCollect 'B' $controlBRoot $expectedAgentIds

    $aPass = $controlA.status -eq 'PASS'
    $bPass = $controlB.status -eq 'PASS'
    $script:evidence.classification = if ($aPass -and $bPass) { 'A_PASS_B_PASS' }
        elseif ($aPass -and -not $bPass) { 'A_PASS_B_FAIL' }
        elseif (-not $aPass -and $bPass) { 'A_FAIL_B_PASS' }
        else { 'A_FAIL_B_FAIL' }
    $script:evidence.failure = if ($aPass -and $bPass) { $null }
        else { "CONTROL_A=$($controlA.status): $($controlA.failure); CONTROL_B=$($controlB.status): $($controlB.failure)" }
    Save-Evidence
    $completed = $aPass -and $bPass
    if ($aPass -and $bPass) {
        Write-Output 'OPENCODE_GLOBAL_RUNTIME_DISCOVERY: PASS (A explicit OPENCODE_CONFIG_DIR; B isolated true global path; dedicated owned server PIDs; GET /api/agent with fixture directory; no model execution)'
    } elseif (-not $aPass -and $bPass) {
        Write-Output 'OPENCODE_GLOBAL_RUNTIME_DISCOVERY: PASS via B; CONTROL A failed, so OPENCODE_CONFIG_DIR precedence/custom-root behavior needs correction or explicit documentation.'
    } else {
        Write-Output "OPENCODE_GLOBAL_RUNTIME_DISCOVERY: PARTIAL ($($script:evidence.classification))"
        $exitCode = 1
    }
    Write-Output "GLOBAL_RUNTIME_EVIDENCE: $run"
} catch {
    $script:evidence.failure = $_.Exception.Message
    if ($script:evidence.classification -eq 'IN_PROGRESS') {
        $script:evidence.classification = if ($_.Exception.Message -match 'CONTROL_A|GLOBAL_RUNTIME_A_|CONTROL_A_FAILED') { 'CONTROL_A_FAILED' }
            elseif ($_.Exception.Message -match 'CONTROL_B|GLOBAL_RUNTIME_B_|CONTROL_B_FAILED') { 'CONTROL_A_PASS_CONTROL_B_FAILED' }
            else { 'FAILED' }
    }
    Save-Evidence
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output "GLOBAL_RUNTIME_EVIDENCE: $run"
    Write-Output "GLOBAL_RUNTIME_QUALIFICATION: $($script:evidence.classification)"
    exit 1
} finally {
    # The server process families are collected and stopped inside Invoke-Control.
    # Remove the recovery receipt only after result collection and classification.
    if ($completed -and (Test-Path -LiteralPath $receiptPath)) { Remove-Item -LiteralPath $receiptPath -Force }
    if ($completed -and (Test-Path -LiteralPath $run -PathType Container)) {
        for ($attempt=1; $attempt -le 10; $attempt++) {
            try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop; break }
            catch {
                if ($attempt -eq 10) { Write-Output "CLEANUP_DEFERRED: $run"; break }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}
exit $exitCode
