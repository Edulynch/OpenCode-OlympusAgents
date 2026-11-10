<div align="center">

# 🏛️ Olympus Agents

<img src="docs/assets/olympus-cover.png" alt="Olympus Agents team on Mount Olympus" width="100%">

**Your AI coding team. One prompt. Eleven roles. You stay in control.**

*Tell Kael what you want to build. Olympus brings in the right specialists.*

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) [![Windows qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md) [![MIT](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

**[⚡ Install](#fast-install) · [🎯 Try it](#your-first-task) · [🧭 Workflows](#normal-vs-fast) · [🛠️ CLI](#portable-cli) · [🗑️ Uninstall](#fast-uninstall) · [📚 Guides](#guides)**

</div>

<a id="your-first-task"></a>

## 🎯 Your First Task

After installation, open OpenCode in your project and try a prompt:

> 📱 **Build:** Create a Flutter habit tracker with local storage and a simple first screen.

> 🐛 **Fix:** Find why this API fails, fix the cause, and run the relevant tests.

> ⚡ **FAST:** Review these independent modules, fix confirmed bugs, and summarize the checks.

**🧭 Kael coordinates.** Ten specialists help with discovery, architecture, coding, testing, review, and security. [Meet the team →](docs/WORKFLOWS.md#the-team)

## Requirements

🪟 **Windows** · **PowerShell 7 (`pwsh`)** · **OpenCode V2 and/or Codex CLI** · **Git** for project installation.

## Fast Install

⚡ **One command. No Olympus checkout.** PowerShell asks **where** (current project, another project, global) and **which harness** (OpenCode, Codex, both).

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.11/install-olympus.ps1')))
```

🔒 The versioned `v0.4.11` bootstrap comes from a [published, immutable release](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.4.11). `releases/latest` metadata selects the published release tag; release metadata checks fail closed. GitHub's immutability flag is not independent cryptographic signature verification. [installation, parameters, safety, and troubleshooting](docs/INSTALLATION.md).

<a id="normal-vs-fast"></a>

## 🧭 NORMAL vs FAST

**NORMAL (default):** Kael uses parallel work only when useful for the task.

**FAST (explicit):** Up to four agents; keeps required checks and does not parallelize dependent tasks.

**Optional OpenCode task modifiers:** `long-mode` · `fast-mode` · `surgical-mode` are task-scoped prompt markers, not a parser or a runtime guarantee. [Examples and rules →](docs/WORKFLOWS.md#optional-opencode-task-modifiers)

<a id="portable-cli"></a>

## 🛠️ Portable CLI

🐍 **Python 3.11+**, from a trusted Olympus source checkout (not a system-wide installed command):

```text
python -B -m olympus models list
python -B -m olympus config check
python -B -m olympus config apply --scope project --target /path/to/project --harness opencode --dry-run
```

🛡️ Global inspection/preview is **read-only**; global execute/recovery is unsupported. [More CLI examples →](specs/001-portable-olympus-cli/quickstart.md) · [Platform support →](docs/RELEASE-v0.5.0.md#supported-operation-matrix)

## Fast Uninstall

🗑️ **One command.** Choose the installed scope and harness; managed-file safeguards remain active.

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.11/uninstall-olympus.ps1')))
```

<a id="guides"></a>

## 📚 Guides

| | Start here |
| --- | --- |
| ⚡ **Install / remove** | [Scopes, direct parameters and troubleshooting](docs/INSTALLATION.md) |
| 🎯 **Use Olympus** | [Team, NORMAL/FAST, prompt examples and task modifiers](docs/WORKFLOWS.md) |
| 🛠️ **CLI** | [Commands and examples](specs/001-portable-olympus-cli/quickstart.md) |
| 🧩 **Compatibility** | [Harness capabilities](docs/HARNESS-CAPABILITIES.md) · [Codex limitations](docs/CODEX-COMPATIBILITY.md) |
| 🧑‍💻 **Contribute** | [Development](docs/DEVELOPMENT.md) · [Roadmap](docs/ROADMAP.md) · [Worktrees](docs/WORKTREES.md) |
| 📦 **Releases** | [Published releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases) · [Changelog](CHANGELOG.md) · [v0.5.0 candidate](docs/RELEASE-v0.5.0.md) |
| 📖 **All docs** | [Documentation index](docs/README.md) · [License](LICENSE) |

**🚦 Support:** OpenCode V2 is in **ACTIVE DEVELOPMENT**; Codex is in **FROZEN COMPATIBILITY**. Windows is the qualified installer platform; other native installers and complete runtime parity are not claimed. [Details →](docs/RELEASE-v0.5.0.md#supported-operation-matrix)

<sub>Olympus is an independent orchestration system, not a fork. The specialized-team idea was informed in part by [codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).</sub>
