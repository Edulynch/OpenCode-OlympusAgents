# Phase 11 — Integrated Routing Qualification (PARTIAL)

This is a focused evidence validator, not a routing/runtime implementation. The
checked-in A–L traces are `SYNTHETIC_TRACE`; their local `SYN-*` references and
ordered events are authored examples, not OpenCode root/child session IDs,
timestamps, guided runs, or proof of model behavior. Static marker checks mean
only that bounded policy text is present. The task owner separately reported
recovered guided outcomes and a reconciled B2 runtime observation (recorded
below and in `baseline.json`). Separately, verified native B3 exports/history
and CLI results are captured in `case-b3.native-trace.json`; verified native
Case C exports/history are captured in `case-c.native-trace.json`; native
Case D invocation history is captured in `case-d.native-trace.json`; the
original Case E1 failure and the later E2 root/child exports are captured in
`case-e.native-trace.json`, `case-e.root-session.export.json`,
`case-e2.native-trace.json`, `case-e2.root-session.export.json`, and
`case-e2.talos-session.export.json`; Case F's native root-only diagnosis is
captured in `case-f.native-trace.json` and `case-f.root-session.export.json`;
Case G's native record and root/Veyra/Thales projections are in
`case-g.native-trace.json`, `case-g.root.session-export.json`,
`case-g.veyra.session-export.json`, and `case-g.thales.session-export.json`.
Case H's native record and sanitized root/Veyra projections are in
`case-h.native-trace.json`, `case-h.root.session-export.json`, and
`case-h.veyra.session-export.json`.
B3, C, D, E2, F, G, H, and the separate Case K FAST/NORMAL profiles qualify their bounded
acceptance outcomes; E1 remains an observed historical routing failure and is
not rewritten as a pass. None of these native captures is inserted into the
synthetic trace corpus or reconstructed as a synthetic lifecycle.

## Automatic local commands

From the repository root, using the pinned Python 3.11 interpreter and standard
library only:

```text
uv run --python 3.11 python tests/phase11-integrated-routing/qualify.py
uv run --python 3.11 python -m unittest discover -s tests/phase11-integrated-routing -p "test_*.py" -v
uv run --python 3.11 python -m unittest discover -s tests/phase11-integrated-routing/fixtures/feature -p "test_*.py" -v
uv run --python 3.11 python -B tests/harness-core/qualify.py --safe-root-read-only
```

The first command validates the versioned case matrix, synthetic event semantics,
completion/evidence claims, separate B1/B2/B3/C/D/E1/E2/F/G/H/K reconciliations, the
bounded B3, C, and D native invocation captures, the original E1 failed-root
projection, the E2 root/child export projections and accepted Talos route, the
F root-only export projection and operational finding, and the G root/child
export joins, static fixture result, evidence-before-diagnosis order, and
conditional Thales follow-up semantics, the bounded H native reconciliation,
both K native profiles and their comparison (including message-span-only
overlap and flexible NORMAL writer-count semantics), and presence-only gate markers. It reports
`PHASE11_ARTIFACTS: PASS` when those artifacts are sound while overall
qualification remains `PHASE11_QUALIFICATION: PARTIAL` pending closure review
and the separate open review items. The second command
applies mutations to valid authored traces and bounded native captures, and
requires the prohibited variants to fail. The third command currently runs only the feature fixture's green
pre-feature compatibility tests. The future feature work must add acceptance
tests under that fixture and rerun this same discovery command for both
calculation and presentation, including the complete contract matrix; do not
treat the baseline scaffold suite as those tests. The Harness Core command
checks root-generated adapters without root rendering; it
retains idempotence, drift, and missing-output checks in its disposable fixture
under the approved Temp `opencode` area. It does not modify real generated
outputs. These commands do not start OpenCode, install packages, contact a
network, run a live agent, run the known-bad cart test, or claim a performance
result. `python -B` suppresses bytecode caches for that run.

Case B's currently checked-in feature fixture is intentionally a pre-feature
scaffold. `CartTotals` currently has only `subtotal_cents` and `total_cents`,
and presentation renders only those fields. The feature requires a real change
to both components: calculation first adds the `discount_cents` result field,
then presentation consumes that field. This result-field dependency is material
but does not require an elaborate work pipeline. Green scaffold compatibility
checks do not implement or qualify the discount feature. Fixture readiness (a
linked contract plus a coherent, passing scaffold) is not a `FRESH_ROOT_NATIVE`
observation and cannot produce a Case B fresh-root PASS.

## B3 native capture and validation boundary

`case-b3.native-trace.json` records `PHASE11_CASE_B_FRESH_ROOT_3` as
`FRESH_ROOT_NATIVE`. Its events are the seven distinct observed root subagent
call results plus the final root completion statement. Each event has an
`ORDER_BASIS` of `observed`; order integers are ordinal labels, never timestamps.
The four direct child sessions are unique; Nox's three and Vera's two root-call
results remain invocation counts, not extra child activations. Native call IDs
join the invocations, but `RESULT_ID`, timestamps, and maximum concurrency stay
`null` where not observed. The final root statement supports zero pending,
unconsumed, and unknown child results, while per-invocation consumption timing
and session-lifetime exact-once remain unknown. No consumption event is placed
after a later action to imply a timestamp.
Unobserved, unrelated gate facts remain `null` rather than being inferred from
the absence of an invocation.

The native record uses the canonical top-level evidence fields but has a bounded
invocation-level validator. The synthetic `validate_trace` lifecycle requires
one start/terminal/consumption sequence per child session and synthetic result
IDs; applying it to B3 would conflate repeated calls on resumed Nox/Vera
sessions and invent missing result IDs. Native validation instead checks the
fixed observed root/child joins, call identities and statuses, direct parents,
observed ordering, route reconciliation, aggregate completion, and preserved
unknowns. These consistency checks do not independently authenticate source
exports. Synthetic `traces.json` and its adversarial lifecycle checks are
unchanged.

The semantic feature route remains Kael -> Veyra -> Kovan -> Nox -> Vera. The
observed unique-session launch order is Kael -> Nox -> Veyra -> Kovan -> Vera
because initial Nox worktree isolation was a justified prerequisite. Nox later
resumed that same session for validation. The Veyra contract preceded Kovan
implementation; Kovan preceded Nox validation and Vera review. Vera's review
and source-review follow-up also came from the same original session. Efficiency
`ACCEPTABLE` is a qualification judgment, not measured latency.

## Case C native capture and validation boundary

`case-c.native-trace.json` records the verified `PHASE11_CASE_C_FRESH_ROOT`
history as `FRESH_ROOT_NATIVE`. It contains the two observed root invocation
creation/return pairs plus the final root completion statement, joined to the
unique Nox and Kovan child sessions. Observed event ordinals are not timestamps;
only the supplied Nox return and later Kovan-call creation epoch-millisecond
values are retained. Those observations support maximum direct-child concurrency
of one. Result IDs, per-invocation consumption times, session-lifetime
exact-once, retries, and duration remain unknown. The root's aggregate terminal
statement supports zero pending, unconsumed, and unknown children.

The expected product route is Kael -> Kovan. The actual unique-session family is
Kael -> Nox -> Kovan because Nox's read-only worktree-isolation verification was
a qualification prerequisite, not product diagnosis. The trace does not reorder
the observed route. Nox confirmed the separate disposable copy at the recorded
HEAD; the historical isolation Git-check exit code remains unknown.

Kovan's native record reports one changed path,
`fixtures/obvious/cart.py`, with subtraction corrected to multiplication under
the explicit fixture contract. The specified single test passed with exit 0;
Kovan also reported a successful `git diff --check`. The latter child result is
recorded separately and is not projected into the literal root terminal facts.
Argus's invocation and unique-session counts are explicitly zero, alongside the
other recorded forbidden-role controls. Efficiency `LEAN` is qualification
judgment, not measured performance. The B3 report's earlier historical pending
labels still include C; the C snapshot's pending set included D, E, F, G, H,
and K. Later D evidence supersedes that snapshot for current qualification state.

## Case D native capture and follow-up coverage boundary

`case-d.native-trace.json` records the supplied fresh-root native history as
invocation-level evidence. The observed session family is Kael -> Nox -> Veyra
-> Argus: Nox verified isolation only, Veyra gathered bounded evidence, and
Argus made one terminal diagnosis consultation using that already-collected
evidence. The product route is Kael -> Veyra -> Argus. The synthetic default D
trace remains the distinct valid iterative path where Argus requests evidence
and follows up in the same session; that request-triggered path retains all
same-session, new-evidence, delivery, consumption, and progress checks.

All three native tool deliveries are `completed`, and all child-session
execution outcomes are `succeeded`. The literal Nox and Veyra return statuses
were not supplied and remain `null`; Argus's literal `RETURN_STATUS` is
`INCONCLUSIVE`, matching `ARGUS_DIAGNOSTIC.STATUS` rather than being normalized
to `SUCCESS`. No functional violation or repair is established. Root execution
metadata is `succeeded`, while semantic `FINAL_OUTCOME` is `NEEDS_USER_INPUT`.
After all children were terminal and the root reported their results consumed,
Kael posed one bounded binary question. The question remains unresolved; this
reconciliation neither asks it again nor replays or repairs the case. Unknown
parent identity, result IDs, per-result consumption timing, and other
unsupported measures remain null. `LEAN` is a qualification judgment, not
latency.

Case D follow-up is `NOT_REQUIRED`, because Argus did not make an evidence
request. Separately,
`ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE: NOT_EXERCISED` means this native D
run did not demonstrate runtime follow-up. An optional genuine
evidence-requesting scenario remains open for final coverage review; this
coverage note is not a Case D blocker or an implicit pass.

## Case E1 native capture — historical routing failure, no rerun

`case-e.root-session.export.json` is a projection of the exact original public
OpenCode V2 export. It preserves the original user prompt, non-reasoning
assistant terminal text, message identities/timing, and root outcome. The export
was captured in memory with `sanitize=false`; all reasoning blocks were removed
before writing, secrets were checked/redacted, and raw export/provider state was
not persisted. The direct-child API query returned an empty list with no next
cursor; the exported messages contained no tool-call records. No other session,
private runtime, or worktree filesystem was accessed.

The root execution outcome is `succeeded`, but the observed product route is
Kael only instead of the Case E matrix's Kael -> Talos. The root answer correctly
classifies the established MEMBER/account-deletion behavior as
`CONFIRMED_SECURITY_DEFECT`, identifies the server-enforced ADMIN-only boundary,
states the non-ADMIN-denied-without-deletion invariant, and proposes safe
synthetic identities with mocked deletion operations. It reports no exploit and
no file changes. Behavior/security/safety/role purity and negative Argus control
are PASS; Talos activation, routing, and fresh-root acceptance are FAIL. The
qualification artifact validator passes only the evidence reconciliation; it
does not turn this product route into a pass. See
`docs/DEFECT-PHASE11-CASE-E-ROUTING.md` for the bounded rule-gap record.

E1 remains an immutable failed historical attempt; the evidence does not
authorize replay or rewrite of that root. E2 below is the later, separate
fresh-root acceptance that closes current Case E. Phase 11 remains PARTIAL;
Cases A-D are unchanged, and Argus same-session follow-up runtime coverage
remains `NOT_EXERCISED`.

## Case E2 native capture — current Case E acceptance

`case-e2.root-session.export.json` and `case-e2.talos-session.export.json` are
reasoning-redacted projections of the completed E2 root and its direct Talos
child. The original exports were read in memory through the public OpenCode V2
read-only API; two root reasoning blocks were removed, the child export had no
reasoning blocks, no secret-pattern matches required redaction, and raw exports
were not persisted. Exact directory metadata paths are not retained, and no
disposable-worktree filesystem, private runtime, or other session was accessed.
The root and child metadata match the supplied disposable-path context; the root
has an explicitly null parent and succeeded, while the Talos child has the root
as parent and also succeeded.

- Root Kael session `ses_ef7eb1d45ffet0gMtEEUam8R4U` is titled “Diagnosing MEMBER
  account-deletion authorization boundary”; its prompt records starting HEAD
  `3e5b2af2c15f9ef2775be3c3f5667edd4db0bdde`.
- The complete two-page root direct-child listing contains exactly Talos
  `ses_ef7ea7bf7ffe4U23sL7M1mi60p`, titled “Diagnose account deletion
  authorization,” with the root as parent and outcome `succeeded`. The root
  export has exactly one completed `subagent` call, ID
  `call_FzRbkaOiUp41wcA0DcJfrrPw`, whose observed Talos input and child-session
  metadata join to that same child and task label
  `PHASE11_CASE_E2_FRESH_ROOT`. The child export has no tool-call records.
- The observed product route is Kael -> Talos, matching the Case E security-bug
  matrix. Talos confirmed the established MEMBER/ADMIN authorization defect and
  advised enforcing trusted authenticated ADMIN authorization before deletion
  side effects. Its implementation mechanism remains unknown. No tools, tests,
  repository inspection, exploit, or file mutation were attempted by Talos.
- The root terminal states that the diagnosis is complete, all required child
  work is terminal and consumed, and no work remains. It does not contain a
  literal E2 `PASS`; Case E2 acceptance is a reconciliation judgment from the
  observed route, diagnosis, safety limits, and root completion statement.
  Result IDs, per-invocation consumption timing, session-lifetime exact-once,
  concurrency, and timing metrics remain `null`; native permission UI/decision
  were not observable.
- E2 behavior, security classification, safety, role purity, Talos activation,
  negative Argus control, routing, result fidelity, completion ownership, and
  fresh-root-native acceptance are PASS. E1 remains
  `NATIVE_EXECUTED_ROUTING_FAIL` with actual route Kael only; E2 does not rewrite
  or replace that historical fact. E2 closes current Case E acceptance.

Phase 11 remains **IN VALIDATION / PARTIAL**, not SHIPPED. At the E2 snapshot,
pending fresh-root work was F, G, H, and K; the later F reconciliation below
removes F from current pending. `ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE`
remains `NOT_EXERCISED`; E2 did not exercise that separate runtime behavior.

## Case F native capture — operational issue, no product bug established

`case-f.native-trace.json` and `case-f.root-session.export.json` preserve the
supplied completed Case F root evidence without rerunning or re-querying it. The
root is Kael `ses_ef6a0d293ffeggS6H8JnsTARAW`; its parent-session field was
`NOT_EXPOSED`. The supplied prompt records starting HEAD
`627946defc9eef0eb25e15d9d8b2865b7d6960ad`; the reconciliation did not verify
that HEAD against a filesystem. The directory-filtered native listing was
exhausted and contained exactly this root. No filesystem audit was performed.
The Nox collector is separate provenance, not a member of the historical Case F
root family.

The complete root export has three messages and no export pagination. The
direct-child query is empty, and the root export has no tool-call records or
nested tool wrappers. Expected and actual routes are both `Kael` only. All
recorded specialist counts are zero, including Argus and Talos; no root runtime
event sequence was reconstructed. Maximum simultaneous children, runtime and
wall-clock durations, retry count, result IDs/consumption timing, and
session-lifetime exact-once remain unknown (`null`). Permission UI and decision
are `NOT_OBSERVABLE`.

The visible terminal classifies the unavailable plain `python` command as an
operational issue because the test command did not start. It establishes neither
a product bug nor a security bug, recommends using the already-known
`uv run --python 3.11 python` runtime for the original targeted command, and
does not execute tests during diagnosis. It reports no install, no file changes,
no unresolved work, required child work terminal and consumed, and no work
remaining. The visible projection omits one reasoning block and provider state
and snapshots; the raw export was not persisted. Nox did not assess secret
filtering; the supplied visible text was inspected before persistence and no
secret credentials were observed, without asserting a filter count.

Case F behavior, operational classification, no-invented-product/security-bug,
negative Argus/Talos controls, no-install, role purity, completion ownership,
routing, and `FRESH_ROOT_NATIVE` acceptance are PASS. `LEAN` is a qualification
judgment, not measured efficiency. E1 remains a failed historical Case E route;
E2 remains the separate accepted Case E result. F and G are no longer pending;
at the F snapshot, H and K remained fresh-root work and Phase 11 stayed
**IN VALIDATION / PARTIAL**.

## Case H native capture — bounded third-party defect containment

`case-h.native-trace.json` and its root/Veyra projections reconcile the exact
completed public sessions. The root is Kael
`ses_ef34594abffexNPYTX6t5yrosg`; its parent is not exposed. Its prompt supplied
the starting HEAD, which this reconciliation did not filesystem-verify. The
paginated direct-child listing returned Veyra
`ses_ef344fba2ffes5dwAj9MP0A0kc` on page one and no additional child on page two;
Veyra's public parent ID matches the root. Root and child exports contain five
and ten messages respectively. The observed product route is Kael -> Veyra, with
one completed root subagent invocation. The public `executed=false` flags remain
alongside `state=completed`; they are not interpreted as proof of non-execution.
Result IDs, timing, concurrency, and permission UI/decision remain unknown.

Veyra's original source tool calls target only `opencode.jsonc` and
`.opencode/agents/kael.md`; the sanitized projection retains the normalized
paths and call identities, not file contents, arguments, or tool results. The
root terminal classifies the established third-party OpenCode runtime defect as
`OPERATIONAL_ISSUE`, not an Olympus product-code bug. No specific local runtime
version or concrete version/configuration action is supported. Existing result
reconciliation, no blind retry, `COMPLETION_UNCONFIRMED` when completion is
unknown, and positive non-start evidence before retry remain the supported
policy. No upstream patch, vendor, or fork was attempted. The projection removes
28 reasoning blocks, records zero matches for the bounded credential-pattern
scan, omits provider state/snapshots and all raw export/source text, and persists
no raw export. This reconciliation performed no Case H execution, runtime
reproduction, or disposable-worktree access. The original terminal reports no
original-run file changes. At the H snapshot, H was accepted natively and K was
the only pending case; Phase 11 remained **IN VALIDATION / PARTIAL**.

## Case K native capture — separate FAST and NORMAL roots

`case-k.native-trace.json` records the task-supplied observations for the two
distinct fresh Kael roots. Both began at the same supplied HEAD in independent
disposable worktrees and used the same four fixture paths. FAST's four useful
Kovan sessions each own one different target and all four supplied writer
message spans overlap. NORMAL's observed useful count is one; semantic NORMAL
acceptance permits a useful count from one through the four-writer ceiling. The
unchanged synthetic `K_NORMAL` trace is an illustrative two-writer example, not
a count requirement.

The native artifact preserves the supplied writer spans and root/child
identities without reconstructing a total event order or fabricating result
IDs, message IDs, root directories, UI decisions, or consumption timing. FAST C
and the NORMAL writer each continued in their original session after an initial
blocked result with no tool attempt/execution and no changes; neither
continuation is a replacement or additional writer. Post-writer Nox
integrity/diff-check sessions are shown separately and excluded from writer
counts. Four overlapping message spans do not establish uninterrupted work,
scheduler/CPU/process parallelism, or wall-clock speedup. The supplied aggregate
root completion facts support required-child completion and reconciliation.

FAST, NORMAL, and their comparison pass. No fresh-root native cases or pending
labels remain. Earlier snapshots that list K as pending remain historical and
unchanged. Phase 11 is still **PARTIAL**, closure-review-ready, and not SHIPPED.
This reconciliation used only task-supplied observations and performed no
runtime recapture. Independent Nox validation is pending.

## Remaining fresh-root work and historical prompts

No current fresh-root case remains unrun. H, F, G, E2, K FAST/NORMAL, and
isolated B3, C, and bounded native D are accepted; E1's routing failure remains
immutable history. A, I, J, and L
prompt references/history are retained below but are not new rerun requests. Do
not reuse a guided/current session as a fresh root. Confirm the effective root
agent, child parentage and actual roles from native session evidence before
accepting a case. Scope each live edit to the disposable
qualification fixture; retain the original project untouched. Stop rather than
retry if an execution result is unknown. The prompts below are starting points,
not pre-recorded results. For a fresh native observation, use the canonical top
fields from `native-trace.template.json` and preserve unknown values as `null`
(never zero); capture invocation-level native facts without fabricating the
synthetic per-session lifecycle.

- `REFERENCE_ONLY PHASE11_CASE_A_GUIDED_RECOVERY` — prior prompt reference: “In a disposable copy, change only
  `fixtures/simple/message.txt` to `Hello Phase 11 ready`. Keep this to one
  scoped edit and verify the exact requested text.”
- `ACCEPTED PHASE11_CASE_B_FRESH_ROOT_3` — completed native evidence is in
  `case-b3.native-trace.json`; no rerun is requested. Original prompt: “In a **clean separate
  disposable project copy** and a new verified Kael root (not the canonical
  qualification repository), read
  `tests/phase11-integrated-routing/fixtures/feature/contract.md` and
  inspect `tests/phase11-integrated-routing/fixtures/feature/`. Implement the
  specified cart discount feature within that fixture, preserving the legacy
  no-discount API and adding/running tests for the full acceptance contract.
  The contract defines the calculation-result field that presentation must
  consume; sequence that dependency proportionately. Atlas is optional and is
  not expected for this bounded producer/consumer dependency alone. Ask a bounded
  question if a material ambiguity remains. Orin is not qualified by this
  bounded case.”
- `ACCEPTED PHASE11_CASE_C_FRESH_ROOT` — native evidence is in
  `case-c.native-trace.json`; no rerun is requested. Original prompt: “In a
  disposable copy, fix the obvious `calculate_total` contract defect in
  `fixtures/obvious/cart.py`; then run its unit test. The fixture is currently
  intentionally wrong, so do not treat its pre-fix failure as a qualification
  failure.”
- `ACCEPTED PHASE11_CASE_D_FRESH_ROOT` — native evidence is in
  `case-d.native-trace.json`; no rerun or renewed question is requested. Veyra's
  precollected bounded evidence was supplied to one Argus consultation. Argus
  correctly stopped `INCONCLUSIVE` / `CAUSE_UNCONFIRMED`; the root asked one
  bounded binary question after child completion. No functional violation or
  repair is established. Runtime same-session follow-up remains
  `NOT_EXERCISED` separately from Case D acceptance.
- `HISTORICAL_FAILURE PHASE11_CASE_E_FRESH_ROOT` — completed native
  evidence is in `case-e.native-trace.json` and the reasoning-redacted original
  export projection is in `case-e.root-session.export.json`. The original root
  succeeded and supplied correct behavior/security/safety findings, but observed
  no child session; expected Kael -> Talos, actual Kael only. This is a product
  routing failure retained for history, not a current acceptance result or an
  instruction to rerun. E2 below separately closes current Case E acceptance.
  Original prompt excerpt, retained for evidence only: “Classify this
  bounded hypothetical defect: a MEMBER can delete another user's account
  although the stated contract is ADMIN-only. Explain the security boundary and
  safe validation; do not attempt an exploit, edit, or broad audit.”
- `ACCEPTED PHASE11_CASE_E2_FRESH_ROOT` — completed native evidence is in
  `case-e2.native-trace.json`; reasoning-redacted root and Talos projections are
  in `case-e2.root-session.export.json` and `case-e2.talos-session.export.json`.
  The observed route is Kael -> Talos, with one succeeded direct child joined to
  one completed root subagent call. E2 closes the latest Case E acceptance while
  preserving E1's `NATIVE_EXECUTED_ROUTING_FAIL` history. No diagnosis replay,
  exploit, tests, or code-level mechanism claim is made.
- `ACCEPTED PHASE11_CASE_F_FRESH_ROOT` — native evidence and safe root-export
  projection are in `case-f.native-trace.json` and
  `case-f.root-session.export.json`. The complete root family is Kael only;
  native API evidence records no direct child, tool call, or nested wrapper.
  The terminal classifies unavailable plain `python` as an operational issue,
  establishes neither a product nor security bug, recommends the known `uv`
  Python 3.11 runtime without executing tests, and reports no install or file
  changes. Root parentage was `NOT_EXPOSED`; its supplied starting HEAD was not
  independently filesystem-verified during reconciliation. No rerun is
  requested. Phase 11 remains PARTIAL.
- `ACCEPTED PHASE11_CASE_G_FRESH_ROOT` — native evidence is in
  `case-g.native-trace.json`; the exact completed root, Veyra, and Thales
  projections are in the three `case-g.*.session-export.json` files. Veyra's
  bounded read established the static same-input sequence PASS, TIMEOUT, PASS;
  it is recorded inconsistency, not reproduced runtime flakiness or cause.
  The observed order is Kael -> Veyra -> Thales; Nox performed no measurement.
  Thales found no materially necessary extra evidence, so one consultation and
  `NOT_REQUIRED` follow-up are correct. If material new evidence is requested,
  collect and consume it before continuing the same Thales session. That
  same-session follow-up remains `NOT_EXERCISED` here. The separate synthetic G
  example retains its iterative route; no Case G rerun is requested. The exports'
  `executed=false` flag coexists with `state=completed` and succeeded linked
   sessions; it is not treated as proof of non-execution. Result IDs and
   per-call consumption timing remain unknown. Veyra's original bounded fixture
   read is present in its session projection; the reconciliation itself did not
   access the disposable worktree. Root isolation was task-supplied and was not
   independently filesystem-audited. The original terminal reports no original
   run file changes; the ten reconciliation paths are listed in
   `RECONCILIATION_FILES_CHANGED` in the native trace.
- `ACCEPTED PHASE11_CASE_H_FRESH_ROOT` — root/Veyra native evidence and sanitized
  projections are recorded in `case-h.native-trace.json`,
  `case-h.root.session-export.json`, and `case-h.veyra.session-export.json`.
  The sole child is Veyra; bounded reads/greps are limited to `opencode.jsonc`
  and `.opencode/agents/kael.md`. Classification is `OPERATIONAL_ISSUE`, with
  existing reconciliation as the safest supported level, no blind retry, and
  no unapproved patch/vendor/fork. No version/config action is supported by the
  bounded evidence. At the H snapshot, K was still pending; the later Case K
  reconciliation below resolves it. Phase 11 remains PARTIAL pending closure review.
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
- `ACCEPTED PHASE11_CASE_K_FRESH_ROOT` — both separate native profiles and their
  comparison are captured in `case-k.native-trace.json`. FAST records four
  useful Kovan writers on disjoint paths; NORMAL records one useful Kovan writer
  in this observation. The two-writer synthetic NORMAL trace remains an
  illustrative example, not a native count rule. Message-span overlap is not
  process/scheduler concurrency or wall-clock speedup. No K rerun is requested.
- `REFERENCE_ONLY PHASE11_CASE_L_NEGATIVE_AUTOMATIC_AEGIS_RECOVERY` — prior prompt reference: “Make the same harmless fixture-only
  edit as case A in a normal project request. Do not enter `/maintain`.” Verify
  Kael does not launch Aegis; this is not an instruction to test or invoke
  Aegis. Do not repeat the recovered negative automatic-Aegis control solely for
  completeness.

## Recovered user-reported observations

The task owner reported that Case B attempt 1 stopped before implementation
because the promised contract was absent. Per that report, it made no changes
and ran no validation; Kael correctly asked for the missing requirement. This
is `FIXTURE_DEFECT`, not a routing defect and not a Case B PASS. The task owner
reported `Question Barrier PASS` and no-invention behavior as positive
`USER_REPORTED` evidence only. No native trace or session ID was supplied for
that attempt.

The task owner then supplied the authoritative observation
`PHASE11_CASE_B_FRESH_ROOT_2`. This record is preserved as a reconciliation, not
as reconstructed native event data:

- Root Kael `ses_efd70d361ffecywLukxPk5m1Sv`, outcome `succeeded`.
- Direct children, all `succeeded` with required results consumed: Veyra
  `ses_efd706277ffeSqUTO9GumJKt5B`; Kovan
  `ses_efd6d87f4ffe2j4zsTzy1mAv0D`; Nox
  `ses_efd69a153ffe0ntGQoaZVOXyZi`; Vera
  `ses_efd69a151ffeftr0qNcEM5VEle`.
- Reported `ACTUAL_ROUTE`: `Kael -> Veyra -> Kovan -> Nox / Vera`.
- `CASE_B2_RUNTIME_BEHAVIOR: PASS` and
  `CASE_B2_NATIVE_ROUTING_EVIDENCE: VALID_OBSERVATION`; however,
  `CASE_B2_FRESH_ROOT_ISOLATION: FAIL` because the run used the canonical
  qualification repository instead of the intended separate disposable copy.
  Therefore `CASE_B2_FRESH_ROOT_ACCEPTANCE: PARTIAL`, not PASS.
- The report says `domain.py` and `presentation.py` were modified and
  `test_feature.py` created; the fixture suite passed 14/14. Vera's final result
  was `ACCEPT` with no findings.
- Atlas did not activate; this is not a routing defect. Planning is optional
  unless execution dependencies materially justify a separate planner. The
  bounded calculation-to-presentation producer/consumer dependency did not
  justify one. Veyra efficiency was `ACCEPTABLE`; no material redundancy was
  established.
- Kovan initially returned `BLOCKED` for a task/grant identity mismatch. Kael
  consumed that result, confirmed no tool execution or edit occurred, corrected
  only the grant identity, and resumed the same Kovan session. This records
  contract friction, not a blind retry or proven material defect. Vera's initial
  parent delivery was interrupted; the original Vera session was retained and
  reconciled with `RESULT_RECONCILIATION: PASS`. No upstream correlation issue
  fix is claimed.
- Event counts/order, consultation counts, Nox/Vera relative order, and
  concurrency remain unknown (`null`). The synthetic A–L corpus remains
  synthetic; no native event sequence is inferred.

The current canonical checkout was separately inspected and remains a clean
pre-feature scaffold: tracked `domain.py`, `presentation.py`, and
`test_scaffold.py`; no `test_feature.py`; all four scaffold checks pass. This
current-tree check is distinct from the B2 report of that session's edits; no
feature delta or explanation for the differing snapshots is inferred, and this
corpus task did not change the fixture. B2 remains `PARTIAL` because isolation
failed; later isolated B3 independently passed and does not rewrite B2's result.

## Isolated B3 native result

The verified root is Kael `ses_efce702a8ffeKcoRaBYMFH9lxa`, outcome
`succeeded`; root and Nox's isolation-verified directory both resolve to
`C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-b3`. Nox verified
isolation and HEAD `ded1f69cbeadf5d21cb9b6b31d5df10123b57990`; the evidence
claims verification only and does not claim worktree creation. Unique direct
child sessions were
Nox `ses_efce6a350ffeLULhF1Hf7l39qJ`, Veyra
`ses_efce5cd8bffexU0SIHi67Y39zP`, Kovan
`ses_efce3ffadffekeRXxYxKkSWsxs`, and Vera
`ses_efcde45cdffe6X5eJbStlshoYu`; all terminated succeeded under that root.

Seven distinct root subagent call results were observed: Nox isolation PASS;
Veyra contract SUCCESS; Kovan implementation PARTIAL while the runtime was
unavailable; same-session Nox validation BLOCKED because Python aliases were
unavailable and zero tests ran; Vera review SUCCESS with no material defects
and tests unverified; same-original-session Vera source review SUCCESS with no
edits; and same-session Nox installed-Python validation SUCCESS (Python
3.11.17, 13 tests passed). The final root reported source integrity and
contract coverage PASS, Vera ACCEPT, no unresolved work, and all required child
results terminal and consumed. Historical runtime exit code, result IDs,
timestamps, concurrency, and session-lifetime exact-once remain unknown. No B3
rerun was performed by corpus reconciliation.

The observed terminal snapshot is tied to root message
`msg_1048ed1e5001AE9cC6bTYFgV3z`: `WORKTREE_ISOLATION PASS`; Python 3.11.17
installed through uv; `TEST_RESULT PASS`; `TEST_COUNT 13`; contract coverage and
source integrity PASS; Nox PASS; Vera ACCEPT;
unresolved work NONE; required children terminal and consumed YES;
`CASE_B_FRESH_ROOT_3 PASS`; nothing running. The validator binds these observed
terminal facts to isolation, runtime, route classification, and completion
records, while keeping expected outcome provenance separate from native export
provenance.

The recorded `TEST_COMMAND` is:

```text
uv run --python 3.11 python -B -m unittest discover -s tests/phase11-integrated-routing/fixtures/feature -p "test_*.py" -v
```

The semantic workflow route is Kael -> Veyra -> Kovan -> Nox -> Vera. The
observed unique child-session launch order is Kael -> Nox -> Veyra -> Kovan ->
Vera because Nox isolation was a justified prerequisite; the route is not
reordered to conceal that fact. B3 classifications are `CASE_B_FRESH_ROOT_3`,
isolation, routing, role purity, negative controls, completion ownership, and
result fidelity PASS; efficiency is ACCEPTABLE as judgment, not a measurement.
Case B acceptance is PASS while Phase 11 remains PARTIAL.

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
- `FRESH_ROOT_NATIVE`: observed native evidence from a separately verified Kael
  root, with actual root identity and any observed child/tool records and order.
  B3, C, D, E2, F, G, H, and both K profiles are accepted; E1's captured native
  routing failure remains historical. B2's
  routing observation is valid context but failed isolation. The recovered A/I/J/L
  observations remain guided/user-reported references and are not fresh-root
  evidence.

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

For synthetic cases, reconcile each completed child's terminal and actual
result-ID consumption exactly once. For native invocation-level captures,
record the observed aggregate child-completion statement without inventing a
per-invocation result ID or consumption time; leave session-lifetime exact-once
unknown unless directly established. Unknown execution means
`COMPLETION_UNCONFIRMED` and no retry. Kael owns bounded
questions; reconcile work before asking, record `QUESTION_RESOLVED` before
dependent work, and do not start that work before the answer. Reasoner evidence
follow-up must be same-session, materially new, produced after its request,
delivered and consumed before follow-up. Record negative controls as observed
counts rather than inferred expectations. Static predicates in `qualify.py`
are marker-presence checks only.

## Current gate

The A–L matrix, unchanged synthetic trace corpus, expanded mutation coverage,
and B3/C/D/E1/E2/F/G/H/K native records are present. Case B1 remains a fixture
defect with Question Barrier PASS; B2 runtime behavior remains PASS but
isolation/acceptance remains PARTIAL; B3, C, D, E2, F, G, and H fresh-root native
acceptance and K FAST/NORMAL/comparison are PASS. E1 remains a historical
Talos-routing failure, while E2 closes current Case E acceptance. No current
fresh-root native case is pending. D did
not exercise Argus follow-up runtime
coverage, which remains a separate open review item. A/I/J/L observations
remain guided/history-only, with no rerun requested. The overall phase is **IN
VALIDATION / PARTIAL**, not SHIPPED.
