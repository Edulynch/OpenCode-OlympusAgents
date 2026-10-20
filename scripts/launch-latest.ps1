# Resolves the latest published Olympus release, then delegates to that immutable release installer.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'uninstall')]
    [string]$Action,
    [Parameter(Mandatory = $true)]
    [ValidateSet('project', 'global')]
    [string]$Scope,
    [Parameter(Mandatory = $true)]
    [ValidateSet('opencode', 'codex', 'all')]
    [string]$Harness,
    [string]$Target = (Get-Location).Path
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

try {
    $pwsh = @(Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue)
    if ($pwsh.Count -eq 0) {
        throw 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 (pwsh) is required.'
    }

    $headers = @{ 'User-Agent' = 'OlympusAgents-Installer' }
    # GitHub's HTTPS metadata and raw source are the acquisition channel. The
    # immutable flag is GitHub's assertion; this does not independently verify
    # a signature or cryptographic provenance for the downloaded bytes.
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest' -Headers $headers -ErrorAction Stop
    Assert-ReleaseBoolean $release 'immutable' $true
    Assert-ReleaseBoolean $release 'draft' $false
    Assert-ReleaseBoolean $release 'prerelease' $false

    $tag = [string](Get-ReleaseField $release 'tag_name')
    if ($tag -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
        throw "LATEST_RELEASE_INVALID: GitHub latest release returned malformed tag '$tag'."
    }
    if ($tag -match '-(?:alpha|beta|rc)\.' -and -not [bool](Get-ReleaseField $release 'prerelease')) {
        throw "LATEST_RELEASE_METADATA_INCONSISTENT: tag '$tag' is prerelease but GitHub reports prerelease=false."
    }
    $publishedAt = [string](Get-ReleaseField $release 'published_at')
    if ([string]::IsNullOrWhiteSpace($publishedAt)) {
        throw 'LATEST_RELEASE_NOT_PUBLISHED: GitHub release has no published_at timestamp.'
    }
    try {
        $publishedTimestamp = [DateTimeOffset]::Parse($publishedAt, [Globalization.CultureInfo]::InvariantCulture)
    } catch {
        throw "LATEST_RELEASE_METADATA_INVALID: published_at '$publishedAt' is not a valid timestamp."
    }
    if ($publishedTimestamp -gt [DateTimeOffset]::UtcNow.AddMinutes(5)) {
        throw "LATEST_RELEASE_METADATA_INVALID: published_at '$publishedAt' is in the future."
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

    if ($Action -eq 'uninstall' -and $Scope -eq 'project' -and
        $installerText -notmatch [regex]::Escape('scripts/project-uninstall.ps1')) {
        throw "PROJECT_UNINSTALL_UNAVAILABLE_IN_LATEST_RELEASE: $tag predates project uninstall support."
    }

    $args = @(
        '-NoProfile',
        '-File', $installer,
        '-Version', $tag,
        '-Target', ([IO.Path]::GetFullPath($Target)),
        '-Scope', $Scope,
        '-Harness', $Harness
    )
    if ($Action -eq 'uninstall') { $args += '-Uninstall' }

    Write-Output "OLYMPUS_ENTRYPOINT: action=$Action scope=$Scope harness=$Harness release=$tag"
    Write-Output "OLYMPUS_RELEASE_EXECUTING: tag=$tag installer=$installerUrl"
    & $pwsh[0].Source @args
    if ($LASTEXITCODE -ne 0) {
        throw "OLYMPUS_ENTRYPOINT_FAILED: release installer exited $LASTEXITCODE."
    }
    Write-Output "OLYMPUS_RELEASE_EXECUTED: tag=$tag exit_code=0"
} finally {
    if ($owned -and (Test-Path -LiteralPath $owned)) {
        Remove-Item -LiteralPath $owned -Recurse -Force -ErrorAction SilentlyContinue
    }
}
