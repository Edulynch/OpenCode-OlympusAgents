"""Human-only doctor guidance; structured diagnostics remain unchanged."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympus import cli, doctor, global_readonly, user_config


def response(*, scope: str = "project", issues: list[dict] | None = None) -> dict:
    context = {"scope": scope}
    if scope == "project":
        context["target"] = "C:/work/sample"
    return {
        "schema_version": 1,
        "operation": "doctor",
        "result": "failed" if issues else "ok",
        "context": context,
        "data": {},
        "issues": issues or [],
    }


def render(value: dict, *, as_json: bool = False) -> tuple[str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        cli.emit(value, as_json)
    return stdout.getvalue(), stderr.getvalue()


class DoctorGuidance(unittest.TestCase):
    def test_project_drift_recommends_preserving_target_edits(self):
        stdout, stderr = render(response(issues=[{
            "code": "managed_file_drift",
            "message": "Managed file changed: .opencode/agents/kael.md",
            "path": ".opencode/agents/kael.md",
        }]))
        self.assertIn("managed_file_drift:", stderr)
        self.assertIn("next step (project scope):", stdout)
        self.assertIn("target: C:/work/sample", stdout)
        self.assertIn("preserve local edits", stdout)
        self.assertIn("reconcile ownership", stdout)

    def test_global_invalid_manifest_and_verifier_guidance_are_contextual(self):
        stdout, stderr = render(response(scope="global", issues=[
            {"code": "invalid_global_manifest", "message": "Unsupported global manifest."},
            {"code": "native_verify_unavailable", "message": "PowerShell 7 unavailable."},
        ]))
        self.assertIn("invalid_global_manifest:", stderr)
        self.assertIn("native_verify_unavailable:", stderr)
        self.assertEqual(2, stdout.count("next step (global scope):"))
        self.assertNotIn("shown above", stdout)
        self.assertIn("Preserve the global manifest", stdout)
        self.assertIn("PowerShell 7 availability", stdout)

    def test_invalid_user_configuration_has_manual_safe_guidance(self):
        stdout, _ = render(response(issues=[{
            "code": "invalid_user_configuration",
            "message": "Invalid JSON: C:/Users/Ada/Olympus/config.json",
        }]))
        self.assertIn("correct its JSON, schema", stdout)
        self.assertIn("then rerun doctor", stdout)

    def test_success_without_issues_has_no_recommendation(self):
        stdout, stderr = render(response())
        self.assertIn("doctor: ok", stdout)
        self.assertNotIn("next step", stdout)
        self.assertEqual("", stderr)

    def test_unknown_issue_remains_visible_with_neutral_fallback(self):
        stdout, stderr = render(response(issues=[{
            "code": "future_diagnostic",
            "message": "Unknown condition.",
        }]))
        self.assertIn("future_diagnostic: Unknown condition.", stderr)
        self.assertIn("Review this issue code and message", stdout)
        self.assertNotIn("install", stdout.lower())

    def test_non_doctor_human_output_is_unchanged(self):
        value = response(issues=[{"code": "future_diagnostic", "message": "Keep visible."}])
        value["operation"] = "config check"
        stdout, stderr = render(value)
        self.assertNotIn("next step", stdout)
        self.assertIn("future_diagnostic: Keep visible.", stderr)

    def test_missing_context_makes_no_location_claim(self):
        value = response(issues=[{"code": "future_diagnostic", "message": "Unknown condition."}])
        value["context"] = {}
        stdout, _ = render(value)
        self.assertIn("next step: Review this issue code and message", stdout)
        self.assertNotIn("shown above", stdout)
        self.assertNotIn("displayed target", stdout)

    def test_json_output_is_exact_response_without_guidance(self):
        value = response(issues=[{"code": "managed_file_drift", "message": "Changed."}])
        before = json.loads(json.dumps(value))
        stdout, stderr = render(value, as_json=True)
        self.assertEqual(json.dumps(value, ensure_ascii=False) + "\n", stdout)
        self.assertEqual("", stderr)
        self.assertEqual(before, value)

    def test_presentation_does_not_resolve_or_write_or_run_commands(self):
        value = response(issues=[{"code": "managed_file_drift", "message": "Changed."}])
        with (
            mock.patch.object(Path, "resolve", side_effect=AssertionError("resolver called")),
            mock.patch.object(Path, "write_text", side_effect=AssertionError("write called")),
            mock.patch.object(Path, "write_bytes", side_effect=AssertionError("write called")),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess called")),
            mock.patch.object(user_config, "select_scope") as select_scope,
            mock.patch.object(global_readonly, "resolve_roots") as resolve_roots,
            mock.patch.object(doctor, "diagnose") as diagnose,
        ):
            render(value)
        select_scope.assert_not_called()
        resolve_roots.assert_not_called()
        diagnose.assert_not_called()


if __name__ == "__main__":
    unittest.main()
