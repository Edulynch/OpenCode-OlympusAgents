# Thales The Sage — focused live routing qualification (user-executed only)

Historical manual qualification fixture: both cases were executed by the user and passed before Phase 4 shipped. **Do not rerun for integration.** The steps below record the original candidate procedure (a disposable trusted Git repository installed from `feature/thales-the-sage`, with a fresh Kael root per case). Inspect native session families and message/tool chronology rather than final prose alone. No implementation or changes to incident evidence are requested. Evidence class: **USER_EXECUTED_LIVE_EVIDENCE**, not task-executed live evidence.

## Read-only uncertain case

Prepare `observations/decision.txt` containing:

```text
expected ROUTE=BLUE
trace A: ROUTE=RED, selector not captured
trace B: ROUTE=BLUE, selector not captured
selector rule: when REGION=west, ROUTE=RED; otherwise ROUTE=BLUE
trace A REGION=west
trace B REGION=east
```

Prompt Kael (do not include the last three lines of the file in the prompt):

> Diagnose a genuinely unresolved discrepancy: for the same nominal input the expected route is BLUE, trace A reports RED and trace B BLUE; neither trace packet contains the selector. This is read-only. Consult Thales **only if the shipped Diagnostic Gate is met**. Ask for the smallest discriminating evidence. Do not read `observations/decision.txt` yourself: if Thales issues an EVIDENCE_REQUEST, validate it and launch exactly one bounded direct Veyra evidence child to read that path. Reconcile the original worker and continue the **same** Thales session with real evidence. Synthesize the bounded advice only after all required native results are terminal, collected and consumed. Do not implement, spawn a third automatic consultation, or route Maintenance. Report root, Thales and worker session IDs.

Require: Kael → one `thales` session using `openai/gpt-6-sol#xhigh` → `STATUS: EVIDENCE_REQUEST` (`TARGET_ROLE`, `QUESTION`, `SCOPE`, `WHY_NEEDED`, `EXPECTED_DISCRIMINATION`) → one direct worker with actual selector evidence → **same Thales ID** continued to `STATUS: ADVICE` → Kael final synthesis consuming both results. No `sorin` agent or session. A missing worker result is not a failure; reconcile the original, stop as COMPLETION_UNCONFIRMED if unknown, and do not fabricate evidence. A second evidence request does not authorize a third automatic consultation.

## Cheap deterministic negative control (fresh root)

Prepare `simple/header.txt` containing `REDA`, with required header `READY`. Prompt:

> Read-only straightforward spelling defect: required `READY` but `simple/header.txt` differs. Identify the actual spelling and recommend one bounded correction, without editing. Use normal bounded worker evidence if useful; do not invoke Thales or Maintenance. Reconcile all children and synthesize.

Require `THALES COUNT: 0`, `SORIN COUNT: 0`, no diagnosis escalation and no unknown required work. Fail the fixture if Kael invokes Thales for this deterministic bug.

## Manual preparation and inspection

From the candidate source root in PowerShell (substitute a new disposable absolute Git project root):

```powershell
$candidate = (Get-Location).Path
$target = Join-Path $env:LOCALAPPDATA 'Temp/opencode/thales-live-candidate'
New-Item -ItemType Directory -Force $target | Out-Null
git -C $target init
pwsh -NoProfile -File (Join-Path $candidate 'install.ps1') -SourceRoot $candidate -Target $target
Push-Location $target
opencode debug agents
# Create observations/decision.txt and simple/header.txt as above, then start
# one fresh Kael session per prompt using your normal OpenCode interface.
Pop-Location
```

The user captured root/child IDs, parentIDs, agent IDs and effective models; EVIDENCE_REQUEST and five required fields; worker terminal evidence; two consultations sharing one Thales ID; Kael's final synthesis; and the negative-control Thales count. Both families had zero pending/unknown work. Phase 4 shipping was explicitly authorized after this user-executed qualification.
