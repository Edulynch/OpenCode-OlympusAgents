[CmdletBinding()]
param(
    [switch]$MockOpenCode,
    [switch]$ResumeAtR1,
    [switch]$ResumeAtPermissions,
    [string]$RecoveryRunId = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$installerText = [IO.File]::ReadAllText($installer)
$defaultVersionMatch = [regex]::Match($installerText, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''\s*,?\s*$')
$releaseVersionMatch = [regex]::Match($installerText, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''')
if (-not $defaultVersionMatch.Success -or -not $releaseVersionMatch.Success -or
    $defaultVersionMatch.Groups[1].Value -cne $releaseVersionMatch.Groups[1].Value) {
    throw 'RELEASE_IDENTITY_INVALID: Installer default and release version marker must agree.'
}
$script:CandidateVersion = $defaultVersionMatch.Groups[1].Value
$script:CandidateRegex = [regex]::Escape($script:CandidateVersion)
$script:CandidateHeading = "## $($script:CandidateVersion)"
$tempOpencode = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode'
if (-not $RecoveryRunId) { $RecoveryRunId = [guid]::NewGuid().ToString('N') }
if ($RecoveryRunId -notmatch '^[A-Za-z0-9-]{8,80}$') { throw 'RECOVERY_RUN_ID_INVALID' }
$run = Join-Path $tempOpencode ('olympus-release-qualification-' + $RecoveryRunId)
$receiptPath = Join-Path $tempOpencode ('olympus-release-qualification-' + $RecoveryRunId + '.json')
$transcriptPath = Join-Path $tempOpencode ('olympus-release-qualification-' + $RecoveryRunId + '.log')
$cliInstallRoot = Join-Path $run 'cli-install'
$cliPathStorePath = Join-Path $cliInstallRoot 'cli-path.json'
. (Join-Path $PSScriptRoot '../installer-test-environment.ps1')
$isolatedEnvironment = $null
$utf8 = [Text.UTF8Encoding]::new($false)
$script:QualificationReceipt = $null
function Save-QualificationReceipt {
    if ($null -ne $script:QualificationReceipt) {
        $script:QualificationReceipt.latest_progress_timestamp = (Get-Date).ToString('o')
        [IO.File]::WriteAllText($receiptPath, ($script:QualificationReceipt | ConvertTo-Json -Depth 15), $utf8)
    }
}

$self = Get-CimInstance Win32_Process -Filter "ProcessId=$PID" -ErrorAction SilentlyContinue
if (-not $self) { throw 'PROCESS_OWNERSHIP_UNAVAILABLE: Cannot record qualification process identity.' }
$parentProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($self.ParentProcessId)" -ErrorAction SilentlyContinue
if (-not $parentProcess) { throw 'PROCESS_OWNERSHIP_UNAVAILABLE: Cannot record qualification parent identity.' }
$script:QualificationReceipt = [ordered]@{
    task_run_id = $RecoveryRunId
    task = "Olympus $($script:CandidateVersion) release qualification"
    state = 'LIVE_OWNED_WORK'
    ownership_marker = $RecoveryRunId
    expected_result_path = $transcriptPath
    progress_counter = 0
    latest_progress_timestamp = (Get-Date).ToString('o')
    process = [ordered]@{
        pid = [int]$self.ProcessId
        start_time = ([datetime]$self.CreationDate).ToString('o')
        executable_path = [string]$self.ExecutablePath
        exact_command_line = [string]$self.CommandLine
        working_directory = (Get-Location).Path
        parent_pid = [int]$self.ParentProcessId
        parent_start_time = ([datetime]$parentProcess.CreationDate).ToString('o')
        ownership_marker = $RecoveryRunId
    }
}
Save-QualificationReceipt

function Check([string]$id, [bool]$valid, [string]$evidence = '') {
    if (-not $valid) {
        if ($evidence) { throw "$id FAIL`n$evidence" }
        throw "$id FAIL"
    }
    Write-Output "$id PASS"
    $script:QualificationReceipt.progress_counter++
    Save-QualificationReceipt
}

function New-Target([string]$name) {
    $target = Join-Path $run $name
    [IO.Directory]::CreateDirectory($target) | Out-Null
    [IO.File]::WriteAllText((Join-Path $target 'user-notes.txt'), "preserve me`n", $utf8)
    & git -C $target init --quiet
    if ($LASTEXITCODE -ne 0) { throw 'GIT_FIXTURE_INIT_FAIL' }
    & git -C $target -c user.name=Qualification -c user.email=qualification@example.invalid add -- user-notes.txt
    if ($LASTEXITCODE -ne 0) { throw 'GIT_FIXTURE_ADD_FAIL' }
    & git -C $target -c user.name=Qualification -c user.email=qualification@example.invalid commit --quiet -m 'qualification fixture'
    if ($LASTEXITCODE -ne 0) { throw 'GIT_FIXTURE_COMMIT_FAIL' }
    return $target
}

function New-SourceArchive([string]$sourceRoot, [string]$tag, [string]$archivePath, [switch]$MisreportVersion) {
    $pack = Join-Path $run ('package-' + [guid]::NewGuid().ToString('N'))
    $top = Join-Path $pack "OpenCode-OlympusAgents-$tag"
    [IO.Directory]::CreateDirectory($top) | Out-Null
    # Keep the local archive fixture hermetic: unrelated user untracked files
    # are not release source; deleted tracked files are not current source either.
    $files = @(& git -C $sourceRoot ls-files --cached)
    if ($LASTEXITCODE -ne 0 -or $files.Count -eq 0) { throw 'GIT_FIXTURE_SOURCE_INVENTORY_FAIL' }
    $deletedFiles = @(& git -C $sourceRoot ls-files --deleted)
    if ($LASTEXITCODE -ne 0) { throw 'GIT_FIXTURE_SOURCE_DELETION_INVENTORY_FAIL' }
    $files = @($files | Where-Object { $_ -notin $deletedFiles })
    if ($files.Count -eq 0) { throw 'GIT_FIXTURE_SOURCE_INVENTORY_FAIL' }
    $installationGuide = 'docs/INSTALLATION.md'
    if ((Test-Path -LiteralPath (Join-Path $sourceRoot $installationGuide) -PathType Leaf) -and $installationGuide -notin $files) {
        $files += $installationGuide
    }
    # Include only these new release resources before they are committed, not arbitrary untracked files.
    foreach ($relative in @(
        'olympus/harnesses/opencode/commands/olympus.ultra.md',
        'olympus/harnesses/opencode/commands/olympus.performance.md',
        '.opencode/commands/olympus.ultra.md',
        '.opencode/commands/olympus.performance.md'
    )) {
        if ((Test-Path -LiteralPath (Join-Path $sourceRoot $relative) -PathType Leaf) -and $relative -notin $files) {
            $files += $relative
        }
    }
    foreach ($relative in $files) {
        $sourceFile = Join-Path $sourceRoot $relative
        $destination = Join-Path $top $relative
        $destinationParent = Split-Path -Parent $destination
        [IO.Directory]::CreateDirectory($destinationParent) | Out-Null
        Copy-Item -LiteralPath $sourceFile -Destination $destination -Force
    }
    if ($MisreportVersion) {
        $path = Join-Path $top 'install.ps1'
        $text = [IO.File]::ReadAllText($path)
        $text = $text.Replace("[string]`$Version = '$($script:CandidateVersion)'", "[string]`$Version = 'v0.2.0'")
        $text = $text.Replace("`$ReleaseVersion = '$($script:CandidateVersion)'", "`$ReleaseVersion = 'v0.2.0'")
        [IO.File]::WriteAllText($path, $text, $utf8)
    } elseif ($tag -in @('v0.3.0-alpha.1','v0.3.0-beta.2','v0.3.0-rc.1')) {
        $path = Join-Path $top 'install.ps1'
        $text = [IO.File]::ReadAllText($path)
        $text = $text.Replace("[string]`$Version = '$($script:CandidateVersion)'", "[string]`$Version = '$tag'")
        $text = $text.Replace("`$ReleaseVersion = '$($script:CandidateVersion)'", "`$ReleaseVersion = '$tag'")
        [IO.File]::WriteAllText($path, $text, $utf8)
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($pack, $archivePath)
    return $archivePath
}

function Assert-QualificationCliTargets([string]$InstallRoot, [string]$PathStorePath) {
    if ([string]::IsNullOrWhiteSpace($InstallRoot) -or -not [IO.Path]::IsPathFullyQualified($InstallRoot) -or
        [string]::IsNullOrWhiteSpace($PathStorePath) -or -not [IO.Path]::IsPathFullyQualified($PathStorePath)) {
        throw 'CLI_FIXTURE_TARGET_INVALID: CLI install root and PATH store must be absolute.'
    }
    $fixturePrefix = [IO.Path]::GetFullPath($run).TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    $installRoot = [IO.Path]::GetFullPath($InstallRoot).TrimEnd([char[]]@('\','/'))
    $pathStore = [IO.Path]::GetFullPath($PathStorePath)
    if (-not $installRoot.StartsWith($fixturePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'CLI_FIXTURE_TARGET_INVALID: CLI install root must be inside this qualification run.'
    }
    $installPrefix = $installRoot + [IO.Path]::DirectorySeparatorChar
    if (-not $pathStore.StartsWith($installPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'CLI_FIXTURE_TARGET_INVALID: PATH store must be inside the fixture CLI install root.'
    }
}

function Test-QualificationCliTargetsReject([string]$InstallRoot, [string]$PathStorePath) {
    try {
        Assert-QualificationCliTargets $InstallRoot $PathStorePath
        return $false
    } catch {
        return $true
    }
}

function Install([string]$target, [string]$archive, [string]$version = '') {
    Assert-QualificationCliTargets $cliInstallRoot $cliPathStorePath
    if (-not $version) { $version = $script:CandidateVersion }
    try {
        $fixture = Expand-ProjectQualificationSource $archive $version
        $output = "OLYMPUS_SOURCE: requested=$version resolved=$version origin=LOCAL_ARCHIVE`n"
        $output += (& pwsh -NoProfile -File (Join-Path $fixture 'scripts/bootstrap.ps1') `
            -Target $target -SourceVersion $version 2>&1 | Out-String)
        $code = $LASTEXITCODE
        if ($code -eq 0) {
            $output += "OLYMPUS_INSTALL: $version READY_OR_NO_CHANGES`n"
            $output += (& pwsh -NoProfile -File (Join-Path $fixture 'scripts/install-cli.ps1') `
                -Action install -SourceRoot $fixture -Version $version `
                -InstallRoot $cliInstallRoot -PathStorePath $cliPathStorePath 2>&1 | Out-String)
            $code = $LASTEXITCODE
        }
        return [pscustomobject]@{ Text=$output; Code=$code }
    } catch { return [pscustomobject]@{ Text=$_.Exception.Message; Code=1 } }
}

function Verify([string]$target, [string]$archive, [string]$version) {
    Assert-QualificationCliTargets $cliInstallRoot $cliPathStorePath
    try {
        $fixture = Expand-ProjectQualificationSource $archive $version
        $bootstrap = Join-Path $fixture 'scripts/bootstrap.ps1'
        $output = (& pwsh -NoProfile -File $bootstrap -Target $target -SourceVersion $version -VerifyOnly 2>&1 | Out-String)
        return [pscustomobject]@{ Text=$output; Code=$LASTEXITCODE }
    } catch {
        $message = $_.Exception.Message
        $reason = if ($message -match '^([A-Z_]+):') { $Matches[1] } else { 'VERIFY_FAILED' }
        return [pscustomobject]@{ Text="OLYMPUS_VERIFY: $version FAIL`nOLYMPUS_VERIFY_REASON: $reason`n$message"; Code=1 }
    }
}

# Reuse current source identity guards without executing the global installer body.
$tokens = $null; $parseErrors = $null
$installerAst = [Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'QUALIFICATION_INSTALLER_PARSE_FAILED' }
foreach ($name in @('Get-DeclaredReleaseVersion','Assert-ArchiveTag')) {
    $definition = $installerAst.Find({ param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }.GetNewClosure(), $true)
    if ($null -eq $definition) { throw "QUALIFICATION_SOURCE_GUARD_MISSING: $name" }
    . ([scriptblock]::Create($definition.Extent.Text))
}

function Expand-ProjectQualificationSource([string]$Archive, [string]$Version) {
    $expanded = Join-Path $run ('project-source-' + [guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $Archive -DestinationPath $expanded
    $roots = @(Get-ChildItem -LiteralPath $expanded -Force)
    if ($roots.Count -ne 1 -or -not $roots[0].PSIsContainer) { throw 'SOURCE_INVALID: No single archive root.' }
    Assert-ArchiveTag $roots[0].Name $Version
    $declared = Get-DeclaredReleaseVersion $roots[0].FullName
    if ($declared -cne $Version) {
        throw "SOURCE_VERSION_MISMATCH: requested '$Version' but resolved source reports '$declared'."
    }
    return $roots[0].FullName
}

function Get-ProjectSnapshot([string]$target) {
    $root = (Resolve-Path -LiteralPath $target).Path.TrimEnd([char[]]@('\','/'))
    $prefix = $root + [IO.Path]::DirectorySeparatorChar
    @(
        Get-ChildItem -LiteralPath $root -Force -Recurse -File | Sort-Object FullName | ForEach-Object {
            $relative = $_.FullName.Substring($prefix.Length)
            $relative + ':' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        }
    ) -join "`n"
}

try {
    # Capture the caller's destination before replacing LOCALAPPDATA with the fixture.
    $hostDefaultCliRoot = Join-Path $env:LOCALAPPDATA 'Programs/Olympus'
    $isolatedEnvironment = Enter-OlympusInstallerTestEnvironment $run
    [IO.Directory]::CreateDirectory($run) | Out-Null
    Start-Transcript -LiteralPath $transcriptPath -Force | Out-Null
    $validCliTargets = $false
    try {
        Assert-QualificationCliTargets $cliInstallRoot $cliPathStorePath
        $validCliTargets = $true
    } catch {}
    $outsideFixtureCliRoot = Join-Path $tempOpencode ('outside-' + $RecoveryRunId)
    $cliTargetRejections = @(
        (Test-QualificationCliTargetsReject '' $cliPathStorePath),
        (Test-QualificationCliTargetsReject $cliInstallRoot ''),
        (Test-QualificationCliTargetsReject 'relative-cli-root' $cliPathStorePath),
        (Test-QualificationCliTargetsReject $cliInstallRoot 'relative-path-store.json'),
        (Test-QualificationCliTargetsReject $outsideFixtureCliRoot (Join-Path $outsideFixtureCliRoot 'cli-path.json')),
        (Test-QualificationCliTargetsReject $cliInstallRoot (Join-Path $run 'escaped-cli-path.json')),
        (Test-QualificationCliTargetsReject $hostDefaultCliRoot (Join-Path $hostDefaultCliRoot 'cli-path.json'))
    )
    Check 'R0_CLI_TARGETS_FAIL_CLOSED' ($validCliTargets -and $cliTargetRejections.Count -eq 7 -and
        @($cliTargetRejections | Where-Object { -not $_ }).Count -eq 0) `
        "valid fixture paths accepted; missing, relative, escaping, and host-default destinations rejected"
    if ($MockOpenCode) {
        $mockBin = Join-Path $run 'mock-bin'
        [IO.Directory]::CreateDirectory($mockBin) | Out-Null
        $fixtureMock = Join-Path $PSScriptRoot 'fixtures/opencode.ps1'
        if (-not (Test-Path -LiteralPath $fixtureMock -PathType Leaf)) { throw 'OPENCODE_STUB_MISSING' }
        Copy-Item -LiteralPath $fixtureMock -Destination (Join-Path $mockBin 'opencode.ps1') -Force
        [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), "@echo off`r`npwsh -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n", [Text.Encoding]::ASCII)
        $env:PATH = $mockBin + [IO.Path]::PathSeparator + $env:PATH
        Write-Output 'RUNTIME_OPEN_CODE: local stub responses; no live OpenCode session or authority smoke.'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archiveInventoryRepo = Join-Path $run ('archive-inventory-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($archiveInventoryRepo) | Out-Null
    [IO.File]::WriteAllText((Join-Path $archiveInventoryRepo 'kept.txt'), "staged bytes`n", $utf8)
    [IO.File]::WriteAllText((Join-Path $archiveInventoryRepo 'removed.txt'), "removed bytes`n", $utf8)
    & git -C $archiveInventoryRepo init --quiet
    if ($LASTEXITCODE -ne 0) { throw 'ARCHIVE_INVENTORY_GIT_INIT_FAIL' }
    & git -C $archiveInventoryRepo add -- kept.txt removed.txt
    if ($LASTEXITCODE -ne 0) { throw 'ARCHIVE_INVENTORY_GIT_ADD_FAIL' }
    [IO.File]::WriteAllText((Join-Path $archiveInventoryRepo 'kept.txt'), "current worktree bytes`n", $utf8)
    Remove-Item -LiteralPath (Join-Path $archiveInventoryRepo 'removed.txt') -Force
    [IO.File]::WriteAllText((Join-Path $archiveInventoryRepo 'user-untracked.txt'), "untracked bytes`n", $utf8)
    $archiveInventoryZip = Join-Path $run 'archive-inventory-regression.zip'
    [void](New-SourceArchive $archiveInventoryRepo 'inventory-regression' $archiveInventoryZip)
    $archiveInventoryExpanded = Join-Path $run ('archive-inventory-expanded-' + [guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $archiveInventoryZip -DestinationPath $archiveInventoryExpanded -ErrorAction Stop
    $archiveInventoryRoot = Join-Path $archiveInventoryExpanded 'OpenCode-OlympusAgents-inventory-regression'
    $keptArchivePath = Join-Path $archiveInventoryRoot 'kept.txt'
    Check 'R0_SOURCE_ARCHIVE_CURRENT_WORKTREE_INVENTORY' (
        (Test-Path -LiteralPath $keptArchivePath -PathType Leaf) -and
        [IO.File]::ReadAllText($keptArchivePath) -eq "current worktree bytes`n" -and
        -not (Test-Path -LiteralPath (Join-Path $archiveInventoryRoot 'removed.txt')) -and
        -not (Test-Path -LiteralPath (Join-Path $archiveInventoryRoot 'user-untracked.txt')))
    $candidateArchive = New-SourceArchive $source $script:CandidateVersion (Join-Path $run "candidate-$($script:CandidateVersion).zip")
    $alphaArchive = New-SourceArchive $source 'v0.3.0-alpha.1' (Join-Path $run 'alpha.zip')
    $betaArchive = New-SourceArchive $source 'v0.3.0-beta.2' (Join-Path $run 'beta.zip')
    $rcArchive = New-SourceArchive $source 'v0.3.0-rc.1' (Join-Path $run 'rc.zip')
    $mismatchArchive = New-SourceArchive $source $script:CandidateVersion (Join-Path $run "mismatch-$($script:CandidateVersion)-to-v020.zip") -MisreportVersion

    $versionText = $installerText
    $releaseIdentityValid = ($versionText -match "(?m)^\s*\[string\]\`$Version\s*=\s*'$($script:CandidateRegex)'" -and
        $versionText -match "(?m)^\`$ReleaseVersion\s*=\s*'$($script:CandidateRegex)'")
    $patternMatch = [regex]::Match($versionText, "(?s)\[ValidatePattern\('([^']+)'\)\]\s*\[string\]\`$Version")
    $versionPattern = if ($patternMatch.Success) { $patternMatch.Groups[1].Value } else { '' }
    $acceptedSyntax = @('v1.2.3','v0.3.0-alpha.1',$script:CandidateVersion,'v2.4.0-rc.12' | Where-Object { $_ -match $versionPattern }).Count -eq 4
    if (-not ($ResumeAtR1 -or $ResumeAtPermissions)) {
        Check 'R0_RELEASE_IDENTITY' $releaseIdentityValid
        Check 'R0_TARGET_IDENTITY_V0110' ($script:CandidateVersion -ceq 'v0.11.0')
        Check 'R0_STABLE_CANDIDATE_VERSION' ($script:CandidateVersion -match '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$')
        Check 'R0_SEMVER_VALIDATOR' ($acceptedSyntax -and 'v1.2.3-preview.1' -notmatch $versionPattern)
        Check 'R23_ALPHA_RC_PARSING' (@('v0.3.0-alpha.1','v0.3.0-rc.12' | Where-Object { $_ -match $versionPattern }).Count -eq 2)
        $transitionScript = Join-Path $PSScriptRoot 'tag-transition-stability.ps1'
        $transitionOutput = (& pwsh -NoProfile -File $transitionScript 2>&1 | Out-String)
        Check 'R0_TAG_TRANSITION_STABILITY' ($LASTEXITCODE -eq 0 -and
            $transitionOutput -match 'PRE_TAG_SEMANTIC_VALIDATION: PASS' -and
            $transitionOutput -match 'SIMULATED_POST_TAG_SEMANTIC_VALIDATION: PASS' -and
            $transitionOutput -match 'TAG-TRANSITION-STABILITY QUALIFICATION: PASS') ("exit=$LASTEXITCODE`n$transitionOutput")
    } elseif ($ResumeAtR1) { Write-Output 'REVALIDATION_START: R1 (previously collected R0/alpha/RC gates not rerun).' }
    else { Write-Output 'REVALIDATION_START: permission checks (previously collected R0/alpha/RC gates not rerun).' }

    # The current prerelease request uses a local ZIP with the same GitHub tag-root layout.
    $target = New-Target 'fresh-candidate-default'
    $first = Install $target $candidateArchive
    $expectedCliRoot = [IO.Path]::GetFullPath($cliInstallRoot).TrimEnd([char[]]@('\','/'))
    $cliRootReport = [regex]::Match($first.Text, '(?m)^OLYMPUS_CLI: .* root=(?<root>.+?)\s*$')
    $reportedCliRoot = $null
    if ($cliRootReport.Success) {
        try { $reportedCliRoot = [IO.Path]::GetFullPath($cliRootReport.Groups['root'].Value.Trim()).TrimEnd([char[]]@('\','/')) }
        catch { $reportedCliRoot = $null }
    }
    $reportedCliRootMatches = ($null -ne $reportedCliRoot -and
        [string]::Equals($reportedCliRoot, $expectedCliRoot, [StringComparison]::OrdinalIgnoreCase))
    $currentCliMarkerPath = Join-Path $cliInstallRoot 'current.txt'
    $currentCliMarker = if (Test-Path -LiteralPath $currentCliMarkerPath -PathType Leaf) {
        [IO.File]::ReadAllText($currentCliMarkerPath).Trim()
    } else { $null }
    $currentCliMarkerMatches = $currentCliMarker -ceq $script:CandidateVersion
    $cliPathStoreExists = Test-Path -LiteralPath $cliPathStorePath -PathType Leaf
    $cliFixtureCheckResult = if ($first.Code -ne 0) { 'INSTALL_FAILED' }
        elseif ($reportedCliRootMatches -and $currentCliMarkerMatches -and $cliPathStoreExists) { 'PASS' }
        else { 'FAIL' }
    $script:QualificationReceipt.cli_fixture = [ordered]@{
        expected_root = $expectedCliRoot
        reported_root = $reportedCliRoot
        reported_root_matches = $reportedCliRootMatches
        current_marker = $currentCliMarker
        current_marker_matches_candidate = $currentCliMarkerMatches
        path_store_exists = $cliPathStoreExists
        check_result = $cliFixtureCheckResult
    }
    Save-QualificationReceipt
    Check 'R1_ISOLATED_CLI_FIXTURE_DESTINATION' ($cliFixtureCheckResult -eq 'PASS') `
        ("result=$cliFixtureCheckResult; expected_root=$expectedCliRoot; reported_root=$reportedCliRoot; " +
            "reported_root_matches=$reportedCliRootMatches; current_marker=$currentCliMarker; " +
            "current_marker_matches_candidate=$currentCliMarkerMatches; path_store_exists=$cliPathStoreExists")
    if (-not $ResumeAtPermissions) {
        $r1Pass = ($first.Code -eq 0 -and
            $first.Text -match "OLYMPUS_SOURCE: requested=$($script:CandidateRegex) resolved=$($script:CandidateRegex) origin=LOCAL_ARCHIVE" -and
            $first.Text -match "OLYMPUS_INSTALL: $($script:CandidateRegex) READY_OR_NO_CHANGES")
        if (-not $r1Pass) { Write-Output "R1_INSTALL_OUTPUT: $($first.Text)" }
        Check 'R1_CANDIDATE_RESOLVED_CANDIDATE' $r1Pass
        $paths = @('opencode.jsonc', '.opencode/orchestrator-install.json',
            '.opencode/plugins/olympus-activity/activity.ts', '.opencode/plugins/olympus-activity/tui.tsx',
            '.opencode/scripts/worktree-setup.ps1')
        $paths += @('kael','veyra','orin','kovan','nox','vera','thales','atlas','argus','talos','helios' | ForEach-Object { ".opencode/agents/$_.md" })
        Check 'R2_CANDIDATE_ROSTER_FILES' (@($paths | Where-Object { -not (Test-Path -LiteralPath (Join-Path $target $_) -PathType Leaf) }).Count -eq 0 -and
            -not (Test-Path -LiteralPath (Join-Path $target '.opencode/agents/aegis.md')) -and
            -not (Test-Path -LiteralPath (Join-Path $target '.opencode/commands/maintain.md')))
        $manifestPath = Join-Path $target '.opencode/orchestrator-install.json'
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        Check 'R2_CANDIDATE_MANIFEST_VERSION_AND_OWNERSHIP' ($manifest.schema_version -eq 1 -and
            $manifest.installed_version -eq $script:CandidateVersion -and $manifest.managed_files.Count -eq 15 -and
            @($manifest.managed_files | Where-Object path -match 'aegis|commands/maintain|agents/maintenance').Count -eq 0)

        $betaVerify = Verify $target $candidateArchive $script:CandidateVersion
        Check 'R24_CANDIDATE_INSTALL_VERIFY_PASS' ($betaVerify.Code -eq 0 -and $betaVerify.Text -match "(?m)^OLYMPUS_VERIFY: $($script:CandidateRegex) PASS\s*$")

        Push-Location $target
        try {
            $agents = (& opencode debug agents 2>&1 | Out-String) | ConvertFrom-Json -Depth 100
            Check 'R3_EFFECTIVE_AGENTS' ($LASTEXITCODE -eq 0 -and @($agents | Where-Object { $_.id -in @('kael','veyra','orin','kovan','nox','vera','thales','atlas','argus','talos','helios') }).Count -eq 11 -and @($agents | Where-Object { $_.id -in @('maintenance','sorin','aegis') }).Count -eq 0)
            $plugins = (& opencode plugin list 2>&1 | Out-String)
            Check 'R9_HUD_DISCOVERY' ($LASTEXITCODE -eq 0 -and $plugins -match 'olympus-activity')
        } finally { Pop-Location }
        $expected = @{
            kael=@('gpt-6.2-sol','high','primary'); thales=@('gpt-6.2-sol','xhigh','subagent'); atlas=@('gpt-6.2-sol','high','subagent'); argus=@('gpt-6.2-sol','high','subagent'); talos=@('gpt-6.2-sol','high','subagent'); helios=@('gpt-6.2-sol','high','subagent')
            veyra=@('gpt-6-luna','max','subagent'); orin=@('gpt-6-luna','max','subagent'); kovan=@('gpt-6-luna','max','subagent')
            nox=@('gpt-6-luna','max','subagent'); vera=@('gpt-6-luna','max','subagent')
        }
        foreach ($id in $expected.Keys) {
            $agent = @($agents | Where-Object id -eq $id)
            Check "R5_MODEL_$id" ($agent.Count -eq 1 -and $agent[0].model.id -eq $expected[$id][0] -and
                $agent[0].model.variant -eq $expected[$id][1] -and $agent[0].mode -eq $expected[$id][2])
        }
        $kaelText = [IO.File]::ReadAllText((Join-Path $target '.opencode/agents/kael.md'))
        Check 'R4_CONTEXTUAL_MAINTENANCE_ON_KAEL' ($kaelText -match 'Kael is the only root orchestrator' -and
            $kaelText -match 'There is no separate maintenance role, command' -and
            -not (Test-Path -LiteralPath (Join-Path $target '.opencode/agents/aegis.md')) -and
            -not (Test-Path -LiteralPath (Join-Path $target '.opencode/commands/maintain.md')))
    } else {
        Write-Output 'REVALIDATION_START: R4_PERMISSION_CHECKS (R1-R4 discovery gates already collected; no gate assertions rerun).'
        if ($first.Code -ne 0) { throw 'Fixture setup failed while restoring permission check context.' }
        Push-Location $target
        try { $agents = (& opencode debug agents 2>&1 | Out-String) | ConvertFrom-Json -Depth 100; if ($LASTEXITCODE -ne 0) { throw 'OpenCode stub fixture setup failed.' } }
        finally { Pop-Location }
    }
    $k = @($agents | Where-Object id -eq kovan)[0]
    $n = @($agents | Where-Object id -eq nox)[0]
    $kael = @($agents | Where-Object id -eq kael)[0]
    $kaelChildren = @($kael.permissions | Where-Object { $_.action -eq 'subagent' -and $_.effect -eq 'allow' } | ForEach-Object resource)
    $expectedChildren = @('veyra','orin','kovan','nox','vera','thales','atlas','argus','talos','helios')
    Check 'R4_KAEL_CAN_ROUTE_NORMAL_SPECIALISTS' ($kaelChildren.Count -eq $expectedChildren.Count -and
        @($expectedChildren | Where-Object { $_ -notin $kaelChildren }).Count -eq 0)
    function Perm($a, [string]$action, [string]$effect) {
        @($a.permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq $effect }).Count -gt 0
    }
    Check 'R10_TRUSTED_AUTONOMY' ((Perm $k shell allow) -and (Perm $k edit allow) -and (Perm $n shell allow) -and (Perm $n edit deny))
    $kaelText = [IO.File]::ReadAllText((Join-Path $target '.opencode/agents/kael.md'))
    Check 'R11_NAMESPACED_PARALLEL_POLICY' ($kaelText -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $kaelText -match 'minimum useful parallelism' -and
        $kaelText -match '/olympus\.ultra <prompt>' -and $kaelText -match '/olympus\.performance <prompt>' -and
        $kaelText -match 'native parallel tool-call batch' -and
        $kaelText -notmatch 'FAST is an explicit user-selected|fast-mode|long-mode|surgical-mode')

    # Prerelease identifiers are accepted end-to-end for current source archives.
    foreach ($entry in @(@('alpha','v0.3.0-alpha.1',$alphaArchive), @('beta','v0.3.0-beta.2',$betaArchive), @('rc','v0.3.0-rc.1',$rcArchive))) {
        $semverTarget = New-Target ('semver-' + $entry[0])
        $result = Install $semverTarget $entry[2] $entry[1]
        $semverManifestPath = Join-Path $semverTarget '.opencode/orchestrator-install.json'
        $semverManifest = if (Test-Path -LiteralPath $semverManifestPath) { Get-Content -LiteralPath $semverManifestPath -Raw | ConvertFrom-Json } else { $null }
        Check ('R14_' + $entry[0].ToUpperInvariant() + '_ACCEPTED') ($result.Code -eq 0 -and
            $result.Text -match ('OLYMPUS_SOURCE: requested=' + [regex]::Escape($entry[1]) + ' resolved=' + [regex]::Escape($entry[1])) -and
            $null -ne $semverManifest -and $semverManifest.installed_version -eq $entry[1])
    }

    $otherBetaTarget = New-Target 'verify-other-beta'
    $otherBetaInstall = Install $otherBetaTarget $betaArchive 'v0.3.0-beta.2'
    if ($otherBetaInstall.Code -ne 0) { throw 'Other-beta fixture install failed before version verification.' }
    $otherBetaVerify = Verify $otherBetaTarget $candidateArchive $script:CandidateVersion
    Check 'R24_CANDIDATE_VS_OTHER_BETA_FAIL' ($otherBetaVerify.Code -ne 0 -and
        $otherBetaVerify.Text -match 'OLYMPUS_VERIFY_REASON: INSTALLED_VERSION_MISMATCH')

    $driftTarget = New-Target 'verify-managed-hash-drift'
    $driftInstall = Install $driftTarget $candidateArchive $script:CandidateVersion
    if ($driftInstall.Code -ne 0) { throw 'Candidate fixture install failed before managed drift verification.' }
    $driftFile = Join-Path $driftTarget '.opencode/agents/kael.md'
    [IO.File]::AppendAllText($driftFile, "`n# verification drift`n", $utf8)
    $driftSnapshot = Get-ProjectSnapshot $driftTarget
    $hashDrift = Verify $driftTarget $candidateArchive $script:CandidateVersion
    Check 'R24_MANAGED_HASH_DRIFT_FAIL' ($hashDrift.Code -ne 0 -and
        $hashDrift.Text -match 'OLYMPUS_VERIFY_REASON: MANAGED_FILE_MISMATCH' -and
        (Get-ProjectSnapshot $driftTarget) -ceq $driftSnapshot)

    $missingTarget = New-Target 'verify-managed-file-missing'
    $missingInstall = Install $missingTarget $candidateArchive $script:CandidateVersion
    if ($missingInstall.Code -ne 0) { throw 'Candidate fixture install failed before missing-file verification.' }
    $missingFile = Join-Path $missingTarget '.opencode/agents/kael.md'
    Remove-Item -LiteralPath $missingFile -Force
    $missingSnapshot = Get-ProjectSnapshot $missingTarget
    $missingVerify = Verify $missingTarget $candidateArchive $script:CandidateVersion
    Check 'R24_MANAGED_FILE_MISSING_FAIL' ($missingVerify.Code -ne 0 -and
        $missingVerify.Text -match "(?m)^OLYMPUS_VERIFY: $($script:CandidateRegex) FAIL\s*$" -and
        $missingVerify.Text -match 'OLYMPUS_VERIFY_REASON: MANAGED_FILE_MISSING' -and
        (Get-ProjectSnapshot $missingTarget) -ceq $missingSnapshot)

    $retiredAgentTarget = New-Target 'verify-retired-agent-active'
    $retiredInstall = Install $retiredAgentTarget $candidateArchive $script:CandidateVersion
    if ($retiredInstall.Code -ne 0) { throw 'Candidate fixture install failed before retired-agent verification.' }
    [IO.File]::WriteAllText((Join-Path $retiredAgentTarget '.opencode/agents/aegis.md'), "id: aegis`n", $utf8)
    $retiredAgentSnapshot = Get-ProjectSnapshot $retiredAgentTarget
    $retiredVerify = Verify $retiredAgentTarget $candidateArchive $script:CandidateVersion
    Check 'R24_CANDIDATE_ROSTER_REJECTS_MAINTENANCE' ($retiredVerify.Code -ne 0 -and
        $retiredVerify.Text -match 'OLYMPUS_VERIFY_REASON: ROSTER_MISMATCH' -and
        (Get-ProjectSnapshot $retiredAgentTarget) -ceq $retiredAgentSnapshot)

    $sourceMismatchVerify = Verify $target $mismatchArchive $script:CandidateVersion
    Check 'R24_REQUESTED_SOURCE_VERSION_MISMATCH_FAIL' ($sourceMismatchVerify.Code -ne 0 -and
        $sourceMismatchVerify.Text -match 'OLYMPUS_VERIFY_REASON: SOURCE_VERSION_MISMATCH')

    # Only the two global/OpenCode public wrappers remain.
    function Test-PublicWrapperSource([string]$Content, [string]$Action) {
        $valid = if ($Action -eq 'install') {
            $Content.Contains('https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1')
        } else { $Content.Contains('uninstall --execute') }
        return ($valid -and $Content -notmatch '-Harness|-Scope|-Target|/master/')
    }

    $wrapperIssues = @()
    foreach ($entry in @(
        @('install/global/opencode.ps1','install'),
        @('uninstall/global/opencode.ps1','uninstall')
    )) {
        $relative = $entry[0]
        $wrapperText = [IO.File]::ReadAllText((Join-Path $source ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)))
        if (-not (Test-PublicWrapperSource $wrapperText $entry[1])) {
            $wrapperIssues += $relative
        }
    }
    Check 'R25_CURRENT_GLOBAL_OPENCODE_WRAPPERS' ($wrapperIssues.Count -eq 0) ($wrapperIssues -join ', ')

    function Test-UnifiedEntrypointSource([string]$Content, [string]$Action) {
        return ($Content.Contains('$launcherUrl = "https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$tag/scripts/launch-latest.ps1"') -and
            $Content.Contains('https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest') -and
            $Content.Contains("Assert-BootstrapReleaseBoolean `$release 'immutable' `$true") -and
            $Content.Contains('LATEST_RELEASE_MUTABLE') -and
            $Content.Contains('LATEST_RELEASE_IDENTITY_MISMATCH') -and
            $Content.Contains('LAUNCHER_BOOTSTRAP_CONTRACT_MISSING') -and
            $Content.Contains('no older launcher fallback is attempted') -and
            -not $Content.Contains('/master/scripts/launch-latest.ps1') -and
            $Content.Contains('Invoke-WebRequest -Uri $launcherUrl -OutFile $ownedLauncher -Headers $headers -ErrorAction Stop') -and
            $Content.Contains("'-Action', '$Action'") -and
            -not $Content.Contains('$selectedHarness') -and -not $Content.Contains("'-Target'"))
    }
    $unifiedEntrypointIssues = @()
    foreach ($entry in @(@('install-olympus.ps1','install'), @('uninstall-olympus.ps1','uninstall'))) {
        $entryText = [IO.File]::ReadAllText((Join-Path $source $entry[0]))
        if (-not (Test-UnifiedEntrypointSource $entryText $entry[1])) {
            $unifiedEntrypointIssues += $entry[0]
        }
    }
    Check 'R25_UNIFIED_ENTRYPOINTS_IMMUTABLE_BOOTSTRAP_AND_ACTION' ($unifiedEntrypointIssues.Count -eq 0) ($unifiedEntrypointIssues -join ', ')
    $installEntryText = [IO.File]::ReadAllText((Join-Path $source 'install-olympus.ps1'))
    $uninstallEntryText = [IO.File]::ReadAllText((Join-Path $source 'uninstall-olympus.ps1'))
    Check 'R25_UNIFIED_ENTRYPOINT_MUTATIONS_REJECTED' (
        -not (Test-UnifiedEntrypointSource ($installEntryText.Replace('/$tag/scripts/launch-latest.ps1', '/master/scripts/launch-latest.ps1')) 'install') -and
        -not (Test-UnifiedEntrypointSource ($installEntryText.Replace("'-Action', 'install'", "'-Action', 'uninstall'")) 'install') -and
        -not (Test-UnifiedEntrypointSource ($uninstallEntryText.Replace("'-Action', 'uninstall'", "'-Action', 'install'")) 'uninstall'))

    $sample = [IO.File]::ReadAllText((Join-Path $source 'install/global/opencode.ps1'))
    $badMutable = $sample.Replace('/releases/latest/download/install-olympus.ps1',
        '/master/scripts/launch-latest.ps1')
    $badWrongHarness = $sample + "`n# -Harness all"
    $badForeignSource = $sample.Replace('https://github.com/Edulynch/OpenCode-OlympusAgents/',
        'https://example.invalid/')
    $badOldTag = $sample.Replace('/releases/latest/download/install-olympus.ps1',
        '/v0.4.6/scripts/launch-latest.ps1')
    Check 'R25_PUBLIC_WRAPPER_MUTATIONS_REJECTED' (
        -not (Test-PublicWrapperSource $badMutable 'install') -and
        -not (Test-PublicWrapperSource $badWrongHarness 'install') -and
        -not (Test-PublicWrapperSource $badForeignSource 'install') -and
        -not (Test-PublicWrapperSource $badOldTag 'install'))

    $changelog = [IO.File]::ReadAllText((Join-Path $source 'CHANGELOG.md'))
    $notesStart = $changelog.IndexOf($script:CandidateHeading, [StringComparison]::Ordinal)
    if ($notesStart -lt 0) { throw "Release-notes section for $($script:CandidateVersion) is missing." }
    $afterCandidate = $changelog.Substring($notesStart + $script:CandidateHeading.Length)
    $nextRelease = [regex]::Match($afterCandidate, '(?m)^##[ \t]+v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?(?:[ \t]+[^\r\n]*)?\r?$')
    $notesEnd = if ($nextRelease.Success) { $notesStart + $script:CandidateHeading.Length + $nextRelease.Index } else { $changelog.Length }
    if ($notesEnd -le $notesStart) { throw "Release-notes section for $($script:CandidateVersion) is unbounded." }
    $releaseNotes = $changelog.Substring($notesStart, $notesEnd - $notesStart)
    $installGuideUrl = "https://github.com/Edulynch/OpenCode-OlympusAgents/blob/$($script:CandidateVersion)/docs/INSTALLATION.md"
    $installGuide = [IO.File]::ReadAllText((Join-Path $source 'docs/INSTALLATION.md'))
    $verifyGuideUrl = "$installGuideUrl#release-selection-identity-and-executable-source"
    $verifyGuideHeadingExists = $installGuide -match '(?im)^##\s+Release selection, identity, and executable source\s*$'
    Check 'R25_RELEASE_NOTES_INSTALLATION' ($releaseNotes -match '(?im)^##\s+Installation\s*$' -and
        $releaseNotes.Contains($installGuideUrl) -and $releaseNotes -match '(?i)Fast Install' -and
        $releaseNotes -match '(?i)Fast Uninstall')
    Check 'R25_RELEASE_NOTES_VERIFY_INSTALLATION' ($releaseNotes -match '(?im)^##\s+Verify installation\s*$' -and
        $releaseNotes.Contains($verifyGuideUrl) -and $verifyGuideHeadingExists -and
        $releaseNotes -match '(?i)read-only|VerifyOnly')
    Check 'R25_RELEASE_NOTES_KEEP_COMMANDS_IN_INSTALL_GUIDE' ($releaseNotes -notmatch '(?i)(?:raw\.githubusercontent\.com/Edulynch/OpenCode-OlympusAgents/|github\.com/Edulynch/OpenCode-OlympusAgents/(?:raw|blob)/)[^\r\n]+?\.ps1' -and
        $releaseNotes -notmatch '(?i)\b(?:irm|iwr|Invoke-WebRequest)\b[^\r\n]*\.ps1')
    $highlightsMatch = [regex]::Match($releaseNotes, '(?ims)^### Highlights\r?\n(?<body>.*?)(?=^### |^## |\z)')
    $highlights = if ($highlightsMatch.Success) { $highlightsMatch.Groups['body'].Value } else { '' }
    $requiredHighlights = @('yield its model turn', 'terminal-result reconciliation',
        '/olympus.ultra <prompt>', '/olympus.performance <prompt>', 'native batched dispatch',
        'approval before implementation', 'before/after correctness validation',
        'internal FAST qualification profile', 'human CLI output',
        '`--verbose`', '`--json` payloads and exit codes remain unchanged',
        '`openai/gpt-6.2-sol`', 'explicit user overrides')
    $missingHighlights = @($requiredHighlights | Where-Object { -not $highlights.Contains($_) })
    Check 'R25_V0110_RELEASE_HIGHLIGHTS' ($missingHighlights.Count -eq 0)
    $capabilityMatch = [regex]::Match($releaseNotes, '(?ims)^### Capability limits\r?\n(?<body>.*?)(?=^### |^## |\z)')
    $capabilityLimits = if ($capabilityMatch.Success) { $capabilityMatch.Groups['body'].Value } else { '' }
    $compatibilityDocs = [IO.File]::ReadAllText((Join-Path $source 'README.md')) + "`n" +
        [IO.File]::ReadAllText((Join-Path $source 'docs/INSTALLATION.md')) + "`n" +
        [IO.File]::ReadAllText((Join-Path $source 'docs/DEVELOPMENT.md'))
    Check 'R25_V0110_CAPABILITY_LIMITS_NOT_OVERCLAIMED' (
        $capabilityLimits -match '(?i)prompt-level guard, not deterministic native argument validation' -and
        $capabilityLimits -match '(?i)not a hard runtime or concurrent-root quota' -and
        $capabilityLimits -match '(?i)does not guarantee simultaneous CPU inference or a latency improvement' -and
        $capabilityLimits -match '(?i)Unowned command collisions fail closed' -and
        $capabilityLimits -match '(?i)Windows with PowerShell 7' -and
        $capabilityLimits -match '(?i)Python 3\.11\+' -and
        $capabilityLimits -match '(?i)OpenCode V2' -and
        $capabilityLimits -match '(?i)Local static and mock fixtures do not establish a public-endpoint install' -and
        $capabilityLimits -match '(?i)provider access or inference' -and
        $capabilityLimits -match '(?i)native permission UI/approval' -and
        $compatibilityDocs -notmatch '(?i)older CLIs|orchestration\.max_children.{0,80}rejected')
    $mutableExecutableUrl = '(?i)(?:raw\.githubusercontent\.com/Edulynch/OpenCode-OlympusAgents/(?:master|main|refs/heads/(?:master|main))/[^\s]+?\.ps1|github\.com/Edulynch/OpenCode-OlympusAgents/(?:raw|blob)/(?:master|main)/[^\s]+?\.ps1)'
    Check 'R25_RELEASE_NO_MUTABLE_EXECUTABLE_SOURCE' ($releaseNotes -notmatch $mutableExecutableUrl -and
        $versionText -match 'archive/refs/tags/\$Version\.zip')

    $releaseGate = Join-Path $PSScriptRoot 'github-release-notes.ps1'
    $gateGood = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody $releaseNotes 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_ACCEPTS_PINNED_HARNESS_COMMANDS' ($LASTEXITCODE -eq 0 -and $gateGood -match "RELEASE_NOTES_CONTRACT: $($script:CandidateRegex) PASS") ("exit=$LASTEXITCODE`n$gateGood")
    $gateDerived = (& pwsh -NoProfile -File $releaseGate -ReleaseBody $releaseNotes 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_DERIVES_CANDIDATE_VERSION' ($LASTEXITCODE -eq 0 -and
        $gateDerived -match "RELEASE_NOTES_CONTRACT: $($script:CandidateRegex) PASS")
    $gateBad = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody ($releaseNotes -replace '(?s)## Verify installation.*', '') 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_REJECTS_MISSING_VERIFY' ($LASTEXITCODE -ne 0 -and $gateBad -match 'RELEASE_NOTES_VERIFY_MISSING')
    $gateMutableWrapperBody = $releaseNotes + [Environment]::NewLine + 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/global/opencode.ps1 | iex'
    $gateMutableWrapper = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody $gateMutableWrapperBody 2>&1 | Out-String)
    Check 'R26_GATE_REJECTS_MUTABLE_WRAPPER_SOURCE' ($LASTEXITCODE -ne 0 -and $gateMutableWrapper -match 'RELEASE_NOTES_MASTER_SOURCE')
    $gateMutableLauncherBody = $releaseNotes + [Environment]::NewLine + 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/scripts/launch-latest.ps1 | iex'
    $gateMutableLauncher = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody $gateMutableLauncherBody 2>&1 | Out-String)
    Check 'R26_GATE_REJECTS_MUTABLE_LAUNCHER_SOURCE' ($LASTEXITCODE -ne 0 -and $gateMutableLauncher -match 'RELEASE_NOTES_MASTER_SOURCE')
    $gateWrongTagBody = $releaseNotes.Replace("/blob/$($script:CandidateVersion)/docs/INSTALLATION.md", '/blob/v0.3.0-beta.2/docs/INSTALLATION.md')
    $gateWrongTag = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody $gateWrongTagBody 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_REJECTS_TAG_MISMATCH' ($LASTEXITCODE -ne 0 -and $gateWrongTag -match 'RELEASE_NOTES_INSTALL_GUIDE_MISSING')
    $wrongHeadingBody = $releaseNotes.Replace("## $($script:CandidateVersion)", '## v0.4.1')
    $gateWrongIdentity = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody $wrongHeadingBody 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_REJECTS_ACTIVE_IDENTITY_MISMATCH' ($LASTEXITCODE -ne 0 -and
        $gateWrongIdentity -match 'RELEASE_NOTES_VERSION_MISMATCH')
    $gateUnstable = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody ($releaseNotes + "`n$($script:CandidateVersion) is not tagged; do not publish.") 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_REJECTS_EPHEMERAL_TAG_STATE' ($LASTEXITCODE -ne 0 -and $gateUnstable -match 'RELEASE_NOTES_EPHEMERAL_TAG_STATE')
    $gateOldBeta = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody ($releaseNotes + "`n$($script:CandidateVersion) is the old v0.3.0-beta.5 target.") 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_REJECTS_OLD_BETA_IDENTITY' ($LASTEXITCODE -ne 0 -and $gateOldBeta -match 'RELEASE_NOTES_TARGET_OLD_BETA')
    $gateUnmergedFoundation = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody ($releaseNotes + "`nThe v0.4.0 foundation remains unmerged.") 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_REJECTS_UNMERGED_FOUNDATION' ($LASTEXITCODE -ne 0 -and $gateUnmergedFoundation -match 'RELEASE_NOTES_FOUNDATION_UNMERGED')
    $gateText = [IO.File]::ReadAllText($releaseGate)
    Check 'R26_GATE_READS_PUBLISHED_GITHUB_RELEASE_BODY' ($gateText -match 'gh\.Source release view' -and
        $gateText -match 'release\.body' -and $gateText -match 'RELEASE_NOTES_EXECUTABLE_COMMANDS_MOVED' -and
        $gateText -match 'RELEASE_NOTES_HARNESS_VERIFY_MISSING')

    $badVersionTarget = New-Target 'bad-version'
    Assert-QualificationCliTargets $cliInstallRoot $cliPathStorePath
    $badVersion = (& pwsh -NoProfile -File $installer -Version 'v1.2.3-preview.1' -SourceArchive $candidateArchive `
        -CliInstallRoot $cliInstallRoot -CliPathStorePath $cliPathStorePath 2>&1 | Out-String)
    Check 'R17_MALFORMED_VERSION_REJECTED' ($LASTEXITCODE -ne 0 -and $badVersion -match 'v1\.2\.3-preview\.1' -and
        $badVersion -match 'no coincide|does not match|validation pattern' -and
        -not (Test-Path -LiteralPath (Join-Path $badVersionTarget '.opencode/orchestrator-install.json')))

    $mismatchTarget = New-Target 'candidate-resolves-v020-negative'
    $mismatch = Install $mismatchTarget $mismatchArchive $script:CandidateVersion
    Check 'R20_REQUESTED_CANDIDATE_RESOLVED_V020_FAILS' ($mismatch.Code -ne 0 -and
        $mismatch.Text.Contains("SOURCE_VERSION_MISMATCH: requested '$($script:CandidateVersion)' but resolved source reports 'v0.2.0'") -and
        -not (Test-Path -LiteralPath (Join-Path $mismatchTarget '.opencode/orchestrator-install.json')) -and
        (Get-Content -LiteralPath (Join-Path $mismatchTarget 'user-notes.txt') -Raw) -eq "preserve me`n")

    $currentManifestPath = Join-Path $target '.opencode/orchestrator-install.json'
    $currentManifest = Get-Content -LiteralPath $currentManifestPath -Raw | ConvertFrom-Json
    $currentManagedFiles = @($currentManifest.managed_files)
    $worktreeSetupPath = Join-Path $target '.opencode/scripts/worktree-setup.ps1'
    $worktreeSetupEntry = @($currentManagedFiles | Where-Object {
        $pathProperty = if ($null -ne $_) { $_.PSObject.Properties['path'] } else { $null }
        $null -ne $pathProperty -and $pathProperty.Value -eq '.opencode/scripts/worktree-setup.ps1'
    })
    $worktreeSetupPresent = Test-Path -LiteralPath $worktreeSetupPath -PathType Leaf
    $worktreeHashProperty = if ($worktreeSetupEntry.Count -eq 1) { $worktreeSetupEntry[0].PSObject.Properties['sha256'] } else { $null }
    $worktreeSetupHashMatches = ($worktreeSetupPresent -and $worktreeSetupEntry.Count -eq 1 -and
        $null -ne $worktreeHashProperty -and
        $worktreeHashProperty.Value -eq (Get-FileHash -LiteralPath $worktreeSetupPath -Algorithm SHA256).Hash.ToLowerInvariant())
    $worktreeSetupPass = ($worktreeSetupPresent -and $currentManagedFiles.Count -eq 15 -and
        $worktreeSetupEntry.Count -eq 1 -and $worktreeSetupHashMatches)
    Check 'R2_CURRENT_WORKTREE_SETUP_INSTALLED_AND_OWNED' $worktreeSetupPass `
        ("installed_version=$($currentManifest.installed_version); helper_present=$worktreeSetupPresent; managed_count=$($currentManagedFiles.Count); helper_entries=$($worktreeSetupEntry.Count); hash_matches=$worktreeSetupHashMatches")
    $invalidInventoryTarget = New-Target 'invalid-current-inventory'
    $invalidInventoryInstall = Install $invalidInventoryTarget $candidateArchive $script:CandidateVersion
    if ($invalidInventoryInstall.Code -ne 0) { throw 'Candidate fixture install failed before malformed-manifest verification.' }
    $invalidManifestPath = Join-Path $invalidInventoryTarget '.opencode/orchestrator-install.json'
    $invalidManifest = Get-Content -LiteralPath $invalidManifestPath -Raw | ConvertFrom-Json
    $invalidManifest.managed_files[1].path = [string]$invalidManifest.managed_files[0].path
    [IO.File]::WriteAllText($invalidManifestPath, (($invalidManifest | ConvertTo-Json -Depth 100) + "`n"), $utf8)
    $invalidInventorySnapshot = Get-ProjectSnapshot $invalidInventoryTarget
    $invalidInventoryUpgrade = Install $invalidInventoryTarget $candidateArchive $script:CandidateVersion
    Check 'R22_CURRENT_DUPLICATE_INVENTORY_REJECTED_READ_ONLY' ($invalidInventoryUpgrade.Code -ne 0 -and
        $invalidInventoryUpgrade.Text -match 'INSTALL_MANIFEST_INCOMPATIBLE' -and
        (Get-ProjectSnapshot $invalidInventoryTarget) -ceq $invalidInventorySnapshot)

    $unownedTarget = New-Target 'unowned-retired-agent'
    $unownedInstall = Install $unownedTarget $candidateArchive
    if ($unownedInstall.Code -ne 0) { throw 'Candidate fixture install failed before unowned-retired test.' }
    $unownedPath = Join-Path $unownedTarget '.opencode/agents/maintenance.md'
    [IO.File]::WriteAllText($unownedPath, "user-owned retired-name file`n", $utf8)
    $unownedHash = (Get-FileHash -LiteralPath $unownedPath -Algorithm SHA256).Hash
    $unownedAegisPath = Join-Path $unownedTarget '.opencode/agents/aegis.md'
    $unownedMaintainPath = Join-Path $unownedTarget '.opencode/commands/maintain.md'
    $unownedSnapshot = Get-ProjectSnapshot $unownedTarget
    $unownedUpgrade = Install $unownedTarget $candidateArchive
    $unownedHashPreserved = (Get-FileHash -LiteralPath $unownedPath -Algorithm SHA256).Hash -eq $unownedHash
    $unownedSnapshotPreserved = (Get-ProjectSnapshot $unownedTarget) -ceq $unownedSnapshot
    $unownedAegisPresent = Test-Path -LiteralPath $unownedAegisPath -PathType Leaf
    $unownedMaintainPresent = Test-Path -LiteralPath $unownedMaintainPath -PathType Leaf
    $unownedConflictPass = ($unownedUpgrade.Code -ne 0 -and $unownedUpgrade.Text -match 'INSTALL_CONFLICT' -and
        $unownedHashPreserved -and $unownedSnapshotPreserved -and -not $unownedAegisPresent -and
        -not $unownedMaintainPresent)
    Check 'R23_UNOWNED_RETIRED_FILE_CONFLICT_NONDESTRUCTIVE' $unownedConflictPass `
        ("exit=$($unownedUpgrade.Code); install_conflict=$($unownedUpgrade.Text -match 'INSTALL_CONFLICT'); user_file_preserved=$unownedHashPreserved; snapshot_preserved=$unownedSnapshotPreserved; aegis_present=$unownedAegisPresent; maintain_command_present=$unownedMaintainPresent`n$($unownedUpgrade.Text)")

    $second = Install $target $candidateArchive
    Check 'R6_REINSTALL' ($second.Code -eq 0 -and $second.Text -match '(?m)^NO_CHANGES\s*$')
    Check 'R12_UNRELATED_USER_FILE' ([IO.File]::ReadAllText((Join-Path $target 'user-notes.txt')) -eq "preserve me`n")
    $changed = Join-Path $target '.opencode/agents/kovan.md'
    [IO.File]::AppendAllText($changed, "`n# local drift`n", $utf8)
    $hash = (Get-FileHash -LiteralPath $changed -Algorithm SHA256).Hash
    $drift = Install $target $candidateArchive
    Check 'R7_DRIFT_REFUSED' ($drift.Code -ne 0 -and $drift.Text -match 'MANAGED_FILE_DRIFT' -and
        (Get-FileHash -LiteralPath $changed -Algorithm SHA256).Hash -eq $hash)
    Check 'R12_UNRELATED_STILL_PRESERVED' ([IO.File]::ReadAllText((Join-Path $target 'user-notes.txt')) -eq "preserve me`n")
    $rootPath = [IO.Path]::GetPathRoot($target)
    $unsafe = Install $rootPath $candidateArchive
    Check 'R8_FILESYSTEM_ROOT_REJECTED' ($unsafe.Code -ne 0 -and $unsafe.Text -match 'UNSAFE_TARGET|TARGET_NOT_GIT')
    Write-Output 'R8_REDIRECTS_CLOUD_CONTAINMENT: covered by Phase 4C target-security cases (run separately)'
    Write-Output 'RUNTIME_ARCHIVE_SOURCE: local archive fixtures were used; remote tag bytes/authentication were not queried.'
    $script:QualificationReceipt.state = 'TERMINAL_RESULT_WRITTEN'
    Save-QualificationReceipt
    if ($MockOpenCode) { Write-Output "RELEASE QUALIFICATION: $($script:CandidateVersion) PASS (local source; OpenCode CLI stubbed; no tag, push, or release created)" }
    else { Write-Output "RELEASE QUALIFICATION: $($script:CandidateVersion) PASS (local tag-shaped source archives; no tag, push, or release created)" }
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    if ($null -ne $script:QualificationReceipt) {
        $script:QualificationReceipt.state = 'FAILED_RESULT_WRITTEN'
        Save-QualificationReceipt
    }
    Write-Output 'RELEASE QUALIFICATION: FAIL'
    exit 1
} finally {
    if ($null -ne $isolatedEnvironment) { Exit-OlympusInstallerTestEnvironment $isolatedEnvironment }
    try { Stop-Transcript | Out-Null } catch { }
    if ($MockOpenCode -and $run -and (Test-Path -LiteralPath $run)) {
        $mockBin = Join-Path $run 'mock-bin'
        if (Test-Path -LiteralPath $mockBin) {
            $env:PATH = ($env:PATH -replace ('^' + [regex]::Escape($mockBin + [IO.Path]::PathSeparator)), '')
        }
    }
    if ($run -and (Test-Path -LiteralPath $run)) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop; break }
            catch {
                if ($attempt -eq 10) {
                    Write-Output "CLEANUP_DEFERRED: OpenCode/Windows still holds disposable fixture $run; remove after handles close."
                    break
                }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}
