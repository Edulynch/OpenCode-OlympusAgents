# Manual explicit Maintenance handoff (prepared; not run by Maintenance)

In a disposable trusted project with Olympus installed from the candidate,
start a fresh Kael conversation. The human user explicitly invokes:

`/maintain Read only the first line of README.md and report it verbatim, or report README_MISSING if the file does not exist. Do not edit files, launch external work, or repeat the operation.`

1. Record the first line beforehand (or confirm absence); record the original
   Maintenance child identity and native terminal result if surfaced. This is a
   deterministic read-only check, not an elevated mutation or Issue #2 repro.
2. Let the original invocation finish through normal native delivery. Check that
   Kael presents the actual first line or README_MISSING and acknowledges the
   completed result, not just a launch acknowledgement. Verify no files changed.
3. If an early tool error occurs naturally, **do not retry**. If the original
   child is identifiable and still executing, expect an IN PROGRESS response:
   "Maintenance is still completing; I'm waiting for its original result."
   Wait for its original terminal result and confirm Kael consumes it once.
   If identity is unavailable or a terminal result remains unrecoverable after
   bounded native reconciliation, expect COMPLETION_UNCONFIRMED without retry.
   Do not claim Olympus changes any platform failure badge.

Record result, whether error/badge occurred and whether it persisted; no error
is required for acceptance. This manual control is **not executed** by the
static/synthetic qualifier or by Maintenance in this task.
