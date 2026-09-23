<div align="center">

# 🏛️ OpenCode Olympus Agents

### Give OpenCode a team — not one giant prompt.

A thin multi-agent orchestration layer for **OpenCode V2**. **OpenCode is the runtime. Olympus coordinates specialized agents.**

Native OpenCode child sessions · bounded orchestration · adaptive parallelism · explicit FAST fan-out · live activity · zero-prompt trusted-project execution.

**v0.1.0: Windows-first / Windows-qualified.**

</div>

---

## 🚀 Quick Start

**Requirements:** Windows, PowerShell 7 (`pwsh`), Git, OpenCode V2 (qualified with `opencode v2.0.14`), access to `openai/gpt-6-sol` and `openai/gpt-6-luna` with the configured variants. Linux/macOS installation has not been qualified.

After the `v0.1.0` tag is created and verified, install into the **current Git worktree root**:

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.1.0/install.ps1 | iex
```

This versioned URL is **not live until the tag is published**. Review the script before piping remote code to `iex`. If the repository is private, GitHub's anonymous raw URL will not work; use Manual Install instead. The installer defaults to the current directory, which must pass bootstrap's Git-root and destination checks. Prefer an explicit target when running a local script:

```powershell
pwsh ./install.ps1 -Version v0.1.0 -Target 'C:\path\to\your-project' -DryRun
pwsh ./install.ps1 -Version v0.1.0 -Target 'C:\path\to\your-project'
```

Once installed, `cd` into the project, run `opencode`, and describe the work. Installation is the explicit project trust action.

### 📦 Manual Install / pre-release preview

From a local copy of this repository (before the tag exists, do **not** use the public one-liner):

```powershell
pwsh ./scripts/bootstrap.ps1 -Target 'C:\path\to\your-project' -DryRun
pwsh ./scripts/bootstrap.ps1 -Target 'C:\path\to\your-project'
```

Bootstrap requires an existing Git worktree root, rejects unsafe targets and redirect escapes, checks conflicts and project worktree state, then validates effective OpenCode agents. `-DryRun` previews without installing. The local development installer can be qualified with `-SourceRoot <local-checkout>`; this is not the public installation path.

**Update/reinstall:** run the versioned installer again with the desired `-Version` and the same target (or run local bootstrap). The manifest at `.opencode/orchestrator-install.json` owns installed files; unchanged managed files yield `NO_CHANGES`, while `MANAGED_FILE_DRIFT` refuses a silent overwrite. Resolve drift deliberately before upgrading; unrelated files are not installer-owned. To remove Olympus, manually remove only the files listed in that manifest and then the manifest itself, after checking for local edits; no automatic uninstaller is provided. Never delete an entire `.opencode` directory without reviewing its contents.

---

## 🧭 The team

```text
Kael
├─ Veyra   research
├─ Orin    architecture
├─ Kovan   implementation
├─ Nox     validation
├─ Vera    review
└─ Sorin   exceptional diagnosis

User
└─ /maintain
   └─ hidden Maintenance
```

The **seven-agent cast** runs ordinary work. The hidden Maintenance Plane handles only explicit user-authorized `/maintain` tasks; Kael cannot route work to it automatically.

| Agent | Role | Model | Writes? | Shell? |
|---|---|---|---|---|
| 👑 Kael | Orchestrator | `openai/gpt-6-sol#high` | No | No |
| 🔭 Veyra | Researcher | `openai/gpt-6-luna#max` | No | No |
| 📐 Orin | Architect | `openai/gpt-6-luna#max` | No | No |
| 🔨 Kovan | Implementer | `openai/gpt-6-luna#max` | Yes, within task ownership | Yes |
| 👁️ Nox | Tester | `openai/gpt-6-luna#max` | No source edits | Yes |
| ⚖️ Vera | Reviewer | `openai/gpt-6-luna#max` | No | No |
| 🧭 Sorin | Deep diagnostician | `openai/gpt-6-sol#xhigh` | No | No |

**Separate, hidden control plane:** Maintenance · `openai/gpt-6-sol#high` · repository administration under `/maintain` only; may edit and use shell when explicitly authorized.

### ⚡ NORMAL vs FAST

- **NORMAL:** adaptive 0–4 active Kael children; minimum useful parallelism, cost/context conscious.
- **FAST:** explicitly user-selected, latency-oriented; up to four children when safe independent partitions exist, including repetitive item/source fan-out.
- **Four is a maximum, not a target.** Dependencies and disjoint writer ownership still apply.

```text
FAST: 20 URLs → 4 researchers → 5 URLs each
```

OpenCode remains the runtime; Olympus makes orchestration decisions, not a new scheduler.

### 👀 Live Activity HUD

```text
⚡ Olympus · 3 active
● Veyra   Researching repository
● Orin    Designing boundaries
● Kovan   Implementing feature
```

The passive, read-only TUI display uses native OpenCode session state. It does **not** control execution. It lets you check child progress without entering child sessions just to see status; it disappears when no direct children are running.

---

## 🛡️ Trust & ownership

An explicitly bootstrapped project is **USER-TRUSTED** at Olympus runtime. Kovan may execute project-controlled commands and edit within a task's `WRITE_SCOPE`; Nox may run project-controlled tests/builds and inspect Git without source edits. Trusted-project shell and normal tool/temp/cache access do not prompt for each routine command. **Olympus is not an OS sandbox.** `WRITE_SCOPE` is an orchestration ownership contract, not filesystem isolation. Do not bootstrap untrusted projects. Bootstrap target safety is stricter and separate: it checks Git roots, containment, redirects, ownership, and drift before installation. Avoid broad destructive commands without explicit authority.

Kael owns completion: implementation + passing validation + no material review findings + acceptance evidence. Research, design, retries and Sorin are used only when useful. No custom scheduler, daemon, agent database, or replacement for OpenCode permissions.

---

## 🧪 Qualification

Windows qualification uses OpenCode v2.0.14 and PowerShell 7.6.6. Run:

```powershell
pwsh ./tests/phase4c/qualify.ps1
pwsh ./tests/activity-hud/qualify.ps1
pwsh ./tests/adaptive-concurrency/qualify.ps1
pwsh ./tests/autonomy/qualify.ps1
pwsh ./tests/release/qualify.ps1
```

These check bootstrap target safety, stacks, managed drift and idempotency, effective agents/models, hidden Maintenance permissions/command, HUD discovery/presentation behavior, adaptive/FAST policy, and trusted-project Kovan/Nox permissions. Release checks exercise the installer against a disposable Git project. **Headless/static checks do not prove interactive child dispatch, live TUI rendering, real FAST selection, or agent runtime execution.** Validate those manually in an OpenCode session before publication; Maintenance interactive routing must be explicitly exercised with `/maintain` and denied when Kael attempts direct delegation.

---

## 🙏 Acknowledgements & provenance

The concept of a more expensive orchestrator coordinating specialized workers was informed in part by [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) (Apache-2.0). Olympus is an independent OpenCode V2 implementation, **not a fork**; no upstream code inheritance was identified in the repository audit. OpenCode provides the runtime; Olympus provides the orchestration/decision layer.

Licensed under [MIT](LICENSE). See [CHANGELOG.md](CHANGELOG.md) for release highlights.
