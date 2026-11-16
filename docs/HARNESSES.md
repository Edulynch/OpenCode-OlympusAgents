# Olympus Core and harness adapters

**Olympus Core defines what Olympus means.** A harness adapter defines how a
runtime expresses that same Core. OpenCode is the only currently supported
Olympus runtime; its declared capability limits never weaken a Core guarantee.

## Source layout

| Source | Owns |
|---|---|
| `olympus/roles/<role>.md` | One conceptual definition and responsibility boundary for each of the 11 canonical roles. Kael is the ROOT ORCHESTRATOR independently of runtime. |
| `olympus/core/identities.toml` | The single canonical full display identity for each technical role ID; the renderer derives OpenCode descriptions and HUD labels from it. |
| `olympus/core/models.toml` | The only role → model family / reasoning effort map and OpenCode identifiers. A family upgrade is one edit followed by rendering and qualification. |
| `olympus/policies/routing.md` and `orchestration.toml` | Specialist suppression, trivial fast path, direct-root ownership, bounded parallelism, and the canonical maximum of four children. |
| `olympus/policies/result-lifecycle.md` | Question barrier, completion barrier, original-result reconciliation, and no-blind-retry semantics. |
| `olympus/policies/authority.md` | Canonical ALLOW / ASK / DENY meaning. |
| `olympus/policies/maintenance-context.md` | Repository identity, contextual maintenance routing, goal-first execution, and the external-project ownership boundary. |
| `olympus/harnesses/capabilities.toml` | The OpenCode capability contract (`SUPPORTED`, `ADAPTABLE`, `PARTIAL`, `GAP`, `NOT_NEEDED`). |
| `olympus/harnesses/opencode/` | OpenCode permission/frontmatter, native role-prompt representation, default config, and activity plugin sources. |

Adapter prompt files intentionally contain runtime-specific instructions, not
second canonical role or model definitions. Changes to Olympus meaning start in
Core; update the relevant adapter representation and qualifications without
copying or deleting a Core guarantee.

## Render and check

Requires Python 3.11+ from the local standard library; no network or packages
are needed.

```powershell
python scripts/render_harnesses.py render --harness opencode
python scripts/render_harnesses.py check --harness opencode
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
| Shared contract presentation | `docs/HARNESS-CAPABILITIES.md` |

Public install/update/uninstall supports **global OpenCode only**, without
project/harness menus or CWD target selection. Kael is selected through a
reversible root `default_agent` receipt. Project-scoped OpenCode configuration,
model overrides, apply/recovery, status, and read-only doctor are separate CLI
operations; managed installation ownership is manifest/hash based and
`VerifyOnly` remains read-only. See [installation](INSTALLATION.md) for current
command scopes and effects.

## Current managed installation contract

The public installer manages global OpenCode only. Current project-scoped
configuration, model overrides, apply/recovery, status, and read-only doctor
are separate CLI operations; they do not install a project. Current manifests
use `schema_version=1`, explicit scope, and hash-own only declared resources.
An existing current-format project manifest requires `scope=project`,
`installed_harnesses=["opencode"]`, nonempty `installed_version` and
`installed_from_commit`, and the current 15-path managed inventory. A current
global manifest requires `scope=global`, exactly OpenCode,
`installed_version=local` or a release tag, nonempty `installed_from_commit`,
and a valid `default_agent_receipt`.

When an existing user-owned global config passes the permission guard, the 13
base resources are managed and the config itself remains unowned; its
`default_agent` field is reconciled using the receipt while preserving other
bytes. If neither config file exists, Olympus creates a managed config and
manages 14 resources. Both counts are current formats, not legacy inventories.
An existing `opencode.json` or `opencode.jsonc` must have a valid ordered V2
`permissions` array with an effective `external_directory * ASK` or `DENY`
fallback. Unsafe, malformed, or ambiguous config blocks before writes; Olympus
does not patch or replace a user-owned config to bypass the guard.
`VerifyOnly` remains read-only; updates and uninstall preserve user changes,
drift, and unowned files. Unsupported or incomplete formats fail closed without
conversion, adoption, or deletion. Use the matching release to remove an
unsupported older installation. No other project is scanned or modified.

The default-agent receipt records actual prior field presence/value and
reconciles `pending_set`, `committed`, and `pending_uninstall` under the existing
writer lock. Conflicts fail closed; `VerifyOnly` never writes or approves
pending state. This protects the field lifecycle, not an all-resource
transaction. See [installation](INSTALLATION.md#ownership-of-the-global-default-agent)
for the operator contract.

### Historical global-install and runtime evidence

The v0.4.0 validation tag introduced the earlier global installer foundation;
release validation failed because release-facing documentation contradicted
the integrated state, and no GitHub Release was created. The v0.4.1 validation
tag also failed because documentation described that version as upcoming; no
GitHub Release was created. Both are immutable historical validation attempts.
The corrective v0.4 line established stable release documentation. These
historical facts do not describe current public routes.

OpenCode V2.0.26 global discovery was observed on isolated Windows with the
v0.4.6 installer: 15 resources, read-only `VerifyOnly`, loader active, 12/12
then-current agents plus two controls, and configuration-level Kael selection.
The current 11-role candidate was not included; no model-backed conversation
or universal runtime compatibility is implied.

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

OpenCode's official config docs confirm global agents under
`~/.config/opencode/agents/`, `OPENCODE_CONFIG_DIR` as a custom config directory,
and later project-local config/`.opencode` sources taking precedence.

The current generated capability contract applies only to OpenCode.
V2.0.26 qualification established agent registration and configuration-level
Kael selection on that dated v0.4.6 installation, **not** a model-backed
conversation, universal V2 compatibility, or behavior of the current 11-role
candidate. The current installer selects global Kael through the reversible
receipt described above; existing sessions and project preferences are not
replaced. No interactive keybind or live permission-UI behavior is inferred
from static evidence.

A historical OpenCode V2.0.20 A/B investigation returned an empty roster. The
older diagnostic used `?directory=...` rather than `location[directory]`,
and did not establish agent-plugin activation completion. The earlier cause
remains undiagnosed; its early snapshots do not override the newer V2.0.26
acceptance. Preserve that history in [Issue #7](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/7).
The long-running `tests/global-runtime/qualify.ps1` remains a diagnostic,
not the support-state gate; it does not yet require the plugin-ready signal.
No Unix global install/runtime or live model-prompt smoke is qualified here.

Global uninstall is available only for manifest/hash-verified resources. It
leaves parent directories, base harness configuration, and project-local state
untouched.

Current static qualification entry points:

```powershell
# Automated global path/ownership/verify/update/uninstall fixtures.
pwsh -NoProfile -File ./tests/global-installer/qualify.ps1

# Historical standalone OpenCode diagnostic (not the V2.0.26 acceptance gate).
pwsh -NoProfile -File ./tests/global-runtime/qualify.ps1
```

The legacy global runtime qualifier remains outside the unified RUNTIME
profile. Its older empty-roster observation did not wait for verified plugin
activation and must not be treated as a current rejection of the V2.0.26
supported-state evidence.

The OpenCode adapter provides Kael, normal specialists, native ASK,
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
Global discovery is separately qualified above for isolated Windows V2.0.26;
no model-backed prompt is implied.

### OpenCode 2.3 subagent compatibility

OpenCode's stable [v2.3.0 release notes](https://github.com/anomalyco/opencode/releases/tag/v2.3.0)
(published 2026-11-13) state that subagents always run in the background, return
their session ID immediately, and report results when idle; a report can remain
partial while the child has its own background work pending. The Olympus prompt
source now expresses this lifecycle without assuming a background input field.

| Surface | State | Evidence and limit |
|---|---|---|
| Native child lifecycle | **ADAPT** | The adaptation is in `olympus/harnesses/opencode/agent-prompts/kael.md`; static fixtures are in `tests/completion-gates/qualify.ps1`. The earlier maintainer-reported Esc smoke below remains separate from the dated concurrent case. |
| Code Mode | **NOT_APPLICABLE** | No consumer or changed-result parser was found in the inspected Olympus adapter/role sources; Kovan's prompt and metadata also forbid `execute`. This is not a host-wide claim about Code Mode. |
| MCP OAuth / localhost | **NO_CHANGE** | The adapter does not register or manage MCP; optional host Serena access remains read-only. No authentication or provider access was tested. |
| MCP events | **NOT_APPLICABLE** | No Olympus consumer was found. |
| TUI plugin surface | **NO_CHANGE** | `olympus/harnesses/opencode/tui.tsx` uses `@opencode/plugin/tui`, `Plugin.define`, `context.ui.slot` at `session.composer.top`, and `context.data.session.list/status`; this is not a server tool-hook or fork API. See the [CLI plugin documentation](https://opencode.ai/docs/build/plugins/cli). |
| `ToolContext.signal`, `session.fork`, `execute.before`, exported `Tool` | **NOT_APPLICABLE** | No consumer was found in the inspected Olympus sources. |
| Existing permission configuration | **NO_CHANGE** | Role metadata plus `olympus/harnesses/opencode/config.jsonc` / `global-permissions.jsonc` remain in place; static hard-deny assertions are in `tests/harness-core/qualify.py`. Native permission UI and decision were **NOT_OBSERVABLE**; no live ASK/DENY qualification is claimed. |
| Interactive HUD | **DEFER** | A reactive source slot is not visual runtime evidence. HUD visibility at low TUI verbosity remains unverified; no default or plugin change was made. |
| Windows shell handoff / interruption survival | **DEFER** | This is runtime-controlled and Olympus has no replacement daemon. No handoff-survival test was performed. |
| Windows worktree setup | **NO_CHANGE** | `olympus/harnesses/opencode/worktree-setup.ps1` retains its Windows gate; it does not establish shell handoff or interruption survival. |
| Case-only rename | **NO_CHANGE** | No Olympus consumer was found; the helper in `olympus/harnesses/opencode/worktree-setup.ps1` creates paths or refuses existing ones rather than renaming. OS case-only rename behavior was not retested. |

This is a scoped compatibility assessment, not a blanket PASS or runtime
qualification.

The following candidate-checkout report is dated evidence for that recorded
checkout and its checks; it does not qualify the current runtime.

The maintainer regenerated `.opencode/agents/kael.md` in the source checkout;
the subsequent read-only OpenCode renderer check matched all 15 managed outputs.
A disposable candidate clone had previously used
HEAD `1a8e4c360c40d6f104f1792d2ab1c86a03f8e970` plus six current overlays:
`render --harness all` changed 1 output (27 unchanged), and the all-harness
read-only renderer check passed all 28 outputs. Focused gates passed
individually: safe-root
Harness Core, external-work ownership (static only), Codex static,
bootstrap-source validation, adaptive concurrency, completion gates, model
migration, preflight, question barrier, result reconciliation, role purity,
routing constraints, trivial fast path, contextual maintenance, and structured
task output. The Harness Core `WinError 2` was reproduced with the default
Python alias under the isolated profile: `sys.executable` pointed to a
nonexistent WindowsApps path beneath the fixture `USERPROFILE`, so
`subprocess.run` could not launch the renderer. Harness Core passed
`--safe-root-read-only` with the local Python 3.13 executable; no product code
change was made. Bootstrap-source validation first lacked `$TEMP\opencode`,
then passed after that fixture directory was created. The original FAST output
remains unavailable beyond its truncated report; the earlier pre-push report
recorded 10 passing tests and one optional pre-commit skip. Subsequently, one
new aggregate FAST run on the synchronized source checkout passed all 16 gates
(`FAIL=0`, `NOT RUN=0`). Its pre-push suite again passed 10 tests, with the
optional pre-commit test skipped because that tool was not installed.

The isolated Public-fixture smoke used the installed OpenCode v2.3.0 CLI.
`debug paths`, `debug config --standalone`, and `debug agents --standalone`
returned exit 0; all 10 runtime paths and all 3 config paths stayed within the
fixture, including its project config. The effective response had 18 unique
IDs: all 11 expected Olympus IDs appeared exactly once, no `aegis` appeared,
and seven additional IDs were present (`build`, `compaction`, `explore`,
`general`, `plan`, `summary`, `title`). Observed config facts were
`kael.mode=primary` and fixture `default_agent=kael`. This confirms expected-ID
presence and those config facts, not an exact 11-entry effective roster.
That isolated CLI smoke did not exercise delegation, cancellation, HUD, or
model-backed interaction. Separately, a native delegated validation session
launched FAST as one background shell job and returned its terminal result.
The parent observed the launch acknowledgement and final child report in that
first run; no matching intermediate notification was collected then.

A subsequent controlled smoke used the existing global CLI unittest suite as
real background work, without repeating FAST or adding sleeps. The parent
received a native `state="running"` partial report, retained the original child
and shell-job identities, and later received the same child's terminal report:
14 tests passed, no skips were reported, and the test sandbox was removed.
The maintainer confirmed pressing Esc while the child was active, interrupting
the parent's response, and then continuing. That UI action is user-reported
external/manual evidence, not the tester's or parent's direct UI observation.
No equivalent job was relaunched.

The tracked-change path lists matched before and after the smoke. Exact
before/after file contents were not captured, so byte-for-byte source
preservation was not established; an already-dirty worktree was not treated as
a test failure or proof of corruption. Interactive HUD and shell
handoff/interruption survival were not tested. Native permission UI and
permission decisions were NOT_OBSERVABLE. These scoped results are not a global
#142 compatibility claim.

### Dated follow-up (2026-11-14)

The test source checkout was clean at HEAD
`d154a4ecb7d40b7e5a246316997c5bf75d4c6638` before and after this native case.
The installed local CLI reported `opencode v2.3.0`;
`opencode api get /api/info` reported server version `2.3.0` at
`2026-11-14T04:07:56.0491244Z`. The official
[v2.3.0 release](https://github.com/anomalyco/opencode/releases/tag/v2.3.0)
was published 2026-11-13, and the public
[@opencode/cli latest registry entry](https://registry.npmjs.org/@opencode%2fcli/latest)
reported `2.3.0`. GitHub's generic `/releases/latest` pointed to legacy v1.19.5
and was not used as V2 version authority. These are dated version observations,
not binary-signature verification, an upgrade, or a claim that v2.3.0 remains
the latest stable 2.x; recheck stable 2.x before any future runtime execution.

For the new native concurrency case, Kael launched two direct Nox children
together and received both launch acknowledgements before either terminal
result; a separate static Veyra assessment supplied the used-surface matrix. The parent kept
the original child/job identities while A was pending; B's failure report
arrived before A's final result, and the parent retained A's pending state
until that same child completed. There was no parent polling, sleep, or
relaunch. A ran
`python -B -m unittest discover -s tests/harness-core -p test_global_cli.py -v`
as one offline background shell job. Its initial report was still running;
the same child later completed with exit 0, 14 tests passed, and no skips. Its
task-local temporary directory was removed after subprocesses ended. The
process-local temporary environment did not alter HOME, USERPROFILE, or auth.

B's original foreground stimulus was
`python -B -c "import sys; print('OA142_EXPECTED_CHILD_COMMAND_FAILURE'); sys.exit(7)"`.
It printed the marker once and requested child exit 7, but the native tool
returned exit 1. That original check failed its exact exit-code expectation;
it does not establish a product bug or native-session crash. Only after all original
results were terminal, one corrected calibration captured PowerShell's
`$LASTEXITCODE`, emitted `OA142_NATIVE_EXIT=7`, and returned tool exit 7. That
calibration passed as an expected child-command failure only; it was not
another concurrency run and A was not rerun. The original failure remains part
of the record.

**Disposable PowerShell calibration only; this intentionally exits that
process with 7. Do not paste it into the maintainer's interactive parent shell.**

```powershell
$ErrorActionPreference = 'Stop'; python -B -c "import sys; print('OA142_EXPECTED_CHILD_COMMAND_FAILURE'); sys.exit(7)"; $nativeExit = $LASTEXITCODE; Write-Output "OA142_NATIVE_EXIT=$nativeExit"; exit $nativeExit
```

This case establishes the observed partial/final result correlation and
handling of the concurrent failed report only for these actors. It does not
prove forced-session crash/cancellation behavior, HUD visibility, Windows
shell-handoff survival, or native permission UI/approval; the earlier Esc
action remains separately identified above as maintainer-reported evidence.

**Decision and reversal boundary:** retain the already-merged minimal native
lifecycle adaptation; this evidence indicates no further production change.
The deferred and not-applicable surfaces prevent a global compatibility
claim. If a proven regression later requires reversal, separately authorize a
normal workflow to revert only lifecycle delta
`3af6d38e8f44da62b53c1e713ac65f533696f588` (canonical Kael source, its matching
generated output, focused assertions, and documentation). Preserve the
independent Git-environment fix
`26140336fb6d6ba98251dd804fb94d230c4b0da0`, PRs #149/#150, and user-config
ownership. No reversal or broader renderer/global-write authority is implied
here.

