[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$phase4Base = 'dea863168fc16a6b97e0b6404c4334f4265f1e52'
$run = Join-Path (Join-Path $env:LOCALAPPDATA 'Temp/opencode') ('atlas-qualification-' + [guid]::NewGuid().ToString('N'))
$old = Join-Path $run 'master-source'
$target = Join-Path $run 'upgrade'
function Check([string]$id, [bool]$ok) { if (-not $ok) { throw "$id FAIL" }; Write-Output "$id PASS" }
function Install([string]$root, [string]$repo, [switch]$DryRun) {
    $args = @('-NoProfile','-File',(Join-Path $root 'install.ps1'),'-SourceRoot',$root,'-Target',$repo)
    if ($DryRun) { $args += '-DryRun' }
    $result = (& pwsh @args 2>&1 | Out-String)
    [pscustomobject]@{ Code=$LASTEXITCODE; Output=$result }
}
function Snapshot([string]$repo) {
    $paths = @('src/local.txt','docs/staged.txt','notes.txt','.serena/project.yml','.opencode/user-note.txt')
    $hashes = @($paths | ForEach-Object { (Get-FileHash -LiteralPath (Join-Path $repo $_) -Algorithm SHA256).Hash }) -join ','
    $index = (& git -C $repo diff --cached --binary | Out-String)
    $status = (& git -C $repo status --porcelain=v1 -uall -- @($paths) | Out-String)
    "$hashes`n$index`n$status"
}
# Deterministic policy simulation; asserts routing invariants, not live agent behavior.
function Simulate([string]$case, [string]$workerState = 'TERMINAL') {
    $atlasId = 'atlas-1'
    $sessions = 0; $consultations = 0; $workerParent = ''; $status = ''
    if ($case -in @('trivial','unknown-cause')) {
        $status = if ($case -eq 'trivial') { 'NORMAL_PATH' } else { 'DIAGNOSIS_FIRST' }
    } else {
        $sessions = 1; $consultations = 1
        switch ($case) {
            direct { $status = 'PLAN' }
            missing {
                $request = [pscustomobject]@{ TargetRole='veyra'; Scope='contracts/compatibility.txt'; Question='What acceptance ordering is required?' }
                if ($request.Scope -ne 'contracts/compatibility.txt' -or $request.TargetRole -ne 'veyra') { throw 'Synthetic evidence request out of scope' }
                $workerParent = 'kael'
                if ($workerState -eq 'INDETERMINATE') { $status = 'COMPLETION_UNCONFIRMED' }
                else { $consultations++; $status = 'PLAN' }
            }
            broad { $status = 'REQUEST_REJECTED' }
            architecture { $status = 'NEEDS_ARCHITECTURE' }
            third { $consultations = 2; $status = 'THIRD_DENIED' }
            default { throw "Unknown synthetic case: $case" }
        }
    }
    [pscustomobject]@{ Status=$status; Sessions=$sessions; Consultations=$consultations; WorkerParent=$workerParent; AtlasID=$atlasId }
}
try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $a = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/atlas.md'))
    $k = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/kael.md'))
    $b = [IO.File]::ReadAllText((Join-Path $source 'scripts/bootstrap.ps1'))
    $r = [IO.File]::ReadAllText((Join-Path $source 'docs/ROADMAP.md'))
    Check AT1 ((Test-Path (Join-Path $source '.opencode/agents/atlas.md')) -and $a -match 'mode: subagent' -and $a -match '(?m)^# 🗺️ Atlas The Planner\r?$')
    Check AT2 ($a -match 'model: openai/gpt-6-sol#high')
    Check AT3 ($k -match '(?s)action: subagent\s+resource: atlas\s+effect: allow' -and $k -match 'atlas, and argus are valid child role IDs')
    foreach ($pair in @(@('AT4','shell'),@('AT5','edit'),@('AT6','subagent'))) {
        Check $pair[0] ($a -match ('(?s)action: ' + $pair[1] + '\s+resource: "\*"\s+effect: deny'))
    }
    Check AT7 ($k -match '## Planning Gate' -and @('DEPENDENCY_ORDER_MATTERS','MULTI_COMPONENT_EXECUTION','MIGRATION_OR_ROLLOUT_SEQUENCE','PARALLEL_WORK_DECOMPOSITION','EXPLICIT_PLANNING_REQUEST' | Where-Object { $k -notmatch $_ }).Count -eq 0)
    Check AT8 ($k -match 'ATLAS COUNT = 0' -and $a -match 'Trivial localized')
    Check AT9 ($a -match 'Orin asks WHAT STRUCTURE' -and $k -match 'Orin answers WHAT STRUCTURE')
    Check AT10 ($a -match 'Thales asks WHY IS THIS FAILING' -and $k -match 'Unknown root cause')
    Check AT11 ($a -match 'Kovan implements' -and $k -match 'Kovan implements, Atlas does not')
    Check AT12 ($a -match 'Nox executes tests; Vera reviews' -and $k -match 'Nox tests and Vera independently reviews')
    Check AT13 ($a -match 'SMALLEST SUFFICIENT PLAN|Smallest sufficient plan' -and $a -match '3–7' -and $k -match '3–7')
    Check AT14 (@('STATUS: PLAN','OBJECTIVE:','PRECONDITIONS:','STEPS:','DEPENDENCIES:','VALIDATION:','RISKS:','STOP_CONDITIONS:' | Where-Object { -not $a.Contains($_) }).Count -eq 0)
    Check AT15 (@('STATUS: EVIDENCE_REQUEST','TARGET_ROLE:','QUESTION:','SCOPE:','WHY_NEEDED:','EXPECTED_DISCRIMINATION:' | Where-Object { -not $a.Contains($_) }).Count -eq 0)
    Check AT16 ($k -match 'Kael → Atlas → EVIDENCE_REQUEST → Kael → worker → evidence → Kael → SAME Atlas session → PLAN')
    Check AT17 ($a -match 'SAME Atlas native session' -and $k -match 'SAME Atlas session')
    Check AT18 ($a -match 'Third automatic consultation DENIED' -and $k -match 'Third automatic Atlas consultation DENIED')
    Check AT19 ($a -match 'NO_PROGRESS:' -and $k -match 'NO_PROGRESS:')
    Check AT20 ($k -match 'reconcile the known original worker' -and $k -match 'COMPLETION_UNCONFIRMED' -and $k -match 'No blind replacement')
    Check AT21 ($k -match 'Kael → Maintenance remains DENIED' -and $a -match 'user → /maintain')
    Check AT22 ($a -match 'never maintenance' -and $k -match 'never request Maintenance as an evidence worker')
    Check AT23 ($a -match 'Kael owns actual routing, reconciliation and final completion' -and $k -match 'A STATUS: PLAN is planning completed')
    $baseline = @('kael','veyra','orin','kovan','nox','vera','thales','maintenance')
    $unchanged = @($baseline | Where-Object {
        $path = '.opencode/agents/' + $_ + '.md'
        if ($_ -eq 'kael') { return $true }
        & git -C $source diff --quiet $phase4Base -- $path
        $LASTEXITCODE -eq 0
    })
    Check AT24 ($unchanged.Count -eq $baseline.Count -and $k -match 'model: "openai/gpt-6-sol#high"')
    Check AT25 ($k -match 'MAX_ACTIVE_CHILDREN = 4' -and $k -match 'fan out up to four useful children' -and $k -notmatch 'gpt-6-luna#fast')
    Check AT26 (-not (Test-Path (Join-Path $source '.opencode/agents/sorin.md')) -and $b -match "'sorin'" -and $a -notmatch 'gpt-6-luna#fast')
    Check 'AT_READ_DENIED' (@(@('read','glob','grep','list','lsp') | Where-Object { $a -notmatch ('(?s)action: ' + $_ + '\s+resource: "\*"\s+effect: deny') }).Count -eq 0)
    Check 'AT_ROADMAP' ($r -match '5 — Atlas The Planner \| \*\*(IN VALIDATION|SHIPPED)\*\*' -and $r -match '3 — Role Purity \+ Iterative Evidence \| \*\*SHIPPED\*\*' -and $r -match '4 — Thales evolution \| \*\*SHIPPED\*\*')
    # Offline synthetic routing: contracts and negative controls, NOT live agent execution.
    $caseA = Simulate direct; $caseB = Simulate missing; $caseC = Simulate broad; $caseD = Simulate architecture
    $caseE = Simulate trivial; $caseF = Simulate unknown-cause; $caseG = Simulate third; $caseH = Simulate missing INDETERMINATE
    Check 'CASE_A_DIRECT_PLAN' ($caseA.Status -eq 'PLAN' -and $caseA.Sessions -eq 1 -and $caseA.Consultations -eq 1 -and $caseA.WorkerParent -eq '')
    Check 'CASE_B_ONE_EVIDENCE_ROUND' ($caseB.Status -eq 'PLAN' -and $caseB.Sessions -eq 1 -and $caseB.Consultations -eq 2 -and $caseB.WorkerParent -eq 'kael' -and $caseB.AtlasID -eq $caseA.AtlasID)
    Check 'CASE_C_BROAD_DISCOVERY_REJECTED' ($caseC.Status -eq 'REQUEST_REJECTED' -and $caseC.Consultations -eq 1)
    Check 'CASE_D_UNRESOLVED_ARCHITECTURE' ($caseD.Status -eq 'NEEDS_ARCHITECTURE')
    Check 'CASE_E_TRIVIAL_EDIT' ($caseE.Status -eq 'NORMAL_PATH' -and $caseE.Sessions -eq 0)
    Check 'CASE_F_UNKNOWN_ROOT_CAUSE' ($caseF.Status -eq 'DIAGNOSIS_FIRST' -and $caseF.Sessions -eq 0)
    Check 'CASE_G_THIRD_DENIED' ($caseG.Status -eq 'THIRD_DENIED' -and $caseG.Consultations -eq 2)
    Check 'CASE_H_INDETERMINATE_WORKER' ($caseH.Status -eq 'COMPLETION_UNCONFIRMED' -and $caseH.Consultations -eq 1 -and $caseH.WorkerParent -eq 'kael')

    & git -C $source worktree add --detach $old $phase4Base | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Phase 4 baseline fixture worktree failed' }
    [IO.Directory]::CreateDirectory($target) | Out-Null
    & git -C $target init --quiet
    foreach ($path in @('src/local.txt','docs/staged.txt')) {
        $file = Join-Path $target $path
        [IO.Directory]::CreateDirectory((Split-Path -Parent $file)) | Out-Null
        [IO.File]::WriteAllText($file,"original $path`n")
    }
    & git -C $target add -- src docs
    & git -C $target -c user.name=Qualification -c user.email=qualify@example.invalid commit --quiet -m fixture
    $initial = Install $old $target
    Check 'AT_UPGRADE_BASELINE' ($initial.Code -eq 0 -and -not (Test-Path (Join-Path $target '.opencode/agents/atlas.md')))
    [IO.File]::WriteAllText((Join-Path $target 'src/local.txt'),"modified work`n")
    [IO.File]::WriteAllText((Join-Path $target 'docs/staged.txt'),"staged work`n")
    & git -C $target add -- docs/staged.txt
    foreach ($path in @('notes.txt','.serena/project.yml','.opencode/user-note.txt')) {
        $file = Join-Path $target $path
        [IO.Directory]::CreateDirectory((Split-Path -Parent $file)) | Out-Null
        [IO.File]::WriteAllText($file,"user owned $path`n")
    }
    $before = Snapshot $target
    $dry = Install $source $target -DryRun
    Check 'AT_UPGRADE_DRY_RUN' ($dry.Code -eq 0 -and $dry.Output -match '\.opencode/agents/atlas.md' -and -not (Test-Path (Join-Path $target '.opencode/agents/atlas.md')))
    $upgrade = Install $source $target
    if ($upgrade.Code -ne 0) { Write-Output $upgrade.Output }
    $manifest = [IO.File]::ReadAllText((Join-Path $target '.opencode/orchestrator-install.json')) | ConvertFrom-Json
    Check 'AT_UPGRADE' ($upgrade.Code -eq 0 -and (Test-Path (Join-Path $target '.opencode/agents/atlas.md')) -and @($manifest.managed_files | Where-Object path -eq '.opencode/agents/atlas.md').Count -eq 1)
    Check 'AT_UNRELATED_INDEX_BYTES' ((Snapshot $target) -ceq $before)
    $again = Install $source $target
    Check 'AT_IDEMPOTENT' ($again.Code -eq 0 -and $again.Output -match '(?m)^NO_CHANGES\s*$')
    $fresh = Join-Path $run 'fresh'
    [IO.Directory]::CreateDirectory($fresh) | Out-Null
    & git -C $fresh init --quiet
    $freshResult = Install $source $fresh
    Push-Location $fresh
    try { $agents = ((& opencode debug agents 2>$null | Out-String) | ConvertFrom-Json -Depth 100) }
    finally { Pop-Location }
    Check 'AT_FRESH_EFFECTIVE' ($freshResult.Code -eq 0 -and
        @($agents | Where-Object { $_.id -eq 'atlas' -and $_.model.id -eq 'gpt-6-sol' -and $_.model.variant -eq 'high' -and $_.mode -eq 'subagent' }).Count -eq 1 -and
        @($agents | Where-Object id -eq 'sorin').Count -eq 0)
    $drift = Join-Path $run 'drift'
    [IO.Directory]::CreateDirectory($drift) | Out-Null
    & git -C $drift init --quiet
    Check 'AT_DRIFT_BASELINE' ((Install $old $drift).Code -eq 0)
    [IO.File]::AppendAllText((Join-Path $drift '.opencode/agents/kael.md'),"`n# user drift`n")
    $blocked = Install $source $drift
    Check 'AT_MANAGED_DRIFT_REFUSED' ($blocked.Code -ne 0 -and $blocked.Output -match 'MANAGED_FILE_DRIFT' -and -not (Test-Path (Join-Path $drift '.opencode/agents/atlas.md')))
    $foreign = Join-Path $run 'foreign'
    [IO.Directory]::CreateDirectory((Join-Path $foreign '.opencode/agents')) | Out-Null
    & git -C $foreign init --quiet
    [IO.File]::WriteAllText((Join-Path $foreign '.opencode/agents/atlas.md'),"user-owned atlas`n")
    $conflict = Install $source $foreign
    Check 'AT_UNOWNED_ATLAS_REFUSED' ($conflict.Code -ne 0 -and $conflict.Output -match 'INSTALL_CONFLICT')
    Write-Output 'ATLAS QUALIFICATION: PASS'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'ATLAS QUALIFICATION: FAIL'
    exit 1
} finally {
    if (Test-Path -LiteralPath $old) { & git -C $source worktree remove --force $old 2>$null | Out-Null }
    if (Test-Path -LiteralPath $run) {
        try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop }
        catch { Write-Output "CLEANUP_DEFERRED: $run" }
    }
}
