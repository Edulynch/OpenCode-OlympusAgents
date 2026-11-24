# Development & qualification

For Olympus maintainers, contributors, installation debugging, qualification, and release engineering. For first-time setup, start with the [README](../README.md).

## Promotion and automatic releases

Contributor work targets `develop`; only a human manually merges a canonical
same-repository `develop` → `master` PR. There is no automatic merge, PAT, or
release dispatch. CI covers PRs to both branches while retaining the exact
required `FAST / Windows` name. On 2026-11-23, the observed `master` ruleset
required a PR and `FAST / Windows`, required zero independent approvals, and
blocked branch deletion and force pushes. Recheck the live ruleset before
rollout; this source change does not alter GitHub settings. The observed
repository also deleted branches on merge. Disable that setting for `develop`
before the first promotion, or GitHub can delete the long-lived source branch.

PRs targeting `master` run `Promotion source` from base-owned
`pull_request_target` metadata only: no checkout, PR code, or secrets. The job
checks the canonical repository and exact `develop` head / `master` base, then
sets that status on the PR head SHA using `statuses: write`. A status name alone
does not prove which GitHub App supplied it. First observe same-repository and
fork allow/deny outcomes and the status's source-app attribution; only then
consider requiring `Promotion source` in the ruleset with its GitHub Actions
integration bound. Until that hosted evidence exists, retain the existing
required checks and treat the source-status/ruleset integration as a rollout
gate, not as proved by local YAML tests.

The release workflow is push-only on exact `master` in the canonical repository.
It remains off unless repository variable `OLYMPUS_RELEASE_ENABLED` is exactly
`true` (unset is off). It rejects created/deleted/forced refs, stale SHAs,
direct pushes, other branches/forks, non-merge commits, ambiguous PR metadata,
and anything other than one merged canonical `develop` → `master` PR whose
merge SHA, first parent, second parent, and event `before` SHA agree. It also
requires that exact SHA still be current `master` before each write boundary.
An unchanged installer version is a successful no-op, including when a
historical tag already exists; migration does not select or bump a version.
For a new version, aligned stable installer markers, a reviewed versioned
changelog block, monotonicity over the prior candidate and latest public
release, and a collision-free tag are required.

### Hosted read-only qualification

After the separate qualification workflow is merged to the protected default
`develop`, a maintainer may manually dispatch **Release / read-only hosted
qualification** from `develop` while `OLYMPUS_RELEASE_ENABLED` is exactly
`false`. The job is limited to the canonical repository and `develop`; it has
only `contents: read` and `pull-requests: read`, does not persist checkout
credentials, and its dedicated API client can issue only GET requests.

The run checks the dispatch SHA against current `develop`, then reads current
`master`, its two parents, and associated PR metadata. It requires the current
master SHA to be the exact merge commit of one closed, merged canonical
`develop` → `master` PR whose head SHA is the merge's second parent. It reads
`install.ps1` at the first parent and current master and uses the release
helper's existing stable-version and no-op classifier; only equal installer
versions qualify as a no-op. It then selects GitHub's latest published stable
release, resolves its exact annotated tag, and confirms that its commit differs
from current master and is rejected by the production `TAG_CONFLICT` predicate.
Missing, malformed, or non-conflicting tag state fails closed as
`TAG_CONFLICT_NOT_EVALUATED`, not as a successful smoke.

This workflow creates or changes no tag or release and cannot verify
`contents: write` draft visibility or the public installer endpoint lifecycle.
It does not enable release, select a version, or replace the production
`master`-push workflow. It is a hosted read-only metadata rehearsal, not release
authorization or an installability claim.

GitHub's repository immutable-release settings endpoint requires administrator
read access, which the ordinary Actions token may not have. The workflow uses
the endpoint when accessible and fails if it reports immutability disabled. If
the endpoint returns 401/403, the explicit repository variable
`OLYMPUS_RELEASE_IMMUTABILITY_CONFIRMED=true` is a manual activation
precondition: an administrator must first enable and verify immutable releases
in repository settings. That variable is an owner assertion, not live platform
proof; remove it before changing the setting. A 404, unset assertion, or any
other API error fails closed. The workflow additionally requires GitHub to
report `immutable=true` after publication.

Each new release run first qualifies the exact push SHA read-only, then creates
an annotated tag, fetches and peels that remote tag, and runs the tagged source
archive through the isolated Windows release qualifier before creating a
**draft**. The draft contains only `install-olympus.ps1` and
`install-olympus.sh` bytes read from that exact commit; their SHA-256 values and
the reviewed notes are checked before publishing. Separate jobs hold
`contents: write` only for tag creation, draft/assets, or publication. Those
jobs do not check out repository code or execute tests/assets; there is no PAT
and no second workflow triggered by the `GITHUB_TOKEN` tag/release writes.
Existing mismatched tags, releases, asset digests, ownership, or immutable
state are conflicts; the workflow never moves, deletes, recreates, or edits a
published release.

The release workflow serializes its runs but GitHub keeps only one pending
concurrency run and a newer pending run may replace it; this is not a FIFO
queue. Promote one PR at a time and wait for its workflow to finish before
merging another. Every writer rechecks current `master`, but a branch update
can race with a remote API operation; sequential promotion is an operational
precondition. If a failed run left an orphan tag, do not delete or recreate it;
investigate and advance only through an authorized new version. A matching
draft for the same SHA can resume after the read-only gates pass.

Create the matching **draft**, attach both assets **before publishing**, and
verify its bytes match the tag; publish only with immutability enabled.

After publication, the workflow verifies `releases/latest`, immutable stable
metadata, the exact annotated tag and both public asset bytes. This is not a
real installer lifecycle: the public latest-endpoint install/VerifyOnly/
uninstall check remains pending for an isolated supported Windows environment
and the documented Linux route. Mocked or local tag qualification is not
equivalent to that endpoint gate. Do not announce availability until the
separate lifecycle evidence is complete; never point executable installation
sources at `master` or `develop`.

The intended public URL is:
`https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1`.
This procedure is documentation, not authorization to change a version, tag,
release setting, PATH, or real installation.

## Optional native Git hooks

The checked-in `.githooks/pre-commit` and `.githooks/pre-push` are **opt-in** and are never installed by cloning OlympusAgents or by an Olympus installer. The pre-commit hook runs the Python secret gate with the official Gitleaks `v8.30.1` executable acquired only from supported release archives whose pinned SHA-256 is verified before execution. It scans Git's active staged-index diff (including an alternate `GIT_INDEX_FILE` used for partial commits), fully redacts and suppresses scanner output, and blocks on a finding or any acquisition/scanner error. It requires Python 3.11+ and network access when no verified archive cache is available; it needs neither pre-commit nor Go. `OLYMPUS_GITLEAKS_CACHE_DIR` may name an optional cache, whose archive is hash-checked on every use.

The native pre-push hook reads Git's update records from stdin. Empty input and deletion-only pushes run no checks because no content is going out. Exactly one non-deletion ref is supported per invocation; multiple content updates are rejected rather than partially qualified. Its local object must peel to the clean checked-out `HEAD`, including annotated or lightweight tags pointing there. A first push/new remote ref checks all tracked paths; later updates use the remote-old-to-local commit diff, retaining deleted paths. If the remote's old object ID is unavailable in the local object database, the range cannot be verified and the push fails closed; fetch that remote history and retry. Push one checked-out branch or a tag at `HEAD` at a time.

For content pushes, the gate requires tracked files and the index to be clean and never stashes or resets user state. It always runs the documentation checker, then runs the existing offline **FAST** profile when any changed path is not documentation-only. Root Markdown and Markdown/images under `docs/` or `specs/` are documentation-only; Core/prompts, tests, code, configuration, and unknown paths select FAST. FAST requires PowerShell 7 (`pwsh`). A manual `python -B scripts/pre_push.py` invocation remains separate and checks all tracked paths without inventing a pushed ref. Push checks do not run Gitleaks, FULL, RUNTIME, or runtime/API checks. The hooks are locally qualified only on Windows with Git for Windows, Python 3.11+, and PowerShell 7; no Linux/macOS hook support is claimed. Hooks can be bypassed; CI secret/history and qualification gates remain mandatory.

From the source checkout root, before opting in, inspect all current Git hooks, the effective `core.hooksPath`, any hooks redirected there (not only `pre-commit`/`pre-push`), `.githooks`, the current branch, and linked worktrees. Switching `core.hooksPath` replaces the active hooks directory and can bypass unrelated hooks; reconcile existing hooks manually before proceeding. In Windows PowerShell:

```powershell
git status --short --branch
git branch --show-current
git worktree list

git config --show-origin --get core.hooksPath
$configuredHooks = (git config --path --get core.hooksPath 2>$null | Out-String).Trim()
if ($configuredHooks) {
    $hookDirectory = if ([IO.Path]::IsPathRooted($configuredHooks)) {
        $configuredHooks
    } else {
        Join-Path (Get-Location) $configuredHooks
    }
} else {
    $hookDirectory = (git rev-parse --path-format=absolute --git-path hooks).Trim()
}
Get-ChildItem -LiteralPath $hookDirectory -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath .githooks -Force -ErrorAction SilentlyContinue
```

Only after reconciling that state, enable both native hooks for this repository:

```powershell
git config --local core.hooksPath .githooks
```

Git runs hooks only when their committed mode is executable. When publishing from Windows, maintainers must preserve mode `100755` for both hook files, for example with `git add --chmod=+x .githooks/pre-commit .githooks/pre-push`; this is a publication detail, not part of local activation.

The setting is local to the repository and may affect sibling worktrees. It persists across branch changes: before using an older branch, verify that it contains `.githooks` and the referenced scripts; otherwise restore the prior hook path or unset the local setting until returning to a branch with these hooks.

For rollback, restore the exact prior **local** value if one existed:

```powershell
git config --local core.hooksPath '<previous-local-value>'
```

If there was no prior local value, remove the opt-in setting:

```powershell
git config --local --unset core.hooksPath
```

That returns Git to an inherited global/system path if one exists, or its default `$GIT_DIR/hooks` directory if none exists. Local hooks remain optional and do not replace CI: CI independently scans tracked and non-ignored current files plus selected Git history. Its pinned release archive uses bounded retries and may be cached by the workflow; each downloaded or restored archive must pass the expected SHA-256 check before execution. A cache-write failure after verified download does not abort scanning, because caching is optional.

## Architecture

Olympus Core defines canonical role responsibilities, model intent, routing, authority, result lifecycle, and contextual maintenance semantics; see the [contextual maintenance policy](../olympus/policies/maintenance-context.md). OpenCode is the only currently supported runtime and the target for new capabilities. Kael is the single conceptual ROOT ORCHESTRATOR, represented as OpenCode's primary agent. The eleven canonical Core roles and their responsibilities remain intact; maintenance uses Kael's normal workflow, selected from the identified target repository and task intent.

### Current support and adapter contract

- **OpenCode — only supported runtime.** Design new features, agents, commands, architectural improvements, and runtime capabilities for OpenCode. Do not add Codex support or compatibility fallbacks.
- Public install/update/uninstall is global/OpenCode-only. Project-scoped OpenCode configuration, overrides, apply/recovery, status, and read-only doctor remain separate CLI behavior, not project installation.
- Use current OpenCode evidence for runtime qualification; static checks do not establish live runtime behavior.

The OpenCode capability contract and its evidence are documented in the [harness guide](HARNESSES.md) and [capability matrix](HARNESS-CAPABILITIES.md).

Kael checks feasibility, repository identity, and task scope using minimal preflight before delegating research or planning. The same Kael workflow handles OlympusAgents development and ordinary project work; there is no separate maintenance command, role, or authorization plane. Kael does not explore repositories, conduct technical research, implement, or execute technical validation; responsible roles gather evidence and perform those tasks, while Kael reconciles their results and owns acceptance. A direct answer from existing context uses no tools or children. The native `/goal` surface remains opt-in and user-selected where available. Feasible work uses only materially needed task-scoped discovery (none, targeted, or bounded subsystem), widening only for an unresolved target/boundary, evidence of wider impact, or a genuinely repository-wide request.

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
OpenCode agent metadata must not append wildcard `external_directory` rules.
OpenCode evaluates agent rules after project rules, so an agent-level wildcard
ASK can override a more-specific project or runtime DENY. This supports
repositories outside the current root—including monorepo/sibling/multi-repo
layouts—only with effective native permission and exact Kael scope. Layouts
are not hardcoded. Native DENY is never elevated by text, WRITE_SCOPE, or an Authority Grant. Repository identity
classifies whether canonical OlympusAgents source is the task target; it does
not grant access to a separate checkout or installed Olympus runtime resources.

The active repository is the verified target of the task, not implicitly the
OlympusAgents source checkout. Each repository receiving source edits needs its
own canonical root and bounded, repository-relative WRITE_SCOPE; a scope for one
root cannot grant access to another. Separately requested non-source external
effects (for example, temporary test artifacts, a shared Git hook, or a global
installation) require an exact target, operation, effect, and applicable native
permission rather than a fabricated repository-relative WRITE_SCOPE. Unrelated
external files, protected paths, and native DENY remain off-limits. Ordinary
test/build temporary output does not grant permission for unrelated source edits.

### Trivial task / authority fast path

For a small deterministic change with known scope and established ownership,
one scoped Kovan writer is sufficient when there is no
architecture/uncertain-diagnosis/cross-subsystem or high-risk work and acceptance
can be checked cheaply from supplied evidence. Kovan may run focused checks as
part of implementation. Kael evaluates that evidence for acceptance; it does
not implement, explore, research, or execute technical validation. Veyra is not
required to rediscover established ownership, Nox is not required unless
distinct test/runtime evidence is needed, and Vera/Atlas/other roles are not
invoked just because they exist. Explicit independent review remains required
when requested. An answer available from existing context uses no tools or
children. This is an eligible-task policy, not an automatic route for every
apparently small task.

For an eligible scoped `NATIVE_ASK` write, Kael determines exact operation,
`WRITE_SCOPE`, repository root and ownership before launch; one Kovan writer is
the only child, attempts the exact native operation, and waits for OpenCode's
native Approve/Reject result. Approval permits the operation to continue but
does not expand scope. Kael evaluates supplied evidence against the requested
target and exact scope proportionally.
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
synthesis; it evaluates supplied evidence and does not perform repository exploration,
technical research, implementation, or technical validation. Veyra supplies
discovery; Orin architecture; Kovan implementation; Nox runtime/test evidence;
Vera independent review. Atlas optionally plans execution order for already-scoped, already-architected changes without discovering, editing or validating; Thales reasons over actual
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
Issue #1's normal-child result reconciliation remains authoritative. Phase 3 user-executed
live Case A (`ses_f21e09d97ffeiyjqAvmZuDRxa9`) confirmed Kael-mediated,
role-pure one-round evidence and the same Sorin session continuing twice;
Case B (`ses_f21dad776ffevU6A5qKcenexjh`) confirmed zero Sorin consultations
on a simple deterministic defect. Both families completed with zero unknown or
unresolved work. Phase 3 evidence class: USER_EXECUTED_LIVE_EVIDENCE; see the
[historical manual fixture instructions](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/5e9bec1a5eb51d9bfcac93931f0d165a48b4a53c/tests/role-purity/RUNME.md).

## Local/bootstrap installation

The public installer is global/OpenCode-only; use the current [installation guide](INSTALLATION.md) for supported installation and safety instructions. Project-scoped CLI configuration features are also available for OpenCode: model overrides, preview/apply, matching recovery, status, and read-only doctor. They do not install a project.

## Managed installation and recovery

An existing current-format project manifest at
`.opencode/orchestrator-install.json` uses `schema_version=1`,
`scope=project`, `installed_harnesses=["opencode"]`, an
explicit nonempty `installed_version` and `installed_from_commit`, and the
current 15-path managed inventory with SHA-256 hashes. Optional opaque
harness-provenance or detection metadata is not ownership. An existing current
global manifest uses the same path and schema with `scope=global`, exactly
OpenCode, `installed_version=local` or a release tag, a nonempty
`installed_from_commit`, and a valid `default_agent_receipt`. With an existing
user-owned global config, the 15 base resources are managed and the config
remains unowned; when Olympus creates the config, all 16 resources are managed.
Both forms are current.

Overrides use `schema_version=1` and an `overrides` map; a missing override file
means empty, with project values taking precedence over global overrides and Core
defaults. Unsupported or incomplete installation formats fail closed without
automatic conversion, adoption, or deletion. A complete current-format
installation remains valid regardless of the release that created it. Remove
an unsupported older installation only through its matching release. Managed
drift and unowned conflicts remain protected; no user files are silently
overwritten.

The global configuration may additionally contain
`"orchestration":{"max_children":N}` for integer `N` from 1 to 8; absence means
the Core default of 4. This is a Kael prompt ceiling for direct children per
root session, not scheduler enforcement or a shared cross-root quota. Model and
effort setters preserve it. The renderer accepts an in-memory ceiling, while
the ordinary render/check path retains the Core default bytes; global installer
updates obtain non-default Kael text from the renderer without writing generated
source outputs. Project config remains strict and consumes the global ceiling
only through explicit project config apply.

`olympus completion powershell|bash` prints opt-in current-shell registration.
Completion candidates come from the argparse command tree and do not resolve
the source checkout, read user configuration, inspect the filesystem, or query
providers/networks. Native shell input is passed as framed data to the read-only
candidate route; profiles are never modified automatically.

Olympus does **not** require a globally clean target Git worktree. Unrelated modified, staged, untracked and tool-generated files (including unrelated content under `.opencode/`) are allowed and preserved. Safety is based on explicit managed destinations and ownership hashes, Git-root validation, and path containment; unsafe targets and unmanaged destination collisions still block. The installer never stashes, resets, cleans, stages, or normalizes user work.

If drift occurs, inspect the reported path and manifest, back up any intentional edits, then restore the affected owned file from a known-good installation/revision before retrying. Do not delete the manifest or force an overwrite to bypass ownership checks. If the manifest itself is damaged or you cannot establish the installed baseline, stop and investigate before reinstalling; preserve unrelated work.

## Qualification

`/olympus.ultra <prompt>` asks Kael to maximize useful independent parallelism within the configured ceiling and existing gates. `FAST` below names only OlympusAgents' offline qualification profile; it is not a user-facing execution mode or trigger.

### TFR in software built with Olympus

The canonical **TFR (risk-based focused testing)** decision rule lives in
`olympus/policies/routing.md` and is delivered to Kael through the supported
OpenCode adapter. For an unrelated user repository, Kael
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
- **Changes depending on actual runtime behavior:** use focused OpenCode RUNTIME evidence where available. Static or legacy Codex fixtures are not current runtime qualification.
- **Failures:** fix the issue and repeat only the affected verification before widening coverage. Do not automatically rerun all of FULL after every adjustment.
- **Evidence reuse:** reuse a recorded result when it proves the same acceptance criterion and the relevant source revision/working-tree state, configuration, dependencies, and runtime conditions remain applicable. Evidence does not expire solely with age; mark it stale when a relevant input changed or applicability/scope cannot be established. Use revision/diff/context evidence rather than repeating hashes unless integrity or ownership specifically requires them. Unknown evidence is not PASS.
- **External-provider boundaries:** Olympus qualification covers Olympus-controlled components and declared integration behavior. Respect each user's stated economic and authentication constraints; do not impose global prohibitions on API keys or paid providers, and do not change authentication without authorization. Do not investigate a user's subscriptions, billing, external entitlements, or authentication settings absent a specific authorized need. Classify `BLOCKED_PROVIDER_ENVIRONMENT` only when observable evidence shows a blocking failure originates outside the integration contract OlympusAgents controls; defects in OlympusAgents' own integration remain product defects.
- **Non-blocking diagnostics and time:** keep auxiliary-harness failures separate from product outcomes, insufficient evidence, and real security blockers; one does not automatically invalidate another. Whenever duration is collected or reported, record `TECHNICAL_EXECUTION_TIME` (active tool/process execution, excluding waiting and coordination) and `TOTAL_ORCHESTRATION_TIME` (task start through validated completion, including waiting and coordination) separately. Mark unobserved values unavailable; do not infer them.

FAST, FULL, and RUNTIME retain their current behavior, and these rules do not replace existing mandatory validation. RUNTIME does not replace FULL, nor FULL RUNTIME. Do not omit failures or report unrun checks as PASS. Avoid unnecessary FULL repetitions without imposing a rigid limit when material changes warrant further validation. Present the relevant diff and evidence for human review at the end; add no separate automated review stage unless required or justified by risk.

Some profile scripts still invoke legacy Codex or dual-harness fixtures. These guard historical test contracts only; they do not establish or imply current Codex support.

Use the following existing checks as starting points for development validation from the source checkout root. This selection does not replace mandatory project, CI, integration, or release gates. Run affected integration checks when shared contracts or installer behavior are affected. Use an existing RUNTIME slice or native smoke when correctness depends on actual harness, process, or UI behavior; static checks alone do not establish native behavior.

| Change | Recommended check |
| --- | --- |
| Release provenance and version/tag policy | `python -B -m unittest discover -s tests/release -p 'test_release_workflow.py' -v` |
| Release-facing README, changelog, or documentation contracts | `pwsh -NoProfile -File ./tests/release/tag-transition-stability.ps1` |
| Olympus Core, renderer, or OpenCode adapter contracts | `python3.11 -B ./scripts/render_harnesses.py check --harness opencode`<br>`python3.11 -B ./tests/harness-core/qualify.py` |
| Completion-gate policy | `pwsh -NoProfile -File ./tests/completion-gates/qualify.ps1` |
| Activity HUD presentation logic | `node --test ./tests/activity-hud/activity.test.mjs` |

### Unified contributor profiles (Issue #11)

From the source checkout root, run exactly one selected profile:

```powershell
pwsh -NoProfile -File ./scripts/qualify.ps1 -Profile FAST
pwsh -NoProfile -File ./scripts/qualify.ps1 -Profile FULL
pwsh -NoProfile -File ./scripts/qualify.ps1 -Profile RUNTIME
```

The profile selections are defined in
[`scripts/qualify.ps1`](../scripts/qualify.ps1); CI can add checks outside those
profiles.

**FAST** is offline-only: the pre-push unittest suite; Harness Core's
read-only checkout validation and disposable fixture renders; bootstrap,
orchestration, and role-contract
qualifiers; contextual-maintenance and structured-output checks; and
external-work ownership static contracts. It never queries a real OpenCode
runtime, does not run the external-work ownership disposable-process
slice, and does not render generated outputs in the checkout. The historical
handoff-fidelity suite and the nine installer/history selectors reserved for
FULL are not included. Direct qualifier defaults remain unchanged.

**FULL** runs FAST exactly once, then the offline global OpenCode API-query
contract, the Windows global-installer fixture, the release qualifier with
`-MockOpenCode`, installer compatibility, and dirty-worktree checks, followed by the Offline
slices of Authority, Activity HUD, Argus, Atlas, Helios, Talos, Thales, Phase 4C,
and Autonomy. Those nine slices execute their existing
local installation, history, upgrade, drift, conflict, and synthetic checks;
Activity also runs its local Node presentation tests. For bootstrap-driven
offline fixtures only, they temporarily put the existing
`tests/release/fixtures/opencode.ps1` qualification stub first on `PATH`, then
restore the original process environment. That explicit deterministic fixture
supports installation setup; its output is not treated as live OpenCode
discovery or effective-runtime evidence, and RUNTIME never uses its output as
runtime evidence. The
FULL dirty-worktree installer check uses the same fixture only for its local
OpenCode `--version` preflight. FULL does not contact a real OpenCode runtime.
It does not call tag-transition stability a second time; that check is
already nested in release qualification. Phase 11's historical corpus is
retained as evidence, not executed as current contract tests by these profiles.

| CI check | What it verifies |
| --- | --- |
| [`FAST / Windows`](../.github/workflows/fast.yml) | Required for `master`; contributor PR CI runs on both `develop` and `master`. Runs offline FAST, release policy tests, authority checks, the packaged CLI lifecycle with mocked release downloads, native PowerShell completion, and isolated installer and worktree fixtures. The post-install fixture uses mocked OpenCode. |
| [`Read-only and integrated CLI coverage / Linux`](../.github/workflows/fast.yml) | Read-only CLI without TOML Kit, followed by integrated CLI tests in a dedicated environment. |
| [`Project manifest, writer-lock, and CLI safety`](../.github/workflows/fast.yml) | Shared Python manifest and lock tests on Windows and Linux. Windows retains PowerShell-specific coverage; Linux checks the POSIX launcher, global install, packaged CLI, and release routing without PowerShell. No macOS runner. |
| [`Secret and link gates`](../.github/workflows/secrets.yml) | Secret scanning and documentation links on Windows and Linux. |
| [`Global-only ASK/DENY / Windows V2 API`](../.github/workflows/native-permission-api.yml) | Real OpenCode V2 permission handling with a local model stub. The assertion rejects ASK through the API; it does not test the interactive permission UI or a hosted model. |
| [`Promotion source`](../.github/workflows/promotion-guard.yml) | Base-owned PR metadata check that writes a distinct status to the exact PR head. Hosted source-app attribution and ruleset association still require platform verification. |
| [`Release / immutable master promotion`](../.github/workflows/release.yml) | Opt-in exact-SHA provenance, read-only candidate/tag qualification, isolated tag/draft/publish jobs, and public metadata/asset-byte checks. Real public installer lifecycle remains a separate pending gate. |

A local FAST pass is not a pass for all CI jobs. Use display names that describe
the behavior and distinguish real runtime from mocked fixtures. Keep required
check names and internal `unittest -k` selectors stable; compare the selected
cases if you change a selector or the test names it matches.

**RUNTIME** does not include FULL or FAST. It runs external-work ownership
disposable process cases and the
existing effective-agent/plugin boundaries for Authority, Activity HUD, Argus,
Atlas, Helios, Talos, Thales, Phase 4C, and Autonomy. Phase 4C's runtime
selector includes P4C-2/11/12/14 and the contextual-maintenance roster check.
Managed-file drift and fail-closed refusal/preservation checks for unsupported
older manifests and retired-resource conflicts remain in FULL Offline and the
direct Both qualifier, not RUNTIME; they do not assert migration, adoption, or
automatic cleanup.
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
unrelated offline suites and manual interactive smokes are not run. If OpenCode
is unavailable, dependent checks are `NOT RUN`, never PASS; the
aggregate is `PARTIAL` (exit 2). Only an explicitly designated missing
prerequisite can produce `NOT RUN`; an unclassified child exit 2 is a failure.
OpenCode global custom-agent discovery is `SUPPORTED` for isolated Windows
V2.0.26 (Issue #7: real v0.4.6 global install, loader active, 12/12 agents,
2/2 controls, Kael configuration-level selection). The unified RUNTIME profile
still excludes the historical long-running `tests/global-runtime/qualify.ps1`:
that diagnostic does not yet observe plugin activation completion, so an early
empty roster is inconclusive. Do not repeat it as a release gate or infer model
execution from the reported discovery PASS. Historical Codex global-runtime
evidence is not current product support.
A completed RUNTIME profile still does **not** qualify interactive child
execution, native ASK UI or human approval/rejection, the question race, or
Activity TUI rendering; those remain separately observed/manual
evidence.

Use the [Prompt Book](../tests/prompt-book/README.md) for an opt-in automated
read-only smoke against real Kael and Nox sessions, and for separate manual
scenarios covering role boundaries, write delegation, and blocked verification.

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
Currently supported OpenCode identifiers are rendered from that file: Sol uses
`openai/gpt-6.2-sol`; Luna remains GPT-6 Luna. Sol roles retain `high` except
Thales (`xhigh`); Luna roles retain `max`. Change a family identifier in Core
and re-render—do not update agent files or installer model tables by hand.
Qualify the model mapping and installer check with:

```powershell
python3.11 -B ./tests/harness-core/qualify.py
```

Earlier runtime evidence in the roadmap remains a historical record of the
model actually used at that time; it is not a current model assignment.

From the source checkout root, use the current harnesses (PowerShell 7; some require `opencode`, Git, and Node):

```powershell
python scripts/render_harnesses.py render --harness opencode
python scripts/render_harnesses.py check --harness opencode
python tests/harness-core/qualify.py
pwsh -NoProfile -File ./tests/worktree-activation/qualify.ps1
pwsh -NoProfile -File ./tests/worktree-activation/native-smoke.ps1
pwsh -NoProfile -File ./tests/trivial-fast-path/qualify.ps1
pwsh -NoProfile -File ./tests/phase4c/qualify.ps1
pwsh -NoProfile -File ./tests/authority/qualify.ps1
pwsh -NoProfile -File ./tests/activity-hud/qualify.ps1
pwsh -NoProfile -File ./tests/adaptive-concurrency/qualify.ps1
pwsh -NoProfile -File ./tests/autonomy/qualify.ps1
pwsh -NoProfile -File ./tests/release/qualify.ps1 -MockOpenCode
pwsh -NoProfile -File ./tests/release/tag-transition-stability.ps1
pwsh -NoProfile -File ./tests/release/installer-compatibility.ps1
pwsh -NoProfile -File ./tests/release/dirty-worktree.ps1
pwsh -NoProfile -File ./tests/preflight/qualify.ps1
pwsh -NoProfile -File ./tests/routing-constraints/qualify.ps1
pwsh -NoProfile -File ./tests/question-barrier/qualify.ps1
pwsh -NoProfile -File ./tests/completion-gates/qualify.ps1
pwsh -NoProfile -File ./tests/result-reconciliation/qualify.ps1
python -B ./tests/maintenance-scope/qualify.py
pwsh -NoProfile -File ./tests/structured-output/qualify.ps1
```

`tests/maintenance-scope/qualify.py` checks the contextual-maintenance policy, target identity boundary, Kael's delegation-only work boundary, unchanged native tool metadata, opt-in `/goal`, current roster, and absence of retired product outputs. It is static and does not claim interactive model behavior. `tests/trivial-fast-path/qualify.ps1` checks the one-Kovan fast path and synthetic acceptance cases; `tests/completion-gates/qualify.ps1` checks static pending-work/completion wording plus synthetic gates. Neither claims live routing or model behavior. `tests/structured-output/qualify.ps1` checks exact requested terminal-field preservation as a general Kael contract, also without claiming live model behavior. `tests/authority/qualify.ps1` stages generated runtime resources in a disposable project, so its live effective-agent probe does not depend on this checkout's `.opencode` outputs. This isolates only the byte/runtime-sensitive gates and does not require serializing unrelated read-only qualifications.

`check` is read-only. Harness-core qualification tests renderer idempotence,
drift/missing-output detection, canonical role/model/policy sources, and the
current OpenCode capability contract. Static checks do not establish live
runtime behavior.

Current code refuses unsupported older manifests and retired-resource conflicts without migration, adoption, or deletion. The Preflight harness checks policy ordering, target/ownership boundaries and a small cart/auth fixture **statically**; it does not execute agents or verify actual child count, discovery tool calls or latency. The Activity HUD harness tests presentation, installation, and plugin discovery, not interactive rendering. Ultra/performance command and adaptive-concurrency checks are static; the autonomy harness checks effective permissions and bootstrap, not interactive child execution. The release qualification's `-MockOpenCode` mode uses a task-local deterministic CLI fixture to exercise installer/bootstrap and verification behavior without contacting a live OpenCode runtime; it does not establish runtime agent/plugin discovery. The release, dirty-worktree, and installer compatibility harnesses use **local source**, not the remote tag, and do not test the interactive UI. The dirty-worktree harness checks unrelated bytes, Git status, index diffs, managed conflict/drift, reinstall and a local-source managed update. The compatibility harness launches the installer via both Windows PowerShell 5.1 (when present) and PowerShell 7 into separate disposable Git projects, and tests missing `pwsh` with a process-local PATH. Some harnesses retain disposable fixtures; check their output. The adaptive-concurrency harness's `DOC` check verifies that the README describes adaptive useful concurrency by default, Ultra as maximizing useful work only up to its configured ceiling, and all existing task dependencies and gates.

`tests/worktree-activation/qualify.ps1` is a Windows-only, disposable Git regression against the current local source. It bootstraps a main fixture using the local installer's version metadata, creates two linked worktrees (whose `.git` entries are files), confirms that neither initially discovers Kael, then provisions both through the manifest-owned helper. It checks per-checkout manifest hashes, user-file preservation, idempotence, conflicts, source drift, and invalid-manifest refusal without writes. Its OpenCode CLI is a deterministic stub; this does not verify live OpenCode runtime behavior.

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

## External work ownership

Kael owns each process, controller, build/test job, and native child session
started for the current task. Keep the task open through tracking, wait/join,
collection, validation, and finalization. Background requests do not authorize
detachment. Before launch, establish that the full lifecycle is observable;
otherwise report BLOCKED without starting it. Missing output is not failure and
never authorizes a blind retry. `tests/external-work-ownership/qualify.ps1`
checks this shared Kael contract and disposable process ownership; it is not an
interactive-agent or runtime-permission test.

### Native child waiting without active reasoning

Keeping a task pending does not require keeping a model turn active. While a
child is pending, Kael may dispatch only work already necessary to the objective,
ready, and independent under existing dependencies and concurrency ceilings; it
does not start opportunistic research, verification, or unrelated work. With
native background children, Kael may continue only that work; otherwise, when
none remains, it sends at most one IN PROGRESS update and ends the turn. Native
child notifications resume the parent to reconcile the original results. If
work is still pending and no necessary independent work is ready, it awaits the
notification without repeating unchanged updates or polling. Treat an earlier
running/partial status as stale until new native evidence arrives.
Yielding does not complete the task, cancel children, release writer ownership,
or authorize replacement invocations. Final completion still requires all
required terminal results to be collected, validated, and consumed once.
Repeated reasoning, no-op calls, unrelated skill loads, sleeps, and polling are
not waiting mechanisms.

`tests/completion-gates/qualify.ps1` checks this prompt contract and synthetic
completion/ownership gates; it does not establish live notification delivery or
latency. For a focused live regression, use the persistent OpenCode service and
a new session loading the corrected Kael prompt, with a small explicitly
requested batch of independent token-only children and no file writes:

- Retain each original child session ID and use native trace/event timestamps
  for task start, each launch, each child's terminal result, parent receipt, and
  the final synthesis. Do not ask the model to estimate timestamps or add polling.
- Check that idle waiting produces no repeated reasoning or unrelated tool calls,
  that native notifications resume reconciliation, and that only the original
  children are consumed before the final response.
- Separate launch overhead, child execution, result-delivery delay, and final
  synthesis. Record `TECHNICAL_EXECUTION_TIME` and `TOTAL_ORCHESTRATION_TIME`
  separately; mark unavailable timestamps or active-execution totals unobserved.
  Overlapping child durations must not be summed as wall-clock latency.
- Report the actual timings and failures; a static PASS or successful invocation
  count is not proof of latency improvement. The historical v2.0.15
  `tests/completion-gates/live-family.ps1` is not a current-runtime benchmark.

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

For each release, first agree and review the new product version in the
`develop` change; do not bump a version as part of a workflow migration. Open a
manual `develop` → `master` PR and wait for all required hosted checks. Do not
merge a second promotion while the release workflow is active. The exact
workflow sequence is:

1. Validate the `master` push SHA, current branch tip, canonical merged PR and
   merge parents; validate the aligned installer markers, changelog section,
   prior/latest version ordering, and tag/release state.
2. Run
   `pwsh -NoProfile -File ./tests/release/qualify.ps1 -MockOpenCode -ExpectedVersion <tag>`
   and `tests/release/github-release-notes.ps1` on the exact candidate SHA. The
   candidate job has read-only permissions; the deterministic OpenCode stub is
   explicitly mocked and does not establish native runtime behavior.
3. Create (or verify on an exact same-SHA retry) the annotated tag. The
   read-only tagged-source job fetches that remote tag, checks its object,
   message, and peeled commit, archives the exact tree, then runs the release
   qualifier against that extracted source with isolated Windows temp/profile
   roots. No `-SourceRoot` or real user destination is used.
4. Only after tagged-source qualification, create/resume a matching draft and
   attach exactly the PS1 and `sh` installer bytes at that tag. Compare source
   SHA-256 digests and draft asset digests before publication. Publish only
   after rechecking the exact `master` tip, tag, release body, assets, and
   immutable-release setting. Do not use npm publication or a second
   release-trigger workflow.
5. Verify `immutable=true`, `draft=false`, `prerelease=false`, the exact
   annotated tag, a timezone-aware publication timestamp, `releases/latest`,
   and downloaded public bytes for both installer assets. Then complete a
   separate disposable public-endpoint install/VerifyOnly/uninstall using the
   supported Windows process-root/CLI-root/PATH-store isolation described in
   [installation qualification](#choosing-qualification-by-change-risk) and
   the documented Linux route. Current Actions automation reports this actual
   public lifecycle as **PENDING**; a dry run or mocked qualifier is not a
   substitute. Stop and investigate if any post-publication check fails; never
   rewrite the immutable tag or release.

An unchanged version is a successful migration no-op even if a historical tag
exists. A changed version colliding with any existing tag/release—including
the historical `v0.12.4` tag at its different target—is a hard conflict. Do not
move, delete, or recreate tags to recover. Only an exact matching draft can
resume. Because the public release-by-tag endpoint may return 404 for drafts, a
valid matching tag with no public release is only a provisional candidate
state: the write-enabled draft stage must enumerate the bounded authenticated
release list and re-read exactly one same-tag draft by numeric ID. A missing,
duplicate, or unverifiable draft is an orphan/conflict requiring maintainer
investigation and an authorized later version.

GitHub concurrency is serial but not FIFO: a newer pending run may replace an
older pending run. If a candidate becomes stale before a write, the workflow
fails closed; rerun that same SHA only if it remains current and eligible.
GitHub's immutability field and tagged-source identity checks are platform
assertions, not independent signature verification by the installer.
