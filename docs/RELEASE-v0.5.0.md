# OlympusAgents v0.5.0 — release candidate

**Status: NOT PUBLISHED.** This is the bounded CLI/release-readiness record for [issue #64](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/64). Do not interpret this document as evidence of a `v0.5.0` tag, released installer or universal CLI packaging. The checkout's current installer/version declaration remains `v0.4.12` until a separately approved release transition.

## What the candidate delivers

- **Slices A/B:** lightweight Python 3.11+ source-checkout CLI for offline queries, canonical model-family/role edits, previews, validation and bounded source recovery; no model API calls are required.
- **Slices C1–C6, project:** managed installed-state preview/apply and recovery, read-only doctor, routing to existing native install/uninstall engines, and current/proposed assignments disclosed **before** project `config apply --execute` writes. Exact managed ownership, manifest, hash and drift guards remain in force.
- **Slice C7, global:** read-only `status`, `doctor` and `config apply --dry-run`; no global `--execute` or recovery. Global writes are deferred to [#122](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/122).
- **Operator UX:** two no-checkout Fast PowerShell entrypoints in the [README](../README.md), interactive project/path/global and harness selection, and advanced copyable CLI commands in the [installation guide](INSTALLATION.md) and [CLI quickstart](../specs/001-portable-olympus-cli/quickstart.md).

There are **11 canonical roles**: 11 OpenCode agents; Codex has Kael as root plus 10 specialists. Aegis and `/maintain` are retired. OpenCode V2 is the actively developed harness; Codex is frozen compatibility, not capability parity.

## Supported-operation matrix

| Operation | Windows | Linux | macOS |
| --- | --- | --- | --- |
| Python CLI queries and source configuration A/B | Qualified with focused checks | Qualified with hosted focused checks | Not verified |
| Managed **project** preview/apply/recovery C1–C6 | Focused native project apply/verify/drift rejection observed | Focused CLI/synthetic-project evidence; native installer not qualified | Not verified |
| **Global** status/doctor/preview C7 | Read-only; native `VerifyOnly` requires PowerShell 7 and supported root | Read-only CLI path; native `VerifyOnly` unavailable/unqualified | Not verified |
| CLI install/uninstall routing | Windows/PowerShell 7 only; delegates to official engines | Not qualified | Not qualified |
| Global config execute/recovery | Unsupported; tracked by #122 | Unsupported | Unsupported |

The portable CLI launchers remain **source-checkout-bound** (`scripts/olympus.cmd` on Windows; `scripts/olympus` on Linux). No wheel, zipapp, standalone executable or automatic universal PATH installation is supplied. Install commands and versions are different from `olympus --version`: the latter only reports source-declared identity, not a published release.

## Known limits and operator cautions

- The public Fast Install/Uninstall commands require Windows, PowerShell 7, a trusted project Git root for project operations, and the relevant harness. They use a published `v0.4.11` bootstrap that selects a qualified release using `releases/latest`; that bootstrap tag is not the final installer version. GitHub's `immutable` field is not an independently verified signature.
- C5 project uninstall does **not** offer a dry-run; global `--harness all` uninstall is sequential, not atomic. The CLI rejects unsupported combinations instead of claiming a transaction.
- Installed model/provider authentication, model availability and runtime session reload are not established by static/CLI checks. OpenCode global and Codex global are different roots; installed assignment evidence can remain unknown.
- A Windows isolated project integration smoke passed official `VerifyOnly`, managed project commit/no-op and drift rejection. **The initial installer command did not pass native OpenCode runtime validation**: OpenCode v2.2.7 failed `debug config` with a transient port-28894 startup error. No listener owner/root cause was established, so do not advertise that install-time runtime validation as PASS.
- No real user-global installation was modified. No paid model/provider execution, FULL/RUNTIME loop, macOS runtime, or broad Linux native-install qualification was performed.

## Acceptance reconciliation for the approved bounded scope

| Requirement | Candidate disposition |
| --- | --- |
| FR-008, FR-022–023 | Project pre-write assignment preview and canonical 11-role/offline query-edit contract delivered; focused tests and GitHub checks recorded in [PR #123](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/123). |
| FR-015–020, SC-006–007 | Managed **project** operations qualified to the stated matrix; global inspection is read-only. Global mutation/recovery is **not accepted** and remains in #122. Partial/unconfirmed results must never claim success. |
| FR-021, FR-024–026, SC-008 | Windows native routing and platform-specific limits documented; Python portability does not imply full native/runtime qualification. Source-bound launchers and prerequisites explicitly disclosed. |
| SC-009 | The operator has copyable Fast entrypoints and checkout-bound CLI examples; a universal standalone `olympus` executable is **not** claimed. |

## Evidence and publication gate

- Merged CLI baseline: `master` commit [`1f11640490eef7af05e10fecce8ee0eb6444f8cd`](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/1f11640490eef7af05e10fecce8ee0eb6444f8cd) (PR #123).
- [Bounded native Windows project integration](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/64#issuecomment-6776438959): official `VerifyOnly` PASS; `OA64_POST_APPLY`, `OA64_DRIFT_REJECTION` and `OA64_PROJECT_INTEGRATION` PASS. The same evidence records the separate OpenCode port-related native-validation failure.
- Existing FAST/Security/native-permission CI on reviewed PR #123 passed; no unrelated full-suite repetition is required for this documentation-only candidate.

**Release gate still pending:** review and merge these docs against a current `master`, reconcile the unexpected GitHub closed state of #64 with the outstanding release gate, verify the final candidate's exact release/version identity and required CI, and obtain explicit maintainer approval before creating any `v0.5.0` tag or GitHub Release. Do not silently expand supported platforms or global write capabilities to satisfy a broad checklist.
