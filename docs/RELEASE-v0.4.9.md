# OlympusAgents v0.4.9

## Highlights

- Make the unified interactive and direct PowerShell installer and uninstaller the primary interface (PR #63).
- Keep the twelve project/global and harness-specific compatibility entrypoints available with their existing behavior and installer safety checks.
- Preserve the additive Dual Harness Installer and its `-Harness opencode`, `-Harness codex`, and `-Harness all` options, `installed_harnesses` ownership, legacy OpenCode installations, user-owned file protection, PowerShell 5.1 / PowerShell 7 launch path, and shared Olympus Harness Core. `VerifyOnly` remains read-only; this release does not claim full parity.

## Validation and limits

- The release gates exercise local source identity, installer UX, and release contracts. These checks do not establish native OpenCode or Codex runtime behavior.
- Installation and `VerifyOnly` against the immutable remote source are separate release acceptance checks; local-source fixtures do not replace them.
- OpenCode Issue #1 (child-result correlation) remains **OPEN/deferred**. Issue #8 (authorization continuity after compaction) also remains **OPEN/deferred**; no fix is claimed.
- Global OpenCode agent discovery remains supported only for isolated Windows with OpenCode V2.0.26, based on the recorded v0.4.6 evidence. Other versions, platforms, and model-backed prompts are not established.
- Codex retains `DENY = GAP`, `AEGIS = GAP`, `QUESTION_CENTRALIZATION = PARTIAL`, `RESULT_RECONCILIATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL/BASIC`; native ASK is adaptable. No full parity is claimed.

## Installation

From a trusted checkout, use the unified installer. This example installs both harnesses in the current project:

```powershell
pwsh -NoProfile -File ./install-olympus.ps1 -Project -Here -Harness all
```

The corresponding unified uninstaller is:

```powershell
pwsh -NoProfile -File ./uninstall-olympus.ps1 -Project -Here -Harness all
```

## Verify installation

`VerifyOnly` is read-only and can verify a selected harness subset using the local checkout:

```powershell
pwsh -NoProfile -File ./install.ps1 -SourceRoot . -Version 'v0.4.9' -Target (Get-Location).Path -Scope project -Harness opencode -VerifyOnly
pwsh -NoProfile -File ./install.ps1 -SourceRoot . -Version 'v0.4.9' -Target (Get-Location).Path -Scope project -Harness codex -VerifyOnly
pwsh -NoProfile -File ./install.ps1 -SourceRoot . -Version 'v0.4.9' -Target (Get-Location).Path -Scope project -Harness all -VerifyOnly
```
