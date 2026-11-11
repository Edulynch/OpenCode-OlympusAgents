"""Offline validation against the checked-in Models.dev capability snapshot."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from functools import lru_cache
from pathlib import Path


class CatalogError(ValueError):
    """A model or declared capability is not supported by the offline catalog."""


_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*/[A-Za-z0-9][A-Za-z0-9._:/-]*\Z")
_EFFORT = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")


def catalog_path(source: Path | None = None) -> Path:
    root = source if source is not None else Path(__file__).resolve().parents[1]
    return root / "olympus" / "core" / "models-dev.json"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate key: {key}")
        result[key] = value
    return result


@lru_cache(maxsize=4)
def load_catalog(path: str) -> dict:
    catalog_file = Path(path)
    try:
        data = json.loads(catalog_file.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError) as error:
        raise CatalogError(f"Cannot read the bundled Models.dev catalog at {catalog_file}: {error}") from error
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or not isinstance(data.get("models"), dict)):
        raise CatalogError(f"The bundled Models.dev catalog has an unsupported structure: {catalog_file}")
    return data


def validate_assignment(model_id: str, effort: str, source: Path, harness: str = "opencode") -> dict:
    """Require exact provider/model identity and declared tool/effort support."""
    if not isinstance(model_id, str) or not _IDENTIFIER.fullmatch(model_id):
        raise CatalogError("Use an exact Models.dev provider/model-id, for example openai/gpt-6-luna.")
    if not isinstance(effort, str) or not _EFFORT.fullmatch(effort):
        raise CatalogError("Use a nonempty, syntactically valid reasoning effort.")

    # Harness support is required even when the model is newer than our catalog.
    capabilities_path = source / "olympus" / "harnesses" / "capabilities.toml"
    try:
        with capabilities_path.open("rb") as stream:
            capabilities = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CatalogError(f"Cannot read declared harness capabilities at {capabilities_path}: {error}") from error
    declared = capabilities.get(harness, {})
    if declared.get("PER_ROLE_MODEL") != "SUPPORTED" or declared.get("PER_ROLE_REASONING") != "SUPPORTED":
        raise CatalogError(f"The {harness} harness does not declare per-role model and reasoning support.")

    catalog = load_catalog(str(catalog_path(source).resolve()))
    model = catalog["models"].get(model_id)
    if model is None:
        # A bundled snapshot may lag behind a custom provider or a newer model.
        # Preserve the explicit ID while making unverified capabilities visible.
        print(f"WARNING: {model_id} is not in bundled Models.dev; model and effort compatibility are unverified.",
              file=sys.stderr)
        return {"catalog_status": "unverified", "model_id": model_id}
    if model.get("tool_call") is not True:
        raise CatalogError(f"{model_id} does not declare tool-call support in Models.dev.")
    if model.get("reasoning") is not True:
        raise CatalogError(f"{model_id} does not declare reasoning support in Models.dev.")
    efforts = model.get("efforts")
    if not isinstance(efforts, list) or effort not in efforts:
        declared = ", ".join(efforts) if isinstance(efforts, list) and efforts else "none"
        raise CatalogError(f"{model_id} does not declare reasoning effort '{effort}'; declared efforts: {declared}.")

    return model
