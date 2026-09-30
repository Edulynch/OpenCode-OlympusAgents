# OpenCode vs Codex: evidence ledger

This document consolidates evidence already observed or statically qualified.
It does not declare a winner. The current branch is based on master
`c90ff16bbf70b3ae7fca53657f147c3bcd89be50` (`v0.3.0-beta.5`); no interactive
multi-agent smoke was repeated for this maintenance run. User-supplied runtime
evidence remains identified as such rather than relabeled as task-executed.

## OpenCode evidence

- Olympus declares full Aegis support: an explicitly invoked `/maintain`
  command enters the hidden Aegis agent, separate from Kael routing. Aegis is
  never a normal Kael child or automatic escalation route.
- Olympus `DENY` is a native hard boundary in OpenCode agent permissions and
  the Core authority contract. It is not an ASK/approval path.
- The passive Activity HUD reads OpenCode session state and displays active
  direct children. `tests/activity-hud/activity.test.mjs` statically exercises
  visibility, identity mapping, and no-interaction behavior.
- Olympus uses native OpenCode ASK where the policy says `ASK`; it is not
  described as pre-approval.
- Upstream issue [#1](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/1)
  remains **OPEN**: upstream result correlation has produced `No tool output
  found`. Olympus retains original-result reconciliation and a no-blind-retry
  rule; absence is not treated as failure or permission to duplicate work. This
  task did not attempt to fix upstream OpenCode.
- The Olympus-only maintenance plane and explicit-user `/maintain` boundary are
  part of Core. Ordinary user-project work remains outside Aegis.
- Project-local `VerifyOnly` is now managed-source/version/manifest/hash
  verification only. It does not run `opencode debug config` or `debug agents`
  in the target; issue #6's temporary-artifact path is tested with a mutating
  external-CLI probe.

## Codex evidence and limits

Previously supplied runtime evidence, audited in
`docs/CODEX-EXPERIMENT-STATUS.md` and `docs/CODEX-COMPATIBILITY.md`, records:

- root Kael: PASS;
- Kael → Veyra: PASS;
- Kael → Kovan → Nox functional path: PASS;
- bounded four-child fan-out/fan-in: PASS;
- four children simultaneously observed `RUNNING`;
- result delivery: PASS;
- ALLOW: supported in the observed path;
- ASK: native approval/adaptable; UI approval was previously confirmed;
- DENY: GAP; Aegis: GAP; activity visibility: basic/partial.

These are user-provided prior runtime observations and were not rerun here.
Codex custom-agent profiles/read-only modes are not treated as hard DENY.
Current `codex --help` on CLI `0.159.1` exposes sandbox choices
`read-only`, `workspace-write`, and `danger-full-access`, and approval choices
`on-request` and `never`; none establishes an Olympus DENY boundary that an
ordinary authorization cannot elevate. Result: **CODEX_DENY: GAP**. No adapter
support was added and Core was not weakened.

Codex supports custom-agent files and global instructions/profile surfaces, but
no demonstrated enforcement maps a user-only maintenance entry to a
distinguishable privileged Olympus context unavailable to Kael. Prompt text or
a profile name alone is not sufficient enforcement. Result:
**CODEX_AEGIS: GAP**. No Codex Aegis is generated. No approval UI was required
for either GAP finding.

The recorded smoke notes also retain diagnostic retries and partials: the
trivial root-only edit needed one safe revalidation after a read-only sandbox
attempt left its fixture unchanged; a non-interactive `codex exec` write was
rejected by its read-only sandbox and did not fulfill acceptance; a
Kovan-calculator test command lacked `python` in its sandbox, while the same
two fixture tests passed when run host-side by Aegis; two malformed CLI
invocations terminated before task start and do not count as task retries.
These cases do not establish interactive permission-profile enforcement or
comparative performance.

The modularized Codex adapter retained the existing Core authority, routing,
role, and model semantics; static qualifications and current diffs verify
technical IDs/models/routing references. No new runtime semantic-parity claim is
made. No quality, speed, cost, or token conclusions are inferred without
comparable measurements. Historical token counts below are reported only where
the runtime recorded them; monetary cost was unavailable.

## Current global-install foundation

This is an unreleased `feature/v0.4.0-foundation` branch feature, not a finished
release or harness victory.

- The public API adds `-Scope project|global`; project remains the default. The
  existing project manifest now records `scope = project`; legacy manifests
  without scope continue to mean project.
- OpenCode global path evidence: installed `opencode debug paths` reported the
  Windows config root under the user's `.config/opencode`; current official docs
  specify `~/.config/opencode`, global `agents/`, `commands/`, and `plugins/`,
  plus `OPENCODE_CONFIG_DIR`. Global Olympus writes those managed resources and
  leaves `opencode.json` untouched; Kael is available by explicit selection,
  not forced as the user's global default.
- The earlier disposable probe returned `[]` from `opencode debug agents` after
  installing the official-path global agent files. Installed CLI `2.0.20`
  source shows that `cli.debug.agents` calls `agent.list` through the default
  server connection (`Ir()` with no standalone option); its help does not offer
  `--standalone`. That command can report the managed service's roster rather
  than the temporary config's runtime. The current standalone equivalent is
  `opencode api --standalone --param directory=<fixture> agent.list`, backed by
  the installed OpenAPI operation `agent.list` (`GET /api/agent`).
- The repeatable `tests/global-runtime/qualify.ps1` run installed all 15 global
  resources into its isolated config root and queried standalone
  `agent.list` from a clean Git fixture without project-local Olympus files.
  The CLI exited 0 but returned `data: []`. Its logs confirmed the temporary
  `OPENCODE_CONFIG_DIR`, yet the private server still subscribed to the real
  Windows profile's `.opencode`, `.claude/skills`, and `.agents/skills` despite
  isolated `HOME`, `USERPROFILE`, `HOMEDRIVE`/`HOMEPATH`, `APPDATA`, XDG, and temp
  values. The user config and project fixture remained unchanged. This is not
  isolated evidence: it neither proves an Olympus install defect nor supports a
  runtime PASS. The qualifier rejects the profile leakage and preserves the
  response/logs/evidence under its printed temporary run directory. OpenCode
  global remains **PARTIAL**; the exact blocker is that a clean isolated
  standalone runtime both observes real profile paths and returns an empty agent
  roster.
- Codex global path evidence: current CLI help declares `~/.codex/config.toml`,
  `$CODEX_HOME`, and profiles at `$CODEX_HOME/<profile>.config.toml`; current
  official docs confirm `$CODEX_HOME/agents/` and global `AGENTS.md` (with
  `AGENTS.override.md` precedence). The foundation installs those global
  agents, root instructions, and an `olympus.config.toml` profile, leaves base
  `config.toml` untouched, and selects the profile with `codex --profile
  olympus`. `codex doctor --json` under the isolated `CODEX_HOME` confirmed the
  config/state root but reported no credentials. `codex agents --help` describes
  browsing agent sessions, not custom-agent discovery. No model-backed
  headless execution was performed; Codex global is **PARTIAL**, not SUPPORTED.
- `-Harness all` uses separate OpenCode and Codex global roots/manifests.
  `VerifyOnly` checks the selected global manifest/files without mixing scopes.
  User-owned global config, drifted resources, or conflicting user `AGENTS.md`
  are not overwritten.
- Upgrade uses manifest/hash ownership. Global uninstall removes only verified
  managed files and the manifest. Migration never removes the project-local
  install; the safe state is `GLOBAL_INSTALLED
  PROJECT_LOCAL_REMAINS_AS_OVERRIDE`. When invoked from a Git project, the
  current project-local Olympus manifest/version/hash state is reported.
- Only Windows PowerShell 7 bootstrap fixtures are qualified; the public
  installer remains launchable from PowerShell 5.1/7. Unix path descriptions
  come from official docs but no Unix runtime was available.

## Comparable real-task matrix

Blank/`NOT_RUN` values are unknown or unobserved, not zero. The two Codex
root-only results and historical measurements below come from the previously
recorded fixture evidence in `docs/CODEX-EXPERIMENT.md`; no OpenCode equivalent
was collected.

| TASK | HARNESS | SUCCESS | WALL_TIME | CHILDREN | RETRIES | APPROVALS | RESULT_LIFECYCLE_ERRORS | UNNECESSARY_ORCHESTRATION | MODEL | EFFORT | COST/TOKENS IF OBSERVED | NOTES |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| Trivial one-file edit | Codex | PASS, root-only | 109.9 s | 0 | 1 safe revalidation | 0 observed | 0 observed; no children | 0 observed | `gpt-6.1-sol` | `high` configured; not emitted by event | 170,393 input (148,224 cached), 717 output, 73 reasoning; cost unavailable | Initial read-only attempt left fixture unchanged; retry used workspace-write in disposable Git root. Not a Kovan/permission-profile smoke. |
| Trivial edit via `codex exec` | Codex | BLOCKED: read-only sandbox | 16 s | 0 | 0 | 0 observed; no TTY | 0 observed; terminal result consumed | 0 observed | `gpt-6.1-sol` | `high` configured; not emitted by event | 26,859 input (20,480 cached), 178 output; cost unavailable | Exit 0 did not mean acceptance: fixture remained pending after write rejection. No interactive approval. |
| Implementation + tests | Codex | PARTIAL | 69.7 s | 0 | 0 | 0 observed | 0 observed; no children | 0 observed | `gpt-6.1-sol` | `high` configured; not emitted by event | 84,593 input (77,824 cached), 501 output, 45 reasoning; cost unavailable | `python -m unittest` failed inside sandbox because `python` was unavailable; Aegis ran the same two fixture tests host-side and both passed. Not Kovan → Nox. |
| Equivalent task set | OpenCode | NOT_RUN | — | — | — | — | — | — | — | — | — | No apples-to-apples result exists. |

Global runtime classification: **OpenCode PARTIAL** (the isolated API probe
returned an empty roster while observing the user's profile), **Codex PARTIAL**
(isolated `CODEX_HOME` confirmed, but runtime agent discovery needs credentials).
See `docs/HARNESSES.md` for exact commands and the required Codex human smoke.

## Future real-task collection template

Do not populate with estimates. `COST/TOKENS IF OBSERVED` must distinguish
measured tokens from unreported cost.

| TASK | HARNESS | SUCCESS | WALL_TIME | CHILDREN | RETRIES | APPROVALS | RESULT_LIFECYCLE_ERRORS | UNNECESSARY_ORCHESTRATION | MODEL | EFFORT | COST/TOKENS IF OBSERVED | NOTES |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |  |  |  |
