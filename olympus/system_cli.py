"""Windows global CLI operations that reuse the immutable release installer."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import install_routing


def update(source: Path, scope: str | None = None, target: Path | None = None) -> int:
    if sys.platform != "win32":
        print("olympus update is qualified only for Windows; no update was started.", file=sys.stderr)
        return 3
    executable = shutil.which("pwsh")
    if executable is None:
        print("PowerShell 7 (pwsh) is required; no update was started.", file=sys.stderr)
        return 3
    supported, version, problem = install_routing._powershell_version(executable)
    if not supported:
        print(problem, file=sys.stderr)
        return 3

    launcher = source / "scripts" / "launch-latest.ps1"
    if not launcher.is_file():
        print(f"The immutable-release update launcher is missing: {launcher}", file=sys.stderr)
        return 3
    from . import user_config

    try:
        selected_scope, selected_target = user_config.select_scope(source, scope, target)
    except user_config.UserConfigError as error:
        print(f"Cannot select a safe Olympus update target: {error}", file=sys.stderr)
        return 3
    command = [
        executable, "-NoProfile", "-File", str(launcher),
        "-Action", "install", "-Scope", selected_scope, "-Harness", "opencode",
        "-Target", str(selected_target or Path.cwd()), "-Update",
    ]
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            command, cwd=source, env=environment, check=False, timeout=1200, shell=False,
        )
    except subprocess.TimeoutExpired:
        print("Update timed out; inspect olympus doctor before retrying.", file=sys.stderr)
        return 4
    except OSError as error:
        print(f"Could not start the immutable-release updater: {error}", file=sys.stderr)
        return 3
    if completed.returncode == 0:
        print("Olympus update completed or is already current; previous and selected versions are reported above.")
        return 0
    print("Olympus update did not complete; no success is assumed.", file=sys.stderr)
    return completed.returncode
