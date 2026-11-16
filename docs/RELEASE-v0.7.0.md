## v0.7.0

> Historical release record: statements below describe v0.7.0 only, not current
> support or routes. Olympus currently supports OpenCode only; public
> install/update/uninstall is global/OpenCode-only.

🏛️ **Safer configuration changes, clearer diagnostics, and bounded OpenCode lifecycle handling.**

### Highlights

- `olympus config apply` offers an explicit preview before `--execute`; global execution is OpenCode-only. `olympus config recover` reconciles only the matching pending operation.
- `olympus doctor` stays read-only and reports actionable installation/configuration guidance without probing provider access.
- OpenCode child-result handling accounts for background work that can make an initial report partial. Optional MCP servers no longer block host use when absent.
- The two public Fast entrypoints remain pinned to the published `v0.6.1` bootstrap. It selects an eligible published stable release from metadata; the selected tag supplies the launcher, installer, and archive. Bootstrap identity and product identity are distinct.

### Qualification and evidence boundaries

- Static fixtures, CI, and documentation checks cover their stated contracts only. They do not establish public-tag installation, global runtime discovery, provider inference, or a general OpenCode compatibility guarantee.
- The dated lifecycle runtime evidence in the [harness guide](HARNESSES.md#opencode-23-subagent-compatibility) used OpenCode CLI/API v2.3.0 and source checkout `d154a4ecb7d40b7e5a246316997c5bf75d4c6638`. One controlled concurrent child case completed successfully; a separate requested exit-7 stimulus returned 1, and a later exit-code calibration was not a second concurrency run. The record does not qualify forced cancellation/crash, HUD visibility, Windows shell handoff, or native permission UI/decision.
- Codex remains frozen compatibility: `DENY = GAP`, `CONTEXTUAL_OLYMPUS_MAINTENANCE = GAP`, `QUESTION_CENTRALIZATION = PARTIAL`, `RESULT_RECONCILIATION = PARTIAL`, and `ACTIVITY_VISIBILITY = PARTIAL`. No full parity is claimed.
- GitHub's immutable-release metadata and exact tag identity are not independent cryptographic signature verification.

## Installation

Use **Fast Install** or **Fast Uninstall** from the [v0.7.0 installation guide](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.7.0/docs/INSTALLATION.md), including supported modes and safety constraints.

## Verify installation

See [release selection, identity and executable source](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.7.0/docs/INSTALLATION.md#release-selection-identity-and-executable-source) for read-only `VerifyOnly` and static validation guidance. `olympus doctor` is read-only; it does not prove native runtime discovery or provider access.
