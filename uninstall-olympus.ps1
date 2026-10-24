# Unified interactive and direct Olympus uninstallation entrypoint.
[CmdletBinding(DefaultParameterSetName = 'Interactive')]
param(
    [Parameter(ParameterSetName = 'ProjectHere')]
    [switch]$Project,
    [Parameter(ParameterSetName = 'ProjectHere')]
    [switch]$Here,
    [Parameter(ParameterSetName = 'ProjectPath')]
    [string]$ProjectPath,
    [Parameter(ParameterSetName = 'Global')]
    [switch]$Global,
    [string]$Harness
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ownedLauncher = $null

function Read-UninstallScope {
    while ($true) {
        Write-Host 'Uninstall scope:'
        Write-Host '  [1] Current project'
        Write-Host '  [2] Another project path'
        Write-Host '  [3] Global'
        $choice = (Read-Host 'Choose 1, 2, or 3').Trim()
        switch ($choice) {
            '1' { return [pscustomobject]@{ Scope = 'project'; Target = (Get-Location).Path } }
            '2' {
                $path = (Read-Host 'Project path').Trim()
                if ($path) { return [pscustomobject]@{ Scope = 'project'; Target = $path } }
                Write-Host 'A project path is required.'
            }
            '3' { return [pscustomobject]@{ Scope = 'global'; Target = (Get-Location).Path } }
            default { Write-Host 'Choose 1, 2, or 3.' }
        }
    }
}

function Read-UninstallHarness {
    while ($true) {
        Write-Host 'Harness:'
        Write-Host '  [1] OpenCode'
        Write-Host '  [2] Codex'
        Write-Host '  [3] Both'
        $choice = (Read-Host 'Choose 1, 2, or 3').Trim()
        switch ($choice) {
            '1' { return 'opencode' }
            '2' { return 'codex' }
            '3' { return 'all' }
            default { Write-Host 'Choose 1, 2, or 3.' }
        }
    }
}

function Assert-InteractiveInput {
    # A host-supplied Read-Host function can provide input without console stdin.
    $readHostProvider = Get-Command Read-Host -ErrorAction SilentlyContinue
    $hasPromptProvider = $null -ne $readHostProvider -and $readHostProvider.CommandType -eq 'Function'
    if (-not [Environment]::UserInteractive -or ([Console]::IsInputRedirected -and -not $hasPromptProvider)) {
        throw 'ARGUMENTS_REQUIRED: Selection is incomplete and interactive input is unavailable. Supply -Project -Here, -ProjectPath <path>, or -Global together with -Harness.'
    }
}

function Get-BootstrapReleaseField([object]$Metadata, [string]$Name) {
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

function Assert-BootstrapReleaseBoolean([object]$Metadata, [string]$Name, [bool]$Expected) {
    $value = Get-BootstrapReleaseField $Metadata $Name
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

try {
    $scope = $null
    $target = $null
    $needsScope = $true
    if ($PSBoundParameters.ContainsKey('ProjectPath')) {
        if ([string]::IsNullOrEmpty($ProjectPath)) {
            throw 'ARGUMENTS_INVALID: -ProjectPath must not be empty.'
        }
        $scope = 'project'
        $target = $ProjectPath
        $needsScope = $false
    } elseif ($PSBoundParameters.ContainsKey('Global')) {
        if (-not $Global) {
            throw 'ARGUMENTS_INVALID: Select global scope with -Global.'
        }
        $scope = 'global'
        $target = (Get-Location).Path
        $needsScope = $false
    } elseif ($PSBoundParameters.ContainsKey('Project') -or $PSBoundParameters.ContainsKey('Here')) {
        if (-not $Project -or -not $Here) {
            throw 'ARGUMENTS_INVALID: Select the current project with both -Project and -Here.'
        }
        $scope = 'project'
        $target = (Get-Location).Path
        $needsScope = $false
    }

    $needsHarness = -not $PSBoundParameters.ContainsKey('Harness')
    if (-not $needsHarness -and $Harness -notin @('opencode', 'codex', 'all')) {
        throw 'ARGUMENTS_INVALID: -Harness must be opencode, codex, or all.'
    }
    if ($needsScope -or $needsHarness) { Assert-InteractiveInput }

    if ($needsScope) {
        $selection = Read-UninstallScope
        $scope = $selection.Scope
        $target = $selection.Target
    }
    if ($needsHarness) { $selectedHarness = Read-UninstallHarness }
    else { $selectedHarness = $Harness.ToLowerInvariant() }

    $pwsh = @(Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue)
    if ($pwsh.Count -eq 0) {
        throw 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 (pwsh) is required.'
    }

    $launcher = $null
    if ($PSCommandPath) {
        $localLauncher = Join-Path (Split-Path -Parent $PSCommandPath) 'scripts/launch-latest.ps1'
        if (Test-Path -LiteralPath $localLauncher -PathType Leaf) { $launcher = $localLauncher }
    }
    if (-not $launcher) {
        $tempBase = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode'
        [IO.Directory]::CreateDirectory($tempBase) | Out-Null
        $ownedLauncher = Join-Path $tempBase ('olympus-uninstall-entry-' + [guid]::NewGuid().ToString('N') + '.ps1')
        $headers = @{ 'User-Agent' = 'OlympusAgents-Installer' }
        $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest' -Headers $headers -ErrorAction Stop
        Assert-BootstrapReleaseBoolean $release 'immutable' $true
        Assert-BootstrapReleaseBoolean $release 'draft' $false
        Assert-BootstrapReleaseBoolean $release 'prerelease' $false
        $tag = [string](Get-BootstrapReleaseField $release 'tag_name')
        if ($tag -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
            throw "LATEST_RELEASE_INVALID: GitHub latest release returned malformed tag '$tag'."
        }
        $publishedAt = Get-BootstrapReleaseField $release 'published_at'
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
        if ($tag -match '-(?:alpha|beta|rc)\.' -and -not [bool](Get-BootstrapReleaseField $release 'prerelease')) {
            throw "LATEST_RELEASE_METADATA_INCONSISTENT: tag '$tag' is prerelease but GitHub reports prerelease=false."
        }

        $launcherUrl = "https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$tag/scripts/launch-latest.ps1"
        Write-Output "OLYMPUS_BOOTSTRAP_SELECTED: tag=$tag immutable=true source=$launcherUrl"
        Invoke-WebRequest -Uri $launcherUrl -OutFile $ownedLauncher -Headers $headers -ErrorAction Stop
        $launcherText = [IO.File]::ReadAllText($ownedLauncher)
        $requiredLauncherMarkers = @('Assert-ReleaseBoolean', 'LATEST_RELEASE_MUTABLE',
            'LATEST_RELEASE_NOT_PUBLISHED', 'LATEST_RELEASE_IDENTITY_MISMATCH', 'published_at')
        $missingLauncherMarkers = @($requiredLauncherMarkers | Where-Object { -not $launcherText.Contains($_) })
        if ($missingLauncherMarkers.Count -gt 0) {
            throw "LAUNCHER_BOOTSTRAP_CONTRACT_MISSING: Release '$tag' launcher lacks immutable-release checks ($($missingLauncherMarkers -join ', ')); no older launcher fallback is attempted."
        }
        $launcher = $ownedLauncher
    }

    $launcherArgs = @(
        '-NoProfile', '-File', $launcher,
        '-Action', 'uninstall',
        '-Scope', $scope,
        '-Harness', $selectedHarness,
        '-Target', [IO.Path]::GetFullPath($target)
    )
    & $pwsh[0].Source @launcherArgs
    if ($LASTEXITCODE -ne 0) {
        throw "OLYMPUS_ENTRYPOINT_FAILED: launcher returned exit code $LASTEXITCODE."
    }
} finally {
    if ($ownedLauncher -and (Test-Path -LiteralPath $ownedLauncher)) {
        Remove-Item -LiteralPath $ownedLauncher -Force -ErrorAction SilentlyContinue
    }
}
