<div align="center">

# 🏛️ OpenCode Olympus Agents

### Give OpenCode a team.

**Install once. Open OpenCode. Start building.**

[![Release v0.1.0](https://img.shields.io/badge/release-v0.1.0-7c3aed?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.1.0)
[![OpenCode V2](https://img.shields.io/badge/OpenCode-V2-f97316?style=flat-square)](https://opencode.ai/docs/)
[![Windows Qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.1.0)
[![MIT License](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

<p><a href="#-install">Install</a> · <a href="#-start-building">Start Building</a> · <a href="#-the-team">Agents</a> · <a href="#-normal-vs-fast">NORMAL vs FAST</a> · <a href="#-live-activity">Live Activity</a> · <a href="#-update">Update</a> · <a href="#-documentation">Docs</a></p>

</div>

## 🚀 Install

### Requirements

- Windows and PowerShell 7 (`pwsh`)
- Git and an existing Git project
- OpenCode V2 with access to `openai/gpt-6-sol` and `openai/gpt-6-luna` (including the configured variants)

Open PowerShell **in the root folder of the Git project** where you want to use Olympus. Run:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.1.0/install.ps1 | iex
```

This installs Olympus into that project, not globally. Only run downloaded scripts in projects you trust; [review the installer](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/v0.1.0/install.ps1) first if you prefer.

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

## 🔄 Update

Olympus is installed per project. To reinstall **v0.1.0** in the same project, run the [Install](#-install) command again from its Git root. The installer checks for local changes to files it manages and will not silently overwrite them. This command is pinned to v0.1.0; it will not automatically install future releases.

## 📚 Documentation

- [OpenCode documentation](https://opencode.ai/docs/) — install and learn OpenCode.
- [Olympus v0.1.0 release](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.1.0) and [changelog](CHANGELOG.md) — release information.
- [License](LICENSE) — MIT.

Olympus is an independent OpenCode V2 project, not a fork. The idea of a specialized agent team was informed in part by [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).
