# Windows-qualified release acquisition; scripts/bootstrap.ps1 owns all target checks.
[CmdletBinding()]
param(
    [ValidatePattern('^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$')]
    [string]$Version = 'v0.12.4',
    [ValidateSet('global')]
    [string]$Scope = 'global',
    [ValidateSet('opencode')]
    [string]$Harness = 'opencode',
    [switch]$DryRun,
    [switch]$VerifyOnly,
    [switch]$Uninstall,
    [switch]$Update,
    # Qualification-only source overrides. Source identity is always checked.
    [string]$SourceRoot,
    [string]$SourceArchive,
    # Qualification-only CLI destination overrides; normal installs use user defaults.
    [string]$CliInstallRoot,
    [string]$CliPathStorePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ReleaseVersion = 'v0.12.4' # Must equal this installer's default and the release target tag.
$owned = $null

function Get-DeclaredReleaseVersion([string]$Source) {
    $scriptPath = Join-Path $Source 'install.ps1'
    if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
        throw 'SOURCE_INVALID: Release source has no install.ps1 identity.'
    }
    $text = [IO.File]::ReadAllText($scriptPath)
    $defaultMatch = [regex]::Match($text, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''\s*,?\s*$')
    if (-not $defaultMatch.Success) { throw 'SOURCE_INVALID: Cannot identify the source release version.' }
    $defaultVersion = $defaultMatch.Groups[1].Value
    $releaseMatch = [regex]::Match($text, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''\s*(?:#.*)?$')
    if ($releaseMatch.Success -and $releaseMatch.Groups[1].Value -cne $defaultVersion) {
        throw 'SOURCE_VERSION_MISMATCH: Release marker and installer default disagree.'
    }
    if ($defaultVersion -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
        throw "SOURCE_INVALID: Source release version is malformed: $defaultVersion"
    }
    return $defaultVersion
}

function Set-UpGlobalCli([string]$Source, [string]$Version, [string]$Action,
                         [string]$InstallRoot, [string]$PathStorePath, [bool]$CompactUpdate = $false) {
    $cliInstaller = Join-Path $Source 'scripts/install-cli.ps1'
    if (-not (Test-Path -LiteralPath $cliInstaller -PathType Leaf)) { throw 'SOURCE_INVALID: Global CLI installer is missing.' }
    $cliArgs = @('-NoProfile', '-File', $cliInstaller, '-Action', $Action,
        '-Version', $Version, '-SourceRoot', $Source)
    if ($InstallRoot) { $cliArgs += @('-InstallRoot', $InstallRoot) }
    if ($PathStorePath) { $cliArgs += @('-PathStorePath', $PathStorePath) }
    $previousCompact = [Environment]::GetEnvironmentVariable('OLYMPUS_CLI_UPDATE_COMPACT', 'Process')
    try {
        [Environment]::SetEnvironmentVariable(
            'OLYMPUS_CLI_UPDATE_COMPACT', $(if ($CompactUpdate) { '1' } else { $null }), 'Process'
        )
        & $pwsh.Source @cliArgs
        $cliExitCode = $LASTEXITCODE
    } finally {
        [Environment]::SetEnvironmentVariable('OLYMPUS_CLI_UPDATE_COMPACT', $previousCompact, 'Process')
    }
    if ($cliExitCode -ne 0) { throw "GLOBAL_CLI_SETUP_FAILED: global CLI setup exited $cliExitCode." }
}

function Assert-ArchiveTag([string]$RootName, [string]$RequestedVersion) {
    # GitHub's generated archive directory may omit the tag's leading v.
    $withoutV = $RequestedVersion.Substring(1)
    $acceptedRoots = @("OpenCode-OlympusAgents-$RequestedVersion", "OpenCode-OlympusAgents-$withoutV")
    if (@($acceptedRoots | Where-Object { $_ -ceq $RootName }).Count -ne 1) {
        throw "SOURCE_VERSION_MISMATCH: Archive root '$RootName' does not identify requested tag '$RequestedVersion'."
    }
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: Olympus installer is Windows-qualified only.' }
    if ($ReleaseVersion -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
        throw 'INSTALLER_RELEASE_VERSION_INVALID: Embedded release identity is malformed.'
    }
    if ($Version -cne $Version.Trim()) { throw 'VERSION_INVALID: Whitespace is not allowed.' }
    if ($VerifyOnly -and $DryRun) { throw 'VERIFY_MODE_INVALID: -VerifyOnly and -DryRun cannot be combined.' }
    if ($VerifyOnly -and $Uninstall) { throw 'VERIFY_MODE_INVALID: -VerifyOnly and -Uninstall cannot be combined.' }
    if ($Update -and ($Uninstall -or $DryRun -or $VerifyOnly)) {
        throw 'UPDATE_MODE_INVALID: -Update cannot be combined with uninstall, dry-run, or VerifyOnly.'
    }
    if ($SourceRoot -and $SourceArchive) { throw 'SOURCE_INVALID: Select only one qualification source override.' }

    $pwsh = Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $pwsh) { throw 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 (pwsh) is required. Install PowerShell 7 and run this command again.' }

    $origin = ''
    if ($SourceRoot) {
        $source = (Resolve-Path -LiteralPath $SourceRoot -ErrorAction Stop).Path
        if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw 'SOURCE_INVALID: SourceRoot must be a directory.' }
        $origin = 'LOCAL_SOURCE'
    } else {
        $tempBase = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode'
        [IO.Directory]::CreateDirectory($tempBase) | Out-Null
        $owned = Join-Path $tempBase ('olympus-install-' + [guid]::NewGuid().ToString('N'))
        [IO.Directory]::CreateDirectory($owned) | Out-Null
        $archive = Join-Path $owned 'release.zip'
        $expanded = Join-Path $owned 'expanded'

        if ($SourceArchive) {
            $archive = (Resolve-Path -LiteralPath $SourceArchive -ErrorAction Stop).Path
            if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) { throw 'SOURCE_INVALID: SourceArchive must be a file.' }
            $origin = 'LOCAL_ARCHIVE'
        } else {
            # The immutable requested release tag is the sole remote source.
            $url = "https://github.com/Edulynch/OpenCode-OlympusAgents/archive/refs/tags/$Version.zip"
            Invoke-WebRequest -Uri $url -OutFile $archive -ErrorAction Stop
            $origin = 'REMOTE_ARCHIVE'
        }

        Expand-Archive -LiteralPath $archive -DestinationPath $expanded -ErrorAction Stop
        $entries = @(Get-ChildItem -LiteralPath $expanded -Force)
        if ($entries.Count -ne 1 -or -not $entries[0].PSIsContainer) { throw 'SOURCE_INVALID: Release archive has no single source root.' }
        Assert-ArchiveTag $entries[0].Name $Version
        $source = $entries[0].FullName
    }

    $resolvedVersion = Get-DeclaredReleaseVersion $source
    if ($resolvedVersion -cne $Version) {
        throw "SOURCE_VERSION_MISMATCH: requested '$Version' but resolved source reports '$resolvedVersion'."
    }
    $bootstrap = Join-Path $source 'scripts/bootstrap.ps1'
    if (-not (Test-Path -LiteralPath $bootstrap -PathType Leaf)) { throw 'SOURCE_INVALID: Release source has no bootstrap script.' }
    if (-not ($Update -and $env:OLYMPUS_UPDATE_COMPACT -ceq '1')) {
        Write-Output "OLYMPUS_SOURCE: requested=$Version resolved=$resolvedVersion origin=$origin"
    }

    if ($Uninstall -and $DryRun) { throw 'UNINSTALL_MODE_INVALID: -Uninstall and -DryRun cannot be combined.' }
    $globalScript = Join-Path $source 'scripts/global-install.ps1'
    if (-not (Test-Path -LiteralPath $globalScript -PathType Leaf)) { throw 'SOURCE_INVALID: Global installer is missing.' }
    $globalArgs = @('-NoProfile', '-File', $globalScript, '-Harness', 'opencode', '-SourceVersion', $resolvedVersion)
    if ($VerifyOnly) { $globalArgs += '-VerifyOnly' }
    if ($DryRun) { $globalArgs += '-DryRun' }
    if ($Uninstall) { $globalArgs += '-Uninstall' }
    if ($Update) { $globalArgs += '-Update' }
    & $pwsh.Source @globalArgs
    if ($LASTEXITCODE -ne 0) { throw "GLOBAL_BOOTSTRAP_FAILED: global installer exited $LASTEXITCODE." }
    if (-not $DryRun -and -not $VerifyOnly) {
        $cliAction = if ($Uninstall) { 'uninstall' } else { 'install' }
        Set-UpGlobalCli -Source $source -Version $resolvedVersion -Action $cliAction `
            -InstallRoot $CliInstallRoot -PathStorePath $CliPathStorePath `
            -CompactUpdate ($Update -and $env:OLYMPUS_UPDATE_COMPACT -ceq '1')
    }
    exit 0
} catch {
    if ($VerifyOnly) {
        $message = $_.Exception.Message
        $reason = if ($message -match '^([A-Z][A-Z0-9_]+):') { $Matches[1] } else { 'VERIFY_FAILED' }
        Write-Output "OLYMPUS_VERIFY: $Version FAIL"
        Write-Output "OLYMPUS_VERIFY_REASON: $reason"
        Write-Output "OLYMPUS_VERIFY_DETAIL: $message"
    }
    Write-Error $_.Exception.Message
    exit 1
} finally {
    # Only the unique directory allocated above is owned by this installer.
    if ($owned -and (Test-Path -LiteralPath $owned)) {
        Remove-Item -LiteralPath $owned -Recurse -Force
    }
}
