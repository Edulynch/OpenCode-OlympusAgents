[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('opencode\olympus-installer-ux-' + [guid]::NewGuid().ToString('N'))
$mockBin = Join-Path $run 'mock-bin'
$dispatchLog = Join-Path $run 'launcher-args.txt'
$installEntry = Join-Path $source 'install-olympus.ps1'
$uninstallEntry = Join-Path $source 'uninstall-olympus.ps1'
$installer = Join-Path $source 'install.ps1'
$globalInstaller = Join-Path $source 'scripts/global-install.ps1'
$originalPath = $env:PATH
$originalDispatchLog = $env:OLYMPUS_ENTRYPOINT_LOG
$realPwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$global:OlympusInstallerUxLauncherFixtureMode = $false
$global:OlympusInstallerUxRemoteBootstrapMode = $false
$global:OlympusInstallerUxApiOrder = @()

function Check([string]$id, [bool]$condition, [string]$evidence = '') {
    if (-not $condition) {
        if ($evidence) { throw "$id FAIL`n$evidence" }
        throw "$id FAIL"
    }
    Write-Output "$id PASS"
}

function Invoke-MockedEntry([string]$Entry, [hashtable]$Parameters, [string[]]$Answers = @()) {
    $global:OlympusInstallerUxReadHostAnswers = @($Answers)
    $global:OlympusInstallerUxReadHostCalls = 0
    & $Entry @Parameters
    return [pscustomobject]@{
        Text = [IO.File]::ReadAllText($script:dispatchLog)
        Prompts = $global:OlympusInstallerUxReadHostCalls
    }
}

function Invoke-IexMockedEntry([string]$Entry, [string[]]$Answers = @()) {
    $global:OlympusInstallerUxReadHostAnswers = @($Answers)
    $global:OlympusInstallerUxReadHostCalls = 0
    $global:OlympusInstallerUxRelease = [pscustomobject]@{
        tag_name = 'v9.8.7'; immutable = $true; draft = $false; prerelease = $false; published_at = '2026-10-01T12:00:00Z'
    }
    $global:OlympusInstallerUxLaunchSource = Join-Path $script:source 'scripts/launch-latest.ps1'
    $global:OlympusInstallerUxRemoteBootstrapMode = $true
    $global:LASTEXITCODE = 0
    $text = ''
    try {
        $text = (Invoke-Expression ([IO.File]::ReadAllText($Entry)) 2>&1 | Out-String)
        return [pscustomobject]@{ Text = $text; Code = $LASTEXITCODE; Prompts = $global:OlympusInstallerUxReadHostCalls }
    } catch {
        $text += $_.Exception.Message
        return [pscustomobject]@{ Text = $text; Code = 1; Prompts = $global:OlympusInstallerUxReadHostCalls }
    } finally {
        $global:OlympusInstallerUxRemoteBootstrapMode = $false
    }
}

function Write-ProjectManifest([string]$Target, [bool]$Drift = $false, [switch]$Legacy) {
    $managed = @(
        @{ Path = '.opencode/agents/kael.md'; Text = "managed agent`n" },
        @{ Path = 'opencode.jsonc'; Text = "{`"agent`":`"kael`"}`n" }
    )
    $entries = foreach ($item in $managed) {
        $full = Join-Path $Target ($item.Path -replace '/', [IO.Path]::DirectorySeparatorChar)
        [IO.Directory]::CreateDirectory((Split-Path -Parent $full)) | Out-Null
        [IO.File]::WriteAllText($full, $item.Text, [Text.UTF8Encoding]::new($false))
        $hash = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Drift -and $item.Path -eq '.opencode/agents/kael.md') {
            [IO.File]::AppendAllText($full, "user edit`n", [Text.UTF8Encoding]::new($false))
        }
        @{ path = $item.Path; sha256 = $hash }
    }
    $manifest = @{
        schema_version = 1
        scope = 'project'
        installed_version = if ($Legacy) { 'v0.2.0' } else { 'v0.4.9' }
        managed_files = @($entries)
    }
    if (-not $Legacy) { $manifest.installed_harnesses = @('opencode') }
    $manifestJson = $manifest | ConvertTo-Json -Depth 10
    $manifestPath = Join-Path $Target '.opencode/orchestrator-install.json'
    [IO.File]::WriteAllText($manifestPath, $manifestJson + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

function New-Project([string]$Name) {
    $target = Join-Path $run $Name
    [IO.Directory]::CreateDirectory($target) | Out-Null
    & git -C $target init --quiet
    if ($LASTEXITCODE -ne 0) { throw "GIT_FIXTURE_INIT_FAIL: $Name" }
    return $target
}

function Invoke-RealUninstall([string]$Target) {
    $output = (& $realPwsh -NoProfile -File $script:installer -SourceRoot $script:source -Target $Target -Harness opencode -Uninstall 2>&1 | Out-String)
    return [pscustomobject]@{ Text = $output; Code = $LASTEXITCODE }
}

function Invoke-NonInteractiveEntry([string]$Entry, [string[]]$Arguments = @()) {
    $output = (& $script:realPwsh -NoProfile -NonInteractive -File $Entry @Arguments 2>&1 | Out-String)
    return [pscustomobject]@{ Text = $output; Code = $LASTEXITCODE }
}

function Read-Host {
    param([string]$Prompt)
    $global:OlympusInstallerUxReadHostCalls++
    if ($global:OlympusInstallerUxReadHostAnswers.Count -eq 0) { throw "UNEXPECTED_PROMPT: $Prompt" }
    $answer = [string]$global:OlympusInstallerUxReadHostAnswers[0]
    if ($global:OlympusInstallerUxReadHostAnswers.Count -gt 1) { $global:OlympusInstallerUxReadHostAnswers = @($global:OlympusInstallerUxReadHostAnswers | Select-Object -Skip 1) }
    else { $global:OlympusInstallerUxReadHostAnswers = @() }
    return $answer
}

function Invoke-WebRequest {
    [CmdletBinding()]
    param([string]$Uri, [string]$OutFile, [hashtable]$Headers)
    if ($global:OlympusInstallerUxRemoteBootstrapMode) {
        $global:OlympusInstallerUxApiOrder += 'launcher-download'
        $global:OlympusInstallerUxLauncherUrl = $Uri
        $global:OlympusInstallerUxDownloadedTo = $OutFile
        Copy-Item -LiteralPath $global:OlympusInstallerUxLaunchSource -Destination $OutFile -Force
        return
    }
    if ($global:OlympusInstallerUxLauncherFixtureMode) {
        $global:OlympusInstallerUxApiOrder += 'installer-download'
        $global:OlympusInstallerUxInstallerDownloadCount++
        $global:OlympusInstallerUxInstallerUrl = $Uri
        [IO.File]::WriteAllText($OutFile, $global:OlympusInstallerUxInstallerText, [Text.UTF8Encoding]::new($false))
        return
    }
    $global:OlympusInstallerUxLauncherUrl = $Uri
    $global:OlympusInstallerUxDownloadedTo = $OutFile
    Copy-Item -LiteralPath $global:OlympusInstallerUxLaunchSource -Destination $OutFile -Force
}

function Invoke-RealGlobalUninstall([string]$Root) {
    $originalConfigDir = $env:OPENCODE_CONFIG_DIR
    try {
        $env:OPENCODE_CONFIG_DIR = $Root
        $output = (& $script:realPwsh -NoProfile -File $script:globalInstaller -Harness opencode -Uninstall 2>&1 | Out-String)
        return [pscustomobject]@{ Text = $output; Code = $LASTEXITCODE }
    } finally {
        if ($null -eq $originalConfigDir) { Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue }
        else { $env:OPENCODE_CONFIG_DIR = $originalConfigDir }
    }
}

function Invoke-RestMethod {
    [CmdletBinding()]
    param([string]$Uri, [hashtable]$Headers)
    $global:OlympusInstallerUxApiOrder += 'release-metadata'
    $global:OlympusInstallerUxMetadataUrl = $Uri
    return $global:OlympusInstallerUxRelease
}

function Invoke-MockedLauncher([string]$Action, [string]$Scope, [string]$Harness, [string]$Target) {
    $global:OlympusInstallerUxInstallerDownloadCount = 0
    $global:OlympusInstallerUxInstallerUrl = $null
        $global:OlympusInstallerUxApiOrder = @()
    $global:OlympusInstallerUxMetadataUrl = $null
    $global:OlympusInstallerUxLauncherFixtureMode = $true
    $global:LASTEXITCODE = 0
    $launcherScript = [scriptblock]::Create([IO.File]::ReadAllText((Join-Path $script:source 'scripts/launch-latest.ps1')))
    $text = ''
    try {
        $text = (& $launcherScript -Action $Action -Scope $Scope -Harness $Harness -Target $Target 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) { return [pscustomobject]@{ Code = $LASTEXITCODE; Text = $text } }
        return [pscustomobject]@{ Code = 0; Text = $text }
    } catch {
        return [pscustomobject]@{ Code = 1; Text = ($text + $_.Exception.Message) }
    } finally {
        $global:OlympusInstallerUxLauncherFixtureMode = $false
    }
}

function Invoke-MockedBootstrap([string]$Action, [object]$PublishedAt, [bool]$Immutable = $true,
    [bool]$Draft = $false, [bool]$Prerelease = $false) {
    $global:OlympusInstallerUxRelease = [pscustomobject]@{
        tag_name = 'v9.8.7'; immutable = $Immutable; draft = $Draft; prerelease = $Prerelease; published_at = $PublishedAt
    }
    $global:OlympusInstallerUxApiOrder = @()
    $global:OlympusInstallerUxRemoteBootstrapMode = $true
    $entry = if ($Action -eq 'install') { $script:installEntry } else { $script:uninstallEntry }
    $entryScript = [scriptblock]::Create([IO.File]::ReadAllText($entry))
    $global:LASTEXITCODE = 0
    $text = ''
    $code = 0
    try {
        $text = (& $entryScript -Global -Harness all 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) { $code = 1 }
    } catch {
        $text += $_.Exception.Message
        $code = 1
    } finally {
        $global:OlympusInstallerUxRemoteBootstrapMode = $false
    }
    return [pscustomobject]@{ Code = $code; Text = $text; ApiOrder = ($global:OlympusInstallerUxApiOrder -join ',') }
}

function Invoke-IsolatedPublishedTimestampConverter([string]$ScriptPath, [object]$Value) {
    $tokens = $null
    $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile($ScriptPath, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count -gt 0) { throw "TIMESTAMP_FIXTURE_PARSE_FAILED: $ScriptPath" }
    $converter = $ast.Find({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq 'ConvertTo-ReleasePublishedTimestamp'
    }, $false)
    if ($null -eq $converter) { throw "TIMESTAMP_CONVERTER_MISSING: $ScriptPath" }
    $runner = [scriptblock]::Create($converter.Extent.Text + "`nConvertTo-ReleasePublishedTimestamp `$args[0]")
    return & $runner $Value
}

try {
    [IO.Directory]::CreateDirectory($mockBin) | Out-Null
    $mockCommand = @'
@echo off
>"%OLYMPUS_ENTRYPOINT_LOG%" echo %*
exit /b 0
'@
    [IO.File]::WriteAllText((Join-Path $mockBin 'pwsh.cmd'), $mockCommand, [Text.Encoding]::ASCII)
    $env:OLYMPUS_ENTRYPOINT_LOG = $dispatchLog
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $env:PATH

    $hereTarget = Join-Path $run 'current project'
    $otherTarget = Join-Path $run 'other project'
    [IO.Directory]::CreateDirectory($hereTarget) | Out-Null
    [IO.Directory]::CreateDirectory($otherTarget) | Out-Null
    Push-Location $hereTarget
    try {
        # No arguments ask for a target and then a harness; the selection reaches the existing launcher.
        $interactiveInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{} -Answers @('2', $otherTarget, '3')
        Check 'INTERACTIVE_INSTALL_PROMPTS_SCOPE_AND_HARNESS' ($interactiveInstall.Prompts -eq 3 -and
            $interactiveInstall.Text -match '(?i)-Action install .*?-Scope project .*?-Harness all .*?-Target')

        $hereInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{ Project = $true; Here = $true; Harness = 'codex' }
        Check 'DIRECT_PROJECT_HERE' ($hereInstall.Prompts -eq 0 -and
            $hereInstall.Text -match '(?i)-Action install .*?-Scope project .*?-Harness codex' -and
            $hereInstall.Text.Contains($hereTarget))

        $pathInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{ ProjectPath = $otherTarget; Harness = 'opencode' }
        Check 'DIRECT_PROJECT_PATH' ($pathInstall.Prompts -eq 0 -and
            $pathInstall.Text -match '(?i)-Action install .*?-Scope project .*?-Harness opencode' -and
            $pathInstall.Text.Contains($otherTarget))

        $globalInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{ Global = $true; Harness = 'all' }
        Check 'DIRECT_GLOBAL' ($globalInstall.Prompts -eq 0 -and
            $globalInstall.Text -match '(?i)-Action install .*?-Scope global .*?-Harness all')

        $partialHereInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{ Project = $true; Here = $true } -Answers @('2')
        Check 'PARTIAL_INSTALL_HERE_PROMPTS_HARNESS_ONLY' ($partialHereInstall.Prompts -eq 1 -and
            $partialHereInstall.Text -match '(?i)-Action install .*?-Scope project .*?-Harness codex' -and
            $partialHereInstall.Text.Contains($hereTarget))

        $partialPathInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{ ProjectPath = $otherTarget } -Answers @('1')
        Check 'PARTIAL_INSTALL_PATH_WITH_SPACES_PROMPTS_HARNESS_ONLY' ($partialPathInstall.Prompts -eq 1 -and
            $partialPathInstall.Text -match '(?i)-Action install .*?-Scope project .*?-Harness opencode' -and
            $partialPathInstall.Text.Contains($otherTarget))

        foreach ($entry in @(
            [pscustomobject]@{ Id = 'IEX_INTERACTIVE_INSTALL'; Path = $installEntry; Action = 'install' },
            [pscustomobject]@{ Id = 'IEX_INTERACTIVE_UNINSTALL'; Path = $uninstallEntry; Action = 'uninstall' }
        )) {
            $iexEntry = Invoke-IexMockedEntry -Entry $entry.Path -Answers @('1', '1')
            Check ($entry.Id + '_OPTIONAL_PROJECTPATH_DOES_NOT_BLOCK') ($iexEntry.Code -eq 0 -and
                $iexEntry.Prompts -eq 2 -and
                [IO.File]::ReadAllText($dispatchLog) -match ("(?i)-Action {0} .*?-Scope project .*?-Harness opencode" -f $entry.Action) -and
                [IO.File]::ReadAllText($dispatchLog).Contains($hereTarget)) (
                    "code=$($iexEntry.Code), prompts=$($iexEntry.Prompts), text=$($iexEntry.Text), dispatch=$([IO.File]::ReadAllText($dispatchLog))")
        }

        $partialHarnessInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{ Harness = 'all' } -Answers @('1')
        Check 'PARTIAL_INSTALL_HARNESS_PROMPTS_SCOPE_ONLY' ($partialHarnessInstall.Prompts -eq 1 -and
            $partialHarnessInstall.Text -match '(?i)-Action install .*?-Scope project .*?-Harness all' -and
            $partialHarnessInstall.Text.Contains($hereTarget))

        $partialGlobalInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{ Global = $true } -Answers @('3')
        Check 'PARTIAL_INSTALL_GLOBAL_PROMPTS_HARNESS_ONLY' ($partialGlobalInstall.Prompts -eq 1 -and
            $partialGlobalInstall.Text -match '(?i)-Action install .*?-Scope global .*?-Harness all')

        $directHereUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ Project = $true; Here = $true; Harness = 'opencode' }
        Check 'DIRECT_UNINSTALL_PROJECT_HERE_FROM_FOREIGN_PROJECT' ($directHereUninstall.Prompts -eq 0 -and
            $directHereUninstall.Text -match '(?i)-Action uninstall .*?-Scope project .*?-Harness opencode' -and
            $directHereUninstall.Text.Contains($hereTarget))

        $interactiveHereInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{} -Answers @('1', '2')
        Check 'INTERACTIVE_INSTALL_PROJECT_HERE_FROM_FOREIGN_PROJECT' ($interactiveHereInstall.Prompts -eq 2 -and
            $interactiveHereInstall.Text -match '(?i)-Action install .*?-Scope project .*?-Harness codex' -and
            $interactiveHereInstall.Text.Contains($hereTarget))

        $interactiveGlobalInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{} -Answers @('3', '1')
        Check 'INTERACTIVE_INSTALL_GLOBAL' ($interactiveGlobalInstall.Prompts -eq 2 -and
            $interactiveGlobalInstall.Text -match '(?i)-Action install .*?-Scope global .*?-Harness opencode')

        $interactiveUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{} -Answers @('1', '2')
        Check 'INTERACTIVE_UNINSTALL_PROMPTS_SCOPE_AND_HARNESS' ($interactiveUninstall.Prompts -eq 2 -and
            $interactiveUninstall.Text -match '(?i)-Action uninstall .*?-Scope project .*?-Harness codex')

        $interactivePathUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{} -Answers @('2', $otherTarget, '1')
        Check 'INTERACTIVE_UNINSTALL_PROJECT_PATH_WITH_SPACES' ($interactivePathUninstall.Prompts -eq 3 -and
            $interactivePathUninstall.Text -match '(?i)-Action uninstall .*?-Scope project .*?-Harness opencode' -and
            $interactivePathUninstall.Text.Contains($otherTarget))

        $interactiveGlobalUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{} -Answers @('3', '3')
        Check 'INTERACTIVE_UNINSTALL_GLOBAL' ($interactiveGlobalUninstall.Prompts -eq 2 -and
            $interactiveGlobalUninstall.Text -match '(?i)-Action uninstall .*?-Scope global .*?-Harness all')

        $pathUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ ProjectPath = $otherTarget; Harness = 'all' }
        Check 'DIRECT_UNINSTALL_PROJECT_PATH' ($pathUninstall.Prompts -eq 0 -and
            $pathUninstall.Text -match '(?i)-Action uninstall .*?-Scope project .*?-Harness all' -and
            $pathUninstall.Text.Contains($otherTarget))

        $globalUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ Global = $true; Harness = 'opencode' }
        Check 'DIRECT_UNINSTALL_GLOBAL' ($globalUninstall.Prompts -eq 0 -and
            $globalUninstall.Text -match '(?i)-Action uninstall .*?-Scope global .*?-Harness opencode')

        $partialHereUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ Project = $true; Here = $true } -Answers @('1')
        Check 'PARTIAL_UNINSTALL_HERE_PROMPTS_HARNESS_ONLY' ($partialHereUninstall.Prompts -eq 1 -and
            $partialHereUninstall.Text -match '(?i)-Action uninstall .*?-Scope project .*?-Harness opencode' -and
            $partialHereUninstall.Text.Contains($hereTarget))

        $partialPathUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ ProjectPath = $otherTarget } -Answers @('3')
        Check 'PARTIAL_UNINSTALL_PATH_WITH_SPACES_PROMPTS_HARNESS_ONLY' ($partialPathUninstall.Prompts -eq 1 -and
            $partialPathUninstall.Text -match '(?i)-Action uninstall .*?-Scope project .*?-Harness all' -and
            $partialPathUninstall.Text.Contains($otherTarget))

        $partialHarnessUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ Harness = 'codex' } -Answers @('1')
        Check 'PARTIAL_UNINSTALL_HARNESS_PROMPTS_SCOPE_ONLY' ($partialHarnessUninstall.Prompts -eq 1 -and
            $partialHarnessUninstall.Text -match '(?i)-Action uninstall .*?-Scope project .*?-Harness codex' -and
            $partialHarnessUninstall.Text.Contains($hereTarget))

        $partialGlobalUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ Global = $true } -Answers @('2')
        Check 'PARTIAL_UNINSTALL_GLOBAL_PROMPTS_HARNESS_ONLY' ($partialGlobalUninstall.Prompts -eq 1 -and
            $partialGlobalUninstall.Text -match '(?i)-Action uninstall .*?-Scope global .*?-Harness codex')

        # IEX has no script path; bootstrap must use the metadata-selected immutable release launcher.
        $global:OlympusInstallerUxLaunchSource = Join-Path $source 'scripts/launch-latest.ps1'
        $global:OlympusInstallerUxRelease = [pscustomobject]@{
            tag_name = 'v9.8.7'; immutable = $true; draft = $false; prerelease = $false; published_at = '2026-10-01T12:00:00Z'
        }
        $global:OlympusInstallerUxRemoteBootstrapMode = $true
        $global:OlympusInstallerUxLauncherUrl = $null
        $global:OlympusInstallerUxDownloadedTo = $null
        $global:OlympusInstallerUxApiOrder = @()
        $remoteInstallBlock = [scriptblock]::Create([IO.File]::ReadAllText($installEntry))
        & $remoteInstallBlock -Global -Harness all
        Check 'REMOTE_INSTALL_BOOTSTRAP_PINS_SELECTED_IMMUTABLE_TAG' ($global:OlympusInstallerUxLauncherUrl -eq
            'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v9.8.7/scripts/launch-latest.ps1' -and
            -not (Test-Path -LiteralPath $global:OlympusInstallerUxDownloadedTo) -and
            [IO.File]::ReadAllText($dispatchLog) -match '(?i)-Action install .*?-Scope global .*?-Harness all' -and
            ($global:OlympusInstallerUxApiOrder -join ',') -ceq 'release-metadata,launcher-download')

        $global:OlympusInstallerUxLauncherUrl = $null
        $global:OlympusInstallerUxDownloadedTo = $null
        $global:OlympusInstallerUxApiOrder = @()
        $remoteUninstallBlock = [scriptblock]::Create([IO.File]::ReadAllText($uninstallEntry))
        & $remoteUninstallBlock -Project -Here -Harness codex
        Check 'REMOTE_UNINSTALL_BOOTSTRAP_PINS_SELECTED_IMMUTABLE_TAG' ($global:OlympusInstallerUxLauncherUrl -eq
            'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v9.8.7/scripts/launch-latest.ps1' -and
            -not (Test-Path -LiteralPath $global:OlympusInstallerUxDownloadedTo) -and
            [IO.File]::ReadAllText($dispatchLog) -match '(?i)-Action uninstall .*?-Scope project .*?-Harness codex' -and
            ($global:OlympusInstallerUxApiOrder -join ',') -ceq 'release-metadata,launcher-download')
        $global:OlympusInstallerUxRemoteBootstrapMode = $false

        $legacyLauncherSource = Join-Path $run 'old-launcher-fixture.ps1'
        [IO.File]::WriteAllText($legacyLauncherSource, "# old launcher without immutable metadata preflight`n", [Text.UTF8Encoding]::new($false))
        $global:OlympusInstallerUxLaunchSource = $legacyLauncherSource
        $dispatchBeforeLegacyBootstrap = [IO.File]::ReadAllText($dispatchLog)
        $global:OlympusInstallerUxRemoteBootstrapMode = $true
        $legacyBootstrapRejected = $false
        try { & $remoteInstallBlock -Global -Harness opencode }
        catch { $legacyBootstrapRejected = $_.Exception.Message -match 'LAUNCHER_BOOTSTRAP_CONTRACT_MISSING' }
        $global:OlympusInstallerUxRemoteBootstrapMode = $false
        Check 'REMOTE_BOOTSTRAP_REJECTS_LEGACY_LAUNCHER_WITHOUT_FALLBACK' ($legacyBootstrapRejected -and
            [IO.File]::ReadAllText($dispatchLog) -ceq $dispatchBeforeLegacyBootstrap)

        $global:OlympusInstallerUxLaunchSource = Join-Path $source 'scripts/launch-latest.ps1'
        $global:OlympusInstallerUxRelease = [pscustomobject]@{
            tag_name = 'v9.8.7'; immutable = $false; draft = $false; prerelease = $false; published_at = '2026-10-01T12:00:00Z'
        }
        $global:OlympusInstallerUxLauncherUrl = $null
        $global:OlympusInstallerUxDownloadedTo = $null
        $dispatchBeforeMutableBootstrap = [IO.File]::ReadAllText($dispatchLog)
        $global:OlympusInstallerUxRemoteBootstrapMode = $true
        $mutableBootstrapRejected = $false
        try { & $remoteUninstallBlock -Project -Here -Harness codex }
        catch { $mutableBootstrapRejected = $_.Exception.Message -match 'LATEST_RELEASE_MUTABLE' }
        $global:OlympusInstallerUxRemoteBootstrapMode = $false
        Check 'REMOTE_BOOTSTRAP_REJECTS_MUTABLE_RELEASE_BEFORE_DOWNLOAD_OR_EXECUTION' ($mutableBootstrapRejected -and
            $global:OlympusInstallerUxLauncherUrl -eq $null -and
            [IO.File]::ReadAllText($dispatchLog) -ceq $dispatchBeforeMutableBootstrap)

        # Exercise all three affected release-selection scripts with typed and
        # zoned values. ConvertFrom-Json mirrors the DateTime kinds produced by
        # PowerShell's JSON path without changing the machine's time zone.
        $stableInstant = [DateTimeOffset]::Parse('2026-10-01T12:00:00Z', [Globalization.CultureInfo]::InvariantCulture)
        $issueTimestamp = '2026-10-21T05:29:57Z'
        $issueDateTimeUtc = [DateTime]::Parse($issueTimestamp, [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind)
        $issueOffsetTimestamp = '2026-10-21T08:29:57+03:00'
        foreach ($timestampScript in @($installEntry, $uninstallEntry, (Join-Path $source 'scripts/launch-latest.ps1'))) {
            $convertedUtcDateTime = Invoke-IsolatedPublishedTimestampConverter $timestampScript $issueDateTimeUtc
            $convertedOffsetObject = Invoke-IsolatedPublishedTimestampConverter $timestampScript ([DateTimeOffset]$issueDateTimeUtc)
            $convertedUtcString = Invoke-IsolatedPublishedTimestampConverter $timestampScript $issueTimestamp
            $convertedOffsetString = Invoke-IsolatedPublishedTimestampConverter $timestampScript $issueOffsetTimestamp
            Check ("ISOLATED_UTC_TYPED_TIMESTAMP_PRESERVED_{0}" -f (Split-Path -Leaf $timestampScript)) (
                $convertedUtcDateTime -is [DateTimeOffset] -and
                $convertedUtcDateTime.UtcDateTime.Ticks -eq $issueDateTimeUtc.Ticks -and
                $convertedUtcDateTime.Offset -eq [TimeSpan]::Zero)
            Check ("ISOLATED_DATETIMEOFFSET_PRESERVED_{0}" -f (Split-Path -Leaf $timestampScript)) (
                $convertedOffsetObject -is [DateTimeOffset] -and
                $convertedOffsetObject.UtcDateTime.Ticks -eq $issueDateTimeUtc.Ticks)
            Check ("ISOLATED_ISO_Z_STRING_PRESERVED_{0}" -f (Split-Path -Leaf $timestampScript)) (
                $convertedUtcString.UtcDateTime.Ticks -eq $issueDateTimeUtc.Ticks)
            Check ("ISOLATED_ISO_OFFSET_STRING_PRESERVED_{0}" -f (Split-Path -Leaf $timestampScript)) (
                $convertedOffsetString.UtcDateTime.Ticks -eq $issueDateTimeUtc.Ticks)
        }
        # Simulate zone-less DateTimeOffset reparsing under several local-zone
        # offsets without changing the host's operating-system time zone.
        foreach ($zoneCase in @(
            [pscustomobject]@{ Id = 'UTC'; Zone = 'UTC' },
            [pscustomobject]@{ Id = 'PACIFIC'; Zone = 'Pacific Standard Time' },
            [pscustomobject]@{ Id = 'CENTRAL_EUROPE'; Zone = 'W. Europe Standard Time' },
            [pscustomobject]@{ Id = 'TOKYO'; Zone = 'Tokyo Standard Time' }
        )) {
            $simulatedSystemZone = [TimeZoneInfo]::FindSystemTimeZoneById($zoneCase.Zone)
            $wallClockWithoutKind = [DateTime]::SpecifyKind($issueDateTimeUtc, [DateTimeKind]::Unspecified)
            $legacyInterpretation = [DateTimeOffset]::new($wallClockWithoutKind,
                $simulatedSystemZone.GetUtcOffset($wallClockWithoutKind))
            $legacyChangedInstant = $legacyInterpretation.UtcDateTime.Ticks -ne $issueDateTimeUtc.Ticks
            $shouldChangeLegacyInstant = $simulatedSystemZone.GetUtcOffset($wallClockWithoutKind) -ne [TimeSpan]::Zero
            Check ("LEGACY_LOCAL_ZONE_INTERPRETATION_{0}" -f $zoneCase.Id) ($legacyChangedInstant -eq $shouldChangeLegacyInstant)
            foreach ($timestampScript in @($installEntry, $uninstallEntry, (Join-Path $source 'scripts/launch-latest.ps1'))) {
                $fixedInZone = Invoke-IsolatedPublishedTimestampConverter $timestampScript $issueDateTimeUtc
                Check ("FIXED_TYPED_UTC_INSTANT_INDEPENDENT_OF_{0}_{1}" -f $zoneCase.Id, (Split-Path -Leaf $timestampScript)) (
                    $fixedInZone.UtcDateTime.Ticks -eq $issueDateTimeUtc.Ticks)
            }
        }
        $utcDateTime = [DateTime]::Parse('2026-10-01T12:00:00Z', [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind)
        $offsetDateTimeOffset = $stableInstant.ToOffset([TimeSpan]::FromHours(2))
        $nearLimitTimestamp = [DateTimeOffset]::UtcNow.AddMinutes(4).ToString('o')
        $sameInstantFromJson = foreach ($isoTimestamp in @(
            '2026-10-01T12:00:00Z',
            '2026-10-01T15:00:00+03:00',
            '2026-10-01T05:00:00-07:00'
        )) {
            ('{"published_at":"' + $isoTimestamp + '"}' | ConvertFrom-Json).published_at
        }
        $validTimestampCases = @(
            [pscustomobject]@{ Id = 'DATETIME_UTC'; Value = $utcDateTime; ExpectedUtc = '2026-10-01T12:00:00' },
            [pscustomobject]@{ Id = 'DATETIMEOFFSET'; Value = $offsetDateTimeOffset; ExpectedUtc = '2026-10-01T12:00:00' },
            [pscustomobject]@{ Id = 'ISO_UTC_STRING'; Value = '2026-10-01T12:00:00Z'; ExpectedUtc = '2026-10-01T12:00:00' },
            [pscustomobject]@{ Id = 'ISO_OFFSET_STRING'; Value = '2026-10-01T14:00:00+02:00'; ExpectedUtc = '2026-10-01T12:00:00' },
            [pscustomobject]@{ Id = 'JSON_UTC_DATETIME'; Value = $sameInstantFromJson[0]; ExpectedUtc = '2026-10-01T12:00:00' },
            [pscustomobject]@{ Id = 'JSON_PLUS_THREE_OFFSET_DATETIME'; Value = $sameInstantFromJson[1]; ExpectedUtc = '2026-10-01T12:00:00' },
            [pscustomobject]@{ Id = 'JSON_MINUS_SEVEN_OFFSET_DATETIME'; Value = $sameInstantFromJson[2]; ExpectedUtc = '2026-10-01T12:00:00' },
            [pscustomobject]@{ Id = 'FUTURE_WITHIN_FIVE_MINUTES'; Value = $nearLimitTimestamp; ExpectedUtc = $null }
        )
        foreach ($entrypointAction in @('install', 'uninstall')) {
            foreach ($timestampCase in $validTimestampCases) {
                $bootstrapTimestamp = Invoke-MockedBootstrap $entrypointAction $timestampCase.Value
                Check ("BOOTSTRAP_{0}_{1}_ACCEPTED" -f $entrypointAction.ToUpperInvariant(), $timestampCase.Id) (
                    $bootstrapTimestamp.Code -eq 0 -and $bootstrapTimestamp.ApiOrder -ceq 'release-metadata,launcher-download' -and
                    [IO.File]::ReadAllText($dispatchLog) -match ("-Action {0}" -f $entrypointAction))
            }
        }

        $invalidTimestampCases = @(
            [pscustomobject]@{ Id = 'INVALID'; Value = 'not-a-date' },
            [pscustomobject]@{ Id = 'ZONELESS'; Value = '2026-10-01T12:00:00' },
            [pscustomobject]@{ Id = 'UNSPECIFIED_DATETIME'; Value = [DateTime]::SpecifyKind(
                [DateTime]::Parse('2026-10-01T12:00:00', [Globalization.CultureInfo]::InvariantCulture),
                [DateTimeKind]::Unspecified) },
            [pscustomobject]@{ Id = 'CLEARLY_FUTURE'; Value = [DateTimeOffset]::UtcNow.AddMinutes(10) }
        )
        foreach ($entrypointAction in @('install', 'uninstall')) {
            foreach ($timestampCase in $invalidTimestampCases) {
                $dispatchBeforeInvalidTimestamp = [IO.File]::ReadAllText($dispatchLog)
                $bootstrapTimestamp = Invoke-MockedBootstrap $entrypointAction $timestampCase.Value
                Check ("BOOTSTRAP_{0}_{1}_REJECTED_BEFORE_DOWNLOAD_OR_EXECUTION" -f $entrypointAction.ToUpperInvariant(), $timestampCase.Id) (
                    $bootstrapTimestamp.Code -ne 0 -and
                    $bootstrapTimestamp.Text -match 'LATEST_RELEASE_METADATA_INVALID' -and
                    $bootstrapTimestamp.ApiOrder -ceq 'release-metadata' -and
                    [IO.File]::ReadAllText($dispatchLog) -ceq $dispatchBeforeInvalidTimestamp)
            }
            foreach ($invalidReleaseFlags in @(
                [pscustomobject]@{ Id = 'MUTABLE'; Immutable = $false; Draft = $false; Prerelease = $false; Expected = 'LATEST_RELEASE_MUTABLE' },
                [pscustomobject]@{ Id = 'DRAFT'; Immutable = $true; Draft = $true; Prerelease = $false; Expected = 'LATEST_RELEASE_NOT_PUBLISHED' },
                [pscustomobject]@{ Id = 'PRERELEASE'; Immutable = $true; Draft = $false; Prerelease = $true; Expected = 'LATEST_RELEASE_NOT_PUBLISHED' }
            )) {
                $dispatchBeforeInvalidReleaseFlags = [IO.File]::ReadAllText($dispatchLog)
                $invalidFlagsResult = Invoke-MockedBootstrap $entrypointAction $utcDateTime `
                    $invalidReleaseFlags.Immutable $invalidReleaseFlags.Draft $invalidReleaseFlags.Prerelease
                Check ("BOOTSTRAP_{0}_{1}_REJECTED" -f $entrypointAction.ToUpperInvariant(), $invalidReleaseFlags.Id) (
                    $invalidFlagsResult.Code -ne 0 -and $invalidFlagsResult.Text -match $invalidReleaseFlags.Expected -and
                    $invalidFlagsResult.ApiOrder -ceq 'release-metadata' -and
                    [IO.File]::ReadAllText($dispatchLog) -ceq $dispatchBeforeInvalidReleaseFlags)
            }
        }

        $escapedMockBin = $mockBin.Replace("'", "''")
        $escapedInstallEntry = $installEntry.Replace("'", "''")
        $nativeCommand = '$env:PATH = ' + "'$escapedMockBin'" + ' + [IO.Path]::PathSeparator + $env:PATH; & ' +
            "'$escapedInstallEntry'" + ' -Project -Here -Harness all'
        $nativeOutput = (& $realPwsh -NoProfile -Command $nativeCommand 2>&1 | Out-String)
        $nativeExit = $LASTEXITCODE
        $nativeDispatch = [IO.File]::ReadAllText($dispatchLog)
        Check 'NATIVE_POWERSHELL_PARAMETERS' ($nativeExit -eq 0 -and
            $nativeDispatch -match '(?i)-Action install .*?-Scope project .*?-Harness all' -and
            $nativeOutput -notmatch 'ARGUMENTS_INVALID')

        foreach ($entry in @(
            [pscustomobject]@{ Id = 'NONINTERACTIVE_INSTALL_REJECTS_MISSING_ARGUMENTS'; Path = $installEntry },
            [pscustomobject]@{ Id = 'NONINTERACTIVE_UNINSTALL_REJECTS_MISSING_ARGUMENTS'; Path = $uninstallEntry }
        )) {
            $nonInteractive = Invoke-NonInteractiveEntry $entry.Path
            Check $entry.Id ($nonInteractive.Code -ne 0 -and $nonInteractive.Text -match 'ARGUMENTS_REQUIRED' -and
                $nonInteractive.Text -notmatch 'Choose 1, 2, or 3')
        }

        foreach ($entry in @(
            [pscustomobject]@{ Id = 'NONINTERACTIVE_PARTIAL_INSTALL_REJECTS_MISSING_HARNESS'; Path = $installEntry },
            [pscustomobject]@{ Id = 'NONINTERACTIVE_PARTIAL_UNINSTALL_REJECTS_MISSING_HARNESS'; Path = $uninstallEntry }
        )) {
            $nonInteractivePartial = Invoke-NonInteractiveEntry $entry.Path @('-Project', '-Here')
            Check $entry.Id ($nonInteractivePartial.Code -ne 0 -and $nonInteractivePartial.Text -match 'ARGUMENTS_REQUIRED' -and
                $nonInteractivePartial.Text -notmatch 'Choose 1, 2, or 3')
        }

        $nonInteractiveInstall = Invoke-MockedEntry -Entry $installEntry -Parameters @{ Project = $true; Here = $true; Harness = 'codex' }
        Check 'NONINTERACTIVE_COMPLETE_INSTALL_DOES_NOT_PROMPT' ($nonInteractiveInstall.Prompts -eq 0 -and
            [IO.File]::ReadAllText($dispatchLog) -match '(?i)-Action install .*?-Scope project .*?-Harness codex')

        $nonInteractiveUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ Global = $true; Harness = 'all' }
        Check 'NONINTERACTIVE_COMPLETE_UNINSTALL_DOES_NOT_PROMPT' ($nonInteractiveUninstall.Prompts -eq 0 -and
            [IO.File]::ReadAllText($dispatchLog) -match '(?i)-Action uninstall .*?-Scope global .*?-Harness all')

        $lastDispatch = [IO.File]::ReadAllText($dispatchLog)
        $invalidCases = @(
            [pscustomobject]@{ Id = 'INCOMPLETE_PROJECT_SCOPE_REJECTED'; Entry = $installEntry; Parameters = @{ Project = $true; Harness = 'all' } },
            [pscustomobject]@{ Id = 'FALSE_GLOBAL_SELECTION_REJECTED'; Entry = $uninstallEntry; Parameters = @{ Global = $false; Harness = 'all' } },
            [pscustomobject]@{ Id = 'EMPTY_INSTALL_PROJECT_PATH_REJECTED'; Entry = $installEntry; Parameters = @{ ProjectPath = ''; Harness = 'all' } },
            [pscustomobject]@{ Id = 'EMPTY_UNINSTALL_PROJECT_PATH_REJECTED'; Entry = $uninstallEntry; Parameters = @{ ProjectPath = ''; Harness = 'all' } },
            [pscustomobject]@{ Id = 'INVALID_INSTALL_HARNESS_REJECTED'; Entry = $installEntry; Parameters = @{ Project = $true; Here = $true; Harness = 'invalid' } },
            [pscustomobject]@{ Id = 'INVALID_UNINSTALL_HARNESS_REJECTED'; Entry = $uninstallEntry; Parameters = @{ Project = $true; Here = $true; Harness = 'invalid' } }
        )
        foreach ($entry in $invalidCases) {
            $failed = $false
            try { $null = Invoke-MockedEntry -Entry $entry.Entry -Parameters $entry.Parameters -Answers @() }
            catch { $failed = $_.Exception.Message -match 'ARGUMENTS_INVALID' }
            Check $entry.Id ($failed -and
                [IO.File]::ReadAllText($dispatchLog) -ceq $lastDispatch -and $global:OlympusInstallerUxReadHostCalls -eq 0)
        }

        foreach ($entry in @(
            [pscustomobject]@{ Id = 'CONTRADICTORY_INSTALL_SCOPE_OPTIONS_REJECTED'; Entry = $installEntry; Parameters = @{ Global = $true; ProjectPath = $otherTarget; Harness = 'all' } },
            [pscustomobject]@{ Id = 'CONTRADICTORY_UNINSTALL_SCOPE_OPTIONS_REJECTED'; Entry = $uninstallEntry; Parameters = @{ Global = $true; ProjectPath = $otherTarget; Harness = 'all' } }
        )) {
            $failed = $false
            try { $null = Invoke-MockedEntry -Entry $entry.Entry -Parameters $entry.Parameters -Answers @() }
            catch { $failed = $_.Exception -is [System.Management.Automation.ParameterBindingException] }
            Check $entry.Id ($failed -and
                [IO.File]::ReadAllText($dispatchLog) -ceq $lastDispatch -and $global:OlympusInstallerUxReadHostCalls -eq 0)
        }

        # Exercise the current launcher with controlled GitHub metadata and a
        # release-installer fixture; the fake pwsh command records, but never
        # executes, the installer invocation.
        $releaseTag = 'v9.8.7'
        $publishedAt = '2026-10-01T12:00:00Z'
        $global:OlympusInstallerUxInstallerText = "[string]`$Version = '$releaseTag'`n`$ReleaseVersion = '$releaseTag'`n scripts/project-uninstall.ps1`n"
        $global:OlympusInstallerUxRelease = [pscustomobject]@{
            tag_name = $releaseTag; immutable = $true; draft = $false; prerelease = $false; published_at = $publishedAt
        }
        $validLaunch = Invoke-MockedLauncher 'install' 'project' 'opencode' $otherTarget
        $validDispatch = [IO.File]::ReadAllText($dispatchLog)
        Check 'LAUNCHER_ACCEPTS_PUBLISHED_IMMUTABLE_RELEASE' ($validLaunch.Code -eq 0 -and
            $global:OlympusInstallerUxMetadataUrl -eq 'https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest' -and
            ($global:OlympusInstallerUxApiOrder -join ',') -ceq 'release-metadata,installer-download' -and
            $global:OlympusInstallerUxInstallerUrl -eq "https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$releaseTag/install.ps1" -and
            $validLaunch.Text -match "OLYMPUS_RELEASE_SELECTED: tag=$releaseTag immutable=true" -and
            $validLaunch.Text -match "OLYMPUS_RELEASE_EXECUTING: tag=$releaseTag" -and
            $validLaunch.Text -match "OLYMPUS_RELEASE_EXECUTED: tag=$releaseTag exit_code=0" -and
            $validDispatch -match "-Version $releaseTag" -and $validDispatch -match "-Harness opencode" -and
            $validDispatch -match [regex]::Escape($otherTarget))

        $validUninstall = Invoke-MockedLauncher 'uninstall' 'project' 'all' $otherTarget
        $uninstallDispatch = [IO.File]::ReadAllText($dispatchLog)
        Check 'LAUNCHER_EXECUTES_SELECTED_RELEASE_FOR_UNINSTALL' ($validUninstall.Code -eq 0 -and
            $uninstallDispatch -match "-Version $releaseTag" -and $uninstallDispatch -match '-Uninstall' -and
            $validUninstall.Text -match "OLYMPUS_RELEASE_EXECUTING: tag=$releaseTag")

        $global:OlympusInstallerUxInstallerText = "[string]`$Version = '$releaseTag'`n`$ReleaseVersion = '$releaseTag'`n scripts/project-uninstall.ps1`n"
        foreach ($timestampCase in $validTimestampCases) {
            $global:OlympusInstallerUxRelease = [pscustomobject]@{
                tag_name = $releaseTag; immutable = $true; draft = $false; prerelease = $false; published_at = $timestampCase.Value
            }
            $timestampLaunch = Invoke-MockedLauncher 'install' 'project' 'opencode' $hereTarget
            $selectedTimestampIsUtc = if ($timestampCase.ExpectedUtc) {
                $timestampLaunch.Text -match ("published_at={0}(?:\.\d+)?\+00:00" -f $timestampCase.ExpectedUtc)
            } else {
                $timestampLaunch.Text -match 'OLYMPUS_RELEASE_SELECTED:'
            }
            Check ("LAUNCHER_{0}_ACCEPTED_WITH_UTC_INSTANT" -f $timestampCase.Id) (
                $timestampLaunch.Code -eq 0 -and $selectedTimestampIsUtc -and
                $global:OlympusInstallerUxInstallerDownloadCount -eq 1)
        }

        $baselineDispatch = [IO.File]::ReadAllText($dispatchLog)
        $metadataFailures = @(
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_MUTABLE_RELEASE'
                Release = [pscustomobject]@{ tag_name=$releaseTag; immutable=$false; draft=$false; prerelease=$false; published_at=$publishedAt }
                Expected = 'LATEST_RELEASE_MUTABLE'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_INCOMPLETE_METADATA'
                Release = [pscustomobject]@{ tag_name=$releaseTag; draft=$false; prerelease=$false; published_at=$publishedAt }
                Expected = 'LATEST_RELEASE_METADATA_INCOMPLETE'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_MISSING_PUBLISHED_TIMESTAMP'
                Release = [pscustomobject]@{ tag_name=$releaseTag; immutable=$true; draft=$false; prerelease=$false }
                Expected = 'LATEST_RELEASE_METADATA_INCOMPLETE'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_UNPUBLISHED_RELEASE'
                Release = [pscustomobject]@{ tag_name=$releaseTag; immutable=$true; draft=$true; prerelease=$false; published_at=$publishedAt }
                Expected = 'LATEST_RELEASE_NOT_PUBLISHED'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_PRERELEASE'
                Release = [pscustomobject]@{ tag_name=$releaseTag; immutable=$true; draft=$false; prerelease=$true; published_at=$publishedAt }
                Expected = 'LATEST_RELEASE_NOT_PUBLISHED'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_INVALID_PUBLISHED_TIMESTAMP'
                Release = [pscustomobject]@{ tag_name=$releaseTag; immutable=$true; draft=$false; prerelease=$false; published_at='not-a-date' }
                Expected = 'LATEST_RELEASE_METADATA_INVALID'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_ZONELESS_PUBLISHED_TIMESTAMP'
                Release = [pscustomobject]@{ tag_name=$releaseTag; immutable=$true; draft=$false; prerelease=$false; published_at='2026-10-01T12:00:00' }
                Expected = 'LATEST_RELEASE_METADATA_INVALID'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_UNSPECIFIED_DATETIME'
                Release = [pscustomobject]@{ tag_name=$releaseTag; immutable=$true; draft=$false; prerelease=$false; published_at=[DateTime]::SpecifyKind(
                    [DateTime]::Parse('2026-10-01T12:00:00', [Globalization.CultureInfo]::InvariantCulture), [DateTimeKind]::Unspecified) }
                Expected = 'LATEST_RELEASE_METADATA_INVALID'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_CLEARLY_FUTURE_PUBLISHED_TIMESTAMP'
                Release = [pscustomobject]@{ tag_name=$releaseTag; immutable=$true; draft=$false; prerelease=$false; published_at=[DateTimeOffset]::UtcNow.AddMinutes(10) }
                Expected = 'LATEST_RELEASE_METADATA_INVALID'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_MUTABLE_BRANCH_TAG'
                Release = [pscustomobject]@{ tag_name='master'; immutable=$true; draft=$false; prerelease=$false; published_at=$publishedAt }
                Expected = 'LATEST_RELEASE_INVALID'
            },
            [pscustomobject]@{
                Id = 'LAUNCHER_REJECTS_PRERELEASE_TAG_MISLABELED_AS_STABLE'
                Release = [pscustomobject]@{ tag_name='v9.8.7-rc.1'; immutable=$true; draft=$false; prerelease=$false; published_at=$publishedAt }
                Expected = 'LATEST_RELEASE_METADATA_INCONSISTENT'
            }
        )
        foreach ($failureCase in $metadataFailures) {
            $global:OlympusInstallerUxRelease = $failureCase.Release
            $failure = Invoke-MockedLauncher 'install' 'global' 'opencode' $hereTarget
            $unchanged = [IO.File]::ReadAllText($dispatchLog) -ceq $baselineDispatch
            Check $failureCase.Id ($failure.Code -ne 0 -and $failure.Text -match $failureCase.Expected -and
                $global:OlympusInstallerUxInstallerDownloadCount -eq 0 -and $unchanged)
        }

        $global:OlympusInstallerUxRelease = [pscustomobject]@{
            tag_name = $releaseTag; immutable = $true; draft = $false; prerelease = $false; published_at = $publishedAt
        }
        $global:OlympusInstallerUxInstallerText = "[string]`$Version = 'v9.8.6'`n`$ReleaseVersion = 'v9.8.6'`n"
        $identityMismatch = Invoke-MockedLauncher 'install' 'project' 'opencode' $hereTarget
        Check 'LAUNCHER_REJECTS_INSTALLER_VERSION_MISMATCH_WITHOUT_EXECUTION' ($identityMismatch.Code -ne 0 -and
            $identityMismatch.Text -match 'LATEST_RELEASE_IDENTITY_MISMATCH' -and
            $global:OlympusInstallerUxInstallerDownloadCount -eq 1 -and
            [IO.File]::ReadAllText($dispatchLog) -ceq $baselineDispatch)

        $global:OlympusInstallerUxRelease = [pscustomobject]@{
            tag_name = $releaseTag; immutable = $true; draft = $false; prerelease = $false; published_at = $publishedAt
        }
        $global:OlympusInstallerUxInstallerText = "[string]`$Version = '$releaseTag'`n`$ReleaseVersion = 'v9.8.6'`n"
        $releaseMarkerMismatch = Invoke-MockedLauncher 'install' 'project' 'opencode' $hereTarget
        Check 'LAUNCHER_REJECTS_RELEASE_MARKER_MISMATCH_WITHOUT_EXECUTION' ($releaseMarkerMismatch.Code -ne 0 -and
            $releaseMarkerMismatch.Text -match 'LATEST_RELEASE_IDENTITY_MISMATCH' -and
            [IO.File]::ReadAllText($dispatchLog) -ceq $baselineDispatch)

        $readmeText = [IO.File]::ReadAllText((Join-Path $script:source 'README.md'))
        $installationText = [IO.File]::ReadAllText((Join-Path $script:source 'docs/INSTALLATION.md'))
        $expectedPublicCommands = @(
            "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.11/install-olympus.ps1')))"
            "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.11/uninstall-olympus.ps1')))"
        )
        $expectedPublicCommandPattern = '^(?:' + [regex]::Escape($expectedPublicCommands[0]) + '|' + [regex]::Escape($expectedPublicCommands[1]) + ')$'
        $readmeCommands = @([regex]::Matches($readmeText, '(?im)^.*$') | Where-Object { $_.Value.Trim() -match $expectedPublicCommandPattern })
        Check 'README_HAS_EXACTLY_TWO_PUBLIC_COMMANDS' ($readmeCommands.Count -eq 2 -and
            $readmeCommands[0].Value.Trim() -ceq $expectedPublicCommands[0] -and
            $readmeCommands[1].Value.Trim() -ceq $expectedPublicCommands[1] -and
            -not $readmeText.Contains('/v0.4.12/install-olympus.ps1') -and
            -not $readmeText.Contains('/v0.4.12/uninstall-olympus.ps1'))
        $requirementsIndex = $readmeText.IndexOf('## Requirements', [StringComparison]::Ordinal)
        $firstCommandIndex = if ($readmeCommands.Count -gt 0) { $readmeCommands[0].Index } else { -1 }
        Check 'README_PREREQUISITES_PRECEDE_FIRST_COMMAND' ($requirementsIndex -ge 0 -and $firstCommandIndex -gt $requirementsIndex)
        Check 'README_KEEPS_COMPACT_INSTALLATION_GUIDE_LINK' ($readmeText.Contains('[installation, parameters, safety, and troubleshooting](docs/INSTALLATION.md)'))

        Check 'INSTALLATION_DOC_COVERS_INTERACTIVE_AND_PARTIAL_SELECTION' ($installationText.Contains('asks for scope and harness') -and
            $installationText.Contains('asks only for the missing values') -and $installationText.Contains('ARGUMENTS_REQUIRED'))
        Check 'INSTALLATION_DOC_COVERS_PUBLISHED_BOOTSTRAP_INVOCATION' (
            $installationText.Contains($expectedPublicCommands[0]) -and
            $installationText.Contains($expectedPublicCommands[1]) -and
            $installationText.Contains('ValidateNotNullOrEmpty'))
        Check 'INSTALLATION_DOC_HAS_ALL_HARNESSES_AND_SPACED_PATHS' ($installationText.Contains('-Harness opencode') -and
            $installationText.Contains('-Harness codex') -and $installationText.Contains('-Harness all') -and
            $installationText.Contains('C:\Users\Ada Lovelace\source\Sample Project'))
        Check 'INSTALLATION_DOC_COVERS_REQUIREMENTS_COMPATIBILITY_AND_LIMITS' ($installationText.Contains('PowerShell 7') -and
            $installationText.Contains('Git is required') -and $installationText.Contains('Linux and macOS are not qualified') -and
            $installationText.Contains('FROZEN COMPATIBILITY'))
        Check 'INSTALLATION_DOC_COVERS_LOCAL_CHECKOUT_ALTERNATIVE' ($installationText.Contains('local source checkout') -and
            $installationText.Contains('-SourceRoot $source'))
        Check 'INSTALLATION_DOC_DISTINGUISHES_LATEST_TAG_IDENTITY_AND_INTEGRITY' ($installationText.Contains('releases/latest') -and
            $installationText.Contains('does **not** preselect the final release installer tag') -and
            $installationText.Contains('returned tag') -and $installationText.Contains('immutable` field is a platform assertion') -and
            $installationText.Contains('published SHA-256') -and $installationText.Contains('executable code'))

        $installBootstrapText = [IO.File]::ReadAllText($installEntry)
        $uninstallBootstrapText = [IO.File]::ReadAllText($uninstallEntry)
        $launcherText = [IO.File]::ReadAllText((Join-Path $script:source 'scripts/launch-latest.ps1'))
        $installerSourceText = [IO.File]::ReadAllText($installer)
        Check 'RELEASE_FLOW_SELECTS_LATEST_AND_DOWNLOADS_BY_TAG_NOT_BRANCH' (
            $installBootstrapText.Contains('/releases/latest') -and $uninstallBootstrapText.Contains('/releases/latest') -and
            $installBootstrapText.Contains('$tag/scripts/launch-latest.ps1') -and $uninstallBootstrapText.Contains('$tag/scripts/launch-latest.ps1') -and
            $launcherText.Contains('/$tag/install.ps1') -and $installerSourceText.Contains('/archive/refs/tags/$Version.zip') -and
            $launcherText.Contains('LATEST_RELEASE_IDENTITY_MISMATCH') -and
            $launcherText -notmatch 'raw\.githubusercontent\.com/Edulynch/OpenCode-OlympusAgents/(?:main|master)/')
    } finally { Pop-Location }

    # Preserve the old twelve public compatibility scripts while the new pair is adopted.
    $compatibilityCount = 0
    foreach ($action in @('install', 'uninstall')) {
        foreach ($scope in @('project', 'global')) {
            foreach ($harness in @('opencode', 'codex', 'all')) {
                $path = Join-Path $source "$action/$scope/$harness.ps1"
                if ((Test-Path -LiteralPath $path -PathType Leaf) -and
                    [IO.File]::ReadAllText($path).Contains('scripts/launch-latest.ps1')) { $compatibilityCount++ }
            }
        }
    }
    Check 'TWELVE_COMPATIBILITY_ENTRYPOINTS' ($compatibilityCount -eq 12)

    # Exercise the existing ownership/hash-protected uninstall through install.ps1.
    $env:PATH = $originalPath
    $safeTarget = New-Project 'safe-uninstall'
    Write-ProjectManifest $safeTarget
    $userFile = Join-Path $safeTarget '.serena/project.yml'
    [IO.Directory]::CreateDirectory((Split-Path -Parent $userFile)) | Out-Null
    [IO.File]::WriteAllText($userFile, "user-owned`n", [Text.UTF8Encoding]::new($false))
    $safe = Invoke-RealUninstall $safeTarget
    Check 'SAFE_UNINSTALL_REMOVES_OWNED_ONLY' ($safe.Code -eq 0 -and
        -not (Test-Path -LiteralPath (Join-Path $safeTarget '.opencode/agents/kael.md')) -and
        -not (Test-Path -LiteralPath (Join-Path $safeTarget 'opencode.jsonc')) -and
        -not (Test-Path -LiteralPath (Join-Path $safeTarget '.opencode/orchestrator-install.json')) -and
        [IO.File]::ReadAllText($userFile) -ceq "user-owned`n")

    $legacyTarget = New-Project 'legacy-version-uninstall'
    Write-ProjectManifest $legacyTarget -Legacy
    $legacyUserFile = Join-Path $legacyTarget 'user-notes.txt'
    [IO.File]::WriteAllText($legacyUserFile, "legacy user data`n", [Text.UTF8Encoding]::new($false))
    $legacyUninstall = Invoke-RealUninstall $legacyTarget
    Check 'LEGACY_PROJECT_MANIFEST_UNINSTALLS_OWNED_ONLY' ($legacyUninstall.Code -eq 0 -and
        -not (Test-Path -LiteralPath (Join-Path $legacyTarget '.opencode/agents/kael.md')) -and
        -not (Test-Path -LiteralPath (Join-Path $legacyTarget 'opencode.jsonc')) -and
        -not (Test-Path -LiteralPath (Join-Path $legacyTarget '.opencode/orchestrator-install.json')) -and
        [IO.File]::ReadAllText($legacyUserFile) -ceq "legacy user data`n")

    $legacyGlobalRoot = Join-Path $run 'legacy global config'
    $legacyGlobalManaged = Join-Path $legacyGlobalRoot 'agents/kael.md'
    $legacyGlobalUserFile = Join-Path $legacyGlobalRoot 'user-settings.json'
    [IO.Directory]::CreateDirectory((Split-Path -Parent $legacyGlobalManaged)) | Out-Null
    [IO.File]::WriteAllText($legacyGlobalManaged, "owned legacy global agent`n", [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($legacyGlobalUserFile, "user global settings`n", [Text.UTF8Encoding]::new($false))
    $legacyGlobalManifestPath = Join-Path $legacyGlobalRoot 'olympus/orchestrator-install.json'
    [IO.Directory]::CreateDirectory((Split-Path -Parent $legacyGlobalManifestPath)) | Out-Null
    $legacyGlobalManifest = @{
        schema_version = 1; scope = 'global'; installed_version = 'previous-release'; installed_harnesses = @('opencode')
        managed_files = @(@{ path = 'agents/kael.md'; sha256 = (Get-FileHash -LiteralPath $legacyGlobalManaged -Algorithm SHA256).Hash.ToLowerInvariant() })
    } | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($legacyGlobalManifestPath, $legacyGlobalManifest, [Text.UTF8Encoding]::new($false))
    $legacyGlobalUninstall = Invoke-RealGlobalUninstall $legacyGlobalRoot
    Check 'LEGACY_GLOBAL_MANIFEST_UNINSTALLS_OWNED_ONLY' ($legacyGlobalUninstall.Code -eq 0 -and
        -not (Test-Path -LiteralPath $legacyGlobalManaged) -and -not (Test-Path -LiteralPath $legacyGlobalManifestPath) -and
        [IO.File]::ReadAllText($legacyGlobalUserFile) -ceq "user global settings`n")

    $unsupportedGlobalRoot = Join-Path $run 'unsupported legacy global config'
    $unsupportedGlobalManaged = Join-Path $unsupportedGlobalRoot 'agents/kael.md'
    [IO.Directory]::CreateDirectory((Split-Path -Parent $unsupportedGlobalManaged)) | Out-Null
    [IO.File]::WriteAllText($unsupportedGlobalManaged, "preserve unsupported old resource`n", [Text.UTF8Encoding]::new($false))
    $unsupportedGlobalManifestPath = Join-Path $unsupportedGlobalRoot 'olympus/orchestrator-install.json'
    [IO.Directory]::CreateDirectory((Split-Path -Parent $unsupportedGlobalManifestPath)) | Out-Null
    $unsupportedGlobalManifest = @{
        schema_version = 1; scope = 'global'; managed_files = @(@{ path = 'agents/kael.md'; sha256 = (Get-FileHash -LiteralPath $unsupportedGlobalManaged -Algorithm SHA256).Hash.ToLowerInvariant() })
    } | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($unsupportedGlobalManifestPath, $unsupportedGlobalManifest, [Text.UTF8Encoding]::new($false))
    $unsupportedGlobal = Invoke-RealGlobalUninstall $unsupportedGlobalRoot
    Check 'UNSUPPORTED_LEGACY_GLOBAL_MANIFEST_BLOCKED_READ_ONLY' ($unsupportedGlobal.Code -ne 0 -and
        $unsupportedGlobal.Text -match 'GLOBAL_HARNESS_FAILED|installed_harnesses' -and
        (Test-Path -LiteralPath $unsupportedGlobalManaged) -and (Test-Path -LiteralPath $unsupportedGlobalManifestPath))

    $driftTarget = New-Project 'drift-uninstall'
    Write-ProjectManifest $driftTarget $true
    $drift = Invoke-RealUninstall $driftTarget
    Check 'SAFE_UNINSTALL_REFUSES_DRIFT_BEFORE_DELETE' ($drift.Code -ne 0 -and
        $drift.Text -match 'MANAGED_FILE_DRIFT' -and
        (Test-Path -LiteralPath (Join-Path $driftTarget '.opencode/agents/kael.md')) -and
        (Test-Path -LiteralPath (Join-Path $driftTarget 'opencode.jsonc')) -and
        (Test-Path -LiteralPath (Join-Path $driftTarget '.opencode/orchestrator-install.json')))

    Write-Output 'INSTALLER UX QUALIFICATION: PASS'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'INSTALLER UX QUALIFICATION: FAIL'
    exit 1
} finally {
    $env:PATH = $originalPath
    if ($null -eq $originalDispatchLog) { Remove-Item Env:OLYMPUS_ENTRYPOINT_LOG -ErrorAction SilentlyContinue }
    else { $env:OLYMPUS_ENTRYPOINT_LOG = $originalDispatchLog }
    if (Test-Path -LiteralPath $run) {
        Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction SilentlyContinue
    }
}
