[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('FAST','FULL','RUNTIME')]
    [string]$Profile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$script:RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$script:PowerShell = Join-Path $PSHOME 'pwsh.exe'
$script:Results = [Collections.Generic.List[object]]::new()
$script:Python = $null

function Resolve-Python311 {
    foreach ($name in @('python3.11','python3','python')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        & $command.Source -B -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { return $command.Source }
    }
    throw 'Python 3.11+ is unavailable locally; no environment or package installation was attempted.'
}

function Add-Result([string]$Name, [string]$Status, [string]$Detail = '', [double]$DurationMs = 0) {
    $null = $script:Results.Add([pscustomobject]@{ Name=$Name; Status=$Status; Detail=$Detail; DurationMs=$DurationMs })
}

function Mark-NotRun([string]$Name, [string]$Reason) {
    Write-Output "[$Name] NOT RUN: $Reason"
    Add-Result $Name 'NOT RUN' $Reason
}

function Invoke-Check([string]$Name, [string]$Executable, [string[]]$Arguments, [switch]$AllowExplicitNotRun) {
    Write-Output "`n=== $Name ==="
    $code = 1
    $output = @()
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $output = @(& $Executable @Arguments 2>&1)
        $code = [int]$LASTEXITCODE
    } catch {
        $output += 'TOOL ERROR: ' + $_.Exception.Message
        $code = 1
    } finally {
        $stopwatch.Stop()
    }
    foreach ($line in $output) { Write-Output $line }
    if ($code -eq 0) {
        Write-Output "[$Name] PASS (exit 0)"
        Add-Result $Name 'PASS' '' $stopwatch.Elapsed.TotalMilliseconds
    } elseif ($code -eq 2) {
        $text = ($output | Out-String)
        if ($AllowExplicitNotRun -and $text -match '(?m)^CODEX_MODEL_CATALOG: NOT RUN \(Codex CLI unavailable\)\s*$') {
            Write-Output "[$Name] NOT RUN (exit 2; explicit Codex CLI prerequisite unavailable)"
            Add-Result $Name 'NOT RUN' 'Codex CLI unavailable; bundled catalog was not checked.' $stopwatch.Elapsed.TotalMilliseconds
        } else {
            Write-Output "[$Name] FAIL (unexpected exit 2 without an allowed explicit NOT RUN reason)"
            Add-Result $Name 'FAIL' 'exit 2 without a designated missing-prerequisite result' $stopwatch.Elapsed.TotalMilliseconds
        }
    } else {
        Write-Output "[$Name] FAIL (exit $code)"
        Add-Result $Name 'FAIL' "exit $code" $stopwatch.Elapsed.TotalMilliseconds
    }
}

function Invoke-PwshCheck([string]$Name, [string]$RelativePath, [string[]]$ExtraArguments = @()) {
    $arguments = @('-NoProfile','-File',(Join-Path $script:RepoRoot $RelativePath)) + $ExtraArguments
    Invoke-Check $Name $script:PowerShell $arguments
}

function Invoke-PythonCheck([string]$Name, [string]$RelativePath, [string[]]$ExtraArguments = @(), [switch]$AllowExplicitNotRun) {
    $arguments = @('-B',(Join-Path $script:RepoRoot $RelativePath)) + $ExtraArguments
    Invoke-Check $Name $script:Python $arguments -AllowExplicitNotRun:$AllowExplicitNotRun
}

function Invoke-FastSlice {
    Write-Output "`n######## FAST — offline-only qualification ########"
    Invoke-PythonCheck 'Harness Core (safe root read-only)' 'tests/harness-core/qualify.py' @('--safe-root-read-only')
    Invoke-PythonCheck 'Codex static profile (no CLI/catalog probe)' 'tests/codex/validate_profile.py' @('--mode','static')

    $offlineSuites = @(
        'tests/aegis-recovery/qualify.ps1',
        'tests/adaptive-concurrency/qualify.ps1',
        'tests/completion-gates/qualify.ps1',
        'tests/maintenance-handoff/qualify.ps1',
        'tests/maintenance-scope/qualify.ps1',
        'tests/model-migration/qualify.ps1',
        'tests/preflight/qualify.ps1',
        'tests/question-barrier/qualify.ps1',
        'tests/result-reconciliation/qualify.ps1',
        'tests/role-purity/qualify.ps1',
        'tests/routing-constraints/qualify.ps1',
        'tests/trivial-fast-path/qualify.ps1'
    )
    foreach ($suite in $offlineSuites) { Invoke-PwshCheck $suite $suite }
    Invoke-PwshCheck 'Maintenance handoff fidelity' 'tests/maintenance-handoff/qualify-fidelity.ps1'
    Invoke-PwshCheck 'External-work ownership static contracts' 'tests/external-work-ownership/qualify.ps1' @('-StaticOnly')
}

function Invoke-FullAdditions {
    Write-Output "`n######## FULL — additions after FAST ########"
    Invoke-PwshCheck 'Global installer qualification' 'tests/global-installer/qualify.ps1'
    Invoke-PwshCheck 'Release qualification (MockOpenCode)' 'tests/release/qualify.ps1' @('-MockOpenCode')
    Invoke-PwshCheck 'Release installer compatibility' 'tests/release/installer-compatibility.ps1'
    Invoke-PwshCheck 'Dual-harness installer' 'tests/release/dual-harness-installer.ps1'
    Invoke-PwshCheck 'Codex instructions precedence' 'tests/codex-instructions-precedence/qualify.ps1'
    # The dirty-worktree installer fixture checks the local CLI version preflight;
    # use the established deterministic stub, never the user's real runtime.
    $dirtyMockRoot = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('issue11-dirty-worktree-opencode-' + [guid]::NewGuid().ToString('N'))
    $dirtyOriginalPath = [Environment]::GetEnvironmentVariable('PATH','Process')
    try {
        [IO.Directory]::CreateDirectory($dirtyMockRoot) | Out-Null
        Copy-Item -LiteralPath (Join-Path $script:RepoRoot 'tests/release/fixtures/opencode.ps1') -Destination (Join-Path $dirtyMockRoot 'opencode.ps1')
        $dirtyWrapper = "@echo off`r`n`"$script:PowerShell`" -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
        [IO.File]::WriteAllText((Join-Path $dirtyMockRoot 'opencode.cmd'), $dirtyWrapper, [Text.Encoding]::ASCII)
        $env:PATH = $dirtyMockRoot + [IO.Path]::PathSeparator + $dirtyOriginalPath
        Invoke-PwshCheck 'Dirty-worktree installer' 'tests/release/dirty-worktree.ps1'
    } finally {
        [Environment]::SetEnvironmentVariable('PATH',$dirtyOriginalPath,'Process')
        if (Test-Path -LiteralPath $dirtyMockRoot) {
            Remove-Item -LiteralPath $dirtyMockRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    Invoke-PythonCheck 'Phase 11 offline qualifier' 'tests/phase11-integrated-routing/qualify.py'
    Invoke-Check 'Phase 11 unittest suite' $script:Python @('-B','-m','unittest','discover','-s',(Join-Path $script:RepoRoot 'tests/phase11-integrated-routing'),'-p','test_*.py','-v')
    Invoke-Check 'Phase 11 feature fixture unittests' $script:Python @('-B','-m','unittest','discover','-s',(Join-Path $script:RepoRoot 'tests/phase11-integrated-routing/fixtures/feature'),'-p','test_*.py','-v')

    $offlineSlices = @(
        @('Authority grants','tests/authority/qualify.ps1'),
        @('Activity HUD','tests/activity-hud/qualify.ps1'),
        @('Argus','tests/argus/qualify.ps1'),
        @('Atlas','tests/atlas/qualify.ps1'),
        @('Helios','tests/helios/qualify.ps1'),
        @('Talos','tests/talos/qualify.ps1'),
        @('Thales','tests/thales/qualify.ps1'),
        @('Phase 4C','tests/phase4c/qualify.ps1'),
        @('Autonomy','tests/autonomy/qualify.ps1')
    )
    foreach ($slice in $offlineSlices) {
        Invoke-PwshCheck $slice[0] $slice[1] @('-QualificationSlice','Offline')
    }
}

function Invoke-RuntimeSlice {
    Write-Output "`n######## RUNTIME — runtime boundaries only; no FULL slice ########"
    $codex = Get-Command codex -ErrorAction SilentlyContinue
    if ($codex) {
        Invoke-PythonCheck 'Codex bundled model catalog only' 'tests/codex/validate_profile.py' @('--mode','catalog') -AllowExplicitNotRun
    } else {
        Mark-NotRun 'Codex bundled model catalog' 'Codex CLI unavailable; catalog is not reported as PASS.'
    }

    Invoke-PwshCheck 'External-work ownership disposable processes only' 'tests/external-work-ownership/qualify.ps1' @('-ProcessesOnly')

    if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) {
        foreach ($suite in @(
            @('Authority effective rules','tests/authority/qualify.ps1'),
            @('Activity plugin discovery','tests/activity-hud/qualify.ps1'),
            @('Argus effective agent','tests/argus/qualify.ps1'),
            @('Atlas effective agent','tests/atlas/qualify.ps1'),
            @('Helios effective agent','tests/helios/qualify.ps1'),
            @('Talos effective agent','tests/talos/qualify.ps1'),
            @('Thales effective agent','tests/thales/qualify.ps1'),
            @('Phase 4C runtime scenarios','tests/phase4c/qualify.ps1'),
            @('Autonomy effective permissions','tests/autonomy/qualify.ps1')
        )) {
            Mark-NotRun $suite[0] 'OpenCode CLI unavailable; runtime boundary not exercised.'
        }
        return
    }

    Invoke-PwshCheck 'Authority effective rules' 'tests/authority/qualify.ps1' @('-QualificationSlice','Runtime')
    Invoke-PwshCheck 'Activity plugin discovery' 'tests/activity-hud/qualify.ps1' @('-QualificationSlice','Runtime')
    foreach ($slice in @(
        @('Argus effective agent','tests/argus/qualify.ps1'),
        @('Atlas effective agent','tests/atlas/qualify.ps1'),
        @('Helios effective agent','tests/helios/qualify.ps1'),
        @('Talos effective agent','tests/talos/qualify.ps1'),
        @('Thales effective agent','tests/thales/qualify.ps1'),
        @('Phase 4C runtime scenarios','tests/phase4c/qualify.ps1'),
        @('Autonomy effective permissions','tests/autonomy/qualify.ps1')
    )) {
        Invoke-PwshCheck $slice[0] $slice[1] @('-QualificationSlice','Runtime')
    }
}

 $originalPath = [Environment]::GetEnvironmentVariable('PATH','Process')
 $originalNoBytecode = [Environment]::GetEnvironmentVariable('PYTHONDONTWRITEBYTECODE','Process')
 $pythonShimRoot = $null
 $profileExitCode = 1
$profileStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
try {
    if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 is required.' }
    if (-not (Test-Path -LiteralPath $script:PowerShell -PathType Leaf)) { throw 'The active PowerShell 7 executable could not be resolved from PSHOME.' }
    $script:Python = Resolve-Python311
    $windowsApps = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
    $pathParts = @($originalPath -split [regex]::Escape([IO.Path]::PathSeparator) | Where-Object {
        $_ -and $_.Trim('"') -ine $windowsApps -and $_.Trim('"') -ine $PSHOME
    })
    $pathParts = @($PSHOME) + $pathParts
    if ($Profile -in @('FAST','FULL')) {
        $approvedTempRoot = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode'
        if (-not (Test-Path -LiteralPath $approvedTempRoot -PathType Container)) { throw 'Approved temp/opencode root is unavailable for the temporary Python command shim.' }
        $pythonShimRoot = Join-Path $approvedTempRoot ('issue11-python-' + [guid]::NewGuid().ToString('N'))
        [IO.Directory]::CreateDirectory($pythonShimRoot) | Out-Null
        $pythonCommand = '@echo off' + "`r`n" + '"' + $script:Python + '" %*' + "`r`n" + 'exit /b %ERRORLEVEL%' + "`r`n"
        [IO.File]::WriteAllText((Join-Path $pythonShimRoot 'python.cmd'), $pythonCommand, [Text.Encoding]::ASCII)
        $pathParts = @($pythonShimRoot) + $pathParts
        $env:PYTHONDONTWRITEBYTECODE = '1'
    }
    $env:PATH = $pathParts -join [IO.Path]::PathSeparator
    $gitRoot = (& git -C $script:RepoRoot rev-parse --show-toplevel 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not [string]::Equals([IO.Path]::GetFullPath($gitRoot),$script:RepoRoot,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'The facade must run from its trusted source checkout.'
    }

    Push-Location $script:RepoRoot
    try {
        if ($Profile -in @('FAST','FULL')) { Invoke-FastSlice }
        if ($Profile -eq 'FULL') { Invoke-FullAdditions }
        if ($Profile -eq 'RUNTIME') { Invoke-RuntimeSlice }
    } finally { Pop-Location }

    $failed = @($script:Results | Where-Object Status -eq 'FAIL')
    $notRun = @($script:Results | Where-Object Status -eq 'NOT RUN')
    $passed = @($script:Results | Where-Object Status -eq 'PASS')
    $overall = if ($failed.Count -gt 0) {
        if ($passed.Count -gt 0 -or $notRun.Count -gt 0) { 'PARTIAL' } else { 'FAILED' }
    } elseif ($notRun.Count -gt 0) { 'PARTIAL' } else { 'PASS' }
    Write-Output "`nQUALIFICATION PROFILE: $Profile $overall (PASS=$($passed.Count); FAIL=$($failed.Count); NOT RUN=$($notRun.Count))"
    if ($failed.Count -gt 0) { $profileExitCode = 1 }
    elseif ($notRun.Count -gt 0) { $profileExitCode = 2 }
    else { $profileExitCode = 0 }
} catch {
    Write-Output ('QUALIFICATION PROFILE: ' + $Profile + ' FAILED: ' + $_.Exception.Message)
    $profileExitCode = 1
} finally {
    [Environment]::SetEnvironmentVariable('PATH',$originalPath,'Process')
    if ($null -eq $originalNoBytecode) {
        Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
    } else {
        [Environment]::SetEnvironmentVariable('PYTHONDONTWRITEBYTECODE',$originalNoBytecode,'Process')
    }
    if ($pythonShimRoot -and (Test-Path -LiteralPath $pythonShimRoot)) {
        Remove-Item -LiteralPath $pythonShimRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
$profileStopwatch.Stop()
Write-Output "`nQUALIFICATION TIMING (top 5 slowest)"
foreach ($result in @($script:Results | Sort-Object -Property DurationMs -Descending | Select-Object -First 5)) {
    Write-Output ('[{0}] {1}: {2:N2} ms' -f $result.Status, $result.Name, $result.DurationMs)
}
Write-Output ('TOTAL PROFILE TIME: {0:N2} ms' -f $profileStopwatch.Elapsed.TotalMilliseconds)
exit $profileExitCode
