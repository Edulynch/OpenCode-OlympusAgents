# Canonical authority semantics

- **ALLOW** — the exact operation is already authorized inside the current task's scope and applicable Olympus boundaries. Proceed without duplicate textual pre-approval.
- **ASK** — the operation is legitimate but requires the runtime/user's approval. Approval is the consent point, not advance authorization; refusal or cancellation stops the operation without fallback or bypass.
- **DENY** — the operation crosses a protected Olympus, user-prohibition, or otherwise non-elevatable boundary. Ordinary grants, approvals, role prompts, retries, or harness adaptation cannot elevate it.

These meanings are Core policy, not OpenCode permission syntax. In OpenCode, the
effective native rule governs whether the exact operation can proceed, requests
approval, or is refused; Core separately governs Olympus task scope, consent, and
non-elevatable boundaries. A task grant or approval cannot override an effective
native DENY or weaken Core DENY. Historical Codex deny assertions remain
defensive checks only; they do not declare Codex a currently supported adapter.

## Out-of-scope task result

Use this separate child result only when the assigned role is eligible to perform
an otherwise legitimate operation, but the exact capability, effect, path, or ref
is outside the current task's assigned scope. The operation must remain
unattempted. This result takes precedence over a normal or specialized result
format only for that scope gap; it is not a normal task completion or failure
status:

```text
STATUS: NEED_AUTHORITY
OPERATION: exact capability and effect required
MINIMUM_SCOPE: smallest exact path/ref scope
REPOSITORY_ROOT: affected trusted repository root
REASON: why the assigned scope blocks this unattempted operation
TASK_BLOCKED: exact blocked task
```

The result creates no authority, approval, retry, or permission to act. Workers
do not ask the user, widen scope, or self-route; Kael reconciles the original
child result and classifies the exact request under the existing authority and
Question Barrier flow. Do not erase or replay already-applied authorized effects;
if a material completed effect needs mention, include it in `REASON` and preserve
ordinary result reconciliation.

Do not use `NEED_AUTHORITY` for a different-role request, unproven ownership,
explicit user prohibition, protected or non-elevatable operation, native DENY,
an actual pending native ASK event for an already assigned operation, permission
rejection/cancellation, unknown permission-UI observation, or task
success/failure. Those retain their existing role, ownership, prohibition,
native-permission, and task-result handling; native DENY remains final and
unknown UI or decision evidence remains `NOT_OBSERVABLE`.

An effective native ASK rule on an otherwise legitimate, role-eligible operation
that has not yet been delegated is only a rule outcome, not a tool attempt or an
actual native ASK event. It does not authorize an attempt: keep the operation
unattempted and return `NEED_AUTHORITY` for the exact scope gap. After Kael
correctly assigns the exact operation with its required current-task
`NATIVE_ASK` grant, invoke it once and let OpenCode handle any actual pending
native ASK event. That event and its approval, rejection, or cancellation stay
in the existing host-consent flow, not `NEED_AUTHORITY`; do not send a duplicate
Kael QUESTION, retry, or bypass a refusal. This distinction does not widen,
renew, or transfer a task scope or grant.
