# Olympus development roadmap

Maintainer-facing, directional, evidence-driven and subject to validation. This is not a release promise, an implementation specification, a commitment to every proposed command, or permission to implement later phases automatically. **SHIPPED** describes delivered capabilities; **IN VALIDATION** identifies work with qualification still in progress; **PLANNED** is future work; **EXPLORATION** is an uncommitted UX idea. Qualification and review precede any promotion of status.

## Current foundation — SHIPPED

- Harness Core, OpenCode adapter, and experimental Codex adapter are present; their declared capability differences remain explicit.
- The dual-harness project-local installer is published. `-Scope project` remains the default; Codex/OpenCode/All selection is supported.
- Completion/reconciliation, external-work ownership, authority, and the explicit `/maintain` → Aegis maintenance entry are part of Core. OpenCode has Aegis, hard DENY, native ASK, and the passive Activity HUD. Codex DENY/Aegis remain gaps and activity visibility is basic/partial.
- Upstream OpenCode result-correlation issue #1 remains OPEN; Olympus keeps no-blind-retry/result reconciliation. Issues #2–#6, #8, and #9 are CLOSED. Issue #8's final same-child runtime resume PASS is recorded in [Issue #8 runtime evidence](ISSUE-8-CHECKPOINT-RESUME.md). Global discovery #7 remains OPEN; OpenCode global runtime discovery is a known GAP. Issue #10 remains OPEN: child-to-parent summaries may omit exact structured fields.
- Release history: the v0.4.0 validation tag records the integrated foundation; its release validation failed because documentation still named beta.5 as the active baseline and contradicted the established integration/tag state, and no GitHub Release was created.
- The v0.4.1 validation tag also failed release validation because documentation treated that version as upcoming and advised against publishing it; no GitHub Release was created.
- Both validation tags are immutable historical records.
- The corrective v0.4 line continues with v0.4.2.

## IN PROGRESS / NEXT

- The v0.4.0 foundation introduced one canonical Full Agent Display Identity source and derived adapters, plus the global OpenCode/Codex/All installer foundation, manifests, verification, update, safe uninstall, and non-destructive project→global migration. The corrective release line preserves these capabilities and project scope as the default; project-local behavior remains backwards-compatible.
- Global OpenCode runtime discovery is **GAP** after corrected path isolation: run `4b1610d3387a4afcaa8fe24336ef0362` resolved home/config/data/cache/state/tmp/log inside the same fresh A/B HOME/XDG/TEMP roots with zero real-profile paths. Both global installs and read-only VerifyOnly passed. Each owned server returned HTTP 200 for the exact clean-fixture location; the first roster response was empty and one explicit lazy-load query returned only seven OpenCode built-ins. The expected Olympus roster and both temporary loader markers were absent in A (custom config layer) and B (true XDG global config), while generated resources and the hidden Aegis hash verified. Issue #7 remains OPEN with a reproducible OpenCode 2.0.20 global-agent discovery gap. Evidence: `C:\Users\Public\opencode-olympus-qualification\olympus-global-runtime-4b1610d3387a4afcaa8fe24336ef0362`.
- Codex global runtime discovery remains **SUPPORTED** based on the user's provided PASS evidence; it was accepted as supplied and not re-run. Issue #7 remains OPEN because OpenCode omitted the installed global Olympus agents after isolation was demonstrated.
- Codex DENY and Codex Aegis remain explicit GAPs. Research found no demonstrated hard-deny equivalent or safely enforced privileged maintenance entry; do not use prompt-only theater or weaken Core.
- Real-project OpenCode-vs-Codex comparison remains NEXT. Existing Codex fixture measurements do not establish a winner or comparative quality/cost/speed.

## Design principles — shipped Phase 3 rules and planned refinements

- **Role purity.** Orchestrators/reasoners own decisions and questions: reason, compare evidence, decide, request focused follow-up, re-consult specialists, synthesize. They do not implement, fix, run tests, or take over another specialist's domain merely to avoid a handoff.
- **Iterative evidence.** Delegation is not one-shot. Re-consult the same specialist for new evidence, clarification, conflict resolution, hypothesis testing, narrower investigation, or validation of a newly discovered fact; prefer focused follow-up to restarting discovery from zero.
- **Orchestrator ownership.** Kael alone routes normal workers. Specialized reasoners own domain questions, hypotheses, and decisions; they request evidence through Kael and do not execute discovery, fixes or tests themselves.
- **Acyclic orchestration.** All workers/reasoners are direct children of Kael; no worker or reasoner spawns another agent. The same reasoner session can be re-consulted after Kael collects new evidence; no reasoner-to-Kael child call or reasoner nesting.
- **Completion ownership.** An orchestrator that launches child/descendant work owns it until required descendants are terminal, collected, and validated. A progress response or parent/root idle state is not family completion; the root entrypoint retains final user-facing completion authority.
- **No-progress rule.** Another diagnostic round needs materially new evidence, a discriminating experiment, a new viable hypothesis, or meaningful scope narrowing. Repeating reasoning over unchanged evidence is not progress.
- **Containment before heroics.** For third-party, build, deployment, tooling, or test-infrastructure failures, prefer a safe local unblock when appropriate over automatically changing upstream source or spending disproportionate time proving root cause.

## Target conceptual roster

The table captures shipped roles and current in-validation identities. Model entries describe the corresponding target/current candidate configuration, not an authorization to change other roles. Future role or command changes still require separate validation.

| Agent | Target model | Responsibility | Status |
|---|---|---|---|
| `kael` — Kael — The Master | GPT-6 Sol High | Master orchestration | SHIPPED; evolving |
| `veyra` — Veyra — The Explorer | GPT-6 Luna Max | Research/discovery | SHIPPED; evolving |
| `orin` — Orin — The Architect | GPT-6 Luna Max | Architecture/boundaries | SHIPPED; evolving |
| `atlas` — Atlas — The Planner | GPT-6 Sol High | Execution planning | SHIPPED; optional, Planning Gate only |
| `kovan` — Kovan — The Coder | GPT-6 Luna Max | Implementation | SHIPPED; evolving |
| `argus` — Argus — The Bug Hunter | GPT-6 Sol High | Functional defect reasoning | SHIPPED; optional, Functional Bug Routing Gate only |
| `nox` — Nox — The Tester | GPT-6 Luna Max | Testing/runtime evidence | SHIPPED; evolving |
| `vera` — Vera — The Judge | GPT-6 Luna Max | Independent review | SHIPPED; evolving |
| `talos` — Talos — The Sentinel | GPT-6 Sol High | Security defect and trust-boundary reasoning | SHIPPED; optional, Security Routing Gate only |
| `thales` — Thales — The Sage | GPT-6 Sol XHigh | High-uncertainty diagnostic escalation | SHIPPED: native evolution of Sorin; live routing qualified |
| `helios` — Helios — The Optimizer | GPT-6 Sol High | Explicit-only optimization feasibility and evidence-bounded proposal | SHIPPED; user-executed live qualification passed |
| `aegis` — Aegis — The Keeper | GPT-6 Luna Max | Hidden privileged task executor through explicit `/maintain`; never a Kael child or ownership gate | SHIPPED on OpenCode; `CODEX_AEGIS = GAP` |

## Defect routing and diagnostic budget — Phase 6 shipped

- **FUNCTIONAL_BUG → optional Argus** only if cause/fix direction is not obvious; deterministic trivial bugs bypass him. **SECURITY_BUG → optional Talos** only when materially security-specific reasoning remains; Phase 7 qualification passed. **OPERATIONAL_ISSUE** (build/deploy/tooling/test infrastructure) → low-cost unblock/containment by default. A **GAP / FEATURE / OPTIMIZATION** is not a bug.
- Thales is **not** a bug category: escalate to this specialist when ordinary diagnosis reaches high uncertainty or stops making useful progress.
- Argus normally uses up to two consultations, with a third only after a second materially discriminating evidence round; a fourth automatic call is denied. Kael alone considers Thales under the independent Diagnostic Gate if diagnosis stays unresolved. Stop on no progress.
- Third-party resolution ladder: correct usage/configuration → available fixed version → upgrade/downgrade/pin → adapter/wrapper → fallback/feature flag → local reversible workaround → patch/vendor/fork **only with explicit approval**. Give workarounds a removal condition when practical.

## Helios — SHIPPED, explicit-only

Explicit user optimization intent may engage Helios; a performance fact alone never does. Cheap feasibility triage precedes bounded Nox measurements or Veyra source evidence. Helios proposes a small, evidence-backed benefit/effort/risk envelope or **DO_NOT_OPTIMIZE**; two automatic consultations normally suffice, third automatic denied. **STOP for user approval** of the concrete proposal before any implementation; Kael alone coordinates approved work, and success requires measured **BEFORE / AFTER / DELTA / TARGET / CORRECTNESS**. Static, synthetic, fresh-install, managed-upgrade and full non-live regression qualification passed. User-executed live evidence passed: Case A (Kael `ses_f1d00092cffei3vpkwwod5V6Gw`) used one Sol High Helios (`ses_f1cffb27fffeQK1m5hcXSf3t3u`) for two consultations in the same session, with bounded Kael-owned Veyra evidence (`ses_f1cff4df4ffeTmrPSOqZia0GBp`), a conservative proposal and an explicit approval stop; Case B (Kael `ses_f1cd99003ffeq9C1V0uMOt5G5L`) was observation-only, with zero Helios children. Case A's generic observer flagged `complete=False`, but native reconciliation confirmed the succeeded root, both terminal children consumed, empty inbox and no remaining required work. Neither live case was rerun during release review.

## Command UX — EXPLORATION

Existing `/maintain` explicitly enters the hidden Aegis executor for its delivered task; it is never an automatic authority route. Normal user-project workflow remains Kael's recommended route. Candidate concepts below are not implemented commitments; exact names and behavior require validation:

- `/power`: use all useful specialists and safe available parallelism aggressively, without bypassing role purity, dependencies, completion, writer ownership, or diagnostic gates.
- `/plan`: explicit planning workflow.
- `/fast`: candidate name for a direct/minimal path for obviously simple implementation work, **not** a skip-validation mode; may be confused with the existing FAST concurrency request profile. Decide the command repertoire in Phase 10.
- `/performance` or `/helios`: explicit Helios optimization workflow.

## Phase order

| Phase | Status | Target / qualification focus |
|---|---|---|
| 0 — Foundation | **SHIPPED** | OpenCode V2 runtime, preflight/discovery, completion and external-work gates, HUD, trusted-project execution, Maintenance Plane, NORMAL/FAST up to four. |
| 1 — Adaptive Concurrency finalization | **IN VALIDATION** | NORMAL 4 / FAST 6 candidate; qualify and review before merging. Not on `master`. |
| 2 — Current Sorin baseline qualification | **SUPERSEDED** | The Sorin-specific qualification plan was superseded by shipped Phase 4 Thales evolution; no Sorin agent or session is to be resurrected. Evidence: the Thales evolution entry in `CHANGELOG.md` and the Phase 4 migration qualification in `tests/thales/`. |
| 3 — Role Purity + Iterative Evidence | **SHIPPED** | Kael-mediated Role Purity, same-session Sorin evidence follow-up, no-progress stop, completion ownership, Issue #1 reconciliation and Issue #2 Maintenance safety. Static/synthetic/full regression passed; user-executed live Cases A and B passed. No third automatic Sorin consultation. |
| 4 — Thales evolution | **SHIPPED** | Sorin visible identity → Thales The Sage; Sol XHigh deep-escalation role, user-executed live routing and deterministic negative control passed. |
| 5 — Atlas The Planner | **SHIPPED** | Sol High, smallest sufficient execution plan; no implementation/discovery ownership; gated use. User-executed live planning and negative control passed. |
| 6 — Argus The Bug Hunter | **SHIPPED** | Optional functional diagnosis; static/synthetic, installer, regression and user-executed live qualification passed. No implementation or direct discovery. |
| 7 — Talos The Sentinel | **SHIPPED** | Bounded security defect and trust-boundary diagnosis; static/synthetic, installer, regression and user-executed live qualification passed. |
| 8 — Helios The Optimizer | **SHIPPED** | Explicit-only feasibility/proposal, mandatory user approval, before/after validation; user-executed live cases A and B passed. |
| 9 — Aegis evolution | **SHIPPED on OpenCode; Codex GAP** | Hidden Aegis on Luna Max accepts the explicit `/maintain` command's task declaration immediately, without repository ownership/provenance admission; preserves Kael/child denials, task scope, and result reconciliation. |
| 10 — Command UX | **EXPLORATION** | Validate a small useful repertoire: candidate `/power`, `/plan`, `/fast`, `/performance`; avoid command sprawl. |
| 11 — Integrated Routing Qualification | **IN VALIDATION / PARTIAL** | Deterministic A–L matrix, semantic validator and mutation negatives are in progress. Fresh-root native evidence remains pending; this phase is not SHIPPED. |
| 12 — Cross-harness evaluation | **PLANNED** | Controlled real-project comparison; report only evidence-backed capability, quality, cost, or speed findings. |

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

### Phase 7 Talos The Sentinel — SHIPPED

Talos is an optional pure security-defect reasoner, not an auditor, implementer or orchestrator. Kael applies the Security Routing Gate only when an evidenced security boundary violation still needs specialist classification, trust-boundary, exploitability, cause, impact or bounded fix-direction reasoning. Functional-only bugs remain Argus territory; operational tooling failures, unpromised security features and optimization do not automatically route Talos. Talos receives Kael-supplied evidence, requests one bounded fact from Veyra or Nox through Kael when needed, and continues in the same session; two consultations normally suffice, three require a second discriminating round and a fourth automatic consultation is denied. No whole-repository audit or exploit execution is required. Vera still independently reviews a change, Thales remains a separate high-uncertainty gate, Atlas plans when needed, Kovan implements, and Kael owns completion. All 17 applicable post-merge non-live suites passed.

**USER_EXECUTED_LIVE_EVIDENCE** (not task-executed): Case A (Kael `ses_f1d56d318ffed1ifg2je4sHOQf`, Talos `ses_f1d569e61ffeKTNR7mL4nZ0SGg`, Veyra `ses_f1d5650eaffee7Cn4Rql085IKm`) verified runtime ID `talos` at `openai/gpt-6-sol#high`, one Talos session with two consultations: EVIDENCE_REQUEST followed by an evidence-backed SECURITY_DIAGNOSIS in that **same** session after bounded `security/access-rule.txt` evidence from a direct Kael-owned Veyra. The diagnosis compared the ADMIN-only DELETE_ACCOUNT boundary against MEMBER accepted, identified a likely guard accepting all non-GUEST roles while preserving runtime-link uncertainty, and bounded impact to the demonstrated non-admin crossing of an admin-only authorization boundary. Fix direction requires ADMIN; validate GUEST denied, MEMBER denied, ADMIN allowed. No direct Talos discovery, implementation, exploit execution, broad audit, third consultation, Argus, Atlas, Thales or Maintenance. Case B (Kael `ses_f1d4251e0ffeXugAHMOPRQpCDw`, Kovan `ses_f1d422305ffey61RnQAE3q38xi`) corrected `REEDY` to `READY` with **Talos count zero** and no other security/diagnostic specialists. Both families completed with pending and unknown zero. The generic Phase-3 observer's default case-A policy label on Case B was not a Talos failure; native child inspection established the zero count. Both cases were user-executed and were not rerun for integration; their disposable fixtures remain retained.

## Premortem guardrails

| Risk | Mitigation direction |
|---|---|
| Orchestration bureaucracy, role overlap, redundant discovery | Smallest sufficient handoff; explicit ownership; re-use focused evidence. |
| Runaway diagnostic loops, Thales overuse/underuse | Evidence budgets, no-progress stop, uncertainty gate and negative controls. |
| Atlas overplanning; Argus gap-vs-bug confusion; Talos security overclassification | Gate planning by complexity; classify against evidence before specialist routing. |
| Helios analysis costs more than benefit; third-party fork/patch debt | Baseline and expected-value stop; reversible containment first, explicit approval for patch/fork. |
| `/power` overfanout; `/fast` skipping validation; command sprawl | Enforce dependencies, writer/completion gates and checks; keep the repertoire small. |
| False completion | Join, collect, validate and report all required work, including descendants and external jobs. |
