[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$cli = @(Get-Command olympus -CommandType Application -ErrorAction SilentlyContinue)
if ($cli.Count -eq 0) { throw 'OLYMPUS_CLI_REQUIRED: Run the installed global Olympus CLI to uninstall.' }

& $cli[0].Source uninstall --execute
if ($LASTEXITCODE -ne 0) { throw 'OLYMPUS_ENTRYPOINT_FAILED: global OpenCode CLI uninstall returned a non-zero exit code.' }
