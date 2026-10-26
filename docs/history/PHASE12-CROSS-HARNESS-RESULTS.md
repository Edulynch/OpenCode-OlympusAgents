# Phase 12 Cross-Harness Results

**Status: CLOSED — three matched pairs, six executions.** This is an evidence
ledger for the frozen design in [the Phase 12 plan](PHASE12-CROSS-HARNESS-PLAN.md),
not a new qualifier, capability certification, or total harness-parity claim.

## Evidence basis and identity

- Runtime facts below are attributed to user-supplied records captured
  immediately after each execution. They were not independently reread from
  native logs; no external trial worktree or rollout was accessed for this
  ledger. No trials were run for this ledger. The summaries retain compact
  session IDs and supplied rollout references, not raw log dumps.
- The supplied pinned baseline is
  `134b2668602368199578972f4498c9118c5f9c55`. A read-only Git check confirmed
  that this commit exists and contains the frozen plan. It is also the current
  repository `HEAD` during ledger creation. Each trial's worktree identity is
  recorded below as supplied provenance, not independently inspected state.
- Supplied worktree labels (under the supplied external
  `C:\Users\BLAUTECH\AppData\Local\Temp\` base):
  `olympus-phase12-t1-opencode`, `olympus-phase12-t1-codex`,
  `olympus-phase12-t2-codex`, `olympus-phase12-t2-opencode`,
  `olympus-phase12-t3-opencode`, `olympus-phase12-t3-codex`.
- Frozen fixture, model, and source/config declarations are those in plan §§3
  and 5; they are declarations, not observed effective runtime state. Per-run
  observed fixture/blob/checkout identities, runtime versions, effective
  model/config, and observed overrides: `null`. Optional comparable runtime
  metrics: `null`.
- `OBSERVED_INTERVENTIONS=0` counts external/user interventions. It does not
  mean there were no orchestrator continuations (see Trial 3, OpenCode).

## Six-execution matrix

| Order | Workload / harness | Root → direct child(ren) | Worktree | Result |
|---|---|---|---|---|
| 1 | Trial 1 `TRIVIAL_EDIT` / OpenCode | `ses_eee4d800bffel2MzHR01Bj3GXY` → `ses_eee4d074bffex96RfarXrSf13a` (`kovan`) | `...t1-opencode` | `VERIFIED` |
| 2 | Trial 1 `TRIVIAL_EDIT` / Codex | `01a111d2-2f6a-7b53-a3a0-1b520e6b817a` → `01a111d2-74d5-7843-b311-28e0edb29cc4` (`kovan`, `/root/kovan_edit`) | `...t1-codex` | `VERIFIED` |
| 3 | Trial 2 `SECURITY_BOUNDARY` / Codex | `01a111f4-a918-7900-8449-d4656e2c9c41` → `01a111f4-f279-7653-af90-b3b215863014` (`talos`, `/root/security_boundary`) | `...t2-codex` | `VERIFIED` |
| 4 | Trial 2 `SECURITY_BOUNDARY` / OpenCode | `ses_eedeb8873ffe4SpmVmfZHANI5g` → `ses_eedeb28cbffeZ0OYHdxgSpWzMW` (`talos`) | `...t2-opencode` | `VERIFIED` |
| 5 | Trial 3 `FAST_INDEPENDENT_TASKS` / OpenCode | `ses_eede4e5a3ffepb2HGispxhLqAv` → A `ses_eede39cbbffezuaK1Os3pZUcaB`; B `ses_eede39c7effeh60KMnpiIJRzDI`; C `ses_eede39c17ffePb5M8bZ6LCGXyX`; D `ses_eede39c0effecTC7FJUV0FEWN4` (all `kovan`) | `...t3-opencode` | `VERIFIED` after same-session continuations |
| 6 | Trial 3 `FAST_INDEPENDENT_TASKS` / Codex | `01a11230-553b-71a0-a421-a65ba09eb706` → A `01a11231-2b26-72c1-a548-c4949f2a83d2`; B `01a11231-44dd-7120-9292-47ac1099ecb0`; C `01a11231-5f45-7f50-b3c5-a17a85b29be6`; D `01a11231-7939-7581-85df-0d3a00764cc9` (all Kovan; `/root/writer_a` through `/root/writer_d`) | `...t3-codex` | `VERIFIED` |

Codex rollout provenance uses the supplied
`C:\Users\BLAUTECH\.codex\sessions\2026\10\06\` base and filenames
`rollout-2026-10-06T<time>-<session-id>.jsonl`. Supplied times: Trial 1 root
09-25-50, child 09-26-07; Trial 2 root 10-03-29, child 10-03-48; Trial 3 root
11-08-40, children A/B/C/D 11-09-35/41/48/55. These are provenance references,
not independently inspected rollout content.

## Trial 1 — `TRIVIAL_EDIT`

Both executions reported the actual route `Kael → Kovan`, one direct child,
and only `tests/phase11-integrated-routing/fixtures/simple/message.txt`
changed to the single line `Hello Phase 12 cross-harness`. Both report no
out-of-scope changes; functional acceptance, delivery/consumption, and
completion passed. External/user interventions: 0.

- **OpenCode:** Kovan completed as a native subagent; its terminal result was
  returned within the root subagent result and consumed before root completion.
- **Codex:** The original child terminal result was received as `FINAL_ANSWER`.
  The root then performed proportional file/diff validation, returned its
  final, and followed with `task_complete`; no replacement child was used.

## Trial 2 — `SECURITY_BOUNDARY`

Both records report actual `Kael → Talos`, `Talos=1`, `Argus=0`, no file
changes, and successful result delivery/consumption. Both are diagnosis-only,
not remediation. The supplied summary classifies the authorization violation:
a `MEMBER` deleting another user's account despite an `ADMIN`-only contract.
The implementation mechanism is `UNKNOWN`. Detailed diagnosis, fix-direction,
or future-validation wording is not reproduced here because it was not present
in the supplied capture summary; none is invented. External/user interventions:
0. Both outcomes are reported `VERIFIED` by the supplied records.

- **Codex:** Talos returned a terminal classification; no tools, source
  inspection, exploit, or writes. The root received `FINAL_ANSWER`, finalized
  after the result, and completed with `task_complete`.
- **OpenCode:** The completed native invocation returned `SECURITY_DIAGNOSIS`,
  consumed before root completion. No inspection, file change, validation, or
  exploit was reported.

## Trial 3 — `FAST_INDEPENDENT_TASKS`

Each harness used four direct Kovan writers, each with one disjoint owned path:
`tests/codex/fixtures/parallel/research-{a,b,c,d}.md`. Useful writers: 4.
Both final records report preservation of each original byte prefix, the exact
required marker once per file, no other changed paths, and passing trial
`git diff --check`.

| Owned path | Exact appended line |
|---|---|
| `tests/codex/fixtures/parallel/research-a.md` | `Phase 12 cross-harness marker: A` |
| `tests/codex/fixtures/parallel/research-b.md` | `Phase 12 cross-harness marker: B` |
| `tests/codex/fixtures/parallel/research-c.md` | `Phase 12 cross-harness marker: C` |
| `tests/codex/fixtures/parallel/research-d.md` | `Phase 12 cross-harness marker: D` |

### OpenCode attempt and continuation history

- First attempt: A `SUCCESS`; D `SUCCESS`. B and C each terminated
  `BLOCKED` with `TOOL_ATTEMPT=NOT_ATTEMPTED` and
  `TOOL_EXECUTION=NOT_EXECUTED`: the mandatory `AUTHORITY_GRANT` heading was
  absent. No mutation occurred for either blocked writer.
- B and C continued in the **same original sessions and IDs** (listed in the
  matrix), not replacement writers. The root explicitly consumed each original
  terminal `BLOCKED` result and confirmed non-execution before supplying the
  corrected `AUTHORITY_GRANT`. Both continuations then succeeded.
- Final acceptance was established only after those continuations. Blind
  mutation retries: 0; replacement writers: 0; external/user interventions: 0.
  Delivery, consumption, and completion: `PASS`.
- Child-reported UTC work intervals for B
  (`2026-10-06T16:51:48.6721649Z`–`16:51:48.9896850Z`) and C
  (`2026-10-06T16:50:58.7918901Z`–`16:52:39.2575601Z`) overlap. This supports
  `OBSERVED_WORK_INTERVAL_CONCURRENCY>=2`, not a native active-child snapshot.
  `MAX_NATIVELY_OBSERVABLE_ACTIVE_CHILD_CONCURRENCY=null`. Reported mutation
  windows did not overlap.

### Codex evidence

- One native root `list_agents` snapshot showed all four writers running:
  `MAX_NATIVELY_OBSERVABLE_ACTIVE_CHILD_CONCURRENCY=4` (snapshot basis; not a
  claim about launch order). A later snapshot showed all four completed with
  terminal results; the root received the results and compared each file
  byte-for-byte with its original plus the exact CRLF-terminated marker.
  `accepted=True` for all four; marker count was 1 per file.
- Only the four owned files changed. Reported mutation windows did not overlap;
  simultaneous writes were unobserved and were not required. Blind retries: 0
  observed; replacements: 0 observed; external/user interventions: 0.
  Delivery, consumption, and completion: `PASS`.

## Closure and interpretation

| Field | Closure |
|---|---|
| Matched pairs / executions | `3/3` pairs; `6/6` executions |
| Trial 1 OpenCode / Codex | `VERIFIED` / `VERIFIED` |
| Trial 2 Codex / OpenCode | `VERIFIED` / `VERIFIED` |
| Trial 3 OpenCode / Codex | `VERIFIED` / `VERIFIED` (OpenCode only after recorded continuations) |
| `FUNCTIONAL_PARITY` | `PASS` for tested required workloads |
| `ROUTING_INVARIANT_PARITY` | `PASS` for tested required routes/invariants |
| `COMPLETION_INVARIANT` | `PASS` |
| `SCOPE_INTEGRITY` | `PASS` |
| `OBSERVED_INTERVENTIONS` | `0` external/user interventions |
| `PERFORMANCE_WINNER_RANKING` | `DISABLED` |
| `NORMAL_FEATURE_ESCALATION` | `NOT_ACTIVATED` — after three matched pairs, no unresolved multi-role handoff, result-delivery, completion-barrier, routing, provenance, or practical adapter-integration ambiguity remained |
| `ISSUE_11_ALIGNMENT` | `PASS` — no new qualifier/framework, fixtures, or regression introduced; no product defect diagnosed here |

Capability limits remain those declared in the frozen plan, not trial parity
awards: Codex `QUESTION_CENTRALIZATION`, `RESULT_RECONCILIATION`, and
`ACTIVITY_VISIBILITY` are `PARTIAL`; Codex `ASK` is `ADAPTABLE`; Codex `DENY`
and `AEGIS` are `GAP`; OpenCode `GLOBAL_RUNTIME_DISCOVERY` is `GAP`. Results
support only the required invariants actually tested. They do **not** establish
total harness parity, equivalence for limited capabilities, performance
superiority, or a harness/model winner.
