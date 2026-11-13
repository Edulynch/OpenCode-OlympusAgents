# Installation and uninstallation

## Start here

Run [Fast Install](../README.md#fast-install) using the same `v0.6.1` tag for the public entrypoint and installer. The entrypoint asks for scope (**current project**, **another project**, or **global**) and harness (**OpenCode**, **Codex**, or **both**) when needed. A successful project or global install sets up the per-user `olympus` command and adds its `bin` folder to the current user's PATH; open a new PowerShell 7 shell afterward.

Then use `olympus version` and `olympus update` from any directory. The public [Fast Uninstall](../README.md#fast-uninstall) entrypoint and `olympus uninstall` remove only managed resources and Olympus's PATH entry.

The public PowerShell entrypoints are executable code. They select an immutable stable release and validate the tag/installer identity before use; GitHub's immutability assertion is not independent cryptographic signature verification.

## Requirements and platform limits

- Windows; this is the only currently qualified installer platform. Linux and macOS are not qualified.
- PowerShell 7 (`pwsh`) installed and available on `PATH`. Windows PowerShell 5.1 may start an entrypoint only when PowerShell 7 is also available; 5.1 alone is insufficient.
- Python 3.11+ is used internally by the global CLI; users invoke `olympus`, not `python -m olympus`.
- Git is required for project-scope installation and uninstallation. Use the root of a trusted Git worktree.
- Install OpenCode V2, Codex CLI, or both according to the selected harness. This does not establish runtime discovery for every version.

OpenCode V2 is in **ACTIVE DEVELOPMENT**. Codex is in **FROZEN COMPATIBILITY**: existing installation and safe-uninstall behavior remain, but no new capability or full parity is implied. Global installation is Windows-qualified. See [harness capabilities](HARNESS-CAPABILITIES.md) and [Codex compatibility](CODEX-COMPATIBILITY.md).

## Public PowerShell entrypoints

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.6.1/install-olympus.ps1')))
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.6.1/uninstall-olympus.ps1')))
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
$install = [scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.6.1/install-olympus.ps1'))
$uninstall = [scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.6.1/uninstall-olympus.ps1'))

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

The v0.6.1 entrypoint queries GitHub's `releases/latest` metadata and requires a valid stable tag with `immutable=true`, `draft=false`, `prerelease=false`, and a published timestamp. The launcher downloads installer/archive content pinned to that returned tag and checks the installer's version identity. It fails closed for missing, malformed, mutable, unpublished, or mismatched sources; it never falls back to `main` or `master`.

These checks establish release selection and tag identity, not cryptographic integrity. GitHub's immutability field is a platform assertion; the installer does not independently verify a signature or published SHA-256 for downloaded executable code. Review each downloaded stage separately if your trust policy requires it.

## Advanced: install from a local source checkout

Maintainers may run `install.ps1` directly against a trusted local checkout instead of using the Fast entrypoints. The checkout's declared release identity must match `-Version`; the installer still validates source identity and uses the existing bootstrap and safety checks. This advanced route installs the local checkout's content, not the currently published release.

```powershell
$source = (Resolve-Path '.').Path
$target = 'C:\Users\Ada Lovelace\source\Sample Project'
pwsh -NoProfile -File (Join-Path $source 'install.ps1') `
    -Version 'v0.6.1' -SourceRoot $source -Target $target -Scope project -Harness opencode
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

### Command scopes and effects

`--source` (when used) is an absolute trusted Olympus source checkout; it is
not the installation target. The following scope auto-detection applies only
to commands that select an effective user configuration: `update`, `agents
list`, `config list`, `doctor`, and role aliases. They use a managed OpenCode
project at the current directory when found, otherwise global scope. Supply
`--scope` and, for project scope, `--target` to be explicit. Other commands
below do not inherit that rule.

| Command | Scope and target | Effect |
|---|---|---|
| `olympus update` (`upgrade`) | Auto-detects, or accepts `--scope project\|global` and project `--target` | Applies the immutable stable release update; Windows/PowerShell 7 only. There is no preview mode. |
| `olympus install` | Defaults to `--scope global --harness opencode`; project requires absolute `--target`. `--harness opencode\|codex\|all`; optional `--version <tag>` | `--dry-run` previews. Otherwise the installer executes, whether or not `--execute` is written. `--execute` makes that intent explicit. |
| `olympus uninstall` | Same defaults and target rules as install | Omitting `--dry-run` executes. Global uninstall supports preview; project uninstall has no dry-run and rejects it. Execution removes only unchanged manifest-owned resources (and global CLI state where applicable). |
| `olympus <role> set-model <id>` / `set-effort <value>` | `<role>`: `kael`, `veyra`, `orin`, `atlas`, `kovan`, `argus`, `nox`, `vera`, `talos`, `thales`, or `helios`; auto-detects or accepts scope/target | Writes the user override immediately and updates a managed installed OpenCode agent when applicable. This is not a canonical source edit and has no dry-run flag. |
| `olympus models list`, `olympus agents list` | Canonical source for models; agents list uses auto-detection or explicit scope/target | Read-only lists. `models list` is offline; `agents list` shows effective values and their sources. |
| `olympus models set-family <family> --opencode <id> --codex <id>` / `olympus agents set-model <role> [--family <family>] [--effort <value>]` (at least one option required) | Canonical checkout selected by `--source`, or this CLI's bundled source | Edits canonical model intent. `--dry-run` previews; omitting it executes the source edit. JSON output for these edits requires `--dry-run`. |
| `olympus config list` / `olympus config check` | List uses auto-detection or explicit scope/target; check reads the selected source and harness | Both are read-only. List shows effective values, precedence, and paths; check compares renderer output without writing. |
| `olympus config apply --scope project\|global --harness opencode\|codex\|all` | Project requires an absolute existing worktree `--target`; global forbids `--target` | Exactly one of `--dry-run` or `--execute` is required. Preview does not write target resources; execution applies the selected managed configuration. Global execution currently supports OpenCode only. |
| `olympus config recover` | No scope recovers a pending canonical source edit; project recovery requires `--scope project --target`; global recovery uses `--scope global --harness opencode` | Explicitly reconciles pending transaction state and may change files. Use only for the matching pending operation; global recovery is OpenCode-only. |
| `olympus status` | Defaults to project and requires `--target`; use `--scope global` without a target for global metadata | Read-only reported manifest/install metadata; it does not verify file integrity. |
| `olympus doctor` | Auto-detects, or accepts explicit scope/target and `--harness`; project scope requires `--target` | Read-only configuration and managed-installation diagnostics. It does not apply repairs or check provider access. |

`olympus update` selects an immutable stable release, refuses downgrades, preserves the user override file, and reports the prior/new version. If managed agents have changed, it lists their names and asks once; `y` permits the update, while `n`, Enter, or non-interactive input preserve them and stop. No hashes or old-version recovery are required.

`olympus <agent> set-model` accepts a syntactically valid `provider/model-id`. Known models are checked against the bundled [Models.dev](https://models.dev) catalog and their declared effort levels; newer or custom IDs absent from the snapshot are allowed with a compatibility warning. Olympus does not test model access. Values are saved to the per-user Olympus configuration shown by `olympus config list`; installed global OpenCode agents consume those values. The catalog is checked in for offline, reproducible validation, so listing and diagnostics do not make a provider request. Olympus never checks API keys, subscriptions, quotas, or model access.

#### Reproducing a Models.dev catalog snapshot

Refresh from a saved raw `https://models.dev/api.json` payload; this recipe
does not make a network or provider request. Preserve the payload bytes as
`models.dev.raw.json` (do not open and re-save it in an editor), set the date
the payload was captured, then run this PowerShell-compatible Python recipe.
It derives provider/model IDs from the API mapping, retains the declared
reasoning/tool-call booleans, and records only explicitly listed `effort`
values; it does not infer defaults. Duplicate or malformed data fails before
the catalog is written.

```powershell
$raw = (Resolve-Path '.\models.dev.raw.json').Path
$catalog = 'olympus/core/models-dev.json'
$snapshotDate = '2026-11-13' # Set to the saved payload's capture date.
@'
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f"duplicate JSON key: {key}"
        result[key] = value
    return result

raw_path, catalog_path, snapshot_date = sys.argv[1:4]
assert date.fromisoformat(snapshot_date).isoformat() == snapshot_date
raw = Path(raw_path).read_bytes()
providers = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
assert isinstance(providers, dict) and providers
models = {}
for provider_id, provider in sorted(providers.items()):
    assert isinstance(provider_id, str) and provider_id and isinstance(provider, dict)
    provider_models = provider.get("models")
    assert isinstance(provider_models, dict)
    for model_key, model in sorted(provider_models.items()):
        assert isinstance(model_key, str) and model_key and isinstance(model, dict)
        assert model.get("id") == model_key
        reasoning, tool_call = model.get("reasoning"), model.get("tool_call")
        assert type(reasoning) is bool and type(tool_call) is bool
        options = model.get("reasoning_options", [])
        assert isinstance(options, list)
        effort_options = []
        for option in options:
            assert isinstance(option, dict) and isinstance(option.get("type"), str)
            if option["type"] == "effort":
                effort_options.append(option)
        assert len(effort_options) <= 1
        efforts = effort_options[0].get("values", []) if effort_options else []
        assert isinstance(efforts, list)
        assert all(isinstance(value, str) and value for value in efforts)
        assert len(efforts) == len(set(efforts))
        model_id = f"{provider_id}/{model_key}"
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*/[A-Za-z0-9][A-Za-z0-9._:/-]*", model_id)
        assert model_id not in models
        models[model_id] = {
            "efforts": efforts, "reasoning": reasoning, "tool_call": tool_call,
        }

assert models
catalog = {
    "model_count": len(models),
    "models": dict(sorted(models.items())),
    "provider_count": len(providers),
    "schema_version": 1,
    "snapshot_date": snapshot_date,
    "source": "https://models.dev/api.json",
    "source_sha256": hashlib.sha256(raw).hexdigest(),
}
assert catalog["model_count"] == len(catalog["models"])
assert catalog["model_count"] == sum(len(provider["models"]) for provider in providers.values())
assert catalog["provider_count"] == len(providers)
assert len(catalog["source_sha256"]) == 64
Path(catalog_path).write_bytes(
    (json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
)
print(f"models={catalog['model_count']} providers={catalog['provider_count']} sha256={catalog['source_sha256']}")
'@ | python -B - $raw $catalog $snapshotDate
```

Review the resulting `model_count`, `provider_count`, source hash, and complete
diff against the saved payload before accepting it:

```powershell
git diff --check -- olympus/core/models-dev.json
git diff --stat -- olympus/core/models-dev.json
git diff -- olympus/core/models-dev.json
```

Keep unknown/custom-model warnings and offline behavior. A newly absent model
may be treated as unknown; never replace an explicit capability or effort
declaration with an inferred default.

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
