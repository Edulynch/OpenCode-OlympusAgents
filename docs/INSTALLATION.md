# Installation and uninstallation

## Start here

The [Fast Install](../README.md#fast-install) is global and OpenCode-only. It has no project/harness selectors or menus, and the current directory never selects the installation target. It sets up the per-user `olympus` command and its user PATH entry; open a new PowerShell 7 shell afterward.

Choose the latest release below or [install a specific version](#install-a-specific-version). Do not execute installers from a mutable `master` URL.

Then use `olympus version` and `olympus update` from any directory. The public [Fast Uninstall](../README.md#fast-uninstall) entrypoint and `olympus uninstall` remove only managed resources and Olympus's PATH entry.

The public PowerShell entrypoints are executable code. They select an immutable stable release and validate the tag/installer identity before use; GitHub's immutability assertion is not independent cryptographic signature verification.

## Requirements and platform limits

- Windows; this is the only currently qualified installer platform. Linux and macOS are not qualified.
- PowerShell 7 (`pwsh`) installed and available on `PATH`. Windows PowerShell 5.1 may start an entrypoint only when PowerShell 7 is also available; 5.1 alone is insufficient.
- Python 3.11+ is used internally by the global CLI; users invoke `olympus`, not `python -m olympus`.
- OpenCode V2. This does not establish runtime discovery for every version.

OpenCode V2 is in **ACTIVE DEVELOPMENT**. Codex adapters and internal project/configuration engines remain for **FROZEN COMPATIBILITY**, not public installation. See [harness capabilities](HARNESS-CAPABILITIES.md) and [Codex compatibility](CODEX-COMPATIBILITY.md).

## Public PowerShell entrypoints

```powershell
& ([scriptblock]::Create((irm 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1')))
olympus uninstall
```

Invoke the downloaded script block with `&` as shown.

Both source entrypoints, `install-olympus.ps1` and `uninstall-olympus.ps1`, are fixed to global OpenCode. Install accepts `-DryRun` or `-Update`; uninstall has no selection arguments. No interactive selection is required.

### Install a specific version

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.8.0/install.ps1')))
```

The tagged `install.ps1` defaults to its embedded version and downloads the exact tag archive, so no extra `-Version` argument is needed. This bypasses `latest` selection. A versioned URL for `install-olympus.ps1` would not pin the installed version: that bootstrap still selects the latest release.

### Removed installation selectors

Project targets and Codex/dual installation are rejected before download or dispatch. CLI install/update/uninstall reject legacy `--scope`, `--harness`, `--target`, and `--version` selectors. The root tagged installer retains fixed `global`/`opencode` defaults and qualification-only source/version overrides, but rejects project/Codex modes.

Ten of the twelve wrappers at `install/{project,global}/{opencode,codex,all}.ps1` and `uninstall/{project,global}/{opencode,codex,all}.ps1` fail clearly without downloading or dispatching. Only the two `global/opencode.ps1` wrappers remain fixed aliases.

### Ownership of the global default agent

An existing `opencode.json` or `opencode.jsonc` remains user-owned. Olympus changes only its root `default_agent`, preserving other bytes, comments, encoding, and preferences. An optional `default_agent_receipt` in the existing installation manifest records actual prior presence/value; it never assumes `consultant`. If the value was already `kael`, an intact manifest-owned Kael agent must prove ownership first.

Uninstall restores another prior value only while the field is still `kael`. It removes a previously absent or already-`kael` field rather than restoring a reference to the deleted agent. Later user choices and deleted configs are preserved. A new minimal config may be wholly manifest-owned; the permissions template itself is unchanged.

The receipt states `pending_set`, `committed`, and `pending_uninstall` are reconciled under the existing writer lock. Resume an interrupted set through install/update or an interrupted uninstall through uninstall; third-value conflicts fail closed. `VerifyOnly` never writes or approves a pending state. These guarantees cover this field lifecycle, not an all-resource transaction. Global defaults do not override project preferences or replace the agent already stored in an existing OpenCode session.

## Release selection, identity, and executable source

The generic entrypoint queries `https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest` metadata only to select a release. It requires `immutable=true`, `draft=false`, `prerelease=false`, a valid stable `tag_name`, and a nonempty, time-zone-aware `published_at` timestamp that is not more than five minutes in the future. The selected tag supplies `scripts/launch-latest.ps1`; that launcher fetches the installer and exact tag archive from the same tag and checks matching version and release markers. Both stages fail closed for missing, malformed, mutable, unpublished, or mismatched sources; there is no mutable-branch or older-launcher fallback.

These checks establish release selection and tag identity, not cryptographic integrity. GitHub's immutability field is a platform assertion; the installer does not independently verify a signature or published SHA-256 for downloaded executable code. Review each downloaded stage separately if your trust policy requires it.

## Advanced: install from a local source checkout

Maintainers may run `install.ps1` directly against a trusted local checkout instead of using the Fast entrypoints. The checkout's declared release identity must match `-Version`; the installer still validates source identity and uses the existing bootstrap and safety checks. This advanced route installs the local checkout's content, not the currently published release.

```powershell
$source = (Resolve-Path '.').Path
pwsh -NoProfile -File (Join-Path $source 'install.ps1') `
    -Version 'v0.8.0' -SourceRoot $source -DryRun
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
to commands that select an effective user configuration: `agents
list`, `config list`, `doctor`, and role aliases. They use a managed OpenCode
project at the current directory when found, otherwise global scope. Supply
`--scope` and, for project scope, `--target` to be explicit. Other commands
below do not inherit that rule.

| Command | Scope and target | Effect |
|---|---|---|
| `olympus update` (`upgrade`) | Fixed global OpenCode; CWD does not select a project | Applies the immutable stable release update; Windows/PowerShell 7 only. There is no preview mode. |
| `olympus install` | Fixed global OpenCode; no scope/harness/target/version selectors | `--dry-run` previews. Otherwise the installer executes; `--execute` makes that intent explicit. `--json` captures native output. |
| `olympus uninstall` | Fixed global OpenCode | `--dry-run` previews; otherwise removes unchanged manifest-owned resources, reverses the still-owned default field, and uninstalls the global CLI/PATH entry. |
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

`olympus config list` shows effective model/effort values, precedence (**project override > global override > canonical defaults**), and absolute paths to each source. Scope-aware commands such as `agents list`, `config list`, and `doctor` select the managed OpenCode project at the current directory when one exists; otherwise they use global scope. Use `--scope project --target <absolute-worktree-root>` or `--scope global` to select explicitly. For example, `olympus doctor --scope project --target 'C:\Users\Ada Lovelace\source\Sample Project'` checks that project. Doctor is read-only: it validates JSON and declared model/effort values and checks managed installation state, but never applies edits or checks provider access. For managed configuration changes, review `olympus config apply ... --dry-run` first, then use `--execute` only for the intended target; global execution is OpenCode-only. `olympus config recover` may change files and is only for reconciling the matching pending operation. See the [command scopes and effects](#command-scopes-and-effects) table before applying or recovering.

Installation is no longer offered per project or for Codex. The retained internal project engines and configuration commands protect compatibility; they do not reopen public installation modes. Existing local overrides are not automatically cleaned.

`--dry-run` may use temporary acquisition/cache locations but does not write global resources. The official engine resolves the global root. The CLI and update are qualified on Windows with PowerShell 7.

## Installation safety

- Execute installers only from trusted official release sources or an explicitly trusted local checkout.
- Installation uses ownership manifests and managed-file hashes; unrelated user files are preserved, and conflicting or drifted managed resources are not silently overwritten.
- Uninstall removes only unchanged, manifest-owned resources. Review any ownership or drift error; do not bypass it.
- `-VerifyOnly` is read-only; it verifies the global OpenCode resources and rejects pending default-agent receipts.
- Static installation does not establish runtime discovery on every runtime/version. Global installation is Windows-qualified only.

## Troubleshooting

- **`OLYMPUS_REQUIRES_POWERSHELL_7`** — install PowerShell 7 and make `pwsh` available on `PATH`.
- **Unknown selector / `PUBLIC_INSTALL_ROUTE_UNSUPPORTED`** — remove legacy project/harness arguments and use the global OpenCode route.
- **`LATEST_RELEASE_MUTABLE`, `LATEST_RELEASE_NOT_PUBLISHED`, or `LATEST_RELEASE_METADATA_*`** — stop. Do not switch to a branch URL or retry through a different installer.
- **`LATEST_RELEASE_IDENTITY_MISMATCH` / `LAUNCHER_BOOTSTRAP_CONTRACT_MISSING`** — stop; downloaded tag contents did not satisfy the expected release contract.
- **Managed-file drift errors** — review user changes. Do not delete or overwrite files to force installation.
- **`GLOBAL_DEFAULT_AGENT_*`** — preserve the config and manifest; use the matching install/uninstall recovery operation. Do not invent a prior default or discard a receipt.
- **Entrypoint URL returns not found** — check the official [Releases page](https://github.com/Edulynch/OpenCode-OlympusAgents/releases); do not substitute a branch URL or older launcher.
