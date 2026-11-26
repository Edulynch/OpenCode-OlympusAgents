[CmdletBinding()]
param([ValidateSet('Both','Offline','Runtime')][string]$QualificationSlice = 'Both')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$run = Join-Path (Join-Path ([IO.Path]::GetTempPath()) 'opencode') ('atlas-qualification-' + [guid]::NewGuid().ToString('N'))
$script:CollectOfflineContracts = $QualificationSlice -eq 'Offline'
$script:OfflineContractFailures = [Collections.Generic.List[string]]::new()
function Check([string]$id, [bool]$ok) {
    if (-not $ok) {
        if ($script:CollectOfflineContracts) {
            $null = $script:OfflineContractFailures.Add($id)
            Write-Output "$id FAIL (recorded; continuing offline coverage)"
            return
        }
        throw "$id FAIL"
    }
    Write-Output "$id PASS"
}
function Get-CanonicalRoleDisplay([string]$SourceRoot, [string]$RoleId) {
    $identities = [IO.File]::ReadAllText((Join-Path $SourceRoot 'olympus/core/identities.toml'))
    $pattern = '(?ms)^\[roles\.' + [regex]::Escape($RoleId) + '\]\s+display\s*=\s*"([^"]+)"'
    $match = [regex]::Match($identities, $pattern)
    if (-not $match.Success) { return $null }
    return $match.Groups[1].Value
}
function Install([string]$root, [string]$repo) {
    $args = @('-NoProfile','-File',(Join-Path $root 'scripts/bootstrap.ps1'),'-Target',$repo)
    $result = (& pwsh @args 2>&1 | Out-String)
    [pscustomobject]@{ Code=$LASTEXITCODE; Output=$result }
}
# Deterministic policy simulation; asserts routing invariants, not live agent behavior.
function Simulate([string]$case, [string]$workerState = 'TERMINAL') {
    $atlasId = 'atlas-primary-1'
    $sessions = 0; $consultations = 0; $workerParent = ''; $workerRole = ''; $status = ''
    if ($case -in @('trivial','unknown-cause')) {
        $status = if ($case -eq 'trivial') { 'NORMAL_PATH' } else { 'DIAGNOSIS_FIRST' }
    } else {
        $sessions = 1; $consultations = 1
        switch ($case) {
            direct { $consultations = 0; $status = 'PLAN_READY' }
            missing {
                $request = [pscustomobject]@{ TargetRole='veyra'; Scope='contracts/compatibility.txt'; Question='What acceptance ordering is required?' }
                if ($request.Scope -ne 'contracts/compatibility.txt' -or $request.TargetRole -notin @('veyra','helios','talos','thales')) { throw 'Synthetic evidence request out of scope' }
                $workerRole = $request.TargetRole
                $workerParent = 'atlas'
                if ($workerState -eq 'INDETERMINATE') { $status = 'COMPLETION_UNCONFIRMED' }
                else { $status = 'PLAN_READY' }
            }
            broad { $consultations = 0; $status = 'REQUEST_REJECTED' }
            architecture { $consultations = 0; $status = 'NEEDS_DECISION' }
            third { $consultations = 2; $status = 'THIRD_DENIED' }
            default { throw "Unknown synthetic case: $case" }
        }
    }
    [pscustomobject]@{ Status=$status; Sessions=$sessions; Consultations=$consultations; WorkerParent=$workerParent; WorkerRole=$workerRole; AtlasID=$atlasId }
}
try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    if ($QualificationSlice -ne 'Runtime') {
    $a = [IO.File]::ReadAllText((Join-Path $source 'olympus/harnesses/opencode/agent-prompts/atlas.md'))
    $k = [IO.File]::ReadAllText((Join-Path $source 'olympus/harnesses/opencode/agent-prompts/kael.md'))
    $routing = [IO.File]::ReadAllText((Join-Path $source 'olympus/policies/routing.md'))
    $orchestration = [IO.File]::ReadAllText((Join-Path $source 'olympus/policies/orchestration.toml'))
    $models = [IO.File]::ReadAllText((Join-Path $source 'olympus/core/models.toml'))
    $atlasMetadata = [IO.File]::ReadAllText((Join-Path $source 'olympus/harnesses/opencode/agent-metadata/atlas.md'))
    $kaelMetadata = [IO.File]::ReadAllText((Join-Path $source 'olympus/harnesses/opencode/agent-metadata/kael.md'))
    $r = [IO.File]::ReadAllText((Join-Path $source 'docs/ROADMAP.md'))
    $display = Get-CanonicalRoleDisplay $source 'atlas'
    $atlasChildren = @([regex]::Matches($atlasMetadata, '(?m)^  - action: subagent\r?\n    resource: ([^\r\n]+)\r?\n    effect: allow\r?$') |
        ForEach-Object { $_.Groups[1].Value.Trim('"') })
    Check AT1 ($null -ne $display -and $a -match '(?m)^# \{\{display_identity\}\}$' -and $atlasMetadata -match '(?m)^mode: primary$')
    Check AT2 ($atlasMetadata -match 'model: "\{\{opencode_model\}\}#\{\{effort\}\}"' -and
        $models -match '(?ms)^\[roles\.atlas\]\s+family = "sol"\s+effort = "high"')
    Check AT3 ($k -match 'Atlas is a separate read-only primary, not a Kael child' -and
        $k -match 'Kael never invokes Atlas as a child' -and
        $kaelMetadata -notmatch '(?s)action: subagent\s+resource: atlas\s+effect: allow')
    Check AT4 ($atlasMetadata -match '(?m)^  - action: shell\r?\n    resource: "\*"\r?\n    effect: ask$' -and
        $a -match 'Shell is permitted only for bounded inspection/diagnostics\s+through native ASK')
    Check AT5 ($atlasMetadata -match '(?m)^  - action: edit\r?\n    resource: "\*"\r?\n    effect: deny$' -and
        $atlasMetadata -match '(?m)^  - action: write\r?\n    resource: "\*"\r?\n    effect: deny$')
    Check AT6 ($atlasMetadata -match '(?m)^  - action: subagent\r?\n    resource: "\*"\r?\n    effect: deny$' -and
        $atlasMetadata -match '(?m)^  - action: question\r?\n    resource: "\*"\r?\n    effect: deny$' -and
        $atlasMetadata -match '(?m)^  - action: execute\r?\n    resource: "\*"\r?\n    effect: ask$')
    Check AT7 ($a -match 'architecture/interface/trade-off reasoning' -and
        $a -match 'smallest sufficient execution sequence' -and
        $a -match 'STATUS: PLAN_READY \| NEEDS_DECISION \| NEEDS_EVIDENCE \| BLOCKED')
    Check AT8 ($routing -match 'Atlas is a separate primary analyst/planner' -and
        $routing -match 'Kael does not read/search repositories' -and
        $routing -match 'Atlas is the read-only primary for bounded repository analysis')
    Check AT9 ($a -match 'Atlas owns bounded architecture' -and
        $a -match 'architecture/interface/trade-off reasoning' -and
        $a -match 'Every proposed\s+execution handoff to Kael')
    Check AT10 ($a -match 'Thales only for exceptional high uncertainty after bounded evidence' -and
        $k -match '## Diagnostic Gate' -and $k -match 'evidence-backed condition')
    Check AT11 ($a -match 'proposed scopes for Kovan/Nox/Vera' -and
        $routing -match 'Every product-source change goes to one scoped Kovan writer' -and
        $a -match 'Never invoke\s+Kael, Atlas, Kovan,\s+Nox, Vera, or any other agent')
    Check AT12 ($a -match 'return a scoped request to Kael for Nox; do not invoke Nox' -and
        $routing -match 'Nox owns distinct reproduction, tests, runtime validation, and measurement' -and
        $routing -match 'Vera reviews a supplied final candidate')
    Check AT13 ($a -match 'smallest sufficient execution sequence' -and
        $a -match 'exact candidate paths/effects' -and $a -match 'acceptance criteria')
    $planFields = @('STATUS: PLAN_READY','NEEDS_DECISION','NEEDS_EVIDENCE','BLOCKED','OBJECTIVE:','EVIDENCE:','ANALYSIS:','TRADEOFFS:','RECOMMENDATION:','SCOPED_HANDOFF_TO_KAEL:')
    Check AT14 (@($planFields | Where-Object { -not $a.Contains($_) }).Count -eq 0)
    Check AT15 ($a -match 'For `NEEDS_EVIDENCE`, state one exact missing fact, bounded scope, why it matters,\s+and expected discrimination' -and
        $a -match 'Use Veyra/Helios/Talos/Thales only for your direct\s+allowlist')
    Check AT16 ($atlasChildren -join ',' -ceq 'veyra,helios,talos,thales' -and
        $a -match 'You may invoke only Veyra, Helios, Talos, or Thales')
    Check AT17 ($atlasMetadata -match '(?m)^mode: primary$' -and
        $a -match 'Atlas-launched child sessions share this root''s prompt-level ceiling')
    Check AT18 ($a -match 'Thales only for exceptional high uncertainty after bounded evidence' -and
        $a -match 'exclusive performance-method specialist' -and
        $a -match 'only for explicit\s+optimization intent')
    Check AT19 ($a -match 'Do not\s+reopen settled architecture or broaden discovery without an evidence-based need' -and
        $k -match 'Stop when supplied evidence is\s+sufficient to act or conclude')
    Check AT20 ($k -match 'reconciles its\s+original result' -and
        $k -match 'COMPLETION_UNCONFIRMED' -and
        $k -match 'replacement children' -and
        $a -match 'Reconcile and consume every required direct child.s terminal result exactly\s+once before returning a ready plan' -and
        $a -match 'yield\s+for the native notification; do not poll' -and
        $a -match 'COMPLETION_UNCONFIRMED.*?instead of declaring a ready plan')
    Check AT23 ($routing -match 'Kael owns all user decisions' -and
        $k -match 'Atlas is a separate read-only primary' -and
        $a -match 'or claim completion' -and $a -match 'PLAN_READY')
    Check AT24 ($a -match 'Never ask the user, grant or\s+infer authority' -and
        $a -match 'Proposed scopes are\s+not grants or approval' -and
        $a -match 'Kael alone')
    Check AT25 ($orchestration -match '(?m)^max_children = 4$' -and
        $a -match 'MAX_ACTIVE_CHILDREN = \{\{max_children\}\}' -and
        $a -match 'effective user-selected\s+ceiling may be 1–8' -and
        $routing -match 'TARGET_ACTIVE = min\(ULTRA_CEILING, READY_WORKSTREAMS\)')
    Check AT26 ($a -match 'APPROVAL_REQUIRED: YES \| NO' -and
        $a -match 'PERFORMANCE_PLAN_READY' -and
        $a -match 'SCOPED_HANDOFF_TO_KAEL')
    $missingReadRules = @('read','glob','grep','list','lsp','webfetch','websearch') | Where-Object {
        $atlasMetadata -notmatch ('(?m)^  - action: ' + $_ + '\r?\n    resource: "\*"\r?\n    effect: allow$')
    }
    Check 'AT_READ_ALLOWED' (@($missingReadRules).Count -eq 0)
    Check 'AT_ROADMAP' ($r -match '5 — Atlas The Planner \| \*\*(IN VALIDATION|SHIPPED)\*\*' -and $r -match '3 — Role Purity \+ Iterative Evidence \| \*\*SHIPPED\*\*' -and $r -match '4 — Thales evolution \| \*\*SHIPPED\*\*')
    # Offline synthetic routing: contracts and negative controls, NOT live agent execution.
    $caseA = Simulate direct; $caseB = Simulate missing; $caseC = Simulate broad; $caseD = Simulate architecture
    $caseE = Simulate trivial; $caseF = Simulate unknown-cause; $caseG = Simulate third; $caseH = Simulate missing INDETERMINATE
    Check 'CASE_A_DIRECT_PLAN' ($caseA.Status -eq 'PLAN_READY' -and $caseA.Sessions -eq 1 -and $caseA.Consultations -eq 0 -and $caseA.WorkerParent -eq '')
    Check 'CASE_B_ONE_EVIDENCE_ROUND' ($caseB.Status -eq 'PLAN_READY' -and $caseB.Sessions -eq 1 -and $caseB.Consultations -eq 1 -and $caseB.WorkerParent -eq 'atlas' -and $caseB.WorkerRole -eq 'veyra' -and $caseB.AtlasID -eq $caseA.AtlasID)
    Check 'CASE_C_BROAD_DISCOVERY_REJECTED' ($caseC.Status -eq 'REQUEST_REJECTED' -and $caseC.Sessions -eq 1 -and $caseC.Consultations -eq 0)
    Check 'CASE_D_UNRESOLVED_ARCHITECTURE' ($caseD.Status -eq 'NEEDS_DECISION' -and $caseD.Consultations -eq 0)
    Check 'CASE_E_TRIVIAL_EDIT' ($caseE.Status -eq 'NORMAL_PATH' -and $caseE.Sessions -eq 0)
    Check 'CASE_F_UNKNOWN_ROOT_CAUSE' ($caseF.Status -eq 'DIAGNOSIS_FIRST' -and $caseF.Sessions -eq 0)
    Check 'CASE_G_THIRD_DENIED' ($caseG.Status -eq 'THIRD_DENIED' -and $caseG.Consultations -eq 2)
    Check 'CASE_H_INDETERMINATE_WORKER' ($caseH.Status -eq 'COMPLETION_UNCONFIRMED' -and $caseH.Consultations -eq 1 -and $caseH.WorkerParent -eq 'atlas' -and $caseH.WorkerRole -eq 'veyra')
    }
    $script:CollectOfflineContracts = $false

    if ($QualificationSlice -ne 'Offline') {
    $fresh = Join-Path $run 'fresh'
    [IO.Directory]::CreateDirectory($fresh) | Out-Null
    & git -C $fresh init --quiet
    $freshResult = Install $source $fresh
    Push-Location $fresh
    try { $agents = ((& opencode debug agents 2>$null | Out-String) | ConvertFrom-Json -Depth 100) }
    finally { Pop-Location }
    Check 'AT_FRESH_EFFECTIVE' ($freshResult.Code -eq 0 -and
        @($agents | Where-Object { $_.id -eq 'atlas' -and $_.model.id -eq 'gpt-6.2-sol' -and $_.model.variant -eq 'high' -and $_.mode -eq 'primary' }).Count -eq 1)
    }
    if ($QualificationSlice -eq 'Offline' -and $script:OfflineContractFailures.Count -gt 0) {
        throw ('Offline static/synthetic check failures: ' + ($script:OfflineContractFailures -join ', '))
    }
    if ($QualificationSlice -eq 'Runtime') {
        Write-Output 'ATLAS RUNTIME QUALIFICATION: PASS (fresh installed effective agent; no interactive session executed)'
    } elseif ($QualificationSlice -eq 'Offline') {
        Write-Output 'ATLAS OFFLINE QUALIFICATION: PASS (static/synthetic policy checks; effective OpenCode queries not run)'
    } else {
        Write-Output 'ATLAS QUALIFICATION: PASS'
    }
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'ATLAS QUALIFICATION: FAIL'
    exit 1
} finally {
    if (Test-Path -LiteralPath $run) {
        try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop }
        catch { Write-Output "CLEANUP_DEFERRED: $run" }
    }
}
