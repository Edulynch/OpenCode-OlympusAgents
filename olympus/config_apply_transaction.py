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


def _cleanup(target: Path, lock, record: dict, record_raw: bytes, record_metadata: os.stat_result,
             file_map: dict[str, dict], *, allowed_states: set[str]):
    if record["state"] not in allowed_states:
        raise TransactionError("Project-apply cleanup was requested for an unsupported state", 4)
    scratch = target / _SCRATCH
    identity = source_edit._lock_identity(lock)
    _, validated_map = _validate_record(target, record, identity)
    if validated_map != file_map:
        raise TransactionError("Project-apply cleanup inventory changed", 4)
    scratch_metadata = _ensure_scratch_identity(target, record)
    artifacts = _scratch_artifacts(target, record, file_map)
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
            raise TransactionError(f"Cannot remove nonempty project-apply directory {directory}", 4) from error
    current, metadata = _read(target, f"{_SCRATCH}/{_RECORD}")
    if (current != record_raw or (metadata.st_dev, metadata.st_ino)
            != (record_metadata.st_dev, record_metadata.st_ino)):
        raise TransactionError("Project-apply record changed during cleanup", 4)
    _safe_remove(target, f"{_SCRATCH}/{_RECORD}", record_raw, stat.S_IMODE(record_metadata.st_mode), lock, identity)
    source_edit._lock_identity(lock, identity)
    current_scratch = os.lstat(scratch)
    if ((current_scratch.st_dev, current_scratch.st_ino) != (scratch_metadata.st_dev, scratch_metadata.st_ino)
            or os.listdir(scratch)):
        raise TransactionError("Project-apply scratch changed during final cleanup", 4)
    try:
        os.rmdir(scratch)
    except OSError as error:
        raise TransactionError(f"Cannot remove empty project-apply scratch: {error}", 4) from error
    source_edit._sync_directory(target)


def _rollback(target: Path, source: Path, lock, record, record_raw, record_metadata):
    live = _inspect(target, source, lock, record, record_raw, record_metadata)
    file_map = live["file_map"]
    new_paths = {path for path, state in live["states"].items() if state == "new"}
    if new_paths:
        live = _inspect(target, source, lock, record, record_raw, record_metadata, require_backups=new_paths)
    else:
        live = _inspect(target, source, lock, record, record_raw, record_metadata,
                        expected_states={path: "old" for path in file_map})
    for index, (relative, entry) in enumerate(file_map.items()):
        if live["states"][relative] == "old":
            continue
        required = {path for path, state in live["states"].items() if state == "new"}
        live = _inspect(target, source, lock, record, record_raw, record_metadata, require_backups=required)
        backup = _artifact(target, f"{_SCRATCH}/{entry['backup']}", entry["old_sha256"], entry["mode"], required=True)
        rollback_relative = f"{_SCRATCH}/staged/rollback-file-{index:04d}.old"
        rollback_path = target / rollback_relative
        existing = _artifact(target, rollback_relative, entry["old_sha256"], entry["mode"], required=False)
        if existing is None:
            try:
                source_edit._write_private_file(rollback_path, target, rollback_relative, backup[0],
                                                entry["mode"], lock, live["identity"])
            except source_edit.BatchError as error:
                raise TransactionError(f"Cannot stage project-apply rollback for {relative}: {error}", 4) from error
        live = _inspect(target, source, lock, record, record_raw, record_metadata, require_backups=required)
        if live["states"][relative] != "new":
            raise TransactionError(f"Project-apply target changed before rollback: {relative}", 4)
        staged, staged_metadata = _read(target, rollback_relative)
        if _hash(staged) != entry["old_sha256"] or stat.S_IMODE(staged_metadata.st_mode) != entry["mode"]:
            raise TransactionError(f"Project-apply rollback evidence changed: {relative}", 4)
        source_edit._lock_identity(lock, live["identity"])
        try:
            os.replace(target / rollback_relative, target / relative)
        except OSError as error:
            raise TransactionError(f"Cannot restore project resource {relative}: {error}", 4) from error
        restored, restored_metadata = _read(target, relative)
        if _hash(restored) != entry["old_sha256"] or stat.S_IMODE(restored_metadata.st_mode) != entry["mode"]:
            raise TransactionError(f"Restored project resource failed verification: {relative}", 4)
        source_edit._sync_directory((target / relative).parent)
        live = _inspect(target, source, lock, record, record_raw, record_metadata)
    live = _inspect(target, source, lock, record, record_raw, record_metadata,
                    expected_states={path: "old" for path in file_map})
    _cleanup(target, lock, record, record_raw, record_metadata, file_map, allowed_states={"PREPARING", "PREPARED"})


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
    identity = source_edit._lock_identity
    try:
        lock = source_edit._acquire_lock(target, create=True)
    except source_edit.LockError as error:
        raise TransactionError(f"Cannot acquire the stable target writer lock: {error}",
                               4 if isinstance(error, source_edit.LockIdentityError) else 3) from error
    try:
        lock_identity = identity(lock)
        if pending(target):
            raise TransactionError("A project-apply or source-edit journal exists; explicitly recover that journal before applying.", 3)
        changes, manifest_old, manifest_new = revalidate()
        if not changes:
            return "no_changes"
        _validate_plan(target, changes, manifest_path)
        if changes[-1].old != manifest_old or changes[-1].new != manifest_new:
            raise TransactionError("Manifest plan changed during locked revalidation", 3)
        files = []
        for index, item in enumerate(changes):
            files.append({"path": item.path, "old_sha256": _hash(item.old), "new_sha256": _hash(item.new),
                          "mode": item.mode, "backup": f"backups/file-{index:04d}.old",
                          "staged": f"staged/file-{index:04d}.new"})
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
        scratch = target / _SCRATCH
        try:
            source_edit._make_directory(scratch / "backups", target, lock, lock_identity)
            source_edit._make_directory(scratch / "staged", target, lock, lock_identity)
            for index, item in enumerate(changes):
                source_edit._lock_identity(lock, lock_identity)
                old, current_metadata = _read(target, item.path)
                if old != item.old or stat.S_IMODE(current_metadata.st_mode) != item.mode:
                    raise TransactionError(f"Project target drifted under lock: {item.path}", 3)
                entry = files[index]
                for relative, payload, expected_hash in (
                    (f"{_SCRATCH}/{entry['backup']}", item.old, entry["old_sha256"]),
                    (f"{_SCRATCH}/{entry['staged']}", item.new, entry["new_sha256"]),
                ):
                    source_edit._write_private_file(target / relative, target, relative, payload,
                                                    item.mode, lock, lock_identity)
                    saved, saved_metadata = _read(target, relative)
                    if _hash(saved) != expected_hash or stat.S_IMODE(saved_metadata.st_mode) != item.mode:
                        raise TransactionError(f"Staged project evidence failed verification: {relative}", 4)
            # Validate the old/new manifests and the complete managed inventory before any target replace.
            record, record_raw, record_metadata = _persist_record(
                target, scratch, {**record, "state": "PREPARED"}, lock, lock_identity,
                previous=(record, record_raw, record_metadata),
            )
            live = _inspect(target, source, lock, record, record_raw, record_metadata,
                            expected_states={item.path: "old" for item in changes},
                            require_backups={item.path for item in changes},
                            require_staged={item.path for item in changes})
            mutation_started = False
            try:
                for index, (item, entry) in enumerate(zip(changes, files)):
                    expected_states = {
                        prior.path: ("new" if prior_index < index else "old")
                        for prior_index, prior in enumerate(changes)
                    }
                    live = _inspect(target, source, lock, record, record_raw, record_metadata,
                                    expected_states=expected_states,
                                    require_backups={prior.path for prior in changes})
                    staged_relative = f"{_SCRATCH}/{entry['staged']}"
                    staged, staged_metadata = _read(target, staged_relative)
                    if _hash(staged) != entry["new_sha256"] or stat.S_IMODE(staged_metadata.st_mode) != item.mode:
                        raise TransactionError(f"Staged project output changed: {item.path}", 4)
                    old, old_metadata = _read(target, item.path)
                    if _hash(old) != entry["old_sha256"] or stat.S_IMODE(old_metadata.st_mode) != item.mode:
                        raise TransactionError(f"Project target changed before replacement: {item.path}", 3)
                    source_edit._lock_identity(lock, live["identity"])
                    mutation_started = True
                    try:
                        os.replace(target / staged_relative, target / item.path)
                    except OSError as error:
                        raise TransactionError(f"Cannot replace project resource {item.path}: {error}", 4) from error
                    replaced, replaced_metadata = _read(target, item.path)
                    if _hash(replaced) != entry["new_sha256"] or stat.S_IMODE(replaced_metadata.st_mode) != item.mode:
                        raise TransactionError(f"Replaced project resource failed verification: {item.path}", 4)
                    source_edit._sync_directory((target / item.path).parent)

                live = _inspect(target, source, lock, record, record_raw, record_metadata,
                                expected_states={item.path: "new" for item in changes},
                                require_backups={item.path for item in changes})
                record, record_raw, record_metadata = _persist_record(
                    target, scratch, {**record, "state": "COMMITTED"}, lock, lock_identity,
                    previous=(record, record_raw, record_metadata),
                )
                live = _inspect(target, source, lock, record, record_raw, record_metadata,
                                expected_states={item.path: "new" for item in changes})
                _cleanup(target, lock, record, record_raw, record_metadata, live["file_map"], allowed_states={"COMMITTED"})
                return "committed"
            except Exception as error:
                try:
                    context = _record_context(target, lock)
                    if context is not None and context[0]["operation_id"] == record["operation_id"]:
                        current_record, current_raw, current_metadata = context
                        if current_record["state"] == "COMMITTED":
                            raise TransactionError(
                                f"Project apply is COMMITTED but cleanup remains pending: {error}", 4,
                            ) from error
                        if current_record["state"] not in ("PREPARING", "PREPARED"):
                            raise TransactionError(f"Project apply state is unconfirmed: {error}", 4) from error
                        _rollback(target, source, lock, current_record, current_raw, current_metadata)
                        raise TransactionError(f"Project apply failed; rollback was confirmed: {error}", 1) from error
                except TransactionError as recovery_error:
                    if "rollback was confirmed" in str(recovery_error):
                        raise
                    raise TransactionError(
                        f"Project apply failed and recovery could not be confirmed: {error}; {recovery_error}", 4,
                    ) from error
                raise TransactionError(f"Project apply failed with unconfirmed state: {error}", 4) from error
        except Exception as error:
            # Failures before PREPARED have not changed project resources. Keep the journal if
            # evidence cannot be safely reconciled; never delete an uncertain scratch tree.
            try:
                context = _record_context(target, lock)
                if context is not None and context[0]["operation_id"] == record["operation_id"]:
                    current_record, current_raw, current_metadata = context
                    if current_record["state"] == "PREPARING":
                        _rollback(target, source, lock, current_record, current_raw, current_metadata)
                        raise TransactionError(f"Project apply preparation failed; no target writes occurred: {error}", 1) from error
            except TransactionError as recovery_error:
                if "no target writes occurred" in str(recovery_error):
                    raise
                raise TransactionError(f"Project apply preparation failed; scratch recovery is unconfirmed: {recovery_error}", 4) from error
            raise
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
        _, file_map = _validate_record(target, record, source_edit._lock_identity(lock))
        if record["state"] == "PREPARING":
            live = _inspect(target, source, lock, record, record_raw, record_metadata,
                            expected_states={path: "old" for path in file_map})
            _cleanup(target, lock, record, record_raw, record_metadata, file_map, allowed_states={"PREPARING"})
            return "discarded_incomplete_prepare"
        if record["state"] == "COMMITTED":
            live = _inspect(target, source, lock, record, record_raw, record_metadata,
                            expected_states={path: "new" for path in file_map})
            _cleanup(target, lock, record, record_raw, record_metadata, file_map, allowed_states={"COMMITTED"})
            return "committed_cleanup"
        live = _inspect(target, source, lock, record, record_raw, record_metadata)
        if all(value == "old" for value in live["states"].values()):
            _cleanup(target, lock, record, record_raw, record_metadata, file_map, allowed_states={"PREPARED"})
            return "discarded_uncommitted"
        _rollback(target, source, lock, record, record_raw, record_metadata)
        return "rolled_back"
    finally:
        try:
            source_edit._release_lock(lock)
        except source_edit.LockError as error:
            raise TransactionError(f"Target lock identity became unconfirmed during project recovery: {error}", 4) from error
