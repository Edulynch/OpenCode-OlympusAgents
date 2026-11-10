# Working with Olympus

The [README](../README.md) is the quick-start page. This guide explains the roles, prompt modes and boundaries in more detail. Olympus is a team coordinated by Kael, not an additional model subscription or an autonomous runtime outside OpenCode. Configure access to the models you plan to use in your own harness.

## Try a task

### Build something

Open OpenCode in your project and describe the outcome:

> Create a Flutter habit tracker. Start with a simple home screen, local storage, and one test for the save flow. Ask me before choosing an external database.

### Diagnose and fix

> Find why this API responds with HTTP 500 for valid input. Reproduce it, fix the cause, and run the tests relevant to the changed module.

### Ask for independent work

> Review these four independent modules for reproducible issues. Fix the confirmed bugs, preserve required checks, and summarize the results.
>
> FAST

FAST is selected explicitly by the user's task. It is not a command that grants broader permissions or guarantees that four workers will run.

## The team

Kael is the single coordinator. Olympus Core defines **11 canonical roles**; OpenCode uses 11 agents, while Codex represents Kael as root plus ten specialist agents. These are responsibilities, not a guarantee of runtime parity.

| Icon | Role | Focus |
| --- | --- | --- |
| 🧭 | **Kael** · The Master | Coordinate, select specialists and reconcile results |
| 🔎 | **Veyra** · The Explorer | Gather relevant evidence |
| 🏗️ | **Orin** · The Architect | Design solutions within the agreed scope |
| 🗺️ | **Atlas** · The Planner | Sequence and bound execution |
| 💻 | **Kovan** · The Coder | Implement approved changes |
| 🐛 | **Argus** · The Bug Hunter | Reproduce and diagnose defects |
| 🧪 | **Nox** · The Tester | Verify observed behavior |
| ⚖️ | **Vera** · The Judge | Review independently |
| 🛡️ | **Talos** · The Sentinel | Assess security risks |
| 🧠 | **Thales** · The Sage | Resolve difficult uncertainty |
| 🚀 | **Helios** · The Optimizer | Examine performance tradeoffs |

The canonical definitions remain in [Olympus Core](../olympus/README.md). Model/provider availability depends on the user's OpenCode or Codex configuration.

## NORMAL vs FAST

| Mode | Selection | What changes |
| --- | --- | --- |
| **NORMAL** | Default | Kael uses only useful, bounded parallelism; simple tasks need no fan-out. |
| **FAST** | Explicit request | When work is independent and safe to split, Kael may use up to **four** active agents. Required checks, writer ownership, dependencies, permissions and completion gates remain unchanged. Dependent tasks never run in parallel just to fill the limit. |

### Optional OpenCode task modifiers

These are **experimental, opt-in prompt markers for Kael on OpenCode V2 only**, not native OpenCode slash commands, CLI flags or runtime features. A controlled A/B test observed completed tasks but **did not establish causal performance improvements** from the modifiers ([issue #92 evidence](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/92#issuecomment-6440098753)).

Place the markers on their own unquoted lines in the **final contiguous block of the task prompt**. They are exact and case-sensitive. For example:

```text
Find the smallest safe fix for the failing API test. Run the relevant checks.

surgical-mode
```

| Marker | Intent | Does not change |
| --- | --- | --- |
| `long-mode` | Reduce optional questions while using the information already available | User approval and authorization requirements |
| `fast-mode` | Request the existing FAST policy | Task dependencies, writer ownership, completion gates or the four-agent ceiling |
| `surgical-mode` | Focus on the requested change and avoid unrelated edits | Necessary tests and safety reviews |

Markers may be combined at the end of a single task; they do not persist into future tasks. Ordinary mentions in documentation, code, quotations or nonterminal prose do not activate them. Ambiguous placement leaves NORMAL behavior unchanged. They are instructions to Kael, **not a parser or a runtime guarantee**. The canonical behavior is maintained in [Kael's OpenCode adapter source](../olympus/harnesses/opencode/agent-prompts/kael.md).

## Contextual maintenance and ownership

- **Kael orchestrates** work inside OlympusAgents and other projects using the same normal team. There is no active Aegis role or `/maintain` command.
- **The user owns product decisions.** Kael checks project identity, scope and feasibility before involving specialists; it cannot silently expand authorization.
- **OpenCode owns runtime execution.** Sessions, subprocesses, tools and permissions belong to the host; Olympus coordinates and reconciles results. Do not interpret static tests as live provider/runtime guarantees.
- **Codex remains frozen compatibility.** OpenCode supports the current contextual maintenance workflow; Codex currently declares it a capability gap. See the [capability matrix](HARNESS-CAPABILITIES.md) and [Codex policy](CODEX-COMPATIBILITY.md).
- **Optional native `/goal`** is chosen by the user when available; it is not silently invoked or required.

The present product direction prioritizes Flutter/Android and 2D games with Flame while retaining websites and other software projects. You do not need to install the wider OlympusSuite to use OlympusAgents. Further implementation detail lives in [Development](DEVELOPMENT.md) and [Roadmap](ROADMAP.md).
