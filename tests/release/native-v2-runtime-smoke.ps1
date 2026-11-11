[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$ExpectedHead,

    [ValidatePattern('^v2\.[0-9]+\.[0-9]+$')]
    [string]$ExpectedOpenCode = 'v2.2.7'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$utf8 = [Text.UTF8Encoding]::new($false)
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) (
    'olympus-v050-native-runtime-' + [guid]::NewGuid().ToString('N')
)
$passed = $false

function Assert-GitSource {
    $root = (& git -C $source rev-parse --show-toplevel 2>$null | Out-String).Trim()
    $rootExit = $LASTEXITCODE
    $head = (& git -C $source rev-parse HEAD 2>$null | Out-String).Trim()
    $headExit = $LASTEXITCODE
    if ($rootExit -ne 0 -or $headExit -ne 0 -or -not $root -or -not $head) {
        throw "SOURCE_IDENTITY_MISMATCH: expected=$ExpectedHead; actual=$head"
    }
    if ([IO.Path]::GetFullPath($root).TrimEnd('\', '/') -ine $source.TrimEnd('\', '/') -or
        $head -cne $ExpectedHead) {
        throw "SOURCE_IDENTITY_MISMATCH: expected=$ExpectedHead; actual=$head"
    }

    # The candidate must be a clean checkout; unrelated user files stay outside it.
    $status = (& git -C $source status --porcelain --untracked-files=all | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $status) {
        throw 'SOURCE_NOT_CLEAN: Use an isolated, clean worktree at the exact PR commit.'
    }
    Write-Output "SOURCE_IDENTITY: PASS ($head)"
}

function New-IsolatedProject([string]$Name) {
    $target = Join-Path $run $Name
    [IO.Directory]::CreateDirectory($target) | Out-Null
    [IO.File]::WriteAllText((Join-Path $target 'README.md'), "Isolated Olympus runtime fixture`n", $utf8)

    & git -C $target init --quiet
    if ($LASTEXITCODE -ne 0) { throw "FIXTURE_INIT_FAILED: $Name" }
    & git -C $target add -- README.md
    if ($LASTEXITCODE -ne 0) { throw "FIXTURE_ADD_FAILED: $Name" }
    & git -C $target -c user.name='Olympus Qualification' `
        -c user.email='qualification@example.invalid' commit --quiet -m 'isolated runtime fixture'
    if ($LASTEXITCODE -ne 0) { throw "FIXTURE_COMMIT_FAILED: $Name" }

    return $target
}

function New-IsolatedEnvironment([string]$Name) {
    $base = Join-Path $run ($Name + '-environment')
    # HOME is a protected automatic PowerShell variable, so use a distinct local name.
    $isolatedHome = Join-Path $base 'home'
    $drive = [IO.Path]::GetPathRoot($isolatedHome).TrimEnd('\')
    $paths = @{
        HOME = $isolatedHome
        USERPROFILE = $isolatedHome
        HOMEDRIVE = $drive
        HOMEPATH = $isolatedHome.Substring($drive.Length)
        APPDATA = (Join-Path $isolatedHome 'AppData/Roaming')
        LOCALAPPDATA = (Join-Path $isolatedHome 'AppData/Local')
        XDG_CONFIG_HOME = (Join-Path $base 'xdg-config')
        XDG_DATA_HOME = (Join-Path $base 'xdg-data')
        XDG_CACHE_HOME = (Join-Path $base 'xdg-cache')
        XDG_STATE_HOME = (Join-Path $base 'xdg-state')
        OPENCODE_CONFIG_DIR = (Join-Path $base 'opencode-config')
        TEMP = (Join-Path $base 'temp')
        TMP = (Join-Path $base 'temp')
    }

    # HOMEDRIVE/HOMEPATH are Windows identity fields, not actual directories.
    # Create only paths owned by this test's unique temporary environment.
    foreach ($key in @('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA',
        'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME',
        'OPENCODE_CONFIG_DIR', 'TEMP', 'TMP')) {
        [IO.Directory]::CreateDirectory([string]$paths[$key]) | Out-Null
    }

    # The test-only command shim makes the installer's nested OpenCode calls
    # use private servers without changing the user's shared service or its port.
    $shimDirectory = Join-Path $base 'standalone-shim'
    [IO.Directory]::CreateDirectory($shimDirectory) | Out-Null
    $shimPath = Join-Path $shimDirectory 'opencode.cmd'
    $shim = "@echo off`r`nopencode.exe --standalone %*`r`nexit /b %errorlevel%`r`n"
    [IO.File]::WriteAllText($shimPath, $shim, [Text.Encoding]::ASCII)
    $paths['OLYMPUS_QUALIFICATION_SHIM'] = $shimPath
    return $paths
}

function Invoke-BoundedProbe {
    param(
        [string]$Name,
        [string]$Project,
        [hashtable]$IsolatedEnvironment,
        [string[]]$Arguments,
        [int]$TimeoutMilliseconds
    )

    $pwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $start = [Diagnostics.ProcessStartInfo]::new([IO.Path]::GetFullPath($pwsh))
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.WorkingDirectory = [IO.Path]::GetFullPath($Project)

    # Keep provider credentials and user OpenCode settings out of both child processes.
    # Native executables and PowerShell still need these Windows process essentials.
    $start.Environment.Clear()
    foreach ($key in @('PATH', 'SystemRoot', 'WINDIR', 'COMSPEC', 'PATHEXT',
        'PSModulePath', 'ProgramFiles', 'ProgramFiles(x86)')) {
        $value = [Environment]::GetEnvironmentVariable($key, 'Process')
        if ($value) { $start.Environment[$key] = $value }
    }
    foreach ($key in $IsolatedEnvironment.Keys) {
        $start.Environment[$key] = [string]$IsolatedEnvironment[$key]
    }
    $shimPath = [string]$IsolatedEnvironment['OLYMPUS_QUALIFICATION_SHIM']
    if (-not (Test-Path -LiteralPath $shimPath -PathType Leaf)) {
        throw "STANDALONE_SHIM_MISSING: $Name"
    }
    $start.Environment['PATH'] = (Split-Path -Parent $shimPath) + ';' + $start.Environment['PATH']
    $effectiveArguments = @('-NoProfile', '-NonInteractive') + @($Arguments)
    foreach ($argument in $effectiveArguments) {
        $start.ArgumentList.Add([string]$argument)
    }

    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw "PROCESS_START_FAILED: $Name" }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()

        $timedOut = -not $process.WaitForExit($TimeoutMilliseconds)
        if ($timedOut) {
            # Kill only this qualification-owned process tree, never a pre-existing service.
            try {
                $process.Kill($true)
                if (-not $process.WaitForExit(5000)) {
                    throw 'Process did not exit after termination.'
                }
            }
            catch { throw "PROCESS_TIMEOUT_CLEANUP_FAILED: $Name; pid=$($process.Id)" }
        }

        # Drain asynchronously opened pipes with a bounded wait, including after timeout.
        if (-not [Threading.Tasks.Task]::WaitAll(
            [Threading.Tasks.Task[]]@($stdoutTask, $stderrTask), 5000)) {
            throw "PROCESS_OUTPUT_DRAIN_TIMEOUT: $Name; pid=$($process.Id)"
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        [IO.File]::WriteAllText((Join-Path $run ($Name + '.stdout.log')), $stdout, $utf8)
        [IO.File]::WriteAllText((Join-Path $run ($Name + '.stderr.log')), $stderr, $utf8)
        if ($timedOut) { throw "PROCESS_TIMEOUT: $Name; pid=$($process.Id)" }

        return [pscustomobject]@{
            Name = $Name
            ExitCode = $process.ExitCode
            Pid = $process.Id
            Stdout = $stdout
            Stderr = $stderr
        }
    } finally { $process.Dispose() }
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'PLATFORM_UNQUALIFIED: This native smoke requires Windows and PowerShell 7.'
    }
    Assert-GitSource

    # V2 has an independent release stream. GitHub releases/latest may select V1.
    $openCodeVersion = (& opencode --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $openCodeVersion -cne "opencode $ExpectedOpenCode") {
        throw "OPENCODE_VERSION_MISMATCH: expected=$ExpectedOpenCode; actual=$openCodeVersion"
    }
    Write-Output "OPENCODE_VERSION: PASS ($openCodeVersion)"
    if (-not (Get-Command opencode.exe -CommandType Application -ErrorAction SilentlyContinue)) {
        throw 'OPENCODE_NATIVE_BINARY_MISSING: Standalone qualification requires opencode.exe on PATH.'
    }
    Write-Output 'OPENCODE_SERVICE_MODE: STANDALONE (user managed service untouched)'

    [IO.Directory]::CreateDirectory($run) | Out-Null

    # A clean native OpenCode control distinguishes runtime startup from Olympus config.
    $clean = New-IsolatedProject 'clean-project'
    $cleanEnvironment = New-IsolatedEnvironment 'clean'
    $cleanResult = Invoke-BoundedProbe -Name 'clean-debug-config' -Project $clean `
        -IsolatedEnvironment $cleanEnvironment `
        -Arguments @('-Command',
            'if ((Get-Command opencode -CommandType Application).Source -ine $env:OLYMPUS_QUALIFICATION_SHIM) { throw "STANDALONE_SHIM_NOT_ACTIVE" }; & opencode debug config') `
        -TimeoutMilliseconds 45000
    if ($cleanResult.ExitCode -ne 0) {
        throw "CLEAN_RUNTIME_FAILED: exit=$($cleanResult.ExitCode); inspect clean-debug-config logs."
    }
    Write-Output "CLEAN_RUNTIME: PASS (pid=$($cleanResult.Pid))"

    # The official candidate installer writes only to a new temporary Git project.
    # Its own post-install checks must discover the effective agents in real OpenCode.
    $candidate = New-IsolatedProject 'candidate-project'
    $candidateEnvironment = New-IsolatedEnvironment 'candidate'
    $installResult = Invoke-BoundedProbe -Name 'candidate-install' -Project $candidate `
        -IsolatedEnvironment $candidateEnvironment `
        -Arguments @('-File', $installer, '-SourceRoot', $source, '-Target', $candidate,
            '-Version', 'v0.5.0', '-Scope', 'project', '-Harness', 'opencode') `
        -TimeoutMilliseconds 90000
    if ($installResult.ExitCode -ne 0 -or
        $installResult.Stdout -notmatch 'OLYMPUS_INSTALL: v0\.5\.0 READY_OR_NO_CHANGES') {
        throw "OLYMPUS_NATIVE_INSTALL_FAILED: exit=$($installResult.ExitCode); inspect candidate-install logs."
    }
    foreach ($required in @('opencode.jsonc', '.opencode/orchestrator-install.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $candidate $required) -PathType Leaf)) {
            throw "MANAGED_INSTALL_FILE_MISSING: $required"
        }
    }
    Write-Output "OLYMPUS_NATIVE_INSTALL: PASS (pid=$($installResult.Pid))"
    $passed = $true
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    throw
} finally {
    if ($passed) {
        # Remove only this probe's randomly named temporary fixtures and logs.
        Remove-Item -LiteralPath $run -Recurse -Force
    } elseif (Test-Path -LiteralPath $run -PathType Container) {
        Write-Output "EVIDENCE_DIRECTORY: $run"
        Write-Output 'EVIDENCE_WARNING: Review logs for secrets before sharing them.'
    }
}

Write-Output 'OA64_NATIVE_STANDALONE_QUALIFICATION: PASS'
