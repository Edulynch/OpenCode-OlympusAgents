# Manual live control (not executed by Maintenance)

Use an installed Olympus in a disposable **trusted** project and a fresh Kael
conversation. This is a manual control of ordinary read-only delegation without
a correlation error, not evidence that the intermittent Issue #1 race is fixed.

1. Ask: "Have Nox read and validate the headings in this project's README.md;
   do not edit files. Report the actual heading list and validation result."
   Ensure README.md exists first. Record original native child session identity
   if surfaced, and the parent result/notification.
2. Wait for the original child to finish using normal native completion delivery.
   Verify that Kael consumes its terminal result once, describes the headings,
   and does not claim completion from a launch acknowledgement or idle root alone.
3. Verify the project tree was not changed and record the observed terminal
   result. If output correlation fails, do not run a replacement: inspect only
   native information already available to the parent; classify an unidentified
   execution as completion unconfirmed. Do not claim a race was reproduced unless
   a real correlation error and its event ordering were observed.

## Optional bounded read-only reproduction (manual)

In separate fresh Kael conversations, repeat the above **at most three times**
with Nox-only read-only tasks (distinct README headings or checked-in text files).
Stop after three attempts or the first observed error, whichever comes first.
Record the parent error time, known original child identity (if available),
native terminal time/result and Kael's decision; do not infer the runtime trigger.
Never use Kovan, writes, retry-on-unknown, polling, or an automated fan-out.
If no error occurs, report "not reproduced" rather than passing a race test.
