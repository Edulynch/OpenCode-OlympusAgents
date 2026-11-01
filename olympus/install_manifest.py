"""Shared read-only parsing for project installation ownership manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANIFEST_PATHS = (
    ".opencode/orchestrator-install.json",
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
    metadata_format: str


def manifest_paths(target: Path) -> tuple[Path, Path]:
    return target / MANIFEST_PATHS[0], target / MANIFEST_PATHS[1]


def manifest_present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def parse_project_manifest(target: Path, path: Path, raw: bytes) -> ProjectManifest:
    relative = next((item for item in MANIFEST_PATHS if target / item == path), None)
    if relative is None:
        raise ManifestError("invalid_location", f"Unsupported project manifest location: {path}")
    try:
        if not path.resolve().is_relative_to(target):
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
    if manifest.get("scope", "project") != "project":
        raise ManifestError("invalid_scope", f"Contradictory project manifest scope at {path}", blocked=True)

    # Contract: optional object<string, object>, with per-harness contents opaque.
    # Schema 1 remains backward compatible: absence means unknown provenance;
    # provenance is descriptive only, never ownership, and no official origin is inferred.
    if "harness_provenance" in manifest:
        provenance = manifest["harness_provenance"]
        if (not isinstance(provenance, dict)
                or any(not isinstance(name, str) or not name.strip() or not isinstance(value, dict)
                       for name, value in provenance.items())):
            raise ManifestError(
                "invalid_provenance",
                f"Invalid harness_provenance metadata at {path}; expected an object of per-harness objects",
            )

    installed = manifest.get("installed_harnesses", ["opencode"])
    if (not isinstance(installed, list) or not installed
            or any(not isinstance(value, str) or value not in ("opencode", "codex") for value in installed)
            or len(installed) != len(set(installed))):
        raise ManifestError("invalid_harnesses", f"Invalid installed_harnesses metadata at {path}")
    expected_location = MANIFEST_PATHS[0] if "opencode" in installed else MANIFEST_PATHS[1]
    if relative != expected_location:
        raise ManifestError(
            "invalid_location",
            f"Manifest location contradicts its reported harness inventory: {path}",
            blocked=True,
        )

    version = manifest.get("installed_version", "unknown")
    commit = manifest.get("installed_from_commit", "unknown")
    if not isinstance(version, str) or not version or not isinstance(commit, str):
        raise ManifestError("invalid_release_metadata", f"Invalid recorded release metadata at {path}")
    return ProjectManifest(
        path=path,
        relative_path=relative,
        data=manifest,
        installed_harnesses=tuple(installed),
        installed_version=version,
        installed_from_commit=commit,
        metadata_format="legacy" if "installed_harnesses" not in manifest else "current",
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
        if not path.resolve().is_relative_to(target):
            raise ManifestError("escaped", f"Manifest escapes the selected target: {path}", blocked=True)
    except (OSError, RuntimeError) as error:
        raise ManifestError("unreadable", f"Cannot resolve installation metadata at {path}: {error}") from error
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ManifestError("unreadable", f"Cannot read installation metadata at {path}: {error}") from error
    return parse_project_manifest(target, path, raw)
