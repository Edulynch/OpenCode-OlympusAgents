# Working on OlympusAgents

Olympus Core defines the product; the OpenCode adapter supplies its supported runtime representation. These instructions apply to this source repository, not to projects that install Olympus.

## Where files belong

| Path | What belongs there |
| --- | --- |
| `olympus/` | Python CLI, diagnostics, installation lifecycle, and ownership/recovery logic. Keep shared platform behavior here rather than duplicating it in shell wrappers. |
| `olympus/core/` | Canonical model and display identity data. Keep existing role IDs aligned across `models.toml`, `identities.toml`, and the role files. |
| `olympus/roles/` and `olympus/policies/` | Role responsibilities and shared behavioral rules, respectively. Keep runtime-specific instructions out of Core. |
| `olympus/harnesses/` | Capability declarations and adapter sources, including OpenCode prompts, metadata, commands, and plugins. |
| `scripts/` | Thin CLI/bootstrap entrypoints and maintainer tooling. Match the interpreter and dependencies of the entrypoint you change. |
| `install/` and `uninstall/` | Compatibility entrypoints; see [install](install/AGENTS.md) and [uninstall](uninstall/AGENTS.md). |
| `tests/`, `specs/`, `docs/`, `.github/` | Follow the local instructions for [tests](tests/AGENTS.md), [release tests](tests/release/AGENTS.md), [specifications](specs/AGENTS.md), [documentation](docs/AGENTS.md), and [CI](.github/AGENTS.md). |

Keep maintainer instructions for `olympus/` and `scripts/` here: Windows CLI packaging collects files recursively from both trees. The renderer also treats Markdown in the canonical role directory as role definitions.

## Change and validation boundaries

- Edit the [Core](olympus/README.md) or adapter source, not generated `.opencode` resources, `opencode.jsonc`, or `docs/HARNESS-CAPABILITIES.md`. Use the [renderer workflow](docs/HARNESSES.md) when generated outputs are in scope.
- Preserve existing user changes. Do not stage, commit, push, publish, or modify a real user installation unless requested.
- Contributor PRs target `develop`; only a human manually merges the canonical `develop` → `master` promotion. See [promotion and release procedure](docs/DEVELOPMENT.md#promotion-and-automatic-releases); do not change repository settings or enable the opt-in release variable as part of source implementation.
- From the repo root, use `python -B scripts/check_docs.py` and `git diff --check` for Markdown changes. For product changes use the smallest relevant check in the [development guide](docs/DEVELOPMENT.md#choosing-qualification-by-change-risk); keep mandatory CI and release gates and distinguish static or mocked evidence from native execution.
