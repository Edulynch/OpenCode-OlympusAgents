#!/usr/bin/env python3
"""Run the bounded local qualification gate before pushing this checkout."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ZERO_OID = re.compile(r"(?:0{40}|0{64})\Z")
OBJECT_OID = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
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
        raise GateError("The pre-push hook supplied an invalid revision.")
    output = git_output(["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"])
    commit = output.decode("ascii", errors="strict").strip()
    if not OBJECT_OID.fullmatch(commit):
        raise GateError("Git did not resolve the supplied revision to a commit.")
    return commit.lower()


def require_clean_tracked_tree() -> None:
    status = git_output(["status", "--porcelain=v1", "-z", "--untracked-files=no"])
    if status:
        raise GateError("Tracked files or the index are dirty in the hook-visible snapshot; push blocked.")


def tracked_paths() -> list[str]:
    return [os.fsdecode(name) for name in git_output(["ls-files", "--cached", "-z"]).split(b"\0") if name]


def validate_remote_ref(ref: str) -> None:
    if not ref or ref.startswith("-") or any(ord(char) <= 32 or ord(char) == 127 for char in ref):
        raise GateError("The pre-push hook supplied an invalid remote ref.")
    try:
        result = subprocess.run(
            ["git", "check-ref-format", "--allow-onelevel", ref],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        raise GateError("Git could not validate the pushed remote ref.") from None
    if result.returncode:
        raise GateError("The pre-push hook supplied an invalid remote ref.")


def parse_push_updates(payload: bytes) -> list[tuple[str, str, str, str]]:
    if not payload:
        return []
    try:
        lines = payload.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError:
        raise GateError("The pre-push hook input is not valid UTF-8.") from None

    updates: list[tuple[str, str, str, str]] = []
    oid_length: int | None = None
    for line in lines:
        fields = line.split(" ")
        if len(fields) != 4 or any(not field for field in fields):
            raise GateError("The pre-push hook supplied a malformed update record.")
        local_ref, local_oid, remote_ref, remote_oid = fields
        if not OBJECT_OID.fullmatch(local_oid) or not OBJECT_OID.fullmatch(remote_oid):
            raise GateError("The pre-push hook supplied an invalid object ID.")
        if len(local_oid) != len(remote_oid) or (oid_length is not None and len(local_oid) != oid_length):
            raise GateError("The pre-push hook supplied inconsistent object ID formats.")
        oid_length = len(local_oid)

        deleting = local_ref == "(delete)"
        if deleting != bool(ZERO_OID.fullmatch(local_oid)):
            raise GateError("The pre-push hook supplied an inconsistent deletion record.")
        if deleting and ZERO_OID.fullmatch(remote_oid):
            raise GateError("The pre-push hook supplied a deletion for a missing remote ref.")
        if not deleting and (
            not local_ref
            or local_ref.startswith("-")
            or any(ord(char) <= 32 or ord(char) == 127 for char in local_ref)
        ):
            raise GateError("The pre-push hook supplied an invalid local ref.")
        validate_remote_ref(remote_ref)
        updates.append((local_ref, local_oid.lower(), remote_ref, remote_oid.lower()))
    return updates


def paths_for_push(from_ref: str | None, to_ref: str | None) -> list[str]:
    if not from_ref and not to_ref:
        resolve_commit("HEAD")
        return tracked_paths()
    if not from_ref or not to_ref:
        raise GateError("The pre-push hook supplied an incomplete revision range.")

    target = resolve_commit(to_ref)
    if target != resolve_commit("HEAD"):
        raise GateError("The pushed revision is not the clean checked-out HEAD.")
    if ZERO_OID.fullmatch(from_ref):
        return tracked_paths()

    base = resolve_commit(from_ref)
    changed = git_output(["diff", "--name-only", "-z", "--no-renames", base, target, "--"])
    return [os.fsdecode(name) for name in changed.split(b"\0") if name]


def paths_for_hook_updates(updates: list[tuple[str, str, str, str]]) -> list[str] | None:
    outgoing = [update for update in updates if update[0] != "(delete)"]
    if not outgoing:
        return None
    if len(outgoing) != 1:
        raise GateError("Push one non-deletion ref at a time; multiple ref updates are unsupported.")
    _, local_oid, _, remote_oid = outgoing[0]
    return paths_for_push(remote_oid, local_oid)


def is_documentation_path(path: str) -> bool:
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if not parts or parts[-1].casefold() == "codex.md":
        return False
    suffix = PurePosixPath(parts[-1]).suffix.casefold()
    if suffix == ".md":
        return len(parts) == 1 or parts[0].casefold() in {"docs", "specs"}
    return suffix in IMAGE_EXTENSIONS and len(parts) > 1 and parts[0].casefold() in {"docs", "specs"}


def run_check(name: str, command: list[str]) -> None:
    child_env = os.environ.copy()
    local_env_names = git_output(["rev-parse", "--local-env-vars"]).decode("ascii").splitlines()
    for variable in local_env_names:
        child_env.pop(variable, None)
    try:
        result = subprocess.run(command, cwd=ROOT, env=child_env, check=False)
    except OSError as error:
        raise GateError(f"{name} prerequisite could not run: {error}") from None
    if result.returncode:
        raise GateError(f"{name} failed (exit {result.returncode}); push blocked.")


def main(argv: list[str] | None = None, *, hook_input: bytes | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local pre-push qualification gate.")
    parser.add_argument(
        "--git-hook",
        action="store_true",
        help="read native Git pre-push update records from stdin",
    )
    args = parser.parse_args(argv)
    try:
        if args.git_hook:
            try:
                payload = sys.stdin.buffer.read() if hook_input is None else hook_input
            except OSError:
                raise GateError("The native pre-push update records could not be read.") from None
            paths = paths_for_hook_updates(parse_push_updates(payload))
            if paths is None:
                print("[pre-push] No content is being pushed; checks skipped.")
                return 0
        else:
            paths = None

        require_clean_tracked_tree()
        if not args.git_hook:
            paths = paths_for_push(None, None)
        if not paths:
            print("[pre-push] No tracked changes to qualify.")
            return 0

        # The docs checker also catches links to deleted code files.
        run_check("Documentation check", [sys.executable, "-B", str(ROOT / "scripts" / "check_docs.py")])
        if any(not is_documentation_path(path) for path in paths):
            pwsh = shutil.which("pwsh")
            if not pwsh:
                raise GateError("PowerShell 7 (pwsh) is required for FAST; push blocked.")
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
