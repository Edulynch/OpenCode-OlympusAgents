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
$originalPath = $env:PATH
$originalDispatchLog = $env:OLYMPUS_ENTRYPOINT_LOG
$realPwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source

function Check([string]$id, [bool]$condition) {
    if (-not $condition) { throw "$id FAIL" }
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

function Write-ProjectManifest([string]$Target, [bool]$Drift = $false) {
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
        installed_harnesses = @('opencode')
        managed_files = @($entries)
    } | ConvertTo-Json -Depth 10
    $manifestPath = Join-Path $Target '.opencode/orchestrator-install.json'
    [IO.File]::WriteAllText($manifestPath, $manifest + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
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

function Invoke-NonInteractiveEntry([string]$Entry) {
    $output = (& $script:realPwsh -NoProfile -NonInteractive -File $Entry 2>&1 | Out-String)
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
    param([string]$Uri, [string]$OutFile)
    $global:OlympusInstallerUxLauncherUrl = $Uri
    $global:OlympusInstallerUxDownloadedTo = $OutFile
    Copy-Item -LiteralPath $global:OlympusInstallerUxLaunchSource -Destination $OutFile -Force
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

        $interactiveUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{} -Answers @('1', '2')
        Check 'INTERACTIVE_UNINSTALL_PROMPTS_SCOPE_AND_HARNESS' ($interactiveUninstall.Prompts -eq 2 -and
            $interactiveUninstall.Text -match '(?i)-Action uninstall .*?-Scope project .*?-Harness codex')

        $pathUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ ProjectPath = $otherTarget; Harness = 'all' }
        Check 'DIRECT_UNINSTALL_PROJECT_PATH' ($pathUninstall.Prompts -eq 0 -and
            $pathUninstall.Text -match '(?i)-Action uninstall .*?-Scope project .*?-Harness all' -and
            $pathUninstall.Text.Contains($otherTarget))

        $globalUninstall = Invoke-MockedEntry -Entry $uninstallEntry -Parameters @{ Global = $true; Harness = 'opencode' }
        Check 'DIRECT_UNINSTALL_GLOBAL' ($globalUninstall.Prompts -eq 0 -and
            $globalUninstall.Text -match '(?i)-Action uninstall .*?-Scope global .*?-Harness opencode')

        # IEX has no script path; both public entries must fetch the existing immutable launcher and clean it up.
        $global:OlympusInstallerUxLaunchSource = Join-Path $source 'scripts/launch-latest.ps1'
        $global:OlympusInstallerUxLauncherUrl = $null
        $global:OlympusInstallerUxDownloadedTo = $null
        $remoteInstallBlock = [scriptblock]::Create([IO.File]::ReadAllText($installEntry))
        & $remoteInstallBlock -Global -Harness all
        Check 'REMOTE_INSTALL_FALLBACK_USES_EXISTING_LAUNCHER' ($global:OlympusInstallerUxLauncherUrl -eq
            'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/scripts/launch-latest.ps1' -and
            -not (Test-Path -LiteralPath $global:OlympusInstallerUxDownloadedTo) -and
            [IO.File]::ReadAllText($dispatchLog) -match '(?i)-Action install .*?-Scope global .*?-Harness all')

        $global:OlympusInstallerUxLauncherUrl = $null
        $global:OlympusInstallerUxDownloadedTo = $null
        $remoteUninstallBlock = [scriptblock]::Create([IO.File]::ReadAllText($uninstallEntry))
        & $remoteUninstallBlock -Project -Here -Harness codex
        Check 'REMOTE_UNINSTALL_FALLBACK_USES_EXISTING_LAUNCHER' ($global:OlympusInstallerUxLauncherUrl -eq
            'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/scripts/launch-latest.ps1' -and
            -not (Test-Path -LiteralPath $global:OlympusInstallerUxDownloadedTo) -and
            [IO.File]::ReadAllText($dispatchLog) -match '(?i)-Action uninstall .*?-Scope project .*?-Harness codex')

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

        $lastDispatch = [IO.File]::ReadAllText($dispatchLog)
        $invalidCases = @(
            [pscustomobject]@{ Id = 'INCOMPLETE_PROJECT_SCOPE_REJECTED'; Entry = $installEntry; Parameters = @{ Project = $true; Harness = 'all' } },
            [pscustomobject]@{ Id = 'DIRECT_HARNESS_REQUIRED'; Entry = $uninstallEntry; Parameters = @{ Global = $true } }
        )
        foreach ($entry in $invalidCases) {
            $failed = $false
            try { $null = Invoke-MockedEntry -Entry $entry.Entry -Parameters $entry.Parameters -Answers @() }
            catch { $failed = $_.Exception.Message -match 'ARGUMENTS_INVALID' }
            Check $entry.Id ($failed -and
                [IO.File]::ReadAllText($dispatchLog) -ceq $lastDispatch -and $global:OlympusInstallerUxReadHostCalls -eq 0)
        }
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
