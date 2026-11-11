[CmdletBinding()]
param(
    [switch]$Child,
    [switch]$MockLatest,
    [string]$Action,
    [string]$Scope,
    [string]$Harness,
    [string]$Target,
    [string]$Version,
    [switch]$DryRun,
    [switch]$Update
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Utf8NoBom = [Text.UTF8Encoding]::new($false)

function Assert([string]$Name, [bool]$Condition) {
    if (-not $Condition) { throw "$Name FAIL" }
    Write-Output "$Name PASS"
}

function Invoke-PowerShell([string[]]$Arguments) {
    $output = (& $script:Pwsh -NoProfile -NonInteractive @Arguments 2>&1 | Out-String)
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "POWERSHELL_FAILED: exit=$code`n$output" }
    return $output
}

function Invoke-Olympus([string]$Name, [string[]]$CommandArguments, [string]$Expected) {
    $output = (& olympus @CommandArguments 2>&1 | Out-String)
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "CLI_FAILED: $Name exit=$code`n$output" }
    if ($Expected -and $output.TrimEnd() -notmatch $Expected) { throw "CLI_OUTPUT_MISMATCH: $Name`n$output" }
    Write-Host "CLI $Name PASS"
    return $output
}

if ($MockLatest) {
    function global:Invoke-RestMethod {
        [CmdletBinding()]
        param([string]$Uri, [hashtable]$Headers)
        [IO.File]::AppendAllText($env:OLYMPUS_SMOKE_REQUEST_LOG, "metadata $Uri`n", [Text.UTF8Encoding]::new($false))
        if ($Uri -cne $env:OLYMPUS_SMOKE_METADATA_URI) { throw "Unexpected metadata request blocked: $Uri" }
        return [IO.File]::ReadAllText($env:OLYMPUS_SMOKE_METADATA_FIXTURE) | ConvertFrom-Json -Depth 20 -ErrorAction Stop
    }

    function global:Invoke-WebRequest {
        [CmdletBinding()]
        param([string]$Uri, [string]$OutFile, [hashtable]$Headers)
        [IO.File]::AppendAllText($env:OLYMPUS_SMOKE_REQUEST_LOG, "installer $Uri`n", [Text.UTF8Encoding]::new($false))
        $expected = $env:OLYMPUS_SMOKE_RAW_BASE + '/' + $env:OLYMPUS_SMOKE_RELEASE_VERSION + '/install.ps1'
        if ($Uri -cne $expected) { throw "Unexpected installer request blocked: $Uri" }
        [IO.File]::Copy($env:OLYMPUS_SMOKE_RELEASE_INSTALLER, $OutFile, $true)
    }

    if (-not $env:OLYMPUS_SMOKE_LAUNCHER) { throw 'SMOKE_LAUNCHER_MISSING' }
    $launchArguments = @{}
    foreach ($name in @('Action', 'Scope', 'Harness', 'Target', 'Version', 'DryRun', 'Update')) {
        if ($PSBoundParameters.ContainsKey($name)) { $launchArguments[$name] = $PSBoundParameters[$name] }
    }
    & $env:OLYMPUS_SMOKE_LAUNCHER @launchArguments
    exit $LASTEXITCODE
}

if ($Child) {
    Set-Location -LiteralPath $env:OLYMPUS_SMOKE_OTHER_DIR
    Assert 'CHILD_CWD_ISOLATED' ((Get-Location).Path -ceq $env:OLYMPUS_SMOKE_OTHER_DIR)
    Assert 'ISOLATED_LAUNCHER_RESOLVES' ((Get-Command olympus -CommandType Application -ErrorAction Stop).Source -ieq $env:OLYMPUS_SMOKE_LAUNCHER_PATH)

    [void](Invoke-Olympus 'version-before-update' @('version') '^olympus v[0-9]+\.[0-9]+\.[0-9]+$')
    [void](Invoke-Olympus 'help' @('help') 'Olympus global CLI')
    [void](Invoke-Olympus 'agents-list' @('agents', 'list') 'nox \| Nox')
    [void](Invoke-Olympus 'nox-set-model' @('nox', 'set-model', 'openai/gpt-6.1-sol') 'openai/gpt-6\.1-sol')
    [void](Invoke-Olympus 'nox-set-effort' @('nox', 'set-effort', 'high') 'high')
    [void](Invoke-Olympus 'config-list' @('config', 'list') 'Run ''olympus doctor'' after manual edits\.')

    $oldPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
    $oldHook = [Environment]::GetEnvironmentVariable('OLYMPUS_SMOKE_UPDATE_HOOK', 'Process')
    try {
        $env:PYTHONPATH = $env:OLYMPUS_SMOKE_HOOK_DIR
        $env:OLYMPUS_SMOKE_UPDATE_HOOK = '1'
        [void](Invoke-Olympus 'stable-update' @('update') ("OLYMPUS_RELEASE_SELECTED: tag=" + [regex]::Escape($env:OLYMPUS_SMOKE_RELEASE_VERSION) + ' immutable=true'))
    } finally {
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $oldPythonPath, 'Process')
        [Environment]::SetEnvironmentVariable('OLYMPUS_SMOKE_UPDATE_HOOK', $oldHook, 'Process')
    }

    [void](Invoke-Olympus 'version-after-update' @('version') ("^olympus " + [regex]::Escape($env:OLYMPUS_SMOKE_RELEASE_VERSION) + '$'))
    [void](Invoke-Olympus 'agents-list-after-update' @('agents', 'list') 'openai/gpt-6\.1-sol')
    [void](Invoke-Olympus 'doctor' @('doctor') 'doctor: ok')

    try {
        $env:PYTHONPATH = $env:OLYMPUS_SMOKE_HOOK_DIR
        $env:OLYMPUS_SMOKE_UPDATE_HOOK = '1'
        [void](Invoke-Olympus 'uninstall' @('uninstall', '--scope', 'global', '--harness', 'opencode', '--execute') 'REMOVED_MANAGED_RESOURCES_ONLY')
    } finally {
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $oldPythonPath, 'Process')
        [Environment]::SetEnvironmentVariable('OLYMPUS_SMOKE_UPDATE_HOOK', $oldHook, 'Process')
    }
    Assert 'USER_OPENCODE_CONFIG_PRESERVED' (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_OPENCODE_CONFIG -PathType Leaf)
    Assert 'USER_GLOBAL_FILE_PRESERVED' (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_GLOBAL_MARKER -PathType Leaf)
    Assert 'USER_CLI_BIN_FILE_PRESERVED' (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_BIN_MARKER -PathType Leaf)
    Assert 'USER_CLI_VERSION_DIRECTORY_PRESERVED' (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_VERSION_MARKER -PathType Leaf)
    Assert 'GLOBAL_MANIFEST_UNINSTALLED' (-not (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_GLOBAL_MANIFEST))
    Assert 'CLI_CURRENT_POINTER_UNINSTALLED' (-not (Test-Path -LiteralPath (Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt')))
    Write-Output 'ISSUE128_GLOBAL_CLI_SMOKE: PASS'
    exit 0
}

$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$script:Pwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$python = (Get-Command python.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$git = (Get-Command git.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: This smoke requires Windows.' }
$powerShellVersion = & $script:Pwsh -NoProfile -Command '$PSVersionTable.PSVersion.Major'
if ($LASTEXITCODE -ne 0 -or [int]($powerShellVersion | Select-Object -Last 1) -lt 7) {
    throw 'POWERSHELL_UNQUALIFIED: PowerShell 7 is required.'
}

$identityText = [IO.File]::ReadAllText((Join-Path $source 'install.ps1'))
$defaultVersion = [regex]::Match($identityText, '(?m)^\s*\[string\]\$Version\s*=\s*''(?<version>[^'']+)''')
$releaseVersionMatch = [regex]::Match($identityText, '(?m)^\s*\$ReleaseVersion\s*=\s*''(?<version>[^'']+)''')
if (-not $defaultVersion.Success -or -not $releaseVersionMatch.Success -or
    $defaultVersion.Groups['version'].Value -cne $releaseVersionMatch.Groups['version'].Value) {
    throw 'SOURCE_VERSION_INVALID: install.ps1 release markers disagree.'
}
$sourceVersion = $defaultVersion.Groups['version'].Value
$stableVersion = [regex]::Match($sourceVersion, '^v(?<major>0|[1-9][0-9]*)\.(?<minor>0|[1-9][0-9]*)\.(?<patch>0|[1-9][0-9]*)$')
if (-not $stableVersion.Success) { throw "SOURCE_VERSION_UNSUPPORTED: $sourceVersion" }
$nextVersion = 'v{0}.{1}.{2}' -f $stableVersion.Groups['major'].Value, $stableVersion.Groups['minor'].Value,
    ([long]$stableVersion.Groups['patch'].Value + 1)

$launcherPath = Join-Path $source 'scripts/launch-latest.ps1'
$launcherText = [IO.File]::ReadAllText($launcherPath)
$apiRepo = [regex]::Match($launcherText, 'https://api\.github\.com/repos/(?<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/releases/latest')
$rawRepo = [regex]::Match($launcherText, 'https://raw\.githubusercontent\.com/(?<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/\$tag/install\.ps1')
if (-not $apiRepo.Success -or -not $rawRepo.Success -or $apiRepo.Groups['repo'].Value -cne $rawRepo.Groups['repo'].Value) {
    throw 'RELEASE_ENDPOINT_INVALID: Cannot derive matching metadata and installer fixture endpoints.'
}
$repository = $apiRepo.Groups['repo'].Value

$tempRoot = if ($env:TEMP) { [IO.Path]::GetFullPath($env:TEMP) } else { [IO.Path]::GetFullPath([IO.Path]::GetTempPath()) }
$fixtureParent = Join-Path $tempRoot 'opencode-issue128-85b307ed71504453a2e1d1e3a6327f75'
$run = Join-Path $fixtureParent ('run-' + [guid]::NewGuid().ToString('N'))
$createdParent = $false
$runCreated = $false
$environmentNames = @(
    'APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'HOME', 'OPENCODE_CONFIG_DIR', 'OLYMPUS_CONFIG_HOME',
    'OLYMPUS_CONFIG_FILE', 'CODEX_HOME', 'PYTHONDONTWRITEBYTECODE', 'OLYMPUS_SMOKE_INSTALL_ROOT',
    'OLYMPUS_SMOKE_PATH_STORE', 'OLYMPUS_SMOKE_RELEASE_VERSION', 'OLYMPUS_SMOKE_RELEASE_INSTALLER',
    'OLYMPUS_SMOKE_RELEASE_ARCHIVE', 'OLYMPUS_SMOKE_METADATA_FIXTURE', 'OLYMPUS_SMOKE_REQUEST_LOG',
    'OLYMPUS_SMOKE_METADATA_URI', 'OLYMPUS_SMOKE_RAW_BASE', 'OLYMPUS_SMOKE_ARCHIVE_URI', 'OLYMPUS_SMOKE_PWSH',
    'OLYMPUS_SMOKE_SCRIPT', 'OLYMPUS_SMOKE_HOOK_DIR', 'OLYMPUS_SMOKE_OTHER_DIR', 'OLYMPUS_SMOKE_LAUNCHER_PATH',
    'OLYMPUS_SMOKE_OPENCODE_CONFIG', 'OLYMPUS_SMOKE_GLOBAL_MARKER', 'OLYMPUS_SMOKE_BIN_MARKER',
    'OLYMPUS_SMOKE_VERSION_MARKER', 'OLYMPUS_SMOKE_GLOBAL_MANIFEST', 'OLYMPUS_SMOKE_USER_CONFIG'
)
$originalEnvironment = @{}
foreach ($name in $environmentNames) { $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$originalProcessPath = $env:PATH
$originalUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')

try {
    if (-not (Test-Path -LiteralPath $fixtureParent -PathType Container)) {
        [IO.Directory]::CreateDirectory($fixtureParent) | Out-Null
        $createdParent = $true
    }
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $runCreated = $true

    $appData = Join-Path $run 'appdata'
    $localAppData = Join-Path $run 'localappdata'
    $profile = Join-Path $run 'profile'
    $opencodeRoot = Join-Path $run 'opencode-global'
    $otherDirectory = Join-Path $run 'other-folder'
    $tempDirectory = Join-Path $run 'temp'
    $installRoot = Join-Path $localAppData 'Programs/Olympus'
    $bin = Join-Path $installRoot 'bin'
    $pathStore = Join-Path $installRoot 'path-store.txt'
    $releaseSource = Join-Path $run ("OpenCode-OlympusAgents-$nextVersion")
    $releaseArchive = Join-Path $run ("release-$nextVersion.zip")
    $metadataFixture = Join-Path $run 'release-metadata.json'
    $requestLog = Join-Path $run 'requests.log'
    $hookDirectory = Join-Path $run 'python-hook'
    $opencodeConfig = Join-Path $opencodeRoot 'opencode.jsonc'
    $globalMarker = Join-Path $opencodeRoot 'user-owned.txt'
    $binMarker = Join-Path $bin 'user-owned.cmd'
    $versionMarker = Join-Path $installRoot "versions/unmanaged/user-owned.txt"
    $manifest = Join-Path $opencodeRoot 'olympus/orchestrator-install.json'
    $userConfig = Join-Path $appData 'Olympus/config.json'

    foreach ($directory in @($appData, $localAppData, $profile, $opencodeRoot, $otherDirectory,
            $tempDirectory, $hookDirectory)) {
        [IO.Directory]::CreateDirectory($directory) | Out-Null
    }

    $env:APPDATA = $appData
    $env:LOCALAPPDATA = $localAppData
    $env:USERPROFILE = $profile
    $env:HOME = $profile
    $env:OPENCODE_CONFIG_DIR = $opencodeRoot
    $env:PYTHONDONTWRITEBYTECODE = '1'
    foreach ($name in @('OLYMPUS_CONFIG_HOME', 'OLYMPUS_CONFIG_FILE', 'CODEX_HOME')) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }

    $userOpenCodeConfig = [IO.File]::ReadAllText((Join-Path $source 'olympus/harnesses/opencode/global-permissions.jsonc'))
    [IO.File]::WriteAllText($opencodeConfig, $userOpenCodeConfig, $Utf8NoBom)
    $savedOpenCodeConfig = [IO.File]::ReadAllBytes($opencodeConfig)

    [IO.Directory]::CreateDirectory($releaseSource) | Out-Null
    $clonePaths = @('olympus', 'scripts', '.opencode', '.codex')
    foreach ($relative in $clonePaths) {
        Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $releaseSource -Recurse
    }
    Copy-Item -LiteralPath (Join-Path $source 'CODEX.md') -Destination $releaseSource
    Copy-Item -LiteralPath (Join-Path $source 'opencode.jsonc') -Destination $releaseSource
    Copy-Item -LiteralPath (Join-Path $source 'install.ps1') -Destination $releaseSource

    $fixtureInstallerPath = Join-Path $releaseSource 'install.ps1'
    $fixtureInstaller = [IO.File]::ReadAllText($fixtureInstallerPath)
    $fixtureInstaller = $fixtureInstaller.Replace("[string]`$Version = '$sourceVersion',", "[string]`$Version = '$nextVersion',")
    $fixtureInstaller = $fixtureInstaller.Replace("`$ReleaseVersion = '$sourceVersion'", "`$ReleaseVersion = '$nextVersion'")
    if ($fixtureInstaller -notmatch [regex]::Escape("[string]`$Version = '$nextVersion',") -or
        $fixtureInstaller -notmatch [regex]::Escape("`$ReleaseVersion = '$nextVersion'")) {
        throw 'FIXTURE_VERSION_PATCH_FAILED: Could not create the controlled next-version source.'
    }

    $newline = if ($fixtureInstaller.Contains("`r`n")) { "`r`n" } else { "`n" }
    $platformAnchor = '    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT)'
    $platformPosition = $fixtureInstaller.IndexOf($platformAnchor, [StringComparison]::Ordinal)
    if ($platformPosition -lt 0) { throw 'FIXTURE_SOURCE_ARCHIVE_MOCK_ANCHOR_MISSING' }
    $tryPosition = $fixtureInstaller.LastIndexOf('try {', $platformPosition, [StringComparison]::Ordinal)
    if ($tryPosition -lt 0) { throw 'FIXTURE_SOURCE_ARCHIVE_MOCK_SCOPE_MISSING' }
    $archiveMock = @'
function global:Invoke-WebRequest {
    [CmdletBinding()]
    param([string]$Uri, [string]$OutFile)
    [IO.File]::AppendAllText($env:OLYMPUS_SMOKE_REQUEST_LOG, "archive $Uri`n", [Text.UTF8Encoding]::new($false))
    if ($Uri -cne $env:OLYMPUS_SMOKE_ARCHIVE_URI) { throw "Unexpected source archive request blocked: $Uri" }
    [IO.File]::Copy($env:OLYMPUS_SMOKE_RELEASE_ARCHIVE, $OutFile, $true)
}
'@
    $archiveMock = $archiveMock.Replace("`n", $newline) + $newline
    $fixtureInstaller = $fixtureInstaller.Insert($tryPosition, $archiveMock)

    $cliAnchor = '& $pwsh.Source @cliArgs'
    if (($fixtureInstaller.Split(@($cliAnchor), [StringSplitOptions]::None).Count - 1) -ne 1) {
        throw 'FIXTURE_CLI_ISOLATION_ANCHOR_INVALID'
    }
    $cliIsolation = @'
if ($env:OLYMPUS_SMOKE_INSTALL_ROOT -and $env:OLYMPUS_SMOKE_PATH_STORE) {
    $cliArgs += @('-InstallRoot', $env:OLYMPUS_SMOKE_INSTALL_ROOT,
        '-PathStorePath', $env:OLYMPUS_SMOKE_PATH_STORE)
}
'@
    $cliIsolation = $cliIsolation.Replace("`n", $newline) + $newline + '            '
    $fixtureInstaller = $fixtureInstaller.Replace($cliAnchor, $cliIsolation + $cliAnchor)
    [IO.File]::WriteAllText($fixtureInstallerPath, $fixtureInstaller, $Utf8NoBom)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory(
        $releaseSource, $releaseArchive, [IO.Compression.CompressionLevel]::Optimal, $true
    )

    $metadata = [ordered]@{
        immutable = $true
        draft = $false
        prerelease = $false
        tag_name = $nextVersion
        published_at = [DateTimeOffset]::UtcNow.AddMinutes(-1).ToString('o')
    } | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($metadataFixture, $metadata, $Utf8NoBom)
    [IO.File]::WriteAllText($requestLog, '', $Utf8NoBom)

    $pythonHook = @'
import os
import subprocess

_real_run = subprocess.run

def _run(command, *positional, **options):
    if os.environ.get("OLYMPUS_SMOKE_UPDATE_HOOK") == "1" and isinstance(command, (list, tuple)):
        try:
            index = command.index("-File")
            launcher = str(command[index + 1])
        except (ValueError, IndexError):
            launcher = ""
        if os.path.basename(launcher).lower() == "launch-latest.ps1":
            replacement = [
                os.environ["OLYMPUS_SMOKE_PWSH"], "-NoProfile", "-NonInteractive",
                "-File", os.environ["OLYMPUS_SMOKE_SCRIPT"], "-MockLatest",
                *[str(value) for value in command[index + 2:]],
            ]
            forwarded = dict(options)
            environment = dict(forwarded.get("env") or os.environ)
            environment["OLYMPUS_SMOKE_LAUNCHER"] = launcher
            forwarded["env"] = environment
            return _real_run(replacement, *positional, **forwarded)
        if os.path.basename(launcher).lower() == "install-cli.ps1":
            command = [*command, "-InstallRoot", os.environ["OLYMPUS_SMOKE_INSTALL_ROOT"],
                       "-PathStorePath", os.environ["OLYMPUS_SMOKE_PATH_STORE"]]
    return _real_run(command, *positional, **options)

subprocess.run = _run
'@
    [IO.File]::WriteAllText((Join-Path $hookDirectory 'sitecustomize.py'), $pythonHook, $Utf8NoBom)

    $apiUri = "https://api.github.com/repos/$repository/releases/latest"
    $rawBase = "https://raw.githubusercontent.com/$repository"
    $archiveUri = "https://github.com/$repository/archive/refs/tags/$nextVersion.zip"
    $env:OLYMPUS_SMOKE_INSTALL_ROOT = $installRoot
    $env:OLYMPUS_SMOKE_PATH_STORE = $pathStore
    $env:OLYMPUS_SMOKE_RELEASE_VERSION = $nextVersion
    $env:OLYMPUS_SMOKE_RELEASE_INSTALLER = $fixtureInstallerPath
    $env:OLYMPUS_SMOKE_RELEASE_ARCHIVE = $releaseArchive
    $env:OLYMPUS_SMOKE_METADATA_FIXTURE = $metadataFixture
    $env:OLYMPUS_SMOKE_REQUEST_LOG = $requestLog
    $env:OLYMPUS_SMOKE_METADATA_URI = $apiUri
    $env:OLYMPUS_SMOKE_RAW_BASE = $rawBase
    $env:OLYMPUS_SMOKE_ARCHIVE_URI = $archiveUri
    $env:OLYMPUS_SMOKE_PWSH = $script:Pwsh
    $env:OLYMPUS_SMOKE_SCRIPT = [IO.Path]::GetFullPath($PSCommandPath)
    $env:OLYMPUS_SMOKE_HOOK_DIR = $hookDirectory
    $env:OLYMPUS_SMOKE_OTHER_DIR = $otherDirectory
    $env:OLYMPUS_SMOKE_LAUNCHER_PATH = $bin + [IO.Path]::DirectorySeparatorChar + 'olympus.cmd'
    $env:OLYMPUS_SMOKE_OPENCODE_CONFIG = $opencodeConfig
    $env:OLYMPUS_SMOKE_GLOBAL_MARKER = $globalMarker
    $env:OLYMPUS_SMOKE_BIN_MARKER = $binMarker
    $env:OLYMPUS_SMOKE_VERSION_MARKER = $versionMarker
    $env:OLYMPUS_SMOKE_GLOBAL_MANIFEST = $manifest
    $env:OLYMPUS_SMOKE_USER_CONFIG = $userConfig

    [IO.Directory]::CreateDirectory((Split-Path -Parent $manifest)) | Out-Null
    [IO.File]::WriteAllText($globalMarker, 'unmanaged global file' + $newline, $Utf8NoBom)
    $globalInstall = Invoke-PowerShell @('-File', (Join-Path $source 'scripts/global-install.ps1'),
        '-Harness', 'opencode', '-SourceVersion', $sourceVersion, '-ProjectTarget', $otherDirectory)
    if ($globalInstall -notmatch ('OLYMPUS_GLOBAL_INSTALL: OPENCODE ' + [regex]::Escape($sourceVersion) + ' READY')) {
        throw "GLOBAL_INSTALL_ASSERTION_FAILED`n$globalInstall"
    }

    $cliInstall = Invoke-PowerShell @('-File', (Join-Path $source 'scripts/install-cli.ps1'),
        '-Action', 'install', '-Version', $sourceVersion, '-SourceRoot', $source,
        '-InstallRoot', $installRoot, '-PathStorePath', $pathStore)
    if ($cliInstall -notmatch ('OLYMPUS_CLI: INSTALLED version=' + [regex]::Escape($sourceVersion))) {
        throw "CLI_INSTALL_ASSERTION_FAILED`n$cliInstall"
    }
    $packagedSource = Join-Path $installRoot "versions/$sourceVersion"
    Assert 'PACKAGED_OPENCODE_GENERATED_ASSETS' ((Test-Path -LiteralPath (Join-Path $packagedSource '.opencode/agents/kael.md')) -and
        (Test-Path -LiteralPath (Join-Path $packagedSource '.opencode/plugins/olympus-activity/activity.ts')) -and
        (Test-Path -LiteralPath (Join-Path $packagedSource '.opencode/scripts/worktree-setup.ps1')))
    Assert 'PACKAGED_CODEX_FROZEN_ASSETS' ((Test-Path -LiteralPath (Join-Path $packagedSource '.codex/agents/veyra.toml')) -and
        (Test-Path -LiteralPath (Join-Path $packagedSource '.codex/config.toml')) -and
        (Test-Path -LiteralPath (Join-Path $packagedSource 'CODEX.md')))
    Assert 'PROJECT_COMMANDS_NOT_PACKAGED' (-not (Test-Path -LiteralPath (Join-Path $packagedSource '.opencode/commands')))
    $persistedPath = [IO.File]::ReadAllText($pathStore)
    Assert 'PATH_STORE_ISOLATED' ($persistedPath -ceq [IO.Path]::GetFullPath($bin))
    $userPathCollision = @(($originalUserPath -split ';') | Where-Object {
        $_ -and [string]::Equals($_.TrimEnd('\', '/'),
            $bin.TrimEnd('\', '/'), [StringComparison]::OrdinalIgnoreCase)
    }).Count -gt 0
    Assert 'NO_USER_PATH_COLLISION' (-not $userPathCollision)

    [IO.File]::WriteAllText($binMarker, '@echo off' + $newline + 'exit /b 0' + $newline, [Text.Encoding]::ASCII)
    [IO.Directory]::CreateDirectory((Split-Path -Parent $versionMarker)) | Out-Null
    [IO.File]::WriteAllText($versionMarker, 'unmanaged version directory' + $newline, $Utf8NoBom)

    $necessaryPath = @(
        $persistedPath,
        (Split-Path -Parent $python),
        (Split-Path -Parent $script:Pwsh),
        (Split-Path -Parent $git),
        (Join-Path $env:SystemRoot 'System32')
    ) | Select-Object -Unique
    $childPath = $necessaryPath -join ';'
    $start = [Diagnostics.ProcessStartInfo]::new([IO.Path]::GetFullPath($script:Pwsh))
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.WorkingDirectory = $otherDirectory
    $start.Environment.Clear()
    foreach ($key in @('SystemRoot', 'WINDIR', 'COMSPEC', 'PATHEXT', 'PSModulePath',
            'ProgramFiles', 'ProgramFiles(x86)', 'SystemDrive')) {
        $value = [Environment]::GetEnvironmentVariable($key, 'Process')
        if ($value) { $start.Environment[$key] = $value }
    }
    $start.Environment['PATH'] = $childPath
    $start.Environment['APPDATA'] = $appData
    $start.Environment['LOCALAPPDATA'] = $localAppData
    $start.Environment['USERPROFILE'] = $profile
    $start.Environment['HOME'] = $profile
    $start.Environment['TEMP'] = $tempDirectory
    $start.Environment['TMP'] = $tempDirectory
    $start.Environment['OPENCODE_CONFIG_DIR'] = $opencodeRoot
    $start.Environment['PYTHONDONTWRITEBYTECODE'] = '1'
    $start.Environment['OLYMPUS_PYTHON'] = [IO.Path]::GetFullPath($python)
    foreach ($name in @('OLYMPUS_SMOKE_INSTALL_ROOT', 'OLYMPUS_SMOKE_PATH_STORE', 'OLYMPUS_SMOKE_RELEASE_VERSION',
            'OLYMPUS_SMOKE_RELEASE_INSTALLER', 'OLYMPUS_SMOKE_RELEASE_ARCHIVE', 'OLYMPUS_SMOKE_METADATA_FIXTURE',
            'OLYMPUS_SMOKE_REQUEST_LOG', 'OLYMPUS_SMOKE_METADATA_URI', 'OLYMPUS_SMOKE_RAW_BASE',
            'OLYMPUS_SMOKE_ARCHIVE_URI', 'OLYMPUS_SMOKE_PWSH', 'OLYMPUS_SMOKE_SCRIPT', 'OLYMPUS_SMOKE_HOOK_DIR',
            'OLYMPUS_SMOKE_OTHER_DIR', 'OLYMPUS_SMOKE_LAUNCHER_PATH', 'OLYMPUS_SMOKE_OPENCODE_CONFIG',
            'OLYMPUS_SMOKE_GLOBAL_MARKER', 'OLYMPUS_SMOKE_BIN_MARKER', 'OLYMPUS_SMOKE_VERSION_MARKER',
            'OLYMPUS_SMOKE_GLOBAL_MANIFEST', 'OLYMPUS_SMOKE_USER_CONFIG')) {
        $start.Environment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }
    foreach ($argument in @('-NoProfile', '-NonInteractive', '-File', [IO.Path]::GetFullPath($PSCommandPath), '-Child')) {
        $start.ArgumentList.Add($argument)
    }
    $childProcess = [Diagnostics.Process]::new()
    $childProcess.StartInfo = $start
    try {
        if (-not $childProcess.Start()) { throw 'CHILD_PROCESS_START_FAILED' }
        $stdout = $childProcess.StandardOutput.ReadToEndAsync()
        $stderr = $childProcess.StandardError.ReadToEndAsync()
        $childProcess.WaitForExit()
        Write-Output $stdout.GetAwaiter().GetResult()
        $childError = $stderr.GetAwaiter().GetResult()
        if ($childError) { Write-Output $childError }
        if ($childProcess.ExitCode -ne 0) { throw "CHILD_SMOKE_FAILED: exit=$($childProcess.ExitCode)" }
    } finally { $childProcess.Dispose() }

    $requests = [IO.File]::ReadAllText($requestLog)
    Assert 'MOCKED_STABLE_RELEASE_METADATA' ($requests -match ('(?m)^metadata ' + [regex]::Escape($apiUri) + '$'))
    Assert 'MOCKED_RELEASE_INSTALLER' ($requests -match ('(?m)^installer ' + [regex]::Escape("$rawBase/$nextVersion/install.ps1") + '$'))
    Assert 'MOCKED_RELEASE_ARCHIVE' ($requests -match ('(?m)^archive ' + [regex]::Escape($archiveUri) + '$'))
    Assert 'ALL_RELEASE_REQUESTS_FIXTURED' (@($requests -split "`n" | Where-Object { $_ }).Count -eq 3)

    Assert 'USER_OPENCODE_CONFIG_UNCHANGED' ([Convert]::ToBase64String($savedOpenCodeConfig) -ceq
        [Convert]::ToBase64String([IO.File]::ReadAllBytes($opencodeConfig)))
    Assert 'USER_GLOBAL_FILE_PRESERVED' ([IO.File]::ReadAllText($globalMarker) -ceq ('unmanaged global file' + $newline))
    $userConfiguration = [IO.File]::ReadAllText($userConfig) | ConvertFrom-Json -AsHashtable -Depth 20
    Assert 'USER_OVERRIDE_PRESERVED' ($userConfiguration.overrides.nox.model -ceq 'openai/gpt-6.1-sol' -and
        $userConfiguration.overrides.nox.effort -ceq 'high')
    Assert 'USER_CLI_BIN_FILE_PRESERVED' (Test-Path -LiteralPath $binMarker -PathType Leaf)
    Assert 'USER_CLI_VERSION_DIRECTORY_PRESERVED' (Test-Path -LiteralPath $versionMarker -PathType Leaf)
    Assert 'GLOBAL_MANAGED_RESOURCES_UNINSTALLED' (-not (Test-Path -LiteralPath $manifest) -and
        -not (Test-Path -LiteralPath (Join-Path $opencodeRoot 'agents/nox.md')))
    Assert 'CLI_MANAGED_RELEASES_UNINSTALLED' (-not (Test-Path -LiteralPath (Join-Path $installRoot 'current.txt')) -and
        -not (Test-Path -LiteralPath (Join-Path $bin 'olympus.cmd')))
    Assert 'OWNED_PATH_ENTRY_UNINSTALLED' ([IO.File]::ReadAllText($pathStore) -ceq '')
    # User PATH can expand %USERPROFILE%; compare under the original environment.
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
    Assert 'USER_PATH_UNCHANGED' ([Environment]::GetEnvironmentVariable('Path', 'User') -ceq $originalUserPath)
    Assert 'PROCESS_PATH_UNCHANGED' ($env:PATH -ceq $originalProcessPath)
    Write-Output "GLOBAL_CLI_SMOKE: PASS (source=$sourceVersion fixture-release=$nextVersion; no published release or API used)"
} finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
    if ($runCreated -and (Test-Path -LiteralPath $run -PathType Container)) {
        Remove-Item -LiteralPath $run -Recurse -Force
    }
    if ($createdParent -and (Test-Path -LiteralPath $fixtureParent -PathType Container) -and
        @(Get-ChildItem -LiteralPath $fixtureParent -Force).Count -eq 0) {
        [IO.Directory]::Delete($fixtureParent)
    }
}
