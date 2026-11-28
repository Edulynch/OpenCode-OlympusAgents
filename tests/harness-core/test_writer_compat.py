"""Focused manifest provenance and cross-language project-writer regressions."""

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
from olympus.install_manifest import (
    MANIFEST_PATHS,
    ManifestError,
    parse_project_manifest,
    read_project_manifest,
)

_WINDOWS_POWERSHELL_AVAILABLE = os.name == "nt" and shutil.which("pwsh") is not None


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
    [Console]::Out.WriteLine("IDENTITY=$($lock.Identity)")
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
        self.environment["OLYMPUS_CONFIG_FILE"] = str(self.sandbox / "fixture-preferences.json")
        self.pwsh = os.environ.get("OLYMPUS_TEST_POWERSHELL") or shutil.which("pwsh")
        self.helper = ROOT / "scripts/target-writer-lock.ps1"
        self.ps_lock_script = self.sandbox / "lock fixture.ps1"
        self.ps_lock_script.write_text(self._POWERSHELL_LOCK_SCRIPT, encoding="utf-8")

    def run_ps(self, script, *arguments, timeout=60, env=None):
        if not self.pwsh:
            self.skipTest("PowerShell 7 is unavailable")
        return subprocess.run([self.pwsh, "-NoProfile", "-File", str(script), *map(str, arguments)],
                              cwd=ROOT, env=self.environment if env is None else env, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout, check=False)

    def mock_opencode_environment(self):
        mock_bin = self.sandbox / "mock-opencode"
        mock_bin.mkdir(exist_ok=True)
        generated = []
        for file in sorted((self.target / ".opencode/agents").glob("*.md")):
            text = file.read_text(encoding="utf-8")
            model = __import__("re").search(r'(?m)^model:\s*"?([^"\s#]+)#([^"\s]+)"?\s*$', text)
            mode = __import__("re").search(r"(?m)^mode:\s*(primary|subagent)\s*$", text)
            if model is None or mode is None:
                continue
            provider, model_id = model.group(1).split("/", 1)
            generated.append({"id": file.stem, "model": {"providerID": provider, "id": model_id,
                                                           "variant": model.group(2)},
                              "mode": mode.group(1)})
        agents = self.sandbox / "mock-agents.json"
        agents.write_text(json.dumps(generated), encoding="utf-8")
        if os.name == "nt":
            (mock_bin / "opencode.cmd").write_text(
                "@echo off\r\n"
                "if \"%~1\"==\"--version\" goto version\r\n"
                "if \"%~1\"==\"debug\" if \"%~2\"==\"config\" exit /b 0\r\n"
                "if \"%~1\"==\"debug\" if \"%~2\"==\"agents\" goto agents\r\n"
                "exit /b 1\r\n"
                ":version\r\n"
                "echo opencode 1.0.0\r\nexit /b 0\r\n"
                ":agents\r\n"
                "type \"%OLYMPUS_TEST_AGENTS%\"\r\nexit /b 0\r\n",
                encoding="ascii",
            )
        else:
            mock_cli = mock_bin / "opencode"
            mock_cli.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "--version" ]; then echo "opencode 1.0.0"; exit 0; fi\n'
                'if [ "$1" = "debug" ] && [ "$2" = "config" ]; then exit 0; fi\n'
                'if [ "$1" = "debug" ] && [ "$2" = "agents" ]; then cat "$OLYMPUS_TEST_AGENTS"; exit $?; fi\n'
                "exit 1\n",
                encoding="utf-8",
            )
            mock_cli.chmod(0o755)
        environment = self.environment.copy()
        environment["PATH"] = str(mock_bin) + os.pathsep + environment.get("PATH", "")
        environment["OLYMPUS_TEST_AGENTS"] = str(agents)
        return environment

    @staticmethod
    def windows_short_path_alias(path):
        import ctypes

        short_path = ctypes.create_unicode_buffer(32768)
        get_short_path_name = ctypes.windll.kernel32.GetShortPathNameW
        get_short_path_name.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        get_short_path_name.restype = ctypes.c_uint32
        short_length = get_short_path_name(str(path), short_path, len(short_path))
        if not short_length or short_length >= len(short_path):
            return None

        candidate = Path(short_path.value)
        if os.path.normcase(os.path.abspath(str(candidate))) == os.path.normcase(
                os.path.abspath(str(path))):
            return None
        try:
            if not candidate.samefile(path):
                return None
        except OSError:
            return None
        return candidate

    def assert_manifest_provenance_via_target(self, target, provenance):
        manifest_path = self.create_managed_install(provenance=provenance)
        payload = manifest_path.read_bytes()
        alias_manifest = target / MANIFEST_PATHS[0]
        parsed = parse_project_manifest(target, alias_manifest, payload)
        self.assertEqual(provenance, parsed.data["harness_provenance"])
        self.assertEqual(provenance, read_project_manifest(target).data["harness_provenance"])

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

    def create_managed_install(self, provenance=None):
        # Rendered outputs and manifests exist only in this disposable Git fixture.
        renderer_path = ROOT / "scripts/render_harnesses.py"
        namespace = {"__file__": str(renderer_path)}
        exec(compile(renderer_path.read_bytes(), str(renderer_path), "exec"), namespace)
        entries = []
        outputs = namespace["outputs_for"](ROOT, "opencode")
        for path in outputs:
            relative = path.relative_to(ROOT).as_posix()
            # Development commands are shipped globally, not in project manifests.
            if relative.startswith(".opencode/commands/") or not (
                relative.startswith(".opencode/") or relative == "opencode.jsonc"
            ):
                continue
            # Bootstrap hashes checkout bytes, including their existing newline style.
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
            "installed_harnesses": ["opencode"],
            "managed_files": sorted(entries, key=lambda item: item["path"]),
        }
        if provenance is not None:
            manifest["harness_provenance"] = provenance
        manifest_path = self.target / MANIFEST_PATHS[0]
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

    def test_slice_c2_3_portable_manifest_schema_1_provenance_is_optional_opaque_metadata(self):
        manifest_path = self.create_managed_install()
        base = json.loads(manifest_path.read_text(encoding="utf-8"))
        parsed_without_provenance = parse_project_manifest(
            self.target, manifest_path, json.dumps(base).encode("utf-8"),
        )
        self.assertEqual(1, parsed_without_provenance.data["schema_version"])
        self.assertNotIn("metadata_format", parsed_without_provenance.data)
        self.assertNotIn("harness_provenance", parsed_without_provenance.data)

        provenance = {
            "opencode": {"kind": "custom", "source_digest": "a" * 64},
            "futureHarness": {"opaque": ["preserve", 1]},
        }
        current = {**base, "harness_provenance": provenance}
        parsed = parse_project_manifest(self.target, manifest_path, json.dumps(current).encode("utf-8"))
        self.assertEqual(1, parsed.data["schema_version"])
        self.assertEqual(provenance, parsed.data["harness_provenance"])

        manifest_path.write_text(json.dumps(current), encoding="utf-8")
        self.assertEqual(provenance, read_project_manifest(self.target).data["harness_provenance"])
        manifest_path.unlink()

        for invalid in ("not-an-object", {"opencode": "not-an-object"}):
            with self.subTest(invalid=invalid), self.assertRaises(ManifestError):
                parse_project_manifest(
                    self.target, manifest_path,
                    json.dumps({**base, "harness_provenance": invalid}).encode("utf-8"))

    def test_slice_c2_3_portable_manifest_provenance_accepts_canonical_target_alias(self):
        if os.name == "nt":
            alias_target = self.windows_short_path_alias(self.target)
            if alias_target is None:
                self.skipTest("SKIPPED: no distinct Windows 8.3 short-path alias is available")
        elif sys.platform == "darwin":
            lexical_target = Path(os.path.abspath(self.target))
            var = Path("/var")
            private_var = Path("/private/var")
            alias_target = None
            if lexical_target == var or lexical_target.is_relative_to(var):
                alias_target = private_var / lexical_target.relative_to(var)
            elif lexical_target == private_var or lexical_target.is_relative_to(private_var):
                alias_target = var / lexical_target.relative_to(private_var)
            if alias_target is None or not alias_target.exists() or not alias_target.samefile(self.target):
                # Keep canonical-alias coverage even on a host whose temporary
                # volume does not expose the conventional /var alias.
                alias_target = self.sandbox / "target alias"
                os.symlink(self.target, alias_target, target_is_directory=True)
        else:
            # Linux has no portable /var-style alias. A directory symlink
            # exercises the same resolve-before-containment contract.
            alias_target = self.sandbox / "target alias"
            os.symlink(self.target, alias_target, target_is_directory=True)

        self.assertNotEqual(
            os.path.normcase(str(alias_target)),
            os.path.normcase(str(self.target)),
            "Canonical-alias coverage requires a path distinct from the original target",
        )
        self.assertTrue(alias_target.samefile(self.target),
                        "Canonical alias must resolve to the original target")
        provenance = {"opencode": {"kind": "custom", "source_digest": "a" * 64}}
        self.assert_manifest_provenance_via_target(alias_target, provenance)

    def test_slice_c2_3_portable_project_manifest_rejects_codex_and_missing_current_metadata_read_only(self):
        manifest_path = self.create_managed_install()
        original = json.loads(manifest_path.read_text(encoding="utf-8"))
        before = self.snapshot_target()
        for invalid in (
            {**original, "installed_harnesses": ["codex"]},
            {key: value for key, value in original.items() if key != "installed_harnesses"},
            {key: value for key, value in original.items() if key != "installed_version"},
            {key: value for key, value in original.items() if key != "installed_from_commit"},
            {**original, "managed_files": [
                *original["managed_files"],
                {"path": ".codex/agents/veyra.toml", "sha256": "0" * 64},
            ]},
        ):
            with self.subTest(invalid=invalid.get("installed_harnesses", "missing-current-field")):
                payload = json.dumps(invalid).encode("utf-8")
                with self.assertRaises(ManifestError):
                    parse_project_manifest(self.target, manifest_path, payload)
                self.assertEqual(before, self.snapshot_target())

    def test_slice_c2_3_portable_manifest_rejects_symlink_escape(self):
        manifest_path = self.target / MANIFEST_PATHS[0]
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        outside_manifest = self.sandbox / "outside-manifest.json"
        outside_manifest.write_text(json.dumps({
            "schema_version": 1,
            "scope": "project",
            "installed_harnesses": ["opencode"],
            "installed_version": "local",
            "installed_from_commit": "fixture-commit",
            "managed_files": [],
            "harness_provenance": {"opencode": {"kind": "custom"}},
        }), encoding="utf-8")
        try:
            os.symlink(outside_manifest, manifest_path)
        except (OSError, NotImplementedError) as error:
            if os.name == "nt":
                self.skipTest(f"SKIPPED: Windows cannot create symlink safety fixture: {error}")
            raise

        try:
            for operation in (
                lambda: parse_project_manifest(
                    self.target, manifest_path, outside_manifest.read_bytes()),
                lambda: read_project_manifest(self.target),
            ):
                with self.subTest(operation=operation.__name__), self.assertRaises(ManifestError) as escaped:
                    operation()
                self.assertEqual("escaped", escaped.exception.code)
                self.assertTrue(escaped.exception.blocked)
        finally:
            manifest_path.unlink(missing_ok=True)

    @unittest.skipUnless(
        _WINDOWS_POWERSHELL_AVAILABLE,
        "Windows-only PowerShell integration; qualified by FAST / Windows.",
    )
    def test_slice_c2_3_windows_powershell_lock_interoperability_and_crash_release(self):
        # Both implementations contend on source_edit's stable OS-native lock.
        lock_path = self.target / ".olympus-cli-edit.lock"
        self.assertFalse(lock_path.exists())
        powershell_owner = self.start_powershell_owner()
        try:
            self.assertTrue(lock_path.is_file(), "PowerShell must create an initially absent lock")
            self.assertEqual(0, lock_path.stat().st_size)
            if os.name != "nt":
                powershell_identity = powershell_owner.stdout.readline().strip()
                python_stat = lock_path.stat()
                expected_identity = (
                    f"{python_stat.st_dev:016X}:{python_stat.st_ino:016X}"
                )
                self.assertEqual(f"IDENTITY={expected_identity}", powershell_identity)
                mode = lock_path.stat().st_mode & 0o777
                self.assertEqual(0o600, mode & 0o600,
                                 "A Unix lock created by PowerShell must remain owner-readable/writable")
                self.assertEqual(0, mode & 0o077,
                                 "A Unix stable lock must not grant group/other permissions")
            with self.assertRaises(source_edit.LockBusy):
                source_edit._acquire_lock(self.target, create=False)
        finally:
            self.stop_owner(powershell_owner, abrupt=True)

        python_after_initial_lock_crash = source_edit._acquire_lock(self.target, create=False)
        source_edit._release_lock(python_after_initial_lock_crash)

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

    @unittest.skipUnless(
        _WINDOWS_POWERSHELL_AVAILABLE,
        "Windows-only PowerShell integration; qualified by FAST / Windows.",
    )
    def test_slice_c2_3_windows_powershell_bootstrap_verify_only_is_read_only_with_opaque_provenance(self):
        provenance = {
            "opencode": {"kind": "custom", "source_digest": "b" * 64},
            "codex": {"historical": True},
            "futureHarness": {"opaque": ["preserve", 1]},
        }
        manifest_path = self.create_managed_install(provenance=provenance)
        self.assertFalse((self.target / ".olympus-cli-edit.lock").exists())
        before = self.snapshot_target()
        verify = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                             "-Harness", "opencode", "-VerifyOnly", env=self.mock_opencode_environment())
        self.assertEqual(0, verify.returncode, verify.stdout + verify.stderr)
        self.assertIn("OLYMPUS_VERIFY: local PASS", verify.stdout)
        self.assertFalse((self.target / ".olympus-cli-edit.lock").exists(),
                         "VerifyOnly must not create a target writer lock")
        self.assertEqual(before, self.snapshot_target())
        self.assertEqual(provenance, json.loads(manifest_path.read_text(encoding="utf-8"))["harness_provenance"])

    def test_slice_c2_3_portable_manifest_rejects_malformed_provenance_without_writes(self):
        manifest_path = self.create_managed_install()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["harness_provenance"] = {"historical": "not-an-object"}
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        before = self.snapshot_target()

        with self.assertRaises(ManifestError):
            read_project_manifest(self.target)
        self.assertFalse((self.target / ".olympus-cli-edit.lock").exists())
        self.assertEqual(before, self.snapshot_target())

    @unittest.skipUnless(
        _WINDOWS_POWERSHELL_AVAILABLE,
        "Windows-only PowerShell integration; qualified by FAST / Windows.",
    )
    def test_slice_c2_3_windows_powershell_uninstall_removes_only_managed_resources(self):
        old_manifest = self.create_managed_install()
        sentinel = self.target / "unmanaged.txt"
        sentinel.write_text("user-owned\n", encoding="utf-8")
        nested = self.target / "nested-project-path"
        nested.mkdir()
        before_nested_rejection = self.snapshot_target()
        nested_result = self.run_ps(ROOT / "scripts/project-uninstall.ps1", "-Target", nested,
                                     "-Harness", "opencode")
        self.assertNotEqual(0, nested_result.returncode)
        self.assertIn("UNSAFE_TARGET", nested_result.stdout + nested_result.stderr)
        self.assertEqual(before_nested_rejection, self.snapshot_target())

        result = self.run_ps(ROOT / "scripts/project-uninstall.ps1", "-Target", self.target,
                             "-Harness", "opencode")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("user-owned\n", sentinel.read_text(encoding="utf-8"))
        self.assertFalse(old_manifest.exists())
        self.assertTrue((self.target / ".olympus-cli-edit.lock").is_file())
        self.assertEqual(0, (self.target / ".olympus-cli-edit.lock").stat().st_size)

    @unittest.skipUnless(
        _WINDOWS_POWERSHELL_AVAILABLE,
        "Windows-only PowerShell integration; qualified by FAST / Windows.",
    )
    def test_slice_c2_3_windows_powershell_existing_project_writers_block_before_target_writes(self):
        self.create_managed_install()
        mock_environment = self.mock_opencode_environment()
        owner = self.start_python_owner()
        try:
            before = self.snapshot_target(omit_lock=True)
            bootstrap = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                                    "-Harness", "opencode", "-Update", env=mock_environment)
            self.assertNotEqual(0, bootstrap.returncode)
            self.assertIn("OLYMPUS_TARGET_LOCK_BUSY", bootstrap.stderr + bootstrap.stdout)
            uninstall = self.run_ps(ROOT / "scripts/project-uninstall.ps1", "-Target", self.target,
                                    "-Harness", "opencode", env=mock_environment)
            self.assertNotEqual(0, uninstall.returncode)
            self.assertIn("OLYMPUS_TARGET_LOCK_BUSY", uninstall.stderr + uninstall.stdout)
            self.assertEqual(before, self.snapshot_target(omit_lock=True))
        finally:
            self.stop_owner(owner)

    def test_slice_c3_portable_project_apply_uses_existing_target_writer_lock(self):
        self.create_managed_install({"opencode": {"kind": "custom"}})
        owner = self.start_python_owner()
        try:
            before = self.snapshot_target(omit_lock=True)
            apply = subprocess.run(
                [sys.executable, "-B", "-m", "olympus", "config", "apply", "--scope", "project",
                 "--target", str(self.target), "--harness", "opencode", "--execute"],
                cwd=ROOT, env=self.environment, capture_output=True, text=True,
                encoding="utf-8", timeout=30, check=False,
            )
            self.assertEqual(3, apply.returncode, apply.stdout + apply.stderr)
            self.assertIn("stable target writer lock", apply.stdout + apply.stderr)
            self.assertEqual(before, self.snapshot_target(omit_lock=True))
            self.assertFalse((self.target / ".olympus-cli-config-apply").exists())
        finally:
            self.stop_owner(owner)

    @unittest.skipUnless(
        _WINDOWS_POWERSHELL_AVAILABLE,
        "Windows-only PowerShell integration; qualified by FAST / Windows.",
    )
    def test_slice_c2_3_windows_powershell_rejected_bootstrap_is_target_read_only_and_does_not_create_lock(self):
        self.create_managed_install()
        managed = self.target / ".opencode/agents/veyra.md"
        managed.write_text("user-modified content\n", encoding="utf-8")
        before = self.snapshot_target()

        result = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                             "-Harness", "opencode", env=self.mock_opencode_environment())

        self.assertNotEqual(0, result.returncode)
        self.assertIn("MANAGED_FILE_DRIFT", result.stdout + result.stderr)
        self.assertFalse((self.target / ".olympus-cli-edit.lock").exists())
        self.assertEqual(before, self.snapshot_target())

    @unittest.skipUnless(
        _WINDOWS_POWERSHELL_AVAILABLE,
        "Windows-only PowerShell integration; qualified by FAST / Windows.",
    )
    def test_slice_c2_3_windows_powershell_rejected_uninstall_is_target_read_only_and_does_not_create_lock(self):
        obsolete = self.target / ".codex/orchestrator-install.json"
        obsolete.parent.mkdir(parents=True, exist_ok=True)
        obsolete.write_text(json.dumps({
            "schema_version": 1, "scope": "project", "installed_harnesses": ["codex"],
            "installed_version": "v0.7.0", "installed_from_commit": "old-commit",
            "managed_files": [],
        }) + "\n", encoding="utf-8")
        before = self.snapshot_target()

        result = self.run_ps(ROOT / "scripts/project-uninstall.ps1", "-Target", self.target,
                             "-Harness", "opencode")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("PROJECT_MANIFEST_INVALID", result.stdout + result.stderr)
        self.assertFalse((self.target / ".olympus-cli-edit.lock").exists())
        self.assertEqual(before, self.snapshot_target())

    @unittest.skipUnless(
        _WINDOWS_POWERSHELL_AVAILABLE,
        "Windows-only PowerShell integration; qualified by FAST / Windows.",
    )
    def test_slice_c2_3_windows_powershell_bootstrap_noop_does_not_modify_target(self):
        self.create_managed_install()
        mock_environment = self.mock_opencode_environment()
        first = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                            "-Harness", "opencode", env=mock_environment)
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        lock_path = self.target / ".olympus-cli-edit.lock"
        self.assertTrue(lock_path.is_file())
        # Simulate an older valid installation without a lock; the no-op must
        # not create one. The previous bootstrap process has already exited.
        lock_path.unlink()
        before = self.snapshot_target()

        second = self.run_ps(ROOT / "scripts/bootstrap.ps1", "-Target", self.target,
                             "-Harness", "opencode", env=mock_environment)

        self.assertEqual(0, second.returncode, second.stdout + second.stderr)
        self.assertIn("NO_CHANGES", second.stdout)
        self.assertFalse(lock_path.exists())
        self.assertEqual(before, self.snapshot_target())

    @unittest.skipUnless(
        _WINDOWS_POWERSHELL_AVAILABLE,
        "Windows-only PowerShell integration; qualified by FAST / Windows.",
    )
    def test_slice_c2_3_windows_powershell_writer_lock_rejects_symlink_lockfile(self):
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

    @unittest.skipUnless(
        _WINDOWS_POWERSHELL_AVAILABLE,
        "Windows-only PowerShell integration; qualified by FAST / Windows.",
    )
    def test_slice_c2_3_windows_powershell_writer_lock_rejects_hardlinked_lockfile(self):
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
