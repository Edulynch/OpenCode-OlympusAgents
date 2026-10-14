"""Focused Slice A checks; fixtures are prepared before every query snapshot."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Import only helpers: neither qualification main nor its broad suite is run.
helpers = load_file("core_snapshot_helpers", ROOT / "tests/harness-core/qualify.py")


class SliceA(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="olympus-cli-a-")
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.source = self.sandbox / "source espacio ñ"
        self.target = self.sandbox / "target espacio ñ"
        self.target.mkdir()
        # A simulated worktree marker is sufficient for metadata-only status.
        (self.target / ".git").mkdir()
        shutil.copytree(ROOT / "olympus", self.source / "olympus",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (self.source / "scripts").mkdir()
        for name in ("render_harnesses.py", "olympus_cli.py", "olympus", "olympus.cmd"):
            shutil.copy2(ROOT / "scripts" / name, self.source / "scripts" / name)
        shutil.copy2(ROOT / "install.ps1", self.source / "install.ps1")
        self.renderer = load_file("fixture_renderer", self.source / "scripts/render_harnesses.py")
        self.outputs = self.renderer.outputs_for(self.source, "all")
        for path, content in self.outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        self.env = os.environ.copy()
        self.env.pop("PYTHONPATH", None)
        for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME",
                    "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "CODEX_HOME",
                    "OPENCODE_CONFIG_DIR", "TMP", "TEMP", "TMPDIR"):
            directory = self.sandbox / key.lower()
            directory.mkdir()
            (directory / "sentinel.txt").write_text("preserve", encoding="utf-8")
            self.env[key] = str(directory)
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.env["PYTHONUTF8"] = "1"
        self.env["OLYMPUS_PYTHON"] = sys.executable

    def snapshot(self):
        paths = set(self.sandbox.rglob("*"))
        return ({path.relative_to(self.sandbox).as_posix(): ("file" if path.is_file() else "directory", path.stat().st_mode)
                 for path in paths}, helpers.snapshot_outputs({path for path in paths if path.is_file()}))

    def query(self, *arguments: str, entry="module"):
        environment = self.env.copy()
        if entry == "module":
            command = [sys.executable, "-B", "-m", "olympus", *arguments]
            cwd = self.source
        elif entry == "module_external":
            # Explicit trusted import context, never code discovered in the target.
            environment["PYTHONPATH"] = str(self.source)
            command = [sys.executable, "-B", "-m", "olympus", *arguments]
            cwd = self.target
        elif entry == "python_launcher":
            command = [sys.executable, "-B", str(self.source / "scripts/olympus_cli.py"), *arguments]
            cwd = self.target
        elif entry == "windows_launcher":
            # /d disables personal cmd AutoRun. All arguments are controlled fixtures.
            batch = subprocess.list2cmdline([str(self.source / "scripts/olympus.cmd"), *arguments])
            command = f'"{environment["COMSPEC"]}" /d /s /c "{batch}"'
            cwd = self.target
        else:
            command = [str(self.source / "scripts/olympus"), *arguments]
            cwd = self.target
        before = self.snapshot()
        try:
            return subprocess.run(command, cwd=cwd, env=environment, capture_output=True,
                                  text=True, encoding="utf-8", check=False, timeout=20)
        finally:
            self.assertEqual(before, self.snapshot(), "Read-only command changed files, directories, hashes or mtimes")

    def json_query(self, *arguments: str, code=0, entry="module"):
        result = self.query(*arguments, "--json", entry=entry)
        self.assertEqual(code, result.returncode, (result.stdout, result.stderr))
        self.assertNotIn("Traceback", result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual({"schema_version", "operation", "result", "context", "data", "issues"}, set(response))
        self.assertEqual(1, response["schema_version"])
        self.assertIsInstance(response["issues"], list)
        return response

    def write_manifest(self, harnesses=None, **changes):
        harnesses = ["codex"] if harnesses is None else harnesses
        folder = ".opencode" if "opencode" in harnesses else ".codex"
        path = self.target / folder / "orchestrator-install.json"
        path.parent.mkdir(exist_ok=True)
        data = {"schema_version": 1, "scope": "project", "installed_harnesses": harnesses,
                "installed_version": "v0.4.9", "installed_from_commit": "unknown", "managed_files": []}
        data.update(changes)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_slice_a_help_version(self):
        help_result = self.query("--help")
        self.assertEqual(0, help_result.returncode)
        for text in ("--source", "models list --json", "config check", "status --scope project", "Python 3.11+"):
            self.assertIn(text, help_result.stdout)
        for command in ("set-family", "set-model", "recover", "apply", "doctor", "uninstall"):
            self.assertNotIn(command, help_result.stdout)
        version = self.query("--version")
        self.assertEqual(0, version.returncode)
        self.assertIn("olympus v0.4.9", version.stdout)
        self.assertIn(str(self.source), version.stdout)

    def test_slice_a_models_human_json_canonical_assignments(self):
        response = self.json_query("models", "list")
        self.assertEqual("models list", response["operation"])
        self.assertEqual("ok", response["result"])
        rows = response["data"]["roles"]
        self.assertEqual(12, len(rows))
        with (self.source / "olympus/core/models.toml").open("rb") as stream:
            models = tomllib.load(stream)
        human = self.query("models", "list")
        self.assertEqual(0, human.returncode)
        self.assertEqual(set(models["roles"]), {row["role"] for row in rows})
        for row in rows:
            intent = models["roles"][row["role"]]
            self.assertEqual(intent["family"], row["family"])
            self.assertEqual(intent["effort"], row["effort"])
            self.assertEqual(models["families"][intent["family"]], row["models"])
            for value in (row["role"], row["identity"], row["family"], row["effort"], *row["models"].values()):
                self.assertIn(value, human.stdout)
        by_role = {row["role"]: row for row in rows}
        self.assertEqual("root", by_role["kael"]["representation"]["codex"])
        self.assertEqual("absent", by_role["aegis"]["representation"]["codex"])
        self.assertEqual(10, sum(row["representation"]["codex"] == "agent" for row in rows))

    def test_slice_a_check_renderer_interface_and_human_json(self):
        for harness in ("all", "opencode", "codex"):
            with self.subTest(harness=harness):
                response = self.json_query("config", "check", "--harness", harness)
                self.assertTrue(response["data"]["coherent"])
                self.assertEqual(len(self.renderer.outputs_for(self.source, harness)), response["data"]["managed_outputs"])
                human = self.query("config", "check", "--harness", harness)
                self.assertEqual(0, human.returncode)
                for key, value in response["data"].items():
                    self.assertIn(f"{key}: {json.dumps(value, ensure_ascii=False)}", human.stdout)
                self.assertEqual("unknown", response["data"]["model_availability"])
                self.assertEqual("not_performed", response["data"]["installation_verification"])

    def test_slice_a_invalid_arguments_and_unavailable_commands(self):
        for arguments in (("models", "missing"), ("models", "set-family", "sol"),
                          ("agents", "set-model", "kael"), ("config", "recover"),
                          ("config", "apply"), ("doctor",), ("install",), ("uninstall",),
                          ("config", "check", "--harness", "invalid"), ("models", "list", "--force"),
                          ("--source", "relative", "models", "list"),
                          ("models", "list", "--source", str(self.source)),
                          ("--version", "models", "list"), ("config",)):
            with self.subTest(arguments=arguments):
                response = self.json_query(*arguments, code=2)
                self.assertEqual("failed", response["result"])
                self.assertTrue(response["issues"])
        human = self.query("models", "list", "--bad")
        self.assertEqual(2, human.returncode)
        self.assertIn("--help", human.stderr)
        self.assertEqual(2, self.query().returncode)

    def test_slice_a_invalid_source(self):
        response = self.json_query("--source", str(self.sandbox / "missing"), "models", "list", code=2)
        self.assertIn("Invalid source", response["issues"][0]["message"])

    def test_slice_a_malformed_toml(self):
        path = self.source / "olympus/core/models.toml"
        path.write_text("[malformed", encoding="utf-8")
        for arguments in (("models", "list"), ("config", "check")):
            response = self.json_query(*arguments, code=1)
            self.assertIn("models.toml", response["issues"][0]["message"])

    def test_slice_a_invalid_source_structure(self):
        (self.source / "olympus/core/models.toml").write_text('roles = "invalid"\n', encoding="utf-8")
        response = self.json_query("models", "list", code=1)
        self.assertEqual("failed", response["result"])

    def test_slice_a_roster_mismatch(self):
        (self.source / "olympus/roles/veyra.md").unlink()
        response = self.json_query("config", "check", code=1)
        self.assertIn("roster", response["issues"][0]["message"])

    def test_slice_a_output_drift_and_missing(self):
        path = self.source / ".codex/agents/veyra.toml"
        path.write_text("fixture drift", encoding="utf-8")
        response = self.json_query("config", "check", "--harness", "codex", code=1)
        self.assertEqual("drift", response["issues"][0]["code"])
        path.unlink()
        response = self.json_query("config", "check", "--harness", "codex", code=1)
        self.assertEqual("missing", response["issues"][0]["code"])
        # Harness selection must not treat unrelated Codex drift as OpenCode drift.
        self.assertEqual("ok", self.json_query("config", "check", "--harness", "opencode")["result"])

    def test_slice_a_status_absent_and_human_json(self):
        arguments = ("status", "--target", str(self.target))
        response = self.json_query(*arguments)
        self.assertEqual("absent", response["result"])
        self.assertEqual([], response["data"]["installed_harnesses"])
        human = self.query(*arguments)
        self.assertEqual(0, human.returncode)
        for key, value in response["data"].items():
            self.assertIn(f"{key}: {json.dumps(value, ensure_ascii=False)}", human.stdout)

    def test_slice_a_status_reported_never_verified(self):
        self.write_manifest(["opencode", "codex"])
        arguments = ("status", "--target", str(self.target), "--harness", "codex")
        response = self.json_query(*arguments)
        self.assertEqual(["opencode", "codex"], response["data"]["installed_harnesses"])
        self.assertEqual("v0.4.9", response["data"]["recorded_version"])
        self.assertEqual("unverified", response["data"]["integrity"])
        self.assertEqual("unverified", response["data"]["ownership"])
        self.assertEqual("unknown", response["data"]["assignments"])
        human = self.query(*arguments)
        for key, value in response["data"].items():
            self.assertIn(f"{key}: {json.dumps(value, ensure_ascii=False)}", human.stdout)

    def test_slice_a_status_invalid_metadata(self):
        path = self.write_manifest()
        for value in ("{broken", "[]", json.dumps({"schema_version": 2, "managed_files": []}),
                      json.dumps({"schema_version": 1, "managed_files": [], "installed_harnesses": []})):
            with self.subTest(value=value):
                path.write_text(value, encoding="utf-8")
                response = self.json_query("status", "--target", str(self.target), code=1)
                self.assertEqual("failed", response["result"])
                self.assertEqual("invalid", response["data"]["installation_state"])

    def test_slice_a_status_contradictory_manifests(self):
        self.write_manifest(["opencode"])
        self.write_manifest(["codex"])
        response = self.json_query("status", "--target", str(self.target), code=3)
        self.assertEqual("blocked", response["result"])
        self.assertEqual("contradictory", response["data"]["installation_state"])

    def test_slice_a_status_legacy_and_selected_absent(self):
        path = self.write_manifest(["opencode"])
        data = json.loads(path.read_text(encoding="utf-8"))
        del data["installed_harnesses"]
        del data["installed_version"]
        path.write_text(json.dumps(data), encoding="utf-8")
        response = self.json_query("status", "--target", str(self.target), "--harness", "codex")
        self.assertEqual("absent", response["result"])
        self.assertEqual("legacy", response["data"]["metadata_format"])
        self.assertEqual("unknown", response["data"]["recorded_version"])

    def test_slice_a_status_context_and_global_block(self):
        for arguments in (("status",), ("status", "--target", "relative"),
                          ("status", "--target", str(self.source)),
                          ("status", "--scope", "global", "--target", str(self.target))):
            with self.subTest(arguments=arguments):
                self.json_query(*arguments, code=2)
        response = self.json_query("status", "--scope", "global", code=3)
        self.assertEqual("blocked", response["result"])
        self.assertEqual("unknown", response["context"]["target"])

    def test_slice_a_pending_scratch_is_reported_not_repaired(self):
        scratch = self.source / ".olympus-cli-edit"
        scratch.mkdir()
        (scratch / "unconfirmed.txt").write_text("unrelated pending state", encoding="utf-8")
        response = self.json_query("models", "list")
        self.assertIn("unconfirmed", response["context"]["source_edit"])

    def test_slice_a_explicit_source_and_python_launcher(self):
        response = self.json_query("--source", str(self.source), "models", "list", entry="python_launcher")
        self.assertEqual(str(self.source), response["context"]["source"])
        response = self.json_query("models", "list", entry="python_launcher")
        self.assertEqual(str(self.source), response["context"]["source"])
        self.json_query("models", "bad", code=2, entry="python_launcher")

    def smoke_entry(self, entry):
        self.assertGreaterEqual(sys.version_info, (3, 11))
        for arguments, expected in ((("--help",), "models list --json"), (("--version",), "olympus v0.4.9")):
            result = self.query(*arguments, entry=entry)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn(expected, result.stdout)
        for arguments in (("models", "list"), ("config", "check"),
                          ("status", "--scope", "project", "--target", str(self.target))):
            with self.subTest(entry=entry, arguments=arguments):
                response = self.json_query("--source", str(self.source), *arguments, entry=entry)
                self.assertEqual(str(self.source), response["context"]["source"])
                human = self.query("--source", str(self.source), *arguments, entry=entry)
                self.assertEqual(0, human.returncode, human.stderr)
                self.assertIn(str(self.source), human.stdout)
                if arguments[0] == "models":
                    self.assertEqual(12, len(response["data"]["roles"]))
                    for row in response["data"]["roles"]:
                        for value in (row["identity"], row["family"], row["effort"], *row["models"].values()):
                            self.assertIn(value, human.stdout)
                else:
                    for key, value in response["data"].items():
                        self.assertIn(f"{key}: {json.dumps(value, ensure_ascii=False)}", human.stdout)
                if arguments[0] == "status":
                    self.assertEqual(str(self.target), response["context"]["target"])
                    self.assertEqual("absent", response["result"])
        # The launcher's default source must remain its checkout even from target cwd.
        self.assertEqual(str(self.source), self.json_query("models", "list", entry=entry)["context"]["source"])
        self.json_query("models", "bad", code=2, entry=entry)
        self.json_query("status", "--scope", "global", code=3, entry=entry)
        # Fixture drift prepared outside the snapshot window; verify exit propagation.
        (self.source / ".codex/agents/veyra.toml").write_text("fixture drift", encoding="utf-8")
        self.json_query("config", "check", "--harness", "codex", code=1, entry=entry)

    def test_slice_a_module_external_context(self):
        self.smoke_entry("module_external")

    @unittest.skipUnless(os.name == "nt", "Native .cmd execution requires Windows")
    def test_slice_a_windows_native_launcher(self):
        self.smoke_entry("windows_launcher")

    @unittest.skipUnless(os.name == "posix", "Native POSIX execution requires Linux CI evidence")
    def test_slice_a_posix_launcher(self):
        self.assertTrue(os.access(ROOT / "scripts/olympus", os.X_OK), "Prepare the checkout launcher executable before tests")
        self.assertTrue(os.access(self.source / "scripts/olympus", os.X_OK))
        self.smoke_entry("posix_launcher")


if __name__ == "__main__":
    unittest.main()
