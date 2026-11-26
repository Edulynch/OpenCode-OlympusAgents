"""Static checks for Issue #28's single-Kael contextual-maintenance contract."""

from __future__ import annotations

import json
import re
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"{name} FAIL")
    print(f"{name} PASS")


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def metadata_rules(metadata: str) -> list[dict[str, str]]:
    """Read native YAML permission triples without relying on the agent's prose."""
    return [
        {"action": action, "resource": resource.strip('"'), "effect": effect}
        for action, resource, effect in re.findall(
            r'(?m)^  - action: ([^\r\n]+)\r?\n    resource: ([^\r\n]+)\r?\n    effect: (allow|deny|ask)\r?$',
            metadata,
        )
    ]


def permission_effect(global_rules: list[dict[str, str]], metadata: str,
                      action: str, resource: str = "*") -> str:
    """Resolve ordered OpenCode V2 permissions with the final matching rule."""
    effective = "allow"  # OpenCode V2's documented base wildcard permission.
    for rule in [*global_rules, *metadata_rules(metadata)]:
        if fnmatchcase(action, rule["action"]) and fnmatchcase(resource, rule["resource"]):
            effective = rule["effect"]
    return effective


def no_bundled_mcp_servers(config: dict) -> bool:
    return not config.get("mcp", {}).get("servers", {})


def main() -> int:
    policy = text("olympus/policies/maintenance-context.md")
    routing = text("olympus/policies/routing.md")
    source_prompt = text("olympus/harnesses/opencode/agent-prompts/kael.md")
    kael_metadata = text("olympus/harnesses/opencode/agent-metadata/kael.md")
    roles = {path.stem for path in (ROOT / "olympus/roles").glob("*.md")}
    models = tomllib.loads(text("olympus/core/models.toml"))
    identities = tomllib.loads(text("olympus/core/identities.toml"))
    capabilities = tomllib.loads(text("olympus/harnesses/capabilities.toml"))
    config_source = re.sub(r"(?m)^\s*//.*(?:\r?\n|$)", "", text("olympus/harnesses/opencode/config.jsonc"))
    opencode_config = json.loads(config_source)
    global_source = re.sub(r"(?m)^\s*//.*(?:\r?\n|$)", "", text("olympus/harnesses/opencode/global-permissions.jsonc"))
    minimal_global_config = json.loads(global_source)
    generated_roles = {path.stem for path in (ROOT / ".opencode/agents").glob("*.md")}

    check("ONE_KAEL_ROOT", "root orchestrator for both ordinary project work and OlympusAgents development" in policy
          and "There is no separate maintenance role" in policy
          and "Kael is the single ROOT ORCHESTRATOR" in routing
          and "Atlas is a separate primary analyst/planner" in routing)
    check("CANONICAL_ROSTER_ALIGNED", len(roles) == 9 and roles == set(models["roles"]) == set(identities["roles"]))
    check("NO_RETIRED_PRODUCT_ROUTE", "aegis" not in roles and not (ROOT / "olympus/roles/aegis.md").exists()
          and not (ROOT / "olympus/policies/maintenance-plane.md").exists()
          and not (ROOT / "olympus/harnesses/opencode/maintain.md").exists()
          and not (ROOT / "olympus/harnesses/opencode/agent-prompts/aegis.md").exists()
          and not (ROOT / "olympus/harnesses/opencode/agent-metadata/aegis.md").exists()
          and "aegis" not in generated_roles
          and not (ROOT / ".opencode/commands/maintain.md").exists())
    check("CONTEXTUAL_TARGET_IDENTITY", all(marker in policy for marker in (
        "olympus/core/models.toml", "olympus/core/identities.toml",
        "olympus/policies/routing.md", "independent project identity",
        "If identity, ownership, or target is unclear or conflicting, stop dependent work")))
    check("EXTERNAL_PROJECT_BOUNDARY", "different user project" in policy
          and re.search(r"do not reach into a separate OlympusAgents checkout", policy, re.IGNORECASE)
          and "manifest-owned files" in policy)
    check("GOAL_REMAINS_OPT_IN", "/goal" in policy and "remains opt-in" in policy
          and "do not require it" in policy and "assume it delegates work" in policy)
    check("KAEL_PROMPT_USES_CANONICAL_POLICY", source_prompt.count("{{maintenance_context_policy}}") == 1
          and "independent project identity" in policy
          and "normal routing and authority rules" in policy)
    preflight = " ".join(source_prompt.partition("### OpenCode repository preflight\n")[2].split("\n## ", 1)[0].split())
    check("KAEL_REPOSITORY_PREFLIGHT_IS_EVIDENCE_ONLY", all(
        marker in preflight for marker in (
            "Kael never runs `git rev-parse`, shell, or repository read/search tools",
            "Reuse an explicit root and identity only from native session context",
            "an Atlas handoff, or Veyra's bounded evidence",
            "If evidence is missing or conflicting, route Veyra",
        )
    ) and "run `git rev-parse --show-toplevel` alone" not in preflight
      and "Kael never probes the root or reads repository files" in policy)
    check("KAEL_DIRECT_REPOSITORY_ACCESS_DENIED", "Kael does not read or search repositories, research, run shell/Git/tests, implement, or mutate files" in source_prompt
          and re.search(r"Kael never reads/searches repositories, runs\s+shell/Git/tests, implements, or executes technical validation", source_prompt)
          and "`WRITE_SCOPE`/`GIT_SCOPE`" in source_prompt
          and "`DO_NOT_TOUCH`" in source_prompt
          and "Kael may directly implement" not in source_prompt
          and "Kael may use native `edit` for small" not in source_prompt
          and "Kael may use native `shell` for small" not in source_prompt)
    kael_rules = metadata_rules(kael_metadata)
    check("KAEL_NATIVE_METADATA_LEAST_PRIVILEGE",
           {"action": "shell", "resource": "*", "effect": "deny"} in kael_rules
           and {"action": "edit", "resource": "*", "effect": "deny"} in kael_rules
           and {"action": "serena_*", "resource": "*", "effect": "deny"} in kael_rules
           and all({"action": action, "resource": "*", "effect": "deny"} in kael_rules
                   for action in ("execute", "read", "glob", "grep", "list", "lsp", "webfetch", "websearch"))
           and not any(rule["action"] == "shell" and rule["effect"] == "allow" for rule in kael_rules)
           and not any(rule["action"].startswith("serena_") and rule["effect"] == "allow" for rule in kael_rules))
    expected_children = ("veyra", "kovan", "nox", "vera", "talos", "helios", "thales")
    kael_children = tuple(rule["resource"] for rule in kael_rules
                          if rule["action"] == "subagent" and rule["effect"] == "allow")
    check("KAEL_SPECIALIST_ALLOWLIST_UNCHANGED", kael_children == expected_children)
    check("ADAPTER_CAPABILITY_CONTRACT", set(capabilities) == {"opencode"}
          and capabilities["opencode"]["CONTEXTUAL_OLYMPUS_MAINTENANCE"] == "SUPPORTED"
          and "AEGIS" not in capabilities["opencode"])
    check("NO_BUNDLED_MCP_SERVERS", no_bundled_mcp_servers(opencode_config))
    check("NO_BUNDLED_MCP_SERVER_QUALIFICATION_REJECTS_DECLARATION",
          not no_bundled_mcp_servers({"mcp": {"servers": {"synthetic": {"type": "local"}}}}))
    check("NO_BUNDLED_MCP_SERVER_QUALIFICATION_ACCEPTS_ABSENT_OR_EMPTY",
          no_bundled_mcp_servers({}) and no_bundled_mcp_servers({"mcp": {"servers": {}}}))
    semantic_tools = (
        "get_symbols_overview", "find_symbol", "find_referencing_symbols",
        "find_implementations", "find_declaration", "get_diagnostics_for_file",
    )
    for role in ("veyra", "kovan"):
        metadata = text(f"olympus/harnesses/opencode/agent-metadata/{role}.md")
        check(f"SERENA_READ_ONLY_TOOLS_ALLOWED_{role.upper()}", all(
            re.search(rf"(?m)^  - action: serena_{tool}\n    resource: \"\*\"\n    effect: allow$", metadata)
            for tool in semantic_tools
        ) and not re.search(r"(?m)^  - action: serena_\*\n    resource: \"\*\"\n    effect: allow$", metadata))
    # The global denial precedes all explicit read-only Serena allowances.
    global_rules = opencode_config["permissions"]
    minimal_global_rules = minimal_global_config["permissions"]
    check("SERENA_DENY_BY_DEFAULT", any(
        rule == {"action": "serena_*", "resource": "*", "effect": "deny"}
        for rule in global_rules
    ))
    check("KAEL_SERENA_DENIED_WITH_MINIMAL_GLOBAL",
          not any(rule["action"].startswith("serena_") for rule in minimal_global_rules)
          and all(permission_effect(minimal_global_rules, kael_metadata, f"serena_{tool}") == "deny"
                  for tool in semantic_tools))
    protected_serena_tools = (
        "serena_replace_symbol_body", "serena_rename_symbol",
        "serena_insert_after_symbol", "serena_insert_before_symbol",
        "serena_replace_content", "serena_create_text_file",
        "serena_serena_repl", "serena_execute_shell_command",
        "serena_write_memory",
    )
    role_metadata = {
        path.stem: path.read_text(encoding="utf-8")
        for path in (ROOT / "olympus/harnesses/opencode/agent-metadata").glob("*.md")
    }
    check("SERENA_MUTATION_TOOLS_DENIED_FOR_EVERY_ROLE", all(
        permission_effect(global_rules, metadata, action) == "deny"
        for metadata in role_metadata.values()
        for action in protected_serena_tools
    ))
    check("SERENA_READ_ONLY_SEMANTICS_EFFECTIVE", all(
        permission_effect(global_rules, role_metadata[role], f"serena_{tool}") == "allow"
        for role in ("kovan", "veyra")
        for tool in semantic_tools
    ) and all(
        permission_effect(global_rules, role_metadata["kael"], f"serena_{tool}") == "deny"
        for tool in semantic_tools
    ))
    check("KAEL_SHELL_DENIED_FOR_ALL_COMMANDS", all(
        permission_effect(global_rules, kael_metadata, "shell", command) == expected
        for command, expected in (
            ("git rev-parse --show-toplevel", "deny"),
            ("git status --short", "deny"),
            ("git branch --show-current", "deny"),
            ("git ls-files -- olympus/core/models.toml", "deny"),
            ("git diff --check", "deny"),
            ("git diff --stat", "deny"),
            ("python scripts/check_docs.py", "deny"),
            ("git push origin feat/28-single-kael-maintenance", "deny"),
            ("git reset --hard", "deny"),
            ("Remove-Item docs/DEVELOPMENT.md", "deny"),
        )
    ))
    check("KAEL_EDIT_DENIED_KOVAN_AND_PLUGIN_BOUNDARIES_UNCHANGED", all(
        permission_effect(global_rules, kael_metadata, "edit", path) == "deny"
        for path in ("src/cart.ts", "olympus/core/models.toml")
    ) and permission_effect(global_rules, role_metadata["kovan"], "edit", "src/cart.ts") == "allow"
      and permission_effect(global_rules, role_metadata["kovan"], "edit", "olympus/core/models.toml") == "allow"
      and permission_effect(global_rules, role_metadata["kovan"], "edit", ".opencode/plugins/project-owned/index.ts") == "ask"
      and permission_effect(global_rules, role_metadata["kovan"], "edit", ".opencode/plugins/olympus-activity/activity.ts") == "deny"
      and permission_effect(global_rules, role_metadata["kovan"], "edit", ".opencode/agents/kovan.md") == "deny")
    check("KAEL_EXTERNAL_DIRECTORY_RULES_UNCHANGED",
          not any(rule["action"] == "external_directory" for rule in kael_rules)
          and permission_effect(global_rules, kael_metadata, "external_directory", "C:/workspace/sibling/src/cart.ts") == "ask")
    check("SERENA_NOT_BLOCKED_BY_KOVAN_PROMPT", "Do not use MCP Serena tools" not in text("olympus/harnesses/opencode/agent-prompts/kovan.md"))
    print("CONTEXTUAL MAINTENANCE QUALIFICATION: PASS (static source/generated contract only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
