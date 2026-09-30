"""Static Codex adapter qualification against the canonical Olympus sources."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / ".codex" / "agents"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def main() -> int:
    require(sys.version_info >= (3, 11), "Python 3.11+ is required for tomllib")
    models = toml(ROOT / "olympus" / "core" / "models.toml")
    policy = toml(ROOT / "olympus" / "policies" / "orchestration.toml")
    capabilities = toml(ROOT / "olympus" / "harnesses" / "capabilities.toml")
    canonical = {path.stem for path in (ROOT / "olympus" / "roles").glob("*.md")}
    supported_children = canonical - {"kael", "aegis"}
    require(len(canonical) == 12 and canonical == set(models["roles"]), "canonical role/model roster mismatch")

    config_path = ROOT / ".codex" / "config.toml"
    config = toml(config_path)
    kael = models["roles"]["kael"]
    kael_family = models["families"][kael["family"]]
    require(config["model"] == kael_family["codex"], "Kael model drifted from Core")
    require(config["model_reasoning_effort"] == kael["effort"], "Kael effort drifted from Core")
    require(config["approval_policy"] == "on-request", "approval policy drifted")
    require(config["default_permissions"] == "olympus-project", "default profile drifted")
    require(config["project_doc_fallback_filenames"] == ["CODEX.md"], "Codex root doc fallback drifted")
    require(config["project_doc_max_bytes"] == 32768, "Codex project-doc limit drifted")
    require(config["agents"]["enabled"] is True, "Codex multi-agent support must be enabled")
    require(config["agents"]["max_concurrent_threads_per_session"] == policy["max_children"], "Codex native cap differs from canonical max children")
    require("sandbox_mode" not in config and "sandbox_workspace_write" not in config, "legacy sandbox settings must not shadow permission profiles")

    profiles = config["permissions"]
    require(set(profiles) == {"olympus-project", "olympus-readonly"}, "unexpected permission profiles")
    require(profiles["olympus-project"]["extends"] == ":workspace", "project profile must extend :workspace")
    require(profiles["olympus-readonly"]["extends"] == ":read-only", "specialist profile must be read-only")
    project_fs = profiles["olympus-project"]["filesystem"][":workspace_roots"]
    read_fs = profiles["olympus-readonly"]["filesystem"][":workspace_roots"]
    protected = {".opencode", "opencode.jsonc", "install.ps1", "scripts/bootstrap.ps1", "scripts/render_harnesses.py", "olympus", "CODEX.md"}
    require(project_fs.get(".") == "write" and read_fs.get(".") == "read", "workspace permission profiles drifted")
    require(all(project_fs.get(path) == "read" for path in protected), "project profile lost an Olympus-owned read-only path")
    require(all(read_fs.get(path) == "read" for path in protected), "read-only profile lost an Olympus-owned read-only path")
    require(config["windows"]["sandbox"] == "elevated", "Windows must use the stronger local sandbox")

    files = sorted(AGENTS.glob("*.toml"))
    require({path.stem for path in files} == supported_children, "Codex custom-agent roster differs from supported canonical roles")
    for path in files:
        role = toml(path)
        name = path.stem
        intent = models["roles"][name]
        family = models["families"][intent["family"]]
        require(role["name"] == name, f"filename/name mismatch: {path.name}")
        require(role.get("description") and role.get("developer_instructions"), f"incomplete agent: {path.name}")
        require(role["model"] == family["codex"], f"model mismatch with Core: {name}")
        require(role["model_reasoning_effort"] == intent["effort"], f"effort mismatch with Core: {name}")
        require(role["default_permissions"] == ("olympus-project" if name == "kovan" else "olympus-readonly"), f"permission profile mismatch: {name}")
        require(role.get("agents", {}).get("enabled") is False, f"recursive delegation not disabled: {name}")

    codex_docs = (ROOT / "CODEX.md").read_text(encoding="utf-8")
    require(all(f"`{name}`" in codex_docs for name in supported_children), "root routing references a missing supported role")
    require("Aegis is intentionally not a Codex custom agent" in codex_docs, "Aegis gap must remain explicit")
    require(not (ROOT / "AGENTS.md").exists(), "do not add AGENTS.md: it can alter other runtimes")
    require(not (AGENTS / "aegis.toml").exists(), "unsafe Codex Aegis entrypoint must stay absent")
    codex_runtime_text = "\n".join(path.read_text(encoding="utf-8") for path in [config_path, ROOT / "CODEX.md", *files])
    require("gpt-6-sol" not in codex_runtime_text, "stale Sol model identifier found in Codex runtime files")
    require("gpt-6-luna" in codex_runtime_text, "Luna roles must remain Luna")
    require(capabilities["codex"]["ALLOW"] == "SUPPORTED", "Codex ALLOW capability drifted")
    require(capabilities["codex"]["ASK"] == "ADAPTABLE", "Codex ASK capability drifted")
    require(capabilities["codex"]["DENY"] == "GAP", "Codex hard DENY gap must remain explicit")
    require(capabilities["codex"]["AEGIS"] == "GAP", "Codex Aegis gap must remain explicit")
    require(capabilities["codex"]["RESULT_DELIVERY"] == "SUPPORTED", "Codex result delivery capability drifted")
    require(capabilities["codex"]["MULTI_AGENT"] == "SUPPORTED" and capabilities["codex"]["BOUNDED_PARALLELISM"] == "SUPPORTED", "runtime-confirmed multi-agent capabilities drifted")

    opencode_agents = ROOT / ".opencode" / "agents"
    opencode_files = sorted(opencode_agents.glob("*.md"))
    require({path.stem for path in opencode_files} == canonical, "OpenCode roster changed")
    opencode_runtime_text = "\n".join(path.read_text(encoding="utf-8") for path in [ROOT / "opencode.jsonc", *opencode_files])
    require("gpt-6-sol" not in opencode_runtime_text, "stale Sol model identifier found in OpenCode runtime files")
    require('"default_agent": "kael"' in (ROOT / "opencode.jsonc").read_text(encoding="utf-8"), "OpenCode default agent drifted")
    render = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "render_harnesses.py"), "check", "--harness", "all"],
        cwd=ROOT,
        check=False,
        timeout=45,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    require(render.returncode == 0, "generated adapters drifted: " + render.stdout + render.stderr)

    codex = shutil.which("codex")
    if codex:
        result = subprocess.run(
            [codex, "debug", "models", "--bundled"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        catalog = json.loads(result.stdout)
        available = {entry["slug"]: entry for entry in catalog["models"]}
        for role, intent in models["roles"].items():
            model = models["families"][intent["family"]]["codex"]
            require(model in available, f"Codex bundled model catalog lacks {model} for {role}")
            efforts = {item["effort"] for item in available[model]["supported_reasoning_levels"]}
            require(intent["effort"] in efforts, f"Codex model {model} lacks {intent['effort']} for {role}")
        print("Codex bundled model catalog: PASS")
    else:
        print("Codex CLI absent: bundled model catalog check skipped")

    print("Olympus Codex static profile qualification: PASS")
    print(f"Codex specialists: {len(files)}; Kael is root; Aegis: explicit GAP; max children: {policy['max_children']}; OpenCode roles: {len(opencode_files)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, OSError, subprocess.SubprocessError, tomllib.TOMLDecodeError) as error:
        print(f"Olympus Codex static profile qualification: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
