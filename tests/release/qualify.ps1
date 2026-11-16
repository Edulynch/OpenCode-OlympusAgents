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

function New-SourceArchive([string]$sourceRoot, [string]$tag, [string]$archivePath, [switch]$MisreportStable) {
    $pack = Join-Path $run ('package-' + [guid]::NewGuid().ToString('N'))
    $top = Join-Path $pack "OpenCode-OlympusAgents-$tag"
    [IO.Directory]::CreateDirectory($top) | Out-Null
    # Keep the local archive fixture hermetic: unrelated user untracked files
    # are not release source. Include the one in-scope new document explicitly.
    $files = @(& git -C $sourceRoot ls-files --cached)
    if ($LASTEXITCODE -ne 0 -or $files.Count -eq 0) { throw 'GIT_FIXTURE_SOURCE_INVENTORY_FAIL' }
    $installationGuide = 'docs/INSTALLATION.md'
    if ((Test-Path -LiteralPath (Join-Path $sourceRoot $installationGuide) -PathType Leaf) -and $installationGuide -notin $files) {
        $files += $installationGuide
    }
    foreach ($relative in $files) {
        $sourceFile = Join-Path $sourceRoot $relative
        $destination = Join-Path $top $relative
        $destinationParent = Split-Path -Parent $destination
        [IO.Directory]::CreateDirectory($destinationParent) | Out-Null
        Copy-Item -LiteralPath $sourceFile -Destination $destination -Force
    }
    if ($MisreportStable) {
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

function Assert-QualificationRunPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path) -or -not [IO.Path]::IsPathFullyQualified($Path)) {
        throw 'HISTORICAL_FIXTURE_PATH_INVALID: Path must be absolute and inside the owned qualification run.'
    }
    $runPrefix = [IO.Path]::GetFullPath($run).TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd([char[]]@('\','/'))
    if (-not $fullPath.StartsWith($runPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'HISTORICAL_FIXTURE_PATH_INVALID: Path must be inside the owned qualification run.'
    }
    return $fullPath
}

function New-GitTagArchive([string]$tag, [string]$archivePath) {
    $archivePath = Assert-QualificationRunPath $archivePath
    $prefix = "OpenCode-OlympusAgents-$tag/"
    & git -C $source archive --format=zip "--prefix=$prefix" $tag -o $archivePath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
        throw "GIT_TAG_ARCHIVE_FAIL: $tag"
    }
    return $archivePath
}

function Get-HistoricalInstaller([string]$SourceRoot, [string]$ExpectedVersion) {
    $source = Assert-QualificationRunPath $SourceRoot
    if ($ExpectedVersion -notin @('v0.2.0','v0.3.0-beta.3') -or
        (Split-Path -Leaf $source) -cne "OpenCode-OlympusAgents-$ExpectedVersion") {
        throw "HISTORICAL_SOURCE_VERSION_MISMATCH: $ExpectedVersion is not an assigned historical tag source."
    }
    $installerPath = Assert-QualificationRunPath (Join-Path $source 'install.ps1')
    $bootstrapPath = Assert-QualificationRunPath (Join-Path $source 'scripts/bootstrap.ps1')
    if (-not (Test-Path -LiteralPath $source -PathType Container) -or
        -not (Test-Path -LiteralPath $installerPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $bootstrapPath -PathType Leaf)) {
        throw 'HISTORICAL_SOURCE_INVALID: Installer or bootstrap is missing from the extracted tag source.'
    }
    $text = [IO.File]::ReadAllText($installerPath)
    $default = [regex]::Match($text, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''\s*,?\s*$')
    $release = [regex]::Match($text, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''')
    if (-not $default.Success -or $default.Groups[1].Value -cne $ExpectedVersion -or
        ($release.Success -and $release.Groups[1].Value -cne $ExpectedVersion)) {
        throw "HISTORICAL_SOURCE_VERSION_MISMATCH: Expected $ExpectedVersion in $installerPath."
    }
    return [pscustomobject]@{
        SourceRoot = $source
        InstallerPath = $installerPath
        Version = $default.Groups[1].Value
    }
}

function Expand-HistoricalSource([string]$ArchivePath, [string]$ExpectedVersion) {
    $archive = Assert-QualificationRunPath $ArchivePath
    $destination = Assert-QualificationRunPath (Join-Path $run ('historical-source-' + ($ExpectedVersion -replace '[^A-Za-z0-9.-]', '-')))
    if (-not (Test-Path -LiteralPath $archive -PathType Leaf) -or (Test-Path -LiteralPath $destination)) {
        throw 'HISTORICAL_SOURCE_INVALID: Archive is missing or the owned extraction destination already exists.'
    }
    [IO.Directory]::CreateDirectory($destination) | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $destination -ErrorAction Stop
    $roots = @(Get-ChildItem -LiteralPath $destination -Force)
    $expectedRoot = "OpenCode-OlympusAgents-$ExpectedVersion"
    if ($roots.Count -ne 1 -or -not $roots[0].PSIsContainer -or $roots[0].Name -cne $expectedRoot) {
        throw "HISTORICAL_SOURCE_INVALID: Expected the single tag-shaped archive root '$expectedRoot'."
    }
    $source = Assert-QualificationRunPath $roots[0].FullName
    [void](Get-HistoricalInstaller $source $ExpectedVersion)
    return $source
}

function Install-Historical([string]$SourceRoot, [string]$Target, [string]$Version) {
    $source = Assert-QualificationRunPath $SourceRoot
    $targetRoot = Assert-QualificationRunPath $Target
    $identity = Get-HistoricalInstaller $source $Version
    if (-not (Test-Path -LiteralPath $targetRoot -PathType Container)) {
        throw 'HISTORICAL_FIXTURE_TARGET_INVALID: Target must be an existing fixture directory.'
    }
    $args = @('-NoProfile', '-File', $identity.InstallerPath, '-Version', $identity.Version,
        '-SourceRoot', $identity.SourceRoot, '-Target', $targetRoot)
    $output = (& pwsh @args 2>&1 | Out-String)
    [pscustomobject]@{
        Text = $output
        Code = $LASTEXITCODE
        Version = $identity.Version
        SourceRoot = $identity.SourceRoot
        InstallerPath = $identity.InstallerPath
    }
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
        if ([IO.File]::ReadAllText($bootstrap) -match '(?m)^\s*\[switch\]\$VerifyOnly') {
            $output = (& pwsh -NoProfile -File $bootstrap -Target $target -SourceVersion $version -VerifyOnly 2>&1 | Out-String)
            return [pscustomobject]@{ Text=$output; Code=$LASTEXITCODE }
        }
        Assert-LegacyOpenCodeInstall $fixture $version $target $bootstrap
        return [pscustomobject]@{ Text="OLYMPUS_VERIFY: $version PASS"; Code=0 }
    } catch {
        $message = $_.Exception.Message
        $reason = if ($message -match '^([A-Z_]+):') { $Matches[1] } else { 'VERIFY_FAILED' }
        return [pscustomobject]@{ Text="OLYMPUS_VERIFY: $version FAIL`nOLYMPUS_VERIFY_REASON: $reason`n$message"; Code=1 }
    }
}

# Keep legacy project qualification on internal engines. Reuse the real source
# identity functions without executing the now-global public installer body.
$tokens = $null; $parseErrors = $null
$installerAst = [Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'QUALIFICATION_INSTALLER_PARSE_FAILED' }
foreach ($name in @('Get-DeclaredReleaseVersion','Assert-ArchiveTag','Get-ContentHash','Get-LegacyManagedSourcePaths','Assert-LegacyOpenCodeInstall')) {
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
    $candidateArchive = New-SourceArchive $source $script:CandidateVersion (Join-Path $run "candidate-$($script:CandidateVersion).zip")
    $stableArchive = New-GitTagArchive 'v0.2.0' (Join-Path $run 'stable-v020.zip')
    $previousBetaArchive = New-GitTagArchive 'v0.3.0-beta.3' (Join-Path $run 'previous-beta3.zip')
    $stableHistoricalSource = Expand-HistoricalSource $stableArchive 'v0.2.0'
    $previousBetaHistoricalSource = Expand-HistoricalSource $previousBetaArchive 'v0.3.0-beta.3'
    $wrongHistoricalVersionRejected = $false
    try { [void](Get-HistoricalInstaller $stableHistoricalSource $script:CandidateVersion) }
    catch { $wrongHistoricalVersionRejected = $_.Exception.Message -match '^HISTORICAL_SOURCE_VERSION_MISMATCH:' }
    Check 'R0_HISTORICAL_SOURCE_REJECTS_CANDIDATE_VERSION' $wrongHistoricalVersionRejected `
        'Historical source identity mismatch is rejected before any historical installer launch.'
    $alphaArchive = New-SourceArchive $source 'v0.3.0-alpha.1' (Join-Path $run 'alpha.zip')
    $betaArchive = New-SourceArchive $source 'v0.3.0-beta.2' (Join-Path $run 'beta.zip')
    $rcArchive = New-SourceArchive $source 'v0.3.0-rc.1' (Join-Path $run 'rc.zip')
    $mismatchArchive = New-SourceArchive $source $script:CandidateVersion (Join-Path $run "mismatch-$($script:CandidateVersion)-to-v020.zip") -MisreportStable

    $versionText = $installerText
    $releaseIdentityValid = ($versionText -match "(?m)^\s*\[string\]\`$Version\s*=\s*'$($script:CandidateRegex)'" -and
        $versionText -match "(?m)^\`$ReleaseVersion\s*=\s*'$($script:CandidateRegex)'")
    $patternMatch = [regex]::Match($versionText, "(?s)\[ValidatePattern\('([^']+)'\)\]\s*\[string\]\`$Version")
    $versionPattern = if ($patternMatch.Success) { $patternMatch.Groups[1].Value } else { '' }
    $acceptedSyntax = @('v1.2.3','v0.3.0-alpha.1',$script:CandidateVersion,'v2.4.0-rc.12' | Where-Object { $_ -match $versionPattern }).Count -eq 4
    if (-not ($ResumeAtR1 -or $ResumeAtPermissions)) {
        Check 'R0_RELEASE_IDENTITY' $releaseIdentityValid
        Check 'R0_TARGET_IDENTITY_V080' ($script:CandidateVersion -ceq 'v0.8.0')
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
            kael=@('gpt-6.1-sol','high','primary'); thales=@('gpt-6.1-sol','xhigh','subagent'); atlas=@('gpt-6.1-sol','high','subagent'); argus=@('gpt-6.1-sol','high','subagent'); talos=@('gpt-6.1-sol','high','subagent'); helios=@('gpt-6.1-sol','high','subagent')
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
    Check 'R11_FAST_POLICY' ($kaelText -match 'MAX_ACTIVE_CHILDREN = 4' -and $kaelText -match 'minimum useful parallelism' -and
        $kaelText -match 'FAST' -and $kaelText -match 'balanced shards: 20 items / 4 workers = 5/5/5/5')

    # Stable SemVer remains installable explicitly; prerelease identifiers are accepted end-to-end.
    $stableTarget = New-Target 'explicit-stable-v020'
    $stable = Install-Historical $stableHistoricalSource $stableTarget 'v0.2.0'
    $stableManifestPath = Join-Path $stableTarget '.opencode/orchestrator-install.json'
    $stableManifest = if (Test-Path -LiteralPath $stableManifestPath -PathType Leaf) {
        try { Get-Content -LiteralPath $stableManifestPath -Raw | ConvertFrom-Json -ErrorAction Stop }
        catch { $null }
    } else { $null }
    $stableInstallPass = ($stable.Code -eq 0 -and $stable.Version -ceq 'v0.2.0' -and
        $stable.SourceRoot -ceq $stableHistoricalSource -and
        $stable.InstallerPath -ceq (Join-Path $stableHistoricalSource 'install.ps1') -and
        $stable.Text -match 'OLYMPUS_INSTALL: v0\.2\.0 READY_OR_NO_CHANGES' -and
        $null -ne $stableManifest -and $stableManifest.schema_version -eq 1 -and
        @($stableManifest.managed_files).Count -gt 0)
    Check 'R13_EXPLICIT_STABLE_INSTALL' $stableInstallPass `
        "installer=$($stable.InstallerPath); exit=$($stable.Code)`n$($stable.Text)"
    $stableVerify = Verify $stableTarget $stableArchive 'v0.2.0'
    Check 'R24_STABLE_INSTALL_VERIFY_PASS' ($stableVerify.Code -eq 0 -and $stableVerify.Text -match '(?m)^OLYMPUS_VERIFY: v0\.2\.0 PASS\s*$')
    $unexpectedLegacyAgent = Join-Path $stableTarget '.opencode/agents/aegis.md'
    [IO.File]::WriteAllText($unexpectedLegacyAgent, "id: aegis`n", $utf8)
    $unexpectedAgentSnapshot = Get-ProjectSnapshot $stableTarget
    $unexpectedAgentVerify = Verify $stableTarget $stableArchive 'v0.2.0'
    Check 'R24_LEGACY_VERIFY_REJECTS_UNEXPECTED_OLYMPUS_AGENT' ($unexpectedAgentVerify.Code -ne 0 -and
        $unexpectedAgentVerify.Text -match 'OLYMPUS_VERIFY_REASON: ROSTER_MISMATCH')
    Check 'R24_LEGACY_VERIFY_UNEXPECTED_AGENT_READ_ONLY' ((Get-ProjectSnapshot $stableTarget) -ceq $unexpectedAgentSnapshot)
    Remove-Item -LiteralPath $unexpectedLegacyAgent -Force
    foreach ($entry in @(@('alpha','v0.3.0-alpha.1',$alphaArchive), @('beta','v0.3.0-beta.2',$betaArchive), @('rc','v0.3.0-rc.1',$rcArchive))) {
        $semverTarget = New-Target ('semver-' + $entry[0])
        $result = Install $semverTarget $entry[2] $entry[1]
        $semverManifestPath = Join-Path $semverTarget '.opencode/orchestrator-install.json'
        $semverManifest = if (Test-Path -LiteralPath $semverManifestPath) { Get-Content -LiteralPath $semverManifestPath -Raw | ConvertFrom-Json } else { $null }
        Check ('R14_' + $entry[0].ToUpperInvariant() + '_ACCEPTED') ($result.Code -eq 0 -and
            $result.Text -match ('OLYMPUS_SOURCE: requested=' + [regex]::Escape($entry[1]) + ' resolved=' + [regex]::Escape($entry[1])) -and
            $null -ne $semverManifest -and $semverManifest.installed_version -eq $entry[1])
    }

    $legacyTarget = New-Target 'verify-legacy-unknown-commit'
    $legacyInstall = Install $legacyTarget $candidateArchive $script:CandidateVersion
    if ($legacyInstall.Code -ne 0) { throw 'Candidate fixture install failed before unknown-commit verification.' }
    $legacyManifestPath = Join-Path $legacyTarget '.opencode/orchestrator-install.json'
    $legacyManifest = Get-Content -LiteralPath $legacyManifestPath -Raw | ConvertFrom-Json
    $legacyManifest.installed_from_commit = 'unknown'
    [void]$legacyManifest.PSObject.Properties.Remove('installed_version')
    [IO.File]::WriteAllText($legacyManifestPath, (($legacyManifest | ConvertTo-Json -Depth 30) + "`n"), $utf8)
    $legacySnapshot = Get-ProjectSnapshot $legacyTarget
    $legacyVerify = Verify $legacyTarget $candidateArchive $script:CandidateVersion
    Check 'R24_UNKNOWN_COMMIT_VERIFIED_BY_CONTENT' ($legacyVerify.Code -eq 0 -and
        $legacyVerify.Text -match "(?m)^OLYMPUS_VERIFY: $($script:CandidateRegex) PASS\s*$")
    Check 'R24_VERIFY_ONLY_READ_ONLY' ((Get-ProjectSnapshot $legacyTarget) -ceq $legacySnapshot)

    $oldStableMismatch = Verify $stableTarget $candidateArchive $script:CandidateVersion
    Check 'R24_CANDIDATE_VS_INSTALLED_STABLE_FAIL' ($oldStableMismatch.Code -ne 0 -and
        $oldStableMismatch.Text -match "(?m)^OLYMPUS_VERIFY: $($script:CandidateRegex) FAIL\s*$" -and
        $oldStableMismatch.Text -match 'OLYMPUS_VERIFY_REASON: MANAGED_FILE_MISMATCH')
    $previousBetaTarget = New-Target 'previous-beta3-historical-install'
    $previousBetaInstall = Install-Historical $previousBetaHistoricalSource $previousBetaTarget 'v0.3.0-beta.3'
    $previousBetaManifestPath = Join-Path $previousBetaTarget '.opencode/orchestrator-install.json'
    $previousBetaManifest = if (Test-Path -LiteralPath $previousBetaManifestPath -PathType Leaf) {
        try { Get-Content -LiteralPath $previousBetaManifestPath -Raw | ConvertFrom-Json -ErrorAction Stop }
        catch { $null }
    } else { $null }
    $previousBetaInstallPass = ($previousBetaInstall.Code -eq 0 -and
        $previousBetaInstall.Version -ceq 'v0.3.0-beta.3' -and
        $previousBetaInstall.SourceRoot -ceq $previousBetaHistoricalSource -and
        $previousBetaInstall.InstallerPath -ceq (Join-Path $previousBetaHistoricalSource 'install.ps1') -and
        $previousBetaInstall.Text -match 'OLYMPUS_INSTALL: v0\.3\.0-beta\.3 READY_OR_NO_CHANGES' -and
        $null -ne $previousBetaManifest -and $previousBetaManifest.schema_version -eq 1 -and
        $previousBetaManifest.installed_version -ceq 'v0.3.0-beta.3' -and
        @($previousBetaManifest.managed_files).Count -gt 0)
    Check 'R27_PREVIOUS_BETA3_SAME_TAG_INSTALL' $previousBetaInstallPass `
        "installer=$($previousBetaInstall.InstallerPath); exit=$($previousBetaInstall.Code)`n$($previousBetaInstall.Text)"
    $previousBetaSnapshot = Get-ProjectSnapshot $previousBetaTarget
    $previousBetaVerify = Verify $previousBetaTarget $previousBetaArchive 'v0.3.0-beta.3'
    Check 'R27_PREVIOUS_BETA3_VERIFY_READ_ONLY' ($previousBetaVerify.Code -eq 0 -and
        $previousBetaVerify.Text -match '(?m)^OLYMPUS_VERIFY: v0\.3\.0-beta\.3 PASS\s*$' -and
        (Get-ProjectSnapshot $previousBetaTarget) -ceq $previousBetaSnapshot)
    [IO.File]::WriteAllText((Join-Path $previousBetaTarget '.opencode/agents/maintenance.md'), "id: maintenance`n", $utf8)
    $previousBetaRosterSnapshot = Get-ProjectSnapshot $previousBetaTarget
    $previousBetaRosterVerify = Verify $previousBetaTarget $previousBetaArchive 'v0.3.0-beta.3'
    $previousBetaRosterReadOnly = (Get-ProjectSnapshot $previousBetaTarget) -ceq $previousBetaRosterSnapshot
    Check 'R27_PREVIOUS_BETA3_ROSTER_NEGATIVE_READ_ONLY' ($previousBetaRosterVerify.Code -ne 0 -and
        $previousBetaRosterVerify.Text -match 'OLYMPUS_VERIFY_REASON: ROSTER_MISMATCH' -and
        $previousBetaRosterReadOnly) `
        "exit=$($previousBetaRosterVerify.Code); read_only=$previousBetaRosterReadOnly`n$($previousBetaRosterVerify.Text)"
    Remove-Item -LiteralPath (Join-Path $previousBetaTarget '.opencode/agents/maintenance.md') -Force
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
    $retiredVerify = Verify $retiredAgentTarget $candidateArchive $script:CandidateVersion
    Check 'R24_CANDIDATE_ROSTER_REJECTS_MAINTENANCE' ($retiredVerify.Code -ne 0 -and
        $retiredVerify.Text -match 'OLYMPUS_VERIFY_REASON: ROSTER_MISMATCH')

    $sourceMismatchVerify = Verify $legacyTarget $mismatchArchive $script:CandidateVersion
    Check 'R24_REQUESTED_SOURCE_VERSION_MISMATCH_FAIL' ($sourceMismatchVerify.Code -ne 0 -and
        $sourceMismatchVerify.Text -match 'OLYMPUS_VERIFY_REASON: SOURCE_VERSION_MISMATCH')

    # Public wrappers (12 variants) must use tag-pinned executable sources.
    function Test-PublicWrapperSource([string]$Content, [string]$Tag,
        [string]$Action, [string]$Scope, [string]$Harness) {
        if ($Scope -ne 'global' -or $Harness -ne 'opencode') {
            $tokens = $null; $errors = $null
            $ast = [Management.Automation.Language.Parser]::ParseInput($Content, [ref]$tokens, [ref]$errors)
            return ($errors.Count -eq 0 -and $ast.EndBlock.Statements.Count -eq 1 -and
                $ast.EndBlock.Statements[0] -is [Management.Automation.Language.ThrowStatementAst])
        }
        $valid = if ($Action -eq 'install') {
            $Content.Contains('https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1')
        } else { $Content.Contains('uninstall --execute') }
        return ($valid -and $Content -notmatch '-Harness|-Scope|-Target|/master/')
    }

    $wrapperIssues = @()
    foreach ($action in @('install','uninstall')) {
        foreach ($scope in @('project','global')) {
            foreach ($harness in @('opencode','codex','all')) {
                $relative = "$action/$scope/$harness.ps1"
                $wrapperText = [IO.File]::ReadAllText((Join-Path $source ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)))
                if (-not (Test-PublicWrapperSource $wrapperText $script:CandidateVersion $action $scope $harness)) {
                    $wrapperIssues += $relative
                }
            }
        }
    }
    Check 'R25_PUBLIC_WRAPPER_TAGGED_SOURCES_AND_ARGUMENTS' ($wrapperIssues.Count -eq 0) ($wrapperIssues -join ', ')

    function Test-UnifiedEntrypointSource([string]$Content, [string]$Action) {
        return ($Content.Contains('$launcherUrl = "https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$tag/scripts/launch-latest.ps1"') -and
            $Content.Contains('https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest') -and
            $Content.Contains("Assert-BootstrapReleaseBoolean `$release 'immutable' `$true") -and
            $Content.Contains('LATEST_RELEASE_MUTABLE') -and
            $Content.Contains('LATEST_RELEASE_IDENTITY_MISMATCH') -and
            $Content.Contains('LAUNCHER_BOOTSTRAP_CONTRACT_MISSING') -and
            $Content.Contains('no older launcher fallback is attempted') -and
            -not $Content.Contains('/v0.4.9/scripts/launch-latest.ps1') -and
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
        -not (Test-PublicWrapperSource $badMutable $script:CandidateVersion 'install' 'global' 'opencode') -and
        -not (Test-PublicWrapperSource $badWrongHarness $script:CandidateVersion 'install' 'global' 'opencode') -and
        -not (Test-PublicWrapperSource $badForeignSource $script:CandidateVersion 'install' 'global' 'opencode') -and
        -not (Test-PublicWrapperSource $badOldTag $script:CandidateVersion 'install' 'global' 'opencode'))

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
    $requiredHighlights = @('global OpenCode','default_agent_receipt','pending_set','pending_uninstall',
        'config apply --dry-run','--execute','read-only','immutable','selected tag')
    $missingHighlights = @($requiredHighlights | Where-Object { -not $releaseNotes.Contains($_) })
    Check 'R25_CURRENT_RELEASE_HIGHLIGHTS' ($missingHighlights.Count -eq 0)
    Check 'R25_CURRENT_CAPABILITY_GAPS_NOT_OVERCLAIMED' ($releaseNotes -match 'DENY\s*=\s*GAP' -and
        $releaseNotes -match 'CONTEXTUAL_OLYMPUS_MAINTENANCE\s*=\s*GAP' -and
        $releaseNotes -match 'QUESTION_CENTRALIZATION\s*=\s*PARTIAL' -and
        $releaseNotes -match 'RESULT_RECONCILIATION\s*=\s*PARTIAL' -and
        $releaseNotes -match 'ACTIVITY_VISIBILITY\s*=\s*PARTIAL\b' -and
        $releaseNotes -notmatch '(?i)AEGIS\s*=\s*GAP|PARTIAL/BASIC' -and
        $releaseNotes -match '(?i)does not establish broad version compatibility' -and
        $releaseNotes -notmatch '(?i)Codex (?:has|provides|supports) (?:full parity|hard DENY|Aegis)')
    $mutableExecutableUrl = '(?i)(?:raw\.githubusercontent\.com/Edulynch/OpenCode-OlympusAgents/(?:master|main|refs/heads/(?:master|main))/[^\s]+?\.ps1|github\.com/Edulynch/OpenCode-OlympusAgents/(?:raw|blob)/(?:master|main)/[^\s]+?\.ps1)'
    Check 'R25_RELEASE_NO_MUTABLE_EXECUTABLE_SOURCE' ($releaseNotes -notmatch $mutableExecutableUrl -and
        $versionText -match 'archive/refs/tags/\$Version\.zip')

    $readme = [IO.File]::ReadAllText((Join-Path $source 'README.md'))
    $fastInstallUrl = 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1'
    $pinnedInstallCommand = "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$($script:CandidateVersion)/install.ps1')))"
    function Get-ReadmePowerShellCodeBlocks([string]$Markdown) {
        $blocks = [System.Collections.Generic.List[string]]::new()
        foreach ($block in [regex]::Matches($Markdown, '(?ims)^```(?:powershell|pwsh|ps1)[ \t]*\r?\n(?<body>.*?)^```[ \t]*\r?$')) {
            $blocks.Add($block.Groups['body'].Value)
        }
        return $blocks.ToArray()
    }
    function Get-ReadmePowerShellParse([string]$Markdown) {
        $statements = [System.Collections.Generic.List[object]]::new()
        $hasParseErrors = $false
        foreach ($code in @(Get-ReadmePowerShellCodeBlocks $Markdown)) {
            $tokens = $null
            $parseErrors = $null
            $ast = [System.Management.Automation.Language.Parser]::ParseInput($code, [ref]$tokens, [ref]$parseErrors)
            if ($parseErrors.Count -gt 0) { $hasParseErrors = $true }
            foreach ($statement in $ast.EndBlock.Statements) { $statements.Add($statement) }
        }
        return [pscustomobject]@{ Statements = $statements.ToArray(); HasParseErrors = $hasParseErrors }
    }
    function Test-ReadmeExpectedBootstrapStatement($Statement, [string]$ExpectedCommand) {
        $tokens = $null
        $parseErrors = $null
        $expectedAst = [System.Management.Automation.Language.Parser]::ParseInput($ExpectedCommand, [ref]$tokens, [ref]$parseErrors)
        if ($parseErrors.Count -gt 0 -or $expectedAst.EndBlock.Statements.Count -ne 1 -or
            $Statement -isnot [System.Management.Automation.Language.PipelineAst]) { return $false }
        $expectedStatement = $expectedAst.EndBlock.Statements[0]
        return ($Statement -is [System.Management.Automation.Language.PipelineAst] -and
            $expectedStatement -is [System.Management.Automation.Language.PipelineAst] -and
            -not $Statement.Background -and -not $expectedStatement.Background -and
            $Statement.Extent.Text.Trim() -ceq $expectedStatement.Extent.Text.Trim())
    }
    function Get-ReadmeFastSection([string]$Markdown, [string]$Heading) {
        return [regex]::Match($Markdown,
            '(?ims)^##[ \t]+' + [regex]::Escape($Heading) + '[ \t]*\r?\n(?<body>.*?)(?=^##[ \t]+|\z)')
    }
    function Test-ReadmeFastCommandContract([string]$Markdown, [string]$InstallCommand, [string]$UninstallCommand) {
        if ([regex]::Matches($Markdown, '(?im)^##[ \t]+Fast Install[ \t]*\r?$').Count -ne 1 -or
            [regex]::Matches($Markdown, '(?im)^##[ \t]+Fast Uninstall[ \t]*\r?$').Count -ne 1 -or
            [regex]::Matches($Markdown, '(?im)^##[ \t]+Fast\b[^\r\n]*\r?$').Count -ne 2) {
            return $false
        }
        $installSection = Get-ReadmeFastSection $Markdown 'Fast Install'
        $uninstallSection = Get-ReadmeFastSection $Markdown 'Fast Uninstall'
        if (-not $installSection.Success -or -not $uninstallSection.Success) { return $false }
        $installParsed = Get-ReadmePowerShellParse $installSection.Groups['body'].Value
        $uninstallParsed = Get-ReadmePowerShellParse $uninstallSection.Groups['body'].Value
        return (-not $installParsed.HasParseErrors -and -not $uninstallParsed.HasParseErrors -and
            $installParsed.Statements.Count -eq 1 -and
            (Test-ReadmeExpectedBootstrapStatement $installParsed.Statements[0] $InstallCommand) -and
            $uninstallParsed.Statements.Count -eq 1 -and
            (Test-ReadmeExpectedBootstrapStatement $uninstallParsed.Statements[0] $UninstallCommand) -and
            [regex]::IsMatch($Markdown, '(?im)\[[^\]]+\]\(docs/INSTALLATION\.md(?:#[^)]+)?\)'))
    }
    function Test-ReadmeGlobalInstallerContract([string]$Markdown, [string]$InstallCommand, [string]$UninstallCommand) {
        $parsed = Get-ReadmePowerShellParse $Markdown
        if ($parsed.HasParseErrors) { return $false }
        $remoteNames = '^(?:irm|iwr|curl(?:\.exe)?|wget(?:\.exe)?|invoke-restmethod|invoke-webrequest|iex|invoke-expression)$'
        $launcherNames = '^(?:pwsh(?:\.exe)?|powershell(?:\.exe)?|start-process)$'
        $installerPath = '(?i)(?:^|[\\/])(?:install|uninstall)(?:-olympus)?\.ps1$'
        $installerFileMention = '(?i)(?:install|uninstall)(?:-olympus)?\.ps1\b'
        $remoteStatements = [System.Collections.Generic.List[object]]::new()
        $directInstallerFound = $false
        foreach ($statement in $parsed.Statements) {
            $commands = @($statement.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true))
            $hasRemoteCommand = $false
            foreach ($command in $commands) {
                $name = [string]$command.GetCommandName()
                if ($name -match $remoteNames) { $hasRemoteCommand = $true }
                if (($name -match $launcherNames -and $statement.Extent.Text -match $installerFileMention) -or
                    $name -match $installerPath) {
                    $directInstallerFound = $true
                }
            }
            if ($hasRemoteCommand) { $remoteStatements.Add($statement) }
        }
        if ($directInstallerFound -or $remoteStatements.Count -ne 2) { return $false }
        $installCount = 0
        $pinnedInstallCount = 0
        $uninstallCount = 0
        foreach ($statement in $remoteStatements) {
            if (Test-ReadmeExpectedBootstrapStatement $statement $InstallCommand) { $installCount++ }
            elseif (Test-ReadmeExpectedBootstrapStatement $statement $pinnedInstallCommand) { $pinnedInstallCount++ }
            elseif (Test-ReadmeExpectedBootstrapStatement $statement $UninstallCommand) { $uninstallCount++ }
            else { return $false }
        }
        return ($installCount -eq 1 -and $pinnedInstallCount -eq 1 -and $uninstallCount -eq 0)
    }
    $fastInstallCommand = "& ([scriptblock]::Create((irm '$fastInstallUrl')))"
    $fastUninstallCommand = 'olympus uninstall'
    $readmeWithLf = $readme.Replace("`r`n", "`n")
    $readmeWithCrLf = $readmeWithLf.Replace("`n", "`r`n")
    Check 'R25_README_FAST_CONTRACT_ACCEPTS_LF_AND_CRLF' (
        (Test-ReadmeFastCommandContract $readmeWithLf $fastInstallCommand $fastUninstallCommand) -and
        (Test-ReadmeFastCommandContract $readmeWithCrLf $fastInstallCommand $fastUninstallCommand) -and
        $readme.Contains($fastInstallUrl) -and
        $readme.Contains('olympus uninstall') -and
        $readme.Contains('published, immutable') -and
        $readme.Contains($pinnedInstallCommand) -and
        $readme -match '(?i)global and OpenCode-only' -and
        -not $readme.Contains('/' + $script:CandidateVersion + '/install-olympus.ps1') -and
        -not $readme.Contains('/' + $script:CandidateVersion + '/uninstall-olympus.ps1'))
    $readmeWithExtraFastHeadingLf = $readmeWithLf + "`n## Fast Extra`n"
    $readmeWithExtraFastHeadingCrLf = $readmeWithCrLf + "`r`n## Fast Extra`r`n"
    Check 'R25_README_REJECTS_EXTRA_FAST_HEADING_LF_AND_CRLF' (
        -not (Test-ReadmeFastCommandContract $readmeWithExtraFastHeadingLf $fastInstallCommand $fastUninstallCommand) -and
        -not (Test-ReadmeFastCommandContract $readmeWithExtraFastHeadingCrLf $fastInstallCommand $fastUninstallCommand))
    Check 'R25_README_HAS_ONLY_TWO_PINNED_FAST_COMMANDS' (
        (Test-ReadmeFastCommandContract $readme $fastInstallCommand $fastUninstallCommand) -and
        (Test-Path -LiteralPath (Join-Path $source 'docs/INSTALLATION.md') -PathType Leaf))
    Check 'R25_README_GLOBAL_INSTALL_COMMANDS_REMAIN_PINNED' (
        Test-ReadmeGlobalInstallerContract $readme $fastInstallCommand $fastUninstallCommand)
    $thirdPrimaryCommand = 'pwsh -NoProfile -File .\install-olympus.ps1 -Project -Here -Harness all'
    $readmeWithThirdPrimaryCommand = $readme.Replace($fastInstallCommand, $fastInstallCommand + "`n" + $thirdPrimaryCommand)
    if (-not $readmeWithThirdPrimaryCommand.Contains($thirdPrimaryCommand)) {
        throw 'R25_NEGATIVE_CONTROL_SETUP_FAILED: direct third Fast Install command was not inserted.'
    }
    Check 'R25_README_REJECTS_THIRD_EXECUTABLE_PRIMARY_COMMAND' (
        -not (Test-ReadmeFastCommandContract $readmeWithThirdPrimaryCommand $fastInstallCommand $fastUninstallCommand))
    $indirectThirdCommand = "& ([scriptblock]::Create((irm '$fastInstallUrl'))) -Global -Harness all"
    $readmeWithIndirectThirdCommand = $readme.Replace($fastInstallCommand, $fastInstallCommand + "`n" + $indirectThirdCommand)
    if (-not $readmeWithIndirectThirdCommand.Contains($indirectThirdCommand)) {
        throw 'R25_NEGATIVE_CONTROL_SETUP_FAILED: indirect ScriptBlock.Create command was not inserted.'
    }
    Check 'R25_README_REJECTS_INDIRECT_SCRIPTBLOCK_COMMAND' (
        -not (Test-ReadmeFastCommandContract $readmeWithIndirectThirdCommand $fastInstallCommand $fastUninstallCommand))
    $thirdBootstrapOutsideFast = $readme + "`n## Alternative setup`n`n" + '```powershell' + "`n" +
        $fastInstallCommand + "`n" + '```' + "`n"
    $alternativeSection = Get-ReadmeFastSection $thirdBootstrapOutsideFast 'Alternative setup'
    if (-not $alternativeSection.Success -or
        -not ($alternativeSection.Groups['body'].Value.Contains($fastInstallCommand))) {
        throw 'R25_NEGATIVE_CONTROL_SETUP_FAILED: third bootstrap was not placed under another heading.'
    }
    Check 'R25_README_REJECTS_GLOBAL_BOOTSTRAP_OUTSIDE_FAST' (
        -not (Test-ReadmeGlobalInstallerContract $thirdBootstrapOutsideFast $fastInstallCommand $fastUninstallCommand))
    $mutableBootstrapCommand = "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install-olympus.ps1')))"
    $readmeWithMutableBootstrap = $readme.Replace($fastInstallCommand, $mutableBootstrapCommand)
    if (-not $readmeWithMutableBootstrap.Contains($mutableBootstrapCommand)) {
        throw 'R25_NEGATIVE_CONTROL_SETUP_FAILED: mutable bootstrap command was not inserted.'
    }
    Check 'R25_README_REJECTS_MUTABLE_BOOTSTRAP_SOURCE' (
        -not (Test-ReadmeFastCommandContract $readmeWithMutableBootstrap $fastInstallCommand $fastUninstallCommand))
    $candidateBootstrapCommand = "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$($script:CandidateVersion)/install-olympus.ps1')))"
    $readmeWithCandidateBootstrap = $readme.Replace($fastInstallCommand, $candidateBootstrapCommand)
    if (-not $readmeWithCandidateBootstrap.Contains($candidateBootstrapCommand)) {
        throw 'R25_NEGATIVE_CONTROL_SETUP_FAILED: candidate bootstrap command was not inserted.'
    }
    Check 'R25_README_REJECTS_UNPUBLISHED_CANDIDATE_BOOTSTRAP' (
        -not (Test-ReadmeFastCommandContract $readmeWithCandidateBootstrap $fastInstallCommand $fastUninstallCommand))
    $legacyIexCommand = "irm $fastInstallUrl | iex"
    $readmeWithLegacyIex = $readme.Replace($fastInstallCommand, $legacyIexCommand)
    if (-not $readmeWithLegacyIex.Contains($legacyIexCommand)) {
        throw 'R25_NEGATIVE_CONTROL_SETUP_FAILED: legacy IEX command was not inserted.'
    }
    Check 'R25_README_REJECTS_PUBLISHED_LEGACY_IEX_INVOCATION' (
        -not (Test-ReadmeFastCommandContract $readmeWithLegacyIex $fastInstallCommand $fastUninstallCommand))
    $foreignBootstrapCommand = "& ([scriptblock]::Create((irm 'https://example.invalid/install-olympus.ps1')))"
    $readmeWithForeignBootstrap = $readme.Replace($fastInstallCommand, $foreignBootstrapCommand)
    if (-not $readmeWithForeignBootstrap.Contains($foreignBootstrapCommand)) {
        throw 'R25_NEGATIVE_CONTROL_SETUP_FAILED: foreign bootstrap command was not inserted.'
    }
    Check 'R25_README_REJECTS_FOREIGN_BOOTSTRAP_ENDPOINT' (
        -not (Test-ReadmeFastCommandContract $readmeWithForeignBootstrap $fastInstallCommand $fastUninstallCommand))
    $readmeWithDescriptions = $readme + "`n## Command references`n`nThe example ``irm $fastInstallUrl | iex`` is descriptive only; see [installer reference](https://example.invalid/install-olympus.ps1).`n`n## Commented example`n`n" +
        '```powershell' + "`n# irm https://example.invalid/install-olympus.ps1 | iex`n" + '```' + "`n"
    Check 'R25_README_IGNORES_PROSE_LINKS_AND_COMMENTS' (
        (Test-ReadmeFastCommandContract $readmeWithDescriptions $fastInstallCommand $fastUninstallCommand) -and
        (Test-ReadmeGlobalInstallerContract $readmeWithDescriptions $fastInstallCommand $fastUninstallCommand))
    Check 'R25_INSTALLATION_GUIDE_HAS_SCOPE_HARNESS_SAFETY_AND_STATUS' (
        $installGuide.Contains($fastInstallUrl) -and $installGuide.Contains($fastUninstallCommand) -and
        $installGuide.Contains($script:CandidateVersion) -and
        $installGuide.Contains('https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest') -and
        $installGuide.Contains($pinnedInstallCommand) -and
        $installGuide.Contains('immutable=true') -and
        $installGuide.Contains('time-zone-aware') -and
        $installGuide.Contains('published_at') -and
        $installGuide.Contains('tag_name') -and
        $installGuide.Contains('matching version and release markers') -and
        $installGuide.Contains('older-launcher fallback') -and
        -not $installGuide.Contains('/' + $script:CandidateVersion + '/install-olympus.ps1') -and
        -not $installGuide.Contains('/' + $script:CandidateVersion + '/uninstall-olympus.ps1') -and
        $installGuide.Contains('ACTIVE DEVELOPMENT') -and
        $installGuide.Contains('FROZEN COMPATIBILITY') -and
        $installGuide.Contains('default_agent_receipt') -and $installGuide.Contains('pending_set') -and
        $installGuide.Contains('pending_uninstall') -and $installGuide.Contains('opencode') -and
        $installGuide.Contains('codex') -and $installGuide.Contains('all') -and
        $installGuide.Contains('immutable=true') -and $installGuide.Contains('VerifyOnly'))
    $v049Start = $changelog.IndexOf('## v0.4.9', [StringComparison]::Ordinal)
    $afterV049 = if ($v049Start -ge 0) { $changelog.Substring($v049Start) } else { '' }
    $v048Offset = $afterV049.IndexOf('## v0.4.8', [StringComparison]::Ordinal)
    $v049History = if ($v048Offset -ge 0) { $afterV049.Substring(0, $v048Offset) } else { $afterV049 }
    Check 'R25_CHANGELOG_PRESERVES_V049_HISTORY' ($v049Start -ge 0 -and
        $v049History.Contains("-Version 'v0.4.9'") -and
        $v049History.Contains('unified interactive and direct PowerShell installer'))

    $releaseGate = Join-Path $PSScriptRoot 'github-release-notes.ps1'
    $gateGood = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody $releaseNotes 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_ACCEPTS_PINNED_HARNESS_COMMANDS' ($LASTEXITCODE -eq 0 -and $gateGood -match "RELEASE_NOTES_CONTRACT: $($script:CandidateRegex) PASS") ("exit=$LASTEXITCODE`n$gateGood")
    $gateDerived = (& pwsh -NoProfile -File $releaseGate -ReleaseBody $releaseNotes 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_DERIVES_CANDIDATE_VERSION' ($LASTEXITCODE -eq 0 -and
        $gateDerived -match "RELEASE_NOTES_CONTRACT: $($script:CandidateRegex) PASS")
    $gateBad = (& pwsh -NoProfile -File $releaseGate -Version $script:CandidateVersion -ReleaseBody ($releaseNotes -replace '(?s)## Verify installation.*', '') 2>&1 | Out-String)
    Check 'R26_RELEASE_GATE_REJECTS_MISSING_VERIFY' ($LASTEXITCODE -ne 0 -and $gateBad -match 'RELEASE_NOTES_VERIFY_MISSING')
    $gateMutableWrapperBody = $releaseNotes + [Environment]::NewLine + 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/project/codex.ps1 | iex'
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

    # The historical inventory owns maintenance.md; the current release retires its old routes.
    $stableManifest = Get-Content -LiteralPath (Join-Path $stableTarget '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    $stableMaintenancePath = Join-Path $stableTarget '.opencode/agents/maintenance.md'
    $stableMaintenancePresent = Test-Path -LiteralPath $stableMaintenancePath -PathType Leaf
    Check 'R22_STABLE_SOURCE_HAS_RETIRED_AGENT' ($stableMaintenancePresent)
    $stableMaintenanceEntries = @($stableManifest.managed_files | Where-Object path -eq '.opencode/agents/maintenance.md')
    Check 'R22_STABLE_HISTORICAL_INVENTORY' ($null -ne $stableManifest -and
        $stableManifest.schema_version -eq 1 -and $stableManifest.managed_files.Count -eq 12 -and
        $stableMaintenanceEntries.Count -eq 1 -and
        @($stableManifest.managed_files | Where-Object path -eq '.opencode/scripts/worktree-setup.ps1').Count -eq 0)
    $upgrade = Install $stableTarget $candidateArchive $script:CandidateVersion
    $upManifestPath = Join-Path $stableTarget '.opencode/orchestrator-install.json'
    $upManifestPresent = Test-Path -LiteralPath $upManifestPath -PathType Leaf
    $upManifestParseError = $null
    $upManifest = $null
    if ($upManifestPresent) {
        try { $upManifest = Get-Content -LiteralPath $upManifestPath -Raw | ConvertFrom-Json -Depth 100 -ErrorAction Stop }
        catch { $upManifestParseError = $_.Exception.Message }
    } else {
        $upManifestParseError = 'Updated manifest is missing.'
    }
    $upManagedFilesProperty = if ($null -ne $upManifest) { $upManifest.PSObject.Properties['managed_files'] } else { $null }
    $upSchemaProperty = if ($null -ne $upManifest) { $upManifest.PSObject.Properties['schema_version'] } else { $null }
    $upVersionProperty = if ($null -ne $upManifest) { $upManifest.PSObject.Properties['installed_version'] } else { $null }
    $upManifestHasManagedFiles = ($null -ne $upManagedFilesProperty -and $null -ne $upManagedFilesProperty.Value)
    $upManagedFiles = @(if ($upManifestHasManagedFiles) { $upManagedFilesProperty.Value })
    $upManifestSchema = if ($null -ne $upSchemaProperty) { $upSchemaProperty.Value } else { $null }
    $upManifestVersion = if ($null -ne $upVersionProperty) { [string]$upVersionProperty.Value } else { $null }
    $retiredOpenCodePaths = @(
        '.opencode/agents/maintenance.md',
        '.opencode/agents/aegis.md',
        '.opencode/commands/maintain.md'
    )
    $retiredPathsPresent = @($retiredOpenCodePaths | Where-Object {
        Test-Path -LiteralPath (Join-Path $stableTarget $_) -PathType Leaf
    })
    $retiredManifestEntries = @($upManagedFiles | Where-Object {
        $pathProperty = if ($null -ne $_) { $_.PSObject.Properties['path'] } else { $null }
        $null -ne $pathProperty -and $pathProperty.Value -in $retiredOpenCodePaths
    } | ForEach-Object { [string]$_.PSObject.Properties['path'].Value })
    $currentAgentDirectory = Join-Path $stableTarget '.opencode/agents'
    $currentAgentCount = if (Test-Path -LiteralPath $currentAgentDirectory -PathType Container) {
        @(Get-ChildItem -LiteralPath $currentAgentDirectory -Filter '*.md' -File).Count
    } else { 0 }
    $retiredFilesAbsent = $retiredPathsPresent.Count -eq 0
    $upgradePass = ($upgrade.Code -eq 0 -and $null -ne $upManifest -and $upManifestPresent -and
        $null -eq $upManifestParseError -and $upManifestSchema -eq 1 -and
        $upManifestHasManagedFiles -and $upManifestVersion -ceq $script:CandidateVersion -and
        $upManagedFiles.Count -eq 15 -and $currentAgentCount -eq 11 -and $retiredFilesAbsent -and
        $retiredManifestEntries.Count -eq 0)
    $upgradeEvidence = "exit=$($upgrade.Code); expected_version=$script:CandidateVersion; manifest_present=$upManifestPresent; schema=$upManifestSchema; installed_version=$upManifestVersion; managed_count=$($upManagedFiles.Count)/15; role_count=$currentAgentCount/11; retired_files_present=$($retiredPathsPresent -join ','); retired_manifest_entries=$($retiredManifestEntries -join ','); parse_error=$upManifestParseError`n$($upgrade.Text)"
    Check 'R22_OWNED_RETIRED_AGENT_MIGRATED' $upgradePass $upgradeEvidence
    $worktreeSetupPath = Join-Path $stableTarget '.opencode/scripts/worktree-setup.ps1'
    $worktreeSetupEntry = @($upManagedFiles | Where-Object {
        $pathProperty = if ($null -ne $_) { $_.PSObject.Properties['path'] } else { $null }
        $null -ne $pathProperty -and $pathProperty.Value -eq '.opencode/scripts/worktree-setup.ps1'
    })
    $worktreeSetupPresent = Test-Path -LiteralPath $worktreeSetupPath -PathType Leaf
    $worktreeHashProperty = if ($worktreeSetupEntry.Count -eq 1) { $worktreeSetupEntry[0].PSObject.Properties['sha256'] } else { $null }
    $worktreeSetupHashMatches = ($worktreeSetupPresent -and $worktreeSetupEntry.Count -eq 1 -and
        $null -ne $worktreeHashProperty -and
        $worktreeHashProperty.Value -eq (Get-FileHash -LiteralPath $worktreeSetupPath -Algorithm SHA256).Hash.ToLowerInvariant())
    $worktreeSetupPass = ($worktreeSetupPresent -and $upManagedFiles.Count -eq 15 -and
        $worktreeSetupEntry.Count -eq 1 -and $worktreeSetupHashMatches)
    Check 'R22_WORKTREE_SETUP_INSTALLED_AND_OWNED' $worktreeSetupPass `
        ("exit=$($upgrade.Code); helper_present=$worktreeSetupPresent; managed_count=$($upManagedFiles.Count); helper_entries=$($worktreeSetupEntry.Count); hash_matches=$worktreeSetupHashMatches`n$($upgrade.Text)")
    $upgradeAgain = Install $stableTarget $candidateArchive $script:CandidateVersion
    $upgradeAgainPass = ($upgradeAgain.Code -eq 0 -and $upgradeAgain.Text -match '(?m)^NO_CHANGES\s*$')
    Check 'R22_UPGRADE_REINSTALL_NO_CHANGES' $upgradeAgainPass `
        ("exit_code=$($upgradeAgain.Code); no_changes_output=$($upgradeAgain.Text -match '(?m)^NO_CHANGES\s*$')`n$($upgradeAgain.Text)")

    $alteredLegacyTarget = New-Target 'altered-historical-inventory'
    $alteredLegacyInstall = Install-Historical $stableHistoricalSource $alteredLegacyTarget 'v0.2.0'
    if ($alteredLegacyInstall.Code -ne 0) { throw 'Stable legacy fixture install failed before inventory test.' }
    $alteredManifestPath = Join-Path $alteredLegacyTarget '.opencode/orchestrator-install.json'
    $alteredManifest = Get-Content -LiteralPath $alteredManifestPath -Raw | ConvertFrom-Json
    $alteredManifest.managed_files = @($alteredManifest.managed_files | ForEach-Object {
        if ($_.path -eq 'opencode.jsonc') {
            [pscustomobject]@{ path='.opencode/scripts/worktree-setup.ps1'; sha256=$_.sha256 }
        } else { $_ }
    })
    [IO.File]::WriteAllText($alteredManifestPath, (($alteredManifest | ConvertTo-Json -Depth 100) + "`n"), $utf8)
    $alteredLegacySnapshot = Get-ProjectSnapshot $alteredLegacyTarget
    $alteredLegacyUpgrade = Install $alteredLegacyTarget $candidateArchive $script:CandidateVersion
    Check 'R22_ALTERED_HISTORICAL_INVENTORY_REJECTED_READ_ONLY' ($alteredLegacyUpgrade.Code -ne 0 -and
        $alteredLegacyUpgrade.Text -match 'INSTALL_MANIFEST_INCOMPATIBLE' -and
        (Get-ProjectSnapshot $alteredLegacyTarget) -ceq $alteredLegacySnapshot)

    $modifiedLegacyTarget = New-Target 'modified-retired-agent'
    $modifiedInstall = Install-Historical $stableHistoricalSource $modifiedLegacyTarget 'v0.2.0'
    if ($modifiedInstall.Code -ne 0) { throw 'Stable legacy fixture install failed before drift test.' }
    $retiredPath = Join-Path $modifiedLegacyTarget '.opencode/agents/maintenance.md'
    [IO.File]::AppendAllText($retiredPath, "`n# local modification`n", $utf8)
    $retiredHash = (Get-FileHash -LiteralPath $retiredPath -Algorithm SHA256).Hash
    $modifiedUpgrade = Install $modifiedLegacyTarget $candidateArchive $script:CandidateVersion
    Check 'R23_MODIFIED_RETIRED_FILE_CONFLICT_NONDESTRUCTIVE' ($modifiedUpgrade.Code -ne 0 -and
        $modifiedUpgrade.Text -match 'MANAGED_FILE_DRIFT' -and
        (Get-FileHash -LiteralPath $retiredPath -Algorithm SHA256).Hash -eq $retiredHash -and
        -not (Test-Path -LiteralPath (Join-Path $modifiedLegacyTarget '.opencode/agents/aegis.md')))

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
