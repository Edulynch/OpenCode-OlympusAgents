[CmdletBinding()]
param([ValidateSet('Both','Offline','Runtime')][string]$QualificationSlice = 'Both')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('thales-qualification-' + [guid]::NewGuid().ToString('N'))
function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}
function Install([string]$root, [string]$repo) {
    $args = @('-NoProfile','-File',(Join-Path $root 'scripts/bootstrap.ps1'),'-Target',$repo)
    $output = (& pwsh @args 2>&1 | Out-String)
    [pscustomobject]@{ Code=$LASTEXITCODE; Output=$output }
}
try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    if ($QualificationSlice -ne 'Runtime') {
    $kael = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/kael.md'))
    $thales = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/thales.md'))
    Check 'TH1_TH2_TH17_SINGLE_IDENTITY' ((Test-Path (Join-Path $source '.opencode/agents/thales.md')) -and
        -not (Test-Path (Join-Path $source '.opencode/agents/sorin.md')))
    Check 'TH3_TH4_ROUTING' ($kael -match 'resource: thales' -and $kael -notmatch '(?i)\bsorin\b' -and
        $kael -match 'Only veyra, orin, kovan, nox, vera, thales, atlas, argus, talos, and helios are valid child role IDs')
    Check 'TH5_TH8_MODEL_PERMISSIONS' ($thales -match 'model: openai/gpt-6.1-sol#xhigh' -and
        @(@('shell','edit','subagent') | ForEach-Object { $thales -match ('(?s)action: ' + $_ + '\s+resource: "?\*"?\s+effect: deny') }) -notcontains $false)
    Check 'TH9_GATE' ($kael -match '## Diagnostic Gate' -and $kael -match 'evidence-backed condition' -and
        $kael -match 'Do not invoke Thales merely because a task is large, complex, or important')
    Check 'TH10_TH16_BUDGET_NEGATIVE' ($kael -match 'No third automatic consultation' -and
        $kael -match 'explicit user authorization' -and $kael -match 'not by itself a reason to invoke Thales')
    Check 'TH11_TH13_ITERATION' ($kael -match 'SAME native Thales session' -and
        $kael -match 'Topology: USER/ROOT → Kael → Thales → EVIDENCE_REQUEST → Kael → worker' -and
        $thales -match 'STATUS: EVIDENCE_REQUEST' -and $thales -match 'EXPECTED_DISCRIMINATION')
    Check 'TH14_TH15_BOUNDARIES' ($kael -match 'PENDING_OR_INDETERMINATE' -and $kael -match 'COMPLETION_UNCONFIRMED' -and
        $kael -match 'Only veyra, orin, kovan, nox, vera, thales, atlas, argus, talos, and helios are valid child role IDs')
    Check 'TH20_TH22_MODELS_CONCURRENCY' ($kael -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $kael -match 'fan out up to four useful children' -and $kael -notmatch 'gpt-6-luna#fast')
    Check 'TH_ROLE_SEMANTICS' ($thales -match 'DO YOUR ROLE. DO NOT ABSORB ANOTHER ROLE TO SAVE A HANDOFF' -and
        $thales -match 'Reasoning is more than repeating worker summaries' -and
        $thales -match 'STATUS: ADVICE \| INCONCLUSIVE \| BLOCKED' -and
        $thales -match 'same native session')
    }
    if ($QualificationSlice -ne 'Offline') {
    $fresh = Join-Path $run 'fresh'
    [IO.Directory]::CreateDirectory($fresh) | Out-Null
    & git -C $fresh init --quiet
    $freshResult = Install $source $fresh
    # The CLI must be queried from the installed project, not this source checkout.
    Push-Location $fresh
    try { $effective = (& opencode debug agents 2>$null | Out-String) }
    finally { Pop-Location }
    $agents = $effective | ConvertFrom-Json -Depth 100
    Check 'TH_FRESH_INSTALL' ($freshResult.Code -eq 0 -and
        (Test-Path (Join-Path $fresh '.opencode/agents/thales.md')) -and
        -not (Test-Path (Join-Path $fresh '.opencode/agents/sorin.md')) -and
        @($agents | Where-Object id -eq 'sorin').Count -eq 0 -and
        @($agents | Where-Object { $_.id -eq 'thales' -and $_.model.id -eq 'gpt-6.1-sol' -and $_.model.variant -eq 'xhigh' }).Count -eq 1)
    }

    if ($QualificationSlice -eq 'Runtime') {
        Write-Output 'THALES RUNTIME QUALIFICATION: PASS (fresh installed effective agent; no interactive session executed)'
    } elseif ($QualificationSlice -eq 'Offline') {
        Write-Output 'THALES OFFLINE QUALIFICATION: PASS (static policy checks; effective OpenCode queries not run)'
    } else {
        Write-Output 'THALES QUALIFICATION: PASS'
    }
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'THALES QUALIFICATION: FAIL'
    exit 1
} finally {
    if (Test-Path -LiteralPath $run) {
        try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop }
        catch { Write-Output "CLEANUP_DEFERRED: $run" }
    }
}
