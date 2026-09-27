# Argus The Bug Hunter — manual live qualification (NOT EXECUTED)

Do not execute agent cases during candidate preparation. Prepare the disposable trusted Git fixture once from candidate repository root using PowerShell:

```powershell
pwsh -NoProfile -File ./tests/argus/prepare-live.ps1 -Target "$env:LOCALAPPDATA\Temp\opencode\argus-live-candidate"
$target = "$env:LOCALAPPDATA\Temp\opencode\argus-live-candidate"
Push-Location $target
opencode debug agents
# Open a fresh Kael root per case in this project through the normal OpenCode interface.
Pop-Location
```

Preparation refuses to replace an existing target. Do not re-run if it already exists. Collect native session IDs, parent IDs, model, message chronology, tool trace, terminal results, consumption, pending and unknown counts; a final-prose assertion is insufficient.

## Case A — nontrivial functional boundary defect (new Kael root)

**Do not show Kael or Argus `bug/shipping-rule.txt` contents or its comparison ahead of time.** Give Kael this exact prompt:

> Diagnose only, do not fix: established requirement in `contracts/shipping.txt` is FREE_SHIPPING for valid subtotal >= 50. Observations in `tests/shipping-observations.txt`: 49 → PAID_SHIPPING, 50 → PAID_SHIPPING, 51 → FREE_SHIPPING. The cause and fix direction are not in my prompt. Apply the Functional Bug Routing Gate, consult one direct Argus session with this packet, and do not inspect `bug/shipping-rule.txt` yourself or supply its contents to Argus initially. Argus should request one exact bounded missing fact through EVIDENCE_REQUEST if needed. Validate the request and route exactly one direct Kael-owned Veyra to `bug/shipping-rule.txt`, then deliver its real rule evidence to the SAME Argus session. Seek BUG_DIAGNOSIS, not implementation or execution planning. No Thales, Maintenance or direct Argus discovery. Collect all required native child terminal results and consume them before final bounded synthesis. Report Kael/Argus/Veyra session IDs, parent IDs, Argus model, consultation count, and pending/unknown counts.

Expected: one Argus session on `openai/gpt-6-sol#high`, consultation #1 EVIDENCE_REQUEST with five required fields, one Kael-owned Veyra restricted to the rule file, SAME Argus consultation #2 BUG_DIAGNOSIS, third 0. Correct diagnosis separates OBSERVED/EXPECTED/CAUSE/EVIDENCE/FIX_DIRECTION/VALIDATION/CONFIDENCE: strict `>` excludes exactly 50; inclusive threshold semantics is the bounded direction; validation includes 49, 50, 51. Confidence must reflect actual contract/rule evidence, not invented details. No implementation, plan, broad discovery, Thales or Maintenance. Independently inspect the native trace for role purity and evidence provenance. A structurally valid but speculative diagnosis FAILS. Family complete; pending 0; unknown 0. If worker evidence is indeterminate, reconcile original or stop COMPLETION_UNCONFIRMED without replacement or Argus continuation.

## Case B — trivial deterministic localized defect (fresh Kael root)

Prompt:

> In `simple/label.txt`, change the visible typo `REEDY` to its established required value `READY` and perform appropriate bounded validation. This is a trivial localized deterministic defect. Use the normal smallest path. Report Argus session and consultation counts after collecting all required results. Do not use Maintenance.

Expected: ARGUS COUNT = 0, normal smallest-path routing; check native child family, not just final prose. Both cases require manual quality review and recorded evidence before Phase 6 can ship. The fixture is retained; no live agent cases have run as part of this preparation.
