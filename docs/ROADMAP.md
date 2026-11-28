# Olympus development roadmap

Maintainer-facing, directional, evidence-driven and subject to validation. This is not a release promise, an implementation specification, a commitment to every proposed command, or permission to implement later phases automatically. **SHIPPED** describes delivered capabilities; **IN VALIDATION** identifies work with qualification still in progress; **PLANNED** is future work; **EXPLORATION** is an uncommitted UX idea. Qualification and review precede any promotion of status.

## Support direction — 2026-11-16

- **OpenCode — the only currently supported Olympus runtime.** Prioritize it for every new feature, agent, command, architectural improvement, and runtime capability.
- Do not add Codex support, compatibility fallbacks, or parity gates. Historical Codex components, evaluations, and release claims remain dated evidence only; they do not define current support or compatibility.
- Preserve OpenCode capability limits and evidence dates. Do not generalize a scoped runtime result to untested versions or platforms.
- The current candidate has nine Core roles: Kael and Atlas as separate primaries and seven specialists.
- OpenCode exposes three global task commands: `/olympus.ultra`, `/olympus.performance`, and `/olympus.performance-ultra`. They respect the selected Kael or Atlas primary. There are no bare aliases; empty-argument usage is a prompt-level guard, not deterministic native enforcement.

## Current foundation — SHIPPED

- The current supported adapter is OpenCode. Project-scoped configuration, overrides, apply/recovery, status, and doctor remain separate CLI operations; public install/update/uninstall is global/OpenCode-only.
- Historical project/global dual-harness installation, Codex adapter behavior, and their dated qualifications are not current product routes. The earlier Codex contract is retained only at the [immutable clean-break baseline](https://github.com/Edulynch/OpenCode-OlympusAgents/tree/8534e94337797f0c734d5abcf91b10a13b013c62).
- Completion/reconciliation, external-work ownership, authority, and contextual maintenance through the same Kael workflow remain current Core behavior. OpenCode capability limits and evidence are stated in the [current capability contract](HARNESS-CAPABILITIES.md).
- Upstream OpenCode result-correlation issue #1 remains OPEN; Olympus keeps no-blind-retry/result reconciliation. Historical Aegis and explicit-command qualification records remain historical only and do not define the current product route. Global discovery #7 has a Windows V2.0.26 real-install and Kael-selection acceptance PASS; historical early roster results remain in the issue thread.
- Historical result-handoff issues [#2](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/2) and [#10](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/10) are CLOSED. Those resolutions do not close upstream issue #1 or imply broader runtime support.
- Release history: the v0.4.0 validation tag records the integrated foundation; its release validation failed because documentation still named beta.5 as the active baseline and contradicted the established integration/tag state, and no GitHub Release was created.
- The v0.4.1 validation tag also failed release validation because documentation treated that version as upcoming and advised against publishing it; no GitHub Release was created.
- Both validation tags are immutable historical records.
- The corrective v0.4.2 release established stable release-facing documentation; v0.4.3 subsequently published the public install and uninstall UX.

## Historical foundation and evidence

- The v0.4.0 foundation introduced one canonical Full Agent Display Identity source and derived adapters, plus the then-existing global OpenCode/Codex/All installer foundation, manifests, verification, update, safe uninstall, and non-destructive project→global migration. These are dated release facts, not current routes or migration promises; current public installation is global/OpenCode-only.
- Historical OpenCode V2.0.20 global-runtime runs returned empty rosters; the old diagnostic used the wrong location query and lacked loader-activation confirmation. The original cause remains unknown (Issue #7), so the results are preserved as historical investigation rather than an active unsupported-capability verdict.
- OpenCode V2.0.26 `GLOBAL_RUNTIME_DISCOVERY = SUPPORTED` on isolated Windows with the actual v0.4.6 global installer (15 resources), verified loader, 12/12 agents, 2/2 controls, and configuration-level selection of primary Kael; no LLM prompt. [Acceptance evidence](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/7#issuecomment-6106396436). This is dated, scoped evidence, not a universal runtime guarantee.
- Historical Codex GAP/SUPPORTED labels describe the earlier adapter and evidence only; Codex is not currently supported and those labels are not current capability claims.
- The Phase 12 cross-harness evaluation is a closed historical record: [3 matched pairs and 6/6 verified executions](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/5e9bec1a5eb51d9bfcac93931f0d165a48b4a53c/docs/history/PHASE12-CROSS-HARNESS-RESULTS.md), with PASS for the tested functional, routing, completion, and scope invariants at that time. It does not establish current Codex support, total parity, superiority, or a harness/model winner.

## Scope and backlog reconciliation — Issues #73 and #75

Olympus coordinates technical execution, routes only useful specialists, reconciles
their results, and reports evidence. The runtime remains responsible for tools,
sessions, permissions, and process behavior. Kael reuses the completed Capability
Preflight (#74) and TFR (#34) contracts; neither requires a second capability system
or a blanket test campaign. OpenCode is the only currently supported Olympus
runtime; earlier cross-harness statements below are historical evidence only.
Product requirements,
feature priority, and acceptance decisions remain with each project owner. Flutter on
Android and 2D games with Flame are priorities, not exclusions: web support remains,
and projects need not install every optional device, game, or web tool.

| Disposition | Reconciled scope |
|---|---|
| **KEEP** | Kael's coordination, authority checks, useful specialists, dependency management, result reconciliation, and truthful completion; runtime-owned tools, sessions, and permissions. |
| **REDUCE** | Unnecessary specialist fan-out, mandatory all-role workflows, broad tool-suite installation, and blanket validation. Use only the smallest useful roles and TFR-proportionate checks; preserve applicable project and CI gates. |
| **DEFER** | Product feature implementation and the proposed mobile/game pilot below. The 70–80% useful-work target is an objective to measure, not a demonstrated capability. No product scope or acceptance decision is made here. |
| **REUSE** | Completed #74 Capability Preflight, completed #34 TFR, current Question Barrier, configured concurrency ceiling and completion policies, and the target project's authorized runtime/tooling. Do not create parallel mechanisms. |

Evidence boundary: Preflight, TFR, configured concurrency, native permissions, and session/result handling
are existing contracts with their documented qualification limits. The two Kael
command behaviors are prompt instructions available in the OpenCode adapter; this
change has static contract evidence only, not live command-recognition evidence.
The pilot is proposed, not performed, and no autonomy percentage is claimed.

### Future pilot proposal — not executed in this maintenance

Use a small, project-owner-approved Flutter/Android vertical slice: for example, a
single checklist item's completion toggle in a demo app. The owner must decide the
feature and acceptance criteria before implementation. A future authorized pilot
would use Preflight to establish the permitted project/device route, capture the
focused test plus observable emulator/device evidence required by TFR, and record
accepted outcome, elapsed time, human interventions, avoidable handoffs, and rework
against a simple baseline. Missing device/tool capability is reported honestly; the
whole tool suite is not a prerequisite. This is a proposal only: no app, game, or
pilot was started here.

## Design principles — shipped Phase 3 rules and planned refinements

- **Role purity.** Orchestrators/reasoners own decisions and questions: reason, compare evidence, decide, request focused follow-up, re-consult specialists, synthesize. They do not implement, fix, run tests, or take over another specialist's domain merely to avoid a handoff.
- **Iterative evidence.** Delegation is not one-shot. Re-consult the same specialist for new evidence, clarification, conflict resolution, hypothesis testing, narrower investigation, or validation of a newly discovered fact; prefer focused follow-up to restarting discovery from zero.
- **Orchestrator ownership.** Kael alone routes normal workers. Specialized reasoners own domain questions, hypotheses, and decisions; they request evidence through Kael and do not execute discovery, fixes or tests themselves.
- **Acyclic orchestration.** Specialists are direct children of the current primary: Kael routes execution; Atlas delegates read-only evidence or reasoning to Veyra, Helios, Talos, or Thales. No specialist spawns another agent. A primary may re-consult the original reasoner after collecting new evidence within its own authority.
- **Completion ownership.** An orchestrator that launches child/descendant work owns it until required descendants are terminal, collected, and validated. A progress response or parent/root idle state is not family completion; the root entrypoint retains final user-facing completion authority.
- **No-progress rule.** Another diagnostic round needs materially new evidence, a discriminating experiment, a new viable hypothesis, or meaningful scope narrowing. Repeating reasoning over unchanged evidence is not progress.
- **Containment before heroics.** For third-party, build, deployment, tooling, or test-infrastructure failures, prefer a safe local unblock when appropriate over automatically changing upstream source or spending disproportionate time proving root cause.

## Target conceptual roster

The table describes the current nine-role candidate. Orin and Argus are retired; the phase history below records earlier releases, not current dispatch rules. Native behavior of the new topology requires separate qualification.

| Agent | Target model | Responsibility | Status |
|---|---|---|---|
| `kael` — Kael — The Master | GPT-6.2 Sol High | Execution orchestration and acceptance | Primary |
| `veyra` — Veyra — The Explorer | GPT-6 Luna Max | Research/discovery | SHIPPED; evolving |
| `atlas` — Atlas — The Planner | GPT-6.2 Sol High | Read-only architecture, functional analysis, and planning handoff | Primary |
| `kovan` — Kovan — The Coder | GPT-6 Luna Max | Implementation | SHIPPED; evolving |
| `nox` — Nox — The Tester | GPT-6 Luna Max | Testing/runtime evidence | SHIPPED; evolving |
| `vera` — Vera — The Judge | GPT-6 Luna Max | Independent review | SHIPPED; evolving |
| `talos` — Talos — The Sentinel | GPT-6.2 Sol High | Security defect and trust-boundary reasoning | Required for established or strongly evidenced material security-boundary defects under diagnosis |
| `thales` — Thales — The Sage | GPT-6.2 Sol XHigh | High-uncertainty diagnostic escalation | Exceptional |
| `helios` — Helios — The Optimizer | GPT-6.2 Sol High | Explicit-only optimization feasibility and evidence-bounded proposal | Specialist |

## Defect routing and diagnostic budget

- **FUNCTIONAL_BUG:** use supplied Atlas analysis when cause or fix direction is materially uncertain; Kael does not delegate to Atlas. A deterministic defect takes the smallest normal implementation and validation path. **SECURITY_BUG → Talos required** when diagnosing or classifying an established or strongly evidenced material security/trust/authorization boundary defect; no additional unanswered security-specific question is required. A generic security mention or suspicion without evidence does not automatically route Talos. **OPERATIONAL_ISSUE** (build/deploy/tooling/test infrastructure) → low-cost unblock/containment by default. A **GAP / FEATURE / OPTIMIZATION** is not a bug.
- Thales is **not** a bug category: escalate to this specialist when ordinary diagnosis reaches high uncertainty or stops making useful progress.
- Use Thales only under the current primary's exceptional diagnostic gate, never as automatic follow-up. Stop on no progress.
- Third-party resolution ladder: correct usage/configuration → available fixed version → upgrade/downgrade/pin → adapter/wrapper → fallback/feature flag → local reversible workaround → patch/vendor/fork **only with explicit approval**. Give workarounds a removal condition when practical.

## Helios — SHIPPED, explicit-only

Explicit user optimization intent may engage Helios; a performance fact alone never does. Cheap feasibility triage precedes bounded Nox measurements or Veyra source evidence. Helios proposes a small, evidence-backed benefit/effort/risk envelope or **DO_NOT_OPTIMIZE**; two automatic consultations normally suffice, third automatic denied. **STOP for user approval** of the concrete proposal before any implementation; Kael alone coordinates approved work, and success requires measured **BEFORE / AFTER / DELTA / TARGET / CORRECTNESS**. Static, synthetic, fresh-install, managed-upgrade and full non-live regression qualification passed. User-executed live evidence passed: Case A (Kael `ses_f1d00092cffei3vpkwwod5V6Gw`) used one Sol High Helios (`ses_f1cffb27fffeQK1m5hcXSf3t3u`) for two consultations in the same session, with bounded Kael-owned Veyra evidence (`ses_f1cff4df4ffeTmrPSOqZia0GBp`), a conservative proposal and an explicit approval stop; Case B (Kael `ses_f1cd99003ffeq9C1V0uMOt5G5L`) was observation-only, with zero Helios children. Case A's generic observer flagged `complete=False`, but native reconciliation confirmed the succeeded root, both terminal children consumed, empty inbox and no remaining required work. Neither live case was rerun during release review.

## Command UX — namespaced OpenCode commands

The earlier Phase 10 decision dropped unnamespaced `/power`, `/plan`,
`/performance`, and `/fast` shortcuts. The three global native commands are
`/olympus.ultra <prompt>`, `/olympus.performance <prompt>`, and
`/olympus.performance-ultra <prompt>`. Ultra minimizes time to acceptance,
not child count; Performance uses the Helios gate and preserves approval of
the concrete direction before implementation. Performance-Ultra applies both.
Kael may execute authorized work; Atlas stops at analysis and a scoped handoff.
The commands preserve ownership and completion gates and have no bare aliases.
Empty-argument usage is guarded in the prompt
because native command metadata has no required-arguments field. `/goal` remains
opt-in and user-selected where the native surface provides it; Kael does not
trigger it invisibly or assume it delegates.

- `/power` and `/plan` — **DROP as Olympus commands**. Select Atlas for read-only planning; the runtime's built-in `/plan` is not an Olympus role invocation.
- Bare `/performance` and `/fast` — **DROP**. Use the explicit namespaced commands above; FAST remains only a maintainer qualification profile, and the trivial fast path remains a policy optimization for routing.

## Phase order

| Phase | Status | Target / qualification focus |
|---|---|---|
| 0 — Foundation | **SHIPPED** | OpenCode V2 runtime, preflight/discovery, completion and external-work gates, HUD, trusted-project execution, contextual maintenance, adaptive concurrency within the configured ceiling. |
| 1 — Adaptive Concurrency finalization | **DEFERRED** | The earlier two-profile concurrency proposal remains unimplemented. Default routing is useful and adaptive; `/olympus.ultra` asks for maximum useful safe concurrency up to the configured 1–8 prompt ceiling without changing the native scheduler or gates. |
| 2 — Current Sorin baseline qualification | **SUPERSEDED** | The Sorin-specific qualification plan was superseded by shipped Phase 4 Thales evolution; no Sorin agent or session is to be resurrected. Evidence: the Thales evolution entry in `CHANGELOG.md` and the Phase 4 migration qualification in `tests/thales/`. |
| 3 — Role Purity + Iterative Evidence | **SHIPPED** | Kael-mediated Role Purity, same-session Sorin evidence follow-up, no-progress stop, completion ownership, and Issue #1 reconciliation. Historical evidence is preserved; current routing has no separate maintenance handoff. |
| 4 — Thales evolution | **SHIPPED** | Sorin visible identity → Thales The Sage; Sol XHigh deep-escalation role, user-executed live routing and deterministic negative control passed. |
| 5 — Atlas The Planner | **SHIPPED** | Sol High, smallest sufficient execution plan; no implementation/discovery ownership; gated use. User-executed live planning and negative control passed. |
| 6 — Argus The Bug Hunter | **SHIPPED** | Optional functional diagnosis; static/synthetic, installer, regression and user-executed live qualification passed. No implementation or direct discovery. |
| 7 — Talos The Sentinel | **SHIPPED** | Bounded security defect and trust-boundary diagnosis; static/synthetic, installer, regression and user-executed live qualification passed. |
| 8 — Helios The Optimizer | **SHIPPED** | Explicit-only feasibility/proposal, mandatory user approval, before/after validation; user-executed live cases A and B passed. |
| 9 — Contextual maintenance (Issue #28) | **IN VALIDATION** | One Kael handles OlympusAgents and external-project work using the normal specialists and gates; former separate maintenance role/command are removed. Historical Codex capability labels are not current support claims. |
| 10 — Command UX | **SUPERSEDED** | Earlier bare shortcuts remain dropped. The current three namespaced commands are listed above. |
| 11 — Integrated Routing Qualification | **SHIPPED** | [Closure evidence](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/8534e94337797f0c734d5abcf91b10a13b013c62/tests/phase11-integrated-routing/baseline.md): qualification is complete with no pending native cases. Case I remains guided PARTIAL; Argus/Thales same-session follow-up runtime coverage was NOT_EXERCISED. These are non-blocking limits, not evidence that every runtime path was exercised. |
| 12 — Cross-harness evaluation | **CLOSED — HISTORICAL** | [Results](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/5e9bec1a5eb51d9bfcac93931f0d165a48b4a53c/docs/history/PHASE12-CROSS-HARNESS-RESULTS.md): 3 matched pairs / 6 verified executions at that time; PASS for tested invariants only. This does not establish current Codex support, total parity, superiority, or a harness/model winner. |

### Phase 3 topology and live qualification — SHIPPED

**KAEL_MEDIATED** passed offline topology certification and the user-executed Phase 3 live qualification: specialized reasoners request bounded evidence through Kael; Kael owns worker sessions, routes focused follow-up to direct children, and re-consults the **same** reasoner with collected evidence. Case A (`ses_f21e09d97ffeiyjqAvmZuDRxa9`) confirmed one bounded Veyra evidence round, two consultations in one Sorin session, Role Purity and complete family reconciliation (unresolved/unknown = 0). Case B (`ses_f21dad776ffevU6A5qKcenexjh`) confirmed the deterministic negative control with Sorin sessions/consultations = 0 and complete family reconciliation. The captured session/message review satisfied the manual structural-review gate. Evidence class: **USER_EXECUTED_LIVE_EVIDENCE**, not task-executed live evidence. No case was rerun during integration. Reasoners remain diagnostic rather than implementing; workers stay direct children of Kael. This respects native subagent depth, simplifies cycle prevention, keeps Completion Gates root-owned, and needs no custom scheduler/runtime.

**DIRECT_NESTED** is **RUNTIME-INCOMPATIBLE** with current OpenCode native subagent depth (`Subagent depth limit reached (1)`), not a prompt failure. No bypass or custom runtime is recommended.

Historical model references in the Phase 4–7 session records below are retained verbatim as evidence of those sessions, not as current configuration. Current model families and reasoning efforts are listed in the roster above.

### Phase 4 Thales The Sage — SHIPPED

Offline/static, fresh-install, v0.2.0-to-candidate upgrade and full non-live regression passed. User-executed live Case A (Kael `ses_f217c2a55ffeXgwTNO96v5Ybzr`, Thales `ses_f217bf452ffe50smZ2Ad30z8z3`, Veyra `ses_f217b9d60ffeOvaDBJN71MxUCc`) verified runtime agent ID `thales` at `openai/gpt-6-sol#xhigh`, one Thales session, two consultations in that same session (EVIDENCE_REQUEST then calibrated ADVICE), direct Kael-owned worker evidence and no Sorin sessions. User-executed live Case B (Kael `ses_f216b02a1ffe0N79YjA86GUgL6`, Veyra `ses_f216ae227ffewhO6EdE35g0cLr`) verified a bounded `REDA` → `READY` deterministic correction recommendation with Thales, Sorin and Maintenance counts all zero. Both families completed with pending and unknown counts zero. Evidence class: **USER_EXECUTED_LIVE_EVIDENCE**, not task-executed live evidence. Neither case was rerun for integration; no third automatic consultation is authorized.

### Phase 5 Atlas The Planner — SHIPPED

Optional Atlas plans the execution of an already-scoped and already-architected change, using the smallest sufficient sequence; Kael applies the Planning Gate and retains evidence routing and completion ownership. Atlas neither discovers, redesigns architecture, diagnoses root cause, implements, tests nor reviews. Offline/static, synthetic, fresh-install, managed-upgrade and non-live regression qualification passed.

User-executed live Case A (Kael `ses_f1e1eef3cffeV8KbtBWzwZbDVm`, Atlas `ses_f1e1ebd96ffeBiApFHkJ4paS6p`, Veyra `ses_f1e1e6759ffevt47wXhKeJsAH2`) verified runtime ID `atlas` at `openai/gpt-6-sol#high`: one Atlas session, two consultations, bounded `contracts/compatibility.txt` evidence from a direct Kael-owned Veyra, `EVIDENCE_REQUEST` followed by `PLAN` in the same Atlas session, and a useful smallest-sufficient compatibility rollout and rollback plan. No direct Atlas discovery, implementation or third consultation occurred. Case B (Kael `ses_f1e1af036ffecnp6pzOjibKQT5`, Kovan `ses_f1e1ac7c6ffePDii4zHwm7fI9e`) changed `READY` to `READY!` with Atlas count and consultation count zero. Both families completed with pending and unknown counts zero. Evidence class: **USER_EXECUTED_LIVE_EVIDENCE**, not task-executed live evidence; neither case was rerun during integration. The disposable fixture manifest retained an older source commit, but SHA-256 comparisons matched the final candidate's runtime assets; an initial empty `opencode debug agents` response resolved on subsequent invocation in the intact fixture. Neither observation required fixture recreation.

### Phase 6 Argus The Bug Hunter — SHIPPED

Argus is one optional `argus` subagent at `openai/gpt-6-sol#high`, with no direct repository discovery, edits or tests. Veyra/Nox collect bounded evidence as direct Kael children; Argus compares hypotheses and returns a calibrated diagnosis or bounded request in the same session. Normal limit two consultations; a third needs a second discriminating evidence round; no automatic fourth. Security, operational failures, unpromised features, optimization and trivial deterministic bugs bypass Argus. Static/synthetic, fresh-install, managed-upgrade and all 16 applicable post-merge non-live suites passed.

**USER_EXECUTED_LIVE_EVIDENCE**: Case A (Kael `ses_f1daec63fffe9KIz6iwZVDMlwd`, Argus `ses_f1dae9029ffe99un2V7aOy5kRZ`, Veyra `ses_f1dae4cd7ffemKeV6WP0EGVCTW`) verified runtime Argus ID and Sol High model, one Argus session with two consultations, EVIDENCE_REQUEST followed by an evidence-backed BUG_DIAGNOSIS in that **same** session after bounded `bug/shipping-rule.txt` evidence from direct Kael-owned Veyra. Diagnosis identified strict `>` excluding threshold 50 against the established `>= 50` contract, suggested inclusive threshold semantics, and bounded validation to 49/50/51. No third consultation, Argus direct discovery, implementation, Atlas, Thales or Maintenance; family complete with pending/unknown zero. Case B (Kael `ses_f1da3bab2ffefQIzpvzR03Awsq`, Kovan `ses_f1da36c9dffefQSzUcybi9eg74`) corrected `REEDY` to `READY` with **Argus count zero**; family complete with pending/unknown zero. Neither valid case was rerun for integration. Earlier attempted Case A (`ses_f1dc6f099ffep6VsmAj6yz4vG7`) was **INFRA_OR_TEST_INSTRUCTION_BLOCKED**, not an Argus failure: root assistant was `build` rather than Kael, with zero Argus/Veyra executions. The [historical `tests/argus/RUNME.md`](https://github.com/Edulynch/OpenCode-OlympusAgents/blob/5e9bec1a5eb51d9bfcac93931f0d165a48b4a53c/tests/argus/RUNME.md) required a fresh explicit Kael root, native agent verification and stop on wrong-agent roots without blind retry. Disposable live fixtures remain retained.

### Phase 7 Talos The Sentinel — SHIPPED

**Historical criterion note:** The Phase 7 wording and traces below are preserved as originally recorded. Phase 11 later replaced the earlier “only when materially security-specific reasoning remains” activation criterion: Talos is required for an established or strongly evidenced material security/trust/authorization boundary defect being diagnosed/classified, without requiring another unanswered security question.

Talos is an optional pure security-defect reasoner, not an auditor, implementer or orchestrator. Kael applies the Security Routing Gate only when an evidenced security boundary violation still needs specialist classification, trust-boundary, exploitability, cause, impact or bounded fix-direction reasoning. Functional-only bugs remain Argus territory; operational tooling failures, unpromised security features and optimization do not automatically route Talos. Talos receives Kael-supplied evidence, requests one bounded fact from Veyra or Nox through Kael when needed, and continues in the same session; two consultations normally suffice, three require a second discriminating round and a fourth automatic consultation is denied. No whole-repository audit or exploit execution is required. Vera still independently reviews a change, Thales remains a separate high-uncertainty gate, Atlas plans when needed, Kovan implements, and Kael owns completion. All 17 applicable post-merge non-live suites passed.

**USER_EXECUTED_LIVE_EVIDENCE** (not task-executed): Case A (Kael `ses_f1d56d318ffed1ifg2je4sHOQf`, Talos `ses_f1d569e61ffeKTNR7mL4nZ0SGg`, Veyra `ses_f1d5650eaffee7Cn4Rql085IKm`) verified runtime ID `talos` at `openai/gpt-6-sol#high`, one Talos session with two consultations: EVIDENCE_REQUEST followed by an evidence-backed SECURITY_DIAGNOSIS in that **same** session after bounded `security/access-rule.txt` evidence from a direct Kael-owned Veyra. The diagnosis compared the ADMIN-only DELETE_ACCOUNT boundary against MEMBER accepted, identified a likely guard accepting all non-GUEST roles while preserving runtime-link uncertainty, and bounded impact to the demonstrated non-admin crossing of an admin-only authorization boundary. Fix direction requires ADMIN; validate GUEST denied, MEMBER denied, ADMIN allowed. No direct Talos discovery, implementation, exploit execution, broad audit, third consultation, Argus, Atlas, Thales or Maintenance. Case B (Kael `ses_f1d4251e0ffeXugAHMOPRQpCDw`, Kovan `ses_f1d422305ffey61RnQAE3q38xi`) corrected `REEDY` to `READY` with **Talos count zero** and no other security/diagnostic specialists. Both families completed with pending and unknown zero. The generic Phase-3 observer's default case-A policy label on Case B was not a Talos failure; native child inspection established the zero count. Both cases were user-executed and were not rerun for integration; their disposable fixtures remain retained.

## Premortem guardrails

| Risk | Mitigation direction |
|---|---|
| Orchestration bureaucracy, role overlap, redundant discovery | Smallest sufficient handoff; explicit ownership; re-use focused evidence. |
| Runaway diagnostic loops, Thales overuse/underuse | Evidence budgets, no-progress stop, uncertainty gate and negative controls. |
| Atlas overplanning; Argus gap-vs-bug confusion; Talos security overclassification | Gate planning by complexity; classify against evidence before specialist routing. |
| Helios analysis costs more than benefit; third-party fork/patch debt | Baseline and expected-value stop; reversible containment first, explicit approval for patch/fork. |
| Command ambiguity or sprawl, including confusion between Ultra, Performance, maintainer FAST qualification and the trivial fast path | Keep command names exact; preserve dependency, writer, validation, approval and completion gates. |
| False completion | Join, collect, validate and report all required work, including descendants and external jobs. |
