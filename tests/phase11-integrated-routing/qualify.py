#!/usr/bin/env python3
"""Small, evidence-aware semantic validator for Phase 11 qualification artifacts.

This validates authored fixture traces and bounded policy markers.  It is not a
router, runtime observer, installer check, or proof of model behavior.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EVIDENCE_CLASSES = {
    "POLICY_BASELINE",
    "SYNTHETIC_TRACE",
    "GUIDED_CURRENT_SESSION",
    "FRESH_ROOT_NATIVE",
}
ROLE_ACTIONS = {
    "kael": {"ROUTE", "CONSUME_RESULT", "ASK_USER", "FINALIZE"},
    "veyra": {"READ_EVIDENCE"},
    "orin": {"ARCHITECT"},
    "kovan": {"IMPLEMENT", "TEST"},
    "nox": {"TEST", "MEASURE"},
    "vera": {"REVIEW"},
    "atlas": {"PLAN"},
    "argus": {"DIAGNOSE_FUNCTIONAL"},
    "talos": {"DIAGNOSE_SECURITY"},
    "thales": {"DIAGNOSE_UNCERTAINTY"},
    "helios": {"OPTIMIZE_ADVISE"},
    "aegis": {"MAINTAIN"},
}
GATED_REASONERS = ("argus", "talos", "thales", "atlas", "helios")
EIGHT_SPECIALISTS = ("veyra", "orin", "atlas", "vera", "argus", "talos", "thales", "helios")
ALL_INVOCABLE_ROLES = tuple(ROLE_ACTIONS)
NORMAL_BUDGET = {"argus": 2, "talos": 2, "thales": 2, "atlas": 2, "helios": 2}
HARD_BUDGET = {"argus": 3, "talos": 3, "thales": 2, "atlas": 2, "helios": 2}
REQUIRED_TRACE_FIELDS = (
    "CASE_ID",
    "REQUEST_CLASS",
    "EXPECTED_ROUTE",
    "ACTUAL_ROUTE",
    "CHILD_SESSIONS",
    "CONSULTATION_COUNTS",
    "MAX_SIMULTANEOUS_CHILDREN",
    "NEGATIVE_CONTROLS",
    "ROLE_PURITY",
    "DEPENDENCY_ORDER",
    "RESULT_FIDELITY",
    "COMPLETION_GATE",
    "USER_QUESTION_COUNT",
    "FINAL_OUTCOME",
    "ROUTING_RESULT",
    "NOTES",
    "EVENTS",
    "EVIDENCE_CLASS",
    "EVIDENCE_PROVENANCE",
    "OPERATIONAL_PROXIES",
    "GATE_FACTS",
    "ROUTE_MODE",
)
REQUIRED_GATE_FACTS = (
    "EXPLICIT_OPTIMIZATION_INTENT",
    "EXPLICIT_PLANNING_INTENT",
    "COMPLEX_FEATURE",
    "OBVIOUS_FUNCTIONAL_CAUSE",
    "NONTRIVIAL_FUNCTIONAL_CAUSE",
    "SECURITY_BOUNDARY",
    "OPERATIONAL_TOOLING_FAILURE",
    "HIGH_UNCERTAINTY_AFTER_BOUNDED_DIAGNOSIS",
    "THIRD_PARTY_BUG",
    "FAST_PROFILE_REQUESTED",
    "NORMAL_PROFILE_REQUESTED",
    "MAINTENANCE_ENTRY_EXPLICIT",
)
NATIVE_SESSION_ID = re.compile(r"^ses_[A-Za-z0-9]+$")
CASE_B2_ROOT_SESSION_ID = "ses_efd70d361ffecywLukxPk5m1Sv"
CASE_B2_CHILD_SESSION_IDS = {
    "Veyra": "ses_efd706277ffeSqUTO9GumJKt5B",
    "Kovan": "ses_efd6d87f4ffe2j4zsTzy1mAv0D",
    "Nox": "ses_efd69a153ffe0ntGQoaZVOXyZi",
    "Vera": "ses_efd69a151ffeftr0qNcEM5VEle",
}
CASE_B2_CLASSIFICATIONS = {
    "CASE_B2_RUNTIME_BEHAVIOR": "PASS",
    "CASE_B2_NATIVE_ROUTING_EVIDENCE": "VALID_OBSERVATION",
    "CASE_B2_FRESH_ROOT_ISOLATION": "FAIL",
    "CASE_B2_FRESH_ROOT_ACCEPTANCE": "PARTIAL",
}
CASE_B2_ACTUAL_ROUTE = "Kael -> Veyra -> Kovan -> Nox / Vera"
CASE_B3_ROOT_SESSION_ID = "ses_efce702a8ffeKcoRaBYMFH9lxa"
CASE_B3_ROOT_DIRECTORY = "C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-b3"
CASE_B3_INITIAL_HEAD = "ded1f69cbeadf5d21cb9b6b31d5df10123b57990"
CASE_B3_TERMINAL_MESSAGE_ID = "msg_1048ed1e5001AE9cC6bTYFgV3z"
CASE_B3_TEST_COMMAND = 'uv run --python 3.11 python -B -m unittest discover -s tests/phase11-integrated-routing/fixtures/feature -p "test_*.py" -v'
CASE_B3_TERMINAL_FACTS = {
    "WORKTREE_ISOLATION": "PASS",
    "PYTHON_RUNTIME": "Python 3.11.17 installed through uv",
    "TEST_COMMAND": CASE_B3_TEST_COMMAND,
    "TEST_RESULT": "PASS",
    "TEST_COUNT": 13,
    "CONTRACT_COVERAGE": "PASS",
    "SOURCE_INTEGRITY_AFTER_TEST": "PASS",
    "NOX": "PASS",
    "VERA": "ACCEPT",
    "UNRESOLVED_WORK": "NONE",
    "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED": "YES",
    "CASE_B_FRESH_ROOT_3": "PASS",
    "NOTHING_RUNNING": True,
}
CASE_B3_CHILD_SESSIONS = [
    ("B3-NOX", "nox", "ses_efce6a350ffeLULhF1Hf7l39qJ"),
    ("B3-VEYRA", "veyra", "ses_efce5cd8bffexU0SIHi67Y39zP"),
    ("B3-KOVAN", "kovan", "ses_efce3ffadffekeRXxYxKkSWsxs"),
    ("B3-VERA", "vera", "ses_efcde45cdffe6X5eJbStlshoYu"),
]
CASE_B3_EXPECTED_ROUTE = ["kael", "veyra", "kovan", "nox", "vera"]
CASE_B3_ACTUAL_ROUTE = ["kael", "nox", "veyra", "kovan", "vera"]
CASE_B3_CALLS = [
    ("B3-NOX", "nox", "call_qwMZACNrVqLA8tmmFCM1eB3W", "msg_10318ff58001ub8abxr5egfLqd", "SUCCESS"),
    ("B3-VEYRA", "veyra", "call_d4KKM4JToyp1bXQ1A3JppG0S", "msg_10319ecd7001TayRkYYC0CnjsM", "SUCCESS"),
    ("B3-KOVAN", "kovan", "call_Rpz7XK5m7owERqLA8JN6740C", "msg_1031b866a001mmZqvYl8apLVzl", "PARTIAL"),
    ("B3-NOX", "nox", "call_C62D1Hr0MpWpEiuKaNaCLssa", "msg_1031f1121001ieqq1bWvW7evXn", "BLOCKED"),
    ("B3-VERA", "vera", "call_xaodFghlKSlXFOPDEgeFdK1J", "msg_103215e85001aLOM4b6TTSc3MA", "SUCCESS"),
    ("B3-VERA", "vera", "call_E8YeCiitk1nrTb1c88EJqpTE", "msg_10322808c0015hGifrTywcYcvB", "SUCCESS"),
    ("B3-NOX", "nox", "call_P7Muj3TbvUxytRrajoipAwpd", "msg_10489ca38001WfLqB678rW4Xjl", "SUCCESS"),
]
CASE_B3_DEPENDENCY_EDGES = {
    ("B3-CALL-1", "B3-CALL-2"),
    ("B3-CALL-2", "B3-CALL-3"),
    ("B3-CALL-3", "B3-CALL-4"),
    ("B3-CALL-3", "B3-CALL-5"),
    ("B3-CALL-5", "B3-CALL-6"),
    ("B3-CALL-4", "B3-CALL-7"),
    ("B3-CALL-3", "B3-CALL-7"),
}
CASE_B3_PENDING_LABELS = [
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_C_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_D_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_E_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_F_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT",
]
CASE_C_PENDING_LABELS = [
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_D_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_E_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_F_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT",
]
CASE_C_ROOT_SESSION_ID = "ses_efa068637ffeq7qrjCSJFLykc5"
CASE_C_NOX_SESSION_ID = "ses_efa05f4dfffe9s0gk5VEbkVRA9"
CASE_C_ROOT_DIRECTORY = "C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-c"
CASE_C_ROOT_TERMINAL_MESSAGE_ID = "msg_105fd3baa001OouobBeNyh4Nup"
CASE_C_ROOT_HEAD = "8e77742ade517d4d903e0c8aa09cd037a44aa3da"
CASE_C_TEST_COMMAND = 'uv run --python 3.11 python -c "import sys; sys.path.insert(0, r\'tests/phase11-integrated-routing/fixtures/obvious\'); import test_cart; test_cart.test_total_is_price_times_quantity(); print(\'PASS: test_total_is_price_times_quantity\')"'
CASE_C_CHANGED_PATH = "tests/phase11-integrated-routing/fixtures/obvious/cart.py"
CASE_C_CHILD_SESSIONS = [
    {
        "TRACE_REF": "C-NOX",
        "NATIVE_SESSION_ID": CASE_C_NOX_SESSION_ID,
        "AGENT": "nox",
        "PARENT_AGENT": "kael",
        "PARENT_SESSION_ID": CASE_C_ROOT_SESSION_ID,
        "LAUNCH_ORDER": 1,
        "INVOCATION_COUNT": 1,
        "EXECUTION_STATE": "SUCCEEDED",
        "FINAL_OUTCOME": "succeeded",
        "RESULT_ID": None,
        "PURPOSE": "read-only isolation verification",
        "DIRECTORY": CASE_C_ROOT_DIRECTORY,
        "PARENT_MESSAGE_ID": "msg_105f97af4001iJ9IWCZzegdMXF",
        "INVOCATION_TOOL_CALL_ID": "call_2s96dKTCsGrYQQHGGciHyiqG",
        "TERMINAL_MESSAGE_ID": "msg_105fa61d2001FgrVyYL9CwszWC",
        "CALL_CREATED_AT_EPOCH_MS": None,
    },
    {
        "TRACE_REF": "C-KOVAN",
        "NATIVE_SESSION_ID": "ses_efa03f35dffeSFO8Kg4CoukMfF",
        "AGENT": "kovan",
        "PARENT_AGENT": "kael",
        "PARENT_SESSION_ID": CASE_C_ROOT_SESSION_ID,
        "LAUNCH_ORDER": 2,
        "INVOCATION_COUNT": 1,
        "EXECUTION_STATE": "SUCCEEDED",
        "FINAL_OUTCOME": "succeeded",
        "RESULT_ID": None,
        "PURPOSE": "localized obvious defect correction",
        "DIRECTORY": CASE_C_ROOT_DIRECTORY,
        "PARENT_MESSAGE_ID": "msg_105fb4574001WppRL4y7Zyc69m",
        "INVOCATION_TOOL_CALL_ID": "call_vnFM7sNEU7T0mQuif6cWPaMY",
        "TERMINAL_MESSAGE_ID": "msg_105fcdec10013C1fOUpx6W5FsO",
        "CALL_CREATED_AT_EPOCH_MS": 1791101738171,
    },
]
CASE_C_CALLS = [
    {
        "TRACE_REF": "C-NOX",
        "AGENT": "nox",
        "TOOL_CALL_ID": "call_2s96dKTCsGrYQQHGGciHyiqG",
        "PARENT_MESSAGE_ID": "msg_105f97af4001iJ9IWCZzegdMXF",
        "TERMINAL_MESSAGE_ID": "msg_105fa61d2001FgrVyYL9CwszWC",
        "RETURN_STATUS": "SUCCESS",
        "CALL_CREATED_AT_EPOCH_MS": None,
        "CALL_COMPLETED_AT_EPOCH_MS": 1791101704676,
    },
    {
        "TRACE_REF": "C-KOVAN",
        "AGENT": "kovan",
        "TOOL_CALL_ID": "call_vnFM7sNEU7T0mQuif6cWPaMY",
        "PARENT_MESSAGE_ID": "msg_105fb4574001WppRL4y7Zyc69m",
        "TERMINAL_MESSAGE_ID": "msg_105fcdec10013C1fOUpx6W5FsO",
        "RETURN_STATUS": "SUCCESS",
        "CALL_CREATED_AT_EPOCH_MS": 1791101738171,
        "CALL_COMPLETED_AT_EPOCH_MS": None,
    },
]
CASE_C_EXPECTED_ROUTE = ["kael", "kovan"]
CASE_C_ACTUAL_ROUTE = ["kael", "nox", "kovan"]
CASE_C_NEGATIVE_ROLES = ("veyra", "orin", "atlas", "argus", "talos", "thales", "helios", "aegis", "vera")
CASE_C_TERMINAL_FACTS = {
    "WORKTREE_ISOLATION": "PASS",
    "STARTING_HEAD": CASE_C_ROOT_HEAD,
    "FILES_CHANGED": [CASE_C_CHANGED_PATH],
    "VALIDATION_COMMAND": CASE_C_TEST_COMMAND,
    "ENVIRONMENT": {
        "UV_NO_SYNC": "1",
        "UV_NO_PROJECT": "1",
        "UV_PYTHON_DOWNLOADS": "never",
        "PYTHONDONTWRITEBYTECODE": "1",
    },
    "VALIDATION_RESULT": "PASS — exit 0",
    "UNRESOLVED_WORK": "NONE",
    "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED": "YES",
    "ANY_WORK_REMAINING": "NO",
}
CURRENT_PHASE11_PENDING_LABELS = [
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_E_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_F_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT",
]
CASE_D_ROOT_SESSION_ID = "ses_ef8c726b7ffeqWgvWlpg0NcU1Q"
CASE_D_ROOT_DIRECTORY = "C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-d"
CASE_D_ROOT_HEAD = "60eb1685ee866a59de46be09dba3555c1cd3e776"
CASE_D_ROOT_TERMINAL_MESSAGE_ID = "msg_1073c822e001Dd7L8U2EANc2Qv"
CASE_D_ROOT_FINAL_FACTS = {
    "WORKTREE_ISOLATION": "PASS",
    "STARTING_HEAD": CASE_D_ROOT_HEAD,
    "FILES_CHANGED": "NONE",
    "DISCRIMINATING_EVIDENCE_FOUND": "NO",
    "DIAGNOSIS": "UNRESOLVED",
    "FINAL_BINARY_QUESTION": "Does this sample’s subtotal of 100 already include the shipping charge of 10—yes or no?",
    "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED": "YES",
    "ANY_WORK_REMAINING": "NO",
    "FINAL_OUTCOME": "NEEDS_USER_INPUT",
}
CASE_D_CHILD_SESSIONS = [
    {
        "TRACE_REF": "D-NOX",
        "NATIVE_SESSION_ID": "ses_ef8c67e03ffeYoAjNx6bfAmNdR",
        "AGENT": "nox",
        "PARENT_AGENT": "kael",
        "PARENT_SESSION_ID": CASE_D_ROOT_SESSION_ID,
        "LAUNCH_ORDER": 1,
        "INVOCATION_COUNT": 1,
        "EXECUTION_STATE": "SUCCEEDED",
        "FINAL_OUTCOME": "succeeded",
        "RESULT_ID": None,
        "PURPOSE": "read-only isolation verification",
        "DIRECTORY": CASE_D_ROOT_DIRECTORY,
        "PARENT_MESSAGE_ID": "msg_10738da77001sw2c1BCxYpNn7f",
        "INVOCATION_TOOL_CALL_ID": "call_A4ea0hsgKaNiR2OIRFRJyvYN",
        "TERMINAL_MESSAGE_ID": "msg_1073ab0ce001a1UsROefqolFon",
        "CALL_CREATED_AT_EPOCH_MS": 1791122552718,
        "CALL_RAN_AT_EPOCH_MS": 1791122571767,
        "CALL_COMPLETED_AT_EPOCH_MS": 1791122679030,
    },
    {
        "TRACE_REF": "D-VEYRA",
        "NATIVE_SESSION_ID": "ses_ef8c49280ffeiI6EQxlG6e4Pjx",
        "AGENT": "veyra",
        "PARENT_AGENT": "kael",
        "PARENT_SESSION_ID": CASE_D_ROOT_SESSION_ID,
        "LAUNCH_ORDER": 2,
        "INVOCATION_COUNT": 1,
        "EXECUTION_STATE": "SUCCEEDED",
        "FINAL_OUTCOME": "succeeded",
        "RESULT_ID": None,
        "PURPOSE": "bounded-contract evidence discovery; no discriminator found",
        "DIRECTORY": CASE_D_ROOT_DIRECTORY,
        "PARENT_MESSAGE_ID": "msg_1073b259a001jMCyxNlxFUkNnL",
        "INVOCATION_TOOL_CALL_ID": "call_oLpgTpp5wYC8wwKERvmdOA6z",
        "TERMINAL_MESSAGE_ID": "msg_1073b8049001QPsKFEXH6oxNVe",
        "CALL_CREATED_AT_EPOCH_MS": 1791122682739,
        "CALL_RAN_AT_EPOCH_MS": 1791122697594,
        "CALL_COMPLETED_AT_EPOCH_MS": 1791122720177,
    },
    {
        "TRACE_REF": "D-ARGUS",
        "NATIVE_SESSION_ID": "ses_ef8c3a562ffemV1PDdCkCYmThm",
        "AGENT": "argus",
        "PARENT_AGENT": "kael",
        "PARENT_SESSION_ID": CASE_D_ROOT_SESSION_ID,
        "LAUNCH_ORDER": 3,
        "INVOCATION_COUNT": 1,
        "EXECUTION_STATE": "SUCCEEDED",
        "FINAL_OUTCOME": "succeeded",
        "RESULT_ID": None,
        "PURPOSE": "one terminal diagnostic consultation on precollected bounded evidence",
        "DIRECTORY": CASE_D_ROOT_DIRECTORY,
        "PARENT_MESSAGE_ID": "msg_1073bc64c001DijUaWJWQkMZt9",
        "INVOCATION_TOOL_CALL_ID": "call_0W8pbZttAJh4hN0upzjDO7Ja",
        "TERMINAL_MESSAGE_ID": "msg_1073c5b890011Ppa5fJwtkxNDF",
        "CALL_CREATED_AT_EPOCH_MS": 1791122729330,
        "CALL_RAN_AT_EPOCH_MS": 1791122758297,
        "CALL_COMPLETED_AT_EPOCH_MS": 1791122768271,
    },
]
CASE_D_LITERAL_RETURN_STATUSES = {"nox": None, "veyra": None, "argus": "INCONCLUSIVE"}
CASE_D_NEGATIVE_ROLES = ("kovan", "orin", "vera", "atlas", "talos", "thales", "helios", "aegis")
CASE_D_EXPECTED_ROUTE = ["kael", "veyra", "argus"]
CASE_D_ACTUAL_ROUTE = ["kael", "nox", "veyra", "argus"]
CASE_D_PENDING_FOLLOWUP_COVERAGE = {
    "status": "NOT_EXERCISED",
    "case_d_followup": "NOT_REQUIRED",
    "native_followup_demonstration": False,
    "meaning": "Case D made no Argus evidence request; same-session follow-up runtime behavior was not demonstrated.",
    "future_review": "An optional genuine evidence-requesting scenario remains open for final coverage review.",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _event_positions(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_kind.setdefault(str(event.get("KIND")), []).append(event)
    return by_kind


def _one_event(events: list[dict[str, Any]], kind: str, ref: str) -> dict[str, Any] | None:
    found = [event for event in events if event.get("KIND") == kind and event.get("CHILD_REF") == ref]
    return found[0] if len(found) == 1 else None


def _consult_events(events: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    return [event for event in events if event.get("KIND") == "CONSULT" and event.get("ACTOR_ROLE") == role]


def _event_entity_order(marker: str, events: list[dict[str, Any]]) -> int | None:
    if ":CONSULT:" in marker:
        session_ref, _, ordinal = marker.rpartition(":CONSULT:")
        try:
            number = int(ordinal)
        except ValueError:
            return None
        found = [
            event
            for event in events
            if event.get("KIND") == "CONSULT"
            and event.get("SESSION_REF") == session_ref
            and event.get("CONSULTATION_NUMBER") == number
        ]
        return found[0].get("ORDER") if len(found) == 1 else None
    if marker.endswith(":RESULT"):
        ref = marker[: -len(":RESULT")]
        event = _one_event(events, "RESULT_CONSUMED", ref)
        return event.get("ORDER") if event else None
    start = _one_event(events, "CHILD_START", marker)
    return start.get("ORDER") if start else None


def _simultaneous_children(events: list[dict[str, Any]]) -> int:
    open_count = 0
    maximum = 0
    for event in sorted(events, key=lambda item: item.get("ORDER", -1)):
        if event.get("KIND") == "CHILD_START":
            open_count += 1
            maximum = max(maximum, open_count)
        elif event.get("KIND") == "CHILD_TERMINAL":
            open_count = max(0, open_count - 1)
    return maximum


def _path_overlaps(left: str, right: str) -> bool:
    a = left.replace("\\", "/").rstrip("/").casefold()
    b = right.replace("\\", "/").rstrip("/").casefold()
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def validate_trace(trace: dict[str, Any], case: dict[str, Any]) -> list[str]:
    """Return semantic discrepancies; an empty list means this trace is internally valid."""
    errors: list[str] = []
    add = errors.append
    missing = [field for field in REQUIRED_TRACE_FIELDS if field not in trace]
    if missing:
        return ["MISSING_REQUIRED_FIELDS:" + ",".join(missing)]

    trace_id = str(trace.get("TRACE_ID", "<unnamed>"))
    if trace.get("CASE_ID") != case.get("id"):
        add("CASE_ID_MISMATCH")
    if trace.get("REQUEST_CLASS") != case.get("request_class"):
        add("REQUEST_CLASS_MISMATCH")
    evidence_class = trace.get("EVIDENCE_CLASS")
    if evidence_class not in EVIDENCE_CLASSES:
        add("UNKNOWN_EVIDENCE_CLASS")

    scenario = trace.get("SCENARIO", "default")
    expected_routes = case.get("expected_routes", {})
    matrix_route = expected_routes.get(scenario)
    if matrix_route is None:
        add("SCENARIO_NOT_IN_CASE_MATRIX")
    elif trace.get("EXPECTED_ROUTE") != matrix_route:
        add("EXPECTED_ROUTE_DOES_NOT_MATCH_CASE_MATRIX")

    events = trace.get("EVENTS")
    children = trace.get("CHILD_SESSIONS")
    if not isinstance(events, list) or not isinstance(children, list):
        return errors + ["EVENTS_OR_CHILD_SESSIONS_NOT_LISTS"]
    orders = [event.get("ORDER") for event in events]
    if any(not isinstance(order, int) for order in orders) or orders != sorted(set(orders)):
        add("EVENT_ORDER_NOT_STRICTLY_INCREASING")
    provenance = trace.get("EVIDENCE_PROVENANCE", {})
    if provenance.get("CLASS") != evidence_class:
        add("PROVENANCE_CLASS_MISMATCH")
    expected_order_basis = "synthetic" if evidence_class == "SYNTHETIC_TRACE" else "observed"
    for event in events:
        if event.get("ORDER_BASIS") != expected_order_basis:
            add("EVENT_ORDER_PROVENANCE_MISSING_OR_MISMATCHED")
            break
    if evidence_class == "SYNTHETIC_TRACE":
        if trace.get("ROOT_SESSION_ID") is not None:
            add("SYNTHETIC_HAS_ROOT_SESSION_ID")
        if provenance.get("NATIVE_ROOT_SESSION_ID") is not None:
            add("SYNTHETIC_HAS_NATIVE_ROOT_ID")
        if provenance.get("NATIVE_CHILD_SESSION_IDS") != []:
            add("SYNTHETIC_HAS_NATIVE_CHILD_IDS")
        if provenance.get("ORDER_BASIS") != "synthetic":
            add("SYNTHETIC_ORDER_NOT_LABELED_SYNTHETIC")
        if any(child.get("NATIVE_SESSION_ID") is not None for child in children):
            add("SYNTHETIC_HAS_NATIVE_SESSION_ID")
    elif evidence_class in {"GUIDED_CURRENT_SESSION", "FRESH_ROOT_NATIVE"}:
        root_id = provenance.get("NATIVE_ROOT_SESSION_ID")
        if not isinstance(root_id, str) or not NATIVE_SESSION_ID.fullmatch(root_id):
            add("NATIVE_EVIDENCE_MISSING_ROOT_SESSION_ID")
        if trace.get("ROOT_SESSION_ID") != root_id:
            add("ROOT_SESSION_ID_PROVENANCE_MISMATCH")
        if provenance.get("ORDER_BASIS") != "observed":
            add("NATIVE_ORDER_NOT_LABELED_OBSERVED")
        if evidence_class == "FRESH_ROOT_NATIVE" and provenance.get("FRESH_ROOT_CONFIRMED") is not True:
            add("FRESH_ROOT_NOT_CONFIRMED")
        native_children = [child.get("NATIVE_SESSION_ID") for child in children]
        if any(not isinstance(session_id, str) or not NATIVE_SESSION_ID.fullmatch(session_id) for session_id in native_children):
            add("NATIVE_CHILD_SESSION_ID_MISSING_OR_INVALID")
        if len(native_children) != len(set(native_children)):
            add("NATIVE_CHILD_SESSION_IDS_NOT_UNIQUE")
        if provenance.get("NATIVE_CHILD_SESSION_IDS") != native_children:
            add("NATIVE_CHILD_SESSION_PROVENANCE_MISMATCH")
        for child in children:
            if child.get("PARENT_SESSION_ID") != root_id:
                add("NATIVE_CHILD_PARENT_SESSION_MISMATCH")
                break
        if root_id in native_children:
            add("NATIVE_ROOT_REUSED_AS_CHILD_SESSION")

    by_ref = {child.get("TRACE_REF"): child for child in children}
    if len(by_ref) != len(children) or None in by_ref:
        add("CHILD_TRACE_REFS_NOT_UNIQUE")
    starts = [event for event in events if event.get("KIND") == "CHILD_START"]
    terminals = [event for event in events if event.get("KIND") == "CHILD_TERMINAL"]
    consumes = [event for event in events if event.get("KIND") == "RESULT_CONSUMED"]
    start_refs = [event.get("CHILD_REF") for event in starts]
    if len(start_refs) != len(set(start_refs)) or set(start_refs) != set(by_ref):
        add("CHILD_START_SESSION_SET_MISMATCH")
    if evidence_class in {"GUIDED_CURRENT_SESSION", "FRESH_ROOT_NATIVE"}:
        for event in events:
            session_ref = event.get("CHILD_REF")
            if session_ref is None and event.get("KIND") in {"CONSULT", "EVIDENCE_REQUEST"}:
                session_ref = event.get("SESSION_REF")
            child = by_ref.get(session_ref)
            if child is not None and event.get("NATIVE_SESSION_ID") != child.get("NATIVE_SESSION_ID"):
                add(f"NATIVE_EVENT_SESSION_JOIN_MISMATCH:{session_ref}")

    terminal_by_ref: dict[str, list[dict[str, Any]]] = {}
    consume_by_ref: dict[str, list[dict[str, Any]]] = {}
    for event in terminals:
        terminal_by_ref.setdefault(event.get("CHILD_REF"), []).append(event)
    for event in consumes:
        consume_by_ref.setdefault(event.get("CHILD_REF"), []).append(event)

    pending = 0
    unconsumed = 0
    unknown = 0
    for ref, child in by_ref.items():
        role = child.get("AGENT")
        if child.get("PARENT_AGENT") != "kael":
            add(f"DIRECT_CHILD_ROUTE_VIOLATION:{role}")
        if role == "aegis":
            add("AEGIS_CHILD_LAUNCH_FORBIDDEN")
        if role not in ROLE_ACTIONS:
            add(f"UNKNOWN_CHILD_ROLE:{role}")
        terminal = terminal_by_ref.get(ref, [])
        consumed = consume_by_ref.get(ref, [])
        state = child.get("EXECUTION_STATE")
        if state == "UNKNOWN":
            unknown += 1
            pending += 1
            if terminal or consumed:
                add(f"UNKNOWN_EXECUTION_RESULT_MUST_NOT_BE_CONSUMED:{ref}")
        elif state in {"SUCCEEDED", "FAILED"}:
            if len(terminal) != 1 or terminal[0].get("STATE") != state:
                add(f"CHILD_TERMINAL_NOT_EXACTLY_ONCE:{ref}")
                if not terminal:
                    pending += 1
            if len(consumed) != 1:
                add(f"RESULT_CONSUMPTION_NOT_EXACTLY_ONCE:{ref}")
                if len(consumed) == 0 and terminal:
                    unconsumed += 1
            elif terminal and consumed[0].get("ORDER", 0) <= terminal[0].get("ORDER", 0):
                add(f"RESULT_CONSUMED_BEFORE_TERMINAL:{ref}")
        else:
            add(f"INVALID_EXECUTION_STATE:{ref}")
    for event in starts:
        if event.get("ACTOR_ROLE") != "kael":
            add("CHILD_LAUNCH_NOT_OWNED_BY_KAEL")
        ref = event.get("CHILD_REF")
        child = by_ref.get(ref)
        if child is not None and event.get("AGENT") != child.get("AGENT"):
            add(f"CHILD_START_SESSION_ROLE_MISMATCH:{ref}")
    for event in consumes:
        if event.get("ACTOR_ROLE") != "kael":
            add("RESULT_CONSUMPTION_NOT_OWNED_BY_KAEL")

    for event in terminals:
        ref = event.get("CHILD_REF")
        if ref not in by_ref:
            add(f"CHILD_TERMINAL_UNKNOWN_CHILD_REF:{ref}")
            continue
        start = _one_event(events, "CHILD_START", ref)
        if start is None or start.get("ORDER", 0) >= event.get("ORDER", 0):
            add(f"CHILD_TERMINAL_BEFORE_START:{ref}")
        if event.get("ACTOR_ROLE") != "kael":
            add(f"CHILD_TERMINAL_NOT_OWNED_BY_KAEL:{ref}")
        if not event.get("RESULT_ID"):
            add(f"CHILD_TERMINAL_RESULT_ID_MISSING:{ref}")
    for event in consumes:
        ref = event.get("CHILD_REF")
        if ref not in by_ref:
            add(f"RESULT_CONSUMED_UNKNOWN_CHILD_REF:{ref}")
            continue
        terminal = _one_event(events, "CHILD_TERMINAL", ref)
        if terminal is None or terminal.get("ORDER", 0) >= event.get("ORDER", 0):
            add(f"RESULT_CONSUMED_WITHOUT_PRIOR_TERMINAL:{ref}")
        elif event.get("RESULT_ID") != terminal.get("RESULT_ID"):
            add(f"RESULT_CONSUMED_ID_DOES_NOT_MATCH_TERMINAL:{ref}")
    terminal_result_ids = [event.get("RESULT_ID") for event in terminals if event.get("RESULT_ID")]
    consumed_result_ids = [event.get("RESULT_ID") for event in consumes if event.get("RESULT_ID")]
    if len(terminal_result_ids) != len(set(terminal_result_ids)):
        add("CHILD_TERMINAL_RESULT_IDS_NOT_UNIQUE")
    if len(consumed_result_ids) != len(set(consumed_result_ids)):
        add("RESULT_ID_CONSUMED_MORE_THAN_ONCE")
    for event in events:
        if event.get("KIND") == "CHILD_TERMINAL" and event.get("CHILD_REF") not in by_ref:
            continue
        ref = event.get("CHILD_REF")
        if event.get("KIND") in {"ACTION", "EVIDENCE_PRODUCED", "EVIDENCE_DELIVERED"} and ref in by_ref:
            child = by_ref[ref]
            role = event.get("ACTOR_ROLE")
            if event.get("KIND") == "EVIDENCE_DELIVERED" and role == "kael":
                pass
            elif role != child.get("AGENT"):
                add(f"CHILD_EVENT_SESSION_ROLE_MISMATCH:{event.get('KIND')}:{ref}")
            start = _one_event(events, "CHILD_START", ref)
            terminal = _one_event(events, "CHILD_TERMINAL", ref)
            if start and event.get("ORDER", 0) <= start.get("ORDER", 0):
                add(f"CHILD_EVENT_BEFORE_START:{event.get('KIND')}:{ref}")
            if terminal and event.get("ORDER", 0) >= terminal.get("ORDER", 0):
                add(f"CHILD_EVENT_AFTER_TERMINAL:{event.get('KIND')}:{ref}")
        elif event.get("KIND") == "ACTION" and event.get("ACTOR_ROLE") not in {"kael", "aegis"}:
            add(f"ACTION_CHILD_REF_MISSING:{event.get('ACTOR_ROLE')}:{event.get('ACTION')}")
    for role in GATED_REASONERS:
        calls = _consult_events(events, role)
        for number, call in enumerate(calls, start=1):
            session = by_ref.get(call.get("SESSION_REF"))
            if session is None or session.get("AGENT") != role:
                add(f"CONSULTATION_SESSION_ROLE_MISMATCH:{role}")
            if call.get("CONSULTATION_NUMBER") != number:
                add(f"CONSULTATION_NUMBER_SEQUENCE_MISMATCH:{role}")
            start = _one_event(events, "CHILD_START", call.get("SESSION_REF", ""))
            if start is None or start.get("ORDER", 0) >= call.get("ORDER", 0):
                add(f"CONSULTATION_BEFORE_SESSION_START:{role}")

    child_order = [
        by_ref[event.get("CHILD_REF")].get("AGENT")
        for event in starts
        if event.get("CHILD_REF") in by_ref
    ]
    if trace.get("ROUTE_MODE") == "KAEL_ROOT":
        derived_route = ["kael", *child_order]
    elif trace.get("ROUTE_MODE") == "USER_MAINTAIN_ROOT":
        entries = [event for event in events if event.get("KIND") == "MAINTENANCE_ENTRY"]
        derived_route = ["user", "/maintain", "aegis"] if len(entries) == 1 else []
    else:
        derived_route = []
        add("UNKNOWN_ROUTE_MODE")
    if trace.get("ACTUAL_ROUTE") != derived_route:
        add("ACTUAL_ROUTE_DOES_NOT_MATCH_OBSERVED_CHILD_ORDER")
    if matrix_route is not None and trace.get("ACTUAL_ROUTE") != matrix_route:
        add("ACTUAL_ROUTE_DIFFERS_FROM_EXPECTED_ROUTE")

    consultation_counts = trace.get("CONSULTATION_COUNTS", {})
    computed_counts = {role: 0 for role in ALL_INVOCABLE_ROLES}
    for child in children:
        if child.get("AGENT") not in GATED_REASONERS and child.get("AGENT") in computed_counts:
            computed_counts[child["AGENT"]] += 1
    for role in GATED_REASONERS:
        computed_counts[role] = len(_consult_events(events, role))
    entries = [event for event in events if event.get("KIND") == "MAINTENANCE_ENTRY"]
    computed_counts["aegis"] += len(entries)
    for role in ALL_INVOCABLE_ROLES:
        if consultation_counts.get(role) != computed_counts[role]:
            add(f"CONSULTATION_COUNT_MISMATCH:{role}")
    for role, required_zero in trace.get("NEGATIVE_CONTROLS", {}).items():
        actual = computed_counts.get(role)
        if required_zero != 0:
            add(f"NEGATIVE_CONTROL_EXPECTATION_NOT_ZERO:{role}")
        if actual != 0:
            add(f"NEGATIVE_CONTROL_ACTIVATED:{role}")
        if role not in computed_counts:
            add(f"NEGATIVE_CONTROL_UNKNOWN_ROLE:{role}")

    for role in GATED_REASONERS:
        calls = _consult_events(events, role)
        count = len(calls)
        if count > HARD_BUDGET[role]:
            add(f"HARD_CONSULTATION_BUDGET_EXCEEDED:{role}")
        if count > NORMAL_BUDGET[role] and role in {"argus", "talos"}:
            third = next((event for event in calls if event.get("CONSULTATION_NUMBER") == 3), {})
            if third.get("SECOND_DISCRIMINATING_ROUND") is not True or not third.get("SEPARATES_HYPOTHESES"):
                add(f"THIRD_CONSULTATION_NOT_JUSTIFIED:{role}")
        if count > 2 and role not in {"argus", "talos"}:
            add(f"AUTOMATIC_CONSULTATION_BUDGET_EXCEEDED:{role}")
        if count > 1:
            session_refs = {event.get("SESSION_REF") for event in calls}
            if len(session_refs) != 1:
                add(f"FOLLOWUP_DID_NOT_REUSE_SAME_SESSION:{role}")
            for previous, current in zip(calls, calls[1:]):
                new_ids = current.get("EVIDENCE_IDS", [])
                if not new_ids:
                    add(f"FOLLOWUP_WITHOUT_NEW_EVIDENCE:{role}")
                    continue
                prior_ids = {
                    evidence_id
                    for call in calls
                    if call.get("ORDER", 0) < current.get("ORDER", 0)
                    for evidence_id in call.get("EVIDENCE_IDS", [])
                }
                if prior_ids.intersection(new_ids):
                    add(f"FOLLOWUP_REUSES_PRIOR_EVIDENCE:{role}")
                delivered = [
                    event
                    for event in events
                    if event.get("KIND") == "EVIDENCE_DELIVERED"
                    and event.get("EVIDENCE_IDS")
                    and set(event["EVIDENCE_IDS"]).intersection(new_ids)
                    and previous.get("ORDER", 0) < event.get("ORDER", 0) < current.get("ORDER", 0)
                ]
                consumed_before = [
                    event
                    for event in events
                    if event.get("KIND") == "RESULT_CONSUMED"
                    and set(event.get("EVIDENCE_IDS", [])).intersection(new_ids)
                    and event.get("ORDER", 0) < current.get("ORDER", 0)
                ]
                if not delivered or not consumed_before:
                    add(f"FOLLOWUP_EVIDENCE_NOT_DELIVERED_AND_CONSUMED:{role}")
                if delivered and consumed_before:
                    if max(event.get("ORDER", 0) for event in delivered) >= min(event.get("ORDER", 0) for event in consumed_before):
                        add(f"FOLLOWUP_EVIDENCE_CONSUMED_BEFORE_DELIVERY:{role}")
                    if max(event.get("ORDER", 0) for event in consumed_before) >= current.get("ORDER", 0):
                        add(f"FOLLOWUP_BEFORE_EVIDENCE_CONSUMPTION:{role}")
        for event in events:
            if event.get("KIND") == "NO_PROGRESS_STOP" and event.get("ACTOR_ROLE") == role:
                if any(call.get("ORDER", 0) > event.get("ORDER", 0) for call in calls):
                    add(f"CONSULTATION_AFTER_NO_PROGRESS_STOP:{role}")

    for request in [event for event in events if event.get("KIND") == "EVIDENCE_REQUEST"]:
        role = request.get("ACTOR_ROLE")
        session_ref = request.get("SESSION_REF")
        calls = [event for event in _consult_events(events, role) if event.get("SESSION_REF") == session_ref]
        prior_calls = [event for event in calls if event.get("ORDER", 0) < request.get("ORDER", 0)]
        later_calls = [event for event in calls if event.get("ORDER", 0) > request.get("ORDER", 0)]
        if not prior_calls:
            add(f"EVIDENCE_REQUEST_WITHOUT_INITIAL_REASONER_CONSULT:{role}")
        elif len(prior_calls) != 1 or prior_calls[0].get("CONSULTATION_NUMBER") != 1:
            add(f"EVIDENCE_REQUEST_NOT_AFTER_FIRST_CONSULT:{role}")
        if not later_calls:
            add(f"EVIDENCE_REQUEST_NOT_FOLLOWED_UP_IN_SAME_SESSION:{role}")
        elif later_calls[0].get("CONSULTATION_NUMBER") != 2:
            add(f"EVIDENCE_REQUEST_NOT_FOLLOWED_BY_SECOND_CONSULT:{role}")
        worker_ref = request.get("WORKER_REF")
        evidence_ids = set(request.get("EVIDENCE_IDS", []))
        worker = by_ref.get(worker_ref)
        if worker is None or worker.get("PARENT_AGENT") != "kael":
            add(f"EVIDENCE_WORKER_NOT_DIRECT_KAEL_CHILD:{role}")
        worker_start = _one_event(events, "CHILD_START", worker_ref or "")
        if worker_start is None or worker_start.get("ORDER", 0) <= request.get("ORDER", 0):
            add(f"EVIDENCE_WORKER_STARTED_BEFORE_REQUEST:{role}")
        produced = [
            event
            for event in events
            if event.get("KIND") == "EVIDENCE_PRODUCED"
            and event.get("CHILD_REF") == worker_ref
            and evidence_ids.intersection(event.get("EVIDENCE_IDS", []))
        ]
        delivered = [
            event
            for event in events
            if event.get("KIND") == "EVIDENCE_DELIVERED"
            and event.get("CHILD_REF") == worker_ref
            and evidence_ids.intersection(event.get("EVIDENCE_IDS", []))
        ]
        if not evidence_ids or not produced or not delivered:
            add(f"REQUESTED_EVIDENCE_NOT_RETURNED:{role}")
            continue
        if any(event.get("ORDER", 0) <= request.get("ORDER", 0) for event in produced):
            add(f"EVIDENCE_PRODUCED_BEFORE_REQUEST:{role}")
        worker_actions = [
            event for event in events
            if event.get("KIND") == "ACTION"
            and event.get("CHILD_REF") == worker_ref
            and event.get("ACTOR_ROLE") == (worker or {}).get("AGENT")
        ]
        if not worker_actions or any(
            not any(action.get("ORDER", 0) < production.get("ORDER", 0) for action in worker_actions)
            for production in produced
        ):
            add(f"EVIDENCE_PRODUCED_WITHOUT_PRIOR_WORKER_ACTION:{role}")
        if any(event.get("ORDER", 0) <= request.get("ORDER", 0) for event in delivered):
            add(f"EVIDENCE_DELIVERED_BEFORE_REQUEST:{role}")
        if any(not event.get("DISTINGUISHING_FACT") or not event.get("DISCRIMINATES") for event in produced):
            add(f"EVIDENCE_NOT_MATERIALLY_DISCRIMINATING:{role}")
        requested_discriminators = request.get("DISCRIMINATES")
        if not requested_discriminators or any(event.get("DISCRIMINATES") != requested_discriminators for event in produced):
            add(f"EVIDENCE_DOES_NOT_ANSWER_DISCRIMINATING_REQUEST:{role}")
        if any(event.get("EVIDENCE_IDS") != request.get("EVIDENCE_IDS") for event in produced + delivered):
            add(f"EVIDENCE_IDS_DO_NOT_MATCH_REQUEST:{role}")
        if any(not any(p.get("ORDER", 0) < d.get("ORDER", 0) for p in produced) for d in delivered):
            add(f"EVIDENCE_DELIVERED_BEFORE_PRODUCTION:{role}")
        if later_calls and not any(event.get("ORDER", 0) < later_calls[0].get("ORDER", 0) for event in delivered):
            add(f"FOLLOWUP_BEFORE_EVIDENCE_DELIVERY:{role}")
        consumed_evidence = [
            event
            for event in consumes
            if event.get("CHILD_REF") == worker_ref
            and evidence_ids.intersection(event.get("EVIDENCE_IDS", []))
        ]
        if not later_calls or not consumed_evidence or not any(
            max(p.get("ORDER", 0) for p in produced) < min(d.get("ORDER", 0) for d in delivered)
            < consumed.get("ORDER", 0) < later_calls[0].get("ORDER", 0)
            for consumed in consumed_evidence
        ):
            add(f"EVIDENCE_NOT_PRODUCED_DELIVERED_CONSUMED_BEFORE_FOLLOWUP:{role}")
        prior_ids = {
            evidence_id
            for call in prior_calls
            for evidence_id in call.get("EVIDENCE_IDS", [])
        }
        if prior_ids.intersection(evidence_ids):
            add(f"REQUEST_REUSES_PRIOR_EVIDENCE:{role}")
        prior_facts = {
            event.get("DISTINGUISHING_FACT")
            for event in events
            if event.get("KIND") in {"EVIDENCE_PRODUCED", "EVIDENCE_DELIVERED"}
            and event.get("ORDER", 0) < request.get("ORDER", 0)
            and prior_ids.intersection(event.get("EVIDENCE_IDS", []))
            and event.get("DISTINGUISHING_FACT")
        }
        produced_facts = {event.get("DISTINGUISHING_FACT") for event in produced if event.get("DISTINGUISHING_FACT")}
        if prior_facts.intersection(produced_facts):
            add(f"FOLLOWUP_EVIDENCE_NOT_MATERIALLY_NEW:{role}")
        for evidence_id in evidence_ids:
            if len([event for event in produced if evidence_id in event.get("EVIDENCE_IDS", [])]) != 1:
                add(f"REQUESTED_EVIDENCE_PRODUCTION_NOT_EXACTLY_ONCE:{role}:{evidence_id}")
            if len([event for event in delivered if evidence_id in event.get("EVIDENCE_IDS", [])]) != 1:
                add(f"REQUESTED_EVIDENCE_DELIVERY_NOT_EXACTLY_ONCE:{role}:{evidence_id}")
        if later_calls:
            followup_ids = set(later_calls[0].get("EVIDENCE_IDS", []))
            if not evidence_ids.issubset(followup_ids):
                add(f"FOLLOWUP_OMITS_REQUESTED_EVIDENCE:{role}")

    actions = [
        {"ROLE": event.get("ACTOR_ROLE"), "ACTION": event.get("ACTION")}
        for event in events
        if event.get("KIND") == "ACTION"
    ]
    purity = trace.get("ROLE_PURITY", {})
    if purity.get("VIOLATIONS") != []:
        add("ROLE_PURITY_RECORDED_VIOLATION")
    if purity.get("OBSERVED_ACTIONS") != actions:
        add("ROLE_PURITY_ACTION_LEDGER_MISMATCH")
    for action in actions:
        role = action.get("ROLE")
        if action.get("ACTION") not in ROLE_ACTIONS.get(role, set()):
            add(f"ROLE_ACTION_NOT_ALLOWED:{role}:{action.get('ACTION')}")
    for event in [event for event in events if event.get("KIND") == "ACTION"]:
        role = event.get("ACTOR_ROLE")
        if role not in {"kael", "aegis"}:
            ref = event.get("CHILD_REF")
            child = by_ref.get(ref)
            if child is None or child.get("AGENT") != role:
                add(f"ACTION_CHILD_SESSION_ROLE_MISMATCH:{role}:{ref}")
        elif event.get("CHILD_REF") is not None:
            child = by_ref.get(event.get("CHILD_REF"))
            if child is None or child.get("AGENT") != role:
                add(f"ACTION_CHILD_SESSION_ROLE_MISMATCH:{role}:{event.get('CHILD_REF')}")

    event_by_ref = {child.get("TRACE_REF"): child for child in children}
    declared_edges = set()
    for edge in trace.get("DEPENDENCY_ORDER", []):
        before_marker = str(edge.get("BEFORE", ""))
        after_marker = str(edge.get("AFTER", ""))
        declared_edges.add((before_marker, after_marker))
        before = _event_entity_order(before_marker, events)
        after = _event_entity_order(after_marker, events)
        if before is None or after is None or before >= after:
            add("DEPENDENCY_ORDER_NOT_OBSERVED")
        if ":CONSULT:" not in after_marker and after_marker in event_by_ref:
            prerequisite_marker = before_marker
            prerequisite_ref = prerequisite_marker[:-len(":RESULT")] if prerequisite_marker.endswith(":RESULT") else prerequisite_marker
            if prerequisite_ref in event_by_ref:
                prerequisite_result = _one_event(events, "RESULT_CONSUMED", prerequisite_ref)
                dependent_start = _one_event(events, "CHILD_START", after_marker)
                if not prerequisite_result or not dependent_start or prerequisite_result.get("ORDER", 0) >= dependent_start.get("ORDER", 0):
                    add("DEPENDENCY_RESULT_NOT_CONSUMED_BEFORE_DEPENDENT_START")
    for required in case.get("mandatory_dependency_edges", []):
        before_ref = next((child.get("TRACE_REF") for child in children if child.get("WORK_ID") == required.get("before_work_id")), None)
        after_ref = next((child.get("TRACE_REF") for child in children if child.get("WORK_ID") == required.get("after_work_id")), None)
        after_consultation = required.get("after_consultation")
        before_marker = f"{before_ref}:RESULT" if before_ref else None
        if after_ref:
            after_marker = after_ref
        elif after_consultation:
            session_ref = next((event.get("SESSION_REF") for event in _consult_events(events, after_consultation.get("role")) if event.get("CONSULTATION_NUMBER") == after_consultation.get("number")), None)
            after_marker = f"{session_ref}:CONSULT:{after_consultation.get('number')}" if session_ref else None
        else:
            after_marker = None
        if not before_marker or not after_marker or (before_marker, after_marker) not in declared_edges:
            add("MANDATORY_DEPENDENCY_EDGE_MISSING")

    question_events = [event for event in events if event.get("KIND") == "USER_QUESTION"]
    if trace.get("USER_QUESTION_COUNT") != len(question_events):
        add("USER_QUESTION_COUNT_MISMATCH")
    if len(question_events) > 1:
        add("MORE_THAN_ONE_BOUNDED_USER_QUESTION")
    for question in question_events:
        if question.get("ACTOR_ROLE") != "kael":
            add("USER_QUESTION_NOT_OWNED_BY_KAEL")
        if not question.get("QUESTION_ID"):
            add("USER_QUESTION_ID_MISSING")
        if not question.get("BOUNDED") or not question.get("QUESTION"):
            add("USER_QUESTION_NOT_BOUNDED")
        question_order = question.get("ORDER", 0)
        for ref in start_refs:
            terminal = terminal_by_ref.get(ref, [])
            consumed = consume_by_ref.get(ref, [])
            start = _one_event(events, "CHILD_START", ref)
            if start and start.get("ORDER", 0) < question_order and (
                len(terminal) != 1
                or len(consumed) != 1
                or terminal[0].get("ORDER", 0) >= question_order
                or consumed[0].get("ORDER", 0) >= question_order
            ):
                add("USER_QUESTION_BEFORE_CHILDREN_RECONCILED")
        resolutions = [
            event for event in events
            if event.get("KIND") == "QUESTION_RESOLVED"
            and event.get("QUESTION_ID") == question.get("QUESTION_ID")
        ]
        if len(resolutions) > 1:
            add("USER_QUESTION_RESOLVED_MORE_THAN_ONCE")
        for resolution in resolutions:
            if resolution.get("ACTOR_ROLE") != "user" or not resolution.get("ANSWER"):
                add("USER_QUESTION_RESOLUTION_INVALID")
            if resolution.get("ORDER", 0) <= question_order:
                add("USER_QUESTION_RESOLVED_BEFORE_ASKED")
        for start in starts:
            if start.get("ORDER", 0) > question_order:
                if not any(
                    resolution.get("ORDER", 0) < start.get("ORDER", 0)
                    for resolution in resolutions
                ):
                    add("DEPENDENT_WORK_BEFORE_QUESTION_RESOLVED")
    for resolution in [event for event in events if event.get("KIND") == "QUESTION_RESOLVED"]:
        if not any(question.get("QUESTION_ID") == resolution.get("QUESTION_ID") for question in question_events):
            add("QUESTION_RESOLUTION_WITHOUT_QUESTION")
    unresolved_questions = [
        question for question in question_events
        if not any(
            resolution.get("QUESTION_ID") == question.get("QUESTION_ID")
            and resolution.get("ORDER", 0) > question.get("ORDER", 0)
            for resolution in events if resolution.get("KIND") == "QUESTION_RESOLVED"
        )
    ]
    if unresolved_questions and trace.get("FINAL_OUTCOME") != "NEEDS_USER_INPUT":
        add("UNRESOLVED_USER_QUESTION_NOT_REPORTED_PENDING")

    gate = trace.get("COMPLETION_GATE", {})
    if gate.get("PENDING_CHILD_COUNT") != pending:
        add("COMPLETION_PENDING_COUNT_MISMATCH")
    if gate.get("UNCONSUMED_RESULT_COUNT") != unconsumed:
        add("COMPLETION_UNCONSUMED_COUNT_MISMATCH")
    if gate.get("UNKNOWN_EXECUTION_COUNT") != unknown:
        add("COMPLETION_UNKNOWN_COUNT_MISMATCH")
    if gate.get("EXACT_ONCE") is not (unconsumed == 0 and all(len(consume_by_ref.get(ref, [])) <= 1 for ref in by_ref)):
        add("COMPLETION_EXACT_ONCE_ASSERTION_MISMATCH")
    if gate.get("QUESTION_BARRIER_SATISFIED") is not (
        not any(error == "USER_QUESTION_BEFORE_CHILDREN_RECONCILED" for error in errors)
    ):
        add("QUESTION_BARRIER_ASSERTION_MISMATCH")
    outcome = trace.get("FINAL_OUTCOME")
    final_events = [event for event in events if event.get("KIND") == "FINAL_OUTCOME"]
    if len(final_events) != 1 or final_events[0].get("VALUE") != outcome:
        add("FINAL_OUTCOME_EVENT_MISMATCH")
    if unknown:
        if outcome != "COMPLETION_UNCONFIRMED":
            add("UNKNOWN_EXECUTION_NOT_REPORTED_UNCONFIRMED")
        work_ids = [child.get("WORK_ID") for child in children]
        for child in children:
            if child.get("EXECUTION_STATE") == "UNKNOWN" and work_ids.count(child.get("WORK_ID")) > 1:
                add("UNKNOWN_EXECUTION_RETRY_FORBIDDEN")
    elif outcome in {"SUCCEEDED", "STOP_FOR_USER_APPROVAL"} and (pending or unconsumed):
        add("FINAL_OUTCOME_BEFORE_COMPLETION_GATE")

    result = trace.get("RESULT_FIDELITY", {})
    if result.get("UNKNOWN") is True:
        if result.get("OBSERVED_RESULT") is not None or result.get("MATCHES") is not None:
            add("UNKNOWN_RESULT_METRIC_MUST_BE_NULL")
    elif result.get("MATCHES") is not (result.get("EXPECTED_RESULT") == result.get("OBSERVED_RESULT")):
        add("RESULT_FIDELITY_ASSERTION_MISMATCH")
    if trace.get("CASE_ID") == "A":
        contract = case.get("request_contract", {})
        expected_text = contract.get("desired_text")
        target = contract.get("target")
        writes = [child for child in children if child.get("AGENT") == "kovan" and target in child.get("WRITE_PATHS", [])]
        matching_actions = [
            event for event in events
            if event.get("KIND") == "ACTION"
            and event.get("ACTOR_ROLE") == "kovan"
            and event.get("ACTION") == "IMPLEMENT"
            and event.get("TARGET") == target
            and event.get("CHILD_REF") in {child.get("TRACE_REF") for child in writes}
        ]
        consumed_values = [
            event.get("RESULT_VALUE") for event in consumes
            if event.get("CHILD_REF") in {child.get("TRACE_REF") for child in writes}
        ]
        if not expected_text or result.get("EXPECTED_RESULT") != expected_text:
            add("CASE_A_EXPECTED_RESULT_DOES_NOT_MATCH_REQUEST")
        if result.get("UNKNOWN") is True:
            if result.get("OBSERVED_RESULT") is not None:
                add("CASE_A_UNKNOWN_RESULT_MUST_REMAIN_NULL")
        else:
            if len(writes) != 1 or len(matching_actions) != 1 or matching_actions[0].get("REQUESTED_VALUE") != expected_text:
                add("CASE_A_EDIT_ACTION_DOES_NOT_MATCH_REQUEST_CONTRACT")
            if len(consumed_values) != 1 or consumed_values[0] != result.get("OBSERVED_RESULT"):
                add("CASE_A_OBSERVED_RESULT_NOT_DERIVED_FROM_CONSUMED_RESULT")
            if result.get("OBSERVED_RESULT") != expected_text or result.get("MATCHES") is not True:
                add("CASE_A_SUCCESS_WITH_STALE_OR_MISMATCHED_CONTENT")

    facts = trace.get("GATE_FACTS", {})
    if any(not isinstance(facts.get(key), bool) for key in REQUIRED_GATE_FACTS):
        add("GATE_FACTS_MISSING_OR_NOT_BOOLEAN")
    counts = computed_counts
    if facts.get("EXPLICIT_OPTIMIZATION_INTENT") and counts["helios"] < 1:
        add("EXPLICIT_OPTIMIZATION_GATE_NOT_ACTIVATED")
    if not facts.get("EXPLICIT_OPTIMIZATION_INTENT") and counts["helios"]:
        add("HELIOS_WITHOUT_EXPLICIT_OPTIMIZATION_INTENT")
    if facts.get("EXPLICIT_PLANNING_INTENT") and counts["atlas"] < 1:
        add("EXPLICIT_PLANNING_GATE_NOT_ACTIVATED")
    if counts["atlas"] and not facts.get("EXPLICIT_PLANNING_INTENT"):
        justification = case.get("planning_gate_justification")
        material_dependencies = justification.get("material_dependencies") if isinstance(justification, dict) else None
        valid_justification = (
            isinstance(justification, dict)
            and justification.get("basis") == "MATERIAL_DEPENDENCY"
            and isinstance(justification.get("rationale"), str)
            and bool(justification["rationale"].strip())
            and isinstance(material_dependencies, list)
            and bool(material_dependencies)
            and all(
                isinstance(dependency, dict)
                and all(
                    isinstance(dependency.get(field), str) and dependency[field].strip()
                    for field in ("producer", "consumer", "planning_need")
                )
                for dependency in material_dependencies
            )
        )
        if not valid_justification:
            add("ATLAS_WITHOUT_EXPLICIT_INTENT_OR_MATERIAL_PLANNING_JUSTIFICATION")
    if facts.get("OBVIOUS_FUNCTIONAL_CAUSE") and counts["argus"]:
        add("ARGUS_FOR_OBVIOUS_FUNCTIONAL_BUG")
    if facts.get("NONTRIVIAL_FUNCTIONAL_CAUSE") and counts["argus"] < 1:
        add("NONTRIVIAL_FUNCTIONAL_GATE_NOT_ACTIVATED")
    if facts.get("SECURITY_BOUNDARY") and (counts["talos"] < 1 or counts["argus"]):
        add("SECURITY_ROUTING_GATE_MISCLASSIFIED")
    if facts.get("OPERATIONAL_TOOLING_FAILURE") and any(counts[role] for role in ("argus", "talos", "thales")):
        add("OPERATIONAL_FAILURE_OVER_ESCALATED")
    if facts.get("HIGH_UNCERTAINTY_AFTER_BOUNDED_DIAGNOSIS") and counts["thales"] < 1:
        add("HIGH_UNCERTAINTY_GATE_NOT_ACTIVATED")

    helios_calls = _consult_events(events, "helios")
    if helios_calls:
        proposals = [event for event in events if event.get("KIND") == "PROPOSAL" and event.get("ACTOR_ROLE") == "helios"]
        approvals = [event for event in events if event.get("KIND") == "APPROVAL_GATE"]
        if not proposals or not approvals or any(event.get("DECISION") != "PENDING" for event in approvals):
            add("HELIOS_PROPOSAL_MISSING_APPROVAL_STOP")
        proposal_order = min((event.get("ORDER", 0) for event in proposals), default=0)
        if any(
            event.get("KIND") == "ACTION"
            and event.get("ACTOR_ROLE") == "kovan"
            and event.get("ACTION") == "IMPLEMENT"
            and event.get("ORDER", 0) > proposal_order
            for event in events
        ):
            add("IMPLEMENTATION_AFTER_HELIOS_PROPOSAL_BEFORE_APPROVAL")
        if outcome != "STOP_FOR_USER_APPROVAL":
            add("HELIOS_DID_NOT_STOP_FOR_USER_APPROVAL")

    if facts.get("THIRD_PARTY_BUG"):
        approval = any(event.get("KIND") == "USER_APPROVAL" and event.get("EXPLICIT") is True for event in events)
        modification = any(event.get("KIND") == "THIRD_PARTY_MODIFICATION" for event in events)
        if modification and not approval:
            add("THIRD_PARTY_PATCH_VENDOR_FORK_WITHOUT_APPROVAL")

    maintenance_entries = [event for event in events if event.get("KIND") == "MAINTENANCE_ENTRY"]
    if facts.get("MAINTENANCE_ENTRY_EXPLICIT") is not bool(maintenance_entries):
        add("MAINTENANCE_ENTRY_GATE_FACT_MISMATCH")
    if maintenance_entries:
        entry = maintenance_entries[0]
        if len(maintenance_entries) != 1 or entry.get("ACTOR_ROLE") != "user" or entry.get("COMMAND") != "/maintain" or entry.get("TARGET_ROLE") != "aegis":
            add("MAINTENANCE_ENTRY_NOT_EXPLICIT_USER_COMMAND")
        for action_event in [event for event in events if event.get("KIND") == "ACTION" and event.get("ACTOR_ROLE") == "aegis"]:
            if entry.get("ORDER", 0) >= action_event.get("ORDER", 0):
                add("AEGIS_ACTION_BEFORE_EXPLICIT_MAINTENANCE_ENTRY")
            if not entry.get("ENTRY_ID") or action_event.get("ENTRY_REF") != entry.get("ENTRY_ID"):
                add("AEGIS_ACTION_NOT_BOUND_TO_EXPLICIT_ENTRY")
    aegis_actions = [event for event in events if event.get("KIND") == "ACTION" and event.get("ACTOR_ROLE") == "aegis"]
    if aegis_actions and not maintenance_entries:
        add("AEGIS_ACTION_WITHOUT_EXPLICIT_MAINTENANCE_ENTRY")
    if any(event.get("KIND") == "CHILD_START" and event.get("AGENT") == "aegis" for event in events):
        add("AEGIS_CHILD_LAUNCH_FORBIDDEN")
    if any(action.get("ROLE") == "aegis" for action in actions) and not maintenance_entries:
        add("AEGIS_ACTION_WITHOUT_EXPLICIT_MAINTENANCE_ENTRY")
    if trace.get("CASE_ID") == "L" and not maintenance_entries and computed_counts["aegis"] != 0:
        add("AEGIS_NORMAL_ROUTE_FORBIDDEN")
    if trace.get("CASE_ID") == "F":
        responses = [event for event in events if event.get("KIND") == "OPERATIONAL_RESPONSE"]
        if len(responses) != 1 or responses[0].get("ACTOR_ROLE") != "kael" or responses[0].get("CLASSIFICATION") != "TOOLING_ONLY":
            add("CASE_F_BOUNDED_TOOLING_RESPONSE_MISSING")
        elif responses[0].get("INSTALL_ATTEMPTED") is not False or responses[0].get("PRODUCT_BUG_ESTABLISHED") is not False:
            add("CASE_F_UNAUTHORIZED_INSTALL_OR_PRODUCT_BUG_CLAIM")
    if trace.get("CASE_ID") == "B" and case.get("positive_orin_qualification") != "NOT_ESTABLISHED_BY_PHASE11_CASE_B":
        add("CASE_B_ORIN_POSITIVE_QUALIFICATION_NOT_ESTABLISHED")

    if facts.get("FAST_PROFILE_REQUESTED"):
        proxies = trace.get("OPERATIONAL_PROXIES", {})
        writers = [child for child in children if child.get("AGENT") == "kovan" and child.get("WRITE_PATHS")]
        if len(writers) > 4 or len(writers) != proxies.get("USEFUL_INDEPENDENT_WRITER_COUNT"):
            add("FAST_WRITER_COUNT_EXCEEDS_OR_MISREPORTS_FOUR")
        if proxies.get("ACTUAL_COUNTED_CONCURRENCY") != _simultaneous_children(events):
            add("FAST_CONCURRENCY_PROXY_MISMATCH")
        if trace.get("MAX_SIMULTANEOUS_CHILDREN") > 4:
            add("FAST_CONCURRENCY_EXCEEDS_FOUR")
        if trace.get("DEPENDENCY_ORDER"):
            add("FAST_WRITERS_NOT_INDEPENDENT")
        paths = [path for child in writers for path in child.get("WRITE_PATHS", [])]
        for index, left in enumerate(paths):
            if any(_path_overlaps(left, right) for right in paths[index + 1 :]):
                add("FAST_WRITER_PATHS_OVERLAP")

    measured_concurrency = _simultaneous_children(events)
    if trace.get("MAX_SIMULTANEOUS_CHILDREN") != measured_concurrency:
        add("MAX_SIMULTANEOUS_CHILDREN_NOT_EVENT_DERIVED")
    if measured_concurrency > 4:
        add("CORE_CHILD_CEILING_EXCEEDED")
    if trace.get("OPERATIONAL_PROXIES", {}).get("ACTUAL_COUNTED_CONCURRENCY") != measured_concurrency:
        add("ACTUAL_COUNTED_CONCURRENCY_PROXY_MISMATCH")
    return errors


def _read_marker(path: str, marker: str) -> bool:
    """Read only until the bounded marker is found; never emit canonical prose."""
    target = REPO / path
    try:
        with target.open(encoding="utf-8") as stream:
            for line in stream:
                if marker in line:
                    return True
    except OSError:
        return False
    return False


def run_static_baseline_checks() -> list[str]:
    checks = (
        (".opencode/agents/kael.md", "## Functional Bug Routing Gate — optional Argus", "ARGUS_GATE_MARKER"),
        (".opencode/agents/kael.md", "## Security Routing Gate — optional Talos", "TALOS_GATE_MARKER"),
        (".opencode/agents/kael.md", "## Planning Gate — optional Atlas", "ATLAS_GATE_MARKER"),
        (".opencode/agents/kael.md", "## Optimization Gate — explicit-only Helios", "HELIOS_GATE_MARKER"),
        (".opencode/agents/kael.md", "## Diagnostic Gate", "THALES_GATE_MARKER"),
        ("olympus/policies/routing.md", "Kael is the single ROOT ORCHESTRATOR", "ROOT_OWNER_MARKER"),
        ("olympus/policies/routing.md", "Children never spawn children.", "NO_NESTED_CHILD_MARKER"),
        ("olympus/policies/orchestration.toml", "max_children = 4", "CORE_CHILD_CEILING_MARKER"),
    )
    return [label for path, marker, label in checks if not _read_marker(path, marker)]


def validate_corpus() -> tuple[list[str], dict[str, Any]]:
    cases_doc = load_json(HERE / "cases.json")
    traces_doc = load_json(HERE / "traces.json")
    cases = {case["id"]: case for case in cases_doc["cases"]}
    seen: set[str] = set()
    failures: list[str] = []
    for trace in traces_doc["traces"]:
        trace_id = trace.get("TRACE_ID", "<unnamed>")
        if trace_id in seen:
            failures.append(f"{trace_id}: DUPLICATE_TRACE_ID")
            continue
        seen.add(trace_id)
        case = cases.get(trace.get("CASE_ID"))
        if case is None:
            failures.append(f"{trace_id}: CASE_NOT_IN_MATRIX")
            continue
        if trace_id not in case.get("trace_ids", []):
            failures.append(f"{trace_id}: TRACE_NOT_DECLARED_BY_MATRIX")
        failures.extend(f"{trace_id}: {error}" for error in validate_trace(trace, case))
    for case in cases_doc["cases"]:
        for trace_id in case.get("trace_ids", []):
            if trace_id not in seen:
                failures.append(f"{case['id']}: MISSING_TRACE:{trace_id}")
    return failures, {"cases": cases_doc, "traces": traces_doc}


def validate_case_b_reconciliation(baseline: dict[str, Any]) -> list[str]:
    """Check the separately reported Case B observations without making a native trace."""
    errors: list[str] = []
    add = errors.append
    report = baseline.get("phase11_b2_reconciliation")
    if not isinstance(report, dict):
        return ["CASE_B_RECONCILIATION_MISSING"]

    case_b1 = report.get("case_b1", {})
    if case_b1.get("classification") != "FIXTURE_DEFECT":
        add("CASE_B1_FIXTURE_DEFECT_CLASSIFICATION_MISMATCH")
    if case_b1.get("question_barrier") != "PASS":
        add("CASE_B1_QUESTION_BARRIER_CLASSIFICATION_MISMATCH")
    if case_b1.get("native_root_session_id") is not None or case_b1.get("native_trace_recorded") is not False:
        add("CASE_B1_UNSUPPORTED_NATIVE_TRACE_CLAIM")

    case_b2 = report.get("case_b2", {})
    if case_b2.get("label") != "PHASE11_CASE_B_FRESH_ROOT_2":
        add("CASE_B2_LABEL_MISMATCH")
    root = case_b2.get("root", {})
    if root != {"session_id": CASE_B2_ROOT_SESSION_ID, "agent": "Kael", "outcome": "succeeded"}:
        add("CASE_B2_ROOT_IDENTITY_MISMATCH")
    if case_b2.get("ACTUAL_ROUTE") != CASE_B2_ACTUAL_ROUTE:
        add("CASE_B2_ACTUAL_ROUTE_MISMATCH")

    children = case_b2.get("direct_children", {})
    if not isinstance(children, dict) or set(children) != set(CASE_B2_CHILD_SESSION_IDS):
        add("CASE_B2_DIRECT_CHILD_SET_MISMATCH")
        children = children if isinstance(children, dict) else {}
    child_ids: list[str] = []
    for agent, session_id in CASE_B2_CHILD_SESSION_IDS.items():
        child = children.get(agent, {})
        if child.get("session_id") != session_id:
            add(f"CASE_B2_CHILD_SESSION_ID_MISMATCH:{agent}")
        if child.get("parent_session_id") != CASE_B2_ROOT_SESSION_ID:
            add(f"CASE_B2_CHILD_PARENT_SESSION_MISMATCH:{agent}")
        if child.get("outcome") != "succeeded" or child.get("result_consumed") is not True:
            add(f"CASE_B2_CHILD_COMPLETION_OR_CONSUMPTION_MISMATCH:{agent}")
        child_ids.append(str(child.get("session_id")))
    if len(child_ids) != len(set(child_ids)) or CASE_B2_ROOT_SESSION_ID in child_ids:
        add("CASE_B2_SESSION_IDENTITIES_NOT_UNIQUE")
    if case_b2.get("all_required_children_terminal_and_consumed") is not True:
        add("CASE_B2_COMPLETION_RECONCILIATION_MISMATCH")

    if case_b2.get("classifications") != CASE_B2_CLASSIFICATIONS:
        add("CASE_B2_CLASSIFICATION_SEPARATION_MISMATCH")
    isolation = case_b2.get("isolation", {})
    if isolation.get("execution_repository") != "CANONICAL_QUALIFICATION_REPOSITORY" or isolation.get("separate_disposable_copy") is not False:
        add("CASE_B2_ISOLATION_EVIDENCE_MISMATCH")
    if case_b2.get("acceptance_status") != "PARTIAL":
        add("CASE_B2_ACCEPTANCE_MUST_REMAIN_PARTIAL")
    if report.get("phase11_status") != "PARTIAL":
        add("PHASE11_STATUS_MUST_REMAIN_PARTIAL")

    fixture_work = case_b2.get("fixture_work", {})
    expected_modified = [
        "tests/phase11-integrated-routing/fixtures/feature/domain.py",
        "tests/phase11-integrated-routing/fixtures/feature/presentation.py",
        "tests/phase11-integrated-routing/fixtures/feature/test_feature.py",
    ]
    if fixture_work.get("reported_modified_paths") != expected_modified:
        add("CASE_B2_REPORTED_FIXTURE_PATHS_MISMATCH")
    if fixture_work.get("feature_tests_passed") != 14 or fixture_work.get("feature_tests_total") != 14:
        add("CASE_B2_FEATURE_TEST_RESULT_MISMATCH")
    review = case_b2.get("review", {})
    if (
        review.get("agent") != "Vera"
        or review.get("session_id") != CASE_B2_CHILD_SESSION_IDS["Vera"]
        or review.get("result") != "ACCEPT"
        or review.get("findings") != []
    ):
        add("CASE_B2_FINAL_REVIEW_RECONCILIATION_MISMATCH")

    planning = case_b2.get("planning", {})
    if planning.get("atlas_activated") is not False or planning.get("atlas_routing_defect") is not False:
        add("CASE_B2_ATLAS_CLASSIFICATION_MISMATCH")
    if planning.get("bounded_producer_consumer_justified_planner") is not False:
        add("CASE_B2_PLANNING_JUSTIFICATION_MISMATCH")
    if planning.get("veyra_efficiency") != "ACCEPTABLE" or planning.get("material_redundancy_proven") is not False:
        add("CASE_B2_VEYRA_EFFICIENCY_CLASSIFICATION_MISMATCH")

    friction = case_b2.get("contract_friction", {})
    kovan = friction.get("kovan", {})
    if (
        kovan.get("session_id") != CASE_B2_CHILD_SESSION_IDS["Kovan"]
        or kovan.get("initial_result") != "BLOCKED"
        or kovan.get("blocker") != "task/grant identity mismatch"
        or kovan.get("kael_consumed_original_result") is not True
        or kovan.get("pre_resume_tool_execution") != "NOT_EXECUTED"
        or kovan.get("pre_resume_edits") != 0
        or kovan.get("corrected_only") != "grant identity"
        or kovan.get("resumed_same_session") is not True
        or kovan.get("blind_retry") is not False
        or children.get("Kovan", {}).get("session_id") != kovan.get("session_id")
    ):
        add("CASE_B2_KOVAN_SESSION_RECONCILIATION_MISMATCH")
    vera = friction.get("vera", {})
    if (
        vera.get("session_id") != CASE_B2_CHILD_SESSION_IDS["Vera"]
        or vera.get("initial_parent_delivery") != "INTERRUPTED"
        or vera.get("same_original_session_retained") is not True
        or vera.get("result_reconciliation") != "PASS"
        or vera.get("upstream_correlation_issue_fix_claimed") is not False
        or children.get("Vera", {}).get("session_id") != vera.get("session_id")
    ):
        add("CASE_B2_VERA_SESSION_RECONCILIATION_MISMATCH")
    reconciliation = case_b2.get("result_reconciliation", {})
    if (
        reconciliation.get("classification") != "PASS"
        or reconciliation.get("vera_session_id") != CASE_B2_CHILD_SESSION_IDS["Vera"]
        or reconciliation.get("same_original_session") is not True
        or reconciliation.get("upstream_correlation_issue_fix_claimed") is not False
    ):
        add("CASE_B2_RESULT_RECONCILIATION_MISMATCH")

    unknowns = case_b2.get("unknowns", {})
    for field in ("event_count", "event_order", "concurrency", "consultation_counts", "relative_nox_vera_order"):
        if unknowns.get(field) is not None:
            add(f"CASE_B2_UNKNOWN_METRIC_MUST_REMAIN_NULL:{field}")
    if unknowns.get("native_event_trace_reconstructed") is not False:
        add("CASE_B2_NATIVE_EVENTS_MUST_NOT_BE_RECONSTRUCTED")
    if case_b2.get("runtime_rerun_performed_by_reconciliation") is not False:
        add("CASE_B2_RUNTIME_MUST_NOT_BE_RERUN_BY_RECONCILIATION")

    next_action = report.get("next_action", {})
    if (
        next_action.get("label") != "PHASE11_CASE_B_FRESH_ROOT_3"
        or next_action.get("clean_separate_disposable_copy") is not True
        or next_action.get("new_verified_kael_root") is not True
    ):
        add("CASE_B3_ISOLATED_NEXT_ACTION_MISMATCH")
    return errors


def validate_native_invocation_capture(trace: dict[str, Any], case: dict[str, Any]) -> list[str]:
    """Validate the bounded native invocation capture without synthetic lifecycle assumptions."""
    errors: list[str] = []
    add = errors.append
    missing = [field for field in REQUIRED_TRACE_FIELDS if field not in trace]
    if missing:
        return ["NATIVE_MISSING_REQUIRED_FIELDS:" + ",".join(missing)]

    if trace.get("TRACE_ID") != "B3-NATIVE":
        add("NATIVE_TRACE_ID_MISMATCH")
    if trace.get("CASE_ID") != "B" or case.get("id") != "B":
        add("NATIVE_CASE_ID_MISMATCH")
    if trace.get("REQUEST_CLASS") != case.get("request_class") or trace.get("REQUEST_CLASS") != "COMPLEX_FEATURE":
        add("NATIVE_REQUEST_CLASS_MISMATCH")
    if trace.get("EVIDENCE_CLASS") != "FRESH_ROOT_NATIVE":
        add("NATIVE_EVIDENCE_CLASS_MISMATCH")
    if trace.get("SCENARIO") != "default" or case.get("expected_routes", {}).get("default") != CASE_B3_EXPECTED_ROUTE:
        add("NATIVE_SCENARIO_OR_MATRIX_ROUTE_MISMATCH")
    if trace.get("EXPECTED_ROUTE") != CASE_B3_EXPECTED_ROUTE:
        add("NATIVE_EXPECTED_ROUTE_MISMATCH")
    if trace.get("ROUTE_MODE") != "KAEL_ROOT":
        add("NATIVE_ROUTE_MODE_MISMATCH")
    if trace.get("ROOT_SESSION_ID") != CASE_B3_ROOT_SESSION_ID:
        add("NATIVE_ROOT_SESSION_ID_MISMATCH")
    if trace.get("ROOT_AGENT") != "kael" or trace.get("ROOT_PARENT_SESSION_ID") is not None:
        add("NATIVE_ROOT_IDENTITY_MISMATCH")
    if trace.get("ROOT_TERMINAL_OUTCOME") != "succeeded" or trace.get("FINAL_OUTCOME") != "succeeded":
        add("NATIVE_ROOT_TERMINAL_OUTCOME_MISMATCH")
    if trace.get("ROOT_TERMINAL_MESSAGE_ID") != CASE_B3_TERMINAL_MESSAGE_ID:
        add("NATIVE_ROOT_TERMINAL_MESSAGE_ID_MISMATCH")
    isolation = trace.get("ROOT_ISOLATION", {})
    if (
        not isinstance(isolation, dict)
        or isolation.get("STATUS") != "PASS"
        or isolation.get("SEPARATE_DISPOSABLE_WORKTREE") is not True
        or isolation.get("INITIAL_NOX_SESSION_ID") != CASE_B3_CHILD_SESSIONS[0][2]
        or trace.get("ROOT_DIRECTORY") != CASE_B3_ROOT_DIRECTORY
        or isolation.get("VERIFIED_DIRECTORY") != CASE_B3_ROOT_DIRECTORY
        or isolation.get("INITIAL_HEAD") != CASE_B3_INITIAL_HEAD
        or isolation.get("VERIFIED_HEAD") != CASE_B3_INITIAL_HEAD
        or isolation.get("VERIFICATION_ONLY") is not True
        or isolation.get("WORKTREE_CREATION_CLAIMED") is not False
    ):
        add("NATIVE_FRESH_ROOT_ISOLATION_MISMATCH")
    expected_runtime_validation = {
        "PYTHON_VERSION": "3.11.17",
        "PYTHON_INSTALLATION_SOURCE": "uv",
        "COMMAND": CASE_B3_TEST_COMMAND,
        "RESULT": "PASS",
        "TESTS_PASSED": 13,
        "CONTRACT_COVERAGE": "PASS",
        "SOURCE_INTEGRITY_AFTER_TEST": "PASS",
        "NOX": "PASS",
        "VERA": "ACCEPT",
        "UNRESOLVED_WORK": "NONE",
        "NOTHING_REMAINED_RUNNING": True,
        "HISTORICAL_RUNTIME_EXIT_CODE": None,
    }
    if trace.get("RUNTIME_VALIDATION") != expected_runtime_validation:
        add("NATIVE_RUNTIME_VALIDATION_FACTS_MISMATCH")
    expected_session_reconciliation = {
        "kovan": {
            "NATIVE_SESSION_ID": CASE_B3_CHILD_SESSIONS[2][2],
            "INVOCATION_COUNT": 1,
            "IMPLEMENTATION_RETURN": "PARTIAL_RUNTIME_UNAVAILABLE",
            "FINAL_SESSION_OUTCOME": "succeeded",
            "REPORTED_CHANGED_PATHS": [
                "tests/phase11-integrated-routing/fixtures/feature/domain.py",
                "tests/phase11-integrated-routing/fixtures/feature/presentation.py",
                "tests/phase11-integrated-routing/fixtures/feature/test_scaffold.py",
            ],
            "SAME_ORIGINAL_SESSION": True,
            "BLIND_RETRY": False,
        },
        "vera": {
            "NATIVE_SESSION_ID": CASE_B3_CHILD_SESSIONS[3][2],
            "INVOCATION_COUNT": 2,
            "REVIEW_RETURN": "SUCCESS",
            "REVIEW_FINDINGS": [],
            "TESTS_VERIFIED_BY_REVIEW": False,
            "FOLLOWUP_RETURN": "SUCCESS",
            "FOLLOWUP_SCOPE": "source review",
            "FOLLOWUP_EDITS": 0,
            "SAME_ORIGINAL_SESSION": True,
        },
        "nox": {
            "NATIVE_SESSION_ID": CASE_B3_CHILD_SESSIONS[0][2],
            "INVOCATION_COUNT": 3,
            "INITIAL_ISOLATION": "PASS",
            "VERIFIED_DIRECTORY": CASE_B3_ROOT_DIRECTORY,
            "VERIFIED_HEAD": CASE_B3_INITIAL_HEAD,
            "INITIAL_VALIDATION": "BLOCKED",
            "FINAL_VALIDATION": "PASS",
            "TESTS_PASSED": 13,
            "SAME_ORIGINAL_SESSION": True,
        },
    }
    if trace.get("SESSION_RECONCILIATION") != expected_session_reconciliation:
        add("NATIVE_SAME_SESSION_RECONCILIATION_MISMATCH")

    provenance = trace.get("EVIDENCE_PROVENANCE", {})
    expected_child_ids = [session_id for _, _, session_id in CASE_B3_CHILD_SESSIONS]
    if not isinstance(provenance, dict):
        provenance = {}
    if provenance.get("CLASS") != "FRESH_ROOT_NATIVE":
        add("NATIVE_PROVENANCE_CLASS_MISMATCH")
    if provenance.get("NATIVE_ROOT_SESSION_ID") != CASE_B3_ROOT_SESSION_ID:
        add("NATIVE_ROOT_PROVENANCE_MISMATCH")
    if provenance.get("NATIVE_ROOT_DIRECTORY") != CASE_B3_ROOT_DIRECTORY:
        add("NATIVE_ROOT_DIRECTORY_PROVENANCE_MISMATCH")
    if provenance.get("NATIVE_CHILD_SESSION_IDS") != expected_child_ids:
        add("NATIVE_CHILD_PROVENANCE_MISMATCH")
    if provenance.get("ORDER_BASIS") != "observed":
        add("NATIVE_ORDER_PROVENANCE_MISMATCH")
    if provenance.get("FRESH_ROOT_CONFIRMED") is not True or provenance.get("USER_REPORTED") is not False:
        add("NATIVE_FRESH_ROOT_PROVENANCE_UNCONFIRMED")
    if provenance.get("OBSERVED_AT") is not None:
        add("NATIVE_UNOBSERVED_TIMESTAMP_MUST_REMAIN_NULL")
    if provenance.get("NATIVE_PERMISSION_UI") != "NOT_OBSERVABLE" or provenance.get("NATIVE_PERMISSION_DECISION") != "NOT_OBSERVABLE":
        add("NATIVE_PERMISSION_OBSERVABILITY_MISMATCH")

    children = trace.get("CHILD_SESSIONS")
    if not isinstance(children, list):
        return errors + ["NATIVE_CHILD_SESSIONS_NOT_LIST"]
    if len(children) != len(CASE_B3_CHILD_SESSIONS):
        add("NATIVE_UNIQUE_CHILD_SESSION_COUNT_MISMATCH")
    refs: list[str] = []
    session_ids: list[str] = []
    expected_invocation_counts = {"B3-NOX": 3, "B3-VEYRA": 1, "B3-KOVAN": 1, "B3-VERA": 2}
    for index, (ref, role, session_id) in enumerate(CASE_B3_CHILD_SESSIONS):
        child = children[index] if index < len(children) and isinstance(children[index], dict) else {}
        if child.get("TRACE_REF") != ref or child.get("AGENT") != role:
            add(f"NATIVE_CHILD_ROLE_OR_ORDER_MISMATCH:{ref}")
        if child.get("NATIVE_SESSION_ID") != session_id or not NATIVE_SESSION_ID.fullmatch(str(child.get("NATIVE_SESSION_ID", ""))):
            add(f"NATIVE_CHILD_SESSION_ID_MISMATCH:{ref}")
        if child.get("PARENT_AGENT") != "kael" or child.get("PARENT_SESSION_ID") != CASE_B3_ROOT_SESSION_ID:
            add(f"NATIVE_CHILD_PARENT_MISMATCH:{ref}")
        if child.get("LAUNCH_ORDER") != index + 1:
            add(f"NATIVE_CHILD_LAUNCH_ORDER_MISMATCH:{ref}")
        if child.get("INVOCATION_COUNT") != expected_invocation_counts[ref]:
            add(f"NATIVE_CHILD_INVOCATION_COUNT_MISMATCH:{ref}")
        if child.get("EXECUTION_STATE") != "SUCCEEDED" or child.get("FINAL_OUTCOME") != "succeeded":
            add(f"NATIVE_CHILD_TERMINAL_OUTCOME_MISMATCH:{ref}")
        if child.get("RESULT_ID") is not None:
            add(f"NATIVE_UNOBSERVED_CHILD_RESULT_ID_MUST_REMAIN_NULL:{ref}")
        refs.append(str(child.get("TRACE_REF")))
        session_ids.append(str(child.get("NATIVE_SESSION_ID")))
    if len(refs) != len(set(refs)) or len(session_ids) != len(set(session_ids)) or CASE_B3_ROOT_SESSION_ID in session_ids:
        add("NATIVE_CHILD_SESSION_IDENTITIES_NOT_UNIQUE")

    events = trace.get("EVENTS")
    if not isinstance(events, list):
        return errors + ["NATIVE_EVENTS_NOT_LIST"]
    if len(events) != len(CASE_B3_CALLS) + 1:
        add("NATIVE_INVOCATION_EVENT_COUNT_MISMATCH")
    orders = [event.get("ORDER") if isinstance(event, dict) else None for event in events]
    if orders != list(range(1, len(events) + 1)):
        add("NATIVE_EVENT_ORDER_NOT_STRICTLY_INCREASING")
    if any(not isinstance(event, dict) or event.get("ORDER_BASIS") != "observed" for event in events):
        add("NATIVE_EVENT_ORDER_BASIS_MISMATCH")

    observed_call_ids: list[str] = []
    observed_call_counts = {role: 0 for role in ALL_INVOCABLE_ROLES}
    for index, (ref, role, call_id, message_id, status) in enumerate(CASE_B3_CALLS):
        event = events[index] if index < len(events) and isinstance(events[index], dict) else {}
        expected_session = next((sid for child_ref, _, sid in CASE_B3_CHILD_SESSIONS if child_ref == ref), None)
        if event.get("EVENT_ID") != f"B3-CALL-{index + 1}" or event.get("KIND") != "ROOT_SUBAGENT_RESULT_RETURNED":
            add(f"NATIVE_INVOCATION_EVENT_KIND_OR_ID_MISMATCH:{index + 1}")
        if event.get("ACTOR_ROLE") != "kael" or event.get("TOOL") != "subagent":
            add(f"NATIVE_INVOCATION_CALLER_MISMATCH:{index + 1}")
        if (
            event.get("CHILD_REF") != ref
            or event.get("SESSION_REF") != ref
            or event.get("NATIVE_SESSION_ID") != expected_session
            or event.get("AGENT") != role
        ):
            add(f"NATIVE_INVOCATION_SESSION_OR_ROLE_JOIN_MISMATCH:{index + 1}")
        if event.get("TOOL_CALL_ID") != call_id or event.get("OBSERVED_MESSAGE_ID") != message_id:
            add(f"NATIVE_INVOCATION_ID_MISMATCH:{index + 1}")
        if event.get("RETURN_STATUS") != status:
            add(f"NATIVE_INVOCATION_RESULT_MISMATCH:{index + 1}")
        if not isinstance(event.get("RETURN_SUMMARY"), str) or not event.get("RETURN_SUMMARY", "").strip():
            add(f"NATIVE_INVOCATION_SUMMARY_MISSING:{index + 1}")
        if index == 0 and (
            event.get("RETURN_SUMMARY") != "Verified worktree isolation directory and initial HEAD; no worktree-creation claim."
            or event.get("VERIFIED_DIRECTORY") != CASE_B3_ROOT_DIRECTORY
            or event.get("VERIFIED_HEAD") != CASE_B3_INITIAL_HEAD
            or event.get("VERIFICATION_SCOPE") != "DIRECTORY_AND_HEAD"
            or event.get("WORKTREE_CREATION_CLAIMED") is not False
        ):
            add("NATIVE_ISOLATION_EVENT_NOT_VERIFICATION_ONLY")
        if index == 2 and event.get("REPORTED_CHANGED_PATHS") != expected_session_reconciliation["kovan"]["REPORTED_CHANGED_PATHS"]:
            add("NATIVE_KOVAN_CHANGED_PATHS_MISMATCH")
        if event.get("RESULT_ID") is not None:
            add(f"NATIVE_UNOBSERVED_RESULT_ID_MUST_REMAIN_NULL:{index + 1}")
        observed_call_ids.append(str(event.get("TOOL_CALL_ID")))
        if role in observed_call_counts:
            observed_call_counts[role] += 1
    if len(observed_call_ids) != len(set(observed_call_ids)):
        add("NATIVE_TOOL_CALL_IDS_NOT_UNIQUE")

    final_event = events[-1] if events and isinstance(events[-1], dict) else {}
    if (
        final_event.get("EVENT_ID") != "B3-ROOT-FINAL"
        or final_event.get("KIND") != "ROOT_FINAL_COMPLETION"
        or final_event.get("ACTOR_ROLE") != "kael"
        or final_event.get("ROOT_SESSION_ID") != CASE_B3_ROOT_SESSION_ID
        or final_event.get("MESSAGE_ID") != trace.get("ROOT_TERMINAL_MESSAGE_ID")
        or final_event.get("VALUE") != "succeeded"
    ):
        add("NATIVE_FINAL_COMPLETION_EVENT_MISMATCH")
    if final_event.get("RESULT_ID") is not None:
        add("NATIVE_UNOBSERVED_FINAL_RESULT_ID_MUST_REMAIN_NULL")

    snapshot = trace.get("OBSERVED_TERMINAL_SNAPSHOT", {})
    if not isinstance(snapshot, dict) or (
        snapshot.get("OBSERVATION") != "OBSERVED_NATIVE_ROOT_TERMINAL_MESSAGE"
        or snapshot.get("ROOT_SESSION_ID") != CASE_B3_ROOT_SESSION_ID
        or snapshot.get("MESSAGE_ID") != CASE_B3_TERMINAL_MESSAGE_ID
        or snapshot.get("FACTS") != CASE_B3_TERMINAL_FACTS
        or final_event.get("TERMINAL_FACTS") != snapshot.get("FACTS")
    ):
        add("NATIVE_TERMINAL_SNAPSHOT_MISMATCH")
    snapshot_facts = snapshot.get("FACTS", {}) if isinstance(snapshot, dict) else {}
    runtime = trace.get("RUNTIME_VALIDATION", {})
    routing_detail = trace.get("ROUTING_RESULT_DETAIL", {})
    derived_terminal_facts = {
        "WORKTREE_ISOLATION": isolation.get("STATUS") if isinstance(isolation, dict) else None,
        "PYTHON_RUNTIME": (
            f"Python {runtime.get('PYTHON_VERSION')} installed through {runtime.get('PYTHON_INSTALLATION_SOURCE')}"
            if isinstance(runtime, dict) else None
        ),
        "TEST_COMMAND": runtime.get("COMMAND") if isinstance(runtime, dict) else None,
        "TEST_RESULT": runtime.get("RESULT") if isinstance(runtime, dict) else None,
        "TEST_COUNT": runtime.get("TESTS_PASSED") if isinstance(runtime, dict) else None,
        "CONTRACT_COVERAGE": runtime.get("CONTRACT_COVERAGE") if isinstance(runtime, dict) else None,
        "SOURCE_INTEGRITY_AFTER_TEST": runtime.get("SOURCE_INTEGRITY_AFTER_TEST") if isinstance(runtime, dict) else None,
        "NOX": runtime.get("NOX") if isinstance(runtime, dict) else None,
        "VERA": runtime.get("VERA") if isinstance(runtime, dict) else None,
        "UNRESOLVED_WORK": runtime.get("UNRESOLVED_WORK") if isinstance(runtime, dict) else None,
        "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED": (
            "YES" if final_event.get("REQUIRED_CHILD_SESSIONS_TERMINAL_AND_CONSUMED") is True else "NO"
        ),
        "CASE_B_FRESH_ROOT_3": routing_detail.get("CASE_B_FRESH_ROOT_3") if isinstance(routing_detail, dict) else None,
        "NOTHING_RUNNING": runtime.get("NOTHING_REMAINED_RUNNING") if isinstance(runtime, dict) else None,
    }
    if snapshot_facts != derived_terminal_facts:
        add("NATIVE_TERMINAL_FACTS_DO_NOT_MATCH_VALIDATION_RECORDS")

    observed_unique_counts = {role: 0 for role in ALL_INVOCABLE_ROLES}
    for child in children:
        role = child.get("AGENT")
        if role in observed_unique_counts:
            observed_unique_counts[role] += 1
    if trace.get("CONSULTATION_COUNTS") != observed_call_counts:
        add("NATIVE_INVOCATION_COUNTS_MISMATCH")
    if trace.get("UNIQUE_CHILD_SESSION_COUNTS") != observed_unique_counts:
        add("NATIVE_UNIQUE_CHILD_COUNTS_MISMATCH")
    if trace.get("CONSULTATION_COUNT_BASIS") != "Counts of distinct completed root subagent invocation results by target role; not unique child sessions and not inferred reasoner consultation events.":
        add("NATIVE_INVOCATION_COUNT_BASIS_MISMATCH")
    if trace.get("MAX_SIMULTANEOUS_CHILDREN") is not None:
        add("NATIVE_UNKNOWN_CONCURRENCY_MUST_REMAIN_NULL")

    negative = trace.get("NEGATIVE_CONTROLS", {})
    negative_roles = ("orin", "atlas", "argus", "talos", "thales", "helios", "aegis")
    for role in negative_roles:
        actual = negative.get(role, {}) if isinstance(negative, dict) else {}
        if actual != {"INVOCATIONS": 0, "UNIQUE_CHILD_SESSIONS": 0}:
            add(f"NATIVE_NEGATIVE_CONTROL_MISMATCH:{role}")

    purity = trace.get("ROLE_PURITY", {})
    expected_tool_classes = {
        "kael": ["subagent", "read"],
        "nox": ["shell", "glob", "read"],
        "veyra": ["glob", "read"],
        "kovan": ["read", "shell", "patch"],
        "vera": ["glob", "read"],
    }
    if not isinstance(purity, dict) or (
        purity.get("STATUS") != "PASS"
        or purity.get("ROOT_AGENT") != "kael"
        or purity.get("ALL_CHILDREN_DIRECT") is not True
        or purity.get("NESTED_DELEGATION_OBSERVED") is not False
        or purity.get("REVIEWER_EDITS_OBSERVED") is not False
        or purity.get("ROOT_SOURCE_WRITES_OBSERVED") is not False
        or purity.get("VIOLATIONS") != []
        or purity.get("TOOL_CLASSES_BY_ROLE") != expected_tool_classes
    ):
        add("NATIVE_ROLE_PURITY_EVIDENCE_MISMATCH")

    route = ["kael", *(child.get("AGENT") for child in children)]
    if trace.get("ACTUAL_ROUTE") != route or trace.get("ACTUAL_ROUTE") != CASE_B3_ACTUAL_ROUTE:
        add("NATIVE_ACTUAL_ROUTE_DOES_NOT_MATCH_UNIQUE_SESSION_LAUNCH_ORDER")
    route_reconciliation = trace.get("ROUTE_RECONCILIATION", {})
    if not isinstance(route_reconciliation, dict) or (
        route_reconciliation.get("EXPECTED_SEMANTIC_ROUTE") != CASE_B3_EXPECTED_ROUTE
        or route_reconciliation.get("OBSERVED_UNIQUE_CHILD_SESSION_LAUNCH_ORDER") != CASE_B3_ACTUAL_ROUTE
        or route_reconciliation.get("CLASSIFICATION") != "JUSTIFIED_PREREQUISITE"
        or "initial Nox worktree-isolation prerequisite" not in route_reconciliation.get("JUSTIFICATION", "")
    ):
        add("NATIVE_ROUTE_DIFFERENCE_NOT_JUSTIFIED")

    event_orders = {event.get("EVENT_ID"): event.get("ORDER") for event in events if isinstance(event, dict)}
    dependency_edges = trace.get("DEPENDENCY_ORDER")
    if not isinstance(dependency_edges, list):
        dependency_edges = []
    observed_edges = {(edge.get("BEFORE"), edge.get("AFTER")) for edge in dependency_edges if isinstance(edge, dict)}
    if observed_edges != CASE_B3_DEPENDENCY_EDGES or len(dependency_edges) != len(CASE_B3_DEPENDENCY_EDGES):
        add("NATIVE_DEPENDENCY_EDGES_MISMATCH")
    for edge in dependency_edges:
        if not isinstance(edge, dict):
            add("NATIVE_DEPENDENCY_EDGE_MALFORMED")
            continue
        before = event_orders.get(edge.get("BEFORE"))
        after = event_orders.get(edge.get("AFTER"))
        if before is None or after is None or before >= after or not edge.get("RELATION"):
            add("NATIVE_DEPENDENCY_ORDER_NOT_OBSERVED")

    result = trace.get("RESULT_FIDELITY", {})
    if not isinstance(result, dict) or (
        result.get("EXPECTED_RESULT") != "succeeded"
        or result.get("EXPECTED_RESULT_SOURCE") != "task acceptance context"
        or result.get("OBSERVED_RESULT") != "succeeded"
        or result.get("OBSERVED_RESULT_SOURCE") != "native root terminal metadata"
        or result.get("MATCHES") is not True
        or result.get("UNKNOWN") is not False
        or result.get("OBSERVED_TERMINAL_MESSAGE_ID") != CASE_B3_TERMINAL_MESSAGE_ID
        or result.get("OBSERVED_TERMINAL_FACTS_MATCH") is not True
    ):
        add("NATIVE_RESULT_FIDELITY_MISMATCH")
    completion = trace.get("COMPLETION_GATE", {})
    required_completion = {
        "PENDING_CHILD_COUNT": 0,
        "UNCONSUMED_RESULT_COUNT": 0,
        "UNKNOWN_EXECUTION_COUNT": 0,
        "EXACT_ONCE": None,
        "QUESTION_BARRIER_SATISFIED": True,
        "ROOT_COMPLETION_STATEMENT_OBSERVED": True,
        "REQUIRED_CHILD_SESSIONS_TERMINAL_AND_CONSUMED": True,
        "SEVEN_DISTINCT_TOOL_CALL_RETURNS_OBSERVED_ONCE": True,
        "SESSION_LIFETIME_EXACT_ONCE": None,
        "CONSUMPTION_TIMING": None,
    }
    if not isinstance(completion, dict) or any(completion.get(key) != value for key, value in required_completion.items()):
        add("NATIVE_COMPLETION_GATE_MISMATCH")
    if (
        final_event.get("PENDING_CHILD_COUNT") != 0
        or final_event.get("UNCONSUMED_RESULT_COUNT") != 0
        or final_event.get("UNKNOWN_EXECUTION_COUNT") != 0
        or final_event.get("REQUIRED_CHILD_SESSIONS_TERMINAL_AND_CONSUMED") is not True
    ):
        add("NATIVE_FINAL_COMPLETION_FACTS_MISMATCH")
    if trace.get("USER_QUESTION_COUNT") != 0:
        add("NATIVE_USER_QUESTION_COUNT_MISMATCH")

    gate_facts = trace.get("GATE_FACTS", {})
    expected_gate_facts = {
        "EXPLICIT_OPTIMIZATION_INTENT": False,
        "EXPLICIT_PLANNING_INTENT": False,
        "COMPLEX_FEATURE": True,
        "OBVIOUS_FUNCTIONAL_CAUSE": None,
        "NONTRIVIAL_FUNCTIONAL_CAUSE": None,
        "SECURITY_BOUNDARY": None,
        "OPERATIONAL_TOOLING_FAILURE": None,
        "HIGH_UNCERTAINTY_AFTER_BOUNDED_DIAGNOSIS": None,
        "THIRD_PARTY_BUG": None,
        "FAST_PROFILE_REQUESTED": False,
        "NORMAL_PROFILE_REQUESTED": None,
        "MAINTENANCE_ENTRY_EXPLICIT": False,
    }
    if gate_facts != expected_gate_facts:
        add("NATIVE_GATE_FACTS_MISMATCH")

    proxies = trace.get("OPERATIONAL_PROXIES", {})
    if not isinstance(proxies, dict) or (
        proxies.get("MAX_SIMULTANEOUS_CHILDREN") is not None
        or proxies.get("ACTUAL_COUNTED_CONCURRENCY") is not None
        or proxies.get("WALL_CLOCK_MS") is not None
        or proxies.get("MEASURED") is not False
        or proxies.get("EFFICIENCY_CLASSIFICATION") != "ACCEPTABLE"
    ):
        add("NATIVE_OPERATIONAL_PROXIES_MISMATCH")
    if trace.get("NATIVE_CAPTURE_MODEL") != "Invocation-level root subagent call results joined to unique direct child session records; intentionally not the synthetic one-lifecycle-per-session event model.":
        add("NATIVE_CAPTURE_MODEL_UNDOCUMENTED")
    if not isinstance(trace.get("NOTES"), str) or not trace.get("NOTES", "").strip():
        add("NATIVE_NOTES_MISSING")
    return errors


def validate_phase11_b3_reconciliation(
    baseline: dict[str, Any], cases_doc: dict[str, Any], trace: dict[str, Any]
) -> list[str]:
    """Reconcile B3 while preserving prior B1/B2 and guided-report classifications."""
    errors = validate_case_b_reconciliation(baseline)
    case_b = next((case for case in cases_doc.get("cases", []) if case.get("id") == "B"), {})
    errors.extend(validate_native_invocation_capture(trace, case_b))
    report = baseline.get("phase11_b3_reconciliation")
    if not isinstance(report, dict):
        return errors + ["CASE_B3_RECONCILIATION_MISSING"]

    expected_classifications = {
        "CASE_B_FRESH_ROOT_3": "PASS",
        "CASE_B_FRESH_ROOT_ACCEPTANCE": "PASS",
        "ISOLATION": "PASS",
        "ROUTING": "PASS",
        "ROLE_PURITY": "PASS",
        "NEGATIVE_CONTROLS": "PASS",
        "COMPLETION_OWNERSHIP": "PASS",
        "RESULT_FIDELITY": "PASS",
        "EFFICIENCY": "ACCEPTABLE",
    }
    if report.get("label") != "PHASE11_CASE_B_FRESH_ROOT_3":
        errors.append("CASE_B3_LABEL_MISMATCH")
    if report.get("evidence_artifact") != "tests/phase11-integrated-routing/case-b3.native-trace.json":
        errors.append("CASE_B3_EVIDENCE_ARTIFACT_LINK_MISMATCH")
    if report.get("root_session_id") != CASE_B3_ROOT_SESSION_ID or report.get("root_terminal_outcome") != "succeeded":
        errors.append("CASE_B3_ROOT_RECONCILIATION_MISMATCH")
    if report.get("root_directory") != CASE_B3_ROOT_DIRECTORY:
        errors.append("CASE_B3_ROOT_DIRECTORY_MISMATCH")
    if report.get("classifications") != expected_classifications:
        errors.append("CASE_B3_CLASSIFICATION_MISMATCH")
    isolation = report.get("isolation", {})
    if not isinstance(isolation, dict) or (
        isolation.get("worktree_isolation") != "PASS"
        or isolation.get("separate_disposable_copy") is not True
        or isolation.get("verified_directory") != CASE_B3_ROOT_DIRECTORY
        or isolation.get("initial_head") != CASE_B3_INITIAL_HEAD
        or isolation.get("verified_head") != CASE_B3_INITIAL_HEAD
        or isolation.get("verification_only") is not True
        or isolation.get("worktree_creation_claimed") is not False
    ):
        errors.append("CASE_B3_ISOLATION_RECONCILIATION_MISMATCH")
    expected_baseline_snapshot = {
        "source": "OBSERVED_NATIVE_ROOT_TERMINAL_MESSAGE",
        "root_session_id": CASE_B3_ROOT_SESSION_ID,
        "message_id": CASE_B3_TERMINAL_MESSAGE_ID,
        "facts": CASE_B3_TERMINAL_FACTS,
    }
    if report.get("observed_terminal_snapshot") != expected_baseline_snapshot:
        errors.append("CASE_B3_BASELINE_TERMINAL_SNAPSHOT_MISMATCH")
    if report.get("child_sessions") != [
        {"role": role, "session_id": session_id, "launch_order": index + 1, "invocation_count": count}
        for index, ((_, role, session_id), count) in enumerate(zip(CASE_B3_CHILD_SESSIONS, (3, 1, 1, 2)))
    ]:
        errors.append("CASE_B3_CHILD_SESSION_RECONCILIATION_MISMATCH")
    if report.get("phase11_status") != "PARTIAL" or report.get("acceptance_status") != "PASS":
        errors.append("CASE_B3_PHASE_OR_ACCEPTANCE_STATUS_MISMATCH")
    if report.get("pending_fresh_root_labels") != CASE_B3_PENDING_LABELS:
        errors.append("CASE_B3_PENDING_LABELS_MISMATCH")
    if report.get("runtime_rerun_performed_by_reconciliation") is not False:
        errors.append("CASE_B3_RECONCILIATION_MUST_NOT_RERUN_CASE")
    expected_reported_paths = [
        "tests/phase11-integrated-routing/fixtures/feature/domain.py",
        "tests/phase11-integrated-routing/fixtures/feature/presentation.py",
        "tests/phase11-integrated-routing/fixtures/feature/test_scaffold.py",
    ]
    expected_runtime_summary = {
        "python": "3.11.17",
        "python_installation_source": "uv",
        "command": CASE_B3_TEST_COMMAND,
        "result": "PASS",
        "tests_passed": 13,
        "contract_coverage": "PASS",
        "source_integrity_after_test": "PASS",
        "historical_runtime_exit_code": None,
        "nox": "PASS",
        "vera": "ACCEPT",
        "nothing_remained_running": True,
        "unresolved_work": "NONE",
    }
    if report.get("runtime_validation") != expected_runtime_summary:
        errors.append("CASE_B3_RUNTIME_VALIDATION_RECONCILIATION_MISMATCH")

    current = baseline.get("live_qualification", {})
    if not isinstance(current, dict) or (
        current.get("pending_labels") != CURRENT_PHASE11_PENDING_LABELS
        or current.get("fresh_root_native") != "B3_PASS; C_PASS; D_PASS; E,F,G,H,K_PENDING"
        or current.get("native_results_claimed") is not True
    ):
        errors.append("CURRENT_PHASE11_PENDING_STATE_MISMATCH")

    action_rows = [
        action for action in cases_doc.get("fresh_root_actions", [])
        if action.get("case_id") == "B" and action.get("label") == "PHASE11_CASE_B_FRESH_ROOT_3"
    ]
    if len(action_rows) != 1 or any(
        action_rows[0].get(key) != value
        for key, value in {
            "status": "PASS",
            "evidence_class": "FRESH_ROOT_NATIVE",
            "evidence_artifact": "case-b3.native-trace.json",
        }.items()
    ):
        errors.append("CASE_B3_MATRIX_EVIDENCE_LINK_MISMATCH")

    reconciliation = report.get("same_original_session_reconciliation", {})
    expected_sessions = {
        "kovan": {
            "session_id": CASE_B3_CHILD_SESSIONS[2][2],
            "invocation_count": 1,
            "implementation_result": "PARTIAL_RUNTIME_UNAVAILABLE",
            "final_session_outcome": "succeeded",
            "reported_changed_paths": expected_reported_paths,
            "same_original_session": True,
            "blind_retry": False,
        },
        "vera": {
            "session_id": CASE_B3_CHILD_SESSIONS[3][2],
            "invocation_count": 2,
            "review_result": "SUCCESS",
            "followup_result": "SUCCESS",
            "tests_verified_by_review": False,
            "same_original_session": True,
            "review_findings": [],
            "followup_edits": 0,
        },
        "nox": {
            "session_id": CASE_B3_CHILD_SESSIONS[0][2],
            "invocation_count": 3,
            "initial_isolation": "PASS",
            "verified_directory": CASE_B3_ROOT_DIRECTORY,
            "verified_head": CASE_B3_INITIAL_HEAD,
            "initial_validation": "BLOCKED",
            "final_validation": "PASS",
            "same_original_session": True,
            "tests_passed": 13,
        },
    }
    if reconciliation != expected_sessions:
        errors.append("CASE_B3_SAME_SESSION_RECONCILIATION_MISMATCH")

    # The earlier recovery observations remain guided/user-reported, not native B3 evidence.
    recovered = baseline.get("recovered_user_observations", {}).get("case_observations", {})
    expected_recovered = {
        "A": ("PASS", "GUIDED_CURRENT_SESSION"),
        "I": ("PARTIAL", "GUIDED_CURRENT_SESSION"),
        "J": ("PASS", "GUIDED_CURRENT_SESSION"),
        "L_negative_automatic_aegis_control": ("PASS", None),
    }
    for case_id, (status, mode) in expected_recovered.items():
        observation = recovered.get(case_id, {})
        if observation.get("reported_status") != status or observation.get("reported_mode") != mode:
            errors.append(f"RECOVERED_HISTORY_PROMOTED_OR_CHANGED:{case_id}")
        if observation.get("native_trace_in_scoped_corpus") is not False:
            errors.append(f"RECOVERED_HISTORY_NATIVE_TRACE_OVERCLAIM:{case_id}")
    return errors


def _case_c_counts() -> dict[str, int]:
    return {role: int(role in {"nox", "kovan"}) for role in ALL_INVOCABLE_ROLES}


def _case_c_unique_session_counts() -> dict[str, int]:
    return {role: int(role in {"nox", "kovan"}) for role in ALL_INVOCABLE_ROLES}


def validate_native_case_c_capture(trace: dict[str, Any], case: dict[str, Any]) -> list[str]:
    """Validate Case C's observed call-level capture without synthetic child lifecycles."""
    errors: list[str] = []
    add = errors.append
    missing = [field for field in REQUIRED_TRACE_FIELDS if field not in trace]
    if missing:
        return ["NATIVE_C_MISSING_REQUIRED_FIELDS:" + ",".join(missing)]

    if trace.get("TRACE_ID") != "C-NATIVE":
        add("NATIVE_C_TRACE_ID_MISMATCH")
    if trace.get("CASE_ID") != "C" or case.get("id") != "C":
        add("NATIVE_C_CASE_ID_MISMATCH")
    if trace.get("REQUEST_CLASS") != case.get("request_class") or trace.get("REQUEST_CLASS") != "OBVIOUS_FUNCTIONAL_BUG":
        add("NATIVE_C_REQUEST_CLASS_MISMATCH")
    if trace.get("EVIDENCE_CLASS") != "FRESH_ROOT_NATIVE":
        add("NATIVE_C_EVIDENCE_CLASS_MISMATCH")
    if trace.get("SCENARIO") != "default" or case.get("expected_routes", {}).get("default") != CASE_C_EXPECTED_ROUTE:
        add("NATIVE_C_SCENARIO_OR_MATRIX_ROUTE_MISMATCH")
    if trace.get("EXPECTED_ROUTE") != CASE_C_EXPECTED_ROUTE:
        add("NATIVE_C_EXPECTED_PRODUCT_ROUTE_MISMATCH")
    if trace.get("ACTUAL_ROUTE") != CASE_C_ACTUAL_ROUTE:
        add("NATIVE_C_ACTUAL_SESSION_FAMILY_MISMATCH")
    if trace.get("ROUTE_MODE") != "KAEL_ROOT":
        add("NATIVE_C_ROUTE_MODE_MISMATCH")
    if (
        trace.get("ROOT_SESSION_ID") != CASE_C_ROOT_SESSION_ID
        or trace.get("ROOT_AGENT") != "kael"
        or trace.get("ROOT_PARENT_SESSION_ID") is not None
        or trace.get("ROOT_DIRECTORY") != CASE_C_ROOT_DIRECTORY
        or trace.get("ROOT_TITLE") != "PHASE11_CASE_C fresh-root cart contract qualification"
    ):
        add("NATIVE_C_ROOT_IDENTITY_MISMATCH")
    if (
        trace.get("ROOT_TERMINAL_OUTCOME") != "succeeded"
        or trace.get("FINAL_OUTCOME") != "succeeded"
        or trace.get("ROOT_TERMINAL_MESSAGE_ID") != CASE_C_ROOT_TERMINAL_MESSAGE_ID
    ):
        add("NATIVE_C_ROOT_TERMINAL_MISMATCH")

    expected_isolation = {
        "STATUS": "PASS",
        "SEPARATE_DISPOSABLE_WORKTREE": True,
        "EXECUTION_REPOSITORY": "SEPARATE_DISPOSABLE_COPY",
        "VERIFIED_DIRECTORY": CASE_C_ROOT_DIRECTORY,
        "INITIAL_HEAD": CASE_C_ROOT_HEAD,
        "VERIFIED_HEAD": CASE_C_ROOT_HEAD,
        "CANONICAL_REPOSITORY_HEAD": CASE_C_ROOT_HEAD,
        "VERIFICATION_ONLY": True,
        "WORKTREE_CREATION_CLAIMED": False,
        "INITIAL_NOX_SESSION_ID": CASE_C_CHILD_SESSIONS[0]["NATIVE_SESSION_ID"],
        "ISOLATION_TOOL_CALL_ID": CASE_C_CALLS[0]["TOOL_CALL_ID"],
        "ISOLATION_PARENT_MESSAGE_ID": CASE_C_CALLS[0]["PARENT_MESSAGE_ID"],
        "ISOLATION_TERMINAL_MESSAGE_ID": CASE_C_CALLS[0]["TERMINAL_MESSAGE_ID"],
        "HISTORICAL_GIT_CHECK_EXIT_CODE": None,
    }
    if trace.get("ROOT_ISOLATION") != expected_isolation:
        add("NATIVE_C_FRESH_ROOT_ISOLATION_MISMATCH")

    provenance = trace.get("EVIDENCE_PROVENANCE", {})
    expected_child_ids = [child["NATIVE_SESSION_ID"] for child in CASE_C_CHILD_SESSIONS]
    if not isinstance(provenance, dict) or (
        provenance.get("CLASS") != "FRESH_ROOT_NATIVE"
        or provenance.get("SOURCE")
        != "Verified native OpenCode V2 read-only API exports/history and session messages collected by Nox; this corpus writer made no API calls, accessed no Case C worktree, and did not rerun the case."
        or provenance.get("NATIVE_ROOT_SESSION_ID") != CASE_C_ROOT_SESSION_ID
        or provenance.get("NATIVE_ROOT_DIRECTORY") != CASE_C_ROOT_DIRECTORY
        or provenance.get("NATIVE_CHILD_SESSION_IDS") != expected_child_ids
        or provenance.get("ORDER_BASIS") != "observed"
        or provenance.get("OBSERVED_AT") is not None
        or provenance.get("USER_REPORTED") is not False
        or provenance.get("FRESH_ROOT_CONFIRMED") is not True
        or provenance.get("NATIVE_PERMISSION_UI") != "NOT_OBSERVABLE"
        or provenance.get("NATIVE_PERMISSION_DECISION") != "NOT_OBSERVABLE"
    ):
        add("NATIVE_C_PROVENANCE_MISMATCH")

    children = trace.get("CHILD_SESSIONS")
    if not isinstance(children, list):
        return errors + ["NATIVE_C_CHILD_SESSIONS_NOT_LIST"]
    if len(children) != len(CASE_C_CHILD_SESSIONS):
        add("NATIVE_C_CHILD_SESSION_SET_MISMATCH")
    for index, expected in enumerate(CASE_C_CHILD_SESSIONS):
        child = children[index] if index < len(children) and isinstance(children[index], dict) else {}
        ref = expected["TRACE_REF"]
        if child.get("TRACE_REF") != ref or child.get("AGENT") != expected["AGENT"]:
            add(f"NATIVE_C_CHILD_ROLE_OR_ORDER_MISMATCH:{ref}")
        if child.get("NATIVE_SESSION_ID") != expected["NATIVE_SESSION_ID"] or not NATIVE_SESSION_ID.fullmatch(str(child.get("NATIVE_SESSION_ID", ""))):
            add(f"NATIVE_C_CHILD_SESSION_ID_MISMATCH:{ref}")
        if child.get("PARENT_AGENT") != "kael" or child.get("PARENT_SESSION_ID") != CASE_C_ROOT_SESSION_ID:
            add(f"NATIVE_C_CHILD_PARENT_MISMATCH:{ref}")
        for key in (
            "LAUNCH_ORDER", "INVOCATION_COUNT", "EXECUTION_STATE", "FINAL_OUTCOME", "RESULT_ID",
            "PURPOSE", "DIRECTORY", "PARENT_MESSAGE_ID", "INVOCATION_TOOL_CALL_ID",
            "TERMINAL_MESSAGE_ID", "CALL_CREATED_AT_EPOCH_MS",
        ):
            if child.get(key) != expected[key]:
                add(f"NATIVE_C_CHILD_RECONCILIATION_MISMATCH:{ref}:{key}")
    child_ids = [child.get("NATIVE_SESSION_ID") for child in children if isinstance(child, dict)]
    if len(child_ids) != len(set(child_ids)) or CASE_C_ROOT_SESSION_ID in child_ids:
        add("NATIVE_C_CHILD_IDENTITIES_NOT_UNIQUE")

    events = trace.get("EVENTS")
    if not isinstance(events, list):
        return errors + ["NATIVE_C_EVENTS_NOT_LIST"]
    if any(not isinstance(event, dict) or event.get("ORDER_BASIS") != "observed" for event in events):
        add("NATIVE_C_EVENT_ORDER_BASIS_MISMATCH")
    orders = [event.get("ORDER") if isinstance(event, dict) else None for event in events]
    if orders != list(range(1, len(events) + 1)):
        add("NATIVE_C_EVENT_ORDER_NOT_STRICTLY_INCREASING")
    if len(events) != 5:
        add("NATIVE_C_EVENT_COUNT_MISMATCH")

    expected_call_events = [
        ("C-CALL-1", "ROOT_SUBAGENT_CALL_CREATED", CASE_C_CALLS[0], 1),
        ("C-CALL-1-RETURN", "ROOT_SUBAGENT_RESULT_RETURNED", CASE_C_CALLS[0], 2),
        ("C-CALL-2", "ROOT_SUBAGENT_CALL_CREATED", CASE_C_CALLS[1], 3),
        ("C-CALL-2-RETURN", "ROOT_SUBAGENT_RESULT_RETURNED", CASE_C_CALLS[1], 4),
    ]
    for event_id, kind, expected, index in expected_call_events:
        event = events[index - 1] if len(events) >= index and isinstance(events[index - 1], dict) else {}
        if event.get("EVENT_ID") != event_id or event.get("KIND") != kind:
            add(f"NATIVE_C_INVOCATION_EVENT_KIND_OR_ORDER_MISMATCH:{index}")
        if event.get("ACTOR_ROLE") != "kael" or event.get("TOOL") != "subagent":
            add(f"NATIVE_C_INVOCATION_PARENT_OR_ROLE_MISMATCH:{index}")
        if (
            event.get("CHILD_REF") != expected["TRACE_REF"]
            or event.get("SESSION_REF") != expected["TRACE_REF"]
            or event.get("NATIVE_SESSION_ID") != CASE_C_CHILD_SESSIONS[(index - 1) // 2]["NATIVE_SESSION_ID"]
            or event.get("AGENT") != expected["AGENT"]
            or event.get("TOOL_CALL_ID") != expected["TOOL_CALL_ID"]
            or event.get("PARENT_MESSAGE_ID") != expected["PARENT_MESSAGE_ID"]
        ):
            add(f"NATIVE_C_INVOCATION_IDENTITY_OR_PARENT_MISMATCH:{index}")
        is_return = kind == "ROOT_SUBAGENT_RESULT_RETURNED"
        if is_return:
            if event.get("OBSERVED_MESSAGE_ID") != expected["TERMINAL_MESSAGE_ID"] or event.get("RETURN_STATUS") != "SUCCESS":
                add(f"NATIVE_C_INVOCATION_TERMINAL_MISMATCH:{index}")
        elif event.get("OBSERVED_MESSAGE_ID") is not None or event.get("RETURN_STATUS") is not None:
            add(f"NATIVE_C_CALL_CREATION_HAS_RETURN_FACTS:{index}")
        for field in ("CALL_CREATED_AT_EPOCH_MS", "CALL_COMPLETED_AT_EPOCH_MS"):
            expected_value = expected.get(field) if (field == "CALL_CREATED_AT_EPOCH_MS" and not is_return) or (field == "CALL_COMPLETED_AT_EPOCH_MS" and is_return) else None
            if event.get(field) != expected_value:
                add(f"NATIVE_C_INVOCATION_TIMESTAMP_MISMATCH:{index}:{field}")
        if event.get("RESULT_ID") is not None:
            add(f"NATIVE_C_UNOBSERVED_RESULT_ID_MUST_REMAIN_NULL:{index}")

    final_event = events[4] if len(events) >= 5 and isinstance(events[4], dict) else {}
    if (
        final_event.get("EVENT_ID") != "C-ROOT-FINAL"
        or final_event.get("KIND") != "ROOT_FINAL_COMPLETION"
        or final_event.get("ACTOR_ROLE") != "kael"
        or final_event.get("ROOT_SESSION_ID") != CASE_C_ROOT_SESSION_ID
        or final_event.get("MESSAGE_ID") != CASE_C_ROOT_TERMINAL_MESSAGE_ID
        or final_event.get("VALUE") != "succeeded"
    ):
        add("NATIVE_C_FINAL_COMPLETION_EVENT_MISMATCH")
    if final_event.get("RESULT_ID") is not None:
        add("NATIVE_C_UNOBSERVED_FINAL_RESULT_ID_MUST_REMAIN_NULL")
    if final_event.get("TERMINAL_FACTS") != CASE_C_TERMINAL_FACTS:
        add("NATIVE_C_ROOT_TERMINAL_FACTS_MISMATCH")

    root_snapshot = trace.get("OBSERVED_TERMINAL_SNAPSHOT", {})
    if not isinstance(root_snapshot, dict) or (
        root_snapshot.get("OBSERVATION") != "OBSERVED_NATIVE_ROOT_TERMINAL_MESSAGE"
        or root_snapshot.get("ROOT_SESSION_ID") != CASE_C_ROOT_SESSION_ID
        or root_snapshot.get("MESSAGE_ID") != CASE_C_ROOT_TERMINAL_MESSAGE_ID
        or root_snapshot.get("FACTS") != CASE_C_TERMINAL_FACTS
        or final_event.get("TERMINAL_FACTS") != root_snapshot.get("FACTS")
    ):
        add("NATIVE_C_TERMINAL_SNAPSHOT_MISMATCH")

    created_events = [event for event in events if isinstance(event, dict) and event.get("KIND") == "ROOT_SUBAGENT_CALL_CREATED"]
    returned_events = [event for event in events if isinstance(event, dict) and event.get("KIND") == "ROOT_SUBAGENT_RESULT_RETURNED"]
    route = ["kael", *(event.get("AGENT") for event in created_events)]
    if route != CASE_C_ACTUAL_ROUTE or trace.get("ACTUAL_ROUTE") != route:
        add("NATIVE_C_ACTUAL_ROUTE_NOT_DERIVED_FROM_OBSERVED_LAUNCH_ORDER")
    expected_counts = _case_c_counts()
    observed_counts = {role: 0 for role in ALL_INVOCABLE_ROLES}
    for event in returned_events:
        if event.get("AGENT") in observed_counts:
            observed_counts[event["AGENT"]] += 1
    if trace.get("CONSULTATION_COUNTS") != expected_counts or observed_counts != expected_counts:
        add("NATIVE_C_INVOCATION_COUNTS_MISMATCH")
    if trace.get("UNIQUE_CHILD_SESSION_COUNTS") != _case_c_unique_session_counts():
        add("NATIVE_C_UNIQUE_CHILD_SESSION_COUNTS_MISMATCH")
    if trace.get("CONSULTATION_COUNT_BASIS") != "Counts of distinct completed root subagent invocation results by target role; not unique child sessions and not inferred reasoner consultation events.":
        add("NATIVE_C_INVOCATION_COUNT_BASIS_MISMATCH")

    simultaneous = 0
    maximum_simultaneous = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("KIND") == "ROOT_SUBAGENT_CALL_CREATED":
            simultaneous += 1
            maximum_simultaneous = max(maximum_simultaneous, simultaneous)
        elif event.get("KIND") == "ROOT_SUBAGENT_RESULT_RETURNED":
            simultaneous = max(0, simultaneous - 1)
    if trace.get("MAX_SIMULTANEOUS_CHILDREN") != 1 or maximum_simultaneous != 1:
        add("NATIVE_C_MAX_SIMULTANEOUS_CHILDREN_MISMATCH")
    if trace.get("DEPENDENCY_ORDER") != [
        {
            "BEFORE": "C-CALL-1-RETURN",
            "AFTER": "C-CALL-2",
            "RELATION": "Nox isolation verification completed before Kovan's localized product correction was invoked.",
        }
    ] or not (
        len(events) >= 3
        and events[1].get("ORDER", 0) < events[2].get("ORDER", 0)
    ):
        add("NATIVE_C_ISOLATION_PREREQUISITE_ORDER_MISMATCH")

    route_reconciliation = trace.get("ROUTE_RECONCILIATION", {})
    if not isinstance(route_reconciliation, dict) or (
        route_reconciliation.get("EXPECTED_PRODUCT_ROUTE") != CASE_C_EXPECTED_ROUTE
        or route_reconciliation.get("OBSERVED_UNIQUE_CHILD_SESSION_LAUNCH_ORDER") != CASE_C_ACTUAL_ROUTE
        or route_reconciliation.get("CLASSIFICATION") != "JUSTIFIED_QUALIFICATION_PREREQUISITE"
        or "not a product diagnosis" not in route_reconciliation.get("JUSTIFICATION", "")
    ):
        add("NATIVE_C_EXPECTED_AND_ACTUAL_ROUTE_CONFLATED")

    negative = trace.get("NEGATIVE_CONTROLS", {})
    for role in CASE_C_NEGATIVE_ROLES:
        if negative.get(role) != {"INVOCATIONS": 0, "UNIQUE_CHILD_SESSIONS": 0}:
            if role == "argus":
                add("NATIVE_C_ARGUS_NEGATIVE_CONTROL_ACTIVATED")
            else:
                add(f"NATIVE_C_NEGATIVE_CONTROL_MISMATCH:{role}")
    if trace.get("GATE_FACTS", {}).get("OBVIOUS_FUNCTIONAL_CAUSE") is not True:
        add("NATIVE_C_OBVIOUS_CAUSE_GATE_MISMATCH")
    if trace.get("CONSULTATION_COUNTS", {}).get("argus") != 0:
        add("NATIVE_C_ARGUS_NEGATIVE_CONTROL_ACTIVATED")
    if negative.get("BASIS") != "No root invocation or unique child activation was observed for the eight required negative-control roles; an additional Vera zero-control was also recorded. Nox was active only for isolation verification.":
        add("NATIVE_C_NEGATIVE_CONTROL_BASIS_MISMATCH")

    expected_role_purity = {
        "STATUS": "PASS",
        "ROOT_AGENT": "kael",
        "ALL_CHILDREN_DIRECT": True,
        "NESTED_DELEGATION_OBSERVED": False,
        "REVIEWER_EDITS_OBSERVED": False,
        "ROOT_SOURCE_WRITES_OBSERVED": False,
        "VIOLATIONS": [],
        "TOOL_CLASSES_BY_ROLE": {
            "kael": ["subagent", "read", "glob"],
            "nox": ["shell"],
            "kovan": ["read", "shell", "patch"],
        },
        "TOOL_COUNTS_BY_ROLE": {
            "kael": {"subagent": 2, "read": 4, "glob": 1},
            "nox": {"shell": 7},
            "kovan": {"read": 2, "shell": 4, "patch": 1},
        },
    }
    if trace.get("ROLE_PURITY") != expected_role_purity:
        add("NATIVE_C_ROLE_PURITY_EVIDENCE_MISMATCH")

    expected_tool_events = [
        {
            "EVENT_ID": "C-KOVAN-PATCH",
            "ORDER_BASIS": "observed",
            "ACTOR_ROLE": "kovan",
            "NATIVE_SESSION_ID": CASE_C_CHILD_SESSIONS[1]["NATIVE_SESSION_ID"],
            "TOOL": "patch",
            "TOOL_CALL_ID": "call_gm68QzM9sO8l5DgOS2Tkls4Q",
            "OBSERVED_MESSAGE_ID": "msg_105fc52e2001R35Hys7l2SxrmZ",
            "STATUS": "SUCCESS",
            "PATHS": [CASE_C_CHANGED_PATH],
            "CHANGE": "subtraction to multiplication per the explicit documented cart contract",
        },
        {
            "EVENT_ID": "C-KOVAN-TEST",
            "ORDER_BASIS": "observed",
            "ACTOR_ROLE": "kovan",
            "NATIVE_SESSION_ID": CASE_C_CHILD_SESSIONS[1]["NATIVE_SESSION_ID"],
            "TOOL": "shell",
            "TOOL_CALL_ID": "call_dZj806Y8huwlRqI8VEDrC7ns",
            "OBSERVED_MESSAGE_ID": "msg_105fc6879001r8nuWFHrt1nCIF",
            "STATUS": "SUCCESS",
            "COMMAND": CASE_C_TEST_COMMAND,
            "EXIT_CODE": 0,
            "TEST_TARGET": "test_cart.test_total_is_price_times_quantity",
            "RESULT": "PASS",
            "ENVIRONMENT": CASE_C_TERMINAL_FACTS["ENVIRONMENT"],
        },
        {
            "EVENT_ID": "C-KOVAN-DIFF-CHECK",
            "ORDER_BASIS": "observed",
            "ACTOR_ROLE": "kovan",
            "NATIVE_SESSION_ID": CASE_C_CHILD_SESSIONS[1]["NATIVE_SESSION_ID"],
            "TOOL": "shell",
            "TOOL_CALL_ID": "call_rYrd2ba8VsCZEEK5obRWCJPs",
            "OBSERVED_MESSAGE_ID": "msg_105fcbb48001l6pEwlZXxCaOm8",
            "STATUS": "SUCCESS",
            "COMMAND": "git diff --check",
            "EXIT_CODE": 0,
        },
    ]
    if trace.get("CHILD_TOOL_EVENTS") != expected_tool_events:
        add("NATIVE_C_CHILD_TOOL_EVIDENCE_MISMATCH")

    expected_runtime_validation = {
        "PYTHON_REQUESTED": "3.11",
        "COMMAND": CASE_C_TEST_COMMAND,
        "RESULT": "PASS",
        "EXIT_CODE": 0,
        "TEST_TARGET": "test_cart.test_total_is_price_times_quantity",
        "TESTS_PASSED": None,
        "ENVIRONMENT": CASE_C_TERMINAL_FACTS["ENVIRONMENT"],
        "SOURCE_INTEGRITY_AFTER_TEST": None,
    }
    if trace.get("RUNTIME_VALIDATION") != expected_runtime_validation:
        add("NATIVE_C_RUNTIME_VALIDATION_MISMATCH")
    if trace.get("LOCAL_VALIDATIONS") != [{"COMMAND": "git diff --check", "RESULT": "PASS", "EXIT_CODE": 0}]:
        add("NATIVE_C_LOCAL_VALIDATION_MISMATCH")

    expected_gate_facts = {
        "EXPLICIT_OPTIMIZATION_INTENT": None,
        "EXPLICIT_PLANNING_INTENT": None,
        "COMPLEX_FEATURE": False,
        "OBVIOUS_FUNCTIONAL_CAUSE": True,
        "NONTRIVIAL_FUNCTIONAL_CAUSE": False,
        "SECURITY_BOUNDARY": None,
        "OPERATIONAL_TOOLING_FAILURE": None,
        "HIGH_UNCERTAINTY_AFTER_BOUNDED_DIAGNOSIS": None,
        "THIRD_PARTY_BUG": None,
        "FAST_PROFILE_REQUESTED": None,
        "NORMAL_PROFILE_REQUESTED": None,
        "MAINTENANCE_ENTRY_EXPLICIT": None,
    }
    if trace.get("GATE_FACTS") != expected_gate_facts:
        add("NATIVE_C_GATE_FACTS_MISMATCH")
    expected_proxies = {
        "PROFILE": None,
        "USEFUL_INDEPENDENT_WRITER_COUNT": None,
        "ACTUAL_COUNTED_CONCURRENCY": 1,
        "RETRY_COUNT": None,
        "WRITER_PATHS_UNIQUE": None,
        "APPROVAL_REQUIRED": None,
        "APPROVAL_GRANTED": None,
        "IMPLEMENTATION_AFTER_APPROVAL": None,
        "WALL_CLOCK_MS": None,
        "MEASURED": False,
        "EFFICIENCY_CLASSIFICATION": "LEAN",
        "EFFICIENCY_CLASSIFICATION_BASIS": "Qualification judgment; not measured latency or throughput.",
    }
    if trace.get("OPERATIONAL_PROXIES") != expected_proxies:
        add("NATIVE_C_OPERATIONAL_PROXIES_MISMATCH")
    if trace.get("NATIVE_CAPTURE_MODEL") != "Invocation-level root subagent call creation/return events joined to unique direct child sessions and the observed root terminal statement; intentionally not the synthetic one-lifecycle-per-session event model.":
        add("NATIVE_C_CAPTURE_MODEL_UNDOCUMENTED")

    expected_result = {
        "EXPECTED_RESULT": "succeeded",
        "EXPECTED_RESULT_SOURCE": "task acceptance context",
        "OBSERVED_RESULT": "succeeded",
        "OBSERVED_RESULT_SOURCE": "native root terminal metadata",
        "MATCHES": True,
        "UNKNOWN": False,
        "OBSERVED_TERMINAL_MESSAGE_ID": CASE_C_ROOT_TERMINAL_MESSAGE_ID,
        "OBSERVED_TERMINAL_FACTS_MATCH": True,
        "COMPARISON_BASIS": "Expected terminal class from task acceptance context is distinguished from the literal native root terminal facts; Case C classification and diff-check result are not projected into the root summary.",
    }
    if trace.get("RESULT_FIDELITY") != expected_result:
        add("NATIVE_C_RESULT_FIDELITY_MISMATCH")
    expected_completion = {
        "PENDING_CHILD_COUNT": 0,
        "UNCONSUMED_RESULT_COUNT": 0,
        "UNKNOWN_EXECUTION_COUNT": 0,
        "EXACT_ONCE": None,
        "QUESTION_BARRIER_SATISFIED": True,
        "ROOT_COMPLETION_STATEMENT_OBSERVED": True,
        "REQUIRED_CHILD_SESSIONS_TERMINAL_AND_CONSUMED": True,
        "TWO_DISTINCT_ROOT_INVOCATION_RETURNS_OBSERVED_ONCE": True,
        "INVOCATION_RESULT_IDS": None,
        "SESSION_LIFETIME_EXACT_ONCE": None,
        "PER_INVOCATION_CONSUMPTION_TIMING": None,
    }
    if trace.get("COMPLETION_GATE") != expected_completion:
        add("NATIVE_C_COMPLETION_GATE_MISMATCH")
    if (
        final_event.get("PENDING_CHILD_COUNT") != 0
        or final_event.get("UNCONSUMED_RESULT_COUNT") != 0
        or final_event.get("UNKNOWN_EXECUTION_COUNT") != 0
        or final_event.get("REQUIRED_CHILD_SESSIONS_TERMINAL_AND_CONSUMED") is not True
    ):
        add("NATIVE_C_FINAL_COMPLETION_FACTS_MISMATCH")
    if trace.get("USER_QUESTION_COUNT") != 0 or trace.get("USER_QUESTION_COUNT_BASIS") != "Complete root history contained no ask-user calls or nested subagents.":
        add("NATIVE_C_USER_QUESTION_COUNT_MISMATCH")
    if not isinstance(trace.get("NOTES"), str) or not trace.get("NOTES", "").strip():
        add("NATIVE_C_NOTES_MISSING")
    return errors


def validate_phase11_c_reconciliation(
    baseline: dict[str, Any], cases_doc: dict[str, Any], trace: dict[str, Any]
) -> list[str]:
    """Bind the native C capture to its latest classification without rewriting B3 history."""
    cases = {case.get("id"): case for case in cases_doc.get("cases", []) if isinstance(case, dict)}
    case_c = cases.get("C", {})
    errors = validate_native_case_c_capture(trace, case_c)
    report = baseline.get("phase11_c_reconciliation")
    if not isinstance(report, dict):
        return errors + ["CASE_C_RECONCILIATION_MISSING"]

    expected_classifications = {
        "CASE_C_FRESH_ROOT_NATIVE": "PASS",
        "ISOLATION": "PASS",
        "ROUTING": "PASS",
        "NEGATIVE_ARGUS_CONTROL": "PASS",
        "ROLE_PURITY": "PASS",
        "RESULT_FIDELITY": "PASS",
        "COMPLETION_OWNERSHIP": "PASS",
        "EFFICIENCY": "LEAN",
    }
    if report.get("label") != "PHASE11_CASE_C_FRESH_ROOT":
        errors.append("CASE_C_LABEL_MISMATCH")
    if report.get("evidence_artifact") != "tests/phase11-integrated-routing/case-c.native-trace.json" or report.get("evidence_class") != "FRESH_ROOT_NATIVE":
        errors.append("CASE_C_EVIDENCE_LINK_MISMATCH")
    if (
        report.get("root_session_id") != CASE_C_ROOT_SESSION_ID
        or report.get("root_directory") != CASE_C_ROOT_DIRECTORY
        or report.get("root_agent") != "kael"
        or report.get("root_parent_session_id") is not None
        or report.get("root_terminal_outcome") != "succeeded"
        or report.get("root_terminal_message_id") != CASE_C_ROOT_TERMINAL_MESSAGE_ID
    ):
        errors.append("CASE_C_ROOT_RECONCILIATION_MISMATCH")
    if report.get("isolation") != {
        "worktree_isolation": "PASS",
        "separate_disposable_copy": True,
        "execution_repository": "SEPARATE_DISPOSABLE_COPY",
        "verification_session_id": CASE_C_CHILD_SESSIONS[0]["NATIVE_SESSION_ID"],
        "verified_directory": CASE_C_ROOT_DIRECTORY,
        "canonical_repository_head": CASE_C_ROOT_HEAD,
        "verified_head": CASE_C_ROOT_HEAD,
        "verification_only": True,
        "worktree_creation_claimed": False,
        "historical_git_check_exit_code": None,
    }:
        errors.append("CASE_C_ISOLATION_RECONCILIATION_MISMATCH")
    if report.get("classifications") != expected_classifications:
        errors.append("CASE_C_CLASSIFICATION_MISMATCH")
    if report.get("acceptance_status") != "PASS":
        errors.append("CASE_C_ACCEPTANCE_STATUS_MISMATCH")
    if report.get("phase11_status") != "PARTIAL":
        errors.append("CASE_C_PHASE_STATUS_MUST_REMAIN_PARTIAL")
    if report.get("pending_fresh_root_labels") != CASE_C_PENDING_LABELS:
        errors.append("CASE_C_CURRENT_PENDING_LABELS_MISMATCH")

    if report.get("expected_product_route") != CASE_C_EXPECTED_ROUTE or report.get("observed_unique_child_session_launch_order") != CASE_C_ACTUAL_ROUTE:
        errors.append("CASE_C_ROUTE_RECONCILIATION_MISMATCH")
    if report.get("route_difference") != "JUSTIFIED_QUALIFICATION_PREREQUISITE: initial Nox worktree-isolation verification preceded the product correction; it is not product diagnosis.":
        errors.append("CASE_C_ROUTE_DIFFERENCE_CLASSIFICATION_MISMATCH")
    expected_report_children = [
        {"role": child["AGENT"], "session_id": child["NATIVE_SESSION_ID"], "launch_order": child["LAUNCH_ORDER"], "invocation_count": 1}
        for child in CASE_C_CHILD_SESSIONS
    ]
    if report.get("child_sessions") != expected_report_children:
        errors.append("CASE_C_CHILD_SESSION_RECONCILIATION_MISMATCH")
    expected_baseline_role_purity = {
        "direct_children_only": True,
        "nested_delegation": False,
        "reviewer_edits": False,
        "root_source_writes": False,
        "tool_counts_by_role": {
            "kael": {"subagent": 2, "read": 4, "glob": 1},
            "nox": {"shell": 7},
            "kovan": {"read": 2, "shell": 4, "patch": 1},
        },
        "negative_role_invocations": {role: 0 for role in CASE_C_NEGATIVE_ROLES},
    }
    if report.get("role_purity") != expected_baseline_role_purity:
        errors.append("CASE_C_ROLE_PURITY_RECONCILIATION_MISMATCH")
    if report.get("root_subagent_call_invocation_counts") != {"nox": 1, "kovan": 1} or report.get("invocation_returns_observed_once") != 2:
        errors.append("CASE_C_INVOCATION_RECONCILIATION_MISMATCH")
    expected_consumption = {
        "final_root_statement": "All required child sessions terminal and consumed.",
        "pending_children": 0,
        "unconsumed_results": 0,
        "unknown_executions": 0,
        "result_ids": None,
        "per_invocation_consumption_timing": None,
        "session_lifetime_exact_once": None,
    }
    if report.get("result_ids") is not None or report.get("result_consumption") != expected_consumption:
        errors.append("CASE_C_RESULT_CONSUMPTION_RECONCILIATION_MISMATCH")
    if report.get("user_question_count") != 0:
        errors.append("CASE_C_USER_QUESTION_COUNT_MISMATCH")
    if report.get("observed_terminal_snapshot") != {
        "source": "OBSERVED_NATIVE_ROOT_TERMINAL_MESSAGE",
        "root_session_id": CASE_C_ROOT_SESSION_ID,
        "message_id": CASE_C_ROOT_TERMINAL_MESSAGE_ID,
        "facts": CASE_C_TERMINAL_FACTS,
    }:
        errors.append("CASE_C_BASELINE_TERMINAL_SNAPSHOT_MISMATCH")
    if report.get("efficiency_basis") != "LEAN is a qualification judgment, not measured latency or throughput.":
        errors.append("CASE_C_EFFICIENCY_BASIS_MISMATCH")
    if report.get("case_rerun_performed_by_reconciliation") is not False:
        errors.append("CASE_C_RECONCILIATION_MUST_NOT_RERUN_CASE")

    current = baseline.get("live_qualification", {})
    if not isinstance(current, dict) or (
        current.get("pending_labels") != CURRENT_PHASE11_PENDING_LABELS
        or current.get("fresh_root_native") != "B3_PASS; C_PASS; D_PASS; E,F,G,H,K_PENDING"
        or current.get("native_results_claimed") is not True
    ):
        errors.append("CURRENT_PHASE11_PENDING_STATE_MISMATCH")

    action_rows = [
        action for action in cases_doc.get("fresh_root_actions", [])
        if action.get("case_id") == "C" and action.get("label") == "PHASE11_CASE_C_FRESH_ROOT"
    ]
    if len(action_rows) != 1 or any(
        action_rows[0].get(key) != value
        for key, value in {
            "status": "PASS",
            "evidence_class": "FRESH_ROOT_NATIVE",
            "evidence_artifact": "case-c.native-trace.json",
        }.items()
    ):
        errors.append("CASE_C_MATRIX_EVIDENCE_LINK_MISMATCH")
    if report.get("case_routing_result") != "CASE_C_FRESH_ROOT_NATIVE_PASS; Argus did not activate for the obvious functional defect.":
        errors.append("CASE_C_ROUTING_RESULT_CLASSIFICATION_MISMATCH")
    return errors


def validate_native_case_d_capture(trace: dict[str, Any], case: dict[str, Any]) -> list[str]:
    """Check Case D's native invocation evidence without inventing a synthetic lifecycle."""
    errors: list[str] = []
    required = (
        "CASE_ID", "REQUEST_CLASS", "EXPECTED_ROUTE", "ACTUAL_ROUTE", "CHILD_SESSIONS",
        "CONSULTATION_COUNTS", "MAX_SIMULTANEOUS_CHILDREN", "NEGATIVE_CONTROLS", "ROLE_PURITY",
        "DEPENDENCY_ORDER", "RESULT_FIDELITY", "COMPLETION_GATE", "USER_QUESTION_COUNT",
        "FINAL_OUTCOME", "ROUTING_RESULT", "NOTES", "EVIDENCE_PROVENANCE", "EVENTS",
        "EVIDENCE_CLASS", "ROOT_SESSION_ID", "ROOT_PARENT_SESSION_ID", "ROOT_EXECUTION_OUTCOME",
    )
    missing = [field for field in required if field not in trace]
    if missing:
        return ["NATIVE_D_MISSING_REQUIRED_FIELDS:" + ",".join(missing)]

    if trace.get("TRACE_ID") != "D-NATIVE" or trace.get("CASE_ID") != "D":
        errors.append("NATIVE_D_IDENTITY_MISMATCH")
    if case.get("id") != "D" or trace.get("REQUEST_CLASS") != case.get("request_class"):
        errors.append("NATIVE_D_REQUEST_CLASS_MISMATCH")
    if trace.get("EVIDENCE_CLASS") != "FRESH_ROOT_NATIVE":
        errors.append("NATIVE_D_EVIDENCE_CLASS_MISMATCH")
    if trace.get("SCENARIO") != "precollected_evidence" or trace.get("ROUTE_MODE") != "KAEL_ROOT":
        errors.append("NATIVE_D_SCENARIO_OR_ROUTE_MODE_MISMATCH")
    routes = case.get("expected_routes", {})
    if routes.get("precollected_evidence") != CASE_D_EXPECTED_ROUTE or trace.get("EXPECTED_ROUTE") != CASE_D_EXPECTED_ROUTE:
        errors.append("NATIVE_D_EXPECTED_PRODUCT_ROUTE_MISMATCH")
    if trace.get("ACTUAL_ROUTE") != CASE_D_ACTUAL_ROUTE:
        errors.append("NATIVE_D_ACTUAL_CHILD_ORDER_MISMATCH")
    if trace.get("ROUTE_RECONCILIATION") != {
        "EXPECTED_PRODUCT_ROUTE": CASE_D_EXPECTED_ROUTE,
        "OBSERVED_UNIQUE_CHILD_SESSION_LAUNCH_ORDER": CASE_D_ACTUAL_ROUTE,
        "CLASSIFICATION": "JUSTIFIED_QUALIFICATION_PREREQUISITE",
        "JUSTIFICATION": "Nox performed read-only isolation verification before the product diagnostic route. Veyra gathered bounded evidence before one Argus consultation; the observed family is preserved without treating Nox as product diagnosis.",
    }:
        errors.append("NATIVE_D_ROUTE_RECONCILIATION_MISMATCH")

    if (
        trace.get("ROOT_SESSION_ID") != CASE_D_ROOT_SESSION_ID
        or trace.get("ROOT_DIRECTORY") != CASE_D_ROOT_DIRECTORY
        or trace.get("ROOT_AGENT") != "kael"
        or trace.get("ROOT_TITLE") != "Phase 11 fresh-root diagnosis qualification"
        or trace.get("ROOT_TERMINAL_MESSAGE_ID") != CASE_D_ROOT_TERMINAL_MESSAGE_ID
    ):
        errors.append("NATIVE_D_ROOT_IDENTITY_MISMATCH")
    if trace.get("ROOT_PARENT_SESSION_ID") is not None or trace.get("ROOT_PARENT_SESSION_ID_OBSERVATION") != "NOT_EXPOSED":
        errors.append("NATIVE_D_ROOT_PARENT_OBSERVATION_MISMATCH")
    if trace.get("ROOT_EXECUTION_OUTCOME") != "succeeded" or trace.get("FINAL_OUTCOME") != "NEEDS_USER_INPUT":
        errors.append("NATIVE_D_EXECUTION_AND_SEMANTIC_OUTCOME_CONFLATED")
    if trace.get("ROOT_ISOLATION") != {
        "STATUS": "PASS",
        "SEPARATE_DISPOSABLE_WORKTREE": True,
        "EXECUTION_REPOSITORY": "REGISTERED_LINKED_WORKTREE",
        "SHARES_CANONICAL_GIT_COMMON_DIR": True,
        "VERIFIED_DIRECTORY": CASE_D_ROOT_DIRECTORY,
        "INITIAL_HEAD": CASE_D_ROOT_HEAD,
        "VERIFIED_HEAD": CASE_D_ROOT_HEAD,
        "CANONICAL_REPOSITORY_HEAD": CASE_D_ROOT_HEAD,
        "VERIFICATION_ONLY": True,
        "WORKTREE_CREATION_CLAIMED": False,
        "NOX_INITIAL_WORKTREE_CLEAN": True,
        "NOX_FINAL_WORKTREE_CLEAN": True,
    }:
        errors.append("NATIVE_D_ISOLATION_RECONCILIATION_MISMATCH")

    children = trace.get("CHILD_SESSIONS")
    if children != CASE_D_CHILD_SESSIONS:
        errors.append("NATIVE_D_CHILD_SESSION_RECONCILIATION_MISMATCH")
    if not isinstance(children, list) or len(children) != 3:
        errors.append("NATIVE_D_CHILD_SESSION_SET_MISMATCH")
        children = children if isinstance(children, list) else []
    child_ids = [child.get("NATIVE_SESSION_ID") for child in children]
    if len(child_ids) != len(set(child_ids)) or CASE_D_ROOT_SESSION_ID in child_ids:
        errors.append("NATIVE_D_SESSION_IDENTITIES_NOT_UNIQUE")
    if any(
        child.get("PARENT_AGENT") != "kael"
        or child.get("PARENT_SESSION_ID") != CASE_D_ROOT_SESSION_ID
        or child.get("EXECUTION_STATE") != "SUCCEEDED"
        or child.get("FINAL_OUTCOME") != "succeeded"
        for child in children
    ):
        errors.append("NATIVE_D_CHILD_PARENT_ROLE_OR_TERMINAL_MISMATCH")

    events = trace.get("EVENTS")
    expected_kinds = [
        "ROOT_SUBAGENT_CALL_CREATED", "ROOT_SUBAGENT_CALL_RUNNING", "ROOT_SUBAGENT_RESULT_RETURNED",
        "ROOT_SUBAGENT_CALL_CREATED", "ROOT_SUBAGENT_CALL_RUNNING", "ROOT_SUBAGENT_RESULT_RETURNED",
        "ROOT_SUBAGENT_CALL_CREATED", "ROOT_SUBAGENT_CALL_RUNNING", "ROOT_SUBAGENT_RESULT_RETURNED",
        "ROOT_FINAL_COMPLETION",
    ]
    if not isinstance(events, list) or [event.get("KIND") for event in events] != expected_kinds:
        errors.append("NATIVE_D_INVOCATION_EVENT_MODEL_MISMATCH")
        events = events if isinstance(events, list) else []
    if [event.get("ORDER") for event in events] != list(range(1, 11)) or any(
        event.get("ORDER_BASIS") != "observed" for event in events
    ):
        errors.append("NATIVE_D_EVENT_ORDER_NOT_OBSERVED")

    for index, child in enumerate(CASE_D_CHILD_SESSIONS):
        group = events[index * 3:index * 3 + 3]
        if len(group) != 3:
            errors.append("NATIVE_D_INVOCATION_EVENT_GROUP_MISSING:" + child["TRACE_REF"])
            continue
        common = {
            "ACTOR_ROLE": "kael",
            "CHILD_REF": child["TRACE_REF"],
            "SESSION_REF": child["TRACE_REF"],
            "NATIVE_SESSION_ID": child["NATIVE_SESSION_ID"],
            "AGENT": child["AGENT"],
            "TOOL": "subagent",
            "TOOL_CALL_ID": child["INVOCATION_TOOL_CALL_ID"],
            "PARENT_MESSAGE_ID": child["PARENT_MESSAGE_ID"],
            "PARENT_SESSION_ID": CASE_D_ROOT_SESSION_ID,
        }
        if any(any(event.get(key) != value for key, value in common.items()) for event in group):
            errors.append("NATIVE_D_INVOCATION_SESSION_OR_ROLE_JOIN_MISMATCH:" + child["TRACE_REF"])
        if (
            group[0].get("CALL_CREATED_AT_EPOCH_MS") != child["CALL_CREATED_AT_EPOCH_MS"]
            or group[1].get("CALL_RAN_AT_EPOCH_MS") != child["CALL_RAN_AT_EPOCH_MS"]
            or group[2].get("CALL_COMPLETED_AT_EPOCH_MS") != child["CALL_COMPLETED_AT_EPOCH_MS"]
            or not (
                child["CALL_CREATED_AT_EPOCH_MS"]
                < child["CALL_RAN_AT_EPOCH_MS"]
                < child["CALL_COMPLETED_AT_EPOCH_MS"]
            )
        ):
            errors.append("NATIVE_D_CALL_TIMING_RECONCILIATION_MISMATCH:" + child["TRACE_REF"])
        if (
            group[2].get("OBSERVED_MESSAGE_ID") != child["TERMINAL_MESSAGE_ID"]
            or group[2].get("TOOL_STATE") != "completed"
            or group[2].get("RETURN_STATUS") != CASE_D_LITERAL_RETURN_STATUSES[child["AGENT"]]
            or group[2].get("CHILD_EXECUTION_OUTCOME") != "succeeded"
            or group[2].get("RESULT_ID") is not None
        ):
            errors.append("NATIVE_D_LITERAL_RETURN_STATUS_OR_TOOL_STATE_MISMATCH:" + child["TRACE_REF"])
    if any(
        left["CALL_COMPLETED_AT_EPOCH_MS"] >= right["CALL_CREATED_AT_EPOCH_MS"]
        for left, right in zip(CASE_D_CHILD_SESSIONS, CASE_D_CHILD_SESSIONS[1:])
    ):
        errors.append("NATIVE_D_NONOVERLAPPING_CHILD_ORDER_MISMATCH")

    if events and events[-1].get("TERMINAL_FACTS") != CASE_D_ROOT_FINAL_FACTS:
        errors.append("NATIVE_D_ROOT_TERMINAL_FACTS_MISMATCH")
    if events and (
        events[-1].get("ROOT_SESSION_ID") != CASE_D_ROOT_SESSION_ID
        or events[-1].get("MESSAGE_ID") != CASE_D_ROOT_TERMINAL_MESSAGE_ID
        or events[-1].get("EXECUTION_OUTCOME") != "succeeded"
        or events[-1].get("SEMANTIC_FINAL_OUTCOME") != "NEEDS_USER_INPUT"
        or events[-1].get("RESULT_ID") is not None
    ):
        errors.append("NATIVE_D_ROOT_TERMINAL_OUTCOME_MISMATCH")
    if any(event.get("RESULT_ID") is not None for event in events) or any(
        "RESULT_CONSUMED" in str(event.get("KIND")) for event in events
    ):
        errors.append("NATIVE_D_UNOBSERVED_RESULT_ID_OR_CONSUMPTION_EVENT")
    provenance = trace.get("EVIDENCE_PROVENANCE", {})
    if (
        provenance.get("CLASS") != "FRESH_ROOT_NATIVE"
        or provenance.get("NATIVE_ROOT_SESSION_ID") != CASE_D_ROOT_SESSION_ID
        or provenance.get("NATIVE_ROOT_DIRECTORY") != CASE_D_ROOT_DIRECTORY
        or provenance.get("NATIVE_ROOT_PARENT_SESSION_ID") is not None
        or provenance.get("NATIVE_ROOT_PARENT_SESSION_ID_OBSERVATION") != "NOT_EXPOSED"
        or provenance.get("NATIVE_CHILD_SESSION_IDS") != child_ids
        or provenance.get("ORDER_BASIS") != "observed"
        or provenance.get("OBSERVED_AT") is not None
        or provenance.get("FRESH_ROOT_CONFIRMED") is not True
        or provenance.get("NATIVE_PERMISSION_UI") != "NOT_OBSERVABLE"
        or provenance.get("NATIVE_PERMISSION_DECISION") != "NOT_OBSERVABLE"
    ):
        errors.append("NATIVE_D_PROVENANCE_MISMATCH")
    snapshot = trace.get("OBSERVED_TERMINAL_SNAPSHOT", {})
    if snapshot != {
        "OBSERVATION": "OBSERVED_NATIVE_ROOT_TERMINAL_MESSAGE",
        "ROOT_SESSION_ID": CASE_D_ROOT_SESSION_ID,
        "MESSAGE_ID": CASE_D_ROOT_TERMINAL_MESSAGE_ID,
        "EXECUTION_OUTCOME": "succeeded",
        "FACTS": CASE_D_ROOT_FINAL_FACTS,
    }:
        errors.append("NATIVE_D_TERMINAL_SNAPSHOT_MISMATCH")

    expected_counts = {role: 0 for role in ALL_INVOCABLE_ROLES}
    expected_counts.update({"nox": 1, "veyra": 1, "argus": 1})
    if trace.get("CONSULTATION_COUNTS") != expected_counts or trace.get("UNIQUE_CHILD_SESSION_COUNTS") != expected_counts:
        errors.append("NATIVE_D_CONSULTATION_OR_SESSION_COUNTS_MISMATCH")
    if trace.get("MAX_SIMULTANEOUS_CHILDREN") != 1 or trace.get("OPERATIONAL_PROXIES", {}).get("ACTUAL_COUNTED_CONCURRENCY") != 1:
        errors.append("NATIVE_D_CONCURRENCY_MISMATCH")
    expected_negative = {
        role: {"INVOCATIONS": 0, "UNIQUE_CHILD_SESSIONS": 0}
        for role in CASE_D_NEGATIVE_ROLES
    }
    expected_negative["BASIS"] = (
        "Complete root history records no invocation for these nonparticipating roles. Nox is a qualification-only isolation prerequisite, while Veyra and Argus are active in the diagnostic workflow."
    )
    if trace.get("NEGATIVE_CONTROLS") != expected_negative:
        errors.append("NATIVE_D_NEGATIVE_CONTROL_MISMATCH")
    role_purity = trace.get("ROLE_PURITY", {})
    if (
        role_purity.get("STATUS") != "PASS"
        or role_purity.get("ALL_CHILDREN_DIRECT") is not True
        or role_purity.get("NESTED_DELEGATION_OBSERVED") is not False
        or role_purity.get("ROOT_SOURCE_WRITES_OBSERVED") is not False
        or role_purity.get("ROOT_IMPLEMENTATION_OBSERVED") is not False
        or role_purity.get("ARGUS_REPOSITORY_EXPLORATION_OBSERVED") is not False
        or role_purity.get("VIOLATIONS") != []
        or role_purity.get("TOOL_COUNTS_BY_ROLE") != {
            "kael": {"subagent": 3}, "nox": {"shell": 7}, "veyra": {"read": 1}, "argus": {}
        }
        or role_purity.get("NEGATIVE_ROLE_INVOCATIONS") != {role: 0 for role in CASE_D_NEGATIVE_ROLES}
    ):
        errors.append("NATIVE_D_ROLE_PURITY_MISMATCH")

    expected_dependency = [{
        "BEFORE": "D-VEYRA:TERMINAL",
        "AFTER": "D-ARGUS:CALL",
        "RELATION": "Already-collected bounded Veyra evidence was supplied to Argus before its single consultation; no per-result consumption timestamp or result ID is claimed.",
    }]
    if trace.get("DEPENDENCY_ORDER") != expected_dependency:
        errors.append("NATIVE_D_PRECOLLECTED_EVIDENCE_ORDER_MISMATCH")
    argus = trace.get("ARGUS_DIAGNOSTIC", {})
    argus_return = events[8] if len(events) > 8 else {}
    if (
        argus.get("NATIVE_SESSION_ID") != CASE_D_CHILD_SESSIONS[2]["NATIVE_SESSION_ID"]
        or argus.get("TERMINAL_MESSAGE_ID") != CASE_D_CHILD_SESSIONS[2]["TERMINAL_MESSAGE_ID"]
        or argus.get("EXECUTION_OUTCOME") != "succeeded"
        or argus.get("CONSULTATION_COUNT") != 1
        or argus.get("STATUS") != "INCONCLUSIVE"
        or argus.get("CAUSE") != "CAUSE_UNCONFIRMED. No functional violation is established."
        or argus.get("EVIDENCE_REQUESTED") is not False
        or argus.get("FOLLOWUP_CONSULTATION") is not False
        or argus.get("FINAL_BINARY_QUESTION") != CASE_D_ROOT_FINAL_FACTS["FINAL_BINARY_QUESTION"]
        or argus_return.get("TOOL_STATE") != "completed"
        or argus_return.get("RETURN_STATUS") != argus.get("STATUS")
        or argus.get("STATUS") != "INCONCLUSIVE"
        or trace.get("FINAL_OUTCOME") != "NEEDS_USER_INPUT"
    ):
        errors.append("NATIVE_D_DIAGNOSTIC_AND_OUTCOME_STATUS_MISMATCH")
    result = trace.get("RESULT_FIDELITY", {})
    if (
        result.get("MATCHES") is not True
        or result.get("UNKNOWN") is not False
        or result.get("ROOT_EXECUTION_OUTCOME") != "succeeded"
        or result.get("SEMANTIC_FINAL_OUTCOME") != "NEEDS_USER_INPUT"
        or result.get("ARGUS_EXECUTION_OUTCOME") != "succeeded"
        or result.get("ARGUS_DIAGNOSTIC_STATUS") != "INCONCLUSIVE"
        or result.get("CAUSE") != "CAUSE_UNCONFIRMED"
        or result.get("FUNCTIONAL_VIOLATION_ESTABLISHED") is not False
        or result.get("REPAIR_SUPPORTED") is not False
    ):
        errors.append("NATIVE_D_RESULT_FIDELITY_MISMATCH")
    completion = trace.get("COMPLETION_GATE", {})
    if (
        completion.get("PENDING_CHILD_COUNT") != 0
        or completion.get("UNCONSUMED_RESULT_COUNT") != 0
        or completion.get("UNKNOWN_EXECUTION_COUNT") != 0
        or completion.get("EXACT_ONCE") is not None
        or completion.get("QUESTION_BARRIER_SATISFIED") is not True
        or completion.get("REQUIRED_CHILD_SESSIONS_TERMINAL_AND_CONSUMED") is not True
        or completion.get("RESULT_IDS") is not None
        or completion.get("PER_RESULT_CONSUMPTION_TIMESTAMPS") is not None
        or completion.get("SESSION_LIFETIME_EXACT_ONCE") is not None
    ):
        errors.append("NATIVE_D_COMPLETION_GATE_MISMATCH")
    question = trace.get("QUESTION_BARRIER", {})
    if (
        trace.get("USER_QUESTION_COUNT") != 1
        or question.get("STATUS") != "PASS"
        or question.get("QUESTION") != CASE_D_ROOT_FINAL_FACTS["FINAL_BINARY_QUESTION"]
        or question.get("QUESTION_TOOL_CALLS") != 0
        or question.get("DISPLAYED_AFTER_ARGUS_RESULT_DELIVERY") is not True
        or question.get("DISPLAYED_AFTER_ALL_CHILDREN_TERMINAL_AND_CONSUMED") is not True
        or question.get("CHILD_RESULT_CONSUMPTION_TIMESTAMPS") is not None
    ):
        errors.append("NATIVE_D_QUESTION_BARRIER_MISMATCH")
    if trace.get("GATE_FACTS", {}).get("NONTRIVIAL_FUNCTIONAL_CAUSE") is not None:
        errors.append("NATIVE_D_UNESTABLISHED_CAUSE_GATE_FACT_MUST_REMAIN_UNKNOWN")
    if trace.get("FUNCTIONAL_VIOLATION_ESTABLISHED") is True or trace.get("REPAIR_SUPPORTED") is True:
        errors.append("NATIVE_D_UNSUPPORTED_BUG_OR_REPAIR_CLAIM")
    expected_classifications = {
        "CASE_D_FRESH_ROOT_NATIVE": "PASS", "ISOLATION": "PASS", "ARGUS_ROUTING": "PASS",
        "NO_INVENTED_CAUSE": "PASS", "NO_PROGRESS_STOP": "PASS", "QUESTION_BARRIER": "PASS",
        "ROLE_PURITY": "PASS", "RESULT_FIDELITY": "PASS", "COMPLETION_OWNERSHIP": "PASS",
        "EFFICIENCY": "LEAN", "CASE_D_ARGUS_FOLLOWUP": "NOT_REQUIRED",
        "ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE": "NOT_EXERCISED",
    }
    if trace.get("ROUTING_RESULT_DETAIL") != expected_classifications:
        errors.append("NATIVE_D_CLASSIFICATION_MISMATCH")
    if (
        trace.get("CASE_D_ARGUS_FOLLOWUP") != "NOT_REQUIRED"
        or trace.get("ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE") != "NOT_EXERCISED"
        or trace.get("OPERATIONAL_PROXIES", {}).get("EFFICIENCY_CLASSIFICATION") != "LEAN"
        or trace.get("OPERATIONAL_PROXIES", {}).get("MEASURED") is not False
        or trace.get("OPERATIONAL_PROXIES", {}).get("WALL_CLOCK_MS") is not None
        or not isinstance(trace.get("NOTES"), str)
        or not trace.get("NOTES", "").strip()
    ):
        errors.append("NATIVE_D_FOLLOWUP_EFFICIENCY_OR_NOTES_MISMATCH")
    return errors


def validate_phase11_d_reconciliation(
    baseline: dict[str, Any], cases_doc: dict[str, Any], trace: dict[str, Any]
) -> list[str]:
    """Bind native Case D evidence to current qualification state and separate coverage."""
    cases = {case.get("id"): case for case in cases_doc.get("cases", []) if isinstance(case, dict)}
    errors = validate_native_case_d_capture(trace, cases.get("D", {}))
    report = baseline.get("phase11_d_reconciliation")
    if not isinstance(report, dict):
        return errors + ["CASE_D_RECONCILIATION_MISSING"]
    expected_classifications = trace.get("ROUTING_RESULT_DETAIL")
    if (
        report.get("task_id") != "P11-D-corpus"
        or report.get("label") != "PHASE11_CASE_D_FRESH_ROOT"
        or report.get("evidence_artifact") != "tests/phase11-integrated-routing/case-d.native-trace.json"
        or report.get("evidence_class") != "FRESH_ROOT_NATIVE"
    ):
        errors.append("CASE_D_EVIDENCE_LINK_OR_LABEL_MISMATCH")
    if (
        report.get("root_session_id") != CASE_D_ROOT_SESSION_ID
        or report.get("root_directory") != CASE_D_ROOT_DIRECTORY
        or report.get("root_agent") != "kael"
        or report.get("root_parent_session_id") is not None
        or report.get("root_parent_session_id_observation") != "NOT_EXPOSED"
        or report.get("root_terminal_outcome") != "succeeded"
        or report.get("root_terminal_message_id") != CASE_D_ROOT_TERMINAL_MESSAGE_ID
    ):
        errors.append("CASE_D_ROOT_RECONCILIATION_MISMATCH")
    if report.get("classifications") != expected_classifications or report.get("acceptance_status") != "PASS":
        errors.append("CASE_D_CLASSIFICATION_OR_ACCEPTANCE_MISMATCH")
    if report.get("phase11_status") != "PARTIAL":
        errors.append("CASE_D_PHASE_STATUS_MUST_REMAIN_PARTIAL")
    if report.get("pending_fresh_root_labels") != CURRENT_PHASE11_PENDING_LABELS:
        errors.append("CASE_D_CURRENT_PENDING_LABELS_MISMATCH")
    if report.get("expected_product_route") != CASE_D_EXPECTED_ROUTE or report.get("observed_unique_child_session_launch_order") != CASE_D_ACTUAL_ROUTE:
        errors.append("CASE_D_ROUTE_RECONCILIATION_MISMATCH")
    expected_children = [
        {
            "role": child["AGENT"],
            "session_id": child["NATIVE_SESSION_ID"],
            "launch_order": child["LAUNCH_ORDER"],
            "invocation_count": 1,
            "tool_state": "completed",
            "execution_outcome": "succeeded",
            "literal_return_status": CASE_D_LITERAL_RETURN_STATUSES[child["AGENT"]],
        }
        for child in CASE_D_CHILD_SESSIONS
    ]
    if report.get("child_sessions") != expected_children:
        errors.append("CASE_D_CHILD_SESSION_RECONCILIATION_MISMATCH")
    if report.get("root_subagent_call_invocation_counts") != {"nox": 1, "veyra": 1, "argus": 1}:
        errors.append("CASE_D_INVOCATION_COUNTS_MISMATCH")
    expected_report_facts = {
        "repository_inspection": {
            "root": "C:/Users/BLAUTECH/OneDrive/WORKSPACE/Personal/Tools/OpenCode-OlympusAgents",
            "branch": "qualify/phase-11-integrated-routing",
            "head_before_d_corpus_edits": CASE_D_ROOT_HEAD,
            "preexisting_working_tree_clean": True,
            "origin": "https://github.com/Edulynch/OpenCode-OlympusAgents.git",
            "origin_source": "task context",
            "git_mutation_performed": False,
        },
        "root_execution_and_semantic_outcomes": {
            "execution_metadata": "succeeded",
            "semantic_final_outcome": "NEEDS_USER_INPUT",
        },
        "isolation": {
            "worktree_isolation": "PASS",
            "separately_registered_worktree": True,
            "shares_canonical_git_common_dir": True,
            "verified_directory": CASE_D_ROOT_DIRECTORY,
            "starting_head": CASE_D_ROOT_HEAD,
            "canonical_repository_head": CASE_D_ROOT_HEAD,
            "verified_only": True,
            "worktree_creation_claimed": False,
            "nox_initial_worktree_clean": True,
            "nox_final_worktree_clean": True,
        },
        "result_consumption": {
            "root_aggregate_statement": "All three child sessions terminal and consumed.",
            "pending_children": 0,
            "unconsumed_results": 0,
            "unknown_executions": 0,
            "result_ids": None,
            "per_result_consumption_timestamps": None,
            "session_lifetime_exact_once": None,
        },
        "user_question_count": 1,
        "question_tool_calls": 0,
        "question_barrier": "PASS",
        "final_binary_question": CASE_D_ROOT_FINAL_FACTS["FINAL_BINARY_QUESTION"],
        "diagnosis": {
            "status": "INCONCLUSIVE",
            "cause": "CAUSE_UNCONFIRMED",
            "functional_violation_established": False,
            "repair_supported": False,
            "discriminating_evidence_found": False,
            "evidence_request_made_by_argus": False,
            "followup_consultation": False,
        },
        "efficiency_basis": "LEAN is a qualification judgment, not measured latency or throughput.",
        "source_integrity": {
            "root_files_changed": "NONE",
            "native_case_replayed_or_repaired": False,
            "writer_source_edits_to_case_fixture": False,
        },
        "case_rerun_performed_by_reconciliation": False,
    }
    for field, expected in expected_report_facts.items():
        if report.get(field) != expected:
            errors.append(f"CASE_D_RECONCILIATION_FACT_MISMATCH:{field}")
    if report.get("route_difference") != (
        "JUSTIFIED_QUALIFICATION_PREREQUISITE: Nox performed read-only isolation verification before the product diagnostic route; Veyra provided bounded evidence before one Argus consultation."
    ):
        errors.append("CASE_D_ROUTE_DIFFERENCE_CLASSIFICATION_MISMATCH")
    if report.get("result_ids") is not None or report.get("per_result_consumption_timestamps") is not None:
        errors.append("CASE_D_UNOBSERVED_RESULT_CONSUMPTION_MUST_REMAIN_NULL")
    if report.get("functional_violation_established") is not False or report.get("repair_supported") is not False:
        errors.append("CASE_D_CAUSE_OR_REPAIR_OVERCLAIM")
    if report.get("case_rerun_performed_by_reconciliation") is not False:
        errors.append("CASE_D_RECONCILIATION_MUST_NOT_RERUN_CASE")
    if report.get("followup") != CASE_D_PENDING_FOLLOWUP_COVERAGE:
        errors.append("CASE_D_FOLLOWUP_COVERAGE_SEPARATION_MISMATCH")

    coverage = baseline.get("argus_same_session_followup_runtime_coverage")
    if coverage != CASE_D_PENDING_FOLLOWUP_COVERAGE:
        errors.append("ARGUS_FOLLOWUP_RUNTIME_COVERAGE_PROMOTED_OR_CONFLATED")
    current = baseline.get("live_qualification", {})
    if not isinstance(current, dict) or (
        current.get("pending_labels") != CURRENT_PHASE11_PENDING_LABELS
        or current.get("fresh_root_native") != "B3_PASS; C_PASS; D_PASS; E,F,G,H,K_PENDING"
        or current.get("native_results_claimed") is not True
        or current.get("overall_status") != "PARTIAL"
    ):
        errors.append("CURRENT_PHASE11_PENDING_STATE_MISMATCH")
    action_rows = [
        action for action in cases_doc.get("fresh_root_actions", [])
        if action.get("case_id") == "D" and action.get("label") == "PHASE11_CASE_D_FRESH_ROOT"
    ]
    if len(action_rows) != 1 or any(
        action_rows[0].get(key) != value
        for key, value in {
            "scenario": "precollected_evidence",
            "status": "PASS",
            "evidence_class": "FRESH_ROOT_NATIVE",
            "evidence_artifact": "case-d.native-trace.json",
        }.items()
    ):
        errors.append("CASE_D_MATRIX_EVIDENCE_LINK_MISMATCH")
    return errors


def main() -> int:
    failures, documents = validate_corpus()
    static_failures = run_static_baseline_checks()
    baseline = load_json(HERE / "baseline.json")
    native_b3 = load_json(HERE / "case-b3.native-trace.json")
    native_c = load_json(HERE / "case-c.native-trace.json")
    native_d = load_json(HERE / "case-d.native-trace.json")
    reconciliation_failures = validate_phase11_b3_reconciliation(
        baseline, documents["cases"], native_b3
    )
    case_c_failures = validate_phase11_c_reconciliation(
        baseline, documents["cases"], native_c
    )
    case_d_failures = validate_phase11_d_reconciliation(
        baseline, documents["cases"], native_d
    )
    for label in ("ARGUS_GATE_MARKER", "TALOS_GATE_MARKER", "ATLAS_GATE_MARKER", "HELIOS_GATE_MARKER", "THALES_GATE_MARKER", "ROOT_OWNER_MARKER", "NO_NESTED_CHILD_MARKER", "CORE_CHILD_CEILING_MARKER"):
        if label in static_failures:
            print(f"STATIC_{label}: FAIL")
        else:
            print(f"STATIC_{label}: PASS (presence-only; not model-behavior proof)")
    for trace in documents["traces"]["traces"]:
        if not any(failure.startswith(f"{trace.get('TRACE_ID')}: ") for failure in failures):
            print(f"{trace.get('TRACE_ID')}: PASS ({trace.get('EVIDENCE_CLASS')})")
    if not reconciliation_failures:
        print("B3-NATIVE: PASS (FRESH_ROOT_NATIVE; invocation-level capture; not inserted into synthetic traces)")
    if not case_c_failures:
        print("C-NATIVE: PASS (FRESH_ROOT_NATIVE; Argus negative control PASS; Nox isolation prerequisite kept separate from product route)")
    if not case_d_failures:
        print("D-NATIVE: PASS (FRESH_ROOT_NATIVE; one terminal Argus diagnosis; unresolved cause correctly stops for one bounded user question)")
    pending_fresh_root_cases = {"E", "F", "G", "H", "K"}
    pending_labels: list[str] = []
    for action in documents["cases"].get("fresh_root_actions", []):
        case_id = action.get("case_id")
        if case_id in pending_fresh_root_cases:
            label = action.get("label", f"PHASE11_CASE_{case_id}_FRESH_ROOT")
            pending_labels.append(label)
            print(f"HUMAN_ACTION_REQUIRED {label}")
    if failures or reconciliation_failures or case_c_failures or case_d_failures:
        for failure in [*failures, *reconciliation_failures, *case_c_failures, *case_d_failures]:
            print(f"FAIL: {failure}")
        print("PHASE11_QUALIFICATION: FAIL (artifact validation only)")
        return 1
    if static_failures:
        for label in static_failures:
            print(f"FAIL: STATIC_{label}")
        print("PHASE11_QUALIFICATION: FAIL (bounded policy marker check)")
        return 1
    print("PHASE11_ARTIFACTS: PASS (synthetic/static artifacts, B3/C/D native invocation captures, and historical reconciliations are internally valid; validation does not authenticate source exports)")
    print("ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE: NOT_EXERCISED (separate optional evidence-requesting scenario remains open for final coverage review; not a Case D blocker)")
    print("MISSING_LIVE_CASES: " + ", ".join(pending_labels) + "; A/I/J/L recovered reports remain guided/history only, with no native result inferred from synthetic traces.")
    print("PHASE11_QUALIFICATION: PARTIAL (B3, C, and D accepted; E/F/G/H/K fresh-root cases remain pending)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
