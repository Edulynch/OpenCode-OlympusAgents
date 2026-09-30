[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [ValidateSet('opencode', 'codex', 'all')]
    [string]$Harness = 'opencode',
    [string]$SourceVersion = 'local',
    [switch]$DryRun,
    [switch]$VerifyOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$OpenCodeManifestRel = '.opencode/orchestrator-install.json'
$CodexManifestRel = '.codex/orchestrator-install.json'
$ManifestRel = $null
$CurrentManifestRel = $null
$SelectedHarnesses = @()
$OpenCodeGenerated = @{}
$CodexGenerated = @{}
$GeneratedByHarness = @{}
$Managed = @()
$OpenCodeManaged = @()
$CodexManaged = @()
$ExistingHarnesses = @()
$InstalledHarnesses = @()
$ExistingEntries = @()
$AllContent = [ordered]@{}
$Retired = @()
if ($SourceVersion -cne 'local' -and $SourceVersion -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
    throw 'SOURCE_VERSION_INVALID: Expected an Olympus SemVer release or local.'
}
$LegacyMaintenanceFiles = @('.opencode/agents/maintenance.md', '.opencode/commands/maintain.md',
    '.opencode/plugins/olympus-activity/activity.ts', '.opencode/plugins/olympus-activity/tui.tsx')
$OldReasoner = '.opencode/agents/sorin.md'
$RetiredMaintenanceAgent = '.opencode/agents/maintenance.md'

function Fail([string]$Code, [string]$Message) { throw "$Code`: $Message" }
function Rel([string]$Path) { ($Path -replace "\\", "/").TrimStart([char[]]@('/')) }
function Has-Cmd([string]$Name) { $null -ne (Get-Command $Name -ErrorAction SilentlyContinue) }

$ReparseTagCache = @{}

function Normalize-Path([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    if (-not [string]::Equals($full, $root, [StringComparison]::OrdinalIgnoreCase)) {
        $full = $full.TrimEnd([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar))
    }
    return $full
}

function Get-ReparseTag([string]$Path) {
    $full = Normalize-Path $Path
    if ($ReparseTagCache.ContainsKey($full)) { return [uint32]$ReparseTagCache[$full] }
    $fsutil = Get-Command fsutil.exe -ErrorAction SilentlyContinue
    if (-not $fsutil) { throw ('REPARSE_PATH_UNVERIFIABLE: fsutil.exe is unavailable for ' + $full) }
    $output = & $fsutil.Source reparsepoint query $full 2>&1
    $exitCode = $LASTEXITCODE
    $match = [regex]::Match(($output | Out-String), '(?i)0x([0-9a-f]{8})')
    if ($exitCode -ne 0 -or -not $match.Success) {
        throw ('REPARSE_PATH_UNVERIFIABLE: cannot read the reparse tag for ' + $full)
    }
    $tag = [Convert]::ToUInt32($match.Groups[1].Value, 16)
    $ReparseTagCache[$full] = $tag
    return $tag
}

function Resolve-PhysicalPath([string]$Path) {
    $full = Normalize-Path $Path
    $volumeRoot = [IO.Path]::GetPathRoot($full)
    $parts = $full.Substring($volumeRoot.Length).Split(
        [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar),
        [StringSplitOptions]::RemoveEmptyEntries)
    $current = $volumeRoot
    for ($i = 0; $i -lt $parts.Count; $i++) {
        $next = Join-Path $current $parts[$i]
        $entry = Get-Item -LiteralPath $next -Force -ErrorAction SilentlyContinue
        if ($null -eq $entry) {
            $remaining = @()
            for ($j = $i; $j -lt $parts.Count; $j++) { $remaining += $parts[$j] }
            $current = Join-Path $current ($remaining -join [IO.Path]::DirectorySeparatorChar)
            break
        }
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $tag = Get-ReparseTag $next
            if (($tag -band [uint32]0x20000000) -ne 0) {
                try { $resolved = $entry.ResolveLinkTarget($true) }
                catch { throw ('REPARSE_PATH_UNVERIFIABLE: cannot resolve ' + $next + ': ' + $_.Exception.Message) }
                if ($null -eq $resolved) { throw ('REPARSE_PATH_UNVERIFIABLE: no redirect target for ' + $next) }
                $current = Normalize-Path $resolved.FullName
            } else {
                # Cloud Files and other non-name-surrogate reparse tags annotate files;
                # they do not redirect path traversal.
                $current = Normalize-Path $entry.FullName
            }
        } else {
            $current = Normalize-Path $entry.FullName
        }
    }
    return Normalize-Path $current
}

function Path-Is-Within([string]$Candidate, [string]$Base, [switch]$AllowEqual) {
    $candidatePath = Resolve-PhysicalPath $Candidate
    $basePath = Resolve-PhysicalPath $Base
    if ([string]::Equals($candidatePath, $basePath, [StringComparison]::OrdinalIgnoreCase)) { return [bool]$AllowEqual }
    $prefix = if ($basePath.EndsWith([IO.Path]::DirectorySeparatorChar)) { $basePath } else { $basePath + [IO.Path]::DirectorySeparatorChar }
    return $candidatePath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)
}

function Canonical-Dir([string]$Path) {
    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    $item = Get-Item -LiteralPath $resolved -Force
    if (-not $item.PSIsContainer) { Fail "TARGET_NOT_DIRECTORY" $Path }
    return Resolve-PhysicalPath $item.FullName
}

function Sha-Bytes([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace("-", "").ToLowerInvariant() }
    finally { $sha.Dispose() }
}
function Sha-Text([string]$Text) { Sha-Bytes $Utf8NoBom.GetBytes($Text) }
function Sha-File([string]$Path) { Sha-Bytes ([IO.File]::ReadAllBytes($Path)) }

function Write-Text([string]$Path, [string]$Content) {
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) { [IO.Directory]::CreateDirectory($parent) | Out-Null }
    [IO.File]::WriteAllText($Path, $Content, $Utf8NoBom)
}

function Get-GeneratedHarnessOutputs([string]$Name) {
    $adapterRoot = Join-Path $SourceRoot ('.' + $Name)
    $outputs = [ordered]@{}
    if (-not (Test-Path -LiteralPath $adapterRoot -PathType Container)) {
        Fail 'SOURCE_FILE_MISSING' ("Generated $Name output directory is missing.")
    }
    $prefix = [IO.Path]::GetFullPath($SourceRoot).TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    foreach ($file in @(Get-ChildItem -LiteralPath $adapterRoot -File -Recurse -Force | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($prefix.Length).Replace('\', '/')
        $text = [IO.File]::ReadAllText($file.FullName)
        if ($text -notmatch 'GENERATED BY scripts/render_harnesses\.py') {
            Fail 'SOURCE_INVALID' ("Harness source file is not a generated Harness Core output: $relative")
        }
        $outputs[$relative] = $text
    }
    $rootOutput = if ($Name -eq 'opencode') { 'opencode.jsonc' } else { 'CODEX.md' }
    $rootPath = Join-Path $SourceRoot $rootOutput
    if (-not (Test-Path -LiteralPath $rootPath -PathType Leaf)) {
        Fail 'SOURCE_FILE_MISSING' ("Generated harness root output is missing: $rootOutput")
    }
    $rootText = [IO.File]::ReadAllText($rootPath)
    if ($rootText -notmatch 'GENERATED BY scripts/render_harnesses\.py') {
        Fail 'SOURCE_INVALID' ("Harness root file is not a generated Harness Core output: $rootOutput")
    }
    $outputs[$rootOutput] = $rootText
    if ($outputs.Count -eq 0) { Fail 'SOURCE_INVALID' ("No generated outputs found for $Name.") }
    return ,$outputs
}

function Get-HarnessSelection([string]$Name) {
    switch ($Name.ToLowerInvariant()) {
        'opencode' { return @('opencode') }
        'codex' { return @('codex') }
        'all' { return @('opencode', 'codex') }
        default { Fail 'HARNESS_INVALID' "Unsupported harness '$Name'." }
    }
}

function Get-SelectedGeneratedContent([string[]]$Harnesses) {
    $content = [ordered]@{}
    foreach ($harness in $Harnesses) {
        foreach ($path in $GeneratedByHarness[$harness].Keys) { $content[$path] = [string]$GeneratedByHarness[$harness][$path] }
    }
    return ,$content
}

function Assert-Target([string]$Raw) {
    if (-not [IO.Path]::IsPathFullyQualified($Raw)) { Fail "UNSAFE_TARGET" "Target must be absolute." }
    $target = Canonical-Dir $Raw
    $root = [IO.Path]::GetPathRoot($target).TrimEnd([char[]]@('\','/'))
    if ([string]::Equals($target, $root, [System.StringComparison]::OrdinalIgnoreCase)) {
        Fail "UNSAFE_TARGET" "Filesystem root is not allowed."
    }
    $homes = @($HOME, [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)) |
        Where-Object { $_ } | ForEach-Object { Resolve-PhysicalPath $_ }
    if ($homes | Where-Object { [string]::Equals($_, $target, [System.StringComparison]::OrdinalIgnoreCase) }) {
        Fail "UNSAFE_TARGET" "User home/profile is not allowed."
    }
    $gitRootRaw = (& git -C $target rev-parse --show-toplevel 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $gitRootRaw) { Fail "TARGET_NOT_GIT" "Target must be a Git worktree." }
    $gitRoot = Canonical-Dir $gitRootRaw
    if (-not [string]::Equals($target, $gitRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Fail "TARGET_NOT_GIT_ROOT" "Use the worktree root: $gitRoot"
    }
    foreach ($surface in @('.opencode', '.codex')) {
        $surfacePath = Join-Path $target $surface
        if (Test-Path -LiteralPath $surfacePath) {
            $surfaceItem = Get-Item -LiteralPath $surfacePath -Force
            if (-not $surfaceItem.PSIsContainer) { Fail "UNSAFE_TARGET_PATH" "$surface is not a directory." }
            if (-not (Path-Is-Within $surfacePath $target -AllowEqual)) {
                Fail "UNSAFE_TARGET_PATH" "$surface resolves outside the target repository."
            }
        }
    }
    return $target
}

function Assert-Install-Destinations([string]$Repo) {
    foreach ($p in @($Managed) + @($OpenCodeManifestRel, $CodexManifestRel, $OldReasoner, $RetiredMaintenanceAgent)) {
        $path = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Path-Is-Within $path $Repo)) {
            Fail "UNSAFE_TARGET_PATH" "Install destination escapes the target repository: $p"
        }
    }
}

function Read-Manifest([string]$Repo) {
    $opencodePath = Join-Path $Repo ($OpenCodeManifestRel -replace '/', [IO.Path]::DirectorySeparatorChar)
    $codexPath = Join-Path $Repo ($CodexManifestRel -replace '/', [IO.Path]::DirectorySeparatorChar)
    if ((Test-Path -LiteralPath $opencodePath) -and -not (Test-Path -LiteralPath $opencodePath -PathType Leaf)) {
        Fail 'INSTALL_CONFLICT' 'OpenCode install manifest path is not a file.'
    }
    if ((Test-Path -LiteralPath $codexPath) -and -not (Test-Path -LiteralPath $codexPath -PathType Leaf)) {
        Fail 'INSTALL_CONFLICT' 'Codex install manifest path is not a file.'
    }
    $hasOpenCode = Test-Path -LiteralPath $opencodePath -PathType Leaf
    $hasCodex = Test-Path -LiteralPath $codexPath -PathType Leaf
    if ($hasOpenCode -and $hasCodex) { Fail 'INSTALL_CONFLICT' 'Both harness install manifests exist; refusing ambiguous ownership metadata.' }
    if (-not $hasOpenCode -and -not $hasCodex) { return $null }
    $script:CurrentManifestRel = if ($hasOpenCode) { $OpenCodeManifestRel } else { $CodexManifestRel }
    $path = if ($hasOpenCode) { $opencodePath } else { $codexPath }
    try { return ([IO.File]::ReadAllText($path) | ConvertFrom-Json -Depth 100) }
    catch { Fail 'INSTALL_CONFLICT' 'Invalid existing install manifest.' }
}

function Get-ManifestHarnesses($Manifest) {
    if ($null -eq $Manifest) { return @() }
    $properties = @($Manifest.PSObject.Properties | ForEach-Object Name)
    if ('installed_harnesses' -in $properties) {
        $values = @($Manifest.installed_harnesses | ForEach-Object { ([string]$_).ToLowerInvariant() })
        if ($values.Count -eq 0 -or @($values | Where-Object { $_ -notin @('opencode', 'codex') }).Count -gt 0 -or
            @($values | Select-Object -Unique).Count -ne $values.Count) {
            Fail 'INSTALL_MANIFEST_INCOMPATIBLE' 'Manifest installed_harnesses is empty, duplicated, or unsupported.'
        }
        return @(@('opencode', 'codex') | Where-Object { $_ -in $values })
    }
    # beta.4 and earlier used the OpenCode-only manifest with no harness field.
    return @('opencode')
}

function Get-LegacyOpenCodeSets {
    $previous = @('.opencode/plugins/olympus-activity/activity.ts', '.opencode/plugins/olympus-activity/tui.tsx')
    # Historical sets had maintenance where the new candidate has aegis.
    $historical = @($OpenCodeManaged | ForEach-Object { if ($_ -eq '.opencode/agents/aegis.md') { $RetiredMaintenanceAgent } else { $_ } })
    $currentBeforeArgus = @($historical | Where-Object { $_ -notin @('.opencode/agents/argus.md', '.opencode/agents/talos.md', '.opencode/agents/helios.md') })
    $currentBeforeTalos = @($historical | Where-Object { $_ -notin @('.opencode/agents/talos.md', '.opencode/agents/helios.md') })
    $currentBeforeHelios = @($historical | Where-Object { $_ -ne '.opencode/agents/helios.md' })
    # Recognize exact historical owned sets, including pre-maintenance and pre-HUD
    # manifests. Counts alone cannot distinguish the old and new reasoner identity.
    $allowed = @()
    foreach ($reasoner in @($OldReasoner, '.opencode/agents/thales.md')) {
        $base = @($currentBeforeArgus | Where-Object { $_ -ne '.opencode/agents/atlas.md' } |
            ForEach-Object { if ($_ -eq '.opencode/agents/thales.md') { $reasoner } else { $_ } })
        foreach ($missing in @(@(), $previous, $LegacyMaintenanceFiles)) {
            $allowed += ,@($base | Where-Object { $_ -notin $missing })
        }
    }
    # Some focused upgrade fixtures simulate pre-HUD/pre-Maintenance ownership
    # from a currently installed candidate, retaining its Atlas-owned path.
    foreach ($missing in @(@(), $previous, $LegacyMaintenanceFiles)) {
        $allowed += ,@($currentBeforeArgus | Where-Object { $_ -notin $missing })
    }
    # Focused legacy fixtures can retain the already-owned current reasoner while
    # reconstructing pre-HUD/pre-Maintenance ownership. Exact sets and hashes
    # still govern every existing path; unowned new destinations still conflict.
    foreach ($missing in @(@(), $previous, $LegacyMaintenanceFiles)) {
        $allowed += ,@($currentBeforeTalos | Where-Object { $_ -notin $missing })
    }
    foreach ($missing in @(@(), $previous, $LegacyMaintenanceFiles)) {
        $allowed += ,@($currentBeforeHelios | Where-Object { $_ -notin $missing })
    }
    foreach ($missing in @(@(), $previous, $LegacyMaintenanceFiles)) {
        $allowed += ,@($OpenCodeManaged | Where-Object { $_ -notin $missing })
        $allowed += ,@($historical | Where-Object { $_ -notin $missing })
    }
    return ,$allowed
}

function Assert-Managed([string]$Repo, $Manifest) {
    if ($null -eq $Manifest) { $script:ExistingHarnesses = @(); $script:ExistingEntries = @(); return @() }
    if ($Manifest.schema_version -ne 1 -or $null -eq $Manifest.managed_files) {
        Fail 'INSTALL_MANIFEST_INCOMPATIBLE' 'Unsupported manifest schema or missing managed_files.'
    }
    $script:ExistingHarnesses = @(Get-ManifestHarnesses $Manifest)
    $entries = @($Manifest.managed_files)
    $actual = @($entries | ForEach-Object { Rel ([string]$_.path) })
    $allowedSets = @()
    if ('opencode' -in $ExistingHarnesses) {
        foreach ($candidate in (Get-LegacyOpenCodeSets)) {
            if ('codex' -in $ExistingHarnesses) { $candidate = @($candidate) + @($CodexManaged) }
            $allowedSets += ,@($candidate)
        }
    }
    if ('codex' -in $ExistingHarnesses -and 'opencode' -notin $ExistingHarnesses) {
        $allowedSets += ,@($CodexManaged)
    }
    $matchCount = 0
    foreach ($candidate in $allowedSets) {
        if ($candidate.Count -eq $actual.Count -and
            @($actual | Where-Object { $_ -notin $candidate }).Count -eq 0) { $matchCount++ }
    }
    if ($matchCount -ne 1) { Fail 'INSTALL_MANIFEST_INCOMPATIBLE' 'Managed file set differs from the installed harness inventory.' }
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($e in $entries) {
        $p = Rel ([string]$e.path)
        if (-not $seen.Add($p)) {
            Fail "INSTALL_MANIFEST_INCOMPATIBLE" "Unexpected or duplicate managed path: $p"
        }
        $full = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $full)) { Fail "MANAGED_FILE_DRIFT" "Missing managed file: $p" }
        if ((Sha-File $full) -ne ([string]$e.sha256).ToLowerInvariant()) {
            Fail "MANAGED_FILE_DRIFT" "Managed file modified: $p"
        }
    }
    foreach ($old in @($OldReasoner, $RetiredMaintenanceAgent)) {
        if ($old -notin $actual -and (Test-Path -LiteralPath (Join-Path $Repo ($old -replace '/', [IO.Path]::DirectorySeparatorChar)))) {
            Fail 'INSTALL_CONFLICT' "Unowned retired agent exists: $old"
        }
    }
    $script:ExistingEntries = @($entries)
    return @($actual | Where-Object { $_ -in @($OldReasoner, $RetiredMaintenanceAgent) })
}

function Assert-No-Conflicts([string]$Repo, $Manifest, $Content) {
    if ('opencode' -in $SelectedHarnesses) {
        foreach ($p in @('opencode.json', '.opencode/opencode.json', '.opencode/opencode.jsonc')) {
            if (Test-Path -LiteralPath (Join-Path $Repo ($p -replace '/', [IO.Path]::DirectorySeparatorChar))) {
                Fail 'INSTALL_CONFLICT' "Foreign OpenCode config exists: $p"
            }
        }
    }
    $owned = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $ExistingEntries) { [void]$owned.Add((Rel ([string]$entry.path))) }
    foreach ($p in $Managed) {
        $full = Join-Path $Repo ($p -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $full) -or $owned.Contains($p)) { continue }
        $actual = [IO.File]::ReadAllText($full)
        if ('opencode' -in $SelectedHarnesses -and ($p -eq 'opencode.jsonc' -or $p.StartsWith('.opencode/', [StringComparison]::OrdinalIgnoreCase))) {
            Fail 'INSTALL_CONFLICT' "Destination exists without ownership metadata: $p"
        }
        if ($actual -cne [string]$Content[$p]) {
            Fail 'INSTALL_CONFLICT' "Destination exists without ownership metadata and differs from generated output: $p"
        }
    }
    if ('opencode' -in $SelectedHarnesses) {
        foreach ($old in @($OldReasoner, $RetiredMaintenanceAgent)) {
            $full = Join-Path $Repo ($old -replace '/', [IO.Path]::DirectorySeparatorChar)
            if ((Test-Path -LiteralPath $full) -and -not $owned.Contains($old)) {
                Fail 'INSTALL_CONFLICT' "Unowned retired agent exists: $old"
            }
        }
    }
}

function Add-Unique([System.Collections.Generic.List[string]]$List, [System.Collections.Generic.HashSet[string]]$Seen, [string]$Value) {
    if ($Seen.Add($Value)) { $List.Add($Value) }
}

function Detect-Project([string]$Repo) {
    $stacks = [System.Collections.Generic.List[string]]::new()
    $commands = [System.Collections.Generic.List[string]]::new()
    $warnings = [System.Collections.Generic.List[string]]::new()
    $stackSeen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $commandSeen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $packageManager = $null

    $packagePath = Join-Path $Repo "package.json"
    if (Test-Path -LiteralPath $packagePath) {
        [void]$stackSeen.Add("node"); $stacks.Add("node")
        try { $pkg = [IO.File]::ReadAllText($packagePath) | ConvertFrom-Json -Depth 100 }
        catch { Fail "INVALID_PACKAGE_JSON" "package.json could not be parsed." }

        $pm = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($pair in @(
            @("npm","package-lock.json"),
            @("pnpm","pnpm-lock.yaml"),
            @("yarn","yarn.lock"),
            @("bun","bun.lock"),
            @("bun","bun.lockb")
        )) {
            if (Test-Path -LiteralPath (Join-Path $Repo $pair[1])) { [void]$pm.Add($pair[0]) }
        }
        if ($pkg.PSObject.Properties.Name -contains "packageManager" -and $pkg.packageManager) {
            $declared = ([string]$pkg.packageManager).Split("@")[0].ToLowerInvariant()
            if ($declared -in @("npm","pnpm","yarn","bun")) { [void]$pm.Add($declared) }
        }
        if ($pm.Count -gt 1) { Fail "AMBIGUOUS_PACKAGE_MANAGER" (($pm | Sort-Object) -join ", ") }
        if ($pm.Count -eq 1) { $packageManager = @($pm)[0] }
        else { $warnings.Add("NODE_PACKAGE_MANAGER_UNDETERMINED") }

        if ($packageManager) {
            if (-not (Has-Cmd $packageManager)) { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: $packageManager") }
            else {
                $scriptNames = @{}
                if ($pkg.PSObject.Properties.Name -contains "scripts" -and $pkg.scripts) {
                    foreach ($p in $pkg.scripts.PSObject.Properties) { $scriptNames[$p.Name] = $true }
                }
                foreach ($name in @("test","lint","typecheck","build")) {
                    if (-not $scriptNames.ContainsKey($name)) { continue }
                    $cmd = $null
                    switch ($packageManager) {
                        "npm"  { if ($name -eq "test") { $cmd = "npm test" } else { $cmd = "npm run $name" } }
                        "pnpm" { $cmd = "pnpm $name" }
                        "yarn" { $cmd = "yarn $name" }
                        "bun"  { if ($name -eq "test") { $cmd = "bun test" } else { $warnings.Add("VALIDATION_COMMAND_DEFERRED: bun $name") } }
                    }
                    if ($cmd) { Add-Unique $commands $commandSeen $cmd }
                }
            }
        }
    }

    $py = Join-Path $Repo "pyproject.toml"
    $pytestIni = Join-Path $Repo "pytest.ini"
    $setupCfg = Join-Path $Repo "setup.cfg"
    $reqs = @(Get-ChildItem -LiteralPath $Repo -File -Filter "requirements*.txt" -ErrorAction SilentlyContinue)
    if ((Test-Path $py) -or (Test-Path $pytestIni) -or (Test-Path $setupCfg) -or $reqs.Count) {
        if ($stackSeen.Add("python")) { $stacks.Add("python") }
        $pyText = if (Test-Path $py) { [IO.File]::ReadAllText($py) } else { "" }
        $setupText = if (Test-Path $setupCfg) { [IO.File]::ReadAllText($setupCfg) } else { "" }
        $reqText = ($reqs | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"

        $usesPytest = (Test-Path $pytestIni) -or $pyText -match "(?m)^\s*\[tool\.pytest" -or
            $setupText -match "(?m)^\s*\[tool:pytest\]" -or $reqText -match "(?mi)^\s*pytest(?:\s*[<>=!~].*)?\s*$"
        if ($usesPytest) {
            if (Has-Cmd "pytest") { Add-Unique $commands $commandSeen "pytest" }
            else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: pytest") }
        }
        $usesRuff = (Test-Path (Join-Path $Repo "ruff.toml")) -or (Test-Path (Join-Path $Repo ".ruff.toml")) -or
            $pyText -match "(?m)^\s*\[tool\.ruff"
        if ($usesRuff) {
            if (Has-Cmd "ruff") { Add-Unique $commands $commandSeen "ruff check ." }
            else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: ruff") }
        }
        if ($pyText -match "(?m)^\s*\[tool\.basedpyright") {
            if (Has-Cmd "basedpyright") { Add-Unique $commands $commandSeen "basedpyright" }
            else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: basedpyright") }
        }
        elseif ((Test-Path (Join-Path $Repo "pyrightconfig.json")) -or $pyText -match "(?m)^\s*\[tool\.pyright") {
            if (Has-Cmd "pyright") { Add-Unique $commands $commandSeen "pyright" }
            else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: pyright") }
        }
    }

    if (Test-Path (Join-Path $Repo "pom.xml")) {
        if ($stackSeen.Add("maven")) { $stacks.Add("maven") }
        if (Test-Path (Join-Path $Repo "mvnw.cmd")) {
            Add-Unique $commands $commandSeen ".\mvnw.cmd test"; Add-Unique $commands $commandSeen ".\mvnw.cmd verify"
        } elseif (Has-Cmd "mvn") {
            Add-Unique $commands $commandSeen "mvn test"; Add-Unique $commands $commandSeen "mvn verify"
        } else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: mvn") }
    }

    if ((Test-Path (Join-Path $Repo "build.gradle")) -or (Test-Path (Join-Path $Repo "build.gradle.kts"))) {
        if ($stackSeen.Add("gradle")) { $stacks.Add("gradle") }
        if (Test-Path (Join-Path $Repo "gradlew.bat")) {
            Add-Unique $commands $commandSeen ".\gradlew.bat test"; Add-Unique $commands $commandSeen ".\gradlew.bat check"
        } else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: gradle wrapper") }
    }

    $pubspec = Join-Path $Repo "pubspec.yaml"
    if (Test-Path $pubspec) {
        $text = [IO.File]::ReadAllText($pubspec)
        if ($text -match "(?m)^\s*flutter\s*:") {
            if ($stackSeen.Add("flutter")) { $stacks.Add("flutter") }
            if (Has-Cmd "flutter") {
                Add-Unique $commands $commandSeen "flutter analyze"; Add-Unique $commands $commandSeen "flutter test"
            } else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: flutter") }
        } else {
            if ($stackSeen.Add("dart")) { $stacks.Add("dart") }
            if (Has-Cmd "dart") {
                Add-Unique $commands $commandSeen "dart analyze"; Add-Unique $commands $commandSeen "dart test"
            } else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: dart") }
        }
    }

    if (Test-Path (Join-Path $Repo "Cargo.toml")) {
        if ($stackSeen.Add("rust")) { $stacks.Add("rust") }
        if (Has-Cmd "cargo") {
            Add-Unique $commands $commandSeen "cargo check"; Add-Unique $commands $commandSeen "cargo test"
        } else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: cargo") }
    }
    if (Test-Path (Join-Path $Repo "go.mod")) {
        if ($stackSeen.Add("go")) { $stacks.Add("go") }
        if (Has-Cmd "go") { Add-Unique $commands $commandSeen "go test ./..." }
        else { $warnings.Add("VALIDATION_TOOL_UNAVAILABLE: go") }
    }

    [pscustomobject]@{
        Stacks = @($stacks)
        ValidationCommands = @($commands)
        Warnings = @($warnings)
        PackageManager = $packageManager
    }
}

function Manifest-Text($Detection, $Content, [string]$Version) {
    $files = foreach ($p in @($Content.Keys | Sort-Object)) { [ordered]@{ path=$p; sha256=Sha-Text ([string]$Content[$p]) } }
    $commit = (& git -C $SourceRoot rev-parse HEAD 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commit) { $commit = "unknown" }
    ([ordered]@{
        schema_version = 1
        installed_version = $Version
        installed_from_commit = $commit
        installed_harnesses = @($InstalledHarnesses)
        managed_files = @($files)
        detected_stacks = @($Detection.Stacks)
        package_manager = $Detection.PackageManager
        validation_commands = @($Detection.ValidationCommands)
    } | ConvertTo-Json -Depth 20) + "`n"
}

function Plan([string]$Repo, $Content, [string]$ManifestText, [string[]]$Retired) {
    $create = [System.Collections.Generic.List[string]]::new()
    $update = [System.Collections.Generic.List[string]]::new()
    foreach ($p in @($Content.Keys | Sort-Object)) {
        $full = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path $full)) { $create.Add($p) }
        elseif ((Sha-File $full) -ne (Sha-Text ([string]$Content[$p]))) { $update.Add($p) }
    }
    $mf = Join-Path $Repo ($ManifestRel -replace "/", [IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path $mf)) { $create.Add($ManifestRel) }
    elseif ((Sha-File $mf) -ne (Sha-Text $ManifestText)) { $update.Add($ManifestRel) }
    $removeList = [System.Collections.Generic.List[string]]::new()
    foreach ($p in $Retired) { if ($p -notin $removeList) { $removeList.Add($p) } }
    if ($CurrentManifestRel -and $CurrentManifestRel -cne $ManifestRel) { $removeList.Add($CurrentManifestRel) }
    [pscustomobject]@{ Creates=@($create); Updates=@($update); Removes=@($removeList) }
}

function Report([string]$Repo, $Detection, $Plan, [string]$Status, [string]$Version, [string]$ModelCheck) {
    Write-Output "TARGET:"; Write-Output $Repo
    Write-Output "TRUST:"; Write-Output "EXPLICIT_BOOTSTRAP"
    Write-Output "STACKS:"; if ($Detection.Stacks.Count) { $Detection.Stacks } else { "(none)" }
    Write-Output "PACKAGE_MANAGER:"; if ($Detection.PackageManager) { $Detection.PackageManager } else { "(none)" }
    Write-Output "VALIDATION:"; $Detection.ValidationCommands
    Write-Output "WARNINGS:"; if ($Detection.Warnings.Count) { $Detection.Warnings } else { "(none)" }
    Write-Output "FILES_TO_CREATE:"; if ($Plan.Creates.Count) { $Plan.Creates } else { "(none)" }
    Write-Output "FILES_TO_UPDATE:"; if ($Plan.Updates.Count) { $Plan.Updates } else { "(none)" }
    Write-Output "FILES_TO_REMOVE:"; if ($Plan.Removes.Count) { $Plan.Removes } else { "(none)" }
    Write-Output "CONFLICTS:"; Write-Output "(none)"
    Write-Output "HARNESS:"; Write-Output ($SelectedHarnesses -join ', ')
    if ('opencode' -in $SelectedHarnesses) { Write-Output "OPENCODE:"; Write-Output $Version }
    Write-Output "MODEL_CHECK:"; Write-Output $ModelCheck
    Write-Output "STATUS:"; Write-Output $Status
}

function Get-Expected-Agents {
    $agentsRoot = Join-Path $SourceRoot '.opencode/agents'
    $files = @(Get-ChildItem -LiteralPath $agentsRoot -Filter '*.md' -File)
    $expected = @{}
    foreach ($file in $files) {
        $text = [IO.File]::ReadAllText($file.FullName)
        $model = [regex]::Match($text, '(?m)^model:\s*["'']?openai/(?<id>[^#"''\s]+)#(?<effort>[A-Za-z]+)["'']?\s*$')
        $mode = [regex]::Match($text, '(?m)^mode:\s*(?<mode>primary|subagent)\s*$')
        if (-not $model.Success -or -not $mode.Success) {
            Fail 'SOURCE_AGENT_MODEL_INVALID' ("Generated role metadata is incomplete: " + $file.Name)
        }
        $expected[$file.BaseName] = @($model.Groups['id'].Value, $model.Groups['effort'].Value, $mode.Groups['mode'].Value)
    }
    $managedAgentCount = @($OpenCodeManaged | Where-Object { $_ -match '^\.opencode/agents/[^/]+\.md$' }).Count
    if ($files.Count -ne $managedAgentCount -or $expected.Count -ne $managedAgentCount) {
        Fail 'SOURCE_AGENT_ROSTER_INVALID' 'Generated OpenCode role files do not match the installer-managed roster.'
    }
    return $expected
}

function Validate-Install([string]$Repo) {
    $expected = Get-Expected-Agents
    $lastMismatch = $null
    Push-Location $Repo
    try {
        for ($attempt = 1; $attempt -le 5; $attempt++) {
            & opencode debug config *> $null
            if ($LASTEXITCODE -ne 0) { Fail "OPENCODE_VALIDATION_FAILED" "debug config failed." }
            $json = (& opencode debug agents 2>$null | Out-String)
            if ($LASTEXITCODE -ne 0) { Fail "OPENCODE_VALIDATION_FAILED" "debug agents failed." }
            try { $agents = $json | ConvertFrom-Json -Depth 100 }
            catch { Fail "OPENCODE_VALIDATION_FAILED" "debug agents output is not JSON." }

            $lastMismatch = $null
            foreach ($name in $expected.Keys) {
                $a = @($agents | Where-Object id -eq $name)
                if ($a.Count -ne 1) {
                    $lastMismatch = "Unexpected effective agent: $name (count=$($a.Count); attempt=$attempt)."
                    break
                }
                $modelId = [string]$a[0].model.id
                $variant = [string]$a[0].model.variant
                $mode = [string]$a[0].mode
                if ($modelId -ne $expected[$name][0] -or $variant -ne $expected[$name][1] -or $mode -ne $expected[$name][2]) {
                    $actual = "$modelId#$variant/$mode"
                    $wanted = "$($expected[$name][0])#$($expected[$name][1])/$($expected[$name][2])"
                    $lastMismatch = "Unexpected effective agent: $name (got $actual; expected $wanted; attempt=$attempt)."
                    break
                }
            }
            if ($null -eq $lastMismatch -and @($agents | Where-Object { $_.id -in @('sorin','maintenance') }).Count -gt 0) {
                $lastMismatch = 'Retired sorin or maintenance agent remains active.'
            }
            if ($null -eq $lastMismatch) { return }
            if ($attempt -lt 5) { Start-Sleep -Milliseconds 250 }
        }
    } finally { Pop-Location }
    Fail "OPENCODE_VALIDATION_FAILED" $lastMismatch
}

function Assert-InstalledHarness([string]$Repo, $Manifest) {
    if ($null -eq $Manifest) { Fail 'MANAGED_FILE_MISMATCH' 'Olympus install manifest is missing.' }
    if ($Manifest.schema_version -ne 1 -or $null -eq $Manifest.managed_files) {
        Fail 'MANAGED_FILE_MISMATCH' 'Olympus install manifest schema or managed file set is unsupported.'
    }
    $manifestProperties = @($Manifest.PSObject.Properties | ForEach-Object Name)
    if ('installed_version' -in $manifestProperties) {
        $recordedVersion = [string]$Manifest.installed_version
        if ($recordedVersion -and $recordedVersion -notin @('unknown', 'local') -and $recordedVersion -cne $SourceVersion) {
            Fail 'INSTALLED_VERSION_MISMATCH' "Manifest records '$recordedVersion'; requested '$SourceVersion'."
        }
    }
    $harnesses = @(Get-ManifestHarnesses $Manifest)
    foreach ($harness in $SelectedHarnesses) {
        if ($harness -notin $harnesses) { Fail 'MANAGED_FILE_MISMATCH' "The installed manifest does not record harness '$harness'." }
        $expected = $GeneratedByHarness[$harness]
        $expectedPaths = @($expected.Keys | Sort-Object)
        $entries = @($Manifest.managed_files)
        $scopeEntries = if ($harness -eq 'opencode') {
            @($entries | Where-Object { ([string]$_.path).Replace('\','/') -match '^\.opencode/' -or ([string]$_.path).Replace('\','/') -eq 'opencode.jsonc' })
        } else {
            @($entries | Where-Object { ([string]$_.path).Replace('\','/') -match '^\.codex/' -or ([string]$_.path).Replace('\','/') -eq 'CODEX.md' })
        }
        $scopePaths = @($scopeEntries | ForEach-Object { Rel ([string]$_.path) } | Sort-Object)
        if ($scopePaths.Count -ne $expectedPaths.Count -or @($expectedPaths | Where-Object { $_ -notin $scopePaths }).Count -gt 0) {
            Fail 'MANAGED_FILE_MISMATCH' "Installed managed file set differs for requested harness '$harness'."
        }
        foreach ($relative in $expectedPaths) {
            $matched = @($scopeEntries | Where-Object { (Rel ([string]$_.path)) -ceq $relative })
            if ($matched.Count -ne 1) { Fail 'MANAGED_FILE_MISMATCH' "Manifest does not uniquely own '$relative'." }
            $full = Join-Path $Repo ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
            if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { Fail 'MANAGED_FILE_MISSING' "Installed managed file is missing: $relative" }
            $expectedHash = Sha-Text ([string]$expected[$relative])
            $targetHash = Sha-File $full
            if ($targetHash -cne $expectedHash -or ([string]$matched[0].sha256).ToLowerInvariant() -cne $targetHash) {
                Fail 'MANAGED_FILE_MISMATCH' "Installed managed content differs from the requested release: $relative"
            }
        }
    }
    if ('opencode' -in $SelectedHarnesses) {
        foreach ($retiredPath in @($OldReasoner, $RetiredMaintenanceAgent)) {
            $retiredFile = Join-Path $Repo ($retiredPath -replace '/', [IO.Path]::DirectorySeparatorChar)
            if (Test-Path -LiteralPath $retiredFile) {
                Fail 'ROSTER_MISMATCH' "Retired or unowned OpenCode agent remains present: $retiredPath"
            }
        }
        if (-not (Has-Cmd 'opencode')) { Fail 'ROSTER_MISMATCH' 'OpenCode CLI is required to validate the active agent roster.' }
        Validate-Install $Repo
    }
}

try {
    if ($VerifyOnly -and $DryRun) { Fail 'VERIFY_MODE_INVALID' '-VerifyOnly and -DryRun cannot be combined.' }
    $SelectedHarnesses = @(Get-HarnessSelection $Harness)
    if (-not (Has-Cmd 'git')) { Fail 'GIT_UNAVAILABLE' 'git is required.' }
    $Repo = Assert-Target $Target
    $manifest = Read-Manifest $Repo
    $inventoryHarnesses = @($SelectedHarnesses)
    if (-not $VerifyOnly -and $null -ne $manifest) {
        foreach ($harness in (Get-ManifestHarnesses $manifest)) {
            if ($harness -notin $inventoryHarnesses) { $inventoryHarnesses += $harness }
        }
    }
    foreach ($harness in $inventoryHarnesses) {
        $GeneratedByHarness[$harness] = Get-GeneratedHarnessOutputs $harness
    }
    if ('opencode' -in $GeneratedByHarness.Keys) {
        $OpenCodeGenerated = $GeneratedByHarness['opencode']
        $OpenCodeManaged = @($OpenCodeGenerated.Keys | Sort-Object)
    }
    if ('codex' -in $GeneratedByHarness.Keys) {
        $CodexGenerated = $GeneratedByHarness['codex']
        $CodexManaged = @($CodexGenerated.Keys | Sort-Object)
    }
    $ManagedContent = Get-SelectedGeneratedContent $SelectedHarnesses
    $Managed = @($ManagedContent.Keys | Sort-Object)
    Assert-Install-Destinations $Repo
    $Version = 'NOT_REQUIRED'
    $ModelCheck = 'NOT_REQUIRED'
    if ('opencode' -in $SelectedHarnesses) {
        if (-not (Has-Cmd 'opencode')) { Fail 'OPENCODE_UNAVAILABLE' 'OpenCode is required for the OpenCode harness.' }
        $Version = (& opencode --version 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { Fail 'OPENCODE_UNAVAILABLE' 'opencode --version failed.' }
        $ModelCheck = 'DISCOVERY_UNAVAILABLE'
        $models = (& opencode models 2>$null | Out-String)
        if ($LASTEXITCODE -eq 0 -and $models) {
            if ($models -notmatch [regex]::Escape('openai/gpt-6.1-sol') -or
                $models -notmatch [regex]::Escape('openai/gpt-6-luna')) {
                Fail 'MODEL_UNAVAILABLE' 'Required GPT-6.1 Sol/GPT-6 Luna IDs are absent.'
            }
            $ModelCheck = 'GPT61_SOL_GPT6_LUNA_IDS_AVAILABLE'
        }
    }

    if ($VerifyOnly) {
        Assert-InstalledHarness $Repo $manifest
        Write-Output "OLYMPUS_VERIFY: $SourceVersion PASS"
        exit 0
    }

    $ownedRetired = @(Assert-Managed $Repo $manifest)
    $ExistingHarnesses = @($script:ExistingHarnesses)
    $InstalledHarnesses = @(@('opencode', 'codex') | Where-Object { $_ -in @($ExistingHarnesses + $SelectedHarnesses) })
    $ManifestRel = if ('opencode' -in $InstalledHarnesses) { $OpenCodeManifestRel } else { $CodexManifestRel }
    $Retired = if ('opencode' -in $SelectedHarnesses) { @($ownedRetired) } else { @() }
    Assert-No-Conflicts $Repo $manifest $ManagedContent
    $manifestDestination = Join-Path $Repo ($ManifestRel -replace '/', [IO.Path]::DirectorySeparatorChar)
    if ((Test-Path -LiteralPath $manifestDestination) -and $CurrentManifestRel -cne $ManifestRel) {
        Fail 'INSTALL_CONFLICT' "Install manifest destination exists without ownership metadata: $ManifestRel"
    }
    # Ownership and destination checks above, not repository-wide Git status,
    # decide whether installation is safe. Unrelated work stays untouched.

    $detection = Detect-Project $Repo
    $AllContent = [ordered]@{}
    if ($null -ne $manifest) {
        foreach ($entry in $ExistingEntries) {
            $p = Rel ([string]$entry.path)
            if ($p -in $Retired) { continue }
            $full = Join-Path $Repo ($p -replace '/', [IO.Path]::DirectorySeparatorChar)
            $AllContent[$p] = [IO.File]::ReadAllText($full)
        }
    }
    foreach ($p in $Managed) { $AllContent[$p] = [string]$ManagedContent[$p] }
    $manifestText = Manifest-Text $detection $AllContent $SourceVersion
    $plan = Plan $Repo $AllContent $manifestText $Retired

    if ($DryRun) {
        Report $Repo $detection $plan "DRY_RUN_READY" $Version $ModelCheck
        exit 0
    }

    if (-not $plan.Creates.Count -and -not $plan.Updates.Count -and -not $plan.Removes.Count) {
        if ('opencode' -in $SelectedHarnesses) { Validate-Install $Repo }
        Report $Repo $detection $plan "NO_CHANGES" $Version $ModelCheck
        exit 0
    }

    foreach ($p in $Managed) {
        $full = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        Write-Text $full ([string]$ManagedContent[$p])
    }
    Write-Text (Join-Path $Repo ($ManifestRel -replace "/", [IO.Path]::DirectorySeparatorChar)) $manifestText

    foreach ($p in $plan.Removes) {
        if ($p -eq $CurrentManifestRel) { continue }
        $full = Join-Path $Repo ($p -replace '/', [IO.Path]::DirectorySeparatorChar)
        $entry = @($ExistingEntries | Where-Object { (Rel ([string]$_.path)) -eq $p })
        if ($entry.Count -ne 1 -or (Sha-File $full) -ne ([string]$entry[0].sha256).ToLowerInvariant()) {
            Fail 'MANAGED_FILE_DRIFT' "Managed file modified before removal: $p"
        }
        [IO.File]::Delete($full)
    }

    foreach ($p in $Managed) {
        $full = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        if ((Sha-File $full) -ne (Sha-Text ([string]$ManagedContent[$p]))) { Fail 'INSTALL_VERIFY_FAILED' $p }
    }
    if ($CurrentManifestRel -and $CurrentManifestRel -cne $ManifestRel) {
        $oldManifest = Join-Path $Repo ($CurrentManifestRel -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $oldManifest -PathType Leaf)) { Fail 'MANAGED_FILE_DRIFT' "Existing manifest disappeared before migration: $CurrentManifestRel" }
        [IO.File]::Delete($oldManifest)
    }

    if ('opencode' -in $SelectedHarnesses) { Validate-Install $Repo }
    Report $Repo $detection $plan "READY" $Version $ModelCheck
    exit 0
}
catch {
    if ($VerifyOnly) {
        $message = $_.Exception.Message
        $reason = if ($message -match '^([A-Z][A-Z0-9_]+):') { $Matches[1] } else { 'VERIFY_FAILED' }
        Write-Output "OLYMPUS_VERIFY: $SourceVersion FAIL"
        Write-Output "OLYMPUS_VERIFY_REASON: $reason"
        Write-Output "OLYMPUS_VERIFY_DETAIL: $message"
    }
    Write-Error $_.Exception.Message
    exit 1
}
