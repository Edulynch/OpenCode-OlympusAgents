#!/usr/bin/env python3
"""Acquire one immutable Olympus release and route its Linux lifecycle."""

from __future__ import annotations

# Olympus pinned-install protocol: 1
# Keep this exact column-zero line to advertise support for bootstrap --_pinned.

import argparse
import base64
import datetime as dt
import hashlib
import importlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


_OWNER = "Edulynch"
_REPOSITORY = "OpenCode-OlympusAgents"
_API = f"https://api.github.com/repos/{_OWNER}/{_REPOSITORY}"
_RELEASE_TAG = re.compile(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_GIT_BLOB_SHA = re.compile(r"[0-9a-f]{40}\Z")
_MAX_JSON = 4 * 1024 * 1024
_MAX_LAUNCHER = 512 * 1024
_MAX_ARCHIVE = 100 * 1024 * 1024
_MAX_ARCHIVE_MEMBERS = 20_000
_MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
_MAX_FILE_BYTES = 16 * 1024 * 1024
_OFFICIAL_HOSTS = frozenset(("api.github.com", "codeload.github.com", "github.com"))
_ROLE_NAMES = (
    "argus", "atlas", "helios", "kael", "kovan", "nox", "orin", "talos",
    "thales", "vera", "veyra",
)
_PYTHON_FILES = (
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
_STATIC_FILES = (
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
_PACKAGE_FILES = frozenset(
    (
        *_PYTHON_FILES,
        *_STATIC_FILES,
        *(f"olympus/roles/{role}.md" for role in _ROLE_NAMES),
        *(f"olympus/harnesses/opencode/agent-metadata/{role}.md" for role in _ROLE_NAMES),
        *(f"olympus/harnesses/opencode/agent-prompts/{role}.md" for role in _ROLE_NAMES),
    )
)
_GENERATED_FILES = frozenset(
    {
        "opencode.jsonc",
        ".opencode/plugins/olympus-activity/activity.ts",
        ".opencode/plugins/olympus-activity/tui.tsx",
        ".opencode/scripts/worktree-setup.ps1",
        ".opencode/commands/olympus.ultra.md",
        ".opencode/commands/olympus.performance.md",
        *(f".opencode/agents/{role}.md" for role in _ROLE_NAMES),
    }
)
_RELEASE_FILES = _PACKAGE_FILES | _GENERATED_FILES


class ReleaseError(RuntimeError):
    def __init__(self, message: str, code: int = 3, kind: str = "release_invalid"):
        super().__init__(message)
        self.code = code
        self.kind = kind


@dataclass(frozen=True, slots=True)
class Release:
    version: str
    commit: str
    tree: str
    published_at: str


class _OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        parsed = urllib.parse.urlsplit(new_url)
        if (parsed.scheme != "https" or parsed.hostname not in _OFFICIAL_HOSTS
                or parsed.username is not None or parsed.password is not None):
            raise ReleaseError("GitHub redirected release acquisition to a non-official HTTPS host.")
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


class _HTTPTransport:
    """Fixed-host, bounded HTTPS transport; environment proxies are not consulted."""

    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(),
            _OfficialRedirect(),
        )

    def get(self, url: str, *, limit: int) -> tuple[str, bytes]:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in _OFFICIAL_HOSTS
                or parsed.username is not None or parsed.password is not None):
            raise ReleaseError("Release acquisition URL is not an official HTTPS endpoint.")
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "OlympusAgents-Linux-Installer",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                final_url = response.geturl()
                final = urllib.parse.urlsplit(final_url)
                if (final.scheme != "https" or final.hostname not in _OFFICIAL_HOSTS
                        or final.username is not None or final.password is not None):
                    raise ReleaseError("Release acquisition ended at a non-official HTTPS URL.")
                raw = response.read(limit + 1)
                if len(raw) > limit:
                    raise ReleaseError("Official release response exceeded its bounded size.")
                return final_url, raw
        except ReleaseError:
            raise
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            raise ReleaseError(f"Could not read official release metadata or bytes: {error}") from error


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _json(transport, url: str, *, limit: int = _MAX_JSON) -> dict:
    _, raw = transport.get(url, limit=limit)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (UnicodeError, ValueError, TypeError) as error:
        raise ReleaseError(f"Official GitHub JSON is invalid: {url}") from error
    if not isinstance(value, dict):
        raise ReleaseError(f"Official GitHub metadata has an unexpected shape: {url}")
    return value


def _published_timestamp(value: object, *, label: str = "Latest") -> dt.datetime:
    if not isinstance(value, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})",
        value,
    ) is None:
        raise ReleaseError(f"{label} stable release has no timezone-aware published_at timestamp.")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ReleaseError(f"{label} stable release published_at timestamp is invalid.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReleaseError(f"{label} stable release published_at timestamp has no timezone.")
    if parsed > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ReleaseError(f"{label} stable release published_at timestamp is in the future.")
    return parsed.astimezone(dt.timezone.utc)


def _select_release(transport, url: str, expected_tag: str | None = None) -> Release:
    metadata = _json(transport, url)
    label = "Latest" if expected_tag is None else "Selected"
    for key, expected in (("immutable", True), ("draft", False), ("prerelease", False)):
        if type(metadata.get(key)) is not bool or metadata[key] is not expected:
            raise ReleaseError(f"{label} release metadata does not assert {key}={str(expected).lower()}.")
    version = metadata.get("tag_name")
    if not isinstance(version, str) or _RELEASE_TAG.fullmatch(version) is None:
        label = "latest" if expected_tag is None else "selected"
        raise ReleaseError(f"GitHub {label} release is not a supported stable Olympus version.")
    if expected_tag is not None and version != expected_tag:
        raise ReleaseError("GitHub release tag does not match the requested stable Olympus version.")
    timestamp = _published_timestamp(metadata.get("published_at"), label=label)
    commit_info = _json(transport, f"{_API}/commits/{version}")
    commit = commit_info.get("sha")
    tree = commit_info.get("commit", {}).get("tree", {}).get("sha")
    if not isinstance(commit, str) or _SHA.fullmatch(commit) is None:
        raise ReleaseError("The selected immutable release does not resolve to a full commit SHA.")
    if not isinstance(tree, str) or _SHA.fullmatch(tree) is None:
        raise ReleaseError("The selected immutable release has no valid Git tree identity.")
    return Release(version, commit, tree, timestamp.isoformat().replace("+00:00", "Z"))


def _select_latest(transport=None) -> Release:
    transport = transport or _HTTPTransport()
    return _select_release(transport, f"{_API}/releases/latest")


def _select_tag(transport, tag: str) -> Release:
    if not isinstance(tag, str) or _RELEASE_TAG.fullmatch(tag) is None:
        raise ReleaseError("Requested release is not a supported stable Olympus version.")
    return _select_release(transport, f"{_API}/releases/tags/{tag}", expected_tag=tag)


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _fetch_launcher(transport, release: Release) -> tuple[bytes, str]:
    path = "scripts/launch-latest.py"
    url = f"{_API}/contents/{path}?ref={release.commit}"
    metadata = _json(transport, url, limit=_MAX_LAUNCHER * 2)
    if (metadata.get("type") != "file" or metadata.get("path") != path
            or metadata.get("encoding") != "base64"
            or type(metadata.get("size")) is not int
            or not 0 < metadata["size"] <= _MAX_LAUNCHER):
        raise ReleaseError("Official contents metadata does not identify the expected launcher file.")
    expected_html = f"https://github.com/{_OWNER}/{_REPOSITORY}/blob/{release.commit}/{path}"
    if metadata.get("html_url") != expected_html:
        raise ReleaseError("Official launcher contents identity does not match the selected commit and path.")
    blob_sha = metadata.get("sha")
    if not isinstance(blob_sha, str) or _GIT_BLOB_SHA.fullmatch(blob_sha) is None:
        raise ReleaseError("Official launcher contents metadata has no valid Git blob digest.")
    encoded = metadata.get("content")
    if not isinstance(encoded, str):
        raise ReleaseError("Official launcher contents response is incomplete.")
    try:
        raw = base64.b64decode("".join(encoded.split()), validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ReleaseError("Official launcher contents are not valid base64.") from error
    if len(raw) != metadata["size"] or _git_blob_sha(raw) != blob_sha:
        raise ReleaseError("Official launcher bytes do not match their GitHub path, size, or digest.")
    return raw, blob_sha


def _verify_bootstrap(transport, release: Release, expected: tuple[str, str, str],
                      launcher_path: Path) -> None:
    version, commit, blob_sha = expected
    if (release.version, release.commit) != (version, commit):
        raise ReleaseError("Selected immutable release changed after the public bootstrap selected it.")
    try:
        running = launcher_path.read_bytes()
    except OSError as error:
        raise ReleaseError(f"Cannot verify the isolated bootstrap launcher: {error}") from error
    if _git_blob_sha(running) != blob_sha:
        raise ReleaseError("Isolated bootstrap launcher bytes differ from the selected official Git blob.")
    official, official_sha = _fetch_launcher(transport, release)
    if official_sha != blob_sha or official != running:
        raise ReleaseError("Official launcher path, commit, and executing bytes do not match.")


def _safe_archive_path(name: str) -> str:
    if (not isinstance(name, str) or not name or "\\" in name or "\0" in name
            or any(ord(char) < 32 or ord(char) == 127 for char in name)):
        raise ReleaseError("Release archive contains an invalid member name.")
    if name.startswith("/"):
        raise ReleaseError("Release archive contains an absolute member path.")
    clean = name[:-1] if name.endswith("/") else name
    parts = clean.split("/")
    if (not clean or any(part in ("", ".", "..") or ":" in part for part in parts)):
        raise ReleaseError("Release archive contains an unsafe or non-canonical member path.")
    return clean


def _fetch_tree(transport, release: Release) -> dict[str, str]:
    url = f"{_API}/git/trees/{release.tree}?recursive=1"
    metadata = _json(transport, url, limit=_MAX_JSON)
    if metadata.get("sha") != release.tree or metadata.get("truncated") is not False:
        raise ReleaseError("Official release tree metadata is incomplete or truncated.")
    entries = metadata.get("tree")
    if not isinstance(entries, list) or len(entries) > _MAX_ARCHIVE_MEMBERS:
        raise ReleaseError("Official release tree exceeds its bounded member inventory.")
    recorded: dict[str, str] = {}
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReleaseError("Official release tree contains a malformed entry.")
        path = _safe_archive_path(entry.get("path"))
        if path in seen:
            raise ReleaseError("Official release tree contains a duplicate path.")
        seen.add(path)
        if path not in _RELEASE_FILES:
            continue
        if (entry.get("type") != "blob" or entry.get("mode") not in ("100644", "100755")
                or not isinstance(entry.get("sha"), str)
                or _GIT_BLOB_SHA.fullmatch(entry["sha"]) is None):
            raise ReleaseError(f"Required release source is not a regular Git blob: {path}")
        recorded[path] = entry["sha"]
    if set(recorded) != _RELEASE_FILES:
        missing = sorted(_RELEASE_FILES - set(recorded))
        raise ReleaseError(f"Immutable release tree is missing required payload files: {', '.join(missing[:5])}")
    return recorded


def _archive_root_name(commit: str) -> tuple[str, str]:
    prefix = f"{_OWNER}-{_REPOSITORY}-"
    url = f"https://codeload.github.com/{_OWNER}/{_REPOSITORY}/legacy.tar.gz/{commit}"
    return prefix, url


def _extract_archive(raw: bytes, release: Release, tree: dict[str, str],
                     destination: Path) -> Path:
    if not isinstance(raw, bytes) or len(raw) > _MAX_ARCHIVE:
        raise ReleaseError("Official source archive exceeds its compressed-size bound.")
    root_prefix, _ = _archive_root_name(release.commit)
    root_name = None
    root_seen = False
    seen: set[str] = set()
    selected: dict[str, bytes] = {}
    member_count = 0
    total_size = 0
    try:
        archive = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz")
    except (tarfile.TarError, OSError) as error:
        raise ReleaseError("Official source archive is not a valid gzip tarball.") from error
    with archive:
        for member in archive:
            member_count += 1
            if member_count > _MAX_ARCHIVE_MEMBERS:
                raise ReleaseError("Official source archive exceeds its member-count bound.")
            name = _safe_archive_path(member.name)
            parts = name.split("/")
            if root_name is None:
                root_name = parts[0]
                commit_suffix = root_name[len(root_prefix):] if root_name.startswith(root_prefix) else ""
                if (not commit_suffix or len(commit_suffix) < 7 or len(commit_suffix) > 40
                        or not re.fullmatch(r"[0-9a-f]+", commit_suffix)
                        or not release.commit.startswith(commit_suffix)):
                    raise ReleaseError("Source archive root does not identify the selected immutable commit.")
            if parts[0] != root_name:
                raise ReleaseError("Source archive contains more than one top-level root.")
            relative = "/".join(parts[1:])
            if not relative:
                if member.type != tarfile.DIRTYPE or member.size != 0:
                    raise ReleaseError("Source archive root is not a plain directory.")
                root_seen = True
            else:
                if relative in seen:
                    raise ReleaseError("Source archive contains a duplicate path.")
                seen.add(relative)
                if (any(
                    key in ("path", "linkpath", "size") or key.startswith("GNU.sparse")
                    for key in member.pax_headers
                ) or getattr(member, "sparse", None)):
                    raise ReleaseError("Source archive uses an overriding or sparse member header.")
                if member.type == tarfile.DIRTYPE:
                    if member.size != 0:
                        raise ReleaseError("Source archive directory has a nonzero payload size.")
                elif member.type in (tarfile.REGTYPE, tarfile.AREGTYPE):
                    if member.size < 0 or member.size > _MAX_FILE_BYTES:
                        raise ReleaseError("Source archive contains an oversized regular file.")
                    total_size += member.size
                    if total_size > _MAX_ARCHIVE_BYTES:
                        raise ReleaseError("Source archive exceeds its expanded-size bound.")
                    if relative in _RELEASE_FILES:
                        stream = archive.extractfile(member)
                        if stream is None:
                            raise ReleaseError(f"Required source archive member has no bytes: {relative}")
                        content = stream.read(member.size + 1)
                        if len(content) != member.size or _git_blob_sha(content) != tree.get(relative):
                            raise ReleaseError(f"Source archive bytes differ from the immutable Git tree: {relative}")
                        selected[relative] = content
                else:
                    raise ReleaseError("Source archive contains a link or special filesystem member.")
        if root_name is None or not root_seen or set(selected) != _RELEASE_FILES:
            raise ReleaseError("Source archive is missing one or more required canonical payload files.")

    try:
        destination.mkdir(mode=0o700)
        for relative, content in sorted(selected.items()):
            path = destination.joinpath(*PurePosixPath(relative).parts)
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(descriptor)
    except (OSError, ValueError) as error:
        raise ReleaseError(f"Cannot stage validated canonical release payload: {error}") from error
    return destination


def _download_source(transport, release: Release, tree: dict[str, str],
                    stage_root: Path) -> Path:
    _, url = _archive_root_name(release.commit)
    _, raw = transport.get(url, limit=_MAX_ARCHIVE)
    source = _extract_archive(raw, release, tree, stage_root / "source")
    return source


def _local_source_root() -> Path | None:
    path = Path(__file__).resolve()
    if (path.name == "launch-latest.py" and path.parent.name == "scripts"
            and (path.parent.parent / "olympus" / "global_cli.py").is_file()):
        return path.parent.parent
    return None


def _bootstrap_path_metadata(path: Path):
    if (not path.is_absolute() or ".." in path.parts
            or path == Path(path.anchor)):
        raise ReleaseError("A bootstrap preflight path is not a canonical absolute path.")
    cursor = Path(path.anchor)
    for index, part in enumerate(path.parts[1:]):
        cursor /= part
        try:
            metadata = os.lstat(cursor)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise ReleaseError(f"Cannot safely inspect bootstrap preflight path {cursor}: {error}") from error
        if (stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                or (index < len(path.parts[1:]) - 1 and not stat.S_ISDIR(metadata.st_mode))):
            raise ReleaseError(f"Bootstrap preflight path traverses an unsafe resource: {cursor}.")
    return metadata


def _bootstrap_read_file(path: Path, *, limit: int, mode: int | None = None) -> bytes | None:
    metadata = _bootstrap_path_metadata(path)
    if metadata is None:
        return None
    uid = getattr(os, "geteuid", None)
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            or metadata.st_size > limit
            or (uid is not None and metadata.st_uid != uid())
            or (mode is not None and os.name == "posix" and stat.S_IMODE(metadata.st_mode) != mode)):
        raise ReleaseError(f"Bootstrap preflight file has unsafe type, owner, links, mode, or size: {path}.")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise ReleaseError(f"Bootstrap preflight file changed while opening: {path}.")
            raw = stream.read(limit + 1)
    except ReleaseError:
        raise
    except OSError as error:
        raise ReleaseError(f"Cannot safely read bootstrap preflight file {path}: {error}") from error
    if len(raw) > limit:
        raise ReleaseError(f"Bootstrap preflight file exceeds its size bound: {path}.")
    return raw


def _bootstrap_user_paths() -> tuple[Path, Path]:
    home = Path.home()
    configured = os.environ.get("XDG_DATA_HOME")
    base = Path(configured) if configured else home / ".local" / "share"
    if not home.is_absolute() or not base.is_absolute():
        raise ReleaseError("The user home and XDG data directory must be absolute.")
    data_root, bin_root = base / "olympus", home / ".local" / "bin"
    for path in (home, base, data_root, bin_root):
        if any(ord(char) < 32 or ord(char) == 127 for char in str(path)):
            raise ReleaseError("Per-user CLI paths may not contain control characters.")
        _bootstrap_path_metadata(path)
    return data_root, bin_root


def _bootstrap_global_root() -> Path:
    override = os.environ.get("OPENCODE_CONFIG_DIR")
    if override:
        root = Path(override)
    else:
        executable = shutil.which("opencode")
        if not executable:
            raise ReleaseError("Cannot confirm clean global absence without the OpenCode CLI path.")
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        try:
            with tempfile.TemporaryDirectory(prefix="olympus-global-path-") as directory:
                completed = subprocess.run(
                    [executable, "debug", "paths"], cwd=directory, env=environment,
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    check=False, timeout=10, shell=False,
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ReleaseError(f"Cannot confirm the global OpenCode path: {error}") from error
        paths = [
            match.group("path").strip()
            for match in re.finditer(r"(?m)^\s*config\s{2,}(?P<path>.+?)\s*$", completed.stdout or "")
        ]
        if completed.returncode or len(paths) != 1:
            raise ReleaseError("OpenCode did not report exactly one global config path.")
        root = Path(paths[0])
    if not root.is_absolute() or root == Path(root.anchor) or ".." in root.parts:
        raise ReleaseError("The global OpenCode config path is not a canonical absolute directory.")
    _bootstrap_path_metadata(root)
    return root


def _validate_bootstrap_package(package_root: Path, tree: dict[str, str],
                                receipt_sha256: str) -> None:
    receipt = "olympus-cli-package.json"
    expected_files = _RELEASE_FILES | {receipt}
    expected_directories = {""}
    for name in expected_files:
        parts = name.split("/")[:-1]
        expected_directories.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    found_files: set[str] = set()
    found_directories: set[str] = set()
    total = 0
    device = None
    uid = getattr(os, "geteuid", None)

    def visit(directory: Path, relative: str) -> None:
        nonlocal total, device
        try:
            metadata = os.lstat(directory)
        except OSError as error:
            raise ReleaseError(f"Cannot safely inspect installed CLI package directory {directory}: {error}") from error
        if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                or (uid is not None and metadata.st_uid != uid())
                or (device is not None and metadata.st_dev != device)
                or (os.name == "posix" and stat.S_IMODE(metadata.st_mode) != 0o555)):
            raise ReleaseError(f"Installed CLI package directory is unsafe or changed: {directory}.")
        if device is None:
            device = metadata.st_dev
        found_directories.add(relative)
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as error:
            raise ReleaseError(f"Cannot enumerate installed CLI package directory {directory}: {error}") from error
        for entry in entries:
            name = f"{relative}/{entry.name}" if relative else entry.name
            try:
                item = entry.stat(follow_symlinks=False)
            except OSError as error:
                raise ReleaseError(f"Cannot inspect installed CLI package resource {name}: {error}") from error
            if (stat.S_ISLNK(item.st_mode)
                    or getattr(item, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                    or (uid is not None and item.st_uid != uid())):
                raise ReleaseError(f"Installed CLI package contains a linked or foreign resource: {name}.")
            if stat.S_ISDIR(item.st_mode):
                if name not in expected_directories:
                    raise ReleaseError(f"Installed CLI package contains an unexpected directory: {name}.")
                visit(directory / entry.name, name)
                continue
            if (not stat.S_ISREG(item.st_mode)
                    or (os.name == "posix" and item.st_nlink != 1)
                    or name not in expected_files or item.st_size > _MAX_FILE_BYTES
                    or (os.name == "posix" and stat.S_IMODE(item.st_mode) != 0o444)):
                raise ReleaseError(f"Installed CLI package contains an unsafe or unexpected file: {name}.")
            file_path = directory / entry.name
            file_metadata = _bootstrap_path_metadata(file_path)
            if file_metadata is None or (device is not None and file_metadata.st_dev != device):
                raise ReleaseError(f"Installed CLI package resource crosses its filesystem: {name}.")
            raw = _bootstrap_read_file(file_path, limit=_MAX_FILE_BYTES, mode=0o444)
            if raw is None:
                raise ReleaseError(f"Installed CLI package resource disappeared: {name}.")
            found_files.add(name)
            total += len(raw)
            if total > _MAX_ARCHIVE_BYTES:
                raise ReleaseError("Installed CLI package exceeds its bounded byte inventory.")
            if name == receipt:
                if hashlib.sha256(raw).hexdigest() != receipt_sha256:
                    raise ReleaseError("Installed CLI package receipt differs from the current marker.")
            else:
                comparable = raw
                if name == "scripts/olympus":
                    comparable = raw.replace(b"\r\n", b"\n")
                    if b"\r" in comparable:
                        raise ReleaseError("Installed POSIX CLI launcher contains unsupported carriage returns.")
                if _git_blob_sha(comparable) != tree.get(name):
                    raise ReleaseError(f"Installed CLI package bytes differ from the pinned Git tree: {name}.")

    _bootstrap_path_metadata(package_root)
    visit(package_root, "")
    if found_files != expected_files or found_directories != expected_directories:
        raise ReleaseError("Installed CLI package inventory differs from the pinned release layout.")


def _bootstrap_install_preflight(transport, release: Release):
    data_root, bin_root = _bootstrap_user_paths()
    current_path = data_root / "current"
    current_raw = _bootstrap_read_file(current_path, limit=1024, mode=0o600)
    if current_raw is None:
        data_metadata = _bootstrap_path_metadata(data_root)
        if data_metadata is not None:
            try:
                with os.scandir(data_root) as entries:
                    if next(entries, None) is not None:
                        raise ReleaseError("Per-user CLI data exists without its current package marker.")
            except OSError as error:
                raise ReleaseError(f"Cannot inspect per-user CLI data directory: {error}") from error
        if _bootstrap_path_metadata(bin_root / "olympus") is not None:
            raise ReleaseError("A stable CLI launcher exists without its current package marker.")
        root = _bootstrap_global_root()
        evidence = (
            root / "olympus" / "orchestrator-install.json",
            root / ".olympus-cli-config-apply",
            root / ".olympus-cli-edit",
            root / ".olympus-cli-edit.lock",
            root / "olympus" / "opencode-guard-pending.json",
        )
        if any(_bootstrap_path_metadata(path) is not None for path in evidence):
            raise ReleaseError(
                "Global Olympus ownership or pending transaction evidence exists without its per-user CLI package.",
                kind="lifecycle_blocked",
            )
        return None

    pending = data_root / "uninstall-pending.json"
    if _bootstrap_path_metadata(pending) is not None:
        raise ReleaseError("CLI uninstall cleanup is pending; rerun explicit uninstall.",
                           kind="lifecycle_blocked")
    try:
        text = current_raw.decode("ascii")
        lines = text.splitlines()
    except UnicodeError as error:
        raise ReleaseError("Per-user CLI current marker is not ASCII.") from error
    if (len(lines) != 3 or text != "\n".join(lines) + "\n"
            or _RELEASE_TAG.fullmatch(lines[0]) is None
            or _SHA.fullmatch(lines[1]) is None
            or re.fullmatch(r"[0-9a-f]{64}", lines[2]) is None):
        raise ReleaseError("Per-user CLI current marker is malformed.", kind="lifecycle_blocked")
    if (lines[0], lines[1]) != (release.version, release.commit):
        raise ReleaseError(
            "A different per-user CLI version/commit is installed; refusing bootstrap install.",
            kind="lifecycle_blocked",
        )

    tree = _fetch_tree(transport, release)
    package_root = data_root / "versions" / lines[0]
    _validate_bootstrap_package(package_root, tree, lines[2])
    lifecycle = _load_lifecycle(package_root, isolated_name=uuid.uuid4().hex)
    global_cli = lifecycle[0]
    try:
        identity = global_cli.recorded_identity()
        if identity is None or (identity.version, identity.commit) != (release.version, release.commit):
            raise ReleaseError("The installed CLI/global identity does not match the selected release.",
                               kind="lifecycle_blocked")
        global_cli.verify(version=release.version, commit=release.commit)
    except ReleaseError:
        raise
    except Exception as error:
        raise ReleaseError(f"Cannot verify the current Linux CLI/global installation: {error}",
                           kind="lifecycle_blocked") from error
    return identity


def _load_lifecycle(source_root: Path, *, isolated_name: str | None = None):
    if isolated_name is None:
        resolved = str(source_root.resolve(strict=True))
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
        return (
            importlib.import_module("olympus.global_cli"),
            importlib.import_module("olympus.global_install"),
            importlib.import_module("olympus.global_readonly"),
        )
    package_name = f"_olympus_release_{isolated_name}"
    init_path = source_root / "olympus" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        package_name, init_path, submodule_search_locations=[str(init_path.parent)],
    )
    if spec is None or spec.loader is None:
        raise ReleaseError("Cannot load the isolated immutable release package.")
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    spec.loader.exec_module(package)
    return (
        importlib.import_module(f"{package_name}.global_cli"),
        importlib.import_module(f"{package_name}.global_install"),
        importlib.import_module(f"{package_name}.global_readonly"),
    )


def _validate_source(source_root: Path, lifecycle, release: Release) -> None:
    global_cli, _, _ = lifecycle
    try:
        cli = importlib.import_module(global_cli.__package__ + ".cli")
        declared = cli.release_version(source_root)
        if declared != release.version:
            raise ReleaseError(
                f"Staged install.ps1 identity is {declared}, not selected release {release.version}.",
            )
        global_cli._validated_source(source_root, release.version, release.commit)
    except ReleaseError:
        raise
    except Exception as error:
        raise ReleaseError(f"Canonical release source failed package validation: {error}") from error


def _release_version_compare(global_install, left: str, right: str) -> int:
    comparison = global_install._version_compare(left, right)
    if comparison is None:
        raise ReleaseError("Installed and latest release versions cannot be ordered safely.")
    return comparison


def _change_plan(global_install, source_root: Path, release: Release, operation: str) -> list[dict]:
    candidate = global_install._candidate(source_root, release.version, release.commit)
    try:
        root, root_identity = global_install._resolve_root(create=False)
    except global_install.GlobalInstallError:
        root = global_install.global_readonly.resolve_roots(("opencode",))["opencode"]
        global_install.global_readonly._root(root)
        if root.exists():
            raise
        if operation == "uninstall":
            return []
        if operation == "update":
            raise ReleaseError("Cannot preview update because the global OpenCode root is missing.")
        global_install._check_roots(candidate.source, root)
        return [
            {"action": "create", "path": path}
            for path in sorted((*candidate.expected, global_install._MANIFEST))
        ]
    global_install._check_roots(candidate.source, root)
    lock = global_install._existing_lock(root, root_identity)
    try:
        if global_install.config_apply_transaction.pending(root):
            raise ReleaseError("A pending global transaction blocks lifecycle preview.")
        manifest_raw, _ = global_install._read(root, global_install._MANIFEST)
        if manifest_raw is not None and lock is None:
            raise ReleaseError("Global lifecycle preview requires the existing stable writer lock.")
        changes = (
            global_install._build_uninstall(root, candidate)
            if operation == "uninstall"
            else global_install._build_install(root, candidate, update=operation == "update")
        )
        return [
            {
                "action": "remove" if item.new is None else "create" if item.old is None else "update",
                "path": item.path,
            }
            for item in changes
        ]
    finally:
        if lock is not None:
            global_install.source_edit._release_lock(lock)


def _response(action: str, dry_run: bool, source_root: Path | None) -> dict:
    mode = "dry-run" if dry_run else "execute"
    return {
        "schema_version": 1,
        "operation": action,
        "result": "blocked",
        "context": {
            "source": str(source_root) if source_root else "official immutable release",
            "kind": "native_install_routing",
            "scope": "global",
            "harness": "opencode",
            "mode": mode,
        },
        "data": {
            "mode": mode,
            "engine": "scripts/launch-latest.py",
            "state": "not_started",
            "native_exit_code": None,
            "native_stdout": "",
            "native_stderr": "",
            "effects": "none_confirmed",
            "cwd_role": "ignored_for_global_target_resolution",
            "release_version": "latest stable",
        },
        "issues": [],
    }


def _plan_logs(plan: list[dict]) -> str:
    return "".join(f"{item['action'].upper()}: {item['path']}\n" for item in plan)


def _success(response: dict, release: Release | None, *, dry_run: bool,
             result: str, plan: list[dict] | None = None, outcome=None) -> tuple[dict, int]:
    data = response["data"]
    data.update({
        "native_exit_code": 0,
        "state": "preview" if dry_run else "ok",
        "effects": (
            "target_read_only_preview; temporary/cache effects may remain"
            if dry_run else "native_engine_confirmed_success"
        ),
        "installation_state": (
            "not_installed" if response["operation"] == "install"
            else "not_removed" if response["operation"] == "uninstall"
            else "installed"
        ),
    })
    if release is not None:
        data.update({"release_version": release.version, "release_commit": release.commit})
        data["native_stdout"] += (
            f"OLYMPUS_RELEASE_SELECTED: tag={release.version} immutable=true "
            f"published_at={release.published_at}\n"
        )
    if plan is not None:
        data["plan"] = plan
        data["native_stdout"] += _plan_logs(plan)
    if outcome is not None:
        data.update({
            "installation_state": (
                "not_removed" if outcome.operation == "uninstall" and outcome.result == "no_changes"
                else "removed" if outcome.operation == "uninstall"
                else "installed"
            ),
            "changed_paths": list(outcome.changed_paths),
            "detail": outcome.detail,
            "lifecycle_result": outcome.result,
        })
        data["native_stdout"] += (
            f"OLYMPUS_GLOBAL_INSTALL: OPENCODE {outcome.version or 'absent'} "
            f"{outcome.result.upper()} ({len(outcome.changed_paths)} managed resources; "
            f"root={outcome.global_root})\n"
        )
    response["result"] = "preview" if dry_run else "ok"
    return response, 0


def _failure(response: dict, error: BaseException, *, effects_started: bool) -> tuple[dict, int]:
    code = getattr(error, "code", 3)
    if not isinstance(code, int) or code not in (1, 2, 3, 4):
        code = 4 if effects_started else 1
    if effects_started and code != 4:
        code = 4
    result = {1: "failed", 2: "failed", 3: "blocked", 4: "unconfirmed"}[code]
    response["result"] = result
    response["data"].update({
        "state": "unconfirmed" if code == 4 else "not_started" if code == 3 else "failed",
        "effects": (
            "unconfirmed_after_native_failure" if code == 4
            else "none_confirmed" if code == 3
            else "target_read_only_preview; temporary/cache effects may remain"
            if response["data"]["mode"] == "dry-run"
            else "none_confirmed"
        ),
        "native_exit_code": code,
        "native_stderr": str(error),
    })
    response["issues"].append({
        "code": getattr(error, "kind", "lifecycle_unconfirmed" if code == 4 else "lifecycle_failed"),
        "message": str(error),
    })
    return response, code


def _check_local_install(global_cli, release: Release, *, action: str):
    identity = global_cli.recorded_identity()
    if action == "install":
        if identity is None:
            return None
        if (identity.version, identity.commit) == (release.version, release.commit):
            global_cli.verify(version=release.version, commit=release.commit)
            return identity
        raise ReleaseError(
            "A different verified Linux CLI/global identity is installed; use 'olympus update'.",
            kind="lifecycle_blocked",
        )
    if action == "update":
        if identity is None:
            raise ReleaseError("Update requires an existing verified Linux CLI/global installation.",
                                kind="lifecycle_blocked")
        comparison = _release_version_compare(
            importlib.import_module(global_cli.__package__ + ".global_install"),
            release.version, identity.version,
        )
        if comparison == 0:
            if identity.commit != release.commit:
                raise ReleaseError(
                    "Latest stable release has the installed version but a different commit; refusing repair.",
                    kind="lifecycle_blocked",
                )
            global_cli.verify(version=release.version, commit=release.commit)
            return identity
        if comparison < 0:
            raise ReleaseError("Latest stable release is older than the installed identity; downgrade blocked.",
                               kind="lifecycle_blocked")
        return identity
    return identity


def _local_uninstall(global_cli, *, dry_run: bool, lifecycle) -> tuple[dict | None, list[dict] | None]:
    if not dry_run:
        return global_cli._uninstall_current(), None
    identity = global_cli.recorded_identity()
    if identity is None:
        return None, []
    global_cli.verify(version=identity.version, commit=identity.commit)
    _, global_install, _ = lifecycle
    candidate = global_install._candidate(
        identity.package_root, identity.version, identity.commit,
    )
    root, root_identity = global_install._resolve_root(create=False)
    global_install._check_roots(candidate.source, root)
    lock = global_install._existing_lock(root, root_identity)
    try:
        if global_install.config_apply_transaction.pending(root):
            raise ReleaseError("A pending global transaction blocks uninstall preview.")
        changes = global_install._build_uninstall(root, candidate)
    finally:
        if lock is not None:
            global_install.source_edit._release_lock(lock)
    package_root = identity.package_root
    plan = [
        {"action": "remove", "path": item.path} for item in changes
    ]
    data_root, bin_root = global_cli._user_paths()
    plan.extend([
        {"action": "remove", "path": str(package_root)},
        {"action": "remove", "path": str(data_root / global_cli._CURRENT)},
        {"action": "remove", "path": str(bin_root / "olympus")},
    ])
    return None, plan


def run_action(action: str, *, dry_run: bool = False, source_root: Path | None = None,
               bootstrap: tuple[str, str, str] | None = None, transport=None,
               temp_parent: Path | None = None, pinned_bootstrap: bool = False) -> tuple[dict, int]:
    """Execute one route; tests inject a trusted transport directly, never endpoint flags."""
    if action not in ("install", "update", "verify", "uninstall"):
        raise ReleaseError("Unsupported Linux lifecycle operation.")
    if bootstrap is not None and len(bootstrap) != 3:
        raise ReleaseError("Bootstrap identity is incomplete.")
    if pinned_bootstrap and (
        action != "install" or bootstrap is None or not isinstance(bootstrap[0], str)
        or _RELEASE_TAG.fullmatch(bootstrap[0]) is None
    ):
        raise ReleaseError("Pinned release selection requires a stable bootstrap install identity.")
    transport = transport or _HTTPTransport()
    source_root = source_root or _local_source_root()
    response = _response(action, dry_run, source_root)
    stage_root: Path | None = None
    effects_started = False
    preserve_stage = False
    release: Release | None = None
    try:
        if bootstrap is not None or action in ("install", "update") or (
            action in ("verify", "uninstall") and source_root is None
        ):
            release = (
                _select_tag(transport, bootstrap[0])
                if pinned_bootstrap else _select_latest(transport)
            )
        if bootstrap is not None:
            if release is None:
                raise ReleaseError("Bootstrap release identity could not be resolved.")
            _verify_bootstrap(transport, release, bootstrap, Path(__file__).resolve())

        if bootstrap is not None and action == "install":
            current = _bootstrap_install_preflight(transport, release)
            if current is not None:
                response, code = _success(
                    response, release, dry_run=dry_run,
                    result="preview" if dry_run else "ok",
                    plan=[] if dry_run else None,
                )
                response["data"]["installation_state"] = "installed"
                return response, code

        if action == "uninstall" and source_root is not None and bootstrap is None:
            lifecycle = _load_lifecycle(source_root)
            global_cli, _, _ = lifecycle
            effects_started = not dry_run
            outcome, plan = _local_uninstall(global_cli, dry_run=dry_run, lifecycle=lifecycle)
            if dry_run:
                return _success(response, None, dry_run=True, result="preview", plan=plan)
            return _success(response, None, dry_run=False, result="ok", outcome=outcome)

        if action == "verify" and source_root is not None and bootstrap is None:
            global_cli, _, _ = _load_lifecycle(source_root)
            identity = global_cli.recorded_identity()
            if identity is None:
                raise ReleaseError("No verified Linux CLI/global installation exists.",
                                   kind="lifecycle_blocked")
            outcome = global_cli.verify(version=identity.version, commit=identity.commit)
            return _success(response, None, dry_run=False, result="ok", outcome=outcome)

        local_lifecycle = _load_lifecycle(source_root) if source_root is not None else None
        current = None
        if action in ("install", "update") and local_lifecycle is not None:
            local_cli = local_lifecycle[0]
            current = _check_local_install(local_cli, release, action=action)
            if current is not None and (current.version, current.commit) == (
                release.version, release.commit,
            ):
                response, code = _success(
                    response, release, dry_run=dry_run, result="preview" if dry_run else "ok",
                    plan=[] if dry_run else None,
                )
                response["data"]["installation_state"] = "installed"
                if action == "update":
                    response["data"]["native_stdout"] += (
                        f"OLYMPUS_UPDATE: Already up to date ({release.version}).\n"
                    )
                return response, code
        elif action == "update":
            raise ReleaseError("The bootstrap entry supports install and uninstall; run update via installed olympus.",
                               kind="lifecycle_blocked")

        tree = _fetch_tree(transport, release)
        stage_root = Path(tempfile.mkdtemp(prefix="olympus-release-", dir=temp_parent))
        staged_source = _download_source(transport, release, tree, stage_root)
        lifecycle = _load_lifecycle(staged_source, isolated_name=uuid.uuid4().hex)
        _validate_source(staged_source, lifecycle, release)
        selected = (
            _select_tag(transport, bootstrap[0])
            if pinned_bootstrap else _select_latest(transport)
        )
        if selected != release:
            raise ReleaseError("Selected immutable release changed during acquisition; no lifecycle was started.")

        global_cli, global_install, _ = lifecycle
        if action in ("install", "update"):
            if dry_run:
                if action == "update" and current is None:
                    raise ReleaseError("Update requires a verified installed identity.", kind="lifecycle_blocked")
                plan = _change_plan(global_install, staged_source, release, action)
                data_root, bin_root = global_cli._user_paths()
                if action == "install" and current is None:
                    plan.extend([
                        {"action": "create", "path": str(data_root / "versions" / release.version)},
                        {"action": "create", "path": str(bin_root / "olympus")},
                        {"action": "create", "path": str(data_root / global_cli._CURRENT)},
                    ])
                elif action == "update":
                    plan.extend([
                        {"action": "create", "path": str(data_root / "versions" / release.version)},
                        {"action": "update", "path": str(data_root / global_cli._CURRENT)},
                    ])
                return _success(response, release, dry_run=True, result="preview", plan=plan)
            effects_started = True
            outcome = (
                global_cli.install(staged_source, version=release.version, commit=release.commit)
                if action == "install"
                else global_cli.update(staged_source, version=release.version, commit=release.commit)
            )
            global_cli.verify(version=release.version, commit=release.commit)
            return _success(response, release, dry_run=False, result="ok", outcome=outcome)

        if action == "uninstall":
            if dry_run:
                current = global_cli.recorded_identity()
                if current is None:
                    return _success(response, release, dry_run=True, result="preview", plan=[])
                global_cli.verify(version=current.version, commit=current.commit)
                try:
                    plan = _change_plan(
                        global_install, current.package_root,
                        Release(current.version, current.commit, release.tree, release.published_at),
                        "uninstall",
                    )
                except (OSError, ValueError) as error:
                    raise ReleaseError(f"Cannot validate current global uninstall plan: {error}") from error
                plan.extend([
                    {"action": "remove", "path": str(current.package_root)},
                    {"action": "remove", "path": str(global_cli._user_paths()[0] / global_cli._CURRENT)},
                    {"action": "remove", "path": str(global_cli._user_paths()[1] / "olympus")},
                ])
                return _success(response, release, dry_run=True, result="preview", plan=plan)
            effects_started = True
            outcome = global_cli._uninstall_current()
            return _success(response, release, dry_run=False, result="ok", outcome=outcome)

        if action == "verify":
            identity = global_cli.recorded_identity()
            if identity is None:
                raise ReleaseError("No verified Linux CLI/global installation exists.",
                                   kind="lifecycle_blocked")
            outcome = global_cli.verify(version=identity.version, commit=identity.commit)
            return _success(response, release, dry_run=False, result="ok", outcome=outcome)

        raise ReleaseError("Unsupported Linux lifecycle operation.")
    except KeyboardInterrupt as error:
        preserve_stage = effects_started and stage_root is not None
        error = ReleaseError(
            "Lifecycle interrupted; effects are unconfirmed. Inspect the selected installation before retrying.",
            4 if effects_started else 3,
            "lifecycle_unconfirmed" if effects_started else "lifecycle_interrupted",
        )
        if preserve_stage:
            response["data"]["preserved_source"] = str(stage_root)
        return _failure(response, error, effects_started=effects_started)
    except BaseException as error:
        preserve_stage = effects_started
        if preserve_stage and stage_root is not None:
            response["data"]["preserved_source"] = str(stage_root)
        return _failure(response, error, effects_started=effects_started)
    finally:
        if stage_root is not None and not preserve_stage:
            shutil.rmtree(stage_root, ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="launch-latest.py",
        description="Acquire an official immutable Olympus release for a Linux lifecycle operation.",
    )
    parser.add_argument("action", choices=("install", "update", "verify", "uninstall"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--_response", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_bootstrap", nargs=3, metavar=("VERSION", "COMMIT", "BLOB_SHA"),
                        help=argparse.SUPPRESS)
    parser.add_argument("--_pinned", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args._pinned and (args.action != "install" or args._bootstrap is None):
        _parser().error("--_pinned is only valid for a bootstrap install.")
    response, code = run_action(
        args.action,
        dry_run=args.dry_run,
        bootstrap=tuple(args._bootstrap) if args._bootstrap else None,
        pinned_bootstrap=args._pinned,
    )
    if args._response:
        print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"Olympus {args.action}: {response['result']}")
        for line in response["data"]["native_stdout"].splitlines():
            print(line)
        if response["data"]["native_stderr"]:
            print(response["data"]["native_stderr"], file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
