<div align="center">

# 🏛️ Olympus Agents

<img src="docs/assets/olympus-cover.png" alt="Olympus Agents team on Mount Olympus" width="100%">

**Your AI coding team. One prompt. Eleven roles. You stay in control.**

🌐 **English · [Español](README.ES.md)**

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) [![Windows qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md) [![Linux (WSL 2)](https://img.shields.io/badge/Linux-WSL%202-2563eb?style=flat-square)](docs/INSTALLATION.md#linux-sh-entrypoint) [![OpenCode v2.4.1](https://img.shields.io/badge/OpenCode-v2.4.1-2563eb?style=flat-square)](https://github.com/anomalyco/opencode/releases/tag/v2.4.1) [![MIT](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

**[🎯 Try it](#your-first-task) · [⚡ Install](#fast-install) · [🧩 Team](#the-team) · [🧭 Commands](#task-parallelism) · [🛠️ CLI](#portable-cli) · [📚 Guides](#guides)**

</div>

<a id="your-first-task"></a>

## 🎯 Your First Task

After [installing Olympus](#fast-install), open OpenCode in your project and tell Kael what you want to do:

> 📱 **Build:** Create a Flutter habit tracker with local storage and a simple first screen.

> 🐛 **Fix:** Find why this API fails, fix the cause, and run the relevant tests.

**🧭 Start with Kael.** It brings in specialists when they help. You don't have to pick an agent for each step.

Kael carries applicable validation evidence forward across implementation, pull requests, CI, and release handoffs, so checks need not be repeated just because the stage changed. If an acceptance criterion is still unsupported, it asks for the smallest needed check; required reviews and release gates still apply.

Need parallel work or a performance review? See [OpenCode commands](#task-parallelism).

## Fast Install

### Windows

**Requirements:** PowerShell 7 (`pwsh`), OpenCode V2, and Python 3.11+.

```powershell
& ([scriptblock]::Create((irm 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1')))
```

✅ **After installing:** open a new PowerShell 7 window and run `olympus version`.

### Linux

**Requirements:** `curl`, `sh`, OpenCode V2, and Python 3.11+.

The [latest stable release](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) includes the Linux entrypoint:

```sh
curl -fsSL https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.sh | sh
```

Validated on Ubuntu 24.04 with WSL 2. [Linux setup and verification →](docs/INSTALLATION.md#linux-sh-entrypoint)

🔄 **Already installed?** Run `olympus update`, then `olympus doctor --scope global`.

🛡️ **Scope:** installation is **global and OpenCode-only** for your user. It selects a published, immutable release and sets Kael as the global default. [Installation safeguards →](docs/INSTALLATION.md)

## Install a specific version

Choose a published stable tag and replace `vX.Y.Z` with that exact tag.

**Windows:**

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/vX.Y.Z/install.ps1')))
```

**Linux:** use the same selected stable tag when it supports Linux installation:

```sh
curl -fsSL https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.sh | sh -s -- vX.Y.Z
```

<a id="the-team"></a>

## 🧩 Meet the team

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

## 🧭 OpenCode Commands

⚡ **`/olympus.ultra <prompt>`** — uses independent work up to the configured prompt ceiling (1–8). Two useful tasks mean at most two workers, even if six slots are available.

> `/olympus.ultra Review these independent modules and summarize the checks.`

📈 **`/olympus.performance <prompt>`** — starts with a baseline and proposes an improvement. Kael asks before applying it unless that specific change is already approved. Afterward, it compares results and checks for regressions.

> `/olympus.performance Evaluate how to reduce this endpoint's latency without changing its behavior.`

💬 **Both need a prompt.** There are no bare `/ultra` or `/performance` aliases. Blank-argument usage is a prompt-level guard, not deterministic native argument validation. [Workflow details →](docs/WORKFLOWS.md#native-task-commands)

<a id="portable-cli"></a>

## 🛠️ Olympus CLI

| Command | What it does |
| --- | --- |
| `olympus --help` | See common commands and examples. |
| `olympus update` | Check for a newer stable release. |
| `olympus agents list` | See agent models and reasoning settings. |
| `olympus config set-max-parallel 6` | Save the global limit for active direct subagents per root session. |
| `olympus doctor --scope global` | Check the global installation without changing it. |

🔍 **Need detail?** Try `olympus update --help` for command help or add `--verbose` to see what ran. Use `--json` where supported for scripts. [All CLI commands and advanced options →](docs/INSTALLATION.md#olympus-cli)

## Fast Uninstall

```powershell
olympus uninstall
```

🗑️ Removes unchanged Olympus-managed resources and its Windows PATH entry while preserving unrelated files and later default-agent choices. [Removal details →](docs/INSTALLATION.md)

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

## Mentions

- [XERJ Corpus Hub](https://hub.xerj.org/corpus/edulynch--opencode-olympusagents)

## ⚠️ Use and responsibility

Agents can modify files and run commands depending on the permissions you grant. Start on a test branch and review changes before merging.

Olympus is provided “as is”, without warranty. See the [MIT License](LICENSE) for the full terms, including the limitation of liability.
