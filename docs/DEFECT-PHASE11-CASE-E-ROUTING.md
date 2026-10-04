# Phase 11 Case E — security-routing coverage defect

**Status:** `FIX_IMPLEMENTED_PENDING_E2`.
**Historical finding:** Confirmed intended-product routing gap; the original
native attempt remains an observed routing failure and has not been rewritten.
**Observed case result:** `NATIVE_EXECUTED_ROUTING_FAIL`.
**Phase 11:** **IN VALIDATION / PARTIAL**.

## Native evidence

The original completed root was reconciled using public, read-only OpenCode V2
API GETs. `tests/phase11-integrated-routing/case-e.native-trace.json` records
the observed route and classifications. The exact user prompt and visible
assistant terminal text are in
`tests/phase11-integrated-routing/case-e.root-session.export.json`, a
reasoning-redacted projection of the original export. The raw export was
captured in memory only; all reasoning blocks were removed before persistence,
secrets were checked, and only observable tool-call ID/name/state stubs would be
retained. This export contained no tool-call records. The native direct-child
query returned zero children and no next cursor. No worktree filesystem, private
runtime, other session, exploit, rerun, or replay was accessed or performed.

Root Kael session `ses_ef85bfb20ffeJDAs5WvP6mQNiP` is titled “Authorization
defect classification for account deletion,” reports execution outcome
`succeeded`, and has API-reported directory
`C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-e`. Parent identity
was not exposed. The prompt's starting HEAD was
`314a6bc529e0d5e17d1662e3765734b7cc80cd86`; worktree isolation is recorded as
`SUPPLIED_VERIFIED`, not independently filesystem-audited.

The prompt states that MEMBER can delete another user's account although only
ADMIN may do so, treats that behavior as established, requests the smallest
sufficient security-specific route, and prohibits exploit attempts, destructive
actions, edits, and broad audit. The terminal response:

- classifies `CONFIRMED_SECURITY_DEFECT` and identifies the server-enforced
  ADMIN-only authorization boundary;
- states that only an authenticated, authorized ADMIN may delete, and that
  MEMBER/non-ADMIN requests must be denied without deletion side effects;
- proposes synthetic identities and mocked deletion operations, including
  MEMBER-denial and ADMIN-allow regression checks;
- reports `EXPLOIT_ATTEMPTED: NO`, `FILES_CHANGED: NONE`,
  `UNRESOLVED_WORK: NONE`, all required children terminal/consumed, and no work
  remaining.

These are behavior, security, and safety PASS findings. The root execution
success is not routing success:

| Dimension | Finding |
|---|---|
| Behavior / security classification / violated boundary | PASS |
| Safe validation / no exploit / role purity | PASS |
| Negative Argus control | PASS — 0 invocations, 0 child sessions |
| Expected product route | Kael -> Talos |
| Observed product route | Kael only; 0 direct children, 0 observable tool-call records |
| Talos activation / routing | FAIL — Talos count 0 |
| Native Case E acceptance | FAIL — `NATIVE_EXECUTED_ROUTING_FAIL` |

The native root is recorded as observed, but Case E remains an unresolved
acceptance item. E, F, G, H, and K remain pending and Phase 11 remains PARTIAL.
Cases A-D are unchanged. `ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE` remains
`NOT_EXERCISED`. No Case E rerun is requested or authorized by this record.

## Bounded root-cause assessment

This is a confirmed **intended-product routing gap**, not a finding that Kael's
security classification was defective. The smallest supported likely cause is
a mismatch between the explicit Phase 11 routing invariant and the written
optional specialist gate:

- The Kael OpenCode prompt says classification alone does not require Talos
  and conditions Talos on an additional materially unanswered security-specific
  question (`olympus/harnesses/opencode/agent-prompts/kael.md:286-292`).
- Talos's own prompt repeats the security-specific unanswered-question
  prerequisite (`olympus/harnesses/opencode/agent-prompts/talos.md:25-27`).
- The Case E matrix expects `default: [kael, talos]`
  (`tests/phase11-integrated-routing/cases.json:96-106`); the completed original
  prompt is retained in the native export projection and its short case
  reference remains in `tests/phase11-integrated-routing/RUNME.md:231-240`.
- The canonical generic routing policy says to choose the smallest sufficient
  role set (`olympus/policies/routing.md:5-7`).

The case's material authorization boundary and correct classification were
explicit; the prompt did not pose an unresolved exploitability, impact, trust,
or classification question. The optional-gate wording is therefore consistent
with a Kael-only response, while the intended Phase 11 invariant requires Talos
for this established boundary. This records the mismatch at the product-rule
level. It does **not** claim the assistant internally followed any particular
reasoning or that its security classification was wrong.

At the time this historical assessment was recorded, read-only `git show` at
the original starting HEAD
`314a6bc529e0d5e17d1662e3765734b7cc80cd86` confirmed the same Kael/Talos gate
text. At that time, `olympus/policies/routing.md` was generic and no Core,
adapter, generated, or global policy had been changed.

## Implemented correction; native closure pending

The corrected invariant is: an ESTABLISHED or STRONGLY EVIDENCED MATERIAL
SECURITY / TRUST / AUTHORIZATION BOUNDARY DEFECT being diagnosed/classified makes
Talos REQUIRED as part of the smallest sufficient role set; no additional
unanswered security-specific question is required for initial activation.
Conservative negative gates remain: unconfirmed security relevance, generic
security wording, nearby authentication/credentials, informational scanner
output, unconfirmed affected-version relevance, operational scanner/tool
failures without product-defect evidence, deterministic non-security functional
defects, gaps/features and optimization do not automatically activate Talos.
Argus remains for independently gated functional diagnosis; mixed defects use
the evidence-supported primary classification and do not automatically invoke
both specialists. Mediated EVIDENCE_REQUEST → bounded Veyra/Nox evidence →
consumed terminal result → SAME Talos session behavior, budgets and no-progress
rules are unchanged; only initial activation semantics changed.

Changed source, regression and record files:

- `olympus/policies/routing.md`
- `olympus/harnesses/opencode/agent-prompts/kael.md`
- `olympus/harnesses/opencode/agent-prompts/talos.md`
- `olympus/harnesses/codex/root.md`
- `olympus/harnesses/codex/agents/talos.toml`
- `tests/talos/qualify.ps1`
- `tests/phase11-integrated-routing/qualify.py` (updated the static marker only;
  Case E expected route and historical native failure remain unchanged)
- `docs/DEFECT-PHASE11-CASE-E-ROUTING.md`

Generated outputs were produced by `scripts/render_harnesses.py`, not edited by
hand: `.opencode/agents/kael.md`, `.opencode/agents/talos.md`, `CODEX.md`, and
`.codex/agents/talos.toml`.

Static validation passed: all-harness render check (29 managed outputs), Phase
11 artifact qualification (exit 0; reports PARTIAL and retains E's observed
failure), Phase 11 unittest suite (58 tests), harness-core safe-root read-only
qualification, routing-constraint qualification, Talos qualification including
the established-boundary and five negative-gate regression cases, and
`git diff --check`. Native closure requires a fresh-root Case E2 after the
implementation commit. Case E attempt 1 remains
`NATIVE_EXECUTED_ROUTING_FAIL`; E remains pending, the old root is not relabelled
PASS, Phase 11 remains PARTIAL, and Case E was not rerun in this maintenance
task.
