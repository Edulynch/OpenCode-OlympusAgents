"""Per-user model overrides consumed by the managed global OpenCode agents."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

from . import models_catalog


class UserConfigError(ValueError):
    """The per-user override file or managed OpenCode target is invalid."""


_MANIFEST = "olympus/orchestrator-install.json"
_PROJECT_CONFIG = ".opencode/olympus-config.json"
_HASH = re.compile(r"[0-9a-fA-F]{64}\Z")
_AGENT_MODEL = re.compile(r'(?m)^model:\s*(?:"([^"]+)"|([^\r\n]+))\s*$')
_DEFAULT_MAX_CHILDREN = 4
_PREFERENCE_LOCK_NAME = ".olympus-user-config.lock"
_CONFIG_LIMIT = 2_000_000
_UNSET = object()


class AtomicWriteUnconfirmed(OSError):
    """Replacement occurred, but its post-publication state was not confirmed."""


def config_path(scope: str = "global", target: Path | None = None) -> Path:
    if scope == "project":
        if target is None or not target.is_absolute():
            raise UserConfigError("Project configuration requires an absolute managed --target.")
        return target / _PROJECT_CONFIG
    if scope != "global":
        raise UserConfigError(f"Unsupported configuration scope: {scope}")
    explicit = os.environ.get("OLYMPUS_CONFIG_FILE")
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            raise UserConfigError("OLYMPUS_CONFIG_FILE must be an absolute path.")
        return path
    config_home = os.environ.get("OLYMPUS_CONFIG_HOME")
    if config_home:
        root = Path(config_home)
    elif os.name == "nt" and os.environ.get("APPDATA"):
        root = Path(os.environ["APPDATA"]) / "Olympus"
    elif os.environ.get("XDG_CONFIG_HOME"):
        root = Path(os.environ["XDG_CONFIG_HOME"]) / "olympus"
    else:
        root = Path.home() / ".config" / "olympus"
    if not root.is_absolute():
        raise UserConfigError("The Olympus user configuration directory must be absolute.")
    return root / "config.json"


def _managed_project(source: Path, cwd: Path | None = None, *,
                     for_diagnostics: bool = False) -> Path | None:
    from . import config_apply, install_manifest, install_routing

    directory = (cwd or Path.cwd()).resolve()
    if not directory.is_dir():
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            timeout=10, env=config_apply._without_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode:
        return None
    try:
        requested = Path(completed.stdout.strip()).resolve(strict=True)
        if requested == source.resolve() or not any(
                install_manifest.manifest_present(path) for path in install_manifest.manifest_paths(requested)):
            return None
        target = install_routing._validate_project_target(source, requested)
        record, _, blockers = config_apply._manifest_record(target)
    except (OSError, RuntimeError, config_apply.PreviewFault) as error:
        raise UserConfigError(f"Cannot safely resolve the current managed project: {error}") from error
    if blockers:
        if all(item.get("code") == "manifest_missing" for item in blockers):
            return None
        if for_diagnostics:
            return target
        raise UserConfigError("The current project's Olympus installation manifest is invalid; no configuration was changed.")
    if record is None or "opencode" not in record.installed_harnesses:
        return None
    return target


def select_scope(source: Path, scope: str | None = None, target: Path | None = None) -> tuple[str, Path | None]:
    """Resolve explicit scope or the managed OpenCode project at the current directory."""
    if scope == "global":
        if target is not None:
            raise UserConfigError("--target is available only with project scope.")
        return "global", None
    if target is not None and scope not in (None, "project"):
        raise UserConfigError("--target is available only with project scope.")
    selected = target
    if selected is None:
        selected = _managed_project(source)
    if selected is None:
        if scope == "project":
            raise UserConfigError("Project scope requires a managed OpenCode project; pass --target <absolute-worktree-root>.")
        return "global", None

    from . import config_apply, install_routing

    try:
        resolved = install_routing._validate_project_target(source, selected)
        record, _, blockers = config_apply._manifest_record(resolved)
    except (OSError, RuntimeError, config_apply.PreviewFault) as error:
        raise UserConfigError(f"Cannot safely resolve the selected project: {error}") from error
    if blockers or record is None or "opencode" not in record.installed_harnesses:
        raise UserConfigError("The selected target is not a managed OpenCode project.")
    return "project", resolved


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate key: {key}")
        result[key] = value
    return result


def _canonical_rows(source: Path) -> list[dict]:
    from .cli import load_renderer, model_assignments

    try:
        return model_assignments(load_renderer(source), source)["roles"]
    except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
        raise UserConfigError(f"Canonical Olympus model configuration is invalid: {error}") from error


def read_config(source: Path, scope: str = "global", target: Path | None = None) -> dict:
    path = config_path(scope, target)
    try:
        if scope == "project":
            from . import config_apply

            raw, issue = config_apply._read_target_file(target, _PROJECT_CONFIG, max_bytes=2_000_000)
            if issue:
                raise UserConfigError(f"Unsafe project Olympus configuration: {issue}")
            if raw is None:
                return {"schema_version": 1, "overrides": {}}
            text = raw.decode("utf-8")
        else:
            raw, _ = _read_atomic_target(path)
            if raw is None:
                return {"schema_version": 1, "overrides": {}}
            text = raw.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_unique_object)
    except UserConfigError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise UserConfigError(f"Olympus configuration is not valid JSON: {path}: {error}") from error
    return _validate_config_value(source, scope, path, value)


def _validate_config_value(source: Path, scope: str, path: Path, value: dict) -> dict:
    rows = _canonical_rows(source)
    roles = {row["role"] for row in rows}
    allowed = {"schema_version", "overrides"}
    if scope == "global":
        allowed.add("orchestration")
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1 or not isinstance(value.get("overrides"), dict)
            or set(value) - allowed or not {"schema_version", "overrides"}.issubset(value)):
        raise UserConfigError(f"Olympus user configuration must contain schema_version 1 and an overrides object: {path}")
    if scope == "global" and "orchestration" in value:
        orchestration = value["orchestration"]
        if (not isinstance(orchestration, dict) or set(orchestration) != {"max_children"}
                or type(orchestration["max_children"]) is not int
                or not 1 <= orchestration["max_children"] <= 8):
            raise UserConfigError(
                f"Olympus global orchestration must contain only integer max_children from 1 to 8: {path}"
            )
    for role, override in value["overrides"].items():
        if role not in roles or not isinstance(override, dict) or not override or set(override) - {"model", "effort"}:
            raise UserConfigError(f"Invalid Olympus override for role '{role}' in {path}.")
        if any(not isinstance(item, str) or not item for item in override.values()):
            raise UserConfigError(f"Override values for '{role}' must be non-empty strings in {path}.")
    return value


def max_children(source: Path) -> int:
    """Return the validated global Kael prompt ceiling, defaulting to Core's four."""
    orchestration = read_config(source, "global").get("orchestration", {})
    return orchestration.get("max_children", _DEFAULT_MAX_CHILDREN)


def effective_roles(source: Path, scope: str = "global", target: Path | None = None) -> list[dict]:
    rows = _canonical_rows(source)
    config = read_config(source, scope, target)
    path = str(config_path(scope, target).resolve())
    global_config = read_config(source, "global") if scope == "project" else {"overrides": {}}
    global_path = str(config_path().resolve())
    defaults = str((source / "olympus/core/models.toml").resolve())
    effective = []
    for row in rows:
        override = config["overrides"].get(row["role"], {})
        global_override = global_config["overrides"].get(row["role"], {})
        model = override.get("model", global_override.get("model", row["models"]["opencode"]))
        effort = override.get("effort", global_override.get("effort", row["effort"]))
        try:
            models_catalog.validate_assignment(model, effort, source)
        except models_catalog.CatalogError as error:
            raise UserConfigError(f"Invalid effective configuration for {row['role']}: {error}") from error
        effective.append({
            "role": row["role"], "identity": row["identity"], "model": model, "effort": effort,
            "model_source": path if "model" in override else global_path if "model" in global_override else defaults,
            "effort_source": path if "effort" in override else global_path if "effort" in global_override else defaults,
            "scope": scope,
        })
    return effective


def _replace_agent_model(content: bytes, model: str, effort: str, role: str) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeError as error:
        raise UserConfigError(f"Managed OpenCode agent {role} is not UTF-8 text.") from error
    matches = list(_AGENT_MODEL.finditer(text))
    if len(matches) != 1:
        raise UserConfigError(f"Managed OpenCode agent {role} must contain exactly one model field.")
    value = f'model: "{model}#{effort}"'
    updated = _AGENT_MODEL.sub(lambda _: value, text, count=1)
    return updated.encode("utf-8")


def _apply_config_to_expected(source: Path, expected: dict[str, bytes], config: dict) -> None:
    rows = {row["role"]: row for row in _canonical_rows(source)}
    for role, override in config["overrides"].items():
        if role not in rows:
            raise UserConfigError(f"Unknown Olympus role '{role}'.")
        model = override.get("model", rows[role]["models"]["opencode"])
        effort = override.get("effort", rows[role]["effort"])
        models_catalog.validate_assignment(model, effort, source)
        relative = f"agents/{role}.md"
        if relative not in expected:
            raise UserConfigError(f"The OpenCode renderer does not manage expected agent {role}.")
        expected[relative] = _replace_agent_model(expected[relative], model, effort, role)


def apply_to_expected(source: Path, expected: dict[str, bytes]) -> None:
    """Make read-only verification compare installed agents with user overrides."""
    _apply_config_to_expected(source, expected, read_config(source))


def _win_api():
    import ctypes
    from ctypes import wintypes

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    class FileInfo(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD), ("creation", FileTime), ("access", FileTime),
            ("write", FileTime), ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD), ("links", wintypes.DWORD), ("index_high", wintypes.DWORD),
            ("index_low", wintypes.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandle.argtypes = (wintypes.HANDLE, ctypes.POINTER(FileInfo))
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.SetFileInformationByHandle.argtypes = (
        wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD,
    )
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel.FlushFileBuffers.argtypes = (wintypes.HANDLE,)
    kernel.FlushFileBuffers.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    return ctypes, wintypes, kernel, FileInfo


def _win_handle_info(handle):
    ctypes, _, kernel, FileInfo = _win_api()
    info = FileInfo()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    identity = (info.volume, (info.index_high << 32) | info.index_low)
    size = (info.size_high << 32) | info.size_low
    return info, identity, size


def _win_open_directory(path: Path, *, create: bool = False):
    ctypes, wintypes, kernel, _ = _win_api()

    def check_path() -> os.stat_result:
        current = Path(path.anchor)
        for component in path.parts[len(current.parts):]:
            current /= component
            try:
                metadata = os.lstat(current)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(current)
                except FileExistsError:
                    pass
                metadata = os.lstat(current)
            if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
                    or getattr(metadata, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise OSError(f"Preference parent is linked or not a directory: {current}")
        return os.lstat(path)

    before = check_path()
    access = 0x0001 | 0x0020 | 0x0080
    if create:
        access |= 0x0002 | 0x0040
    handle = kernel.CreateFileW(
        str(path), access,
        0x00000001 | 0x00000002 | 0x00000004, None, 3,
        0x02000000 | 0x00200000, None,
    )
    if handle == wintypes.HANDLE(-1).value:
        code = ctypes.get_last_error()
        if code in (2, 3):
            raise FileNotFoundError(code, os.strerror(code), str(path))
        raise ctypes.WinError(code)
    try:
        info, identity, _ = _win_handle_info(handle)
        current = check_path()
        if (not info.attributes & 0x10 or info.attributes & 0x400
                or identity[1] != current.st_ino
                or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)):
            raise OSError(f"Preference parent identity changed or is unsafe: {path}")
        return handle, (current.st_dev, current.st_ino)
    except BaseException:
        kernel.CloseHandle(handle)
        raise


def _open_parent_directory(path: Path, *, create: bool = False):
    path = Path(os.path.abspath(os.fspath(path)))
    if not path.name or path == Path(path.anchor):
        raise OSError("User configuration path must name a file below the filesystem root")
    if os.name == "nt":
        return _win_open_directory(path.parent, create=create)
    if os.name != "posix" or not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise OSError("Safe preference directory handles are unavailable on this platform")

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path.anchor, flags)
    try:
        for component in path.parent.parts[len(Path(path.anchor).parts):]:
            try:
                before = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, dir_fd=descriptor)
                except FileExistsError:
                    pass
                before = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            if (not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode)
                    or getattr(before, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise OSError(f"Preference parent is linked or not a directory: {path.parent}")
            child = os.open(component, flags, dir_fd=descriptor)
            opened = os.fstat(child)
            placed = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            if ((opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                    or (placed.st_dev, placed.st_ino) != (before.st_dev, before.st_ino)):
                os.close(child)
                raise OSError(f"Preference parent identity changed while opening: {path.parent}")
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        return descriptor, (metadata.st_dev, metadata.st_ino)
    except BaseException:
        os.close(descriptor)
        raise


def _close_parent_directory(handle) -> None:
    if os.name == "nt":
        _, _, kernel, _ = _win_api()
        kernel.CloseHandle(handle)
    else:
        os.close(handle)


def _verify_parent_directory(path: Path, expected: tuple[int, int]) -> None:
    handle, identity = _open_parent_directory(path)
    try:
        if identity != expected:
            raise OSError("User configuration parent no longer identifies the authorized directory")
    finally:
        _close_parent_directory(handle)


def _check_regular(metadata: os.stat_result, path: Path) -> None:
    if (not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            or metadata.st_nlink != 1 or metadata.st_size > _CONFIG_LIMIT):
        raise OSError(f"User configuration is linked, oversized, or not a private regular file: {path}")


def _open_existing_file(path: Path, parent_handle, flags: int) -> int:
    if os.name != "nt":
        return os.open(path.name, flags, dir_fd=parent_handle)

    import msvcrt

    ctypes, wintypes, kernel, _ = _win_api()
    handle = kernel.CreateFileW(
        str(path), 0x80000000, 0x00000001 | 0x00000002 | 0x00000004, None, 3, 0x00200000, None,
    )
    if handle == wintypes.HANDLE(-1).value:
        code = ctypes.get_last_error()
        if code == 2:
            raise FileNotFoundError(code, os.strerror(code), str(path))
        raise ctypes.WinError(code)
    try:
        fd = msvcrt.open_osfhandle(handle, getattr(os, "O_BINARY", 0))
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    try:
        info, identity, _ = _win_handle_info(msvcrt.get_osfhandle(fd))
        opened = os.fstat(fd)
        if (info.attributes & 0x400 or identity[1] != opened.st_ino
                or info.links != opened.st_nlink):
            raise OSError(f"User configuration is a reparse point or changed identity: {path}")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_entry(path: Path, parent_handle, parent_identity: tuple[int, int]):
    _verify_parent_directory(path, parent_identity)
    try:
        before = (os.stat(path.name, dir_fd=parent_handle, follow_symlinks=False)
                  if os.name != "nt" else os.lstat(path))
    except FileNotFoundError:
        return None, None
    _check_regular(before, path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = _open_existing_file(path, parent_handle, flags)
    try:
        opened = os.fstat(descriptor)
        _check_regular(opened, path)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise OSError(f"User configuration changed identity while opening: {path}")
        chunks = []
        total = 0
        while True:
            block = os.read(descriptor, min(1024 * 1024, _CONFIG_LIMIT + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            if total > _CONFIG_LIMIT:
                raise OSError(f"User configuration exceeds the safety limit: {path}")
        after = os.fstat(descriptor)
        placed = (os.stat(path.name, dir_fd=parent_handle, follow_symlinks=False)
                  if os.name != "nt" else os.lstat(path))
        _verify_parent_directory(path, parent_identity)
        if ((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or (after.st_dev, after.st_ino) != (placed.st_dev, placed.st_ino)):
            raise OSError(f"User configuration changed while reading: {path}")
        return b"".join(chunks), after
    finally:
        os.close(descriptor)


def _read_atomic_target(path: Path, parent_identity: tuple[int, int] | None = None):
    path = Path(os.path.abspath(os.fspath(path)))
    try:
        parent_handle, identity = _open_parent_directory(path)
    except FileNotFoundError:
        return None, None
    try:
        if parent_identity is not None and identity != parent_identity:
            raise OSError("User configuration parent identity changed")
        return _read_entry(path, parent_handle, identity)
    finally:
        _close_parent_directory(parent_handle)


def _win_create_temporary(path: Path, parent_handle):
    import msvcrt

    ctypes, wintypes, kernel, _ = _win_api()
    initial = f".{path.name}-{secrets.token_hex(12)}.tmp"
    handle = kernel.CreateFileW(
        str(path.parent / initial), 0x80000000 | 0x40000000 | 0x00010000 | 0x00000100,
        0x00000001 | 0x00000002 | 0x00000004, None, 1, 0x00000100 | 0x00200000, None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDWR | getattr(os, "O_BINARY", 0))
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    try:
        name = f".{path.name}-{secrets.token_hex(12)}.tmp"
        _win_rename(fd, parent_handle, name, replace=False)
        metadata = os.fstat(fd)
        placed = os.lstat(path.parent / name)
        _check_regular(metadata, path)
        if (metadata.st_dev, metadata.st_ino) != (placed.st_dev, placed.st_ino):
            raise OSError("Bound temporary preference identity could not be verified")
        return fd, name
    except BaseException:
        try:
            _win_dispose(fd)
        except OSError:
            pass
        os.close(fd)
        raise


def _win_set_mode(descriptor: int, mode: int) -> None:
    import msvcrt

    ctypes, wintypes, kernel, _ = _win_api()

    class FileBasicInfo(ctypes.Structure):
        _fields_ = [
            ("creation_time", ctypes.c_longlong), ("last_access_time", ctypes.c_longlong),
            ("last_write_time", ctypes.c_longlong), ("change_time", ctypes.c_longlong),
            ("file_attributes", wintypes.DWORD),
        ]

    kernel.GetFileInformationByHandleEx.argtypes = (
        wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD,
    )
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    handle = msvcrt.get_osfhandle(descriptor)
    info = FileBasicInfo()
    if not kernel.GetFileInformationByHandleEx(
            handle, 0, ctypes.byref(info), ctypes.sizeof(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    info.file_attributes = (
        info.file_attributes & ~0x00000001 if mode & stat.S_IWRITE
        else info.file_attributes | 0x00000001
    )
    if not kernel.SetFileInformationByHandle(handle, 0, ctypes.byref(info), ctypes.sizeof(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    verified = FileBasicInfo()
    if not kernel.GetFileInformationByHandleEx(
            handle, 0, ctypes.byref(verified), ctypes.sizeof(verified)):
        raise ctypes.WinError(ctypes.get_last_error())
    if verified.file_attributes != info.file_attributes:
        raise OSError("Temporary user configuration attributes failed handle verification")


def _win_rename(descriptor: int, parent_handle, name: str, *, replace: bool) -> None:
    import msvcrt

    ctypes, wintypes, _, _ = _win_api()

    class RenameInfo(ctypes.Structure):
        _fields_ = [
            ("replace", wintypes.BOOLEAN), ("root", wintypes.HANDLE),
            ("length", wintypes.ULONG), ("name", wintypes.WCHAR * 1),
        ]

    class StatusUnion(ctypes.Union):
        _fields_ = [("status", ctypes.c_long), ("pointer", ctypes.c_void_p)]

    class IoStatusBlock(ctypes.Structure):
        _anonymous_ = ("value",)
        _fields_ = [("value", StatusUnion), ("information", ctypes.c_size_t)]

    encoded = name.encode("utf-16-le")
    offset = RenameInfo.name.offset
    buffer = ctypes.create_string_buffer(offset + len(encoded))
    info = ctypes.cast(buffer, ctypes.POINTER(RenameInfo)).contents
    info.replace = 1 if replace else 0
    info.root = parent_handle
    info.length = len(encoded)
    ctypes.memmove(ctypes.addressof(info) + offset, encoded, len(encoded))
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtSetInformationFile.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(IoStatusBlock), wintypes.LPVOID, wintypes.ULONG, wintypes.INT,
    )
    ntdll.NtSetInformationFile.restype = ctypes.c_long
    status_block = IoStatusBlock()
    status = ntdll.NtSetInformationFile(
        msvcrt.get_osfhandle(descriptor), ctypes.byref(status_block), buffer, len(buffer), 10,
    )
    if status < 0 or status_block.status < 0:
        raise OSError(
            f"Handle-relative user configuration rename failed "
            f"(NtSetInformationFile status 0x{status & 0xffffffff:08x}, "
            f"IoStatusBlock 0x{status_block.status & 0xffffffff:08x})"
        )
    if status != 0 or status_block.status != 0:
        raise OSError(
            f"Handle-relative user configuration rename was not synchronously confirmed "
            f"(NtSetInformationFile status 0x{status & 0xffffffff:08x}, "
            f"IoStatusBlock 0x{status_block.status & 0xffffffff:08x})"
        )


def _win_dispose(descriptor: int) -> None:
    import msvcrt

    ctypes, _, kernel, _ = _win_api()
    disposition = ctypes.c_ubyte(1)
    if not kernel.SetFileInformationByHandle(
            msvcrt.get_osfhandle(descriptor), 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
        raise ctypes.WinError(ctypes.get_last_error())


def _write_atomic(path: Path, content: bytes, *, mode: int | None = None,
                  expected_old=_UNSET, parent_identity: tuple[int, int] | None = None) -> None:
    """Replace one preference leaf; production callers hold its stable parent lock."""
    path = Path(os.path.abspath(os.fspath(path)))
    parent_handle, identity = _open_parent_directory(path, create=True)
    descriptor = -1
    temporary_name = None
    temporary_identity = None
    replaced = False
    try:
        if parent_identity is not None and identity != parent_identity:
            raise OSError("User configuration parent identity changed before replacement")
        old, old_metadata = _read_entry(path, parent_handle, identity)
        if expected_old is not _UNSET and old != expected_old:
            raise OSError("User configuration changed before its atomic replacement")

        if os.name == "nt":
            descriptor, temporary_name = _win_create_temporary(path, parent_handle)
            temporary_metadata = os.fstat(descriptor)
            temporary_identity = (temporary_metadata.st_dev, temporary_metadata.st_ino)
        else:
            for _ in range(10):
                temporary_name = f".{path.name}-{secrets.token_hex(12)}.tmp"
                try:
                    descriptor = os.open(
                        temporary_name,
                        os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
                        | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
                        0o600, dir_fd=parent_handle,
                    )
                    temporary_metadata = os.fstat(descriptor)
                    temporary_identity = (temporary_metadata.st_dev, temporary_metadata.st_ino)
                    break
                except FileExistsError:
                    continue
            if descriptor < 0:
                raise OSError("Cannot allocate a private temporary preference file")
        os.set_inheritable(descriptor, False)
        file_mode = 0o600 if mode is None and os.name != "nt" else (
            0o666 if mode is None else mode
        )
        if os.name == "nt":
            _win_set_mode(descriptor, file_mode)
        elif hasattr(os, "fchmod"):
            os.fchmod(descriptor, file_mode)
        else:
            os.chmod(path.parent / temporary_name, file_mode)
        view = memoryview(content)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("short write while preparing user configuration")
            written += count
        if os.name == "nt":
            import msvcrt

            ctypes, _, kernel, _ = _win_api()
            if not kernel.FlushFileBuffers(msvcrt.get_osfhandle(descriptor)):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        saved = bytearray()
        while block := os.read(descriptor, 1024 * 1024):
            saved.extend(block)
        temporary_metadata = os.fstat(descriptor)
        _check_regular(temporary_metadata, path)
        if (temporary_metadata.st_dev, temporary_metadata.st_ino) != temporary_identity:
            raise OSError("Temporary user configuration changed identity while being written")
        temporary_placed = (os.stat(temporary_name, dir_fd=parent_handle, follow_symlinks=False)
                            if os.name != "nt" else os.lstat(path.parent / temporary_name))
        if (bytes(saved) != content or (temporary_placed.st_dev, temporary_placed.st_ino) != temporary_identity
                or stat.S_IMODE(temporary_metadata.st_mode) != stat.S_IMODE(file_mode)):
            raise OSError("Temporary user configuration failed byte, mode, or identity verification")

        current, current_metadata = _read_entry(path, parent_handle, identity)
        if expected_old is not _UNSET and current != expected_old:
            raise OSError("User configuration changed immediately before its atomic replacement")
        if current != old or (
                current_metadata is not None and old_metadata is not None
                and (current_metadata.st_dev, current_metadata.st_ino)
                != (old_metadata.st_dev, old_metadata.st_ino)):
            raise OSError("User configuration destination changed before replacement")
        try:
            if os.name == "nt":
                _win_rename(descriptor, parent_handle, path.name, replace=True)
            else:
                os.replace(
                    temporary_name, path.name, src_dir_fd=parent_handle, dst_dir_fd=parent_handle,
                )
        except OSError:
            try:
                published, published_metadata = _read_entry(path, parent_handle, identity)
                replaced = (published is not None and published_metadata is not None
                            and (published_metadata.st_dev, published_metadata.st_ino) == temporary_identity)
            except OSError:
                replaced = False
            raise
        replaced = True
        if os.name == "nt":
            import msvcrt

            ctypes, _, kernel, _ = _win_api()
            if not kernel.FlushFileBuffers(msvcrt.get_osfhandle(descriptor)):
                raise ctypes.WinError(ctypes.get_last_error())
        elif os.name == "posix":
            os.fsync(parent_handle)
        _verify_parent_directory(path, identity)
        published, published_metadata = _read_entry(path, parent_handle, identity)
        if (published != content or published_metadata is None
                or stat.S_IMODE(published_metadata.st_mode) != stat.S_IMODE(file_mode)
                or (published_metadata.st_dev, published_metadata.st_ino) != temporary_identity):
            raise OSError("Published user configuration failed byte, mode, or identity verification")
    except OSError as error:
        if replaced:
            raise AtomicWriteUnconfirmed(
                f"User configuration replacement occurred but post-publication durability or identity "
                f"could not be confirmed; preserve any transaction recovery evidence: {error}"
            ) from error
        raise
    finally:
        if descriptor >= 0:
            if not replaced and temporary_name is not None and temporary_identity is not None:
                try:
                    if os.name == "nt":
                        _win_dispose(descriptor)
                    else:
                        placed = os.stat(temporary_name, dir_fd=parent_handle, follow_symlinks=False)
                        if (placed.st_dev, placed.st_ino) == temporary_identity:
                            os.unlink(temporary_name, dir_fd=parent_handle)
                except OSError:
                    pass
            os.close(descriptor)
        _close_parent_directory(parent_handle)


def _acquire_preference_lock(path: Path, *, create_parent: bool = True):
    from . import source_edit

    path = Path(os.path.abspath(os.fspath(path)))
    try:
        parent_handle, identity = _open_parent_directory(path, create=create_parent)
    except OSError as error:
        raise OSError(f"User configuration parent is unsafe: {error}") from error
    try:
        lock = source_edit._acquire_path_lock(path.parent / _PREFERENCE_LOCK_NAME, create=True)
        try:
            _verify_parent_directory(path, identity)
            if source_edit._lock_identity(lock) != lock.identity:
                raise source_edit.LockIdentityError("Shared preferences lock identity changed")
            return lock
        except BaseException:
            source_edit._release_lock(lock)
            raise
    finally:
        _close_parent_directory(parent_handle)


def _ensure_global_root(root: Path):
    from . import global_readonly

    try:
        if sys.platform.startswith("linux"):
            return global_readonly._ensure_linux_directory(root, create=True)
        root.mkdir(parents=True, exist_ok=True)
        global_readonly._root(root)
        return global_readonly._root(root.resolve(strict=True)), None
    except (global_readonly.GlobalFault, OSError, RuntimeError) as error:
        raise UserConfigError(
            f"Cannot safely create the global OpenCode root; no configuration was changed: {error}"
        ) from error


def _verify_global_root(global_readonly, root: Path, identity: tuple[int, int] | None) -> None:
    if identity is None:
        return
    try:
        global_readonly._verify_linux_directory(root, identity)
    except global_readonly.GlobalFault as error:
        raise UserConfigError(
            f"Global OpenCode root changed before configuration write; no configuration was changed: {error}"
        ) from error


def _prepare_installed_update(source: Path, role: str, model: str, effort: str,
                              scope: str, target: Path | None, *, global_root: Path | None = None,
                              max_children: int | None = None):
    from . import config_apply, global_readonly
    from .cli import load_renderer

    try:
        renderer = load_renderer(source)
        if scope == "project":
            if target is None:
                raise UserConfigError("Project override requires a managed project target.")
            root = target
            record, raw_manifest, blockers = config_apply._manifest_record(root)
            if blockers or record is None or raw_manifest is None:
                raise UserConfigError("The project Olympus ownership manifest is unavailable; no configuration was changed.")
            if record.relative_path != ".opencode/orchestrator-install.json":
                raise UserConfigError("The project Olympus ownership manifest is unsupported; no configuration was changed.")
            manifest = record.data
            manifest_relative = record.relative_path
            expected = config_apply._render_managed_outputs(source, renderer, ("opencode",))["opencode"]
            _, inventory_issues = config_apply._manifest_entries(record, set(expected))
            if inventory_issues:
                raise UserConfigError("The project Olympus inventory is unsupported; no configuration was changed.")
        else:
            root = global_root or global_readonly.resolve_roots(("opencode",))["opencode"]
            manifest_relative = _MANIFEST
            raw_manifest = global_readonly._read(root, manifest_relative)
            if raw_manifest is None:
                return None
            expected = global_readonly._expected(
                source, renderer, ("opencode",), max_children=max_children,
            )["opencode"]
            manifest, _ = global_readonly._parse_manifest_bytes(raw_manifest, "opencode", expected)
    except global_readonly.GlobalFault as error:
        raise UserConfigError(str(error)) from error
    except (ValueError, UnicodeError) as error:
        raise UserConfigError("The installed OpenCode ownership manifest is invalid; no files were changed.") from error

    agent_updates = []
    agent_roles = ("kael", "atlas") if max_children is not None else (role,)
    if max_children is not None:
        _apply_config_to_expected(source, expected, read_config(source, scope, target))
    for agent_role in agent_roles:
        relative = f"agents/{agent_role}.md"
        owned_relative = f".opencode/{relative}" if scope == "project" else relative
        entries = [entry for entry in manifest["managed_files"]
                   if isinstance(entry, dict) and entry.get("path") == owned_relative]
        if (len(entries) != 1 or not isinstance(entries[0].get("sha256"), str)
                or not _HASH.fullmatch(entries[0]["sha256"])):
            raise UserConfigError(
                f"The installed Olympus manifest does not manage {agent_role}; no configuration was changed."
            )
        if scope == "project":
            from . import config_apply

            current, issue = config_apply._read_target_file(root, f".opencode/{relative}")
            if issue:
                raise UserConfigError(
                    f"The project-managed {agent_role} agent is unsafe; no configuration was changed."
                )
        else:
            current = global_readonly._read(root, relative)
        if current is None or hashlib.sha256(current).hexdigest() != entries[0]["sha256"].lower():
            raise UserConfigError(
                f"Managed OpenCode agent {agent_role} was changed outside Olympus; "
                "preserve it and run olympus doctor."
            )
        if max_children is None:
            updated = _replace_agent_model(current, model, effort, agent_role)
        else:
            updated = expected.get(relative)
            if updated is None:
                raise UserConfigError(f"The OpenCode renderer does not manage expected agent {agent_role}.")
        entries[0]["sha256"] = hashlib.sha256(updated).hexdigest()
        agent_path = root / (f".opencode/{relative}" if scope == "project" else relative)
        agent_updates.append((agent_path, current, updated))
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest_path = root / manifest_relative
    return tuple(agent_updates), manifest_path, raw_manifest, manifest_bytes


def _check_global_recovery(root: Path) -> None:
    from . import config_apply_transaction, global_readonly

    if config_apply_transaction.pending(root):
        raise UserConfigError(
            "A pending Olympus global apply or source-edit journal blocks configuration changes; no files were changed."
        )
    try:
        intent = global_readonly._read(root, global_readonly._OPENCODE_GUARD_INTENT)
    except global_readonly.GlobalFault as error:
        raise UserConfigError(
            f"Cannot safely inspect the pending OpenCode guard intent; no configuration was changed: {error}"
        ) from error
    if intent is not None:
        raise UserConfigError(
            "An OpenCode guard transaction is pending; preserve it for explicit recovery; no files were changed."
        )


def _check_preference_recovery(path: Path, source: Path) -> None:
    from . import config_apply_transaction

    try:
        config_apply_transaction.check_preference_recovery(path, source)
    except config_apply_transaction.TransactionError as error:
        raise UserConfigError(str(error)) from error


def _preflight_global_manifest(root: Path) -> None:
    from . import global_readonly

    try:
        raw = global_readonly._read(root, _MANIFEST)
        if raw is not None:
            global_readonly._parse_manifest_bytes(raw, "opencode", None)
    except global_readonly.GlobalFault as error:
        raise UserConfigError(str(error)) from error


def _config_bytes(path: Path, scope: str, target: Path | None) -> bytes | None:
    if scope == "project":
        from . import config_apply

        raw, issue = config_apply._read_target_file(target, _PROJECT_CONFIG)
        if issue:
            raise UserConfigError(f"Unsafe project Olympus configuration: {issue}")
        return raw
    try:
        raw, _ = _read_atomic_target(path)
    except OSError as error:
        raise UserConfigError(f"Cannot safely inspect Olympus user configuration: {error}") from error
    if raw is None:
        return None
    return raw


def _commit_override(path: Path, encoded: bytes, scope: str, target: Path | None, installed,
                     *, root_check=None, source: Path, lock, change: dict,
                     project_fallback: dict | None = None) -> None:
    config_before = _config_bytes(path, scope, target)
    destinations = []
    if installed is not None:
        agent_updates, manifest_path, manifest_before, manifest_after = installed
        changed_agents = [(agent_path, current, updated) for agent_path, current, updated in agent_updates
                          if updated != current]
        if changed_agents:
            if manifest_after == manifest_before:
                raise UserConfigError("Managed agent receipts did not change with their content; no files were changed.")
            destinations.extend(changed_agents)
            destinations.append((manifest_path, manifest_before, manifest_after))
    if config_before != encoded:
        destinations.append((path, config_before, encoded))
    if not destinations:
        return

    if len(destinations) == 1:
        if root_check is not None:
            root_check()
        destination, _, content = destinations[0]
        if scope == "global" and destination == path:
            from . import config_apply_transaction

            try:
                descriptor = config_apply_transaction._settings_preference_descriptor(
                    scope, target, path, create_parent=True,
                )
                parent = descriptor["parent_identity"]
                current, _ = config_apply_transaction._settings_external_read(
                    path, (parent["st_dev"], parent["st_ino"]),
                )
            except config_apply_transaction.TransactionError as error:
                raise UserConfigError(str(error)) from error
            if current != config_before:
                raise UserConfigError("Global preferences changed before their atomic write.")
            parent_identity = (parent["st_dev"], parent["st_ino"])
        else:
            parent_identity = None
        _write_atomic(
            destination, content, expected_old=config_before, parent_identity=parent_identity,
        )
        return
    if installed is None:
        raise UserConfigError("A coordinated configuration update has no managed installation.")
    from . import config_apply_transaction

    try:
        config_apply_transaction.commit_user_config(
            target if scope == "project" else installed[0][0][0].parents[1],
            source, lock, scope, path, config_before, encoded, installed, change,
            root_check=root_check, project_fallback=project_fallback,
        )
    except config_apply_transaction.TransactionError as error:
        raise UserConfigError(str(error)) from error


def set_override(source: Path, role: str, field: str, value: str,
                 scope: str = "global", target: Path | None = None) -> tuple[Path, bool]:
    if field not in ("model", "effort"):
        raise UserConfigError(f"Unsupported override field: {field}")
    rows = {row["role"]: row for row in _canonical_rows(source)}
    if role not in rows:
        raise UserConfigError(f"Unknown Olympus agent '{role}'.")
    path = config_path(scope, target)
    lock = None
    preference_lock = None
    global_root = None
    global_root_identity = None
    if scope == "project":
        from . import config_apply, install_routing, source_edit

        try:
            target = install_routing._validate_project_target(source, target)
            record, _, blockers = config_apply._manifest_record(target)
            if blockers or record is None or "opencode" not in record.installed_harnesses:
                raise UserConfigError("The selected target is not a managed OpenCode project.")
            from .cli import load_renderer

            expected = config_apply._render_managed_outputs(source, load_renderer(source), ("opencode",))["opencode"]
            _, inventory_issues = config_apply._manifest_entries(record, set(expected))
            if inventory_issues:
                raise UserConfigError("The project Olympus inventory is incomplete or unsupported; no configuration was changed.")
            lock = source_edit._acquire_lock(target, create=True)
        except (source_edit.LockError, OSError) as error:
            raise UserConfigError(f"Cannot safely lock the managed project; no configuration was changed: {error}") from error
    else:
        from . import global_readonly, source_edit

        try:
            global_root = global_readonly.resolve_roots(("opencode",))["opencode"]
        except (global_readonly.GlobalFault, OSError, RuntimeError) as error:
            raise UserConfigError(
                f"Cannot safely resolve the global OpenCode root; no configuration was changed: {error}"
            ) from error
        try:
            global_root, global_root_identity = _ensure_global_root(global_root)
            _verify_global_root(global_readonly, global_root, global_root_identity)
            lock = source_edit._acquire_lock(global_root, create=True)
            _verify_global_root(global_readonly, global_root, global_root_identity)
        except (global_readonly.GlobalFault, source_edit.LockError, OSError, RuntimeError) as error:
            raise UserConfigError(
                f"Cannot safely lock the global OpenCode root; no configuration was changed: {error}"
            ) from error
    try:
        if scope == "project":
            from . import config_apply_transaction

            try:
                preference_lock = _acquire_preference_lock(path)
            except (source_edit.LockError, OSError) as error:
                raise UserConfigError(
                    f"Cannot safely acquire the shared preferences lock; no configuration was changed: {error}"
                ) from error
            if config_apply_transaction.pending(target):
                raise UserConfigError("A pending Olympus project edit blocks configuration changes; no files were changed.")
        else:
            _check_global_recovery(global_root)
            try:
                preference_lock = _acquire_preference_lock(path)
            except (source_edit.LockError, OSError) as error:
                raise UserConfigError(
                    f"Cannot safely acquire the shared preferences lock; no configuration was changed: {error}"
                ) from error
        _check_preference_recovery(path, source)
        config = read_config(source, scope, target)
        override = dict(config["overrides"].get(role, {}))
        override[field] = value
        global_override = read_config(source, "global")["overrides"].get(role, {}) if scope == "project" else {}
        project_fallback = None
        if scope == "project":
            project_fallback = {
                "model": global_override.get("model", rows[role]["models"]["opencode"]),
                "effort": global_override.get("effort", rows[role]["effort"]),
            }
        effective_model = override.get("model", (project_fallback or {}).get(
            "model", rows[role]["models"]["opencode"],
        ))
        effective_effort = override.get("effort", (project_fallback or {}).get(
            "effort", rows[role]["effort"],
        ))
        try:
            models_catalog.validate_assignment(effective_model, effective_effort, source)
        except models_catalog.CatalogError as error:
            raise UserConfigError(str(error)) from error
        config["overrides"][role] = override
        encoded = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        installed = _prepare_installed_update(
            source, role, effective_model, effective_effort, scope, target, global_root=global_root,
        )
        if scope == "project" and installed is None:
            raise UserConfigError("The project-managed OpenCode agent is unavailable; no configuration was changed.")
        root_check = (
            (lambda: _verify_global_root(global_readonly, global_root, global_root_identity))
            if scope != "project" and global_root_identity is not None else None
        )
        _commit_override(
            path, encoded, scope, target, installed, root_check=root_check, source=source, lock=lock,
            change={"kind": "override", "role": role, "field": field, "value": value},
            project_fallback=project_fallback,
        )
    finally:
        try:
            if preference_lock is not None:
                from . import source_edit

                source_edit._release_lock(preference_lock)
        finally:
            if lock is not None:
                from . import source_edit

                source_edit._release_lock(lock)
    applied = installed is not None
    return path.resolve(), applied


def set_max_children(source: Path, value: int) -> tuple[Path, bool]:
    if type(value) is not int or not 1 <= value <= 8:
        raise UserConfigError("max-parallel must be an integer from 1 to 8.")
    from . import global_readonly, source_edit

    try:
        global_root = global_readonly.resolve_roots(("opencode",))["opencode"]
    except (global_readonly.GlobalFault, OSError, RuntimeError) as error:
        raise UserConfigError(
            f"Cannot safely resolve the global OpenCode root; no configuration was changed: {error}"
        ) from error
    _preflight_global_manifest(global_root)
    try:
        global_root, global_root_identity = _ensure_global_root(global_root)
        _verify_global_root(global_readonly, global_root, global_root_identity)
        lock = source_edit._acquire_lock(global_root, create=True)
        _verify_global_root(global_readonly, global_root, global_root_identity)
    except (global_readonly.GlobalFault, source_edit.LockError, OSError, RuntimeError) as error:
        raise UserConfigError(
            f"Cannot safely lock the global OpenCode root; no configuration was changed: {error}"
        ) from error
    preference_lock = None
    try:
        _check_global_recovery(global_root)
        try:
            preference_lock = _acquire_preference_lock(config_path())
        except (source_edit.LockError, OSError) as error:
            raise UserConfigError(
                f"Cannot safely acquire the shared preferences lock; no configuration was changed: {error}"
            ) from error
        _check_preference_recovery(config_path(), source)
        config = read_config(source, "global")
        rows = {row["role"]: row for row in _canonical_rows(source)}
        kael = config["overrides"].get("kael", {})
        model = kael.get("model", rows["kael"]["models"]["opencode"])
        effort = kael.get("effort", rows["kael"]["effort"])
        try:
            models_catalog.validate_assignment(model, effort, source)
        except models_catalog.CatalogError as error:
            raise UserConfigError(str(error)) from error
        config["orchestration"] = {"max_children": value}
        encoded = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        installed = _prepare_installed_update(
            source, "kael", model, effort, "global", None,
            global_root=global_root, max_children=value,
        )
        root_check = (
            (lambda: _verify_global_root(global_readonly, global_root, global_root_identity))
            if global_root_identity is not None else None
        )
        _commit_override(
            config_path(), encoded, "global", None, installed, root_check=root_check, source=source, lock=lock,
            change={"kind": "max_children", "value": value},
        )
    finally:
        try:
            if preference_lock is not None:
                source_edit._release_lock(preference_lock)
        finally:
            source_edit._release_lock(lock)
    return config_path().resolve(), installed is not None


def config_listing(source: Path, scope: str = "global", target: Path | None = None) -> dict:
    roles = effective_roles(source, scope, target)
    path = config_path(scope, target).resolve()
    models_path = (source / "olympus/core/models.toml").resolve()
    try:
        if scope == "project":
            root = target
        else:
            from . import global_readonly

            root = global_readonly.resolve_roots(("opencode",))["opencode"]
        root_state = "available"
        agent_paths = {row["role"]: str((root / (".opencode/agents" if scope == "project" else "agents") /
                                         f"{row['role']}.md").resolve()) for row in roles}
    except (OSError, ValueError):
        root_state = "unavailable"
        agent_paths = {}
    sources = []
    if scope == "project":
        sources.append({"layer": "project override", "path": str(path), "exists": path.is_file()})
    global_path = config_path().resolve()
    parallel = {
        "max_children": max_children(source),
        "source": "GLOBAL",
        "path": str(global_path),
    }
    sources.append({"layer": "global override", "path": str(global_path), "exists": global_path.is_file()})
    sources.append({"layer": "canonical default", "path": str(models_path), "exists": models_path.is_file()})
    return {
        "scope": scope, "precedence": (["project override"] if scope == "project" else []) +
        ["global override", "canonical default"],
        "max_parallel": parallel,
        "sources": sources,
        "opencode_root_state": root_state, "managed_agent_paths": agent_paths,
        "roles": roles,
        "manual_edit_apply": "Apply manual edits with 'olympus install' (global) or 'olympus update' (project); doctor is read-only.",
        "manual_edit_reminder": "Run 'olympus doctor' after manual edits.",
    }


def diagnose(source: Path, scope: str = "global", target: Path | None = None) -> dict:
    roles = effective_roles(source, scope, target)
    global_path = config_path().resolve()
    return {
        "state": "valid", "scope": scope, "config_path": str(config_path(scope, target).resolve()),
        "max_parallel": {
            "max_children": max_children(source), "source": "GLOBAL", "path": str(global_path),
        },
        "catalog_path": str(models_catalog.catalog_path(source).resolve()),
        "models_checked": len(roles), "provider_access_checked": False,
    }
