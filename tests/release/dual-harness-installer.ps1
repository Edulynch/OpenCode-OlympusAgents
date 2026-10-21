[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('opencode\olympus-dual-installer-' + [guid]::NewGuid().ToString('N'))
$originalPath = $env:PATH
$originalVerifyProbe = $env:OLYMPUS_VERIFYONLY_PROBE
$originalVerifyCallLog = $env:OLYMPUS_VERIFYONLY_CALL_LOG
$utf8 = [Text.UTF8Encoding]::new($false)

function Check([string]$id, [bool]$condition) {
    if (-not $condition) { throw "$id FAIL" }
    Write-Output "$id PASS"
}

function New-Target([string]$name) {
    $target = Join-Path $run $name
    [IO.Directory]::CreateDirectory($target) | Out-Null
    & git -C $target init --quiet
    if ($LASTEXITCODE -ne 0) { throw "GIT_FIXTURE_INIT_FAIL: $name" }
    return $target
}

function Run-Installer([string]$target, [string[]]$arguments) {
    $args = @('-NoProfile', '-File', $installer, '-SourceRoot', $source, '-Target', $target) + $arguments
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 turns native stderr into a terminating error
        # under Stop; preserve expected installer failures as captured evidence.
        $ErrorActionPreference = 'Continue'
        $output = (& pwsh @args 2>&1 | Out-String)
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousErrorActionPreference }
    return [pscustomobject]@{ Text=$output; Code=$code }
}

function Install([string]$target, [string]$harness = '') {
    $arguments = if ($harness) { @('-Harness', $harness) } else { @() }
    return Run-Installer $target $arguments
}

function Verify([string]$target, [string]$harness) {
    return Run-Installer $target (@('-Harness', $harness, '-VerifyOnly'))
}

function Snapshot([string]$target) {
    $root = (Resolve-Path -LiteralPath $target).Path.TrimEnd([char[]]@('\','/'))
    $prefix = $root + [IO.Path]::DirectorySeparatorChar
    @(
        Get-ChildItem -LiteralPath $root -Force -Recurse | Sort-Object FullName | ForEach-Object {
            $relative = $_.FullName.Substring($prefix.Length)
            if ($_.PSIsContainer) { $relative + ':DIRECTORY' }
            else { $relative + ':SHA256:' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
        }
    ) -join "`n"
}

function Write-Fixture([string]$target, [string]$relative, [string]$contents) {
    $path = Join-Path $target ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
    [IO.Directory]::CreateDirectory((Split-Path -Parent $path)) | Out-Null
    [IO.File]::WriteAllText($path, $contents, $utf8)
}

function Has-GeneratedSurface([string]$target, [string]$harness) {
    $manifestPaths = @('.opencode/orchestrator-install.json', '.codex/orchestrator-install.json')
    $existingManifests = @($manifestPaths | Where-Object {
        Test-Path -LiteralPath (Join-Path $target ($_ -replace '/', [IO.Path]::DirectorySeparatorChar)) -PathType Leaf
    })
    if ($existingManifests.Count -ne 1) { return $false }
    $manifestPath = Join-Path $target ($existingManifests[0] -replace '/', [IO.Path]::DirectorySeparatorChar)
    try { $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json }
    catch { return $false }
    if ($harness -notin @($manifest.installed_harnesses | ForEach-Object { [string]$_ })) { return $false }

    # The install manifest is the generated/managed-file contract. Do not
    # recurse the adapter directory: legitimate project files (for example,
    # SpecKit commands) may live beside managed OpenCode outputs.
    $managedPaths = @($manifest.managed_files | ForEach-Object { ([string]$_.path).Replace('\','/') })
    $rootFile = if ($harness -eq 'opencode') { 'opencode.jsonc' } else { 'CODEX.md' }
    $surfacePaths = if ($harness -eq 'opencode') {
        @($managedPaths | Where-Object { $_.StartsWith('.opencode/', [StringComparison]::OrdinalIgnoreCase) -or $_ -ceq $rootFile })
    } else {
        @($managedPaths | Where-Object { $_.StartsWith('.codex/', [StringComparison]::OrdinalIgnoreCase) -or $_ -ceq $rootFile })
    }
    if ($surfacePaths.Count -eq 0 -or $rootFile -notin $surfacePaths) { return $false }
    foreach ($relative in $surfacePaths) {
        $installed = Join-Path $target ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) { return $false }
    }
    return $true
}

try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $mockBin = Join-Path $run 'mock-bin'
    [IO.Directory]::CreateDirectory($mockBin) | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'fixtures/opencode.ps1') -Destination (Join-Path $mockBin 'opencode.ps1')
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), "@echo off`r`npwsh -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n", [Text.Encoding]::ASCII)
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $env:PATH

    # A: the published one-line/default invocation remains OpenCode-only.
    $defaultTarget = New-Target 'default-opencode'
    $specKitPath = '.opencode/commands/speckit.plan.md'
    Write-Fixture $defaultTarget $specKitPath "user-owned SpecKit command`n"
    $specKitFullPath = Join-Path $defaultTarget ($specKitPath -replace '/', [IO.Path]::DirectorySeparatorChar)
    $specKitHashBefore = (Get-FileHash -LiteralPath $specKitFullPath -Algorithm SHA256).Hash
    $default = Install $defaultTarget
    $defaultManifest = Get-Content -LiteralPath (Join-Path $defaultTarget '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'A_DEFAULT_OPENCODE_ONLY' ($default.Code -eq 0 -and (Has-GeneratedSurface $defaultTarget 'opencode') -and
        -not (Test-Path -LiteralPath (Join-Path $defaultTarget '.codex')) -and
        $defaultManifest.scope -eq 'project' -and @($defaultManifest.installed_harnesses).Count -eq 1 -and
        $defaultManifest.installed_harnesses[0] -eq 'opencode')
    $defaultManagedPaths = @($defaultManifest.managed_files | ForEach-Object { ([string]$_.path).Replace('\','/') })
    $defaultVerify = Verify $defaultTarget 'opencode'
    Check 'A_FOREIGN_SPECKIT_FILE_REMAINS_UNMANAGED' ($specKitPath -notin $defaultManagedPaths -and
        (Test-Path -LiteralPath $specKitFullPath -PathType Leaf) -and
        (Get-FileHash -LiteralPath $specKitFullPath -Algorithm SHA256).Hash -eq $specKitHashBefore -and
        $defaultVerify.Code -eq 0)
    Check 'A_DEFAULT_VERIFY_PASS' ($defaultVerify.Code -eq 0)

    # B: explicit OpenCode is equivalent to the default.
    $opencodeTarget = New-Target 'explicit-opencode'
    $opencode = Install $opencodeTarget 'opencode'
    Check 'B_OPENCODE_INSTALL' ($opencode.Code -eq 0 -and (Has-GeneratedSurface $opencodeTarget 'opencode') -and
        -not (Test-Path -LiteralPath (Join-Path $opencodeTarget '.codex')) -and (Verify $opencodeTarget 'opencode').Code -eq 0)

    # C: Codex has no OpenCode surface and installs without an OpenCode executable.
    $codexTarget = New-Target 'codex-only'
    $codex = Install $codexTarget 'codex'
    $codexManifest = Get-Content -LiteralPath (Join-Path $codexTarget '.codex/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'C_CODEX_ONLY' ($codex.Code -eq 0 -and (Has-GeneratedSurface $codexTarget 'codex') -and
        -not (Test-Path -LiteralPath (Join-Path $codexTarget '.opencode')) -and
        -not (Test-Path -LiteralPath (Join-Path $codexTarget 'opencode.jsonc')) -and
        @($codexManifest.installed_harnesses).Count -eq 1 -and $codexManifest.installed_harnesses[0] -eq 'codex')
    Check 'C_CODEX_VERIFY_PASS' ((Verify $codexTarget 'codex').Code -eq 0)

    # D: all creates both rendered adapter surfaces under one ownership manifest.
    $allTarget = New-Target 'all'
    $all = Install $allTarget 'all'
    $allManifest = Get-Content -LiteralPath (Join-Path $allTarget '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'D_ALL_INSTALL' ($all.Code -eq 0 -and (Has-GeneratedSurface $allTarget 'opencode') -and
        (Has-GeneratedSurface $allTarget 'codex') -and @($allManifest.installed_harnesses).Count -eq 2 -and
        $allManifest.installed_harnesses[0] -eq 'opencode' -and $allManifest.installed_harnesses[1] -eq 'codex')
    Check 'D_ALL_VERIFY_PASS' ((Verify $allTarget 'all').Code -eq 0)

    # E/F: adding a harness preserves the existing managed harness; a Codex-only
    # manifest moves to the OpenCode-owned manifest path when OpenCode is added.
    $addCodex = New-Target 'opencode-then-codex'
    $firstOp = Install $addCodex 'opencode'
    $opHash = (Get-FileHash -LiteralPath (Join-Path $addCodex '.opencode/agents/kael.md') -Algorithm SHA256).Hash
    $secondCodex = Install $addCodex 'codex'
    $bothManifest = Get-Content -LiteralPath (Join-Path $addCodex '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'E_ADD_CODEX_TO_OPENCODE' ($firstOp.Code -eq 0 -and $secondCodex.Code -eq 0 -and
        (Has-GeneratedSurface $addCodex 'opencode') -and (Has-GeneratedSurface $addCodex 'codex') -and
        (Get-FileHash -LiteralPath (Join-Path $addCodex '.opencode/agents/kael.md') -Algorithm SHA256).Hash -eq $opHash -and
        (Verify $addCodex 'all').Code -eq 0 -and @($bothManifest.installed_harnesses).Count -eq 2)

    $addOpenCode = New-Target 'codex-then-opencode'
    $firstCx = Install $addOpenCode 'codex'
    $cxHash = (Get-FileHash -LiteralPath (Join-Path $addOpenCode '.codex/config.toml') -Algorithm SHA256).Hash
    $secondOp = Install $addOpenCode 'opencode'
    $migratedManifest = Get-Content -LiteralPath (Join-Path $addOpenCode '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'F_ADD_OPENCODE_TO_CODEX' ($firstCx.Code -eq 0 -and $secondOp.Code -eq 0 -and
        (Has-GeneratedSurface $addOpenCode 'opencode') -and (Has-GeneratedSurface $addOpenCode 'codex') -and
        (Get-FileHash -LiteralPath (Join-Path $addOpenCode '.codex/config.toml') -Algorithm SHA256).Hash -eq $cxHash -and
        -not (Test-Path -LiteralPath (Join-Path $addOpenCode '.codex/orchestrator-install.json')) -and
        (Verify $addOpenCode 'all').Code -eq 0 -and @($migratedManifest.installed_harnesses).Count -eq 2)

    # G/I: subset verification ignores the other installed harness, including its drift.
    $subset = New-Target 'subset-verify'
    $subsetInstall = Install $subset 'all'
    $subsetCleanCodexVerify = Verify $subset 'codex'
    $subsetCleanOpenVerify = Verify $subset 'opencode'
    Check 'G_SUBSET_VERIFY_ALL_CLEAN_PASS' ($subsetInstall.Code -eq 0 -and
        $subsetCleanCodexVerify.Code -eq 0 -and $subsetCleanOpenVerify.Code -eq 0)
    $subsetCodexPath = Join-Path $subset '.codex/config.toml'
    [IO.File]::AppendAllText($subsetCodexPath, "`n# drift`n", $utf8)
    $subsetCodexVerify = Verify $subset 'codex'
    $subsetOpenVerify = Verify $subset 'opencode'
    Check 'G_SUBSET_VERIFY_ISOLATES_DRIFT' ($subsetCodexVerify.Code -ne 0 -and
        $subsetCodexVerify.Text -match 'OLYMPUS_VERIFY: .* FAIL' -and $subsetOpenVerify.Code -eq 0)
    $subsetOpPath = Join-Path $subset '.opencode/agents/kael.md'
    [IO.File]::AppendAllText($subsetOpPath, "`n# drift`n", $utf8)
    Check 'I_CROSS_HARNESS_ISOLATION' ((Verify $subset 'codex').Code -ne 0 -and
        (Verify $subset 'opencode').Code -ne 0)
    $isolationCodex = New-Target 'opencode-drift-codex-pass'
    [void](Install $isolationCodex 'all')
    [IO.File]::AppendAllText((Join-Path $isolationCodex '.opencode/agents/kael.md'), "`n# drift`n", $utf8)
    Check 'I_CODEX_VERIFY_IGNORES_OPENCODE_DRIFT' ((Verify $isolationCodex 'codex').Code -eq 0)
    $isolationOpen = New-Target 'codex-drift-opencode-pass'
    [void](Install $isolationOpen 'all')
    [IO.File]::AppendAllText((Join-Path $isolationOpen '.codex/config.toml'), "`n# drift`n", $utf8)
    Check 'I_OPENCODE_VERIFY_IGNORES_CODEX_DRIFT' ((Verify $isolationOpen 'opencode').Code -eq 0)

    # H: each requested managed set detects its own hash drift.
    $driftCodex = Verify $subset 'codex'
    $driftOpen = Verify $subset 'opencode'
    Check 'H_WRONG_HARNESS_DRIFT_FAILS' ($driftCodex.Code -ne 0 -and $driftOpen.Code -ne 0)

    # J: user-owned differing Codex/OpenCode files are never replaced.
    foreach ($fixture in @(@('codex-config', '.codex/config.toml'), @('codex-root', 'CODEX.md'),
        @('opencode-config', 'opencode.jsonc'), @('opencode-agent', '.opencode/agents/kael.md'))) {
        $conflictTarget = New-Target ('conflict-' + $fixture[0])
        Write-Fixture $conflictTarget $fixture[1] "user-owned content`n"
        $path = Join-Path $conflictTarget ($fixture[1] -replace '/', [IO.Path]::DirectorySeparatorChar)
        $before = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        $harness = if ($fixture[0] -like 'codex-*') { 'codex' } else { 'opencode' }
        $conflict = Install $conflictTarget $harness
        Check ('J_USER_OWNED_CONFLICT_' + $fixture[0].ToUpperInvariant()) ($conflict.Code -ne 0 -and
            $conflict.Text -match 'INSTALL_CONFLICT' -and (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $before -and
            -not (Test-Path -LiteralPath (Join-Path $conflictTarget '.opencode/orchestrator-install.json')) -and
            -not (Test-Path -LiteralPath (Join-Path $conflictTarget '.codex/orchestrator-install.json')))
    }
    $adoptTarget = New-Target 'codex-adopt-exact-generated-files'
    [IO.Directory]::CreateDirectory((Join-Path $adoptTarget '.codex')) | Out-Null
    Copy-Item -LiteralPath (Join-Path $source '.codex/config.toml') -Destination (Join-Path $adoptTarget '.codex/config.toml') -Force
    Copy-Item -LiteralPath (Join-Path $source 'CODEX.md') -Destination (Join-Path $adoptTarget 'CODEX.md') -Force
    $adopt = Install $adoptTarget 'codex'
    Check 'J_CODEX_EXACT_GENERATED_OUTPUT_ADOPTED' ($adopt.Code -eq 0 -and
        (Verify $adoptTarget 'codex').Code -eq 0)

    # K: beta.4-style OpenCode metadata remains recognized, and Codex can be added.
    $legacy = New-Target 'legacy-beta4-opencode'
    $legacyInstall = Install $legacy 'opencode'
    $legacyManifestPath = Join-Path $legacy '.opencode/orchestrator-install.json'
    $legacyManifest = Get-Content -LiteralPath $legacyManifestPath -Raw | ConvertFrom-Json
    [void]$legacyManifest.PSObject.Properties.Remove('installed_harnesses')
    [IO.File]::WriteAllText($legacyManifestPath, (($legacyManifest | ConvertTo-Json -Depth 30) + "`n"), $utf8)
    $legacyUpgrade = Install $legacy 'opencode'
    $legacyAdd = Install $legacy 'codex'
    $legacyUpgradedManifest = Get-Content -LiteralPath $legacyManifestPath -Raw | ConvertFrom-Json
    Check 'K_LEGACY_BETA4_UPGRADE_AND_ADD_CODEX' ($legacyInstall.Code -eq 0 -and $legacyUpgrade.Code -eq 0 -and
        $legacyAdd.Code -eq 0 -and (Has-GeneratedSurface $legacy 'opencode') -and (Has-GeneratedSurface $legacy 'codex') -and
        @($legacyUpgradedManifest.installed_harnesses).Count -eq 2 -and (Verify $legacy 'all').Code -eq 0)

    # L: every VerifyOnly mode is strict managed-file verification. A runtime
    # discovery call would create .serena in this probe, so none may be launched.
    $probeLog = Join-Path $run 'verify-only-external-runtime-calls.log'
    $env:OLYMPUS_VERIFYONLY_PROBE = '1'
    $env:OLYMPUS_VERIFYONLY_CALL_LOG = $probeLog
    foreach ($entry in @(@($defaultTarget, 'opencode'), @($codexTarget, 'codex'), @($allTarget, 'all'))) {
        $before = Snapshot $entry[0]
        $result = Verify $entry[0] $entry[1]
        $after = Snapshot $entry[0]
        Check ('L_VERIFYONLY_READ_ONLY_' + $entry[1].ToUpperInvariant()) ($result.Code -eq 0 -and $after -ceq $before -and
            -not (Test-Path -LiteralPath (Join-Path $entry[0] '.serena')))
    }
    Check 'L_VERIFYONLY_NEVER_LAUNCHES_MUTABLE_RUNTIME_DISCOVERY' (-not (Test-Path -LiteralPath $probeLog))
    Remove-Item Env:OLYMPUS_VERIFYONLY_PROBE -ErrorAction SilentlyContinue
    Remove-Item Env:OLYMPUS_VERIFYONLY_CALL_LOG -ErrorAction SilentlyContinue

    $installerText = [IO.File]::ReadAllText($installer)
    Check 'M_HARNESS_API_AND_DEFAULT' ($installerText -match "\[string\]\`$Harness\s*=\s*'opencode'" -and
        $installerText -match "\[string\]\`$Scope\s*=\s*'project'" -and
        $installerText -match "\[ValidateSet\('project', 'global'\)\]" -and
        $installerText -match "\[ValidateSet\('opencode', 'codex', 'all'\)\]")
    $tag = 'v9.9.9'
    $docsUrl = "https://github.com/Edulynch/OpenCode-OlympusAgents/blob/$tag/docs/INSTALLATION.md"
    $verifyDocsUrl = "$docsUrl#release-selection-identity-and-executable-source"
    $releaseBody = "## Installation`n`nFast Install and Fast Uninstall commands, including parameter and harness details, are documented in $docsUrl.`n`n## Verify installation`n`nRead-only VerifyOnly harness checks and safety are documented in $verifyDocsUrl.`n"
    $releaseGate = Join-Path $source 'tests/release/github-release-notes.ps1'
    $releasePass = (& pwsh -NoProfile -File $releaseGate -Version $tag -ReleaseBody $releaseBody 2>&1 | Out-String)
    Check 'M_RELEASE_CONTRACT_FUTURE_DUAL_COMMANDS' ($LASTEXITCODE -eq 0 -and $releasePass -match 'RELEASE_NOTES_CONTRACT: v9\.9\.9 PASS')
    $releaseMissing = (& pwsh -NoProfile -File $releaseGate -Version $tag -ReleaseBody ($releaseBody.Replace($verifyDocsUrl, '')) 2>&1 | Out-String)
    Check 'M_RELEASE_CONTRACT_REJECTS_MISSING_VERIFY_SAFETY_GUIDE' ($LASTEXITCODE -ne 0 -and $releaseMissing -match 'RELEASE_NOTES_HARNESS_VERIFY_MISSING')
    Write-Output 'DUAL-HARNESS INSTALLER QUALIFICATION: PASS (isolated local installs; no interactive harness session)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'DUAL-HARNESS INSTALLER QUALIFICATION: FAIL'
    exit 1
} finally {
    $env:PATH = $originalPath
    if ($null -eq $originalVerifyProbe) { Remove-Item Env:OLYMPUS_VERIFYONLY_PROBE -ErrorAction SilentlyContinue }
    else { $env:OLYMPUS_VERIFYONLY_PROBE = $originalVerifyProbe }
    if ($null -eq $originalVerifyCallLog) { Remove-Item Env:OLYMPUS_VERIFYONLY_CALL_LOG -ErrorAction SilentlyContinue }
    else { $env:OLYMPUS_VERIFYONLY_CALL_LOG = $originalVerifyCallLog }
    if ($run -and (Test-Path -LiteralPath $run)) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop; break }
            catch {
                if ($attempt -eq 10) { Write-Output "CLEANUP_DEFERRED: $run"; break }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}
