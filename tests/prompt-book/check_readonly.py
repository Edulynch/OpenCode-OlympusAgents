"""Opt-in native OpenCode smoke and before/after routing observations."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SUBJECT = "tests/prompt-book/README.md"
HEADING = "Prepare the fixture"
MISSING = "tests/prompt-book/missing-required-evidence.txt"
FIXTURE = "tests/prompt-book/.routing-fixture/status.txt"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def tool_error_message(error):
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        message = error.get("message")
        return message if isinstance(message, str) else ""
    return ""


def permission_error(error):
    if isinstance(error, str):
        return "permission.rejected" in error.lower()
    if isinstance(error, dict):
        fields = [error[key] for key in ("type", "code", "name", "kind", "message") if key in error]
        if not fields or any(not isinstance(value, str) for value in fields):
            raise ValueError("unexpected native tool error shape")
        return any("permission.rejected" in value.lower() for value in fields)
    return False


def permission_rejected_event(value):
    if not isinstance(value, dict):
        return False
    if value.get("type") == "permission.rejected":
        return True
    permission = value.get("permission")
    return (
        isinstance(permission, dict)
        and (permission.get("type") == "permission.rejected"
             or permission.get("status") in {"rejected", "permission.rejected"})
    )


def permission_rejected_tool_state(state):
    return isinstance(state, dict) and permission_error(state.get("error"))


def permission_rejected_trace(events):
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("unexpected native event shape")
        if permission_rejected_event(event):
            return True
        if event.get("type") == "tool_use":
            part = event.get("part", {})
            if not isinstance(part, dict):
                raise ValueError("unexpected native tool event shape")
            state = part.get("state", {})
            if not isinstance(state, dict):
                raise ValueError("unexpected native tool state")
            if (permission_rejected_event(part)
                    or permission_rejected_tool_state(state)):
                return True
        if event.get("type") == "error" and permission_error(event.get("error")):
            return True
    return False


def command(*args):
    executable = shutil.which(args[0])
    if not executable:
        raise FileNotFoundError(f"{args[0]} is not on PATH")
    result = subprocess.run(
        (executable, *args[1:]), cwd=ROOT, env={**os.environ, "PWD": str(ROOT)},
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
    return result.stdout


def permission_notice(*streams):
    return any(b"permission requested:" in stream.lower() for stream in streams)


def run_prompt(title, prompt, *, auto=False):
    flags = ["--auto"] if auto else []
    executable = shutil.which("opencode")
    if not executable:
        raise FileNotFoundError("opencode is not on PATH")
    result = subprocess.run(
        (executable, "run", "--standalone", *flags, "--agent", "kael", "--format", "json",
         "--title", f"Prompt Book - {title}", prompt),
        cwd=ROOT, env={**os.environ, "PWD": str(ROOT)}, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    events, unparsed = [], False
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            unparsed = True
    terminal = bool(events and events[-1]["type"] == "step_finish"
                    and events[-1]["part"]["reason"] == "stop")
    notice = permission_notice(result.stdout, result.stderr)
    rejected = permission_rejected_trace(events)
    require(terminal, "root terminal not confirmed" +
            ("; native permission request/rejection observed" if notice or rejected else ""))
    tools = [event["part"] for event in events if event["type"] == "tool_use"]
    replies = [event for event in events if event["type"] == "text"]
    require(replies, "missing root reply" +
            ("; native permission request/rejection observed" if notice or rejected else ""))
    return tools, replies, dict(
        permission_notice=notice,
        permission_rejected=rejected,
        returncode=result.returncode,
        error_event=any(event["type"] == "error" for event in events),
        unparsed_output=unparsed,
    )


def export(session_id, parent=None):
    require(re.fullmatch(r"ses_[A-Za-z0-9]+", session_id), "invalid native session ID")
    # Native read evidence is redacted by --sanitize. Consume only these newly owned
    # original exports in memory; never echo raw records.
    record = json.loads(command("opencode", "session", "export", "--standalone", session_id))
    info, last = record["info"], record["messages"][-1]
    require(info["id"] == session_id and (parent is None or info["parentID"] == parent),
            "native export identity mismatch")
    require(info["outcome"] == last["outcome"] and last["type"] == "idle",
            "original session terminal result not confirmed")
    return record


def child_record(tool, reply):
    child_id = tool["state"].get("metadata", {}).get("metadata", {}).get("sessionID")
    require(isinstance(child_id, str), "original child session ID is missing")
    record = export(child_id, parent=reply["sessionID"])
    require(record["info"]["time"]["idle"] <= reply["timestamp"], "root closed before its child")
    return child_id, record


def assistant_parts(record, role, part_type):
    return [part for message in record["messages"] if message.get("agent") == role
            for part in message.get("content", []) if part["type"] == part_type]


def same_path(path, target):
    try:
        candidate = Path(path)
        if ".." in candidate.parts:
            return False
        actual = candidate if candidate.is_absolute() else ROOT / candidate
        expected = ROOT / target
        return os.path.normcase(os.path.abspath(actual)) == os.path.normcase(os.path.abspath(expected))
    except (OSError, TypeError, ValueError):
        return False


def evidence():
    return (command("git", "status", "--porcelain=v1", "-z", "--untracked-files=all"),
            command("git", "diff", "--no-ext-diff", "--binary", "HEAD"), (ROOT / SUBJECT).read_bytes())


def changed_evidence_channels(before, after):
    names = ("git status", "git diff", "README bytes")
    return [name for name, old, new in zip(names, before, after) if old != new]


def require_unchanged(before, context):
    changes = changed_evidence_channels(before, evidence())
    require(not changes, f"{context}: repository evidence differs in channel(s): {', '.join(changes)}")


def exact_field(text, field, expected):
    return re.findall(rf"(?m)^{field}:[ \t]*(.*?)[ \t]*$", text) == [expected]


def arithmetic():
    return run_prompt("routing arithmetic", "Compute 19 + 23. Reply on one line as ANSWER: <number>.")


def nox_read(title, prompt, target, status):
    tools, replies, run = run_prompt(
        title, prompt + " Do not use shell, write files, or access other paths.", auto=True)
    require(run["returncode"] == 0 and not run["error_event"] and not run["unparsed_output"],
            "native Nox run did not complete cleanly")
    require([tool["tool"] for tool in tools] == ["subagent"]
            and tools[0]["state"]["input"]["agent"] == "nox", "expected one Nox delegation")
    child_id, child = child_record(tools[0], replies[-1])
    reads = assistant_parts(child, "nox", "tool")
    require(len(reads) == 1 and reads[0]["name"] == "read", "expected one Nox read")
    state = reads[0]["state"]
    require(same_path(state["input"]["path"], target), "Nox read a different file")
    require(state["status"] == status, f"unexpected native Nox read status: {state['status']}")
    report = "\n".join(part["text"] for part in assistant_parts(child, "nox", "text"))
    require(child["info"]["outcome"] == "succeeded", "original Nox result did not succeed")
    return child_id, state, report, replies[-1]["part"]["text"]


def readonly(initial):
    tools, replies, run = arithmetic()
    require(run["returncode"] == 0 and not run["error_event"] and not run["unparsed_output"]
            and not tools and exact_field(replies[-1]["part"]["text"], "ANSWER", "42"),
            "arithmetic routing or answer")
    print("PASS arithmetic: correct answer; zero tools and children", flush=True)
    child_id, _, report, reply = nox_read(
        "independent read", f"Have Nox independently read {SUBJECT} and report the section heading "
        "immediately after 'Automated read-only checks'. Wait for the original result.", SUBJECT, "completed",
    )
    require(HEADING in reply and HEADING in report, "missing correct independent read answer")
    require_unchanged(initial, "independent read")
    print(f"PASS independent read: Nox {child_id} finished before Kael", flush=True)
    require(not os.path.lexists(ROOT / MISSING), f"negative fixture must be absent: {MISSING}")
    child_id, state, report, reply = nox_read(
        "blocked verification", f"Have Nox use native read once on {MISSING} to verify that it contains READY. "
        "This verification is required; do not substitute any check. Wait for the original report. "
        "Give the final field VERIFICATION with value PASS or BLOCKED, then name the file and explain.",
        MISSING, "error",
    )
    require(re.findall(r"(?m)^VERIFICATION: (.*)$", reply)
            and re.search(r"(?m)^VERIFICATION: BLOCKED(?:[ \t]+[—–-][ \t]+.+)?$", reply)
            and Path(MISSING).name in reply, "missing final blocked verdict")
    require(state["error"]["message"].startswith("File not found:"), "read failed for another reason")
    require(re.search(r"(?m)^STATUS:[ \t]*(BLOCKED|FAILED)[ \t]*$", report), "Nox reported no blockage")
    require(not os.path.lexists(ROOT / MISSING), "negative case created the missing file")
    require_unchanged(initial, "blocked verification")
    print(f"PASS blocked verification: Nox {child_id} observed a missing file; Kael reported BLOCKED")


def comparison_evidence(tools, reply):
    root_id = reply["sessionID"]
    root = export(root_id)
    children = []
    for tool in tools:
        if tool["tool"] == "subagent":
            child_id, child = child_record(tool, reply)
            role = tool["state"]["input"]["agent"]
            notices = sum(msg["type"] == "synthetic" and child_id in msg.get("text", "")
                          for msg in root["messages"])
            children.append((role, child, notices))
    return root, children


def permission_rejected(record):
    messages = record.get("messages")
    if not isinstance(messages, list):
        raise ValueError("unexpected exported session shape")
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("unexpected exported message shape")
        if permission_rejected_event(message):
            return True
        content = message.get("content", [])
        if not isinstance(content, list):
            raise ValueError("unexpected exported message content")
        for part in content:
            if not isinstance(part, dict):
                raise ValueError("unexpected exported content part")
            if permission_rejected_event(part):
                return True
            if part.get("type") == "tool":
                state = part.get("state", {})
                if not isinstance(state, dict):
                    raise ValueError("unexpected exported tool state")
                if permission_rejected_tool_state(state):
                    return True
    return False


def permission_observed(run, root, children):
    export_rejected = any(
        permission_rejected(record) for record in [root, *(child for _, child, _ in children)]
    )
    return run["permission_notice"], run["permission_rejected"], export_rejected


def usage(case, tools, root, children):
    roles = [("kael", root, None), *children]
    summary = []
    totals = dict.fromkeys(("input", "cache_read", "cache_write", "output", "reasoning"), 0)
    for role, record, notices in roles:
        info = record["info"]
        tokens = info.get("tokens", {})
        row = {key: tokens.get(key) for key in ("input", "output", "reasoning")}
        row.update({f"cache_{key}": tokens.get("cache", {}).get(key) for key in ("read", "write")})
        for key, value in row.items():
            totals[key] = totals[key] + value if isinstance(value, int) and totals[key] is not None else None
        models = sorted({f"{m['providerID']}/{m['id']}#{m.get('variant', 'default')}"
                         for msg in record["messages"] if (m := msg.get("model"))})
        cost = info.get("cost")
        summary.append(dict(role=role, models=models, tokens=row, native_cost=cost if cost and cost > 0 else None,
                            terminal_notices=notices, session=info["id"]))
    costs = [item["native_cost"] for item in summary]
    print("USAGE " + json.dumps(dict(case=case, tools=[tool["tool"] for tool in tools], sessions=summary,
                                    tokens=totals, native_cost=sum(costs) if all(costs) else None)), flush=True)


def reparse(path):
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def safe_fixture_parent(directory):
    root = ROOT.resolve(strict=True)
    parent = directory.parent
    try:
        parent.relative_to(root)
        return (ROOT == root and not reparse(root) and parent.resolve(strict=True) == parent
                and parent.is_dir() and not reparse(parent))
    except (OSError, ValueError):
        return False


def safe_fixture(directory, target, owner):
    try:
        if not safe_fixture_parent(directory) or reparse(directory):
            return False
        current = directory.lstat()
        if not stat.S_ISDIR(current.st_mode) or not os.path.samestat(current, owner):
            return False
        if list(directory.iterdir()) != [target]:
            return False
        file_stat = target.lstat()
        return (not reparse(target) and stat.S_ISREG(file_stat.st_mode)
                and file_stat.st_nlink == 1)
    except OSError:
        return False


def native_fixture_edit(part):
    if (part["name"] not in {"edit", "write", "patch", "apply_patch"}
            or part["state"]["status"] != "completed"):
        return False
    data = part["state"]["input"]
    files = [data[key] for key in ("path", "filePath", "file_path") if key in data]
    if not files:
        files = re.findall(r"(?m)^\*\*\* Update File: (.+?)\r?$", "\n".join(
            value for value in data.values() if isinstance(value, str)
        ))
    return len(files) == 1 and same_path(files[0], FIXTURE)


def same_root(path):
    try:
        return os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(ROOT))
    except (OSError, TypeError, ValueError):
        return False


def state_text(state):
    content = state.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        part["text"] for part in content
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
    )


def kovan_fixture_byte_check(part):
    state = part.get("state", {})
    if not isinstance(state, dict):
        return False
    data = state.get("input", {})
    if not isinstance(data, dict):
        return False
    command_text = data.get("command", "")
    if (part.get("name") != "shell" or state.get("status") != "completed"
            or not isinstance(command_text, str)
            or not same_root(data.get("workdir", ""))):
        return False
    read_calls = list(re.finditer(r"\bReadAllBytes\s*\(\s*(?P<argument>[^)]*)\)", command_text, re.IGNORECASE))
    if (len(read_calls) != 1 or re.search(
            r"(?i)\b(?:WriteAllBytes|WriteAllText|Set-Content|Add-Content|Out-File|"
            r"Remove-Item|Move-Item|Copy-Item|New-Item|Clear-Content|Set-Item|"
            r"ReadAllText|ReadAllLines|OpenRead|Get-Content|Get-Item|Get-ChildItem|"
            r"Start-Process|Invoke-Expression|Invoke-WebRequest|Invoke-RestMethod)\b|"
            r"(?<!<)>(?!>)",
            command_text,
    )):
        return False
    argument = read_calls[0].group("argument").strip()
    literal = re.fullmatch(r"""(?P<quote>['"])(?P<path>.*?)(?P=quote)""", argument)
    if literal:
        read_path = literal.group("path")
    elif re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", argument):
        assignment = re.search(
            rf"{re.escape(argument)}\s*=\s*(['\"])(?P<path>[^'\"]+)\1",
            command_text[:read_calls[0].start()],
            re.IGNORECASE,
        )
        if not assignment:
            return False
        read_path = assignment.group("path")
    else:
        return False
    if read_path.replace("\\", "/") != FIXTURE:
        return False
    metadata = state.get("metadata", {})
    output = state_text(state)
    expected_hex = "HEX=52-45-41-44-59-20-7C-20-32-20-69-74-65-6D-73-0A"
    return (isinstance(metadata, dict) and metadata.get("exit") == 0
            and expected_hex in output and "MATCH=True" in output)


def kovan_scope_and_check(record):
    calls = assistant_parts(record, "kovan", "tool")
    if (len(calls) != 3 or [part["name"] for part in calls] != ["read", "patch", "shell"]
            or not native_fixture_edit(calls[1])):
        return False
    initial_read = calls[0]
    if (initial_read["state"]["status"] != "completed"
            or not same_path(initial_read["state"]["input"].get("path", ""), FIXTURE)):
        return False
    report = "\n".join(part["text"] for part in assistant_parts(record, "kovan", "text")).lower()
    reported_check = ("verified" in report
                      and not re.search(r"\b(?:not|unable to|could not|couldn't)\s+(?:independently\s+)?verify\b", report))
    return reported_check and kovan_fixture_byte_check(calls[2])


def root_probe(tool):
    state = tool.get("state", {})
    return (tool.get("tool") == "shell" and state.get("status") == "completed"
            and state.get("input", {}).get("command") == "git rev-parse --show-toplevel")


def scoped_preflight(tools):
    paths = (FIXTURE, "README.md", "olympus/core/models.toml", "olympus/core/identities.toml",
             "olympus/policies/routing.md", ".opencode/orchestrator-install.json")
    for index, tool in enumerate(tools):
        if root_probe(tool):
            if index != 0:
                return False
            continue
        if tool.get("tool") != "read":
            return False
        state = tool.get("state", {})
        target = next((path for path in paths if same_path(state.get("input", {}).get("path", ""), path)), None)
        if target is None:
            return False
        if state.get("status") == "completed":
            continue
        error = state.get("error")
        message = tool_error_message(error).replace("\\", "/").lower()
        missing = message[len("file not found:"):].strip().strip("\"'")
        if (target != ".opencode/orchestrator-install.json" or state.get("status") != "error"
                or not message.startswith("file not found:")
                or not (missing == ".opencode/orchestrator-install.json"
                        or missing.endswith("/.opencode/orchestrator-install.json"))
                or permission_error(error)):
            return False
    return True


def compare(mode, initial):
    candidate = mode == "candidate"
    tools, replies, run = arithmetic()
    root, children = comparison_evidence(tools, replies[-1])
    usage("arithmetic", tools, root, children)
    arithmetic_ok = (not tools and run["returncode"] == 0 and not run["error_event"]
                     and not run["unparsed_output"] and root["info"]["outcome"] == "succeeded"
                     and exact_field(replies[-1]["part"]["text"], "ANSWER", "42"))
    require_unchanged(initial, "arithmetic")

    tools, replies, run = run_prompt(
        "routing investigation", f"Using {SUBJECT}, find the exact level-two heading immediately after the "
        "Automated read-only checks section. Reply on one line as NEXT_HEADING: <heading>.",
    )
    root, children = comparison_evidence(tools, replies[-1])
    usage("investigation", tools, root, children)
    answer = exact_field(replies[-1]["part"]["text"], "NEXT_HEADING", HEADING)
    veyra_calls = assistant_parts(children[0][1], "veyra", "tool") if len(children) == 1 else []
    veyra_read_ok = (len(veyra_calls) == 1 and veyra_calls[0]["name"] == "read"
                     and veyra_calls[0]["state"]["status"] == "completed"
                     and same_path(veyra_calls[0]["state"]["input"].get("path", ""), SUBJECT))
    investigation_root_ok = (
        len(tools) in {1, 2} and tools[-1]["tool"] == "subagent"
        and (len(tools) == 1 or (len(tools[:-1]) == 1 and root_probe(tools[0])))
    )
    investigation_notice, investigation_trace_rejected, investigation_export_rejected = permission_observed(
        run, root, children)
    investigation_ok = (
        answer and investigation_root_ok and len(children) == 1 and children[0][0] == "veyra"
        and children[0][2] == 1 and tools[-1]["state"]["status"] == "completed"
        and root["info"]["outcome"] == "succeeded"
        and children[0][1]["info"]["outcome"] == "succeeded" and veyra_read_ok
        and HEADING in "\n".join(part["text"] for part in assistant_parts(children[0][1], "veyra", "text"))
        and run["returncode"] == 0 and not run["error_event"] and not run["unparsed_output"]
        and not investigation_notice and not investigation_trace_rejected and not investigation_export_rejected
    )
    require_unchanged(initial, "investigation")
    print(f"{mode}: arithmetic={arithmetic_ok}; investigation_answer={answer}; "
          f"investigation_accepted={investigation_ok}; root_probe_only={investigation_root_ok}; "
          f"permission_notice={'observed' if investigation_notice else 'not-observed'}; "
          f"trace_permission_rejected={'observed' if investigation_trace_rejected else 'not-observed'}; "
          f"export_permission_rejected={'observed' if investigation_export_rejected else 'not-observed'}", flush=True)

    target = ROOT / FIXTURE
    directory = target.parent
    require(safe_fixture_parent(directory), "fixture parent escapes the checkout or is a reparse point")
    require(not os.path.lexists(directory), f"fixture already exists and was not inspected or changed: {FIXTURE}")
    directory.mkdir()  # Exclusive: never overwrite an existing fixture.
    owner = directory.lstat()
    terminal = False
    try:
        require(stat.S_ISDIR(owner.st_mode) and not reparse(directory)
                and directory.resolve(strict=True) == directory,
                "fixture directory is not a normal child directory")
        with target.open("xb") as fixture:
            fixture.write(b"PENDING\n")
        require(safe_fixture(directory, target, owner), "new fixture failed safety checks")
        tools, replies, run = run_prompt(
            "routing write", f"The trusted repository root for this task is {ROOT}. The only task-owned "
            f"file is {FIXTURE}, created exclusively for this task and currently containing PENDING. Replace "
            "its contents with one line READY | 2 items followed by a newline. Do not change any other paths, "
            "commit, or ask for additional permissions. Report whether you verified the new value.",
        )
        root, children = comparison_evidence(tools, replies[-1])
        terminal = True
        usage("write", tools, root, children)
        value_ok = safe_fixture(directory, target, owner) and target.read_bytes() == b"READY | 2 items\n"
        write_notice, write_trace_rejected, write_export_rejected = permission_observed(run, root, children)
        write_ok = (
            value_ok and bool(tools) and tools[-1]["tool"] == "subagent"
            and tools[-1]["state"]["status"] == "completed"
            and len(children) == 1 and children[0][0] == "kovan" and children[0][2] == 1
            and root["info"]["outcome"] == "succeeded" and children[0][1]["info"]["outcome"] == "succeeded"
            and scoped_preflight(tools[:-1]) and kovan_scope_and_check(children[0][1])
            and run["returncode"] == 0 and not run["error_event"] and not run["unparsed_output"]
            and not write_notice and not write_trace_rejected and not write_export_rejected
        )
    finally:
        # Unknown execution is not permission to remove its input or launch a replacement.
        if terminal:
            if safe_fixture(directory, target, owner):
                target.unlink()
                directory.rmdir()
            else:
                print(f"Fixture retained after safety-check failure: {FIXTURE}", file=sys.stderr)
        elif os.path.lexists(directory):
            print(f"Fixture retained pending reconciliation: {FIXTURE}", file=sys.stderr)
    fixture_absent = not os.path.lexists(directory)
    changes = changed_evidence_channels(initial, evidence())
    require(fixture_absent, f"fixture absence not verified: {FIXTURE}; evidence channel(s): "
            f"{', '.join(changes) if changes else 'unchanged'}")
    require(not changes, f"after write comparison: repository evidence differs in channel(s): {', '.join(changes)}")
    print(f"{mode}: exact_lf_bytes={value_ok}; kovan_only={write_ok}; "
          f"permission_notice={'observed' if write_notice else 'not-observed'}; "
          f"trace_permission_rejected={'observed' if write_trace_rejected else 'not-observed'}; "
          f"export_permission_rejected={'observed' if write_export_rejected else 'not-observed'}; "
          f"fixture_absent={fixture_absent}")
    if candidate:
        require(arithmetic_ok and investigation_ok and write_ok, "one or more routing cases failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare", choices=("baseline", "candidate"),
                        help="also run a scoped disposable edit; comparison never uses --auto")
    args = parser.parse_args()
    try:
        print(command("opencode", "--version").decode().strip(), flush=True)
        initial = evidence()
        if args.compare:
            compare(args.compare, initial)
        else:
            readonly(initial)
    except (AttributeError, KeyError, IndexError, OSError, TypeError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"NOT PASS: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
