[CmdletBinding()]
param([string]$Target = (Join-Path $env:LOCALAPPDATA 'Temp/opencode/helios-live-candidate'))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (Test-Path -LiteralPath $Target) { throw "Fixture already exists; preserve it or choose another -Target: $Target" }
[IO.Directory]::CreateDirectory($Target) | Out-Null
& git -C $Target init --quiet
if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
$artifact = Join-Path $Target 'artifact/report.html'
[IO.Directory]::CreateDirectory((Split-Path -Parent $artifact)) | Out-Null
$bytes = [Text.Encoding]::ASCII
$eightMiB = 8 * 1024 * 1024
$header = '<!doctype html><title>Qualification report</title>' + "`n"
$open = '<script type="application/json" data-report-payload="shared">'
$close = '</script>' + "`n"
$payload = 'A' * ($eightMiB - $bytes.GetByteCount($open + $close))
$intro = $header + ('R' * ($eightMiB - $bytes.GetByteCount($header)))
$writer = [IO.StreamWriter]::new($artifact,$false,$bytes)
try {
    $writer.Write($intro)
    for ($i=0; $i -lt 4; $i++) { $writer.Write($open); $writer.Write($payload); $writer.Write($close) }
} finally { $writer.Dispose() }
$size = (Get-Item -LiteralPath $artifact).Length
if ($size -ne 40 * 1024 * 1024) { throw "Fixture size unexpected: $size" }
$facts = @{
    'config/report-export.txt' = "Current report export embeds four copies of the same shared payload into artifact/report.html. A supported export option 'shared_payload_mode = reference_once' emits one shared copy and three references; browser consumer resolves references. This option is disabled. References and supported consumer must be validated for equivalent render. The first 8 MiB of report are unrelated content and must not be removed.`n"
    'observations/size.txt' = "Prepared artifact/report.html measured by Get-Item.Length: $size bytes (40 MiB). Desired target: < 25 MiB. Actual post-change measurement not available. Correctness: report render must remain equivalent.`n"
}
foreach ($entry in $facts.GetEnumerator()) {
    $path=Join-Path $Target $entry.Key
    [IO.Directory]::CreateDirectory((Split-Path -Parent $path)) | Out-Null
    [IO.File]::WriteAllText($path,$entry.Value,[Text.UTF8Encoding]::new($false))
}
& git -C $Target add -- artifact config observations
& git -C $Target -c user.name=Qualification -c user.email=qualify@example.invalid commit --quiet -m 'fixture: measured oversized report'
if ($LASTEXITCODE -ne 0) { throw 'fixture commit failed' }
$output=(& pwsh -NoProfile -File (Join-Path $source 'install.ps1') -SourceRoot $source -Target $Target 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "fixture installer failed: $output" }
Write-Output "LIVE_FIXTURE: $Target"
Write-Output "MEASURED_BASELINE_BYTES: $size"
Write-Output 'LIVE_AGENT_CASES: NOT_EXECUTED'
