"""Small static qualifications for the three Issue #8 Aegis invariants."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import render_harnesses as renderer


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name + " FAIL")
    print(name + " PASS")


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def has_subagent_deny(source: str) -> bool:
    return re.search(
        r'(?ms)^\s*- action: subagent\s*\r?\n\s+resource: "?\*"?\s*\r?\n\s+effect: deny\s*$',
        source,
    ) is not None


def main() -> None:
    policy = text("olympus/policies/maintenance-plane.md")
    command_source = text("olympus/harnesses/opencode/maintain.md")
    command = text(".opencode/commands/maintain.md")
    aegis_prompt = text("olympus/harnesses/opencode/agent-prompts/aegis.md")
    aegis_role = text("olympus/roles/aegis.md")
    aegis_metadata = text("olympus/harnesses/opencode/agent-metadata/aegis.md")
    kael_metadata = text("olympus/harnesses/opencode/agent-metadata/kael.md")
    kael_prompt = text("olympus/harnesses/opencode/agent-prompts/kael.md")
    command_header = re.match(r"\A---\r?\n(.*?)\r?\n---", command, re.DOTALL)
    source_header = re.match(r"\A---\r?\n(.*?)\r?\n---", command_source, re.DOTALL)
    if command_header is None or source_header is None:
        raise AssertionError("/maintain frontmatter missing")

    active_text = "\n".join((policy, command_source, command, aegis_prompt, aegis_role, kael_prompt))
    obsolete_states = re.compile(
        r"MAINTENANCE_AUTH|AEGIS_SCOPE|UNPROVEN|maintenance_authorization|accepted_scope"
    )
    check(
        "T1_MAINTENANCE_EXECUTION",
        all(
            phrase in command_source
            for phrase in (
                "The user invoked /maintain and requests the following maintenance task:",
                "$ARGUMENTS",
            )
        )
        and "agent: aegis" in source_header.group(1)
        and "subagent: true" in source_header.group(1)
        and "Do not request additional Olympus authorization" in policy
        and "does not start a separate Olympus-side approval flow" in policy
        and not obsolete_states.search(active_text),
    )

    check(
        "T2_TASK_CONTINUITY",
        all(
            phrase in policy
            for phrase in (
                "An OpenCode continuation carries the same task through compaction",
                "Continue from the task context retained by that session",
                "without a special status preamble or another command-origin check",
                "Keep the original task boundaries",
                "stop dependent operations, especially writes",
            )
        )
        and "Context loss is a missing-information problem" in policy,
    )

    child_metadata = [
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "olympus/harnesses/opencode/agent-metadata").glob("*.md"))
        if path.stem not in {"kael", "aegis"}
    ]
    check(
        "T3_NATIVE_ISOLATION",
        "agent: aegis" in command_header.group(1)
        and "subagent: true" in command_header.group(1)
        and "hidden: true" in aegis_metadata
        and "mode: subagent" in aegis_metadata
        and has_subagent_deny(aegis_metadata)
        and has_subagent_deny(kael_metadata)
        and not re.search(r"(?ms)^\s*- action: subagent\s*\r?\n\s+resource: aegis\s*\r?\n\s+effect: allow\s*$", kael_metadata)
        and all(has_subagent_deny(metadata) for metadata in child_metadata)
        and "Kael → Aegis DENIED" in policy
        and "child → Aegis DENIED" in policy
        and "Kael → Aegis DENIED" in kael_prompt,
    )

    outputs = renderer.outputs_for(ROOT, "opencode")
    check(
        "GENERATED_OUTPUTS_MATCH_RENDERER",
        all(path.read_text(encoding="utf-8") == expected for path, expected in outputs.items()),
    )
    before = {path: path.read_bytes() for path in outputs}
    check(
        "RENDERER_CHECK_READ_ONLY",
        renderer.run(ROOT, "check", "opencode") == 0
        and before == {path: path.read_bytes() for path in outputs},
    )
    print("ISSUE #8 STATIC QUALIFICATION: PASS; NATIVE_SMOKE_PENDING (static checks are not runtime proof)")


if __name__ == "__main__":
    main()
