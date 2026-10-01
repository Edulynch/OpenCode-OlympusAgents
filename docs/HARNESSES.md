# Olympus Core and harness adapters

**Olympus Core defines what Olympus means.** A harness adapter defines how a
runtime expresses that same Core. The officially supported harnesses are
OpenCode and Codex; capability gaps are explicit and never weaken a Core
guarantee.

## Source layout

| Source | Owns |
|---|---|
| `olympus/roles/<role>.md` | One conceptual definition and responsibility boundary for each of the 12 canonical roles. Kael is the ROOT ORCHESTRATOR independently of runtime. |
| `olympus/core/identities.toml` | The single canonical full display identity for each technical role ID; renderers derive OpenCode descriptions/HUD and Codex descriptions/root heading from it. |
| `olympus/core/models.toml` | The only role → model family / reasoning effort map, plus each family's OpenCode and Codex identifier. A family upgrade is one edit followed by rendering and qualification. |
| `olympus/policies/routing.md` and `orchestration.toml` | Specialist suppression, trivial fast path, direct-root ownership, bounded parallelism, and the canonical maximum of four children. |
| `olympus/policies/result-lifecycle.md` | Question barrier, completion barrier, original-result reconciliation, and no-blind-retry semantics. |
| `olympus/policies/authority.md` | Canonical ALLOW / ASK / DENY meaning. |
| `olympus/policies/maintenance-plane.md` | Task-scoped Aegis authority established by explicit `/maintain` command entry, and the no-automatic-escalation boundary. |
| `olympus/harnesses/capabilities.toml` | The two-harness capability contract (`SUPPORTED`, `ADAPTABLE`, `PARTIAL`, `GAP`, `NOT_NEEDED`). |
| `olympus/harnesses/opencode/` | OpenCode permission/frontmatter, native role-prompt representation, `/maintain`, default config, and activity plugin sources. |
| `olympus/harnesses/codex/` | Codex-native role-prompt representation, root instructions, project config, and permission profile. Codex has no Aegis agent. |

Adapter prompt files intentionally contain runtime-specific instructions, not
second canonical role or model definitions. Changes to Olympus meaning start in
Core; update the relevant adapter representation and qualifications without
copying or deleting a Core guarantee.

## Render and check

Requires Python 3.11+ from the local standard library; no network or packages
are needed.

```powershell
python scripts/render_harnesses.py render --harness opencode
python scripts/render_harnesses.py render --harness codex
python scripts/render_harnesses.py render --harness all
python scripts/render_harnesses.py check --harness all
python tests/harness-core/qualify.py
```

`render` is deterministic and idempotent. `check` is read-only: it compares
expected bytes in memory, reports every missing/drifted output, creates no
temporary repository files, and exits nonzero on drift. Generated files contain
a parser-safe generated marker; **edit Core/adapter source, not generated
outputs**.

## Generated outputs

| Adapter | Managed/generated outputs |
|---|---|
| OpenCode | `.opencode/agents/**`, `.opencode/commands/maintain.md`, `.opencode/plugins/olympus-activity/**`, `opencode.jsonc` |
| Codex | `CODEX.md`, `.codex/config.toml`, `.codex/agents/*.toml` |
| Shared contract presentation | `docs/HARNESS-CAPABILITIES.md` |

The installer accepts `-Scope project` (the default and project-scope behavior
remains compatible with beta.5) or the tagged global-install foundation `-Scope global`; either scope accepts
`-Harness opencode`, `-Harness codex`, or
`-Harness all`; the default remains `opencode` for the existing one-line install
experience. It discovers generated adapter outputs under `.opencode/**` and
`.codex/**` and the generated root file for each harness, so role rosters and
policies are not copied into a second installer inventory. Additions are
non-destructive: choosing one harness never removes the other.

Managed ownership remains hash-based. A manifest records `installed_harnesses`
and the union of managed output hashes. Existing beta.4 OpenCode manifests with
no harness field are interpreted as OpenCode-only and upgraded in place. For an
OpenCode installation the manifest remains `.opencode/orchestrator-install.json`;
a Codex-only installation uses `.codex/orchestrator-install.json`, so it does not
create `.opencode/**` or `opencode.jsonc`. Adding OpenCode to Codex safely moves
the manifest to the OpenCode location while retaining Codex outputs. Differing
unowned destinations are conflicts; exact generated Codex files may be adopted.
VerifyOnly checks only the requested harness subset, so drift in the other
installed harness does not invalidate a subset verification. It is read-only.
Project `VerifyOnly` verifies generated source, scope/version metadata, manifest
ownership, and hashes only; it does not launch OpenCode runtime discovery or any
optional external tooling in the project target.

## Global installation foundation (introduced in tagged v0.4.0)

Path evidence gathered for this foundation:

| Harness | Windows evidence | Unix-like evidence | Global resources used |
|---|---|---|---|
| OpenCode | Fresh CLI child `opencode debug paths` reported home/config/data/cache/state/tmp/log within isolated HOME, four XDG roots, and TEMP. `OPENCODE_CONFIG_DIR` selects the config layer only; it is not a sandbox for all global paths. | Official current docs specify `~/.config/opencode`; no Unix runtime was available. | Official agent/plugin docs identify `~/.config/opencode/agents/` and `~/.config/opencode/plugins/`; global commands use the same config-root `commands/` convention. The user-owned `opencode.json` is not overwritten; Kael is available by explicit selection, but no global default-agent change is made. |
| Codex | Current CLI help resolves user configuration from `~/.codex/config.toml`; the current CLI accepts `CODEX_HOME` and profiles at `$CODEX_HOME/<name>.config.toml`. | Current official docs specify `~/.codex` unless `CODEX_HOME` is set; no Unix runtime was available. | Global custom agents at `~/.codex/agents/`, profile `olympus.config.toml`, and the global instructions file `AGENTS.md`. The existing base `config.toml` is not modified; use `codex --profile olympus`. Existing `AGENTS.md` is a user-owned conflict and is never overwritten. |

Current official path/config references (consulted 2026-09-30): [OpenCode
agents](https://opencode.ai/docs/agents/), [commands](https://opencode.ai/docs/commands/),
[plugins](https://opencode.ai/docs/plugins/), [config](https://opencode.ai/docs/config/);
[Codex global instructions](https://developers.openai.com/codex/agent-configuration/agents-md.md),
[subagents](https://developers.openai.com/codex/agent-configuration/subagents.md),
[config reference](https://developers.openai.com/codex/config-file/config-reference.md).
Codex's global `AGENTS.override.md` also takes precedence over `AGENTS.md`; the
installer treats an existing global override as a conflict rather than writing
an inactive Olympus root.

The installer remains Windows-qualified. `-Scope global` defaults to no user-data
overwrite, records `scope = global`, `installed_harnesses`, `installed_version`,
and hash-owned `managed_files`, and `-VerifyOnly` verifies one scope at a time.
OpenCode global `opencode.json` and Codex base `config.toml` remain untouched.
Updates refuse drift, preserve unrelated user config, and do not remove
project-local installs; the explicit migration result is `GLOBAL_INSTALLED
PROJECT_LOCAL_REMAINS_AS_OVERRIDE`. A project-local Olympus manifest in the
current Git root is reported, including version/hash drift. Other repositories
are not scanned or modified. Static global installer qualification passes, but
runtime discovery is a separate contract:

| Harness | Global support | Runtime evidence and blocker |
|---|---|---|
| OpenCode | **GAP** | CLI `2.0.20`; run `4b1610d3387a4afcaa8fe24336ef0362` preflighted `opencode debug paths` in fresh A/B processes sharing the same isolated `HOME`, `USERPROFILE`, four XDG roots, and `TEMP/TMP`; every required path, including `tmp` and `log`, resolved inside those roots, with zero real-profile paths in runtime output. Both global installs and read-only `VerifyOnly` passed; each clean fixture returned HTTP 200 for `GET /api/agent` with the exact fixture location. The first response was empty; one explicit lazy-load probe returned only built-ins (`build`, `compaction`, `explore`, `general`, `plan`, `summary`, `title`). No Olympus agent or either diagnostic marker appeared, although all 12 generated global agent files were installed and verified and the hidden/subagent Aegis resource hash matched. Both owned servers were stopped after identity/listener checks and evidence/logs collected. Global custom-agent discovery remains a GAP and issue #7 stays OPEN. Evidence: `C:\Users\Public\opencode-olympus-qualification\olympus-global-runtime-4b1610d3387a4afcaa8fe24336ef0362`. |
| Codex | **SUPPORTED** | The user-provided Codex runtime evidence classifies `CODEX_GLOBAL_RUNTIME: SUPPORTED`. It was accepted as supplied and not re-run during this continuation; no additional Codex smoke or profile investigation was performed. Existing `DENY = GAP` and `AEGIS = GAP` classifications are unchanged. |

OpenCode's official current config docs confirm global agents under
`~/.config/opencode/agents/`, `OPENCODE_CONFIG_DIR` as a custom config directory,
and later project-local config/`.opencode` sources taking precedence. Codex's
current docs confirm global instructions under `$CODEX_HOME/AGENTS.md` (unless
`AGENTS.override.md` exists), project instructions layered after the global
instructions, custom agents under `$CODEX_HOME/agents/`, and profile files at
`$CODEX_HOME/<profile>.config.toml`. These contracts establish intended paths
and precedence, not runtime discovery. A global install plus unrelated project
files and the installer-owned project override/migration paths are covered by
isolated installer tests; no runtime semantic merge is claimed.

The generated capability row `GLOBAL_RUNTIME_DISCOVERY` is per-harness:
OpenCode is `GAP` because its isolated runtime omitted the installed global
Olympus agents in both config modes; Codex remains `SUPPORTED` based on the
user-provided runtime PASS evidence and was not re-run. The OpenCode
qualification `tests/global-runtime/qualify.ps1` records the fresh child
environment, all effective `debug paths`, exact server PID/endpoint, config
root, clean fixture cwd, first and lazy-load API responses, logs, and
real-profile sentinel results. `OPENCODE_CONFIG_DIR` is a config-layer
override, not a sandbox for global data/cache/state paths. Latest evidence:
`C:\Users\Public\opencode-olympus-qualification\olympus-global-runtime-4b1610d3387a4afcaa8fe24336ef0362`.
No Unix global install/runtime is qualified.

### Codex global runtime evidence

The user-provided Codex runtime evidence is recorded as
`CODEX_GLOBAL_RUNTIME: SUPPORTED`. It was not rerun during this continuation; no
further Codex profile/authentication investigation or additional smoke was
performed.

Global uninstall is available only for manifest/hash-verified resources. It
leaves parent directories, base harness configuration, and project-local state
untouched. The v0.4.0 validation tag contains this foundation; release
validation failed because release-facing documentation contradicted its
integrated state, and no GitHub Release was created. The v0.4.1 validation tag
also failed release validation because documentation described that version as
upcoming; no GitHub Release was created. Both tags are immutable historical
validation attempts. The corrective v0.4 line continues with a stable,
version-neutral release-documentation model.

Static qualification entry points for this foundation (the active installer
identity is defined by `install.ps1`; beta.5 references below remain
historical):

```powershell
# Read-only plan from a checkout; writes nothing to either global root.
pwsh -NoProfile -File ./install.ps1 -SourceRoot . -Scope global -Harness opencode -DryRun
pwsh -NoProfile -File ./install.ps1 -SourceRoot . -Scope global -Harness codex -DryRun
pwsh -NoProfile -File ./install.ps1 -SourceRoot . -Scope global -Harness all -DryRun

# Automated global path/ownership/verify/update/uninstall fixtures.
pwsh -NoProfile -File ./tests/global-installer/qualify.ps1

# OpenCode global path isolation and roster qualification.
pwsh -NoProfile -File ./tests/global-runtime/qualify.ps1
```

The OpenCode project adapter provides the `/maintain` command, hidden Aegis,
native ASK, hard DENY, Activity HUD, roles, models, permissions, and
installer-managed surface. This project capability statement does not imply
global runtime discovery, which remains a `GAP`.
Codex installation does not imply capability parity: Codex multi-agent and
result delivery are supported, ALLOW is supported, ASK is adaptable, DENY and
Aegis remain gaps, and activity visibility is partial/basic. See the generated
[capability contract](HARNESS-CAPABILITIES.md).

Codex uses its root thread as Kael, custom specialists, per-role model/effort,
native multi-agent tools, bounded fan-out/fan-in, child result delivery, and
native activity visibility. Current user-provided runtime evidence records
Kael root, Kael→Veyra, Kovan→Nox functional work, four-child fan-out/fan-in,
concurrency of at least two, result delivery, ALLOW, and native ASK approval
as passing/confirmed; these smokes were **not rerun** during modularization.
`tests/codex/validate_profile.py` remains static qualification only.

## Declared Codex gaps

- `DENY = GAP`: Codex does not currently provide equivalent hard Olympus
  resource protection. Its read-only permission-profile rules remain documented
  honestly as policy/profile protection, not an immutable ACL.
- `AEGIS = GAP`: no Codex Aegis or unsafe substitute is installed.
- `RESULT_DELIVERY = SUPPORTED`: native delivery passed in the user-provided runtime evidence; missing-result recovery remains a separate `PARTIAL` capability.
- `ASK = ADAPTABLE`: native approval is used, not claimed as an identical
  per-role Olympus grant. Native requests from child threads can be visible
  outside Kael, so question centralization is `PARTIAL`.
- `RESULT_RECONCILIATION = PARTIAL`: Core requires reconciliation; successful
  delivery is observed, but recovery of a missing Codex result is not claimed as
  runtime-qualified.
- `ACTIVITY_VISIBILITY = PARTIAL`: use native Codex visibility; no equivalent
  Activity HUD is recreated.

Canonical project-local command examples (replace `<TAG>` with a published tag
that contains this installer):

```powershell
# OpenCode only (also the default)
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1 | iex

# Codex only
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness codex

# Both harnesses
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness all

# Verify only the selected managed surface (read-only)
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness opencode -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness codex -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness all -Target (Get-Location).Path -VerifyOnly
```

No generic plugin framework, automatic harness detection, or additional
harness is introduced. The v0.4.0 tag added a narrow global scope to the
existing installer only; the corrective v0.4 release line does not introduce a
new harness. A future harness may be added only through a separate adapter that
satisfies and honestly declares the Olympus capability contract.
