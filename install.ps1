# Windows-qualified release acquisition; scripts/bootstrap.ps1 owns all target checks.
[CmdletBinding()]
param(
    [ValidatePattern('^v[0-9]+\.[0-9]+\.[0-9]+$')]
    [string]$Version = 'v0.1.2',
    [string]$Target = (Get-Location).Path,
    [switch]$DryRun,
    # Qualification-only: use a local source checkout before the release tag exists.
    [string]$SourceRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$owned = $null
try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: v0.1.2 installer is Windows-qualified only.' }
    $pwsh = Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue
    if (-not $pwsh) { throw 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 (pwsh) is required. Install PowerShell 7 and run this command again.' }
    if ($SourceRoot) {
        $source = (Resolve-Path -LiteralPath $SourceRoot -ErrorAction Stop).Path
        if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw 'SOURCE_INVALID: SourceRoot must be a directory.' }
    } else {
        # The stable source is an immutable release tag, never the moving master branch.
        $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        $owned = Join-Path $tempBase ('olympus-install-' + [guid]::NewGuid().ToString('N'))
        [IO.Directory]::CreateDirectory($owned) | Out-Null
        $archive = Join-Path $owned 'release.zip'
        $expanded = Join-Path $owned 'expanded'
        $url = "https://github.com/Edulynch/OpenCode-OlympusAgents/archive/refs/tags/$Version.zip"
        Invoke-WebRequest -Uri $url -OutFile $archive -ErrorAction Stop
        Expand-Archive -LiteralPath $archive -DestinationPath $expanded -ErrorAction Stop
        $entries = @(Get-ChildItem -LiteralPath $expanded -Force)
        if ($entries.Count -ne 1 -or -not $entries[0].PSIsContainer) { throw 'SOURCE_INVALID: Release archive has no single source root.' }
        $source = $entries[0].FullName
    }
    $bootstrap = Join-Path $source 'scripts/bootstrap.ps1'
    if (-not (Test-Path -LiteralPath $bootstrap -PathType Leaf)) { throw 'SOURCE_INVALID: Release source has no bootstrap script.' }
    # Keep bootstrap's own process semantics, drift checks, containment and effective-agent validation.
    $args = @('-NoProfile', '-File', $bootstrap, '-Target', $Target)
    if ($DryRun) { $args += '-DryRun' }
    & $pwsh.Source @args
    if ($LASTEXITCODE -ne 0) { throw "BOOTSTRAP_FAILED: bootstrap exited $LASTEXITCODE; no installer cleanup touches the target." }
    if ($DryRun) { Write-Output "OLYMPUS_INSTALL: $Version DRY_RUN_READY" }
    else { Write-Output "OLYMPUS_INSTALL: $Version READY_OR_NO_CHANGES" }
} finally {
    # Only the unique directory allocated above is owned by this installer.
    if ($owned -and (Test-Path -LiteralPath $owned)) {
        Remove-Item -LiteralPath $owned -Recurse -Force
    }
}
