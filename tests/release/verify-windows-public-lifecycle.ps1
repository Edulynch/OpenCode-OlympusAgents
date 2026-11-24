[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repository = 'Edulynch/OpenCode-OlympusAgents'
$Version = 'v0.12.8'
$ExpectedReleaseId = 456634162
$ExpectedTagObject = '17d72b0f6c4b9ad013f9050b581c5d93eaa9e6f1'
$ExpectedCommit = '7e1dfdf1a767929b76c6c8f1db1f8ab898bdb15c'
$ExpectedInstallerSize = 6199
$ExpectedInstallerSha256 = '4c85b0caaa116827a683f30ae574173ab8791f74294281d6e5dbbf2f6b811a2d'
$ExpectedInstallBlob = 'c389063908e3f4cb2086f04c324395d8ca5b081c'
$ApiRoot = "https://api.github.com/repos/$Repository"
$LatestInstallerUrl = "https://github.com/$Repository/releases/latest/download/install-olympus.ps1"
$Headers = @{
    Accept = 'application/vnd.github+json'
    'User-Agent' = 'OlympusAgents-Public-Windows-Lifecycle'
    'X-GitHub-Api-Version' = '2022-11-28'
}
$RawHeaders = @{ 'User-Agent' = 'OlympusAgents-Public-Windows-Lifecycle' }

function Block-UnsafeHost([string]$Reason) {
    Write-Output "PUBLIC_WINDOWS_LIFECYCLE_GUARD: BLOCKED reason=$Reason"
    exit 2
}

if ($env:GITHUB_ACTIONS -cne 'true' -or
    $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or
    $env:RUNNER_OS -cne 'Windows' -or
    [Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or
    $env:GITHUB_REPOSITORY -cne $Repository -or
    $env:GITHUB_EVENT_NAME -cne 'pull_request' -or
    $env:GITHUB_BASE_REF -cne 'develop' -or
    -not $env:GITHUB_EVENT_PATH -or
    -not (Test-Path -LiteralPath $env:GITHUB_EVENT_PATH -PathType Leaf)) {
    Block-UnsafeHost 'requires the canonical same-repository pull_request on a GitHub-hosted Windows runner'
}
try {
    $event = Get-Content -LiteralPath $env:GITHUB_EVENT_PATH -Raw |
        ConvertFrom-Json -Depth 50 -ErrorAction Stop
} catch {
    Block-UnsafeHost 'pull_request event metadata is unavailable'
}
if ($event.repository.full_name -cne $Repository -or
    $event.pull_request.base.repo.full_name -cne $Repository -or
    $event.pull_request.head.repo.full_name -cne $Repository -or
    $event.pull_request.base.ref -cne 'develop') {
    Block-UnsafeHost 'event is not an official same-repository PR to develop'
}
Write-Output 'PUBLIC_WINDOWS_LIFECYCLE_GUARD: PASS (GitHub-hosted Windows; the User PATH registry is disposable)'

function Get-GitHubJson([string]$Uri) {
    return Invoke-RestMethod -Method Get -Uri $Uri -Headers $Headers -ErrorAction Stop
}

function Assert-ExpectedRelease($Release) {
    if ([long]$Release.id -ne $ExpectedReleaseId -or
        $Release.tag_name -cne $Version -or
        $Release.immutable -isnot [bool] -or -not $Release.immutable -or
        $Release.draft -isnot [bool] -or $Release.draft -or
        $Release.prerelease -isnot [bool] -or $Release.prerelease -or
        [string]::IsNullOrWhiteSpace([string]$Release.published_at)) {
        throw 'PUBLIC_RELEASE_IDENTITY_MISMATCH: latest must be the reviewed immutable v0.12.8 release.'
    }
    $assets = @($Release.assets | Where-Object { $_.name -ceq 'install-olympus.ps1' })
    if ($assets.Count -ne 1 -or
        [long]$assets[0].size -ne $ExpectedInstallerSize -or
        $assets[0].digest -cne "sha256:$ExpectedInstallerSha256" -or
        $assets[0].browser_download_url -cne "https://github.com/$Repository/releases/download/$Version/install-olympus.ps1") {
        throw 'PUBLIC_INSTALL_ASSET_METADATA_MISMATCH: latest Windows asset metadata differs from the reviewed size or digest.'
    }
    return $assets[0]
}

function Get-CanonicalFileMetadata([string]$Path) {
    $file = Get-GitHubJson "$ApiRoot/contents/$Path`?ref=$ExpectedCommit"
    if ($file.type -cne 'file' -or $file.path -cne $Path -or
        $file.sha -notmatch '^[0-9a-f]{40}$' -or [long]$file.size -le 0) {
        throw "TAGGED_FILE_METADATA_INVALID: $Path is not a canonical file at the expected commit."
    }
    return $file
}

function Get-GitBlobSha1([byte[]]$Bytes) {
    $header = [Text.Encoding]::ASCII.GetBytes("blob $($Bytes.Length)`0")
    $gitObject = [byte[]]::new($header.Length + $Bytes.Length)
    [Array]::Copy($header, 0, $gitObject, 0, $header.Length)
    [Array]::Copy($Bytes, 0, $gitObject, $header.Length, $Bytes.Length)
    $sha = [Security.Cryptography.SHA1]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($gitObject))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Download-VerifiedTaggedFile([string]$Path, $Metadata, [string]$Destination) {
    $uri = "https://raw.githubusercontent.com/$Repository/$Version/$Path"
    Invoke-WebRequest -Uri $uri -OutFile $Destination -Headers $RawHeaders -ErrorAction Stop
    $bytes = [IO.File]::ReadAllBytes($Destination)
    $actualBlob = Get-GitBlobSha1 $bytes
    if ($bytes.Length -ne [long]$Metadata.size -or $actualBlob -cne $Metadata.sha) {
        throw "TAGGED_FILE_BLOB_MISMATCH: downloaded $Path does not match GitHub's canonical blob."
    }
    return $actualBlob
}

function Assert-TaggedInstallerIdentity([string]$Path) {
    $text = [IO.File]::ReadAllText($Path)
    $default = [regex]::Match($text, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''\s*,?\s*$')
    $marker = [regex]::Match($text, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''\s*(?:#.*)?$')
    if (-not $default.Success -or -not $marker.Success -or
        $default.Groups[1].Value -cne $Version -or $marker.Groups[1].Value -cne $Version) {
        throw 'TAGGED_INSTALLER_IDENTITY_MISMATCH: verified source does not declare v0.12.8.'
    }
}

function Get-PathEntries([AllowNull()][string]$Value) {
    if ([string]::IsNullOrEmpty($Value)) { return @() }
    $entries = @($Value.Split(';'))
    if (@($entries | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) {
        throw 'USER_PATH_BASELINE_UNSAFE: empty PATH entries cannot be proven preserved.'
    }
    return $entries
}

function Normalize-PathEntry([string]$Value) {
    try { return [IO.Path]::GetFullPath($Value).TrimEnd([char[]]@('\','/')) }
    catch { return $Value.TrimEnd([char[]]@('\','/')) }
}

function Test-SequenceEqual([string[]]$Actual, [string[]]$Expected) {
    if ($Actual.Count -ne $Expected.Count) { return $false }
    for ($index = 0; $index -lt $Actual.Count; $index++) {
        if ($Actual[$index] -cne $Expected[$index]) { return $false }
    }
    return $true
}

function Assert-PathAdded([string[]]$Before, [string]$AfterValue, [string]$ManagedBin) {
    $after = @(Get-PathEntries $AfterValue)
    $managed = @($after | Where-Object {
        [string]::Equals((Normalize-PathEntry $_), (Normalize-PathEntry $ManagedBin),
            [StringComparison]::OrdinalIgnoreCase)
    })
    $other = @($after | Where-Object {
        -not [string]::Equals((Normalize-PathEntry $_), (Normalize-PathEntry $ManagedBin),
            [StringComparison]::OrdinalIgnoreCase)
    })
    if ($managed.Count -ne 1 -or -not (Test-SequenceEqual $other $Before)) {
        throw 'USER_PATH_INSTALL_MISMATCH: installation must add exactly its managed bin while preserving other entries.'
    }
}

function Assert-PathRestored([string[]]$Before, [string]$AfterValue, [string]$ManagedBin) {
    $after = @(Get-PathEntries $AfterValue)
    if (@($after | Where-Object {
            [string]::Equals((Normalize-PathEntry $_), (Normalize-PathEntry $ManagedBin),
                [StringComparison]::OrdinalIgnoreCase)
        }).Count -ne 0 -or -not (Test-SequenceEqual $after $Before)) {
        throw 'USER_PATH_UNINSTALL_MISMATCH: uninstall did not remove only the managed entry and preserve all other entries.'
    }
}

function Get-TreeSnapshot([string]$Root) {
    $records = [Collections.Generic.List[string]]::new()
    $base = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\','/'))
    foreach ($item in @(Get-ChildItem -LiteralPath $base -Recurse -Force -ErrorAction Stop |
            Sort-Object FullName)) {
        $relative = $item.FullName.Substring($base.Length + 1).Replace('\','/')
        if ($item.PSIsContainer) {
            $records.Add("D:$relative")
        } else {
            $digest = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            $records.Add('F:{0}:{1}' -f $relative, $digest)
        }
    }
    return ($records.ToArray() -join "`n")
}

function Read-And-CheckManifest([string]$ManifestPath, [string]$ConfigRoot) {
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw 'PUBLIC_INSTALL_MANIFEST_MISSING: install did not create the global ownership manifest.'
    }
    try {
        $manifest = [IO.File]::ReadAllText($ManifestPath) | ConvertFrom-Json -Depth 40 -ErrorAction Stop
    } catch {
        throw 'PUBLIC_INSTALL_MANIFEST_INVALID: global manifest is not valid JSON.'
    }
    if ($manifest.schema_version -ne 1 -or $manifest.scope -cne 'global' -or
        $manifest.installed_version -cne $Version -or
        @($manifest.installed_harnesses).Count -ne 1 -or
        [string]$manifest.installed_harnesses[0] -cne 'opencode') {
        throw 'PUBLIC_INSTALL_MANIFEST_IDENTITY_MISMATCH: expected global OpenCode v0.12.8.'
    }
    $installedCommit = [string]$manifest.installed_from_commit
    if ($installedCommit -cne $ExpectedCommit -and $installedCommit -cne 'unknown') {
        throw 'PUBLIC_INSTALL_MANIFEST_COMMIT_MISMATCH: value must be the independently verified commit or the documented archive value unknown.'
    }
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $paths = [Collections.Generic.List[string]]::new()
    $root = [IO.Path]::GetFullPath($ConfigRoot).TrimEnd([char[]]@('\','/'))
    $prefix = $root + [IO.Path]::DirectorySeparatorChar
    foreach ($entry in @($manifest.managed_files)) {
        $relative = ([string]$entry.path).Replace('\','/')
        if ([string]::IsNullOrWhiteSpace($relative) -or [IO.Path]::IsPathRooted($relative) -or
            $relative -match '(^|/)\.\.?(/|$)' -or $relative.Contains(':') -or
            -not $seen.Add($relative)) {
            throw 'PUBLIC_INSTALL_MANIFEST_PATH_INVALID: refusing an unsafe or duplicate managed path.'
        }
        $full = [IO.Path]::GetFullPath((Join-Path $root ($relative.Replace('/', [IO.Path]::DirectorySeparatorChar))))
        if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $full -PathType Leaf)) {
            throw 'PUBLIC_INSTALL_MANIFEST_FILE_MISSING: a declared managed file is missing or escapes the fixture root.'
        }
        $paths.Add($full)
    }
    if ($paths.Count -eq 0 -or $seen.Contains('opencode.jsonc')) {
        throw 'PUBLIC_INSTALL_MANIFEST_INVENTORY_INVALID: expected managed resources and a user-owned OpenCode config.'
    }
    return [pscustomobject]@{ Manifest=$manifest; Commit=$installedCommit; ManagedPaths=$paths.ToArray() }
}

function Invoke-ChildPwsh([string]$Path, [string[]]$Arguments, [string]$Label) {
    $lines = @(& $script:PwshPath -NoProfile -NonInteractive -File $Path @Arguments 2>&1 |
        ForEach-Object { [string]$_ })
    $code = $LASTEXITCODE
    foreach ($line in @($lines | Where-Object {
            $_ -match '^(OLYMPUS_(?:SOURCE|RELEASE_SELECTED|ENTRYPOINT|RELEASE_EXECUTING|RELEASE_EXECUTED|GLOBAL_VERIFY|CLI|CLI_PATH|RUNTIME_VALIDATION_WARNING)|PUBLIC_)'
        })) {
        Write-Output $line
    }
    if ($code -ne 0) {
        $diagnostic = @($lines | Where-Object { $_ -match 'OLYMPUS_|FAILED|ERROR' } | Select-Object -First 2) -join '; '
        throw "$Label failed with exit code $code. $diagnostic"
    }
    return [pscustomobject]@{ ExitCode=$code; Lines=$lines }
}

$runRoot = $null
$installAttempted = $false
$uninstallAttempted = $false
$uninstallSucceeded = $false
$environmentCaptured = $false
$failure = $null
$cleanupFailure = $null
$originalEnvironment = @{}
$environmentNames = @(
    'PATH','TEMP','TMP','TMPDIR','USERPROFILE','HOME','APPDATA','LOCALAPPDATA',
    'OPENCODE_CONFIG_DIR','OPENCODE_DATA_DIR','OPENCODE_CACHE_DIR','OPENCODE_STATE_DIR',
    'OLYMPUS_CONFIG_HOME','OLYMPUS_CONFIG_FILE','OLYMPUS_CLI_ROOT','OLYMPUS_CLI_PATH_STORE',
    'OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT','OLYMPUS_VERIFYONLY_PROBE',
    'OLYMPUS_VERIFYONLY_CALL_LOG','CODEX_HOME',
    'XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_STATE_HOME',
    'PYTHONDONTWRITEBYTECODE'
)

try {
    $script:PwshPath = (Get-Command pwsh.exe -CommandType Application -ErrorAction Stop).Source
    $latest = Get-GitHubJson "$ApiRoot/releases/latest"
    $latestAsset = Assert-ExpectedRelease $latest
    $byId = Get-GitHubJson "$ApiRoot/releases/$ExpectedReleaseId"
    $pinnedAsset = Assert-ExpectedRelease $byId
    if ($latest.id -ne $byId.id -or $latest.tag_name -cne $byId.tag_name -or
        $latestAsset.digest -cne $pinnedAsset.digest) {
        throw 'PUBLIC_LATEST_RELEASE_CHANGED: /latest and the reviewed immutable release ID disagree.'
    }

    $tagRef = Get-GitHubJson "$ApiRoot/git/ref/tags/$Version"
    if ($tagRef.object.type -cne 'tag' -or $tagRef.object.sha -cne $ExpectedTagObject) {
        throw 'PUBLIC_TAG_NOT_EXPECTED_ANNOTATED_OBJECT: v0.12.8 did not resolve to the reviewed tag object.'
    }
    $tag = Get-GitHubJson "$ApiRoot/git/tags/$ExpectedTagObject"
    if ($tag.tag -cne $Version -or $tag.object.type -cne 'commit' -or
        $tag.object.sha -cne $ExpectedCommit) {
        throw 'PUBLIC_TAG_PEEL_MISMATCH: annotated v0.12.8 tag did not peel to the reviewed commit.'
    }

    $installMetadata = Get-CanonicalFileMetadata 'install.ps1'
    $uninstallMetadata = Get-CanonicalFileMetadata 'uninstall-olympus.ps1'
    if ($installMetadata.sha -cne $ExpectedInstallBlob) {
        throw 'TAGGED_INSTALLER_BLOB_MISMATCH: canonical v0.12.8 install.ps1 blob differs from the reviewed object.'
    }

    if (-not $env:RUNNER_TEMP -or -not [IO.Path]::IsPathFullyQualified($env:RUNNER_TEMP)) {
        throw 'RUNNER_TEMP_INVALID: no absolute GitHub-hosted runner temp is available.'
    }
    $runnerTemp = [IO.Path]::GetFullPath($env:RUNNER_TEMP)
    $volume = [IO.Path]::GetPathRoot($runnerTemp)
    if ($runnerTemp.TrimEnd([char[]]@('\','/')) -ceq $volume.TrimEnd([char[]]@('\','/'))) {
        throw 'RUNNER_TEMP_INVALID: filesystem root is not a fixture location.'
    }
    $approvedTemp = Join-Path $runnerTemp 'opencode'
    [IO.Directory]::CreateDirectory($approvedTemp) | Out-Null
    $runRoot = Join-Path $approvedTemp ('public-windows-lifecycle-' + [guid]::NewGuid().ToString('N'))
    if (Test-Path -LiteralPath $runRoot) { throw 'FIXTURE_PATH_COLLISION: refusing an existing fixture root.' }
    [IO.Directory]::CreateDirectory($runRoot) | Out-Null

    $latestInstallerPath = Join-Path $runRoot 'public-latest-install-olympus.ps1'
    Invoke-WebRequest -Uri $LatestInstallerUrl -OutFile $latestInstallerPath `
        -Headers $RawHeaders -ErrorAction Stop
    $assetBytes = [IO.File]::ReadAllBytes($latestInstallerPath)
    $assetSha = (Get-FileHash -LiteralPath $latestInstallerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($assetBytes.Length -ne $ExpectedInstallerSize -or $assetSha -cne $ExpectedInstallerSha256) {
        throw 'PUBLIC_INSTALL_ASSET_MISMATCH: downloaded latest asset differs from the reviewed byte length or SHA-256.'
    }

    $taggedInstallerPath = Join-Path $runRoot 'tagged-install.ps1'
    $taggedUninstallerPath = Join-Path $runRoot 'tagged-uninstall-olympus.ps1'
    $installBlob = Download-VerifiedTaggedFile 'install.ps1' $installMetadata $taggedInstallerPath
    $uninstallBlob = Download-VerifiedTaggedFile 'uninstall-olympus.ps1' $uninstallMetadata $taggedUninstallerPath
    Assert-TaggedInstallerIdentity $taggedInstallerPath
    Write-Output "PUBLIC_RELEASE_PROVENANCE: PASS id=$ExpectedReleaseId version=$Version tag_object=$ExpectedTagObject commit=$ExpectedCommit"
    Write-Output "PUBLIC_INSTALL_ASSET: PASS size=$($assetBytes.Length) sha256=$assetSha"
    Write-Output "PUBLIC_TAGGED_SOURCES: PASS install.ps1_blob=$installBlob uninstall_blob=$uninstallBlob"

    $fixtureRoot = Join-Path $runRoot 'fixture'
    $configRoot = Join-Path $fixtureRoot 'opencode-config'
    $profileRoot = Join-Path $fixtureRoot 'profile'
    $localAppData = Join-Path $fixtureRoot 'localappdata'
    $mockBin = Join-Path $fixtureRoot 'mock-bin'
    $workRoot = Join-Path $fixtureRoot 'work'
    $processTemp = Join-Path $fixtureRoot 'temp'
    foreach ($directory in @(
        $configRoot, $profileRoot, $localAppData, $mockBin, $workRoot, $processTemp,
        (Join-Path $fixtureRoot 'appdata'), (Join-Path $fixtureRoot 'xdg-config'),
        (Join-Path $fixtureRoot 'xdg-data'), (Join-Path $fixtureRoot 'xdg-cache'),
        (Join-Path $fixtureRoot 'xdg-state'), (Join-Path $fixtureRoot 'codex'),
        (Join-Path $fixtureRoot 'olympus')
    )) {
        [IO.Directory]::CreateDirectory($directory) | Out-Null
    }

    $fixtureStub = Join-Path $PSScriptRoot 'fixtures/opencode.ps1'
    if (-not (Test-Path -LiteralPath $fixtureStub -PathType Leaf)) {
        throw 'OPENCODE_FIXTURE_MISSING: deterministic release fixture is unavailable.'
    }
    Copy-Item -LiteralPath $fixtureStub -Destination (Join-Path $mockBin 'opencode.ps1')
    $shim = "@echo off`r`npwsh -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), $shim, [Text.Encoding]::ASCII)

    $userConfigPath = Join-Path $configRoot 'opencode.jsonc'
    $userConfigText = @'
{
  "default_agent": "lifecycle-sentinel",
  "permissions": [
    {"action": "external_directory", "resource": "*", "effect": "ask"}
  ],
  "user_marker": "preserve-me"
}
'@
    [IO.File]::WriteAllText($userConfigPath, $userConfigText, [Text.UTF8Encoding]::new($false))
    $originalConfigBytes = [Convert]::ToBase64String([IO.File]::ReadAllBytes($userConfigPath))
    $sentinelPath = Join-Path $profileRoot 'preserve-bytes.bin'
    $sentinelBytes = [byte[]]@(0,1,2,127,128,255)
    [IO.File]::WriteAllBytes($sentinelPath, $sentinelBytes)
    $originalSentinel = [Convert]::ToBase64String([IO.File]::ReadAllBytes($sentinelPath))

    foreach ($name in $environmentNames) {
        $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }
    $environmentCaptured = $true
    $processEnvironment = @{
        TEMP=$processTemp; TMP=$processTemp; TMPDIR=$processTemp
        USERPROFILE=$profileRoot; HOME=$profileRoot
        APPDATA=(Join-Path $fixtureRoot 'appdata'); LOCALAPPDATA=$localAppData
        OPENCODE_CONFIG_DIR=$configRoot
        OPENCODE_DATA_DIR=(Join-Path $fixtureRoot 'opencode-data')
        OPENCODE_CACHE_DIR=(Join-Path $fixtureRoot 'opencode-cache')
        OPENCODE_STATE_DIR=(Join-Path $fixtureRoot 'opencode-state')
        OLYMPUS_CONFIG_HOME=(Join-Path $fixtureRoot 'olympus')
        OLYMPUS_CONFIG_FILE=(Join-Path $fixtureRoot 'olympus/config.json')
        OLYMPUS_CLI_ROOT=(Join-Path $fixtureRoot 'cli')
        OLYMPUS_CLI_PATH_STORE=$null
        OLYMPUS_GLOBAL_FIXTURE_OPENCODE_ROOT=$configRoot
        OLYMPUS_VERIFYONLY_PROBE=$null
        OLYMPUS_VERIFYONLY_CALL_LOG=$null
        CODEX_HOME=(Join-Path $fixtureRoot 'codex')
        XDG_CONFIG_HOME=(Join-Path $fixtureRoot 'xdg-config')
        XDG_DATA_HOME=(Join-Path $fixtureRoot 'xdg-data')
        XDG_CACHE_HOME=(Join-Path $fixtureRoot 'xdg-cache')
        XDG_STATE_HOME=(Join-Path $fixtureRoot 'xdg-state')
        PYTHONDONTWRITEBYTECODE='1'
    }
    foreach ($name in $processEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, [string]$processEnvironment[$name], 'Process')
    }
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $originalEnvironment['PATH']
    $resolvedOpenCode = (Get-Command opencode -CommandType Application -ErrorAction Stop |
        Select-Object -First 1).Source
    if (-not [string]::Equals([IO.Path]::GetFullPath($resolvedOpenCode),
            [IO.Path]::GetFullPath((Join-Path $mockBin 'opencode.cmd')),
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'LIVE_OPENCODE_REFUSED: the deterministic fixture is not first on process PATH.'
    }

    $cliRoot = Join-Path $localAppData 'Programs/Olympus'
    $cliBin = Join-Path $cliRoot 'bin'
    $originalUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $originalMachinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $originalUserPathEntries = @(Get-PathEntries $originalUserPath)
    if (@($originalUserPathEntries | Where-Object {
            [string]::Equals((Normalize-PathEntry $_), (Normalize-PathEntry $cliBin),
                [StringComparison]::OrdinalIgnoreCase)
        }).Count -gt 0) {
        throw 'USER_PATH_BASELINE_CONFLICT: disposable runner already contains the fixture CLI path.'
    }

    $globalManifestPath = Join-Path $configRoot 'olympus/orchestrator-install.json'
    $installAttempted = $true
    Push-Location $workRoot
    try {
        $installResult = Invoke-ChildPwsh $latestInstallerPath @() 'Public latest install'
        if (@($installResult.Lines | Where-Object {
                $_ -match "(?m)^OLYMPUS_ENTRYPOINT: action=install scope=global harness=opencode release=$([regex]::Escape($Version))$"
            }).Count -ne 1) {
            throw 'PUBLIC_INSTALL_ROUTE_MISMATCH: latest asset did not execute the expected global OpenCode route.'
        }
    } finally {
        Pop-Location
    }

    $installed = Read-And-CheckManifest $globalManifestPath $configRoot
    $installedConfig = [IO.File]::ReadAllText($userConfigPath) | ConvertFrom-Json -Depth 20
    if ($installedConfig.default_agent -cne 'kael' -or
        $installedConfig.user_marker -cne 'preserve-me' -or
        @($installed.Manifest.managed_files | Where-Object { $_.path -ceq 'opencode.jsonc' }).Count -ne 0) {
        throw 'PUBLIC_INSTALL_USER_CONFIG_MISMATCH: install did not preserve ownership of the sentinel config.'
    }
    Assert-PathAdded $originalUserPathEntries ([Environment]::GetEnvironmentVariable('Path', 'User')) $cliBin
    if ([Environment]::GetEnvironmentVariable('Path', 'Machine') -cne $originalMachinePath) {
        throw 'MACHINE_PATH_CHANGED: public install must never change machine PATH.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $cliBin 'olympus.cmd') -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $cliRoot 'path-entry.txt') -PathType Leaf)) {
        throw 'PUBLIC_CLI_INSTALL_INCOMPLETE: managed launcher or PATH ownership record is missing.'
    }
    $cliVersionRoot = [IO.Path]::GetFullPath((Join-Path $cliRoot "versions/$Version"))
    $cliManifestPath = Join-Path $cliVersionRoot 'olympus-cli-manifest.json'
    if (-not (Test-Path -LiteralPath $cliManifestPath -PathType Leaf)) {
        throw 'PUBLIC_CLI_MANIFEST_MISSING: expected versioned CLI ownership marker is missing.'
    }
    try {
        $cliManifest = [IO.File]::ReadAllText($cliManifestPath) | ConvertFrom-Json -Depth 30 -ErrorAction Stop
    } catch {
        throw 'PUBLIC_CLI_MANIFEST_INVALID: installed CLI ownership marker is not valid JSON.'
    }
    if ($cliManifest -isnot [System.Management.Automation.PSCustomObject]) {
        throw 'PUBLIC_CLI_MANIFEST_INVALID: installed CLI ownership marker must be a JSON object.'
    }
    $manifestFields = @($cliManifest.PSObject.Properties.Name)
    if (($cliManifest.schema_version -isnot [int] -and $cliManifest.schema_version -isnot [long]) -or
        $cliManifest.schema_version -ne 1 -or $cliManifest.version -isnot [string] -or
        $cliManifest.version -cne $Version -or
        $manifestFields.Count -ne 3 -or
        @($manifestFields | Where-Object { $_ -cnotin @('schema_version','version','files') }).Count -gt 0 -or
        $null -eq $cliManifest.files -or $cliManifest.files -isnot [array] -or $cliManifest.files.Count -eq 0) {
        throw 'PUBLIC_CLI_MANIFEST_MISMATCH: installed CLI marker is not v0.12.8.'
    }
    $managedCliFiles = [Collections.Generic.List[string]]::new()
    $seenCliFiles = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $cliVersionPrefix = $cliVersionRoot.TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    foreach ($entry in $cliManifest.files) {
        if ($entry -isnot [System.Management.Automation.PSCustomObject]) {
            throw 'PUBLIC_CLI_MANIFEST_ENTRY_INVALID: each managed file must be a path/SHA-256 object.'
        }
        $entryFields = @($entry.PSObject.Properties.Name)
        if ($entryFields.Count -ne 2 -or
            @($entryFields | Where-Object { $_ -cnotin @('path','sha256') }).Count -gt 0 -or
            $entry.path -isnot [string] -or $entry.sha256 -isnot [string]) {
            throw 'PUBLIC_CLI_MANIFEST_ENTRY_INVALID: each managed file must contain only string path and sha256 fields.'
        }
        $relative = $entry.path
        $sha256 = $entry.sha256
        $segments = $relative.Split('/')
        if ([string]::IsNullOrWhiteSpace($relative) -or $relative.Contains('\') -or
            [IO.Path]::IsPathRooted($relative) -or $relative.Contains(':') -or
            @($segments | Where-Object { [string]::IsNullOrEmpty($_) -or $_ -in @('.','..') }).Count -gt 0 -or
            $sha256 -cnotmatch '^[0-9a-f]{64}$' -or -not $seenCliFiles.Add($relative)) {
            throw 'PUBLIC_CLI_MANIFEST_PATH_INVALID: managed paths and SHA-256 values must be canonical, safe, and unique.'
        }
        $full = [IO.Path]::GetFullPath((Join-Path $cliVersionRoot ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)))
        if (-not $full.StartsWith($cliVersionPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $full -PathType Leaf)) {
            throw 'PUBLIC_CLI_MANIFEST_FILE_MISSING: a declared managed payload file is missing or outside its version root.'
        }
        if ((Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sha256) {
            throw "PUBLIC_CLI_MANIFEST_FILE_HASH_MISMATCH: managed payload file differs from its ownership marker: $relative"
        }
        $managedCliFiles.Add($full)
    }
    $cliOutput = @(& (Join-Path $cliBin 'olympus.cmd') version 2>&1 | ForEach-Object { [string]$_ })
    $cliExit = $LASTEXITCODE
    if ($cliExit -ne 0 -or @($cliOutput | Where-Object { $_ -ceq "olympus $Version" }).Count -ne 1) {
        throw 'PUBLIC_CLI_VERSION_MISMATCH: installed Olympus CLI did not report v0.12.8.'
    }
    $manifestCommitAttests = $installed.Commit -ceq $ExpectedCommit
    Write-Output "PUBLIC_INSTALL_MANIFEST: PASS installed_version=$Version installed_from_commit=$($installed.Commit) manifest_commit_attests=$($manifestCommitAttests.ToString().ToLowerInvariant()) source_identity=independently_verified"
    Write-Output "PUBLIC_CLI_VERSION: PASS $($cliOutput -join ' ')"

    $beforeVerify = Get-TreeSnapshot $fixtureRoot
    $pathBeforeVerify = [Environment]::GetEnvironmentVariable('Path', 'User')
    $machinePathBeforeVerify = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $verifyCallLog = Join-Path $runRoot 'verify-only-opencode-calls.log'
    $env:OLYMPUS_VERIFYONLY_PROBE = '1'
    $env:OLYMPUS_VERIFYONLY_CALL_LOG = $verifyCallLog
    try {
        Push-Location $workRoot
        try {
            $verifyResult = Invoke-ChildPwsh $taggedInstallerPath @('-VerifyOnly') 'Exact tagged VerifyOnly'
        } finally {
            Pop-Location
        }
    } finally {
        $env:OLYMPUS_VERIFYONLY_PROBE = $null
        $env:OLYMPUS_VERIFYONLY_CALL_LOG = $null
    }
    if (@($verifyResult.Lines | Where-Object {
            $_ -match "(?m)^OLYMPUS_GLOBAL_VERIFY: opencode $([regex]::Escape($Version)) PASS\b"
        }).Count -ne 1 -or
        (Get-TreeSnapshot $fixtureRoot) -cne $beforeVerify -or
        [Environment]::GetEnvironmentVariable('Path', 'User') -cne $pathBeforeVerify -or
        [Environment]::GetEnvironmentVariable('Path', 'Machine') -cne $machinePathBeforeVerify -or
        (Test-Path -LiteralPath $verifyCallLog) -or
        (Test-Path -LiteralPath (Join-Path $workRoot '.serena'))) {
        throw 'PUBLIC_VERIFY_ONLY_NOT_READ_ONLY: exact tagged VerifyOnly changed state or invoked OpenCode discovery.'
    }
    $installedAgain = Read-And-CheckManifest $globalManifestPath $configRoot
    if ($installedAgain.Commit -cne $installed.Commit -or
        $installedAgain.Manifest.installed_version -cne $installed.Manifest.installed_version) {
        throw 'PUBLIC_INSTALL_MANIFEST_CHANGED: manifest identity drifted during VerifyOnly.'
    }
    Assert-PathAdded $originalUserPathEntries ([Environment]::GetEnvironmentVariable('Path', 'User')) $cliBin
    Write-Output "PUBLIC_VERIFY_ONLY: PASS version=$Version read_only=true live_opencode_calls=0"

    $latestBeforeUninstall = Get-GitHubJson "$ApiRoot/releases/latest"
    [void](Assert-ExpectedRelease $latestBeforeUninstall)
    if ([long]$latestBeforeUninstall.id -ne $ExpectedReleaseId) {
        throw 'PUBLIC_LATEST_CHANGED_BEFORE_UNINSTALL: refusing to attribute an uninstall to another release.'
    }
} catch {
    $failure = $_.Exception.Message
}

if ($installAttempted -and $null -eq $failure) {
    try {
        $uninstallAttempted = $true
        Push-Location $workRoot
        try {
            $uninstallResult = Invoke-ChildPwsh $taggedUninstallerPath @() 'Public latest uninstall'
        } finally {
            Pop-Location
        }
        if (@($uninstallResult.Lines | Where-Object {
                $_ -match "(?m)^OLYMPUS_ENTRYPOINT: action=uninstall scope=global harness=opencode release=$([regex]::Escape($Version))$"
            }).Count -ne 1 -or
            @($uninstallResult.Lines | Where-Object {
                $_ -match "(?m)^OLYMPUS_RELEASE_EXECUTED: tag=$([regex]::Escape($Version)) exit_code=0$"
            }).Count -ne 1) {
            throw 'PUBLIC_UNINSTALL_ROUTE_MISMATCH: public uninstaller did not execute the expected v0.12.8 route.'
        }
        $latestAfterUninstall = Get-GitHubJson "$ApiRoot/releases/latest"
        [void](Assert-ExpectedRelease $latestAfterUninstall)
        if ([long]$latestAfterUninstall.id -ne $ExpectedReleaseId) {
            throw 'PUBLIC_LATEST_CHANGED_DURING_UNINSTALL: latest release identity changed during the lifecycle.'
        }

        if (Test-Path -LiteralPath $globalManifestPath -PathType Leaf) {
            throw 'PUBLIC_UNINSTALL_MANIFEST_REMAINS: global ownership manifest was not removed.'
        }
        foreach ($path in $installed.ManagedPaths) {
            if (Test-Path -LiteralPath $path) {
                throw 'PUBLIC_UNINSTALL_MANAGED_FILE_REMAINS: an unchanged manifest-owned resource was not removed.'
            }
        }
        foreach ($path in $managedCliFiles) {
            if (Test-Path -LiteralPath $path) {
                throw 'PUBLIC_UNINSTALL_CLI_PAYLOAD_REMAINS: a manifest-owned CLI payload file was not removed.'
            }
        }
        if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($userConfigPath)) -cne $originalConfigBytes -or
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($sentinelPath)) -cne $originalSentinel) {
            throw 'PUBLIC_UNINSTALL_USER_DATA_CHANGED: sentinel config or binary bytes were not preserved.'
        }
        Assert-PathRestored $originalUserPathEntries ([Environment]::GetEnvironmentVariable('Path', 'User')) $cliBin
        if ([Environment]::GetEnvironmentVariable('Path', 'Machine') -cne $originalMachinePath) {
            throw 'MACHINE_PATH_CHANGED: public uninstall changed machine PATH.'
        }
        foreach ($path in @(
                (Join-Path $cliBin 'olympus.cmd'),
                (Join-Path $cliRoot 'path-entry.txt'),
                (Join-Path $cliRoot 'current.txt'),
                $cliManifestPath)) {
            if (Test-Path -LiteralPath $path) {
                throw 'PUBLIC_UNINSTALL_CLI_FILE_REMAINS: a managed CLI launcher, pointer, ownership file, or manifest remains.'
            }
        }
        $uninstallSucceeded = $true
        Write-Output "PUBLIC_UNINSTALL: PASS managed_files_removed=$($installed.ManagedPaths.Count) cli_payload_files_removed=$($managedCliFiles.Count) user_path_entries_preserved=true user_config_bytes_preserved=true sentinel_bytes_preserved=true machine_path_unchanged=true"
    } catch {
        $cleanupFailure = $_.Exception.Message
    }
}

if ($environmentCaptured) {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
}
if ($null -eq $failure -and $null -ne $cleanupFailure) { $failure = $cleanupFailure }
if ($null -ne $failure) {
    Write-Output "PUBLIC_WINDOWS_LIFECYCLE: FAIL reason=$failure"
    if ($null -ne $cleanupFailure) {
        Write-Output "PUBLIC_WINDOWS_LIFECYCLE_CLEANUP: FAIL reason=$cleanupFailure (the hosted runner will be discarded; PATH was not repaired by the test)"
    }
    exit 1
}
if (-not $installAttempted -or -not $uninstallAttempted -or -not $uninstallSucceeded) {
    Write-Output 'PUBLIC_WINDOWS_LIFECYCLE: FAIL reason=install/verify/uninstall lifecycle did not complete.'
    exit 1
}
try {
    Remove-Item -LiteralPath $runRoot -Recurse -Force -ErrorAction Stop
} catch {
    Write-Output "PUBLIC_WINDOWS_LIFECYCLE: FAIL reason=fixture cleanup failed under runner temp: $($_.Exception.Message)"
    exit 1
}
Write-Output "PUBLIC_WINDOWS_LIFECYCLE: PASS version=$Version commit=$ExpectedCommit manifest_from_commit=$($installed.Commit) manifest_commit_attests=$($manifestCommitAttests.ToString().ToLowerInvariant()) host=github-hosted-windows disposable_user_path=true mocked_opencode=true"
