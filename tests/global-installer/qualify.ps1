[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$globalInstaller = Join-Path $source 'scripts/global-install.ps1'
$projectInstaller = Join-Path $source 'scripts/bootstrap.ps1'
$projectUninstaller = Join-Path $source 'scripts/project-uninstall.ps1'
$installerText = [IO.File]::ReadAllText($installer)
$candidateVersionMatch = [regex]::Match($installerText, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''')
if (-not $candidateVersionMatch.Success) { throw 'RELEASE_IDENTITY_INVALID: Installer default version is unavailable.' }
$candidateVersion = $candidateVersionMatch.Groups[1].Value
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('opencode\olympus-global-installer-' + [guid]::NewGuid().ToString('N'))
$originalPath = $env:PATH
$originalOpenCodeRoot = $env:OPENCODE_CONFIG_DIR
$originalFixtureOpenCodeRoot = $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT
$originalOlympusConfigFile = $env:OLYMPUS_CONFIG_FILE
$cliInstallRoot = Join-Path $run 'cli-install'
$cliPathStorePath = Join-Path $cliInstallRoot 'path-store.txt'
$utf8 = [Text.UTF8Encoding]::new($false)
. (Join-Path $PSScriptRoot '../installer-test-environment.ps1')
$isolatedEnvironment = $null

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
    $scope = 'project'
    $harness = 'opencode'
    $remaining = [System.Collections.Generic.List[string]]::new()
    for ($index = 0; $index -lt $Arguments.Count; $index++) {
        if ($Arguments[$index] -eq '-Scope' -and $index + 1 -lt $Arguments.Count) {
            $scope = $Arguments[++$index]
        } elseif ($Arguments[$index] -eq '-Harness' -and $index + 1 -lt $Arguments.Count) {
            $harness = $Arguments[++$index]
        } elseif ($Arguments[$index] -eq '-Target' -and $index + 1 -lt $Arguments.Count) {
            $index++
        } elseif ($Arguments[$index] -eq '-Uninstall' -and $scope -eq 'project') {
            continue
        } else { $remaining.Add($Arguments[$index]) }
    }
    $isUninstall = '-Uninstall' -in $Arguments
    if ($scope -eq 'project') {
        $engine = if ($isUninstall) { $projectUninstaller } else { $projectInstaller }
        $engineArgs = @('-NoProfile', '-File', $engine, '-Target', $Target, '-Harness', $harness)
        if (-not $isUninstall) { $engineArgs += @('-SourceVersion', $candidateVersion) }
        $engineArgs += $remaining
    } elseif ($harness -eq 'opencode') {
        $engineArgs = @('-NoProfile', '-File', $installer, '-SourceRoot', $source,
            '-Version', $candidateVersion, '-Scope', 'global', '-Harness', 'opencode',
            '-CliInstallRoot', $cliInstallRoot, '-CliPathStorePath', $cliPathStorePath) + $remaining
    } else {
        $engineArgs = @('-NoProfile', '-File', $globalInstaller, '-Harness', $harness,
            '-SourceVersion', $candidateVersion, '-ProjectTarget', $Target) + $remaining
    }
    $previousOpenCodeRoot = $env:OPENCODE_CONFIG_DIR
    if ($scope -eq 'global') {
        $env:OPENCODE_CONFIG_DIR = [string]$env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT
    }
    $previousErrorActionPreference = $ErrorActionPreference
    $locationPushed = $false
    try {
        Push-Location -LiteralPath $Target
        $locationPushed = $true
        # Windows PowerShell 5.1 turns native stderr into a terminating error
        # under Stop; preserve expected installer failures as captured evidence.
        $ErrorActionPreference = 'Continue'
        Push-Location -LiteralPath $Target
        try {
            $output = (& pwsh @engineArgs 2>&1 | Out-String)
            $code = $LASTEXITCODE
        } finally { Pop-Location }
    } finally {
        if ($locationPushed) { Pop-Location }
        $ErrorActionPreference = $previousErrorActionPreference
        if ($null -eq $previousOpenCodeRoot) { Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue }
        else { $env:OPENCODE_CONFIG_DIR = $previousOpenCodeRoot }
    }
    return [pscustomobject]@{ Text=$output; Code=$code }
}

function Global-Install([string]$Target, [string]$Harness = 'opencode') {
    Run-Installer $Target @('-Scope','global','-Harness',$Harness)
}

function Global-Verify([string]$Target, [string]$Harness = 'opencode') {
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

function Get-AccessDaclSnapshot([string]$Path) {
    $acl = [IO.FileSystemAclExtensions]::GetAccessControl(
        [IO.FileInfo]::new($Path), [Security.AccessControl.AccessControlSections]::Access)
    $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    return [pscustomobject]@{
        Sddl = $acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)
        Protected = $acl.AreAccessRulesProtected
        ExplicitCount = @($rules | Where-Object { -not $_.IsInherited }).Count
        InheritedCount = @($rules | Where-Object { $_.IsInherited }).Count
    }
}

function Set-ProtectedFixtureDacl([string]$Path) {
    $acl = [IO.FileSystemAclExtensions]::GetAccessControl(
        [IO.FileInfo]::new($Path), [Security.AccessControl.AccessControlSections]::Access)
    $acl.SetAccessRuleProtection($true, $false)
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        $sid, [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.AccessControlType]::Allow)
    $acl.SetAccessRule($rule)
    [IO.FileSystemAclExtensions]::SetAccessControl([IO.FileInfo]::new($Path), $acl)
    $snapshot = Get-AccessDaclSnapshot $Path
    if (-not $snapshot.Protected -or $snapshot.ExplicitCount -eq 0 -or $snapshot.InheritedCount -ne 0) {
        throw "FIXTURE_DACL_SETUP_FAILED: $Path"
    }
    return $snapshot
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
    $isolatedEnvironment = Enter-OlympusInstallerTestEnvironment $run
    $env:OLYMPUS_CLI_ROOT = $cliInstallRoot
    $env:OLYMPUS_CLI_PATH_STORE = $cliPathStorePath
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: global install qualification is Windows-only.' }
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $openCodeRoot = Join-Path $run 'OpenCode Global Config'
    $env:OLYMPUS_CONFIG_FILE = Join-Path $run 'Olympus User Config/config.json'
    [IO.Directory]::CreateDirectory($openCodeRoot) | Out-Null
    $project = New-Target 'opencode-project'
    $mockBin = Join-Path $run 'mock-bin'
    [IO.Directory]::CreateDirectory($mockBin) | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../release/fixtures/opencode.ps1') -Destination (Join-Path $mockBin 'opencode.ps1')
    $mockCommand = "@echo off`r`npwsh -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), $mockCommand, [Text.Encoding]::ASCII)
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $env:PATH
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeRoot
    Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue

    $openUserConfig = Join-Path $openCodeRoot 'opencode.json'
    # A user-owned V2 config with an ASK fallback and a later narrow DENY is
    # safe to preserve byte-for-byte; no manifest should claim ownership.
    $safeUserConfig = '{"user_owned":true,"permissions":[{"action":"external_directory","resource":"*","effect":"ask"},{"action":"external_directory","resource":"C:/fixture/prohibited/*","effect":"deny"}]}' + "`n"
    [IO.File]::WriteAllText($openUserConfig, $safeUserConfig, $utf8)
    $expectedOpenUserConfig = $safeUserConfig.Insert(1, '"default_agent":"kael",')

    # The existing project-local default stays project-scoped and records scope.
    $localInstall = Run-Installer $project @('-Harness','opencode')
    $localManifestPath = Join-Path $project '.opencode/orchestrator-install.json'
    $localManifest = Get-Content -LiteralPath $localManifestPath -Raw | ConvertFrom-Json
    Check 'PROJECT_SCOPE_OPENCODE_INSTALL' ($localInstall.Code -eq 0 -and $localManifest.scope -eq 'project' -and
        $localManifest.installed_version -eq $candidateVersion -and $localManifest.installed_harnesses.Count -eq 1 -and
        $localManifest.installed_harnesses[0] -eq 'opencode') `
        ("exit=$($localInstall.Code)`n$($localInstall.Text)")
    $projectBeforeVerify = Snapshot $project
    $projectVerify = Run-Installer $project @('-Harness','opencode','-VerifyOnly')
    Check 'PROJECT_VERIFYONLY_UNAFFECTED' ($projectVerify.Code -eq 0 -and (Snapshot $project) -ceq $projectBeforeVerify)

    $projectBeforeGlobalInstall = Snapshot $project
    $globalInstall = Global-Install $project 'opencode'
    Check 'GLOBAL_OPENCODE_INSTALL' ($globalInstall.Code -eq 0 -and
        $globalInstall.Text -match 'OLYMPUS_GLOBAL_INSTALL: OPENCODE .* READY') ("exit=$($globalInstall.Code)`n$($globalInstall.Text)")
    $capRoot = Join-Path $run 'cap-global'
    [IO.Directory]::CreateDirectory($capRoot) | Out-Null
    $capConfig = Join-Path $run 'cap-config.json'
    $previousCapRoot = $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT
    $previousConfigFile = $env:OLYMPUS_CONFIG_FILE
    try {
        $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $capRoot
        $env:OLYMPUS_CONFIG_FILE = $capConfig
        [IO.File]::WriteAllText($capConfig,
            '{"schema_version":1,"overrides":{},"orchestration":{"max_children":2}}' + "`n", $utf8)
        $capInstall = Global-Install $project 'opencode'
        $capAgent = Join-Path $capRoot 'agents/kael.md'
        $capManifest = Join-Path $capRoot 'olympus/orchestrator-install.json'
        $manifest = [IO.File]::ReadAllText($capManifest) | ConvertFrom-Json
        $kaelEntry = $manifest.managed_files | Where-Object { $_.path -ceq 'agents/kael.md' }
        Check 'GLOBAL_MAX_PARALLEL_INITIAL_INSTALL' (
            $capInstall.Code -eq 0 -and
            [IO.File]::ReadAllText($capAgent).Contains('MAX_ACTIVE_CHILDREN = 2') -and
            $kaelEntry.sha256 -ceq (Get-FileHash -LiteralPath $capAgent -Algorithm SHA256).Hash.ToLowerInvariant()
        ) ("exit=$($capInstall.Code)`n$($capInstall.Text)")

        [IO.File]::WriteAllText($capConfig,
            '{"schema_version":1,"overrides":{},"orchestration":{"max_children":1}}' + "`n", $utf8)
        $capUpdate = Run-Installer $project @('-Scope','global','-Harness','opencode','-Update')
        $beforeCapVerify = Snapshot $capRoot
        $capVerify = Global-Verify $project 'opencode'
        Check 'GLOBAL_MAX_PARALLEL_UPDATE_VERIFYONLY' (
            $capUpdate.Code -eq 0 -and
            [IO.File]::ReadAllText($capAgent).Contains('MAX_ACTIVE_CHILDREN = 1') -and
            $capVerify.Code -eq 0 -and $capVerify.Text -match 'OLYMPUS_GLOBAL_VERIFY: opencode' -and
            (Snapshot $capRoot) -ceq $beforeCapVerify
        ) ("update=$($capUpdate.Code)`n$($capUpdate.Text)`nverify=$($capVerify.Code)`n$($capVerify.Text)")

        [IO.File]::WriteAllText($capConfig,
            '{"schema_version":1,"overrides":{},"orchestration":{"max_children":true}}' + "`n", $utf8)
        $beforeInvalidCap = Snapshot $capRoot
        $invalidCap = Global-Install $project 'opencode'
        Check 'GLOBAL_MAX_PARALLEL_REJECTS_BOOLEAN_WITHOUT_WRITES' (
            $invalidCap.Code -ne 0 -and $invalidCap.Text -match 'USER_CONFIG_INVALID' -and
            (Snapshot $capRoot) -ceq $beforeInvalidCap
        ) ("exit=$($invalidCap.Code)`n$($invalidCap.Text)")

        $caseVariantConfig = '{"schema_version":1,"overrides":{},"Orchestration":{"max_children":2}}' + "`n"
        [IO.File]::WriteAllText($capConfig, $caseVariantConfig, $utf8)
        $beforeCaseVariant = Snapshot $capRoot
        $caseVariantInstall = Global-Install $project 'opencode'
        Check 'GLOBAL_USER_CONFIG_REJECTS_CASE_VARIANT_KEY_WITHOUT_WRITES' (
            $caseVariantInstall.Code -ne 0 -and
            $caseVariantInstall.Text -match 'USER_CONFIG_INVALID' -and
            (Snapshot $capRoot) -ceq $beforeCaseVariant -and
            [IO.File]::ReadAllText($capConfig) -ceq $caseVariantConfig
        ) ("exit=$($caseVariantInstall.Code)`n$($caseVariantInstall.Text)")
    } finally {
        $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $previousCapRoot
        $env:OLYMPUS_CONFIG_FILE = $previousConfigFile
    }
    Check 'GLOBAL_PROJECT_OVERRIDE_RETAINED' ($globalInstall.Text -match 'GLOBAL_INSTALLED PROJECT_LOCAL_REMAINS_AS_OVERRIDE' -and
        $globalInstall.Text -match 'PROJECT_LOCAL_OVERRIDE: opencode' -and
        (Snapshot $project) -ceq $projectBeforeGlobalInstall) ("exit=$($globalInstall.Code)`n$($globalInstall.Text)`nPROJECT_SNAPSHOT_UNCHANGED=$((Snapshot $project) -ceq $projectBeforeGlobalInstall)")
    Check 'GLOBAL_OPENCODE_CONTEXTUAL_KAEL_ROSTER' ((Test-Path (Join-Path $openCodeRoot 'agents/kael.md')) -and
        (Test-Path (Join-Path $openCodeRoot 'plugins/olympus-activity/activity.ts')) -and
        -not (Test-Path (Join-Path $openCodeRoot 'agents/aegis.md')) -and
        -not (Test-Path (Join-Path $openCodeRoot 'commands/maintain.md')))
    Check 'GLOBAL_USER_CONFIG_PROTECTED' ([IO.File]::ReadAllText($openUserConfig) -ceq $expectedOpenUserConfig -and
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
        # Keep stable-lock initialization out of the rejection-side snapshot.
        [IO.File]::WriteAllBytes((Join-Path $unsafeRoot '.olympus-cli-edit.lock'), [byte[]]::new(0))
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
        [IO.File]::ReadAllText($safeBroadFile) -ceq $safeBroadText.Insert(1, '"default_agent":"kael",') -and
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
        $null -ne $denyManifest -and $denyManifest.schema_version -eq 1 -and $denyManifest.scope -ceq 'global' -and
        @($denyManifest.installed_harnesses).Count -eq 1 -and $denyManifest.installed_harnesses[0] -ceq 'opencode' -and
        -not [string]::IsNullOrWhiteSpace([string]$denyManifest.installed_version) -and
        -not [string]::IsNullOrWhiteSpace([string]$denyManifest.installed_from_commit) -and
        $denyManifest.managed_files.Count -eq 14 -and
        @($denyManifest.managed_files | Where-Object { [string]$_.sha256 -notmatch '^(?i:[0-9a-f]{64})$' }).Count -eq 0 -and
        $denyManifest.default_agent_receipt.state -ceq 'committed' -and
        @($denyManifest.managed_files | Where-Object { $_.path -eq 'opencode.jsonc' }).Count -eq 0 -and
        [IO.File]::ReadAllText($userDenyPath) -ceq $userDenyText.Insert($userDenyText.IndexOf('"permissions"'), '"default_agent":"kael",')
    ) ("exit=$($denyInstall.Code)`n$($denyInstall.Text)")
    # A 14-resource current install is valid only with its user-config receipt.
    $userDenyManifestPath = Join-Path $userDenyRoot 'olympus/orchestrator-install.json'
    $userDenyManifestBytes = [IO.File]::ReadAllBytes($userDenyManifestPath)
    [void]$denyManifest.PSObject.Properties.Remove('default_agent_receipt')
    [IO.File]::WriteAllText($userDenyManifestPath, ($denyManifest | ConvertTo-Json -Depth 20), $utf8)
    $missingReceiptBefore = Snapshot $userDenyRoot
    $missingReceiptInstall = Global-Install $project 'opencode'
    $missingReceiptVerify = Global-Verify $project 'opencode'
    Check 'GLOBAL_14_RESOURCE_MANIFEST_REQUIRES_RECEIPT_READONLY' (
        $missingReceiptInstall.Code -ne 0 -and
        $missingReceiptInstall.Text -match 'GLOBAL_DEFAULT_AGENT_RECEIPT_MISSING' -and
        $missingReceiptVerify.Code -ne 0 -and
        $missingReceiptVerify.Text -match 'GLOBAL_DEFAULT_AGENT_RECEIPT_MISSING' -and
        $missingReceiptVerify.Text -match 'Uninstall it with the Olympus version that created this installation, then install the current version' -and
        (Snapshot $userDenyRoot) -ceq $missingReceiptBefore
    ) ("exit=$($missingReceiptInstall.Code)`n$($missingReceiptInstall.Text)")
    [IO.File]::WriteAllBytes($userDenyManifestPath, $userDenyManifestBytes)

    foreach ($selector in @('codex','all')) {
        $unsupportedBefore = Snapshot $userDenyRoot
        $unsupported = Global-Install $project $selector
        Check ('GLOBAL_UNSUPPORTED_SELECTOR_' + $selector.ToUpperInvariant() + '_NO_WRITES') (
            $unsupported.Code -ne 0 -and (Snapshot $userDenyRoot) -ceq $unsupportedBefore
        ) ("exit=$($unsupported.Code)`n$($unsupported.Text)")
    }
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeRoot

    # Qualify the sole current OpenCode global selector.
    $openCodeOnlyRoot = Join-Path $run 'OpenCode Only Global Config'
    [IO.Directory]::CreateDirectory($openCodeOnlyRoot) | Out-Null
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeOnlyRoot
    $openCodeOnly = Run-Installer $project @('-Scope','global','-Harness','opencode')
    $openCodeOnlyManifest = Get-Content (Join-Path $openCodeOnlyRoot 'olympus/orchestrator-install.json') -Raw | ConvertFrom-Json
    $requiredGlobalCommands = @(
        'commands/olympus.ultra.md',
        'commands/olympus.performance.md',
        'commands/olympus.performance-ultra.md'
    )
    $expectedGlobalPaths = @(
        'agents/kael.md', 'agents/atlas.md', 'agents/veyra.md', 'agents/kovan.md',
        'agents/nox.md', 'agents/vera.md', 'agents/helios.md', 'agents/talos.md', 'agents/thales.md',
        'plugins/olympus-activity/activity.ts', 'plugins/olympus-activity/tui.tsx'
    ) + $requiredGlobalCommands
    Check 'GLOBAL_OPENCODE_ONLY_SELECTOR' ($openCodeOnly.Code -eq 0 -and $openCodeOnlyManifest.schema_version -eq 1 -and
        $openCodeOnlyManifest.scope -ceq 'global' -and $openCodeOnlyManifest.installed_harnesses.Count -eq 1 -and
        $openCodeOnlyManifest.installed_harnesses[0] -ceq 'opencode' -and
        -not [string]::IsNullOrWhiteSpace([string]$openCodeOnlyManifest.installed_version) -and
        -not [string]::IsNullOrWhiteSpace([string]$openCodeOnlyManifest.installed_from_commit) -and
        $openCodeOnlyManifest.managed_files.Count -eq 15 -and
        @($openCodeOnlyManifest.managed_files | Where-Object { [string]$_.sha256 -notmatch '^(?i:[0-9a-f]{64})$' }).Count -eq 0 -and
        $openCodeOnlyManifest.default_agent_receipt.state -ceq 'committed' -and
        [string]::Join("`n", @($openCodeOnlyManifest.managed_files | ForEach-Object { $_.path } | Sort-Object)) -ceq
            [string]::Join("`n", @($expectedGlobalPaths + 'opencode.jsonc' | Sort-Object)))
    $managedGlobalCommands = @($openCodeOnlyManifest.managed_files |
        Where-Object { $_.path -in $requiredGlobalCommands })
    Check 'GLOBAL_NAMESPACED_COMMANDS_ARE_MANAGED' (
        $managedGlobalCommands.Count -eq 3 -and
        @($requiredGlobalCommands | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $openCodeOnlyRoot $_) -PathType Leaf)
        }).Count -eq 0 -and (Global-Verify $project 'opencode').Code -eq 0
    )
    $ownedGuardPath = Join-Path $openCodeOnlyRoot 'opencode.jsonc'
    Check 'GLOBAL_ONLY_EXTERNAL_ASK_MANAGED' (
        (Get-ExternalFallback $ownedGuardPath) -eq 'ask' -and
        @($openCodeOnlyManifest.managed_files | Where-Object { $_.path -eq 'opencode.jsonc' }).Count -eq 1 -and
        (Global-Verify $project 'opencode').Code -eq 0
    )
    $legacyRoot = Join-Path $run 'OpenCode v0.10.0 Inventory Refused'
    [IO.Directory]::CreateDirectory($legacyRoot) | Out-Null
    Copy-Item -Path (Join-Path $openCodeOnlyRoot '*') -Destination $legacyRoot -Recurse
    $legacyManifestPath = Join-Path $legacyRoot 'olympus/orchestrator-install.json'
    $legacyManifest = Get-Content -LiteralPath $legacyManifestPath -Raw | ConvertFrom-Json
    $legacyManifest.installed_version = 'v0.10.0'
    $legacyManifest.managed_files = @($legacyManifest.managed_files | Where-Object {
        $_.path -notin $requiredGlobalCommands
    })
    foreach ($commandPath in $requiredGlobalCommands) {
        [IO.File]::Delete((Join-Path $legacyRoot $commandPath))
    }
    [IO.File]::WriteAllText($legacyManifestPath, ($legacyManifest | ConvertTo-Json -Depth 30), $utf8)
    $legacyLockPath = Join-Path $legacyRoot '.olympus-cli-edit.lock'
    if (Test-Path -LiteralPath $legacyLockPath) { [IO.File]::Delete($legacyLockPath) }
    $beforeLegacy = Snapshot $legacyRoot
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $legacyRoot
    foreach ($operation in @('Install','Update','Force','Uninstall','VerifyOnly')) {
        $arguments = @('-Scope','global','-Harness','opencode')
        if ($operation -ne 'Install') { $arguments += ('-' + $operation) }
        $rejected = Run-Installer $project $arguments
        Check ('GLOBAL_V010_' + $operation.ToUpperInvariant() + '_REFUSED_BEFORE_LOCK') (
            $rejected.Code -ne 0 -and $rejected.Text -match 'GLOBAL_MANIFEST_INVALID' -and
            $rejected.Text -match 'Uninstall it with the Olympus version that created this installation, then install the current version' -and
            (Snapshot $legacyRoot) -ceq $beforeLegacy -and
            -not (Test-Path -LiteralPath $legacyLockPath)
        ) ("operation=$operation; exit=$($rejected.Code)`n$($rejected.Text)")
    }
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeOnlyRoot
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
    $defaultGuardText = $guardSourceText.Insert($guardSourceText.IndexOf('{') + 1, "`n  `"default_agent`": `"kael`",")
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
        $recoverManifest.managed_files.Count -eq 15 -and
        @($recoverManifest.managed_files | Where-Object { $_.path -eq 'opencode.jsonc' }).Count -eq 1 -and
        [IO.File]::ReadAllText($recoverGuardPath) -ceq $defaultGuardText -and
        -not (Test-Path -LiteralPath $recoverIntentPath) -and
        (Global-Verify $project 'opencode').Code -eq 0
    ) ("exit=$($recoverInstall.Code)`n$($recoverInstall.Text)")

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
        [IO.File]::ReadAllText((Join-Path $intentOnlyRoot 'opencode.jsonc')) -ceq $defaultGuardText
    ) ("exit=$($intentOnlyInstall.Code)`n$($intentOnlyInstall.Text)")

    # An altered guard with the same pending marker cannot be adopted. A
    # failed recovery must leave the caller's current bytes untouched.
    $recoverConflictRoot = Join-Path $run 'OpenCode Guard Interrupted Conflict'
    [IO.Directory]::CreateDirectory((Join-Path $recoverConflictRoot 'olympus')) | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $recoverConflictRoot '.olympus-cli-edit.lock'), [byte[]]::new(0))
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
    [IO.File]::WriteAllBytes((Join-Path $doubleConfigRoot '.olympus-cli-edit.lock'), [byte[]]::new(0))
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

    # An old expanded inventory is rejected as a whole; obsolete files are not
    # automatically adopted, converted, or deleted.
    $obsoleteRoot = Join-Path $run 'OpenCode Obsolete Inventory Refused'
    [IO.Directory]::CreateDirectory($obsoleteRoot) | Out-Null
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $obsoleteRoot
    $obsoleteSeed = Global-Install $project 'opencode'
    if ($obsoleteSeed.Code -ne 0) { throw "Obsolete inventory fixture install failed: $($obsoleteSeed.Text)" }
    $obsoleteManifestPath = Join-Path $obsoleteRoot 'olympus/orchestrator-install.json'
    $obsoleteManifest = Get-Content -LiteralPath $obsoleteManifestPath -Raw | ConvertFrom-Json
    foreach ($entry in @(
        @{ path='agents/aegis.md'; text="historical generated agent`n" },
        @{ path='commands/maintain.md'; text="historical generated command`n" }
    )) {
        $obsoleteFile = Join-Path $obsoleteRoot $entry.path
        [IO.Directory]::CreateDirectory((Split-Path -Parent $obsoleteFile)) | Out-Null
        [IO.File]::WriteAllText($obsoleteFile, $entry.text, $utf8)
        $obsoleteManifest.managed_files += [pscustomobject]@{
            path=$entry.path
            sha256=(Get-FileHash -LiteralPath $obsoleteFile -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    [IO.File]::WriteAllText($obsoleteManifestPath, (($obsoleteManifest | ConvertTo-Json -Depth 20) + "`n"), $utf8)
    $obsoleteBefore = Snapshot $obsoleteRoot
    $obsoleteUpdate = Global-Install $project 'opencode'
    Check 'GLOBAL_OLD_INVENTORY_REFUSED_WITHOUT_CLEANUP' ($obsoleteUpdate.Code -ne 0 -and
        $obsoleteUpdate.Text -match 'GLOBAL_MANIFEST_INVALID' -and
        (Snapshot $obsoleteRoot) -ceq $obsoleteBefore -and
        (Test-Path (Join-Path $obsoleteRoot 'agents/aegis.md')) -and
        (Test-Path (Join-Path $obsoleteRoot 'commands/maintain.md')))
    $obsoleteForce = Run-Installer $project @('-Scope','global','-Harness','opencode','-Force')
    Check 'GLOBAL_FORCE_DOES_NOT_BYPASS_EXACT_INVENTORY' (
        $obsoleteForce.Code -ne 0 -and $obsoleteForce.Text -match 'GLOBAL_MANIFEST_INVALID' -and
        (Snapshot $obsoleteRoot) -ceq $obsoleteBefore
    ) ("exit=$($obsoleteForce.Code)`n$($obsoleteForce.Text)")

    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeOnlyRoot
    $openCodeOnlyManifestPath = Join-Path $openCodeOnlyRoot 'olympus/orchestrator-install.json'
    $ownedGuardUninstall = Run-Installer $project @('-Scope','global','-Harness','opencode','-Uninstall')
    Check 'GLOBAL_OWNED_ONLY_GUARD_REMOVED_ON_UNINSTALL' (
        $ownedGuardUninstall.Code -eq 0 -and
        -not (Test-Path $ownedGuardPath) -and
        -not (Test-Path $openCodeOnlyManifestPath)
    )

    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $openCodeRoot
    $openManifestPath = Join-Path $openCodeRoot 'olympus/orchestrator-install.json'
    $openManifestText = [IO.File]::ReadAllText($openManifestPath)
    $openManifest = $openManifestText | ConvertFrom-Json
    Check 'GLOBAL_USER_CONFIG_MANIFEST_CURRENT_14_RESOURCE_FORM' (
        $openManifest.schema_version -eq 1 -and $openManifest.scope -ceq 'global' -and
        @($openManifest.installed_harnesses).Count -eq 1 -and $openManifest.installed_harnesses[0] -ceq 'opencode' -and
        -not [string]::IsNullOrWhiteSpace([string]$openManifest.installed_version) -and
        -not [string]::IsNullOrWhiteSpace([string]$openManifest.installed_from_commit) -and
        $openManifest.managed_files.Count -eq 14 -and
        @($openManifest.managed_files | Where-Object { [string]$_.sha256 -notmatch '^(?i:[0-9a-f]{64})$' }).Count -eq 0 -and
        $openManifest.default_agent_receipt.state -ceq 'committed' -and
        (Test-Path -LiteralPath $openUserConfig) -and
        -not (Test-Path -LiteralPath (Join-Path $openCodeRoot 'opencode.jsonc'))
    )

    $openBeforeVerify = Snapshot $openCodeRoot
    $verify = Global-Verify $project 'opencode'
    Check 'GLOBAL_VERIFYONLY_OPENCODE_READONLY' ($verify.Code -eq 0 -and
        $verify.Text -match 'OLYMPUS_GLOBAL_VERIFY: opencode' -and (Snapshot $openCodeRoot) -ceq $openBeforeVerify)
    foreach ($selector in @('codex','all')) {
        $unsupported = Global-Verify $project $selector
        Check ('GLOBAL_VERIFYONLY_REJECTS_' + $selector.ToUpperInvariant()) (
            $unsupported.Code -ne 0 -and (Snapshot $openCodeRoot) -ceq $openBeforeVerify
        ) ("exit=$($unsupported.Code)`n$($unsupported.Text)")
    }
    $openManifestBytes = [IO.File]::ReadAllBytes($openManifestPath)
    [IO.File]::Delete($openManifestPath)
    $missingManifestBefore = Snapshot $openCodeRoot
    $missingManifestVerify = Global-Verify $project 'opencode'
    Check 'GLOBAL_VERIFYONLY_MISSING_MANIFEST_REJECTED_READONLY' ($missingManifestVerify.Code -ne 0 -and
        $missingManifestVerify.Text -match 'GLOBAL_MANIFEST_MISSING' -and
        (Snapshot $openCodeRoot) -ceq $missingManifestBefore)
    [IO.File]::WriteAllBytes($openManifestPath, $openManifestBytes)

    # Global update remains hash-owned and preserves the project override and user config.
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
    Check 'GLOBAL_MANAGED_DRIFT_DETECTED' ($openDrift.Code -ne 0 -and $openDrift.Text -match 'GLOBAL_MANAGED_FILE_DRIFT')
    [IO.File]::WriteAllText($openAgentPath, $openAgentBefore, $utf8)

    $missingAgentPath = Join-Path $openCodeRoot 'agents/nox.md'
    $openUserConfigBeforeForce = [IO.File]::ReadAllBytes($openUserConfig)
    $userNotePath = Join-Path $openCodeRoot 'user-note.txt'
    [IO.File]::WriteAllText($userNotePath, 'preserve during force repair', $utf8)
    $forceManifest = [IO.File]::ReadAllText($openManifestPath) | ConvertFrom-Json -Depth 20
    $forceManifest.installed_version = 'v0.3.0-beta.4'
    [IO.File]::WriteAllText($openManifestPath, (($forceManifest | ConvertTo-Json -Depth 20) + "`n"), $utf8)
    $manifestDaclBeforeForce = Set-ProtectedFixtureDacl $openManifestPath
    $manifestBytesBeforeFault = [IO.File]::ReadAllBytes($openManifestPath)
    $cliPointerPath = Join-Path $cliInstallRoot 'current.txt'
    $cliPointerBytesBeforeFault = [IO.File]::ReadAllBytes($cliPointerPath)
    $cliManifestPath = Join-Path $cliInstallRoot "versions/$candidateVersion/olympus-cli-manifest.json"
    $cliManifestBytesBeforeFault = [IO.File]::ReadAllBytes($cliManifestPath)

    $agentDaclBeforeForce = Set-ProtectedFixtureDacl $openAgentPath
    $hardLinkAlias = Join-Path $run 'unowned-managed-agent-hardlink.md'
    New-Item -ItemType HardLink -Path $hardLinkAlias -Target $openAgentPath -ErrorAction Stop | Out-Null
    [IO.File]::AppendAllText($openAgentPath, "`n# qualification force drift`n", $utf8)
    $hardLinkBytesBeforeForce = [IO.File]::ReadAllBytes($hardLinkAlias)
    $hardLinkDaclBeforeForce = Get-AccessDaclSnapshot $hardLinkAlias
    [IO.File]::Delete($missingAgentPath)
    $beforeNonForceRepair = Snapshot $openCodeRoot
    $nonForceRepair = Run-Installer $project @('-Scope','global','-Harness','opencode','-Update')
    Check 'GLOBAL_NONFORCE_UPDATE_PRESERVES_CHANGED_AND_MISSING_RESOURCES' (
            $nonForceRepair.Code -ne 0 -and $nonForceRepair.Text -match 'GLOBAL_MANAGED_FILE_DRIFT' -and
            (Snapshot $openCodeRoot) -ceq $beforeNonForceRepair
    ) ("exit=$($nonForceRepair.Code)`n$($nonForceRepair.Text)")

    $faultRoot = Join-Path $run 'force-interruption-source'
    $faultScripts = Join-Path $faultRoot 'scripts'
    [IO.Directory]::CreateDirectory($faultRoot) | Out-Null
    foreach ($relative in @('olympus','.opencode')) {
        Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $faultRoot -Recurse
    }
    Copy-Item -LiteralPath (Join-Path $source 'scripts') -Destination $faultRoot -Recurse
    Copy-Item -LiteralPath (Join-Path $source 'opencode.jsonc') -Destination $faultRoot
    $faultWriterPath = Join-Path $faultScripts 'global-install.ps1'
    $faultWriterText = [IO.File]::ReadAllText($globalInstaller)
    $faultAnchor = 'Write-GlobalResource $destination ([string]$outputs[$relative])'
    if (($faultWriterText.Split(@($faultAnchor), [StringSplitOptions]::None).Count - 1) -ne 1) {
        throw 'FORCE_INTERRUPTION_FIXTURE_ANCHOR_INVALID'
    }
    $faultNewline = if ($faultWriterText.Contains("`r`n")) { "`r`n" } else { "`n" }
    $faultInjection = $faultAnchor + $faultNewline +
        "            if (`$env:OLYMPUS_GLOBAL_FAIL_AFTER_MANAGED_WRITE -ceq '1') { throw 'QUALIFICATION_INTERRUPTED_AFTER_MANAGED_WRITE' }"
    $faultWriterText = $faultWriterText.Replace($faultAnchor, $faultInjection)
    [IO.File]::WriteAllText($faultWriterPath, $faultWriterText, $utf8)
    $previousOpenCodeRoot = $env:OPENCODE_CONFIG_DIR
    $previousFaultSwitch = $env:OLYMPUS_GLOBAL_FAIL_AFTER_MANAGED_WRITE
    $previousPreference = $ErrorActionPreference
    try {
        $env:OPENCODE_CONFIG_DIR = $openCodeRoot
        $env:OLYMPUS_GLOBAL_FAIL_AFTER_MANAGED_WRITE = '1'
        $ErrorActionPreference = 'Continue'
        $faultOutput = (& pwsh -NoProfile -File $faultWriterPath -Harness opencode `
            -SourceVersion $candidateVersion -ProjectTarget $project -Update -Force 2>&1 | Out-String)
        $faultCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
        if ($null -eq $previousOpenCodeRoot) { Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue }
        else { $env:OPENCODE_CONFIG_DIR = $previousOpenCodeRoot }
        if ($null -eq $previousFaultSwitch) { Remove-Item Env:OLYMPUS_GLOBAL_FAIL_AFTER_MANAGED_WRITE -ErrorAction SilentlyContinue }
        else { $env:OLYMPUS_GLOBAL_FAIL_AFTER_MANAGED_WRITE = $previousFaultSwitch }
    }
    $manifestAfterFault = [IO.File]::ReadAllBytes($openManifestPath)
    $cliManifestAfterFault = [IO.File]::ReadAllBytes($cliManifestPath)
    $cliPointerAfterFault = [IO.File]::ReadAllBytes($cliPointerPath)
    $hardLinkDaclAfterFault = Get-AccessDaclSnapshot $hardLinkAlias
    Check 'GLOBAL_FORCE_INTERRUPTION_AFTER_WRITE_RETAINS_RECEIPT_AND_RETRY_STATE' (
        $faultCode -ne 0 -and $faultOutput -match 'QUALIFICATION_INTERRUPTED_AFTER_MANAGED_WRITE' -and
        [Convert]::ToBase64String($manifestBytesBeforeFault) -ceq [Convert]::ToBase64String($manifestAfterFault) -and
        [Convert]::ToBase64String($cliManifestBytesBeforeFault) -ceq [Convert]::ToBase64String($cliManifestAfterFault) -and
        [Convert]::ToBase64String($cliPointerBytesBeforeFault) -ceq [Convert]::ToBase64String($cliPointerAfterFault) -and
        [IO.File]::ReadAllText($openAgentPath) -ceq [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/kael.md')) -and
        -not (Test-Path -LiteralPath $missingAgentPath) -and
        [Convert]::ToBase64String($hardLinkBytesBeforeForce) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($hardLinkAlias)) -and
        $hardLinkDaclAfterFault.Sddl -ceq $hardLinkDaclBeforeForce.Sddl -and
        [Convert]::ToBase64String($openUserConfigBeforeForce) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($openUserConfig))
    ) ("exit=$faultCode`n$faultOutput")

    $forceRepair = Run-Installer $project @('-Scope','global','-Harness','opencode','-Update','-Force')
    $manifestAfterForce = if (Test-Path -LiteralPath $openManifestPath) {
        [IO.File]::ReadAllText($openManifestPath) | ConvertFrom-Json -Depth 20
    } else { $null }
    $allManagedHashesMatch = $null -ne $manifestAfterForce -and @($manifestAfterForce.managed_files | Where-Object {
        $managedPath = Join-Path $openCodeRoot ($_.path -replace '/', [IO.Path]::DirectorySeparatorChar)
        -not (Test-Path -LiteralPath $managedPath -PathType Leaf) -or
        (Get-FileHash -LiteralPath $managedPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne [string]$_.sha256
    }).Count -eq 0
    Check 'GLOBAL_FORCE_REPAIRS_RECEIPTED_DRIFT_AND_PRESERVES_USER_STATE' (
        $forceRepair.Code -eq 0 -and
        [IO.File]::ReadAllText($openAgentPath) -ceq
            [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/kael.md')) -and
        [IO.File]::ReadAllText($missingAgentPath) -ceq
            [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/nox.md')) -and
        [Convert]::ToBase64String($openUserConfigBeforeForce) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($openUserConfig)) -and
        [IO.File]::ReadAllText($userNotePath) -ceq 'preserve during force repair' -and
        $null -ne $manifestAfterForce -and
        $manifestAfterForce.installed_version -ceq $candidateVersion -and
        $allManagedHashesMatch -and
        (Get-AccessDaclSnapshot $openManifestPath).Sddl -ceq $manifestDaclBeforeForce.Sddl -and
        (Get-AccessDaclSnapshot $openManifestPath).Protected -and
        (Get-AccessDaclSnapshot $openAgentPath).Sddl -ceq $agentDaclBeforeForce.Sddl -and
        [Convert]::ToBase64String($hardLinkBytesBeforeForce) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($hardLinkAlias)) -and
        (Get-AccessDaclSnapshot $hardLinkAlias).Sddl -ceq $hardLinkDaclBeforeForce.Sddl -and
        [Convert]::ToBase64String($cliPointerBytesBeforeFault) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($cliPointerPath)) -and
        (Global-Verify $project 'opencode').Code -eq 0
    ) ("exit=$($forceRepair.Code)`n$($forceRepair.Text)")

    # Uninstall removes only manifest-owned resources, keeping unrelated global state.
    [IO.File]::WriteAllText($userNotePath, 'preserve', $utf8)
    $uninstall = Run-Installer $project @('-Scope','global','-Harness','opencode','-Uninstall')
    Check 'GLOBAL_UNINSTALL_ONLY_OWNED_RESOURCES' ($uninstall.Code -eq 0 -and
        -not (Test-Path (Join-Path $openCodeRoot 'agents/kael.md')) -and
        -not (Test-Path $openManifestPath) -and
        (Test-Path $openUserConfig) -and
        (Test-Path (Join-Path $openCodeRoot 'user-note.txt')) -and
        (Snapshot $project) -ceq $projectBeforeGlobalInstall)
    Write-Output 'GLOBAL INSTALLER QUALIFICATION: PASS (isolated fixture roots; no real HOME writes or interactive harness session)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'GLOBAL INSTALLER QUALIFICATION: FAIL'
    exit 1
} finally {
    if ($null -ne $isolatedEnvironment) { Exit-OlympusInstallerTestEnvironment $isolatedEnvironment }
    $env:PATH = $originalPath
    if ($null -eq $originalOpenCodeRoot) { Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue }
    else { $env:OPENCODE_CONFIG_DIR = $originalOpenCodeRoot }
    if ($null -eq $originalFixtureOpenCodeRoot) { Remove-Item Env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT -ErrorAction SilentlyContinue }
    else { $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $originalFixtureOpenCodeRoot }
    if ($null -eq $originalOlympusConfigFile) { Remove-Item Env:OLYMPUS_CONFIG_FILE -ErrorAction SilentlyContinue }
    else { $env:OLYMPUS_CONFIG_FILE = $originalOlympusConfigFile }
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
