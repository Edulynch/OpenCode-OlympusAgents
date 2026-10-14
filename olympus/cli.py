"""Portable, offline, read-only Olympus commands using the canonical renderer."""

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
        description="Read-only Olympus CLI. Python 3.11+; trusted checkout; offline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Examples:\n"
                "  olympus models list --json\n"
                "  olympus config check\n"
                "  olympus status --scope project --target <absolute-worktree-root>\n"
                "Source queries do not verify installations or model availability.\n"
                "macOS is not verified."),
        allow_abbrev=False,
    )
    root.add_argument("--source", type=Path, help="absolute trusted source checkout (before command)")
    root.add_argument("--version", action="store_true", help="show the source release version")
    commands = root.add_subparsers(dest="command", parser_class=Parser)
    models = commands.add_parser("models", help="query canonical model assignments", allow_abbrev=False)
    model_commands = models.add_subparsers(dest="action", required=True, parser_class=Parser)
    listing = model_commands.add_parser("list", help="list all twelve roles and both adapters", allow_abbrev=False)
    listing.add_argument("--json", action="store_true")
    config = commands.add_parser("config", help="check local source and generated outputs", allow_abbrev=False)
    config_commands = config.add_subparsers(dest="action", required=True, parser_class=Parser)
    check = config_commands.add_parser("check", help="compare renderer outputs without writing", allow_abbrev=False)
    check.add_argument("--harness", choices=("opencode", "codex", "all"), default="all")
    check.add_argument("--json", action="store_true")
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
        response["operation"] = "version" if args.version else " ".join(filter(None, (args.command, getattr(args, "action", None))))
        source = source_root(args.source)
        response["context"] = {"source": str(source), "kind": "canonical_source"}
        if (source / ".olympus-cli-edit").exists():
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
        code = installation_status(args, response)
        emit(response, as_json)
        return code
    except CLIError as error:
        response["result"] = "blocked" if error.code == 3 else "failed"
        response["issues"].append({"code": "invalid_arguments" if error.code == 2 else "query_failed", "message": str(error)})
        emit(response, as_json)
        return error.code
    except (OSError, UnicodeError) as error:
        response["result"] = "failed"
        response["issues"].append({"code": "read_failed", "message": str(error)})
        emit(response, as_json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
