"""Windows global CLI operations that reuse the immutable release installer."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import install_routing


def update(source: Path, *, verbose: bool = False, force: bool = False) -> int:
    if sys.platform.startswith("linux") and os.name == "posix":
        from . import cli

        if force:
            response, code = install_routing._run_linux_launcher(
                source, "update", dry_run=False, force=True,
            )
        else:
            response, code = install_routing._run_linux_launcher(
                source, "update", dry_run=False,
            )
        if verbose:
            cli.emit(response, False, verbose=True)
            return code
        print("Checking for updates...", flush=True)
        print(f"olympus update: {response.get('result', 'unknown')}")
        cli._emit_native_output_summary(response.get("data", {}))
        cli._emit_issues(response)
        if code == 4:
            print("Update effects are unconfirmed; inspect olympus doctor before retrying.", file=sys.stderr)
        return code
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
    command = [
        executable, "-NoProfile", "-File", str(launcher),
        "-Action", "install", "-Update",
    ]
    if force:
        command.append("-Force")
    if verbose:
        command.append("-Verbose")
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if verbose:
        environment.pop("OLYMPUS_UPDATE_COMPACT", None)
    else:
        environment["OLYMPUS_UPDATE_COMPACT"] = "1"
    print("Checking for updates...", flush=True)
    try:
        completed = subprocess.run(
            command, cwd=source, env=environment, check=False, timeout=1200, shell=False,
        )
    except subprocess.TimeoutExpired:
        print("Update timed out; effects are unconfirmed. Inspect olympus doctor before retrying.", file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        print("Update interrupted; effects are unconfirmed. Inspect olympus doctor before retrying.", file=sys.stderr)
        return 4
    except OSError as error:
        print(f"Could not start the immutable-release updater: {error}", file=sys.stderr)
        return 3
    if completed.returncode != 0:
        print(f"Update did not complete (native exit {completed.returncode}); review native output above. "
              "No automatic retry was attempted.", file=sys.stderr)
    return completed.returncode
