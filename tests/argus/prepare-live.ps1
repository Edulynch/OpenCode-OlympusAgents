[CmdletBinding()]
param([string]$Target = (Join-Path $env:LOCALAPPDATA 'Temp/opencode/argus-live-candidate'))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (Test-Path -LiteralPath $Target) { throw "Fixture already exists; preserve it or choose another -Target: $Target" }
[IO.Directory]::CreateDirectory($Target) | Out-Null
& git -C $Target init --quiet
if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
$files = @{
    'contracts/shipping.txt' = "REQUIREMENT: For valid subtotals, apply FREE_SHIPPING when subtotal >= 50; apply PAID_SHIPPING below 50.`n"
    'bug/shipping-rule.txt' = "shipping threshold = 50`nif subtotal > threshold: FREE_SHIPPING`nelse: PAID_SHIPPING`n"
    'tests/shipping-observations.txt' = "subtotal 49 => PAID_SHIPPING`nsubtotal 50 => PAID_SHIPPING`nsubtotal 51 => FREE_SHIPPING`n"
    'simple/label.txt' = "REEDY`nrequired: READY`n"
}
foreach ($entry in $files.GetEnumerator()) {
    $path = Join-Path $Target $entry.Key
    [IO.Directory]::CreateDirectory((Split-Path -Parent $path)) | Out-Null
    [IO.File]::WriteAllText($path,$entry.Value,[Text.UTF8Encoding]::new($false))
}
& git -C $Target add -- contracts bug tests simple
& git -C $Target -c user.name=Qualification -c user.email=qualify@example.invalid commit --quiet -m 'fixture: shipping boundary defect'
if ($LASTEXITCODE -ne 0) { throw 'fixture commit failed' }
$output = (& pwsh -NoProfile -File (Join-Path $source 'install.ps1') -SourceRoot $source -Target $Target 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "fixture installer failed: $output" }
Write-Output "LIVE_FIXTURE: $Target"
Write-Output 'LIVE_AGENT_CASES: NOT_EXECUTED'
