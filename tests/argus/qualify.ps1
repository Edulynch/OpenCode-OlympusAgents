[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$production = '63357c4e8394a0646acb80e8725b576a12c91e62'
$run = Join-Path (Join-Path $env:LOCALAPPDATA 'Temp/opencode') ('argus-qualification-' + [guid]::NewGuid().ToString('N'))
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
function Simulate([string]$case, [string]$worker = 'TERMINAL') {
    # Offline policy simulation only; never interpreted as a live agent trace.
    $eligible = $case -in @('one-round','second-round','fourth','uncertain','indeterminate')
    $sessions = if ($eligible) { 1 } else { 0 }
    $calls = $sessions; $status = 'NORMAL_PATH'; $workerParent = ''
    if ($eligible) {
        $workerParent = 'kael'
        if ($worker -eq 'INDETERMINATE') { $status = 'COMPLETION_UNCONFIRMED' }
        else {
            $calls = if ($case -in @('second-round','fourth','uncertain')) { 3 } else { 2 }
            $status = switch ($case) {
                'fourth' { 'FOURTH_DENIED' }
                'uncertain' { 'INCONCLUSIVE' }
                default { 'BUG_DIAGNOSIS' }
            }
        }
    } else {
        $status = switch ($case) {
            'trivial' { 'TRIVIAL_BYPASS' }
            'security' { 'SECURITY_BUG' }
            'operational' { 'OPERATIONAL_ISSUE' }
            'gap' { 'GAP_FEATURE' }
            'optimization' { 'OPTIMIZATION' }
            default { throw "unknown case: $case" }
        }
    }
    [pscustomobject]@{ Status=$status; Sessions=$sessions; Consultations=$calls; WorkerParent=$workerParent; SessionID=if ($eligible) { 'argus-1' } else { '' } }
}
try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $a = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/argus.md'))
    $k = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/kael.md'))
    $b = [IO.File]::ReadAllText((Join-Path $source 'scripts/bootstrap.ps1'))
    $r = [IO.File]::ReadAllText((Join-Path $source 'docs/ROADMAP.md'))
    Check AR1 ($a -match '(?m)^# 🐞 Argus The Bug Hunter\r?$' -and $a -match 'mode: subagent' -and $b -match '".opencode/agents/argus.md"')
    Check AR2 ($a -match 'model: openai/gpt-6.1-sol#high')
    Check AR3 ($k -match '(?s)action: subagent\s+resource: argus\s+effect: allow' -and $k -match 'atlas, argus, talos, and helios are valid child role IDs')
    foreach ($pair in @(@('AR4','shell'),@('AR5','edit'),@('AR6','subagent'))) { Check $pair[0] ($a -match ('(?s)action: ' + $pair[1] + '\s+resource: "\*"\s+effect: deny')) }
    Check AR7 (@('read','glob','grep','list','lsp' | Where-Object { $a -notmatch ('(?s)action: ' + $_ + '\s+resource: "\*"\s+effect: deny') }).Count -eq 0)
    Check AR8 ($k -match '## Functional Bug Routing Gate' -and $k -match 'FUNCTIONAL_CAUSE_UNKNOWN' -and $k -match 'MULTIPLE_PLAUSIBLE_CAUSES' -and $k -match 'FIX_DIRECTION_AMBIGUOUS')
    Check AR9 ($k -match 'ARGUS COUNT = 0' -and $a -match 'ARGUS COUNT = 0')
    Check AR10 ($k -match 'SECURITY_BUG.*not Argus' -and $a -match 'CLASSIFICATION: SECURITY_BUG')
    Check AR11 ($k -match 'OPERATIONAL_ISSUE.*NOT ARGUS BY DEFAULT' -and $a -match 'OPERATIONAL_ISSUE.*NOT ARGUS BY DEFAULT')
    Check AR12 ($k -match 'GAP / FEATURE.*NOT BUG' -and $a -match 'GAP / FEATURE.*NOT BUG')
    Check AR13 ($k -match 'OPTIMIZATION.*NOT BUG' -and $a -match 'OPTIMIZATION.*NOT BUG')
    Check AR14 ($k -match 'Thales handles HIGH-UNCERTAINTY TECHNICAL ESCALATION' -and $a -match 'Argus never invokes Thales')
    Check AR15 ($k -match 'Diagnose before Atlas' -and $a -match 'Atlas orders execution')
    Check AR16 ($k -match 'Kovan implements the supported fix' -and $a -match 'Kovan implements')
    Check AR17 ($k -match 'Veyra owns repository/file/contract evidence and Nox owns runtime/test evidence' -and $a -match 'Veyra owns repository/file/contract evidence')
    Check AR18 (@('STATUS: BUG_DIAGNOSIS','CLASSIFICATION: FUNCTIONAL_BUG','OBSERVED:','EXPECTED:','CAUSE:','EVIDENCE:','FIX_DIRECTION:','VALIDATION:','CONFIDENCE:','STOP_CONDITIONS:' | Where-Object { -not $a.Contains($_) }).Count -eq 0)
    Check AR19 (@('STATUS: EVIDENCE_REQUEST','TARGET_ROLE: veyra | nox','QUESTION:','SCOPE:','WHY_NEEDED:','EXPECTED_DISCRIMINATION:' | Where-Object { -not $a.Contains($_) }).Count -eq 0)
    Check AR20 ($k -match 'Kael → Argus → EVIDENCE_REQUEST → Kael → Veyra or Nox → evidence → Kael → SAME Argus session' -and $a -match 'Kael → Argus → EVIDENCE_REQUEST')
    Check AR21 ($k -match 'SAME Argus session' -and $a -match 'SAME Argus session')
    Check AR22 ($k -match 'up to 2 consultations total' -and $a -match 'up to 2 consultations total')
    Check AR23 ($k -match 'SECOND discriminating evidence round' -and $a -match 'SECOND discriminating evidence round')
    Check AR24 ($k -match 'Fourth automatic consultation DENIED' -and $a -match 'Automatic consultation #4 DENIED')
    Check AR25 ($k -match 'NO_PROGRESS:' -and $a -match 'NO_PROGRESS')
    Check AR26 ($k -match 'MISSING OUTPUT != WORKER FAILURE' -and $k -match 'COMPLETION_UNCONFIRMED' -and $k -match 'never launch replacement')
    Check AR27 ($k -match 'Issue #2 Aegis handoff remain unchanged' -and $k -match 'MAINTENANCE_RESULT_PENDING')
    Check AR28 ($a -match 'Kael → Aegis DENIED' -and $k -match 'Kael → Aegis remains DENIED' -and $k -match 'user → /maintain explicit only')
    Check AR29 ($k -match 'BUG_DIAGNOSIS means diagnosis only' -and $a -match 'Kael owns final completion')
    $expected = @{ kael='gpt-6.1-sol#high'; atlas='gpt-6.1-sol#high'; argus='gpt-6.1-sol#high'; thales='gpt-6.1-sol#xhigh'; helios='gpt-6.1-sol#high'; aegis='gpt-6-luna#max'; veyra='gpt-6-luna#max'; orin='gpt-6-luna#max'; kovan='gpt-6-luna#max'; nox='gpt-6-luna#max'; vera='gpt-6-luna#max' }
    Check AR30 (@($expected.Keys | Where-Object { ([IO.File]::ReadAllText((Join-Path $source ".opencode/agents/$_.md"))) -notmatch ('(?m)^model: "?openai/' + [regex]::Escape($expected[$_]) + '"?\r?$') }).Count -eq 0)
    Check AR31 ($k -match 'MAX_ACTIVE_CHILDREN = 4' -and $k -match 'fan out up to four useful children')
    Check AR32 (-not (Test-Path (Join-Path $source '.opencode/agents/sorin.md')) -and $b -match '\$OldReasoner = ''.opencode/agents/sorin.md''')
    Check AR33 ((& git -C $source grep -n -i 'gpt-6-luna#fast' -- '.opencode/agents' 'opencode.jsonc' | Out-String).Length -eq 0)
    Check AR_ROADMAP ($r -match '6 — Argus The Bug Hunter \| \*\*SHIPPED\*\*' -and $r -match 'USER_EXECUTED_LIVE_EVIDENCE' -and $r -match 'INFRA_OR_TEST_INSTRUCTION_BLOCKED' -and @('3 — Role Purity + Iterative Evidence','4 — Thales evolution','5 — Atlas The Planner' | Where-Object { $r -notmatch ([regex]::Escape($_) + ' \| \*\*SHIPPED\*\*') }).Count -eq 0)

    $caseA = Simulate one-round; $caseB = Simulate second-round; $caseC = Simulate fourth
    Check CASE_A ($caseA.Status -eq 'BUG_DIAGNOSIS' -and $caseA.Sessions -eq 1 -and $caseA.Consultations -eq 2 -and $caseA.WorkerParent -eq 'kael')
    Check CASE_B ($caseB.Status -eq 'BUG_DIAGNOSIS' -and $caseB.Sessions -eq 1 -and $caseB.Consultations -eq 3 -and $caseB.SessionID -eq $caseA.SessionID)
    Check CASE_C ($caseC.Status -eq 'FOURTH_DENIED' -and $caseC.Consultations -eq 3)
    foreach ($pair in @(@('D','trivial','TRIVIAL_BYPASS'),@('E','security','SECURITY_BUG'),@('F','operational','OPERATIONAL_ISSUE'),@('G','gap','GAP_FEATURE'),@('H','optimization','OPTIMIZATION'))) {
        $result = Simulate $pair[1]
        Check ('CASE_' + $pair[0]) ($result.Status -eq $pair[2] -and $result.Sessions -eq 0 -and $result.Consultations -eq 0)
    }
    $caseI = Simulate uncertain; Check CASE_I ($caseI.Status -eq 'INCONCLUSIVE' -and $caseI.Consultations -eq 3 -and $k -match 'existing Diagnostic Gate')
    $caseJ = Simulate indeterminate INDETERMINATE; Check CASE_J ($caseJ.Status -eq 'COMPLETION_UNCONFIRMED' -and $caseJ.Consultations -eq 1 -and $caseJ.WorkerParent -eq 'kael')

    & git -C $source worktree add --detach $old $production | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'production worktree fixture failed' }
    $upgrade = Join-Path $run 'upgrade'
    [IO.Directory]::CreateDirectory($upgrade) | Out-Null
    & git -C $upgrade init --quiet
    foreach ($path in @('src/local.txt','docs/staged.txt')) {
        $dest = Join-Path $upgrade $path; [IO.Directory]::CreateDirectory((Split-Path $dest -Parent)) | Out-Null
        [IO.File]::WriteAllText($dest,"original $path`n")
    }
    & git -C $upgrade add -- src docs
    & git -C $upgrade -c user.name=Qualification -c user.email=qualification@example.invalid commit --quiet -m fixture
    $initial = Install $old $upgrade
    Check U_BASE ($initial.Code -eq 0 -and -not (Test-Path (Join-Path $upgrade '.opencode/agents/argus.md')))
    [IO.File]::WriteAllText((Join-Path $upgrade 'src/local.txt'),"modified work`n")
    [IO.File]::WriteAllText((Join-Path $upgrade 'docs/staged.txt'),"staged work`n")
    & git -C $upgrade add -- docs/staged.txt
    foreach ($path in @('notes.txt','.serena/project.yml','.opencode/user-note.txt')) {
        $dest = Join-Path $upgrade $path; [IO.Directory]::CreateDirectory((Split-Path $dest -Parent)) | Out-Null
        [IO.File]::WriteAllText($dest,"user owned $path`n")
    }
    $before = Snapshot $upgrade
    $dry = Install $source $upgrade -DryRun
    Check U_DRY ($dry.Code -eq 0 -and $dry.Output -match '\.opencode/agents/argus.md' -and -not (Test-Path (Join-Path $upgrade '.opencode/agents/argus.md')))
    $installed = Install $source $upgrade
    if ($installed.Code -ne 0) { Write-Output $installed.Output }
    $manifest = [IO.File]::ReadAllText((Join-Path $upgrade '.opencode/orchestrator-install.json')) | ConvertFrom-Json
    Check U_UPGRADE ($installed.Code -eq 0 -and (Test-Path (Join-Path $upgrade '.opencode/agents/argus.md')) -and @($manifest.managed_files | Where-Object path -eq '.opencode/agents/argus.md').Count -eq 1)
    Check U_USER_INDEX ((Snapshot $upgrade) -ceq $before)
    $again = Install $source $upgrade
    Check U_IDEMPOTENT ($again.Code -eq 0 -and $again.Output -match '(?m)^NO_CHANGES\s*$')
    $fresh = Join-Path $run 'fresh'; [IO.Directory]::CreateDirectory($fresh) | Out-Null; & git -C $fresh init --quiet
    $freshResult = Install $source $fresh
    Push-Location $fresh
    try { $agents = ((& opencode debug agents 2>$null | Out-String) | ConvertFrom-Json -Depth 100) }
    finally { Pop-Location }
    $effectiveArgus = @($agents | Where-Object id -eq 'argus')
    Check F_FRESH ($freshResult.Code -eq 0 -and @($effectiveArgus | Where-Object { $_.model.id -eq 'gpt-6.1-sol' -and $_.model.variant -eq 'high' -and $_.mode -eq 'subagent' }).Count -eq 1 -and @($agents | Where-Object id -eq 'sorin').Count -eq 0)
    Check F_EFFECTIVE_DENY ($effectiveArgus.Count -eq 1 -and @('shell','edit','subagent','read','glob','grep','list','lsp' | Where-Object { $action = $_; @($effectiveArgus[0].permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq 'deny' }).Count -lt 1 -or @($effectiveArgus[0].permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq 'allow' }).Count -gt 0 }).Count -eq 0)
    Check F_ROSTER (@($expected.Keys | Where-Object { $id = $_; $want = $expected[$id].Split('#'); @($agents | Where-Object { $_.id -eq $id -and $_.model.id -eq $want[0] -and $_.model.variant -eq $want[1] }).Count -ne 1 }).Count -eq 0)
    $drift = Join-Path $run 'drift'; [IO.Directory]::CreateDirectory($drift) | Out-Null; & git -C $drift init --quiet
    Check D_BASE ((Install $old $drift).Code -eq 0)
    [IO.File]::AppendAllText((Join-Path $drift '.opencode/agents/kael.md'),"`n# user drift`n")
    $blocked = Install $source $drift
    Check D_REFUSED ($blocked.Code -ne 0 -and $blocked.Output -match 'MANAGED_FILE_DRIFT' -and -not (Test-Path (Join-Path $drift '.opencode/agents/argus.md')))
    $foreign = Join-Path $run 'foreign'; [IO.Directory]::CreateDirectory((Join-Path $foreign '.opencode/agents')) | Out-Null; & git -C $foreign init --quiet
    [IO.File]::WriteAllText((Join-Path $foreign '.opencode/agents/argus.md'),"user-owned argus`n")
    $conflict = Install $source $foreign
    Check D_UNOWNED_REFUSED ($conflict.Code -ne 0 -and $conflict.Output -match 'INSTALL_CONFLICT')
    Write-Output 'ARGUS QUALIFICATION: PASS'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'ARGUS QUALIFICATION: FAIL'
    exit 1
} finally {
    if (Test-Path -LiteralPath $old) { & git -C $source worktree remove --force $old 2>$null | Out-Null }
    if (Test-Path -LiteralPath $run) {
        try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop }
        catch { Write-Output "CLEANUP_DEFERRED: $run" }
    }
}
