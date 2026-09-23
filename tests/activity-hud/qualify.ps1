[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$work = Join-Path $root 'tests/.phase4c-work'
$fixture = Join-Path $work ('activity-' + [guid]::NewGuid().ToString('N'))
$plugin = '.opencode/plugins/olympus-activity'
$utf8 = [Text.UTF8Encoding]::new($false)
try {
    & node --test (Join-Path $PSScriptRoot 'activity.test.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'H4-H8: Node presentation checks failed.' }
    $plugins = (& opencode plugin list 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $plugins -notmatch 'olympus-activity') { throw ('H2: Plugin discovery failed: ' + $plugins) }
    Write-Output 'H2: native project plugin discovered (does not assert TUI rendering)'

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

    $again = (& pwsh -NoProfile -File (Join-Path $root 'scripts/bootstrap.ps1') -Target $fixture 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $again -notmatch '(?m)^NO_CHANGES\s*$') { throw ('H1: Reinstall not idempotent: ' + $again) }
    Write-Output 'H1: reinstall idempotent PASS'
    # Emulate a clean owned installation from immediately before the HUD.
    $manifest.managed_files = @($manifest.managed_files | Where-Object { $_.path -notin $paths })
    [IO.File]::WriteAllText($manifestPath, (($manifest | ConvertTo-Json -Depth 100) + "`n"), $utf8)
    foreach ($path in $paths) { [IO.File]::Delete((Join-Path $fixture $path)) }
    $upgrade = (& pwsh -NoProfile -File (Join-Path $root 'scripts/bootstrap.ps1') -Target $fixture 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $upgrade -notmatch '(?m)^READY\s*$') { throw ('H1: Pre-HUD managed upgrade failed: ' + $upgrade) }
    foreach ($path in $paths) { if (-not (Test-Path (Join-Path $fixture $path))) { throw ('H1: Upgrade missing ' + $path) } }
    Write-Output 'H1: pre-HUD managed install safely upgraded PASS'
    $changed = Join-Path $fixture $paths[1]
    [IO.File]::AppendAllText($changed, "// local user edit`n", $utf8)
    $before = (Get-FileHash $changed -Algorithm SHA256).Hash
    $drift = (& pwsh -NoProfile -File (Join-Path $root 'scripts/bootstrap.ps1') -Target $fixture 2>&1 | Out-String)
    if ($LASTEXITCODE -eq 0 -or $drift -notmatch 'MANAGED_FILE_DRIFT' -or (Get-FileHash $changed -Algorithm SHA256).Hash -ne $before) {
        throw ('H9: Managed drift not preserved: ' + $drift)
    }
    Write-Output 'H9: managed modification rejected without overwrite PASS'
    Write-Output 'ACTIVITY HUD QUALIFICATION: PASS (static and discovery; interactive smoke not run)'
    Write-Output ('FIXTURE_RETAINED: ' + $fixture)
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output ('FIXTURE_RETAINED: ' + $fixture)
    Write-Output 'ACTIVITY HUD QUALIFICATION: FAIL'
    exit 1
}
