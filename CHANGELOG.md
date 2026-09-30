# Unreleased

## v0.3.0-beta.4

**Status: local release candidate; no tag or GitHub Release created.**

### Highlights

- Add Olympus Harness Core as the single canonical role, policy, model-intent, orchestration, and capability source; render deterministic OpenCode and Codex adapters from it.
- Retain experimental Codex runtime support and bounded multi-agent orchestration (up to four children); this is not full Codex parity.
- Map Sol roles to GPT-6.1 Sol while Luna roles remain GPT-6 Luna, with canonical reasoning efforts preserved.
- Publish the adapter capability contract: OpenCode hard DENY remains supported; Codex DENY and Codex Aegis remain documented gaps.
- Add the Aegis Early Scope Gate and classify maintenance by target ownership, not by the requested operation.
- Fix `/maintain` generated frontmatter and the runtime handoff so the explicit command routes to hidden Aegis.
- Retain the tagged-source installer contract, managed-file hashes, and read-only `-VerifyOnly` checks.

### Known limitations

- OpenCode V2 Issue #1 (`No tool output found`) remains open and upstream; Olympus does not claim to fix it.
- Codex does not provide Olympus hard DENY or Aegis support; its capability contract continues to report both as `GAP`.

## Installation

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.4/install.ps1 | iex
```

## Verify installation

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.4/install.ps1'))) -Version 'v0.3.0-beta.4' -Target (Get-Location).Path -VerifyOnly
```

## v0.3.0-beta.3 critical fixes candidate

**Status: source candidate; this task creates no tag or release.**

- Add exact current-task ALLOW/NATIVE_ASK Authority Grants: native ASK scopes may reach OpenCode's permission layer without duplicate textual pre-authorization, while Olympus-owned protections and `/maintain`'s Olympus-only boundary remain enforced.
- Make the release installer accept Olympus SemVer prereleases, bind requested versions to resolved source identity, and qualify archive/version/roster/manifest end-to-end.
- Add read-only `-VerifyOnly` installation verification against the requested release's managed files, hashes, and roster; do not infer installed version from manifest text alone.

## Installation

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.3/install.ps1 | iex
```

## Verify installation

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.3/install.ps1'))) -Version 'v0.3.0-beta.3' -Target (Get-Location).Path -VerifyOnly
```

# 0.3.0-beta.1 (published prerelease)

**Status: published 2026-09-28 as prerelease tag `v0.3.0-beta.1`.**

## Highlights

- Add gated specialists: Argus for functional-defect diagnosis, Atlas for execution planning, Talos for security-defect diagnosis, and Thales (evolved from Sorin) for high-uncertainty technical diagnosis.
- Add Helios for explicitly requested, evidence-bounded optimization proposals that stop for user approval.
- Rename the hidden privileged maintenance executor to Aegis while preserving explicit `/maintain` entry; Kael cannot route to Aegis. Bootstrap migrates hash-verified owned legacy installs and rejects unowned or modified retired-agent files.
- Strengthen completion/result reconciliation and ownership: reconcile original work rather than blindly retrying, and collect and validate required terminal results before claiming completion.
- Add qualification fixtures and update bootstrap, Activity HUD, and maintainer documentation for the expanded roster and handoffs.

## Why beta

This prerelease is intended for real-project use before stable v0.3.0 so regressions and operational problems can be found and addressed.

## Known limitations

- The intermittent OpenCode result-correlation trigger tracked by Issue #1 remains unidentified and unfixed; Olympus mitigates unsafe retries by reconciling original work, but does not fix the runtime cause.
- Automated Aegis qualification covers bootstrap, routing boundaries, and synthetic handoff behavior; interactive `/maintain` result delivery is not simulated and remains a real-use validation target.
- OpenCode's visible maintenance-failure badge is outside Olympus control; whether an early badge persists after later result reconciliation is unproven.

## Requirements and install

- Windows, PowerShell 7, Git, an existing trusted Git project, and OpenCode V2 with GPT-6 Sol and GPT-6 Luna available (including the variants Olympus uses).
- Run the installer only from the root of a Git project you trust; review the installer first if preferred.

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.1/install.ps1 | iex
```

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
