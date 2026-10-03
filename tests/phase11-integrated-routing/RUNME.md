# Phase 11 — Integrated Routing Qualification (PARTIAL)

This is a focused evidence validator, not a routing/runtime implementation. The
checked-in A–L traces are `SYNTHETIC_TRACE`; their local `SYN-*` references and
ordered events are authored examples, not OpenCode root/child session IDs,
timestamps, guided runs, or proof of model behavior. Static marker checks mean
only that bounded policy text is present. The task owner separately reported
some recovered guided outcomes (recorded below); no native per-case trace is in
this scoped corpus and those reports do not qualify fresh-root cases.

## Automatic local commands

From the repository root, using the pinned Python 3.11 interpreter and standard
library only:

```text
uv run --python 3.11 python tests/phase11-integrated-routing/qualify.py
uv run --python 3.11 python -m unittest discover -s tests/phase11-integrated-routing -p "test_*.py" -v
uv run --python 3.11 python -B tests/harness-core/qualify.py --safe-root-read-only
```

The first command validates the versioned case matrix, the event semantics,
completion/evidence claims, and presence-only gate markers. It exits successfully
when the authored artifacts are sound but prints `PHASE11_QUALIFICATION:
PARTIAL` until fresh-root native evidence is captured. The second command
applies mutations to valid authored traces and requires the prohibited variants
to fail. The Harness Core command checks root-generated adapters without root
rendering; it retains idempotence, drift, and missing-output checks in its
disposable fixture under the approved Temp `opencode` area. It does not modify
real generated outputs. These commands do not start OpenCode, install packages,
contact a network, run a live agent, run the known-bad cart test, or claim a
performance result. `python -B` suppresses bytecode caches for that run.

## Remaining fresh-root work remains user action

Use a separate clean disposable project copy and a **new, verified Kael root for
each pending case**. Only B, C, D, E, F, G, H, and K below are pending fresh-root
actions. A, I, J, and L prompt references/history are retained below but are not
new rerun requests. Do not reuse a guided/current session as a fresh root. Confirm the
effective root agent, child parentage and actual roles from native session
evidence before accepting a case. Scope each live edit to the disposable
qualification fixture; retain the original project untouched. Stop rather than
retry if an execution result is unknown. The prompts below are starting points,
not pre-recorded results. Capture the complete trace schema in
`native-trace.template.json`, preserving unknown values as `null` (never zero).

- `REFERENCE_ONLY PHASE11_CASE_A_GUIDED_RECOVERY` — prior prompt reference: “In a disposable copy, change only
  `fixtures/simple/message.txt` to `Hello Phase 11 ready`. Keep this to one
  scoped edit and verify the exact requested text.”
- `HUMAN_ACTION_REQUIRED PHASE11_CASE_B_FRESH_ROOT` — “In a disposable copy, implement a
  small multi-component cart discount feature with an explicit contract,
  separate calculation and presentation responsibilities, and compatibility
  tests. The requirement and boundaries are supplied; do not redesign the
  architecture. Orin is not qualified by this bounded case. Plan dependencies
  only if they materially matter.”
- `HUMAN_ACTION_REQUIRED PHASE11_CASE_C_FRESH_ROOT` — “In a disposable copy, fix the
  obvious `calculate_total` contract defect in
  `fixtures/obvious/cart.py`; then run its unit test. The fixture is currently
  intentionally wrong, so do not treat its pre-fix failure as a qualification
  failure.”
- `HUMAN_ACTION_REQUIRED PHASE11_CASE_D_FRESH_ROOT` — “Read only the ambiguous fixture
  evidence. `subtotal=100`, `shipping=10`, and an observed total of 110 may mean
  either the input already includes shipping or the domain calculation adds it
  twice. Ask for the smallest bounded discriminating evidence and continue in
  the same Argus session. The supplied fixture has no discriminator; if none is
  found, do not pick a cause and ask the smallest binary user question. Do not
  repair the fixture.”
- `HUMAN_ACTION_REQUIRED PHASE11_CASE_E_FRESH_ROOT` — “Classify this bounded hypothetical
  defect: a MEMBER can delete another user's account although the stated
  contract is ADMIN-only. Explain the security boundary and safe validation;
  do not attempt an exploit, edit, or broad audit.”
- `HUMAN_ACTION_REQUIRED PHASE11_CASE_F_FRESH_ROOT` — “The test command is unavailable
  because the local runner is not installed. Suggest the cheapest bounded
  containment or usage correction; do not classify this as a product bug or
  install anything.”
- `HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT` — “The fixed observation sequence in
  `fixtures/flaky/observations.json` is PASS, TIMEOUT, PASS for the same input.
  It is deterministic evidence, not random instability. Use bounded diagnosis
  only if the Diagnostic Gate applies; stop without repeating unchanged
  evidence.”
- `HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT` — “A third-party dependency has a
  confirmed defect. Use the safe resolution ladder (configuration/version,
  wrapper/fallback, reversible workaround) and stop before any upstream patch,
  vendor, or fork unless I explicitly approve that concrete action.”
- `REFERENCE_ONLY PHASE11_CASE_I_GUIDED_RECOVERY` — prior prompt reference: “Please evaluate whether optimizing
  `fixtures/benchmark/tiny_work.py:square_sum` for the stated target of reducing
  runtime by at least 20% is worthwhile. Use only bounded evidence and stop for
  my approval before implementation.” The target is user intent, not a measured
  baseline; record unknown measurements as null.
- `REFERENCE_ONLY PHASE11_CASE_I_NEGATIVE_CONTROL` (not a rerun request) — prior prompt reference: “The toy
  benchmark reports 3 ms. Tell me whether that is slow; I am not asking you to
  optimize it.” Helios must not activate on this fact-only request.
- `REFERENCE_ONLY PHASE11_CASE_J_GUIDED_RECOVERY` — prior prompt reference: “Give me the smallest sufficient
  ordered plan for rolling out the already-chosen feature across the two
  supplied components, including validation and rollback. Do not implement.”
- `REFERENCE_ONLY PHASE11_CASE_J_NEGATIVE_CONTROL` (not a rerun request) — prior prompt reference: “Change the
  simple fixture greeting to `Hello Phase 11 ready`.” A trivial local edit does
  not need Atlas.
- `HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT` — Run two independent fresh roots on
  the same disposable task: request the FAST profile for four independent
  fixture-only text edits (disjoint files), then run a separate NORMAL-profile
  control. Capture actual child start/terminal order, useful writer count,
  nonoverlapping paths, dependency edges, and measured maximum simultaneous
  children. Requested parallelism is not evidence of achieved concurrency.
- `REFERENCE_ONLY PHASE11_CASE_L_NEGATIVE_AUTOMATIC_AEGIS_RECOVERY` — prior prompt reference: “Make the same harmless fixture-only
  edit as case A in a normal project request. Do not enter `/maintain`.” Verify
  Kael does not launch Aegis; this is not an instruction to test or invoke
  Aegis. Do not repeat the recovered negative automatic-Aegis control solely for
  completeness.

## Recovered user-reported observations

The task owner reported these preserved recovery outcomes: Case A `PASS`
(`GUIDED_CURRENT_SESSION`); Case I `PARTIAL` guided, with the useful baseline
missing; Case J `PASS` (`GUIDED_CURRENT_SESSION`); and Case L's negative
automatic-Aegis control `PASS`. These are `USER_REPORTED_RECOVERED` observations,
not reconstructed trace events or fresh-root passes. No case-specific session
IDs or original native trace records were supplied in this corpus; do not
invent IDs or relabel the synthetic A/I/J/L records. The referenced recovery
sessions were old Kovan `ses_effe57255ffeJWL1K6kuhu8Fr1` and Vera
`ses_effb08273ffebb6fzuHwVmxilk`; these identify writer/reviewer recovery
sessions only, not the Case A/I/J/L native roots. Preserve them if available.

## Evidence classes and capture discipline

- `POLICY_BASELINE`: bounded static policy markers and source fingerprints;
  proves policy text/asset identity only.
- `SYNTHETIC_TRACE`: hand-authored or generated deterministic event example;
  never satisfies a live or fresh-root requirement.
- `GUIDED_CURRENT_SESSION`: native evidence captured in a guided/current root;
  useful context, but not independent fresh-root evidence.
- `FRESH_ROOT_NATIVE`: observed native evidence from a separately created,
  verified Kael root with actual child/session IDs and captured event ordering.
  This is required for the currently pending B, C, D, E, F, G, H, and K cases.
  The recovered A/I/J/L observations remain guided/user-reported references and
  are not fresh-root evidence.

Record the required uppercase labels exactly: `CASE_ID`, `REQUEST_CLASS`,
`EXPECTED_ROUTE`, `ACTUAL_ROUTE`, `CHILD_SESSIONS`, `CONSULTATION_COUNTS`,
`MAX_SIMULTANEOUS_CHILDREN`, `NEGATIVE_CONTROLS`, `ROLE_PURITY`,
`DEPENDENCY_ORDER`, `RESULT_FIDELITY`, `COMPLETION_GATE`,
`USER_QUESTION_COUNT`, `FINAL_OUTCOME`, `ROUTING_RESULT`, and `NOTES`; also
retain operational proxies and evidence provenance. Native records must have
`ROOT_SESSION_ID` equal to `EVIDENCE_PROVENANCE.NATIVE_ROOT_SESSION_ID`; each
direct child's observed native session ID and `PARENT_SESSION_ID` must agree
with provenance and that root; and each event's `CHILD_REF`/`SESSION_REF` must
join to the same observed session and role. Mark every native event order as
`observed`. These internal-consistency checks do not authenticate a trace.
Keep expected routes separate from observed actual routes. Record native
session IDs only when actually observed. Event order must say `observed` or
`synthetic`; do not invent timestamps, IDs, consultation counts, or concurrency.
Record unknown metrics as `null`, not `0`. A final answer must not include
chain-of-thought.

For each case, reconcile all known work: every completed child terminates and
its actual result ID is consumed exactly once before completion. Unknown
execution means `COMPLETION_UNCONFIRMED` and no retry. Kael owns bounded
questions; reconcile work before asking, record `QUESTION_RESOLVED` before
dependent work, and do not start that work before the answer. Reasoner evidence
follow-up must be same-session, materially new, produced after its request,
delivered and consumed before follow-up. Record negative controls as observed
counts rather than inferred expectations. Static predicates in `qualify.py`
are marker-presence checks only.

## Current gate

The A–L matrix and synthetic/mutation suite are present. Recovered guided
outcomes above remain user-reported only; the current scoped corpus has no
native per-case records. Fresh-root evidence is pending for B, C, D, E, F, G,
H, and K only; A, I, J, and L are retained as reference/history, with no rerun
requested. The phase is **IN VALIDATION / PARTIAL**, not SHIPPED.
