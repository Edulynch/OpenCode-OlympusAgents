# Documentation index

Start with the root [README](../README.md) for installation and the short product overview. This index maps current guidance to its source of truth and keeps completed work and old decisions easy to find.

## Sources of truth

| Subject | Canonical source | Use |
| --- | --- | --- |
| First install and removal | [README](../README.md) and [installation guide](INSTALLATION.md) | The README has the two first-run commands; the guide explains supported platforms, parameters, safeguards, and troubleshooting. |
| Olympus roles, routing, authority, and policies | [Olympus Core](../olympus/README.md) | Edit the canonical Core or adapter source when behavior changes. Generated harness files are outputs. |
| Harness capabilities and support status | [Capability source](../olympus/harnesses/capabilities.toml), [capability matrix](HARNESS-CAPABILITIES.md), and [Codex compatibility policy](CODEX-COMPATIBILITY.md) | The TOML file owns capability data; the rendered matrix is a read-only view. Codex remains at its documented frozen baseline. |
| Feature requirements and evidence | [`specs/`](../specs/README.md) | Keep implemented and retrospective contracts there. `specs/future/` is a proposal register, not implementation authority. |
| Spec Kit setup and local customizations | [Spec Kit audit](../.specify/README.md), [constitution](../.specify/memory/constitution.md), and [template overrides](../.specify/templates/overrides/) | Spec Kit stays the specification workflow. The local audit records its version and update decision. |
| Release history | [Changelog](../CHANGELOG.md) and the dated release records below | Release documents preserve what shipped and the evidence known at that time; they do not describe a newer release. |

Issue #91 keeps documentation versioned in this repository. Enabling or publishing a Wiki remains outside this change and subject to #67; any future Wiki navigation should point back here rather than become a second copy of contracts. Installation UX work in #66 remains a separate scope; this index only links to the existing guide.

## Current guidance and release records

The files below are the 9 documents retained at the top of `docs/`. No per-document names or CODEOWNERS rules were recorded; the owner column assigns a maintainer area as a proposed responsibility, not a named person.

| Document | Purpose and audience | State, relationship, and incoming references | Proposed owner |
| --- | --- | --- | --- |
| [CODEX-COMPATIBILITY.md](CODEX-COMPATIBILITY.md) | Frozen Codex support contract and evidence limits for contributors | **Vigente.** Canonical Codex compatibility policy; linked by README, constitution, and contributor guidance. Historical experiments are indexed below. | Repository maintainers |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Architecture, contribution, installation details, qualification, and release process | **Vigente.** Canonical contributor and development guide; links the Issue #8 historical evidence. | Repository maintainers |
| [HARNESS-CAPABILITIES.md](HARNESS-CAPABILITIES.md) | Operator-facing capability matrix | **Vigente, generated.** Rendered from `olympus/harnesses/capabilities.toml`; edit the source and use the existing renderer. | Core maintainers (source); renderer-owned output |
| [HARNESSES.md](HARNESSES.md) | Harness map and installation/output reference | **Vigente.** Maintainer and contributor reference; Core and the renderer define behavior. Historical evaluations link to this page. | Repository maintainers |
| [INSTALLATION.md](INSTALLATION.md) | Detailed public install, removal, scope, and recovery guide | **Vigente.** Canonical extended installer guide; the README remains the first-run entrypoint. | Repository maintainers |
| [ROADMAP.md](ROADMAP.md) | Directional shipped, in-validation, and proposed work | **Vigente, directional.** Not a release promise or implementation authorization; links to closed Phase 12 results. | Repository maintainers |
| [WORKTREES.md](WORKTREES.md) | Worktree setup and use | **Vigente.** Operational guidance; related retrospective behavior is recorded under `specs/`. | Repository maintainers |
| [RELEASE-v0.4.8.md](RELEASE-v0.4.8.md) | v0.4.8 release record | **Histórico.** Preserved release facts; superseded as current-version guidance by later release records. | Release maintainer (proposed role) |
| [RELEASE-v0.4.9.md](RELEASE-v0.4.9.md) | v0.4.9 release record | **Histórico.** Preserved release facts; remains linked from the constitution as a dated example. | Release maintainer (proposed role) |

## Historical records

These 7 pages moved from `docs/` to `docs/history/`. Their decisions, status statements, and evidence remain unchanged; only relative links were adjusted. The historical evidence acquisition snapshot under `specs/001-portable-olympus-cli/evidence/` retains the original paths as provenance.

| Move mapping: `docs/<name>` → `docs/history/<name>` | Purpose, state, and relationship | Incoming references | Proposed owner |
| --- | --- | --- | --- |
| [CODEX-EXPERIMENT.md](history/CODEX-EXPERIMENT.md) | **Histórico.** Original harness-comparison notes; current support policy lives in CODEX-COMPATIBILITY and DEVELOPMENT. | Evidence acquisition snapshot | Repository maintainers |
| [CODEX-EXPERIMENT-STATUS.md](history/CODEX-EXPERIMENT-STATUS.md) | **Histórico.** Experiment status snapshot; its current Codex status is superseded by CODEX-COMPATIBILITY and DEVELOPMENT. | Evidence acquisition snapshot | Repository maintainers |
| [HARNESS-EVALUATION.md](history/HARNESS-EVALUATION.md) | **Histórico.** Earlier evidence ledger, retained with its original qualifications; it is not the completed Phase 12 results ledger. | Evidence acquisition snapshot | Repository maintainers |
| [DEFECT-PHASE11-CASE-E-ROUTING.md](history/DEFECT-PHASE11-CASE-E-ROUTING.md) | **Histórico, cerrado.** Bounded Case E diagnosis and correction; the fixture instructions retain a link to this record. | Phase 11 RUNME; evidence acquisition snapshot | Repository maintainers |
| [ISSUE-8-CHECKPOINT-RESUME.md](history/ISSUE-8-CHECKPOINT-RESUME.md) | **Histórico.** Evidence for the exact same-session continuation; it does not resolve the later open compaction report. | DEVELOPMENT; evidence acquisition snapshot | Repository maintainers |
| [PHASE12-CROSS-HARNESS-PLAN.md](history/PHASE12-CROSS-HARNESS-PLAN.md) | **Histórico, cerrado.** Frozen plan and constraints; the results ledger supersedes its earlier no-trial status. | Phase 12 results ledger | Repository maintainers |
| [PHASE12-CROSS-HARNESS-RESULTS.md](history/PHASE12-CROSS-HARNESS-RESULTS.md) | **Histórico, cerrado.** Six-execution Phase 12 results and limits; authoritative for that evaluation. | Changelog, roadmap, Phase 12 plan | Repository maintainers |

No exact duplicate documents were removed. The experiment and evaluation records overlap with current compatibility guidance, but retain distinct historical evidence. The roadmap remains a status summary; it does not replace specifications or release records.

## Related repository documentation

- [Specs catalog](../specs/README.md), [future proposal register](../specs/future/README.md), current feature contracts under `specs/001-portable-olympus-cli/`, and the v0.4.9 retrospective evidence under `specs/retrospective/v0.4.9/`.
- [.specify audit](../.specify/README.md), [constitution](../.specify/memory/constitution.md), and project template overrides under `.specify/templates/overrides/`.
- [Olympus Core overview](../olympus/README.md), [harness overview](../olympus/harnesses/README.md), role definitions under `olympus/roles/`, and policies under `olympus/policies/`.
- Root references: [README](../README.md), [CONTRIBUTING](../CONTRIBUTING.md), [SECURITY](../SECURITY.md), [CHANGELOG](../CHANGELOG.md), and [LICENSE](../LICENSE).

## Maintenance and link checks

When an accepted change alters installation, runtime behavior, authority, harness support, or release procedure, update the existing canonical guide or contract for that subject. Record a release in the existing changelog and dated release record when one is made. Preserve completed decisions in `docs/history/` and link any replacement to the earlier rationale. Small code changes do not need a new page, ADR framework, or Wiki copy.

Run `python -B scripts/check_docs.py` after editing Markdown. It checks local links, heading anchors, and index coverage in tracked and non-ignored untracked Markdown at the repository root and under `docs/`, `specs/`, `tests/`, `olympus/`, and `.specify/`. It skips generated harness adapter copies and the synthetic fixture trees `tests/codex/fixtures/` and `tests/phase11-integrated-routing/fixtures/`. It does not fetch external URLs; verify those when their target matters. GitHub Actions runs the same local check.
