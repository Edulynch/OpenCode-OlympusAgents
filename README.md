<div align="center">

# 🏛️ Olympus Agents

**Your AI coding team for OpenCode and Codex.**

Plan, build, test, and review without manually coordinating agents.

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest)
[![OpenCode V2](https://img.shields.io/badge/OpenCode-V2-f97316?style=flat-square)](https://opencode.ai/docs/)
[![Windows qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md)
[![MIT](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

[Install](#-install) · [Start](#-start-building) · [Agents](#-meet-the-team) · [Compatibility](#-compatibility--trust) · [Uninstall](#-uninstall) · [Help](#-troubleshooting)

</div>

## 🚀 Install

| You need | |
|---|---|
| System | Windows, PowerShell 7, Git |
| Runtime | OpenCode V2, Codex CLI, or both |
| Project install | A trusted Git repository root |

Run **one** command for your runtime. Each entrypoint resolves the latest published release and uses its immutable tag.

### Project install (recommended)

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/project/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/project/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/project/all.ps1 | iex
```

Installing one runtime later does not remove the other.

### Global install

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/global/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/global/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/global/all.ps1 | iex
```

| Global support | OpenCode | Codex |
|---|---|---|
| File installation and verification | Supported | Supported |
| Agent discovery in runtime | **SUPPORTED** (Windows V2.0.26; isolated) | **SUPPORTED** (user-provided evidence) |

OpenCode global installation **preserves your existing default agent**. Start `opencode --standalone` (or `opencode` with your usual service), then select the visible primary agent **Kael** from the V2 agent list (**Ctrl+X**, then **A** by default), or cycle primary agents with **Shift+Tab**. Keybinds can be customized; see the [official V2 keybinds](https://opencode.ai/v2/docs/cli/keybinds). To make Kael the default for **new sessions**, opt in by setting `"default_agent": "kael"` in your own `~/.config/opencode/opencode.jsonc`; the installer does not edit it. In a **project install**, the project `opencode.jsonc` already selects Kael when that configuration is loaded. Existing sessions retain their selected agent. Qualification covered agent discovery and config-level selection on isolated Windows/OpenCode V2.0.26; **interactive key use and a model-backed prompt were not tested**. See [capabilities](docs/HARNESS-CAPABILITIES.md) and [Issue #7](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/7).

### Git worktrees (OpenCode, opt-in)

**OpenCode → Settings → Projects → Startup command**

```text
pwsh -NoProfile -File "%OPENCODE_WORKTREE_BASE%\.opencode\scripts\worktree-setup.ps1"
```

Install Olympus in the base checkout first. Keep any existing startup command instead of replacing it. [Worktree setup and safety →](docs/WORKTREES.md)

## 💬 Start Building

Run the CLI you installed:

```powershell
# OpenCode
opencode

# Codex
codex
```

**Example prompt**

> Add a search bar to my app. Make it keyboard-accessible and run the relevant tests.

Kael routes work to the team; you do not need to pick agents manually.

## 🧭 Meet the Team

| Agent | Role |
|---|---|
| **Kael — The Master** | Coordinates requests and delivers results |
| **Veyra — The Explorer** | Explores code and gathers context |
| **Orin — The Architect** | Designs boundaries and architecture |
| **Atlas — The Planner** | Plans scoped implementation steps |
| **Kovan — The Coder** | Implements changes |
| **Argus — The Bug Hunter** | Diagnoses difficult functional bugs |
| **Nox — The Tester** | Runs checks and tests |
| **Vera — The Judge** | Reviews work |
| **Talos — The Sentinel** | Investigates evidenced security boundary defects |
| **Thales — The Sage** | Provides focused technical reasoning |
| **Helios — The Optimizer** | Proposes explicitly requested optimizations |

## ⚡ NORMAL vs FAST

| Mode | Use |
|---|---|
| **NORMAL** (default) | Only as much parallel work as the task needs |
| **FAST** (explicit) | Up to four independent agents when safe |

**NORMAL** (default): use only the parallel work that is useful.
Explicitly ask for **FAST**: up to four agents can run independent tasks.

```text
FAST: check these independent modules and fix the issues.
```

FAST does not skip checks and never runs dependent tasks in parallel.

## 👀 Live Activity

```text
⚡ Olympus · 3 active
● Veyra   Researching repository
● Orin    Designing boundaries
● Kovan   Implementing feature
```

The OpenCode HUD is read-only. Codex has its own basic/partial activity view.

## 🔧 Maintenance (OpenCode)

| Action | Command |
|---|---|
| Explicit Aegis maintenance | `/maintain <task>` |
| Normal project work | Ask Kael in plain language |

Normal Git work (including project releases) belongs to the normal Kael plane.
Aegis is hidden and cannot be invoked automatically by Kael. Codex has no equivalent Aegis capability.

## 🛡️ Compatibility & Trust

| Capability | OpenCode | Codex |
|---|---|---|
| Project agents | Supported | Supported |
| Hard native `DENY` | Supported | GAP |
| Native permission `ASK` | Supported | Adaptable |
| Aegis maintenance | Supported | GAP |
| Activity display | Olympus HUD | Native, partial |

Only install in **trusted repositories**. Kovan and Nox can run shell commands; task scope is **not** an OS sandbox. Olympus preserves user-owned files and refuses unsafe managed-file changes.

Codex root `AGENTS.override.md` or `AGENTS.md` may override the installed `CODEX.md`. See [Issue #23](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/23).

[Full capability table →](docs/HARNESS-CAPABILITIES.md)

## 🧹 Uninstall

Uninstall removes only manifest-owned files; modified managed files are protected from silent deletion.

### Project uninstall

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/uninstall/project/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/uninstall/project/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/uninstall/project/all.ps1 | iex
```

### Global uninstall

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/uninstall/global/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/uninstall/global/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/uninstall/global/all.ps1 | iex
```

## 🔄 Update

Run the same [install command](#-install) again for the same scope and runtime. Only Olympus-managed files are updated.

## 🆘 Troubleshooting

| Problem | What to do |
|---|---|
| `opencode` not found | [Install OpenCode V2](https://opencode.ai/docs/) |
| `OLYMPUS_REQUIRES_POWERSHELL_7` | Install PowerShell 7 |
| Git target rejected | Run in the project's Git root |
| `MANAGED_FILE_DRIFT` | Inspect your changes; [recovery guide](docs/DEVELOPMENT.md) |
| Agents missing in a new worktree | [Enable worktree startup](docs/WORKTREES.md) |
| Codex uses other root instructions | Check `AGENTS.override.md` / `AGENTS.md` ([Issue #23](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/23)) |

## 📚 Documentation

| Guide | Contents |
|---|---|
| [Worktrees](docs/WORKTREES.md) | Setup, existing worktrees, conflicts |
| [Harnesses](docs/HARNESSES.md) | OpenCode and Codex integration |
| [Capabilities](docs/HARNESS-CAPABILITIES.md) | Exact support and known gaps |
| [Development](docs/DEVELOPMENT.md) | Testing, permissions, release process |
| [Roadmap](docs/ROADMAP.md) | Planned improvements |
| [Releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases) · [Changelog](CHANGELOG.md) | Versions and changes |
| [License](LICENSE) | MIT |

Olympus is an independent orchestration system, not a fork. The specialized-team idea was informed in part by [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).
