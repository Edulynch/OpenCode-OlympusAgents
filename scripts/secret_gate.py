#!/usr/bin/env python3
"""Run a quiet, integrity-pinned Gitleaks scan over files and Git history."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


VERSION = "8.30.1"
ASSETS = {
    ("Windows", "AMD64"): ("windows_x64.zip", "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e"),
    ("Windows", "ARM64"): ("windows_arm64.zip", "b95f5e4f5c425cedca7ee203d9afd29597e692c4924a12ed42f970537c72cc0f"),
    ("Linux", "x86_64"): ("linux_x64.tar.gz", "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"),
    ("Linux", "aarch64"): ("linux_arm64.tar.gz", "e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080"),
}
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024


class GateError(Exception):
    """An error safe to summarize without exposing tool output or paths."""


def quiet_run(args: list[str], *, cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise GateError("A required local command failed or timed out.") from None


def _download_asset(asset: str, expected_sha256: str) -> bytes:
    url = f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/gitleaks_{VERSION}_{asset}"
    request = urllib.request.Request(url, headers={"User-Agent": "OlympusAgents-secret-gate"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read(MAX_ARCHIVE_BYTES + 1)
    except Exception:
        raise GateError("Could not download the pinned Gitleaks release from GitHub.") from None
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise GateError("The downloaded Gitleaks archive exceeded the size limit.")
    _verify_sha256(payload, expected_sha256)
    return payload


def _verify_sha256(payload: bytes, expected_sha256: str) -> None:
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise GateError("The downloaded Gitleaks archive failed its pinned SHA-256 check.")


def ensure_binary(destination: Path) -> Path:
    system = platform.system()
    machine = platform.machine()
    key = (system, machine)
    if key not in ASSETS:
        raise GateError("This gate supports Windows and Linux x64/ARM64 only.")
    asset, expected_sha256 = ASSETS[key]
    archive = _download_asset(asset, expected_sha256)
    binary = destination / ("gitleaks.exe" if system == "Windows" else "gitleaks")

    try:
        if asset.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                members = [item for item in package.infolist() if PurePosixPath(item.filename).name == "gitleaks.exe" and not item.is_dir()]
                if len(members) != 1:
                    raise GateError("The verified archive does not contain exactly one Gitleaks executable.")
                binary.write_bytes(package.read(members[0]))
        else:
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
                members = [item for item in package.getmembers() if PurePosixPath(item.name).name == "gitleaks" and item.isfile()]
                if len(members) != 1:
                    raise GateError("The verified archive does not contain exactly one Gitleaks executable.")
                stream = package.extractfile(members[0])
                if stream is None:
                    raise GateError("The verified archive executable could not be read.")
                binary.write_bytes(stream.read())
        if system != "Windows":
            binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except GateError:
        raise
    except (OSError, tarfile.TarError, zipfile.BadZipFile, RuntimeError):
        raise GateError("The verified Gitleaks archive could not be unpacked safely.") from None

    version_check = quiet_run([str(binary), "version"], timeout=30)
    try:
        reported = version_check.stdout.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        reported = ""
    if version_check.returncode != 0 or reported != VERSION:
        raise GateError("The extracted executable does not report the pinned Gitleaks version.")
    return binary


def repository_root(requested: Path | None) -> Path:
    if requested is None:
        result = quiet_run(["git", "rev-parse", "--show-toplevel"])
        if result.returncode != 0:
            raise GateError("Run this gate inside a Git worktree.")
        root_text = result.stdout.decode("utf-8", "strict").strip()
        if not root_text:
            raise GateError("The current Git worktree root could not be determined.")
        return Path(root_text).resolve()
    root = requested.resolve()
    result = quiet_run(["git", "rev-parse", "--show-toplevel"], cwd=root)
    if result.returncode != 0:
        raise GateError("The requested directory is not a Git worktree.")
    try:
        resolved = Path(result.stdout.decode("utf-8", "strict").strip()).resolve()
    except (UnicodeDecodeError, OSError):
        raise GateError("The Git worktree root could not be resolved.") from None
    if resolved != root:
        raise GateError("The requested directory must be the Git worktree root.")
    return root


def current_files(root: Path, staging: Path) -> int:
    try:
        root = root.resolve(strict=True)
    except OSError:
        raise GateError("The Git worktree root could not be resolved.") from None
    result = quiet_run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root)
    if result.returncode != 0:
        raise GateError("Git could not enumerate tracked and non-ignored untracked files.")
    try:
        names = result.stdout.split(b"\0")
        count = 0
        for raw_name in names:
            if not raw_name:
                continue
            relative = Path(os.fsdecode(raw_name))
            if relative.is_absolute() or ".." in relative.parts:
                raise GateError("Git returned a path outside the worktree.")
            source = root / relative
            try:
                parent_root = source.parent.resolve(strict=True)
                parent_root.relative_to(root)
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                raise GateError("A worktree path resolves outside the repository.") from None
            try:
                info = source.lstat()
            except FileNotFoundError:
                continue  # Deleted tracked file.
            if stat.S_ISDIR(info.st_mode):
                continue  # A submodule entry has no local file content to stage.
            target = staging.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if stat.S_ISLNK(info.st_mode):
                # Scan the link text without following a possibly external target.
                target.write_bytes(os.fsencode(os.readlink(source)))
            elif stat.S_ISREG(info.st_mode):
                target.write_bytes(source.read_bytes())
            else:
                continue
            count += 1
        return count
    except GateError:
        raise
    except (OSError, UnicodeError, ValueError):
        raise GateError("A current worktree file could not be staged safely for scanning.") from None


def resolve_base(root: Path, requested: str) -> str:
    if not requested or "\0" in requested:
        raise GateError("The history base reference is invalid.")
    result = quiet_run(["git", "rev-parse", "--verify", "--end-of-options", f"{requested}^{{commit}}"], cwd=root)
    if result.returncode != 0:
        raise GateError("The requested history base does not resolve to a commit.")
    base = result.stdout.decode("ascii", "strict").strip()
    merge_base = quiet_run(["git", "merge-base", base, "HEAD"], cwd=root)
    if merge_base.returncode != 0:
        raise GateError("The history base is not connected to the current HEAD.")
    return base


def scan_files(binary: Path, source: Path, *, cwd: Path, config: Path, ignore_file: Path) -> tuple[int, int]:
    """Return (exit status, finding count) without exposing captured tool output."""
    args = [str(binary), "dir", "--config", str(config), "--gitleaks-ignore-path", str(ignore_file), "--ignore-gitleaks-allow", "--no-banner", "--redact=100", "--report-format", "json", "--report-path", "-", "--log-level", "fatal", str(source)]
    result = quiet_run(args, cwd=cwd)
    return result.returncode, _result_count(result)


def scan_history(binary: Path, *, cwd: Path, config: Path, ignore_file: Path, history: str | None = None, all_history: bool = False) -> tuple[int, int]:
    """Scan the selected Git history range without exposing captured output."""
    log_options = "--all" if all_history else f"{history}..HEAD"
    args = [str(binary), "git", "--config", str(config), "--gitleaks-ignore-path", str(ignore_file), "--ignore-gitleaks-allow", "--no-banner", "--redact=100", "--report-format", "json", "--report-path", "-", "--log-level", "fatal", f"--log-opts={log_options}", str(cwd)]
    result = quiet_run(args, cwd=cwd)
    return result.returncode, _result_count(result)


def _result_count(result: subprocess.CompletedProcess[bytes]) -> int:
    if result.returncode == 0:
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise GateError("Gitleaks returned an unexpected scan result.") from None
            if data:
                raise GateError("Gitleaks returned findings with a success status.")
        return 0
    if result.returncode != 1:
        raise GateError("Gitleaks encountered a scan or configuration error.")
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise GateError("Gitleaks failed without a parseable redacted finding result.") from None
    if not isinstance(data, list) or not data:
        raise GateError("Gitleaks failed without a parseable redacted finding result.")
    return len(data)


def run_gate(root: Path, binary: Path, *, base: str | None = None, all_history: bool = False) -> int:
    history = resolve_base(root, base) if base else None
    with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-") as temporary:
        temporary_root = Path(temporary)
        try:
            if os.name != "nt":
                temporary_root.chmod(0o700)
            staged = temporary_root / "current-files"
            staged.mkdir()
            config = temporary_root / "gitleaks.toml"
            config.write_text('[extend]\nuseDefault = true\n', encoding="utf-8")
            ignore_file = temporary_root / ".gitleaksignore"
            ignore_file.write_text("", encoding="utf-8")
            file_count = current_files(root, staged)
        except OSError:
            raise GateError("Could not prepare a private temporary scan directory.") from None
        status, findings = scan_files(binary, staged, cwd=root, config=config, ignore_file=ignore_file)
        if findings:
            print(f"[gitleaks] FAIL: {findings} finding(s) in current files; output was redacted and discarded.")
            return 1
        if status != 0:
            raise GateError("Gitleaks did not complete the current-files scan.")
        print(f"[gitleaks] PASS: {file_count} tracked or non-ignored untracked file(s) scanned.")
        if history is not None or all_history:
            status, findings = scan_history(binary, cwd=root, config=config, ignore_file=ignore_file, history=history, all_history=all_history)
            if findings:
                print(f"[gitleaks] FAIL: {findings} finding(s) in the requested Git history; output was redacted and discarded.")
                return 1
            if status != 0:
                raise GateError("Gitleaks did not complete the requested Git-history scan.")
            scope = "all reachable history" if all_history else "base-to-HEAD history"
            print(f"[gitleaks] PASS: {scope} scanned.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an integrity-pinned Gitleaks gate without exposing findings.")
    parser.add_argument("--repo", type=Path, help="Git worktree root (defaults to the current worktree).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--base", help="Scan commits reachable from HEAD but not from this commit/ref.")
    group.add_argument("--all-history", action="store_true", help="Scan all refs and commits reachable in this clone.")
    args = parser.parse_args(argv)
    try:
        root = repository_root(args.repo)
        with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-bin-") as temporary:
            binary = ensure_binary(Path(temporary))
            return run_gate(root, binary, base=args.base, all_history=args.all_history)
    except GateError as error:
        print(f"[gitleaks] ERROR: {error}", file=sys.stderr)
        return 2
    except Exception:
        print("[gitleaks] ERROR: unexpected local gate failure; sensitive output was suppressed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
