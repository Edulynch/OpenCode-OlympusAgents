"""Read-only project installation diagnostics through the existing verifier."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


_REASON = re.compile(r"(?m)^OLYMPUS_VERIFY_REASON: ([A-Z][A-Z0-9_]*)\s*$")
_DETAIL = re.compile(r"(?m)^OLYMPUS_VERIFY_DETAIL: (.*)$")
_POWERSHELL_VERSION = re.compile(r"(?m)^PowerShell ([0-9]+)\.")
_DRIFT_REASONS = {"MANAGED_FILE_DRIFT", "MANAGED_FILE_MISSING", "MANAGED_FILE_MISMATCH", "ROSTER_MISMATCH"}
_INVALID_MANIFEST_REASONS = {"INSTALL_CONFLICT", "INSTALL_MANIFEST_INCOMPATIBLE"}


def _windows_verifier_supported() -> bool:
    return sys.platform == "win32"


def _powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _powershell_7(executable: str) -> bool:
    environment = os.environ.copy()
    options = {
        "env": environment,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "check": False,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    # pwsh writes its noninteractive startup cache under USERPROFILE even with -NoProfile.
    with tempfile.TemporaryDirectory(prefix="olympus-doctor-pwsh-") as user_profile:
        environment["USERPROFILE"] = user_profile
        completed = subprocess.run([executable, "-Version"], **options)
    match = _POWERSHELL_VERSION.search(completed.stdout or "")
    return completed.returncode == 0 and match is not None and int(match.group(1)) >= 7


def _run_verify_only(executable: str, source: Path, target: Path, harness: str,
                     source_version: str) -> subprocess.CompletedProcess:
    script = (
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        f"& {_powershell_literal(str(source / 'scripts' / 'bootstrap.ps1'))} "
        f"-Target {_powershell_literal(str(target))} -Harness {_powershell_literal(harness)} "
        f"-SourceVersion {_powershell_literal(source_version)} -VerifyOnly"
    )
    command = [
        executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script,
    ]
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    options = {
        "cwd": source,
        "env": environment,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "check": False,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    with tempfile.TemporaryDirectory(prefix="olympus-doctor-pwsh-") as user_profile:
        environment["USERPROFILE"] = user_profile
        return subprocess.run(command, **options)


def _set_issue(response: dict, code: str, message: str) -> None:
    response["issues"] = [{"code": code, "message": message}]


def _unavailable(response: dict, code: str, message: str) -> int:
    response["result"] = "blocked"
    response["data"]["installation_state"] = "verification_unavailable"
    response["data"]["integrity"] = "unverified"
    response["data"]["verification"]["state"] = "unavailable"
    _set_issue(response, code, message)
    return 3


def diagnose(source: Path, args, response: dict, *, source_version: str,
             source_query) -> int:
    """Populate a doctor response without persistent source or target writes."""
    from . import config_apply

    selected = ("opencode", "codex") if args.harness == "all" else (args.harness,)
    data = {
        "installation_state": "unknown",
        "integrity": "unverified",
        "manifest_state": "unknown",
        "source_version": source_version,
        "source_provenance": "local_checkout",
        "recorded_version": "unknown",
        "recorded_source_commit": "unknown",
        "installed_harnesses": [],
        "selected_harnesses": list(selected),
        "harnesses": {name: "unverified" for name in selected},
        "assignments": "unknown",
        "runtime_discovery": "not_performed",
        "verification": {
            "state": "not_run",
            "engine": "scripts/bootstrap.ps1 -VerifyOnly",
            "platform": "Windows with PowerShell 7 only",
        },
    }
    response["operation"] = "doctor"
    response["context"] = {
        "source": str(source),
        "kind": "project_installation_diagnostic",
        "scope": "project",
        "harness": args.harness,
        "target": str(args.target),
    }
    response["data"] = data
    response["issues"] = []

    try:
        target = config_apply._validate_target(source, args.target)
    except config_apply.PreviewFault as error:
        response["result"] = "blocked" if error.code == 3 else "failed"
        _set_issue(response, error.issue_code, str(error))
        return error.code
    response["context"]["target"] = str(target)

    record, _, blockers = config_apply._manifest_record(target)
    if blockers:
        codes = {item["code"] for item in blockers}
        if codes == {"manifest_missing"}:
            data.update({"installation_state": "absent", "manifest_state": "absent", "integrity": "unverified"})
            data["harnesses"] = {name: "absent" for name in selected}
            response["result"] = "absent"
            return 0
        response["issues"] = blockers
        invalid = any(code.startswith("invalid") or code in {"ambiguous_manifest", "manifest_too_large"}
                      for code in codes)
        data["installation_state"] = "invalid" if invalid else "verification_unavailable"
        data["manifest_state"] = "invalid" if invalid else "unavailable"
        data["verification"]["state"] = "not_run"
        response["result"] = "blocked"
        return 3

    assert record is not None
    installed = list(record.installed_harnesses)
    present = [name for name in selected if name in installed]
    missing = [name for name in selected if name not in installed]
    data.update({
        "manifest_state": "valid",
        "installed_harnesses": installed,
        "recorded_version": record.installed_version,
        "recorded_source_commit": record.installed_from_commit,
        "manifest": record.relative_path,
        "harnesses": {name: "absent" if name in missing else "unverified" for name in selected},
    })
    if not present:
        data["installation_state"] = "partial" if installed else "absent"
        data["manifest_state"] = "valid"
        response["result"] = "absent"
        _set_issue(response, "harness_absent", "The selected harness is not recorded in the project manifest.")
        return 0

    verify_harness = present[0] if len(present) == 1 else "all"
    source_data, source_issues = source_query(source, "config check", verify_harness)
    if source_issues or not source_data.get("coherent"):
        data["source_coherent"] = False
        data["source_issues"] = source_issues
        return _unavailable(response, "source_drift", "The local source outputs do not match the canonical renderer; VerifyOnly was not run.")
    data["source_coherent"] = True

    bootstrap = source / "scripts" / "bootstrap.ps1"
    if not bootstrap.is_file():
        return _unavailable(response, "verifier_missing", f"The existing verifier is missing: {bootstrap}")
    if not _windows_verifier_supported():
        return _unavailable(response, "platform_unqualified", "Project VerifyOnly is qualified only on Windows; no verification was claimed.")
    executable = shutil.which("pwsh")
    if executable is None:
        return _unavailable(response, "verifier_unavailable", "PowerShell 7 (pwsh) is unavailable; no verification was claimed.")
    try:
        if not _powershell_7(executable):
            return _unavailable(response, "verifier_version_unsupported",
                                 "PowerShell 7 or later is required; no verification was claimed.")
    except OSError as error:
        return _unavailable(response, "verifier_unavailable", f"Could not query PowerShell version: {error}")

    verification_version = "local" if record.installed_version == "local" else source_version
    data["verification"]["source_version"] = verification_version
    try:
        completed = _run_verify_only(executable, source, target, verify_harness, verification_version)
    except OSError as error:
        return _unavailable(response, "verifier_unavailable", f"Could not start PowerShell VerifyOnly: {error}")

    output = completed.stdout or ""
    passed = f"OLYMPUS_VERIFY: {verification_version} PASS"
    reason_match = _REASON.search(output)
    detail_match = _DETAIL.search(output)
    reason = reason_match.group(1) if reason_match else ""
    detail = detail_match.group(1).strip() if detail_match else ""
    if completed.returncode == 0 and passed in output.splitlines():
        data.update({"installation_state": "verified" if not missing else "partial", "integrity": "verified"})
        data["verification"]["state"] = "verified"
        for name in present:
            data["harnesses"][name] = "verified"
        if missing:
            response["result"] = "absent"
            _set_issue(response, "harness_absent", "The selected harness is not recorded in the project manifest.")
        else:
            response["result"] = "ok"
        return 0

    data["verification"]["state"] = "failed"
    if reason in _DRIFT_REASONS:
        manifest_problem = reason == "MANAGED_FILE_MISMATCH" and any(
            marker in detail.lower() for marker in (
                "manifest schema", "project-scope", "does not record harness",
                "managed file set differs", "manifest does not uniquely own",
            )
        )
        if manifest_problem:
            data["installation_state"] = "invalid"
            data["manifest_state"] = "invalid"
            code, state, exit_code = "invalid_manifest", "blocked", 3
        else:
            data["installation_state"] = "drift"
            data["integrity"] = "drift"
            for name in present:
                data["harnesses"][name] = "drift"
            code, state, exit_code = "managed_file_drift", "failed", 1
    elif reason in _INVALID_MANIFEST_REASONS:
        data["installation_state"] = "invalid"
        data["manifest_state"] = "invalid"
        code, state, exit_code = "invalid_manifest", "blocked", 3
    elif reason == "INSTALLED_VERSION_MISMATCH":
        data["installation_state"] = "verification_unavailable"
        data["verification"]["state"] = "unavailable"
        code, state, exit_code = "version_mismatch", "blocked", 3
    else:
        data["installation_state"] = "verification_unavailable" if not reason else "failed"
        data["verification"]["state"] = "unavailable" if not reason else "failed"
        code, state, exit_code = "verification_unavailable" if not reason else "verification_failed", "blocked" if not reason else "failed", 3 if not reason else 1
    response["result"] = state
    message = detail or (f"VerifyOnly reported {reason}." if reason else
                         f"VerifyOnly exited {completed.returncode} without a structured diagnostic.")
    if reason:
        data["verification"]["reason"] = reason
    _set_issue(response, code, message)
    return exit_code
