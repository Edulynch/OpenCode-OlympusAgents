# Working with Olympus

Start with the quick guide in [English](../README.md) or [Español](../README.ES.md). This guide explains task commands and workflow boundaries. Olympus coordinates agents within OpenCode; configure model access in OpenCode as usual.

## Try a task

### Build something

Open OpenCode in your project and describe the outcome:

> Create a Flutter habit tracker. Start with a simple home screen, local storage, and one test for the save flow. Ask me before choosing an external database.

### Diagnose and fix

> Find why this API responds with HTTP 500 for valid input. Reproduce it, fix the cause, and run the tests relevant to the changed module.

### Ask for independent work

> `/olympus.ultra Review these four independent modules for reproducible issues. Fix confirmed bugs, preserve required checks, and summarize the results.`

The command asks Kael to maximize useful, safe concurrency within the configured ceiling; it does not grant broader permissions or guarantee that any particular number of workers will run.

## The team

Kael coordinates the [eleven-agent team](../README.md#the-team) ([Español](../README.ES.md#the-team)). [Olympus Core](../olympus/README.md) defines the role boundaries.

## Parallelism

| Policy | Selection | What changes |
| --- | --- | --- |
| **Default** | Any ordinary task | Kael adapts parallelism to useful independent work; simple tasks need no fan-out. The global prompt ceiling can be set from 1 to 8 per root session. |
| **Ultra** | `/olympus.ultra <prompt>` | Kael actively seeks useful independent work up to the configured ceiling. It is not a target; dependencies, ownership, permissions, validation and completion gates remain unchanged. This prompt policy does not enforce the native scheduler. |

### Native task commands

The global OpenCode installation provides exactly these two namespaced commands:

```text
/olympus.ultra <prompt>
/olympus.performance <prompt>
```

There are no bare `/ultra` or `/performance` aliases. Both commands run in the current Kael session, accept the full task text, and retain normal role, authority, native-permission, dependency, validation, reconciliation and completion gates. Empty or whitespace-only arguments display usage and must not trigger tools or agents; this guard is in the prompt because native command metadata has no required-argument field, so it is not deterministic runtime enforcement.

`/olympus.ultra` asks Kael to launch ready, independent assignments together up to the configured 1–8 ceiling. More eligible work can start as slots free up. Kael does not fill slots with duplicate, overlapping, dependent or otherwise unhelpful work.

`/olympus.performance` is explicit optimization intent. Kael uses the existing target/baseline/Helios gate when useful, presents a concrete proposal and stops for human approval before implementation unless the user already approved a sufficiently specific direction with understood tradeoffs. Optimization does not automatically select Ultra. Successful implementation still requires before/after/delta/target evidence and correctness validation. The canonical behavior is maintained in [Kael's OpenCode adapter source](../olympus/harnesses/opencode/agent-prompts/kael.md).

## Contextual maintenance and ownership

- **Kael orchestrates** work inside OlympusAgents and other projects using the same normal team. There is no active Aegis role or `/maintain` command.
- **The user owns product decisions.** Kael checks project identity, scope and feasibility before involving specialists; it cannot silently expand authorization.
- **OpenCode owns runtime execution.** Sessions, subprocesses, tools and permissions belong to the host; Olympus coordinates and reconciles results. Do not interpret static tests as live provider/runtime guarantees.
- **OpenCode is the only currently supported runtime.** Historical Codex behavior is not a support or compatibility promise; see the [capability contract](HARNESS-CAPABILITIES.md).
- **Optional native `/goal`** is chosen by the user when available; it is not silently invoked or required.

The present product direction prioritizes Flutter/Android and 2D games with Flame while retaining websites and other software projects. You do not need to install the wider OlympusSuite to use OlympusAgents. Further implementation detail lives in [Development](DEVELOPMENT.md) and [Roadmap](ROADMAP.md).
