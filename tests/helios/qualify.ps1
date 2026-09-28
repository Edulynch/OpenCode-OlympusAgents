[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$production = 'a5b2c9a12f542217e7d9927034486f922756d17c'
$run = Join-Path (Join-Path $env:LOCALAPPDATA 'Temp/opencode') ('helios-qualification-' + [guid]::NewGuid().ToString('N'))
$old = Join-Path $run 'production-source'
function Check([string]$id, [bool]$ok) { if (-not $ok) { throw "$id FAIL" }; Write-Output "$id PASS" }
function Install([string]$root, [string]$target, [switch]$DryRun) {
    $args = @('-NoProfile','-File',(Join-Path $root 'install.ps1'),'-SourceRoot',$root,'-Target',$target)
    if ($DryRun) { $args += '-DryRun' }
    $output = (& pwsh @args 2>&1 | Out-String)
    [pscustomobject]@{ Code=$LASTEXITCODE; Output=$output }
}
function Snapshot([string]$root) {
    $paths = @('src/local.txt','docs/staged.txt','notes.txt','.serena/project.yml','.opencode/user-note.txt')
    $hashes = @($paths | ForEach-Object { (Get-FileHash -LiteralPath (Join-Path $root $_) -Algorithm SHA256).Hash }) -join ','
    $index = (& git -C $root diff --cached --binary | Out-String)
    $status = (& git -C $root status --porcelain=v1 -uall -- @($paths) | Out-String)
    "$hashes`n$index`n$status"
}
function Simulate([string]$case) {
    # Offline state-machine simulation only; NOT agent execution or live qualification.
    $intent = $case -in @('proposal','already-met','architecture','third','indeterminate','approval','regression')
    $calls = if ($intent) { 1 } else { 0 }
    $state = if ($intent) { 'TRIAGE' } else { 'NO_ROUTE' }
    $worker = ''; $workerParent = ''; $same = $false; $implementation = $false
    if ($intent) {
        switch ($case) {
            'already-met' { $state = 'DO_NOT_OPTIMIZE' }
            'indeterminate' { $state = 'COMPLETION_UNCONFIRMED'; $worker = 'ORIGINAL_UNRESOLVED' }
            'architecture' { $state = 'NEEDS_ARCHITECTURE' }
            default {
                $state = 'EVIDENCE_REQUEST'; $worker = 'nox'; $workerParent = 'kael'
                $calls++; $same = $true; $state = 'OPTIMIZATION_PROPOSAL'
            }
        }
    }
    if ($case -eq 'third') { $state = 'THIRD_DENIED' }
    if ($case -eq 'regression') { $state = 'VALIDATION_FAILED' }
    [pscustomobject]@{ Status=$state; Sessions=[int]$intent; Calls=$calls; Worker=$worker; WorkerParent=$workerParent; SameSession=$same; Implemented=$implementation }
}
try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $h = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/helios.md'))
    $k = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/kael.md'))
    $b = [IO.File]::ReadAllText((Join-Path $source 'scripts/bootstrap.ps1'))
    $r = [IO.File]::ReadAllText((Join-Path $source 'docs/ROADMAP.md'))
    Check HE1 ($h -match '(?m)^# ☀️ Helios The Optimizer\r?$' -and $h -match 'mode: subagent' -and $b -match '".opencode/agents/helios.md"')
    Check HE2 ($h -match 'model: openai/gpt-6-sol#high')
    Check HE3 ($k -match '(?s)action: subagent\s+resource: helios\s+effect: allow' -and $k -match 'and helios are valid child role IDs')
    foreach ($pair in @(@('HE4','shell'),@('HE5','edit'),@('HE6','subagent'))) { Check $pair[0] ($h -match ('(?s)action: ' + $pair[1] + '\s+resource: "\*"\s+effect: deny')) }
    Check HE7 (@('read','glob','grep','list','lsp' | Where-Object { $h -notmatch ('(?s)action: ' + $_ + '\s+resource: "\*"\s+effect: deny') }).Count -eq 0)
    Check HE8 ($k -match '## Optimization Gate — explicit-only Helios' -and $h -match 'User intent must explicitly ask')
    Check HE9 ($k -match 'HELIOS COUNT = 0' -and $h -match 'fact alone' -and -not (Test-Path (Join-Path $source '.opencode/commands/helios.md')) -and -not (Test-Path (Join-Path $source '.opencode/commands/performance.md')))
    Check HE10 ($k -match 'CHEAP FEASIBILITY TRIAGE' -and $h -match 'TARGET_METRIC, CURRENT_EVIDENCE, DESIRED_THRESHOLD and MEANINGFUL_DELTA')
    Check HE11 ($k -match 'DO_NOT_OPTIMIZE is a successful outcome' -and $h -match 'STATUS: DO_NOT_OPTIMIZE')
    Check HE12 (@('STATUS: OPTIMIZATION_PROPOSAL','OBJECTIVE:','BASELINE:','TARGET:','BOTTLENECK:','OPPORTUNITY:','PROPOSAL:','EXPECTED_BENEFIT:','EFFORT:','RISK:','CONFIDENCE:','VALIDATION:','TRADEOFFS:','STOP_CONDITIONS:','APPROVAL_REQUIRED: YES' | Where-Object { -not $h.Contains($_) }).Count -eq 0)
    Check HE13 (@('STATUS: EVIDENCE_REQUEST','TARGET_ROLE: veyra | nox','QUESTION:','SCOPE:','WHY_NEEDED:','EXPECTED_DISCRIMINATION:' | Where-Object { -not $h.Contains($_) }).Count -eq 0)
    Check HE14 ($k -match 'MANDATORY USER APPROVAL GATE' -and $h -match 'STOP FOR USER APPROVAL')
    Check HE15 ($k -match 'No automatic Kovan, Atlas, implementation' -and $h -match 'No automatic Atlas, Kovan')
    Check HE16 ($k -match 'BEFORE, AFTER, DELTA, TARGET and CORRECTNESS' -and $h -match 'target unmet or correctness regression')
    Check HE17 ($h -match 'Atlas asks HOW' -and $k -match 'Helios asks WHETHER/WHAT')
    Check HE18 ($h -match 'Argus diagnoses WRONG functional behavior')
    Check HE19 ($h -match 'Talos diagnoses security defects' -and $h -match 'never recommend weakening')
    Check HE20 ($h -match "Thales handles high-uncertainty technical diagnosis" -and $k -match 'Do not invoke Thales merely because performance')
    Check HE21 ($h -match 'STATUS: NEEDS_ARCHITECTURE' -and $k -match 'Kael decides whether Orin')
    Check HE22 ($h -match 'Nox MEASURES' -and $k -match 'Nox MEASURES')
    Check HE23 ($h -match 'Vera independently reviews implemented correctness' -and $k -match 'Vera independently reviews')
    Check HE24 ($k -match 'Kael → Helios → EVIDENCE_REQUEST → Kael' -and $h -match 'direct Kael-owned Veyra or Nox')
    Check HE25 ($k -match 'SAME Helios session' -and $h -match 'SAME Helios session')
    Check HE26 ($k -match 'up to 2 Helios consultations' -and $h -match 'up to 2 Helios consultations')
    Check HE27 ($k -match 'Third automatic consultation DENIED' -and $h -match 'Third automatic consultation DENIED')
    Check HE28 ($k -match 'NO_PROGRESS:' -and $h -match 'NO_PROGRESS:')
    Check HE29 ($k -match 'MISSING OUTPUT != WORKER FAILURE' -and $h -match 'reconciles that original')
    Check HE30 ($k -match 'Issue #2 Aegis handoff stays intact' -and $k -match 'MAINTENANCE_RESULT_PENDING')
    Check HE31 ($k -match 'Kael → Aegis DENIED' -and $h -match 'user → /maintain explicit only')
    Check HE32 ($k -match 'Kael retains all routing, reconciliation and root completion' -and $h -match 'Kael retains routing, reconciliation and root completion')
    $expected = @{ kael='gpt-6-sol#high'; atlas='gpt-6-sol#high'; argus='gpt-6-sol#high'; talos='gpt-6-sol#high'; helios='gpt-6-sol#high'; thales='gpt-6-sol#xhigh'; aegis='gpt-6-luna#max'; veyra='gpt-6-luna#max'; orin='gpt-6-luna#max'; kovan='gpt-6-luna#max'; nox='gpt-6-luna#max'; vera='gpt-6-luna#max' }
    Check HE33 (@($expected.Keys | Where-Object { ([IO.File]::ReadAllText((Join-Path $source ".opencode/agents/$_.md"))) -notmatch ('(?m)^model: "?openai/' + [regex]::Escape($expected[$_]) + '"?\r?$') }).Count -eq 0)
    Check HE34 ($k -match 'MAX_ACTIVE_CHILDREN = 4' -and $k -match 'fan out up to four useful children')
    Check HE35 (-not (Test-Path (Join-Path $source '.opencode/agents/sorin.md')) -and $b -match '\$OldReasoner = ''.opencode/agents/sorin.md''')
    Check HE36 ((& git -C $source grep -n -i 'gpt-6-luna#fast' -- '.opencode/agents' 'opencode.jsonc' | Out-String).Length -eq 0)
    Check HE_ROADMAP ($r -match '8 — Helios The Optimizer \| \*\*SHIPPED\*\*' -and @('3 — Role Purity + Iterative Evidence','4 — Thales evolution','5 — Atlas The Planner','6 — Argus The Bug Hunter','7 — Talos The Sentinel' | Where-Object { $r -notmatch ([regex]::Escape($_) + ' \| \*\*SHIPPED\*\*') }).Count -eq 0)
    $a=Simulate proposal; Check CASE_A ($a.Status -eq 'OPTIMIZATION_PROPOSAL' -and $a.Sessions -eq 1 -and $a.Calls -eq 2 -and $a.WorkerParent -eq 'kael' -and $a.SameSession -and -not $a.Implemented)
    $c=Simulate already-met; Check CASE_B ($c.Status -eq 'DO_NOT_OPTIMIZE' -and -not $c.Implemented)
    $c=Simulate fact; Check CASE_C ($c.Sessions -eq 0 -and $c.Calls -eq 0)
    $c=Simulate architecture; Check CASE_D ($c.Status -eq 'NEEDS_ARCHITECTURE' -and -not $c.Implemented)
    Check CASE_E ((Simulate functional).Sessions -eq 0 -and $k -match 'Correctness defects belong to Argus')
    Check CASE_F ((Simulate security).Sessions -eq 0 -and $k -match 'security boundary defects belong to Talos')
    $c=Simulate third; Check CASE_G ($c.Status -eq 'THIRD_DENIED' -and $c.Calls -eq 2)
    $c=Simulate indeterminate; Check CASE_H ($c.Status -eq 'COMPLETION_UNCONFIRMED' -and $c.Worker -eq 'ORIGINAL_UNRESOLVED' -and $c.Calls -eq 1)
    $c=Simulate approval; Check CASE_I ($c.Status -eq 'OPTIMIZATION_PROPOSAL' -and -not $c.Implemented -and $k -match 'STOP')
    $c=Simulate regression; Check CASE_J ($c.Status -eq 'VALIDATION_FAILED' -and $k -match 'correctness regression = NOT successful')

    & git -C $source worktree add --detach $old $production | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'production worktree fixture failed' }
    $upgrade = Join-Path $run 'upgrade'; [IO.Directory]::CreateDirectory($upgrade) | Out-Null; & git -C $upgrade init --quiet
    foreach ($path in @('src/local.txt','docs/staged.txt')) {
        $dest=Join-Path $upgrade $path; [IO.Directory]::CreateDirectory((Split-Path $dest -Parent)) | Out-Null
        [IO.File]::WriteAllText($dest,"original $path`n")
    }
    & git -C $upgrade add -- src docs
    & git -C $upgrade -c user.name=Qualification -c user.email=qualification@example.invalid commit --quiet -m fixture
    $initial=Install $old $upgrade
    Check U_BASE ($initial.Code -eq 0 -and -not (Test-Path (Join-Path $upgrade '.opencode/agents/helios.md')))
    [IO.File]::WriteAllText((Join-Path $upgrade 'src/local.txt'),"modified work`n")
    [IO.File]::WriteAllText((Join-Path $upgrade 'docs/staged.txt'),"staged work`n")
    & git -C $upgrade add -- docs/staged.txt
    foreach ($path in @('notes.txt','.serena/project.yml','.opencode/user-note.txt')) {
        $dest=Join-Path $upgrade $path; [IO.Directory]::CreateDirectory((Split-Path $dest -Parent)) | Out-Null
        [IO.File]::WriteAllText($dest,"user owned $path`n")
    }
    $before=Snapshot $upgrade
    $dry=Install $source $upgrade -DryRun
    Check U_DRY ($dry.Code -eq 0 -and $dry.Output -match '\.opencode/agents/helios.md' -and -not (Test-Path (Join-Path $upgrade '.opencode/agents/helios.md')))
    $installed=Install $source $upgrade
    if ($installed.Code -ne 0) { Write-Output $installed.Output }
    $manifest=[IO.File]::ReadAllText((Join-Path $upgrade '.opencode/orchestrator-install.json')) | ConvertFrom-Json
    Check U_UPGRADE ($installed.Code -eq 0 -and (Test-Path (Join-Path $upgrade '.opencode/agents/helios.md')) -and @($manifest.managed_files | Where-Object path -eq '.opencode/agents/helios.md').Count -eq 1 -and @($manifest.managed_files | Where-Object path -eq '.opencode/agents/talos.md').Count -eq 1)
    Check U_USER_INDEX ((Snapshot $upgrade) -ceq $before)
    $again=Install $source $upgrade; Check U_IDEMPOTENT ($again.Code -eq 0 -and $again.Output -match '(?m)^NO_CHANGES\s*$')
    $fresh=Join-Path $run 'fresh'; [IO.Directory]::CreateDirectory($fresh) | Out-Null; & git -C $fresh init --quiet
    $freshResult=Install $source $fresh
    Push-Location $fresh
    try { $agents=((& opencode debug agents 2>$null | Out-String) | ConvertFrom-Json -Depth 100) }
    finally { Pop-Location }
    $effective=@($agents | Where-Object id -eq 'helios')
    Check F_FRESH ($freshResult.Code -eq 0 -and @($effective | Where-Object { $_.model.id -eq 'gpt-6-sol' -and $_.model.variant -eq 'high' -and $_.mode -eq 'subagent' }).Count -eq 1 -and @($agents | Where-Object id -eq 'sorin').Count -eq 0)
    Check F_EFFECTIVE_DENY ($effective.Count -eq 1 -and @('shell','edit','subagent','read','glob','grep','list','lsp' | Where-Object { $action=$_; @($effective[0].permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq 'deny' }).Count -lt 1 -or @($effective[0].permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq 'allow' }).Count -gt 0 }).Count -eq 0)
    Check F_ROSTER (@($expected.Keys | Where-Object { $id=$_; $want=$expected[$id].Split('#'); @($agents | Where-Object { $_.id -eq $id -and $_.model.id -eq $want[0] -and $_.model.variant -eq $want[1] }).Count -ne 1 }).Count -eq 0)
    $drift=Join-Path $run 'drift'; [IO.Directory]::CreateDirectory($drift) | Out-Null; & git -C $drift init --quiet
    Check D_BASE ((Install $old $drift).Code -eq 0)
    [IO.File]::AppendAllText((Join-Path $drift '.opencode/agents/kael.md'),"`n# user drift`n")
    $blocked=Install $source $drift
    Check D_REFUSED ($blocked.Code -ne 0 -and $blocked.Output -match 'MANAGED_FILE_DRIFT' -and -not (Test-Path (Join-Path $drift '.opencode/agents/helios.md')))
    $foreign=Join-Path $run 'foreign'; [IO.Directory]::CreateDirectory((Join-Path $foreign '.opencode/agents')) | Out-Null; & git -C $foreign init --quiet
    [IO.File]::WriteAllText((Join-Path $foreign '.opencode/agents/helios.md'),"user-owned helios`n")
    $conflict=Install $source $foreign
    Check D_UNOWNED_REFUSED ($conflict.Code -ne 0 -and $conflict.Output -match 'INSTALL_CONFLICT')
    Write-Output 'HELIOS QUALIFICATION: PASS'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'HELIOS QUALIFICATION: FAIL'
    exit 1
} finally {
    if (Test-Path -LiteralPath $old) { & git -C $source worktree remove --force $old 2>$null | Out-Null }
    if (Test-Path -LiteralPath $run) {
        try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop }
        catch { Write-Output "CLEANUP_DEFERRED: $run" }
    }
}
