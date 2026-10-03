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
supersedes that label set for the current validation: only B, C, D, E, F, G, H,
and K remain pending fresh-root actions. Phase 11 remains
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

The current scoped trace corpus remains synthetic, and fresh-root native
qualification remains pending for B, C, D, E, F, G, H, and K only. A, I, J,
and L prompts are retained as reference/history; no rerun is requested for the
recovered A/I/J/L observations or I/J negative controls.

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
justification. Static artifact validation may report PASS, but Case B acceptance
remains PARTIAL until user-controlled `PHASE11_CASE_B_FRESH_ROOT_3` runs in a
clean separate disposable copy with a new verified Kael root. No B3 run or
worktree launch was performed.

## Reconciliation-task repository preflight

Before these edits, the repository was clean on branch
`qualify/phase-11-integrated-routing` at
`5b3761acf10125a97585f9b1dbcc127d15f50828`; all seven assigned Phase 11 targets
were tracked. Origin was
`https://github.com/Edulynch/OpenCode-OlympusAgents.git`; no upstream branch was
configured. No Git mutation was performed.
