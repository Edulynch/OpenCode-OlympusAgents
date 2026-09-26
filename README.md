<div align="center">

# 🏛️ OpenCode Olympus Agents

### Give OpenCode a team.

**Install once. Open OpenCode. Start building.**

[![Release v0.1.2](https://img.shields.io/badge/release-v0.1.2-7c3aed?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.1.2)
[![OpenCode V2](https://img.shields.io/badge/OpenCode-V2-f97316?style=flat-square)](https://opencode.ai/docs/)
[![Windows Qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.1.2)
[![MIT License](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

<p><a href="#-install">Install</a> · <a href="#-start-building">Start Building</a> · <a href="#-the-team">Agents</a> · <a href="#-normal-vs-fast">NORMAL vs FAST</a> · <a href="#-live-activity">Live Activity</a> · <a href="#-update">Update</a> · <a href="#-documentation">Docs</a></p>

</div>

## 🚀 Install

### Requirements

- Windows with PowerShell 7 installed
- Git and an existing Git project
- OpenCode V2 with GPT-6 Sol and GPT-6 Luna available (including the variants Olympus uses)

Open PowerShell **in the root folder of the Git project** where you want to use Olympus. Run:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.1.2/install.ps1 | iex
```

This installs Olympus into that project, not globally. Only run downloaded scripts in projects you trust; [review the installer](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.1.2/install.ps1) first if you prefer.

## 💬 Start Building

In the same project folder, run:

```powershell
opencode
```

Then describe what you want to build in plain language. For example:

> Add a search bar to my app. Make it keyboard-accessible and run the relevant tests.

Kael coordinates the team as needed: research, implementation, testing, and review. You don't have to choose agents yourself.

## 🧭 The Team

| Agent | What they do |
|---|---|
| 👑 **Kael** | Understands your request and coordinates the work. |
| 🔭 **Veyra** | Researches the project and gathers context. |
| 📐 **Orin** | Plans tricky changes. |
| 🔨 **Kovan** | Writes code. |
| 👁️ **Nox** | Runs checks and tests. |
| ⚖️ **Vera** | Reviews the result. |
| 🧭 **Sorin** | Helps diagnose difficult problems when needed. |

OpenCode is the runtime. Olympus is the orchestration and decision layer that helps this team work together.

## 🔧 Maintenance

For advanced repository administration, use `/maintain <task>` (for example, release preparation, Git maintenance, Olympus configuration maintenance, or repository-level administration). Maintenance is separate from the normal seven-agent team: Kael cannot invoke it automatically. Ordinary feature development does not require `/maintain`.

## ⚡ NORMAL vs FAST

**NORMAL** is the default: Olympus uses only as much parallel work as is useful for your task.

If speed matters, explicitly ask for **FAST** in your request (for example, “FAST: check these independent modules and fix the issues”). Olympus can split independent work across up to four agents at a time when it is safe to do so. FAST does not skip checks or make dependent tasks run in parallel.

## 👀 Live Activity

When agents are working, OpenCode can show who is active and what they're doing:

```text
⚡ Olympus · 3 active
● Veyra   Researching repository
● Orin    Designing boundaries
● Kovan   Implementing feature
```

The activity display is read-only and disappears when no agents are working.

## 🛡️ Trust

Olympus treats an installed project as trusted. Kovan and Nox can run commands from that project while implementing and validating work. Only install Olympus into repositories you trust; see [Development & qualification](docs/DEVELOPMENT.md) for details.

## 🔄 Update

Olympus is installed per project. To reinstall **v0.1.2** in the same project, run the [Install](#-install) command again from its Git root. Olympus preserves unrelated project work and refuses to overwrite changed files it manages. This command is pinned to v0.1.2; it will not automatically install future releases.

## 🆘 Troubleshooting

- **`opencode` command unavailable?** Install and configure [OpenCode](https://opencode.ai/docs/) first.
- **`OLYMPUS_REQUIRES_POWERSHELL_7`?** Install PowerShell 7 and run the same install command again.
- **Not a valid Git project root?** Open PowerShell in the root folder of your Git project and run the installer again.
- **`MANAGED_FILE_DRIFT`?** Olympus found a manually changed file it manages and refused to overwrite it silently. See [Development & qualification](docs/DEVELOPMENT.md) for recovery details.

## 📚 Documentation

- [OpenCode documentation](https://opencode.ai/docs/) — install and learn OpenCode.
- [Development & qualification](docs/DEVELOPMENT.md) — maintainer docs, bootstrap internals, qualification, and release workflow.
- [Roadmap](docs/ROADMAP.md) — planned agent evolution and future qualification work.
- [Olympus v0.1.2 release](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.1.2) and [changelog](CHANGELOG.md) — release information.
- [License](LICENSE) — MIT.

Olympus is an independent OpenCode V2 project, not a fork. The idea of a specialized agent team was informed in part by [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).
