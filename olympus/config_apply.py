"""Preview and explicitly apply updates to an existing project installation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tomllib
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
_MAX_MANIFEST_BYTES = 2_000_000
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


def _read_target_file(target: Path, relative: str, *, max_bytes: int | None = None) -> tuple[bytes | None, str | None]:
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
            raw = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
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
        raw, issue = _read_target_file(target, relative, max_bytes=_MAX_MANIFEST_BYTES)
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
    if len(raw) > _MAX_MANIFEST_BYTES:
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
        "apply_available": True,
        "preview_state": "blocked",
        "assignments": _unknown_assignments(),
        "changes": [],
        "unchanged": [],
        "preserved": {"harnesses": [], "resources": []},
        "conflicts": [],
        "checks": [],
    }


def _unknown_assignments() -> dict[str, Any]:
    return {
        "status": "unknown",
        "evidence": "not_verified",
        "family": "unknown",
        "proposal_source": "unknown",
        "roles": [],
        "roots": {
            "opencode": {"state": "unknown", "current_status": "unknown", "current": None, "proposed": None},
            "codex": {"state": "unknown", "current_status": "unknown", "current": None, "proposed": None},
        },
    }


_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]*\Z")


def _opencode_scalar(value: str) -> dict[str, str] | None:
    if (len(value) < 3 or not value.startswith('"') or not value.endswith('"')
            or "\\" in value):
        return None
    value = value[1:-1]
    parts = value.split("#")
    if len(parts) > 2 or not _MODEL_ID.fullmatch(parts[0]):
        return None
    if len(parts) == 2 and not _MODEL_ID.fullmatch(parts[1]):
        return None
    return {"model": parts[0], **({"effort": parts[1]} if len(parts) == 2 else {})}


def _frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    closing = text.find("\n---\n", 4)
    return text[:closing + 5] if closing >= 0 else None


def _verified_opencode_agent(raw: bytes, expected: bytes) -> dict[str, str] | None:
    try:
        actual_text, expected_text = raw.decode("utf-8"), expected.decode("utf-8")
    except UnicodeError:
        return None
    actual, template = _frontmatter(actual_text), _frontmatter(expected_text)
    if actual is None or template is None:
        return None
    pattern = re.compile(r"(?m)^model: ([^\r\n]*)$")
    actual_matches, template_matches = list(pattern.finditer(actual)), list(pattern.finditer(template))
    if len(actual_matches) != 1 or len(template_matches) != 1:
        return None
    assignment = _opencode_scalar(actual_matches[0].group(1))
    if assignment is None or actual[:actual_matches[0].start(1)] != template[:template_matches[0].start(1)]:
        return None
    if actual[actual_matches[0].end(1):] != template[template_matches[0].end(1):]:
        return None
    return assignment


def _verified_opencode_root(raw: bytes, expected: bytes) -> dict[str, str] | None:
    try:
        actual_text, template_text = raw.decode("utf-8"), expected.decode("utf-8")
    except UnicodeError:
        return None
    pattern = re.compile(r'(?m)^  "model": ("(?:[^"\\]|\\.)*"),$')
    actual_matches, template_matches = list(pattern.finditer(actual_text)), list(pattern.finditer(template_text))
    if len(actual_matches) != 1 or len(template_matches) != 1:
        return None
    actual_literal = actual_matches[0].group(1)
    try:
        model = json.loads(actual_literal)
    except json.JSONDecodeError:
        return None
    if (not isinstance(model, str) or json.dumps(model, ensure_ascii=False) != actual_literal
            or not _MODEL_ID.fullmatch(model)):
        return None
    actual_rebuilt = actual_text[:actual_matches[0].start(1)] + template_matches[0].group(1) + actual_text[actual_matches[0].end(1):]
    template_rebuilt = template_text[:template_matches[0].start(1)] + template_matches[0].group(1) + template_text[template_matches[0].end(1):]
    if actual_rebuilt != template_rebuilt:
        return None
    return {"model": model}


def _verified_codex(raw: bytes) -> dict[str, str] | None:
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError):
        return None
    model, effort = data.get("model"), data.get("model_reasoning_effort")
    if (not isinstance(model, str) or not _MODEL_ID.fullmatch(model)
            or not isinstance(effort, str) or not _MODEL_ID.fullmatch(effort)):
        return None
    return {"model": model, "effort": effort}


def _assignment_preview(installed: tuple[str, ...], selected: tuple[str, ...], current: dict[str, bytes],
                        expected_by_harness: dict[str, dict[str, bytes]], renderer, source: Path,
                        assignment_query: Callable | None) -> dict[str, Any]:
    result = _unknown_assignments()
    if assignment_query is None:
        return result
    try:
        canonical = assignment_query(renderer, source) if assignment_query is not None else None
        rows = canonical.get("roles") if isinstance(canonical, dict) else None
        if not isinstance(rows, list):
            return result
        by_role = {row["role"]: row for row in rows if isinstance(row, dict) and isinstance(row.get("role"), str)}
        if not rows or len(by_role) != len(rows):
            return result
    except Exception:
        return result

    def state_for(harness: str) -> str:
        return "not_installed" if harness not in installed else "selected" if harness in selected else "preserved"

    def current_for(harness: str, relative: str, root: bool = False) -> tuple[str, dict[str, str] | None]:
        if harness not in installed:
            return "not_installed", None
        raw, expected = current.get(relative), expected_by_harness.get(harness, {}).get(relative)
        if raw is None or expected is None:
            return "unsupported", None
        if harness == "opencode":
            value = (_verified_opencode_root(raw, expected) if root
                     else _verified_opencode_agent(raw, expected))
        else:
            value = _verified_codex(raw)
        return ("verified", value) if value is not None else ("unsupported", None)

    roles: list[dict[str, Any]] = []
    statuses: list[str] = []
    for role in sorted(by_role):
        row = by_role[role]
        representations: dict[str, Any] = {}
        for harness in ("opencode", "codex"):
            representation = row.get("representation", {}).get(harness, "unknown")
            state = state_for(harness)
            if harness == "codex" and representation == "root":
                representations[harness] = {"representation": "root", "state": state}
                continue
            relative = (f".opencode/agents/{role}.md" if harness == "opencode"
                        else f".codex/agents/{role}.toml")
            current_status, current_value = current_for(harness, relative)
            if harness in installed:
                statuses.append(current_status)
            models = row.get("models", {})
            proposed = ({"model": models.get(harness), "effort": row.get("effort")}
                        if harness in selected and isinstance(models, dict) else None)
            representations[harness] = {
                "representation": representation,
                "state": state,
                "current_status": current_status,
                "current": current_value,
                "proposed": proposed,
            }
        proposed_family = row.get("family") if any(harness in selected for harness in installed) else None
        roles.append({
            "role": role,
            "identity": row.get("identity"),
            "family": {"current": "unknown", "proposed": proposed_family},
            "harnesses": representations,
        })

    root_specs = {
        "opencode": ("opencode.jsonc", "opencode", "kael"),
        "codex": (".codex/config.toml", "codex", "kael"),
    }
    roots: dict[str, Any] = {}
    for harness, (relative, _, role) in root_specs.items():
        state = state_for(harness)
        current_status, current_value = current_for(harness, relative, root=True)
        if harness in installed:
            statuses.append(current_status)
        row = by_role.get(role, {})
        models = row.get("models", {}) if isinstance(row, dict) else {}
        proposed = None
        if harness in selected and isinstance(models, dict):
            proposed = {"model": models.get(harness)}
            if harness == "codex":
                proposed["effort"] = row.get("effort")
        roots[harness] = {
            "state": state,
            "current_status": current_status,
            "current": current_value,
            "proposed": proposed,
        }

    verified = statuses.count("verified")
    unsupported = statuses.count("unsupported")
    result.update({
        "status": "verified" if not unsupported else "partial" if verified else "unsupported",
        "evidence": "managed_hash_verified_bytes",
        "family": "unknown",
        "proposal_source": "canonical_renderer" if by_role else "unknown",
        "selected_harnesses": [item for item in installed if item in selected],
        "preserved_harnesses": [item for item in installed if item not in selected],
        "roles": roles,
        "roots": roots,
    })
    return result


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


def _updated_manifest_bytes(record: ProjectManifest, raw: bytes, selected: tuple[str, ...],
                            expected_by_harness: dict[str, dict[str, bytes]], source_commit: str) -> bytes:
    data = json.loads(raw.decode("utf-8-sig"))
    entries = []
    for original in data["managed_files"]:
        entry = dict(original)
        relative = entry["path"].replace("\\", "/")
        if relative.startswith(".opencode/") or relative == "opencode.jsonc":
            harness = "opencode"
        elif relative.startswith(".codex/") or relative == "CODEX.md":
            harness = "codex"
        else:
            raise PreviewFault(3, "unsupported_manifest_inventory", f"Unsupported manifest resource: {relative}")
        if harness in selected:
            content = expected_by_harness[harness].get(relative)
            if content is None:
                raise PreviewFault(3, "unsupported_manifest_inventory", f"Renderer omitted owned resource: {relative}")
            entry["sha256"] = _digest(content)
        entries.append(entry)
    data["managed_files"] = sorted(entries, key=lambda item: item["path"].replace("\\", "/"))
    provenance = data.get("harness_provenance")
    if isinstance(provenance, dict):
        retained = {name: value for name, value in provenance.items() if name not in selected}
        if retained:
            data["harness_provenance"] = retained
        else:
            data.pop("harness_provenance")
    # A local working checkout is not an immutable official release, even when
    # its installer marker has release-shaped text.
    data["installed_version"] = "local"
    data["installed_from_commit"] = source_commit
    if data == record.data:
        return raw
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def preview(source: Path, args, response: dict, *, source_query: Callable, load_renderer: Callable,
            release_version: Callable, assignment_query: Callable | None = None) -> int:
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

        from .config_apply_transaction import pending
        if pending(target):
            return _blocked(response, [{
                "code": "pending_project_apply",
                "message": "A project-apply or source-edit journal is pending; explicitly recover that writer state before applying.",
            }])

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

        assignments = _assignment_preview(
            installed, tuple(selected), current, expected_by_harness, renderer, source, assignment_query,
        )

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

        source_commit = "unknown"
        metadata_differences = []
        if record.installed_version != "local":
            metadata_differences.append({
                "field": "installed_version",
                "current": record.installed_version,
                "proposed": "local",
            })
        if record.installed_from_commit != source_commit:
            metadata_differences.append({
                "field": "installed_from_commit",
                "current": record.installed_from_commit,
                "proposed": source_commit,
            })
        proposed_manifest = _updated_manifest_bytes(
            record, manifest_raw, selected, expected_by_harness, source_commit,
        )
        manifest_write_planned = proposed_manifest != manifest_raw
        preserved_harnesses = [name for name in installed if name not in selected]
        response["result"] = "ok" if changes or manifest_write_planned else "no_changes"
        response["data"] = {
            "preview_only": True,
            "apply_available": True,
            "preview_state": "ready" if changes or manifest_write_planned else "no_changes",
            "source_version": source_version,
            "source_provenance": "local_checkout",
            "source_commit": source_commit,
            "installed_harnesses": list(installed),
            "selected_harnesses": list(selected),
            "assignments": assignments,
            "changes": changes,
            "unchanged": unchanged,
            "preserved": {"harnesses": preserved_harnesses, "resources": preserved_resources},
            "manifest": {
                "path": record.relative_path,
                "sha256": _digest(manifest_raw),
                "recorded_version": record.installed_version,
                "recorded_source_commit": record.installed_from_commit,
                "ownership": "managed_paths_and_hashes_match",
                "proposed_version": "local",
                "proposed_source_commit": source_commit,
                "proposed_sha256": _digest(proposed_manifest),
                "write_planned": manifest_write_planned,
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
            "execution": "not_run; no target writes (use --execute to apply)",
        }
        return 0
    except PreviewFault as error:
        return _failed(response, error)


def _execution_plan(source: Path, args, response: dict, *, load_renderer: Callable):
    from .config_apply_transaction import Change

    target = Path(response["context"]["target"])
    record, manifest_raw, blockers = _manifest_record(target)
    if blockers or record is None or manifest_raw is None:
        raise PreviewFault(3, "target_changed", "Project ownership changed after preview; no writes were made.")
    selected = ("opencode", "codex") if args.harness == "all" else (args.harness,)
    try:
        renderer = load_renderer(source)
        by_harness = _render_managed_outputs(source, renderer, record.installed_harnesses)
    except PreviewFault:
        raise
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, AttributeError) as error:
        raise PreviewFault(1, "source_invalid", f"Cannot prepare project apply from the selected source: {error}") from error

    resource_changes = []
    for harness in record.installed_harnesses:
        if harness not in selected:
            continue
        for relative, desired in sorted(by_harness[harness].items()):
            old, issue = _read_target_file(target, relative)
            if issue or old is None:
                raise PreviewFault(3, "target_changed", issue or f"Managed resource disappeared: {relative}")
            if old == desired:
                continue
            path, metadata, path_issue = _lstat_target_path(target, relative)
            if path_issue or metadata is None or path is None:
                raise PreviewFault(3, "target_changed", path_issue or f"Cannot inspect managed resource: {relative}")
            resource_changes.append(Change(relative, old, desired, stat.S_IMODE(metadata.st_mode)))

    source_commit = "unknown"
    manifest_new = _updated_manifest_bytes(record, manifest_raw, selected, by_harness, source_commit)
    manifest_path = record.relative_path
    if manifest_new != manifest_raw:
        old, issue = _read_target_file(target, manifest_path)
        path, metadata, path_issue = _lstat_target_path(target, manifest_path)
        if issue or old is None or path_issue or metadata is None or path is None:
            raise PreviewFault(3, "target_changed", issue or path_issue or "Project manifest changed after preview.")
        resource_changes.sort(key=lambda item: item.path)
        resource_changes.append(Change(manifest_path, old, manifest_new, stat.S_IMODE(metadata.st_mode)))

    planned = {item["path"]: item for item in response["data"].get("changes", [])}
    actual = {item.path: {"current_sha256": _digest(item.old), "proposed_sha256": _digest(item.new)}
              for item in resource_changes if item.path != manifest_path}
    if (set(planned) != set(actual)
            or any(planned[path].get("current_sha256") != values["current_sha256"]
                   or planned[path].get("proposed_sha256") != values["proposed_sha256"]
                   for path, values in actual.items())
            or response["data"]["manifest"].get("proposed_sha256") != _digest(manifest_new)):
        raise PreviewFault(3, "target_changed", "Project plan changed after preview; no writes were made.")
    return tuple(resource_changes), manifest_path, manifest_raw, manifest_new


def _plan_fingerprint(response: dict) -> tuple:
    data = response["data"]
    manifest = data.get("manifest", {})
    return (
        tuple((item["path"], item["current_sha256"], item["proposed_sha256"])
              for item in data.get("changes", [])),
        manifest.get("proposed_sha256"),
        tuple(data.get("selected_harnesses", [])),
    )


def execute(source: Path, args, response: dict, *, source_query: Callable, load_renderer: Callable,
            release_version: Callable, assignment_query: Callable) -> int:
    """Explicitly apply one previewed project plan under the shared target lock."""
    from . import config_apply_transaction as transaction
    from . import source_edit

    code = preview(source, args, response, source_query=source_query,
                   load_renderer=load_renderer, release_version=release_version,
                   assignment_query=assignment_query)
    if code:
        emit_preview(response, False)
        return code
    preview_printed = False
    try:
        changes, manifest_path, manifest_old, manifest_new = _execution_plan(
            source, args, response, load_renderer=load_renderer,
        )
        if not changes:
            response["result"] = "no_changes"
            response["data"]["preview_state"] = "no_changes"
            response["data"]["preview_only"] = False
            response["data"]["execution"] = "no_changes"
            emit_preview(response, False)
            print("execution: no_changes")
            return 0

        before = _plan_fingerprint(response)
        print("Execution preview (not yet applied):")
        emit_preview(response, False)
        preview_printed = True

        def revalidate():
            latest = {"schema_version": 1, "operation": "config apply", "result": "ok",
                      "context": {}, "data": {}, "issues": []}
            latest_code = preview(source, args, latest, source_query=source_query,
                                  load_renderer=load_renderer, release_version=release_version,
                                  assignment_query=assignment_query)
            if latest_code:
                raise transaction.TransactionError(
                    "Locked project revalidation failed: " + "; ".join(item["message"] for item in latest["issues"]),
                    latest_code,
                )
            if _plan_fingerprint(latest) != before:
                raise transaction.TransactionError("Project state changed after preview; rerun config apply --dry-run.", 3)
            latest_changes, latest_manifest_path, latest_old, latest_new = _execution_plan(
                source, args, latest, load_renderer=load_renderer,
            )
            if latest_manifest_path != manifest_path:
                raise transaction.TransactionError("Project manifest location changed after preview.", 3)
            return latest_changes, latest_old, latest_new

        state = transaction.commit(
            Path(response["context"]["target"]), source, changes, manifest_path,
            manifest_old, manifest_new, revalidate,
        )
        if state == "no_changes":
            response["result"] = "no_changes"
            response["data"]["execution"] = "no_changes"
            response["data"]["preview_only"] = False
            print("execution: no_changes")
            return 0
        response["result"] = "ok"
        response["data"]["preview_state"] = "applied"
        response["data"]["preview_only"] = False
        response["data"]["execution"] = "committed"
        response["data"]["manifest"]["write_planned"] = False
        response["data"]["manifest"]["sha256"] = _digest(manifest_new)
        response["data"]["manifest"]["recorded_version"] = "local"
        response["data"]["manifest"]["recorded_source_commit"] = response["data"]["source_commit"]
        response["data"]["manifest"]["ownership"] = "managed_paths_and_hashes_match"
        print("execution: committed")
        return 0
    except PreviewFault as error:
        code = _failed(response, error)
        if not preview_printed:
            emit_preview(response, False)
        else:
            print(f"config apply: {response['result']}", file=sys.stderr)
            print(str(error), file=sys.stderr)
        return code
    except transaction.TransactionError as error:
        response["result"] = {1: "failed", 3: "blocked", 4: "unconfirmed"}.get(error.code, "failed")
        response["data"]["execution"] = (
            "rollback_confirmed" if "rollback was confirmed" in str(error)
            or "no target writes occurred" in str(error) else "unconfirmed"
        )
        response["issues"] = [{"code": response["result"], "message": str(error)}]
        if preview_printed:
            print(f"config apply: {response['result']}", file=sys.stderr)
            print(str(error), file=sys.stderr)
        else:
            emit_preview(response, False)
        return error.code
    except (OSError, UnicodeError, source_edit.BatchError, source_edit.LockError) as error:
        response["result"] = "unconfirmed"
        response["data"]["execution"] = "unconfirmed"
        response["issues"] = [{"code": "unconfirmed", "message": str(error)}]
        if preview_printed:
            print("config apply: unconfirmed", file=sys.stderr)
            print(str(error), file=sys.stderr)
        else:
            emit_preview(response, False)
        return 4


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
    if "assignments" in data:
        print(f"assignments: {json.dumps(data['assignments'], ensure_ascii=False)}")
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
