<div align="center">

# 🏛️ Olympus Agents

**Your AI coding team. One prompt. Eleven roles. You stay in control.**

🌐 **English · [Español](README.ES.md)**

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) [![Windows qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md) [![MIT](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

**[🎯 Try it](#your-first-task) · [⚡ Install](#fast-install) · [👥 Team](#the-team) · [🧭 Commands](#task-parallelism) · [🛠️ CLI](#portable-cli) · [📚 Guides](#guides)**

</div>

<a id="your-first-task"></a>

## 🎯 Your First Task

Open OpenCode in your project and tell Kael what you want to do:

> 📱 **Build:** Create a Flutter habit tracker with local storage and a simple first screen.

> 🐛 **Fix:** Find why this API fails, fix the cause, and run the relevant tests.

> ⚡ **Ultra:** `/olympus.ultra Review these independent modules, fix confirmed bugs, and summarize the checks.`

> 📈 **Performance:** `/olympus.performance Reduce the latency of this endpoint while preserving its behavior.`

**🧭 Start with Kael.** It brings in specialists when they help. You don't have to pick an agent for each step.

## Fast Install

🪟 **Requirements:** Windows · PowerShell 7 (`pwsh`) · OpenCode V2 · Python 3.11+ for the CLI.

```powershell
& ([scriptblock]::Create((irm 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1')))
```

✅ **After installing:** open a new PowerShell 7 window and run `olympus version`.

🔄 **Already installed?** Run `olympus update`, then `olympus doctor --scope global`.

🛡️ **Scope:** installation is **global and OpenCode-only**. It selects a published, immutable release, sets Kael as the global default, and adds the per-user `olympus` command to PATH. [Installation safeguards →](docs/INSTALLATION.md)

## Install a specific version

To install `v0.11.0` instead of the latest release:

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.11.0/install.ps1')))
```

<a id="the-team"></a>

## 👥 Meet the team

| Agent | When it helps |
| --- | --- |
| 🧭 **Kael** | Coordinates your task and brings together the results. |
| 🔎 **Veyra** | Finds relevant code, documentation, and evidence. |
| 🏗️ **Orin** | Designs interfaces and weighs architecture choices. |
| 🗺️ **Atlas** | Turns an agreed change into an ordered plan. |
| 💻 **Kovan** | Implements changes within the agreed scope. |
| 🐛 **Argus** | Diagnoses bugs when the cause isn't obvious. |
| 🧪 **Nox** | Runs checks and verifies what actually happened. |
| ⚖️ **Vera** | Reviews changes independently for errors and regressions. |
| 🛡️ **Talos** | Diagnoses security defects and assesses impact. |
| 🧠 **Thales** | Helps untangle difficult technical failures. |
| 🚀 **Helios** | Weighs performance improvements against their cost and risk. |

🧠 **Default models:** Sol roles use GPT‑6.2 Sol. Luna roles and your explicit model choices are unchanged. [Model configuration →](docs/INSTALLATION.md#olympus-cli)

<a id="task-parallelism"></a>

## 🧭 Task Parallelism

⚡ **`/olympus.ultra <prompt>`** — uses independent work up to the configured prompt ceiling (1–8). Two useful tasks mean at most two workers, even if six slots are available.

📈 **`/olympus.performance <prompt>`** — starts with a baseline and proposes an improvement. Kael asks before applying it unless that specific change is already approved. Afterward, it compares results and checks for regressions.

💬 **Both need a prompt.** There are no bare `/ultra` or `/performance` aliases. Blank-argument usage is a prompt-level guard, not deterministic native argument validation. [Workflow details →](docs/WORKFLOWS.md#native-task-commands)

<a id="portable-cli"></a>

## 🛠️ Olympus CLI

| Try this in PowerShell 7 | What it does |
| --- | --- |
| `olympus agents list` | See agent models and reasoning settings. |
| `olympus config set-max-parallel 6` | Save the global limit for active direct subagents per root session. |
| `olympus doctor --scope global` | Check the global installation without changing it. |

🔍 **Need detail?** Add `--verbose`. Use `--json` where supported for scripts. [All CLI commands and advanced options →](docs/INSTALLATION.md#olympus-cli)

## Fast Uninstall

```powershell
olympus uninstall
```

🗑️ Removes unchanged Olympus-managed resources and its PATH entry while preserving unrelated files and later default-agent choices. [Removal details →](docs/INSTALLATION.md)

<a id="guides"></a>

## 📚 Guides

| | Start here |
| --- | --- |
| ⚡ **Install / remove** | [Scopes, direct parameters and troubleshooting](docs/INSTALLATION.md) |
| 🎯 **Use Olympus** | [Team, task commands and prompt examples](docs/WORKFLOWS.md) |
| 🛠️ **CLI** | [Commands, model configuration, and diagnostics](docs/INSTALLATION.md#olympus-cli) |
| 🧩 **OpenCode support** | [Current capability contract](docs/HARNESS-CAPABILITIES.md) · [Installation and safety](docs/INSTALLATION.md) |
| 🛡️ **Security** | [Report a security issue](SECURITY.md) |
| 🧑‍💻 **Contribute** | [Development](docs/DEVELOPMENT.md) · [Roadmap](docs/ROADMAP.md) · [Worktrees](docs/WORKTREES.md) |
| 📦 **Releases** | [Latest stable release](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) · [All releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases) · [Changelog](CHANGELOG.md) |
| 📖 **All docs** | [Documentation index](docs/README.md) · [License](LICENSE) |

<sub>Olympus is an independent orchestration system, not a fork. The specialized-team idea was informed in part by [codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).</sub>
