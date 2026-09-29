# Windows-qualified release acquisition; scripts/bootstrap.ps1 owns all target checks.
[CmdletBinding()]
param(
    [ValidatePattern('^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$')]
    [string]$Version = 'v0.3.0-beta.3',
    [string]$Target = (Get-Location).Path,
    [switch]$DryRun,
    # Qualification-only source overrides. Source identity is always checked.
    [string]$SourceRoot,
    [string]$SourceArchive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ReleaseVersion = 'v0.3.0-beta.3' # Must equal this installer's default and published tag.
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
    if ($SourceRoot -and $SourceArchive) { throw 'SOURCE_INVALID: Select only one qualification source override.' }

    $pwsh = Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue
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
    Write-Output "OLYMPUS_SOURCE: requested=$Version resolved=$resolvedVersion origin=$origin"

    # Keep bootstrap's own process semantics, drift checks, containment and effective-agent validation.
    $args = @('-NoProfile', '-File', $bootstrap, '-Target', $Target)
    $bootstrapText = [IO.File]::ReadAllText($bootstrap)
    if ($bootstrapText -match '(?m)^\s*\[string\]\$SourceVersion\s*=') {
        $args += @('-SourceVersion', $resolvedVersion)
    }
    if ($DryRun) { $args += '-DryRun' }
    & $pwsh.Source @args
    if ($LASTEXITCODE -ne 0) { throw "BOOTSTRAP_FAILED: bootstrap exited $LASTEXITCODE; no installer cleanup touches the target." }
    if ($DryRun) { Write-Output "OLYMPUS_INSTALL: $resolvedVersion DRY_RUN_READY" }
    else { Write-Output "OLYMPUS_INSTALL: $resolvedVersion READY_OR_NO_CHANGES" }
} finally {
    # Only the unique directory allocated above is owned by this installer.
    if ($owned -and (Test-Path -LiteralPath $owned)) {
        Remove-Item -LiteralPath $owned -Recurse -Force
    }
}
