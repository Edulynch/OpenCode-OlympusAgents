"""Focused Slice A checks; fixtures are prepared before every query snapshot."""

from __future__ import annotations

import importlib.util
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympus import source_edit


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


class SliceBLock(unittest.TestCase):
    _WORKER = r'''
import os
import sys
from pathlib import Path
from olympus import source_edit

source = Path(sys.argv[1])
route = sys.argv[2]
action = sys.argv[3]
inspection = Path(sys.argv[4]) if sys.argv[4] else None
lock = None
try:
    lock = source_edit._acquire_lock(source, create=(route == "edit"))
except source_edit.LockBusy:
    print("BUSY", flush=True)
    raise SystemExit(23)
except Exception as error:
    print("ERROR " + type(error).__name__, flush=True)
    raise SystemExit(24)

try:
    if route == "recover" and inspection is not None:
        inspection.write_text("inspected", encoding="utf-8")
    print("LOCKED", flush=True)
    if action == "hold":
        sys.stdin.readline()
    elif action == "raise":
        raise RuntimeError("fixture exception")
except RuntimeError:
    print("EXCEPTION", flush=True)
    raise SystemExit(17)
finally:
    if lock is not None:
        source_edit._release_lock(lock)
'''

    def setUp(self):
        temp_root = Path(tempfile.gettempdir())
        preferred_temp = temp_root / "opencode"
        if preferred_temp.is_dir():
            temp_root = preferred_temp
        self.temporary = tempfile.TemporaryDirectory(prefix="olympus-cli-lock espacio ñ-",
                                                     dir=temp_root)
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.source = self.sandbox / "origen canónico ñ"
        self.source.mkdir()
        self.environment = os.environ.copy()
        self.environment["PYTHONPATH"] = str(ROOT)
        self.environment["PYTHONDONTWRITEBYTECODE"] = "1"
        self.environment["PYTHONUTF8"] = "1"

    def _identity(self, path):
        metadata = path.stat()
        return metadata.st_dev, metadata.st_ino

    def _prepare_existing_lock(self, source):
        lock = source_edit._acquire_lock(source, create=True)
        identity = source_edit._lock_identity(lock)
        source_edit._release_lock(lock)
        return identity

    def _command(self, source, route, action, inspection=None):
        return [sys.executable, "-B", "-c", self._WORKER, str(source), route, action,
                str(inspection) if inspection is not None else ""]

    def _spawn_owner(self, source, route="edit", inspection=None):
        process = subprocess.Popen(self._command(source, route, "hold", inspection), cwd=ROOT,
                                   env=self.environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", bufsize=1)
        first_line = queue.Queue()
        reader = threading.Thread(target=lambda: first_line.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            line = first_line.get(timeout=15)
        except queue.Empty:
            process.kill()
            process.communicate(timeout=5)
            self.fail("Lock owner did not report acquisition within 15 seconds")
        if line.strip() != "LOCKED":
            stdout, stderr = process.communicate(timeout=5)
            self.fail(f"Lock owner failed: {line!r} {stdout!r} {stderr!r}")
        return process

    def _stop_owner(self, process):
        if process.poll() is None:
            process.stdin.write("release\n")
            process.stdin.flush()
            stdout, stderr = process.communicate(timeout=10)
        else:
            stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(0, process.returncode, (stdout, stderr))

    def _try_worker(self, source, route, inspection=None):
        return subprocess.run(self._command(source, route, "once", inspection), cwd=ROOT,
                              env=self.environment, capture_output=True, text=True,
                              encoding="utf-8", timeout=15, check=False)

    def test_slice_b_lock_creation_is_exclusive_empty_stable_and_private(self):
        path = self.source / ".olympus-cli-edit.lock"
        missing_recovery = self._try_worker(self.source, "recover")
        self.assertEqual(24, missing_recovery.returncode, missing_recovery.stdout + missing_recovery.stderr)
        self.assertFalse(path.exists(), "Recovery must not create a missing stable lock")

        lock = source_edit._acquire_lock(self.source, create=True)
        identity = source_edit._lock_identity(lock)
        self.assertFalse(os.get_inheritable(lock.descriptor))
        self.assertTrue(path.is_file())
        self.assertEqual(0, path.stat().st_size)
        source_edit._release_lock(lock)

        self.assertTrue(path.exists(), "Normal release must preserve the stable lock path")
        self.assertEqual(identity, self._identity(path))
        self.assertEqual(0, path.stat().st_size)
        stable_snapshot = helpers.snapshot_outputs({path})
        reopened = source_edit._acquire_lock(self.source, create=False)
        self.assertEqual(identity, source_edit._lock_identity(reopened))
        source_edit._release_lock(reopened)
        self.assertEqual(stable_snapshot, helpers.snapshot_outputs({path}))

    def test_slice_b_lock_aliases_resolve_to_one_canonical_lock(self):
        alias = self.source.parent / self.source.name / ".." / self.source.name
        lock = source_edit._acquire_lock(alias, create=True)
        try:
            self.assertEqual(self.source.resolve(), lock.path.parent)
            identity = source_edit._lock_identity(lock)
            with self.assertRaises(source_edit.LockBusy):
                source_edit._acquire_lock(self.source, create=False)
            self.assertEqual(identity, self._identity(self.source / ".olympus-cli-edit.lock"))
        finally:
            source_edit._release_lock(lock)

    def test_slice_b_lock_rejects_symlink_paths(self):
        link_target = self.sandbox / "external empty lock"
        link_target.touch()
        symlink = self.source / ".olympus-cli-edit.lock"
        try:
            os.symlink(link_target, symlink)
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"Host cannot create a file symlink for the safety fixture: {error}")
        with self.assertRaises(source_edit.LockError):
            source_edit._acquire_lock(self.source, create=False)
        symlink.unlink()

    def test_slice_b_lock_rejects_hardlink_paths(self):
        link_target = self.sandbox / "external empty lock"
        link_target.touch()
        hardlink = self.source / ".olympus-cli-edit.lock"
        try:
            os.link(link_target, hardlink)
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"Host cannot create a hard-link safety fixture: {error}")
        with self.assertRaises(source_edit.LockError):
            source_edit._acquire_lock(self.source, create=False)
        self.assertEqual(2, link_target.stat().st_nlink)

    def test_slice_b_lock_detects_identity_contradiction_and_path_substitution(self):
        lock = source_edit._acquire_lock(self.source, create=True)
        path = self.source / ".olympus-cli-edit.lock"
        identity = source_edit._lock_identity(lock)
        with self.assertRaises(source_edit.LockIdentityError):
            source_edit._lock_identity(lock, expected=(identity[0], identity[1] + 1))
        source_edit._release_lock(lock)

        replacement = self.source / "replacement"
        replacement.touch()
        replacement_identity = self._identity(replacement)
        os.replace(replacement, path)
        self.assertEqual(replacement_identity, self._identity(path))
        self.assertNotEqual(identity, replacement_identity)
        replacement_lock = source_edit._acquire_lock(self.source, create=False)
        try:
            with self.assertRaises(source_edit.LockIdentityError):
                source_edit._lock_identity(replacement_lock, expected=identity)
        finally:
            source_edit._release_lock(replacement_lock)
        self.assertTrue(path.exists(), "Identity failure must not unlink or recreate the substituted path")
        self.assertEqual(replacement_identity, self._identity(path))

    def test_slice_b_lock_edit_edit_contention_uses_kernel_locking(self):
        source = self.sandbox / "edit edit"
        source.mkdir()
        path = source / ".olympus-cli-edit.lock"
        owner = self._spawn_owner(source, "edit")
        try:
            identity = self._identity(path)
            self.assertEqual(0, path.stat().st_size)
            contender = self._try_worker(source, "edit")
            self.assertEqual(23, contender.returncode, contender.stdout + contender.stderr)
            self.assertEqual("BUSY", contender.stdout.strip())
            self.assertEqual(identity, self._identity(path))
            self.assertEqual(0, path.stat().st_size)
        finally:
            self._stop_owner(owner)

    def test_slice_b_lock_edit_recover_blocks_before_batch_inspection(self):
        source = self.sandbox / "edit recovery"
        source.mkdir()
        inspection = source / "batch inspection marker"
        owner = self._spawn_owner(source, "edit")
        try:
            identity = self._identity(source / ".olympus-cli-edit.lock")
            contender = self._try_worker(source, "recover", inspection)
            self.assertEqual(23, contender.returncode, contender.stdout + contender.stderr)
            self.assertEqual("BUSY", contender.stdout.strip())
            self.assertFalse(inspection.exists(), "Recovery inspected its batch before acquiring the active lock")
            self.assertEqual(identity, self._identity(source / ".olympus-cli-edit.lock"))
        finally:
            self._stop_owner(owner)

        recovered = self._try_worker(source, "recover", inspection)
        self.assertEqual(0, recovered.returncode, recovered.stdout + recovered.stderr)
        self.assertEqual("inspected", inspection.read_text(encoding="utf-8"))
        self.assertEqual(identity, self._identity(source / ".olympus-cli-edit.lock"))

    def test_slice_b_lock_recover_recover_contention(self):
        source = self.sandbox / "recovery recovery"
        source.mkdir()
        self._prepare_existing_lock(source)
        owner_inspection = source / "owner inspection marker"
        contender_inspection = source / "contender inspection marker"
        owner = self._spawn_owner(source, "recover", owner_inspection)
        try:
            identity = self._identity(source / ".olympus-cli-edit.lock")
            self.assertEqual("inspected", owner_inspection.read_text(encoding="utf-8"))
            contender = self._try_worker(source, "recover", contender_inspection)
            self.assertEqual(23, contender.returncode, contender.stdout + contender.stderr)
            self.assertEqual("BUSY", contender.stdout.strip())
            self.assertFalse(contender_inspection.exists())
            self.assertEqual(identity, self._identity(source / ".olympus-cli-edit.lock"))
        finally:
            self._stop_owner(owner)

    def test_slice_b_lock_releases_after_python_exception(self):
        path = self.source / ".olympus-cli-edit.lock"
        lock = source_edit._acquire_lock(self.source, create=True)
        identity = source_edit._lock_identity(lock)
        with self.assertRaisesRegex(ValueError, "fixture exception"):
            try:
                raise ValueError("fixture exception")
            finally:
                source_edit._release_lock(lock)
        self.assertTrue(path.exists())
        self.assertEqual(identity, self._identity(path))
        following = source_edit._acquire_lock(self.source, create=False)
        self.assertEqual(identity, source_edit._lock_identity(following))
        source_edit._release_lock(following)

    def test_slice_b_lock_releases_after_abrupt_process_termination(self):
        source = self.sandbox / "abrupt termination"
        source.mkdir()
        path = source / ".olympus-cli-edit.lock"
        owner = self._spawn_owner(source, "edit")
        identity = self._identity(path)
        owner.kill()
        owner.wait(timeout=10)
        owner.stdout.close()
        owner.stderr.close()
        owner.stdin.close()
        self.assertNotEqual(0, owner.returncode, "Owner must be terminated rather than normally releasing")
        self.assertEqual(identity, self._identity(path))

        following = source_edit._acquire_lock(source, create=False)
        self.assertEqual(identity, source_edit._lock_identity(following))
        self.assertEqual(0, path.stat().st_size)
        source_edit._release_lock(following)
        self.assertEqual(identity, self._identity(path))


if __name__ == "__main__":
    unittest.main()
