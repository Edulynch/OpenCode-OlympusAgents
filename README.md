<div align="center">

# 🏛️ Olympus Agents

<img src="docs/assets/olympus-cover.png" alt="Olympus Agents team with Kael coordinating coding specialists on Mount Olympus" width="100%">

**Your AI coding team, with active development on OpenCode V2.**

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) [![OpenCode V2](https://img.shields.io/badge/OpenCode-V2-f97316?style=flat-square)](https://opencode.ai/docs/) [![Windows qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md) [![MIT](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

[Install](#-install) · [Start](#-start-building) · [Agents](#-meet-the-team) · [Compatibility](#%EF%B8%8F-compatibility--trust) · [Uninstall](#-uninstall) · [Help](#-troubleshooting)

</div>

## 🚀 Install

You’ll need **Windows, PowerShell 7, and Git**, plus **OpenCode V2**, **Codex CLI**, or both. OpenCode V2 is the active-development runtime; Codex remains available at its frozen compatibility baseline. Run a project install from the root of a **trusted Git repository**.

The unified installer below is the primary interface. The legacy public commands remain compatible and use the immutable `v0.4.9` entrypoints and second-stage launcher. The launcher reads GitHub’s latest-release metadata, then downloads the installer from the selected release’s immutable tag. To install an exact version, run that release’s root `install.ps1` from the [Releases page](https://github.com/Edulynch/OpenCode-OlympusAgents/releases).

### Unified installer (from a checkout)

The repository provides one interactive installer. With no arguments, it asks whether to use the current project, another project path, or global scope, then asks for OpenCode, Codex, or both. This command runs the script in this checkout and reuses the release launcher and installer:

```powershell
pwsh -NoProfile -File ./install-olympus.ps1
```

For non-interactive installs, provide a native PowerShell scope parameter and a harness:

```powershell
pwsh -NoProfile -File ./install-olympus.ps1 -Project -Here -Harness all
pwsh -NoProfile -File ./install-olympus.ps1 -ProjectPath 'C:\Repos\sample' -Harness codex
pwsh -NoProfile -File ./install-olympus.ps1 -Global -Harness opencode
```

The interface uses PowerShell's declared native parameters (`-Project -Here`, `-ProjectPath`, and `-Global`) without adding a GNU-style argument parser. The twelve immutable v0.4.9 project/global and harness-specific install and uninstall commands remain supported in the compatibility sections below.

<details>
<summary>Compatibility: legacy install commands</summary>

### Project install

Choose the command for the runtime you want in this repository.

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/install/project/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/install/project/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/install/project/all.ps1 | iex
```

Run one command for the runtime or runtimes you use. You can add another runtime later; installing it leaves the first one in place.

### Global install

Use a global install to make Olympus available across your projects.

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/install/global/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/install/global/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/install/global/all.ps1 | iex
```

Global installation supports file installation and verification in both runtimes. Runtime agent discovery has separate evidence:

| Global support | OpenCode | Codex |
|---|---|---|
| File installation and verification | Supported | Supported |
| Agent discovery in runtime | **SUPPORTED** (Windows V2.0.26; isolated) | **SUPPORTED** (user-provided evidence) |

For **OpenCode**, global installation preserves your current default agent. Start with `opencode --standalone` or use your usual `opencode` service.

To select Kael, open the OpenCode V2 agent list with **Ctrl+X**, then **A** (the default), and choose **Kael**. You can also cycle primary agents with **Shift+Tab**. OpenCode V2 keybindings are customizable; see [V2 keybinds](https://opencode.ai/v2/docs/cli/keybinds).

If you want Kael to be the default for **new sessions**, set `"default_agent": "kael"` in `~/.config/opencode/opencode.jsonc`. The installer leaves this file unchanged. A project install selects Kael through the project’s `opencode.jsonc` when it loads; existing sessions keep their selected agent.

On isolated Windows with OpenCode V2.0.26, qualification covered runtime agent discovery and config-level selection. **Interactive key use and a model-backed prompt were not tested.** See [capabilities](docs/HARNESS-CAPABILITIES.md) and [Issue #7](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/7).

</details>

### Git worktrees (OpenCode, opt-in)

```text
pwsh -NoProfile -File "%OPENCODE_WORKTREE_BASE%\.opencode\scripts\worktree-setup.ps1"
```

Set this as the **OpenCode → Settings → Projects → Startup command**. Install Olympus in the base checkout first, and preserve any startup command you already use. [Worktree setup and safety →](docs/WORKTREES.md)

## Read-only operator CLI (from a checkout)

This checkout's Slice A CLI requires **Python 3.11+** and only its standard library. Run from the trusted Olympus checkout:

```text
python3.11 -B -m olympus --help
python3.11 -B -m olympus --version
python3.11 -B -m olympus models list
python3.11 -B -m olympus models list --json
python3.11 -B -m olympus config check --json
python3.11 -B -m olympus status --scope project --target "<absolute-Git-worktree-root>" --json
```

Queries preserve files and resolve all twelve roles through Core and the existing renderer. `config check` checks source/output consistency; `status` reads reported installation metadata and leaves integrity, ownership and installed assignments **unverified/unknown**. Global status is blocked without discovery. Editing and installed operations are unavailable through this CLI.

Windows Python and native `.cmd` smoke passed. Linux hosted run [38644271501](https://github.com/Edulynch/OpenCode-OlympusAgents/actions/runs/38644271501/job/116127153113) passed for PR #69; that run prepared the launcher with `chmod`, so the updated workflow still needs final CI to verify the Git-tracked executable bit without preparation. macOS **NOT VERIFIED**. See the [Slice A quickstart](specs/001-portable-olympus-cli/quickstart.md) for checkout-bound launchers, interpreter selection, human/JSON results and exit codes. The CLI does not call models or install dependencies.

## 💬 Start Building

From your project root, start the runtime you installed:

**OpenCode**

```shell
opencode
```

**Codex**

```shell
codex
```

Then tell Kael what you want to build. For example:

> “Add a search bar to my app. Make it keyboard-accessible and run the relevant tests.”

When Olympus is installed for a project, its configuration selects Kael when that project loads.

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

**NORMAL (default):** Kael chooses the amount of parallel work that fits the task.

**FAST (explicit):** When work is safe to split, Kael can use up to four independent agents. FAST keeps the required checks and does not parallelize dependent tasks.

> **Example:** “FAST: check these independent modules and fix the issues.”

## 👀 Live Activity

- **OpenCode:** The Olympus HUD shows read-only activity.
- **Codex:** Native activity is basic and partial.

## 🔧 Maintenance (OpenCode)

Ordinary project work, including Git and releases, stays with Kael. Ask Kael in plain language for those tasks.

For privileged OpenCode maintenance, explicitly run:

```text
/maintain <task>
```

This invokes hidden Aegis. Kael never invokes Aegis automatically. Codex has no equivalent Aegis capability.

## 🛡️ Compatibility & Trust

**Support policy (2026-10-16):** OpenCode V2 — **ACTIVE DEVELOPMENT**. Codex — **FROZEN COMPATIBILITY**: Codex is not removed or declared wholly incompatible, and its existing components, installers, manifests, and uninstall protections remain. New OpenCode capabilities do not require Codex equivalents. Codex authority, Aegis, hard `DENY`, and observability differences are frozen gaps; no new Codex version is claimed verified without version-specific evidence. See the [Codex baseline](docs/CODEX-COMPATIBILITY.md) and [roadmap](docs/ROADMAP.md).

| Capability | OpenCode | Codex |
|---|---|---|
| Project agents | Supported | Supported |
| Hard native `DENY` | Supported | GAP |
| Native permission `ASK` | Supported | Adaptable |
| Aegis maintenance | Supported | GAP |
| Activity display | Olympus HUD | Native, partial |

Install only in **trusted repositories**. Kovan and Nox can run shell commands, and task scope is **not an OS sandbox**. Olympus preserves user-owned files and refuses unsafe changes to managed files.

The following Codex CLI **0.162.1** observations distinguish root instructions from specialist threads:

- **Kael:** represented by root instructions, not a selectable child agent.
- **`/status`:** shows the root instruction-source label.
- **`/debug-config`:** shows configuration layers.
- **`/subagents`:** lists spawned specialist threads.
- **`/agents`:** shows the project-task dashboard; it does not prove a child role is active.
- **Root instruction precedence:** a nonempty `AGENTS.override.md` or `AGENTS.md` takes precedence over the `CODEX.md` fallback.

See the [Codex verification guide](docs/CODEX-COMPATIBILITY.md#verificar-kael-y-especialistas-en-codex-issue-23), [Issue #23](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/23), and the [full capability table](docs/HARNESS-CAPABILITIES.md).

## 🧹 Uninstall

### Unified uninstaller (from a checkout)

With no arguments, the interactive uninstaller asks whether to use the current project, another project path, or global scope, then asks for OpenCode, Codex, or both. It runs the script in this checkout:

```powershell
pwsh -NoProfile -File ./uninstall-olympus.ps1
```

For non-interactive uninstalls, provide a native PowerShell scope parameter and a harness:

```powershell
pwsh -NoProfile -File ./uninstall-olympus.ps1 -Project -Here -Harness all
pwsh -NoProfile -File ./uninstall-olympus.ps1 -ProjectPath 'C:\Repos\sample' -Harness codex
pwsh -NoProfile -File ./uninstall-olympus.ps1 -Global -Harness opencode
```

<details>
<summary>Compatibility: legacy uninstall commands</summary>

### Project uninstall

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/uninstall/project/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/uninstall/project/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/uninstall/project/all.ps1 | iex
```

### Global uninstall

**OpenCode**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/uninstall/global/opencode.ps1 | iex
```

**Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/uninstall/global/codex.ps1 | iex
```

**OpenCode + Codex**

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/uninstall/global/all.ps1 | iex
```

</details>

Uninstall removes only manifest-owned files. Modified managed files are protected from silent deletion.

## 🔄 Update

To update, rerun the matching [install command](#-install) for the same runtime and scope. Only Olympus-managed files are updated. For an exact version, follow the [release pinning guidance](#-install).

## 🆘 Troubleshooting

- **`opencode` not found:** [Install OpenCode V2](https://opencode.ai/docs/).
- **`OLYMPUS_REQUIRES_POWERSHELL_7`:** Install PowerShell 7.
- **Git target rejected:** Run the project installer from the repository root.
- **`MANAGED_FILE_DRIFT`:** Review your changes and follow the [recovery guide](docs/DEVELOPMENT.md).
- **Agents missing in a new worktree:** [Enable worktree startup](docs/WORKTREES.md).
- **Codex uses other root instructions:** Check `AGENTS.override.md` and `AGENTS.md`; see [Issue #23](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/23).

## 📚 Documentation

- [Worktrees](docs/WORKTREES.md) — setup, existing worktrees, and conflicts.
- [Harnesses](docs/HARNESSES.md) — OpenCode and Codex integration.
- [Capabilities](docs/HARNESS-CAPABILITIES.md) — exact support and known gaps.
- [Development](docs/DEVELOPMENT.md) — testing, permissions, and release process.
- [Roadmap](docs/ROADMAP.md) — planned improvements.
- [Releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases) and [Changelog](CHANGELOG.md) — versions and changes.
- [License](LICENSE) — MIT.

Olympus is an independent orchestration system, not a fork. The specialized-team idea was informed in part by [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).
