# Issue #8 — Aegis checkpoint/resume runtime evidence

**Observed:** 2026-10-01

**OpenCode:** `v2.0.21`

**Classification:** `CHECKPOINT_RESUME_RUNTIME: GAP`

## Runtime mechanism found

The installed CLI exposes session continuation, not an explicit checkpoint
primitive:

- `opencode run --help` lists `--continue` / `-c` (“Continue the last
  session”) and `--session` / `-s <id>` (“Session ID to continue, or to create
  if it does not exist”).
- `opencode session --help` lists `list`, `delete`, `export`, and `import`; it
  has no checkpoint, pause, or restore operation.
- The local session API (`opencode api session.list` and `session.get`) exposes
  persisted session identity and agent metadata. The live session for this
  task is identified as an Aegis child of the `/maintain` root. This confirms
  the fresh command entry and current session identity only; it is not evidence
  that this session was interrupted and resumed.

Thus `opencode run --session <id>` is the available continuation mechanism for
a stored conversation. The inspected runtime surface provides no explicit
checkpoint/controlled-interruption control or native marker proving that a
continued session retains the original Aegis execution's accepted scope after
context loss.

## Smoke result and safety boundary

This task itself entered through `/maintain`; it immediately emitted
`MAINTENANCE_AUTH: VALID` and `AEGIS_SCOPE: ACCEPTED` before any tool use. No
repository changes were made during runtime inspection.

A real same-run interruption/resume smoke was **not** run. From an already
running Aegis child, the installed CLI exposes no safe way to pause this agent
turn and resume it later within the same foreground-owned execution. Starting
another `/maintain` smoke would create another Aegis child (delegation), which
is prohibited for this executor; sending a continuation to the currently active
session could race with the existing turn and would not be a controlled
checkpoint/resume. No PASS is inferred from static qualification, CLI session
continuation, or current session metadata.

The current fresh invocation demonstrates command-entry acceptance only.
Authorization retention, task-scope retention, a no-reconstruction resume, and
non-inheritance by a genuinely new unauthenticated Aegis execution remain
unproven. The unauthenticated Aegis path was not forced because that would test
a prohibited entry route. No Olympus authorization-contract fix is justified
by this observation.

## Outcome

- Fresh `/maintain` acceptance: **PASS** (current run only).
- Checkpoint creation: **UNSUPPORTED** by the inspected CLI surface.
- Same-run resume: **UNPROVEN**; stored-session continuation exists, but the
  required Aegis authorization-retention behavior was not safely exercised.
- Authorization/task scope retained: **UNPROVEN**.
- Authorization reconstruction loop: **UNPROVEN** (no resume occurred).
- Issue #8 remains **OPEN** pending a safe, real same-run runtime observation.

Static checks remain useful contract qualifications, not substitutes for the
missing runtime evidence. See `tests/maintenance-scope/qualify.ps1` and the
maintenance/routing/authority qualification results recorded with this change.
