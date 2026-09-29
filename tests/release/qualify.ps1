[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('olympus-release-qualification-' + [guid]::NewGuid().ToString('N'))
$utf8 = [Text.UTF8Encoding]::new($false)
function Check([string]$id, [bool]$valid) {
    if (-not $valid) { throw "$id FAIL" }
    Write-Output "$id PASS"
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
    foreach ($item in Get-ChildItem -LiteralPath $sourceRoot -Force | Where-Object Name -ne '.git') {
        Copy-Item -LiteralPath $item.FullName -Destination $top -Recurse -Force
    }
    if ($MisreportStable) {
        $path = Join-Path $top 'install.ps1'
        $text = [IO.File]::ReadAllText($path)
        $text = $text.Replace("[string]`$Version = 'v0.3.0-beta.3'", "[string]`$Version = 'v0.2.0'")
        $text = $text.Replace("`$ReleaseVersion = 'v0.3.0-beta.3'", "`$ReleaseVersion = 'v0.2.0'")
        [IO.File]::WriteAllText($path, $text, $utf8)
    } elseif ($tag -in @('v0.3.0-alpha.1','v0.3.0-beta.2','v0.3.0-rc.1')) {
        $path = Join-Path $top 'install.ps1'
        $text = [IO.File]::ReadAllText($path)
        $text = $text.Replace("[string]`$Version = 'v0.3.0-beta.3'", "[string]`$Version = '$tag'")
        $text = $text.Replace("`$ReleaseVersion = 'v0.3.0-beta.3'", "`$ReleaseVersion = '$tag'")
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

try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $candidateArchive = New-SourceArchive $source 'v0.3.0-beta.3' (Join-Path $run 'candidate-beta3.zip')
    $stableArchive = New-GitTagArchive 'v0.2.0' (Join-Path $run 'stable-v020.zip')
    $alphaArchive = New-SourceArchive $source 'v0.3.0-alpha.1' (Join-Path $run 'alpha.zip')
    $betaArchive = New-SourceArchive $source 'v0.3.0-beta.2' (Join-Path $run 'beta.zip')
    $rcArchive = New-SourceArchive $source 'v0.3.0-rc.1' (Join-Path $run 'rc.zip')
    $mismatchArchive = New-SourceArchive $source 'v0.3.0-beta.3' (Join-Path $run 'mismatch-beta3-to-v020.zip') -MisreportStable

    $versionText = [IO.File]::ReadAllText($installer)
    Check 'R0_RELEASE_IDENTITY' ($versionText -match "(?m)^\s*\[string\]\`$Version\s*=\s*'v0\.3\.0-beta\.3'" -and
        $versionText -match "(?m)^\`$ReleaseVersion\s*=\s*'v0\.3\.0-beta\.3'")
    $patternMatch = [regex]::Match($versionText, "(?s)\[ValidatePattern\('([^']+)'\)\]\s*\[string\]\`$Version")
    $versionPattern = if ($patternMatch.Success) { $patternMatch.Groups[1].Value } else { '' }
    $acceptedSyntax = @('v1.2.3','v0.3.0-alpha.1','v0.3.0-beta.3','v2.4.0-rc.12' | Where-Object { $_ -match $versionPattern }).Count -eq 4
    Check 'R0_SEMVER_VALIDATOR' ($acceptedSyntax -and 'v1.2.3-preview.1' -notmatch $versionPattern)

    # The beta.3 request uses a local ZIP with the same GitHub tag-root layout.
    $target = New-Target 'fresh-beta3-default'
    $first = Install $target $candidateArchive
    Check 'R1_REQUESTED_BETA3_RESOLVED_BETA3' ($first.Code -eq 0 -and
        $first.Text -match 'OLYMPUS_SOURCE: requested=v0\.3\.0-beta\.3 resolved=v0\.3\.0-beta\.3 origin=LOCAL_ARCHIVE' -and
        $first.Text -match 'OLYMPUS_INSTALL: v0\.3\.0-beta\.3 READY_OR_NO_CHANGES')
    $paths = @('opencode.jsonc', '.opencode/orchestrator-install.json', '.opencode/commands/maintain.md',
        '.opencode/plugins/olympus-activity/activity.ts', '.opencode/plugins/olympus-activity/tui.tsx')
    $paths += @('kael','veyra','orin','kovan','nox','vera','thales','atlas','argus','talos','helios','aegis' | ForEach-Object { ".opencode/agents/$_.md" })
    Check 'R2_BETA3_ROSTER_FILES' (@($paths | Where-Object { -not (Test-Path -LiteralPath (Join-Path $target $_) -PathType Leaf) }).Count -eq 0 -and
        -not (Test-Path -LiteralPath (Join-Path $target '.opencode/agents/maintenance.md')))
    $manifestPath = Join-Path $target '.opencode/orchestrator-install.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    Check 'R2_BETA3_MANIFEST_VERSION_AND_OWNERSHIP' ($manifest.schema_version -eq 1 -and
        $manifest.installed_version -eq 'v0.3.0-beta.3' -and $manifest.managed_files.Count -eq 16 -and
        @($manifest.managed_files | Where-Object path -eq '.opencode/agents/aegis.md').Count -eq 1 -and
        @($manifest.managed_files | Where-Object path -eq '.opencode/agents/maintenance.md').Count -eq 0)

    Push-Location $target
    try {
        $agents = (& opencode debug agents 2>&1 | Out-String) | ConvertFrom-Json -Depth 100
        Check 'R3_EFFECTIVE_AGENTS' ($LASTEXITCODE -eq 0 -and @($agents | Where-Object { $_.id -in @('kael','veyra','orin','kovan','nox','vera','thales','atlas','argus','talos','helios','aegis') }).Count -eq 12 -and @($agents | Where-Object { $_.id -in @('maintenance','sorin') }).Count -eq 0)
        $plugins = (& opencode plugin list 2>&1 | Out-String)
        Check 'R9_HUD_DISCOVERY' ($LASTEXITCODE -eq 0 -and $plugins -match 'olympus-activity')
    } finally { Pop-Location }
    $expected = @{
        kael=@('gpt-6-sol','high','primary'); thales=@('gpt-6-sol','xhigh','subagent'); atlas=@('gpt-6-sol','high','subagent'); argus=@('gpt-6-sol','high','subagent'); talos=@('gpt-6-sol','high','subagent'); helios=@('gpt-6-sol','high','subagent')
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
    foreach ($entry in @(@('alpha','v0.3.0-alpha.1',$alphaArchive), @('beta','v0.3.0-beta.2',$betaArchive), @('rc','v0.3.0-rc.1',$rcArchive))) {
        $semverTarget = New-Target ('semver-' + $entry[0])
        $result = Install $semverTarget $entry[2] $entry[1]
        $semverManifestPath = Join-Path $semverTarget '.opencode/orchestrator-install.json'
        $semverManifest = if (Test-Path -LiteralPath $semverManifestPath) { Get-Content -LiteralPath $semverManifestPath -Raw | ConvertFrom-Json } else { $null }
        Check ('R14_' + $entry[0].ToUpperInvariant() + '_ACCEPTED') ($result.Code -eq 0 -and
            $result.Text -match ('OLYMPUS_SOURCE: requested=' + [regex]::Escape($entry[1]) + ' resolved=' + [regex]::Escape($entry[1])) -and
            $null -ne $semverManifest -and $semverManifest.installed_version -eq $entry[1])
    }

    $badVersionTarget = New-Target 'bad-version'
    $badVersion = (& pwsh -NoProfile -File $installer -Version 'v1.2.3-preview.1' -Target $badVersionTarget -SourceArchive $candidateArchive 2>&1 | Out-String)
    Check 'R17_MALFORMED_VERSION_REJECTED' ($LASTEXITCODE -ne 0 -and $badVersion -match 'v1\.2\.3-preview\.1' -and
        $badVersion -match 'no coincide|does not match|validation pattern' -and
        -not (Test-Path -LiteralPath (Join-Path $badVersionTarget '.opencode/orchestrator-install.json')))

    $mismatchTarget = New-Target 'beta3-resolves-v020-negative'
    $mismatch = Install $mismatchTarget $mismatchArchive 'v0.3.0-beta.3'
    Check 'R20_REQUESTED_BETA3_RESOLVED_V020_FAILS' ($mismatch.Code -ne 0 -and
        $mismatch.Text -match "SOURCE_VERSION_MISMATCH: requested 'v0\.3\.0-beta\.3' but resolved source reports 'v0\.2\.0'" -and
        -not (Test-Path -LiteralPath (Join-Path $mismatchTarget '.opencode/orchestrator-install.json')) -and
        (Get-Content -LiteralPath (Join-Path $mismatchTarget 'user-notes.txt') -Raw) -eq "preserve me`n")

    # Verified owned legacy maintenance.md is migrated; modified or unowned copies are never replaced.
    Check 'R22_STABLE_SOURCE_HAS_RETIRED_AGENT' (Test-Path -LiteralPath (Join-Path $stableTarget '.opencode/agents/maintenance.md'))
    $upgrade = Install $stableTarget $candidateArchive 'v0.3.0-beta.3'
    $upManifest = Get-Content -LiteralPath (Join-Path $stableTarget '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'R22_OWNED_RETIRED_AGENT_MIGRATED' ($upgrade.Code -eq 0 -and
        -not (Test-Path -LiteralPath (Join-Path $stableTarget '.opencode/agents/maintenance.md')) -and
        (Test-Path -LiteralPath (Join-Path $stableTarget '.opencode/agents/aegis.md')) -and
        $upManifest.installed_version -eq 'v0.3.0-beta.3' -and
        @($upManifest.managed_files | Where-Object path -eq '.opencode/agents/maintenance.md').Count -eq 0)

    $modifiedLegacyTarget = New-Target 'modified-retired-agent'
    $modifiedInstall = Install $modifiedLegacyTarget $stableArchive 'v0.2.0'
    if ($modifiedInstall.Code -ne 0) { throw 'Stable legacy fixture install failed before drift test.' }
    $retiredPath = Join-Path $modifiedLegacyTarget '.opencode/agents/maintenance.md'
    [IO.File]::AppendAllText($retiredPath, "`n# local modification`n", $utf8)
    $retiredHash = (Get-FileHash -LiteralPath $retiredPath -Algorithm SHA256).Hash
    $modifiedUpgrade = Install $modifiedLegacyTarget $candidateArchive 'v0.3.0-beta.3'
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
    Write-Output 'RELEASE QUALIFICATION: PASS (local tag-shaped source archives; no tag, push, or release created)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'RELEASE QUALIFICATION: FAIL'
    exit 1
} finally {
    if ($run -and (Test-Path -LiteralPath $run)) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop; break }
            catch {
                if ($attempt -eq 10) {
                    Write-Output 'CLEANUP_DEFERRED: OpenCode/Windows still holds the disposable fixture; remove after handles close.'
                    break
                }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}
