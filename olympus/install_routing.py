"""Narrow CLI routing to the existing Windows install/uninstall engines."""

from __future__ import annotations

import os
import json
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
_LINUX_ENGINE_TIMEOUT = 1200


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


def _run_linux_launcher(source: Path, operation: str, *, dry_run: bool) -> tuple[dict, int]:
    from .cli import CLIError

    launcher = source / "scripts" / "launch-latest.py"
    if not launcher.is_file():
        raise CLIError(f"The immutable-release Linux launcher is missing: {launcher}", 3)
    command = [
        sys.executable, "-I", "-S", "-B", str(launcher), operation, "--_response",
    ]
    if dry_run:
        command.append("--dry-run")
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            command, cwd=source, env=environment, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
            timeout=_LINUX_ENGINE_TIMEOUT, shell=False,
        )
    except subprocess.TimeoutExpired as error:
        message = (
            "Linux release operation timed out; effects are unconfirmed. "
            "Inspect the selected installation before retrying."
            if not dry_run else "Linux release preview timed out; no target execution was requested."
        )
        response = {
            "schema_version": 1, "operation": operation,
            "result": "unconfirmed" if not dry_run else "failed",
            "context": {"source": str(source), "kind": "native_install_routing",
                        "scope": "global", "harness": "opencode",
                        "mode": "dry-run" if dry_run else "execute"},
            "data": {
                "mode": "dry-run" if dry_run else "execute",
                "engine": "scripts/launch-latest.py",
                "state": "unconfirmed" if not dry_run else "failed",
                "native_exit_code": None,
                "native_stdout": _timeout_output(error.stdout),
                "native_stderr": _timeout_output(error.stderr),
                "effects": "unconfirmed_after_native_failure" if not dry_run
                else "target_read_only_preview; temporary/cache effects may remain",
                "cwd_role": "ignored_for_global_target_resolution",
            },
            "issues": [{"code": "linux_launcher_timeout", "message": message}],
        }
        return response, 4 if not dry_run else 1
    except KeyboardInterrupt:
        code = 4 if not dry_run else 1
        result = "unconfirmed" if not dry_run else "failed"
        response = {
            "schema_version": 1, "operation": operation, "result": result,
            "context": {"source": str(source), "kind": "native_install_routing",
                        "scope": "global", "harness": "opencode",
                        "mode": "dry-run" if dry_run else "execute"},
            "data": {
                "mode": "dry-run" if dry_run else "execute",
                "engine": "scripts/launch-latest.py", "state": result,
                "native_exit_code": None, "native_stdout": "", "native_stderr": "",
                "effects": "unconfirmed_after_native_failure" if not dry_run
                else "target_read_only_preview; temporary/cache effects may remain",
                "cwd_role": "ignored_for_global_target_resolution",
            },
            "issues": [{
                "code": "linux_launcher_interrupted",
                "message": "Linux release operation was interrupted; inspect before retrying."
                if not dry_run else "Linux release preview was interrupted; no target execution was requested.",
            }],
        }
        return response, code
    except OSError as error:
        response = {
            "schema_version": 1, "operation": operation, "result": "blocked",
            "context": {"source": str(source), "kind": "native_install_routing",
                        "scope": "global", "harness": "opencode",
                        "mode": "dry-run" if dry_run else "execute"},
            "data": {
                "mode": "dry-run" if dry_run else "execute",
                "engine": "scripts/launch-latest.py", "state": "not_started",
                "native_exit_code": None, "native_stdout": "", "native_stderr": str(error),
                "effects": "none_confirmed",
                "cwd_role": "ignored_for_global_target_resolution",
            },
            "issues": [{"code": "linux_launcher_start_failed", "message": str(error)}],
        }
        return response, 3

    try:
        response = json.loads(completed.stdout)
        if (not isinstance(response, dict)
                or set(response) != {"schema_version", "operation", "result", "context", "data", "issues"}
                or response["schema_version"] != 1 or response["operation"] != operation
                or not isinstance(response["context"], dict)
                or not isinstance(response["data"], dict)
                or not isinstance(response["issues"], list)):
            raise ValueError("Linux release coordinator returned an invalid response.")
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        response = {
            "schema_version": 1, "operation": operation,
            "result": "unconfirmed" if completed.returncode != 0 else "failed",
            "context": {"source": str(source), "kind": "native_install_routing",
                        "scope": "global", "harness": "opencode",
                        "mode": "dry-run" if dry_run else "execute"},
            "data": {
                "mode": "dry-run" if dry_run else "execute",
                "engine": "scripts/launch-latest.py",
                "state": "unconfirmed" if completed.returncode != 0 else "failed",
                "native_exit_code": completed.returncode,
                "native_stdout": completed.stdout or "",
                "native_stderr": completed.stderr or "",
                "effects": "unconfirmed_after_native_failure" if completed.returncode != 0
                else "none_confirmed",
                "cwd_role": "ignored_for_global_target_resolution",
            },
            "issues": [{"code": "linux_launcher_response_invalid", "message": str(error)}],
        }
        return response, 4 if completed.returncode != 0 else 1
    expected_codes = {
        "preview": 0, "ok": 0, "failed": 1, "blocked": 3, "unconfirmed": 4,
    }
    matched = (
        expected_codes.get(response["result"]) == completed.returncode
        or response["result"] == "failed" and completed.returncode == 2
    )
    if not matched:
        response["result"] = "unconfirmed"
        response["data"].update({
            "state": "unconfirmed",
            "effects": "unconfirmed_after_native_failure",
            "native_exit_code": completed.returncode,
        })
        response["issues"].append({
            "code": "linux_launcher_result_mismatch",
            "message": "Linux release coordinator response and process exit code disagree.",
        })
        return response, 4
    response["context"]["source"] = str(source)
    response["data"]["native_exit_code"] = completed.returncode
    if completed.stderr:
        response["data"]["native_stderr"] = (
            response["data"].get("native_stderr", "") + completed.stderr
        )
    if completed.returncode == 0:
        return response, 0
    if completed.returncode in (1, 2, 3, 4):
        return response, completed.returncode
    response["result"] = "unconfirmed"
    response["data"].update({
        "state": "unconfirmed",
        "effects": "unconfirmed_after_native_failure",
    })
    response["issues"].append({
        "code": "linux_launcher_exit_unknown",
        "message": f"Linux release coordinator exited with unrecognized code {completed.returncode}.",
    })
    return response, 4


def run(source: Path, args, response: dict, *, emit, as_json: bool) -> int:
    operation = args.command
    dry_run = args.dry_run
    mode = "dry-run" if dry_run else "execute"
    response["context"] = {
        "source": str(source), "kind": "native_install_routing", "scope": "global",
        "harness": "opencode", "mode": mode,
    }
    response["data"] = {
        "mode": mode, "engine": "not_started", "native_exit_code": None,
        "native_stdout": "", "native_stderr": "", "effects": "none_confirmed",
    }
    response["issues"] = []
    response["data"]["cwd_role"] = "ignored_for_global_target_resolution"
    if operation == "install":
        response["data"]["release_version"] = "latest stable"

    linux = sys.platform.startswith("linux") and os.name == "posix"
    if linux:
        script = source / "scripts" / "launch-latest.py"
        engine = "scripts/launch-latest.py"
    elif operation == "install":
        script = source / "scripts" / "launch-latest.ps1"
        engine = "scripts/launch-latest.ps1"
    else:
        script = source / "scripts" / "global-install.ps1"
        engine = "scripts/global-install.ps1"
    if not script.is_file():
        return _finish(response, emit, as_json, 3, "blocked", "native_engine_missing",
                       f"The existing native engine is missing: {script}")

    if linux:
        try:
            routed, code = _run_linux_launcher(source, operation, dry_run=dry_run)
        except Exception as error:
            return _finish(response, emit, as_json, 3, "blocked", "linux_launcher_blocked", str(error))
        emit(routed, as_json)
        return code

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
        command.extend(["-Action", "install"])
        if dry_run:
            command.append("-DryRun")
    else:
        command.extend(["-Harness", "opencode", "-Uninstall"])
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
        if operation == "uninstall" and not dry_run:
            cli_uninstaller = source / "scripts" / "install-cli.ps1"
            if cli_uninstaller.is_file():
                cleanup = subprocess.run(
                    [executable, "-NoProfile", "-NonInteractive", "-File", str(cli_uninstaller), "-Action", "uninstall"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    check=False, timeout=_ENGINE_TIMEOUT, env=environment, shell=False,
                )
                response["data"]["native_stdout"] += cleanup.stdout or ""
                response["data"]["native_stderr"] += cleanup.stderr or ""
                if cleanup.returncode != 0:
                    response["data"].update({"state": "unconfirmed", "effects": "global harness removed; CLI cleanup failed"})
                    return _finish(response, emit, as_json, 4, "unconfirmed", "global_cli_cleanup_failed",
                                   "Global managed resources were removed but CLI PATH cleanup failed; inspect the installation before retrying.")
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
