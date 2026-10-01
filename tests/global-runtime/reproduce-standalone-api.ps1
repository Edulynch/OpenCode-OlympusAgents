# Historical failure reproducer for `opencode api --standalone`; the maintained
# qualification starts and owns its own `opencode serve` process.
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
$utf8 = [Text.UTF8Encoding]::new($false)
$completed = $false
$exitCode = 0
$savedEnvironment = @{}
$environmentKeys = @(
    'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA', 'LOCALAPPDATA',
    'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME',
    'TMP', 'TEMP', 'OPENCODE_CONFIG_DIR', 'OLYMPUS_GLOBAL_RUNTIME_RUN_ID'
)
$evidence = [ordered]@{
    task_run_id = $runId
    started_at = (Get-Date).ToString('o')
    source_root = $source
    run_root = $run
    classification = 'IN_PROGRESS'
    cli = $null
    cli_version = $null
    global_config_root = $null
    fixture_root = $null
    installer_exit_code = $null
    api_exit_code = $null
    discovered_agent_ids = @()
    expected_agent_ids = @()
    profile_leaks = @()
    blocker = $null
    failure = $null
}

function Save-Evidence {
    if (Test-Path -LiteralPath $run -PathType Container) {
        $evidence.updated_at = (Get-Date).ToString('o')
        [IO.File]::WriteAllText($evidencePath, ($evidence | ConvertTo-Json -Depth 20), $utf8)
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
    if ($command.CommandType -eq [Management.Automation.CommandTypes]::Application -and
        [IO.Path]::GetExtension($command.Source) -ieq '.exe') {
        return $command.Source
    }
    if ([IO.Path]::GetExtension($command.Source) -ieq '.ps1') {
        $wrapperRoot = Split-Path -Parent $command.Source
        $bundledExe = Join-Path $wrapperRoot 'node_modules/@opencode/cli/bin/opencode.exe'
        if (Test-Path -LiteralPath $bundledExe -PathType Leaf) { return $bundledExe }
    }
    throw 'OPENCODE_EXECUTABLE_UNRESOLVED: Could not resolve the installed OpenCode executable without a shell wrapper.'
}

function Get-ProfileLeakEvidence([string]$Text, [string[]]$ProtectedPaths, [string[]]$ProfileRoots) {
    $normalizedText = $Text.Replace('\\', '\').Replace('/', '\')
    $leaks = [System.Collections.Generic.List[string]]::new()
    foreach ($path in $ProtectedPaths) {
        if (-not $path) { continue }
        $normalizedPath = [IO.Path]::GetFullPath($path).TrimEnd([char[]]@('\','/')).Replace('/', '\')
        if ($normalizedText.IndexOf($normalizedPath, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $leaks.Add($normalizedPath)
        }
    }
    foreach ($profileRoot in $ProfileRoots) {
        if (-not $profileRoot) { continue }
        $normalizedRoot = [IO.Path]::GetFullPath($profileRoot).TrimEnd([char[]]@('\','/')).Replace('/', '\')
        $rootPattern = [regex]::Escape($normalizedRoot)
        $homePattern = '(?im)^.*\b(?:home|userprofile|user profile|profile directory)\b[^\r\n]{0,80}' +
            $rootPattern + '(?:[\\/\s]|$).*$'
        if ($normalizedText -match $homePattern) {
            $leaks.Add("profile/home field references $normalizedRoot")
        }
    }
    return @($leaks | Sort-Object -Unique)
}

function Get-ProjectStatus([string]$Target) {
    $git = Get-Command git -CommandType Application -ErrorAction Stop
    $status = @(& $git.Source -C $Target status --porcelain --untracked-files=all 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "FIXTURE_GIT_STATUS_FAILED: $($status -join "`n")" }
    return ($status -join "`n").Trim()
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'PLATFORM_UNQUALIFIED: OpenCode global runtime qualification requires Windows.'
    }
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw 'POWERSHELL_UNQUALIFIED: Run this qualification under PowerShell 7.'
    }
    [IO.Directory]::CreateDirectory($tempRoot) | Out-Null
    [IO.Directory]::CreateDirectory($run) | Out-Null

    $pwsh = Get-Command pwsh -CommandType Application -ErrorAction Stop
    $openCodeExecutable = Get-OpenCodeExecutable
    $profileRoot = Join-Path $run 'isolated-profile'
    $configRoot = Join-Path $run 'opencode-config'
    $isolatedTemp = Join-Path $run 'temp'
    $fixture = Join-Path $run 'trusted-fixture'
    foreach ($directory in @($profileRoot, $configRoot, $isolatedTemp, $fixture)) {
        [IO.Directory]::CreateDirectory($directory) | Out-Null
    }
    $profileDrive = [IO.Path]::GetPathRoot($profileRoot).TrimEnd('\')
    $profileRemainder = $profileRoot.Substring($profileDrive.Length)
    $isolatedEnvironment = @{
        HOME = $profileRoot
        USERPROFILE = $profileRoot
        HOMEDRIVE = $profileDrive
        HOMEPATH = $profileRemainder
        APPDATA = (Join-Path $profileRoot 'AppData/Roaming')
        LOCALAPPDATA = (Join-Path $profileRoot 'AppData/Local')
        XDG_CONFIG_HOME = (Join-Path $profileRoot '.config')
        XDG_DATA_HOME = (Join-Path $profileRoot '.local/share')
        XDG_STATE_HOME = (Join-Path $profileRoot '.local/state')
        XDG_CACHE_HOME = (Join-Path $profileRoot '.cache')
        TMP = $isolatedTemp
        TEMP = $isolatedTemp
        OPENCODE_CONFIG_DIR = $configRoot
        OLYMPUS_GLOBAL_RUNTIME_RUN_ID = $runId
    }
    foreach ($key in $environmentKeys) {
        $value = [Environment]::GetEnvironmentVariable($key, 'Process')
        $savedEnvironment[$key] = [pscustomobject]@{ Exists = ($null -ne $value); Value = $value }
    }
    foreach ($key in $isolatedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key, [string]$isolatedEnvironment[$key], 'Process') }

    $readme = Join-Path $fixture 'README.md'
    [IO.File]::WriteAllText($readme, "Isolated global runtime discovery fixture.`n", $utf8)
    $readmeHash = (Get-FileHash -LiteralPath $readme -Algorithm SHA256).Hash
    & git -C $fixture init --quiet
    if ($LASTEXITCODE -ne 0) { throw 'FIXTURE_GIT_INIT_FAILED' }
    $fixtureStatusBefore = Get-ProjectStatus $fixture

    $userConfig = Join-Path $configRoot 'opencode.json'
    [IO.File]::WriteAllText($userConfig, '{"theme":"system","qualification_user_owned":true}' + "`n", $utf8)
    $userConfigHash = (Get-FileHash -LiteralPath $userConfig -Algorithm SHA256).Hash

    $expectedAgentIds = @(Get-ChildItem -LiteralPath (Join-Path $source '.opencode/agents') -Filter '*.md' -File |
        Sort-Object Name | ForEach-Object { $_.BaseName })
    $evidence.cli = $openCodeExecutable
    $evidence.global_config_root = $configRoot
    $evidence.fixture_root = $fixture
    $evidence.expected_agent_ids = $expectedAgentIds
    Save-Evidence

    $versionStdout = Join-Path $run 'opencode-version.stdout.txt'
    $versionStderr = Join-Path $run 'opencode-version.stderr.txt'
    & $openCodeExecutable --version 1> $versionStdout 2> $versionStderr
    $versionExitCode = $LASTEXITCODE
    $cliVersion = (([IO.File]::ReadAllText($versionStdout) + [IO.File]::ReadAllText($versionStderr)).Trim())
    $evidence.cli_version = $cliVersion
    Check 'GLOBAL_RUNTIME_OPENCODE_CLI_AVAILABLE' ($versionExitCode -eq 0 -and $cliVersion)

    $installerStdout = Join-Path $run 'installer.stdout.txt'
    $installerStderr = Join-Path $run 'installer.stderr.txt'
    $installerArgs = @('-NoProfile', '-File', $installer, '-SourceRoot', $source, '-Target', $fixture,
        '-Scope', 'global', '-Harness', 'opencode')
    & $pwsh.Source @installerArgs 1> $installerStdout 2> $installerStderr
    $evidence.installer_exit_code = $LASTEXITCODE
    $installerText = [IO.File]::ReadAllText($installerStdout) + [IO.File]::ReadAllText($installerStderr)
    Check 'GLOBAL_RUNTIME_ISOLATED_INSTALL' ($evidence.installer_exit_code -eq 0 -and
        $installerText -match 'OLYMPUS_GLOBAL_INSTALL: OPENCODE .* READY' -and
        (Test-Path -LiteralPath (Join-Path $configRoot 'agents/kael.md') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $configRoot 'agents/veyra.md') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $configRoot 'olympus/orchestrator-install.json') -PathType Leaf)) $installerText
    Check 'GLOBAL_RUNTIME_FIXTURE_HAS_NO_LOCAL_OLYMPUS_RESOURCES' (
        -not (Test-Path -LiteralPath (Join-Path $fixture '.opencode')) -and
        -not (Test-Path -LiteralPath (Join-Path $fixture 'opencode.jsonc')) -and
        -not (Test-Path -LiteralPath (Join-Path $fixture '.codex')))

    $apiStdout = Join-Path $run 'agent-list.stdout.txt'
    $apiStderr = Join-Path $run 'agent-list.stderr.txt'
    $apiArgs = @('api', '--standalone', '--log-level', 'debug', '--print-logs', '--param', "directory=$fixture", 'agent.list')
    [IO.File]::WriteAllText((Join-Path $run 'agent-list.command.txt'),
        ($openCodeExecutable + ' ' + ($apiArgs -join ' ')), $utf8)
    $originalLocation = (Get-Location).Path
    try {
        Set-Location -LiteralPath $fixture
        & $openCodeExecutable @apiArgs 1> $apiStdout 2> $apiStderr
        $evidence.api_exit_code = $LASTEXITCODE
    } finally { Set-Location -LiteralPath $originalLocation }
    $apiResponse = [IO.File]::ReadAllText($apiStdout)
    $apiLogs = [IO.File]::ReadAllText($apiStderr)
    $combinedRuntimeEvidence = $apiResponse + "`n" + $apiLogs

    $actualProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    $knownFolders = @(
        $actualProfile,
        [Environment]::GetFolderPath([Environment+SpecialFolder]::ApplicationData),
        [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    ) | Where-Object { $_ }
    $protectedProfilePaths = [System.Collections.Generic.List[string]]::new()
    foreach ($root in $knownFolders) {
        foreach ($relative in @('.opencode', '.claude/skills', '.agents/skills', '.config/opencode',
            '.local/share/opencode', '.local/state/opencode', '.cache/opencode', '.codex')) {
            $protectedProfilePaths.Add((Join-Path $root $relative))
        }
    }
    $profileRoots = @($actualProfile, $savedEnvironment['USERPROFILE'].Value, $savedEnvironment['HOME'].Value) |
        Where-Object { $_ } | Sort-Object -Unique
    $profileLeaks = @(Get-ProfileLeakEvidence $combinedRuntimeEvidence @($protectedProfilePaths) $profileRoots)
    $evidence.profile_leaks = $profileLeaks
    if ($profileLeaks.Count -gt 0) {
        $evidence.classification = 'PARTIAL'
        $evidence.blocker = 'The standalone server subscribed to real user-profile config/skill paths despite isolated HOME/USERPROFILE values; runtime isolation is unproven.'
    }
    Save-Evidence

    if ($evidence.api_exit_code -ne 0 -or -not $apiResponse.Trim()) {
        $evidence.classification = 'PARTIAL'
        $evidence.blocker = 'The standalone agent.list query did not return a successful response; runtime discovery was not demonstrated.'
        Save-Evidence
        throw "GLOBAL_RUNTIME_DISCOVERY_PARTIAL: standalone agent.list failed or returned no response (exit=$($evidence.api_exit_code))."
    }
    Check 'GLOBAL_RUNTIME_STANDALONE_AGENT_LIST' $true
    try { $apiObject = ConvertFrom-Json -InputObject $apiResponse -AsHashtable -Depth 100 }
    catch {
        $evidence.classification = 'PARTIAL'
        $evidence.blocker = 'The standalone agent.list response was not parseable JSON; runtime discovery was not demonstrated.'
        Save-Evidence
        throw ('GLOBAL_RUNTIME_DISCOVERY_PARTIAL: agent.list response is not JSON: ' + $_.Exception.Message)
    }
    if ($apiObject -is [System.Collections.IDictionary] -and $apiObject.Contains('data')) {
        $agents = @($apiObject['data'])
    } elseif ($apiObject -is [System.Collections.IDictionary] -and $apiObject.Contains('agents')) {
        $agents = @($apiObject['agents'])
    } else { $agents = @($apiObject) }
    $discoveredAgentIds = @($agents | ForEach-Object {
        if ($_ -is [System.Collections.IDictionary]) {
            if ($_.Contains('id')) { [string]$_['id'] }
            elseif ($_.Contains('name')) { [string]$_['name'] }
        } elseif ($null -ne $_.id) { [string]$_.id }
        elseif ($null -ne $_.name) { [string]$_.name }
    } | Where-Object { $_ } | Sort-Object -Unique)
    $evidence.discovered_agent_ids = $discoveredAgentIds
    Save-Evidence

    Check 'GLOBAL_RUNTIME_USER_CONFIG_UNCHANGED' ((Get-FileHash -LiteralPath $userConfig -Algorithm SHA256).Hash -eq $userConfigHash)
    Check 'GLOBAL_RUNTIME_FIXTURE_UNCHANGED' ((Get-ProjectStatus $fixture) -ceq $fixtureStatusBefore -and
        (Get-FileHash -LiteralPath $readme -Algorithm SHA256).Hash -eq $readmeHash)

    if ($profileLeaks.Count -gt 0) {
        Save-Evidence
        throw ('GLOBAL_RUNTIME_DISCOVERY_PARTIAL: profile leakage detected (' + ($profileLeaks -join '; ') +
            "); standalone agent.list returned $($discoveredAgentIds.Count) agent(s).")
    }
    Check 'GLOBAL_RUNTIME_NO_HOME_OR_PROFILE_LEAKAGE' $true

    if ($evidence.api_exit_code -ne 0 -or @($discoveredAgentIds | Where-Object { $_ -notin $expectedAgentIds }).Count -gt 0) {
        $evidence.classification = 'PARTIAL'
        $evidence.blocker = 'The standalone agent.list call failed or returned an unexpected response; installed global resource discovery is unproven.'
        Save-Evidence
        throw "GLOBAL_RUNTIME_DISCOVERY_PARTIAL: agent.list returned an error or unexpected agent IDs: $($discoveredAgentIds -join ',')"
    }
    $missingAgentIds = @($expectedAgentIds | Where-Object { $_ -notin $discoveredAgentIds })
    if ($missingAgentIds.Count -gt 0) {
        $evidence.classification = 'PARTIAL'
        $evidence.blocker = 'The isolated standalone agent.list roster omitted one or more installed Olympus global custom agents.'
        Save-Evidence
        throw "GLOBAL_RUNTIME_DISCOVERY_PARTIAL: global agent.list omitted expected Olympus agents: $($missingAgentIds -join ',')"
    }

    Check 'GLOBAL_RUNTIME_ALL_GLOBAL_AGENTS_DISCOVERED' ($expectedAgentIds.Count -eq 12 -and
        @($discoveredAgentIds | Where-Object { $_ -in $expectedAgentIds }).Count -eq $expectedAgentIds.Count)
    $evidence.classification = 'PASS'
    $evidence.blocker = $null
    Save-Evidence
    Write-Output 'GLOBAL_RUNTIME_DISCOVERY: PASS (standalone agent.list discovered all 12 isolated global Olympus agents; no model execution)'
    $completed = $true
} catch {
    $exitCode = 1
    if (-not $evidence.failure) { $evidence.failure = $_.Exception.Message }
    if ($evidence.classification -eq 'IN_PROGRESS') {
        $evidence.classification = if ($_.Exception.Message -match 'GLOBAL_RUNTIME_DISCOVERY_PARTIAL') { 'PARTIAL' } else { 'FAILED' }
    }
    Save-Evidence
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    if ($evidence.classification -eq 'PARTIAL') {
        Write-Output ('GLOBAL_RUNTIME_DISCOVERY: PARTIAL (' + [string]$evidence.blocker + ')')
    } else { Write-Output 'GLOBAL RUNTIME QUALIFICATION: FAIL' }
    Write-Output "GLOBAL_RUNTIME_EVIDENCE: $run"
} finally {
    foreach ($key in $environmentKeys) {
        $saved = $savedEnvironment[$key]
        if ($null -eq $saved) { continue }
        if ($saved.Exists) { [Environment]::SetEnvironmentVariable($key, $saved.Value, 'Process') }
        else { [Environment]::SetEnvironmentVariable($key, $null, 'Process') }
    }
    if ($completed -and (Test-Path -LiteralPath $run -PathType Container)) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop; break }
            catch {
                if ($attempt -eq 10) { Write-Output "CLEANUP_DEFERRED: $run"; break }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}
exit $exitCode
