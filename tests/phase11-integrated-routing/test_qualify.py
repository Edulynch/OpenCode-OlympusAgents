"""Semantic positive traces and adversarial mutations for Phase 11 artifacts."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from qualify import (
    CASE_B2_CHILD_SESSION_IDS,
    CASE_B2_ROOT_SESSION_ID,
    CASE_C_NOX_SESSION_ID,
    CASE_E_CLASSIFICATIONS,
    CASE_E_EXPECTED_ROUTE,
    CASE_F_CLASSIFICATIONS,
    CASE_F_COLLECTOR_SESSION_ID,
    CASE_F_EXPECTED_ROUTE,
    CASE_F_ROOT_SESSION_ID,
    CASE_G_CLASSIFICATIONS,
    CASE_G_EXPECTED_ROUTE,
    CASE_G_ROOT_SESSION_ID,
    CASE_G_THALES_SESSION_ID,
    CASE_G_VEYRA_SESSION_ID,
    CASE_H_CLASSIFICATIONS,
    CASE_H_EXPECTED_ROUTE,
    CASE_H_ROOT_SESSION_ID,
    CASE_H_VEYRA_SESSION_ID,
    EIGHT_SPECIALISTS,
    HARD_BUDGET,
    load_json,
    run_static_baseline_checks,
    validate_case_b_reconciliation,
    validate_native_case_c_capture,
    validate_native_case_d_capture,
    validate_native_case_e_capture,
    validate_native_case_e2_capture,
    validate_native_case_f_capture,
    validate_native_case_g_capture,
    validate_native_case_h_capture,
    validate_native_invocation_capture,
    validate_phase11_c_reconciliation,
    validate_phase11_d_reconciliation,
    validate_phase11_e_reconciliation,
    validate_phase11_e2_reconciliation,
    validate_phase11_f_reconciliation,
    validate_phase11_g_reconciliation,
    validate_phase11_h_reconciliation,
    validate_phase11_b3_reconciliation,
    validate_trace,
)


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CASES_DOC = load_json(HERE / "cases.json")
TRACES_DOC = load_json(HERE / "traces.json")
BASELINE_DOC = load_json(HERE / "baseline.json")
NATIVE_B3_DOC = load_json(HERE / "case-b3.native-trace.json")
NATIVE_C_DOC = load_json(HERE / "case-c.native-trace.json")
NATIVE_D_DOC = load_json(HERE / "case-d.native-trace.json")
NATIVE_E_DOC = load_json(HERE / "case-e.native-trace.json")
NATIVE_E_EXPORT_DOC = load_json(HERE / "case-e.root-session.export.json")
NATIVE_E2_DOC = load_json(HERE / "case-e2.native-trace.json")
NATIVE_E2_ROOT_EXPORT_DOC = load_json(HERE / "case-e2.root-session.export.json")
NATIVE_E2_CHILD_EXPORT_DOC = load_json(HERE / "case-e2.talos-session.export.json")
NATIVE_F_DOC = load_json(HERE / "case-f.native-trace.json")
NATIVE_F_EXPORT_DOC = load_json(HERE / "case-f.root-session.export.json")
NATIVE_G_DOC = load_json(HERE / "case-g.native-trace.json")
NATIVE_G_ROOT_EXPORT_DOC = load_json(HERE / "case-g.root.session-export.json")
NATIVE_G_VEYRA_EXPORT_DOC = load_json(HERE / "case-g.veyra.session-export.json")
NATIVE_G_THALES_EXPORT_DOC = load_json(HERE / "case-g.thales.session-export.json")
NATIVE_H_DOC = load_json(HERE / "case-h.native-trace.json")
NATIVE_H_ROOT_EXPORT_DOC = load_json(HERE / "case-h.root.session-export.json")
NATIVE_H_VEYRA_EXPORT_DOC = load_json(HERE / "case-h.veyra.session-export.json")
CASES = {case["id"]: case for case in CASES_DOC["cases"]}
TRACES = {trace["TRACE_ID"]: trace for trace in TRACES_DOC["traces"]}


def changed(trace_id: str) -> dict:
    return copy.deepcopy(TRACES[trace_id])


def failures(trace: dict) -> set[str]:
    return set(validate_trace(trace, CASES[trace["CASE_ID"]]))


def insert_event(trace: dict, event: dict, before_kind: str = "FINAL_OUTCOME") -> None:
    """Insert an adversarial event and keep synthetic sequence labels monotonic."""
    target = next(i for i, item in enumerate(trace["EVENTS"]) if item["KIND"] == before_kind)
    for item in trace["EVENTS"][target:]:
        item["ORDER"] += 1
    event["ORDER"] = trace["EVENTS"][target - 1]["ORDER"] + 1 if target else 1
    event.setdefault("ORDER_BASIS", "synthetic")
    trace["EVENTS"].insert(target, event)


class CorpusTests(unittest.TestCase):
    def test_all_authored_traces_are_semantically_valid(self) -> None:
        self.assertEqual(set(CASES), set("ABCDEFGHIJKL"))
        declared = {trace_id for case in CASES_DOC["cases"] for trace_id in case["trace_ids"]}
        self.assertEqual(declared, set(TRACES))
        for trace_id, trace in TRACES.items():
            with self.subTest(trace=trace_id):
                self.assertEqual([], validate_trace(trace, CASES[trace["CASE_ID"]]))

    def test_presence_only_policy_markers_pass(self) -> None:
        self.assertEqual([], run_static_baseline_checks())

    def test_case_b_no_atlas_route_is_artifact_pass_not_native_acceptance(self) -> None:
        trace = TRACES["B"]
        self.assertTrue(trace["GATE_FACTS"]["COMPLEX_FEATURE"])
        self.assertFalse(trace["GATE_FACTS"]["EXPLICIT_PLANNING_INTENT"])
        self.assertEqual(["kael", "veyra", "kovan", "nox", "vera"], trace["EXPECTED_ROUTE"])
        self.assertEqual(trace["EXPECTED_ROUTE"], trace["ACTUAL_ROUTE"])
        self.assertEqual(0, trace["CONSULTATION_COUNTS"]["atlas"])
        self.assertNotIn("atlas", [child["AGENT"] for child in trace["CHILD_SESSIONS"]])
        self.assertEqual([], validate_trace(trace, CASES["B"]))
        self.assertEqual(
            {"feature-tests", "feature-review"},
            {edge["after_work_id"] for edge in CASES["B"]["mandatory_dependency_edges"]},
        )

    def test_case_b_reconciliation_keeps_identity_and_partial_classifications(self) -> None:
        self.assertEqual([], validate_case_b_reconciliation(BASELINE_DOC))
        report = BASELINE_DOC["phase11_b2_reconciliation"]
        self.assertEqual("FIXTURE_DEFECT", report["case_b1"]["classification"])
        self.assertEqual("PASS", report["case_b1"]["question_barrier"])
        case_b2 = report["case_b2"]
        self.assertEqual(CASE_B2_ROOT_SESSION_ID, case_b2["root"]["session_id"])
        self.assertEqual(set(CASE_B2_CHILD_SESSION_IDS), set(case_b2["direct_children"]))
        self.assertEqual("FAIL", case_b2["classifications"]["CASE_B2_FRESH_ROOT_ISOLATION"])
        self.assertEqual("PARTIAL", case_b2["classifications"]["CASE_B2_FRESH_ROOT_ACCEPTANCE"])
        self.assertEqual("PARTIAL", report["phase11_status"])
        self.assertIsNone(case_b2["unknowns"]["event_order"])
        self.assertIsNone(case_b2["unknowns"]["concurrency"])
        self.assertEqual("PHASE11_CASE_B_FRESH_ROOT_3", report["next_action"]["label"])

    def test_synthetic_evidence_never_claims_native_session_ids(self) -> None:
        for trace_id, trace in TRACES.items():
            with self.subTest(trace=trace_id):
                self.assertEqual("SYNTHETIC_TRACE", trace["EVIDENCE_CLASS"])
                self.assertIsNone(trace["EVIDENCE_PROVENANCE"]["NATIVE_ROOT_SESSION_ID"])
                self.assertEqual([], trace["EVIDENCE_PROVENANCE"]["NATIVE_CHILD_SESSION_IDS"])
                self.assertTrue(all(child["NATIVE_SESSION_ID"] is None for child in trace["CHILD_SESSIONS"]))

    def test_b3_native_invocations_are_separate_from_synthetic_session_lifecycle(self) -> None:
        trace = NATIVE_B3_DOC
        self.assertEqual([], validate_native_invocation_capture(trace, CASES["B"]))
        self.assertEqual([], validate_phase11_b3_reconciliation(BASELINE_DOC, CASES_DOC, trace))
        self.assertNotIn("B3-NATIVE", TRACES)
        self.assertTrue(all(item["EVIDENCE_CLASS"] == "SYNTHETIC_TRACE" for item in TRACES.values()))
        self.assertEqual(
            {"nox": 3, "veyra": 1, "kovan": 1, "vera": 2},
            {role: count for role, count in trace["CONSULTATION_COUNTS"].items() if count},
        )
        self.assertEqual(
            {"nox": 1, "veyra": 1, "kovan": 1, "vera": 1},
            {role: count for role, count in trace["UNIQUE_CHILD_SESSION_COUNTS"].items() if count},
        )
        self.assertIsNone(trace["COMPLETION_GATE"]["SESSION_LIFETIME_EXACT_ONCE"])
        self.assertIsNone(trace["MAX_SIMULTANEOUS_CHILDREN"])
        self.assertIsNone(trace["GATE_FACTS"]["SECURITY_BOUNDARY"])
        self.assertEqual(13, trace["RUNTIME_VALIDATION"]["TESTS_PASSED"])
        self.assertEqual(
            "OBSERVED_NATIVE_ROOT_TERMINAL_MESSAGE",
            trace["OBSERVED_TERMINAL_SNAPSHOT"]["OBSERVATION"],
        )
        self.assertEqual(
            trace["OBSERVED_TERMINAL_SNAPSHOT"]["FACTS"],
            trace["EVENTS"][-1]["TERMINAL_FACTS"],
        )
        self.assertEqual(3, len(trace["SESSION_RECONCILIATION"]["kovan"]["REPORTED_CHANGED_PATHS"]))
        self.assertEqual("PARTIAL", BASELINE_DOC["phase11_b3_reconciliation"]["phase11_status"])
        self.assertEqual("PASS", CASES_DOC["fresh_root_actions"][1]["status"])

    def test_case_c_native_capture_preserves_isolation_and_product_routes_separately(self) -> None:
        trace = NATIVE_C_DOC
        self.assertEqual([], validate_native_case_c_capture(trace, CASES["C"]))
        self.assertEqual([], validate_phase11_c_reconciliation(BASELINE_DOC, CASES_DOC, trace))
        self.assertNotIn("C-NATIVE", TRACES)
        self.assertTrue(all(item["EVIDENCE_CLASS"] == "SYNTHETIC_TRACE" for item in TRACES.values()))
        self.assertEqual(["kael", "kovan"], trace["EXPECTED_ROUTE"])
        self.assertEqual(["kael", "nox", "kovan"], trace["ACTUAL_ROUTE"])
        self.assertEqual(0, trace["NEGATIVE_CONTROLS"]["argus"]["INVOCATIONS"])
        self.assertEqual(0, trace["NEGATIVE_CONTROLS"]["veyra"]["INVOCATIONS"])
        self.assertEqual(0, trace["NEGATIVE_CONTROLS"]["vera"]["INVOCATIONS"])
        self.assertEqual("PASS", trace["ROUTING_RESULT_DETAIL"]["NEGATIVE_ARGUS_CONTROL"])
        self.assertEqual(1, trace["MAX_SIMULTANEOUS_CHILDREN"])
        self.assertEqual("LEAN", trace["OPERATIONAL_PROXIES"]["EFFICIENCY_CLASSIFICATION"])
        self.assertIsNone(trace["COMPLETION_GATE"]["SESSION_LIFETIME_EXACT_ONCE"])
        self.assertIsNone(trace["EVENTS"][0]["CALL_CREATED_AT_EPOCH_MS"])
        for fact in (
            "EXPLICIT_OPTIMIZATION_INTENT",
            "EXPLICIT_PLANNING_INTENT",
            "SECURITY_BOUNDARY",
            "OPERATIONAL_TOOLING_FAILURE",
            "HIGH_UNCERTAINTY_AFTER_BOUNDED_DIAGNOSIS",
            "THIRD_PARTY_BUG",
            "FAST_PROFILE_REQUESTED",
            "MAINTENANCE_ENTRY_EXPLICIT",
        ):
            self.assertIsNone(trace["GATE_FACTS"][fact])
        self.assertTrue(all(event["ORDER_BASIS"] == "observed" for event in trace["CHILD_TOOL_EVENTS"]))
        self.assertNotIn("CASE_C_FRESH_ROOT_NATIVE", trace["OBSERVED_TERMINAL_SNAPSHOT"]["FACTS"])
        self.assertNotIn("git diff --check", trace["OBSERVED_TERMINAL_SNAPSHOT"]["FACTS"].values())
        self.assertEqual("PARTIAL", BASELINE_DOC["phase11_c_reconciliation"]["phase11_status"])
        self.assertEqual("PASS", CASES_DOC["fresh_root_actions"][2]["status"])
        self.assertEqual(
            "HUMAN_ACTION_REQUIRED PHASE11_CASE_C_FRESH_ROOT",
            BASELINE_DOC["phase11_b3_reconciliation"]["pending_fresh_root_labels"][0],
        )


class NativeCaptureMutationTests(unittest.TestCase):
    def test_native_isolation_requires_joined_directory_head_and_no_creation_claim(self) -> None:
        missing_root_directory = copy.deepcopy(NATIVE_B3_DOC)
        missing_root_directory.pop("ROOT_DIRECTORY")
        self.assertIn(
            "NATIVE_FRESH_ROOT_ISOLATION_MISMATCH",
            validate_native_invocation_capture(missing_root_directory, CASES["B"]),
        )

        contradictory_directory = copy.deepcopy(NATIVE_B3_DOC)
        contradictory_directory["ROOT_ISOLATION"]["VERIFIED_DIRECTORY"] = "C:/temp/other-copy"
        self.assertIn(
            "NATIVE_FRESH_ROOT_ISOLATION_MISMATCH",
            validate_native_invocation_capture(contradictory_directory, CASES["B"]),
        )

        nox_directory_mismatch = copy.deepcopy(NATIVE_B3_DOC)
        nox_directory_mismatch["SESSION_RECONCILIATION"]["nox"]["VERIFIED_DIRECTORY"] = "C:/temp/other-copy"
        self.assertIn(
            "NATIVE_SAME_SESSION_RECONCILIATION_MISMATCH",
            validate_native_invocation_capture(nox_directory_mismatch, CASES["B"]),
        )

        fabricated_creation = copy.deepcopy(NATIVE_B3_DOC)
        event = fabricated_creation["EVENTS"][0]
        event["RETURN_SUMMARY"] = "Created a new worktree and verified its HEAD."
        event["WORKTREE_CREATION_CLAIMED"] = True
        self.assertIn(
            "NATIVE_ISOLATION_EVENT_NOT_VERIFICATION_ONLY",
            validate_native_invocation_capture(fabricated_creation, CASES["B"]),
        )

        baseline_path_conflict = copy.deepcopy(BASELINE_DOC)
        baseline_path_conflict["phase11_b3_reconciliation"]["root_directory"] = "C:/temp/other-copy"
        self.assertIn(
            "CASE_B3_ROOT_DIRECTORY_MISMATCH",
            validate_phase11_b3_reconciliation(baseline_path_conflict, CASES_DOC, NATIVE_B3_DOC),
        )

    def test_native_terminal_snapshot_must_match_runtime_isolation_and_completion(self) -> None:
        wrong_snapshot_test_count = copy.deepcopy(NATIVE_B3_DOC)
        wrong_snapshot_test_count["OBSERVED_TERMINAL_SNAPSHOT"]["FACTS"]["TEST_COUNT"] = 12
        self.assertIn(
            "NATIVE_TERMINAL_SNAPSHOT_MISMATCH",
            validate_native_invocation_capture(wrong_snapshot_test_count, CASES["B"]),
        )

        contradictory_runtime = copy.deepcopy(NATIVE_B3_DOC)
        contradictory_runtime["RUNTIME_VALIDATION"]["SOURCE_INTEGRITY_AFTER_TEST"] = "FAIL"
        errors = validate_native_invocation_capture(contradictory_runtime, CASES["B"])
        self.assertIn("NATIVE_RUNTIME_VALIDATION_FACTS_MISMATCH", errors)
        self.assertIn("NATIVE_TERMINAL_FACTS_DO_NOT_MATCH_VALIDATION_RECORDS", errors)

        contradictory_completion = copy.deepcopy(NATIVE_B3_DOC)
        contradictory_completion["EVENTS"][-1]["REQUIRED_CHILD_SESSIONS_TERMINAL_AND_CONSUMED"] = False
        errors = validate_native_invocation_capture(contradictory_completion, CASES["B"])
        self.assertIn("NATIVE_FINAL_COMPLETION_FACTS_MISMATCH", errors)
        self.assertIn("NATIVE_TERMINAL_FACTS_DO_NOT_MATCH_VALIDATION_RECORDS", errors)

        conflated_provenance = copy.deepcopy(NATIVE_B3_DOC)
        conflated_provenance["RESULT_FIDELITY"]["OBSERVED_RESULT_SOURCE"] = "task acceptance context"
        self.assertIn(
            "NATIVE_RESULT_FIDELITY_MISMATCH",
            validate_native_invocation_capture(conflated_provenance, CASES["B"]),
        )

        baseline_snapshot_mismatch = copy.deepcopy(BASELINE_DOC)
        baseline_snapshot_mismatch["phase11_b3_reconciliation"]["observed_terminal_snapshot"]["facts"]["TEST_COUNT"] = 12
        self.assertIn(
            "CASE_B3_BASELINE_TERMINAL_SNAPSHOT_MISMATCH",
            validate_phase11_b3_reconciliation(baseline_snapshot_mismatch, CASES_DOC, NATIVE_B3_DOC),
        )

    def test_native_capture_rejects_wrong_parent_role_and_native_ids(self) -> None:
        wrong_parent = copy.deepcopy(NATIVE_B3_DOC)
        wrong_parent["CHILD_SESSIONS"][2]["PARENT_SESSION_ID"] = "ses_wrongparent"
        self.assertIn(
            "NATIVE_CHILD_PARENT_MISMATCH:B3-KOVAN",
            validate_native_invocation_capture(wrong_parent, CASES["B"]),
        )

        wrong_role = copy.deepcopy(NATIVE_B3_DOC)
        wrong_role["CHILD_SESSIONS"][1]["AGENT"] = "kovan"
        self.assertIn(
            "NATIVE_CHILD_ROLE_OR_ORDER_MISMATCH:B3-VEYRA",
            validate_native_invocation_capture(wrong_role, CASES["B"]),
        )

        wrong_child_id = copy.deepcopy(NATIVE_B3_DOC)
        wrong_child_id["CHILD_SESSIONS"][0]["NATIVE_SESSION_ID"] = "ses_wrongnox"
        self.assertIn(
            "NATIVE_CHILD_SESSION_ID_MISMATCH:B3-NOX",
            validate_native_invocation_capture(wrong_child_id, CASES["B"]),
        )

        wrong_event_join = copy.deepcopy(NATIVE_B3_DOC)
        wrong_event_join["EVENTS"][3]["NATIVE_SESSION_ID"] = "ses_wrongnox"
        self.assertIn(
            "NATIVE_INVOCATION_SESSION_OR_ROLE_JOIN_MISMATCH:4",
            validate_native_invocation_capture(wrong_event_join, CASES["B"]),
        )

        wrong_call = copy.deepcopy(NATIVE_B3_DOC)
        wrong_call["EVENTS"][4]["TOOL_CALL_ID"] = "call_replacement"
        self.assertIn(
            "NATIVE_INVOCATION_ID_MISMATCH:5",
            validate_native_invocation_capture(wrong_call, CASES["B"]),
        )

    def test_native_capture_rejects_relabeling_order_or_fabricated_result_ids(self) -> None:
        relabelled = copy.deepcopy(NATIVE_B3_DOC)
        relabelled["EVIDENCE_CLASS"] = "SYNTHETIC_TRACE"
        self.assertIn(
            "NATIVE_EVIDENCE_CLASS_MISMATCH",
            validate_native_invocation_capture(relabelled, CASES["B"]),
        )

        wrong_basis = copy.deepcopy(NATIVE_B3_DOC)
        wrong_basis["EVENTS"][2]["ORDER_BASIS"] = "synthetic"
        self.assertIn(
            "NATIVE_EVENT_ORDER_BASIS_MISMATCH",
            validate_native_invocation_capture(wrong_basis, CASES["B"]),
        )

        wrong_order = copy.deepcopy(NATIVE_B3_DOC)
        wrong_order["EVENTS"][2]["ORDER"] = 2
        self.assertIn(
            "NATIVE_EVENT_ORDER_NOT_STRICTLY_INCREASING",
            validate_native_invocation_capture(wrong_order, CASES["B"]),
        )

        fabricated_result = copy.deepcopy(NATIVE_B3_DOC)
        fabricated_result["EVENTS"][0]["RESULT_ID"] = "result-invented"
        self.assertIn(
            "NATIVE_UNOBSERVED_RESULT_ID_MUST_REMAIN_NULL:1",
            validate_native_invocation_capture(fabricated_result, CASES["B"]),
        )

        fabricated_timestamp = copy.deepcopy(NATIVE_B3_DOC)
        fabricated_timestamp["EVIDENCE_PROVENANCE"]["OBSERVED_AT"] = "2026-10-03T00:00:00Z"
        self.assertIn(
            "NATIVE_UNOBSERVED_TIMESTAMP_MUST_REMAIN_NULL",
            validate_native_invocation_capture(fabricated_timestamp, CASES["B"]),
        )

        fabricated_gate = copy.deepcopy(NATIVE_B3_DOC)
        fabricated_gate["GATE_FACTS"]["SECURITY_BOUNDARY"] = False
        self.assertIn(
            "NATIVE_GATE_FACTS_MISMATCH",
            validate_native_invocation_capture(fabricated_gate, CASES["B"]),
        )

        overstated_tests = copy.deepcopy(NATIVE_B3_DOC)
        overstated_tests["RUNTIME_VALIDATION"]["TESTS_PASSED"] = 14
        self.assertIn(
            "NATIVE_RUNTIME_VALIDATION_FACTS_MISMATCH",
            validate_native_invocation_capture(overstated_tests, CASES["B"]),
        )

    def test_native_capture_rejects_false_completion_or_history_promotion(self) -> None:
        incomplete = copy.deepcopy(NATIVE_B3_DOC)
        incomplete["COMPLETION_GATE"]["PENDING_CHILD_COUNT"] = 1
        self.assertIn(
            "NATIVE_COMPLETION_GATE_MISMATCH",
            validate_native_invocation_capture(incomplete, CASES["B"]),
        )

        overclaimed_exact_once = copy.deepcopy(NATIVE_B3_DOC)
        overclaimed_exact_once["COMPLETION_GATE"]["SESSION_LIFETIME_EXACT_ONCE"] = True
        self.assertIn(
            "NATIVE_COMPLETION_GATE_MISMATCH",
            validate_native_invocation_capture(overclaimed_exact_once, CASES["B"]),
        )

        promoted_b2 = copy.deepcopy(BASELINE_DOC)
        promoted_b2["phase11_b2_reconciliation"]["case_b2"]["acceptance_status"] = "PASS"
        self.assertIn(
            "CASE_B2_ACCEPTANCE_MUST_REMAIN_PARTIAL",
            validate_phase11_b3_reconciliation(promoted_b2, CASES_DOC, NATIVE_B3_DOC),
        )

        promoted_guided = copy.deepcopy(BASELINE_DOC)
        promoted_guided["recovered_user_observations"]["case_observations"]["A"]["native_trace_in_scoped_corpus"] = True
        self.assertIn(
            "RECOVERED_HISTORY_NATIVE_TRACE_OVERCLAIM:A",
            validate_phase11_b3_reconciliation(promoted_guided, CASES_DOC, NATIVE_B3_DOC),
        )

        stale_pending = copy.deepcopy(BASELINE_DOC)
        stale_pending["live_qualification"]["pending_labels"].insert(
            0, "HUMAN_ACTION_REQUIRED PHASE11_CASE_B_FRESH_ROOT"
        )
        self.assertIn(
            "CURRENT_PHASE11_PENDING_STATE_MISMATCH",
            validate_phase11_b3_reconciliation(stale_pending, CASES_DOC, NATIVE_B3_DOC),
        )


class NativeCaseCMutationTests(unittest.TestCase):
    def test_case_c_authoritative_nox_identity_rejects_truncated_form(self) -> None:
        authoritative_id = "ses_efa05f4dfffe9s0gk5VEbkVRA9"
        self.assertEqual(authoritative_id, CASE_C_NOX_SESSION_ID)
        self.assertEqual(authoritative_id, NATIVE_C_DOC["CHILD_SESSIONS"][0]["NATIVE_SESSION_ID"])
        self.assertEqual(authoritative_id, NATIVE_C_DOC["EVIDENCE_PROVENANCE"]["NATIVE_CHILD_SESSION_IDS"][0])

        truncated_id = authoritative_id[:-1]
        self.assertEqual("ses_efa05f4dfffe9s0gk5VEbkVRA", truncated_id)
        truncated = copy.deepcopy(NATIVE_C_DOC)
        truncated["ROOT_ISOLATION"]["INITIAL_NOX_SESSION_ID"] = truncated_id
        truncated["CHILD_SESSIONS"][0]["NATIVE_SESSION_ID"] = truncated_id
        truncated["EVIDENCE_PROVENANCE"]["NATIVE_CHILD_SESSION_IDS"][0] = truncated_id
        for event in truncated["EVENTS"][:2]:
            event["NATIVE_SESSION_ID"] = truncated_id
        errors = validate_native_case_c_capture(truncated, CASES["C"])
        self.assertIn("NATIVE_C_CHILD_SESSION_ID_MISMATCH:C-NOX", errors)
        self.assertIn("NATIVE_C_PROVENANCE_MISMATCH", errors)

    def test_case_c_native_capture_binds_child_parent_role_and_identity(self) -> None:
        wrong_parent = copy.deepcopy(NATIVE_C_DOC)
        wrong_parent["CHILD_SESSIONS"][0]["PARENT_SESSION_ID"] = "ses_wrongparent"
        self.assertIn(
            "NATIVE_C_CHILD_PARENT_MISMATCH:C-NOX",
            validate_native_case_c_capture(wrong_parent, CASES["C"]),
        )

        wrong_role = copy.deepcopy(NATIVE_C_DOC)
        wrong_role["CHILD_SESSIONS"][0]["AGENT"] = "kovan"
        self.assertIn(
            "NATIVE_C_CHILD_ROLE_OR_ORDER_MISMATCH:C-NOX",
            validate_native_case_c_capture(wrong_role, CASES["C"]),
        )

        wrong_child_id = copy.deepcopy(NATIVE_C_DOC)
        wrong_child_id["CHILD_SESSIONS"][1]["NATIVE_SESSION_ID"] = "ses_wrongkovan"
        self.assertIn(
            "NATIVE_C_CHILD_SESSION_ID_MISMATCH:C-KOVAN",
            validate_native_case_c_capture(wrong_child_id, CASES["C"]),
        )

        wrong_event_join = copy.deepcopy(NATIVE_C_DOC)
        wrong_event_join["EVENTS"][3]["NATIVE_SESSION_ID"] = "ses_wrongkovan"
        self.assertIn(
            "NATIVE_C_INVOCATION_IDENTITY_OR_PARENT_MISMATCH:4",
            validate_native_case_c_capture(wrong_event_join, CASES["C"]),
        )

    def test_case_c_native_capture_requires_observed_invocation_order(self) -> None:
        duplicate_order = copy.deepcopy(NATIVE_C_DOC)
        duplicate_order["EVENTS"][2]["ORDER"] = 2
        self.assertIn(
            "NATIVE_C_EVENT_ORDER_NOT_STRICTLY_INCREASING",
            validate_native_case_c_capture(duplicate_order, CASES["C"]),
        )

        relabelled_order = copy.deepcopy(NATIVE_C_DOC)
        relabelled_order["EVENTS"][2]["ORDER_BASIS"] = "synthetic"
        self.assertIn(
            "NATIVE_C_EVENT_ORDER_BASIS_MISMATCH",
            validate_native_case_c_capture(relabelled_order, CASES["C"]),
        )

    def test_case_c_argus_nonactivation_is_first_class_evidence(self) -> None:
        activated = copy.deepcopy(NATIVE_C_DOC)
        activated["CONSULTATION_COUNTS"]["argus"] = 1
        activated["NEGATIVE_CONTROLS"]["argus"] = {"INVOCATIONS": 1, "UNIQUE_CHILD_SESSIONS": 1}
        errors = validate_native_case_c_capture(activated, CASES["C"])
        self.assertIn("NATIVE_C_ARGUS_NEGATIVE_CONTROL_ACTIVATED", errors)

        false_obvious_gate = copy.deepcopy(NATIVE_C_DOC)
        false_obvious_gate["GATE_FACTS"]["OBVIOUS_FUNCTIONAL_CAUSE"] = False
        self.assertIn(
            "NATIVE_C_OBVIOUS_CAUSE_GATE_MISMATCH",
            validate_native_case_c_capture(false_obvious_gate, CASES["C"]),
        )

        fabricated_intent = copy.deepcopy(NATIVE_C_DOC)
        fabricated_intent["GATE_FACTS"]["EXPLICIT_OPTIMIZATION_INTENT"] = False
        self.assertIn(
            "NATIVE_C_GATE_FACTS_MISMATCH",
            validate_native_case_c_capture(fabricated_intent, CASES["C"]),
        )

    def test_case_c_child_tool_events_require_observed_order_basis(self) -> None:
        missing_order_basis = copy.deepcopy(NATIVE_C_DOC)
        missing_order_basis["CHILD_TOOL_EVENTS"][1].pop("ORDER_BASIS")
        self.assertIn(
            "NATIVE_C_CHILD_TOOL_EVIDENCE_MISMATCH",
            validate_native_case_c_capture(missing_order_basis, CASES["C"]),
        )

    def test_case_c_false_completion_and_terminal_mismatch_are_rejected(self) -> None:
        false_completion = copy.deepcopy(NATIVE_C_DOC)
        false_completion["EVENTS"][-1]["UNCONSUMED_RESULT_COUNT"] = 1
        errors = validate_native_case_c_capture(false_completion, CASES["C"])
        self.assertIn("NATIVE_C_FINAL_COMPLETION_FACTS_MISMATCH", errors)

        wrong_terminal_snapshot = copy.deepcopy(NATIVE_C_DOC)
        wrong_terminal_snapshot["OBSERVED_TERMINAL_SNAPSHOT"]["FACTS"]["ANY_WORK_REMAINING"] = "YES"
        self.assertIn(
            "NATIVE_C_TERMINAL_SNAPSHOT_MISMATCH",
            validate_native_case_c_capture(wrong_terminal_snapshot, CASES["C"]),
        )

        wrong_child_terminal = copy.deepcopy(NATIVE_C_DOC)
        wrong_child_terminal["EVENTS"][3]["RETURN_STATUS"] = "FAILED"
        self.assertIn(
            "NATIVE_C_INVOCATION_TERMINAL_MISMATCH:4",
            validate_native_case_c_capture(wrong_child_terminal, CASES["C"]),
        )

        wrong_root_terminal = copy.deepcopy(NATIVE_C_DOC)
        wrong_root_terminal["ROOT_TERMINAL_OUTCOME"] = "failed"
        self.assertIn(
            "NATIVE_C_ROOT_TERMINAL_MISMATCH",
            validate_native_case_c_capture(wrong_root_terminal, CASES["C"]),
        )

    def test_case_c_status_promotion_keeps_b3_history_and_current_pending_distinct(self) -> None:
        stale_current = copy.deepcopy(BASELINE_DOC)
        stale_current["live_qualification"]["pending_labels"].insert(
            0, "HUMAN_ACTION_REQUIRED PHASE11_CASE_C_FRESH_ROOT"
        )
        self.assertIn(
            "CURRENT_PHASE11_PENDING_STATE_MISMATCH",
            validate_phase11_c_reconciliation(stale_current, CASES_DOC, NATIVE_C_DOC),
        )

        rewritten_b3_history = copy.deepcopy(BASELINE_DOC)
        rewritten_b3_history["phase11_b3_reconciliation"]["pending_fresh_root_labels"].remove(
            "HUMAN_ACTION_REQUIRED PHASE11_CASE_C_FRESH_ROOT"
        )
        self.assertIn(
            "CASE_B3_PENDING_LABELS_MISMATCH",
            validate_phase11_b3_reconciliation(rewritten_b3_history, CASES_DOC, NATIVE_B3_DOC),
        )

        shipped = copy.deepcopy(BASELINE_DOC)
        shipped["phase11_c_reconciliation"]["phase11_status"] = "SHIPPED"
        self.assertIn(
            "CASE_C_PHASE_STATUS_MUST_REMAIN_PARTIAL",
            validate_phase11_c_reconciliation(shipped, CASES_DOC, NATIVE_C_DOC),
        )


class NativeCaseDMutationTests(unittest.TestCase):
    def test_case_d_native_capture_accepts_bounded_diagnostic_limit_not_a_repair(self) -> None:
        self.assertEqual(["kael", "argus", "veyra"], CASES["D"]["expected_routes"]["default"])
        self.assertEqual(["kael", "veyra", "argus"], CASES["D"]["expected_routes"]["precollected_evidence"])
        self.assertNotIn("mandatory_dependency_edges", CASES["D"])
        self.assertEqual([], validate_native_case_d_capture(NATIVE_D_DOC, CASES["D"]))
        self.assertEqual([], validate_phase11_d_reconciliation(BASELINE_DOC, CASES_DOC, NATIVE_D_DOC))
        self.assertEqual("succeeded", NATIVE_D_DOC["ROOT_EXECUTION_OUTCOME"])
        self.assertEqual("NEEDS_USER_INPUT", NATIVE_D_DOC["FINAL_OUTCOME"])
        self.assertEqual("INCONCLUSIVE", NATIVE_D_DOC["ARGUS_DIAGNOSTIC"]["STATUS"])
        self.assertEqual("CAUSE_UNCONFIRMED. No functional violation is established.", NATIVE_D_DOC["ARGUS_DIAGNOSTIC"]["CAUSE"])
        self.assertFalse(NATIVE_D_DOC["RESULT_FIDELITY"]["FUNCTIONAL_VIOLATION_ESTABLISHED"])
        self.assertFalse(NATIVE_D_DOC["RESULT_FIDELITY"]["REPAIR_SUPPORTED"])
        self.assertEqual(1, NATIVE_D_DOC["CONSULTATION_COUNTS"]["argus"])
        self.assertEqual("NOT_REQUIRED", NATIVE_D_DOC["CASE_D_ARGUS_FOLLOWUP"])
        self.assertEqual("NOT_EXERCISED", NATIVE_D_DOC["ARGUS_SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE"])
        self.assertNotIn("HUMAN_ACTION_REQUIRED PHASE11_CASE_D_FRESH_ROOT", BASELINE_DOC["live_qualification"]["pending_labels"])
        self.assertIn("HUMAN_ACTION_REQUIRED PHASE11_CASE_D_FRESH_ROOT", BASELINE_DOC["phase11_c_reconciliation"]["pending_fresh_root_labels"])
        self.assertEqual("PARTIAL", BASELINE_DOC["live_qualification"]["overall_status"])

    def test_case_d_native_capture_rejects_wrong_identity_parent_role_and_order(self) -> None:
        wrong_parent = copy.deepcopy(NATIVE_D_DOC)
        wrong_parent["CHILD_SESSIONS"][0]["PARENT_SESSION_ID"] = "ses_wrongparent"
        self.assertIn("NATIVE_D_CHILD_SESSION_RECONCILIATION_MISMATCH", validate_native_case_d_capture(wrong_parent, CASES["D"]))
        wrong_role = copy.deepcopy(NATIVE_D_DOC)
        wrong_role["CHILD_SESSIONS"][1]["AGENT"] = "argus"
        self.assertIn("NATIVE_D_CHILD_SESSION_RECONCILIATION_MISMATCH", validate_native_case_d_capture(wrong_role, CASES["D"]))
        wrong_identity = copy.deepcopy(NATIVE_D_DOC)
        wrong_identity["CHILD_SESSIONS"][2]["NATIVE_SESSION_ID"] = "ses_wrongargus"
        self.assertIn("NATIVE_D_CHILD_SESSION_RECONCILIATION_MISMATCH", validate_native_case_d_capture(wrong_identity, CASES["D"]))
        wrong_event_join = copy.deepcopy(NATIVE_D_DOC)
        wrong_event_join["EVENTS"][4]["NATIVE_SESSION_ID"] = "ses_wrongveyra"
        self.assertIn("NATIVE_D_INVOCATION_SESSION_OR_ROLE_JOIN_MISMATCH:D-VEYRA", validate_native_case_d_capture(wrong_event_join, CASES["D"]))
        wrong_order = copy.deepcopy(NATIVE_D_DOC)
        wrong_order["EVENTS"][3]["ORDER"] = 3
        self.assertIn("NATIVE_D_EVENT_ORDER_NOT_OBSERVED", validate_native_case_d_capture(wrong_order, CASES["D"]))
        fabricated_result = copy.deepcopy(NATIVE_D_DOC)
        fabricated_result["EVENTS"][2]["RESULT_ID"] = "result-invented"
        self.assertIn("NATIVE_D_UNOBSERVED_RESULT_ID_OR_CONSUMPTION_EVENT", validate_native_case_d_capture(fabricated_result, CASES["D"]))

    def test_case_d_native_capture_rejects_unbarriered_question_forced_followup_and_false_completion(self) -> None:
        unbarriered = copy.deepcopy(NATIVE_D_DOC)
        unbarriered["QUESTION_BARRIER"]["DISPLAYED_AFTER_ALL_CHILDREN_TERMINAL_AND_CONSUMED"] = False
        self.assertIn("NATIVE_D_QUESTION_BARRIER_MISMATCH", validate_native_case_d_capture(unbarriered, CASES["D"]))
        forced_followup = copy.deepcopy(NATIVE_D_DOC)
        forced_followup["ARGUS_DIAGNOSTIC"]["CONSULTATION_COUNT"] = 2
        self.assertIn("NATIVE_D_DIAGNOSTIC_AND_OUTCOME_STATUS_MISMATCH", validate_native_case_d_capture(forced_followup, CASES["D"]))
        false_completion = copy.deepcopy(NATIVE_D_DOC)
        false_completion["COMPLETION_GATE"]["PENDING_CHILD_COUNT"] = 1
        self.assertIn("NATIVE_D_COMPLETION_GATE_MISMATCH", validate_native_case_d_capture(false_completion, CASES["D"]))
        wrong_status = copy.deepcopy(NATIVE_D_DOC)
        wrong_status["ROOT_EXECUTION_OUTCOME"] = "NEEDS_USER_INPUT"
        self.assertIn("NATIVE_D_EXECUTION_AND_SEMANTIC_OUTCOME_CONFLATED", validate_native_case_d_capture(wrong_status, CASES["D"]))
        invented_cause = copy.deepcopy(NATIVE_D_DOC)
        invented_cause["RESULT_FIDELITY"]["FUNCTIONAL_VIOLATION_ESTABLISHED"] = True
        self.assertIn("NATIVE_D_RESULT_FIDELITY_MISMATCH", validate_native_case_d_capture(invented_cause, CASES["D"]))

    def test_case_d_tool_delivery_session_execution_and_diagnostic_statuses_are_distinct(self) -> None:
        returns = [event for event in NATIVE_D_DOC["EVENTS"] if event["KIND"] == "ROOT_SUBAGENT_RESULT_RETURNED"]
        self.assertEqual(["completed"] * 3, [event["TOOL_STATE"] for event in returns])
        self.assertEqual(["succeeded"] * 3, [event["CHILD_EXECUTION_OUTCOME"] for event in returns])
        self.assertEqual([None, None, "INCONCLUSIVE"], [event["RETURN_STATUS"] for event in returns])
        self.assertEqual([], validate_native_case_d_capture(NATIVE_D_DOC, CASES["D"]))

        mislabeled_argus = copy.deepcopy(NATIVE_D_DOC)
        mislabeled_argus["EVENTS"][8]["RETURN_STATUS"] = "SUCCESS"
        errors = validate_native_case_d_capture(mislabeled_argus, CASES["D"])
        self.assertIn("NATIVE_D_LITERAL_RETURN_STATUS_OR_TOOL_STATE_MISMATCH:D-ARGUS", errors)
        self.assertIn("NATIVE_D_DIAGNOSTIC_AND_OUTCOME_STATUS_MISMATCH", errors)

        fabricated_nox_status = copy.deepcopy(NATIVE_D_DOC)
        fabricated_nox_status["EVENTS"][2]["RETURN_STATUS"] = "SUCCESS"
        self.assertIn(
            "NATIVE_D_LITERAL_RETURN_STATUS_OR_TOOL_STATE_MISMATCH:D-NOX",
            validate_native_case_d_capture(fabricated_nox_status, CASES["D"]),
        )
        fabricated_veyra_status = copy.deepcopy(NATIVE_D_DOC)
        fabricated_veyra_status["EVENTS"][5]["RETURN_STATUS"] = "SUCCESS"
        self.assertIn(
            "NATIVE_D_LITERAL_RETURN_STATUS_OR_TOOL_STATE_MISMATCH:D-VEYRA",
            validate_native_case_d_capture(fabricated_veyra_status, CASES["D"]),
        )

        execution_as_resolution = copy.deepcopy(NATIVE_D_DOC)
        execution_as_resolution["FINAL_OUTCOME"] = "succeeded"
        execution_as_resolution["EVENTS"][9]["SEMANTIC_FINAL_OUTCOME"] = "succeeded"
        self.assertIn(
            "NATIVE_D_EXECUTION_AND_SEMANTIC_OUTCOME_CONFLATED",
            validate_native_case_d_capture(execution_as_resolution, CASES["D"]),
        )

    def test_case_d_followup_coverage_cannot_be_promoted_or_moved_into_pending_cases(self) -> None:
        promoted = copy.deepcopy(BASELINE_DOC)
        promoted["argus_same_session_followup_runtime_coverage"]["status"] = "PASS"
        self.assertIn(
            "ARGUS_FOLLOWUP_RUNTIME_COVERAGE_PROMOTED_OR_CONFLATED",
            validate_phase11_d_reconciliation(promoted, CASES_DOC, NATIVE_D_DOC),
        )
        relabeled_pending = copy.deepcopy(BASELINE_DOC)
        relabeled_pending["live_qualification"]["pending_labels"].insert(0, "HUMAN_ACTION_REQUIRED PHASE11_CASE_D_FRESH_ROOT")
        self.assertIn(
            "CURRENT_PHASE11_PENDING_STATE_MISMATCH",
            validate_phase11_d_reconciliation(relabeled_pending, CASES_DOC, NATIVE_D_DOC),
        )
        false_completion = copy.deepcopy(BASELINE_DOC)
        false_completion["phase11_d_reconciliation"]["result_consumption"]["pending_children"] = 1
        self.assertIn(
            "CASE_D_RECONCILIATION_FACT_MISMATCH:result_consumption",
            validate_phase11_d_reconciliation(false_completion, CASES_DOC, NATIVE_D_DOC),
        )


class NativeCaseEMutationTests(unittest.TestCase):
    def test_case_e_reconciles_original_native_failure_without_promoting_acceptance(self) -> None:
        self.assertEqual(CASE_E_EXPECTED_ROUTE, ["kael", "talos"])
        self.assertEqual([], validate_native_case_e_capture(NATIVE_E_DOC, CASES["E"], NATIVE_E_EXPORT_DOC))
        self.assertEqual(
            [],
            validate_phase11_e_reconciliation(
                BASELINE_DOC, CASES_DOC, NATIVE_E_DOC, NATIVE_E_EXPORT_DOC
            ),
        )
        self.assertEqual("NATIVE_EXECUTED_ROUTING_FAIL", NATIVE_E_DOC["CASE_RESULT"])
        self.assertEqual(["kael", "talos"], NATIVE_E_DOC["EXPECTED_ROUTE"])
        self.assertEqual(["kael"], NATIVE_E_DOC["ACTUAL_ROUTE"])
        self.assertEqual([], NATIVE_E_DOC["CHILD_SESSIONS"])
        self.assertEqual(0, NATIVE_E_DOC["CONSULTATION_COUNTS"]["talos"])
        self.assertEqual(0, NATIVE_E_DOC["CONSULTATION_COUNTS"]["argus"])
        self.assertEqual("PASS", NATIVE_E_DOC["CLASSIFICATIONS"]["CASE_E_NEGATIVE_ARGUS_CONTROL"])
        self.assertEqual("FAIL", NATIVE_E_DOC["CLASSIFICATIONS"]["CASE_E_TALOS_ACTIVATION"])
        self.assertEqual("FAIL", NATIVE_E_DOC["CASE_ACCEPTANCE"])
        self.assertEqual(CASE_E_CLASSIFICATIONS, NATIVE_E_DOC["CLASSIFICATIONS"])
        self.assertEqual(1, NATIVE_E_EXPORT_DOC["projection_and_redaction"]["reasoning_blocks_removed"])
        self.assertFalse(NATIVE_E_EXPORT_DOC["projection_and_redaction"]["raw_export_persisted"])
        self.assertIn("PHASE11_CASE_E_FRESH_ROOT", NATIVE_E_EXPORT_DOC["messages"][0]["text"])
        self.assertNotIn("[redacted:text:", NATIVE_E_EXPORT_DOC["messages"][0]["text"])
        self.assertNotIn("reasoning", [part["type"] for part in NATIVE_E_EXPORT_DOC["messages"][1]["content"]])
        self.assertEqual("PARTIAL", BASELINE_DOC["live_qualification"]["overall_status"])
        self.assertEqual(
            [
                "HUMAN_ACTION_REQUIRED PHASE11_CASE_E_FRESH_ROOT",
                "HUMAN_ACTION_REQUIRED PHASE11_CASE_F_FRESH_ROOT",
                "HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT",
                "HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT",
                "HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT",
            ],
            BASELINE_DOC["phase11_e_reconciliation"]["pending_fresh_root_labels"],
        )
        self.assertEqual(
            ["HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT"],
            BASELINE_DOC["live_qualification"]["pending_labels"],
        )
        self.assertEqual("NOT_EXERCISED", BASELINE_DOC["argus_same_session_followup_runtime_coverage"]["status"])
        self.assertEqual("PASS", BASELINE_DOC["phase11_b3_reconciliation"]["acceptance_status"])
        self.assertEqual("PASS", BASELINE_DOC["phase11_c_reconciliation"]["acceptance_status"])
        self.assertEqual("PASS", BASELINE_DOC["phase11_d_reconciliation"]["acceptance_status"])

    def test_case_e_failure_cannot_be_promoted_and_missing_record_is_rejected(self) -> None:
        promoted = copy.deepcopy(BASELINE_DOC)
        promoted["phase11_e_reconciliation"]["acceptance_status"] = "PASS"
        promoted["phase11_e_reconciliation"]["case_result"] = "PASS"
        self.assertIn(
            "CASE_E_ROUTING_FAILURE_PROMOTED_OR_REPLAYED",
            validate_phase11_e_reconciliation(promoted, CASES_DOC, NATIVE_E_DOC, NATIVE_E_EXPORT_DOC),
        )

        promoted_matrix = copy.deepcopy(CASES_DOC)
        action = next(row for row in promoted_matrix["fresh_root_actions"] if row["case_id"] == "E")
        action["status"] = "PASS"
        action["acceptance_status"] = "PASS"
        self.assertIn(
            "CASE_E_MATRIX_FAILURE_OR_EVIDENCE_LINK_MISMATCH",
            validate_phase11_e_reconciliation(BASELINE_DOC, promoted_matrix, NATIVE_E_DOC, NATIVE_E_EXPORT_DOC),
        )

        missing_report = copy.deepcopy(BASELINE_DOC)
        missing_report.pop("phase11_e_reconciliation")
        self.assertIn(
            "CASE_E_RECONCILIATION_MISSING",
            validate_phase11_e_reconciliation(missing_report, CASES_DOC, NATIVE_E_DOC, NATIVE_E_EXPORT_DOC),
        )

    def test_case_e_rejects_fabricated_talos_activation_and_route(self) -> None:
        fabricated = copy.deepcopy(NATIVE_E_DOC)
        fabricated["CHILD_SESSIONS"] = [{"AGENT": "talos", "NATIVE_SESSION_ID": "ses_forgedtalos"}]
        fabricated["ACTUAL_ROUTE"] = ["kael", "talos"]
        fabricated["CONSULTATION_COUNTS"]["talos"] = 1
        fabricated["UNIQUE_CHILD_SESSION_COUNTS"]["talos"] = 1
        fabricated["API_EVIDENCE"]["DIRECT_CHILD_QUERY"]["CHILD_COUNT"] = 1
        errors = validate_native_case_e_capture(fabricated, CASES["E"], NATIVE_E_EXPORT_DOC)
        self.assertIn("NATIVE_E_CHILD_SESSION_SET_MISMATCH", errors)
        self.assertIn("NATIVE_E_SPECIALIST_COUNTS_MISMATCH", errors)
        self.assertIn("NATIVE_E_UNIQUE_CHILD_COUNTS_MISMATCH", errors)
        self.assertIn("NATIVE_E_FABRICATED_TALOS_ACTIVATION", errors)
        self.assertIn("NATIVE_E_ACTUAL_ROUTE_OR_FABRICATED_CHILD_MISMATCH", errors)

    def test_case_e1_history_label_is_retained_but_not_current_pending(self) -> None:
        stale_current = copy.deepcopy(BASELINE_DOC)
        stale_current["live_qualification"]["pending_labels"].insert(
            0, "HUMAN_ACTION_REQUIRED PHASE11_CASE_E_FRESH_ROOT"
        )
        self.assertIn(
            "CURRENT_PHASE11_PENDING_STATE_MISMATCH",
            validate_phase11_e_reconciliation(stale_current, CASES_DOC, NATIVE_E_DOC, NATIVE_E_EXPORT_DOC),
        )

        weakened = copy.deepcopy(CASES_DOC)
        case_e = next(case for case in weakened["cases"] if case["id"] == "E")
        case_e["expected_routes"]["default"] = ["kael"]
        errors = validate_phase11_e_reconciliation(BASELINE_DOC, weakened, NATIVE_E_DOC, NATIVE_E_EXPORT_DOC)
        self.assertIn("NATIVE_E_TALOS_EXPECTATION_WEAKENED", errors)

    def test_case_e_rejects_core_change_or_internal_rationale_overclaim(self) -> None:
        fixed = copy.deepcopy(NATIVE_E_DOC)
        fixed["CORE_POLICY_MODIFIED"] = True
        self.assertIn(
            "NATIVE_E_FAILURE_PROMOTED_OR_PROHIBITED_ACTION_CLAIMED",
            validate_native_case_e_capture(fixed, CASES["E"], NATIVE_E_EXPORT_DOC),
        )

        overclaimed = copy.deepcopy(BASELINE_DOC)
        overclaimed["phase11_e_reconciliation"]["route_cause"]["internal_model_rationale_claimed"] = True
        self.assertIn(
            "CASE_E_ROOT_CAUSE_BOUNDS_OR_CITATIONS_MISMATCH",
            validate_phase11_e_reconciliation(overclaimed, CASES_DOC, NATIVE_E_DOC, NATIVE_E_EXPORT_DOC),
        )

        shipped = copy.deepcopy(BASELINE_DOC)
        shipped["live_qualification"]["overall_status"] = "SHIPPED"
        self.assertIn(
            "CURRENT_PHASE11_PENDING_STATE_MISMATCH",
            validate_phase11_e_reconciliation(shipped, CASES_DOC, NATIVE_E_DOC, NATIVE_E_EXPORT_DOC),
        )


class NativeCaseE2MutationTests(unittest.TestCase):
    def test_case_e2_reconciles_the_native_talos_route_and_keeps_e1_history(self) -> None:
        self.assertEqual(
            [],
            validate_native_case_e2_capture(
                NATIVE_E2_DOC, CASES["E"], NATIVE_E2_ROOT_EXPORT_DOC, NATIVE_E2_CHILD_EXPORT_DOC
            ),
        )
        self.assertEqual(
            [],
            validate_phase11_e2_reconciliation(
                BASELINE_DOC,
                CASES_DOC,
                NATIVE_E2_DOC,
                NATIVE_E2_ROOT_EXPORT_DOC,
                NATIVE_E2_CHILD_EXPORT_DOC,
            ),
        )
        self.assertEqual(["kael", "talos"], NATIVE_E2_DOC["ACTUAL_ROUTE"])
        self.assertEqual("NATIVE_EXECUTED_ROUTING_PASS", NATIVE_E2_DOC["CASE_RESULT"])
        self.assertEqual("FAIL", NATIVE_E_DOC["CASE_ACCEPTANCE"])
        self.assertEqual("NATIVE_EXECUTED_ROUTING_FAIL", NATIVE_E_DOC["CASE_RESULT"])
        self.assertEqual(2, NATIVE_E2_ROOT_EXPORT_DOC["projection_and_redaction"]["reasoning_blocks_removed"])
        self.assertEqual(0, NATIVE_E2_CHILD_EXPORT_DOC["projection_and_redaction"]["reasoning_blocks_removed"])
        self.assertFalse(NATIVE_E2_ROOT_EXPORT_DOC["projection_and_redaction"]["raw_export_persisted"])
        self.assertFalse(NATIVE_E2_CHILD_EXPORT_DOC["projection_and_redaction"]["raw_export_persisted"])
        self.assertEqual("PARTIAL", BASELINE_DOC["live_qualification"]["overall_status"])
        self.assertEqual(
            ["HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT"],
            BASELINE_DOC["live_qualification"]["pending_labels"],
        )
        self.assertEqual(
            "NOT_EXERCISED",
            BASELINE_DOC["argus_same_session_followup_runtime_coverage"]["status"],
        )

    def test_case_e2_rejects_child_parent_and_route_mutations(self) -> None:
        wrong_child = copy.deepcopy(NATIVE_E2_DOC)
        wrong_child["CHILD_SESSIONS"][0]["NATIVE_SESSION_ID"] = "ses_forgedtalos"
        self.assertIn(
            "NATIVE_E2_CHILD_SESSION_PARENT_ROLE_OR_RESULT_JOIN_MISMATCH",
            validate_native_case_e2_capture(
                wrong_child, CASES["E"], NATIVE_E2_ROOT_EXPORT_DOC, NATIVE_E2_CHILD_EXPORT_DOC
            ),
        )

        wrong_parent = copy.deepcopy(NATIVE_E2_DOC)
        wrong_parent["CHILD_SESSIONS"][0]["PARENT_SESSION_ID"] = "ses_wrongparent"
        self.assertIn(
            "NATIVE_E2_CHILD_SESSION_PARENT_ROLE_OR_RESULT_JOIN_MISMATCH",
            validate_native_case_e2_capture(
                wrong_parent, CASES["E"], NATIVE_E2_ROOT_EXPORT_DOC, NATIVE_E2_CHILD_EXPORT_DOC
            ),
        )

        wrong_export_parent = copy.deepcopy(NATIVE_E2_CHILD_EXPORT_DOC)
        wrong_export_parent["session"]["parent_id"] = "ses_wrongparent"
        self.assertIn(
            "NATIVE_E2_CHILD_EXPORT_PARENT_OR_METADATA_MISMATCH",
            validate_native_case_e2_capture(
                NATIVE_E2_DOC, CASES["E"], NATIVE_E2_ROOT_EXPORT_DOC, wrong_export_parent
            ),
        )

        wrong_route = copy.deepcopy(NATIVE_E2_DOC)
        wrong_route["ACTUAL_ROUTE"] = ["kael"]
        self.assertIn(
            "NATIVE_E2_ROUTE_OR_EXPECTATION_MISMATCH",
            validate_native_case_e2_capture(
                wrong_route, CASES["E"], NATIVE_E2_ROOT_EXPORT_DOC, NATIVE_E2_CHILD_EXPORT_DOC
            ),
        )

    def test_case_e2_rejects_fabricated_results_and_e1_history_promotion(self) -> None:
        fabricated_result = copy.deepcopy(NATIVE_E2_DOC)
        fabricated_result["CHILD_SESSIONS"][0]["RESULT_ID"] = "result-invented"
        self.assertIn(
            "NATIVE_E2_CHILD_SESSION_PARENT_ROLE_OR_RESULT_JOIN_MISMATCH",
            validate_native_case_e2_capture(
                fabricated_result, CASES["E"], NATIVE_E2_ROOT_EXPORT_DOC, NATIVE_E2_CHILD_EXPORT_DOC
            ),
        )

        overclaimed_consumption = copy.deepcopy(NATIVE_E2_DOC)
        overclaimed_consumption["RESULT_CONSUMPTION"]["RESULT_IDS"] = ["result-invented"]
        self.assertIn(
            "NATIVE_E2_RESULT_CONSUMPTION_RECONCILIATION_MISMATCH",
            validate_native_case_e2_capture(
                overclaimed_consumption, CASES["E"], NATIVE_E2_ROOT_EXPORT_DOC, NATIVE_E2_CHILD_EXPORT_DOC
            ),
        )

        promoted_e1 = copy.deepcopy(NATIVE_E2_DOC)
        promoted_e1["E1_HISTORICAL_ATTEMPT"]["ACCEPTANCE_STATUS"] = "PASS"
        self.assertIn(
            "NATIVE_E2_E1_FAILED_HISTORY_REWRITTEN_OR_MISJOINED",
            validate_native_case_e2_capture(
                promoted_e1, CASES["E"], NATIVE_E2_ROOT_EXPORT_DOC, NATIVE_E2_CHILD_EXPORT_DOC
            ),
        )

    def test_case_e2_reconciliation_cannot_promote_e1_or_ship_phase11(self) -> None:
        promoted_e1 = copy.deepcopy(BASELINE_DOC)
        promoted_e1["phase11_e_reconciliation"]["acceptance_status"] = "PASS"
        self.assertIn(
            "CASE_E2_E1_FAILED_HISTORICAL_ATTEMPT_NOT_PRESERVED",
            validate_phase11_e2_reconciliation(
                promoted_e1,
                CASES_DOC,
                NATIVE_E2_DOC,
                NATIVE_E2_ROOT_EXPORT_DOC,
                NATIVE_E2_CHILD_EXPORT_DOC,
            ),
        )

        shipped = copy.deepcopy(BASELINE_DOC)
        shipped["live_qualification"]["overall_status"] = "SHIPPED"
        self.assertIn(
            "CURRENT_PHASE11_E2_PENDING_STATE_MISMATCH",
            validate_phase11_e2_reconciliation(
                shipped,
                CASES_DOC,
                NATIVE_E2_DOC,
                NATIVE_E2_ROOT_EXPORT_DOC,
                NATIVE_E2_CHILD_EXPORT_DOC,
            ),
        )


class NativeCaseFMutationTests(unittest.TestCase):
    def test_case_f_native_capture_accepts_the_complete_observed_kael_only_route(self) -> None:
        self.assertEqual(CASE_F_ROOT_SESSION_ID, NATIVE_F_DOC["EVIDENCE_PROVENANCE"]["NATIVE_ROOT_SESSION_ID"])
        self.assertEqual([], NATIVE_F_DOC["CHILD_SESSIONS"])
        self.assertEqual(["kael"], CASE_F_EXPECTED_ROUTE)
        self.assertEqual(CASE_F_CLASSIFICATIONS, NATIVE_F_DOC["CLASSIFICATIONS"])
        self.assertEqual([], validate_native_case_f_capture(NATIVE_F_DOC, CASES["F"], NATIVE_F_EXPORT_DOC))
        self.assertEqual(
            [],
            validate_phase11_f_reconciliation(BASELINE_DOC, CASES_DOC, NATIVE_F_DOC, NATIVE_F_EXPORT_DOC),
        )
        self.assertEqual(0, NATIVE_F_DOC["API_EVIDENCE"]["DIRECT_CHILD_QUERY"]["CHILD_COUNT"])
        self.assertEqual(0, NATIVE_F_DOC["API_EVIDENCE"]["ROOT_TOOL_CALL_RECORD_COUNT"])
        self.assertEqual(0, NATIVE_F_DOC["API_EVIDENCE"]["NESTED_TOOL_WRAPPER_COUNT"])
        self.assertEqual(0, NATIVE_F_DOC["CONSULTATION_COUNTS"]["argus"])
        self.assertEqual(0, NATIVE_F_DOC["CONSULTATION_COUNTS"]["talos"])
        self.assertIsNone(NATIVE_F_DOC["MAX_SIMULTANEOUS_CHILDREN"])
        self.assertEqual([], NATIVE_F_DOC["DEPENDENCY_ORDER"])
        self.assertEqual("NOT_ASSESSED_BY_NOX", NATIVE_F_EXPORT_DOC["projection_and_redaction"]["secret_filtering"])
        self.assertFalse(NATIVE_F_EXPORT_DOC["projection_and_redaction"]["raw_export_persisted"])
        self.assertNotIn(
            CASE_F_COLLECTOR_SESSION_ID,
            [child.get("NATIVE_SESSION_ID") for child in NATIVE_F_DOC["CHILD_SESSIONS"]],
        )
        self.assertNotIn("EVENTS", NATIVE_F_DOC)
        self.assertEqual("PARTIAL", BASELINE_DOC["live_qualification"]["overall_status"])
        self.assertEqual(
            ["HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT"],
            BASELINE_DOC["live_qualification"]["pending_labels"],
        )
        self.assertEqual("FAIL", BASELINE_DOC["phase11_e_reconciliation"]["acceptance_status"])
        self.assertEqual("PASS", BASELINE_DOC["phase11_e2_reconciliation"]["acceptance_status"])
        self.assertEqual("NOT_EXERCISED", BASELINE_DOC["argus_same_session_followup_runtime_coverage"]["status"])

    def test_case_f_rejects_root_route_child_and_specialist_count_drift(self) -> None:
        wrong_root = copy.deepcopy(NATIVE_F_DOC)
        wrong_root["ROOT_SESSION_ID"] = "ses_forgedroot"
        self.assertIn(
            "NATIVE_F_ROOT_IDENTITY_OR_UNVERIFIED_HEAD_MISMATCH",
            validate_native_case_f_capture(wrong_root, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        wrong_provenance = copy.deepcopy(NATIVE_F_DOC)
        wrong_provenance["EVIDENCE_PROVENANCE"]["NATIVE_ROOT_SESSION_ID"] = "ses_forgedroot"
        self.assertIn(
            "NATIVE_F_ROOT_OR_CAPTURE_PROVENANCE_MISMATCH",
            validate_native_case_f_capture(wrong_provenance, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        wrong_route = copy.deepcopy(NATIVE_F_DOC)
        wrong_route["ACTUAL_ROUTE"] = ["kael", "argus"]
        self.assertIn(
            "NATIVE_F_ROUTE_OR_OPERATIONAL_RESULT_FIDELITY_MISMATCH",
            validate_native_case_f_capture(wrong_route, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        fabricated_child = copy.deepcopy(NATIVE_F_DOC)
        fabricated_child["CHILD_SESSIONS"] = [{"AGENT": "talos", "NATIVE_SESSION_ID": "ses_forgedtalos"}]
        self.assertIn(
            "NATIVE_F_CHILD_COUNTS_OR_UNKNOWN_CONCURRENCY_MISMATCH",
            validate_native_case_f_capture(fabricated_child, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        fabricated_call = copy.deepcopy(NATIVE_F_DOC)
        fabricated_call["API_EVIDENCE"]["ROOT_TOOL_CALL_RECORD_COUNT"] = 1
        self.assertIn(
            "NATIVE_F_API_CHILD_TOOL_OR_EXPORT_OBSERVATION_MISMATCH",
            validate_native_case_f_capture(fabricated_call, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        activated_argus = copy.deepcopy(NATIVE_F_DOC)
        activated_argus["CONSULTATION_COUNTS"]["argus"] = 1
        self.assertIn(
            "NATIVE_F_CHILD_COUNTS_OR_UNKNOWN_CONCURRENCY_MISMATCH",
            validate_native_case_f_capture(activated_argus, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

    def test_case_f_rejects_operational_product_security_install_file_and_completion_drift(self) -> None:
        invented_product_bug = copy.deepcopy(NATIVE_F_DOC)
        invented_product_bug["OPERATIONAL_FINDING"]["PRODUCT_BUG_ESTABLISHED"] = True
        self.assertIn(
            "NATIVE_F_OPERATIONAL_CLASSIFICATION_OR_PRODUCT_SECURITY_CLAIMS_MISMATCH",
            validate_native_case_f_capture(invented_product_bug, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        invented_security_bug = copy.deepcopy(NATIVE_F_DOC)
        invented_security_bug["OBSERVED_TERMINAL_SNAPSHOT"]["FACTS"]["SECURITY_BUG_ESTABLISHED"] = "YES"
        self.assertIn(
            "NATIVE_F_TERMINAL_OPERATIONAL_PRODUCT_SECURITY_OR_COMPLETION_FACTS_MISMATCH",
            validate_native_case_f_capture(invented_security_bug, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        wrong_classification = copy.deepcopy(NATIVE_F_DOC)
        wrong_classification["OPERATIONAL_FINDING"]["CLASSIFICATION"] = "PRODUCT_BUG"
        self.assertIn(
            "NATIVE_F_OPERATIONAL_CLASSIFICATION_OR_PRODUCT_SECURITY_CLAIMS_MISMATCH",
            validate_native_case_f_capture(wrong_classification, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        install_claim = copy.deepcopy(NATIVE_F_DOC)
        install_claim["INSTALL_ATTEMPTED"] = "YES"
        self.assertIn(
            "NATIVE_F_INSTALL_FILE_CHANGE_OR_REPLAY_CLAIM_MISMATCH",
            validate_native_case_f_capture(install_claim, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        file_claim = copy.deepcopy(NATIVE_F_DOC)
        file_claim["FILES_CHANGED"] = ["README.md"]
        self.assertIn(
            "NATIVE_F_INSTALL_FILE_CHANGE_OR_REPLAY_CLAIM_MISMATCH",
            validate_native_case_f_capture(file_claim, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        false_completion = copy.deepcopy(NATIVE_F_DOC)
        false_completion["COMPLETION_GATE"]["PENDING_CHILD_COUNT"] = 1
        self.assertIn(
            "NATIVE_F_COMPLETION_OR_TERMINAL_OUTCOME_MISMATCH",
            validate_native_case_f_capture(false_completion, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

        fabricated_timing = copy.deepcopy(NATIVE_F_DOC)
        fabricated_timing["UNKNOWN_METRICS"]["WALL_CLOCK_MS"] = 222
        self.assertIn(
            "NATIVE_F_UNKNOWN_METRIC_OR_PERMISSION_OBSERVABILITY_OVERCLAIM",
            validate_native_case_f_capture(fabricated_timing, CASES["F"], NATIVE_F_EXPORT_DOC),
        )

    def test_case_f_rejects_terminal_export_drift_and_current_status_promotion(self) -> None:
        changed_terminal = copy.deepcopy(NATIVE_F_EXPORT_DOC)
        text = changed_terminal["messages"][1]["content"][0]["text"]
        changed_terminal["messages"][1]["content"][0]["text"] = text.replace(
            "PRODUCT_BUG_ESTABLISHED:\nNO", "PRODUCT_BUG_ESTABLISHED:\nYES"
        )
        self.assertIn(
            "NATIVE_F_EXPORT_TERMINAL_OPERATIONAL_PRODUCT_SECURITY_OR_COMPLETION_FACTS_MISMATCH",
            validate_native_case_f_capture(NATIVE_F_DOC, CASES["F"], changed_terminal),
        )

        appended_contradictions = (
            "PRODUCT_BUG_ESTABLISHED:\nYES",
            "SECURITY_BUG_ESTABLISHED:\nYES",
            "INSTALL_ATTEMPTED:\nYES",
            "FILES_CHANGED:\nREADME.md",
            "UNRESOLVED_WORK:\ncase remains open",
            "REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED:\nNO",
            "ANY_WORK_REMAINING:\nYES",
        )
        for contradiction in appended_contradictions:
            with self.subTest(contradiction=contradiction):
                appended_claim = copy.deepcopy(NATIVE_F_EXPORT_DOC)
                original_text = appended_claim["messages"][1]["content"][0]["text"]
                appended_claim["messages"][1]["content"][0]["text"] = (
                    original_text + "\n\n" + contradiction
                )
                self.assertIn(
                    "NATIVE_F_EXPORT_TERMINAL_OPERATIONAL_PRODUCT_SECURITY_OR_COMPLETION_FACTS_MISMATCH",
                    validate_native_case_f_capture(NATIVE_F_DOC, CASES["F"], appended_claim),
                )

        added_reasoning = copy.deepcopy(NATIVE_F_EXPORT_DOC)
        added_reasoning["messages"][1]["content"].append({"type": "reasoning", "text": "omitted"})
        self.assertIn(
            "NATIVE_F_EXPORT_PROJECTION_TOOL_OR_SECRET_FILTER_CLAIM_MISMATCH",
            validate_native_case_f_capture(NATIVE_F_DOC, CASES["F"], added_reasoning),
        )

        stale_pending = copy.deepcopy(BASELINE_DOC)
        stale_pending["live_qualification"]["pending_labels"].insert(
            0, "HUMAN_ACTION_REQUIRED PHASE11_CASE_F_FRESH_ROOT"
        )
        self.assertIn(
            "CURRENT_PHASE11_F_PENDING_STATE_MISMATCH",
            validate_phase11_f_reconciliation(stale_pending, CASES_DOC, NATIVE_F_DOC, NATIVE_F_EXPORT_DOC),
        )

        shipped = copy.deepcopy(BASELINE_DOC)
        shipped["live_qualification"]["overall_status"] = "SHIPPED"
        self.assertIn(
            "CURRENT_PHASE11_F_PENDING_STATE_MISMATCH",
            validate_phase11_f_reconciliation(shipped, CASES_DOC, NATIVE_F_DOC, NATIVE_F_EXPORT_DOC),
        )

        rewritten_e1 = copy.deepcopy(BASELINE_DOC)
        rewritten_e1["phase11_e_reconciliation"]["acceptance_status"] = "PASS"
        self.assertIn(
            "CASE_F_E1_FAILED_HISTORY_OR_E2_ACCEPTANCE_REWRITTEN",
            validate_phase11_f_reconciliation(rewritten_e1, CASES_DOC, NATIVE_F_DOC, NATIVE_F_EXPORT_DOC),
        )


class NativeCaseGMutationTests(unittest.TestCase):
    def test_case_g_reconciles_native_route_and_conditional_followup_without_runtime_claims(self) -> None:
        self.assertEqual(CASE_G_ROOT_SESSION_ID, NATIVE_G_DOC["ROOT_SESSION_ID"])
        self.assertEqual(CASE_G_EXPECTED_ROUTE, ["kael", "veyra", "thales"])
        self.assertEqual(CASE_G_EXPECTED_ROUTE, NATIVE_G_DOC["ACTUAL_ROUTE"])
        self.assertEqual(
            [CASE_G_VEYRA_SESSION_ID, CASE_G_THALES_SESSION_ID],
            [child["NATIVE_SESSION_ID"] for child in NATIVE_G_DOC["CHILD_SESSIONS"]],
        )
        self.assertEqual(0, NATIVE_G_DOC["CONSULTATION_COUNTS"]["nox"])
        self.assertEqual(1, NATIVE_G_DOC["CONSULTATION_COUNTS"]["thales"])
        self.assertTrue(all(call["EXECUTED"] is False for call in NATIVE_G_DOC["API_EVIDENCE"]["ROOT_TOOL_CALL_RECORDS"]))
        self.assertTrue(all(call["TOOL_STATE"] == "completed" for call in NATIVE_G_DOC["API_EVIDENCE"]["ROOT_TOOL_CALL_RECORDS"]))
        self.assertIn("do not interpret it as proof of non-execution", NATIVE_G_DOC["API_EVIDENCE"]["TOOL_EXECUTED_FLAG_CAVEAT"])
        self.assertEqual("NOT_REQUIRED", NATIVE_G_DOC["THALES_FOLLOWUP"]["FOLLOWUP_STATUS"])
        self.assertEqual("NOT_EXERCISED", NATIVE_G_DOC["THALES_FOLLOWUP"]["SAME_SESSION_FOLLOWUP_RUNTIME_COVERAGE"])
        self.assertFalse(NATIVE_G_DOC["RESULT_FIDELITY"]["RUNTIME_FLAKINESS_REPRODUCED"])
        self.assertEqual("UNCONFIRMED", NATIVE_G_DOC["RESULT_FIDELITY"]["SUPPORTED_CAUSE"])
        self.assertEqual("PASS", NATIVE_G_DOC["CASE_ACCEPTANCE"])
        self.assertEqual(CASE_G_CLASSIFICATIONS, NATIVE_G_DOC["CLASSIFICATIONS"])
        self.assertEqual(
            [],
            validate_native_case_g_capture(
                NATIVE_G_DOC,
                CASES["G"],
                NATIVE_G_ROOT_EXPORT_DOC,
                NATIVE_G_VEYRA_EXPORT_DOC,
                NATIVE_G_THALES_EXPORT_DOC,
            ),
        )
        self.assertEqual(
            [],
            validate_phase11_g_reconciliation(
                BASELINE_DOC,
                CASES_DOC,
                NATIVE_G_DOC,
                NATIVE_G_ROOT_EXPORT_DOC,
                NATIVE_G_VEYRA_EXPORT_DOC,
                NATIVE_G_THALES_EXPORT_DOC,
            ),
        )
        self.assertEqual(
            ["HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT"],
            BASELINE_DOC["live_qualification"]["pending_labels"],
        )
        for prior in ("phase11_b3_reconciliation", "phase11_c_reconciliation", "phase11_d_reconciliation", "phase11_e_reconciliation", "phase11_e2_reconciliation", "phase11_f_reconciliation"):
            self.assertIn("HUMAN_ACTION_REQUIRED PHASE11_CASE_G_FRESH_ROOT", BASELINE_DOC[prior]["pending_fresh_root_labels"])

        missing_change_log = copy.deepcopy(BASELINE_DOC)
        missing_change_log["phase11_g_reconciliation"]["reconciliation_files_changed"] = []
        self.assertIn(
            "CASE_G_BASELINE_RECONCILIATION_MISMATCH:reconciliation_files_changed",
            validate_phase11_g_reconciliation(
                missing_change_log, CASES_DOC, NATIVE_G_DOC, NATIVE_G_ROOT_EXPORT_DOC,
                NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC,
            ),
        )

    def test_case_g_synthetic_iterative_example_is_preserved_and_still_validated(self) -> None:
        synthetic = TRACES["G"]
        self.assertEqual(["kael", "nox", "thales", "veyra"], synthetic["ACTUAL_ROUTE"])
        self.assertEqual(2, synthetic["CONSULTATION_COUNTS"]["thales"])
        self.assertEqual(2, len([event for event in synthetic["EVENTS"] if event.get("KIND") == "CONSULT" and event.get("ACTOR_ROLE") == "thales"]))
        self.assertEqual([], validate_trace(synthetic, CASES["G"]))
        self.assertNotIn("mandatory_dependency_edges", CASES["G"])
        self.assertEqual(2, len(CASES["G"]["synthetic_illustrative_dependency_edges"]))
        self.assertEqual(["kael", "nox", "thales", "veyra"], CASES["G"]["expected_routes"]["default"])

    def test_case_g_rejects_invented_cause_reruns_or_changed_terminal_join(self) -> None:
        invented_cause = copy.deepcopy(NATIVE_G_DOC)
        invented_cause["RESULT_FIDELITY"]["SUPPORTED_CAUSE"] = "NETWORK_TIMEOUT"
        self.assertIn(
            "NATIVE_G_CHILD_DIAGNOSTIC_OR_ROOT_TERMINAL_CAUSE_FIDELITY_MISMATCH",
            validate_native_case_g_capture(
                invented_cause, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

        rerun_claim = copy.deepcopy(NATIVE_G_ROOT_EXPORT_DOC)
        terminal = next(item for item in rerun_claim["messages"] if item["id"] == NATIVE_G_DOC["ROOT_TERMINAL_MESSAGE_ID"])
        terminal["content"][0]["text"] = terminal["content"][0]["text"].replace("RANDOM_RERUNS: 0", "RANDOM_RERUNS: 3")
        terminal["text"] = terminal["content"][0]["text"]
        errors = validate_native_case_g_capture(
            NATIVE_G_DOC, CASES["G"], rerun_claim, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
        )
        self.assertIn("NATIVE_G_CHILD_DIAGNOSTIC_OR_ROOT_TERMINAL_CAUSE_FIDELITY_MISMATCH", errors)

        wrong_terminal_id = copy.deepcopy(NATIVE_G_DOC)
        wrong_terminal_id["CHILD_SESSIONS"][1]["TERMINAL_MESSAGE_ID"] = "msg_fabricated"
        self.assertIn(
            "NATIVE_G_CHILD_PARENT_ROLE_OUTCOME_OR_ROUTE_JOIN_MISMATCH",
            validate_native_case_g_capture(
                wrong_terminal_id, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

        wrong_parent = copy.deepcopy(NATIVE_G_VEYRA_EXPORT_DOC)
        wrong_parent["session"]["parent_id"] = "ses_fabricated_parent"
        self.assertIn(
            "NATIVE_G_CHILD_EXPORT_METADATA_OR_MESSAGE_JOIN_MISMATCH",
            validate_native_case_g_capture(
                NATIVE_G_DOC, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, wrong_parent, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

    def test_case_g_rejects_missing_gate_and_wrong_measurement_or_source_ownership(self) -> None:
        missing_gate = copy.deepcopy(NATIVE_G_ROOT_EXPORT_DOC)
        user = next(item for item in missing_gate["messages"] if item["type"] == "user")
        user["text"] = user["text"].replace("STAGE 1:", "STAGE ONE:")
        self.assertIn(
            "NATIVE_G_ORIGINAL_PROMPT_SCOPE_OR_NO_RERUN_GATE_MISMATCH",
            validate_native_case_g_capture(
                NATIVE_G_DOC, CASES["G"], missing_gate, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

        wrong_source_owner = copy.deepcopy(NATIVE_G_DOC)
        wrong_source_owner["EVIDENCE_OWNERSHIP"]["SOURCE_EVIDENCE_ROLE"] = "nox"
        self.assertIn(
            "NATIVE_G_EVIDENCE_ROLE_OWNERSHIP_OR_ROLE_PURITY_MISMATCH",
            validate_native_case_g_capture(
                wrong_source_owner, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

        fabricated_measurement = copy.deepcopy(NATIVE_G_DOC)
        fabricated_measurement["EVIDENCE_OWNERSHIP"]["ACTUAL_MEASUREMENT_PERFORMED"] = True
        fabricated_measurement["CONSULTATION_COUNTS"]["nox"] = 1
        self.assertIn(
            "NATIVE_G_EVIDENCE_ROLE_OWNERSHIP_OR_ROLE_PURITY_MISMATCH",
            validate_native_case_g_capture(
                fabricated_measurement, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

        altered_child_prompt = copy.deepcopy(NATIVE_G_VEYRA_EXPORT_DOC)
        child_prompt = next(item for item in altered_child_prompt["messages"] if item["type"] == "user")
        child_prompt["text"] = child_prompt["text"].replace("ordered result sequence", "exact ordered outcomes")
        self.assertIn(
            "NATIVE_G_USER_PROMPT_PROJECTION_HASH_MISMATCH",
            validate_native_case_g_capture(
                NATIVE_G_DOC, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, altered_child_prompt, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

    def test_case_g_rejects_followup_claims_not_supported_by_current_terminal(self) -> None:
        required = copy.deepcopy(NATIVE_G_DOC)
        required["THALES_FOLLOWUP"]["MATERIALLY_NEW_EVIDENCE_NEEDED"] = True
        errors = validate_native_case_g_capture(
            required, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
        )
        self.assertIn("NATIVE_G_THALES_FOLLOWUP_CLAIMS_NOT_SUPPORTED_BY_OBSERVED_EXPORT", errors)

        requested = copy.deepcopy(NATIVE_G_DOC)
        requested["THALES_FOLLOWUP"]["EVIDENCE_REQUEST_MADE"] = True
        errors = validate_native_case_g_capture(
            requested, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
        )
        self.assertIn("NATIVE_G_THALES_FOLLOWUP_CLAIMS_NOT_SUPPORTED_BY_OBSERVED_EXPORT", errors)

        forged_followup = copy.deepcopy(NATIVE_G_DOC)
        forged_followup["THALES_FOLLOWUP"].update(
            {
                "CONSULTATION_COUNT": 2,
                "EVIDENCE_REQUEST_MADE": True,
                "MATERIALLY_NEW_EVIDENCE_NEEDED": True,
                "FOLLOWUP_STATUS": "SAME_SESSION_FOLLOWUP_REQUIRED",
                "FOLLOWUP_CONSULTATION_COUNT": 1,
                "FOLLOWUP_SESSION_ID": CASE_G_THALES_SESSION_ID,
            }
        )
        self.assertIn(
            "NATIVE_G_THALES_FOLLOWUP_CLAIMS_NOT_SUPPORTED_BY_OBSERVED_EXPORT",
            validate_native_case_g_capture(
                forged_followup, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

        missing_observed_basis = copy.deepcopy(NATIVE_G_THALES_EXPORT_DOC)
        terminal = next(item for item in missing_observed_basis["messages"] if item["type"] == "assistant")
        terminal["text"] = terminal["text"].replace("not materially necessary", "required")
        terminal["content"][0]["text"] = terminal["content"][0]["text"].replace("not materially necessary", "required")
        self.assertIn(
            "NATIVE_G_THALES_FOLLOWUP_CLAIMS_NOT_SUPPORTED_BY_OBSERVED_EXPORT",
            validate_native_case_g_capture(
                NATIVE_G_DOC, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, NATIVE_G_VEYRA_EXPORT_DOC, missing_observed_basis
            ),
        )

    def test_case_g_rejects_fabricated_result_ids_or_route_reordering(self) -> None:
        fabricated_result = copy.deepcopy(NATIVE_G_ROOT_EXPORT_DOC)
        fabricated_result["tool_call_records"][0]["result_id"] = "result-fabricated"
        self.assertIn(
            "NATIVE_G_ROOT_TOOL_CALL_ORDER_OR_RESULT_ID_MISMATCH",
            validate_native_case_g_capture(
                NATIVE_G_DOC, CASES["G"], fabricated_result, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

        reversed_calls = copy.deepcopy(NATIVE_G_ROOT_EXPORT_DOC)
        reversed_calls["tool_call_records"].reverse()
        self.assertIn(
            "NATIVE_G_ROOT_TOOL_CALL_ORDER_OR_RESULT_ID_MISMATCH",
            validate_native_case_g_capture(
                NATIVE_G_DOC, CASES["G"], reversed_calls, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

        invented_time = copy.deepcopy(NATIVE_G_ROOT_EXPORT_DOC)
        terminal = next(item for item in invented_time["messages"] if item["id"] == NATIVE_G_DOC["ROOT_TERMINAL_MESSAGE_ID"])
        terminal["time"]["completed"] += 1
        self.assertIn(
            "NATIVE_G_ROOT_EXPORT_MESSAGE_ORDER_OR_TERMINAL_JOIN_MISMATCH",
            validate_native_case_g_capture(
                NATIVE_G_DOC, CASES["G"], invented_time, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

        changed_execution_flag = copy.deepcopy(NATIVE_G_ROOT_EXPORT_DOC)
        changed_execution_flag["tool_call_records"][0]["executed"] = True
        self.assertIn(
            "NATIVE_G_ROOT_TOOL_CALL_ORDER_OR_RESULT_ID_MISMATCH",
            validate_native_case_g_capture(
                NATIVE_G_DOC, CASES["G"], changed_execution_flag, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
            ),
        )

    def test_case_g_rejects_incomplete_aggregate_completion_or_fabricated_result_id(self) -> None:
        for field, value in (
            ("PENDING_CHILD_COUNT", 1),
            ("REQUIRED_CHILDREN_TERMINAL_AND_CONSUMED", False),
            ("RESULT_IDS", ["result-fabricated"]),
        ):
            with self.subTest(field=field):
                incomplete = copy.deepcopy(NATIVE_G_DOC)
                incomplete["COMPLETION_GATE"][field] = value
                self.assertIn(
                    "NATIVE_G_COMPLETION_RERUN_FILE_CHANGE_OR_ACCEPTANCE_STATUS_MISMATCH",
                    validate_native_case_g_capture(
                        incomplete, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC, NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC
                    ),
                )

        misleading_reconciliation = copy.deepcopy(NATIVE_G_DOC)
        misleading_reconciliation["RECONCILIATION_FILES_CHANGED"] = []
        misleading_reconciliation["NOTES"] = "No worktree access or source change occurred."
        self.assertIn(
            "NATIVE_G_COMPLETION_RERUN_FILE_CHANGE_OR_ACCEPTANCE_STATUS_MISMATCH",
            validate_native_case_g_capture(
                misleading_reconciliation, CASES["G"], NATIVE_G_ROOT_EXPORT_DOC,
                NATIVE_G_VEYRA_EXPORT_DOC, NATIVE_G_THALES_EXPORT_DOC,
            ),
        )


class NativeCaseHMutationTests(unittest.TestCase):
    def test_case_h_reconciles_bounded_native_route_and_keeps_phase11_partial(self) -> None:
        self.assertEqual(CASE_H_ROOT_SESSION_ID, NATIVE_H_DOC["ROOT_SESSION_ID"])
        self.assertEqual(CASE_H_EXPECTED_ROUTE, NATIVE_H_DOC["ACTUAL_ROUTE"])
        self.assertEqual(CASE_H_VEYRA_SESSION_ID, NATIVE_H_DOC["CHILD_SESSIONS"][0]["NATIVE_SESSION_ID"])
        self.assertEqual(
            {"opencode.jsonc", ".opencode/agents/kael.md"},
            set(NATIVE_H_VEYRA_EXPORT_DOC["source_evidence_scope"]["paths"]),
        )
        self.assertEqual(CASE_H_CLASSIFICATIONS, NATIVE_H_DOC["CLASSIFICATIONS"])
        self.assertEqual("LEAN", NATIVE_H_DOC["EFFICIENCY"]["CLASSIFICATION"])
        self.assertIsNone(NATIVE_H_DOC["UNKNOWN_METRICS"]["LOCAL_RUNTIME_VERSION"])
        self.assertIsNone(NATIVE_H_DOC["UNKNOWN_METRICS"]["MAX_SIMULTANEOUS_CHILDREN"])
        self.assertEqual("NOT_OBSERVABLE", NATIVE_H_DOC["UNKNOWN_METRICS"]["NATIVE_PERMISSION_UI"])
        self.assertEqual("NOT_OBSERVABLE", NATIVE_H_DOC["UNKNOWN_METRICS"]["NATIVE_PERMISSION_DECISION"])
        self.assertEqual(
            [],
            validate_native_case_h_capture(
                NATIVE_H_DOC, CASES["H"], NATIVE_H_ROOT_EXPORT_DOC, NATIVE_H_VEYRA_EXPORT_DOC
            ),
        )
        self.assertEqual(
            [],
            validate_phase11_h_reconciliation(
                BASELINE_DOC, CASES_DOC, NATIVE_H_DOC, NATIVE_H_ROOT_EXPORT_DOC, NATIVE_H_VEYRA_EXPORT_DOC
            ),
        )
        self.assertEqual(
            ["HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT"],
            BASELINE_DOC["live_qualification"]["pending_labels"],
        )
        self.assertEqual("PARTIAL", BASELINE_DOC["live_qualification"]["overall_status"])
        self.assertEqual(
            ["HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT", "HUMAN_ACTION_REQUIRED PHASE11_CASE_K_FRESH_ROOT"],
            BASELINE_DOC["phase11_g_reconciliation"]["pending_fresh_root_labels"],
        )
        for prior in (
            "phase11_b3_reconciliation", "phase11_c_reconciliation", "phase11_d_reconciliation",
            "phase11_e_reconciliation", "phase11_e2_reconciliation", "phase11_f_reconciliation",
        ):
            self.assertIn("HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT", BASELINE_DOC[prior]["pending_fresh_root_labels"])

    def test_case_h_rejects_scope_classification_and_parentage_mutations(self) -> None:
        overbroad_scope = copy.deepcopy(NATIVE_H_VEYRA_EXPORT_DOC)
        overbroad_scope["source_evidence_scope"]["paths"].append("unassigned.txt")
        self.assertIn(
            "NATIVE_H_SOURCE_SCOPE_OVERBROAD_OR_PROJECTION_MISMATCH",
            validate_native_case_h_capture(
                NATIVE_H_DOC, CASES["H"], NATIVE_H_ROOT_EXPORT_DOC, overbroad_scope
            ),
        )

        invented_product_bug = copy.deepcopy(NATIVE_H_DOC)
        invented_product_bug["THIRD_PARTY_CLASSIFICATION"]["PRODUCT_CODE_BUG_ESTABLISHED"] = True
        self.assertIn(
            "NATIVE_H_BOUNDED_FINDING_OR_SAFE_RESOLUTION_MISMATCH",
            validate_native_case_h_capture(
                invented_product_bug, CASES["H"], NATIVE_H_ROOT_EXPORT_DOC, NATIVE_H_VEYRA_EXPORT_DOC
            ),
        )

        wrong_parent = copy.deepcopy(NATIVE_H_VEYRA_EXPORT_DOC)
        wrong_parent["session"]["parent_id"] = "ses_fabricated_parent"
        self.assertIn(
            "NATIVE_H_ROOT_CHILD_METADATA_OR_PARENT_JOIN_MISMATCH",
            validate_native_case_h_capture(
                NATIVE_H_DOC, CASES["H"], NATIVE_H_ROOT_EXPORT_DOC, wrong_parent
            ),
        )

        rewritten_history = copy.deepcopy(BASELINE_DOC)
        rewritten_history["phase11_g_reconciliation"]["pending_fresh_root_labels"].remove(
            "HUMAN_ACTION_REQUIRED PHASE11_CASE_H_FRESH_ROOT"
        )
        self.assertIn(
            "CASE_H_HISTORICAL_PENDING_SNAPSHOT_REWRITTEN:phase11_g_reconciliation",
            validate_phase11_h_reconciliation(
                rewritten_history, CASES_DOC, NATIVE_H_DOC, NATIVE_H_ROOT_EXPORT_DOC, NATIVE_H_VEYRA_EXPORT_DOC
            ),
        )

    def test_case_h_rejects_retry_patch_role_completion_and_runtime_overclaims(self) -> None:
        mutations = (
            ("NATIVE_H_BOUNDED_FINDING_OR_SAFE_RESOLUTION_MISMATCH", "NO_BLIND_RETRY", "BLIND_RETRY_SAFE", True),
            ("NATIVE_H_BOUNDED_FINDING_OR_SAFE_RESOLUTION_MISMATCH", "NO_UNAPPROVED_PATCH", "UPSTREAM_PATCH_ATTEMPTED", True),
            ("NATIVE_H_BOUNDED_FINDING_OR_SAFE_RESOLUTION_MISMATCH", "NO_VENDOR_OR_FORK", "VENDOR_OR_FORK_ATTEMPTED", True),
            ("NATIVE_H_COMPLETION_PROVENANCE_OR_ACCEPTANCE_MISMATCH", "UNKNOWN_METRICS", "LOCAL_RUNTIME_VERSION", "1.2.3"),
            ("NATIVE_H_BOUNDED_FINDING_OR_SAFE_RESOLUTION_MISMATCH", "CONSULTATION_COUNTS", "argus", 1),
            ("NATIVE_H_COMPLETION_PROVENANCE_OR_ACCEPTANCE_MISMATCH", "COMPLETION_GATE", "RESULT_IDS", ["fabricated"]),
        )
        for error, section, field, value in mutations:
            with self.subTest(section=section, field=field):
                altered = copy.deepcopy(NATIVE_H_DOC)
                altered[section][field] = value
                self.assertIn(
                    error,
                    validate_native_case_h_capture(
                        altered, CASES["H"], NATIVE_H_ROOT_EXPORT_DOC, NATIVE_H_VEYRA_EXPORT_DOC
                    ),
                )

        raw_text = copy.deepcopy(NATIVE_H_ROOT_EXPORT_DOC)
        raw_text["messages"][0]["text"] = "raw prompt must not be persisted"
        self.assertIn(
            "NATIVE_H_RAW_CONTENT_OR_TIMING_PERSISTED",
            validate_native_case_h_capture(
                NATIVE_H_DOC, CASES["H"], raw_text, NATIVE_H_VEYRA_EXPORT_DOC
            ),
        )


class MutationTests(unittest.TestCase):
    def test_b2_isolation_failure_cannot_be_promoted_to_full_acceptance(self) -> None:
        lost_isolation = copy.deepcopy(BASELINE_DOC)
        report = lost_isolation["phase11_b2_reconciliation"]
        report["case_b2"]["classifications"]["CASE_B2_FRESH_ROOT_ISOLATION"] = "PASS"
        self.assertIn("CASE_B2_CLASSIFICATION_SEPARATION_MISMATCH", validate_case_b_reconciliation(lost_isolation))

        overaccepted = copy.deepcopy(BASELINE_DOC)
        overaccepted["phase11_b2_reconciliation"]["case_b2"]["acceptance_status"] = "PASS"
        self.assertIn("CASE_B2_ACCEPTANCE_MUST_REMAIN_PARTIAL", validate_case_b_reconciliation(overaccepted))

        phase_overaccepted = copy.deepcopy(BASELINE_DOC)
        phase_overaccepted["phase11_b2_reconciliation"]["phase11_status"] = "PASS"
        self.assertIn("PHASE11_STATUS_MUST_REMAIN_PARTIAL", validate_case_b_reconciliation(phase_overaccepted))

    def test_b2_session_identity_and_result_reconciliation_are_bound(self) -> None:
        wrong_kovan = copy.deepcopy(BASELINE_DOC)
        wrong_kovan["phase11_b2_reconciliation"]["case_b2"]["direct_children"]["Kovan"]["session_id"] = "ses_wrongkovan"
        errors = validate_case_b_reconciliation(wrong_kovan)
        self.assertIn("CASE_B2_CHILD_SESSION_ID_MISMATCH:Kovan", errors)
        self.assertIn("CASE_B2_KOVAN_SESSION_RECONCILIATION_MISMATCH", errors)

        replaced_vera = copy.deepcopy(BASELINE_DOC)
        case_b2 = replaced_vera["phase11_b2_reconciliation"]["case_b2"]
        case_b2["review"]["session_id"] = "ses_replacementvera"
        case_b2["result_reconciliation"]["same_original_session"] = False
        errors = validate_case_b_reconciliation(replaced_vera)
        self.assertIn("CASE_B2_FINAL_REVIEW_RECONCILIATION_MISMATCH", errors)
        self.assertIn("CASE_B2_RESULT_RECONCILIATION_MISMATCH", errors)

    def test_event_order_must_be_globally_strictly_increasing(self) -> None:
        trace = changed("A")
        trace["EVENTS"][1]["ORDER"] = 1
        self.assertIn("EVENT_ORDER_NOT_STRICTLY_INCREASING", failures(trace))

    def test_result_consumed_before_terminal_is_rejected(self) -> None:
        trace = changed("A")
        terminal = next(event for event in trace["EVENTS"] if event.get("KIND") == "CHILD_TERMINAL")
        consumed = next(event for event in trace["EVENTS"] if event.get("KIND") == "RESULT_CONSUMED")
        terminal["ORDER"], consumed["ORDER"] = consumed["ORDER"], terminal["ORDER"]
        trace["EVENTS"].sort(key=lambda event: event["ORDER"])

        errors = failures(trace)
        self.assertIn("RESULT_CONSUMED_WITHOUT_PRIOR_TERMINAL:SYN-W1", errors)
        self.assertIn("RESULT_CONSUMED_BEFORE_TERMINAL:SYN-W1", errors)

    def test_fresh_root_native_label_with_only_root_id_is_rejected(self) -> None:
        # This forged in-memory mutation starts from an obvious synthetic trace;
        # rejection tests consistency checks only and is not native evidence.
        root_only = changed("A")
        root_only["EVIDENCE_CLASS"] = "FRESH_ROOT_NATIVE"
        root_only["ROOT_SESSION_ID"] = "ses_forgedroot"

        errors = failures(root_only)
        self.assertIn("ROOT_SESSION_ID_PROVENANCE_MISMATCH", errors)
        self.assertIn("NATIVE_CHILD_SESSION_ID_MISSING_OR_INVALID", errors)
        self.assertIn("NATIVE_CHILD_SESSION_PROVENANCE_MISMATCH", errors)
        self.assertIn("EVENT_ORDER_PROVENANCE_MISSING_OR_MISMATCHED", errors)

    def test_case_a_request_contract_and_consumed_result_reject_stale_success(self) -> None:
        trace = changed("A")
        self.assertEqual("Hello Phase 11 ready", CASES["A"]["request_contract"]["desired_text"])
        self.assertEqual([], validate_trace(trace, CASES["A"]))
        stale = changed("A")
        consumed = next(event for event in stale["EVENTS"] if event.get("KIND") == "RESULT_CONSUMED")
        consumed["RESULT_VALUE"] = "Hello Phase 11"
        stale["RESULT_FIDELITY"]["OBSERVED_RESULT"] = "Hello Phase 11"
        stale["RESULT_FIDELITY"]["MATCHES"] = True
        self.assertIn("CASE_A_SUCCESS_WITH_STALE_OR_MISMATCHED_CONTENT", failures(stale))

    def test_case_b_request_contract_links_the_feature_fixture(self) -> None:
        request = CASES["B"].get("request_contract")
        self.assertIsInstance(request, dict)
        self.assertEqual(
            "tests/phase11-integrated-routing/fixtures/feature/contract.md",
            request["contract_path"],
        )
        self.assertEqual(
            "tests/phase11-integrated-routing/fixtures/feature",
            request["fixture_root"],
        )
        self.assertEqual(
            "tests/phase11-integrated-routing/fixtures/feature/domain.py:calculate_cart",
            request["calculation_boundary"],
        )
        self.assertEqual(
            "tests/phase11-integrated-routing/fixtures/feature/presentation.py:render_totals",
            request["presentation_boundary"],
        )
        self.assertIn("two-field CartTotals(subtotal_cents, total_cents)", request["compatibility_requirement"])
        self.assertIn("domain.py:calculate_cart adds CartTotals.discount_cents", request["material_dependency"])
        self.assertIn("presentation.py:render_totals consumes it", request["material_dependency"])
        self.assertTrue((REPO_ROOT / request["contract_path"]).is_file())
        self.assertTrue((REPO_ROOT / request["fixture_root"]).is_dir())
        self.assertTrue((REPO_ROOT / request["fixture_root"] / "test_scaffold.py").is_file())
        self.assertTrue((REPO_ROOT / request["calculation_boundary"].split(":", 1)[0]).is_file())
        self.assertTrue((REPO_ROOT / request["presentation_boundary"].split(":", 1)[0]).is_file())
        contract = (REPO_ROOT / request["contract_path"]).read_text(encoding="utf-8")
        self.assertIn("pre-feature scaffold", contract.lower())
        self.assertIn("calculate_total(subtotal_cents: int) -> int", contract)
        self.assertIn("discount_cents: int = 0", contract)
        self.assertIn("777 != 12,345 // 10", contract)
        self.assertIn("777 != 12,345 - 12,111", contract)
        implementation = next(child for child in TRACES["B"]["CHILD_SESSIONS"] if child["WORK_ID"] == "feature-implementation")
        self.assertEqual(
            ["fixtures/feature/domain.py", "fixtures/feature/presentation.py"],
            implementation["WRITE_PATHS"],
        )

    def test_complexity_alone_does_not_justify_atlas_but_material_gate_data_can(self) -> None:
        trace = changed("J")
        trace["CASE_ID"] = "B"
        trace["REQUEST_CLASS"] = CASES["B"]["request_class"]
        trace["SCENARIO"] = "default"
        trace["GATE_FACTS"]["EXPLICIT_PLANNING_INTENT"] = False
        trace["GATE_FACTS"]["COMPLEX_FEATURE"] = True
        errors = validate_trace(trace, CASES["B"])
        self.assertIn("ATLAS_WITHOUT_EXPLICIT_INTENT_OR_MATERIAL_PLANNING_JUSTIFICATION", errors)

        complex_only = copy.deepcopy(CASES["B"])
        complex_only["planning_gate_justification"] = {
            "basis": "COMPLEX_FEATURE",
            "rationale": "It is complex.",
            "material_dependencies": [],
        }
        self.assertIn(
            "ATLAS_WITHOUT_EXPLICIT_INTENT_OR_MATERIAL_PLANNING_JUSTIFICATION",
            validate_trace(trace, complex_only),
        )
        materially_justified = copy.deepcopy(CASES["B"])
        materially_justified["planning_gate_justification"] = {
            "basis": "MATERIAL_DEPENDENCY",
            "rationale": "Independent workstreams require an explicit cross-workstream ordering decision.",
            "material_dependencies": [
                {
                    "producer": "contract-selection",
                    "consumer": "migration-design",
                    "planning_need": "A shared compatibility decision must precede both workstreams.",
                }
            ],
        }
        self.assertNotIn(
            "ATLAS_WITHOUT_EXPLICIT_INTENT_OR_MATERIAL_PLANNING_JUSTIFICATION",
            validate_trace(trace, materially_justified),
        )

    def test_synthetic_trace_cannot_be_relabelled_native_by_changing_label_or_root(self) -> None:
        root_only = changed("A")
        root_only["ROOT_SESSION_ID"] = "ses_forgedroot"
        self.assertIn("SYNTHETIC_HAS_ROOT_SESSION_ID", failures(root_only))
        relabelled = changed("A")
        relabelled["EVIDENCE_CLASS"] = "GUIDED_CURRENT_SESSION"
        relabelled["ROOT_SESSION_ID"] = "ses_forgedroot"
        relabelled["EVIDENCE_PROVENANCE"]["CLASS"] = "GUIDED_CURRENT_SESSION"
        relabelled["EVIDENCE_PROVENANCE"]["NATIVE_ROOT_SESSION_ID"] = "ses_forgedroot"
        self.assertIn("NATIVE_CHILD_SESSION_ID_MISSING_OR_INVALID", failures(relabelled))
        self.assertIn("EVENT_ORDER_PROVENANCE_MISSING_OR_MISMATCHED", failures(relabelled))

    def test_native_root_child_and_event_session_joins_must_agree(self) -> None:
        # Forged in-memory mutation data exercises consistency checks only; it is not evidence.
        native = changed("A")
        root_id, child_id = "ses_testroot", "ses_testchild"
        native["EVIDENCE_CLASS"] = "GUIDED_CURRENT_SESSION"
        native["ROOT_SESSION_ID"] = root_id
        native["EVIDENCE_PROVENANCE"].update({
            "CLASS": "GUIDED_CURRENT_SESSION",
            "NATIVE_ROOT_SESSION_ID": root_id,
            "NATIVE_CHILD_SESSION_IDS": [child_id],
            "ORDER_BASIS": "observed",
        })
        native["CHILD_SESSIONS"][0].update({"NATIVE_SESSION_ID": child_id, "PARENT_SESSION_ID": "ses_wrongparent"})
        for event in native["EVENTS"]:
            event["ORDER_BASIS"] = "observed"
            if event.get("CHILD_REF") == "SYN-W1":
                event["NATIVE_SESSION_ID"] = child_id
        self.assertIn("NATIVE_CHILD_PARENT_SESSION_MISMATCH", failures(native))
        wrong_event_join = copy.deepcopy(native)
        wrong_event_join["CHILD_SESSIONS"][0]["PARENT_SESSION_ID"] = root_id
        next(event for event in wrong_event_join["EVENTS"] if event.get("KIND") == "CHILD_START")["NATIVE_SESSION_ID"] = "ses_wrongchild"
        self.assertIn("NATIVE_EVENT_SESSION_JOIN_MISMATCH:SYN-W1", failures(wrong_event_join))

    def test_terminal_refs_order_and_result_ids_are_bound(self) -> None:
        unknown = changed("A")
        insert_event(unknown, {"KIND": "CHILD_TERMINAL", "ACTOR_ROLE": "kael", "CHILD_REF": "SYN-UNKNOWN", "STATE": "SUCCEEDED", "RESULT_ID": "SYN-UNKNOWN-RESULT"})
        self.assertIn("CHILD_TERMINAL_UNKNOWN_CHILD_REF:SYN-UNKNOWN", failures(unknown))
        fabricated = changed("A")
        consumed = next(event for event in fabricated["EVENTS"] if event.get("KIND") == "RESULT_CONSUMED")
        consumed["RESULT_ID"] = "SYN-FABRICATED-RESULT"
        self.assertIn("RESULT_CONSUMED_ID_DOES_NOT_MATCH_TERMINAL:SYN-W1", failures(fabricated))
        before_start = changed("A")
        start = next(event for event in before_start["EVENTS"] if event.get("KIND") == "CHILD_START")
        terminal = next(event for event in before_start["EVENTS"] if event.get("KIND") == "CHILD_TERMINAL")
        start["ORDER"], terminal["ORDER"] = terminal["ORDER"], start["ORDER"]
        before_start["EVENTS"].sort(key=lambda event: event["ORDER"])
        self.assertIn("CHILD_TERMINAL_BEFORE_START:SYN-W1", failures(before_start))

    def test_case_mandatory_dependency_edges_are_present_and_result_precedes_child(self) -> None:
        missing = changed("B")
        missing["DEPENDENCY_ORDER"] = missing["DEPENDENCY_ORDER"][1:]
        self.assertIn("MANDATORY_DEPENDENCY_EDGE_MISSING", failures(missing))
        reversed_edge = changed("B")
        reversed_edge["DEPENDENCY_ORDER"][0] = {"BEFORE": "SYN-W1:RESULT", "AFTER": "SYN-E1"}
        self.assertIn("DEPENDENCY_ORDER_NOT_OBSERVED", failures(reversed_edge))
        early = changed("B")
        events = early["EVENTS"]
        start = next(event for event in events if event.get("KIND") == "CHILD_START" and event.get("CHILD_REF") == "SYN-T1")
        consumed = next(event for event in events if event.get("KIND") == "RESULT_CONSUMED" and event.get("CHILD_REF") == "SYN-W1")
        start["ORDER"], consumed["ORDER"] = consumed["ORDER"], start["ORDER"]
        events.sort(key=lambda event: event["ORDER"])
        self.assertIn("DEPENDENCY_RESULT_NOT_CONSUMED_BEFORE_DEPENDENT_START", failures(early))

    def test_each_specialist_has_a_first_class_forbidden_role_control(self) -> None:
        simple = TRACES["A"]
        for role in EIGHT_SPECIALISTS:
            with self.subTest(role=role):
                self.assertEqual(0, simple["NEGATIVE_CONTROLS"][role])
                mutant = changed("A")
                ref = "SYN-BAD"
                mutant["CHILD_SESSIONS"].append(
                    {"TRACE_REF": ref, "NATIVE_SESSION_ID": None, "AGENT": role, "PARENT_AGENT": "kael", "EXECUTION_STATE": "SUCCEEDED", "WORK_ID": f"forbidden-{role}", "WRITE_PATHS": []}
                )
                mutant["ACTUAL_ROUTE"].append(role)
                mutant["CONSULTATION_COUNTS"][role] = 1
                action = {"veyra": "READ_EVIDENCE", "orin": "ARCHITECT", "atlas": "PLAN", "vera": "REVIEW", "argus": "DIAGNOSE_FUNCTIONAL", "talos": "DIAGNOSE_SECURITY", "thales": "DIAGNOSE_UNCERTAINTY", "helios": "OPTIMIZE_ADVISE"}[role]
                final_index = next(i for i, event in enumerate(mutant["EVENTS"]) if event["KIND"] == "FINAL_OUTCOME")
                is_reasoner = role in {"atlas", "argus", "talos", "thales", "helios"}
                event_count = 5 if is_reasoner else 4
                for event in mutant["EVENTS"][final_index:]:
                    event["ORDER"] += event_count
                bad_events = [{"ORDER": final_index + 1, "ORDER_BASIS": "synthetic", "KIND": "CHILD_START", "ACTOR_ROLE": "kael", "CHILD_REF": ref, "AGENT": role}]
                if is_reasoner:
                    bad_events.append({"ORDER": final_index + 2, "ORDER_BASIS": "synthetic", "KIND": "CONSULT", "ACTOR_ROLE": role, "SESSION_REF": ref, "CONSULTATION_NUMBER": 1, "EVIDENCE_IDS": []})
                action_order = final_index + (3 if is_reasoner else 2)
                bad_events.extend(
                    [
                        {"ORDER": action_order, "ORDER_BASIS": "synthetic", "KIND": "ACTION", "ACTOR_ROLE": role, "ACTION": action, "CHILD_REF": ref},
                        {"ORDER": action_order + 1, "ORDER_BASIS": "synthetic", "KIND": "CHILD_TERMINAL", "ACTOR_ROLE": "kael", "CHILD_REF": ref, "STATE": "SUCCEEDED"},
                        {"ORDER": action_order + 2, "ORDER_BASIS": "synthetic", "KIND": "RESULT_CONSUMED", "ACTOR_ROLE": "kael", "CHILD_REF": ref, "RESULT_ID": "SYN-BAD-RESULT"},
                    ]
                )
                mutant["EVENTS"][final_index:final_index] = bad_events
                mutant["ROLE_PURITY"]["OBSERVED_ACTIONS"].append({"ROLE": role, "ACTION": action})
                self.assertIn(f"NEGATIVE_CONTROL_ACTIVATED:{role}", failures(mutant))

    def test_nox_and_aegis_are_also_first_class_negative_controls(self) -> None:
        simple = TRACES["A"]
        self.assertEqual(0, simple["NEGATIVE_CONTROLS"]["nox"])
        self.assertEqual(0, simple["NEGATIVE_CONTROLS"]["aegis"])
        aegis = changed("L_NORMAL")
        aegis["CHILD_SESSIONS"].append({"TRACE_REF": "SYN-AEGIS", "NATIVE_SESSION_ID": None, "AGENT": "aegis", "PARENT_AGENT": "kael", "EXECUTION_STATE": "SUCCEEDED", "WORK_ID": "forbidden-aegis-child", "WRITE_PATHS": []})
        self.assertIn("AEGIS_CHILD_LAUNCH_FORBIDDEN", failures(aegis))

    def test_worker_must_be_direct_kael_child_and_role_actions_stay_pure(self) -> None:
        worker = changed("D")
        worker["CHILD_SESSIONS"][1]["PARENT_AGENT"] = "argus"
        self.assertIn("DIRECT_CHILD_ROUTE_VIOLATION:veyra", failures(worker))
        plan = changed("J")
        plan_action = next(event for event in plan["EVENTS"] if event.get("ACTOR_ROLE") == "atlas" and event.get("KIND") == "ACTION")
        plan_action["ACTION"] = "IMPLEMENT"
        self.assertIn("ROLE_ACTION_NOT_ALLOWED:atlas:IMPLEMENT", failures(plan))

    def test_action_actor_must_join_the_referenced_child_session_role(self) -> None:
        mutant = changed("B")
        nox_ref = next(child["TRACE_REF"] for child in mutant["CHILD_SESSIONS"] if child["AGENT"] == "nox")
        insert_event(mutant, {"KIND": "ACTION", "ACTOR_ROLE": "kovan", "ACTION": "TEST", "CHILD_REF": nox_ref}, "FINAL_OUTCOME")
        mutant["ROLE_PURITY"]["OBSERVED_ACTIONS"].append({"ROLE": "kovan", "ACTION": "TEST"})
        self.assertIn(f"ACTION_CHILD_SESSION_ROLE_MISMATCH:kovan:{nox_ref}", failures(mutant))

    def test_argus_and_thales_followup_reuses_same_session_and_new_evidence(self) -> None:
        self.assertEqual(set(), failures(changed("D")))
        for trace_id, role in (("D", "argus"), ("G", "thales")):
            with self.subTest(role=role):
                trace = changed(trace_id)
                calls = [event for event in trace["EVENTS"] if event.get("KIND") == "CONSULT" and event.get("ACTOR_ROLE") == role]
                calls[1]["SESSION_REF"] = "SYN-OTHER-SESSION"
                self.assertIn(f"FOLLOWUP_DID_NOT_REUSE_SAME_SESSION:{role}", failures(trace))
                trace = changed(trace_id)
                calls = [event for event in trace["EVENTS"] if event.get("KIND") == "CONSULT" and event.get("ACTOR_ROLE") == role]
                calls[1]["EVIDENCE_IDS"] = []
                self.assertIn(f"FOLLOWUP_WITHOUT_NEW_EVIDENCE:{role}", failures(trace))
        reused = changed("G")
        request = next(event for event in reused["EVENTS"] if event.get("KIND") == "EVIDENCE_REQUEST")
        produced = next(event for event in reused["EVENTS"] if event.get("KIND") == "EVIDENCE_PRODUCED")
        delivered = next(event for event in reused["EVENTS"] if event.get("KIND") == "EVIDENCE_DELIVERED" and event.get("CHILD_REF") == request["WORKER_REF"])
        consume = next(event for event in reused["EVENTS"] if event.get("KIND") == "RESULT_CONSUMED" and event.get("CHILD_REF") == request["WORKER_REF"])
        followup = next(event for event in reused["EVENTS"] if event.get("KIND") == "CONSULT" and event.get("CONSULTATION_NUMBER") == 2)
        for event in (request, produced, delivered, consume, followup):
            event["EVIDENCE_IDS"] = ["SYN-OBS1"]
        self.assertIn("FOLLOWUP_REUSES_PRIOR_EVIDENCE:thales", failures(reused))
        duplicate_fact = changed("G")
        old_fact = next(event["DISTINGUISHING_FACT"] for event in duplicate_fact["EVENTS"] if event.get("KIND") == "EVIDENCE_DELIVERED" and event.get("CHILD_REF") == "SYN-N0")
        new_fact = next(event for event in duplicate_fact["EVENTS"] if event.get("KIND") == "EVIDENCE_PRODUCED")
        new_fact["DISTINGUISHING_FACT"] = old_fact
        self.assertIn("FOLLOWUP_EVIDENCE_NOT_MATERIALLY_NEW:thales", failures(duplicate_fact))
        unchanged_argus_evidence = changed("D")
        consultations = [event for event in unchanged_argus_evidence["EVENTS"] if event.get("KIND") == "CONSULT" and event.get("ACTOR_ROLE") == "argus"]
        consultations[0]["EVIDENCE_IDS"] = ["SYN-E1"]
        consultations[1]["EVIDENCE_IDS"] = ["SYN-E1"]
        self.assertIn("FOLLOWUP_REUSES_PRIOR_EVIDENCE:argus", failures(unchanged_argus_evidence))

        evidence_request_without_followup = changed("D")
        followup = next(
            event for event in evidence_request_without_followup["EVENTS"]
            if event.get("KIND") == "CONSULT" and event.get("ACTOR_ROLE") == "argus" and event.get("CONSULTATION_NUMBER") == 2
        )
        evidence_request_without_followup["EVENTS"].remove(followup)
        evidence_request_without_followup["CONSULTATION_COUNTS"]["argus"] = 1
        self.assertIn("EVIDENCE_REQUEST_NOT_FOLLOWED_UP_IN_SAME_SESSION:argus", failures(evidence_request_without_followup))
        out_of_order = changed("D")
        events = out_of_order["EVENTS"]
        delivery = next(event for event in events if event.get("KIND") == "EVIDENCE_DELIVERED")
        production = next(event for event in events if event.get("KIND") == "EVIDENCE_PRODUCED")
        delivery["ORDER"], production["ORDER"] = production["ORDER"], delivery["ORDER"]
        events.sort(key=lambda event: event["ORDER"])
        self.assertIn("EVIDENCE_DELIVERED_BEFORE_PRODUCTION:argus", failures(out_of_order))

    def test_consultation_budgets_and_no_progress_stop(self) -> None:
        self.assertEqual({"argus": 3, "talos": 3, "thales": 2, "atlas": 2, "helios": 2}, HARD_BUDGET)
        argus = changed("D")
        insert_event(argus, {"KIND": "CONSULT", "ACTOR_ROLE": "argus", "SESSION_REF": "SYN-R1", "CONSULTATION_NUMBER": 3, "EVIDENCE_IDS": []}, "CHILD_TERMINAL")
        argus["CONSULTATION_COUNTS"]["argus"] = 3
        self.assertIn("THIRD_CONSULTATION_NOT_JUSTIFIED:argus", failures(argus))
        argus_four = changed("D")
        insert_event(argus_four, {"KIND": "CONSULT", "ACTOR_ROLE": "argus", "SESSION_REF": "SYN-R1", "CONSULTATION_NUMBER": 3, "EVIDENCE_IDS": ["SYN-E2"]}, "CHILD_TERMINAL")
        insert_event(argus_four, {"KIND": "CONSULT", "ACTOR_ROLE": "argus", "SESSION_REF": "SYN-R1", "CONSULTATION_NUMBER": 4, "EVIDENCE_IDS": ["SYN-E2"]}, "CHILD_TERMINAL")
        argus_four["CONSULTATION_COUNTS"]["argus"] = 4
        self.assertIn("HARD_CONSULTATION_BUDGET_EXCEEDED:argus", failures(argus_four))
        talos = changed("E")
        insert_event(talos, {"KIND": "CONSULT", "ACTOR_ROLE": "talos", "SESSION_REF": "SYN-R1", "CONSULTATION_NUMBER": 2, "EVIDENCE_IDS": ["SYN-T1"]}, "CHILD_TERMINAL")
        insert_event(talos, {"KIND": "CONSULT", "ACTOR_ROLE": "talos", "SESSION_REF": "SYN-R1", "CONSULTATION_NUMBER": 3, "EVIDENCE_IDS": ["SYN-T2"]}, "CHILD_TERMINAL")
        talos["CONSULTATION_COUNTS"]["talos"] = 3
        self.assertIn("THIRD_CONSULTATION_NOT_JUSTIFIED:talos", failures(talos))
        talos_four = changed("E")
        for number in range(2, 5):
            insert_event(talos_four, {"KIND": "CONSULT", "ACTOR_ROLE": "talos", "SESSION_REF": "SYN-R1", "CONSULTATION_NUMBER": number, "EVIDENCE_IDS": [f"SYN-T{number}"]}, "CHILD_TERMINAL")
        talos_four["CONSULTATION_COUNTS"]["talos"] = 4
        self.assertIn("HARD_CONSULTATION_BUDGET_EXCEEDED:talos", failures(talos_four))
        for trace_id, role in (("G", "thales"), ("J", "atlas"), ("I", "helios")):
            with self.subTest(role=role):
                trace = changed(trace_id)
                session = next(child["TRACE_REF"] for child in trace["CHILD_SESSIONS"] if child["AGENT"] == role)
                existing_count = sum(event.get("KIND") == "CONSULT" and event.get("ACTOR_ROLE") == role for event in trace["EVENTS"])
                for number in range(existing_count + 1, HARD_BUDGET[role] + 2):
                    insert_event(trace, {"KIND": "CONSULT", "ACTOR_ROLE": role, "SESSION_REF": session, "CONSULTATION_NUMBER": number, "EVIDENCE_IDS": [f"SYN-EXTRA-{number}"]}, "CHILD_TERMINAL")
                trace["CONSULTATION_COUNTS"][role] = HARD_BUDGET[role] + 1
                self.assertIn(f"HARD_CONSULTATION_BUDGET_EXCEEDED:{role}", failures(trace))
        no_progress = changed("D")
        insert_event(no_progress, {"KIND": "NO_PROGRESS_STOP", "ACTOR_ROLE": "argus", "SESSION_REF": "SYN-R1"}, "CONSULT")
        self.assertIn("CONSULTATION_AFTER_NO_PROGRESS_STOP:argus", failures(no_progress))
        stopped = changed("G")
        second_consult = next(event for event in stopped["EVENTS"] if event.get("KIND") == "CONSULT" and event.get("CONSULTATION_NUMBER") == 2)
        insert_order = second_consult["ORDER"] + 1
        for event in stopped["EVENTS"]:
            if event["ORDER"] >= insert_order:
                event["ORDER"] += 1
        stopped["EVENTS"].insert(stopped["EVENTS"].index(second_consult) + 1, {"ORDER": insert_order, "ORDER_BASIS": "synthetic", "KIND": "NO_PROGRESS_STOP", "ACTOR_ROLE": "thales", "SESSION_REF": "SYN-R1"})
        self.assertEqual(set(), failures(stopped))

    def test_dependency_order_is_evidence_derived(self) -> None:
        trace = changed("D")
        trace["DEPENDENCY_ORDER"] = [{"BEFORE": "SYN-R1:CONSULT:2", "AFTER": "SYN-W1:RESULT"}]
        self.assertIn("DEPENDENCY_ORDER_NOT_OBSERVED", failures(trace))

    def test_completion_requires_terminal_and_exactly_once_consumption(self) -> None:
        missing = changed("A")
        missing["EVENTS"] = [event for event in missing["EVENTS"] if not (event["KIND"] == "RESULT_CONSUMED" and event.get("CHILD_REF") == "SYN-W1")]
        self.assertIn("RESULT_CONSUMPTION_NOT_EXACTLY_ONCE:SYN-W1", failures(missing))
        duplicate = changed("A")
        consumed = next(event for event in duplicate["EVENTS"] if event["KIND"] == "RESULT_CONSUMED")
        insert_event(duplicate, copy.deepcopy(consumed))
        self.assertIn("RESULT_CONSUMPTION_NOT_EXACTLY_ONCE:SYN-W1", failures(duplicate))

    def test_unknown_execution_stops_without_retry_or_fabricated_result(self) -> None:
        unknown = changed("A")
        unknown["CHILD_SESSIONS"][0]["EXECUTION_STATE"] = "UNKNOWN"
        unknown["EVENTS"] = [event for event in unknown["EVENTS"] if event["KIND"] not in {"ACTION", "CHILD_TERMINAL", "RESULT_CONSUMED"}]
        unknown["EVENTS"][-1]["ORDER"] = len(unknown["EVENTS"])
        unknown["ROLE_PURITY"]["OBSERVED_ACTIONS"] = []
        unknown["COMPLETION_GATE"].update({"PENDING_CHILD_COUNT": 1, "UNCONSUMED_RESULT_COUNT": 0, "UNKNOWN_EXECUTION_COUNT": 1, "EXACT_ONCE": True})
        unknown["FINAL_OUTCOME"] = "COMPLETION_UNCONFIRMED"
        unknown["EVENTS"][-1]["VALUE"] = "COMPLETION_UNCONFIRMED"
        unknown["ROUTING_RESULT"] = "STOP_NO_RETRY"
        unknown["RESULT_FIDELITY"].update({"EXPECTED_RESULT": "Hello Phase 11 ready", "OBSERVED_RESULT": None, "MATCHES": None, "UNKNOWN": True})
        self.assertEqual([], validate_trace(unknown, CASES["A"]))
        retry = copy.deepcopy(unknown)
        retry["CHILD_SESSIONS"].append({"TRACE_REF": "SYN-W2", "NATIVE_SESSION_ID": None, "AGENT": "kovan", "PARENT_AGENT": "kael", "EXECUTION_STATE": "SUCCEEDED", "WORK_ID": "simple-message-edit", "WRITE_PATHS": ["fixtures/simple/message.txt"]})
        insert_event(retry, {"KIND": "CHILD_START", "ACTOR_ROLE": "kael", "CHILD_REF": "SYN-W2", "AGENT": "kovan"})
        retry["ACTUAL_ROUTE"].append("kovan")
        retry["CONSULTATION_COUNTS"]["kovan"] = 2
        retry["MAX_SIMULTANEOUS_CHILDREN"] = 2
        retry["COMPLETION_GATE"]["PENDING_CHILD_COUNT"] = 2
        self.assertIn("UNKNOWN_EXECUTION_RETRY_FORBIDDEN", failures(retry))

    def test_question_barrier_and_single_bounded_question(self) -> None:
        valid = changed("A")
        insert_event(valid, {"KIND": "ACTION", "ACTOR_ROLE": "kael", "ACTION": "ASK_USER"})
        insert_event(valid, {"KIND": "USER_QUESTION", "ACTOR_ROLE": "kael", "QUESTION_ID": "SYN-Q1", "BOUNDED": True, "QUESTION": "Which greeting variant should the fixture use?"})
        valid["ROLE_PURITY"]["OBSERVED_ACTIONS"].append({"ROLE": "kael", "ACTION": "ASK_USER"})
        valid["USER_QUESTION_COUNT"] = 1
        valid["FINAL_OUTCOME"] = "NEEDS_USER_INPUT"
        valid["EVENTS"][-1]["VALUE"] = "NEEDS_USER_INPUT"
        self.assertEqual(set(), failures(valid))
        unanswered = copy.deepcopy(valid)
        unanswered["FINAL_OUTCOME"] = "SUCCEEDED"
        unanswered["EVENTS"][-1]["VALUE"] = "SUCCEEDED"
        self.assertIn("UNRESOLVED_USER_QUESTION_NOT_REPORTED_PENDING", failures(unanswered))
        early = changed("D")
        insert_event(early, {"KIND": "USER_QUESTION", "ACTOR_ROLE": "kael", "BOUNDED": True, "QUESTION": "Which contract applies?"}, "EVIDENCE_DELIVERED")
        early["USER_QUESTION_COUNT"] = 1
        early["COMPLETION_GATE"]["QUESTION_BARRIER_SATISFIED"] = False
        self.assertIn("USER_QUESTION_BEFORE_CHILDREN_RECONCILED", failures(early))
        non_kael = changed("A")
        insert_event(non_kael, {"KIND": "USER_QUESTION", "ACTOR_ROLE": "veyra", "QUESTION_ID": "SYN-Q1", "BOUNDED": True, "QUESTION": "Which greeting?"})
        non_kael["USER_QUESTION_COUNT"] = 1
        self.assertIn("USER_QUESTION_NOT_OWNED_BY_KAEL", failures(non_kael))
        pre_answer = changed("B")
        question = {"ORDER_BASIS": "synthetic", "KIND": "USER_QUESTION", "ACTOR_ROLE": "kael", "QUESTION_ID": "SYN-Q1", "BOUNDED": True, "QUESTION": "Which supplied display contract applies?"}
        events = pre_answer["EVENTS"]
        insert_at = next(i for i, event in enumerate(events) if event.get("KIND") == "CHILD_START" and event.get("CHILD_REF") == "SYN-T1")
        events.insert(insert_at, question)
        for order, event in enumerate(events, start=1):
            event["ORDER"] = order
        pre_answer["USER_QUESTION_COUNT"] = 1
        self.assertIn("DEPENDENT_WORK_BEFORE_QUESTION_RESOLVED", failures(pre_answer))
        resolved = copy.deepcopy(pre_answer)
        start_order = next(event["ORDER"] for event in resolved["EVENTS"] if event.get("KIND") == "CHILD_START" and event.get("CHILD_REF") == "SYN-T1")
        resolved["EVENTS"].insert(
            next(i for i, event in enumerate(resolved["EVENTS"]) if event["ORDER"] == start_order),
            {"ORDER": 0, "ORDER_BASIS": "synthetic", "KIND": "QUESTION_RESOLVED", "ACTOR_ROLE": "user", "QUESTION_ID": "SYN-Q1", "ANSWER": "Use the supplied display contract."},
        )
        for order, event in enumerate(resolved["EVENTS"], start=1):
            event["ORDER"] = order
        self.assertNotIn("DEPENDENT_WORK_BEFORE_QUESTION_RESOLVED", failures(resolved))
        two = changed("A")
        insert_event(two, {"KIND": "USER_QUESTION", "ACTOR_ROLE": "kael", "QUESTION_ID": "SYN-Q1", "BOUNDED": True, "QUESTION": "Question one?"})
        insert_event(two, {"KIND": "USER_QUESTION", "ACTOR_ROLE": "kael", "QUESTION_ID": "SYN-Q2", "BOUNDED": True, "QUESTION": "Question two?"})
        two["USER_QUESTION_COUNT"] = 2
        self.assertIn("MORE_THAN_ONE_BOUNDED_USER_QUESTION", failures(two))

    def test_fast_concurrency_counts_are_real_event_counts_and_writers_do_not_overlap(self) -> None:
        dishonest = changed("K_FAST")
        dishonest["OPERATIONAL_PROXIES"]["ACTUAL_COUNTED_CONCURRENCY"] = 3
        self.assertIn("FAST_CONCURRENCY_PROXY_MISMATCH", failures(dishonest))
        over_limit = changed("K_FAST")
        over_limit["OPERATIONAL_PROXIES"]["USEFUL_INDEPENDENT_WRITER_COUNT"] = 5
        over_limit["OPERATIONAL_PROXIES"]["ACTUAL_COUNTED_CONCURRENCY"] = 5
        over_limit["MAX_SIMULTANEOUS_CHILDREN"] = 5
        self.assertIn("FAST_CONCURRENCY_EXCEEDS_FOUR", failures(over_limit))
        overlapping = changed("K_FAST")
        overlapping["CHILD_SESSIONS"][1]["WRITE_PATHS"] = list(overlapping["CHILD_SESSIONS"][0]["WRITE_PATHS"])
        self.assertIn("FAST_WRITER_PATHS_OVERLAP", failures(overlapping))
        dependent = changed("K_FAST")
        dependent["DEPENDENCY_ORDER"] = [{"BEFORE": "SYN-W1:RESULT", "AFTER": "SYN-W2"}]
        self.assertIn("FAST_WRITERS_NOT_INDEPENDENT", failures(dependent))

    def test_helios_needs_explicit_intent_and_stops_before_implementation(self) -> None:
        no_intent = changed("I")
        no_intent["GATE_FACTS"]["EXPLICIT_OPTIMIZATION_INTENT"] = False
        self.assertIn("HELIOS_WITHOUT_EXPLICIT_OPTIMIZATION_INTENT", failures(no_intent))
        implementation = changed("I")
        proposal = next(event for event in implementation["EVENTS"] if event["KIND"] == "PROPOSAL")
        insert_event(implementation, {"KIND": "ACTION", "ACTOR_ROLE": "kovan", "ACTION": "IMPLEMENT"}, "APPROVAL_GATE")
        implementation["ROLE_PURITY"]["OBSERVED_ACTIONS"].insert(
            implementation["ROLE_PURITY"]["OBSERVED_ACTIONS"].index({"ROLE": "helios", "ACTION": "OPTIMIZE_ADVISE"}) + 1,
            {"ROLE": "kovan", "ACTION": "IMPLEMENT"},
        )
        self.assertGreater(proposal["ORDER"], 0)
        self.assertIn("IMPLEMENTATION_AFTER_HELIOS_PROPOSAL_BEFORE_APPROVAL", failures(implementation))

    def test_third_party_change_requires_explicit_approval(self) -> None:
        patch = changed("H")
        insert_event(patch, {"KIND": "THIRD_PARTY_MODIFICATION", "ACTOR_ROLE": "kovan", "OPERATION": "VENDOR"})
        self.assertIn("THIRD_PARTY_PATCH_VENDOR_FORK_WITHOUT_APPROVAL", failures(patch))

    def test_explicit_maintain_entry_must_precede_and_bind_aegis_actions(self) -> None:
        reversed_entry = changed("L_EXPLICIT_MAINTAIN")
        entry = next(event for event in reversed_entry["EVENTS"] if event.get("KIND") == "MAINTENANCE_ENTRY")
        action = next(event for event in reversed_entry["EVENTS"] if event.get("KIND") == "ACTION" and event.get("ACTOR_ROLE") == "aegis")
        entry["ORDER"], action["ORDER"] = action["ORDER"], entry["ORDER"]
        reversed_entry["EVENTS"].sort(key=lambda event: event["ORDER"])
        self.assertIn("AEGIS_ACTION_BEFORE_EXPLICIT_MAINTENANCE_ENTRY", failures(reversed_entry))
        unbound = changed("L_EXPLICIT_MAINTAIN")
        aegis = next(event for event in unbound["EVENTS"] if event.get("KIND") == "ACTION" and event.get("ACTOR_ROLE") == "aegis")
        aegis["ENTRY_REF"] = "SYN-OTHER-ENTRY"
        self.assertIn("AEGIS_ACTION_NOT_BOUND_TO_EXPLICIT_ENTRY", failures(unbound))

    def test_case_f_and_orin_boundary_are_explicit_synthetic_contracts(self) -> None:
        f = changed("F")
        self.assertEqual([], validate_trace(f, CASES["F"]))
        response = next(event for event in f["EVENTS"] if event.get("KIND") == "OPERATIONAL_RESPONSE")
        response["INSTALL_ATTEMPTED"] = True
        self.assertIn("CASE_F_UNAUTHORIZED_INSTALL_OR_PRODUCT_BUG_CLAIM", failures(f))
        self.assertEqual(0, TRACES["B"]["NEGATIVE_CONTROLS"]["orin"])
        self.assertEqual("NOT_ESTABLISHED_BY_PHASE11_CASE_B", CASES["B"]["positive_orin_qualification"])
        overclaim = copy.deepcopy(CASES["B"])
        overclaim["positive_orin_qualification"] = "PASS"
        self.assertIn("CASE_B_ORIN_POSITIVE_QUALIFICATION_NOT_ESTABLISHED", validate_trace(TRACES["B"], overclaim))

    def test_expected_and_actual_routes_are_independent(self) -> None:
        mutant = changed("B")
        mutant["EXPECTED_ROUTE"] = list(mutant["ACTUAL_ROUTE"])
        mutant["EXPECTED_ROUTE"].append("thales")
        self.assertIn("EXPECTED_ROUTE_DOES_NOT_MATCH_CASE_MATRIX", failures(mutant))

    def test_unknown_observation_metrics_are_null_not_zero(self) -> None:
        trace = changed("I")
        trace["RESULT_FIDELITY"].update({"OBSERVED_RESULT": None, "MATCHES": None, "UNKNOWN": True})
        self.assertEqual(set(), failures(trace))
        fabricated = changed("I")
        fabricated["RESULT_FIDELITY"].update({"OBSERVED_RESULT": 0, "MATCHES": False, "UNKNOWN": True})
        self.assertIn("UNKNOWN_RESULT_METRIC_MUST_BE_NULL", failures(fabricated))


if __name__ == "__main__":
    unittest.main()
