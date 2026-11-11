## v0.6.0

🏛️ **One prompt. Eleven roles. One `olympus` CLI.**

### Highlights

- **System command:** invoke `olympus` from any directory after installing the Windows user-PATH launcher.
- **Self-update:** `olympus update` and `upgrade` select stable immutable releases with exact source identity checks.
- **Agent configuration:** `olympus agents list`, `olympus <agent> set-model provider/model-id`, and `set-effort`, with persistent overrides.
- **Models.dev:** known models receive offline capability validation; well-formed unlisted identifiers are allowed with an explicit compatibility warning, without checking provider access.
- **Diagnostics:** `olympus config list` displays effective values and absolute paths; `olympus doctor` checks configuration statically.
- **Safe updates:** modified managed agents are listed by name and require explicit confirmation before replacement.

### Qualification

- [PR #130](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/130): required CI workflows passed, including FAST / Windows, native V2 permission API, and security/documentation.
- Focused CLI tests and an isolated Windows fresh-shell smoke: PASS, including controlled stable-update and uninstall preservation.
- Real user installations, model-inference requests, and local FULL/RUNTIME were not exercised.

### Support boundaries

Windows and PowerShell 7 are the qualified installer platform; the global CLI uses Python 3.11+ internally. OpenCode V2 is primary, while Codex remains frozen compatibility. The bundled Models.dev snapshot does not verify model entitlement or capability for unlisted identifiers. GitHub's immutable flag is not independent signature verification.

## Installation

Use **Fast Install** or **Fast Uninstall** with the exact-tag commands in the [v0.6.0 installation guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.6.0/docs/INSTALLATION.md). The `olympus` command becomes available from a new shell after installation.

## Verify installation

Use `olympus version`, `olympus config list`, and `olympus doctor`. For read-only `VerifyOnly` and safe source selection, consult [release selection, identity and executable source](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.6.0/docs/INSTALLATION.md#release-selection-identity-and-executable-source).
