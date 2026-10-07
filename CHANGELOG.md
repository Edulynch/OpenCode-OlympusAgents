# Release notes

## [Unreleased]

Changes after v0.4.3 go here.

The Issue #10 OPEN references in the versioned v0.4.0 and v0.4.2 notes below record status at those releases; they are historical.

## v0.4.3

### Highlights

- Add a contributor-facing qualification entry point with the `FAST`, `FULL`, and `RUNTIME` profiles. FAST and FULL remain offline and deterministic; RUNTIME is separate and contains only supported runtime boundaries. Authority Runtime uses an isolated, hermetic fixture environment ([qualification details](docs/DEVELOPMENT.md#unified-contributor-profiles-issue-11)).
- Phase 11 Integrated Routing Qualification is **SHIPPED** with no pending native cases; Case I remains guided PARTIAL and Argus/Thales same-session follow-up runtime coverage remains NOT_EXERCISED ([closure evidence](tests/phase11-integrated-routing/baseline.md)).
- Phase 12 cross-harness evaluation is **CLOSED**: 3 matched pairs / 6 verified executions, with PASS limited to tested invariants; capability gaps remain and no total parity or winner is claimed ([results](docs/PHASE12-CROSS-HARNESS-RESULTS.md)).
- [Issue #10 is CLOSED](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/10) after the maintenance-specific exact-field handoff fix was integrated ([commit](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/a83847b84d6603aed144f5a8ce4b77de8a48fe32)); its Runtime fidelity PASS predates integration, and no post-integration smoke was repeated.
- Retain the Dual Harness Installer with explicit `-Harness opencode`, `-Harness codex`, and `-Harness all` entrypoints. Installation is additive; `installed_harnesses` records manifest ownership, and existing legacy OpenCode installations remain upgradeable. Project scope remains the default, and installation and uninstall are available for both project and global scope.
- Project uninstall uses the ownership manifest and SHA-256 hashes, refuses managed-file drift, and preserves the other harness when uninstalling only one harness. Global uninstall removes only manifest/hash-verified resources.
- Keep the Windows-qualified global static-install foundation. The installer can be launched from PowerShell 5.1 or PowerShell 7; PowerShell 7 selection is deterministic when PATH contains multiple `pwsh` executables.
- Retain Olympus Harness Core as the shared source for OpenCode and Codex outputs; `VerifyOnly` checks the selected managed harness subset read-only, and user-owned files are preserved.

### Capability limits

- OpenCode V2 Issue #1 remains OPEN upstream (`No tool output found`); Olympus reconciles original results where possible and forbids blind retry, but does not fix upstream result correlation.
- Issue #7 remains OPEN because OpenCode global runtime discovery remains a known GAP.
- Global static installation is supported for both harnesses, but global runtime discovery is **GAP** for OpenCode and **SUPPORTED** for Codex (based on supplied runtime evidence). OpenCode global installation must not be treated as runtime-qualified.
- Codex `DENY = GAP`, `AEGIS = GAP`, `RESULT_RECONCILIATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; Codex ASK is adaptable, not identical to OpenCode ASK. This release does not claim full parity.
- Global installation is Windows-qualified. No Unix global install/runtime qualification is claimed.

## Installation

Choose the immutable v0.4.3 release source from the root of the trusted Git project:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.3/install.ps1 | iex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.3/install.ps1'))) -Harness codex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.3/install.ps1'))) -Harness all
```

The default is project-local OpenCode; use `-Scope global` explicitly for global installation. Global static installation does not imply OpenCode global runtime discovery support.

## Verify installation

Each command verifies only the selected managed project-local harness subset and is read-only:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.3/install.ps1'))) -Harness opencode -Version 'v0.4.3' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.3/install.ps1'))) -Harness codex -Version 'v0.4.3' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.3/install.ps1'))) -Harness all -Version 'v0.4.3' -Target (Get-Location).Path -VerifyOnly
```

## v0.4.2

This corrective release makes release-facing documentation remain truthful when
the exact validated `master` commit becomes an immutable tag. Product/version
content is kept separate from per-release execution state. Release validation
history is recorded below; neither validation tag is represented as a published
GitHub Release.

### Highlights

- Carry forward the Olympus Harness Core and its deterministic OpenCode and Codex adapters.
- Derive full agent display identities from one Core source and map Sol roles to GPT-6.1 Sol while Luna roles remain on GPT-6 Luna.
- Retain the Dual Harness Installer for OpenCode and Codex. `-Harness opencode`, `-Harness codex`, and `-Harness all` are additive; `installed_harnesses` records manifest ownership, VerifyOnly is read-only, and user-owned files are preserved. Existing legacy OpenCode installations remain upgradeable.
- Keep the public Windows installer launchable from PowerShell 5.1 and PowerShell 7; PowerShell 7 runs the bootstrap.
- Carry forward the Windows-qualified global static-install foundation with manifests, hash-checked update, safe uninstall of owned files only, and non-destructive project-to-global migration; project scope remains the default.
- Replace transient pre-tag claims with tag-transition-stable product and version documentation; add semantic regression coverage for the same bytes before and after tagging.
- Record the historical v0.4.0 and v0.4.1 validation-tag failures without representing either as a published GitHub Release.

### Capability limits

- Global static installation is supported for both harnesses, but global runtime discovery is **GAP** for OpenCode and **SUPPORTED** for Codex (based on supplied runtime evidence). OpenCode global installation must not be treated as runtime-qualified.
- Codex `DENY = GAP`, `AEGIS = GAP`, `RESULT_RECONCILIATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; Codex ASK is adaptable, not identical to OpenCode ASK. This release does not claim full parity.
- OpenCode V2 Issue #1 remains OPEN upstream (`No tool output found`); Olympus reconciles original results where possible and forbids blind retry, but does not fix upstream result correlation.
- Issue #7 remains OPEN because OpenCode global runtime discovery is a known GAP. Issue #10 remains OPEN because child-to-parent summaries may omit exact structured fields.
- Global installation is Windows-qualified. No Unix global install/runtime qualification is claimed.

## Installation

Choose a published version from [GitHub Releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases), then run the matching immutable-tag command from the root of the trusted Git project:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.2/install.ps1 | iex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.2/install.ps1'))) -Harness codex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.2/install.ps1'))) -Harness all
```

The default is project-local OpenCode. Global commands are separate; their static install success does not imply OpenCode global runtime discovery support.

## Verify installation

Each command verifies only the selected managed project-local harness subset and is read-only:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.2/install.ps1'))) -Harness opencode -Version 'v0.4.2' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.2/install.ps1'))) -Harness codex -Version 'v0.4.2' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.2/install.ps1'))) -Harness all -Version 'v0.4.2' -Target (Get-Location).Path -VerifyOnly
```

## v0.4.1

**History: v0.4.1 is an immutable validation tag. Release validation failed because release-facing documentation still described that version as upcoming and advised against publishing it. No GitHub Release v0.4.1 was created.**

The corrective release line records the documentation and qualification fixes in v0.4.2.

## v0.4.0

**History: v0.4.0 is an immutable validation tag on the integrated `master` foundation. Release validation failed because release-facing documentation still named beta.5 as the active baseline and contradicted the established integration/tag state. No GitHub Release v0.4.0 was created.**

### Highlights

- Add Olympus Harness Core as the canonical role, policy, model-intent, display-identity, orchestration, and capability source; deterministically render the OpenCode and Codex adapters.
- Derive full agent display identities from one Core source and migrate Sol roles to GPT-6.1 Sol while Luna roles remain on GPT-6 Luna.
- Retain the Dual Harness Installer for OpenCode and Codex. `-Harness opencode`, `-Harness codex`, and `-Harness all` are additive; `installed_harnesses` records manifest ownership, VerifyOnly is read-only, and user-owned files are preserved. Existing legacy OpenCode installations remain upgradeable.
- Keep the public Windows installer launchable from PowerShell 5.1 and PowerShell 7; PowerShell 7 runs the bootstrap.
- Add a Windows-qualified global static-install foundation with manifests, hash-checked update, safe uninstall of owned files only, and non-destructive project-to-global migration; project scope remains the default.
- Close Issue #8 after the supplied same-child runtime continuation PASS retained Aegis identity, marker, task scope, `MAINTENANCE_AUTH`, and `AEGIS_SCOPE`.

### Capability limits

- Global static installation is supported for both harnesses, but global runtime discovery is **GAP** for OpenCode and **SUPPORTED** for Codex (based on supplied runtime evidence). OpenCode global installation must not be treated as runtime-qualified.
- Codex `DENY = GAP`, `AEGIS = GAP`, `RESULT_RECONCILIATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; Codex ASK is adaptable, not identical to OpenCode ASK. This release does not claim full parity.
- OpenCode V2 Issue #1 remains OPEN upstream (`No tool output found`); Olympus seeks and consumes the original result when recoverable, reports `COMPLETION_UNCONFIRMED` when it is not, and forbids blind retry, but does not fix upstream result correlation.
- Issue #10 remains OPEN: child-to-parent summaries may omit exact structured fields. Existing completion gates and no-blind-retry semantics remain in place; the observed loss reduces orchestration fidelity and may require blocking/recovery when exact fields are needed.
- Global installation is Windows-qualified. No Unix global install/runtime qualification is claimed.

## Installation

Open PowerShell in the root of the trusted Git project and use the exact immutable v0.4.0 tag:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1 | iex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Harness codex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Harness all
```

The default is project-local OpenCode. Global commands are separate; their static install success does not imply OpenCode global runtime discovery support:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Scope global -Harness opencode
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Scope global -Harness codex
```

## Verify installation

Each command verifies only the selected managed project-local harness subset and is read-only:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Harness opencode -Version 'v0.4.0' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Harness codex -Version 'v0.4.0' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Harness all -Version 'v0.4.0' -Target (Get-Location).Path -VerifyOnly
```

Global `VerifyOnly` checks installed global manifests and managed hashes; it does not prove runtime discovery:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Scope global -Harness opencode -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Scope global -Harness codex -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.0/install.ps1'))) -Scope global -Harness all -VerifyOnly
```

## v0.3.0-beta.5

### Highlights

- Add the project-local Dual Harness Installer for OpenCode and Codex, both rendered from Olympus Harness Core.
- OpenCode remains the backwards-compatible default when `-Harness` is omitted; select `-Harness opencode`, `-Harness codex`, or `-Harness all` explicitly as needed.
- Harness installation is additive. The `installed_harnesses` ownership-manifest field records selected harnesses, and `-VerifyOnly` checks the selected harness or subset without modifying files.
- Preserve differing user-owned files and refuse conflicting destinations or drifted managed files instead of silently overwriting them.
- Support Codex-only installation without creating `.opencode/**`; safely upgrade legacy OpenCode installations and add either harness to the other.
- Keep Windows PowerShell 5.1 launcher and PowerShell 7 compatibility within the existing qualification coverage.

### Harness capabilities

OpenCode and Codex both use Olympus Harness Core, but their capabilities are not identical. Codex `DENY = GAP`, `AEGIS = GAP`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; this release does not claim full parity.

## Installation

### OpenCode (default and backwards-compatible)

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.5/install.ps1 | iex
```

This is the normal installer command and defaults to `-Harness opencode`.

### Codex

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.5/install.ps1'))) -Harness codex
```

### OpenCode + Codex

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.5/install.ps1'))) -Harness all
```

## Verify installation

Each command verifies the exact same immutable beta.5 source and only the selected harness subset:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.5/install.ps1'))) -Harness opencode -Version 'v0.3.0-beta.5' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.5/install.ps1'))) -Harness codex -Version 'v0.3.0-beta.5' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.3.0-beta.5/install.ps1'))) -Harness all -Version 'v0.3.0-beta.5' -Target (Get-Location).Path -VerifyOnly
```

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
