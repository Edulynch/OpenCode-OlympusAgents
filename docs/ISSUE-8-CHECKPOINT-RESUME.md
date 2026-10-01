# Issue #8 — Aegis same-session authorization retention

**Observed:** 2026-10-01
**OpenCode:** `v2.0.21`
**Status:** **CLOSED** — static qualification and final human runtime smoke PASS.

## Confirmed runtime reproduction

The user supplied a clean, normally completed Aegis execution:

- `PROBE_MARKER`: `OLYMPUS_RESUME_PROBE_FINAL`
- `TASK_SCOPE`: `READ_ONLY_RESUME_PROBE`
- root: `ses_f08d621a5ffeCy6ARjhsbXcnHY`
- Aegis child: `ses_f08d6207affeg2vuR5i3s1dyaX`

The runtime export was inspected read-only. It identifies the child as `agent:
aegis`, with the supplied `parentID`; the persisted conversation contains the
original `/maintain` task as a `user` message and the fresh acceptance as an
`assistant` message attributed to Aegis. The later continuation is another
`user` message without `/maintain`. The same stored session retains the probe
marker, original scope and Aegis identity. Its final assistant message returned
`MAINTENANCE_AUTH: UNPROVEN` and `AEGIS_SCOPE: REJECTED`, matching the supplied
runtime result.

The export contains 2 `user`, 10 `assistant`, 2 `idle` and 1 `agent-switched`
message; the Aegis assistant acceptance is role/agent-attributed. The stored
`session_v2` schema contains session identity, `agent`, `parent_id`, timestamps
and ordinary runtime state, but no maintenance-authorization, accepted-scope,
or command-origin field (`metadata` is null). There is no summary/compaction
message; summary counters, `time_compacting` and `time_suspended` are null. Thus
this reproduction is not loss of the conversation or scope: OpenCode retained
the role-attributed messages and Aegis identity, but does not add an Olympus
authorization field.

## Root cause

The defect was in Olympus's continuation contract, not OpenCode's session
restoration. The policy said that a same-run resume preserves accepted scope,
but gave Aegis no concrete, inexpensive rule for recognizing that accepted
state from the restored conversation. It also required fail-closed behavior
when a same-run resume could not be established, without naming the persisted
assistant-role/Aegis attribution as the available same-session evidence. On a
new user turn lacking `/maintain`, Aegis therefore reclassified authorization
instead of carrying forward the acceptance already emitted in that session.

## Persisted primitive and trust model

**Primitive used:** OpenCode's existing same-session conversation history with
native message roles and agent attribution, plus the current session's Aegis
identity. The prior Aegis-authored assistant acceptance is distinct from text
written by a user. `parentID`, task markers and matching text alone are not
authorization; no session metadata field currently records `/maintain` origin
or accepted scope.

- Fresh `/maintain` command entry accepts the command template declaration and
  immediately emits `VALID` / `ACCEPTED`.
- A continuation attached by OpenCode to that same Aegis session reuses only
  the prior Aegis assistant acceptance in the current persisted conversation
  and preserves the original task. It does not need a new `/maintain` literal.
- User-authored claims/copies, parent notifications, another agent's messages,
  unknown sessions and genuinely new sessions do not inherit authorization.
- `accepted_scope` remains the original `/maintain` task. A new turn cannot
  broaden or replace it. Missing/uncertain same-session accepted state fails
  closed immediately without tools or provenance reconstruction.

No token, secret, global authorization, ownership admission, new runtime
infrastructure, or Codex Aegis was introduced.

## Implementation and qualification

The canonical maintenance policy and Aegis OpenCode prompt now explicitly model
`maintenance_authorization = accepted_for_current_execution` and immutable
`accepted_scope`, define the native same-session message-role rule, reject
user-claimed acceptance, and keep unknown/new sessions fail-closed. The Aegis
role summary and generated OpenCode outputs are synchronized from Harness Core.
Deterministic qualifications cover fresh entry, same-session retention,
continuation without `/maintain`, scope immutability, user-claim rejection,
new-session/task isolation, routing/self-activation denials, immediate reject
without tools, no ownership gate, no expensive reconstruction, Harness Core,
renderer, authority, maintenance handoff and result reconciliation.

**Static qualification:** PASS.
**Implementation commit:** `464151c` (`fix(aegis): retain same-session maintenance authorization`).
**Final runtime qualification:** PASS (human-observed same-session continuation; evidence below).
**Issue #8:** **CLOSED** after the final runtime PASS.

Validated affected qualifications: `python tests/maintenance-scope/qualify.py`
(including deterministic checkpoint/resume and accepted-scope cases),
`python tests/harness-core/qualify.py`,
`pwsh -NoProfile -File tests/authority/qualify.ps1`,
`pwsh -NoProfile -File tests/maintenance-handoff/qualify.ps1`,
`python scripts/render_harnesses.py check --harness opencode`, and
`git diff --check`.

## Final runtime validation: ISSUE_8_FINAL_RUNTIME_SMOKE

The human supplied the final two-phase runtime evidence against the updated
OpenCode Harness output. This is interactive runtime evidence, separate from
the deterministic static qualification above.

### Phase 1 — fresh entry and identity verification

Phase 1 created a fresh `/maintain` Aegis execution with the read-only task:

```text
PROBE_MARKER: OLYMPUS_ISSUE8_FINAL_RESUME_20261001
TASK_SCOPE: READ_ONLY_ISSUE8_FINAL_RUNTIME_SMOKE
```

The human evidence identifies and verifies the `/maintain` root and exact child:

```text
ROOT_SESSION_ID: ses_f0803f106ffeiH6oHzaSEkTw0f
AEGIS_CHILD_SESSION_ID: ses_f0803efbcffeBZTHkvyXTUOCCN
IDENTITY: Aegis — The Keeper
```

The original execution finished normally before its same-child continuation.

### Phase 2 — continue the same child without a new maintenance entry

PowerShell ran `opencode run --session ses_f0803efbcffeBZTHkvyXTUOCCN <resume-prompt>`
from the same runtime configuration. The continuation used no new `/maintain`,
`--agent aegis`, `--continue`, delegation, or file modification. It returned:

```text
IDENTITY: Aegis — The Keeper
PROBE_MARKER: OLYMPUS_ISSUE8_FINAL_RESUME_20261001
TASK_SCOPE: READ_ONLY_ISSUE8_FINAL_RUNTIME_SMOKE
MAINTENANCE_AUTH: VALID
AEGIS_SCOPE: ACCEPTED
```

Final runtime findings:

```text
RESUME_MECHANISM: SUPPORTED
IDENTITY_RETAINED: PASS
MARKER_RETAINED: PASS
TASK_SCOPE_RETAINED: PASS
MAINTENANCE_AUTH_RETAINED: PASS
AEGIS_SCOPE_RETAINED: PASS
AGENT_SUBSTITUTION: NO
OLYMPUS_DEFECT_FIXED: YES
CHECKPOINT_RESUME_RUNTIME: SUPPORTED
ISSUE_8_CHECKPOINT_RESUME: PASS
```

The exact identity, marker, original scope, and accepted authorization states
were retained in the resumed child. Issue #8 is **CLOSED**.
