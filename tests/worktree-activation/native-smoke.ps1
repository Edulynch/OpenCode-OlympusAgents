[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$pwsh = Join-Path $PSHOME 'pwsh.exe'
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('opencode\olympus-native-worktree-' + [guid]::NewGuid().ToString('N'))
$main = Join-Path $run 'main'
$worktreeRoot = Join-Path $run 'worktrees'
$mockBin = Join-Path $run 'mock-bin'
$created = @()
$openCodeCommand = Get-Command opencode -ErrorAction SilentlyContinue | Select-Object -First 1
$originalPath = [Environment]::GetEnvironmentVariable('PATH','Process')
$environmentNames = @('XDG_DATA_HOME','XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_STATE_HOME','OPENCODE_CONFIG_DIR')
$originalEnvironment = @{}
foreach ($name in $environmentNames) { $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
$utf8 = [Text.UTF8Encoding]::new($false)

function Check([string]$Id, [bool]$Condition, [string]$Evidence = '') {
    if (-not $Condition) {
        if ($Evidence) { throw "$Id FAIL`n$Evidence" }
        throw "$Id FAIL"
    }
    Write-Output "$Id PASS"
}

function Run-Git([string]$Directory, [string[]]$Arguments) {
    $output = @(& git -C $Directory @Arguments 2>&1)
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "GIT_FIXTURE_FAILED: git $($Arguments -join ' ') in $Directory`n$($output | Out-String)" }
    return $output
}

function Run-OpenCode([string[]]$Arguments) {
    $output = @(& $openCodeCommand.Source @Arguments 2>&1)
    $code = $LASTEXITCODE
    return [pscustomobject]@{ Code=$code; Text=($output | Out-String) }
}

function Run-Script([string]$Path, [string[]]$Arguments = @()) {
    $output = @(& $pwsh -NoProfile -File $Path @Arguments 2>&1)
    $code = $LASTEXITCODE
    return [pscustomobject]@{ Code=$code; Text=($output | Out-String) }
}

function Sha-File([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-Manifest([string]$Directory) {
    $manifestPath = Join-Path $Directory '.opencode/orchestrator-install.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { return $false }
    $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json -Depth 100
    foreach ($entry in @($manifest.managed_files)) {
        $path = Join-Path $Directory ([string]$entry.path -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            (Sha-File $path) -cne ([string]$entry.sha256).ToLowerInvariant()) { return $false }
    }
    return $true
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'PLATFORM_UNQUALIFIED: Native worktree smoke is Windows-only.'
    }
    if (-not $openCodeCommand) { throw 'OPENCODE_UNAVAILABLE: Native OpenCode V2 CLI was not found.' }
    $version = Run-OpenCode @('--version')
    if ($version.Code -ne 0 -or $version.Text -notmatch 'opencode v2\.0\.(2[4-9]|[3-9][0-9])') {
        throw "OPENCODE_VERSION_UNQUALIFIED: Expected OpenCode V2.0.24 or newer; got $($version.Text.Trim())."
    }
    Write-Output ('NATIVE_OPENCODE_VERSION: ' + $version.Text.Trim())

    [IO.Directory]::CreateDirectory($run) | Out-Null
    [IO.Directory]::CreateDirectory($worktreeRoot) | Out-Null
    [IO.Directory]::CreateDirectory($mockBin) | Out-Null
    [IO.Directory]::CreateDirectory($main) | Out-Null
    Run-Git $main @('init','--quiet') | Out-Null
    Run-Git $main @('config','user.name','Olympus Native Worktree Test') | Out-Null
    Run-Git $main @('config','user.email','olympus-native-worktree@example.invalid') | Out-Null
    [IO.File]::WriteAllText((Join-Path $main 'README.md'), "Disposable native API worktree fixture.`n", $utf8)
    Run-Git $main @('add','README.md') | Out-Null
    Run-Git $main @('commit','--quiet','-m','fixture') | Out-Null

    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../release/fixtures/opencode.ps1') -Destination (Join-Path $mockBin 'opencode.ps1')
    $wrapper = "@echo off`r`n`"$pwsh`" -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), $wrapper, [Text.Encoding]::ASCII)
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $originalPath
    $install = Run-Script (Join-Path $source 'install.ps1') @('-Target',$main,'-Harness','opencode','-SourceRoot',$source,'-Version','v0.4.4')
    Check 'NATIVE_FIXTURE_PROJECT_INSTALL' ($install.Code -eq 0) $install.Text
    $env:PATH = $originalPath

    # Keep OpenCode's database, cache, config and state in this task-owned fixture.
    $runtimePathNames = @{
        XDG_DATA_HOME = 'data'
        XDG_CACHE_HOME = 'cache'
        XDG_CONFIG_HOME = 'config'
        XDG_STATE_HOME = 'state'
    }
    foreach ($name in $runtimePathNames.Keys) {
        $path = Join-Path $run $runtimePathNames[$name]
        [IO.Directory]::CreateDirectory($path) | Out-Null
        [Environment]::SetEnvironmentVariable($name,$path,'Process')
    }
    $configRoot = Join-Path $run 'config/opencode'
    [IO.Directory]::CreateDirectory($configRoot) | Out-Null
    $env:OPENCODE_CONFIG_DIR = $configRoot

    Push-Location -LiteralPath $main
    try {
        $projectsResult = Run-OpenCode @('api','--standalone','project.list')
        Check 'NATIVE_PROJECT_LIST' ($projectsResult.Code -eq 0) $projectsResult.Text
        $projects = $projectsResult.Text | ConvertFrom-Json -Depth 100
        $project = @($projects | Where-Object { [string]::Equals([string]$_.canonical,$main,[StringComparison]::OrdinalIgnoreCase) })
        Check 'NATIVE_PROJECT_ID_RESOLVED' ($project.Count -eq 1 -and [string]$project[0].id)
        $projectId = [string]$project[0].id

        $startup = 'pwsh -NoProfile -File "%OPENCODE_WORKTREE_BASE%\.opencode\scripts\worktree-setup.ps1"'
        $projectUpdateBody = @{ commands = @{ start = $startup } } | ConvertTo-Json -Depth 10 -Compress
        $update = Run-OpenCode @('api','--standalone','project.update','--param',("projectID=" + $projectId),'--data',$projectUpdateBody)
        Check 'NATIVE_PROJECT_STARTUP_SAVED' ($update.Code -eq 0 -and $update.Text -match 'OPENCODE_WORKTREE_BASE') $update.Text

        foreach ($suffix in @('b','c')) {
            $body = @{
                projectID = $projectId
                from = $main
                directory = $worktreeRoot
                name = "checkout-$suffix"
            } | ConvertTo-Json -Depth 10 -Compress
            $result = Run-OpenCode @('api','--standalone','worktree.create','--data',$body)
            Check ("NATIVE_WORKTREE_${suffix}_CREATED") ($result.Code -eq 0) $result.Text
            $info = $result.Text | ConvertFrom-Json -Depth 100
            $created += [string]$info.directory
        }
        Check 'NATIVE_STARTUP_CREATED_BOTH_MANIFESTS' ($created.Count -eq 2 -and
            (Assert-Manifest $created[0]) -and (Assert-Manifest $created[1]))
    } finally { Pop-Location }

    foreach ($directory in $created) {
        $marker = Join-Path $directory 'checkout-only.txt'
        if ($directory -eq $created[0]) { [IO.File]::WriteAllText($marker,'B',$utf8) }
        else { [IO.File]::WriteAllText($marker,'C',$utf8) }
        Push-Location -LiteralPath $directory
        try {
            $location = 'location[directory]=' + $directory
            $config = Run-OpenCode @('api','--standalone','config.get','--param',$location)
            $configEntries = if ($config.Code -eq 0) { $config.Text | ConvertFrom-Json -Depth 100 } else { @() }
            $rootConfig = @($configEntries | Where-Object {
                $_.type -eq 'document' -and [string]::Equals([string]$_.path,(Join-Path $directory 'opencode.jsonc'),[StringComparison]::OrdinalIgnoreCase)
            })
            Check 'NATIVE_WORKTREE_EFFECTIVE_DEFAULT_IS_KAEL' ($rootConfig.Count -eq 1 -and $rootConfig[0].info.default_agent -ceq 'kael') $config.Text
        } finally { Pop-Location }
    }
    Check 'NATIVE_WORKTREE_MARKERS_STAY_SEPARATE' ((Get-Content (Join-Path $created[0] 'checkout-only.txt') -Raw) -ceq 'B' -and
        (Get-Content (Join-Path $created[1] 'checkout-only.txt') -Raw) -ceq 'C')
    Write-Output 'NATIVE WORKTREE STARTUP SMOKE: PASS (OpenCode V2 awaited Project.Commands.start; effective config loaded; no model request)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'NATIVE WORKTREE STARTUP SMOKE: FAIL'
    exit 1
} finally {
    [Environment]::SetEnvironmentVariable('PATH',$originalPath,'Process')
    foreach ($name in $environmentNames) {
        $value = $originalEnvironment[$name]
        if ($null -eq $value) { Remove-Item -LiteralPath ("Env:" + $name) -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name,$value,'Process') }
    }
    if ($run -and (Test-Path -LiteralPath $run)) {
        if (Test-Path -LiteralPath $main -PathType Container) {
            $treesToRemove = @($created)
            [Array]::Reverse($treesToRemove)
            foreach ($tree in $treesToRemove) {
                if (Test-Path -LiteralPath $tree -PathType Container) {
                    & git -C $main worktree remove --force $tree 2>$null | Out-Null
                }
            }
        }
        Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction SilentlyContinue
    }
}
