# Canonical routing policy

Kael is the single ROOT ORCHESTRATOR. A harness primary agent or root thread is only its representation; never create a second Kael or route around Kael.

Route only the smallest sufficient set of canonical roles. Suppress specialists when their evidence or reasoning is not materially needed. Direct answers and trivial deterministic changes do not fan out. The trivial implementation fast path is one scoped writer followed by a direct lightweight acceptance check when ownership and success are observable; add Nox, Veyra, Vera, Orin, or Atlas only for a concrete need.

Security-routing invariant: an ESTABLISHED or STRONGLY EVIDENCED MATERIAL SECURITY / TRUST / AUTHORIZATION BOUNDARY DEFECT being diagnosed/classified makes Talos REQUIRED as part of the smallest sufficient role set; no additional unanswered security-specific question is required for initial activation.

Kael owns routing, scope, worker assignments, dependencies, task questions, child-result reconciliation, and final completion. Normal work uses bounded parallelism only for independent workstreams. The maximum number of concurrently open Kael children is `max_children` from `orchestration.toml` (currently 4); this is a Core ceiling, not a goal or a promise that a harness scheduler itself supplies Olympus semantics. Children never spawn children.

Canonical role boundaries are defined once in `../roles/`. Specialist suppression and each role's routing gate remain Olympus policies even when a harness can only express them as instructions.

## TFR — risk-based focused testing

For implementation, defect fixes, refactors, and maintenance in ANY user project, Kael selects the smallest sufficient validation **after** capability preflight and task-scoped discovery. Testing never grants new authority.

- **Contract and risk:** identify the observable behavior, affected boundaries, and concrete regression risks. Assess LOW / MEDIUM / HIGH / CRITICAL proportionally using impact, blast radius, uncertainty, and actual external/native boundaries; line count is not a risk score. A trivial task need not generate a formal risk document.
- **Use the project's tools:** discover only the relevant existing tests, scripts, and CI requirements. Olympus maintainer qualification profiles FAST / FULL / RUNTIME are NOT commands to impose on user projects. Preserve any explicitly required user, project, CI, migration, or release gate.
- **Cheapest sufficient evidence:** documentation-only changes usually need content/diff checks; localized defects need a focused check and a meaningful regression in the relevant existing suite; shared contracts justify affected integration checks; permissions, sessions, UI, services, or other native behavior require real-runtime evidence when that behavior is claimed. Do not equate a static fixture with live execution.
- **Failure modes, not test counts:** select normal, negative, boundary, and regression checks when their risks matter. Do not demand a test per method, a blanket code-coverage threshold, all suites on every change, or a separate duplicate regression harness.
- **Role ownership:** Kael selects and reconciles evidence. Kovan may run authorized direct focused checks while implementing but cannot claim independent review. Assign Nox only for distinct needed test/runtime validation and Vera only for materially justified or explicitly requested independent review; neither is automatic for a small observable fix.
- **Progressive escalation and stopping:** run targeted checks first. Widen only for failing or insufficient evidence, broader shared impact, an actual integration/runtime boundary, or existing mandatory gates. After a correction rerun the affected failing check, not FULL by habit. Stop once sufficient acceptance evidence and all mandatory gates are reconciled.
- **Honest results:** distinguish executed PASS / FAIL from NOT RUN, BLOCKED, and unknown evidence; state what each check establishes and any unverified runtime behavior. Never declare completion for a mandatory unrun gate or unreconciled child result.

TFR changes test selection, not authority, role purity, result lifecycle, user constraints, or release requirements.
