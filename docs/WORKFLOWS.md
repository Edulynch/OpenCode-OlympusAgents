# Working with Olympus

Start with the quick guide in [English](../README.md) or [Español](../README.ES.md). This guide explains task commands and workflow boundaries. Olympus coordinates agents within OpenCode; configure model access in OpenCode as usual.

## Try a task

### First task in a plain Git project

Use a disposable local Git repository and a real OpenCode session with
OlympusAgents (Kael) already available and an already usable model. The project
itself needs no Olympus checkout, project-scoped setup, or extra harness. Do not
grant blanket permissions; handle any native permission request through
OpenCode's normal scoped UI.

In the repository root, create these two files:

`status.py`:

```python
def format_status(status, detail):
    return f"{detail} | {status}"
```

`test_status.py`:

```python
import unittest

from status import format_status


class StatusTest(unittest.TestCase):
    def test_status_precedes_detail(self):
        self.assertEqual(format_status("READY", "2 items"), "READY | 2 items")
```

Run `git init` and `git add status.py test_status.py` to record the baseline
without committing. This test should fail before the change:

```sh
python -B -m unittest -v test_status.StatusTest.test_status_precedes_detail
```

Give Kael this task without naming a worker:

> In this disposable Git project, change `status.py` so status appears before
> detail while preserving the ` | ` separator. Only `status.py` may change. Run
> `python -B -m unittest -v test_status.StatusTest.test_status_precedes_detail`,
> report the observed result and exact diff, and do not commit.

Afterward, independently rerun the test and inspect the result:

```sh
python -B -m unittest -v test_status.StatusTest.test_status_precedes_detail
git diff --check
git status --short
git diff -- status.py
```

Expect one passing test, a clean whitespace check, and only the intended
formatter change in the diff. Record the actual OpenCode version, model, test
output, and diff; this fixture does not establish behavior beyond that run.

### Build something

Open OpenCode in your project and describe the outcome:

> Create a Flutter habit tracker. Start with a simple home screen, local storage, and one test for the save flow. Ask me before choosing an external database.

### Diagnose and fix

> Find why this API responds with HTTP 500 for valid input. Reproduce it, fix the cause, and run the tests relevant to the changed module.

### Ask for independent work

> `/olympus.ultra Review these four independent modules for reproducible issues. Fix confirmed bugs, preserve required checks, and summarize the results.`

Run this execution example from Kael. From Atlas, the same command remains
read-only and ends with analysis plus a scoped handoff. Neither mode grants
broader permissions or guarantees that a particular number of workers will run.

## Primaries and specialists

The current roster has nine roles: Kael and Atlas are separate primaries, and
Kael has seven specialist children. Orin and Argus are retired; neither is a
current role. [Olympus Core](../olympus/README.md) defines the role boundaries.

- **Kael** owns user decisions, execution routing, dependencies, evidence
  reconciliation, acceptance, and task completion. Kael does not directly read
  or search repositories, research, run shell/Git/tests, or edit files. It
  routes implementation and normal authorized Git work to Kovan, and distinct
  testing/runtime evidence to Nox.
- **Atlas** is a separate read-only primary for bounded repository analysis,
  architecture, trade-offs, defect hypotheses, and plans. It hands a scoped
  proposal to Kael; it cannot implement, mutate Git, test, review a final
  candidate, or accept work. Its shell access is only for bounded inspection
  and diagnostics through native ASK; ASK is not a sandbox. Atlas may delegate
  only to Veyra, Helios, Talos, or Thales.
- **Kael's seven children:** Veyra (evidence), Kovan (implementation and normal
  project Git), Nox (reproduction/tests/runtime/measurement), Vera (independent
  review), Helios (explicit optimization method), Talos (security diagnosis),
  and Thales (exceptional technical diagnosis). Atlas is not a Kael child.

## Task results and handoffs

For operational updates, use localized human-facing **Status** followed by a
concrete **Result** (one concise line may combine them, status first). Add
**Verification/Evidence** when checks materially matter, naming each relevant
check and its state, including checks not run. Include **Blocker** only when
one exists; finish with **Next** only when useful. These labels are for people,
not internal handoff fields. Exact `EXPECTED_OUTPUT` takes precedence, while
ordinary conversation and direct answers stay natural. Say IN PROGRESS when
required work is active and FAILED only for an observed failure. Describe
unknown execution in prose; never say idle unless that state is known.

The examples use one small change: move the status text before details in
`src/task_summary.py`.

**Required checks passed; optional smoke skipped**

> Status: Complete and idle — Result: `src/task_summary.py` now puts status before details.\
> Verification: `tests/test_task_summary.py::test_status_precedes_details` passed; optional CLI smoke was not run.

**Required check pending**

> Status: Partial — Result: the status-first change is implemented.\
> Verification: required `tests/test_task_summary.py::test_status_precedes_details` has not run; no test process is active.\
> Next: run `python -m unittest discover -s tests -p test_task_summary.py`.

**Required check blocked**

> Status: Blocked — Result: the change is implemented, but acceptance is not verified.\
> Verification: required `tests/test_task_summary.py::test_status_precedes_details` could not start; no pass/fail result exists.\
> Blocker: Python is unavailable in the test environment.\
> Next: restore the test environment and run the required test.

### Kovan result example

After the same small code change, Kovan reports through its existing result contract:

```text
STATUS: SUCCESS
SUMMARY: Put task status before its details.
CHANGES: Updated the existing task-summary formatter.
FILES: src/task_summary.py
TESTS: tests/test_task_summary.py::test_status_precedes_details — PASS; optional CLI smoke not run.
ACCEPTANCE: Status leads; existing details remain.
RISKS: None identified.
BLOCKERS: None.
RECOMMENDATION: ACCEPT
SCOPE_COMPLIANCE: PASS
OUT_OF_SCOPE_CHANGES: none
```

The human labels do not change internal handoff fields, existing authority or
completion gates. Nox retains independent validation; Kael retains root
completion.

## Parallelism

| Policy | Selection | What changes |
| --- | --- | --- |
| **Default** | Any ordinary task | Kael or Atlas adapts concurrency to useful, independent work; simple tasks need no fan-out. The shared prompt-ceiling preference is 1–8 for each primary root session, not a quota across sessions. |
| **Ultra** | `/olympus.ultra <prompt>` | The current primary seeks ready, independent work up to the effective prompt ceiling. The ceiling is not a target; no scheduler is added, and dependencies, ownership, permissions, validation, and completion gates remain unchanged. |

Only one mutative writer may use a worktree at a time. Parallel writers need
isolated worktrees and non-conflicting refs and shared resources; disjoint file
paths in one worktree are not enough.

### Native task commands

The global OpenCode installation provides exactly these three namespaced commands:

```text
/olympus.ultra <prompt>
/olympus.performance <prompt>
/olympus.performance-ultra <prompt>
```

All three commands run in the current **Kael or Atlas primary** session and
accept the full task text. There are no bare aliases. Empty or whitespace-only
arguments return usage; invocation from another primary returns
supported-primary guidance. Neither case triggers tools or agents. This is a
prompt guard, not deterministic native argument enforcement. Every command
retains the active primary's normal role, authority, native-permission,
dependency, validation, reconciliation, and completion boundaries.

`/olympus.ultra` is latency-first: admit only ready, independent work and
dispatch/refill slots as they become available. Before dispatch, Kael or Atlas
records `ULTRA_CEILING`, `READY_WORKSTREAMS`,
`TARGET_ACTIVE = min(ULTRA_CEILING, READY_WORKSTREAMS)`, and observed
`CURRENT_ACTIVE`. The final receipt records `ULTRA_WORKSTREAMS`,
`PEAK_ACTIVE_CHILDREN`, `TOTAL_CHILD_SESSIONS`, `WRITER_WORKTREES`,
`DUPLICATE_CHECKS`, and `UNDERFILL_REASON`. Underfill must use the canonical
reason: `ONLY_N_INDEPENDENT_WORKSTREAMS` (with observed N),
`DEPENDENCY_UNRESOLVED`, `WRITER_OR_RESOURCE_CONFLICT`, `PERMISSION_BLOCKED`,
`NO_ELIGIBLE_ROLE`, or `COORDINATION_COST_EXCEEDS_EXPECTED_LATENCY_BENEFIT`;
use `NONE` when there is no underfill and `UNKNOWN` only when the cause cannot
be established. Never invent counts or add a scheduler, controller, or
artificial fan-out. For Atlas, Ultra ends in read-only analysis and a scoped
handoff; it does not authorize execution.

`/olympus.performance` is explicit optimization intent. Helios supplies the
exclusive method. Kael routes missing measurements to Nox; Atlas requests that
evidence from Kael. If a concrete
direction or trade-offs remain unsettled, Kael presents the proposal and waits
for user approval before implementation. A sufficiently specific direction
already approved by the user does not need duplicate approval. Implementation
acceptance requires measured `BEFORE`, `AFTER`, `DELTA`, `TARGET`, and
`CORRECTNESS`; unknown values stay unknown.

`/olympus.performance-ultra` combines the same Performance gate with Ultra
admission. It does not make Ultra automatic for other requests, authorize
implementation, or bypass approval and validation. Atlas remains read-only and
returns a performance plan and scoped handoff. Canonical behavior is maintained
in [Kael's OpenCode adapter source](../olympus/harnesses/opencode/agent-prompts/kael.md)
and [routing policy](../olympus/policies/routing.md).

## Contextual maintenance and ownership

- **Kael orchestrates** work inside OlympusAgents and other projects using the same normal team. There is no active Aegis role or `/maintain` command.
- **Project-owned OpenCode extensions** (skills, plugins, custom agents and commands) can be implemented by Kovan in the assigned scope. Managed files are protected; project OpenCode config needs explicit scope and the applicable native decision. Candidate rendering in the OlympusAgents source worktree is not installation.
- **The user owns product decisions.** Kael checks project identity, scope and feasibility before involving specialists; it cannot silently expand authorization.
- **Readiness comes before expensive work.** Kael groups foreseeable material decisions, reuses authority already granted, and continues useful independent work when a workstream is blocked. Native permission questions remain with the host.
- **OpenCode owns runtime execution.** Sessions, subprocesses, tools and permissions belong to the host; Olympus coordinates and reconciles results. Do not interpret static tests as live provider/runtime guarantees.
- **OpenCode is the only currently supported runtime.** Historical Codex behavior is not a support or compatibility promise; see the [capability contract](HARNESS-CAPABILITIES.md).
- **Optional native `/goal`** is chosen by the user when available; it is not silently invoked or required.

The present product direction prioritizes Flutter/Android and 2D games with Flame while retaining websites and other software projects. You do not need to install the wider OlympusSuite to use OlympusAgents. Further implementation detail lives in [Development](DEVELOPMENT.md) and [Roadmap](ROADMAP.md).
