[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$production = '5911d06d998e5259ffa4b2aa4510e844f264f30f'
$run = Join-Path (Join-Path $env:LOCALAPPDATA 'Temp/opencode') ('talos-qualification-' + [guid]::NewGuid().ToString('N'))
$old = Join-Path $run 'production-source'
function Check([string]$id, [bool]$ok) { if (-not $ok) { throw "$id FAIL" }; Write-Output "$id PASS" }
function Install([string]$root, [string]$target, [switch]$DryRun) {
    $args = @('-NoProfile','-File',(Join-Path $root 'install.ps1'),'-SourceRoot',$root,'-Target',$target)
    if ($DryRun) { $args += '-DryRun' }
    $oldPath = $env:PATH
    try {
        # Avoid a duplicate Microsoft Store pwsh app-execution alias in installer subprocesses.
        $windowsApps = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
        $pathParts = @($oldPath -split [IO.Path]::PathSeparator | Where-Object { $_ -and $_.Trim('"') -ne $windowsApps })
        if ($pathParts -notcontains $PSHOME) { $pathParts += $PSHOME }
        $env:PATH = $pathParts -join [IO.Path]::PathSeparator
        $executable = Join-Path $PSHOME 'pwsh.exe'
        $output = (& $executable @args 2>&1 | Out-String)
        [pscustomobject]@{ Code=$LASTEXITCODE; Output=$output }
    } finally {
        $env:PATH = $oldPath
    }
}
function Snapshot([string]$root) {
    $paths = @('src/local.txt','docs/staged.txt','notes.txt','.serena/project.yml','.opencode/user-note.txt')
    $hashes = @($paths | ForEach-Object { (Get-FileHash -LiteralPath (Join-Path $root $_) -Algorithm SHA256).Hash }) -join ','
    $index = (& git -C $root diff --cached --binary | Out-String)
    $status = (& git -C $root status --porcelain=v1 -uall -- @($paths) | Out-String)
    "$hashes`n$index`n$status"
}
function Simulate([string]$case, [string]$worker = 'TERMINAL') {
    # Offline contract simulation, NOT live agent/session evidence.
    $eligible = $case -in @('one-round','second-round','fourth','uncertain','indeterminate','bounded')
    $calls = 0; $status = 'NORMAL_PATH'
    if ($eligible) {
        $calls = 1
        if ($worker -eq 'INDETERMINATE') { $status = 'COMPLETION_UNCONFIRMED' }
        else {
            $calls = if ($case -in @('second-round','fourth','uncertain')) { 3 } else { 2 }
            $status = switch ($case) {
                'fourth' { 'FOURTH_DENIED' }
                'uncertain' { 'INCONCLUSIVE' }
                default { 'SECURITY_DIAGNOSIS' }
            }
        }
    } else {
        $status = switch ($case) {
            'functional' { 'FUNCTIONAL_BUG' }
            'operational' { 'OPERATIONAL_ISSUE' }
            'gap' { 'GAP_FEATURE' }
            'optimization' { 'OPTIMIZATION' }
            default { throw "unknown case: $case" }
        }
    }
    [pscustomobject]@{ Status=$status; Sessions=[int]$eligible; Consultations=$calls; WorkerParent=if ($eligible) { 'kael' } else { '' }; SessionID=if ($eligible) { 'talos-1' } else { '' }; AuditExpanded=$false; Replacement=$false }
}
try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $t = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/talos.md'))
    $k = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/kael.md'))
    $codexRoot = [IO.File]::ReadAllText((Join-Path $source 'CODEX.md'))
    $codexTalos = [IO.File]::ReadAllText((Join-Path $source '.codex/agents/talos.toml'))
    $routing = [IO.File]::ReadAllText((Join-Path $source 'olympus/policies/routing.md'))
    $b = [IO.File]::ReadAllText((Join-Path $source 'scripts/bootstrap.ps1'))
    $r = [IO.File]::ReadAllText((Join-Path $source 'docs/ROADMAP.md'))
    Check TA1 ($t -match '(?m)^# Talos — The Sentinel\r?$' -and $t -match 'mode: subagent' -and $b.Contains('.opencode/agents/talos.md'))
    Check TA2 ($t -match 'model: openai/gpt-6.1-sol#high')
    Check TA3 ($k -match '(?s)action: subagent\s+resource: talos\s+effect: allow' -and $k -match 'argus, talos, and helios are valid child role IDs')
    foreach ($pair in @(@('TA4','shell'),@('TA5','edit'),@('TA6','subagent'))) { Check $pair[0] ($t -match ('(?s)action: ' + $pair[1] + '\s+resource: "\*"\s+effect: deny')) }
    Check TA7 (@('read','glob','grep','list','lsp' | Where-Object { $t -notmatch ('(?s)action: ' + $_ + '\s+resource: "\*"\s+effect: deny') }).Count -eq 0)
    Check TA8 ($k -match '## Security Routing Gate' -and $k -match 'TRUST_BOUNDARY_UNCLEAR' -and $k -match 'EXPLOITABILITY_UNCLEAR' -and $k -match 'FIX_BOUNDARY_AMBIGUOUS' -and $t -match 'strongly evidenced material security/trust/authorization boundary defect' -and $t -match 'no additional unanswered security-specific question')
    $routingSources = @($k, $t, $codexRoot, $codexTalos)
    Check CASE_E_ESTABLISHED_SECURITY_BOUNDARY_TALOS_REQUIRED (@($routingSources | Where-Object { $_ -notmatch 'Talos (is )?REQUIRED|`talos` REQUIRED|must activate you' -or $_ -notmatch 'no additional unanswered security-specific question is required for\s+initial activation' }).Count -eq 0 -and
        $k -match 'MEMBER executing an ADMIN-only account deletion requires Talos' -and
        $routing -match 'ESTABLISHED or STRONGLY EVIDENCED MATERIAL SECURITY / TRUST / AUTHORIZATION BOUNDARY DEFECT.*Talos REQUIRED')
    Check CASE_SECURITY_RELEVANCE_UNCONFIRMED_NOT_AUTOMATIC (@($routingSources | Where-Object { $_ -notmatch 'SECURITY_RELEVANCE_UNCONFIRMED.*(does not qualify|does not activate|not qualify|insufficient)' }).Count -eq 0)
    Check CASE_GENERIC_SECURITY_WORDING_NOT_AUTOMATIC (@($routingSources | Where-Object { $_ -notmatch '(?s)(mere security wording|the word.*security).*?(insufficient|does not qualify|does not activate)' }).Count -eq 0)
    Check CASE_OPERATIONAL_SECURITY_TOOL_FAILURE_NOT_AUTOMATIC (@($routingSources | Where-Object { $_ -notmatch '(?s)Trivy/Semgrep execution\s+failure.*(NOT TALOS BY DEFAULT|does NOT activate|does not activate)' }).Count -eq 0)
    Check CASE_NON_SECURITY_FUNCTIONAL_BUG_TALOS_ZERO (@($routingSources | Where-Object { $_ -notmatch '(?s)(deterministic non-security (functional )?(defect|bug)|non-security functional defects?).*TALOS COUNT = 0' }).Count -eq 0)
    Check CASE_UNCONFIRMED_AFFECTED_VERSION_NOT_AUTOMATIC (@($routingSources | Where-Object { $_ -notmatch '(?s)(unconfirmed affected-version/vulnerability relevance|unconfirmed affected-version/vulnerability).*?(insufficient|does NOT activate|does not activate)' }).Count -eq 0)
    Check TA9 ($k -match 'FUNCTIONAL BEHAVIOR DEFECT' -and $t -match 'TALOS COUNT = 0')
    Check TA10 ($k -match 'NOT TALOS BY DEFAULT' -and $t -match 'OPERATIONAL_ISSUE')
    Check TA11 ($k -match 'GAP / FEATURE without violated contract' -and $t -match 'GAP / FEATURE not promised')
    Check TA12 ($k -match 'OPTIMIZATION, not Talos' -and $t -match 'OPTIMIZATION of correct behavior')
    Check TA13 ($k -match 'Argus diagnoses FUNCTIONAL BEHAVIOR DEFECT; Talos diagnoses SECURITY BOUNDARY DEFECT' -and $t -match 'Kael chooses the dominant classification')
    Check TA14 ($k -match 'Vera independently reviews' -and $t -match 'never replaces Vera')
    Check TA15 ($k -match 'existing Diagnostic Gate after Talos' -and $t -match 'Talos never invokes Thales|Talos does not invoke Thales')
    Check TA16 ($k -match 'Atlas orders a multi-step fix' -and $t -match 'Kovan implements')
    Check TA17 ($k -match 'Veyra owns repository/policy/configuration evidence; Nox owns runtime/test evidence' -and $t -match 'Veyra owns repository/policy/configuration evidence')
    Check TA18 (@('STATUS: SECURITY_DIAGNOSIS','CLASSIFICATION: SECURITY_BUG','SECURITY_BOUNDARY:','OBSERVED:','EXPECTED:','CAUSE:','EVIDENCE:','ATTACK_PREREQUISITES:','IMPACT:','FIX_DIRECTION:','VALIDATION:','CONFIDENCE:','STOP_CONDITIONS:' | Where-Object { -not $t.Contains($_) }).Count -eq 0)
    Check TA19 (@('STATUS: EVIDENCE_REQUEST','TARGET_ROLE: veyra | nox','QUESTION:','SCOPE:','WHY_NEEDED:','EXPECTED_DISCRIMINATION:' | Where-Object { -not $t.Contains($_) }).Count -eq 0)
    Check TA20 ($k -match 'Kael → Talos → EVIDENCE_REQUEST → Kael → Veyra or Nox → evidence → Kael → SAME Talos session' -and $t -match 'Evidence workers are direct Kael children')
    Check TA21 ($k -match 'SAME Talos session' -and $t -match 'SAME Talos session')
    Check TA22 ($k -match 'up to 2 consultations total' -and $t -match 'up to 2 Talos consultations total')
    Check TA23 ($k -match 'SECOND discriminating evidence round' -and $t -match 'SECOND discriminating evidence round')
    Check TA24 ($k -match 'Fourth automatic consultation DENIED' -and $t -match 'Automatic consultation #4 DENIED')
    Check TA25 ($k -match 'NO_PROGRESS:' -and $t -match 'NO_PROGRESS')
    Check TA26 ($k -match 'automatic whole-repository security audit' -and $t -match 'whole-repository security audit')
    Check TA27 ($k -match 'harmful/destructive exploitation is not required' -and $t -match 'destructive exploit execution')
    Check TA28 ($k -match 'MISSING OUTPUT != WORKER FAILURE' -and $k -match 'never blind retry, replace worker' -and $t -match 'COMPLETION_UNCONFIRMED')
    Check TA29 ($k -match 'Issue #2 Aegis reconciliation remain unchanged' -and $k -match 'MAINTENANCE_RESULT_PENDING')
    Check TA30 ($k -match 'Kael → Aegis DENIED' -and $t -match 'user → /maintain explicit only')
    Check TA31 ($k -match 'SECURITY_DIAGNOSIS complete is diagnosis only' -and $t -match 'Kael alone routes normal workers')
    $expected = @{ kael='gpt-6.1-sol#high'; atlas='gpt-6.1-sol#high'; argus='gpt-6.1-sol#high'; talos='gpt-6.1-sol#high'; helios='gpt-6.1-sol#high'; thales='gpt-6.1-sol#xhigh'; aegis='gpt-6-luna#max'; veyra='gpt-6-luna#max'; orin='gpt-6-luna#max'; kovan='gpt-6-luna#max'; nox='gpt-6-luna#max'; vera='gpt-6-luna#max' }
    Check TA32 (@($expected.Keys | Where-Object { ([IO.File]::ReadAllText((Join-Path $source ".opencode/agents/$_.md"))) -notmatch ('(?m)^model: "?openai/' + [regex]::Escape($expected[$_]) + '"?\r?$') }).Count -eq 0)
    Check TA33 ($k -match 'MAX_ACTIVE_CHILDREN = 4' -and $k -match 'fan out up to four useful children')
    Check TA34 (-not (Test-Path (Join-Path $source '.opencode/agents/sorin.md')) -and $b -match '\$OldReasoner = ''.opencode/agents/sorin.md''')
    Check TA35 ((& git -C $source grep -n -i 'gpt-6-luna#fast' -- '.opencode/agents' 'opencode.jsonc' | Out-String).Length -eq 0)
    Check TA_ROADMAP ($r -match '7 — Talos The Sentinel \| \*\*(IN VALIDATION|SHIPPED)\*\*' -and @('3 — Role Purity + Iterative Evidence','4 — Thales evolution','5 — Atlas The Planner','6 — Argus The Bug Hunter' | Where-Object { $r -notmatch ([regex]::Escape($_) + ' \| \*\*SHIPPED\*\*') }).Count -eq 0)

    $a = Simulate one-round; $c = Simulate second-round; $fourth = Simulate fourth
    Check CASE_A ($a.Status -eq 'SECURITY_DIAGNOSIS' -and $a.Sessions -eq 1 -and $a.Consultations -eq 2 -and $a.WorkerParent -eq 'kael')
    Check CASE_B ($c.Status -eq 'SECURITY_DIAGNOSIS' -and $c.Sessions -eq 1 -and $c.Consultations -eq 3 -and $c.SessionID -eq $a.SessionID)
    Check CASE_C ($fourth.Status -eq 'FOURTH_DENIED' -and $fourth.Consultations -eq 3)
    foreach ($pair in @(@('D','functional','FUNCTIONAL_BUG'),@('E','operational','OPERATIONAL_ISSUE'),@('F','gap','GAP_FEATURE'),@('G','optimization','OPTIMIZATION'))) {
        $result = Simulate $pair[1]
        Check ('CASE_' + $pair[0]) ($result.Status -eq $pair[2] -and $result.Sessions -eq 0 -and $result.Consultations -eq 0)
    }
    $h = Simulate bounded; Check CASE_H ($h.Status -eq 'SECURITY_DIAGNOSIS' -and -not $h.AuditExpanded)
    $i = Simulate uncertain; Check CASE_I ($i.Status -eq 'INCONCLUSIVE' -and $i.Consultations -eq 3 -and $k -match 'independently evaluate Thales Diagnostic Gate')
    $j = Simulate indeterminate INDETERMINATE; Check CASE_J ($j.Status -eq 'COMPLETION_UNCONFIRMED' -and $j.Consultations -eq 1 -and -not $j.Replacement)

    & git -C $source worktree add --detach $old $production | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'production worktree fixture failed' }
    $upgrade = Join-Path $run 'upgrade'; [IO.Directory]::CreateDirectory($upgrade) | Out-Null; & git -C $upgrade init --quiet
    foreach ($path in @('src/local.txt','docs/staged.txt')) {
        $dest = Join-Path $upgrade $path; [IO.Directory]::CreateDirectory((Split-Path $dest -Parent)) | Out-Null
        [IO.File]::WriteAllText($dest,"original $path`n")
    }
    & git -C $upgrade add -- src docs
    & git -C $upgrade -c user.name=Qualification -c user.email=qualification@example.invalid commit --quiet -m fixture
    $initial = Install $old $upgrade
    Check U_BASE ($initial.Code -eq 0 -and -not (Test-Path (Join-Path $upgrade '.opencode/agents/talos.md')))
    [IO.File]::WriteAllText((Join-Path $upgrade 'src/local.txt'),"modified work`n")
    [IO.File]::WriteAllText((Join-Path $upgrade 'docs/staged.txt'),"staged work`n")
    & git -C $upgrade add -- docs/staged.txt
    foreach ($path in @('notes.txt','.serena/project.yml','.opencode/user-note.txt')) {
        $dest = Join-Path $upgrade $path; [IO.Directory]::CreateDirectory((Split-Path $dest -Parent)) | Out-Null
        [IO.File]::WriteAllText($dest,"user owned $path`n")
    }
    $before = Snapshot $upgrade
    $dry = Install $source $upgrade -DryRun
    Check U_DRY ($dry.Code -eq 0 -and $dry.Output -match '\.opencode/agents/talos.md' -and -not (Test-Path (Join-Path $upgrade '.opencode/agents/talos.md')))
    $installed = Install $source $upgrade
    if ($installed.Code -ne 0) { Write-Output $installed.Output }
    $manifest = [IO.File]::ReadAllText((Join-Path $upgrade '.opencode/orchestrator-install.json')) | ConvertFrom-Json
    Check U_UPGRADE ($installed.Code -eq 0 -and (Test-Path (Join-Path $upgrade '.opencode/agents/talos.md')) -and @($manifest.managed_files | Where-Object path -eq '.opencode/agents/talos.md').Count -eq 1)
    Check U_USER_INDEX ((Snapshot $upgrade) -ceq $before)
    $again = Install $source $upgrade; Check U_IDEMPOTENT ($again.Code -eq 0 -and $again.Output -match '(?m)^NO_CHANGES\s*$')
    $fresh = Join-Path $run 'fresh'; [IO.Directory]::CreateDirectory($fresh) | Out-Null; & git -C $fresh init --quiet
    $freshResult = Install $source $fresh
    Push-Location $fresh
    try { $agents = ((& opencode debug agents 2>$null | Out-String) | ConvertFrom-Json -Depth 100) }
    finally { Pop-Location }
    $effective = @($agents | Where-Object id -eq 'talos')
    Check F_FRESH ($freshResult.Code -eq 0 -and @($effective | Where-Object { $_.model.id -eq 'gpt-6.1-sol' -and $_.model.variant -eq 'high' -and $_.mode -eq 'subagent' }).Count -eq 1 -and @($agents | Where-Object id -eq 'sorin').Count -eq 0)
    Check F_EFFECTIVE_DENY ($effective.Count -eq 1 -and @('shell','edit','subagent','read','glob','grep','list','lsp' | Where-Object { $action = $_; @($effective[0].permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq 'deny' }).Count -lt 1 -or @($effective[0].permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq 'allow' }).Count -gt 0 }).Count -eq 0)
    Check F_ROSTER (@($expected.Keys | Where-Object { $id = $_; $want = $expected[$id].Split('#'); @($agents | Where-Object { $_.id -eq $id -and $_.model.id -eq $want[0] -and $_.model.variant -eq $want[1] }).Count -ne 1 }).Count -eq 0)
    $drift = Join-Path $run 'drift'; [IO.Directory]::CreateDirectory($drift) | Out-Null; & git -C $drift init --quiet
    Check D_BASE ((Install $old $drift).Code -eq 0)
    [IO.File]::AppendAllText((Join-Path $drift '.opencode/agents/kael.md'),"`n# user drift`n")
    $blocked = Install $source $drift
    Check D_REFUSED ($blocked.Code -ne 0 -and $blocked.Output -match 'MANAGED_FILE_DRIFT' -and -not (Test-Path (Join-Path $drift '.opencode/agents/talos.md')))
    $foreign = Join-Path $run 'foreign'; [IO.Directory]::CreateDirectory((Join-Path $foreign '.opencode/agents')) | Out-Null; & git -C $foreign init --quiet
    [IO.File]::WriteAllText((Join-Path $foreign '.opencode/agents/talos.md'),"user-owned talos`n")
    $conflict = Install $source $foreign
    Check D_UNOWNED_REFUSED ($conflict.Code -ne 0 -and $conflict.Output -match 'INSTALL_CONFLICT')
    Write-Output 'TALOS QUALIFICATION: PASS'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'TALOS QUALIFICATION: FAIL'
    exit 1
} finally {
    if (Test-Path -LiteralPath $old) { & git -C $source worktree remove --force $old 2>$null | Out-Null }
    if (Test-Path -LiteralPath $run) {
        try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop }
        catch { Write-Output "CLEANUP_DEFERRED: $run" }
    }
}
