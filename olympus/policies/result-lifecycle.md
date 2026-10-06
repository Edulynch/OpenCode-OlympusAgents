# Canonical question and result lifecycle

## Question barrier

Kael centralizes task questions and prerequisites. If a user decision is already known to be required, ask before launching dependent work. After fan-out, do not ask while a child is running, an original result is pending or indeterminate, or a terminal result has not been reconciled, collected, validated, and consumed. Unknown work is not an empty barrier. Harness-native permission approval may be an adapter-specific ASK path; report honestly whether the harness guarantees centralization.

## Completion barrier

Kael owns completion. Define required work, track original identities, join all required execution, reconcile family membership, collect terminal outputs, validate the acceptance facts, and consume each original result once before reporting completion. A root's first response, idle state, launch acknowledgement, launcher exit, or session-list absence alone is not completion evidence.

## Missing-result reconciliation

Missing output is not failure. Seek and validate the result from the original execution before deciding recovery. Later observable activity outranks stale metadata. Keep execution ownership distinct from result visibility. If original identity, terminal result, delivery, or outcome remains unknown, stop as `COMPLETION_UNCONFIRMED`; do not replace it.

## No blind retry

Never retry an unknown or live original. Retry only after positive evidence that the prior operation did not execute, the original output/effects have been reconciled, the affected gate is identified, repetition is safe, and duplication is ruled out. Preserve collected results and repeat only the lost gate. Destructive or high-impact repetition needs proportionate explicit authorization.

## Interrupted compound mutations

An interrupted, cancelled, missing-result, or otherwise indeterminate compound mutation may have partially applied. Reconcile actual repository/file state against the original targets before continuation; distinguish applied from unapplied effects, never replay the full mutation blindly, and continue only missing bounded work. Confirmed non-execution remains subject to the existing bounded retry rules.
