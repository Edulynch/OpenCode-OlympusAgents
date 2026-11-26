---
description: Evaluate an explicit performance or optimization task
subagent: false
---

User task:
$ARGUMENTS

If the user task is empty or contains only whitespace, respond only with `Usage: /olympus.performance <prompt>`. Do not call tools or launch agents.

Before using tools, check the already-known current primary. If it is neither Kael nor Atlas, respond only: `Use /olympus.performance from a Kael or Atlas primary session.` Do not call tools, switch agents, or delegate to imitate either primary.

Set `DOMAIN_MODE: PERFORMANCE`. Otherwise treat the task above as explicit optimization intent and follow the current primary's canonical role and Performance Gate; do not duplicate or weaken those rules. Kael applies its Optimization Gate, involving Helios only when a decision materially benefits, and obtains approval for any concrete unsettled direction before implementation. Any implementation still requires before/after/delta/target measurements and correctness validation before acceptance.

Atlas remains read-only: analyze performance and prepare a scoped handoff, using Helios only when useful under the same gate; finish with `PERFORMANCE_PLAN_READY`, preserve unknown measurements as unknown, and do not write, execute, or claim acceptance. This command does not select `/olympus.ultra` or bypass ownership, permission, dependency, reconciliation, validation, or completion gates.
