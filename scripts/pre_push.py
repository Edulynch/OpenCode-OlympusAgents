#!/usr/bin/env python3
"""Run the bounded local qualification gate before pushing this checkout."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ZERO_OID = re.compile(r"(?:0{40}|0{64})\Z")
IMAGE_EXTENSIONS = {".avif", ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp"}


class GateError(RuntimeError):
    """A prerequisite or check failed, so the push must stop."""


def git_output(args: list[str]) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as error:
        raise GateError(f"Git could not run: {error}") from None
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GateError(f"Git command failed ({result.returncode}): {detail or 'no diagnostic'}")
    return result.stdout


def resolve_commit(ref: str) -> str:
    if not ref or ref.startswith("-") or any(ord(char) <= 32 or ord(char) == 127 for char in ref):
        raise GateError("The pre-push manager supplied an invalid revision.")
    output = git_output(["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"])
    commit = output.decode("ascii", errors="strict").strip()
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", commit):
        raise GateError("Git did not resolve the supplied revision to a commit.")
    return commit.lower()


def require_clean_tracked_tree() -> None:
    status = git_output(["status", "--porcelain=v1", "-z", "--untracked-files=no"])
    if status:
        raise GateError("Tracked files or the index are dirty in the hook-visible snapshot; push blocked.")


def tracked_paths() -> list[str]:
    return [os.fsdecode(name) for name in git_output(["ls-files", "--cached", "-z"]).split(b"\0") if name]


def paths_for_push(
    from_ref: str | None,
    to_ref: str | None,
    local_branch: str | None = None,
) -> list[str]:
    if not from_ref and not to_ref:
        head = resolve_commit("HEAD")
        if local_branch and resolve_commit(local_branch) != head:
            raise GateError("The pre-push manager's local branch does not resolve to checked-out HEAD.")
        return tracked_paths()
    if not from_ref or not to_ref:
        raise GateError("The pre-push manager supplied an incomplete revision range.")

    target = resolve_commit(to_ref)
    if target != resolve_commit("HEAD"):
        raise GateError("The pushed revision is not the clean checked-out HEAD.")
    if ZERO_OID.fullmatch(from_ref):
        return tracked_paths()

    base = resolve_commit(from_ref)
    changed = git_output(["diff", "--name-only", "-z", "--no-renames", base, target, "--"])
    return [os.fsdecode(name) for name in changed.split(b"\0") if name]


def is_documentation_path(path: str) -> bool:
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if not parts or parts[-1].casefold() == "codex.md":
        return False
    suffix = PurePosixPath(parts[-1]).suffix.casefold()
    if suffix == ".md":
        return len(parts) == 1 or parts[0].casefold() in {"docs", "specs"}
    return suffix in IMAGE_EXTENSIONS and len(parts) > 1 and parts[0].casefold() in {"docs", "specs"}


def run_check(name: str, command: list[str]) -> None:
    try:
        result = subprocess.run(command, cwd=ROOT, check=False)
    except OSError as error:
        raise GateError(f"{name} prerequisite could not run: {error}") from None
    if result.returncode:
        raise GateError(f"{name} failed (exit {result.returncode}); push blocked.")


def main() -> int:
    try:
        require_clean_tracked_tree()
        from_ref = os.environ.get("PRE_COMMIT_FROM_REF") or None
        to_ref = os.environ.get("PRE_COMMIT_TO_REF") or None
        local_branch = os.environ.get("PRE_COMMIT_LOCAL_BRANCH") or None
        paths = paths_for_push(from_ref, to_ref, local_branch)
        if not paths:
            print("[pre-push] No tracked changes to qualify.")
            return 0

        # The docs checker also catches links to deleted code files.
        run_check("Documentation check", [sys.executable, "-B", str(ROOT / "scripts" / "check_docs.py")])
        if any(not is_documentation_path(path) for path in paths):
            pwsh = shutil.which("pwsh")
            if not pwsh:
                raise GateError("PowerShell 7 (pwsh) is required for FAST; push blocked.")
            # shortcut: pre-commit exposes one push ref range; upgrade only if multi-ref coverage is required.
            run_check("FAST", [pwsh, "-NoProfile", "-File", str(ROOT / "scripts" / "qualify.ps1"), "-Profile", "FAST"])
        else:
            print("[pre-push] Documentation-only change; FAST skipped.")
        print("[pre-push] PASS")
        return 0
    except (GateError, UnicodeError) as error:
        print(f"[pre-push] FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
