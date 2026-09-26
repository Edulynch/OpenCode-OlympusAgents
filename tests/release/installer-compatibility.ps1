[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('olympus-installer-compat-' + [guid]::NewGuid().ToString('N'))
function Check([string]$id, [bool]$valid) {
    if (-not $valid) { throw "$id FAIL" }
    Write-Output "$id PASS"
}
try {
    $text = [IO.File]::ReadAllText($installer)
    Check 'P3_STRICT_MODE' ($text -match 'Set-StrictMode\s+-Version\s+Latest')
    Check 'P5_NO_ISWINDOWS' ($text -notmatch '\$IsWindows' -and $text -match 'OSVersion\.Platform' -and $text -match 'PLATFORM_UNQUALIFIED')

    $pwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop).Source
    $hosts = @()
    $windowsPowerShell = Get-Command powershell.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($windowsPowerShell) {
        $version = (& $windowsPowerShell.Source -NoProfile -Command '$PSVersionTable.PSVersion.Major' | Out-String).Trim()
        if ($version -eq '5') { $hosts += [pscustomobject]@{ Id='P1_WINDOWS_POWERSHELL_5_1'; Path=$windowsPowerShell.Source } }
        else { Write-Output "P1_WINDOWS_POWERSHELL_5_1 UNAVAILABLE (found major version $version)" }
    } else { Write-Output 'P1_WINDOWS_POWERSHELL_5_1 UNAVAILABLE' }
    $hosts += [pscustomobject]@{ Id='P2_POWERSHELL_7'; Path=$pwsh }

    [IO.Directory]::CreateDirectory($run) | Out-Null
    $results = @()
    foreach ($hostEntry in $hosts) {
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
        $dry = (& $hostEntry.Path -NoProfile -File $installer -SourceRoot $source -Target $target -DryRun 2>&1 | Out-String)
        Check ($hostEntry.Id + '_DRY_RUN') ($LASTEXITCODE -eq 0 -and
            $dry -match 'OLYMPUS_INSTALL: v0.2.0 DRY_RUN_READY' -and
            -not (Test-Path -LiteralPath (Join-Path $target '.opencode/orchestrator-install.json')))
        $output = (& $hostEntry.Path -NoProfile -File $installer -SourceRoot $source -Target $target 2>&1 | Out-String)
        $code = $LASTEXITCODE
        $manifestPath = Join-Path $target '.opencode/orchestrator-install.json'
        Check $hostEntry.Id ($code -eq 0 -and $output -match '(?m)^READY\s*$' -and
            $output -match 'OLYMPUS_INSTALL: v0.2.0 READY_OR_NO_CHANGES' -and
            (Test-Path -LiteralPath $manifestPath -PathType Leaf))
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        Check ($hostEntry.Id + '_ASSETS') ($manifest.managed_files.Count -eq 12 -and
            (Test-Path -LiteralPath (Join-Path $target '.opencode/plugins/olympus-activity/activity.ts') -PathType Leaf))
        $toolStatus = (& git -C $target status --porcelain=v1 -uall -- .serena | Out-String)
        Check ($hostEntry.Id + '_UNTRACKED_TOOL_STATE') ($LASTEXITCODE -eq 0 -and
            (@($toolFiles | ForEach-Object { (Get-FileHash -LiteralPath (Join-Path $target $_) -Algorithm SHA256).Hash }) -join ',') -eq ($toolHashes -join ',') -and
            $toolStatus -match '(?m)^\?\? \.serena/\.gitignore\s*$' -and
            $toolStatus -match '(?m)^\?\? \.serena/project\.yml\s*$')
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
& $Installer -SourceRoot $SourceRoot -Target $Target
'@)
    foreach ($hostEntry in $hosts) {
        $output = (& $hostEntry.Path -NoProfile -File $missingFixture -Installer $installer -SourceRoot $missingSource -Target $missingTarget -EmptyPath $run 2>&1 | Out-String)
        $code = $LASTEXITCODE
        Check ('P4_PWSH_MISSING_' + $hostEntry.Id) ($code -ne 0 -and
            $output -match 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 \(pwsh\) is required' -and
            $output -notmatch 'SOURCE_INVALID|BOOTSTRAP_FAILED|VariableIsUndefined' -and
            -not (Test-Path -LiteralPath $missingTarget))
    }
    Write-Output 'INSTALLER COMPATIBILITY: PASS (local source; remote v0.2.0 tag not yet published)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'INSTALLER COMPATIBILITY: FAIL'
    exit 1
} finally {
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
