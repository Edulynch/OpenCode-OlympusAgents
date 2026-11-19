"""Windows regression tests for literal, no-clobber Spec Kit plan setup."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SETUP_PLAN = ROOT / ".specify/scripts/powershell/setup-plan.ps1"
COMMON = ROOT / ".specify/scripts/powershell/common.ps1"
RACE_HOOK = r"""

function Resolve-TemplateContent {
    param([string]$TemplateName, [string]$RepoRoot)
    [System.IO.File]::WriteAllText($env:SPECIFY_TEST_RACE_PLAN, 'competing plan')
    return 'template must not replace the competing plan'
}
"""


class SetupPlanRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != "nt":
            raise unittest.SkipTest("Spec Kit setup-plan regression requires Windows.")
        cls.pwsh = shutil.which("pwsh")
        if cls.pwsh is None:
            raise unittest.SkipTest("PowerShell 7 is unavailable.")

    def setUp(self):
        temp_parent = Path(tempfile.gettempdir()) / "opencode"
        temp_parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix="specify-setup-plan-", dir=temp_parent
        )
        self.addCleanup(self.temporary.cleanup)

        self.root = Path(self.temporary.name) / "repo [checkout]"
        self.script_dir = self.root / ".specify/scripts/powershell"
        self.script_dir.mkdir(parents=True)
        shutil.copyfile(SETUP_PLAN, self.script_dir / SETUP_PLAN.name)
        shutil.copyfile(COMMON, self.script_dir / COMMON.name)

        self.feature_dir = self.root / "specs/[team]"
        specify_dir = self.root / ".specify"
        specify_dir.mkdir(parents=True, exist_ok=True)
        (specify_dir / "feature.json").write_text(
            json.dumps({"feature_directory": "specs/[team]"}),
            encoding="utf-8",
        )
        self.plan = self.feature_dir / "plan.md"

    def write_template(self, content: str = "# Fixture plan\n"):
        template_dir = self.root / ".specify/templates/overrides"
        template_dir.mkdir(parents=True, exist_ok=True)
        with (template_dir / "plan-template.md").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            stream.write(content)

    def run_setup(
        self,
        *,
        race_plan: Path | None = None,
        feature_directory: str | Path | None = None,
        no_persist: bool = True,
    ):
        environment = os.environ.copy()
        environment.pop("SPECIFY_FEATURE", None)
        environment.pop("SPECIFY_FEATURE_DIRECTORY", None)
        environment["SPECIFY_INIT_DIR"] = str(self.root)
        if feature_directory is not None:
            environment["SPECIFY_FEATURE_DIRECTORY"] = str(feature_directory)
        if no_persist:
            environment["SPECIFY_FEATURE_NO_PERSIST"] = "1"
        else:
            environment.pop("SPECIFY_FEATURE_NO_PERSIST", None)
        if race_plan is not None:
            environment["SPECIFY_TEST_RACE_PLAN"] = str(race_plan)
        else:
            environment.pop("SPECIFY_TEST_RACE_PLAN", None)
        return subprocess.run(
            [
                self.pwsh,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(self.script_dir / SETUP_PLAN.name),
                "-Json",
            ],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

    def assert_json_output(self, result):
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(str(self.plan), payload["IMPL_PLAN"])
        self.assertEqual(str(self.feature_dir), payload["FEATURE_DIR"])
        return payload

    def test_saved_absolute_sibling_is_rejected_without_writes(self):
        sibling = Path(self.temporary.name) / (self.root.name + " stale checkout")
        sibling.mkdir()
        sentinel = sibling / "sentinel.txt"
        sentinel.write_bytes(b"old checkout")
        feature_json = self.root / ".specify/feature.json"
        feature_json.write_text(
            json.dumps({"feature_directory": str(sibling / "specs" / "old-feature")}),
            encoding="utf-8",
        )
        original_state = feature_json.read_bytes()

        result = self.run_setup()

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertEqual("", result.stdout)
        self.assertIn("inside the selected project", result.stderr)
        self.assertEqual(original_state, feature_json.read_bytes())
        self.assertEqual(b"old checkout", sentinel.read_bytes())
        self.assertEqual([sentinel], list(sibling.iterdir()))

    def test_saved_relative_escape_is_rejected_without_writes(self):
        sibling = Path(self.temporary.name) / "repo [relative sibling]"
        sibling.mkdir()
        sentinel = sibling / "sentinel.txt"
        sentinel.write_bytes(b"do not touch")
        feature_json = self.root / ".specify/feature.json"
        feature_json.write_text(
            json.dumps(
                {"feature_directory": "../repo [relative sibling]/specs/old-feature"}
            ),
            encoding="utf-8",
        )
        original_state = feature_json.read_bytes()

        result = self.run_setup()

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("inside the selected project", result.stderr)
        self.assertEqual(original_state, feature_json.read_bytes())
        self.assertEqual(b"do not touch", sentinel.read_bytes())
        self.assertEqual([sentinel], list(sibling.iterdir()))

    def test_explicit_relative_escape_and_drive_relative_are_rejected(self):
        sibling = Path(self.temporary.name) / "repo [explicit sibling]"
        sibling.mkdir()
        sentinel = sibling / "sentinel.txt"
        sentinel.write_bytes(b"do not touch")
        feature_json = self.root / ".specify/feature.json"
        original_state = feature_json.read_bytes()

        for value in (
            "../repo [explicit sibling]/specs/old-feature",
            "C:specs/old-feature",
        ):
            with self.subTest(feature_directory=value):
                result = self.run_setup(
                    feature_directory=value,
                    no_persist=False,
                )
                self.assertNotEqual(0, result.returncode, result.stdout)
                self.assertEqual("", result.stdout)
                self.assertEqual(original_state, feature_json.read_bytes())
                self.assertEqual([sentinel], list(sibling.iterdir()))

    def test_saved_relative_path_normalizes_inside_checkout(self):
        feature_json = self.root / ".specify/feature.json"
        feature_json.write_text(
            json.dumps({"feature_directory": "specs/../specs/[team]"}),
            encoding="utf-8",
        )
        original_state = feature_json.read_bytes()

        result = self.run_setup()

        self.assert_json_output(result)
        self.assertEqual(original_state, feature_json.read_bytes())
        self.assertTrue(self.plan.is_file())

    def test_saved_project_root_is_rejected(self):
        feature_json = self.root / ".specify/feature.json"
        feature_json.write_text(
            json.dumps({"feature_directory": str(self.root)}),
            encoding="utf-8",
        )

        result = self.run_setup()

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("project root cannot be used", result.stderr)
        self.assertFalse(self.plan.exists())

    def test_explicit_external_override_is_transient(self):
        external = Path(self.temporary.name) / "explicit external [feature]"
        feature_json = self.root / ".specify/feature.json"
        original_state = feature_json.read_bytes()

        result = self.run_setup(feature_directory=external, no_persist=False)

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(str(external), payload["FEATURE_DIR"])
        self.assertTrue((external / "plan.md").is_file())
        self.assertEqual(original_state, feature_json.read_bytes())

        next_run = self.run_setup(no_persist=False)

        self.assert_json_output(next_run)
        self.assertEqual(original_state, feature_json.read_bytes())

    def test_explicit_local_override_persists_relative_path(self):
        feature_json = self.root / ".specify/feature.json"

        result = self.run_setup(feature_directory=self.feature_dir, no_persist=False)

        self.assert_json_output(result)
        self.assertEqual(
            {"feature_directory": os.path.join("specs", "[team]")},
            json.loads(feature_json.read_text(encoding="utf-8")),
        )

    def test_explicit_local_override_honors_no_persist(self):
        feature_json = self.root / ".specify/feature.json"
        feature_json.write_text(
            json.dumps({"feature_directory": "specs/previous"}),
            encoding="utf-8",
        )
        original_state = feature_json.read_bytes()

        result = self.run_setup(feature_directory=self.feature_dir)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(self.feature_dir), json.loads(result.stdout)["FEATURE_DIR"])
        self.assertEqual(original_state, feature_json.read_bytes())

    def test_saved_junction_component_is_rejected_without_writes(self):
        link = self.root / "specs/redirected"
        link.parent.mkdir(parents=True)
        target = Path(self.temporary.name) / "junction target"
        target.mkdir()
        sentinel = target / "sentinel.txt"
        sentinel.write_bytes(b"junction target")
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if junction.returncode != 0:
            self.skipTest(f"Windows junction creation unavailable: {junction.stderr}")

        feature_json = self.root / ".specify/feature.json"
        original_state = feature_json.read_bytes()
        explicit_result = self.run_setup(
            feature_directory=link,
            no_persist=False,
        )
        self.assertEqual(0, explicit_result.returncode, explicit_result.stderr)
        self.assertEqual(str(link), json.loads(explicit_result.stdout)["FEATURE_DIR"])
        self.assertEqual(original_state, feature_json.read_bytes())
        plan_bytes = (target / "plan.md").read_bytes()

        feature_json.write_text(
            json.dumps({"feature_directory": "specs/redirected"}),
            encoding="utf-8",
        )
        original_state = feature_json.read_bytes()

        result = self.run_setup()

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("symbolic link or junction", result.stderr)
        self.assertEqual(original_state, feature_json.read_bytes())
        self.assertEqual(plan_bytes, (target / "plan.md").read_bytes())
        self.assertEqual([target / "plan.md", sentinel], sorted(target.iterdir()))

    def test_existing_plan_with_brackets_is_preserved(self):
        self.feature_dir.mkdir(parents=True)
        original = b"\xef\xbb\xbfuser-authored plan\r\nkeep exactly"
        self.plan.write_bytes(original)
        self.write_template("# Do not replace the existing plan.\n")

        result = self.run_setup()

        self.assert_json_output(result)
        self.assertEqual(original, self.plan.read_bytes())
        self.assertIn("Plan already exists", result.stderr)
        self.assertNotIn("Plan already exists", result.stdout)

    def test_fresh_bracketed_feature_gets_template_and_repeat_does_not_clobber(self):
        template = "# Actual override\nKeep λ unchanged.\n"
        self.write_template(template)

        first = self.run_setup()

        self.assert_json_output(first)
        self.assertEqual(template.encode("utf-8"), self.plan.read_bytes())
        self.assertIn("Copied plan template", first.stderr)

        second = self.run_setup()

        self.assert_json_output(second)
        self.assertEqual(template.encode("utf-8"), self.plan.read_bytes())
        self.assertIn("Plan already exists", second.stderr)
        self.assertEqual([self.plan], list(self.feature_dir.iterdir()))

    def test_missing_template_creates_empty_plan(self):
        result = self.run_setup()

        self.assert_json_output(result)
        self.assertEqual(b"", self.plan.read_bytes())
        self.assertIn("Warning: Plan template not found", result.stderr)

    def test_competing_creation_is_reported_without_overwrite(self):
        self.write_template()
        common = self.script_dir / COMMON.name
        with common.open("a", encoding="utf-8", newline="") as stream:
            stream.write(RACE_HOOK)

        result = self.run_setup(race_plan=self.plan)

        self.assert_json_output(result)
        self.assertEqual(b"competing plan", self.plan.read_bytes())
        self.assertIn("Plan already exists", result.stderr)
        self.assertNotIn("Copied plan template", result.stderr)
        self.assertEqual([self.plan], list(self.feature_dir.iterdir()))

    def test_non_file_plan_collision_propagates_io_error(self):
        self.feature_dir.mkdir(parents=True)
        self.plan.mkdir()
        self.write_template()

        result = self.run_setup()

        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertNotIn("Plan already exists", result.stderr)
        self.assertEqual([], list(self.feature_dir.glob(".plan.md.*.tmp")))


if __name__ == "__main__":
    unittest.main()
