# Development & qualification

For Olympus maintainers, contributors, installation debugging, qualification, and release engineering. For first-time setup, start with the [README](../README.md).

## Optional local Gitleaks hook

The repository provides an **opt-in** `.pre-commit-config.yaml` that pins the official Gitleaks `v8.30.1` hook to a specific upstream commit. It checks the **staged changes** before a local commit and redacts secrets in its output. It is not installed by cloning OlympusAgents or by any Olympus installer; it requires [pre-commit](https://pre-commit.com/) and Go on the contributor's machine. The first run needs network access to bootstrap the pinned hook.

Before installing any hook, inspect the effective Git hooks location and any existing `pre-commit` hook. Git's `core.hooksPath` can redirect hooks away from the default directory. In Windows PowerShell:

```powershell
cd 'D:\WORKSPACE\Personal\Tools\OpenCode-OlympusAgents'
git status --short --branch
git branch --show-current

$hookDirectory = (git rev-parse --path-format=absolute --git-path hooks).Trim()
Get-Item -LiteralPath (Join-Path $hookDirectory 'pre-commit') -ErrorAction SilentlyContinue
git config --show-origin --get core.hooksPath
```

If an existing hook or custom hooks path is configured, reconcile it manually first; **do not overwrite or bypass it automatically**. Once the hook location is confirmed to be safe, the contributor may choose to install and run the local check:

```powershell
cd 'D:\WORKSPACE\Personal\Tools\OpenCode-OlympusAgents'
git status --short --branch
git branch --show-current

py -m pip install --user pre-commit
pre-commit install --allow-missing-config
pre-commit run gitleaks
```

The hook checks staged changes, not the entire repository or historical commits. `--allow-missing-config` skips the hook in older worktrees that lack this file; it does **not** provide secret scanning for those worktrees. A hook can also be bypassed locally, so the independent CI secret gate remains mandatory. CI scans tracked and non-ignored current files plus the selected Git history. Its pinned release archive is downloaded with bounded retries and may be cached by the workflow; every cached or newly downloaded archive must pass the expected SHA-256 check before execution. A missing or invalid archive fails the gate closed. A cache-write failure after a verified download does not abort scanning, because caching is optional. No credentials, findings, or executable files are shared with the local hook.

## Architecture

Olympus Core defines canonical role responsibilities, model intent, routing, authority, result lifecycle, and contextual maintenance semantics. OpenCode V2 is the active-development runtime; its adapter is prioritized for new capabilities. The Codex adapter preserves its frozen compatibility baseline. Sharing Core does not create a Codex-parity requirement. Kael is the single conceptual ROOT ORCHESTRATOR: OpenCode represents it as its primary agent, while Codex represents it as the root thread. The eleven canonical Core roles and their responsibilities remain intact; maintenance uses Kael's normal workflow, selected from the identified target repository and task intent.

### Support and adapter contract — 2026-10-16

- **OpenCode V2 — ACTIVE DEVELOPMENT.** Design new features, agents, commands, architectural improvements, and runtime capabilities for OpenCode first. OpenCode-only capabilities do not need Codex equivalents.
- **Codex — FROZEN COMPATIBILITY.** Do not remove existing Codex components, installers, manifests, or uninstall protections; do not add integrations or close gaps solely for parity. Only evidenced critical Codex fixes or regressions introduced by shared-code changes are in scope, with a concrete bounded target.
- Retain existing tests protecting shared integrity and compatibility. Do not create Codex gates for OpenCode-only capabilities. Existing Codex static/integrity and shared installer checks remain what they are; their presence is not a mandate to qualify Codex parity for new work.
- The frozen Codex gaps include contextual OlympusAgents maintenance, authority differences, hard `DENY`, and observability. Do not claim verification of newer Codex versions without specific evidence.

**Future contract to keep the adapters decoupled:** specify shared Core invariants separately from adapter-specific capabilities and evidence. A new OpenCode-only behavior should be designed and qualified against its OpenCode contract; a missing Codex mapping must not block it. Codex checks apply when a change actually touches shared integrity/compatibility or is an explicitly authorized critical Codex correction—not as a parity gate. This is policy guidance, not an implementation or test-suite change in this task.

Kael checks feasibility, repository identity, and task scope before delegated research or planning. The same Kael workflow handles OlympusAgents development and ordinary project work; there is no separate maintenance command, role, or authorization plane. The native `/goal` surface remains opt-in and user-selected where available. Feasible work starts with task-scoped discovery (none, targeted file, or bounded subsystem) and widens only for an unresolved target/boundary, evidence of wider impact, or a genuinely repository-wide request. Broad research remains available when justified.

### Authority Grants — beta.3

Permission outcomes are explicit: **ALLOW** means an in-scope tool can run
directly; **NATIVE_ASK** means an otherwise eligible exact operation may be
attempted so OpenCode can request one-shot user approval; **DENY** means do not
invoke the tool. NATIVE_ASK is not prior user approval. A worker returns
`NEED_AUTHORITY` only when it discovers a legitimate path/operation not yet
delegated to it, with exact operation, minimum scope, repository root, reason,
and blocked task. Children cannot ask the user or self-escalate. Kael reconciles
outstanding results, then verifies role, ownership, and user prohibitions before
classifying/redelegating. Native ASK consent is obtained in OpenCode's permission
UI, not duplicated by a Kael QUESTION.
If no applicable native ASK exists and the request is not already ALLOW,
compatible needs may be consolidated into one precise Kael QUESTION under the
Question Barrier.

An Authority Grant is a current-task delegation field, not a persistent ACL:

```text
agent: kovan
operation: WRITE_SCOPE (create/update only)
scope: .opencode/plugins/foo/**
repository_root: <canonical affected repository root>
permission_mode: NATIVE_ASK
lifetime: current_task
task_id: <current task identity>
```

The authorized agent, operation/effect, paths/refs, repository root, and task
must match exactly; the grant expires at task end and never covers siblings,
other agents or inferred operations. For NATIVE_ASK, Kael delegates the exact
agent, operation/effect, WRITE_SCOPE, repository root, task identity and
permission mode; Kovan attempts that tool once without textual pre-authorization
and waits for the native permission result. Approval allows continuation;
rejection/cancellation means stop with no fallback or retry. A write grant does
not authorize deletion, rename, destructive replacement, Git side effects or
other high-impact work. Role/tool limits continue to apply. User prohibitions
(including “do not modify .opencode”) deny without a question. The native edit
policy makes project-owned `.opencode/**` resources ASK, with explicit DENY for `.opencode/agents/**`,
`.opencode/plugins/olympus-activity/**`, the
installer manifest, OpenCode config files, and other known Olympus-managed
assets. Root `opencode.json[c]` is DENY. A project-owned
`.opencode/plugins/<name>/**` is eligible only with positive project-ownership
evidence and no Olympus-owned collision. Its exact native ASK is the user
authorization point; Kael must not also send a duplicate QUESTION. The child
must reach the native permission layer by attempting the exact scoped tool;
reject means no write, approval is one-shot and grants no sibling paths. Do not
special-case project names. Kovan's broad project edit ALLOW must not be paired with a
blanket `edit * deny`, which blocks project-owned paths from reaching their
more-specific native ASK rules; the explicit Olympus-owned DENYs remain in force.

The project-wide `external_directory` default is ASK, not blanket ALLOW or DENY;
normal agents have no wildcard external allow. This supports repositories outside
the current root—including monorepo/sibling/multi-repo layouts—only after native
user approval and exact Kael scope. Layouts are not hardcoded. Native DENY is
never elevated by text, WRITE_SCOPE, or an Authority Grant. Repository identity
classifies whether canonical OlympusAgents source is the task target; it does
not grant access to a separate checkout or installed Olympus runtime resources.

### Trivial task / authority fast path

For a small deterministic operation with known scope and established ownership,
one sufficient writer, no architecture/uncertain diagnosis/cross-subsystem or
high-risk work, and directly verifiable acceptance, Kael may use one writer and
proportional direct verification. Specialist value must exceed orchestration
cost: Veyra is not required to rediscover established ownership, Nox is not
required for a simple directly observable success, and Vera/Atlas/other roles
are not invoked just because they exist. Explicit independent review remains
required when requested. This is an eligible-task policy, not an automatic route
for every apparently small task.

For an eligible scoped `NATIVE_ASK` write, Kael determines exact operation,
`WRITE_SCOPE`, repository root and ownership before launch; Kovan is the only
child, attempts the exact native operation, and waits for OpenCode's native
Approve/Reject result. Approval permits the operation to continue but does not
expand scope. Kael checks the requested target and exact scope proportionally.
Acceptance follows the real objective: a trailing newline is immaterial unless
exact bytes were explicitly required. Material validation failure, uncertain
ownership, scope expansion, unknown root cause, cross-subsystem/architectural
work, security-sensitive or destructive/high-risk behavior, conflict/drift, or
a true need for review exits this path and returns to normal orchestration.
Reconcile the original writer before dependent work; do not retry a completed
and accepted operation or irrelevant formatting. Retry only for a material
acceptance failure with a reconciled original and a justified different bounded
strategy.

The performance contract is proportional orchestration effort, not a seconds
SLA: trivial work should incur child/role/retry/verification decisions
proportional to the task; runtime and model latency vary. The static deterministic
qualification measures child count, role count, retries, and unnecessary
verification stages (not wall-clock time):

`pwsh -NoProfile -File ./tests/trivial-fast-path/qualify.ps1`

### Phase 3 — role purity and iterative evidence (shipped)

**DO YOUR ROLE; DO NOT ABSORB ANOTHER ROLE TO SAVE A HANDOFF.** Kael owns Preflight,
routing, dependencies, session families, reconciliation, retry decisions and final
synthesis. Veyra supplies discovery; Orin architecture; Kovan implementation;
Nox runtime/test evidence; Vera independent review. Atlas optionally plans execution order for already-scoped, already-architected changes without discovering, editing or validating; Thales reasons over actual
evidence under the existing Diagnostic Gate; straightforward bugs do not trigger
Thales. Reasoners identify hypotheses and discriminating evidence, not execute
specialist work or self-review in place of Vera.

The certified **KAEL_MEDIATED** topology is USER/ROOT → Kael → Thales →
EVIDENCE_REQUEST → Kael → worker → evidence → Kael → SAME Thales session → decision
→ Kael → execution/finalization. Reasoners and workers are direct Kael children;
reasoner-to-worker subagents hit the native depth limit (1). A bounded request
names TARGET_ROLE, QUESTION, SCOPE, WHY_NEEDED and EXPECTED_DISCRIMINATION.
Kael checks role, scope, novelty, dependencies and plane boundaries. Follow up
narrowly only when material new information is expected. The first Thales call
requires the Diagnostic Gate, the second requires completed bounded action and
material new evidence; no third automatic call.

An open evidence round inherits Issue #1 safety: missing tool output never means
FAILED worker evidence or retry permission. Retain the known original worker,
wait, reconcile, consume once and only then re-consult the SAME Thales session.
Pending or indeterminate evidence does not complete the round. Unknown execution
stops as COMPLETION_UNCONFIRMED without an invented empty packet or replacement
worker. Kael finalizes only after terminal reconciled workers, actual evidence,
consumed reasoner final result, root synthesis and zero unresolved/unknown work.
The conservative two-consultation Thales budget remains in force: initial request,
worker evidence, then a final Thales consultation is possible. If Thales asks for
a second evidence round on call two, a third automatic consultation to conclude
is **not** allowed. Stop for explicit user authorization before any third Thales
consultation, and require a terminal/reconciled/validated second evidence round;
do not count an unconsulted reasoner conclusion as complete.
Static/synthetic qualification: `pwsh -NoProfile -File ./tests/role-purity/qualify.ps1`.
Live qualification was executed by the user, not by this integration task.
Issue #1's normal-child result reconciliation remains authoritative. The former
Issue #2 Aegis handoff is retired by the Issue #28 clean break; its reports remain
historical evidence and do not define a current route. Phase 3 user-executed
live Case A (`ses_f21e09d97ffeiyjqAvmZuDRxa9`) confirmed Kael-mediated,
role-pure one-round evidence and the same Sorin session continuing twice;
Case B (`ses_f21dad776ffevU6A5qKcenexjh`) confirmed zero Sorin consultations
on a simple deterministic defect. Both families completed with zero unknown or
unresolved work. Phase 3 evidence class: USER_EXECUTED_LIVE_EVIDENCE; see
`tests/role-purity/RUNME.md` for the historical manual fixture instructions.

## Local/bootstrap installation

From an Olympus source checkout, project bootstrap targets the **root of a separate, trusted Git project** on Windows with Git and PowerShell 7 available. OpenCode project installation additionally requires the OpenCode CLI and configured models; Codex-only project installation does not invoke OpenCode. The public installer can be launched from Windows PowerShell 5.1 or PowerShell 7 and delegates bootstrap to installed `pwsh`. `-Scope project` remains the default and its behavior is compatible with beta.5; `-Harness` accepts `opencode` (default), `codex`, or `all`, case-insensitively. The v0.4.0 and v0.4.1 immutable validation tags both failed release validation because of release-facing documentation contradictions; neither resulted in a GitHub Release. `-Scope global` writes to the evidenced harness user directories, does not overwrite global base config, and is currently Windows-qualified. Global OpenCode runtime discovery is `SUPPORTED` for isolated Windows/OpenCode V2.0.26 based on real v0.4.6 install, plugin activation, agent roster and opt-in Kael selection evidence (Issue #7); no live model prompt or cross-version guarantee is implied. Codex global runtime is `SUPPORTED` based on separately supplied runtime evidence. `-Version` accepts only Olympus SemVer `vX.Y.Z`, `vX.Y.Z-alpha.N`, `vX.Y.Z-beta.N`, or `vX.Y.Z-rc.N`; the remote source must be the immutable matching tag.

```powershell
pwsh -NoProfile -File ./scripts/bootstrap.ps1 -Target 'C:\path\to\project' -DryRun
pwsh -NoProfile -File ./scripts/bootstrap.ps1 -Target 'C:\path\to\project'
```

For `-Scope project`, `-Target` must be an absolute path to the Git worktree root; `-DryRun` checks and reports proposed changes without writing them. Project `-VerifyOnly` resolves the requested release like install mode, then checks only the selected harness subset against generated outputs, project-scope manifest ownership, and SHA-256 hashes. It does not launch external runtime discovery in the target. An additional installed harness—including its drift—does not fail a subset verification. Global `-VerifyOnly` checks only the selected global manifest/resources; OpenCode path discovery, when required, runs outside the project. Both forms are read-only and do not create/update manifests or repair drift. A recorded non-legacy `installed_version` that conflicts with the requested version fails explicitly. `scripts/bootstrap.ps1` derives its managed inventory from generated Harness Core outputs in its own checkout and **does not accept `-SourceRoot`**. For local installer qualification, `install.ps1` has `-SourceRoot` and local tag-shaped `-SourceArchive` overrides; both validate source identity. The public installer fetches the archive for the exact requested immutable tag, validates archive-root tag and embedded version, and fails closed on mismatch. Project manifests record `scope = project`; global manifests record `scope = global`, `installed_harnesses`, version and managed hashes. Legacy manifests without scope remain interpreted as project-local. The global path update/uninstall foundation never cleans project-local state.

Canonical project-local command forms (replace `<TAG>` with the exact published tag containing the dual-harness installer; do not use `master`):

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1 | iex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness codex
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness all
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness opencode -Version '<TAG>' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness codex -Version '<TAG>' -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness all -Version '<TAG>' -Target (Get-Location).Path -VerifyOnly
```

## Managed installation and recovery

The active harness manifest records installed source commit, `installed_harnesses`, managed paths and SHA-256 hashes, plus project detection metadata. OpenCode installations use `.opencode/orchestrator-install.json`; Codex-only installations use `.codex/orchestrator-install.json`. OpenCode manages generated `.opencode/**` and `opencode.jsonc`; Codex manages generated `.codex/**` and `CODEX.md`. Adding a harness preserves the existing set, with the manifest moved to the OpenCode location when OpenCode is added to a Codex-only project. On reinstall, unchanged selected assets yield `NO_CHANGES` (after effective OpenCode agent validation when selected). Missing or modified selected owned files yield `MANAGED_FILE_DRIFT`; differing unowned destinations yield `INSTALL_CONFLICT`. An exact generated Codex destination may be adopted, while differing user-owned TOML/Markdown/config is never overwritten. OpenCode retains its existing stricter unowned-destination behavior.

Phase 4 upgrades recognize the exact historical Sorin managed-file set (including earlier pre-HUD/pre-Maintenance sets). The owned Sorin file must still match its manifest hash; the installer then installs Thales, removes the verified owned Sorin file, and writes a Thales-only manifest. A user-modified Sorin file fails drift protection; an unowned Sorin or Thales path fails conflict protection. Fresh installs create Thales only. Qualification: `pwsh -NoProfile -File ./tests/thales/qualify.ps1`. The focused live routing fixture in `tests/thales/RUNME.md` was executed by the user and passed; it was not rerun during integration. Phase 4 is SHIPPED on master. Evidence class: USER_EXECUTED_LIVE_EVIDENCE.

The Issue #28 clean break removes the Aegis role and `/maintain` command from current outputs. Project bootstrap retires those resources only when an exact legacy manifest and hashes establish ownership; modified files remain drift blockers and unowned collisions remain preserved/conflicting. Global updates likewise remove only unchanged resources recorded in their ownership manifest. Current qualification checks the single Kael roster and safe retirement behavior; historical Aegis results remain in the dated history and issue records, not as current product routes.

Olympus does **not** require a globally clean target Git worktree. Unrelated modified, staged, untracked and tool-generated files (including unrelated content under `.opencode/`) are allowed and preserved. Safety is based on explicit managed destinations and ownership hashes, Git-root validation, and path containment; unsafe targets and unmanaged destination collisions still block. The installer never stashes, resets, cleans, stages, or normalizes user work.

If drift occurs, inspect the reported path and manifest, back up any intentional edits, then restore the affected owned file from a known-good installation/revision before retrying. Do not delete the manifest or force an overwrite to bypass ownership checks. If the manifest itself is damaged or you cannot establish the installed baseline, stop and investigate before reinstalling; preserve unrelated work.

## Qualification

The contextual `FAST:` request asks Olympus to use useful independent parallelism within its existing limits. The `FAST` qualification profile below selects offline checks; these two meanings are separate, and neither skips required validation or completion gates.

### TFR in software built with Olympus

The canonical **TFR (risk-based focused testing)** decision rule lives in
`olympus/policies/routing.md` and is delivered to Kael in both OpenCode and
Codex through the existing renderer. For an unrelated user repository, Kael
discovers that project's real testing commands and chooses proportionate
checks; it does **not** assume Olympus's own FAST/FULL/RUNTIME qualifier
profiles exist there. Nox and Vera are used only for distinct needed evidence,
and passing static prompts is not a claim about live model decisions.

For example, [Issue #47](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/47)
calls for verifying creation and cleanup of Olympus's temporary Python command
shim, without reproducing generic operating-system permission handling.

The guidance below concerns **qualification of OlympusAgents itself**.
Keep historical coverage and mandatory gates until an evidenced contract
mapping and measured cost justify consolidation; do not delete tests just
because they are slow.

### Choosing qualification by change risk

Choose checks that provide evidence proportionate to the change's risk, affected
surface, available evidence, and acceptance criteria. Do not run FULL by default;
begin with the smallest focused check that establishes the changed contract.

- **Documentation-only changes:** review the content and run `git diff --check`. Do not run FULL or RUNTIME by default.
- **Localized bugs or changes:** first run the directly affected test or qualifier. Add FAST when shared contracts may also be affected.
- **Olympus Core, routing, authority, models, or shared policies:** use focused tests during development; add FAST for affected shared contracts. Use FULL only when cross-layer impact, insufficient narrower evidence, or an existing mandatory gate justifies it.
- **Installers, bootstrap, releases, or compatibility:** run affected fixtures during development. Use FULL only when change risk is material, impact is shared/cross-layer, narrower evidence is insufficient, or an existing mandatory integration/release gate requires it. Installer/bootstrap work alone does not make FULL mandatory.
- **Changes depending on actual runtime behavior:** prioritize focused OpenCode V2 RUNTIME evidence. Run Codex runtime checks only for an in-scope critical Codex correction or a shared-code regression where runtime evidence is materially needed; do not add a Codex gate for an OpenCode-only capability.
- **Failures:** fix the issue and repeat only the affected verification before widening coverage. Do not automatically rerun all of FULL after every adjustment.
- **Evidence reuse:** reuse a recorded result when it proves the same acceptance criterion and the relevant source revision/working-tree state, configuration, dependencies, and runtime conditions remain applicable. Evidence does not expire solely with age; mark it stale when a relevant input changed or applicability/scope cannot be established. Use revision/diff/context evidence rather than repeating hashes unless integrity or ownership specifically requires them. Unknown evidence is not PASS.
- **External-provider boundaries:** Olympus qualification covers Olympus-controlled components and declared integration behavior. Respect each user's stated economic and authentication constraints; do not impose global prohibitions on API keys or paid providers, and do not change authentication without authorization. Do not investigate a user's subscriptions, billing, external entitlements, or authentication settings absent a specific authorized need. Classify `BLOCKED_PROVIDER_ENVIRONMENT` only when observable evidence shows a blocking failure originates outside the integration contract OlympusAgents controls; defects in OlympusAgents' own integration remain product defects.
- **Non-blocking diagnostics and time:** keep auxiliary-harness failures separate from product outcomes, insufficient evidence, and real security blockers; one does not automatically invalidate another. Whenever duration is collected or reported, record `TECHNICAL_EXECUTION_TIME` (active tool/process execution, excluding waiting and coordination) and `TOTAL_ORCHESTRATION_TIME` (task start through validated completion, including waiting and coordination) separately. Mark unobserved values unavailable; do not infer them.

FAST, FULL, and RUNTIME retain their current behavior, and these rules do not replace existing mandatory validation. RUNTIME does not replace FULL, nor FULL RUNTIME. Do not omit failures or report unrun checks as PASS. Avoid unnecessary FULL repetitions without imposing a rigid limit when material changes warrant further validation. Present the relevant diff and evidence for human review at the end; add no separate automated review stage unless required or justified by risk.

The existing Codex checks in FAST/FULL/RUNTIME remain for their established shared-integrity, compatibility, and baseline purposes. They are not expanded to new OpenCode-only capabilities. The Codex catalog probe is not evidence that a new Codex version or runtime capability was verified.

Use the following existing checks as starting points for development validation from the source checkout root. This selection does not replace mandatory project, CI, integration, or release gates. Run affected integration checks when shared contracts or installer behavior are affected. Use an existing RUNTIME slice or native smoke when correctness depends on actual harness, process, or UI behavior; static checks alone do not establish native behavior.

| Change | Recommended check |
| --- | --- |
| Release-facing README, changelog, or documentation contracts | `pwsh -NoProfile -File ./tests/release/tag-transition-stability.ps1` |
| Olympus Core, renderer, or generated adapter contracts | `python3.11 -B ./scripts/render_harnesses.py check --harness all`<br>`python3.11 -B ./tests/harness-core/qualify.py --safe-root-read-only` |
| Completion-gate policy | `pwsh -NoProfile -File ./tests/completion-gates/qualify.ps1` |
| Activity HUD presentation logic | `node --test ./tests/activity-hud/activity.test.mjs` |
| Codex root-instruction precedence | `pwsh -NoProfile -File ./tests/codex-instructions-precedence/qualify.ps1` |
| Dual-harness installation or subset verification | `pwsh -NoProfile -File ./tests/release/dual-harness-installer.ps1` |

### Unified contributor profiles (Issue #11)

From the source checkout root, run exactly one selected profile:

```powershell
pwsh -NoProfile -File ./scripts/qualify.ps1 -Profile FAST
pwsh -NoProfile -File ./scripts/qualify.ps1 -Profile FULL
pwsh -NoProfile -File ./scripts/qualify.ps1 -Profile RUNTIME
```

**FAST** is offline-only: safe-root-read-only Harness Core; Codex static checks;
the 13 established PowerShell contract checks (including handoff fidelity); and
external-work ownership static contracts. It never queries OpenCode or Codex,
does not run disposable processes, and does not render generated outputs in the
checkout. It does not include the nine installer/history selectors reserved for
FULL. Direct qualifier defaults remain unchanged.

**FULL** runs FAST exactly once, then the Windows global-installer fixture, the
release qualifier with `-MockOpenCode`, installer compatibility, dual-harness
installer, dirty-worktree checks, and the three existing Phase 11 offline
commands (qualifier, integrated-routing unittests, feature-fixture unittests),
followed by the Offline slices of Authority, Activity HUD, Argus, Atlas, Helios,
Talos, Thales, Phase 4C, and Autonomy. Those nine slices execute their existing
local installation, history, upgrade, drift, conflict, and synthetic checks;
Activity also runs its local Node presentation tests. For bootstrap-driven
offline fixtures only, they temporarily put the existing
`tests/release/fixtures/opencode.ps1` qualification stub first on `PATH`, then
restore the original process environment. That explicit deterministic fixture
supports installation setup; its output is not treated as live OpenCode
discovery or effective-runtime evidence, and RUNTIME never uses its output as
runtime evidence. The
FULL dirty-worktree installer check uses the same fixture only for its local
OpenCode `--version` preflight. FULL does not contact a real OpenCode or Codex
runtime. It does not call tag-transition stability a second time; that check is
already nested in release qualification. Phase 11's existing historical corpus
is used as-is.

**RUNTIME** does not include FULL or FAST. It runs only the Codex bundled-model
catalog probe, external-work ownership disposable process cases, and the
existing effective-agent/plugin boundaries for Authority, Activity HUD, Argus,
Atlas, Helios, Talos, Thales, Phase 4C, and Autonomy. Phase 4C's runtime
selector includes P4C-2/11/12/14 and the contextual-maintenance roster check.
Managed-file drift and legacy-resource retirement assertions remain in FULL
Offline and the direct Both qualifier, not RUNTIME.
Authority Runtime builds a unique fixture under
`C:\Users\Public\olympus-authority-qualification`, copies only the current
canonical `olympus` sources plus the renderer and bootstrap scripts, renders
OpenCode outputs there, and bootstraps them into a minimal Git project. The
bootstrap uses the existing qualification stub from a child-only `PATH`; its
output is setup evidence only. Runtime runs its queries from the fixture
project: `debug paths` first confirms isolated paths, then Runtime starts an
owned loopback OpenCode service on an ephemeral port and verifies its isolated
XDG state registry. The subsequent `debug config`, authenticated
`GET /api/integration`, and `debug agents` queries use that same backend. The
integration request waits for plugin activation and verifies the returned
`location.directory`; it uses only the service password from the fixture
registry. Runtime checks that the registry still names the owned process after
each query and verifies the owned loopback listener before stopping the service.
Cleanup confirms process exit and drained streams, then removes the fixture;
cleanup or removal failures fail qualification.
Offline makes no real OpenCode calls; Both runs Offline plus this same Runtime
path.
Fresh fixture installs needed by runtime checks are part of their setup;
unrelated offline suites and manual interactive smokes are not run. If Codex or
OpenCode is unavailable, dependent checks are `NOT RUN`, never PASS; the
aggregate is `PARTIAL` (exit 2). Only an explicitly designated missing
prerequisite can produce `NOT RUN`; an unclassified child exit 2 is a failure.
OpenCode global custom-agent discovery is `SUPPORTED` for isolated Windows
V2.0.26 (Issue #7: real v0.4.6 global install, loader active, 12/12 agents,
2/2 controls, Kael configuration-level selection). The unified RUNTIME profile
still excludes the historical long-running `tests/global-runtime/qualify.ps1`:
that diagnostic does not yet observe plugin activation completion, so an early
empty roster is inconclusive. Do not repeat it as a release gate or infer model
execution from the reported discovery PASS. Codex global runtime remains
`SUPPORTED` on user-provided evidence, not rerun here.
A completed RUNTIME profile still does **not** qualify interactive child
execution, native ASK UI or human approval/rejection, the question race, Codex
sessions, or Activity TUI rendering; those remain separately observed/manual
evidence.

The profile runner uses a locally available Python 3.11+ interpreter, PowerShell
7, and Git; it does not download packages or choose an environment manager.
RUNTIME's external-process slice uses `ConvertFrom-Json -DateKind String` and
requires PowerShell 7.5+; FAST runs only its `StaticOnly` selector and has no
DateKind requirement. FULL's global installer is Windows-only. Release
qualification with `-MockOpenCode` requires Windows `Win32_Process` process
identity support and local historical refs `v0.2.0` and `v0.3.0-beta.3`.
Other existing history-sensitive suites require their checked-in Git objects,
including handoff `70f22...`, Argus `63357c4e8394a0646acb80e8725b576a12c91e62`,
Atlas `dea863168fc16a6b97e0b6404c4334f4265f1e52`, Helios
`a5b2c9a12f542217e7d9927034486f922756d17c`, Talos
`5911d06d998e5259ffa4b2aa4510e844f264f30f`, and Thales tag `v0.2.0`.
Phase 4C's historical identity fixture also needs commit
`3ab1495fdfcdb8503e2411effe81e814da3f6eb6`; its local migration checks run in
FULL and its existing effective-runtime portion is also selected by RUNTIME.

The direct qualifier commands below retain their original combined behavior when
called without a selector. The profile switches only select bounded existing
slices; they do not add suites, profiles to Olympus itself, or duplicate tests.

### Current model mapping

`olympus/core/models.toml` is the sole conceptual role→family/effort map.
Harness-specific identifiers are translations from that file: Sol currently
renders as `openai/gpt-6.1-sol` for OpenCode and `gpt-6.1-sol` for Codex; Luna
remains GPT-6 Luna. Sol roles retain `high` except Thales (`xhigh`); Luna roles
retain `max`. Change a family identifier in Core and re-render—do not update
agent files or installer model tables by hand. Qualify the model mapping and
installer check with:

```powershell
pwsh -NoProfile -File ./tests/model-migration/qualify.ps1
```

Earlier runtime evidence in the roadmap remains a historical record of the
model actually used at that time; it is not a current model assignment.

From the source checkout root, use the current harnesses (PowerShell 7; some require `opencode`, Git, and Node):

```powershell
python scripts/render_harnesses.py render --harness all
python scripts/render_harnesses.py check --harness all
python tests/harness-core/qualify.py
python tests/codex/validate_profile.py
pwsh -NoProfile -File ./tests/worktree-activation/qualify.ps1
pwsh -NoProfile -File ./tests/worktree-activation/native-smoke.ps1
pwsh -NoProfile -File ./tests/model-migration/qualify.ps1
pwsh -NoProfile -File ./tests/trivial-fast-path/qualify.ps1
pwsh -NoProfile -File ./tests/phase4c/qualify.ps1
pwsh -NoProfile -File ./tests/authority/qualify.ps1
pwsh -NoProfile -File ./tests/activity-hud/qualify.ps1
pwsh -NoProfile -File ./tests/adaptive-concurrency/qualify.ps1
pwsh -NoProfile -File ./tests/autonomy/qualify.ps1
pwsh -NoProfile -File ./tests/release/qualify.ps1 -MockOpenCode
pwsh -NoProfile -File ./tests/release/tag-transition-stability.ps1
pwsh -NoProfile -File ./tests/release/installer-compatibility.ps1
pwsh -NoProfile -File ./tests/release/dual-harness-installer.ps1
pwsh -NoProfile -File ./tests/release/dirty-worktree.ps1
pwsh -NoProfile -File ./tests/preflight/qualify.ps1
pwsh -NoProfile -File ./tests/routing-constraints/qualify.ps1
pwsh -NoProfile -File ./tests/question-barrier/qualify.ps1
pwsh -NoProfile -File ./tests/completion-gates/qualify.ps1
pwsh -NoProfile -File ./tests/result-reconciliation/qualify.ps1
python -B ./tests/maintenance-scope/qualify.py
pwsh -NoProfile -File ./tests/structured-output/qualify.ps1
```

`tests/maintenance-scope/qualify.py` checks the contextual-maintenance policy, target identity boundary, opt-in `/goal`, current Kael roster, and absence of retired product outputs. It is static and does not claim interactive model behavior. `tests/structured-output/qualify.ps1` checks exact requested terminal-field preservation as a general Kael contract, also without claiming live model behavior. Phase 11 routing traces remain historical evidence; their former Aegis contract is superseded and is not part of current qualification profiles. `tests/authority/qualify.ps1` stages generated runtime resources in a disposable project, so its live effective-agent probe does not depend on this checkout's `.opencode` outputs. This isolates only the byte/runtime-sensitive gates and does not require serializing unrelated read-only qualifications.

`check` is read-only. Harness-core qualification tests renderer idempotence,
drift/missing-output detection, canonical role/model/policy sources, and
cross-harness capability claims. Codex static qualification uses the local
bundled model catalogue when `codex` is installed; it does not run an
interactive Codex smoke.

Phase 4C covers bootstrap security, contextual-maintenance roster discovery, and hash-verified retirement of legacy resources. The Preflight harness checks policy ordering, target/ownership boundaries and a small cart/auth fixture **statically**; it does not execute agents or verify actual child count, discovery tool calls or latency. The Activity HUD harness tests presentation, installation, and plugin discovery, not interactive rendering. Adaptive Concurrency / FAST checks are static; the autonomy harness checks effective permissions and bootstrap, not interactive child execution. The release qualification's `-MockOpenCode` mode uses a task-local deterministic CLI fixture to exercise installer/bootstrap and verification behavior without contacting a live OpenCode runtime; it does not establish runtime agent/plugin discovery. The release, dirty-worktree, and installer compatibility harnesses use **local source**, not the remote tag, and do not test the interactive UI. The dirty-worktree harness checks unrelated bytes, Git status, index diffs, managed conflict/drift, reinstall and a local-source managed update. The compatibility harness launches the installer via both Windows PowerShell 5.1 (when present) and PowerShell 7 into separate disposable Git projects, and tests missing `pwsh` with a process-local PATH. Some harnesses retain disposable fixtures; check their output. The adaptive-concurrency harness's `DOC` check verifies that the README describes NORMAL as the default using only useful parallelism, FAST as explicitly requested with up to four agents, and FAST as preserving checks and task dependencies.

`tests/worktree-activation/qualify.ps1` is a Windows-only, disposable Git regression. It installs the immutable `v0.4.4` source into a main checkout, creates two linked worktrees (whose `.git` entries are files), confirms that neither discovers Kael, upgrades the main checkout, provisions both through the manifest-owned helper, and checks per-checkout hashes, user-file preservation, idempotence, conflicts and source drift. Its OpenCode installer CLI is a deterministic stub.

`tests/worktree-activation/native-smoke.ps1` uses the installed OpenCode CLI with all OpenCode data/config/cache/state redirected to a task-owned temporary directory. It installs into a disposable Git repository, saves `Project.Commands.start` through the OpenCode API, creates two native worktrees through `worktree.create`, and validates each copied manifest and effective `default_agent`. OpenCode V2's awaited startup hook is exercised; **no model prompt, effective agent roster, Kael delegation, or cancellation event is claimed**. Those require a separately observed prompt/session smoke and are not established by these fixtures.

The Routing/Constraints, Authority Grants, and Question Barrier harnesses verify static contracts plus deterministic synthetic cases; they do not claim interactive runtime execution or real process termination. `tests/authority/qualify.ps1` also inspects OpenCode's effective agent rules, but approval/rejection delivery and exact runtime tool behavior require an interactive OpenCode session. Report interactive evidence separately from static qualification output. The Question Barrier live race remains separate and must be reported as `RUNTIME_QUESTION_RACE: NOT AUTOMATED` unless observed.

Native ASK is a client-side permission event, not a requirement for literal `ASK`
transcript text. Keep four facts separate in a child report: `TOOL_ATTEMPT`,
`TOOL_EXECUTION` and its direct result, `NATIVE_PERMISSION_UI`, and
`USER_CONFIRMED_EXTERNAL_OBSERVATION`. Use
`NATIVE_PERMISSION_UI: OBSERVED_ASK | OBSERVED_NO_ASK | NOT_OBSERVABLE` and
`NATIVE_PERMISSION_DECISION: APPROVED | REJECTED | NOT_OBSERVABLE`; report UI or
decision only when directly observable in that agent's context/tool result.
Otherwise use `NOT_OBSERVABLE`. Tool success does not establish that ASK was
absent, and tool failure/denial alone does not establish a human rejection. A
later user confirmation may be recorded as attributed external/manual evidence,
without presenting it as the agent's own observation. Classify
`NATIVE_AUTHORITY_ASK_RUNTIME: PASS` only when an assigned child attempts the
exact tool, the native permission event remains pending for the client's
decision, and the tool executes only after approval; rejection/cancellation
must leave it unexecuted with no fallback or bypass. Static qualification can
test the delegation/tool-attempt contract but cannot establish that the native
UI appeared or that a human approved/rejected; it reports `NOT ASSESSED BY
STATIC QUALIFICATION`. Report observed interactive evidence separately. The
Question Barrier live-race status remains independent.

## Result correlation safety (Issue #1)

A missing parent tool output is **not** evidence that delegated work failed or never started. In the two historical observations, the parent correlation error preceded the original Nox child's terminal result; both terminal results persisted. The exact OpenCode runtime trigger is unproven. Kael first reconciles an identifiable original child through native completion/results, retaining its assignment until it can consume and validate the original result once. Observable terminal session truth outranks an earlier parent correlation error. If the original cannot be recovered or execution cannot be disproved, report completion unconfirmed rather than blindly retry, including for read-only work and especially for side effects. Only positive native evidence of non-execution makes a bounded retry eligible. No poller, resolver or persistent dedupe state is added. Phase 3's Kael-mediated iterative evidence loops inherit this rule: never feed a reasoner fabricated failure or replacement evidence for an indeterminate worker; reconcile the original or stop unconfirmed. The focused deterministic fixture is `tests/result-reconciliation/qualify.ps1`; manual live instructions are in `tests/result-reconciliation/live-control.md`. Neither claims to reproduce the intermittent runtime race.

## Exact structured task output

When a user specifies required terminal fields (for example through
`EXPECTED_OUTPUT`), preserve every required field name and produced value
verbatim in Kael's final result. A concise summary may accompany those fields but
cannot replace, rename, paraphrase, or omit them. Missing, renamed, duplicated,
or conflicting fields are `STRUCTURED_RESULT_INCOMPLETE`; do not infer missing
values or retry an otherwise completed operation. The synthetic check is
`tests/structured-output/qualify.ps1`; it does not claim live model behavior.
Historical Issue #10 evidence remains in its issue and prior release records.

## Trusted-project execution

Explicitly bootstrapped projects are treated as trusted. Kovan can edit and use shell within its assigned task ownership; Nox can use shell for validation but does not edit source. `WRITE_SCOPE` is an orchestration ownership contract, **not an OS sandbox**: shell can access paths beyond it, so agent instructions still matter. Native `external_directory` ASK prevents a blanket path-taking-tool grant outside the runtime root. Bootstrap target safety (Git root, containment, conflict and drift checks) remains separate and stricter; agent trust never relaxes installation checks.

## Activity HUD

The passive, read-only plugin uses native OpenCode child-session list and status to show running agents and their tasks. It appears only when direct children are active; it does not spawn sessions, poll, or alter orchestration.

## Retired Aegis workflow — historical record only

Issue #28's approved 2026-11-07 clean break replaces the former separate
maintenance route with contextual work through the one Kael orchestrator. The
historical Issue #2/#8 handoff, compaction, and permission observations remain in
dated history files and issue comments; they are not current product behavior
or qualification requirements. The current policy is
`olympus/policies/maintenance-context.md`.

## External work ownership

Kael owns each process, controller, build/test job, and native child session
started for the current task. Keep the task open through tracking, wait/join,
collection, validation, and finalization. Background requests do not authorize
detachment. Before launch, establish that the full lifecycle is observable;
otherwise report BLOCKED without starting it. Missing output is not failure and
never authorizes a blind retry. `tests/external-work-ownership/qualify.ps1`
checks this shared Kael contract and disposable process ownership; it is not an
interactive-agent or runtime-permission test.

OpenCode v2.0.15 completion semantics: `POST /api/session/{sessionID}/command` executes a slash-command callback immediately; `POST /api/session/{sessionID}/prompt` durably admits input and schedules execution. A CLI `opencode run` exit or a root assistant response is not a session-family completion signal. `POST /api/experimental/session/{sessionID}/wait` waits for **one** agent loop to become idle (HTTP 204), not its descendants or a terminal result. `GET /api/session/active` lists only foreground drains owned by that server process: absence is not proof of terminal completion. Use `GET /api/session?parentID=<root>` (paginate), recursively discover descendants, `GET /api/session/{sessionID}` (outcome, time.idle), `GET /api/session/{sessionID}/inbox` and messages/export to verify terminal result and parent consumption. Recheck family membership before concluding. There is no documented family-wide wait in this version. Distinguish MESSAGE_COMPLETE, ROOT_IDLE and FAMILY_COMPLETE (the last is a validated workflow condition, not an OpenCode API status). If a child has no terminal outcome/result, classify it as unconfirmed even if the root has gone idle. Bounded waits must end with an honest PARTIAL/BLOCKED report rather than fabricate success.

### Question Barrier

Kael does not ask a human question while any task child is running, an original result is pending/indeterminate, or a terminal result/completion notification has not been reconciled, collected, validated and consumed. Reconcile the existing family and consume each original result once before presenting a question. Unknown work is not an empty barrier. If a user decision is already known to be a prerequisite, ask before launching dependent children. A question that becomes necessary after fan-out is deferred until the barrier is empty; while it is pending, dependent children remain pending. Deterministic decisions already specified by the request, constraints, capabilities or routing have QUESTION COUNT = 0.

### Restart and process recovery

Recovery preserves chronological evidence. Later messages, tool/process activity, progress, or a collected result outrank an older metadata snapshot. An old `session.outcome=failed` cannot override later activity; classify that identity as `STATE_INCONSISTENT_AFTER_RESTART` and continue reconciliation. Absence from `/api/session/active` means only that the session is absent from that endpoint's current list, not that it completed. Distinguish `LIVE_OWNED_WORK`, `TERMINAL_COLLECTED_WORK`, `STATE_INCONSISTENT_AFTER_RESTART`, `ORPHAN_CANDIDATE`, and `CONFIRMED_OWNED_ORPHAN`.

For a process that may outlive its launcher/runtime, use the task's available lifecycle evidence to verify identity, progress, ownership, and terminal output before recovery. Parent disappearance, responsiveness, or process-name similarity alone is insufficient. Never retry a live or unreconciled original, and never terminate by process name or broad pattern. If safe cleanup or duplicate-free revalidation cannot be established, report the limitation rather than guessing.

## Release process

Release-facing documentation is committed as product/version content, not as an
ephemeral release-state ledger. A candidate commit must remain truthful both
before tagging and after that exact commit is tagged; do not write that the
active version is still future, untagged, unmerged, pending publication, or
forbidden from publication. Keep execution status in qualification output and
this procedure.

Use this state machine for each release:

1. **Master validated.** Run release/version and documentation-claim
   qualifications on the exact `master` commit. Review capability gaps and
   static-versus-interactive limits; release notes must include `Installation`
   and `Verify installation` sections with commands pinned to the same version.
2. **Tag candidate.** Create the candidate tag from the validated commit. A
   beta/prerelease must not use mutable `master` as its installer source.
3. **Validate the immutable remote tag.** Fetch/inspect that exact tag and run
   installer and VerifyOnly checks against its tag-shaped source/URL in
   disposable Git projects. Local-source `tests/release/qualify.ps1` does not
   replace this tagged-source validation.
4. **If PASS, create the GitHub Release.** Use the same tag and validated notes,
   then run `pwsh -NoProfile -File ./tests/release/github-release-notes.ps1
   -Version <tag>` to check the actual published Release body.
5. **If FAIL, keep the tag immutable and advance the patch version.** Do not
   move, delete, or recreate the failed tag; make corrections on `master`,
   validate the next patch candidate, and repeat the state machine. A failed
   validation tag does not itself constitute a published release.

The release-notes gate checks the actual GitHub body after publication and
rejects missing or mismatched install/verification commands. The local
qualification checks are deterministic and do not create tags or releases.
