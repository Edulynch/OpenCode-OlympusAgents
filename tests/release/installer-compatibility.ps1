[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('olympus-installer-compat-' + [guid]::NewGuid().ToString('N'))
$originalPath = $env:PATH
. (Join-Path $PSScriptRoot '../installer-test-environment.ps1')
$isolatedEnvironment = $null
$projectInstaller = Join-Path $source 'scripts/bootstrap.ps1'
function Check([string]$id, [bool]$valid) {
    if (-not $valid) { throw "$id FAIL" }
    Write-Output "$id PASS"
}
try {
    $isolatedEnvironment = Enter-OlympusInstallerTestEnvironment $run
    $text = [IO.File]::ReadAllText($installer)
    $defaultVersion = [regex]::Match($text, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''')
    $releaseVersion = [regex]::Match($text, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''')
    Check 'P6_RELEASE_IDENTITY' ($defaultVersion.Success -and $releaseVersion.Success -and
        $defaultVersion.Groups[1].Value -ceq $releaseVersion.Groups[1].Value)
    $script:CandidateVersion = $defaultVersion.Groups[1].Value
    $candidatePattern = [regex]::Escape($script:CandidateVersion)
    Check 'P3_STRICT_MODE' ($text -match 'Set-StrictMode\s+-Version\s+Latest')
    Check 'P5_NO_ISWINDOWS' ($text -notmatch '\$IsWindows' -and $text -match 'OSVersion\.Platform' -and $text -match 'PLATFORM_UNQUALIFIED')

    $pwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $hosts = @()
    $windowsPowerShell = Get-Command powershell.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($windowsPowerShell) {
        $version = (& $windowsPowerShell.Source -NoProfile -Command '$PSVersionTable.PSVersion.Major' | Out-String).Trim()
        if ($version -eq '5') { $hosts += [pscustomobject]@{ Id='P1_WINDOWS_POWERSHELL_5_1'; Path=$windowsPowerShell.Source } }
        else { Write-Output "P1_WINDOWS_POWERSHELL_5_1 UNAVAILABLE (found major version $version)" }
    } else { Write-Output 'P1_WINDOWS_POWERSHELL_5_1 UNAVAILABLE' }
    $hosts += [pscustomobject]@{ Id='P2_POWERSHELL_7'; Path=$pwsh }

    [IO.Directory]::CreateDirectory($run) | Out-Null
    $mockBin = Join-Path $run 'mock-bin'
    [IO.Directory]::CreateDirectory($mockBin) | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'fixtures/opencode.ps1') -Destination (Join-Path $mockBin 'opencode.ps1')
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), "@echo off`r`npwsh -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n", [Text.Encoding]::ASCII)
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $env:PATH
    $results = @()
    $expectedOpenCodeAssets = @(
        'opencode.jsonc',
        '.opencode/agents/argus.md',
        '.opencode/agents/atlas.md',
        '.opencode/agents/helios.md',
        '.opencode/agents/kael.md',
        '.opencode/agents/kovan.md',
        '.opencode/agents/nox.md',
        '.opencode/agents/orin.md',
        '.opencode/agents/talos.md',
        '.opencode/agents/thales.md',
        '.opencode/agents/vera.md',
        '.opencode/agents/veyra.md',
        '.opencode/plugins/olympus-activity/activity.ts',
        '.opencode/plugins/olympus-activity/tui.tsx',
        '.opencode/scripts/worktree-setup.ps1'
    ) | Sort-Object
    foreach ($hostEntry in $hosts) {
        $publicDry = (& $hostEntry.Path -NoProfile -File $installer -SourceRoot $source -DryRun `
            -CliInstallRoot $env:OLYMPUS_CLI_ROOT -CliPathStorePath $env:OLYMPUS_CLI_PATH_STORE 2>&1 | Out-String)
        Check ($hostEntry.Id + '_PUBLIC_GLOBAL_HANDOFF') ($LASTEXITCODE -eq 0 -and
            $publicDry -match 'GLOBAL_INSTALL_DRY_RUN: opencode' -and
            -not (Test-Path (Join-Path $env:OPENCODE_CONFIG_DIR 'olympus/orchestrator-install.json')))
        # The public entrypoint hands off to PS7; retained internal engines are PS7-only.
        $engineHost = $pwsh
        $target = Join-Path $run $hostEntry.Id
        [IO.Directory]::CreateDirectory($target) | Out-Null
        & git -C $target init --quiet
        Check ($hostEntry.Id + '_GIT_FIXTURE') ($LASTEXITCODE -eq 0)
        $toolDir = Join-Path $target '.serena'
        [IO.Directory]::CreateDirectory($toolDir) | Out-Null
        $toolFiles = @('.serena/.gitignore','.serena/project.yml')
        [IO.File]::WriteAllText((Join-Path $target $toolFiles[0]), "# local tool`n")
        [IO.File]::WriteAllText((Join-Path $target $toolFiles[1]), "project: local`n")
        $toolHashes = @($toolFiles | ForEach-Object { (Get-FileHash -LiteralPath (Join-Path $target $_) -Algorithm SHA256).Hash })
        $dry = (& $engineHost -NoProfile -File $projectInstaller -SourceVersion $script:CandidateVersion -Target $target -DryRun 2>&1 | Out-String)
        Check ($hostEntry.Id + '_DRY_RUN') ($LASTEXITCODE -eq 0 -and
            $dry -match '(?m)^DRY_RUN_READY\s*$' -and
            -not (Test-Path -LiteralPath (Join-Path $target '.opencode/orchestrator-install.json')))
        $output = (& $engineHost -NoProfile -File $projectInstaller -SourceVersion $script:CandidateVersion -Target $target 2>&1 | Out-String)
        $code = $LASTEXITCODE
        $manifestPath = Join-Path $target '.opencode/orchestrator-install.json'
        Check $hostEntry.Id ($code -eq 0 -and $output -match '(?m)^READY\s*$' -and
            $output -match '(?m)^READY\s*$' -and
            (Test-Path -LiteralPath $manifestPath -PathType Leaf))
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        $installedAssets = @($manifest.managed_files | ForEach-Object { ([string]$_.path).Replace('\','/') } | Sort-Object)
        Check ($hostEntry.Id + '_ASSETS') ($manifest.schema_version -eq 1 -and $manifest.scope -ceq 'project' -and
            @($manifest.installed_harnesses).Count -eq 1 -and $manifest.installed_harnesses[0] -ceq 'opencode' -and
            $manifest.installed_version -ceq $script:CandidateVersion -and
            -not [string]::IsNullOrWhiteSpace([string]$manifest.installed_from_commit) -and
            $manifest.managed_files.Count -eq 15 -and
            @($manifest.managed_files | Where-Object { [string]$_.sha256 -notmatch '^(?i:[0-9a-f]{64})$' }).Count -eq 0 -and
            [string]::Join("`n", $installedAssets) -ceq [string]::Join("`n", $expectedOpenCodeAssets) -and
            (Test-Path -LiteralPath (Join-Path $target '.opencode/plugins/olympus-activity/activity.ts') -PathType Leaf))
        $toolStatus = (& git -C $target status --porcelain=v1 -uall -- .serena | Out-String)
        Check ($hostEntry.Id + '_UNTRACKED_TOOL_STATE') ($LASTEXITCODE -eq 0 -and
            (@($toolFiles | ForEach-Object { (Get-FileHash -LiteralPath (Join-Path $target $_) -Algorithm SHA256).Hash }) -join ',') -eq ($toolHashes -join ',') -and
            $toolStatus -match '(?m)^\?\? \.serena/\.gitignore\s*$' -and
            $toolStatus -match '(?m)^\?\? \.serena/project\.yml\s*$')

        foreach ($selector in @('codex','all')) {
            $unsupportedTarget = Join-Path $run ($hostEntry.Id + '-unsupported-' + $selector)
            [IO.Directory]::CreateDirectory($unsupportedTarget) | Out-Null
            & git -C $unsupportedTarget init --quiet
            Check ($hostEntry.Id + '_UNSUPPORTED_GIT_FIXTURE_' + $selector.ToUpperInvariant()) ($LASTEXITCODE -eq 0)
            $unsupportedBefore = (& git -C $unsupportedTarget status --porcelain=v1 --untracked-files=all | Out-String).Trim()
            $unsupported = (& $engineHost -NoProfile -File $projectInstaller -SourceVersion $script:CandidateVersion `
                -Target $unsupportedTarget -Harness $selector 2>&1 | Out-String)
            $unsupportedCode = $LASTEXITCODE
            $unsupportedAfter = (& git -C $unsupportedTarget status --porcelain=v1 --untracked-files=all | Out-String).Trim()
            Check ($hostEntry.Id + '_UNSUPPORTED_SELECTOR_' + $selector.ToUpperInvariant()) ($unsupportedCode -ne 0 -and
                $unsupportedAfter -ceq $unsupportedBefore -and
                -not (Test-Path -LiteralPath (Join-Path $unsupportedTarget '.opencode/orchestrator-install.json')))
        }
        $results += $target
    }
    if ($results.Count -eq 2) {
        $a = [IO.File]::ReadAllText((Join-Path $results[0] '.opencode/orchestrator-install.json')) | ConvertFrom-Json
        $b = [IO.File]::ReadAllText((Join-Path $results[1] '.opencode/orchestrator-install.json')) | ConvertFrom-Json
        Check 'P1_P2_EQUIVALENT_INSTALLS' ($a.installed_from_commit -eq $b.installed_from_commit -and
            ((Get-FileHash (Join-Path $results[0] 'opencode.jsonc')).Hash -eq
             (Get-FileHash (Join-Path $results[1] 'opencode.jsonc')).Hash))
    }

    # pwsh prepends its own directory to PATH at startup: clear PATH inside the child,
    # not just in the parent. An invalid source and absent target prove the early check.
    $missingTarget = Join-Path $run 'must-not-be-created'
    $missingSource = Join-Path $run 'must-not-be-read'
    $missingFixture = Join-Path $run 'pwsh-missing.ps1'
    [IO.File]::WriteAllText($missingFixture, @'
param([string]$Installer, [string]$SourceRoot, [string]$Target, [string]$EmptyPath)
$env:PATH = $EmptyPath
& $Installer -SourceRoot $SourceRoot
'@)
    foreach ($hostEntry in $hosts) {
        $output = (& $hostEntry.Path -NoProfile -File $missingFixture -Installer $installer -SourceRoot $missingSource -Target $missingTarget -EmptyPath $run 2>&1 | Out-String)
        $code = $LASTEXITCODE
        Check ('P4_PWSH_MISSING_' + $hostEntry.Id) ($code -ne 0 -and
            $output -match 'OLYMPUS_REQUIRES_POWERSHELL_7:\s*PowerShell 7 \(pwsh\) is\s*required' -and
            $output -notmatch 'SOURCE_INVALID|BOOTSTRAP_FAILED|VariableIsUndefined' -and
            -not (Test-Path -LiteralPath $missingTarget))
    }
    Write-Output 'INSTALLER COMPATIBILITY: PASS (local source; deterministic OpenCode CLI fixture; remote publication status not queried)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'INSTALLER COMPATIBILITY: FAIL'
    exit 1
} finally {
    if ($null -ne $isolatedEnvironment) { Exit-OlympusInstallerTestEnvironment $isolatedEnvironment }
    $env:PATH = $originalPath
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
