# Contributing to OlympusAgents

Thanks for helping keep the framework reliable and approachable. Small, focused pull requests are preferred over new infrastructure.

## Runtime support policy

- **OpenCode V2 — ACTIVE DEVELOPMENT and the only supported Olympus runtime.** Prioritize it for features, agents, commands, architecture, and runtime capabilities. Do not add Codex support or compatibility fallbacks.
- Keep OpenCode ownership, permission, integrity, installer, and recovery safeguards.

## Before you start

- Use Windows, Git, PowerShell 7 and Python 3.11+ for the supported offline contributor qualifications.
- Start from current `master`; work on a topic branch. Do not commit directly to release tags.
- For bugs, explain **expected versus observed** behavior, affected harness/version, a minimal reproduction, and what is still unknown.
- For security issues, use [SECURITY.md](SECURITY.md) instead of sharing private details in public discussions.

## Make a focused change

- Keep each PR to one concern. Do not change models, permissions, routing, installer ownership or runtime contracts to resolve an unrelated test failure.
- Prefer updating existing deterministic checks rather than creating a test suite for every change.
- When editing canonical Olympus Core or OpenCode adapter definitions, regenerate the relevant managed output using the existing renderer; **do not hand-edit generated `.opencode/` files alone**.
- Explain capability limits; do not report static qualifications as live runtime evidence.
- Git hooks and model-backed agents are **not required** to contribute.

## Run proportionate checks

| Change | Minimum useful validation |
| --- | --- |
| Documentation, badges, images | Review rendered content, `python -B scripts/check_docs.py`, `git diff --check`, and the relevant existing documentation qualifier when commands/contracts change |
| Security-sensitive repository content | Run `python -B -m unittest discover -s tests/security -p 'test_secret_gate.py' -v`, then `python -B scripts/secret_gate.py --base origin/master` (or select another reachable base explicitly) |
| Localized defect | A focused regression in its existing suite |
| Shared Olympus contract or policy | Focused checks plus `FAST` |
| Significant installer/release work | Relevant installer fixtures and `FULL` before integration |
| Runtime behavior | Prioritize focused OpenCode V2 evidence |

Run FAST from the repository root:

```powershell
pwsh -NoProfile -File ./scripts/qualify.ps1 -Profile FAST
```

GitHub Actions also runs FAST for pull requests targeting `master`. FULL and RUNTIME are deliberately separate and are not CI defaults. See [the testing guidance](docs/DEVELOPMENT.md#choosing-qualification-by-change-risk).

The security workflow runs the same documentation and secret checks on pull requests, pushes to `master`, and manual runs. The Gitleaks gate downloads and verifies its pinned open-source CLI on each explicit invocation; it has no required Git hook and never publishes a report. See [the scanner and evidence-handling contract](SECURITY.md#secret-scanning-and-handling-evidence).

## Pull request checklist

- Summarize what changed and why.
- Link the issue when there is one.
- List the actual commands run and their results, including any **NOT RUN** gates.
- Keep the diff reviewable, avoid unrelated formatting, and do not rewrite historical release evidence.
- Allow a maintainer to review before merge; never rewrite an already published release tag.
