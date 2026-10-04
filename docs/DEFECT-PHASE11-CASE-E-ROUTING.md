# Phase 11 Case E — security-routing coverage defect

**Status:** `CLOSED — VERIFIED_BY_E2_FRESH_ROOT_NATIVE`.
**Historical finding:** Confirmed intended-product routing gap; the original
native attempt remains an observed routing failure and has not been rewritten.
**Historical E1 result:** `NATIVE_EXECUTED_ROUTING_FAIL`.
**Current Case E acceptance:** E2 `NATIVE_EXECUTED_ROUTING_PASS`.
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

At this E1 snapshot, Case E remained an unresolved acceptance item alongside F,
G, H, and K. This historical pending state is superseded only by the E2 closure
record below; Cases A-D and
`ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE: NOT_EXERCISED` were unchanged.
No replay of E1 is requested or authorized by this record.

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

## Implemented correction; E2 pending at the time of this historical note

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

The validation results and pending state recorded above were current before the
E2 reconciliation. The later E2 root below supersedes only the pending-closure
statement; it does not alter this record of the E1 failure or the implementation
history.

## E2 native confirmation and closure — `PH11-E2-CLOSURE`

The completed E2 root and its direct child were reconciled from the public,
read-only OpenCode V2 metadata, export, message-list, and direct-child APIs. The
root is Kael session `ses_ef7eb1d45ffet0gMtEEUam8R4U`, has an explicitly null
parent, succeeded, and is titled “Diagnosing MEMBER account-deletion
authorization boundary.” Its prompt records starting HEAD
`3e5b2af2c15f9ef2775be3c3f5667edd4db0bdde`. Root and child directory metadata
matched the supplied disposable-path context; exact directory paths were not
retained. No disposable-worktree filesystem or private runtime state was
accessed.

The complete root direct-child listing required two pages and contained exactly
one child: Talos `ses_ef7ea7bf7ffe4U23sL7M1mi60p`, parented to the root, outcome
`succeeded`, title “Diagnose account deletion authorization.” The root export
contains exactly one completed `subagent` call, ID
`call_FzRbkaOiUp41wcA0DcJfrrPw`; its observed input identifies Talos and the
`PHASE11_CASE_E2_FRESH_ROOT` label, and its child-session metadata matches that
same direct child. The Talos export contains no tool-call records. Both message
lists were reconciled over two pages; the second cursor-only page for each was
empty.

The root and child export projections are
`tests/phase11-integrated-routing/case-e2.root-session.export.json` and
`tests/phase11-integrated-routing/case-e2.talos-session.export.json`; the
bounded trace is `tests/phase11-integrated-routing/case-e2.native-trace.json`.
Two root reasoning blocks were removed and the child had none. Retained prompt
and terminal text matches the public exports, no secret-pattern matches
required redaction, and raw exports were not persisted. No private child
subtree, tool result body, runtime database, or worktree filesystem was
inspected.

- Expected and observed product route: Kael -> Talos. E2 therefore verifies
  current Case E routing acceptance. Behavior/security, safety, role purity,
  Talos activation, negative Argus control, routing, result fidelity, completion
  ownership, and fresh-root-native classifications are PASS.
- Talos confirmed the established behavior violates the ADMIN-only account
  deletion boundary. The minimum fix direction is trusted, authenticated
  server-side ADMIN authorization before deletion side effects; the specific
  implementation mechanism remains unknown. No tools, tests, exploit, source
  inspection, or file mutation were attempted by the diagnosis child.
- The root terminal states that required child work is terminal and consumed and
  that no work remains. It does not contain a literal E2 `PASS`; acceptance is a
  reconciliation judgment based on the observed route, diagnosis, safety
  limits, and aggregate completion statement. Per-invocation result IDs and
  consumption timing, session-lifetime exact-once, concurrency, and timing
  remain `null`; native permission UI and decision remain `NOT_OBSERVABLE`.
- E1 remains unchanged as a failed historical attempt:
  `NATIVE_EXECUTED_ROUTING_FAIL`, expected Kael -> Talos, observed Kael only,
  acceptance `FAIL`. E2 does not rewrite E1 or claim that its root passed.

Accordingly, the routing defect is **CLOSED —
`VERIFIED_BY_E2_FRESH_ROOT_NATIVE`**. Current Case E acceptance is closed by E2;
overall Phase 11 remains **IN VALIDATION / PARTIAL**, not SHIPPED. Fresh-root
work F, G, H, and K remains pending. A is PASS guided/recovered, B/C/D/E2 are
accepted fresh-root-native, I is PARTIAL guided, J is PASS guided/recovered, and
L's recovered negative automatic-Aegis control is PASS.
`ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE` remains `NOT_EXERCISED`.
The closure's static validation commands and results are recorded in
`tests/phase11-integrated-routing/baseline.md`; they validate artifacts and do
not constitute a Case E rerun or independent source-export authentication.
