# Phase 11 baseline evidence — POLICY_BASELINE

Captured before any working-tree file edit. Repository root was
`C:/Users/BLAUTECH/OneDrive/WORKSPACE/Personal/Tools/OpenCode-OlympusAgents`;
initial branch `master`, `HEAD` and local `origin/master` all resolved to
`a83847b84d6603aed144f5a8ce4b77de8a48fe32`, and the initial tracked working
tree was clean. The qualification branch was created only after the expected
master commit and absence of a branch-name collision were checked.

## Existing qualification evidence

Task context supplied the prior Nox session
`ses_effeefaa9ffeomSljdRv5MoyCf`: `routing-constraints`, `trivial-fast-path`,
and `preflight` were reported static PASS, each run twice. These are duplicate
static suite runs, not independent cases or live routing evidence. Other suites
were `NOT_RUN` by that baseline due to conservatively scoped side effects or
excluded paths; that does not mean they failed.

Before writing, this child re-ran the scoped existing `trivial-fast-path`
qualification twice; both invocations passed. One scoped
`routing-constraints` invocation failed at the static assertion
`POLICY_CONSTRAINT_SEMANTICS` after four preceding assertions passed. This is
recorded as a mismatch between the supplied Nox report and the writer's single
static-script attempt. No diagnosis, retry, canonical edit, or claim of live
routing failure is made. The preflight suite was not independently rerun.

## Source fingerprints and refs

| Asset | SHA-256 before edits |
|---|---|
| `.opencode/agents/kael.md` | `894B7BC1E2EE6E057286C85A6E9889C21C33D7238BD0A8A7F04F6CDD092E4C1D` |
| `olympus/policies/routing.md` | `6BA11AA2EA92E16AACBA218DA2E995D3A7F61BDA2399F1D8ABFE93F10F0D838A` |
| `olympus/policies/orchestration.toml` | `633E978389320E7CD1D897DAE828B03AACE924402E7E5470F8904993EEE96515` |

The `v0.4.2` annotated object `bc30cb6ac41e85513d03368dea73241b8c1de3c6`
peeling to `591e8bcf8915da4805001abfb76e7d853217ef6b`, and the configured
origin URL, are recorded from Kael's assignment context; remote write access
was not verified and the release ref is not `HEAD`.

## Qualification state

`POLICY_BASELINE` fingerprints and bounded marker presence do not prove runtime
behavior. The authored A–L files in this scope provide only
`SYNTHETIC_TRACE` positives and mutation negatives. No guided current-session or
fresh-root native evidence was captured at this baseline. At that time, A–L
were marked pending under the original labels. The later recovery report below
recorded B, C, D, E, F, G, H, and K as pending at that point; the subsequent B3
reconciliation below supersedes B's pending status. Phase 11 remains
**IN VALIDATION / PARTIAL**.

## Later recovery report supplied for P11-FIX-20261003

The task owner subsequently reported Case A `PASS` guided, Case I `PARTIAL`
guided with its useful baseline missing, Case J `PASS` guided, and Case L
negative automatic-Aegis control `PASS`. These are retained as
`USER_REPORTED_RECOVERED`, not as inspected native traces or fresh-root results.
No case-specific native session IDs were supplied in this repository; the
recovery session IDs below identify writer/reviewer recovery sessions, not
qualification-case roots. No recovery rerun was performed.

- Old Kovan writer recovery: `ses_effe57255ffeJWL1K6kuhu8Fr1` — `PARTIAL`.
- Vera review recovery: `ses_effb08273ffebb6fzuHwVmxilk` — `PARTIAL/RETRY`,
  terminal succeeded.

The current scoped trace corpus remains synthetic. At the time of this recovery
report, fresh-root native qualification remained pending for B, C, D, E, F, G,
H, and K. The later isolated B3 native result is recorded separately below; at
that B3 snapshot only C, D, E, F, G, H, and K were still listed as pending.
A, I, J, and L prompts are
retained as reference/history; no rerun is requested for the recovered A/I/J/L
observations or I/J negative controls.

## Gate C mutation-coverage correction — P11-NOX-COVERAGE-FIX-20261003

Task context reports that terminal Nox session
`ses_eff5a0de1ffekZ6Qna6AISnN6g` found missing persistent coverage for global
strict event ordering, result consumption before terminal, and a
`FRESH_ROOT_NATIVE` root-only relabeling. Nox reported that the validator already
rejected these adversaries, so no validator implementation change was requested.
Three unit mutations now persist those checks. They operate on in-memory copies
of synthetic trace A only; `traces.json` remains unchanged, and the mutations
are not native evidence or an authenticity claim.

The previously reported suite count was 25 tests. After these additions, the
requested local unittest command ran **28 tests, all passing**. The Phase 11
qualifier exited 0 with its expected `PARTIAL` native-qualification status, and
`git diff --check` passed.

## Safe root full-output coverage correction — P11-VERA-CORRECTION-20261003

Task context supplied Vera review session `ses_eff484aa4ffe7bBnNnwNJRZ1YH`
(`PARTIAL/RETRY`) and reported Nox's terminal success. Vera's sole material
finding was that the safe-root snapshot covered the 28 per-harness outputs but
omitted the shared `docs/HARNESS-CAPABILITIES.md` included by all-mode output
enumeration. The bounded test-only correction now snapshots
`renderer.outputs_for(ROOT, "all")` and runs the renderer's read-only `all`
check as well as the individual harness checks. The root-render guard and
disposable fixture checks remain in place.

The safe qualification observed 29 managed outputs before and after checks.
`docs/HARNESS-CAPABILITIES.md` retained SHA-256
`f5c65234c198538399745052b6441e48bd86496501a62a8bcf9a333b1e161e97` and
mtime_ns `1790989597071443300` in both snapshots; the all-output hash/mtime
comparison passed. No root render occurred and the generated document was not
modified. The harness-core safe qualification passed; the Phase 11 suite ran
28 tests, all passing; the qualifier exited 0 with expected `PARTIAL` status;
and `git diff --check` passed. Prior manual A1–A8 results were not rerun or
altered.

## Case B runtime reconciliation — `phase11-b2-reconcile`

The task owner supplied B1 and B2 facts authoritatively; this task did not rerun
Case B or reconstruct native event records.

- **B1:** the promised contract was absent, classified `FIXTURE_DEFECT`; the
  `Question Barrier` passed. No native root ID or trace was supplied. This is
  not a routing defect and not a Case B pass.
- **B2:** label `PHASE11_CASE_B_FRESH_ROOT_2`; root Kael
  `ses_efd70d361ffecywLukxPk5m1Sv`, outcome `succeeded`. Reported direct
  children, each `succeeded` with its required result consumed:
  - Veyra — `ses_efd706277ffeSqUTO9GumJKt5B`
  - Kovan — `ses_efd6d87f4ffe2j4zsTzy1mAv0D`
  - Nox — `ses_efd69a153ffe0ntGQoaZVOXyZi`
  - Vera — `ses_efd69a151ffeftr0qNcEM5VEle`
- Reported route: `Kael -> Veyra -> Kovan -> Nox / Vera`.
  `CASE_B2_RUNTIME_BEHAVIOR: PASS` and
  `CASE_B2_NATIVE_ROUTING_EVIDENCE: VALID_OBSERVATION`; the run used the
  canonical qualification repository rather than the intended separate
  disposable copy, so `CASE_B2_FRESH_ROOT_ISOLATION: FAIL` and
  `CASE_B2_FRESH_ROOT_ACCEPTANCE: PARTIAL`.
- The user report records `domain.py` and `presentation.py` modified,
  `test_feature.py` created, fixture tests `14/14` passing, and Vera final
  `ACCEPT` with no findings.
- Atlas did not activate and was not a routing defect. Planning is optional
  unless execution dependencies materially justify a separate planner; this
  bounded producer/consumer dependency did not. Veyra efficiency was
  `ACCEPTABLE`; no material redundancy was proven.
- Kovan initially returned `BLOCKED` because of a task/grant identity mismatch.
  Kael consumed the result, confirmed no tool execution or edit, corrected only
  the grant identity, and resumed the same Kovan session. This is recorded as
  contract friction, not a blind retry or proven material defect. Vera's initial
  parent delivery was interrupted; the same original Vera session was retained
  and reconciled, `RESULT_RECONCILIATION: PASS`. No upstream correlation issue
  fix is claimed.
- Native event count/order, consultation counts, relative Nox/Vera order, and
  concurrency remain unknown (`null`). The authored trace corpus remains
  `SYNTHETIC_TRACE`; the B2 record is separate and is not a synthetic or native
  event sequence.

The current canonical checkout was inspected separately before edits. Its
feature fixture is still the tracked pre-feature scaffold (`domain.py`,
`presentation.py`, `test_scaffold.py`); `test_feature.py` is absent and
untracked. The four scaffold compatibility tests passed. B2's report of that
session's changed files is preserved as historical runtime context; the current
clean scaffold snapshot does not establish what happened to those session
changes, and no explanation or feature delta is inferred. This task did not
write any fixture files.

The corrected synthetic Case B example expects bounded no-Atlas routing and
retains only the mandatory implementation-before-tests and
implementation-before-review edges. Complexity alone is not a Planning Gate
justification. B2's recorded acceptance remains PARTIAL; the later isolated B3
native result below independently qualifies Case B. The corpus reconciliation
did not rerun B3 or launch/access its worktree.

## Isolated Case B3 native reconciliation — P11-B3-corpus

The verified native evidence supplied with this task is captured in
`case-b3.native-trace.json` as `FRESH_ROOT_NATIVE`. It came from Nox's read-only
OpenCode API exports/history and CLI validation results; this corpus writer did
not re-export data, inspect the B3 worktree, create/resume the root, or rerun the
case.

- Root Kael `ses_efce702a8ffeKcoRaBYMFH9lxa`, parent `null`, terminal
  `succeeded`; root directory and Nox's isolation-verified directory both
  resolve to `C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-b3`.
  Nox verified isolation and HEAD
  `ded1f69cbeadf5d21cb9b6b31d5df10123b57990`; the evidence claims verification
  only and makes no worktree-creation claim.
- Four unique direct child sessions, all terminal `succeeded`, in observed
  launch order: Nox `ses_efce6a350ffeLULhF1Hf7l39qJ`; Veyra
  `ses_efce5cd8bffexU0SIHi67Y39zP`; Kovan
  `ses_efce3ffadffekeRXxYxKkSWsxs`; Vera
  `ses_efcde45cdffe6X5eJbStlshoYu`.
- Seven ordered, distinct completed root subagent call results were observed:
  Nox isolation `SUCCESS`; Veyra contract `SUCCESS`; Kovan implementation
  `PARTIAL` (runtime unavailable); same-session Nox validation `BLOCKED`
  (Python aliases unavailable, zero tests); Vera review `SUCCESS` (no material
  defects, tests unverified); same-original-session Vera source review
  `SUCCESS` (no edits); same-session Nox validation `SUCCESS` (Python 3.11.17,
  13 passed). The final root reported contract coverage and source integrity
  PASS, Nox PASS, Vera ACCEPT, no unresolved work, and all required child
  results terminal and consumed.
- The observed root terminal snapshot at
  `msg_1048ed1e5001AE9cC6bTYFgV3z` records `WORKTREE_ISOLATION: PASS`,
  `PYTHON_RUNTIME: Python 3.11.17 installed through uv`, the exact fixture
  unittest command, `TEST_RESULT: PASS`, `TEST_COUNT: 13`, `CONTRACT_COVERAGE:
  PASS`, `SOURCE_INTEGRITY_AFTER_TEST: PASS`, `NOX: PASS`, `VERA: ACCEPT`,
  `UNRESOLVED_WORK: NONE`, `REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED: YES`,
  `CASE_B_FRESH_ROOT_3: PASS`, and nothing running. `RESULT_FIDELITY` keeps the
  expected terminal class from task context separate from these observed
  exported terminal facts.
- Invocation counts are Nox 3, Veyra 1, Kovan 1, Vera 2; unique child sessions
  are Nox 1, Veyra 1, Kovan 1, Vera 1. Tool-call IDs join the seven invocation
  results; they are not `RESULT_ID`s. Each return was observed once; aggregate
  child completion is supported by the final root statement. Result-consumption
  timing, session-lifetime exact-once, timestamps, concurrency, and the earlier
  runtime exit code remain `null`/unknown. No result ID or consumption event is
  fabricated.
- Semantic feature route is `Kael -> Veyra -> Kovan -> Nox -> Vera`; observed
  unique-session launch order is `Kael -> Nox -> Veyra -> Kovan -> Vera` because
  initial Nox isolation was a justified prerequisite. The route is recorded as
  observed, not reordered to match expectation. Later Nox validation and Vera
  follow-up reused their original sessions; Kovan remained the same original
  session, whose implementation return was PARTIAL while its session terminal
  outcome was succeeded.
- `CASE_B_FRESH_ROOT_3`, isolation, routing, role purity, negative controls,
  completion ownership, and result fidelity are PASS. Efficiency is
  `ACCEPTABLE` as a qualification judgment, not a latency measurement. B3 is
  accepted; B1 remains `FIXTURE_DEFECT` with Question Barrier PASS; B2 runtime
  remains PASS while B2 isolation/acceptance remains PARTIAL. Overall Phase 11
  remains PARTIAL; the B3 snapshot listed C, D, E, F, G, H, and K as pending
  at that time.
  A/I/J/L recovered
  observations remain guided/history-only.

The native event list is invocation-level plus the final root completion
statement, not a one-lifecycle-per-child synthetic trace. Every event's order
basis is `observed`, with ordinal labels rather than timestamps. The bounded
native validator is separate from `validate_trace`; it preserves missing result
IDs and aggregate consumption uncertainty. The synthetic `traces.json` and its
adversarial lifecycle expectations are unchanged.

## Isolated Case C native reconciliation — `P11-C-corpus`

The supplied Nox-verified native history is captured separately in
`case-c.native-trace.json` as `FRESH_ROOT_NATIVE`. The original evidence
collector Nox used native read-only OpenCode V2 APIs; this corpus writer did not
call those APIs, access the Case C worktree, rerun the case, or convert it into
the synthetic trace corpus.

- Root Kael `ses_efa068637ffeq7qrjCSJFLykc5`, parent `null`, terminal
  `succeeded`; the root directory was
  `C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-c`. The initial
  read-only Nox isolation verification confirmed that this copy was registered
  separately from the canonical repository at HEAD
  `8e77742ade517d4d903e0c8aa09cd037a44aa3da`. The historical isolation Git
  check exit code is unavailable; no worktree-creation claim is made.
- Two unique direct child sessions, both terminal `succeeded`, were observed in
  launch order: Nox `ses_efa05f4dfffe9s0gk5VEbkVRA9` for one read-only isolation
  verification, then Kovan `ses_efa03f35dffeSFO8Kg4CoukMfF` for one localized
  obvious-defect correction. Both used the Case C directory and had the exact
  Case C root as parent. Nox's result returned at epoch-ms `1791101704676`;
  Kovan's invocation was created at epoch-ms `1791101738171`, after Nox
  completed. This supports maximum direct-child concurrency `1`; the timestamps
  are retained only at those observed event points, not expanded into durations.
- The product route is `Kael -> Kovan`. The actual unique-session family is
  `Kael -> Nox -> Kovan`. The Nox session was an isolation prerequisite, not
  product diagnosis; the observed route is kept distinct rather than reordered
  to match the expected product route.
- Kovan changed only
  `tests/phase11-integrated-routing/fixtures/obvious/cart.py`, replacing
  subtraction with multiplication per the documented cart contract. Its
  recorded single-function validation command passed with exit 0 under
  `UV_NO_SYNC=1`, `UV_NO_PROJECT=1`, `UV_PYTHON_DOWNLOADS=never`, and
  `PYTHONDONTWRITEBYTECODE=1`. Kovan's separate `git diff --check` also passed
  with exit 0. The root terminal records the validation command/result and
  changed path, but does not literally include the separate diff-check result
  or the `CASE_C_FRESH_ROOT_NATIVE` classification.
- The evidence classifies an obvious functional cause (`true`), a nontrivial
  functional cause (`false`), and a complex feature (`false`). The complete
  original prompt was not supplied, so unrelated intent and issue-domain gate
  facts remain `null` rather than being inferred from non-activation.
- The child patch, test, and diff-check records carry `ORDER_BASIS: observed`.
  They have no invented ordinal indices or timestamps and do not assert an
  interleaving with the root-level invocation events.
- The literal root terminal message
  `msg_105fd3baa001OouobBeNyh4Nup` reports worktree isolation PASS, starting
  HEAD `8e77742ade517d4d903e0c8aa09cd037a44aa3da`, the one changed path, the
  validation command and `PASS — exit 0`, the four environment values, no
  unresolved work, all required child sessions terminal and consumed, and no
  remaining work. Case acceptance, route classification, Argus control, and
  efficiency are qualification judgments, not extra literal root fields.
- Argus invocation and unique-session counts are both zero. The eight required
  negative controls (Veyra, Orin, Atlas, Argus, Talos, Thales, Helios, and
  Aegis) are zero; the additional Vera zero-control is also recorded.
  Nox is active for isolation and is therefore not counted as a forbidden-role
  negative control. Role purity passed: direct children only,
  no nested delegation, no reviewer edits, and no root source writes. The native
  tool ledger is Kael: 2 subagent, 4 read, 1 glob; Nox: 7 shell; Kovan: 2 read,
  4 shell, 1 patch.
- Two distinct root invocation returns are present once; the final root
  statement supports zero pending, unconsumed, or unknown child results. Native
  result IDs, per-invocation consumption timing, session-lifetime exact-once,
  retry count, wall-clock/runtime duration, and native permission UI/decision
  remain unknown or not observable. No result IDs or consumption events are
  inferred. The complete root history had zero user questions.
- `CASE_C_FRESH_ROOT_NATIVE`, isolation, routing, negative Argus control, role
  purity, result fidelity, and completion ownership are PASS. Efficiency is
  `LEAN` as a qualification judgment, not a measured latency/throughput result.
  Case C is accepted; B1 remains `FIXTURE_DEFECT` with Question Barrier PASS;
  B2 runtime remains PASS while isolation/acceptance remains PARTIAL; B3 remains
  PASS. The B3 capture's historical pending labels still include C as of its
  earlier snapshot. At the C snapshot, current pending fresh-root work was D,
  E, F, G, H, and K; later Case D evidence below removes D from current pending
  state without rewriting the historical C snapshot.
  A guided/recovered PASS, I guided PARTIAL, J guided/recovered PASS, and L's
  recovered negative automatic-Aegis PASS remain history-only, not fresh-root
  evidence. Overall Phase 11 remains **IN VALIDATION / PARTIAL**, not SHIPPED.

## Prior P11-C repository preflight

Before the P11-C corpus edits, the repository was clean on branch
`qualify/phase-11-integrated-routing` at
`5b3761acf10125a97585f9b1dbcc127d15f50828`; the seven then-assigned Phase 11 targets
were tracked. Origin was
`https://github.com/Edulynch/OpenCode-OlympusAgents.git`; no upstream branch was
configured. No Git mutation was performed.

## Case D native reconciliation — `P11-D-corpus`

The supplied Nox native reconciliation and Veyra scoped expectation discovery
are recorded separately in `case-d.native-trace.json` as
`FRESH_ROOT_NATIVE`. This writer did not access the original Case D
worktree/session, call native APIs, replay the case, or repair a fixture.

- Before this D corpus edit, the canonical repository was clean on branch
  `qualify/phase-11-integrated-routing` at
  `60eb1685ee866a59de46be09dba3555c1cd3e776` (read-only Git status/HEAD check).
  The configured origin URL is from task context; no Git mutation was performed.
- Root Kael `ses_ef8c726b7ffeqWgvWlpg0NcU1Q` has execution metadata outcome
  `succeeded`; the semantic `FINAL_OUTCOME` is `NEEDS_USER_INPUT`. The root's
  parent session field was not exposed and remains `null` labeled
  `NOT_EXPOSED`. The registered qualification worktree was verified only at
  HEAD `60eb1685ee866a59de46be09dba3555c1cd3e776`; it is a linked worktree
  sharing the canonical Git common directory. No worktree-creation claim is
  made. Nox reported the worktree clean before and after; the root reported
  `FILES_CHANGED: NONE`.
- Three direct child sessions, each terminal `succeeded` under the same root,
  were observed in order: Nox `ses_ef8c67e03ffeYoAjNx6bfAmNdR` for read-only
  isolation; Veyra `ses_ef8c49280ffeiI6EQxlG6e4Pjx` for bounded evidence; Argus
  `ses_ef8c3a562ffemV1PDdCkCYmThm` for one diagnosis consultation. The observed
  session family is Kael -> Nox -> Veyra -> Argus; the semantic product route is
  Kael -> Veyra -> Argus. Nox is a qualification prerequisite, not product
  diagnosis. Native tool delivery state is `completed` for all three and their
  child-session execution outcomes are `succeeded`; the literal Nox/Veyra
  `RETURN_STATUS` fields were not supplied and remain `null`. Argus's literal
  `RETURN_STATUS` is `INCONCLUSIVE`, matching its diagnostic status; this is not
  normalized to `SUCCESS` from the completed delivery or succeeded session.
- Veyra found no input provenance or subtotal-domain contract distinguishing
  whether the subtotal includes shipping. The already-collected bounded evidence
  was supplied to Argus; no further discriminator was available. Argus returned
  `INCONCLUSIVE` with `CAUSE_UNCONFIRMED`; no functional violation is established
  and no repair is supported. The `NONTRIVIAL_FUNCTIONAL_BUG` request label is
  not promoted into a confirmed violation or cause.
- The root reports all three children terminal and consumed before one
  parent-authored binary text question. `USER_QUESTION_COUNT` is 1; there were no
  question-tool calls. The unresolved question is preserved exactly in the
  native artifact and is not asked again here. Aggregate pending, unconsumed,
  and unknown child counts are zero; result IDs and per-result consumption
  timestamps remain `null`, not fabricated events. Native permission UI and
  decision are `NOT_OBSERVABLE`.
- Case D's bounded diagnostic-limit, isolation, Argus routing, no-invented-cause,
  no-progress-stop, question barrier, role purity, result fidelity, and
  completion ownership classifications are PASS. Efficiency is `LEAN` as a
  qualification judgment, not a latency measurement. Case D follow-up is
  `NOT_REQUIRED` because Argus made no evidence request.
- Separately, `ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE` is
  `NOT_EXERCISED`: Case D does not demonstrate runtime same-session follow-up.
  An optional genuine evidence-requesting scenario remains open for final
  coverage review; it is not a Case D blocker or an implicit pass. The synthetic
  iterative D trace remains unchanged and continues to represent an actual
  evidence-request/follow-up path subject to generic same-session, new-evidence,
  production, delivery, consumption, and no-progress validation.
- Current fresh-root work is E, F, G, H, and K. Overall Phase 11 remains
  **IN VALIDATION / PARTIAL**, not SHIPPED. Historical B3 and C pending snapshots
  remain unchanged.
- Final local validation: the Phase 11 unit suite passed all 53 tests; the
  qualifier exited 0 with its expected `PARTIAL` status; the feature fixture's
  four compatibility tests passed; Harness Core safe-root read-only validation
  passed with 29 managed outputs unchanged; and `git diff --check` passed. These
  are corpus/validator checks, not a Case D replay or native-export
  authentication.

## Case E native reconciliation — `P11-E-RECON-RECORD`

The original completed Case E root was reconciled through public read-only
OpenCode V2 API GETs. Its native export and metadata identify Kael session
`ses_ef85bfb20ffeJDAs5WvP6mQNiP`, title “Authorization defect classification
for account deletion,” directory
`C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-e`, and execution
outcome `succeeded`. Parent identity was not exposed. The `sanitize=false`
export was captured in memory only; the checked-in
`case-e.root-session.export.json` is a projection retaining the original user
prompt and visible assistant terminal text, message IDs/times and outcome. One
reasoning block was removed, no secret values required redaction, and the raw
export was not persisted. The root export had zero observable tool-call records.
The separate direct-child query returned an empty list and no next-page cursor;
no specialist activation is inferred or invented. No private runtime, Case E
worktree filesystem, or other session was accessed, and no case rerun/replay was
performed.

The original prompt identifies an established hypothetical authorization
failure: a `MEMBER` can delete another user's account despite the `ADMIN`-only
contract, requests the smallest sufficient security-specific route, and
explicitly forbids exploit execution, destructive action, edits, or broad audit.
The terminal answer classifies `CONFIRMED_SECURITY_DEFECT`, identifies the
server-enforced ADMIN-only boundary, states the invariant that non-ADMIN access
is denied without deletion side effects, and proposes synthetic identities
with mocked deletion operations. It reports `EXPLOIT_ATTEMPTED: NO`,
`FILES_CHANGED: NONE`, `UNRESOLVED_WORK: NONE`, required children terminal and
consumed, and no work remaining. These behavioral and safety facts are distinct
from routing acceptance.

- **Expected product route:** Kael -> Talos. **Observed route:** Kael only.
  Native child/tool evidence records Talos 0 and Argus 0. The negative Argus
  control passes; the required Talos activation does not.
- `CASE_E_BEHAVIOR`, security classification/boundary, safe validation, safety,
  role purity, and negative Argus control are PASS. Talos activation, routing,
  and fresh-root acceptance are FAIL. Root execution `succeeded` is not Case E
  routing success: result is `NATIVE_EXECUTED_ROUTING_FAIL`.
- **Confirmed intended-product routing gap; likely cause: security-gate wording
  mismatch.** Kael's OpenCode prompt says classification alone does not require
  Talos and requires an established/strongly evidenced defect *and* a materially
  unanswered security-specific question (`olympus/harnesses/opencode/agent-prompts/kael.md:286-292`).
  Talos's prompt repeats this threshold (`.../talos.md:25-27`). Case E's expected
  route and explicit authorization contract are in `cases.json:96-106`; the
  generic smallest-sufficient rule is `olympus/policies/routing.md:5-7`. The
  tested product invariant is that an established material security/trust/
  authorization boundary activates Talos. The smallest correction goal is to
  align that gate with the invariant while reserving Argus for an independently
  gated non-security functional diagnosis. No internal model rationale or
  defective security classification is claimed; no Core correction was made.

At the E1 snapshot, E remained an unresolved acceptance item alongside F, G, H,
and K. That pending state is historical: the later E2 fresh-root reconciliation
below closes current Case E acceptance without changing E1's observed routing
failure. Overall Phase 11 remains **IN VALIDATION / PARTIAL**, not SHIPPED. The
E1 failure is not an instruction or authorization to rerun that root. A-D
acceptance and the separate
`ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE: NOT_EXERCISED` status remain
unchanged. The rules above were also read at starting HEAD
`314a6bc529e0d5e17d1662e3765734b7cc80cd86` using read-only `git show`.

## Case E2 fresh-root native reconciliation — `PH11-E2-CLOSURE`

E2 is the later, distinct fresh-root attempt that closes current Case E
acceptance. The exact completed root and direct Talos child were read through
public, read-only OpenCode V2 metadata, export, message-list, and direct-child
GETs. The root direct-child listing required two pages and contained exactly one
child, Talos; the root and child message lists each required two pages and their
second cursor-only pages were empty. The API metadata directory strings matched
the supplied disposable-path context; exact paths were omitted from the
projection, and no disposable-worktree filesystem was read.

- Root Kael `ses_ef7eb1d45ffet0gMtEEUam8R4U` is parentless, succeeded, and is
  titled “Diagnosing MEMBER account-deletion authorization boundary.” Its
  original prompt records starting HEAD
  `3e5b2af2c15f9ef2775be3c3f5667edd4db0bdde`.
- The sole direct child is Talos
  `ses_ef7ea7bf7ffe4U23sL7M1mi60p`, parented to that root, succeeded, and titled
  “Diagnose account deletion authorization.” The root export contains exactly
  one completed `subagent` call, ID `call_FzRbkaOiUp41wcA0DcJfrrPw`; its
  observed Talos input, child metadata, and direct-child listing join to that
  child and the exact task label `PHASE11_CASE_E2_FRESH_ROOT`. The child export
  contains no tool-call records.
- The reasoning-redacted projections are
  `case-e2.root-session.export.json` and
  `case-e2.talos-session.export.json`; the bounded native record is
  `case-e2.native-trace.json`. Two root reasoning blocks were removed, the child
  had zero reasoning blocks, the retained prompt/terminal text matches the
  exports, no secret-pattern matches required redaction, and raw exports were
  not persisted.
- The observed product route is Kael -> Talos, matching the E security-bug
  expectation. Talos confirmed the established MEMBER/ADMIN account-deletion
  authorization defect; server-side authorization using trusted identity/role
  information must precede deletion side effects. The enforcement failure is
  established, but the implementation mechanism is unknown. No tools, tests,
  repository access, exploit, or file changes were reported by the child.
- The root terminal reports the required child work terminal and consumed,
  `EXPLOIT_ATTEMPTED: NO`, `FILES_CHANGED: NONE`, and no work remaining. It does
  not contain a literal E2 `PASS`; E2 acceptance is a reconciliation judgment
  from the observed route, diagnosis, safety limits, and aggregate completion
  statement. Result IDs, per-invocation consumption timing, session-lifetime
  exact-once, concurrency, and timing remain `null`; native permission UI and
  decision are `NOT_OBSERVABLE`.
- E2 behavior, security classification, safety, role purity, Talos activation,
  negative Argus control, routing, result fidelity, completion ownership, and
  fresh-root-native acceptance are PASS. E1 remains
  `NATIVE_EXECUTED_ROUTING_FAIL` with expected Kael -> Talos and observed Kael
  only; its source trace and projection remain unchanged and its failed history
  is preserved.

The latest live Phase 11 snapshot therefore removes E from current pending work;
only F, G, H, and K remain pending fresh-root actions. Phase 11 remains
**IN VALIDATION / PARTIAL**, not SHIPPED. A is PASS guided/recovered, B/C/D/E2
are accepted `FRESH_ROOT_NATIVE`, I is PARTIAL guided, J is PASS
guided/recovered, and L's recovered negative automatic-Aegis control is PASS.
`ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE` remains
`NOT_EXERCISED`; E2 did not demonstrate same-session follow-up behavior.

Closure validation from the canonical repository passed:

- `uv run --python 3.11 python tests/phase11-integrated-routing/qualify.py` —
  exit 0; `PHASE11_ARTIFACTS: PASS`, overall `PARTIAL`.
- `uv run --python 3.11 python -m unittest discover -s tests/phase11-integrated-routing -p "test_*.py" -v` —
  62 tests, all passing, including E2 child/parent, route, result, and E1-history
  mutations.
- `uv run --python 3.11 python -B tests/harness-core/qualify.py --safe-root-read-only` —
  PASS; all 29 managed-output hashes and mtimes were unchanged.
- `uv run --python 3.11 python scripts/render_harnesses.py check --harness all` —
  PASS, read-only, 29 managed outputs.
- `git diff --check` — PASS; only line-ending warnings were emitted.

The E2 native/reconciliation validator adds material semantic checks and should
receive independent Nox or Vera review before adoption; this writer did not
perform or delegate that review. Kael decides whether to request the review.
