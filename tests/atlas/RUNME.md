# Atlas The Planner — manual live qualification (NOT EXECUTED)

Do not run these agent cases as part of candidate preparation. Use two fresh Kael roots in the disposable trusted Git fixture; collect native session/message chronology, not only final prose. Phase 5 stays IN VALIDATION until the user qualifies both.

Prepare from candidate repository root in PowerShell:

```powershell
pwsh -NoProfile -File ./tests/atlas/prepare-live.ps1 -Target "$env:LOCALAPPDATA\Temp\opencode\atlas-live-candidate"
$target = "$env:LOCALAPPDATA\Temp\opencode\atlas-live-candidate"
Push-Location $target
opencode debug agents
# Open a fresh Kael root for each case in this project through your normal OpenCode interface.
Pop-Location
```

If already prepared, use that fixture without rerunning the preparation script (it refuses to replace an existing path).

## Case A — planning-critical omitted fact

Give a fresh Kael session this prompt; do NOT quote or reveal `contracts/compatibility.txt` contents in the prompt:

> Produce an execution plan only for an already-architected version-header rollout. Gateway owns `X-Contract-Version` emission; orders service owns acceptance. Scope is `gateway/config.txt`, `services/orders.txt`, `tests/routing.txt`; the current state is v1. We need a safe v2 rollout preserving compatibility and a bounded validation/rollback sequence. One exact planning-critical rollout fact is omitted: the existing compatibility policy in `contracts/compatibility.txt`. Do not read this file yourself and do not tell Atlas its contents up front. Apply the Planning Gate; consult Atlas as a direct child. If Atlas requests that fact, validate its bounded EVIDENCE_REQUEST, route exactly ONE direct Kael-owned Veyra to `contracts/compatibility.txt`, reconcile the original worker and deliver actual evidence to the SAME Atlas session. No implementation, no direct Atlas repository discovery, no Maintenance, no third automatic consultation. After a STATUS: PLAN, give only a concise planning synthesis after required family results are collected. Report root/Atlas/Veyra session IDs and Atlas consultation count.

Expected: Kael → one Atlas session (`openai/gpt-6-sol#high`) → `STATUS: EVIDENCE_REQUEST` with five fields and exact bounded path → one Kael-owned Veyra → real file evidence → SAME Atlas session → `STATUS: PLAN` → Kael planning synthesis. Atlas sessions 1; consultations 2; third 0; worker parent Kael. Atlas direct discovery NONE; implementation NONE. Review plan QUALITY manually: small, concrete ordered steps (service dual-acceptance before gateway emission, overlap validation and safe rollback, eventual v1 retirement only after callers gone), actual meaningful dependencies and bounded validation; no invented components/files, architecture redesign, broad discovery, corporate ceremony/unnecessary phases or completion claim. A bloated or useless plan FAILS even if contract fields exist. Pending/unknown required work must be zero before final synthesis. Indeterminate worker: reconcile original or stop COMPLETION_UNCONFIRMED; no replacement or premature continuation.

## Case B — negative control (new Kael root)

Prompt:

> In `simple/label.txt`, change the localized label from `READY` to `READY!` and perform appropriate bounded validation. This is a trivial edit. Use the normal smallest path; do not use Atlas or Maintenance. Report Atlas session/consultation counts. Collect all required worker results before completion.

Expected: ATLAS COUNT = 0; smallest normal routing, no Atlas planning consultation. Review actual child list and final result; absence of Atlas from final prose alone is insufficient proof.

For both cases, inspect native session IDs, parent IDs, agent/model, each consultation's message and tool trace, terminal evidence, worker result consumption, pending/unknown counts and final Kael synthesis. Record findings separately; this file is a procedure, not live evidence.
