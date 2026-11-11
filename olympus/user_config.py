"""Per-user model overrides consumed by the managed global OpenCode agents."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path

from . import models_catalog


class UserConfigError(ValueError):
    """The per-user override file or managed OpenCode target is invalid."""


_MANIFEST = "olympus/orchestrator-install.json"
_PROJECT_CONFIG = ".opencode/olympus-config.json"
_HASH = re.compile(r"[0-9a-fA-F]{64}\Z")
_AGENT_MODEL = re.compile(r'(?m)^model:\s*(?:"([^"]+)"|([^\r\n]+))\s*$')


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
    elif os.environ.get("APPDATA"):
        root = Path(os.environ["APPDATA"]) / "Olympus"
    elif os.environ.get("XDG_CONFIG_HOME"):
        root = Path(os.environ["XDG_CONFIG_HOME"]) / "olympus"
    else:
        root = Path.home() / ".config" / "olympus"
    if not root.is_absolute():
        raise UserConfigError("The Olympus user configuration directory must be absolute.")
    return root / "config.json"


def _managed_project(source: Path, cwd: Path | None = None) -> Path | None:
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
            if not path.exists():
                return {"schema_version": 1, "overrides": {}}
            if path.is_symlink() or not path.is_file():
                raise UserConfigError(f"Olympus user configuration is not a regular file: {path}")
            text = path.read_text(encoding="utf-8")
        value = json.loads(text, object_pairs_hook=_unique_object)
    except UserConfigError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise UserConfigError(f"Olympus configuration is not valid JSON: {path}: {error}") from error
    rows = _canonical_rows(source)
    roles = {row["role"] for row in rows}
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1 or not isinstance(value.get("overrides"), dict)
            or set(value) != {"schema_version", "overrides"}):
        raise UserConfigError(f"Olympus user configuration must contain schema_version 1 and an overrides object: {path}")
    for role, override in value["overrides"].items():
        if role not in roles or not isinstance(override, dict) or not override or set(override) - {"model", "effort"}:
            raise UserConfigError(f"Invalid Olympus override for role '{role}' in {path}.")
        if any(not isinstance(item, str) or not item for item in override.values()):
            raise UserConfigError(f"Override values for '{role}' must be non-empty strings in {path}.")
    return value


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


def apply_to_expected(source: Path, expected: dict[str, bytes]) -> None:
    """Make read-only verification compare installed agents with user overrides."""
    rows = {row["role"]: row for row in _canonical_rows(source)}
    config = read_config(source)
    for role, override in config["overrides"].items():
        if role not in rows:
            raise UserConfigError(f"Unknown Olympus role '{role}' in {config_path()}.")
        model = override.get("model", rows[role]["models"]["opencode"])
        effort = override.get("effort", rows[role]["effort"])
        models_catalog.validate_assignment(model, effort, source)
        relative = f"agents/{role}.md"
        if relative not in expected:
            raise UserConfigError(f"The OpenCode renderer does not manage expected agent {role}.")
        expected[relative] = _replace_agent_model(expected[relative], model, effort, role)


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _prepare_installed_update(source: Path, role: str, model: str, effort: str,
                              scope: str, target: Path | None):
    from . import config_apply, global_readonly

    try:
        if scope == "project":
            if target is None:
                raise UserConfigError("Project override requires a managed project target.")
            root, manifest_relative = target, ".opencode/orchestrator-install.json"
            raw_manifest, issue = config_apply._read_target_file(root, manifest_relative)
            if issue or raw_manifest is None:
                raise UserConfigError("The project Olympus ownership manifest is unavailable; no configuration was changed.")
        else:
            root = global_readonly.resolve_roots(("opencode",))["opencode"]
            manifest_relative = _MANIFEST
            raw_manifest = global_readonly._read(root, manifest_relative)
            if raw_manifest is None:
                return None
    except global_readonly.GlobalFault as error:
        if error.reason == "global_path_unavailable" and scope == "global":
            return None
        raise UserConfigError(str(error)) from error

    try:
        manifest = json.loads(raw_manifest.decode("utf-8"), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError) as error:
        raise UserConfigError("The installed OpenCode ownership manifest is invalid; no files were changed.") from error
    expected_scope = "project" if scope == "project" else "global"
    if not isinstance(manifest, dict):
        raise UserConfigError("The installed OpenCode ownership manifest is unsupported; no files were changed.")
    harnesses = manifest.get("installed_harnesses", ["opencode"] if scope == "project" else None)
    if (manifest.get("schema_version") != 1
            or (manifest.get("scope") != "global" if scope == "global" else manifest.get("scope", "project") != "project")
            or not isinstance(harnesses, list) or "opencode" not in harnesses
            or (scope == "global" and harnesses != ["opencode"])
            or not isinstance(manifest.get("managed_files"), list)):
        raise UserConfigError("The installed OpenCode ownership manifest is unsupported; no files were changed.")

    relative = f"agents/{role}.md"
    owned_relative = f".opencode/{relative}" if scope == "project" else relative
    entries = [entry for entry in manifest["managed_files"]
               if isinstance(entry, dict) and entry.get("path") == owned_relative]
    if len(entries) != 1 or not isinstance(entries[0].get("sha256"), str) or not _HASH.fullmatch(entries[0]["sha256"]):
        raise UserConfigError(f"The installed Olympus manifest does not manage {role}; no configuration was changed.")
    if scope == "project":
        from . import config_apply

        current, issue = config_apply._read_target_file(root, f".opencode/{relative}")
        if issue:
            raise UserConfigError(f"The project-managed {role} agent is unsafe; no configuration was changed.")
    else:
        current = global_readonly._read(root, relative)
    if current is None or hashlib.sha256(current).hexdigest() != entries[0]["sha256"].lower():
        raise UserConfigError(f"Managed OpenCode agent {role} was changed outside Olympus; preserve it and run olympus doctor.")
    updated = _replace_agent_model(current, model, effort, role)
    entries[0]["sha256"] = hashlib.sha256(updated).hexdigest()
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    agent_path = root / (f".opencode/{relative}" if scope == "project" else relative)
    manifest_path = root / manifest_relative
    return agent_path, current, updated, manifest_path, raw_manifest, manifest_bytes


def _config_bytes(path: Path, scope: str, target: Path | None) -> bytes | None:
    if scope == "project":
        from . import config_apply

        raw, issue = config_apply._read_target_file(target, _PROJECT_CONFIG)
        if issue:
            raise UserConfigError(f"Unsafe project Olympus configuration: {issue}")
        return raw
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise UserConfigError(f"Olympus user configuration is not a regular file: {path}")
    return path.read_bytes()


def _commit_override(path: Path, encoded: bytes, scope: str, target: Path | None, installed) -> None:
    changes: list[tuple[Path, bytes | None]] = []
    config_before = _config_bytes(path, scope, target)
    try:
        if installed is not None:
            agent_path, current, updated, manifest_path, manifest_before, manifest_after = installed
            if updated != current:
                _write_atomic(agent_path, updated)
                changes.append((agent_path, current))
                if manifest_after != manifest_before:
                    _write_atomic(manifest_path, manifest_after)
                    changes.append((manifest_path, manifest_before))
        _write_atomic(path, encoded)
        changes.append((path, config_before))
    except BaseException as error:
        rollback_errors = []
        for changed_path, old in reversed(changes):
            try:
                if old is None:
                    changed_path.unlink(missing_ok=True)
                else:
                    _write_atomic(changed_path, old)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        if rollback_errors:
            raise UserConfigError("Configuration update failed and rollback could not be confirmed; inspect the affected files.") from error
        raise


def set_override(source: Path, role: str, field: str, value: str,
                 scope: str = "global", target: Path | None = None) -> tuple[Path, bool]:
    if field not in ("model", "effort"):
        raise UserConfigError(f"Unsupported override field: {field}")
    rows = {row["role"]: row for row in _canonical_rows(source)}
    if role not in rows:
        raise UserConfigError(f"Unknown Olympus agent '{role}'.")
    path = config_path(scope, target)
    lock = None
    if scope == "project":
        from . import config_apply, install_routing, source_edit

        try:
            target = install_routing._validate_project_target(source, target)
            record, _, blockers = config_apply._manifest_record(target)
            if blockers or record is None or "opencode" not in record.installed_harnesses:
                raise UserConfigError("The selected target is not a managed OpenCode project.")
            lock = source_edit._acquire_lock(target, create=True)
        except (source_edit.LockError, OSError) as error:
            raise UserConfigError(f"Cannot safely lock the managed project; no configuration was changed: {error}") from error
    try:
        if scope == "project":
            from . import config_apply_transaction

            if config_apply_transaction.pending(target):
                raise UserConfigError("A pending Olympus project edit blocks configuration changes; no files were changed.")
        config = read_config(source, scope, target)
        override = dict(config["overrides"].get(role, {}))
        override[field] = value
        global_override = read_config(source, "global")["overrides"].get(role, {}) if scope == "project" else {}
        effective_model = override.get("model", global_override.get("model", rows[role]["models"]["opencode"]))
        effective_effort = override.get("effort", global_override.get("effort", rows[role]["effort"]))
        try:
            models_catalog.validate_assignment(effective_model, effective_effort, source)
        except models_catalog.CatalogError as error:
            raise UserConfigError(str(error)) from error
        config["overrides"][role] = override
        encoded = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        installed = _prepare_installed_update(source, role, effective_model, effective_effort, scope, target)
        if scope == "project" and installed is None:
            raise UserConfigError("The project-managed OpenCode agent is unavailable; no configuration was changed.")
        _commit_override(path, encoded, scope, target, installed)
    finally:
        if lock is not None:
            from . import source_edit

            source_edit._release_lock(lock)
    applied = installed is not None
    return path.resolve(), applied


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
    sources.append({"layer": "global override", "path": str(global_path), "exists": global_path.is_file()})
    sources.append({"layer": "canonical default", "path": str(models_path), "exists": models_path.is_file()})
    return {
        "scope": scope, "precedence": (["project override"] if scope == "project" else []) +
        ["global override", "canonical default"],
        "sources": sources,
        "opencode_root_state": root_state, "managed_agent_paths": agent_paths,
        "roles": roles,
        "manual_edit_apply": "Apply manual edits with 'olympus install' (global) or 'olympus update' (project); doctor is read-only.",
        "manual_edit_reminder": "Run 'olympus doctor' after manual edits.",
    }


def diagnose(source: Path, scope: str = "global", target: Path | None = None) -> dict:
    roles = effective_roles(source, scope, target)
    return {
        "state": "valid", "scope": scope, "config_path": str(config_path(scope, target).resolve()),
        "catalog_path": str(models_catalog.catalog_path(source).resolve()),
        "models_checked": len(roles), "provider_access_checked": False,
    }
