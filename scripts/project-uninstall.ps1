# Removes only project-local files that Olympus explicitly owns in its install manifest.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [Parameter(Mandatory = $true)]
    [ValidateSet('opencode')]
    [string]$Harness
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$OpenCodeManifestRel = '.opencode/orchestrator-install.json'
$CurrentProjectInventory = @(
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
    '.opencode/plugins/olympus-activity/activity.ts',
    '.opencode/plugins/olympus-activity/tui.tsx',
    '.opencode/scripts/worktree-setup.ps1',
    'opencode.jsonc'
)
$writerLock = $null
$pathComparison = if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
    [StringComparison]::OrdinalIgnoreCase
} else {
    [StringComparison]::Ordinal
}

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
    if (-not $full.StartsWith($prefix, $pathComparison)) {
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

function Assert-No-Config-Recovery([string]$Repo) {
    $pendingPath = Join-Path $Repo '.olympus-cli-config-apply'
    try { $pending = Get-Item -LiteralPath $pendingPath -Force -ErrorAction Stop }
    catch {
        if ($_.CategoryInfo.Category -eq 'ObjectNotFound') { return }
        Fail 'CONFIG_RECOVERY_PENDING' "Cannot safely inspect project recovery state: $($_.Exception.Message)"
    }
    if ($null -ne $pending) {
        Fail 'CONFIG_RECOVERY_PENDING' 'A project config/settings transaction is pending; recover it explicitly before uninstalling.'
    }
}

function Get-ManifestPropertyNames($Manifest) {
    if ($Manifest -is [System.Collections.IDictionary]) {
        return @($Manifest.Keys | ForEach-Object { [string]$_ })
    }
    return @($Manifest.PSObject.Properties | ForEach-Object Name)
}

function Get-PathHarness([string]$Relative) {
    $path = Normalize-Relative $Relative
    if ($path -ceq 'opencode.jsonc' -or $path.StartsWith('.opencode/', [StringComparison]::OrdinalIgnoreCase)) {
        return 'opencode'
    }
    Fail 'PROJECT_MANIFEST_INVALID' "Managed path is outside the current OpenCode inventory: $path"
}

function Get-InstalledHarnesses($Manifest) {
    $properties = @(Get-ManifestPropertyNames $Manifest)
    if ('installed_harnesses' -notin $properties) {
        Fail 'PROJECT_MANIFEST_INVALID' 'Manifest must explicitly declare only the OpenCode harness.'
    }

    if ($Manifest.installed_harnesses -isnot [System.Collections.IList]) {
        Fail 'PROJECT_MANIFEST_INVALID' 'installed_harnesses must be an array.'
    }
    $values = @($Manifest.installed_harnesses | ForEach-Object { [string]$_ })
    if ($values.Count -ne 1 -or $values[0] -cne 'opencode') {
        Fail 'PROJECT_MANIFEST_INVALID' 'installed_harnesses must be exactly ["opencode"].'
    }
    return @('opencode')
}

function Get-HarnessProvenance($Manifest) {
    # JSON object keys are case-sensitive. Preserve opaque future harness names
    # exactly instead of collapsing keys that differ only by case.
    $result = [System.Collections.Specialized.OrderedDictionary]::new([StringComparer]::Ordinal)
    $properties = @(Get-ManifestPropertyNames $Manifest)
    if ('harness_provenance' -notin $properties) { return $result }

    # Schema 1 may omit provenance. When present it is opaque per-harness
    # metadata, not ownership evidence; preserve entries outside the selection.
    $provenance = if ($Manifest -is [System.Collections.IDictionary]) {
        $Manifest['harness_provenance']
    } else {
        $Manifest.harness_provenance
    }
    if ($null -eq $provenance -or
        ($provenance -isnot [System.Management.Automation.PSCustomObject] -and
         $provenance -isnot [System.Collections.IDictionary])) {
        Fail 'PROJECT_MANIFEST_INVALID' 'harness_provenance must be an object keyed by harness.'
    }
    $entries = if ($provenance -is [System.Collections.IDictionary]) {
        @($provenance.Keys | ForEach-Object { [pscustomobject]@{ Name=[string]$_; Value=$provenance[$_] } })
    } else {
        @($provenance.PSObject.Properties)
    }
    foreach ($entry in $entries) {
        $name = [string]$entry.Name
        $value = $entry.Value
        if ([string]::IsNullOrWhiteSpace($name) -or
            ($value -isnot [System.Management.Automation.PSCustomObject] -and
             $value -isnot [System.Collections.IDictionary])) {
            Fail 'PROJECT_MANIFEST_INVALID' 'Each harness_provenance entry must be a non-empty keyed object.'
        }
        $result[$name] = $value
    }
    return $result
}

function Read-ProjectManifest([string]$Repo) {
    $openCodePath = Resolve-ManagedPath $Repo $OpenCodeManifestRel
    $codexPath = Resolve-ManagedPath $Repo '.codex/orchestrator-install.json'
    if (Test-Path -LiteralPath $codexPath) {
        Fail 'PROJECT_MANIFEST_INVALID' 'Codex project manifests are unsupported and will not be migrated.'
    }
    $hasOpenCode = Test-Path -LiteralPath $openCodePath -PathType Leaf

    if (-not $hasOpenCode) {
        Fail 'PROJECT_MANIFEST_MISSING' 'No Olympus project install manifest exists.'
    }

    $path = $openCodePath
    try {
        $manifest = [IO.File]::ReadAllText($path) | ConvertFrom-Json -AsHashtable -Depth 100
    } catch {
        Fail 'PROJECT_MANIFEST_INVALID' 'Olympus project manifest is invalid JSON.'
    }

    if ($manifest.schema_version -ne 1 -or [string]$manifest.scope -cne 'project' -or
        $manifest.installed_version -isnot [string] -or [string]::IsNullOrWhiteSpace($manifest.installed_version) -or
        $manifest.installed_from_commit -isnot [string] -or [string]::IsNullOrWhiteSpace($manifest.installed_from_commit) -or
        $null -eq $manifest.managed_files) {
        Fail 'PROJECT_MANIFEST_INVALID' 'Current schema v1 project metadata is incomplete or unsupported.'
    }
    [void](Get-HarnessProvenance $manifest)

    return [pscustomobject]@{ Path = $path; Manifest = $manifest }
}

try {
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
    # Ask Git whether the supplied working directory has a prefix inside the
    # worktree rather than comparing path strings. Git and the OS can report
    # the same macOS directory as /var/... and /private/var/..., respectively.
    $gitPrefix = (& $git[0].Source -C $repo rev-parse --show-prefix 2>$null | Out-String)
    if ($LASTEXITCODE -ne 0) {
        Fail 'UNSAFE_TARGET' 'Cannot determine the target path within its Git project.'
    }
    if (-not [string]::IsNullOrEmpty($gitPrefix.Trim())) {
        Fail 'UNSAFE_TARGET' 'Target must be the Git project root, not a nested directory.'
    }

    $state = Read-ProjectManifest $repo
    $manifestHashSnapshot = Get-FileHashText $state.Path
    $manifest = $state.Manifest
    $installed = @(Get-InstalledHarnesses $manifest)
    $selected = @('opencode')

    foreach ($name in $selected) {
        if ($name -notin $installed) {
            Fail 'HARNESS_NOT_INSTALLED' "Harness '$name' is not recorded as installed in this project."
        }
    }

    $entries = @($manifest.managed_files)
    if ($entries.Count -ne $CurrentProjectInventory.Count) {
        Fail 'PROJECT_MANIFEST_INVALID' 'managed_files is not the exact current OpenCode inventory.'
    }

    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $validated = [System.Collections.Generic.List[object]]::new()
    foreach ($entry in $entries) {
        $relative = Normalize-Relative ([string]$entry.path)
        if (-not $seen.Add($relative)) {
            Fail 'PROJECT_MANIFEST_INVALID' "Duplicate managed path: $relative"
        }
        if ($relative -cnotin $CurrentProjectInventory) {
            Fail 'PROJECT_MANIFEST_INVALID' "Managed path is not in the current OpenCode inventory: $relative"
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
    if ($remove.Count -eq 0) {
        Fail 'PROJECT_MANIFEST_INVALID' 'The selected harness has no managed files recorded.'
    }


    # All read-only rejection checks finish before acquiring the stable lock.
    # Revalidate the manifest and managed bytes under that lock before writing.
    . (Join-Path $PSScriptRoot 'target-writer-lock.ps1')
    $writerLock = Enter-OlympusTargetWriterLock $repo
    Assert-No-Config-Recovery $repo
    $revalidatedState = Read-ProjectManifest $repo
    if (-not [string]::Equals($revalidatedState.Path, $state.Path, $pathComparison) -or
        (Get-FileHashText $revalidatedState.Path) -cne $manifestHashSnapshot) {
        Fail 'TARGET_CHANGED' 'Project manifest changed after preflight.'
    }
    foreach ($item in $validated) {
        $currentFull = Resolve-ManagedPath $repo $item.Relative
        if (-not [string]::Equals($currentFull, $item.Full, $pathComparison) -or
            -not (Test-Path -LiteralPath $currentFull -PathType Leaf) -or
            (Get-FileHashText $currentFull) -cne ([string]$item.Entry.sha256).ToLowerInvariant()) {
            Fail 'TARGET_CHANGED' "Managed file changed after preflight: $($item.Relative)"
        }
    }
    Assert-OlympusTargetWriterLock $writerLock
    foreach ($item in $remove) {
        [IO.File]::Delete($item.Full)
        Write-Output "REMOVED: $($item.Relative)"
    }

    [IO.File]::Delete($state.Path)

    Write-Output "OLYMPUS_PROJECT_UNINSTALL: $Harness REMOVED_MANAGED_RESOURCES_ONLY"
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    if ($null -ne $writerLock) { Exit-OlympusTargetWriterLock $writerLock }
}
