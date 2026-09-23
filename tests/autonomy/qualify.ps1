[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$work = Join-Path $root 'tests/.phase4c-work'
$fixture = Join-Path $work ('autonomy-' + [guid]::NewGuid().ToString('N'))
$utf8 = [Text.UTF8Encoding]::new($false)
function Check([string]$Id, [bool]$Ok) {
    if (-not $Ok) { throw "$Id FAIL" }
    Write-Output "$Id PASS"
}
function Has($agent, [string]$action, [string]$effect) {
    return @($agent.permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq $effect }).Count -gt 0
}
try {
    [IO.Directory]::CreateDirectory($fixture) | Out-Null
    [IO.File]::WriteAllText((Join-Path $fixture 'README.md'), "autonomy fixture`n", $utf8)
    & git -C $fixture init --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Fixture Git init failed.' }
    & git -C $fixture -c user.name=Qualification -c user.email=qualification@example.invalid add -- README.md
    & git -C $fixture -c user.name=Qualification -c user.email=qualification@example.invalid commit --quiet -m fixture
    if ($LASTEXITCODE -ne 0) { throw 'Fixture Git commit failed.' }
    $install = (& pwsh -NoProfile -File (Join-Path $root 'scripts/bootstrap.ps1') -Target $fixture 2>&1 | Out-String)
    Check AU12 ($LASTEXITCODE -eq 0 -and $install -match '(?m)^READY\s*$')
    Push-Location $fixture
    try {
        $agents = (& opencode debug agents 2>&1 | Out-String) | ConvertFrom-Json -Depth 100
        if ($LASTEXITCODE -ne 0) { throw 'OpenCode agent diagnostics failed.' }
    } finally { Pop-Location }
    $k = @($agents | Where-Object id -eq kovan)[0]
    $n = @($agents | Where-Object id -eq nox)[0]
    Check AU1 (Has $k shell allow)
    Check AU2 ((Has $k edit allow) -and @($k.permissions | Where-Object { $_.action -eq 'edit' -and $_.resource -eq '.opencode/*' -and $_.effect -eq 'deny' }).Count -gt 0)
    Check AU3_STATIC ((Has $k shell allow) -and (Has $k edit allow) -and ([IO.File]::ReadAllText((Join-Path $fixture '.opencode/agents/kovan.md')) -match 'Project scripts created as'))
    Check AU4_STATIC ((Has $n shell allow) -and @($n.permissions | Where-Object { $_.action -eq 'shell' -and $_.resource -eq 'pwsh -NoProfile -File ./safe-validation.ps1' -and $_.effect -eq 'allow' }).Count -eq 0)
    Check AU5 (Has $n edit deny)
    foreach ($case in @(@('AU6','kael'), @('AU7','veyra'), @('AU8','orin'), @('AU9','vera'), @('AU10','sorin'))) {
        $a = @($agents | Where-Object id -eq $case[1])[0]
        Check $case[0] ((Has $a shell deny) -and (Has $a edit deny) -and -not (Has $a shell allow))
    }
    Check AU11_STATIC ((Has $k external_directory allow) -and (Has $n external_directory allow) -and @($k.permissions + $n.permissions | Where-Object { $_.action -eq 'shell' -and $_.effect -eq 'ask' }).Count -eq 0)
    $again = (& pwsh -NoProfile -File (Join-Path $root 'scripts/bootstrap.ps1') -Target $fixture 2>&1 | Out-String)
    Check AU12_IDEMPOTENT ($LASTEXITCODE -eq 0 -and $again -match '(?m)^NO_CHANGES\s*$')
    Write-Output 'AU3/AU4/AU11 RUNTIME: PENDING INTERACTIVE VALIDATION (no child-agent execution in this harness)'
    Write-Output 'AUTONOMY QUALIFICATION: PASS (static effective permissions and bootstrap only)'
    Write-Output ('FIXTURE_RETAINED: ' + $fixture)
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output ('FIXTURE_RETAINED: ' + $fixture)
    Write-Output 'AUTONOMY QUALIFICATION: FAIL'
    exit 1
}
