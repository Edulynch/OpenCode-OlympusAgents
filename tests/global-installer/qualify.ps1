[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$installerText = [IO.File]::ReadAllText($installer)
$candidateVersionMatch = [regex]::Match($installerText, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''')
if (-not $candidateVersionMatch.Success) { throw 'RELEASE_IDENTITY_INVALID: Installer default version is unavailable.' }
$candidateVersion = $candidateVersionMatch.Groups[1].Value
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

function Get-ExternalFallback([string]$ConfigPath) {
    # Model only the V2 last-matching wildcard fallback; runtime ASK and user
    # approval must still be observed separately in a native host smoke test.
    $jsonc = [IO.File]::ReadAllText($ConfigPath) -replace '(?m)^\s*//[^\r\n]*', ''
    $config = $jsonc | ConvertFrom-Json -Depth 30
    $effect = 'allow'
    foreach ($rule in @($config.permissions)) {
        if ('external_directory' -like $rule.action -and $rule.resource -ceq '*') {
            $effect = [string]$rule.effect
        }
    }
    return $effect
}

function Resolve-SyntheticExternalDecision([string]$ConfigPath, [string]$ExternalPath, [object[]]$ExtraRules = @()) {
    # This is an explicit ordered-rule model, not evidence of a native dialog.
    $jsonc = [IO.File]::ReadAllText($ConfigPath) -replace '(?m)^\s*//[^\r\n]*', ''
    $config = $jsonc | ConvertFrom-Json -Depth 30
    $decision = 'allow'
    foreach ($rule in (@($config.permissions) + @($ExtraRules))) {
        if ('external_directory' -like [string]$rule.action -and $ExternalPath -like [string]$rule.resource) {
            $decision = [string]$rule.effect
        }
    }
    return $decision
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
    # A user-owned V2 config with an ASK fallback and a later narrow DENY is
    # safe to preserve byte-for-byte; no manifest should claim ownership.
    $safeUserConfig = '{"user_owned":true,"permissions":[{"action":"external_directory","resource":"*","effect":"ask"},{"action":"external_directory","resource":"C:/fixture/prohibited/*","effect":"deny"}]}' + "`n"
    [IO.File]::WriteAllText($openUserConfig, $safeUserConfig, $utf8)
    [IO.File]::WriteAllText($codexUserConfig, "model = 'user-choice'`n", $utf8)
    $openUserHash = (Get-FileHash -LiteralPath $openUserConfig -Algorithm SHA256).Hash
    $codexUserHash = (Get-FileHash -LiteralPath $codexUserConfig -Algorithm SHA256).Hash

    # The existing project-local default stays project-scoped and records scope.
    $localInstall = Run-Installer $project @('-Harness','all')
    $localManifestPath = Join-Path $project '.opencode/orchestrator-install.json'
    $localManifest = Get-Content -LiteralPath $localManifestPath -Raw | ConvertFrom-Json
    Check 'PROJECT_SCOPE_ALL_INSTALL' ($localInstall.Code -eq 0 -and $localManifest.scope -eq 'project' -and
        $localManifest.installed_version -eq $candidateVersion -and $localManifest.installed_harnesses.Count -eq 2 -and
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
    Check 'GLOBAL_OPENCODE_CONTEXTUAL_KAEL_ROSTER' ((Test-Path (Join-Path $openCodeRoot 'agents/kael.md')) -and
        (Test-Path (Join-Path $openCodeRoot 'plugins/olympus-activity/activity.ts')) -and
        -not (Test-Path (Join-Path $openCodeRoot 'agents/aegis.md')) -and
        -not (Test-Path (Join-Path $openCodeRoot 'commands/maintain.md')))
    Check 'GLOBAL_CODEX_PROFILE_AND_AGENTS' ((Test-Path (Join-Path $codexHome 'agents/veyra.toml')) -and
        (Test-Path (Join-Path $codexHome 'olympus.config.toml')) -and
        (Test-Path (Join-Path $codexHome 'AGENTS.md')) -and
        (Get-Content (Join-Path $codexHome 'olympus.config.toml') -Raw).Contains('model = "gpt-6.1-sol"'))
    Check 'GLOBAL_USER_CONFIG_PROTECTED' ((Get-FileHash -LiteralPath $openUserConfig -Algorithm SHA256).Hash -eq $openUserHash -and
        (Get-FileHash -LiteralPath $codexUserConfig -Algorithm SHA256).Hash -eq $codexUserHash -and
        -not (Test-Path (Join-Path $openCodeRoot 'opencode.jsonc')))
    Check 'GLOBAL_USER_SPECIFIC_DENY_REMAINS_LAST' ((Get-ExternalFallback $openUserConfig) -eq 'ask' -and
        (Resolve-SyntheticExternalDecision $openUserConfig 'C:/fixture/prohibited/sentinel.txt') -eq 'deny' -and
        (Resolve-SyntheticExternalDecision $openUserConfig 'C:/fixture/authorized/sentinel.txt') -eq 'ask')

    # Unsafe user-owned configs must fail before creating an agent, manifest,
    # or alternative config file; the user must correct their own settings.
    foreach ($unsafeCase in @(
        @{ Name='missing-permissions'; Text='{"user_owned":true}' },
        @{ Name='default-allow'; Text='{"permissions":[{"action":"external_directory","resource":"*","effect":"allow"}]}' },
        @{ Name='last-rule-allow'; Text='{"permissions":[{"action":"external_directory","resource":"*","effect":"ask"},{"action":"*","resource":"*","effect":"allow"}]}' },
        @{ Name='double-wildcard-allow'; Text='{"permissions":[{"action":"external_directory","resource":"*","effect":"ask"},{"action":"external_directory","resource":"**","effect":"allow"}]}' },
        @{ Name='wildcard-question-allow'; Text='{"permissions":[{"action":"external_directory","resource":"*","effect":"deny"},{"action":"*","resource":"?*","effect":"allow"}]}' },
        @{ Name='wildcard-path-allow'; Text='{"permissions":[{"action":"external_directory","resource":"*","effect":"ask"},{"action":"external_directory","resource":"*/**","effect":"allow"}]}' },
        @{ Name='drive-wildcard-allow'; Text='{"permissions":[{"action":"external_directory","resource":"*","effect":"ask"},{"action":"external_directory","resource":"?:/**","effect":"allow"}]}' },
        @{ Name='colon-wildcard-allow'; Text='{"permissions":[{"action":"external_directory","resource":"*","effect":"ask"},{"action":"external_directory","resource":"*:*","effect":"allow"}]}' },
        @{ Name='question-deny-false-fallback'; Text='{"permissions":[{"action":"external_directory","resource":"*","effect":"allow"},{"action":"external_directory","resource":"?","effect":"deny"}]}' },
        @{ Name='questions-ask-false-fallback'; Text='{"permissions":[{"action":"external_directory","resource":"*","effect":"allow"},{"action":"external_directory","resource":"??","effect":"ask"}]}' },
        @{ Name='malformed'; Text='{"permissions":[' }
    )) {
        $unsafeRoot = Join-Path $run ('OpenCode Unsafe ' + $unsafeCase.Name)
        [IO.Directory]::CreateDirectory($unsafeRoot) | Out-Null
        $unsafeFile = Join-Path $unsafeRoot 'opencode.jsonc'
        [IO.File]::WriteAllText($unsafeFile, $unsafeCase.Text, $utf8)
        $unsafeBefore = Snapshot $unsafeRoot
        $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $unsafeRoot
        $unsafeInstall = Run-Installer $project @('-Scope','global','-Harness','opencode')
        Check ('GLOBAL_UNSAFE_USER_CONFIG_' + $unsafeCase.Name.ToUpperInvariant().Replace('-','_')) (
            $unsafeInstall.Code -ne 0 -and
            $unsafeInstall.Text -match 'GLOBAL_EXTERNAL_GUARD_UNSAFE' -and
            (Snapshot $unsafeRoot) -ceq $unsafeBefore
        ) ("exit=$($unsafeInstall.Code)`n$($unsafeInstall.Text)")
    }

    # A later universal ASK restores the safe fallback. Narrow user DENYs
    # remain intact; the validator must follow ordered rules, not first-match.
    $safeBroadRoot = Join-Path $run 'OpenCode Safe Broad Restoration'
    [IO.Directory]::CreateDirectory($safeBroadRoot) | Out-Null
    $safeBroadFile = Join-Path $safeBroadRoot 'opencode.jsonc'
    $safeBroadText = '{"permissions":[{"action":"external_directory","resource":"**","effect":"allow"},{"action":"external_directory","resource":"*","effect":"ask"},{"action":"external_directory","resource":"C:/fixture/authorized/*","effect":"allow"},{"action":"external_directory","resource":"C:\\fixture\\authorized-extra\\*","effect":"allow"},{"action":"external_directory","resource":"C:/fixture/prohibited/*","effect":"deny"}]}'
    [IO.File]::WriteAllText($safeBroadFile, $safeBroadText, $utf8)
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $safeBroadRoot
    $safeBroadInstall = Global-Install $project 'opencode'
    Check 'GLOBAL_LATER_ASK_AND_NARROW_DENY_PRESERVED' (
        $safeBroadInstall.Code -eq 0 -and
        [IO.File]::ReadAllText($safeBroadFile) -ceq $safeBroadText -and
        (Resolve-SyntheticExternalDecision $safeBroadFile 'C:/fixture/prohibited/sentinel.txt') -eq 'deny'
    ) ("exit=$($safeBroadInstall.Code)`n$($safeBroadInstall.Text)")

    # A JSONC user config with trailing commas and an explicit DENY fallback
    # is a supported safe case; never rewrite it or adopt it into the manifest.
    $userDenyRoot = Join-Path $run 'OpenCode User Global DENY'
    [IO.Directory]::CreateDirectory($userDenyRoot) | Out-Null
    $userDenyPath = Join-Path $userDenyRoot 'opencode.jsonc'
    $userDenyText = "{`n // user-owned`n `"permissions`": [{`"action`":`"external_directory`",`"resource`":`"*`",`"effect`":`"deny`"},],`n}`n"
    [IO.File]::WriteAllText($userDenyPath, $userDenyText, $utf8)
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $userDenyRoot
    $denyInstall = Run-Installer $project @('-Scope','global','-Harness','opencode')
    $denyManifest = if ($denyInstall.Code -eq 0) { Get-Content (Join-Path $userDenyRoot 'olympus/orchestrator-install.json') -Raw | ConvertFrom-Json } else { $null }
    Check 'GLOBAL_USER_JSONC_DENY_PRESERVED' (
        $denyInstall.Code -eq 0 -and
        $null -ne $denyManifest -and $denyManifest.managed_files.Count -eq 13 -and
        @($denyManifest.managed_files | Where-Object { $_.path -eq 'opencode.jsonc' }).Count -eq 0 -and
        [IO.File]::ReadAllText($userDenyPath) -ceq $userDenyText
    ) ("exit=$($denyInstall.Code)`n$($denyInstall.Text)")
    # Reproduce an older 13-file global install with no config. Upgrading it
    # must establish the missing guard without disturbing its owned agents.
    [IO.File]::Delete($userDenyPath)
    $legacyNoConfigUpgrade = Global-Install $project 'opencode'
    $legacyUpgradedManifest = Get-Content (Join-Path $userDenyRoot 'olympus/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'GLOBAL_13_FILE_UPGRADE_ADDS_MANAGED_ASK' (
        $legacyNoConfigUpgrade.Code -eq 0 -and
        $legacyUpgradedManifest.managed_files.Count -eq 14 -and
        (Get-ExternalFallback $userDenyPath) -eq 'ask'
    ) ("exit=$($legacyNoConfigUpgrade.Code)`n$($legacyNoConfigUpgrade.Text)")
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeRoot

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
        $openCodeOnlyManifest.managed_files.Count -eq 14)
    $ownedGuardPath = Join-Path $openCodeOnlyRoot 'opencode.jsonc'
    Check 'GLOBAL_ONLY_EXTERNAL_ASK_MANAGED' (
        (Get-ExternalFallback $ownedGuardPath) -eq 'ask' -and
        @($openCodeOnlyManifest.managed_files | Where-Object { $_.path -eq 'opencode.jsonc' }).Count -eq 1 -and
        (Global-Verify $project 'opencode').Code -eq 0
    )
    # ASK requires approval (a rejected approval blocks the read). A following
    # explicit specific DENY rejects without prompting; these are modeled
    # outcomes, not a native observation of either prompt or rejection.
    $externalProbe = 'C:/fixture/prohibited/sentinel.txt'
    $explicitDeny = [pscustomobject]@{ action='external_directory'; resource='C:/fixture/prohibited/*'; effect='deny' }
    $askDecision = Resolve-SyntheticExternalDecision $ownedGuardPath $externalProbe
    $denyDecision = Resolve-SyntheticExternalDecision $ownedGuardPath $externalProbe @($explicitDeny)
    Check 'GLOBAL_ONLY_ASK_AND_SPECIFIC_DENY_SYNTHETIC' (
        $askDecision -eq 'ask' -and $denyDecision -eq 'deny' -and
        $askDecision -ne 'allow'
    )

    # Simulate a process interruption after the minimal guard was written but
    # before its ownership manifest. The durable intent must let a later
    # install adopt only the exact expected bytes and then retire the marker.
    $recoverRoot = Join-Path $run 'OpenCode Guard Interrupted Install'
    [IO.Directory]::CreateDirectory((Join-Path $recoverRoot 'olympus')) | Out-Null
    $recoverGuardPath = Join-Path $recoverRoot 'opencode.jsonc'
    $guardSourcePath = Join-Path $source 'olympus/harnesses/opencode/global-permissions.jsonc'
    $guardSourceText = [IO.File]::ReadAllText($guardSourcePath)
    $guardSourceHash = (Get-FileHash -LiteralPath $guardSourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $recoverIntentPath = Join-Path $recoverRoot 'olympus/opencode-guard-pending.json'
    $recoverIntent = ([ordered]@{
        schema_version = 1
        harness = 'opencode'
        resource = 'opencode.jsonc'
        sha256 = $guardSourceHash
    } | ConvertTo-Json -Depth 5) + "`n"
    [IO.File]::WriteAllText($recoverIntentPath, $recoverIntent, $utf8)
    [IO.File]::WriteAllText($recoverGuardPath, $guardSourceText, $utf8)
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $recoverRoot
    $recoverVerifyBefore = Global-Verify $project 'opencode'
    $recoverInstall = Global-Install $project 'opencode'
    $recoverManifestPath = Join-Path $recoverRoot 'olympus/orchestrator-install.json'
    $recoverManifest = if ($recoverInstall.Code -eq 0) { Get-Content -LiteralPath $recoverManifestPath -Raw | ConvertFrom-Json } else { $null }
    Check 'GLOBAL_INTERRUPTED_GUARD_RECOVERED_AND_OWNED' (
        $recoverVerifyBefore.Code -ne 0 -and
        $recoverInstall.Code -eq 0 -and $null -ne $recoverManifest -and
        $recoverManifest.managed_files.Count -eq 14 -and
        @($recoverManifest.managed_files | Where-Object { $_.path -eq 'opencode.jsonc' }).Count -eq 1 -and
        (Get-FileHash -LiteralPath $recoverGuardPath -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $guardSourceHash -and
        -not (Test-Path -LiteralPath $recoverIntentPath) -and
        (Global-Verify $project 'opencode').Code -eq 0
    ) ("exit=$($recoverInstall.Code)`n$($recoverInstall.Text)")

    # A legacy 13-file upgrade can be interrupted after an old managed agent
    # was replaced with the canonical bytes but before manifest publication.
    # Unrecognized edits are never adopted, even with a valid guard intent.
    $upgradeRoot = Join-Path $run 'OpenCode Interrupted Managed Upgrade'
    [IO.Directory]::CreateDirectory($upgradeRoot) | Out-Null
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $upgradeRoot
    $upgradeSeed = Global-Install $project 'opencode'
    if ($upgradeSeed.Code -ne 0) { throw "Interrupted upgrade fixture install failed: $($upgradeSeed.Text)" }
    $upgradeManifestPath = Join-Path $upgradeRoot 'olympus/orchestrator-install.json'
    $upgradeManifest = Get-Content -LiteralPath $upgradeManifestPath -Raw | ConvertFrom-Json
    $upgradeAgent = Join-Path $upgradeRoot 'agents/kael.md'
    $currentAgentText = [IO.File]::ReadAllText($upgradeAgent)
    $priorAgentText = $currentAgentText + "`n# prior managed version`n"
    [IO.File]::WriteAllText($upgradeAgent, $priorAgentText, $utf8)
    $upgradeAgentEntry = @($upgradeManifest.managed_files | Where-Object { $_.path -eq 'agents/kael.md' })[0]
    $upgradeAgentEntry.sha256 = (Get-FileHash -LiteralPath $upgradeAgent -Algorithm SHA256).Hash.ToLowerInvariant()
    $upgradeManifest.managed_files = @($upgradeManifest.managed_files | Where-Object { $_.path -ne 'opencode.jsonc' })
    $upgradeManifest.installed_version = 'historical-13-file-version'
    [IO.File]::WriteAllText($upgradeManifestPath, (($upgradeManifest | ConvertTo-Json -Depth 20) + "`n"), $utf8)
    [IO.File]::Delete((Join-Path $upgradeRoot 'opencode.jsonc'))
    [IO.File]::WriteAllText((Join-Path $upgradeRoot 'olympus/opencode-guard-pending.json'), $recoverIntent, $utf8)
    [IO.File]::WriteAllText((Join-Path $upgradeRoot 'opencode.jsonc'), $guardSourceText, $utf8)
    [IO.File]::WriteAllText($upgradeAgent, 'unrecognized user edit', $utf8)
    $unknownUpgradeBefore = Snapshot $upgradeRoot
    $unknownUpgrade = Global-Install $project 'opencode'
    Check 'GLOBAL_PENDING_UPGRADE_UNKNOWN_DRIFT_FAILS_CLOSED' (
        $unknownUpgrade.Code -ne 0 -and $unknownUpgrade.Text -match 'GLOBAL_MANAGED_FILE_DRIFT' -and
        (Snapshot $upgradeRoot) -ceq $unknownUpgradeBefore
    ) ("exit=$($unknownUpgrade.Code)`n$($unknownUpgrade.Text)")
    [IO.File]::WriteAllText($upgradeAgent, $currentAgentText, $utf8)
    $upgradeRecovered = Global-Install $project 'opencode'
    $upgradeRecoveredManifest = if ($upgradeRecovered.Code -eq 0) { Get-Content -LiteralPath $upgradeManifestPath -Raw | ConvertFrom-Json } else { $null }
    Check 'GLOBAL_PENDING_13_TO_14_MANAGED_AGENT_ROLLFORWARD' (
        $upgradeRecovered.Code -eq 0 -and $null -ne $upgradeRecoveredManifest -and
        $upgradeRecoveredManifest.managed_files.Count -eq 14 -and
        -not (Test-Path (Join-Path $upgradeRoot 'olympus/opencode-guard-pending.json')) -and
        (Global-Verify $project 'opencode').Code -eq 0
    ) ("exit=$($upgradeRecovered.Code)`n$($upgradeRecovered.Text)")

    # Exercise the exact production writer in isolation. The concurrent-file
    # case is modeled at the final create syscall, where CreateNew must fail
    # without replacing existing config bytes.
    $nativeInstallerPath = Join-Path $source 'scripts/global-install.ps1'
    $parseTokens = $null
    $parseErrors = $null
    $installerAst = [System.Management.Automation.Language.Parser]::ParseFile($nativeInstallerPath, [ref]$parseTokens, [ref]$parseErrors)
    $guardWriters = @($installerAst.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Write-NewOpenCodeGuard'
    }, $true))
    Check 'GLOBAL_GUARD_EXCLUSIVE_WRITER_PARSES' ($parseErrors.Count -eq 0 -and $guardWriters.Count -eq 1)
    $exclusiveProbe = [scriptblock]::Create(
        'param([string]$path, [string]$text)' + "`n" +
        '$Utf8NoBom = [Text.UTF8Encoding]::new($false)' + "`n" +
        $guardWriters[0].Extent.Text + "`n" +
        'Write-NewOpenCodeGuard $path $text'
    )
    $raceConfigPath = Join-Path $run 'exclusive-writer-user-config.jsonc'
    $raceUserBytes = '{"user_owned":true,"permissions":[]}'
    [IO.File]::WriteAllText($raceConfigPath, $raceUserBytes, $utf8)
    $raceRejected = $false
    try { & $exclusiveProbe $raceConfigPath $guardSourceText }
    catch { $raceRejected = $true }
    Check 'GLOBAL_GUARD_EXCLUSIVE_CREATE_PRESERVES_RACING_USER_CONFIG' (
        $raceRejected -and [IO.File]::ReadAllText($raceConfigPath) -ceq $raceUserBytes
    )
    $freshConfigPath = Join-Path $run 'exclusive-writer-fresh-guard.jsonc'
    & $exclusiveProbe $freshConfigPath $guardSourceText
    Check 'GLOBAL_GUARD_EXCLUSIVE_CREATE_WRITES_NEW_FILE' (
        [IO.File]::ReadAllText($freshConfigPath) -ceq $guardSourceText
    )

    # The second config format can appear after an exclusive .jsonc create.
    # Exercise the production post-write collision check without changing
    # existing fixture files or depending on a nondeterministic timing race.
    $collisionFunctions = @($installerAst.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Assert-NoOpenCodeConfigCollision'
    }, $true))
    Check 'GLOBAL_GUARD_FORMAT_COLLISION_CHECK_PARSES' ($collisionFunctions.Count -eq 1)
    $formatProbe = [scriptblock]::Create(
        'param([string]$root)' + "`n" +
        '$OpenCodeConfigRelative = ''opencode.jsonc''' + "`n" +
        'function Assert-SafeDestination([string]$root, [string]$relative) { Join-Path $root $relative }' + "`n" +
        'function Fail([string]$code, [string]$message) { throw "$code`: $message" }' + "`n" +
        $collisionFunctions[0].Extent.Text + "`n" +
        'Assert-NoOpenCodeConfigCollision $root'
    )
    $formatCollisionRoot = Join-Path $run 'post-create-format-collision'
    [IO.Directory]::CreateDirectory($formatCollisionRoot) | Out-Null
    $formatCollisionJson = Join-Path $formatCollisionRoot 'opencode.json'
    $formatCollisionJsonc = Join-Path $formatCollisionRoot 'opencode.jsonc'
    [IO.File]::WriteAllText($formatCollisionJsonc, $guardSourceText, $utf8)
    [IO.File]::WriteAllText($formatCollisionJson, '{"permissions":[]}', $utf8)
    $formatCollisionBefore = Snapshot $formatCollisionRoot
    $formatCollisionRejected = $false
    try { & $formatProbe $formatCollisionRoot }
    catch { $formatCollisionRejected = $_.Exception.Message -match 'GLOBAL_EXTERNAL_GUARD_UNSAFE' }
    Check 'GLOBAL_GUARD_SECOND_CONFIG_APPEARING_AFTER_CREATE_REJECTED' (
        $formatCollisionRejected -and (Snapshot $formatCollisionRoot) -ceq $formatCollisionBefore
    )
    [IO.File]::Delete($formatCollisionJson)
    & $formatProbe $formatCollisionRoot
    Check 'GLOBAL_GUARD_NO_SECOND_CONFIG_ACCEPTED' (Test-Path -LiteralPath $formatCollisionJsonc -PathType Leaf)

    # A safe user-owned .json must receive the same collision protection if
    # another process creates .jsonc while agents are being installed.
    [IO.File]::Delete($formatCollisionJsonc)
    [IO.File]::WriteAllText($formatCollisionJson, $safeUserConfig, $utf8)
    & $formatProbe $formatCollisionRoot
    [IO.File]::WriteAllText($formatCollisionJsonc, $guardSourceText, $utf8)
    $unownedCollisionBefore = Snapshot $formatCollisionRoot
    $unownedCollisionRejected = $false
    try { & $formatProbe $formatCollisionRoot }
    catch { $unownedCollisionRejected = $_.Exception.Message -match 'GLOBAL_EXTERNAL_GUARD_UNSAFE' }
    Check 'GLOBAL_USER_OWNED_FORMAT_COLLISION_REJECTED' (
        $unownedCollisionRejected -and (Snapshot $formatCollisionRoot) -ceq $unownedCollisionBefore
    )

    # The interrupted-install recovery fixture resumes in its own root;
    # earlier upgrade and collision probes must not change its destination.
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $recoverRoot

    # A crash after manifest replacement but before intent cleanup must also
    # be idempotently reconciled, and only an owned guard is removed on uninstall.
    [IO.File]::WriteAllText($recoverIntentPath, $recoverIntent, $utf8)
    $recoverNoop = Global-Install $project 'opencode'
    $recoverUninstall = Run-Installer $project @('-Scope','global','-Harness','opencode','-Uninstall')
    Check 'GLOBAL_INTERRUPTED_GUARD_CLEANUP_AND_UNINSTALL' (
        $recoverNoop.Code -eq 0 -and $recoverUninstall.Code -eq 0 -and
        -not (Test-Path -LiteralPath $recoverIntentPath) -and
        -not (Test-Path -LiteralPath $recoverGuardPath) -and
        -not (Test-Path -LiteralPath $recoverManifestPath)
    ) ("install=$($recoverNoop.Code)`n$($recoverNoop.Text)`nuninstall=$($recoverUninstall.Code)`n$($recoverUninstall.Text)")

    # Intent persisted before any guard bytes were written is safe to resume.
    $intentOnlyRoot = Join-Path $run 'OpenCode Guard Intent Only'
    [IO.Directory]::CreateDirectory((Join-Path $intentOnlyRoot 'olympus')) | Out-Null
    $intentOnlyMarker = Join-Path $intentOnlyRoot 'olympus/opencode-guard-pending.json'
    [IO.File]::WriteAllText($intentOnlyMarker, $recoverIntent, $utf8)
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $intentOnlyRoot
    $intentOnlyInstall = Global-Install $project 'opencode'
    Check 'GLOBAL_INTERRUPTED_BEFORE_GUARD_WRITE_RECOVERED' (
        $intentOnlyInstall.Code -eq 0 -and
        -not (Test-Path -LiteralPath $intentOnlyMarker) -and
        (Get-FileHash -LiteralPath (Join-Path $intentOnlyRoot 'opencode.jsonc') -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $guardSourceHash
    ) ("exit=$($intentOnlyInstall.Code)`n$($intentOnlyInstall.Text)")

    # An altered guard with the same pending marker cannot be adopted. A
    # failed recovery must leave the caller's current bytes untouched.
    $recoverConflictRoot = Join-Path $run 'OpenCode Guard Interrupted Conflict'
    [IO.Directory]::CreateDirectory((Join-Path $recoverConflictRoot 'olympus')) | Out-Null
    [IO.File]::WriteAllText((Join-Path $recoverConflictRoot 'olympus/opencode-guard-pending.json'), $recoverIntent, $utf8)
    [IO.File]::WriteAllText((Join-Path $recoverConflictRoot 'opencode.jsonc'), '{"permissions":[]}', $utf8)
    $recoverConflictBefore = Snapshot $recoverConflictRoot
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $recoverConflictRoot
    $recoverConflict = Global-Install $project 'opencode'
    Check 'GLOBAL_INTERRUPTED_GUARD_CONFLICT_FAIL_CLOSED' (
        $recoverConflict.Code -ne 0 -and
        $recoverConflict.Text -match 'GLOBAL_GUARD_RECOVERY_CONFLICT' -and
        (Snapshot $recoverConflictRoot) -ceq $recoverConflictBefore
    ) ("exit=$($recoverConflict.Code)`n$($recoverConflict.Text)")
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeOnlyRoot

    $doubleConfigRoot = Join-Path $run 'OpenCode Ambiguous Config'
    [IO.Directory]::CreateDirectory($doubleConfigRoot) | Out-Null
    [IO.File]::WriteAllText((Join-Path $doubleConfigRoot 'opencode.json'), $safeUserConfig, $utf8)
    [IO.File]::WriteAllText((Join-Path $doubleConfigRoot 'opencode.jsonc'), $safeUserConfig, $utf8)
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $doubleConfigRoot
    $doubleBefore = Snapshot $doubleConfigRoot
    $doubleInstall = Global-Install $project 'opencode'
    Check 'GLOBAL_AMBIGUOUS_USER_CONFIG_FAIL_CLOSED' ($doubleInstall.Code -ne 0 -and
        $doubleInstall.Text -match 'GLOBAL_EXTERNAL_GUARD_UNSAFE' -and
        (Snapshot $doubleConfigRoot) -ceq $doubleBefore)
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeOnlyRoot

    $ownedGuardOriginal = [IO.File]::ReadAllText($ownedGuardPath)
    [IO.File]::AppendAllText($ownedGuardPath, "// user changed managed guard`n", $utf8)
    $guardDriftBefore = Snapshot $openCodeOnlyRoot
    $guardDriftVerify = Global-Verify $project 'opencode'
    $guardDriftUninstall = Run-Installer $project @('-Scope','global','-Harness','opencode','-Uninstall')
    Check 'GLOBAL_MANAGED_GUARD_DRIFT_PRESERVED' (
        $guardDriftVerify.Code -ne 0 -and $guardDriftVerify.Text -match 'GLOBAL_MANAGED_FILE_DRIFT' -and
        $guardDriftUninstall.Code -ne 0 -and $guardDriftUninstall.Text -match 'GLOBAL_MANAGED_FILE_DRIFT' -and
        (Snapshot $openCodeOnlyRoot) -ceq $guardDriftBefore
    )
    [IO.File]::WriteAllText($ownedGuardPath, $ownedGuardOriginal, $utf8)

    # A clean-break update retires the previous Aegis/command only when the old
    # global manifest still owns their exact bytes.
    $openCodeOnlyManifestPath = Join-Path $openCodeOnlyRoot 'olympus/orchestrator-install.json'
    $legacyPaths = @('agents/aegis.md','commands/maintain.md')
    $legacyText = @('historical generated agent','historical generated command')
    $retiredManifest = Get-Content -LiteralPath $openCodeOnlyManifestPath -Raw | ConvertFrom-Json
    for ($i = 0; $i -lt $legacyPaths.Count; $i++) {
        $legacyFile = Join-Path $openCodeOnlyRoot $legacyPaths[$i]
        [IO.Directory]::CreateDirectory((Split-Path -Parent $legacyFile)) | Out-Null
        [IO.File]::WriteAllText($legacyFile, $legacyText[$i] + "`n", $utf8)
        $retiredManifest.managed_files += [pscustomobject]@{
            path=$legacyPaths[$i]
            sha256=(Get-FileHash -LiteralPath $legacyFile -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    [IO.File]::WriteAllText($openCodeOnlyManifestPath, (($retiredManifest | ConvertTo-Json -Depth 20) + "`n"), $utf8)
    $globalMigration = Run-Installer $project @('-Scope','global','-Harness','opencode')
    $migratedGlobalManifest = Get-Content -LiteralPath $openCodeOnlyManifestPath -Raw | ConvertFrom-Json
    Check 'GLOBAL_RETIRED_RESOURCES_HASH_VERIFIED_REMOVAL' ($globalMigration.Code -eq 0 -and
        -not (Test-Path (Join-Path $openCodeOnlyRoot 'agents/aegis.md')) -and
        -not (Test-Path (Join-Path $openCodeOnlyRoot 'commands/maintain.md')) -and
        $migratedGlobalManifest.managed_files.Count -eq 14)

    $ownedGuardUninstall = Run-Installer $project @('-Scope','global','-Harness','opencode','-Uninstall')
    Check 'GLOBAL_OWNED_ONLY_GUARD_REMOVED_ON_UNINSTALL' (
        $ownedGuardUninstall.Code -eq 0 -and
        -not (Test-Path $ownedGuardPath) -and
        -not (Test-Path $openCodeOnlyManifestPath)
    )

    $openCodeDriftRoot = Join-Path $run 'OpenCode Global Retired Drift'
    [IO.Directory]::CreateDirectory($openCodeDriftRoot) | Out-Null
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeDriftRoot
    $driftInstall = Run-Installer $project @('-Scope','global','-Harness','opencode')
    if ($driftInstall.Code -ne 0) { throw "Global drift fixture install failed: $($driftInstall.Text)" }
    $driftManifestPath = Join-Path $openCodeDriftRoot 'olympus/orchestrator-install.json'
    $driftManifest = Get-Content -LiteralPath $driftManifestPath -Raw | ConvertFrom-Json
    $driftLegacy = Join-Path $openCodeDriftRoot 'agents/aegis.md'
    [IO.File]::WriteAllText($driftLegacy, "historical generated agent`n", $utf8)
    $driftManifest.managed_files += [pscustomobject]@{
        path='agents/aegis.md'
        sha256=(Get-FileHash -LiteralPath $driftLegacy -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $driftCommand = Join-Path $openCodeDriftRoot 'commands/maintain.md'
    [IO.Directory]::CreateDirectory((Split-Path -Parent $driftCommand)) | Out-Null
    [IO.File]::WriteAllText($driftCommand, "historical generated command`n", $utf8)
    $driftManifest.managed_files += [pscustomobject]@{
        path='commands/maintain.md'
        sha256=(Get-FileHash -LiteralPath $driftCommand -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    [IO.File]::WriteAllText($driftManifestPath, (($driftManifest | ConvertTo-Json -Depth 20) + "`n"), $utf8)
    [IO.File]::AppendAllText($driftLegacy, "user edit`n", $utf8)
    $driftBefore = Snapshot $openCodeDriftRoot
    $driftUpdate = Run-Installer $project @('-Scope','global','-Harness','opencode')
    Check 'GLOBAL_MODIFIED_RETIRED_RESOURCE_PRESERVED' ($driftUpdate.Code -ne 0 -and
        $driftUpdate.Text -match 'GLOBAL_MANAGED_FILE_DRIFT' -and
        (Snapshot $openCodeDriftRoot) -ceq $driftBefore)

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
        $openManifest.managed_files.Count -eq 13 -and $codexManifest.managed_files.Count -eq 12)

    $openBeforeVerify = Snapshot $openCodeRoot
    $codexBeforeVerify = Snapshot $codexHome
    $verifyAll = Global-Verify $project 'all'
    Check 'GLOBAL_VERIFYONLY_ALL_READONLY' ($verifyAll.Code -eq 0 -and $verifyAll.Text -match 'OLYMPUS_GLOBAL_VERIFY: opencode' -and
        $verifyAll.Text -match 'OLYMPUS_GLOBAL_VERIFY: codex' -and (Snapshot $openCodeRoot) -ceq $openBeforeVerify -and
        (Snapshot $codexHome) -ceq $codexBeforeVerify)

    # Issue #46: exact generated files without the ownership manifest are not
    # a verified global installation. Exercise each harness in fixture-owned
    # roots and restore the original manifest bytes for later qualification.
    foreach ($fixture in @(
        @{ Harness='opencode'; Root=$openCodeRoot; Manifest=$openManifestPath },
        @{ Harness='codex'; Root=$codexHome; Manifest=$codexManifestPath }
    )) {
        $harness = [string]$fixture.Harness
        $manifestPath = [string]$fixture.Manifest
        $manifestBytes = [IO.File]::ReadAllBytes($manifestPath)
        try {
            [IO.File]::Delete($manifestPath)
            $beforeMissing = Snapshot $fixture.Root
            $missing = Global-Verify $project $harness
            $afterMissing = Snapshot $fixture.Root
            $checkPrefix = 'GLOBAL_VERIFYONLY_' + $harness.ToUpperInvariant()
            Check ($checkPrefix + '_MISSING_MANIFEST_REJECTED') ($missing.Code -ne 0 -and
                $missing.Text -match 'GLOBAL_MANIFEST_MISSING' -and
                $missing.Text -notmatch ('OLYMPUS_GLOBAL_VERIFY: ' + $harness + ' .* PASS')) (
                "exit=$($missing.Code)`n$($missing.Text)")
            Check ($checkPrefix + '_MISSING_MANIFEST_READONLY') ($beforeMissing -ceq $afterMissing)
        } finally {
            [IO.File]::WriteAllBytes($manifestPath, $manifestBytes)
        }
    }
    $restoredVerify = Global-Verify $project 'all'
    Check 'GLOBAL_VERIFYONLY_ALL_RESTORED_PASS' ($restoredVerify.Code -eq 0 -and
        (Snapshot $openCodeRoot) -ceq $openBeforeVerify -and
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
