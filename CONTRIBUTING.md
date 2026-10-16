# Contributing to OlympusAgents

Thanks for helping keep the framework reliable and approachable. Small, focused pull requests are preferred over new infrastructure.

## Runtime support policy (2026-10-16)

- **OpenCode V2 — ACTIVE DEVELOPMENT.** Prioritize it for new features, agents, commands, architecture, and runtime capabilities. New OpenCode-only capabilities do not require Codex equivalents.
- **Codex — FROZEN COMPATIBILITY.** Preserve existing Codex components, installers, manifests, and uninstall protections. Do not add integrations or pursue parity-only gap closure. Only evidenced critical Codex fixes or regressions introduced by shared-code changes are in scope.
- Keep existing shared-integrity and compatibility tests; do not create Codex gates for OpenCode-only work. Codex gaps in authority, Aegis, hard `DENY`, and observability remain frozen. Do not claim newer Codex versions verified without evidence.

## Before you start

- Use Windows, Git, PowerShell 7 and Python 3.11+ for the supported offline contributor qualifications.
- Start from current `master`; work on a topic branch. Do not commit directly to release tags.
- For bugs, explain **expected versus observed** behavior, affected harness/version, a minimal reproduction, and what is still unknown.
- For security issues, use [SECURITY.md](SECURITY.md) instead of sharing private details in public discussions.

## Make a focused change

- Keep each PR to one concern. Do not change models, permissions, routing, installer ownership or runtime contracts to resolve an unrelated test failure.
- Prefer updating existing deterministic checks rather than creating a test suite for every change.
- When editing canonical Olympus Core or adapter definitions, regenerate the relevant managed output using the existing renderer; **do not hand-edit generated `.opencode/` or `.codex/` files alone**.
- Explain compatibility or capability limits; do not report static qualifications as live runtime evidence. Do not treat Codex parity as an acceptance criterion for new OpenCode capabilities.
- Git hooks and model-backed agents are **not required** to contribute.

## Run proportionate checks

| Change | Minimum useful validation |
| --- | --- |
| Documentation, badges, images | Review rendered content, links, `git diff --check`, and the relevant existing documentation qualifier when commands/contracts change |
| Localized defect | A focused regression in its existing suite |
| Shared Olympus contract or policy | Focused checks plus `FAST` |
| Significant installer/release/compatibility work | Relevant installer fixtures and `FULL` before integration |
| Runtime behavior | Prioritize focused OpenCode V2 evidence; Codex runtime evidence only for an in-scope critical fix or materially relevant shared-code regression |

Run FAST from the repository root:

```powershell
pwsh -NoProfile -File ./scripts/qualify.ps1 -Profile FAST
```

GitHub Actions also runs FAST for pull requests targeting `master`. FULL and RUNTIME are deliberately separate and are not CI defaults. See [the testing guidance](docs/DEVELOPMENT.md#choosing-qualification-by-change-risk).

## Pull request checklist

- Summarize what changed and why.
- Link the issue when there is one.
- List the actual commands run and their results, including any **NOT RUN** gates.
- Keep the diff reviewable, avoid unrelated formatting, and do not rewrite historical release evidence.
- Allow a maintainer to review before merge; never rewrite an already published release tag.
