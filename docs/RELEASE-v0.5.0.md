# OlympusAgents v0.5.0 — release candidate

**Pre-publication record; not proof of a GitHub Release.** This document tracks the bounded CLI/release-readiness evidence for [issue #64](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/64). Publishing a tag and GitHub Release remains a separate maintainer decision.

The checkout's installer default and release marker declare `v0.5.0`; the twelve legacy wrapper sources reference the same tag. This identifies a candidate source tree, not a published artifact or a universal CLI package.

## What the candidate delivers

- **Slices A/B:** lightweight Python 3.11+ source-checkout CLI for offline queries, canonical model-family/role edits, previews, validation and bounded source recovery; no model API calls are required.
- **Slices C1–C6, project:** managed installed-state preview/apply and recovery, read-only doctor, routing to existing native install/uninstall engines, and current/proposed assignments disclosed **before** project `config apply --execute` writes. Exact managed ownership, manifest, hash and drift guards remain in force.
- **Slice C7, global:** read-only `status`, `doctor` and `config apply --dry-run`; no global `--execute` or recovery. Global writes are deferred to [#122](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/122).
- **Operator UX:** icon-first, example-led [README](../README.md), two no-checkout Fast PowerShell entrypoints, interactive project/path/global and harness selection, the [workflow guide](WORKFLOWS.md) for detailed roles/modes, and copyable advanced CLI commands in [installation](INSTALLATION.md) and the [CLI quickstart](../specs/001-portable-olympus-cli/quickstart.md).

There are **11 canonical roles**: 11 OpenCode agents; Codex has Kael as root plus 10 specialists. Aegis and `/maintain` are retired. OpenCode V2 is the actively developed harness; Codex is frozen compatibility, not capability parity.

## Supported-operation matrix

| Operation | Windows | Linux | macOS |
| --- | --- | --- | --- |
| Python CLI queries and source configuration A/B | Qualified with focused checks | Qualified with hosted focused checks | Not verified |
| Managed **project** preview/apply/recovery C1–C6 | Focused native project apply/verify/drift rejection observed; isolated OpenCode V2 installation/discovery qualified with a private `--standalone` server | Focused CLI/synthetic-project evidence; native installer not qualified | Not verified |
| **Global** status/doctor/preview C7 | Read-only; native `VerifyOnly` requires PowerShell 7 and supported root | Read-only CLI path; native `VerifyOnly` unavailable/unqualified | Not verified |
| CLI install/uninstall routing | Windows/PowerShell 7 only; delegates to official engines | Not qualified | Not qualified |
| Global config execute/recovery | Unsupported; tracked by #122 | Unsupported | Unsupported |

The portable CLI launchers remain **source-checkout-bound** (`scripts/olympus.cmd` on Windows; `scripts/olympus` on Linux). No wheel, zipapp, standalone executable or automatic universal PATH installation is supplied. Install commands and versions are different from `olympus --version`: the latter only reports source-declared identity, not a published release.

## Known limits and operator cautions

- The public Fast Install/Uninstall commands require Windows, PowerShell 7, a trusted project Git root for project operations, and the relevant harness. They use a published `v0.4.11` bootstrap that selects a qualified release using `releases/latest`; that bootstrap tag is not the final installer version. GitHub's `immutable` field is not an independently verified signature.
- C5 project uninstall does **not** offer a dry-run; global `--harness all` uninstall is sequential, not atomic. The CLI rejects unsupported combinations instead of claiming a transaction.
- The model catalog was verified in the real Windows OpenCode profile for `openai/gpt-6.1-sol` and `openai/gpt-6-luna`. The isolated installer then received **only these prequalified model IDs** for its `models` query; provider credentials were not copied. This validates the model-ID gate, **not** successful provider authentication, paid inference or runtime session reload. OpenCode global and Codex global are different roots; installed assignment evidence can remain unknown.
- A Windows isolated project integration smoke passed official `VerifyOnly`, managed project commit/no-op and drift rejection. A later OpenCode v2.2.7 installer smoke also passed `CLEAN_RUNTIME`, `OLYMPUS_NATIVE_INSTALL` and `OA64_NATIVE_STANDALONE_QUALIFICATION` at exact source SHA `7b8a08b1ec88d8ccbff538d35f46b76336e99d1f`. An earlier run failed because the user's existing OpenCode shared server occupied port 28894; the corrected smoke used separate **private `--standalone` servers** and left the shared service untouched. This proves isolated native startup/install/discovery, **not shared-service parity**.
- No real user-global installation was modified. No paid model/provider execution, full production-runtime/provider workflow, macOS runtime, or broad Linux native-install qualification was performed.

## Acceptance reconciliation for the approved bounded scope

| Requirement | Candidate disposition |
| --- | --- |
| FR-008, FR-022–023 | Project pre-write assignment preview and canonical 11-role/offline query-edit contract delivered; focused tests and GitHub checks recorded in [PR #123](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/123). |
| FR-015–020, SC-006–007 | Managed **project** operations qualified to the stated matrix; global inspection is read-only. Global mutation/recovery is **not accepted** and remains in #122. Partial/unconfirmed results must never claim success. |
| FR-021, FR-024–026, SC-008 | Windows native routing and platform-specific limits documented; Python portability does not imply full native/runtime qualification. Source-bound launchers and prerequisites explicitly disclosed. |
| SC-009 | The operator has copyable Fast entrypoints and checkout-bound CLI examples; a universal standalone `olympus` executable is **not** claimed. |

## Evidence and publication gate

- Merged CLI baseline: `master` commit [`1f11640490eef7af05e10fecce8ee0eb6444f8cd`](https://github.com/Edulynch/OpenCode-OlympusAgents/commit/1f11640490eef7af05e10fecce8ee0eb6444f8cd) (PR #123).
- [Onboarding PR #124](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/124) and [icon-first README PR #125](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/125) are integrated into `master`; #125 had all three GitHub workflows green. PowerShell-only documentation contract tests were not separately run in the Linux editing environment.
- [Bounded native Windows project integration](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/64#issuecomment-6776438959): official `VerifyOnly` PASS; `OA64_POST_APPLY`, `OA64_DRIFT_REJECTION` and `OA64_PROJECT_INTEGRATION` PASS. This earlier evidence also records the initial shared-server port conflict; the later independent standalone smoke qualifies a different, explicitly limited runtime mode.
- [Release preparation PR #126](https://github.com/Edulynch/OpenCode-OlympusAgents/pull/126): all three GitHub checks **SUCCESS** on `7b8a08b1ec88d8ccbff538d35f46b76336e99d1f`; Windows `SOURCE_IDENTITY`, `OPENCODE_VERSION`, `HOST_MODEL_CATALOG`, `CLEAN_RUNTIME`, `OLYMPUS_NATIVE_INSTALL` and `OA64_NATIVE_STANDALONE_QUALIFICATION` **PASS** at that SHA. The isolated `models` response is host-prequalified, not proof of credentials inside the fixture or shared-service parity.
- **Final-SHA gate pending:** this documentation reconciliation changes the candidate SHA. The exact resulting head still requires a final focused version/release validation, Windows native standalone check and applicable CI before publication.

**Publication gate:** verify the exact final candidate SHA, run the targeted Windows PowerShell release/version contract and standalone native installer check, reconcile outstanding evidence in the reopened issue, and obtain explicit maintainer approval before merge, tag or GitHub Release. The shared-service port conflict is documented historical evidence, not a current standalone runtime failure. Do not silently expand supported platforms or global write capabilities to satisfy a broad checklist.
