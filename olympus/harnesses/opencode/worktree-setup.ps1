<#
    Provision an OpenCode-created Git worktree from its Olympus-enabled base checkout.
    OpenCode V2 supplies OPENCODE_WORKTREE_BASE and OPENCODE_WORKTREE_PATH to
    Project.Commands.start. This script only copies resources owned by the
    project's verified Olympus install manifest; it never downloads or deletes.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Fail([string]$Code, [string]$Message) { throw "$Code`: $Message" }

function Full-Path([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    if (-not [string]::Equals($full, $root, [StringComparison]::OrdinalIgnoreCase)) {
        $full = $full.TrimEnd([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar))
    }
    return $full
}

function Git-Output([string]$Directory, [string[]]$Arguments) {
    $output = @(& git -C $Directory @Arguments 2>$null)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { Fail 'WORKTREE_SETUP_GIT_FAILED' "git $($Arguments -join ' ') failed in $Directory." }
    return (($output | Out-String).Trim())
}

function Get-Git-Root([string]$Directory) {
    $root = Git-Output $Directory @('rev-parse', '--show-toplevel')
    if (-not $root) { Fail 'WORKTREE_SETUP_NOT_GIT' "No Git worktree root was found for $Directory." }
    return Full-Path $root
}

function Get-Git-Common-Directory([string]$Directory) {
    $root = Get-Git-Root $Directory
    $common = Git-Output $Directory @('rev-parse', '--git-common-dir')
    if (-not [IO.Path]::IsPathFullyQualified($common)) { $common = Join-Path $root $common }
    $common = Full-Path $common
    if (-not (Test-Path -LiteralPath $common -PathType Container)) {
        Fail 'WORKTREE_SETUP_NOT_GIT' "Git common directory is unavailable for $Directory."
    }
    return Full-Path (Resolve-Path -LiteralPath $common -ErrorAction Stop).Path
}

function Normalize-Managed-Path([string]$Path) {
    $relative = $Path.Replace('\', '/')
    if (-not $relative -or [IO.Path]::IsPathRooted($relative) -or
        $relative -match '(^|/)\.\.(/|$)' -or $relative -match '(^|/)\.(?:/|$)' -or
        $relative -match '[:\x00]') {
        Fail 'WORKTREE_SETUP_MANIFEST_INVALID' "Unsafe managed path: $Path"
    }
    $allowed = $relative -ceq 'opencode.jsonc' -or $relative -ceq 'CODEX.md' -or
        $relative -match '^\.opencode/agents/[A-Za-z0-9_-]+\.md$' -or
        $relative -ceq '.opencode/commands/maintain.md' -or
        $relative -match '^\.opencode/plugins/olympus-activity/(activity\.ts|tui\.tsx)$' -or
        $relative -ceq '.opencode/scripts/worktree-setup.ps1' -or
        $relative -match '^\.codex/agents/[A-Za-z0-9_-]+\.toml$' -or
        $relative -ceq '.codex/config.toml'
    if (-not $allowed) { Fail 'WORKTREE_SETUP_MANIFEST_INVALID' "Unexpected managed path: $relative" }
    return $relative
}

function Get-Contained-Path([string]$Root, [string]$Relative) {
    $rootPath = Full-Path $Root
    $segments = $Relative -split '/'
    $full = Full-Path (Join-Path $rootPath ($segments -join [IO.Path]::DirectorySeparatorChar))
    $prefix = $rootPath.TrimEnd([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)) + [IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'WORKTREE_SETUP_PATH_UNSAFE' "Managed path escapes its checkout: $Relative"
    }

    $cursor = $rootPath
    for ($index = 0; $index -lt $segments.Count; $index++) {
        $cursor = Join-Path $cursor $segments[$index]
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
        if ($null -eq $item) { continue }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Fail 'WORKTREE_SETUP_PATH_UNSAFE' "Managed path traverses a reparse point: $Relative"
        }
        if ($index -lt ($segments.Count - 1) -and -not $item.PSIsContainer) {
            Fail 'WORKTREE_SETUP_PATH_UNSAFE' "Managed parent is not a directory: $Relative"
        }
    }
    return $full
}

function Sha-Bytes([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Write-New-File([string]$Path, [byte[]]$Bytes) {
    $parent = Split-Path -Parent $Path
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temp = Join-Path $parent ('.olympus-worktree-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $stream = [IO.File]::Open($temp, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            $stream.Write($Bytes, 0, $Bytes.Length)
            $stream.Flush($true)
        } finally { $stream.Dispose() }
        [IO.File]::Move($temp, $Path)
    } finally {
        if (Test-Path -LiteralPath $temp -PathType Leaf) { [IO.File]::Delete($temp) }
    }
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        Fail 'WORKTREE_SETUP_PLATFORM_UNQUALIFIED' 'This startup command is qualified for OpenCode V2 on Windows.'
    }
    if (-not (Get-Command git -CommandType Application -ErrorAction SilentlyContinue)) {
        Fail 'WORKTREE_SETUP_GIT_UNAVAILABLE' 'Git is required.'
    }
    if (-not $env:OPENCODE_WORKTREE_BASE -or -not $env:OPENCODE_WORKTREE_PATH) {
        Fail 'WORKTREE_SETUP_ENV_MISSING' 'OpenCode must provide OPENCODE_WORKTREE_BASE and OPENCODE_WORKTREE_PATH.'
    }

    $base = Full-Path $env:OPENCODE_WORKTREE_BASE
    $target = Full-Path $env:OPENCODE_WORKTREE_PATH
    if (-not (Test-Path -LiteralPath $base -PathType Container) -or
        -not (Test-Path -LiteralPath $target -PathType Container)) {
        Fail 'WORKTREE_SETUP_DIRECTORY_MISSING' 'The source and destination worktrees must already exist.'
    }
    $base = Get-Git-Root $base
    $target = Get-Git-Root $target
    if ([string]::Equals($base, $target, [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'WORKTREE_SETUP_TARGET_INVALID' 'The source and destination worktrees must be different checkouts.'
    }
    $baseCommon = Get-Git-Common-Directory $base
    $targetCommon = Get-Git-Common-Directory $target
    if (-not [string]::Equals($baseCommon, $targetCommon, [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'WORKTREE_SETUP_TARGET_INVALID' 'The destination is not a linked worktree of the Olympus-enabled source checkout.'
    }

    # Reject the same foreign OpenCode config locations as the bootstrap
    # installer, before calculating or applying any worktree writes.
    foreach ($alternative in @('opencode.json', '.opencode/opencode.json', '.opencode/opencode.jsonc')) {
        if (Test-Path -LiteralPath (Get-Contained-Path $target $alternative)) {
            Fail 'WORKTREE_SETUP_CONFLICT' "Foreign OpenCode config exists: $alternative"
        }
    }

    $manifestRelative = '.opencode/orchestrator-install.json'
    $sourceManifestPath = Get-Contained-Path $base $manifestRelative
    if (-not (Test-Path -LiteralPath $sourceManifestPath -PathType Leaf)) {
        Fail 'WORKTREE_SETUP_MANIFEST_MISSING' 'The source checkout has no Olympus project install manifest.'
    }
    try { $manifestText = [IO.File]::ReadAllText($sourceManifestPath); $manifest = $manifestText | ConvertFrom-Json -Depth 100 }
    catch { Fail 'WORKTREE_SETUP_MANIFEST_INVALID' 'The source checkout has an invalid Olympus install manifest.' }
    if ($manifest.schema_version -ne 1 -or $null -eq $manifest.managed_files -or
        ('scope' -in @($manifest.PSObject.Properties | ForEach-Object Name) -and [string]$manifest.scope -cne 'project')) {
        Fail 'WORKTREE_SETUP_MANIFEST_INVALID' 'Only a schema v1 project install manifest is supported.'
    }
    # A new worktree helper only ships in modern manifests, so it must not
    # silently accept the legacy no-harness format.
    $harnesses = @($manifest.installed_harnesses | ForEach-Object { [string]$_ })
    if ($harnesses.Count -lt 1 -or $harnesses.Count -gt 2 -or
        @($harnesses | Where-Object { $_ -cnotin @('opencode', 'codex') }).Count -gt 0 -or
        @($harnesses | Select-Object -Unique).Count -ne $harnesses.Count -or
        'opencode' -cnotin $harnesses) {
        Fail 'WORKTREE_SETUP_MANIFEST_INVALID' 'The source manifest must declare OpenCode and at most one Codex harness.'
    }

    # Installed projects lack Core renderer sources; this is the exact current
    # bootstrap-generated roster. Historical sets remain bootstrap-only.
    $expectedOpenCode = @(
        '.opencode/agents/aegis.md',
        '.opencode/agents/argus.md',
        '.opencode/agents/atlas.md',
        '.opencode/agents/helios.md',
        '.opencode/agents/kael.md',
        '.opencode/agents/kovan.md',
        '.opencode/agents/nox.md',
        '.opencode/agents/orin.md',
        '.opencode/agents/talos.md',
        '.opencode/agents/thales.md',
        '.opencode/agents/vera.md',
        '.opencode/agents/veyra.md',
        '.opencode/commands/maintain.md',
        '.opencode/plugins/olympus-activity/activity.ts',
        '.opencode/plugins/olympus-activity/tui.tsx',
        '.opencode/scripts/worktree-setup.ps1',
        'opencode.jsonc'
    )
    $expectedCodex = @(
        '.codex/agents/argus.toml',
        '.codex/agents/atlas.toml',
        '.codex/agents/helios.toml',
        '.codex/agents/kovan.toml',
        '.codex/agents/nox.toml',
        '.codex/agents/orin.toml',
        '.codex/agents/talos.toml',
        '.codex/agents/thales.toml',
        '.codex/agents/vera.toml',
        '.codex/agents/veyra.toml',
        '.codex/config.toml',
        'CODEX.md'
    )
    $expected = @($expectedOpenCode)
    if ('codex' -in $harnesses) { $expected += $expectedCodex }

    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $payloads = [Collections.Generic.List[object]]::new()
    $setupEntryFound = $false
    foreach ($entry in @($manifest.managed_files)) {
        $relative = Normalize-Managed-Path ([string]$entry.path)
        if ($expected -cnotcontains $relative) {
            Fail 'WORKTREE_SETUP_MANIFEST_INVALID' "Managed path is not in the approved current inventory: $relative"
        }
        if (-not $seen.Add($relative)) { Fail 'WORKTREE_SETUP_MANIFEST_INVALID' "Duplicate managed path: $relative" }
        $expectedHash = ([string]$entry.sha256).ToLowerInvariant()
        if ($expectedHash -notmatch '^[0-9a-f]{64}$') { Fail 'WORKTREE_SETUP_MANIFEST_INVALID' "Invalid SHA-256 for $relative" }
        $sourcePath = Get-Contained-Path $base $relative
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            Fail 'WORKTREE_SETUP_SOURCE_MISSING' "Managed source file is missing: $relative"
        }
        $bytes = [IO.File]::ReadAllBytes($sourcePath)
        if ((Sha-Bytes $bytes) -cne $expectedHash) {
            Fail 'WORKTREE_SETUP_SOURCE_DRIFT' "Managed source file changed: $relative"
        }
        if ($relative -ceq '.opencode/scripts/worktree-setup.ps1') {
            $executingPath = Full-Path $PSCommandPath
            if (-not [string]::Equals($executingPath, $sourcePath, [StringComparison]::OrdinalIgnoreCase)) {
                Fail 'WORKTREE_SETUP_SOURCE_INVALID' 'The active setup script is not the manifest-owned source copy.'
            }
            $setupEntryFound = $true
        }
        $null = $payloads.Add([pscustomobject]@{ Relative=$relative; Bytes=$bytes; Hash=$expectedHash })
    }
    # An exact approved set with no duplicates must also have every expected entry.
    if ($seen.Count -ne $expected.Count -or -not $setupEntryFound -or 'opencode.jsonc' -notin $seen) {
        Fail 'WORKTREE_SETUP_MANIFEST_INVALID' 'The source manifest does not match the complete approved harness inventory.'
    }

    $manifestBytes = [Text.UTF8Encoding]::new($false).GetBytes($manifestText)
    $manifestHash = Sha-Bytes $manifestBytes
    $writes = [Collections.Generic.List[object]]::new()
    foreach ($payload in $payloads) {
        $destination = Get-Contained-Path $target $payload.Relative
        if (Test-Path -LiteralPath $destination) {
            $item = Get-Item -LiteralPath $destination -Force
            if ($item.PSIsContainer -or (Sha-Bytes ([IO.File]::ReadAllBytes($destination))) -cne $payload.Hash) {
                Fail 'WORKTREE_SETUP_CONFLICT' "Refusing to replace an existing user or drifted file: $($payload.Relative)"
            }
        } else {
            $null = $writes.Add([pscustomobject]@{ Path=$destination; Bytes=$payload.Bytes; Relative=$payload.Relative })
        }
    }
    $destinationManifest = Get-Contained-Path $target $manifestRelative
    if (Test-Path -LiteralPath $destinationManifest) {
        $item = Get-Item -LiteralPath $destinationManifest -Force
        if ($item.PSIsContainer -or (Sha-Bytes ([IO.File]::ReadAllBytes($destinationManifest))) -cne $manifestHash) {
            Fail 'WORKTREE_SETUP_CONFLICT' 'Refusing to replace an existing or drifted Olympus manifest.'
        }
    } else {
        $null = $writes.Add([pscustomobject]@{ Path=$destinationManifest; Bytes=$manifestBytes; Relative=$manifestRelative })
    }

    foreach ($write in $writes) {
        # Re-check the exact destination immediately before creating it. File.Move
        # does not replace a concurrently-created path, so user files stay safe.
        $destination = Get-Contained-Path $target $write.Relative
        if (Test-Path -LiteralPath $destination) {
            $item = Get-Item -LiteralPath $destination -Force
            if ($item.PSIsContainer -or (Sha-Bytes ([IO.File]::ReadAllBytes($destination))) -cne (Sha-Bytes $write.Bytes)) {
                Fail 'WORKTREE_SETUP_CONFLICT' "Destination changed during setup: $($write.Relative)"
            }
            continue
        }
        Write-New-File $destination $write.Bytes
    }

    Write-Output "OLYMPUS_WORKTREE_SETUP: PASS (source=$base; target=$target; created=$($writes.Count))"
    exit 0
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
