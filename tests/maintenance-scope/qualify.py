"""Deterministic source and generated-contract qualifications; no live agent claims."""
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import render_harnesses as renderer


def check(name, ok):
    if not ok:
        raise AssertionError(name + " FAIL")
    print(name.encode("ascii", errors="backslashreplace").decode() + " PASS")


def main():
    text = lambda p: (ROOT / p).read_text(encoding="utf-8")
    policy = text("olympus/policies/maintenance-plane.md").strip()
    prompt = text("olympus/harnesses/opencode/agent-prompts/aegis.md")
    role = text("olympus/roles/aegis.md")
    command = text(".opencode/commands/maintain.md")
    agent = text(".opencode/agents/aegis.md")
    outputs = renderer.outputs_for(ROOT, "opencode")
    check("FRESH_GENERATED_COMMAND_VALID_ACCEPT", all(s in command for s in (
        "The user invoked /maintain and authorizes the following task:",
        "Fresh invocation starts with `MAINTENANCE_AUTH: VALID` and `AEGIS_SCOPE: ACCEPTED`")))
    check("ONE_CANONICAL_POLICY", policy in command and policy in agent)
    check("NO_OWNERSHIP_ADMISSION", "Acceptance does not depend on an Olympus repository or Olympus-owned target" in policy)
    check("ARBITRARY_REPOSITORY_ACCEPTED", "in any repository, including ordinary user projects" in policy)
    for boundary in ("Kael → Aegis DENIED", "child → Aegis DENIED", "Aegis cannot self-activate"):
        check(boundary, boundary in policy)
    check("HIDDEN_NO_DELEGATION", "hidden: true" in agent and 'action: subagent\n    resource: "*"\n    effect: deny' in agent)
    check("TASK_SCOPE_CANNOT_BROADEN", "Authority covers only the task delivered by the command template" in policy and "Do not broaden task scope" in policy)
    check("DESTRUCTIVE_NOT_IMPLICITLY_AUTHORIZED", "Destructive or high-impact operations still require explicit task authorization; an operation not included in the task is not implicitly authorized" in policy)
    for path in ("olympus/harnesses/opencode/maintain.md", ".opencode/commands/maintain.md"):
        check("FRONTMATTER_BYTE_ZERO_" + path, (ROOT / path).read_bytes().startswith(b"---\n"))
        header = text(path).split("---", 2)[1]
        check("AGENT_SUBAGENT_" + path, "agent: aegis" in header and "subagent: true" in header)
    sequence = "COMMAND_ENTRY → MAINTENANCE_AUTH_VALID → AEGIS_SCOPE_ACCEPTED → TASK_EXECUTION"
    check("NO_INTERMEDIATE_CLASSIFICATION", sequence in policy and "There is no reasoning or authorization classification phase" in policy)
    check("ACCEPT_BEFORE_EXECUTION", command.index(sequence) < command.index("Perform exactly the maintenance task"))
    check("SAME_RUN_RESUME_ACCEPTED", "resume of the same Aegis execution preserves its accepted task-scoped state and original task boundaries" in policy)
    check("NEW_EXECUTION_REQUIRES_COMMAND", "genuinely new Aegis execution: it must originate again through `/maintain`" in policy)
    check("UNCERTAIN_RESUME_FAILS_CLOSED_QUICKLY", "fail closed immediately with `MAINTENANCE_AUTH: UNPROVEN` and `AEGIS_SCOPE: REJECTED`" in policy and "stop without tools, long reasoning, authorization reconstruction or retry" in policy)
    check("UNAUTHENTICATED_ENTRY_FAILS_CLOSED", "A new entry without `/maintain` likewise fails closed immediately" in policy)
    check("NO_PROVENANCE_RECONSTRUCTION", "Do not require independent proof" in policy and "checkpoint provenance reconstruction" in policy)
    check("NO_BLIND_RETRY", "No blind retry" in policy)
    for content in (policy, command, agent, prompt, role):
        check("NO_OBSOLETE_GATE", not re.search(r"Cheap scope gate|Olympus-only scope check|Accept only when|ordinary user-project target is OUT_OF_SCOPE|cheap target-ownership", content))
    check("RENDERER_DETERMINISTIC", outputs == renderer.outputs_for(ROOT, "opencode"))
    check("GENERATED_OUTPUT_MATCHES_RENDERER", all(text(str(p.relative_to(ROOT))) == expected for p, expected in outputs.items()))
    before = {p: p.read_bytes() for p in outputs}
    check("RENDERER_CHECK", renderer.run(ROOT, "check", "opencode") == 0)
    check("CHECK_READ_ONLY", before == {p: p.read_bytes() for p in outputs})
    print("MAINTENANCE SCOPE/AUTH QUALIFICATION: PASS (static; runtime smoke required)")


if __name__ == "__main__":
    main()
