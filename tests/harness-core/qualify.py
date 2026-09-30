"""Static and renderer qualifications for the canonical Olympus Core/adapters."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RENDERER = ROOT / "scripts" / "render_harnesses.py"
EXPECTED_CAPABILITIES = {
    "ROOT_ORCHESTRATOR",
    "CUSTOM_SPECIALISTS",
    "PER_ROLE_MODEL",
    "PER_ROLE_REASONING",
    "MULTI_AGENT",
    "BOUNDED_PARALLELISM",
    "QUESTION_CENTRALIZATION",
    "COMPLETION_BARRIER",
    "RESULT_DELIVERY",
    "RESULT_RECONCILIATION",
    "ALLOW",
    "ASK",
    "DENY",
    "AEGIS",
    "ACTIVITY_VISIBILITY",
}


def check(name: str, ok: bool) -> None:
    if not ok:
        raise AssertionError(f"{name} FAIL")
    print(f"{name} PASS")


def run_renderer(action: str, harness: str, root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RENDERER), action, "--harness", harness, "--root", str(root)],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=45,
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    check("PYTHON_311_PLUS", sys.version_info >= (3, 11))
    with (ROOT / "olympus" / "core" / "models.toml").open("rb") as stream:
        models = tomllib.load(stream)
    with (ROOT / "olympus" / "policies" / "orchestration.toml").open("rb") as stream:
        orchestration = tomllib.load(stream)
    with (ROOT / "olympus" / "harnesses" / "capabilities.toml").open("rb") as stream:
        capabilities = tomllib.load(stream)

    canonical_roles = {path.stem for path in (ROOT / "olympus" / "roles").glob("*.md")}
    check("CANONICAL_12_UNIQUE_ROLE_FILES", len(canonical_roles) == 12 and canonical_roles == set(models["roles"]))
    check("ONE_ROOT_ORCHESTRATOR", "ROOT ORCHESTRATOR" in (ROOT / "olympus/roles/kael.md").read_text(encoding="utf-8"))

    opencode_files = {path.stem: path for path in (ROOT / ".opencode/agents").glob("*.md")}
    codex_files = {path.stem: path for path in (ROOT / ".codex/agents").glob("*.toml")}
    check("OPENCODE_EXPECTED_ROSTER", set(opencode_files) == canonical_roles)
    check("CODEX_EXPECTED_SUPPORTED_ROSTER", set(codex_files) == canonical_roles - {"kael", "aegis"})

    for role, intent in models["roles"].items():
        family = models["families"][intent["family"]]
        opencode_text = opencode_files[role].read_text(encoding="utf-8")
        opencode_model = f"{family['opencode']}#{intent['effort']}"
        check(f"OPENCODE_MODEL_{role.upper()}", f"model: \"{opencode_model}\"" in opencode_text or f"model: {opencode_model}" in opencode_text)
        if role == "kael":
            continue
        if role == "aegis":
            check("CODEX_AEGIS_OMITTED", role not in codex_files)
            continue
        with codex_files[role].open("rb") as stream:
            codex_agent = tomllib.load(stream)
        check(f"CODEX_MODEL_{role.upper()}", codex_agent["model"] == family["codex"])
        check(f"CODEX_EFFORT_{role.upper()}", codex_agent["model_reasoning_effort"] == intent["effort"])
        check(f"ROLE_FILENAME_MAPPING_{role.upper()}", codex_agent["name"] == role == codex_files[role].stem)

    kael_intent = models["roles"]["kael"]
    kael_family = models["families"][kael_intent["family"]]
    codex_config = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
    check("CODEX_ROOT_MODEL_INTENT", codex_config["model"] == kael_family["codex"] and codex_config["model_reasoning_effort"] == kael_intent["effort"])
    check("SOL_TRANSLATION_BOTH_ADAPTERS", models["families"]["sol"]["opencode"] == "openai/gpt-6.1-sol" and models["families"]["sol"]["codex"] == "gpt-6.1-sol")
    check("LUNA_REMAINS_LUNA", models["families"]["luna"]["opencode"].endswith("gpt-6-luna") and models["families"]["luna"]["codex"] == "gpt-6-luna" and all(models["roles"][r]["family"] == "luna" for r in ("veyra", "orin", "kovan", "nox", "vera", "aegis")))
    check("NO_STALE_GPT_6_SOL_OUTPUT", all("gpt-6-sol" not in path.read_text(encoding="utf-8") for path in [*opencode_files.values(), *codex_files.values(), ROOT / "CODEX.md", ROOT / ".codex/config.toml", ROOT / "opencode.jsonc"]))
    check("EFFORTS_CANONICAL", models["roles"]["thales"]["effort"] == "xhigh" and models["roles"]["kovan"]["effort"] == "max" and all(models["roles"][r]["effort"] == "high" for r in ("kael", "atlas", "argus", "talos", "helios")))

    check("MAX_CHILDREN_CANONICAL_FOUR", orchestration["max_children"] == 4)
    routing = (ROOT / "olympus/policies/routing.md").read_text(encoding="utf-8")
    check("TRIVIAL_FAST_PATH_CANONICAL", "trivial implementation fast path" in routing and routing.count("trivial implementation fast path") == 1)
    lifecycle = (ROOT / "olympus/policies/result-lifecycle.md").read_text(encoding="utf-8")
    check("QUESTION_BARRIER_CANONICAL_ONCE", lifecycle.count("## Question barrier") == 1)
    check("COMPLETION_BARRIER_CANONICAL_ONCE", lifecycle.count("## Completion barrier") == 1)
    check("RESULT_RECONCILIATION_CANONICAL_ONCE", lifecycle.count("## Missing-result reconciliation") == 1)
    check("NO_BLIND_RETRY_CANONICAL_ONCE", lifecycle.count("## No blind retry") == 1)
    authority = (ROOT / "olympus/policies/authority.md").read_text(encoding="utf-8")
    check("AUTHORITY_SEMANTICS_CANONICAL", all(authority.count(f"**{term}**") == 1 for term in ("ALLOW", "ASK", "DENY")))

    check("OPENCODE_DENY_SUPPORTED", capabilities["opencode"]["DENY"] == "SUPPORTED")
    check("CODEX_DENY_GAP", capabilities["codex"]["DENY"] == "GAP")
    check("OPENCODE_AEGIS_SUPPORTED", capabilities["opencode"]["AEGIS"] == "SUPPORTED" and (ROOT / ".opencode/agents/aegis.md").is_file())
    check("CODEX_AEGIS_GAP", capabilities["codex"]["AEGIS"] == "GAP" and not (ROOT / ".codex/agents/aegis.toml").exists())
    check("CODEX_RESULT_DELIVERY_SUPPORTED", capabilities["codex"]["RESULT_DELIVERY"] == "SUPPORTED")
    check("CAPABILITY_CONTRACT_COMPLETE", set(capabilities) == {"opencode", "codex"} and all(set(value) == EXPECTED_CAPABILITIES for value in capabilities.values()) and all(state in {"SUPPORTED", "ADAPTABLE", "PARTIAL", "GAP", "NOT_NEEDED"} for value in capabilities.values() for state in value.values()))
    check("CODEX_ACTIVITY_IS_BASIC_PARTIAL", capabilities["codex"]["ACTIVITY_VISIBILITY"] == "PARTIAL")
    check("CODEX_ASK_ADAPTABLE", capabilities["codex"]["ASK"] == "ADAPTABLE")

    protected_paths = ("olympus/**", ".codex/**", "CODEX.md", "scripts/render_harnesses.py")
    protected = True
    for role, path in opencode_files.items():
        if role == "aegis":
            continue
        header = path.read_text(encoding="utf-8").split("\n---\n", 1)[0]
        for resource in protected_paths:
            protected = protected and f'resource: "{resource}"\n    effect: deny' in header
    check("OPENCODE_CORE_AND_GENERATOR_HARD_DENY", protected)
    check("CODEX_CORE_SOURCE_READ_ONLY_POLICY", all(codex_config["permissions"][profile]["filesystem"][":workspace_roots"].get(path) == "read" for profile in ("olympus-project", "olympus-readonly") for path in ("olympus", "scripts/render_harnesses.py")))

    spec = importlib.util.spec_from_file_location("olympus_renderer", RENDERER)
    if spec is None or spec.loader is None:
        raise AssertionError("renderer could not be imported")
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    managed = renderer.outputs_for(ROOT, "all")
    before = {path: (digest(path), path.stat().st_mtime_ns) for path in managed}
    first = run_renderer("render", "all")
    check("RENDER_ALL_DETERMINISTIC", first.returncode == 0 and "wrote 0 changed output(s)" in first.stdout)
    second = run_renderer("render", "all")
    check("SECOND_RENDER_ZERO_DIFF", second.returncode == 0 and "wrote 0 changed output(s)" in second.stdout)
    check("RENDER_OPENCODE_COMMAND", run_renderer("check", "opencode").returncode == 0)
    check("RENDER_CODEX_COMMAND", run_renderer("check", "codex").returncode == 0)
    readonly = run_renderer("check", "all")
    after = {path: (digest(path), path.stat().st_mtime_ns) for path in managed}
    check("CHECK_MODE_READ_ONLY", readonly.returncode == 0 and before == after and "read-only" in readonly.stdout)

    temp_base = Path.home() / "AppData" / "Local" / "Temp" / "opencode"
    if not temp_base.is_dir():
        temp_base = Path(tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix="olympus-harness-qual-", dir=temp_base) as temporary:
        fixture = Path(temporary)
        shutil.copytree(ROOT / "olympus", fixture / "olympus")
        (fixture / "scripts").mkdir()
        shutil.copy2(RENDERER, fixture / "scripts" / RENDERER.name)
        rendered = run_renderer("render", "all", fixture)
        check("FIXTURE_RENDER", rendered.returncode == 0)
        drifted = fixture / ".opencode" / "agents" / "kael.md"
        drifted.write_text(drifted.read_text(encoding="utf-8") + "\nmanual drift\n", encoding="utf-8")
        drift_check = run_renderer("check", "opencode", fixture)
        check("MANUAL_DRIFT_DETECTED", drift_check.returncode == 1 and "DRIFT drift: .opencode/agents/kael.md" in drift_check.stdout)
        restored = run_renderer("render", "opencode", fixture)
        check("DRIFT_RENDER_RESTORES_OUTPUT", restored.returncode == 0)
        missing = fixture / "CODEX.md"
        missing.unlink()
        missing_check = run_renderer("check", "codex", fixture)
        check("MISSING_GENERATED_OUTPUT_DETECTED", missing_check.returncode == 1 and "DRIFT missing: CODEX.md" in missing_check.stdout)

    print("OLYMPUS_HARNESS_CORE_QUALIFICATION: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, OSError, subprocess.SubprocessError, tomllib.TOMLDecodeError) as error:
        print(f"OLYMPUS_HARNESS_CORE_QUALIFICATION: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
