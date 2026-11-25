# Resolves the latest published Olympus release, then delegates to that immutable release installer.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'uninstall')]
    [string]$Action,
    [switch]$DryRun,
    [switch]$Update,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$owned = $null
$script:UpdateNativeStarted = $false
$script:CompactUpdate = $false

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

function Test-UpdateManagedCliRelative([string]$Relative) {
    $value = $Relative.Replace('\','/')
    return (-not [IO.Path]::IsPathRooted($value) -and
        $value -notmatch '[\x00-\x1f:*?"<>|]' -and $value -notmatch '(^|/)/' -and
        $value -notmatch '(^|/)\.\.?(/|$)' -and $value -notmatch '(^|/)$' -and
        ($value.StartsWith('olympus/') -or $value.StartsWith('scripts/') -or
         $value -ceq 'install.ps1' -or $value -ceq 'opencode.jsonc' -or
         $value -match '^\.opencode/'))
}

function Get-ExistingUpdateCliItem([string]$Path) {
    try { return Get-Item -LiteralPath $Path -Force -ErrorAction Stop }
    catch {
        if ($_.Exception -is [Management.Automation.ItemNotFoundException] -or
            $_.FullyQualifiedErrorId -like 'PathNotFound,*') { return $null }
        throw 'UPDATE_CLI_VERSION_UNKNOWN: An active CLI path could not be inspected safely.'
    }
}

function Assert-SafeUpdateCliPath([string]$Path, [string]$Expected = 'Any') {
    if (-not [IO.Path]::IsPathFullyQualified($Path)) {
        throw 'UPDATE_CLI_VERSION_UNKNOWN: An active CLI path is not absolute.'
    }
    $full = [IO.Path]::GetFullPath($Path)
    $volume = [IO.Path]::GetPathRoot($full)
    $cursor = $volume
    $parts = @($full.Substring($volume.Length) -split '[\\/]' | Where-Object { $_ })
    for ($index = 0; $index -lt $parts.Count; $index++) {
        $cursor = Join-Path $cursor $parts[$index]
        $item = Get-ExistingUpdateCliItem $cursor
        if ($null -eq $item) { break }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI path traverses a reparse point.'
        }
        $isLeaf = $index -eq ($parts.Count - 1)
        if (-not $isLeaf -and -not $item.PSIsContainer) {
            throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI path has a non-directory parent.'
        }
        if ($isLeaf -and $Expected -eq 'Container' -and -not $item.PSIsContainer) {
            throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI path is not a directory.'
        }
        if ($isLeaf -and $Expected -eq 'Leaf' -and $item.PSIsContainer) {
            throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI path is not a file.'
        }
    }
    return $full
}

function Get-InstalledGlobalVersion([switch]$AllowSplit, [switch]$AllowMissingCliPayload) {
    $root = $null
    if ($env:OPENCODE_CONFIG_DIR) { $root = [IO.Path]::GetFullPath($env:OPENCODE_CONFIG_DIR) }
    else {
        $commands = @(Get-Command opencode -CommandType Application -ErrorAction SilentlyContinue)
        if ($commands.Count -eq 0) {
            throw 'UPDATE_INSTALLATION_UNKNOWN: OpenCode configuration could not be resolved; set OPENCODE_CONFIG_DIR to the installed global root or run olympus doctor.'
        }
        $paths = @(& $commands[0].Source debug paths 2>$null | ForEach-Object {
            if ($_ -match '^\s*config\s{2,}(.+?)\s*$') { $Matches[1].Trim() }
        })
        if ($LASTEXITCODE -ne 0 -or $paths.Count -ne 1 -or -not [IO.Path]::IsPathFullyQualified($paths[0])) {
            throw 'UPDATE_INSTALLATION_UNKNOWN: OpenCode configuration could not be resolved; set OPENCODE_CONFIG_DIR to the installed global root or run olympus doctor.'
        }
        $root = $paths[0]
    }
    if (-not $root -or -not [IO.Path]::IsPathFullyQualified($root) -or
        [IO.Path]::GetFullPath($root) -eq [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($root))) {
        throw 'UPDATE_INSTALLATION_UNKNOWN: The global OpenCode configuration root is unavailable or unsafe; run olympus doctor before updating.'
    }
    $manifestPath = Join-Path $root 'olympus/orchestrator-install.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw 'UPDATE_INSTALLATION_UNKNOWN: No managed global Olympus installation was found; run olympus install before updating.'
    }
    try { $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json -Depth 30 -ErrorAction Stop }
    catch { throw 'UPDATE_MANIFEST_INVALID: The installed Olympus version record is unreadable; run olympus doctor before updating.' }
    if ($null -eq $manifest -or $null -eq $manifest.PSObject.Properties['scope'] -or
        $null -eq $manifest.PSObject.Properties['installed_harnesses'] -or
        $null -eq $manifest.PSObject.Properties['installed_version'] -or
        $manifest.scope -cne 'global' -or @($manifest.installed_harnesses).Count -ne 1 -or
        [string]$manifest.installed_harnesses[0] -cne 'opencode') {
        throw 'UPDATE_MANIFEST_INVALID: The installed Olympus version record is not a supported global installation; run olympus doctor before updating.'
    }
    $installed = [string]$manifest.installed_version
    if (-not [regex]::IsMatch($installed, '\Av(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?\z')) {
        throw 'UPDATE_VERSION_UNKNOWN: The global installation has no recognized release version; run olympus doctor and reinstall before updating.'
    }

    $cliRoot = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Programs/Olympus' } else { $null }
    if (-not $cliRoot -or -not [IO.Path]::IsPathFullyQualified($cliRoot)) {
        throw 'UPDATE_CLI_VERSION_UNKNOWN: The global CLI installation root is unavailable; run olympus install to repair it before updating.'
    }
    $cliRoot = [IO.Path]::GetFullPath($cliRoot)
    if ($cliRoot -eq [IO.Path]::GetPathRoot($cliRoot)) {
        throw 'UPDATE_CLI_VERSION_UNKNOWN: The global CLI installation root is unsafe; run olympus install to repair it before updating.'
    }
    Write-Verbose "Active global CLI installation path: $cliRoot"
    $currentPath = Join-Path $cliRoot 'current.txt'
    [void](Assert-SafeUpdateCliPath $currentPath 'Leaf')
    if (-not (Test-Path -LiteralPath $currentPath -PathType Leaf)) {
        throw 'UPDATE_CLI_VERSION_UNKNOWN: The global CLI current.txt pointer is missing; run olympus install to repair it before updating.'
    }
    $pointer = [IO.File]::ReadAllText($currentPath)
    $pointerMatch = [regex]::Match($pointer, '\A(?<version>v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?)(?:\r?\n)?\z')
    if (-not $pointerMatch.Success) {
        throw 'UPDATE_CLI_VERSION_UNKNOWN: The global CLI current.txt pointer is malformed; run olympus doctor before updating.'
    }
    $cliVersion = $pointerMatch.Groups['version'].Value
    $versionRoot = Join-Path $cliRoot ("versions/" + $cliVersion)
    $cliManifestPath = Join-Path $versionRoot 'olympus-cli-manifest.json'
    [void](Assert-SafeUpdateCliPath $versionRoot 'Container')
    [void](Assert-SafeUpdateCliPath $cliManifestPath 'Leaf')
    if (-not (Test-Path -LiteralPath $versionRoot -PathType Container) -or
        -not (Test-Path -LiteralPath $cliManifestPath -PathType Leaf)) {
        throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI release or its ownership marker is missing; run olympus install to repair it before updating.'
    }
    try { $cliManifest = [IO.File]::ReadAllText($cliManifestPath) | ConvertFrom-Json -Depth 30 -ErrorAction Stop }
    catch { throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI ownership marker is unreadable; run olympus doctor before updating.' }
    $manifestProperties = if ($null -ne $cliManifest) {
        @($cliManifest.PSObject.Properties | ForEach-Object Name)
    } else { @() }
    if ($manifestProperties.Count -ne 3 -or
        @('schema_version','version','files' | Where-Object { $_ -cnotin $manifestProperties }).Count -gt 0 -or
        ($cliManifest.schema_version -isnot [int] -and $cliManifest.schema_version -isnot [long]) -or
        $cliManifest.schema_version -ne 1 -or $cliManifest.version -isnot [string] -or
        $cliManifest.version -cne $cliVersion -or
        $cliManifest.files -isnot [System.Collections.IList] -or @($cliManifest.files).Count -eq 0) {
        throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI ownership marker does not match current.txt; run olympus doctor before updating.'
    }

    $cliFileMap = @{}
    $seenCliFiles = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in @($cliManifest.files)) {
        $entryProperties = if ($null -ne $entry) {
            @($entry.PSObject.Properties | ForEach-Object Name)
        } else { @() }
        if ($entryProperties.Count -ne 2 -or
            @('path','sha256' | Where-Object { $_ -cnotin $entryProperties }).Count -gt 0 -or
            $entry.path -isnot [string] -or $entry.sha256 -isnot [string]) {
            throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI ownership marker has an incomplete file receipt; run olympus doctor before updating.'
        }
        $relative = ([string]$entry.path).Replace('\','/')
        if (-not (Test-UpdateManagedCliRelative $relative) -or
            -not $seenCliFiles.Add($relative) -or $entry.sha256 -notmatch '^(?i:[0-9a-f]{64})$') {
            throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI ownership marker contains an unsafe or duplicate file receipt.'
        }
        $cliFileMap[$relative] = ([string]$entry.sha256).ToLowerInvariant()
    }
    foreach ($relative in @('install.ps1', 'scripts/olympus_cli.py', 'scripts/launch-latest.ps1')) {
        if (-not $cliFileMap.ContainsKey($relative)) {
            throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI ownership marker does not prove a required release file; run olympus install to repair it before updating.'
        }
        $identityPath = Join-Path $versionRoot ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        [void](Assert-SafeUpdateCliPath $identityPath 'Leaf')
        if (-not (Test-Path -LiteralPath $identityPath -PathType Leaf)) {
            if ($AllowMissingCliPayload -and $relative -cne 'install.ps1') { continue }
            throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI ownership marker is missing a required release file; run olympus install to repair it before updating.'
        }
    }
    $identityPath = Join-Path $versionRoot 'install.ps1'
    if (Test-Path -LiteralPath $identityPath -PathType Leaf) {
        $identityHash = (Get-FileHash -LiteralPath $identityPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($identityHash -ceq $cliFileMap['install.ps1']) {
            $identityText = [IO.File]::ReadAllText($identityPath)
            $defaultMatch = [regex]::Match($identityText, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''\s*,?\s*$')
            $releaseMatch = [regex]::Match($identityText, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''\s*(?:#.*)?$')
            if (-not $defaultMatch.Success -or -not $releaseMatch.Success -or
                $defaultMatch.Groups[1].Value -cne $cliVersion -or $releaseMatch.Groups[1].Value -cne $cliVersion) {
                throw 'UPDATE_CLI_VERSION_UNKNOWN: The receipt-bound active CLI identity does not match current.txt; run olympus doctor before updating.'
            }
        } else {
            throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI identity file differs from its ownership receipt; run olympus doctor before updating.'
        }
    } else {
        throw 'UPDATE_CLI_VERSION_UNKNOWN: The active CLI identity file is missing; run olympus doctor before updating.'
    }
    if ($installed -cne $cliVersion -and -not $AllowSplit) {
        throw "UPDATE_VERSION_MISMATCH: Global OpenCode is $installed but the active CLI is $cliVersion; run olympus doctor and repair the installation before updating."
    }
    return [pscustomobject]@{ GlobalVersion=$installed; CliVersion=$cliVersion }
}

try {
    if ($Force -and ($Action -ne 'install' -or $DryRun)) {
        throw 'UPDATE_FORCE_MODE_INVALID: -Force is available only for a non-dry-run install/update.'
    }
    if ($Force) { $Update = $true }
    if ($DryRun -and $Action -ne 'install') {
        throw 'DRY_RUN_UNSUPPORTED: -DryRun is available only for install.'
    }
    if ($Update -and ($Action -ne 'install' -or $DryRun)) {
        throw 'UPDATE_MODE_INVALID: -Update is available only for a normal install.'
    }
    $installed = $null
    if ($Update) {
        $installed = Get-InstalledGlobalVersion -AllowSplit:$Force -AllowMissingCliPayload:$Force
        $script:CompactUpdate = $env:OLYMPUS_UPDATE_COMPACT -ceq '1'
        if ($installed.GlobalVersion -ceq $installed.CliVersion) {
            Write-Verbose "Global OpenCode and active CLI version markers match at $($installed.GlobalVersion); update preflight does not verify file integrity."
        } else {
            Write-Verbose "Global OpenCode version is $($installed.GlobalVersion); active CLI version is $($installed.CliVersion); force repair preflight does not verify file integrity."
        }
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
        $installedForComparison = $installed.GlobalVersion
        if ($Force) {
            $splitComparison = Compare-ReleaseTag $installed.GlobalVersion $installed.CliVersion
            if ($splitComparison -ge 0) { $installedForComparison = $installed.GlobalVersion }
            else { $installedForComparison = $installed.CliVersion }
            foreach ($identity in @($installed.GlobalVersion, $installed.CliVersion)) {
                if ((Compare-ReleaseTag $tag $identity) -lt 0) {
                    throw "UPDATE_DOWNGRADE_BLOCKED: Latest stable release $tag is older than installed $identity; no downgrade was started."
                }
            }
        }
        $comparison = Compare-ReleaseTag $tag $installedForComparison
        Write-Verbose "Latest stable release tag is $tag."
        if ($comparison -le 0 -and -not $Force) {
            if ($comparison -eq 0) { Write-Output "Already up to date ($($installed.GlobalVersion))." }
            else { Write-Output "Already up to date ($installedForComparison is newer than latest stable $tag)." }
            $global:LASTEXITCODE = 0
            return
        }
        if ($Force) {
            Write-Output "Repairing Olympus from global=$($installed.GlobalVersion) cli=$($installed.CliVersion) to $tag..."
        } else {
            Write-Output "Updating Olympus from $($installed.GlobalVersion) to $tag..."
        }
    }
    if (-not $script:CompactUpdate) {
        Write-Output "OLYMPUS_RELEASE_SELECTED: tag=$tag immutable=true published_at=$($publishedTimestamp.ToUniversalTime().ToString('o'))"
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
    if ($Force) { $args += '-Force' }
    if ($DryRun) { $args += '-DryRun' }

    if (-not $script:CompactUpdate) {
        Write-Output "OLYMPUS_ENTRYPOINT: action=$Action scope=global harness=opencode release=$tag"
        Write-Output "OLYMPUS_RELEASE_EXECUTING: tag=$tag installer=$installerUrl"
    }
    if ($Update) { $script:UpdateNativeStarted = $true }
    & $pwsh[0].Source @args
    if ($LASTEXITCODE -ne 0) {
        $installerExitCode = $LASTEXITCODE
        if ($Update) {
            Write-Output "Update failed; native installer exited $installerExitCode. Effects may be partial; inspect olympus doctor before retrying."
            exit $installerExitCode
        }
        Write-Output "OLYMPUS_ENTRYPOINT_FAILED: release installer exited $installerExitCode."
        exit $installerExitCode
    }
    if ($Update) {
        $installed = Get-InstalledGlobalVersion
        if ($installed.GlobalVersion -cne $tag -or $installed.CliVersion -cne $tag) {
            throw "UPDATE_RESULT_UNCONFIRMED: The installer returned success, but global OpenCode and CLI are not both $tag."
        }
        Write-Output "Updated to $tag."
    }
    if (-not $script:CompactUpdate) { Write-Output "OLYMPUS_RELEASE_EXECUTED: tag=$tag exit_code=0" }
} catch {
    if ($Update) {
        Write-Error $_.Exception.Message -ErrorAction Continue
        if ($script:UpdateNativeStarted) {
            Write-Output 'Update effects are unconfirmed; inspect olympus doctor before retrying.'
            exit 4
        }
        Write-Output 'Update did not start; no installation changes were made.'
        exit 3
    }
    throw
} finally {
    if ($owned -and (Test-Path -LiteralPath $owned)) {
        Remove-Item -LiteralPath $owned -Recurse -Force -ErrorAction SilentlyContinue
    }
}
