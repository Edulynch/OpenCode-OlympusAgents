# Removes only project-local files that Olympus explicitly owns in its install manifest.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [Parameter(Mandatory = $true)]
    [ValidateSet('opencode', 'codex', 'all')]
    [string]$Harness
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$OpenCodeManifestRel = '.opencode/orchestrator-install.json'
$CodexManifestRel = '.codex/orchestrator-install.json'

function Fail([string]$Code, [string]$Message) {
    throw ($Code + ': ' + $Message)
}

function Normalize-Relative([string]$Path) {
    $value = $Path.Replace('\', '/').Trim()
    if (-not $value -or [IO.Path]::IsPathRooted($value) -or
        $value -match '(^|/)\.\.(/|$)' -or $value -match '(^|/)\.(?:/|$)') {
        Fail 'PROJECT_MANIFEST_INVALID' "Unsafe managed path: $Path"
    }
    return $value.TrimStart('/')
}

function Resolve-ManagedPath([string]$Repo, [string]$Relative) {
    $relativePath = Normalize-Relative $Relative
    $base = [IO.Path]::GetFullPath($Repo).TrimEnd([char[]]@('\','/'))
    $full = [IO.Path]::GetFullPath((Join-Path $base ($relativePath -replace '/', [IO.Path]::DirectorySeparatorChar)))
    $prefix = $base + [IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'PROJECT_PATH_UNSAFE' "Managed path escapes the project root: $Relative"
    }

    # Refuse junction/symlink traversal so a managed relative path cannot delete outside the repository.
    $cursor = $base
    foreach ($part in ($relativePath -split '/')) {
        $cursor = Join-Path $cursor $part
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
        if ($null -ne $item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Fail 'PROJECT_PATH_UNSAFE' "Managed path traverses a reparse point: $Relative"
        }
    }
    return $full
}

function Get-FileHashText([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($Path)))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-PathHarness([string]$Relative) {
    $path = Normalize-Relative $Relative
    if ($path -ceq 'opencode.jsonc' -or $path.StartsWith('.opencode/', [StringComparison]::OrdinalIgnoreCase)) {
        return 'opencode'
    }
    if ($path -ceq 'CODEX.md' -or $path.StartsWith('.codex/', [StringComparison]::OrdinalIgnoreCase)) {
        return 'codex'
    }
    Fail 'PROJECT_MANIFEST_INVALID' "Managed path cannot be attributed to a supported harness: $path"
}

function Get-InstalledHarnesses($Manifest) {
    $properties = @($Manifest.PSObject.Properties | ForEach-Object Name)
    if ('installed_harnesses' -notin $properties) {
        # Older project manifests were OpenCode-only before the dual-harness inventory existed.
        return @('opencode')
    }

    $values = @($Manifest.installed_harnesses | ForEach-Object { ([string]$_).ToLowerInvariant() })
    $unique = @($values | Select-Object -Unique)
    if ($values.Count -eq 0 -or $values.Count -ne $unique.Count -or
        @($values | Where-Object { $_ -notin @('opencode', 'codex') }).Count -ne 0) {
        Fail 'PROJECT_MANIFEST_INVALID' 'installed_harnesses is empty, duplicated, or unsupported.'
    }
    return @($values)
}

function Read-ProjectManifest([string]$Repo) {
    $openCodePath = Resolve-ManagedPath $Repo $OpenCodeManifestRel
    $codexPath = Resolve-ManagedPath $Repo $CodexManifestRel
    $hasOpenCode = Test-Path -LiteralPath $openCodePath -PathType Leaf
    $hasCodex = Test-Path -LiteralPath $codexPath -PathType Leaf

    if ($hasOpenCode -and $hasCodex) {
        Fail 'PROJECT_MANIFEST_CONFLICT' 'Both project manifest locations exist; refusing ambiguous ownership metadata.'
    }
    if (-not $hasOpenCode -and -not $hasCodex) {
        Fail 'PROJECT_MANIFEST_MISSING' 'No Olympus project install manifest exists.'
    }

    $path = if ($hasOpenCode) { $openCodePath } else { $codexPath }
    try {
        $manifest = [IO.File]::ReadAllText($path) | ConvertFrom-Json -Depth 100
    } catch {
        Fail 'PROJECT_MANIFEST_INVALID' 'Olympus project manifest is invalid JSON.'
    }

    if ($manifest.schema_version -ne 1 -or $null -eq $manifest.managed_files) {
        Fail 'PROJECT_MANIFEST_INVALID' 'Unsupported project manifest schema or missing managed_files.'
    }
    $properties = @($manifest.PSObject.Properties | ForEach-Object Name)
    if ('scope' -in $properties -and [string]$manifest.scope -cne 'project') {
        Fail 'PROJECT_MANIFEST_INVALID' 'Manifest does not describe a project-scope installation.'
    }

    return [pscustomobject]@{ Path = $path; Manifest = $manifest }
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        Fail 'PLATFORM_UNQUALIFIED' 'Project uninstall is Windows-qualified only.'
    }
    if (-not [IO.Path]::IsPathFullyQualified($Target)) {
        Fail 'UNSAFE_TARGET' 'Target must be an absolute project-root path.'
    }

    $repo = (Resolve-Path -LiteralPath $Target -ErrorAction Stop).Path
    $git = @(Get-Command git -CommandType Application -ErrorAction SilentlyContinue)
    if ($git.Count -eq 0) { Fail 'GIT_UNAVAILABLE' 'git is required.' }
    $gitRoot = (& $git[0].Source -C $repo rev-parse --show-toplevel 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $gitRoot) {
        Fail 'UNSAFE_TARGET' 'Target must be an existing Git project root.'
    }
    if (-not [string]::Equals([IO.Path]::GetFullPath($gitRoot).TrimEnd([char[]]@('\','/')),
        [IO.Path]::GetFullPath($repo).TrimEnd([char[]]@('\','/')), [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'UNSAFE_TARGET' 'Target must be the Git project root, not a nested directory.'
    }

    $state = Read-ProjectManifest $repo
    $manifest = $state.Manifest
    $installed = @(Get-InstalledHarnesses $manifest)
    $selected = if ($Harness -eq 'all') { @($installed) } else { @($Harness) }

    foreach ($name in $selected) {
        if ($name -notin $installed) {
            Fail 'HARNESS_NOT_INSTALLED' "Harness '$name' is not recorded as installed in this project."
        }
    }

    $entries = @($manifest.managed_files)
    if ($entries.Count -eq 0) { Fail 'PROJECT_MANIFEST_INVALID' 'managed_files is empty.' }

    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $validated = [System.Collections.Generic.List[object]]::new()
    foreach ($entry in $entries) {
        $relative = Normalize-Relative ([string]$entry.path)
        if (-not $seen.Add($relative)) {
            Fail 'PROJECT_MANIFEST_INVALID' "Duplicate managed path: $relative"
        }
        $owner = Get-PathHarness $relative
        if ($owner -notin $installed) {
            Fail 'PROJECT_MANIFEST_INVALID' "Managed path '$relative' belongs to '$owner', which is absent from installed_harnesses."
        }

        $expected = ([string]$entry.sha256).ToLowerInvariant()
        if ($expected -notmatch '^[0-9a-f]{64}$') {
            Fail 'PROJECT_MANIFEST_INVALID' "Managed path '$relative' has an invalid SHA-256."
        }

        $full = Resolve-ManagedPath $repo $relative
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
            Fail 'MANAGED_FILE_DRIFT' "Managed file is missing: $relative"
        }
        if ((Get-FileHashText $full) -cne $expected) {
            Fail 'MANAGED_FILE_DRIFT' "Managed file was modified: $relative"
        }

        $validated.Add([pscustomobject]@{
            Entry = $entry
            Relative = $relative
            Full = $full
            Harness = $owner
        })
    }

    $remove = @($validated | Where-Object { $_.Harness -in $selected })
    $keep = @($validated | Where-Object { $_.Harness -notin $selected })
    if ($remove.Count -eq 0) {
        Fail 'PROJECT_MANIFEST_INVALID' 'The selected harness has no managed files recorded.'
    }

    $remainingHarnesses = @($installed | Where-Object { $_ -notin $selected })
    $nextManifestPath = $null
    if ($remainingHarnesses.Count -gt 0) {
        $nextManifestRel = if ('opencode' -in $remainingHarnesses) { $OpenCodeManifestRel } else { $CodexManifestRel }
        $nextManifestPath = Resolve-ManagedPath $repo $nextManifestRel
        if (-not [string]::Equals($nextManifestPath, $state.Path, [StringComparison]::OrdinalIgnoreCase) -and
            (Test-Path -LiteralPath $nextManifestPath)) {
            Fail 'PROJECT_MANIFEST_CONFLICT' "Next manifest location already exists: $nextManifestRel"
        }
    }

    # All drift and destination checks finish before the first destructive operation.
    foreach ($item in $remove) {
        [IO.File]::Delete($item.Full)
        Write-Output "REMOVED: $($item.Relative)"
    }

    if ($remainingHarnesses.Count -eq 0) {
        [IO.File]::Delete($state.Path)
    } else {
        $properties = @($manifest.PSObject.Properties | ForEach-Object Name)
        if ('installed_harnesses' -in $properties) {
            $manifest.installed_harnesses = @($remainingHarnesses)
        } else {
            $manifest | Add-Member -NotePropertyName installed_harnesses -NotePropertyValue @($remainingHarnesses)
        }
        $manifest.managed_files = @($keep | ForEach-Object { $_.Entry })
        $manifestText = ($manifest | ConvertTo-Json -Depth 100) + [Environment]::NewLine

        $parent = Split-Path -Parent $nextManifestPath
        if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
            [IO.Directory]::CreateDirectory($parent) | Out-Null
        }
        [IO.File]::WriteAllText($nextManifestPath, $manifestText, $Utf8NoBom)
        if (-not [string]::Equals($nextManifestPath, $state.Path, [StringComparison]::OrdinalIgnoreCase)) {
            [IO.File]::Delete($state.Path)
        }
    }

    Write-Output "OLYMPUS_PROJECT_UNINSTALL: $Harness REMOVED_MANAGED_RESOURCES_ONLY"
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
