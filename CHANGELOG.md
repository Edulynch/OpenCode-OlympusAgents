# 0.2.0

## Added

- Capability Preflight decides routing boundaries before unnecessary research or delegation.
- Task-scoped, progressive repository discovery starts narrow and expands only when warranted.
- Reliable completion gates require delegated results to be terminal, collected and consumed before claiming completion.
- Maintenance keeps external work foreground-owned through its terminal outcome, including parallel work.
- A maintainer-facing [development roadmap](docs/ROADMAP.md).

## Changed

- Repository administration can be redirected to explicit `/maintain` before application research.
- Missing parent tool output does not imply child failure or authorize a blind retry: Olympus reconciles the original child when possible and reports `COMPLETION_UNCONFIRMED` when execution cannot be established safely.

## Known limitations

- The intermittent OpenCode result-correlation trigger tracked by Issue #1 remains unidentified and unfixed; v0.2.0 mitigates unsafe retry behavior.
- NORMAL and FAST remain capped at four concurrent children. Planned Role Purity and new specialist agents are not included.

# 0.1.2

Installer/bootstrap hotfix:

- Installation and reinstall no longer require an otherwise clean project worktree.
- Preserve unrelated modified, staged, untracked and tool-generated project files without touching their index state.
- Keep managed destination conflict, ownership, unsafe-target and managed-file drift protections enforced.

# 0.1.1

Windows installer hotfix:

- Launch the one-line installer from Windows PowerShell 5.1 or PowerShell 7.
- PowerShell 7 remains required and runs the bootstrap; missing `pwsh` now fails early with a clear message.

# 0.1.0

Initial Windows-qualified OpenCode V2 release candidate:

- Kael orchestration and six specialist children, with a separate hidden Maintenance Plane.
- Passive live Activity HUD; adaptive concurrency 0–4 and explicit FAST fan-out.
- Zero-prompt trusted-project Kovan implementation and Nox validation.
- Managed project bootstrap with target safety, drift checks, idempotency and qualification harnesses.
