# Development & qualification

For Olympus maintainers, contributors, installation debugging, qualification, and release engineering. For first-time setup, start with the [README](../README.md).

## Architecture

OpenCode is the runtime; Olympus is the orchestration and decision layer. Kael coordinates seven normal agents (including itself); the hidden Maintenance Plane is separate.

## Local/bootstrap installation

From an Olympus source checkout, bootstrap into the **root of a separate, trusted Git project** on Windows with PowerShell 7, Git, and OpenCode V2 available:

```powershell
pwsh -NoProfile -File ./scripts/bootstrap.ps1 -Target 'C:\path\to\project' -DryRun
pwsh -NoProfile -File ./scripts/bootstrap.ps1 -Target 'C:\path\to\project'
```

`-Target` is required and must be an absolute path to the Git worktree root; `-DryRun` checks and reports the proposed changes without writing them. `scripts/bootstrap.ps1` reads managed assets from its own source checkout and **does not accept `-SourceRoot`**. For local-source installer qualification, `install.ps1` has a qualification-only `-SourceRoot` option; the public installer normally fetches an immutable release tag. Bootstrap rejects unsafe targets independently of trusted-project agent execution.

## Managed installation and recovery

The target's `.opencode/orchestrator-install.json` records installed source commit, managed paths and SHA-256 hashes, plus project detection metadata. Managed assets include the root `opencode.jsonc`, Olympus agents, `/maintain` command, and Activity HUD plugin under `.opencode/`. On reinstall, unchanged managed assets yield `NO_CHANGES` (after effective-agent validation). Missing or modified owned files yield `MANAGED_FILE_DRIFT` rather than a silent overwrite; a destination that already exists without ownership metadata yields `INSTALL_CONFLICT`. Unrelated project files are not installer-owned, although target Git cleanliness is checked before installation.

If drift occurs, inspect the reported path and manifest, back up any intentional edits, then restore the affected owned file from a known-good installation/revision before retrying. Do not delete the manifest or force an overwrite to bypass ownership checks. If the manifest itself is damaged or you cannot establish the installed baseline, stop and investigate before reinstalling; preserve unrelated work.

## Qualification

From the source checkout root, use the current harnesses (PowerShell 7; some require `opencode`, Git, and Node):

```powershell
pwsh -NoProfile -File ./tests/phase4c/qualify.ps1
pwsh -NoProfile -File ./tests/activity-hud/qualify.ps1
pwsh -NoProfile -File ./tests/adaptive-concurrency/qualify.ps1
pwsh -NoProfile -File ./tests/autonomy/qualify.ps1
pwsh -NoProfile -File ./tests/release/qualify.ps1
```

Phase 4C covers bootstrap security and static Maintenance Plane checks; there is no separate Maintenance qualifier. The Activity HUD harness tests presentation, installation, and plugin discovery, not interactive rendering. Adaptive Concurrency / FAST checks are static; the autonomy harness checks effective permissions and bootstrap, not interactive child execution. The release harness uses **local source**, not the remote tag, and does not test the interactive UI. Some harnesses retain disposable fixtures; check their output. The current adaptive-concurrency harness also still expects an older README FAST example, so its `DOC` assertion needs a separate test-maintenance update after the beginner README rewrite; do not interpret that mismatch as a runtime failure.

## Trusted-project execution

Explicitly bootstrapped projects are treated as trusted. Kovan can edit and use shell within its assigned task ownership; Nox can use shell for validation but does not edit source. `WRITE_SCOPE` is an orchestration ownership contract, **not an OS sandbox**: shell can access paths beyond it, so agent instructions still matter. Bootstrap target safety (Git root, containment, conflict and drift checks) remains separate and stricter; agent trust never relaxes installation checks.

## Activity HUD

The passive, read-only plugin uses native OpenCode child-session list and status to show running agents and their tasks. It appears only when direct children are active; it does not spawn sessions, poll, or alter orchestration.

## Maintenance Plane

Kael → Maintenance: **DENIED** (not an automatic escalation path). User → `/maintain <task>` → Maintenance: **ALLOWED** for explicit repository administration. Maintenance is hidden and outside the ordinary seven-agent routing.

## Release process

Run qualification → review release readiness (including remaining static-vs-interactive gaps and documentation) → tag the reviewed commit → validate the installer against the **tagged** source/URL in a clean Git project → publish the release. `tests/release/qualify.ps1` is a local-source check, not a substitute for tagged installer validation. Do not move an existing release tag or change released content as part of documentation maintenance.
