# Documentation index

Start with the quick guide in [English](../README.md) or [Español](../README.ES.md) for examples, installation, and the current nine-role team: Kael and Atlas as separate primaries, plus Kael's seven specialists. Orin and Argus are retired. Then open the guide for the subject you need.

## Sources of truth

| Subject | Canonical source | Use |
| --- | --- | --- |
| First install and removal | [README](../README.md) and [installation guide](INSTALLATION.md) | The README has the two first-run commands; the guide explains supported platforms, parameters, safeguards, and troubleshooting. |
| Team, commands, and prompt examples | [README](../README.md#the-team) and [workflow guide](WORKFLOWS.md) | The README introduces both primaries and Kael's seven specialists; the workflow guide explains `/olympus.ultra`, `/olympus.performance`, and `/olympus.performance-ultra`. Canonical behavior stays in Core. |
| Olympus roles, routing, authority, and policies | [Olympus Core](../olympus/README.md) | Edit the canonical Core or adapter source when behavior changes. Generated harness files are outputs. |
| Harness capabilities and support status | [Capability source](../olympus/harnesses/capabilities.toml) and [OpenCode capability contract](HARNESS-CAPABILITIES.md) | OpenCode is the only currently supported Olympus runtime. |
| Feature requirements and evidence | [`specs/`](../specs/README.md) | Keep implemented and retrospective contracts there. `specs/future/` is a proposal register, not implementation authority. |
| Spec Kit setup and local customizations | [Spec Kit audit](../.specify/README.md), [constitution](../.specify/memory/constitution.md), and [template overrides](../.specify/templates/overrides/) | Spec Kit stays the specification workflow. The local audit records its version and update decision. |
| Release history | [Changelog](../CHANGELOG.md) and the dated release records below | Release documents preserve what shipped and the evidence known at that time; they do not describe a newer release. |
| Issue triage, decisions, gates, and WIP | [GitHub issues](https://github.com/Edulynch/OpenCode-OlympusAgents/issues) | GitHub and canonical specs remain authoritative. Follow #92 for mission/cleanup policy. |

Issue #91 keeps documentation versioned in this repository. Enabling or publishing a Wiki remains outside this change and subject to #67; any future Wiki navigation should point back here rather than become a second copy of contracts. Installation UX work in #66 remains a separate scope; this index only links to the existing guide.

## User guides

- [Installation](INSTALLATION.md) — install and remove Olympus, check requirements, and troubleshoot.
- [Workflows](WORKFLOWS.md) — use Olympus commands and follow task examples.
- [Worktrees](WORKTREES.md) — set up Olympus in an OpenCode Git worktree.

## Technical reference

- [Harnesses](HARNESSES.md) — source layout, renderer, generated outputs, and managed installation contract.
- [Harness capabilities](HARNESS-CAPABILITIES.md) — generated support matrix; edit the [capability source](../olympus/harnesses/capabilities.toml), not the generated page.

## Contributing and project status

- [Development](DEVELOPMENT.md) — architecture, qualification, the manual promotion path, and opt-in immutable Release gates.
- [Roadmap](ROADMAP.md) — shipped, in-validation, and proposed work; not a release promise or implementation authorization.
- [Documentation organization](AGENTS.md) — where to put new pages and how to check them. See the conventions for [guides](guide/AGENTS.md), [reference](reference/AGENTS.md), and [assets](assets/AGENTS.md).

## Historical records

- [v0.4.9 release record](RELEASE-v0.4.9.md) — preserved release facts and the dated example linked from the constitution.
- [v0.5.0 qualification snapshot](RELEASE-v0.5.0.md) — pre-publication evidence preserved alongside the [stable v0.5.0 release](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/tag/v0.5.0).

The seven removed pages from `docs/history/` remain reviewable in the [pre-cleanup tree](https://github.com/Edulynch/OpenCode-OlympusAgents/tree/5e9bec1a5eb51d9bfcac93931f0d165a48b4a53c/docs/history).

The roadmap remains a status summary; it does not replace specifications or release records.

## Related repository documentation

- [Specs catalog](../specs/README.md), [future proposal register](../specs/future/README.md), current feature contracts under `specs/001-portable-olympus-cli/`, and the v0.4.9 retrospective evidence under `specs/retrospective/v0.4.9/`.
- [.specify audit](../.specify/README.md), [constitution](../.specify/memory/constitution.md), and project template overrides under `.specify/templates/overrides/`.
- [Olympus Core overview](../olympus/README.md), [harness overview](../olympus/harnesses/README.md), role definitions under `olympus/roles/`, and policies under `olympus/policies/`.
- Root references: [README](../README.md), [CONTRIBUTING](../CONTRIBUTING.md), [SECURITY](../SECURITY.md), [CHANGELOG](../CHANGELOG.md), and [LICENSE](../LICENSE).

## Maintenance and link checks

When an accepted change alters installation, runtime behavior, authority, harness support, or release procedure, update the existing canonical guide or contract for that subject. Record a release in the existing changelog and dated release record when one is made. Preserve completed decisions in `docs/history/` and link any replacement to the earlier rationale. Small code changes do not need a new page, ADR framework, or Wiki copy.

Run `python -B scripts/check_docs.py` after editing Markdown. It checks local links, heading anchors, and index coverage in tracked and non-ignored untracked Markdown at the repository root and under `docs/`, `specs/`, `tests/`, `olympus/`, and `.specify/`, including fixture Markdown. It does not fetch external URLs; verify those when their target matters. GitHub Actions runs the same local check.

The index gate emits a fixed **NOTICE for 6 unversioned historical attachment links** in the v0.4.9 evidence report. Those temporary logs and cleanup artifacts are not part of the Git baseline, so those exact links are not validated; some files may remain in a local checkout. All other missing document targets fail the gate, including a new broken link in that same report. The notice does not exclude the evidence report or any Gitleaks scan scope.
