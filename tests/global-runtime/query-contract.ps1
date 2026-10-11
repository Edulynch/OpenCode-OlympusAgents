# Static-only check: do not launch OpenCode or inspect the user's global profile.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$qualifier = Join-Path $PSScriptRoot 'qualify.ps1'
$source = [IO.File]::ReadAllText($qualifier)

function Check([string]$Label, [bool]$Condition) {
    if (-not $Condition) { throw "$Label FAIL" }
    Write-Output "$Label PASS"
}

$expectedUri = '$requestUri = "$endpoint/api/agent?location%5Bdirectory%5D=$encodedDirectory"'
$previousUri = '$requestUri = "$endpoint/api/agent?directory=$encodedDirectory"'
Check 'GLOBAL_AGENT_V2_LOCATION_QUERY' ($source.Contains($expectedUri) -and
    -not $source.Contains($previousUri))

# The query key and the fixture directory are encoded independently.
$directory = 'C:\fixture worktree & name+other'
$encodedDirectory = [Uri]::EscapeDataString($directory)
$uri = [Uri]::new("http://127.0.0.1:43121/api/agent?location%5Bdirectory%5D=$encodedDirectory")
$query = [Uri]::UnescapeDataString($uri.Query.TrimStart('?'))
Check 'GLOBAL_AGENT_QUERY_URI_ENCODING' ($uri.AbsolutePath -ceq '/api/agent' -and
    $query -ceq ("location[directory]=" + $directory))

# A list of currently registered agents is not an activation-complete event.
Check 'GLOBAL_AGENT_EMPTY_ROSTER_NEEDS_EVIDENCE' (
    $source.Contains("elseif (`$reproducibleGlobalRosterGap) { 'NEEDS_RUNTIME_EVIDENCE' }") -and
    $source.Contains('OPENCODE_GLOBAL_RUNTIME_DISCOVERY: NEEDS_RUNTIME_EVIDENCE') -and
    -not $source.Contains("elseif (`$reproducibleGlobalRosterGap) { 'GAP' }")
)

Write-Output 'GLOBAL AGENT QUERY CONTRACT: PASS (offline only; no OpenCode runtime, network, or global profile access)'
