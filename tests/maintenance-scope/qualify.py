"""Static checks for Issue #28's single-Kael contextual-maintenance contract."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"{name} FAIL")
    print(f"{name} PASS")


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def main() -> int:
    policy = text("olympus/policies/maintenance-context.md")
    routing = text("olympus/policies/routing.md")
    prompt = text(".opencode/agents/kael.md")
    source_prompt = text("olympus/harnesses/opencode/agent-prompts/kael.md")
    kael_metadata = text("olympus/harnesses/opencode/agent-metadata/kael.md")
    roles = {path.stem for path in (ROOT / "olympus/roles").glob("*.md")}
    models = tomllib.loads(text("olympus/core/models.toml"))
    identities = tomllib.loads(text("olympus/core/identities.toml"))
    capabilities = tomllib.loads(text("olympus/harnesses/capabilities.toml"))
    config_source = re.sub(r"(?m)^\s*//.*(?:\r?\n|$)", "", text("olympus/harnesses/opencode/config.jsonc"))
    opencode_config = json.loads(config_source)
    generated_roles = {path.stem for path in (ROOT / ".opencode/agents").glob("*.md")}

    check("ONE_KAEL_ROOT", "root orchestrator for both ordinary project work and OlympusAgents development" in policy
          and "There is no separate maintenance role" in policy
          and "never create a second Kael or route around Kael" in routing)
    check("CANONICAL_ROSTER_ALIGNED", len(roles) == 11 and roles == set(models["roles"]) == set(identities["roles"]))
    check("NO_RETIRED_PRODUCT_ROUTE", "aegis" not in roles and not (ROOT / "olympus/roles/aegis.md").exists()
          and not (ROOT / "olympus/policies/maintenance-plane.md").exists()
          and not (ROOT / "olympus/harnesses/opencode/maintain.md").exists()
          and not (ROOT / "olympus/harnesses/opencode/agent-prompts/aegis.md").exists()
          and not (ROOT / "olympus/harnesses/opencode/agent-metadata/aegis.md").exists()
          and "aegis" not in generated_roles
          and not (ROOT / ".opencode/commands/maintain.md").exists())
    check("CONTEXTUAL_TARGET_IDENTITY", all(marker in policy for marker in (
        "olympus/core/models.toml", "olympus/core/identities.toml",
        "olympus/policies/routing.md", "project-identity evidence",
        "do not perform dependent writes")))
    check("EXTERNAL_PROJECT_BOUNDARY", "different user project" in policy
          and re.search(r"do not reach into a separate OlympusAgents checkout", policy, re.IGNORECASE)
          and "manifest-owned files" in policy)
    check("GOAL_REMAINS_OPT_IN", "/goal" in policy and "remains opt-in" in policy
          and "do not require it" in policy and "assume it delegates work" in policy)
    check("KAEL_PROMPT_USES_CANONICAL_POLICY", policy.strip() in prompt
          and "project-identity evidence" in policy
          and "ordinary Kael workflow" in policy)
    check("KAEL_DIRECT_TOOLS_ARE_SCOPE_BOUND", "native `edit`" in source_prompt
          and "native `shell`" in source_prompt
          and "effective permission and exact task scope allow" in source_prompt
          and "`WRITE_SCOPE`/`GIT_SCOPE`" in source_prompt
          and "`DO_NOT_TOUCH`" in source_prompt
          and "Master Orchestrator is read-only" not in source_prompt
          and "Kael remains shell DENY" not in source_prompt
          and re.search(r'(?m)^  - action: shell\n    resource: "\*"\n    effect: allow$', kael_metadata)
          and re.search(r'(?m)^  - action: edit\n    resource: "\*"\n    effect: allow$', kael_metadata))
    check("ADAPTER_CAPABILITY_CONTRACT", capabilities["opencode"]["CONTEXTUAL_OLYMPUS_MAINTENANCE"] == "SUPPORTED"
          and capabilities["codex"]["CONTEXTUAL_OLYMPUS_MAINTENANCE"] == "GAP"
          and "AEGIS" not in capabilities["opencode"] and "AEGIS" not in capabilities["codex"])
    serena = opencode_config["mcp"]["servers"]["serena"]
    check("SERENA_REGISTERED_ONCE_IN_NATIVE_V2_CONFIG", serena["type"] == "local"
          and serena["disabled"] is False and serena["codemode"] is False
          and serena["command"][0] == "serena" and "--project-from-cwd" in serena["command"]
          and len(re.findall(r'(?m)^\s*"serena"\s*:', config_source)) == 1)
    semantic_tools = (
        "get_symbols_overview", "find_symbol", "find_referencing_symbols",
        "find_implementations", "find_declaration", "get_diagnostics_for_file",
    )
    for role in ("kael", "veyra", "kovan"):
        metadata = text(f"olympus/harnesses/opencode/agent-metadata/{role}.md")
        check(f"SERENA_READ_ONLY_TOOLS_ALLOWED_{role.upper()}", all(
            re.search(rf"(?m)^  - action: serena_{tool}\n    resource: \"\*\"\n    effect: allow$", metadata)
            for tool in semantic_tools
        ) and not re.search(r"(?m)^  - action: serena_\*\n    resource: \"\*\"\n    effect: allow$", metadata))
    check("SERENA_NOT_BLOCKED_BY_KOVAN_PROMPT", "Do not use MCP Serena tools" not in text("olympus/harnesses/opencode/agent-prompts/kovan.md"))
    print("CONTEXTUAL MAINTENANCE QUALIFICATION: PASS (static source/generated contract only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
