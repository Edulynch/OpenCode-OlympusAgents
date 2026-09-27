# Talos The Sentinel — manual live qualification (USER_EXECUTED_LIVE_EVIDENCE: PASS)

Prepare the disposable trusted Git fixture from the candidate repository root, once:

```powershell
pwsh -NoProfile -File ./tests/talos/prepare-live.ps1 -Target "$env:LOCALAPPDATA\Temp\opencode\talos-live-candidate"
$target = "$env:LOCALAPPDATA\Temp\opencode\talos-live-candidate"
Push-Location $target
opencode debug agents
Pop-Location
```

Preparation refuses to overwrite an existing fixture. For **each case**, use a separate fresh root in `$target`, explicitly created as Kael using the exact `opencode run --agent kael` command below. Do not rely on a UI's default agent (it might be `build`). Capture root session ID from native run/session events; export using `opencode session export <root-session-id>` and verify the **root assistant message** `agent == kael` before accepting or continuing qualification. If not Kael: STOP that case, classify **INFRA_OR_TEST_INSTRUCTION_BLOCKED**, not a Talos failure; do not blindly retry/replace indeterminate workers. Inspect native IDs, parent IDs, models, message/tool chronology, terminal results, parent consumption, pending and unknown; final prose alone is not proof. Live review is manual and not part of candidate preparation.

## Case A — admin-only authorization defect

**Start a new explicit-Kael root and verify its root assistant agent.** Do not show Kael or Talos `security/access-rule.txt` or its contents upfront. From `$target`:

```powershell
opencode run --agent kael --format json 'Diagnose only, do not fix: requirement in contracts/access-policy.txt says only ADMIN may execute DELETE_ACCOUNT for another account. Observations in observations/access.txt show MEMBER execution accepted. The implementation cause is not in my prompt. Apply the Security Routing Gate, consult one direct Talos session with this bounded packet; do not inspect security/access-rule.txt yourself or supply its contents to Talos initially. Talos should request one exact missing rule fact via EVIDENCE_REQUEST. Validate that request; route exactly ONE direct Kael-owned Veyra to security/access-rule.txt. Deliver its real evidence to the SAME Talos session. Seek SECURITY_DIAGNOSIS, not implementation, exploit execution or planning. No Argus, Thales, Aegis, or Talos direct discovery. Collect and consume all native child terminal results before bounded synthesis. Report Kael/Talos/Veyra session IDs, parents, Talos model, consultation count, pending and unknown counts.'
```

Expected one Talos session at `openai/gpt-6-sol#high`, consultation #1 `EVIDENCE_REQUEST` (TARGET_ROLE/QUESTION/SCOPE/WHY_NEEDED/EXPECTED_DISCRIMINATION), one direct Kael-owned Veyra, consultation #2 in **SAME Talos session** `SECURITY_DIAGNOSIS`, third 0. Diagnosis must identify admin-only authorization boundary, MEMBER accepted vs only ADMIN accepted, source guard `role != GUEST` instead of requiring ADMIN; impact bounded to non-admin MEMBER crossing the admin-only boundary. Defensive direction: enforce exact required authorization boundary. Validation: GUEST denied, MEMBER denied, ADMIN allowed. No broader compromise claims, attack playbook, exploit execution, implementation, execution plan or broad audit. No Argus, Thales or Aegis. Family complete, pending 0, unknown 0. Speculative/sensational analysis FAILS even if structurally valid. Indeterminate worker: reconcile original; otherwise COMPLETION_UNCONFIRMED, no Talos continuation or replacement.

## Case B — functional-only negative control

**Start a different fresh explicit-Kael root and verify its root assistant agent.** From `$target`:

```powershell
opencode run --agent kael --format json 'In simple/label.txt, change the visible typo REEDY to its established required value READY and perform bounded validation. This is a straightforward functional-only defect; use the normal smallest path. Report Talos session and consultation counts after collecting all required results. Do not use Aegis.'
```

Expected **TALOS COUNT = 0**, normal smallest-path route. Review native family, not just prose. Both cases passed user-run live evidence and independent manual quality review; preserve accepted fixtures/evidence rather than rerunning valid cases. See `docs/ROADMAP.md` for session IDs and accepted findings.
