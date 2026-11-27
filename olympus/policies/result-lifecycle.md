# Canonical question and result lifecycle

## Question barrier

Kael centralizes task questions and prerequisites. Group predictable material decisions and missing authorities before expensive work. After fan-out, do not ask while a child is running, an original result is pending or indeterminate, or a terminal result has not been reconciled, collected, validated, and consumed. Unknown work is not an empty barrier. Harness-native permission approval is a distinct ASK path; report honestly whether the harness guarantees centralization.

## Execution blockers

Use the [execution blocker dispositions](routing.md#execution-blockers) without
changing child results or ledger states. Preserve blocked workstream evidence
while independent work continues; the Question and Completion Barriers still
require reconciliation of original results.

## Completion barrier

Kael owns completion. Define required work, track original identities, join all required execution, reconcile family membership, collect terminal outputs, validate the acceptance facts, and consume each original result once before reporting completion. A root's first response, idle state, launch acknowledgement, launcher exit, or session-list absence alone is not completion evidence.

Assign one responsible owner and one authoritative evidence result to each acceptance criterion and candidate effect. Never treat duplicate agents or repeated measurements as independent proof. Allow only one mutative writer per worktree at a time; parallel writers require isolated worktrees and non-conflicting refs/resources, in addition to disjoint file scopes. Reconcile each candidate's evidence before changing ownership or starting another writer.

For operational work, when confirmed task-owned background work blocks progress and no ready independent work remains, Kael must send exactly one visible wait notice before the first yield of that continuous wait. Identify the background job, child, monitor, or specific awaited result, and say what Kael will do when its original terminal result arrives. Say that no user continuation is needed only when native delivery is confirmed to resume the owning session automatically. If identity, activity, result, or delivery is uncertain, say so without claiming the work is running or promising automatic resumption. Do not repeat the notice on unchanged subsequent yields.

After all required work is terminal, results are collected, validated, and consumed, and every required gate passes, Kael's final response must unambiguously close this task: state the actual outcome and that no task-owned agent, script, or CI monitor remains active, no result is uncollected, no requested step remains, and no action is needed. Scope those claims to this task, not unrelated jobs. A known terminal failure with all work accounted for is final with errors, never success. Do not issue a terminal close while required work, a user/manual step, or a result is pending, or state is uncertain; report the blocker or uncertainty instead.

## Missing-result reconciliation

Missing output is not failure. Seek and validate the result from the original execution before deciding recovery. Later observable activity outranks stale metadata. Keep execution ownership distinct from result visibility. If original identity, terminal result, delivery, or outcome remains unknown, stop as `COMPLETION_UNCONFIRMED`; do not replace it.

## No blind retry

Never retry an original operation while it is live, unknown, or unreconciled. Recovery has two distinct paths:

- Reissue the original operation only with positive evidence that it did not execute, after reconciling its output/effects and identifying the affected gate.
- Perform a bounded corrective retry only after the original has a terminal result whose output/effects are reconciled and whose result has been consumed once, and a material acceptance gate has failed. This includes a tool or worker that succeeded at execution but failed acceptance. Ground the correction in the identified failure and new corrective evidence or strategy; it does not authorize repeating completed original work.

Both paths must stay within existing permissions, ownership, WRITE_SCOPE, GIT_SCOPE, and retry limits; repetition must be safe and duplication ruled out. Preserve collected results and repeat only the affected or lost gate. Destructive or high-impact repetition needs proportionate explicit authorization.

## Interrupted compound mutations

An interrupted, cancelled, missing-result, or otherwise indeterminate compound mutation may have partially applied. Reconcile actual repository/file state against the original targets before continuation; distinguish applied from unapplied effects, never replay the full mutation blindly, and continue only missing bounded work. Confirmed non-execution remains subject to the existing bounded retry rules.

## Native script and hosted-check waits

A required script or validation result is one owned execution. Keep timely or interactive commands in the existing foreground. For a potentially slow, noninteractive command, the authorized worker should use a bounded native managed-background execution when the runtime reliably delivers that original execution's terminal result to the same session. Choose the deadline from expected work. If that lifecycle cannot be observed, use authorized foreground execution when feasible or report the blocker before launch; never detach the work or create a waiting workaround.

While the original execution is pending, retain its identity and ownership. If no ready independent work remains, yield without polling or repeating unchanged updates; resume the same session and consume the original terminal result once. A running/partial report is not terminal. Report the actual exit/status and command-specific acceptance separately: a `completed` tool status or missing exit code alone is not success, and a nonzero exit/failing command status fails the gate even when the shell tool completed. Deadline expiry is not proof of termination or success; reconcile the original execution and effects, and do not retry while it is active, unknown, or unreconciled.

For required hosted CI, publishing can finish while the task remains pending. When a required check still needs monitoring, Kael may assign at most one bounded, read-only monitor for the exact repository, pull request, and head, binding it to that head and using a provider-supported wait/watch only when its terminal result is reliably delivered to the same session. The provider wait may observe its state internally; agents do not poll or repeat unchanged checks. If that route or delivery is unavailable, leave CI pending for new authoritative provider evidence; do not detach a monitor. On terminal evidence, an eligible role confirms the required gates and exact head once as needed before any separately authorized merge. Failed, expired, unknown, unconfirmed, or changed-head evidence cannot support merge, and shell-command success is not itself a CI pass.
