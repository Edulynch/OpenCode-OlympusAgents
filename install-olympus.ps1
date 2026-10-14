# Unified interactive and direct Olympus installation entrypoint.
[CmdletBinding(DefaultParameterSetName = 'Interactive')]
param(
    [Parameter(ParameterSetName = 'ProjectHere')]
    [switch]$Project,
    [Parameter(ParameterSetName = 'ProjectHere')]
    [switch]$Here,
    [Parameter(ParameterSetName = 'ProjectPath')]
    [ValidateNotNullOrEmpty()]
    [string]$ProjectPath,
    [Parameter(ParameterSetName = 'Global')]
    [switch]$Global,
    [ValidateSet('opencode', 'codex', 'all')]
    [string]$Harness
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ownedLauncher = $null

function Read-InstallScope {
    while ($true) {
        Write-Host 'Install scope:'
        Write-Host '  [1] Current project'
        Write-Host '  [2] Another project path'
        Write-Host '  [3] Global'
        $choice = (Read-Host 'Choose 1, 2, or 3').Trim()
        switch ($choice) {
            '1' { return [pscustomobject]@{ Scope = 'project'; Target = (Get-Location).Path } }
            '2' {
                $path = (Read-Host 'Project path').Trim()
                if ($path) { return [pscustomobject]@{ Scope = 'project'; Target = $path } }
                Write-Host 'A project path is required.'
            }
            '3' { return [pscustomobject]@{ Scope = 'global'; Target = (Get-Location).Path } }
            default { Write-Host 'Choose 1, 2, or 3.' }
        }
    }
}

function Read-InstallHarness {
    while ($true) {
        Write-Host 'Harness:'
        Write-Host '  [1] OpenCode'
        Write-Host '  [2] Codex'
        Write-Host '  [3] Both'
        $choice = (Read-Host 'Choose 1, 2, or 3').Trim()
        switch ($choice) {
            '1' { return 'opencode' }
            '2' { return 'codex' }
            '3' { return 'all' }
            default { Write-Host 'Choose 1, 2, or 3.' }
        }
    }
}

try {
    if ($PSBoundParameters.Count -eq 0) {
        # A host-supplied Read-Host function can provide input without console stdin.
        $readHostProvider = Get-Command Read-Host -ErrorAction SilentlyContinue
        $hasPromptProvider = $null -ne $readHostProvider -and $readHostProvider.CommandType -eq 'Function'
        if (-not [Environment]::UserInteractive -or ([Console]::IsInputRedirected -and -not $hasPromptProvider)) {
            throw 'ARGUMENTS_REQUIRED: Interactive mode requires a terminal. Supply -Project -Here, -ProjectPath <path>, or -Global together with -Harness.'
        }
        $selection = Read-InstallScope
        $scope = $selection.Scope
        $target = $selection.Target
        $selectedHarness = Read-InstallHarness
    } else {
        if (-not $PSBoundParameters.ContainsKey('Harness')) {
            throw 'ARGUMENTS_INVALID: Direct mode requires -Harness opencode, -Harness codex, or -Harness all.'
        }
        $selectedHarness = $Harness.ToLowerInvariant()

        if ($PSCmdlet.ParameterSetName -eq 'ProjectHere') {
            if (-not $Project -or -not $Here) {
                throw 'ARGUMENTS_INVALID: Select the current project with both -Project and -Here.'
            }
            $scope = 'project'
            $target = (Get-Location).Path
        } elseif ($PSCmdlet.ParameterSetName -eq 'ProjectPath') {
            $scope = 'project'
            $target = $ProjectPath
        } elseif ($PSCmdlet.ParameterSetName -eq 'Global' -and $Global) {
            $scope = 'global'
            $target = (Get-Location).Path
        } else {
            throw 'ARGUMENTS_INVALID: Select -Project -Here, -ProjectPath <path>, or -Global.'
        }
    }

    $pwsh = @(Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue)
    if ($pwsh.Count -eq 0) {
        throw 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 (pwsh) is required.'
    }

    $launcher = $null
    if ($PSCommandPath) {
        $localLauncher = Join-Path (Split-Path -Parent $PSCommandPath) 'scripts/launch-latest.ps1'
        if (Test-Path -LiteralPath $localLauncher -PathType Leaf) { $launcher = $localLauncher }
    }
    if (-not $launcher) {
        $tempBase = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode'
        [IO.Directory]::CreateDirectory($tempBase) | Out-Null
        $ownedLauncher = Join-Path $tempBase ('olympus-install-entry-' + [guid]::NewGuid().ToString('N') + '.ps1')
        # This immutable launcher already exists; the release-specific installer it selects is pinned by its tag.
        Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.8/scripts/launch-latest.ps1' -OutFile $ownedLauncher -ErrorAction Stop
        $launcher = $ownedLauncher
    }

    $launcherArgs = @(
        '-NoProfile', '-File', $launcher,
        '-Action', 'install',
        '-Scope', $scope,
        '-Harness', $selectedHarness,
        '-Target', [IO.Path]::GetFullPath($target)
    )
    & $pwsh[0].Source @launcherArgs
    if ($LASTEXITCODE -ne 0) {
        throw "OLYMPUS_ENTRYPOINT_FAILED: launcher returned exit code $LASTEXITCODE."
    }
} finally {
    if ($ownedLauncher -and (Test-Path -LiteralPath $ownedLauncher)) {
        Remove-Item -LiteralPath $ownedLauncher -Force -ErrorAction SilentlyContinue
    }
}
