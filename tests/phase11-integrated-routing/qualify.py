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


def main() -> int:
    failures, documents = validate_corpus()
    static_failures = run_static_baseline_checks()
    reconciliation_failures = validate_case_b_reconciliation(load_json(HERE / "baseline.json"))
    for label in ("ARGUS_GATE_MARKER", "TALOS_GATE_MARKER", "ATLAS_GATE_MARKER", "HELIOS_GATE_MARKER", "THALES_GATE_MARKER", "ROOT_OWNER_MARKER", "NO_NESTED_CHILD_MARKER", "CORE_CHILD_CEILING_MARKER"):
        if label in static_failures:
            print(f"STATIC_{label}: FAIL")
        else:
            print(f"STATIC_{label}: PASS (presence-only; not model-behavior proof)")
    for trace in documents["traces"]["traces"]:
        if not any(failure.startswith(f"{trace.get('TRACE_ID')}: ") for failure in failures):
            print(f"{trace.get('TRACE_ID')}: PASS ({trace.get('EVIDENCE_CLASS')})")
    pending_fresh_root_cases = {"B", "C", "D", "E", "F", "G", "H", "K"}
    pending_labels: list[str] = []
    for action in documents["cases"].get("fresh_root_actions", []):
        case_id = action.get("case_id")
        if case_id in pending_fresh_root_cases:
            label = action.get("label", f"PHASE11_CASE_{case_id}_FRESH_ROOT")
            pending_labels.append(label)
            print(f"HUMAN_ACTION_REQUIRED {label}")
    if failures or reconciliation_failures:
        for failure in [*failures, *reconciliation_failures]:
            print(f"FAIL: {failure}")
        print("PHASE11_QUALIFICATION: FAIL (artifact validation only)")
        return 1
    if static_failures:
        for label in static_failures:
            print(f"FAIL: STATIC_{label}")
        print("PHASE11_QUALIFICATION: FAIL (bounded policy marker check)")
        return 1
    print("PHASE11_ARTIFACTS: PASS (synthetic/static artifacts and reconciled report record are internally valid; report data is not reconstructed native event evidence)")
    print("MISSING_LIVE_CASES: " + ", ".join(pending_labels) + "; A/I/J/L recovered reports remain reference-only, with no native result inferred from synthetic traces.")
    print("PHASE11_QUALIFICATION: PARTIAL (artifacts PASS; Case B acceptance awaits isolated B3, and other listed fresh-root cases remain pending)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
