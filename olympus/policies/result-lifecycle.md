# Canonical question and result lifecycle

## Question barrier

Kael centralizes task questions and prerequisites. If a user decision is already known to be required, ask before launching dependent work. After fan-out, do not ask while a child is running, an original result is pending or indeterminate, or a terminal result has not been reconciled, collected, validated, and consumed. Unknown work is not an empty barrier. Harness-native permission approval may be an adapter-specific ASK path; report honestly whether the harness guarantees centralization.

## Completion barrier

Kael owns completion. Define required work, track original identities, join all required execution, reconcile family membership, collect terminal outputs, validate the acceptance facts, and consume each original result once before reporting completion. A root's first response, idle state, launch acknowledgement, launcher exit, or session-list absence alone is not completion evidence.

## Missing-result reconciliation

Missing output is not failure. Seek and validate the result from the original execution before deciding recovery. Later observable activity outranks stale metadata. Keep execution ownership distinct from result visibility. If original identity, terminal result, delivery, or outcome remains unknown, stop as `COMPLETION_UNCONFIRMED`; do not replace it.

## No blind retry

Never retry an original operation while it is live, unknown, or unreconciled. Recovery has two distinct paths:

- Reissue the original operation only with positive evidence that it did not execute, after reconciling its output/effects and identifying the affected gate.
- Perform a bounded corrective retry only after the original has a terminal result whose output/effects are reconciled and whose result has been consumed once, and a material acceptance gate has failed. This includes a tool or worker that succeeded at execution but failed acceptance. Ground the correction in the identified failure and new corrective evidence or strategy; it does not authorize repeating completed original work.

Both paths must stay within existing permissions, ownership, WRITE_SCOPE, GIT_SCOPE, and retry limits; repetition must be safe and duplication ruled out. Preserve collected results and repeat only the affected or lost gate. Destructive or high-impact repetition needs proportionate explicit authorization.

## Interrupted compound mutations

An interrupted, cancelled, missing-result, or otherwise indeterminate compound mutation may have partially applied. Reconcile actual repository/file state against the original targets before continuation; distinguish applied from unapplied effects, never replay the full mutation blindly, and continue only missing bounded work. Confirmed non-execution remains subject to the existing bounded retry rules.
