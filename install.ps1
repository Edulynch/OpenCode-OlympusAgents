# Windows-qualified release acquisition; scripts/bootstrap.ps1 owns all target checks.
[CmdletBinding()]
param(
    [ValidatePattern('^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$')]
    [string]$Version = 'v0.12.10',
    [ValidateSet('global')]
    [string]$Scope = 'global',
    [ValidateSet('opencode')]
    [string]$Harness = 'opencode',
    [switch]$DryRun,
    [switch]$VerifyOnly,
    [switch]$Uninstall,
    [switch]$Update,
    [switch]$Force,
    # Qualification-only source overrides. Source identity is always checked.
    [string]$SourceRoot,
    [string]$SourceArchive,
    # Qualification-only CLI destination overrides; normal installs use user defaults.
    [string]$CliInstallRoot,
    [string]$CliPathStorePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ReleaseVersion = 'v0.12.10' # Must equal this installer's default and the release target tag.
$owned = $null
$ArchiveGeneratedPaths = @(
    'opencode.jsonc',
    '.opencode/agents/atlas.md',
    '.opencode/agents/helios.md',
    '.opencode/agents/kael.md',
    '.opencode/agents/kovan.md',
    '.opencode/agents/nox.md',
    '.opencode/agents/talos.md',
    '.opencode/agents/thales.md',
    '.opencode/agents/vera.md',
    '.opencode/agents/veyra.md',
    '.opencode/plugins/olympus-activity/activity.ts',
    '.opencode/plugins/olympus-activity/tui.tsx',
    '.opencode/scripts/worktree-setup.ps1',
    '.opencode/commands/olympus.ultra.md',
    '.opencode/commands/olympus.performance.md',
    '.opencode/commands/olympus.performance-ultra.md',
    'docs/HARNESS-CAPABILITIES.md'
)

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
                         [string]$InstallRoot, [string]$PathStorePath, [bool]$CompactUpdate = $false,
                         [bool]$Force = $false, [bool]$ValidateOnly = $false) {
    $cliInstaller = Join-Path $Source 'scripts/install-cli.ps1'
    if (-not (Test-Path -LiteralPath $cliInstaller -PathType Leaf)) { throw 'SOURCE_INVALID: Global CLI installer is missing.' }
    $cliArgs = @('-NoProfile', '-File', $cliInstaller, '-Action', $Action,
        '-Version', $Version, '-SourceRoot', $Source)
    if ($InstallRoot) { $cliArgs += @('-InstallRoot', $InstallRoot) }
    if ($PathStorePath) { $cliArgs += @('-PathStorePath', $PathStorePath) }
    if ($Force) { $cliArgs += '-Force' }
    if ($ValidateOnly) { $cliArgs += '-ValidateOnly' }
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

function Get-InstallItemOrNull([string]$Path) {
    try { return Get-Item -LiteralPath $Path -Force -ErrorAction Stop }
    catch {
        if ($_.Exception -is [Management.Automation.ItemNotFoundException] -and
            $_.FullyQualifiedErrorId -like 'PathNotFound,*') { return $null }
        throw "SOURCE_PATH_INSPECTION_FAILED: Cannot inspect '$Path': $($_.Exception.Message)"
    }
}

function Assert-ContainedInstallPath([string]$Boundary, [string]$Root, [string]$Relative, [string]$Kind) {
    if ($Kind -notin @('File','Directory')) { throw 'SOURCE_RENDER_PATH_UNSAFE: Invalid path kind.' }
    $boundaryFull = [IO.Path]::GetFullPath($Boundary)
    $rootFull = [IO.Path]::GetFullPath($Root)
    $boundaryPrefix = $boundaryFull.TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    if ((-not [string]::Equals($rootFull, $boundaryFull, [StringComparison]::OrdinalIgnoreCase) -and
            -not $rootFull.StartsWith($boundaryPrefix, [StringComparison]::OrdinalIgnoreCase)) -or
        ($Relative -and ([IO.Path]::IsPathRooted($Relative) -or
            $Relative -match '(^|[\\/])\.\.?([\\/]|$)'))) {
        throw 'SOURCE_RENDER_PATH_UNSAFE: Render path is outside its owned directory.'
    }
    $relativePath = if ($Relative) { $Relative -replace '/', [IO.Path]::DirectorySeparatorChar } else { '' }
    $targetPath = if ($relativePath) { Join-Path $rootFull $relativePath } else { $rootFull }
    $full = [IO.Path]::GetFullPath($targetPath)
    if (-not $full.StartsWith($boundaryPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'SOURCE_RENDER_PATH_UNSAFE: Render path escapes its owned directory.'
    }
    foreach ($directory in @($boundaryFull, $rootFull)) {
        $item = Get-InstallItemOrNull $directory
        if ($null -eq $item -or -not $item.PSIsContainer -or
            ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "SOURCE_RENDER_PATH_UNSAFE: Render directory is missing, not a directory, or a reparse point: $directory"
        }
    }
    $volume = [IO.Path]::GetPathRoot($full)
    $parts = @($full.Substring($volume.Length) -split '[\\/]' | Where-Object { $_ })
    $cursor = $volume
    for ($index = 0; $index -lt $parts.Count; $index++) {
        $cursor = Join-Path $cursor $parts[$index]
        $item = Get-InstallItemOrNull $cursor
        if ($null -eq $item) { continue }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "SOURCE_RENDER_PATH_UNSAFE: Render path traverses a reparse point: $cursor"
        }
        $isLeaf = $index -eq ($parts.Count - 1)
        if ((-not $isLeaf -or $Kind -eq 'Directory') -and -not $item.PSIsContainer) {
            throw "SOURCE_RENDER_PATH_UNSAFE: Render path has a non-directory component: $cursor"
        }
        if ($isLeaf -and $Kind -eq 'File' -and $item.PSIsContainer) {
            throw "SOURCE_RENDER_PATH_UNSAFE: Render output is a directory: $cursor"
        }
    }
    return $full
}

function Get-ArchiveRenderInventory([string]$Boundary, [string]$Root) {
    [void](Assert-ContainedInstallPath $Boundary $Root '' 'Directory')
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    $files = @{}
    $directories = [System.Collections.Generic.List[string]]::new()
    foreach ($item in @(Get-ChildItem -LiteralPath $Root -Force -Recurse -ErrorAction Stop)) {
        $relative = $item.FullName.Substring($prefix.Length).Replace('\','/')
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "SOURCE_RENDER_STAGE_INVALID: Stage contains a reparse point: $relative"
        }
        if ($item.PSIsContainer) {
            [void](Assert-ContainedInstallPath $Boundary $Root $relative 'Directory')
            $directories.Add($relative)
        } else {
            $path = Assert-ContainedInstallPath $Boundary $Root $relative 'File'
            $files[$relative] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    return [pscustomobject]@{ Files=$files; Directories=@($directories.ToArray()) }
}

function Get-ArchiveGeneratedDirectories {
    $directories = @{}
    foreach ($relative in $ArchiveGeneratedPaths) {
        $parent = Split-Path -Parent ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        while ($parent) {
            $directories[$parent.Replace('\','/')] = $true
            $parent = Split-Path -Parent $parent
        }
    }
    return @($directories.Keys | Sort-Object)
}

function Resolve-Python311 {
    foreach ($name in @('python3.11','python3','python.exe','python')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -eq $command) { continue }
        try {
            & $command.Source -B -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $command.Source }
        } catch {}
    }
    throw 'PYTHON_UNAVAILABLE: Python 3.11+ is required to render tag-archive installs; no environment or package installation was attempted.'
}

function Invoke-ArchiveRender([string]$Source, [string]$OwnedRoot) {
    $python = Resolve-Python311
    $renderer = Assert-ContainedInstallPath $OwnedRoot $Source 'scripts/render_harnesses.py' 'File'
    if (-not (Test-Path -LiteralPath $renderer -PathType Leaf)) {
        throw 'SOURCE_INVALID: Release archive is missing scripts/render_harnesses.py.'
    }
    $stage = Join-Path $OwnedRoot 'render-stage'
    [void](Assert-ContainedInstallPath $OwnedRoot $OwnedRoot 'render-stage' 'Directory')
    [IO.Directory]::CreateDirectory($stage) | Out-Null
    [void](Assert-ContainedInstallPath $OwnedRoot $OwnedRoot 'render-stage' 'Directory')
    $renderOutput = (& $python -B $renderer render --harness opencode --root $Source --output-root $stage 2>&1 | Out-String)
    $renderCode = $LASTEXITCODE
    if ($renderCode -ne 0) {
        throw "SOURCE_RENDERER_FAILED: Rendering archive sources exited $renderCode. $($renderOutput.Trim())"
    }

    $rendered = Get-ArchiveRenderInventory $OwnedRoot $stage
    $expectedPaths = @($ArchiveGeneratedPaths | Sort-Object)
    $actualPaths = @($rendered.Files.Keys | Sort-Object)
    $expectedDirectories = @(Get-ArchiveGeneratedDirectories)
    $actualDirectories = @($rendered.Directories | Sort-Object)
    if ($actualPaths.Count -ne $ArchiveGeneratedPaths.Count -or
        [string]::Join("`n", [string[]]$actualPaths) -cne [string]::Join("`n", [string[]]$expectedPaths) -or
        [string]::Join("`n", [string[]]$actualDirectories) -cne
            [string]::Join("`n", [string[]]$expectedDirectories)) {
        throw "SOURCE_RENDER_STAGE_INVALID: Renderer stage inventory does not match the $($ArchiveGeneratedPaths.Count) expected generated files. $($renderOutput.Trim())"
    }

    $checkOutput = (& $python -B $renderer check --harness opencode --root $Source --output-root $stage 2>&1 | Out-String)
    $checkCode = $LASTEXITCODE
    $checked = Get-ArchiveRenderInventory $OwnedRoot $stage
    $checkedPaths = @($checked.Files.Keys | Sort-Object)
    $stageUnchanged = [string]::Join("`n", [string[]]$checkedPaths) -ceq
        [string]::Join("`n", [string[]]$expectedPaths)
    foreach ($relative in $expectedPaths) {
        if (-not $checked.Files.ContainsKey($relative) -or
            $checked.Files[$relative] -cne $rendered.Files[$relative]) { $stageUnchanged = $false }
    }
    if ($checkCode -ne 0 -or
        $checkOutput -notmatch "HARNESS_RENDER_CHECK: PASS \(opencode; $($ArchiveGeneratedPaths.Count) managed output\(s\); read-only\)" -or
        -not $stageUnchanged -or
        [string]::Join("`n", [string[]]@($checked.Directories | Sort-Object)) -cne
            [string]::Join("`n", [string[]]$expectedDirectories)) {
        throw "SOURCE_RENDERER_CHECK_FAILED: Rendered archive stage failed its read-only inventory check. $($checkOutput.Trim())"
    }

    foreach ($relative in $expectedPaths) {
        $stageFile = Assert-ContainedInstallPath $OwnedRoot $stage $relative 'File'
        $destination = Assert-ContainedInstallPath $OwnedRoot $Source $relative 'File'
        $parentRelative = Split-Path -Parent ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        if ($parentRelative) {
            $parent = Assert-ContainedInstallPath $OwnedRoot $Source $parentRelative 'Directory'
            [IO.Directory]::CreateDirectory($parent) | Out-Null
            [void](Assert-ContainedInstallPath $OwnedRoot $Source $parentRelative 'Directory')
        }
        $destination = Assert-ContainedInstallPath $OwnedRoot $Source $relative 'File'
        $temporaryName = '.olympus-render-' + [guid]::NewGuid().ToString('N') + '.tmp'
        $temporaryRelative = if ($parentRelative) { Join-Path $parentRelative $temporaryName } else { $temporaryName }
        $temporary = Assert-ContainedInstallPath $OwnedRoot $Source $temporaryRelative 'File'
        $backup = $null
        try {
            [IO.File]::Copy($stageFile, $temporary)
            if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant() -cne
                $rendered.Files[$relative]) {
                throw "SOURCE_RENDER_COPY_FAILED: Staged bytes changed while copying '$relative'."
            }
            $existing = Get-InstallItemOrNull $destination
            if ($null -ne $existing) {
                [void](Assert-ContainedInstallPath $OwnedRoot $Source $relative 'File')
                $backupName = '.olympus-render-' + [guid]::NewGuid().ToString('N') + '.bak'
                $backupRelative = if ($parentRelative) { Join-Path $parentRelative $backupName } else { $backupName }
                $backup = Assert-ContainedInstallPath $OwnedRoot $Source $backupRelative 'File'
                if ($null -ne (Get-InstallItemOrNull $backup)) {
                    throw "SOURCE_RENDER_COPY_FAILED: Temporary backup path already exists for '$relative'."
                }
                [IO.File]::Replace($temporary, $destination, $backup)
                [IO.File]::Delete($backup)
            } else {
                [IO.File]::Move($temporary, $destination)
            }
            if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -cne
                $rendered.Files[$relative]) {
                throw "SOURCE_RENDER_COPY_FAILED: Destination bytes do not match the verified render for '$relative'."
            }
        } finally {
            $temporaryItem = Get-InstallItemOrNull $temporary
            if ($null -ne $temporaryItem) {
                [void](Assert-ContainedInstallPath $OwnedRoot $Source $temporaryRelative 'File')
                [IO.File]::Delete($temporary)
            }
            if ($backup) {
                $backupItem = Get-InstallItemOrNull $backup
                if ($null -ne $backupItem) {
                    [void](Assert-ContainedInstallPath $OwnedRoot $Source $backupRelative 'File')
                    [IO.File]::Delete($backup)
                }
            }
        }
    }
    Write-Output "OLYMPUS_SOURCE_RENDER: PASS ($($ArchiveGeneratedPaths.Count) generated files; isolated stage checked read-only before install)"
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: Olympus installer is Windows-qualified only.' }
    if ($ReleaseVersion -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
        throw 'INSTALLER_RELEASE_VERSION_INVALID: Embedded release identity is malformed.'
    }
    if ($Version -cne $Version.Trim()) { throw 'VERSION_INVALID: Whitespace is not allowed.' }
    if ($VerifyOnly -and $DryRun) { throw 'VERIFY_MODE_INVALID: -VerifyOnly and -DryRun cannot be combined.' }
    if ($VerifyOnly -and $Uninstall) { throw 'VERIFY_MODE_INVALID: -VerifyOnly and -Uninstall cannot be combined.' }
    if ($Force -and ($Uninstall -or $DryRun -or $VerifyOnly)) {
        throw 'UPDATE_FORCE_MODE_INVALID: -Force cannot be combined with uninstall, dry-run, or VerifyOnly.'
    }
    if ($Force) { $Update = $true }
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
    if ($origin -in @('LOCAL_ARCHIVE','REMOTE_ARCHIVE') -and -not $Uninstall) {
        Invoke-ArchiveRender -Source $source -OwnedRoot $owned
    }
    $globalArgs = @('-NoProfile', '-File', $globalScript, '-Harness', 'opencode', '-SourceVersion', $resolvedVersion)
    if ($VerifyOnly) { $globalArgs += '-VerifyOnly' }
    if ($DryRun) { $globalArgs += '-DryRun' }
    if ($Uninstall) { $globalArgs += '-Uninstall' }
    if ($Update) { $globalArgs += '-Update' }
    if ($Force) { $globalArgs += '-Force' }
    if (-not $Uninstall -and -not $DryRun -and -not $VerifyOnly) {
        Set-UpGlobalCli -Source $source -Version $resolvedVersion -Action 'install' `
            -InstallRoot $CliInstallRoot -PathStorePath $CliPathStorePath `
            -CompactUpdate ($Update -and $env:OLYMPUS_UPDATE_COMPACT -ceq '1') `
            -Force $Force -ValidateOnly $true
    }
    & $pwsh.Source @globalArgs
    if ($LASTEXITCODE -ne 0) { throw "GLOBAL_BOOTSTRAP_FAILED: global installer exited $LASTEXITCODE." }
    if (-not $DryRun -and -not $VerifyOnly) {
        $cliAction = if ($Uninstall) { 'uninstall' } else { 'install' }
        Set-UpGlobalCli -Source $source -Version $resolvedVersion -Action $cliAction `
            -InstallRoot $CliInstallRoot -PathStorePath $CliPathStorePath `
            -CompactUpdate ($Update -and $env:OLYMPUS_UPDATE_COMPACT -ceq '1') -Force $Force
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
