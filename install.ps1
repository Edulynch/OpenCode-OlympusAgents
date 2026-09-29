# Windows-qualified release acquisition; scripts/bootstrap.ps1 owns all target checks.
[CmdletBinding()]
param(
    [ValidatePattern('^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$')]
    [string]$Version = 'v0.3.0-beta.3',
    [string]$Target = (Get-Location).Path,
    [switch]$DryRun,
    [switch]$VerifyOnly,
    # Qualification-only source overrides. Source identity is always checked.
    [string]$SourceRoot,
    [string]$SourceArchive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ReleaseVersion = 'v0.3.0-beta.3' # Must equal this installer's default and published tag.
$owned = $null

function Get-ContentHash([string]$Path) {
    $utf8 = [Text.UTF8Encoding]::new($false)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $utf8.GetBytes([IO.File]::ReadAllText($Path))
        ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
    } finally { $sha.Dispose() }
}

function Get-ManagedSourcePaths([string]$BootstrapPath) {
    $text = [IO.File]::ReadAllText($BootstrapPath)
    $block = [regex]::Match($text, '(?ms)^\s*\$Managed\s*=\s*@\(\s*(?<body>.*?)^\s*\)')
    if (-not $block.Success) { throw 'SOURCE_INVALID: Cannot read the release managed-file inventory.' }
    $paths = [System.Collections.Generic.List[string]]::new()
    foreach ($line in ($block.Groups['body'].Value -split '\r?\n')) {
        $item = $line.Trim()
        if (-not $item -or $item.StartsWith('#')) { continue }
        $match = [regex]::Match($item, '^(?:"(?<double>[^"]+)"|''(?<single>[^'']+)'')\s*,?$')
        if (-not $match.Success) { throw 'SOURCE_INVALID: Release managed-file inventory is not a literal path list.' }
        $path = if ($match.Groups['double'].Success) { $match.Groups['double'].Value } else { $match.Groups['single'].Value }
        if ([IO.Path]::IsPathRooted($path) -or $path -match '(^|[/\\])\.\.([/\\]|$)' -or $paths.Contains($path)) {
            throw "SOURCE_INVALID: Invalid or duplicate managed path '$path'."
        }
        $paths.Add($path.Replace('\', '/'))
    }
    if ($paths.Count -eq 0) { throw 'SOURCE_INVALID: Release managed-file inventory is empty.' }
    return @($paths)
}

function Assert-InstalledRelease([string]$Source, [string]$RequestedVersion, [string]$ProjectPath) {
    $pathRoot = [IO.Path]::GetPathRoot($ProjectPath)
    $driveAbsolute = $ProjectPath -match '^[A-Za-z]:[\\/]'
    $uncAbsolute = $ProjectPath -match '^\\\\[^\\]+\\[^\\]+'
    if (-not $pathRoot -or (-not $driveAbsolute -and -not $uncAbsolute)) { throw 'MANAGED_FILE_MISMATCH: Target must be an absolute project-root path.' }
    $targetItem = Get-Item -LiteralPath $ProjectPath -ErrorAction Stop
    if (-not $targetItem.PSIsContainer) { throw 'MANAGED_FILE_MISMATCH: Target is not a directory.' }
    $target = (Resolve-Path -LiteralPath $ProjectPath -ErrorAction Stop).Path
    $git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue
    if (-not $git) { throw 'MANAGED_FILE_MISMATCH: Git is required to identify the target project root.' }
    $gitRoot = (& $git.Source -C $target rev-parse --show-toplevel 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $gitRoot) { throw 'MANAGED_FILE_MISMATCH: Target is not a Git project.' }
    $gitRoot = (Resolve-Path -LiteralPath $gitRoot -ErrorAction Stop).Path
    if (-not [string]::Equals($target.TrimEnd('\','/'), $gitRoot.TrimEnd('\','/'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'MANAGED_FILE_MISMATCH: Target must be the Git worktree root.'
    }

    $bootstrap = Join-Path $Source 'scripts/bootstrap.ps1'
    if (-not (Test-Path -LiteralPath $bootstrap -PathType Leaf)) { throw 'SOURCE_INVALID: Release source has no bootstrap script.' }
    $managed = @(Get-ManagedSourcePaths $bootstrap)
    $sourceAgents = @($managed | Where-Object { $_ -match '^\.opencode/agents/[^/]+\.md$' } | Sort-Object)
    if ($sourceAgents.Count -eq 0) { throw 'SOURCE_INVALID: Release source declares no agent roster.' }

    $manifestPath = Join-Path $target '.opencode/orchestrator-install.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw 'MANAGED_FILE_MISMATCH: Olympus install manifest is missing.'
    }
    try { $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json }
    catch { throw 'MANAGED_FILE_MISMATCH: Olympus install manifest is invalid.' }
    if ($manifest.schema_version -ne 1 -or $null -eq $manifest.managed_files) {
        throw 'MANAGED_FILE_MISMATCH: Olympus install manifest schema or managed file set is unsupported.'
    }

    # A recorded version is useful evidence, never the sole integrity check. Old
    # manifests may omit it (or record local); release bytes below remain decisive.
    $manifestProperties = @($manifest.PSObject.Properties | ForEach-Object Name)
    if ('installed_version' -in $manifestProperties) {
        $recordedVersion = [string]$manifest.installed_version
        if ($recordedVersion -and $recordedVersion -notin @('unknown', 'local') -and $recordedVersion -cne $RequestedVersion) {
            throw "INSTALLED_VERSION_MISMATCH: manifest records '$recordedVersion'; requested '$RequestedVersion'."
        }
    }

    $entries = @($manifest.managed_files)
    $entryPaths = [System.Collections.Generic.List[string]]::new()
    $entryByPath = @{}
    foreach ($entry in $entries) {
        $path = ([string]$entry.path).Replace('\', '/')
        if (-not $path -or $entryByPath.ContainsKey($path)) {
            throw 'MANAGED_FILE_MISMATCH: Manifest contains an empty or duplicate managed path.'
        }
        $entryPaths.Add($path)
        $entryByPath[$path] = $entry
    }
    if ($entryPaths.Count -ne $managed.Count -or @($managed | Where-Object { $_ -notin $entryPaths }).Count -gt 0 -or
        @($entryPaths | Where-Object { $_ -notin $managed }).Count -gt 0) {
        throw 'MANAGED_FILE_MISMATCH: Installed managed file set differs from the requested release.'
    }

    foreach ($path in $managed) {
        $sourceFile = Join-Path $Source ($path -replace '/', [IO.Path]::DirectorySeparatorChar)
        $targetFile = Join-Path $target ($path -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf)) {
            throw "SOURCE_INVALID: Release managed file is missing: $path"
        }
        if (-not (Test-Path -LiteralPath $targetFile -PathType Leaf)) {
            throw "MANAGED_FILE_MISMATCH: Installed managed file is missing: $path"
        }
        $sourceHash = Get-ContentHash $sourceFile
        $targetHash = Get-ContentHash $targetFile
        if ($targetHash -cne $sourceHash -or [string]$entryByPath[$path].sha256 -notmatch ('(?i)^' + [regex]::Escape($targetHash) + '$')) {
            throw "MANAGED_FILE_MISMATCH: Installed managed content differs from release source: $path"
        }
    }

    $installedAgents = @($entryPaths | Where-Object { $_ -match '^\.opencode/agents/[^/]+\.md$' } | Sort-Object)
    if ($installedAgents.Count -ne $sourceAgents.Count -or @($sourceAgents | Where-Object { $_ -notin $installedAgents }).Count -gt 0) {
        throw 'ROSTER_MISMATCH: Installed agent roster differs from the requested release.'
    }
    $sourceAgentIds = @($sourceAgents | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_) })
    $knownOlympusAgents = @('kael','veyra','orin','kovan','nox','vera','thales','sorin','atlas','argus','talos','helios','aegis','maintenance')
    $activeAgentDirectory = Join-Path $target '.opencode/agents'
    foreach ($retired in @($knownOlympusAgents | Where-Object { $_ -notin $sourceAgentIds })) {
        if (Test-Path -LiteralPath (Join-Path $activeAgentDirectory ($retired + '.md'))) {
            throw "ROSTER_MISMATCH: Agent '$retired' is not part of the requested release roster."
        }
    }
    if ($RequestedVersion -ceq 'v0.3.0-beta.3' -and '.opencode/agents/aegis.md' -notin $sourceAgents) {
        throw 'ROSTER_MISMATCH: beta.3 release source does not include the managed Aegis agent.'
    }

    $opencode = Get-Command opencode -ErrorAction SilentlyContinue
    if (-not $opencode) { throw 'ROSTER_MISMATCH: OpenCode CLI is required to validate the active agent roster.' }
    Push-Location $target
    try {
        $agentJson = (& opencode debug agents 2>&1 | Out-String)
        $agentExitCode = $LASTEXITCODE
    } finally { Pop-Location }
    if ($agentExitCode -ne 0) { throw 'ROSTER_MISMATCH: OpenCode could not resolve the active agent roster.' }
    try { $activeAgents = $agentJson | ConvertFrom-Json }
    catch { throw 'ROSTER_MISMATCH: OpenCode returned an invalid active agent roster.' }
    foreach ($agentId in $sourceAgentIds) {
        if (@($activeAgents | Where-Object { $_.id -ceq $agentId }).Count -ne 1) {
            throw "ROSTER_MISMATCH: Expected exactly one active '$agentId' agent from the requested release."
        }
    }
    foreach ($retired in @($knownOlympusAgents | Where-Object { $_ -notin $sourceAgentIds })) {
        if (@($activeAgents | Where-Object { $_.id -ceq $retired }).Count -gt 0) {
            throw "ROSTER_MISMATCH: Retired or unexpected '$retired' agent is active."
        }
    }
    if ($RequestedVersion -ceq 'v0.3.0-beta.3' -and @($activeAgents | Where-Object { $_.id -ceq 'maintenance' }).Count -gt 0) {
        throw 'ROSTER_MISMATCH: maintenance is active in the beta.3 roster.'
    }
}

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
    if ($VerifyOnly -and $DryRun) { throw 'VERIFY_MODE_INVALID: -VerifyOnly and -DryRun cannot be combined.' }
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

    if ($VerifyOnly) {
        Assert-InstalledRelease $source $Version $Target
        Write-Output "OLYMPUS_VERIFY: $Version PASS"
        exit 0
    }

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
