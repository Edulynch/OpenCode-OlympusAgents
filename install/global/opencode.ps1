[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Update
)

$ErrorActionPreference = 'Stop'
$bootstrap = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('olympus-install-' + [guid]::NewGuid().ToString('N') + '.ps1')

try {
    if ($DryRun -and $Update) { throw 'UPDATE_MODE_INVALID: -Update cannot be combined with -DryRun.' }
    $pwsh = @(Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue)
    if ($pwsh.Count -eq 0) {
        throw 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 (pwsh) is required.'
    }

    Invoke-WebRequest -Uri 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1' -OutFile $bootstrap -ErrorAction Stop
    $arguments = @('-NoProfile', '-File', $bootstrap)
    if ($DryRun) { $arguments += '-DryRun' }
    if ($Update) { $arguments += '-Update' }
    & $pwsh[0].Source @arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'OLYMPUS_ENTRYPOINT_FAILED: global OpenCode bootstrap returned a non-zero exit code.'
    }
} finally {
    if (Test-Path -LiteralPath $bootstrap) {
        Remove-Item -LiteralPath $bootstrap -Force -ErrorAction SilentlyContinue
    }
}
