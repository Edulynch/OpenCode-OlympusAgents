"""Private stable-lock, fixed-batch, and explicit-recovery primitives for Slice B.

There is no public writer API here. Commit and recovery validate the concrete
T015 record while holding the stable lock and never inspect a pending batch
before acquiring it.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import tomllib
import types
import uuid
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


_LOCK_NAME = ".olympus-cli-edit.lock"
_SCRATCH_NAME = ".olympus-cli-edit"
_RECORD_NAME = "record.json"
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class LockError(RuntimeError):
    """The stable edit lock is missing, unsafe, or has changed identity."""


class LockBusy(LockError):
    """Another cooperating process owns the stable edit lock."""


class LockIdentityError(LockError):
    """The lock descriptor and canonical path no longer identify one file."""


class BatchError(RuntimeError):
    """A private Slice B batch could not be safely prepared."""


class BatchBlocked(BatchError):
    """A pending batch, unsafe resource, or active lock blocks preparation."""


class BatchConflict(BatchBlocked):
    """The candidate no longer matches its read-set or renderer outputs."""


@dataclass(slots=True)
class _Lock:
    path: Path
    descriptor: int
    identity: tuple[int, int]
    released: bool = False


@dataclass(frozen=True, slots=True)
class _PreparedBatch:
    """Receipt for a persisted PREPARED batch; original targets remain untouched."""

    operation_id: str
    source_root: Path
    scratch_path: Path
    record_path: Path
    write_set: tuple[str, ...]
    record: dict[str, Any]


def _canonical_source(source_root: os.PathLike[str] | str) -> Path:
    try:
        source = Path(source_root).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise LockError(f"Invalid canonical source root: {source_root}") from error
    if not source.is_dir():
        raise LockError(f"Canonical source root is not a directory: {source}")
    return source


def _file_identity(metadata: os.stat_result, description: str) -> tuple[int, int]:
    attributes = getattr(metadata, "st_file_attributes", 0)
    if attributes & _REPARSE_POINT or stat.S_ISLNK(metadata.st_mode):
        raise LockError(f"Lock may not be a link or reparse point: {description}")
    if not stat.S_ISREG(metadata.st_mode):
        raise LockError(f"Lock must be a regular file: {description}")
    if metadata.st_nlink != 1:
        raise LockError(f"Lock must not have hard-link aliases: {description}")
    if metadata.st_size != 0:
        raise LockError(f"Lock file must remain empty: {description}")
    identity = (metadata.st_dev, metadata.st_ino)
    if identity[0] < 0 or identity[1] <= 0:
        raise LockIdentityError(f"Filesystem did not provide a stable lock identity: {description}")
    return identity


def _lock_identity(lock: _Lock, expected: tuple[int, int] | None = None) -> tuple[int, int]:
    """Verify descriptor/path identity and return the stable (device, inode)."""
    if lock.released:
        raise LockIdentityError("Lock descriptor has already been released")
    try:
        descriptor_stat = os.fstat(lock.descriptor)
        path_stat = os.lstat(lock.path)
    except OSError as error:
        raise LockIdentityError(f"Cannot verify stable lock identity at {lock.path}") from error

    try:
        descriptor_identity = _file_identity(descriptor_stat, "open descriptor")
        path_identity = _file_identity(path_stat, str(lock.path))
    except LockError as error:
        raise LockIdentityError(f"Stable lock is no longer a safe regular file: {lock.path}") from error
    if descriptor_identity != path_identity or descriptor_identity != lock.identity:
        raise LockIdentityError(f"Stable lock path was substituted: {lock.path}")
    if expected is not None and descriptor_identity != expected:
        raise LockIdentityError(f"Stable lock identity contradicts the expected identity: {lock.path}")
    return descriptor_identity


def _acquire_lock(source_root: os.PathLike[str] | str, *, create: bool) -> _Lock:
    """Acquire the canonical source's stable lock without waiting.

    ``create=True`` is only for a preflight-approved real edit and uses
    exclusive creation. Recovery callers must use ``create=False``; that path
    never creates, truncates, or replaces the stable lock.
    """
    source = _canonical_source(source_root)
    path = source / _LOCK_NAME
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    try:
        if create:
            try:
                descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                descriptor = os.open(path, flags)
        else:
            descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.EMLINK):
            raise LockError(f"Lock may not be a link: {path}") from error
        raise LockError(f"Cannot open stable lock at {path}: {error}") from error

    acquired = False
    try:
        os.set_inheritable(descriptor, False)
        descriptor_stat = os.fstat(descriptor)
        initial_identity = _file_identity(descriptor_stat, "open descriptor")
        try:
            path_stat = os.lstat(path)
        except OSError as error:
            raise LockIdentityError(f"Stable lock path disappeared during acquisition: {path}") from error
        path_identity = _file_identity(path_stat, str(path))
        if initial_identity != path_identity:
            raise LockIdentityError(f"Stable lock path changed during acquisition: {path}")

        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EDEADLK) or getattr(error, "winerror", None) in (32, 33, 36):
                    raise LockBusy(f"Stable lock is owned by another process: {path}") from error
                raise LockError(f"Cannot acquire stable lock at {path}: {error}") from error
        else:
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EAGAIN):
                    raise LockBusy(f"Stable lock is owned by another process: {path}") from error
                raise LockError(f"Cannot acquire stable lock at {path}: {error}") from error

        acquired = True
        lock = _Lock(path=path, descriptor=descriptor, identity=initial_identity)
        _lock_identity(lock)
        return lock
    except BaseException:
        if acquired:
            try:
                _unlock_descriptor(descriptor)
            except OSError:
                pass
        os.close(descriptor)
        raise


def _unlock_descriptor(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _release_lock(lock: _Lock) -> None:
    """Release the OS lock and close its private, non-inheritable descriptor."""
    if lock.released:
        raise LockIdentityError("Lock descriptor has already been released")

    identity_error: LockIdentityError | None = None
    try:
        _lock_identity(lock)
    except LockIdentityError as error:
        identity_error = error

    unlock_error: OSError | None = None
    try:
        _unlock_descriptor(lock.descriptor)
    except OSError as error:
        unlock_error = error
    finally:
        try:
            os.close(lock.descriptor)
        finally:
            lock.released = True

    if identity_error is not None:
        raise identity_error
    if unlock_error is not None:
        raise LockError(f"Cannot release stable lock at {lock.path}: {unlock_error}") from unlock_error


def _mode_signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IMODE(metadata.st_mode),
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_nlink,
        getattr(metadata, "st_file_attributes", 0),
    )


def _safe_root_metadata(root: Path) -> os.stat_result:
    try:
        metadata = os.lstat(root)
    except OSError as error:
        raise BatchBlocked(f"Cannot inspect canonical source root: {root}") from error
    if (stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
            or not stat.S_ISDIR(metadata.st_mode)):
        raise BatchBlocked(f"Canonical source root is not a safe directory: {root}")
    return metadata


def _relative_parts(relative: str) -> tuple[str, ...]:
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or ":" in relative):
        raise BatchBlocked(f"Unsafe source-relative path: {relative!r}")
    parsed = PurePosixPath(relative)
    if (parsed.is_absolute() or parsed.as_posix() != relative
            or not parsed.parts or any(part in ("", ".", "..") for part in parsed.parts)):
        raise BatchBlocked(f"Unsafe source-relative path: {relative!r}")
    return parsed.parts


def _checked_path(root: Path, relative: str, *, kind: str) -> tuple[Path, os.stat_result]:
    """Walk a source-relative path with lstat checks; never follow a link."""
    if kind not in ("file", "directory"):
        raise ValueError(f"Unsupported resource kind: {kind}")
    root_metadata = _safe_root_metadata(root)
    current = root
    metadata = root_metadata
    parts = _relative_parts(relative)
    for index, part in enumerate(parts):
        current = current / part
        try:
            metadata = os.lstat(current)
        except OSError as error:
            raise BatchBlocked(f"Missing batch resource: {relative}") from error
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or attributes & _REPARSE_POINT:
            raise BatchBlocked(f"Linked/reparse batch resource is not accepted: {relative}")
        if metadata.st_dev != root_metadata.st_dev:
            raise BatchBlocked(f"Cross-filesystem batch resource is not accepted: {relative}")
        final = index == len(parts) - 1
        if not final and not stat.S_ISDIR(metadata.st_mode):
            raise BatchBlocked(f"Batch path contains a non-directory component: {relative}")
        if final and kind == "directory" and not stat.S_ISDIR(metadata.st_mode):
            raise BatchBlocked(f"Batch resource is not a directory: {relative}")
        if final and kind == "file":
            if not stat.S_ISREG(metadata.st_mode):
                raise BatchBlocked(f"Batch resource is not a regular file: {relative}")
            if metadata.st_nlink != 1:
                raise BatchBlocked(f"Hard-linked batch resource is not accepted: {relative}")
    return current, metadata


def _safe_read(root: Path, relative: str) -> tuple[bytes, os.stat_result]:
    path, before = _checked_path(root, relative, kind="file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise BatchBlocked(f"Cannot safely open batch resource {relative}: {error}") from error
    try:
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or getattr(opened, "st_file_attributes", 0) & _REPARSE_POINT):
            raise BatchBlocked(f"Batch resource changed identity while opening: {relative}")
        blocks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            blocks.append(block)
        after = os.fstat(descriptor)
        try:
            path_after = os.lstat(path)
        except OSError as error:
            raise BatchBlocked(f"Batch resource disappeared while reading: {relative}") from error
        if (_mode_signature(opened) != _mode_signature(after)
                or (after.st_dev, after.st_ino) != (path_after.st_dev, path_after.st_ino)):
            raise BatchConflict(f"Batch resource changed while reading: {relative}")
        return b"".join(blocks), after
    finally:
        os.close(descriptor)


def _add_snapshot_entry(
    root: Path,
    relative: str,
    signatures: dict[str, tuple[Any, ...]],
    contents: dict[str, bytes],
    *,
    kind: str,
) -> None:
    path, metadata = _checked_path(root, relative, kind=kind)
    if kind == "directory":
        signatures[relative] = ("directory", *_mode_signature(metadata))
        return
    content, stable = _safe_read(root, relative)
    signatures[relative] = (
        "file", *_mode_signature(stable), hashlib.sha256(content).hexdigest()
    )
    contents[relative] = content


def _candidate_snapshot(
    root: Path,
    outputs: dict[Path, str],
) -> tuple[dict[str, tuple[Any, ...]], dict[str, bytes]]:
    """Recreate T014's complete read-set without importing its TOML editor."""
    signatures: dict[str, tuple[Any, ...]] = {}
    contents: dict[str, bytes] = {}
    olympus = root / "olympus"

    def visit(directory: Path, relative: str, *, record_directory: bool) -> None:
        if record_directory:
            _add_snapshot_entry(root, relative, signatures, contents, kind="directory")
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as error:
            raise BatchBlocked(f"Cannot inventory renderer inputs under {relative}: {error}") from error
        for child in children:
            child_relative = child.relative_to(root).as_posix()
            try:
                metadata = os.lstat(child)
            except OSError as error:
                raise BatchBlocked(f"Cannot inspect renderer input {child_relative}") from error
            attributes = getattr(metadata, "st_file_attributes", 0)
            if stat.S_ISLNK(metadata.st_mode) or attributes & _REPARSE_POINT:
                raise BatchBlocked(f"Linked/reparse renderer input is not accepted: {child_relative}")
            if metadata.st_dev != _safe_root_metadata(root).st_dev:
                raise BatchBlocked(f"Cross-filesystem renderer input is not accepted: {child_relative}")
            if stat.S_ISDIR(metadata.st_mode):
                visit(child, child_relative, record_directory=True)
            elif stat.S_ISREG(metadata.st_mode):
                _add_snapshot_entry(root, child_relative, signatures, contents, kind="file")
            else:
                raise BatchBlocked(f"Non-regular renderer input is not accepted: {child_relative}")

    # T014 snapshots the contents below olympus/, not the root directory entry.
    visit(olympus, "olympus", record_directory=False)
    _add_snapshot_entry(root, "scripts", signatures, contents, kind="directory")
    _add_snapshot_entry(root, "scripts/render_harnesses.py", signatures, contents, kind="file")

    for output in sorted(outputs, key=lambda item: item.as_posix()):
        try:
            relative = output.relative_to(root).as_posix()
        except ValueError as error:
            raise BatchBlocked(f"Renderer output escapes the canonical source: {output}") from error
        parts = _relative_parts(relative)
        for index in range(1, len(parts)):
            parent_relative = "/".join(parts[:index])
            if parent_relative not in signatures:
                _add_snapshot_entry(root, parent_relative, signatures, contents, kind="directory")
        _add_snapshot_entry(root, relative, signatures, contents, kind="file")
    return signatures, contents


def _load_checked_renderer(root: Path):
    raw, _ = _safe_read(root, "scripts/render_harnesses.py")
    try:
        text = raw.decode("utf-8")
        module = types.ModuleType("_olympus_batch_renderer")
        module.__file__ = str(root / "scripts/render_harnesses.py")
        exec(compile(text, module.__file__, "exec"), module.__dict__)
    except (OSError, UnicodeError, SyntaxError) as error:
        raise BatchConflict(f"Cannot load canonical fixture renderer: {error}") from error
    return module


def _rendered_bytes(text: str, original: bytes, relative: str) -> bytes:
    if "\r" in text:
        raise BatchConflict(f"Renderer produced ambiguous carriage returns for {relative}")
    crlf_count = original.count(b"\r\n")
    without_crlf = original.replace(b"\r\n", b"")
    if b"\r" in without_crlf or (crlf_count and b"\n" in without_crlf):
        raise BatchConflict(f"Mixed or ambiguous newlines in renderer output {relative}")
    raw = text.encode("utf-8")
    return raw.replace(b"\n", b"\r\n") if crlf_count else raw


def _semantic_changes(before: Any, after: Any, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: set[tuple[str, ...]] = set()
        for key in set(before) | set(after):
            if key not in before or key not in after:
                changes.add((*prefix, str(key)))
            else:
                changes.update(_semantic_changes(before[key], after[key], (*prefix, str(key))))
        return changes
    return set() if before == after else {prefix}


def _candidate_source(candidate: Any) -> Path:
    try:
        original = Path(candidate.source_root)
        if not original.is_absolute():
            raise BatchBlocked("Candidate source root must be absolute")
        source = original.resolve(strict=True)
    except BatchBlocked:
        raise
    except (AttributeError, OSError, RuntimeError, TypeError) as error:
        raise BatchBlocked("Candidate has no valid canonical source root") from error
    if not source.is_dir():
        raise BatchBlocked(f"Candidate source is not a directory: {source}")
    _safe_root_metadata(source)
    return source


def _validate_candidate(candidate: Any, source: Path) -> tuple[tuple[Any, ...], dict[str, tuple[Any, ...]], dict[str, bytes]]:
    """Validate candidate provenance, full read-set, write-set and renderer bytes."""
    try:
        preview = candidate.preview
        preview_data = preview["data"]
        operation = preview["operation"]
        read_set = candidate.read_set
        files = tuple(candidate.files)
    except (AttributeError, KeyError, TypeError) as error:
        raise BatchBlocked("Candidate is incomplete or has an unsupported shape") from error
    if operation not in ("models set-family", "agents set-model"):
        raise BatchBlocked(f"Unsupported candidate operation: {operation!r}")
    if preview.get("schema_version") != 1 or preview.get("context", {}).get("source") != str(source):
        raise BatchConflict("Candidate schema or canonical source context changed")
    if not isinstance(read_set, dict):
        raise BatchBlocked("Candidate read-set is not an inventory")

    # Inspect the source tree and renderer before executing the canonical renderer.
    _checked_path(source, "scripts/render_harnesses.py", kind="file")
    _checked_path(source, "olympus", kind="directory")
    renderer = _load_checked_renderer(source)
    preliminary, _ = _candidate_snapshot(source, {})
    preliminary_drift = [path for path, signature in preliminary.items()
                         if read_set.get(path) != signature]
    if preliminary_drift:
        raise BatchConflict(
            "Candidate source/read-set drifted before renderer validation: "
            + ", ".join(
                f"{path} (saved={read_set.get(path)!r}, current={preliminary[path]!r})"
                for path in preliminary_drift[:3]
            )
        )
    try:
        old_models, policies, capabilities, identities, roles = renderer.checked_sources(source)
        old_outputs = renderer.outputs_for(source, "all")
        if not isinstance(old_outputs, dict) or not old_outputs:
            raise BatchConflict("Canonical renderer returned no managed outputs")
    except BatchError:
        raise
    except Exception as error:
        raise BatchConflict(f"Canonical renderer rejected the fixture source: {error}") from error

    current_read_set, contents = _candidate_snapshot(source, old_outputs)
    if current_read_set != read_set:
        raise BatchConflict("Candidate read-set drifted before batch preparation")

    file_by_path: dict[str, Any] = {}
    for item in files:
        try:
            relative = item.relative_path
            parts = _relative_parts(relative)
            expected_path = source.joinpath(*parts)
            path = Path(item.path)
            if path != expected_path or relative in file_by_path:
                raise BatchConflict(f"Candidate has an invalid or duplicate target: {relative!r}")
            file_by_path[relative] = item
        except (AttributeError, TypeError) as error:
            raise BatchBlocked("Candidate contains an invalid target entry") from error
    if list(file_by_path) != sorted(file_by_path):
        raise BatchConflict("Candidate targets are not in canonical path order")

    write_set = preview_data.get("write_set")
    if not isinstance(write_set, list) or write_set != list(file_by_path):
        raise BatchConflict("Candidate preview and file write-set disagree")
    no_op = not files
    if preview_data.get("no_op") is not no_op:
        raise BatchConflict("Candidate no-op flag disagrees with its files")
    if no_op:
        if (preview.get("result") != "no_changes"
                or preview_data.get("models_toml_changed") is not False
                or preview_data.get("outputs_changed") != []):
            raise BatchConflict("No-op candidate contains changed resources")
    elif preview.get("result") != "ok":
        raise BatchConflict("Changed candidate has an invalid preview result")

    # The renderer's complete old output roster must still be byte-coherent.
    old_output_bytes: dict[str, bytes] = {}
    for path, text in old_outputs.items():
        relative = path.relative_to(source).as_posix()
        actual = contents.get(relative)
        if actual is None or _rendered_bytes(text, actual, relative) != actual:
            raise BatchConflict(f"Managed output drifted: {relative}")
        old_output_bytes[relative] = actual

    models_relative = "olympus/core/models.toml"
    models_old = contents.get(models_relative)
    if models_old is None:
        raise BatchBlocked("Canonical models.toml is missing from the candidate read-set")
    try:
        if tomllib.loads(models_old.decode("utf-8")) != old_models:
            raise BatchConflict("models.toml disagrees with canonical renderer sources")
    except (UnicodeError, tomllib.TOMLDecodeError) as error:
        raise BatchConflict(f"Cannot parse fixture models.toml: {error}") from error

    expected_payloads: dict[str, bytes] = {}
    model_item = file_by_path.get(models_relative)
    if no_op:
        if model_item is not None:
            raise BatchConflict("No-op candidate unexpectedly contains models.toml")
    else:
        if model_item is None:
            raise BatchConflict("Changed candidate omits models.toml")
        try:
            new_models = tomllib.loads(model_item.new_bytes.decode("utf-8"))
        except (AttributeError, UnicodeError, tomllib.TOMLDecodeError) as error:
            raise BatchConflict(f"Candidate models.toml is not valid UTF-8 TOML: {error}") from error
        if model_item.old_bytes != models_old or model_item.new_bytes == models_old:
            raise BatchConflict("Candidate models.toml bytes do not describe a real edit")
        if hashlib.sha256(models_old).hexdigest() != model_item.old_sha256:
            raise BatchConflict("Candidate models.toml old hash is invalid")
        if hashlib.sha256(model_item.new_bytes).hexdigest() != model_item.new_sha256:
            raise BatchConflict("Candidate models.toml new hash is invalid")

        request = preview_data.get("request", {})
        expected_updates: dict[tuple[str, ...], Any] = {}
        if operation == "models set-family":
            family = request.get("family")
            model_ids = request.get("models")
            if not isinstance(family, str) or not isinstance(model_ids, dict):
                raise BatchConflict("Family candidate request is malformed")
            expected_updates = {
                ("families", family, "opencode"): model_ids.get("opencode"),
                ("families", family, "codex"): model_ids.get("codex"),
            }
        else:
            role = request.get("role")
            family = request.get("family")
            effort = request.get("effort")
            if (not isinstance(role, str) or not isinstance(family, dict)
                    or not isinstance(effort, dict)):
                raise BatchConflict("Role candidate request is malformed")
            for field, values in (("family", family), ("effort", effort)):
                if values.get("old") != values.get("new"):
                    expected_updates[("roles", role, field)] = values.get("new")
        expected_changes = {path for path, value in expected_updates.items()
                            if value is not None and _nested_value(old_models, path) != value}
        if (_semantic_changes(old_models, new_models) != expected_changes
                or any(_nested_value(new_models, path) != value
                       for path, value in expected_updates.items() if value is not None)):
            raise BatchConflict("Candidate models.toml contains changes outside its preview request")
        expected_payloads[models_relative] = model_item.new_bytes

        try:
            new_outputs = renderer.opencode_outputs(source, new_models, policies, identities, roles)
            new_outputs.update(renderer.codex_outputs(source, new_models, policies, identities, roles))
            new_outputs[source / "docs" / "HARNESS-CAPABILITIES.md"] = renderer.capability_doc(capabilities)
        except Exception as error:
            raise BatchConflict(f"Renderer rejected candidate models.toml: {error}") from error
        if set(new_outputs) != set(old_outputs):
            raise BatchConflict("Candidate renderer changed the managed output roster")
        changed_outputs: list[str] = []
        for path, text in new_outputs.items():
            relative = path.relative_to(source).as_posix()
            original = old_output_bytes[relative]
            expected = _rendered_bytes(text, original, relative)
            if expected != original:
                expected_payloads[relative] = expected
                changed_outputs.append(relative)
        if preview_data.get("outputs_changed") != sorted(changed_outputs):
            raise BatchConflict("Candidate output changes disagree with the canonical renderer")

    if set(file_by_path) != set(expected_payloads):
        raise BatchConflict("Candidate write-set is not models.toml plus changed existing outputs")
    for relative, item in file_by_path.items():
        if relative not in (models_relative, *[path.relative_to(source).as_posix() for path in old_outputs]):
            raise BatchBlocked(f"Candidate target is outside the fixed renderer write-set: {relative}")
        current = contents.get(relative)
        signature = current_read_set.get(relative)
        if current is None or signature is None:
            raise BatchBlocked(f"Candidate target is absent from the read-set: {relative}")
        mode = signature[3]
        if (item.old_bytes != current or item.new_bytes != expected_payloads[relative]
                or item.old_bytes == item.new_bytes
                or hashlib.sha256(item.old_bytes).hexdigest() != item.old_sha256
                or hashlib.sha256(item.new_bytes).hexdigest() != item.new_sha256
                or item.mode != mode or signature[0] != "file" or signature[3] != mode):
            raise BatchConflict(f"Candidate bytes, hashes, or mode disagree for {relative}")

    # Recheck after renderer evaluation to catch observable changes during validation.
    final_read_set, final_contents = _candidate_snapshot(source, old_outputs)
    if final_read_set != read_set or final_contents != contents:
        raise BatchConflict("Canonical source/read-set changed while validating the batch")
    return files, current_read_set, contents


def _nested_value(data: Any, path: tuple[str, ...]) -> Any:
    current = data
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return object()
        current = current[part]
    return current


def _scratch_absent(source: Path) -> None:
    scratch = source / _SCRATCH_NAME
    try:
        os.lstat(scratch)
    except FileNotFoundError:
        return
    except OSError as error:
        raise BatchBlocked(f"Cannot safely inspect pending batch path: {scratch}") from error
    raise BatchBlocked(f"A pending or unsafe batch already exists: {scratch}")


def _make_directory(path: Path, source: Path, lock: _Lock, identity: tuple[int, int]) -> None:
    _lock_identity(lock, identity)
    try:
        os.mkdir(path, 0o700)
    except OSError as error:
        raise BatchBlocked(f"Cannot create private batch directory {path}: {error}") from error
    try:
        metadata = os.lstat(path)
    except OSError as error:
        raise BatchBlocked(f"Cannot verify private batch directory {path}") from error
    root_metadata = _safe_root_metadata(source)
    if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
            or metadata.st_dev != root_metadata.st_dev):
        raise BatchBlocked(f"Private batch directory is unsafe or cross-filesystem: {path}")


def _write_private_file(
    path: Path,
    source: Path,
    relative: str,
    payload: bytes,
    mode: int,
    lock: _Lock,
    identity: tuple[int, int],
) -> tuple[int, int]:
    _lock_identity(lock, identity)
    parent_relative = PurePosixPath(relative).parent.as_posix()
    if parent_relative != ".":
        _checked_path(source, parent_relative, kind="directory")
    try:
        os.lstat(path)
    except FileNotFoundError:
        pass
    except OSError as error:
        raise BatchBlocked(f"Cannot inspect staged resource {relative}: {error}") from error
    else:
        raise BatchBlocked(f"Staged resource already exists: {relative}")

    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise BatchBlocked(f"Cannot create staged resource {relative}: {error}") from error
    try:
        os.set_inheritable(descriptor, False)
        created = os.fstat(descriptor)
        if (not stat.S_ISREG(created.st_mode) or created.st_nlink != 1
                or created.st_dev != _safe_root_metadata(source).st_dev
                or getattr(created, "st_file_attributes", 0) & _REPARSE_POINT):
            raise BatchBlocked(f"Staged resource is not a safe same-filesystem file: {relative}")
        view = memoryview(payload)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("short write while staging batch data")
            written += count
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, mode)
        else:
            _lock_identity(lock, identity)
            os.chmod(path, mode)
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        saved: list[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            saved.append(block)
        verified = b"".join(saved)
        after = os.fstat(descriptor)
        try:
            path_after = os.lstat(path)
        except OSError as error:
            raise BatchBlocked(f"Staged resource disappeared during verification: {relative}") from error
        if (verified != payload or (created.st_dev, created.st_ino) != (after.st_dev, after.st_ino)
                or after.st_size != len(payload)
                or after.st_nlink != 1
                or (after.st_dev, after.st_ino) != (path_after.st_dev, path_after.st_ino)
                or stat.S_IMODE(after.st_mode) != stat.S_IMODE(mode)):
            raise BatchConflict(f"Staged resource bytes, mode, or identity failed verification: {relative}")
        return after.st_dev, after.st_ino
    finally:
        os.close(descriptor)


def _sync_directory(path: Path) -> None:
    """Best-effort directory metadata sync; file fsync remains mandatory."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except (OSError, NotImplementedError):
        return
    try:
        os.fsync(descriptor)
    except (OSError, NotImplementedError):
        pass
    finally:
        os.close(descriptor)


def _persist_prepared_record(
    source: Path,
    scratch: Path,
    record: dict[str, Any],
    lock: _Lock,
    identity: tuple[int, int],
) -> Path:
    payload = (json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    temporary_relative = f"{_SCRATCH_NAME}/.record.json.tmp"
    temporary = source / temporary_relative
    record_relative = f"{_SCRATCH_NAME}/{_RECORD_NAME}"
    record_path = source / record_relative
    # Windows exposes only the read-only attribute through chmod; use the
    # platform's normal writable mode while relying on the scratch ACL.
    record_mode = 0o666 if os.name == "nt" else 0o600
    _checked_path(source, _SCRATCH_NAME, kind="directory")
    _write_private_file(temporary, source, temporary_relative, payload, record_mode, lock, identity)
    _lock_identity(lock, identity)
    _checked_path(source, _SCRATCH_NAME, kind="directory")
    try:
        os.lstat(record_path)
    except FileNotFoundError:
        pass
    else:
        raise BatchBlocked("Prepared record path unexpectedly exists")
    try:
        temporary_info = _checked_path(source, temporary_relative, kind="file")[1]
        os.replace(temporary, record_path)
    except OSError as error:
        raise BatchBlocked(f"Cannot atomically persist PREPARED record: {error}") from error
    _sync_directory(scratch)
    written, metadata = _safe_read(source, record_relative)
    if (written != payload or (metadata.st_dev, metadata.st_ino)
            != (temporary_info.st_dev, temporary_info.st_ino)):
        raise BatchConflict("Persisted PREPARED record failed byte or identity verification")
    return record_path


def _prepare_batch(candidate: Any) -> _PreparedBatch | None:
    """Persist a fixed, recoverable PREPARED batch without replacing any target.

    This is deliberately only T015: it creates and verifies backups, staged
    candidates, and the PREPARED record. Original models and generated outputs
    are never modified here; public dispatch and recovery are not provided.
    """
    source = _candidate_source(candidate)
    _scratch_absent(source)
    files, read_set, contents = _validate_candidate(candidate, source)
    if not files:
        return None

    operation_id = uuid.uuid4().hex
    try:
        lock = _acquire_lock(source, create=True)
    except LockError as error:
        raise BatchBlocked(f"Cannot acquire the stable source-edit lock: {error}") from error

    try:
        lock_identity = _lock_identity(lock)
        _scratch_absent(source)
        files, read_set, contents = _validate_candidate(candidate, source)
        if not files:
            return None

        scratch = source / _SCRATCH_NAME
        _make_directory(scratch, source, lock, lock_identity)
        _sync_directory(source)
        backups_dir = scratch / "backups"
        staged_dir = scratch / "staged"
        _make_directory(backups_dir, source, lock, lock_identity)
        _make_directory(staged_dir, source, lock, lock_identity)

        file_records: list[dict[str, Any]] = []
        for index, item in enumerate(files):
            _lock_identity(lock, lock_identity)
            relative = item.relative_path
            old_bytes, current_metadata = _safe_read(source, relative)
            current_mode = stat.S_IMODE(current_metadata.st_mode)
            if (old_bytes != item.old_bytes or current_mode != item.mode
                    or hashlib.sha256(old_bytes).hexdigest() != item.old_sha256):
                raise BatchConflict(f"Target drifted after lock acquisition: {relative}")
            backup_relative = f"{_SCRATCH_NAME}/backups/file-{index:04d}.old"
            staged_relative = f"{_SCRATCH_NAME}/staged/file-{index:04d}.new"
            backup_path = source / backup_relative
            staged_path = source / staged_relative
            _write_private_file(backup_path, source, backup_relative, old_bytes,
                                item.mode, lock, lock_identity)
            backup_bytes, backup_metadata = _safe_read(source, backup_relative)
            if (backup_bytes != old_bytes or stat.S_IMODE(backup_metadata.st_mode) != item.mode
                    or hashlib.sha256(backup_bytes).hexdigest() != item.old_sha256):
                raise BatchConflict(f"Original backup failed exact verification: {relative}")
            _write_private_file(staged_path, source, staged_relative, item.new_bytes,
                                item.mode, lock, lock_identity)
            staged_bytes, staged_metadata = _safe_read(source, staged_relative)
            if (staged_bytes != item.new_bytes or stat.S_IMODE(staged_metadata.st_mode) != item.mode
                    or hashlib.sha256(staged_bytes).hexdigest() != item.new_sha256):
                raise BatchConflict(f"New staged bytes failed exact verification: {relative}")
            file_records.append({
                "path": relative,
                "old_sha256": item.old_sha256,
                "new_sha256": item.new_sha256,
                "mode": item.mode,
                "backup": backup_relative[len(_SCRATCH_NAME) + 1:],
                "staged": staged_relative[len(_SCRATCH_NAME) + 1:],
            })

        # Revalidate the entire read-set and all prepared bytes immediately
        # before recording PREPARED. No original target replacement occurs.
        _lock_identity(lock, lock_identity)
        _, final_read_set, final_contents = _validate_candidate(candidate, source)
        if final_read_set != read_set or final_contents != contents:
            raise BatchConflict("Source/read-set changed while staging the batch")
        for item, entry in zip(files, file_records):
            backup_bytes, backup_meta = _safe_read(source, f"{_SCRATCH_NAME}/{entry['backup']}")
            staged_bytes, staged_meta = _safe_read(source, f"{_SCRATCH_NAME}/{entry['staged']}")
            if (backup_bytes != item.old_bytes or staged_bytes != item.new_bytes
                    or stat.S_IMODE(backup_meta.st_mode) != item.mode
                    or stat.S_IMODE(staged_meta.st_mode) != item.mode):
                raise BatchConflict(f"Prepared files changed before PREPARED: {item.relative_path}")

        _sync_directory(backups_dir)
        _sync_directory(staged_dir)
        _sync_directory(scratch)

        read_records = []
        for relative, signature in sorted(read_set.items()):
            if not isinstance(signature, tuple) or len(signature) < 4:
                raise BatchBlocked(f"Malformed read-set signature: {relative}")
            kind = signature[0]
            if kind not in ("file", "directory"):
                raise BatchBlocked(f"Malformed read-set kind: {relative}")
            read_records.append({
                "path": relative,
                "kind": kind,
                "sha256": signature[-1] if kind == "file" else None,
                "mode": signature[3],
            })
        record = {
            "schema_version": 1,
            "operation_id": operation_id,
            "source_root": str(source),
            "lock_identity": {
                "path": _LOCK_NAME,
                "st_dev": lock_identity[0],
                "st_ino": lock_identity[1],
            },
            "state": "PREPARED",
            "read_set": read_records,
            "files": file_records,
        }
        _lock_identity(lock, lock_identity)
        record_path = _persist_prepared_record(source, scratch, record, lock, lock_identity)
        _lock_identity(lock, lock_identity)
        return _PreparedBatch(
            operation_id=operation_id,
            source_root=source,
            scratch_path=scratch,
            record_path=record_path,
            write_set=tuple(item.relative_path for item in files),
            record=record,
        )
    finally:
        _release_lock(lock)


def _record_bytes(record: dict[str, Any]) -> bytes:
    return (json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            + "\n").encode("utf-8")


def _json_object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _decode_record(raw: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_object_no_duplicates)
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise BatchBlocked(f"Batch {description} is incomplete or invalid JSON") from error
    if not isinstance(value, dict):
        raise BatchBlocked(f"Batch {description} is not a record object")
    return value


def _record_map(source: Path, record: dict[str, Any], lock_identity: tuple[int, int]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Validate the concrete T015 schema before opening any batch resource."""
    if set(record) != {
        "schema_version", "operation_id", "source_root", "lock_identity",
        "state", "read_set", "files",
    }:
        raise BatchBlocked("Batch record has missing or unexpected fields")
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise BatchBlocked("Unsupported batch record schema_version")
    operation_id = record["operation_id"]
    if not isinstance(operation_id, str) or re.fullmatch(r"[0-9a-f]{32}", operation_id) is None:
        raise BatchBlocked("Batch record operation_id is invalid")
    if record["source_root"] != str(source):
        raise BatchBlocked("Batch record belongs to a different canonical source root")
    lock_record = record["lock_identity"]
    if (not isinstance(lock_record, dict)
            or set(lock_record) != {"path", "st_dev", "st_ino"}
            or lock_record.get("path") != _LOCK_NAME
            or type(lock_record.get("st_dev")) is not int
            or type(lock_record.get("st_ino")) is not int
            or (lock_record["st_dev"], lock_record["st_ino"]) != lock_identity):
        raise BatchBlocked("Batch record does not match the acquired stable lock identity")
    if record["state"] not in ("PREPARED", "COMMITTED"):
        raise BatchBlocked("Batch record state is absent or unsupported")

    read_records = record["read_set"]
    file_records = record["files"]
    if not isinstance(read_records, list) or not isinstance(file_records, list) or not file_records:
        raise BatchBlocked("Batch record read_set/files are incomplete")

    read_map: dict[str, dict[str, Any]] = {}
    previous_path: str | None = None
    for entry in read_records:
        if (not isinstance(entry, dict)
                or set(entry) != {"path", "kind", "sha256", "mode"}):
            raise BatchBlocked("Batch record has an invalid read_set entry")
        relative = entry["path"]
        _relative_parts(relative)
        if previous_path is not None and relative <= previous_path:
            raise BatchBlocked("Batch record read_set paths are duplicated or unordered")
        previous_path = relative
        if (entry["kind"] not in ("file", "directory")
                or type(entry["mode"]) is not int
                or not 0 <= entry["mode"] <= 0o7777):
            raise BatchBlocked(f"Batch read_set metadata is invalid for {relative}")
        digest = entry["sha256"]
        if entry["kind"] == "file":
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise BatchBlocked(f"Batch read_set hash is invalid for {relative}")
        elif digest is not None:
            raise BatchBlocked(f"Batch directory read_set entry has a file hash: {relative}")
        read_map[relative] = entry

    file_map: dict[str, dict[str, Any]] = {}
    previous_path = None
    for index, entry in enumerate(file_records):
        if (not isinstance(entry, dict)
                or set(entry) != {"path", "old_sha256", "new_sha256", "mode", "backup", "staged"}):
            raise BatchBlocked("Batch record has an invalid files entry")
        relative = entry["path"]
        _relative_parts(relative)
        if previous_path is not None and relative <= previous_path:
            raise BatchBlocked("Batch target paths are duplicated or unordered")
        previous_path = relative
        old_hash, new_hash = entry["old_sha256"], entry["new_sha256"]
        if (not isinstance(old_hash, str) or re.fullmatch(r"[0-9a-f]{64}", old_hash) is None
                or not isinstance(new_hash, str) or re.fullmatch(r"[0-9a-f]{64}", new_hash) is None
                or old_hash == new_hash):
            raise BatchBlocked(f"Batch target hashes are invalid for {relative}")
        mode = entry["mode"]
        if type(mode) is not int or not 0 <= mode <= 0o7777:
            raise BatchBlocked(f"Batch target mode is invalid for {relative}")
        expected_backup = f"backups/file-{index:04d}.old"
        expected_staged = f"staged/file-{index:04d}.new"
        if (entry["backup"] != expected_backup
                or entry["staged"] != expected_staged):
            raise BatchBlocked(f"Batch backup/staged path is outside its fixed schema: {relative}")
        read_entry = read_map.get(relative)
        if (read_entry is None or read_entry["kind"] != "file"
                or read_entry["mode"] != mode or read_entry["sha256"] != old_hash):
            raise BatchBlocked(f"Batch target conflicts with its original read_set entry: {relative}")
        file_map[relative] = entry
    if "olympus/core/models.toml" not in file_map:
        raise BatchBlocked("Batch write-set omits canonical olympus/core/models.toml")
    return read_map, file_map


def _record_context(source: Path, lock: _Lock) -> tuple[dict[str, Any], bytes, os.stat_result] | None:
    """Load the record only after the existing stable lock has been acquired."""
    _lock_identity(lock)
    scratch = source / _SCRATCH_NAME
    try:
        os.lstat(scratch)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise BatchBlocked(f"Cannot inspect pending batch scratch: {error}") from error
    _checked_path(source, _SCRATCH_NAME, kind="directory")
    try:
        raw, metadata = _safe_read(source, f"{_SCRATCH_NAME}/{_RECORD_NAME}")
    except BatchBlocked as error:
        raise BatchBlocked("Pending scratch has no complete, safely readable record") from error
    record = _decode_record(raw, "record")
    _record_map(source, record, _lock_identity(lock))
    if raw != _record_bytes(record):
        raise BatchBlocked("Batch record is not in the canonical persisted form")
    return record, raw, metadata


def _optional_artifact(source: Path, relative: str) -> tuple[bytes, os.stat_result] | None:
    path = source / relative
    try:
        os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise BatchBlocked(f"Cannot inspect batch artifact {relative}: {error}") from error
    return _safe_read(source, relative)


def _artifact_digest(
    source: Path,
    relative: str,
    expected_hash: str,
    expected_mode: int,
    *,
    required: bool,
) -> tuple[bytes, os.stat_result] | None:
    artifact = _optional_artifact(source, relative)
    if artifact is None:
        if required:
            raise BatchBlocked(f"Required batch backup/staged file is missing: {relative}")
        return None
    raw, metadata = artifact
    if (hashlib.sha256(raw).hexdigest() != expected_hash
            or stat.S_IMODE(metadata.st_mode) != expected_mode):
        raise BatchBlocked(f"Batch backup/staged file is corrupt or has a changed mode: {relative}")
    return artifact


def _validate_scratch_layout(
    source: Path,
    record: dict[str, Any],
    record_raw: bytes,
    lock_identity: tuple[int, int],
    *,
    required_backups: set[str] | None = None,
    require_all_staged: bool = False,
) -> dict[str, tuple[bytes, os.stat_result]]:
    """Validate only the record-enumerated artifacts; never sweep unknown scratch."""
    _lock_path = source / _SCRATCH_NAME
    _checked_path(source, _SCRATCH_NAME, kind="directory")
    try:
        top_names = set(os.listdir(_lock_path))
    except OSError as error:
        raise BatchBlocked(f"Cannot enumerate pending batch scratch: {error}") from error
    allowed_top = {_RECORD_NAME, ".record.json.tmp", "backups", "staged"}
    if top_names - allowed_top:
        raise BatchBlocked("Pending scratch contains unenumerated resources")
    if _RECORD_NAME not in top_names:
        raise BatchBlocked("Pending scratch has no authoritative operation record")

    _, file_map = _record_map(source, record, lock_identity)
    expected_backup_names = {entry["backup"].split("/", 1)[1] for entry in file_map.values()}
    expected_staged_names = {entry["staged"].split("/", 1)[1] for entry in file_map.values()}
    expected_rollback_names = {f"rollback-file-{index:04d}.old" for index in range(len(file_map))}
    artifacts: dict[str, tuple[bytes, os.stat_result]] = {}

    for directory_name, expected_names in (
        ("backups", expected_backup_names),
        ("staged", expected_staged_names | expected_rollback_names),
    ):
        relative_dir = f"{_SCRATCH_NAME}/{directory_name}"
        if directory_name not in top_names:
            continue
        _checked_path(source, relative_dir, kind="directory")
        try:
            names = set(os.listdir(source / relative_dir))
        except OSError as error:
            raise BatchBlocked(f"Cannot enumerate batch {directory_name}: {error}") from error
        if names - expected_names:
            raise BatchBlocked(f"Batch {directory_name} contains unenumerated resources")

    if ".record.json.tmp" in top_names:
        temporary, metadata = _safe_read(source, f"{_SCRATCH_NAME}/.record.json.tmp")
        candidate = _decode_record(temporary, "temporary record")
        _record_map(source, candidate, lock_identity)
        if temporary != _record_bytes(candidate):
            raise BatchBlocked("Temporary batch record is incomplete or noncanonical")
        if candidate["state"] not in ("PREPARED", "COMMITTED"):
            raise BatchBlocked("Temporary batch record state is invalid")
        stable_current = {**record, "state": "PREPARED"}
        stable_candidate = {**candidate, "state": "PREPARED"}
        if stable_current != stable_candidate:
            raise BatchBlocked("Temporary batch record belongs to a different operation")
        artifacts[f"{_SCRATCH_NAME}/.record.json.tmp"] = (temporary, metadata)

    for index, (relative, entry) in enumerate(file_map.items()):
        backup_path = f"{_SCRATCH_NAME}/{entry['backup']}"
        staged_path = f"{_SCRATCH_NAME}/{entry['staged']}"
        rollback_path = f"{_SCRATCH_NAME}/staged/rollback-file-{index:04d}.old"
        backup = _artifact_digest(
            source, backup_path, entry["old_sha256"], entry["mode"],
            required=relative in (required_backups or set()),
        )
        staged = _artifact_digest(
            source, staged_path, entry["new_sha256"], entry["mode"],
            required=require_all_staged,
        )
        rollback = _artifact_digest(
            source, rollback_path, entry["old_sha256"], entry["mode"], required=False,
        )
        if backup is not None:
            artifacts[backup_path] = backup
        if staged is not None:
            artifacts[staged_path] = staged
        if rollback is not None:
            artifacts[rollback_path] = rollback
    return artifacts


def _live_batch(
    source: Path,
    lock: _Lock,
    record: dict[str, Any],
    record_raw: bytes,
    record_metadata: os.stat_result,
    *,
    expected_states: dict[str, str] | None = None,
    required_backups: set[str] | None = None,
    require_all_staged: bool = False,
) -> dict[str, Any]:
    """Validate record, target states/modes, renderer read-set, and scratch under lock."""
    identity = _lock_identity(lock)
    read_map, file_map = _record_map(source, record, identity)
    _ensure_record(source, lock, record, record_raw, record_metadata)

    states: dict[str, str] = {}
    for relative, entry in file_map.items():
        raw, metadata = _safe_read(source, relative)
        digest = hashlib.sha256(raw).hexdigest()
        if stat.S_IMODE(metadata.st_mode) != entry["mode"]:
            raise BatchConflict(f"Batch target mode changed: {relative}")
        if digest == entry["old_sha256"]:
            state = "old"
        elif digest == entry["new_sha256"]:
            state = "new"
        else:
            raise BatchConflict(f"Batch target has a third, externally changed hash: {relative}")
        if expected_states is not None and expected_states.get(relative) != state:
            raise BatchConflict(f"Batch target changed unexpectedly during replacement: {relative}")
        states[relative] = state

    try:
        renderer = _load_checked_renderer(source)
        outputs = renderer.outputs_for(source, "all")
        if not isinstance(outputs, dict) or not outputs:
            raise BatchConflict("Canonical renderer returned no managed outputs during recovery")
        output_paths = {path.relative_to(source).as_posix() for path in outputs}
    except BatchError:
        raise
    except Exception as error:
        raise BatchBlocked(f"Cannot validate canonical renderer during recovery: {error}") from error

    allowed_targets = output_paths | {"olympus/core/models.toml"}
    if not set(file_map) <= allowed_targets:
        raise BatchBlocked("Batch write-set includes a path outside the fixed renderer target set")
    try:
        current_read, contents = _candidate_snapshot(source, outputs)
    except BatchError:
        raise
    except Exception as error:
        raise BatchBlocked(f"Cannot validate batch read-set: {error}") from error
    if set(current_read) != set(read_map):
        added = sorted(set(current_read) - set(read_map))
        missing = sorted(set(read_map) - set(current_read))
        raise BatchConflict(f"Batch read-set inventory changed (added={added[:3]}, missing={missing[:3]})")
    for relative, entry in read_map.items():
        signature = current_read[relative]
        if signature[0] != entry["kind"] or signature[3] != entry["mode"]:
            raise BatchConflict(f"Batch read-set kind or mode changed: {relative}")
        if relative not in file_map and entry["kind"] == "file" and signature[-1] != entry["sha256"]:
            raise BatchConflict(f"External batch read-set file changed: {relative}")

    artifacts = _validate_scratch_layout(
        source, record, record_raw, identity,
        required_backups=required_backups,
        require_all_staged=require_all_staged,
    )
    return {
        "source": source,
        "identity": identity,
        "read_map": read_map,
        "file_map": file_map,
        "states": states,
        "renderer": renderer,
        "outputs": outputs,
        "contents": contents,
        "artifacts": artifacts,
    }


def _ensure_record(
    source: Path,
    lock: _Lock,
    record: dict[str, Any],
    expected_raw: bytes,
    expected_metadata: os.stat_result,
) -> None:
    _lock_identity(lock)
    raw, metadata = _safe_read(source, f"{_SCRATCH_NAME}/{_RECORD_NAME}")
    if (raw != expected_raw
            or (metadata.st_dev, metadata.st_ino) != (expected_metadata.st_dev, expected_metadata.st_ino)
            or _decode_record(raw, "record") != record):
        raise BatchConflict("Authoritative batch record changed during the operation")


def _require_states(live: dict[str, Any], expected: str, message: str) -> None:
    if any(state != expected for state in live["states"].values()):
        raise BatchConflict(message)


def _verify_renderer_coherence(live: dict[str, Any]) -> None:
    source = live["source"]
    for path, text in live["outputs"].items():
        try:
            relative = path.relative_to(source).as_posix()
        except ValueError as error:
            raise BatchBlocked(f"Renderer output escapes the batch source: {path}") from error
        actual = live["contents"].get(relative)
        if actual is None or _rendered_bytes(text, actual, relative) != actual:
            raise BatchConflict(f"Batch state is not renderer-coherent: {relative}")


def _remove_owned_file(
    source: Path,
    lock: _Lock,
    relative: str,
    expected_hash: str,
    expected_mode: int,
) -> None:
    artifact = _optional_artifact(source, relative)
    if artifact is None:
        return
    raw, metadata = artifact
    if (hashlib.sha256(raw).hexdigest() != expected_hash
            or stat.S_IMODE(metadata.st_mode) != expected_mode):
        raise BatchBlocked(f"Refusing to remove changed batch evidence: {relative}")
    _lock_identity(lock)
    current, current_metadata = _safe_read(source, relative)
    if (current != raw
            or (current_metadata.st_dev, current_metadata.st_ino) != (metadata.st_dev, metadata.st_ino)):
        raise BatchConflict(f"Batch evidence changed before cleanup: {relative}")
    try:
        os.unlink(source / relative)
    except OSError as error:
        raise BatchBlocked(f"Cannot remove verified batch temporary {relative}: {error}") from error


def _cleanup_batch(
    source: Path,
    lock: _Lock,
    record: dict[str, Any],
    record_raw: bytes,
    record_metadata: os.stat_result,
    *,
    final_state: str,
) -> None:
    if final_state not in ("old", "new"):
        raise ValueError("cleanup requires a coherent old or new terminal state")
    live = _live_batch(source, lock, record, record_raw, record_metadata)
    _require_states(live, final_state, f"Cannot clean a non-{final_state} batch")
    _verify_renderer_coherence(live)
    scratch_metadata = _checked_path(source, _SCRATCH_NAME, kind="directory")[1]
    _, file_map = _record_map(source, record, live["identity"])

    for index, entry in enumerate(file_map.values()):
        _remove_owned_file(source, lock, f"{_SCRATCH_NAME}/{entry['staged']}",
                           entry["new_sha256"], entry["mode"])
        _remove_owned_file(source, lock,
                           f"{_SCRATCH_NAME}/staged/rollback-file-{index:04d}.old",
                           entry["old_sha256"], entry["mode"])
        _remove_owned_file(source, lock, f"{_SCRATCH_NAME}/{entry['backup']}",
                           entry["old_sha256"], entry["mode"])

    temporary = live["artifacts"].get(f"{_SCRATCH_NAME}/.record.json.tmp")
    if temporary is not None:
        _remove_owned_file(source, lock, f"{_SCRATCH_NAME}/.record.json.tmp",
                           hashlib.sha256(temporary[0]).hexdigest(), stat.S_IMODE(temporary[1].st_mode))

    for directory_name in ("staged", "backups"):
        relative = f"{_SCRATCH_NAME}/{directory_name}"
        try:
            _checked_path(source, relative, kind="directory")
        except BatchBlocked as error:
            if "Missing batch resource" in str(error):
                continue
            raise
        _lock_identity(lock, live["identity"])
        try:
            os.rmdir(source / relative)
        except OSError as error:
            raise BatchBlocked(f"Cannot remove nonempty or changed batch directory {relative}") from error

    # Revalidate targets/read-set and the authoritative record after artifact cleanup.
    live = _live_batch(source, lock, record, record_raw, record_metadata)
    _require_states(live, final_state, f"Batch changed during {final_state} cleanup")
    _verify_renderer_coherence(live)
    _ensure_record(source, lock, record, record_raw, record_metadata)
    _remove_owned_file(source, lock, f"{_SCRATCH_NAME}/{_RECORD_NAME}",
                       hashlib.sha256(record_raw).hexdigest(), stat.S_IMODE(record_metadata.st_mode))
    _lock_identity(lock, live["identity"])
    try:
        if os.listdir(source / _SCRATCH_NAME):
            raise BatchBlocked("Pending scratch gained unenumerated resources during final cleanup")
        current_scratch = _checked_path(source, _SCRATCH_NAME, kind="directory")[1]
        if (current_scratch.st_dev, current_scratch.st_ino) != (scratch_metadata.st_dev, scratch_metadata.st_ino):
            raise BatchConflict("Pending scratch directory changed identity during cleanup")
        os.rmdir(source / _SCRATCH_NAME)
    except BatchError:
        raise
    except OSError as error:
        raise BatchBlocked(f"Cannot remove empty pending scratch: {error}") from error
    _lock_identity(lock, live["identity"])


def _replace_record_state(
    source: Path,
    lock: _Lock,
    record: dict[str, Any],
    record_raw: bytes,
    record_metadata: os.stat_result,
    live: dict[str, Any],
    new_record: dict[str, Any],
) -> tuple[bytes, os.stat_result]:
    temporary_relative = f"{_SCRATCH_NAME}/.record.json.tmp"
    temporary = source / temporary_relative
    payload = _record_bytes(new_record)
    record_mode = stat.S_IMODE(record_metadata.st_mode)
    temporary_identity = _write_private_file(
        temporary, source, temporary_relative, payload, record_mode, lock, live["identity"]
    )
    # The authoritative PREPARED record remains the source of truth until replace.
    _ensure_record(source, lock, record, record_raw, record_metadata)
    _lock_identity(lock, live["identity"])
    try:
        os.replace(temporary, source / f"{_SCRATCH_NAME}/{_RECORD_NAME}")
    except OSError as error:
        raise BatchBlocked(f"Cannot persist COMMITTED batch record: {error}") from error
    _sync_directory(source / _SCRATCH_NAME)
    written, metadata = _safe_read(source, f"{_SCRATCH_NAME}/{_RECORD_NAME}")
    if (written != payload
            or (metadata.st_dev, metadata.st_ino) != temporary_identity):
        raise BatchConflict("Persisted COMMITTED record failed byte or identity verification")
    return written, metadata


def _rollback_prepared_locked(
    source: Path,
    lock: _Lock,
    record: dict[str, Any],
    record_raw: bytes,
    record_metadata: os.stat_result,
) -> None:
    if record["state"] != "PREPARED":
        raise BatchBlocked("Only a PREPARED batch may be rolled back")
    live = _live_batch(source, lock, record, record_raw, record_metadata)
    required = {relative for relative, state in live["states"].items() if state == "new"}
    if required:
        live = _live_batch(
            source, lock, record, record_raw, record_metadata,
            required_backups=required,
        )
    else:
        _require_states(live, "old", "PREPARED batch has an unsupported target state")

    for index, (relative, entry) in enumerate(live["file_map"].items()):
        if live["states"][relative] == "old":
            continue
        # Revalidate the complete batch and all backups needed for the remaining
        # restores before every individual os.replace.
        current_required = {path for path, state in live["states"].items() if state == "new"}
        live = _live_batch(
            source, lock, record, record_raw, record_metadata,
            required_backups=current_required,
        )
        if live["states"][relative] != "new":
            raise BatchConflict(f"Rollback target is no longer the batch's new state: {relative}")
        backup_relative = f"{_SCRATCH_NAME}/{entry['backup']}"
        backup = _artifact_digest(source, backup_relative, entry["old_sha256"], entry["mode"], required=True)
        rollback_relative = f"{_SCRATCH_NAME}/staged/rollback-file-{index:04d}.old"
        rollback_path = source / rollback_relative
        saved_rollback = _optional_artifact(source, rollback_relative)
        if saved_rollback is None:
            _write_private_file(
                rollback_path, source, rollback_relative, backup[0], entry["mode"],
                lock, live["identity"],
            )
        else:
            saved_bytes, saved_metadata = saved_rollback
            if (saved_bytes != backup[0] or stat.S_IMODE(saved_metadata.st_mode) != entry["mode"]):
                raise BatchBlocked(f"Existing rollback stage is not the verified backup: {relative}")

        # Last checks immediately before replacement prevent overwriting any
        # observable third target/read-set state. The stable descriptor remains held.
        live = _live_batch(
            source, lock, record, record_raw, record_metadata,
            required_backups=current_required,
        )
        if live["states"][relative] != "new":
            raise BatchConflict(f"Rollback target changed before restore: {relative}")
        staged_bytes, staged_metadata = _safe_read(source, rollback_relative)
        if (hashlib.sha256(staged_bytes).hexdigest() != entry["old_sha256"]
                or stat.S_IMODE(staged_metadata.st_mode) != entry["mode"]):
            raise BatchBlocked(f"Verified rollback stage changed before restore: {relative}")
        _lock_identity(lock, live["identity"])
        try:
            os.replace(source / rollback_relative, source / relative)
        except OSError as error:
            raise BatchBlocked(f"Cannot restore original target {relative}: {error}") from error
        restored, restored_metadata = _safe_read(source, relative)
        if (hashlib.sha256(restored).hexdigest() != entry["old_sha256"]
                or stat.S_IMODE(restored_metadata.st_mode) != entry["mode"]):
            raise BatchConflict(f"Restored target failed old hash/mode verification: {relative}")
        live = _live_batch(source, lock, record, record_raw, record_metadata)

    live = _live_batch(source, lock, record, record_raw, record_metadata)
    _require_states(live, "old", "Rollback did not restore the complete old batch")
    _verify_renderer_coherence(live)
    _cleanup_batch(source, lock, record, record_raw, record_metadata, final_state="old")


def _commit_batch(prepared: _PreparedBatch) -> str:
    """Replace a T015 batch individually; caught failures roll back under this lock."""
    if not isinstance(prepared, _PreparedBatch):
        raise BatchBlocked("Commit requires the private T015 prepared-batch receipt")
    source = _canonical_source(prepared.source_root)
    if source != prepared.source_root:
        raise BatchBlocked("Prepared batch source root is no longer canonical")
    try:
        lock = _acquire_lock(source, create=False)
    except LockError as error:
        raise BatchBlocked(f"Cannot acquire the existing stable batch lock: {error}") from error
    mutation_started = False
    record: dict[str, Any] | None = None
    record_raw = b""
    record_metadata: os.stat_result | None = None
    try:
        context = _record_context(source, lock)
        if context is None:
            raise BatchBlocked("Prepared batch scratch disappeared before commit")
        record, record_raw, record_metadata = context
        if (record["state"] != "PREPARED"
                or record["operation_id"] != prepared.operation_id
                or tuple(entry["path"] for entry in record["files"]) != prepared.write_set
                or record != prepared.record):
            raise BatchBlocked("Prepared-batch receipt does not match its authoritative record")
        live = _live_batch(
            source, lock, record, record_raw, record_metadata,
            expected_states={relative: "old" for relative in prepared.write_set},
            required_backups=set(prepared.write_set), require_all_staged=True,
        )
        _require_states(live, "old", "Original targets changed before batch commit")
        _verify_renderer_coherence(live)

        for index, (relative, entry) in enumerate(live["file_map"].items()):
            expected = {
                path: ("new" if prior_index < index else "old")
                for prior_index, path in enumerate(live["file_map"])
            }
            live = _live_batch(
                source, lock, record, record_raw, record_metadata,
                expected_states=expected,
                required_backups=set(live["file_map"]),
            )
            stage_relative = f"{_SCRATCH_NAME}/{entry['staged']}"
            staged_bytes, staged_metadata = _safe_read(source, stage_relative)
            if (hashlib.sha256(staged_bytes).hexdigest() != entry["new_sha256"]
                    or stat.S_IMODE(staged_metadata.st_mode) != entry["mode"]):
                raise BatchConflict(f"Staged candidate changed before replacement: {relative}")
            target_bytes, target_metadata = _safe_read(source, relative)
            if (hashlib.sha256(target_bytes).hexdigest() != entry["old_sha256"]
                    or stat.S_IMODE(target_metadata.st_mode) != entry["mode"]):
                raise BatchConflict(f"Original target changed before replacement: {relative}")
            _lock_identity(lock, live["identity"])
            mutation_started = True
            try:
                os.replace(source / stage_relative, source / relative)
            except OSError as error:
                raise BatchBlocked(f"Cannot replace batch target {relative}: {error}") from error
            replaced, replaced_metadata = _safe_read(source, relative)
            if (hashlib.sha256(replaced).hexdigest() != entry["new_sha256"]
                    or stat.S_IMODE(replaced_metadata.st_mode) != entry["mode"]):
                raise BatchConflict(f"Replaced target failed new hash/mode verification: {relative}")

        live = _live_batch(
            source, lock, record, record_raw, record_metadata,
            expected_states={relative: "new" for relative in live["file_map"]},
            required_backups=set(live["file_map"]),
        )
        _require_states(live, "new", "Batch did not reach the complete new state")
        _verify_renderer_coherence(live)
        committed_record = {**record, "state": "COMMITTED"}
        record_raw, record_metadata = _replace_record_state(
            source, lock, record, record_raw, record_metadata, live, committed_record,
        )
        record = committed_record
        committed_live = _live_batch(source, lock, record, record_raw, record_metadata)
        _require_states(committed_live, "new", "COMMITTED batch no longer has all new targets")
        _verify_renderer_coherence(committed_live)
        _cleanup_batch(source, lock, record, record_raw, record_metadata, final_state="new")
        return "committed"
    except Exception as error:
        if not mutation_started or record is None or record_metadata is None:
            raise
        # A committed record is terminal truth: never roll it back merely because
        # post-commit cleanup failed or its result could not be collected.
        try:
            current = _record_context(source, lock)
            if current is not None and current[0].get("operation_id") == prepared.operation_id:
                current_record, current_raw, current_metadata = current
                if current_record.get("state") == "COMMITTED":
                    raise BatchBlocked(
                        f"Batch is COMMITTED but post-commit validation/cleanup is pending: {error}"
                    ) from error
                if current_record.get("state") != "PREPARED":
                    raise BatchBlocked(f"Batch state is unconfirmed after commit failure: {error}") from error
                _rollback_prepared_locked(
                    source, lock, current_record, current_raw, current_metadata,
                )
                raise BatchError(f"Batch commit failed; rollback was confirmed: {error}") from error
        except BatchError as recovery_error:
            if "rollback was confirmed" in str(recovery_error):
                raise
            raise BatchBlocked(
                f"Batch commit failed and same-lock rollback could not be confirmed: {error}; {recovery_error}"
            ) from error
        raise BatchBlocked(f"Batch commit failed with unconfirmed operation state: {error}") from error
    finally:
        _release_lock(lock)


def _recover_batch(source_root: os.PathLike[str] | str) -> str:
    """Explicit stdlib recovery for one PREPARED/COMMITTED Slice B batch."""
    source = _canonical_source(source_root)
    try:
        lock = _acquire_lock(source, create=False)
    except LockError as error:
        raise BatchBlocked(f"Recovery requires the existing stable lock: {error}") from error
    try:
        context = _record_context(source, lock)
        if context is None:
            return "no_changes"
        record, record_raw, record_metadata = context
        live = _live_batch(source, lock, record, record_raw, record_metadata)
        if record["state"] == "COMMITTED":
            _require_states(live, "new", "COMMITTED batch is not entirely in its new state")
            _verify_renderer_coherence(live)
            _cleanup_batch(source, lock, record, record_raw, record_metadata, final_state="new")
            return "committed_cleanup"

        current_new = {relative for relative, state in live["states"].items() if state == "new"}
        if current_new:
            live = _live_batch(
                source, lock, record, record_raw, record_metadata,
                required_backups=current_new,
            )
        else:
            _require_states(live, "old", "PREPARED batch contains an unsupported target state")
        _rollback_prepared_locked(source, lock, record, record_raw, record_metadata)
        return "rolled_back"
    finally:
        _release_lock(lock)
