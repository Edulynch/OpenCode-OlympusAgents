# Olympus Core and harness adapters

**Olympus Core defines what Olympus means.** A harness adapter defines how a
runtime expresses that same Core. The officially supported harnesses are
OpenCode and Codex; capability gaps are explicit and never weaken a Core
guarantee.

## Source layout

| Source | Owns |
|---|---|
| `olympus/roles/<role>.md` | One conceptual definition and responsibility boundary for each of the 11 canonical roles. Kael is the ROOT ORCHESTRATOR independently of runtime. |
| `olympus/core/identities.toml` | The single canonical full display identity for each technical role ID; renderers derive OpenCode descriptions/HUD and Codex descriptions/root heading from it. |
| `olympus/core/models.toml` | The only role → model family / reasoning effort map, plus each family's OpenCode and Codex identifier. A family upgrade is one edit followed by rendering and qualification. |
| `olympus/policies/routing.md` and `orchestration.toml` | Specialist suppression, trivial fast path, direct-root ownership, bounded parallelism, and the canonical maximum of four children. |
| `olympus/policies/result-lifecycle.md` | Question barrier, completion barrier, original-result reconciliation, and no-blind-retry semantics. |
| `olympus/policies/authority.md` | Canonical ALLOW / ASK / DENY meaning. |
| `olympus/policies/maintenance-context.md` | Repository identity, contextual maintenance routing, goal-first execution, and the external-project ownership boundary. |
| `olympus/harnesses/capabilities.toml` | The two-harness capability contract (`SUPPORTED`, `ADAPTABLE`, `PARTIAL`, `GAP`, `NOT_NEEDED`). |
| `olympus/harnesses/opencode/` | OpenCode permission/frontmatter, native role-prompt representation, default config, and activity plugin sources. |
| `olympus/harnesses/codex/` | Codex-native role-prompt representation, root instructions, project config, and permission profile. Contextual Olympus maintenance remains a declared capability gap. |

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
expected bytes in memory, reports missing/drifted outputs and known retired
OpenCode outputs, creates no temporary repository files, and exits nonzero on
drift. Rendering refuses to overwrite stale retired paths; remove only verified
generated outputs first. Generated files contain
a parser-safe generated marker; **edit Core/adapter source, not generated
outputs**.

## Generated outputs

| Adapter | Managed/generated outputs |
|---|---|
| OpenCode | `.opencode/agents/**`, `.opencode/plugins/olympus-activity/**`, `opencode.jsonc` |
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
| OpenCode | Fresh CLI child `opencode debug paths` reported home/config/data/cache/state/tmp/log within isolated HOME, four XDG roots, and TEMP. `OPENCODE_CONFIG_DIR` selects the config layer only; it is not a sandbox for all global paths. | Official current docs specify `~/.config/opencode`; no Unix runtime was available. | Official agent/plugin docs identify `~/.config/opencode/agents/` and `~/.config/opencode/plugins/`; global commands use the same config-root `commands/` convention. User-owned `opencode.json` / `opencode.jsonc` is not overwritten. An empty global config root receives a minimal manifest-owned `opencode.jsonc` with `external_directory * ASK`; no global default-agent change is made. |
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

The installer remains Windows-qualified. `-Scope global` does not overwrite
user-owned configuration, records `scope = global`, `installed_harnesses`,
`installed_version`, and hash-owned `managed_files`, and `-VerifyOnly` verifies
one scope at a time. Codex base `config.toml` remains untouched. OpenCode's
global `opencode.json` or `opencode.jsonc`, **if already user-owned**, remains
untouched, but the installer must validate an ordered V2 `permissions` array
with an effective `external_directory * ASK` or `DENY` fallback. It refuses an
unprotected, malformed, or ambiguous existing global config **before writing**
OpenCode resources, with `GLOBAL_EXTERNAL_GUARD_UNSAFE`. The user must fix the
config; the installer does not silently patch it. If neither global config
exists, it creates a minimal `opencode.jsonc` as a **14th managed resource**
(11 agents, 2 plugin files, 1 guard), without setting a default agent or
changing models/MCP configuration. This guard is hash-verified on update and
`VerifyOnly`, and removed on uninstall only while unmodified. If a user edits
it, verification and uninstall fail safely rather than deleting their edits.
With a pre-existing safe user config, only the original 13 OpenCode assets are
manifest-owned. Updates refuse drift, preserve unrelated user config, and do not remove
project-local installs; the explicit migration result is `GLOBAL_INSTALLED
PROJECT_LOCAL_REMAINS_AS_OVERRIDE`. A project-local Olympus manifest in the
current Git root is reported, including version/hash drift. Other repositories
are not scanned or modified. Before the first guard write, the installer persists
an Olympus-only `olympus/opencode-guard-pending.json` ownership intent. If interrupted
before the manifest is committed, the next installation reclaims **only** an
exact-hash guard, rejects altered bytes, and removes the intent after the
manifest is safely written. During that same pending install, already-written
managed agents/plugins may roll forward **only** if their bytes match the
current canonical source exactly; an unknown edit or missing retired file
still requires manual reconciliation, preserving all original bytes. The guard
itself is created with exclusive `CreateNew` semantics, so a `.jsonc` config
appearing after preflight cannot be overwritten. The installer also rechecks
the competing `.json` name around manifest publication and refuses to report
success if it appears. A collision may leave the ownership intent pending and
must be resolved manually after preserving the user config. The intent and a
matching hash prove recoverable bytes, not cryptographic authorship if another
process creates **identical** bytes between intent and guard creation; avoid
concurrent global config writers during installation or recovery.
`VerifyOnly` and uninstall fail closed while an
unreconciled intent exists; run the regular installer to recover first. This
guard-specific recovery does not claim full transactionality for all global
agent/plugin resources.

The read-only global CLI does not silently report `no_changes` for a historical
13-resource inventory with no global config: it proposes the missing managed
guard. It blocks on an unsafe or ambiguous user config, while still preserving
safe JSON/JSONC user configs outside Olympus ownership. Static global installer
qualification passes, but
runtime discovery is a separate contract:

| Harness | Global support | Runtime evidence and blocker |
|---|---|---|
| OpenCode | **SUPPORTED — Windows V2.0.26 (isolated)** | Historical real `v0.4.6` global install: 15 managed resources; `VerifyOnly` read-only PASS; `opencode.config.agent` `active`; 12/12 agents plus 2/2 independent controls. The current 11-role candidate has not yet been included in that runtime evidence. [Issue #7 acceptance](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/7#issuecomment-6106396436). |
| Codex | **SUPPORTED** | The user-provided Codex runtime evidence classifies `CODEX_GLOBAL_RUNTIME: SUPPORTED`. It was accepted as supplied and not re-run during this continuation; contextual Olympus maintenance and `DENY` remain declared gaps. |

**Permission precedence limit:** V2 resolves the **last matching rule**, not
the narrowest resource. A global-user specific `external_directory DENY`
followed by a project `external_directory * ASK` can therefore resolve to ASK;
this existing project-configuration behavior was **not** introduced or fixed
by the agent-level rules change in PR #121. Conversely, a later path-specific
DENY remains effective and Olympus agents do not append their own wildcard ASK
over it. User-configured exceptions may still permit deliberate external
access. `policies.tool.use` hard-deny is a separate mechanism. Shell execution
has host authority and is not a filesystem sandbox. Static fixture tests cover
both orderings, global-only ASK versus specific DENY, user-config preservation,
and failure/ownership cases; they do **not** establish a live native global-only
permission prompt or denial. Native global-only qualification remains required
before making a blanket runtime security claim. An optional
`tests/global-installer/native-permission-api-smoke.ps1` probes the isolated V2
server permission API: it records native ASK, replies programmatically with
`reject`, and checks automatic specific DENY **without interactive dialogs**.
The default invocation checks permission-engine behavior only; the Windows CI
workflow supplies `-NativeToolRead` and also triggers an actual OpenCode `read`
against synthetic external sentinels with a local deterministic model fixture.
That native tool-read check has observed a denied read and no sentinel-content
exposure under its isolated settings, **not** a human-observed rejection,
an interactive TUI prompt, or a general alternative-tool/shell sandbox claim.
See the official
[V2 permissions](https://opencode.ai/docs/permissions/) and
[server permission API](https://opencode.ai/docs/api) references.

OpenCode's official current config docs confirm global agents under
`~/.config/opencode/agents/`, `OPENCODE_CONFIG_DIR` as a custom config directory,
and later project-local config/`.opencode` sources taking precedence. Codex's
current docs confirm global instructions under `$CODEX_HOME/AGENTS.md` (unless
`AGENTS.override.md` exists), project instructions layered after the global
instructions, custom agents under `$CODEX_HOME/agents/`, and profile files at
`$CODEX_HOME/<profile>.config.toml`. These path/precedence rules remain
separate from the runtime qualification recorded above. A global install plus
unrelated project files and the installer-owned project override/migration paths are covered by
isolated installer tests; no runtime semantic merge is claimed.

The generated `GLOBAL_RUNTIME_DISCOVERY` capability is `SUPPORTED` for both
harnesses, on different evidence: OpenCode was tested in an isolated Windows
V2.0.26 instance; Codex uses previously supplied global runtime PASS evidence.
OpenCode qualification established agent registration and configuration-level
Kael selection, **not** a model-backed conversation, universal V2 compatibility,
or automatic replacement of a user's default. The installer preserves any
pre-existing safe user-owned global `opencode.json` / `opencode.jsonc`, or
creates a minimal managed guard if neither exists. For interactive
selection, start `opencode --standalone` (or `opencode` with your usual
service) and choose visible primary **Kael** using the V2 agent list
(**Ctrl+X**, then **A** by default) or cycle agents with **Shift+Tab**.
These are configurable keybinds; see the [official OpenCode V2
keybinds](https://opencode.ai/v2/docs/cli/keybinds). Alternatively, opt in
to `"default_agent": "kael"` in your own global
`~/.config/opencode/opencode.jsonc` for new sessions; project-local
`opencode.jsonc` already sets Kael when the project configuration loads.
An existing session's agent selection is not overwritten. The operator's
V2 CLI rejected the previously documented top-level agent-selection flag;
the keyboard instructions are documented upstream but are not claimed as
a separately executed interactive qualification here.

A historical OpenCode V2.0.20 A/B investigation returned an empty roster. The
older diagnostic used `?directory=...` rather than `location[directory]`,
and did not establish agent-plugin activation completion. The earlier cause
remains undiagnosed; its early snapshots do not override the newer V2.0.26
acceptance. Preserve that history in [Issue #7](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/7).
The long-running `tests/global-runtime/qualify.ps1` remains a diagnostic,
not the support-state gate; it does not yet require the plugin-ready signal.
No Unix global install/runtime or live model-prompt smoke is qualified here.

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

# Historical standalone OpenCode diagnostic (not the V2.0.26 acceptance gate).
pwsh -NoProfile -File ./tests/global-runtime/qualify.ps1
```

The legacy global runtime qualifier remains outside the unified RUNTIME
profile. Its older empty-roster observation did not wait for verified plugin
activation and must not be treated as a current rejection of the V2.0.26
supported-state evidence.

The OpenCode project adapter provides Kael, normal specialists, native ASK,
hard DENY, Activity HUD, models, permissions, and installer-managed resources.
Contextual Olympus maintenance uses the same Kael workflow; the current 11-role
candidate requires its own runtime evidence. The OpenCode adapter does not
register any MCP server. MCP is optional user/host configuration: Olympus does
not require an MCP CLI on `PATH`, install Serena, or manage the user's MCP
settings. If a user or host separately makes Serena tools available, the
canonical Olympus configuration keeps their grants limited to read-only
symbol-navigation tools for Kael, Veyra, and Kovan, with the global `serena_*`
denial and mutation-tool defenses preserved. These conditional grants are not a
Serena prerequisite or a guarantee against host-level MCP failures; normal
non-MCP tools remain subject to their configured permissions.
Global discovery is separately
qualified above for isolated Windows V2.0.26; no model-backed prompt is implied.
Codex installation does not imply capability parity: Codex multi-agent and
result delivery are supported, ALLOW is supported, ASK is adaptable, DENY and
contextual Olympus maintenance remain gaps, and activity visibility is partial/basic. See the generated
[capability contract](HARNESS-CAPABILITIES.md).

Codex uses its root thread as Kael, custom specialists, per-role model/effort,
native multi-agent tools, bounded fan-out/fan-in, child result delivery, and
native activity visibility. Current user-provided runtime evidence records
Kael root, Kael→Veyra, Kovan→Nox functional work, four-child fan-out/fan-in,
concurrency of at least two, result delivery, ALLOW, and native ASK approval
as passing/confirmed; these smokes were **not rerun** during modularization.
`tests/codex/validate_profile.py` remains static qualification only.

The direct Codex qualifier keeps its no-argument combined behavior. Its internal
`--mode static` runs source/profile assertions without locating or invoking the
Codex CLI; it omits the renderer check already exercised by safe Harness Core
qualification. `--mode catalog` runs only `codex debug models --bundled`; when
the CLI is absent it prints `CODEX_MODEL_CATALOG: NOT RUN (Codex CLI unavailable)`
and exits 2. The contributor facade recognizes that explicit prerequisite result
as `NOT RUN`; an unexplained child exit 2 is a failure, not a pass or skip.
Neither mode performs an interactive Codex smoke. The contributor profile entry
point and its FAST/FULL/RUNTIME boundaries are documented in
[Development & qualification](DEVELOPMENT.md#unified-contributor-profiles-issue-11).

## Declared Codex gaps

- `DENY = GAP`: Codex does not currently provide equivalent hard Olympus
  resource protection. Its read-only permission-profile rules remain documented
  honestly as policy/profile protection, not an immutable ACL.
- `CONTEXTUAL_OLYMPUS_MAINTENANCE = GAP`: no Codex support is claimed for the contextual Olympus maintenance workflow.
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
