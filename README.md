<div align="center">

# 🏛️ Olympus Agents

### Give your coding runtime a team.

**Multi-agent coding orchestration for OpenCode and Codex.**

**Install once. Start building.**

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest)
[![OpenCode V2](https://img.shields.io/badge/OpenCode-V2-f97316?style=flat-square)](https://opencode.ai/docs/)
[![Windows Qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md)
[![MIT License](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

<p><a href="#-install">Install</a> · <a href="#-uninstall">Uninstall</a> · <a href="#-start-building">Start Building</a> · <a href="#-the-team">Agents</a> · <a href="#-normal-vs-fast">NORMAL vs FAST</a> · <a href="#-live-activity">Live Activity</a> · <a href="#-update">Update</a> · <a href="#-documentation">Docs</a></p>

</div>

## 🚀 Install

### Requirements

- Windows with PowerShell 7 installed
- Git
- OpenCode V2 when installing the OpenCode harness; Codex CLI when installing the Codex harness

Choose the runtime explicitly: **OpenCode**, **Codex**, or **both**. There is no public default harness.

The small one-line entrypoints below resolve the latest published GitHub release automatically. The actual Olympus installer is then downloaded and executed from that release's exact immutable tag, so you never have to replace a version manually.

### Project install

Open PowerShell in the root of the Git project where you want Olympus.

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

Installing one harness is additive; it does not remove the other.

### Global install

Global installation is also explicit:

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

Codex global runtime discovery is supported. OpenCode global files can be installed and verified, but OpenCode global runtime discovery remains a documented upstream **GAP**; use project installation when you need dependable OpenCode runtime discovery.

Only run downloaded scripts you trust. The public entrypoint is intentionally small and auditable; release installation remains pinned to the immutable release tag it resolves.

## 🧹 Uninstall

Olympus removes only resources recorded in its ownership manifest. If an Olympus-managed file was modified, project uninstall refuses to delete it instead of silently discarding the change.

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

## 💬 Start Building

In the same project folder, start the runtime you installed:

```powershell
# OpenCode
opencode

# Codex
codex
```

Then describe what you want to build in plain language. For example:

> Add a search bar to my app. Make it keyboard-accessible and run the relevant tests.

Kael coordinates the team as needed: research, implementation, testing, and review. You don't have to choose agents yourself.

## 🧭 The Team

| Agent | What they do |
|---|---|
| **Kael — The Master** (`kael`) | Understands your request and coordinates the work. |
| **Veyra — The Explorer** (`veyra`) | Researches the project and gathers context. |
| **Orin — The Architect** (`orin`) | Decides architecture and interface boundaries. |
| **Atlas — The Planner** (`atlas`) | Optionally plans the execution order of already-scoped changes. |
| **Kovan — The Coder** (`kovan`) | Writes code. |
| **Argus — The Bug Hunter** (`argus`) | Optionally diagnoses nontrivial functional defects. |
| **Nox — The Tester** (`nox`) | Runs checks and tests. |
| **Vera — The Judge** (`vera`) | Reviews the result. |
| **Talos — The Sentinel** (`talos`) | Optionally reasons about evidenced security defects. |
| **Thales — The Sage** (`thales`) | Helps diagnose difficult problems when needed. |
| **Helios — The Optimizer** (`helios`) | On explicit optimization requests, proposes a bounded improvement and stops for user approval. |

Olympus Core defines what the team and its orchestration mean. Harness adapters define how each runtime expresses the same Core. **OpenCode and Codex are the two supported project-local harnesses**; Codex uses its native root, agents, approvals, and activity view, while capability gaps remain explicit. Global static installation is supported for both, but global runtime discovery is `GAP` for OpenCode and `SUPPORTED` for Codex; see the [capability contract](docs/HARNESS-CAPABILITIES.md).

The OpenCode and Codex adapters use the same Olympus Core, but their capabilities are not identical. OpenCode provides hard DENY, the explicit `/maintain` → Aegis entry, and the Activity HUD. Codex supports multi-agent work, result delivery, ALLOW, and adaptable ASK; DENY and Aegis remain gaps, and activity visibility is basic/partial. See the [capability contract](docs/HARNESS-CAPABILITIES.md).

### Out-of-scope project work

Workers return `NEED_AUTHORITY` only when they discover an otherwise legitimate scope not yet delegated. Kael classifies requests as ALLOW, NATIVE_ASK, or DENY. For an exact eligible project-owned path covered by native ASK, Kael delegates the exact task/scope as `NATIVE_ASK`: the child attempts the tool and OpenCode's native permission UI obtains the user's one-shot decision; this is not pre-approval and does not trigger a duplicate Kael QUESTION. Rejection/cancellation stops without fallback. If native ASK does not apply, Kael uses the Question Barrier when needed. Explicit user prohibitions and Olympus-owned native DENYs cannot be overridden. Explicit `/maintain` accepts the delivered task in any repository.

## 🔧 Maintenance

Use `/maintain <task>` to explicitly invoke the hidden 🛡️ Aegis The Keeper executor in any repository. The Olympus-owned command immediately establishes `MAINTENANCE_AUTH: VALID` and `AEGIS_SCOPE: ACCEPTED` for the delivered task, without a second provenance or ownership gate. Kael cannot invoke Aegis automatically. Normal work, including project releases, belongs to the normal Kael plane by recommendation because it offers routing, specialists and fast-path work. Destructive or high-impact operations require explicit task authorization.

Canonical display identities live in `olympus/core/identities.toml`; OpenCode and Codex derive display descriptions from this source. Aegis — The Keeper (`aegis`) is the hidden maintenance identity and is not a normal team worker.

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

The OpenCode activity display is read-only and disappears when no agents are working. Codex uses its native agent/activity visibility; Olympus does not claim the same HUD there.

## 🛡️ Trust

Olympus treats an installed project as trusted. Kovan and Nox can run commands from that project while implementing and validating work. Only install Olympus into repositories you trust; see [Development & qualification](docs/DEVELOPMENT.md) for details.

Contributors can run the unified qualification entry point from a source checkout with `pwsh -NoProfile -File ./scripts/qualify.ps1 -Profile FAST` (replace `FAST` with `FULL` or `RUNTIME`). FAST is offline-only, FULL adds the existing installer/history fixtures with an explicit qualification stub where needed, and RUNTIME is limited to effective runtime boundaries; the known OpenCode global-discovery GAP (#7) is diagnosed separately, not treated as supported. See [Development & qualification](docs/DEVELOPMENT.md) for prerequisites and evidence limits.

## 🔄 Update

Run the same **install** command again for the same scope and harness. The entrypoint resolves the latest published release and the installer updates only Olympus-managed resources.

Examples:

```powershell
# Project / OpenCode
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/project/opencode.ps1 | iex

# Global / Codex
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/global/codex.ps1 | iex
```

Advanced verification, tagged release validation, and installer internals are documented in [Development & qualification](docs/DEVELOPMENT.md) and [Harness installation](docs/HARNESSES.md).

## 🆘 Troubleshooting

- **`opencode` command unavailable?** Install and configure [OpenCode](https://opencode.ai/docs/) first.
- **`OLYMPUS_REQUIRES_POWERSHELL_7`?** Install PowerShell 7 and run the same install command again.
- **Not a valid Git project root?** Open PowerShell in the root folder of your Git project and run the installer again.
- **`MANAGED_FILE_DRIFT`?** Olympus found a manually changed file it manages and refused to overwrite it silently. See [Development & qualification](docs/DEVELOPMENT.md) for recovery details.

## 📚 Documentation

- [OpenCode documentation](https://opencode.ai/docs/) — install and learn OpenCode.
- [Development & qualification](docs/DEVELOPMENT.md) — maintainer docs, bootstrap internals, qualification, and release workflow.
- [Core and harness adapters](docs/HARNESSES.md) — canonical source layout, generated outputs, renderer/check commands, and capability contract.
- [Harness capability contract](docs/HARNESS-CAPABILITIES.md) — current OpenCode and Codex support states.
- [Roadmap](docs/ROADMAP.md) — planned agent evolution and future qualification work.
- [GitHub Releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases) and [changelog](CHANGELOG.md) — published versions and release history.
- [License](LICENSE) — MIT.

Olympus is an independent orchestration system with officially supported OpenCode and Codex adapters, not a fork. The idea of a specialized agent team was informed in part by [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).
