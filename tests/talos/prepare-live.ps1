[CmdletBinding()]
param([string]$Target = (Join-Path $env:LOCALAPPDATA 'Temp/opencode/talos-live-candidate'))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (Test-Path -LiteralPath $Target) { throw "Fixture already exists; preserve it or choose another -Target: $Target" }
[IO.Directory]::CreateDirectory($Target) | Out-Null
& git -C $Target init --quiet
if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
$files = @{
    'contracts/access-policy.txt' = "REQUIREMENT: Only ADMIN may execute DELETE_ACCOUNT for another account. GUEST and MEMBER must be denied.`n"
    'security/access-rule.txt' = "DELETE_ACCOUNT`nrequired_role = ADMIN`nactual guard: role != GUEST`nGUEST denied; MEMBER allowed; ADMIN allowed`n"
    'observations/access.txt' = "DELETE_ACCOUNT for another account: MEMBER execution accepted; ADMIN execution accepted. Cause not established by this observation.`n"
    'simple/label.txt' = "REEDY`nrequired: READY`n"
}
foreach ($entry in $files.GetEnumerator()) {
    $path = Join-Path $Target $entry.Key
    [IO.Directory]::CreateDirectory((Split-Path -Parent $path)) | Out-Null
    [IO.File]::WriteAllText($path,$entry.Value,[Text.UTF8Encoding]::new($false))
}
& git -C $Target add -- contracts security observations simple
& git -C $Target -c user.name=Qualification -c user.email=qualify@example.invalid commit --quiet -m 'fixture: admin-only authorization boundary'
if ($LASTEXITCODE -ne 0) { throw 'fixture commit failed' }
$output = (& pwsh -NoProfile -File (Join-Path $source 'install.ps1') -SourceRoot $source -Target $Target 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "fixture installer failed: $output" }
Write-Output "LIVE_FIXTURE: $Target"
Write-Output 'LIVE_AGENT_CASES: NOT_EXECUTED'
