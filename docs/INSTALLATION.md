# Installation and uninstallation

## Start here

Run [Fast Install](../README.md#fast-install) once after v0.6.0 is published. This release is in preparation, not yet published; the remote command will work after publication, using the same v0.6.0 tag for the entrypoint and installer. The entrypoint asks for scope (**current project**, **another project**, or **global**) and harness (**OpenCode**, **Codex**, or **both**) when needed. A successful project or global install sets up the per-user `olympus` command and adds its `bin` folder to the current user's PATH; open a new PowerShell 7 shell afterward.

Then use `olympus version` and `olympus update` from any directory. The public [Fast Uninstall](../README.md#fast-uninstall) entrypoint and `olympus uninstall` remove only managed resources and Olympus's PATH entry.

The public PowerShell entrypoints are executable code. Once published, they select an immutable stable release and validate the tag/installer identity before use; GitHub's immutability assertion is not independent cryptographic signature verification.

## Requirements and platform limits

- Windows; this is the only currently qualified installer platform. Linux and macOS are not qualified.
- PowerShell 7 (`pwsh`) installed and available on `PATH`. Windows PowerShell 5.1 may start an entrypoint only when PowerShell 7 is also available; 5.1 alone is insufficient.
- Python 3.11+ is used internally by the global CLI; users invoke `olympus`, not `python -m olympus`.
- Git is required for project-scope installation and uninstallation. Use the root of a trusted Git worktree.
- Install OpenCode V2, Codex CLI, or both according to the selected harness. This does not establish runtime discovery for every version.

OpenCode V2 is in **ACTIVE DEVELOPMENT**. Codex is in **FROZEN COMPATIBILITY**: existing installation and safe-uninstall behavior remain, but no new capability or full parity is implied. Global installation is Windows-qualified. See [harness capabilities](HARNESS-CAPABILITIES.md) and [Codex compatibility](CODEX-COMPATIBILITY.md).

## Public PowerShell entrypoints

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.6.0/install-olympus.ps1')))
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.6.0/uninstall-olympus.ps1')))
```

Invoke the downloaded script block with `&` as shown.

When run in an interactive terminal with no selection parameters, either entrypoint asks for scope and harness. A valid partial selection asks only for the missing values. For example, `-Global` asks only for a harness, while `-Harness codex` asks only for scope. If all required values are supplied, the command runs without prompting and is suitable for non-interactive use. If a required value is missing and interactive input is unavailable, it exits with `ARGUMENTS_REQUIRED` instead of waiting for input.

### Scope and harness selection

| Scope | Parameters | Target |
|---|---|---|
| Current project | `-Project -Here` | Current directory; must be the Git worktree root |
| Another project | `-ProjectPath <path>` | The specified Git worktree root |
| Global | `-Global` | User-level runtime configuration |

`-Harness` accepts `opencode`, `codex`, or `all`; it has no implicit default. Supply `-Project` and `-Here` together. `-ProjectPath`, `-Global`, and the `-Project -Here` pair are mutually exclusive; contradictory choices are rejected. Do not mix those scope selectors. A quoted `-ProjectPath` may contain spaces.

The examples below fetch the public entrypoint text, then invoke it with explicit parameters. Run the `-Project -Here` examples from the project root. The project-path target intentionally contains spaces.

```powershell
$install = [scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.6.0/install-olympus.ps1'))
$uninstall = [scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.6.0/uninstall-olympus.ps1'))

# Install OpenCode in the current project, Codex in a project path, or both globally.
& $install -Project -Here -Harness opencode
& $install -ProjectPath 'C:\Users\Ada Lovelace\source\Sample Project' -Harness codex
& $install -Global -Harness all

# The corresponding safe uninstalls.
& $uninstall -Project -Here -Harness opencode
& $uninstall -ProjectPath 'C:\Users\Ada Lovelace\source\Sample Project' -Harness codex
& $uninstall -Global -Harness all
```

For non-interactive use, provide one complete scope selection and `-Harness` (for example, `pwsh -NoProfile -File .\install-olympus.ps1 -Project -Here -Harness all`). A lone `-Project` or `-Here` is invalid; use both. PowerShell also rejects combinations such as `-Global -ProjectPath ...`. Without a terminal or other usable interactive input, incomplete selections fail with `ARGUMENTS_REQUIRED`.

The twelve legacy install/uninstall wrappers remain for compatibility at `install/{project,global}/{opencode,codex,all}.ps1` and `uninstall/{project,global}/{opencode,codex,all}.ps1`. The unified entrypoints above are the two primary public commands.

## Release selection, identity, and executable source

The v0.6.0 entrypoint queries GitHub's `releases/latest` metadata and requires a valid stable tag with `immutable=true`, `draft=false`, `prerelease=false`, and a published timestamp. The launcher downloads installer/archive content pinned to that returned tag and checks the installer's version identity. It fails closed for missing, malformed, mutable, unpublished, or mismatched sources; it never falls back to `main` or `master`.

These checks establish release selection and tag identity, not cryptographic integrity. GitHub's immutability field is a platform assertion; the installer does not independently verify a signature or published SHA-256 for downloaded executable code. Review each downloaded stage separately if your trust policy requires it.

## Advanced: install from a local source checkout

Maintainers may run `install.ps1` directly against a trusted local checkout instead of using the Fast entrypoints. The checkout's declared release identity must match `-Version`; the installer still validates source identity and uses the existing bootstrap and safety checks. This advanced route installs the local checkout's content, not the currently published release.

```powershell
$source = (Resolve-Path '.').Path
$target = 'C:\Users\Ada Lovelace\source\Sample Project'
pwsh -NoProfile -File (Join-Path $source 'install.ps1') `
    -Version 'v0.6.0' -SourceRoot $source -Target $target -Scope project -Harness opencode
```

Use the version actually declared by the checkout; do not copy the example version blindly. Local-source installation is for advanced, trusted-checkout use and is not evidence that the corresponding release is published or immutable.

## Olympus CLI

The global command works from any directory and uses one product version. Python is an internal runtime dependency; users do not need a checkout or `python -m olympus`.

```powershell
olympus version
olympus update
olympus agents list
olympus nox set-model openai/gpt-6-luna
olympus nox set-effort high
olympus config list
olympus doctor
olympus install
olympus uninstall
```

`olympus update` selects an immutable stable release, refuses downgrades, preserves the user override file, and reports the prior/new version. If managed agents have changed, it lists their names and asks once; `y` permits the update, while `n`, Enter, or non-interactive input preserve them and stop. No hashes or old-version recovery are required.

`olympus <agent> set-model` accepts only an exact `provider/model-id` from the bundled [Models.dev](https://models.dev) catalog. `set-effort` accepts only levels declared for that model. Values are saved to the per-user Olympus configuration shown by `olympus config list`; installed global OpenCode agents consume those values. The catalog is checked in for offline, reproducible validation, so listing and diagnostics do not make a provider request. Olympus never checks API keys, subscriptions, quotas, or model access.

`olympus config list` shows effective model/effort values, precedence (**project override > global override > canonical defaults**), and absolute paths to each source. Scope-aware commands such as `agents list`, `config list`, and `doctor` select the managed OpenCode project at the current directory when one exists; otherwise they use global scope. Use `--scope project --target <absolute-worktree-root>` or `--scope global` to select explicitly. For example, `olympus doctor --scope project --target 'C:\Users\Ada Lovelace\source\Sample Project'` checks that project. Doctor is read-only: it validates JSON and declared model/effort values and checks managed installation state, but never applies edits or checks provider access. After manually editing JSON, use `olympus install --scope global --harness opencode --execute` for global configuration or `olympus update --scope project --target <absolute-worktree-root>` for project configuration to apply the effective values.

Project installation remains explicit and uses the existing ownership safeguards:

```powershell
olympus install --scope project --target 'C:\Users\Ada Lovelace\source\Sample Project' --harness opencode --dry-run
olympus install --scope project --target 'C:\Users\Ada Lovelace\source\Sample Project' --harness opencode --execute
olympus uninstall --scope project --target 'C:\Users\Ada Lovelace\source\Sample Project' --harness opencode --execute
```

`--dry-run` may use temporary acquisition/cache locations but does not write project resources. Global scope rejects `--target`; the official engine resolves the global root. Uninstall removes only unchanged, manifest-owned files. The CLI and update are qualified on Windows with PowerShell 7; Codex remains frozen compatibility.

## Installation safety

- Install only into a repository you trust. Project scope requires the Git worktree root.
- Installation uses ownership manifests and managed-file hashes; unrelated user files are preserved, and conflicting or drifted managed resources are not silently overwritten.
- Uninstall removes only unchanged, manifest-owned resources. Review any ownership or drift error; do not bypass it.
- `-VerifyOnly` is read-only and verifies the selected installed harness subset.
- Static installation does not establish runtime discovery on every runtime/version. Global installation is Windows-qualified only.

## Troubleshooting

- **`OLYMPUS_REQUIRES_POWERSHELL_7`** — install PowerShell 7 and make `pwsh` available on `PATH`.
- **`ARGUMENTS_REQUIRED`** — provide a complete scope and harness, or use a terminal with interactive input.
- **`ARGUMENTS_INVALID` or parameter-set error** — select exactly one valid scope: `-Project -Here`, `-ProjectPath <path>`, or `-Global`; provide `-Harness opencode`, `-Harness codex`, or `-Harness all`.
- **`LATEST_RELEASE_MUTABLE`, `LATEST_RELEASE_NOT_PUBLISHED`, or `LATEST_RELEASE_METADATA_*`** — stop. Do not switch to a branch URL or retry through a different installer.
- **`LATEST_RELEASE_IDENTITY_MISMATCH` / `LAUNCHER_BOOTSTRAP_CONTRACT_MISSING`** — stop; downloaded tag contents did not satisfy the expected release contract.
- **Git target or managed-file drift errors** — select the actual worktree root and review user changes. Do not delete or overwrite files to force installation.
- **Entrypoint URL returns not found** — check the official [Releases page](https://github.com/Edulynch/OpenCode-OlympusAgents/releases); do not substitute a branch URL or older launcher.
