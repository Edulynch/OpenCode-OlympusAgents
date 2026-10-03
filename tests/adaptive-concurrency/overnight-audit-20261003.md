# Adaptive-concurrency overnight evidence audit — 2026-10-03

## Decision

**KEEP_FAST_4.** Keep the current bounded four-worker policy. This audit does
not justify promoting the concurrency limit or changing Core routing. The
evidence gap remains: no comparative runtime measurement was made, and no
six-way trial was attempted. No latency, throughput, or other numeric benefit
is claimed.

This is a documentation-only record of the supplied Nox audit and focused
Veyra review, not a new test run. The audit is point-in-time; no timestamp or
external result identifier was exposed in the supplied record.

## Commands and observed results

The following commands/results were reported by the audit:

| Command | Result |
| --- | --- |
| `git status --short` | Exit 0. |
| `git status -- tests/adaptive-concurrency tests/harness-core docs/DEVELOPMENT.md` | Exit 0. |
| `git diff --name-only -- tests/adaptive-concurrency tests/harness-core docs/DEVELOPMENT.md` | Exit 0. |
| `pwsh -NoProfile -File tests/adaptive-concurrency/qualify.ps1` | Exit 0; AC1–AC10 and DOC passed. Interactive selection and fanout remained pending. |
| `uv run --python 3.11 python tests/harness-core/qualify.py` | **NOT EXECUTED** by Nox because the qualifier could write protected project surfaces. This is not a test failure. |

The scoped before/after Git-state checks were reported clean. This does not
claim a globally clean worktree: the pre-existing `docs/ROADMAP.md` change and
untracked `tests/phase11-integrated-routing/` work were not read by Nox and are
outside this audit's scope. The separate Phase12 document was also explicitly
left untouched.

Veyra's focused review found that the root qualifier's render-all path can
rewrite `.opencode/**`, `.codex/**`, root `opencode.jsonc`, `CODEX.md`, and
`docs/HARNESS-CAPABILITIES.md`. The existing read-only
`scripts/render_harnesses.py check --harness all` route is a drift check, not
full qualification; full fixture validation uses an approved temporary
location rather than project source. No safe full-qualifier option was
identified in this audit. Resolution is being handled independently in
Phase11. This point-in-time observation does not assert that human action is
intrinsically required if a safe project-test option is later established.

## Scenario-by-scenario evidence and limits

| Scenario / claim | Evidence | Limit |
| --- | --- | --- |
| Six independent read-only shards | The active-child ceiling was four; no native six-way attempt was made. | No six-way run, peak-active measurement, latency comparison, or throughput measurement. |
| Ownership, dependency, and trivial FAST-at-four safeguards | Static checks/assertions were reviewed. | Runtime behavior was not measured. |
| Seven partitions at four workers | The asserted layout was `2/2/2/1`. | Static partition arithmetic only; not an observed run or performance result. |
| Twenty partitions at four workers | The asserted layout was `5/5/5/5`. | Static partition arithmetic only; not an observed run or performance result. |
| Six-worker layouts | The layouts `2/1/1/1/1/1` and `4/4/3/3/3/3` were considered. | Arithmetic only; neither is measurement, and neither came from a six-way trial. |
| Nox/VERA safe independent post-write parallelism; reasoner follow-up requirement | These are identified as required scenario/follow-up evidence. | No dedicated runtime scenario was run; no execution order is established by the audit. |
| Same-repository/ref Git serialization | Static ownership/conflict safeguards were considered. | No observed queueing or serialized runtime trace. |
| Overlapping `WRITE_SCOPE` | Static conflict/denial checks were considered. | No observed scheduler queueing or runtime serialization measurement. |
| Core policy promotion | No material Core routing defect was demonstrated in the supplied evidence. | No Core change or promotion is supported by this audit. |

The recorded session/continuation context is provenance only, not a trial
trace: it does not establish freshly isolated A–L roots, measured peak active
workers, or a six-way benchmark. The formal native-permission UI and decision
were **NOT_OBSERVABLE**; absence of a visible prompt was not inferred.

## Outcome and reconsideration criteria

Retain FAST-at-four as the current bounded policy. Promotion is unsupported by
this evidence. Reconsider only after authorized real measurements and the
relevant safety checks; do not infer numeric benefit from the static layouts
above. Preserve the four-worker ceiling unless separate, explicit user
authority for Core maintenance is provided and a change is actually needed.

This documentation task itself ran no tests or native concurrency trial and
made no Core change or Git mutation.
