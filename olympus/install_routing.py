"""Narrow CLI routing to the existing Windows install/uninstall engines."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


_RELEASE_TAG = re.compile(
    r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?"
)
_POWERSHELL_VERSION = re.compile(r"(?m)^PowerShell ([0-9]+)\.")
_VERSION_TIMEOUT = 10
_ENGINE_TIMEOUT = 300


def _finish(response: dict, emit, as_json: bool, code: int, result: str,
            issue_code: str | None = None, message: str | None = None) -> int:
    response["result"] = result
    if issue_code is not None and message is not None:
        response["issues"].append({"code": issue_code, "message": message})
    emit(response, as_json)
    return code


def _validate_project_target(source: Path, requested: Path | None):
    from . import config_apply

    if requested is None or not requested.is_absolute():
        raise config_apply.PreviewFault(
            2, "invalid_target", "Project install/uninstall requires an absolute --target worktree root.",
        )
    try:
        target = requested.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise config_apply.PreviewFault(
            2, "invalid_target", f"Target does not resolve to an existing directory: {requested}",
        ) from error
    if not target.is_dir():
        raise config_apply.PreviewFault(2, "invalid_target", f"Target is not a directory: {target}")
    marker = target / ".git"
    if not (marker.is_dir() or marker.is_file()):
        raise config_apply.PreviewFault(2, "invalid_target", "Target must be a Git worktree root with a .git marker.")
    return config_apply._validate_target(source, requested)


def _powershell_version(executable: str) -> tuple[bool, str, str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    # Keep startup cache writes from the read-only version probe out of the user's profile.
    with tempfile.TemporaryDirectory(prefix="olympus-cli-pwsh-") as user_profile:
        environment["USERPROFILE"] = user_profile
        try:
            completed = subprocess.run(
                [executable, "-Version"], capture_output=True, text=True, encoding="utf-8",
                errors="replace", check=False, timeout=_VERSION_TIMEOUT, env=environment, shell=False,
            )
        except subprocess.TimeoutExpired as error:
            return False, "", f"PowerShell version probe timed out after {_VERSION_TIMEOUT} seconds."
        except KeyboardInterrupt:
            return False, "", "PowerShell version probe was interrupted; no install engine was started."
    output = completed.stdout or ""
    match = _POWERSHELL_VERSION.search(output)
    if completed.returncode == 0 and match is not None and int(match.group(1)) >= 7:
        return True, output.strip(), ""
    return False, output.strip(), "PowerShell 7 or later (pwsh) is required."


def _timeout_output(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run(source: Path, args, response: dict, *, emit, as_json: bool) -> int:
    operation = args.command
    scope = args.scope
    harness = args.harness
    dry_run = args.dry_run
    mode = "dry-run" if dry_run else "execute"
    response["context"] = {
        "source": str(source), "kind": "native_install_routing", "scope": scope,
        "harness": harness, "mode": mode,
    }
    response["data"] = {
        "mode": mode, "engine": "not_started", "native_exit_code": None,
        "native_stdout": "", "native_stderr": "", "effects": "none_confirmed",
    }
    response["issues"] = []

    requested_target = args.target
    if scope == "global" and requested_target is not None:
        return _finish(response, emit, as_json, 2, "failed", "invalid_arguments",
                       "--target is incompatible with --scope global; global roots are resolved by the official engine.")
    if operation == "install":
        release = args.release_version
        if _RELEASE_TAG.fullmatch(release) is None:
            return _finish(response, emit, as_json, 2, "failed", "invalid_release_tag",
                           "--version must be one exact Olympus release tag (for example v1.2.3).")
        response["data"]["release_version"] = release
    elif scope == "project" and (requested_target is None or not requested_target.is_absolute()):
        return _finish(response, emit, as_json, 2, "failed", "invalid_target",
                       "Project install/uninstall requires an absolute --target worktree root.")
    if operation == "uninstall" and scope == "project" and dry_run:
        return _finish(response, emit, as_json, 3, "blocked", "dry_run_unsupported",
                       "The existing project uninstaller has no dry-run mode; no native process was started.")

    target = None
    if scope == "project":
        from . import config_apply

        try:
            target = _validate_project_target(source, requested_target)
        except config_apply.PreviewFault as error:
            result = "blocked" if error.code == 3 else "failed"
            return _finish(response, emit, as_json, error.code, result, error.issue_code, str(error))
        response["context"]["target"] = str(target)
        response["data"]["target"] = str(target)

    if scope == "global":
        cwd = Path.cwd()
        response["context"].update({"cwd": str(cwd), "cwd_role": "read_only_project_override_context"})
        response["data"]["cwd_role"] = "read_only_project_override_context"

    if operation == "install":
        script = source / "scripts" / "launch-latest.ps1"
        engine = "scripts/launch-latest.ps1"
    elif scope == "project":
        script = source / "scripts" / "project-uninstall.ps1"
        engine = "scripts/project-uninstall.ps1"
    else:
        script = source / "scripts" / "global-install.ps1"
        engine = "scripts/global-install.ps1"
    if not script.is_file():
        return _finish(response, emit, as_json, 3, "blocked", "native_engine_missing",
                       f"The existing native engine is missing: {script}")

    if sys.platform != "win32":
        return _finish(response, emit, as_json, 3, "blocked", "platform_unqualified",
                       "Install/uninstall routing is qualified only on Windows; no native operation was started.")
    executable = shutil.which("pwsh")
    if executable is None:
        return _finish(response, emit, as_json, 3, "blocked", "powershell_unavailable",
                       "PowerShell 7 (pwsh) is unavailable; no native operation was started.")
    try:
        supported, version, problem = _powershell_version(executable)
    except OSError as error:
        supported, version, problem = False, "", f"Could not query PowerShell 7: {error}"
    response["data"]["powershell_version"] = version
    if not supported:
        return _finish(response, emit, as_json, 3, "blocked", "powershell_unsupported", problem)

    command = [executable, "-NoProfile", "-NonInteractive", "-File", str(script)]
    if operation == "install":
        command.extend(["-Action", "install", "-Scope", scope, "-Harness", harness,
                        "-Version", args.release_version])
        if target is not None:
            command.extend(["-Target", str(target)])
        if dry_run:
            command.append("-DryRun")
    elif scope == "project":
        command.extend(["-Target", str(target), "-Harness", harness])
    else:
        command.extend(["-Harness", harness, "-Uninstall"])
        if dry_run:
            command.append("-DryRun")

    response["data"]["engine"] = engine
    response["data"]["effects"] = "unconfirmed_until_native_result"
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, timeout=_ENGINE_TIMEOUT, env=environment, shell=False,
        )
    except subprocess.TimeoutExpired as error:
        response["data"].update({
            "native_stdout": _timeout_output(error.stdout),
            "native_stderr": _timeout_output(error.stderr),
            "state": "unconfirmed" if not dry_run else "failed",
            "effects": "unconfirmed; descendant processes may continue" if not dry_run else "no target execution requested; temporary/cache effects may remain",
        })
        code = 4 if not dry_run else 1
        result = "unconfirmed" if not dry_run else "failed"
        return _finish(response, emit, as_json, code, result, "native_timeout",
                       f"Native command exceeded {_ENGINE_TIMEOUT} seconds; no automatic retry was attempted.")
    except KeyboardInterrupt:
        state = "unconfirmed" if not dry_run else "failed"
        effects = "unconfirmed; descendant processes may continue" if not dry_run else "no target execution requested; temporary/cache effects may remain"
        response["data"].update({"state": state, "effects": effects})
        code = 4 if not dry_run else 1
        return _finish(response, emit, as_json, code, state, "native_interrupted",
                       "Native command was interrupted; no automatic retry was attempted.")
    except OSError as error:
        response["data"].update({"state": "not_started", "effects": "none_confirmed"})
        return _finish(response, emit, as_json, 3, "blocked", "native_start_failed",
                       f"Could not start the native engine: {error}")

    response["data"].update({
        "native_exit_code": completed.returncode,
        "native_stdout": completed.stdout or "",
        "native_stderr": completed.stderr or "",
    })
    if completed.returncode == 0:
        if dry_run:
            response["data"].update({
                "state": "preview",
                "effects": "target_read_only_preview; temporary/cache effects may remain",
            })
            response["data"]["installation_state"] = "not_installed" if operation == "install" else "not_removed"
            return _finish(response, emit, as_json, 0, "preview")
        response["data"].update({"state": "ok", "effects": "native_engine_confirmed_success"})
        return _finish(response, emit, as_json, 0, "ok")

    if dry_run:
        response["data"].update({
            "state": "failed",
            "effects": "target_read_only_preview; temporary/cache effects may remain",
        })
        return _finish(response, emit, as_json, 1, "failed", "native_operation_failed",
                       f"Native preview exited with code {completed.returncode}.")
    response["data"].update({"state": "unconfirmed", "effects": "unconfirmed_after_native_failure"})
    return _finish(response, emit, as_json, 4, "unconfirmed", "native_operation_unconfirmed",
                   f"Native operation exited with code {completed.returncode}; partial effects cannot be ruled out. Inspect before retrying.")
