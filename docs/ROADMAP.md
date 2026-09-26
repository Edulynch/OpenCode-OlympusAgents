# Olympus development roadmap

Maintainer-facing, directional, evidence-driven and subject to validation. This is not a release promise, an implementation specification, a commitment to every proposed command, or permission to implement later phases automatically. **SHIPPED** describes the current `master` foundation; **IN VALIDATION** identifies an unmerged candidate; **PLANNED** is future work; **EXPLORATION** is an uncommitted UX idea. Qualification and review precede any promotion of status.

## Current foundation — SHIPPED on master

- OpenCode V2 supplies the runtime; Olympus is a thin orchestration/decision layer.
- Capability Preflight and Task-Scoped / Progressive Discovery bound early investigation.
- Reliable Completion Gates and Strict External Work Ownership require collecting and validating required work before declaring completion.
- The passive Activity HUD reports active child work; trusted-project Kovan implementation and Nox validation have shell access with distinct edit boundaries.
- The explicit `/maintain` Maintenance Plane stays outside normal Kael routing.
- Adaptive concurrency uses NORMAL (default, useful parallelism) and explicit FAST (latency priority); **both currently cap Kael-launched children at four on `master`**. The NORMAL 4 / FAST 6 split exists on an unmerged candidate branch and is **IN VALIDATION**, not shipped.

## Design principles — PLANNED refinements

- **Role purity.** Orchestrators/reasoners own decisions and questions: reason, compare evidence, decide, request focused follow-up, re-consult specialists, synthesize. They do not implement, fix, run tests, or take over another specialist's domain merely to avoid a handoff.
- **Iterative evidence.** Delegation is not one-shot. Re-consult the same specialist for new evidence, clarification, conflict resolution, hypothesis testing, narrower investigation, or validation of a newly discovered fact; prefer focused follow-up to restarting discovery from zero.
- **Orchestrator ownership.** Kael alone routes normal workers. Specialized reasoners own domain questions, hypotheses, and decisions; they request evidence through Kael and do not execute discovery, fixes or tests themselves.
- **Acyclic orchestration.** All workers/reasoners are direct children of Kael; no worker or reasoner spawns another agent. The same reasoner session can be re-consulted after Kael collects new evidence; no reasoner-to-Kael child call or reasoner nesting.
- **Completion ownership.** An orchestrator that launches child/descendant work owns it until required descendants are terminal, collected, and validated. A progress response or parent/root idle state is not family completion; the root entrypoint retains final user-facing completion authority.
- **No-progress rule.** Another diagnostic round needs materially new evidence, a discriminating experiment, a new viable hypothesis, or meaningful scope narrowing. Repeating reasoning over unchanged evidence is not progress.
- **Containment before heroics.** For third-party, build, deployment, tooling, or test-infrastructure failures, prefer a safe local unblock when appropriate over automatically changing upstream source or spending disproportionate time proving root cause.

## Target conceptual roster

The table distinguishes existing roles from proposed identities. Model entries are targets for the future roster, **not claims about installed model configuration**. This roadmap does not create or rename agents.

| Agent | Target model | Responsibility | Status |
|---|---|---|---|
| 👑 Kael The Master | GPT-6 Sol High | Master orchestration | SHIPPED; evolving |
| 🔭 Veyra The Explorer | GPT-6 Luna Max | Research/discovery | SHIPPED; evolving |
| 📐 Orin The Architect | GPT-6 Luna Max | Architecture/boundaries | SHIPPED; evolving |
| 🗺️ Atlas The Planner | GPT-6 Sol High | Execution planning | PLANNED; proposed |
| 🔨 Kovan The Coder | GPT-6 Luna Max | Implementation | SHIPPED; evolving |
| 🐞 Argus The Bug Hunter | GPT-6 Sol High | Functional defect reasoning | PLANNED; proposed |
| 👁️ Nox The Tester | GPT-6 Luna Max | Testing/runtime evidence | SHIPPED; evolving |
| ⚖️ Vera The Judge | GPT-6 Luna Max | Independent review | SHIPPED; evolving |
| 🛡️ Talos The Sentinel | GPT-6 Sol High | Security defect/exploitability reasoning | PLANNED; proposed |
| 🧠 Thales The Sage | GPT-6 Sol XHigh | High-uncertainty diagnostic escalation | PLANNED evolution/rename of current Sorin |
| ☀️ Helios The Optimizer | GPT-6 Sol High | Explicit optimization analysis/orchestration | PLANNED; proposed |
| 🛡️ Aegis The Keeper | GPT-6 Luna Max target | Explicit Maintenance/admin execution | PLANNED visible identity/model adjustment of current Maintenance |

## Defect routing and diagnostic budget — PLANNED

- **FUNCTIONAL_BUG → Argus**; **SECURITY_BUG → Talos**; **OPERATIONAL_ISSUE** (build/deploy/tooling/test infrastructure) → low-cost unblock/containment by default. A **GAP / FEATURE / OPTIMIZATION** is not a bug.
- Thales is **not** a bug category: escalate to this specialist when ordinary diagnosis reaches high uncertainty or stops making useful progress.
- Bound Argus evidence rounds; reserve rarer Thales escalation rounds. Stop on no progress; go deeper only when expected value warrants it, or when the user explicitly requests deeper investigation. These are directions, not fixed implementation constants.
- Third-party resolution ladder: correct usage/configuration → available fixed version → upgrade/downgrade/pin → adapter/wrapper → fallback/feature flag → local reversible workaround → patch/vendor/fork **only with explicit approval**. Give workarounds a removal condition when practical.

## Helios — PLANNED, explicit-only

An optimization request may explicitly engage Helios; ordinary Kael work does not route there automatically. Target flow: analyze → establish baseline → estimate optimization envelope → propose expected benefit / effort / risk → **STOP for user approval** → delegate implementation only after approval → measure **BEFORE vs AFTER**. Helios may conclude **DO NOT OPTIMIZE** when likely improvement does not justify the work.

## Command UX — EXPLORATION

Existing `/maintain` enters the explicit Maintenance plane. Candidate concepts below are not implemented commitments; exact names and behavior require validation:

- `/power`: use all useful specialists and safe available parallelism aggressively, without bypassing role purity, dependencies, completion, writer ownership, or diagnostic gates.
- `/plan`: explicit planning workflow.
- `/fast`: candidate name for a direct/minimal path for obviously simple implementation work, **not** a skip-validation mode; may be confused with the existing FAST concurrency request profile. Decide the command repertoire in Phase 10.
- `/performance` or `/helios`: explicit Helios optimization workflow.

## Phase order

| Phase | Status | Target / qualification focus |
|---|---|---|
| 0 — Foundation | **SHIPPED** | OpenCode V2 runtime, preflight/discovery, completion and external-work gates, HUD, trusted-project execution, Maintenance Plane, NORMAL/FAST up to four. |
| 1 — Adaptive Concurrency finalization | **IN VALIDATION** | NORMAL 4 / FAST 6 candidate; qualify and review before merging. Not on `master`. |
| 2 — Current Sorin baseline qualification | **PLANNED** | Explicit invocation, automatic Diagnostic Gate, and negative control where Sorin must **not** activate. |
| 3 — Role Purity + Iterative Evidence | **IN VALIDATION** (final candidate branch only) | Kael-mediated policy on current master, same-session Sorin follow-up, no-progress stop, Issue #1/#2 reconciliation, static/synthetic qualification; manual live validation still required before promotion. A second evidence round cannot produce a third automatic Sorin consultation under the conservative budget. |
| 4 — Thales evolution | **PLANNED** | Sorin visible identity → Thales The Sage; preserve XHigh deep-escalation role; qualify routing. |
| 5 — Atlas The Planner | **PLANNED** | Sol High, smallest sufficient execution plan; no implementation/discovery ownership; gated use. |
| 6 — Argus The Bug Hunter | **PLANNED** | Functional bugs only, evidence-driven diagnosis, budget, third-party containment policy. |
| 7 — Talos The Sentinel | **PLANNED** | Security defects, exploitability/blast-radius reasoning; not general functional debugging. |
| 8 — Helios The Optimizer | **PLANNED** | Explicit-only analyze/propose/approval/delegate/measure flow. |
| 9 — Aegis evolution | **PLANNED** | Maintenance visible identity, Luna Max target; executor, not strategist. |
| 10 — Command UX | **EXPLORATION** | Validate a small useful repertoire: candidate `/power`, `/plan`, `/fast`, `/performance`; avoid command sprawl. |
| 11 — Integrated Routing Qualification | **PLANNED** | Fixtures: simple edit, complex feature, functional bug, security bug, operational/build issue, difficult/flaky diagnosis, third-party bug, optimization request, explicit planning, power mode, maintenance boundary. |
| 12 — Release | **PLANNED** | Only after integrated qualification. |

### Phase 3A topology qualification — selected; Phase 3 candidate not shipped

**KAEL_MEDIATED** passed offline certification of a completed live run: specialized reasoners request bounded evidence through Kael; Kael owns worker sessions, routes focused follow-up to Veyra/Nox, and re-consults the **same** reasoner with collected evidence. Reasoners remain diagnostic rather than implementing; workers stay direct children of Kael. This respects native subagent depth, simplifies cycle prevention, keeps Completion Gates root-owned, and needs no custom scheduler/runtime. Production routing remains unchanged; Phase 3 policy exists only on the unmerged feature candidate pending live validation.

**DIRECT_NESTED** is **RUNTIME-INCOMPATIBLE** with current OpenCode native subagent depth (`Subagent depth limit reached (1)`), not a prompt failure. No bypass or custom runtime is recommended.

## Premortem guardrails

| Risk | Mitigation direction |
|---|---|
| Orchestration bureaucracy, role overlap, redundant discovery | Smallest sufficient handoff; explicit ownership; re-use focused evidence. |
| Runaway diagnostic loops, Thales overuse/underuse | Evidence budgets, no-progress stop, uncertainty gate and negative controls. |
| Atlas overplanning; Argus gap-vs-bug confusion; Talos security overclassification | Gate planning by complexity; classify against evidence before specialist routing. |
| Helios analysis costs more than benefit; third-party fork/patch debt | Baseline and expected-value stop; reversible containment first, explicit approval for patch/fork. |
| `/power` overfanout; `/fast` skipping validation; command sprawl | Enforce dependencies, writer/completion gates and checks; keep the repertoire small. |
| False completion | Join, collect, validate and report all required work, including descendants and external jobs. |
