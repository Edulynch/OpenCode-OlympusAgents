"""Focused Slice A checks; fixtures are prepared before every query snapshot."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import queue
import shutil
import stat
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
from olympus.cli import release_version


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
        self.source_version = release_version(self.source)
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
        for command in ("models set-family", "agents set-model", "config recover"):
            self.assertIn(command, help_result.stdout)
        for command in ("config apply", "doctor", "install", "uninstall"):
            self.assertNotRegex(help_result.stdout, rf"\b{command}\b")
        version = self.query("--version")
        self.assertEqual(0, version.returncode)
        self.assertIn(f"olympus {self.source_version}", version.stdout)
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
        for arguments, expected in ((("--help",), "models list --json"),
                                    (("--version",), f"olympus {self.source_version}")):
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


class SliceBModelEdit(unittest.TestCase):
    def setUp(self):
        temp_root = Path(tempfile.gettempdir())
        preferred_temp = temp_root / "opencode"
        if preferred_temp.is_dir():
            temp_root = preferred_temp
        self.temporary = tempfile.TemporaryDirectory(prefix="olympus-cli-model espacio ñ-",
                                                     dir=temp_root)
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.source = self.sandbox / "source fixture ñ"
        shutil.copytree(ROOT / "olympus", self.source / "olympus",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        scripts = self.source / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts/render_harnesses.py", scripts / "render_harnesses.py")
        self.renderer = load_file("slice_b_fixture_renderer", scripts / "render_harnesses.py")
        initial_outputs = self.renderer.outputs_for(self.source, "all")
        for path, content in initial_outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))

    def model_edit(self):
        # Do not import TOML Kit at test-module import time; lock/A tests stay stdlib-only.
        from olympus import model_edit
        return model_edit

    def snapshot(self):
        paths = set(self.source.rglob("*"))
        inventory = {
            path.relative_to(self.source).as_posix():
            ("directory" if path.is_dir() else "file", path.stat().st_mode,
             path.stat().st_size, path.stat().st_mtime_ns)
            for path in paths
        }
        files = {path for path in paths if path.is_file()}
        return inventory, helpers.snapshot_outputs(files)

    def rendered_candidate_outputs(self, candidate):
        model_file = next(item for item in candidate.files
                          if item.relative_path == "olympus/core/models.toml")
        models, policies, capabilities, identities, roles = self.renderer.checked_sources(self.source)
        candidate_models = tomllib.loads(model_file.new_bytes.decode("utf-8"))
        outputs = self.renderer.opencode_outputs(self.source, candidate_models, policies, identities, roles)
        outputs.update(self.renderer.codex_outputs(self.source, candidate_models, policies, identities, roles))
        outputs[self.source / "docs/HARNESS-CAPABILITIES.md"] = self.renderer.capability_doc(capabilities)
        return outputs

    def assert_preview_matches_renderer(self, candidate):
        model_file = next(item for item in candidate.files
                          if item.relative_path == "olympus/core/models.toml")
        rendered = self.rendered_candidate_outputs(candidate)
        expected = {"olympus/core/models.toml"} if model_file.new_bytes != model_file.old_bytes else set()
        for path, content in rendered.items():
            expected_bytes = content.encode("utf-8")
            if expected_bytes != path.read_bytes():
                expected.add(path.relative_to(self.source).as_posix())
        self.assertEqual(expected, set(candidate.preview["data"]["write_set"]))
        self.assertEqual(expected, {item.relative_path for item in candidate.files})
        by_path = {item.relative_path: item for item in candidate.files}
        for path, content in rendered.items():
            relative = path.relative_to(self.source).as_posix()
            if relative in by_path:
                self.assertEqual(content.encode("utf-8"), by_path[relative].new_bytes)

    def test_slice_b_tomlkit_import_is_lazy_and_missing_dependency_blocks(self):
        result = subprocess.run(
            [sys.executable, "-B", "-c",
             "import sys; from olympus import model_edit; print('tomlkit' in sys.modules)"],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, encoding="utf-8", check=False, timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("False", result.stdout.strip())

        model_edit = self.model_edit()
        before = self.snapshot()
        from unittest.mock import patch
        with patch.object(model_edit.importlib, "import_module", side_effect=ImportError("fixture absent")):
            with self.assertRaisesRegex(model_edit.ModelEditError, "tomlkit==0.13.3"):
                model_edit._build_set_family_candidate(self.source, "sol", "new-sol", "new-codex")
        self.assertEqual(before, self.snapshot(), "Missing optional dependency must not mutate the fixture")
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_toml_round_trip_preserves_bytes_newlines_and_final_newline(self):
        model_edit = self.model_edit()
        source = (self.source / "olympus/core/models.toml").read_bytes()
        lf = source.replace(b"\r\n", b"\n")
        variants = {
            "lf": lf,
            "crlf": lf.replace(b"\n", b"\r\n"),
            "no_final_newline": lf.rstrip(b"\n"),
        }
        for label, raw in variants.items():
            with self.subTest(label=label):
                candidate = model_edit._prepare_toml_candidate(
                    raw, {("families", "sol", "opencode"): "openai/new-sol"}
                )
                self.assertEqual(raw, candidate.old_bytes)
                self.assertEqual("openai/new-sol", tomllib.loads(candidate.new_bytes.decode("utf-8"))
                                 ["families"]["sol"]["opencode"])
                if label == "crlf":
                    self.assertEqual(0, candidate.new_bytes.replace(b"\r\n", b"").count(b"\n"))
                    self.assertTrue(candidate.new_bytes.endswith(b"\r\n"))
                elif label == "lf":
                    self.assertNotIn(b"\r", candidate.new_bytes)
                    self.assertTrue(candidate.new_bytes.endswith(b"\n"))
                else:
                    self.assertFalse(candidate.new_bytes.endswith(b"\n"))

    def test_slice_b_toml_preserves_comments_order_quoted_dotted_inline_and_string_style(self):
        model_edit = self.model_edit()
        raw = (
            b"# unrelated target text: families.sol.opencode = 'fake-id'\n"
            b"families.\"sol\".opencode = 'old-opencode' # preserve comment\n"
            b"families.sol.codex = \"\"\"old-codex\"\"\"\n"
            b"families.luna = { opencode = 'openai/luna', codex = \"gpt-luna\" }\n"
            b"note = \"opencode = 'not-a-target'\"\n"
            b"[roles.\"kael\"]\n"
            b"family = 'sol'\n"
            b"effort = \"\"\"high\"\"\"\n"
            b"[roles.veyra]\n"
            b"family = 'luna'\n"
            b"effort = 'max'"
        )
        candidate = model_edit._prepare_toml_candidate(raw, {
            ("families", "sol", "opencode"): "new-opencode",
            ("families", "sol", "codex"): "new-codex",
            ("families", "luna", "opencode"): "openai/new-luna",
            ("roles", "kael", "effort"): "max",
        })
        self.assertEqual(b"families.\"sol\".opencode = 'new-opencode' # preserve comment\n",
                         next(line for line in candidate.new_bytes.splitlines(keepends=True)
                              if line.startswith(b'families."sol".opencode')))
        self.assertIn(b'families.sol.codex = """new-codex"""\n', candidate.new_bytes)
        self.assertIn(b"families.luna = { opencode = 'openai/new-luna', codex = \"gpt-luna\" }\n",
                      candidate.new_bytes)
        self.assertIn(b"note = \"opencode = 'not-a-target'\"\n", candidate.new_bytes)
        self.assertIn(b'effort = """max"""\n', candidate.new_bytes)
        self.assertEqual("max", tomllib.loads(candidate.new_bytes.decode("utf-8"))["roles"]["kael"]["effort"])

    def test_slice_b_ids_require_full_ascii_identifier_match(self):
        model_edit = self.model_edit()
        for valid in ("openai/gpt-6.1-sol", "gpt-6-luna", "A1._:/-Z"):
            with self.subTest(valid=valid):
                self.assertEqual(valid, model_edit._validate_id(valid, "fixture ID"))
        for invalid in ("", " starts-with-space", "ends-with-space ", "has space", "quote'", "quote\"",
                        "back\\slash", "line\nbreak", "trailing-newline\n", "hash#", "brace{", "tab\t", "éclair"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(model_edit.ModelEditError):
                    model_edit._validate_id(invalid, "fixture ID")
        with self.assertRaises(model_edit.ModelEditError):
            model_edit._prepare_toml_candidate(
                (self.source / "olympus/core/models.toml").read_bytes(),
                {("families", "sol", "opencode"): "bad ID"},
            )

    def test_slice_b_toml_rejects_mixed_malformed_incompatible_and_unauthorized_edits(self):
        model_edit = self.model_edit()
        baseline = (self.source / "olympus/core/models.toml").read_bytes()
        normalized = baseline.replace(b"\r\n", b"\n")
        mixed = normalized.replace(b"\n", b"\r\n", 1)
        with self.assertRaisesRegex(model_edit.ModelEditError, "Mixed LF/CRLF"):
            model_edit._prepare_toml_candidate(mixed, {("families", "sol", "opencode"): "new-id"})
        invalid_effort = baseline.replace(b'effort = "high"', b'effort = "bad\\nvalue"', 1)
        for raw in (b"[families\n", baseline.replace(b"openai/gpt-6.1-sol", b"invalid id", 1), invalid_effort):
            with self.subTest(raw=raw[:24]):
                with self.assertRaises(model_edit.ModelEditError):
                    model_edit._prepare_toml_candidate(raw, {("families", "sol", "codex"): "new-codex"})
        for updates in (
            {("identities", "kael", "display"): "New identity"},
            {("families", "sol", "opencode"): 42},
            {("roles", "unknown", "effort"): "high"},
            {("roles", "kael", "effort"): "vendor-invented"},
        ):
            with self.subTest(updates=updates):
                with self.assertRaises(model_edit.ModelEditError):
                    model_edit._prepare_toml_candidate(baseline, updates)

    def test_slice_b_family_candidate_identifies_all_roles_and_exact_renderer_outputs(self):
        model_edit = self.model_edit()
        before = self.snapshot()
        candidate = model_edit._build_set_family_candidate(
            self.source, "sol", "openai/sol-next", "codex-sol-next"
        )
        self.assertEqual(before, self.snapshot(), "Preview must be completely in memory")
        self.assertEqual(["argus", "atlas", "helios", "kael", "talos", "thales"],
                         candidate.preview["data"]["affected_roles"])
        self.assertEqual("openai/gpt-6.1-sol", candidate.preview["data"]["roles"][0]
                         ["models"]["opencode"]["old"])
        rows = {row["role"]: row for row in candidate.preview["data"]["roles"]}
        self.assertEqual("root", rows["kael"]["representation"]["codex"])
        self.assertNotIn("aegis", rows)
        self.assertEqual("openai/sol-next", rows["kael"]["models"]["opencode"]["new"])
        self.assertEqual("codex-sol-next", rows["kael"]["models"]["codex"]["new"])
        self.assertEqual(1, candidate.preview["schema_version"])
        self.assertEqual(candidate.preview, json.loads(json.dumps(candidate.preview, ensure_ascii=False)))
        human = model_edit._format_preview_human(candidate.preview)
        for row in rows.values():
            for field in ("family", "effort"):
                self.assertIn(row[field]["old"], human)
                self.assertIn(row[field]["new"], human)
            for runtime in ("opencode", "codex"):
                self.assertIn(row["models"][runtime]["old"], human)
                self.assertIn(row["models"][runtime]["new"], human)
        self.assert_preview_matches_renderer(candidate)
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_specialist_candidate_preserves_other_roles_and_outputs(self):
        model_edit = self.model_edit()
        before = self.snapshot()
        candidate = model_edit._build_set_role_candidate(self.source, "veyra", family="sol", effort="high")
        self.assertEqual(before, self.snapshot())
        self.assertEqual(["veyra"], candidate.preview["data"]["affected_roles"])
        model_file = next(item for item in candidate.files if item.relative_path == "olympus/core/models.toml")
        old = tomllib.loads(model_file.old_bytes.decode("utf-8"))
        new = tomllib.loads(model_file.new_bytes.decode("utf-8"))
        self.assertEqual("sol", new["roles"]["veyra"]["family"])
        self.assertEqual("high", new["roles"]["veyra"]["effort"])
        for role in set(old["roles"]) - {"veyra"}:
            self.assertEqual(old["roles"][role], new["roles"][role])
        self.assertEqual({"olympus/core/models.toml", ".opencode/agents/veyra.md", ".codex/agents/veyra.toml"},
                         set(candidate.preview["data"]["write_set"]))
        self.assert_preview_matches_renderer(candidate)

    def test_slice_b_effort_only_candidate_changes_one_role_and_is_renderer_exact(self):
        model_edit = self.model_edit()
        candidate = model_edit._build_set_role_candidate(self.source, "thales", effort="high")
        self.assertEqual(["thales"], candidate.preview["data"]["affected_roles"])
        row = candidate.preview["data"]["roles"][0]
        self.assertEqual({"old": "xhigh", "new": "high"}, row["effort"])
        self.assertEqual(row["models"]["opencode"]["old"], row["models"]["opencode"]["new"])
        self.assertEqual(row["models"]["codex"]["old"], row["models"]["codex"]["new"])
        self.assert_preview_matches_renderer(candidate)

    def test_slice_b_kael_root_and_aegis_codex_absence_are_preserved(self):
        model_edit = self.model_edit()
        kael = model_edit._build_set_role_candidate(self.source, "kael", family="luna", effort="max")
        kael_row = kael.preview["data"]["roles"][0]
        self.assertEqual("root", kael_row["representation"]["codex"])
        self.assertNotIn(".codex/agents/kael.toml", kael.preview["data"]["write_set"])
        self.assertNotIn("CODEX.md", kael.preview["data"]["write_set"])
        self.assert_preview_matches_renderer(kael)

        aegis = model_edit._build_set_role_candidate(self.source, "aegis", family="sol", effort="high")
        aegis_row = aegis.preview["data"]["roles"][0]
        self.assertEqual("absent", aegis_row["representation"]["codex"])
        self.assertNotIn(".codex/agents/aegis.toml", aegis.preview["data"]["write_set"])
        self.assert_preview_matches_renderer(aegis)

    def test_slice_b_noop_has_no_files_lock_scratch_or_source_mutations(self):
        model_edit = self.model_edit()
        before = self.snapshot()
        family = model_edit._build_set_family_candidate(self.source, "sol", "openai/gpt-6.1-sol", "gpt-6.1-sol")
        role = model_edit._build_set_role_candidate(self.source, "veyra", family="luna", effort="max")
        self.assertTrue(family.preview["data"]["no_op"])
        self.assertEqual("no_changes", family.preview["result"])
        self.assertEqual([], family.preview["data"]["write_set"])
        self.assertEqual((), family.files)
        self.assertEqual("no_changes", role.preview["result"])
        self.assertEqual([], role.preview["data"]["write_set"])
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_candidate_rejects_drift_missing_and_mixed_newline_outputs(self):
        model_edit = self.model_edit()
        drift = self.source / ".codex/agents/veyra.toml"
        original = drift.read_bytes()
        drift.write_bytes(original + b"# drift\n")
        with self.assertRaisesRegex(model_edit.ModelEditError, "drift"):
            model_edit._build_set_family_candidate(self.source, "sol", "openai/new-sol", "new-codex")
        drift.write_bytes(original)

        drift.unlink()
        with self.assertRaisesRegex(model_edit.ModelEditError, "Missing renderer resource"):
            model_edit._build_set_family_candidate(self.source, "sol", "openai/new-sol", "new-codex")
        drift.write_bytes(original)

        drift.write_bytes(original.replace(b"\n", b"\r\n", 1))
        with self.assertRaisesRegex(model_edit.ModelEditError, "Mixed LF/CRLF"):
            model_edit._build_set_family_candidate(self.source, "sol", "openai/new-sol", "new-codex")

    def test_slice_b_candidate_rejects_linked_outputs(self):
        model_edit = self.model_edit()
        output = self.source / ".codex/agents/veyra.toml"
        link_target = self.sandbox / "linked-output-target"
        link_target.write_bytes(output.read_bytes())
        output.unlink()
        try:
            os.link(link_target, output)
        except (NotImplementedError, OSError) as error:
            output.write_bytes(link_target.read_bytes())
            self.skipTest(f"Host cannot create a hard-link safety fixture: {error}")
        with self.assertRaisesRegex(model_edit.ModelEditError, "Hard-linked"):
            model_edit._build_set_family_candidate(self.source, "sol", "openai/new-sol", "new-codex")

    def test_slice_b_candidate_rejects_symlinked_outputs(self):
        model_edit = self.model_edit()
        output = self.source / ".codex/agents/veyra.toml"
        link_target = self.sandbox / "symlink-output-target"
        link_target.write_bytes(output.read_bytes())
        output.unlink()
        try:
            os.symlink(link_target, output)
        except (NotImplementedError, OSError) as error:
            output.write_bytes(link_target.read_bytes())
            self.skipTest(f"Host cannot create a symlink safety fixture: {error}")
        with self.assertRaisesRegex(model_edit.ModelEditError, "Linked/reparse"):
            model_edit._build_set_family_candidate(self.source, "sol", "openai/new-sol", "new-codex")

    def _snapshot_without_batch_control(self):
        inventory, contents = self.snapshot()
        inventory = {
            relative: value for relative, value in inventory.items()
            if relative != ".olympus-cli-edit.lock"
            and relative != ".olympus-cli-edit"
            and not relative.startswith(".olympus-cli-edit/")
        }
        contents = {
            path: value for path, value in contents.items()
            if path.name != ".olympus-cli-edit.lock"
            and self._relative_from(path, self.source) != ".olympus-cli-edit"
            and not self._relative_from(path, self.source).startswith(".olympus-cli-edit/")
        }
        return inventory, contents

    def _snapshot_outside_targets(self, candidate):
        inventory, contents = self._snapshot_without_batch_control()
        targets = {item.relative_path for item in candidate.files}
        changed_parent_directories = set()
        for target in targets:
            parent = Path(target).parent
            while parent != Path("."):
                changed_parent_directories.add(parent.as_posix())
                parent = parent.parent
        inventory = {
            path: ((value[0], value[1], value[2], None)
                   if path in changed_parent_directories and value[0] == "directory" else value)
            for path, value in inventory.items() if path not in targets
        }
        contents = {
            path: value for path, value in contents.items()
            if self._relative_from(path, self.source) not in targets
        }
        return inventory, contents

    def _relative_from(self, path, root):
        return path.relative_to(root).as_posix()

    def test_slice_b_batch_persists_prepared_record_backups_and_staging_only(self):
        model_edit = self.model_edit()
        candidate = model_edit._build_set_family_candidate(
            self.source, "sol", "openai/sol-batch", "codex-sol-batch"
        )
        before = self._snapshot_without_batch_control()
        original_targets = {
            item.relative_path: (item.old_bytes, item.mode, item.path.stat().st_mtime_ns,
                                 (item.path.stat().st_dev, item.path.stat().st_ino))
            for item in candidate.files
        }

        prepared = source_edit._prepare_batch(candidate)

        self.assertIsInstance(prepared, source_edit._PreparedBatch)
        self.assertEqual("PREPARED", prepared.record["state"])
        self.assertEqual(1, prepared.record["schema_version"])
        self.assertEqual(prepared.operation_id, prepared.record["operation_id"])
        self.assertTrue(prepared.operation_id)
        self.assertEqual(str(self.source.resolve()), prepared.record["source_root"])
        self.assertEqual(".olympus-cli-edit.lock", prepared.record["lock_identity"]["path"])
        lock_path = self.source / ".olympus-cli-edit.lock"
        self.assertEqual((lock_path.stat().st_dev, lock_path.stat().st_ino),
                         (prepared.record["lock_identity"]["st_dev"],
                          prepared.record["lock_identity"]["st_ino"]))
        self.assertEqual(tuple(candidate.preview["data"]["write_set"]), prepared.write_set)
        self.assertEqual(prepared.record, json.loads(prepared.record_path.read_text(encoding="utf-8")))

        file_records = {entry["path"]: entry for entry in prepared.record["files"]}
        self.assertEqual(set(candidate.preview["data"]["write_set"]), set(file_records))
        self.assertIn("olympus/core/models.toml", file_records)
        for item in candidate.files:
            entry = file_records[item.relative_path]
            backup = prepared.scratch_path / entry["backup"]
            staged = prepared.scratch_path / entry["staged"]
            self.assertEqual(item.old_bytes, backup.read_bytes())
            self.assertEqual(item.new_bytes, staged.read_bytes())
            self.assertEqual(item.old_bytes, item.path.read_bytes(), "T015 must not replace original targets")
            self.assertEqual(item.mode, os.stat(backup).st_mode & 0o7777)
            self.assertEqual(item.mode, os.stat(staged).st_mode & 0o7777)
            self.assertEqual(hashlib.sha256(item.old_bytes).hexdigest(), entry["old_sha256"])
            self.assertEqual(hashlib.sha256(item.new_bytes).hexdigest(), entry["new_sha256"])
            self.assertEqual(item.old_sha256, entry["old_sha256"])
            self.assertEqual(item.new_sha256, entry["new_sha256"])
            self.assertEqual(item.mode, entry["mode"])
            self.assertEqual(original_targets[item.relative_path],
                             (item.path.read_bytes(), item.mode, item.path.stat().st_mtime_ns,
                              (item.path.stat().st_dev, item.path.stat().st_ino)))

        read_records = {entry["path"]: entry for entry in prepared.record["read_set"]}
        self.assertEqual(set(candidate.read_set), set(read_records))
        for relative, signature in candidate.read_set.items():
            entry = read_records[relative]
            self.assertEqual(signature[0], entry["kind"])
            self.assertEqual(signature[3], entry["mode"])
            self.assertEqual(signature[-1] if signature[0] == "file" else None, entry["sha256"])
        self.assertEqual(before, self._snapshot_without_batch_control(),
                         "Only the stable lock and private batch scratch may be added")
        self.assertEqual(0, lock_path.stat().st_size)
        self.assertFalse((prepared.scratch_path / ".record.json.tmp").exists())

    def test_slice_b_batch_noop_creates_no_lock_or_scratch(self):
        model_edit = self.model_edit()
        candidate = model_edit._build_set_family_candidate(
            self.source, "sol", "openai/gpt-6.1-sol", "gpt-6.1-sol"
        )
        before = self.snapshot()

        result = source_edit._prepare_batch(candidate)

        self.assertIsNone(result)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_batch_rejects_readset_drift_before_creating_control_files(self):
        model_edit = self.model_edit()
        candidate = model_edit._build_set_role_candidate(
            self.source, "veyra", family="sol", effort="high"
        )
        unrelated_input = self.source / "olympus/policies/orchestration.toml"
        unrelated_input.write_bytes(unrelated_input.read_bytes() + b"\n# fixture drift\n")
        before = self.snapshot()

        with self.assertRaises(source_edit.BatchConflict):
            source_edit._prepare_batch(candidate)

        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_batch_rejects_mode_drift_before_creating_control_files(self):
        model_edit = self.model_edit()
        candidate = model_edit._build_set_role_candidate(
            self.source, "veyra", family="sol", effort="high"
        )
        target = self.source / "olympus/core/models.toml"
        original_mode = stat.S_IMODE(target.stat().st_mode)
        changed_mode = (original_mode & ~stat.S_IWRITE
                        if original_mode & stat.S_IWRITE else original_mode | stat.S_IWRITE)
        os.chmod(target, changed_mode)
        if stat.S_IMODE(target.stat().st_mode) == original_mode:
            self.skipTest("Host filesystem does not expose a mutable fixture mode")
        before = self.snapshot()

        with self.assertRaisesRegex(source_edit.BatchConflict, "read-set drift"):
            source_edit._prepare_batch(candidate)

        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_batch_rejects_unsafe_target_path_before_control_files(self):
        from dataclasses import replace

        model_edit = self.model_edit()
        candidate = model_edit._build_set_role_candidate(
            self.source, "veyra", family="sol", effort="high"
        )
        unsafe = replace(candidate.files[0], relative_path="../outside", path=self.source.parent / "outside")
        invalid_candidate = replace(candidate, files=(unsafe, *candidate.files[1:]))
        before = self.snapshot()

        with self.assertRaisesRegex(source_edit.BatchBlocked, "Unsafe source-relative path"):
            source_edit._prepare_batch(invalid_candidate)

        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_batch_rejects_symlinked_output_before_control_files(self):
        model_edit = self.model_edit()
        candidate = model_edit._build_set_role_candidate(
            self.source, "veyra", family="sol", effort="high"
        )
        target = self.source / ".codex/agents/veyra.toml"
        link_target = self.sandbox / "unsafe-output-target"
        link_target.write_bytes(target.read_bytes())
        target.unlink()
        try:
            os.symlink(link_target, target)
        except (NotImplementedError, OSError) as error:
            target.write_bytes(link_target.read_bytes())
            self.skipTest(f"Host cannot create a symlink safety fixture: {error}")
        before = self.snapshot()

        with self.assertRaisesRegex(source_edit.BatchBlocked, "Linked/reparse"):
            source_edit._prepare_batch(candidate)

        self.assertEqual(before, self.snapshot())
        self.assertTrue(target.is_symlink())
        self.assertEqual(link_target.read_bytes(), target.read_bytes())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_batch_rejects_hardlinked_target_without_changing_it(self):
        model_edit = self.model_edit()
        candidate = model_edit._build_set_role_candidate(
            self.source, "veyra", family="sol", effort="high"
        )
        target = self.source / ".codex/agents/veyra.toml"
        external_alias = self.sandbox / "external-hardlink-target"
        original = target.read_bytes()
        external_alias.write_bytes(original)
        target.unlink()
        try:
            os.link(external_alias, target)
        except (NotImplementedError, OSError) as error:
            target.write_bytes(original)
            self.skipTest(f"Host cannot create a hard-link safety fixture: {error}")
        before = self.snapshot()

        with self.assertRaisesRegex(source_edit.BatchBlocked, "Hard-linked"):
            source_edit._prepare_batch(candidate)

        self.assertEqual(before, self.snapshot())
        self.assertEqual(original, target.read_bytes())
        self.assertEqual(original, external_alias.read_bytes())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_batch_record_failure_preserves_staging_and_never_replaces_targets(self):
        from unittest.mock import patch

        model_edit = self.model_edit()
        candidate = model_edit._build_set_role_candidate(
            self.source, "veyra", family="sol", effort="high"
        )
        before_targets = {
            item.relative_path: (item.old_bytes, item.mode, item.path.stat().st_mtime_ns,
                                 (item.path.stat().st_dev, item.path.stat().st_ino))
            for item in candidate.files
        }
        original_replace = os.replace
        target_replacements = []
        record_path = self.source / ".olympus-cli-edit/record.json"

        def fail_record_replace(source, destination):
            destination = Path(destination)
            if destination in {item.path for item in candidate.files}:
                target_replacements.append(destination)
                raise AssertionError("T015 must not replace a target")
            if destination == record_path:
                raise OSError("fixture failure before PREPARED record replacement")
            return original_replace(source, destination)

        with patch.object(source_edit.os, "replace", side_effect=fail_record_replace):
            with self.assertRaises(source_edit.BatchBlocked):
                source_edit._prepare_batch(candidate)

        self.assertEqual([], target_replacements)
        self.assertTrue((self.source / ".olympus-cli-edit.lock").is_file())
        self.assertFalse(record_path.exists())
        self.assertTrue((self.source / ".olympus-cli-edit/.record.json.tmp").is_file())
        for item in candidate.files:
            self.assertEqual(before_targets[item.relative_path],
                             (item.path.read_bytes(), item.mode, item.path.stat().st_mtime_ns,
                              (item.path.stat().st_dev, item.path.stat().st_ino)))
        scratch = self.source / ".olympus-cli-edit"
        for index, item in enumerate(candidate.files):
            self.assertEqual(item.old_bytes, (scratch / "backups" / f"file-{index:04d}.old").read_bytes())
            self.assertEqual(item.new_bytes, (scratch / "staged" / f"file-{index:04d}.new").read_bytes())

    def _family_candidate(self):
        return self.model_edit()._build_set_family_candidate(
            self.source, "sol", "openai/sol-t016", "codex/sol-t016"
        )

    def _prepared_family(self):
        candidate = self._family_candidate()
        prepared = source_edit._prepare_batch(candidate)
        self.assertIsNotNone(prepared)
        return candidate, prepared

    def _replace_prepared_targets(self, prepared, relatives):
        selected = set(relatives)
        lock = source_edit._acquire_lock(self.source, create=False)
        try:
            identity = source_edit._lock_identity(lock)
            for index, entry in enumerate(prepared.record["files"]):
                if entry["path"] not in selected:
                    continue
                source_edit._lock_identity(lock, identity)
                os.replace(prepared.scratch_path / entry["staged"], self.source / entry["path"])
        finally:
            source_edit._release_lock(lock)

    def _run_abrupt_commit(self, prepared, target_count):
        payload = {
            "operation_id": prepared.operation_id,
            "source_root": str(prepared.source_root),
            "scratch_path": str(prepared.scratch_path),
            "record_path": str(prepared.record_path),
            "write_set": list(prepared.write_set),
            "record": prepared.record,
        }
        script = r'''
import json, os, sys
from pathlib import Path
from olympus import source_edit
data = json.loads(sys.argv[1])
prepared = source_edit._PreparedBatch(
    operation_id=data["operation_id"], source_root=Path(data["source_root"]),
    scratch_path=Path(data["scratch_path"]), record_path=Path(data["record_path"]),
    write_set=tuple(data["write_set"]), record=data["record"],
)
targets = {str(Path(data["source_root"]) / relative) for relative in data["write_set"]}
original = os.replace
count = 0
def abrupt_replace(src, dst):
    global count
    result = original(src, dst)
    if str(Path(dst)) in targets:
        count += 1
        if count == int(sys.argv[2]):
            os._exit(91)
    return result
source_edit.os.replace = abrupt_replace
source_edit._commit_batch(prepared)
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, json.dumps(payload), str(target_count)],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, encoding="utf-8", check=False, timeout=30,
        )
        self.assertEqual(91, result.returncode, result.stderr)

    def _run_abrupt_recovery(self, source, restore_count):
        script = r'''
import builtins, os, sys
from pathlib import Path
original_import = builtins.__import__
def stdlib_only(name, *args, **kwargs):
    if name == "tomlkit" or name.startswith("tomlkit."):
        raise AssertionError("recovery attempted to import TOML Kit")
    return original_import(name, *args, **kwargs)
builtins.__import__ = stdlib_only
from olympus import source_edit
original_replace = os.replace
count = 0
def abrupt_restore(src, dst):
    global count
    result = original_replace(src, dst)
    if "rollback-file-" in Path(src).name:
        count += 1
        if count == int(sys.argv[2]):
            os._exit(92)
    return result
source_edit.os.replace = abrupt_restore
source_edit._recover_batch(Path(sys.argv[1]))
'''
        base_executable = Path(sys.base_prefix) / "python.exe"
        if os.name != "nt":
            base_executable = Path(sys.base_prefix) / "bin" / "python3.11"
        python = str(base_executable) if base_executable.is_file() else sys.executable
        result = subprocess.run(
            [python, "-B", "-c", script, str(source), str(restore_count)],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, encoding="utf-8", check=False, timeout=30,
        )
        self.assertEqual(92, result.returncode, result.stderr)

    def _assert_targets_old(self, candidate):
        for item in candidate.files:
            self.assertEqual(item.old_bytes, item.path.read_bytes(), item.relative_path)
            self.assertEqual(item.mode, stat.S_IMODE(item.path.stat().st_mode), item.relative_path)
        self.assertEqual("PASS", self.renderer_check())

    def renderer_check(self):
        for path, expected in self.renderer.outputs_for(self.source, "all").items():
            if path.read_bytes() != expected.encode("utf-8"):
                return "FAIL"
        return "PASS"

    def test_slice_b_commit_uses_individual_replace_and_confirms_complete_renderer_state(self):
        from unittest.mock import patch

        candidate, prepared = self._prepared_family()
        before = self._snapshot_outside_targets(candidate)
        target_paths = {item.path for item in candidate.files}
        replacements = []
        original_replace = os.replace

        def record_replacements(source, destination):
            destination = Path(destination)
            if destination in target_paths:
                replacements.append(destination)
            return original_replace(source, destination)

        with patch.object(source_edit.os, "replace", side_effect=record_replacements):
            self.assertEqual("committed", source_edit._commit_batch(prepared))

        self.assertEqual(list(sorted(target_paths)), replacements)
        self.assertEqual(before, self._snapshot_outside_targets(candidate))
        self.assertFalse((self.source / ".olympus-cli-edit").exists())
        lock = self.source / ".olympus-cli-edit.lock"
        self.assertTrue(lock.is_file())
        self.assertEqual(0, lock.stat().st_size)
        self.assertEqual((prepared.record["lock_identity"]["st_dev"],
                          prepared.record["lock_identity"]["st_ino"]),
                         (lock.stat().st_dev, lock.stat().st_ino))
        for item in candidate.files:
            self.assertEqual(item.new_bytes, item.path.read_bytes(), item.relative_path)
            self.assertEqual(item.mode, stat.S_IMODE(item.path.stat().st_mode), item.relative_path)
        self.assertEqual("PASS", self.renderer_check())

    def test_slice_b_caught_replacement_failure_rolls_back_under_same_lock(self):
        from unittest.mock import patch

        candidate, prepared = self._prepared_family()
        before = self._snapshot_outside_targets(candidate)
        fail_target = candidate.files[2].path
        target_paths = {item.path for item in candidate.files}
        failed = False
        touched = []
        original_replace = os.replace

        def fail_one_target(source, destination):
            nonlocal failed
            destination = Path(destination)
            if destination == fail_target and not failed:
                failed = True
                raise OSError("fixture replacement failure")
            if destination in target_paths:
                touched.append(destination)
            return original_replace(source, destination)

        with patch.object(source_edit.os, "replace", side_effect=fail_one_target):
            with self.assertRaisesRegex(source_edit.BatchError, "rollback was confirmed"):
                source_edit._commit_batch(prepared)

        self.assertTrue(failed)
        self.assertGreaterEqual(len(touched), 4, "two committed targets must be restored individually")
        self._assert_targets_old(candidate)
        self.assertEqual(before, self._snapshot_outside_targets(candidate))
        self.assertFalse((self.source / ".olympus-cli-edit").exists())
        lock = self.source / ".olympus-cli-edit.lock"
        self.assertTrue(lock.is_file())
        self.assertEqual(0, lock.stat().st_size)
        self.assertEqual((prepared.record["lock_identity"]["st_dev"],
                          prepared.record["lock_identity"]["st_ino"]),
                         (lock.stat().st_dev, lock.stat().st_ino))

    def test_slice_b_abrupt_partial_commit_and_interrupted_recovery_are_repeatable(self):
        candidate, prepared = self._prepared_family()
        before = self._snapshot_outside_targets(candidate)
        self._run_abrupt_commit(prepared, 3)
        persisted = json.loads(prepared.record_path.read_text(encoding="utf-8"))
        self.assertEqual("PREPARED", persisted["state"])
        self.assertEqual(3, sum(item.path.read_bytes() == item.new_bytes for item in candidate.files))

        # Recovery itself dies after two verified restore renames. Its backups
        # remain intact, and a second explicit recovery completes the rollback.
        self._run_abrupt_recovery(self.source, 2)
        self.assertTrue(prepared.record_path.is_file())
        self.assertEqual("PREPARED", json.loads(prepared.record_path.read_text(encoding="utf-8"))["state"])
        for entry in prepared.record["files"]:
            backup = prepared.scratch_path / entry["backup"]
            self.assertEqual(entry["old_sha256"], hashlib.sha256(backup.read_bytes()).hexdigest())

        from unittest.mock import patch
        original_import = __import__

        def reject_editor(name, *args, **kwargs):
            if name == "tomlkit" or name.startswith("tomlkit."):
                raise AssertionError("recovery imported the optional editor")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=reject_editor):
            self.assertEqual("rolled_back", source_edit._recover_batch(self.source))
        self._assert_targets_old(candidate)
        self.assertEqual(before, self._snapshot_outside_targets(candidate))
        self.assertFalse((self.source / ".olympus-cli-edit").exists())
        self.assertEqual("no_changes", source_edit._recover_batch(self.source))

    def test_slice_b_recovery_prepared_old_and_all_new_both_finish_old(self):
        candidate, prepared = self._prepared_family()
        self.assertEqual("rolled_back", source_edit._recover_batch(self.source))
        self._assert_targets_old(candidate)
        self.assertFalse(prepared.scratch_path.exists())

        candidate, prepared = self._prepared_family()
        self._replace_prepared_targets(prepared, prepared.write_set)
        self.assertEqual("rolled_back", source_edit._recover_batch(self.source))
        self._assert_targets_old(candidate)
        self.assertFalse(prepared.scratch_path.exists())

    def test_slice_b_committed_partial_cleanup_is_explicitly_repeatable_without_removed_backups(self):
        from unittest.mock import patch

        candidate, prepared = self._prepared_family()
        original_remove = source_edit._remove_owned_file
        removed_one_backup = False

        def interrupt_cleanup(source, lock, relative, expected_hash, expected_mode):
            nonlocal removed_one_backup
            original_remove(source, lock, relative, expected_hash, expected_mode)
            if "/backups/" in relative.replace("\\", "/") and not removed_one_backup:
                removed_one_backup = True
                raise OSError("fixture interruption during COMMITTED cleanup")

        with patch.object(source_edit, "_remove_owned_file", side_effect=interrupt_cleanup):
            with self.assertRaisesRegex(source_edit.BatchBlocked, "COMMITTED"):
                source_edit._commit_batch(prepared)

        self.assertTrue(removed_one_backup)
        self.assertEqual("COMMITTED", json.loads(prepared.record_path.read_text(encoding="utf-8"))["state"])
        self.assertFalse((prepared.scratch_path / prepared.record["files"][0]["backup"]).exists())
        self.assertEqual("committed_cleanup", source_edit._recover_batch(self.source))
        for item in candidate.files:
            self.assertEqual(item.new_bytes, item.path.read_bytes(), item.relative_path)
            self.assertEqual(item.mode, stat.S_IMODE(item.path.stat().st_mode), item.relative_path)
        self.assertEqual("PASS", self.renderer_check())
        self.assertFalse(prepared.scratch_path.exists())

    def test_slice_b_recovery_blocks_third_hash_missing_target_and_external_readset_drift(self):
        candidate, prepared = self._prepared_family()
        changed = candidate.files[0]
        self._replace_prepared_targets(prepared, [changed.relative_path])
        third = candidate.files[1]
        third.path.write_bytes(b"third party state")
        third_state = third.path.read_bytes()
        with self.assertRaises(source_edit.BatchConflict):
            source_edit._recover_batch(self.source)
        self.assertEqual(changed.new_bytes, changed.path.read_bytes(), "no restore before full-set validation")
        self.assertEqual(third_state, third.path.read_bytes())
        self.assertTrue(prepared.record_path.is_file())

        # Rebuild the isolated fixture for a missing target conflict.
        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        changed = candidate.files[0]
        self._replace_prepared_targets(prepared, [changed.relative_path])
        missing = candidate.files[1]
        missing.path.unlink()
        with self.assertRaises(source_edit.BatchBlocked):
            source_edit._recover_batch(self.source)
        self.assertEqual(changed.new_bytes, changed.path.read_bytes(), "missing target blocks before restore")
        self.assertFalse(missing.path.exists())
        self.assertTrue(prepared.record_path.is_file())

        # An unrelated canonical input is part of the read-set; do not restore
        # any new target when its recorded content has drifted.
        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        changed = candidate.files[0]
        self._replace_prepared_targets(prepared, [changed.relative_path])
        unrelated = self.source / "olympus/policies/orchestration.toml"
        unrelated.write_bytes(unrelated.read_bytes() + b"\n# external fixture drift\n")
        current_target = changed.path.read_bytes()
        with self.assertRaises(source_edit.BatchConflict):
            source_edit._recover_batch(self.source)
        self.assertEqual(current_target, changed.path.read_bytes())
        self.assertTrue(prepared.record_path.is_file())

    def _reset_source_fixture(self):
        shutil.copytree(ROOT / "olympus", self.source / "olympus",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        scripts = self.source / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts/render_harnesses.py", scripts / "render_harnesses.py")
        self.renderer = load_file("slice_b_fixture_renderer_reset", scripts / "render_harnesses.py")
        for path, content in self.renderer.outputs_for(self.source, "all").items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))

    def test_slice_b_recovery_blocks_mode_and_required_backup_conflicts_before_restore(self):
        candidate, prepared = self._prepared_family()
        changed = candidate.files[0]
        self._replace_prepared_targets(prepared, [changed.relative_path])
        original_mode = stat.S_IMODE(changed.path.stat().st_mode)
        changed_mode = (original_mode & ~stat.S_IWRITE
                        if original_mode & stat.S_IWRITE else original_mode | stat.S_IWRITE)
        os.chmod(changed.path, changed_mode)
        if stat.S_IMODE(changed.path.stat().st_mode) == original_mode:
            self.skipTest("Host filesystem does not expose a mutable fixture target mode")
        changed_mode_observed = stat.S_IMODE(changed.path.stat().st_mode)
        with self.assertRaises(source_edit.BatchConflict):
            source_edit._recover_batch(self.source)
        self.assertEqual(changed_mode_observed, stat.S_IMODE(changed.path.stat().st_mode))
        self.assertTrue(prepared.record_path.is_file())
        os.chmod(changed.path, original_mode)

        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        changed = candidate.files[0]
        self._replace_prepared_targets(prepared, [changed.relative_path])
        entry = prepared.record["files"][0]
        backup = prepared.scratch_path / entry["backup"]
        backup.write_bytes(b"corrupt backup")
        current_target = changed.path.read_bytes()
        with self.assertRaises(source_edit.BatchBlocked):
            source_edit._recover_batch(self.source)
        self.assertEqual(current_target, changed.path.read_bytes())
        self.assertEqual(b"corrupt backup", backup.read_bytes())
        self.assertTrue(prepared.record_path.is_file())

        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        changed = candidate.files[0]
        self._replace_prepared_targets(prepared, [changed.relative_path])
        backup = prepared.scratch_path / prepared.record["files"][0]["backup"]
        backup.unlink()
        current_target = changed.path.read_bytes()
        with self.assertRaises(source_edit.BatchBlocked):
            source_edit._recover_batch(self.source)
        self.assertEqual(current_target, changed.path.read_bytes())
        self.assertTrue(prepared.record_path.is_file())

        # Any staged candidate that remains must still be byte-for-byte new,
        # even when the current target is already old and no restore is needed.
        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        staged = prepared.scratch_path / prepared.record["files"][0]["staged"]
        staged.write_bytes(b"corrupt staged candidate")
        original_targets = {item.relative_path: item.path.read_bytes() for item in candidate.files}
        with self.assertRaises(source_edit.BatchBlocked):
            source_edit._recover_batch(self.source)
        self.assertEqual(original_targets,
                         {item.relative_path: item.path.read_bytes() for item in candidate.files})
        self.assertTrue(prepared.record_path.is_file())

    def test_slice_b_incomplete_or_invalid_record_blocks_without_cleanup_or_target_changes(self):
        candidate, prepared = self._prepared_family()
        scratch = prepared.scratch_path
        record_path = prepared.record_path
        original_targets = {item.relative_path: item.path.read_bytes() for item in candidate.files}
        scratch_names = set(os.listdir(scratch))
        record_path.unlink()
        with self.assertRaises(source_edit.BatchBlocked):
            source_edit._recover_batch(self.source)
        self.assertEqual(original_targets,
                         {item.relative_path: item.path.read_bytes() for item in candidate.files})
        self.assertEqual(scratch_names - {"record.json"}, set(os.listdir(scratch)))

        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        record = dict(prepared.record)
        record["schema_version"] = 2
        prepared.record_path.write_bytes(source_edit._record_bytes(record))
        original_targets = {item.relative_path: item.path.read_bytes() for item in candidate.files}
        invalid_record_bytes = prepared.record_path.read_bytes()
        with self.assertRaises(source_edit.BatchBlocked):
            source_edit._recover_batch(self.source)
        self.assertEqual(invalid_record_bytes, prepared.record_path.read_bytes())
        self.assertEqual(original_targets,
                         {item.relative_path: item.path.read_bytes() for item in candidate.files})

        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        record = dict(prepared.record)
        record["source_root"] = str(self.source.parent / "other-source")
        prepared.record_path.write_bytes(source_edit._record_bytes(record))
        with self.assertRaisesRegex(source_edit.BatchBlocked, "different canonical source"):
            source_edit._recover_batch(self.source)
        self.assertTrue(prepared.record_path.is_file())

        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        record = dict(prepared.record)
        record["files"] = [dict(entry) for entry in prepared.record["files"]]
        record["files"][0]["path"] = "../outside"
        prepared.record_path.write_bytes(source_edit._record_bytes(record))
        with self.assertRaises(source_edit.BatchBlocked):
            source_edit._recover_batch(self.source)
        self.assertTrue(prepared.record_path.is_file())

        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        record = dict(prepared.record)
        record["lock_identity"] = dict(prepared.record["lock_identity"])
        record["lock_identity"]["st_ino"] += 1
        prepared.record_path.write_bytes(source_edit._record_bytes(record))
        with self.assertRaisesRegex(source_edit.BatchBlocked, "stable lock identity"):
            source_edit._recover_batch(self.source)
        self.assertTrue(prepared.record_path.is_file())

        shutil.rmtree(self.source)
        self._reset_source_fixture()
        candidate, prepared = self._prepared_family()
        lock_path = self.source / ".olympus-cli-edit.lock"
        lock_path.unlink()  # Fixture simulates a missing control file; recovery must not recreate it.
        record_before = prepared.record_path.read_bytes()
        with self.assertRaises(source_edit.BatchBlocked):
            source_edit._recover_batch(self.source)
        self.assertFalse(lock_path.exists())
        self.assertEqual(record_before, prepared.record_path.read_bytes())
        self.assertTrue(prepared.scratch_path.exists())

    def _t017_seed_sentinels(self):
        """Create non-target sentinels before T017 snapshots, only in fixtures."""
        cache = self.source / "olympus" / "__pycache__" / "t017_fixture.pyc"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(b"T017 fixture cache sentinel\x00")
        for relative, payload in (
            (".opencode/olympus-install-manifest.sentinel", b"fixture opencode manifest\n"),
            (".codex/olympus-install-manifest.sentinel", b"fixture codex manifest\n"),
        ):
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        self.t017_external_root = self.sandbox / "installed manifest sentinels"
        external_payloads = {
            ".opencode/agents/veyra.md": b"installed sentinel prompt\n",
            ".opencode/olympus-install-manifest.json": b'{"sentinel":"opencode"}\n',
            ".codex/agents/veyra.toml": b'model = "installed-sentinel"\n',
            ".codex/olympus-install-manifest.json": b'{"sentinel":"codex"}\n',
            "cache/__pycache__/installed_fixture.pyc": b"installed cache sentinel\x00",
        }
        for relative, payload in external_payloads.items():
            path = self.t017_external_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

    def _t017_external_snapshot(self):
        root = self.t017_external_root
        paths = set(root.rglob("*"))
        inventory = {
            path.relative_to(root).as_posix(): (
                "directory" if path.is_dir() else "file",
                stat.S_IMODE(path.stat().st_mode),
                path.stat().st_size,
                path.stat().st_mtime_ns,
            )
            for path in paths
        }
        return inventory, helpers.snapshot_outputs({path for path in paths if path.is_file()})

    def _t017_reset_fixture(self):
        if self.source.exists():
            shutil.rmtree(self.source)
        self._reset_source_fixture()
        self._t017_seed_sentinels()

    def _run_t017_abrupt_commit(self, prepared, boundary):
        """Exit a real child at boundary 0..N around target os.replace calls."""
        payload = {
            "operation_id": prepared.operation_id,
            "source_root": str(prepared.source_root),
            "scratch_path": str(prepared.scratch_path),
            "record_path": str(prepared.record_path),
            "write_set": list(prepared.write_set),
            "record": prepared.record,
        }
        script = r'''
import json, os, sys
from pathlib import Path
from olympus import source_edit
data = json.loads(sys.argv[1])
prepared = source_edit._PreparedBatch(
    operation_id=data["operation_id"], source_root=Path(data["source_root"]),
    scratch_path=Path(data["scratch_path"]), record_path=Path(data["record_path"]),
    write_set=tuple(data["write_set"]), record=data["record"],
)
targets = {(Path(data["source_root"]) / relative).resolve() for relative in data["write_set"]}
boundary = int(sys.argv[2])
original = os.replace
count = 0
def abrupt_replace(src, dst):
    global count
    if Path(dst).resolve() in targets:
        if boundary == 0 and count == 0:
            os._exit(91)
        result = original(src, dst)
        count += 1
        if count == boundary:
            os._exit(91)
        return result
    return original(src, dst)
source_edit.os.replace = abrupt_replace
source_edit._commit_batch(prepared)
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, json.dumps(payload, ensure_ascii=False), str(boundary)],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.assertEqual(91, result.returncode, result.stdout + result.stderr)

    def _run_t017_abrupt_recovery(self, source, restore_count):
        script = r'''
import builtins, os, sys
from pathlib import Path
original_import = builtins.__import__
def stdlib_only(name, *args, **kwargs):
    if name == "tomlkit" or name.startswith("tomlkit."):
        raise AssertionError("recovery attempted to import TOML Kit")
    return original_import(name, *args, **kwargs)
builtins.__import__ = stdlib_only
from olympus import source_edit
original_replace = os.replace
count = 0
def abrupt_restore(src, dst):
    global count
    result = original_replace(src, dst)
    if "rollback-file-" in Path(src).name:
        count += 1
        if count == int(sys.argv[2]):
            os._exit(92)
    return result
source_edit.os.replace = abrupt_restore
source_edit._recover_batch(Path(sys.argv[1]))
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, str(source), str(restore_count)],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.assertEqual(92, result.returncode, result.stdout + result.stderr)

    def test_slice_b_t017_failure_before_prepared_retains_fixture_evidence(self):
        from unittest.mock import patch

        self._t017_seed_sentinels()
        candidate = self._family_candidate()
        self.assertEqual(14, len(candidate.files), "T017 must use the maximum baseline write-set")
        before_targets = {
            item.relative_path: (item.old_bytes, item.mode, item.path.stat().st_mtime_ns)
            for item in candidate.files
        }
        before_outside = self._snapshot_outside_targets(candidate)
        before_external = self._t017_external_snapshot()
        record_path = self.source / ".olympus-cli-edit" / "record.json"
        original_replace = os.replace

        def fail_before_prepared(source, destination):
            if Path(destination) == record_path:
                raise OSError("T017 fixture interruption before PREPARED record persistence")
            return original_replace(source, destination)

        with patch.object(source_edit.os, "replace", side_effect=fail_before_prepared):
            with self.assertRaises(source_edit.BatchBlocked):
                source_edit._prepare_batch(candidate)

        self.assertFalse(record_path.exists())
        scratch = self.source / ".olympus-cli-edit"
        self.assertTrue((scratch / ".record.json.tmp").is_file())
        self.assertTrue((scratch / "backups").is_dir())
        self.assertTrue((scratch / "staged").is_dir())
        lock_path = self.source / ".olympus-cli-edit.lock"
        self.assertTrue(lock_path.is_file())
        self.assertEqual(0, lock_path.stat().st_size)
        for item in candidate.files:
            self.assertEqual(
                before_targets[item.relative_path],
                (item.path.read_bytes(), stat.S_IMODE(item.path.stat().st_mode), item.path.stat().st_mtime_ns),
            )
        self.assertEqual(before_outside, self._snapshot_outside_targets(candidate))
        self.assertEqual(before_external, self._t017_external_snapshot())

    def test_slice_b_t017_crash_at_all_15_maximum_write_set_boundaries_recovers_old(self):
        for boundary in range(15):
            with self.subTest(replacement_boundary=boundary):
                if boundary:
                    self._t017_reset_fixture()
                else:
                    self._t017_seed_sentinels()
                candidate, prepared = self._prepared_family()
                self.assertEqual(14, len(candidate.files), "baseline family edit must have 14 targets")
                self.assertEqual(14, len(prepared.write_set))
                before_outside = self._snapshot_outside_targets(candidate)
                before_external = self._t017_external_snapshot()

                self._run_t017_abrupt_commit(prepared, boundary)

                persisted = json.loads(prepared.record_path.read_text(encoding="utf-8"))
                self.assertEqual("PREPARED", persisted["state"])
                self.assertEqual(prepared.operation_id, persisted["operation_id"])
                self.assertEqual(boundary, sum(item.path.read_bytes() == item.new_bytes for item in candidate.files))
                for index, (item, entry) in enumerate(zip(candidate.files, prepared.record["files"])):
                    self.assertEqual(item.relative_path, entry["path"])
                    self.assertEqual(item.mode, stat.S_IMODE(item.path.stat().st_mode))
                    backup = prepared.scratch_path / entry["backup"]
                    self.assertEqual(entry["old_sha256"], hashlib.sha256(backup.read_bytes()).hexdigest())
                    staged = prepared.scratch_path / entry["staged"]
                    self.assertEqual(index >= boundary, staged.exists())
                    self.assertEqual(boundary <= index, item.path.read_bytes() == item.old_bytes)
                self.assertEqual(before_outside, self._snapshot_outside_targets(candidate))
                self.assertEqual(before_external, self._t017_external_snapshot())

                self.assertEqual("rolled_back", source_edit._recover_batch(self.source))
                self._assert_targets_old(candidate)
                self.assertEqual(before_outside, self._snapshot_outside_targets(candidate))
                self.assertEqual(before_external, self._t017_external_snapshot())
                self.assertFalse(prepared.scratch_path.exists())
                self.assertEqual("no_changes", source_edit._recover_batch(self.source))
                lock_path = self.source / ".olympus-cli-edit.lock"
                self.assertEqual((prepared.record["lock_identity"]["st_dev"],
                                  prepared.record["lock_identity"]["st_ino"]),
                                 (lock_path.stat().st_dev, lock_path.stat().st_ino))

    def test_slice_b_t017_interrupted_rollback_repeats_without_consuming_backups(self):
        self._t017_seed_sentinels()
        candidate, prepared = self._prepared_family()
        before_outside = self._snapshot_outside_targets(candidate)
        before_external = self._t017_external_snapshot()
        self._run_t017_abrupt_commit(prepared, 3)
        self.assertEqual("PREPARED", json.loads(prepared.record_path.read_text(encoding="utf-8"))["state"])
        self.assertEqual(3, sum(item.path.read_bytes() == item.new_bytes for item in candidate.files))

        self._run_t017_abrupt_recovery(self.source, 2)
        self.assertEqual("PREPARED", json.loads(prepared.record_path.read_text(encoding="utf-8"))["state"])
        self.assertEqual(len(candidate.files) - 1,
                         sum(item.path.read_bytes() == item.old_bytes for item in candidate.files))
        self.assertEqual(1, sum(item.path.read_bytes() == item.new_bytes for item in candidate.files))
        for entry in prepared.record["files"]:
            backup = prepared.scratch_path / entry["backup"]
            self.assertEqual(entry["old_sha256"], hashlib.sha256(backup.read_bytes()).hexdigest())
            self.assertEqual(entry["mode"], stat.S_IMODE(backup.stat().st_mode))

        self.assertEqual("rolled_back", source_edit._recover_batch(self.source))
        self._assert_targets_old(candidate)
        self.assertEqual(before_outside, self._snapshot_outside_targets(candidate))
        self.assertEqual(before_external, self._t017_external_snapshot())
        self.assertFalse(prepared.scratch_path.exists())
        self.assertEqual("no_changes", source_edit._recover_batch(self.source))

    def test_slice_b_t017_committed_cleanup_pending_and_partial_are_repeatable(self):
        from unittest.mock import patch

        self._t017_seed_sentinels()
        candidate, prepared = self._prepared_family()
        before_outside = self._snapshot_outside_targets(candidate)
        before_external = self._t017_external_snapshot()
        original_cleanup = source_edit._cleanup_batch

        def interrupt_before_cleanup(source, lock, record, record_raw, record_metadata, *, final_state):
            if final_state == "new":
                raise OSError("T017 interruption after COMMITTED and before cleanup")
            return original_cleanup(source, lock, record, record_raw, record_metadata,
                                   final_state=final_state)

        with patch.object(source_edit, "_cleanup_batch", side_effect=interrupt_before_cleanup):
            with self.assertRaises(source_edit.BatchBlocked):
                source_edit._commit_batch(prepared)
        self.assertEqual("COMMITTED", json.loads(prepared.record_path.read_text(encoding="utf-8"))["state"])
        self.assertTrue(all((prepared.scratch_path / entry["backup"]).is_file()
                            for entry in prepared.record["files"]))
        self.assertTrue(all(item.path.read_bytes() == item.new_bytes for item in candidate.files))
        self.assertEqual("committed_cleanup", source_edit._recover_batch(self.source))
        self.assertTrue(all(item.path.read_bytes() == item.new_bytes for item in candidate.files))
        self.assertEqual("PASS", self.renderer_check())
        self.assertEqual(before_outside, self._snapshot_outside_targets(candidate))
        self.assertEqual(before_external, self._t017_external_snapshot())
        self.assertFalse(prepared.scratch_path.exists())

        self._t017_reset_fixture()
        candidate, prepared = self._prepared_family()
        before_outside = self._snapshot_outside_targets(candidate)
        before_external = self._t017_external_snapshot()
        original_remove = source_edit._remove_owned_file
        removed_backup = False

        def interrupt_partial_cleanup(source, lock, relative, expected_hash, expected_mode):
            nonlocal removed_backup
            original_remove(source, lock, relative, expected_hash, expected_mode)
            if "/backups/" in relative.replace("\\", "/") and not removed_backup:
                removed_backup = True
                raise OSError("T017 interruption during partial COMMITTED cleanup")

        with patch.object(source_edit, "_remove_owned_file", side_effect=interrupt_partial_cleanup):
            with self.assertRaises(source_edit.BatchBlocked):
                source_edit._commit_batch(prepared)
        record = json.loads(prepared.record_path.read_text(encoding="utf-8"))
        self.assertEqual("COMMITTED", record["state"])
        self.assertTrue(removed_backup)
        self.assertFalse((prepared.scratch_path / record["files"][0]["backup"]).exists())
        self.assertTrue(all(item.path.read_bytes() == item.new_bytes for item in candidate.files))
        self.assertEqual("committed_cleanup", source_edit._recover_batch(self.source))
        self.assertTrue(all(item.path.read_bytes() == item.new_bytes for item in candidate.files))
        self.assertEqual("PASS", self.renderer_check())
        self.assertEqual(before_outside, self._snapshot_outside_targets(candidate))
        self.assertEqual(before_external, self._t017_external_snapshot())
        self.assertFalse(prepared.scratch_path.exists())

    def test_slice_b_t017_conflicts_never_overwrite_external_or_ambiguous_resources(self):
        self._t017_seed_sentinels()
        candidate, prepared = self._prepared_family()
        self._replace_prepared_targets(prepared, [candidate.files[0].relative_path])
        external_target = candidate.files[1]
        external_target.path.write_bytes(b"external third-hash state")
        before_source = self.snapshot()
        before_external = self._t017_external_snapshot()
        with self.assertRaises(source_edit.BatchConflict):
            source_edit._recover_batch(self.source)
        self.assertEqual(before_source, self.snapshot())
        self.assertEqual(before_external, self._t017_external_snapshot())
        self.assertEqual(b"external third-hash state", external_target.path.read_bytes())
        self.assertTrue(prepared.record_path.is_file())

        self._t017_reset_fixture()
        candidate, prepared = self._prepared_family()
        self._replace_prepared_targets(prepared, [candidate.files[0].relative_path])
        unrelated = self.source / "olympus/policies/orchestration.toml"
        unrelated.write_bytes(unrelated.read_bytes() + b"\n# external read-set drift\n")
        before_source = self.snapshot()
        before_external = self._t017_external_snapshot()
        with self.assertRaises(source_edit.BatchConflict):
            source_edit._recover_batch(self.source)
        self.assertEqual(before_source, self.snapshot())
        self.assertEqual(before_external, self._t017_external_snapshot())
        self.assertEqual(candidate.files[0].new_bytes, candidate.files[0].path.read_bytes())
        self.assertTrue(prepared.record_path.is_file())

        self._t017_reset_fixture()
        candidate, prepared = self._prepared_family()
        self._replace_prepared_targets(prepared, [candidate.files[0].relative_path])
        missing_target = candidate.files[1].path
        missing_target.unlink()
        before_source = self.snapshot()
        with self.assertRaises(source_edit.BatchBlocked):
            source_edit._recover_batch(self.source)
        self.assertEqual(before_source, self.snapshot())
        self.assertFalse(missing_target.exists())
        self.assertTrue(prepared.record_path.is_file())

        for damage in ("corrupt", "missing"):
            with self.subTest(backup=damage):
                self._t017_reset_fixture()
                candidate, prepared = self._prepared_family()
                self._replace_prepared_targets(prepared, [candidate.files[0].relative_path])
                backup = prepared.scratch_path / prepared.record["files"][0]["backup"]
                if damage == "corrupt":
                    backup.write_bytes(b"corrupt recovery backup")
                else:
                    backup.unlink()
                before_source = self.snapshot()
                before_external = self._t017_external_snapshot()
                with self.assertRaises(source_edit.BatchBlocked):
                    source_edit._recover_batch(self.source)
                self.assertEqual(before_source, self.snapshot())
                self.assertEqual(before_external, self._t017_external_snapshot())
                self.assertEqual(candidate.files[0].new_bytes, candidate.files[0].path.read_bytes())
                self.assertTrue(prepared.record_path.is_file())

        self._t017_reset_fixture()
        candidate, prepared = self._prepared_family()
        self._replace_prepared_targets(prepared, [candidate.files[0].relative_path])
        mode_target = candidate.files[0].path
        original_mode = stat.S_IMODE(mode_target.stat().st_mode)
        alternate_mode = (original_mode & ~stat.S_IWRITE
                          if original_mode & stat.S_IWRITE else original_mode | stat.S_IWRITE)
        os.chmod(mode_target, alternate_mode)
        changed_mode = stat.S_IMODE(mode_target.stat().st_mode)
        self.assertNotEqual(original_mode, changed_mode, "Windows fixture filesystem must expose mode divergence")
        before_source = self.snapshot()
        before_external = self._t017_external_snapshot()
        with self.assertRaises(source_edit.BatchConflict):
            source_edit._recover_batch(self.source)
        self.assertEqual(before_source, self.snapshot())
        self.assertEqual(before_external, self._t017_external_snapshot())
        self.assertEqual(changed_mode, stat.S_IMODE(mode_target.stat().st_mode))
        self.assertTrue(prepared.record_path.is_file())

    def test_slice_b_t017_incomplete_schema_context_and_path_records_block(self):
        cases = ("truncated", "schema", "context", "path", "lock_identity")
        for case in cases:
            with self.subTest(record_case=case):
                self._t017_reset_fixture()
                candidate, prepared = self._prepared_family()
                if case == "truncated":
                    prepared.record_path.write_bytes(b'{"schema_version":1,"state":"PREPARED"')
                else:
                    record = json.loads(prepared.record_path.read_text(encoding="utf-8"))
                    if case == "schema":
                        record["schema_version"] = 2
                    elif case == "context":
                        record["source_root"] = str(self.sandbox / "another source")
                    elif case == "path":
                        record["files"][0]["path"] = "../outside"
                    else:
                        record["lock_identity"]["st_ino"] += 1
                    prepared.record_path.write_bytes(source_edit._record_bytes(record))
                invalid_record = prepared.record_path.read_bytes()
                before_source = self.snapshot()
                before_external = self._t017_external_snapshot()
                with self.assertRaises(source_edit.BatchBlocked):
                    source_edit._recover_batch(self.source)
                self.assertEqual(before_source, self.snapshot())
                self.assertEqual(before_external, self._t017_external_snapshot())
                self.assertEqual(invalid_record, prepared.record_path.read_bytes())
                self.assertTrue(prepared.scratch_path.exists())
                for item in candidate.files:
                    self.assertEqual(item.old_bytes, item.path.read_bytes(), item.relative_path)

    def test_slice_b_t017_occupied_lock_blocks_before_batch_inspection(self):
        self._t017_seed_sentinels()
        candidate, prepared = self._prepared_family()
        before_targets = {
            item.relative_path: (item.path.read_bytes(), stat.S_IMODE(item.path.stat().st_mode),
                                 item.path.stat().st_mtime_ns)
            for item in candidate.files
        }
        record_before = prepared.record_path.read_bytes()
        before_outside = self._snapshot_outside_targets(candidate)
        before_external = self._t017_external_snapshot()
        marker = self.sandbox / "recovery inspection marker"
        owner_script = r'''
import sys
from pathlib import Path
from olympus import source_edit
lock = source_edit._acquire_lock(Path(sys.argv[1]), create=False)
print("LOCKED", flush=True)
sys.stdin.readline()
source_edit._release_lock(lock)
'''
        owner = subprocess.Popen(
            [sys.executable, "-B", "-c", owner_script, str(self.source)],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ready = queue.Queue()
        reader = threading.Thread(target=lambda: ready.put(owner.stdout.readline()), daemon=True)
        reader.start()
        owner_output = ("", "")
        try:
            try:
                line = ready.get(timeout=15)
            except queue.Empty:
                self.fail("T017 lock owner did not acquire the existing lock")
            self.assertEqual("LOCKED\n", line)
            contender_script = r'''
import sys
from pathlib import Path
from olympus import source_edit
marker = Path(sys.argv[2])
original = source_edit._record_context
def observed(*args, **kwargs):
    marker.write_text("inspected", encoding="utf-8")
    return original(*args, **kwargs)
source_edit._record_context = observed
try:
    source_edit._recover_batch(Path(sys.argv[1]))
except source_edit.BatchBlocked as error:
    print("BLOCKED", str(error))
    raise SystemExit(23)
raise SystemExit(0)
'''
            contender = subprocess.run(
                [sys.executable, "-B", "-c", contender_script, str(self.source), str(marker)],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"},
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.assertEqual(23, contender.returncode, contender.stdout + contender.stderr)
            self.assertIn("BLOCKED", contender.stdout)
            self.assertFalse(marker.exists(), "Recovery inspected the record while the native lock was occupied")
            self.assertEqual(before_targets, {
                item.relative_path: (item.path.read_bytes(), stat.S_IMODE(item.path.stat().st_mode),
                                     item.path.stat().st_mtime_ns)
                for item in candidate.files
            })
            self.assertEqual(record_before, prepared.record_path.read_bytes())
            self.assertEqual(before_external, self._t017_external_snapshot())
            self.assertTrue(prepared.record_path.is_file())
        finally:
            if owner.poll() is None:
                try:
                    owner.stdin.write("release\n")
                    owner.stdin.flush()
                except (BrokenPipeError, OSError):
                    owner.kill()
            try:
                owner_output = owner.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                owner.kill()
                owner_output = owner.communicate(timeout=10)

        self.assertEqual(0, owner.returncode, owner_output)
        self.assertEqual("rolled_back", source_edit._recover_batch(self.source))
        self._assert_targets_old(candidate)
        self.assertEqual(before_outside, self._snapshot_outside_targets(candidate))
        self.assertEqual(before_external, self._t017_external_snapshot())
        self.assertEqual("no_changes", source_edit._recover_batch(self.source))


class SliceBCLIIntegration(unittest.TestCase):
    """Public T018 dispatch tests; every writer targets a disposable source fixture."""

    def setUp(self):
        temp_root = Path(tempfile.gettempdir())
        preferred_temp = temp_root / "opencode"
        if preferred_temp.is_dir():
            temp_root = preferred_temp
        self.temporary = tempfile.TemporaryDirectory(
            prefix="olympus-cli-t018-space ñ-", dir=temp_root,
        )
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.source = self.sandbox / "source fixture ñ"
        self._make_source_fixture(self.source)
        self.env = os.environ.copy()
        self.env.update({
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
        })

    def _make_source_fixture(self, source):
        shutil.copytree(ROOT / "olympus", source / "olympus",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        scripts = source / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts/render_harnesses.py", scripts / "render_harnesses.py")
        shutil.copy2(ROOT / "install.ps1", source / "install.ps1")
        self.renderer = load_file("slice_b_t018_fixture_renderer", scripts / "render_harnesses.py")
        for path, content in self.renderer.outputs_for(source, "all").items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
        sentinel = source / ".opencode" / "unmanaged-fixture.sentinel"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(b"unmanaged fixture must remain byte-identical\n")

    def _run(self, *arguments, source=None, timeout=30):
        selected_source = self.source if source is None else source
        command = [sys.executable, "-B", "-m", "olympus", "--source", str(selected_source), *arguments]
        return subprocess.run(
            command, cwd=ROOT, env=self.env, capture_output=True, text=True,
            encoding="utf-8", check=False, timeout=timeout,
        )

    def _run_with_optional_imports_blocked(self, *arguments, block_editor=True,
                                            block_tomlkit=True, timeout=30):
        script = r'''
import builtins, importlib, os, sys
block_editor = os.environ.get("OLYMPUS_TEST_BLOCK_EDITOR") == "1"
block_tomlkit = os.environ.get("OLYMPUS_TEST_BLOCK_TOMLKIT") == "1"
original_import = builtins.__import__
def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if block_tomlkit and (name == "tomlkit" or name.startswith("tomlkit.")):
        raise ModuleNotFoundError("No module named 'tomlkit'")
    if block_editor and (name == "olympus.model_edit"
                         or name == "olympus" and "model_edit" in (fromlist or ())):
        raise AssertionError("Slice A/recovery attempted to import the Slice B model editor")
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = guarded_import
original_import_module = importlib.import_module
def guarded_import_module(name, package=None):
    if block_tomlkit and (name == "tomlkit" or name.startswith("tomlkit.")):
        raise ModuleNotFoundError("No module named 'tomlkit'")
    if block_editor and name == "olympus.model_edit":
        raise AssertionError("Slice A/recovery attempted to import the Slice B model editor")
    return original_import_module(name, package)
importlib.import_module = guarded_import_module
from olympus.cli import main
raise SystemExit(main(sys.argv[1:]))
'''
        env = self.env.copy()
        env["OLYMPUS_TEST_BLOCK_EDITOR"] = "1" if block_editor else "0"
        env["OLYMPUS_TEST_BLOCK_TOMLKIT"] = "1" if block_tomlkit else "0"
        return subprocess.run(
            [sys.executable, "-B", "-c", script, "--source", str(self.source), *arguments],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
            check=False, timeout=timeout,
        )

    def _call_main(self, *arguments):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from olympus import cli

        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(["--source", str(self.source), *arguments])
        return code, stdout.getvalue(), stderr.getvalue()

    def _model_edit(self):
        from olympus import model_edit
        return model_edit

    def _file_snapshot(self, source=None):
        root = self.source if source is None else source
        snapshot = {}
        for path in root.rglob("*"):
            if path.is_file():
                raw = path.read_bytes()
                metadata = path.stat()
                snapshot[path.relative_to(root).as_posix()] = (
                    hashlib.sha256(raw).hexdigest(), stat.S_IMODE(metadata.st_mode),
                    metadata.st_size, metadata.st_mtime_ns,
                )
        return snapshot

    def _assert_renderer_coherent(self):
        for path, content in self.renderer.outputs_for(self.source, "all").items():
            self.assertEqual(content.encode("utf-8"), path.read_bytes(), path.relative_to(self.source))

    def test_slice_b_t018_parser_rejects_invalid_surface_before_artifacts(self):
        before = self._file_snapshot()
        help_result = self._run("--help")
        self.assertEqual(0, help_result.returncode, help_result.stderr)
        for command in ("set-family", "set-model", "recover", "installed-target application is separate"):
            self.assertIn(command, help_result.stdout)
        self.assertEqual(before, self._file_snapshot())
        cases = (
            ("models", "set-family", "sol", "--opencode", "valid-id"),
            ("models", "set-family", "sol", "--opencode", "valid-id", "--codex", "valid-codex",
             "--json"),
            ("models", "set-family", "sol", "--opencode", "valid-id", "--codex", "valid-codex",
             "--scope", "project", "--target", str(self.sandbox)),
            ("agents", "set-model", "veyra"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = self._run(*arguments)
                self.assertEqual(2, result.returncode, (result.stdout, result.stderr))
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
                self.assertFalse((self.source / ".olympus-cli-edit").exists())
                self.assertEqual(before, self._file_snapshot())

        invalid_json = self._run(
            "models", "set-family", "sol", "--opencode", "valid-id", "--codex", "valid-codex", "--json",
        )
        self.assertEqual(2, invalid_json.returncode)
        error_doc = json.loads(invalid_json.stdout)
        self.assertEqual(1, error_doc["schema_version"])
        self.assertEqual("failed", error_doc["result"])
        self.assertIn("requires --dry-run", error_doc["issues"][0]["message"])
        self.assertEqual(before, self._file_snapshot())

    def test_slice_b_t018_preview_human_json_and_kael_aegis_are_read_only(self):
        before = self._file_snapshot()
        family = self._run(
            "models", "set-family", "sol", "--opencode", "openai/t018-sol", "--codex", "codex/t018-sol",
            "--dry-run", "--json",
        )
        self.assertEqual(0, family.returncode, family.stderr)
        preview = json.loads(family.stdout)
        self.assertEqual({"schema_version", "operation", "result", "context", "data", "issues"}, set(preview))
        self.assertEqual(1, preview["schema_version"])
        self.assertEqual("models set-family", preview["operation"])
        self.assertEqual("ok", preview["result"])
        self.assertEqual(14, len(preview["data"]["write_set"]))
        self.assertEqual("openai/t018-sol", preview["data"]["request"]["models"]["opencode"])
        self.assertEqual("codex/t018-sol", preview["data"]["request"]["models"]["codex"])

        human = self._run("agents", "set-model", "veyra", "--effort", "high", "--dry-run")
        self.assertEqual(0, human.returncode, human.stderr)
        self.assertIn("agents set-model: ok", human.stdout)
        self.assertIn("veyra", human.stdout)
        self.assertIn("write_set:", human.stdout)
        self.assertNotIn('"schema_version"', human.stdout)

        kael = self._run("agents", "set-model", "kael", "--family", "luna", "--effort", "max",
                         "--dry-run", "--json")
        aegis = self._run("agents", "set-model", "aegis", "--family", "sol", "--effort", "high",
                          "--dry-run", "--json")
        self.assertEqual(0, kael.returncode, kael.stderr)
        self.assertEqual(0, aegis.returncode, aegis.stderr)
        kael_row = json.loads(kael.stdout)["data"]["roles"][0]
        aegis_row = json.loads(aegis.stdout)["data"]["roles"][0]
        self.assertEqual("root", kael_row["representation"]["codex"])
        self.assertNotIn(".codex/agents/kael.toml", json.loads(kael.stdout)["data"]["write_set"])
        self.assertEqual("absent", aegis_row["representation"]["codex"])
        self.assertNotIn(".codex/agents/aegis.toml", json.loads(aegis.stdout)["data"]["write_set"])
        self.assertEqual(before, self._file_snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_t018_invalid_identifiers_and_drift_do_not_create_write_artifacts(self):
        before = self._file_snapshot()
        invalid = self._run(
            "models", "set-family", "sol", "--opencode", "bad id", "--codex", "valid-codex",
        )
        self.assertEqual(2, invalid.returncode, (invalid.stdout, invalid.stderr))
        self.assertEqual(before, self._file_snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

        drift = self.source / ".codex/agents/veyra.toml"
        original = drift.read_bytes()
        drift.write_bytes(original + b"# fixture drift\n")
        before_drift_command = self._file_snapshot()
        result = self._run(
            "models", "set-family", "sol", "--opencode", "openai/new-sol", "--codex", "codex-new",
        )
        self.assertEqual(3, result.returncode, (result.stdout, result.stderr))
        self.assertIn("drift", (result.stdout + result.stderr).lower())
        self.assertEqual(before_drift_command, self._file_snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_t018_explicit_commit_noop_and_unmanaged_file_preservation(self):
        initial_noop_before = self._file_snapshot()
        initial_noop = self._run(
            "models", "set-family", "sol", "--opencode", "openai/gpt-6.1-sol", "--codex", "gpt-6.1-sol",
        )
        self.assertEqual(0, initial_noop.returncode, (initial_noop.stdout, initial_noop.stderr))
        self.assertIn("execution: no_changes", initial_noop.stdout)
        self.assertEqual(initial_noop_before, self._file_snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

        preview_result = self._run(
            "models", "set-family", "sol", "--opencode", "openai/applied-sol", "--codex", "codex-applied-sol",
            "--dry-run", "--json",
        )
        self.assertEqual(0, preview_result.returncode, preview_result.stderr)
        preview = json.loads(preview_result.stdout)
        changed = set(preview["data"]["write_set"])
        before = self._file_snapshot()

        applied = self._run(
            "models", "set-family", "sol", "--opencode", "openai/applied-sol", "--codex", "codex-applied-sol",
        )
        self.assertEqual(0, applied.returncode, (applied.stdout, applied.stderr))
        self.assertIn("Execution preview (not yet applied):", applied.stdout)
        self.assertIn("execution: committed", applied.stdout)
        self.assertEqual(14, len(changed))
        self._assert_renderer_coherent()
        self.assertTrue((self.source / ".olympus-cli-edit.lock").is_file())
        self.assertEqual(0, (self.source / ".olympus-cli-edit.lock").stat().st_size)
        self.assertFalse((self.source / ".olympus-cli-edit").exists())
        after = self._file_snapshot()
        for relative, signature in before.items():
            if relative not in changed and relative != ".olympus-cli-edit.lock":
                self.assertEqual(signature, after.get(relative), relative)
        self.assertEqual("unmanaged fixture must remain byte-identical\n",
                         (self.source / ".opencode/unmanaged-fixture.sentinel").read_text(encoding="utf-8"))

        role_preview_result = self._run(
            "agents", "set-model", "veyra", "--family", "sol", "--effort", "high", "--dry-run", "--json",
        )
        self.assertEqual(0, role_preview_result.returncode, role_preview_result.stderr)
        role_write_set = set(json.loads(role_preview_result.stdout)["data"]["write_set"])
        self.assertEqual({"olympus/core/models.toml", ".opencode/agents/veyra.md", ".codex/agents/veyra.toml"},
                         role_write_set)
        role_apply = self._run("agents", "set-model", "veyra", "--family", "sol", "--effort", "high")
        self.assertEqual(0, role_apply.returncode, (role_apply.stdout, role_apply.stderr))
        self.assertIn("execution: committed", role_apply.stdout)
        self._assert_renderer_coherent()

        noop_before = self._file_snapshot()
        noop = self._run(
            "agents", "set-model", "veyra", "--family", "sol", "--effort", "high",
        )
        self.assertEqual(0, noop.returncode, (noop.stdout, noop.stderr))
        self.assertIn("execution: no_changes", noop.stdout)
        self.assertEqual(noop_before, self._file_snapshot())
        self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_t018_pending_scratch_blocks_without_overwrite_and_recovery_context_is_minimal(self):
        scratch = self.source / ".olympus-cli-edit"
        scratch.mkdir()
        marker = scratch / "unconfirmed.sentinel"
        marker.write_bytes(b"preserve unconfirmed evidence\n")
        before = self._file_snapshot()
        blocked = self._run(
            "agents", "set-model", "veyra", "--effort", "high",
        )
        self.assertEqual(3, blocked.returncode, (blocked.stdout, blocked.stderr))
        self.assertEqual(before, self._file_snapshot())
        self.assertEqual(b"preserve unconfirmed evidence\n", marker.read_bytes())
        self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())

        recovery_only = self.sandbox / "recovery without models"
        recovery_only.mkdir()
        recovery = self._run("config", "recover", source=recovery_only)
        self.assertEqual(3, recovery.returncode, (recovery.stdout, recovery.stderr))
        self.assertIn("Recovery requires the existing stable lock", recovery.stdout + recovery.stderr)
        self.assertNotIn("Invalid source: missing", recovery.stdout + recovery.stderr)
        self.assertFalse((recovery_only / ".olympus-cli-edit.lock").exists())

    def test_slice_b_t018_recovery_command_rolls_back_a_fixture_pending_batch(self):
        from olympus import source_edit

        candidate = self._model_edit()._build_set_family_candidate(
            self.source, "sol", "openai/recovery-sol", "codex/recovery-sol",
        )
        prepared = source_edit._prepare_batch(candidate)
        self.assertIsNotNone(prepared)
        lock = source_edit._acquire_lock(self.source, create=False)
        try:
            identity = source_edit._lock_identity(lock)
            for entry in prepared.record["files"][:3]:
                source_edit._lock_identity(lock, identity)
                os.replace(prepared.scratch_path / entry["staged"], self.source / entry["path"])
        finally:
            source_edit._release_lock(lock)
        self.assertEqual("PREPARED", json.loads(prepared.record_path.read_text(encoding="utf-8"))["state"])

        recovered = self._run("config", "recover")
        self.assertEqual(0, recovered.returncode, (recovered.stdout, recovered.stderr))
        self.assertIn("config recover: rolled_back", recovered.stdout)
        self.assertFalse(prepared.scratch_path.exists())
        for item in candidate.files:
            self.assertEqual(item.old_bytes, item.path.read_bytes(), item.relative_path)
            self.assertEqual(item.mode, stat.S_IMODE(item.path.stat().st_mode), item.relative_path)
        self._assert_renderer_coherent()
        self.assertEqual("no_changes", source_edit._recover_batch(self.source))

        # Also route an authoritative COMMITTED record with cleanup pending
        # through the public recovery command; the operation is confirmed only
        # after every managed output is already in the new renderer state.
        committed_candidate = self._model_edit()._build_set_family_candidate(
            self.source, "luna", "openai/committed-luna", "codex/committed-luna",
        )
        committed_prepared = source_edit._prepare_batch(committed_candidate)
        original_cleanup = source_edit._cleanup_batch

        def interrupt_committed_cleanup(source, lock, record, record_raw, record_metadata, *, final_state):
            if final_state == "new":
                raise OSError("fixture cleanup interruption after COMMITTED")
            return original_cleanup(source, lock, record, record_raw, record_metadata, final_state=final_state)

        from unittest.mock import patch
        with patch.object(source_edit, "_cleanup_batch", side_effect=interrupt_committed_cleanup):
            with self.assertRaises(source_edit.BatchBlocked):
                source_edit._commit_batch(committed_prepared)
        self.assertEqual("COMMITTED", json.loads(committed_prepared.record_path.read_text(encoding="utf-8"))["state"])

        original_remove = source_edit._remove_owned_file
        removed_backup = False

        def interrupt_recovery_cleanup(source, lock, relative, expected_hash, expected_mode):
            nonlocal removed_backup
            original_remove(source, lock, relative, expected_hash, expected_mode)
            if "/backups/" in relative.replace("\\", "/") and not removed_backup:
                removed_backup = True
                raise source_edit.BatchBlocked("fixture interruption during COMMITTED cleanup")

        with patch.object(source_edit, "_remove_owned_file", side_effect=interrupt_recovery_cleanup):
            recovery_code, recovery_stdout, recovery_stderr = self._call_main("config", "recover")
        self.assertTrue(removed_backup)
        self.assertEqual(4, recovery_code, recovery_stdout + recovery_stderr)
        self.assertIn("unconfirmed", recovery_stdout.lower())
        self.assertFalse((committed_prepared.scratch_path
                          / committed_prepared.record["files"][0]["backup"]).exists())
        self.assertTrue(committed_prepared.record_path.is_file())

        committed_recovery = self._run("config", "recover")
        self.assertEqual(0, committed_recovery.returncode, (committed_recovery.stdout, committed_recovery.stderr))
        self.assertIn("config recover: committed_cleanup", committed_recovery.stdout)
        self.assertFalse(committed_prepared.scratch_path.exists())
        self._assert_renderer_coherent()

    def test_slice_b_t018_busy_lock_blocks_public_recovery_and_preserves_batch(self):
        from olympus import source_edit

        candidate = self._model_edit()._build_set_family_candidate(
            self.source, "sol", "openai/contended-sol", "codex/contended-sol",
        )
        prepared = source_edit._prepare_batch(candidate)
        self.assertIsNotNone(prepared)
        record_before = prepared.record_path.read_bytes()
        targets_before = {item.relative_path: item.path.read_bytes() for item in candidate.files}
        owner_script = r'''
import sys
from pathlib import Path
from olympus import source_edit
lock = source_edit._acquire_lock(Path(sys.argv[1]), create=False)
print("LOCKED", flush=True)
sys.stdin.readline()
source_edit._release_lock(lock)
'''
        owner = subprocess.Popen(
            [sys.executable, "-B", "-c", owner_script, str(self.source)], cwd=ROOT,
            env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ready = queue.Queue()
        reader = threading.Thread(target=lambda: ready.put(owner.stdout.readline()), daemon=True)
        reader.start()
        owner_output = ("", "")
        try:
            try:
                self.assertEqual("LOCKED\n", ready.get(timeout=15))
            except queue.Empty:
                self.fail("T018 lock owner did not acquire the fixture's existing lock")
            blocked = self._run("config", "recover")
            self.assertEqual(3, blocked.returncode, (blocked.stdout, blocked.stderr))
            self.assertIn("blocked", blocked.stdout.lower())
            self.assertEqual(record_before, prepared.record_path.read_bytes())
            self.assertEqual(targets_before, {item.relative_path: item.path.read_bytes() for item in candidate.files})
            self.assertTrue(prepared.scratch_path.exists())
        finally:
            if owner.poll() is None:
                try:
                    owner.stdin.write("release\n")
                    owner.stdin.flush()
                except (BrokenPipeError, OSError):
                    owner.kill()
            try:
                owner_output = owner.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                owner.kill()
                owner_output = owner.communicate(timeout=10)
        self.assertEqual(0, owner.returncode, owner_output)
        self.assertEqual("rolled_back", source_edit._recover_batch(self.source))

    def test_slice_b_t018_confirmed_rollback_exit_1_and_unconfirmed_exit_4(self):
        from unittest.mock import patch
        from olympus import source_edit

        for unconfirmed in (False, True):
            with self.subTest(unconfirmed=unconfirmed):
                if unconfirmed:
                    shutil.rmtree(self.source)
                    self._make_source_fixture(self.source)
                candidate = self._model_edit()._build_set_family_candidate(
                    self.source, "sol", "openai/exit-sol", "codex/exit-sol",
                )
                fail_target = candidate.files[2].path
                original_replace = os.replace
                failed_initial = False
                failed_rollback = False

                def inject_commit_failure(source, destination):
                    nonlocal failed_initial, failed_rollback
                    source_path, destination_path = Path(source), Path(destination)
                    if destination_path == fail_target and source_path.name.endswith(".new") and not failed_initial:
                        failed_initial = True
                        raise OSError("fixture target replacement fault")
                    if (unconfirmed and "rollback-file-" in source_path.name
                            and not failed_rollback):
                        failed_rollback = True
                        raise OSError("fixture rollback replacement fault")
                    return original_replace(source, destination)

                before_targets = {item.relative_path: item.old_bytes for item in candidate.files}
                with patch.object(source_edit.os, "replace", side_effect=inject_commit_failure):
                    code, stdout, stderr = self._call_main(
                        "models", "set-family", "sol", "--opencode", "openai/exit-sol", "--codex", "codex/exit-sol",
                    )

                self.assertTrue(failed_initial)
                if unconfirmed:
                    self.assertTrue(failed_rollback)
                    self.assertEqual(4, code, stdout)
                    self.assertIn("unconfirmed", stdout.lower())
                    self.assertTrue((self.source / ".olympus-cli-edit").exists())
                    self.assertEqual("rolled_back", source_edit._recover_batch(self.source))
                else:
                    self.assertEqual(1, code, stdout)
                    self.assertIn("rollback was confirmed", stdout + stderr)
                self.assertEqual(before_targets,
                                 {item.relative_path: item.path.read_bytes() for item in candidate.files})
                self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_t018_slice_a_stays_independent_of_tomlkit_and_model_editor(self):
        script = r'''
import builtins, sys
original_import = builtins.__import__
def stdlib_only(name, *args, **kwargs):
    if name == "tomlkit" or name.startswith("tomlkit.") or name == "olympus.model_edit":
        raise AssertionError("Slice A imported an optional Slice B editor")
    return original_import(name, *args, **kwargs)
builtins.__import__ = stdlib_only
from olympus.cli import main
raise SystemExit(main(sys.argv[1:]))
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, "--source", str(self.source), "models", "list", "--json"],
            cwd=ROOT, env=self.env, capture_output=True, text=True, encoding="utf-8", check=False, timeout=20,
        )
        self.assertEqual(0, result.returncode, (result.stdout, result.stderr))
        self.assertEqual(12, len(json.loads(result.stdout)["data"]["roles"]))
        self.assertEqual("False", subprocess.run(
            [sys.executable, "-B", "-c",
             "import sys; import olympus.cli; print('tomlkit' in sys.modules)"]
            , cwd=ROOT, env=self.env, capture_output=True, text=True, encoding="utf-8", check=False,
        ).stdout.strip())

    def test_slice_b_t019_public_preview_write_sets_match_fixture_mutations(self):
        cases = (
            ("sol", ("models", "set-family", "sol", "--opencode", "openai/t019-sol",
                      "--codex", "codex/t019-sol"), 14),
            ("luna", ("models", "set-family", "luna", "--opencode", "openai/t019-luna",
                       "--codex", "codex/t019-luna"), 12),
            ("specialist", ("agents", "set-model", "veyra", "--family", "sol", "--effort", "high"), 3),
            ("kael", ("agents", "set-model", "kael", "--family", "luna", "--effort", "max"), {3, 4}),
            ("aegis", ("agents", "set-model", "aegis", "--family", "sol", "--effort", "high"), 2),
            ("no-op", ("models", "set-family", "sol", "--opencode", "openai/gpt-6.1-sol",
                        "--codex", "gpt-6.1-sol"), 0),
        )
        for label, command, expected_count in cases:
            with self.subTest(case=label):
                source = self.sandbox / f"write set {label} ñ"
                self._make_source_fixture(source)
                models_path = source / "olympus/core/models.toml"
                original_models = models_path.read_bytes()
                newline = b"\r\n" if b"\r\n" in original_models else b"\n"
                comment = "# T019 unrelated TOML trivia ñ".encode("utf-8") + newline
                models_path.write_bytes(comment + original_models)

                before_preview = self._file_snapshot(source)
                preview_result = self._run(*command, "--dry-run", "--json", source=source)
                self.assertEqual(0, preview_result.returncode, preview_result.stdout + preview_result.stderr)
                preview = json.loads(preview_result.stdout)
                write_set = set(preview["data"]["write_set"])
                self.assertIn(len(write_set), expected_count if isinstance(expected_count, set)
                              else {expected_count})
                self.assertEqual(before_preview, self._file_snapshot(source))
                self.assertFalse((source / ".olympus-cli-edit.lock").exists())
                self.assertFalse((source / ".olympus-cli-edit").exists())

                applied = self._run(*command, source=source)
                self.assertEqual(0, applied.returncode, applied.stdout + applied.stderr)
                after_apply = self._file_snapshot(source)
                actual_changed = {
                    relative for relative, signature in after_apply.items()
                    if relative != ".olympus-cli-edit.lock" and before_preview.get(relative) != signature
                }
                actual_changed.update(
                    relative for relative in before_preview
                    if relative not in after_apply and relative != ".olympus-cli-edit.lock"
                )
                self.assertEqual(write_set, actual_changed)
                self.assertEqual(len(write_set), len(actual_changed))
                self.assertTrue(models_path.read_bytes().startswith(comment))
                if write_set:
                    self.assertIn("execution: committed", applied.stdout)
                    self.assertTrue((source / ".olympus-cli-edit.lock").is_file())
                    self.assertEqual(0, (source / ".olympus-cli-edit.lock").stat().st_size)
                else:
                    self.assertIn("execution: no_changes", applied.stdout)
                    self.assertFalse((source / ".olympus-cli-edit.lock").exists())
                self.assertFalse((source / ".olympus-cli-edit").exists())
                for path, content in self.renderer.outputs_for(source, "all").items():
                    self.assertEqual(content.encode("utf-8"), path.read_bytes(), path.relative_to(source))

    def test_slice_b_t019_slice_a_entrypoints_are_read_only_without_editor(self):
        target = self.sandbox / "status target ñ"
        (target / ".git").mkdir(parents=True)
        (target / ".git" / "HEAD").write_text("ref: refs/heads/fixture\n", encoding="utf-8")
        target_sentinel = target / "unmanaged.sentinel"
        target_sentinel.write_bytes(b"status must remain read-only\n")

        def snapshot_tree(root):
            snapshot = {}
            for path in root.rglob("*"):
                if path.is_file():
                    raw = path.read_bytes()
                    metadata = path.stat()
                    snapshot[path.relative_to(root).as_posix()] = (
                        hashlib.sha256(raw).hexdigest(), stat.S_IMODE(metadata.st_mode),
                        metadata.st_size, metadata.st_mtime_ns,
                    )
            return snapshot

        target_before = snapshot_tree(target)
        source_before = self._file_snapshot()
        commands = (
            (("--help",), lambda result: self.assertIn("config recover", result.stdout)),
            (("--version",), lambda result: self.assertIn("olympus ", result.stdout)),
            (("models", "list", "--json"), lambda result: self.assertEqual(
                12, len(json.loads(result.stdout)["data"]["roles"]))),
            (("config", "check", "--json"), lambda result: self.assertTrue(
                json.loads(result.stdout)["data"]["coherent"])),
            (("status", "--scope", "project", "--target", str(target), "--json"),
             lambda result: self.assertEqual("absent", json.loads(result.stdout)["result"])),
        )
        for arguments, validate in commands:
            with self.subTest(arguments=arguments):
                result = self._run_with_optional_imports_blocked(*arguments)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                validate(result)
                self.assertEqual(source_before, self._file_snapshot())
                self.assertEqual(target_before, snapshot_tree(target))
                self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
                self.assertFalse((self.source / ".olympus-cli-edit").exists())

    def test_slice_b_t019_missing_editor_blocks_edits_and_recovery_is_stdlib_only(self):
        before_missing_dependency = self._file_snapshot()
        for arguments in (
            ("models", "set-family", "sol", "--opencode", "openai/missing-sol",
             "--codex", "codex/missing-sol", "--dry-run", "--json"),
            ("models", "set-family", "sol", "--opencode", "openai/missing-sol",
             "--codex", "codex/missing-sol"),
        ):
            with self.subTest(arguments=arguments):
                result = self._run_with_optional_imports_blocked(
                    *arguments, block_editor=False, block_tomlkit=True,
                )
                self.assertEqual(3, result.returncode, result.stdout + result.stderr)
                self.assertIn("tomlkit==0.13.3", result.stdout + result.stderr)
                self.assertEqual(before_missing_dependency, self._file_snapshot())
                self.assertFalse((self.source / ".olympus-cli-edit.lock").exists())
                self.assertFalse((self.source / ".olympus-cli-edit").exists())

        from olympus import source_edit
        candidate = self._model_edit()._build_set_family_candidate(
            self.source, "sol", "openai/recovery-sol", "codex/recovery-sol",
        )
        prepared = source_edit._prepare_batch(candidate)
        self.assertIsNotNone(prepared)
        lock = source_edit._acquire_lock(self.source, create=False)
        try:
            identity = source_edit._lock_identity(lock)
            for entry in prepared.record["files"][:3]:
                source_edit._lock_identity(lock, identity)
                os.replace(prepared.scratch_path / entry["staged"], self.source / entry["path"])
        finally:
            source_edit._release_lock(lock)

        recovered = self._run_with_optional_imports_blocked("config", "recover")
        self.assertEqual(0, recovered.returncode, recovered.stdout + recovered.stderr)
        self.assertIn("config recover: rolled_back", recovered.stdout)
        self.assertFalse((prepared.scratch_path).exists())
        self.assertTrue((self.source / ".olympus-cli-edit.lock").is_file())
        self.assertEqual(0, (self.source / ".olympus-cli-edit.lock").stat().st_size)
        self.assertFalse((self.source / ".olympus-cli-edit").exists())
        for item in candidate.files:
            self.assertEqual(item.old_bytes, item.path.read_bytes(), item.relative_path)
            self.assertEqual(item.mode, stat.S_IMODE(item.path.stat().st_mode), item.relative_path)
        self._assert_renderer_coherent()
        self.assertEqual("no_changes", source_edit._recover_batch(self.source))


if __name__ == "__main__":
    unittest.main()
