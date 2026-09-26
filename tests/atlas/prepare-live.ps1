[CmdletBinding()]
param([string]$Target = (Join-Path $env:LOCALAPPDATA 'Temp/opencode/atlas-live-candidate'))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (Test-Path -LiteralPath $Target) { throw "Fixture already exists; preserve it or choose another -Target: $Target" }
[IO.Directory]::CreateDirectory($Target) | Out-Null
& git -C $Target init --quiet
if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
$files = @{
    'gateway/config.txt' = "route: orders`nheader: X-Contract-Version v1`n"
    'services/orders.txt' = "accept: X-Contract-Version v1`nhandler: existing orders endpoint`n"
    'contracts/compatibility.txt' = "ARCHITECTURE: Gateway owns version-header emission; orders service owns version acceptance. Do not move responsibilities.`nROLLOUT FACT: Orders must accept v1 and v2 concurrently before gateway begins emitting v2; remove v1 acceptance only after all v1 callers are retired. Reversing the order causes failed requests. Gateway rollback to v1 remains safe while dual acceptance exists.`n"
    'tests/routing.txt' = "existing: gateway emits v1 and orders accepts v1`nrequired: v1 and v2 acceptance during overlap; gateway emits v2 after dual acceptance; rollback to v1 works`n"
    'simple/label.txt' = "READY`n"
}
foreach ($entry in $files.GetEnumerator()) {
    $path = Join-Path $Target $entry.Key
    [IO.Directory]::CreateDirectory((Split-Path -Parent $path)) | Out-Null
    [IO.File]::WriteAllText($path,$entry.Value,[Text.UTF8Encoding]::new($false))
}
& git -C $Target add -- gateway services contracts tests simple
& git -C $Target -c user.name=Qualification -c user.email=qualify@example.invalid commit --quiet -m 'fixture: version header rollout'
if ($LASTEXITCODE -ne 0) { throw 'fixture commit failed' }
$output = (& pwsh -NoProfile -File (Join-Path $source 'install.ps1') -SourceRoot $source -Target $Target 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "fixture installer failed: $output" }
Write-Output "LIVE_FIXTURE: $Target"
Write-Output 'LIVE_AGENT_CASES: NOT_EXECUTED'
