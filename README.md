<div align="center">

# 🏛️ Olympus Agents

<img src="docs/assets/olympus-cover.png" alt="Olympus Agents team with Kael coordinating coding specialists on Mount Olympus" width="100%">

**Your AI coding team for OpenCode V2 and Codex.**

*One orchestrator. Specialized agents. Work you can verify.*

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) [![OpenCode V2](https://img.shields.io/badge/OpenCode-V2-f97316?style=flat-square)](https://opencode.ai/v2/docs/) [![Windows qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md) [![MIT](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

[⚡ Fast Install](#fast-install) · [🧹 Fast Uninstall](#fast-uninstall) · [🧭 How it works](#-how-olympus-works) · [📖 Documentation](#-documentation)

</div>

## Requirements

- 🪟 **Windows** — the installer is currently Windows-qualified; Linux and macOS are not qualified.
- ⚡ **PowerShell 7** — `pwsh` on `PATH`. Windows PowerShell 5.1 can start the entrypoint only when PowerShell 7 is also installed.
- 🌱 **Git** — required for project scope; start from the root of a trusted Git worktree.
- 🤖 **Runtime** — OpenCode V2, Codex CLI, or both, depending on the harness you want.

## Fast Install

⚡ **One command. No Olympus checkout required.** Choose the project/global scope and harness when prompted.

The URLs below start from the versioned `v0.4.10` bootstrap. That bootstrap queries GitHub's `releases/latest` metadata to select an eligible published release and tag; `v0.4.10` is not a preselected final installer version. The release metadata checks fail closed when their requirements are not met.

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.10/install-olympus.ps1 | iex
```

## Fast Uninstall

🧹 **One matching command.** Removes only eligible, unchanged Olympus-managed resources; unrelated user files remain protected.

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.10/uninstall-olympus.ps1 | iex
```

🛡️ The bootstrap selects a tag for its release launcher; that launcher resolves `releases/latest` again for the installer and source archive and checks installer identity before execution. GitHub's immutability flag is not independent cryptographic signature verification. See [installation, parameters, safety, and troubleshooting](docs/INSTALLATION.md).

## 🧭 How Olympus works

- **🧭 Kael coordinates** — scopes work, selects specialists and reconciles results.
- **🛠️ Specialists contribute** — implement, investigate and review within their assigned responsibilities.
- **🧪 Evidence matters** — focused checks and independent review support completion claims; offline tests do not prove live runtime behavior.

## 🤖 Project status

- **OpenCode V2: ACTIVE DEVELOPMENT.** The primary target for ongoing improvements.
- **Codex: FROZEN COMPATIBILITY.** Existing support and safe uninstall behavior remain; new capability parity is not implied.

## ⚡ NORMAL vs FAST

- **NORMAL (default):** Kael chooses useful, bounded parallel work for the task.
- **FAST (explicit):** when work is safe to split, it uses up to four agents, keeps required checks, and does not parallelize dependent tasks.

## 🛡️ Maintenance (OpenCode)

Ordinary Git work, including releases, stays with Kael in the normal project workflow. Only an explicit `/maintain` invokes hidden Aegis; Kael never escalates there automatically. Codex has no equivalent Aegis capability.

## 📖 Documentation

- **🚀 Getting started:** [Installation](docs/INSTALLATION.md) — parameters, versions, safety, troubleshooting.
- **🤖 Compatibility:** [Harness capabilities](docs/HARNESS-CAPABILITIES.md) · [Codex compatibility](docs/CODEX-COMPATIBILITY.md)
- **🛠️ Contributors:** [Development](docs/DEVELOPMENT.md) · [Roadmap](docs/ROADMAP.md) · [Worktrees](docs/WORKTREES.md)
- **📦 Releases:** [Releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases) · [Changelog](CHANGELOG.md) · [License](LICENSE)

Olympus is an independent orchestration system, not a fork. The specialized-team idea was informed in part by [codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).
