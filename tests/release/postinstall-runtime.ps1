[CmdletBinding()]
param([string]$SourceRoot = (Join-Path $PSScriptRoot '../..'))

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceRoot -ErrorAction Stop).Path
$installer = Join-Path $source 'install.ps1'
$installerText = [IO.File]::ReadAllText($installer)
$defaultVersion = [regex]::Match($installerText, "(?m)^\s*\[string\]\`$Version\s*=\s*'([^']+)'")
$releaseVersion = [regex]::Match($installerText, "(?m)^\s*\`$ReleaseVersion\s*=\s*'([^']+)'")
if (-not $defaultVersion.Success -or -not $releaseVersion.Success -or
    $defaultVersion.Groups[1].Value -cne $releaseVersion.Groups[1].Value) {
    throw 'TEST_SOURCE_VERSION_INVALID: installer identity fields are missing or disagree.'
}
$candidateVersion = $defaultVersion.Groups[1].Value
$candidateVersionPattern = [regex]::Escape($candidateVersion)
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('olympus-132-postinstall-' + [guid]::NewGuid().ToString('N'))
$runCreated = $false
$utf8 = [Text.UTF8Encoding]::new($false)
$envNames = @('PATH','TEMP','TMP','APPDATA','LOCALAPPDATA','USERPROFILE','HOME',
    'OPENCODE_CONFIG_DIR','OPENCODE_DATA_DIR','OPENCODE_CACHE_DIR','OPENCODE_STATE_DIR',
    'OLYMPUS_CONFIG_HOME','OLYMPUS_CONFIG_FILE','OLYMPUS_132_FIXTURE_ROOT','OLYMPUS_132_RUNTIME_MODE',
    'XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_STATE_HOME')
$originalEnvironment = @{}
foreach ($name in $envNames) { $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$originalUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$originalMachinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')

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

function Invoke-Installer([string]$target, [string]$cliRoot, [string]$pathStore, [switch]$VerifyOnly) {
    $arguments = @('-NoProfile','-File',$installer,'-SourceRoot',$source,'-Target',$target,
        '-CliInstallRoot',$cliRoot,'-CliPathStorePath',$pathStore)
    if ($VerifyOnly) { $arguments += '-VerifyOnly' }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $text = (& pwsh @arguments 2>&1 | Out-String)
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    return [pscustomobject]@{ Text=$text; Code=$code }
}

function Copy-InvalidModelSource([string]$destination) {
    foreach ($directory in @('scripts','.opencode','.opencode/plugins','.opencode/scripts','olympus/core')) {
        [IO.Directory]::CreateDirectory((Join-Path $destination $directory)) | Out-Null
    }
    foreach ($relative in @('scripts/bootstrap.ps1','scripts/target-writer-lock.ps1','opencode.jsonc','olympus/core/models-dev.json')) {
        $target = Join-Path $destination ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        Copy-Item -LiteralPath (Join-Path $source ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)) -Destination $target
    }
    Copy-Item -LiteralPath (Join-Path $source '.opencode/agents') -Destination (Join-Path $destination '.opencode/agents') -Recurse
    Copy-Item -LiteralPath (Join-Path $source '.opencode/plugins/olympus-activity') -Destination (Join-Path $destination '.opencode/plugins/olympus-activity') -Recurse
    Copy-Item -LiteralPath (Join-Path $source '.opencode/scripts/worktree-setup.ps1') -Destination (Join-Path $destination '.opencode/scripts/worktree-setup.ps1')
    $agent = Join-Path $destination '.opencode/agents/kael.md'
    $text = [IO.File]::ReadAllText($agent)
    $changed = [regex]::new('(?m)^mode: primary\s*$').Replace($text, 'mode: invalid', 1)
    if ($changed -ceq $text) { throw 'STATIC_FIXTURE_SETUP_FAIL: Could not invalidate the generated source role metadata.' }
    [IO.File]::WriteAllText($agent, $changed, $utf8)
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'PLATFORM_UNQUALIFIED: This focused installer test requires Windows.' }
    if (Test-Path -LiteralPath $run) { throw "TEMP_PATH_PREEXISTS: refusing to use $run" }
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $runCreated = $true

    $profile = Join-Path $run 'profile'
    $mockBin = Join-Path $run 'mock-bin'
    $systemTemp = Join-Path $run 'system-temp'
    foreach ($path in @($profile,$mockBin,$systemTemp)) { [IO.Directory]::CreateDirectory($path) | Out-Null }
    foreach ($name in @('appdata','localappdata','opencode-config','opencode-data','opencode-cache','opencode-state',
            'olympus-config','xdg-config','xdg-data','xdg-cache','xdg-state')) {
        [IO.Directory]::CreateDirectory((Join-Path $run $name)) | Out-Null
    }
    foreach ($mapping in @(
        @('TEMP',$systemTemp), @('TMP',$systemTemp), @('APPDATA',(Join-Path $run 'appdata')),
        @('LOCALAPPDATA',(Join-Path $run 'localappdata')), @('USERPROFILE',$profile), @('HOME',$profile),
        @('OPENCODE_CONFIG_DIR',(Join-Path $run 'opencode-config')), @('OPENCODE_DATA_DIR',(Join-Path $run 'opencode-data')),
        @('OPENCODE_CACHE_DIR',(Join-Path $run 'opencode-cache')), @('OPENCODE_STATE_DIR',(Join-Path $run 'opencode-state')),
        @('OLYMPUS_CONFIG_HOME',(Join-Path $run 'olympus-config')), @('OLYMPUS_CONFIG_FILE',''),
        @('XDG_CONFIG_HOME',(Join-Path $run 'xdg-config')), @('XDG_DATA_HOME',(Join-Path $run 'xdg-data')),
        @('XDG_CACHE_HOME',(Join-Path $run 'xdg-cache')), @('XDG_STATE_HOME',(Join-Path $run 'xdg-state')),
        @('OLYMPUS_132_FIXTURE_ROOT',$run), @('OLYMPUS_132_RUNTIME_MODE','config-fails'))) {
        [Environment]::SetEnvironmentVariable([string]$mapping[0], [string]$mapping[1], 'Process')
    }

    $fixture = @'
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Command)
Set-StrictMode -Version Latest
$log = Join-Path $env:OLYMPUS_132_FIXTURE_ROOT 'opencode-calls.log'
$name = $Command -join ' '
if ($name -eq 'debug config' -and $env:OLYMPUS_132_RUNTIME_MODE -eq 'config-fails') {
    [IO.File]::AppendAllText($log, "$name exit=23`n")
    exit 23
}
if ($name -eq 'debug config') {
    [IO.File]::AppendAllText($log, "$name exit=0`n")
    Write-Output '[]'
    exit 0
}
if ($name -eq 'debug agents' -and $env:OLYMPUS_132_RUNTIME_MODE -eq 'agents-invalid-json') {
    [IO.File]::AppendAllText($log, "$name exit=0 invalid-json`n")
    Write-Output '{'
    exit 0
}
if ($name -eq 'debug agents') {
    [IO.File]::AppendAllText($log, "$name exit=0`n")
    Write-Output '[]'
    exit 0
}
if ($name -eq '--version') {
    [IO.File]::AppendAllText($log, "$name exit=0`n")
    Write-Output 'OpenCode issue132 fixture'
    exit 0
}
[IO.File]::AppendAllText($log, "$name exit=2 unsupported`n")
exit 2
'@
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.ps1'), $fixture, $utf8)
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), "@echo off`r`npwsh -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n", [Text.Encoding]::ASCII)
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $originalEnvironment['PATH']

    $target = New-Target 'config-failure'
    $cliRoot = Join-Path $run 'cli-config-failure'
    $pathStore = Join-Path $cliRoot 'path-store.txt'
    $install = Invoke-Installer $target $cliRoot $pathStore
    $logPath = Join-Path $run 'opencode-calls.log'
    $calls = if (Test-Path -LiteralPath $logPath) { @(Get-Content -LiteralPath $logPath) } else { @() }
    $failureEvidence = @($install.Text -split '\r?\n' | Where-Object { $_ -match 'OPENCODE_VALIDATION_FAILED|BOOTSTRAP_FAILED' } | Select-Object -First 1)
    $cliCreated = Test-Path -LiteralPath (Join-Path $cliRoot 'bin/olympus.cmd') -PathType Leaf
    Write-Output "DEBUG_CONFIG_RED_CASE: installer_exit=$($install.Code); cli_created=$cliCreated; fixture_log=$($calls -join ','); failure=$($failureEvidence -join '')"
    $warning = "OLYMPUS_RUNTIME_VALIDATION_WARNING: OpenCode runtime configuration and effective agents could not be verified; installation continues. Run 'olympus doctor' for static checks."
    Check 'P1_RUNTIME_CONFIG_FAILURE_IS_WARNING' ($install.Code -eq 0 -and $install.Text.Contains($warning) -and
        $install.Text -match "OLYMPUS_INSTALL: $candidateVersionPattern READY_OR_NO_CHANGES" -and
        @($calls | Where-Object { $_ -ceq 'debug config exit=23' }).Count -eq 1 -and $cliCreated -and
        $install.Text -notmatch '(?i)runtime[^\r\n]*\bPASS\b')
    $cliBin = Join-Path $cliRoot 'bin'
    Check 'P2_ISOLATED_GLOBAL_CLI_CREATED' ((Test-Path -LiteralPath (Join-Path $cliBin 'olympus.cmd') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path (Join-Path $cliRoot 'versions') (Join-Path $candidateVersion 'olympus-cli-manifest.json')) -PathType Leaf) -and
        (Test-Path -LiteralPath $pathStore -PathType Leaf) -and
        [IO.File]::ReadAllText($pathStore).Contains($cliBin))

    $beforeVerifyCalls = @($calls | Where-Object { $_ -match '^debug ' }).Count
    $verify = Invoke-Installer $target $cliRoot $pathStore -VerifyOnly
    $calls = @(Get-Content -LiteralPath $logPath)
    Check 'P3_VERIFYONLY_STATIC_AND_RUNTIME_READ_ONLY' ($verify.Code -eq 0 -and
        $verify.Text -match "OLYMPUS_VERIFY: $candidateVersionPattern PASS" -and
        @($calls | Where-Object { $_ -match '^debug ' }).Count -eq $beforeVerifyCalls)

    $agentPath = Join-Path $target '.opencode/agents/kael.md'
    [IO.File]::AppendAllText($agentPath, "`n# task fixture drift`n", $utf8)
    $driftHash = (Get-FileHash -LiteralPath $agentPath -Algorithm SHA256).Hash
    $manifestPath = Join-Path $target '.opencode/orchestrator-install.json'
    $manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
    $driftInstall = Invoke-Installer $target $cliRoot $pathStore
    Check 'P4_HASH_DRIFT_REJECTED_WITHOUT_OVERWRITE' ($driftInstall.Code -ne 0 -and
        $driftInstall.Text -match 'MANAGED_FILE_DRIFT' -and
        (Get-FileHash -LiteralPath $agentPath -Algorithm SHA256).Hash -ceq $driftHash -and
        (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash -ceq $manifestHash)

    $conflict = New-Target 'unowned-config'
    $conflictPath = Join-Path $conflict 'opencode.jsonc'
    [IO.File]::WriteAllText($conflictPath, '{"user_owned":true}' + "`n", $utf8)
    $conflictHash = (Get-FileHash -LiteralPath $conflictPath -Algorithm SHA256).Hash
    $conflictCli = Join-Path $run 'cli-unowned-config'
    $conflictResult = Invoke-Installer $conflict $conflictCli (Join-Path $conflictCli 'path-store.txt')
    Check 'P5_UNOWNED_DESTINATION_REJECTED_UNCHANGED' ($conflictResult.Code -ne 0 -and
        $conflictResult.Text -match 'INSTALL_CONFLICT' -and
        (Get-FileHash -LiteralPath $conflictPath -Algorithm SHA256).Hash -ceq $conflictHash -and
        -not (Test-Path -LiteralPath (Join-Path $conflict '.opencode/orchestrator-install.json')) -and
        -not (Test-Path -LiteralPath $conflictCli))

    $invalidSource = Join-Path $run 'invalid-static-source-copy'
    Copy-InvalidModelSource $invalidSource
    $staticTarget = New-Target 'invalid-static-target'
    $debugCallsBeforeStatic = @($calls | Where-Object { $_ -match '^debug ' }).Count
    $bootstrap = Join-Path $invalidSource 'scripts/bootstrap.ps1'
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $staticOutput = (& pwsh -NoProfile -File $bootstrap -Target $staticTarget -Harness opencode 2>&1 | Out-String)
        $staticExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    $calls = @(Get-Content -LiteralPath $logPath)
    $staticPass = $staticExit -ne 0 -and
        $staticOutput -match 'SOURCE_AGENT_MODEL_INVALID' -and
        $staticOutput -notmatch 'OLYMPUS_RUNTIME_VALIDATION_WARNING' -and
        @($calls | Where-Object { $_ -match '^debug ' }).Count -eq $debugCallsBeforeStatic
    if (-not $staticPass) {
        Write-Output "STATIC_SOURCE_CASE: exit=$staticExit; output=$(($staticOutput -replace '\s+',' ').Trim()); debug_calls=$(@($calls | Where-Object { $_ -match '^debug ' }).Count)"
    }
    Check 'P6_STATIC_SOURCE_METADATA_STAYS_MANDATORY' $staticPass

    $agentsTarget = New-Target 'invalid-runtime-agents-json'
    $agentsCli = Join-Path $run 'cli-invalid-runtime-agents'
    $env:OLYMPUS_132_RUNTIME_MODE = 'agents-invalid-json'
    $agentsInstall = Invoke-Installer $agentsTarget $agentsCli (Join-Path $agentsCli 'path-store.txt')
    $calls = @(Get-Content -LiteralPath $logPath)
    Check 'P7_RUNTIME_AGENT_JSON_FAILURE_IS_WARNING' ($agentsInstall.Code -eq 0 -and
        $agentsInstall.Text.Contains($warning) -and
        @($calls | Where-Object { $_ -ceq 'debug agents exit=0 invalid-json' }).Count -eq 1 -and
        (Test-Path -LiteralPath (Join-Path $agentsCli 'bin/olympus.cmd') -PathType Leaf))

    Check 'P8_PERSISTENT_PATH_UNCHANGED' ([Environment]::GetEnvironmentVariable('Path','User') -ceq $originalUserPath -and
        [Environment]::GetEnvironmentVariable('Path','Machine') -ceq $originalMachinePath)
    Write-Output 'POST-INSTALL RUNTIME REGRESSION: PASS (isolated Windows fixtures; no real OpenCode runtime or persistent PATH changes)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'POST-INSTALL RUNTIME REGRESSION: FAIL'
    exit 1
} finally {
    foreach ($name in $envNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
    if ($runCreated -and (Test-Path -LiteralPath $run)) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop; break }
            catch {
                if ($attempt -eq 10) { Write-Output "CLEANUP_DEFERRED: $run"; break }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}
