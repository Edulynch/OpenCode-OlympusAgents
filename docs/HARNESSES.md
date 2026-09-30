# Olympus Core and harness adapters

**Olympus Core defines what Olympus means.** A harness adapter defines how a
runtime expresses that same Core. The officially supported harnesses are
OpenCode and Codex; capability gaps are explicit and never weaken a Core
guarantee.

## Source layout

| Source | Owns |
|---|---|
| `olympus/roles/<role>.md` | One conceptual definition and responsibility boundary for each of the 12 canonical roles. Kael is the ROOT ORCHESTRATOR independently of runtime. |
| `olympus/core/models.toml` | The only role → model family / reasoning effort map, plus each family's OpenCode and Codex identifier. A family upgrade is one edit followed by rendering and qualification. |
| `olympus/policies/routing.md` and `orchestration.toml` | Specialist suppression, trivial fast path, direct-root ownership, bounded parallelism, and the canonical maximum of four children. |
| `olympus/policies/result-lifecycle.md` | Question barrier, completion barrier, original-result reconciliation, and no-blind-retry semantics. |
| `olympus/policies/authority.md` | Canonical ALLOW / ASK / DENY meaning. |
| `olympus/policies/maintenance-plane.md` | Olympus-only privileged maintenance semantics and the explicit-user boundary. |
| `olympus/harnesses/capabilities.toml` | The two-harness capability contract (`SUPPORTED`, `ADAPTABLE`, `PARTIAL`, `GAP`, `NOT_NEEDED`). |
| `olympus/harnesses/opencode/` | OpenCode permission/frontmatter, native role-prompt representation, `/maintain`, default config, and activity plugin sources. |
| `olympus/harnesses/codex/` | Codex-native role-prompt representation, root instructions, project config, and permission profile. Codex has no Aegis agent. |

Adapter prompt files intentionally contain runtime-specific instructions, not
second canonical role or model definitions. Changes to Olympus meaning start in
Core; update the relevant adapter representation and qualifications without
copying or deleting a Core guarantee.

## Render and check

Requires Python 3.11+ from the local standard library; no network or packages
are needed.

```powershell
python scripts/render_harnesses.py render --harness opencode
python scripts/render_harnesses.py render --harness codex
python scripts/render_harnesses.py render --harness all
python scripts/render_harnesses.py check --harness all
python tests/harness-core/qualify.py
```

`render` is deterministic and idempotent. `check` is read-only: it compares
expected bytes in memory, reports every missing/drifted output, creates no
temporary repository files, and exits nonzero on drift. Generated files contain
a parser-safe generated marker; **edit Core/adapter source, not generated
outputs**.

## Generated outputs

| Adapter | Managed/generated outputs |
|---|---|
| OpenCode | `.opencode/agents/**`, `.opencode/commands/maintain.md`, `.opencode/plugins/olympus-activity/**`, `opencode.jsonc` |
| Codex | `CODEX.md`, `.codex/config.toml`, `.codex/agents/*.toml` |
| Shared contract presentation | `docs/HARNESS-CAPABILITIES.md` |

OpenCode preserves the current `/maintain` command, hidden Aegis, native ASK,
hard DENY, Activity HUD, roles, models, permissions, and installer-managed
surface. The current OpenCode installer continues to consume the checked-in
generated OpenCode files and its existing VerifyOnly path is qualified. It is
not redesigned here.

Codex uses its root thread as Kael, custom specialists, per-role model/effort,
native multi-agent tools, bounded fan-out/fan-in, child result delivery, and
native activity visibility. Current user-provided runtime evidence records
Kael root, Kael→Veyra, Kovan→Nox functional work, four-child fan-out/fan-in,
concurrency of at least two, result delivery, ALLOW, and native ASK approval
as passing/confirmed; these smokes were **not rerun** during modularization.
`tests/codex/validate_profile.py` remains static qualification only.

## Declared Codex gaps

- `DENY = GAP`: Codex does not currently provide equivalent hard Olympus
  resource protection. Its read-only permission-profile rules remain documented
  honestly as policy/profile protection, not an immutable ACL.
- `AEGIS = GAP`: no Codex Aegis or unsafe substitute is installed.
- `RESULT_DELIVERY = SUPPORTED`: native delivery passed in the user-provided runtime evidence; missing-result recovery remains a separate `PARTIAL` capability.
- `ASK = ADAPTABLE`: native approval is used, not claimed as an identical
  per-role Olympus grant. Native requests from child threads can be visible
  outside Kael, so question centralization is `PARTIAL`.
- `RESULT_RECONCILIATION = PARTIAL`: Core requires reconciliation; successful
  delivery is observed, but recovery of a missing Codex result is not claimed as
  runtime-qualified.
- `ACTIVITY_VISIBILITY = PARTIAL`: use native Codex visibility; no equivalent
  Activity HUD is recreated.

The Codex installer / VerifyOnly path is a documented next task. A future
harness can be added through another adapter only if it can satisfy and honestly
declare the Olympus capability contract.
