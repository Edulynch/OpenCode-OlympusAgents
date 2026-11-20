"""Opt-in native OpenCode smoke: three read-only prompts, no permission assertions."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SUBJECT = "tests/prompt-book/README.md"
HEADING = "Prepare the fixture"
MISSING = "tests/prompt-book/missing-required-evidence.txt"


def command(*args):
    # OpenCode 2.3.2 prefers PWD over cwd, including on Windows.
    executable = shutil.which(args[0])
    if not executable:
        raise FileNotFoundError(f"{args[0]} is not on PATH")
    return subprocess.check_output(
        (executable, *args[1:]), cwd=ROOT, env={**os.environ, "PWD": str(ROOT)}, stderr=subprocess.PIPE,
    )


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def run_prompt(title, prompt, expected_tool):
    output = command(
        "opencode", "run", "--standalone", "--auto", "--agent", "kael", "--format", "json",
        "--title", f"Prompt Book - {title}",
        prompt + " Do not use shell, write files, or access other paths.",
    )
    events = [json.loads(line) for line in output.splitlines() if line.strip()]
    require(events and events[-1]["type"] == "step_finish"
            and events[-1]["part"]["reason"] == "stop"
            and not any(event["type"] == "error" for event in events), "missing successful root trace")
    tools = [event["part"] for event in events if event["type"] == "tool_use"]
    require([tool["tool"] for tool in tools] == [expected_tool], "unexpected root tool or delegation")
    require(tools[0]["state"]["status"] == "completed", "root tool did not complete")
    replies = [event for event in events if event["type"] == "text"]
    require(replies, "missing root reply")
    return tools[0]["state"], replies


def nox_read(delegated, reply, target, expected_status):
    require(delegated["input"]["agent"] == "nox", "unexpected child role")
    child_id = delegated["metadata"]["metadata"]["sessionID"]
    require(re.fullmatch(r"ses_[A-Za-z0-9]+", child_id), "invalid native child ID")
    child = json.loads(command("opencode", "session", "export", "--standalone", child_id))
    info, messages = child["info"], child["messages"]
    require(info["id"] == child_id and info["parentID"] == reply["sessionID"],
            "export does not match the original child")
    require(info["outcome"] == "succeeded" and messages[-1]["type"] == "idle"
            and messages[-1]["outcome"] == "succeeded", "child did not deliver a terminal report")
    require(info["time"]["idle"] <= reply["timestamp"], "root closed before child finished")
    parts = [part for msg in messages if msg.get("agent") == "nox" for part in msg["content"]]
    reads = [part for part in parts if part["type"] == "tool"]
    require(len(reads) == 1 and reads[0]["name"] == "read", "Nox did not perform exactly one read")
    state = reads[0]["state"]
    require((ROOT / state["input"]["path"]).resolve() == ROOT / target, "Nox read a different file")
    require(state["status"] == expected_status, f"unexpected native Nox read status: {state['status']}")
    text = "\n".join(part["text"] for part in parts if part["type"] == "text")
    return child_id, state, text


def evidence():
    return (
        command("git", "status", "--porcelain=v1", "-z", "--untracked-files=all"),
        command("git", "diff", "--no-ext-diff", "--binary", "HEAD"),
        (ROOT / SUBJECT).read_bytes(),
    )


def blocked_verification(initial):
    require(not os.path.lexists(ROOT / MISSING), f"negative fixture must be absent: {MISSING}")
    delegated, replies = run_prompt(
        "blocked verification", f"Have Nox use the native read tool once on {MISSING} to verify "
        "that it contains READY. This verification is required; do not substitute any check. "
        "Wait for Nox's original report before giving your verdict. In the final answer, include "
        "the field VERIFICATION with value PASS or BLOCKED, then name the file and explain the result.",
        "subagent",
    )
    reply = replies[-1]
    root_id = reply["sessionID"]
    verdicts = [re.findall(r"(?m)^VERIFICATION: (.*)$", event["part"]["text"]) for event in replies]
    require(not any(verdicts[:-1]) and len(verdicts[-1]) == 1
            and re.fullmatch(r"BLOCKED(?:[ \t]+[—–-][ \t]+.+)?", verdicts[-1][0].strip()),
            f"Kael {root_id} did not give exactly one final blocked verdict")
    require(Path(MISSING).name in reply["part"]["text"], f"Kael {root_id} did not identify the missing input")
    child_id, state, report = nox_read(delegated, reply, MISSING, "error")
    require(state["error"]["message"].startswith("File not found:"), "native read failed for another reason")
    require(re.search(r"(?m)^STATUS:[ \t]*(BLOCKED|FAILED)[ \t]*$", report),
            "Nox did not report that the verification could not pass")
    require(not os.path.lexists(ROOT / MISSING) and evidence() == initial,
            "negative case changed the worktree or created the missing file")
    print(f"PASS blocked verification: Nox {child_id} observed a missing file; Kael {root_id} reported BLOCKED")


def main():
    try:
        initial = evidence()
        print(command("opencode", "--version").decode().strip(), flush=True)
        direct, replies = run_prompt(
            "direct read", f"Read {SUBJECT} and report the section heading immediately after "
            "'Automated read-only checks'.", "read",
        )
        reply = replies[-1]
        require(HEADING in reply["part"]["text"], "missing correct final answer")
        require((ROOT / direct["input"]["path"]).resolve() == ROOT / SUBJECT, "Kael read a different file")
        require(HEADING in direct["output"], "native read did not show the heading")
        require(evidence() == initial, "worktree changed during direct read")
        print(f"PASS direct read: {reply['sessionID']}; one read and no delegation", flush=True)

        delegated, replies = run_prompt(
            "independent read", f"Have Nox independently read {SUBJECT} and report the section "
            "heading immediately after 'Automated read-only checks'. Wait for the original result.",
            "subagent",
        )
        reply = replies[-1]
        require(HEADING in reply["part"]["text"], "missing correct final answer")
        child_id, _, report = nox_read(delegated, reply, SUBJECT, "completed")
        require(HEADING in report, "original Nox result did not contain the heading")
        require(evidence() == initial, "worktree changed during independent read")
        print(f"PASS independent read: Nox {child_id} finished before Kael {reply['sessionID']}", flush=True)

        blocked_verification(initial)
    except (KeyError, IndexError, OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"NOT PASS: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
