"""Explicit OpenCode global apply over the existing private transaction journal."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Callable

from . import config_apply, config_apply_transaction, global_readonly


_MANIFEST = "olympus/orchestrator-install.json"


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _build_plan(candidate: dict) -> dict:
    root: Path = candidate["root"]
    expected: dict[str, bytes] = candidate["expected"]
    current: dict[str, bytes] = candidate["current"]
    entries: dict[str, str] = candidate["entries"]
    manifest = candidate["manifest"]
    manifest_raw: bytes = candidate["manifest_raw"]
    changes: list[config_apply_transaction.GlobalChange] = []

    for relative, desired in sorted(expected.items()):
        old = current.get(relative)
        if relative not in entries:
            if relative != "opencode.jsonc" or candidate["guard_state"] != "missing":
                continue
            if old is not None:
                raise config_apply_transaction.TransactionError(
                    "The unowned global OpenCode config appeared after preview; no write was made.", 3,
                )
            mode = 0o666 if os.name == "nt" else 0o600
        else:
            if old is None:
                raise config_apply_transaction.TransactionError(
                    f"A manifest-owned global resource disappeared: {relative}", 3,
                )
            if old == desired:
                continue
            path, metadata, issue = config_apply._lstat_target_path(root, relative)
            if issue or path is None or metadata is None:
                raise config_apply_transaction.TransactionError(issue or f"Cannot inspect global resource: {relative}", 3)
            mode = stat.S_IMODE(metadata.st_mode)
        if old != desired:
            changes.append(config_apply_transaction.GlobalChange(relative, old, desired, mode))

    new_data = json.loads(manifest_raw.decode("utf-8"))
    new_entries = []
    for original in new_data["managed_files"]:
        item = dict(original)
        relative = item["path"]
        if relative in expected:
            item["sha256"] = _digest(expected[relative])
        new_entries.append(item)
    if any(change.path == "opencode.jsonc" and change.old is None for change in changes):
        new_entries.append({"path": "opencode.jsonc", "sha256": _digest(expected["opencode.jsonc"])})
    new_data["managed_files"] = sorted(new_entries, key=lambda item: item["path"])
    manifest_new = (manifest_raw if new_data == manifest else
                    (json.dumps(new_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    if manifest_new != manifest_raw:
        path, metadata, issue = config_apply._lstat_target_path(root, _MANIFEST)
        if issue or path is None or metadata is None:
            raise config_apply_transaction.TransactionError(issue or "Global ownership manifest disappeared.", 3)
        changes.sort(key=lambda item: item.path)
        changes.append(config_apply_transaction.GlobalChange(
            _MANIFEST, manifest_raw, manifest_new, stat.S_IMODE(metadata.st_mode), manifest=True,
        ))
    elif changes:
        raise config_apply_transaction.TransactionError(
            "Global resource changes have no corresponding manifest update; refusing an unowned write set.", 3,
        )
    return {"root": root, "changes": tuple(changes), "manifest_old": manifest_raw,
            "manifest_new": manifest_new, "manifest_path": _MANIFEST}


def _plan_fingerprint(plan: dict) -> tuple:
    return tuple((item.path, None if item.old is None else _digest(item.old), _digest(item.new), item.mode)
                 for item in plan["changes"])


def _inspect(source: Path, args, response: dict, *, source_query: Callable, load_renderer: Callable,
             release_version: Callable, assignment_query: Callable) -> tuple[int, dict | None]:
    sink: dict = {}
    code = global_readonly.inspect(
        source, args, response, source_query=source_query, load_renderer=load_renderer,
        release_version=release_version, assignment_query=assignment_query,
        operation="config apply", plan_sink=sink,
    )
    if code or response.get("result") == "absent":
        return code, None
    try:
        return 0, _build_plan(sink)
    except config_apply_transaction.TransactionError as error:
        response["result"] = "blocked" if error.code == 3 else "unconfirmed" if error.code == 4 else "failed"
        response["issues"] = [{"code": response["result"], "message": str(error)}]
        return error.code, None


def _unsupported(response: dict, harness: str) -> int:
    response.update({"operation": "config apply", "result": "blocked",
                     "context": {"scope": "global", "harness": harness, "kind": "global_config_apply"},
                     "data": {"preview_only": True, "apply_available": False, "execution": "not_started",
                              "changes": [], "assignments": {"status": "unknown", "evidence": "not_verified",
                                                                  "roles": [], "roots": {}}},
                     "issues": [{"code": "global_harness_unsupported",
                                 "message": "Global config apply execution is currently limited to --harness opencode."}]})
    return 3


def execute(source: Path, args, response: dict, *, source_query: Callable, load_renderer: Callable,
            release_version: Callable, assignment_query: Callable) -> int:
    """Execute only an explicit OpenCode plan, with locked revalidation and recovery evidence."""
    if args.harness != "opencode":
        return _unsupported(response, args.harness)
    code, plan = _inspect(source, args, response, source_query=source_query,
                          load_renderer=load_renderer, release_version=release_version,
                          assignment_query=assignment_query)
    if code:
        response["data"].update({"preview_only": False, "execution": "not_started"})
        return code
    if plan is None:
        response["result"] = "blocked"
        response["issues"] = [{"code": "global_manifest_missing",
                                "message": "Global config apply updates an existing managed installation; it does not install or adopt one."}]
        response["data"].update({"preview_only": False, "apply_available": False, "execution": "not_started"})
        return 3
    if not plan["changes"]:
        response["result"] = "no_changes"
        response["data"].update({"preview_only": False, "execution": "no_changes"})
        return 0
    response["data"].update({"preview_only": False, "execution": "not_started"})

    def revalidate():
        latest = {"schema_version": 1, "operation": "config apply", "result": "ok",
                  "context": {}, "data": {}, "issues": []}
        latest_code, latest_plan = _inspect(
            source, args, latest, source_query=source_query, load_renderer=load_renderer,
            release_version=release_version, assignment_query=assignment_query,
        )
        if latest_code or latest_plan is None:
            raise config_apply_transaction.TransactionError(
                "Locked global revalidation failed: " + "; ".join(item["message"] for item in latest["issues"]),
                latest_code or 3,
            )
        if latest_plan["root"] != plan["root"]:
            raise config_apply_transaction.TransactionError(
                "Resolved global OpenCode root changed after preview; no write was made.", 3,
            )
        if _plan_fingerprint(latest_plan) != _plan_fingerprint(plan):
            raise config_apply_transaction.TransactionError(
                "Global configuration changed after preview; rerun config apply --dry-run.", 3,
            )
        return latest_plan

    try:
        state = config_apply_transaction.commit_global(plan["root"], source, plan["changes"],
                                                       plan["manifest_path"], revalidate,
                                                       load_renderer=load_renderer)
    except config_apply_transaction.TransactionError as error:
        response["result"] = {1: "failed", 3: "blocked", 4: "unconfirmed"}.get(error.code, "failed")
        response["data"]["execution"] = (
            "not_started" if error.code == 3 else
            "rollback_confirmed" if "rollback was confirmed" in str(error) else "unconfirmed"
        )
        response["issues"] = [{"code": response["result"], "message": str(error)}]
        return error.code
    response["result"] = "ok" if state == "committed" else "no_changes"
    response["data"].update({"preview_only": False, "execution": state})
    return 0


def recover(source: Path, args, response: dict, *, load_renderer: Callable) -> int:
    """Explicitly reconcile one OpenCode global apply journal."""
    if args.harness != "opencode":
        response.update({"operation": "config recover", "result": "blocked",
                         "context": {"scope": "global", "harness": args.harness},
                         "data": {}, "issues": [{"code": "global_harness_unsupported",
                                                  "message": "Global config recovery is currently limited to --harness opencode."}]})
        return 3
    if args.target is not None:
        response.update({"operation": "config recover", "result": "failed", "context": {"scope": "global"},
                         "data": {}, "issues": [{"code": "invalid_target", "message": "--target is incompatible with --scope global."}]})
        return 2
    try:
        root = global_readonly.resolve_roots(("opencode",))["opencode"]
        state = config_apply_transaction.recover_global(root, source, load_renderer=load_renderer)
    except config_apply_transaction.TransactionError as error:
        code = error.code
        result = {1: "failed", 3: "blocked", 4: "unconfirmed"}.get(code, "failed")
        response.update({"operation": "config recover", "result": result,
                         "context": {"source": str(source), "scope": "global", "harness": "opencode",
                                      "root": str(root) if "root" in locals() else "unresolved"},
                         "data": {}, "issues": [{"code": result, "message": str(error)}]})
        return code
    except global_readonly.GlobalFault as error:
        response.update({"operation": "config recover", "result": "blocked" if error.code == 3 else "failed",
                         "context": {"source": str(source), "scope": "global", "harness": "opencode"},
                         "data": {}, "issues": [{"code": error.reason, "message": str(error)}]})
        return error.code
    response.update({"operation": "config recover", "result": "no_changes" if state == "no_changes" else "ok",
                     "context": {"source": str(source), "scope": "global", "harness": "opencode", "root": str(root)},
                     "data": {"recovery": state}, "issues": []})
    return 0
