"""Shared read-only parsing for project installation ownership manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANIFEST_PATHS = (
    ".opencode/orchestrator-install.json",
    # Include this location so unsupported manifests here are detected and refused.
    ".codex/orchestrator-install.json",
)


class ManifestError(ValueError):
    def __init__(self, code: str, message: str, *, blocked: bool = False):
        super().__init__(message)
        self.code = code
        self.blocked = blocked


@dataclass(frozen=True, slots=True)
class ProjectManifest:
    path: Path
    relative_path: str
    data: dict[str, Any]
    installed_harnesses: tuple[str, ...]
    installed_version: str
    installed_from_commit: str


def manifest_paths(target: Path) -> tuple[Path, Path]:
    return target / MANIFEST_PATHS[0], target / MANIFEST_PATHS[1]


def manifest_present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _manifest_is_within_target(target: Path, path: Path) -> bool:
    # Resolve both sides before comparing. On Windows this canonicalizes 8.3
    # aliases; on macOS it normalizes aliases such as /var -> /private/var.
    canonical_target = target.resolve()
    canonical_path = path.resolve()
    return canonical_path.is_relative_to(canonical_target)


def parse_project_manifest(target: Path, path: Path, raw: bytes) -> ProjectManifest:
    relative = next((item for item in MANIFEST_PATHS if target / item == path), None)
    if relative is None:
        raise ManifestError("invalid_location", f"Unsupported project manifest location: {path}")
    try:
        if not _manifest_is_within_target(target, path):
            raise ManifestError("escaped", f"Manifest escapes the selected target: {path}", blocked=True)
    except (OSError, RuntimeError) as error:
        raise ManifestError("unreadable", f"Cannot resolve installation metadata at {path}: {error}") from error
    try:
        manifest = json.loads(raw.decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ManifestError("invalid_json", f"Cannot read installation metadata at {path}: {error}") from error
    if (not isinstance(manifest, dict)
            or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != 1
            or not isinstance(manifest.get("managed_files"), list)):
        raise ManifestError("invalid_schema", f"Unsupported manifest schema or managed_files at {path}")
    if manifest.get("scope") != "project":
        raise ManifestError("invalid_scope", f"Contradictory project manifest scope at {path}", blocked=True)

    # Contract: optional object<string, object>, with per-harness contents opaque.
    # Optional descriptive metadata never establishes ownership or official origin.
    if "harness_provenance" in manifest:
        provenance = manifest["harness_provenance"]
        if (not isinstance(provenance, dict)
                or any(not isinstance(name, str) or not name.strip() or not isinstance(value, dict)
                       for name, value in provenance.items())):
            raise ManifestError(
                "invalid_provenance",
                f"Invalid harness_provenance metadata at {path}; expected an object of per-harness objects",
            )

    installed = manifest.get("installed_harnesses")
    if installed != ["opencode"]:
        raise ManifestError("invalid_harnesses", f"Invalid installed_harnesses metadata at {path}")
    if relative != MANIFEST_PATHS[0]:
        raise ManifestError(
            "invalid_location",
            f"Manifest location contradicts its reported harness inventory: {path}",
            blocked=True,
        )

    version = manifest.get("installed_version")
    commit = manifest.get("installed_from_commit")
    if (not isinstance(version, str) or not version
            or not isinstance(commit, str) or not commit):
        raise ManifestError("invalid_release_metadata", f"Invalid recorded release metadata at {path}")
    entries = manifest["managed_files"]
    seen: set[str] = set()
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != {"path", "sha256"}
                or not isinstance(entry["path"], str) or not entry["path"]
                or "\\" in entry["path"] or entry["path"].startswith("/")
                or any(part in ("", ".", "..") for part in entry["path"].split("/"))
                or not isinstance(entry["sha256"], str)
                or len(entry["sha256"]) != 64
                or any(character not in "0123456789abcdefABCDEF" for character in entry["sha256"])):
            raise ManifestError("invalid_inventory", f"Invalid managed_files entry at {path}")
        managed_path = entry["path"]
        folded = managed_path.casefold()
        if folded in seen:
            raise ManifestError("invalid_inventory", f"Duplicate managed_files path at {path}: {managed_path}")
        if managed_path.startswith(".codex/") or managed_path == "CODEX.md":
            raise ManifestError("invalid_inventory", f"Obsolete Codex inventory is unsupported at {path}: {managed_path}")
        seen.add(folded)
    if not entries:
        raise ManifestError("invalid_inventory", f"Empty managed_files inventory at {path}")
    return ProjectManifest(
        path=path,
        relative_path=relative,
        data=manifest,
        installed_harnesses=tuple(installed),
        installed_version=version,
        installed_from_commit=commit,
    )


def read_project_manifest(target: Path) -> ProjectManifest | None:
    paths = manifest_paths(target)
    present = [path for path in paths if manifest_present(path)]
    if not present:
        return None
    if len(present) != 1:
        raise ManifestError(
            "contradictory",
            "Both project manifest locations exist; reported ownership metadata is ambiguous",
            blocked=True,
        )
    path = present[0]
    try:
        if not _manifest_is_within_target(target, path):
            raise ManifestError("escaped", f"Manifest escapes the selected target: {path}", blocked=True)
    except (OSError, RuntimeError) as error:
        raise ManifestError("unreadable", f"Cannot resolve installation metadata at {path}: {error}") from error
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ManifestError("unreadable", f"Cannot read installation metadata at {path}: {error}") from error
    return parse_project_manifest(target, path, raw)
