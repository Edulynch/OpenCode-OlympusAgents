#!/bin/sh
set -eu

case " $* " in
  *" --help "*|*" -h "*)
    cat <<'HELP'
Olympus Linux installer

Usage: sh install-olympus.sh [install|uninstall] [--dry-run] [--execute] [--json]

Uses Python 3.11 or newer and official immutable GitHub release metadata.
Install is the default action. Uninstall is safe to repeat after an interrupted cleanup.
No administrator privileges, Bash, PowerShell, curl, or package installation is used.
HELP
    exit 0
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Olympus requires Python 3.11 or newer (python3 was not found).' >&2
  exit 3
fi
if ! python3 -I -S -B -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
  printf '%s\n' 'Olympus requires Python 3.11 or newer.' >&2
  exit 3
fi

exec python3 -I -S -B - "$@" <<'PY'
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OWNER = "Edulynch"
REPOSITORY = "OpenCode-OlympusAgents"
API = f"https://api.github.com/repos/{OWNER}/{REPOSITORY}"
OFFICIAL_HOSTS = {"api.github.com", "github.com", "codeload.github.com"}
RELEASE_TAG = re.compile(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        parsed = urllib.parse.urlsplit(new_url)
        if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
            raise ValueError("GitHub redirected to a non-official HTTPS host.")
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def get(url: str, limit: int) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
        raise ValueError("Refusing a non-official release URL.")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(),
        OfficialRedirect(),
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "OlympusAgents-Linux-Bootstrap",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with opener.open(request, timeout=30) as response:
        final = urllib.parse.urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname not in OFFICIAL_HOSTS:
            raise ValueError("Release bytes came from a non-official HTTPS host.")
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Official release response exceeded its bounded size.")
    return raw


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field: {key}")
        value[key] = item
    return value


def json_object(url: str, limit: int = 4 * 1024 * 1024) -> dict:
    value = json.loads(get(url, limit).decode("utf-8"), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("Official GitHub metadata has an unexpected shape.")
    return value


def selected_release():
    release = json_object(f"{API}/releases/latest")
    for key, expected in (("immutable", True), ("draft", False), ("prerelease", False)):
        if type(release.get(key)) is not bool or release[key] is not expected:
            raise ValueError(f"Latest release metadata does not assert {key}={str(expected).lower()}.")
    version = release.get("tag_name")
    if not isinstance(version, str) or not RELEASE_TAG.fullmatch(version):
        raise ValueError("GitHub latest release is not a supported stable Olympus version.")
    published = release.get("published_at")
    if not isinstance(published, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})",
        published,
    ) is None:
        raise ValueError("Latest release has no timezone-aware published_at timestamp.")
    timestamp = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError("Latest release published_at timestamp is invalid or in the future.")
    commit = json_object(f"{API}/commits/{version}").get("sha")
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise ValueError("Latest stable release does not resolve to a full commit SHA.")

    path = "scripts/launch-latest.py"
    contents = json_object(
        f"{API}/contents/{path}?ref={commit}",
        limit=1024 * 1024,
    )
    if (contents.get("type") != "file" or contents.get("path") != path
            or contents.get("encoding") != "base64"
            or type(contents.get("size")) is not int or not 0 < contents["size"] <= 512 * 1024
            or contents.get("html_url")
            != f"https://github.com/{OWNER}/{REPOSITORY}/blob/{commit}/{path}"):
        raise ValueError("Official contents metadata does not identify the expected release launcher.")
    blob_sha = contents.get("sha")
    encoded = contents.get("content")
    if not isinstance(blob_sha, str) or not SHA.fullmatch(blob_sha) or not isinstance(encoded, str):
        raise ValueError("Official launcher metadata has no valid path digest or bytes.")
    raw = base64.b64decode("".join(encoded.split()), validate=True)
    git_sha = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    if len(raw) != contents["size"] or git_sha != blob_sha:
        raise ValueError("Official launcher bytes differ from their path, size, or Git blob digest.")
    return version, commit, blob_sha, raw


def emit_error(action: str, message: str, as_json: bool, code: int = 3) -> int:
    result_name = {1: "failed", 2: "failed", 3: "blocked", 4: "unconfirmed"}.get(code, "failed")
    payload = {
        "schema_version": 1,
        "operation": action,
        "result": result_name,
        "context": {
            "source": "official immutable release",
            "kind": "native_install_routing",
            "scope": "global",
            "harness": "opencode",
            "mode": "dry-run" if "--dry-run" in sys.argv[1:] else "execute",
        },
        "data": {
            "mode": "dry-run" if "--dry-run" in sys.argv[1:] else "execute",
            "engine": "install-olympus.sh",
            "state": "unconfirmed" if code == 4 else "not_started",
            "native_exit_code": code,
            "native_stdout": "",
            "native_stderr": message,
            "effects": "unconfirmed_after_native_failure" if code == 4 else "none_confirmed",
            "cwd_role": "ignored_for_global_target_resolution",
        },
        "issues": [{"code": "release_bootstrap_failed", "message": message}],
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"Olympus {action}: blocked\n{message}", file=sys.stderr)
    return code


def render_human(response: dict) -> None:
    print(f"Olympus {response['operation']}: {response['result']}")
    data = response.get("data", {})
    if data.get("release_version") and data["release_version"] != "latest stable":
        print(f"Release: {data['release_version']}")
    for item in data.get("plan", []):
        print(f"{item['action'].capitalize()}: {item['path']}")
    for line in data.get("native_stdout", "").splitlines():
        if line.startswith("OLYMPUS_UPDATE:"):
            print(line.partition(":")[2].strip())
    if response["result"] == "ok" and data.get("lifecycle_result") == "no_changes":
        print("No installation changes were needed.")
    if data.get("detail"):
        print(data["detail"])
    issue_messages = {item.get("message") for item in response.get("issues", [])}
    if data.get("native_stderr") and data["native_stderr"].strip() not in issue_messages:
        print(data["native_stderr"], file=sys.stderr)
    for issue in response.get("issues", []):
        print(f"{issue['code']}: {issue['message']}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="install-olympus.sh",
        description="Install or uninstall the verified Olympus Linux CLI and global OpenCode resources.",
    )
    parser.add_argument("action", nargs="?", choices=("install", "uninstall"), default="install")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="validate and print a read-only plan")
    modes.add_argument("--execute", action="store_true", help="explicitly execute the lifecycle operation")
    parser.add_argument("--json", action="store_true", help="emit one JSON result")
    args = parser.parse_args()
    try:
        version, commit, blob_sha, launcher = selected_release()
    except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as error:
        return emit_error(args.action, str(error), args.json)

    try:
        with tempfile.TemporaryDirectory(prefix="olympus-bootstrap-") as folder:
            path = Path(folder) / "launch-latest.py"
            with path.open("xb") as stream:
                stream.write(launcher)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(path, 0o600)
            command = [
                sys.executable, "-I", "-S", "-B", str(path), args.action,
                "--_response", "--_bootstrap", version, commit, blob_sha,
            ]
            if args.dry_run:
                command.append("--dry-run")
            try:
                completed = subprocess.run(
                    command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    check=False, timeout=1800, shell=False, env=os.environ.copy(),
                )
            except subprocess.TimeoutExpired:
                return emit_error(
                    args.action,
                    "Official release operation timed out; effects are unconfirmed. Inspect the installation before retrying.",
                    args.json,
                    4,
                )
            except KeyboardInterrupt:
                return emit_error(
                    args.action,
                    "Official release operation was interrupted; effects are unconfirmed. Inspect before retrying.",
                    args.json,
                    4,
                )
        try:
            response = json.loads(completed.stdout)
            if (not isinstance(response, dict) or response.get("schema_version") != 1
                    or response.get("operation") != args.action):
                raise ValueError("Release coordinator returned an invalid response.")
        except (ValueError, json.JSONDecodeError):
            message = completed.stderr.strip() or completed.stdout.strip() or "Release coordinator returned no result."
            return emit_error(args.action, message, args.json, 4 if completed.returncode else 1)
        if args.json:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
        else:
            render_human(response)
        return completed.returncode
    except (OSError, ValueError) as error:
        return emit_error(args.action, str(error), args.json)


raise SystemExit(main())
PY
