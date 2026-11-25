"""Linux per-user CLI package coordination for the staged global lifecycle.

Lock order is always the per-user CLI package lock, then the global target
lock acquired internally by :mod:`olympus.global_install`.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import shlex
import stat
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import global_install, global_readonly, source_edit


_RECEIPT = "olympus-cli-package.json"
_CURRENT = "current"
_CLEANUP_RECORD = "uninstall-pending.json"
_PACKAGE_KIND = "olympus_linux_cli"
_CLEANUP_KIND = "olympus_linux_cli_uninstall"
_MAX_FILES = 512
_MAX_FILE_BYTES = 8 * 1024 * 1024
_MAX_PACKAGE_BYTES = 64 * 1024 * 1024
_VERSION = global_install._RELEASE
_COMMIT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_STAGING_NAME = re.compile(r"\.staging-[0-9a-f]{32}\Z")
_PYTHON_INPUTS = (
    "olympus/__init__.py",
    "olympus/__main__.py",
    "olympus/cli.py",
    "olympus/config_apply.py",
    "olympus/config_apply_transaction.py",
    "olympus/doctor.py",
    "olympus/global_apply.py",
    "olympus/global_cli.py",
    "olympus/global_install.py",
    "olympus/global_readonly.py",
    "olympus/install_manifest.py",
    "olympus/install_routing.py",
    "olympus/model_edit.py",
    "olympus/models_catalog.py",
    "olympus/source_edit.py",
    "olympus/system_cli.py",
    "olympus/user_config.py",
)
_STATIC_INPUTS = (
    "olympus/core/models.toml",
    "olympus/core/identities.toml",
    "olympus/core/models-dev.json",
    "olympus/policies/orchestration.toml",
    "olympus/policies/routing.md",
    "olympus/policies/maintenance-context.md",
    "olympus/harnesses/capabilities.toml",
    "olympus/harnesses/opencode/config.jsonc",
    "olympus/harnesses/opencode/activity.ts",
    "olympus/harnesses/opencode/tui.tsx",
    "olympus/harnesses/opencode/worktree-setup.ps1",
    "olympus/harnesses/opencode/global-permissions.jsonc",
    "olympus/harnesses/opencode/commands/olympus.ultra.md",
    "olympus/harnesses/opencode/commands/olympus.performance.md",
    "scripts/render_harnesses.py",
    "scripts/olympus_cli.py",
    "scripts/olympus",
    "scripts/launch-latest.py",
    "install.ps1",
)
_ROLE_NAMES = ("argus", "atlas", "helios", "kael", "kovan", "nox", "orin",
               "talos", "thales", "vera", "veyra")
_ROLE_INPUTS = tuple(f"olympus/roles/{role}.md" for role in _ROLE_NAMES)
_AGENT_METADATA_INPUTS = tuple(
    f"olympus/harnesses/opencode/agent-metadata/{role}.md" for role in _ROLE_NAMES
)
_AGENT_PROMPT_INPUTS = tuple(
    f"olympus/harnesses/opencode/agent-prompts/{role}.md" for role in _ROLE_NAMES
)
_PACKAGE_INPUTS = (
    *_PYTHON_INPUTS,
    *_STATIC_INPUTS,
    *_ROLE_INPUTS,
    *_AGENT_METADATA_INPUTS,
    *_AGENT_PROMPT_INPUTS,
)
_OUTPUT_FIXED = (
    "opencode.jsonc",
    ".opencode/plugins/olympus-activity/activity.ts",
    ".opencode/plugins/olympus-activity/tui.tsx",
    ".opencode/scripts/worktree-setup.ps1",
    ".opencode/commands/olympus.ultra.md",
    ".opencode/commands/olympus.performance.md",
)


class GlobalCliError(RuntimeError):
    """A Linux CLI package transition was rejected or could not be confirmed."""

    def __init__(self, message: str, code: int = 3):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class InstalledIdentity:
    """Read-only local identity for update checks; no release lookup is performed."""

    version: str
    commit: str
    package_root: Path
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class _CleanupRecord:
    version: str
    commit: str
    receipt_sha256: str
    versions_dev: int
    versions_ino: int
    package_dev: int
    package_ino: int


@dataclass(frozen=True, slots=True)
class CliOutcome:
    operation: str
    result: str
    version: str
    commit: str
    package_root: str
    global_root: str
    changed_paths: tuple[str, ...] = ()
    detail: str = ""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _require_linux() -> None:
    if not sys.platform.startswith("linux") or os.name != "posix":
        raise GlobalCliError("The per-user CLI package lifecycle is qualified only on Linux.", 3)


def _identity(version: str, commit: str) -> tuple[str, str]:
    if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
        raise GlobalCliError("CLI package version must be a supported release tag.")
    if not isinstance(commit, str) or _COMMIT.fullmatch(commit) is None:
        raise GlobalCliError("CLI package commit identity must be a non-empty safe token.")
    return version, commit


def _user_paths() -> tuple[Path, Path]:
    home = Path.home()
    configured = os.environ.get("XDG_DATA_HOME")
    base = Path(configured) if configured else home / ".local" / "share"
    if not home.is_absolute() or not base.is_absolute():
        raise GlobalCliError("The user home and XDG data directory must be absolute.")
    data_root, bin_root = base / "olympus", home / ".local" / "bin"
    for path in (data_root, bin_root):
        if any(ord(char) < 32 or ord(char) == 127 for char in str(path)):
            raise GlobalCliError("User package paths may not contain control characters.")
        try:
            global_readonly._root(path)
        except global_readonly.GlobalFault as error:
            raise GlobalCliError(f"Unsafe per-user CLI path: {error}") from error
    return data_root, bin_root


def _overlaps(left: Path, right: Path) -> bool:
    left = left.resolve(strict=False)
    right = right.resolve(strict=False)
    return left == right or left in right.parents or right in left.parents


def _configured_global_root() -> Path:
    try:
        root = global_readonly.resolve_roots(("opencode",))["opencode"]
        return global_readonly._root(root)
    except (global_readonly.GlobalFault, OSError, RuntimeError) as error:
        raise GlobalCliError(f"Cannot safely resolve the global OpenCode target: {error}") from error


def _check_path_separation(source: Path | None, data_root: Path, bin_root: Path,
                           global_root: Path) -> None:
    paths = [("CLI data", data_root), ("CLI bin", bin_root), ("global target", global_root)]
    if source is not None:
        paths.append(("staged source", source))
    for index, (left_name, left) in enumerate(paths):
        for right_name, right in paths[index + 1:]:
            if _overlaps(left, right):
                raise GlobalCliError(f"{left_name} and {right_name} paths overlap; no lifecycle was started.")


def _ensure_directory(path: Path, *, create: bool):
    try:
        return global_readonly._ensure_linux_directory(path, create=create)
    except global_readonly.GlobalFault as error:
        if not create and str(error).startswith("Global configuration root is missing:"):
            return None
        raise GlobalCliError(f"Cannot safely inspect per-user directory {path}: {error}") from error


def _verify_directory(path: Path, identity: tuple[int, int]) -> None:
    try:
        global_readonly._verify_linux_directory(path, identity)
    except global_readonly.GlobalFault as error:
        raise GlobalCliError(f"Per-user directory identity changed: {path}: {error}", 4) from error


def _sync_directory_strict(path: Path, identity: tuple[int, int], lock,
                           lock_identity: tuple[int, int]) -> None:
    try:
        source_edit._lock_identity(lock, lock_identity)
    except source_edit.LockError as error:
        raise GlobalCliError(f"Per-user CLI package lock identity is unconfirmed: {error}", 4) from error
    _verify_directory(path, identity)
    descriptor = -1
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if ((opened.st_dev, opened.st_ino) != identity
                or not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.geteuid()):
            raise GlobalCliError(f"Per-user directory identity changed before durable sync: {path}", 4)
        os.fsync(descriptor)
        synced = os.fstat(descriptor)
        placed = os.lstat(path)
        if ((synced.st_dev, synced.st_ino) != identity
                or not stat.S_ISDIR(synced.st_mode) or synced.st_uid != os.geteuid()
                or (placed.st_dev, placed.st_ino) != identity
                or not stat.S_ISDIR(placed.st_mode) or stat.S_ISLNK(placed.st_mode)):
            raise GlobalCliError(f"Per-user directory identity changed during durable sync: {path}", 4)
        try:
            source_edit._lock_identity(lock, lock_identity)
        except source_edit.LockError as error:
            raise GlobalCliError(
                f"Per-user CLI package lock identity is unconfirmed: {error}", 4,
            ) from error
    except GlobalCliError:
        raise
    except (OSError, NotImplementedError) as error:
        raise GlobalCliError(f"Cannot durably sync per-user directory {path}: {error}", 4) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _safe_read(root: Path, relative: str, *, limit: int = _MAX_FILE_BYTES):
    try:
        raw, metadata = source_edit._safe_read(root, relative)
    except (source_edit.BatchError, OSError) as error:
        raise GlobalCliError(f"Cannot safely read {relative}: {error}") from error
    if len(raw) > limit or metadata.st_uid != os.geteuid() or metadata.st_nlink != 1:
        raise GlobalCliError(f"Owned resource has an unsafe owner, link count, or size: {relative}")
    return raw, metadata


def _signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev, metadata.st_ino, stat.S_IMODE(metadata.st_mode),
        metadata.st_size, metadata.st_mtime_ns, metadata.st_nlink,
    )


def _generated_paths(source: Path, renderer, roles: set[str]) -> dict[str, str]:
    try:
        outputs = renderer.outputs_for(source, "opencode")
    except Exception as error:
        raise GlobalCliError(f"Cannot render the staged OpenCode payload: {error}") from error
    expected = {f".opencode/agents/{role}.md" for role in roles} | set(_OUTPUT_FIXED)
    actual: dict[str, str] = {}
    for path, content in outputs.items():
        try:
            relative = path.relative_to(source).as_posix()
            source_edit._relative_parts(relative)
        except (ValueError, source_edit.BatchError) as error:
            raise GlobalCliError(f"Renderer output escapes its staged source: {path}") from error
        if relative in actual or not isinstance(content, str):
            raise GlobalCliError(f"Renderer produced a duplicate or non-text output: {relative}")
        actual[relative] = content
    if set(actual) != expected or len(actual) != 17:
        raise GlobalCliError("Renderer output inventory differs from the bounded Linux CLI package layout.")
    return actual


def _collect_payload_once(source: Path) -> tuple[dict[str, bytes], dict[str, tuple[int, ...]]]:
    from . import cli

    payload: dict[str, bytes] = {}
    signatures: dict[str, tuple[int, ...]] = {}
    total = 0

    def add(relative: str) -> None:
        nonlocal total
        source_edit._relative_parts(relative)
        if relative in payload:
            raise GlobalCliError(f"Duplicate package input: {relative}")
        raw, metadata = _safe_read(source, relative)
        if metadata.st_dev != source_edit._safe_root_metadata(source).st_dev:
            raise GlobalCliError(f"Cross-filesystem package input is not accepted: {relative}")
        payload[relative] = raw
        signatures[relative] = _signature(metadata)
        total += len(raw)
        if len(payload) > _MAX_FILES or total > _MAX_PACKAGE_BYTES:
            raise GlobalCliError("Staged CLI package exceeds its bounded file or byte inventory.")

    for relative in _PACKAGE_INPUTS:
        add(relative)

    try:
        roles = {Path(item).stem for item in _ROLE_INPUTS}
        renderer = cli.load_renderer(source)
        generated = _generated_paths(source, renderer, roles)
        for relative in generated:
            add(relative)
        source_data, issues = cli.source_query(source, "config check", "opencode")
    except GlobalCliError:
        raise
    except Exception as error:
        raise GlobalCliError(f"Cannot validate the staged renderer inventory: {error}") from error
    if issues or not source_data.get("coherent"):
        raise GlobalCliError("Staged source renderer outputs are missing or drifted.")
    return payload, signatures


def _build_source_payload(source: Path, version: str, commit: str) -> dict[str, bytes]:
    from . import cli

    _identity(version, commit)
    if not isinstance(source, Path) or not source.is_absolute():
        raise GlobalCliError("Staged source must be an absolute directory.")
    try:
        source = source.resolve(strict=True)
        source_edit._safe_root_metadata(source)
        declared = cli.release_version(source)
    except (OSError, RuntimeError, source_edit.BatchError, cli.CLIError) as error:
        raise GlobalCliError(f"Cannot validate staged source identity: {error}") from error
    if declared != version:
        raise GlobalCliError(
            f"Requested package version {version} does not match staged install.ps1 identity {declared}."
        )
    first, first_signatures = _collect_payload_once(source)
    second, second_signatures = _collect_payload_once(source)
    if first != second or first_signatures != second_signatures:
        raise GlobalCliError("Staged source bytes or path identities changed during package validation.")
    launcher = first["scripts/olympus"].replace(b"\r\n", b"\n")
    if b"\r" in launcher:
        raise GlobalCliError("POSIX scripts/olympus contains unsupported bare carriage returns.")
    first["scripts/olympus"] = launcher
    return first


def _validated_source(source: Path, version: str, commit: str) -> tuple[Path, dict[str, bytes], tuple[int, int]]:
    if not isinstance(source, Path) or not source.is_absolute():
        raise GlobalCliError("Staged source must be an absolute directory.")
    try:
        canonical = source.resolve(strict=True)
        before = source_edit._safe_root_metadata(canonical)
        payload = _build_source_payload(canonical, version, commit)
        after = source_edit._safe_root_metadata(canonical)
    except (OSError, RuntimeError, source_edit.BatchError) as error:
        raise GlobalCliError(f"Cannot preserve staged source identity: {error}") from error
    identity = (before.st_dev, before.st_ino)
    if (after.st_dev, after.st_ino) != identity:
        raise GlobalCliError("Staged source root identity changed during validation.", 4)
    return canonical, payload, identity


def _current_bytes(version: str, commit: str, receipt_sha256: str) -> bytes:
    return f"{version}\n{commit}\n{receipt_sha256}\n".encode("ascii")


def _cleanup_record_bytes(record: _CleanupRecord) -> bytes:
    return _canonical({
        "schema_version": 1,
        "kind": _CLEANUP_KIND,
        "version": record.version,
        "commit": record.commit,
        "receipt_sha256": record.receipt_sha256,
        "versions_dev": record.versions_dev,
        "versions_ino": record.versions_ino,
        "package_dev": record.package_dev,
        "package_ino": record.package_ino,
    })


def _read_cleanup_record(data_root: Path) -> _CleanupRecord | None:
    path = data_root / _CLEANUP_RECORD
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise GlobalCliError(f"Cannot inspect pending CLI uninstall evidence: {error}", 4) from error
    if (not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & global_readonly._REPARSE
            or metadata.st_uid != os.geteuid() or metadata.st_nlink != 1
            or metadata.st_size > 2048 or stat.S_IMODE(metadata.st_mode) != 0o600):
        raise GlobalCliError("Pending CLI uninstall evidence has unsafe ownership, links, or mode.", 4)
    try:
        raw, metadata = _safe_read(data_root, _CLEANUP_RECORD, limit=2048)
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (GlobalCliError, UnicodeError, ValueError, TypeError) as error:
        raise GlobalCliError(f"Pending CLI uninstall evidence is invalid: {error}", 4) from error
    fields = {
        "schema_version", "kind", "version", "commit", "receipt_sha256",
        "versions_dev", "versions_ino", "package_dev", "package_ino",
    }
    if (not isinstance(record, dict) or set(record) != fields
            or type(record["schema_version"]) is not int or record["schema_version"] != 1
            or record["kind"] != _CLEANUP_KIND
            or not isinstance(record["version"], str) or _VERSION.fullmatch(record["version"]) is None
            or not isinstance(record["commit"], str) or _COMMIT.fullmatch(record["commit"]) is None
            or not isinstance(record["receipt_sha256"], str) or _HASH.fullmatch(record["receipt_sha256"]) is None
            or any(type(record[key]) is not int or record[key] < 0
                   for key in ("versions_dev", "package_dev"))
            or any(type(record[key]) is not int or record[key] <= 0
                   for key in ("versions_ino", "package_ino"))
            or raw != _cleanup_record_bytes(_CleanupRecord(
                record["version"], record["commit"], record["receipt_sha256"],
                record["versions_dev"], record["versions_ino"],
                record["package_dev"], record["package_ino"],
            ))
            or metadata.st_uid != os.geteuid() or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600):
        raise GlobalCliError("Pending CLI uninstall evidence has an unsupported schema or identity.", 4)
    return _CleanupRecord(
        record["version"], record["commit"], record["receipt_sha256"],
        record["versions_dev"], record["versions_ino"],
        record["package_dev"], record["package_ino"],
    )


def _create_cleanup_record(data_root: Path, identity: InstalledIdentity,
                           lock, lock_identity: tuple[int, int]) -> _CleanupRecord:
    expected_root = data_root / "versions" / identity.version
    if identity.package_root != expected_root:
        raise GlobalCliError("Cannot record cleanup for a non-canonical CLI package path.", 4)
    verified = _validate_package(
        expected_root, version=identity.version, commit=identity.commit,
        receipt_sha256=identity.receipt_sha256,
    )
    if verified != identity:
        raise GlobalCliError("CLI package identity changed before cleanup evidence was recorded.", 4)
    versions_info = _ensure_directory(data_root / "versions", create=False)
    if versions_info is None:
        raise GlobalCliError("Cannot record cleanup without the verified CLI versions directory.", 4)
    versions_root, versions_identity = versions_info
    if expected_root.parent != versions_root:
        raise GlobalCliError("CLI versions directory is not the exact package parent.", 4)
    package_metadata = os.lstat(expected_root)
    if (not stat.S_ISDIR(package_metadata.st_mode) or stat.S_ISLNK(package_metadata.st_mode)
            or package_metadata.st_uid != os.geteuid()
            or package_metadata.st_dev != versions_identity[0]):
        raise GlobalCliError("CLI package root is unsafe before cleanup evidence is recorded.", 4)
    record = _CleanupRecord(
        identity.version, identity.commit, identity.receipt_sha256,
        versions_identity[0], versions_identity[1],
        package_metadata.st_dev, package_metadata.st_ino,
    )
    if _read_cleanup_record(data_root) is not None:
        raise GlobalCliError("A CLI uninstall cleanup record already exists.", 4)
    try:
        source_edit._write_private_file(
            data_root / _CLEANUP_RECORD, data_root, _CLEANUP_RECORD,
            _cleanup_record_bytes(record), 0o600, lock, lock_identity,
        )
        source_edit._sync_directory(data_root)
        saved = _read_cleanup_record(data_root)
    except (source_edit.BatchError, OSError, GlobalCliError) as error:
        raise GlobalCliError(f"Cannot persist exact CLI uninstall evidence: {error}", 4) from error
    if saved != record:
        raise GlobalCliError("Persisted CLI uninstall evidence did not verify.", 4)
    return record


def _parse_current(raw: bytes) -> tuple[str, str, str]:
    try:
        text = raw.decode("ascii")
        lines = text.splitlines()
    except UnicodeError as error:
        raise GlobalCliError("Per-user CLI current marker is not ASCII.") from error
    if (len(lines) != 3 or text != "\n".join(lines) + "\n"
            or _VERSION.fullmatch(lines[0]) is None
            or _COMMIT.fullmatch(lines[1]) is None
            or _HASH.fullmatch(lines[2]) is None):
        raise GlobalCliError("Per-user CLI current marker is malformed.")
    return lines[0], lines[1], lines[2]


def _launcher_bytes(data_root: Path) -> bytes:
    quoted = shlex.quote(str(data_root))
    return (
        "#!/bin/sh\n"
        "set -eu\n"
        f"data_root={quoted}\n"
        "if ! IFS= read -r version < \"$data_root/current\"; then\n"
        "  printf '%s\\n' 'Olympus CLI current package marker is unavailable.' >&2\n"
        "  exit 3\n"
        "fi\n"
        "case \"$version\" in\n"
        "  v[0-9]*.[0-9]*.[0-9]*) ;;\n"
        "  *) printf '%s\\n' 'Olympus CLI package marker is invalid.' >&2; exit 3 ;;\n"
        "esac\n"
        "case \"$version\" in\n"
        "  *[!A-Za-z0-9.-]*) printf '%s\\n' 'Olympus CLI package marker is invalid.' >&2; exit 3 ;;\n"
        "esac\n"
        "exec sh \"$data_root/versions/$version/scripts/olympus\" \"$@\"\n"
    ).encode("utf-8")


def _package_receipt(version: str, commit: str, payload: dict[str, bytes]) -> bytes:
    return _canonical({
        "schema_version": 1,
        "kind": _PACKAGE_KIND,
        "version": version,
        "commit": commit,
        "files": [
            {"path": path, "sha256": _digest(raw)}
            for path, raw in sorted(payload.items())
        ],
    })


def _payload_matches_package(payload: dict[str, bytes], identity: InstalledIdentity) -> bool:
    raw, _ = _safe_read(identity.package_root, _RECEIPT, limit=2_000_000)
    try:
        receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, ValueError, TypeError) as error:
        raise GlobalCliError("Installed CLI package receipt is invalid.") from error
    recorded = {
        item["path"]: item["sha256"]
        for item in receipt.get("files", [])
        if isinstance(item, dict) and set(item) == {"path", "sha256"}
    } if isinstance(receipt, dict) else {}
    return recorded == {path: _digest(raw) for path, raw in payload.items()}


def _scan_package_tree(package_root: Path) -> tuple[dict[str, tuple[bytes, os.stat_result]], dict[str, os.stat_result]]:
    files: dict[str, tuple[bytes, os.stat_result]] = {}
    directories: dict[str, os.stat_result] = {}
    root_metadata = os.lstat(package_root)
    if (not stat.S_ISDIR(root_metadata.st_mode) or stat.S_ISLNK(root_metadata.st_mode)
            or getattr(root_metadata, "st_file_attributes", 0) & global_readonly._REPARSE
            or root_metadata.st_uid != os.geteuid()):
        raise GlobalCliError(f"Unsafe CLI package root: {package_root}")
    device = root_metadata.st_dev

    def visit(directory: Path, relative: str) -> None:
        try:
            metadata = os.lstat(directory)
            if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
                    or metadata.st_dev != device or metadata.st_uid != os.geteuid()):
                raise GlobalCliError(f"Unsafe CLI package directory: {relative or '.'}")
            directories[relative] = metadata
            for entry in sorted(os.scandir(directory), key=lambda item: item.name):
                item = entry.stat(follow_symlinks=False)
                child = f"{relative}/{entry.name}" if relative else entry.name
                if (stat.S_ISLNK(item.st_mode)
                        or getattr(item, "st_file_attributes", 0) & global_readonly._REPARSE
                        or item.st_dev != device or item.st_uid != os.geteuid()):
                    raise GlobalCliError(f"Unsafe linked or foreign CLI package resource: {child}")
                if stat.S_ISDIR(item.st_mode):
                    visit(directory / entry.name, child)
                elif stat.S_ISREG(item.st_mode) and item.st_nlink == 1:
                    raw, stable = _safe_read(package_root, child)
                    files[child] = (raw, stable)
                    if len(files) > _MAX_FILES + 1:
                        raise GlobalCliError("CLI package exceeds its bounded file inventory.")
                else:
                    raise GlobalCliError(f"CLI package resource is not a singly linked regular file: {child}")
        except GlobalCliError:
            raise
        except (OSError, source_edit.BatchError) as error:
            raise GlobalCliError(f"Cannot safely inventory CLI package {relative or '.'}: {error}") from error

    visit(package_root, "")
    return files, directories


def _durability_signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_uid,
        metadata.st_nlink, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns,
    )


def _sync_validated_package_files(
    package_root: Path, files: dict[str, tuple[bytes, os.stat_result]],
    lock, lock_identity: tuple[int, int],
) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    for relative, (_, expected_metadata) in sorted(files.items()):
        descriptor = -1
        try:
            source_edit._lock_identity(lock, lock_identity)
            path, checked = source_edit._checked_path(package_root, relative, kind="file")
            if _durability_signature(checked) != _durability_signature(expected_metadata):
                raise GlobalCliError(f"Reused CLI package file changed before durable sync: {relative}", 4)
            descriptor = os.open(path, flags)
            opened = os.fstat(descriptor)
            if _durability_signature(opened) != _durability_signature(expected_metadata):
                raise GlobalCliError(f"Reused CLI package file changed while opening: {relative}", 4)
            try:
                os.fsync(descriptor)
            except (OSError, NotImplementedError) as error:
                raise GlobalCliError(
                    f"Cannot durably sync reused CLI package file {relative}: {error}", 4,
                ) from error
            synced = os.fstat(descriptor)
            _, placed = source_edit._checked_path(package_root, relative, kind="file")
            if (_durability_signature(synced) != _durability_signature(expected_metadata)
                    or _durability_signature(placed) != _durability_signature(expected_metadata)):
                raise GlobalCliError(f"Reused CLI package file changed during durable sync: {relative}", 4)
            source_edit._lock_identity(lock, lock_identity)
        except GlobalCliError:
            raise
        except (OSError, source_edit.BatchError, source_edit.LockError) as error:
            raise GlobalCliError(
                f"Cannot safely durably sync reused CLI package file {relative}: {error}", 4,
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)


def _sync_validated_package_directories(
    package_root: Path, root_identity: tuple[int, int],
    directories: dict[str, os.stat_result], lock, lock_identity: tuple[int, int],
) -> None:
    root_metadata = directories.get("")
    if (root_metadata is None
            or (root_metadata.st_dev, root_metadata.st_ino) != root_identity):
        raise GlobalCliError("Reused CLI package root changed after validation.", 4)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    for relative, expected_metadata in sorted(
        directories.items(), key=lambda item: (item[0].count("/"), item[0]), reverse=True,
    ):
        descriptor = -1
        try:
            source_edit._lock_identity(lock, lock_identity)
            path = package_root
            if relative:
                path, checked = source_edit._checked_path(
                    package_root, relative, kind="directory",
                )
            else:
                _verify_directory(package_root, root_identity)
                checked = os.lstat(package_root)
            if _durability_signature(checked) != _durability_signature(expected_metadata):
                raise GlobalCliError(
                    f"Reused CLI package directory changed before durable sync: {relative or '.'}", 4,
                )
            descriptor = os.open(path, flags)
            opened = os.fstat(descriptor)
            if _durability_signature(opened) != _durability_signature(expected_metadata):
                raise GlobalCliError(
                    f"Reused CLI package directory changed while opening: {relative or '.'}", 4,
                )
            try:
                os.fsync(descriptor)
            except (OSError, NotImplementedError) as error:
                raise GlobalCliError(
                    f"Cannot durably sync reused CLI package directory {relative or '.'}: {error}", 4,
                ) from error
            synced = os.fstat(descriptor)
            if relative:
                _, placed = source_edit._checked_path(
                    package_root, relative, kind="directory",
                )
            else:
                placed = os.lstat(package_root)
            if (_durability_signature(synced) != _durability_signature(expected_metadata)
                    or _durability_signature(placed) != _durability_signature(expected_metadata)):
                raise GlobalCliError(
                    f"Reused CLI package directory changed during durable sync: {relative or '.'}", 4,
                )
            source_edit._lock_identity(lock, lock_identity)
        except GlobalCliError:
            raise
        except (OSError, source_edit.BatchError, source_edit.LockError) as error:
            raise GlobalCliError(
                f"Cannot safely durably sync reused CLI package directory "
                f"{relative or '.'}: {error}", 4,
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)


def _parse_package_receipt(raw_receipt: bytes, receipt_metadata: os.stat_result, *,
                           version: str | None = None, commit: str | None = None,
                           receipt_sha256: str | None = None) -> tuple[str, str, dict[str, str], str]:
    digest = _digest(raw_receipt)
    if receipt_sha256 is not None and digest != receipt_sha256:
        raise GlobalCliError("CLI package receipt does not match the current marker.")
    try:
        receipt = json.loads(raw_receipt.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, ValueError, TypeError) as error:
        raise GlobalCliError("CLI package receipt is invalid JSON.") from error
    if (not isinstance(receipt, dict)
            or set(receipt) != {"schema_version", "kind", "version", "commit", "files"}
            or type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1
            or receipt["kind"] != _PACKAGE_KIND
            or not isinstance(receipt["version"], str) or _VERSION.fullmatch(receipt["version"]) is None
            or not isinstance(receipt["commit"], str) or _COMMIT.fullmatch(receipt["commit"]) is None
            or raw_receipt != _canonical(receipt)
            or stat.S_IMODE(receipt_metadata.st_mode) != 0o444):
        raise GlobalCliError("CLI package receipt has unsupported ownership or schema.")
    actual_version, actual_commit = receipt["version"], receipt["commit"]
    if ((version is not None and actual_version != version)
            or (commit is not None and actual_commit != commit)):
        raise GlobalCliError("CLI package version or commit does not match the requested identity.")
    entries = receipt["files"]
    if not isinstance(entries, list) or not entries or len(entries) > _MAX_FILES:
        raise GlobalCliError("CLI package receipt has an empty or oversized file inventory.")
    recorded: dict[str, str] = {}
    previous = ""
    for item in entries:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"}
                or not isinstance(item["path"], str) or not isinstance(item["sha256"], str)):
            raise GlobalCliError("CLI package receipt has a malformed file entry.")
        path, file_hash = item["path"], item["sha256"]
        try:
            source_edit._relative_parts(path)
        except source_edit.BatchError as error:
            raise GlobalCliError(f"CLI package receipt contains an unsafe path: {path!r}") from error
        if (path <= previous or path == _RECEIPT or _HASH.fullmatch(file_hash) is None):
            raise GlobalCliError("CLI package receipt paths or hashes are duplicated, unordered, or invalid.")
        previous = path
        recorded[path] = file_hash
    return actual_version, actual_commit, recorded, digest


def _validate_package(package_root: Path, *, version: str | None = None,
                      commit: str | None = None, receipt_sha256: str | None = None,
                      sync_durable: bool = False, lock=None,
                      lock_identity: tuple[int, int] | None = None) -> InstalledIdentity:
    from . import cli

    try:
        _, identity = _ensure_directory(package_root, create=False)
    except (TypeError, ValueError) as error:
        raise GlobalCliError(f"CLI package directory is unavailable: {package_root}") from error
    if identity is None:
        raise GlobalCliError(f"CLI package directory is missing: {package_root}")
    _verify_directory(package_root, identity)
    raw_receipt, receipt_meta = _safe_read(package_root, _RECEIPT, limit=2_000_000)
    actual_version, actual_commit, recorded, digest = _parse_package_receipt(
        raw_receipt, receipt_meta, version=version, commit=commit,
        receipt_sha256=receipt_sha256,
    )

    files, directories = _scan_package_tree(package_root)
    expected_files = set(recorded) | {_RECEIPT}
    if set(files) != expected_files:
        raise GlobalCliError("CLI package contains missing or unenumerated resources.")
    expected_directories = {""}
    for path in expected_files:
        parts = path.split("/")[:-1]
        expected_directories.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    if set(directories) != expected_directories:
        raise GlobalCliError("CLI package contains missing or unenumerated directories.")
    total = 0
    for path, expected_hash in recorded.items():
        raw, metadata = files[path]
        total += len(raw)
        if _digest(raw) != expected_hash or stat.S_IMODE(metadata.st_mode) != 0o444:
            raise GlobalCliError(f"CLI package file hash or mode differs from its receipt: {path}")
    if total > _MAX_PACKAGE_BYTES:
        raise GlobalCliError("CLI package exceeds its bounded byte inventory.")
    for directory, metadata in directories.items():
        if stat.S_IMODE(metadata.st_mode) != 0o555:
            raise GlobalCliError(f"CLI package directory mode differs from its immutable receipt: {directory or '.'}")

    expected_paths = set(_package_input_paths(package_root))
    if expected_paths != set(recorded):
        raise GlobalCliError("CLI package is outside the bounded Olympus source/payload inventory.")
    try:
        declared_version = cli.release_version(package_root)
    except cli.CLIError as error:
        raise GlobalCliError(f"CLI package release provenance is invalid: {error}") from error
    if declared_version != actual_version:
        raise GlobalCliError("CLI package receipt disagrees with its packaged install.ps1 release identity.")
    if sync_durable:
        if lock is None or lock_identity is None:
            raise GlobalCliError("Durable package validation requires the active CLI package lock.", 4)
        _sync_validated_package_files(package_root, files, lock, lock_identity)
        _sync_validated_package_directories(
            package_root, identity, directories, lock, lock_identity,
        )
    return InstalledIdentity(actual_version, actual_commit, package_root, digest)


def _known_package_paths() -> set[str]:
    return (
        set(_PACKAGE_INPUTS) | set(_OUTPUT_FIXED)
        | {f".opencode/agents/{role}.md" for role in _ROLE_NAMES}
    )


def _validate_force_package(package_root: Path, *, version: str | None = None,
                            commit: str | None = None,
                            receipt_sha256: str | None = None) -> InstalledIdentity:
    """Recognize a damaged package only through its intact exact receipt and bounded tree."""
    info = _ensure_directory(package_root, create=False)
    if info is None:
        raise GlobalCliError(f"CLI package directory is missing: {package_root}")
    package_root, identity = info
    _verify_directory(package_root, identity)
    raw_receipt, receipt_meta = _safe_read(package_root, _RECEIPT, limit=2_000_000)
    actual_version, actual_commit, recorded, digest = _parse_package_receipt(
        raw_receipt, receipt_meta, version=version, commit=commit,
        receipt_sha256=receipt_sha256,
    )
    if set(recorded) != _known_package_paths():
        raise GlobalCliError("CLI package receipt differs from the bounded Olympus package inventory.")
    files, directories = _scan_package_tree(package_root)
    expected_files = set(recorded) | {_RECEIPT}
    expected_directories = {""}
    for path in expected_files:
        parts = path.split("/")[:-1]
        expected_directories.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    if not set(files) <= expected_files or not set(directories) <= expected_directories:
        raise GlobalCliError("CLI package contains unenumerated resources.")
    if sum(len(raw) for raw, _ in files.values()) > _MAX_PACKAGE_BYTES:
        raise GlobalCliError("CLI package exceeds its bounded byte inventory.")
    return InstalledIdentity(actual_version, actual_commit, package_root, digest)


def _preflight_force_package_repair(package_root: Path, payload: dict[str, bytes], *,
                                    version: str, commit: str,
                                    receipt_sha256: str) -> bool:
    identity = _validate_force_package(
        package_root, version=version, commit=commit, receipt_sha256=receipt_sha256,
    )
    if not _payload_matches_package(payload, identity):
        raise GlobalCliError("Installed CLI package receipt differs from the verified source payload.")
    files, directories = _scan_package_tree(package_root)
    expected_files = set(payload) | {_RECEIPT}
    expected_directories = {""}
    for relative in expected_files:
        parts = relative.split("/")[:-1]
        expected_directories.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    if not set(files) <= expected_files or not set(directories) <= expected_directories:
        raise GlobalCliError("CLI package contains unenumerated resources.")
    changed = tuple(
        relative for relative, desired in sorted(payload.items())
        if relative not in files
        or files[relative][0] != desired
        or stat.S_IMODE(files[relative][1].st_mode) != 0o444
    )
    needs_repair = (
        bool(changed) or set(directories) != expected_directories
        or any(stat.S_IMODE(item.st_mode) != 0o555 for item in directories.values())
    )
    if not needs_repair or not sys.platform.startswith("linux"):
        return needs_repair

    versions_info = _ensure_directory(package_root.parent, create=False)
    if versions_info is None or package_root != versions_info[0] / version:
        raise GlobalCliError("CLI package repair target is not its exact version directory.")
    versions_root, versions_identity = versions_info
    global_install._require_no_posix_acl(
        versions_root, "default", expected_identity=versions_identity,
    )
    for relative in changed:
        old = files.get(relative)
        if old is not None:
            global_install._require_no_posix_acl(
                package_root / relative, "access",
                expected_identity=(old[1].st_dev, old[1].st_ino),
            )
    # Repair changes directory modes as a set; inspect every affected directory first.
    for relative, metadata in directories.items():
        global_install._require_no_posix_acl(
            package_root / relative, "access",
            expected_identity=(metadata.st_dev, metadata.st_ino),
        )
    for relative in sorted(expected_directories - set(directories)):
        current = package_root
        parent_relative = ""
        for part in relative.split("/"):
            child = current / part
            try:
                child_metadata = os.lstat(child)
            except FileNotFoundError:
                parent_metadata = directories.get(parent_relative)
                if parent_metadata is None:
                    raise GlobalCliError("CLI package repair parent changed during ACL preflight.", 4)
                global_install._require_no_posix_acl(
                    current, "default",
                    expected_identity=(parent_metadata.st_dev, parent_metadata.st_ino),
                )
                break
            if not stat.S_ISDIR(child_metadata.st_mode) or stat.S_ISLNK(child_metadata.st_mode):
                raise GlobalCliError(f"Unsafe CLI package repair parent: {child}", 4)
            current = child
            parent_relative = f"{parent_relative}/{part}".strip("/")
    return True


def _package_input_paths(source: Path) -> list[str]:
    """Recompute only the fixed package layout; never adopt arbitrary files."""
    from . import cli

    try:
        roles = {Path(item).stem for item in _ROLE_INPUTS}
        generated = _generated_paths(source, cli.load_renderer(source), roles)
    except GlobalCliError:
        raise
    except Exception as error:
        raise GlobalCliError(f"Cannot validate packaged renderer inventory: {error}") from error
    paths = set(_PACKAGE_INPUTS) | set(generated)
    return sorted(paths)


def _stage_package(data_root: Path, source_payload: dict[str, bytes],
                   version: str, commit: str, data_identity: tuple[int, int],
                   lock, lock_identity: tuple[int, int], *,
                   force: bool = False) -> Path:
    relative_stage = f"versions/.staging-{uuid.uuid4().hex}"
    stage = data_root / relative_stage
    try:
        versions_identity = None
        if force:
            versions_info = _ensure_directory(data_root / "versions", create=False)
            if versions_info is None:
                raise GlobalCliError("Versioned CLI package directory is missing.")
            versions_root, versions_identity = versions_info
            global_install._require_no_posix_acl(
                versions_root, "default", expected_identity=versions_identity,
            )
            _verify_directory(versions_root, versions_identity)
        source_edit._make_directory(stage, data_root, lock, lock_identity)
        metadata = os.lstat(stage)
        staged_identities = {relative_stage: (metadata.st_dev, metadata.st_ino)}
        if force:
            global_install._require_no_posix_acl(
                stage, "access", expected_identity=staged_identities[relative_stage],
            )
            global_install._require_no_posix_acl(
                stage, "default", expected_identity=staged_identities[relative_stage],
            )
        directories = {relative_stage}
        for relative in sorted(source_payload):
            package_relative = f"{relative_stage}/{relative}"
            parent = Path(package_relative).parent.as_posix()
            parents = []
            cursor = Path(parent)
            while cursor.as_posix() != relative_stage:
                parents.append(cursor.as_posix())
                cursor = cursor.parent
            for item in reversed(parents):
                directory = data_root / item
                try:
                    os.lstat(directory)
                except FileNotFoundError:
                    if force:
                        parent_relative = Path(item).parent.as_posix()
                        parent_identity = (
                            versions_identity if parent_relative == "versions"
                            else staged_identities.get(parent_relative)
                        )
                        if parent_identity is None:
                            raise GlobalCliError("CLI package staging parent identity is unavailable.", 4)
                        global_install._require_no_posix_acl(
                            directory.parent, "default",
                            expected_identity=parent_identity,
                        )
                    source_edit._make_directory(directory, data_root, lock, lock_identity)
                    metadata = os.lstat(directory)
                    staged_identities[item] = (metadata.st_dev, metadata.st_ino)
                    if force:
                        global_install._require_no_posix_acl(
                            directory, "access", expected_identity=staged_identities[item],
                        )
                        global_install._require_no_posix_acl(
                            directory, "default", expected_identity=staged_identities[item],
                        )
                directories.add(item)
            if force:
                parent_identity = staged_identities.get(parent)
                if parent_identity is None:
                    raise GlobalCliError("CLI package staging parent identity is unavailable.", 4)
                global_install._require_no_posix_acl(
                    data_root / parent, "default", expected_identity=parent_identity,
                )
            written_identity = source_edit._write_private_file(
                data_root / package_relative, data_root, package_relative,
                source_payload[relative], 0o444, lock, lock_identity,
            )
            if force:
                global_install._require_no_posix_acl(
                    data_root / package_relative, "access",
                    expected_identity=written_identity,
                )
        receipt = _package_receipt(version, commit, source_payload)
        receipt_relative = f"{relative_stage}/{_RECEIPT}"
        if force:
            global_install._require_no_posix_acl(
                stage, "default", expected_identity=staged_identities[relative_stage],
            )
        receipt_identity = source_edit._write_private_file(
            data_root / receipt_relative, data_root, receipt_relative, receipt, 0o444,
            lock, lock_identity,
        )
        if force:
            global_install._require_no_posix_acl(
                data_root / receipt_relative, "access",
                expected_identity=receipt_identity,
            )
        for relative in sorted(directories, key=lambda item: item.count("/"), reverse=True):
            _set_directory_mode(
                data_root, relative, 0o555, data_identity, lock, lock_identity, sync=True,
                reject_acl=force,
            )
        package_root = data_root / relative_stage
        _validate_package(
            package_root, version=version, commit=commit,
            receipt_sha256=_digest(receipt),
        )
        return package_root
    except GlobalCliError:
        raise
    except BaseException as error:
        raise GlobalCliError(
            f"CLI package staging is incomplete; preserve {stage} for inspection: {error}", 4,
        ) from error


def _set_directory_mode(root: Path, relative: str, mode: int,
                        root_identity: tuple[int, int], lock,
                        lock_identity: tuple[int, int], *, sync: bool = False,
                        reject_acl: bool = False) -> None:
    path = root / relative
    _verify_directory(root, root_identity)
    source_edit._lock_identity(lock, lock_identity)
    try:
        before = os.lstat(path)
        if (not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode)
                or before.st_uid != os.geteuid() or before.st_dev != os.lstat(root).st_dev):
            raise GlobalCliError(f"Unsafe CLI package directory before mode change: {relative}", 4)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise GlobalCliError(f"CLI package directory changed before mode change: {relative}", 4)
            if reject_acl:
                global_install._require_no_posix_acl(
                    path, "access", expected_identity=(before.st_dev, before.st_ino), code=4,
                )
            os.fchmod(descriptor, mode)
            after = os.fstat(descriptor)
            placed = os.lstat(path)
            if ((after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
                    or (placed.st_dev, placed.st_ino) != (after.st_dev, after.st_ino)
                    or stat.S_IMODE(after.st_mode) != mode):
                raise GlobalCliError(f"CLI package directory mode or identity is unconfirmed: {relative}", 4)
            if sync:
                try:
                    os.fsync(descriptor)
                except (OSError, NotImplementedError) as error:
                    raise GlobalCliError(
                        f"Cannot durably sync staged CLI package directory {root / relative}: {error}",
                        4,
                    ) from error
                synced = os.fstat(descriptor)
                placed = os.lstat(path)
                if ((synced.st_dev, synced.st_ino) != (before.st_dev, before.st_ino)
                        or (placed.st_dev, placed.st_ino) != (synced.st_dev, synced.st_ino)
                        or stat.S_IMODE(synced.st_mode) != mode):
                    raise GlobalCliError(
                        f"CLI package directory changed during durable sync: {root / relative}", 4,
                    )
                source_edit._lock_identity(lock, lock_identity)
        finally:
            os.close(descriptor)
    except GlobalCliError:
        raise
    except OSError as error:
        raise GlobalCliError(f"Cannot set CLI package directory mode for {relative}: {error}", 4) from error


def _repair_package_files(package_root: Path, payload: dict[str, bytes], *,
                          version: str, commit: str, receipt_sha256: str,
                          lock, lock_identity: tuple[int, int]) -> tuple[str, ...]:
    _preflight_force_package_repair(
        package_root, payload, version=version, commit=commit,
        receipt_sha256=receipt_sha256,
    )
    identity = _validate_force_package(
        package_root, version=version, commit=commit, receipt_sha256=receipt_sha256,
    )
    if not _payload_matches_package(payload, identity):
        raise GlobalCliError("Installed CLI package receipt differs from the verified source payload.")
    files, directories = _scan_package_tree(package_root)
    expected_files = set(payload) | {_RECEIPT}
    expected_directories = {""}
    for relative in expected_files:
        parts = relative.split("/")[:-1]
        expected_directories.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    if not set(files) <= expected_files or not set(directories) <= expected_directories:
        raise GlobalCliError("CLI package contains unenumerated resources.")

    changed = tuple(
        relative for relative, desired in sorted(payload.items())
        if relative not in files
        or files[relative][0] != desired
        or stat.S_IMODE(files[relative][1].st_mode) != 0o444
    )
    changed_directories = (
        set(expected_directories) - set(directories)
        | {
            relative for relative, metadata in directories.items()
            if stat.S_IMODE(metadata.st_mode) != 0o555
        }
    )
    if (not changed and set(directories) == expected_directories
            and all(stat.S_IMODE(item.st_mode) == 0o555 for item in directories.values())):
        return ()

    versions_info = _ensure_directory(package_root.parent, create=False)
    if versions_info is None:
        raise GlobalCliError("CLI package repair has no verified versions directory.")
    versions_root, versions_identity = versions_info
    if package_root != versions_root / version:
        raise GlobalCliError("CLI package repair target is not its exact version directory.")
    package_metadata = os.lstat(package_root)
    package_identity = (package_metadata.st_dev, package_metadata.st_ino)
    stage_name = f".staging-{uuid.uuid4().hex}"
    stage = versions_root / stage_name
    staged_directories: dict[str, tuple[int, int]] = {}
    target_started = False
    try:
        global_install._require_no_posix_acl(
            versions_root, "default", expected_identity=versions_identity,
        )
        source_edit._make_directory(stage, versions_root, lock, lock_identity)
        metadata = os.lstat(stage)
        staged_directories[stage_name] = (metadata.st_dev, metadata.st_ino)
        global_install._require_no_posix_acl(
            stage, "access", expected_identity=staged_directories[stage_name],
        )
        global_install._require_no_posix_acl(
            stage, "default", expected_identity=staged_directories[stage_name],
        )
        for relative in changed:
            parts = relative.split("/")[:-1]
            for index in range(1, len(parts) + 1):
                staged_relative = f"{stage_name}/{'/'.join(parts[:index])}"
                if staged_relative in staged_directories:
                    continue
                staged_path = versions_root / staged_relative
                parent_relative = str(Path(staged_relative).parent)
                parent_identity = staged_directories.get(parent_relative)
                if parent_identity is None:
                    raise GlobalCliError("CLI package staging parent identity is unavailable.", 4)
                global_install._require_no_posix_acl(
                    staged_path.parent, "default", expected_identity=parent_identity,
                )
                source_edit._make_directory(staged_path, versions_root, lock, lock_identity)
                metadata = os.lstat(staged_path)
                staged_directories[staged_relative] = (metadata.st_dev, metadata.st_ino)
                global_install._require_no_posix_acl(
                    staged_path, "access",
                    expected_identity=staged_directories[staged_relative],
                )
                global_install._require_no_posix_acl(
                    staged_path, "default",
                    expected_identity=staged_directories[staged_relative],
                )
            staged_relative = f"{stage_name}/{relative}"
            parent_identity = staged_directories.get(str(Path(staged_relative).parent))
            if parent_identity is None:
                raise GlobalCliError("CLI package staging parent identity is unavailable.", 4)
            global_install._require_no_posix_acl(
                (versions_root / staged_relative).parent, "default",
                expected_identity=parent_identity,
            )
            staged_identity = source_edit._write_private_file(
                versions_root / staged_relative, versions_root, staged_relative,
                payload[relative], 0o444, lock, lock_identity,
            )
            global_install._require_no_posix_acl(
                versions_root / staged_relative, "access",
                expected_identity=staged_identity,
            )
        for relative, staged_identity in sorted(
            staged_directories.items(), key=lambda item: item[0].count("/"), reverse=True,
        ):
            _sync_directory_strict(
                versions_root / relative, staged_identity, lock, lock_identity,
            )

        _verify_directory(package_root, package_identity)
        current_files, current_directories = _scan_package_tree(package_root)
        if (set(current_files) != set(files) or set(current_directories) != set(directories)
                or any(current_files[name][0] != files[name][0]
                       or _signature(current_files[name][1]) != _signature(files[name][1])
                       for name in files)
                or any(_durability_signature(current_directories[name])
                       != _durability_signature(directories[name]) for name in directories)):
            raise GlobalCliError("CLI package changed during force-repair staging.", 4)

        _preflight_force_package_repair(
            package_root, payload, version=version, commit=commit,
            receipt_sha256=receipt_sha256,
        )
        target_started = True
        for relative in sorted(directories, key=lambda item: (item.count("/"), item)):
            _set_directory_mode(
                package_root, relative, 0o700, package_identity, lock, lock_identity,
                reject_acl=True,
            )
        for relative in sorted(expected_directories - set(directories),
                               key=lambda item: (item.count("/"), item)):
            target_directory = package_root / relative
            global_install._require_no_posix_acl(target_directory.parent, "default", code=4)
            source_edit._make_directory(target_directory, package_root, lock, lock_identity)
            global_install._require_no_posix_acl(target_directory, "access", code=4)
            global_install._require_no_posix_acl(target_directory, "default", code=4)

        for relative in changed:
            target = package_root / relative
            staged_relative = f"{stage_name}/{relative}"
            staged_path = versions_root / staged_relative
            try:
                staged_metadata = os.lstat(staged_path)
            except OSError as error:
                raise GlobalCliError(
                    f"Cannot inspect staged CLI repair resource {relative}: {error}", 4,
                ) from error
            old = files.get(relative)
            if old is None:
                try:
                    os.lstat(target)
                except FileNotFoundError:
                    pass
                else:
                    raise GlobalCliError(
                        f"CLI package repair target appeared before publication: {relative}", 4,
                    )
            else:
                current, current_metadata = _safe_read(package_root, relative)
                if current != old[0] or _signature(current_metadata) != _signature(old[1]):
                    raise GlobalCliError(
                        f"CLI package repair target changed before publication: {relative}", 4,
                    )
                global_install._require_no_posix_acl(
                    target, "access",
                    expected_identity=(current_metadata.st_dev, current_metadata.st_ino),
                    code=4,
                )
            global_install._require_no_posix_acl(
                staged_path, "access",
                expected_identity=(staged_metadata.st_dev, staged_metadata.st_ino), code=4,
            )
            source_edit._lock_identity(lock, lock_identity)
            try:
                if old is None:
                    os.link(staged_path, target)
                    os.unlink(staged_path)
                else:
                    os.replace(staged_path, target)
            except OSError as error:
                raise GlobalCliError(
                    f"Cannot atomically restore CLI package resource {relative}: {error}", 4,
                ) from error
            source_edit._sync_directory(target.parent)
            restored, restored_metadata = _safe_read(package_root, relative)
            if (restored != payload[relative]
                    or (restored_metadata.st_dev, restored_metadata.st_ino)
                    != (staged_metadata.st_dev, staged_metadata.st_ino)
                    or stat.S_IMODE(restored_metadata.st_mode) != 0o444):
                raise GlobalCliError(
                    f"Restored CLI package resource failed verification: {relative}", 4,
                )
            global_install._require_no_posix_acl(
                target, "access",
                expected_identity=(restored_metadata.st_dev, restored_metadata.st_ino),
                code=4,
            )

        for relative in sorted(
            expected_directories, key=lambda item: (item.count("/"), item), reverse=True,
        ):
            _set_directory_mode(
                package_root, relative, 0o555, package_identity, lock, lock_identity,
                sync=True, reject_acl=True,
            )
        for relative, staged_identity in sorted(
            staged_directories.items(), key=lambda item: item[0].count("/"), reverse=True,
        ):
            path = versions_root / relative
            metadata = os.lstat(path)
            if ((metadata.st_dev, metadata.st_ino) != staged_identity
                    or not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
                    or metadata.st_uid != os.geteuid()):
                raise GlobalCliError(
                    f"Staging directory identity changed during CLI repair: {relative}", 4,
                )
            source_edit._lock_identity(lock, lock_identity)
            os.rmdir(path)
        _sync_directory_strict(versions_root, versions_identity, lock, lock_identity)
        _validate_package(
            package_root, version=version, commit=commit, receipt_sha256=receipt_sha256,
        )
        return tuple(sorted((*changed, *changed_directories)))
    except GlobalCliError as error:
        if target_started and error.code != 4:
            raise GlobalCliError(f"CLI package force repair is unconfirmed: {error}", 4) from error
        raise
    except BaseException as error:
        code = 4 if target_started else 3
        state = "is unconfirmed" if target_started else "could not be staged"
        raise GlobalCliError(f"CLI package force repair {state}: {error}", code) from error


def _repair_stable_launcher(data_root: Path, bin_root: Path,
                            bin_identity: tuple[int, int], lock,
                            lock_identity: tuple[int, int]) -> bool:
    expected = _launcher_bytes(data_root)
    try:
        old, old_metadata = _safe_read(bin_root, "olympus", limit=64 * 1024)
    except GlobalCliError as error:
        try:
            os.lstat(bin_root / "olympus")
        except FileNotFoundError:
            old, old_metadata = None, None
        else:
            raise error
    if (old == expected and old_metadata is not None
            and stat.S_IMODE(old_metadata.st_mode) == 0o755):
        return False

    temporary_relative = f".olympus-{uuid.uuid4().hex}.tmp"
    temporary = bin_root / temporary_relative
    global_install._require_no_posix_acl(
        bin_root, "default", expected_identity=bin_identity,
    )
    if old_metadata is not None:
        global_install._require_no_posix_acl(
            bin_root / "olympus", "access",
            expected_identity=(old_metadata.st_dev, old_metadata.st_ino),
        )
    staged_identity = source_edit._write_private_file(
        temporary, bin_root, temporary_relative, expected, 0o755, lock, lock_identity,
    )
    global_install._require_no_posix_acl(
        bin_root, "default", expected_identity=bin_identity, code=4,
    )
    global_install._require_no_posix_acl(
        temporary, "access", expected_identity=staged_identity, code=4,
    )
    staged_metadata = os.lstat(temporary)
    if old_metadata is None:
        try:
            os.lstat(bin_root / "olympus")
        except FileNotFoundError:
            pass
        else:
            raise GlobalCliError("Stable CLI launcher appeared before force repair.", 4)
    else:
        current, current_metadata = _safe_read(bin_root, "olympus", limit=64 * 1024)
        if current != old or _signature(current_metadata) != _signature(old_metadata):
            raise GlobalCliError("Stable CLI launcher changed before force repair.", 4)
        global_install._require_no_posix_acl(
            bin_root / "olympus", "access",
            expected_identity=(current_metadata.st_dev, current_metadata.st_ino), code=4,
        )
    global_install._require_no_posix_acl(temporary, "access", code=4)
    source_edit._lock_identity(lock, lock_identity)
    try:
        if old_metadata is None:
            os.link(temporary, bin_root / "olympus")
            os.unlink(temporary)
        else:
            os.replace(temporary, bin_root / "olympus")
    except OSError as error:
        raise GlobalCliError(f"Cannot atomically restore the stable CLI launcher: {error}", 4) from error
    _sync_directory_strict(bin_root, bin_identity, lock, lock_identity)
    restored, restored_metadata = _safe_read(bin_root, "olympus", limit=64 * 1024)
    if (restored != expected
            or (restored_metadata.st_dev, restored_metadata.st_ino)
            != (staged_metadata.st_dev, staged_metadata.st_ino)
            or stat.S_IMODE(restored_metadata.st_mode) != 0o755):
        raise GlobalCliError("Restored stable CLI launcher failed verification.", 4)
    global_install._require_no_posix_acl(
        bin_root / "olympus", "access",
        expected_identity=(restored_metadata.st_dev, restored_metadata.st_ino), code=4,
    )
    return True


def _preflight_force_launcher(data_root: Path, bin_root: Path,
                              bin_identity: tuple[int, int]) -> bool:
    expected = _launcher_bytes(data_root)
    try:
        old, metadata = _safe_read(bin_root, "olympus", limit=64 * 1024)
    except GlobalCliError as error:
        try:
            os.lstat(bin_root / "olympus")
        except FileNotFoundError:
            old, metadata = None, None
        else:
            raise error
    if (old == expected and metadata is not None
            and stat.S_IMODE(metadata.st_mode) == 0o755):
        return False
    global_install._require_no_posix_acl(
        bin_root, "default", expected_identity=bin_identity,
    )
    if metadata is not None:
        global_install._require_no_posix_acl(
            bin_root / "olympus", "access",
            expected_identity=(metadata.st_dev, metadata.st_ino),
        )
    return True


def _preflight_force_cli_update(data_root: Path, data_identity: tuple[int, int],
                                bin_root: Path, bin_identity: tuple[int, int],
                                previous: InstalledIdentity, *,
                                version: str, commit: str,
                                payload: dict[str, bytes]) -> None:
    versions_info = _ensure_directory(data_root / "versions", create=False)
    if versions_info is None:
        raise GlobalCliError("Versioned CLI package directory is missing.")
    versions_root, _ = versions_info
    destination = versions_root / version
    try:
        os.lstat(destination)
    except FileNotFoundError:
        destination_exists = False
    except OSError as error:
        raise GlobalCliError(f"Cannot inspect CLI package destination: {error}") from error
    else:
        destination_exists = True

    if destination_exists:
        identity = _validate_force_package(destination, version=version, commit=commit)
        if not _payload_matches_package(payload, identity):
            raise GlobalCliError("Existing CLI update package differs from the verified source payload.")
        _preflight_force_package_repair(
            destination, payload, version=version, commit=commit,
            receipt_sha256=identity.receipt_sha256,
        )
    else:
        global_install._require_no_posix_acl(
            versions_root, "default", expected_identity=versions_info[1],
        )

    if (version, commit) != (previous.version, previous.commit):
        current, metadata = _safe_read(data_root, _CURRENT, limit=1024)
        expected = _current_bytes(previous.version, previous.commit, previous.receipt_sha256)
        if current != expected:
            raise GlobalCliError("Current CLI marker changed before force-update ACL preflight.", 4)
        global_install._require_no_posix_acl(
            data_root, "default", expected_identity=data_identity,
        )
        global_install._require_no_posix_acl(
            data_root / _CURRENT, "access",
            expected_identity=(metadata.st_dev, metadata.st_ino),
        )
    _preflight_force_launcher(data_root, bin_root, bin_identity)


def _publish_package_noreplace(versions_root: Path, staging_name: str, version: str,
                               versions_identity: tuple[int, int], lock,
                               lock_identity: tuple[int, int]) -> None:
    """Atomically publish only a tool-owned staging directory without replacing a version."""
    if _STAGING_NAME.fullmatch(staging_name) is None or _VERSION.fullmatch(version) is None:
        raise GlobalCliError("CLI package publication names are outside the owned versions namespace.", 4)
    _verify_directory(versions_root, versions_identity)
    source_edit._lock_identity(lock, lock_identity)
    descriptor = -1
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(versions_root, flags)
        root_metadata = os.fstat(descriptor)
        if ((root_metadata.st_dev, root_metadata.st_ino) != versions_identity
                or root_metadata.st_uid != os.geteuid()):
            raise GlobalCliError("Versioned CLI package directory identity changed before publication.", 4)
        staged = os.stat(staging_name, dir_fd=descriptor, follow_symlinks=False)
        if (not stat.S_ISDIR(staged.st_mode) or stat.S_ISLNK(staged.st_mode)
                or staged.st_dev != root_metadata.st_dev or staged.st_uid != os.geteuid()):
            raise GlobalCliError("Staged CLI package is not a safe direct child of the versions directory.", 4)

        try:
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = libc.renameat2
        except (AttributeError, OSError) as error:
            raise GlobalCliError(
                f"Atomic no-replace package publication is unavailable: {error}", 4,
            ) from error
        renameat2.argtypes = (
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
        )
        renameat2.restype = ctypes.c_int
        if renameat2(
            descriptor, os.fsencode(staging_name), descriptor, os.fsencode(version), 1,
        ) != 0:
            error_number = ctypes.get_errno() or errno.EIO
            raise GlobalCliError(
                f"Atomic no-replace package publication failed: {os.strerror(error_number)}",
                4,
            )
        try:
            os.fsync(descriptor)
        except (OSError, NotImplementedError) as error:
            raise GlobalCliError(
                f"Cannot durably sync published CLI package directory: {error}", 4,
            ) from error

        published = os.stat(version, dir_fd=descriptor, follow_symlinks=False)
        try:
            os.stat(staging_name, dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise GlobalCliError("Staged CLI package remained after publication.", 4)
        if ((published.st_dev, published.st_ino) != (staged.st_dev, staged.st_ino)
                or not stat.S_ISDIR(published.st_mode) or stat.S_ISLNK(published.st_mode)):
            raise GlobalCliError("Published CLI package identity could not be confirmed.", 4)
        published_root = os.fstat(descriptor)
        if (published_root.st_dev, published_root.st_ino) != versions_identity:
            raise GlobalCliError("Versioned CLI package directory changed during publication.", 4)
        _verify_directory(versions_root, versions_identity)
        source_edit._lock_identity(lock, lock_identity)
    except GlobalCliError:
        raise
    except OSError as error:
        raise GlobalCliError(f"Cannot safely publish CLI package without replacement: {error}", 4) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_state(data_root: Path, bin_root: Path, *,
                allow_cleanup_pending: bool = False,
                allow_managed_drift: bool = False) -> InstalledIdentity | None:
    data_info = _ensure_directory(data_root, create=False)
    bin_info = _ensure_directory(bin_root, create=False)
    if data_info is None:
        if bin_info is not None:
            try:
                os.lstat(bin_root / "olympus")
            except FileNotFoundError:
                return None
            except OSError as error:
                raise GlobalCliError(f"Cannot inspect the stable CLI launcher: {error}") from error
            raise GlobalCliError("A stable CLI launcher exists without its per-user package marker.")
        return None
    data_root, data_identity = data_info
    _verify_directory(data_root, data_identity)
    pending = _read_cleanup_record(data_root)
    if pending is not None and not allow_cleanup_pending:
        raise GlobalCliError(
            f"CLI uninstall cleanup for {pending.version} is pending; rerun explicit uninstall.", 4,
        )
    try:
        marker_meta = os.lstat(data_root / _CURRENT)
    except FileNotFoundError:
        if bin_info is not None:
            try:
                os.lstat(bin_root / "olympus")
            except FileNotFoundError:
                return None
            except OSError as error:
                raise GlobalCliError(f"Cannot inspect the stable CLI launcher: {error}") from error
            raise GlobalCliError("A stable CLI launcher exists without its current package marker.")
        return None
    except OSError as error:
        raise GlobalCliError(f"Cannot inspect the current CLI marker: {error}") from error
    if not stat.S_ISREG(marker_meta.st_mode) or stat.S_ISLNK(marker_meta.st_mode):
        raise GlobalCliError("The current CLI marker is not a regular owned file.")
    raw_current, marker_meta = _safe_read(data_root, _CURRENT, limit=1024)
    if stat.S_IMODE(marker_meta.st_mode) != 0o600:
        raise GlobalCliError("The current CLI marker has an unexpected mode.")
    version, commit, receipt_hash = _parse_current(raw_current)
    package_root = data_root / "versions" / version
    identity = (
        _validate_force_package(
            package_root, version=version, commit=commit, receipt_sha256=receipt_hash,
        )
        if allow_managed_drift else _validate_package(
            package_root, version=version, commit=commit, receipt_sha256=receipt_hash,
        )
    )
    if bin_info is None:
        raise GlobalCliError("The current CLI package has no safe ~/.local/bin directory.")
    bin_root, _ = bin_info
    if allow_managed_drift:
        try:
            os.lstat(bin_root / "olympus")
        except FileNotFoundError:
            pass
        except OSError as error:
            raise GlobalCliError(f"Cannot inspect the stable CLI launcher: {error}") from error
        else:
            _safe_read(bin_root, "olympus", limit=64 * 1024)
    else:
        launcher, launcher_meta = _safe_read(bin_root, "olympus", limit=64 * 1024)
        if launcher != _launcher_bytes(data_root) or stat.S_IMODE(launcher_meta.st_mode) != 0o755:
            raise GlobalCliError("The stable CLI launcher is changed or does not match its package root.")
    return identity


def _acquire_package_lock(data_root: Path, *, create: bool):
    try:
        lock = source_edit._acquire_lock(data_root, create=create)
        return lock, source_edit._lock_identity(lock)
    except source_edit.LockError as error:
        code = 4 if isinstance(error, source_edit.LockIdentityError) else 3
        raise GlobalCliError(f"Cannot acquire the stable per-user CLI package lock: {error}", code) from error


def _release_package_lock(lock) -> None:
    try:
        source_edit._release_lock(lock)
    except source_edit.LockError as error:
        raise GlobalCliError(f"Per-user CLI package lock identity is unconfirmed: {error}", 4) from error


def _read_global_manifest(source: Path, version: str, commit: str):
    candidate = global_install._candidate(source, version, commit)
    try:
        root = global_readonly.resolve_roots(("opencode",))["opencode"]
        root = global_readonly._root(root)
    except (global_readonly.GlobalFault, OSError, RuntimeError) as error:
        raise GlobalCliError(f"Cannot safely resolve global OpenCode target: {error}") from error
    info = _ensure_directory(root, create=False)
    if info is None:
        return root, None, candidate, None, None
    root, root_identity = info
    try:
        manifest, entries, raw, _ = global_install._manifest(root, candidate)
    except global_install.GlobalInstallError:
        raise
    if manifest is None:
        return root, None, candidate, None, root_identity
    if (manifest["installed_version"] != version
            or manifest["installed_from_commit"] != commit):
        raise GlobalCliError("Global OpenCode version/commit marker differs from the CLI package identity.")
    return root, manifest, candidate, raw, root_identity


def _require_global(source: Path, version: str, commit: str) -> tuple[Path, str]:
    root, manifest, _, marker_before, identity_before = _read_global_manifest(source, version, commit)
    if manifest is None:
        raise GlobalCliError("The matching global OpenCode ownership marker is absent.")
    outcome = global_install.verify(source, version=version, commit=commit)
    if outcome.result != "verified" or Path(outcome.root) != root:
        raise GlobalCliError("Global OpenCode verification did not confirm the expected target.", 4)
    root_after, manifest_after, _, marker_after, identity_after = _read_global_manifest(
        source, version, commit,
    )
    if (root_after != root or manifest_after is None or marker_after != marker_before
            or identity_after != identity_before):
        raise GlobalCliError("Global OpenCode ownership marker or root changed during verification.", 4)
    return root, outcome.result


def _global_identity_without_package() -> tuple[str, str] | None:
    try:
        root = global_readonly.resolve_roots(("opencode",))["opencode"]
        root = global_readonly._root(root)
    except (global_readonly.GlobalFault, OSError, RuntimeError) as error:
        raise GlobalCliError(f"Cannot safely resolve global OpenCode target: {error}") from error
    info = _ensure_directory(root, create=False)
    if info is None:
        return None
    root, _ = info
    raw = global_readonly._read(root, global_readonly._MANIFEST)
    if raw is None:
        from . import config_apply_transaction

        if config_apply_transaction.pending(root):
            raise GlobalCliError("A pending global transaction exists without an installed CLI package.", 4)
        return None
    try:
        manifest, _ = global_readonly._parse_manifest_bytes(raw, "opencode", None)
    except global_readonly.GlobalFault as error:
        raise GlobalCliError(f"Cannot identify the existing global OpenCode installation: {error}") from error
    return manifest["installed_version"], manifest["installed_from_commit"]


def _stage_and_transition(source: Path, version: str, commit: str, operation: str,
                          payload: dict[str, bytes],
                          data_root: Path, data_identity: tuple[int, int],
                          versions_root: Path, versions_identity: tuple[int, int],
                          bin_root: Path, bin_identity: tuple[int, int],
                           lock, lock_identity: tuple[int, int],
                           previous: InstalledIdentity | None, *,
                           force: bool = False) -> CliOutcome:
    destination = versions_root / version
    package_published = False
    package_repaired: tuple[str, ...] = ()
    if operation == "install":
        try:
            os.lstat(destination)
        except FileNotFoundError:
            pass
        except OSError as error:
            raise GlobalCliError(f"Cannot inspect CLI package destination: {error}") from error
        else:
            raise GlobalCliError(
                f"Versioned CLI package already exists; refusing adoption or overwrite: {destination}",
            )

        staged = _stage_package(
            data_root, payload, version, commit, data_identity, lock, lock_identity,
        )
        _verify_directory(data_root, data_identity)
        _verify_directory(versions_root, versions_identity)
        _, existing_manifest, _, _, _ = _read_global_manifest(staged, version, commit)
        if existing_manifest is not None:
            _require_global(staged, version, commit)
        lifecycle = global_install.install(staged, version=version, commit=commit)
        package_identity = None
        target_already_committed = False
    else:
        if previous is None:
            raise GlobalCliError("Update requires a verified current CLI package.")
        comparison = global_install._version_compare(version, previous.version)
        if comparison is None or comparison <= 0:
            raise GlobalCliError("CLI update must be a strictly newer supported release.")

        previous_pair = (previous.version, previous.commit)
        target_pair = (version, commit)
        installed_pair = _global_identity_without_package()
        if installed_pair == previous_pair:
            if not force:
                _require_global(previous.package_root, previous.version, previous.commit)
            target_already_committed = False
        elif installed_pair == target_pair:
            target_already_committed = True
        else:
            raise GlobalCliError(
                "Global OpenCode identity is neither the verified current release nor this update target.",
                4,
            )

        try:
            os.lstat(destination)
        except FileNotFoundError:
            destination_exists = False
        except OSError as error:
            raise GlobalCliError(f"Cannot inspect CLI package destination: {error}") from error
        else:
            destination_exists = True

        if target_already_committed and not destination_exists:
            raise GlobalCliError(
                "The committed global update has no intact local target package to activate.", 4,
            )
        if destination_exists:
            package_identity = (
                _validate_force_package(destination, version=version, commit=commit)
                if force else _validate_package(
                    destination, version=version, commit=commit, sync_durable=True,
                    lock=lock, lock_identity=lock_identity,
                )
            )
            if not _payload_matches_package(payload, package_identity):
                raise GlobalCliError(
                    "Existing CLI update package differs from the verified source payload.",
                )
            if force:
                package_repaired = _repair_package_files(
                    destination, payload, version=version, commit=commit,
                    receipt_sha256=package_identity.receipt_sha256,
                    lock=lock, lock_identity=lock_identity,
                )
                package_identity = _validate_package(
                    destination, version=version, commit=commit, sync_durable=True,
                    lock=lock, lock_identity=lock_identity,
                )
            _sync_directory_strict(
                versions_root, versions_identity, lock, lock_identity,
            )
        else:
            staged = _stage_package(
                data_root, payload, version, commit, data_identity, lock, lock_identity,
                force=force,
            )
            _verify_directory(data_root, data_identity)
            _verify_directory(versions_root, versions_identity)
            _publish_package_noreplace(
                versions_root, staged.name, version, versions_identity, lock, lock_identity,
            )
            package_published = True
            package_identity = _validate_package(
                destination, version=version, commit=commit,
            )
            if not _payload_matches_package(payload, package_identity):
                raise GlobalCliError(
                    "Published CLI update package differs from the verified source payload.", 4,
                )

        _verify_directory(data_root, data_identity)
        _verify_directory(versions_root, versions_identity)
        installed_pair = _global_identity_without_package()
        if installed_pair == previous_pair:
            if not force:
                _require_global(previous.package_root, previous.version, previous.commit)
            lifecycle = global_install.update(
                destination, version=version, commit=commit, force=force,
            )
            target_already_committed = False
        elif installed_pair == target_pair:
            target_already_committed = True
            lifecycle = (
                global_install.update(destination, version=version, commit=commit, force=True)
                if force else None
            )
        else:
            raise GlobalCliError(
                "Global OpenCode identity changed to an unrelated release during update.", 4,
            )

    try:
        global_root, _ = _require_global(destination if operation == "update" else staged,
                                         version, commit)
    except BaseException as error:
        if lifecycle is None:
            raise GlobalCliError(
                "The target global version/commit could not be confirmed before CLI activation; "
                f"preserve package evidence at {destination}: {error}", 4,
            ) from error
        raise GlobalCliError(
            f"Global lifecycle returned {lifecycle.result}, but its version/commit could not be confirmed; "
            f"preserve package evidence at {staged if operation == 'install' else destination}: {error}",
            4,
        ) from error

    try:
        if operation == "install":
            _verify_directory(versions_root, versions_identity)
            try:
                os.lstat(destination)
            except FileNotFoundError:
                pass
            else:
                raise GlobalCliError(
                    f"Versioned CLI destination appeared during activation: {destination}", 4,
                )
            _publish_package_noreplace(
                versions_root, staged.name, version, versions_identity, lock, lock_identity,
            )
            package_published = True
            package_identity = _validate_package(
                destination, version=version, commit=commit,
            )
        else:
            package_identity = _validate_package(
                destination, version=version, commit=commit,
            )
            if not _payload_matches_package(payload, package_identity):
                raise GlobalCliError(
                    "CLI update package changed after global verification.", 4,
                )
        _verify_directory(data_root, data_identity)
        if previous is None:
            try:
                os.lstat(bin_root / "olympus")
            except FileNotFoundError:
                pass
            else:
                raise GlobalCliError("Stable CLI launcher appeared during activation.", 4)
            source_edit._write_private_file(
                bin_root / "olympus", bin_root, "olympus", _launcher_bytes(data_root),
                0o755, lock, lock_identity,
            )
        _activate_current(
            data_root, data_identity, package_identity, lock, lock_identity,
            bin_root, bin_identity, previous, force=force,
        )
        launcher_repaired = (
            _repair_stable_launcher(data_root, bin_root, bin_identity, lock, lock_identity)
            if force else False
        )
        _verify_directory(data_root, data_identity)
        activated = _read_state(data_root, bin_root)
        if (activated is None or activated.version != version or activated.commit != commit):
            raise GlobalCliError("Activated CLI package identity did not verify.", 4)
        _require_global(destination, version, commit)
    except BaseException as error:
        global_state = (
            f"Global lifecycle committed as {lifecycle.result}"
            if lifecycle is not None
            else "Global update already verified"
        )
        package_evidence = (
            f"{staged} and/or {destination}" if operation == "install" else str(destination)
        )
        raise GlobalCliError(
            f"{global_state}, but CLI activation is unconfirmed; "
            f"preserve package evidence at {package_evidence}, plus the global evidence: {error}", 4,
        ) from error

    changed = [str(data_root / _CURRENT)]
    if package_published:
        changed.insert(0, str(destination))
    if force:
        changed.extend(str(destination / item) for item in package_repaired)
        if launcher_repaired:
            changed.append(str(bin_root / "olympus"))
    if previous is None:
        changed.append(str(bin_root / "olympus"))
    if lifecycle is not None:
        changed.extend(lifecycle.changed_paths)
    detail = (
        "The previously committed global update and per-user CLI package identities verified."
        if target_already_committed
        else "Global and per-user CLI package identities verified."
    )
    return CliOutcome(
        operation, "committed", version, commit, str(destination), str(global_root),
        tuple(changed), detail,
    )


def _activate_current(data_root: Path, data_identity: tuple[int, int],
                      package_identity: InstalledIdentity, lock,
                      lock_identity: tuple[int, int], bin_root: Path,
                      bin_identity: tuple[int, int], previous: InstalledIdentity | None,
                      *, force: bool = False) -> None:
    _verify_directory(data_root, data_identity)
    _verify_directory(bin_root, bin_identity)
    payload = _current_bytes(
        package_identity.version, package_identity.commit, package_identity.receipt_sha256,
    )
    current_path = data_root / _CURRENT
    if previous is None:
        relative = _CURRENT
        source_edit._write_private_file(
            current_path, data_root, relative, payload, 0o600, lock, lock_identity,
        )
        return

    old_raw, old_meta = _safe_read(data_root, _CURRENT, limit=1024)
    old_expected = _current_bytes(previous.version, previous.commit, previous.receipt_sha256)
    if old_raw != old_expected:
        raise GlobalCliError("Current CLI marker changed before activation.", 4)
    if force:
        global_install._require_no_posix_acl(
            data_root, "default", expected_identity=data_identity, code=4,
        )
        global_install._require_no_posix_acl(
            current_path, "access",
            expected_identity=(old_meta.st_dev, old_meta.st_ino), code=4,
        )
    temporary_relative = f".current-{uuid.uuid4().hex}.tmp"
    temporary = data_root / temporary_relative
    staged_identity = source_edit._write_private_file(
        temporary, data_root, temporary_relative, payload, 0o600, lock, lock_identity,
    )
    if force:
        global_install._require_no_posix_acl(
            temporary, "access", expected_identity=staged_identity, code=4,
        )
    staged_meta = os.lstat(temporary)
    current_again, current_meta = _safe_read(data_root, _CURRENT, limit=1024)
    if (current_again != old_raw or current_meta.st_dev != old_meta.st_dev
            or current_meta.st_ino != old_meta.st_ino):
        raise GlobalCliError("Current CLI marker changed before atomic activation.", 4)
    if force:
        global_install._require_no_posix_acl(
            current_path, "access",
            expected_identity=(current_meta.st_dev, current_meta.st_ino), code=4,
        )
        global_install._require_no_posix_acl(temporary, "access", code=4)
    _verify_directory(data_root, data_identity)
    source_edit._lock_identity(lock, lock_identity)
    os.replace(temporary, current_path)
    written, written_meta = _safe_read(data_root, _CURRENT, limit=1024)
    if (written != payload or (written_meta.st_dev, written_meta.st_ino)
            != (staged_meta.st_dev, staged_meta.st_ino)):
        raise GlobalCliError("Atomic current CLI marker activation could not be verified.", 4)
    if force:
        global_install._require_no_posix_acl(
            current_path, "access",
            expected_identity=(written_meta.st_dev, written_meta.st_ino), code=4,
        )
    _sync_directory_strict(data_root, data_identity, lock, lock_identity)


def _inspect_cleanup_package(data_root: Path, record: _CleanupRecord):
    versions_info = _ensure_directory(data_root / "versions", create=False)
    if versions_info is None:
        raise GlobalCliError("Pending uninstall evidence has no CLI versions directory.", 4)
    versions_root, versions_identity = versions_info
    if (versions_identity != (record.versions_dev, record.versions_ino)
            or record.package_dev != record.versions_dev):
        raise GlobalCliError("CLI versions directory changed since uninstall cleanup was recorded.", 4)
    package_root = data_root / "versions" / record.version
    if package_root.parent != versions_root:
        raise GlobalCliError("Pending uninstall package path is not the exact versions child.", 4)
    try:
        root_metadata = os.lstat(package_root)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise GlobalCliError(f"Cannot inspect pending CLI package cleanup: {error}", 4) from error
    if (not stat.S_ISDIR(root_metadata.st_mode) or stat.S_ISLNK(root_metadata.st_mode)
            or root_metadata.st_uid != os.geteuid()
            or (root_metadata.st_dev, root_metadata.st_ino) != (record.package_dev, record.package_ino)):
        raise GlobalCliError("Pending uninstall package root no longer matches its recorded identity.", 4)

    files, directories = _scan_package_tree(package_root)
    if _RECEIPT not in files:
        if files or set(directories) != {""} or stat.S_IMODE(root_metadata.st_mode) != 0o700:
            raise GlobalCliError("Package receipt is missing before the exact package tree was emptied.", 4)
        return files, directories, {}

    raw_receipt, receipt_metadata = files[_RECEIPT]
    _, _, recorded, _ = _parse_package_receipt(
        raw_receipt, receipt_metadata, version=record.version, commit=record.commit,
        receipt_sha256=record.receipt_sha256,
    )
    expected_files = set(recorded) | {_RECEIPT}
    expected_directories = {""}
    for relative in expected_files:
        parts = relative.split("/")[:-1]
        expected_directories.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    if (not set(files) <= expected_files or not set(directories) <= expected_directories):
        raise GlobalCliError("Pending CLI package contains unexpected files or directories.", 4)

    total = 0
    for relative, (raw, metadata) in files.items():
        if relative == _RECEIPT:
            continue
        if (_digest(raw) != recorded[relative] or stat.S_IMODE(metadata.st_mode) != 0o444):
            raise GlobalCliError(f"Refusing to resume cleanup of changed CLI package file: {relative}", 4)
        total += len(raw)
    if total > _MAX_PACKAGE_BYTES:
        raise GlobalCliError("Pending CLI package exceeds its bounded byte inventory.", 4)
    for relative, metadata in directories.items():
        if stat.S_IMODE(metadata.st_mode) not in (0o555, 0o700):
            raise GlobalCliError(f"Pending CLI package directory has an unexpected mode: {relative or '.'}", 4)
    return files, directories, recorded


def _remove_package(data_root: Path, record: _CleanupRecord, lock,
                    lock_identity: tuple[int, int]) -> None:
    snapshot = _inspect_cleanup_package(data_root, record)
    if snapshot is None:
        return
    files, directories, recorded = snapshot
    package_root = data_root / "versions" / record.version
    root_identity = (record.package_dev, record.package_ino)
    if not files:
        root_metadata = os.lstat(package_root)
        if (not stat.S_ISDIR(root_metadata.st_mode) or stat.S_ISLNK(root_metadata.st_mode)
                or root_metadata.st_uid != os.geteuid() or stat.S_IMODE(root_metadata.st_mode) != 0o700
                or (root_metadata.st_dev, root_metadata.st_ino) != root_identity):
            raise GlobalCliError("Refusing to remove an unverified empty CLI package root.", 4)
        source_edit._lock_identity(lock, lock_identity)
        os.rmdir(package_root)
        return

    for relative in sorted(directories, key=lambda item: item.count("/")):
        mode = stat.S_IMODE(directories[relative].st_mode)
        if mode != 0o700:
            _set_directory_mode(
                package_root, relative or ".", 0o700, root_identity, lock, lock_identity,
            )

    for relative in sorted(recorded, reverse=True):
        if relative not in files:
            continue
        raw, metadata = files[relative]
        current, current_metadata = _safe_read(package_root, relative)
        if (current != raw or (current_metadata.st_dev, current_metadata.st_ino)
                != (metadata.st_dev, metadata.st_ino)):
            raise GlobalCliError(f"Refusing to remove changed CLI package file: {relative}", 4)
        source_edit._lock_identity(lock, lock_identity)
        os.unlink(package_root / relative)

    for relative in sorted(
        (item for item in directories if item), key=lambda item: item.count("/"), reverse=True,
    ):
        directory = package_root / relative
        metadata = os.lstat(directory)
        expected = directories[relative]
        if ((metadata.st_dev, metadata.st_ino) != (expected.st_dev, expected.st_ino)
                or stat.S_IMODE(metadata.st_mode) != 0o700
                or metadata.st_uid != os.geteuid()):
            raise GlobalCliError(f"Refusing to remove changed CLI package directory: {relative}", 4)
        source_edit._lock_identity(lock, lock_identity)
        os.rmdir(directory)

    raw_receipt, receipt_metadata = files[_RECEIPT]
    current_receipt, current_metadata = _safe_read(package_root, _RECEIPT, limit=2_000_000)
    if (current_receipt != raw_receipt or (current_metadata.st_dev, current_metadata.st_ino)
            != (receipt_metadata.st_dev, receipt_metadata.st_ino)):
        raise GlobalCliError("Refusing to remove changed CLI package receipt.", 4)
    source_edit._lock_identity(lock, lock_identity)
    os.unlink(package_root / _RECEIPT)
    root_metadata = os.lstat(package_root)
    if (not stat.S_ISDIR(root_metadata.st_mode) or stat.S_ISLNK(root_metadata.st_mode)
            or root_metadata.st_uid != os.geteuid() or stat.S_IMODE(root_metadata.st_mode) != 0o700
            or (root_metadata.st_dev, root_metadata.st_ino) != root_identity):
        raise GlobalCliError("Refusing to remove a changed CLI package root.", 4)
    source_edit._lock_identity(lock, lock_identity)
    os.rmdir(package_root)


def _unlink_owned(root: Path, relative: str, expected: bytes, mode: int,
                  lock, lock_identity: tuple[int, int]) -> None:
    raw, metadata = _safe_read(root, relative, limit=max(len(expected), 1024))
    if raw != expected or stat.S_IMODE(metadata.st_mode) != mode:
        raise GlobalCliError(f"Refusing to remove changed per-user CLI resource: {relative}", 4)
    source_edit._lock_identity(lock, lock_identity)
    raw_again, metadata_again = _safe_read(root, relative, limit=max(len(expected), 1024))
    if (raw_again != raw or (metadata_again.st_dev, metadata_again.st_ino)
            != (metadata.st_dev, metadata.st_ino)):
        raise GlobalCliError(f"Per-user CLI resource changed before cleanup: {relative}", 4)
    os.unlink(root / relative)


def _unlink_if_present(root: Path, relative: str, expected: bytes, mode: int,
                       lock, lock_identity: tuple[int, int]) -> None:
    try:
        os.lstat(root / relative)
    except FileNotFoundError:
        return
    except OSError as error:
        raise GlobalCliError(f"Cannot inspect per-user CLI cleanup resource {relative}: {error}", 4) from error
    _unlink_owned(root, relative, expected, mode, lock, lock_identity)


def _resume_pending_uninstall(record: _CleanupRecord, data_root: Path, bin_root: Path,
                              global_root: Path, lock,
                              lock_identity: tuple[int, int]) -> CliOutcome:
    identity = InstalledIdentity(
        record.version, record.commit, data_root / "versions" / record.version,
        record.receipt_sha256,
    )
    lifecycle_paths: tuple[str, ...] = ()
    installed_global = _global_identity_without_package()
    if installed_global is not None:
        if installed_global != (record.version, record.commit):
            raise GlobalCliError(
                "A different global Olympus identity blocks pending CLI uninstall cleanup; "
                "preserve the record and reconcile explicitly.", 4,
            )
        local = _read_state(data_root, bin_root, allow_cleanup_pending=True)
        if local != identity or _inspect_cleanup_package(data_root, record) is None:
            raise GlobalCliError("Matching global uninstall cannot resume without the intact recorded CLI package.", 4)
        _require_global(identity.package_root, record.version, record.commit)
        lifecycle = global_install.uninstall(
            identity.package_root, version=record.version, commit=record.commit,
        )
        if _global_identity_without_package() is not None:
            raise GlobalCliError("Global Olympus ownership remains after pending uninstall.", 4)
        lifecycle_paths = lifecycle.changed_paths

    try:
        _inspect_cleanup_package(data_root, record)
        _unlink_if_present(
            bin_root, "olympus", _launcher_bytes(data_root), 0o755, lock, lock_identity,
        )
        _unlink_if_present(
            data_root, _CURRENT,
            _current_bytes(record.version, record.commit, record.receipt_sha256),
            0o600, lock, lock_identity,
        )
        _remove_package(data_root, record, lock, lock_identity)
        if _inspect_cleanup_package(data_root, record) is not None:
            raise GlobalCliError("Recorded CLI package remains after cleanup.", 4)
        _unlink_owned(
            data_root, _CLEANUP_RECORD, _cleanup_record_bytes(record), 0o600,
            lock, lock_identity,
        )
        source_edit._sync_directory(data_root)
    except BaseException as error:
        raise GlobalCliError(
            f"CLI uninstall cleanup remains pending for {record.version}; rerun explicit uninstall "
            f"with the same version/commit and preserve {_CLEANUP_RECORD}: {error}", 4,
        ) from error
    return CliOutcome(
        "uninstall", "committed", record.version, record.commit,
        str(identity.package_root), str(global_root),
        (str(identity.package_root), str(bin_root / "olympus"),
         str(data_root / _CURRENT), str(data_root / _CLEANUP_RECORD), *lifecycle_paths),
        "The recorded global and per-user CLI cleanup completed.",
    )


def _outcome(operation: str, result: str, identity: InstalledIdentity,
             global_root: Path, *, detail: str = "") -> CliOutcome:
    return CliOutcome(
        operation, result, identity.version, identity.commit, str(identity.package_root),
        str(global_root), detail=detail,
    )


def _ensure_current_durable(*, version: str, commit: str) -> InstalledIdentity:
    """Confirm the active package/global pair and durably sync its current marker directory."""
    _require_linux()
    version, commit = _identity(version, commit)
    data_root, bin_root = _user_paths()
    global_root = _configured_global_root()
    _check_path_separation(None, data_root, bin_root, global_root)
    if _ensure_directory(data_root, create=False) is None:
        raise GlobalCliError("No installed per-user Olympus CLI package exists.")

    lock, lock_identity = _acquire_package_lock(data_root, create=False)
    try:
        current = _read_state(data_root, bin_root)
        if current is None:
            raise GlobalCliError("No installed per-user Olympus CLI package exists.")
        if (current.version, current.commit) != (version, commit):
            raise GlobalCliError(
                "Installed per-user CLI version/commit differs from the selected release.",
            )
        data_info = _ensure_directory(data_root, create=False)
        if data_info is None:
            raise GlobalCliError("Per-user CLI data directory disappeared before durable sync.", 4)
        data_root, data_identity = data_info
        _check_path_separation(None, data_root, bin_root, global_root)
        _require_global(current.package_root, current.version, current.commit)
        _sync_directory_strict(data_root, data_identity, lock, lock_identity)
        if _read_state(data_root, bin_root) != current:
            raise GlobalCliError("Per-user CLI identity changed during current-marker durable sync.", 4)
        return current
    finally:
        _release_package_lock(lock)


def _update_recovery_identity(*, force: bool = False) -> InstalledIdentity | None:
    """Read-only recognition of an exact package/global split from an interrupted update."""
    _require_linux()
    data_root, bin_root = _user_paths()
    global_root = _configured_global_root()
    _check_path_separation(None, data_root, bin_root, global_root)
    if _ensure_directory(data_root, create=False) is None:
        _read_state(data_root, bin_root)
        return None

    lock, _ = _acquire_package_lock(data_root, create=False)
    try:
        current = _read_state(data_root, bin_root, allow_managed_drift=force)
        if current is None:
            return None
        if current.package_root != data_root / "versions" / current.version:
            raise GlobalCliError("Verified CLI package is not the exact installed version directory.")

        installed = _global_identity_without_package()
        if installed is None or installed == (current.version, current.commit):
            return None
        comparison = global_install._version_compare(installed[0], current.version)
        if comparison is None or comparison <= 0:
            raise GlobalCliError(
                "The split global identity is not a strictly newer recoverable update.", 4,
            )

        target = (
            _validate_force_package(
                data_root / "versions" / installed[0],
                version=installed[0], commit=installed[1],
            )
            if force else _validate_package(
                data_root / "versions" / installed[0],
                version=installed[0], commit=installed[1],
            )
        )
        if not force:
            _require_global(target.package_root, target.version, target.commit)
        if _read_state(data_root, bin_root) != current:
            raise GlobalCliError("Per-user CLI identity changed during update recovery inspection.", 4)
        return target
    finally:
        _release_package_lock(lock)


def _force_update_identity() -> InstalledIdentity | None:
    """Read the current identity from its marker and exact package receipt, allowing managed drift."""
    _require_linux()
    data_root, bin_root = _user_paths()
    global_root = _configured_global_root()
    _check_path_separation(None, data_root, bin_root, global_root)
    if _ensure_directory(data_root, create=False) is None:
        current = _read_state(data_root, bin_root, allow_managed_drift=True)
        if current is None and _global_identity_without_package() is not None:
            raise GlobalCliError("A global Olympus installation exists without its matching CLI package.")
        return None
    lock, _ = _acquire_package_lock(data_root, create=False)
    try:
        current = _read_state(data_root, bin_root, allow_managed_drift=True)
        if current is None:
            if _global_identity_without_package() is not None:
                raise GlobalCliError("A global Olympus installation exists without its matching CLI package.")
            return None
        if current.package_root != data_root / "versions" / current.version:
            raise GlobalCliError("Verified CLI package is not the exact installed version directory.")
        if _global_identity_without_package() != (current.version, current.commit):
            raise GlobalCliError("Global OpenCode identity differs from the receipt-bound CLI identity.")
        if _read_state(data_root, bin_root, allow_managed_drift=True) != current:
            raise GlobalCliError("Per-user CLI identity changed during force-update preflight.", 4)
        return current
    finally:
        _release_package_lock(lock)


def recorded_identity() -> InstalledIdentity | None:
    """Return the verified local/global version+commit pair without creating paths."""
    _require_linux()
    data_root, bin_root = _user_paths()
    global_root = _configured_global_root()
    _check_path_separation(None, data_root, bin_root, global_root)
    before = _read_state(data_root, bin_root)
    if before is None:
        if _global_identity_without_package() is not None:
            raise GlobalCliError("A global Olympus installation exists without its matching CLI package.")
        return None
    lock, _ = _acquire_package_lock(data_root, create=False)
    try:
        current = _read_state(data_root, bin_root)
        if current is None or current != before:
            raise GlobalCliError("Per-user CLI identity changed while it was being read.", 4)
        if current.package_root != data_root / "versions" / current.version:
            raise GlobalCliError("Verified CLI package is not the exact installed version directory.", 4)
        _check_path_separation(None, data_root, bin_root, global_root)
        _require_global(current.package_root, current.version, current.commit)
        return current
    finally:
        _release_package_lock(lock)


def verify(*, version: str, commit: str) -> CliOutcome:
    """Read-only verification of launcher, current/package receipt, and global marker."""
    _require_linux()
    version, commit = _identity(version, commit)
    identity = recorded_identity()
    if identity is None:
        raise GlobalCliError("No installed per-user Olympus CLI package exists.")
    if (identity.version, identity.commit) != (version, commit):
        raise GlobalCliError("Installed per-user CLI version/commit differs from the requested identity.")
    data_root, bin_root = _user_paths()
    global_root, _ = _require_global(identity.package_root, version, commit)
    return _outcome("verify", "verified", identity, global_root)


def install(source: Path, *, version: str, commit: str) -> CliOutcome:
    """Stage, install, then activate a fresh per-user Linux CLI package."""
    _require_linux()
    version, commit = _identity(version, commit)
    source, payload, source_identity = _validated_source(source, version, commit)
    data_root, bin_root = _user_paths()
    global_root = _configured_global_root()
    _check_path_separation(source, data_root, bin_root, global_root)
    if (source_edit._safe_root_metadata(source).st_dev,
            source_edit._safe_root_metadata(source).st_ino) != source_identity:
        raise GlobalCliError("Staged source root identity changed before installation.", 4)
    existing = _read_state(data_root, bin_root)
    if existing is not None:
        lock, _ = _acquire_package_lock(data_root, create=False)
        try:
            current = _read_state(data_root, bin_root)
            if current != existing:
                raise GlobalCliError("Per-user CLI package changed during install preflight.", 4)
            if (current.version, current.commit) != (version, commit):
                raise GlobalCliError("A per-user CLI package already exists; use update for a newer source.")
            if not _payload_matches_package(payload, current):
                raise GlobalCliError("Same-version CLI source differs from the installed package; refusing repair.")
            _require_global(current.package_root, version, commit)
            return _outcome("install", "no_changes", current, global_root)
        finally:
            _release_package_lock(lock)

    data_info = _ensure_directory(data_root, create=True)
    bin_info = _ensure_directory(bin_root, create=True)
    if data_info is None or bin_info is None:
        raise GlobalCliError("Cannot establish per-user CLI package directories.", 4)
    data_root, data_identity = data_info
    bin_root, bin_identity = bin_info
    lock, lock_identity = _acquire_package_lock(data_root, create=True)
    try:
        current = _read_state(data_root, bin_root)
        if current is not None:
            if (current.version, current.commit) == (version, commit):
                _require_global(current.package_root, version, commit)
                return _outcome("install", "no_changes", current, global_root)
            raise GlobalCliError("A per-user CLI package appeared during install preflight; use update.")
        versions_info = _ensure_directory(data_root / "versions", create=True)
        if versions_info is None:
            raise GlobalCliError("Cannot create the per-user versioned package directory.", 4)
        versions_root, versions_identity = versions_info
        return _stage_and_transition(
            source, version, commit, "install", payload, data_root, data_identity,
            versions_root, versions_identity, bin_root, bin_identity,
            lock, lock_identity, None,
        )
    finally:
        _release_package_lock(lock)


def update(source: Path, *, version: str, commit: str, force: bool = False) -> CliOutcome:
    """Stage a newer release, or explicitly restore only receipted managed resources."""
    _require_linux()
    version, commit = _identity(version, commit)
    source, payload, source_identity = _validated_source(source, version, commit)
    data_root, bin_root = _user_paths()
    global_root = _configured_global_root()
    _check_path_separation(source, data_root, bin_root, global_root)
    if (source_edit._safe_root_metadata(source).st_dev,
            source_edit._safe_root_metadata(source).st_ino) != source_identity:
        raise GlobalCliError("Staged source root identity changed before update.", 4)
    existing = _read_state(data_root, bin_root, allow_managed_drift=force)
    if existing is None:
        raise GlobalCliError("Update requires an existing verified per-user CLI package.")
    lock, lock_identity = _acquire_package_lock(data_root, create=False)
    try:
        previous = _read_state(data_root, bin_root, allow_managed_drift=force)
        if previous is None or previous != existing:
            raise GlobalCliError("Per-user CLI package changed during update preflight.", 4)
        data_info = _ensure_directory(data_root, create=False)
        bin_info = _ensure_directory(bin_root, create=False)
        if data_info is None or bin_info is None:
            raise GlobalCliError("Per-user CLI directories disappeared during update preflight.", 4)
        data_root, data_identity = data_info
        bin_root, bin_identity = bin_info
        _check_path_separation(source, data_root, bin_root, global_root)
        if (version, commit) == (previous.version, previous.commit):
            if force:
                if not _payload_matches_package(payload, previous):
                    raise GlobalCliError(
                        "Same-version CLI source differs from its installed package receipt; refusing repair."
                    )
                if _global_identity_without_package() != (version, commit):
                    raise GlobalCliError(
                        "Same-version force repair requires the exact global manifest identity."
                    )
                global_install._preflight_force_update(
                    source, version=version, commit=commit,
                )
                _preflight_force_cli_update(
                    data_root, data_identity, bin_root, bin_identity, previous,
                    version=version, commit=commit,
                    payload=payload,
                )
                lifecycle = global_install.update(
                    source, version=version, commit=commit, force=True,
                )
                package_changed = _repair_package_files(
                    previous.package_root, payload, version=version, commit=commit,
                    receipt_sha256=previous.receipt_sha256,
                    lock=lock, lock_identity=lock_identity,
                )
                launcher_changed = _repair_stable_launcher(
                    data_root, bin_root, bin_identity, lock, lock_identity,
                )
                repaired = _read_state(data_root, bin_root)
                if repaired is None or (repaired.version, repaired.commit) != (version, commit):
                    raise GlobalCliError("Force-repaired CLI package identity did not verify.", 4)
                global_root, _ = _require_global(repaired.package_root, version, commit)
                _sync_directory_strict(data_root, data_identity, lock, lock_identity)
                changed = [
                    *(str(previous.package_root / relative) for relative in package_changed),
                    *((str(bin_root / "olympus"),) if launcher_changed else ()),
                    *lifecycle.changed_paths,
                ]
                return CliOutcome(
                    "update", "committed" if changed else "no_changes", version, commit,
                    str(repaired.package_root), str(global_root), tuple(changed),
                    "Receipt-owned package, launcher, global resources, and identities verified.",
                )
            if not _payload_matches_package(payload, previous):
                raise GlobalCliError("Same-version CLI source differs from the installed package; refusing repair.")
            _require_global(previous.package_root, version, commit)
            _sync_directory_strict(data_root, data_identity, lock, lock_identity)
            return _outcome("update", "no_changes", previous, global_root)
        comparison = global_install._version_compare(version, previous.version)
        if comparison is None or comparison <= 0:
            raise GlobalCliError("CLI update must be a strictly newer supported release.")
        versions_info = _ensure_directory(data_root / "versions", create=False)
        if versions_info is None:
            raise GlobalCliError("Versioned CLI package directory is missing.")
        versions_root, versions_identity = versions_info
        if force:
            global_install._preflight_force_update(
                source, version=version, commit=commit,
            )
            _preflight_force_cli_update(
                data_root, data_identity, bin_root, bin_identity, previous,
                version=version, commit=commit,
                payload=payload,
            )
        return _stage_and_transition(
            source, version, commit, "update", payload, data_root, data_identity,
            versions_root, versions_identity, bin_root, bin_identity,
            lock, lock_identity, previous, force=force,
        )
    finally:
        _release_package_lock(lock)


def _uninstall_identity(version: str | None, commit: str | None, *, current_only: bool) -> CliOutcome:
    _require_linux()
    if current_only:
        if version is not None or commit is not None:
            raise GlobalCliError("Internal current-package uninstall does not accept a supplied identity.")
        requested = None
    else:
        version, commit = _identity(version, commit)
        requested = (version, commit)
    data_root, bin_root = _user_paths()
    global_root = _configured_global_root()
    _check_path_separation(None, data_root, bin_root, global_root)
    data_info = _ensure_directory(data_root, create=False)
    if data_info is None:
        _read_state(data_root, bin_root)
        if _global_identity_without_package() is not None:
            raise GlobalCliError("Cannot uninstall a global installation without its matching CLI package.")
        return CliOutcome(
            "uninstall", "no_changes", version or "", commit or "", "", str(global_root),
        )
    data_root, _ = data_info
    if _read_cleanup_record(data_root) is None:
        existing = _read_state(data_root, bin_root)
        if existing is None:
            if _global_identity_without_package() is not None:
                raise GlobalCliError("Cannot uninstall a global installation without its matching CLI package.")
            return CliOutcome(
                "uninstall", "no_changes", version or "", commit or "", "", str(global_root),
            )
    lock, lock_identity = _acquire_package_lock(data_root, create=False)
    try:
        pending = _read_cleanup_record(data_root)
        if pending is not None:
            if requested is not None and (pending.version, pending.commit) != requested:
                raise GlobalCliError(
                    "Requested uninstall identity differs from the pending package/receipt cleanup record.", 4,
                )
            return _resume_pending_uninstall(
                pending, data_root, bin_root, global_root, lock, lock_identity,
            )

        identity = _read_state(data_root, bin_root)
        if identity is None:
            if _global_identity_without_package() is not None:
                raise GlobalCliError("Cannot uninstall a global installation without its matching CLI package.")
            return CliOutcome(
                "uninstall", "no_changes", version or "", commit or "", "", str(global_root),
            )
        if requested is not None and (identity.version, identity.commit) != requested:
            raise GlobalCliError("Requested uninstall version/commit does not match the installed package.")
        global_root, _ = _require_global(
            identity.package_root, identity.version, identity.commit,
        )
        record = _create_cleanup_record(data_root, identity, lock, lock_identity)
        return _resume_pending_uninstall(
            record, data_root, bin_root, global_root, lock, lock_identity,
        )
    finally:
        _release_package_lock(lock)


def uninstall(*, version: str, commit: str) -> CliOutcome:
    """Uninstall or explicitly resume cleanup of one exact per-user CLI package."""
    return _uninstall_identity(version, commit, current_only=False)


def _uninstall_current() -> CliOutcome:
    """Uninstall only the package identity read under the per-user package lock."""
    return _uninstall_identity(None, None, current_only=True)


__all__ = [
    "CliOutcome", "GlobalCliError", "InstalledIdentity",
    "install", "recorded_identity", "uninstall", "update", "verify",
]
