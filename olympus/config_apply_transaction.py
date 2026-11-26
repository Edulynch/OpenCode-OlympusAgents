"""Recoverable project-target transaction for explicit config apply."""

from __future__ import annotations

import hashlib
import base64
import json
import os
import re
import stat
import sys
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
    if manifest_path != MANIFEST_PATHS[0]:
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
                    relative == "opencode.jsonc" or relative.startswith(".opencode/")
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


def _record_context(target: Path, lock, *, settings_source: Path | None = None
                    ) -> tuple[dict[str, Any], bytes, os.stat_result] | None:
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
        if ".record.json.tmp" in top:
            if settings_source is None:
                raise TransactionError("Unpublished project-apply record is ambiguous; evidence was preserved", 4)
            return _settings_initial_temp(target, settings_source, lock, "project")
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
    if isinstance(record, dict) and record.get("kind") == _SETTINGS_KIND:
        if raw != _canonical_record(record):
            raise TransactionError("User-settings record is not in canonical persisted form", 4)
        return record, raw, metadata
    _validate_record(target, record, identity)
    if raw != _canonical_record(record):
        raise TransactionError("Project-apply record is not in canonical persisted form", 4)
    return record, raw, metadata


def _manifest_maps(target: Path, record: dict, file_map: dict[str, dict], states: dict[str, str], source: Path,
                   renderer) -> tuple[Any, Any, dict[str, str], dict[str, str]]:
    old_raw, new_raw = _manifest_bytes(target, record, file_map, states, state=record["state"])
    from .config_apply import _LEGACY_PROJECT_MANIFEST_VERSIONS, _render_managed_outputs

    old_manifest = _parse_manifest(target, record["manifest_path"], old_raw)
    if old_manifest.installed_version in _LEGACY_PROJECT_MANIFEST_VERSIONS:
        raise TransactionError(
            f"Legacy project manifest receipt {old_manifest.installed_version} cannot be recovered; "
            "uninstall with its source version, then install the current release.",
            4,
        )
    if old_manifest.relative_path != record["manifest_path"]:
        raise TransactionError("Old manifest location contradicts the project-apply record", 4)
    old_harnesses = old_manifest.installed_harnesses
    try:
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
    if new_manifest.installed_version in _LEGACY_PROJECT_MANIFEST_VERSIONS:
        raise TransactionError(
            f"Legacy project manifest receipt {new_manifest.installed_version} cannot be recovered; "
            "uninstall with its source version, then install the current release.",
            4,
        )
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
        context = _record_context(target, lock, settings_source=source)
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
    if set(old_items) != set(new_items):
        raise TransactionError("Global apply cannot change the installed ownership inventory", 4)
    for path, old_item in old_items.items():
        expected_item = dict(old_item)
        expected_item["sha256"] = new_entries[path]
        if new_items[path] != expected_item:
            raise TransactionError(f"Global apply changed unrequested manifest metadata: {path}", 4)
    changed = {path for path in set(old_entries) | set(new_entries)
               if old_entries.get(path) != new_entries.get(path)}
    if global_readonly._DEFAULT_AGENT_RECEIPT in old_manifest and "opencode.jsonc" in changed:
        raise TransactionError("Global apply must preserve the installer-receipted OpenCode config", 4)
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
                or item.old is None
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
        if (not isinstance(old_hash, str) or _HASH.fullmatch(old_hash) is None
                or not isinstance(new_hash, str) or _HASH.fullmatch(new_hash) is None
                or old_hash == new_hash or type(mode) is not int or not 0 <= mode <= 0o7777
                or entry["staged"] != f"staged/file-{index:04d}.new"
                or entry["backup"] != f"backups/file-{index:04d}.old"):
            raise TransactionError(f"Global-apply file metadata is invalid for {relative}", 4)
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


def _global_record_context(target: Path, lock, expected: dict[str, bytes], *, source: Path | None = None):
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
        if ".record.json.tmp" in top:
            if source is None:
                raise TransactionError("Unpublished global-apply record is ambiguous; evidence was preserved", 4)
            return _settings_initial_temp(target, source, lock, "global")
        raise TransactionError("Global-apply scratch has no authoritative record; evidence was preserved", 4)
    try:
        raw, record_metadata = _bounded_read(target, f"{_SCRATCH}/{_RECORD}", 6_000_000)
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=source_edit._json_object_no_duplicates)
    except TransactionError:
        raise
    except (UnicodeError, ValueError, OSError) as error:
        raise TransactionError("Global-apply record is incomplete or invalid; evidence was preserved", 4) from error
    if isinstance(record, dict) and record.get("kind") == _SETTINGS_KIND:
        if raw != _canonical_record(record):
            raise TransactionError("User-settings record is not in canonical persisted form", 4)
        return record, raw, record_metadata
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
    expected_backups = {entry["backup"].split("/", 1)[1] for entry in file_map.values()}
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
        candidates = [
            (f"{_SCRATCH}/{entry['backup']}", entry["old_sha256"], relative in (required_backups or set())),
            (f"{_SCRATCH}/{entry['staged']}", entry["new_sha256"], relative in (required_staged or set())),
            (f"{_SCRATCH}/staged/rollback-file-{index:04d}.old", entry["old_sha256"], False),
        ]
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
            state = None
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
            if item.old is None or current != item.old or metadata is None or stat.S_IMODE(metadata.st_mode) != item.mode:
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
    if isinstance(record, dict) and record.get("kind") == _SETTINGS_KIND:
        scope = "global" if expected is not None else "project"
        return _recover_settings_cycle(target, source, lock, record, record_raw, record_metadata, scope)
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
            if (item.old is None or old != item.old or metadata is None
                    or stat.S_IMODE(metadata.st_mode) != item.mode):
                raise TransactionError(f"Global target changed before journal preparation: {item.path}", 3)
            if item.old == item.new or not 0 <= item.mode <= 0o7777:
                raise TransactionError(f"Invalid global apply candidate: {item.path}", 3)
        manifest_change = changes[-1]
        old_manifest, manifest_metadata = _global_target(target, manifest_path)
        if (old_manifest != manifest_change.old or manifest_metadata is None
                or stat.S_IMODE(manifest_metadata.st_mode) != manifest_change.mode):
            raise TransactionError("Global manifest changed before journal preparation", 3)
        files = [{"path": item.path, "old_sha256": _hash(item.old),
                  "new_sha256": _hash(item.new), "mode": item.mode,
                  "backup": f"backups/file-{index:04d}.old",
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


_SETTINGS_KIND = "user_config"
_SETTINGS_PREFERENCES = "@global-user-config"
_SETTINGS_LIMIT = 2_000_000


def _settings_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _settings_parent(path: Path, *, create: bool = False) -> tuple[Path, os.stat_result]:
    """Resolve a global preferences parent without accepting links or reparse points."""
    path = _settings_absolute(path)
    if not path.is_absolute() or not path.name:
        raise TransactionError("Global user configuration path is not a safe file path", 4)
    parent = path.parent
    current = Path(path.anchor)
    for part in parent.parts[len(current.parts):]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if not create:
                raise TransactionError("Global user configuration parent is missing; preserve recovery evidence", 4)
            try:
                os.mkdir(current)
                metadata = os.lstat(current)
            except OSError as error:
                raise TransactionError(f"Cannot create global user configuration parent: {error}", 4) from error
        except OSError as error:
            raise TransactionError(f"Cannot inspect global user configuration parent: {error}", 4) from error
        if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT):
            raise TransactionError("Global user configuration parent is linked or not a directory", 4)
    try:
        metadata = os.lstat(parent)
    except OSError as error:
        raise TransactionError(f"Cannot inspect global user configuration parent: {error}", 4) from error
    if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
            or not metadata.st_ino):
        raise TransactionError("Global user configuration parent identity is unsafe or unavailable", 4)
    return parent, metadata


def _settings_external_read(path: Path, parent_identity: tuple[int, int] | None = None):
    path = _settings_absolute(path)
    parent, parent_metadata = _settings_parent(path)
    identity = (parent_metadata.st_dev, parent_metadata.st_ino)
    if parent_identity is not None and identity != parent_identity:
        raise TransactionError("Global user configuration parent identity changed; preserve recovery evidence", 4)
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        return None, None
    except OSError as error:
        raise TransactionError(f"Cannot inspect global user configuration: {error}", 4) from error
    if (not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode)
            or getattr(before, "st_file_attributes", 0) & _REPARSE_POINT or before.st_nlink != 1
            or before.st_size > _SETTINGS_LIMIT):
        raise TransactionError("Global user configuration is linked, oversized, or not a private regular file", 4)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise TransactionError(f"Cannot safely open global user configuration: {error}", 4) from error
    try:
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or getattr(opened, "st_file_attributes", 0) & _REPARSE_POINT):
            raise TransactionError("Global user configuration changed identity while opening", 4)
        chunks = []
        total = 0
        while True:
            block = os.read(descriptor, min(1024 * 1024, _SETTINGS_LIMIT + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            if total > _SETTINGS_LIMIT:
                raise TransactionError("Global user configuration exceeds the safety limit", 4)
        after = os.fstat(descriptor)
        try:
            path_after = os.lstat(path)
        except OSError as error:
            raise TransactionError("Global user configuration disappeared while reading", 4) from error
        _, parent_after = _settings_parent(path)
        if ((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or (after.st_dev, after.st_ino) != (path_after.st_dev, path_after.st_ino)
                or (parent_after.st_dev, parent_after.st_ino) != identity):
            raise TransactionError("Global user configuration changed while reading", 4)
        return b"".join(chunks), after
    finally:
        os.close(descriptor)


def _settings_preference_descriptor(scope: str, target: Path, path: Path, *, create_parent: bool = False) -> dict:
    from . import user_config

    if scope == "project":
        return {"relative": ".opencode/olympus-config.json"}
    current = _settings_absolute(user_config.config_path("global"))
    path = _settings_absolute(path)
    if os.path.normcase(str(current)) != os.path.normcase(str(path)):
        raise TransactionError("Global preference path differs from the runtime-derived Olympus config path", 4)
    parent, metadata = _settings_parent(path, create=create_parent)
    return {
        "path": str(path),
        "parent": str(parent),
        "parent_identity": {"st_dev": metadata.st_dev, "st_ino": metadata.st_ino},
    }


def _settings_agent_paths(record: dict) -> tuple[str, ...]:
    if record["change"].get("kind") == "max_children":
        return ("agents/kael.md", "agents/atlas.md")
    return (record["agent_path"],)


def _settings_validate_record(target: Path, source: Path, lock, record: Any, scope: str) -> dict[str, dict]:
    expected_fields = {
        "schema_version", "kind", "scope", "operation_id", "target_root", "scratch_identity",
        "lock_identity", "state", "role", "change", "agent_path", "manifest_path",
        "preference_target", "project_fallback", "manifest_old_b64", "manifest_new_b64", "files",
    }
    if not isinstance(record, dict) or set(record) != expected_fields:
        raise TransactionError("User-settings recovery record has missing or unexpected fields", 4)
    if (type(record["schema_version"]) is not int or record["schema_version"] != 1
            or record["kind"] != _SETTINGS_KIND or record["scope"] != scope
            or not isinstance(record["operation_id"], str)
            or re.fullmatch(r"[0-9a-f]{32}", record["operation_id"]) is None
            or record["target_root"] != str(target)
            or record["state"] not in ("PREPARING", "PREPARED", "COMMITTED")):
        raise TransactionError("User-settings recovery record scope, identity, or state is invalid", 4)
    lock_identity = source_edit._lock_identity(lock)
    lock_record = record["lock_identity"]
    if (not isinstance(lock_record, dict) or set(lock_record) != {"path", "st_dev", "st_ino"}
            or lock_record["path"] != source_edit._LOCK_NAME
            or type(lock_record["st_dev"]) is not int or type(lock_record["st_ino"]) is not int
            or (lock_record["st_dev"], lock_record["st_ino"]) != lock_identity):
        raise TransactionError("User-settings record does not match the acquired stable target lock", 4)
    scratch_identity = record["scratch_identity"]
    if (not isinstance(scratch_identity, dict) or set(scratch_identity) != {"st_dev", "st_ino"}
            or type(scratch_identity["st_dev"]) is not int or type(scratch_identity["st_ino"]) is not int):
        raise TransactionError("User-settings scratch identity is invalid", 4)
    _ensure_scratch_identity(target, record)

    from . import user_config

    role = record["role"]
    change = record["change"]
    roles = {row["role"] for row in user_config._canonical_rows(source)}
    if not isinstance(role, str) or role not in roles or not isinstance(change, dict):
        raise TransactionError("User-settings record names an unknown role or invalid change", 4)
    fallback = record["project_fallback"]
    if scope == "project":
        if (not isinstance(fallback, dict) or set(fallback) != {"model", "effort"}
                or not isinstance(fallback["model"], str) or not isinstance(fallback["effort"], str)):
            raise TransactionError("Project fallback assignment is missing or invalid", 4)
        from . import models_catalog

        try:
            models_catalog.validate_assignment(fallback["model"], fallback["effort"], source)
        except models_catalog.CatalogError as error:
            raise TransactionError(f"Recorded project fallback assignment is invalid: {error}", 4) from error
    elif fallback is not None:
        raise TransactionError("Global user-settings record must not contain a project fallback", 4)
    if change.get("kind") == "override":
        if (set(change) != {"kind", "role", "field", "value"} or change["role"] != role
                or change["field"] not in ("model", "effort") or not isinstance(change["value"], str)
                or not change["value"]):
            raise TransactionError("User-settings override record is invalid", 4)
    elif change.get("kind") == "max_children":
        if (scope != "global" or role != "kael" or set(change) != {"kind", "value"}
                or type(change["value"]) is not int or not 1 <= change["value"] <= 8):
            raise TransactionError("User-settings max-children record is invalid", 4)
    else:
        raise TransactionError("User-settings record has an unsupported operation", 4)

    agent_path = f"{'.opencode/' if scope == 'project' else ''}agents/{role}.md"
    manifest_path = ".opencode/orchestrator-install.json" if scope == "project" else _GLOBAL_MANIFEST
    if record["agent_path"] != agent_path or record["manifest_path"] != manifest_path:
        raise TransactionError("User-settings record names an unsupported role or manifest path", 4)
    agent_paths = _settings_agent_paths(record)
    if scope == "project":
        if record["preference_target"] != {"relative": ".opencode/olympus-config.json"}:
            raise TransactionError("Project preference record names an unsupported path", 4)
        preference_path = ".opencode/olympus-config.json"
    else:
        descriptor = record["preference_target"]
        if (not isinstance(descriptor, dict)
                or set(descriptor) != {"path", "parent", "parent_identity"}
                or not isinstance(descriptor["path"], str) or not Path(descriptor["path"]).is_absolute()
                or not isinstance(descriptor["parent"], str)
                or descriptor["parent"] != str(Path(descriptor["path"]).parent)
                or not isinstance(descriptor["parent_identity"], dict)
                or set(descriptor["parent_identity"]) != {"st_dev", "st_ino"}
                or type(descriptor["parent_identity"]["st_dev"]) is not int
                or type(descriptor["parent_identity"]["st_ino"]) is not int):
            raise TransactionError("Global preference path or anchored parent identity is invalid", 4)
        current = _settings_preference_descriptor(scope, target, Path(descriptor["path"]))
        if current != descriptor:
            raise TransactionError(
                "Global preferences no longer resolve to the recorded path and parent identity; preserve recovery evidence",
                4,
            )
        preference_path = _SETTINGS_PREFERENCES

    files = record["files"]
    expected_paths = [*agent_paths, manifest_path, preference_path]
    legacy_paths = [agent_path, manifest_path, preference_path]
    if (change["kind"] == "max_children" and isinstance(files, list) and len(files) == 3
            and [item.get("path") if isinstance(item, dict) else None for item in files] == legacy_paths):
        raise TransactionError(
            "Legacy max-children user-settings journal contains only Kael; preserve its evidence and "
            "recover it with the Olympus source version that created it.",
            4,
        )
    if not isinstance(files, list) or len(files) != len(expected_paths):
        raise TransactionError(
            f"User-settings record must contain exactly {len(expected_paths)} destinations", 4,
        )
    file_map: dict[str, dict] = {}
    for index, entry in enumerate(files):
        if not isinstance(entry, dict) or set(entry) != {
            "path", "old_sha256", "new_sha256", "mode", "backup", "staged",
        }:
            raise TransactionError("User-settings record has an invalid destination entry", 4)
        old_hash, new_hash = entry["old_sha256"], entry["new_sha256"]
        if (entry["path"] != expected_paths[index] or entry["path"] in file_map
                or (old_hash is not None and (not isinstance(old_hash, str) or _HASH.fullmatch(old_hash) is None))
                or not isinstance(new_hash, str) or _HASH.fullmatch(new_hash) is None
                or (index < len(expected_paths) - 1 and old_hash is None)
                or (index < len(agent_paths)
                    and old_hash == new_hash and change["kind"] != "max_children")
                or (index == len(expected_paths) - 2 and old_hash == new_hash)
                or (index == len(expected_paths) - 1 and old_hash == new_hash and old_hash is None)
                or type(entry["mode"]) is not int or not 0 <= entry["mode"] <= 0o7777
                or entry["backup"] != f"backups/file-{index:04d}.old"
                or entry["staged"] != f"staged/file-{index:04d}.new"):
            raise TransactionError(f"User-settings destination metadata is invalid: {entry.get('path')}", 4)
        file_map[entry["path"]] = entry
    try:
        old_manifest = base64.b64decode(record["manifest_old_b64"], validate=True)
        new_manifest = base64.b64decode(record["manifest_new_b64"], validate=True)
    except (ValueError, TypeError) as error:
        raise TransactionError("User-settings manifest receipts are invalid", 4) from error
    if len(old_manifest) > _SETTINGS_LIMIT or len(new_manifest) > _SETTINGS_LIMIT:
        raise TransactionError("User-settings manifest receipt exceeds the safety limit", 4)
    if (_hash(old_manifest) != file_map[manifest_path]["old_sha256"]
            or _hash(new_manifest) != file_map[manifest_path]["new_sha256"]):
        raise TransactionError("User-settings manifest hashes contradict their record", 4)
    return file_map


def _settings_artifacts(target: Path, record: dict, file_map: dict[str, dict], *,
                        required_backups: set[str] | None = None,
                        required_staged: set[str] | None = None):
    _ensure_scratch_identity(target, record)
    scratch = target / _SCRATCH
    top = set(os.listdir(scratch))
    allowed_top = {_RECORD, ".record.json.tmp", "backups", "staged"}
    if top - allowed_top or _RECORD not in top:
        raise TransactionError("User-settings scratch contains unenumerated resources", 4)
    expected_backups = {entry["backup"].split("/", 1)[1] for entry in file_map.values()
                        if entry["old_sha256"] is not None}
    expected_staged = {entry["staged"].split("/", 1)[1] for entry in file_map.values()}
    expected_rollback = {f"rollback-file-{index:04d}.old" for index in range(len(file_map))}
    for directory, allowed in (("backups", expected_backups), ("staged", expected_staged | expected_rollback)):
        if directory in top:
            source_edit._checked_path(target, f"{_SCRATCH}/{directory}", kind="directory")
            names = set(os.listdir(scratch / directory))
            if names - allowed:
                raise TransactionError(f"User-settings {directory} contains unenumerated resources", 4)
    artifacts: dict[str, tuple[bytes, os.stat_result]] = {}
    if ".record.json.tmp" in top:
        temporary, metadata = _bounded_read(target, f"{_SCRATCH}/.record.json.tmp", 6_000_000)
        try:
            temp_record = json.loads(temporary.decode("utf-8"),
                                     object_pairs_hook=source_edit._json_object_no_duplicates)
        except (UnicodeError, ValueError) as error:
            raise TransactionError("Temporary user-settings record is invalid", 4) from error
        current = dict(record)
        temp_state = temp_record.pop("state", None) if isinstance(temp_record, dict) else None
        current.pop("state", None)
        transition = {"PREPARING": "PREPARED", "PREPARED": "COMMITTED"}.get(record["state"])
        if (temporary != _canonical_record({**current, "state": temp_state})
                or temp_record != current or temp_state != transition):
            raise TransactionError("Temporary user-settings record belongs to another operation", 4)
        artifacts[f"{_SCRATCH}/.record.json.tmp"] = (temporary, metadata)
    for index, (relative, entry) in enumerate(file_map.items()):
        candidates = [
            (f"{_SCRATCH}/{entry['backup']}", entry["old_sha256"],
             relative in (required_backups or set())),
            (f"{_SCRATCH}/{entry['staged']}", entry["new_sha256"],
             relative in (required_staged or set())),
            (f"{_SCRATCH}/staged/rollback-file-{index:04d}.old", entry["old_sha256"], False),
        ]
        for artifact_relative, digest, required in candidates:
            if digest is None:
                try:
                    os.lstat(target / artifact_relative)
                except FileNotFoundError:
                    continue
                except OSError as error:
                    raise TransactionError(f"Cannot inspect user-settings evidence {artifact_relative}: {error}", 4) from error
                raise TransactionError(f"Unexpected user-settings evidence has no recorded old state: {artifact_relative}", 4)
            value = _artifact(target, artifact_relative, digest, entry["mode"], required=required)
            if value is not None:
                artifacts[artifact_relative] = value
    return artifacts


def _settings_config_value(source: Path, scope: str, raw: bytes | None, path: Path):
    from . import user_config

    if raw is None:
        return {"schema_version": 1, "overrides": {}}
    if len(raw) > _SETTINGS_LIMIT:
        raise TransactionError("User-settings preference exceeds the safety limit", 4)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=user_config._unique_object)
        return user_config._validate_config_value(source, scope, path, value)
    except (UnicodeError, ValueError, TypeError, user_config.UserConfigError) as error:
        raise TransactionError(f"User-settings preference evidence is invalid: {error}", 4) from error


def _settings_changed_config(source: Path, record: dict, old_raw: bytes | None, new_raw: bytes | None):
    from . import user_config

    old_config = _settings_config_value(source, record["scope"], old_raw,
                                        Path(".opencode/olympus-config.json") if record["scope"] == "project"
                                        else Path(record["preference_target"]["path"]))
    expected = json.loads(json.dumps(old_config))
    change = record["change"]
    if change["kind"] == "override":
        override = dict(expected["overrides"].get(record["role"], {}))
        override[change["field"]] = change["value"]
        expected["overrides"][record["role"]] = override
    else:
        expected["orchestration"] = {"max_children": change["value"]}
    expected_raw = (json.dumps(expected, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if new_raw is not None and expected_raw != new_raw:
        raise TransactionError("User-settings record does not describe exactly one supported preference change", 4)
    return old_config, expected, expected_raw


def _settings_initial_temp(target: Path, source: Path, lock, scope: str):
    scratch = target / _SCRATCH
    top = set(os.listdir(scratch))
    if top != {".record.json.tmp"}:
        raise TransactionError("Unpublished user-settings scratch is ambiguous; evidence was preserved", 4)
    raw, metadata = _bounded_read(target, f"{_SCRATCH}/.record.json.tmp", 6_000_000)
    try:
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=source_edit._json_object_no_duplicates)
    except (UnicodeError, ValueError, TypeError) as error:
        raise TransactionError("Unpublished user-settings record is invalid; evidence was preserved", 4) from error
    expected_mode = 0o666 if os.name == "nt" else 0o600
    if (not isinstance(record, dict) or record.get("kind") != _SETTINGS_KIND
            or record.get("state") != "PREPARING" or raw != _canonical_record(record)
            or not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != expected_mode):
        raise TransactionError("Unpublished user-settings record is not a canonical PREPARING record", 4)
    file_map = _settings_validate_record(target, source, lock, record, scope)

    current: dict[str, bytes | None] = {}
    for relative, entry in file_map.items():
        value, target_metadata = _settings_read_target(target, record, relative)
        if (_hash(value) if value is not None else None) != entry["old_sha256"] or (
                target_metadata is not None and stat.S_IMODE(target_metadata.st_mode) != entry["mode"]
                or target_metadata is None and entry["old_sha256"] is not None):
            raise TransactionError(
                f"Unpublished user-settings record has changed destinations: {relative}", 4,
            )
        current[relative] = value

    old_manifest = base64.b64decode(record["manifest_old_b64"], validate=True)
    new_manifest = base64.b64decode(record["manifest_new_b64"], validate=True)
    agent_paths = _settings_agent_paths(record)
    _, old_entries, new_entries = _settings_manifest_data(
        target, source, record, old_manifest, new_manifest,
    )
    for relative, digest in old_entries.items():
        value, _ = _global_target(target, relative)
        if (value is None or _hash(value) != digest
                or relative not in agent_paths and new_entries.get(relative) != digest):
            raise TransactionError(f"Unpublished user-settings receipt drifted: {relative}", 4)
    for relative in agent_paths:
        agent_entry = file_map[relative]
        if (old_entries.get(relative) != agent_entry["old_sha256"]
                or new_entries.get(relative) != agent_entry["new_sha256"]):
            raise TransactionError("Unpublished user-settings agent receipt contradicts its record", 4)
    preference_path = ".opencode/olympus-config.json" if scope == "project" else _SETTINGS_PREFERENCES
    old_config, new_config, new_preference = _settings_changed_config(
        source, record, current[preference_path], None,
    )
    if _hash(new_preference) != file_map[preference_path]["new_sha256"]:
        raise TransactionError("Unpublished user-settings preference receipt is inconsistent", 4)
    old_agents = {relative: current[relative] for relative in agent_paths}
    if any(agent is None for agent in old_agents.values()):
        raise TransactionError("Unpublished user-settings agent is missing", 4)
    new_agents = _settings_derive_new_agents(source, record, old_config, new_config, old_agents)
    if any(_hash(new_agents[relative]) != file_map[relative]["new_sha256"] for relative in agent_paths):
        raise TransactionError("Unpublished user-settings agent receipt is inconsistent", 4)
    _settings_agent_binding(source, record, old_config, new_config, old_agents, new_agents)

    for relative, entry in file_map.items():
        value, target_metadata = _settings_read_target(target, record, relative)
        if (_hash(value) if value is not None else None) != entry["old_sha256"] or (
                target_metadata is not None and stat.S_IMODE(target_metadata.st_mode) != entry["mode"]
                or target_metadata is None and entry["old_sha256"] is not None):
            raise TransactionError(f"Unpublished user-settings destination changed before promotion: {relative}", 4)
    for relative, digest in old_entries.items():
        value, _ = _global_target(target, relative)
        if value is None or _hash(value) != digest:
            raise TransactionError(f"Unpublished managed resource changed before promotion: {relative}", 4)

    identity = source_edit._lock_identity(lock)
    temp_path = scratch / ".record.json.tmp"
    record_path = scratch / _RECORD
    try:
        os.lstat(record_path)
    except FileNotFoundError:
        pass
    else:
        raise TransactionError("Unpublished user-settings record path unexpectedly exists", 4)
    again, again_metadata = _bounded_read(target, f"{_SCRATCH}/.record.json.tmp", 6_000_000)
    if (again != raw or (again_metadata.st_dev, again_metadata.st_ino)
            != (metadata.st_dev, metadata.st_ino)):
        raise TransactionError("Unpublished user-settings record changed before promotion", 4)
    source_edit._lock_identity(lock, identity)
    try:
        os.replace(temp_path, record_path)
    except OSError as error:
        raise TransactionError(f"Cannot promote verified user-settings record: {error}", 4) from error
    source_edit._sync_directory(scratch)
    promoted, promoted_metadata = _read(target, f"{_SCRATCH}/{_RECORD}")
    if (promoted != raw or (promoted_metadata.st_dev, promoted_metadata.st_ino)
            != (metadata.st_dev, metadata.st_ino)):
        raise TransactionError("Promoted user-settings record failed identity verification", 4)
    return record, promoted, promoted_metadata


def _settings_effective(source: Path, scope: str, role: str, config: dict,
                        project_fallback: dict | None = None):
    from . import models_catalog, user_config

    rows = {row["role"]: row for row in user_config._canonical_rows(source)}
    override = config["overrides"].get(role, {})
    fallback = project_fallback or {}
    model = override.get("model", fallback.get("model", rows[role]["models"]["opencode"]))
    effort = override.get("effort", fallback.get("effort", rows[role]["effort"]))
    try:
        models_catalog.validate_assignment(model, effort, source)
    except models_catalog.CatalogError as error:
        raise TransactionError(f"User-settings effective assignment is invalid: {error}", 4) from error
    return model, effort


def _settings_manifest_data(target: Path, source: Path, record: dict, old_raw: bytes, new_raw: bytes):
    from . import config_apply, global_readonly, install_manifest
    from .cli import load_renderer

    try:
        renderer = load_renderer(source)
        if record["scope"] == "global":
            expected = global_readonly._expected(source, renderer, ("opencode",))["opencode"]
            old_data, old_entries = global_readonly._parse_manifest_bytes(old_raw, "opencode", expected)
            new_data, new_entries = global_readonly._parse_manifest_bytes(new_raw, "opencode", expected)
        else:
            expected = config_apply._render_managed_outputs(source, renderer, ("opencode",))["opencode"]
            old_manifest = install_manifest.parse_project_manifest(
                target, target / record["manifest_path"], old_raw,
            )
            new_manifest = install_manifest.parse_project_manifest(
                target, target / record["manifest_path"], new_raw,
            )
            if (old_manifest.installed_version in config_apply._LEGACY_PROJECT_MANIFEST_VERSIONS
                    or new_manifest.installed_version in config_apply._LEGACY_PROJECT_MANIFEST_VERSIONS):
                raise TransactionError(
                    "Legacy project manifest receipt cannot be recovered; "
                    "uninstall with its source version, then install the current release.",
                    4,
                )
            old_data, new_data = old_manifest.data, new_manifest.data
            old_entries = {item["path"]: item["sha256"].lower() for item in old_data["managed_files"]}
            new_entries = {item["path"]: item["sha256"].lower() for item in new_data["managed_files"]}
            if set(old_entries) != set(expected) or set(new_entries) != set(expected):
                raise TransactionError("Project user-settings manifest inventory is incomplete or unsupported", 4)
    except TransactionError:
        raise
    except Exception as error:
        raise TransactionError(f"Cannot validate user-settings manifest receipts: {error}", 4) from error

    agent_paths = _settings_agent_paths(record)
    if (set(old_entries) != set(new_entries)
            or {key: value for key, value in old_data.items() if key != "managed_files"}
            != {key: value for key, value in new_data.items() if key != "managed_files"}):
        raise TransactionError("User-settings manifest changed ownership or non-hash metadata", 4)
    for relative in old_entries:
        if relative not in agent_paths and old_entries[relative] != new_entries[relative]:
            raise TransactionError(f"User-settings manifest changed an unrelated receipt: {relative}", 4)
    return expected, old_entries, new_entries


def _settings_expected_max_children_agents(source: Path, config: dict, value: int) -> dict[str, bytes]:
    from . import global_readonly, user_config
    from .cli import load_renderer

    expected = global_readonly._expected(
        source, load_renderer(source), ("opencode",), max_children=value,
    )["opencode"]
    user_config._apply_config_to_expected(source, expected, config)
    return {relative: expected[relative] for relative in ("agents/kael.md", "agents/atlas.md")}


def _settings_agent_binding(source: Path, record: dict, old_config: dict, new_config: dict,
                            old_agents: dict[str, bytes | None],
                            new_agents: dict[str, bytes | None]) -> None:
    from . import user_config

    role = record["role"]
    change = record["change"]
    scope = record["scope"]
    agent_paths = _settings_agent_paths(record)
    entries = {entry["path"]: entry for entry in record["files"]}
    if change["kind"] == "max_children":
        children_old = old_config.get("orchestration", {}).get("max_children", 4)
        children_new = new_config["orchestration"]["max_children"]
        expected_old = _settings_expected_max_children_agents(source, old_config, children_old)
        expected_new = _settings_expected_max_children_agents(source, new_config, children_new)
        for relative in agent_paths:
            old_agent, new_agent = old_agents.get(relative), new_agents.get(relative)
            entry = entries[relative]
            if (_hash(expected_new[relative]) != entry["new_sha256"]
                    or new_agent is not None and new_agent != expected_new[relative]
                    or old_config != new_config and old_agent is not None
                    and (old_agent != expected_old[relative]
                         or _hash(expected_old[relative]) != entry["old_sha256"])):
                raise TransactionError(
                    "User-settings primary agents do not match the recorded old/new preferences", 4,
                )
        return

    old_agent, new_agent = old_agents.get(record["agent_path"]), new_agents.get(record["agent_path"])
    fallback = record["project_fallback"]
    old_model, old_effort = _settings_effective(source, scope, role, old_config, fallback)
    new_model, new_effort = _settings_effective(source, scope, role, new_config, fallback)
    unchanged_preferences = old_config == new_config
    if old_agent is not None:
        try:
            text = old_agent.decode("utf-8")
        except UnicodeError as error:
            raise TransactionError("Recorded old role agent is not UTF-8 text", 4) from error
        matches = list(user_config._AGENT_MODEL.finditer(text))
        old_assignment = (
            (matches[0].group(1) or matches[0].group(2).strip()) if len(matches) == 1 else None
        )
        derived_new = user_config._replace_agent_model(old_agent, new_model, new_effort, role)
        if scope == "project":
            old_overrides = old_config["overrides"].get(role, {})
            old_parts = old_assignment.split("#", 1) if old_assignment is not None else []
            old_preferences_match = (
                len(old_parts) == 2
                and ("model" not in old_overrides or old_parts[0] == old_overrides["model"])
                and ("effort" not in old_overrides or old_parts[1] == old_overrides["effort"])
            )
        else:
            old_preferences_match = old_assignment == f"{old_model}#{old_effort}"
        if ((not unchanged_preferences and not old_preferences_match)
                or _hash(derived_new) != entries[record["agent_path"]]["new_sha256"]
                or new_agent is not None and derived_new != new_agent):
            raise TransactionError("User-settings old agent is not bound to the exact old/new preferences", 4)
    if new_agent is not None:
        try:
            text = new_agent.decode("utf-8")
        except UnicodeError as error:
            raise TransactionError("Recorded new role agent is not UTF-8 text", 4) from error
        matches = list(user_config._AGENT_MODEL.finditer(text))
        new_assignment = (
            (matches[0].group(1) or matches[0].group(2).strip()) if len(matches) == 1 else None
        )
        if new_assignment != f"{new_model}#{new_effort}":
            raise TransactionError("User-settings new agent is not bound to the exact old/new preferences", 4)


def _settings_new_agent_binding(source: Path, record: dict, new_config: dict,
                                new_agents: dict[str, bytes]) -> None:
    from . import user_config

    role = record["role"]
    if record["change"]["kind"] == "max_children":
        expected = _settings_expected_max_children_agents(
            source, new_config, new_config.get("orchestration", {}).get("max_children", 4),
        )
        if any(new_agents.get(relative) != expected[relative] for relative in _settings_agent_paths(record)):
            raise TransactionError("Committed primary agents do not match the recorded preferences", 4)
        return
    new_agent = new_agents[record["agent_path"]]
    model, effort = _settings_effective(
        source, record["scope"], role, new_config, record["project_fallback"],
    )
    if user_config._replace_agent_model(new_agent, model, effort, role) != new_agent:
        raise TransactionError("Committed role agent does not match the recorded preferences", 4)


def _settings_derive_new_agents(source: Path, record: dict, old_config: dict, new_config: dict,
                               old_agents: dict[str, bytes | None]) -> dict[str, bytes]:
    from . import user_config

    role = record["role"]
    if record["change"]["kind"] == "max_children":
        return _settings_expected_max_children_agents(
            source, new_config, new_config.get("orchestration", {}).get("max_children", 4),
        )
    old_agent = old_agents[record["agent_path"]]
    if old_agent is None:
        raise TransactionError("Unpublished user-settings agent is missing", 4)
    model, effort = _settings_effective(
        source, record["scope"], role, new_config, record["project_fallback"],
    )
    return {record["agent_path"]: user_config._replace_agent_model(old_agent, model, effort, role)}


def _settings_validate_new_preference(record: dict, config: dict) -> None:
    change = record["change"]
    if change["kind"] == "override":
        actual = config["overrides"].get(record["role"], {}).get(change["field"])
    else:
        actual = config.get("orchestration", {}).get("max_children")
    if actual != change["value"] or (
            change["kind"] == "max_children" and type(actual) is not int):
        raise TransactionError("Committed preference does not contain the recorded setter value", 4)


def _settings_read_target(target: Path, record: dict, relative: str):
    if relative == _SETTINGS_PREFERENCES and record["scope"] == "global":
        descriptor = record["preference_target"]
        parent_identity = (descriptor["parent_identity"]["st_dev"], descriptor["parent_identity"]["st_ino"])
        return _settings_external_read(Path(descriptor["path"]), parent_identity)
    return _global_target(target, relative)


def _settings_inspect(target: Path, source: Path, lock, record: dict, record_raw: bytes,
                      record_metadata: os.stat_result, *, expected_states: dict[str, str] | None = None,
                      require_backups: set[str] | None = None, require_staged: set[str] | None = None):
    identity = source_edit._lock_identity(lock)
    file_map = _settings_validate_record(target, source, lock, record, record["scope"])
    current_record, current_metadata = _read(target, f"{_SCRATCH}/{_RECORD}")
    if (current_record != record_raw
            or (current_metadata.st_dev, current_metadata.st_ino)
            != (record_metadata.st_dev, record_metadata.st_ino)):
        raise TransactionError("Authoritative user-settings record changed", 4)
    states = {}
    for relative, entry in file_map.items():
        current, metadata = _settings_read_target(target, record, relative)
        digest = _hash(current) if current is not None else None
        if entry["old_sha256"] == entry["new_sha256"] and digest == entry["old_sha256"]:
            state = "same"
        elif digest == entry["old_sha256"]:
            state = "old"
        elif digest == entry["new_sha256"]:
            state = "new"
        else:
            raise TransactionError(f"User-settings target has an external third state: {relative}", 4)
        if (metadata is not None and stat.S_IMODE(metadata.st_mode) != entry["mode"]
                or metadata is None and state != "old"):
            raise TransactionError(f"User-settings target mode or presence changed: {relative}", 4)
        if expected_states is not None and expected_states.get(relative) != state:
            raise TransactionError(f"User-settings target changed unexpectedly: {relative}", 4)
        states[relative] = state
    old_manifest = base64.b64decode(record["manifest_old_b64"], validate=True)
    new_manifest = base64.b64decode(record["manifest_new_b64"], validate=True)
    expected, old_entries, new_entries = _settings_manifest_data(
        target, source, record, old_manifest, new_manifest,
    )
    agent_paths = _settings_agent_paths(record)
    for relative in agent_paths:
        agent_entry = file_map[relative]
        if (old_entries.get(relative) != agent_entry["old_sha256"]
                or new_entries.get(relative) != agent_entry["new_sha256"]):
            raise TransactionError("User-settings manifest receipt contradicts a recorded role agent", 4)
    for relative, digest in old_entries.items():
        if relative in agent_paths:
            continue
        current, _ = _global_target(target, relative)
        if current is None or _hash(current) != digest or new_entries.get(relative) != digest:
            raise TransactionError(f"Unchanged manifest-owned resource drifted: {relative}", 4)
    artifacts = _settings_artifacts(target, record, file_map, required_backups=require_backups,
                                    required_staged=require_staged)
    old_agents, new_agents = {}, {}
    for relative in agent_paths:
        entry = file_map[relative]
        old_backup = artifacts.get(f"{_SCRATCH}/{entry['backup']}")
        old_agents[relative] = old_backup[0] if old_backup is not None else (
            _settings_read_target(target, record, relative)[0]
            if states[relative] in ("old", "same") else None
        )
        staged_agent = artifacts.get(f"{_SCRATCH}/{entry['staged']}")
        new_agents[relative] = staged_agent[0] if staged_agent is not None else (
            _settings_read_target(target, record, relative)[0]
            if states[relative] in ("new", "same") else None
        )
    preference_entry = file_map[
        ".opencode/olympus-config.json" if record["scope"] == "project" else _SETTINGS_PREFERENCES
    ]
    preference_path = preference_entry["path"]
    preference_state = states[preference_path]
    preference_backup = (
        artifacts.get(f"{_SCRATCH}/{preference_entry['backup']}")
        if preference_entry["old_sha256"] is not None else None
    )
    staged_preference = artifacts.get(f"{_SCRATCH}/{preference_entry['staged']}")
    current_preference, _ = _settings_read_target(target, record, preference_path)
    config_path = (Path(".opencode/olympus-config.json") if record["scope"] == "project"
                   else Path(record["preference_target"]["path"]))
    if (preference_backup is not None or preference_state in ("old", "same")
            or preference_entry["old_sha256"] is None):
        old_preference = preference_backup[0] if preference_backup is not None else (
            current_preference if preference_state in ("old", "same") else None
        )
        old_config, new_config, expected_new_preference = _settings_changed_config(
            source, record, old_preference, None,
        )
        if _hash(expected_new_preference) != preference_entry["new_sha256"]:
            raise TransactionError("Recorded preference hash contradicts its supported setter operation", 4)
        if (preference_state == "new" and current_preference != expected_new_preference
                or staged_preference is not None and staged_preference[0] != expected_new_preference):
            raise TransactionError("User-settings preference bytes contradict their exact old/new transition", 4)
        new_preference = expected_new_preference
    else:
        if current_preference is None or _hash(current_preference) != preference_entry["new_sha256"]:
            raise TransactionError("Committed user preferences are missing or do not match their recorded hash", 4)
        new_preference = current_preference
        new_config = _settings_config_value(source, record["scope"], new_preference, config_path)
        _settings_validate_new_preference(record, new_config)
        old_config = None
    if old_config is None:
        if any(states[relative] not in ("new", "same") for relative in agent_paths):
            raise TransactionError("Preferences are committed but a managed agent is not at its new state", 4)
        for relative in agent_paths:
            if new_agents[relative] is None:
                new_agents[relative] = _settings_read_target(target, record, relative)[0]
        _settings_new_agent_binding(source, record, new_config, new_agents)
    else:
        _settings_agent_binding(source, record, old_config, new_config, old_agents, new_agents)
    return {"identity": identity, "file_map": file_map, "states": states, "artifacts": artifacts,
            "old_entries": old_entries, "new_entries": new_entries,
            "preference_state": preference_state, "old_config": old_config, "new_config": new_config}


def _settings_expected_state(file_map: dict[str, dict], *, new: bool) -> dict[str, str]:
    result = {}
    for relative, entry in file_map.items():
        result[relative] = ("same" if entry["old_sha256"] == entry["new_sha256"]
                            else "new" if new else "old")
    return result


def _settings_final_state(target: Path, record: dict, file_map: dict[str, dict],
                          expected_states: dict[str, str]) -> None:
    for relative, entry in file_map.items():
        current, metadata = _settings_read_target(target, record, relative)
        state = expected_states[relative]
        digest = _hash(current) if current is not None else None
        expected_digest = entry["old_sha256"] if state in ("old", "same") else entry["new_sha256"]
        if digest != expected_digest or (
                metadata is not None and stat.S_IMODE(metadata.st_mode) != entry["mode"]
                or metadata is None and expected_digest is not None):
            raise TransactionError(f"User-settings destination changed during cleanup: {relative}", 4)


def _settings_cleanup(target: Path, source: Path, lock, record: dict, record_raw: bytes,
                      record_metadata: os.stat_result, file_map: dict[str, dict],
                      expected_states: dict[str, str]) -> None:
    identity = source_edit._lock_identity(lock)
    scratch = target / _SCRATCH
    _ensure_scratch_identity(target, record)
    live = _settings_inspect(
        target, source, lock, record, record_raw, record_metadata,
        expected_states=expected_states,
    )
    artifacts = live["artifacts"]
    for relative, (raw, metadata) in artifacts.items():
        _safe_remove(target, relative, raw, stat.S_IMODE(metadata.st_mode), lock, identity)
    for directory in ("staged", "backups"):
        try:
            os.lstat(scratch / directory)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise TransactionError(f"Cannot inspect user-settings directory {directory}: {error}", 4) from error
        try:
            source_edit._checked_path(target, f"{_SCRATCH}/{directory}", kind="directory")
        except source_edit.BatchError as error:
            raise TransactionError(str(error), 4) from error
        source_edit._lock_identity(lock, identity)
        try:
            os.rmdir(scratch / directory)
        except OSError as error:
            raise TransactionError(f"Cannot remove nonempty user-settings directory {directory}", 4) from error
    current, metadata = _read(target, f"{_SCRATCH}/{_RECORD}")
    if (current != record_raw or (metadata.st_dev, metadata.st_ino)
            != (record_metadata.st_dev, record_metadata.st_ino)):
        raise TransactionError("User-settings record changed during cleanup", 4)
    _settings_inspect(
        target, source, lock, record, record_raw, record_metadata,
        expected_states=expected_states,
    )
    _settings_final_state(target, record, file_map, expected_states)
    _safe_remove(target, f"{_SCRATCH}/{_RECORD}", record_raw, stat.S_IMODE(record_metadata.st_mode), lock, identity)
    source_edit._lock_identity(lock, identity)
    scratch_metadata = os.lstat(scratch)
    if ((scratch_metadata.st_dev, scratch_metadata.st_ino)
            != (record["scratch_identity"]["st_dev"], record["scratch_identity"]["st_ino"])
            or os.listdir(scratch)):
        raise TransactionError("User-settings scratch changed during final cleanup", 4)
    try:
        os.rmdir(scratch)
    except OSError as error:
        raise TransactionError(f"Cannot remove empty user-settings scratch: {error}", 4) from error
    source_edit._sync_directory(target)


def _settings_publish(target: Path, source: Path, lock, record: dict, relative: str,
                      expected_old: bytes | None, content: bytes, mode: int, *,
                      stage_relative: str | None = None, root_check=None) -> None:
    identity = source_edit._lock_identity(lock)
    if root_check is not None:
        root_check()
    if relative not in (*_settings_agent_paths(record), record["manifest_path"]):
        raise TransactionError("User-settings recovery may publish only its managed agents and manifest", 4)
    current, metadata = _global_target(target, relative)
    if current != expected_old or (
            current is not None and (metadata is None or stat.S_IMODE(metadata.st_mode) != mode)):
        raise TransactionError(f"User-settings target changed before replacement: {relative}", 4)
    if stage_relative is None:
        index = next(index for index, entry in enumerate(record["files"]) if entry["path"] == relative)
        stage_relative = f"{_SCRATCH}/staged/rollback-file-{index:04d}.old"
        if _artifact(target, stage_relative, _hash(content), mode, required=False) is None:
            source_edit._write_private_file(
                target / stage_relative, target, stage_relative, content, mode, lock, identity,
            )
    staged, staged_metadata = _read(target, stage_relative)
    if staged != content or stat.S_IMODE(staged_metadata.st_mode) != mode:
        raise TransactionError(f"User-settings staged bytes changed: {relative}", 4)
    current, metadata = _global_target(target, relative)
    if current != expected_old or (
            current is not None and (metadata is None or stat.S_IMODE(metadata.st_mode) != mode)):
        raise TransactionError(f"User-settings target changed immediately before replacement: {relative}", 4)
    source_edit._lock_identity(lock, identity)
    try:
        os.replace(target / stage_relative, target / relative)
    except OSError as error:
        raise TransactionError(f"Cannot replace user-settings target {relative}: {error}", 4) from error
    replaced, replaced_metadata = _global_target(target, relative)
    if replaced != content or replaced_metadata is None or stat.S_IMODE(replaced_metadata.st_mode) != mode:
        raise TransactionError(f"Replaced user-settings target failed verification: {relative}", 4)
    source_edit._sync_directory((target / relative).parent)


def _recover_settings_cycle(target: Path, source: Path, lock, record: dict, record_raw: bytes,
                            record_metadata: os.stat_result, scope: str, *, root_check=None) -> str:
    file_map = _settings_validate_record(target, source, lock, record, scope)
    if record["state"] == "PREPARING":
        expected = _settings_expected_state(file_map, new=False)
        _settings_inspect(target, source, lock, record, record_raw, record_metadata,
                          expected_states=expected)
        _settings_cleanup(target, source, lock, record, record_raw, record_metadata, file_map, expected)
        return "discarded_incomplete_prepare"
    if record["state"] == "COMMITTED":
        expected = _settings_expected_state(file_map, new=True)
        _settings_inspect(target, source, lock, record, record_raw, record_metadata,
                          expected_states=expected)
        _settings_cleanup(target, source, lock, record, record_raw, record_metadata, file_map, expected)
        return "committed_cleanup"

    live = _settings_inspect(target, source, lock, record, record_raw, record_metadata)
    preference_path = ".opencode/olympus-config.json" if scope == "project" else _SETTINGS_PREFERENCES
    preference = file_map[preference_path]
    agent_paths = _settings_agent_paths(record)
    managed_paths = (*agent_paths, record["manifest_path"])
    preference_committed = (
        preference["old_sha256"] != preference["new_sha256"]
        and live["preference_state"] == "new"
    )
    if preference_committed:
        if any(live["states"][relative] not in ("new", "same") for relative in managed_paths):
            raise TransactionError(
                "Preferences reached their commit point before all managed resources reached the new state", 4,
            )
        expected = _settings_expected_state(file_map, new=True)
        _settings_cleanup(target, source, lock, record, record_raw, record_metadata, file_map, expected)
        return "committed_cleanup"

    required = {
        relative for relative in managed_paths
        if live["states"][relative] == "new" and file_map[relative]["old_sha256"] is not None
    }
    if required:
        live = _settings_inspect(
            target, source, lock, record, record_raw, record_metadata, require_backups=required,
        )
    if not required:
        expected = _settings_expected_state(file_map, new=False)
        _settings_cleanup(target, source, lock, record, record_raw, record_metadata, file_map, expected)
        return "discarded_uncommitted"

    for relative in (record["manifest_path"], *agent_paths):
        if live["states"][relative] in ("old", "same"):
            continue
        entry = file_map[relative]
        remaining = {
            path for path in managed_paths
            if path != relative and live["states"][path] == "new"
            and file_map[path]["old_sha256"] is not None
        }
        live = _settings_inspect(
            target, source, lock, record, record_raw, record_metadata, require_backups=remaining | {relative},
        )
        backup = _artifact(
            target, f"{_SCRATCH}/{entry['backup']}", entry["old_sha256"], entry["mode"], required=True,
        )[0]
        current, _ = _settings_read_target(target, record, relative)
        _settings_publish(
            target, source, lock, record, relative, current, backup, entry["mode"],
            root_check=root_check,
        )
        live = _settings_inspect(
            target, source, lock, record, record_raw, record_metadata,
            require_backups=remaining,
        )
    expected = _settings_expected_state(file_map, new=False)
    _settings_inspect(target, source, lock, record, record_raw, record_metadata, expected_states=expected)
    _settings_cleanup(target, source, lock, record, record_raw, record_metadata, file_map, expected)
    return "rolled_back"


def _settings_commit_preferences(target: Path, source: Path, lock, record: dict,
                                 expected_old: bytes | None, content: bytes, root_check=None) -> None:
    from . import user_config

    entry = next(item for item in record["files"] if item["path"] in (
        ".opencode/olympus-config.json", _SETTINGS_PREFERENCES,
    ))
    path = (target / entry["path"] if record["scope"] == "project"
            else Path(record["preference_target"]["path"]))
    mode = entry["mode"]
    identity = source_edit._lock_identity(lock)

    def verify_old() -> None:
        current, metadata = _settings_read_target(target, record, entry["path"])
        if current != expected_old or (
                metadata is not None and stat.S_IMODE(metadata.st_mode) != mode
                or metadata is None and expected_old is not None):
            raise TransactionError("User preferences changed before their atomic commit", 4)

    if root_check is not None:
        root_check()
    verify_old()
    source_edit._lock_identity(lock, identity)
    if root_check is not None:
        root_check()
    verify_old()
    try:
        user_config._write_atomic(path, content, mode=mode)
    except OSError as error:
        raise TransactionError(f"Cannot atomically commit user preferences: {error}", 4) from error
    current, metadata = _settings_read_target(target, record, entry["path"])
    if current != content or metadata is None or stat.S_IMODE(metadata.st_mode) != mode:
        raise TransactionError("Atomically committed user preferences failed verification", 4)


def commit_user_config(target: Path, source: Path, lock, scope: str, preference_path: Path,
                       preference_old: bytes | None, preference_new: bytes, installed,
                       change: dict, *, root_check=None, project_fallback: dict | None = None) -> str:
    """Journal setter updates that coordinate managed agents, receipts, and preferences."""
    target = Path(target).resolve(strict=True)
    identity = source_edit._lock_identity(lock)
    if pending(target):
        raise TransactionError("A pending Olympus transaction blocks user-settings changes", 3)
    from . import user_config

    agent_updates, manifest_path, manifest_old, manifest_new = installed
    agent_changes = []
    for agent_path, agent_old, agent_new in agent_updates:
        agent_relative = Path(agent_path).relative_to(target).as_posix()
        agent_current, agent_metadata = _global_target(target, agent_relative)
        if (agent_current != agent_old or agent_metadata is None
                or not isinstance(agent_new, bytes)):
            raise TransactionError(
                f"Managed agent changed before user-settings journal preparation: {agent_relative}", 3,
            )
        agent_changes.append((
            agent_relative, agent_old, agent_new, stat.S_IMODE(agent_metadata.st_mode),
        ))
    if not agent_changes or len({item[0] for item in agent_changes}) != len(agent_changes):
        raise TransactionError("User-settings journal requires distinct managed agent destinations", 3)
    manifest_relative = Path(manifest_path).relative_to(target).as_posix()
    if scope == "project":
        preference_target = {"relative": ".opencode/olympus-config.json"}
        preference_relative = ".opencode/olympus-config.json"
        observed_preference, preference_metadata = _global_target(target, preference_relative)
        if observed_preference != preference_old:
            raise TransactionError("Project preferences changed before journal preparation", 3)
    elif scope == "global":
        preference_target = _settings_preference_descriptor(
            scope, target, preference_path, create_parent=True,
        )
        preference_relative = _SETTINGS_PREFERENCES
        parent_identity = (
            preference_target["parent_identity"]["st_dev"],
            preference_target["parent_identity"]["st_ino"],
        )
        observed_preference, preference_metadata = _settings_external_read(preference_path, parent_identity)
        if observed_preference != preference_old:
            raise TransactionError("Global preferences changed before journal preparation", 3)
    else:
        raise TransactionError(f"Unsupported user-settings scope: {scope}", 3)

    manifest_current, manifest_metadata = _global_target(target, manifest_relative)
    if (manifest_current != manifest_old or manifest_metadata is None):
        raise TransactionError("Managed agent or manifest changed before user-settings journal preparation", 3)
    role = change.get("role", "kael")
    if len(preference_new) > _SETTINGS_LIMIT:
        raise TransactionError("User-settings preference exceeds the safety limit", 3)
    preference_mode = (
        stat.S_IMODE(preference_metadata.st_mode) if preference_metadata is not None
        else 0o666 if os.name == "nt" else 0o600
    )
    changes = [
        *agent_changes,
        (manifest_relative, manifest_old, manifest_new, stat.S_IMODE(manifest_metadata.st_mode)),
        (preference_relative, preference_old, preference_new, preference_mode),
    ]
    files = [{
        "path": relative, "old_sha256": _hash(old) if old is not None else None,
        "new_sha256": _hash(new), "mode": file_mode,
        "backup": f"backups/file-{index:04d}.old", "staged": f"staged/file-{index:04d}.new",
    } for index, (relative, old, new, file_mode) in enumerate(changes)]
    if root_check is not None:
        root_check()
    record = {
        "schema_version": 1, "kind": _SETTINGS_KIND, "scope": scope, "operation_id": uuid.uuid4().hex,
        "target_root": str(target), "scratch_identity": {"st_dev": 0, "st_ino": 0},
        "lock_identity": {"path": source_edit._LOCK_NAME, "st_dev": identity[0], "st_ino": identity[1]},
        "state": "PREPARING", "role": role, "change": change,
        "agent_path": agent_changes[0][0], "manifest_path": manifest_relative,
        "preference_target": preference_target, "project_fallback": project_fallback,
        "manifest_old_b64": base64.b64encode(manifest_old).decode("ascii"),
        "manifest_new_b64": base64.b64encode(manifest_new).decode("ascii"), "files": files,
    }
    record, record_raw, record_metadata = _write_record_new(target, record, lock, identity)
    scratch = target / _SCRATCH
    prepared = False
    try:
        source_edit._make_directory(scratch / "backups", target, lock, identity)
        source_edit._make_directory(scratch / "staged", target, lock, identity)
        for (relative, old, new, file_mode), entry in zip(changes, files):
            source_edit._lock_identity(lock, identity)
            current, metadata = _settings_read_target(target, record, relative)
            if current != old or (
                    current is not None and (metadata is None or stat.S_IMODE(metadata.st_mode) != file_mode)):
                raise TransactionError(f"User-settings target drifted during preparation: {relative}", 3)
            if relative == preference_relative:
                continue
            if old is not None:
                backup_path = f"{_SCRATCH}/{entry['backup']}"
                source_edit._write_private_file(
                    target / backup_path, target, backup_path, old, file_mode, lock, identity,
                )
                backup, backup_metadata = _read(target, backup_path)
                if backup != old or stat.S_IMODE(backup_metadata.st_mode) != file_mode:
                    raise TransactionError(f"User-settings backup failed verification: {relative}", 4)
            staged_path = f"{_SCRATCH}/{entry['staged']}"
            source_edit._write_private_file(
                target / staged_path, target, staged_path, new, file_mode, lock, identity,
            )
            staged, staged_metadata = _read(target, staged_path)
            if staged != new or stat.S_IMODE(staged_metadata.st_mode) != file_mode:
                raise TransactionError(f"User-settings staged output failed verification: {relative}", 4)
        record, record_raw, record_metadata = _persist_record(
            target, scratch, {**record, "state": "PREPARED"}, lock, identity,
            previous=(record, record_raw, record_metadata),
        )
        file_map = _settings_validate_record(target, source, lock, record, scope)
        managed = (*(item[0] for item in agent_changes), manifest_relative)
        required = {relative for relative in managed if file_map[relative]["old_sha256"] is not None}
        _settings_inspect(
            target, source, lock, record, record_raw, record_metadata,
            expected_states=_settings_expected_state(file_map, new=False),
            require_backups=required, require_staged=set(managed),
        )
        prepared = True
        states = _settings_expected_state(file_map, new=False)
        for relative in managed:
            entry = file_map[relative]
            if entry["old_sha256"] == entry["new_sha256"]:
                continue
            current, _ = _settings_read_target(target, record, relative)
            staged = f"{_SCRATCH}/{entry['staged']}"
            content, content_metadata = _read(target, staged)
            if _hash(content) != entry["new_sha256"] or stat.S_IMODE(content_metadata.st_mode) != entry["mode"]:
                raise TransactionError(f"User-settings staged output changed: {relative}", 4)
            _settings_publish(
                target, source, lock, record, relative, current, content, entry["mode"],
                stage_relative=staged, root_check=root_check,
            )
            states[relative] = "new"
            _settings_inspect(
                target, source, lock, record, record_raw, record_metadata, expected_states=states,
                require_backups=required,
            )
        precommit_expected = _settings_expected_state(file_map, new=False)
        for relative in managed:
            precommit_expected[relative] = (
                "new" if file_map[relative]["old_sha256"] != file_map[relative]["new_sha256"] else "same"
            )
        _settings_inspect(
            target, source, lock, record, record_raw, record_metadata,
            expected_states=precommit_expected, require_backups=required,
        )
        preference_entry = file_map[preference_relative]
        if preference_entry["old_sha256"] != preference_entry["new_sha256"]:
            _settings_commit_preferences(
                target, source, lock, record, preference_old, preference_new, root_check,
            )
        expected = _settings_expected_state(file_map, new=True)
        _settings_inspect(
            target, source, lock, record, record_raw, record_metadata,
            expected_states=expected, require_backups=required,
        )
        record, record_raw, record_metadata = _persist_record(
            target, scratch, {**record, "state": "COMMITTED"}, lock, identity,
            previous=(record, record_raw, record_metadata),
        )
        _settings_inspect(
            target, source, lock, record, record_raw, record_metadata, expected_states=expected,
        )
        _settings_cleanup(target, source, lock, record, record_raw, record_metadata, file_map, expected)
        return "committed"
    except Exception as error:
        try:
            context = (_global_record_context(target, lock, {}, source=source) if scope == "global"
                       else _record_context(target, lock, settings_source=source))
            if context is not None and context[0].get("operation_id") == record["operation_id"]:
                current_record, current_raw, current_metadata = context
                if current_record["state"] == "COMMITTED":
                    raise TransactionError(
                        f"User-settings update is COMMITTED but cleanup remains pending: {error}", 4,
                    ) from error
                result = _recover_settings_cycle(
                    target, source, lock, current_record, current_raw, current_metadata, scope,
                    root_check=root_check,
                )
                if result in ("rolled_back", "discarded_uncommitted", "discarded_incomplete_prepare"):
                    raise TransactionError(
                        f"User-settings update failed; rollback was confirmed: {error}", 1,
                    ) from error
                if result == "committed_cleanup":
                    return "committed"
        except TransactionError as recovery_error:
            if "rollback was confirmed" in str(recovery_error):
                raise
            raise TransactionError(
                f"User-settings update failed and recovery could not be confirmed: {error}; {recovery_error}", 4,
            ) from error
        if prepared:
            raise TransactionError(f"User-settings update failed with unconfirmed state: {error}", 4) from error
        raise TransactionError(f"User-settings preparation failed with unconfirmed state: {error}", 4) from error


def _is_linux_lifecycle_journal(target: Path) -> bool:
    scratch = target / _SCRATCH
    try:
        scratch_metadata = os.lstat(scratch)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise TransactionError(f"Cannot inspect global recovery scratch: {error}", 4) from error
    if (not stat.S_ISDIR(scratch_metadata.st_mode) or stat.S_ISLNK(scratch_metadata.st_mode)
            or getattr(scratch_metadata, "st_file_attributes", 0) & _REPARSE_POINT):
        raise TransactionError("Global recovery scratch is linked or not a directory; preserve its evidence", 4)
    record_path = scratch / _RECORD
    try:
        record_metadata = os.lstat(record_path)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise TransactionError(f"Cannot inspect global recovery record: {error}", 4) from error
    if (not stat.S_ISREG(record_metadata.st_mode) or stat.S_ISLNK(record_metadata.st_mode)
            or getattr(record_metadata, "st_file_attributes", 0) & _REPARSE_POINT
            or record_metadata.st_size > 6_000_000):
        raise TransactionError("Global recovery record is unsafe or oversized; preserve its evidence", 4)
    raw, _ = _bounded_read(target, f"{_SCRATCH}/{_RECORD}", 6_000_000)
    try:
        record = json.loads(
            raw.decode("utf-8"), object_pairs_hook=source_edit._json_object_no_duplicates,
        )
    except (UnicodeError, ValueError, TypeError):
        return False
    return isinstance(record, dict) and record.get("kind") == "linux_global_lifecycle"


def recover_global(target: Path, source: Path, *, load_renderer) -> str:
    """Explicitly roll back one PREPARED global apply or clean a COMMITTED journal."""
    from . import global_readonly

    target = global_readonly._root(target)
    if target.is_dir():
        target = target.resolve(strict=True)
    if sys.platform.startswith("linux") and _is_linux_lifecycle_journal(target):
        from . import global_install

        try:
            configured = global_readonly.resolve_roots(("opencode",))["opencode"]
            if configured.is_dir():
                configured = configured.resolve(strict=True)
            if configured != target:
                raise TransactionError(
                    "Lifecycle recovery target differs from the configured global OpenCode root", 4,
                )
            return global_install.recover(source).result
        except global_install.GlobalInstallError as error:
            raise TransactionError(str(error), error.code) from error
        except global_readonly.GlobalFault as error:
            raise TransactionError(str(error), error.code) from error
        except (OSError, RuntimeError) as error:
            raise TransactionError(f"Cannot resolve lifecycle recovery target: {error}", 4) from error
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
        context = _global_record_context(target, lock, expected, source=source)
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
