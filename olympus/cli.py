"""Portable, offline Olympus queries and explicit source-model edits."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


class CLIError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CLIError(f"{message}. See olympus --help.", 2)


def parser() -> Parser:
    root = Parser(
        prog="olympus",
        description="Offline Olympus CLI. Python 3.11+; trusted checkout; no provider calls.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Examples:\n"
                "  olympus models list --json\n"
                "  olympus models set-family sol --opencode openai/new-sol --codex codex/new-sol --dry-run --json\n"
                "  olympus agents set-model veyra --effort high --dry-run\n"
                "  olympus config recover\n"
                "  olympus config check\n"
                "  olympus status --scope project --target <absolute-worktree-root>\n"
                "Edits affect only the canonical source checkout; installed-target application is separate.\n"
                "Queries do not verify installations or model availability.\n"
                "macOS is not verified."),
        allow_abbrev=False,
    )
    root.add_argument("--source", type=Path, help="absolute trusted source checkout (before command)")
    root.add_argument("--version", action="store_true", help="show the source release version")
    commands = root.add_subparsers(dest="command", parser_class=Parser)
    models = commands.add_parser("models", help="query or explicitly edit canonical model assignments", allow_abbrev=False)
    model_commands = models.add_subparsers(dest="action", required=True, parser_class=Parser)
    listing = model_commands.add_parser("list", help="list all twelve roles and both adapters", allow_abbrev=False)
    listing.add_argument("--json", action="store_true")
    set_family = model_commands.add_parser("set-family", help="explicitly edit both IDs of an existing family", allow_abbrev=False)
    set_family.add_argument("family")
    set_family.add_argument("--opencode", required=True)
    set_family.add_argument("--codex", required=True)
    set_family.add_argument("--dry-run", action="store_true")
    set_family.add_argument("--json", action="store_true", help="JSON preview; requires --dry-run")
    agents = commands.add_parser("agents", help="edit canonical role model intent", allow_abbrev=False)
    agent_commands = agents.add_subparsers(dest="action", required=True, parser_class=Parser)
    set_model = agent_commands.add_parser("set-model", help="explicitly edit an existing role", allow_abbrev=False)
    set_model.add_argument("role")
    set_model.add_argument("--family")
    set_model.add_argument("--effort")
    set_model.add_argument("--dry-run", action="store_true")
    set_model.add_argument("--json", action="store_true", help="JSON preview; requires --dry-run")
    config = commands.add_parser("config", help="check local source and generated outputs", allow_abbrev=False)
    config_commands = config.add_subparsers(dest="action", required=True, parser_class=Parser)
    check = config_commands.add_parser("check", help="compare renderer outputs without writing", allow_abbrev=False)
    check.add_argument("--harness", choices=("opencode", "codex", "all"), default="all")
    check.add_argument("--json", action="store_true")
    config_commands.add_parser("recover", help="explicitly recover one pending source-edit batch", allow_abbrev=False)
    status = commands.add_parser("status", help="read reported installation metadata; no integrity verification", allow_abbrev=False)
    status.add_argument("--scope", choices=("project", "global"), default="project")
    status.add_argument("--target", type=Path, help="absolute Git worktree root; required for project scope")
    status.add_argument("--harness", choices=("opencode", "codex", "all"), default="all")
    status.add_argument("--json", action="store_true")
    return root


def source_root(requested: Path | None) -> Path:
    candidate = requested if requested is not None else Path(__file__).resolve().parents[1]
    if not candidate.is_absolute():
        raise CLIError("--source must be an absolute trusted checkout path", 2)
    source = candidate.resolve()
    for relative in ("olympus/core/models.toml", "scripts/render_harnesses.py", "install.ps1"):
        if not (source / relative).is_file():
            raise CLIError(f"Invalid source: missing {source / relative}", 2)
        if not (source / relative).resolve().is_relative_to(source):
            raise CLIError(f"Source resource escapes checkout: {source / relative}", 3)
    return source


def recovery_source_root(requested: Path | None) -> Path:
    """Resolve recovery's source context without preflighting models or batch state."""
    candidate = requested if requested is not None else Path(__file__).resolve().parents[1]
    if not candidate.is_absolute():
        raise CLIError("--source must be an absolute trusted checkout path", 2)
    try:
        source = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise CLIError(f"Invalid recovery source: {candidate}", 2) from error
    if not source.is_dir():
        raise CLIError(f"Recovery source is not a directory: {source}", 2)
    return source


def release_version(source: Path) -> str:
    # Reuse the existing release identity; do not execute the installer.
    text = (source / "install.ps1").read_text(encoding="utf-8")
    default = re.search(r"(?m)^\s*\[string\]\$Version\s*=\s*'([^']+)'\s*,?\s*$", text)
    marker = re.search(r"(?m)^\s*\$ReleaseVersion\s*=\s*'([^']+)'\s*(?:#.*)?$", text)
    if default is None or marker is None or default[1] != marker[1]:
        raise CLIError("Source release identity is missing or contradictory in install.ps1")
    if re.fullmatch(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?", marker[1]) is None:
        raise CLIError("Source release identity in install.ps1 is malformed")
    return marker[1]


def load_renderer(source: Path):
    path = source / "scripts" / "render_harnesses.py"
    if not path.resolve().is_relative_to(source):
        raise CLIError(f"Renderer escapes trusted source: {path}", 3)
    spec = importlib.util.spec_from_file_location("olympus_source_renderer", path)
    if spec is None or spec.loader is None:
        raise CLIError(f"Cannot load canonical renderer: {path}")
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    return renderer


def model_assignments(renderer, source: Path) -> dict:
    # checked_sources uses tomllib and validates the single canonical registry.
    models, _, _, identities, roles = renderer.checked_sources(source)
    if len(roles) != 12:
        raise CLIError(f"Expected twelve canonical roles, found {len(roles)}")
    rows = []
    for role in sorted(roles):
        resolved = {}
        for harness in ("opencode", "codex"):
            model, effort = renderer.role_model(models, role, harness)
            if not isinstance(model, str) or not model.strip() or any(ord(c) < 32 or ord(c) == 127 for c in model):
                raise CLIError(f"Invalid {harness} model identifier for {role}")
            resolved[harness] = model
        if not isinstance(effort, str) or not effort.strip():
            raise CLIError(f"Invalid canonical effort for {role}")
        rows.append({"role": role, "identity": identities[role],
                     "family": models["roles"][role]["family"], "effort": effort,
                     "models": resolved,
                     "representation": {"opencode": "agent", "codex": "root" if role == "kael" else "absent" if role == "aegis" else "agent"}})
    return {"roles": rows}


def source_query(source: Path, operation: str, harness: str) -> tuple[dict, list[dict]]:
    renderer = load_renderer(source)
    try:
        assignments = model_assignments(renderer, source)
        if operation == "models list":
            return assignments, []
        expected = renderer.outputs_for(source, harness)
        issues = []
        for path, content in sorted(expected.items(), key=lambda pair: pair[0].as_posix()):
            if not path.resolve().is_relative_to(source):
                raise CLIError(f"Generated output escapes source: {path}", 3)
            relative = path.relative_to(source).as_posix()
            if not path.is_file():
                issues.append({"code": "missing", "message": f"Missing generated output: {relative}", "path": relative})
            elif renderer.read_text(path) != content:
                issues.append({"code": "drift", "message": f"Generated output differs from renderer: {relative}", "path": relative})
        return {"harness": harness, "managed_outputs": len(expected),
                "coherent": not issues, "installation_verification": "not_performed",
                "model_availability": "unknown"}, issues
    except (renderer.RenderError, KeyError, TypeError, ValueError, AttributeError) as error:
        raise CLIError(f"Invalid canonical source or renderer input: {error}") from error


def installation_status(args, response: dict) -> int:
    response["context"].update({"kind": "installation_metadata", "scope": args.scope,
                                "harness": args.harness})
    response["data"] = {"installed_harnesses": [], "integrity": "unverified",
                        "ownership": "unverified", "assignments": "unknown",
                        "runtime_validation": "not_performed", "evidence": "none"}
    if args.scope == "global":
        if args.target is not None:
            raise CLIError("--target is incompatible with --scope global", 2)
        response["context"]["target"] = "unknown"
        raise CLIError("Global location is unresolved: Slice A does not perform native discovery. Use explicit project scope for available metadata.", 3)
    if args.target is None or not args.target.is_absolute():
        raise CLIError("Project status requires --target <absolute-worktree-root>", 2)
    target = args.target.resolve()
    if not target.is_dir() or not ((target / ".git").is_dir() or (target / ".git").is_file()):
        raise CLIError(f"Target must be a Git worktree root with a .git marker: {target}", 2)
    response["context"]["target"] = str(target)
    manifests = [target / f".{harness}" / "orchestrator-install.json" for harness in ("opencode", "codex")]
    present = [path for path in manifests if path.exists() or path.is_symlink()]
    if not present:
        response["result"] = "absent"
        response["data"]["installation_state"] = "absent"
        return 0
    response["data"]["manifests"] = [str(path) for path in present]
    if len(present) != 1:
        response["data"]["installation_state"] = "contradictory"
        raise CLIError("Both project manifest locations exist; reported ownership metadata is ambiguous", 3)
    path = present[0]
    if not path.resolve().is_relative_to(target):
        raise CLIError(f"Manifest escapes the selected target: {path}", 3)
    response["data"]["installation_state"] = "invalid"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeError, OSError) as error:
        raise CLIError(f"Cannot read installation metadata at {path}: {error}") from error
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1 or not isinstance(manifest.get("managed_files"), list):
        raise CLIError(f"Unsupported manifest schema or managed_files at {path}")
    if manifest.get("scope", "project") != "project":
        raise CLIError(f"Contradictory project manifest scope at {path}", 3)
    # Existing project engines recognize older OpenCode-only metadata without inventory.
    installed = manifest.get("installed_harnesses", ["opencode"])
    if not isinstance(installed, list) or not installed or any(value not in ("opencode", "codex") for value in installed) or len(installed) != len(set(installed)):
        raise CLIError(f"Invalid installed_harnesses metadata at {path}")
    expected_location = manifests[0] if "opencode" in installed else manifests[1]
    if path != expected_location:
        raise CLIError(f"Manifest location contradicts its reported harness inventory: {path}", 3)
    version = manifest.get("installed_version", "unknown")
    commit = manifest.get("installed_from_commit", "unknown")
    if not isinstance(version, str) or not version or not isinstance(commit, str):
        raise CLIError(f"Invalid recorded release metadata at {path}")
    response["data"].update({"installation_state": "reported", "installed_harnesses": installed,
                             "recorded_version": version, "recorded_source_commit": commit,
                             "evidence": "reported_manifest",
                             "metadata_format": "legacy" if "installed_harnesses" not in manifest else "current"})
    selected = ("opencode", "codex") if args.harness == "all" else (args.harness,)
    response["data"]["harnesses"] = {name: "reported" if name in installed else "absent" for name in selected}
    if not any(name in installed for name in selected):
        response["result"] = "absent"
    return 0


def emit(response: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(response, ensure_ascii=False))
        return
    print(f"{response['operation']}: {response['result']}")
    for key, value in response["context"].items():
        print(f"{key}: {value}")
    # Human presentation uses the same data objects as JSON, with no resolver.
    for key, value in response["data"].items():
        if key == "roles":
            for role in value:
                print(f"{role['role']} | {role['identity']} | family={role['family']} | effort={role['effort']} | "
                      f"opencode={role['models']['opencode']} ({role['representation']['opencode']}) | "
                      f"codex={role['models']['codex']} ({role['representation']['codex']})")
        else:
            print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    for issue in response["issues"]:
        print(f"{issue['code']}: {issue['message']}", file=sys.stderr)


def _model_edit_error_code(error) -> int:
    """Keep invalid requests distinct from source/dependency conflicts."""
    message = str(error)
    invalid_request_prefixes = (
        "Invalid proposed", "Invalid existing", "Unknown model family",
        "Unknown canonical role", "Family name must", "Role must",
        "At least one of family or effort", "Effort is not present",
        "Proposed family", "Proposed effort", "Model family has no canonical roles",
        "Unauthorized or missing TOML scalar path", "Only existing three-part",
    )
    return 2 if message.startswith(invalid_request_prefixes) else 3


def _batch_error_code(error, source_edit, *, recovery: bool = False) -> int:
    if isinstance(error, source_edit.BatchConflict):
        return 3
    if isinstance(error, source_edit.BatchBlocked):
        message = str(error).lower()
        if ("unconfirmed" in message or "could not be confirmed" in message
                or "committed but post-commit" in message
                or "cannot remove verified batch temporary" in message
                or "cannot remove nonempty or changed batch directory" in message
                or "cannot remove empty pending scratch" in message
                or "pending scratch gained unenumerated resources" in message):
            return 4
        if recovery:
            confirmed_blockers = (
                "recovery requires the existing stable lock", "pending scratch",
                "batch record", "unsupported batch", "batch read_set", "batch target",
                "batch backup/staged", "required batch backup/staged", "missing batch resource",
                "unsafe source-relative path", "unsafe", "cannot inspect", "cannot enumerate",
                "cannot validate canonical renderer", "different canonical source",
            )
            if not any(marker in message for marker in confirmed_blockers):
                # Recovery may have restored some targets or partially cleaned
                # a terminal batch before an operational error. Do not flatten
                # that outcome into a confirmed blocked/no-change result.
                return 4
        return 3
    if isinstance(error, source_edit.BatchError):
        return 1  # The transaction reports this only after a confirmed rollback.
    if isinstance(error, source_edit.LockIdentityError):
        return 4
    if isinstance(error, source_edit.LockError):
        return 3
    return 1


def _adopt_preview(response: dict, preview: dict) -> None:
    response.clear()
    response.update(preview)


def _run_model_edit(source: Path, args, response: dict) -> int:
    # Both modules are intentionally imported only after argparse and source
    # context validation. TOML Kit itself remains lazy inside model_edit.
    from . import model_edit, source_edit

    try:
        if args.command == "models":
            candidate = model_edit._build_set_family_candidate(
                source, args.family, args.opencode, args.codex,
            )
        else:
            if args.family is None and args.effort is None:
                raise CLIError("agents set-model requires --family and/or --effort", 2)
            candidate = model_edit._build_set_role_candidate(
                source, args.role, family=args.family, effort=args.effort,
            )
    except model_edit.ModelEditError as error:
        raise CLIError(str(error), _model_edit_error_code(error)) from error

    preview = dict(candidate.preview)
    preview_context = dict(preview["context"])
    if (source / ".olympus-cli-edit").exists():
        preview_context["source_edit"] = "unconfirmed; explicit recovery required"
    preview["context"] = preview_context
    _adopt_preview(response, preview)

    if args.dry_run:
        if args.json:
            print(json.dumps(response, ensure_ascii=False))
        else:
            print(model_edit._format_preview_human(preview))
        return 0

    # Execution is the explicit command without --dry-run. Show the exact
    # candidate before staging or replacing any target; no extra prompt.
    print("Execution preview (not yet applied):")
    print(model_edit._format_preview_human(preview))
    try:
        prepared = source_edit._prepare_batch(candidate)
        if prepared is None:
            response["result"] = "no_changes"
            print("execution: no_changes")
            return 0
        result = source_edit._commit_batch(prepared)
        if result != "committed":
            response["result"] = "unconfirmed"
            raise CLIError(f"Batch returned unexpected execution state: {result}", 4)
    except source_edit.BatchError as error:
        code = _batch_error_code(error, source_edit)
        response["result"] = {1: "failed", 3: "blocked", 4: "unconfirmed"}[code]
        raise CLIError(str(error), code) from error
    except source_edit.LockError as error:
        code = _batch_error_code(error, source_edit)
        response["result"] = "unconfirmed" if code == 4 else "blocked"
        raise CLIError(str(error), code) from error
    print("execution: committed")
    return 0


def _run_recovery(source: Path, response: dict) -> int:
    # Recovery is stdlib-only and acquires the existing stable lock before its
    # implementation inspects the record, backups, or targets.
    from . import source_edit

    try:
        result = source_edit._recover_batch(source)
    except source_edit.BatchError as error:
        code = _batch_error_code(error, source_edit, recovery=True)
        response["result"] = {1: "failed", 3: "blocked", 4: "unconfirmed"}[code]
        raise CLIError(str(error), code) from error
    except source_edit.LockError as error:
        code = _batch_error_code(error, source_edit, recovery=True)
        response["result"] = "unconfirmed" if code == 4 else "blocked"
        raise CLIError(str(error), code) from error
    response["operation"] = "config recover"
    response["result"] = "no_changes" if result == "no_changes" else "ok"
    response["data"] = {"recovery": result}
    print(f"config recover: {result}")
    print(f"source: {source}")
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    response = {"schema_version": 1, "operation": "arguments", "result": "ok",
                "context": {}, "data": {}, "issues": []}
    as_json = "--json" in arguments
    try:
        cli_parser = parser()
        args = cli_parser.parse_args(arguments)
        if args.version and args.command:
            raise CLIError("--version cannot be combined with a command", 2)
        if not args.version and not args.command:
            cli_parser.error("a command is required")
        operation = "version" if args.version else " ".join(
            filter(None, (args.command, getattr(args, "action", None)))
        )
        response["operation"] = operation
        if operation in ("models set-family", "agents set-model") and args.json and not args.dry_run:
            raise CLIError("--json for model edits requires --dry-run", 2)
        if args.command == "agents" and args.action == "set-model" and args.family is None and args.effort is None:
            raise CLIError("agents set-model requires --family and/or --effort", 2)
        source = recovery_source_root(args.source) if operation == "config recover" else source_root(args.source)
        response["context"] = {"source": str(source), "kind": "canonical_source"}
        if operation != "config recover" and (source / ".olympus-cli-edit").exists():
            response["context"]["source_edit"] = "unconfirmed; not repaired"
        if args.version:
            print(f"olympus {release_version(source)} (source: {source})")
            return 0
        if response["operation"] in ("models list", "config check"):
            harness = getattr(args, "harness", "all")
            response["context"]["harness"] = harness
            response["data"], response["issues"] = source_query(source, response["operation"], harness)
            if response["issues"]:
                response["result"] = "failed"
            emit(response, as_json)
            return 1 if response["issues"] else 0
        if response["operation"] in ("models set-family", "agents set-model"):
            return _run_model_edit(source, args, response)
        if response["operation"] == "config recover":
            return _run_recovery(source, response)
        code = installation_status(args, response)
        emit(response, as_json)
        return code
    except CLIError as error:
        if error.code == 3:
            response["result"] = "blocked"
        elif error.code == 4:
            response["result"] = "unconfirmed"
        else:
            response["result"] = "failed"
        response["issues"].append({
            "code": "invalid_arguments" if error.code == 2 else "query_failed",
            "message": str(error),
        })
        emit(response, as_json)
        return error.code
    except (OSError, UnicodeError) as error:
        response["result"] = "failed"
        response["issues"].append({"code": "read_failed", "message": str(error)})
        emit(response, as_json)
        return 1
    except KeyboardInterrupt:
        response["result"] = "unconfirmed"
        response["issues"].append({
            "code": "unconfirmed",
            "message": "Operation interrupted; inspect/recover pending source-edit state explicitly.",
        })
        emit(response, as_json)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
