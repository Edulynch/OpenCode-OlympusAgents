# Contextual Olympus maintenance

Kael is the only root orchestrator for both ordinary project work and OlympusAgents development. There is no separate maintenance role, command, privileged plane, or Olympus-side authorization flow.

Treat the requested result as one goal-first mission: Kael owns diagnosis, scoped implementation, proportionate validation, correction, and delivery under the normal role and completion rules. A native `/goal` surface remains opt-in and user-selected; do not require it, invoke it invisibly, or assume it delegates work. When unavailable, use the current user prompt and ordinary Kael workflow.

## Identify the target repository

Before routing or writing, identify the active Git worktree root and the repository the requested change targets. Treat it as the OlympusAgents source repository only when the root contains the canonical Olympus Core files (`olympus/core/models.toml`, `olympus/core/identities.toml`, and `olympus/policies/routing.md`) and independent project-identity evidence identifies OlympusAgents, such as the root project README/metadata or its Git remote. A directory name, a request mentioning Olympus, or an isolated matching file is not sufficient evidence; if identity evidence conflicts, stop and ask only for the missing task detail. If identity or target is unclear, do not perform dependent writes.

When the target is this OlympusAgents repository, handle its source, adapter, renderer, tests, and documentation through Kael's normal routing and authority rules. Kael may make a small direct change when its effective tools and scope allow; Kovan may implement larger or otherwise useful scoped changes. Repository identity classifies the target, it does not authorize unrelated paths, destructive effects, Git mutations, publication, global installation changes, credentials, or excluded work.

## Preserve the external-project boundary

For a different user project, work only on that project's requested scope. Do not reach into a separate OlympusAgents checkout or alter Olympus-managed runtime resources installed in that project, including generated `.opencode`/`.codex` outputs and manifest-owned files. Explain the ownership/target boundary and stop; do not silently broaden the task or suggest an automatic route to a privileged executor.

This rule does not block an explicitly requested task whose identified target is the OlympusAgents source repository. It does not change native OpenCode permissions, role boundaries, the task-scoped authority contract, or the normal requirements for user authorization of high-impact actions.
