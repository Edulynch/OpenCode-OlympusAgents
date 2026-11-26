# Installation and uninstallation

## Start here

Quick guides: [English](../README.md) · [Español](../README.ES.md).

The [Fast Install](../README.md#fast-install) is per-user, global, and OpenCode-only. It has no project/harness selectors or menus, and the current directory never selects the installation target. It installs the `olympus` CLI and exactly `/olympus.ultra`, `/olympus.performance`, and `/olympus.performance-ultra` as global OpenCode commands; bare aliases are not provided.

Choose the latest release below or [install a specific version](#install-a-specific-version). Do not execute installers from a mutable `master` URL.

Then use `olympus version` and `olympus update` from any directory. [Fast Uninstall](../README.md#fast-uninstall) removes managed resources and, on Windows, Olympus's PATH entry.

The public entrypoints are executable code. They select an immutable stable release and validate the tag/installer identity before use; GitHub's immutability assertion is not independent cryptographic signature verification.

## Requirements and platform limits

- **Windows:** PowerShell 7 (`pwsh`) on `PATH`. Windows PowerShell 5.1 alone is insufficient. Tag-archive operations other than uninstall—including install/update, `-DryRun`, and `-VerifyOnly`—also require Python 3.11+ on `PATH` to render and check generated OpenCode resources before target changes; trusted `-SourceRoot` checkout mode is not rendered. The previously published `v0.11.1` release is Windows-only.
- **Linux:** POSIX `sh` and `curl` for the one-line command. The candidate's lifecycle and runtime discovery were validated on Ubuntu 24.04 in WSL 2 with OpenCode V2.3.2. This does not qualify native Linux.
- **macOS:** no CI coverage and not qualified.
- **All supported installs:** OpenCode V2 and Python 3.11+. Runtime discovery on every OpenCode version is not implied.

OpenCode is the only currently supported Olympus runtime. See the [OpenCode capability contract](HARNESS-CAPABILITIES.md).

## Public PowerShell entrypoints

```powershell
& ([scriptblock]::Create((irm 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1')))
olympus uninstall
```

Invoke the downloaded script block with `&` as shown.

Both source entrypoints, `install-olympus.ps1` and `uninstall-olympus.ps1`, are fixed to global OpenCode. Install accepts `-DryRun`, `-Update`, or `-Force`; `-Force` selects update. Uninstall has no selection arguments. No interactive selection is required.

## Linux `sh` entrypoint

The [latest stable release](https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest) includes the Linux entrypoint:

```sh
curl -fsSL https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.sh | sh
```

To preview the install without writing global resources, pass `--dry-run`:

```sh
curl -fsSL https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.sh | sh -s -- --dry-run
```

After installing, run:

```sh
~/.local/bin/olympus doctor --scope global
```

On Linux, the launcher is `~/.local/bin/olympus` and packages live under `$XDG_DATA_HOME/olympus` (default `~/.local/share/olympus`). Use the full launcher path if `~/.local/bin` is not on `PATH`. The installer leaves `PATH` and shell profiles unchanged.

Run `~/.local/bin/olympus uninstall` to remove the active package. If cleanup was interrupted after the launcher was removed, pass `uninstall` to the bootstrap:

```sh
curl -fsSL https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.sh | sh -s -- uninstall
```

### Install a specific version

#### Windows

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/vX.Y.Z/install.ps1')))
```

Replace `vX.Y.Z` with the exact tag of a published stable release. The tagged `install.ps1` defaults to its embedded version and downloads the exact tag archive, so no extra `-Version` argument is needed. This bypasses `latest` selection. A versioned URL for `install-olympus.ps1` would not pin the installed version: that bootstrap still selects the latest release.

#### Linux

Pass the exact tag of a published stable, immutable release that supports installation by tag:

```sh
curl -fsSL https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.sh | sh -s -- vX.Y.Z
```

Replace `vX.Y.Z` with the release tag. Add `--dry-run` after the tag to preview. The bootstrap stops if the tag is unavailable, the selected launcher does not support installation by tag, or a different installation is already present. It never falls back to another release or replaces an existing installation with an older one. Use `olympus update` to upgrade to the latest eligible release.

### Supported route and selector validation

Public installation accepts only the global OpenCode route. Project targets and non-OpenCode installation requests are rejected before download or dispatch. CLI install/update/uninstall reject `--scope`, `--harness`, `--target`, and `--version` selectors. The root tagged installer is fixed to global OpenCode.

### Ownership of the global default agent

An existing `opencode.json` or `opencode.jsonc` remains user-owned. Olympus changes only its root `default_agent`, preserving other bytes, comments, encoding, and preferences. An optional `default_agent_receipt` in the existing installation manifest records actual prior presence/value; it never assumes `consultant`. If the value was already `kael`, an intact manifest-owned Kael agent must prove ownership first.

Uninstall restores another prior value only while the field is still `kael`. It removes a previously absent or already-`kael` field rather than restoring a reference to the deleted agent. Later user choices and deleted configs are preserved. A new minimal config may be wholly manifest-owned; the permissions template itself is unchanged.

The receipt states `pending_set`, `committed`, and `pending_uninstall` are reconciled under the existing writer lock. Resume an interrupted set through install/update or an interrupted uninstall through uninstall; third-value conflicts fail closed. `VerifyOnly` never writes or approves a pending state. These guarantees cover this field lifecycle, not an all-resource transaction. Global defaults do not override project preferences or replace the agent already stored in an existing OpenCode session.

### Current installation formats and project-scoped configuration

Current project manifests use `schema_version=1`, explicit `scope=project`,
`installed_harnesses=["opencode"]`, nonempty `installed_version` and
`installed_from_commit`, and the current 13-path managed inventory with hashes.
Global manifests use `schema_version=1`, `scope=global`, exactly OpenCode,
`installed_version=local` or a release tag, a nonempty `installed_from_commit`,
and a valid `default_agent_receipt`. When the existing global config is
user-owned, 14 base resources (nine agents, three commands, and two Activity
files) are managed and the config remains unowned; if
Olympus creates the config, 15 resources are managed. Both are valid current
formats. All three namespaced command files are global-only and are not added
to project manifests or project config apply.

Older role/command inventories, unsupported legacy manifests, and receipt-less
global manifests are rejected rather than migrated or adopted. `--force` does
not bypass those checks. `olympus doctor` is read-only: use it to inspect the
reported state, not to migrate or repair it. For an unsupported older
installation, use the Olympus version that created it to uninstall, then
install the current version; never manually delete files or receipts. For a
global installation, rerun the current public entrypoint from [Fast Install](../README.md#fast-install)
after the old version's uninstall completes. For an older project-managed
configuration, follow that creator version's project uninstall procedure, then
use only the current supported project-configuration flow. If the creator
version or its supported uninstall route cannot be established, stop and seek
maintainer guidance rather than forcing or deleting resources.

New command destinations that already exist without current manifest ownership
are collisions, even when their bytes match Olympus output; the installer will
not adopt or overwrite them.

### Safe transition from an unsupported installation

1. Run the read-only diagnostic for the exact target: `olympus doctor --scope
   global`, or `olympus doctor --scope project --target
   <absolute-worktree-root>`. Doctor reports state; it does not migrate files.
2. Identify the Olympus version that created the installation and use that
   version's supported uninstall procedure. Do not use the current `--force`
   option to cross an unsupported manifest or receipt.
3. After the old installation is removed through its matching procedure, install
   the current release using the supported global entrypoint above. For project
   configuration, use the current supported project workflow; `config apply`
   does not install, adopt, or migrate an absent/legacy manifest.
4. Verify with `olympus version` and the appropriate read-only `olympus doctor`
   command. Do not manually delete managed files, manifests, or receipts.

The updater preserves your explicit model and effort overrides and global
concurrency preference. Use the updater, not `config apply`, to install the
three global commands. Verify them in a new OpenCode session.

Overrides use `schema_version=1` with an `overrides` map; a missing file means
empty, and precedence is project override, global override, then Core defaults.
These project-scoped CLI operations do not install project resources.

Global model and effort setters resolve the safe OpenCode root and coordinate
with the installer and Python writers through the shared
`.olympus-cli-edit.lock`. They refuse to read or update override/managed data
while `.olympus-cli-config-apply`, `.olympus-cli-edit`, or
`olympus/opencode-guard-pending.json` indicates pending recovery; setters do not
recover or remove these controls. If the root cannot be resolved safely, the
setter leaves the override and managed resources unchanged. If the safe root is
known but absent, Olympus creates only its directory hierarchy and stable lock;
without a managed manifest, the setter writes only the requested user override
configuration.

When a setter must update both preferences and a managed agent/manifest, it
records exact recovery evidence under the same writer lock. If the process is
interrupted, use the matching `olympus config recover` command before retrying.
The atomic preference replacement is the commit point: if preferences still
match their old bytes (or remain absent), recovery restores only transaction-owned
managed files; if they match the exact new bytes, recovery keeps the committed
preferences and managed outputs and only cleans the journal. Recovery never
rewrites or removes preferences. Changed preference bytes, managed files, paths,
or modes leave the evidence untouched for inspection. Keep the recorded global
`OLYMPUS_CONFIG_FILE` selection in place until recovery finishes. Preference-only
or single-file updates continue to use one atomic replacement without a journal.
This covers process interruption, not power loss or hardware durability.

An incomplete or unsupported format is rejected without automatic conversion,
adoption, or deletion. A complete current-format installation remains valid
regardless of which release created it. If an older unsupported installation
needs removal, use the release that owns it.

## Release selection, identity, and executable source

The generic entrypoint queries `https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest` metadata only to select a release. It requires `immutable=true`, `draft=false`, `prerelease=false`, a valid stable `tag_name`, and a nonempty, time-zone-aware `published_at` timestamp that is not more than five minutes in the future. The selected tag supplies `scripts/launch-latest.ps1`; that launcher fetches the installer and exact tag archive from the same tag and checks matching version and release markers. Both stages fail closed for missing, malformed, mutable, unpublished, or mismatched sources; there is no mutable-branch or older-launcher fallback.

These checks establish release selection and tag identity, not cryptographic integrity. GitHub's immutability field is a platform assertion; the installer does not independently verify a signature or published SHA-256 for downloaded executable code. Review each downloaded stage separately if your trust policy requires it.

## Advanced: install from a local source checkout

Maintainers may run `install.ps1` directly against a trusted local checkout instead of using the Fast entrypoints. The checkout's declared release identity must match `-Version`; the installer still validates source identity and uses the existing bootstrap and safety checks. This advanced route installs the local checkout's content, not the currently published release.

```powershell
$source = (Resolve-Path '.').Path
pwsh -NoProfile -File (Join-Path $source 'install.ps1') `
    -Version 'vX.Y.Z' -SourceRoot $source -DryRun
```

Use the version actually declared by the checkout; do not copy the example version blindly. Local-source installation is for advanced, trusted-checkout use and is not evidence that the corresponding release is published or immutable.

## Olympus CLI

The global command works from any directory and uses one product version. Python is an internal runtime dependency; users do not need a checkout or `python -m olympus`.

```powershell
olympus --help
olympus version
olympus update
olympus update --help
olympus agents list
olympus nox set-model openai/gpt-6-luna
olympus nox set-effort high
olympus config list
olympus config set-max-parallel 2
olympus doctor
olympus install
olympus uninstall
```

Start with `olympus --help` or open help for a specific action, such as
`olympus config apply --help`. Human output shows the result, affected scope,
and any next step. Use `--verbose` for technical details or `--json` where
supported for automation. `--verbose` does not alter a JSON payload or exit
status. Native warnings and interactive update confirmations stay visible.

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
| `olympus version` (`--version`) | The release selected by the CLI, or by `--source` if supplied | Prints one version line. Does not verify the OpenCode installation. |
| `olympus update` (`upgrade`) | Fixed global OpenCode; CWD does not select a project | Installs a newer immutable stable release. When both installed versions match the latest, it reports that Olympus is up to date without downloading the release archive or running the installer. `--force` (Windows/Linux only) requests a full reinstall of manifest-proven managed files; drift replacement is limited to those paths. No backup, unknown-file cleanup, adoption, or downgrade. There is no preview mode. |
| `olympus install` | Fixed global OpenCode; no scope/harness/target/version selectors | `--dry-run` previews. Otherwise the installer executes; `--execute` makes that intent explicit. `--json` captures native output. |
| `olympus uninstall` | Fixed global OpenCode | `--dry-run` previews; otherwise removes unchanged manifest-owned resources, reverses the still-owned default field, and removes the active CLI. PATH entry cleanup applies only to Windows. |
| `olympus <role> set-model <id>` / `set-effort <value>` | Current role IDs: `kael`, `atlas`, `veyra`, `kovan`, `nox`, `vera`, `helios`, `talos`, and `thales`; auto-detects or accepts scope/target | Writes the user override immediately and updates a managed installed OpenCode agent when applicable. Global setters require a safely resolved root and honor the shared lock and pending-recovery controls above. This is not a canonical source edit and has no dry-run flag. |
| `olympus config set-max-parallel N` | Global user configuration; `N` is an integer from 1 to 8 | Updates the shared prompt-level ceiling for Kael and Atlas and their managed global prompts when installed. Default is 4. It does not control the native scheduler, combine separate root sessions into one quota, cancel active children, or update existing project installations implicitly. |
| `olympus models list`, `olympus agents list` | Canonical source for models; agents list uses auto-detection or explicit scope/target | Read-only lists. `models list` is offline; `agents list` shows effective values and their sources. |
| `olympus models set-family <family> --opencode <id>` / `olympus agents set-model <role> [--family <family>] [--effort <value>]` (at least one option required) | Canonical checkout selected by `--source`, or this CLI's bundled source | Edits canonical model intent. `--dry-run` previews; omitting it executes the source edit. JSON output for these edits requires `--dry-run`. |
| `olympus config list` / `olympus config check` | List uses auto-detection or explicit scope/target; check reads the selected source and OpenCode harness | Both are read-only. List shows effective values, precedence, and paths; check compares renderer output without writing. |
| `olympus config apply --scope project\|global --harness opencode` | Project requires an absolute existing worktree `--target`; global forbids `--target` | Exactly one of `--dry-run` or `--execute` is required. Preview does not write target resources; execution applies the selected managed OpenCode configuration. |
| `olympus config recover` | No scope recovers a pending canonical source edit; project recovery requires `--scope project --target`; global recovery uses `--scope global --harness opencode` | Explicitly reconciles pending source edits, config applies, or coordinated user-settings updates and may change files. Use only for the matching pending operation. |
| `olympus status` | Defaults to project and requires `--target`; use `--scope global` without a target for global metadata | Read-only reported manifest/install metadata; it does not verify file integrity. |
| `olympus doctor` | Auto-detects or accepts explicit scope/target; project scope requires `--target`; `--harness opencode` is the supported harness | Read-only configuration and managed-installation diagnostics. It does not apply repairs or check provider access. |
| `olympus completion powershell` / `olympus completion bash` | Current shell only: PowerShell 7 on Windows or Bash on Linux | Prints optional native registration code. Load it explicitly in the current shell; completion uses local CLI commands/options/choices only and does not inspect files, providers, networks, or configuration. No profile is edited. |

For a project copy, first preview `olympus config apply --scope project --target <absolute-worktree-root> --harness opencode --dry-run`, then execute only when the proposed change is intended. Project `config list` labels the concurrency ceiling as `GLOBAL`. Project apply uses the shared global prompt-ceiling preference when rendering Kael and Atlas; changing that preference alone does not rewrite existing project agents or sessions, so explicitly apply the intended project update. Project apply excludes the three global-only command files and does not duplicate them.

To enable completion only in the current shell:

```powershell
olympus completion powershell | Out-String | Invoke-Expression
```

```bash
eval "$(olympus completion bash)"
```

PowerShell registration is for Windows PowerShell 7; Bash registration is for Linux Bash. To persist it, review and copy the emitted registration into a user-owned profile yourself (for example `$PROFILE` or `~/.bashrc`). Olympus never creates or edits shell profiles automatically.

`olympus update` does not downgrade a newer installation. If it cannot confirm
that the installed CLI version matches the global OpenCode version, it stops
and suggests a next step instead of reinstalling. Use `olympus doctor --scope
global` to investigate; an up-to-date message is not an integrity check.

On Windows and Linux, `olympus update --force` explicitly requests a full
reinstall of the manifest-proven managed files. It may replace drifted content
only on paths whose ownership is verified; it does not adopt or overwrite
unowned files, remove unknown files, create backups, or authorize a downgrade.
User-owned/custom configuration, authentication, and permissions remain outside
the force scope. macOS is not supported.

If an older installed CLI does not recognize `--force`, or its CLI/global
version preflight blocks the update, use the official latest-release bootstrap
when its selected release is v0.12.10 or later. The bootstrap performs the
update without invoking the installed CLI parser:

```powershell
& ([scriptblock]::Create((irm 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1'))) -Force
```

```sh
curl -fsSL https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.sh | sh -s -- --force
```

Windows `-Force` implies update; Linux `--force` selects update and is not
combined with an exact-version positional tag or `--dry-run`. These bootstraps
select the latest eligible stable release and do not pin the product version;
use the exact-tag `install.ps1` instructions above when pinning is required.
Earlier bootstrap releases do not recognize these force options.

When a normal update runs, it preserves the override file. If managed agents
have changed, it lists them and asks once: `y` permits the update, while `n`,
Enter, or non-interactive input preserve the changes and stop. `--force` is the
explicit alternative for drift on verified manifest-owned files; it does not
create a backup.

`olympus <agent> set-model` accepts a syntactically valid `provider/model-id`. Known models are checked against the bundled [Models.dev](https://models.dev) catalog and their declared effort levels; newer or custom IDs absent from the snapshot are allowed with a compatibility warning. Olympus does not test model access. Values are saved to the per-user Olympus configuration shown by `olympus config list`; installed global OpenCode agents consume those values. The catalog is checked in for offline, reproducible validation, so listing and diagnostics do not make a provider request. Olympus never checks API keys, subscriptions, quotas, or model access.

#### Reproducing a Models.dev catalog snapshot

Refresh from a saved raw `https://models.dev/api.json` payload; this recipe
does not make a network or provider request. Preserve the payload bytes as
`models.dev.raw.json` (do not open and re-save it in an editor), set the date
the payload was captured, then run this PowerShell-compatible Python recipe.
It derives provider/model IDs from the API mapping, retains the declared
reasoning/tool-call booleans, and records only explicitly listed `effort`
values; it does not infer defaults. Duplicate or malformed data fails before
the catalog is written. Snapshot lookup keys preserve Models.dev's upstream
spelling, including nested or special-character IDs; they are not CLI
assignment syntax. Empty IDs and control characters remain invalid.

```powershell
$raw = (Resolve-Path '.\models.dev.raw.json').Path
$catalog = 'olympus/core/models-dev.json'
$snapshotDate = '2026-11-17' # Set to the saved payload's capture date.
@'
import hashlib
import json
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
    assert not any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in provider_id)
    provider_models = provider.get("models")
    assert isinstance(provider_models, dict)
    for model_key, model in sorted(provider_models.items()):
        assert isinstance(model_key, str) and model_key and isinstance(model, dict)
        assert not any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in model_key)
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

Public installation, update, and uninstall remain global/OpenCode-only. This does not remove project-scoped configuration: model overrides, `config list`/`check`/`apply`, matching `config recover`, `status`, and read-only `doctor` remain separate CLI operations for OpenCode. They do not install missing resources or turn project configuration into project installation. Existing local overrides are not automatically cleaned.

`--dry-run` may use temporary acquisition/cache locations but does not write global resources. The official engine resolves the global root; the current project is not the installation target.

## Installation safety

- Execute installers only from trusted official release sources or an explicitly trusted local checkout.
- Installation uses ownership manifests and managed-file hashes; unrelated user files are preserved, and conflicting or drifted managed resources are not silently overwritten.
- Uninstall removes only unchanged, manifest-owned resources. Review any ownership or drift error; do not bypass it.
- Windows `-VerifyOnly` and `olympus doctor --scope global` are read-only; they check global OpenCode resources without approving pending default-agent receipts.
- Static installation does not establish runtime discovery on every OpenCode version. See the [platform limits](#requirements-and-platform-limits).

## Troubleshooting

- **`OLYMPUS_REQUIRES_POWERSHELL_7`** — install PowerShell 7 and make `pwsh` available on `PATH`.
- **Unknown selector / `PUBLIC_INSTALL_ROUTE_UNSUPPORTED`** — remove legacy selectors from install/update/uninstall and use the global OpenCode route.
- **`LATEST_RELEASE_MUTABLE`, `LATEST_RELEASE_NOT_PUBLISHED`, or `LATEST_RELEASE_METADATA_*`** — stop. Do not switch to a branch URL or retry through a different installer.
- **`LATEST_RELEASE_IDENTITY_MISMATCH` / `LAUNCHER_BOOTSTRAP_CONTRACT_MISSING`** — stop; downloaded tag contents did not satisfy the expected release contract.
- **Managed-file drift errors** — review user changes. Do not delete or overwrite files to force installation.
- **`GLOBAL_DEFAULT_AGENT_*`** — preserve the config and manifest; use the matching install/uninstall recovery operation. Do not invent a prior default or discard a receipt.
- **Entrypoint URL returns not found** — check the official [Releases page](https://github.com/Edulynch/OpenCode-OlympusAgents/releases); do not substitute a branch URL or older launcher.
