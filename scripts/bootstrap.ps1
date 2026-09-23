[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$ManifestRel = ".opencode/orchestrator-install.json"
$Managed = @(
    "opencode.jsonc",
    ".opencode/agents/kael.md",
    ".opencode/agents/veyra.md",
    ".opencode/agents/orin.md",
    ".opencode/agents/kovan.md",
    ".opencode/agents/nox.md",
    ".opencode/agents/vera.md",
    ".opencode/agents/sorin.md",
    ".opencode/agents/maintenance.md",
    ".opencode/commands/maintain.md"
)
$NewManaged = @('.opencode/agents/maintenance.md', '.opencode/commands/maintain.md')
$SafeGit = @(
    "git status",
    "git status --short",
    "git status --porcelain",
    "git status --porcelain=v2",
    "git diff",
    "git diff --check",
    "git diff --cached",
    "git diff --cached --check",
    "git diff --name-only",
    "git diff --raw",
    "git rev-parse HEAD",
    "git ls-files"
)

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
    $oc = Join-Path $target ".opencode"
    if (Test-Path -LiteralPath $oc) {
        $ocItem = Get-Item -LiteralPath $oc -Force
        if (-not $ocItem.PSIsContainer) { Fail "UNSAFE_TARGET_PATH" ".opencode is not a directory." }
        if (-not (Path-Is-Within $oc $target -AllowEqual)) {
            Fail "UNSAFE_TARGET_PATH" ".opencode resolves outside the target repository."
        }
    }
    return $target
}

function Assert-Install-Destinations([string]$Repo) {
    foreach ($p in @($Managed) + @($ManifestRel)) {
        $path = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Path-Is-Within $path $Repo)) {
            Fail "UNSAFE_TARGET_PATH" "Install destination escapes the target repository: $p"
        }
    }
}

function Dirty-Paths([string]$Repo) {
    $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($argsList in @(
        @("diff","--name-only"),
        @("diff","--cached","--name-only"),
        @("ls-files","--others","--exclude-standard")
    )) {
        $out = & git -C $Repo @argsList 2>$null
        if ($LASTEXITCODE -ne 0) { Fail "GIT_INSPECTION_FAILED" "Cannot inspect target." }
        foreach ($p in $out) { if ($p) { [void]$set.Add((Rel $p)) } }
    }
    @($set)
}

function Read-Manifest([string]$Repo) {
    $path = Join-Path $Repo ($ManifestRel -replace "/", [IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try { [IO.File]::ReadAllText($path) | ConvertFrom-Json -Depth 100 }
    catch { Fail "INSTALL_CONFLICT" "Invalid existing install manifest." }
}

function Assert-Managed([string]$Repo, $Manifest) {
    if ($null -eq $Manifest) { return }
    if ($Manifest.schema_version -ne 1) { Fail "INSTALL_MANIFEST_INCOMPATIBLE" "Unsupported manifest schema." }
    $expected = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $Managed | ForEach-Object { [void]$expected.Add($_) }
    $entries = @($Manifest.managed_files)
    $legacy = $entries.Count -eq ($Managed.Count - $NewManaged.Count)
    if ($entries.Count -ne $Managed.Count -and -not $legacy) { Fail "INSTALL_MANIFEST_INCOMPATIBLE" "Managed file set changed." }
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($e in $entries) {
        $p = Rel ([string]$e.path)
        if (-not $expected.Contains($p) -or ($legacy -and $p -in $NewManaged) -or -not $seen.Add($p)) {
            Fail "INSTALL_MANIFEST_INCOMPATIBLE" "Unexpected or duplicate managed path: $p"
        }
        $full = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $full)) { Fail "MANAGED_FILE_DRIFT" "Missing managed file: $p" }
        if ((Sha-File $full) -ne ([string]$e.sha256).ToLowerInvariant()) {
            Fail "MANAGED_FILE_DRIFT" "Managed file modified: $p"
        }
    }
    if ($legacy) {
        foreach ($p in $NewManaged) {
            if (Test-Path -LiteralPath (Join-Path $Repo ($p -replace '/', [IO.Path]::DirectorySeparatorChar))) {
                Fail "INSTALL_CONFLICT" "New destination exists without ownership metadata: $p"
            }
        }
    }
}

function Assert-No-Conflicts([string]$Repo, $Manifest) {
    foreach ($p in @("opencode.json", ".opencode/opencode.json", ".opencode/opencode.jsonc")) {
        if (Test-Path -LiteralPath (Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar))) {
            Fail "INSTALL_CONFLICT" "Foreign OpenCode config exists: $p"
        }
    }
    if ($null -eq $Manifest) {
        foreach ($p in $Managed) {
            if (Test-Path -LiteralPath (Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar))) {
                Fail "INSTALL_CONFLICT" "Destination exists without ownership metadata: $p"
            }
        }
    }
}

function Assert-Git-State([string]$Repo, $Manifest) {
    $dirty = @(Dirty-Paths $Repo)
    if ($dirty.Count -eq 0) { return }
    if ($null -eq $Manifest) { Fail "TARGET_WORKTREE_DIRTY" ($dirty -join ", ") }
    $allowed = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $Managed | ForEach-Object { [void]$allowed.Add($_) }
    [void]$allowed.Add($ManifestRel)
    $unexpected = @($dirty | Where-Object { -not $allowed.Contains((Rel $_)) })
    if ($unexpected.Count) { Fail "TARGET_WORKTREE_DIRTY" ($unexpected -join ", ") }
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
    $SafeGit | ForEach-Object { Add-Unique $commands $commandSeen $_ }
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

function Target-Nox([string]$Source, [string[]]$Commands) {
    $text = $Source.Replace("`r`n","`n")
    $marks = [regex]::Matches($text, "(?m)^---\s*$")
    if ($marks.Count -lt 2) { Fail "SOURCE_NOX_INVALID" "Missing frontmatter." }
    $front = $text.Substring($marks[0].Index + $marks[0].Length,
        $marks[1].Index - ($marks[0].Index + $marks[0].Length)).Trim("`n")
    $body = $text.Substring($marks[1].Index + $marks[1].Length)
    $front = [regex]::Replace($front,
        "(?m)^  - action: shell\r?\n    resource: [^\r\n]+\r?\n    effect: allow\r?\n?", "")
    if ($front -notmatch "(?ms)- action: shell\s+resource: [`"']\*[`"']\s+effect: deny") {
        Fail "SOURCE_NOX_INVALID" "Missing shell deny fallback."
    }
    $allow = [Text.StringBuilder]::new()
    foreach ($cmd in $Commands) {
        $escaped = $cmd.Replace("'","''")
        [void]$allow.Append("  - action: shell`n    resource: '$escaped'`n    effect: allow`n")
    }
    $generated = "---`n$($front.TrimEnd())`n$($allow.ToString())---$body"
    if ($generated -match "(?ms)- action: shell\s+resource: [^\r\n]+\s+effect: ask") {
        Fail "GENERATED_NOX_UNSAFE" "Shell ASK is forbidden."
    }
    if ($generated -match "(?ms)- action: shell\s+resource: [`"']\*[`"']\s+effect: allow") {
        Fail "GENERATED_NOX_UNSAFE" "Wildcard shell ALLOW is forbidden."
    }
    $generated
}

function Managed-Content($Detection) {
    $map = [ordered]@{}
    foreach ($p in $Managed) {
        $src = Join-Path $SourceRoot ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path $src)) { Fail "SOURCE_FILE_MISSING" $p }
        $text = [IO.File]::ReadAllText($src)
        if ($p -eq ".opencode/agents/nox.md") { $text = Target-Nox $text $Detection.ValidationCommands }
        $map[$p] = $text
    }
    $map
}

function Manifest-Text($Detection, $Content) {
    $files = foreach ($p in $Managed) { [ordered]@{ path=$p; sha256=Sha-Text ([string]$Content[$p]) } }
    $commit = (& git -C $SourceRoot rev-parse HEAD 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commit) { $commit = "unknown" }
    ([ordered]@{
        schema_version = 1
        installed_from_commit = $commit
        managed_files = @($files)
        detected_stacks = @($Detection.Stacks)
        package_manager = $Detection.PackageManager
        validation_commands = @($Detection.ValidationCommands)
    } | ConvertTo-Json -Depth 20) + "`n"
}

function Plan([string]$Repo, $Content, [string]$ManifestText) {
    $create = [System.Collections.Generic.List[string]]::new()
    $update = [System.Collections.Generic.List[string]]::new()
    foreach ($p in $Managed) {
        $full = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path $full)) { $create.Add($p) }
        elseif ((Sha-File $full) -ne (Sha-Text ([string]$Content[$p]))) { $update.Add($p) }
    }
    $mf = Join-Path $Repo ($ManifestRel -replace "/", [IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path $mf)) { $create.Add($ManifestRel) }
    elseif ((Sha-File $mf) -ne (Sha-Text $ManifestText)) { $update.Add($ManifestRel) }
    [pscustomobject]@{ Creates=@($create); Updates=@($update) }
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
    Write-Output "CONFLICTS:"; Write-Output "(none)"
    Write-Output "OPENCODE:"; Write-Output $Version
    Write-Output "MODEL_CHECK:"; Write-Output $ModelCheck
    Write-Output "STATUS:"; Write-Output $Status
}

function Validate-Install([string]$Repo) {
    $expected = @{
        "kael"=@("gpt-6-sol","high","primary")
        "sorin"=@("gpt-6-sol","xhigh","subagent")
        "veyra"=@("gpt-6-luna","max","subagent")
        "orin"=@("gpt-6-luna","max","subagent")
        "kovan"=@("gpt-6-luna","max","subagent")
        "nox"=@("gpt-6-luna","max","subagent")
        "vera"=@("gpt-6-luna","max","subagent")
        "maintenance"=@("gpt-6-sol","high","subagent")
    }
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
            if ($null -eq $lastMismatch) { return }
            if ($attempt -lt 5) { Start-Sleep -Milliseconds 250 }
        }
    } finally { Pop-Location }
    Fail "OPENCODE_VALIDATION_FAILED" $lastMismatch
}
try {
    if (-not (Has-Cmd "git")) { Fail "GIT_UNAVAILABLE" "git is required." }
    if (-not (Has-Cmd "opencode")) { Fail "OPENCODE_UNAVAILABLE" "opencode is required." }

    $Repo = Assert-Target $Target
    Assert-Install-Destinations $Repo
    $Version = (& opencode --version 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { Fail "OPENCODE_UNAVAILABLE" "opencode --version failed." }

    $ModelCheck = "DISCOVERY_UNAVAILABLE"
    $models = (& opencode models 2>$null | Out-String)
    if ($LASTEXITCODE -eq 0 -and $models) {
        if ($models -notmatch [regex]::Escape("openai/gpt-6-sol") -or
            $models -notmatch [regex]::Escape("openai/gpt-6-luna")) {
            Fail "MODEL_UNAVAILABLE" "Required GPT-6 Sol/Luna IDs are absent."
        }
        $ModelCheck = "GPT6_SOL_LUNA_IDS_AVAILABLE"
    }

    $manifest = Read-Manifest $Repo
    Assert-Managed $Repo $manifest
    Assert-No-Conflicts $Repo $manifest
    Assert-Git-State $Repo $manifest

    $detection = Detect-Project $Repo
    $content = Managed-Content $detection
    $manifestText = Manifest-Text $detection $content
    $plan = Plan $Repo $content $manifestText

    if ($DryRun) {
        Report $Repo $detection $plan "DRY_RUN_READY" $Version $ModelCheck
        exit 0
    }

    if (-not $plan.Creates.Count -and -not $plan.Updates.Count) {
        Validate-Install $Repo
        Report $Repo $detection $plan "NO_CHANGES" $Version $ModelCheck
        exit 0
    }

    foreach ($p in $Managed) {
        $full = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        Write-Text $full ([string]$content[$p])
    }
    Write-Text (Join-Path $Repo ($ManifestRel -replace "/", [IO.Path]::DirectorySeparatorChar)) $manifestText

    foreach ($p in $Managed) {
        $full = Join-Path $Repo ($p -replace "/", [IO.Path]::DirectorySeparatorChar)
        if ((Sha-File $full) -ne (Sha-Text ([string]$content[$p]))) { Fail "INSTALL_VERIFY_FAILED" $p }
    }

    Validate-Install $Repo
    Report $Repo $detection $plan "READY" $Version $ModelCheck
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
