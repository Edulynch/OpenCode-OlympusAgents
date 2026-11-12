"""Recoverable project-target transaction for explicit config apply."""

from __future__ import annotations

import hashlib
import base64
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import source_edit
from .install_manifest import MANIFEST_PATHS, ManifestError, parse_project_manifest


_SCRATCH = ".olympus-cli-config-apply"
_RECORD = "record.json"
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_HASH = re.compile(r"[0-9a-f]{64}")


class TransactionError(RuntimeError):
    def __init__(self, message: str, code: int = 3):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Change:
    path: str
    old: bytes
    new: bytes
    mode: int


@dataclass(frozen=True, slots=True)
class GlobalChange:
    path: str
    old: bytes | None
    new: bytes
    mode: int
    manifest: bool = False


def pending(target: Path) -> bool:
    for name in (_SCRATCH, source_edit._SCRATCH_NAME):
        try:
            os.lstat(target / name)
        except FileNotFoundError:
            continue
        except OSError:
            return True
        return True
    return False


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_record(record: dict[str, Any]) -> bytes:
    return (json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _read(root: Path, relative: str) -> tuple[bytes, os.stat_result]:
    try:
        return source_edit._safe_read(root, relative)
    except source_edit.BatchError as error:
        raise TransactionError(str(error), 3) from error


def _bounded_read(root: Path, relative: str, limit: int) -> tuple[bytes, os.stat_result]:
    from .config_apply import _lstat_target_path, _read_target_file

    path, before, issue = _lstat_target_path(root, relative)
    if issue or before is None or path is None:
        raise TransactionError(issue or f"Missing transaction resource: {relative}", 4)
    if before.st_size > limit:
        raise TransactionError(f"Project-apply resource exceeds the safety limit: {relative}", 4)
    raw, issue = _read_target_file(root, relative, max_bytes=limit)
    if issue or raw is None or len(raw) > limit:
        raise TransactionError(issue or f"Project-apply resource exceeds the safety limit: {relative}", 4)
    _, after, issue = _lstat_target_path(root, relative)
    if issue or after is None or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        raise TransactionError(issue or f"Project-apply resource changed while reading: {relative}", 4)
    return raw, after


def _artifact(root: Path, relative: str, digest: str, mode: int, *, required: bool) -> tuple[bytes, os.stat_result] | None:
    try:
        os.lstat(root / relative)
    except FileNotFoundError:
        if required:
            raise TransactionError(f"Required project-apply evidence is missing: {relative}", 4)
        return None
    except OSError as error:
        raise TransactionError(f"Cannot inspect project-apply evidence {relative}: {error}", 4) from error
    raw, metadata = _read(root, relative)
    if _hash(raw) != digest or stat.S_IMODE(metadata.st_mode) != mode:
        raise TransactionError(f"Project-apply evidence changed or is corrupt: {relative}", 4)
    return raw, metadata


def _safe_remove(root: Path, relative: str, raw: bytes, mode: int, lock, identity) -> None:
    saved, metadata = _read(root, relative)
    if saved != raw or stat.S_IMODE(metadata.st_mode) != mode:
        raise TransactionError(f"Refusing to remove changed project-apply evidence: {relative}", 4)
    source_edit._lock_identity(lock, identity)
    current, current_metadata = _read(root, relative)
    if (current != saved or (current_metadata.st_dev, current_metadata.st_ino)
            != (metadata.st_dev, metadata.st_ino)):
        raise TransactionError(f"Project-apply evidence changed before cleanup: {relative}", 4)
    try:
        os.unlink(root / relative)
    except OSError as error:
        raise TransactionError(f"Cannot remove verified project-apply evidence {relative}: {error}", 4) from error


def _manifest_bytes(target: Path, record: dict[str, Any], file_map: dict[str, dict[str, Any]], states: dict[str, str], *,
                    state: str) -> tuple[bytes, bytes]:
    relative = record["manifest_path"]
    entry = file_map[relative]
    current, _ = _read(target, relative)
    current_hash = _hash(current)
    if current_hash not in (entry["old_sha256"], entry["new_sha256"]):
        raise TransactionError("Project manifest is neither the recorded old nor new state", 4)
    if state == "PREPARING" and current_hash != entry["old_sha256"]:
        raise TransactionError("PREPARING project apply unexpectedly changed its manifest", 4)
    try:
        old_raw = base64.b64decode(record["manifest_old_b64"], validate=True)
        new_raw = base64.b64decode(record["manifest_new_b64"], validate=True)
    except (KeyError, ValueError, TypeError) as error:
        raise TransactionError("Project-apply manifest receipt is invalid", 4) from error
    if len(old_raw) > 2_000_000 or len(new_raw) > 2_000_000:
        raise TransactionError("Project-apply manifest receipt exceeds the safety limit", 4)
    if _hash(old_raw) != entry["old_sha256"] or _hash(new_raw) != entry["new_sha256"]:
        raise TransactionError("Project-apply manifest receipt hashes contradict its record", 4)
    return old_raw, new_raw


def _parse_manifest(target: Path, relative: str, raw: bytes):
    try:
        return parse_project_manifest(target, target / relative, raw)
    except ManifestError as error:
        raise TransactionError(f"Project-apply manifest evidence is invalid: {error}", 4) from error


def _ensure_scratch_identity(target: Path, record: dict[str, Any]) -> os.stat_result:
    try:
        metadata = os.lstat(target / _SCRATCH)
    except OSError as error:
        raise TransactionError("Project-apply scratch disappeared", 4) from error
    expected = record["scratch_identity"]
    if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
            or (metadata.st_dev, metadata.st_ino) != (expected["st_dev"], expected["st_ino"])):
        raise TransactionError("Project-apply scratch identity changed or is unsafe", 4)
    return metadata


def _validate_record(target: Path, record: Any, lock_identity: tuple[int, int]) -> tuple[dict[str, dict], dict[str, dict]]:
    if not isinstance(record, dict) or set(record) != {
        "schema_version", "operation_id", "target_root", "scratch_identity", "lock_identity",
        "state", "manifest_path", "manifest_old_b64", "manifest_new_b64", "files",
    }:
        raise TransactionError("Project-apply record has missing or unexpected fields", 4)
    if (type(record["schema_version"]) is not int or record["schema_version"] != 1
            or not isinstance(record["operation_id"], str)
            or re.fullmatch(r"[0-9a-f]{32}", record["operation_id"]) is None
            or record["target_root"] != str(target)
            or record["state"] not in ("PREPARING", "PREPARED", "COMMITTED")):
        raise TransactionError("Project-apply record identity or state is invalid", 4)
    lock_record = record["lock_identity"]
    if (not isinstance(lock_record, dict) or set(lock_record) != {"path", "st_dev", "st_ino"}
            or lock_record["path"] != source_edit._LOCK_NAME
            or type(lock_record["st_dev"]) is not int or type(lock_record["st_ino"]) is not int
            or (lock_record["st_dev"], lock_record["st_ino"]) != lock_identity):
        raise TransactionError("Project-apply record does not match the acquired stable target lock", 4)
    scratch_identity = record["scratch_identity"]
    if (not isinstance(scratch_identity, dict) or set(scratch_identity) != {"st_dev", "st_ino"}
            or type(scratch_identity["st_dev"]) is not int or type(scratch_identity["st_ino"]) is not int):
        raise TransactionError("Project-apply scratch identity is invalid", 4)
    _ensure_scratch_identity(target, record)

    manifest_path = record["manifest_path"]
    if manifest_path not in MANIFEST_PATHS:
        raise TransactionError("Project-apply record names an unsupported manifest path", 4)
    files = record["files"]
    if not isinstance(files, list) or not files:
        raise TransactionError("Project-apply record has no file inventory", 4)
    file_map: dict[str, dict] = {}
    previous = None
    for index, entry in enumerate(files):
        if not isinstance(entry, dict) or set(entry) != {
            "path", "old_sha256", "new_sha256", "mode", "backup", "staged",
        }:
            raise TransactionError("Project-apply record has an invalid file entry", 4)
        relative = entry["path"]
        try:
            source_edit._relative_parts(relative)
        except source_edit.BatchError as error:
            raise TransactionError(f"Project-apply record has an unsafe target path: {relative!r}", 4) from error
        if (not isinstance(relative, str) or (index < len(files) - 1 and relative <= (previous or ""))
                or (relative != manifest_path and not (
                    relative == "CODEX.md" or relative == "opencode.jsonc"
                    or relative.startswith(".opencode/") or relative.startswith(".codex/")
                ))):
            raise TransactionError("Project-apply file inventory is duplicated, unordered, or outside managed surfaces", 4)
        if index < len(files) - 1:
            previous = relative
        if (not isinstance(entry["old_sha256"], str) or _HASH.fullmatch(entry["old_sha256"]) is None
                or not isinstance(entry["new_sha256"], str) or _HASH.fullmatch(entry["new_sha256"]) is None
                or entry["old_sha256"] == entry["new_sha256"]
                or type(entry["mode"]) is not int or not 0 <= entry["mode"] <= 0o7777
                or entry["backup"] != f"backups/file-{index:04d}.old"
                or entry["staged"] != f"staged/file-{index:04d}.new"):
            raise TransactionError(f"Project-apply record metadata is invalid for {relative}", 4)
        file_map[relative] = entry
    if manifest_path not in file_map or files[-1]["path"] != manifest_path:
        raise TransactionError("Project-apply manifest must be the final transaction target", 4)
    return {}, file_map


def _record_context(target: Path, lock) -> tuple[dict[str, Any], bytes, os.stat_result] | None:
    identity = source_edit._lock_identity(lock)
    scratch = target / _SCRATCH
    try:
        scratch_metadata = os.lstat(scratch)
    except FileNotFoundError:
        return None
    if (not stat.S_ISDIR(scratch_metadata.st_mode) or stat.S_ISLNK(scratch_metadata.st_mode)
            or getattr(scratch_metadata, "st_file_attributes", 0) & _REPARSE_POINT):
        raise TransactionError("Project-apply scratch is a link/reparse point or not a directory", 4)
    try:
        top = set(os.listdir(scratch))
    except OSError as error:
        raise TransactionError(f"Cannot enumerate project-apply scratch: {error}", 4) from error
    if _RECORD not in top:
        if top <= {"backups", "staged"}:
            for name in top:
                path = scratch / name
                metadata = os.lstat(path)
                if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
                        or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT):
                    raise TransactionError("Unrecorded project-apply scratch is not safely empty", 4)
                if os.listdir(path):
                    raise TransactionError("Unrecorded project-apply scratch contains evidence", 4)
            for name in top:
                os.rmdir(scratch / name)
            os.rmdir(scratch)
            source_edit._sync_directory(target)
            return None
        raise TransactionError("Project-apply scratch has no authoritative record; evidence was preserved", 4)
    try:
        record_info = os.lstat(scratch / _RECORD)
        if record_info.st_size > 6_000_000:
            raise TransactionError("Project-apply record exceeds the safety limit; evidence was preserved", 4)
        raw, metadata = _bounded_read(target, f"{_SCRATCH}/{_RECORD}", 6_000_000)
        record = json.loads(raw.decode("utf-8"))
    except TransactionError:
        raise
    except (UnicodeError, ValueError, OSError) as error:
        raise TransactionError("Project-apply record is incomplete or invalid; evidence was preserved", 4) from error
    _validate_record(target, record, identity)
    if raw != _canonical_record(record):
        raise TransactionError("Project-apply record is not in canonical persisted form", 4)
    return record, raw, metadata


def _manifest_maps(target: Path, record: dict, file_map: dict[str, dict], states: dict[str, str], source: Path,
                   renderer) -> tuple[Any, Any, dict[str, str], dict[str, str]]:
    old_raw, new_raw = _manifest_bytes(target, record, file_map, states, state=record["state"])
    old_manifest = _parse_manifest(target, record["manifest_path"], old_raw)
    if old_manifest.relative_path != record["manifest_path"]:
        raise TransactionError("Old manifest location contradicts the project-apply record", 4)
    old_harnesses = old_manifest.installed_harnesses
    try:
        from .config_apply import _render_managed_outputs
        by_harness = _render_managed_outputs(source, renderer, old_harnesses)
    except TransactionError:
        raise
    except Exception as error:
        raise TransactionError(f"Cannot validate current renderer inventory for project recovery: {error}", 4) from error
    expected = {path for resources in by_harness.values() for path in resources}

    def manifest_entries(manifest, description: str) -> dict[str, str]:
        entries: dict[str, str] = {}
        for item in manifest.data["managed_files"]:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise TransactionError(f"{description} manifest inventory is invalid", 4)
            path = item["path"].replace("\\", "/")
            digest = item.get("sha256")
            if path in entries or not isinstance(digest, str) or _HASH.fullmatch(digest.lower()) is None:
                raise TransactionError(f"{description} manifest inventory is duplicated or invalid", 4)
            entries[path] = digest.lower()
        if set(entries) != expected:
            raise TransactionError(f"{description} manifest inventory differs from the current renderer", 4)
        return entries

    old_entries = manifest_entries(old_manifest, "Old")
    new_manifest = _parse_manifest(target, record["manifest_path"], new_raw)
    if new_manifest.relative_path != record["manifest_path"] or new_manifest.installed_harnesses != old_harnesses:
        raise TransactionError("New manifest changes project ownership or harness inventory", 4)
    new_entries = manifest_entries(new_manifest, "New")
    rendered_hashes = {path: _hash(content) for resources in by_harness.values()
                       for path, content in resources.items()}
    for relative in expected:
        if (old_entries[relative] != new_entries[relative]
                and new_entries[relative] != rendered_hashes[relative]):
            raise TransactionError(f"Updated manifest hash is not the current renderer output: {relative}", 4)
    for relative, entry in file_map.items():
        if relative == record["manifest_path"]:
            if entry["old_sha256"] != _hash(old_raw) or entry["new_sha256"] != _hash(new_raw):
                raise TransactionError("Project-apply manifest hashes contradict its record", 4)
        elif old_entries.get(relative) != entry["old_sha256"] or new_entries.get(relative) != entry["new_sha256"]:
            raise TransactionError(f"Project-apply hashes contradict manifest ownership: {relative}", 4)
    for relative in expected - set(file_map):
        if old_entries[relative] != new_entries[relative]:
            raise TransactionError(f"Unrecorded managed hash changed in project manifest: {relative}", 4)

    for relative in expected:
        raw, _ = _read(target, relative)
        digest = _hash(raw)
        if relative in file_map:
            state = states.get(relative)
            expected_digest = old_entries[relative] if state in (None, "old") else new_entries[relative]
        else:
            expected_digest = old_entries[relative]
        if digest != expected_digest:
            raise TransactionError(f"Managed project resource is neither its recorded old nor new state: {relative}", 4)
    return old_manifest, new_manifest, old_entries, new_entries


def _scratch_artifacts(target: Path, record: dict, file_map: dict[str, dict], *, require_backups: set[str] | None = None,
                       require_staged: set[str] | None = None) -> dict[str, tuple[bytes, os.stat_result]]:
    _ensure_scratch_identity(target, record)
    scratch = target / _SCRATCH
    top = set(os.listdir(scratch))
    allowed_top = {_RECORD, ".record.json.tmp", "backups", "staged"}
    if top - allowed_top or _RECORD not in top:
        raise TransactionError("Project-apply scratch contains unenumerated resources", 4)
    expected_backups = {entry["backup"].split("/", 1)[1] for entry in file_map.values()}
    expected_staged = {entry["staged"].split("/", 1)[1] for entry in file_map.values()}
    expected_rollback = {f"rollback-file-{index:04d}.old" for index in range(len(file_map))}
    for directory, allowed in (("backups", expected_backups), ("staged", expected_staged | expected_rollback)):
        if directory in top:
            source_edit._checked_path(target, f"{_SCRATCH}/{directory}", kind="directory")
            names = set(os.listdir(scratch / directory))
            if names - allowed:
                raise TransactionError(f"Project-apply {directory} directory has unenumerated resources", 4)
    artifacts: dict[str, tuple[bytes, os.stat_result]] = {}
    if ".record.json.tmp" in top:
        temp, metadata = _bounded_read(target, f"{_SCRATCH}/.record.json.tmp", 6_000_000)
        try:
            temporary_record = json.loads(temp.decode("utf-8"))
        except (UnicodeError, ValueError) as error:
            raise TransactionError("Temporary project-apply record is invalid; evidence was preserved", 4) from error
        if (temp != _canonical_record(temporary_record)
                or temporary_record.get("operation_id") != record["operation_id"]
                or temporary_record.get("state") not in ("PREPARING", "PREPARED", "COMMITTED")):
            raise TransactionError("Temporary project-apply record belongs to another operation", 4)
        artifacts[f"{_SCRATCH}/.record.json.tmp"] = (temp, metadata)
    for index, (relative, entry) in enumerate(file_map.items()):
        for artifact_relative, digest, required in (
            (f"{_SCRATCH}/{entry['backup']}", entry["old_sha256"], relative in (require_backups or set())),
            (f"{_SCRATCH}/{entry['staged']}", entry["new_sha256"], relative in (require_staged or set())),
            (f"{_SCRATCH}/staged/rollback-file-{index:04d}.old", entry["old_sha256"], False),
        ):
            value = _artifact(target, artifact_relative, digest, entry["mode"], required=required)
            if value is not None:
                artifacts[artifact_relative] = value
    return artifacts


def _inspect(target: Path, source: Path, lock, record: dict, record_raw: bytes, record_metadata: os.stat_result,
             *, expected_states: dict[str, str] | None = None, require_backups: set[str] | None = None,
             require_staged: set[str] | None = None):
    identity = source_edit._lock_identity(lock)
    _, file_map = _validate_record(target, record, identity)
    raw, metadata = _read(target, f"{_SCRATCH}/{_RECORD}")
    if (raw != record_raw or (metadata.st_dev, metadata.st_ino) != (record_metadata.st_dev, record_metadata.st_ino)):
        raise TransactionError("Authoritative project-apply record changed", 4)
    states: dict[str, str] = {}
    for relative, entry in file_map.items():
        current, current_metadata = _read(target, relative)
        digest = _hash(current)
        if stat.S_IMODE(current_metadata.st_mode) != entry["mode"]:
            raise TransactionError(f"Project-apply target mode changed: {relative}", 4)
        if digest == entry["old_sha256"]:
            state = "old"
        elif digest == entry["new_sha256"]:
            state = "new"
        else:
            raise TransactionError(f"Project-apply target has an external third-state change: {relative}", 4)
        if expected_states is not None and expected_states.get(relative) != state:
            raise TransactionError(f"Project-apply target changed unexpectedly: {relative}", 4)
        states[relative] = state
    renderer = None
    try:
        from .cli import load_renderer
        renderer = load_renderer(source)
    except Exception as error:
        raise TransactionError(f"Cannot load source renderer for project recovery: {error}", 4) from error
    manifests = _manifest_maps(target, record, file_map, states, source, renderer)
    artifacts = _scratch_artifacts(target, record, file_map,
                                   require_backups=require_backups, require_staged=require_staged)
    return {"identity": identity, "file_map": file_map, "states": states,
            "manifests": manifests, "artifacts": artifacts}


def _persist_record(target: Path, scratch: Path, record: dict, lock, identity,
                    *, previous: tuple[dict, bytes, os.stat_result] | None = None):
    relative_tmp = f"{_SCRATCH}/.record.json.tmp"
    temporary = scratch / ".record.json.tmp"
    payload = _canonical_record(record)
    record_mode = 0o666 if os.name == "nt" else 0o600
    source_edit._write_private_file(temporary, target, relative_tmp, payload, record_mode, lock, identity)
    if previous is None:
        record_relative = f"{_SCRATCH}/{_RECORD}"
        try:
            os.lstat(target / record_relative)
        except FileNotFoundError:
            pass
        else:
            raise TransactionError("Project-apply record path unexpectedly exists", 4)
    else:
        old_record, old_raw, old_metadata = previous
        current_raw, current_metadata = _read(target, f"{_SCRATCH}/{_RECORD}")
        if (current_raw != old_raw or (current_metadata.st_dev, current_metadata.st_ino)
                != (old_metadata.st_dev, old_metadata.st_ino)):
            raise TransactionError("Project-apply record changed before state transition", 4)
    source_edit._lock_identity(lock, identity)
    try:
        os.replace(temporary, target / f"{_SCRATCH}/{_RECORD}")
    except OSError as error:
        raise TransactionError(f"Cannot persist project-apply {record['state']} record: {error}", 4) from error
    source_edit._sync_directory(scratch)
    written, metadata = _read(target, f"{_SCRATCH}/{_RECORD}")
    if written != payload:
        raise TransactionError(f"Persisted project-apply {record['state']} record failed verification", 4)
    return record, written, metadata


def _write_record_new(target: Path, record: dict, lock, identity):
    scratch = target / _SCRATCH
    source_edit._make_directory(scratch, target, lock, identity)
    scratch_stat = os.lstat(scratch)
    record["scratch_identity"] = {"st_dev": scratch_stat.st_dev, "st_ino": scratch_stat.st_ino}
    source_edit._sync_directory(target)
    return _persist_record(target, scratch, record, lock, identity)


def _validate_plan(target: Path, changes: tuple[Change, ...], manifest_path: str) -> None:
    if not changes or changes[-1].path != manifest_path:
        raise TransactionError("Project-apply requires a manifest-last nonempty write set", 3)
    previous = ""
    for item in changes[:-1]:
        if item.path <= previous or item.path in MANIFEST_PATHS:
            raise TransactionError("Project-apply write set is duplicated or unordered", 3)
        previous = item.path
    if len({item.path for item in changes}) != len(changes):
        raise TransactionError("Project-apply write set contains duplicate paths", 3)
    for item in changes:
        if not 0 <= item.mode <= 0o7777 or item.old == item.new:
            raise TransactionError(f"Invalid project-apply candidate for {item.path}", 3)
        raw, metadata = _read(target, item.path)
        if raw != item.old or stat.S_IMODE(metadata.st_mode) != item.mode:
            raise TransactionError(f"Project target changed before transaction preparation: {item.path}", 3)


def commit(target: Path, source: Path, changes: tuple[Change, ...], manifest_path: str,
           manifest_old: bytes, manifest_new: bytes, revalidate) -> str:
    """Apply a validated project plan while holding the shared target-writer lock."""
    _validate_plan(target, changes, manifest_path)
    try:
        lock = source_edit._acquire_lock(target, create=True)
    except source_edit.LockError as error:
        raise TransactionError(f"Cannot acquire the stable target writer lock: {error}",
                               4 if isinstance(error, source_edit.LockIdentityError) else 3) from error
    try:
        lock_identity = source_edit._lock_identity(lock)
        if pending(target):
            raise TransactionError("A project-apply or source-edit journal exists; explicitly recover that journal before applying.", 3)
        changes, manifest_old, manifest_new = revalidate()
        if not changes:
            return "no_changes"
        _validate_plan(target, changes, manifest_path)
        if changes[-1].old != manifest_old or changes[-1].new != manifest_new:
            raise TransactionError("Manifest plan changed during locked revalidation", 3)
        files = [{"path": item.path, "old_sha256": _hash(item.old), "new_sha256": _hash(item.new),
                  "mode": item.mode, "backup": f"backups/file-{index:04d}.old",
                  "staged": f"staged/file-{index:04d}.new"}
                 for index, item in enumerate(changes)]
        record = {
            "schema_version": 1,
            "operation_id": uuid.uuid4().hex,
            "target_root": str(target),
            "scratch_identity": {"st_dev": 0, "st_ino": 0},
            "lock_identity": {"path": source_edit._LOCK_NAME, "st_dev": lock_identity[0], "st_ino": lock_identity[1]},
            "state": "PREPARING",
            "manifest_path": manifest_path,
            "manifest_old_b64": base64.b64encode(manifest_old).decode("ascii"),
            "manifest_new_b64": base64.b64encode(manifest_new).decode("ascii"),
            "files": files,
        }
        record, record_raw, record_metadata = _write_record_new(target, record, lock, lock_identity)
        return _commit_cycle(target, source, lock, record, record_raw, record_metadata, changes, files)
    finally:
        try:
            source_edit._release_lock(lock)
        except source_edit.LockError as error:
            raise TransactionError(f"Target lock identity became unconfirmed during project apply: {error}", 4) from error


def recover(target: Path, source: Path) -> str:
    """Explicitly roll back one PREPARED project batch or clean a COMMITTED one."""
    try:
        lock = source_edit._acquire_lock(target, create=False)
    except source_edit.LockError as error:
        raise TransactionError(f"Project recovery requires the existing stable target lock: {error}", 3) from error
    try:
        try:
            os.lstat(target / source_edit._SCRATCH_NAME)
        except FileNotFoundError:
            pass
        else:
            raise TransactionError("A source-edit batch is pending in this target; recover it before project recovery.", 3)
        context = _record_context(target, lock)
        if context is None:
            return "no_changes"
        record, record_raw, record_metadata = context
        return _recover_cycle(target, source, lock, record, record_raw, record_metadata)
    finally:
        try:
            source_edit._release_lock(lock)
        except source_edit.LockError as error:
            raise TransactionError(f"Target lock identity became unconfirmed during project recovery: {error}", 4) from error


_GLOBAL_SCHEMA = 2
_GLOBAL_MANIFEST = "olympus/orchestrator-install.json"


def _global_expected(source: Path, load_renderer) -> dict[str, bytes]:
    from . import global_readonly, user_config

    try:
        expected = global_readonly._expected(source, load_renderer(source), ("opencode",))["opencode"]
        user_config.apply_to_expected(source, expected)
        return expected
    except Exception as error:
        raise TransactionError(f"Cannot validate the OpenCode global renderer during recovery: {error}", 4) from error


def _global_target(root: Path, relative: str) -> tuple[bytes | None, os.stat_result | None]:
    from .config_apply import _lstat_target_path, _read_target_file

    path, metadata, issue = _lstat_target_path(root, relative)
    if issue:
        raise TransactionError(issue, 4)
    if metadata is None:
        return None, None
    raw, issue = _read_target_file(root, relative, max_bytes=2_000_000)
    if issue or raw is None:
        raise TransactionError(issue or f"Cannot read global resource: {relative}", 4)
    _, after, issue = _lstat_target_path(root, relative)
    if issue or after is None or (metadata.st_dev, metadata.st_ino) != (after.st_dev, after.st_ino):
        raise TransactionError(issue or f"Global resource changed while reading: {relative}", 4)
    return raw, after


def _global_manifest_receipts(record: dict[str, Any], expected: dict[str, bytes]):
    from . import global_readonly

    try:
        old_raw = base64.b64decode(record["manifest_old_b64"], validate=True)
        new_raw = base64.b64decode(record["manifest_new_b64"], validate=True)
    except (KeyError, ValueError, TypeError) as error:
        raise TransactionError("Global-apply manifest receipt is invalid", 4) from error
    if len(old_raw) > 2_000_000 or len(new_raw) > 2_000_000:
        raise TransactionError("Global-apply manifest receipt exceeds the safety limit", 4)
    try:
        old_manifest, old_entries = global_readonly._parse_manifest_bytes(old_raw, "opencode", expected)
        new_manifest, new_entries = global_readonly._parse_manifest_bytes(new_raw, "opencode", expected)
    except global_readonly.GlobalFault as error:
        raise TransactionError(f"Global-apply manifest evidence is invalid: {error}", 4) from error
    if (old_manifest is None or new_manifest is None
            or {key: value for key, value in old_manifest.items() if key != "managed_files"}
            != {key: value for key, value in new_manifest.items() if key != "managed_files"}):
        raise TransactionError("Global apply may change only managed-file hashes in the global manifest", 4)
    old_items = {item["path"]: item for item in old_manifest["managed_files"]}
    new_items = {item["path"]: item for item in new_manifest["managed_files"]}
    if not set(old_items).issubset(new_items) or set(new_items) - set(old_items) not in (set(), {"opencode.jsonc"}):
        raise TransactionError("Global apply manifest changes an unsupported ownership inventory", 4)
    for path, old_item in old_items.items():
        expected_item = dict(old_item)
        expected_item["sha256"] = new_entries[path]
        if new_items[path] != expected_item:
            raise TransactionError(f"Global apply changed unrequested manifest metadata: {path}", 4)
    if set(new_items) - set(old_items) and new_items["opencode.jsonc"] != {
        "path": "opencode.jsonc", "sha256": hashlib.sha256(expected["opencode.jsonc"]).hexdigest(),
    }:
        raise TransactionError("New global guard ownership does not match the canonical guard", 4)
    changed = {path for path in set(old_entries) | set(new_entries)
               if old_entries.get(path) != new_entries.get(path)}
    for path in changed:
        if new_entries.get(path) != hashlib.sha256(expected[path]).hexdigest():
            raise TransactionError(f"Global manifest candidate differs from canonical output: {path}", 4)
    return old_raw, new_raw, old_manifest, new_manifest, old_entries, new_entries, changed


def _validate_global_candidates(changes: tuple[GlobalChange, ...], expected: dict[str, bytes]):
    if not changes or changes[-1].path != _GLOBAL_MANIFEST or not changes[-1].manifest:
        raise TransactionError("Global apply requires a manifest-last transaction", 3)
    old_raw, new_raw = changes[-1].old, changes[-1].new
    if old_raw is None:
        raise TransactionError("Global apply cannot create or adopt an ownership manifest", 3)
    receipt = {"manifest_old_b64": base64.b64encode(old_raw).decode("ascii"),
               "manifest_new_b64": base64.b64encode(new_raw).decode("ascii")}
    _, _, _, _, old_entries, new_entries, changed = _global_manifest_receipts(receipt, expected)
    if {item.path for item in changes[:-1]} != changed:
        raise TransactionError("Global apply write-set contradicts its manifest delta", 3)
    for item in changes[:-1]:
        if (item.new is None or _hash(item.new) != new_entries.get(item.path)
                or _hash(item.new) != _hash(expected[item.path])
                or (item.old is None and (item.path != "opencode.jsonc" or item.path in old_entries))
                or (item.old is not None and _hash(item.old) != old_entries.get(item.path))):
            raise TransactionError(f"Global candidate bytes contradict the ownership receipt: {item.path}", 3)


def _validate_global_record(target: Path, record: Any, lock_identity: tuple[int, int],
                            expected: dict[str, bytes]):
    if not isinstance(record, dict) or set(record) != {
        "schema_version", "scope", "operation_id", "target_root", "scratch_identity", "lock_identity",
        "state", "harness", "manifest_path", "manifest_old_b64", "manifest_new_b64", "files",
    }:
        raise TransactionError("Global-apply record has missing or unexpected fields", 4)
    if (type(record["schema_version"]) is not int or record["schema_version"] != _GLOBAL_SCHEMA
            or record["scope"] != "global" or record["harness"] != "opencode"
            or re.fullmatch(r"[0-9a-f]{32}", str(record["operation_id"])) is None
            or record["target_root"] != str(target)
            or record["state"] not in ("PREPARING", "PREPARED", "COMMITTED")
            or record["manifest_path"] != _GLOBAL_MANIFEST):
        raise TransactionError("Global-apply record scope, identity, or state is invalid", 4)
    lock_record = record["lock_identity"]
    if (not isinstance(lock_record, dict) or set(lock_record) != {"path", "st_dev", "st_ino"}
            or lock_record["path"] != source_edit._LOCK_NAME
            or type(lock_record["st_dev"]) is not int or type(lock_record["st_ino"]) is not int
            or (lock_record["st_dev"], lock_record["st_ino"]) != lock_identity):
        raise TransactionError("Global-apply record does not match the acquired stable target lock", 4)
    scratch_identity = record["scratch_identity"]
    if (not isinstance(scratch_identity, dict) or set(scratch_identity) != {"st_dev", "st_ino"}
            or type(scratch_identity["st_dev"]) is not int or type(scratch_identity["st_ino"]) is not int):
        raise TransactionError("Global-apply scratch identity is invalid", 4)
    _ensure_scratch_identity(target, record)
    old_raw, new_raw, old_manifest, new_manifest, old_entries, new_entries, changed = \
        _global_manifest_receipts(record, expected)
    files = record["files"]
    if not isinstance(files, list) or not files:
        raise TransactionError("Global-apply record has no write-set", 4)
    file_map: dict[str, dict] = {}
    previous = ""
    for index, entry in enumerate(files):
        if not isinstance(entry, dict) or set(entry) != {
            "path", "old_sha256", "new_sha256", "mode", "backup", "staged",
        }:
            raise TransactionError("Global-apply record has an invalid file entry", 4)
        relative = entry["path"]
        try:
            source_edit._relative_parts(relative)
        except source_edit.BatchError as error:
            raise TransactionError(f"Global-apply record has an unsafe path: {relative!r}", 4) from error
        if (not isinstance(relative, str) or relative in file_map
                or (index < len(files) - 1 and relative <= previous)
                or (relative != _GLOBAL_MANIFEST and relative not in expected)):
            raise TransactionError("Global-apply write-set is duplicated, unordered, or outside the OpenCode inventory", 4)
        if index < len(files) - 1:
            previous = relative
        old_hash, new_hash, mode = entry["old_sha256"], entry["new_sha256"], entry["mode"]
        if ((old_hash is not None and (not isinstance(old_hash, str) or _HASH.fullmatch(old_hash) is None))
                or not isinstance(new_hash, str) or _HASH.fullmatch(new_hash) is None
                or old_hash == new_hash or type(mode) is not int or not 0 <= mode <= 0o7777
                or entry["staged"] != f"staged/file-{index:04d}.new"
                or entry["backup"] != (None if old_hash is None else f"backups/file-{index:04d}.old")):
            raise TransactionError(f"Global-apply file metadata is invalid for {relative}", 4)
        if old_hash is None and relative != "opencode.jsonc":
            raise TransactionError("Only the legacy OpenCode guard may be created by global apply", 4)
        file_map[relative] = entry
    if files[-1]["path"] != _GLOBAL_MANIFEST:
        raise TransactionError("Global ownership manifest must be the final transaction target", 4)
    if set(file_map) - {_GLOBAL_MANIFEST} != changed:
        raise TransactionError("Global-apply write-set contradicts the old/new manifest receipts", 4)
    manifest_entry = file_map[_GLOBAL_MANIFEST]
    if (manifest_entry["old_sha256"] != hashlib.sha256(old_raw).hexdigest()
            or manifest_entry["new_sha256"] != hashlib.sha256(new_raw).hexdigest()):
        raise TransactionError("Global-apply manifest hashes contradict their receipt", 4)
    for path in changed:
        entry = file_map[path]
        if (entry["old_sha256"] != old_entries.get(path)
                or entry["new_sha256"] != new_entries.get(path)):
            raise TransactionError(f"Global-apply hashes contradict manifest ownership: {path}", 4)
    return file_map, old_entries, new_entries, old_raw, new_raw


def _global_record_context(target: Path, lock, expected: dict[str, bytes]):
    identity = source_edit._lock_identity(lock)
    scratch = target / _SCRATCH
    try:
        metadata = os.lstat(scratch)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise TransactionError(f"Cannot inspect global-apply scratch: {error}", 4) from error
    if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT):
        raise TransactionError("Global-apply scratch is a link/reparse point or not a directory", 4)
    try:
        top = set(os.listdir(scratch))
    except OSError as error:
        raise TransactionError(f"Cannot enumerate global-apply scratch: {error}", 4) from error
    if _RECORD not in top:
        if top <= {"backups", "staged"}:
            for name in top:
                path = scratch / name
                item = os.lstat(path)
                if (not stat.S_ISDIR(item.st_mode) or stat.S_ISLNK(item.st_mode)
                        or getattr(item, "st_file_attributes", 0) & _REPARSE_POINT or os.listdir(path)):
                    raise TransactionError("Unrecorded global-apply scratch contains evidence; preserve it", 4)
            for name in top:
                os.rmdir(scratch / name)
            os.rmdir(scratch)
            source_edit._sync_directory(target)
            return None
        raise TransactionError("Global-apply scratch has no authoritative record; evidence was preserved", 4)
    try:
        raw, record_metadata = _bounded_read(target, f"{_SCRATCH}/{_RECORD}", 6_000_000)
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=source_edit._json_object_no_duplicates)
    except TransactionError:
        raise
    except (UnicodeError, ValueError, OSError) as error:
        raise TransactionError("Global-apply record is incomplete or invalid; evidence was preserved", 4) from error
    _validate_global_record(target, record, identity, expected)
    if raw != _canonical_record(record):
        raise TransactionError("Global-apply record is not in canonical persisted form", 4)
    return record, raw, record_metadata


def _global_artifacts(target: Path, record: dict, file_map: dict[str, dict], *,
                      required_backups: set[str] | None = None,
                      required_staged: set[str] | None = None):
    _ensure_scratch_identity(target, record)
    scratch = target / _SCRATCH
    try:
        top = set(os.listdir(scratch))
    except OSError as error:
        raise TransactionError(f"Cannot enumerate global-apply scratch: {error}", 4) from error
    if top - {_RECORD, ".record.json.tmp", "backups", "staged"} or _RECORD not in top:
        raise TransactionError("Global-apply scratch contains unenumerated resources", 4)
    expected_backups = {entry["backup"].split("/", 1)[1] for entry in file_map.values() if entry["backup"]}
    expected_staged = {entry["staged"].split("/", 1)[1] for entry in file_map.values()}
    expected_rollback = {f"rollback-file-{index:04d}.old" for index in range(len(file_map))}
    for directory, allowed in (("backups", expected_backups), ("staged", expected_staged | expected_rollback)):
        if directory in top:
            try:
                source_edit._checked_path(target, f"{_SCRATCH}/{directory}", kind="directory")
                names = set(os.listdir(scratch / directory))
            except (OSError, source_edit.BatchError) as error:
                raise TransactionError(f"Cannot inspect global-apply {directory} evidence", 4) from error
            if names - allowed:
                raise TransactionError(f"Global-apply {directory} contains unenumerated resources", 4)
    artifacts: dict[str, tuple[bytes, os.stat_result]] = {}
    if ".record.json.tmp" in top:
        temporary, metadata = _bounded_read(target, f"{_SCRATCH}/.record.json.tmp", 6_000_000)
        try:
            temp_record = json.loads(temporary.decode("utf-8"), object_pairs_hook=source_edit._json_object_no_duplicates)
        except (UnicodeError, ValueError) as error:
            raise TransactionError("Temporary global-apply record is invalid", 4) from error
        current = dict(record)
        temp_state = temp_record.pop("state", None) if isinstance(temp_record, dict) else None
        current.pop("state", None)
        allowed_transition = {"PREPARING": "PREPARED", "PREPARED": "COMMITTED"}.get(record["state"])
        if (temporary != _canonical_record({**current, "state": temp_state})
                or temp_record != current or temp_state != allowed_transition):
            raise TransactionError("Temporary global-apply record belongs to another operation", 4)
        artifacts[f"{_SCRATCH}/.record.json.tmp"] = (temporary, metadata)
    for index, (relative, entry) in enumerate(file_map.items()):
        candidates = []
        if entry["backup"]:
            candidates.append((f"{_SCRATCH}/{entry['backup']}", entry["old_sha256"], relative in (required_backups or set())))
        candidates.append((f"{_SCRATCH}/{entry['staged']}", entry["new_sha256"], relative in (required_staged or set())))
        candidates.append((f"{_SCRATCH}/staged/rollback-file-{index:04d}.old", entry["old_sha256"], False))
        for artifact_relative, digest, required in candidates:
            if digest is None:
                continue
            value = _artifact(target, artifact_relative, digest, entry["mode"], required=required)
            if value is not None:
                artifacts[artifact_relative] = value
    return artifacts


def _inspect_global(target: Path, source: Path, lock, record: dict, record_raw: bytes,
                    record_metadata: os.stat_result, expected: dict[str, bytes], *,
                    require_backups: set[str] | None = None,
                    require_staged: set[str] | None = None):
    identity = source_edit._lock_identity(lock)
    file_map, old_entries, new_entries, old_manifest, new_manifest = \
        _validate_global_record(target, record, identity, expected)
    current_record, current_record_metadata = _read(target, f"{_SCRATCH}/{_RECORD}")
    if (current_record != record_raw
            or (current_record_metadata.st_dev, current_record_metadata.st_ino)
            != (record_metadata.st_dev, record_metadata.st_ino)):
        raise TransactionError("Authoritative global-apply record changed", 4)
    states: dict[str, str] = {}
    for relative, entry in file_map.items():
        current, metadata = _global_target(target, relative)
        if current is None:
            state = "old" if entry["old_sha256"] is None else None
        else:
            digest = _hash(current)
            if digest == entry["old_sha256"]:
                state = "old"
            elif digest == entry["new_sha256"]:
                state = "new"
            else:
                state = None
            if state is not None and metadata is not None and stat.S_IMODE(metadata.st_mode) != entry["mode"]:
                state = None
        if state is None:
            raise TransactionError(f"Global-apply target has a foreign third state: {relative}", 4)
        states[relative] = state
    for relative, digest in old_entries.items():
        if relative in file_map:
            continue
        raw = _global_target(target, relative)[0]
        if raw is None or _hash(raw) != digest or new_entries.get(relative) != digest:
            raise TransactionError(f"Unchanged manifest-owned global resource drifted: {relative}", 4)
    if record["state"] == "PREPARING" and any(value != "old" for value in states.values()):
        raise TransactionError("PREPARING global apply changed a target before its prepared journal", 4)
    if record["state"] == "COMMITTED" and any(value != "new" for value in states.values()):
        raise TransactionError("COMMITTED global apply has a target that is not in its new state", 4)
    artifacts = _global_artifacts(target, record, file_map, required_backups=require_backups,
                                  required_staged=require_staged)
    return {"identity": identity, "file_map": file_map, "states": states,
            "old_manifest": old_manifest, "new_manifest": new_manifest, "artifacts": artifacts}


def _validate_cycle_record(target: Path, lock, record: dict, expected: dict[str, bytes] | None):
    if not isinstance(record, dict):
        raise TransactionError("Transaction record is invalid", 4)
    identity = source_edit._lock_identity(lock)
    if "scope" in record:
        if expected is None:
            raise TransactionError("Global transaction recovery requires its validated OpenCode inventory", 4)
        return "global", _validate_global_record(target, record, identity, expected)[0]
    return "project", _validate_record(target, record, identity)[1]


def _cycle_target(target: Path, relative: str, kind: str):
    if kind == "global":
        return _global_target(target, relative)
    raw, metadata = _read(target, relative)
    return raw, metadata


def _inspect_cycle(target: Path, source: Path, lock, kind: str, record: dict, record_raw: bytes,
                   record_metadata: os.stat_result, expected: dict[str, bytes] | None, *,
                   expected_states: dict[str, str] | None = None,
                   require_backups: set[str] | None = None,
                   require_staged: set[str] | None = None):
    if kind == "global":
        if expected is None:
            raise TransactionError("Global transaction inspection requires its validated OpenCode inventory", 4)
        live = _inspect_global(target, source, lock, record, record_raw, record_metadata, expected,
                               require_backups=require_backups, require_staged=require_staged)
        if expected_states is not None and live["states"] != expected_states:
            raise TransactionError("Global target state changed before the next journaled write", 4)
        return live
    if kind == "project":
        return _inspect(target, source, lock, record, record_raw, record_metadata,
                        expected_states=expected_states, require_backups=require_backups,
                        require_staged=require_staged)
    raise TransactionError("Transaction cycle has an unsupported validated scope", 4)


def _cleanup_scratch(target: Path, lock, record: dict, record_raw: bytes,
                     record_metadata: os.stat_result, file_map: dict[str, dict], *,
                     allowed_states: set[str], expected: dict[str, bytes] | None = None):
    if record["state"] not in allowed_states:
        raise TransactionError("Transaction cleanup was requested for an unsupported state", 4)
    kind, validated_map = _validate_cycle_record(target, lock, record, expected)
    if validated_map != file_map:
        raise TransactionError("Transaction cleanup inventory changed", 4)
    identity = source_edit._lock_identity(lock)
    scratch = target / _SCRATCH
    scratch_metadata = _ensure_scratch_identity(target, record)
    artifacts = (_global_artifacts(target, record, file_map) if kind == "global"
                 else _scratch_artifacts(target, record, file_map))
    for relative, (raw, metadata) in artifacts.items():
        _safe_remove(target, relative, raw, stat.S_IMODE(metadata.st_mode), lock, identity)
    for directory in ("staged", "backups"):
        path = scratch / directory
        try:
            source_edit._checked_path(target, f"{_SCRATCH}/{directory}", kind="directory")
        except source_edit.BatchError as error:
            if "Missing batch resource" in str(error):
                continue
            raise TransactionError(str(error), 4) from error
        source_edit._lock_identity(lock, identity)
        try:
            os.rmdir(path)
        except OSError as error:
            raise TransactionError(f"Cannot remove nonempty transaction directory {directory}", 4) from error
    current, metadata = _read(target, f"{_SCRATCH}/{_RECORD}")
    if (current != record_raw or (metadata.st_dev, metadata.st_ino)
            != (record_metadata.st_dev, record_metadata.st_ino)):
        raise TransactionError("Transaction record changed during cleanup", 4)
    _safe_remove(target, f"{_SCRATCH}/{_RECORD}", record_raw, stat.S_IMODE(record_metadata.st_mode), lock, identity)
    source_edit._lock_identity(lock, identity)
    current_scratch = os.lstat(scratch)
    if ((current_scratch.st_dev, current_scratch.st_ino)
            != (scratch_metadata.st_dev, scratch_metadata.st_ino) or os.listdir(scratch)):
        raise TransactionError("Transaction scratch changed during final cleanup", 4)
    try:
        os.rmdir(scratch)
    except OSError as error:
        raise TransactionError(f"Cannot remove empty transaction scratch: {error}", 4) from error
    source_edit._sync_directory(target)


def _cycle_record_context(target: Path, lock, kind: str, expected: dict[str, bytes] | None):
    if kind == "global":
        return _global_record_context(target, lock, expected)
    return _record_context(target, lock)


def _rollback_files(target: Path, source: Path, lock, kind: str, record: dict, record_raw: bytes,
                    record_metadata: os.stat_result, expected: dict[str, bytes] | None):
    live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata, expected)
    file_map = live["file_map"]
    required = {path for path, state in live["states"].items()
                if state == "new" and file_map[path]["old_sha256"] is not None}
    if required:
        live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata,
                              expected, require_backups=required)
    elif kind == "project":
        live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata,
                              expected, expected_states={path: "old" for path in file_map})
    else:
        live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata,
                              expected, require_backups=set())
    for index, relative in enumerate(file_map):
        entry = file_map[relative]
        if live["states"][relative] == "old":
            continue
        required = {path for path, state in live["states"].items()
                    if state == "new" and file_map[path]["old_sha256"] is not None}
        live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata,
                              expected, require_backups=required)
        prefix = "Global" if kind == "global" else "Project"
        if entry["old_sha256"] is None:
            if kind != "global":
                raise TransactionError("Project transaction cannot roll back a created target", 4)
            current, metadata = _cycle_target(target, relative, kind)
            if current is None or _hash(current) != entry["new_sha256"] or metadata is None:
                raise TransactionError(f"Created global guard no longer matches its transaction: {relative}", 4)
            source_edit._lock_identity(lock, live["identity"])
            try:
                os.unlink(target / relative)
            except OSError as error:
                raise TransactionError(f"Cannot remove verified transaction-created global guard: {error}", 4) from error
            source_edit._sync_directory((target / relative).parent)
        else:
            backup = _artifact(target, f"{_SCRATCH}/{entry['backup']}", entry["old_sha256"], entry["mode"], required=True)
            rollback_relative = f"{_SCRATCH}/staged/rollback-file-{index:04d}.old"
            existing = _artifact(target, rollback_relative, entry["old_sha256"], entry["mode"], required=False)
            if existing is None:
                try:
                    source_edit._write_private_file(target / rollback_relative, target, rollback_relative,
                                                    backup[0], entry["mode"], lock, live["identity"])
                except source_edit.BatchError as error:
                    raise TransactionError(f"Cannot stage {kind}-apply rollback for {relative}: {error}", 4) from error
            live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata,
                                  expected, require_backups=required)
            current, metadata = _cycle_target(target, relative, kind)
            if (live["states"][relative] != "new" or current is None or metadata is None
                    or _hash(current) != entry["new_sha256"]
                    or stat.S_IMODE(metadata.st_mode) != entry["mode"]):
                raise TransactionError(f"{prefix.lower()} resource changed before rollback: {relative}", 4)
            staged, staged_metadata = _read(target, rollback_relative)
            if _hash(staged) != entry["old_sha256"] or stat.S_IMODE(staged_metadata.st_mode) != entry["mode"]:
                raise TransactionError(f"{kind.capitalize()} rollback evidence changed: {relative}", 4)
            source_edit._lock_identity(lock, live["identity"])
            try:
                os.replace(target / rollback_relative, target / relative)
            except OSError as error:
                raise TransactionError(f"Cannot restore {kind} resource {relative}: {error}", 4) from error
            restored, restored_metadata = _cycle_target(target, relative, kind)
            if (restored is None or _hash(restored) != entry["old_sha256"]
                    or stat.S_IMODE(restored_metadata.st_mode) != entry["mode"]):
                raise TransactionError(f"Restored {kind} resource failed verification: {relative}", 4)
            source_edit._sync_directory((target / relative).parent)
        live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata, expected)
    if any(value != "old" for value in live["states"].values()):
        raise TransactionError(f"{kind.capitalize()} rollback did not restore every recorded old state", 4)
    _cleanup_scratch(target, lock, record, record_raw, record_metadata, file_map,
                     allowed_states={"PREPARING", "PREPARED"}, expected=expected)


def _commit_cycle(target: Path, source: Path, lock, record: dict, record_raw: bytes,
                  record_metadata: os.stat_result, changes, files: list[dict], *,
                  expected: dict[str, bytes] | None = None) -> str:
    kind, file_map = _validate_cycle_record(target, lock, record, expected)
    if [item.path for item in changes] != list(file_map):
        raise TransactionError("Transaction candidates differ from the validated journal write-set", 4)
    identity = source_edit._lock_identity(lock)
    scratch = target / _SCRATCH
    backup_paths = {item.path for item in changes if item.old is not None}
    staged_paths = {item.path for item in changes}
    prefix = "Global" if kind == "global" else "Project"
    prepared_state_verified = False
    try:
        source_edit._make_directory(scratch / "backups", target, lock, identity)
        source_edit._make_directory(scratch / "staged", target, lock, identity)
        for index, item in enumerate(changes):
            source_edit._lock_identity(lock, identity)
            old, metadata = _cycle_target(target, item.path, kind)
            if (old != item.old or (item.old is not None
                                    and (metadata is None or stat.S_IMODE(metadata.st_mode) != item.mode))):
                raise TransactionError(f"{prefix} target drifted under lock: {item.path}", 3)
            entry = files[index]
            if item.old is not None:
                backup_relative = f"{_SCRATCH}/{entry['backup']}"
                source_edit._write_private_file(target / backup_relative, target, backup_relative,
                                                item.old, item.mode, lock, identity)
                backup, backup_metadata = _read(target, backup_relative)
                if _hash(backup) != entry["old_sha256"] or stat.S_IMODE(backup_metadata.st_mode) != item.mode:
                    raise TransactionError(f"{prefix} backup failed verification: {item.path}", 4)
            staged_relative = f"{_SCRATCH}/{entry['staged']}"
            source_edit._write_private_file(target / staged_relative, target, staged_relative,
                                            item.new, item.mode, lock, identity)
            staged, staged_metadata = _read(target, staged_relative)
            if _hash(staged) != entry["new_sha256"] or stat.S_IMODE(staged_metadata.st_mode) != item.mode:
                raise TransactionError(f"{prefix} staged output failed verification: {item.path}", 4)

        record, record_raw, record_metadata = _persist_record(
            target, scratch, {**record, "state": "PREPARED"}, lock, identity,
            previous=(record, record_raw, record_metadata),
        )
        _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata, expected,
                       expected_states={item.path: "old" for item in changes},
                       require_backups=backup_paths, require_staged=staged_paths)
        prepared_state_verified = True
        for index, (item, entry) in enumerate(zip(changes, files)):
            expected_states = {prior.path: ("new" if prior_index < index else "old")
                               for prior_index, prior in enumerate(changes)}
            live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata,
                                  expected, expected_states=expected_states, require_backups=backup_paths)
            staged_relative = f"{_SCRATCH}/{entry['staged']}"
            staged, staged_metadata = _read(target, staged_relative)
            if _hash(staged) != entry["new_sha256"] or stat.S_IMODE(staged_metadata.st_mode) != item.mode:
                raise TransactionError(f"{prefix} staged output changed: {item.path}", 4)
            current, metadata = _cycle_target(target, item.path, kind)
            if item.old is None:
                if kind != "global":
                    raise TransactionError("Project transaction cannot create a target", 4)
                _create_global_file(target, item.path, staged, item.mode, lock, live["identity"])
            else:
                if current != item.old or metadata is None or stat.S_IMODE(metadata.st_mode) != item.mode:
                    raise TransactionError(f"{prefix} target changed before replacement: {item.path}", 3)
                source_edit._lock_identity(lock, live["identity"])
                try:
                    os.replace(target / staged_relative, target / item.path)
                except OSError as error:
                    raise TransactionError(f"Cannot replace {kind} resource {item.path}: {error}", 4) from error
                replaced, replaced_metadata = _cycle_target(target, item.path, kind)
                if (replaced != item.new or replaced_metadata is None
                        or stat.S_IMODE(replaced_metadata.st_mode) != item.mode):
                    raise TransactionError(f"Replaced {kind} output failed verification: {item.path}", 4)
                source_edit._sync_directory((target / item.path).parent)

        live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata,
                              expected, expected_states={item.path: "new" for item in changes},
                              require_backups=backup_paths)
        record, record_raw, record_metadata = _persist_record(
            target, scratch, {**record, "state": "COMMITTED"}, lock, identity,
            previous=(record, record_raw, record_metadata),
        )
        live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata,
                              expected, expected_states={item.path: "new" for item in changes})
        _cleanup_scratch(target, lock, record, record_raw, record_metadata, live["file_map"],
                         allowed_states={"COMMITTED"}, expected=expected)
        return "committed"
    except Exception as error:
        preserve_prepared = False
        try:
            context = _cycle_record_context(target, lock, kind, expected)
            if context is not None and context[0]["operation_id"] == record["operation_id"]:
                current_record, current_raw, current_metadata = context
                if (kind == "project" and current_record["state"] == "PREPARED"
                        and not prepared_state_verified):
                    preserve_prepared = True
                elif current_record["state"] == "COMMITTED":
                    raise TransactionError(
                        f"{prefix} apply is COMMITTED but cleanup remains pending: {error}", 4,
                    ) from error
                elif current_record["state"] not in ("PREPARING", "PREPARED"):
                    raise TransactionError(f"{prefix} apply state is unconfirmed: {error}", 4) from error
                else:
                    _rollback_files(target, source, lock, kind, current_record, current_raw,
                                    current_metadata, expected)
                    if current_record["state"] == "PREPARING":
                        raise TransactionError(
                            f"{prefix} apply preparation failed; no target writes occurred: {error}", 1,
                        ) from error
                    raise TransactionError(f"{prefix} apply failed; rollback was confirmed: {error}", 1) from error
        except TransactionError as recovery_error:
            if ("rollback was confirmed" in str(recovery_error)
                    or "no target writes occurred" in str(recovery_error)):
                raise
            raise TransactionError(
                f"{prefix} apply failed and recovery could not be confirmed: {error}; {recovery_error}", 4,
            ) from error
        if preserve_prepared:
            raise error
        raise TransactionError(f"{prefix} apply failed with unconfirmed state: {error}", 4) from error


def _recover_cycle(target: Path, source: Path, lock, record: dict, record_raw: bytes,
                   record_metadata: os.stat_result, *, expected: dict[str, bytes] | None = None) -> str:
    kind, file_map = _validate_cycle_record(target, lock, record, expected)
    if record["state"] == "PREPARING":
        _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata, expected,
                       expected_states={path: "old" for path in file_map})
        _cleanup_scratch(target, lock, record, record_raw, record_metadata, file_map,
                         allowed_states={"PREPARING"}, expected=expected)
        return "discarded_incomplete_prepare"
    if record["state"] == "COMMITTED":
        live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata,
                              expected, expected_states={path: "new" for path in file_map})
        _cleanup_scratch(target, lock, record, record_raw, record_metadata, live["file_map"],
                         allowed_states={"COMMITTED"}, expected=expected)
        return "committed_cleanup"
    live = _inspect_cycle(target, source, lock, kind, record, record_raw, record_metadata, expected)
    if all(value == "old" for value in live["states"].values()):
        _cleanup_scratch(target, lock, record, record_raw, record_metadata, file_map,
                         allowed_states={"PREPARED"}, expected=expected)
        return "discarded_uncommitted"
    _rollback_files(target, source, lock, kind, record, record_raw, record_metadata, expected)
    return "rolled_back"


def _create_global_file(target: Path, relative: str, payload: bytes, mode: int, lock, identity):
    from .config_apply import _lstat_target_path

    path, metadata, issue = _lstat_target_path(target, relative)
    if issue or path is None or metadata is not None:
        raise TransactionError(issue or f"Global destination appeared before exclusive creation: {relative}", 3)
    source_edit._lock_identity(lock, identity)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, mode)
    except OSError as error:
        raise TransactionError(f"Cannot exclusively create global resource {relative}: {error}", 3) from error
    try:
        view = memoryview(payload)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("short write while creating global resource")
            written += count
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if metadata.st_size != len(payload) or stat.S_IMODE(metadata.st_mode) != stat.S_IMODE(mode):
            raise TransactionError(f"Created global resource metadata failed verification: {relative}", 4)
    except OSError as error:
        raise TransactionError(f"Cannot finish global resource creation {relative}: {error}", 4) from error
    finally:
        os.close(descriptor)
    current, current_metadata = _global_target(target, relative)
    if (current != payload or current_metadata is None
            or stat.S_IMODE(current_metadata.st_mode) != stat.S_IMODE(mode)):
        raise TransactionError(f"Created global resource failed byte/mode verification: {relative}", 4)
    source_edit._sync_directory(path.parent)


def commit_global(target: Path, source: Path, changes: tuple[GlobalChange, ...], manifest_path: str,
                  revalidate, *, load_renderer) -> str:
    """Apply an OpenCode-only global write-set using schema-2 receipts and the shared lock."""
    from . import global_readonly

    target = global_readonly._root(target)
    if not target.is_dir():
        raise TransactionError("Resolved global OpenCode root is not an existing directory", 3)
    target = target.resolve(strict=True)
    if manifest_path != _GLOBAL_MANIFEST:
        raise TransactionError("Global apply requires the fixed OpenCode manifest path", 3)
    try:
        lock = source_edit._acquire_lock(target, create=True)
    except source_edit.LockError as error:
        raise TransactionError(f"Cannot acquire the stable global target writer lock: {error}",
                               4 if isinstance(error, source_edit.LockIdentityError) else 3) from error
    try:
        lock_identity = source_edit._lock_identity(lock)
        if pending(target):
            raise TransactionError("A global-apply or source-edit journal exists; explicitly recover it before applying.", 3)
        latest = revalidate()
        changes = tuple(latest["changes"])
        if not changes:
            return "no_changes"
        if changes[-1].path != manifest_path or changes[-1].old is None:
            raise TransactionError("Global apply requires an existing manifest as its final write", 3)
        expected = _global_expected(source, load_renderer)
        _validate_global_candidates(changes, expected)
        previous = ""
        for item in changes[:-1]:
            try:
                source_edit._relative_parts(item.path)
            except source_edit.BatchError as error:
                raise TransactionError(str(error), 3) from error
            if item.path not in expected or item.path <= previous or item.manifest:
                raise TransactionError("Global apply write-set is unordered or outside the fixed OpenCode inventory", 3)
            previous = item.path
            old, metadata = _global_target(target, item.path)
            if item.old is None:
                if item.path != "opencode.jsonc" or old is not None:
                    raise TransactionError(f"Global create target is not safely absent: {item.path}", 3)
            elif old != item.old or metadata is None or stat.S_IMODE(metadata.st_mode) != item.mode:
                raise TransactionError(f"Global target changed before journal preparation: {item.path}", 3)
            if item.old == item.new or not 0 <= item.mode <= 0o7777:
                raise TransactionError(f"Invalid global apply candidate: {item.path}", 3)
        manifest_change = changes[-1]
        old_manifest, manifest_metadata = _global_target(target, manifest_path)
        if (old_manifest != manifest_change.old or manifest_metadata is None
                or stat.S_IMODE(manifest_metadata.st_mode) != manifest_change.mode):
            raise TransactionError("Global manifest changed before journal preparation", 3)
        files = [{"path": item.path, "old_sha256": None if item.old is None else _hash(item.old),
                  "new_sha256": _hash(item.new), "mode": item.mode,
                  "backup": None if item.old is None else f"backups/file-{index:04d}.old",
                  "staged": f"staged/file-{index:04d}.new"}
                 for index, item in enumerate(changes)]
        record = {
            "schema_version": _GLOBAL_SCHEMA, "scope": "global", "operation_id": uuid.uuid4().hex,
            "target_root": str(target), "scratch_identity": {"st_dev": 0, "st_ino": 0},
            "lock_identity": {"path": source_edit._LOCK_NAME, "st_dev": lock_identity[0], "st_ino": lock_identity[1]},
            "state": "PREPARING", "harness": "opencode", "manifest_path": manifest_path,
            "manifest_old_b64": base64.b64encode(manifest_change.old).decode("ascii"),
            "manifest_new_b64": base64.b64encode(manifest_change.new).decode("ascii"), "files": files,
        }
        record, record_raw, record_metadata = _write_record_new(target, record, lock, lock_identity)
        return _commit_cycle(target, source, lock, record, record_raw, record_metadata, changes, files,
                             expected=expected)
    finally:
        try:
            source_edit._release_lock(lock)
        except source_edit.LockError as error:
            raise TransactionError(f"Global target lock identity became unconfirmed during apply: {error}", 4) from error


def recover_global(target: Path, source: Path, *, load_renderer) -> str:
    """Explicitly roll back one PREPARED global apply or clean a COMMITTED journal."""
    from . import global_readonly

    target = global_readonly._root(target)
    if target.is_dir():
        target = target.resolve(strict=True)
    try:
        lock = source_edit._acquire_lock(target, create=False)
    except source_edit.LockError as error:
        raise TransactionError(f"Global recovery requires the existing stable target lock: {error}",
                               4 if isinstance(error, source_edit.LockIdentityError) else 3) from error
    try:
        try:
            os.lstat(target / source_edit._SCRATCH_NAME)
        except FileNotFoundError:
            pass
        else:
            raise TransactionError("A source-edit batch is pending in this global root; recover it first", 3)
        try:
            os.lstat(target / _SCRATCH)
        except FileNotFoundError:
            return "no_changes"
        except OSError as error:
            raise TransactionError(f"Cannot inspect global-apply scratch: {error}", 4) from error
        expected = _global_expected(source, load_renderer)
        context = _global_record_context(target, lock, expected)
        if context is None:
            return "no_changes"
        record, record_raw, record_metadata = context
        return _recover_cycle(target, source, lock, record, record_raw, record_metadata,
                              expected=expected)
    finally:
        try:
            source_edit._release_lock(lock)
        except source_edit.LockError as error:
            raise TransactionError(f"Global target lock identity became unconfirmed during recovery: {error}", 4) from error
