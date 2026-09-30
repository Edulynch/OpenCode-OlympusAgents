[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('opencode\olympus-global-installer-' + [guid]::NewGuid().ToString('N'))
$originalPath = $env:PATH
$originalOpenCodeRoot = $env:OPENCODE_CONFIG_DIR
$originalCodexHome = $env:CODEX_HOME
$originalFixtureOpenCodeRoot = $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT
$utf8 = [Text.UTF8Encoding]::new($false)

function Check([string]$Id, [bool]$Condition, [string]$Evidence = '') {
    if (-not $Condition) {
        if ($Evidence) { throw "$Id FAIL`n$Evidence" }
        throw "$Id FAIL"
    }
    Write-Output "$Id PASS"
}

function New-Target([string]$Name) {
    $target = Join-Path $run $Name
    [IO.Directory]::CreateDirectory($target) | Out-Null
    & git -C $target init --quiet
    if ($LASTEXITCODE -ne 0) { throw "GIT_FIXTURE_INIT_FAIL: $Name" }
    return $target
}

function Run-Installer([string]$Target, [string[]]$Arguments) {
    $args = @('-NoProfile', '-File', $installer, '-SourceRoot', $source, '-Target', $Target) + $Arguments
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

function Global-Install([string]$Target, [string]$Harness = 'all') {
    Run-Installer $Target @('-Scope','global','-Harness',$Harness)
}

function Global-Verify([string]$Target, [string]$Harness = 'all') {
    Run-Installer $Target @('-Scope','global','-Harness',$Harness,'-VerifyOnly')
}

function Snapshot([string]$Root) {
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) { return '<MISSING_ROOT>' }
    $base = (Resolve-Path -LiteralPath $Root).Path.TrimEnd([char[]]@('\','/'))
    $prefix = $base + [IO.Path]::DirectorySeparatorChar
    @(
        Get-ChildItem -LiteralPath $base -Force -Recurse | Sort-Object FullName | ForEach-Object {
            $relative = $_.FullName.Substring($prefix.Length)
            if ($_.PSIsContainer) { $relative + ':DIRECTORY' }
            else { $relative + ':SHA256:' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
        }
    ) -join "`n"
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: global install qualification is Windows-only.' }
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $openCodeRoot = Join-Path $run 'OpenCode Global Config'
    $codexHome = Join-Path $run 'Codex Global Home'
    [IO.Directory]::CreateDirectory($openCodeRoot) | Out-Null
    [IO.Directory]::CreateDirectory($codexHome) | Out-Null
    $project = New-Target 'migration-project'
    $mockBin = Join-Path $run 'mock-bin'
    [IO.Directory]::CreateDirectory($mockBin) | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../release/fixtures/opencode.ps1') -Destination (Join-Path $mockBin 'opencode.ps1')
    $mockCommand = "@echo off`r`npwsh -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), $mockCommand, [Text.Encoding]::ASCII)
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $env:PATH
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeRoot
    Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue
    $env:CODEX_HOME = $codexHome

    $openUserConfig = Join-Path $openCodeRoot 'opencode.json'
    $codexUserConfig = Join-Path $codexHome 'config.toml'
    [IO.File]::WriteAllText($openUserConfig, '{"user_owned":true}' + "`n", $utf8)
    [IO.File]::WriteAllText($codexUserConfig, "model = 'user-choice'`n", $utf8)
    $openUserHash = (Get-FileHash -LiteralPath $openUserConfig -Algorithm SHA256).Hash
    $codexUserHash = (Get-FileHash -LiteralPath $codexUserConfig -Algorithm SHA256).Hash

    # The existing project-local default stays project-scoped and records scope.
    $localInstall = Run-Installer $project @('-Harness','all')
    $localManifestPath = Join-Path $project '.opencode/orchestrator-install.json'
    $localManifest = Get-Content -LiteralPath $localManifestPath -Raw | ConvertFrom-Json
    Check 'PROJECT_SCOPE_ALL_INSTALL' ($localInstall.Code -eq 0 -and $localManifest.scope -eq 'project' -and
        $localManifest.installed_version -eq 'v0.3.0-beta.5' -and $localManifest.installed_harnesses.Count -eq 2 -and
        $localManifest.installed_harnesses[0] -eq 'opencode' -and $localManifest.installed_harnesses[1] -eq 'codex')
    $projectBeforeVerify = Snapshot $project
    $projectVerify = Run-Installer $project @('-Harness','all','-VerifyOnly')
    Check 'PROJECT_VERIFYONLY_ALL_UNAFFECTED' ($projectVerify.Code -eq 0 -and (Snapshot $project) -ceq $projectBeforeVerify)

    $projectBeforeMigration = Snapshot $project
    $globalInstall = Global-Install $project 'all'
    Check 'GLOBAL_OPENCODE_AND_CODEX_INSTALL' ($globalInstall.Code -eq 0 -and
        $globalInstall.Text -match 'OLYMPUS_GLOBAL_INSTALL: OPENCODE .* READY' -and
        $globalInstall.Text -match 'OLYMPUS_GLOBAL_INSTALL: CODEX .* READY') ("exit=$($globalInstall.Code)`n$($globalInstall.Text)")
    Check 'GLOBAL_BOTH_PROJECT_OVERRIDES_RETAINED' ($globalInstall.Text -match 'GLOBAL_INSTALLED PROJECT_LOCAL_REMAINS_AS_OVERRIDE' -and
        $globalInstall.Text -match 'PROJECT_LOCAL_OVERRIDE: opencode' -and $globalInstall.Text -match 'PROJECT_LOCAL_OVERRIDE: codex' -and
        (Snapshot $project) -ceq $projectBeforeMigration) ("exit=$($globalInstall.Code)`n$($globalInstall.Text)`nPROJECT_SNAPSHOT_UNCHANGED=$((Snapshot $project) -ceq $projectBeforeMigration)")
    Check 'GLOBAL_OPENCODE_RESOLVES_CURRENT_CLI_CONFIG_PATH' ((Test-Path (Join-Path $openCodeRoot 'agents/kael.md')) -and
        (Test-Path (Join-Path $openCodeRoot 'commands/maintain.md')) -and
        (Test-Path (Join-Path $openCodeRoot 'plugins/olympus-activity/activity.ts')))
    Check 'GLOBAL_CODEX_PROFILE_AND_AGENTS' ((Test-Path (Join-Path $codexHome 'agents/veyra.toml')) -and
        (Test-Path (Join-Path $codexHome 'olympus.config.toml')) -and
        (Test-Path (Join-Path $codexHome 'AGENTS.md')) -and
        (Get-Content (Join-Path $codexHome 'olympus.config.toml') -Raw).Contains('model = "gpt-6.1-sol"'))
    Check 'GLOBAL_USER_CONFIG_PROTECTED' ((Get-FileHash -LiteralPath $openUserConfig -Algorithm SHA256).Hash -eq $openUserHash -and
        (Get-FileHash -LiteralPath $codexUserConfig -Algorithm SHA256).Hash -eq $codexUserHash)

    $conflictCodexHome = Join-Path $run 'Codex User Instructions Conflict'
    [IO.Directory]::CreateDirectory($conflictCodexHome) | Out-Null
    $conflictInstructions = Join-Path $conflictCodexHome 'AGENTS.md'
    [IO.File]::WriteAllText($conflictInstructions, "user global instructions`n", $utf8)
    $conflictInstructionsHash = (Get-FileHash -LiteralPath $conflictInstructions -Algorithm SHA256).Hash
    $env:CODEX_HOME = $conflictCodexHome
    $codexConflict = Run-Installer $project @('-Scope','global','-Harness','codex')
    Check 'GLOBAL_USER_OWNED_CODEX_INSTRUCTIONS_CONFLICT' ($codexConflict.Code -ne 0 -and
        $codexConflict.Text -match 'GLOBAL_INSTALL_CONFLICT' -and
        (Get-FileHash -LiteralPath $conflictInstructions -Algorithm SHA256).Hash -eq $conflictInstructionsHash -and
        -not (Test-Path (Join-Path $conflictCodexHome 'agents/veyra.toml')))
    $overrideCodexHome = Join-Path $run 'Codex Global Override Instructions'
    [IO.Directory]::CreateDirectory($overrideCodexHome) | Out-Null
    [IO.File]::WriteAllText((Join-Path $overrideCodexHome 'AGENTS.override.md'), "user override instructions`n", $utf8)
    $env:CODEX_HOME = $overrideCodexHome
    $codexOverrideConflict = Run-Installer $project @('-Scope','global','-Harness','codex')
    Check 'GLOBAL_CODEX_OVERRIDE_PRECEDENCE_CONFLICT' ($codexOverrideConflict.Code -ne 0 -and
        $codexOverrideConflict.Text -match 'GLOBAL_INSTALL_CONFLICT' -and
        -not (Test-Path (Join-Path $overrideCodexHome 'AGENTS.md')) -and
        -not (Test-Path (Join-Path $overrideCodexHome 'agents/veyra.toml')))
    $env:CODEX_HOME = $codexHome

    # Qualify the successful per-harness global selectors independently of -all.
    $openCodeOnlyRoot = Join-Path $run 'OpenCode Only Global Config'
    [IO.Directory]::CreateDirectory($openCodeOnlyRoot) | Out-Null
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeOnlyRoot
    $openCodeOnly = Run-Installer $project @('-Scope','global','-Harness','opencode')
    $openCodeOnlyManifest = Get-Content (Join-Path $openCodeOnlyRoot 'olympus/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'GLOBAL_OPENCODE_ONLY_SELECTOR' ($openCodeOnly.Code -eq 0 -and $openCodeOnlyManifest.scope -eq 'global' -and
        $openCodeOnlyManifest.installed_harnesses.Count -eq 1 -and $openCodeOnlyManifest.installed_harnesses[0] -eq 'opencode' -and
        $openCodeOnlyManifest.managed_files.Count -eq 15)
    $codexOnlyHome = Join-Path $run 'Codex Only Global Home'
    [IO.Directory]::CreateDirectory($codexOnlyHome) | Out-Null
    $env:CODEX_HOME = $codexOnlyHome
    $codexOnly = Run-Installer $project @('-Scope','global','-Harness','codex')
    $codexOnlyManifest = Get-Content (Join-Path $codexOnlyHome 'olympus/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'GLOBAL_CODEX_ONLY_SELECTOR' ($codexOnly.Code -eq 0 -and $codexOnlyManifest.scope -eq 'global' -and
        $codexOnlyManifest.installed_harnesses.Count -eq 1 -and $codexOnlyManifest.installed_harnesses[0] -eq 'codex' -and
        $codexOnlyManifest.managed_files.Count -eq 12)
    $env:CODEX_HOME = $codexHome
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeRoot

    $openManifestPath = Join-Path $openCodeRoot 'olympus/orchestrator-install.json'
    $codexManifestPath = Join-Path $codexHome 'olympus/orchestrator-install.json'
    $openManifestText = [IO.File]::ReadAllText($openManifestPath)
    $codexManifestText = [IO.File]::ReadAllText($codexManifestPath)
    $openManifest = $openManifestText | ConvertFrom-Json
    $codexManifest = $codexManifestText | ConvertFrom-Json
    Check 'GLOBAL_MANIFEST_SCOPE_AND_RESOURCES' ($openManifest.scope -eq 'global' -and $codexManifest.scope -eq 'global' -and
        $openManifest.installed_harnesses[0] -eq 'opencode' -and $codexManifest.installed_harnesses[0] -eq 'codex' -and
        $openManifest.managed_files.Count -eq 15 -and $codexManifest.managed_files.Count -eq 12)

    $openBeforeVerify = Snapshot $openCodeRoot
    $codexBeforeVerify = Snapshot $codexHome
    $verifyAll = Global-Verify $project 'all'
    Check 'GLOBAL_VERIFYONLY_ALL_READONLY' ($verifyAll.Code -eq 0 -and $verifyAll.Text -match 'OLYMPUS_GLOBAL_VERIFY: opencode' -and
        $verifyAll.Text -match 'OLYMPUS_GLOBAL_VERIFY: codex' -and (Snapshot $openCodeRoot) -ceq $openBeforeVerify -and
        (Snapshot $codexHome) -ceq $codexBeforeVerify)

    # Global update remains hash-owned and preserves both local overrides and user config.
    $openManifest.installed_version = 'v0.3.0-beta.4'
    [IO.File]::WriteAllText($openManifestPath, (($openManifest | ConvertTo-Json -Depth 20) + "`n"), $utf8)
    $versionDrift = Run-Installer $project @('-Scope','global','-Harness','opencode','-VerifyOnly')
    Check 'GLOBAL_VERSION_DRIFT_DETECTED' ($versionDrift.Code -ne 0 -and $versionDrift.Text -match 'GLOBAL_VERSION_DRIFT')
    $update = Run-Installer $project @('-Scope','global','-Harness','opencode')
    Check 'GLOBAL_UPDATE' ($update.Code -eq 0 -and $update.Text -match 'OLYMPUS_GLOBAL_INSTALL: OPENCODE .* READY' -and
        (Global-Verify $project 'opencode').Code -eq 0)

    $openAgentPath = Join-Path $openCodeRoot 'agents/kael.md'
    $openAgentBefore = [IO.File]::ReadAllText($openAgentPath)
    [IO.File]::AppendAllText($openAgentPath, "`n# qualification drift`n", $utf8)
    $openDrift = Run-Installer $project @('-Scope','global','-Harness','opencode','-VerifyOnly')
    $codexSubset = Global-Verify $project 'codex'
    Check 'GLOBAL_MANAGED_DRIFT_DETECTED' ($openDrift.Code -ne 0 -and $openDrift.Text -match 'GLOBAL_MANAGED_FILE_DRIFT')
    Check 'GLOBAL_SUBSET_VERIFY_IGNORES_OTHER_HARNESS' ($codexSubset.Code -eq 0)
    [IO.File]::WriteAllText($openAgentPath, $openAgentBefore, $utf8)

    $codexProfilePath = Join-Path $codexHome 'olympus.config.toml'
    $codexProfileBefore = [IO.File]::ReadAllText($codexProfilePath)
    [IO.File]::AppendAllText($codexProfilePath, "`n# qualification drift`n", $utf8)
    $codexDrift = Run-Installer $project @('-Scope','global','-Harness','codex','-VerifyOnly')
    $openSubset = Global-Verify $project 'opencode'
    Check 'GLOBAL_CODEX_MANAGED_DRIFT_DETECTED' ($codexDrift.Code -ne 0 -and $codexDrift.Text -match 'GLOBAL_MANAGED_FILE_DRIFT')
    Check 'GLOBAL_OPENCODE_SUBSET_VERIFY_IGNORES_CODEX_DRIFT' ($openSubset.Code -eq 0)
    [IO.File]::WriteAllText($codexProfilePath, $codexProfileBefore, $utf8)

    # Uninstall removes only manifest-owned resources, keeping unrelated global state.
    [IO.File]::WriteAllText((Join-Path $openCodeRoot 'user-note.txt'), 'preserve', $utf8)
    [IO.File]::WriteAllText((Join-Path $codexHome 'user-note.txt'), 'preserve', $utf8)
    $uninstall = Run-Installer $project @('-Scope','global','-Harness','all','-Uninstall')
    Check 'GLOBAL_UNINSTALL_ONLY_OWNED_RESOURCES' ($uninstall.Code -eq 0 -and
        -not (Test-Path (Join-Path $openCodeRoot 'agents/kael.md')) -and
        -not (Test-Path (Join-Path $codexHome 'agents/veyra.toml')) -and
        -not (Test-Path $openManifestPath) -and -not (Test-Path $codexManifestPath) -and
        (Test-Path $openUserConfig) -and (Test-Path $codexUserConfig) -and
        (Test-Path (Join-Path $openCodeRoot 'user-note.txt')) -and (Test-Path (Join-Path $codexHome 'user-note.txt')) -and
        (Snapshot $project) -ceq $projectBeforeMigration)
    Write-Output 'GLOBAL INSTALLER QUALIFICATION: PASS (isolated fixture roots; no real HOME writes or interactive harness session)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'GLOBAL INSTALLER QUALIFICATION: FAIL'
    exit 1
} finally {
    $env:PATH = $originalPath
    if ($null -eq $originalOpenCodeRoot) { Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue }
    else { $env:OPENCODE_CONFIG_DIR = $originalOpenCodeRoot }
    if ($null -eq $originalCodexHome) { Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue }
    else { $env:CODEX_HOME = $originalCodexHome }
    if ($null -eq $originalFixtureOpenCodeRoot) { Remove-Item Env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT -ErrorAction SilentlyContinue }
    else { $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $originalFixtureOpenCodeRoot }
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
