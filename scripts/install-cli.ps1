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

function Fail([string]$Code, [string]$Message) { throw "$Code`: $Message" }

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
         $value -match '^\.codex/agents/[^/]+\.toml$' -or
         $value -in @('.codex/config.toml', 'CODEX.md', 'opencode.jsonc')))
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
        if (Test-Path -LiteralPath $PathStorePath -PathType Leaf) { return [IO.File]::ReadAllText($PathStorePath) }
        return ''
    }
    return [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Get-PathOwnershipPath { return Join-Path $InstallRoot 'path-entry.txt' }

function Test-OwnsPathEntry([string]$Entry) {
    $ownershipPath = Get-PathOwnershipPath
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
        @{ directory='.opencode/agents'; filter='*.md'; expected=11 },
        @{ directory='.codex/agents'; filter='*.toml'; expected=10 }
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
            '.opencode/scripts/worktree-setup.ps1', '.codex/config.toml', 'CODEX.md', 'opencode.jsonc')) {
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
    if (-not (Test-Path -LiteralPath $VersionsRoot -PathType Container)) { return @() }
    foreach ($directory in @(Get-ChildItem -LiteralPath $VersionsRoot -Directory)) {
        $manifest = Get-VersionManifest $directory.FullName
        if ($null -eq $manifest -or [string]$manifest.version -cne $directory.Name) { continue }
        $known.Add($directory.Name)
        foreach ($entry in @($manifest.files)) {
            $relative = ([string]$entry.path).Replace('\','/')
            if (-not (Test-ManagedRelative $relative)) { continue }
            $file = Join-Path $directory.FullName ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
            if (Test-Path -LiteralPath $file -PathType Leaf) {
                if ((Get-FileSha256 $file) -ceq ([string]$entry.sha256).ToLowerInvariant()) { [IO.File]::Delete($file) }
            }
        }
        [IO.File]::Delete((Join-Path $directory.FullName 'olympus-cli-manifest.json'))
        foreach ($child in @(Get-ChildItem -LiteralPath $directory.FullName -Directory -Recurse | Sort-Object FullName -Descending)) {
            if (@(Get-ChildItem -LiteralPath $child.FullName -Force).Count -eq 0) { [IO.Directory]::Delete($child.FullName) }
        }
        if (@(Get-ChildItem -LiteralPath $directory.FullName -Force).Count -eq 0) { [IO.Directory]::Delete($directory.FullName) }
    }
    if (@(Get-ChildItem -LiteralPath $VersionsRoot -Force).Count -eq 0) { [IO.Directory]::Delete($VersionsRoot) }
    return $known.ToArray()
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
    if (-not (Test-Path -LiteralPath $source -PathType Container)) { Fail 'SOURCE_INVALID' 'The CLI release source is unavailable.' }

    if ($Action -eq 'uninstall') {
        $ownsPath = Test-OwnsPathEntry $bin
        $sourceWrapper = Join-Path $source 'scripts/olympus.cmd'
        $wrapperContent = if (Test-Path -LiteralPath $sourceWrapper -PathType Leaf) { [IO.File]::ReadAllText($sourceWrapper) } else { $null }
        $knownVersions = @(Remove-ManagedVersions $versionsRoot)
        if ($ownsPath) {
            Set-UserPathEntry $bin $false | Out-Null
            [IO.File]::Delete((Get-PathOwnershipPath))
        }
        if ((Test-Path -LiteralPath $wrapper -PathType Leaf) -and $null -ne $wrapperContent -and
            ([IO.File]::ReadAllText($wrapper) -ceq $wrapperContent)) { [IO.File]::Delete($wrapper) }
        if ((Test-Path -LiteralPath $currentPath -PathType Leaf) -and
            [IO.File]::ReadAllText($currentPath).Trim() -in $knownVersions) { [IO.File]::Delete($currentPath) }
        if ($ownsPath -and (Test-Path -LiteralPath $bin -PathType Container) -and @(Get-ChildItem -LiteralPath $bin -Force).Count -eq 0) { [IO.Directory]::Delete($bin) }
        foreach ($directory in @($versionsRoot, $InstallRoot)) {
            if ((Test-Path -LiteralPath $directory -PathType Container) -and @(Get-ChildItem -LiteralPath $directory -Force).Count -eq 0) { [IO.Directory]::Delete($directory) }
        }
        Write-Output 'OLYMPUS_CLI: UNINSTALLED managed launcher and unchanged version files; user configuration and unmanaged files were preserved.'
        exit 0
    }

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
        [IO.Directory]::CreateDirectory($versionsRoot) | Out-Null
        $stage = Join-Path $versionsRoot ('.stage-' + [guid]::NewGuid().ToString('N'))
        try {
            [IO.Directory]::CreateDirectory($stage) | Out-Null
            Copy-Item -LiteralPath (Join-Path $source 'olympus') -Destination $stage -Recurse
            Copy-Item -LiteralPath (Join-Path $source 'scripts') -Destination $stage -Recurse
            Copy-Item -LiteralPath (Join-Path $source 'install.ps1') -Destination $stage
            foreach ($relative in (Get-GeneratedSourceFiles $source)) {
                $sourceFile = Join-Path $source ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
                $destination = Join-Path $stage ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
                [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
                Copy-Item -LiteralPath $sourceFile -Destination $destination
            }
            $files = foreach ($file in (Get-SourceFiles $stage)) {
                [ordered]@{ path=$file.Substring($stage.Length + 1).Replace('\','/'); sha256=(Get-FileSha256 $file) }
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
    Write-Output "OLYMPUS_CLI: $result root=$InstallRoot"
    Write-Output 'OLYMPUS_CLI_PATH: added to the current user PATH; open a new PowerShell 7 shell to use it from any directory.'
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
