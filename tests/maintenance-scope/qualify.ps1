[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'qualify.py')
exit $LASTEXITCODE
