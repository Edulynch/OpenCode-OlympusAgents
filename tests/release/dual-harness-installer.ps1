[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'scripts/bootstrap.ps1'
$candidateVersion = ([regex]::Match([IO.File]::ReadAllText((Join-Path $source 'install.ps1')),
    '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''')).Groups[1].Value
. (Join-Path $PSScriptRoot '../installer-test-environment.ps1')
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('opencode\olympus-dual-installer-' + [guid]::NewGuid().ToString('N'))
$originalPath = $env:PATH
$originalVerifyProbe = $env:OLYMPUS_VERIFYONLY_PROBE
$originalVerifyCallLog = $env:OLYMPUS_VERIFYONLY_CALL_LOG
$utf8 = [Text.UTF8Encoding]::new($false)
$isolatedEnvironment = $null

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
    $args = @('-NoProfile', '-File', $installer, '-SourceVersion', $candidateVersion, '-Target', $target) + $arguments
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

function Has-GeneratedSurface([string]$target) {
    $manifestPath = Join-Path $target '.opencode/orchestrator-install.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or
        (Test-Path -LiteralPath (Join-Path $target '.codex/orchestrator-install.json'))) { return $false }
    try { $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json }
    catch { return $false }
    $expected = @(
        '.opencode/agents/atlas.md', '.opencode/agents/helios.md',
        '.opencode/agents/kael.md', '.opencode/agents/kovan.md', '.opencode/agents/nox.md',
        '.opencode/agents/talos.md', '.opencode/agents/thales.md',
        '.opencode/agents/vera.md', '.opencode/agents/veyra.md',
        '.opencode/plugins/olympus-activity/activity.ts', '.opencode/plugins/olympus-activity/tui.tsx',
        '.opencode/scripts/worktree-setup.ps1', 'opencode.jsonc'
    ) | Sort-Object
    $managedPaths = @($manifest.managed_files | ForEach-Object { ([string]$_.path).Replace('\','/') })
    if ($manifest.schema_version -ne 1 -or $manifest.scope -cne 'project' -or
        @($manifest.installed_harnesses).Count -ne 1 -or $manifest.installed_harnesses[0] -cne 'opencode' -or
        [string]::IsNullOrWhiteSpace([string]$manifest.installed_version) -or
        [string]::IsNullOrWhiteSpace([string]$manifest.installed_from_commit) -or
        $managedPaths.Count -ne 13 -or
        [string]::Join("`n", @($managedPaths | Sort-Object)) -cne [string]::Join("`n", $expected)) { return $false }
    foreach ($entry in @($manifest.managed_files)) {
        $relative = ([string]$entry.path).Replace('\','/')
        $installed = Join-Path $target ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $installed -PathType Leaf) -or
            [string]$entry.sha256 -notmatch '^(?i:[0-9a-f]{64})$' -or
            (Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash -ine [string]$entry.sha256) { return $false }
    }
    return $true
}

try {
    $isolatedEnvironment = Enter-OlympusInstallerTestEnvironment $run
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $mockBin = Join-Path $run 'mock-bin'
    [IO.Directory]::CreateDirectory($mockBin) | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'fixtures/opencode.ps1') -Destination (Join-Path $mockBin 'opencode.ps1')
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), "@echo off`r`npwsh -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n", [Text.Encoding]::ASCII)
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $env:PATH

    # A: the current default owns exactly the 13-resource project inventory.
    $defaultTarget = New-Target 'default-opencode'
    $specKitPath = '.opencode/commands/speckit.plan.md'
    Write-Fixture $defaultTarget $specKitPath "user-owned SpecKit command`n"
    $specKitFullPath = Join-Path $defaultTarget ($specKitPath -replace '/', [IO.Path]::DirectorySeparatorChar)
    $specKitHashBefore = (Get-FileHash -LiteralPath $specKitFullPath -Algorithm SHA256).Hash
    $default = Install $defaultTarget
    $defaultManifest = Get-Content -LiteralPath (Join-Path $defaultTarget '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'A_DEFAULT_OPENCODE_ONLY' ($default.Code -eq 0 -and (Has-GeneratedSurface $defaultTarget) -and
        -not (Test-Path -LiteralPath (Join-Path $defaultTarget '.codex')) -and
        $defaultManifest.scope -eq 'project' -and @($defaultManifest.installed_harnesses).Count -eq 1 -and
        $defaultManifest.installed_harnesses[0] -eq 'opencode' -and
        $defaultManifest.managed_files.Count -eq 13 -and
        -not [string]::IsNullOrWhiteSpace([string]$defaultManifest.installed_from_commit))
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
    Check 'B_OPENCODE_INSTALL' ($opencode.Code -eq 0 -and (Has-GeneratedSurface $opencodeTarget) -and
        -not (Test-Path -LiteralPath (Join-Path $opencodeTarget '.codex')) -and (Verify $opencodeTarget 'opencode').Code -eq 0)

    foreach ($selector in @('codex','all')) {
        $unsupported = New-Target ('unsupported-' + $selector)
        $before = Snapshot $unsupported
        $result = Install $unsupported $selector
        Check ('C_UNSUPPORTED_SELECTOR_' + $selector.ToUpperInvariant()) ($result.Code -ne 0 -and
            (Snapshot $unsupported) -ceq $before -and
            -not (Test-Path -LiteralPath (Join-Path $unsupported '.opencode/orchestrator-install.json')))
    }

    $codexManifestTarget = New-Target 'codex-manifest-refused'
    Write-Fixture $codexManifestTarget '.codex/orchestrator-install.json' '{"scope":"project","installed_harnesses":["codex"]}'
    $codexManifestBefore = Snapshot $codexManifestTarget
    $codexManifestInstall = Install $codexManifestTarget
    Check 'D_CODEX_MANIFEST_REFUSED_WITHOUT_WRITES' ($codexManifestInstall.Code -ne 0 -and
        $codexManifestInstall.Text -match 'INSTALL_MANIFEST_INCOMPATIBLE' -and
        (Snapshot $codexManifestTarget) -ceq $codexManifestBefore)

    # Current manifests require explicit one-harness metadata; no old shape is upgraded.
    $missingMetadataTarget = New-Target 'missing-current-metadata-refused'
    [void](Install $missingMetadataTarget 'opencode')
    $missingMetadataPath = Join-Path $missingMetadataTarget '.opencode/orchestrator-install.json'
    $missingMetadata = Get-Content -LiteralPath $missingMetadataPath -Raw | ConvertFrom-Json
    [void]$missingMetadata.PSObject.Properties.Remove('installed_harnesses')
    [IO.File]::WriteAllText($missingMetadataPath, (($missingMetadata | ConvertTo-Json -Depth 30) + "`n"), $utf8)
    $missingMetadataBefore = Snapshot $missingMetadataTarget
    $missingMetadataUpdate = Install $missingMetadataTarget 'opencode'
    Check 'E_MISSING_CURRENT_METADATA_REFUSED_READ_ONLY' ($missingMetadataUpdate.Code -ne 0 -and
        $missingMetadataUpdate.Text -match 'INSTALL_MANIFEST_INCOMPATIBLE' -and
        (Snapshot $missingMetadataTarget) -ceq $missingMetadataBefore)

    $dualMetadataTarget = New-Target 'dual-current-metadata-refused'
    [void](Install $dualMetadataTarget 'opencode')
    $dualMetadataPath = Join-Path $dualMetadataTarget '.opencode/orchestrator-install.json'
    $dualMetadata = Get-Content -LiteralPath $dualMetadataPath -Raw | ConvertFrom-Json
    $dualMetadata.installed_harnesses = @('opencode','codex')
    [IO.File]::WriteAllText($dualMetadataPath, (($dualMetadata | ConvertTo-Json -Depth 30) + "`n"), $utf8)
    $dualMetadataBefore = Snapshot $dualMetadataTarget
    $dualMetadataUpdate = Install $dualMetadataTarget 'opencode'
    Check 'F_DUAL_HARNESS_METADATA_REFUSED_READ_ONLY' ($dualMetadataUpdate.Code -ne 0 -and
        $dualMetadataUpdate.Text -match 'INSTALL_MANIFEST_INCOMPATIBLE' -and
        (Snapshot $dualMetadataTarget) -ceq $dualMetadataBefore)

    $dualLocationTarget = New-Target 'dual-manifest-locations-refused'
    [void](Install $dualLocationTarget 'opencode')
    Write-Fixture $dualLocationTarget '.codex/orchestrator-install.json' '{"scope":"project","installed_harnesses":["codex"]}'
    $dualLocationBefore = Snapshot $dualLocationTarget
    $dualLocationUpdate = Install $dualLocationTarget 'opencode'
    Check 'G_DUAL_MANIFEST_LOCATIONS_REFUSED_READ_ONLY' ($dualLocationUpdate.Code -ne 0 -and
        $dualLocationUpdate.Text -match 'INSTALL_MANIFEST_INCOMPATIBLE' -and
        (Snapshot $dualLocationTarget) -ceq $dualLocationBefore)

    # User-owned current OpenCode destinations are never adopted or replaced.
    foreach ($fixture in @(@('opencode-config', 'opencode.jsonc'), @('opencode-agent', '.opencode/agents/kael.md'))) {
        $conflictTarget = New-Target ('user-conflict-' + $fixture[0])
        Write-Fixture $conflictTarget $fixture[1] "user-owned content`n"
        $path = Join-Path $conflictTarget ($fixture[1] -replace '/', [IO.Path]::DirectorySeparatorChar)
        $before = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        $conflict = Install $conflictTarget 'opencode'
        Check ('H_USER_OWNED_CONFLICT_' + $fixture[0].ToUpperInvariant()) ($conflict.Code -ne 0 -and
            $conflict.Text -match 'INSTALL_CONFLICT' -and (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $before -and
            -not (Test-Path -LiteralPath (Join-Path $conflictTarget '.opencode/orchestrator-install.json')))
    }

    # VerifyOnly is strict and read-only; runtime discovery would create .serena.
    $probeLog = Join-Path $run 'verify-only-external-runtime-calls.log'
    $env:OLYMPUS_VERIFYONLY_PROBE = '1'
    $env:OLYMPUS_VERIFYONLY_CALL_LOG = $probeLog
    $beforeVerify = Snapshot $defaultTarget
    $result = Verify $defaultTarget 'opencode'
    Check 'I_VERIFYONLY_READ_ONLY_OPENCODE' ($result.Code -eq 0 -and
        (Snapshot $defaultTarget) -ceq $beforeVerify -and
        -not (Test-Path -LiteralPath (Join-Path $defaultTarget '.serena')))
    foreach ($selector in @('codex','all')) {
        $beforeVerify = Snapshot $defaultTarget
        $result = Verify $defaultTarget $selector
        Check ('I_VERIFYONLY_REJECTS_' + $selector.ToUpperInvariant()) ($result.Code -ne 0 -and
            (Snapshot $defaultTarget) -ceq $beforeVerify)
    }
    Check 'L_VERIFYONLY_NEVER_LAUNCHES_MUTABLE_RUNTIME_DISCOVERY' (-not (Test-Path -LiteralPath $probeLog))
    Remove-Item Env:OLYMPUS_VERIFYONLY_PROBE -ErrorAction SilentlyContinue
    Remove-Item Env:OLYMPUS_VERIFYONLY_CALL_LOG -ErrorAction SilentlyContinue

    $installerText = [IO.File]::ReadAllText($installer)
    Check 'M_INTERNAL_HARNESS_API_AND_DEFAULT' ($installerText -match "\[string\]\`$Harness\s*=\s*'opencode'" -and
        $installerText -match "\[ValidateSet\('opencode'\)\]")
    $tag = 'v9.9.9'
    $docsUrl = "https://github.com/Edulynch/OpenCode-OlympusAgents/blob/$tag/docs/INSTALLATION.md"
    $verifyDocsUrl = "$docsUrl#release-selection-identity-and-executable-source"
    $releaseBody = "## Installation`n`nFast Install and Fast Uninstall commands, including parameter and harness details, are documented in $docsUrl.`n`n## Verify installation`n`nRead-only VerifyOnly harness checks and safety are documented in $verifyDocsUrl.`n"
    $releaseGate = Join-Path $source 'tests/release/github-release-notes.ps1'
    $releasePass = (& pwsh -NoProfile -File $releaseGate -Version $tag -ReleaseBody $releaseBody 2>&1 | Out-String)
    Check 'M_RELEASE_CONTRACT_CURRENT_OPENCode_COMMANDS' ($LASTEXITCODE -eq 0 -and $releasePass -match 'RELEASE_NOTES_CONTRACT: v9\.9\.9 PASS')
    $releaseMissing = (& pwsh -NoProfile -File $releaseGate -Version $tag -ReleaseBody ($releaseBody.Replace($verifyDocsUrl, '')) 2>&1 | Out-String)
    Check 'M_RELEASE_CONTRACT_REJECTS_MISSING_VERIFY_SAFETY_GUIDE' ($LASTEXITCODE -ne 0 -and $releaseMissing -match 'RELEASE_NOTES_HARNESS_VERIFY_MISSING')
    Write-Output 'OPENCODE-ONLY PROJECT INSTALLER QUALIFICATION: PASS (isolated local installs; no interactive harness session)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'OPENCODE-ONLY PROJECT INSTALLER QUALIFICATION: FAIL'
    exit 1
} finally {
    if ($null -ne $isolatedEnvironment) { Exit-OlympusInstallerTestEnvironment $isolatedEnvironment }
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
