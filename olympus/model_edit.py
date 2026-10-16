"""Private, in-memory preparation and preview for Slice B model edits.

This module does not write source files, managed outputs, locks, or scratch.
TOML Kit is imported only when a candidate is prepared.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import stat
import tomllib
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]*")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_TOML_KIT_VERSION = "0.13.3"


class ModelEditError(ValueError):
    """A requested model candidate is invalid, ambiguous, or incoherent."""


@dataclass(frozen=True, slots=True)
class _TomlCandidate:
    old_bytes: bytes
    new_bytes: bytes
    old_models: dict[str, Any]
    new_models: dict[str, Any]
    changed_paths: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True, slots=True)
class _FileCandidate:
    path: Path
    relative_path: str
    old_bytes: bytes
    new_bytes: bytes
    mode: int
    old_sha256: str
    new_sha256: str


@dataclass(frozen=True, slots=True)
class _EditCandidate:
    source_root: Path
    preview: dict[str, Any]
    files: tuple[_FileCandidate, ...]
    read_set: dict[str, tuple[Any, ...]]


def _require_tomlkit():
    """Load the one optional editor dependency lazily and enforce its pin."""
    try:
        tomlkit = importlib.import_module("tomlkit")
    except ImportError as error:
        raise ModelEditError(
            "Slice B model preview requires optional dependency tomlkit==0.13.3"
        ) from error
    if getattr(tomlkit, "__version__", None) != _TOML_KIT_VERSION:
        raise ModelEditError(
            f"Slice B requires tomlkit=={_TOML_KIT_VERSION}; "
            f"found {getattr(tomlkit, '__version__', 'unknown')}"
        )
    return tomlkit


def _validate_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise ModelEditError(
            f"Invalid {label}: IDs must fully match [A-Za-z0-9][A-Za-z0-9._:/-]*"
        )
    return value


def _validate_model_data(models: object) -> tuple[dict[str, Any], dict[str, Any], set[str]]:
    if not isinstance(models, dict):
        raise ModelEditError("models.toml root must be a table")
    families = models.get("families")
    roles = models.get("roles")
    if not isinstance(families, dict) or not families:
        raise ModelEditError("models.toml must contain a non-empty families table")
    if not isinstance(roles, dict) or not roles:
        raise ModelEditError("models.toml must contain a non-empty roles table")

    for family_name, family in families.items():
        if not isinstance(family_name, str) or not isinstance(family, dict):
            raise ModelEditError("Model families must be named tables")
        for runtime in ("opencode", "codex"):
            if runtime not in family:
                raise ModelEditError(f"Family {family_name!r} is missing {runtime} model ID")
            _validate_id(family[runtime], f"existing {runtime} ID in family {family_name!r}")

    efforts: set[str] = set()
    for role, intent in roles.items():
        if not isinstance(role, str) or not isinstance(intent, dict):
            raise ModelEditError("Model roles must be named tables")
        family_name = intent.get("family")
        if not isinstance(family_name, str) or family_name not in families:
            raise ModelEditError(f"Role {role!r} refers to an unknown model family")
        effort = intent.get("effort")
        if (not isinstance(effort, str) or not effort or effort != effort.strip()
                or any(ord(character) < 32 or ord(character) == 127 for character in effort)):
            raise ModelEditError(f"Role {role!r} has an invalid canonical effort")
        efforts.add(effort)
    return families, roles, efforts


def _dict_value(data: dict[str, Any], path: tuple[str, str, str]) -> Any:
    first, second, third = path
    return data[first][second][third]


def _changed_paths(before: Any, after: Any, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[tuple[str, ...]] = []
        for key in sorted(set(before) | set(after), key=str):
            if key not in before or key not in after:
                changes.append((*prefix, str(key)))
            else:
                changes.extend(_changed_paths(before[key], after[key], (*prefix, str(key))))
        return changes
    return [] if before == after else [prefix]


def _path_item(document: Any, path: tuple[str, str, str]) -> tuple[Any, str, Any]:
    parent = document
    for key in path[:-1]:
        try:
            parent = parent[key]
        except (KeyError, TypeError) as error:
            raise ModelEditError(f"TOML target does not exist: {'.'.join(path)}") from error
    key = path[-1]
    try:
        item = parent[key]
    except (KeyError, TypeError) as error:
        raise ModelEditError(f"TOML target does not exist: {'.'.join(path)}") from error
    return parent, key, item


def _set_preserved_string(tomlkit: Any, document: Any, path: tuple[str, str, str], value: str) -> None:
    from tomlkit.items import String

    parent, key, item = _path_item(document, path)
    if not isinstance(item, String):
        raise ModelEditError(f"TOML target is not a scalar string: {'.'.join(path)}")
    string_type = item._t
    parent[key] = tomlkit.string(
        value,
        literal=string_type.is_literal(),
        multiline=string_type.is_multiline(),
    )


def _newline_style(raw: bytes, label: str) -> bytes:
    crlf_count = raw.count(b"\r\n")
    without_crlf = raw.replace(b"\r\n", b"")
    if b"\r" in without_crlf:
        raise ModelEditError(f"Ambiguous carriage-return convention in {label}")
    if crlf_count and b"\n" in without_crlf:
        raise ModelEditError(f"Mixed LF/CRLF newlines are not preservable in {label}")
    return b"\r\n" if crlf_count else b"\n"


def _parse_models_bytes(raw: bytes, label: str = "models.toml") -> tuple[Any, str, dict[str, Any]]:
    tomlkit = _require_tomlkit()
    _newline_style(raw, label)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ModelEditError(f"{label} is not valid UTF-8") from error
    if text.startswith("\ufeff"):
        raise ModelEditError(f"UTF-8 BOM is not accepted in {label}")
    try:
        document = tomlkit.parse(text)
        round_trip = tomlkit.dumps(document).encode("utf-8")
        semantic = tomllib.loads(text)
    except Exception as error:
        raise ModelEditError(f"Cannot parse {label} as unambiguous TOML: {error}") from error
    if round_trip != raw:
        raise ModelEditError(f"TOML Kit does not round-trip {label} byte-identically")
    _validate_model_data(semantic)
    return document, text, semantic


def _prepare_toml_candidate(
    models_bytes: bytes,
    updates: Mapping[tuple[str, str, str], str],
) -> _TomlCandidate:
    """Prepare only existing model scalar fields and prove all other bytes survive."""
    if not isinstance(models_bytes, bytes):
        raise ModelEditError("models.toml input must be bytes")
    if not isinstance(updates, Mapping):
        raise ModelEditError("Model edits must be a mapping of existing scalar paths")

    tomlkit = _require_tomlkit()
    original_document, original_text, old_models = _parse_models_bytes(models_bytes)
    families, roles, efforts = _validate_model_data(old_models)
    changed: dict[tuple[str, str, str], str] = {}

    for path, value in updates.items():
        if (not isinstance(path, tuple) or len(path) != 3
                or not all(isinstance(part, str) for part in path)):
            raise ModelEditError("Only existing three-part model scalar paths may be edited")
        area, name, field = path
        if area == "families" and name in families and field in ("opencode", "codex"):
            _validate_id(value, f"proposed {field} ID for family {name!r}")
        elif area == "roles" and name in roles and field == "family":
            if not isinstance(value, str) or value not in families:
                raise ModelEditError(f"Proposed family for role {name!r} must already exist")
        elif area == "roles" and name in roles and field == "effort":
            if not isinstance(value, str) or value not in efforts:
                raise ModelEditError(f"Proposed effort for role {name!r} is not canonical")
        else:
            raise ModelEditError(f"Unauthorized or missing TOML scalar path: {path!r}")
        if _dict_value(old_models, path) != value:
            changed[path] = value

    if not changed:
        return _TomlCandidate(models_bytes, models_bytes, old_models, old_models, ())

    # Start from a fresh, byte-validated document rather than mutating caller data.
    document = tomlkit.parse(original_text)
    for path, value in changed.items():
        _set_preserved_string(tomlkit, document, path, value)
    try:
        new_text = tomlkit.dumps(document)
        new_bytes = new_text.encode("utf-8")
        new_models = tomllib.loads(new_text)
    except Exception as error:
        raise ModelEditError(f"Edited model document is not valid TOML: {error}") from error
    if tomlkit.dumps(tomlkit.parse(new_text)).encode("utf-8") != new_bytes:
        raise ModelEditError("Edited TOML candidate does not round-trip byte-identically")
    _validate_model_data(new_models)

    expected_paths = {tuple(path) for path in changed}
    actual_paths = set(_changed_paths(old_models, new_models))
    if actual_paths != expected_paths:
        raise ModelEditError(
            f"Edited TOML changed unauthorized semantic paths: {sorted(actual_paths ^ expected_paths)}"
        )
    for path, value in changed.items():
        if _dict_value(new_models, path) != value:
            raise ModelEditError(f"Edited TOML did not apply requested scalar {'.'.join(path)}")

    # Revert just the authorized values in the serialized candidate. The exact
    # original bytes must return, proving every other byte (trivia included) is
    # unchanged. This is the masked-byte comparison without text search/replace.
    reverted = tomlkit.parse(new_text)
    for path in changed:
        _set_preserved_string(tomlkit, reverted, path, _dict_value(old_models, path))
    if tomlkit.dumps(reverted).encode("utf-8") != models_bytes:
        raise ModelEditError("TOML candidate alters bytes outside the authorized scalar values")

    return _TomlCandidate(
        old_bytes=models_bytes,
        new_bytes=new_bytes,
        old_models=old_models,
        new_models=new_models,
        changed_paths=tuple(sorted(changed)),
    )


def _canonical_source(source_root: str | Path) -> Path:
    source = Path(source_root)
    if not source.is_absolute():
        raise ModelEditError("Source root must be an absolute trusted checkout path")
    try:
        source = source.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ModelEditError(f"Cannot resolve source root: {source_root}") from error
    if not source.is_dir():
        raise ModelEditError(f"Source root is not a directory: {source}")
    return source


def _file_signature(metadata: Any) -> tuple[Any, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IMODE(metadata.st_mode),
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_nlink,
        getattr(metadata, "st_file_attributes", 0),
    )


def _check_component(path: Path, root: Path, *, final_kind: str | None = None) -> Any:
    root_stat = root.stat()
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ModelEditError(f"Renderer resource escapes the source root: {path}") from error
    current = root
    metadata = root_stat
    parts = relative.parts
    for index, part in enumerate(parts):
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as error:
            raise ModelEditError(f"Missing renderer resource: {current}") from error
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or attributes & _REPARSE_POINT:
            raise ModelEditError(f"Linked/reparse resources are not accepted: {current}")
        if metadata.st_dev != root_stat.st_dev:
            raise ModelEditError(f"Cross-filesystem renderer resource is not accepted: {current}")
        is_final = index == len(parts) - 1
        if not is_final or final_kind == "directory":
            if not stat.S_ISDIR(metadata.st_mode):
                raise ModelEditError(f"Expected a regular directory: {current}")
        elif final_kind == "file":
            if not stat.S_ISREG(metadata.st_mode):
                raise ModelEditError(f"Expected a regular file: {current}")
            if metadata.st_nlink != 1:
                raise ModelEditError(f"Hard-linked resources are not accepted: {current}")
    return metadata


def _read_safe_file(path: Path, root: Path) -> tuple[bytes, Any]:
    metadata = _check_component(path, root, final_kind="file")
    open_flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, open_flags)
    except OSError as error:
        raise ModelEditError(f"Cannot safely open renderer resource {path}: {error}") from error
    try:
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino)
                or getattr(opened, "st_file_attributes", 0) & _REPARSE_POINT):
            raise ModelEditError(f"Renderer resource changed identity while opening: {path}")
        chunks = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(descriptor)
        path_after = path.lstat()
        if (_file_signature(opened) != _file_signature(after)
                or (after.st_dev, after.st_ino) != (path_after.st_dev, path_after.st_ino)):
            raise ModelEditError(f"Renderer resource changed while reading: {path}")
        return b"".join(chunks), after
    finally:
        os.close(descriptor)


def _snapshot_source_tree(source: Path) -> dict[str, tuple[Any, ...]]:
    result: dict[str, tuple[Any, ...]] = {}
    olympus_dir = source / "olympus"
    _check_component(olympus_dir, source, final_kind="directory")

    def visit(directory: Path) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as error:
            raise ModelEditError(f"Cannot inventory renderer inputs under {directory}: {error}") from error
        for path in entries:
            metadata = _check_component(
                path,
                source,
                final_kind="directory" if path.is_dir() and not path.is_symlink() else "file",
            )
            relative = path.relative_to(source).as_posix()
            if stat.S_ISDIR(metadata.st_mode):
                result[relative] = ("directory", *_file_signature(metadata))
                visit(path)
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1:
                    raise ModelEditError(f"Hard-linked renderer input is not accepted: {path}")
                content, stable = _read_safe_file(path, source)
                result[relative] = ("file", *_file_signature(stable), hashlib.sha256(content).hexdigest())
            else:
                raise ModelEditError(f"Non-regular renderer input is not accepted: {path}")

    visit(olympus_dir)
    scripts_dir = source / "scripts"
    scripts_metadata = _check_component(scripts_dir, source, final_kind="directory")
    result[scripts_dir.relative_to(source).as_posix()] = ("directory", *_file_signature(scripts_metadata))
    renderer_path = source / "scripts" / "render_harnesses.py"
    content, metadata = _read_safe_file(renderer_path, source)
    result[renderer_path.relative_to(source).as_posix()] = (
        "file", *_file_signature(metadata), hashlib.sha256(content).hexdigest()
    )
    return result


def _snapshot_outputs(
    source: Path,
    outputs: Mapping[Path, str],
) -> tuple[dict[str, tuple[Any, ...]], dict[Path, tuple[bytes, Any]]]:
    signatures: dict[str, tuple[Any, ...]] = {}
    contents: dict[Path, tuple[bytes, Any]] = {}
    for path in sorted(outputs, key=lambda item: item.as_posix()):
        parent = path.parent
        while parent != source:
            if not parent.is_relative_to(source):
                raise ModelEditError(f"Renderer output directory escapes the source root: {parent}")
            parent_metadata = _check_component(parent, source, final_kind="directory")
            relative_parent = parent.relative_to(source).as_posix()
            signatures.setdefault(relative_parent, ("directory", *_file_signature(parent_metadata)))
            parent = parent.parent
        metadata = _check_component(path, source, final_kind="file")
        raw, stable = _read_safe_file(path, source)
        relative = path.relative_to(source).as_posix()
        signatures[relative] = ("file", *_file_signature(stable), hashlib.sha256(raw).hexdigest())
        contents[path] = (raw, stable)
    return signatures, contents


def _load_renderer(source: Path):
    path = source / "scripts" / "render_harnesses.py"
    raw, _ = _read_safe_file(path, source)
    try:
        text = raw.decode("utf-8")
        module = types.ModuleType("_olympus_candidate_renderer")
        module.__file__ = str(path)
        exec(compile(text, str(path), "exec"), module.__dict__)
    except (OSError, UnicodeError, SyntaxError) as error:
        raise ModelEditError(f"Cannot load canonical renderer {path}: {error}") from error
    return module


def _compose_outputs(renderer: Any, source: Path, models: dict[str, Any], policies: dict[str, Any],
                     capabilities: dict[str, Any], identities: dict[str, str], roles: set[str]) -> dict[Path, str]:
    outputs = renderer.opencode_outputs(source, models, policies, identities, roles)
    codex = renderer.codex_outputs(source, models, policies, identities, roles)
    outputs.update(codex)
    outputs[source / "docs" / "HARNESS-CAPABILITIES.md"] = renderer.capability_doc(capabilities)
    return outputs


def _expected_output_bytes(text: str, newline: bytes, path: Path) -> bytes:
    if "\r" in text:
        raise ModelEditError(f"Renderer produced an ambiguous CR character for {path}")
    raw = text.encode("utf-8")
    return raw.replace(b"\n", b"\r\n") if newline == b"\r\n" else raw


def _role_rows(old_models: dict[str, Any], new_models: dict[str, Any], identities: dict[str, str],
               affected: list[str]) -> list[dict[str, Any]]:
    rows = []
    for role in affected:
        old_intent = old_models["roles"][role]
        new_intent = new_models["roles"][role]
        old_models_by_runtime = old_models["families"][old_intent["family"]]
        new_models_by_runtime = new_models["families"][new_intent["family"]]
        rows.append({
            "role": role,
            "identity": identities[role],
            "family": {"old": old_intent["family"], "new": new_intent["family"]},
            "effort": {"old": old_intent["effort"], "new": new_intent["effort"]},
            "models": {
                runtime: {"old": old_models_by_runtime[runtime], "new": new_models_by_runtime[runtime]}
                for runtime in ("opencode", "codex")
            },
            "representation": {
                "opencode": "agent",
                "codex": "root" if role == "kael" else "absent" if role == "aegis" else "agent",
            },
        })
    return rows


def _make_candidate(source_root: str | Path, operation: str,
                    request: dict[str, Any]) -> _EditCandidate:
    source = _canonical_source(source_root)
    models_path = source / "olympus" / "core" / "models.toml"
    renderer_path = source / "scripts" / "render_harnesses.py"
    if not models_path.is_file() or not renderer_path.is_file():
        raise ModelEditError("Source is missing canonical models.toml or renderer")

    before_inputs = _snapshot_source_tree(source)
    renderer = _load_renderer(source)
    try:
        old_models, policies, capabilities, identities, roles = renderer.checked_sources(source)
        roles = set(roles)
        if len(roles) != 12:
            raise ModelEditError(f"Expected twelve canonical roles, found {len(roles)}")
        if set(identities) != roles or set(old_models.get("roles", {})) != roles:
            raise ModelEditError("Source roster, identities, and model roles are ambiguous")
        old_models = dict(old_models)
        old_families, old_role_data, old_efforts = _validate_model_data(old_models)
        old_outputs = _compose_outputs(renderer, source, old_models, policies, capabilities, identities, roles)
    except ModelEditError:
        raise
    except Exception as error:
        raise ModelEditError(f"Canonical sources or renderer are invalid: {error}") from error

    if operation == "models set-family":
        family = request["family"]
        opencode_id = _validate_id(request["opencode_id"], "proposed OpenCode ID")
        codex_id = _validate_id(request["codex_id"], "proposed Codex ID")
        if family not in old_families:
            raise ModelEditError(f"Unknown model family: {family}")
        affected = sorted(role for role, intent in old_role_data.items()
                          if intent.get("family") == family)
        if not affected:
            raise ModelEditError(f"Model family has no canonical roles: {family}")
        updates = {
            ("families", family, "opencode"): opencode_id,
            ("families", family, "codex"): codex_id,
        }
        preview_request = {
            "family": family,
            "models": {"opencode": opencode_id, "codex": codex_id},
        }
    elif operation == "agents set-model":
        role = request["role"]
        requested_family = request["family"]
        requested_effort = request["effort"]
        if role not in old_role_data:
            raise ModelEditError(f"Unknown canonical role: {role}")
        if requested_family is not None and requested_family not in old_families:
            raise ModelEditError(f"Unknown model family: {requested_family}")
        if requested_effort is not None and requested_effort not in old_efforts:
            raise ModelEditError(f"Effort is not present in the canonical role set: {requested_effort}")
        current = old_role_data[role]
        updates = {}
        if requested_family is not None:
            updates[("roles", role, "family")] = requested_family
        if requested_effort is not None:
            updates[("roles", role, "effort")] = requested_effort
        affected = [role]
        preview_request = {
            "role": role,
            "family": {"old": current["family"],
                       "new": requested_family if requested_family is not None else current["family"]},
            "effort": {"old": current["effort"],
                       "new": requested_effort if requested_effort is not None else current["effort"]},
        }
    else:
        raise ModelEditError(f"Unsupported private model-edit operation: {operation}")

    models_bytes, models_metadata = _read_safe_file(models_path, source)
    try:
        if tomllib.loads(models_bytes.decode("utf-8")) != old_models:
            raise ModelEditError("models.toml changed or disagrees with checked_sources")
    except (UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ModelEditError(f"Canonical models.toml is invalid: {error}") from error
    toml_candidate = _prepare_toml_candidate(models_bytes, updates)
    if toml_candidate.old_models != old_models:
        raise ModelEditError("TOML Kit model data disagrees with the canonical renderer")

    new_models = toml_candidate.new_models
    try:
        new_outputs = _compose_outputs(renderer, source, new_models, policies, capabilities, identities, roles)
    except Exception as error:
        raise ModelEditError(f"Renderer rejected the in-memory model candidate: {error}") from error
    if set(new_outputs) != set(old_outputs):
        raise ModelEditError("Candidate renderer changed the managed output roster")

    before_output_signatures, output_contents = _snapshot_outputs(source, old_outputs)
    file_candidates: list[_FileCandidate] = []
    if toml_candidate.new_bytes != models_bytes:
        file_candidates.append(_file_candidate(models_path, source, models_bytes,
                                               toml_candidate.new_bytes, models_metadata))

    output_changes: list[str] = []
    for path in sorted(old_outputs, key=lambda item: item.relative_to(source).as_posix()):
        old_bytes, output_metadata = output_contents[path]
        newline = _newline_style(old_bytes, path.relative_to(source).as_posix())
        expected_old = _expected_output_bytes(old_outputs[path], newline, path)
        if old_bytes != expected_old:
            raise ModelEditError(f"Managed output drift prevents preview: {path.relative_to(source).as_posix()}")
        new_bytes = _expected_output_bytes(new_outputs[path], newline, path)
        if new_bytes != old_bytes:
            output_changes.append(path.relative_to(source).as_posix())
            file_candidates.append(_file_candidate(path, source, old_bytes, new_bytes, output_metadata))

    after_inputs = _snapshot_source_tree(source)
    after_output_signatures, _ = _snapshot_outputs(source, old_outputs)
    if before_inputs != after_inputs or before_output_signatures != after_output_signatures:
        raise ModelEditError("Canonical source/read-set changed while preparing the preview")

    read_set = {**before_inputs, **before_output_signatures}
    file_candidates.sort(key=lambda item: item.relative_path)
    rows = _role_rows(old_models, new_models, identities, affected)
    no_op = not file_candidates
    preview = {
        "schema_version": 1,
        "operation": operation,
        "result": "no_changes" if no_op else "ok",
        "context": {"kind": "canonical_source", "source": str(source)},
        "data": {
            "request": preview_request,
            "affected_roles": list(affected),
            "roles": rows,
            "models_toml_changed": toml_candidate.new_bytes != models_bytes,
            "outputs_changed": output_changes,
            "write_set": [item.relative_path for item in file_candidates],
            "no_op": no_op,
        },
        "issues": [],
    }
    return _EditCandidate(source, preview, tuple(file_candidates), read_set)


def _file_candidate(path: Path, source: Path, old_bytes: bytes, new_bytes: bytes,
                    metadata: Any) -> _FileCandidate:
    _check_component(path, source, final_kind="file")
    relative = path.relative_to(source).as_posix()
    return _FileCandidate(
        path=path,
        relative_path=relative,
        old_bytes=old_bytes,
        new_bytes=new_bytes,
        mode=stat.S_IMODE(metadata.st_mode),
        old_sha256=hashlib.sha256(old_bytes).hexdigest(),
        new_sha256=hashlib.sha256(new_bytes).hexdigest(),
    )


def _build_set_family_candidate(source_root: str | Path, family: str,
                                opencode_id: str, codex_id: str) -> _EditCandidate:
    _validate_id(opencode_id, "proposed OpenCode ID")
    _validate_id(codex_id, "proposed Codex ID")
    if not isinstance(family, str) or not family:
        raise ModelEditError("Family name must be a non-empty existing family")

    return _make_candidate(
        source_root,
        "models set-family",
        {"family": family, "opencode_id": opencode_id, "codex_id": codex_id},
    )


def _build_set_role_candidate(source_root: str | Path, role: str, *,
                              family: str | None = None,
                              effort: str | None = None) -> _EditCandidate:
    if not isinstance(role, str) or not role:
        raise ModelEditError("Role must be an existing canonical role")
    if family is None and effort is None:
        raise ModelEditError("At least one of family or effort must be requested")
    if family is not None and (not isinstance(family, str) or not family):
        raise ModelEditError("Family must be an existing canonical family")
    if effort is not None and (not isinstance(effort, str) or not effort):
        raise ModelEditError("Effort must be a non-empty canonical value")

    return _make_candidate(
        source_root,
        "agents set-model",
        {"role": role, "family": family, "effort": effort},
    )


def _format_preview_human(preview: dict[str, Any]) -> str:
    """Human view of the same JSON-serializable preview object."""
    lines = [f"{preview['operation']}: {preview['result']}", f"source: {preview['context']['source']}"]
    for row in preview["data"]["roles"]:
        lines.append(
            f"{row['role']} ({row['identity']}): family {row['family']['old']} -> {row['family']['new']}; "
            f"effort {row['effort']['old']} -> {row['effort']['new']}; "
            f"OpenCode {row['models']['opencode']['old']} -> {row['models']['opencode']['new']}; "
            f"Codex {row['models']['codex']['old']} -> {row['models']['codex']['new']} "
            f"({row['representation']['codex']})"
        )
    paths = preview["data"]["write_set"]
    lines.append("write_set: " + (", ".join(paths) if paths else "(none)"))
    return "\n".join(lines)
