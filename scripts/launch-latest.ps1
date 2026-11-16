# Resolves the latest published Olympus release, then delegates to that immutable release installer.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'uninstall')]
    [string]$Action,
    [switch]$DryRun,
    [switch]$Update
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$owned = $null

function Get-ReleaseField([object]$Metadata, [string]$Name) {
    if ($null -eq $Metadata) { throw 'LATEST_RELEASE_METADATA_INVALID: GitHub returned no release metadata.' }
    if ($Metadata -is [System.Collections.IDictionary]) {
        if (-not $Metadata.Contains($Name)) {
            throw "LATEST_RELEASE_METADATA_INCOMPLETE: GitHub release metadata is missing '$Name'."
        }
        return $Metadata[$Name]
    }

    $property = $Metadata.PSObject.Properties[$Name]
    if ($null -eq $property) {
        throw "LATEST_RELEASE_METADATA_INCOMPLETE: GitHub release metadata is missing '$Name'."
    }
    return $property.Value
}

function Assert-ReleaseBoolean([object]$Metadata, [string]$Name, [bool]$Expected) {
    $value = Get-ReleaseField $Metadata $Name
    if ($value -isnot [bool] -or $value -ne $Expected) {
        if ($Name -eq 'immutable' -and $Expected) {
            throw 'LATEST_RELEASE_MUTABLE: GitHub release metadata does not assert immutable=true.'
        }
        throw "LATEST_RELEASE_NOT_PUBLISHED: GitHub release metadata field '$Name' is not $Expected."
    }
}

function ConvertTo-ReleasePublishedTimestamp([object]$Value) {
    if ($null -eq $Value) { throw 'published_at is null.' }
    if ($Value -is [DateTimeOffset]) { return $Value }
    if ($Value -is [DateTime]) {
        if ($Value.Kind -eq [DateTimeKind]::Unspecified) {
            throw 'published_at DateTime has no time-zone kind.'
        }
        if ($Value.Kind -eq [DateTimeKind]::Local) {
            $localWallTime = [DateTime]::SpecifyKind($Value, [DateTimeKind]::Unspecified)
            if ([TimeZoneInfo]::Local.IsInvalidTime($localWallTime) -or
                [TimeZoneInfo]::Local.IsAmbiguousTime($localWallTime)) {
                throw 'published_at DateTime has an invalid or ambiguous local time.'
            }
        }
        return [DateTimeOffset]::new([DateTime]$Value)
    }
    if ($Value -isnot [string] -or
        $Value -notmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|[+-]\d{2}:\d{2})$') {
        throw 'published_at must be a time-zone-aware ISO 8601 timestamp.'
    }

    $timestamp = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse(
        $Value,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::None,
        [ref]$timestamp
    )) {
        throw 'published_at is not a valid ISO 8601 timestamp.'
    }
    return $timestamp
}

function Compare-ReleaseTag([string]$Left, [string]$Right) {
    $pattern = '^v(?<major>0|[1-9][0-9]*)\.(?<minor>0|[1-9][0-9]*)\.(?<patch>0|[1-9][0-9]*)(?:-(?<stage>alpha|beta|rc)\.(?<sequence>0|[1-9][0-9]*))?$'
    $a = [regex]::Match($Left, $pattern)
    $b = [regex]::Match($Right, $pattern)
    if (-not $a.Success -or -not $b.Success) { throw 'UPDATE_VERSION_UNKNOWN: Cannot compare an unrecognized Olympus release tag.' }
    foreach ($part in @('major','minor','patch')) {
        $comparison = ([long]$a.Groups[$part].Value).CompareTo([long]$b.Groups[$part].Value)
        if ($comparison -ne 0) { return $comparison }
    }
    $aStable = -not $a.Groups['stage'].Success
    $bStable = -not $b.Groups['stage'].Success
    if ($aStable -ne $bStable) { return $(if ($aStable) { 1 } else { -1 }) }
    if ($aStable) { return 0 }
    $stageOrder = @{ alpha=1; beta=2; rc=3 }
    $stageComparison = ([int]$stageOrder[$a.Groups['stage'].Value]).CompareTo([int]$stageOrder[$b.Groups['stage'].Value])
    if ($stageComparison -ne 0) { return $stageComparison }
    return ([long]$a.Groups['sequence'].Value).CompareTo([long]$b.Groups['sequence'].Value)
}

function Get-InstalledGlobalVersion {
    $root = $null
    if ($env:OPENCODE_CONFIG_DIR) { $root = [IO.Path]::GetFullPath($env:OPENCODE_CONFIG_DIR) }
    else {
        $commands = @(Get-Command opencode -CommandType Application -ErrorAction SilentlyContinue)
        if ($commands.Count -eq 0) { return $null }
        $paths = @(& $commands[0].Source debug paths 2>$null | ForEach-Object {
            if ($_ -match '^\s*config\s{2,}(.+?)\s*$') { $Matches[1].Trim() }
        })
        if ($LASTEXITCODE -ne 0 -or $paths.Count -ne 1 -or -not [IO.Path]::IsPathFullyQualified($paths[0])) { return $null }
        $root = $paths[0]
    }
    $manifestPath = Join-Path $root 'olympus/orchestrator-install.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) { return $null }
    try { $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json -Depth 30 -ErrorAction Stop }
    catch { throw 'UPDATE_MANIFEST_INVALID: The installed Olympus version record is unreadable; no update was started.' }
    if ($manifest.scope -cne 'global' -or @($manifest.installed_harnesses).Count -ne 1 -or
        [string]$manifest.installed_harnesses[0] -cne 'opencode') {
        throw 'UPDATE_MANIFEST_INVALID: The installed Olympus version record is not a supported global installation.'
    }
    $installed = [string]$manifest.installed_version
    if ($installed -ceq 'local' -or $installed -ceq 'unknown' -or $installed -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') { return $null }
    return $installed
}

try {
    if ($DryRun -and $Action -ne 'install') {
        throw 'DRY_RUN_UNSUPPORTED: -DryRun is available only for install.'
    }
    if ($Update -and ($Action -ne 'install' -or $DryRun)) {
        throw 'UPDATE_MODE_INVALID: -Update is available only for a normal install.'
    }
    $pwsh = @(Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue)
    if ($pwsh.Count -eq 0) {
        throw 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 (pwsh) is required.'
    }

    $headers = @{ 'User-Agent' = 'OlympusAgents-Installer' }
    # GitHub's HTTPS metadata and raw source are the acquisition channel. The
    # immutable flag is GitHub's assertion; this does not independently verify
    # a signature or cryptographic provenance for the downloaded bytes.
    $releaseUri = 'https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest'
    $release = Invoke-RestMethod -Uri $releaseUri -Headers $headers -ErrorAction Stop
    Assert-ReleaseBoolean $release 'immutable' $true
    Assert-ReleaseBoolean $release 'draft' $false
    Assert-ReleaseBoolean $release 'prerelease' $false

    $tag = [string](Get-ReleaseField $release 'tag_name')
    if (-not [regex]::IsMatch($tag, '\Av(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?\z')) {
        throw "LATEST_RELEASE_INVALID: GitHub latest release returned malformed tag '$tag'."
    }
    if ($tag -match '-(?:alpha|beta|rc)\.' -and -not [bool](Get-ReleaseField $release 'prerelease')) {
        throw "LATEST_RELEASE_METADATA_INCONSISTENT: tag '$tag' is prerelease but GitHub reports prerelease=false."
    }

    $publishedAt = Get-ReleaseField $release 'published_at'
    if ($null -eq $publishedAt -or ($publishedAt -is [string] -and [string]::IsNullOrWhiteSpace($publishedAt))) {
        throw 'LATEST_RELEASE_NOT_PUBLISHED: GitHub release has no published_at timestamp.'
    }
    try {
        $publishedTimestamp = ConvertTo-ReleasePublishedTimestamp $publishedAt
    } catch {
        throw "LATEST_RELEASE_METADATA_INVALID: published_at '$publishedAt' is not a valid time-zone-aware timestamp."
    }
    if ($publishedTimestamp -gt [DateTimeOffset]::UtcNow.AddMinutes(5)) {
        throw "LATEST_RELEASE_METADATA_INVALID: published_at '$publishedAt' is in the future."
    }

    if ($Action -eq 'install' -and $Update) {
        $installed = Get-InstalledGlobalVersion
        if ($installed -and (Compare-ReleaseTag $tag $installed) -lt 0) {
            Write-Output "OLYMPUS_UPDATE: NO_DOWNGRADE current=$installed latest=$tag"
            exit 0
        }
        if ($installed) { Write-Output "OLYMPUS_UPDATE: current=$installed latest=$tag" }
    }
    Write-Output "OLYMPUS_RELEASE_SELECTED: tag=$tag immutable=true published_at=$($publishedTimestamp.ToUniversalTime().ToString('o'))"

    $tempBase = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'olympus'
    [IO.Directory]::CreateDirectory($tempBase) | Out-Null
    $owned = Join-Path $tempBase ('entrypoint-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($owned) | Out-Null
    $installer = Join-Path $owned 'install.ps1'

    $installerUrl = "https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$tag/install.ps1"
    Invoke-WebRequest -Uri $installerUrl -OutFile $installer -Headers $headers -ErrorAction Stop

    # "latest" chooses a release; execution itself is pinned to the exact tag the API returned.
    $installerText = [IO.File]::ReadAllText($installer)
    $defaultMatch = [regex]::Match($installerText, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''\s*,?\s*$')
    $releaseMatch = [regex]::Match($installerText, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''\s*(?:#.*)?$')
    if (-not $defaultMatch.Success -or -not $releaseMatch.Success -or
        $defaultMatch.Groups[1].Value -cne $tag -or $releaseMatch.Groups[1].Value -cne $tag) {
        throw "LATEST_RELEASE_IDENTITY_MISMATCH: Downloaded installer does not identify itself as $tag."
    }

    $args = @(
        '-NoProfile'
    )
    if (-not $Update) { $args += '-NonInteractive' }
    $args += @(
        '-File', $installer,
        '-Version', $tag,
        '-Scope', 'global',
        '-Harness', 'opencode'
    )
    if ($Action -eq 'uninstall') { $args += '-Uninstall' }
    if ($Update) { $args += '-Update' }
    if ($DryRun) { $args += '-DryRun' }

    Write-Output "OLYMPUS_ENTRYPOINT: action=$Action scope=global harness=opencode release=$tag"
    Write-Output "OLYMPUS_RELEASE_EXECUTING: tag=$tag installer=$installerUrl"
    & $pwsh[0].Source @args
    if ($LASTEXITCODE -ne 0) {
        $installerExitCode = $LASTEXITCODE
        Write-Output "OLYMPUS_ENTRYPOINT_FAILED: release installer exited $installerExitCode."
        exit $installerExitCode
    }
    Write-Output "OLYMPUS_RELEASE_EXECUTED: tag=$tag exit_code=0"
} finally {
    if ($owned -and (Test-Path -LiteralPath $owned)) {
        Remove-Item -LiteralPath $owned -Recurse -Force -ErrorAction SilentlyContinue
    }
}
