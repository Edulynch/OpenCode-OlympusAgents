# Olympus Agents

Olympus is an AI coding team with **OpenCode V2 in ACTIVE DEVELOPMENT** and **Codex in FROZEN COMPATIBILITY**.

[![Latest release](https://img.shields.io/github/v/release/Edulynch/OpenCode-OlympusAgents?style=flat-square)](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) [![Windows qualified](https://img.shields.io/badge/Windows-qualified-2563eb?style=flat-square)](docs/HARNESSES.md) [![MIT](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)](LICENSE)

## Requirements

- Windows; this installer is currently Windows-qualified.
- PowerShell 7 (`pwsh`) available on `PATH`. Windows PowerShell 5.1 may start a command only when PowerShell 7 is also installed.
- Git for project-scope operations; select the root of a trusted Git worktree.
- Install OpenCode V2 and/or Codex CLI for the harnesses you intend to use.

## Fast Install

The URLs below start from the versioned `v0.4.11` bootstrap. That bootstrap queries GitHub's `releases/latest` metadata to select an eligible published release and tag; `v0.4.11` is not a preselected final installer version. The release metadata checks fail closed when their requirements are not met.

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.11/install-olympus.ps1 | iex
```

## Fast Uninstall

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.11/uninstall-olympus.ps1 | iex
```

The bootstrap selects a tag for its release launcher; that launcher resolves `releases/latest` again for the installer and source archive and checks installer identity before execution. GitHub's immutability flag is not independent cryptographic signature verification. See [installation, parameters, safety, and troubleshooting](docs/INSTALLATION.md).

## Project status

- **OpenCode V2: ACTIVE DEVELOPMENT.**
- **Codex: FROZEN COMPATIBILITY.** Existing support and safe uninstall behavior remain; no new Codex capabilities or parity are implied.

## NORMAL vs FAST

**NORMAL (default):** Kael chooses useful, bounded parallel work for the task.

**FAST (explicit):** when work is safe to split, it uses up to four agents, keeps required checks, and does not parallelize dependent tasks.

## Maintenance (OpenCode)

Ordinary Git work, including releases, stays with Kael in the normal project workflow. Only an explicit `/maintain` invokes hidden Aegis; Kael never escalates there automatically. Codex has no equivalent Aegis capability.

## Documentation

- [Installation](docs/INSTALLATION.md) — prerequisites, entrypoints, parameters, safety, and troubleshooting.
- [Harness capabilities](docs/HARNESS-CAPABILITIES.md) · [Codex compatibility](docs/CODEX-COMPATIBILITY.md)
- [Development](docs/DEVELOPMENT.md) · [Roadmap](docs/ROADMAP.md) · [Worktrees](docs/WORKTREES.md)
- [Releases](https://github.com/Edulynch/OpenCode-OlympusAgents/releases) · [Changelog](CHANGELOG.md) · [License](LICENSE)

Olympus is an independent orchestration system, not a fork. The specialized-team idea was informed in part by [codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0).
