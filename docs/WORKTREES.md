# OpenCode Git worktrees with Olympus

Olympus is installed separately in each project checkout. A new Git worktree does **not** inherit untracked Olympus files from the base checkout.

| | Requirement |
|---|---|
| Harness | OpenCode V2, project-installed Olympus |
| System | Windows, Git, PowerShell 7 |
| Source | A trusted checkout with a valid Olympus project manifest |
| Target | Another linked worktree of the **same** Git repository |
| Setup | Explicit opt-in; not a global agent installation |

## 1. Install in the base checkout

Run the [OpenCode project installer](../README.md#project-install-recommended) and confirm it completed successfully.

## 2. Enable automatic setup for new worktrees

In **OpenCode → Settings → Projects → Startup command**, set:

```text
pwsh -NoProfile -File "%OPENCODE_WORKTREE_BASE%\.opencode\scripts\worktree-setup.ps1"
```

If the project already has a startup command, **preserve it** and integrate the helper deliberately. Do not overwrite an existing command.

OpenCode V2 supplies the two environment variables and waits for `Project.Commands.start` before finishing native worktree creation. The setup also applies to the native project worktree path under `--standalone`.

## 3. Set up an existing or manually created worktree

Use the paths of your own two linked checkouts:

```powershell
$env:OPENCODE_WORKTREE_BASE = "D:\path\to\base-checkout"
$env:OPENCODE_WORKTREE_PATH = "D:\path\to\linked-worktree"

pwsh -NoProfile -File "$env:OPENCODE_WORKTREE_BASE\.opencode\scripts\worktree-setup.ps1"
```

The worktree must already exist and belong to the same Git repository.

## What the helper does

| Behavior | Guarantee |
|---|---|
| Copies | Only exact Olympus-managed paths listed in the verified source manifest |
| Checks | SHA-256 hashes, repository identity, source/destination containment |
| Ownership | Writes a separate project manifest into each linked worktree |
| Re-running | Idempotent when the managed installation is unchanged |
| Conflicts | Refuses unowned, tracked, modified, or conflicting destinations |
| Side effects | No remote downloads, Git staging, commits, or history changes |
| Scope | Project-local; does not rely on OpenCode global agent discovery |

Saving the startup command is explicit consent for OpenCode to execute the local helper whenever it creates a new linked worktree.

## Troubleshooting

| Symptom | Check |
|---|---|
| Missing environment variables | Both `OPENCODE_WORKTREE_BASE` and `OPENCODE_WORKTREE_PATH` must be set |
| Manifest missing or invalid | Recheck the Olympus project installation in the base checkout |
| Resource/hash conflict | Inspect the reported path; do not force-copy or overwrite user files |
| Different Git repository | The helper only supports linked worktrees sharing the same Git repository |
| Prompt cancels although Kael is present | Capture the native OpenCode session status/error and actual worktree location; do not assume setup caused the cancellation |

The helper addresses missing project-local Olympus resources. It does **not** prove universal runtime behavior or fix every prompt cancellation.

[Back to quick start →](../README.md#-install)
