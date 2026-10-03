# Development & qualification

For Olympus maintainers, contributors, installation debugging, qualification, and release engineering. For first-time setup, start with the [README](../README.md).

## Architecture

Olympus Core defines role responsibilities, model intent, routing, authority, result lifecycle, and maintenance-plane semantics. OpenCode and Codex adapters express that same Core in their native surfaces. Kael is the single conceptual ROOT ORCHESTRATOR: OpenCode represents it as its primary agent, while Codex represents it as the root thread. Aegis remains a separate privileged Olympus maintenance role, supported only through OpenCode's explicit `/maintain` entry.

Kael checks feasibility and plane routing from the request **before** delegated research or planning. Explicit `/maintain` accepts its delivered task in any repository; its command entry is sufficient authorization. Ordinary user-project work, including ordinary Git administration, remains in the normal plane; Git alone is not an Aegis capability boundary. Kael does not automatically delegate to Aegis. Feasible work starts with task-scoped discovery (none, targeted file, or bounded subsystem) and widens only for an unresolved target/boundary, evidence of wider impact, or a genuinely repository-wide request. Broad research remains available when justified.

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
`.opencode/commands/maintain.md`, `.opencode/plugins/olympus-activity/**`, the
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
never elevated by text, WRITE_SCOPE, or an Authority Grant. The explicit
`/maintain` command enters Aegis for its delivered task in any repository; it is
not an automatic route for ordinary project authority requests.

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
The original Issue #1 normal-worker and Issue #2 explicit Aegis result
reconciliation remain authoritative. Evidence requests cannot route Aegis;
an identified running Aegis child stays PENDING despite an early error,
and its later original result controls the actual task outcome. The historical
Issue #2 live evidence is USER_EXECUTED_LIVE_EVIDENCE. Phase 3 user-executed
live Case A (`ses_f21e09d97ffeiyjqAvmZuDRxa9`) confirmed Kael-mediated,
role-pure one-round evidence and the same Sorin session continuing twice;
Case B (`ses_f21dad776ffevU6A5qKcenexjh`) confirmed zero Sorin consultations
on a simple deterministic defect. Both families completed with zero unknown or
unresolved work. Phase 3 evidence class: USER_EXECUTED_LIVE_EVIDENCE; see
`tests/role-purity/RUNME.md` for the historical manual fixture instructions.

## Local/bootstrap installation

From an Olympus source checkout, project bootstrap targets the **root of a separate, trusted Git project** on Windows with Git and PowerShell 7 available. OpenCode project installation additionally requires the OpenCode CLI and configured models; Codex-only project installation does not invoke OpenCode. The public installer can be launched from Windows PowerShell 5.1 or PowerShell 7 and delegates bootstrap to installed `pwsh`. `-Scope project` remains the default and its behavior is compatible with beta.5; `-Harness` accepts `opencode` (default), `codex`, or `all`, case-insensitively. The v0.4.0 and v0.4.1 immutable validation tags both failed release validation because of release-facing documentation contradictions; neither resulted in a GitHub Release. `-Scope global` writes to the evidenced harness user directories, does not overwrite global base config, and is currently Windows-qualified. Global OpenCode runtime discovery is `GAP`, while Codex global runtime is `SUPPORTED` based on supplied runtime evidence. `-Version` accepts only Olympus SemVer `vX.Y.Z`, `vX.Y.Z-alpha.N`, `vX.Y.Z-beta.N`, or `vX.Y.Z-rc.N`; the remote source must be the immutable matching tag.

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

The Aegis migration preserves `/maintain` while changing its effective agent ID from `maintenance` to `aegis` and its model target to GPT-6 Luna Max. Bootstrap recognizes an exact, hash-verified owned legacy manifest, removes the old `maintenance.md` agent, installs `aegis.md`, and validates effective Aegis discovery; unowned or modified retired files remain conflict/drift blockers. Phase 4C qualification includes this managed-upgrade path, command routing, and Kael's no-Aegis-child boundary. Interactive command execution is not simulated by the static/bootstrap harness.

Olympus does **not** require a globally clean target Git worktree. Unrelated modified, staged, untracked and tool-generated files (including unrelated content under `.opencode/`) are allowed and preserved. Safety is based on explicit managed destinations and ownership hashes, Git-root validation, and path containment; unsafe targets and unmanaged destination collisions still block. The installer never stashes, resets, cleans, stages, or normalizes user work.

If drift occurs, inspect the reported path and manifest, back up any intentional edits, then restore the affected owned file from a known-good installation/revision before retrying. Do not delete the manifest or force an overwrite to bypass ownership checks. If the manifest itself is damaged or you cannot establish the installed baseline, stop and investigate before reinstalling; preserve unrelated work.

## Qualification

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
pwsh -NoProfile -File ./tests/aegis-recovery/qualify.ps1
pwsh -NoProfile -File ./tests/completion-gates/qualify.ps1
pwsh -NoProfile -File ./tests/result-reconciliation/qualify.ps1
pwsh -NoProfile -File ./tests/maintenance-handoff/qualify.ps1
pwsh -NoProfile -File ./tests/maintenance-handoff/qualify-fidelity.ps1
```

`tests/maintenance-scope/qualify.ps1` checks byte-zero frontmatter in both canonical and generated files, and `tests/authority/qualify.ps1` is the live effective-agent probe that changes to this checkout and runs `opencode debug agents`. Run both after any Harness Core render has finished; do not overlap either with a process that renders/rewrites this checkout's `.opencode` outputs. This isolates only the byte/runtime-sensitive gates and does not require serializing unrelated read-only qualifications.

`check` is read-only. Harness-core qualification tests renderer idempotence,
drift/missing-output detection, canonical role/model/policy sources, and
cross-harness capability claims. Codex static qualification uses the local
bundled model catalogue when `codex` is installed; it does not run an
interactive Codex smoke.

Phase 4C covers bootstrap security and static Maintenance Plane checks; the separate Maintenance handoff qualifier covers Issue #2 policy and synthetic event ordering, not interactive delivery. The Preflight harness checks policy ordering, boundaries and a small cart/auth fixture **statically**; it does not execute agents or verify actual child count, discovery tool calls or latency. The Activity HUD harness tests presentation, installation, and plugin discovery, not interactive rendering. Adaptive Concurrency / FAST checks are static; the autonomy harness checks effective permissions and bootstrap, not interactive child execution. The release qualification's `-MockOpenCode` mode uses a task-local deterministic CLI fixture to exercise installer/bootstrap and verification behavior without contacting a live OpenCode runtime; it does not establish runtime agent/plugin discovery. The release, dirty-worktree, and installer compatibility harnesses use **local source**, not the remote tag, and do not test the interactive UI. The dirty-worktree harness checks unrelated bytes, Git status, index diffs, managed conflict/drift, reinstall and a local-source managed update. The compatibility harness launches the installer via both Windows PowerShell 5.1 (when present) and PowerShell 7 into separate disposable Git projects, and tests missing `pwsh` with a process-local PATH. Some harnesses retain disposable fixtures; check their output. The adaptive-concurrency harness's `DOC` check verifies that the README describes NORMAL as the default using only useful parallelism, FAST as explicitly requested with up to four agents, and FAST as preserving checks and task dependencies.

The Routing/Constraints, Authority Grants, Question Barrier, and Aegis Recovery harnesses verify static contracts plus deterministic synthetic cases; they do not claim interactive runtime execution or real process termination. `tests/authority/qualify.ps1` also inspects OpenCode's effective agent rules, but approval/rejection delivery and exact runtime tool behavior require an interactive OpenCode session. Report interactive evidence separately from static qualification output. The Question Barrier live race remains separate and must be reported as `RUNTIME_QUESTION_RACE: NOT AUTOMATED` unless observed.

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

## Explicit Aegis result visibility (Issue #2)

Issue #2 applies Issue #1's safety principle to the separate explicit `/maintain` handoff; it is not a duplicate of Issue #1. Track **execution** (RUNNING / TERMINAL), **result visibility** (PENDING / VISIBLE / UNAVAILABLE), and **task outcome** (only from the actual terminal Aegis result when visible) separately. An early `No tool output found` or platform error is not proof Aegis failed. An identifiable Aegis child still executing means `MAINTENANCE_RESULT_PENDING`, IN PROGRESS, wait for the original native result; do not finalize unconfirmed or retry. When the original later returns, consume it once, regardless of the earlier error. A TERMINAL / VISIBLE result of `SYNTHETIC_CONTRACT_UNVERIFIABLE` means execution completed but the substantive contract is unverifiable, not success; a result saying BLOCKED or PARTIAL retains that outcome. Native evidence positively establishing terminal failure is required for FAILED. Unknown child identity, or a known child's terminal result that remains unavailable after bounded native reconciliation, is `COMPLETION_UNCONFIRMED`, never an automatic retry of elevated work. An observably active known child must not be abandoned to finalize unconfirmed.

Olympus owns Kael's interpretation and user-facing synthesis; OpenCode owns platform tool/subagent presentation. Olympus does not claim to change or suppress OpenCode's visible "Maintenance failed" badge. Whether the historical early badge persisted after terminal completion is unproven. `tests/maintenance-handoff/qualify.ps1` uses static assertions and synthetic timelines; `tests/maintenance-handoff/live-control.md` prepares a manual read-only healthy handoff, **not executed by Aegis** and not a requirement to reproduce the intermittent error.

Issue #10's maintenance-specific exact-field contract uses `EXPECTED_OUTPUT`:
Aegis preserves requested terminal field names and values, and Kael retains
them through dependent decisions while allowing a concise additive summary.
For the confirmed missing-separator case only, Kael may recognize an exact
field token declared in `EXPECTED_OUTPUT` immediately following either exact
known metadata literal: `AEGIS_SCOPE: ACCEPTED` or `MAINTENANCE_AUTH: VALID`.
No arbitrary splitting, fuzzy labels, inferred values, or duplicate required
fields are accepted; absent or renamed fields/values remain
`STRUCTURED_RESULT_INCOMPLETE`. This does not
change Issue #1 missing-result/no-blind-retry semantics. The focused
`tests/maintenance-handoff/qualify-fidelity.ps1` includes the exact runtime
reproduction synthetically; it still does not prove native Aegis-to-Kael runtime
delivery. Keep Issue #10 open until a new-session live Maintenance Handoff smoke
verifies Aegis's terminal output and all exact values available to Kael.

## Trusted-project execution

Explicitly bootstrapped projects are treated as trusted. Kovan can edit and use shell within its assigned task ownership; Nox can use shell for validation but does not edit source. `WRITE_SCOPE` is an orchestration ownership contract, **not an OS sandbox**: shell can access paths beyond it, so agent instructions still matter. Native `external_directory` ASK prevents a blanket path-taking-tool grant outside the runtime root. Bootstrap target safety (Git root, containment, conflict and drift checks) remains separate and stricter; agent trust never relaxes installation checks.

## Activity HUD

The passive, read-only plugin uses native OpenCode child-session list and status to show running agents and their tasks. It appears only when direct children are active; it does not spawn sessions, poll, or alter orchestration.

## Aegis Plane (explicit maintenance operations)

Kael → Aegis: **DENIED**; child → Aegis: **DENIED**. User → `/maintain <task>` → Aegis accepts the delivered task in any repository. Aegis is hidden, cannot self-activate, and cannot accept automatic escalation or broaden task scope.

Fresh command entry immediately emits `MAINTENANCE_AUTH: VALID` and `AEGIS_SCOPE: ACCEPTED`, then executes the delivered task. No classification phase, repository ownership gate, independent invocation proof, envelope, durable authorization marker or provenance reconstruction. Same-run runtime resume preserves accepted task scope; a genuinely new execution requires `/maintain` again. An uncertain resume or unauthenticated entry fails closed immediately without tools or long reasoning.

The normal project workflow must not directly modify an Olympus-owned target, such as global Nox, or automatically invoke Aegis. Explain that project-plane boundary without broadening the task. This protection does not restrict explicit `/maintain` admission by repository or target ownership.

Ordinary trusted-project Git (status/diff, task-owned staging, explicitly requested commit/push, branch/tag work, or ordinary project release) belongs to the normal Kael/Kovan plane. Kovan may perform it only within the task's explicit repository/Git ownership; stage only task-owned paths. Destructive or high-impact operations such as history rewrite, force-push, reset/clean, destructive ref changes, or publishing require explicit, proportionate authorization, but do not route to Aegis solely because Git is involved. Explicit `/maintain` may authorize repository operations within its delivered task; it does not implicitly authorize destructive or high-impact work outside that task.

Aegis separates authorized repository administration from software-development investigation. Authorized Git operations start with Git-scoped non-mutating feasibility checks (target, scope, state, remote and tools as relevant), not application architecture. Read/authentication evidence alone does not prove remote write permission.

Parallel Aegis administration is permitted through shell and OpenCode session APIs, not through Olympus child-agent routing. It must track every launched root and descendant, join, collect and validate required results before declaring success; unknown/uncollected children mean PARTIAL or COMPLETION_UNCONFIRMED. Do not serialize independent jobs as a substitute for joining them.

The Aegis fresh-entry contract is statically qualified by
`tests/maintenance-scope/qualify.ps1`, `tests/maintenance-handoff/qualify.ps1`,
frontmatter, routing, authority, reconciliation and renderer checks. A
user-provided fresh-entry runtime smoke on 2026-09-30 returned
`MAINTENANCE_AUTH: VALID` and `AEGIS_SCOPE: ACCEPTED` in about 5.5 seconds, with
zero requested tools, file changes or child sessions. It did not qualify resume.

The final user-provided runtime smoke on 2026-10-01 passed: Aegis identity,
marker, original task scope, `MAINTENANCE_AUTH`, and `AEGIS_SCOPE` were retained;
explicit same-child `opencode run --session <id>` continuation worked. Issue #8
is **CLOSED**. The evidence and scope limits are recorded in
[ISSUE-8-CHECKPOINT-RESUME.md](ISSUE-8-CHECKPOINT-RESUME.md); this audit did not
rerun that smoke.

External work ownership is the outer lifecycle rule for work Aegis launches to fulfill the current user request: PowerShell processes, scripts/controllers, builds, tests, benchmark controllers, disposable validation and OpenCode roots created through session APIs. Normal synchronous commands whose tool call returns only on completion are already owned. **Foreground/join is mandatory**, regardless of duration or a request to run in the background: launch → track → wait/join → collect → validate → final response. Aegis briefly explains that it will wait rather than detach. Progress updates are not final responses. A launcher exit is not sufficient when subordinate work survives it; reuse the family-aware completion gate below. A reliably completing controller can own its own subordinate jobs; Aegis waits for and validates its terminal report rather than duplicating that controller's tracking. Independent external jobs can still run in parallel, provided all required jobs are joined before finalization.

Before launch, ensure the full lifecycle can be observed and joined; otherwise report BLOCKED without launching. No detached handoff, user PID/status polling, global registry, daemon or scheduled monitor. On Windows, necessary child processes must be headless (no visible console or focus stealing) while Aegis captures their output, errors, exit code and results. Prefer direct shell execution to extra child shells. On a finite timeout, inspect and safely stop owned work when possible, then report TIMEOUT/PARTIAL/BLOCKED without silently leaving required jobs active. Kael relays only the terminal Aegis outcome, not an in-progress controller as a finished task.

For local static/semantic policy and disposable external-process qualification, run `pwsh -NoProfile -File ./tests/external-work-ownership/qualify.ps1`. Its live foreground controller and parallel cases measure launch, terminal and simulated Aegis final times, but do not themselves constitute interactive Aegis-agent or visible-window observation; run an interactive `/maintain` smoke separately if required.

OpenCode v2.0.15 completion semantics: `POST /api/session/{sessionID}/command` executes a slash-command callback immediately; `POST /api/session/{sessionID}/prompt` durably admits input and schedules execution. A CLI `opencode run` exit or a root assistant response is not a session-family completion signal. `POST /api/experimental/session/{sessionID}/wait` waits for **one** agent loop to become idle (HTTP 204), not its descendants or a terminal result. `GET /api/session/active` lists only foreground drains owned by that server process: absence is not proof of terminal completion. Use `GET /api/session?parentID=<root>` (paginate), recursively discover descendants, `GET /api/session/{sessionID}` (outcome, time.idle), `GET /api/session/{sessionID}/inbox` and messages/export to verify terminal result and parent consumption. Recheck family membership before concluding. There is no documented family-wide wait in this version. Distinguish MESSAGE_COMPLETE, ROOT_IDLE and FAMILY_COMPLETE (the last is a validated workflow condition, not an OpenCode API status). If a child has no terminal outcome/result, classify it as unconfirmed even if the root has gone idle. Bounded waits must end with an honest PARTIAL/BLOCKED report rather than fabricate success.

### Question Barrier

Kael does not ask a human question while any task child is running, an original result is pending/indeterminate, or a terminal result/completion notification has not been reconciled, collected, validated and consumed. Reconcile the existing family and consume each original result once before presenting a question. Unknown work is not an empty barrier. If a user decision is already known to be a prerequisite, ask before launching dependent children. A question that becomes necessary after fan-out is deferred until the barrier is empty; while it is pending, dependent children remain pending. Deterministic decisions already specified by the request, constraints, capabilities or routing have QUESTION COUNT = 0.

### Restart and process recovery

Recovery preserves chronological evidence. Later messages, tool/process activity, progress, or a collected result outrank an older metadata snapshot. An old `session.outcome=failed` cannot override later activity; classify that identity as `STATE_INCONSISTENT_AFTER_RESTART` and continue reconciliation. Absence from `/api/session/active` means only that the session is absent from that endpoint's current list, not that it completed. Distinguish `LIVE_OWNED_WORK`, `TERMINAL_COLLECTED_WORK`, `STATE_INCONSISTENT_AFTER_RESTART`, `ORPHAN_CANDIDATE`, and `CONFIRMED_OWNED_ORPHAN`.

For any external process that may outlive its launcher/runtime, retain a minimal task-scoped receipt in the approved temporary `opencode` area: unique run ID; per-process PID and start time, executable, exact command line, working directory, parent PID and start time, ownership marker where supported, expected result path, and latest meaningful progress. Classify each process as ACTIVE (evidenced progress), STALLED (no progress for a finite task-bounded window), ORPHANED (verified Olympus/Aegis ownership, recorded owner gone, no recoverable result, and no progress), or UNKNOWN. Parent disappearance, `Responding=True`, or process-name similarity alone is insufficient. Never retry an owned active process or terminate by process name/pattern. Before terminating a verified owned stalled/orphaned process, recheck its exact identity and marker. After cleanup, seek the original output first; only the affected lost/uncollected gate may become eligible for explicit revalidation, and only repeat it when safe and duplication is ruled out. Missing output is neither failure nor retry permission; consume the original result once.

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
