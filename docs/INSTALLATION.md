# Installation and uninstallation

## Requirements and platform limits

- Windows; this is the only currently qualified installer platform. Linux and macOS are not qualified.
- PowerShell 7 (`pwsh`) installed and available on `PATH`. Windows PowerShell 5.1 may start an entrypoint only when PowerShell 7 is also available; 5.1 alone is insufficient.
- Git is required for project-scope installation and uninstallation. Use the root of a trusted Git worktree.
- Install OpenCode V2, Codex CLI, or both according to the selected harness. This does not establish runtime discovery for every version.

OpenCode V2 is in **ACTIVE DEVELOPMENT**. Codex is in **FROZEN COMPATIBILITY**: existing installation and safe-uninstall behavior remain, but no new capability or full parity is implied. Global installation is Windows-qualified. See [harness capabilities](HARNESS-CAPABILITIES.md) and [Codex compatibility](CODEX-COMPATIBILITY.md).

## The two public Fast entrypoints

The public command URLs below start from the versioned `v0.4.12` bootstrap scripts. That version identifies the bootstrap source only; it does **not** preselect the final release installer tag. Each bootstrap consults GitHub's `releases/latest` metadata to select a published release and tag that passes its checks.

```powershell
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.12/install-olympus.ps1 | iex
irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.12/uninstall-olympus.ps1 | iex
```

When run in an interactive terminal with no selection parameters, either entrypoint asks for scope and harness. A valid partial selection asks only for the missing values. For example, `-Global` asks only for a harness, while `-Harness codex` asks only for scope. If all required values are supplied, the command runs without prompting and is suitable for non-interactive use. If a required value is missing and interactive input is unavailable, it exits with `ARGUMENTS_REQUIRED` instead of waiting for input.

### Scope and harness selection

| Scope | Parameters | Target |
|---|---|---|
| Current project | `-Project -Here` | Current directory; must be the Git worktree root |
| Another project | `-ProjectPath <path>` | The specified Git worktree root |
| Global | `-Global` | User-level runtime configuration |

`-Harness` accepts `opencode`, `codex`, or `all`; it has no implicit default. Supply `-Project` and `-Here` together. `-ProjectPath`, `-Global`, and the `-Project -Here` pair are mutually exclusive; contradictory choices are rejected. Do not mix those scope selectors. A quoted `-ProjectPath` may contain spaces.

The examples below fetch the public bootstrap text, then invoke it with explicit parameters. Run the `-Project -Here` examples from the project root. The project-path target intentionally contains spaces.

```powershell
$install = [scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.12/install-olympus.ps1'))
$uninstall = [scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.12/uninstall-olympus.ps1'))

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

1. The versioned Fast command first runs its `v0.4.12` bootstrap source. The bootstrap requests `https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest` and validates the returned release metadata: `immutable=true`, `draft=false`, `prerelease=false`, a valid Olympus tag, and a published timestamp. The returned `tag_name` selects the tag used to download that release's `scripts/launch-latest.ps1`.
2. That release launcher also requests `releases/latest` and validates the response. Its returned tag selects the `install.ps1` download and the exact tag archive subsequently requested by the installer. The selected installer must identify itself with matching version and release markers, and the archive/source identity is checked before installation proceeds. A missing, malformed, mutable, unpublished, or mismatched source fails closed; there is no mutable-branch or older-launcher fallback.
3. These checks distinguish release selection and tag identity from cryptographic integrity. GitHub's `immutable` field is a platform assertion; the installer does not independently verify a signature or a published SHA-256 for the downloaded executable code. The bootstrap and later downloaded scripts are executable code, not merely release metadata.

The following is the **remote published-release flow**: it downloads the versioned bootstrap into a new, uniquely named temporary directory for inspection. Do not save it in a checkout or another directory that might contain a neighboring launcher. The bootstrap can use a sibling `scripts/launch-latest.ps1` if one exists; these checks ensure the inspection directory contains only the downloaded entrypoint. The .NET `CreateNew` mode below fails rather than replacing an existing file.

Run both PowerShell 7 blocks in the same session. The first downloads and displays the entrypoint without executing it; the second is an explicitly separate execution step.

```powershell
$uri = 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.12/install-olympus.ps1'
$inspectionDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ('olympus-bootstrap-inspection-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $inspectionDirectory) {
    throw 'The generated inspection directory already exists; start again with a new GUID.'
}
$null = [System.IO.Directory]::CreateDirectory($inspectionDirectory)
if (@(Get-ChildItem -LiteralPath $inspectionDirectory -Force).Count -ne 0) {
    throw 'The new inspection directory is not empty; stop and use a different directory.'
}

$bootstrapPath = Join-Path $inspectionDirectory 'install-olympus.ps1'
$response = Invoke-WebRequest -Uri $uri -ErrorAction Stop
if ([string]::IsNullOrWhiteSpace($response.Content)) {
    throw 'The downloaded bootstrap is empty; stop and investigate.'
}
$bytes = [System.Text.UTF8Encoding]::new($false).GetBytes([string]$response.Content)
$stream = [System.IO.File]::Open($bootstrapPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try {
    $stream.Write($bytes, 0, $bytes.Length)
}
finally {
    $stream.Dispose()
}

# Inspection only: this displays the downloaded file; it does not execute it.
Get-Content -LiteralPath $bootstrapPath
```

Inspect the displayed content and decide separately whether to execute it. Before execution, verify that the directory still contains exactly that one file; this prevents the bootstrap from selecting a neighboring local launcher. The following command is a separate, deliberate execution step, with an example project path that contains spaces:

```powershell
$inspectionItems = @(Get-ChildItem -LiteralPath $inspectionDirectory -Force)
if ($inspectionItems.Count -ne 1 -or $inspectionItems[0].FullName -ne $bootstrapPath -or $inspectionItems[0].PSIsContainer) {
    throw 'The inspection directory contains an unexpected neighboring item; do not execute the bootstrap.'
}
pwsh -NoProfile -File $bootstrapPath -ProjectPath 'C:\Users\Ada Lovelace\source\Sample Project' -Harness opencode
```

The versioned bootstrap uses GitHub `releases/latest` metadata to select the tag; it then downloads later tag-selected code. Inspecting the entrypoint does **not** inspect or cryptographically verify the launcher, installer, or archive that may subsequently be downloaded and executed. Review each stage separately if required by your trust policy. The `immutable` metadata check is not an independent signature or SHA-256 verification. Do not substitute `main`, `master`, or another mutable branch URL.

This remote published-release flow is distinct from deliberately installing from a trusted local checkout, described below. The local-checkout route installs that checkout's content rather than selecting the current published release.

## Advanced: install from a local source checkout

Maintainers may run `install.ps1` directly against a trusted local checkout instead of using the Fast entrypoints. The checkout's declared release identity must match `-Version`; the installer still validates source identity and uses the existing bootstrap and safety checks. This advanced route installs the local checkout's content, not the currently published release.

```powershell
$source = (Resolve-Path '.').Path
$target = 'C:\Users\Ada Lovelace\source\Sample Project'
pwsh -NoProfile -File (Join-Path $source 'install.ps1') `
    -Version 'v0.4.12' -SourceRoot $source -Target $target -Scope project -Harness opencode
```

Use the version actually declared by the checkout; do not copy the example version blindly. Local-source installation is for advanced, trusted-checkout use and is not evidence that the corresponding release is published or immutable.

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
