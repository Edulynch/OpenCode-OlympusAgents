[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('olympus-installer-compat-' + [guid]::NewGuid().ToString('N'))
$originalPath = $env:PATH
$originalFixtureOpenCodeRoot = [Environment]::GetEnvironmentVariable('OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT', 'Process')
. (Join-Path $PSScriptRoot '../installer-test-environment.ps1')
$isolatedEnvironment = $null
$testEnvironment = $null
$projectInstaller = Join-Path $source 'scripts/bootstrap.ps1'
function Check([string]$id, [bool]$valid) {
    if (-not $valid) { throw "$id FAIL" }
    Write-Output "$id PASS"
}
function Get-Python311 {
    foreach ($name in @('python3.11','python3','python')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        try {
            & $command.Source -B -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $command.Source }
        } catch {}
    }
    throw 'Python 3.11+ is unavailable locally; no environment or package installation was attempted.'
}
function Get-PackageInventory([string]$Root) {
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    @(
        Get-ChildItem -LiteralPath $Root -File -Recurse -Force | ForEach-Object {
            [pscustomobject]@{
                Path = $_.FullName.Substring($prefix.Length).Replace('\','/')
                Sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        } | Sort-Object Path
    )
}
function Get-TreeSnapshot([string]$Root) {
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) { return '<MISSING_ROOT>' }
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    @(
        Get-ChildItem -LiteralPath $Root -Force -Recurse | Sort-Object FullName | ForEach-Object {
            $relative = $_.FullName.Substring($prefix.Length).Replace('\','/')
            if ($_.PSIsContainer) { $relative + ':DIRECTORY' }
            else { $relative + ':SHA256:' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
        }
    ) -join "`n"
}
function Get-SelectedFileSnapshot([string]$Root, [string[]]$Paths) {
    @(
        foreach ($relative in $Paths) {
            $path = Join-Path $Root ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                "$relative SHA256=$((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash)"
            } else { "$relative MISSING" }
        }
    ) -join "`n"
}
function New-TagArchive([string]$Container, [string]$ArchivePath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory(
        $Container, $ArchivePath, [IO.Compression.CompressionLevel]::Optimal, $false
    )
}
try {
    $isolatedEnvironment = Enter-OlympusInstallerTestEnvironment $run
    $testEnvironment = @{
        OPENCODE_CONFIG_DIR = $env:OPENCODE_CONFIG_DIR
        OLYMPUS_CLI_ROOT = $env:OLYMPUS_CLI_ROOT
        OLYMPUS_CLI_PATH_STORE = $env:OLYMPUS_CLI_PATH_STORE
        OLYMPUS_CONFIG_FILE = $env:OLYMPUS_CONFIG_FILE
    }
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

    $python = Get-Python311
    $renderer = Join-Path $source 'scripts/render_harnesses.py'
    $sourceHead = (& git -C $source rev-parse HEAD 2>$null | Out-String).Trim()
    $headExitCode = $LASTEXITCODE
    $sourceStatus = (& git -C $source status --porcelain=v1 --untracked-files=all 2>$null | Out-String).Trim()
    $statusExitCode = $LASTEXITCODE
    Check 'STAGED_PACKAGE_SOURCE_EVIDENCE' ($headExitCode -eq 0 -and $statusExitCode -eq 0 -and
        $sourceHead -match '^(?i:[0-9a-f]{40,64})$')
    $sourceWorktree = if ($sourceStatus) { 'DIRTY' } else { 'CLEAN' }
    $packageRoot = Join-Path $run 'staged-package'
    $renderOutput = (& $python -B $renderer render --harness opencode --root $source --output-root $packageRoot 2>&1 | Out-String)
    $renderExitCode = $LASTEXITCODE
    Check 'STAGED_PACKAGE_RENDER' ($renderExitCode -eq 0 -and
        $renderOutput -match 'HARNESS_RENDER: PASS \(opencode; wrote 18 changed output\(s\), 0 unchanged\)')

    $expectedPackageGenerated = @($expectedOpenCodeAssets + @(
        '.opencode/commands/olympus.ultra.md',
        '.opencode/commands/olympus.performance.md',
        'docs/HARNESS-CAPABILITIES.md'
    )) | Sort-Object
    $sourceGeneratedSnapshot = Get-SelectedFileSnapshot $source $expectedPackageGenerated
    $supportPaths = @('scripts/bootstrap.ps1','scripts/target-writer-lock.ps1','olympus/core/models-dev.json')
    foreach ($relative in $supportPaths) {
        $destination = Join-Path $packageRoot ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
        Copy-Item -LiteralPath (Join-Path $source ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)) -Destination $destination
    }
    $packageSupportMatches = @(
        foreach ($relative in $supportPaths) {
            $sourcePath = Join-Path $source ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
            $packagePath = Join-Path $packageRoot ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
            (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash -ceq
                (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash
        }
    )
    Check 'STAGED_PACKAGE_SUPPORT_FILES' ($packageSupportMatches.Count -eq 3 -and
        @($packageSupportMatches | Where-Object { -not $_ }).Count -eq 0)

    $expectedPackagePaths = @($expectedPackageGenerated + $supportPaths) | Sort-Object
    $packageInventory = @(Get-PackageInventory $packageRoot)
    $packagePaths = @($packageInventory | ForEach-Object Path)
    $packageEvidence = @($packageInventory | ForEach-Object { "$($_.Path) SHA256=$($_.Sha256)" }) -join "`n"
    Check 'STAGED_PACKAGE_INVENTORY' ($expectedPackageGenerated.Count -eq 18 -and
        $expectedPackagePaths.Count -eq 21 -and $packageInventory.Count -eq 21 -and
        [string]::Join("`n", [string[]]$packagePaths) -ceq
            [string]::Join("`n", [string[]]$expectedPackagePaths) -and
        @($packageInventory | Where-Object { $_.Sha256 -notmatch '^(?i:[0-9a-f]{64})$' }).Count -eq 0)
    Write-Output "STAGED_PACKAGE_SOURCE: working-tree snapshot; checkout HEAD=$sourceHead; worktree=$sourceWorktree"
    if ($sourceStatus) { Write-Output "STAGED_PACKAGE_SOURCE_WORKTREE_CHANGES: $sourceStatus" }
    Write-Output 'STAGED_PACKAGE_MANIFEST_COMMIT_EXPECTED: unknown (Git-free package; not source provenance)'
    foreach ($entry in $packageInventory) {
        Write-Output "STAGED_PACKAGE_FILE: $($entry.Path) SHA256=$($entry.Sha256)"
    }

    $checkOutput = (& $python -B $renderer check --harness opencode --root $source --output-root $packageRoot 2>&1 | Out-String)
    $checkExitCode = $LASTEXITCODE
    $checkedInventory = @(Get-PackageInventory $packageRoot)
    $checkedEvidence = @($checkedInventory | ForEach-Object { "$($_.Path) SHA256=$($_.Sha256)" }) -join "`n"
    Check 'STAGED_PACKAGE_RENDER_CHECK' ($checkExitCode -eq 0 -and
        $checkOutput -match 'HARNESS_RENDER_CHECK: PASS \(opencode; 18 managed output\(s\); read-only\)' -and
        $checkedEvidence -ceq $packageEvidence)

    $packageHashByPath = @{}
    foreach ($entry in $packageInventory) { $packageHashByPath[$entry.Path] = $entry.Sha256 }
    $packageBootstrap = Join-Path $packageRoot 'scripts/bootstrap.ps1'
    Check 'STAGED_PACKAGE_BOOTSTRAP_BINDING' (
        [IO.Path]::GetFullPath($packageBootstrap) -ceq [IO.Path]::GetFullPath((Join-Path $packageRoot 'scripts/bootstrap.ps1')) -and
        $packageHashByPath.ContainsKey('scripts/bootstrap.ps1') -and
        (Get-FileHash -LiteralPath $packageBootstrap -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $packageHashByPath['scripts/bootstrap.ps1'] -and
        -not (Test-Path -LiteralPath (Join-Path $packageRoot '.git')))
    Write-Output "STAGED_PACKAGE_BOOTSTRAP: $packageBootstrap"
    $packageTarget = Join-Path $run 'staged-package-target'
    [IO.Directory]::CreateDirectory($packageTarget) | Out-Null
    & git -C $packageTarget init --quiet
    Check 'STAGED_PACKAGE_TARGET_GIT_FIXTURE' ($LASTEXITCODE -eq 0)
    $packageOutput = (& $pwsh -NoProfile -File $packageBootstrap -SourceVersion $script:CandidateVersion -Target $packageTarget 2>&1 | Out-String)
    $packageExitCode = $LASTEXITCODE
    $packageManifestPath = Join-Path $packageTarget '.opencode/orchestrator-install.json'
    Check 'STAGED_PACKAGE_BOOTSTRAP' ($packageExitCode -eq 0 -and
        $packageOutput -match '(?m)^READY\s*$' -and
        (Test-Path -LiteralPath $packageManifestPath -PathType Leaf))
    $packageManifest = Get-Content -LiteralPath $packageManifestPath -Raw | ConvertFrom-Json
    $packageManagedPaths = @($packageManifest.managed_files | ForEach-Object { ([string]$_.path).Replace('\','/') } | Sort-Object)
    Check 'STAGED_PACKAGE_MANIFEST' ($packageManifest.schema_version -eq 1 -and $packageManifest.scope -ceq 'project' -and
        @($packageManifest.installed_harnesses).Count -eq 1 -and $packageManifest.installed_harnesses[0] -ceq 'opencode' -and
        $packageManifest.installed_version -ceq $script:CandidateVersion -and
        $packageManifest.installed_from_commit -ceq 'unknown' -and
        $packageManifest.managed_files.Count -eq 15 -and
        @($packageManifest.managed_files | Where-Object { [string]$_.sha256 -notmatch '^(?i:[0-9a-f]{64})$' }).Count -eq 0 -and
        [string]::Join("`n", [string[]]$packageManagedPaths) -ceq [string]::Join("`n", [string[]]$expectedOpenCodeAssets))
    $installedPackageHashesMatch = @(
        foreach ($relative in $expectedOpenCodeAssets) {
            $manifestEntries = @($packageManifest.managed_files | Where-Object { ([string]$_.path).Replace('\','/') -ceq $relative })
            $installedPath = Join-Path $packageTarget ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
            if (-not $packageHashByPath.ContainsKey($relative) -or $manifestEntries.Count -ne 1 -or
                -not (Test-Path -LiteralPath $installedPath -PathType Leaf)) {
                $false
                continue
            }
            $installedHash = (Get-FileHash -LiteralPath $installedPath -Algorithm SHA256).Hash.ToLowerInvariant()
            $installedHash -ceq $packageHashByPath[$relative] -and
                ([string]$manifestEntries[0].sha256).ToLowerInvariant() -ceq $installedHash
        }
    )
    Check 'STAGED_PACKAGE_INSTALLED_HASHES' ($installedPackageHashesMatch.Count -eq 15 -and
        @($installedPackageHashesMatch | Where-Object { -not $_ }).Count -eq 0)
    $consumedPackageInventory = @(Get-PackageInventory $packageRoot)
    $consumedPackageEvidence = @($consumedPackageInventory | ForEach-Object { "$($_.Path) SHA256=$($_.Sha256)" }) -join "`n"
    Check 'STAGED_PACKAGE_CONSUMPTION_READ_ONLY' ($consumedPackageEvidence -ceq $packageEvidence)
    Write-Output 'STAGED_PACKAGE_CASE: PASS (18 generated + 3 support files; isolated mocked bootstrap; package unchanged)'

    $archiveContainer = Join-Path $run 'offline-archive-source'
    $archiveRoot = Join-Path $archiveContainer ('OpenCode-OlympusAgents-' + $script:CandidateVersion)
    [IO.Directory]::CreateDirectory($archiveRoot) | Out-Null
    foreach ($relative in @('olympus','scripts','.opencode','docs')) {
        Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $archiveRoot -Recurse -Force
    }
    foreach ($relative in @('install.ps1','opencode.jsonc')) {
        Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $archiveRoot -Force
    }
    $canary = 'ARCHIVE_RENDER_CANARY_' + [guid]::NewGuid().ToString('N')
    $archiveKovanSource = Join-Path $archiveRoot 'olympus/harnesses/opencode/agent-prompts/kovan.md'
    [IO.File]::AppendAllText($archiveKovanSource, "`n$canary`n", [Text.UTF8Encoding]::new($false))
    $staleArchiveKovan = Join-Path $archiveRoot '.opencode/agents/kovan.md'
    Check 'ARCHIVE_CANARY_CHECKED_IN_OUTPUT_STAYS_STALE' (
        -not [IO.File]::ReadAllText($staleArchiveKovan).Contains($canary)
    )
    $archivePath = Join-Path $run 'offline-tag.zip'
    New-TagArchive $archiveContainer $archivePath
    $archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash

    $expectedArchiveStage = Join-Path $run 'offline-archive-expected-render'
    [IO.Directory]::CreateDirectory($expectedArchiveStage) | Out-Null
    $expectedArchiveRender = (& $python -B $renderer render --harness opencode --root $archiveRoot `
        --output-root $expectedArchiveStage 2>&1 | Out-String)
    $expectedArchiveRenderCode = $LASTEXITCODE
    Check 'ARCHIVE_CANARY_EXPECTED_RENDER' ($expectedArchiveRenderCode -eq 0 -and
        $expectedArchiveRender -match 'HARNESS_RENDER: PASS \(opencode; wrote 18 changed output\(s\), 0 unchanged\)')
    $expectedArchiveKovan = Join-Path $expectedArchiveStage '.opencode/agents/kovan.md'
    $expectedArchiveKovanBytes = [IO.File]::ReadAllBytes($expectedArchiveKovan)
    $expectedArchiveKovanHash = (Get-FileHash -LiteralPath $expectedArchiveKovan -Algorithm SHA256).Hash.ToLowerInvariant()
    Check 'ARCHIVE_CANARY_IS_RENDERED_FROM_SOURCE' ([IO.File]::ReadAllText($expectedArchiveKovan).Contains($canary))

    # The checked-in output remains stale, while a canonical-source parse error
    # must stop the archive path before global or CLI targets are reached.
    $invalidModels = Join-Path $archiveRoot 'olympus/core/models.toml'
    [IO.File]::WriteAllText($invalidModels, '[malformed', [Text.UTF8Encoding]::new($false))
    $renderFailureArchive = Join-Path $run 'offline-render-failure.zip'
    New-TagArchive $archiveContainer $renderFailureArchive
    foreach ($target in @('render-failure-opencode','render-failure-cli')) {
        [IO.Directory]::CreateDirectory((Join-Path $run $target)) | Out-Null
    }
    $failureGlobalRoot = Join-Path $run 'render-failure-opencode'
    $failureCliRoot = Join-Path $run 'render-failure-cli'
    $failurePathStore = Join-Path $failureCliRoot 'path-store.txt'
    $failureConfig = Join-Path $run 'render-failure-user-config.json'
    $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $failureGlobalRoot
    $env:OLYMPUS_CONFIG_FILE = $failureConfig
    Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue
    $failureGlobalBefore = Get-TreeSnapshot $failureGlobalRoot
    $failureCliBefore = Get-TreeSnapshot $failureCliRoot
    $renderFailureOutput = (& $pwsh -NoProfile -File $installer -Version $script:CandidateVersion `
        -SourceArchive $renderFailureArchive -CliInstallRoot $failureCliRoot -CliPathStorePath $failurePathStore `
        2>&1 | Out-String)
    $renderFailureCode = $LASTEXITCODE
    Check 'ARCHIVE_RENDER_FAILURE_BLOCKS_TARGET_MUTATION' ($renderFailureCode -ne 0 -and
        $renderFailureOutput -match 'SOURCE_RENDERER_FAILED' -and
        (Get-TreeSnapshot $failureGlobalRoot) -ceq $failureGlobalBefore -and
        (Get-TreeSnapshot $failureCliRoot) -ceq $failureCliBefore -and
        -not (Test-Path -LiteralPath $failureConfig))

    # Removing the renderer from the temporary archive proves uninstall keeps
    # its existing path and does not acquire a new Python/render dependency.
    Remove-Item -LiteralPath (Join-Path $archiveRoot 'scripts/render_harnesses.py') -Force
    $uninstallArchive = Join-Path $run 'offline-uninstall-without-renderer.zip'
    New-TagArchive $archiveContainer $uninstallArchive

    foreach ($hostEntry in $hosts) {
        $archiveGlobalRoot = Join-Path $run ($hostEntry.Id + '-archive-opencode')
        $archiveCliRoot = Join-Path $run ($hostEntry.Id + '-archive-cli')
        $archivePathStore = Join-Path $archiveCliRoot 'path-store.txt'
        $archiveConfig = Join-Path $run ($hostEntry.Id + '-archive-user-config.json')
        [IO.Directory]::CreateDirectory($archiveGlobalRoot) | Out-Null
        [IO.Directory]::CreateDirectory($archiveCliRoot) | Out-Null
        $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $archiveGlobalRoot
        $env:OLYMPUS_CONFIG_FILE = $archiveConfig
        $env:OLYMPUS_CLI_ROOT = $archiveCliRoot
        $env:OLYMPUS_CLI_PATH_STORE = $archivePathStore
        Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue

        $archiveInstall = (& $hostEntry.Path -NoProfile -File $installer -Version $script:CandidateVersion `
            -SourceArchive $archivePath -CliInstallRoot $archiveCliRoot -CliPathStorePath $archivePathStore `
            2>&1 | Out-String)
        $archiveInstallCode = $LASTEXITCODE
        $globalManifestPath = Join-Path $archiveGlobalRoot 'olympus/orchestrator-install.json'
        $globalKovanPath = Join-Path $archiveGlobalRoot 'agents/kovan.md'
        $cliKovanPath = Join-Path $archiveCliRoot ('versions/' + $script:CandidateVersion + '/.opencode/agents/kovan.md')
        $cliManifestPath = Join-Path $archiveCliRoot ('versions/' + $script:CandidateVersion + '/olympus-cli-manifest.json')
        Check ($hostEntry.Id + '_ARCHIVE_INSTALL_RENDERED_CANARY') ($archiveInstallCode -eq 0 -and
            $archiveInstall -match 'OLYMPUS_SOURCE_RENDER: PASS \(18 generated files; isolated stage checked read-only before install\)' -and
            (Test-Path -LiteralPath $globalManifestPath -PathType Leaf) -and
            (Test-Path -LiteralPath $cliManifestPath -PathType Leaf))
        $globalManifest = Get-Content -LiteralPath $globalManifestPath -Raw | ConvertFrom-Json
        $globalKovanEntry = @($globalManifest.managed_files | Where-Object { $_.path -ceq 'agents/kovan.md' })
        $cliManifest = Get-Content -LiteralPath $cliManifestPath -Raw | ConvertFrom-Json
        $cliKovanEntry = @($cliManifest.files | Where-Object { $_.path -ceq '.opencode/agents/kovan.md' })
        Check ($hostEntry.Id + '_ARCHIVE_RENDERED_BYTES_REACH_BOTH_CONSUMERS') (
            $globalKovanEntry.Count -eq 1 -and $cliKovanEntry.Count -eq 1 -and
            $globalKovanEntry[0].sha256 -ceq $expectedArchiveKovanHash -and
            $cliKovanEntry[0].sha256 -ceq $expectedArchiveKovanHash -and
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($globalKovanPath)) -ceq
                [Convert]::ToBase64String($expectedArchiveKovanBytes) -and
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($cliKovanPath)) -ceq
                [Convert]::ToBase64String($expectedArchiveKovanBytes))

        $globalBeforeDryRun = Get-TreeSnapshot $archiveGlobalRoot
        $cliBeforeDryRun = Get-TreeSnapshot $archiveCliRoot
        $archiveDryRun = (& $hostEntry.Path -NoProfile -File $installer -Version $script:CandidateVersion `
            -SourceArchive $archivePath -DryRun -CliInstallRoot $archiveCliRoot -CliPathStorePath $archivePathStore `
            2>&1 | Out-String)
        Check ($hostEntry.Id + '_ARCHIVE_DRY_RUN_READ_ONLY') ($LASTEXITCODE -eq 0 -and
            $archiveDryRun -match 'OLYMPUS_SOURCE_RENDER: PASS' -and
            (Get-TreeSnapshot $archiveGlobalRoot) -ceq $globalBeforeDryRun -and
            (Get-TreeSnapshot $archiveCliRoot) -ceq $cliBeforeDryRun)

        $globalBeforeVerify = Get-TreeSnapshot $archiveGlobalRoot
        $cliBeforeVerify = Get-TreeSnapshot $archiveCliRoot
        $archiveVerify = (& $hostEntry.Path -NoProfile -File $installer -Version $script:CandidateVersion `
            -SourceArchive $archivePath -VerifyOnly -CliInstallRoot $archiveCliRoot -CliPathStorePath $archivePathStore `
            2>&1 | Out-String)
        Check ($hostEntry.Id + '_ARCHIVE_VERIFY_ONLY_READ_ONLY') ($LASTEXITCODE -eq 0 -and
            $archiveVerify -match 'OLYMPUS_SOURCE_RENDER: PASS' -and
            $archiveVerify -match 'GLOBAL_VERIFY: opencode' -and
            (Get-TreeSnapshot $archiveGlobalRoot) -ceq $globalBeforeVerify -and
            (Get-TreeSnapshot $archiveCliRoot) -ceq $cliBeforeVerify)

        $archiveUninstall = (& $hostEntry.Path -NoProfile -File $installer -Version $script:CandidateVersion `
            -SourceArchive $uninstallArchive -Uninstall -CliInstallRoot $archiveCliRoot `
            -CliPathStorePath $archivePathStore 2>&1 | Out-String)
        Check ($hostEntry.Id + '_ARCHIVE_UNINSTALL_SKIPS_RENDER') ($LASTEXITCODE -eq 0 -and
            $archiveUninstall -notmatch 'OLYMPUS_SOURCE_RENDER|SOURCE_RENDERER_FAILED' -and
            -not (Test-Path -LiteralPath $globalManifestPath) -and
            -not (Test-Path -LiteralPath $cliManifestPath) -and
            (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -ceq $archiveHash)
    }
    Write-Output 'OFFLINE_SOURCE_ARCHIVE_CASE: PASS (tag-shaped ZIP; stale checked-in output; canonical-source canary; global manifest and CLI receipt; DryRun/VerifyOnly read-only; uninstall skips renderer)'
    Check 'ARCHIVE_INSTALL_SOURCE_CHECKOUT_UNCHANGED' (
        (Get-SelectedFileSnapshot $source $expectedPackageGenerated) -ceq $sourceGeneratedSnapshot
    )
    foreach ($name in $testEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $testEnvironment[$name], 'Process')
    }
    if ($null -eq $originalFixtureOpenCodeRoot) { Remove-Item Env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT -ErrorAction SilentlyContinue }
    else { $env:OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT = $originalFixtureOpenCodeRoot }

    foreach ($hostEntry in $hosts) {
        $publicDry = (& $hostEntry.Path -NoProfile -File $installer -SourceRoot $source -DryRun `
            -CliInstallRoot $env:OLYMPUS_CLI_ROOT -CliPathStorePath $env:OLYMPUS_CLI_PATH_STORE 2>&1 | Out-String)
        $sourceAfterDryRun = Get-SelectedFileSnapshot $source $expectedPackageGenerated
        Check ($hostEntry.Id + '_PUBLIC_GLOBAL_HANDOFF') ($LASTEXITCODE -eq 0 -and
            $publicDry -match 'GLOBAL_INSTALL_DRY_RUN: opencode' -and
            $publicDry -notmatch 'OLYMPUS_SOURCE_RENDER' -and
            $sourceAfterDryRun -ceq $sourceGeneratedSnapshot -and
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
            $output -match 'OLYMPUS_REQUIRES_POWERSHELL_7:\s*PowerShell\s+7 \(pwsh\) is\s*required' -and
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
