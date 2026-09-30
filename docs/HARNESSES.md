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
| `olympus/policies/maintenance-plane.md` | Trusted current-user `/maintain` authorization, task-scoped Aegis authority, and normal Kael-plane protections. |
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

The project-local installer accepts `-Harness opencode`, `-Harness codex`, or
`-Harness all`; the default remains `opencode` for the existing one-line install
experience. It discovers generated adapter outputs under `.opencode/**` and
`.codex/**` and the generated root file for each harness, so role rosters and
policies are not copied into a second installer inventory. Additions are
non-destructive: choosing one harness never removes the other.

Managed ownership remains hash-based. A manifest records `installed_harnesses`
and the union of managed output hashes. Existing beta.4 OpenCode manifests with
no harness field are interpreted as OpenCode-only and upgraded in place. For an
OpenCode installation the manifest remains `.opencode/orchestrator-install.json`;
a Codex-only installation uses `.codex/orchestrator-install.json`, so it does not
create `.opencode/**` or `opencode.jsonc`. Adding OpenCode to Codex safely moves
the manifest to the OpenCode location while retaining Codex outputs. Differing
unowned destinations are conflicts; exact generated Codex files may be adopted.
VerifyOnly checks only the requested harness subset, so drift in the other
installed harness does not invalidate a subset verification. It is read-only.

OpenCode still provides the `/maintain` command, hidden Aegis, native ASK, hard
DENY, Activity HUD, roles, models, permissions, and installer-managed surface.
Codex installation does not imply capability parity: Codex multi-agent and
result delivery are supported, ALLOW is supported, ASK is adaptable, DENY and
Aegis remain gaps, and activity visibility is partial/basic. See the generated
[capability contract](HARNESS-CAPABILITIES.md).

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

Canonical project-local command examples (replace `<TAG>` with a published tag
that contains this installer):

```powershell
# OpenCode only (also the default)
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1 | iex

# Codex only
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness codex

# Both harnesses
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness all

# Verify only the selected managed surface (read-only)
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness opencode -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness codex -Target (Get-Location).Path -VerifyOnly
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/<TAG>/install.ps1'))) -Harness all -Target (Get-Location).Path -VerifyOnly
```

No global Olympus installer, plugin framework, automatic harness detection, or
additional harness is introduced. A future harness may be added only through a
separate adapter that satisfies and honestly declares the Olympus capability
contract.
