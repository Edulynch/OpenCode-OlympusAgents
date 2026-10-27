# Release notes

## [Unreleased]

Changes after the latest published release go here.

## v0.4.12

### Highlights

- Fix optional `-ProjectPath` and `-Harness` validation in the public install and uninstall entrypoints when invoked through `Invoke-Expression` (`IEX`); interactive prompts and direct argument validation remain covered.
- Prepare exact-tag Fast Install and Fast Uninstall bootstrap URLs. The URL pins the bootstrap source only: each bootstrap consults `releases/latest` metadata to select an eligible published release and tag, so it does not pin the installed version.
- Preserve release-metadata rejection, tag and installer identity checks, project/global scope selection, Git worktree-root checks, ownership manifests, managed-file hash/drift protection, safe uninstall of unchanged manifest-owned resources, and read-only `VerifyOnly` behavior.
- Preserve the additive **Dual Harness Installer** for `-Harness opencode`, `-Harness codex`, and `-Harness all`, `installed_harnesses`, legacy OpenCode installations, PowerShell 5.1 / PowerShell 7 launch compatibility, user-owned file protection, and shared Olympus Harness Core. `VerifyOnly` remains read-only; this release does not claim full parity.

### Validation

- Local candidate checks exercise release identity, the twelve wrapper sources, public entrypoint argument flows, release-note and README contracts, tag-transition stability, and installer ownership/security regressions using isolated fixtures.
- Local candidate qualification is not acceptance of a published v0.4.12 source: it does not establish that public source exists, remote bytes or GitHub metadata, a published integrity signature, or native runtime behavior.

### Capability limits

- The installer is Windows-qualified only and requires PowerShell 7; project-scope operations require Git and a trusted Git worktree root. Static installation does not establish runtime discovery on every runtime or version.
- OpenCode V2 remains in **ACTIVE DEVELOPMENT**; Codex remains in **FROZEN COMPATIBILITY**. Codex retains `DENY = GAP`, `AEGIS = GAP`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; this release does not claim full parity.
- OpenCode Issue #1 (child-result correlation) and Issue #8 (authorization continuity after compaction) remain **OPEN/deferred**; no upstream or compaction fix is claimed. GitHub's `immutable` metadata is not independent cryptographic signature verification.

## Installation

See the [v0.4.12 installation guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.4.12/docs/INSTALLATION.md) for the Fast Install and Fast Uninstall entrypoints, scope and harness selection, requirements, and safety details.

## Verify installation

Read-only `VerifyOnly` instructions and release-source verification limits are documented in the [installation guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.4.12/docs/INSTALLATION.md#release-selection-identity-and-executable-source). Local candidate fixtures do not establish remote source availability or native runtime behavior.

## v0.4.11

### Highlights

- Correct GitHub `published_at` handling in both Fast bootstraps and the latest-release launcher: preserve UTC-aware `DateTime`/`DateTimeOffset` values and accept valid ISO 8601 timestamps ending in `Z` or an explicit numeric `±HH:MM` offset, comparing the represented instant consistently.
- Continue rejecting missing, incomplete, malformed, or timezone-naive timestamps, invalid or ambiguous local times, and timestamps more than five minutes in the future. Mutable, draft, prerelease, and otherwise invalid release metadata still fails closed.
- Keep `releases/latest` as metadata selection only. The selected tag supplies the launcher, installer, and source archive; GitHub's `immutable` flag is not independent signature or cryptographic source verification.
- Preserve managed-file ownership, hash/drift checks, user-file protections, and read-only `VerifyOnly`; no new harness or runtime capability is claimed.
- Preserve the existing additive **Dual Harness Installer** for `-Harness opencode`, `-Harness codex`, and `-Harness all`; retain `installed_harnesses` ownership, legacy OpenCode installations, user-owned file protections, the PowerShell 5.1 / PowerShell 7 launch path, and shared Olympus Harness Core. `VerifyOnly` remains read-only. This release does not claim full parity.

### Validation

- Local regression fixtures exercise typed UTC values, `Z` and numeric-offset timestamps across both Fast bootstraps and the latest-release launcher, and check that invalid metadata is rejected before download or execution.
- Local fixtures do not establish current remote GitHub metadata, remote source bytes, tag immutability, or native runtime behavior.

### Capability limits

- OpenCode Issue #1 (child-result correlation) remains **OPEN/deferred**; Olympus reconciliation guidance does not fix the upstream behavior.
- OpenCode Issue #8 (authorization continuity after compaction) remains **OPEN/deferred**. The earlier scoped same-session PASS did not test compaction; no fix is claimed.
- The Codex adapter remains `SUPPORTED_WITH_DECLARED_GAPS`: `DENY = GAP`, `AEGIS = GAP`, `QUESTION_CENTRALIZATION = PARTIAL`, `RESULT_RECONCILIATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; native ASK is `ADAPTABLE`. This release does not claim full parity.

## Installation

See the [v0.4.11 installation guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.4.11/docs/INSTALLATION.md) for the pinned Fast Install and Fast Uninstall entrypoints, requirements, scope/harness selection, and safety details.

## Verify installation

Read-only verification examples and release-verification limits are documented in the [installation guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.4.11/docs/INSTALLATION.md#release-selection-identity-and-executable-source). Local fixtures do not establish published remote metadata, source bytes, tag immutability, or runtime behavior.

## v0.4.10

### Highlights

- Prepare the Fast Install and Fast Uninstall entrypoints and the twelve legacy install/uninstall wrappers with a consistent `v0.4.10` candidate identity.
- Keep `releases/latest` as metadata discovery only. Reject missing, malformed, unpublished, mutable, or identity-mismatched releases before the selected release installer runs; executable acquisition remains pinned to a release tag, with no mutable-branch fallback.
- Preserve the existing additive **Dual Harness Installer**: `-Harness opencode`, `-Harness codex`, and `-Harness all`; `installed_harnesses`; legacy OpenCode installations; user-owned file protection; the PowerShell 5.1 / PowerShell 7 launch path; and shared Olympus Harness Core. `VerifyOnly` remains read-only. This release does not claim full parity.
- Keep OpenCode V2 in **ACTIVE DEVELOPMENT** and Codex in **FROZEN COMPATIBILITY**. No new Codex capabilities are added.

### Validation

- Focused local fixtures cover release identity, entrypoint routing, metadata rejection, and preservation of installation ownership and drift protections.
- These fixtures do not establish remote GitHub release metadata, remote source bytes, release immutability, or native runtime behavior.

### Capability limits

- OpenCode Issue #1 (child-result correlation) remains **OPEN/deferred**; Olympus reconciliation guidance does not fix the upstream behavior.
- OpenCode Issue #8 (authorization continuity after compaction) remains **OPEN/deferred**. The earlier scoped same-session PASS did not test compaction; no fix is claimed.
- The Codex adapter remains `SUPPORTED_WITH_DECLARED_GAPS`: `DENY = GAP`, `AEGIS = GAP`, `QUESTION_CENTRALIZATION = PARTIAL`, `RESULT_RECONCILIATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; native ASK is `ADAPTABLE`. No new Codex version or full parity is claimed.

## Installation

See the [v0.4.10 installation guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.4.10/docs/INSTALLATION.md) for the pinned Fast Install and Fast Uninstall entrypoints, requirements, scope/harness selection, and safety details.

## Verify installation

Read-only verification examples and release-verification limits are documented in the [installation guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.4.10/docs/INSTALLATION.md#release-selection-and-safety). Local fixture qualification is not evidence of published, immutable remote source.

## v0.4.9

### Highlights

- Promote the unified interactive and direct PowerShell installer and uninstaller as the primary interface, while retaining all twelve project/global and harness-specific compatibility entrypoints and the existing safety checks (PR #63).
- Preserve the existing additive **Dual Harness Installer**: `-Harness opencode`, `-Harness codex`, and `-Harness all`; `installed_harnesses`; legacy OpenCode installations; user-owned file protection; the PowerShell 5.1 / PowerShell 7 launch path; and shared Olympus Harness Core. `VerifyOnly` remains read-only. This release does not claim full parity.

### Validation

- Deterministic local fixtures cover installer UX, release contracts, and source identity; they do not establish native OpenCode or Codex behavior.
- Installation and `VerifyOnly` against the immutable remote source are separate release acceptance checks; local-source fixtures do not replace them.

### Capability limits

- OpenCode Issue #1 (child-result correlation) remains **OPEN/deferred**; Olympus reconciliation guidance does not fix the upstream behavior.
- OpenCode Issue #8 (authorization continuity after compaction) remains **OPEN/deferred**. The earlier scoped same-session PASS did not test compaction; no fix is claimed.
- Global OpenCode agent discovery is **SUPPORTED only for isolated Windows with OpenCode V2.0.26**, based on the recorded v0.4.6 global install, active loader, 12 Olympus agents plus two controls, and configuration-level Kael selection. No model-backed prompt or support for other versions or operating systems is established.
- The Codex adapter classification is `SUPPORTED_WITH_DECLARED_GAPS`, based on user-provided runtime evidence accepted as supplied. Separate historical root-only metrics do not establish Kovan→Nox runtime evidence or comparative results. Codex retains `DENY = GAP`, `AEGIS = GAP`, `QUESTION_CENTRALIZATION = PARTIAL`, `RESULT_RECONCILIATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; native ASK is `ADAPTABLE`.
- Codex `DENY = GAP` and `AEGIS = GAP`; `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; native ASK is adaptable. This release does not claim full parity.

## Installation

From a trusted checkout, use the unified entrypoints. For example, install both harnesses in the current project:

```powershell
pwsh -NoProfile -File ./install-olympus.ps1 -Project -Here -Harness all
```

The matching unified uninstaller is also available from the checkout:

```powershell
pwsh -NoProfile -File ./uninstall-olympus.ps1 -Project -Here -Harness all
```

## Verify installation

Read-only verification against a local checkout and the selected harness subset:

```powershell
pwsh -NoProfile -File ./install.ps1 -SourceRoot . -Version 'v0.4.9' -Target (Get-Location).Path -Scope project -Harness opencode -VerifyOnly
pwsh -NoProfile -File ./install.ps1 -SourceRoot . -Version 'v0.4.9' -Target (Get-Location).Path -Scope project -Harness codex -VerifyOnly
pwsh -NoProfile -File ./install.ps1 -SourceRoot . -Version 'v0.4.9' -Target (Get-Location).Path -Scope project -Harness all -VerifyOnly
```

## v0.4.8

### Highlights

- Refresh the README with an illustrated cover, clearer spacing, copyable commands, and a working Compatibility navigation anchor ([#43](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/adc4b35), [#44](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/6adcf81), [#45](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/1527fba)).
- Add a Windows FAST GitHub Actions workflow with pinned actions and meaning-based README contract checks ([#52](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/3056179)).
- Add contributor guidance, responsible security-reporting instructions, and weekly GitHub Actions dependency updates ([#53](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/8b63b3d)).
- Keep generated OpenCode Activity plugin bytes unchanged while making its source template parseable by CodeQL ([#54](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/23bbc96)).
- Require the global ownership manifest for read-only `VerifyOnly`; missing-manifest fixtures cover OpenCode and Codex and assert verification leaves files unchanged ([#55](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/fcae2bf)).
- Let FAST and FULL qualification create the approved temporary Python shim root when it is absent ([#56](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/88170ea)).
- Document risk-based selection of existing focused checks. Clarify that an original operation can be reissued only with evidence it did not execute, while a corrective retry requires a reconciled, consumed terminal result and a material failed acceptance gate; existing permission, ownership, scope, and retry limits still apply ([#57](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/392ebcf), [#58](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/835f107)).
- Clarify that the OpenCode authority prompts allow omission of `AUTHORITY_GRANT` only for an exact, confirmed-ALLOW assignment with ownership and in-scope evidence. NATIVE_ASK still requires an exact current-task grant; this does not bypass DENY or explicit constraints ([#59](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/79a9c55)).
- Clarify current harness support and the provenance and limits of historical runtime evidence ([#60](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/18b7669)).
- Preserve the existing additive **Dual Harness Installer**: `-Harness opencode`, `-Harness codex`, and `-Harness all`; `installed_harnesses`; legacy OpenCode installations; user-owned file protection; the PowerShell 5.1 / PowerShell 7 launch path; and shared Olympus Harness Core. `VerifyOnly` remains read-only. This release does not claim full parity.

### Validation

- Deterministic fixtures cover project-owned contracts; static qualification does not establish native OpenCode or Codex behavior.
- Installation and `VerifyOnly` against the immutable remote v0.4.8 tag are separate release acceptance gates; local-source fixtures do not replace them.

### Capability limits

- OpenCode Issue #1 (child-result correlation) remains **OPEN/deferred**; Olympus reconciliation guidance does not fix the upstream behavior.
- OpenCode Issue #8 (authorization continuity after compaction) remains **OPEN/deferred**. The earlier scoped same-session PASS did not test compaction; no fix is claimed.
- Global OpenCode agent discovery is **SUPPORTED only for isolated Windows with OpenCode V2.0.26**, based on the recorded v0.4.6 global install, active loader, 12 Olympus agents plus two controls, and configuration-level Kael selection. No model-backed prompt or support for other versions or operating systems is established.
- The Codex adapter classification is `SUPPORTED_WITH_DECLARED_GAPS`, based on user-provided runtime evidence accepted as supplied. Separate historical root-only metrics do not establish Kovan→Nox runtime evidence or comparative results. Codex retains `DENY = GAP`, `AEGIS = GAP`, `QUESTION_CENTRALIZATION = PARTIAL`, `RESULT_RECONCILIATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; native ASK is `ADAPTABLE`.
- Codex `DENY = GAP` and `AEGIS = GAP`; `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; native ASK is adaptable. This release does not claim full parity.

## Installation

From a trusted Git project root, use the immutable tag. OpenCode is the default; choose Codex or both explicitly:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.8/install.ps1 | iex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.8/install.ps1'))) -Harness codex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.8/install.ps1'))) -Harness all
```

For project/global scope and safe uninstall, use the tagged installer's `-Scope`, `-Harness`, and `-Uninstall` parameters.

## Verify installation

Read-only verification with the same immutable tag and exact installed harness subset:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.8/install.ps1'))) -Harness opencode -Version 'v0.4.8' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.8/install.ps1'))) -Harness codex -Version 'v0.4.8' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.8/install.ps1'))) -Harness all -Version 'v0.4.8' -Target (Get-Location).Path -VerifyOnly
```

## v0.4.7

### Highlights

- Deliver **TFR risk-based focused testing** as a canonical Olympus policy for both OpenCode and Codex: risk-based checks, conditional Nox/Vera, mandatory gates preserved, and original-result reconciliation. No additional review agent or testing tier.
- Qualify isolated Windows/OpenCode V2.0.26 global agent discovery using the real v0.4.6 installer: 12 Olympus agents and two controls, native loader active, and configuration-level Kael selection. No other runtime/version parity is implied.
- Fix OpenCode V2 startup documentation: select Kael in the native agent picker, or opt in to `default_agent`; do not use the unsupported top-level `--agent kael` flag.
- Document Codex 0.162.1 root `CODEX.md` instructions and the observed native `/subagents` UI, a scoped Veyra delegation, and original-result return; preserve the distinction from `/agents` task lists.
- Source all twelve public install/uninstall entrypoint scripts and their second-stage launcher from the **immutable v0.4.7 tag**, never from `master`. The launcher queries `releases/latest` for **metadata only**; any newer selected installer's executable code and archive are fetched from its own immutable release tag.
- Preserve the **Dual Harness Installer** as **additive** for `-Harness opencode`, `-Harness codex`, and `-Harness all`, including `installed_harnesses` manifests, `legacy OpenCode installations`, `user-owned` file protection, `VerifyOnly`, Windows PowerShell 5.1 / PowerShell 7 launchers and **Olympus Harness Core**.
- Clarify Issue #8's historical same-session continuation PASS (OpenCode v2.0.21) versus its later reopened compaction/authorization failure (v2.0.26), without altering historical evidence.

### Validation

- Existing TFR and completion-gate changes received focused deterministic qualification during development; these static checks do not prove every live runtime outcome.
- Historical Windows OpenCode global-loader evidence and Codex native delegation evidence predate this candidate; no new live prompt or permission-enforcement PASS is asserted.
- Install and VerifyOnly on the immutable remote tag are release acceptance gates, separate from local-source fixtures.

### Capability limits

- Issue #1 (upstream OpenCode child-result correlation) remains **OPEN/deferred**. Olympus reconciliation mitigates indeterminate outcomes but does not fix upstream.
- Issue #8 (authorization continuity after compaction) remains **OPEN/deferred** despite the earlier scoped same-session PASS; no new fix is claimed.
- Codex `DENY = GAP`, `AEGIS = GAP`, `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; this release **does not claim full parity**.
- A pinned `v0.4.7` public wrapper may choose a newer published installer using latest-release metadata. To fix the **installed** version instead, invoke that exact tag's root `install.ps1` directly.

## Installation

From a trusted Git project root, use the immutable tag. OpenCode is the default; choose Codex or both explicitly:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install.ps1 | iex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install.ps1'))) -Harness codex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install.ps1'))) -Harness all
```

For project/global scope and safe uninstall, use the tagged installer's `-Scope`, `-Harness`, and `-Uninstall` parameters.

## Verify installation

Read-only verification with the same immutable tag and exact installed harness subset:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install.ps1'))) -Harness opencode -Version 'v0.4.7' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install.ps1'))) -Harness codex -Version 'v0.4.7' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install.ps1'))) -Harness all -Version 'v0.4.7' -Target (Get-Location).Path -VerifyOnly
```

## v0.4.6

### Highlights

- Make the README installation-first: short sections, direct project/global install and uninstall commands, compact agent and compatibility tables, and minimal prose.
- Move the OpenCode worktree opt-in, manual setup, safety guarantees, and troubleshooting details to `docs/WORKTREES.md`.
- Correct the version history: the v0.4.5 notes incorrectly said agent permissions were unchanged. The worktree qualification hotfix added a **specific native edit DENY** for Kovan on `.opencode/scripts/worktree-setup.ps1`; this version preserves that protection.
- Keep the **Dual Harness Installer** additive for `-Harness opencode`, `-Harness codex`, and `-Harness all`. Its `installed_harnesses` inventory, legacy OpenCode installations, user-owned file protections, `VerifyOnly`, Windows PowerShell 5.1 / PowerShell 7 launchers, and Olympus Harness Core behavior remain unchanged. This patch updates documentation and the release identity only.

### Validation

- The v0.4.5 remote tagged archive passed a project `-Harness all` install and read-only `VerifyOnly` checks for OpenCode, Codex, and all; the user's fixture file hash was preserved.
- The v0.4.5 master FULL qualification passed 35/35 offline suites, including the OpenCode V2 `location[directory]` diagnostic contract and the Kovan worktree-helper DENY checks. No model request or OpenCode global runtime discovery is inferred from those qualifications.
- Worktree native smoke evidence preceded the later permission/qualification fixes; no additional model smoke is claimed by this documentation patch.

### Capability limits

- OpenCode global files install and verify, but global agent discovery remains **GAP/not runtime-proven** (Issue #7). Codex global discovery remains SUPPORTED on user-provided evidence, not a new smoke here.
- Codex `DENY = GAP`, `AEGIS = GAP`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; this release does not claim full parity. OpenCode has native DENY and the explicit `/maintain` entry, but the latter is not available through Codex.
- This patch corrects README usability and release-note accuracy; it does not extend runtime capabilities.

## Installation

From a trusted Git project root, use the immutable release installer. OpenCode is the direct installer's default; select Codex or both explicitly:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.6/install.ps1 | iex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.6/install.ps1'))) -Harness codex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.6/install.ps1'))) -Harness all
```

For project-local OpenCode Git worktrees, see the [opt-in guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.4.6/docs/WORKTREES.md).

## Verify installation

Read-only checks for the exact installed harness subset:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.6/install.ps1'))) -Harness opencode -Version 'v0.4.6' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.6/install.ps1'))) -Harness codex -Version 'v0.4.6' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.6/install.ps1'))) -Harness all -Version 'v0.4.6' -Target (Get-Location).Path -VerifyOnly
```

## v0.4.5

### Highlights

- Fix OpenCode V2 project-local activation in newly created Git worktrees with an opt-in `Project.Commands.start` command and a local, manifest-verified setup helper (Issue #27). Two isolated worktrees processed a read-only first prompt using Kael on OpenCode v2.0.26.
- Require the exact Olympus-owned resource inventory, 17 OpenCode files or 29 for an OpenCode + Codex installation, including SHA-256 validation and strict source/destination isolation. Reject missing, extra, and drifted resources before installation.
- Preserve user-owned files: reject competing `opencode.json` / `opencode.jsonc` configuration locations, and never adopt an existing file without a matching worktree-local ownership manifest, even if its content hash is identical. Fail safely rather than overwriting or silently changing the effective configuration.
- Keep startup opt-in and idempotent: re-running a verified setup reports no changes. Respect existing startup commands; no global installation or mutable download is required.
- Retain compatibility with legacy OpenCode installations and the additive Dual Harness Installer using explicit `-Harness opencode`, `-Harness codex`, and `-Harness all`. Existing `installed_harnesses`, PowerShell 5.1 / PowerShell 7 entrypoints, Olympus Harness Core, and read-only `VerifyOnly` behavior are unchanged.

### Validation

- Windows fixture qualification: 23 checks passed for worktree provisioning, manifests, hashes, idempotence, alternate configuration conflicts, and preservation of byte-identical preexisting files (including files tracked by Git).
- Release `-MockOpenCode`, Phase4C `-QualificationSlice Offline`, and installer compatibility qualifications passed during this change; PowerShell 5.1 and PowerShell 7 installer compatibility were exercised.
- Fix the noninteractive global OpenCode diagnostic (Issue #7) to query `agent.list` using V2 `location[directory]`. An offline FULL qualification checks the URI contract and refuses to classify missing agents as a proven runtime GAP without evidence that registration completed. Global runtime discovery remains unverified.
- Native worktree activation and a read-only first prompt through Kael were observed in two isolated checkouts on an earlier candidate commit. Later updates were limited to manifest and user-file protection; those model prompts were not repeated.
- Python 3.11 renderer checks now pass for all 30 managed outputs on Windows, alongside source/generated worktree helper parity. These checks do not establish universal runtime behavior.

### Capability limits

- Worktree provisioning is opt-in and qualified for OpenCode V2 on Windows. It addresses missing Olympus project resources in linked worktrees; it does not establish the cause of every possible prompt cancellation.
- OpenCode global runtime discovery remains a documented GAP. Codex `DENY = GAP`, `AEGIS = GAP`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; this release does not claim full parity between harnesses.
- Issue #8 (authorization continuity across compaction/resume) and Issue #28 (explicit Kael-to-Aegis maintenance delegation) remain independent. No privileged maintenance route or agent permissions change in this patch.

## Installation

From the root of a trusted Git project, use the immutable release tag. OpenCode project installation is the default; select the other harnesses explicitly:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.5/install.ps1 | iex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.5/install.ps1'))) -Harness codex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.5/install.ps1'))) -Harness all
```

The Git worktree startup hook is optional; see the README for the per-project OpenCode setup and precautions when another startup command already exists.

## Verify installation

These checks verify the exact managed installation subset without changing files:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.5/install.ps1'))) -Harness opencode -Version 'v0.4.5' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.5/install.ps1'))) -Harness codex -Version 'v0.4.5' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.5/install.ps1'))) -Harness all -Version 'v0.4.5' -Target (Get-Location).Path -VerifyOnly
```

## v0.4.4

### Highlights

- Freeze the existing Olympus architecture for this maintenance release: no new tiers or commands, and no changes to models, roles, authority policy, or concurrency limits.
- Publish version-neutral project/global install and uninstall entrypoints in the README. Install entrypoints resolve the latest published release and then invoke the installer from that exact immutable tag; installation remains explicit about harness and scope.
- Close the Command UX exploration: `/power`, `/plan`, `/performance`, and `/fast` are not Olympus commands. Natural language and existing routing remain primary; `/maintain` remains the explicit privileged entry.
- Warn during Codex install and `-VerifyOnly` when a non-empty project-root `AGENTS.override.md` or `AGENTS.md` takes precedence over generated `CODEX.md`. The warning is non-fatal and leaves user-owned instructions unchanged; an existing isolated regression is included in FULL.
- Correct stale roadmap model labels to GPT-6.1 Sol and refresh release/concurrency status; preserve Issue #7 as an observed global-discovery GAP with its root cause unproven.
- Strengthen the existing release/documentation qualification for all six version-neutral project/global install entrypoints, rejecting wrong-scope, directly pinned, root-installer, or foreign README install commands. Qualification profiles now report elapsed time and the five slowest checks; the existing R27 release assertion handles the source-mismatch diagnostic accurately.
- Make the existing PowerShell 5.1/7 compatibility check accept the line-wrapped missing-`pwsh` diagnostic while still requiring early failure before target creation.
- Document risk-proportionate validation guidance for documentation, localized changes, shared policy, installer/release, and runtime-dependent changes without changing FAST, FULL, or RUNTIME behavior.
- Retain the Dual Harness Installer with explicit `-Harness opencode`, `-Harness codex`, and `-Harness all` selections. Installation is additive; `installed_harnesses` records manifest ownership; legacy OpenCode installations remain upgradeable. The public installer launches from PowerShell 5.1 or PowerShell 7, with PowerShell 7 running bootstrap. Olympus Harness Core remains the shared source; `VerifyOnly` is read-only and user-owned files are preserved.

### Capability limits

- OpenCode global runtime discovery remains **GAP**: isolated evidence observed the expected global Olympus roster missing, but does not establish the root cause. Issue #7 remains OPEN. Codex global runtime discovery is **SUPPORTED** on user-provided PASS evidence; it was not rerun here. Static global installation does not prove runtime discovery.
- OpenCode V2 Issue #1 remains OPEN upstream (`No tool output found`). Olympus reconciles original results where possible and forbids blind retry; it does not fix upstream result correlation.
- Codex `DENY = GAP`, `AEGIS = GAP`, `RESULT_RECONCILIATION = PARTIAL`, `QUESTION_CENTRALIZATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; Codex ASK is adaptable, not identical to OpenCode ASK. This release does not claim full parity.
- Codex root-instruction and specialist-visibility follow-up #23 remains OPEN. The precedence warning detects only non-empty project-root `AGENTS.override.md` / `AGENTS.md`; it does not prove which instructions or specialist activity are effective in every session. Codex has no Olympus Aegis or `/maintain` equivalent.
- Optional Codex auto-review evaluation in Issue #13 remains deferred; this release does not enable it or change permission behavior.
- Global installation is Windows-qualified. No Unix global install/runtime qualification is claimed.

## Installation

Open PowerShell in the root of the trusted Git project. These commands use the same exact v0.4.4 tag for installer source and version identity:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.4/install.ps1 | iex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.4/install.ps1'))) -Harness codex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.4/install.ps1'))) -Harness all
```

The default is project-local OpenCode; use `-Scope global` explicitly for global installation. Global OpenCode installation does not imply runtime discovery support.

## Verify installation

Each command verifies only the selected managed project-local harness subset and is read-only:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.4/install.ps1'))) -Harness opencode -Version 'v0.4.4' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.4/install.ps1'))) -Harness codex -Version 'v0.4.4' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.4/install.ps1'))) -Harness all -Version 'v0.4.4' -Target (Get-Location).Path -VerifyOnly
```

## v0.4.3

### Highlights

- Add a contributor-facing qualification entry point with the `FAST`, `FULL`, and `RUNTIME` profiles. FAST and FULL remain offline and deterministic; RUNTIME is separate and contains only supported runtime boundaries. Authority Runtime uses an isolated, hermetic fixture environment ([qualification details](docs/DEVELOPMENT.md#unified-contributor-profiles-issue-11)).
- Phase 11 Integrated Routing Qualification is **SHIPPED** with no pending native cases; Case I remains guided PARTIAL and Argus/Thales same-session follow-up runtime coverage remains NOT_EXERCISED ([closure evidence](tests/phase11-integrated-routing/baseline.md)).
- Phase 12 cross-harness evaluation is **CLOSED**: 3 matched pairs / 6 verified executions, with PASS limited to tested invariants; capability gaps remain and no total parity or winner is claimed ([results](docs/history/PHASE12-CROSS-HARNESS-RESULTS.md)).
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
