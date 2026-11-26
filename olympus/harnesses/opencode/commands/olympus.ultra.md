---
description: Maximize useful, safe concurrency for one task
subagent: false
---

User task:
$ARGUMENTS

If the user task is empty or contains only whitespace, respond only with `Usage: /olympus.ultra <prompt>`. Do not call tools or launch agents.

Before using tools, check the already-known current primary. If it is neither Kael nor Atlas, respond only: `Use /olympus.ultra from a Kael or Atlas primary session.` Do not call tools, switch agents, or delegate to imitate either primary.

Otherwise treat the task above as the current request and follow the current primary's canonical role, authority, ownership, validation, result, and completion rules. For Kael, Ultra is latency-first through accepted execution; for Atlas, it is latency-first through `PLAN_READY` and a scoped handoff to Kael, never execution.

Use the Ultra admission fields and exact `UNDERFILL_REASON` categories in the canonical routing policy: `ULTRA_CEILING`, `READY_WORKSTREAMS`, `TARGET_ACTIVE`, and observed `CURRENT_ACTIVE`. Dispatch ready, independent work up to `TARGET_ACTIVE`; same-role children are allowed only for genuinely independent work. Use native background child sessions and keep filling available slots as work becomes ready, including across separate dispatch calls. Do not wait for a whole wave, require a single batch, poll, add a scheduler/controller, create artificial fan-out, or repeat checks. Apply the canonical one-mutative-writer-per-worktree rule and resolve shared-resource conflicts before dispatch.

Finish with the canonical compact Ultra receipt. Preserve unknown counts or causes as `UNKNOWN`; never report blocked work as ready or invent counts.
