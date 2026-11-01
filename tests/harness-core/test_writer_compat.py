"""Focused Slice C2.3 provenance and Python/PowerShell writer regressions."""

from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympus import source_edit
from olympus.install_manifest import ManifestError, parse_project_manifest


class SliceC2_3WriterCompatibility(unittest.TestCase):
    _PYTHON_LOCK_HOLDER = r'''
import sys
from pathlib import Path
from olympus import source_edit

lock = source_edit._acquire_lock(Path(sys.argv[1]), create=True)
print("LOCKED", flush=True)
try:
    sys.stdin.readline()
finally:
    source_edit._release_lock(lock)
'''
    _POWERSHELL_LOCK_SCRIPT = r'''
param([string]$HelperPath, [string]$Target, [string]$Mode)
$ErrorActionPreference = 'Stop'
. $HelperPath
$lock = $null
try {
    $lock = Enter-OlympusTargetWriterLock $Target
    [Console]::Out.WriteLine('LOCKED')
    [Console]::Out.Flush()
    if ($Mode -eq 'hold') { [Console]::In.ReadLine() | Out-Null }
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 23
} finally {
    if ($null -ne $lock) { Exit-OlympusTargetWriterLock $lock }
}
'''

    def setUp(self):
        temp_root = Path(tempfile.gettempdir()) / "opencode"
        if not temp_root.is_dir():
            temp_root = Path(tempfile.gettempdir())
        self.temporary = tempfile.TemporaryDirectory(prefix="olympus-cli-c2-3-fixture-",
                                                     dir=temp_root)
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.target = self.sandbox / "target project"
        self.target.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.target)], check=True,
                       capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.environment = os.environ.copy()
        self.environment["PYTHONPATH"] = str(ROOT)
        self.environment["PYTHONDONTWRITEBYTECODE"] = "1"
        self.environment["PYTHONUTF8"] = "1"
        self.pwsh = os.environ.get("OLYMPUS_TEST_POWERSHELL") or shutil.which("pwsh")
        self.helper = ROOT / "scripts/target-writer-lock.ps1"
        self.ps_lock_script = self.sandbox / "lock fixture.ps1"
        self.ps_lock_script.write_text(self._POWERSHELL_LOCK_SCRIPT, encoding="utf-8")

    def run_ps(self, script, *arguments, timeout=60):
        if not self.pwsh:
            self.skipTest("PowerShell 7 is unavailable")
        return subprocess.run([self.pwsh, "-NoProfile", "-File", str(script), *map(str, arguments)],
                              cwd=ROOT, env=self.environment, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout, check=False)

    def snapshot_target(self, *, omit_lock=False):
        snapshot = {}
        lock_path = self.target / ".olympus-cli-edit.lock"
        for path in self.target.rglob("*"):
            if omit_lock and path == lock_path:
                continue
            relative = path.relative_to(self.target).as_posix()
            metadata = path.stat()
            if path.is_file():
                snapshot[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest(), metadata.st_mtime_ns)
            else:
                snapshot[relative] = ("directory", metadata.st_mtime_ns)
        return snapshot

    def create_managed_install(self, harnesses=("opencode", "codex"), provenance=None):
        # Rendered outputs and manifests exist only in this disposable Git fixture.
        renderer_path = ROOT / "scripts/render_harnesses.py"
        namespace = {"__file__": str(renderer_path)}
        exec(compile(renderer_path.read_bytes(), str(renderer_path), "exec"), namespace)
        entries = []
        for harness in harnesses:
            outputs = namespace["outputs_for"](ROOT, harness)
            for path, content in outputs.items():
                relative = path.relative_to(ROOT).as_posix()
                if not (relative.startswith(f".{harness}/") or relative in ("opencode.jsonc", "CODEX.md")):
                    continue
                # Bootstrap's verifier hashes the generated checkout bytes,
                # including its existing newline style; reuse those bytes.
                raw = (ROOT / relative).read_bytes()
                destination = self.target / Path(relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
                entries.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest()})
        manifest = {
            "schema_version": 1,
            "scope": "project",
            "installed_version": "local",
            "installed_from_commit": "fixture-commit",
            "installed_harnesses": list(harnesses),
            "managed_files": sorted(entries, key=lambda item: item["path"]),
        }
        if provenance is not None:
            manifest["harness_provenance"] = provenance
        manifest_path = (self.target / (".opencode" if "opencode" in harnesses else ".codex") /
                         "orchestrator-install.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        return manifest_path

    def start_python_owner(self):
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", self._PYTHON_LOCK_HOLDER, str(self.target)],
            cwd=ROOT, env=self.environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
        )
        first_line = queue.Queue()
        reader = threading.Thread(target=lambda: first_line.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            line = first_line.get(timeout=15)
        except queue.Empty:
            process.kill()
            process.communicate(timeout=5)
            self.fail("Python lock owner did not acquire within 15 seconds")
        if line.strip() != "LOCKED":
            stdout, stderr = process.communicate(timeout=5)
            self.fail(f"Python lock owner failed: {line!r} {stdout!r} {stderr!r}")
        return process

    def start_powershell_owner(self):
        if not self.pwsh:
            self.skipTest("PowerShell 7 is unavailable")
        process = subprocess.Popen(
            [self.pwsh, "-NoProfile", "-File", str(self.ps_lock_script), str(self.helper),
             str(self.target), "hold"],
            cwd=ROOT, env=self.environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
        )
        first_line = queue.Queue()
        reader = threading.Thread(target=lambda: first_line.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            line = first_line.get(timeout=15)
        except queue.Empty:
            process.kill()
            process.communicate(timeout=5)
            self.fail("PowerShell lock owner did not acquire within 15 seconds")
        if line.strip() != "LOCKED":
            stdout, stderr = process.communicate(timeout=5)
            self.fail(f"PowerShell lock owner failed: {line!r} {stdout!r} {stderr!r}")
        return process

    @staticmethod
    def stop_owner(process, *, abrupt=False):
        if abrupt:
            process.kill()
        elif process.poll() is None:
            process.stdin.write("release\n")
            process.stdin.flush()
        stdout, stderr = process.communicate(timeout=10)
        if not abrupt and process.returncode != 0:
            raise AssertionError(f"Lock owner failed: {stdout!r} {stderr!r}")

    def test_slice_c2_3_manifest_schema_1_provenance_is_optional_opaque_metadata(self):
        manifest_path = self.target / ".opencode/orchestrator-install.json"
        manifest_path.parent.mkdir(parents=True)
        base = {
            "schema_version": 1,
            "scope": "project",
            "installed_harnesses": ["opencode"],
            "installed_version": "local",
            "installed_from_commit": "fixture-commit",
            "managed_files": [],
        }
        legacy = parse_project_manifest(self.target, manifest_path, json.dumps(base).encode("utf-8"))
        self.assertEqual(1, legacy.data["schema_version"])
        self.assertNotIn("harness_provenance", legacy.data)

        provenance = {
            "opencode": {"kind": "custom", "source_digest": "a" * 64},
            "futureHarness": {"opaque": ["preserve", 1]},
        }
        current = {**base, "harness_provenance": provenance}
        parsed = parse_project_manifest(self.target, manifest_path, json.dumps(current).encode("utf-8"))
        self.assertEqual(1, parsed.data["schema_version"])
        self.assertEqual(provenance, parsed.data["harness_provenance"])

        for invalid in ("not-an-object", {"opencode": "not-an-object"}):
            with self.subTest(invalid=invalid), self.assertRaises(ManifestError):
                parse_project_manifest(
                    self.target, manifest_path,
                    json.dumps({**base, "harness_provenance": invalid}).encode("utf-8"))

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_python_powershell_lock_interoperability_and_crash_release(self):
        # Both implementations contend on source_edit's stable OS-native lock.
        python_owner = self.start_python_owner()
        try:
            contender = self.run_ps(self.ps_lock_script, self.helper, self.target, "try")
            self.assertEqual(23, contender.returncode, contender.stdout + contender.stderr)
            self.assertIn("OLYMPUS_TARGET_LOCK_BUSY", contender.stderr)
        finally:
            self.stop_owner(python_owner)

        ps_after_python_release = self.run_ps(self.ps_lock_script, self.helper, self.target, "try")
        self.assertEqual(0, ps_after_python_release.returncode,
                         ps_after_python_release.stdout + ps_after_python_release.stderr)

        python_owner = self.start_python_owner()
        try:
            contender = self.run_ps(self.ps_lock_script, self.helper, self.target, "try")
            self.assertEqual(23, contender.returncode, contender.stdout + contender.stderr)
            self.assertIn("OLYMPUS_TARGET_LOCK_BUSY", contender.stderr)
        finally:
            self.stop_owner(python_owner, abrupt=True)

        ps_after_python_crash = self.run_ps(self.ps_lock_script, self.helper, self.target, "try")
        self.assertEqual(0, ps_after_python_crash.returncode, ps_after_python_crash.stdout + ps_after_python_crash.stderr)

        powershell_owner = self.start_powershell_owner()
        try:
            with self.assertRaises(source_edit.LockBusy):
                source_edit._acquire_lock(self.target, create=False)
        finally:
            self.stop_owner(powershell_owner)

        python_after_powershell_release = source_edit._acquire_lock(self.target, create=False)
        source_edit._release_lock(python_after_powershell_release)

        powershell_owner = self.start_powershell_owner()
        try:
            with self.assertRaises(source_edit.LockBusy):
                source_edit._acquire_lock(self.target, create=False)
        finally:
            self.stop_owner(powershell_owner, abrupt=True)

        python_after_powershell_crash = source_edit._acquire_lock(self.target, create=False)
        try:
            lock_path = self.target / ".olympus-cli-edit.lock"
            self.assertTrue(lock_path.is_file())
            self.assertEqual(0, lock_path.stat().st_size)
        finally:
            source_edit._release_lock(python_after_powershell_crash)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_bootstrap_preserves_unselected_provenance_and_verify_only_is_read_only(self):
        provenance = {
            "opencode": {"kind": "custom", "source_digest": "b" * 64},
            "codex": {"kind": "custom", "source_digest": "c" * 64},
            "futureHarness": {"opaque": "preserve"},
            "FutureHarness": {"opaque": "preserve-distinct-case"},
            "OpenCode": {"opaque": "preserve-distinct-harness-key"},
        }
        manifest_path = self.create_managed_install(provenance=provenance)
        before_verify = self.snapshot_target()
        verify = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                             "-Harness", "codex", "-VerifyOnly")
        self.assertEqual(0, verify.returncode, verify.stdout + verify.stderr)
        self.assertIn("OLYMPUS_VERIFY: local PASS", verify.stdout)
        self.assertFalse((self.target / ".olympus-cli-edit.lock").exists(),
                         "VerifyOnly must not create a target writer lock")
        self.assertEqual(before_verify, self.snapshot_target())

        install = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                              "-Harness", "codex")
        self.assertEqual(0, install.returncode, install.stdout + install.stderr)
        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(1, updated["schema_version"])
        self.assertEqual({"opencode": provenance["opencode"],
                          "futureHarness": provenance["futureHarness"],
                          "FutureHarness": provenance["FutureHarness"],
                          "OpenCode": provenance["OpenCode"]},
                         updated["harness_provenance"])
        self.assertNotIn("codex", updated["harness_provenance"],
                         "Bootstrap must not assert official provenance for rewritten output")
        lock_path = self.target / ".olympus-cli-edit.lock"
        self.assertTrue(lock_path.is_file())
        self.assertEqual(0, lock_path.stat().st_size)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_verify_only_rejects_malformed_provenance_without_writes(self):
        manifest_path = self.create_managed_install(("codex",))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["harness_provenance"] = {"codex": "not-an-object"}
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        before = self.snapshot_target()

        verify = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                             "-Harness", "codex", "-VerifyOnly")

        self.assertNotEqual(0, verify.returncode)
        self.assertIn("INSTALL_MANIFEST_INCOMPATIBLE", verify.stdout + verify.stderr)
        self.assertFalse((self.target / ".olympus-cli-edit.lock").exists())
        self.assertEqual(before, self.snapshot_target())

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_uninstall_removes_only_selected_harness_provenance(self):
        provenance = {
            "opencode": {"kind": "custom", "source_digest": "d" * 64},
            "codex": {"kind": "custom", "source_digest": "e" * 64},
            "futureHarness": {"opaque": "preserve"},
            "FutureHarness": {"opaque": "preserve-distinct-case"},
            "OpenCode": {"opaque": "preserve-distinct-harness-key"},
        }
        old_manifest = self.create_managed_install(provenance=provenance)
        sentinel = self.target / "unmanaged.txt"
        sentinel.write_text("user-owned\n", encoding="utf-8")
        result = self.run_ps(ROOT / "scripts/project-uninstall.ps1", "-Target", self.target,
                             "-Harness", "opencode")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

        remaining_manifest = self.target / ".codex/orchestrator-install.json"
        self.assertTrue(remaining_manifest.is_file())
        updated = json.loads(remaining_manifest.read_text(encoding="utf-8"))
        self.assertEqual(1, updated["schema_version"])
        self.assertEqual(["codex"], updated["installed_harnesses"])
        self.assertEqual({"codex": provenance["codex"],
                          "futureHarness": provenance["futureHarness"],
                          "FutureHarness": provenance["FutureHarness"],
                          "OpenCode": provenance["OpenCode"]},
                         updated["harness_provenance"])
        self.assertEqual("user-owned\n", sentinel.read_text(encoding="utf-8"))
        self.assertFalse(old_manifest.exists())
        self.assertTrue((self.target / ".olympus-cli-edit.lock").is_file())
        self.assertEqual(0, (self.target / ".olympus-cli-edit.lock").stat().st_size)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_existing_project_writers_block_before_target_writes(self):
        self.create_managed_install(("codex",))
        owner = self.start_python_owner()
        try:
            before = self.snapshot_target(omit_lock=True)
            bootstrap = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                                    "-Harness", "codex")
            self.assertNotEqual(0, bootstrap.returncode)
            self.assertIn("OLYMPUS_TARGET_LOCK_BUSY", bootstrap.stderr)
            uninstall = self.run_ps(ROOT / "scripts/project-uninstall.ps1", "-Target", self.target,
                                    "-Harness", "codex")
            self.assertNotEqual(0, uninstall.returncode)
            self.assertIn("OLYMPUS_TARGET_LOCK_BUSY", uninstall.stderr)
            self.assertEqual(before, self.snapshot_target(omit_lock=True))
        finally:
            self.stop_owner(owner)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_rejected_bootstrap_is_target_read_only_and_does_not_create_lock(self):
        self.create_managed_install(("codex",))
        managed = self.target / "CODEX.md"
        managed.write_text("user-modified content\n", encoding="utf-8")
        before = self.snapshot_target()

        result = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                             "-Harness", "codex")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("MANAGED_FILE_DRIFT", result.stdout + result.stderr)
        self.assertFalse((self.target / ".olympus-cli-edit.lock").exists())
        self.assertEqual(before, self.snapshot_target())

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_rejected_uninstall_is_target_read_only_and_does_not_create_lock(self):
        self.create_managed_install(("codex",))
        before = self.snapshot_target()

        result = self.run_ps(ROOT / "scripts/project-uninstall.ps1", "-Target", self.target,
                             "-Harness", "opencode")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("HARNESS_NOT_INSTALLED", result.stdout + result.stderr)
        self.assertFalse((self.target / ".olympus-cli-edit.lock").exists())
        self.assertEqual(before, self.snapshot_target())

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_bootstrap_noop_does_not_modify_target(self):
        self.create_managed_install(("codex",))
        first = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                            "-Harness", "codex")
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        lock_path = self.target / ".olympus-cli-edit.lock"
        self.assertTrue(lock_path.is_file())
        # Simulate an older valid installation without a lock; the no-op must
        # not create one. The previous bootstrap process has already exited.
        lock_path.unlink()
        before = self.snapshot_target()

        second = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                             "-Harness", "codex")

        self.assertEqual(0, second.returncode, second.stdout + second.stderr)
        self.assertIn("NO_CHANGES", second.stdout)
        self.assertFalse(lock_path.exists())
        self.assertEqual(before, self.snapshot_target())

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_writer_lock_rejects_symlink_lockfile(self):
        lock_path = self.target / ".olympus-cli-edit.lock"
        external = self.sandbox / "outside-lock-target"
        external.write_text("outside\n", encoding="utf-8")
        try:
            os.symlink(external, lock_path)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Host cannot create a symlink safety fixture: {error}")
        before = external.read_bytes()

        result = self.run_ps(self.ps_lock_script, self.helper, self.target, "try")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("OLYMPUS_TARGET_LOCK_UNSAFE", result.stdout + result.stderr)
        self.assertEqual(before, external.read_bytes())
        self.assertTrue(lock_path.is_symlink())

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is unavailable")
    def test_slice_c2_3_writer_lock_rejects_hardlinked_lockfile(self):
        lock_path = self.target / ".olympus-cli-edit.lock"
        external = self.sandbox / "outside-lock-target"
        external.write_bytes(b"")
        try:
            os.link(external, lock_path)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Host cannot create a hard-link safety fixture: {error}")

        result = self.run_ps(self.ps_lock_script, self.helper, self.target, "try")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("OLYMPUS_TARGET_LOCK_UNSAFE", result.stdout + result.stderr)
        self.assertEqual(0, external.stat().st_size)
        self.assertEqual(2, external.stat().st_nlink)


if __name__ == "__main__":
    unittest.main()
