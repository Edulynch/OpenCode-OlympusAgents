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
