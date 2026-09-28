# Helios The Optimizer — candidate-fixture live cases (NOT EXECUTED)

These two candidate-fixture cases were not run. This does not invalidate the separate user-executed Helios live cases already recorded in `docs/ROADMAP.md`; do not rerun those accepted cases for release preparation.

The retained disposable fixture is `$env:LOCALAPPDATA\Temp\opencode\helios-live-candidate-20260927`. Prepare it **only if absent** from the candidate root:

```powershell
$target = "$env:LOCALAPPDATA\Temp\opencode\helios-live-candidate-20260927"
if (-not (Test-Path -LiteralPath $target)) { pwsh -NoProfile -File ./tests/helios/prepare-live.ps1 -Target $target }
Push-Location $target
opencode debug agents
Pop-Location
```

Preparation refuses to overwrite an existing target. Record the measured byte count: 41,943,040 bytes = 40 MiB, target < 25 MiB. Source configuration explains a potential deduplication direction; **do not reveal the exact cause to Kael or Helios up front**. Keep cases A and B in separate **fresh explicit Kael roots**; commands below MUST use `opencode run --agent kael`. Capture each root ID from native run/session events and use `opencode session export <root-session-id>` to verify the root assistant message `agent == kael`. If not Kael: **INFRA_OR_TEST_INSTRUCTION_BLOCKED**, not Helios failure; stop and do not blindly retry an indeterminate worker. Review native child IDs, parent IDs, model, message chronology, terminal outcomes, parent consumption, pending and unknown. A root's first answer/idle status alone is not family completion. Agent cases are NOT part of preparation.

## Case A — explicit optimization proposal, one bounded evidence round

From `$target`:

```powershell
opencode run --agent kael --format json 'Evaluate whether we should optimize artifact/report.html to below 25 MiB; propose only, do not implement. The measured baseline is 40 MiB (41,943,040 bytes), recorded in observations/size.txt. I do not know what accounts for its size; do not inspect config/report-export.txt or artifact/report.html yourself or tell Helios the cause initially. Route ONE Helios at Sol High for cheap feasibility and a precise EVIDENCE_REQUEST; after validating the request, route exactly ONE direct Kael-owned Veyra to the bounded config/report-export.txt and artifact/report.html composition question. Deliver actual evidence to the SAME Helios session for an evidence-bounded OPTIMIZATION_PROPOSAL or DO_NOT_OPTIMIZE. Surface expected benefit, effort, risk, validation and material tradeoffs and STOP FOR USER APPROVAL. No implementation, Atlas, Kovan or Helios direct discovery. Consume all original terminal results. Report Kael/Helios/Veyra session IDs, parents, model, consultations, pending and unknown.'
```

Expect one Helios session, two consultations (EVIDENCE_REQUEST then OPTIMIZATION_PROPOSAL), third zero; one bounded Veyra directly under Kael. Evidence can support a ~24 MiB reduction by replacing three redundant 8 MiB copies with references **only if** supported consumer behavior is validated; no claim of measured after-state, successful optimization or guarantee that target will be met. Proposal must include OBJECTIVE, BASELINE, TARGET, BOTTLENECK, OPPORTUNITY, PROPOSAL, EXPECTED_BENEFIT, EFFORT, RISK, CONFIDENCE, VALIDATION (BEFORE / AFTER / DELTA / TARGET / CORRECTNESS), TRADEOFFS, STOP_CONDITIONS, APPROVAL_REQUIRED: YES. No architecture redesign, auto-implementation, Kovan or Atlas. No direct Helios read/glob/grep/list/LSP/shell/edit. Family complete, pending 0, unknown 0. For indeterminate worker result reconcile the original; otherwise COMPLETION_UNCONFIRMED, without fabricating measurement or replacing it.

## Case B — factual observation, no explicit optimization request

Use a **different fresh root** in `$target`:

```powershell
opencode run --agent kael --format json 'artifact/report.html is currently 40 MiB (41,943,040 bytes). This is an observation only. Acknowledge it without proposing or starting optimization analysis. Report whether any Helios sessions were used and account for all required work.'
```

Expect **HELIOS COUNT = 0**. Verify root assistant == kael and family complete with pending/unknown zero. Do not run these agent cases during candidate preparation; report LIVE EVIDENCE: NOT_EXECUTED until user runs and reviews them.
