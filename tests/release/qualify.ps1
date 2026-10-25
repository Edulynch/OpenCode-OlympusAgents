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

function New-GitTagArchive([string]$tag, [string]$archivePath) {
    $prefix = "OpenCode-OlympusAgents-$tag/"
    & git -C $source archive --format=zip "--prefix=$prefix" $tag -o $archivePath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
        throw "GIT_TAG_ARCHIVE_FAIL: $tag"
    }
    return $archivePath
}

function Install([string]$target, [string]$archive, [string]$version = '') {
    $args = @('-NoProfile', '-File', $installer, '-Target', $target, '-SourceArchive', $archive)
    if ($version) { $args += @('-Version', $version) }
    $output = (& pwsh @args 2>&1 | Out-String)
    [pscustomobject]@{ Text=$output; Code=$LASTEXITCODE }
}

function Verify([string]$target, [string]$archive, [string]$version) {
    $args = @('-NoProfile', '-File', $installer, '-Target', $target, '-SourceArchive', $archive,
        '-Version', $version, '-VerifyOnly')
    $output = (& pwsh @args 2>&1 | Out-String)
    [pscustomobject]@{ Text=$output; Code=$LASTEXITCODE }
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
    [IO.Directory]::CreateDirectory($run) | Out-Null
    Start-Transcript -LiteralPath $transcriptPath -Force | Out-Null
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
        Check 'R0_TARGET_IDENTITY_V0412' ($script:CandidateVersion -ceq 'v0.4.12')
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
    if (-not $ResumeAtPermissions) {
        $r1Pass = ($first.Code -eq 0 -and
            $first.Text -match "OLYMPUS_SOURCE: requested=$($script:CandidateRegex) resolved=$($script:CandidateRegex) origin=LOCAL_ARCHIVE" -and
            $first.Text -match "OLYMPUS_INSTALL: $($script:CandidateRegex) READY_OR_NO_CHANGES")
        if (-not $r1Pass) { Write-Output "R1_INSTALL_OUTPUT: $($first.Text)" }
        Check 'R1_CANDIDATE_RESOLVED_CANDIDATE' $r1Pass
        $paths = @('opencode.jsonc', '.opencode/orchestrator-install.json', '.opencode/commands/maintain.md',
            '.opencode/plugins/olympus-activity/activity.ts', '.opencode/plugins/olympus-activity/tui.tsx',
            '.opencode/scripts/worktree-setup.ps1')
        $paths += @('kael','veyra','orin','kovan','nox','vera','thales','atlas','argus','talos','helios','aegis' | ForEach-Object { ".opencode/agents/$_.md" })
        Check 'R2_CANDIDATE_ROSTER_FILES' (@($paths | Where-Object { -not (Test-Path -LiteralPath (Join-Path $target $_) -PathType Leaf) }).Count -eq 0 -and
            -not (Test-Path -LiteralPath (Join-Path $target '.opencode/agents/maintenance.md')))
        $manifestPath = Join-Path $target '.opencode/orchestrator-install.json'
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        Check 'R2_CANDIDATE_MANIFEST_VERSION_AND_OWNERSHIP' ($manifest.schema_version -eq 1 -and
            $manifest.installed_version -eq $script:CandidateVersion -and $manifest.managed_files.Count -eq 17 -and
            @($manifest.managed_files | Where-Object path -eq '.opencode/agents/aegis.md').Count -eq 1 -and
            @($manifest.managed_files | Where-Object path -eq '.opencode/agents/maintenance.md').Count -eq 0)

        $betaVerify = Verify $target $candidateArchive $script:CandidateVersion
        Check 'R24_CANDIDATE_INSTALL_VERIFY_PASS' ($betaVerify.Code -eq 0 -and $betaVerify.Text -match "(?m)^OLYMPUS_VERIFY: $($script:CandidateRegex) PASS\s*$")

        Push-Location $target
        try {
            $agents = (& opencode debug agents 2>&1 | Out-String) | ConvertFrom-Json -Depth 100
            Check 'R3_EFFECTIVE_AGENTS' ($LASTEXITCODE -eq 0 -and @($agents | Where-Object { $_.id -in @('kael','veyra','orin','kovan','nox','vera','thales','atlas','argus','talos','helios','aegis') }).Count -eq 12 -and @($agents | Where-Object { $_.id -in @('maintenance','sorin') }).Count -eq 0)
            $plugins = (& opencode plugin list 2>&1 | Out-String)
            Check 'R9_HUD_DISCOVERY' ($LASTEXITCODE -eq 0 -and $plugins -match 'olympus-activity')
        } finally { Pop-Location }
        $expected = @{
            kael=@('gpt-6.1-sol','high','primary'); thales=@('gpt-6.1-sol','xhigh','subagent'); atlas=@('gpt-6.1-sol','high','subagent'); argus=@('gpt-6.1-sol','high','subagent'); talos=@('gpt-6.1-sol','high','subagent'); helios=@('gpt-6.1-sol','high','subagent')
            veyra=@('gpt-6-luna','max','subagent'); orin=@('gpt-6-luna','max','subagent'); kovan=@('gpt-6-luna','max','subagent')
            nox=@('gpt-6-luna','max','subagent'); vera=@('gpt-6-luna','max','subagent'); aegis=@('gpt-6-luna','max','subagent')
        }
        foreach ($id in $expected.Keys) {
            $agent = @($agents | Where-Object id -eq $id)
            Check "R5_MODEL_$id" ($agent.Count -eq 1 -and $agent[0].model.id -eq $expected[$id][0] -and
                $agent[0].model.variant -eq $expected[$id][1] -and $agent[0].mode -eq $expected[$id][2])
        }
        $m = @($agents | Where-Object id -eq aegis)[0]
        Check 'R4_AEGIS_HIDDEN' ($m.mode -eq 'subagent' -and $m.hidden -eq $true)
        $maintainCommand = [IO.File]::ReadAllText((Join-Path $target '.opencode/commands/maintain.md'))
        Check 'R4_MAINTAIN_ROUTES_AEGIS' ($maintainCommand -match '(?m)^agent: aegis\s*$' -and $maintainCommand -match '(?m)^subagent: true\s*$')
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
    Check 'R4_KAEL_CANNOT_ROUTE_AEGIS' (@($kaelChildren | Where-Object { $_ -eq 'aegis' -or $_ -eq '*' }).Count -eq 0)
    function Perm($a, [string]$action, [string]$effect) {
        @($a.permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq $effect }).Count -gt 0
    }
    Check 'R10_TRUSTED_AUTONOMY' ((Perm $k shell allow) -and (Perm $k edit allow) -and (Perm $n shell allow) -and (Perm $n edit deny))
    $kaelText = [IO.File]::ReadAllText((Join-Path $target '.opencode/agents/kael.md'))
    Check 'R11_FAST_POLICY' ($kaelText -match 'MAX_ACTIVE_CHILDREN = 4' -and $kaelText -match 'minimum useful parallelism' -and
        $kaelText -match 'FAST' -and $kaelText -match 'balanced shards: 20 items / 4 workers = 5/5/5/5')

    # Stable SemVer remains installable explicitly; prerelease identifiers are accepted end-to-end.
    $stableTarget = New-Target 'explicit-stable-v020'
    $stable = Install $stableTarget $stableArchive 'v0.2.0'
    Check 'R13_EXPLICIT_STABLE_INSTALL' ($stable.Code -eq 0 -and
        $stable.Text -match 'OLYMPUS_SOURCE: requested=v0\.2\.0 resolved=v0\.2\.0 origin=LOCAL_ARCHIVE' -and
        $stable.Text -match 'OLYMPUS_INSTALL: v0\.2\.0 READY_OR_NO_CHANGES' -and
        (Get-Content -LiteralPath (Join-Path $stableTarget '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json).managed_files.Count -gt 0)
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
    $previousBetaTarget = New-Target 'previous-beta3-cannot-resolve-candidate'
    $previousBetaInstall = Install $previousBetaTarget $previousBetaArchive $script:CandidateVersion
    $previousBetaErrorPattern = [regex]::Escape(
        "Archive root 'OpenCode-OlympusAgents-v0.3.0-beta.3' does not identify"
    ) + "[\s|]*requested tag[\s|]*'" +
        [regex]::Escape($script:CandidateVersion) + "'\."

    Check 'R27_PREVIOUS_BETA3_CANNOT_SATISFY_CANDIDATE' (
        $previousBetaInstall.Code -ne 0 -and
        $previousBetaInstall.Text -match 'SOURCE_VERSION_MISMATCH' -and
        $previousBetaInstall.Text -match $previousBetaErrorPattern -and
        -not (Test-Path -LiteralPath (Join-Path $previousBetaTarget '.opencode/orchestrator-install.json')) -and
        (Get-Content -LiteralPath (Join-Path $previousBetaTarget 'user-notes.txt') -Raw) -eq "preserve me`n"
    )
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
    $missingFile = Join-Path $missingTarget '.opencode/agents/aegis.md'
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
    [IO.File]::WriteAllText((Join-Path $retiredAgentTarget '.opencode/agents/maintenance.md'), "id: maintenance`n", $utf8)
    $retiredVerify = Verify $retiredAgentTarget $candidateArchive $script:CandidateVersion
    Check 'R24_CANDIDATE_ROSTER_REJECTS_MAINTENANCE' ($retiredVerify.Code -ne 0 -and
        $retiredVerify.Text -match 'OLYMPUS_VERIFY_REASON: ROSTER_MISMATCH')

    $sourceMismatchVerify = Verify $legacyTarget $mismatchArchive $script:CandidateVersion
    Check 'R24_REQUESTED_SOURCE_VERSION_MISMATCH_FAIL' ($sourceMismatchVerify.Code -ne 0 -and
        $sourceMismatchVerify.Text -match 'OLYMPUS_VERIFY_REASON: SOURCE_VERSION_MISMATCH')

    # Public wrappers (12 variants) must use tag-pinned executable sources.
    function Test-PublicWrapperSource([string]$Content, [string]$Tag,
        [string]$Action, [string]$Scope, [string]$Harness) {
        $expectedLauncher = 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/' +
            $Tag + '/scripts/launch-latest.ps1'
        $urls = [regex]::Matches($Content,
            'https://raw\.githubusercontent\.com/Edulynch/OpenCode-OlympusAgents/[^\s]+?\.ps1')
        return ($urls.Count -eq 1 -and $urls[0].Value -ceq $expectedLauncher -and
            $Content.Contains("Invoke-WebRequest -Uri '$expectedLauncher' -OutFile " + '$launcher' + " -ErrorAction Stop") -and
            $Content.Contains("-Action '$Action' -Scope '$Scope' -Harness '$Harness' -Target (Get-Location).Path"))
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
            [regex]::IsMatch($Content, "(?m)^\s*'-Action',\s*'$([regex]::Escape($Action))',\s*$") -and
            $Content.Contains("'-Harness', `$selectedHarness,") -and
            $Content.Contains("'-Target', [IO.Path]::GetFullPath(`$target)"))
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
        -not (Test-UnifiedEntrypointSource ($installEntryText.Replace("'-Action', 'install',", "'-Action', 'uninstall',")) 'install') -and
        -not (Test-UnifiedEntrypointSource ($uninstallEntryText.Replace("'-Action', 'uninstall',", "'-Action', 'install',")) 'uninstall'))

    $sample = [IO.File]::ReadAllText((Join-Path $source 'install/project/codex.ps1'))
    $badMutable = $sample.Replace('/' + $script:CandidateVersion + '/scripts/launch-latest.ps1',
        '/master/scripts/launch-latest.ps1')
    $badWrongHarness = $sample.Replace("-Harness 'codex'", "-Harness 'all'")
    $badForeignSource = $sample.Replace('https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/',
        'https://example.invalid/')
    $badOldTag = $sample.Replace('/' + $script:CandidateVersion + '/scripts/launch-latest.ps1',
        '/v0.4.6/scripts/launch-latest.ps1')
    Check 'R25_PUBLIC_WRAPPER_MUTATIONS_REJECTED' (
        -not (Test-PublicWrapperSource $badMutable $script:CandidateVersion 'install' 'project' 'codex') -and
        -not (Test-PublicWrapperSource $badWrongHarness $script:CandidateVersion 'install' 'project' 'codex') -and
        -not (Test-PublicWrapperSource $badForeignSource $script:CandidateVersion 'install' 'project' 'codex') -and
        -not (Test-PublicWrapperSource $badOldTag $script:CandidateVersion 'install' 'project' 'codex'))

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
    $requiredHighlights = @('Dual Harness Installer','-Harness opencode','-Harness codex','-Harness all',
        'installed_harnesses','additive','legacy OpenCode installations','PowerShell 5.1','PowerShell 7','Olympus Harness Core',
        'VerifyOnly','user-owned','does not claim full parity')
    $missingHighlights = @($requiredHighlights | Where-Object { -not $releaseNotes.Contains($_) })
    Check 'R25_DUAL_HARNESS_RELEASE_HIGHLIGHTS' ($missingHighlights.Count -eq 0)
    Check 'R25_CAPABILITY_GAPS_NOT_OVERCLAIMED' ($releaseNotes -match 'DENY\s*=\s*GAP' -and
        $releaseNotes -match 'AEGIS\s*=\s*GAP' -and $releaseNotes -match 'ACTIVITY_VISIBILITY\s*=\s*PARTIAL/BASIC' -and
        $releaseNotes -match 'does not claim full parity' -and $releaseNotes -notmatch '(?i)Codex (?:has|provides|supports) (?:full parity|hard DENY|Aegis)')
    $mutableExecutableUrl = '(?i)(?:raw\.githubusercontent\.com/Edulynch/OpenCode-OlympusAgents/(?:master|main|refs/heads/(?:master|main))/[^\s]+?\.ps1|github\.com/Edulynch/OpenCode-OlympusAgents/(?:raw|blob)/(?:master|main)/[^\s]+?\.ps1)'
    Check 'R25_RELEASE_NO_MUTABLE_EXECUTABLE_SOURCE' ($releaseNotes -notmatch $mutableExecutableUrl -and
        $versionText -match 'archive/refs/tags/\$Version\.zip')

    $readme = [IO.File]::ReadAllText((Join-Path $source 'README.md'))
    $fastInstallUrl = "https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$($script:CandidateVersion)/install-olympus.ps1"
    $fastUninstallUrl = "https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$($script:CandidateVersion)/uninstall-olympus.ps1"
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
        $expectedPipeline = $expectedAst.EndBlock.Statements[0]
        if ($expectedPipeline -isnot [System.Management.Automation.Language.PipelineAst] -or
            $Statement.Background -or $expectedPipeline.Background -or
            $Statement.PipelineElements.Count -ne 2 -or $expectedPipeline.PipelineElements.Count -ne 2) { return $false }
        for ($index = 0; $index -lt 2; $index++) {
            $actualCommand = $Statement.PipelineElements[$index]
            $expectedCommandAst = $expectedPipeline.PipelineElements[$index]
            if ($actualCommand -isnot [System.Management.Automation.Language.CommandAst] -or
                $expectedCommandAst -isnot [System.Management.Automation.Language.CommandAst] -or
                $actualCommand.GetCommandName() -cne $expectedCommandAst.GetCommandName() -or
                $actualCommand.InvocationOperator -ne [System.Management.Automation.Language.TokenKind]::Unknown -or
                $actualCommand.Redirections.Count -ne 0 -or
                $actualCommand.CommandElements.Count -ne $expectedCommandAst.CommandElements.Count) { return $false }
            for ($element = 0; $element -lt $actualCommand.CommandElements.Count; $element++) {
                $actualValue = $actualCommand.CommandElements[$element]
                $expectedValue = $expectedCommandAst.CommandElements[$element]
                if ($actualValue -isnot [System.Management.Automation.Language.StringConstantExpressionAst] -or
                    $expectedValue -isnot [System.Management.Automation.Language.StringConstantExpressionAst] -or
                    $actualValue.Value -cne $expectedValue.Value) { return $false }
            }
        }
        return $true
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
        $uninstallCount = 0
        foreach ($statement in $remoteStatements) {
            if (Test-ReadmeExpectedBootstrapStatement $statement $InstallCommand) { $installCount++ }
            elseif (Test-ReadmeExpectedBootstrapStatement $statement $UninstallCommand) { $uninstallCount++ }
            else { return $false }
        }
        return ($installCount -eq 1 -and $uninstallCount -eq 1)
    }
    $fastInstallCommand = "irm $fastInstallUrl | iex"
    $fastUninstallCommand = "irm $fastUninstallUrl | iex"
    $readmeWithLf = $readme.Replace("`r`n", "`n")
    $readmeWithCrLf = $readmeWithLf.Replace("`n", "`r`n")
    Check 'R25_README_FAST_CONTRACT_ACCEPTS_LF_AND_CRLF' (
        (Test-ReadmeFastCommandContract $readmeWithLf $fastInstallCommand $fastUninstallCommand) -and
        (Test-ReadmeFastCommandContract $readmeWithCrLf $fastInstallCommand $fastUninstallCommand))
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
    $mutableBootstrapCommand = 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install-olympus.ps1 | iex'
    $readmeWithMutableBootstrap = $readme.Replace($fastInstallCommand, $mutableBootstrapCommand)
    if (-not $readmeWithMutableBootstrap.Contains($mutableBootstrapCommand)) {
        throw 'R25_NEGATIVE_CONTROL_SETUP_FAILED: mutable bootstrap command was not inserted.'
    }
    Check 'R25_README_REJECTS_MUTABLE_BOOTSTRAP_SOURCE' (
        -not (Test-ReadmeFastCommandContract $readmeWithMutableBootstrap $fastInstallCommand $fastUninstallCommand))
    $foreignBootstrapCommand = 'irm https://example.invalid/install-olympus.ps1 | iex'
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
        $installGuide.Contains($fastInstallUrl) -and $installGuide.Contains($fastUninstallUrl) -and
        $installGuide.Contains($script:CandidateVersion) -and
        $installGuide.Contains('ACTIVE DEVELOPMENT') -and
        $installGuide.Contains('FROZEN COMPATIBILITY') -and
        $installGuide.Contains('-Project -Here') -and $installGuide.Contains('-ProjectPath') -and
        $installGuide.Contains('-Global') -and $installGuide.Contains('opencode') -and
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
    $badVersion = (& pwsh -NoProfile -File $installer -Version 'v1.2.3-preview.1' -Target $badVersionTarget -SourceArchive $candidateArchive 2>&1 | Out-String)
    Check 'R17_MALFORMED_VERSION_REJECTED' ($LASTEXITCODE -ne 0 -and $badVersion -match 'v1\.2\.3-preview\.1' -and
        $badVersion -match 'no coincide|does not match|validation pattern' -and
        -not (Test-Path -LiteralPath (Join-Path $badVersionTarget '.opencode/orchestrator-install.json')))

    $mismatchTarget = New-Target 'candidate-resolves-v020-negative'
    $mismatch = Install $mismatchTarget $mismatchArchive $script:CandidateVersion
    Check 'R20_REQUESTED_CANDIDATE_RESOLVED_V020_FAILS' ($mismatch.Code -ne 0 -and
        $mismatch.Text.Contains("SOURCE_VERSION_MISMATCH: requested '$($script:CandidateVersion)' but resolved source reports 'v0.2.0'") -and
        -not (Test-Path -LiteralPath (Join-Path $mismatchTarget '.opencode/orchestrator-install.json')) -and
        (Get-Content -LiteralPath (Join-Path $mismatchTarget 'user-notes.txt') -Raw) -eq "preserve me`n")

    # Verified owned legacy maintenance.md is migrated; modified or unowned copies are never replaced.
    Check 'R22_STABLE_SOURCE_HAS_RETIRED_AGENT' (Test-Path -LiteralPath (Join-Path $stableTarget '.opencode/agents/maintenance.md'))
    $stableManifest = Get-Content -LiteralPath (Join-Path $stableTarget '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'R22_STABLE_HISTORICAL_INVENTORY' ($stableManifest.managed_files.Count -eq 12 -and
        @($stableManifest.managed_files | Where-Object path -eq '.opencode/scripts/worktree-setup.ps1').Count -eq 0)
    $upgrade = Install $stableTarget $candidateArchive $script:CandidateVersion
    $upManifest = Get-Content -LiteralPath (Join-Path $stableTarget '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'R22_OWNED_RETIRED_AGENT_MIGRATED' ($upgrade.Code -eq 0 -and
        -not (Test-Path -LiteralPath (Join-Path $stableTarget '.opencode/agents/maintenance.md')) -and
        (Test-Path -LiteralPath (Join-Path $stableTarget '.opencode/agents/aegis.md')) -and
        $upManifest.installed_version -eq $script:CandidateVersion -and
        @($upManifest.managed_files | Where-Object path -eq '.opencode/agents/maintenance.md').Count -eq 0)
    $worktreeSetupPath = Join-Path $stableTarget '.opencode/scripts/worktree-setup.ps1'
    $worktreeSetupEntry = @($upManifest.managed_files | Where-Object path -eq '.opencode/scripts/worktree-setup.ps1')
    Check 'R22_WORKTREE_SETUP_INSTALLED_AND_OWNED' ((Test-Path -LiteralPath $worktreeSetupPath -PathType Leaf) -and
        $upManifest.managed_files.Count -eq 17 -and $worktreeSetupEntry.Count -eq 1 -and
        $worktreeSetupEntry[0].sha256 -eq (Get-FileHash -LiteralPath $worktreeSetupPath -Algorithm SHA256).Hash.ToLowerInvariant())
    $upgradeAgain = Install $stableTarget $candidateArchive $script:CandidateVersion
    Check 'R22_UPGRADE_REINSTALL_NO_CHANGES' ($upgradeAgain.Code -eq 0 -and $upgradeAgain.Text -match '(?m)^NO_CHANGES\s*$')

    $alteredLegacyTarget = New-Target 'altered-historical-inventory'
    $alteredLegacyInstall = Install $alteredLegacyTarget $stableArchive 'v0.2.0'
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
    $modifiedInstall = Install $modifiedLegacyTarget $stableArchive 'v0.2.0'
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
    $unownedUpgrade = Install $unownedTarget $candidateArchive
    Check 'R23_UNOWNED_RETIRED_FILE_CONFLICT_NONDESTRUCTIVE' ($unownedUpgrade.Code -ne 0 -and
        $unownedUpgrade.Text -match 'INSTALL_CONFLICT' -and
        (Get-FileHash -LiteralPath $unownedPath -Algorithm SHA256).Hash -eq $unownedHash -and
        (Test-Path -LiteralPath (Join-Path $unownedTarget '.opencode/agents/aegis.md')))

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
