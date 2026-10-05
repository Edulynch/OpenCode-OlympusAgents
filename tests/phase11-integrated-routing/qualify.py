#!/usr/bin/env python3
"""Small, evidence-aware semantic validator for Phase 11 qualification artifacts.

This validates authored fixture traces and bounded policy markers.  It is not a
router, runtime observer, installer check, or proof of model behavior.
"""

from __future__ import annotations

import hashlib
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
CASE_E1_PENDING_LABELS = [
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_E_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_F_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT",
]
CURRENT_PHASE11_PENDING_LABELS = [
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT",
]
CASE_F_PENDING_LABELS = [
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT",
]
CASE_E2_PENDING_LABELS = [
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_F_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT",
    "HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT",
]
CURRENT_PHASE11_FRESH_ROOT_STATE = (
    "B3_PASS; C_PASS; D_PASS; E2_PASS (E1 routing failure retained as historical); F_PASS; G_PASS; H,K_PENDING"
)
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
CASE_E_ROOT_SESSION_ID = "ses_ef85bfb20ffeJDAs5WvP6mQNiP"
CASE_E_ROOT_DIRECTORY = "C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-e"
CASE_E_ROOT_HEAD = "314a6bc529e0d5e17d1662e3765734b7cc80cd86"
CASE_E_ROOT_TERMINAL_MESSAGE_ID = "msg_107a40611001npv8Iw2mdWMDAA"
CASE_E_ROOT_OUTCOME_MESSAGE_ID = "msg_107a4842f001hhVbJJOjM5TQdC"
CASE_E_USER_MESSAGE_ID = "msg_107a404e4001UY2IIX9U53JNmM"
CASE_E_EXPECTED_ROUTE = ["kael", "talos"]
CASE_E_ACTUAL_ROUTE = ["kael"]
CASE_E_NATIVE_RESULT = "NATIVE_EXECUTED_ROUTING_FAIL"
CASE_E_CLASSIFICATIONS = {
    "CASE_E_BEHAVIOR": "PASS",
    "CASE_E_SECURITY_CLASSIFICATION": "PASS",
    "CASE_E_SECURITY_BOUNDARY": "PASS",
    "CASE_E_SAFE_VALIDATION": "PASS",
    "CASE_E_SAFETY": "PASS",
    "CASE_E_ROLE_PURITY": "PASS",
    "CASE_E_NEGATIVE_ARGUS_CONTROL": "PASS",
    "CASE_E_TALOS_ACTIVATION": "FAIL",
    "CASE_E_ROUTING": "FAIL",
    "CASE_E_FRESH_ROOT_NATIVE_ACCEPTANCE": "FAIL",
}
CASE_E_ROLE_COUNTS = {role: 0 for role in ALL_INVOCABLE_ROLES}
CASE_E1_FRESH_ROOT_STATE = (
    "B3_PASS; C_PASS; D_PASS; E_NATIVE_EXECUTED_ROUTING_FAIL (acceptance pending); F,G,H,K_PENDING"
)
CASE_E2_LABEL = "PHASE11_CASE_E2_FRESH_ROOT"
CASE_E2_SCENARIO = "E2_AFTER_ROUTING_FIX"
CASE_E2_ROOT_SESSION_ID = "ses_ef7eb1d45ffet0gMtEEUam8R4U"
CASE_E2_CHILD_SESSION_ID = "ses_ef7ea7bf7ffe4U23sL7M1mi60p"
CASE_E2_ROOT_STARTING_HEAD = "3e5b2af2c15f9ef2775be3c3f5667edd4db0bdde"
CASE_E2_ROOT_TERMINAL_MESSAGE_ID = "msg_10815cfae001A2M4kLRGYUKmim"
CASE_E2_ROOT_OUTCOME_MESSAGE_ID = "msg_108160f11001WJh7C5F2Af7Fjq"
CASE_E2_ROOT_USER_MESSAGE_ID = "msg_10814e2c0001tCz9PXoRCTrZlr"
CASE_E2_ROOT_TOOL_MESSAGE_ID = "msg_10814e44b0013BwVGjWAtJ5bI0"
CASE_E2_ROOT_TOOL_CALL_ID = "call_FzRbkaOiUp41wcA0DcJfrrPw"
CASE_E2_CHILD_TERMINAL_MESSAGE_ID = "msg_108158539001dmAoz2pmGe7UbG"
CASE_E2_CHILD_OUTCOME_MESSAGE_ID = "msg_10815cec9001nEiTyrQRxUINQM"
CASE_E2_CHILD_USER_MESSAGE_ID = "msg_108158527002QGsXxMzV3Uxnmr"
CASE_E2_EXPECTED_ROUTE = ["kael", "talos"]
CASE_E2_NATIVE_RESULT = "NATIVE_EXECUTED_ROUTING_PASS"
CASE_E2_CURRENT_PHASE_STATE = (
    "B3_PASS; C_PASS; D_PASS; E2_PASS (E1 routing failure retained as historical); F,G,H,K_PENDING"
)
CASE_E2_ROLE_COUNTS = {role: 0 for role in ALL_INVOCABLE_ROLES}
CASE_E2_ROLE_COUNTS["talos"] = 1
CASE_E2_CLASSIFICATIONS = {
    "CASE_E2_BEHAVIOR": "PASS",
    "CASE_E2_SECURITY_CLASSIFICATION": "PASS",
    "CASE_E2_SAFETY": "PASS",
    "CASE_E2_ROLE_PURITY": "PASS",
    "CASE_E2_TALOS_ACTIVATION": "PASS",
    "CASE_E2_NEGATIVE_ARGUS_CONTROL": "PASS",
    "CASE_E2_ROUTING": "PASS",
    "CASE_E2_RESULT_FIDELITY": "PASS",
    "CASE_E2_COMPLETION_OWNERSHIP": "PASS",
    "CASE_E2_FRESH_ROOT_NATIVE": "PASS",
}
CASE_F_LABEL = "PHASE11_CASE_F_FRESH_ROOT"
CASE_F_ROOT_SESSION_ID = "ses_ef6a0d293ffeggS6H8JnsTARAW"
CASE_F_COLLECTOR_SESSION_ID = "ses_ef69769d4ffeOolSaq4q5CN7EI"
CASE_F_ROOT_DIRECTORY = "C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-f"
CASE_F_ROOT_STARTING_HEAD = "627946defc9eef0eb25e15d9d8b2865b7d6960ad"
CASE_F_ROOT_TITLE = "Windows command-unavailable environment issue"
CASE_F_ROOT_USER_MESSAGE_ID = "msg_1095f2d70001yQlPWbonusnuKa"
CASE_F_ROOT_TERMINAL_MESSAGE_ID = "msg_1095f2e910011Hmw2KfRXxqMw7"
CASE_F_ROOT_IDLE_MESSAGE_ID = "msg_1095f74b4001R44GqxRV7jViXp"
CASE_F_EXPECTED_ROUTE = ["kael"]
CASE_F_ROLE_COUNTS = {role: 0 for role in ALL_INVOCABLE_ROLES}
CASE_F_CLASSIFICATIONS = {
    "CASE_F_BEHAVIOR": "PASS",
    "CASE_F_OPERATIONAL_CLASSIFICATION": "PASS",
    "CASE_F_NO_PRODUCT_BUG_INVENTED": "PASS",
    "CASE_F_NO_SECURITY_BUG_INVENTED": "PASS",
    "CASE_F_NEGATIVE_ARGUS_CONTROL": "PASS",
    "CASE_F_NEGATIVE_TALOS_CONTROL": "PASS",
    "CASE_F_NO_INSTALL": "PASS",
    "CASE_F_ROLE_PURITY": "PASS",
    "CASE_F_COMPLETION_OWNERSHIP": "PASS",
    "CASE_F_ROUTING": "PASS",
    "CASE_F_FRESH_ROOT_NATIVE": "PASS",
}
CASE_F_TERMINAL_FACTS = {
    "CLASSIFICATION": "OPERATIONAL_ISSUE — plain `python` is unavailable in the Windows shell; test execution did not start.",
    "PRODUCT_BUG_ESTABLISHED": "NO",
    "SECURITY_BUG_ESTABLISHED": "NO",
    "SMALLEST_SAFE_NEXT_ACTION": "Recommend invoking the original targeted unittest command through the known working `uv run --python 3.11 python` runtime, without installation or configuration changes. Do not execute tests during this diagnosis.",
    "EVIDENCE_REQUIRED_FOR_PRODUCT_BUG": "An actual failure after tests start under a working runtime, supported by expected behavior and evidence attributing the failure to product code rather than the environment or test harness.",
    "INSTALL_ATTEMPTED": "NO",
    "FILES_CHANGED": "NONE",
    "UNRESOLVED_WORK": "NONE",
    "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED": "YES",
    "ANY_WORK_REMAINING": "NO",
}
CASE_G_LABEL = "PHASE11_CASE_G_FRESH_ROOT"
CASE_G_ROOT_SESSION_ID = "ses_ef3d4954bffeHMU8o3nWFjf6EP"
CASE_G_ROOT_DIRECTORY = "C:/Users/BLAUTECH/AppData/Local/Temp/olympus-phase11-case-g"
CASE_G_ROOT_WINDOWS_DIRECTORY = CASE_G_ROOT_DIRECTORY.replace("/", "\\")
CASE_G_ROOT_HEAD = "e3636c062a3a6db3ccebd4fbdff69acf1173bf99"
CASE_G_ROOT_TITLE = "Read-only diagnosis of intermittent observations fixture"
CASE_G_ROOT_USER_MESSAGE_ID = "msg_10c2b6ab9001ZLjHXX0JfQoQrs"
CASE_G_ROOT_USER_PROMPT_SHA256 = "77FDF180ED0D90BF0FD23742AB86BB747A08BB4399701DB4809DD275AC85E7D8"
CASE_G_ROOT_VEYRA_MESSAGE_ID = "msg_10c2b6be5001vwuEXvTOo0xskF"
CASE_G_ROOT_THALES_MESSAGE_ID = "msg_10c2bfeea001cM0D5Y3nfgAUkF"
CASE_G_ROOT_TERMINAL_MESSAGE_ID = "msg_10c2d05be0012Dg2Rpzb6aUNMy"
CASE_G_ROOT_IDLE_MESSAGE_ID = "msg_10c2d2b57001xBqfhbbMBm1iCA"
CASE_G_VEYRA_SESSION_ID = "ses_ef3d436eeffefhfC3CHLrYorMG"
CASE_G_VEYRA_USER_MESSAGE_ID = "msg_10c2bca51001OrJjv1qXjt5JQh"
CASE_G_VEYRA_USER_PROMPT_SHA256 = "EFC50834DD77AFB8AAE98EECD8205EBBEF275AD580EF4B7237BCE273FB8FE65B"
CASE_G_VEYRA_READ_MESSAGE_ID = "msg_10c2bca7d001Np34ZVxAqQT5Lm"
CASE_G_VEYRA_READ_CALL_ID = "call_axU3cxBfC0QRwZ90jk9yLNlV"
CASE_G_VEYRA_TERMINAL_MESSAGE_ID = "msg_10c2bdbb1001nrByoALlwcHbCp"
CASE_G_VEYRA_IDLE_MESSAGE_ID = "msg_10c2bfdc6001016ETthcuT1PqF"
CASE_G_THALES_SESSION_ID = "ses_ef3d386abffeVKv396Rg46d5Ls"
CASE_G_THALES_USER_MESSAGE_ID = "msg_10c2c7a84001qJjkJ997lidz9p"
CASE_G_THALES_USER_PROMPT_SHA256 = "621EC9D060B355F0F3D4DB7A94D60B1E8598B3A08CB68A23F71BD1AD6D7808C4"
CASE_G_THALES_TERMINAL_MESSAGE_ID = "msg_10c2c7aaf001QnQ9OkAut43aHF"
CASE_G_THALES_IDLE_MESSAGE_ID = "msg_10c2d04e1001lMSjeE0QmvFAdd"
CASE_G_VEYRA_ROOT_CALL_ID = "call_tr3IllNvxfWefARWraSij01y"
CASE_G_THALES_ROOT_CALL_ID = "call_FFOFQnncfDZDt201HQks5Gkt"
CASE_G_EXPECTED_ROUTE = ["kael", "veyra", "thales"]
CASE_G_EXPECTED_FOLLOWUP = {
    "CONSULTATION_COUNT": 1,
    "EVIDENCE_REQUEST_MADE": False,
    "MATERIALLY_NEW_EVIDENCE_NEEDED": False,
    "FOLLOWUP_STATUS": "NOT_REQUIRED",
    "FOLLOWUP_CONSULTATION_COUNT": 0,
    "FOLLOWUP_SESSION_ID": None,
    "SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE": "NOT_EXERCISED",
    "BASIS": "Thales reports that additional metadata is not materially necessary and recommends stopping; no follow-up request or second consultation appears in the exports.",
}
CASE_G_RECONCILIATION_FILES_CHANGED = [
    "tests/phase11-integrated-routing/RUNME.md",
    "tests/phase11-integrated-routing/baseline.json",
    "tests/phase11-integrated-routing/baseline.md",
    "tests/phase11-integrated-routing/case-g.native-trace.json",
    "tests/phase11-integrated-routing/case-g.root.session-export.json",
    "tests/phase11-integrated-routing/case-g.thales.session-export.json",
    "tests/phase11-integrated-routing/case-g.veyra.session-export.json",
    "tests/phase11-integrated-routing/cases.json",
    "tests/phase11-integrated-routing/qualify.py",
    "tests/phase11-integrated-routing/test_qualify.py",
]
CASE_G_RECONCILIATION_NOTES = (
    "The fixed PASS/TIMEOUT/PASS sequence comes from a synthetic fixture and establishes recorded inconsistency only. "
    "Veyra's original bounded fixture read supplied source evidence before Thales; Nox remains the owner of any actual "
    "runtime measurement but performed none here. Thales reports that additional metadata is not materially necessary, "
    "so one consultation and no follow-up are supported; if material new evidence is requested in a future case, collect "
    "and consume it before continuing the same Thales session. Synthetic trace G remains a separate illustrative iterative "
    "example. The original root terminal reports FILES_CHANGED: NONE. This reconciliation performed no Case G rerun or "
    "runtime reproduction and did not access the disposable worktree; it changed only the scoped Phase 11 paths listed "
    "in RECONCILIATION_FILES_CHANGED."
)
CASE_G_BASELINE_SOURCE = (
    "Corrected, schema-guided projection of the exact completed public OpenCode V2 metadata and export responses, "
    "bound to the task-supplied Nox verification and root completion facts. The original Veyra fixture read is "
    "preserved as original-run work; this reconciliation performed no Case G rerun or runtime replay and did not "
    "access the disposable worktree."
)
CASE_G_ROOT_TERMINAL_FACTS = {
    "WORKTREE_ISOLATION": "SUPPLIED_VERIFIED",
    "OBSERVED_SEQUENCE": "Same input `item-7`, quantity `2`: PASS → TIMEOUT → PASS",
    "ADDITIONAL_DISCRIMINATING_EVIDENCE_USED": "NO",
    "DIAGNOSIS": "Synthetic records establish same-input outcome inconsistency, not reproduced runtime flakiness or a deterministic root cause.",
    "CONFIDENCE": "HIGH in recorded inconsistency; causal confidence unestablished",
    "SUPPORTED_CAUSE": "UNCONFIRMED",
    "RANDOM_RERUNS": "0",
    "FILES_CHANGED": "NONE",
    "UNRESOLVED_WORK": "NONE",
    "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED": "YES",
    "ANY_WORK_REMAINING": "NO",
}
CASE_G_VEYRA_TERMINAL_TEXT = (
    "STATUS: SUCCESS\n\nSUMMARY:\nINPUT_IDENTITY_VALUE: Same input — id `item-7`, quantity `2`.\n"
    "OBSERVED_SEQUENCE: ordinal 1 `PASS`; ordinal 2 `TIMEOUT`; ordinal 3 `PASS`.\n\n"
    "CHANGES: none\nFILES: `tests/phase11-integrated-routing/fixtures/flaky/observations.json` (read only)\n"
    "TESTS: not run\nACCEPTANCE: Fixed input identity/value and exact ordered outcomes recorded from the fixture.\n"
    "RISKS: Fixture observations only; no runtime execution facts established.\nBLOCKERS: none\n"
    "RECOMMENDATION: ACCEPT"
)
CASE_G_THALES_TERMINAL_TEXT = (
    "STATUS: ADVICE\n\nDIAGNOSIS: The supplied records show different outcomes for the same fixed input. "
    "They establish recorded inconsistency—not reproduced runtime flakiness or a causal diagnosis.\n\n"
    "EVIDENCE: Input `item-7`, quantity `2`; ordered outcomes `PASS → TIMEOUT → PASS`. Evidence is synthetic; "
    "this task performed no executions.\n\nALTERNATIVE_HYPOTHESES: Unrecorded contextual differences and synthetic "
    "fixture construction remain possible explanations; neither is established or favored.\n\n"
    "MISSING_EVIDENCE: No causal evidence is supplied. Additional metadata is not materially necessary for this "
    "smallest supported conclusion.\n\nRECOMMENDED_NEXT_ACTION: Stop at recorded outcome inconsistency with cause "
    "unconfirmed. Do not request another read merely to seek specificity.\n\nRECOMMENDED_ROLE: none\n\n"
    "EXECUTION_DECISION: STOP\n\nRISKS: Treating identical input as identical execution conditions; mistaking fixture "
    "records for reproduced behavior; attributing the timeout to an unsupported cause.\n\n"
    "CONFIDENCE: High in the recorded inconsistency; causal confidence cannot be assessed.\n\n"
    "SUPPORTED_CAUSE: UNCONFIRMED"
)
CASE_G_ROLE_COUNTS = {role: 0 for role in ALL_INVOCABLE_ROLES}
CASE_G_ROLE_COUNTS["veyra"] = 1
CASE_G_ROLE_COUNTS["thales"] = 1
CASE_G_NEGATIVE_ROLES = ("nox", "argus", "talos", "kovan", "orin", "atlas", "helios", "aegis", "vera")
CASE_G_CLASSIFICATIONS = {
    "CASE_G_FRESH_ROOT_NATIVE": "PASS",
    "CASE_G_EVIDENCE_BEFORE_ESCALATION": "PASS",
    "CASE_G_THALES_DIAGNOSIS": "PASS",
    "CASE_G_NO_UNNEEDED_FOLLOWUP": "PASS",
    "CASE_G_NO_RERUN": "PASS",
    "CASE_G_NO_INVENTED_CAUSE": "PASS",
    "CASE_G_ROLE_PURITY": "PASS",
    "CASE_G_RESULT_FIDELITY": "PASS",
    "CASE_G_COMPLETION_OWNERSHIP": "PASS",
    "CASE_G_THALES_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE": "NOT_EXERCISED",
}
CASE_E_TERMINAL_FACTS = {
    "WORKTREE_ISOLATION": "SUPPLIED_VERIFIED",
    "SECURITY_CLASSIFICATION": "CONFIRMED_SECURITY_DEFECT under the supplied established behavior: authorization bypass. Unauthorized deletion violates account integrity and availability, making this materially security-specific rather than merely incorrect functional behavior.",
    "VIOLATED_BOUNDARY": "A MEMBER crosses the server-enforced privilege boundary protecting ADMIN-only account deletion and acts on another user’s account.",
    "EXPECTED_INVARIANT": "Account deletion requires an authenticated, authorized ADMIN. MEMBER requests must be denied without deletion side effects, regardless of target account or caller-supplied role claims.",
    "SAFE_VALIDATION": (
        "For a future fix, use synthetic identities and mocked deletion operations; no real accounts or exploit attempts. Verify:\n"
        "- MEMBER deleting another account: denied; deletion operation never invoked.\n"
        "- MEMBER deleting their own account: denied under the stated ADMIN-only contract.\n"
        "- Changing target identifiers or supplying an ADMIN role claim cannot bypass denial.\n"
        "- Anonymous, missing-role, and other non-ADMIN callers: denied.\n"
        "- Authenticated ADMIN deleting a valid permitted target: allowed; mocked deletion invoked as expected.\n"
        "- Every supported deletion entry point enforces the same invariant."
    ),
    "EXPLOIT_ATTEMPTED": "NO",
    "FILES_CHANGED": "NONE",
    "UNRESOLVED_WORK": "NONE",
    "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED": "YES",
    "ANY_WORK_REMAINING": "NO",
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
    required_dependency_edges = list(case.get("mandatory_dependency_edges", []))
    if evidence_class == "SYNTHETIC_TRACE":
        required_dependency_edges.extend(case.get("synthetic_illustrative_dependency_edges", []))
    for required in required_dependency_edges:
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
        (".opencode/agents/kael.md", "## Security Routing Gate — Talos required for established boundaries", "TALOS_GATE_MARKER"),
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
            or current.get("fresh_root_native") != CURRENT_PHASE11_FRESH_ROOT_STATE
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
        or current.get("fresh_root_native") != CURRENT_PHASE11_FRESH_ROOT_STATE
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
    if report.get("pending_fresh_root_labels") != CASE_E1_PENDING_LABELS:
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
        or current.get("fresh_root_native") != CURRENT_PHASE11_FRESH_ROOT_STATE
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


def validate_native_case_e_capture(
    trace: dict[str, Any], case: dict[str, Any], root_export: dict[str, Any]
) -> list[str]:
    """Validate Case E's native expected routing failure without promoting it to a pass."""
    errors: list[str] = []
    cases = case if isinstance(case, dict) else {}
    expected_routes = cases.get("expected_routes", {})
    matrix_route = expected_routes.get("default") if isinstance(expected_routes, dict) else None
    if (
        cases.get("id") != "E"
        or cases.get("request_class") != "SECURITY_BUG"
        or matrix_route != CASE_E_EXPECTED_ROUTE
        or trace.get("CASE_ID") != "E"
        or trace.get("SCENARIO") != "default"
        or trace.get("REQUEST_CLASS") != "SECURITY_BUG"
        or trace.get("EVIDENCE_CLASS") != "FRESH_ROOT_NATIVE"
    ):
        errors.append("NATIVE_E_IDENTITY_OR_EXPECTATION_MISMATCH")
    if (
        trace.get("ROOT_SESSION_ID") != CASE_E_ROOT_SESSION_ID
        or trace.get("ROOT_DIRECTORY", "").replace("\\", "/") != CASE_E_ROOT_DIRECTORY
        or trace.get("ROOT_AGENT") != "kael"
        or trace.get("ROOT_PARENT_SESSION_ID") is not None
        or trace.get("ROOT_PARENT_SESSION_ID_OBSERVATION") != "NOT_EXPOSED"
        or trace.get("ROOT_TITLE") != "Authorization defect classification for account deletion"
        or trace.get("ROOT_EXECUTION_OUTCOME") != "succeeded"
        or trace.get("ROOT_TERMINAL_MESSAGE_ID") != CASE_E_ROOT_TERMINAL_MESSAGE_ID
        or trace.get("ROOT_OUTCOME_MESSAGE_ID") != CASE_E_ROOT_OUTCOME_MESSAGE_ID
        or trace.get("ROOT_STARTING_HEAD") != CASE_E_ROOT_HEAD
    ):
        errors.append("NATIVE_E_ROOT_IDENTITY_OR_OUTCOME_MISMATCH")

    isolation = trace.get("ROOT_ISOLATION", {})
    if (
        isolation.get("WORKTREE_ISOLATION") != "SUPPLIED_VERIFIED"
        or isolation.get("STARTING_HEAD_SOURCE") != "Original user prompt"
        or isolation.get("SEPARATE_DISPOSABLE_WORKTREE") is not None
        or isolation.get("FILESYSTEM_AUDIT_PERFORMED") is not False
    ):
        errors.append("NATIVE_E_ISOLATION_SOURCE_OR_SCOPE_MISMATCH")

    export_session = root_export.get("session", {})
    if (
        root_export.get("evidence_class") != "FRESH_ROOT_NATIVE"
        or export_session.get("id") != CASE_E_ROOT_SESSION_ID
        or export_session.get("agent") != "kael"
        or export_session.get("directory", "").replace("\\", "/") != CASE_E_ROOT_DIRECTORY
        or export_session.get("title") != "Authorization defect classification for account deletion"
        or export_session.get("execution_outcome") != "succeeded"
        or export_session.get("parent_id") is not None
        or export_session.get("parent_id_observation") != "NOT_EXPOSED"
        or root_export.get("terminal_message_id") != CASE_E_ROOT_TERMINAL_MESSAGE_ID
        or root_export.get("terminal_outcome_record", {}).get("message_id") != CASE_E_ROOT_OUTCOME_MESSAGE_ID
        or root_export.get("terminal_outcome_record", {}).get("outcome") != "succeeded"
    ):
        errors.append("NATIVE_E_EXPORT_SESSION_RECONCILIATION_MISMATCH")
    projection = root_export.get("projection_and_redaction", {})
    export_query = root_export.get("export_query", {})
    if (
        export_query.get("path") != f"/api/experimental/session/{CASE_E_ROOT_SESSION_ID}/export?sanitize=false"
        or export_query.get("result") != "SUCCESS"
        or projection.get("raw_export_persisted") is not False
        or projection.get("reasoning_blocks_removed") != 1
        or projection.get("secret_values_redacted") != 0
        or projection.get("unrecognized_content_blocks_omitted") != 0
    ):
        errors.append("NATIVE_E_EXPORT_PROJECTION_OR_REASONING_REDACTION_MISMATCH")
    export_child_query = root_export.get("direct_child_query", {})
    export_child_response = export_child_query.get("response", {})
    if (
        export_child_query.get("path") != f"/api/session?parentID={CASE_E_ROOT_SESSION_ID}"
        or export_child_query.get("result") != "SUCCESS"
        or export_child_response.get("parent_id") != CASE_E_ROOT_SESSION_ID
        or export_child_response.get("count") != 0
        or export_child_response.get("children") != []
        or export_child_response.get("cursor_next") is not None
        or export_child_response.get("pages") != 1
    ):
        errors.append("NATIVE_E_EXPORT_CHILD_QUERY_MISMATCH")
    messages = root_export.get("messages", [])
    if [message.get("type") for message in messages] != ["user", "assistant", "idle"]:
        errors.append("NATIVE_E_EXPORTED_MESSAGE_SEQUENCE_MISMATCH")
    user = messages[0] if len(messages) > 0 and isinstance(messages[0], dict) else {}
    assistant = messages[1] if len(messages) > 1 and isinstance(messages[1], dict) else {}
    if user.get("id") != CASE_E_USER_MESSAGE_ID or assistant.get("id") != CASE_E_ROOT_TERMINAL_MESSAGE_ID:
        errors.append("NATIVE_E_EXPORTED_MESSAGE_ID_MISMATCH")
    user_text = user.get("text") if isinstance(user.get("text"), str) else ""
    if (
        "PHASE11_CASE_E_FRESH_ROOT" not in user_text
        or "Use the smallest sufficient security-specific route." not in user_text
        or "Do NOT:" not in user_text
        or "Do not route to Argus merely because the request contains the word \"bug\"." not in user_text
        or user_text.startswith("[redacted:")
    ):
        errors.append("NATIVE_E_ORIGINAL_USER_PROMPT_NOT_PRESERVED")
    assistant_content = assistant.get("content", [])
    if any(
        re.search(r"reason|thought|analysis", str(part.get("type", "")), re.IGNORECASE)
        for part in assistant_content if isinstance(part, dict)
    ):
        errors.append("NATIVE_E_REASONING_BLOCK_PERSISTED")
    assistant_text = "\n".join(
        part.get("text", "")
        for part in assistant_content
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
    ).replace("\r\n", "\n")
    for label, value in CASE_E_TERMINAL_FACTS.items():
        if f"{label}:\n{value}" not in assistant_text:
            errors.append(f"NATIVE_E_TERMINAL_TEXT_FACT_MISSING:{label}")
    if not assistant_text or assistant_text.startswith("[redacted:"):
        errors.append("NATIVE_E_ASSISTANT_TERMINAL_TEXT_NOT_PRESERVED")
    if messages[-1].get("id") != CASE_E_ROOT_OUTCOME_MESSAGE_ID or messages[-1].get("outcome") != "succeeded":
        errors.append("NATIVE_E_ROOT_OUTCOME_MESSAGE_MISMATCH")

    api = trace.get("API_EVIDENCE", {})
    child_query = api.get("DIRECT_CHILD_QUERY", {})
    if (
        child_query.get("PATH") != f"/api/session?parentID={CASE_E_ROOT_SESSION_ID}"
        or child_query.get("RESULT") != "SUCCESS"
        or child_query.get("PARENT_SESSION_ID") != CASE_E_ROOT_SESSION_ID
        or child_query.get("CHILD_COUNT") != 0
        or child_query.get("CHILDREN") != []
        or child_query.get("CURSOR_NEXT") is not None
        or child_query.get("PAGES") != 1
        or api.get("ROOT_TOOL_CALL_RECORDS") != []
        or api.get("ROOT_TOOL_CALL_RECORD_COUNT") != 0
        or root_export.get("tool_call_records") != []
    ):
        errors.append("NATIVE_E_CHILD_OR_TOOL_OBSERVATION_MISMATCH")
    if trace.get("CHILD_SESSIONS") != []:
        errors.append("NATIVE_E_CHILD_SESSION_SET_MISMATCH")
    if trace.get("CONSULTATION_COUNTS") != CASE_E_ROLE_COUNTS:
        errors.append("NATIVE_E_SPECIALIST_COUNTS_MISMATCH")
    if trace.get("UNIQUE_CHILD_SESSION_COUNTS") != CASE_E_ROLE_COUNTS:
        errors.append("NATIVE_E_UNIQUE_CHILD_COUNTS_MISMATCH")
    if trace.get("MAX_SIMULTANEOUS_CHILDREN") is not None:
        errors.append("NATIVE_E_UNOBSERVED_CONCURRENCY_MUST_REMAIN_NULL")

    if trace.get("EXPECTED_ROUTE") != CASE_E_EXPECTED_ROUTE or matrix_route != CASE_E_EXPECTED_ROUTE:
        errors.append("NATIVE_E_TALOS_EXPECTATION_WEAKENED")
    child_roles = [child.get("AGENT") for child in trace.get("CHILD_SESSIONS", []) if isinstance(child, dict)]
    derived_route = ["kael", *child_roles]
    if trace.get("ACTUAL_ROUTE") != derived_route or derived_route != CASE_E_ACTUAL_ROUTE:
        errors.append("NATIVE_E_ACTUAL_ROUTE_OR_FABRICATED_CHILD_MISMATCH")
    if trace.get("ROUTE_RECONCILIATION", {}).get("CLASSIFICATION") != CASE_E_NATIVE_RESULT:
        errors.append("NATIVE_E_EXPECTED_ROUTING_FAILURE_NOT_RECORDED")

    if trace.get("OBSERVED_TERMINAL_SNAPSHOT", {}).get("FACTS") != CASE_E_TERMINAL_FACTS:
        errors.append("NATIVE_E_TERMINAL_SNAPSHOT_FACTS_MISMATCH")
    assessment = trace.get("SECURITY_ASSESSMENT", {})
    if (
        assessment.get("CLASSIFICATION") != "CONFIRMED_SECURITY_DEFECT"
        or assessment.get("EXPLOIT_ATTEMPTED") != "NO"
        or assessment.get("FILES_CHANGED") != "NONE"
        or "ADMIN" not in assessment.get("EXPECTED_INVARIANT", "")
        or "synthetic identities" not in assessment.get("SAFE_VALIDATION", "").lower()
        or "mocked deletion operations" not in assessment.get("SAFE_VALIDATION", "").lower()
    ):
        errors.append("NATIVE_E_SECURITY_OR_SAFETY_EVIDENCE_MISMATCH")
    role_purity = trace.get("ROLE_PURITY", {})
    if (
        role_purity.get("STATUS") != "PASS"
        or role_purity.get("ROOT_AGENT") != "kael"
        or role_purity.get("NESTED_DELEGATION_OBSERVED") is not False
        or role_purity.get("ROOT_SOURCE_WRITES_OBSERVED") is not False
        or role_purity.get("EXPLOIT_ATTEMPTED") != "NO"
        or role_purity.get("VIOLATIONS") != []
    ):
        errors.append("NATIVE_E_ROLE_PURITY_OR_SAFETY_MISMATCH")
    negative = trace.get("NEGATIVE_CONTROLS", {})
    argus = negative.get("argus", {})
    if (
        argus.get("INVOCATIONS") != 0
        or argus.get("UNIQUE_CHILD_SESSIONS") != 0
        or argus.get("STATUS") != "PASS"
        or trace.get("CONSULTATION_COUNTS", {}).get("argus") != 0
    ):
        errors.append("NATIVE_E_NEGATIVE_ARGUS_CONTROL_NOT_PASS")
    talos = negative.get("talos", {})
    if (
        talos.get("INVOCATIONS") != 0
        or talos.get("UNIQUE_CHILD_SESSIONS") != 0
        or talos.get("STATUS") != "FAIL"
    ):
        errors.append("NATIVE_E_TALOS_ACTIVATION_FAILURE_NOT_RECORDED")
    if trace.get("CONSULTATION_COUNTS", {}).get("talos") != 0:
        errors.append("NATIVE_E_FABRICATED_TALOS_ACTIVATION")

    if trace.get("CLASSIFICATIONS") != CASE_E_CLASSIFICATIONS:
        errors.append("NATIVE_E_CLASSIFICATION_STATUS_MISMATCH")
    result = trace.get("RESULT_FIDELITY", {})
    if (
        result.get("EXPECTED_PRODUCT_ROUTE") != CASE_E_EXPECTED_ROUTE
        or result.get("OBSERVED_PRODUCT_ROUTE") != CASE_E_ACTUAL_ROUTE
        or result.get("ROUTE_MATCHES") is not False
        or result.get("SECURITY_BEHAVIOR_MATCHES") is not True
        or result.get("ROOT_EXECUTION_OUTCOME") != "succeeded"
        or result.get("CASE_ACCEPTANCE") != "FAIL"
    ):
        errors.append("NATIVE_E_RESULT_FIDELITY_OR_EXECUTION_ACCEPTANCE_CONFLATED")
    unknowns = trace.get("UNKNOWN_METRICS", {})
    if (
        unknowns.get("MAX_SIMULTANEOUS_CHILDREN") is not None
        or unknowns.get("PER_INVOCATION_RESULT_IDS") is not None
        or unknowns.get("SESSION_LIFETIME_EXACT_ONCE") is not None
        or unknowns.get("NATIVE_PERMISSION_UI") != "NOT_OBSERVABLE"
        or unknowns.get("NATIVE_PERMISSION_DECISION") != "NOT_OBSERVABLE"
        or unknowns.get("WORKTREE_FILESYSTEM_AUDIT") != "NOT_PERFORMED"
    ):
        errors.append("NATIVE_E_UNKNOWN_OR_UNOBSERVED_METRIC_OVERCLAIM")
    if (
        trace.get("CASE_RESULT") != CASE_E_NATIVE_RESULT
        or trace.get("CASE_ACCEPTANCE") != "FAIL"
        or trace.get("CASE_RERUN_PERFORMED_BY_RECONCILIATION") is not False
        or trace.get("CORE_POLICY_MODIFIED") is not False
    ):
        errors.append("NATIVE_E_FAILURE_PROMOTED_OR_PROHIBITED_ACTION_CLAIMED")
    return errors


def validate_phase11_e_reconciliation(
    baseline: dict[str, Any],
    cases_doc: dict[str, Any],
    trace: dict[str, Any],
    root_export: dict[str, Any],
) -> list[str]:
    """Bind Case E native evidence and its expected routing failure to Phase 11 state."""
    cases = {
        case.get("id"): case
        for case in cases_doc.get("cases", [])
        if isinstance(case, dict)
    }
    errors = validate_native_case_e_capture(trace, cases.get("E", {}), root_export)
    report = baseline.get("phase11_e_reconciliation")
    if not isinstance(report, dict):
        return errors + ["CASE_E_RECONCILIATION_MISSING"]
    if (
        report.get("task_id") != "P11-E-RECON-RECORD"
        or report.get("label") != "PHASE11_CASE_E_FRESH_ROOT"
        or report.get("evidence_artifact") != "tests/phase11-integrated-routing/case-e.native-trace.json"
        or report.get("export_artifact") != "tests/phase11-integrated-routing/case-e.root-session.export.json"
        or report.get("evidence_class") != "FRESH_ROOT_NATIVE"
    ):
        errors.append("CASE_E_EVIDENCE_LINK_OR_LABEL_MISMATCH")
    if (
        report.get("root_session_id") != CASE_E_ROOT_SESSION_ID
        or report.get("root_directory", "").replace("\\", "/") != CASE_E_ROOT_DIRECTORY
        or report.get("root_agent") != "kael"
        or report.get("root_parent_session_id") is not None
        or report.get("root_parent_session_id_observation") != "NOT_EXPOSED"
        or report.get("root_title") != "Authorization defect classification for account deletion"
        or report.get("root_terminal_outcome") != "succeeded"
        or report.get("root_terminal_message_id") != CASE_E_ROOT_TERMINAL_MESSAGE_ID
        or report.get("root_outcome_message_id") != CASE_E_ROOT_OUTCOME_MESSAGE_ID
        or report.get("root_starting_head") != CASE_E_ROOT_HEAD
    ):
        errors.append("CASE_E_BASELINE_ROOT_RECONCILIATION_MISMATCH")
    if (
        report.get("expected_product_route") != CASE_E_EXPECTED_ROUTE
        or report.get("observed_product_route") != CASE_E_ACTUAL_ROUTE
        or report.get("direct_child_count") != 0
        or report.get("root_tool_call_record_count") != 0
        or report.get("consultation_counts") != CASE_E_ROLE_COUNTS
        or report.get("unique_child_session_counts") != CASE_E_ROLE_COUNTS
    ):
        errors.append("CASE_E_BASELINE_ROUTE_OR_COUNTS_MISMATCH")
    if report.get("classifications") != CASE_E_CLASSIFICATIONS:
        errors.append("CASE_E_BASELINE_CLASSIFICATIONS_MISMATCH")
    if (
        report.get("terminal_facts") != CASE_E_TERMINAL_FACTS
        or report.get("isolation", {}).get("status") != "SUPPLIED_VERIFIED"
        or report.get("isolation", {}).get("starting_head") != CASE_E_ROOT_HEAD
        or report.get("isolation", {}).get("separate_disposable_worktree") is not None
        or report.get("isolation", {}).get("filesystem_audit_performed") is not False
    ):
        errors.append("CASE_E_BASELINE_TERMINAL_OR_ISOLATION_FACTS_MISMATCH")
    cause = report.get("route_cause", {})
    required_citations = {
        "olympus/harnesses/opencode/agent-prompts/kael.md:286-292",
        "olympus/harnesses/opencode/agent-prompts/talos.md:25-27",
        "olympus/policies/routing.md:5-7",
        "tests/phase11-integrated-routing/cases.json:96-106",
        "tests/phase11-integrated-routing/RUNME.md:199-202",
    }
    if (
        cause.get("classification") != "CONFIRMED_INTENDED_PRODUCT_ROUTING_GAP"
        or cause.get("likely_cause") != "SECURITY_GATE_WORDING_MISMATCH"
        or cause.get("internal_model_rationale_claimed") is not False
        or cause.get("security_classification_defect_claimed") is not False
        or not required_citations.issubset(set(cause.get("evidence_citations", [])))
    ):
        errors.append("CASE_E_ROOT_CAUSE_BOUNDS_OR_CITATIONS_MISMATCH")
    if (
        report.get("acceptance_status") != "FAIL"
        or report.get("case_result") != CASE_E_NATIVE_RESULT
        or report.get("phase11_status") != "PARTIAL"
        or report.get("case_rerun_performed_by_reconciliation") is not False
        or report.get("core_policy_modified") is not False
    ):
        errors.append("CASE_E_ROUTING_FAILURE_PROMOTED_OR_REPLAYED")
    if report.get("pending_fresh_root_labels") != CASE_E1_PENDING_LABELS:
        errors.append("CASE_E_PENDING_LABELS_MISMATCH")
    if report.get("argus_same_session_followup_runtime_coverage") != "NOT_EXERCISED":
        errors.append("CASE_E_ARGUS_FOLLOWUP_COVERAGE_PROMOTED")

    current = baseline.get("live_qualification", {})
    if not isinstance(current, dict) or (
        current.get("pending_labels") != CURRENT_PHASE11_PENDING_LABELS
        or current.get("fresh_root_native") != CURRENT_PHASE11_FRESH_ROOT_STATE
        or current.get("native_results_claimed") is not True
        or current.get("overall_status") != "PARTIAL"
    ):
        errors.append("CURRENT_PHASE11_PENDING_STATE_MISMATCH")
    if baseline.get("argus_same_session_followup_runtime_coverage") != CASE_D_PENDING_FOLLOWUP_COVERAGE:
        errors.append("ARGUS_FOLLOWUP_RUNTIME_COVERAGE_PROMOTED_OR_CONFLATED")
    actions = [
        action for action in cases_doc.get("fresh_root_actions", [])
        if isinstance(action, dict)
        and action.get("case_id") == "E"
        and action.get("label") == "PHASE11_CASE_E_FRESH_ROOT"
    ]
    expected_action = {
        "scenario": "default",
        "status": CASE_E_NATIVE_RESULT,
        "evidence_class": "FRESH_ROOT_NATIVE",
        "evidence_artifact": "case-e.native-trace.json",
        "acceptance_status": "FAIL",
        "pending_resolution": True,
    }
    if len(actions) != 1 or any(actions[0].get(key) != value for key, value in expected_action.items()):
        errors.append("CASE_E_MATRIX_FAILURE_OR_EVIDENCE_LINK_MISMATCH")
    return errors


def _export_message(export: dict[str, Any], message_id: str) -> dict[str, Any] | None:
    messages = export.get("messages", [])
    if not isinstance(messages, list):
        return None
    found = [message for message in messages if isinstance(message, dict) and message.get("id") == message_id]
    return found[0] if len(found) == 1 else None


def _export_text(export: dict[str, Any], message_id: str) -> str:
    message = _export_message(export, message_id)
    if message is None:
        return ""
    return "\n".join(
        part.get("text", "")
        for part in message.get("content", [])
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _export_content_types(export: dict[str, Any]) -> list[str]:
    types: list[str] = []
    for message in export.get("messages", []):
        if isinstance(message, dict) and message.get("type") == "assistant":
            types.extend(
                str(part.get("type"))
                for part in message.get("content", [])
                if isinstance(part, dict)
            )
    return types


def validate_native_case_e2_capture(
    trace: dict[str, Any],
    case: dict[str, Any],
    root_export: dict[str, Any],
    child_export: dict[str, Any],
) -> list[str]:
    """Validate E2's observed Talos route while retaining E1 as failed history."""
    errors: list[str] = []
    case = case if isinstance(case, dict) else {}
    root_export = root_export if isinstance(root_export, dict) else {}
    child_export = child_export if isinstance(child_export, dict) else {}
    expected_routes = case.get("expected_routes", {})
    matrix_route = expected_routes.get(CASE_E2_SCENARIO) if isinstance(expected_routes, dict) else None

    if (
        case.get("id") != "E"
        or case.get("request_class") != "SECURITY_BUG"
        or matrix_route != CASE_E2_EXPECTED_ROUTE
        or trace.get("CASE_ID") != "E"
        or trace.get("ATTEMPT_ID") != "E2"
        or trace.get("SCENARIO") != CASE_E2_SCENARIO
        or trace.get("REQUEST_CLASS") != "SECURITY_BUG"
        or trace.get("EVIDENCE_CLASS") != "FRESH_ROOT_NATIVE"
    ):
        errors.append("NATIVE_E2_IDENTITY_OR_EXPECTATION_MISMATCH")

    if (
        trace.get("ROOT_SESSION_ID") != CASE_E2_ROOT_SESSION_ID
        or trace.get("ROOT_DIRECTORY_METADATA_MATCH") is not True
        or trace.get("ROOT_AGENT") != "kael"
        or trace.get("ROOT_PARENT_SESSION_ID") is not None
        or trace.get("ROOT_PARENT_SESSION_ID_OBSERVATION") != "EXPLICIT_NULL"
        or trace.get("ROOT_TITLE") != "Diagnosing MEMBER account-deletion authorization boundary"
        or trace.get("ROOT_EXECUTION_OUTCOME") != "succeeded"
        or trace.get("ROOT_TERMINAL_MESSAGE_ID") != CASE_E2_ROOT_TERMINAL_MESSAGE_ID
        or trace.get("ROOT_OUTCOME_MESSAGE_ID") != CASE_E2_ROOT_OUTCOME_MESSAGE_ID
        or trace.get("ROOT_USER_MESSAGE_ID") != CASE_E2_ROOT_USER_MESSAGE_ID
        or trace.get("ROOT_TOOL_CALL_MESSAGE_ID") != CASE_E2_ROOT_TOOL_MESSAGE_ID
        or trace.get("ROOT_STARTING_HEAD") != CASE_E2_ROOT_STARTING_HEAD
    ):
        errors.append("NATIVE_E2_ROOT_IDENTITY_OR_OUTCOME_MISMATCH")

    isolation = trace.get("ROOT_ISOLATION", {})
    if (
        isolation.get("WORKTREE_ISOLATION") != "SUPPLIED_VERIFIED"
        or isolation.get("LOCATION_MATCHED_SUPPLIED_DISPOSABLE_PATH") is not True
        or isolation.get("STARTING_HEAD_SOURCE") != "Original root user prompt"
        or isolation.get("SEPARATE_DISPOSABLE_WORKTREE") is not None
        or isolation.get("FILESYSTEM_AUDIT_PERFORMED") is not False
    ):
        errors.append("NATIVE_E2_ISOLATION_SOURCE_OR_SCOPE_MISMATCH")

    provenance = trace.get("EVIDENCE_PROVENANCE", {})
    if (
        provenance.get("CLASS") != "FRESH_ROOT_NATIVE"
        or provenance.get("NATIVE_ROOT_SESSION_ID") != CASE_E2_ROOT_SESSION_ID
        or provenance.get("NATIVE_CHILD_SESSION_IDS") != [CASE_E2_CHILD_SESSION_ID]
        or provenance.get("ORDER_BASIS") != "observed"
        or provenance.get("FRESH_ROOT_CONFIRMED") is not True
    ):
        errors.append("NATIVE_E2_PROVENANCE_OR_FRESH_ROOT_MISMATCH")

    root_session = root_export.get("session", {})
    root_meta_query = root_export.get("session_metadata_query", {})
    root_export_query = root_export.get("export_query", {})
    root_projection = root_export.get("projection_and_redaction", {})
    root_messages_query = root_export.get("message_list_query", {})
    if (
        root_export.get("evidence_class") != "FRESH_ROOT_NATIVE"
        or root_meta_query.get("method") != "GET"
        or root_meta_query.get("path") != f"/api/session/{CASE_E2_ROOT_SESSION_ID}"
        or root_meta_query.get("result") != "SUCCESS"
        or root_export_query.get("method") != "GET"
        or root_export_query.get("path") != f"/api/experimental/session/{CASE_E2_ROOT_SESSION_ID}/export?sanitize=false"
        or root_export_query.get("result") != "SUCCESS"
        or root_session.get("id") != CASE_E2_ROOT_SESSION_ID
        or root_session.get("agent") != "kael"
        or root_session.get("parent_id") is not None
        or root_session.get("parent_id_observation") != "EXPLICIT_NULL"
        or root_session.get("directory_observation") != "MATCHED_SUPPLIED_DISPOSABLE_PATH; exact metadata path omitted from this projection"
        or root_session.get("title") != "Diagnosing MEMBER account-deletion authorization boundary"
        or root_session.get("execution_outcome") != "succeeded"
    ):
        errors.append("NATIVE_E2_ROOT_EXPORT_METADATA_MISMATCH")
    if (
        root_messages_query.get("method") != "GET"
        or root_messages_query.get("path") != f"/api/session/{CASE_E2_ROOT_SESSION_ID}/message?limit=100&order=asc"
        or root_messages_query.get("result") != "SUCCESS"
        or root_messages_query.get("pages") != 2
        or root_messages_query.get("cursor_next") is not None
        or root_messages_query.get("message_count") != 4
        or root_messages_query.get("message_ids") != [
            CASE_E2_ROOT_USER_MESSAGE_ID,
            CASE_E2_ROOT_TOOL_MESSAGE_ID,
            CASE_E2_ROOT_TERMINAL_MESSAGE_ID,
            CASE_E2_ROOT_OUTCOME_MESSAGE_ID,
        ]
        or root_messages_query.get("message_types") != ["user", "assistant", "assistant", "idle"]
    ):
        errors.append("NATIVE_E2_ROOT_MESSAGE_API_RECONCILIATION_MISMATCH")
    if (
        root_projection.get("raw_export_persisted") is not False
        or root_projection.get("reasoning_blocks_removed") != 2
        or root_projection.get("secret_values_redacted") != 0
        or root_projection.get("unrecognized_content_blocks_omitted") != 0
        or any(re.search(r"(?i)reason|thought|analysis", kind) for kind in _export_content_types(root_export))
    ):
        errors.append("NATIVE_E2_ROOT_EXPORT_PROJECTION_OR_REASONING_REDACTION_MISMATCH")

    root_messages = root_export.get("messages", [])
    if [message.get("type") for message in root_messages if isinstance(message, dict)] != [
        "user", "assistant", "assistant", "idle"
    ]:
        errors.append("NATIVE_E2_ROOT_MESSAGE_SEQUENCE_MISMATCH")
    root_user = _export_message(root_export, CASE_E2_ROOT_USER_MESSAGE_ID) or {}
    root_prompt = root_user.get("text", "") if isinstance(root_user.get("text"), str) else ""
    root_terminal_text = _export_text(root_export, CASE_E2_ROOT_TERMINAL_MESSAGE_ID)
    if (
        CASE_E2_LABEL not in root_prompt
        or CASE_E2_ROOT_STARTING_HEAD not in root_prompt
        or "MEMBER" not in root_prompt
        or "ADMIN" not in root_prompt
        or "Use the smallest sufficient route" not in root_prompt
        or "PHASE11_CASE_E2_FRESH_ROOT" not in root_prompt
    ):
        errors.append("NATIVE_E2_ORIGINAL_ROOT_PROMPT_OR_LABEL_NOT_PRESERVED")
    required_root_phrases = (
        "SECURITY_CLASSIFICATION:\nCONFIRMED_SECURITY_DEFECT",
        "VIOLATED_BOUNDARY:\nServer-side authorization for account deletion",
        "FIX_DIRECTION:\nRequire authenticated ADMIN authorization from trusted identity/role information",
        "SAFE_VALIDATION:\nFuture non-destructive tests using a mocked deletion service",
        "These tests were not run.",
        "EXPLOIT_ATTEMPTED:\nNO",
        "FILES_CHANGED:\nNONE",
        "UNRESOLVED_WORK:\nNONE for this diagnosis",
        "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED:\nYES",
        "ANY_WORK_REMAINING:\nNO",
    )
    if not root_terminal_text or any(phrase not in root_terminal_text for phrase in required_root_phrases):
        errors.append("NATIVE_E2_ROOT_TERMINAL_FACTS_NOT_PRESERVED")
    if root_export.get("terminal_message_id") != CASE_E2_ROOT_TERMINAL_MESSAGE_ID or (
        root_export.get("terminal_outcome_record", {}).get("message_id") != CASE_E2_ROOT_OUTCOME_MESSAGE_ID
        or root_export.get("terminal_outcome_record", {}).get("outcome") != "succeeded"
    ):
        errors.append("NATIVE_E2_ROOT_TERMINAL_OUTCOME_MESSAGE_MISMATCH")

    expected_tool_call = {
        "id": CASE_E2_ROOT_TOOL_CALL_ID,
        "name": "subagent",
        "state": "completed",
        "agent": "talos",
        "task_label": CASE_E2_LABEL,
        "child_session_id": CASE_E2_CHILD_SESSION_ID,
        "result_id": None,
    }
    if root_export.get("tool_call_records") != [expected_tool_call]:
        errors.append("NATIVE_E2_ROOT_TOOL_CALL_OR_CHILD_JOIN_MISMATCH")
    tool_message = _export_message(root_export, CASE_E2_ROOT_TOOL_MESSAGE_ID) or {}
    tool_parts = [
        part for part in tool_message.get("content", [])
        if isinstance(part, dict) and part.get("type") == "tool"
    ]
    if len(tool_parts) != 1 or any(
        tool_parts[0].get(key) != value
        for key, value in {
            "id": CASE_E2_ROOT_TOOL_CALL_ID,
            "name": "subagent",
            "state": "completed",
            "agent": "talos",
            "task_label": CASE_E2_LABEL,
            "child_session_id": CASE_E2_CHILD_SESSION_ID,
        }.items()
    ):
        errors.append("NATIVE_E2_ROOT_TOOL_MESSAGE_STUB_MISMATCH")

    child_session = child_export.get("session", {})
    child_meta_query = child_export.get("session_metadata_query", {})
    child_export_query = child_export.get("export_query", {})
    child_projection = child_export.get("projection_and_redaction", {})
    child_messages_query = child_export.get("message_list_query", {})
    if (
        child_export.get("evidence_class") != "FRESH_ROOT_NATIVE"
        or child_meta_query.get("method") != "GET"
        or child_meta_query.get("path") != f"/api/session/{CASE_E2_CHILD_SESSION_ID}"
        or child_meta_query.get("result") != "SUCCESS"
        or child_export_query.get("method") != "GET"
        or child_export_query.get("path") != f"/api/experimental/session/{CASE_E2_CHILD_SESSION_ID}/export?sanitize=false"
        or child_export_query.get("result") != "SUCCESS"
        or child_session.get("id") != CASE_E2_CHILD_SESSION_ID
        or child_session.get("agent") != "talos"
        or child_session.get("parent_id") != CASE_E2_ROOT_SESSION_ID
        or child_session.get("parent_id_observation") != "EXPLICIT_ID"
        or child_session.get("directory_observation") != "MATCHED_SUPPLIED_DISPOSABLE_PATH; exact metadata path omitted from this projection"
        or child_session.get("title") != "Diagnose account deletion authorization"
        or child_session.get("execution_outcome") != "succeeded"
    ):
        errors.append("NATIVE_E2_CHILD_EXPORT_PARENT_OR_METADATA_MISMATCH")
    if (
        child_messages_query.get("method") != "GET"
        or child_messages_query.get("path") != f"/api/session/{CASE_E2_CHILD_SESSION_ID}/message?limit=100&order=asc"
        or child_messages_query.get("result") != "SUCCESS"
        or child_messages_query.get("pages") != 2
        or child_messages_query.get("cursor_next") is not None
        or child_messages_query.get("message_count") != 3
        or child_messages_query.get("message_ids") != [
            CASE_E2_CHILD_USER_MESSAGE_ID,
            CASE_E2_CHILD_TERMINAL_MESSAGE_ID,
            CASE_E2_CHILD_OUTCOME_MESSAGE_ID,
        ]
        or child_messages_query.get("message_types") != ["user", "assistant", "idle"]
    ):
        errors.append("NATIVE_E2_CHILD_MESSAGE_API_RECONCILIATION_MISMATCH")
    if (
        child_projection.get("raw_export_persisted") is not False
        or child_projection.get("reasoning_blocks_removed") != 0
        or child_projection.get("secret_values_redacted") != 0
        or child_projection.get("unrecognized_content_blocks_omitted") != 0
        or any(re.search(r"(?i)reason|thought|analysis", kind) for kind in _export_content_types(child_export))
        or child_export.get("tool_call_records") != []
    ):
        errors.append("NATIVE_E2_CHILD_EXPORT_PROJECTION_OR_TOOL_BOUNDARY_MISMATCH")
    child_messages = child_export.get("messages", [])
    if [message.get("type") for message in child_messages if isinstance(message, dict)] != ["user", "assistant", "idle"]:
        errors.append("NATIVE_E2_CHILD_MESSAGE_SEQUENCE_MISMATCH")
    child_user = _export_message(child_export, CASE_E2_CHILD_USER_MESSAGE_ID) or {}
    child_prompt = child_user.get("text", "") if isinstance(child_user.get("text"), str) else ""
    child_terminal_text = _export_text(child_export, CASE_E2_CHILD_TERMINAL_MESSAGE_ID)
    required_child_phrases = (
        "TASK_ID: PHASE11_CASE_E2_FRESH_ROOT",
        "ROLE: talos",
        "STATUS: SECURITY_DIAGNOSIS",
        "CLASSIFICATION: SECURITY_BUG — CONFIRMED_SECURITY_DEFECT",
        "SECURITY_BOUNDARY: ADMIN-only authorization for account deletion",
        "CAUSE: Authorization enforcement fails for the established case. The implementation mechanism is unconfirmed",
        "FIX_DIRECTION: Enforce authenticated ADMIN authorization server-side, using trusted identity and role information",
        "Future non-destructive tests using a mocked deletion service",
        "EXECUTION: No tools, exploits, tests, repository access, or file mutations attempted.",
        "COMPLETION: Security diagnosis complete.",
    )
    if (
        CASE_E2_LABEL not in child_prompt
        or CASE_E2_ROOT_STARTING_HEAD not in child_prompt
        or any(phrase not in child_terminal_text for phrase in required_child_phrases[2:])
    ):
        errors.append("NATIVE_E2_TALOS_DIAGNOSIS_OR_SOURCE_UNCERTAINTY_MISMATCH")
    if child_export.get("terminal_message_id") != CASE_E2_CHILD_TERMINAL_MESSAGE_ID or (
        child_export.get("terminal_outcome_record", {}).get("message_id") != CASE_E2_CHILD_OUTCOME_MESSAGE_ID
        or child_export.get("terminal_outcome_record", {}).get("outcome") != "succeeded"
    ):
        errors.append("NATIVE_E2_CHILD_TERMINAL_OUTCOME_MESSAGE_MISMATCH")

    direct_query = root_export.get("direct_child_query", {})
    direct_response = direct_query.get("response", {})
    expected_direct_child = {
        "id": CASE_E2_CHILD_SESSION_ID,
        "agent": "talos",
        "parent_id": CASE_E2_ROOT_SESSION_ID,
        "title": "Diagnose account deletion authorization",
        "outcome": "succeeded",
        "directory_matches_supplied_disposable_path": True,
    }
    if (
        direct_query.get("method") != "GET"
        or direct_query.get("path") != f"/api/session?parentID={CASE_E2_ROOT_SESSION_ID}&limit=100"
        or direct_query.get("result") != "SUCCESS"
        or direct_response.get("parent_id") != CASE_E2_ROOT_SESSION_ID
        or direct_response.get("count") != 1
        or direct_response.get("children") != [expected_direct_child]
        or direct_response.get("cursor_next") is not None
        or direct_response.get("pages") != 2
    ):
        errors.append("NATIVE_E2_DIRECT_CHILD_QUERY_OR_PARENT_JOIN_MISMATCH")

    api = trace.get("API_EVIDENCE", {})
    api_child_query = api.get("DIRECT_CHILD_QUERY", {})
    if (
        api_child_query.get("PATH") != f"/api/session?parentID={CASE_E2_ROOT_SESSION_ID}&limit=100"
        or api_child_query.get("RESULT") != "SUCCESS"
        or api_child_query.get("PARENT_SESSION_ID") != CASE_E2_ROOT_SESSION_ID
        or api_child_query.get("CHILD_COUNT") != 1
        or api_child_query.get("CURSOR_NEXT") is not None
        or api_child_query.get("PAGES") != 2
        or api.get("ROOT_TOOL_CALL_RECORDS") != [{
            "CALL_ID": CASE_E2_ROOT_TOOL_CALL_ID,
            "NAME": "subagent",
            "STATE": "completed",
            "AGENT": "talos",
            "TASK_LABEL": CASE_E2_LABEL,
            "CHILD_SESSION_ID": CASE_E2_CHILD_SESSION_ID,
            "RESULT_ID": None,
        }]
        or api.get("ROOT_TOOL_CALL_RECORD_COUNT") != 1
        or api.get("CHILD_TOOL_CALL_RECORDS") != []
    ):
        errors.append("NATIVE_E2_API_TOOL_OR_CHILD_OBSERVATION_MISMATCH")

    children = trace.get("CHILD_SESSIONS", [])
    if not isinstance(children, list) or len(children) != 1:
        errors.append("NATIVE_E2_CHILD_SESSION_SET_MISMATCH")
        children = []
    expected_child = {
        "TRACE_REF": "E2-TALOS",
        "NATIVE_SESSION_ID": CASE_E2_CHILD_SESSION_ID,
        "AGENT": "talos",
        "PARENT_AGENT": "kael",
        "PARENT_SESSION_ID": CASE_E2_ROOT_SESSION_ID,
        "LAUNCH_ORDER": 1,
        "INVOCATION_COUNT": 1,
        "EXECUTION_STATE": "SUCCEEDED",
        "FINAL_OUTCOME": "succeeded",
        "RESULT_ID": None,
        "TITLE": "Diagnose account deletion authorization",
        "PURPOSE": "Bounded security diagnosis using the established authorization facts; no repository discovery or execution.",
        "PARENT_MESSAGE_ID": CASE_E2_ROOT_TOOL_MESSAGE_ID,
        "INVOCATION_TOOL_CALL_ID": CASE_E2_ROOT_TOOL_CALL_ID,
        "TOOL_STATE": "completed",
        "TOOL_TASK_LABEL": CASE_E2_LABEL,
        "TERMINAL_MESSAGE_ID": CASE_E2_CHILD_TERMINAL_MESSAGE_ID,
        "OUTCOME_MESSAGE_ID": CASE_E2_CHILD_OUTCOME_MESSAGE_ID,
    }
    if children != [expected_child]:
        errors.append("NATIVE_E2_CHILD_SESSION_PARENT_ROLE_OR_RESULT_JOIN_MISMATCH")
    child_roles = [child.get("AGENT") for child in children]
    derived_route = ["kael", *child_roles]
    if (
        trace.get("EXPECTED_ROUTE") != CASE_E2_EXPECTED_ROUTE
        or matrix_route != CASE_E2_EXPECTED_ROUTE
        or trace.get("ACTUAL_ROUTE") != derived_route
        or derived_route != CASE_E2_EXPECTED_ROUTE
        or trace.get("ROUTE_RECONCILIATION", {}).get("EXPECTED_PRODUCT_ROUTE") != CASE_E2_EXPECTED_ROUTE
        or trace.get("ROUTE_RECONCILIATION", {}).get("OBSERVED_UNIQUE_CHILD_SESSION_LAUNCH_ORDER") != CASE_E2_EXPECTED_ROUTE
        or trace.get("ROUTE_RECONCILIATION", {}).get("CLASSIFICATION") != CASE_E2_NATIVE_RESULT
    ):
        errors.append("NATIVE_E2_ROUTE_OR_EXPECTATION_MISMATCH")
    if (
        trace.get("CONSULTATION_COUNTS") != CASE_E2_ROLE_COUNTS
        or trace.get("UNIQUE_CHILD_SESSION_COUNTS") != CASE_E2_ROLE_COUNTS
        or trace.get("ROOT_SUBAGENT_CALL_INVOCATION_COUNTS") != {"talos": 1}
    ):
        errors.append("NATIVE_E2_SPECIALIST_OR_INVOCATION_COUNTS_MISMATCH")
    negative = trace.get("NEGATIVE_CONTROLS", {})
    argus = negative.get("argus", {})
    if (
        argus.get("INVOCATIONS") != 0
        or argus.get("UNIQUE_CHILD_SESSIONS") != 0
        or argus.get("STATUS") != "PASS"
        or trace.get("CONSULTATION_COUNTS", {}).get("argus") != 0
        or any(trace.get("CONSULTATION_COUNTS", {}).get(role) != 0 for role in ("kovan", "orin", "atlas", "thales", "helios", "aegis"))
    ):
        errors.append("NATIVE_E2_NEGATIVE_ARGUS_OR_FORBIDDEN_ROLE_CONTROL_MISMATCH")

    role_purity = trace.get("ROLE_PURITY", {})
    if (
        role_purity.get("STATUS") != "PASS"
        or role_purity.get("ROOT_AGENT") != "kael"
        or role_purity.get("ALL_CHILDREN_DIRECT") is not True
        or role_purity.get("NESTED_DELEGATION_OBSERVED") is not False
        or role_purity.get("REVIEWER_EDITS_OBSERVED") is not False
        or role_purity.get("ROOT_SOURCE_WRITES_OBSERVED") is not False
        or role_purity.get("EXPLOIT_ATTEMPTED") != "NO"
        or role_purity.get("VIOLATIONS") != []
    ):
        errors.append("NATIVE_E2_ROLE_PURITY_OR_SAFETY_MISMATCH")

    if trace.get("CLASSIFICATIONS") != CASE_E2_CLASSIFICATIONS:
        errors.append("NATIVE_E2_CLASSIFICATION_STATUS_MISMATCH")
    result = trace.get("RESULT_FIDELITY", {})
    if (
        result.get("EXPECTED_PRODUCT_ROUTE") != CASE_E2_EXPECTED_ROUTE
        or result.get("OBSERVED_PRODUCT_ROUTE") != CASE_E2_EXPECTED_ROUTE
        or result.get("ROUTE_MATCHES") is not True
        or result.get("SECURITY_BEHAVIOR_MATCHES") is not True
        or result.get("ROOT_EXECUTION_OUTCOME") != "succeeded"
        or result.get("CASE_ACCEPTANCE") != "PASS"
        or "not an explicit literal PASS" not in result.get("CASE_ACCEPTANCE_BASIS", "")
    ):
        errors.append("NATIVE_E2_RESULT_FIDELITY_OR_EXECUTION_ACCEPTANCE_MISMATCH")
    if (
        trace.get("COMPLETION_GATE", {}).get("PENDING_CHILD_COUNT") != 0
        or trace.get("COMPLETION_GATE", {}).get("UNCONSUMED_RESULT_COUNT") != 0
        or trace.get("COMPLETION_GATE", {}).get("UNKNOWN_EXECUTION_COUNT") != 0
        or trace.get("COMPLETION_GATE", {}).get("REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED") is not True
        or trace.get("COMPLETION_GATE", {}).get("PER_INVOCATION_RESULT_IDS") is not None
        or trace.get("COMPLETION_GATE", {}).get("PER_INVOCATION_CONSUMPTION_TIMING") is not None
        or trace.get("COMPLETION_GATE", {}).get("SESSION_LIFETIME_EXACT_ONCE") is not None
    ):
        errors.append("NATIVE_E2_COMPLETION_OR_RESULT_ID_OVERCLAIM")
    consumption = trace.get("RESULT_CONSUMPTION", {})
    if (
        consumption.get("ROOT_AGGREGATE_STATEMENT") != "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED: YES"
        or consumption.get("PENDING_CHILDREN") != 0
        or consumption.get("UNCONSUMED_RESULTS") != 0
        or consumption.get("UNKNOWN_EXECUTIONS") != 0
        or consumption.get("RESULT_IDS") is not None
        or consumption.get("PER_INVOCATION_CONSUMPTION_TIMING") is not None
        or consumption.get("SESSION_LIFETIME_EXACT_ONCE") is not None
    ):
        errors.append("NATIVE_E2_RESULT_CONSUMPTION_RECONCILIATION_MISMATCH")
    unknowns = trace.get("UNKNOWN_METRICS", {})
    if (
        unknowns.get("MAX_SIMULTANEOUS_CHILDREN") is not None
        or unknowns.get("PER_INVOCATION_RESULT_IDS") is not None
        or unknowns.get("PER_INVOCATION_CONSUMPTION_TIMING") is not None
        or unknowns.get("SESSION_LIFETIME_EXACT_ONCE") is not None
        or unknowns.get("TIMING_METRICS") is not None
        or unknowns.get("NATIVE_PERMISSION_UI") != "NOT_OBSERVABLE"
        or unknowns.get("NATIVE_PERMISSION_DECISION") != "NOT_OBSERVABLE"
        or unknowns.get("WORKTREE_FILESYSTEM_AUDIT") != "NOT_PERFORMED"
        or trace.get("MAX_SIMULTANEOUS_CHILDREN") is not None
        or trace.get("OBSERVED_SEQUENCE", {}).get("MAX_SIMULTANEOUS_CHILDREN") is not None
        or trace.get("OBSERVED_SEQUENCE", {}).get("TIMING_METRICS") is not None
    ):
        errors.append("NATIVE_E2_UNKNOWN_OR_UNOBSERVED_METRIC_OVERCLAIM")
    if trace.get("EFFICIENCY", {}).get("CLASSIFICATION") != "LEAN" or trace.get("EFFICIENCY", {}).get("BASIS") != (
        "One required direct Talos consultation; no latency, throughput, or concurrency claim."
    ):
        errors.append("NATIVE_E2_EFFICIENCY_BASIS_MISMATCH")

    history = trace.get("E1_HISTORICAL_ATTEMPT", {})
    if (
        history.get("LABEL") != "PHASE11_CASE_E_FRESH_ROOT"
        or history.get("ROOT_SESSION_ID") != CASE_E_ROOT_SESSION_ID
        or history.get("RESULT") != CASE_E_NATIVE_RESULT
        or history.get("EXPECTED_ROUTE") != CASE_E_EXPECTED_ROUTE
        or history.get("ACTUAL_ROUTE") != CASE_E_ACTUAL_ROUTE
        or history.get("ACCEPTANCE_STATUS") != "FAIL"
        or history.get("ARTIFACTS_PRESERVED") is not True
    ):
        errors.append("NATIVE_E2_E1_FAILED_HISTORY_REWRITTEN_OR_MISJOINED")
    if (
        trace.get("CASE_RESULT") != CASE_E2_NATIVE_RESULT
        or trace.get("CASE_ACCEPTANCE") != "PASS"
        or trace.get("CASE_RERUN_PERFORMED_BY_RECONCILIATION") is not False
        or trace.get("CORE_POLICY_MODIFIED") is not False
        or trace.get("FINAL_OUTCOME") != "SUCCEEDED"
        or trace.get("USER_QUESTION_COUNT") != 0
    ):
        errors.append("NATIVE_E2_ACCEPTANCE_OR_PROHIBITED_ACTION_CLAIM_MISMATCH")
    return errors


def validate_phase11_e2_reconciliation(
    baseline: dict[str, Any],
    cases_doc: dict[str, Any],
    trace: dict[str, Any],
    root_export: dict[str, Any],
    child_export: dict[str, Any],
) -> list[str]:
    """Bind E2 native evidence to latest Phase 11 state without rewriting E1."""
    cases = {
        case.get("id"): case
        for case in cases_doc.get("cases", [])
        if isinstance(case, dict)
    }
    errors = validate_native_case_e2_capture(trace, cases.get("E", {}), root_export, child_export)
    report = baseline.get("phase11_e2_reconciliation")
    if not isinstance(report, dict):
        return errors + ["CASE_E2_RECONCILIATION_MISSING"]
    if (
        report.get("task_id") != "PH11-E2-CLOSURE"
        or report.get("label") != CASE_E2_LABEL
        or report.get("attempt") != "E2"
        or report.get("evidence_artifact") != "tests/phase11-integrated-routing/case-e2.native-trace.json"
        or report.get("root_export_artifact") != "tests/phase11-integrated-routing/case-e2.root-session.export.json"
        or report.get("child_export_artifact") != "tests/phase11-integrated-routing/case-e2.talos-session.export.json"
        or report.get("evidence_class") != "FRESH_ROOT_NATIVE"
    ):
        errors.append("CASE_E2_EVIDENCE_LINK_OR_LABEL_MISMATCH")
    if (
        report.get("root_session_id") != CASE_E2_ROOT_SESSION_ID
        or report.get("root_directory_metadata_match") is not True
        or report.get("root_directory_path_persisted") is not False
        or report.get("root_agent") != "kael"
        or report.get("root_parent_session_id") is not None
        or report.get("root_parent_session_id_observation") != "EXPLICIT_NULL"
        or report.get("root_title") != "Diagnosing MEMBER account-deletion authorization boundary"
        or report.get("root_terminal_outcome") != "succeeded"
        or report.get("root_terminal_message_id") != CASE_E2_ROOT_TERMINAL_MESSAGE_ID
        or report.get("root_outcome_message_id") != CASE_E2_ROOT_OUTCOME_MESSAGE_ID
        or report.get("root_user_message_id") != CASE_E2_ROOT_USER_MESSAGE_ID
        or report.get("root_starting_head") != CASE_E2_ROOT_STARTING_HEAD
    ):
        errors.append("CASE_E2_BASELINE_ROOT_RECONCILIATION_MISMATCH")
    expected_report_tool = {
        "id": CASE_E2_ROOT_TOOL_CALL_ID,
        "name": "subagent",
        "state": "completed",
        "agent": "talos",
        "task_label": CASE_E2_LABEL,
        "child_session_id": CASE_E2_CHILD_SESSION_ID,
        "result_id": None,
    }
    if (
        report.get("root_tool_call") != expected_report_tool
        or report.get("child_sessions") != [{
            "role": "talos",
            "session_id": CASE_E2_CHILD_SESSION_ID,
            "parent_session_id": CASE_E2_ROOT_SESSION_ID,
            "title": "Diagnose account deletion authorization",
            "outcome": "succeeded",
            "invocation_count": 1,
            "tool_state": "completed",
            "tool_call_id": CASE_E2_ROOT_TOOL_CALL_ID,
            "terminal_message_id": CASE_E2_CHILD_TERMINAL_MESSAGE_ID,
            "result_id": None,
        }]
        or report.get("expected_product_route") != CASE_E2_EXPECTED_ROUTE
        or report.get("observed_product_route") != CASE_E2_EXPECTED_ROUTE
        or report.get("direct_child_count") != 1
        or report.get("root_tool_call_record_count") != 1
        or report.get("consultation_counts") != CASE_E2_ROLE_COUNTS
        or report.get("unique_child_session_counts") != CASE_E2_ROLE_COUNTS
    ):
        errors.append("CASE_E2_BASELINE_ROUTE_CHILD_OR_COUNTS_MISMATCH")
    if report.get("classifications") != CASE_E2_CLASSIFICATIONS:
        errors.append("CASE_E2_BASELINE_CLASSIFICATIONS_MISMATCH")
    if report.get("terminal_facts") != trace.get("OBSERVED_TERMINAL_SNAPSHOT", {}).get("FACTS"):
        errors.append("CASE_E2_BASELINE_TERMINAL_FACTS_MISMATCH")
    expected_consumption = {
        "root_aggregate_statement": "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED: YES",
        "pending_children": 0,
        "unconsumed_results": 0,
        "unknown_executions": 0,
        "result_ids": None,
        "per_invocation_consumption_timing": None,
        "session_lifetime_exact_once": None,
    }
    if report.get("result_consumption") != expected_consumption:
        errors.append("CASE_E2_BASELINE_RESULT_CONSUMPTION_MISMATCH")
    expected_isolation = {
        "status": "SUPPLIED_VERIFIED",
        "starting_head": CASE_E2_ROOT_STARTING_HEAD,
        "starting_head_source": "Original root user prompt",
        "directory_metadata_match": True,
        "directory_path_persisted": False,
        "separate_disposable_worktree": None,
        "filesystem_audit_performed": False,
    }
    if report.get("isolation") != expected_isolation:
        errors.append("CASE_E2_BASELINE_ISOLATION_SCOPE_MISMATCH")
    if (
        report.get("mechanism_uncertainty") != "Authorization enforcement failure is confirmed for the established case; the specific implementation mechanism is unconfirmed."
        or report.get("acceptance_status") != "PASS"
        or report.get("case_result") != CASE_E2_NATIVE_RESULT
        or report.get("phase11_status") != "PARTIAL"
        or report.get("case_rerun_performed_by_reconciliation") is not False
        or report.get("core_policy_modified") is not False
        or report.get("efficiency") != "LEAN"
    ):
        errors.append("CASE_E2_ACCEPTANCE_PHASE_OR_UNCERTAINTY_MISMATCH")
    expected_validation = {
        "phase11_qualifier": {
            "command": "uv run --python 3.11 python tests/phase11-integrated-routing/qualify.py",
            "exit_code": 0,
            "result": "PHASE11_ARTIFACTS: PASS; PHASE11_QUALIFICATION: PARTIAL",
        },
        "phase11_unittest": {
            "command": 'uv run --python 3.11 python -m unittest discover -s tests/phase11-integrated-routing -p "test_*.py" -v',
            "exit_code": 0,
            "test_count": 62,
            "result": "PASS",
        },
        "harness_core_safe_root": {
            "command": "uv run --python 3.11 python -B tests/harness-core/qualify.py --safe-root-read-only",
            "exit_code": 0,
            "result": "PASS",
            "managed_output_count_before": 29,
            "managed_output_count_after": 29,
            "hash_mtime_unchanged": True,
        },
        "renderer_check": {
            "command": "uv run --python 3.11 python scripts/render_harnesses.py check --harness all",
            "exit_code": 0,
            "result": "PASS (all; 29 managed output(s); read-only)",
        },
        "git_diff_check": {
            "command": "git diff --check",
            "exit_code": 0,
            "result": "PASS",
            "line_ending_warnings_only": True,
        },
    }
    if report.get("validation") != expected_validation:
        errors.append("CASE_E2_VALIDATION_RECORD_MISMATCH")
    if report.get("pending_fresh_root_labels") != CASE_E2_PENDING_LABELS:
        errors.append("CASE_E2_PENDING_LABELS_MISMATCH")
    if report.get("argus_same_session_followup_runtime_coverage") != "NOT_EXERCISED":
        errors.append("CASE_E2_ARGUS_FOLLOWUP_COVERAGE_PROMOTED")

    e1 = baseline.get("phase11_e_reconciliation", {})
    e1_history = report.get("e1_historical_attempt", {})
    if (
        e1.get("root_session_id") != CASE_E_ROOT_SESSION_ID
        or e1.get("acceptance_status") != "FAIL"
        or e1.get("case_result") != CASE_E_NATIVE_RESULT
        or e1.get("expected_product_route") != CASE_E_EXPECTED_ROUTE
        or e1.get("observed_product_route") != CASE_E_ACTUAL_ROUTE
        or e1_history.get("label") != "PHASE11_CASE_E_FRESH_ROOT"
        or e1_history.get("root_session_id") != CASE_E_ROOT_SESSION_ID
        or e1_history.get("acceptance_status") != "FAIL"
        or e1_history.get("case_result") != CASE_E_NATIVE_RESULT
        or e1_history.get("expected_product_route") != CASE_E_EXPECTED_ROUTE
        or e1_history.get("observed_product_route") != CASE_E_ACTUAL_ROUTE
        or e1_history.get("native_artifacts_unchanged") is not True
    ):
        errors.append("CASE_E2_E1_FAILED_HISTORICAL_ATTEMPT_NOT_PRESERVED")

    current = baseline.get("live_qualification", {})
    if not isinstance(current, dict) or (
        current.get("pending_labels") != CURRENT_PHASE11_PENDING_LABELS
        or current.get("fresh_root_native") != CURRENT_PHASE11_FRESH_ROOT_STATE
        or current.get("native_results_claimed") is not True
        or current.get("overall_status") != "PARTIAL"
        or "PH11-E2-CLOSURE" not in current.get("current_pending_state_source", "")
    ):
        errors.append("CURRENT_PHASE11_E2_PENDING_STATE_MISMATCH")
    if baseline.get("argus_same_session_followup_runtime_coverage") != CASE_D_PENDING_FOLLOWUP_COVERAGE:
        errors.append("ARGUS_FOLLOWUP_RUNTIME_COVERAGE_PROMOTED_OR_CONFLATED")

    actions = [
        action for action in cases_doc.get("fresh_root_actions", [])
        if isinstance(action, dict) and action.get("case_id") == "E"
    ]
    e1_actions = [action for action in actions if action.get("label") == "PHASE11_CASE_E_FRESH_ROOT"]
    e2_actions = [action for action in actions if action.get("label") == CASE_E2_LABEL]
    expected_e1_action = {
        "scenario": "default",
        "status": CASE_E_NATIVE_RESULT,
        "evidence_class": "FRESH_ROOT_NATIVE",
        "evidence_artifact": "case-e.native-trace.json",
        "acceptance_status": "FAIL",
        "pending_resolution": True,
    }
    expected_e2_action = {
        "scenario": CASE_E2_SCENARIO,
        "status": "PASS",
        "evidence_class": "FRESH_ROOT_NATIVE",
        "evidence_artifact": "case-e2.native-trace.json",
        "acceptance_status": "PASS",
        "pending_resolution": False,
        "attempt": "E2",
        "supersedes_latest_acceptance": "E1",
    }
    if len(e1_actions) != 1 or any(e1_actions[0].get(key) != value for key, value in expected_e1_action.items()):
        errors.append("CASE_E1_MATRIX_HISTORY_REWRITTEN_OR_MISLINKED")
    if len(e2_actions) != 1 or any(e2_actions[0].get(key) != value for key, value in expected_e2_action.items()):
        errors.append("CASE_E2_MATRIX_STATUS_OR_EVIDENCE_LINK_MISMATCH")
    recovered = baseline.get("recovered_user_observations", {}).get("case_observations", {})
    recovered_expected = {
        "A": {"reported_status": "PASS", "reported_mode": "GUIDED_CURRENT_SESSION"},
        "I": {"reported_status": "PARTIAL", "reported_mode": "GUIDED_CURRENT_SESSION"},
        "J": {"reported_status": "PASS", "reported_mode": "GUIDED_CURRENT_SESSION"},
        "L_negative_automatic_aegis_control": {"reported_status": "PASS"},
    }
    if any(
        not isinstance(recovered.get(case_id), dict)
        or any(recovered[case_id].get(key) != value for key, value in expected.items())
        for case_id, expected in recovered_expected.items()
    ):
        errors.append("CASE_E2_RECOVERED_A_I_J_L_HISTORY_PROMOTED_OR_CHANGED")
    return errors


def validate_native_case_f_capture(
    trace: dict[str, Any], case: dict[str, Any], root_export: dict[str, Any]
) -> list[str]:
    """Validate Case F's observed Kael-only operational diagnosis and safe projection."""
    errors: list[str] = []
    case = case if isinstance(case, dict) else {}
    trace = trace if isinstance(trace, dict) else {}
    root_export = root_export if isinstance(root_export, dict) else {}
    expected_routes = case.get("expected_routes", {})
    matrix_route = expected_routes.get("default") if isinstance(expected_routes, dict) else None

    required_fields = (
        "CASE_ID", "REQUEST_CLASS", "EXPECTED_ROUTE", "ACTUAL_ROUTE", "CHILD_SESSIONS",
        "CONSULTATION_COUNTS", "MAX_SIMULTANEOUS_CHILDREN", "NEGATIVE_CONTROLS",
        "ROLE_PURITY", "DEPENDENCY_ORDER", "RESULT_FIDELITY", "COMPLETION_GATE",
        "USER_QUESTION_COUNT", "FINAL_OUTCOME", "ROUTING_RESULT", "NOTES",
        "EVIDENCE_PROVENANCE",
    )
    missing = [field for field in required_fields if field not in trace]
    if missing:
        errors.append("NATIVE_F_REQUIRED_FIELDS_MISSING:" + ",".join(missing))

    if (
        case.get("id") != "F"
        or case.get("request_class") != "OPERATIONAL_TOOLING_ISSUE"
        or matrix_route != CASE_F_EXPECTED_ROUTE
        or trace.get("CASE_ID") != "F"
        or trace.get("SCENARIO") != "default"
        or trace.get("REQUEST_CLASS") != "OPERATIONAL_TOOLING_ISSUE"
        or trace.get("EVIDENCE_CLASS") != "FRESH_ROOT_NATIVE"
    ):
        errors.append("NATIVE_F_IDENTITY_OR_MATRIX_EXPECTATION_MISMATCH")

    if (
        trace.get("ROOT_SESSION_ID") != CASE_F_ROOT_SESSION_ID
        or trace.get("ROOT_DIRECTORY", "").replace("\\", "/") != CASE_F_ROOT_DIRECTORY
        or trace.get("ROOT_AGENT") != "kael"
        or trace.get("ROOT_PARENT_SESSION_ID") is not None
        or trace.get("ROOT_PARENT_SESSION_ID_OBSERVATION") != "NOT_EXPOSED"
        or trace.get("ROOT_TITLE") != CASE_F_ROOT_TITLE
        or trace.get("ROOT_EXECUTION_OUTCOME") != "succeeded"
        or trace.get("ROOT_USER_MESSAGE_ID") != CASE_F_ROOT_USER_MESSAGE_ID
        or trace.get("ROOT_TERMINAL_MESSAGE_ID") != CASE_F_ROOT_TERMINAL_MESSAGE_ID
        or trace.get("ROOT_IDLE_MESSAGE_ID") != CASE_F_ROOT_IDLE_MESSAGE_ID
        or trace.get("ROOT_STARTING_HEAD") != CASE_F_ROOT_STARTING_HEAD
        or trace.get("ROOT_STARTING_HEAD_SOURCE") != "Original root user prompt"
        or trace.get("ROOT_STARTING_HEAD_FILESYSTEM_VERIFIED") is not False
    ):
        errors.append("NATIVE_F_ROOT_IDENTITY_OR_UNVERIFIED_HEAD_MISMATCH")

    expected_isolation = {
        "WORKTREE_ISOLATION": "SUPPLIED_VERIFIED",
        "DIRECTORY_METADATA_MATCHES_PROMPT": True,
        "ROOT_ONLY_FILTERED_LIST_MEMBERSHIP": True,
        "STARTING_HEAD_SOURCE": "Original root user prompt",
        "STARTING_HEAD_FILESYSTEM_VERIFIED": False,
        "SEPARATE_DISPOSABLE_WORKTREE": None,
        "FILESYSTEM_AUDIT_PERFORMED": False,
    }
    if trace.get("ROOT_ISOLATION") != expected_isolation:
        errors.append("NATIVE_F_ISOLATION_OR_FILESYSTEM_AUDIT_OVERCLAIM")

    expected_provenance = {
        "CLASS": "FRESH_ROOT_NATIVE",
        "SOURCE": "Nox-supplied direct native OpenCode V2 read-only API reconciliation and complete root export projection; historical root not rerun.",
        "NATIVE_ROOT_SESSION_ID": CASE_F_ROOT_SESSION_ID,
        "NATIVE_CHILD_SESSION_IDS": [],
        "ORDER_BASIS": "NOT_APPLICABLE_NO_RUNTIME_EVENT_SEQUENCE_CAPTURED",
        "FRESH_ROOT_CONFIRMED": True,
        "CAPTURED_BY_ROLE": "nox",
        "CAPTURED_BY_SESSION_ID": CASE_F_COLLECTOR_SESSION_ID,
        "CAPTURE_SESSION_IS_ROOT_CHILD": False,
    }
    if trace.get("EVIDENCE_PROVENANCE") != expected_provenance:
        errors.append("NATIVE_F_ROOT_OR_CAPTURE_PROVENANCE_MISMATCH")
    if "EVENTS" in trace and trace.get("EVENTS") != []:
        errors.append("NATIVE_F_UNOBSERVED_RUNTIME_EVENTS_MUST_NOT_BE_ADDED")

    api = trace.get("API_EVIDENCE", {})
    expected_api = {
        "SOURCE": "OpenCode V2 public read-only API",
        "ROOT_METADATA_GET": {
            "PATH": f"/api/session/{CASE_F_ROOT_SESSION_ID}",
            "RESULT": "SUCCESS",
        },
        "ROOT_EXPORT_GET": {
            "PATH": f"/api/experimental/session/{CASE_F_ROOT_SESSION_ID}/export?sanitize=false",
            "RESULT": "SUCCESS",
            "PROJECTION_ARTIFACT": "case-f.root-session.export.json",
            "MESSAGE_COUNT": 3,
            "EXPORT_PAGINATION": "NONE_OBSERVED",
            "REASONING_BLOCKS_REMOVED": 1,
            "PROVIDER_STATE_AND_SNAPSHOTS_OMITTED": True,
            "RAW_EXPORT_PERSISTED": False,
            "SECRET_FILTERING": "NOT_ASSESSED_BY_NOX",
        },
        "DIRECT_CHILD_QUERY": {
            "PATH": f"/api/session?parentID={CASE_F_ROOT_SESSION_ID}",
            "RESULT": "SUCCESS",
            "PARENT_SESSION_ID": CASE_F_ROOT_SESSION_ID,
            "CHILD_COUNT": 0,
            "CHILDREN": [],
            "CURSOR_PREVIOUS": None,
            "CURSOR_NEXT": None,
            "PAGES": 1,
        },
        "DIRECTORY_FILTERED_ROOT_MEMBERSHIP_QUERY": {
            "PATH": "/api/session?parentID=null&directory=C%3A%5CUsers%5CBLAUTECH%5CAppData%5CLocal%5CTemp%5Colympus-phase11-case-f",
            "RESULT": "SUCCESS",
            "PARENT_ID_FILTER": None,
            "PARENT_ID_FIELD_OBSERVATION": "NOT_EXPOSED",
            "PAGE_ITEM_COUNTS": [1, 0],
            "PAGES": 2,
            "CURSOR_EXHAUSTED": True,
            "TOTAL_FILTERED_ITEMS": 1,
            "MATCHING_ROOT_SESSION_IDS": [CASE_F_ROOT_SESSION_ID],
            "ROOT_MEMBERSHIP": True,
        },
        "ROOT_TOOL_CALL_RECORDS": [],
        "ROOT_TOOL_CALL_RECORD_COUNT": 0,
        "NESTED_TOOL_WRAPPER_COUNT": 0,
        "TOOL_OBSERVATION_LIMIT": "Complete three-message root export contained no tool-call records or nested tool wrappers; no private runtime or worktree filesystem was accessed.",
    }
    if api != expected_api:
        errors.append("NATIVE_F_API_CHILD_TOOL_OR_EXPORT_OBSERVATION_MISMATCH")

    if (
        trace.get("CHILD_SESSIONS") != []
        or trace.get("CONSULTATION_COUNTS") != CASE_F_ROLE_COUNTS
        or trace.get("UNIQUE_CHILD_SESSION_COUNTS") != CASE_F_ROLE_COUNTS
        or trace.get("MAX_SIMULTANEOUS_CHILDREN") is not None
    ):
        errors.append("NATIVE_F_CHILD_COUNTS_OR_UNKNOWN_CONCURRENCY_MISMATCH")

    expected_negative = {
        role: {"INVOCATIONS": 0, "UNIQUE_CHILD_SESSIONS": 0}
        for role in ALL_INVOCABLE_ROLES if role != "kael"
    }
    expected_negative["argus"]["STATUS"] = "PASS"
    expected_negative["talos"]["STATUS"] = "PASS"
    if trace.get("NEGATIVE_CONTROLS") != expected_negative:
        errors.append("NATIVE_F_NEGATIVE_ARGUS_TALOS_OR_SPECIALIST_COUNTS_MISMATCH")

    expected_role_purity = {
        "STATUS": "PASS",
        "ROOT_AGENT": "kael",
        "NO_DIRECT_CHILDREN_OBSERVED": True,
        "NO_NESTED_TOOL_WRAPPERS_OBSERVED": True,
        "REVIEWER_EDITS_OBSERVED": False,
        "ROOT_REPORTED_FILES_CHANGED": "NONE",
        "FILESYSTEM_AUDIT_PERFORMED": False,
        "VIOLATIONS": [],
    }
    if trace.get("ROLE_PURITY") != expected_role_purity:
        errors.append("NATIVE_F_ROLE_PURITY_OR_FILE_AUDIT_OVERCLAIM")
    if trace.get("DEPENDENCY_ORDER") != []:
        errors.append("NATIVE_F_DEPENDENCY_ORDER_INVENTED")

    expected_result = {
        "EXPECTED_PRODUCT_ROUTE": CASE_F_EXPECTED_ROUTE,
        "OBSERVED_PRODUCT_ROUTE": CASE_F_EXPECTED_ROUTE,
        "ROUTE_MATCHES": True,
        "EXPECTED_OPERATIONAL_CLASSIFICATION": "OPERATIONAL_ISSUE",
        "OBSERVED_OPERATIONAL_CLASSIFICATION": "OPERATIONAL_ISSUE",
        "PRODUCT_BUG_ESTABLISHED": False,
        "SECURITY_BUG_ESTABLISHED": False,
        "ROOT_EXECUTION_OUTCOME": "succeeded",
        "CASE_ACCEPTANCE": "PASS",
        "CASE_ACCEPTANCE_BASIS": "The observed command-unavailable condition is correctly classified without claiming an application failure; no test was run during diagnosis.",
    }
    if (
        trace.get("EXPECTED_ROUTE") != CASE_F_EXPECTED_ROUTE
        or trace.get("ACTUAL_ROUTE") != CASE_F_EXPECTED_ROUTE
        or trace.get("ROUTE_RECONCILIATION", {}).get("EXPECTED_PRODUCT_ROUTE") != CASE_F_EXPECTED_ROUTE
        or trace.get("ROUTE_RECONCILIATION", {}).get("OBSERVED_PRODUCT_ROUTE") != CASE_F_EXPECTED_ROUTE
        or trace.get("ROUTE_RECONCILIATION", {}).get("OBSERVED_UNIQUE_CHILD_SESSION_LAUNCH_ORDER") != CASE_F_EXPECTED_ROUTE
        or trace.get("ROUTE_RECONCILIATION", {}).get("CLASSIFICATION") != "NATIVE_EXECUTED_ROUTING_PASS"
        or trace.get("RESULT_FIDELITY") != expected_result
    ):
        errors.append("NATIVE_F_ROUTE_OR_OPERATIONAL_RESULT_FIDELITY_MISMATCH")

    expected_completion = {
        "PENDING_CHILD_COUNT": 0,
        "UNCONSUMED_RESULT_COUNT": 0,
        "UNKNOWN_EXECUTION_COUNT": 0,
        "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED": True,
        "ROOT_TERMINAL": True,
        "RESULT_IDS": None,
        "PER_INVOCATION_CONSUMPTION_TIMING": None,
        "SESSION_LIFETIME_EXACT_ONCE": None,
    }
    if (
        trace.get("COMPLETION_GATE") != expected_completion
        or trace.get("USER_QUESTION_COUNT") != 0
        or trace.get("FINAL_OUTCOME") != "SUCCEEDED"
        or trace.get("ROUTING_RESULT") != "PASS"
        or trace.get("CASE_RESULT") != "NATIVE_EXECUTED_ROUTING_PASS"
        or trace.get("CASE_ACCEPTANCE") != "PASS"
    ):
        errors.append("NATIVE_F_COMPLETION_OR_TERMINAL_OUTCOME_MISMATCH")

    if trace.get("CLASSIFICATIONS") != CASE_F_CLASSIFICATIONS:
        errors.append("NATIVE_F_CLASSIFICATION_STATUS_MISMATCH")
    if trace.get("OBSERVED_TERMINAL_SNAPSHOT") != {
        "SOURCE": "OBSERVED_NATIVE_ROOT_TERMINAL_MESSAGE",
        "ROOT_SESSION_ID": CASE_F_ROOT_SESSION_ID,
        "MESSAGE_ID": CASE_F_ROOT_TERMINAL_MESSAGE_ID,
        "FACTS": CASE_F_TERMINAL_FACTS,
    }:
        errors.append("NATIVE_F_TERMINAL_OPERATIONAL_PRODUCT_SECURITY_OR_COMPLETION_FACTS_MISMATCH")
    expected_operational_finding = {
        "CLASSIFICATION": "OPERATIONAL_ISSUE",
        "FAILURE": "The plain `python` command is unavailable in the Windows shell; test execution did not start.",
        "PRODUCT_BUG_ESTABLISHED": False,
        "SECURITY_BUG_ESTABLISHED": False,
        "TESTS_RUN_DURING_DIAGNOSIS": "NONE",
        "SMALLEST_SAFE_NEXT_ACTION": "Recommend the original targeted unittest command through the known working `uv run --python 3.11 python` runtime, without installation or configuration changes; do not execute tests during diagnosis.",
        "EVIDENCE_REQUIRED_FOR_PRODUCT_BUG": "An actual failure after tests start under a working runtime, supported by expected behavior and evidence attributing the failure to product code rather than the environment or test harness.",
    }
    if trace.get("OPERATIONAL_FINDING") != expected_operational_finding:
        errors.append("NATIVE_F_OPERATIONAL_CLASSIFICATION_OR_PRODUCT_SECURITY_CLAIMS_MISMATCH")
    if (
        trace.get("INSTALL_ATTEMPTED") != "NO"
        or trace.get("FILES_CHANGED") != "NONE"
        or trace.get("CORE_POLICY_MODIFIED") is not False
        or trace.get("CASE_RERUN_PERFORMED_BY_RECONCILIATION") is not False
    ):
        errors.append("NATIVE_F_INSTALL_FILE_CHANGE_OR_REPLAY_CLAIM_MISMATCH")
    if trace.get("EFFICIENCY") != {
        "CLASSIFICATION": "LEAN",
        "BASIS": "One required Kael-only operational diagnosis; no latency, throughput, or concurrency claim.",
    }:
        errors.append("NATIVE_F_EFFICIENCY_OR_METRIC_OVERCLAIM")
    expected_unknowns = {
        "MAX_SIMULTANEOUS_CHILDREN": None,
        "WALL_CLOCK_MS": None,
        "RUNTIME_DURATION_MS": None,
        "RETRY_COUNT": None,
        "PER_INVOCATION_RESULT_IDS": None,
        "PER_INVOCATION_CONSUMPTION_TIMING": None,
        "SESSION_LIFETIME_EXACT_ONCE": None,
        "NATIVE_PERMISSION_UI": "NOT_OBSERVABLE",
        "NATIVE_PERMISSION_DECISION": "NOT_OBSERVABLE",
        "WORKTREE_FILESYSTEM_AUDIT": "NOT_PERFORMED",
    }
    if trace.get("UNKNOWN_METRICS") != expected_unknowns:
        errors.append("NATIVE_F_UNKNOWN_METRIC_OR_PERMISSION_OBSERVABILITY_OVERCLAIM")

    if root_export.get("evidence_class") != "FRESH_ROOT_NATIVE" or root_export.get("source_api") != (
        "OpenCode V2 public read-only API"
    ):
        errors.append("NATIVE_F_EXPORT_IDENTITY_OR_SOURCE_MISMATCH")
    expected_session = {
        "id": CASE_F_ROOT_SESSION_ID,
        "agent": "kael",
        "parent_id": None,
        "parent_id_observation": "NOT_EXPOSED",
        "directory": "C:\\Users\\BLAUTECH\\AppData\\Local\\Temp\\olympus-phase11-case-f",
        "title": CASE_F_ROOT_TITLE,
        "execution_outcome": "succeeded",
        "created_epoch_ms": 1791158595160,
        "updated_epoch_ms": 1791158597772,
        "idle_epoch_ms": 1791158613172,
        "viewed_epoch_ms": 1791158613172,
    }
    if root_export.get("session") != expected_session:
        errors.append("NATIVE_F_EXPORT_ROOT_METADATA_MISMATCH")
    if (
        root_export.get("session_metadata_query") != {
            "method": "GET", "path": f"/api/session/{CASE_F_ROOT_SESSION_ID}", "result": "SUCCESS"
        }
        or root_export.get("export_query") != {
            "method": "GET",
            "path": f"/api/experimental/session/{CASE_F_ROOT_SESSION_ID}/export?sanitize=false",
            "result": "SUCCESS",
        }
        or root_export.get("direct_child_query", {}).get("response") != {
            "parent_id": CASE_F_ROOT_SESSION_ID,
            "data": [],
            "cursor_previous": None,
            "cursor_next": None,
            "pages": 1,
        }
        or root_export.get("directory_filtered_root_membership_query") != {
            "method": "GET",
            "path": "/api/session?parentID=null&directory=C%3A%5CUsers%5CBLAUTECH%5CAppData%5CLocal%5CTemp%5Colympus-phase11-case-f",
            "result": "SUCCESS",
            "parent_id_filter": None,
            "parent_id_field_observation": "NOT_EXPOSED",
            "page_item_counts": [1, 0],
            "pages": 2,
            "cursor_exhausted": True,
            "total_filtered_items": 1,
            "matching_root_session_ids": [CASE_F_ROOT_SESSION_ID],
            "root_membership": True,
        }
    ):
        errors.append("NATIVE_F_EXPORT_API_QUERY_OR_ROOT_MEMBERSHIP_MISMATCH")

    messages = root_export.get("messages", [])
    message_types = [item.get("type") for item in messages if isinstance(item, dict)]
    message_ids = [item.get("id") for item in messages if isinstance(item, dict)]
    if (
        root_export.get("message_count") != 3
        or root_export.get("export_pagination") != "NONE_OBSERVED"
        or message_types != ["user", "assistant", "idle"]
        or message_ids != [CASE_F_ROOT_USER_MESSAGE_ID, CASE_F_ROOT_TERMINAL_MESSAGE_ID, CASE_F_ROOT_IDLE_MESSAGE_ID]
        or root_export.get("terminal_message_id") != CASE_F_ROOT_TERMINAL_MESSAGE_ID
        or root_export.get("terminal_outcome_record") != {
            "message_id": CASE_F_ROOT_IDLE_MESSAGE_ID, "type": "idle", "outcome": "succeeded"
        }
    ):
        errors.append("NATIVE_F_EXPORT_MESSAGE_OR_TERMINAL_SEQUENCE_MISMATCH")
    user_message = _export_message(root_export, CASE_F_ROOT_USER_MESSAGE_ID) or {}
    user_prompt = user_message.get("text", "") if isinstance(user_message.get("text"), str) else ""
    prompt_markers = (
        CASE_F_LABEL,
        CASE_F_ROOT_STARTING_HEAD,
        "C:\\Users\\BLAUTECH\\AppData\\Local\\Temp\\olympus-phase11-case-f",
        "`python -m unittest ...`",
        "plain `python` command is unavailable",
        "There is no observed failing product test",
        "`uv run --python 3.11 python`",
        "- install Python or dependencies;",
        "Do not run tests merely to create evidence",
    )
    if (
        user_message.get("files") != []
        or user_message.get("agents") != []
        or any(marker not in user_prompt for marker in prompt_markers)
    ):
        errors.append("NATIVE_F_ORIGINAL_PROMPT_OR_SCOPE_LIMITS_NOT_PRESERVED")

    terminal_text = _export_text(root_export, CASE_F_ROOT_TERMINAL_MESSAGE_ID)
    terminal_labels = tuple(CASE_F_TERMINAL_FACTS)
    terminal_label_pattern = re.compile(
        r"(?m)^(" + "|".join(re.escape(label) for label in terminal_labels) + r"):[ \t]*(.*)$"
    )
    terminal_label_matches = list(terminal_label_pattern.finditer(terminal_text))
    terminal_values: dict[str, list[str]] = {}
    for index, match in enumerate(terminal_label_matches):
        next_start = (
            terminal_label_matches[index + 1].start()
            if index + 1 < len(terminal_label_matches)
            else len(terminal_text)
        )
        inline_value = match.group(2).strip()
        following_text = terminal_text[match.end():next_start].strip()
        value = "\n".join(part for part in (inline_value, following_text) if part)
        terminal_values.setdefault(match.group(1), []).append(value)
    if any(
        len(terminal_values.get(label, [])) != 1
        or terminal_values[label][0] != expected
        for label, expected in CASE_F_TERMINAL_FACTS.items()
    ):
        errors.append("NATIVE_F_EXPORT_TERMINAL_OPERATIONAL_PRODUCT_SECURITY_OR_COMPLETION_FACTS_MISMATCH")

    content_types = _export_content_types(root_export)
    expected_projection = {
        "description": "Persisted only the supplied user prompt, visible assistant terminal text, root/message metadata, and empty observed tool-call projection. One reasoning block was removed; provider state and snapshots were omitted; raw export was not persisted. Nox did not assess secret filtering. The corpus writer inspected the supplied visible text and observed no secret credentials; no filter or redaction count is claimed.",
        "reasoning_blocks_removed": 1,
        "provider_state_omitted": True,
        "snapshots_omitted": True,
        "secret_filtering": "NOT_ASSESSED_BY_NOX",
        "visible_secret_credentials_observed": False,
        "raw_export_persisted": False,
    }
    if (
        root_export.get("tool_call_records") != []
        or root_export.get("tool_call_record_count") != 0
        or root_export.get("nested_tool_wrapper_count") != 0
        or root_export.get("projection_and_redaction") != expected_projection
        or any(re.search(r"(?i)reason|thought|analysis", kind) for kind in content_types)
    ):
        errors.append("NATIVE_F_EXPORT_PROJECTION_TOOL_OR_SECRET_FILTER_CLAIM_MISMATCH")
    return errors


def validate_phase11_f_reconciliation(
    baseline: dict[str, Any],
    cases_doc: dict[str, Any],
    trace: dict[str, Any],
    root_export: dict[str, Any],
) -> list[str]:
    """Bind F's native observation into current Phase 11 state without rewriting history."""
    cases = {
        case.get("id"): case
        for case in cases_doc.get("cases", [])
        if isinstance(case, dict)
    }
    errors = validate_native_case_f_capture(trace, cases.get("F", {}), root_export)
    report = baseline.get("phase11_f_reconciliation")
    if not isinstance(report, dict):
        return errors + ["CASE_F_RECONCILIATION_MISSING"]
    if (
        report.get("task_id") != "phase11-f-corpus-write"
        or report.get("label") != CASE_F_LABEL
        or report.get("evidence_artifact") != "tests/phase11-integrated-routing/case-f.native-trace.json"
        or report.get("export_artifact") != "tests/phase11-integrated-routing/case-f.root-session.export.json"
        or report.get("evidence_class") != "FRESH_ROOT_NATIVE"
    ):
        errors.append("CASE_F_EVIDENCE_LINK_OR_LABEL_MISMATCH")
    expected_root_fields = {
        "root_session_id": CASE_F_ROOT_SESSION_ID,
        "root_directory": CASE_F_ROOT_DIRECTORY,
        "root_agent": "kael",
        "root_parent_session_id": None,
        "root_parent_session_id_observation": "NOT_EXPOSED",
        "root_title": CASE_F_ROOT_TITLE,
        "root_terminal_outcome": "succeeded",
        "root_user_message_id": CASE_F_ROOT_USER_MESSAGE_ID,
        "root_terminal_message_id": CASE_F_ROOT_TERMINAL_MESSAGE_ID,
        "root_idle_message_id": CASE_F_ROOT_IDLE_MESSAGE_ID,
        "root_starting_head": CASE_F_ROOT_STARTING_HEAD,
        "root_starting_head_source": "Original root user prompt",
        "root_starting_head_filesystem_verified": False,
    }
    if any(report.get(key) != value for key, value in expected_root_fields.items()):
        errors.append("CASE_F_BASELINE_ROOT_IDENTITY_OR_STARTING_HEAD_OVERCLAIM")
    expected_membership = {
        "status": "SUPPLIED_VERIFIED",
        "directory_metadata_matches_prompt": True,
        "root_only_list_membership": True,
        "directory_query_pages": 2,
        "directory_query_page_item_counts": [1, 0],
        "directory_query_total_filtered_items": 1,
        "directory_query_cursor_exhausted": True,
        "parent_id_observation": "NOT_EXPOSED",
        "filesystem_audit_performed": False,
        "separate_disposable_worktree": None,
    }
    if report.get("root_membership") != expected_membership:
        errors.append("CASE_F_BASELINE_ROOT_MEMBERSHIP_OR_ISOLATION_OVERCLAIM")
    if (
        report.get("direct_child_count") != 0
        or report.get("root_tool_call_record_count") != 0
        or report.get("nested_tool_wrapper_count") != 0
        or report.get("root_export_message_count") != 3
        or report.get("root_export_pagination") != "NONE_OBSERVED"
        or report.get("child_sessions") != []
        or report.get("expected_product_route") != CASE_F_EXPECTED_ROUTE
        or report.get("observed_product_route") != CASE_F_EXPECTED_ROUTE
        or report.get("consultation_counts") != CASE_F_ROLE_COUNTS
        or report.get("unique_child_session_counts") != CASE_F_ROLE_COUNTS
        or report.get("max_simultaneous_children") is not None
    ):
        errors.append("CASE_F_BASELINE_ROUTE_CHILD_OR_SPECIALIST_COUNTS_MISMATCH")
    if report.get("classifications") != CASE_F_CLASSIFICATIONS or report.get("terminal_facts") != CASE_F_TERMINAL_FACTS:
        errors.append("CASE_F_BASELINE_CLASSIFICATIONS_OR_TERMINAL_FACTS_MISMATCH")
    expected_completion = {
        "pending_child_count": 0,
        "unconsumed_result_count": 0,
        "unknown_execution_count": 0,
        "required_children_terminal_and_consumed": True,
        "result_ids": None,
        "per_invocation_consumption_timing": None,
        "session_lifetime_exact_once": None,
    }
    if (
        report.get("completion_gate") != expected_completion
        or report.get("user_question_count") != 0
        or report.get("final_outcome") != "SUCCEEDED"
        or report.get("install_attempted") != "NO"
        or report.get("files_changed") != "NONE"
        or report.get("core_policy_modified") is not False
        or report.get("case_rerun_performed_by_reconciliation") is not False
    ):
        errors.append("CASE_F_BASELINE_COMPLETION_INSTALL_OR_FILE_FACTS_MISMATCH")
    expected_projection = {
        "reasoning_blocks_removed": 1,
        "provider_state_omitted": True,
        "snapshots_omitted": True,
        "secret_filtering": "NOT_ASSESSED_BY_NOX",
        "visible_secret_credentials_observed": False,
        "raw_export_persisted": False,
    }
    if report.get("projection_and_redaction") != expected_projection:
        errors.append("CASE_F_BASELINE_PROJECTION_OR_SECRET_FILTER_CLAIM_MISMATCH")
    expected_unknowns = {
        "max_simultaneous_children": None,
        "wall_clock_ms": None,
        "runtime_duration_ms": None,
        "retry_count": None,
        "per_invocation_result_ids": None,
        "per_invocation_consumption_timing": None,
        "session_lifetime_exact_once": None,
        "native_permission_ui": "NOT_OBSERVABLE",
        "native_permission_decision": "NOT_OBSERVABLE",
        "worktree_filesystem_audit": "NOT_PERFORMED",
    }
    if report.get("unknowns") != expected_unknowns:
        errors.append("CASE_F_BASELINE_UNKNOWN_METRICS_OR_PERMISSION_OBSERVABILITY_OVERCLAIM")
    validation = report.get("writer_local_validation", {})
    if (
        validation.get("phase11_qualifier") != {
            "command": "uv run --python 3.11 python -B tests/phase11-integrated-routing/qualify.py",
            "exit_code": 0,
            "result": "PHASE11_ARTIFACTS: PASS; PHASE11_QUALIFICATION: PARTIAL",
        }
        or validation.get("phase11_unittest") != {
            "command": "uv run --python 3.11 python -B -m unittest discover -s tests/phase11-integrated-routing -p \"test_*.py\" -v",
            "exit_code": 0,
            "test_count": 66,
            "result": "PASS",
        }
        or validation.get("harness_core_safe_root") != {
            "command": "uv run --python 3.11 python -B tests/harness-core/qualify.py --safe-root-read-only",
            "exit_code": 0,
            "result": "PASS",
            "managed_output_count_before": 29,
            "managed_output_count_after": 29,
            "hash_mtime_unchanged": True,
        }
        or validation.get("renderer_check") != {
            "command": "uv run --python 3.11 python -B scripts/render_harnesses.py check --harness all",
            "exit_code": 0,
            "result": "PASS (all; 29 managed output(s); read-only)",
        }
        or validation.get("git_diff_check") != {
            "command": "git diff --check",
            "exit_code": 0,
            "result": "PASS",
            "line_ending_warnings_only": True,
        }
        or validation.get("pythondontwritebytecode") is not True
        or validation.get("case_f_rerun_performed") is not False
    ):
        errors.append("CASE_F_WRITER_VALIDATION_RECORD_MISMATCH")
    if (
        report.get("efficiency") != "LEAN"
        or report.get("acceptance_status") != "PASS"
        or report.get("case_result") != "NATIVE_EXECUTED_ROUTING_PASS"
        or report.get("phase11_status") != "PARTIAL"
        or report.get("pending_fresh_root_labels") != CASE_F_PENDING_LABELS
    ):
        errors.append("CASE_F_ACCEPTANCE_PHASE_STATUS_OR_PENDING_LABELS_MISMATCH")

    current = baseline.get("live_qualification", {})
    if not isinstance(current, dict) or (
        current.get("pending_labels") != CURRENT_PHASE11_PENDING_LABELS
        or current.get("fresh_root_native") != CURRENT_PHASE11_FRESH_ROOT_STATE
        or current.get("native_results_claimed") is not True
        or current.get("overall_status") != "PARTIAL"
        or "phase11-f-corpus-write" not in current.get("current_pending_state_source", "")
    ):
        errors.append("CURRENT_PHASE11_F_PENDING_STATE_MISMATCH")
    if baseline.get("argus_same_session_followup_runtime_coverage") != CASE_D_PENDING_FOLLOWUP_COVERAGE:
        errors.append("CASE_F_ARGUS_FOLLOWUP_RUNTIME_COVERAGE_PROMOTED_OR_CONFLATED")

    actions = [
        action for action in cases_doc.get("fresh_root_actions", [])
        if isinstance(action, dict) and action.get("case_id") == "F" and action.get("label") == CASE_F_LABEL
    ]
    expected_action = {
        "scenario": "default",
        "status": "PASS",
        "evidence_class": "FRESH_ROOT_NATIVE",
        "evidence_artifact": "case-f.native-trace.json",
        "acceptance_status": "PASS",
        "pending_resolution": False,
    }
    if len(actions) != 1 or any(actions[0].get(key) != value for key, value in expected_action.items()):
        errors.append("CASE_F_MATRIX_STATUS_OR_EVIDENCE_LINK_MISMATCH")

    # E1 remains the immutable failed attempt; E2 remains the separate accepted retry.
    e1 = baseline.get("phase11_e_reconciliation", {})
    e2 = baseline.get("phase11_e2_reconciliation", {})
    if (
        e1.get("acceptance_status") != "FAIL"
        or e1.get("case_result") != CASE_E_NATIVE_RESULT
        or e1.get("root_session_id") != CASE_E_ROOT_SESSION_ID
        or e2.get("acceptance_status") != "PASS"
        or e2.get("case_result") != CASE_E2_NATIVE_RESULT
        or e2.get("root_session_id") != CASE_E2_ROOT_SESSION_ID
        or e2.get("pending_fresh_root_labels") != CASE_E2_PENDING_LABELS
    ):
        errors.append("CASE_F_E1_FAILED_HISTORY_OR_E2_ACCEPTANCE_REWRITTEN")
    return errors


def validate_native_case_g_capture(
    trace: dict[str, Any],
    case: dict[str, Any],
    root_export: dict[str, Any],
    veyra_export: dict[str, Any],
    thales_export: dict[str, Any],
) -> list[str]:
    """Check Case G's native evidence-before-diagnosis route and conditional follow-up."""
    errors: list[str] = []
    trace = trace if isinstance(trace, dict) else {}
    case = case if isinstance(case, dict) else {}
    root_export = root_export if isinstance(root_export, dict) else {}
    veyra_export = veyra_export if isinstance(veyra_export, dict) else {}
    thales_export = thales_export if isinstance(thales_export, dict) else {}
    add = errors.append

    required_fields = (
        "CASE_ID", "REQUEST_CLASS", "EVIDENCE_CLASS", "ROOT_SESSION_ID", "EXPECTED_ROUTE",
        "ACTUAL_ROUTE", "CHILD_SESSIONS", "CONSULTATION_COUNTS", "UNIQUE_CHILD_SESSION_COUNTS",
        "NEGATIVE_CONTROLS", "ROLE_PURITY", "DEPENDENCY_ORDER", "RESULT_FIDELITY", "API_EVIDENCE",
        "THALES_FOLLOWUP", "ROOT_TERMINAL_FACTS", "COMPLETION_GATE", "FINAL_OUTCOME",
        "CASE_ACCEPTANCE", "EVIDENCE_PROVENANCE",
    )
    missing = [field for field in required_fields if field not in trace]
    if missing:
        add("NATIVE_G_REQUIRED_FIELDS_MISSING:" + ",".join(missing))

    expected_native_acceptance = {
        "expected_product_route": CASE_G_EXPECTED_ROUTE,
        "source_evidence_role": "veyra",
        "actual_measurement_owner": "nox",
        "actual_measurement_required": False,
        "thales_second_same_session_consultation": "REQUIRED_ONLY_IF_MATERIALLY_NEW_EVIDENCE_REQUESTED_OR_NEEDED",
        "followup_runtime_coverage_may_remain": "NOT_EXERCISED",
    }
    synthetic_route = ["kael", "nox", "thales", "veyra"]
    synthetic_edges = [
        {
            "before_work_id": "fixed-flaky-observation-capture",
            "after_work_id": "bounded-uncertainty-diagnosis",
        },
        {
            "before_work_id": "fixed-sequence-source-evidence",
            "after_consultation": {"role": "thales", "number": 2},
        },
    ]
    if (
        case.get("id") != "G"
        or case.get("request_class") != "HARD_FLAKY_DIAGNOSIS"
        or case.get("expected_routes", {}).get("default") != synthetic_route
        or case.get("native_acceptance") != expected_native_acceptance
        or "mandatory_dependency_edges" in case
        or case.get("synthetic_illustrative_dependency_edges") != synthetic_edges
        or trace.get("CASE_ID") != "G"
        or trace.get("REQUEST_CLASS") != "HARD_FLAKY_DIAGNOSIS"
        or trace.get("EVIDENCE_CLASS") != "FRESH_ROOT_NATIVE"
        or trace.get("CASE_LABEL") != CASE_G_LABEL
        or trace.get("EXPECTED_ROUTE") != CASE_G_EXPECTED_ROUTE
        or trace.get("ACTUAL_ROUTE") != CASE_G_EXPECTED_ROUTE
    ):
        add("NATIVE_G_IDENTITY_MATRIX_OR_NATIVE_SEMANTICS_MISMATCH")

    try:
        fixed_fixture = load_json(HERE / "fixtures/flaky/observations.json")
    except (OSError, json.JSONDecodeError):
        fixed_fixture = None
    if (
        not isinstance(fixed_fixture, dict)
        or fixed_fixture.get("kind") != "fixed synthetic contradictory sequence"
        or fixed_fixture.get("same_input") != {"id": "item-7", "quantity": 2}
        or fixed_fixture.get("observations")
        != [
            {"ordinal": 1, "result": "PASS"},
            {"ordinal": 2, "result": "TIMEOUT"},
            {"ordinal": 3, "result": "PASS"},
        ]
    ):
        add("NATIVE_G_STATIC_FIXTURE_INPUT_OR_ORDERED_OBSERVATIONS_MISMATCH")

    route_reconciliation = trace.get("ROUTE_RECONCILIATION", {})
    if (
        route_reconciliation.get("SYNTHETIC_TRACE_ROUTE") != ["kael", "nox", "thales", "veyra"]
        or route_reconciliation.get("EXPECTED_NATIVE_PRODUCT_ROUTE") != CASE_G_EXPECTED_ROUTE
        or route_reconciliation.get("OBSERVED_NATIVE_PRODUCT_ROUTE") != CASE_G_EXPECTED_ROUTE
        or route_reconciliation.get("OBSERVED_ROOT_CALL_ORDER") != ["veyra", "thales"]
        or route_reconciliation.get("CLASSIFICATION") != "PASS"
    ):
        add("NATIVE_G_SYNTHETIC_AND_NATIVE_ROUTE_SEPARATION_MISMATCH")

    expected_root_session = {
        "id": CASE_G_ROOT_SESSION_ID,
        "agent": "kael",
        "parent_id": None,
        "parent_id_observation": "NOT_EXPOSED",
        "directory": "C:\\Users\\BLAUTECH\\AppData\\Local\\Temp\\olympus-phase11-case-g",
        "title": CASE_G_ROOT_TITLE,
        "execution_outcome": "succeeded",
        "time": {"created": 1791205534628, "updated": 1791205536328, "idle": 1791205649239, "viewed": 1791205649239},
    }
    if (
        trace.get("ROOT_SESSION_ID") != CASE_G_ROOT_SESSION_ID
        or trace.get("ROOT_DIRECTORY", "").replace("\\", "/") != CASE_G_ROOT_DIRECTORY
        or trace.get("ROOT_AGENT") != "kael"
        or trace.get("ROOT_PARENT_SESSION_ID") is not None
        or trace.get("ROOT_PARENT_SESSION_ID_OBSERVATION") != "NOT_EXPOSED_IN_EXPORT; NULL_SUPPLIED_IN_TASK_CONTEXT"
        or trace.get("ROOT_TITLE") != CASE_G_ROOT_TITLE
        or trace.get("ROOT_EXECUTION_OUTCOME") != "succeeded"
        or trace.get("ROOT_USER_MESSAGE_ID") != CASE_G_ROOT_USER_MESSAGE_ID
        or trace.get("ROOT_VEYRA_INVOCATION_MESSAGE_ID") != CASE_G_ROOT_VEYRA_MESSAGE_ID
        or trace.get("ROOT_THALES_INVOCATION_MESSAGE_ID") != CASE_G_ROOT_THALES_MESSAGE_ID
        or trace.get("ROOT_TERMINAL_MESSAGE_ID") != CASE_G_ROOT_TERMINAL_MESSAGE_ID
        or trace.get("ROOT_IDLE_MESSAGE_ID") != CASE_G_ROOT_IDLE_MESSAGE_ID
        or trace.get("ROOT_STARTING_HEAD") != CASE_G_ROOT_HEAD
        or trace.get("ROOT_STARTING_HEAD_SOURCE") != "Original root user prompt"
        or trace.get("ROOT_STARTING_HEAD_FILESYSTEM_VERIFIED_BY_RECONCILIATION") is not False
        or root_export.get("session") != expected_root_session
    ):
        add("NATIVE_G_ROOT_METADATA_OR_EXPORT_JOIN_MISMATCH")

    expected_exports = (
        (
            root_export, CASE_G_ROOT_SESSION_ID, 5, 3,
            CASE_G_ROOT_USER_MESSAGE_ID, CASE_G_ROOT_USER_PROMPT_SHA256,
        ),
        (
            veyra_export, CASE_G_VEYRA_SESSION_ID, 4, 2,
            CASE_G_VEYRA_USER_MESSAGE_ID, CASE_G_VEYRA_USER_PROMPT_SHA256,
        ),
        (
            thales_export, CASE_G_THALES_SESSION_ID, 3, 2,
            CASE_G_THALES_USER_MESSAGE_ID, CASE_G_THALES_USER_PROMPT_SHA256,
        ),
    )
    for export, session_id, message_count, reasoning_count, prompt_id, prompt_hash in expected_exports:
        if (
            export.get("evidence_class") != "FRESH_ROOT_NATIVE"
            or export.get("source_api") != "OpenCode V2 public read-only API"
            or export.get("export_schema")
            != "OpenAPI SessionTransfer.Data: response.data.info plus response.data.messages; assistant public text is in message.content entries with type=text."
            or export.get("session_metadata_query") != {
                "method": "GET", "path": f"/api/session/{session_id}", "result": "SUCCESS"
            }
            or export.get("export_query") != {
                "method": "GET",
                "path": f"/api/experimental/session/{session_id}/export?sanitize=false",
                "result": "SUCCESS",
            }
            or export.get("message_count") != message_count
            or len(export.get("messages", [])) != message_count
            or export.get("export_pagination") != "NONE_OBSERVED"
        ):
            add("NATIVE_G_EXPORT_SCHEMA_METADATA_OR_LINK_MISMATCH")
        projection = export.get("projection_and_redaction", {})
        if (
            projection.get("reasoning_blocks_removed") != reasoning_count
            or projection.get("secret_values_redacted") != 0
            or projection.get("unrecognized_content_blocks_omitted") != 0
            or projection.get("provider_state_omitted") is not True
            or projection.get("snapshots_omitted") is not True
            or projection.get("tool_arguments_and_results_omitted") is not True
            or projection.get("raw_export_persisted") is not False
            or export.get("content_availability", {}).get("user_prompt_sha256") != prompt_hash
            or any(re.search(r"(?i)reason|thought|analysis", kind) for kind in _export_content_types(export))
        ):
            add("NATIVE_G_SANITIZATION_OR_PROVIDER_PRIVATE_CONTENT_MISMATCH")
        projected_prompt = (_export_message(export, prompt_id) or {}).get("text", "")
        if not isinstance(projected_prompt, str) or _sha256_text(projected_prompt) != prompt_hash:
            add("NATIVE_G_USER_PROMPT_PROJECTION_HASH_MISMATCH")

    root_messages = root_export.get("messages", [])
    expected_root_message_ids = [
        CASE_G_ROOT_USER_MESSAGE_ID,
        CASE_G_ROOT_VEYRA_MESSAGE_ID,
        CASE_G_ROOT_THALES_MESSAGE_ID,
        CASE_G_ROOT_TERMINAL_MESSAGE_ID,
        CASE_G_ROOT_IDLE_MESSAGE_ID,
    ]
    expected_root_message_times = [
        {"created": 1791205534665},
        {"created": 1791205535121, "streamed": 1791205558605, "completed": 1791205572299},
        {"created": 1791205572587, "streamed": 1791205603780, "completed": 1791205639596},
        {"created": 1791205639798, "streamed": 1791205649032, "completed": 1791205649235},
        {"created": 1791205649239},
    ]
    if (
        [message.get("id") for message in root_messages if isinstance(message, dict)] != expected_root_message_ids
        or [message.get("type") for message in root_messages if isinstance(message, dict)]
        != ["user", "assistant", "assistant", "assistant", "idle"]
        or [message.get("time") for message in root_messages if isinstance(message, dict)] != expected_root_message_times
        or root_export.get("terminal_message_id") != CASE_G_ROOT_TERMINAL_MESSAGE_ID
        or root_export.get("terminal_outcome_record") != {
            "message_id": CASE_G_ROOT_IDLE_MESSAGE_ID, "type": "idle", "outcome": "succeeded"
        }
    ):
        add("NATIVE_G_ROOT_EXPORT_MESSAGE_ORDER_OR_TERMINAL_JOIN_MISMATCH")

    root_prompt = (_export_message(root_export, CASE_G_ROOT_USER_MESSAGE_ID) or {}).get("text", "")
    root_prompt_markers = (
        CASE_G_LABEL,
        CASE_G_ROOT_HEAD,
        CASE_G_ROOT_WINDOWS_DIRECTORY,
        "fixtures/flaky/observations.json",
        "Do NOT rerun, reproduce, randomize",
        "STAGE 1",
        "If the diagnosis remains materially uncertain",
        "After that evidence is terminal and consumed, continue the SAME existing diagnostic specialist session",
    )
    if not isinstance(root_prompt, str) or any(marker not in root_prompt for marker in root_prompt_markers):
        add("NATIVE_G_ORIGINAL_PROMPT_SCOPE_OR_NO_RERUN_GATE_MISMATCH")
    veyra_prompt = (_export_message(veyra_export, CASE_G_VEYRA_USER_MESSAGE_ID) or {}).get("text", "")
    if (
        "TASK_ID: PHASE11_CASE_G_STAGE1" not in veyra_prompt
        or "ROLE: veyra" not in veyra_prompt
        or "ordered result sequence, preserving actual values and order" not in veyra_prompt
        or "READ_SCOPE: tests/phase11-integrated-routing/fixtures/flaky/observations.json (STAGE 1: fixed input identity/value and ordered observations only)" not in veyra_prompt
        or "Do not use, report, interpret, or base conclusions on randomized, network, or purpose metadata" not in veyra_prompt
    ):
        add("NATIVE_G_VEYRA_STAGE1_SCOPE_OR_SOURCE_OWNERSHIP_MISMATCH")

    root_calls = root_export.get("tool_call_records", [])
    expected_root_calls = [
        {
            "id": CASE_G_VEYRA_ROOT_CALL_ID,
            "name": "subagent",
            "executed": False,
            "state": "completed",
            "agent": "veyra",
            "task_label": "PHASE11_CASE_G_STAGE1",
            "child_session_id": CASE_G_VEYRA_SESSION_ID,
            "result_id": None,
        },
        {
            "id": CASE_G_THALES_ROOT_CALL_ID,
            "name": "subagent",
            "executed": False,
            "state": "completed",
            "agent": "thales",
            "task_label": "PHASE11_CASE_G_DIAGNOSIS",
            "child_session_id": CASE_G_THALES_SESSION_ID,
            "result_id": None,
        },
    ]
    trace_calls = trace.get("API_EVIDENCE", {}).get("ROOT_TOOL_CALL_RECORDS")
    if root_calls != expected_root_calls or trace_calls != [
        {
            "ORDER": 1,
            "PARENT_MESSAGE_ID": CASE_G_ROOT_VEYRA_MESSAGE_ID,
            "TOOL_CALL_ID": CASE_G_VEYRA_ROOT_CALL_ID,
            "AGENT": "veyra",
            "TASK_LABEL": "PHASE11_CASE_G_STAGE1",
            "CHILD_SESSION_ID": CASE_G_VEYRA_SESSION_ID,
            "EXECUTED": False,
            "TOOL_STATE": "completed",
            "RESULT_ID": None,
        },
        {
            "ORDER": 2,
            "PARENT_MESSAGE_ID": CASE_G_ROOT_THALES_MESSAGE_ID,
            "TOOL_CALL_ID": CASE_G_THALES_ROOT_CALL_ID,
            "AGENT": "thales",
            "TASK_LABEL": "PHASE11_CASE_G_DIAGNOSIS",
            "CHILD_SESSION_ID": CASE_G_THALES_SESSION_ID,
            "EXECUTED": False,
            "TOOL_STATE": "completed",
            "RESULT_ID": None,
        },
    ]:
        add("NATIVE_G_ROOT_TOOL_CALL_ORDER_OR_RESULT_ID_MISMATCH")
    if trace.get("API_EVIDENCE", {}).get("TOOL_EXECUTED_FLAG_CAVEAT") != (
        "The public exports report executed=false on both root subagent calls and Veyra's read call even though each observed tool state is completed; the linked child session exports succeeded and the root terminal reports child results consumed. Preserve this flag, but do not interpret it as proof of non-execution or as negating completed results."
    ):
        add("NATIVE_G_EXECUTED_FLAG_INTERPRETATION_MISMATCH")

    child_sessions = trace.get("CHILD_SESSIONS", [])
    expected_child_fields = [
        {
            "TRACE_REF": "G-VEYRA", "NATIVE_SESSION_ID": CASE_G_VEYRA_SESSION_ID, "AGENT": "veyra",
            "PARENT_AGENT": "kael", "PARENT_SESSION_ID": CASE_G_ROOT_SESSION_ID, "LAUNCH_ORDER": 1,
            "INVOCATION_COUNT": 1, "EXECUTION_STATE": "SUCCEEDED", "FINAL_OUTCOME": "succeeded",
            "RETURN_STATUS": "SUCCESS", "RESULT_ID": None, "PARENT_MESSAGE_ID": CASE_G_ROOT_VEYRA_MESSAGE_ID,
            "INVOCATION_TOOL_CALL_ID": CASE_G_VEYRA_ROOT_CALL_ID,
            "TERMINAL_MESSAGE_ID": CASE_G_VEYRA_TERMINAL_MESSAGE_ID, "TERMINAL_RETURN_CONSUMED": True,
        },
        {
            "TRACE_REF": "G-THALES", "NATIVE_SESSION_ID": CASE_G_THALES_SESSION_ID, "AGENT": "thales",
            "PARENT_AGENT": "kael", "PARENT_SESSION_ID": CASE_G_ROOT_SESSION_ID, "LAUNCH_ORDER": 2,
            "INVOCATION_COUNT": 1, "EXECUTION_STATE": "SUCCEEDED", "FINAL_OUTCOME": "succeeded",
            "RETURN_STATUS": "ADVICE", "RESULT_ID": None, "PARENT_MESSAGE_ID": CASE_G_ROOT_THALES_MESSAGE_ID,
            "INVOCATION_TOOL_CALL_ID": CASE_G_THALES_ROOT_CALL_ID,
            "TERMINAL_MESSAGE_ID": CASE_G_THALES_TERMINAL_MESSAGE_ID, "TERMINAL_RETURN_CONSUMED": True,
        },
    ]
    if len(child_sessions) != 2 or any(
        any(child.get(key) != value for key, value in expected.items())
        for child, expected in zip(child_sessions, expected_child_fields)
    ):
        add("NATIVE_G_CHILD_PARENT_ROLE_OUTCOME_OR_ROUTE_JOIN_MISMATCH")

    expected_child_sessions = (
        (veyra_export, CASE_G_VEYRA_SESSION_ID, "veyra", CASE_G_VEYRA_TERMINAL_MESSAGE_ID,
         [CASE_G_VEYRA_USER_MESSAGE_ID, CASE_G_VEYRA_READ_MESSAGE_ID, CASE_G_VEYRA_TERMINAL_MESSAGE_ID, CASE_G_VEYRA_IDLE_MESSAGE_ID],
         ["user", "assistant", "assistant", "idle"],
         {
             "id": CASE_G_VEYRA_SESSION_ID, "agent": "veyra", "parent_id": CASE_G_ROOT_SESSION_ID,
             "parent_id_observation": "EXPLICIT_ID", "directory": "C:\\Users\\BLAUTECH\\AppData\\Local\\Temp\\olympus-phase11-case-g",
             "title": "Collect fixed observation sequence", "execution_outcome": "succeeded",
             "time": {"created": 1791205558860, "updated": 1791205558867, "idle": 1791205572038},
         },
         [
             {"created": 1791205558894},
             {"created": 1791205559154, "streamed": 1791205562977, "completed": 1791205563284},
             {"created": 1791205563567, "streamed": 1791205571812, "completed": 1791205572026},
             {"created": 1791205572038},
         ]),
        (thales_export, CASE_G_THALES_SESSION_ID, "thales", CASE_G_THALES_TERMINAL_MESSAGE_ID,
         [CASE_G_THALES_USER_MESSAGE_ID, CASE_G_THALES_TERMINAL_MESSAGE_ID, CASE_G_THALES_IDLE_MESSAGE_ID],
         ["user", "assistant", "idle"],
         {
             "id": CASE_G_THALES_SESSION_ID, "agent": "thales", "parent_id": CASE_G_ROOT_SESSION_ID,
             "parent_id_observation": "EXPLICIT_ID", "directory": "C:\\Users\\BLAUTECH\\AppData\\Local\\Temp\\olympus-phase11-case-g",
             "title": "Diagnose contradictory fixed observations", "execution_outcome": "succeeded",
             "time": {"created": 1791205603966, "updated": 1791205603974, "idle": 1791205639393},
         },
         [
             {"created": 1791205604001},
             {"created": 1791205604296, "streamed": 1791205639204, "completed": 1791205639385},
             {"created": 1791205639393},
         ]),
    )
    for export, session_id, role, terminal_id, message_ids, message_types, expected_session, expected_times in expected_child_sessions:
        session = export.get("session", {})
        messages = export.get("messages", [])
        if (
            session != expected_session
            or session.get("id") != session_id
            or session.get("agent") != role
            or session.get("parent_id") != CASE_G_ROOT_SESSION_ID
            or session.get("parent_id_observation") != "EXPLICIT_ID"
            or session.get("directory", "").replace("\\", "/") != CASE_G_ROOT_DIRECTORY
            or session.get("execution_outcome") != "succeeded"
            or [message.get("id") for message in messages if isinstance(message, dict)] != message_ids
            or [message.get("type") for message in messages if isinstance(message, dict)] != message_types
            or [message.get("time") for message in messages if isinstance(message, dict)] != expected_times
            or export.get("terminal_message_id") != terminal_id
            or export.get("terminal_outcome_record", {}).get("outcome") != "succeeded"
        ):
            add("NATIVE_G_CHILD_EXPORT_METADATA_OR_MESSAGE_JOIN_MISMATCH")

    veyra_read_stub = {
        "id": CASE_G_VEYRA_READ_CALL_ID,
        "name": "read",
        "executed": False,
        "state": "completed",
        "result_id": None,
    }
    if veyra_export.get("tool_call_records") != [veyra_read_stub] or thales_export.get("tool_call_records") != []:
        add("NATIVE_G_CHILD_TOOL_OR_NESTED_DELEGATION_MISMATCH")
    veyra_read_message = _export_message(veyra_export, CASE_G_VEYRA_READ_MESSAGE_ID) or {}
    veyra_read_content = veyra_read_message.get("content", [])
    if (
        len(veyra_read_content) != 1
        or veyra_read_content[0].get("id") != CASE_G_VEYRA_READ_CALL_ID
        or veyra_read_content[0].get("executed") is not False
        or veyra_read_content[0].get("state") != "completed"
        or veyra_read_content[0].get("time")
        != {"created": 1791205562933, "ran": 1791205562956, "completed": 1791205563049}
    ):
        add("NATIVE_G_CHILD_READ_TOOL_STATUS_OR_EXECUTED_FLAG_MISMATCH")
    veyra_call_message = _export_message(root_export, CASE_G_ROOT_VEYRA_MESSAGE_ID) or {}
    thales_call_message = _export_message(root_export, CASE_G_ROOT_THALES_MESSAGE_ID) or {}
    veyra_call_content = veyra_call_message.get("content", [])
    thales_call_content = thales_call_message.get("content", [])
    if (
        len(veyra_call_content) != 1
        or veyra_call_content[0].get("id") != CASE_G_VEYRA_ROOT_CALL_ID
        or veyra_call_content[0].get("executed") is not False
        or veyra_call_content[0].get("child_session_id") != CASE_G_VEYRA_SESSION_ID
        or len(thales_call_content) != 1
        or thales_call_content[0].get("id") != CASE_G_THALES_ROOT_CALL_ID
        or thales_call_content[0].get("executed") is not False
        or thales_call_content[0].get("child_session_id") != CASE_G_THALES_SESSION_ID
        or veyra_call_content[0].get("time")
        != {"created": 1791205542474, "ran": 1791205558522, "completed": 1791205572047}
        or thales_call_content[0].get("time")
        != {"created": 1791205581434, "ran": 1791205603660, "completed": 1791205639399}
        or veyra_call_content[0].get("time", {}).get("completed", 0)
        >= thales_call_message.get("time", {}).get("created", 0)
    ):
        add("NATIVE_G_SOURCE_EVIDENCE_ORDER_OR_CHILD_CALL_JOIN_MISMATCH")

    actual_counts = trace.get("CONSULTATION_COUNTS")
    unique_counts = trace.get("UNIQUE_CHILD_SESSION_COUNTS")
    if actual_counts != CASE_G_ROLE_COUNTS or unique_counts != CASE_G_ROLE_COUNTS:
        add("NATIVE_G_CONSULTATION_OR_UNIQUE_SESSION_COUNTS_MISMATCH")
    negative = trace.get("NEGATIVE_CONTROLS", {})
    if any(
        negative.get(role) != {"INVOCATIONS": 0, "UNIQUE_CHILD_SESSIONS": 0}
        or CASE_G_ROLE_COUNTS.get(role) != 0
        for role in CASE_G_NEGATIVE_ROLES
    ):
        add("NATIVE_G_NEGATIVE_ROLE_CONTROL_ACTIVATED_OR_MISCOUNTED")

    expected_ownership = {
        "SOURCE_EVIDENCE_ROLE": "veyra",
        "SOURCE_EVIDENCE_KIND": "read-only fixed fixture observations",
        "ACTUAL_MEASUREMENT_ROLE": "nox",
        "ACTUAL_MEASUREMENT_PERFORMED": False,
        "NOX_INVOCATIONS": 0,
        "MEASUREMENT_REASON": "No runtime measurement or rerun was authorized or performed; the supplied sequence is synthetic fixture evidence.",
    }
    expected_purity = {
        "STATUS": "PASS",
        "ROOT_AGENT": "kael",
        "DIRECT_CHILDREN_ONLY": True,
        "NO_NESTED_SUBAGENT_DELEGATION": True,
        "VEYRA_SOURCE_EVIDENCE_OWNER": True,
        "NOX_ACTUAL_MEASUREMENT_OWNER": True,
        "NOX_MEASUREMENT_PERFORMED": False,
        "REVIEWER_EDITS": False,
        "ROOT_SOURCE_WRITES": False,
        "ORIGINAL_RUN_FILES_CHANGED": "NONE",
        "VIOLATIONS": [],
    }
    if trace.get("EVIDENCE_OWNERSHIP") != expected_ownership or trace.get("ROLE_PURITY") != expected_purity:
        add("NATIVE_G_EVIDENCE_ROLE_OWNERSHIP_OR_ROLE_PURITY_MISMATCH")

    expected_edges = [
        {"BEFORE": "G-VEYRA:RESULT", "AFTER": "G-THALES:CONSULT:1", "ORDER_BASIS": "observed root export order"},
        {"BEFORE": "G-THALES:RESULT", "AFTER": "G-ROOT:FINALIZE", "ORDER_BASIS": "observed root export order"},
    ]
    if trace.get("DEPENDENCY_ORDER") != expected_edges:
        add("NATIVE_G_EVIDENCE_BEFORE_DIAGNOSIS_OR_TERMINAL_ORDER_MISMATCH")
    thales_prompt = (_export_message(thales_export, CASE_G_THALES_USER_MESSAGE_ID) or {}).get("text", "")
    if (
        "Veyra's terminal Stage 1 result" not in thales_prompt
        or "item-7, quantity 2" not in thales_prompt
        or "ordinal 2 TIMEOUT" not in thales_prompt
        or "TASK_ID: PHASE11_CASE_G_DIAGNOSIS" not in thales_prompt
        or "ROLE: thales" not in thales_prompt
        or "Do not conduct any reads yourself" not in thales_prompt
    ):
        add("NATIVE_G_THALES_DID_NOT_RECEIVE_VEYRA_EVIDENCE")

    expected_followup = trace.get("THALES_FOLLOWUP", {})
    thales_terminal_text = _export_text(thales_export, CASE_G_THALES_TERMINAL_MESSAGE_ID)
    observed_no_followup_markers = (
        "Additional metadata is not materially necessary for this "
        "smallest supported conclusion." in thales_terminal_text
        and "Do not request another read merely to seek specificity." in thales_terminal_text
        and "EXECUTION_DECISION: STOP" in thales_terminal_text
    )
    if (
        not isinstance(expected_followup, dict)
        or expected_followup != CASE_G_EXPECTED_FOLLOWUP
        or not observed_no_followup_markers
    ):
        add("NATIVE_G_THALES_FOLLOWUP_CLAIMS_NOT_SUPPORTED_BY_OBSERVED_EXPORT")
    if (
        not isinstance(expected_followup, dict)
        or expected_followup.get("SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE") != "NOT_EXERCISED"
        or trace.get("ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE") != "NOT_EXERCISED"
    ):
        add("NATIVE_G_REASONER_FOLLOWUP_COVERAGE_OVERCLAIM")

    veyra_text = _export_text(veyra_export, CASE_G_VEYRA_TERMINAL_MESSAGE_ID)
    thales_text = _export_text(thales_export, CASE_G_THALES_TERMINAL_MESSAGE_ID)
    thales_required_markers = (
        "not reproduced runtime flakiness or a causal diagnosis",
        "Additional metadata is not materially necessary",
        "Do not request another read merely to seek specificity",
        "SUPPORTED_CAUSE: UNCONFIRMED",
        "causal confidence cannot be assessed",
    )
    result_fidelity = trace.get("RESULT_FIDELITY", {})
    if (
        veyra_text != CASE_G_VEYRA_TERMINAL_TEXT
        or thales_text != CASE_G_THALES_TERMINAL_TEXT
        or trace.get("ROOT_TERMINAL_FACTS") != CASE_G_ROOT_TERMINAL_FACTS
        or trace.get("OBSERVED_TERMINAL_SNAPSHOT", {}).get("FACTS") != CASE_G_ROOT_TERMINAL_FACTS
        or trace.get("OBSERVED_TERMINAL_SNAPSHOT", {}).get("TEXT") != _export_text(root_export, CASE_G_ROOT_TERMINAL_MESSAGE_ID)
        or any(marker not in thales_text for marker in thales_required_markers)
        or result_fidelity.get("SAME_INPUT") != {"id": "item-7", "quantity": 2}
        or result_fidelity.get("OBSERVED_SEQUENCE") != ["PASS", "TIMEOUT", "PASS"]
        or result_fidelity.get("OBSERVATIONS_ARE_SYNTHETIC_FIXTURE_EVIDENCE") is not True
        or result_fidelity.get("RUNTIME_FLAKINESS_REPRODUCED") is not False
        or result_fidelity.get("DIAGNOSIS") != "RECORDED_SAME_INPUT_OUTCOME_INCONSISTENCY"
        or result_fidelity.get("DETERMINISTIC_CAUSE_ESTABLISHED") is not False
        or result_fidelity.get("SUPPORTED_CAUSE") != "UNCONFIRMED"
        or result_fidelity.get("CAUSAL_CONFIDENCE") != "UNESTABLISHED"
        or result_fidelity.get("ADDITIONAL_DISCRIMINATING_EVIDENCE_USED") is not False
    ):
        add("NATIVE_G_CHILD_DIAGNOSTIC_OR_ROOT_TERMINAL_CAUSE_FIDELITY_MISMATCH")

    expected_completion = {
        "PENDING_CHILD_COUNT": 0,
        "UNCONSUMED_RESULT_COUNT": 0,
        "UNKNOWN_EXECUTION_COUNT": 0,
        "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED": True,
        "ROOT_TERMINAL": True,
        "RESULT_IDS": None,
        "PER_INVOCATION_CONSUMPTION_TIMING": None,
        "SESSION_LIFETIME_EXACT_ONCE": None,
        "AGGREGATE_TERMINAL_SOURCE": "Root terminal says REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED: YES; result IDs and per-invocation consumption timing are not exposed.",
    }
    if (
        trace.get("COMPLETION_GATE") != expected_completion
        or trace.get("USER_QUESTION_COUNT") != 0
        or trace.get("FINAL_OUTCOME") != "SUCCEEDED"
        or trace.get("ROUTING_RESULT") != "PASS"
        or trace.get("CASE_ACCEPTANCE") != "PASS"
        or trace.get("CASE_RESULT") != "FRESH_ROOT_NATIVE_ACCEPTANCE_PASS"
        or trace.get("CASE_RERUN_PERFORMED_BY_RECONCILIATION") is not False
        or trace.get("RECONCILIATION_FILES_CHANGED") != CASE_G_RECONCILIATION_FILES_CHANGED
        or trace.get("NOTES") != CASE_G_RECONCILIATION_NOTES
        or trace.get("EFFICIENCY", {}).get("CLASSIFICATION") != "LEAN"
        or trace.get("CLASSIFICATIONS") != CASE_G_CLASSIFICATIONS
    ):
        add("NATIVE_G_COMPLETION_RERUN_FILE_CHANGE_OR_ACCEPTANCE_STATUS_MISMATCH")
    expected_unknowns = {
        "MAX_SIMULTANEOUS_CHILDREN": None,
        "WALL_CLOCK_MS": None,
        "RUNTIME_DURATION_MS": None,
        "RETRY_COUNT": None,
        "PER_INVOCATION_RESULT_IDS": None,
        "PER_INVOCATION_CONSUMPTION_TIMING": None,
        "SESSION_LIFETIME_EXACT_ONCE": None,
        "NATIVE_PERMISSION_UI": "NOT_OBSERVABLE",
        "NATIVE_PERMISSION_DECISION": "NOT_OBSERVABLE",
        "WORKTREE_FILESYSTEM_AUDIT": "NOT_PERFORMED",
    }
    if (
        trace.get("MAX_SIMULTANEOUS_CHILDREN") is not None
        or trace.get("UNKNOWN_METRICS") != expected_unknowns
        or trace.get("EFFICIENCY", {}).get("BASIS")
        != "Qualification judgment for one bounded source consultation, one Thales diagnosis, and no reruns; not a measured latency or throughput result."
    ):
        add("NATIVE_G_UNKNOWN_TIMING_CONCURRENCY_PERMISSION_OR_EFFICIENCY_OVERCLAIM")

    provenance = trace.get("EVIDENCE_PROVENANCE", {})
    if (
        provenance.get("CLASS") != "FRESH_ROOT_NATIVE"
        or provenance.get("NATIVE_ROOT_SESSION_ID") != CASE_G_ROOT_SESSION_ID
        or provenance.get("NATIVE_CHILD_SESSION_IDS") != [CASE_G_VEYRA_SESSION_ID, CASE_G_THALES_SESSION_ID]
        or provenance.get("FRESH_ROOT_CONFIRMED") is not True
        or provenance.get("WORKTREE_ISOLATION") != "SUPPLIED_VERIFIED"
        or provenance.get("CAPTURE_SESSION_IS_ROOT_CHILD") is not False
        or trace.get("ROOT_ISOLATION", {}).get("WORKTREE_ISOLATION") != "SUPPLIED_VERIFIED"
        or trace.get("ROOT_ISOLATION", {}).get("SEPARATE_DISPOSABLE_WORKTREE") is not None
        or trace.get("ROOT_ISOLATION", {}).get("FILESYSTEM_AUDIT_PERFORMED") is not False
    ):
        add("NATIVE_G_ISOLATION_OR_PROVENANCE_OVERCLAIM")
    return errors


def validate_phase11_g_reconciliation(
    baseline: dict[str, Any],
    cases_doc: dict[str, Any],
    trace: dict[str, Any],
    root_export: dict[str, Any],
    veyra_export: dict[str, Any],
    thales_export: dict[str, Any],
) -> list[str]:
    """Bind G's native capture to the current PARTIAL state without rewriting snapshots."""
    cases = {
        case.get("id"): case
        for case in cases_doc.get("cases", [])
        if isinstance(case, dict)
    }
    errors = validate_native_case_g_capture(
        trace, cases.get("G", {}), root_export, veyra_export, thales_export
    )
    report = baseline.get("phase11_g_reconciliation")
    if not isinstance(report, dict):
        return errors + ["CASE_G_RECONCILIATION_MISSING"]
    expected_thales_followup = {
        "consultation_count": 1,
        "evidence_request_made": False,
        "materially_new_evidence_needed": False,
        "followup_status": "NOT_REQUIRED",
        "followup_consultation_count": 0,
        "followup_session_id": None,
        "same_session_followup_runtime_coverage": "NOT_EXERCISED",
        "basis": "Thales reports that additional metadata is not materially necessary and recommends stopping; no follow-up request or second consultation appears in the exports.",
    }
    expected_root_calls = [
        {
            "order": 1,
            "parent_message_id": CASE_G_ROOT_VEYRA_MESSAGE_ID,
            "tool_call_id": CASE_G_VEYRA_ROOT_CALL_ID,
            "agent": "veyra",
            "child_session_id": CASE_G_VEYRA_SESSION_ID,
            "executed": False,
            "state": "completed",
            "result_id": None,
        },
        {
            "order": 2,
            "parent_message_id": CASE_G_ROOT_THALES_MESSAGE_ID,
            "tool_call_id": CASE_G_THALES_ROOT_CALL_ID,
            "agent": "thales",
            "child_session_id": CASE_G_THALES_SESSION_ID,
            "executed": False,
            "state": "completed",
            "result_id": None,
        },
    ]
    expected_report = {
        "task_id": "P11-G-reconcile-write",
        "source": CASE_G_BASELINE_SOURCE,
        "label": CASE_G_LABEL,
        "evidence_artifact": "tests/phase11-integrated-routing/case-g.native-trace.json",
        "root_export_artifact": "tests/phase11-integrated-routing/case-g.root.session-export.json",
        "veyra_export_artifact": "tests/phase11-integrated-routing/case-g.veyra.session-export.json",
        "thales_export_artifact": "tests/phase11-integrated-routing/case-g.thales.session-export.json",
        "evidence_class": "FRESH_ROOT_NATIVE",
        "root_session_id": CASE_G_ROOT_SESSION_ID,
        "root_directory": CASE_G_ROOT_DIRECTORY,
        "root_agent": "kael",
        "root_parent_session_id": None,
        "root_parent_session_id_observation": "NOT_EXPOSED_IN_EXPORT; NULL_SUPPLIED_IN_TASK_CONTEXT",
        "root_title": CASE_G_ROOT_TITLE,
        "root_terminal_outcome": "succeeded",
        "root_user_message_id": CASE_G_ROOT_USER_MESSAGE_ID,
        "root_terminal_message_id": CASE_G_ROOT_TERMINAL_MESSAGE_ID,
        "root_idle_message_id": CASE_G_ROOT_IDLE_MESSAGE_ID,
        "root_starting_head": CASE_G_ROOT_HEAD,
        "root_starting_head_source": "Original root user prompt",
        "root_starting_head_filesystem_verified_by_reconciliation": False,
        "expected_product_route": CASE_G_EXPECTED_ROUTE,
        "observed_product_route": CASE_G_EXPECTED_ROUTE,
        "root_tool_calls": expected_root_calls,
        "consultation_counts": CASE_G_ROLE_COUNTS,
        "unique_child_session_counts": CASE_G_ROLE_COUNTS,
        "nox_actual_measurement_owner": True,
        "nox_measurements_performed": 0,
        "thales_followup": expected_thales_followup,
        "tool_executed_flag_caveat": (
            "The public exports report executed=false on both root subagent calls and Veyra's read call even though each observed tool state is completed; the linked child session exports succeeded and the root terminal reports child results consumed. Preserve this flag, but do not interpret it as proof of non-execution or as negating completed results."
        ),
        "argus_same_session_followup_runtime_coverage": "NOT_EXERCISED",
        "terminal_facts": CASE_G_ROOT_TERMINAL_FACTS,
        "acceptance_status": "PASS",
        "case_result": "FRESH_ROOT_NATIVE_ACCEPTANCE_PASS",
        "phase11_status": "PARTIAL",
        "pending_fresh_root_labels": CURRENT_PHASE11_PENDING_LABELS,
        "case_rerun_performed_by_reconciliation": False,
        "reconciliation_files_changed": CASE_G_RECONCILIATION_FILES_CHANGED,
    }
    for key, expected in expected_report.items():
        if report.get(key) != expected:
            errors.append(f"CASE_G_BASELINE_RECONCILIATION_MISMATCH:{key}")

    expected_projection = {
        "root_reasoning_blocks_removed": 3,
        "veyra_reasoning_blocks_removed": 2,
        "thales_reasoning_blocks_removed": 2,
        "secret_values_redacted": 0,
        "provider_state_and_snapshots_omitted": True,
        "tool_arguments_and_results_omitted": True,
        "raw_exports_persisted": False,
    }
    if report.get("projection_and_redaction") != expected_projection:
        errors.append("CASE_G_BASELINE_PROJECTION_OR_REDACTION_MISMATCH")
    expected_completion = {
        "pending_child_count": 0,
        "unconsumed_result_count": 0,
        "unknown_execution_count": 0,
        "required_children_terminal_and_consumed": True,
        "result_ids": None,
        "per_invocation_consumption_timing": None,
        "session_lifetime_exact_once": None,
    }
    if report.get("completion_gate") != expected_completion:
        errors.append("CASE_G_BASELINE_COMPLETION_OR_RESULT_ID_OVERCLAIM")
    if report.get("classifications") != CASE_G_CLASSIFICATIONS or report.get("efficiency") != "LEAN":
        errors.append("CASE_G_BASELINE_CLASSIFICATION_OR_EFFICIENCY_MISMATCH")

    current = baseline.get("live_qualification", {})
    if (
        current.get("pending_labels") != CURRENT_PHASE11_PENDING_LABELS
        or current.get("fresh_root_native") != CURRENT_PHASE11_FRESH_ROOT_STATE
        or current.get("overall_status") != "PARTIAL"
        or "P11-G-reconcile-write" not in current.get("current_pending_state_source", "")
    ):
        errors.append("CURRENT_PHASE11_G_PENDING_STATE_MISMATCH")
    for snapshot_name in (
        "phase11_b3_reconciliation", "phase11_c_reconciliation", "phase11_d_reconciliation",
        "phase11_e_reconciliation", "phase11_e2_reconciliation", "phase11_f_reconciliation",
    ):
        snapshot = baseline.get(snapshot_name, {})
        if "HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT" not in snapshot.get("pending_fresh_root_labels", []):
            errors.append(f"CASE_G_HISTORICAL_PENDING_SNAPSHOT_REWRITTEN:{snapshot_name}")

    actions = [
        action for action in cases_doc.get("fresh_root_actions", [])
        if isinstance(action, dict) and action.get("case_id") == "G" and action.get("label") == CASE_G_LABEL
    ]
    expected_action = {
        "scenario": "default",
        "status": "PASS",
        "evidence_class": "FRESH_ROOT_NATIVE",
        "evidence_artifact": "case-g.native-trace.json",
        "acceptance_status": "PASS",
        "pending_resolution": False,
    }
    if len(actions) != 1 or any(actions[0].get(key) != value for key, value in expected_action.items()):
        errors.append("CASE_G_MATRIX_STATUS_OR_EVIDENCE_LINK_MISMATCH")
    if baseline.get("argus_same_session_followup_runtime_coverage") != CASE_D_PENDING_FOLLOWUP_COVERAGE:
        errors.append("CASE_G_ARGUS_FOLLOWUP_RUNTIME_COVERAGE_PROMOTED_OR_CONFLATED")
    return errors


def main() -> int:
    failures, documents = validate_corpus()
    static_failures = run_static_baseline_checks()
    baseline = load_json(HERE / "baseline.json")
    native_b3 = load_json(HERE / "case-b3.native-trace.json")
    native_c = load_json(HERE / "case-c.native-trace.json")
    native_d = load_json(HERE / "case-d.native-trace.json")
    native_e = load_json(HERE / "case-e.native-trace.json")
    case_e_export = load_json(HERE / "case-e.root-session.export.json")
    native_e2 = load_json(HERE / "case-e2.native-trace.json")
    case_e2_root_export = load_json(HERE / "case-e2.root-session.export.json")
    case_e2_child_export = load_json(HERE / "case-e2.talos-session.export.json")
    native_f = load_json(HERE / "case-f.native-trace.json")
    case_f_root_export = load_json(HERE / "case-f.root-session.export.json")
    native_g = load_json(HERE / "case-g.native-trace.json")
    case_g_root_export = load_json(HERE / "case-g.root.session-export.json")
    case_g_veyra_export = load_json(HERE / "case-g.veyra.session-export.json")
    case_g_thales_export = load_json(HERE / "case-g.thales.session-export.json")
    reconciliation_failures = validate_phase11_b3_reconciliation(
        baseline, documents["cases"], native_b3
    )
    case_c_failures = validate_phase11_c_reconciliation(
        baseline, documents["cases"], native_c
    )
    case_d_failures = validate_phase11_d_reconciliation(
        baseline, documents["cases"], native_d
    )
    case_e_failures = validate_phase11_e_reconciliation(
        baseline, documents["cases"], native_e, case_e_export
    )
    case_e2_failures = validate_phase11_e2_reconciliation(
        baseline,
        documents["cases"],
        native_e2,
        case_e2_root_export,
        case_e2_child_export,
    )
    case_f_failures = validate_phase11_f_reconciliation(
        baseline, documents["cases"], native_f, case_f_root_export
    )
    case_g_failures = validate_phase11_g_reconciliation(
        baseline,
        documents["cases"],
        native_g,
        case_g_root_export,
        case_g_veyra_export,
        case_g_thales_export,
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
    if not case_e_failures:
        print("E1-NATIVE: HISTORICAL_FAILURE_PRESERVED (original product route Kael-only versus required Kael -> Talos remains FAIL)")
    if not case_e2_failures:
        print("E2-NATIVE: PASS (FRESH_ROOT_NATIVE; direct Talos child and route reconciled; E1 failure retained as history)")
    if not case_f_failures:
        print("F-NATIVE: PASS (FRESH_ROOT_NATIVE; Kael-only operational diagnosis; no product/security defect invented)")
    if not case_g_failures:
        print("G-NATIVE: PASS (FRESH_ROOT_NATIVE; Veyra source evidence precedes one Thales diagnosis; no Nox measurement or unneeded follow-up)")
    pending_fresh_root_cases = {"H", "K"}
    pending_labels: list[str] = []
    for action in documents["cases"].get("fresh_root_actions", []):
        case_id = action.get("case_id")
        if case_id in pending_fresh_root_cases:
            label = action.get("label", f"PHASE11_CASE_{case_id}_FRESH_ROOT")
            pending_labels.append(label)
            if case_id == "E" and action.get("status") == CASE_E_NATIVE_RESULT:
                print(f"PENDING_ACCEPTANCE {label} (observed routing failure; no Case E rerun requested)")
            else:
                print(f"HUMAN_ACTION_REQUIRED {label}")
    if failures or reconciliation_failures or case_c_failures or case_d_failures or case_e_failures or case_e2_failures or case_f_failures or case_g_failures:
        for failure in [
            *failures,
            *reconciliation_failures,
            *case_c_failures,
            *case_d_failures,
            *case_e_failures,
            *case_e2_failures,
            *case_f_failures,
            *case_g_failures,
        ]:
            print(f"FAIL: {failure}")
        print("PHASE11_QUALIFICATION: FAIL (artifact validation only)")
        return 1
    if static_failures:
        for label in static_failures:
            print(f"FAIL: STATIC_{label}")
        print("PHASE11_QUALIFICATION: FAIL (bounded policy marker check)")
        return 1
    print("PHASE11_ARTIFACTS: PASS (synthetic/static artifacts, B3/C/D/E2/F/G native reconciliations, and E1 historical failure are internally consistent; validation does not authenticate source exports)")
    print("ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE: NOT_EXERCISED (separate optional evidence-requesting scenario remains open for final coverage review; not a Case D blocker)")
    print("PENDING_CASES: " + ", ".join(pending_labels) + "; F and G are accepted natively, E2 closes current Case E acceptance while E1's observed routing failure remains historical; A/I/J/L recovered reports remain guided/history only.")
    print("PHASE11_QUALIFICATION: PARTIAL (B3, C, D, E2, F, and G accepted; E1 failure retained as history; H/K acceptance remains pending)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
