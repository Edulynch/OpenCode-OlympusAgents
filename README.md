<div align="center">

# 🏛️ Olympus Agents

<img src="docs/assets/olympus-cover.webp" alt="Olympus Agents team with Kael coordinating coding specialists on Mount Olympus" width="1400">

**Your AI coding team for OpenCode and Codex.**

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) [![OpenCode V2](https://img.shields.io/badge/OpenCode-V2-f97316?style=flat-square)](https://opencode.ai/docs/) [![Windows qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md) [![MIT](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

[Install](#-install) · [Start](#-start-building) · [Agents](#-meet-the-team) · [Compatibility](#-compatibility--trust) · [Uninstall](#-uninstall) · [Help](#-troubleshooting)

</div>

## 🚀 Install

| Item | Details |
|---|---|
| System | Windows, PowerShell 7, Git |
| Runtime | OpenCode V2, Codex CLI, or both |
| Project install | Run at a trusted Git repository root |
| Public source | Immutable `v0.4.7` entrypoint and second-stage launcher URLs |
| Release selection | The launcher reads GitHub latest-release metadata, then downloads the selected release's installer from its immutable tag |
| Exact version | Use that release's root `install.ps1` ([Releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases)) |

### Project install (recommended)

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install/project/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install/project/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install/project/all.ps1 | iex
```

Run **one** command for your runtime. Installing another runtime later does not remove the first.

### Global install

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install/global/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install/global/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/install/global/all.ps1 | iex
```

| Global support | OpenCode | Codex |
|---|---|---|
| File installation and verification | Supported | Supported |
| Agent discovery in runtime | **SUPPORTED** (Windows V2.0.26; isolated) | **SUPPORTED** (user-provided evidence) |

| OpenCode global activation | Behavior |
|---|---|
| Startup | Preserves your existing default agent. Run `opencode --standalone` or `opencode` with your usual service. |
| Select Kael | Open the V2 agent list with **Ctrl+X**, then **A** (default), and select **Kael**; or cycle primary agents with **Shift+Tab**. [V2 keybinds](https://opencode.ai/v2/docs/cli/keybinds) are customizable. |
| Optional default | To select Kael for **new sessions**, set `"default_agent": "kael"` in `~/.config/opencode/opencode.jsonc`. The installer leaves this file unchanged. |
| Project install | The project `opencode.jsonc` selects Kael when loaded. Existing sessions keep their selected agent. |
| Qualification | Isolated Windows/OpenCode V2.0.26 covered agent discovery and config-level selection; **interactive key use and a model-backed prompt were not tested**. See [capabilities](docs/HARNESS-CAPABILITIES.md) and [Issue #7](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/7). |

### Git worktrees (OpenCode, opt-in)

```text
pwsh -NoProfile -File "%OPENCODE_WORKTREE_BASE%\.opencode\scripts\worktree-setup.ps1"
```

Set this under **OpenCode → Settings → Projects → Startup command**. Install Olympus in the base checkout first; preserve any existing startup command. [Worktree setup and safety →](docs/WORKTREES.md)

## 💬 Start Building

| Runtime | Command |
|---|---|
| OpenCode | `opencode` |
| Codex | `codex` |

Example: `Add a search bar to my app. Make it keyboard-accessible and run the relevant tests.`

When active, Kael routes work to specialists; project installs select Kael through configuration.

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

| Mode | Behavior |
|---|---|
| **NORMAL** (default) | Uses only the parallel work useful for the task |
| **FAST** (explicit) | Runs up to four independent agents when safe; never skips checks or parallelizes dependent tasks |

Example: `FAST: check these independent modules and fix the issues.`

## 👀 Live Activity

| Runtime | Activity |
|---|---|
| OpenCode | Olympus HUD with read-only activity |
| Codex | Basic, partial native activity view |

## 🔧 Maintenance (OpenCode)

| Work | Route |
|---|---|
| Normal project work, including Git and releases | Ask Kael in plain language |
| Privileged maintenance | Explicitly ask OpenCode `/maintain <task>` to invoke hidden Aegis |
| Codex | No equivalent Aegis capability |

Aegis is never invoked automatically by Kael.

## 🛡️ Compatibility & Trust

| Capability | OpenCode | Codex |
|---|---|---|
| Project agents | Supported | Supported |
| Hard native `DENY` | Supported | GAP |
| Native permission `ASK` | Supported | Adaptable |
| Aegis maintenance | Supported | GAP |
| Activity display | Olympus HUD | Native, partial |

Install only in **trusted repositories**. Kovan and Nox can run shell commands; task scope is **not an OS sandbox**. Olympus preserves user-owned files and refuses unsafe managed-file changes.

Codex CLI **0.162.1** observations:

| Check | What it shows |
|---|---|
| Kael | Root instructions, not a selectable child agent |
| `/status` | Root instruction-source label |
| `/debug-config` | Configuration layers |
| `/subagents` | Spawned specialist threads |
| `/agents` | Project-task dashboard; not proof of a child role |
| Root instructions | A nonempty `AGENTS.override.md` or `AGENTS.md` takes precedence over the `CODEX.md` fallback |

[Codex verification guide](docs/CODEX-COMPATIBILITY.md#verificar-kael-y-especialistas-en-codex-issue-23) · [Issue #23](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/23) · [Full capability table →](docs/HARNESS-CAPABILITIES.md)

## 🧹 Uninstall

### Project uninstall

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/uninstall/project/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/uninstall/project/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/uninstall/project/all.ps1 | iex
```

Uninstall removes only manifest-owned files; modified managed files are protected from silent deletion.

### Global uninstall

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/uninstall/global/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/uninstall/global/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.7/uninstall/global/all.ps1 | iex
```

## 🔄 Update

| Need | Action |
|---|---|
| Update | Rerun the matching [install command](#-install) for the same runtime and scope; only Olympus-managed files are updated. |
| Exact version | See [Install](#-install) for release pinning. |

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
