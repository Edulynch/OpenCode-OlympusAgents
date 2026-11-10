<div align="center">

# 🏛️ Olympus Agents

<img src="docs/assets/olympus-cover.png" alt="Olympus Agents team on Mount Olympus" width="100%">

**Your AI development team, ready for OpenCode V2.**

*Bring the idea. Kael coordinates the specialists. You stay in control.*

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) [![Windows qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md) [![MIT](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

[Install](#fast-install) · [First task](#your-first-task) · [Meet the team](#meet-the-team) · [CLI](#portable-cli) · [Uninstall](#fast-uninstall) · [Documentation](#documentation)

</div>

Olympus is an AI coding team with **OpenCode V2 in ACTIVE DEVELOPMENT** and **Codex in FROZEN COMPATIBILITY**.

## Why Olympus?

- **One point of contact:** tell Kael what you need; Kael involves specialists only when useful.
- **Made for real projects:** explore, design, implement, test and review with the same coordinated team.
- **You retain control:** project permissions, trusted sources and required checks remain in effect.
- **No extra AI subscription included:** bring your own OpenCode setup and access to the configured models.

## Requirements

- Windows; this installer is currently Windows-qualified.
- PowerShell 7 (`pwsh`) available on `PATH`. Windows PowerShell 5.1 may start a command only when PowerShell 7 is also installed.
- Git for project-scope operations; select the root of a trusted Git worktree.
- Install OpenCode V2 and/or Codex CLI for the harnesses you intend to use.

## Fast Install

**One copy-and-paste command. No Olympus checkout needed.** Run this in PowerShell from your trusted Git project's root, or choose another project/global scope when prompted. The installer asks for the scope and harness (OpenCode, Codex, or both) when they are not supplied.

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.11/install-olympus.ps1')))
```

## Fast Uninstall

The matching command asks what to remove and protects user-owned files:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.11/uninstall-olympus.ps1')))
```

For unattended commands, project paths (including spaces), harness selection, verification, or troubleshooting, see the [installation guide](docs/INSTALLATION.md). It documents `-Project -Here`, `-ProjectPath` and `-Global` with the exact supported PowerShell syntax.

<details>
<summary>How the published bootstrap selects a release</summary>

These commands use the versioned `v0.4.11` bootstrap from the published, immutable [release](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.4.11). It pins the bootstrap source, not the installed version. Each bootstrap and its release launcher consults `releases/latest` metadata to select an eligible published release tag. Release metadata checks fail closed when invalid. The launcher resolves `releases/latest` again for the installer and source archive and checks installer identity before execution. GitHub's immutability flag is not independent cryptographic signature verification. See [installation, parameters, safety, and troubleshooting](docs/INSTALLATION.md).

</details>

## Your First Task

After installing, open OpenCode in your project and describe the outcome in plain language:

> "Create a Flutter habit tracker with local storage and a simple first screen."

> "Find why this API fails, fix the cause and run the relevant tests."

> "FAST: review these independent modules, fix confirmed bugs and summarize the checks."

## Meet the Team

**Kael is your single coordinator.** Olympus currently has **11 canonical roles** (OpenCode: 11 agents; Codex: Kael as root plus 10 specialists). These are the roles defined by Olympus Core, not a promise that every harness has the same runtime capabilities.

<details>
<summary>Meet all 11 roles</summary>

| Role | Specialty |
| --- | --- |
| **Kael** · The Master | Coordinates work and reconciles results |
| **Veyra** · The Explorer | Finds relevant evidence |
| **Orin** · The Architect | Designs bounded solutions |
| **Atlas** · The Planner | Orders complex execution |
| **Kovan** · The Coder | Implements changes |
| **Argus** · The Bug Hunter | Diagnoses defects |
| **Nox** · The Tester | Verifies behavior |
| **Vera** · The Judge | Reviews work independently |
| **Talos** · The Sentinel | Assesses security issues |
| **Thales** · The Sage | Helps with difficult uncertainty |
| **Helios** · The Optimizer | Evaluates performance improvements |

</details>

## Portable CLI

Olympus also includes a lightweight Python 3.11+ CLI for inspecting model choices, editing canonical configuration, diagnosing installations and safely applying managed changes to **existing project installations**. On Windows, start it from a trusted Olympus source checkout using `scripts/olympus.cmd`; Linux has the checkout-bound `scripts/olympus` launcher. There is **no separately installed universal `olympus` command** or blanket Linux/macOS native-installer guarantee.

Global configuration status, doctor and preview are **read-only**; global execute/recovery is deferred. See the [CLI quickstart](specs/001-portable-olympus-cli/quickstart.md) and the [v0.5.0 candidate support matrix](docs/RELEASE-v0.5.0.md).

## 📌 Project status

- **OpenCode V2: ACTIVE DEVELOPMENT.**
- **Codex: FROZEN COMPATIBILITY.** Existing support and safe uninstall behavior remain; no new Codex capabilities or parity are implied.

## 🧭 NORMAL vs FAST

**NORMAL (default):** Kael chooses useful, bounded parallel work for the task.

**FAST (explicit):** when work is safe to split, it uses up to four agents, keeps required checks, and does not parallelize dependent tasks.

### Optional OpenCode task modifiers (experimental; opt-in)

> **Experimental — Kael/OpenCode V2 only.** These are task-scoped **prompt markers**, not OpenCode slash commands, CLI commands, or built-in runtime flags. A small controlled A/B test confirmed task completion but **did not establish causal improvements** from the modifiers ([evidence in #92](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/92#issuecomment-6440098753)).

Append any combination of the exact standalone lines `long-mode`, `fast-mode`, and
`surgical-mode` at the end of the task prompt. They apply only to that task; ordinary
mentions, quotations, code, and documentation do not activate them. `long-mode`
reduces optional questions without implying consent; `fast-mode` reuses the existing
FAST policy; `surgical-mode` avoids unrelated edits while retaining needed tests.
Without a marker, existing NORMAL/explicit FAST behavior is unchanged. These are
Kael prompt instructions, not a parser or a runtime guarantee.

Olympus coordinates and reconciles work; OpenCode retains tools, sessions, processes,
and permissions. Kael uses only specialists that add value. Capability Preflight and
risk-based focused testing reuse existing contracts. Product decisions and acceptance
criteria belong to the project owner. Current product direction prioritizes Flutter
on Android and 2D games with Flame while retaining web support; Olympus does not require
the entire tools suite to be installed.

## 🛠️ Contextual maintenance

Kael is the sole orchestrator for external projects and OlympusAgents. Maintenance is a task context, not a separate role or command: Kael uses the normal specialists and proportionate validation, with Olympus source writes scoped to the identified OlympusAgents repository. OpenCode supports this contextual workflow; Codex currently declares it a capability gap. The optional native `/goal` UX is user-selected where available and is not required or silently invoked.

## Documentation

- [Installation](docs/INSTALLATION.md) — prerequisites, entrypoints, parameters, safety, and troubleshooting.
- [Documentation index](docs/README.md) — canonical sources, current guides, and historical records.
- [Harness capabilities](docs/HARNESS-CAPABILITIES.md) · [Codex compatibility](docs/CODEX-COMPATIBILITY.md)
- [Development](docs/DEVELOPMENT.md) · [Roadmap](docs/ROADMAP.md) · [Worktrees](docs/WORKTREES.md)
- [Releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases) · [Changelog](CHANGELOG.md) · [License](LICENSE)

Olympus is an independent orchestration system, not a fork. The specialized-team idea was informed in part by [codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).
