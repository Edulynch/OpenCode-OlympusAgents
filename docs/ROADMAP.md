# Olympus development roadmap

Maintainer-facing, directional, evidence-driven and subject to validation. This is not a release promise, an implementation specification, a commitment to every proposed command, or permission to implement later phases automatically. **SHIPPED** describes the current `master` foundation; **IN VALIDATION** identifies an unmerged candidate; **PLANNED** is future work; **EXPLORATION** is an uncommitted UX idea. Qualification and review precede any promotion of status.

## Current foundation — SHIPPED on master

- OpenCode V2 supplies the runtime; Olympus is a thin orchestration/decision layer.
- Capability Preflight and Task-Scoped / Progressive Discovery bound early investigation.
- Reliable Completion Gates and Strict External Work Ownership require collecting and validating required work before declaring completion.
- The passive Activity HUD reports active child work; trusted-project Kovan implementation and Nox validation have shell access with distinct edit boundaries.
- The explicit `/maintain` Maintenance Plane stays outside normal Kael routing.
- Adaptive concurrency uses NORMAL (default, useful parallelism) and explicit FAST (latency priority); **both currently cap Kael-launched children at four on `master`**. The NORMAL 4 / FAST 6 split exists on an unmerged candidate branch and is **IN VALIDATION**, not shipped.

## Design principles — shipped Phase 3 rules and planned refinements

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
| 🗺️ Atlas The Planner | GPT-6 Sol High | Execution planning | SHIPPED; optional, Planning Gate only |
| 🔨 Kovan The Coder | GPT-6 Luna Max | Implementation | SHIPPED; evolving |
| 🐞 Argus The Bug Hunter | GPT-6 Sol High | Functional defect reasoning | SHIPPED; optional, Functional Bug Routing Gate only |
| 👁️ Nox The Tester | GPT-6 Luna Max | Testing/runtime evidence | SHIPPED; evolving |
| ⚖️ Vera The Judge | GPT-6 Luna Max | Independent review | SHIPPED; evolving |
| 🛡️ Talos The Sentinel | GPT-6 Sol High | Security defect/exploitability reasoning | PLANNED; proposed |
| 🧠 Thales The Sage | GPT-6 Sol XHigh | High-uncertainty diagnostic escalation | SHIPPED: native evolution of Sorin; live routing qualified |
| ☀️ Helios The Optimizer | GPT-6 Sol High | Explicit optimization analysis/orchestration | PLANNED; proposed |
| 🛡️ Aegis The Keeper | GPT-6 Luna Max target | Explicit Maintenance/admin execution | PLANNED visible identity/model adjustment of current Maintenance |

## Defect routing and diagnostic budget — Phase 6 shipped

- **FUNCTIONAL_BUG → optional Argus** only if cause/fix direction is not obvious; deterministic trivial bugs bypass him. **SECURITY_BUG** is excluded (Talos remains planned); **OPERATIONAL_ISSUE** (build/deploy/tooling/test infrastructure) → low-cost unblock/containment by default. A **GAP / FEATURE / OPTIMIZATION** is not a bug.
- Thales is **not** a bug category: escalate to this specialist when ordinary diagnosis reaches high uncertainty or stops making useful progress.
- Argus normally uses up to two consultations, with a third only after a second materially discriminating evidence round; a fourth automatic call is denied. Kael alone considers Thales under the independent Diagnostic Gate if diagnosis stays unresolved. Stop on no progress.
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
| 3 — Role Purity + Iterative Evidence | **SHIPPED** | Kael-mediated Role Purity, same-session Sorin evidence follow-up, no-progress stop, completion ownership, Issue #1 reconciliation and Issue #2 Maintenance safety. Static/synthetic/full regression passed; user-executed live Cases A and B passed. No third automatic Sorin consultation. |
| 4 — Thales evolution | **SHIPPED** | Sorin visible identity → Thales The Sage; Sol XHigh deep-escalation role, user-executed live routing and deterministic negative control passed. |
| 5 — Atlas The Planner | **SHIPPED** | Sol High, smallest sufficient execution plan; no implementation/discovery ownership; gated use. User-executed live planning and negative control passed. |
| 6 — Argus The Bug Hunter | **SHIPPED** | Optional functional diagnosis; static/synthetic, installer, regression and user-executed live qualification passed. No implementation or direct discovery. |
| 7 — Talos The Sentinel | **PLANNED** | Security defects, exploitability/blast-radius reasoning; not general functional debugging. |
| 8 — Helios The Optimizer | **PLANNED** | Explicit-only analyze/propose/approval/delegate/measure flow. |
| 9 — Aegis evolution | **PLANNED** | Maintenance visible identity, Luna Max target; executor, not strategist. |
| 10 — Command UX | **EXPLORATION** | Validate a small useful repertoire: candidate `/power`, `/plan`, `/fast`, `/performance`; avoid command sprawl. |
| 11 — Integrated Routing Qualification | **PLANNED** | Fixtures: simple edit, complex feature, functional bug, security bug, operational/build issue, difficult/flaky diagnosis, third-party bug, optimization request, explicit planning, power mode, maintenance boundary. |
| 12 — Release | **PLANNED** | Only after integrated qualification. |

### Phase 3 topology and live qualification — SHIPPED

**KAEL_MEDIATED** passed offline topology certification and the user-executed Phase 3 live qualification: specialized reasoners request bounded evidence through Kael; Kael owns worker sessions, routes focused follow-up to direct children, and re-consults the **same** reasoner with collected evidence. Case A (`ses_f21e09d97ffeiyjqAvmZuDRxa9`) confirmed one bounded Veyra evidence round, two consultations in one Sorin session, Role Purity and complete family reconciliation (unresolved/unknown = 0). Case B (`ses_f21dad776ffevU6A5qKcenexjh`) confirmed the deterministic negative control with Sorin sessions/consultations = 0 and complete family reconciliation. The captured session/message review satisfied the manual structural-review gate. Evidence class: **USER_EXECUTED_LIVE_EVIDENCE**, not task-executed live evidence. No case was rerun during integration. Reasoners remain diagnostic rather than implementing; workers stay direct children of Kael. This respects native subagent depth, simplifies cycle prevention, keeps Completion Gates root-owned, and needs no custom scheduler/runtime.

**DIRECT_NESTED** is **RUNTIME-INCOMPATIBLE** with current OpenCode native subagent depth (`Subagent depth limit reached (1)`), not a prompt failure. No bypass or custom runtime is recommended.

### Phase 4 Thales The Sage — SHIPPED

Offline/static, fresh-install, v0.2.0-to-candidate upgrade and full non-live regression passed. User-executed live Case A (Kael `ses_f217c2a55ffeXgwTNO96v5Ybzr`, Thales `ses_f217bf452ffe50smZ2Ad30z8z3`, Veyra `ses_f217b9d60ffeOvaDBJN71MxUCc`) verified runtime agent ID `thales` at `openai/gpt-6-sol#xhigh`, one Thales session, two consultations in that same session (EVIDENCE_REQUEST then calibrated ADVICE), direct Kael-owned worker evidence and no Sorin sessions. User-executed live Case B (Kael `ses_f216b02a1ffe0N79YjA86GUgL6`, Veyra `ses_f216ae227ffewhO6EdE35g0cLr`) verified a bounded `REDA` → `READY` deterministic correction recommendation with Thales, Sorin and Maintenance counts all zero. Both families completed with pending and unknown counts zero. Evidence class: **USER_EXECUTED_LIVE_EVIDENCE**, not task-executed live evidence. Neither case was rerun for integration; no third automatic consultation is authorized.

### Phase 5 Atlas The Planner — SHIPPED

Optional Atlas plans the execution of an already-scoped and already-architected change, using the smallest sufficient sequence; Kael applies the Planning Gate and retains evidence routing and completion ownership. Atlas neither discovers, redesigns architecture, diagnoses root cause, implements, tests nor reviews. Offline/static, synthetic, fresh-install, managed-upgrade and non-live regression qualification passed.

User-executed live Case A (Kael `ses_f1e1eef3cffeV8KbtBWzwZbDVm`, Atlas `ses_f1e1ebd96ffeBiApFHkJ4paS6p`, Veyra `ses_f1e1e6759ffevt47wXhKeJsAH2`) verified runtime ID `atlas` at `openai/gpt-6-sol#high`: one Atlas session, two consultations, bounded `contracts/compatibility.txt` evidence from a direct Kael-owned Veyra, `EVIDENCE_REQUEST` followed by `PLAN` in the same Atlas session, and a useful smallest-sufficient compatibility rollout and rollback plan. No direct Atlas discovery, implementation or third consultation occurred. Case B (Kael `ses_f1e1af036ffecnp6pzOjibKQT5`, Kovan `ses_f1e1ac7c6ffePDii4zHwm7fI9e`) changed `READY` to `READY!` with Atlas count and consultation count zero. Both families completed with pending and unknown counts zero. Evidence class: **USER_EXECUTED_LIVE_EVIDENCE**, not task-executed live evidence; neither case was rerun during integration. The disposable fixture manifest retained an older source commit, but SHA-256 comparisons matched the final candidate's runtime assets; an initial empty `opencode debug agents` response resolved on subsequent invocation in the intact fixture. Neither observation required fixture recreation.

### Phase 6 Argus The Bug Hunter — SHIPPED

Argus is one optional `argus` subagent at `openai/gpt-6-sol#high`, with no direct repository discovery, edits or tests. Veyra/Nox collect bounded evidence as direct Kael children; Argus compares hypotheses and returns a calibrated diagnosis or bounded request in the same session. Normal limit two consultations; a third needs a second discriminating evidence round; no automatic fourth. Security, operational failures, unpromised features, optimization and trivial deterministic bugs bypass Argus. Static/synthetic, fresh-install, managed-upgrade and all 16 applicable post-merge non-live suites passed.

**USER_EXECUTED_LIVE_EVIDENCE**: Case A (Kael `ses_f1daec63fffe9KIz6iwZVDMlwd`, Argus `ses_f1dae9029ffe99un2V7aOy5kRZ`, Veyra `ses_f1dae4cd7ffemKeV6WP0EGVCTW`) verified runtime Argus ID and Sol High model, one Argus session with two consultations, EVIDENCE_REQUEST followed by an evidence-backed BUG_DIAGNOSIS in that **same** session after bounded `bug/shipping-rule.txt` evidence from direct Kael-owned Veyra. Diagnosis identified strict `>` excluding threshold 50 against the established `>= 50` contract, suggested inclusive threshold semantics, and bounded validation to 49/50/51. No third consultation, Argus direct discovery, implementation, Atlas, Thales or Maintenance; family complete with pending/unknown zero. Case B (Kael `ses_f1da3bab2ffefQIzpvzR03Awsq`, Kovan `ses_f1da36c9dffefQSzUcybi9eg74`) corrected `REEDY` to `READY` with **Argus count zero**; family complete with pending/unknown zero. Neither valid case was rerun for integration. Earlier attempted Case A (`ses_f1dc6f099ffep6VsmAj6yz4vG7`) was **INFRA_OR_TEST_INSTRUCTION_BLOCKED**, not an Argus failure: root assistant was `build` rather than Kael, with zero Argus/Veyra executions. `tests/argus/RUNME.md` now requires a fresh explicit Kael root, native agent verification and stop on wrong-agent roots without blind retry. Disposable live fixtures remain retained.

## Premortem guardrails

| Risk | Mitigation direction |
|---|---|
| Orchestration bureaucracy, role overlap, redundant discovery | Smallest sufficient handoff; explicit ownership; re-use focused evidence. |
| Runaway diagnostic loops, Thales overuse/underuse | Evidence budgets, no-progress stop, uncertainty gate and negative controls. |
| Atlas overplanning; Argus gap-vs-bug confusion; Talos security overclassification | Gate planning by complexity; classify against evidence before specialist routing. |
| Helios analysis costs more than benefit; third-party fork/patch debt | Baseline and expected-value stop; reversible containment first, explicit approval for patch/fork. |
| `/power` overfanout; `/fast` skipping validation; command sprawl | Enforce dependencies, writer/completion gates and checks; keep the repertoire small. |
| False completion | Join, collect, validate and report all required work, including descendants and external jobs. |
