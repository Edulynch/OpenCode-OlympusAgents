"""Inspect managed global installations without becoming a global writer.

Global OpenCode and Codex installations have different roots and inventories.
This reader keeps that distinction explicit and never adopts an unowned file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import config_apply, install_routing


_MANIFEST = "olympus/orchestrator-install.json"
_OPENCODE_GUARD_INTENT = "olympus/opencode-guard-pending.json"
_HASH = re.compile(r"[0-9a-fA-F]{64}\Z")
_POWERSHELL_VERSION = re.compile(r"(?m)^PowerShell ([0-9]+)\.")
_CONFIG_PATH = re.compile(r"(?m)^\s*config\s{2,}(?P<path>.+?)\s*$")
_CODEX_INTRO = re.compile(
    r"This file is the Codex adapter's root representation:.*?Codex owns the user-facing result\.",
    re.DOTALL,
)
_GLOBAL_INTRO = (
    "This is the global Olympus root instruction and Kael identity. "
    "Start Codex with `codex --profile olympus` to use the global Olympus model and agent defaults. "
    "Project-local instructions and overrides remain in place and take precedence where Codex defines them."
)
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class GlobalFault(ValueError):
    """Keep unsupported global operations distinct from malformed requests."""

    def __init__(self, reason: str, message: str, code: int = 3):
        super().__init__(message)
        self.reason = reason
        self.code = code


def _root(path: Path) -> Path:
    if not path.is_absolute() or path == Path(path.anchor) or ".." in path.parts:
        raise GlobalFault("invalid_global_root", "A global configuration root must be an absolute, non-filesystem-root path.", 2)
    # Inspect each existing ancestor before opening the root; resolve() alone
    # would silently follow an untrusted junction or symlink.
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        try:
            meta = os.lstat(cursor)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise GlobalFault("unsafe_global_root", f"Cannot inspect global path component: {error}") from error
        if stat.S_ISLNK(meta.st_mode) or getattr(meta, "st_file_attributes", 0) & _REPARSE:
            raise GlobalFault("unsafe_global_root", "A global configuration root traverses a link or reparse point.")
        if not stat.S_ISDIR(meta.st_mode):
            raise GlobalFault("unsafe_global_root", "A global configuration path component is not a directory.")
    return path


def _opencode_root() -> Path:
    override = os.environ.get("OPENCODE_CONFIG_DIR")
    if override:
        return _root(Path(override))
    executable = shutil.which("opencode")
    if not executable:
        raise GlobalFault("global_path_unavailable", "OpenCode CLI is required to resolve its global config directory.")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        with tempfile.TemporaryDirectory(prefix="olympus-global-path-") as directory:
            found = subprocess.run(
                [executable, "debug", "paths"], cwd=directory, env=environment,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                check=False, timeout=10, shell=False,
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GlobalFault("global_path_unavailable", f"OpenCode path discovery was unavailable: {error}") from error
    paths = [match.group("path").strip() for match in _CONFIG_PATH.finditer(found.stdout or "")]
    if found.returncode or len(paths) != 1:
        raise GlobalFault("global_path_unavailable", "OpenCode did not report exactly one global config path.")
    return _root(Path(paths[0]))


def _codex_root() -> Path:
    return _root(Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))


def resolve_roots(selected: tuple[str, ...]) -> dict[str, Path]:
    roots = {name: _opencode_root() if name == "opencode" else _codex_root() for name in selected}
    if len(roots) == 2:
        left, right = roots["opencode"], roots["codex"]
        # A nested pair of roots could share the same manifest/resources; refuse
        # to report two independent owners where path isolation is unproven.
        if left == right or left in right.parents or right in left.parents:
            raise GlobalFault("overlapping_global_roots", "OpenCode and Codex global roots overlap; ownership is ambiguous.")
    return roots


def _expected(source: Path, renderer, selected: tuple[str, ...]) -> dict[str, dict[str, bytes]]:
    rendered = renderer.outputs_for(source, "all")
    outputs = {name: {} for name in selected}
    for file, content in rendered.items():
        if not file.is_relative_to(source) or not isinstance(content, str):
            raise GlobalFault("source_invalid", "Renderer produced an unsafe or non-text output.", 1)
        relative = file.relative_to(source).as_posix()
        harness, destination = None, None
        if relative.startswith(".opencode/agents/"):
            harness, destination = "opencode", relative.removeprefix(".opencode/")
        elif relative.startswith(".opencode/plugins/olympus-activity/"):
            harness, destination = "opencode", relative.removeprefix(".opencode/")
        elif relative.startswith(".codex/agents/"):
            harness, destination = "codex", relative.removeprefix(".codex/")
        elif relative == ".codex/config.toml":
            harness, destination = "codex", "olympus.config.toml"
        elif relative == "CODEX.md":
            harness, destination = "codex", "AGENTS.md"
            if len(_CODEX_INTRO.findall(content)) != 1:
                raise GlobalFault("source_invalid", "Codex root instructions lack the expected global adaptation anchor.", 1)
            content = _CODEX_INTRO.sub(_GLOBAL_INTRO, content, count=1)
        if harness in outputs:
            outputs[harness][destination] = content.encode("utf-8")
    if "opencode" in outputs:
        # The native global installer owns this guard only when no user config
        # existed. Both the installer and read-only CLI use these exact bytes.
        guard_path = source / "olympus/harnesses/opencode/global-permissions.jsonc"
        if not guard_path.is_file():
            raise GlobalFault("source_invalid", "Global permission guard template is missing.", 1)
        outputs["opencode"]["opencode.jsonc"] = guard_path.read_bytes()
    if ("opencode" in outputs and len(outputs["opencode"]) != 14) or ("codex" in outputs and len(outputs["codex"]) != 12):
        raise GlobalFault("source_inventory_unsupported", "Global renderer inventory differs from the official engine.")
    return outputs


def _read(root: Path, relative: str) -> bytes | None:
    raw, issue = config_apply._read_target_file(root, relative, max_bytes=2_000_000)
    if issue or (raw is not None and len(raw) > 2_000_000):
        raise GlobalFault("unsafe_global_resource", issue or f"Global resource exceeds the read limit: {relative}")
    return raw


def _manifest(root: Path, harness: str, expected: dict[str, bytes] | None):
    raw = _read(root, _MANIFEST)
    if raw is None:
        return None, {}, {}
    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate global manifest key: {key}")
            result[key] = value
        return result

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (ValueError, UnicodeError) as error:
        raise GlobalFault("invalid_global_manifest", "Global manifest is not valid JSON.") from error
    if (not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1
            or data.get("scope") != "global" or data.get("installed_harnesses") != [harness]
            or not isinstance(data.get("installed_version"), str) or not data["installed_version"]
            or not isinstance(data.get("installed_from_commit"), str) or not data["installed_from_commit"]
            or not isinstance(data.get("managed_files"), list)):
        raise GlobalFault("invalid_global_manifest", "Global manifest ownership, version or schema is unsupported.")
    # Only the local marker and official release tag grammar are interpretable.
    # An unknown string must not silently become an actionable global preview.
    if data["installed_version"] != "local" and install_routing._RELEASE_TAG.fullmatch(data["installed_version"]) is None:
        raise GlobalFault("unsupported_global_version", "Global manifest has an unsupported installed version.")
    entries: dict[str, str] = {}
    for item in data["managed_files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            raise GlobalFault("invalid_global_manifest", "Global manifest has a malformed managed resource.")
        path, digest = item["path"], item["sha256"]
        if (not path or "\\" in path or path.startswith("/") or
                any(part in ("", ".", "..") for part in path.split("/")) or
                path.casefold() in (existing.casefold() for existing in entries) or
                _HASH.fullmatch(digest) is None):
            raise GlobalFault("invalid_global_manifest", "Global manifest has a duplicate or unsafe managed resource.")
        if expected is not None and path not in expected:
            raise GlobalFault("unsupported_global_inventory", "Global manifest owns a resource outside the current adapter inventory.")
        entries[path] = digest.lower()
    if expected is not None:
        allowed_inventory = {frozenset(expected)}
        if harness == "opencode":
            # A pre-existing safe user-owned config is intentionally absent
            # from the manifest; older 13-resource installs use the same shape.
            allowed_inventory.add(frozenset(set(expected) - {"opencode.jsonc"}))
        if frozenset(entries) not in allowed_inventory:
            raise GlobalFault("unsupported_global_inventory", "Global manifest inventory does not match the current adapter inventory.")
    return data, entries, {"sha256": hashlib.sha256(raw).hexdigest(), "path": _MANIFEST}


def _verified_files(root: Path, entries: dict[str, str]) -> dict[str, bytes]:
    current: dict[str, bytes] = {}
    for path, digest in sorted(entries.items()):
        raw = _read(root, path)
        if raw is None or hashlib.sha256(raw).hexdigest() != digest:
            raise GlobalFault("global_managed_file_drift", f"Global managed resource is missing or changed: {path}", 1)
        current[path] = raw
    return current


def _jsonc_without_comments(raw: bytes) -> str:
    """Discard JSONC comments and trailing commas without touching string data."""
    text = raw.decode("utf-8")
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            output.append(char)
        elif char == "/" and next_char == "/":
            # Retain line endings so comments cannot merge adjacent tokens.
            while index < len(text) and text[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue
        elif char == "/" and next_char == "*":
            end = text.find("*/", index + 2)
            if end < 0:
                raise ValueError("Unterminated JSONC block comment")
            output.extend("\n" if c == "\n" else " " for c in text[index:end + 2])
            index = end + 2
            continue
        else:
            output.append(char)
        index += 1
    cleaned = "".join(output)
    result: list[str] = []
    in_string = escaped = False
    for index, char in enumerate(cleaned):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == ",":
            # Avoid allocating a full suffix for every comma in an untrusted
            # global config, which could otherwise produce quadratic work.
            lookahead = index + 1
            while lookahead < len(cleaned) and cleaned[lookahead].isspace():
                lookahead += 1
            if lookahead < len(cleaned) and cleaned[lookahead] in "}]":
                char = " "
        result.append(char)
    return "".join(result)


def _unowned_opencode_guard(root: Path) -> str:
    """Match the installer's safe-user-config contract before trusting a legacy inventory."""
    json_file = _read(root, "opencode.json")
    jsonc_file = _read(root, "opencode.jsonc")
    if json_file is not None and jsonc_file is not None:
        raise GlobalFault("global_external_guard_unsafe", "Both global OpenCode config formats exist; precedence is ambiguous.")
    raw = json_file if json_file is not None else jsonc_file
    if raw is None:
        return "missing"
    try:
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSONC field")
                result[key] = value
            return result

        def invalid_constant(value):
            raise ValueError(f"Invalid JSONC constant {value}")

        config = json.loads(_jsonc_without_comments(raw), object_pairs_hook=unique_pairs,
                            parse_constant=invalid_constant)
        rules = config["permissions"]
        if not isinstance(config, dict) or not isinstance(rules, list):
            raise ValueError("Global permissions must be an ordered V2 array")
        fallback = "allow"
        for rule in rules:
            if not isinstance(rule, dict) or not all(isinstance(rule.get(key), str)
                                                      for key in ("action", "resource", "effect")):
                raise ValueError("Malformed V2 global permission rule")
            if (not rule["action"] or not rule["resource"]
                    or rule["effect"] not in ("allow", "ask", "deny")):
                raise ValueError("Unsupported V2 global permission rule")
            # V2 documents only * and ? wildcards; fnmatch's bracket classes
            # would incorrectly accept a pattern V2 treats as literal.
            action_pattern = re.escape(rule["action"]).replace(r"\*", ".*").replace(r"\?", ".")
            # Unanchored ALLOW patterns can cover every external path even if
            # they contain punctuation (for example '?:/**' on Windows).
            # Only an explicit drive, Unix directory, UNC share, or home root
            # qualifies as a deliberately scoped user exception.
            normalized_resource = rule["resource"].replace("\\", "/")
            scoped = bool(re.match(r"^(?:[A-Za-z]:/|/[^/*?]+|//[^/*?]+/[^/*?]+|~/|\$HOME/)",
                                   normalized_resource))
            # '?' consumes exactly one character; it cannot establish a
            # global protective fallback after an earlier wildcard ALLOW.
            universal = bool(re.fullmatch(r"\*+", rule["resource"]))
            if ((universal or (rule["effect"] == "allow" and not scoped))
                    and re.fullmatch(action_pattern, "external_directory")):
                fallback = rule["effect"]
        if fallback not in ("ask", "deny"):
            raise ValueError("External directory fallback resolves to ALLOW")
    except (UnicodeError, ValueError, KeyError, TypeError) as error:
        raise GlobalFault("global_external_guard_unsafe", "Existing user OpenCode global config does not establish an external_directory ASK/DENY fallback.") from error
    return "safe_user_config"


def _assignments(installed: dict[str, dict[str, bytes]], expected: dict[str, dict[str, bytes]],
                 canonical: dict) -> dict:
    rows = []
    for row in canonical["roles"]:
        harnesses = {}
        for harness in ("opencode", "codex"):
            if harness not in installed:
                harnesses[harness] = {"state": "not_selected", "current_status": "unknown", "current": None, "proposed": None}
                continue
            if harness == "codex" and row["role"] == "kael":
                harnesses[harness] = {"state": "root", "current_status": "see_roots", "current": None, "proposed": None}
                continue
            path = f"agents/{row['role']}.{'md' if harness == 'opencode' else 'toml'}"
            raw, template = installed[harness].get(path), expected[harness].get(path)
            parsed = (config_apply._verified_opencode_agent(raw, template) if harness == "opencode"
                      else config_apply._verified_codex(raw)) if raw is not None and template is not None else None
            harnesses[harness] = {"state": "selected", "current_status": "verified" if parsed else "unsupported",
                                   "current": parsed, "proposed": {"model": row["models"][harness], "effort": row["effort"]}}
        rows.append({"role": row["role"], "identity": row["identity"],
                     "family": {"current": "unknown", "proposed": row["family"]}, "harnesses": harnesses})
    roots = {"opencode": {"state": "not_managed", "current": None, "proposed": None}}
    if "codex" in installed:
        parsed = config_apply._verified_codex(installed["codex"].get("olympus.config.toml", b""))
        kael = next(row for row in canonical["roles"] if row["role"] == "kael")
        roots["codex"] = {"state": "selected", "current_status": "verified" if parsed else "unsupported",
                          "current": parsed, "proposed": {"model": kael["models"]["codex"], "effort": kael["effort"]}}
    else:
        roots["codex"] = {"state": "not_selected", "current_status": "unknown", "current": None, "proposed": None}
    statuses = [representation["current_status"] for role in rows
                for representation in role["harnesses"].values()
                if representation["current_status"] in ("verified", "unsupported")]
    statuses.extend(item["current_status"] for item in roots.values()
                    if item.get("current_status") in ("verified", "unsupported"))
    verified = statuses.count("verified")
    return {"status": "partial" if verified and "unsupported" in statuses else
            "unsupported" if "unsupported" in statuses else "verified",
            "evidence": "managed_hash_verified_bytes", "family": "unknown", "proposal_source": "canonical_renderer",
            "selected_harnesses": list(installed), "preserved_harnesses": [], "roles": rows, "roots": roots}


def _native_failure_reason(stdout: str, harness: str) -> tuple[str, str, int]:
    """Translate only the official harness failure marker into stable CLI results."""
    failures = {
        "GLOBAL_MANAGED_FILE_DRIFT": ("drift", "global_managed_file_drift", 1),
        "GLOBAL_VERSION_DRIFT": ("version_mismatch", "version_mismatch", 3),
        "GLOBAL_MANIFEST_INVALID": ("invalid_manifest", "invalid_global_manifest", 3),
        "GLOBAL_INSTALL_CONFLICT": ("conflict", "global_install_conflict", 3),
    }
    prefix = f"GLOBAL_HARNESS_FAILED: {harness} "
    for line in stdout.splitlines():
        if line.startswith(prefix):
            marker = line[len(prefix):].partition(":")[0]
            return failures.get(marker, ("unavailable", "native_verify_unavailable", 3))
    return "unavailable", "native_verify_unavailable", 3


def _native_verify(source: Path, root: Path, harness: str, version: str) -> tuple[str, str, str | None, int]:
    if sys.platform != "win32":
        return "unavailable", "Global native VerifyOnly is qualified only on Windows.", "native_verify_unavailable", 3
    executable = shutil.which("pwsh")
    if executable is None or not (source / "scripts/global-install.ps1").is_file():
        return "unavailable", "PowerShell 7 or the official global verifier is unavailable.", "native_verify_unavailable", 3
    # Root overrides pin the same audited target while USERPROFILE contains
    # PowerShell's startup cache outside the real user profile.
    with tempfile.TemporaryDirectory(prefix="olympus-global-verify-") as profile:
        env = os.environ.copy()
        env["USERPROFILE"] = profile
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["OPENCODE_CONFIG_DIR" if harness == "opencode" else "CODEX_HOME"] = str(root)
        try:
            probe = subprocess.run(
                [executable, "-Version"], env=env, cwd=source, capture_output=True,
                text=True, encoding="utf-8", errors="replace", check=False,
                timeout=10, shell=False,
            )
            match = _POWERSHELL_VERSION.search(probe.stdout or "")
            if probe.returncode != 0 or match is None or int(match.group(1)) < 7:
                return "unavailable", "The native verifier requires PowerShell 7 or later.", "native_verify_unavailable", 3
            result = subprocess.run(
                [executable, "-NoProfile", "-NonInteractive", "-File", str(source / "scripts/global-install.ps1"),
                 "-Harness", harness, "-SourceVersion", version, "-VerifyOnly"],
                env=env, cwd=source, capture_output=True, text=True, encoding="utf-8", errors="replace",
                check=False, timeout=30, shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return "unavailable", f"Global native verifier could not finish: {error}", "native_verify_unavailable", 3
    line = f"OLYMPUS_GLOBAL_VERIFY: {harness} {version} PASS"
    if result.returncode == 0 and any(item.startswith(line + " (") for item in result.stdout.splitlines()):
        return "verified", "Official global VerifyOnly passed.", None, 0
    state, issue_code, exit_code = _native_failure_reason(result.stdout, harness)
    return state, "Official global VerifyOnly did not pass; see the reported failure category.", issue_code, exit_code


def inspect(source: Path, args, response: dict, *, source_query: Callable, load_renderer: Callable,
            release_version: Callable, assignment_query: Callable, operation: str) -> int:
    """Report each global harness independently and preserve the original failure."""
    selected = ("opencode", "codex") if args.harness == "all" else (args.harness,)
    response.update({"operation": operation, "context": {"scope": "global", "harness": args.harness, "source": str(source)},
                     "data": {"harnesses": {}, "runtime_discovery": "not_performed"}, "issues": []})
    if getattr(args, "target", None) is not None:
        response["result"] = "failed"
        response["issues"] = [{"code": "invalid_target", "message": "--target is incompatible with --scope global."}]
        return 2
    if operation == "config apply" and getattr(args, "execute", False):
        response["result"] = "blocked"
        response["issues"] = [{"code": "global_execute_unavailable", "message": "Global apply requires a separate writer/rollback qualification; no execution is enabled."}]
        return 3
    try:
        roots = resolve_roots(selected)
        expected = None
        if operation != "status":
            source_data, issues = source_query(source, "config check", args.harness)
            if issues or not source_data.get("coherent"):
                raise GlobalFault("source_drift", "Canonical generated source is not coherent with the renderer.")
            renderer = load_renderer(source)
            expected = _expected(source, renderer, selected)
            if "opencode" in expected:
                from . import user_config

                user_config.apply_to_expected(source, expected["opencode"])
        current_by_harness: dict[str, dict[str, bytes]] = {}
        changes: list[dict[str, str]] = []
        absent, blocked = [], []
        failure_codes: list[int] = []
        for harness in selected:
            root = roots[harness]
            response["data"]["harnesses"][harness] = {"root": str(root), "state": "unverified"}
            try:
                manifest, entries, meta = _manifest(root, harness, expected[harness] if expected else None)
                if manifest is None:
                    absent.append(harness)
                    response["data"]["harnesses"][harness]["state"] = "absent"
                    continue
                item = response["data"]["harnesses"][harness]
                item.update({"manifest": meta, "installed_version": manifest["installed_version"],
                             "installed_from_commit": manifest["installed_from_commit"], "managed_files": len(entries)})
                if operation == "status":
                    item["state"] = "reported"
                    item["integrity"] = "unverified"
                    continue
                current = _verified_files(root, entries)
                current_by_harness[harness] = current
                item["integrity"] = "hash_verified"
                if harness == "opencode":
                    if _read(root, _OPENCODE_GUARD_INTENT) is not None:
                        # The Windows writer owns pending recovery; a read-only
                        # preview must not declare an interrupted install done.
                        raise GlobalFault("global_guard_recovery_pending", "An OpenCode guard transaction is pending; rerun the global installer to reconcile ownership.")
                    if "opencode.jsonc" not in entries:
                        guard_state = _unowned_opencode_guard(root)
                        item["external_guard"] = guard_state
                        if guard_state == "missing" and operation == "config apply":
                            changes.append({"harness": "opencode", "path": "opencode.jsonc", "action": "create",
                                            "proposed_sha256": hashlib.sha256(expected[harness]["opencode.jsonc"]).hexdigest()})
                if harness == "codex":
                    # The native installer refuses this user-owned, higher-priority
                    # instruction file, even if every Olympus-managed byte matches.
                    _, override, override_issue = config_apply._lstat_target_path(root, "AGENTS.override.md")
                    if override_issue:
                        raise GlobalFault("unsafe_global_resource", override_issue)
                    if override is not None:
                        raise GlobalFault("global_install_conflict", "Global Codex AGENTS.override.md takes precedence over managed AGENTS.md.")
                if operation == "doctor":
                    version = "local" if manifest["installed_version"] == "local" else release_version(source)
                    state, detail, issue_code, exit_code = _native_verify(source, root, harness, version)
                    item.update({"state": state, "verification": detail})
                    if state != "verified":
                        blocked.append(harness)
                        failure_codes.append(exit_code)
                        response["issues"].append({"code": issue_code,
                                                   "message": detail, "harness": harness})
                else:
                    item["state"] = "ready"
                    for path, desired in sorted(expected[harness].items()):
                        if path not in current:
                            # Preserve pre-existing user config and historical
                            # 13-file inventories; native VerifyOnly handles
                            # their safety in the supported Windows runtime.
                            continue
                        if current[path] != desired:
                            changes.append({"harness": harness, "path": path, "action": "update",
                                            "current_sha256": hashlib.sha256(current[path]).hexdigest(),
                                            "proposed_sha256": hashlib.sha256(desired).hexdigest()})
            except GlobalFault as error:
                blocked.append(harness)
                failure_codes.append(error.code)
                response["data"]["harnesses"][harness]["state"] = "drift" if error.code == 1 else "blocked"
                response["issues"].append({"code": error.reason, "message": str(error), "harness": harness})
        response["data"]["selection_state"] = "partial" if absent and len(absent) != len(selected) else "absent" if absent else "complete"
        if absent and len(absent) != len(selected):
            response["issues"].append({"code": "harness_absent", "message": "At least one selected global harness is not installed."})
        if operation == "config apply":
            response["data"].update({"preview_only": True, "apply_available": False, "changes": changes,
                                     "assignments": {"status": "unknown", "evidence": "not_verified", "roles": [], "roots": {}}})
            if not blocked and not absent:
                response["data"]["assignments"] = _assignments(current_by_harness, expected, assignment_query(load_renderer(source), source))
        if blocked:
            code = 3 if 3 in failure_codes else 1
            response["result"] = "blocked" if code == 3 else "failed"
            return code
        if absent:
            response["result"] = "absent"
            return 0
        response["result"] = "no_changes" if operation == "config apply" and not changes else "ok"
        return 0
    except GlobalFault as error:
        response["result"] = "failed" if error.code == 1 else "blocked" if error.code == 3 else "failed"
        response["issues"].append({"code": error.reason, "message": str(error)})
        return error.code
