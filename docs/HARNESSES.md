# Olympus Core and harness adapters

**Olympus Core defines what Olympus means.** A harness adapter defines how a
runtime expresses that same Core. OpenCode is the only currently supported
Olympus runtime; adapter limits describe representation and evidence, never
weaken or redefine Core policy.

## Source layout

| Source | Owns |
|---|---|
| `olympus/roles/<role>.md` | One conceptual definition and responsibility boundary for each of the nine canonical roles. Kael is the root orchestrator; Atlas is a separate read-only primary. |
| `olympus/core/identities.toml` | The single canonical full display identity for each technical role ID; the renderer derives OpenCode descriptions and HUD labels from it. |
| `olympus/core/models.toml` | The only role → model family / reasoning effort map and OpenCode identifiers. A family upgrade is one edit followed by rendering and qualification. |
| `olympus/policies/routing.md` and `orchestration.toml` | Specialist suppression, trivial fast path, direct-root ownership, bounded parallelism, a default ceiling of four children, and a user-selected prompt ceiling of 1–8 per primary session. |
| `olympus/policies/result-lifecycle.md` | Question barrier, completion barrier, original-result reconciliation, and no-blind-retry semantics. |
| `olympus/policies/authority.md` | Canonical ALLOW / ASK / DENY meaning. |
| `olympus/policies/maintenance-context.md` | Repository identity, contextual maintenance routing, goal-first execution, and the external-project ownership boundary. |
| `olympus/harnesses/capabilities.toml` | The OpenCode capability contract (`SUPPORTED`, `ADAPTABLE`, `PARTIAL`, `GAP`, `NOT_NEEDED`). |
| `olympus/harnesses/opencode/` | OpenCode permission/frontmatter, native role-prompt representation, default config, and activity plugin sources. |

Adapter prompt files intentionally contain runtime-specific instructions, not
second canonical role or model definitions. Changes to Olympus meaning start in
Core; update the relevant adapter representation and qualifications without
copying or weakening Core policy.

## Render and check

Requires Python 3.11+ from the local standard library; no network or packages
are needed.

```powershell
python scripts/render_harnesses.py render --harness opencode
python scripts/render_harnesses.py check --harness opencode
python tests/harness-core/qualify.py
```

`render` is deterministic and idempotent. `check` is read-only: it compares
the current generated inventory, reports missing or changed outputs, creates
no temporary repository files, and exits nonzero on a mismatch. Neither
command reports or removes retired outputs outside that inventory. Before
removing an old file by hand, verify that Olympus generated it. Generated
files contain a parser-safe marker; **edit Core/adapter source, not generated
outputs**.

For detached candidate generation, `--output-root` relocates every managed
output while `--root` (or the script checkout by default) remains the source:

```powershell
python -B scripts/render_harnesses.py render --harness opencode --output-root D:\staging\olympus-candidate
python -B scripts/render_harnesses.py check --harness opencode --output-root D:\staging\olympus-candidate
```

Use an isolated, project-controlled staging directory that is not loaded by
OpenCode. The option rejects overlapping roots and known symlink, reparse-point,
and hardlink redirects, but path inspection cannot prove the directory is
inactive or prevent concurrent replacement; keep it operator-owned. `check`
remains read-only, and candidate files are not activated or installed.
`--output-root` applies only to `render` and `check`, not to `kael`.

## Generated outputs

| Adapter | Managed/generated outputs |
|---|---|
| OpenCode | `.opencode/agents/**`, `.opencode/commands/olympus.ultra.md`, `.opencode/commands/olympus.performance.md`, `.opencode/commands/olympus.performance-ultra.md`, `.opencode/plugins/olympus-activity/**`, `.opencode/scripts/worktree-setup.ps1`, `opencode.jsonc` |
| Shared contract presentation | `docs/HARNESS-CAPABILITIES.md` |

The renderer currently emits 16 OpenCode runtime outputs: nine role agents,
three commands, two Activity plugin files, the worktree setup script, and
`opencode.jsonc`. It renders the capability matrix separately. Verify the
current generated inventory with the read-only
`python -B scripts/render_harnesses.py check --harness opencode`; renderer
output membership is not itself an installer ownership declaration. Staged
renderer outputs and manifest-owned installation resources are distinct
inventories.

### Core-to-prompt synchronization

The renderer synchronizes the canonical role roster, display identities, and
per-role model identifiers/effort into OpenCode role metadata; it also injects
the Core `max_children` value and derived parallelism guidance into prompts.
Kael's prompt receives the complete canonical maintenance-context policy, the
TFR section from `routing.md`, and the coding-behavior section; Kovan's prompt
receives the coding-behavior section.

The renderer does not semantically translate every Core policy. Operational
instructions in the prompts—including authority and result-lifecycle/routing
behavior not covered by those explicit substitutions—must be kept manually in
sync with Core. A rendered prompt or a `SUPPORTED` status is not proof that
OpenCode enforces every instruction.

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
`installed_from_commit`, and the current 13-path managed inventory. A current
global manifest requires `scope=global`, exactly OpenCode,
`installed_version=local` or a release tag, nonempty `installed_from_commit`,
and a valid `default_agent_receipt`.

When an existing user-owned global config passes the permission guard, the 14
base resources (nine agents, three commands, and two Activity files) are
managed and the config itself remains unowned; its
`default_agent` field is reconciled using the receipt while preserving other
bytes. If neither config file exists, Olympus creates a managed config and
manages 15 resources. The global manifest excludes the generated worktree
setup script. Both counts are current formats. All three command files
are global-only and excluded from the 13-path project inventory; project
`config apply` does not create duplicate command files. Old role/command
inventories, unsupported legacy manifests, and receipt-less global manifests
are rejected rather than migrated or adopted. `--force` does not bypass those
checks. Read-only `olympus doctor` explains the reported state; it does not
migrate or repair it. For an unsupported older installation, uninstall with the
Olympus version that created it, then install the current version. Do not
manually delete files or receipts.

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

The OpenCode adapter represents Kael, normal specialists, native ASK,
hard DENY, Activity HUD, models, permissions, and installer-managed resources
through the mechanisms and evidence limits in the [capability table](#capability-evidence).
Contextual Olympus maintenance uses the same Kael workflow; the current
nine-role roster requires its own runtime evidence. The OpenCode adapter does not
register any MCP server. MCP is optional user/host configuration: Olympus does
not require an MCP CLI on `PATH`, install Serena, or manage the user's MCP
settings. If a user or host separately makes Serena tools available, the
canonical Olympus configuration keeps read-only symbol-navigation grants for
Veyra and Kovan; Kael has a role-specific `serena_*` DENY because the minimal
global permission source has no Serena default denial. These conditional grants
are not a Serena prerequisite or a guarantee against host-level MCP failures.
Global discovery is separately qualified above for isolated Windows V2.0.26;
no model-backed prompt is implied.

### Kael and Atlas native permission boundaries

Kael's metadata denies direct repository reads/searches, shell/Git, tests,
research, and edits; Kael owns decisions, routing, reconciliation, and
completion, not direct technical execution. Its seven child roles are Veyra,
Kovan, Nox, Vera, Helios, Talos, and Thales. Atlas is a separate read-only
primary: its metadata permits scoped repository reads and declares shell and
execute as native ASK. Atlas's prompt limits shell to bounded inspection and
diagnostics; it never authorizes mutation, Git writes, tests, or external
actions. Atlas may delegate only to Veyra, Helios, Talos, and Thales.

Native ASK is the consent point, not prior approval or a sandbox. Shell retains
host authority and is not an OS sandbox. Effective access still depends on
shared, project, user, and host/system permission rules. Static source and
renderer checks describe configured rules only; they do not establish tool
execution, permission UI or decisions, or user/account state.

**Historical Issue #177 qualification (OpenCode V2.3.2; 2026-11-22).** Nox's
independent isolated run of `pwsh -NoProfile -File ./tests/authority/qualify.ps1 -QualificationSlice Runtime` reported `AUTH14_OPENCODE_EFFECTIVE_RULES PASS` and
fixture cleanup PASS; this evaluated loaded rules only (Kael edit DENY, shell
DENY except the exact root probe, Serena 6/6 DENY, ten named specialists ALLOW
and unlisted DENY, inherited external-directory ASK without a Kael-local
override, and Kovan ordinary edit ALLOW/project-plugin ASK/Activity DENY), not
tool execution.
**USER_REPORTED:** the renderer changed one managed Kael output, left 17
unchanged, and `HARNESS_RENDER_CHECK: PASS` (18 managed); in a separate
disposable Windows project, the TUI showed Veyra start and finish the read-only
“Leer primer encabezado README” task before Kael reported the line-1 heading
`# Prueba aislada del issue 177` and said no file was modified. This is one
delegation/completion/answer observation—not independent filesystem-integrity
evidence, a denied-action attempt, ASK UI/decision evidence, an observed root
shell probe, or fresh global-scope evidence.

## OpenCode 2.4.0 role tool boundaries

The canonical role metadata denies `automation_*` and `browser`, each on
resource `*`, for Kael, Kovan, Nox, Orin, Vera, and Veyra. Argus, Atlas, Helios,
Talos, and Thales already deny every action on every resource in their role
metadata; they need no duplicate tool-specific rules. OpenCode V2.4.0 maps a
namespace/tool pair to its effective `namespace_tool` permission ID, so
`automation_*` covers `automation_create`, `automation_list`,
`automation_pause`, `automation_resume`, and `automation_delete`, including
Code Mode calls through those tools. The browser tool uses the `browser` action
([OpenCode browser documentation](https://opencode.ai/docs/tools#browser)).

These are Olympus role-level native denials only. They do not disable a user's
manual `/automation` command, block browser use by other agents, or edit root,
user, or profile permissions. The Authority source/matcher checks evaluate
both routes with last-matching-rule semantics; the isolated runtime check
requires each of the 11 expected Olympus IDs exactly once, permits additional
OpenCode built-ins, and reports each protected action's effective decision.
Static source checks and isolated fixtures are not evidence of the native
permission UI, human approval/rejection, or an arbitrary user's effective
profile.

**OpenCode V2.4.0 evidence (2026-11-23).** The bundled Windows CLI was first
run at clean source commit `08e328264bbf6f3e66f90d8c6f3d47a210075168`:
all three baseline invocations exited 0.

- Before the role-metadata edits, `tests/authority/qualify.ps1
  -QualificationSlice Runtime` passed `AUTH14_OPENCODE_EFFECTIVE_RULES`.
  This baseline checked existing Kael/Kovan effective rules, not uniqueness
  of all 11 Olympus IDs or the new automation/browser denials.
- `tests/global-installer/native-permission-api-smoke.ps1 -NativeToolRead`
  observed an ASK case rejected programmatically through the API, automatic
  specific DENY, and a denied fixture read with no sentinel exposure. This was
  not an interactive permission UI or human decision.
- `tests/worktree-activation/native-smoke.ps1` exited 0 after validating two
  native worktrees, their valid manifests, and `default_agent=kael`; it did not
  validate the full role roster or permission UI.

After the source edits, Authority Runtime ran on a disposable, freshly rendered
candidate and exited 0 with `AUTH14_OPENCODE_EFFECTIVE_RULES PASS` and owned
fixture cleanup PASS. It found all 11 Olympus IDs exactly once, plus seven
additional IDs, and effective DENY for all 66 checks (the five listed
`automation_*` actions and `browser` across the 11 roles). Existing Kael
shell/edit/root-only probe/named-subagent assertions and Kovan permission
assertions also passed. `/api/integration` verified response shape and
directory only; it did not establish plugin activation/readiness.

Optional direct Code Mode/catalog visibility (including blank-profile checks)
and browser Desktop invocation were **NOT RUN** and are not required for closure.
No runtime tool-catalog/availability or browser-UI assertion is made. The
effective DENY results are permission-rule evidence only; they do not establish
that a protected action was invoked or blocked at the tool boundary, or that a
tool is absent from the runtime catalog. Native permission UI and human decisions
were not observed and remain evidence limits, not closure gates. Interactive HUD
evidence is limited to the
user-reported Windows observation below; it does not qualify OpenCode 2.4 runtime
compatibility. Parent/child report delivery has only the separate partial
observation recorded below. Docker, real installation, credentials, and
user-global automation/browser settings were not touched. The deterministic
local fake provider was not repurposed, and absence of a Desktop run is not a
product failure finding. The HUD candidate keeps a direct child visible while
its session is running or while the optional reactive root-tree job list reports
supported active work owned by that child's represented tree. Static source and
Node-test evidence remains distinct from the bounded visual observation.
Preserve authentication and user-global automation/browser settings.

The read-only `python -B scripts/render_harnesses.py check --harness opencode`
historically exited 1: exactly these six tracked generated agents were stale:
`.opencode/agents/{kael,kovan,nox,orin,vera,veyra}.md`. No other generated
output mismatch was reported. **USER_REPORTED:** a subsequent manual
`python -B scripts/render_harnesses.py render --harness opencode` reported
`HARNESS_RENDER: PASS (opencode; wrote 6 changed output(s), 12 unchanged)`,
then `python -B scripts/render_harnesses.py check --harness opencode` reported
`HARNESS_RENDER_CHECK: PASS (opencode; 18 managed output(s); read-only)`.
This records the supplied transcript, not an independent rerun or an
unreported exit code. That pass predates the current canonical HUD edits and is
not current renderer evidence.

**USER_REPORTED — later manual renderer synchronization after the final HUD
source change.** `python -B scripts/render_harnesses.py render --harness opencode`
reported `HARNESS_RENDER: PASS (opencode; wrote 2 changed output(s), 16 unchanged)`,
followed by
`python -B scripts/render_harnesses.py check --harness opencode` reporting
`HARNESS_RENDER_CHECK: PASS (opencode; 18 managed output(s); read-only)`. This
supplied transcript, not an independent rerun or a separately supplied exit
code, supersedes the earlier stale-output note as current renderer evidence.
This documentation task did not render or edit generated outputs.

**USER_REPORTED — separate manual TUI trace; exact runtime version not
supplied.** A screenshot showed the Activity HUD `1 active` with `Nox — The
Tester` and task `Validar documentación en segundo plano`, plus the native
footer `1 subagent`. Kael said Nox's session had started in that frame, but the
shell-job launch was not yet confirmed. This is a partial visual observation;
it does not show either the HUD or native subagents view during the critical
interval when a shell job was active and the child idle. Later pasted output
from the same conversation said `Nox finished`; Kael reported that Nox ran
`python -B scripts/check_docs.py` in a native background job and received the
final report, and the checker printed PASS after 102 Markdown files with six
historical attachments excluded. Nox's transcript identifies two distinct
background shell jobs: it reports the native launch and terminal notification
for the original, and a terminal notification for the accidental duplicate;
both reportedly printed the same PASS output and finished. Thus exactly-once
execution was historically recorded **FAILED** for this trace. This job
attribution and Kael's receipt of the Nox report are user-supplied transcript
evidence, not independently verified from raw tool results. Neither job's
terminal command exit code or raw tool result was supplied, so exit status
remains unknown; no cause for the duplicate is inferred. The conversation
summary reports no jobs/results pending, and Nox reports the same tracked-path
status before and after; that does not establish byte-for-byte integrity. This
trace does not establish the exact OpenCode version and is not a check performed
by this documentation task.

**USER_REPORTED — later before-change Windows TUI captures; exact version not
shown.** Both captures initially show Nox as `Running`. After Nox yields with
the original background job, the root first receives a `Nox finished` notice
containing only the launch ID; in the following same-root view, the Olympus HUD
is absent while native Subagents still lists Nox without `Running`. Later, the
original shell completes with `HUD_PROBE_END`, and Nox's report correlates the
original shell ID `sh_20e5075be001YhNYEPUanLgJym`. A second `Nox finished`
notice is the child's resumption result, not evidence of a second shell launch.
The root's final account says one job and no relaunch; the native shell exit
value was not exposed, and the native pane later showed no active subagents.
These captures motivate retaining the idle child row while its original native
work remains active. They do **not** show a Shell running pane in the critical
frame, establish the exact OpenCode version, or expose a native shell exit
code. At that point the candidate UI had not yet been rerun; these before-change
captures do not qualify its behavior. The earlier two reported duplicate events
remain historical; their relation to these captures and their causality are
unconfirmed.

**USER_REPORTED — post-change Windows TUI visual check PASS for this one
scenario only; exact OpenCode version not shown.** Four screenshots from the
exact worktree show one probe sequence. After
the first `Nox finished` progress/yield notice, while the root remained pending
on the original shell job, the same root frame shows the Olympus HUD `1 active`
Nox row and a native active Subagents row for Nox without a `Running` label. A
companion child frame shows one Background shell command,
`Start-Sleep -Seconds 45; Write-Output 'HUD_PROBE_END'; exit 0`, and a progress
report with the original job ID. After the second child notice, a later root
frame shows the terminal report for that original job with `HUD_PROBE_END`; the
root reports no active task work and the HUD no longer shows Nox. The repeated
progress report is for the same ID, not a second shell call. This one scenario
supports the row remaining visible while the yielded child has pending work and
clearing after completion. The screenshots do not show a Shell pane while the
job is running or a separate native Subagents pane at the final frame; no exact
runtime version or native shell exit is shown. The command's `exit 0` text is
not an observed shell exit status. This does not establish a general fix for
earlier duplicate events or broader runtime compatibility.

## Capability evidence

Each row separates adapter representation, the evidence that supports the
recorded status, and the material limit on that evidence. Static checks establish
source/renderer contracts, not live model behavior. Runtime observations below
are limited to their stated OpenCode version, platform, and scenario.

| Capability ID | Mechanism | Evidence | Material limit |
|---|---|---|---|
| `ROOT_ORCHESTRATOR` | Canonical Kael role is rendered with OpenCode primary-agent metadata and selected as the root default agent. | Core/config assertions in [`tests/harness-core/qualify.py`](../tests/harness-core/qualify.py); Windows OpenCode V2.0.26 selection in [the historical record](#historical-global-install-and-runtime-evidence) and V2.3.0 selection in [the compatibility record](#opencode-23-subagent-compatibility). | Agent registration and selection do not establish model compliance or a correct response. |
| `CUSTOM_SPECIALISTS` | Renderer requires metadata and a prompt for every canonical role; OpenCode exposes the named agent definitions. | Renderer/roster checks in [`tests/harness-core/qualify.py`](../tests/harness-core/qualify.py); isolated Windows OpenCode V2.3.0 observed 11 Olympus IDs among 18 effective IDs in [the recorded case](#opencode-23-subagent-compatibility). | The additional host IDs were present; roster presence does not establish that every specialist can be delegated successfully. |
| `PER_ROLE_MODEL` | Canonical role-to-family mappings render an OpenCode model identifier into each role's metadata. | [`models.toml`](../olympus/core/models.toml) and deterministic per-role checks in [`tests/harness-core/qualify.py`](../tests/harness-core/qualify.py). | No general provider access, model availability, or live per-role model selection is established. |
| `PER_ROLE_REASONING` | Canonical effort values render as OpenCode `#variant` metadata for each role. | [`models.toml`](../olympus/core/models.toml) and deterministic per-role metadata checks in [`tests/harness-core/qualify.py`](../tests/harness-core/qualify.py). | A rendered variant does not establish that a provider supports or honors it. |
| `MULTI_AGENT` | Kael's instructions use OpenCode native direct child sessions; Olympus does not supply a separate scheduler. | Two concurrent direct Nox children were observed on Windows OpenCode V2.3.0 in [the dated case](#dated-follow-up-2026-11-14). | This scoped observation is not universal evidence for execution, fan-out, cancellation, or service availability. |
| `BOUNDED_PARALLELISM` | Core `max_children=4` is injected into Kael's prompt as a per-root-session ceiling with adaptive guidance. | [`orchestration.toml`](../olympus/policies/orchestration.toml), [`render_harnesses.py`](../scripts/render_harnesses.py), and the static [`adaptive-concurrency` qualification](../tests/adaptive-concurrency/qualify.ps1); two concurrent children were observed in [the V2.3.0 case](#dated-follow-up-2026-11-14). | The ceiling is prompt guidance, not scheduler enforcement, a cross-root quota, or an OS mutex; observing two children did not test ceiling enforcement. |
| `QUESTION_CENTRALIZATION` | Core result-lifecycle policy and Kael's prompt centralize user questions through the root orchestrator. | Static/synthetic [`question-barrier` qualification](../tests/question-barrier/qualify.ps1) and the [qualification limits](DEVELOPMENT.md#question-barrier). | A live question race has not been demonstrated. |
| `COMPLETION_BARRIER` | Core completion policy and Kael's prompt require original child results to be reconciled before completion. | Static/synthetic [`completion-gates` qualification](../tests/completion-gates/qualify.ps1); a pending original child was awaited through its terminal report in [the V2.3.0 case](#dated-follow-up-2026-11-14). | The dated case does not establish behavior for every child crash or cancellation. |
| `RESULT_DELIVERY` | OpenCode provides native child-result reports; Kael's prompt consumes the original child result. | A partial report followed by a terminal report from the same child was observed on Windows OpenCode V2.3.0 in [the dated case](#dated-follow-up-2026-11-14). | One observed delivery path is not a universal native delivery guarantee. |
| `RESULT_RECONCILIATION` | Core result-lifecycle policy and Kael's prompt retain the original child and prohibit blind retry on missing output. | Deterministic [`result-reconciliation` fixture](../tests/result-reconciliation/qualify.ps1) and [documented Issue #1 ordering](DEVELOPMENT.md#result-correlation-safety-issue-1). | The intermittent trigger was not reproduced; there is no exactly-once runtime enforcement. |
| `ALLOW` | Core task authority is combined with the effective native OpenCode permission rule for the exact operation. | Static scope and effective-rule assertions in [`tests/authority/qualify.ps1`](../tests/authority/qualify.ps1). | Configuration and fixture evidence are not blanket live API or permission-UI proof for arbitrary operations. |
| `ASK` | An applicable native OpenCode ASK rule requests permission; Core instructions require an exact scoped attempt and separate reporting of permission observation. | Static/synthetic authority checks and the isolated [permission API smoke](../tests/global-installer/native-permission-api-smoke.ps1), which programmatically rejects its ASK case. | Programmatic rejection is not human approval, interactive TUI visibility, or evidence that a notice appeared to a user. |
| `DENY` | Native rules refuse the exact operation, while Core DENY remains a non-elevatable policy boundary. | Effective-rule assertions in [`tests/authority/qualify.ps1`](../tests/authority/qualify.ps1) and the specific automatic-denial case in the isolated [permission API smoke](../tests/global-installer/native-permission-api-smoke.ps1). | This is not general shell/filesystem isolation; shell retains host authority and the fixtures do not establish a universal sandbox. |
| `CONTEXTUAL_OLYMPUS_MAINTENANCE` | The renderer transcludes canonical maintenance policy into Kael's prompt, which routes by target identity and task intent. | Static [`maintenance-scope` qualification](../tests/maintenance-scope/qualify.py) and the [canonical policy](../olympus/policies/maintenance-context.md). | Static coverage does not establish live, universal routing behavior. |
| `ACTIVITY_VISIBILITY` | The passive Activity plugin reads native session status and, when available, the reactive root-tree job list to show a direct child while its session or supported child-tree work is active. | Plugin source and the Node [presentation test](../tests/activity-hud/activity.test.mjs), [qualification](../tests/activity-hud/qualify.ps1), and user-reported before/after captures above. | Static/source evidence does not establish TUI rendering. The before-change captures show the HUD missing while native Subagents listed an idle child; the post-change captures show one Windows scenario where the row remained during a yielded child’s pending job and cleared after completion. The screenshots do not show a Shell pane while running, an exact runtime version, or the native shell exit status; this is not broader runtime qualification. |
| `GLOBAL_RUNTIME_DISCOVERY` | Isolated OpenCode configuration/data paths are used to check global agent discovery separately from renderer output or file placement. | Historical Windows OpenCode V2.0.26/v0.4.6 evidence found 12 then-current agents and two controls; current-team Windows V2.3.0 (#143) observed 11 Olympus IDs among 18 in [the recorded case](#opencode-23-subagent-compatibility); the V2.3.2 candidate report observed 11 expected IDs, with uniqueness unverified ([#180 evidence](../specs/001-portable-olympus-cli/evidence/issue-180-first-use.md)). | Evidence is limited to recorded Windows versions and isolated paths; it does not establish Unix global install/runtime, model execution, or universal public-install discovery. |

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

