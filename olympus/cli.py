"""Portable, offline Olympus queries and explicit configuration previews/edits."""

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
    help_notes = (
        "Model IDs use the exact provider/model-id form listed at https://models.dev. "
        "Olympus validates declared catalog capabilities but never verifies model access, credentials, or subscriptions. "
        "Use 'olympus config list' for absolute configuration paths and precedence. "
        "Apply manual edits with 'olympus install' (global) or 'olympus update' (project); "
        "then run 'olympus doctor', which only verifies configuration."
    )
    root = Parser(
        prog="olympus",
        description="Olympus global CLI. Python 3.11+ is used internally; no model-provider calls are made.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Examples:\n"
                "  olympus version\n"
                "  olympus update\n"
                "  olympus agents list\n"
                "  olympus nox set-model openai/gpt-6-luna\n"
                "  olympus nox set-effort high\n"
                "  olympus config list\n"
                "  olympus doctor\n"
                "  olympus install\n"
                "  olympus uninstall\n"
                "  olympus models list --json\n"
                "  olympus models set-family sol --opencode openai/new-sol --codex codex/new-sol --dry-run --json\n"
                "  olympus agents set-model veyra --effort high --dry-run\n"
                "  olympus config recover\n"
                "  olympus config check\n"
                "  olympus config apply --scope project --target <absolute-worktree-root> --harness opencode --dry-run\n"
                "  olympus config apply --scope project --target <absolute-worktree-root> --harness opencode --execute\n"
                "  olympus config apply --scope global --harness opencode --execute\n"
                "  olympus config recover --scope global --harness opencode\n"
                "  olympus install --scope project --target <absolute-worktree-root> --harness opencode --version <release-tag> --dry-run\n"
                "  olympus uninstall --scope project --target <absolute-worktree-root> --harness opencode --execute\n"
                "  olympus doctor --scope project --target <absolute-worktree-root> --harness all [--json]\n"
                "  olympus doctor --scope global --harness opencode [--json]\n"
                "  olympus config apply --scope global --harness codex --dry-run --json\n"
                 "  olympus status --scope project --target <absolute-worktree-root>\n"
                 "Source-edit and project-apply commands are advanced checkout operations.\n"
                 "Config apply writes only with --execute; global execution currently supports OpenCode only.\n"
                 "Doctor performs static configuration checks; it never probes a model provider.\n"
                 + help_notes),
        allow_abbrev=False,
    )
    root.add_argument("--source", type=Path, help="absolute trusted source checkout (before command)")
    root.add_argument("--version", action="store_true", help="show the source release version")
    commands = root.add_subparsers(dest="command", parser_class=Parser)
    commands.add_parser("help", help="show Olympus commands and model configuration guidance", allow_abbrev=False)
    commands.add_parser("version", help="show the installed Olympus product version", allow_abbrev=False)
    update = commands.add_parser("update", aliases=["upgrade"], help="update the managed current project or global installation", allow_abbrev=False)
    update.add_argument("--scope", choices=("project", "global"), help="select a managed project or global installation (default: effective scope)")
    update.add_argument("--target", type=Path, help="absolute managed project worktree root; project scope only")
    models = commands.add_parser("models", help="query or explicitly edit canonical model assignments", allow_abbrev=False)
    model_commands = models.add_subparsers(dest="action", required=True, parser_class=Parser)
    listing = model_commands.add_parser("list", help="list all eleven roles and both adapters", allow_abbrev=False)
    listing.add_argument("--json", action="store_true")
    set_family = model_commands.add_parser("set-family", help="explicitly edit both IDs of an existing family", allow_abbrev=False)
    set_family.add_argument("family")
    set_family.add_argument("--opencode", required=True)
    set_family.add_argument("--codex", required=True)
    set_family.add_argument("--dry-run", action="store_true")
    set_family.add_argument("--json", action="store_true", help="JSON preview; requires --dry-run")
    agents = commands.add_parser("agents", help="list effective agents or edit canonical role model intent", allow_abbrev=False)
    agent_commands = agents.add_subparsers(dest="action", required=True, parser_class=Parser)
    agent_list = agent_commands.add_parser("list", help="list effective models, efforts, and sources", allow_abbrev=False)
    agent_list.add_argument("--json", action="store_true")
    agent_list.add_argument("--scope", choices=("project", "global"), help="select scope (default: effective scope)")
    agent_list.add_argument("--target", type=Path, help="absolute managed project worktree root; project scope only")
    set_model = agent_commands.add_parser("set-model", help="explicitly edit an existing role", allow_abbrev=False)
    set_model.add_argument("role")
    set_model.add_argument("--family")
    set_model.add_argument("--effort")
    set_model.add_argument("--dry-run", action="store_true")
    set_model.add_argument("--json", action="store_true", help="JSON preview; requires --dry-run")
    roles = ("kael", "veyra", "orin", "atlas", "kovan", "argus", "nox", "vera", "talos", "thales", "helios")
    for role in roles:
        role_parser = commands.add_parser(role, help=f"configure the global {role} agent", allow_abbrev=False)
        role_commands = role_parser.add_subparsers(dest="role_action", required=True, parser_class=Parser)
        model = role_commands.add_parser("set-model", help="set the exact provider/model-id", allow_abbrev=False,
                                         description=help_notes)
        model.add_argument("model_id", help="exact provider/model-id, for example openai/gpt-6-luna")
        effort = role_commands.add_parser("set-effort", help="set a catalog-declared reasoning effort", allow_abbrev=False,
                                          description=help_notes)
        effort.add_argument("effort", help="effort declared for this model by Models.dev")
        for scoped in (model, effort):
            scoped.add_argument("--scope", choices=("project", "global"), help="select scope (default: effective scope)")
            scoped.add_argument("--target", type=Path, help="absolute managed project worktree root; project scope only")

    config = commands.add_parser("config", help="list effective configuration or check generated outputs", allow_abbrev=False,
                                 description=help_notes)
    config_commands = config.add_subparsers(dest="action", required=True, parser_class=Parser)
    config_list = config_commands.add_parser("list", help="list effective values, absolute source paths, and precedence", allow_abbrev=False)
    config_list.add_argument("--scope", choices=("project", "global"), help="select scope (default: effective scope)")
    config_list.add_argument("--target", type=Path, help="absolute managed project worktree root; project scope only")
    check = config_commands.add_parser("check", help="compare renderer outputs without writing", allow_abbrev=False)
    check.add_argument("--harness", choices=("opencode", "codex", "all"), default="all")
    check.add_argument("--json", action="store_true")
    apply = config_commands.add_parser(
        "apply", help="preview an existing project/global installation; execute explicitly", allow_abbrev=False,
    )
    apply.add_argument("--scope", choices=("project", "global"), required=True)
    apply.add_argument("--target", type=Path, help="absolute existing Git worktree root; project scope only")
    apply.add_argument("--harness", choices=("opencode", "codex", "all"), required=True)
    mode = apply.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="read-only preview; no target writes")
    mode.add_argument("--execute", action="store_true", help="explicitly apply project or OpenCode global configuration")
    apply.add_argument("--json", action="store_true", help="emit a single JSON result")
    install = commands.add_parser("install", help="install an immutable official release through the existing installer", allow_abbrev=False)
    install.add_argument("--scope", choices=("project", "global"), default="global")
    install.add_argument("--target", type=Path, help="absolute existing Git worktree root; project scope only")
    install.add_argument("--harness", choices=("opencode", "codex", "all"), default="opencode")
    install.add_argument("--version", dest="release_version", help="optional exact immutable release tag (default: latest stable)")
    install_mode = install.add_mutually_exclusive_group()
    install_mode.add_argument("--dry-run", action="store_true", help="preview through the official installer")
    install_mode.add_argument("--execute", action="store_true", help="execute the official installer")
    install.add_argument("--json", action="store_true", help="emit one JSON result with captured native output")
    uninstall = commands.add_parser("uninstall", help="remove only manifest-owned resources through the existing engine", allow_abbrev=False)
    uninstall.add_argument("--scope", choices=("project", "global"), default="global")
    uninstall.add_argument("--target", type=Path, help="absolute existing Git worktree root; project scope only")
    uninstall.add_argument("--harness", choices=("opencode", "codex", "all"), default="opencode")
    uninstall_mode = uninstall.add_mutually_exclusive_group()
    uninstall_mode.add_argument("--dry-run", action="store_true", help="preview when the native engine supports it")
    uninstall_mode.add_argument("--execute", action="store_true", help="execute the existing uninstall engine")
    uninstall.add_argument("--json", action="store_true", help="emit one JSON result with captured native output")
    doctor = commands.add_parser("doctor", help="read-only managed installation diagnostic", allow_abbrev=False)
    doctor.add_argument("--scope", choices=("project", "global"), help="select scope (default: effective scope)")
    doctor.add_argument("--target", type=Path, help="absolute existing Git worktree root; project scope only")
    doctor.add_argument("--harness", choices=("opencode", "codex", "all"), default="opencode")
    doctor.add_argument("--json", action="store_true")
    recover = config_commands.add_parser("recover", help="explicitly recover one pending source edit or config apply", allow_abbrev=False)
    recover.add_argument("--scope", choices=("project", "global"), help="project selects a target apply journal")
    recover.add_argument("--target", type=Path, help="absolute project root for project-apply recovery")
    recover.add_argument("--harness", choices=("opencode", "codex", "all"), help="global recovery currently supports opencode only")
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
    if len(roles) != 11:
        raise CLIError(f"Expected eleven canonical roles, found {len(roles)}")
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
                     "representation": {"opencode": "agent", "codex": "root" if role == "kael" else "agent"}})
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


def installation_status(source: Path, args, response: dict) -> int:
    from .install_manifest import ManifestError, manifest_paths, manifest_present, read_project_manifest

    response["context"].update({"kind": "installation_metadata", "scope": args.scope,
                                "harness": args.harness})
    response["data"] = {"installed_harnesses": [], "integrity": "unverified",
                        "ownership": "unverified", "assignments": "unknown",
                        "runtime_validation": "not_performed", "evidence": "none"}
    if args.scope == "global":
        from . import global_readonly

        return global_readonly.inspect(
            source, args, response, source_query=source_query,
            load_renderer=load_renderer, release_version=release_version,
            assignment_query=model_assignments, operation="status",
        )
    if args.target is None or not args.target.is_absolute():
        raise CLIError("Project status requires --target <absolute-worktree-root>", 2)
    target = args.target.resolve()
    if not target.is_dir() or not ((target / ".git").is_dir() or (target / ".git").is_file()):
        raise CLIError(f"Target must be a Git worktree root with a .git marker: {target}", 2)
    response["context"]["target"] = str(target)
    manifests = manifest_paths(target)
    present = [path for path in manifests if manifest_present(path)]
    if not present:
        response["result"] = "absent"
        response["data"]["installation_state"] = "absent"
        return 0
    response["data"]["manifests"] = [str(path) for path in present]
    if len(present) != 1:
        response["data"]["installation_state"] = "contradictory"
        raise CLIError("Both project manifest locations exist; reported ownership metadata is ambiguous", 3)
    response["data"]["installation_state"] = "invalid"
    try:
        record = read_project_manifest(target)
    except ManifestError as error:
        if error.code == "contradictory":
            response["data"]["installation_state"] = "contradictory"
        raise CLIError(str(error), 3 if error.blocked else 1) from error
    if record is None:
        response["result"] = "absent"
        response["data"]["installation_state"] = "absent"
        return 0
    installed = list(record.installed_harnesses)
    response["data"]["manifests"] = [str(record.path)]
    response["data"].update({"installation_state": "reported", "installed_harnesses": installed,
                             "recorded_version": record.installed_version,
                             "recorded_source_commit": record.installed_from_commit,
                             "evidence": "reported_manifest",
                             "metadata_format": record.metadata_format})
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
                if "model" in role:
                    print(f"{role['role']} | {role['identity']} | model={role['model']} | effort={role['effort']} | "
                          f"model source={role['model_source']} | effort source={role['effort_source']}")
                else:
                    print(f"{role['role']} | {role['identity']} | family={role['family']} | effort={role['effort']} | "
                          f"opencode={role['models']['opencode']} ({role['representation']['opencode']}) | "
                          f"codex={role['models']['codex']} ({role['representation']['codex']})")
        elif key == "manual_edit_reminder" and response["operation"] == "config list":
            continue
        else:
            print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    if response["operation"] == "config list":
        print("Run 'olympus doctor' after manual edits.")
    for issue in response["issues"]:
        print(f"{issue['code']}: {issue['message']}", file=sys.stderr)
    if response["operation"] == "doctor":
        guidance = {
            "managed_file_drift": "Inspect the listed managed path and compare it with the trusted source; preserve local edits and reconcile ownership before any update or uninstall.",
            "global_managed_file_drift": "Inspect the listed global managed path and preserve local edits; reconcile ownership before any update or uninstall.",
            "source_drift": "Run `python scripts/render_harnesses.py check --harness all` in the displayed source; reconcile intentional source/output differences before applying anything.",
            "invalid_manifest": "Preserve the manifest and managed files; inspect and manually reconcile the manifest format and ownership before install, update, or uninstall.",
            "invalid_global_manifest": "Preserve the global manifest and resources; inspect and manually reconcile its format and ownership before install, update, or uninstall.",
            "ambiguous_manifest": "Preserve both manifest locations and all managed files; resolve which manifest owns this displayed project before taking action.",
            "unsafe_manifest": "Preserve the manifest and target files; inspect the unsafe path or file type before any operation that could change ownership.",
            "manifest_too_large": "Preserve the manifest; inspect it manually and do not treat this read-limit result as a valid ownership check.",
            "invalid_manifest_entry": "Preserve the manifest and managed files; inspect the malformed entry and reconcile ownership before any update or uninstall.",
            "invalid_manifest_hash": "Preserve the manifest and managed files; inspect the invalid hash entry without rewriting it to match current files.",
            "unsupported_manifest_inventory": "Preserve the manifest and managed files; compare its inventory with a trusted compatible source before taking action.",
            "unsupported_global_inventory": "Preserve the global manifest and files; compare its inventory with a trusted compatible source before taking action.",
            "version_mismatch": "Compare the recorded and source versions shown above, then choose the intended trusted release before any explicit update; no version change was made.",
            "unsupported_global_version": "Preserve the global installation and verify its recorded release against a trusted supported release before changing it.",
            "platform_unqualified": "Run doctor on a Windows system with PowerShell 7 (pwsh); this platform result did not verify the installation.",
            "verifier_missing": "Inspect the displayed trusted source checkout and restore its verifier only from that source; no installation verification ran.",
            "verifier_unavailable": "Run doctor on Windows with PowerShell 7 (pwsh) available; this result did not verify the installation.",
            "verifier_version_unsupported": "Use PowerShell 7 or later (`pwsh`) and rerun doctor; this result did not verify the installation.",
            "native_verify_unavailable": "Check the displayed platform, PowerShell 7 availability, and verifier diagnostic; no verification was established.",
            "verification_unavailable": "Review the verifier diagnostic above and rerun doctor only when the stated verification prerequisite is available.",
            "verification_failed": "Review the VerifyOnly diagnostic above and preserve the indicated files while reconciling the cause; doctor made no repair.",
            "invalid_user_configuration": "Inspect the configuration path named above and correct its JSON, schema, or declared model/effort values manually, then rerun doctor.",
            "harness_absent": "Confirm the selected harness and scope are intended; install it only after reviewing the displayed target and ownership.",
            "invalid_target": "Select the intended existing Git worktree root and keep the canonical source checkout separate from the project target.",
            "source_is_target": "Choose a separate existing project worktree; never use the canonical source checkout as its own installation target.",
            "git_unavailable": "Make Git available and verify the selected directory is the intended worktree root before rerunning doctor.",
            "target_unconfirmed": "Verify the displayed directory is the actual Git worktree root and that Git can inspect it; no target was changed.",
            "invalid_global_root": "Select the intended absolute global configuration root and verify it is not a filesystem root before retrying.",
            "global_path_unavailable": "Verify the OpenCode CLI or configured global path and inspect the selected global root before retrying; do not guess or move the root.",
            "overlapping_global_roots": "Inspect the resolved OpenCode and Codex roots and keep them distinct; do not change either installation until ownership is clear.",
            "unsafe_global_root": "Inspect the displayed global path components for links, reparse points, or non-directory entries; preserve them until ownership is clear.",
            "unsafe_global_resource": "Preserve the reported global resource and inspect its path/type manually before any operation that could change it.",
            "global_external_guard_unsafe": "Inspect the existing global OpenCode config and resolve ambiguous rules manually; establish an external_directory ASK or DENY fallback before applying configuration.",
            "global_install_conflict": "Preserve the user-owned conflicting resource and inspect the reported path; do not force an overwrite.",
            "global_apply_recovery_pending": "Preserve the pending journal and verify it belongs to the displayed global OpenCode root; use only the explicit recovery path named in the diagnostic.",
            "global_guard_recovery_pending": "Preserve the pending intent and global config; inspect the interrupted install and verify root ownership before choosing recovery.",
            "source_invalid": "Inspect the canonical source and renderer diagnostic above; resolve source errors before applying any generated output.",
            "source_inventory_unsupported": "Compare the displayed source inventory with the supported adapter inventory and use a compatible trusted source before applying anything.",
            "configuration_invalid": "Inspect the configuration diagnostic and displayed path, correct the input manually, and rerun doctor; no repair was attempted.",
            "read_failed": "Check that the displayed source or target resource is readable, preserve its contents, then rerun doctor.",
            "query_failed": "Review the query diagnostic and displayed source/target paths; verify them manually before retrying and do not repair managed files from this generic error.",
        }
        for issue in response["issues"]:
            recommendation = guidance.get(issue.get("code"))
            if recommendation is None:
                recommendation = "Review this issue code and message before choosing a repair; no repair was attempted."
            scope = response.get("context", {}).get("scope")
            context = f" ({scope} scope)" if scope else ""
            print(f"next step{context}: {recommendation}")


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


def _run_project_recovery(source: Path, args, response: dict) -> int:
    from . import config_apply, config_apply_transaction
    from . import source_edit

    response["operation"] = "config recover"
    response["context"] = {"source": str(source), "kind": "project_apply_recovery", "scope": "project"}
    if args.harness is not None:
        raise CLIError("--harness is available only with --scope global for config recovery.", 2)
    if args.scope == "global":
        raise CLIError("Global config recovery is unavailable.", 3)
    if args.scope != "project" or args.target is None or not args.target.is_absolute():
        raise CLIError("Project recovery requires --scope project --target <absolute-worktree-root>.", 2)
    target = config_apply._validate_target(source, args.target)
    response["context"]["target"] = str(target)
    try:
        result = config_apply_transaction.recover(target, source)
    except config_apply_transaction.TransactionError as error:
        response["result"] = {1: "failed", 3: "blocked", 4: "unconfirmed"}.get(error.code, "failed")
        response["issues"] = [{"code": response["result"], "message": str(error)}]
        emit(response, False)
        return error.code
    except (OSError, UnicodeError, source_edit.BatchError, source_edit.LockError) as error:
        response["result"] = "unconfirmed"
        response["issues"] = [{"code": "unconfirmed", "message": str(error)}]
        emit(response, False)
        return 4
    response["result"] = "no_changes" if result == "no_changes" else "ok"
    response["data"] = {"recovery": result}
    print(f"config recover: {result}")
    print(f"target: {target}")
    return 0


def _run_global_recovery(source: Path, args, response: dict) -> int:
    from . import global_apply

    args.harness = args.harness or "opencode"
    return global_apply.recover(source, args, response, load_renderer=load_renderer)


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
        operation = "version" if args.version else " ".join(filter(None, (
            args.command, getattr(args, "role_action", None) if args.command in {
                "kael", "veyra", "orin", "atlas", "kovan", "argus", "nox", "vera", "talos", "thales", "helios",
            } else getattr(args, "action", None),
        )))
        response["operation"] = operation
        if operation in ("models set-family", "agents set-model") and args.json and not args.dry_run:
            raise CLIError("--json for model edits requires --dry-run", 2)
        if operation == "config apply" and args.json and args.execute and args.scope != "global":
            raise CLIError("--json for config apply requires --dry-run", 2)
        if args.command == "agents" and args.action == "set-model" and args.family is None and args.effort is None:
            raise CLIError("agents set-model requires --family and/or --effort", 2)
        source = recovery_source_root(args.source) if operation == "config recover" else source_root(args.source)
        response["context"] = {"source": str(source), "kind": "canonical_source"}
        if operation != "config recover" and (source / ".olympus-cli-edit").exists():
            response["context"]["source_edit"] = "unconfirmed; not repaired"
        if args.command == "help":
            print(cli_parser.format_help(), end="")
            return 0
        if args.version or args.command == "version":
            print(f"olympus {release_version(source)}")
            return 0
        if args.command in ("update", "upgrade"):
            from . import system_cli

            return system_cli.update(source, args.scope, args.target)
        if args.command == "agents" and args.action == "list":
            from . import user_config

            scope, target = user_config.select_scope(source, args.scope, args.target)
            rows = user_config.effective_roles(source, scope, target)
            response["data"] = {"scope": scope, "target": str(target) if target else None, "roles": rows}
            response["result"] = "ok"
            emit(response, args.json)
            return 0
        if args.command == "config" and args.action == "list":
            from . import user_config

            scope, target = user_config.select_scope(source, args.scope, args.target)
            response["data"] = user_config.config_listing(source, scope, target)
            response["result"] = "ok"
            emit(response, as_json)
            return 0
        if args.command in {
            "kael", "veyra", "orin", "atlas", "kovan", "argus", "nox", "vera", "talos", "thales", "helios",
        } and args.role_action in ("set-model", "set-effort"):
            from . import user_config

            field = "model" if args.role_action == "set-model" else "effort"
            value = args.model_id if field == "model" else args.effort
            scope, target = user_config.select_scope(source, args.scope, args.target)
            path, applied = user_config.set_override(source, args.command, field, value, scope, target)
            response["data"] = {"role": args.command, field: value, "scope": scope,
                                 "target": str(target) if target else None,
                                 "source": str(path), "installed_agent_updated": applied}
            response["result"] = "ok"
            emit(response, False)
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
            if args.scope == "global":
                code = _run_global_recovery(source, args, response)
                emit(response, as_json)
                return code
            if args.scope is not None or args.target is not None:
                return _run_project_recovery(source, args, response)
            if args.harness is not None:
                raise CLIError("--harness requires --scope global for config recovery.", 2)
            return _run_recovery(source, response)
        if response["operation"] == "config apply":
            from . import config_apply

            if args.scope == "global":
                if args.execute:
                    from . import global_apply

                    code = global_apply.execute(
                        source, args, response, source_query=source_query,
                        load_renderer=load_renderer, release_version=release_version,
                        assignment_query=model_assignments,
                    )
                else:
                    from . import global_readonly

                    code = global_readonly.inspect(
                        source, args, response, source_query=source_query,
                        load_renderer=load_renderer, release_version=release_version,
                        assignment_query=model_assignments, operation="config apply",
                    )
                emit(response, as_json)
                return code

            if args.execute:
                return config_apply.execute(
                    source, args, response, source_query=source_query,
                    load_renderer=load_renderer, release_version=release_version,
                    assignment_query=model_assignments,
                )
            code = config_apply.preview(source, args, response, source_query=source_query,
                                        load_renderer=load_renderer, release_version=release_version,
                                        assignment_query=model_assignments)
            config_apply.emit_preview(response, as_json)
            return code
        if response["operation"] == "doctor":
            from . import doctor
            from . import user_config
            from .models_catalog import CatalogError

            project_request = args.scope == "project" or (args.scope is None and args.target is not None)
            check_user_configuration = args.scope == "global" or (args.scope is None and args.target is None)
            if args.scope == "global" and args.target is not None:
                raise CLIError("--target is available only with project scope.", 2)
            if args.scope is None and not project_request:
                try:
                    args.scope, args.target = user_config.select_scope(source, args.scope, args.target)
                except user_config.UserConfigError as error:
                    response["result"] = "failed"
                    response["issues"] = [{"code": "invalid_user_configuration", "message": str(error)}]
                    emit(response, as_json)
                    return 1
            elif project_request:
                args.scope = "project"
                if args.target is not None:
                    from . import config_apply

                    try:
                        target = config_apply._validate_target(source, args.target)
                        record, _, blockers = config_apply._manifest_record(target)
                        check_user_configuration = (
                            not blockers and record is not None and "opencode" in record.installed_harnesses
                        )
                        if check_user_configuration:
                            args.target = target
                    except (config_apply.PreviewFault, OSError, RuntimeError):
                        check_user_configuration = False

            try:
                user_configuration = (
                    user_config.diagnose(source, args.scope, args.target) if check_user_configuration else None
                )
            except (user_config.UserConfigError, CatalogError) as error:
                response["result"] = "failed"
                response["issues"] = [{"code": "invalid_user_configuration", "message": str(error)}]
                emit(response, as_json)
                return 1

            if args.scope == "global":
                from . import global_readonly

                code = global_readonly.inspect(
                    source, args, response, source_query=source_query,
                    load_renderer=load_renderer, release_version=release_version,
                    assignment_query=model_assignments, operation="doctor",
                )
                if user_configuration is not None:
                    response["data"]["user_configuration"] = user_configuration
                emit(response, as_json)
                return code

            code = doctor.diagnose(source, args, response, source_version=release_version(source),
                                   source_query=source_query)
            if user_configuration is not None:
                response["data"]["user_configuration"] = user_configuration
            emit(response, as_json)
            return code
        if response["operation"] in ("install", "uninstall"):
            from . import install_routing

            return install_routing.run(source, args, response, emit=emit, as_json=as_json)
        code = installation_status(source, args, response)
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
    except ValueError as error:
        response["result"] = "failed"
        response["issues"].append({"code": "configuration_invalid", "message": str(error)})
        emit(response, as_json)
        return 1
    except (OSError, UnicodeError) as error:
        response["result"] = "failed"
        response["issues"].append({"code": "read_failed", "message": str(error)})
        emit(response, as_json)
        return 1
    except KeyboardInterrupt:
        code = 4
        response["result"] = "unconfirmed"
        message = "Operation interrupted; inspect/recover pending source-edit state explicitly."
        if response.get("operation") == "config apply":
            args = locals().get("args", None)
            if getattr(args, "scope", None) == "global":
                response["data"].update({"preview_only": False, "execution": "unconfirmed"})
                message = ("Global OpenCode config apply interrupted; inspect and explicitly recover the pending state "
                           "with config recover --scope global --harness opencode.")
            else:
                target = str(getattr(args, "target", "unknown"))
                message = ("Project config apply interrupted; inspect and explicitly recover the pending project state "
                           f"with config recover --scope project --target {target}.")
        elif response.get("operation") in ("install", "uninstall"):
            if response.get("data", {}).get("engine", "not_started") == "not_started":
                code = 3
                response["result"] = "blocked"
                response["data"].update({"state": "not_started", "effects": "none_confirmed"})
                message = "Install/uninstall preflight was interrupted; no native engine was started."
            else:
                response["data"].update({
                    "state": "unconfirmed",
                    "effects": "unconfirmed; descendant processes may continue",
                })
                message = "Native install/uninstall was interrupted; effects are unconfirmed. Inspect the selected installation before retrying."
        response["issues"].append({
            "code": "unconfirmed" if code == 4 else "preflight_interrupted",
            "message": message,
        })
        emit(response, as_json)
        return code


if __name__ == "__main__":
    raise SystemExit(main())
