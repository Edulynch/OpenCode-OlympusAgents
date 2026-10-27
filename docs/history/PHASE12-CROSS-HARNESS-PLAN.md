# Phase 12 Cross-Harness Plan

**Authority and status.** This remains the authoritative reduced Phase 12 plan; its frozen design is preserved. It supersedes the historical six-workload scope recorded on `qualify/overnight-evidence-20261003-eff88d7f`, which is not restored or copied wholesale. The no-trials status records the point when this plan was frozen, not current phase status. Phase 12 is now **CLOSED**; see the [results ledger](PHASE12-CROSS-HARNESS-RESULTS.md).

## 1. Purpose and comparison limits

Compare whether OpenCode and Codex preserve the important runtime invariants for the same shared, claimed-supported capabilities represented through both harnesses: bounded routing, scope, required result handling, completion, and functional task acceptance. This is not a winner ranking, model-intelligence assessment, performance-superiority claim, or parity claim for capabilities marked `GAP`, `PARTIAL`, or `ADAPTABLE`. Capability declarations are limits on interpretation, not trial results. Do not emulate or equalize unsupported features to manufacture parity. Do not repeat Phase 11 merely for symmetry.

## 2. Frozen execution design

### Default matrix and order

The default is exactly three matched pairs (six clean, isolated executions):

| Pair | Workload | Execution 1 | Execution 2 |
|---|---|---|---|
| Trial 1 | `TRIVIAL_EDIT` | OpenCode | Codex |
| Trial 2 | `SECURITY_BOUNDARY` | Codex | OpenCode |
| Trial 3 | `FAST_INDEPENDENT_TASKS` | OpenCode | Codex |

This counterbalanced order is frozen. Do not randomize, reorder in response to results, or use an earlier result to alter a later prompt. Each harness in a pair receives identical task wording and starts from its own fresh, disposable copy/worktree of the **same pinned plan-bearing baseline commit**. Every execution is isolated; do not transfer working-tree changes, solutions, results, session state, or other execution artifacts between harnesses or trials. Do not require identical session IDs, scheduler behavior, writer count, concurrency, child order, timing, or speedup.

The frozen baseline is the exact commit containing this accepted plan **after commit/integration**. The pre-plan HEAD recorded under Validation is not the trial baseline. This plan cannot contain its own eventual commit SHA. Before any run, the trial ledger must resolve and pin the plan-bearing commit SHA and verify the fixtures and relevant frozen-source/config identities against it. Do not start a trial until this is done. A separate user-authorized later execution after integration is required; this assignment does not integrate or execute the plan.

### Default and escalation-only workload selection

Default required workloads are only `TRIVIAL_EDIT`, `SECURITY_BOUNDARY`, and `FAST_INDEPENDENT_TASKS`.

`NORMAL_FEATURE` is escalation-only, and may be added only for a concrete unresolved multi-role handoff, result-delivery, completion-barrier, or practical adapter-integration ambiguity that the default set cannot discriminate. Any escalation requires an explicit rationale identifying the observed ambiguity, why this workload distinguishes it, and why it is not answered by existing evidence. Do not add it for symmetry.

`FUNCTIONAL_BUG`, `ARCHITECTURE_HEAVY`, and `HARD_DIAGNOSIS` are removed from the defaults. Their existing policies and tests remain intact. Activate any only when concrete ambiguity in prior matched evidence shows that workload would discriminate a material question; record the ambiguity and explicit rationale. Do not add a workload merely to recreate the former six-item scope.

### Matched workload instructions and acceptance

Use the exact same prompt for both harnesses in each pair. Requirements below are acceptance conditions, not a demand for identical internal topology.

**ROUTING-BLIND PROMPT RULE —** When route/specialist selection is an acceptance property, the matched runnable prompt MUST NOT disclose the expected route or specialist identity; expected routing belongs in acceptance/evaluation metadata, not user task text, to prevent benchmark prompt leakage. Exceptions: an explicit user-selected profile such as FAST; explicit planning/optimization intent when that intent itself is the task; or a role name when role selection is not the property under comparison.

#### `TRIVIAL_EDIT`

**Runnable matched task wording:**

> Change only `tests/phase11-integrated-routing/fixtures/simple/message.txt` from its baseline text `Hello Phase 11 ready` to the single-line text `Hello Phase 12 cross-harness`. Use the smallest sufficient route. Change no other path. Do not add unnecessary research, planning, diagnosis, testing, review, or other specialist work when the result can be validated directly and cheaply. Ensure all required delegated work reaches a terminal result and is consumed before root completion. Report changed paths and acceptance evidence.

**Acceptance:**

- EXPECTED SEMANTIC ROUTE: Kael → Kovan.
- The only authorized changed path is `tests/phase11-integrated-routing/fixtures/simple/message.txt`; its resulting text must be exactly `Hello Phase 12 cross-harness` (one line, with no extra text). No unrelated changes are allowed.
- The required terminal result must actually be delivered and consumed before root completion; gratuitous specialist fan-out is a failure.
- Do not require matching session IDs, timing, or scheduler behavior, or identical topology beyond the semantic invariant where native representation differs non-materially.

#### `SECURITY_BOUNDARY`

**Runnable matched task wording:**

> Using only these supplied facts, diagnose: a `MEMBER` can delete another user's account; the established contract permits account deletion only to `ADMIN`. Classify the issue; identify the violated authorization/trust boundary; provide the minimum safe defensive fix direction; and specify bounded future validation. Do not inspect implementation, source, or runtime; write or implement; attempt exploitation; or broaden into a security audit. Use the smallest sufficient route under current Olympus policy. Report an unknown implementation mechanism as unknown.

**Acceptance:**

- EXPECTED SEMANTIC ROUTE: Kael → Talos.
- NEGATIVE CONTROL: Argus = 0.
- Require actual Kael direct-child Talos invocation and delivery and consumption of Talos's terminal result, not just a proposed or named route.
- Preserve classification of the established authorization violation, do not invent an implementation mechanism, and involve no unrelated specialist without a material reason. Diagnosis-only restrictions remain binding: no implementation/write, source or runtime inspection, exploitation, or security audit; include the minimum safe defensive fix direction and bounded future validation.

#### `FAST_INDEPENDENT_TASKS`

**Runnable matched task wording:**

> In explicit FAST mode, append exactly one new line to each of the four existing files below, preserving all prior contents. The sole new line in `tests/codex/fixtures/parallel/research-a.md` must be `Phase 12 cross-harness marker: A`; in `tests/codex/fixtures/parallel/research-b.md`, `Phase 12 cross-harness marker: B`; in `tests/codex/fixtures/parallel/research-c.md`, `Phase 12 cross-harness marker: C`; and in `tests/codex/fixtures/parallel/research-d.md`, `Phase 12 cross-harness marker: D`. Keep file ownership disjoint: each file must have exactly one authorized writer scope, and writer scopes must not overlap. Use no more than four active children. If a mutation is indeterminate, retain original writer/session ownership and wait for, reconcile, and consume that writer's original native terminal result before inspecting file state or retrying; never inspect-and-write concurrently with a potentially active original writer. If the original execution/result cannot be established, mark `UNCONFIRMED` and do not replace or retry automatically. Only after terminal reconciliation may you inspect actual state to distinguish applied from missing effects; inspection alone does not authorize retry, and any separately authorized continuation covers missing bounded work only. Ensure all required children reach terminal results and those results are delivered and consumed before root completion. Report exact changed paths, acceptance, useful writer count, and any observable concurrency with its measurement basis.

The only authorized changes are the four named files. Each must retain its complete prior contents and gain its exact marker once, as one new final line; no other file may change. The four file operations have disjoint ownership. The active-child ceiling is four, not a target or a concurrency measurement. If multiple writers are used, scopes must be disjoint. For an indeterminate mutation, retain original writer/session ownership and reconcile and consume its original native terminal result before inspecting files or retrying; never inspect-and-write concurrently with a potentially active original writer. If the original execution/result cannot be established, mark `UNCONFIRMED` and do not replace or retry automatically. Only after terminal reconciliation may actual state be inspected to distinguish applied from missing effects. Inspection alone never authorizes retry; any separately authorized continuation is limited to missing bounded work. All required child results must be terminal, delivered, and consumed before root completion. Functional equivalence is the four exact resulting files and correct completion/scope behavior—not matching writer count, concurrency, order, elapsed time, or speedup.

## 3. Fixture and frozen-source evidence

The following identities were checked at the pre-plan HEAD for planning and must be rechecked at the eventual plan-bearing baseline before trial 1. `Git blob` is the committed object identity; `canonical` byte count and SHA-256 describe the committed LF bytes; `observed checkout SHA-256` describes the current raw checkout bytes. These are distinct bases, not interchangeable hashes.

| Path | Git blob SHA-1 | Canonical committed bytes | Canonical committed SHA-256 | Observed checkout SHA-256 |
|---|---|---:|---|---|
| `tests/phase11-integrated-routing/fixtures/simple/message.txt` | `ae77a9e8d168fcc6041b4a0c494ab655c9cc2946` | 21 | `f08468cc319f694692fafcbedfdfb171c9c1d5d59e21c2a2810e7277108f143b` | `a8ce80203278ebe04b2b75779c868dd0f9f236416735d122d8d856c8dab67420` |
| `tests/codex/fixtures/parallel/research-a.md` | `b5af647eccd5eb52f8d20ed0d5e10eef3e1a791c` | 109 | `8bf3b7039d8664e629bbc4190117d24986cdf69c77010c6ba52a88bd6b274922` | `6610f346a6018035007698560b5a0ac3a30825ec3b8be71a5d3c0155aa3f472d` |
| `tests/codex/fixtures/parallel/research-b.md` | `0daa0b2100260ff34371d7dace8fc5964bee8e24` | 123 | `dbeac8dfcba53e4f0acc34f3bd3149045b7682151799a301526ab1f484b8d2ed` | `aa832f76ccc232e7328e769af4b3bac3bcba3f5cc0c7a3d3e89c972e79f0eeb2` |
| `tests/codex/fixtures/parallel/research-c.md` | `36c3f04109032608ea469d5563f4f2b813167828` | 130 | `8d990b498d5fb1ecc89a418fa2eefd6c6353a044ae465e92f1c0c18704efc606` | `85726daa3befa21a03511a4280aab8f4397ebd7e42b25c7ebadbf4082df95556` |
| `tests/codex/fixtures/parallel/research-d.md` | `15ae035e28616e4bf224cf33246671174d1513a6` | 144 | `5dba556e8d70bbcfcb66e21813827dce0f08c0f4fbf633e043e11dbbee793881` | `9c13f4c79b006459f159bc4ddc70eaf2c2ac7d19ef4a25a63b9fae8cd0139332` |

All five current committed blobs end with LF; the observed checkout forms end with CRLF. Exact normalized checkout bytes match their committed blobs. Text/eol attributes are unspecified and the conversion mechanism is not established. Do not compare an LF canonical SHA-256 to a CRLF checkout SHA-256 as if they shared a byte basis. In the ledger, state the identity basis explicitly; compare paired raw checkout identities only on the same basis and stop on an unexplained mismatch. Do not weaken the pinned identity or normalize away an unexplained difference.

Baseline texts (shown with `\n` line separators; each file has a final newline):

| Path | Baseline text |
|---|---|
| `tests/phase11-integrated-routing/fixtures/simple/message.txt` | `Hello Phase 11 ready\n` |
| `tests/codex/fixtures/parallel/research-a.md` | `# Independent research item A\n\nThe \`queue_depth\` metric is sampled once per second. Its unit is queued jobs.\n` |
| `tests/codex/fixtures/parallel/research-b.md` | `# Independent research item B\n\nThe \`retry_count\` metric is sampled at request completion. Its unit is retries per request.\n` |
| `tests/codex/fixtures/parallel/research-c.md` | `# Independent research item C\n\nThe \`worker_age_seconds\` metric is sampled when a worker is selected. Its unit is elapsed seconds.\n` |
| `tests/codex/fixtures/parallel/research-d.md` | `# Independent research item D\n\nThe \`completed_total\` metric increments only after a result is durably acknowledged. Its unit is completed jobs.\n` |

At each eventual execution, verify the fixture paths exist and identify the expected frozen blobs from the pinned baseline. Capture both the committed canonical identity and raw checkout identity, including basis/line endings. At pair level, stop for differing fixture or baseline identity; do not repair, rebase, substitute, or relax the frozen identity inside a trial.

## 4. Capability contract and interpretation

These are declarations from `olympus/harnesses/capabilities.toml`, not matched pass/fail trial results. `GAP` is not `FAIL`. Do not award parity for a `GAP`, `PARTIAL`, or `ADAPTABLE` capability; do not emulate or equalize it. Record capability limits wherever they affect an interpretation, and do not invent observability.

| Capability | OpenCode | Codex |
|---|---|---|
| `ROOT_ORCHESTRATOR` | SUPPORTED | SUPPORTED |
| `CUSTOM_SPECIALISTS` | SUPPORTED | SUPPORTED |
| `PER_ROLE_MODEL` | SUPPORTED | SUPPORTED |
| `PER_ROLE_REASONING` | SUPPORTED | SUPPORTED |
| `MULTI_AGENT` | SUPPORTED | SUPPORTED |
| `BOUNDED_PARALLELISM` | SUPPORTED | SUPPORTED |
| `QUESTION_CENTRALIZATION` | SUPPORTED | PARTIAL |
| `COMPLETION_BARRIER` | SUPPORTED | SUPPORTED |
| `RESULT_DELIVERY` | SUPPORTED | SUPPORTED |
| `RESULT_RECONCILIATION` | SUPPORTED | PARTIAL |
| `ALLOW` | SUPPORTED | SUPPORTED |
| `ASK` | SUPPORTED | ADAPTABLE |
| `DENY` | SUPPORTED | GAP |
| `AEGIS` | SUPPORTED | GAP |
| `ACTIVITY_VISIBILITY` | SUPPORTED | PARTIAL |
| `GLOBAL_RUNTIME_DISCOVERY` | GAP | SUPPORTED |

A capability limitation makes a task inapplicable only when that task's required acceptance depends on it; report that limitation, stop the affected comparison, and do not call it a failure or parity. In particular, do not infer `DENY` or `AEGIS` behavior in Codex, complete question/result observability from a `PARTIAL`, or global discovery in OpenCode from another capability's support.

## 5. Frozen model/config identity and actual runtime

At the current source baseline, `olympus/core/models.toml` maps Sol to OpenCode `openai/gpt-6.1-sol` and Codex `gpt-6.1-sol`; Luna maps to OpenCode `openai/gpt-6-luna` and Codex `gpt-6-luna`. Role mappings are: Sol/high for Kael, Atlas, Argus, Talos, and Helios; Sol/xhigh for Thales; Luna/max for Veyra, Orin, Kovan, Nox, Vera, and Aegis. OpenCode appends effort as `#effort`; Codex stores reasoning effort separately. The Codex renderer excludes Aegis.

The current rendered OpenCode source config (`opencode.jsonc`, rendered from `olympus/harnesses/opencode/config.jsonc`) has `default_agent = kael` and default model `openai/gpt-6.1-sol`; `.opencode/agents/kael.md` identifies Kael as `openai/gpt-6.1-sol#high`. The rendered Codex source config (`.codex/config.toml`, rendered from `olympus/harnesses/codex/config.toml`) has model `gpt-6.1-sol`, reasoning `high`, agents enabled, and `max_concurrent_threads_per_session = 4`.

These are frozen-source/config declarations, not proof of a future process's actual effective settings. In each trial record harness/runtime identity and version, effective model/config identity and observable overrides when available. Unknown runtime version, override, or effective setting is `null`, not inferred from this source snapshot. Do not change these configurations as part of the plan or trial prompts.

## 6. Per-execution evidence ledger

Keep one compact ledger record per execution, linked to its matched pair. Capture actual observations only; use `null` for unavailable values rather than inventing telemetry. At minimum record:

- workload, pair/execution order, harness, exact pinned plan-bearing baseline commit, and isolated copy/worktree identity;
- each relevant fixture path, Git blob identity, canonical committed byte count/SHA-256, observed checkout SHA-256, and explicit hash/line-ending basis;
- harness/runtime version and identity when observable, effective model/config identity from frozen source, and any observed runtime override (otherwise `null`);
- root and direct-child identities/roles where observable, the requested and actual route, each required child's terminal outcome, and observable evidence of result delivery and consumption;
- actual changed paths, workload-specific functional acceptance, scope result, and capability interpretation limits;
- intervention count and reason, plus any retry/replacement behavior and the reason/observed state supporting it;
- for FAST, useful writer count, each writer's disjoint scope, maximum **natively observable** active-child concurrency and its precise measurement basis. If not natively observable, record `null`; do not infer concurrency from a ceiling, launch acknowledgements, or completion order.

Record paired evidence independently; do not transfer a result from one harness to another. Preserve first-attempt evidence and attach later interventions/retries to that original attempt. Trial artifacts are lightweight observations and summaries, not a new large qualifier or a repository-wide log dump.

## 7. Metrics, repetitions, and stop conditions

`PERFORMANCE_WINNER_RANKING` is disabled. Elapsed time is optional only when start/stop definitions and observation are comparable. Tokens/cost are optional only when both harnesses expose comparable measurements; `TOKENS_COST_REQUIRED` is `NO`. Never infer missing values, score a capability gap, claim speedup from incomparable data, or declare a harness/model winner.

Default to one clean isolated run per harness per required workload. Repeat only to investigate material nondeterminism, blocked or ambiguous provenance, or to confirm a concrete discrepancy. Preserve the first attempt; record any intervention and retry against that attempt. A missing result is never an automatic mutation replacement or blind retry. Retain original writer/session ownership and wait for, reconcile, and consume its original native terminal result before inspecting files or retrying; never inspect-and-write concurrently while it may still be active. If the original execution/result cannot be established, mark `UNCONFIRMED` and do not replace or retry automatically. Only after terminal reconciliation may actual state be inspected to distinguish applied from missing effects; inspection alone does not authorize retry, and any separately authorized continuation is limited to missing bounded work.

Stop the affected comparison for a Core routing defect, differing fixture or baseline identity, an unauthorized operation being required, ambiguous provenance, inability to establish required completion, or a capability `GAP` that makes the task inapplicable. Do not silently repair a `BLOCKED` or `UNCONFIRMED` outcome into `VERIFIED`/pass. Preserve evidence and resolve the blocker before any separately authorized continuation.

## 8. Final reporting and Issue #11 alignment

For each workload, report separate OpenCode and Codex statuses: `VERIFIED`, `INCOMPLETE`, `BLOCKED`, or `UNCONFIRMED`. `VERIFIED` requires observable provenance and all applicable functional, routing, scope, required result-delivery/consumption, and completion criteria. `INCOMPLETE` means a known terminal execution did not satisfy one or more applicable criteria; `BLOCKED` records a known blocker or inapplicable task; `UNCONFIRMED` means required execution, provenance, or completion cannot be established. Unknown is not verified.

Report these fields without a winner score: `FUNCTIONAL_PARITY`, `ROUTING_INVARIANT_PARITY`, `COMPLETION_INVARIANT`, `SCOPE_INTEGRITY`, `CAPABILITY_LIMITATIONS`, `OBSERVED_INTERVENTIONS`, and `OPTIONAL_RUNTIME_METRICS`. State only what observations support. Do not claim parity where a capability is `GAP`, `PARTIAL`, or `ADAPTABLE`.

Issue #11 alignment: add no new meta-test framework, large qualifier, or fixtures. Reuse existing deterministic qualification families for policy contracts and reuse the existing fixtures above. Add a regression only if a distinct new defect is found. If a future product defect is found, fix it and independently verify that fix before making further unrelated comparison claims; that does not automatically expand the scope of this plan or authorize implementation under this documentation task.

## 9. Planning-task validation and readiness

Before this document was created, `docs/PHASE12-CROSS-HARNESS-PLAN.md` was absent and the read-only Git check showed a clean working tree on `plan/phase-12-cross-harness-reduced` at pre-plan HEAD `345297901b69b9def30aab271134bf1e23852f99`. That pre-plan commit is provenance for planning only, not the trial baseline. Planning validation is limited to target absence, read-only Git branch/HEAD/status, the five fixture paths/text/identities, the capability source, and `git diff --check` for this document. No runtime trial, Phase 11/Core/render/install/release suite, or other test suite was part of that planning task. At planning-validation time, no runtime trial had started. Integration and the plan-bearing baseline pin were prerequisites; **READY_FOR_PHASE12_TRIAL_1 was NO** until both were complete and a separate user-authorized trial assignment existed.

The no-trial statement and the `PHASE12_PLAN` / readiness values below are a historical planning snapshot, not current status. Phase 12 subsequently closed; the [results ledger](PHASE12-CROSS-HARNESS-RESULTS.md) records its executions and bounded interpretation.

PHASE12_PLAN:
FROZEN_PENDING_EXECUTION

DEFAULT_REQUIRED_RUNTIME_TRIAL_COUNT:
3 matched pairs / 6 executions

DEFAULT_REQUIRED_TRIALS:
TRIVIAL_EDIT
SECURITY_BOUNDARY
FAST_INDEPENDENT_TASKS

ESCALATION_ONLY:
NORMAL_FEATURE

DEFAULT_REMOVED:
FUNCTIONAL_BUG
ARCHITECTURE_HEAVY
HARD_DIAGNOSIS

PERFORMANCE_WINNER_RANKING:
DISABLED

TOKENS_COST_REQUIRED:
NO

ISSUE_11_ALIGNMENT:
PASS
