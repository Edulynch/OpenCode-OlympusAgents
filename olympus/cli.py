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


_ROLE_NAMES = ("kael", "veyra", "atlas", "kovan", "nox", "vera",
               "talos", "thales", "helios")


class RootParser(Parser):
    def format_usage(self) -> str:
        return "usage: olympus [--source CHECKOUT] [--version] [--verbose] COMMAND [ARGS ...]\n"

    def format_help(self) -> str:
        return (
            self.format_usage() + "\n"
            "Olympus global CLI. Manage your OpenCode installation and team.\n"
            "\n"
            "Examples:\n"
            "  olympus version                Show the release version\n"
            "  olympus update                 Check for a newer release\n"
            "  olympus agents list            See your team's models and settings\n"
            "  olympus doctor --scope global  Check your global installation\n"
            "\n"
            "More commands:\n"
            "  install, uninstall          Manage the global installation (upgrade = update)\n"
            "  agents, models, config      View or configure models and settings\n"
            "  status, completion, help    Read metadata, set up completion, or see help\n"
            "  olympus nox set-effort high  Change an agent's reasoning effort\n"
            "\n"
            "Options:\n"
            "  --source CHECKOUT  use an absolute trusted source checkout (before command)\n"
            "  --version          show the source release version\n"
            "  --verbose          show technical response details\n"
            "  -h, --help         show help for this command\n"
            "\n"
            "Advanced: config check, config apply, config recover, models set-family, agents set-model.\n"
            "Run 'olympus <command> --help' for scope, mode, and an example.\n"
        )


def _set_help(parser: argparse.ArgumentParser, description: str, example: str) -> None:
    parser.description = description
    parser.epilog = f"Example: {example}"


def parser() -> Parser:
    root = RootParser(
        prog="olympus",
        allow_abbrev=False,
    )
    root.add_argument("--source", type=Path, metavar="CHECKOUT",
                      help="use an absolute trusted source checkout (before command)")
    root.add_argument("--version", action="store_true", help="show the source release version")
    root.add_argument("--verbose", action="store_true", help="show technical response details")
    commands = root.add_subparsers(dest="command", parser_class=Parser)
    help_command = commands.add_parser(
        "help", help="show the command map and examples", allow_abbrev=False,
        description="Show common commands and how to find detailed command help. No files are changed.",
    )
    _set_help(help_command, help_command.description, "olympus --help")
    version = commands.add_parser(
        "version", help="print the source release version", allow_abbrev=False,
        description="Print the source-declared Olympus release version. No files are changed.",
    )
    _set_help(version, version.description, "olympus version")
    update = commands.add_parser(
        "update", aliases=["upgrade"], help="update the global OpenCode installation",
        allow_abbrev=False,
        description=(
            "Update the fixed global OpenCode installation. --force requests a full reinstall of "
            "manifest-owned files and permits replacing drift only on those paths."
        ),
    )
    update.add_argument("--force", action="store_true",
                        help="reinstall proven managed files; replace drift only on those paths")
    _set_help(update, update.description, "olympus update --force")
    update.set_defaults(command="update")
    completion = commands.add_parser("completion", help="print session-local shell completion registration",
                                     allow_abbrev=False,
                                     description="Print optional shell completion code; no profile or config is changed.")
    completion.add_argument("shell", choices=("powershell", "bash"))
    _set_help(completion, completion.description, "olympus completion powershell")
    models = commands.add_parser(
        "models", help="query or explicitly edit canonical model assignments", allow_abbrev=False,
        description="Inspect canonical model assignments or explicitly edit source model intent.",
    )
    _set_help(models, models.description, "olympus models list --json")
    model_commands = models.add_subparsers(dest="action", required=True, parser_class=Parser)
    listing = model_commands.add_parser(
        "list", help="list all nine OpenCode role assignments", allow_abbrev=False,
        description="Read the canonical OpenCode role assignments without writing files.",
    )
    listing.add_argument("--json", action="store_true")
    _set_help(listing, listing.description, "olympus models list --json")
    set_family = model_commands.add_parser(
        "set-family", help="explicitly edit an existing family", allow_abbrev=False,
        description="Edit canonical model intent in the selected source checkout. --dry-run previews; otherwise this writes.",
    )
    set_family.add_argument("family")
    set_family.add_argument("--opencode", required=True)
    set_family.add_argument("--dry-run", action="store_true")
    set_family.add_argument("--json", action="store_true", help="JSON preview; requires --dry-run")
    _set_help(set_family, set_family.description,
              "olympus models set-family sol --opencode openai/new-sol --dry-run")
    agents = commands.add_parser(
        "agents", help="list effective agents or edit canonical role model intent", allow_abbrev=False,
        description="List effective assignments or explicitly edit canonical role model intent.",
    )
    _set_help(agents, agents.description, "olympus agents list")
    agent_commands = agents.add_subparsers(dest="action", required=True, parser_class=Parser)
    agent_list = agent_commands.add_parser(
        "list", help="list effective models, efforts, and sources", allow_abbrev=False,
        description="Read effective values and their sources. Scope defaults to the effective project or global config.",
    )
    agent_list.add_argument("--json", action="store_true")
    agent_list.add_argument("--scope", choices=("project", "global"), help="select scope (default: effective scope)")
    agent_list.add_argument("--target", type=Path, help="absolute managed project worktree root; project scope only")
    _set_help(agent_list, agent_list.description, "olympus agents list --scope global")
    set_model = agent_commands.add_parser(
        "set-model", help="explicitly edit an existing role", allow_abbrev=False,
        description=(
            "Edit canonical role model intent in the selected source checkout; supply --family and/or --effort. "
            "--dry-run previews; otherwise this writes."
        ),
    )
    set_model.add_argument("role")
    set_model.add_argument("--family")
    set_model.add_argument("--effort")
    set_model.add_argument("--dry-run", action="store_true")
    set_model.add_argument("--json", action="store_true", help="JSON preview; requires --dry-run")
    _set_help(set_model, set_model.description,
              "olympus agents set-model veyra --effort high --dry-run")
    for role in _ROLE_NAMES:
        role_parser = commands.add_parser(
            role, help=f"configure the {role} model or effort override", allow_abbrev=False,
            description=(
                f"Set a per-user {role} override; this writes Olympus user configuration. "
                "Scope defaults to the effective project or global config; project scope needs --target."
            ),
        )
        _set_help(role_parser, role_parser.description,
                  f"olympus {role} set-model openai/gpt-6-luna --scope global")
        role_commands = role_parser.add_subparsers(dest="role_action", required=True, parser_class=Parser)
        model = role_commands.add_parser(
            "set-model", help="set the exact provider/model-id", allow_abbrev=False,
            description=(
                f"Write the {role} model override to Olympus user configuration. "
                "Scope defaults to the effective project or global config; project scope needs --target. "
                "Known model IDs use the offline catalog; access is not verified."
            ),
        )
        model.add_argument("model_id", help="exact provider/model-id, for example openai/gpt-6-luna")
        effort = role_commands.add_parser("set-effort", help="set a catalog-declared reasoning effort", allow_abbrev=False,
                                          description=(
                                              f"Write the {role} effort override to Olympus user configuration. "
                                              "Scope defaults to the effective project or global config; "
                                              "project scope needs --target."
                                          ))
        effort.add_argument("effort", help="effort declared for this model by Models.dev")
        for scoped in (model, effort):
            scoped.add_argument("--scope", choices=("project", "global"), help="select scope (default: effective scope)")
            scoped.add_argument("--target", type=Path, help="absolute managed project worktree root; project scope only")
        _set_help(model, model.description,
                  f"olympus {role} set-model openai/gpt-6-luna --scope global")
        _set_help(effort, effort.description,
                  f"olympus {role} set-effort high --scope global")

    config = commands.add_parser("config", help="list effective configuration or check generated outputs", allow_abbrev=False,
                                 description=(
                                     "List effective configuration, check generated outputs, or explicitly apply/recover "
                                     "a matching configuration transaction."
                                 ))
    _set_help(config, config.description, "olympus config list --scope global")
    config_commands = config.add_subparsers(dest="action", required=True, parser_class=Parser)
    config_list = config_commands.add_parser(
        "list", help="list effective values, absolute source paths, and precedence", allow_abbrev=False,
        description="Read effective settings, their precedence, and absolute source paths. No files are changed.",
    )
    config_list.add_argument("--scope", choices=("project", "global"), help="select scope (default: effective scope)")
    config_list.add_argument("--target", type=Path, help="absolute managed project worktree root; project scope only")
    _set_help(config_list, config_list.description, "olympus config list --scope global")
    max_parallel = config_commands.add_parser(
        "set-max-parallel", help="set the global Kael child ceiling (default: 4; prompt policy only)",
        allow_abbrev=False,
        description=(
            "Write the global prompt-level child ceiling (1-8); update the installed global Kael prompt when present. "
            "This does not change the native scheduler or existing project installations."
        ),
    )
    max_parallel.add_argument("value", type=int, metavar="N", help="integer from 1 to 8")
    _set_help(max_parallel, max_parallel.description, "olympus config set-max-parallel 2")
    check = config_commands.add_parser(
        "check", help="compare renderer outputs without writing", allow_abbrev=False,
        description="Read the selected source and compare generated OpenCode outputs. No writes or provider checks.",
    )
    check.add_argument("--harness", choices=("opencode",), default="opencode")
    check.add_argument("--json", action="store_true")
    _set_help(check, check.description, "olympus config check --json")
    apply = config_commands.add_parser(
        "apply", help="preview an existing project/global installation; execute explicitly", allow_abbrev=False,
        description=(
            "Select an existing managed OpenCode installation. --dry-run is read-only; --execute applies the plan. "
            "Project scope needs an absolute Git worktree --target; global scope forbids --target."
        ),
    )
    apply.add_argument("--scope", choices=("project", "global"), required=True)
    apply.add_argument("--target", type=Path, help="absolute existing Git worktree root; project scope only")
    apply.add_argument("--harness", choices=("opencode",), required=True)
    mode = apply.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="read-only preview; no target writes")
    mode.add_argument("--execute", action="store_true", help="explicitly apply project or OpenCode global configuration")
    apply.add_argument("--json", action="store_true", help="emit a single JSON result")
    _set_help(apply, apply.description,
              "olympus config apply --scope project --target <absolute-worktree-root> --harness opencode --dry-run")
    install = commands.add_parser(
        "install", help="install the latest global OpenCode release", allow_abbrev=False,
        description=(
            "Install the fixed global OpenCode release. --dry-run previews; otherwise the installer executes. "
            "Preview may leave temporary/cache effects."
        ),
    )
    install_mode = install.add_mutually_exclusive_group()
    install_mode.add_argument("--dry-run", action="store_true", help="preview through the official installer")
    install_mode.add_argument("--execute", action="store_true", help="execute the official installer")
    install.add_argument("--json", action="store_true", help="emit one JSON result with captured native output")
    _set_help(install, install.description, "olympus install --dry-run")
    uninstall = commands.add_parser(
        "uninstall", help="remove the global OpenCode installation", allow_abbrev=False,
        description=(
            "Remove unchanged manifest-owned global OpenCode resources and the CLI PATH entry. "
            "--dry-run previews when supported; otherwise the uninstall engine executes."
        ),
    )
    uninstall_mode = uninstall.add_mutually_exclusive_group()
    uninstall_mode.add_argument("--dry-run", action="store_true", help="preview when the native engine supports it")
    uninstall_mode.add_argument("--execute", action="store_true", help="execute the existing uninstall engine")
    uninstall.add_argument("--json", action="store_true", help="emit one JSON result with captured native output")
    _set_help(uninstall, uninstall.description, "olympus uninstall --dry-run")
    doctor = commands.add_parser(
        "doctor", help="read-only managed installation diagnostic", allow_abbrev=False,
        description=(
            "Read-only configuration and managed-installation diagnostics. Scope defaults to effective config; "
            "project scope needs --target. "
            "doctor does not repair files or verify model-provider access."
        ),
    )
    doctor.add_argument("--scope", choices=("project", "global"), help="select scope (default: effective scope)")
    doctor.add_argument("--target", type=Path, help="absolute existing Git worktree root; project scope only")
    doctor.add_argument("--harness", choices=("opencode",), default="opencode")
    doctor.add_argument("--json", action="store_true")
    _set_help(doctor, doctor.description, "olympus doctor --scope global")
    recover = config_commands.add_parser(
        "recover", help="explicitly recover one pending source edit or config apply", allow_abbrev=False,
        description=(
            "Reconcile only the matching pending source edit or project/global apply; recovery may change files. "
            "Project recovery needs --scope project and --target; global recovery needs --scope global --harness opencode."
        ),
    )
    recover.add_argument("--scope", choices=("project", "global"), help="project selects a target apply journal")
    recover.add_argument("--target", type=Path, help="absolute project root for project-apply recovery")
    recover.add_argument("--harness", choices=("opencode",), help="global recovery requires opencode")
    _set_help(recover, recover.description,
              "olympus config recover --scope global --harness opencode")
    status = commands.add_parser(
        "status", help="read reported installation metadata; no integrity verification", allow_abbrev=False,
        description=(
            "Read reported install metadata without verifying file integrity. Defaults to project scope, which needs "
            "--target; use global scope without a target for global metadata."
        ),
    )
    status.add_argument("--scope", choices=("project", "global"), default="project")
    status.add_argument("--target", type=Path, help="absolute Git worktree root; required for project scope")
    status.add_argument("--harness", choices=("opencode",), default="opencode")
    status.add_argument("--json", action="store_true")
    _set_help(status, status.description, "olympus status --scope global")

    def add_verbose_options(current: argparse.ArgumentParser) -> None:
        for action in current._actions:
            if not isinstance(action, argparse._SubParsersAction):
                continue
            for child in action.choices.values():
                if "--verbose" not in child._option_string_actions:
                    child.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS,
                                       help="show technical response details")
                add_verbose_options(child)

    add_verbose_options(root)
    return root


def _completion_candidates(cli_parser: argparse.ArgumentParser, words: list[str], current: str) -> list[str]:
    """Return static argparse-derived candidates without parsing or resolving a source."""
    if len(words) > 128 or any(len(word) > 4096 for word in (*words, current)):
        return []
    active = cli_parser
    positionals = [action for action in active._actions if not action.option_strings]
    positional_index = 0
    pending = None
    pending_count = 0

    def nargs_count(action) -> int:
        nargs = action.nargs
        if nargs == 0 or isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction,
                                             argparse._StoreConstAction, argparse._CountAction,
                                             argparse._HelpAction, argparse._VersionAction)):
            return 0
        if nargs is None or nargs == "?":
            return 1
        if type(nargs) is int:
            return nargs
        return 0

    for word in words:
        if pending is not None:
            if word == "=":
                continue
            pending_count -= 1
            if pending_count <= 0:
                pending = None
            continue

        option, separator, attached = word.partition("=")
        option_action = active._option_string_actions.get(option) if word.startswith("-") else None
        if option_action is not None:
            count = nargs_count(option_action)
            if count and separator and not attached:
                pending, pending_count = option_action, count
            elif count and not separator:
                pending, pending_count = option_action, count
            continue
        if word.startswith("-") and word != "-":
            continue
        if positional_index >= len(positionals):
            continue

        action = positionals[positional_index]
        if isinstance(action, argparse._SubParsersAction):
            selected = action.choices.get(word)
            positional_index += 1
            if selected is not None:
                active = selected
                positionals = [item for item in active._actions if not item.option_strings]
                positional_index = 0
        elif action.nargs in ("*", "+"):
            continue
        else:
            positional_index += 1

    def choice_values(action) -> list[str]:
        if action is None or action.choices is None:
            return []
        values = action.choices.keys() if isinstance(action.choices, dict) else action.choices
        return [str(value) for value in values]

    def matching(values: list[str], prefix: str) -> list[str]:
        return [value for value in values if value.startswith(prefix)]

    if pending is not None:
        return matching(choice_values(pending), current)

    if current.startswith("--") and "=" in current:
        option, value_prefix = current.split("=", 1)
        action = active._option_string_actions.get(option)
        if action is not None and nargs_count(action):
            return matching([f"{option}={value}" for value in choice_values(action)],
                            f"{option}={value_prefix}")

    if current.startswith("-"):
        options = [option for action in active._actions for option in action.option_strings]
        return matching(options, current)

    if not current:
        candidates = []
        if positional_index < len(positionals):
            candidates.extend(choice_values(positionals[positional_index]))
        candidates.extend(option for action in active._actions for option in action.option_strings)
        return candidates

    if positional_index < len(positionals):
        action = positionals[positional_index]
        if isinstance(action, argparse._SubParsersAction):
            return matching(choice_values(action), current)
        return matching(choice_values(action), current)
    return []


_COMPLETION_POWERSHELL = r"""Register-ArgumentCompleter -Native -CommandName 'olympus','olympus.cmd' -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    if ($null -eq $commandAst) { return }
    $words = [System.Collections.Generic.List[string]]::new()
    $elements = @($commandAst.CommandElements)
    for ($index = 1; $index -lt $elements.Count; $index++) {
        $element = $elements[$index]
        if ($element.Extent.StartOffset -ge $cursorPosition) { break }
        if ($element.Extent.EndOffset -ge $cursorPosition) { break }
        if ($element -is [System.Management.Automation.Language.StringConstantExpressionAst]) {
            $words.Add([string]$element.Value)
        } elseif ($element -is [System.Management.Automation.Language.ExpandableStringExpressionAst] -and
                  $element.NestedExpressions.Count -eq 0) {
            $words.Add([string]$element.Value)
        } elseif ($element -is [System.Management.Automation.Language.CommandParameterAst]) {
            $raw = [string]$element.Extent.Text
            if ($raw -match '^--[^=\s]+=[\s\S]*$') {
                $words.Add($raw)
                continue
            }
            if ($raw.StartsWith('-')) { $words.Add($raw) }
            else { $words.Add('--' + $element.ParameterName.TrimStart('-')) }
            if ($null -ne $element.Argument) {
                if ($element.Argument -is [System.Management.Automation.Language.StringConstantExpressionAst]) {
                    $words.Add([string]$element.Argument.Value)
                } elseif ($element.Argument -is [System.Management.Automation.Language.ExpandableStringExpressionAst] -and
                          $element.Argument.NestedExpressions.Count -eq 0) {
                    $words.Add([string]$element.Argument.Value)
                } else {
                    return
                }
            }
        } else {
            return
        }
    }
    $payload = [ordered]@{ words = $words.ToArray(); current = [string]$wordToComplete } |
        ConvertTo-Json -Compress
    $frame = "OLYMPUS-COMPLETE-PS-V1`n" + $payload
    try {
        $candidates = $frame | & olympus --_completion-query-v1 2>$null
        foreach ($candidate in $candidates) {
            $text = [string]$candidate
            if ($text.StartsWith([string]$wordToComplete, [StringComparison]::OrdinalIgnoreCase)) {
                [System.Management.Automation.CompletionResult]::new(
                    $text, $text, 'ParameterValue', $text
                )
            }
        }
    } catch { }
}"""

_COMPLETION_BASH = r"""_olympus_complete() {
    COMPREPLY=()
    local current
    local candidate
    local index word cursor=-1
    local -a words=()
    for ((index = 0; index < ${#COMP_WORDS[@]}; index++)); do
        word="${COMP_WORDS[index]}"
        if [[ $word == "=" && ${#words[@]} -gt 0 && ${words[${#words[@]}-1]} == --* ]]; then
            words[${#words[@]}-1]+="="
            [[ $index -eq $COMP_CWORD ]] && cursor=$((${#words[@]} - 1))
            continue
        fi
        [[ $index -eq $COMP_CWORD ]] && cursor=${#words[@]}
        words+=("$word")
    done
    (( cursor >= 1 && cursor < ${#words[@]} )) || return
    current="${words[cursor]}"
    while IFS= read -r candidate; do
        [[ $candidate == "$current"* ]] && COMPREPLY+=("$candidate")
    done < <(
        {
            printf '%s\0%s\0' 'OLYMPUS-COMPLETE-BASH-V1' "$cursor"
            printf '%s\0' "${words[@]}"
        } | olympus --_completion-query-v1 2>/dev/null
    )
}
complete -F _olympus_complete -o nosort olympus"""


def _completion_query(arguments: list[str]) -> int:
    if arguments:
        return 0
    try:
        raw = sys.stdin.buffer.read(32_769)
        if len(raw) > 32_768:
            return 0
        if raw.startswith(b"OLYMPUS-COMPLETE-PS-V1\n"):
            value = json.loads(raw[len(b"OLYMPUS-COMPLETE-PS-V1\n"):].decode("utf-8"))
            if (not isinstance(value, dict) or set(value) != {"words", "current"}
                    or not isinstance(value["words"], list) or not isinstance(value["current"], str)
                    or any(not isinstance(item, str) for item in value["words"])):
                return 0
            words, current = value["words"], value["current"]
        elif raw.startswith(b"OLYMPUS-COMPLETE-BASH-V1\0") and raw.endswith(b"\0"):
            fields = raw[len(b"OLYMPUS-COMPLETE-BASH-V1\0"):-1].split(b"\0")
            cursor = int(fields[0].decode("ascii"))
            shell_words = [item.decode("utf-8") for item in fields[1:]]
            if (len(shell_words) < 2 or cursor < 1 or cursor >= len(shell_words)
                    or shell_words[0].replace("\\", "/").rsplit("/", 1)[-1].casefold()
                    not in ("olympus", "olympus.cmd")):
                return 0
            words, current = shell_words[1:cursor], shell_words[cursor]
        else:
            return 0
        candidates = _completion_candidates(parser(), words, current)
    except (AttributeError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return 0
    for candidate in candidates:
        print(candidate)
    return 0


def _completion_registration(arguments: list[str]) -> str | None:
    for index, token in enumerate(arguments):
        if token != "completion" or arguments[index + 1:] not in (["powershell"], ["bash"]):
            continue
        prefix = arguments[:index]
        if not prefix or (len(prefix) == 2 and prefix[0] == "--source") or prefix == ["--version"]:
            return arguments[index + 1]
    return None


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
    if len(roles) != 9:
        raise CLIError(f"Expected nine canonical roles, found {len(roles)}")
    rows = []
    for role in sorted(roles):
        resolved = {}
        model, effort = renderer.role_model(models, role)
        if not isinstance(model, str) or not model.strip() or any(ord(c) < 32 or ord(c) == 127 for c in model):
            raise CLIError(f"Invalid OpenCode model identifier for {role}")
        if not isinstance(effort, str) or not effort.strip():
            raise CLIError(f"Invalid canonical effort for {role}")
        rows.append({"role": role, "identity": identities[role],
                     "family": models["roles"][role]["family"], "effort": effort,
                     "models": {"opencode": model},
                     "representation": {"opencode": "agent"}})
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
                             "evidence": "reported_manifest"})
    selected = (args.harness,)
    response["data"]["harnesses"] = {name: "reported" if name in installed else "absent" for name in selected}
    if not any(name in installed for name in selected):
        response["result"] = "absent"
    return 0


def _source_label(path: str) -> str:
    if path.replace("\\", "/").endswith("/olympus/core/models.toml"):
        return "canonical default"
    if path.replace("\\", "/").endswith("/.opencode/olympus-config.json"):
        return "project override"
    return "global override"


def _emit_issues(response: dict) -> None:
    for issue in response.get("issues", []):
        details = [issue.get("code", "issue"), issue.get("message", "")]
        for key in ("path", "harness"):
            if issue.get(key):
                details.append(f"{key}={issue[key]}")
        print(": ".join(value for value in details if value), file=sys.stderr)


def _emit_assignments(rows: list[dict]) -> None:
    if not rows:
        print("  (none)")
        return
    models = [row.get("model") or row["models"]["opencode"] for row in rows]
    width = max(len("MODEL"), *(len(model) for model in models))
    print(f"  {'AGENT':<8}  {'MODEL':<{width}}  {'EFFORT':<6}  SOURCE")
    for row, model in zip(rows, models):
        if "model_source" in row:
            source = _source_label(row["model_source"])
            effort_source = _source_label(row["effort_source"])
            if effort_source != source:
                source += f"; effort: {effort_source}"
        else:
            source = row["family"]
        print(f"  {row['role']:<8}  {model:<{width}}  {row['effort']:<6}  {source}")


_DOCTOR_GUIDANCE = {
    "managed_file_drift": "Inspect the listed managed path and compare it with the trusted source; preserve local edits and reconcile ownership before any update or uninstall.",
    "global_managed_file_drift": "Inspect the listed global managed path and preserve local edits; reconcile ownership before any update or uninstall.",
    "source_drift": "Run `python scripts/render_harnesses.py check --harness opencode` in the displayed source; reconcile intentional source/output differences before applying anything.",
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


def _doctor_recommendation(code: str) -> str:
    return _DOCTOR_GUIDANCE.get(
        code, "Review this issue code and message before choosing a repair; no repair was attempted.",
    )


def _emit_native_output_summary(data: dict) -> None:
    counts = {}
    notices = []
    for raw_line in data.get("native_stdout", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        action, separator, _ = line.partition(":")
        if separator and action in ("CREATE", "UPDATE", "REMOVE"):
            action = action.lower()
            counts[action] = counts.get(action, 0) + 1
        elif line.startswith(("OLYMPUS_ENTRYPOINT:", "OLYMPUS_RELEASE_EXECUTING:",
                              "OLYMPUS_RELEASE_EXECUTED:")):
            continue
        elif line.startswith("OLYMPUS_RELEASE_SELECTED:"):
            match = re.search(r"\btag=([^\s]+)", line)
            notices.append(f"Selected release: {match.group(1)}" if match else f"Native output: {line}")
        elif line.startswith("OLYMPUS_GLOBAL_INSTALL:"):
            match = re.match(
                r"OLYMPUS_GLOBAL_INSTALL:\s+(\S+)\s+(\S+)\s+(\S+)\s+\((\d+) managed resources;",
                line,
            )
            notices.append(
                f"Native result: {match.group(1)} {match.group(2)} {match.group(3)} "
                f"({match.group(4)} managed resources)."
                if match else f"Native output: {line}"
            )
        elif line.startswith(("GLOBAL_INSTALL_DRY_RUN:", "GLOBAL_UNINSTALL_DRY_RUN:")):
            notices.append(f"Native preview: {line.partition(':')[2].strip()}")
        elif line.startswith("OLYMPUS_UPDATE:"):
            notices.append(f"Native update: {line.partition(':')[2].strip()}")
        else:
            # Unknown output may be a safety diagnostic; keep it visible in compact mode.
            notices.append(f"Native notice: {line}")
    if counts:
        print("Planned resources: " + ", ".join(f"{action} {count}" for action, count in counts.items()))
    for notice in notices:
        print(notice)


def _emit_human_summary(response: dict) -> None:
    operation, result = response.get("operation", "Olympus"), response.get("result", "unknown")
    context, data = response.get("context", {}), response.get("data", {})
    setter = operation == "config set-max-parallel" or operation.endswith(("set-model", "set-effort"))
    if setter and result == "ok":
        if "max_children" in data:
            message = f"Saved global prompt ceiling: {data['max_children']} children (prompt policy only)."
        else:
            field = "model" if "model" in data else "effort"
            message = f"Saved {data['role']} {field}: {data[field]} ({data.get('scope', 'global')})."
        if "installed_agent_updated" in data:
            message += " Installed agent: " + ("updated." if data["installed_agent_updated"] else "not updated (saved only).")
        if data.get("target"):
            message += f" Target: {data['target']}"
        print(message)
        _emit_issues(response)
        return
    print(f"{operation}: {result}")
    scope = context.get("scope", data.get("scope"))
    if scope:
        print(f"Scope: {scope}")
    target = context.get("target", data.get("target"))
    if not target and operation == "config list" and scope == "project":
        project_config = next((item for item in data.get("sources", [])
                               if item.get("layer") == "project override"), None)
        if project_config:
            target = str(Path(project_config["path"]).parent.parent)
    harness_data = data.get("harnesses", {})
    if not target and isinstance(harness_data, dict):
        opencode = harness_data.get("opencode", {})
        if isinstance(opencode, dict):
            target = opencode.get("root")
    if target:
        print(f"Target: {target}")

    if operation in ("models list", "agents list"):
        print("Assignments:")
        _emit_assignments(data.get("roles", []))
    elif operation == "config list":
        parallel = data.get("max_parallel", {})
        if parallel:
            print(f"Global prompt ceiling: {parallel['max_children']} children (prompt policy; not an effective project setting)")
        precedence = data.get("precedence", [])
        if precedence:
            print(f"Precedence: {' > '.join(precedence)}")
        print(f"OpenCode root: {data.get('opencode_root_state', 'unknown')}")
        print("Effective assignments:")
        _emit_assignments(data.get("roles", []))
        sources = data.get("sources", [])
        if sources:
            print("Configuration sources:")
            for item in sources:
                state = "present" if item["exists"] else "not created"
                print(f"  {item['layer']}: {item['path']} ({state})")
        print("Next step: run 'olympus doctor' after manual edits.")
    elif operation == "config check":
        print(f"Renderer outputs: {'coherent' if data.get('coherent') else 'drift'} "
              f"({data.get('managed_outputs', 0)} checked)")
        print("Installation verification: not performed; model access: unknown")
    elif operation == "config apply":
        harnesses = data.get("selected_harnesses", [])
        if not harnesses:
            harnesses = [context["harness"]] if context.get("harness") else []
        if harnesses:
            print(f"Harness: {', '.join(harnesses)}")
        if "source_version" in data:
            print(f"Source version: {data['source_version']}")
        if "preview_state" in data:
            print(f"Preview: {data['preview_state']}")
        if "execution" in data:
            execution = data["execution"]
            print(f"Execution: {execution}")
        elif data.get("preview_only"):
            print("Execution: not run (preview only; no target writes)")
        assignments = data.get("assignments", {})
        if assignments.get("status") in ("verified", "partial", "unsupported"):
            print(f"Assignments: {assignments['status']}")
        changes = data.get("changes", [])
        manifest = data.get("manifest")
        if not isinstance(manifest, dict):
            opencode = data.get("harnesses", {}).get("opencode", {})
            manifest = opencode.get("manifest", {}) if isinstance(opencode, dict) else {}
        manifest_path = manifest.get("path") if isinstance(manifest, dict) else None
        manifest_planned = bool(changes) or bool(manifest.get("write_planned")) if isinstance(manifest, dict) else bool(changes)
        add_manifest = bool(manifest_path and manifest_planned
                            and manifest_path not in {item["path"] for item in changes})
        print(f"Resources to update ({len(changes) + int(add_manifest)}):")
        for item in changes:
            print(f"  {item['path']}")
        if add_manifest:
            print(f"  {manifest_path} (ownership manifest)")
        if not changes and not add_manifest:
            print("  (none)")
        unchanged = data.get("unchanged", [])
        if not changes and data.get("preview_state") == "no_changes":
            print(f"Resources already current: {len(unchanged)}")
        preserved = data.get("preserved", {})
        if preserved.get("harnesses"):
            print(f"Harnesses preserved: {', '.join(preserved['harnesses'])}")
        if data.get("preview_only") and (changes or add_manifest):
            print("Next step: rerun this command with --execute to apply the listed changes.")
        elif data.get("execution") in ("unconfirmed", "rollback_unconfirmed"):
            print("Next step: inspect the target and use the matching 'olympus config recover' command before retrying.")
        elif data.get("execution") == "rollback_confirmed":
            print("Next step: review the reported failure, then rerun the preview before deciding whether to retry.")
        elif response.get("issues") and data.get("preview_only"):
            print("Next step: resolve the listed blockers and rerun the preview; no target writes were made.")
        elif response.get("issues") and data.get("execution") == "not_started":
            print("Next step: resolve the listed blocker; execution did not start.")
        elif response.get("issues"):
            print("Next step: resolve the listed blocker and rerun the preview before applying.")
        elif result == "no_changes":
            print("Next step: none; the target is already current.")
    elif operation in ("doctor", "status"):
        state = data.get("installation_state")
        if state:
            print(f"Installation: {state}")
        integrity = data.get("integrity")
        if integrity:
            print(f"Integrity: {integrity}" + (" (metadata only; not verified)" if operation == "status" else ""))
        harnesses = data.get("harnesses", {})
        if isinstance(harnesses, dict):
            for name, item in harnesses.items():
                if isinstance(item, dict):
                    state = item.get("state", "unknown")
                    if operation == "status":
                        state += f"; integrity {item.get('integrity', 'unverified')}"
                    print(f"{name}: {state}")
                else:
                    print(f"{name}: {item}")
        verification = data.get("verification", {})
        if verification:
            print(f"Verification: {verification.get('state', 'unknown')}")
        user_configuration = data.get("user_configuration", {})
        if user_configuration:
            print(f"User configuration: {user_configuration.get('state', 'unknown')}")
        if data.get("recorded_version"):
            print(f"Recorded version: {data['recorded_version']}")
        if operation == "status":
            print("Next step: run 'olympus doctor' to verify installation integrity.")
        elif not response.get("issues"):
            print("Next step: none; no repair is needed." if result == "ok"
                  else "Next step: review the installation state before changing it.")
    elif setter:
        print("No setting change confirmed.")
    elif operation in ("install", "uninstall"):
        if data.get("engine"):
            print(f"Native engine: {data.get('state', data['engine'])}")
        if data.get("effects"):
            effects = {
                "none_confirmed": "No effects confirmed.",
                "unconfirmed_until_native_result": "Unconfirmed until the native engine returns.",
                "target_read_only_preview; temporary/cache effects may remain":
                    "Target was not changed; temporary/cache effects may remain.",
                "unconfirmed; descendant processes may continue":
                    "Effects are unconfirmed; descendant processes may continue.",
                "unconfirmed_after_native_failure": "Effects are unconfirmed after native failure.",
                "native_engine_confirmed_success": "Native engine confirmed success.",
                "global harness removed; CLI cleanup failed":
                    "Global resources were removed, but CLI PATH cleanup failed.",
            }.get(data["effects"], data["effects"])
            print(f"Effects: {effects}")
        if data.get("installation_state") and result != "preview":
            print(f"Installation: {data['installation_state']}")
        _emit_native_output_summary(data)
        if data.get("native_stderr"):
            print(data["native_stderr"].rstrip(), file=sys.stderr)
        if result == "preview":
            print("Next step: review the native plan, then rerun with --execute to apply it.")
        elif result == "ok" and operation == "install":
            print("Next step: run 'olympus doctor' to verify the installation.")
        elif result == "ok":
            print("Next step: open a new shell to refresh the removed PATH entry.")
        elif result == "blocked":
            print("Next step: resolve the listed blocker; no native engine was started.")
        elif result == "unconfirmed":
            print("Next step: inspect the selected installation and native output before retrying; effects are unconfirmed.")
        elif result == "failed":
            print("Next step: review the native diagnostic and resolve it before retrying.")
    elif operation == "config recover":
        recovery = data.get("recovery")
        if recovery:
            print(f"Recovery: {recovery}")
    else:
        for key, value in data.items():
            if value is None or isinstance(value, (str, int, float, bool)):
                print(f"{key}: {value}")

    _emit_issues(response)
    if operation == "doctor":
        for issue in response.get("issues", []):
            recommendation = _doctor_recommendation(issue.get("code"))
            scope = response.get("context", {}).get("scope")
            context = f" ({scope} scope)" if scope else ""
            print(f"Next step{context}: {recommendation}")
    elif operation == "config check" and response.get("issues"):
        print("Next step: reconcile source/output differences, then rerun 'olympus config check'.")


def emit(response: dict, as_json: bool, *, verbose: bool = False) -> None:
    if as_json:
        print(json.dumps(response, ensure_ascii=False))
        return
    if not verbose:
        _emit_human_summary(response)
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
                          f"opencode={role['models']['opencode']} ({role['representation']['opencode']})")
        elif key == "manual_edit_reminder" and response["operation"] == "config list":
            continue
        else:
            print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    if response["operation"] == "config list":
        print("Run 'olympus doctor' after manual edits.")
    _emit_issues(response)
    if response["operation"] == "doctor":
        for issue in response["issues"]:
            recommendation = _doctor_recommendation(issue.get("code"))
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
                source, args.family, args.opencode,
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
            print(model_edit._format_preview_human(preview, verbose=args.verbose))
        return 0

    # Execution is the explicit command without --dry-run. Show the exact
    # candidate before staging or replacing any target; no extra prompt.
    print("Execution preview (not yet applied):")
    print(model_edit._format_preview_human(preview, verbose=args.verbose, executing=True))
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


def _run_project_recovery(source: Path, args, response: dict, *, verbose: bool = False) -> int:
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
        emit(response, False, verbose=verbose)
        return error.code
    except (OSError, UnicodeError, source_edit.BatchError, source_edit.LockError) as error:
        response["result"] = "unconfirmed"
        response["issues"] = [{"code": "unconfirmed", "message": str(error)}]
        emit(response, False, verbose=verbose)
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
    if arguments == ["--_completion-query-v1"]:
        return _completion_query([])
    completion_shell = _completion_registration(arguments)
    if completion_shell is not None:
        print(_COMPLETION_POWERSHELL if completion_shell == "powershell" else _COMPLETION_BASH)
        return 0
    response = {"schema_version": 1, "operation": "arguments", "result": "ok",
                "context": {}, "data": {}, "issues": []}
    as_json = "--json" in arguments
    verbose = False

    def output(payload: dict, json_output: bool) -> None:
        emit(payload, json_output, verbose=verbose)

    try:
        cli_parser = parser()
        args = cli_parser.parse_args(arguments)
        verbose = args.verbose
        if args.version and args.command:
            raise CLIError("--version cannot be combined with a command", 2)
        if not args.version and not args.command:
            cli_parser.error("a command is required")
        operation = "version" if args.version else " ".join(filter(None, (
            args.command, getattr(args, "role_action", None) if args.command in _ROLE_NAMES
            else getattr(args, "action", None),
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
        if args.command == "completion":
            print(_COMPLETION_POWERSHELL if args.shell == "powershell" else _COMPLETION_BASH)
            return 0
        if args.version or args.command == "version":
            print(f"olympus {release_version(source)}")
            return 0
        if args.command == "update":
            from . import system_cli

            return system_cli.update(source, verbose=bool(args.verbose), force=bool(args.force))
        if args.command == "agents" and args.action == "list":
            from . import user_config

            scope, target = user_config.select_scope(source, args.scope, args.target)
            rows = user_config.effective_roles(source, scope, target)
            response["data"] = {"scope": scope, "target": str(target) if target else None, "roles": rows}
            response["result"] = "ok"
            output(response, args.json)
            return 0
        if args.command == "config" and args.action == "list":
            from . import user_config

            scope, target = user_config.select_scope(source, args.scope, args.target)
            response["data"] = user_config.config_listing(source, scope, target)
            response["result"] = "ok"
            output(response, as_json)
            return 0
        if args.command == "config" and args.action == "set-max-parallel":
            if not 1 <= args.value <= 8:
                raise CLIError("max-parallel must be an integer from 1 to 8.", 2)
            from . import user_config

            path, applied = user_config.set_max_children(source, args.value)
            response["data"] = {"max_children": args.value, "scope": "global",
                                "preference_scope": "global", "source": str(path),
                                "installed_agent_updated": applied}
            response["result"] = "ok"
            output(response, False)
            return 0
        if args.command in _ROLE_NAMES and args.role_action in ("set-model", "set-effort"):
            from . import user_config

            field = "model" if args.role_action == "set-model" else "effort"
            value = args.model_id if field == "model" else args.effort
            scope, target = user_config.select_scope(source, args.scope, args.target)
            path, applied = user_config.set_override(source, args.command, field, value, scope, target)
            response["data"] = {"role": args.command, field: value, "scope": scope,
                                 "target": str(target) if target else None,
                                 "source": str(path), "installed_agent_updated": applied}
            response["result"] = "ok"
            output(response, False)
            return 0
        if response["operation"] in ("models list", "config check"):
            harness = getattr(args, "harness", "opencode")
            response["context"]["harness"] = harness
            response["data"], response["issues"] = source_query(source, response["operation"], harness)
            if response["issues"]:
                response["result"] = "failed"
            output(response, as_json)
            return 1 if response["issues"] else 0
        if response["operation"] in ("models set-family", "agents set-model"):
            return _run_model_edit(source, args, response)
        if response["operation"] == "config recover":
            if args.scope == "global":
                code = _run_global_recovery(source, args, response)
                output(response, as_json)
                return code
            if args.scope is not None or args.target is not None:
                return _run_project_recovery(source, args, response, verbose=verbose)
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
                output(response, as_json)
                return code

            if args.execute:
                return config_apply.execute(
                    source, args, response, source_query=source_query,
                    load_renderer=load_renderer, release_version=release_version,
                    assignment_query=model_assignments, verbose=verbose,
                )
            code = config_apply.preview(source, args, response, source_query=source_query,
                                        load_renderer=load_renderer, release_version=release_version,
                                        assignment_query=model_assignments)
            config_apply.emit_preview(response, as_json, verbose=verbose)
            return code
        if response["operation"] == "doctor":
            from . import doctor
            from . import user_config
            from .models_catalog import CatalogError

            if args.scope == "global" and args.target is not None:
                raise CLIError("--target is available only with project scope.", 2)
            if args.scope is None and args.target is None:
                try:
                    args.target = user_config._managed_project(source, for_diagnostics=True)
                except user_config.UserConfigError as error:
                    response["result"] = "failed"
                    response["issues"] = [{"code": "invalid_user_configuration", "message": str(error)}]
                    output(response, as_json)
                    return 1
                args.scope = "project" if args.target is not None else "global"
            check_user_configuration = args.scope == "global"
            if not check_user_configuration:
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
                output(response, as_json)
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
                output(response, as_json)
                return code

            code = doctor.diagnose(source, args, response, source_version=release_version(source),
                                   source_query=source_query)
            if user_configuration is not None:
                response["data"]["user_configuration"] = user_configuration
            output(response, as_json)
            return code
        if response["operation"] in ("install", "uninstall"):
            from . import install_routing

            return install_routing.run(source, args, response, emit=output, as_json=as_json)
        code = installation_status(source, args, response)
        output(response, as_json)
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
        output(response, as_json)
        return error.code
    except ValueError as error:
        response["result"] = "failed"
        response["issues"].append({"code": "configuration_invalid", "message": str(error)})
        output(response, as_json)
        return 1
    except (OSError, UnicodeError) as error:
        response["result"] = "failed"
        response["issues"].append({"code": "read_failed", "message": str(error)})
        output(response, as_json)
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
        output(response, as_json)
        return code


if __name__ == "__main__":
    raise SystemExit(main())
