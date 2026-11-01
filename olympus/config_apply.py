"""Read-only preview of an update to an existing project installation.

This slice deliberately has no target writer. It validates the current project
manifest and every manifest-owned file before presenting an in-memory render.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from .install_manifest import (
    MANIFEST_PATHS,
    ManifestError,
    ProjectManifest,
    manifest_paths,
    manifest_present,
    parse_project_manifest,
)


_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_OPEN_CODE_FOREIGN_CONFIGS = (
    "opencode.json",
    ".opencode/opencode.json",
    ".opencode/opencode.jsonc",
)
_RETIRED_OPEN_CODE_AGENTS = (
    ".opencode/agents/sorin.md",
    ".opencode/agents/maintenance.md",
)


class PreviewFault(ValueError):
    def __init__(self, code: int, issue_code: str, message: str):
        super().__init__(message)
        self.code = code
        self.issue_code = issue_code


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _without_git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("GIT_"):
            environment.pop(key, None)
    return environment


def _validate_target(source: Path, requested: Path) -> Path:
    if not requested.is_absolute():
        raise PreviewFault(2, "invalid_target", "Project config apply requires an absolute --target path.")
    try:
        target = requested.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise PreviewFault(2, "invalid_target", f"Target does not resolve to an existing directory: {requested}") from error
    if not target.is_dir():
        raise PreviewFault(2, "invalid_target", f"Target is not a directory: {target}")
    if target == Path(target.anchor):
        raise PreviewFault(2, "invalid_target", "A filesystem root cannot be a project target.")
    try:
        home = Path.home().resolve(strict=True)
    except (OSError, RuntimeError):
        home = None
    if home is not None and _same_path(target, home):
        raise PreviewFault(2, "invalid_target", "A user home/profile directory cannot be a project target.")
    if _same_path(target, source):
        raise PreviewFault(3, "source_is_target", "The canonical source checkout cannot also be the installation target.")

    try:
        completed = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
            env=_without_git_environment(),
        )
    except FileNotFoundError as error:
        raise PreviewFault(3, "git_unavailable", "Git is required to confirm the project worktree root.") from error
    except subprocess.TimeoutExpired as error:
        raise PreviewFault(3, "target_unconfirmed", "Git did not confirm the target worktree root within 10 seconds.") from error
    try:
        git_root = Path(completed.stdout.strip()).resolve(strict=True) if completed.returncode == 0 else None
    except (OSError, RuntimeError):
        git_root = None
    if git_root is None:
        raise PreviewFault(2, "invalid_target", "Target is not a Git worktree: --target must name an existing project root.")
    if not _same_path(git_root, target):
        raise PreviewFault(2, "invalid_target", f"Target is not the Git worktree root; use {git_root}.")
    return target


def _lexical_relative(relative: str) -> tuple[str, ...]:
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise ValueError("Expected a canonical, relative POSIX path")
    path = PurePosixPath(relative)
    if (path.is_absolute() or path.as_posix() != relative
            or any(part in ("", ".", "..") for part in path.parts)):
        raise ValueError("Expected a contained, relative path")
    return path.parts


def _lstat_target_path(target: Path, relative: str) -> tuple[Path | None, os.stat_result | None, str | None]:
    """Inspect path components without following symlinks/reparse points."""
    try:
        parts = _lexical_relative(relative)
    except ValueError as error:
        return None, None, str(error)
    current = target
    for index, part in enumerate(parts):
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return current, None, None
        except OSError as error:
            return current, None, f"Cannot inspect target path {relative}: {error}"
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT:
            return current, metadata, f"Linked/reparse target path is not safe: {relative}"
        if index < len(parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            return current, metadata, f"Target parent is not a directory: {relative}"
    return current, metadata, None


def _read_target_file(target: Path, relative: str) -> tuple[bytes | None, str | None]:
    path, before, issue = _lstat_target_path(target, relative)
    if issue:
        return None, issue
    if before is None:
        return None, None
    assert path is not None
    if not stat.S_ISREG(before.st_mode):
        return None, f"Managed target is not a regular file: {relative}"
    if before.st_nlink > 1:
        return None, f"Hard-linked managed target is not safe to update: {relative}"

    descriptor = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink > 1
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            return None, f"Managed target identity changed during preview: {relative}"
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            raw = stream.read()
            after = os.fstat(stream.fileno())
        path_after, after_path, path_issue = _lstat_target_path(target, relative)
        if path_issue or after_path is None or path_after != path:
            return None, path_issue or f"Managed target disappeared during preview: {relative}"
        if ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                or (after_path.st_dev, after_path.st_ino) != (opened.st_dev, opened.st_ino)):
            return None, f"Managed target changed during preview: {relative}"
        return raw, None
    except OSError as error:
        return None, f"Cannot read managed target {relative}: {error}"
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _existing_path_issue(target: Path, relative: str) -> tuple[bool, str | None]:
    path, metadata, issue = _lstat_target_path(target, relative)
    if issue:
        return False, issue
    if metadata is None:
        return False, None
    if not stat.S_ISREG(metadata.st_mode):
        return True, f"Conflicting destination is not a regular file: {relative}"
    return True, None


def _manifest_record(target: Path) -> tuple[ProjectManifest | None, bytes | None, list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    paths = manifest_paths(target)
    present: list[Path] = []
    raw_by_path: dict[Path, bytes] = {}
    for relative, path in zip(MANIFEST_PATHS, paths):
        raw, issue = _read_target_file(target, relative)
        if issue:
            blockers.append({"code": "unsafe_manifest", "message": issue, "path": relative})
        elif raw is not None:
            present.append(path)
            raw_by_path[path] = raw
    if blockers:
        return None, None, blockers
    if len(present) > 1:
        return None, None, [{
            "code": "ambiguous_manifest",
            "message": "Both project manifest locations exist; ownership is ambiguous.",
        }]
    if not present:
        return None, None, [{
            "code": "manifest_missing",
            "message": "No existing Olympus project manifest was found; config apply does not install or adopt a target.",
        }]
    path = present[0]
    raw = raw_by_path[path]
    if len(raw) > 2_000_000:
        return None, None, [{
            "code": "manifest_too_large",
            "message": "Project install manifest exceeds the 2 MB read-only preview limit.",
            "path": path.relative_to(target).as_posix(),
        }]
    try:
        record = parse_project_manifest(target, path, raw)
    except ManifestError as error:
        code = "ambiguous_manifest" if error.code == "contradictory" else "invalid_manifest"
        return None, None, [{"code": code, "message": str(error), "path": path.relative_to(target).as_posix()}]
    return record, raw, blockers


def _render_managed_outputs(source: Path, renderer, installed: tuple[str, ...]) -> dict[str, dict[str, bytes]]:
    selector = "all" if set(installed) == {"opencode", "codex"} else installed[0]
    rendered = renderer.outputs_for(source, selector)
    by_harness: dict[str, dict[str, bytes]] = {name: {} for name in installed}
    for path, content in rendered.items():
        try:
            if not path.resolve().is_relative_to(source):
                raise PreviewFault(3, "source_path_unsafe", f"Rendered source output escapes the checkout: {path}")
            relative = path.relative_to(source).as_posix()
        except ValueError as error:
            raise PreviewFault(3, "source_path_unsafe", f"Rendered source output is outside the checkout: {path}") from error
        if relative.startswith(".opencode/") or relative == "opencode.jsonc":
            harness = "opencode"
        elif relative.startswith(".codex/") or relative == "CODEX.md":
            harness = "codex"
        else:
            # all also returns the source-side capability document, not an
            # installed resource.
            continue
        if harness not in by_harness:
            raise PreviewFault(3, "source_inventory_unsupported", f"Renderer returned an unselected managed resource: {relative}")
        if not isinstance(content, str):
            raise PreviewFault(1, "source_invalid", f"Renderer returned non-text content for {relative}")
        by_harness[harness][relative] = content.encode("utf-8")
    return by_harness


def _manifest_entries(record: ProjectManifest, expected: set[str]) -> tuple[dict[str, str], list[dict[str, str]]]:
    entries: dict[str, str] = {}
    blockers: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in record.data["managed_files"]:
        if not isinstance(entry, dict):
            blockers.append({"code": "invalid_manifest_entry", "message": "Manifest managed_files contains a non-object entry."})
            continue
        raw_path = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(raw_path, str):
            blockers.append({"code": "invalid_manifest_entry", "message": "Manifest managed_files entry has no string path."})
            continue
        relative = raw_path.replace("\\", "/")
        folded = relative.casefold()
        if folded in seen:
            blockers.append({"code": "duplicate_manifest_path", "message": f"Manifest contains a duplicate managed path: {relative}", "path": relative})
            continue
        seen.add(folded)
        if relative not in expected:
            blockers.append({"code": "unsupported_manifest_inventory", "message": f"Manifest contains a path outside the current renderer inventory: {relative}", "path": relative})
            continue
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            blockers.append({"code": "invalid_manifest_hash", "message": f"Manifest has an invalid SHA-256 for {relative}.", "path": relative})
            continue
        entries[relative] = digest.lower()
    missing = sorted(expected - set(entries))
    if missing:
        blockers.append({
            "code": "incomplete_manifest_inventory",
            "message": "Manifest does not own every resource in the current renderer inventory: " + ", ".join(missing),
        })
    return entries, blockers


def _blank_data() -> dict[str, Any]:
    return {
        "preview_only": True,
        "apply_available": False,
        "preview_state": "blocked",
        "changes": [],
        "unchanged": [],
        "preserved": {"harnesses": [], "resources": []},
        "conflicts": [],
        "checks": [],
    }


def _blocked(response: dict, blockers: list[dict[str, str]], data: dict[str, Any] | None = None) -> int:
    response["result"] = "blocked"
    response["data"] = _blank_data() if data is None else data
    response["data"]["preview_only"] = True
    response["data"]["apply_available"] = False
    response["data"]["preview_state"] = "blocked"
    response["data"]["changes"] = []
    response["data"]["unchanged"] = []
    response["issues"] = blockers
    response["data"]["conflicts"] = blockers
    return 3


def _failed(response: dict, error: PreviewFault) -> int:
    response["result"] = "blocked" if error.code == 3 else "failed"
    response["data"] = _blank_data()
    response["issues"] = [{"code": error.issue_code, "message": str(error)}]
    response["data"]["conflicts"] = list(response["issues"]) if error.code == 3 else []
    return error.code


def preview(source: Path, args, response: dict, *, source_query: Callable, load_renderer: Callable,
            release_version: Callable) -> int:
    response["operation"] = "config apply"
    response["context"] = {
        "source": str(source),
        "kind": "config_apply_preview",
        "scope": args.scope,
        "harness": args.harness,
        "target": str(args.target),
    }
    try:
        if args.scope != "project":
            raise PreviewFault(3, "scope_unavailable", "This slice supports config apply previews only for --scope project.")
        target = _validate_target(source, args.target)
        response["context"]["target"] = str(target)

        for surface in (".opencode", ".codex"):
            path, metadata, issue = _lstat_target_path(target, surface)
            if issue:
                return _blocked(response, [{"code": "unsafe_target_path", "message": issue, "path": surface}])
            if metadata is not None and not stat.S_ISDIR(metadata.st_mode):
                return _blocked(response, [{
                    "code": "unsafe_target_path",
                    "message": f"Harness destination is not a directory: {surface}",
                    "path": surface,
                }])

        record, manifest_raw, blockers = _manifest_record(target)
        if blockers or record is None or manifest_raw is None:
            return _blocked(response, blockers or [{"code": "manifest_missing", "message": "No verifiable project manifest was found."}])

        selected = ("opencode", "codex") if args.harness == "all" else (args.harness,)
        installed = record.installed_harnesses
        if any(name not in installed for name in selected):
            absent = [name for name in selected if name not in installed]
            return _blocked(response, [{
                "code": "harness_not_installed",
                "message": "Preview cannot install or adopt an absent harness: " + ", ".join(absent),
            }], {
                **_blank_data(),
                "installed_harnesses": list(installed),
                "selected_harnesses": list(selected),
                "manifest": {"path": record.relative_path, "ownership": "metadata_only"},
            })

        selector = "all" if len(installed) == 2 else installed[0]
        source_data, source_issues = source_query(source, "config check", selector)
        if source_issues:
            source_blockers = [
                {"code": "source_output_drift", "message": item["message"], **({"path": item["path"]} if item.get("path") else {})}
                for item in source_issues
            ]
            return _blocked(response, source_blockers, {
                **_blank_data(),
                "installed_harnesses": list(installed),
                "selected_harnesses": list(selected),
                "source_coherent": False,
                "manifest": {"path": record.relative_path, "ownership": "metadata_only"},
            })

        try:
            source_version = release_version(source)
            renderer = load_renderer(source)
            by_harness = _render_managed_outputs(source, renderer, installed)
        except PreviewFault:
            raise
        except (OSError, UnicodeError, KeyError, TypeError, ValueError, AttributeError) as error:
            raise PreviewFault(1, "source_invalid", f"Cannot render a valid project preview from the selected source: {error}") from error

        expected_by_harness = {name: by_harness[name] for name in installed}
        expected_paths = {path for resources in expected_by_harness.values() for path in resources}
        entries, entry_blockers = _manifest_entries(record, expected_paths)
        if entry_blockers:
            return _blocked(response, entry_blockers, {
                **_blank_data(),
                "installed_harnesses": list(installed),
                "selected_harnesses": list(selected),
                "source_version": source_version,
                "source_coherent": bool(source_data.get("coherent")),
                "manifest": {"path": record.relative_path, "ownership": "unverified_inventory"},
            })

        conflicts: list[dict[str, str]] = []
        current: dict[str, bytes] = {}
        for relative in sorted(expected_paths):
            raw, issue = _read_target_file(target, relative)
            if issue:
                conflicts.append({"code": "unsafe_or_unreadable_managed_file", "message": issue, "path": relative})
                continue
            if raw is None:
                conflicts.append({"code": "managed_file_missing", "message": f"Manifest-owned resource is missing: {relative}", "path": relative})
                continue
            current[relative] = raw
            actual_hash = _digest(raw)
            if actual_hash != entries[relative]:
                conflicts.append({
                    "code": "managed_file_drift",
                    "message": f"Manifest-owned resource differs from its recorded SHA-256: {relative}",
                    "path": relative,
                })

        if "opencode" in selected:
            for relative in (*_OPEN_CODE_FOREIGN_CONFIGS, *_RETIRED_OPEN_CODE_AGENTS):
                exists, issue = _existing_path_issue(target, relative)
                if issue:
                    conflicts.append({"code": "unsafe_or_conflicting_destination", "message": issue, "path": relative})
                elif exists:
                    conflicts.append({
                        "code": "unowned_destination_conflict",
                        "message": f"OpenCode has a conflicting or retired unowned destination: {relative}",
                        "path": relative,
                    })

        if conflicts:
            return _blocked(response, conflicts, {
                **_blank_data(),
                "installed_harnesses": list(installed),
                "selected_harnesses": list(selected),
                "source_version": source_version,
                "source_coherent": bool(source_data.get("coherent")),
                "manifest": {
                    "path": record.relative_path,
                    "sha256": _digest(manifest_raw),
                    "ownership": "not_verified_due_to_conflict",
                },
            })

        changes: list[dict[str, str]] = []
        unchanged: list[dict[str, str]] = []
        preserved_resources: list[dict[str, str]] = []
        for harness in installed:
            for relative, desired in sorted(expected_by_harness[harness].items()):
                raw = current[relative]
                if harness not in selected:
                    preserved_resources.append({"path": relative, "harness": harness})
                elif raw == desired:
                    unchanged.append({"path": relative, "sha256": _digest(raw)})
                else:
                    changes.append({
                        "path": relative,
                        "action": "update",
                        "current_sha256": _digest(raw),
                        "proposed_sha256": _digest(desired),
                    })

        metadata_differences = []
        if record.installed_version != source_version:
            metadata_differences.append({
                "field": "installed_version",
                "current": record.installed_version,
                "source_release_marker": source_version,
            })
        preserved_harnesses = [name for name in installed if name not in selected]
        response["result"] = "ok" if changes or metadata_differences else "no_changes"
        response["data"] = {
            "preview_only": True,
            "apply_available": False,
            "preview_state": "ready" if changes or metadata_differences else "no_changes",
            "source_version": source_version,
            "installed_harnesses": list(installed),
            "selected_harnesses": list(selected),
            "changes": changes,
            "unchanged": unchanged,
            "preserved": {"harnesses": preserved_harnesses, "resources": preserved_resources},
            "manifest": {
                "path": record.relative_path,
                "sha256": _digest(manifest_raw),
                "recorded_version": record.installed_version,
                "recorded_source_commit": record.installed_from_commit,
                "ownership": "managed_paths_and_hashes_match",
                "write_planned": False,
                "metadata_differences": metadata_differences,
                "managed_hashes_to_refresh_if_applied": [item["path"] for item in changes],
            },
            "source_coherent": bool(source_data.get("coherent")),
            "checks": [
                "absolute target is an existing Git worktree root",
                "project manifest schema, location, scope, and harness inventory are valid",
                "manifest inventory matches the current renderer-managed file set",
                "all manifest-owned files are regular, unlinked, and match recorded hashes",
                "selected output conflicts and retired OpenCode destinations are absent",
            ],
            "conflicts": [],
            "execution": "not_implemented; this command performs no target writes",
        }
        return 0
    except PreviewFault as error:
        return _failed(response, error)


def emit_preview(response: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(response, ensure_ascii=False))
        return
    print(f"{response['operation']}: {response['result']}")
    for key, value in response["context"].items():
        print(f"{key}: {value}")
    data = response["data"]
    print(f"preview_state: {data.get('preview_state', 'blocked')}")
    print(f"execution: {data.get('execution', 'not implemented; no target writes')}")
    for key in ("source_version", "installed_harnesses", "selected_harnesses", "manifest"):
        if key in data:
            print(f"{key}: {json.dumps(data[key], ensure_ascii=False)}")
    for key, label in (("changes", "resources_to_update"), ("unchanged", "resources_unchanged")):
        print(f"{label}:")
        for item in data.get(key, []):
            print(f"  - {item['path']}" + (f" ({item['action']})" if "action" in item else ""))
        if not data.get(key):
            print("  (none)")
    preserved = data.get("preserved", {})
    print(f"harnesses_preserved: {json.dumps(preserved.get('harnesses', []), ensure_ascii=False)}")
    if preserved.get("resources"):
        print("resources_preserved:")
        for item in preserved["resources"]:
            print(f"  - {item['path']}")
    for issue in response["issues"]:
        print(f"{issue['code']}: {issue['message']}", file=sys.stderr)
