[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'uninstall')]
    [string]$Action,
    [string]$Version,
    [string]$SourceRoot,
    [string]$InstallRoot,
    [string]$PathStorePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$script:CliGeneratedCommandFiles = @(
    '.opencode/commands/olympus.ultra.md',
    '.opencode/commands/olympus.performance.md'
)

function Fail([string]$Code, [string]$Message) { throw "$Code`: $Message" }

function Get-ExistingCliItem([string]$Path) {
    try { return Get-Item -LiteralPath $Path -Force -ErrorAction Stop }
    catch {
        if ($_.Exception -is [Management.Automation.ItemNotFoundException] -and
            $_.FullyQualifiedErrorId -like 'PathNotFound,*') { return $null }
        Fail 'CLI_PATH_INSPECTION_FAILED' "Cannot inspect path '$Path': $($_.Exception.Message)"
    }
}

function Assert-SafeCliPath([string]$Path, [string]$Expected = 'Any') {
    if (-not [IO.Path]::IsPathFullyQualified($Path)) { Fail 'CLI_PATH_INVALID' "CLI path is not absolute: $Path" }
    $full = [IO.Path]::GetFullPath($Path)
    $volume = [IO.Path]::GetPathRoot($full)
    if (-not $volume) { Fail 'CLI_PATH_INVALID' "CLI path has no filesystem root: $Path" }
    $item = Get-ExistingCliItem $volume
    if ($null -eq $item -or -not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Fail 'CLI_PATH_UNSAFE' "CLI path traverses an unsafe filesystem root: $Path"
    }
    $parts = @($full.Substring($volume.Length) -split '[\\/]' | Where-Object { $_ })
    $cursor = $volume
    for ($index = 0; $index -lt $parts.Count; $index++) {
        $cursor = Join-Path $cursor $parts[$index]
        $item = Get-ExistingCliItem $cursor
        if ($null -eq $item) { break }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Fail 'CLI_PATH_UNSAFE' "CLI path traverses a reparse point: $Path"
        }
        $isLeaf = $index -eq ($parts.Count - 1)
        if ((-not $isLeaf -or $Expected -eq 'Container') -and -not $item.PSIsContainer) {
            Fail 'CLI_PATH_UNSAFE' "CLI path has a non-directory component: $Path"
        }
        if ($isLeaf -and $Expected -eq 'Leaf' -and $item.PSIsContainer) {
            Fail 'CLI_PATH_UNSAFE' "CLI file path is a directory: $Path"
        }
    }
    return [IO.Path]::GetFullPath($Path)
}

function Get-CliDirectoryItems([string]$Path) {
    try { return @(Get-ChildItem -LiteralPath $Path -Directory -Force -ErrorAction Stop) }
    catch { Fail 'CLI_PATH_INSPECTION_FAILED' "Cannot enumerate path '$Path': $($_.Exception.Message)" }
}

function Get-CliCleanupDirectories([string]$Root) {
    $directories = [System.Collections.Generic.List[string]]::new()
    $pending = [System.Collections.Generic.Stack[string]]::new()
    $pending.Push($Root)
    while ($pending.Count -gt 0) {
        $parent = $pending.Pop()
        [void](Assert-SafeCliPath $parent 'Container')
        foreach ($child in (Get-CliDirectoryItems $parent)) {
            $item = Get-ExistingCliItem $child.FullName
            if ($null -eq $item -or -not $item.PSIsContainer -or
                ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
            $path = Assert-SafeCliPath $item.FullName 'Container'
            $directories.Add($path)
            $pending.Push($path)
        }
    }
    return $directories.ToArray()
}

function Remove-EmptyCliDirectory([string]$Path) {
    $item = Get-ExistingCliItem $Path
    if ($null -eq $item) { return }
    [void](Assert-SafeCliPath $Path 'Container')
    try { $children = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction Stop) }
    catch { Fail 'CLI_PATH_INSPECTION_FAILED' "Cannot enumerate path '$Path': $($_.Exception.Message)" }
    if ($children.Count -eq 0) {
        [void](Assert-SafeCliPath $Path 'Container')
        [IO.Directory]::Delete($Path)
    }
}

function Get-ReleaseIdentity([string]$Root) {
    $path = Join-Path $Root 'install.ps1'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { Fail 'SOURCE_INVALID' 'The Olympus release identity is missing.' }
    $text = [IO.File]::ReadAllText($path)
    $default = [regex]::Match($text, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''')
    $marker = [regex]::Match($text, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''')
    if (-not $default.Success -or -not $marker.Success -or $default.Groups[1].Value -cne $marker.Groups[1].Value -or
        $default.Groups[1].Value -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
        Fail 'SOURCE_INVALID' 'The Olympus release identity is malformed or contradictory.'
    }
    return $default.Groups[1].Value
}

function Get-FileSha256([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }

function Compare-ReleaseTag([string]$Left, [string]$Right) {
    $pattern = '^v(?<major>0|[1-9][0-9]*)\.(?<minor>0|[1-9][0-9]*)\.(?<patch>0|[1-9][0-9]*)(?:-(?<stage>alpha|beta|rc)\.(?<sequence>0|[1-9][0-9]*))?$'
    $a = [regex]::Match($Left, $pattern)
    $b = [regex]::Match($Right, $pattern)
    if (-not $a.Success -or -not $b.Success) { Fail 'CLI_VERSION_CONFLICT' 'Cannot compare an unrecognized Olympus release tag.' }
    foreach ($part in @('major','minor','patch')) {
        $comparison = ([long]$a.Groups[$part].Value).CompareTo([long]$b.Groups[$part].Value)
        if ($comparison -ne 0) { return $comparison }
    }
    $aStable = -not $a.Groups['stage'].Success
    $bStable = -not $b.Groups['stage'].Success
    if ($aStable -ne $bStable) { return $(if ($aStable) { 1 } else { -1 }) }
    if ($aStable) { return 0 }
    $order = @{ alpha=1; beta=2; rc=3 }
    $stageComparison = ([int]$order[$a.Groups['stage'].Value]).CompareTo([int]$order[$b.Groups['stage'].Value])
    if ($stageComparison -ne 0) { return $stageComparison }
    return ([long]$a.Groups['sequence'].Value).CompareTo([long]$b.Groups['sequence'].Value)
}

function Test-ManagedRelative([string]$Relative) {
    $value = $Relative.Replace('\','/')
    return (-not [IO.Path]::IsPathRooted($value) -and $value -notmatch '(^|/)\.\.(/|$)' -and
         ($value.StartsWith('olympus/') -or $value.StartsWith('scripts/') -or $value -ceq 'install.ps1' -or
           $value -match '^\.opencode/agents/[^/]+\.md$' -or
           $value -match '^\.opencode/plugins/olympus-activity/(activity\.ts|tui\.tsx)$' -or
           $value -ceq '.opencode/scripts/worktree-setup.ps1' -or
           $value -ceq 'opencode.jsonc' -or
           $script:CliGeneratedCommandFiles -ccontains $value))
}

function Write-Atomic([string]$Path, [byte[]]$Bytes) {
    $parent = Split-Path -Parent $Path
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temporary = Join-Path $parent ('.olympus-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $stream = [IO.FileStream]::new($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
            [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough)
        try { $stream.Write($Bytes, 0, $Bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
        [IO.File]::Move($temporary, $Path, $true)
    } finally { if (Test-Path -LiteralPath $temporary) { [IO.File]::Delete($temporary) } }
}

function Get-PathValue {
    if ($PathStorePath) {
        if ($Action -eq 'uninstall') { [void](Assert-SafeCliPath $PathStorePath 'Leaf') }
        if (Test-Path -LiteralPath $PathStorePath -PathType Leaf) { return [IO.File]::ReadAllText($PathStorePath) }
        return ''
    }
    return [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Get-PathOwnershipPath { return Join-Path $InstallRoot 'path-entry.txt' }

function Test-OwnsPathEntry([string]$Entry) {
    $ownershipPath = Get-PathOwnershipPath
    if ($Action -eq 'uninstall') { [void](Assert-SafeCliPath $ownershipPath) }
    if (-not (Test-Path -LiteralPath $ownershipPath)) { return $false }
    if (-not (Test-Path -LiteralPath $ownershipPath -PathType Leaf) -or
        -not [string]::Equals((Normalize-PathEntry ([IO.File]::ReadAllText($ownershipPath).Trim())),
            (Normalize-PathEntry $Entry), [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'CLI_PATH_CONFLICT' 'The PATH ownership record is invalid; no PATH entry was removed.'
    }
    return $true
}

function Set-PathValue([string]$Value) {
    if ($PathStorePath) {
        if ($Action -eq 'uninstall') { [void](Assert-SafeCliPath $PathStorePath 'Leaf') }
        Write-Atomic $PathStorePath $Utf8NoBom.GetBytes($Value)
    } else {
        [Environment]::SetEnvironmentVariable('Path', $Value, 'User')
        $all = [System.Collections.Generic.List[string]]::new()
        foreach ($item in @($Value -split ';') + @($env:PATH -split ';')) {
            if (-not $item -or @($all | Where-Object { [string]::Equals($_, $item, [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0) { continue }
            $all.Add($item)
        }
        $env:PATH = $all -join ';'
        if (-not ('OlympusCli.EnvironmentBroadcast' -as [type])) {
            Add-Type -Namespace OlympusCli -Name EnvironmentBroadcast -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll", CharSet=System.Runtime.InteropServices.CharSet.Auto, SetLastError=true)]
public static extern System.IntPtr SendMessageTimeout(System.IntPtr hWnd, uint Msg, System.UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out System.UIntPtr result);
'@
        }
        $result = [UIntPtr]::Zero
        [void][OlympusCli.EnvironmentBroadcast]::SendMessageTimeout([IntPtr]0xffff, 0x001A, [UIntPtr]::Zero,
            'Environment', 0x0002, 5000, [ref]$result)
    }
}

function Normalize-PathEntry([string]$Value) {
    if (-not $Value) { return '' }
    try { return [IO.Path]::GetFullPath($Value).TrimEnd('\','/') } catch { return $Value.TrimEnd('\','/') }
}

function Set-UserPathEntry([string]$Entry, [bool]$Add) {
    $comparison = [StringComparison]::OrdinalIgnoreCase
    $existing = [string](Get-PathValue)
    $items = @($existing -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $normalized = Normalize-PathEntry $Entry
    $matches = @($items | Where-Object { [string]::Equals((Normalize-PathEntry $_), $normalized, $comparison) })
    if ($Add -and $matches.Count -eq 0) { $items += $Entry }
    if (-not $Add -and $matches.Count -gt 0) {
        $removed = $false
        $retained = [System.Collections.Generic.List[string]]::new()
        foreach ($item in $items) {
            if (-not $removed -and [string]::Equals((Normalize-PathEntry $item), $normalized, $comparison)) {
                $removed = $true
                continue
            }
            $retained.Add($item)
        }
        $items = $retained.ToArray()
    }
    if (($Add -and $matches.Count -eq 0) -or (-not $Add -and $matches.Count -gt 0)) { Set-PathValue ($items -join ';') }
    return [bool]($Add -and $matches.Count -eq 0)
}

function Get-GeneratedSourceFiles([string]$Root) {
    $files = [System.Collections.Generic.List[string]]::new()
    foreach ($definition in @(
        @{ directory='.opencode/agents'; filter='*.md'; expected=11 }
    )) {
        $directory = Join-Path $Root $definition.directory
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) { Fail 'SOURCE_INVALID' "Generated source directory is missing: $($definition.directory)" }
        $agents = @(Get-ChildItem -LiteralPath $directory -Filter $definition.filter -File | Sort-Object Name)
        if ($agents.Count -ne $definition.expected) { Fail 'SOURCE_INVALID' "Unexpected generated agent inventory: $($definition.directory)" }
        foreach ($agent in $agents) {
            $relative = $agent.FullName.Substring($Root.TrimEnd('\','/').Length + 1).Replace('\','/')
            if ([IO.File]::ReadAllText($agent.FullName) -notmatch 'GENERATED BY scripts/render_harnesses\.py') { Fail 'SOURCE_INVALID' "Not a generated Harness Core output: $relative" }
            $files.Add($relative)
        }
    }
    foreach ($relative in @('.opencode/plugins/olympus-activity/activity.ts', '.opencode/plugins/olympus-activity/tui.tsx',
            '.opencode/scripts/worktree-setup.ps1', 'opencode.jsonc')) {
        $path = Join-Path $Root ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            [IO.File]::ReadAllText($path) -notmatch 'GENERATED BY scripts/render_harnesses\.py') {
            Fail 'SOURCE_INVALID' "Generated Harness Core output is missing or invalid: $relative"
        }
        $files.Add($relative)
    }
    foreach ($relative in $script:CliGeneratedCommandFiles) {
        $path = Join-Path $Root ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            [IO.File]::ReadAllText($path) -notmatch 'GENERATED BY scripts/render_harnesses\.py') {
            Fail 'SOURCE_INVALID' "Generated Harness Core output is missing or invalid: $relative"
        }
        $files.Add($relative)
    }
    return $files.ToArray()
}

function Get-SourceFiles([string]$Root) {
    $files = [System.Collections.Generic.List[string]]::new()
    foreach ($directory in @('olympus', 'scripts')) {
        $base = Join-Path $Root $directory
        if (-not (Test-Path -LiteralPath $base -PathType Container)) { Fail 'SOURCE_INVALID' "Release source is missing $directory/." }
        foreach ($file in @(Get-ChildItem -LiteralPath $base -File -Recurse | Where-Object { $_.Extension -ne '.pyc' -and $_.FullName -notmatch '[\\/]__pycache__([\\/]|$)' })) {
            $files.Add($file.FullName)
        }
    }
    $installer = Join-Path $Root 'install.ps1'
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { Fail 'SOURCE_INVALID' 'Release source is missing install.ps1.' }
    $files.Add($installer)
    foreach ($relative in (Get-GeneratedSourceFiles $Root)) {
        $files.Add((Join-Path $Root ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)))
    }
    return @($files)
}

function Get-VersionManifest([string]$Path) {
    $manifestPath = Join-Path $Path 'olympus-cli-manifest.json'
    if ($Action -eq 'uninstall') { [void](Assert-SafeCliPath $manifestPath) }
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { return $null }
    try { $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json -Depth 30 -ErrorAction Stop }
    catch { Fail 'CLI_VERSION_CONFLICT' "A version directory has an unreadable ownership marker: $Path" }
    if ($manifest.schema_version -ne 1 -or -not $manifest.version -or $null -eq $manifest.files) {
        Fail 'CLI_VERSION_CONFLICT' "A version directory has an unsupported ownership marker: $Path"
    }
    return $manifest
}

function Assert-VersionFiles([string]$Path, $Manifest) {
    foreach ($entry in @($Manifest.files)) {
        $relative = ([string]$entry.path).Replace('\','/')
        if (-not (Test-ManagedRelative $relative) -or
            [string]$entry.sha256 -notmatch '^(?i:[0-9a-f]{64})$') { Fail 'CLI_VERSION_CONFLICT' 'The CLI ownership marker contains an unsafe file path.' }
        $file = Join-Path $Path ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-FileSha256 $file) -cne ([string]$entry.sha256).ToLowerInvariant()) {
            Fail 'CLI_VERSION_CONFLICT' "A managed CLI release file was changed; preserving it: $relative"
        }
    }
}

function Remove-ManagedVersions([string]$VersionsRoot) {
    $known = [System.Collections.Generic.List[string]]::new()
    [void](Assert-SafeCliPath $VersionsRoot 'Container')
    if (-not (Test-Path -LiteralPath $VersionsRoot -PathType Container)) { return @() }
    foreach ($directory in (Get-CliDirectoryItems $VersionsRoot)) {
        $item = Get-ExistingCliItem $directory.FullName
        if ($null -eq $item) { continue }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            if ($item.Name -match '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
                Fail 'CLI_PATH_UNSAFE' "A managed CLI version path is a reparse point: $($item.FullName)"
            }
            continue
        }
        [void](Assert-SafeCliPath $item.FullName 'Container')
        $manifest = Get-VersionManifest $directory.FullName
        if ($null -eq $manifest -or [string]$manifest.version -cne $directory.Name) { continue }
        $known.Add($directory.Name)
        foreach ($entry in @($manifest.files)) {
            $relative = ([string]$entry.path).Replace('\','/')
            if (Test-ManagedRelative $relative) {
                $file = Join-Path $directory.FullName ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
                [void](Assert-SafeCliPath $file)
            }
        }
        $cleanupDirectories = @(Get-CliCleanupDirectories $directory.FullName)
        foreach ($entry in @($manifest.files)) {
            $relative = ([string]$entry.path).Replace('\','/')
            if (-not (Test-ManagedRelative $relative)) { continue }
            $file = Join-Path $directory.FullName ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
            [void](Assert-SafeCliPath $file)
            if (Test-Path -LiteralPath $file -PathType Leaf) {
                if ((Get-FileSha256 $file) -ceq ([string]$entry.sha256).ToLowerInvariant()) { [IO.File]::Delete($file) }
            }
        }
        $manifestPath = Join-Path $directory.FullName 'olympus-cli-manifest.json'
        [void](Assert-SafeCliPath $manifestPath)
        [IO.File]::Delete($manifestPath)
        foreach ($child in ($cleanupDirectories | Sort-Object Length -Descending)) {
            Remove-EmptyCliDirectory $child
        }
        Remove-EmptyCliDirectory $directory.FullName
    }
    Remove-EmptyCliDirectory $VersionsRoot
    return $known.ToArray()
}

function Assert-SafeCliUninstallPaths([string]$VersionsRoot) {
    foreach ($path in @($InstallRoot, $VersionsRoot, $bin, $wrapper, (Get-PathOwnershipPath), $currentPath)) {
        [void](Assert-SafeCliPath $path)
    }
    if ($PathStorePath) { [void](Assert-SafeCliPath $PathStorePath 'Leaf') }
    if (-not (Test-Path -LiteralPath $VersionsRoot -PathType Container)) { return }
    foreach ($directory in (Get-CliDirectoryItems $VersionsRoot)) {
        $item = Get-ExistingCliItem $directory.FullName
        if ($null -eq $item) { continue }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            if ($item.Name -match '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
                Fail 'CLI_PATH_UNSAFE' "A managed CLI version path is a reparse point: $($item.FullName)"
            }
            continue
        }
        [void](Assert-SafeCliPath $item.FullName 'Container')
        $manifest = Get-VersionManifest $item.FullName
        if ($null -eq $manifest -or [string]$manifest.version -cne $item.Name) { continue }
        foreach ($entry in @($manifest.files)) {
            $relative = ([string]$entry.path).Replace('\','/')
            if (Test-ManagedRelative $relative) {
                [void](Assert-SafeCliPath (Join-Path $item.FullName ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)))
            }
        }
        [void](Get-CliCleanupDirectories $item.FullName)
    }
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { Fail 'PLATFORM_UNQUALIFIED' 'The global Olympus CLI is currently qualified only on Windows.' }
    if (-not $InstallRoot) {
        if (-not $env:LOCALAPPDATA) { Fail 'CLI_PATH_INVALID' 'LOCALAPPDATA is unavailable; no global CLI path was changed.' }
        $InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs/Olympus'
    }
    if (-not [IO.Path]::IsPathFullyQualified($InstallRoot)) { Fail 'CLI_PATH_INVALID' 'The CLI installation root must be absolute.' }
    $InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
    if ($InstallRoot -eq [IO.Path]::GetPathRoot($InstallRoot)) { Fail 'CLI_PATH_INVALID' 'The filesystem root is not a valid CLI installation target.' }
    if ($PathStorePath) {
        $PathStorePath = [IO.Path]::GetFullPath($PathStorePath)
        if (-not $PathStorePath.StartsWith($InstallRoot.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            Fail 'CLI_TEST_PATH_STORE_INVALID' 'An isolated PATH store must be inside the selected CLI installation root.'
        }
    }
    $bin = Join-Path $InstallRoot 'bin'
    $wrapper = Join-Path $bin 'olympus.cmd'
    $versionsRoot = Join-Path $InstallRoot 'versions'
    $currentPath = Join-Path $InstallRoot 'current.txt'
    $source = if ($SourceRoot) { [IO.Path]::GetFullPath($SourceRoot) } else { [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')) }

    if ($Action -eq 'uninstall') {
        Assert-SafeCliUninstallPaths $versionsRoot
        if (-not (Test-Path -LiteralPath $source -PathType Container)) { Fail 'SOURCE_INVALID' 'The CLI release source is unavailable.' }
        $ownsPath = Test-OwnsPathEntry $bin
        $sourceWrapper = Join-Path $source 'scripts/olympus.cmd'
        $wrapperContent = if (Test-Path -LiteralPath $sourceWrapper -PathType Leaf) { [IO.File]::ReadAllText($sourceWrapper) } else { $null }
        $knownVersions = @(Remove-ManagedVersions $versionsRoot)
        if ($ownsPath) {
            Set-UserPathEntry $bin $false | Out-Null
            $ownershipPath = Get-PathOwnershipPath
            [void](Assert-SafeCliPath $ownershipPath)
            [IO.File]::Delete($ownershipPath)
        }
        [void](Assert-SafeCliPath $wrapper)
        if ((Test-Path -LiteralPath $wrapper -PathType Leaf) -and $null -ne $wrapperContent -and
            ([IO.File]::ReadAllText($wrapper) -ceq $wrapperContent)) {
            [void](Assert-SafeCliPath $wrapper 'Leaf')
            [IO.File]::Delete($wrapper)
        }
        [void](Assert-SafeCliPath $currentPath)
        if ((Test-Path -LiteralPath $currentPath -PathType Leaf) -and
            [IO.File]::ReadAllText($currentPath).Trim() -in $knownVersions) {
            [void](Assert-SafeCliPath $currentPath 'Leaf')
            [IO.File]::Delete($currentPath)
        }
        if ($ownsPath) { Remove-EmptyCliDirectory $bin }
        foreach ($directory in @($versionsRoot, $InstallRoot)) { Remove-EmptyCliDirectory $directory }
        Write-Output 'OLYMPUS_CLI: UNINSTALLED managed launcher and unchanged version files; user configuration and unmanaged files were preserved.'
        exit 0
    }

    if (-not (Test-Path -LiteralPath $source -PathType Container)) { Fail 'SOURCE_INVALID' 'The CLI release source is unavailable.' }
    $sourceVersion = Get-ReleaseIdentity $source
    if (-not $Version) { $Version = $sourceVersion }
    if ($Version -cne $sourceVersion) { Fail 'SOURCE_VERSION_MISMATCH' "Requested $Version but source identifies as $sourceVersion." }
    [IO.Directory]::CreateDirectory($InstallRoot) | Out-Null
    $previous = if (Test-Path -LiteralPath $currentPath -PathType Leaf) { [IO.File]::ReadAllText($currentPath).Trim() } else { '' }
    if ($previous -and $previous -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
        Fail 'CLI_VERSION_CONFLICT' 'The current CLI version marker is unknown; it was preserved.'
    }
    if ($previous -and $previous -cne $Version -and (Compare-ReleaseTag $Version $previous) -lt 0) {
        Write-Output "OLYMPUS_CLI: NO_DOWNGRADE current=$previous requested=$Version"
        if (Test-Path -LiteralPath $wrapper -PathType Leaf) { Set-UserPathEntry $bin $true }
        exit 0
    }

    $versionPath = Join-Path $versionsRoot $Version
    if (Test-Path -LiteralPath $versionPath) {
        $manifest = Get-VersionManifest $versionPath
        if ($null -eq $manifest -or [string]$manifest.version -cne $Version) { Fail 'CLI_VERSION_CONFLICT' "The version directory is not owned by Olympus: $versionPath" }
        Assert-VersionFiles $versionPath $manifest
    } else {
        $sourceFiles = @(Get-SourceFiles $source)
        $sourcePrefix = $source.TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
        [IO.Directory]::CreateDirectory($versionsRoot) | Out-Null
        $stage = Join-Path $versionsRoot ('.stage-' + [guid]::NewGuid().ToString('N'))
        try {
            [IO.Directory]::CreateDirectory($stage) | Out-Null
            $files = foreach ($sourceFile in $sourceFiles) {
                $relative = $sourceFile.Substring($sourcePrefix.Length).Replace('\','/')
                $destination = Join-Path $stage ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
                [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
                Copy-Item -LiteralPath $sourceFile -Destination $destination
                [ordered]@{ path=$relative; sha256=(Get-FileSha256 $destination) }
            }
            $manifestText = ([ordered]@{ schema_version=1; version=$Version; files=@($files) } | ConvertTo-Json -Depth 10) + "`n"
            [IO.File]::WriteAllText((Join-Path $stage 'olympus-cli-manifest.json'), $manifestText, $Utf8NoBom)
            [IO.Directory]::Move($stage, $versionPath)
        } finally {
            if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
        }
    }

    $sourceWrapper = Join-Path $source 'scripts/olympus.cmd'
    if (-not (Test-Path -LiteralPath $sourceWrapper -PathType Leaf)) { Fail 'SOURCE_INVALID' 'The global CLI launcher is missing.' }
    if (Test-Path -LiteralPath $wrapper -PathType Leaf) {
        if ([IO.File]::ReadAllText($wrapper) -cne [IO.File]::ReadAllText($sourceWrapper)) { Fail 'CLI_LAUNCHER_CONFLICT' 'A different user-owned olympus.cmd already exists; it was preserved.' }
    } else {
        [IO.Directory]::CreateDirectory($bin) | Out-Null
        [IO.File]::WriteAllText($wrapper, [IO.File]::ReadAllText($sourceWrapper), $Utf8NoBom)
    }
    Write-Atomic $currentPath $Utf8NoBom.GetBytes($Version + "`n")
    $ownsPath = Test-OwnsPathEntry $bin
    $addedPath = Set-UserPathEntry $bin $true
    if ($addedPath -and -not $ownsPath) {
        Write-Atomic (Get-PathOwnershipPath) $Utf8NoBom.GetBytes($bin)
    }
    $result = if ($previous -and $previous -cne $Version) { "UPDATED from=$previous to=$Version" } elseif ($previous) { "READY version=$Version" } else { "INSTALLED version=$Version" }
    if ($env:OLYMPUS_CLI_UPDATE_COMPACT -cne '1') {
        Write-Output "OLYMPUS_CLI: $result root=$InstallRoot"
        Write-Output 'OLYMPUS_CLI_PATH: added to the current user PATH; open a new PowerShell 7 shell to use it from any directory.'
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
