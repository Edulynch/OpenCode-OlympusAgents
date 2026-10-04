"""Semantic positive traces and adversarial mutations for Phase 11 artifacts."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from qualify import (
    CASE_B2_CHILD_SESSION_IDS,
    CASE_B2_ROOT_SESSION_ID,
    EIGHT_SPECIALISTS,
    HARD_BUDGET,
    load_json,
    run_static_baseline_checks,
    validate_case_b_reconciliation,
    validate_native_invocation_capture,
    validate_phase11_b3_reconciliation,
    validate_trace,
)


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CASES_DOC = load_json(HERE / "cases.json")
TRACES_DOC = load_json(HERE / "traces.json")
BASELINE_DOC = load_json(HERE / "baseline.json")
NATIVE_B3_DOC = load_json(HERE / "case-b3.native-trace.json")
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
