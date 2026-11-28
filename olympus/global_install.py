"""Private, PowerShell-free per-user OpenCode lifecycle for staged sources."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config_apply, config_apply_transaction, global_readonly, source_edit, user_config


_MANIFEST = global_readonly._MANIFEST
_SCRATCH = config_apply_transaction._SCRATCH
_RECORD = config_apply_transaction._RECORD
_SCHEMA = 1
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_RELEASE = re.compile(
    r"v(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)(?:-(?P<stage>alpha|beta|rc)\."
    r"(?P<sequence>0|[1-9][0-9]*))?\Z"
)
_STATES = ("PREPARING", "PREPARED", "COMMITTED")


class GlobalInstallError(RuntimeError):
    """A global lifecycle operation was rejected or could not be confirmed."""

    def __init__(self, message: str, code: int = 3):
        super().__init__(message)
        self.code = code


def _require_no_posix_acl(path: Path, kind: str, *,
                          expected_identity: tuple[int, int] | None = None,
                          code: int = 3) -> None:
    """Fail closed before force replaces or chmods Linux resources with ACL policy."""
    if not sys.platform.startswith("linux"):
        return
    attribute = {
        "access": "system.posix_acl_access",
        "default": "system.posix_acl_default",
    }.get(kind)
    if attribute is None:
        raise GlobalInstallError("Unsupported Linux ACL inspection kind.", code)
    listxattr = getattr(os, "listxattr", None)
    if not callable(listxattr):
        raise GlobalInstallError(f"Cannot establish Linux ACL state for {path}.", code)
    descriptor = -1
    try:
        before = os.lstat(path)
        if (stat.S_ISLNK(before.st_mode)
                or getattr(before, "st_file_attributes", 0) & global_readonly._REPARSE
                or not (stat.S_ISREG(before.st_mode) or stat.S_ISDIR(before.st_mode))
                or kind == "default" and not stat.S_ISDIR(before.st_mode)):
            raise GlobalInstallError(f"Unsafe Linux ACL inspection target: {path}", code)
        identity = (before.st_dev, before.st_ino)
        if expected_identity is not None and identity != expected_identity:
            raise GlobalInstallError(f"Linux ACL inspection target changed: {path}", code)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        if stat.S_ISDIR(before.st_mode):
            flags |= getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != identity:
            raise GlobalInstallError(f"Linux ACL inspection target changed while opening: {path}", code)
        try:
            attributes = set(listxattr(descriptor))
        except (OSError, TypeError, NotImplementedError) as error:
            raise GlobalInstallError(
                f"Cannot establish Linux ACL state for {path}: {error}", code,
            ) from error
        placed = os.lstat(path)
        if ((placed.st_dev, placed.st_ino) != identity
                or (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino) != identity):
            raise GlobalInstallError(f"Linux ACL inspection target changed during inspection: {path}", code)
        if attribute in attributes:
            raise GlobalInstallError(
                f"Force repair refuses to alter {kind}-ACL-bearing managed resource: {path}", code,
            )
    except GlobalInstallError:
        raise
    except (OSError, TypeError, NotImplementedError) as error:
        raise GlobalInstallError(
            f"Cannot establish Linux ACL state for {path}: {error}", code,
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


@dataclass(frozen=True, slots=True)
class LifecycleOutcome:
    operation: str
    result: str
    root: str
    version: str | None = None
    changed_paths: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True, slots=True)
class _Candidate:
    source: Path
    version: str
    commit: str
    expected: dict[str, bytes]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class _Change:
    path: str
    old: bytes | None
    new: bytes | None
    old_mode: int | None
    new_mode: int | None


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _candidate(source: Path, version: str, commit: str) -> _Candidate:
    if not isinstance(source, Path) or not source.is_absolute():
        raise GlobalInstallError("Staged source must be an absolute directory.")
    try:
        source = source.resolve(strict=True)
        source_edit._safe_root_metadata(source)
    except (OSError, RuntimeError, source_edit.BatchError) as error:
        raise GlobalInstallError(f"Staged source is unavailable or unsafe: {error}") from error
    if not isinstance(version, str) or (
        version != "local" and _RELEASE.fullmatch(version) is None
    ):
        raise GlobalInstallError("Staged source version must be 'local' or a supported release tag.")
    if not isinstance(commit, str) or not commit.strip():
        raise GlobalInstallError("Staged source commit identity must be a non-empty string.")
    try:
        from .cli import load_renderer

        expected = global_readonly._expected(
            source, load_renderer(source), ("opencode",), include_default_agent=True,
        )["opencode"]
        user_config.apply_to_expected(source, expected)
    except Exception as error:
        raise GlobalInstallError(f"Cannot stage a verified OpenCode renderer inventory: {error}") from error
    fingerprint = _digest(_canonical({path: _digest(raw) for path, raw in sorted(expected.items())}))
    return _Candidate(source, version, commit.strip(), expected, fingerprint)


def _ensure_root(root: Path, *, create: bool) -> tuple[Path, tuple[int, int]]:
    try:
        global_readonly._root(root)
        if root == Path.home().resolve():
            raise global_readonly.GlobalFault("unsafe_global_root", "The user home directory is not an OpenCode config root.")
        if sys.platform.startswith("linux"):
            return global_readonly._ensure_linux_directory(root, create=create)
        missing: list[Path] = []
        cursor = root
        while True:
            try:
                metadata = os.lstat(cursor)
            except FileNotFoundError:
                if not create:
                    raise GlobalInstallError(f"Global OpenCode root does not exist: {root}")
                missing.append(cursor)
                parent = cursor.parent
                if parent == cursor:
                    raise GlobalInstallError("Cannot create a global config filesystem root.")
                cursor = parent
                continue
            if (stat.S_ISLNK(metadata.st_mode) or
                    getattr(metadata, "st_file_attributes", 0) & global_readonly._REPARSE or
                    not stat.S_ISDIR(metadata.st_mode)):
                raise GlobalInstallError(f"Global OpenCode root traverses an unsafe path: {cursor}")
            break
        for directory in reversed(missing):
            try:
                os.mkdir(directory, 0o700)
            except FileExistsError:
                pass
            metadata = os.lstat(directory)
            if (stat.S_ISLNK(metadata.st_mode) or
                    getattr(metadata, "st_file_attributes", 0) & global_readonly._REPARSE or
                    not stat.S_ISDIR(metadata.st_mode)):
                raise GlobalInstallError(f"Global OpenCode root changed while being created: {directory}")
        resolved = global_readonly._root(root.resolve(strict=True))
        metadata = os.lstat(resolved)
        return resolved, (metadata.st_dev, metadata.st_ino)
    except global_readonly.GlobalFault as error:
        raise GlobalInstallError(str(error), error.code) from error
    except (OSError, RuntimeError) as error:
        raise GlobalInstallError(f"Cannot safely resolve global OpenCode root: {error}") from error


def _resolve_root(*, create: bool) -> tuple[Path, tuple[int, int]]:
    try:
        root = global_readonly.resolve_roots(("opencode",))["opencode"]
    except (global_readonly.GlobalFault, OSError, RuntimeError) as error:
        raise GlobalInstallError(f"Cannot resolve the global OpenCode root: {error}") from error
    return _ensure_root(root, create=create)


def _verify_root(root: Path, identity: tuple[int, int]) -> None:
    if sys.platform.startswith("linux"):
        try:
            global_readonly._verify_linux_directory(root, identity)
        except global_readonly.GlobalFault as error:
            raise GlobalInstallError(str(error), error.code) from error


def _check_roots(source: Path, root: Path) -> None:
    if root == source or root.is_relative_to(source) or source.is_relative_to(root):
        raise GlobalInstallError("The global config root must not overlap the staged source checkout.")


def _existing_lock(root: Path, root_identity: tuple[int, int]):
    lock_path = root / source_edit._LOCK_NAME
    _verify_root(root, root_identity)
    try:
        os.lstat(lock_path)
    except FileNotFoundError:
        _verify_root(root, root_identity)
        return None
    except OSError as error:
        raise GlobalInstallError(f"Cannot inspect the stable global writer lock: {error}", 4) from error
    _verify_root(root, root_identity)
    try:
        lock = source_edit._acquire_lock(root, create=False)
    except source_edit.LockError as error:
        raise GlobalInstallError(f"Cannot acquire the existing stable global writer lock: {error}") from error
    try:
        _verify_root(root, root_identity)
    except BaseException:
        source_edit._release_lock(lock)
        raise
    return lock


def _read(root: Path, relative: str) -> tuple[bytes | None, os.stat_result | None]:
    try:
        source_edit._relative_parts(relative)
    except source_edit.BatchError as error:
        raise GlobalInstallError(str(error)) from error
    path, before, issue = config_apply._lstat_target_path(root, relative)
    if issue:
        raise GlobalInstallError(issue)
    if before is None:
        return None, None
    raw, issue = config_apply._read_target_file(root, relative, max_bytes=2_000_000)
    if issue or raw is None:
        raise GlobalInstallError(issue or f"Cannot safely read global resource: {relative}")
    _, after, issue = config_apply._lstat_target_path(root, relative)
    if (issue or after is None or path is None or
            (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)):
        raise GlobalInstallError(issue or f"Global resource changed while reading: {relative}")
    return raw, after


def _current_config(root: Path) -> tuple[str | None, bytes | None, os.stat_result | None]:
    json_raw, json_meta = _read(root, "opencode.json")
    jsonc_raw, jsonc_meta = _read(root, "opencode.jsonc")
    if json_raw is not None and jsonc_raw is not None:
        raise GlobalInstallError(
            "Both OpenCode global config formats exist; precedence is ambiguous."
        )
    if json_raw is not None:
        return "opencode.json", json_raw, json_meta
    if jsonc_raw is not None:
        return "opencode.jsonc", jsonc_raw, jsonc_meta
    return None, None, None


def _skip_trivia(text: str, index: int) -> int:
    while index < len(text):
        if text[index].isspace() or (index == 0 and text[index] == "\ufeff"):
            index += 1
        elif text.startswith("//", index):
            end = text.find("\n", index + 2)
            index = len(text) if end < 0 else end + 1
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise ValueError("Unterminated JSONC block comment")
            index = end + 2
        else:
            return index
    return index


def _string_token(text: str, index: int) -> tuple[str, int]:
    if index >= len(text) or text[index] != '"':
        raise ValueError("Expected a JSON string")
    try:
        value, end = json.JSONDecoder().raw_decode(text, index)
    except ValueError as error:
        raise ValueError("Invalid JSON string") from error
    if not isinstance(value, str):
        raise ValueError("Expected a JSON string")
    return value, end


def _value_end(text: str, index: int) -> int:
    index = _skip_trivia(text, index)
    if index >= len(text):
        raise ValueError("Missing JSONC value")
    char = text[index]
    if char == '"':
        return _string_token(text, index)[1]
    if char in "{[":
        closing = "}" if char == "{" else "]"
        cursor = _skip_trivia(text, index + 1)
        if cursor < len(text) and text[cursor] == closing:
            return cursor + 1
        while cursor < len(text):
            if char == "{":
                _, cursor = _string_token(text, cursor)
                cursor = _skip_trivia(text, cursor)
                if cursor >= len(text) or text[cursor] != ":":
                    raise ValueError("Invalid JSONC object member")
                cursor = _value_end(text, cursor + 1)
            else:
                cursor = _value_end(text, cursor)
            cursor = _skip_trivia(text, cursor)
            if cursor < len(text) and text[cursor] == ",":
                cursor = _skip_trivia(text, cursor + 1)
                if cursor < len(text) and text[cursor] == closing:
                    return cursor + 1
                continue
            if cursor < len(text) and text[cursor] == closing:
                return cursor + 1
            raise ValueError("Invalid JSONC collection delimiter")
        raise ValueError("Unterminated JSONC collection")
    end = index
    while end < len(text) and not text[end].isspace() and text[end] not in ",}]":
        if text.startswith(("//", "/*"), end):
            break
        end += 1
    if end == index:
        raise ValueError("Invalid JSONC primitive")
    return end


def _config_snapshot(raw: bytes) -> tuple[dict, str, list[dict[str, Any]]]:
    try:
        text = raw.decode("utf-8")
        cleaned = global_readonly._jsonc_without_comments(raw)
        config = json.loads(
            cleaned,
            object_pairs_hook=source_edit._json_object_no_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
        if not isinstance(config, dict):
            raise ValueError("OpenCode config root must be an object")
        index = _skip_trivia(text, 0)
        if index >= len(text) or text[index] != "{":
            raise ValueError("OpenCode config root must be an object")
        fields: list[dict[str, Any]] = []
        cursor = _skip_trivia(text, index + 1)
        if cursor < len(text) and text[cursor] == "}":
            return config, text, fields
        previous_comma: int | None = None
        while cursor < len(text):
            key_start = cursor
            key, cursor = _string_token(text, cursor)
            cursor = _skip_trivia(text, cursor)
            if cursor >= len(text) or text[cursor] != ":":
                raise ValueError("OpenCode config has an invalid property delimiter")
            value_start = _skip_trivia(text, cursor + 1)
            value_stop = _value_end(text, value_start)
            member = {
                "key": key, "key_start": key_start, "value_start": value_start,
                "value_end": value_stop, "comma_before": previous_comma,
                "comma_after": None,
            }
            fields.append(member)
            cursor = _skip_trivia(text, value_stop)
            if cursor < len(text) and text[cursor] == ",":
                member["comma_after"] = cursor
                previous_comma = cursor
                cursor = _skip_trivia(text, cursor + 1)
                if cursor < len(text) and text[cursor] == "}":
                    break
                continue
            if cursor < len(text) and text[cursor] == "}":
                break
            raise ValueError("OpenCode config has an invalid object delimiter")
        if cursor >= len(text) or text[cursor] != "}":
            raise ValueError("Unterminated OpenCode config object")
        return config, text, fields
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise GlobalInstallError(
            "OpenCode config is invalid or cannot be safely spliced without rewriting it."
        ) from error


def _splice_default_agent(raw: bytes, value_json: str | None) -> bytes:
    """Replace/remove only the root default_agent token, preserving other bytes."""
    config, text, fields = _config_snapshot(raw)
    matches = [field for field in fields if field["key"] == "default_agent"]
    if len(matches) > 1:
        raise GlobalInstallError("OpenCode config has duplicate default_agent fields.")
    if matches:
        field = matches[0]
        if value_json is not None:
            replacement = text[:field["value_start"]] + value_json + text[field["value_end"]:]
        else:
            start, end = field["key_start"], field["value_end"]
            if field["comma_after"] is not None:
                end = field["comma_after"] + 1
            elif field["comma_before"] is not None:
                start = field["comma_before"]
            replacement = text[:start] + text[end:]
    elif value_json is None:
        replacement = text
    else:
        opening = _skip_trivia(text, 0)
        token = json.dumps("default_agent", ensure_ascii=False) + ": " + value_json
        comma = "," if fields else ""
        replacement = text[:opening + 1] + token + comma + text[opening + 1:]
    try:
        updated = replacement.encode("utf-8")
        _config_snapshot(updated)
    except UnicodeError as error:
        raise GlobalInstallError("OpenCode config could not be safely encoded.") from error
    return updated


def _receipt(config_path: str, previous_present: bool, previous_value_json: str | None) -> dict:
    return {
        "version": 1, "state": "committed", "config_path": config_path,
        "installed_value": "kael", "previous_present": previous_present,
        "previous_value_json": previous_value_json,
        "restore_action": ("set" if previous_present and
                           json.loads(previous_value_json) != "kael" else "remove"),
    }


def _receipt_previous(receipt: dict) -> str | None:
    if receipt["restore_action"] == "set":
        return receipt["previous_value_json"]
    if receipt["restore_action"] == "remove":
        return None
    raise GlobalInstallError("Default-agent receipt has no supported restore action.", 4)


def _manifest_bytes(version: str, commit: str, entries: dict[str, bytes],
                    receipt: dict) -> bytes:
    value = {
        "schema_version": 1, "scope": "global", "installed_harnesses": ["opencode"],
        "installed_version": version, "installed_from_commit": commit,
        "managed_files": [
            {"path": path, "sha256": _digest(raw)} for path, raw in sorted(entries.items())
        ],
        "default_agent_receipt": receipt,
    }
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _manifest(root: Path, candidate: _Candidate) -> tuple[dict | None, dict[str, str], bytes | None, os.stat_result | None]:
    raw, metadata = _read(root, _MANIFEST)
    if raw is None:
        return None, {}, None, None
    try:
        data, entries = global_readonly._parse_manifest_bytes(raw, "opencode", candidate.expected)
    except global_readonly.GlobalFault as error:
        raise GlobalInstallError(str(error), error.code) from error
    return data, entries, raw, metadata


def _validate_owned_files(root: Path, entries: dict[str, str], *,
                          allow_drift: bool = False) -> dict[str, tuple[bytes | None, os.stat_result | None]]:
    result: dict[str, tuple[bytes | None, os.stat_result | None]] = {}
    for relative, expected_hash in sorted(entries.items()):
        raw, metadata = _read(root, relative)
        if raw is None or metadata is None:
            if allow_drift:
                result[relative] = (None, None)
                continue
            raise GlobalInstallError(f"Manifest-owned global resource is missing: {relative}", 1)
        if _digest(raw) != expected_hash and not allow_drift:
            raise GlobalInstallError(f"Manifest-owned global resource drifted: {relative}", 1)
        result[relative] = (raw, metadata)
    return result


def _version_compare(left: str, right: str) -> int | None:
    a, b = _RELEASE.fullmatch(left), _RELEASE.fullmatch(right)
    if a is None or b is None:
        return 0 if left == right else None
    for part in ("major", "minor", "patch"):
        difference = int(a[part]) - int(b[part])
        if difference:
            return 1 if difference > 0 else -1
    a_stable, b_stable = not a["stage"], not b["stage"]
    if a_stable != b_stable:
        return 1 if a_stable else -1
    if a_stable:
        return 0
    order = {"alpha": 1, "beta": 2, "rc": 3}
    stage_difference = order[a["stage"]] - order[b["stage"]]
    if stage_difference:
        return 1 if stage_difference > 0 else -1
    return (int(a["sequence"]) > int(b["sequence"])) - (int(a["sequence"]) < int(b["sequence"]))


_SHARED_PRIMARY_CAP_MARKER = b"MAX_ACTIVE_CHILDREN = "
_SHARED_PRIMARY_CAP = re.compile(rb"MAX_ACTIVE_CHILDREN = ([0-9]+)(?=`|\))")


def _assert_shared_primary_caps_coherent(
    current: dict[str, tuple[bytes | None, os.stat_result | None]],
) -> None:
    pair = [current.get(f"agents/{role}.md") for role in ("kael", "atlas")]
    if any(item is None or item[0] is None for item in pair):
        return
    kael, atlas = (item[0] for item in pair)
    if (_SHARED_PRIMARY_CAP_MARKER not in kael
            or _SHARED_PRIMARY_CAP_MARKER not in atlas):
        return

    caps = []
    for prompt in (kael, atlas):
        matches = list(_SHARED_PRIMARY_CAP.finditer(prompt))
        if (len(matches) != prompt.count(_SHARED_PRIMARY_CAP_MARKER)
                or not matches
                or any(not 1 <= int(match.group(1)) <= 8 for match in matches)
                or len({int(match.group(1)) for match in matches}) != 1):
            raise GlobalInstallError(
                "Installed primary cap mismatch: shared Kael/Atlas markers are malformed or inconsistent."
            )
        caps.append(int(matches[0].group(1)))
    if caps[0] != caps[1]:
        raise GlobalInstallError(
            f"Installed primary cap mismatch: Kael={caps[0]}, Atlas={caps[1]}; refusing update."
        )


def _inventory_for_receipt(expected: dict[str, bytes], owns_guard: bool) -> dict[str, bytes]:
    return {path: raw for path, raw in expected.items()
            if path != "opencode.jsonc" or owns_guard}


def _make_change(path: str, old: bytes | None, old_meta: os.stat_result | None,
                 new: bytes | None, *, default_mode: int = 0o644) -> _Change | None:
    if old == new:
        return None
    old_mode = stat.S_IMODE(old_meta.st_mode) if old_meta is not None else None
    new_mode = old_mode if old_mode is not None else (default_mode if os.name != "nt" else 0o666)
    return _Change(path, old, new, old_mode, new_mode if new is not None else None)


def _sort_changes(changes: list[_Change]) -> tuple[_Change, ...]:
    return tuple(sorted((item for item in changes if item.path != _MANIFEST), key=lambda item: item.path)
                 + [item for item in changes if item.path == _MANIFEST])


def _require_default_acl_for_missing_parents(root: Path, relative: str, *,
                                            root_identity: tuple[int, int],
                                            code: int) -> None:
    current = root
    metadata = os.lstat(root)
    if (metadata.st_dev, metadata.st_ino) != root_identity:
        raise GlobalInstallError("Global root changed before ACL parent preflight.", code)
    for part in source_edit._relative_parts(relative)[:-1]:
        child = current / part
        try:
            child_metadata = os.lstat(child)
        except FileNotFoundError:
            _require_no_posix_acl(
                current, "default",
                expected_identity=(metadata.st_dev, metadata.st_ino), code=code,
            )
            return
        except OSError as error:
            raise GlobalInstallError(f"Cannot inspect global resource parent {child}: {error}", code) from error
        if (stat.S_ISLNK(child_metadata.st_mode)
                or getattr(child_metadata, "st_file_attributes", 0) & global_readonly._REPARSE
                or not stat.S_ISDIR(child_metadata.st_mode)
                or child_metadata.st_dev != metadata.st_dev):
            raise GlobalInstallError(f"Unsafe global resource parent: {child}", code)
        current = child
        metadata = child_metadata


def _force_acl_preflight(root: Path, root_identity: tuple[int, int],
                         changes: tuple[_Change, ...], *, code: int = 3) -> None:
    if not sys.platform.startswith("linux") or not changes:
        return
    _require_no_posix_acl(root, "default", expected_identity=root_identity, code=code)
    for item in changes:
        if item.old is not None:
            current, metadata = _read(root, item.path)
            if (current != item.old or metadata is None
                    or stat.S_IMODE(metadata.st_mode) != item.old_mode):
                raise GlobalInstallError(
                    f"Global resource changed before ACL preflight: {item.path}", code,
                )
            _require_no_posix_acl(
                root / item.path, "access",
                expected_identity=(metadata.st_dev, metadata.st_ino), code=code,
            )
        _require_default_acl_for_missing_parents(
            root, item.path, root_identity=root_identity, code=code,
        )


def _build_install(root: Path, candidate: _Candidate, *, update: bool,
                   force: bool = False) -> tuple[_Change, ...]:
    manifest, old_entries, old_manifest, manifest_meta = _manifest(root, candidate)
    if manifest is None:
        if update:
            raise GlobalInstallError("Cannot update an OpenCode global installation without its ownership manifest.")
        config_path, config_raw, config_meta = _current_config(root)
        if config_raw is not None:
            try:
                global_readonly._unowned_opencode_guard(root)
            except global_readonly.GlobalFault as error:
                raise GlobalInstallError(str(error), error.code) from error
            config, text, fields = _config_snapshot(config_raw)
            defaults = [field for field in fields if field["key"] == "default_agent"]
            if defaults and config.get("default_agent") == "kael":
                raise GlobalInstallError(
                    "Existing default_agent is already kael without Olympus ownership evidence."
                )
            previous = text[defaults[0]["value_start"]:defaults[0]["value_end"]] if defaults else None
            if defaults and not isinstance(config.get("default_agent"), str):
                raise GlobalInstallError("Existing default_agent must be a string before Olympus can manage it.")
            receipt = _receipt(config_path, bool(defaults), previous)
            config_new = _splice_default_agent(config_raw, json.dumps("kael"))
            owned_expected = _inventory_for_receipt(candidate.expected, False)
        else:
            config_path = "opencode.jsonc"
            receipt = _receipt(config_path, False, None)
            config_new = candidate.expected["opencode.jsonc"]
            owned_expected = _inventory_for_receipt(candidate.expected, True)

        changes: list[_Change] = []
        for relative, desired in sorted(owned_expected.items()):
            current, metadata = _read(root, relative)
            if current is not None:
                raise GlobalInstallError(f"Unowned global destination already exists: {relative}")
            change = _make_change(relative, None, None, desired)
            if change:
                changes.append(change)
        if config_path != "opencode.jsonc" or config_raw is not None:
            change = _make_change(config_path, config_raw, config_meta, config_new)
            if change:
                changes.append(change)
        manifest_new = _manifest_bytes(candidate.version, candidate.commit, owned_expected, receipt)
        change = _make_change(_MANIFEST, None, None, manifest_new, default_mode=0o600)
        if change:
            changes.append(change)
        return _sort_changes(changes)

    if not update:
        if manifest["installed_version"] == candidate.version:
            current = _validate_owned_files(root, old_entries)
            if all(raw == candidate.expected.get(path) for path, (raw, _) in current.items()):
                try:
                    global_readonly._default_agent_status(root, manifest)
                    if "opencode.jsonc" not in old_entries:
                        global_readonly._unowned_opencode_guard(root)
                except global_readonly.GlobalFault as error:
                    raise GlobalInstallError(str(error), error.code) from error
                return ()
        raise GlobalInstallError("An OpenCode global installation already exists; use update for a newer source.")

    receipt = manifest[global_readonly._DEFAULT_AGENT_RECEIPT]
    if receipt["state"] != "committed":
        raise GlobalInstallError(
            f"OpenCode default-agent receipt is {receipt['state']}; recover its owning lifecycle first."
        )
    old_version = manifest["installed_version"]
    if force and old_version == candidate.version and manifest["installed_from_commit"] != candidate.commit:
        raise GlobalInstallError("Same-version force repair requires the exact manifest commit identity.")
    comparison = _version_compare(candidate.version, old_version)
    if comparison is None:
        raise GlobalInstallError("Local and release versions cannot be ordered; refusing an implicit version transition.")
    if comparison < 0:
        raise GlobalInstallError(f"Refusing to downgrade OpenCode global installation from {old_version} to {candidate.version}.")
    owns_guard = "opencode.jsonc" in old_entries
    current = _validate_owned_files(root, old_entries, allow_drift=force)
    if update:
        _assert_shared_primary_caps_coherent(current)
    if force and owns_guard:
        guard, _ = _read(root, "opencode.jsonc")
        if guard is None or _digest(guard) != old_entries["opencode.jsonc"]:
            raise GlobalInstallError(
                "Force repair will not overwrite a changed or missing receipt-owned OpenCode config."
            )
    if comparison == 0:
        if force:
            desired_entries = _inventory_for_receipt(candidate.expected, owns_guard)
            if (set(desired_entries) != set(old_entries)
                    or any(_digest(desired_entries[path]) != old_entries[path]
                           for path in desired_entries)):
                raise GlobalInstallError(
                    "Same-version source differs from the installed manifest; refusing force repair."
                )
            changes = []
            for relative, desired in sorted(desired_entries.items()):
                old, metadata = current[relative]
                change = _make_change(relative, old, metadata, desired)
                if change:
                    changes.append(change)
            if changes:
                manifest_new = _manifest_bytes(
                    candidate.version, candidate.commit, desired_entries, receipt,
                )
                if manifest_new == old_manifest:
                    manifest_new += b"\n"
                change = _make_change(
                    _MANIFEST, old_manifest, manifest_meta, manifest_new, default_mode=0o600,
                )
                if change is None:
                    raise GlobalInstallError("Force repair could not preserve manifest-last transaction ordering.", 4)
                changes.append(change)
            return _sort_changes(changes)
        if not all(raw == candidate.expected.get(path) for path, (raw, _) in current.items()):
            raise GlobalInstallError(
                "Same-version source differs from installed managed bytes; refusing an implicit repair."
            )
        return ()

    config_path, config_raw, _ = _current_config(root)
    if config_raw is not None:
        try:
            global_readonly._unowned_opencode_guard(root)
        except global_readonly.GlobalFault as error:
            raise GlobalInstallError(str(error), error.code) from error
        if "opencode.jsonc" in old_entries and config_path == "opencode.json":
            raise GlobalInstallError("An unowned opencode.json conflicts with the owned opencode.jsonc guard.")
    desired_entries = _inventory_for_receipt(candidate.expected, owns_guard)
    changes = []
    for relative, desired in sorted(desired_entries.items()):
        old_pair = current.get(relative)
        if old_pair is None:
            old, metadata = _read(root, relative)
            if old is not None:
                raise GlobalInstallError(f"New global destination collides with an unowned resource: {relative}")
        else:
            old, metadata = old_pair
        change = _make_change(relative, old, metadata, desired)
        if change:
            changes.append(change)
    new_manifest = _manifest_bytes(candidate.version, candidate.commit, desired_entries, receipt)
    change = _make_change(_MANIFEST, old_manifest, manifest_meta, new_manifest, default_mode=0o600)
    if change:
        changes.append(change)
    return _sort_changes(changes)


def _build_uninstall(root: Path, candidate: _Candidate) -> tuple[_Change, ...]:
    manifest, entries, manifest_raw, manifest_meta = _manifest(root, candidate)
    if manifest is None or manifest_raw is None:
        return ()
    current = _validate_owned_files(root, entries)
    receipt = manifest[global_readonly._DEFAULT_AGENT_RECEIPT]
    if receipt["state"] != "committed":
        raise GlobalInstallError(
            f"OpenCode default-agent receipt is {receipt['state']}; recover its owning lifecycle first."
        )
    config_path, config_raw, config_meta = _current_config(root)
    if config_raw is not None:
        try:
            global_readonly._unowned_opencode_guard(root)
        except global_readonly.GlobalFault as error:
            raise GlobalInstallError(str(error), error.code) from error

    changes: list[_Change] = []
    if config_path == receipt["config_path"] and config_raw is not None and config_path not in entries:
        config, _, fields = _config_snapshot(config_raw)
        default_fields = [field for field in fields if field["key"] == "default_agent"]
        if default_fields and config.get("default_agent") == receipt["installed_value"]:
            restored = _splice_default_agent(config_raw, _receipt_previous(receipt))
            change = _make_change(config_path, config_raw, config_meta, restored)
            if change:
                changes.append(change)
    for relative, (raw, metadata) in current.items():
        change = _make_change(relative, raw, metadata, None)
        if change:
            changes.append(change)
    change = _make_change(_MANIFEST, manifest_raw, manifest_meta, None, default_mode=0o600)
    if change:
        changes.append(change)
    return _sort_changes(changes)


def _ensure_parent(root: Path, relative: str, lock, identity) -> None:
    parts = source_edit._relative_parts(relative)[:-1]
    current = root
    root_dev = os.lstat(root).st_dev
    for part in parts:
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            source_edit._lock_identity(lock, identity)
            try:
                os.mkdir(current, 0o755)
            except FileExistsError:
                pass
            metadata = os.lstat(current)
        if (stat.S_ISLNK(metadata.st_mode) or
                getattr(metadata, "st_file_attributes", 0) & global_readonly._REPARSE or
                not stat.S_ISDIR(metadata.st_mode) or metadata.st_dev != root_dev):
            raise GlobalInstallError(f"Unsafe global resource parent: {current}", 4)


def _record_for(root: Path, candidate: _Candidate, operation: str,
                changes: tuple[_Change, ...], identity: tuple[int, int]) -> dict:
    manifest_change = next(item for item in changes if item.path == _MANIFEST)
    return {
        "schema_version": _SCHEMA, "kind": "linux_global_lifecycle",
        "operation_id": uuid.uuid4().hex, "operation": operation,
        "target_root": str(root), "source_root": str(candidate.source),
        "source_version": candidate.version, "source_commit": candidate.commit,
        "source_fingerprint": candidate.fingerprint,
        "scratch_identity": {"st_dev": 0, "st_ino": 0},
        "lock_identity": {"path": source_edit._LOCK_NAME, "st_dev": identity[0], "st_ino": identity[1]},
        "state": "PREPARING",
        "manifest_old_b64": (base64.b64encode(manifest_change.old).decode("ascii")
                             if manifest_change.old is not None else None),
        "manifest_new_b64": (base64.b64encode(manifest_change.new).decode("ascii")
                             if manifest_change.new is not None else None),
        "files": [
            {
                "path": item.path, "old_present": item.old is not None,
                "old_sha256": _digest(item.old) if item.old is not None else None,
                "old_mode": item.old_mode, "new_present": item.new is not None,
                "new_sha256": _digest(item.new) if item.new is not None else None,
                "new_mode": item.new_mode,
                "backup": f"backups/file-{index:04d}.old" if item.old is not None else None,
                "staged": f"staged/file-{index:04d}.new" if item.new is not None else None,
            }
            for index, item in enumerate(changes)
        ],
    }


def _persist_record(root: Path, scratch: Path, record: dict, lock, identity,
                    previous: tuple[dict, bytes, os.stat_result] | None = None,
                    *, force: bool = False):
    temporary_relative = f"{_SCRATCH}/.record.json.tmp"
    record_relative = f"{_SCRATCH}/{_RECORD}"
    temporary = root / temporary_relative
    payload = _canonical(record)
    try:
        if force:
            _require_no_posix_acl(scratch, "default", code=4)
        source_edit._write_private_file(
            temporary, root, temporary_relative, payload, 0o600 if os.name != "nt" else 0o666,
            lock, identity,
        )
        if force:
            _require_no_posix_acl(temporary, "access", code=4)
        if previous is None:
            try:
                os.lstat(root / record_relative)
            except FileNotFoundError:
                pass
            else:
                raise GlobalInstallError("Lifecycle record path unexpectedly exists.", 4)
        else:
            current, metadata = _read(root, record_relative)
            if current != previous[1] or metadata is None or (
                metadata.st_dev, metadata.st_ino
            ) != (previous[2].st_dev, previous[2].st_ino):
                raise GlobalInstallError("Lifecycle record changed before state transition.", 4)
            if force:
                _require_no_posix_acl(
                    root / record_relative, "access",
                    expected_identity=(metadata.st_dev, metadata.st_ino), code=4,
                )
        if force:
            _require_no_posix_acl(scratch, "default", code=4)
            _require_no_posix_acl(temporary, "access", code=4)
        source_edit._lock_identity(lock, identity)
        os.replace(temporary, root / record_relative)
        source_edit._sync_directory(scratch)
        written, metadata = _read(root, record_relative)
        if written != payload or metadata is None:
            raise GlobalInstallError("Persisted lifecycle record failed verification.", 4)
        if force:
            _require_no_posix_acl(
                root / record_relative, "access",
                expected_identity=(metadata.st_dev, metadata.st_ino), code=4,
            )
        return record, written, metadata
    except GlobalInstallError:
        raise
    except (OSError, source_edit.BatchError) as error:
        raise GlobalInstallError(f"Cannot persist lifecycle journal: {error}", 4) from error


def _safe_remove(root: Path, relative: str, raw: bytes, mode: int, lock, identity,
                 root_identity: tuple[int, int]) -> None:
    current, metadata = _read(root, relative)
    if current != raw or metadata is None or stat.S_IMODE(metadata.st_mode) != mode:
        raise GlobalInstallError(f"Refusing to remove changed lifecycle evidence: {relative}", 4)
    _verify_root(root, root_identity)
    source_edit._lock_identity(lock, identity)
    current_again, metadata_again = _read(root, relative)
    if (current_again != current or metadata_again is None or
            (metadata_again.st_dev, metadata_again.st_ino) != (metadata.st_dev, metadata.st_ino)):
        raise GlobalInstallError(f"Lifecycle evidence changed before cleanup: {relative}", 4)
    _verify_root(root, root_identity)
    try:
        os.unlink(root / relative)
    except OSError as error:
        raise GlobalInstallError(f"Cannot remove lifecycle evidence {relative}: {error}", 4) from error


def _record_context(root: Path, lock):
    scratch = root / _SCRATCH
    try:
        metadata = os.lstat(scratch)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise GlobalInstallError(f"Cannot inspect lifecycle scratch: {error}", 4) from error
    if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or
            getattr(metadata, "st_file_attributes", 0) & global_readonly._REPARSE):
        raise GlobalInstallError("Lifecycle scratch is linked or not a directory.", 4)
    top = set(os.listdir(scratch))
    if _RECORD not in top:
        raise GlobalInstallError("Lifecycle scratch has no authoritative record; preserve its evidence.", 4)
    raw, record_metadata = _read(root, f"{_SCRATCH}/{_RECORD}")
    try:
        if raw is None or len(raw) > 6_000_000:
            raise ValueError("missing or oversized record")
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=source_edit._json_object_no_duplicates)
    except (UnicodeError, ValueError, TypeError) as error:
        raise GlobalInstallError("Lifecycle record is invalid; preserve its evidence.", 4) from error
    if raw != _canonical(record) or record_metadata is None:
        raise GlobalInstallError("Lifecycle record is not canonical; preserve its evidence.", 4)
    return record, raw, record_metadata, metadata, top


def _read_artifact(root: Path, relative: str, digest: str, mode: int, *, required: bool):
    raw, metadata = _read(root, relative)
    if raw is None or metadata is None:
        if required:
            raise GlobalInstallError(f"Required lifecycle evidence is missing: {relative}", 4)
        return None
    if _digest(raw) != digest or stat.S_IMODE(metadata.st_mode) != mode:
        raise GlobalInstallError(f"Lifecycle evidence changed or is corrupt: {relative}", 4)
    return raw, metadata


def _validate_record(root: Path, candidate: _Candidate, lock, record: Any, scratch_metadata,
                     top: set[str]) -> tuple[dict[str, dict], dict[str, tuple[bytes, os.stat_result] | None]]:
    required_fields = {
        "schema_version", "kind", "operation_id", "operation", "target_root", "source_root",
        "source_version", "source_commit", "source_fingerprint", "scratch_identity",
        "lock_identity", "state", "manifest_old_b64", "manifest_new_b64", "files",
    }
    if not isinstance(record, dict) or set(record) != required_fields:
        raise GlobalInstallError("Lifecycle record has missing or unexpected fields.", 4)
    if (type(record["schema_version"]) is not int or record["schema_version"] != _SCHEMA
            or record["kind"] != "linux_global_lifecycle"
            or re.fullmatch(r"[0-9a-f]{32}", str(record["operation_id"])) is None
            or record["operation"] not in ("install", "update", "uninstall")
            or record["target_root"] != str(root)
            or record["source_root"] != str(candidate.source)
            or record["source_version"] != candidate.version
            or record["source_commit"] != candidate.commit
            or record["source_fingerprint"] != candidate.fingerprint
            or record["state"] not in _STATES):
        raise GlobalInstallError("Lifecycle record identity, provenance, or state is invalid.", 4)
    lock_record = record["lock_identity"]
    identity = source_edit._lock_identity(lock)
    if (not isinstance(lock_record, dict) or set(lock_record) != {"path", "st_dev", "st_ino"}
            or lock_record["path"] != source_edit._LOCK_NAME
            or (lock_record["st_dev"], lock_record["st_ino"]) != identity):
        raise GlobalInstallError("Lifecycle record does not match the stable target lock.", 4)
    scratch_record = record["scratch_identity"]
    if (not isinstance(scratch_record, dict) or set(scratch_record) != {"st_dev", "st_ino"}
            or (scratch_record["st_dev"], scratch_record["st_ino"])
            != (scratch_metadata.st_dev, scratch_metadata.st_ino)):
        raise GlobalInstallError("Lifecycle scratch identity changed or is unsafe.", 4)
    if top - {_RECORD, ".record.json.tmp", "backups", "staged"}:
        raise GlobalInstallError("Lifecycle scratch contains unenumerated resources.", 4)
    if record["state"] != "PREPARING" and set(("backups", "staged")) - top:
        raise GlobalInstallError("Lifecycle scratch is incomplete; preserve its evidence.", 4)

    files = record["files"]
    if (not isinstance(files, list) or not files or not isinstance(files[-1], dict)
            or files[-1].get("path") != _MANIFEST):
        raise GlobalInstallError("Lifecycle file inventory is empty or not manifest-last.", 4)
    allowed = set(candidate.expected) | {"opencode.json"}
    file_map: dict[str, dict] = {}
    expected_backups, expected_staged = set(), set()
    previous = ""
    for index, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != {
            "path", "old_present", "old_sha256", "old_mode", "new_present", "new_sha256",
            "new_mode", "backup", "staged",
        }:
            raise GlobalInstallError("Lifecycle file entry is malformed.", 4)
        relative = item["path"]
        try:
            source_edit._relative_parts(relative)
        except source_edit.BatchError as error:
            raise GlobalInstallError(f"Lifecycle record contains an unsafe path: {relative!r}", 4) from error
        if (not isinstance(relative, str) or relative in file_map or
                relative != _MANIFEST and relative not in allowed or
                index < len(files) - 1 and relative <= previous):
            raise GlobalInstallError("Lifecycle file inventory is duplicated, unordered, or outside the OpenCode scope.", 4)
        previous = relative
        file_map[relative] = item
        for prefix, present_key, hash_key, mode_key, expected_names in (
            ("backup", "old_present", "old_sha256", "old_mode", expected_backups),
            ("staged", "new_present", "new_sha256", "new_mode", expected_staged),
        ):
            present, digest, mode = item[present_key], item[hash_key], item[mode_key]
            if type(present) is not bool:
                raise GlobalInstallError("Lifecycle presence marker is invalid.", 4)
            if not present:
                if digest is not None or mode is not None or item[prefix] is not None:
                    raise GlobalInstallError("Lifecycle absent-state metadata is contradictory.", 4)
            else:
                if (not isinstance(digest, str) or _HASH.fullmatch(digest) is None
                        or type(mode) is not int or not 0 <= mode <= 0o7777):
                    raise GlobalInstallError("Lifecycle evidence metadata is invalid.", 4)
                expected_name = (f"backups/file-{index:04d}.old" if prefix == "backup"
                                 else f"staged/file-{index:04d}.new")
                if item[prefix] != expected_name:
                    raise GlobalInstallError("Lifecycle evidence path is invalid.", 4)
                expected_names.add(expected_name.split("/", 1)[1])
    for directory, allowed_names in (("backups", expected_backups), ("staged", expected_staged)):
        path = root / _SCRATCH / directory
        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            if record["state"] == "PREPARING":
                continue
            raise GlobalInstallError(f"Lifecycle {directory} evidence is missing.", 4)
        except OSError as error:
            raise GlobalInstallError(f"Cannot inspect lifecycle {directory} evidence.", 4) from error
        if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or
                getattr(metadata, "st_file_attributes", 0) & global_readonly._REPARSE):
            raise GlobalInstallError(f"Lifecycle {directory} evidence is unsafe.", 4)
        if set(os.listdir(path)) - allowed_names:
            raise GlobalInstallError(f"Lifecycle {directory} contains unenumerated evidence.", 4)

    manifest_entry = file_map[_MANIFEST]
    try:
        old_manifest = (base64.b64decode(record["manifest_old_b64"], validate=True)
                        if record["manifest_old_b64"] is not None else None)
        new_manifest = (base64.b64decode(record["manifest_new_b64"], validate=True)
                        if record["manifest_new_b64"] is not None else None)
    except (ValueError, TypeError) as error:
        raise GlobalInstallError("Lifecycle manifest receipt is invalid.", 4) from error
    if ((old_manifest is None) != (not manifest_entry["old_present"])
            or (new_manifest is None) != (not manifest_entry["new_present"])
            or old_manifest is not None and _digest(old_manifest) != manifest_entry["old_sha256"]
            or new_manifest is not None and _digest(new_manifest) != manifest_entry["new_sha256"]):
        raise GlobalInstallError("Lifecycle manifest receipt contradicts its journal.", 4)
    manifest_maps: dict[str, dict[str, str] | None] = {"old": None, "new": None}
    manifest_values: dict[str, dict | None] = {"old": None, "new": None}
    for label, raw in (("old", old_manifest), ("new", new_manifest)):
        if raw is None:
            continue
        try:
            data, entries = global_readonly._parse_manifest_bytes(raw, "opencode", candidate.expected)
        except global_readonly.GlobalFault as error:
            raise GlobalInstallError(f"Lifecycle {label} manifest is invalid: {error}", 4) from error
        manifest_maps[label] = entries
        manifest_values[label] = data
        receipt = data.get(global_readonly._DEFAULT_AGENT_RECEIPT)
        if not isinstance(receipt, dict) or receipt.get("state") != "committed":
            raise GlobalInstallError(f"Lifecycle {label} manifest receipt is not committed.", 4)
        if ("opencode.jsonc" in entries and
                (receipt["config_path"] != "opencode.jsonc" or receipt["previous_present"])):
            raise GlobalInstallError(f"Lifecycle {label} owned guard receipt is contradictory.", 4)
        if (label == "new" and record["operation"] != "uninstall"
                and (data.get("installed_version") != candidate.version
                     or data.get("installed_from_commit") != candidate.commit)):
            raise GlobalInstallError("Lifecycle manifest version contradicts its source.", 4)
    if record["operation"] == "install" and old_manifest is not None:
        raise GlobalInstallError("Install journal unexpectedly has an old manifest.", 4)
    if record["operation"] in ("update", "uninstall") and old_manifest is None:
        raise GlobalInstallError("Lifecycle journal is missing its old manifest.", 4)
    if record["operation"] == "uninstall" and new_manifest is not None:
        raise GlobalInstallError("Uninstall journal unexpectedly has a new manifest.", 4)
    old_entries = manifest_maps["old"] or {}
    new_entries = manifest_maps["new"] or {}
    same_version_repair = False
    if record["operation"] == "install":
        receipt = manifest_values["new"][global_readonly._DEFAULT_AGENT_RECEIPT]
        expected_inventory = set(_inventory_for_receipt(
            candidate.expected, "opencode.jsonc" in new_entries,
        ))
        if set(new_entries) != expected_inventory:
            raise GlobalInstallError("Install journal inventory differs from the staged source.", 4)
        changed_managed = set(new_entries)
        if "opencode.jsonc" not in new_entries:
            config_item = file_map.get(receipt["config_path"])
            if config_item is None:
                raise GlobalInstallError("Install journal omits its receipt-owned user config edit.", 4)
        elif receipt["previous_present"]:
            raise GlobalInstallError("New guard receipt unexpectedly records a prior config value.", 4)
    elif record["operation"] == "update":
        old_value, new_value = manifest_values["old"], manifest_values["new"]
        if old_value[global_readonly._DEFAULT_AGENT_RECEIPT] != new_value[global_readonly._DEFAULT_AGENT_RECEIPT]:
            raise GlobalInstallError("Update journal changed default-agent ownership history.", 4)
        receipt = new_value[global_readonly._DEFAULT_AGENT_RECEIPT]
        expected_inventory = set(_inventory_for_receipt(
            candidate.expected, "opencode.jsonc" in new_entries,
        ))
        if set(new_entries) != expected_inventory:
            raise GlobalInstallError("Update journal inventory differs from the staged source.", 4)
        comparison = _version_compare(candidate.version, old_value["installed_version"])
        if comparison == 1:
            changed_managed = {
                path for path in set(old_entries) | set(new_entries)
                if old_entries.get(path) != new_entries.get(path)
            }
        elif (comparison == 0
              and old_value["installed_from_commit"] == candidate.commit
              and new_value["installed_from_commit"] == candidate.commit
              and old_entries == new_entries):
            changed_managed = set(old_entries)
            same_version_repair = True
        else:
            raise GlobalInstallError("Update journal is not a verified newer release or same-version repair.", 4)
    else:
        receipt = manifest_values["old"][global_readonly._DEFAULT_AGENT_RECEIPT]
        changed_managed = set(old_entries)
    actual_paths = set(file_map) - {_MANIFEST}
    extra_paths = actual_paths - changed_managed
    if record["operation"] == "install":
        allowed_extra = ({receipt["config_path"]} if "opencode.jsonc" not in new_entries else set())
        if actual_paths != changed_managed | allowed_extra:
            raise GlobalInstallError("Install journal write-set contradicts manifest ownership.", 4)
    elif record["operation"] == "update":
        if same_version_repair:
            if (not actual_paths or not actual_paths <= changed_managed
                    or any(
                        not file_map[path]["new_present"]
                        or file_map[path]["new_sha256"] != new_entries[path]
                        or file_map[path]["old_present"]
                        and file_map[path]["old_sha256"] == old_entries[path]
                        for path in actual_paths
                    )):
                raise GlobalInstallError("Same-version repair journal is outside its manifest receipt.", 4)
        else:
            unchanged_owned = {
                path for path in set(old_entries) & set(new_entries)
                if old_entries[path] == new_entries[path]
            }
            repair_paths = actual_paths - changed_managed
            if (not actual_paths <= changed_managed | unchanged_owned
                    or any(
                        file_map[path]["new_sha256"] != new_entries[path]
                        or file_map[path]["old_present"]
                        and file_map[path]["old_sha256"] == old_entries[path]
                        for path in repair_paths
                    )):
                raise GlobalInstallError("Update journal contains a non-manifest user-config write.", 4)
    else:
        allowed_extra = ({receipt["config_path"]} if receipt["config_path"] not in old_entries else set())
        if actual_paths not in (changed_managed, changed_managed | allowed_extra):
            raise GlobalInstallError("Uninstall journal write-set contradicts its receipt.", 4)

    def saved_bytes(relative: str, item: dict, *, old: bool) -> bytes | None:
        present = item["old_present"] if old else item["new_present"]
        if not present:
            return None
        artifact_name = item["backup"] if old else item["staged"]
        digest = item["old_sha256"] if old else item["new_sha256"]
        mode = item["old_mode"] if old else item["new_mode"]
        artifact = _read_artifact(
            root, f"{_SCRATCH}/{artifact_name}", digest, mode, required=False,
        )
        if artifact is not None:
            return artifact[0]
        if _target_state(root, relative, item) == ("old" if old else "new"):
            current, _ = _read(root, relative)
            return current
        return None

    for relative in extra_paths:
        item = file_map[relative]
        if record["operation"] == "update":
            continue
        if record["operation"] == "install":
            old_raw, new_raw = saved_bytes(relative, item, old=True), saved_bytes(relative, item, old=False)
            if new_raw is None and old_raw is not None:
                new_raw = _splice_default_agent(old_raw, json.dumps("kael"))
            if old_raw is None or new_raw is None or relative != receipt["config_path"]:
                raise GlobalInstallError("Install journal lacks its user-config old/new evidence.", 4)
            try:
                global_readonly._unowned_opencode_guard_bytes(old_raw)
                old_config, old_text, old_fields = _config_snapshot(old_raw)
                field = next((field for field in old_fields if field["key"] == "default_agent"), None)
                if field is not None and old_config.get("default_agent") == "kael":
                    raise ValueError("unowned kael value")
                previous_raw = old_text[field["value_start"]:field["value_end"]] if field else None
                if (bool(field) != receipt["previous_present"]
                        or previous_raw != receipt["previous_value_json"]
                        or _splice_default_agent(old_raw, json.dumps("kael")) != new_raw):
                    raise ValueError("receipt does not match the config splice")
                global_readonly._unowned_opencode_guard_bytes(new_raw)
            except (ValueError, GlobalInstallError, global_readonly.GlobalFault) as error:
                raise GlobalInstallError("Install journal config splice is not receipt-authorized.", 4) from error
        else:
            old_raw, new_raw = saved_bytes(relative, item, old=True), saved_bytes(relative, item, old=False)
            if new_raw is None and old_raw is not None:
                new_raw = _splice_default_agent(old_raw, _receipt_previous(receipt))
            if old_raw is None or new_raw is None or relative != receipt["config_path"]:
                raise GlobalInstallError("Uninstall journal lacks its receipt-authorized config restore.", 4)
            try:
                old_config, _, old_fields = _config_snapshot(old_raw)
                field = next((field for field in old_fields if field["key"] == "default_agent"), None)
                if field is None or old_config.get("default_agent") != "kael":
                    raise ValueError("installed default_agent is not present")
                restore = _receipt_previous(receipt)
                if _splice_default_agent(old_raw, restore) != new_raw:
                    raise ValueError("restored config bytes do not match the receipt")
                global_readonly._unowned_opencode_guard_bytes(new_raw)
            except (ValueError, GlobalInstallError, global_readonly.GlobalFault) as error:
                raise GlobalInstallError("Uninstall journal config restore is not receipt-authorized.", 4) from error
    for relative, item in file_map.items():
        if relative == _MANIFEST:
            continue
        if item["old_present"] and not (
            record["operation"] == "update" and relative in actual_paths
            and relative in old_entries
        ):
            old_hash = (manifest_maps["old"] or {}).get(relative)
            if old_hash is not None and old_hash != item["old_sha256"]:
                raise GlobalInstallError(f"Old manifest hash contradicts lifecycle backup: {relative}", 4)
        if item["new_present"]:
            new_hash = (manifest_maps["new"] or {}).get(relative)
            if new_hash is not None and new_hash != item["new_sha256"]:
                raise GlobalInstallError(f"New manifest hash contradicts lifecycle output: {relative}", 4)
            if relative in candidate.expected and new_hash is not None:
                target_state = _target_state(root, relative, item)
                staged = _read_artifact(
                    root, f"{_SCRATCH}/{item['staged']}", item["new_sha256"],
                    item["new_mode"], required=False,
                )
                current, _ = _read(root, relative)
                output = staged[0] if staged is not None else current
                if output is not None and output != candidate.expected[relative]:
                    raise GlobalInstallError(
                        f"Staged output differs from the renderer; preserve lifecycle evidence: {relative}", 4,
                    )
                if output is None and target_state == "new":
                    raise GlobalInstallError(f"Lifecycle output evidence is unavailable: {relative}", 4)
    for label, entries in manifest_maps.items():
        if entries is None:
            continue
        for relative, expected_hash in entries.items():
            if relative in file_map:
                continue
            raw, _ = _read(root, relative)
            if raw is None or _digest(raw) != expected_hash:
                raise GlobalInstallError(f"Unchanged manifest-owned resource drifted during recovery: {relative}", 4)
            if label == "new" and raw != candidate.expected.get(relative):
                raise GlobalInstallError(f"Unchanged resource differs from the staged source: {relative}", 4)

    artifacts: dict[str, tuple[bytes, os.stat_result] | None] = {}
    for relative, item in file_map.items():
        for field, present, digest, mode in (
            ("backup", item["old_present"], item["old_sha256"], item["old_mode"]),
            ("staged", item["new_present"], item["new_sha256"], item["new_mode"]),
        ):
            artifact_relative = f"{_SCRATCH}/{item[field]}" if present else None
            artifact = (_read_artifact(root, artifact_relative, digest, mode, required=False)
                        if artifact_relative is not None else None)
            artifacts[artifact_relative] = artifact if artifact_relative is not None else None
    temporary_raw, temporary_meta = _read(root, f"{_SCRATCH}/.record.json.tmp")
    if temporary_raw is not None:
        try:
            temp_record = json.loads(temporary_raw.decode("utf-8"), object_pairs_hook=source_edit._json_object_no_duplicates)
        except (UnicodeError, ValueError) as error:
            raise GlobalInstallError("Temporary lifecycle record is invalid.", 4) from error
        expected_state = {"PREPARING": "PREPARED", "PREPARED": "COMMITTED"}.get(record["state"])
        current = dict(record)
        current.pop("state")
        temp_state = temp_record.pop("state", None) if isinstance(temp_record, dict) else None
        if (temporary_raw != _canonical({**current, "state": temp_state})
                or temp_record != current or temp_state != expected_state or temporary_meta is None):
            raise GlobalInstallError("Temporary lifecycle record is foreign or contradictory.", 4)
        artifacts[f"{_SCRATCH}/.record.json.tmp"] = (temporary_raw, temporary_meta)
    return file_map, artifacts


def _target_state(root: Path, relative: str, entry: dict) -> str:
    current, metadata = _read(root, relative)
    if current is None:
        return "old" if not entry["old_present"] else "new" if not entry["new_present"] else "foreign"
    digest = _digest(current)
    mode = stat.S_IMODE(metadata.st_mode) if metadata is not None else None
    if entry["old_present"] and digest == entry["old_sha256"] and mode == entry["old_mode"]:
        return "old"
    if entry["new_present"] and digest == entry["new_sha256"] and mode == entry["new_mode"]:
        return "new"
    return "foreign"


def _cleanup(root: Path, lock, identity, root_identity: tuple[int, int],
             record: dict, record_raw: bytes, record_meta: os.stat_result,
             file_map: dict[str, dict], artifacts):
    for relative, value in artifacts.items():
        if value is None:
            continue
        raw, metadata = value
        _safe_remove(root, relative, raw, stat.S_IMODE(metadata.st_mode), lock, identity,
                     root_identity)
    for directory in ("staged", "backups"):
        path = root / _SCRATCH / directory
        _verify_root(root, root_identity)
        source_edit._lock_identity(lock, identity)
        try:
            os.rmdir(path)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise GlobalInstallError(f"Cannot remove lifecycle evidence directory {directory}: {error}", 4) from error
    current, metadata = _read(root, f"{_SCRATCH}/{_RECORD}")
    if (current != record_raw or metadata is None or
            (metadata.st_dev, metadata.st_ino) != (record_meta.st_dev, record_meta.st_ino)):
        raise GlobalInstallError("Lifecycle record changed during cleanup.", 4)
    _safe_remove(root, f"{_SCRATCH}/{_RECORD}", record_raw, stat.S_IMODE(record_meta.st_mode),
                 lock, identity, root_identity)
    scratch_meta = os.lstat(root / _SCRATCH)
    if (os.listdir(root / _SCRATCH) or
            (scratch_meta.st_dev, scratch_meta.st_ino) != (
                record["scratch_identity"]["st_dev"], record["scratch_identity"]["st_ino"]
            )):
        raise GlobalInstallError("Lifecycle scratch changed during final cleanup.", 4)
    _verify_root(root, root_identity)
    source_edit._lock_identity(lock, identity)
    os.rmdir(root / _SCRATCH)
    source_edit._sync_directory(root)


def _rollback(root: Path, lock, identity, root_identity: tuple[int, int],
              file_map: dict[str, dict], *, guard_acl: bool = False) -> None:
    for relative, entry in reversed(list(file_map.items())):
        state = _target_state(root, relative, entry)
        if state == "foreign":
            raise GlobalInstallError(f"Lifecycle target has foreign bytes; preserve it: {relative}", 4)
        if state == "old":
            continue
        if entry["old_present"]:
            backup_relative = f"{_SCRATCH}/{entry['backup']}"
            backup = _read_artifact(root, backup_relative, entry["old_sha256"], entry["old_mode"], required=True)
            if backup is None:
                raise GlobalInstallError(f"Missing rollback evidence for {relative}", 4)
            _verify_root(root, root_identity)
            if guard_acl:
                _require_default_acl_for_missing_parents(
                    root, relative, root_identity=root_identity, code=4,
                )
            _ensure_parent(root, relative, lock, identity)
            source_edit._lock_identity(lock, identity)
            _verify_root(root, root_identity)
            if guard_acl:
                current, metadata = _read(root, relative)
                if metadata is not None:
                    _require_no_posix_acl(
                        root / relative, "access",
                        expected_identity=(metadata.st_dev, metadata.st_ino), code=4,
                    )
                _require_no_posix_acl(root / backup_relative, "access", code=4)
            try:
                os.replace(root / backup_relative, root / relative)
            except OSError as error:
                raise GlobalInstallError(f"Cannot restore lifecycle target {relative}: {error}", 4) from error
            if guard_acl:
                restored, restored_metadata = _read(root, relative)
                if restored is None or restored_metadata is None:
                    raise GlobalInstallError(
                        f"Cannot verify ACL state of restored global resource {relative}", 4,
                    )
                _require_no_posix_acl(
                    root / relative, "access",
                    expected_identity=(restored_metadata.st_dev, restored_metadata.st_ino), code=4,
                )
        else:
            raw, metadata = _read(root, relative)
            if raw is None or metadata is None or _digest(raw) != entry["new_sha256"]:
                raise GlobalInstallError(f"Lifecycle target changed before rollback: {relative}", 4)
            _verify_root(root, root_identity)
            source_edit._lock_identity(lock, identity)
            if guard_acl:
                _require_no_posix_acl(
                    root / relative, "access",
                    expected_identity=(metadata.st_dev, metadata.st_ino), code=4,
                )
            try:
                os.unlink(root / relative)
            except OSError as error:
                raise GlobalInstallError(f"Cannot remove newly created lifecycle target {relative}: {error}", 4) from error
        source_edit._sync_directory((root / relative).parent)
        if _target_state(root, relative, entry) != "old":
            raise GlobalInstallError(f"Lifecycle rollback failed verification: {relative}", 4)


def _recover_locked(root: Path, candidate: _Candidate, lock, context,
                    root_identity: tuple[int, int], *, guard_acl: bool = False) -> str:
    if context is None:
        return "no_changes"
    record, record_raw, record_meta, scratch_meta, top = context
    _verify_root(root, root_identity)
    identity = source_edit._lock_identity(lock)
    file_map, artifacts = _validate_record(root, candidate, lock, record, scratch_meta, top)
    states = {relative: _target_state(root, relative, entry) for relative, entry in file_map.items()}
    if "foreign" in states.values():
        raise GlobalInstallError("Lifecycle target has foreign bytes; preserve the journal and target files.", 4)
    if record["state"] == "PREPARING":
        if any(state != "old" for state in states.values()):
            raise GlobalInstallError("PREPARING lifecycle journal unexpectedly changed targets.", 4)
        _cleanup(root, lock, identity, root_identity, record, record_raw, record_meta,
                 file_map, artifacts)
        return "discarded_incomplete_prepare"
    if record["state"] == "COMMITTED":
        if any(state != "new" for state in states.values()):
            raise GlobalInstallError("COMMITTED lifecycle journal has an incomplete target set.", 4)
        _cleanup(root, lock, identity, root_identity, record, record_raw, record_meta,
                 file_map, artifacts)
        return "committed_cleanup"
    _rollback(root, lock, identity, root_identity, file_map, guard_acl=guard_acl)
    if any(_target_state(root, relative, entry) != "old" for relative, entry in file_map.items()):
        raise GlobalInstallError("Lifecycle rollback left a non-old target state.", 4)
    context = _record_context(root, lock)
    if context is None:
        raise GlobalInstallError("Lifecycle journal disappeared after rollback.", 4)
    file_map, artifacts = _validate_record(root, candidate, lock, context[0], context[3], context[4])
    _cleanup(root, lock, identity, root_identity, context[0], context[1], context[2],
             file_map, artifacts)
    return "rolled_back"


def _commit(root: Path, root_identity: tuple[int, int], candidate: _Candidate, operation: str,
            changes: tuple[_Change, ...], lock=None, *, force: bool = False) -> str:
    if not changes and lock is None:
        raise GlobalInstallError("A lifecycle no-op requires the existing stable global writer lock.")
    if changes and changes[-1].path != _MANIFEST:
        raise GlobalInstallError("Lifecycle write-set must be manifest-last.")
    owns_lock = lock is None
    _verify_root(root, root_identity)
    if owns_lock:
        try:
            lock = source_edit._acquire_lock(root, create=True)
        except source_edit.LockError as error:
            raise GlobalInstallError(f"Cannot acquire the shared global writer lock: {error}") from error
    try:
        identity = source_edit._lock_identity(lock)
        _verify_root(root, root_identity)
        if config_apply_transaction.pending(root):
            raise GlobalInstallError("A global apply, lifecycle, or source-edit journal is pending; recover it first.")
        # Rebuild the candidate plan after acquiring the shared lock.
        latest = (_build_uninstall(root, candidate) if operation == "uninstall"
                  else _build_install(
                      root, candidate, update=operation == "update", force=force,
                  ))
        if [(item.path, item.old, item.new, item.old_mode, item.new_mode) for item in latest] != [
            (item.path, item.old, item.new, item.old_mode, item.new_mode) for item in changes
        ]:
            raise GlobalInstallError("Global installation changed before locked revalidation.")
        if not changes:
            return "no_changes"
        if force:
            _force_acl_preflight(root, root_identity, changes)
        for item in changes:
            _verify_root(root, root_identity)
            current, metadata = _read(root, item.path)
            if current != item.old or (
                current is not None and (metadata is None or stat.S_IMODE(metadata.st_mode) != item.old_mode)
            ):
                raise GlobalInstallError(f"Global target changed before lifecycle preparation: {item.path}")
        record = _record_for(root, candidate, operation, changes, identity)
        scratch = root / _SCRATCH
        _verify_root(root, root_identity)
        try:
            source_edit._make_directory(scratch, root, lock, identity)
        except source_edit.BatchError as error:
            raise GlobalInstallError(f"Cannot create lifecycle journal: {error}", 4) from error
        _verify_root(root, root_identity)
        scratch_meta = os.lstat(scratch)
        record["scratch_identity"] = {"st_dev": scratch_meta.st_dev, "st_ino": scratch_meta.st_ino}
        source_edit._sync_directory(root)
        _verify_root(root, root_identity)
        record, record_raw, record_meta = _persist_record(
            root, scratch, record, lock, identity, force=force,
        )
        try:
            _verify_root(root, root_identity)
            if force:
                _require_no_posix_acl(scratch, "default", code=4)
            source_edit._make_directory(scratch / "backups", root, lock, identity)
            if force:
                _require_no_posix_acl(scratch / "backups", "access", code=4)
                _require_no_posix_acl(scratch / "backups", "default", code=4)
            _verify_root(root, root_identity)
            if force:
                _require_no_posix_acl(scratch, "default", code=4)
            source_edit._make_directory(scratch / "staged", root, lock, identity)
            if force:
                _require_no_posix_acl(scratch / "staged", "access", code=4)
                _require_no_posix_acl(scratch / "staged", "default", code=4)
            for index, item in enumerate(changes):
                if item.old is not None:
                    relative = f"{_SCRATCH}/backups/file-{index:04d}.old"
                    _verify_root(root, root_identity)
                    if force:
                        _require_no_posix_acl(scratch / "backups", "default", code=4)
                    backup_identity = source_edit._write_private_file(
                        root / relative, root, relative, item.old, item.old_mode or 0o600, lock, identity,
                    )
                    if force:
                        _require_no_posix_acl(
                            root / relative, "access",
                            expected_identity=backup_identity, code=4,
                        )
                if item.new is not None:
                    relative = f"{_SCRATCH}/staged/file-{index:04d}.new"
                    _verify_root(root, root_identity)
                    if force:
                        _require_no_posix_acl(scratch / "staged", "default", code=4)
                    staged_identity = source_edit._write_private_file(
                        root / relative, root, relative, item.new, item.new_mode or 0o600, lock, identity,
                    )
                    if force:
                        _require_no_posix_acl(
                            root / relative, "access",
                            expected_identity=staged_identity, code=4,
                        )
            _verify_root(root, root_identity)
            record, record_raw, record_meta = _persist_record(
                root, scratch, {**record, "state": "PREPARED"}, lock, identity,
                previous=(record, record_raw, record_meta), force=force,
            )
            context = _record_context(root, lock)
            file_map, _ = _validate_record(root, candidate, lock, context[0], context[3], context[4])
            if force:
                _force_acl_preflight(root, root_identity, changes, code=4)
                for index, item in enumerate(changes):
                    if item.old is not None:
                        _require_no_posix_acl(
                            root / _SCRATCH / "backups" / f"file-{index:04d}.old",
                            "access", code=4,
                        )
                    if item.new is not None:
                        _require_no_posix_acl(
                            root / _SCRATCH / "staged" / f"file-{index:04d}.new",
                            "access", code=4,
                        )
            for index, item in enumerate(changes):
                _verify_root(root, root_identity)
                if force:
                    _require_default_acl_for_missing_parents(
                        root, item.path, root_identity=root_identity, code=4,
                    )
                _ensure_parent(root, item.path, lock, identity)
                current, metadata = _read(root, item.path)
                if current != item.old or (
                    current is not None and (metadata is None or stat.S_IMODE(metadata.st_mode) != item.old_mode)
                ):
                    raise GlobalInstallError(f"Global target changed before replacement: {item.path}", 4)
                if force:
                    if metadata is not None:
                        _require_no_posix_acl(
                            root / item.path, "access",
                            expected_identity=(metadata.st_dev, metadata.st_ino), code=4,
                        )
                    if item.new is not None:
                        _require_no_posix_acl(
                            root / _SCRATCH / "staged" / f"file-{index:04d}.new",
                            "access", code=4,
                        )
                _verify_root(root, root_identity)
                source_edit._lock_identity(lock, identity)
                if item.new is None:
                    try:
                        os.unlink(root / item.path)
                    except OSError as error:
                        raise GlobalInstallError(f"Cannot remove global resource {item.path}: {error}", 4) from error
                else:
                    staged = root / _SCRATCH / "staged" / f"file-{index:04d}.new"
                    try:
                        if item.old is None:
                            os.link(staged, root / item.path)
                            os.unlink(staged)
                        else:
                            os.replace(staged, root / item.path)
                    except OSError as error:
                        raise GlobalInstallError(f"Cannot publish global resource {item.path}: {error}", 4) from error
                _verify_root(root, root_identity)
                source_edit._sync_directory((root / item.path).parent)
                if _target_state(root, item.path, file_map[item.path]) != "new":
                    raise GlobalInstallError(f"Published global resource failed verification: {item.path}", 4)
                if force and item.new is not None:
                    _, published_metadata = _read(root, item.path)
                    if published_metadata is None:
                        raise GlobalInstallError(
                            f"Published global resource identity is unavailable: {item.path}", 4,
                        )
                    _require_no_posix_acl(
                        root / item.path, "access",
                        expected_identity=(published_metadata.st_dev, published_metadata.st_ino),
                        code=4,
                    )
            _verify_root(root, root_identity)
            record, record_raw, record_meta = _persist_record(
                root, scratch, {**record, "state": "COMMITTED"}, lock, identity,
                previous=(record, record_raw, record_meta), force=force,
            )
            context = _record_context(root, lock)
            file_map, artifacts = _validate_record(root, candidate, lock, context[0], context[3], context[4])
            _cleanup(root, lock, identity, root_identity, record, record_raw, record_meta,
                     file_map, artifacts)
            return "committed"
        except Exception as error:
            try:
                context = _record_context(root, lock)
                if context is None:
                    raise GlobalInstallError("Lifecycle journal disappeared during execution.", 4)
                state = context[0]["state"]
                if state == "COMMITTED":
                    recovered = _recover_locked(
                        root, candidate, lock, context, root_identity, guard_acl=force,
                    )
                    if recovered == "committed_cleanup":
                        return "committed"
                recovered = _recover_locked(
                    root, candidate, lock, context, root_identity, guard_acl=force,
                )
                if recovered in ("discarded_incomplete_prepare", "rolled_back"):
                    raise GlobalInstallError(f"Lifecycle failed; rollback was confirmed: {error}", 1) from error
            except GlobalInstallError as recovery_error:
                if "rollback was confirmed" in str(recovery_error):
                    raise
                raise GlobalInstallError(
                    f"Lifecycle failed and recovery is unconfirmed: {error}; {recovery_error}", 4,
                ) from error
            raise GlobalInstallError(f"Lifecycle failed with unconfirmed state: {error}", 4) from error
    finally:
        if owns_lock:
            try:
                source_edit._release_lock(lock)
            except source_edit.LockError as error:
                raise GlobalInstallError(f"Global writer lock identity became unconfirmed: {error}", 4) from error


def _operate(source: Path, version: str, commit: str, operation: str, *,
             force: bool = False) -> LifecycleOutcome:
    candidate = _candidate(source, version, commit)
    if version == "v0.10.0":
        raise GlobalInstallError(
            f"Staged global source version '{version}' is historically unsupported; use the current source.",
        )
    root, root_identity = _resolve_root(create=operation == "install")
    _check_roots(candidate.source, root)
    lock = _existing_lock(root, root_identity)
    try:
        if lock is not None:
            _verify_root(root, root_identity)
            if config_apply_transaction.pending(root):
                raise GlobalInstallError(
                    "A global lifecycle/apply or source-edit journal is pending; recover it first."
                )
        if lock is None:
            if config_apply_transaction.pending(root):
                raise GlobalInstallError(
                    "A pending global transaction has no stable writer lock; preserve its evidence for explicit recovery.",
                    4,
                )
            manifest_raw, _ = _read(root, _MANIFEST)
            if manifest_raw is not None:
                lock = _existing_lock(root, root_identity)
                if lock is None:
                    raise GlobalInstallError(
                        "An installed global manifest has no stable writer lock; refusing an unlocked lifecycle observation.",
                        4,
                    )
                _verify_root(root, root_identity)
                if config_apply_transaction.pending(root):
                    raise GlobalInstallError(
                        "A global lifecycle/apply or source-edit journal is pending; recover it first."
                    )

        if operation == "uninstall":
            changes = _build_uninstall(root, candidate)
        else:
            changes = _build_install(
                root, candidate, update=operation == "update", force=force,
            )

        if lock is not None:
            _verify_root(root, root_identity)
            if config_apply_transaction.pending(root):
                raise GlobalInstallError("A global lifecycle/apply or source-edit journal is pending; recover it first.")
            result = _commit(
                root, root_identity, candidate, operation, changes, lock=lock, force=force,
            )
        elif changes:
            result = _commit(
                root, root_identity, candidate, operation, changes, force=force,
            )
        else:
            # An absent uninstall is the only legitimate no-op without an installed lock.
            lock = _existing_lock(root, root_identity)
            if lock is None:
                if config_apply_transaction.pending(root):
                    raise GlobalInstallError(
                        "A pending global transaction has no stable writer lock; preserve its evidence for explicit recovery.",
                        4,
                    )
                manifest_raw, _ = _read(root, _MANIFEST)
                if manifest_raw is not None or operation != "uninstall":
                    raise GlobalInstallError(
                        "A lifecycle no-op requires the existing stable global writer lock; refusing to create one.",
                        4,
                    )
                result = "no_changes"
            else:
                result = _commit(
                    root, root_identity, candidate, operation, changes, lock=lock, force=force,
                )
        return LifecycleOutcome(operation, result, str(root), candidate.version,
                                tuple(item.path for item in changes))
    finally:
        if lock is not None:
            try:
                source_edit._release_lock(lock)
            except source_edit.LockError as error:
                raise GlobalInstallError(f"Global writer lock identity became unconfirmed: {error}", 4) from error


def _preflight_force_update(source: Path, *, version: str, commit: str) -> None:
    """Inspect global targets before a coordinated CLI force mutation."""
    candidate = _candidate(source, version, commit)
    root, root_identity = _resolve_root(create=False)
    _check_roots(candidate.source, root)
    lock = _existing_lock(root, root_identity)
    if lock is None:
        raise GlobalInstallError("Force preflight requires the existing stable global writer lock.", 4)
    try:
        _verify_root(root, root_identity)
        if config_apply_transaction.pending(root):
            raise GlobalInstallError("A pending global transaction blocks force repair.")
        changes = _build_install(root, candidate, update=True, force=True)
        _force_acl_preflight(root, root_identity, changes)
    finally:
        try:
            source_edit._release_lock(lock)
        except source_edit.LockError as error:
            raise GlobalInstallError(f"Global writer lock identity is unconfirmed: {error}", 4) from error


def install(source: Path, *, version: str = "local", commit: str = "unknown") -> LifecycleOutcome:
    """Install one staged source, refusing collisions or an unrequested transition."""
    return _operate(source, version, commit, "install")


def update(source: Path, *, version: str = "local", commit: str = "unknown",
           force: bool = False) -> LifecycleOutcome:
    """Update a newer source, or repair only receipt-owned files when explicitly forced."""
    return _operate(source, version, commit, "update", force=force)


def uninstall(source: Path, *, version: str = "local", commit: str = "unknown") -> LifecycleOutcome:
    """Remove unchanged manifest-owned resources and restore only the receipted field."""
    return _operate(source, version, commit, "uninstall")


def verify(source: Path, *, version: str = "local", commit: str = "unknown") -> LifecycleOutcome:
    """Verify source bytes, installed version, receipts, and pending state without writes."""
    candidate = _candidate(source, version, commit)
    root, root_identity = _resolve_root(create=False)
    _check_roots(candidate.source, root)
    lock = _existing_lock(root, root_identity)
    if lock is None:
        if config_apply_transaction.pending(root):
            raise GlobalInstallError(
                "A pending global transaction has no stable writer lock; preserve its evidence for explicit recovery.",
                4,
            )
        raise GlobalInstallError("Global verification requires the existing stable writer lock.", 4)
    try:
        _verify_root(root, root_identity)
        if config_apply_transaction.pending(root):
            raise GlobalInstallError("A global lifecycle/apply or source-edit journal is pending.", 3)
        manifest, entries, _, _ = _manifest(root, candidate)
        if manifest is None:
            raise GlobalInstallError("No Olympus global ownership manifest exists.", 3)
        if manifest["installed_version"] != version:
            raise GlobalInstallError(
                f"Installed global version is {manifest['installed_version']}; requested {version}.", 3,
            )
        current = _validate_owned_files(root, entries)
        if any(raw != candidate.expected.get(path) for path, (raw, _) in current.items()):
            raise GlobalInstallError("Installed managed resources differ from this staged source.", 1)
        try:
            global_readonly._default_agent_status(root, manifest)
            if "opencode.jsonc" not in entries:
                global_readonly._unowned_opencode_guard(root)
        except global_readonly.GlobalFault as error:
            raise GlobalInstallError(str(error), error.code) from error
        return LifecycleOutcome("verify", "verified", str(root), version,
                                detail="Python content, version, and receipt checks passed.")
    finally:
        try:
            source_edit._release_lock(lock)
        except source_edit.LockError as error:
            raise GlobalInstallError(f"Global verification lock identity became unconfirmed: {error}", 4) from error


def recover(source: Path) -> LifecycleOutcome:
    """Rollback one prepared lifecycle journal or clean a committed one."""
    root, root_identity = _resolve_root(create=False)
    lock = _existing_lock(root, root_identity)
    if lock is None:
        raise GlobalInstallError("Lifecycle recovery requires the existing stable target lock.")
    try:
        _verify_root(root, root_identity)
        try:
            os.lstat(root / source_edit._SCRATCH_NAME)
        except FileNotFoundError:
            pass
        else:
            raise GlobalInstallError("A source-edit journal is pending; recover it with its owning operation first.")
        context = _record_context(root, lock)
        if context is None:
            return LifecycleOutcome("recover", "no_changes", str(root))
        record = context[0]
        if not isinstance(record, dict):
            raise GlobalInstallError("Lifecycle record is invalid.", 4)
        candidate = _candidate(
            source, record.get("source_version"), record.get("source_commit"),
        )
        _check_roots(candidate.source, root)
        result = _recover_locked(root, candidate, lock, context, root_identity)
        return LifecycleOutcome("recover", result, str(root), candidate.version)
    finally:
        try:
            source_edit._release_lock(lock)
        except source_edit.LockError as error:
            raise GlobalInstallError(f"Global recovery lock identity became unconfirmed: {error}", 4) from error
