<!--
Temporary amendment-review scratch: remove after review.
Constitution Sync Impact Report
Version change: unversioned, unratified generic scaffold -> 1.0.0, first ratified adoption
Modified principles: none; the scaffold had no ratified principles
Added principles: I. Olympus Core Is Canonical; II. Authority Follows the Runtime;
  III. Prefer Simple Changes Backed by Evidence; IV. Validate Proportionally to Risk;
  V. Preserve Compatibility and Installation Integrity;
  VI. Keep Specification, Design, Implementation, and Verification Distinct;
  VII. Respect Scope and Use Spec Kit Proportionally
Added sections: Compatibility and Installation Integrity; Proportional Spec-Driven Development
Removed principles: none
Template sync: project overrides added for specification, planning, and tasks
Follow-up: none
-->

# OpenCode-OlympusAgents Constitution

## Core Principles

### I. Olympus Core Is Canonical

Olympus Core defines the canonical roles, identities, models, policies, and capabilities. OpenCode and Codex are adapters to that shared core; their features, controls, and supported workflows may differ. Preserve the twelve-role roster and each role's ownership as defined by Core. Do not infer adapter parity from shared names or prompts. See [Olympus Core](../../olympus/README.md), [roles](../../olympus/roles/), [identities](../../olympus/core/identities.toml), [models](../../olympus/core/models.toml), and [capabilities](../../olympus/harnesses/capabilities.toml).

### II. Authority Follows the Runtime

Kael owns task routing, scope reconciliation, and final completion, including consumption of required child results. Aegis requires explicit invocation through the supported OpenCode `/maintain` path. Kael and child agents must not invoke, activate, or escalate to Aegis automatically; Aegis remains within its defined authority. ALLOW permits only the exact authorized operation within the task and writable scope. ASK means a native approval may be available for an eligible operation; approval does not expand authority. DENY cannot be elevated by an ordinary approval, grant, or prompt. These labels define policy authority; runtime enforcement is a separate claim and requires runtime evidence. Report missing controls as gaps and preserve the policy. Codex's documented Aegis and DENY capability gaps remain limitations; prompt text does not close them. Follow [routing](../../olympus/policies/routing.md), [authority](../../olympus/policies/authority.md), [maintenance](../../olympus/policies/maintenance-plane.md), [result lifecycle](../../olympus/policies/result-lifecycle.md), and [Codex compatibility notes](../../docs/CODEX-COMPATIBILITY.md).

### III. Prefer Simple Changes Backed by Evidence

Choose the simplest maintainable design that satisfies the authorized need. Add an abstraction, service, dependency, agent, or layer only when a concrete requirement and evidence justify its cost. Keep claims traceable to repository or runtime evidence, distinguish known behavior from assumptions, and leave unknowns explicit.

### IV. Validate Proportionally to Risk

Apply the project's TFR approach: after capability preflight and bounded discovery, select the smallest checks sufficient for the observable behavior, its boundaries, and its risks. Preserve applicable user, project, CI, release, and migration gates; do not add duplicate harnesses or gates. Identify checks as deterministic, simulated, or real-runtime and report PASS, FAIL, NOT RUN, BLOCKED, or unknown accurately. A static fixture does not prove native runtime behavior. See [harness guidance](../../docs/HARNESSES.md), [development guidance](../../docs/DEVELOPMENT.md), and the [Codex compatibility notes](../../docs/CODEX-COMPATIBILITY.md).

### V. Preserve Compatibility and Installation Integrity

Changes must respect the v0.4.9 architecture, centralized model management, role ownership, manifests, installer and uninstaller behavior, user configuration, drift protection, and installation integrity. Treat generated or Olympus Core-owned files as protected sources; update their canonical source through the supported maintenance plane. Check compatibility against the documented [release baseline](../../docs/RELEASE-v0.4.9.md) and [contribution guidance](../../CONTRIBUTING.md). Do not restructure the framework to fit a documentation workflow.

### VI. Keep Specification, Design, Implementation, and Verification Distinct

Specifications state scope and observable behavior; plans record design and dependencies; tasks order authorized work; verification records evidence. Retrospective specifications describe the implementation actually evidenced and do not invent requirements. New or changed behavior states its authorized scope, acceptance criteria, relevant dependencies and risks, and focused verification. A gap found during documentation remains an observation until separately authorized.

### VII. Respect Scope and Use Spec Kit Proportionally

Honor explicit user constraints and the authorized change boundary. Do not infer implementation authorization or scope expansion from a specification; execution requires the applicable user authorization. Use only the Spec Kit artifacts needed for the task; a trivial or documentation-only change does not require a full feature workflow. The templates guide documentation and do not create approval, commit, deployment, or release authority.

## Compatibility and Installation Integrity

Project-specific architecture, role definitions, model sources, security and governance rules, adapter capabilities, installation behavior, and release procedures remain documented in their canonical sources linked above. This constitution states governing principles and does not duplicate those manuals. Where an adapter lacks a documented capability or technical control, record that limitation and preserve the applicable policy.

## Proportional Spec-Driven Development

Use existing behavior as the baseline for retrospective documentation. For new or changed behavior, document only the user-authorized delta. Keep expected checks in the plan distinct from checks actually run, and preserve any material uncertainty or runtime limitation. The active templates in `../templates/overrides/` adapt Spec Kit artifacts to these principles; they do not change the behavior of workflow scripts or integrations.

## Governance

This constitution governs Spec Kit documentation and project decisions within the user's authorized scope. It does not override user constraints, grant protected-file authority, or supersede Olympus Core policy and runtime controls. Amendments follow the existing project review process and record their impact; this adds no approval gate. Use semantic versions: MAJOR for redefining or removing a principle, MINOR for adding a principle or normative obligation, and PATCH for clarification that does not change normative meaning. Keep an amendment history below; this is the first ratified adoption, so no earlier constitutional history is implied.

**Version**: 1.0.0 | **Ratified**: 2026-10-14 | **Last Amended**: 2026-10-14

### Amendment History

- **1.0.0 (2026-10-14)**: First ratified OlympusAgents constitution, aligned to the v0.4.9 functional baseline.
