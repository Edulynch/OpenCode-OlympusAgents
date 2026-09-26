# Development & qualification

For Olympus maintainers, contributors, installation debugging, qualification, and release engineering. For first-time setup, start with the [README](../README.md).

## Architecture

OpenCode is the runtime; Olympus is the orchestration and decision layer. Kael coordinates seven normal agents (including itself); the hidden Maintenance Plane is separate.

Kael checks feasibility and plane routing from the request **before** delegated research or planning. Known Maintenance-only operations receive a user-facing `/maintain <task>` handoff, not automatic delegation. Feasible work starts with task-scoped discovery (none, targeted file, or bounded subsystem) and widens only for an unresolved target/boundary, evidence of wider impact, or a genuinely repository-wide request. Broad research remains available when justified.

## Local/bootstrap installation

From an Olympus source checkout, bootstrap into the **root of a separate, trusted Git project** on Windows with PowerShell 7, Git, and OpenCode V2 available. The v0.2.0 public installer can be launched from Windows PowerShell 5.1 or PowerShell 7, but delegates bootstrap to installed `pwsh`:

```powershell
pwsh -NoProfile -File ./scripts/bootstrap.ps1 -Target 'C:\path\to\project' -DryRun
pwsh -NoProfile -File ./scripts/bootstrap.ps1 -Target 'C:\path\to\project'
```

`-Target` is required and must be an absolute path to the Git worktree root; `-DryRun` checks and reports the proposed changes without writing them. `scripts/bootstrap.ps1` reads managed assets from its own source checkout and **does not accept `-SourceRoot`**. For local-source installer qualification, `install.ps1` has a qualification-only `-SourceRoot` option; the public installer normally fetches an immutable release tag. Bootstrap rejects unsafe targets independently of trusted-project agent execution.

## Managed installation and recovery

The target's `.opencode/orchestrator-install.json` records installed source commit, managed paths and SHA-256 hashes, plus project detection metadata. Managed assets include the root `opencode.jsonc`, Olympus agents, `/maintain` command, and Activity HUD plugin under `.opencode/`. On reinstall, unchanged managed assets yield `NO_CHANGES` (after effective-agent validation). Missing or modified owned files yield `MANAGED_FILE_DRIFT` rather than a silent overwrite; a destination that already exists without ownership metadata yields `INSTALL_CONFLICT` (including protected foreign OpenCode configuration).

Olympus does **not** require a globally clean target Git worktree. Unrelated modified, staged, untracked and tool-generated files (including unrelated content under `.opencode/`) are allowed and preserved. Safety is based on explicit managed destinations and ownership hashes, Git-root validation, and path containment; unsafe targets and unmanaged destination collisions still block. The installer never stashes, resets, cleans, stages, or normalizes user work.

If drift occurs, inspect the reported path and manifest, back up any intentional edits, then restore the affected owned file from a known-good installation/revision before retrying. Do not delete the manifest or force an overwrite to bypass ownership checks. If the manifest itself is damaged or you cannot establish the installed baseline, stop and investigate before reinstalling; preserve unrelated work.

## Qualification

From the source checkout root, use the current harnesses (PowerShell 7; some require `opencode`, Git, and Node):

```powershell
pwsh -NoProfile -File ./tests/phase4c/qualify.ps1
pwsh -NoProfile -File ./tests/activity-hud/qualify.ps1
pwsh -NoProfile -File ./tests/adaptive-concurrency/qualify.ps1
pwsh -NoProfile -File ./tests/autonomy/qualify.ps1
pwsh -NoProfile -File ./tests/release/qualify.ps1
pwsh -NoProfile -File ./tests/release/installer-compatibility.ps1
pwsh -NoProfile -File ./tests/release/dirty-worktree.ps1
pwsh -NoProfile -File ./tests/preflight/qualify.ps1
pwsh -NoProfile -File ./tests/completion-gates/qualify.ps1
pwsh -NoProfile -File ./tests/result-reconciliation/qualify.ps1
```

Phase 4C covers bootstrap security and static Maintenance Plane checks; there is no separate Maintenance qualifier. The Preflight harness checks policy ordering, boundaries and a small cart/auth fixture **statically**; it does not execute agents or verify actual child count, discovery tool calls or latency. The Activity HUD harness tests presentation, installation, and plugin discovery, not interactive rendering. Adaptive Concurrency / FAST checks are static; the autonomy harness checks effective permissions and bootstrap, not interactive child execution. The release, dirty-worktree, and installer compatibility harnesses use **local source**, not the remote tag, and do not test the interactive UI. The dirty-worktree harness checks unrelated bytes, Git status, index diffs, managed conflict/drift, reinstall and a local-source managed update. The compatibility harness launches the installer via both Windows PowerShell 5.1 (when present) and PowerShell 7 into separate disposable Git projects, and tests missing `pwsh` with a process-local PATH. Some harnesses retain disposable fixtures; check their output. The adaptive-concurrency harness's `DOC` check verifies that the README describes NORMAL as the default using only useful parallelism, FAST as explicitly requested with up to four agents, and FAST as preserving checks and task dependencies.

## Result correlation safety (Issue #1)

A missing parent tool output is **not** evidence that delegated work failed or never started. In the two historical observations, the parent correlation error preceded the original Nox child's terminal result; both terminal results persisted. The exact OpenCode runtime trigger is unproven. Kael first reconciles an identifiable original child through native completion/results, retaining its assignment until it can consume and validate the original result once. Observable terminal session truth outranks an earlier parent correlation error. If the original cannot be recovered or execution cannot be disproved, report completion unconfirmed rather than blindly retry, including for read-only work and especially for side effects. Only positive native evidence of non-execution makes a bounded retry eligible. No poller, resolver or persistent dedupe state is added. Phase 3's Kael-mediated iterative evidence loops inherit this rule: never feed a reasoner fabricated failure or replacement evidence for an indeterminate worker; reconcile the original or stop unconfirmed. The focused deterministic fixture is `tests/result-reconciliation/qualify.ps1`; manual live instructions are in `tests/result-reconciliation/live-control.md`. Neither claims to reproduce the intermittent runtime race.

## Trusted-project execution

Explicitly bootstrapped projects are treated as trusted. Kovan can edit and use shell within its assigned task ownership; Nox can use shell for validation but does not edit source. `WRITE_SCOPE` is an orchestration ownership contract, **not an OS sandbox**: shell can access paths beyond it, so agent instructions still matter. Bootstrap target safety (Git root, containment, conflict and drift checks) remains separate and stricter; agent trust never relaxes installation checks.

## Activity HUD

The passive, read-only plugin uses native OpenCode child-session list and status to show running agents and their tasks. It appears only when direct children are active; it does not spawn sessions, poll, or alter orchestration.

## Maintenance Plane

Kael → Maintenance: **DENIED** (not an automatic escalation path). User → `/maintain <task>` → Maintenance: **ALLOWED** for explicit repository administration. Maintenance is hidden and outside the ordinary seven-agent routing.

Maintenance separates repository administration from software-development investigation. Git-only operations start with Git-scoped non-mutating feasibility checks (target, scope, state, remote and tools as relevant), not application architecture. Read/authentication evidence alone does not prove remote write permission.

Parallel Maintenance administration is permitted through shell and OpenCode session APIs, not through Olympus child-agent routing. It must track every launched root and descendant, join, collect and validate required results before declaring success; unknown/uncollected children mean PARTIAL or COMPLETION_UNCONFIRMED. Do not serialize independent jobs as a substitute for joining them.

External work ownership is the outer lifecycle rule for work Maintenance launches to fulfill the current user request: PowerShell processes, scripts/controllers, builds, tests, benchmark controllers, disposable validation and OpenCode roots created through session APIs. Normal synchronous commands whose tool call returns only on completion are already owned. **Foreground/join is mandatory**, regardless of duration or a request to run in the background: launch → track → wait/join → collect → validate → final response. Maintenance briefly explains that it will wait rather than detach. Progress updates are not final responses. A launcher exit is not sufficient when subordinate work survives it; reuse the family-aware completion gate below. A reliably completing controller can own its own subordinate jobs; Maintenance waits for and validates its terminal report rather than duplicating that controller's tracking. Independent external jobs can still run in parallel, provided all required jobs are joined before finalization.

Before launch, ensure the full lifecycle can be observed and joined; otherwise report BLOCKED without launching. No detached handoff, user PID/status polling, global registry, daemon or scheduled monitor. On Windows, necessary child processes must be headless (no visible console or focus stealing) while Maintenance captures their output, errors, exit code and results. Prefer direct shell execution to extra child shells. On a finite timeout, inspect and safely stop owned work when possible, then report TIMEOUT/PARTIAL/BLOCKED without silently leaving required jobs active. Kael relays only the terminal Maintenance outcome, not an in-progress controller as a finished task.

For local static/semantic policy and disposable external-process qualification, run `pwsh -NoProfile -File ./tests/external-work-ownership/qualify.ps1`. Its live foreground controller and parallel cases measure launch, terminal and simulated Maintenance final times, but do not themselves constitute interactive Maintenance-agent or visible-window observation; run an interactive `/maintain` smoke separately if required.

OpenCode v2.0.15 completion semantics: `POST /api/session/{sessionID}/command` executes a slash-command callback immediately; `POST /api/session/{sessionID}/prompt` durably admits input and schedules execution. A CLI `opencode run` exit or a root assistant response is not a session-family completion signal. `POST /api/experimental/session/{sessionID}/wait` waits for **one** agent loop to become idle (HTTP 204), not its descendants or a terminal result. `GET /api/session/active` lists only foreground drains owned by that server process: absence is not proof of terminal completion. Use `GET /api/session?parentID=<root>` (paginate), recursively discover descendants, `GET /api/session/{sessionID}` (outcome, time.idle), `GET /api/session/{sessionID}/inbox` and messages/export to verify terminal result and parent consumption. Recheck family membership before concluding. There is no documented family-wide wait in this version. Distinguish MESSAGE_COMPLETE, ROOT_IDLE and FAMILY_COMPLETE (the last is a validated workflow condition, not an OpenCode API status). If a child has no terminal outcome/result, classify it as unconfirmed even if the root has gone idle. Bounded waits must end with an honest PARTIAL/BLOCKED report rather than fabricate success.

## Release process

Run qualification → review release readiness (including remaining static-vs-interactive gaps and documentation) → tag the reviewed commit → validate the installer against the **tagged** source/URL in disposable Git projects → publish the release. `tests/release/qualify.ps1` is a local-source check, not a substitute for tagged installer validation. Do not move an existing release tag or change released content as part of documentation maintenance.
