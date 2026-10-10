[CmdletBinding()]
param([ValidateSet('Both','Offline','Runtime')][string]$QualificationSlice = 'Both')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$work = Join-Path $root 'tests/.phase4c-work'
$fixture = Join-Path $work ('activity-' + [guid]::NewGuid().ToString('N'))
$plugin = '.opencode/plugins/olympus-activity'
$utf8 = [Text.UTF8Encoding]::new($false)
$originalPath = [Environment]::GetEnvironmentVariable('PATH','Process')
$mockBin = $null
function Enable-OfflineOpenCodeStub([string]$FixtureRoot) {
    $script:mockBin = Join-Path $FixtureRoot ('activity-opencode-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($script:mockBin) | Out-Null
    Copy-Item -LiteralPath (Join-Path $root 'tests/release/fixtures/opencode.ps1') -Destination (Join-Path $script:mockBin 'opencode.ps1')
    $pwsh = Join-Path $PSHOME 'pwsh.exe'
    $wrapper = "@echo off`r`n`"$pwsh`" -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
    [IO.File]::WriteAllText((Join-Path $script:mockBin 'opencode.cmd'), $wrapper, [Text.Encoding]::ASCII)
    $windowsApps = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
    $parts = @($originalPath -split [regex]::Escape([IO.Path]::PathSeparator) | Where-Object {
        $_ -and $_.Trim('"') -ine $windowsApps -and $_.Trim('"') -ine $PSHOME
    })
    $env:PATH = (@($script:mockBin,$PSHOME) + $parts) -join [IO.Path]::PathSeparator
}
try {
    if ($QualificationSlice -eq 'Offline') {
        [IO.Directory]::CreateDirectory($work) | Out-Null
        Enable-OfflineOpenCodeStub $work
    }
    if ($QualificationSlice -ne 'Runtime') {
    & node --test (Join-Path $PSScriptRoot 'activity.test.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'H4-H8: Node presentation checks failed.' }
    }
    if ($QualificationSlice -ne 'Offline') {
    $plugins = (& opencode plugin list 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $plugins -notmatch 'olympus-activity') { throw ('H2: Plugin discovery failed: ' + $plugins) }
    Write-Output 'H2: native project plugin discovered (does not assert TUI rendering)'
    }

    [IO.Directory]::CreateDirectory($work) | Out-Null
    [IO.Directory]::CreateDirectory($fixture) | Out-Null
    [IO.File]::WriteAllText((Join-Path $fixture 'README.md'), "Activity qualification fixture`n", $utf8)
    [IO.File]::WriteAllText((Join-Path $fixture '.gitignore'), ".serena/`n", $utf8)
    & git -C $fixture init --quiet
    & git -C $fixture -c user.name=Qualification -c user.email=qualification@example.invalid add -- README.md .gitignore
    & git -C $fixture -c user.name=Qualification -c user.email=qualification@example.invalid commit --quiet -m fixture
    if ($LASTEXITCODE -ne 0) { throw 'Fixture Git setup failed.' }

    $first = (& pwsh -NoProfile -File (Join-Path $root 'scripts/bootstrap.ps1') -Target $fixture 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $first -notmatch '(?m)^READY\s*$') { throw ('H1: Fresh bootstrap failed: ' + $first) }
    if ($QualificationSlice -ne 'Runtime') {
    $paths = @("$plugin/activity.ts", "$plugin/tui.tsx")
    $manifestPath = Join-Path $fixture '.opencode/orchestrator-install.json'
    $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json
    foreach ($path in $paths) {
        $installed = Join-Path $fixture $path
        $source = Join-Path $root $path
        if (-not (Test-Path $installed)) { throw ('H1: Missing ' + $path) }
        if ((Get-FileHash $installed -Algorithm SHA256).Hash -ne (Get-FileHash $source -Algorithm SHA256).Hash) { throw ('H1: Unexpected installed content ' + $path) }
        if (@($manifest.managed_files | Where-Object path -eq $path).Count -ne 1) { throw ('H1: Manifest does not own ' + $path) }
    }
    Write-Output 'H1: fresh install and manifest ownership PASS'
    if (Test-Path (Join-Path $fixture 'package.json')) { throw 'H3: Package dependency introduced.' }
    Write-Output 'H3: no package.json or install dependency PASS'
    }
    if ($QualificationSlice -ne 'Offline') {
    Push-Location $fixture
    try {
        & opencode debug config *> $null
        if ($LASTEXITCODE -ne 0) { throw 'H2: debug config failed.' }
        & opencode debug agents *> $null
        if ($LASTEXITCODE -ne 0) { throw 'H2: debug agents failed.' }
        $discovery = (& opencode plugin list 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0 -or $discovery -notmatch 'olympus-activity') { throw ('H2: Installed plugin undiscovered: ' + $discovery) }
    } finally { Pop-Location }
    Write-Output 'H2: installed project plugin discovered, config and agents diagnostics PASS'
    }

    if ($QualificationSlice -ne 'Runtime') {
    $again = (& pwsh -NoProfile -File (Join-Path $root 'scripts/bootstrap.ps1') -Target $fixture 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $again -notmatch '(?m)^NO_CHANGES\s*$') { throw ('H1: Reinstall not idempotent: ' + $again) }
    Write-Output 'H1: reinstall idempotent PASS'
    # Reconstruct a real pre-HUD inventory: the worktree setup helper was
    # introduced later, so it must be absent from this historical fixture too.
    $historicalMissing = @($paths) + @('.opencode/scripts/worktree-setup.ps1')
    $manifest.managed_files = @($manifest.managed_files | Where-Object { $_.path -notin $historicalMissing })
    [IO.File]::WriteAllText($manifestPath, (($manifest | ConvertTo-Json -Depth 100) + "`n"), $utf8)
    foreach ($path in $historicalMissing) { [IO.File]::Delete((Join-Path $fixture $path)) }
    if (@($manifest.managed_files | Where-Object { $_.path -in $historicalMissing }).Count -gt 0) {
        throw 'H1: Historical inventory retained a post-HUD managed resource.'
    }
    $upgrade = (& pwsh -NoProfile -File (Join-Path $root 'scripts/bootstrap.ps1') -Target $fixture 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $upgrade -notmatch '(?m)^READY\s*$') { throw ('H1: Pre-HUD managed upgrade failed: ' + $upgrade) }
    foreach ($path in $historicalMissing) {
        if (-not (Test-Path (Join-Path $fixture $path))) { throw ('H1: Upgrade missing ' + $path) }
        if ((Get-FileHash (Join-Path $fixture $path) -Algorithm SHA256).Hash -ne
            (Get-FileHash (Join-Path $root $path) -Algorithm SHA256).Hash) {
            throw ('H1: Upgrade altered managed resource ' + $path)
        }
    }
    Write-Output 'H1: pre-HUD/pre-helper managed install safely upgraded PASS'
    $changed = Join-Path $fixture $paths[1]
    [IO.File]::AppendAllText($changed, "// local user edit`n", $utf8)
    $before = (Get-FileHash $changed -Algorithm SHA256).Hash
    $drift = (& pwsh -NoProfile -File (Join-Path $root 'scripts/bootstrap.ps1') -Target $fixture 2>&1 | Out-String)
    if ($LASTEXITCODE -eq 0 -or $drift -notmatch 'MANAGED_FILE_DRIFT' -or (Get-FileHash $changed -Algorithm SHA256).Hash -ne $before) {
        throw ('H9: Managed drift not preserved: ' + $drift)
    }
    Write-Output 'H9: managed modification rejected without overwrite PASS'
    }
    if ($QualificationSlice -eq 'Runtime') {
        Write-Output 'ACTIVITY HUD RUNTIME QUALIFICATION: PASS (OpenCode plugin discovery; TUI smoke not run)'
    } elseif ($QualificationSlice -eq 'Offline') {
        Write-Output 'ACTIVITY HUD OFFLINE QUALIFICATION: PASS (Node presentation and bootstrap/history checks; live plugin discovery not run)'
    } else {
        Write-Output 'ACTIVITY HUD QUALIFICATION: PASS (static and discovery; interactive smoke not run)'
    }
    Write-Output ('FIXTURE_RETAINED: ' + $fixture)
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output ('FIXTURE_RETAINED: ' + $fixture)
    Write-Output 'ACTIVITY HUD QUALIFICATION: FAIL'
    exit 1
} finally {
    [Environment]::SetEnvironmentVariable('PATH',$originalPath,'Process')
    if ($mockBin -and (Test-Path -LiteralPath $mockBin)) {
        Remove-Item -LiteralPath $mockBin -Recurse -Force -ErrorAction SilentlyContinue
    }
}
