[CmdletBinding()]
param(
    [switch]$Child,
    [switch]$MockLatest,
    [string]$Action,
    [string]$Scope,
    [string]$Harness,
    [string]$Target,
    [string]$Version,
    [switch]$DryRun,
    [switch]$Update,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Utf8NoBom = [Text.UTF8Encoding]::new($false)

function Assert([string]$Name, [bool]$Condition, [string]$Evidence = '') {
    if (-not $Condition) { throw "$Name FAIL`n$Evidence" }
    Write-Output "$Name PASS"
}

function Invoke-PowerShell([string[]]$Arguments) {
    $output = (& $script:Pwsh -NoProfile -NonInteractive @Arguments 2>&1 | Out-String)
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "POWERSHELL_FAILED: exit=$code`n$output" }
    return $output
}

function Invoke-PowerShellResult([string[]]$Arguments) {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = (& $script:Pwsh -NoProfile -NonInteractive @Arguments 2>&1 | Out-String)
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    return [pscustomobject]@{ Text=$output; Code=$code }
}

function Invoke-Olympus([string]$Name, [string[]]$CommandArguments, [string]$Expected) {
    $output = (& olympus @CommandArguments 2>&1 | Out-String)
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "CLI_FAILED: $Name exit=$code`n$output" }
    if ($Expected -and $output.TrimEnd() -notmatch $Expected) { throw "CLI_OUTPUT_MISMATCH: $Name`n$output" }
    Write-Host "CLI $Name PASS"
    return $output
}

function Invoke-OlympusFailure([string]$Name, [string[]]$CommandArguments, [int]$ExpectedExitCode, [string]$Expected) {
    $output = (& olympus @CommandArguments 2>&1 | Out-String)
    $code = $LASTEXITCODE
    if ($code -ne $ExpectedExitCode -or $output -notmatch $Expected) {
        throw "CLI_FAILURE_MISMATCH: $Name exit=$code expected=$ExpectedExitCode`n$output"
    }
    Write-Host "CLI $Name PASS"
    return $output
}

function Get-TreeSnapshot([string]$Root) {
    $prefix = $Root.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
    return @(Get-ChildItem -LiteralPath $Root -File -Recurse -Force | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring($prefix.Length).Replace('\','/')
        "$relative=$((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash)"
    })
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

$script:Pwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source

if ($MockLatest) {
    function global:Invoke-RestMethod {
        [CmdletBinding()]
        param([string]$Uri, [hashtable]$Headers)
        [IO.File]::AppendAllText($env:OLYMPUS_SMOKE_REQUEST_LOG, "metadata $Uri`n", [Text.UTF8Encoding]::new($false))
        if ($Uri -cne $env:OLYMPUS_SMOKE_METADATA_URI) { throw "Unexpected metadata request blocked: $Uri" }
        if ($env:OLYMPUS_SMOKE_METADATA_FAIL -eq '1') { throw 'SMOKE_METADATA_UNAVAILABLE' }
        return [IO.File]::ReadAllText($env:OLYMPUS_SMOKE_METADATA_FIXTURE) | ConvertFrom-Json -Depth 20 -ErrorAction Stop
    }

    function global:Invoke-WebRequest {
        [CmdletBinding()]
        param([string]$Uri, [string]$OutFile, [hashtable]$Headers)
        [IO.File]::AppendAllText($env:OLYMPUS_SMOKE_REQUEST_LOG, "installer $Uri`n", [Text.UTF8Encoding]::new($false))
        $expected = $env:OLYMPUS_SMOKE_RAW_BASE + '/' + $env:OLYMPUS_SMOKE_RELEASE_VERSION + '/install.ps1'
        if ($Uri -cne $expected) { throw "Unexpected installer request blocked: $Uri" }
        [IO.File]::Copy($env:OLYMPUS_SMOKE_RELEASE_INSTALLER, $OutFile, $true)
    }

    if (-not $env:OLYMPUS_SMOKE_LAUNCHER) { throw 'SMOKE_LAUNCHER_MISSING' }
    $launchArguments = @{}
    foreach ($name in @('Action', 'DryRun', 'Update', 'Force')) {
        if ($PSBoundParameters.ContainsKey($name)) { $launchArguments[$name] = $PSBoundParameters[$name] }
    }
    if ($PSBoundParameters.ContainsKey('Verbose')) { $launchArguments['Verbose'] = $true }
    & $env:OLYMPUS_SMOKE_LAUNCHER @launchArguments
    exit $LASTEXITCODE
}

if ($Child) {
    Set-Location -LiteralPath $env:OLYMPUS_SMOKE_OTHER_DIR
    Assert 'CHILD_CWD_ISOLATED' ((Get-Location).Path -ceq $env:OLYMPUS_SMOKE_OTHER_DIR)
    Assert 'ISOLATED_LAUNCHER_RESOLVES' ((Get-Command olympus -CommandType Application -ErrorAction Stop).Source -ieq $env:OLYMPUS_SMOKE_LAUNCHER_PATH)

    [void](Invoke-Olympus 'version-before-update' @('version') '^olympus v[0-9]+\.[0-9]+\.[0-9]+$')
    [void](Invoke-Olympus 'help' @('help') 'Olympus global CLI')
    [void](Invoke-Olympus 'agents-list' @('agents', 'list') '(?m)^[ \t]+nox[ \t]+openai/gpt-6-luna[ \t]+max[ \t]+canonical default\r?$')
    [void](Invoke-Olympus 'nox-set-model' @('nox', 'set-model', 'openai/gpt-6.1-sol') 'openai/gpt-6\.1-sol')
    [void](Invoke-Olympus 'nox-set-effort' @('nox', 'set-effort', 'high') 'high')
    [void](Invoke-Olympus 'config-list' @('config', 'list') 'Run ''olympus doctor'' after manual edits\.')

    $oldPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
    $oldHook = [Environment]::GetEnvironmentVariable('OLYMPUS_SMOKE_UPDATE_HOOK', 'Process')
    $manifestDaclBeforeStableUpdate = Get-AccessDaclSnapshot $env:OLYMPUS_SMOKE_GLOBAL_MANIFEST
    try {
        $env:PYTHONPATH = $env:OLYMPUS_SMOKE_HOOK_DIR
        $env:OLYMPUS_SMOKE_UPDATE_HOOK = '1'
        $updateOutput = Invoke-Olympus 'stable-update' @('update') ("Updated to " + [regex]::Escape($env:OLYMPUS_SMOKE_RELEASE_VERSION) + '\.')
        Assert 'UPDATE_PROGRESS_AND_RESULT_VISIBLE' (
            $updateOutput.Contains('Checking for updates...') -and
            $updateOutput.Contains("Updating Olympus from") -and
            $updateOutput.Contains("Updated to $($env:OLYMPUS_SMOKE_RELEASE_VERSION).")
        )
        Assert 'UPDATE_DEFAULT_OUTPUT_IS_CONCISE' (
            $updateOutput -notmatch '(?m)^OLYMPUS_(SOURCE|RELEASE_SELECTED|ENTRYPOINT|RELEASE_EXECUTING|RELEASE_EXECUTED|GLOBAL_INSTALL|CLI|CLI_PATH):' -and
            $updateOutput -match 'GLOBAL_DEFAULT_AGENT:'
        ) $updateOutput
        Assert 'STABLE_UPDATE_PRESERVES_PROTECTED_MANIFEST_DACL' (
            (Get-AccessDaclSnapshot $env:OLYMPUS_SMOKE_GLOBAL_MANIFEST).Sddl -ceq
                $manifestDaclBeforeStableUpdate.Sddl
        )
    } finally {
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $oldPythonPath, 'Process')
        [Environment]::SetEnvironmentVariable('OLYMPUS_SMOKE_UPDATE_HOOK', $oldHook, 'Process')
    }

    [void](Invoke-Olympus 'version-after-update' @('version') ("^olympus " + [regex]::Escape($env:OLYMPUS_SMOKE_RELEASE_VERSION) + '$'))
    [void](Invoke-Olympus 'agents-list-after-update' @('agents', 'list') '(?m)^[ \t]+nox[ \t]+openai/gpt-6\.1-sol[ \t]+high[ \t]+global override\r?$')
    [void](Invoke-Olympus 'doctor' @('doctor') 'doctor: ok')

    $globalBeforeNoOp = @(Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)
    $cliBeforeNoOp = @(Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)
    $requestCountBeforeNoOp = @([IO.File]::ReadAllText($env:OLYMPUS_SMOKE_REQUEST_LOG) -split "`n" |
        Where-Object { $_ }).Count
    try {
        $env:PYTHONPATH = $env:OLYMPUS_SMOKE_HOOK_DIR
        $env:OLYMPUS_SMOKE_UPDATE_HOOK = '1'
        $sameVersionResult = "Already up to date ($($env:OLYMPUS_SMOKE_RELEASE_VERSION))."
        $defaultNoOp = Invoke-Olympus 'same-version-update-1' @('update') ([regex]::Escape($sameVersionResult))
        $verboseNoOp = Invoke-Olympus 'same-version-update-2' @('update', '--verbose') ([regex]::Escape($sameVersionResult))
    } finally {
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $oldPythonPath, 'Process')
        [Environment]::SetEnvironmentVariable('OLYMPUS_SMOKE_UPDATE_HOOK', $oldHook, 'Process')
    }
    Assert 'UPDATE_VERBOSE_OUTPUT_RETAINS_TECHNICAL_DETAILS' (
        $verboseNoOp -match 'Global OpenCode and active CLI version markers match' -and
        $verboseNoOp -match ('Active global CLI installation path: ' + [regex]::Escape($env:OLYMPUS_SMOKE_INSTALL_ROOT)) -and
        $defaultNoOp -notmatch 'Active global CLI installation path:'
    )
    Assert 'SAME_VERSION_UPDATE_GLOBAL_FILES_UNCHANGED' (@(Compare-Object $globalBeforeNoOp (Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)).Count -eq 0)
    Assert 'SAME_VERSION_UPDATE_CLI_AND_PATH_UNCHANGED' (@(Compare-Object $cliBeforeNoOp (Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)).Count -eq 0)
    $sameVersionRequests = @([IO.File]::ReadAllText($env:OLYMPUS_SMOKE_REQUEST_LOG) -split "`n" |
        Where-Object { $_ })
    Assert 'SAME_VERSION_UPDATE_CHECKS_METADATA_TWICE' (@($sameVersionRequests | Where-Object { $_ -like 'metadata *' }).Count -eq 3)
    Assert 'SAME_VERSION_UPDATE_NEVER_REDOWNLOADS_ASSETS' (
        @($sameVersionRequests | Where-Object { $_ -like 'installer *' }).Count -eq 1 -and
        @($sameVersionRequests | Where-Object { $_ -like 'archive *' }).Count -eq 1 -and
        $sameVersionRequests.Count -eq ($requestCountBeforeNoOp + 2)
    )

    $originalManifestBytes = [IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST)
    $originalCurrentBytes = [IO.File]::ReadAllBytes((Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt'))
    $requestCountBeforeBlocked = $sameVersionRequests.Count
    try {
        $env:PYTHONPATH = $env:OLYMPUS_SMOKE_HOOK_DIR
        $env:OLYMPUS_SMOKE_UPDATE_HOOK = '1'
        [IO.File]::Delete($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST)
        $preflightFailure = Invoke-OlympusFailure 'missing-installation-update-blocked' @('update') 3 'UPDATE_INSTALLATION_UNKNOWN'
        Assert 'UPDATE_PREFLIGHT_FAILURE_CONFIRMS_NO_CHANGE' ($preflightFailure -match 'Update did not start; no installation changes were made')
        [IO.File]::WriteAllBytes($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST, $originalManifestBytes)

        $manifest = [IO.File]::ReadAllText($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST) | ConvertFrom-Json -AsHashtable -Depth 20
        $manifest.installed_version = 'local'
        [IO.File]::WriteAllText($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST,
            ($manifest | ConvertTo-Json -Depth 20) + "`n", $Utf8NoBom)
        [void](Invoke-OlympusFailure 'unknown-global-version-update-blocked' @('update') 3 'UPDATE_VERSION_UNKNOWN')
        [IO.File]::WriteAllBytes($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST, $originalManifestBytes)

        $manifest = [IO.File]::ReadAllText($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST) | ConvertFrom-Json -AsHashtable -Depth 20
        $manifest.installed_version = 'v0.0.0'
        [IO.File]::WriteAllText($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST,
            ($manifest | ConvertTo-Json -Depth 20) + "`n", $Utf8NoBom)
        [void](Invoke-OlympusFailure 'split-version-update-blocked' @('update') 3 'UPDATE_VERSION_MISMATCH')
        [IO.File]::WriteAllBytes($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST, $originalManifestBytes)

        [IO.File]::WriteAllText((Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt'), '../invalid' + "`n", $Utf8NoBom)
        [void](Invoke-OlympusFailure 'invalid-cli-pointer-update-blocked' @('update') 3 'Olympus CLI release files are missing')
        [IO.File]::WriteAllBytes((Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt'), $originalCurrentBytes)

        $requestsBeforeNetworkFailure = @([IO.File]::ReadAllText($env:OLYMPUS_SMOKE_REQUEST_LOG) -split "`n" |
            Where-Object { $_ })
        Assert 'BLOCKED_LOCAL_VERSIONS_FAIL_BEFORE_METADATA' (@($requestsBeforeNetworkFailure | Where-Object { $_ -like 'metadata *' }).Count -eq 3)
        $env:OLYMPUS_SMOKE_METADATA_FAIL = '1'
        [void](Invoke-OlympusFailure 'metadata-network-failure-no-write' @('update') 3 'SMOKE_METADATA_UNAVAILABLE')
    } finally {
        [IO.File]::WriteAllBytes($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST, $originalManifestBytes)
        [IO.File]::WriteAllBytes((Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt'), $originalCurrentBytes)
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $oldPythonPath, 'Process')
        [Environment]::SetEnvironmentVariable('OLYMPUS_SMOKE_UPDATE_HOOK', $oldHook, 'Process')
        [Environment]::SetEnvironmentVariable('OLYMPUS_SMOKE_METADATA_FAIL', $null, 'Process')
    }
    Assert 'BLOCKED_UPDATES_DO_NOT_CHANGE_GLOBAL_FILES' (@(Compare-Object $globalBeforeNoOp (Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)).Count -eq 0)
    Assert 'BLOCKED_UPDATES_DO_NOT_CHANGE_CLI_OR_PATH' (@(Compare-Object $cliBeforeNoOp (Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)).Count -eq 0)
    $requestsAfterFailures = @([IO.File]::ReadAllText($env:OLYMPUS_SMOKE_REQUEST_LOG) -split "`n" | Where-Object { $_ })
    Assert 'NETWORK_FAILURE_ONLY_ADDS_METADATA_REQUEST' (@($requestsAfterFailures | Where-Object { $_ -like 'metadata *' }).Count -eq 4)
    Assert 'NETWORK_FAILURE_DOES_NOT_FETCH_ASSETS' (
        @($requestsAfterFailures | Where-Object { $_ -like 'installer *' }).Count -eq 1 -and
        @($requestsAfterFailures | Where-Object { $_ -like 'archive *' }).Count -eq 1 -and
        $requestsAfterFailures.Count -eq ($requestCountBeforeBlocked + 1)
    )

    $originalFixtureInstallerBytes = [IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_RELEASE_INSTALLER)
    $requestCountBeforeInstallerFailure = $requestsAfterFailures.Count
    try {
        $env:PYTHONPATH = $env:OLYMPUS_SMOKE_HOOK_DIR
        $env:OLYMPUS_SMOKE_UPDATE_HOOK = '1'
        $manifest = [IO.File]::ReadAllText($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST) | ConvertFrom-Json -AsHashtable -Depth 20
        $manifest.installed_version = $env:OLYMPUS_SMOKE_SOURCE_VERSION
        [IO.File]::WriteAllText($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST,
            ($manifest | ConvertTo-Json -Depth 20) + "`n", $Utf8NoBom)
        [IO.File]::WriteAllText((Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt'),
            $env:OLYMPUS_SMOKE_SOURCE_VERSION + "`n", $Utf8NoBom)
        $failingInstaller = @"
[CmdletBinding()]
param(
    [string]`$Version = '$($env:OLYMPUS_SMOKE_RELEASE_VERSION)',
    [string]`$Scope = 'global',
    [string]`$Harness = 'opencode',
    [switch]`$Update
)
`$ReleaseVersion = '$($env:OLYMPUS_SMOKE_RELEASE_VERSION)'
exit 23
"@
        [IO.File]::WriteAllText($env:OLYMPUS_SMOKE_RELEASE_INSTALLER, $failingInstaller, $Utf8NoBom)
        [void](Invoke-OlympusFailure 'installer-failure-exit-23-preserved' @('update') 23 'Effects may be partial')
        [IO.File]::WriteAllText($env:OLYMPUS_SMOKE_RELEASE_INSTALLER, $failingInstaller.Replace('exit 23', 'exit 3'), $Utf8NoBom)
        $nativeExit3 = Invoke-OlympusFailure 'installer-failure-exit-3-preserved' @('update') 3 'Effects may be partial'
        Assert 'NATIVE_EXIT_3_IS_NOT_PREFLIGHT_FAILURE' (
            $nativeExit3 -notmatch 'Update did not start; no installation changes were made' -and
            $nativeExit3 -match 'Effects may be partial'
        )
    } finally {
        [IO.File]::WriteAllBytes($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST, $originalManifestBytes)
        [IO.File]::WriteAllBytes((Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt'), $originalCurrentBytes)
        [IO.File]::WriteAllBytes($env:OLYMPUS_SMOKE_RELEASE_INSTALLER, $originalFixtureInstallerBytes)
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $oldPythonPath, 'Process')
        [Environment]::SetEnvironmentVariable('OLYMPUS_SMOKE_UPDATE_HOOK', $oldHook, 'Process')
    }
    Assert 'INSTALLER_FAILURE_DOES_NOT_CHANGE_GLOBAL_FILES' (@(Compare-Object $globalBeforeNoOp (Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)).Count -eq 0)
    Assert 'INSTALLER_FAILURE_DOES_NOT_CHANGE_CLI_OR_PATH' (@(Compare-Object $cliBeforeNoOp (Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)).Count -eq 0)
    $requestsAfterInstallerFailure = @([IO.File]::ReadAllText($env:OLYMPUS_SMOKE_REQUEST_LOG) -split "`n" | Where-Object { $_ })
    Assert 'INSTALLER_FAILURE_IS_FIXTURED_WITHOUT_ARCHIVE' (
        @($requestsAfterInstallerFailure | Where-Object { $_ -like 'installer *' }).Count -eq 3 -and
        @($requestsAfterInstallerFailure | Where-Object { $_ -like 'archive *' }).Count -eq 1 -and
        $requestsAfterInstallerFailure.Count -eq ($requestCountBeforeInstallerFailure + 4)
    )

    $wrapper = Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'bin/olympus.cmd'
    $sourceWrapper = [IO.File]::ReadAllText((Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'scripts/olympus.cmd'))
    $alternateWrapper = if ($sourceWrapper.Contains("`r`n")) {
        $sourceWrapper.Replace("`r`n", "`n")
    } else {
        $sourceWrapper.Replace("`n", "`r`n")
    }
    if ($alternateWrapper -ceq $sourceWrapper) { throw 'SMOKE_NEWLINE_VARIANT_UNAVAILABLE' }
    [IO.File]::WriteAllText($wrapper, $alternateWrapper, [Text.Encoding]::ASCII)
    $alternateWrapperBytes = [IO.File]::ReadAllBytes($wrapper)
    $normalCliReinstall = Invoke-PowerShell @('-File',
        (Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'scripts/install-cli.ps1'),
        '-Action','install','-Version',$env:OLYMPUS_SMOKE_RELEASE_VERSION,
        '-SourceRoot',$env:OLYMPUS_SMOKE_SOURCE_ROOT,
        '-InstallRoot',$env:OLYMPUS_SMOKE_INSTALL_ROOT,'-PathStorePath',$env:OLYMPUS_SMOKE_PATH_STORE)
    Assert 'CLI_LAUNCHER_ACCEPTS_AND_PRESERVES_LF_CRLF_EQUIVALENCE' (
        $normalCliReinstall -match 'OLYMPUS_CLI: READY' -and
        [Convert]::ToBase64String($alternateWrapperBytes) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($wrapper))
    )

    $globalAgent = Join-Path $env:OPENCODE_CONFIG_DIR 'agents/kael.md'
    $missingGlobalAgent = Join-Path $env:OPENCODE_CONFIG_DIR 'agents/nox.md'
    $cliManagedFile = Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT `
        ("versions/$($env:OLYMPUS_SMOKE_RELEASE_VERSION)/olympus/cli.py")
    $expectedGlobalNox = [IO.File]::ReadAllText($missingGlobalAgent)
    [IO.File]::AppendAllText($globalAgent, "`n# fixture-only managed drift`n", $Utf8NoBom)
    [IO.File]::Delete($missingGlobalAgent)
    [IO.File]::AppendAllText($cliManagedFile, "`n# fixture-only managed drift`n", $Utf8NoBom)
    $manifest = [IO.File]::ReadAllText($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST) |
        ConvertFrom-Json -AsHashtable -Depth 20
    $manifest.installed_version = $env:OLYMPUS_SMOKE_SOURCE_VERSION
    [IO.File]::WriteAllText($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST,
        ($manifest | ConvertTo-Json -Depth 20) + "`n", $Utf8NoBom)

    $globalBeforeForceChecks = @(Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)
    $cliBeforeForceChecks = @(Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)
    $nonForceGlobalRepair = Invoke-PowerShellResult @('-File',
        (Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'scripts/global-install.ps1'),
        '-Harness','opencode','-SourceVersion',$env:OLYMPUS_SMOKE_RELEASE_VERSION,'-Update')
    Assert 'GLOBAL_NONFORCE_UPDATE_REFUSES_MANAGED_DRIFT' (
        $nonForceGlobalRepair.Code -ne 0 -and $nonForceGlobalRepair.Text -match 'GLOBAL_MANAGED_FILE_DRIFT' -and
        @(Compare-Object $globalBeforeForceChecks (Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)).Count -eq 0
    ) $nonForceGlobalRepair.Text
    $nonForceCliRepair = Invoke-PowerShellResult @('-File',
        (Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'scripts/install-cli.ps1'),
        '-Action','install','-Version',$env:OLYMPUS_SMOKE_RELEASE_VERSION,
        '-SourceRoot',$env:OLYMPUS_SMOKE_SOURCE_ROOT,
        '-InstallRoot',$env:OLYMPUS_SMOKE_INSTALL_ROOT,'-PathStorePath',$env:OLYMPUS_SMOKE_PATH_STORE)
    Assert 'CLI_NONFORCE_INSTALL_REFUSES_MANAGED_DRIFT' (
        $nonForceCliRepair.Code -ne 0 -and $nonForceCliRepair.Text -match 'CLI_VERSION_CONFLICT' -and
        @(Compare-Object $cliBeforeForceChecks (Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)).Count -eq 0
    ) $nonForceCliRepair.Text

    $userConfigBeforeForce = [IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_OPENCODE_CONFIG)
    $globalMarkerBeforeForce = [IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_GLOBAL_MARKER)
    $binMarkerBeforeForce = [IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_BIN_MARKER)
    $versionMarkerBeforeForce = [IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_VERSION_MARKER)
    [IO.File]::WriteAllText($wrapper, '@echo off' + "`n" + 'rem unproven user launcher' + "`n",
        [Text.Encoding]::ASCII)
    $globalBeforeLauncherConflict = @(Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)
    $cliBeforeLauncherConflict = @(Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)
    $env:OLYMPUS_SMOKE_LAUNCHER = Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'scripts/launch-latest.ps1'
    $forceLauncherConflict = Invoke-PowerShellResult @('-File',$env:OLYMPUS_SMOKE_SCRIPT,
        '-MockLatest','-Action','install','-Update','-Force')
    Assert 'UNPROVEN_LAUNCHER_BLOCKS_FORCE_BEFORE_OPENCODE_WRITES' (
        $forceLauncherConflict.Code -ne 0 -and $forceLauncherConflict.Text -match 'CLI_LAUNCHER_CONFLICT' -and
        @(Compare-Object $globalBeforeLauncherConflict (Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)).Count -eq 0 -and
        @(Compare-Object $cliBeforeLauncherConflict (Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)).Count -eq 0
    ) $forceLauncherConflict.Text
    [IO.File]::WriteAllBytes($wrapper, $alternateWrapperBytes)

    $forceRepair = Invoke-PowerShellResult @('-File',$env:OLYMPUS_SMOKE_SCRIPT,
        '-MockLatest','-Action','install','-Update','-Force')
    Assert 'FORCE_UPDATE_SUCCEEDED_FROM_RECOGNIZED_SPLIT' (
        $forceRepair.Code -eq 0 -and $forceRepair.Text -match 'Updated to'
    ) $forceRepair.Text
    $forcedGlobalManifest = [IO.File]::ReadAllText($env:OLYMPUS_SMOKE_GLOBAL_MANIFEST) |
        ConvertFrom-Json -Depth 20
    Assert 'FORCE_REPAIRS_GLOBAL_VERSION_MARKER' (
        $forcedGlobalManifest.installed_version -ceq $env:OLYMPUS_SMOKE_RELEASE_VERSION
    ) ([string]$forcedGlobalManifest.installed_version)
    $fixtureGlobalAgent = Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT '.opencode/agents/kael.md'
    $fixtureAgentHash = (Get-FileHash -LiteralPath $fixtureGlobalAgent -Algorithm SHA256).Hash
    $expectedAgentHash = (Get-FileHash -LiteralPath $env:OLYMPUS_SMOKE_EXPECTED_GLOBAL_AGENT -Algorithm SHA256).Hash
    $installedAgentHash = (Get-FileHash -LiteralPath $globalAgent -Algorithm SHA256).Hash
    $forceRepairAgentEvidence = "replica_sha256=$fixtureAgentHash; renderer_sha256=$expectedAgentHash; installed_sha256=$installedAgentHash"
    Assert 'FORCE_REPAIRS_CHANGED_GLOBAL_AGENT' (
        [Convert]::ToBase64String([IO.File]::ReadAllBytes($globalAgent)) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_EXPECTED_GLOBAL_AGENT))
    ) $forceRepairAgentEvidence
    Write-Output "FORCE_REPAIR_GLOBAL_AGENT_COMPARE: $forceRepairAgentEvidence"
    Assert 'FORCE_RESTORES_MISSING_GLOBAL_AGENT' (
        [IO.File]::ReadAllText($missingGlobalAgent) -ceq $expectedGlobalNox
    )
    Assert 'FORCE_REPAIRS_CLI_VERSIONED_FILES' (
        [IO.File]::ReadAllText((Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt')).Trim() -ceq
            $env:OLYMPUS_SMOKE_RELEASE_VERSION -and
        [IO.File]::ReadAllText($cliManagedFile) -ceq
            [IO.File]::ReadAllText((Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'olympus/cli.py'))
    )
    Assert 'FORCE_PRESERVES_USER_FILES_AND_NEWLINE_EQUIVALENT_LAUNCHER' (
        [Convert]::ToBase64String($userConfigBeforeForce) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_OPENCODE_CONFIG)) -and
        [Convert]::ToBase64String($globalMarkerBeforeForce) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_GLOBAL_MARKER)) -and
        [Convert]::ToBase64String($binMarkerBeforeForce) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_BIN_MARKER)) -and
        [Convert]::ToBase64String($versionMarkerBeforeForce) -ceq
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_VERSION_MARKER)) -and
        [Convert]::ToBase64String($alternateWrapperBytes) -ceq
        [Convert]::ToBase64String([IO.File]::ReadAllBytes($wrapper))
    )

    $unprovenCliRoot = Join-Path (Split-Path -Parent $env:OLYMPUS_SMOKE_OTHER_DIR) 'cli-current-without-receipt'
    $unprovenCliBin = Join-Path $unprovenCliRoot 'bin'
    [IO.Directory]::CreateDirectory($unprovenCliBin) | Out-Null
    [IO.File]::WriteAllText((Join-Path $unprovenCliRoot 'current.txt'),
        $env:OLYMPUS_SMOKE_RELEASE_VERSION + "`n", $Utf8NoBom)
    [IO.File]::WriteAllText((Join-Path $unprovenCliBin 'olympus.cmd'), $sourceWrapper, [Text.Encoding]::ASCII)
    $unprovenCliBefore = @(Get-TreeSnapshot $unprovenCliRoot)
    $unprovenCliForce = Invoke-PowerShellResult @('-File',
        (Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'scripts/install-cli.ps1'),
        '-Action','install','-Version',$env:OLYMPUS_SMOKE_RELEASE_VERSION,'-Force',
        '-SourceRoot',$env:OLYMPUS_SMOKE_SOURCE_ROOT,
        '-InstallRoot',$unprovenCliRoot,'-PathStorePath',(Join-Path $unprovenCliRoot 'path-store.txt'))
    Assert 'FORCE_REFUSES_MISSING_CLI_RECEIPT_WITHOUT_WRITES' (
        $unprovenCliForce.Code -ne 0 -and $unprovenCliForce.Text -match 'CLI_VERSION_CONFLICT' -and
        @(Compare-Object $unprovenCliBefore (Get-TreeSnapshot $unprovenCliRoot)).Count -eq 0
    ) $unprovenCliForce.Text

    $globalBeforeMissingLauncher = @(Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)
    [IO.File]::Delete($wrapper)
    $missingLauncherForce = Invoke-PowerShellResult @('-File',
        (Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'scripts/install-cli.ps1'),
        '-Action','install','-Version',$env:OLYMPUS_SMOKE_RELEASE_VERSION,'-Force',
        '-SourceRoot',$env:OLYMPUS_SMOKE_SOURCE_ROOT,
        '-InstallRoot',$env:OLYMPUS_SMOKE_INSTALL_ROOT,'-PathStorePath',$env:OLYMPUS_SMOKE_PATH_STORE)
    Assert 'FORCE_RESTORES_ABSENT_RECEIPTED_LAUNCHER' (
        $missingLauncherForce.Code -eq 0 -and
        [IO.File]::ReadAllText($wrapper) -ceq $sourceWrapper -and
        @(Compare-Object $globalBeforeMissingLauncher (Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)).Count -eq 0
    ) $missingLauncherForce.Text

    $currentPath = Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt'
    $currentDacl = Set-ProtectedFixtureDacl $currentPath
    $activeReleaseRoot = Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT `
        "versions/$($env:OLYMPUS_SMOKE_RELEASE_VERSION)"
    $missingActiveLauncher = Join-Path $activeReleaseRoot 'scripts/launch-latest.ps1'
    [IO.File]::Delete($missingActiveLauncher)
    $missingPayloadRepair = Invoke-PowerShellResult @('-File',$env:OLYMPUS_SMOKE_SCRIPT,
        '-MockLatest','-Action','install','-Update','-Force')
    $currentDaclAfterRepair = Get-AccessDaclSnapshot $currentPath
    Assert 'FORCE_PREFLIGHT_REPAIRS_MISSING_RECEIPTED_ACTIVE_PAYLOAD' (
        $missingPayloadRepair.Code -eq 0 -and
        (Test-Path -LiteralPath $missingActiveLauncher -PathType Leaf) -and
        [IO.File]::ReadAllText($currentPath).Trim() -ceq $env:OLYMPUS_SMOKE_RELEASE_VERSION -and
        $currentDaclAfterRepair.Sddl -ceq $currentDacl.Sddl -and
        $currentDaclAfterRepair.Protected -and
        $currentDaclAfterRepair.ExplicitCount -eq $currentDacl.ExplicitCount -and
        $currentDaclAfterRepair.InheritedCount -eq $currentDacl.InheritedCount
    ) $missingPayloadRepair.Text

    $fixtureRoot = Split-Path -Parent $env:OLYMPUS_SMOKE_OTHER_DIR
    $bootstrapLauncherFixture = Join-Path $fixtureRoot 'official-bootstrap-launcher.ps1'
    $bootstrapSourceText = [IO.File]::ReadAllText((Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'scripts/launch-latest.ps1'))
    $bootstrapNewline = if ($bootstrapSourceText.Contains("`r`n")) { "`r`n" } else { "`n" }
    $bootstrapLauncherMock = @'
function global:Invoke-RestMethod {
    [CmdletBinding()]
    param([string]$Uri, [hashtable]$Headers)
    return [pscustomobject]@{
        immutable=$true; draft=$false; prerelease=$false
        tag_name=$env:OLYMPUS_SMOKE_RELEASE_VERSION
        published_at=[DateTimeOffset]::UtcNow.AddMinutes(-1)
    }
}
function global:Invoke-WebRequest {
    [CmdletBinding()]
    param([string]$Uri, [string]$OutFile, [hashtable]$Headers)
    $expected = "https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$($env:OLYMPUS_SMOKE_RELEASE_VERSION)/install.ps1"
    if ($Uri -cne $expected) { throw "Unexpected fixture installer request: $Uri" }
    [IO.File]::Copy($env:OLYMPUS_SMOKE_BOOTSTRAP_INSTALLER, $OutFile, $true)
}
'@
    $bootstrapLauncherMock = $bootstrapLauncherMock.Replace("`n", $bootstrapNewline) + $bootstrapNewline
    $launcherTry = [regex]::Match($bootstrapSourceText, '(?m)^try \{\r?\n')
    if (-not $launcherTry.Success) { throw 'BOOTSTRAP_LAUNCHER_FIXTURE_ANCHOR_MISSING' }
    $launcherTry = $launcherTry.Index + $launcherTry.Length
    $bootstrapSourceText = $bootstrapSourceText.Insert($launcherTry, $bootstrapLauncherMock)
    [IO.File]::WriteAllText($bootstrapLauncherFixture, $bootstrapSourceText, $Utf8NoBom)

    $bootstrapInstallerFixture = Join-Path $fixtureRoot 'official-bootstrap-installer.ps1'
    $bootstrapInstallerLog = Join-Path $fixtureRoot 'official-bootstrap-installer.log'
    $bootstrapInstallerText = @'
[CmdletBinding()]
param(
    [string]$Version = '__OLYMPUS_SMOKE_RELEASE_VERSION__',
    [string]$Scope,
    [string]$Harness,
    [switch]$Update,
    [switch]$Force
)
$ReleaseVersion = '__OLYMPUS_SMOKE_RELEASE_VERSION__'
if (-not $Force) { exit 41 }
[IO.File]::WriteAllText($env:OLYMPUS_SMOKE_BOOTSTRAP_LOG, "force=$($Force.IsPresent);version=$Version")
$cliArgs = @(
    '-NoProfile','-File',(Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'scripts/install-cli.ps1'),
    '-Action','install','-Version',$Version,'-SourceRoot',$env:OLYMPUS_SMOKE_SOURCE_ROOT,
    '-InstallRoot',$env:OLYMPUS_SMOKE_INSTALL_ROOT,'-PathStorePath',$env:OLYMPUS_SMOKE_PATH_STORE,'-Force'
)
& $env:OLYMPUS_SMOKE_PWSH @cliArgs
exit $LASTEXITCODE
'@
    $bootstrapInstallerText = $bootstrapInstallerText.Replace(
        '__OLYMPUS_SMOKE_RELEASE_VERSION__', $env:OLYMPUS_SMOKE_RELEASE_VERSION)
    [IO.File]::WriteAllText($bootstrapInstallerFixture, $bootstrapInstallerText, $Utf8NoBom)

    $bootstrapFixture = Join-Path $fixtureRoot 'official-install-olympus.ps1'
    $bootstrapEntryText = [IO.File]::ReadAllText((Join-Path $env:OLYMPUS_SMOKE_SOURCE_ROOT 'install-olympus.ps1'))
    $bootstrapEntryMock = @'
function global:Invoke-RestMethod {
    [CmdletBinding()]
    param([string]$Uri, [hashtable]$Headers)
    return [pscustomobject]@{
        immutable=$true; draft=$false; prerelease=$false
        tag_name=$env:OLYMPUS_SMOKE_RELEASE_VERSION
        published_at=[DateTimeOffset]::UtcNow.AddMinutes(-1)
    }
}
function global:Invoke-WebRequest {
    [CmdletBinding()]
    param([string]$Uri, [string]$OutFile, [hashtable]$Headers)
    $expected = "https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$($env:OLYMPUS_SMOKE_RELEASE_VERSION)/scripts/launch-latest.ps1"
    if ($Uri -cne $expected) { throw "Unexpected fixture launcher request: $Uri" }
    [IO.File]::Copy($env:OLYMPUS_SMOKE_BOOTSTRAP_LAUNCHER, $OutFile, $true)
}
'@
    $bootstrapEntryNewline = if ($bootstrapEntryText.Contains("`r`n")) { "`r`n" } else { "`n" }
    $bootstrapEntryMock = $bootstrapEntryMock.Replace("`n", $bootstrapEntryNewline) + $bootstrapEntryNewline
    $entryTry = [regex]::Match($bootstrapEntryText, '(?m)^try \{\r?\n')
    if (-not $entryTry.Success) { throw 'OFFICIAL_BOOTSTRAP_FIXTURE_ANCHOR_MISSING' }
    $entryTry = $entryTry.Index + $entryTry.Length
    $bootstrapEntryText = $bootstrapEntryText.Insert($entryTry, $bootstrapEntryMock)
    [IO.File]::WriteAllText($bootstrapFixture, $bootstrapEntryText, $Utf8NoBom)

    $missingCliPayload = Join-Path $activeReleaseRoot 'scripts/olympus_cli.py'
    [IO.File]::Delete($missingCliPayload)
    $env:OLYMPUS_SMOKE_BOOTSTRAP_LAUNCHER = $bootstrapLauncherFixture
    $env:OLYMPUS_SMOKE_BOOTSTRAP_INSTALLER = $bootstrapInstallerFixture
    $env:OLYMPUS_SMOKE_BOOTSTRAP_LOG = $bootstrapInstallerLog
    $officialBootstrap = Invoke-PowerShellResult @('-File',$bootstrapFixture,'-Force')
    $currentDaclAfterBootstrap = Get-AccessDaclSnapshot $currentPath
    Assert 'OFFICIAL_BOOTSTRAP_REPAIRS_WITH_OLD_CLI_PAYLOAD_ABSENT' (
        $officialBootstrap.Code -eq 0 -and
        (Test-Path -LiteralPath $missingCliPayload -PathType Leaf) -and
        [IO.File]::ReadAllText($bootstrapInstallerLog) -match '^force=True;' -and
        [IO.File]::ReadAllText($currentPath).Trim() -ceq $env:OLYMPUS_SMOKE_RELEASE_VERSION -and
        $currentDaclAfterBootstrap.Sddl -ceq $currentDacl.Sddl -and
        $currentDaclAfterBootstrap.Protected -and
        $currentDaclAfterBootstrap.ExplicitCount -eq $currentDacl.ExplicitCount -and
        $currentDaclAfterBootstrap.InheritedCount -eq $currentDacl.InheritedCount
    ) $officialBootstrap.Text
    foreach ($name in @('OLYMPUS_SMOKE_BOOTSTRAP_LAUNCHER','OLYMPUS_SMOKE_BOOTSTRAP_INSTALLER',
            'OLYMPUS_SMOKE_BOOTSTRAP_LOG')) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }

    $activeIdentityPath = Join-Path $activeReleaseRoot 'install.ps1'
    $activeIdentityBytes = [IO.File]::ReadAllBytes($activeIdentityPath)
    try {
        [IO.File]::AppendAllText($activeIdentityPath, "`n# fixture-only identity drift`n", $Utf8NoBom)
        $globalBeforeActiveIdentityDrift = @(Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)
        $cliBeforeActiveIdentityDrift = @(Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)
        $requestsBeforeActiveIdentityDrift = [IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_REQUEST_LOG)
        $activeIdentityDrift = Invoke-PowerShellResult @('-File',$env:OLYMPUS_SMOKE_SCRIPT,
            '-MockLatest','-Action','install','-Update','-Force')
        Assert 'FORCE_PREFLIGHT_REJECTS_ACTIVE_CLI_IDENTITY_RECEIPT_MISMATCH' (
            $activeIdentityDrift.Code -ne 0 -and
            $activeIdentityDrift.Text -match 'UPDATE_CLI_VERSION_UNKNOWN' -and
            @(Compare-Object $globalBeforeActiveIdentityDrift (Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)).Count -eq 0 -and
            @(Compare-Object $cliBeforeActiveIdentityDrift (Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)).Count -eq 0 -and
            [Convert]::ToBase64String($requestsBeforeActiveIdentityDrift) -ceq
                [Convert]::ToBase64String([IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_REQUEST_LOG))
        ) $activeIdentityDrift.Text

        [IO.File]::Delete($activeIdentityPath)
        $globalBeforeMissingActiveIdentity = @(Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)
        $cliBeforeMissingActiveIdentity = @(Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)
        $requestsBeforeMissingActiveIdentity = [IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_REQUEST_LOG)
        $missingActiveIdentity = Invoke-PowerShellResult @('-File',$env:OLYMPUS_SMOKE_SCRIPT,
            '-MockLatest','-Action','install','-Update','-Force')
        Assert 'FORCE_PREFLIGHT_REJECTS_MISSING_ACTIVE_CLI_IDENTITY' (
            $missingActiveIdentity.Code -ne 0 -and
            $missingActiveIdentity.Text -match 'UPDATE_CLI_VERSION_UNKNOWN' -and
            @(Compare-Object $globalBeforeMissingActiveIdentity (Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)).Count -eq 0 -and
            @(Compare-Object $cliBeforeMissingActiveIdentity (Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)).Count -eq 0 -and
            [Convert]::ToBase64String($requestsBeforeMissingActiveIdentity) -ceq
                [Convert]::ToBase64String([IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_REQUEST_LOG))
        ) $missingActiveIdentity.Text
    } finally {
        [IO.File]::WriteAllBytes($activeIdentityPath, $activeIdentityBytes)
    }

    $cliManifestPath = Join-Path $activeReleaseRoot 'olympus-cli-manifest.json'
    $validCliManifestBytes = [IO.File]::ReadAllBytes($cliManifestPath)
    try {
        $malformedCliManifest = [IO.File]::ReadAllText($cliManifestPath) |
            ConvertFrom-Json -AsHashtable -Depth 20
        $malformedCliManifest.files[0].sha256 = 'not-a-sha256'
        [IO.File]::WriteAllText($cliManifestPath,
            ($malformedCliManifest | ConvertTo-Json -Depth 20) + "`n", $Utf8NoBom)
        $globalBeforeMalformedReceipt = @(Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)
        $cliBeforeMalformedReceipt = @(Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)
        $malformedReceiptUpdate = Invoke-PowerShellResult @('-File',$env:OLYMPUS_SMOKE_SCRIPT,
            '-MockLatest','-Action','install','-Update','-Force')
        Assert 'FORCE_PREFLIGHT_REJECTS_MALFORMED_ACTIVE_CLI_RECEIPT' (
            $malformedReceiptUpdate.Code -ne 0 -and
            $malformedReceiptUpdate.Text -match 'UPDATE_CLI_VERSION_UNKNOWN' -and
            @(Compare-Object $globalBeforeMalformedReceipt (Get-TreeSnapshot $env:OPENCODE_CONFIG_DIR)).Count -eq 0 -and
            @(Compare-Object $cliBeforeMalformedReceipt (Get-TreeSnapshot $env:OLYMPUS_SMOKE_INSTALL_ROOT)).Count -eq 0
        ) $malformedReceiptUpdate.Text
    } finally {
        [IO.File]::WriteAllBytes($cliManifestPath, $validCliManifestBytes)
    }

    $originalFixtureMetadataBytes = [IO.File]::ReadAllBytes($env:OLYMPUS_SMOKE_METADATA_FIXTURE)
    try {
        $lowerRelease = [IO.File]::ReadAllText($env:OLYMPUS_SMOKE_METADATA_FIXTURE) |
            ConvertFrom-Json -AsHashtable -Depth 10
        $lowerRelease.tag_name = $env:OLYMPUS_SMOKE_SOURCE_VERSION
        [IO.File]::WriteAllText($env:OLYMPUS_SMOKE_METADATA_FIXTURE,
            ($lowerRelease | ConvertTo-Json -Depth 10), $Utf8NoBom)
        $requestsBeforeDowngradeBlock = @([IO.File]::ReadAllText($env:OLYMPUS_SMOKE_REQUEST_LOG) -split "`n" |
            Where-Object { $_ })
        $downgradeBlocked = Invoke-PowerShellResult @('-File',$env:OLYMPUS_SMOKE_SCRIPT,
            '-MockLatest','-Action','install','-Update','-Force')
        $requestsAfterDowngradeBlock = @([IO.File]::ReadAllText($env:OLYMPUS_SMOKE_REQUEST_LOG) -split "`n" |
            Where-Object { $_ })
        Assert 'FORCE_REJECTS_RELEASE_BELOW_EITHER_INSTALLED_IDENTITY' (
            $downgradeBlocked.Code -ne 0 -and $downgradeBlocked.Text -match 'UPDATE_DOWNGRADE_BLOCKED' -and
            @($requestsAfterDowngradeBlock | Where-Object { $_ -like 'installer *' }).Count -eq
                @($requestsBeforeDowngradeBlock | Where-Object { $_ -like 'installer *' }).Count -and
            @($requestsAfterDowngradeBlock | Where-Object { $_ -like 'archive *' }).Count -eq
                @($requestsBeforeDowngradeBlock | Where-Object { $_ -like 'archive *' }).Count
        ) $downgradeBlocked.Text
    } finally {
        [IO.File]::WriteAllBytes($env:OLYMPUS_SMOKE_METADATA_FIXTURE, $originalFixtureMetadataBytes)
    }
    [IO.File]::WriteAllText($wrapper, $sourceWrapper, [Text.Encoding]::ASCII)
    [Environment]::SetEnvironmentVariable('OLYMPUS_SMOKE_LAUNCHER', $null, 'Process')

    try {
        $env:PYTHONPATH = $env:OLYMPUS_SMOKE_HOOK_DIR
        $env:OLYMPUS_SMOKE_UPDATE_HOOK = '1'
        [void](Invoke-Olympus 'uninstall' @('uninstall', '--execute') 'REMOVED_MANAGED_RESOURCES_ONLY')
    } finally {
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $oldPythonPath, 'Process')
        [Environment]::SetEnvironmentVariable('OLYMPUS_SMOKE_UPDATE_HOOK', $oldHook, 'Process')
    }
    Assert 'USER_OPENCODE_CONFIG_PRESERVED' (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_OPENCODE_CONFIG -PathType Leaf)
    Assert 'USER_GLOBAL_FILE_PRESERVED' (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_GLOBAL_MARKER -PathType Leaf)
    Assert 'USER_CLI_BIN_FILE_PRESERVED' (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_BIN_MARKER -PathType Leaf)
    Assert 'USER_CLI_VERSION_DIRECTORY_PRESERVED' (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_VERSION_MARKER -PathType Leaf)
    Assert 'GLOBAL_MANIFEST_UNINSTALLED' (-not (Test-Path -LiteralPath $env:OLYMPUS_SMOKE_GLOBAL_MANIFEST))
    Assert 'CLI_CURRENT_POINTER_UNINSTALLED' (-not (Test-Path -LiteralPath (Join-Path $env:OLYMPUS_SMOKE_INSTALL_ROOT 'current.txt')))
    Write-Output 'INSTALLED_CLI_LIFECYCLE: PASS'
    exit 0
}

$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$python = (Get-Command python.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$git = (Get-Command git.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: This smoke requires Windows.' }
$powerShellVersion = & $script:Pwsh -NoProfile -Command '$PSVersionTable.PSVersion.Major'
if ($LASTEXITCODE -ne 0 -or [int]($powerShellVersion | Select-Object -Last 1) -lt 7) {
    throw 'POWERSHELL_UNQUALIFIED: PowerShell 7 is required.'
}

$identityText = [IO.File]::ReadAllText((Join-Path $source 'install.ps1'))
$defaultVersion = [regex]::Match($identityText, '(?m)^\s*\[string\]\$Version\s*=\s*''(?<version>[^'']+)''')
$releaseVersionMatch = [regex]::Match($identityText, '(?m)^\s*\$ReleaseVersion\s*=\s*''(?<version>[^'']+)''')
if (-not $defaultVersion.Success -or -not $releaseVersionMatch.Success -or
    $defaultVersion.Groups['version'].Value -cne $releaseVersionMatch.Groups['version'].Value) {
    throw 'SOURCE_VERSION_INVALID: install.ps1 release markers disagree.'
}
$sourceVersion = $defaultVersion.Groups['version'].Value
$stableVersion = [regex]::Match($sourceVersion, '^v(?<major>0|[1-9][0-9]*)\.(?<minor>0|[1-9][0-9]*)\.(?<patch>0|[1-9][0-9]*)$')
if (-not $stableVersion.Success) { throw "SOURCE_VERSION_UNSUPPORTED: $sourceVersion" }
$nextVersion = 'v{0}.{1}.{2}' -f $stableVersion.Groups['major'].Value, $stableVersion.Groups['minor'].Value,
    ([long]$stableVersion.Groups['patch'].Value + 1)

$launcherPath = Join-Path $source 'scripts/launch-latest.ps1'
$launcherText = [IO.File]::ReadAllText($launcherPath)
$apiRepo = [regex]::Match($launcherText, 'https://api\.github\.com/repos/(?<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/releases/latest')
$rawRepo = [regex]::Match($launcherText, 'https://raw\.githubusercontent\.com/(?<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/\$tag/install\.ps1')
if (-not $apiRepo.Success -or -not $rawRepo.Success -or $apiRepo.Groups['repo'].Value -cne $rawRepo.Groups['repo'].Value) {
    throw 'RELEASE_ENDPOINT_INVALID: Cannot derive matching metadata and installer fixture endpoints.'
}
$repository = $apiRepo.Groups['repo'].Value

$tempRoot = if ($env:TEMP) { [IO.Path]::GetFullPath($env:TEMP) } else { [IO.Path]::GetFullPath([IO.Path]::GetTempPath()) }
$fixtureParent = Join-Path $tempRoot 'olympus-cli-smoke'
$run = Join-Path $fixtureParent ('run-' + [guid]::NewGuid().ToString('N'))
$createdParent = $false
$runCreated = $false
$environmentNames = @(
    'APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'HOME', 'OPENCODE_CONFIG_DIR', 'OLYMPUS_CONFIG_HOME',
    'OLYMPUS_CONFIG_FILE', 'PYTHONDONTWRITEBYTECODE', 'OLYMPUS_SMOKE_INSTALL_ROOT',
    'OLYMPUS_SMOKE_PATH_STORE', 'OLYMPUS_SMOKE_RELEASE_VERSION', 'OLYMPUS_SMOKE_RELEASE_INSTALLER',
    'OLYMPUS_SMOKE_RELEASE_ARCHIVE', 'OLYMPUS_SMOKE_SOURCE_ROOT', 'OLYMPUS_SMOKE_METADATA_FIXTURE', 'OLYMPUS_SMOKE_REQUEST_LOG',
    'OLYMPUS_SMOKE_METADATA_URI', 'OLYMPUS_SMOKE_RAW_BASE', 'OLYMPUS_SMOKE_ARCHIVE_URI', 'OLYMPUS_SMOKE_PWSH',
    'OLYMPUS_SMOKE_METADATA_FAIL', 'OLYMPUS_SMOKE_SOURCE_VERSION',
    'OLYMPUS_UPDATE_COMPACT', 'OLYMPUS_CLI_UPDATE_COMPACT',
    'OLYMPUS_SMOKE_SCRIPT', 'OLYMPUS_SMOKE_HOOK_DIR', 'OLYMPUS_SMOKE_OTHER_DIR', 'OLYMPUS_SMOKE_LAUNCHER_PATH',
    'OLYMPUS_SMOKE_EXPECTED_GLOBAL_AGENT', 'OLYMPUS_SMOKE_LAUNCHER',
    'OLYMPUS_SMOKE_OPENCODE_CONFIG', 'OLYMPUS_SMOKE_GLOBAL_MARKER', 'OLYMPUS_SMOKE_BIN_MARKER',
    'OLYMPUS_SMOKE_VERSION_MARKER', 'OLYMPUS_SMOKE_GLOBAL_MANIFEST', 'OLYMPUS_SMOKE_USER_CONFIG',
    'OLYMPUS_CLI_ROOT', 'OLYMPUS_CLI_PATH_STORE', 'XDG_CONFIG_HOME'
)
$originalEnvironment = @{}
foreach ($name in $environmentNames) { $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$originalProcessPath = $env:PATH
$originalUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')

try {
    if (-not (Test-Path -LiteralPath $fixtureParent -PathType Container)) {
        [IO.Directory]::CreateDirectory($fixtureParent) | Out-Null
        $createdParent = $true
    }
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $runCreated = $true

    $appData = Join-Path $run 'appdata'
    $localAppData = Join-Path $run 'localappdata'
    $profile = Join-Path $run 'profile'
    $opencodeRoot = Join-Path $run 'opencode-global'
    $otherDirectory = Join-Path $run 'other-folder'
    $tempDirectory = Join-Path $run 'temp'
    $installRoot = Join-Path $localAppData 'Programs/Olympus'
    $bin = Join-Path $installRoot 'bin'
    $pathStore = Join-Path $installRoot 'path-store.txt'
    $releaseSource = Join-Path $run ("OpenCode-OlympusAgents-$nextVersion")
    $releaseArchive = Join-Path $run ("release-$nextVersion.zip")
    $metadataFixture = Join-Path $run 'release-metadata.json'
    $requestLog = Join-Path $run 'requests.log'
    $hookDirectory = Join-Path $run 'python-hook'
    $opencodeConfig = Join-Path $opencodeRoot 'opencode.jsonc'
    $globalMarker = Join-Path $opencodeRoot 'user-owned.txt'
    $binMarker = Join-Path $bin 'user-owned.cmd'
    $versionMarker = Join-Path $installRoot "versions/unmanaged/user-owned.txt"
    $manifest = Join-Path $opencodeRoot 'olympus/orchestrator-install.json'
    $userConfig = Join-Path $appData 'Olympus/config.json'

    foreach ($directory in @($appData, $localAppData, $profile, $opencodeRoot, $otherDirectory,
            $tempDirectory, $hookDirectory)) {
        [IO.Directory]::CreateDirectory($directory) | Out-Null
    }

    $env:APPDATA = $appData
    $env:LOCALAPPDATA = $localAppData
    $env:USERPROFILE = $profile
    $env:HOME = $profile
    $env:OPENCODE_CONFIG_DIR = $opencodeRoot
    $env:OLYMPUS_CLI_ROOT = $installRoot
    $env:OLYMPUS_CLI_PATH_STORE = $pathStore
    $env:XDG_CONFIG_HOME = Join-Path $run 'xdg'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    foreach ($name in @('OLYMPUS_CONFIG_HOME', 'OLYMPUS_CONFIG_FILE')) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    foreach ($name in @('OLYMPUS_UPDATE_COMPACT', 'OLYMPUS_CLI_UPDATE_COMPACT')) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    $env:OLYMPUS_CONFIG_FILE = $userConfig

    $userOpenCodeConfig = '{"user_owned":true,"permissions":[{"action":"external_directory","resource":"*","effect":"ask"},{"action":"external_directory","resource":"C:/fixture/prohibited/*","effect":"deny"}]}' + "`n"
    [IO.File]::WriteAllText($opencodeConfig, $userOpenCodeConfig, $Utf8NoBom)
    $savedOpenCodeConfig = [IO.File]::ReadAllBytes($opencodeConfig)

    [IO.Directory]::CreateDirectory($releaseSource) | Out-Null
    $clonePaths = @('olympus', 'scripts', '.opencode')
    foreach ($relative in $clonePaths) {
        Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $releaseSource -Recurse
    }
    Copy-Item -LiteralPath (Join-Path $source 'opencode.jsonc') -Destination $releaseSource
    Copy-Item -LiteralPath (Join-Path $source 'install.ps1') -Destination $releaseSource
    Copy-Item -LiteralPath (Join-Path $source 'install-olympus.ps1') -Destination $releaseSource

    $fixtureInstallerPath = Join-Path $releaseSource 'install.ps1'
    $fixtureInstaller = [IO.File]::ReadAllText($fixtureInstallerPath)
    $fixtureInstaller = $fixtureInstaller.Replace("[string]`$Version = '$sourceVersion',", "[string]`$Version = '$nextVersion',")
    $fixtureInstaller = $fixtureInstaller.Replace("`$ReleaseVersion = '$sourceVersion'", "`$ReleaseVersion = '$nextVersion'")
    if ($fixtureInstaller -notmatch [regex]::Escape("[string]`$Version = '$nextVersion',") -or
        $fixtureInstaller -notmatch [regex]::Escape("`$ReleaseVersion = '$nextVersion'")) {
        throw 'FIXTURE_VERSION_PATCH_FAILED: Could not create the controlled next-version source.'
    }

    $newline = if ($fixtureInstaller.Contains("`r`n")) { "`r`n" } else { "`n" }
    $platformAnchor = '    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT)'
    $platformPosition = $fixtureInstaller.IndexOf($platformAnchor, [StringComparison]::Ordinal)
    if ($platformPosition -lt 0) { throw 'FIXTURE_SOURCE_ARCHIVE_MOCK_ANCHOR_MISSING' }
    $tryPosition = $fixtureInstaller.LastIndexOf('try {', $platformPosition, [StringComparison]::Ordinal)
    if ($tryPosition -lt 0) { throw 'FIXTURE_SOURCE_ARCHIVE_MOCK_SCOPE_MISSING' }
    $archiveMock = @'
function global:Invoke-WebRequest {
    [CmdletBinding()]
    param([string]$Uri, [string]$OutFile)
    [IO.File]::AppendAllText($env:OLYMPUS_SMOKE_REQUEST_LOG, "archive $Uri`n", [Text.UTF8Encoding]::new($false))
    if ($Uri -cne $env:OLYMPUS_SMOKE_ARCHIVE_URI) { throw "Unexpected source archive request blocked: $Uri" }
    [IO.File]::Copy($env:OLYMPUS_SMOKE_RELEASE_ARCHIVE, $OutFile, $true)
}
'@
    $archiveMock = $archiveMock.Replace("`n", $newline) + $newline
    $fixtureInstaller = $fixtureInstaller.Insert($tryPosition, $archiveMock)

    $cliAnchor = '& $pwsh.Source @cliArgs'
    if (($fixtureInstaller.Split(@($cliAnchor), [StringSplitOptions]::None).Count - 1) -ne 1) {
        throw 'FIXTURE_CLI_ISOLATION_ANCHOR_INVALID'
    }
    $cliIsolation = @'
if ($env:OLYMPUS_SMOKE_INSTALL_ROOT -and $env:OLYMPUS_SMOKE_PATH_STORE) {
    $cliArgs += @('-InstallRoot', $env:OLYMPUS_SMOKE_INSTALL_ROOT,
        '-PathStorePath', $env:OLYMPUS_SMOKE_PATH_STORE)
}
'@
    $cliIsolation = $cliIsolation.Replace("`n", $newline) + $newline + '            '
    $fixtureInstaller = $fixtureInstaller.Replace($cliAnchor, $cliIsolation + $cliAnchor)
    [IO.File]::WriteAllText($fixtureInstallerPath, $fixtureInstaller, $Utf8NoBom)

    $expectedRenderRoot = Join-Path $run 'force-repair-expected-render'
    $expectedGlobalAgent = Join-Path $expectedRenderRoot '.opencode/agents/kael.md'
    $renderer = Join-Path $releaseSource 'scripts/render_harnesses.py'
    $renderOutput = (& $python -B $renderer render --harness opencode --root $releaseSource `
        --output-root $expectedRenderRoot 2>&1 | Out-String)
    $renderExitCode = $LASTEXITCODE
    Assert 'FORCE_REPAIR_EXPECTATION_RENDERED' (
        $renderExitCode -eq 0 -and $renderOutput -match 'HARNESS_RENDER: PASS \(opencode;' -and
        (Test-Path -LiteralPath $expectedGlobalAgent -PathType Leaf)
    ) $renderOutput

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory(
        $releaseSource, $releaseArchive, [IO.Compression.CompressionLevel]::Optimal, $true
    )

    $metadata = [ordered]@{
        immutable = $true
        draft = $false
        prerelease = $false
        tag_name = $nextVersion
        published_at = [DateTimeOffset]::UtcNow.AddMinutes(-1).ToString('o')
    } | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($metadataFixture, $metadata, $Utf8NoBom)
    [IO.File]::WriteAllText($requestLog, '', $Utf8NoBom)

    $pythonHook = @'
import os
import subprocess

_real_run = subprocess.run

def _run(command, *positional, **options):
    if os.environ.get("OLYMPUS_SMOKE_UPDATE_HOOK") == "1" and isinstance(command, (list, tuple)):
        try:
            index = command.index("-File")
            launcher = str(command[index + 1])
        except (ValueError, IndexError):
            launcher = ""
        if os.path.basename(launcher).lower() == "launch-latest.ps1":
            replacement = [
                os.environ["OLYMPUS_SMOKE_PWSH"], "-NoProfile", "-NonInteractive",
                "-File", os.environ["OLYMPUS_SMOKE_SCRIPT"], "-MockLatest",
                *[str(value) for value in command[index + 2:]],
            ]
            forwarded = dict(options)
            environment = dict(forwarded.get("env") or os.environ)
            environment["OLYMPUS_SMOKE_LAUNCHER"] = launcher
            forwarded["env"] = environment
            return _real_run(replacement, *positional, **forwarded)
        if os.path.basename(launcher).lower() == "install-cli.ps1":
            command = [*command, "-InstallRoot", os.environ["OLYMPUS_SMOKE_INSTALL_ROOT"],
                       "-PathStorePath", os.environ["OLYMPUS_SMOKE_PATH_STORE"]]
    return _real_run(command, *positional, **options)

subprocess.run = _run
'@
    [IO.File]::WriteAllText((Join-Path $hookDirectory 'sitecustomize.py'), $pythonHook, $Utf8NoBom)

    $apiUri = "https://api.github.com/repos/$repository/releases/latest"
    $rawBase = "https://raw.githubusercontent.com/$repository"
    $archiveUri = "https://github.com/$repository/archive/refs/tags/$nextVersion.zip"
    $env:OLYMPUS_SMOKE_INSTALL_ROOT = $installRoot
    $env:OLYMPUS_SMOKE_PATH_STORE = $pathStore
    $env:OLYMPUS_SMOKE_RELEASE_VERSION = $nextVersion
    $env:OLYMPUS_SMOKE_SOURCE_VERSION = $sourceVersion
    $env:OLYMPUS_SMOKE_RELEASE_INSTALLER = $fixtureInstallerPath
    $env:OLYMPUS_SMOKE_RELEASE_ARCHIVE = $releaseArchive
    $env:OLYMPUS_SMOKE_SOURCE_ROOT = $releaseSource
    $env:OLYMPUS_SMOKE_EXPECTED_GLOBAL_AGENT = $expectedGlobalAgent
    $env:OLYMPUS_SMOKE_METADATA_FIXTURE = $metadataFixture
    $env:OLYMPUS_SMOKE_REQUEST_LOG = $requestLog
    $env:OLYMPUS_SMOKE_METADATA_URI = $apiUri
    $env:OLYMPUS_SMOKE_RAW_BASE = $rawBase
    $env:OLYMPUS_SMOKE_ARCHIVE_URI = $archiveUri
    $env:OLYMPUS_SMOKE_PWSH = $script:Pwsh
    $env:OLYMPUS_SMOKE_SCRIPT = [IO.Path]::GetFullPath($PSCommandPath)
    $env:OLYMPUS_SMOKE_HOOK_DIR = $hookDirectory
    $env:OLYMPUS_SMOKE_OTHER_DIR = $otherDirectory
    $env:OLYMPUS_SMOKE_LAUNCHER_PATH = $bin + [IO.Path]::DirectorySeparatorChar + 'olympus.cmd'
    $env:OLYMPUS_SMOKE_OPENCODE_CONFIG = $opencodeConfig
    $env:OLYMPUS_SMOKE_GLOBAL_MARKER = $globalMarker
    $env:OLYMPUS_SMOKE_BIN_MARKER = $binMarker
    $env:OLYMPUS_SMOKE_VERSION_MARKER = $versionMarker
    $env:OLYMPUS_SMOKE_GLOBAL_MANIFEST = $manifest
    $env:OLYMPUS_SMOKE_USER_CONFIG = $userConfig

    [IO.Directory]::CreateDirectory((Split-Path -Parent $manifest)) | Out-Null
    [IO.File]::WriteAllText($globalMarker, 'unmanaged global file' + $newline, $Utf8NoBom)
    $globalInstall = Invoke-PowerShell @('-File', (Join-Path $source 'scripts/global-install.ps1'),
        '-Harness', 'opencode', '-SourceVersion', $sourceVersion, '-ProjectTarget', $otherDirectory)
    if ($globalInstall -notmatch ('OLYMPUS_GLOBAL_INSTALL: OPENCODE ' + [regex]::Escape($sourceVersion) + ' READY')) {
        throw "GLOBAL_INSTALL_ASSERTION_FAILED`n$globalInstall"
    }

    $cliInstall = Invoke-PowerShell @('-File', (Join-Path $source 'scripts/install-cli.ps1'),
        '-Action', 'install', '-Version', $sourceVersion, '-SourceRoot', $source,
        '-InstallRoot', $installRoot, '-PathStorePath', $pathStore)
    if ($cliInstall -notmatch ('OLYMPUS_CLI: INSTALLED version=' + [regex]::Escape($sourceVersion))) {
        throw "CLI_INSTALL_ASSERTION_FAILED`n$cliInstall"
    }
    $packagedSource = Join-Path $installRoot "versions/$sourceVersion"
    Assert 'PACKAGED_OPENCODE_GENERATED_ASSETS' ((Test-Path -LiteralPath (Join-Path $packagedSource '.opencode/agents/kael.md')) -and
        (Test-Path -LiteralPath (Join-Path $packagedSource '.opencode/plugins/olympus-activity/activity.ts')) -and
        (Test-Path -LiteralPath (Join-Path $packagedSource '.opencode/scripts/worktree-setup.ps1')))
    Assert 'PACKAGED_SOURCE_HAS_NO_RETIRED_CODEX_OUTPUTS' (
        -not (Test-Path -LiteralPath (Join-Path $packagedSource '.codex')) -and
        -not (Test-Path -LiteralPath (Join-Path $packagedSource 'CODEX.md'))
    )
    $packagedCommandDirectory = Join-Path $packagedSource '.opencode/commands'
    $packagedCommands = @(if (Test-Path -LiteralPath $packagedCommandDirectory -PathType Container) {
        @(Get-ChildItem -LiteralPath $packagedCommandDirectory -File | ForEach-Object { $_.Name })
    })
    $expectedCommands = @('olympus.performance-ultra.md','olympus.performance.md','olympus.ultra.md')
    Assert 'PACKAGED_ONLY_REQUIRED_GLOBAL_COMMANDS' (
        $packagedCommands.Count -eq $expectedCommands.Count -and
        @(Compare-Object $expectedCommands $packagedCommands -CaseSensitive).Count -eq 0
    )
    $persistedPath = [IO.File]::ReadAllText($pathStore)
    Assert 'PATH_STORE_ISOLATED' ($persistedPath -ceq [IO.Path]::GetFullPath($bin))
    $userPathCollision = @(($originalUserPath -split ';') | Where-Object {
        $_ -and [string]::Equals($_.TrimEnd('\', '/'),
            $bin.TrimEnd('\', '/'), [StringComparison]::OrdinalIgnoreCase)
    }).Count -gt 0
    Assert 'NO_USER_PATH_COLLISION' (-not $userPathCollision)

    [IO.File]::WriteAllText($binMarker, '@echo off' + $newline + 'exit /b 0' + $newline, [Text.Encoding]::ASCII)
    [IO.Directory]::CreateDirectory((Split-Path -Parent $versionMarker)) | Out-Null
    [IO.File]::WriteAllText($versionMarker, 'unmanaged version directory' + $newline, $Utf8NoBom)

    $necessaryPath = @(
        $persistedPath,
        (Split-Path -Parent $python),
        (Split-Path -Parent $script:Pwsh),
        (Split-Path -Parent $git),
        (Join-Path $env:SystemRoot 'System32')
    ) | Select-Object -Unique
    $childPath = $necessaryPath -join ';'
    $start = [Diagnostics.ProcessStartInfo]::new([IO.Path]::GetFullPath($script:Pwsh))
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.WorkingDirectory = $otherDirectory
    $start.Environment.Clear()
    foreach ($key in @('SystemRoot', 'WINDIR', 'COMSPEC', 'PATHEXT', 'PSModulePath',
            'ProgramFiles', 'ProgramFiles(x86)', 'SystemDrive')) {
        $value = [Environment]::GetEnvironmentVariable($key, 'Process')
        if ($value) { $start.Environment[$key] = $value }
    }
    $start.Environment['PATH'] = $childPath
    $start.Environment['APPDATA'] = $appData
    $start.Environment['LOCALAPPDATA'] = $localAppData
    $start.Environment['USERPROFILE'] = $profile
    $start.Environment['HOME'] = $profile
    $start.Environment['TEMP'] = $tempDirectory
    $start.Environment['TMP'] = $tempDirectory
    $start.Environment['OPENCODE_CONFIG_DIR'] = $opencodeRoot
    $start.Environment['PYTHONDONTWRITEBYTECODE'] = '1'
    $start.Environment['OLYMPUS_PYTHON'] = [IO.Path]::GetFullPath($python)
    foreach ($name in @('OLYMPUS_SMOKE_INSTALL_ROOT', 'OLYMPUS_SMOKE_PATH_STORE', 'OLYMPUS_SMOKE_RELEASE_VERSION',
            'OLYMPUS_SMOKE_RELEASE_INSTALLER', 'OLYMPUS_SMOKE_RELEASE_ARCHIVE', 'OLYMPUS_SMOKE_SOURCE_ROOT', 'OLYMPUS_SMOKE_METADATA_FIXTURE',
            'OLYMPUS_SMOKE_REQUEST_LOG', 'OLYMPUS_SMOKE_METADATA_URI', 'OLYMPUS_SMOKE_RAW_BASE',
            'OLYMPUS_SMOKE_ARCHIVE_URI', 'OLYMPUS_SMOKE_PWSH', 'OLYMPUS_SMOKE_METADATA_FAIL',
            'OLYMPUS_SMOKE_SOURCE_VERSION',
            'OLYMPUS_SMOKE_SCRIPT', 'OLYMPUS_SMOKE_HOOK_DIR', 'OLYMPUS_SMOKE_EXPECTED_GLOBAL_AGENT',
            'OLYMPUS_SMOKE_OTHER_DIR', 'OLYMPUS_SMOKE_LAUNCHER_PATH', 'OLYMPUS_SMOKE_LAUNCHER', 'OLYMPUS_SMOKE_OPENCODE_CONFIG',
            'OLYMPUS_SMOKE_GLOBAL_MARKER', 'OLYMPUS_SMOKE_BIN_MARKER', 'OLYMPUS_SMOKE_VERSION_MARKER',
            'OLYMPUS_SMOKE_GLOBAL_MANIFEST', 'OLYMPUS_SMOKE_USER_CONFIG')) {
        $start.Environment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }
    foreach ($argument in @('-NoProfile', '-NonInteractive', '-File', [IO.Path]::GetFullPath($PSCommandPath), '-Child')) {
        $start.ArgumentList.Add($argument)
    }
    $childProcess = [Diagnostics.Process]::new()
    $childProcess.StartInfo = $start
    try {
        if (-not $childProcess.Start()) { throw 'CHILD_PROCESS_START_FAILED' }
        $stdout = $childProcess.StandardOutput.ReadToEndAsync()
        $stderr = $childProcess.StandardError.ReadToEndAsync()
        $childProcess.WaitForExit()
        Write-Output $stdout.GetAwaiter().GetResult()
        $childError = $stderr.GetAwaiter().GetResult()
        if ($childError) { Write-Output $childError }
        if ($childProcess.ExitCode -ne 0) { throw "CHILD_SMOKE_FAILED: exit=$($childProcess.ExitCode)" }
    } finally { $childProcess.Dispose() }

    $requests = [IO.File]::ReadAllText($requestLog)
    $requestLines = @($requests -split "`n" | Where-Object { $_ })
    Assert 'MOCKED_STABLE_RELEASE_METADATA' ($requests -match ('(?m)^metadata ' + [regex]::Escape($apiUri) + '$'))
    Assert 'MOCKED_RELEASE_INSTALLER' ($requests -match ('(?m)^installer ' + [regex]::Escape("$rawBase/$nextVersion/install.ps1") + '$'))
    Assert 'MOCKED_RELEASE_ARCHIVE' ($requests -match ('(?m)^archive ' + [regex]::Escape($archiveUri) + '$'))
    Assert 'ALL_RELEASE_REQUESTS_FIXTURED' (
        $requestLines.Count -eq 20 -and
        @($requestLines | Where-Object { $_ -like 'metadata *' }).Count -eq 10 -and
        @($requestLines | Where-Object { $_ -like 'installer *' }).Count -eq 6 -and
        @($requestLines | Where-Object { $_ -like 'archive *' }).Count -eq 4
    ) ("total=$($requestLines.Count); metadata=$(@($requestLines | Where-Object { $_ -like 'metadata *' }).Count); installer=$(@($requestLines | Where-Object { $_ -like 'installer *' }).Count); archive=$(@($requestLines | Where-Object { $_ -like 'archive *' }).Count)")

    Assert 'USER_OPENCODE_CONFIG_UNCHANGED' ([Convert]::ToBase64String($savedOpenCodeConfig) -ceq
        [Convert]::ToBase64String([IO.File]::ReadAllBytes($opencodeConfig)))
    Assert 'USER_GLOBAL_FILE_PRESERVED' ([IO.File]::ReadAllText($globalMarker) -ceq ('unmanaged global file' + $newline))
    $userConfiguration = [IO.File]::ReadAllText($userConfig) | ConvertFrom-Json -AsHashtable -Depth 20
    Assert 'USER_OVERRIDE_PRESERVED' ($userConfiguration.overrides.nox.model -ceq 'openai/gpt-6.1-sol' -and
        $userConfiguration.overrides.nox.effort -ceq 'high')
    Assert 'USER_CLI_BIN_FILE_PRESERVED' (Test-Path -LiteralPath $binMarker -PathType Leaf)
    Assert 'USER_CLI_VERSION_DIRECTORY_PRESERVED' (Test-Path -LiteralPath $versionMarker -PathType Leaf)
    Assert 'GLOBAL_MANAGED_RESOURCES_UNINSTALLED' (-not (Test-Path -LiteralPath $manifest) -and
        -not (Test-Path -LiteralPath (Join-Path $opencodeRoot 'agents/nox.md')))
    Assert 'CLI_MANAGED_RELEASES_UNINSTALLED' (-not (Test-Path -LiteralPath (Join-Path $installRoot 'current.txt')) -and
        -not (Test-Path -LiteralPath (Join-Path $bin 'olympus.cmd')))
    Assert 'OWNED_PATH_ENTRY_UNINSTALLED' ([IO.File]::ReadAllText($pathStore) -ceq '')
    # User PATH can expand %USERPROFILE%; compare under the original environment.
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
    Assert 'USER_PATH_UNCHANGED' ([Environment]::GetEnvironmentVariable('Path', 'User') -ceq $originalUserPath)
    Assert 'PROCESS_PATH_UNCHANGED' ($env:PATH -ceq $originalProcessPath)
    Write-Output "GLOBAL_CLI_SMOKE: PASS (source=$sourceVersion fixture-release=$nextVersion; no published release or API used)"
} finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
    if ($runCreated -and (Test-Path -LiteralPath $run -PathType Container)) {
        Remove-Item -LiteralPath $run -Recurse -Force
    }
    if ($createdParent -and (Test-Path -LiteralPath $fixtureParent -PathType Container) -and
        @(Get-ChildItem -LiteralPath $fixtureParent -Force).Count -eq 0) {
        [IO.Directory]::Delete($fixtureParent)
    }
}
