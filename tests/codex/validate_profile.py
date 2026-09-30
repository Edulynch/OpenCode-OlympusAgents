"""Static qualification for the experimental Olympus Codex profile."""

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
BASELINE = "c11d4f59370871a5c0978daab2512ea39c0928c0"
EXPECTED = {
    "veyra": ("gpt-6-luna", "max", "olympus-readonly"),
    "orin": ("gpt-6-luna", "max", "olympus-readonly"),
    "atlas": ("gpt-6.1-sol", "high", "olympus-readonly"),
    "kovan": ("gpt-6-luna", "max", "olympus-project"),
    "argus": ("gpt-6.1-sol", "high", "olympus-readonly"),
    "nox": ("gpt-6-luna", "max", "olympus-readonly"),
    "vera": ("gpt-6-luna", "max", "olympus-readonly"),
    "talos": ("gpt-6.1-sol", "high", "olympus-readonly"),
    "thales": ("gpt-6.1-sol", "xhigh", "olympus-readonly"),
    "helios": ("gpt-6.1-sol", "high", "olympus-readonly"),
}
OPENCODE_EXPECTED = {
    "kael": ("gpt-6.1-sol", "high"),
    "veyra": ("gpt-6-luna", "max"),
    "orin": ("gpt-6-luna", "max"),
    "atlas": ("gpt-6.1-sol", "high"),
    "kovan": ("gpt-6-luna", "max"),
    "argus": ("gpt-6.1-sol", "high"),
    "nox": ("gpt-6-luna", "max"),
    "vera": ("gpt-6-luna", "max"),
    "talos": ("gpt-6.1-sol", "high"),
    "thales": ("gpt-6.1-sol", "xhigh"),
    "helios": ("gpt-6.1-sol", "high"),
    "aegis": ("gpt-6-luna", "max"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def opencode_model(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"(?m)^model:\s*[\"']?openai/([A-Za-z0-9._-]+)#(low|medium|high|xhigh|max|ultra)[\"']?\s*$",
        text,
    )
    require(match is not None, f"missing OpenCode model/effort: {path.name}")
    return match.group(1), match.group(2)


def main() -> int:
    require(sys.version_info >= (3, 11), "Python 3.11+ is required for tomllib")
    config_path = ROOT / ".codex" / "config.toml"
    config = toml(config_path)
    require(config["model"] == "gpt-6.1-sol", "Kael model drifted")
    require(config["model_reasoning_effort"] == "high", "Kael effort drifted")
    require(config["approval_policy"] == "on-request", "approval policy drifted")
    require(config["default_permissions"] == "olympus-project", "default profile drifted")
    require(config["project_doc_fallback_filenames"] == ["CODEX.md"], "Codex root doc fallback drifted")
    require(config["project_doc_max_bytes"] == 32768, "Codex project-doc limit drifted")
    require(config["agents"]["enabled"] is True, "Codex multi-agent support must be enabled")
    require(config["agents"]["max_concurrent_threads_per_session"] == 4, "child concurrency cap must be four")
    require("sandbox_mode" not in config, "legacy sandbox mode must not shadow permission profiles")
    require("sandbox_workspace_write" not in config, "legacy workspace-write settings must not shadow permission profiles")

    profiles = config["permissions"]
    require(set(profiles) == {"olympus-project", "olympus-readonly"}, "unexpected permission profiles")
    require(profiles["olympus-project"]["extends"] == ":workspace", "project profile must extend :workspace")
    require(profiles["olympus-readonly"]["extends"] == ":read-only", "specialist profile must extend :read-only")
    project_fs = profiles["olympus-project"]["filesystem"][":workspace_roots"]
    read_fs = profiles["olympus-readonly"]["filesystem"][":workspace_roots"]
    protected = {".opencode", "opencode.jsonc", "install.ps1", "scripts/bootstrap.ps1", "CODEX.md"}
    require(project_fs.get(".") == "write", "project profile must allow workspace writes")
    require(read_fs.get(".") == "read", "specialist profile must be read-only")
    require(all(project_fs.get(path) == "read" for path in protected), "project profile lost a protected Olympus path")
    require(all(read_fs.get(path) == "read" for path in protected), "read-only profile lost a protected Olympus path")
    require(config["windows"]["sandbox"] == "elevated", "Windows must use the stronger local sandbox")

    files = sorted(AGENTS.glob("*.toml"))
    require({path.stem for path in files} == set(EXPECTED), "custom-agent roster differs from expected Olympus roles")
    names: set[str] = set()
    for path in files:
        role = toml(path)
        name = role["name"]
        require(name not in names, f"duplicate role identifier: {name}")
        names.add(name)
        require(name == path.stem, f"filename/name mismatch: {path.name}")
        require(role.get("description"), f"missing description: {path.name}")
        require(role.get("developer_instructions"), f"missing instructions: {path.name}")
        model, effort, permission = EXPECTED[name]
        require(role["model"] == model, f"model mismatch: {name}")
        require(role["model_reasoning_effort"] == effort, f"effort mismatch: {name}")
        require(role["default_permissions"] == permission, f"permission profile mismatch: {name}")
        require(role.get("agents", {}).get("enabled") is False, f"recursive delegation not disabled: {name}")

    codex_docs = (ROOT / "CODEX.md").read_text(encoding="utf-8")
    require(all(f"`{name}`" in codex_docs for name in EXPECTED), "root routing references a missing role")
    require("Aegis is intentionally not a Codex custom agent" in codex_docs, "Aegis gap must remain explicit")
    require(not (ROOT / "AGENTS.md").exists(), "do not add AGENTS.md: it can alter other runtimes")
    codex_runtime_text = "\n".join(
        path.read_text(encoding="utf-8") for path in [config_path, ROOT / "CODEX.md", *files]
    )
    require("gpt-6-sol" not in codex_runtime_text, "stale Sol model identifier found in Codex runtime files")
    require("gpt-6-luna" in codex_runtime_text, "Luna roles must remain Luna")
    require(not (AGENTS / "aegis.toml").exists(), "unsafe Codex Aegis entrypoint must stay absent")

    opencode_agents = ROOT / ".opencode" / "agents"
    opencode_files = sorted(opencode_agents.glob("*.md"))
    require({path.stem for path in opencode_files} == set(OPENCODE_EXPECTED), "OpenCode roster changed")
    for path in opencode_files:
        require(opencode_model(path) == OPENCODE_EXPECTED[path.stem], f"OpenCode model/effort drifted: {path.name}")
    opencode_config = (ROOT / "opencode.jsonc").read_text(encoding="utf-8")
    require('"default_agent": "kael"' in opencode_config, "OpenCode Kael default drifted")
    require('"model": "openai/gpt-6.1-sol"' in opencode_config, "OpenCode default model drifted")
    opencode_runtime_text = "\n".join(
        path.read_text(encoding="utf-8") for path in [ROOT / "opencode.jsonc", *opencode_files]
    )
    require("gpt-6-sol" not in opencode_runtime_text, "stale Sol model identifier found in OpenCode runtime files")
    untouched = subprocess.run(
        ["git", "diff", "--quiet", BASELINE, "--", ".opencode", "opencode.jsonc"],
        cwd=ROOT,
        check=False,
        timeout=15,
    )
    require(untouched.returncode == 0, "OpenCode runtime files differ from the stated baseline")

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
        for name, (model, effort, _) in {"kael": ("gpt-6.1-sol", "high", "olympus-project"), **EXPECTED}.items():
            require(model in available, f"Codex bundled model catalog lacks {model} for {name}")
            efforts = {item["effort"] for item in available[model]["supported_reasoning_levels"]}
            require(effort in efforts, f"Codex model {model} lacks {effort} for {name}")
        print("Codex bundled model catalog: PASS")
    else:
        print("Codex CLI absent: bundled model catalog check skipped")

    print("Olympus Codex static profile qualification: PASS")
    print(
        f"Codex custom agents: {len(files)}; Aegis: intentionally absent; concurrency cap: 4; "
        f"OpenCode roles: {len(opencode_files)}; OpenCode files unchanged from {BASELINE[:7]}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, OSError, subprocess.SubprocessError, tomllib.TOMLDecodeError) as error:
        print(f"Olympus Codex static profile qualification: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
