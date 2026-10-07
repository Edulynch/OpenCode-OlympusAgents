# Public one-command entrypoint for Olympus uninstall (global, all).
$ErrorActionPreference = 'Stop'
$launcher = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('olympus-launch-' + [guid]::NewGuid().ToString('N') + '.ps1')

try {
    # Keep the public command tiny; this launcher resolves the latest release and pins actual execution to that tag.
    Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/scripts/launch-latest.ps1' -OutFile $launcher -ErrorAction Stop
    $pwsh = @(Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue)
    if ($pwsh.Count -eq 0) {
        throw 'OLYMPUS_REQUIRES_POWERSHELL_7: PowerShell 7 (pwsh) is required.'
    }

    & $pwsh[0].Source -NoProfile -File $launcher -Action 'uninstall' -Scope 'global' -Harness 'all' -Target (Get-Location).Path
    if ($LASTEXITCODE -ne 0) {
        throw 'OLYMPUS_ENTRYPOINT_FAILED: launcher returned a non-zero exit code.'
    }
} finally {
    if (Test-Path -LiteralPath $launcher) {
        Remove-Item -LiteralPath $launcher -Force -ErrorAction SilentlyContinue
    }
}
