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

try {
    $pwsh = @(Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue)
    if ($pwsh.Count -eq 0) {
        throw 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 (pwsh) is required.'
    }

    $headers = @{ 'User-Agent' = 'OlympusAgents-Installer' }
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest' -Headers $headers -ErrorAction Stop
    $tag = [string]$release.tag_name
    if ($tag -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
        throw "LATEST_RELEASE_INVALID: GitHub latest release returned malformed tag '$tag'."
    }

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
        '-NoProfile',
        '-File', $installer,
        '-Version', $tag,
        '-Target', ([IO.Path]::GetFullPath($Target)),
        '-Scope', $Scope,
        '-Harness', $Harness
    )
    if ($Action -eq 'uninstall') { $args += '-Uninstall' }

    Write-Output "OLYMPUS_ENTRYPOINT: action=$Action scope=$Scope harness=$Harness release=$tag"
    & $pwsh[0].Source @args
    if ($LASTEXITCODE -ne 0) {
        throw "OLYMPUS_ENTRYPOINT_FAILED: release installer exited $LASTEXITCODE."
    }
} finally {
    if ($owned -and (Test-Path -LiteralPath $owned)) {
        Remove-Item -LiteralPath $owned -Recurse -Force -ErrorAction SilentlyContinue
    }
}
