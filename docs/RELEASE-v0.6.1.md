## v0.6.1

🏛️ **OlympusAgents maintenance: don't confuse runtime discovery with installation integrity.**

### Highlights

- **Installer reliability:** once static validation, managed-file ownership and write verification succeed, a failed `opencode debug config` no longer aborts a project installation.
- **Honest diagnostics:** failed or inconsistent OpenCode runtime agent discovery produces `OLYMPUS_RUNTIME_VALIDATION_WARNING` and recommends `olympus doctor`.
- **Safety preserved:** malformed source data, managed-file drift and user-owned destination conflicts still fail closed. `VerifyOnly` remains read-only.
- **CLI availability:** the installer can proceed to register the `olympus` command after a runtime-only validation failure.

### Qualification

- [PR #133](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/133) passed required CI, including targeted Windows P1–P8 postinstall tests and isolated smoke; security and native permission workflows also passed.
- Qualification used isolated internal destinations and a simulated OpenCode failure. The public v0.6.1 entrypoint with real OpenCode is **not** established by those fixtures; run a public-tag smoke after publication.
- No provider access checks, inferencing, general FULL/RUNTIME suites or mutations of users' real OpenCode profiles were performed.

### Boundaries

The global `external_directory` ASK/DENY guard is **unchanged**. An existing OpenCode global `opencode.json` without a safe explicit fallback can still block global installation. Do not overwrite a user's config or create a second config format to bypass the guard. Windows, PowerShell 7 and internal Python 3.11+ remain the qualified environment. Codex remains frozen compatibility.

## Installation

Use **Fast Install** or **Fast Uninstall** with the exact-tag commands and prerequisites in the [v0.6.1 installation guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.6.1/docs/INSTALLATION.md).

## Verify installation

Read [release selection, identity and executable source](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.6.1/docs/INSTALLATION.md#release-selection-identity-and-executable-source) for read-only `VerifyOnly`. Use `olympus version`, `olympus config list` and `olympus doctor` for static checks. A runtime validation warning is not proof that all agents are discoverable.
