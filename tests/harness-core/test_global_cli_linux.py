"""Disposable-fixture checks for the Linux per-user CLI package coordinator."""

from __future__ import annotations

import errno
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympus import config_apply_transaction, global_cli, global_install, source_edit
from olympus.cli import load_renderer, release_version


def _extended_posix_acl_xattr() -> bytes:
    undefined = 0xFFFFFFFF
    named_user = (os.getuid() + 1) & undefined
    entries = (
        (0x01, 0x06, undefined), (0x02, 0x04, named_user),
        (0x04, 0x04, undefined), (0x10, 0x04, undefined),
        (0x20, 0x00, undefined),
    )
    return struct.pack("<I", 0x0002) + b"".join(
        struct.pack("<HHI", *entry) for entry in entries
    )


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux CLI package lifecycle requires Linux.")
class LinuxGlobalCli(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="olympus-global-cli-")
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.home = self.sandbox / "home"
        self.home.mkdir()
        self.data = self.sandbox / "xdg-data"
        self.preferences = self.sandbox / "xdg-config" / "olympus" / "config.json"
        self.preferences.parent.mkdir(parents=True)
        self.preference_bytes = b'{"schema_version":1,"overrides":{}}\n'
        self.preferences.write_bytes(self.preference_bytes)
        self.global_root = self.sandbox / "opencode"
        self.outside = self.sandbox / "outside-checkout"
        self.outside.mkdir()
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "XDG_DATA_HOME": str(self.data),
            "XDG_CONFIG_HOME": str(self.preferences.parents[1]),
            "OPENCODE_CONFIG_DIR": str(self.global_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
        }
        for name in ("PYTHONPATH", "OLYMPUS_PYTHON", "OLYMPUS_CONFIG_FILE", "OLYMPUS_CONFIG_HOME"):
            self.env.pop(name, None)
        self.enterContext(mock.patch.dict(os.environ, self.env, clear=True))
        self.v1 = release_version(ROOT)
        self.v2 = self._next_version(self.v1)
        self.commit1 = "a" * 40
        self.commit2 = "b" * 40

    @staticmethod
    def _next_version(version: str) -> str:
        parts = version.removeprefix("v").split(".")
        major, minor, patch = (int(item) for item in parts[:3])
        return f"v{major}.{minor}.{patch + 1}"

    def _source(self, name: str, version: str, *, change_kael: bool = False) -> Path:
        source = self.sandbox / name
        shutil.copytree(
            ROOT / "olympus", source / "olympus",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        scripts = source / "scripts"
        scripts.mkdir()
        for filename in ("render_harnesses.py", "olympus_cli.py", "olympus", "launch-latest.py"):
            shutil.copy2(ROOT / "scripts" / filename, scripts / filename)
        (scripts / "side-loaded.py").write_text("not repository-owned\n", encoding="utf-8")
        (source / "olympus/unlisted_module.py").write_text("not repository-owned\n", encoding="utf-8")
        (source / "olympus/core/unlisted.json").write_text("{}\n", encoding="utf-8")
        (scripts / "launch-latest.ps1").write_text("not part of the Linux package\n", encoding="utf-8")

        install_text = (ROOT / "install.ps1").read_text(encoding="utf-8")
        current = release_version(ROOT)
        install_text = install_text.replace(f"$Version = '{current}'", f"$Version = '{version}'", 1)
        install_text = install_text.replace(f"$ReleaseVersion = '{current}'", f"$ReleaseVersion = '{version}'", 1)
        (source / "install.ps1").write_text(install_text, encoding="utf-8")

        if change_kael:
            models = source / "olympus/core/models.toml"
            original = models.read_text(encoding="utf-8")
            changed = original.replace(
                '[roles.kael]\nfamily = "sol"',
                '[roles.kael]\nfamily = "luna"',
                1,
            )
            if changed == original:
                raise AssertionError("Fixture did not find the canonical Kael family input.")
            models.write_text(changed, encoding="utf-8")

        renderer = load_renderer(source)
        for path, content in renderer.outputs_for(source, "opencode").items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        (source / "olympus/__pycache__").mkdir()
        (source / "olympus/__pycache__/ignored.py").write_text("ignored\n", encoding="utf-8")
        (source / "olympus/secrets").mkdir()
        (source / "olympus/secrets/ignored.py").write_text("ignored\n", encoding="utf-8")
        (source / ".git").mkdir()
        (source / "tests").mkdir()
        (source / "tests/ignored.py").write_text("ignored\n", encoding="utf-8")
        return source

    def _run(self, source: Path, version: str, commit: str):
        return global_cli.install(source, version=version, commit=commit)

    def _snapshot(self, root: Path | None) -> dict[str, tuple]:
        if root is None or not root.exists():
            return {}
        result = {}
        for path in [root, *sorted(root.rglob("*"))]:
            metadata = path.lstat()
            relative = "." if path == root else path.relative_to(root).as_posix()
            if path.is_file():
                result[relative] = (
                    "file", path.read_bytes(), metadata.st_mode, metadata.st_mtime_ns,
                    metadata.st_dev, metadata.st_ino,
                )
            elif path.is_dir():
                result[relative] = (
                    "directory", metadata.st_mode, metadata.st_mtime_ns,
                    metadata.st_dev, metadata.st_ino,
                )
            else:
                result[relative] = ("other", metadata.st_mode, metadata.st_mtime_ns)
        return result

    def _scope_snapshot(self, *sources: Path) -> dict[str, dict[str, tuple]]:
        return {str(path): self._snapshot(path) for path in sources}

    def _require_acl_free_fixture(self, *roots: Path) -> None:
        if not hasattr(os, "listxattr"):
            self.skipTest("mode-only force repair requires Linux ACL xattr inspection")
        unsupported = {
            getattr(errno, name, None) for name in ("ENOTSUP", "EOPNOTSUPP", "ENOSYS")
        } - {None}
        for root in roots:
            candidates = [root, *(path for path in root.rglob("*"))]
            for path in candidates:
                try:
                    attributes = set(os.listxattr(path))
                except OSError as error:
                    if error.errno in unsupported:
                        self.skipTest("mode-only force repair requires ACL-capable fixture storage")
                    raise
                if attributes & {"system.posix_acl_access", "system.posix_acl_default"}:
                    self.skipTest("mode-only force repair fixture already has POSIX ACL policy")

    def test_fresh_package_runs_externally_and_omits_unowned_assets(self):
        source = self._source("source-v1", self.v1)
        before_source = self._snapshot(source)
        outcome = self._run(source, self.v1, self.commit1)
        self.assertEqual(("install", "committed"), (outcome.operation, outcome.result))

        launcher = self.home / ".local/bin/olympus"
        package = self.data / "olympus/versions" / self.v1
        receipt = json.loads((package / global_cli._RECEIPT).read_text(encoding="utf-8"))
        paths = {entry["path"] for entry in receipt["files"]}
        generated = global_cli._generated_paths(
            package, load_renderer(package),
            {Path(item).stem for item in global_cli._ROLE_INPUTS},
        )
        expected_paths = set(global_cli._PACKAGE_INPUTS) | set(generated)
        self.assertEqual(expected_paths, paths, "receipt must match the exact repository-owned inventory")
        self.assertEqual(
            set(global_cli._PYTHON_INPUTS),
            {path for path in paths if path.startswith("olympus/") and path.endswith(".py")},
        )
        self.assertIn("scripts/launch-latest.py", paths)
        self.assertEqual(16, len(generated), "generated renderer inventory must remain canonical")
        self.assertEqual(
            {".opencode/commands/olympus.ultra.md", ".opencode/commands/olympus.performance.md",
             ".opencode/commands/olympus.performance-ultra.md"},
            {path for path in generated if path.startswith(".opencode/commands/")},
        )
        for unlisted in (
            "scripts/side-loaded.py",
            "olympus/unlisted_module.py", "olympus/core/unlisted.json",
            "olympus/__pycache__/ignored.py", "olympus/secrets/ignored.py",
            "tests/ignored.py",
        ):
            self.assertNotIn(unlisted, paths)
        self.assertNotIn("scripts/launch-latest.ps1", paths)
        self.assertNotIn("olympus/README.md", paths)
        self.assertFalse(any(path.startswith("tests/") or path.startswith(".git/") for path in paths))
        self.assertEqual(before_source, self._snapshot(source), "staging changed its immutable source")
        self.assertEqual(self.preference_bytes, self.preferences.read_bytes())

        python3 = shutil.which("python3")
        self.assertIsNotNone(python3, "stock python3 is required for the external launcher test")
        probe = subprocess.run(
            [python3, "-c", "import sys; raise SystemExit(sys.version_info < (3, 11))"],
            env=self.env, capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(0, probe.returncode, "external launcher test requires Python 3.11+")
        result = subprocess.run(
            [str(launcher), "version"], cwd=self.outside, env=self.env,
            capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual([f"olympus {self.v1}"], result.stdout.splitlines())
        self.assertEqual("", result.stderr)

        identity = global_cli.recorded_identity()
        self.assertEqual((self.v1, self.commit1), (identity.version, identity.commit))
        self.assertEqual("verified", global_cli.verify(
            version=self.v1, commit=self.commit1,
        ).result)

    def test_atomic_package_publication_failure_keeps_stage_and_never_falls_back(self):
        versions_root = self.sandbox / "versions"
        versions_root.mkdir()
        staging_name = ".staging-" + "c" * 32
        staged = versions_root / staging_name
        staged.mkdir()
        payload = staged / "sentinel"
        payload.write_bytes(b"preserve staged package\n")
        versions_root, versions_identity = global_cli._ensure_directory(
            versions_root, create=False,
        )
        lock = source_edit._acquire_lock(versions_root, create=True)
        syscall = mock.Mock(return_value=-1)
        libc = mock.Mock()
        libc.renameat2 = syscall
        try:
            lock_identity = source_edit._lock_identity(lock)
            with (
                mock.patch("olympus.global_cli.ctypes.CDLL", return_value=libc),
                mock.patch("olympus.global_cli.ctypes.get_errno", return_value=errno.ENOSYS),
                mock.patch(
                    "olympus.global_cli.os.rename",
                    side_effect=AssertionError("ordinary rename fallback is forbidden"),
                ),
            ):
                with self.assertRaises(global_cli.GlobalCliError) as caught:
                    global_cli._publish_package_noreplace(
                        versions_root, staging_name, self.v1, versions_identity,
                        lock, lock_identity,
                    )
            self.assertEqual(4, caught.exception.code)
            self.assertIn("Atomic no-replace", str(caught.exception))
            syscall.assert_called_once()
            self.assertEqual(1, syscall.call_args.args[-1])
            self.assertEqual(b"preserve staged package\n", payload.read_bytes())
            self.assertFalse((versions_root / self.v1).exists())
        finally:
            source_edit._release_lock(lock)

    def test_existing_launcher_and_version_collisions_are_never_overwritten(self):
        source = self._source("source-v1", self.v1)
        bin_root = self.home / ".local/bin"
        bin_root.mkdir(parents=True)
        launcher = bin_root / "olympus"
        launcher.write_bytes(b"user-owned executable\n")
        before = launcher.read_bytes()
        with self.assertRaises(global_cli.GlobalCliError):
            self._run(source, self.v1, self.commit1)
        self.assertEqual(before, launcher.read_bytes())
        self.assertFalse(self.global_root.exists())
        self.assertFalse((self.data / "olympus").exists())

        launcher.unlink()
        data_root = self.data / "olympus"
        collision = data_root / "versions" / self.v1
        collision.mkdir(parents=True)
        user_file = collision / "keep.txt"
        user_file.write_bytes(b"not ours\n")
        with self.assertRaisesRegex(global_cli.GlobalCliError, "refusing adoption or overwrite"):
            self._run(source, self.v1, self.commit1)
        self.assertEqual(b"not ours\n", user_file.read_bytes())
        self.assertFalse(self.global_root.exists())

    def test_upgrade_same_identity_noop_and_mismatched_markers(self):
        first = self._source("source-v1", self.v1)
        second = self._source("source-v2", self.v2, change_kael=True)
        same_version_changed = self._source(
            "source-v1-different", self.v1, change_kael=True,
        )
        self._run(first, self.v1, self.commit1)

        data_root = self.data / "olympus"
        launcher = self.home / ".local/bin"
        tracked = (data_root, launcher, self.global_root, self.preferences.parent, first)
        before = self._scope_snapshot(*tracked)
        self.assertEqual("no_changes", global_cli.install(
            first, version=self.v1, commit=self.commit1,
        ).result)
        self.assertEqual("no_changes", global_cli.update(
            first, version=self.v1, commit=self.commit1,
        ).result)
        self.assertEqual(before, self._scope_snapshot(*tracked))

        with self.assertRaisesRegex(global_cli.GlobalCliError, "differs from the installed package"):
            global_cli.update(same_version_changed, version=self.v1, commit=self.commit1)
        self.assertEqual(before, self._scope_snapshot(*tracked))

        upgraded = global_cli.update(second, version=self.v2, commit=self.commit2)
        self.assertEqual(("committed", self.v2, self.commit2),
                         (upgraded.result, upgraded.version, upgraded.commit))
        self.assertTrue((data_root / "versions" / self.v1).is_dir())
        self.assertTrue((data_root / "versions" / self.v2).is_dir())
        installed = global_cli.recorded_identity()
        self.assertEqual((self.v2, self.commit2), (installed.version, installed.commit))
        with self.assertRaises(global_cli.GlobalCliError):
            global_cli.verify(version=self.v2, commit=self.commit1)

    def test_force_same_latest_repairs_receipt_owned_package_launcher_and_global_files(self):
        source = self._source("source-v1", self.v1)
        self._run(source, self.v1, self.commit1)
        data_root = self.data / "olympus"
        package = data_root / "versions" / self.v1
        self._require_acl_free_fixture(
            package, data_root, self.home / ".local/bin", self.global_root,
        )

        earlier_package_file = package / "olympus/cli.py"
        earlier_expected = earlier_package_file.read_bytes()
        earlier_package_file.chmod(0o644)
        earlier_package_file.write_bytes(b"earlier damaged package resource\n")
        earlier_package_file.chmod(0o444)
        package_file = package / "olympus/global_cli.py"
        expected_package_file = package_file.read_bytes()
        package_file.chmod(0o644)
        package_file.write_bytes(b"damaged package resource\n")
        package_file.chmod(0o444)
        missing_package_file = package / "olympus/doctor.py"
        package_file_parent = missing_package_file.parent
        package_file_parent_mode = stat.S_IMODE(package_file_parent.stat().st_mode)
        try:
            package_file_parent.chmod(package_file_parent_mode | stat.S_IWUSR)
            missing_package_file.unlink()
        finally:
            package_file_parent.chmod(package_file_parent_mode)

        global_file = self.global_root / "agents/kael.md"
        global_file.write_bytes(b"damaged global resource\n")
        missing_global_file = self.global_root / "commands/olympus.ultra.md"
        expected_global = missing_global_file.read_bytes()
        missing_global_file.unlink()
        launcher = self.home / ".local/bin/olympus"
        launcher.write_bytes(b"damaged stable launcher\n")
        user_note = data_root / "user-note.txt"
        user_note.write_bytes(b"preserve user data\n")
        preferences_before = self.preferences.read_bytes()

        real_replace = os.replace
        replacements = []

        def interrupt_after_first_package_replace(source_path, destination_path):
            destination = Path(destination_path)
            if destination in {earlier_package_file, package_file}:
                replacements.append(destination)
                if destination == package_file:
                    raise OSError("fixture package ACL-safe repair interruption")
            return real_replace(source_path, destination_path)

        with mock.patch("olympus.global_cli.os.replace", side_effect=interrupt_after_first_package_replace):
            with self.assertRaisesRegex(
                global_cli.GlobalCliError, "Cannot atomically restore CLI package resource",
            ):
                global_cli.update(source, version=self.v1, commit=self.commit1, force=True)
        self.assertEqual([earlier_package_file, package_file], replacements)
        self.assertEqual(earlier_expected, earlier_package_file.read_bytes())
        self.assertEqual(b"damaged package resource\n", package_file.read_bytes())
        self.assertTrue(missing_package_file.is_file())

        retry_source = self._source("source-v1-retry", self.v1)
        repaired = global_cli.update(
            retry_source, version=self.v1, commit=self.commit1, force=True,
        )
        self.assertEqual(("committed", self.v1, self.commit1),
                         (repaired.result, repaired.version, repaired.commit))
        self.assertEqual(expected_package_file, package_file.read_bytes())
        self.assertTrue(missing_package_file.is_file())
        self.assertNotEqual(b"damaged global resource\n", global_file.read_bytes())
        self.assertEqual(expected_global, missing_global_file.read_bytes())
        self.assertEqual(global_cli._launcher_bytes(data_root), launcher.read_bytes())
        self.assertEqual(b"preserve user data\n", user_note.read_bytes())
        self.assertEqual(preferences_before, self.preferences.read_bytes())
        self.assertEqual("verified", global_cli.verify(
            version=self.v1, commit=self.commit1,
        ).result)
        self.assertEqual("verified", global_install.verify(
            retry_source, version=self.v1, commit=self.commit1,
        ).result)
        launcher.unlink()
        restored_launcher = global_cli.update(
            retry_source, version=self.v1, commit=self.commit1, force=True,
        )
        self.assertEqual("committed", restored_launcher.result)
        self.assertEqual(global_cli._launcher_bytes(data_root), launcher.read_bytes())
        no_op = global_cli.update(retry_source, version=self.v1, commit=self.commit1, force=True)
        self.assertEqual(("no_changes", ()), (no_op.result, no_op.changed_paths))

    def test_force_repair_preserves_unknown_package_files_and_fails_closed(self):
        source = self._source("source-v1", self.v1)
        self._run(source, self.v1, self.commit1)
        package = self.data / "olympus/versions" / self.v1
        package.chmod(0o755)
        unknown = package / "user-owned-note.txt"
        unknown.write_bytes(b"keep\n")
        package.chmod(0o555)
        before = self._scope_snapshot(
            package, self.home / ".local/bin", self.global_root,
        )

        with self.assertRaises(global_cli.GlobalCliError):
            global_cli.update(source, version=self.v1, commit=self.commit1, force=True)
        self.assertEqual(b"keep\n", unknown.read_bytes())
        self.assertEqual(
            before,
            self._scope_snapshot(package, self.home / ".local/bin", self.global_root),
        )

    @unittest.skipUnless(sys.platform.startswith("linux"), "native POSIX ACL xattrs require Linux.")
    def test_force_preflights_later_package_acl_before_earlier_replacement_or_mode_change(self):
        source = self._source("source-v1", self.v1)
        self._run(source, self.v1, self.commit1)
        package = self.data / "olympus/versions" / self.v1
        earlier = package / "olympus/cli.py"
        later = package / "olympus/global_cli.py"
        earlier.chmod(0o644)
        earlier.write_bytes(b"earlier package drift\n")
        earlier.chmod(0o444)
        later.chmod(0o644)
        later.write_bytes(b"later package drift\n")
        later.chmod(0o444)
        try:
            os.setxattr(later, "system.posix_acl_access", _extended_posix_acl_xattr())
        except OSError as error:
            unsupported = {
                getattr(errno, name, None) for name in ("ENOTSUP", "EOPNOTSUPP", "ENOSYS", "EPERM")
            } - {None}
            if error.errno in unsupported:
                self.skipTest("fixture storage/user cannot create POSIX access ACL xattrs")
            raise
        self.assertIn("system.posix_acl_access", os.listxattr(later))
        before = self._scope_snapshot(
            package, self.home / ".local/bin", self.global_root,
        )

        with self.assertRaisesRegex(global_install.GlobalInstallError, "access-ACL-bearing"):
            global_cli.update(source, version=self.v1, commit=self.commit1, force=True)

        self.assertEqual(
            before,
            self._scope_snapshot(package, self.home / ".local/bin", self.global_root),
        )
        self.assertEqual(b"earlier package drift\n", earlier.read_bytes())
        self.assertEqual(b"later package drift\n", later.read_bytes())
        self.assertIn("system.posix_acl_access", os.listxattr(later))

    @unittest.skipUnless(sys.platform.startswith("linux"), "native POSIX ACL xattrs require Linux.")
    def test_force_rejects_package_stage_parent_default_acl_before_any_repair(self):
        source = self._source("source-v1", self.v1)
        self._run(source, self.v1, self.commit1)
        package = self.data / "olympus/versions" / self.v1
        managed = package / "olympus/global_cli.py"
        managed.chmod(0o644)
        managed.write_bytes(b"managed package drift\n")
        managed.chmod(0o444)
        versions_root = package.parent
        try:
            os.setxattr(
                versions_root, "system.posix_acl_default", _extended_posix_acl_xattr(),
            )
        except OSError as error:
            unsupported = {
                getattr(errno, name, None) for name in ("ENOTSUP", "EOPNOTSUPP", "ENOSYS", "EPERM")
            } - {None}
            if error.errno in unsupported:
                self.skipTest("fixture storage/user cannot create POSIX default ACL xattrs")
            raise
        self.assertIn("system.posix_acl_default", os.listxattr(versions_root))
        before = self._scope_snapshot(
            package, self.home / ".local/bin", self.global_root,
        )

        with self.assertRaisesRegex(global_install.GlobalInstallError, "default-ACL-bearing"):
            global_cli.update(source, version=self.v1, commit=self.commit1, force=True)

        self.assertEqual(
            before,
            self._scope_snapshot(package, self.home / ".local/bin", self.global_root),
        )
        self.assertEqual(b"managed package drift\n", managed.read_bytes())
        self.assertIn("system.posix_acl_default", os.listxattr(versions_root))

    @unittest.skipUnless(sys.platform.startswith("linux"), "native POSIX ACL xattrs require Linux.")
    def test_force_preflights_launcher_parent_default_acl_before_any_managed_repair(self):
        source = self._source("source-v1", self.v1)
        self._run(source, self.v1, self.commit1)
        data_root = self.data / "olympus"
        package = data_root / "versions" / self.v1
        bin_root = self.home / ".local/bin"
        self._require_acl_free_fixture(data_root, bin_root, self.global_root)

        global_file = self.global_root / "agents/kael.md"
        global_file.write_bytes(b"managed global drift\n")
        package_file = package / "olympus/cli.py"
        package_file.chmod(0o644)
        package_file.write_bytes(b"managed package drift\n")
        package_file.chmod(0o444)
        launcher = bin_root / "olympus"
        launcher_sentinel = b"preserve launcher sentinel\n"
        launcher.write_bytes(launcher_sentinel)

        try:
            os.setxattr(
                bin_root, "system.posix_acl_default", _extended_posix_acl_xattr(),
            )
        except OSError as error:
            unsupported = {
                getattr(errno, name, None) for name in ("ENOTSUP", "EOPNOTSUPP", "ENOSYS", "EPERM")
            } - {None}
            if error.errno in unsupported:
                self.skipTest("fixture storage/user cannot create POSIX default ACL xattrs")
            raise
        self.assertIn("system.posix_acl_default", os.listxattr(bin_root))

        before = self._scope_snapshot(data_root, bin_root, self.global_root)
        current_before = (data_root / global_cli._CURRENT).read_bytes()
        receipt_before = (package / global_cli._RECEIPT).read_bytes()
        manifest_before = (self.global_root / global_install._MANIFEST).read_bytes()

        with self.assertRaisesRegex(global_install.GlobalInstallError, "default-ACL-bearing"):
            global_cli.update(source, version=self.v1, commit=self.commit1, force=True)

        self.assertEqual(before, self._scope_snapshot(data_root, bin_root, self.global_root))
        self.assertEqual(launcher_sentinel, launcher.read_bytes())
        self.assertEqual(b"managed global drift\n", global_file.read_bytes())
        self.assertEqual(b"managed package drift\n", package_file.read_bytes())
        self.assertEqual(current_before, (data_root / global_cli._CURRENT).read_bytes())
        self.assertEqual(receipt_before, (package / global_cli._RECEIPT).read_bytes())
        self.assertEqual(manifest_before, (self.global_root / global_install._MANIFEST).read_bytes())
        self.assertIn("system.posix_acl_default", os.listxattr(bin_root))

    def test_force_repairs_acl_free_package_directory_mode_without_file_drift(self):
        source = self._source("source-v1", self.v1)
        self._run(source, self.v1, self.commit1)
        package = self.data / "olympus/versions" / self.v1
        self._require_acl_free_fixture(
            package, self.data / "olympus", self.home / ".local/bin", self.global_root,
        )
        managed_directory = package / "olympus"
        managed_directory.chmod(0o755)

        repaired = global_cli.update(
            source, version=self.v1, commit=self.commit1, force=True,
        )

        self.assertEqual("committed", repaired.result)
        self.assertEqual(0o555, stat.S_IMODE(managed_directory.stat().st_mode))
        self.assertIn(str(managed_directory), repaired.changed_paths)
        self.assertEqual("verified", global_cli.verify(
            version=self.v1, commit=self.commit1,
        ).result)

    def test_force_newer_upgrade_resumes_after_global_commit_before_cli_activation(self):
        source_v1 = self._source("source-v1", self.v1)
        self._run(source_v1, self.v1, self.commit1)
        self._require_acl_free_fixture(
            self.data / "olympus", self.home / ".local/bin", self.global_root,
        )
        source_v2 = self._source("source-v2", self.v2)
        real_update = global_install.update

        def commit_then_interrupt(*args, **kwargs):
            real_update(*args, **kwargs)
            raise RuntimeError("fixture interruption after global commit")

        with mock.patch(
            "olympus.global_cli.global_install.update", side_effect=commit_then_interrupt,
        ):
            with self.assertRaisesRegex(RuntimeError, "after global commit"):
                global_cli.update(
                    source_v2, version=self.v2, commit=self.commit2, force=True,
                )

        previous = global_cli._read_state(self.data / "olympus", self.home / ".local/bin")
        self.assertEqual((self.v1, self.commit1), (previous.version, previous.commit))
        self.assertEqual((self.v2, self.commit2), global_cli._global_identity_without_package())
        resumed = global_cli.update(
            source_v2, version=self.v2, commit=self.commit2, force=True,
        )

        self.assertEqual("committed", resumed.result)
        self.assertEqual("verified", global_cli.verify(
            version=self.v2, commit=self.commit2,
        ).result)
        self.assertEqual("verified", global_install.verify(
            source_v2, version=self.v2, commit=self.commit2,
        ).result)
        self.assertFalse(config_apply_transaction.pending(self.global_root))

    def test_uninstall_preserves_user_xdg_preferences_and_unknown_siblings(self):
        source = self._source("source-v1", self.v1)
        self._run(source, self.v1, self.commit1)
        data_root = self.data / "olympus"
        versions = data_root / "versions"
        bin_root = self.home / ".local/bin"
        sibling = versions / "user-owned-version"
        sibling.mkdir()
        note = sibling / "note.txt"
        note.write_bytes(b"preserve sibling\n")
        data_note = data_root / "user-note.json"
        data_note.write_bytes(b"preserve data\n")
        other_command = bin_root / "other-tool"
        other_command.write_bytes(b"preserve bin sibling\n")
        before_preferences = self.preferences.read_bytes()

        removed = global_cli.uninstall(version=self.v1, commit=self.commit1)
        self.assertEqual(("uninstall", "committed"), (removed.operation, removed.result))
        self.assertFalse((versions / self.v1).exists())
        self.assertFalse((data_root / "current").exists())
        self.assertFalse((bin_root / "olympus").exists())
        self.assertEqual(b"preserve sibling\n", note.read_bytes())
        self.assertEqual(b"preserve data\n", data_note.read_bytes())
        self.assertEqual(b"preserve bin sibling\n", other_command.read_bytes())
        self.assertEqual(before_preferences, self.preferences.read_bytes())
        self.assertIsNone(global_cli.recorded_identity())
        self.assertTrue((data_root / source_edit._LOCK_NAME).is_file())

    def test_uninstall_preflight_and_pending_cleanup_resume_preserve_exact_ownership(self):
        source = self._source("source-v1", self.v1)
        self._run(source, self.v1, self.commit1)
        data_root = self.data / "olympus"
        package = data_root / "versions" / self.v1
        versions = data_root / "versions"
        launcher = self.home / ".local/bin/olympus"
        current = data_root / "current"
        manifest = self.global_root / "olympus/orchestrator-install.json"
        cleanup_record = data_root / global_cli._CLEANUP_RECORD
        sibling = versions / "user-owned-version"
        sibling.mkdir()
        sibling_note = sibling / "note.txt"
        sibling_note.write_bytes(b"preserve sibling\n")
        receipt = package / global_cli._RECEIPT
        before_receipt = receipt.read_bytes()
        launcher_bytes = launcher.read_bytes()

        launcher.write_bytes(b"changed local launcher\n")
        with self.assertRaises(global_cli.GlobalCliError):
            global_cli.uninstall(version=self.v1, commit=self.commit1)
        self.assertTrue(manifest.is_file(), "invalid local state must not start global uninstall")
        self.assertTrue(current.is_file())
        launcher.write_bytes(launcher_bytes)

        real_unlink = os.unlink
        package_unlinks = []

        def fail_package_cleanup(path, *args, **kwargs):
            try:
                relative = Path(path).relative_to(package).as_posix()
            except ValueError:
                return real_unlink(path, *args, **kwargs)
            if len(package_unlinks) == 1:
                raise OSError("fixture cleanup interruption")
            package_unlinks.append(relative)
            return real_unlink(path, *args, **kwargs)

        with mock.patch("olympus.global_cli.os.unlink", side_effect=fail_package_cleanup):
            with self.assertRaises(global_cli.GlobalCliError) as caught:
                global_cli.uninstall(version=self.v1, commit=self.commit1)
        self.assertEqual(4, caught.exception.code)
        self.assertIn("cleanup remains pending", str(caught.exception))
        self.assertEqual(1, len(package_unlinks), "fixture should stop after one payload file was pruned")
        self.assertFalse(launcher.exists(), "launcher reference must be retired before payload pruning")
        self.assertFalse(current.exists(), "current reference must be retired before payload pruning")
        self.assertFalse(manifest.exists(), "global uninstall must not be blindly rolled back")
        self.assertEqual(before_receipt, receipt.read_bytes(), "receipt is retained as recovery evidence")
        self.assertFalse((package / package_unlinks[0]).exists())
        self.assertTrue(cleanup_record.is_file())
        cleanup_data = json.loads(cleanup_record.read_text(encoding="utf-8"))
        self.assertEqual((self.v1, self.commit1, global_cli._digest(before_receipt)),
                         (cleanup_data["version"], cleanup_data["commit"],
                          cleanup_data["receipt_sha256"]))
        self.assertNotIn("package_root", cleanup_data, "record must derive only the canonical version path")
        self.assertTrue((data_root / source_edit._LOCK_NAME).is_file())

        foreign = package / "unowned-note.txt"
        foreign.write_bytes(b"preserve foreign package data\n")
        with self.assertRaises(global_cli.GlobalCliError):
            global_cli.uninstall(version=self.v1, commit=self.commit1)
        self.assertEqual(b"preserve foreign package data\n", foreign.read_bytes())
        self.assertEqual(before_receipt, receipt.read_bytes())
        foreign.unlink()

        pending_snapshot = self._scope_snapshot(data_root, self.home / ".local/bin", self.global_root)
        with self.assertRaisesRegex(global_cli.GlobalCliError, "cleanup.*pending"):
            global_cli.recorded_identity()
        with self.assertRaises(global_cli.GlobalCliError):
            global_cli.verify(version=self.v1, commit=self.commit1)
        with self.assertRaises(global_cli.GlobalCliError):
            global_cli.install(source, version=self.v1, commit=self.commit1)
        with self.assertRaises(global_cli.GlobalCliError):
            global_cli.update(source, version=self.v1, commit=self.commit1)
        with self.assertRaises(global_cli.GlobalCliError):
            global_cli.uninstall(version=self.v1, commit=self.commit2)
        self.assertEqual(
            pending_snapshot,
            self._scope_snapshot(data_root, self.home / ".local/bin", self.global_root),
            "blocked operations must not alter pending cleanup state",
        )

        global_before_resume = self._snapshot(self.global_root)
        with mock.patch(
            "olympus.global_cli.global_install.uninstall",
            side_effect=AssertionError("completed global uninstall must not be repeated"),
        ) as global_uninstall:
            resumed = global_cli._uninstall_current()
            global_uninstall.assert_not_called()
        self.assertEqual(("uninstall", "committed"), (resumed.operation, resumed.result))
        self.assertEqual(global_before_resume, self._snapshot(self.global_root))
        self.assertFalse(package.exists())
        self.assertFalse(cleanup_record.exists())
        self.assertEqual(b"preserve sibling\n", sibling_note.read_bytes())
        self.assertIsNone(global_cli.recorded_identity())

    def test_activation_failure_after_global_commit_is_exit4_and_keeps_evidence(self):
        first = self._source("source-v1", self.v1)
        second = self._source("source-v2", self.v2, change_kael=True)
        self._run(first, self.v1, self.commit1)
        data_root = self.data / "olympus"
        current_before = (data_root / "current").read_bytes()

        with mock.patch("olympus.global_cli._activate_current", side_effect=OSError("fixture interruption")):
            with self.assertRaises(global_cli.GlobalCliError) as caught:
                global_cli.update(second, version=self.v2, commit=self.commit2)
        self.assertEqual(4, caught.exception.code)
        self.assertIn("activation is unconfirmed", str(caught.exception))
        self.assertEqual(current_before, (data_root / "current").read_bytes())
        self.assertTrue((data_root / "versions" / self.v2 / global_cli._RECEIPT).is_file())
        manifest = json.loads(
            (self.global_root / "olympus/orchestrator-install.json").read_text(encoding="utf-8")
        )
        self.assertEqual((self.v2, self.commit2),
                         (manifest["installed_version"], manifest["installed_from_commit"]))
        with self.assertRaises(global_cli.GlobalCliError):
            global_cli.recorded_identity()

        before_recovery = self._scope_snapshot(
            self.data / "olympus", self.home / ".local/bin", self.global_root,
        )
        recovered = global_cli._update_recovery_identity()
        self.assertEqual((self.v2, self.commit2), (recovered.version, recovered.commit))
        self.assertEqual(
            before_recovery,
            self._scope_snapshot(
                self.data / "olympus", self.home / ".local/bin", self.global_root,
            ),
        )
        with mock.patch(
            "olympus.global_cli.global_install.update",
            side_effect=AssertionError("a committed global update must not be repeated"),
        ) as global_update:
            outcome = global_cli.update(second, version=self.v2, commit=self.commit2)
            global_update.assert_not_called()
        self.assertEqual(("committed", self.v2, self.commit2),
                         (outcome.result, outcome.version, outcome.commit))
        self.assertEqual((self.v2, self.commit2),
                         (global_cli.recorded_identity().version,
                          global_cli.recorded_identity().commit))
        self.assertEqual("verified", global_cli.verify(
            version=self.v2, commit=self.commit2,
        ).result)

    def test_package_publication_failure_keeps_global_old_and_retry_completes(self):
        first = self._source("source-v1", self.v1)
        second = self._source("source-v2", self.v2, change_kael=True)
        self._run(first, self.v1, self.commit1)
        data_root = self.data / "olympus"

        with (
            mock.patch(
                "olympus.global_cli._publish_package_noreplace",
                side_effect=global_cli.GlobalCliError("fixture publication interruption", 4),
            ),
            mock.patch("olympus.global_cli.global_install.update") as global_update,
        ):
            with self.assertRaisesRegex(global_cli.GlobalCliError, "publication interruption"):
                global_cli.update(second, version=self.v2, commit=self.commit2)
            global_update.assert_not_called()

        current = global_cli.recorded_identity()
        self.assertEqual((self.v1, self.commit1), (current.version, current.commit))
        manifest = json.loads(
            (self.global_root / "olympus/orchestrator-install.json").read_text(encoding="utf-8")
        )
        self.assertEqual((self.v1, self.commit1),
                         (manifest["installed_version"], manifest["installed_from_commit"]))
        self.assertFalse((data_root / "versions" / self.v2).exists())

        outcome = global_cli.update(second, version=self.v2, commit=self.commit2)
        self.assertEqual(("committed", self.v2, self.commit2),
                         (outcome.result, outcome.version, outcome.commit))
        self.assertEqual((self.v2, self.commit2),
                         (global_cli.recorded_identity().version,
                          global_cli.recorded_identity().commit))

    def test_published_package_directory_sync_failure_blocks_global_update_and_retry_resyncs(self):
        first = self._source("source-v1", self.v1)
        second = self._source("source-v2", self.v2, change_kael=True)
        self._run(first, self.v1, self.commit1)
        data_root = self.data / "olympus"
        versions_root = data_root / "versions"
        versions_metadata = versions_root.stat()
        versions_identity = (versions_metadata.st_dev, versions_metadata.st_ino)
        real_fsync = os.fsync
        failed = False

        def fail_versions_sync(descriptor):
            nonlocal failed
            metadata = os.fstat(descriptor)
            if ((metadata.st_dev, metadata.st_ino) == versions_identity and not failed):
                failed = True
                raise OSError("fixture versions directory fsync failure")
            return real_fsync(descriptor)

        with (
            mock.patch("olympus.global_cli.os.fsync", side_effect=fail_versions_sync),
            mock.patch("olympus.global_cli.global_install.update") as global_update,
        ):
            with self.assertRaisesRegex(global_cli.GlobalCliError, "durably sync published"):
                global_cli.update(second, version=self.v2, commit=self.commit2)
            global_update.assert_not_called()

        self.assertTrue(failed)
        self.assertTrue((versions_root / self.v2 / global_cli._RECEIPT).is_file())
        current = global_cli.recorded_identity()
        self.assertEqual((self.v1, self.commit1), (current.version, current.commit))

        nested_directory = versions_root / self.v2 / "olympus"
        nested_metadata = nested_directory.stat()
        nested_identity = (nested_metadata.st_dev, nested_metadata.st_ino)
        reused_file = nested_directory / "global_cli.py"
        reused_file_metadata = reused_file.stat()
        reused_file_identity = (reused_file_metadata.st_dev, reused_file_metadata.st_ino)
        real_fsync = os.fsync
        nested_failed = False

        def fail_nested_sync(descriptor):
            nonlocal nested_failed
            metadata = os.fstat(descriptor)
            if ((metadata.st_dev, metadata.st_ino) == nested_identity and not nested_failed):
                nested_failed = True
                raise OSError("fixture reused nested package directory fsync failure")
            return real_fsync(descriptor)

        with (
            mock.patch("olympus.global_cli.os.fsync", side_effect=fail_nested_sync),
            mock.patch("olympus.global_cli.global_install.update") as global_update,
        ):
            with self.assertRaisesRegex(global_cli.GlobalCliError, "reused CLI package directory olympus"):
                global_cli.update(second, version=self.v2, commit=self.commit2)
            global_update.assert_not_called()
        self.assertTrue(nested_failed)
        current = global_cli.recorded_identity()
        self.assertEqual((self.v1, self.commit1), (current.version, current.commit))

        events = []
        real_update = global_cli.global_install.update

        def record_versions_sync(descriptor):
            metadata = os.fstat(descriptor)
            if (metadata.st_dev, metadata.st_ino) == reused_file_identity:
                events.append("package-file-fsync")
            if (metadata.st_dev, metadata.st_ino) == nested_identity:
                events.append("nested-package-fsync")
            if (metadata.st_dev, metadata.st_ino) == versions_identity:
                events.append("versions-fsync")
            return real_fsync(descriptor)

        def record_global_update(*args, **kwargs):
            events.append("global-update")
            return real_update(*args, **kwargs)

        with (
            mock.patch("olympus.global_cli.os.fsync", side_effect=record_versions_sync),
            mock.patch.object(
                global_cli, "_publish_package_noreplace",
                wraps=global_cli._publish_package_noreplace,
            ) as publish,
            mock.patch.object(
                global_cli.global_install, "update", side_effect=record_global_update,
            ),
        ):
            outcome = global_cli.update(second, version=self.v2, commit=self.commit2)
        publish.assert_not_called()
        self.assertLess(events.index("package-file-fsync"), events.index("nested-package-fsync"))
        self.assertLess(events.index("nested-package-fsync"), events.index("versions-fsync"))
        self.assertLess(events.index("versions-fsync"), events.index("global-update"))
        self.assertEqual(("committed", self.v2, self.commit2),
                         (outcome.result, outcome.version, outcome.commit))
        self.assertNotIn(str(versions_root / self.v2), outcome.changed_paths)

    def test_staged_package_directory_sync_failure_prevents_global_update(self):
        first = self._source("source-v1", self.v1)
        second = self._source("source-v2", self.v2, change_kael=True)
        self._run(first, self.v1, self.commit1)
        real_fsync = os.fsync
        failed = False

        def fail_staged_directory_sync(descriptor):
            nonlocal failed
            if stat.S_ISDIR(os.fstat(descriptor).st_mode) and not failed:
                failed = True
                raise OSError("fixture staged directory fsync failure")
            return real_fsync(descriptor)

        with (
            mock.patch("olympus.global_cli.os.fsync", side_effect=fail_staged_directory_sync),
            mock.patch("olympus.global_cli.global_install.update") as global_update,
        ):
            with self.assertRaisesRegex(global_cli.GlobalCliError, "durably sync staged"):
                global_cli.update(second, version=self.v2, commit=self.commit2)
            global_update.assert_not_called()

        self.assertTrue(failed)
        current = global_cli.recorded_identity()
        self.assertEqual((self.v1, self.commit1), (current.version, current.commit))
        self.assertFalse((self.data / "olympus" / "versions" / self.v2).exists())

    def test_current_marker_directory_sync_failure_is_repaired_by_same_version_retry(self):
        first = self._source("source-v1", self.v1)
        second = self._source("source-v2", self.v2, change_kael=True)
        self._run(first, self.v1, self.commit1)
        data_root = self.data / "olympus"
        data_metadata = data_root.stat()
        data_identity = (data_metadata.st_dev, data_metadata.st_ino)
        real_fsync = os.fsync
        failed = False

        def fail_data_root_sync(descriptor):
            nonlocal failed
            metadata = os.fstat(descriptor)
            if (metadata.st_dev, metadata.st_ino) == data_identity and not failed:
                failed = True
                raise OSError("fixture current marker directory fsync failure")
            return real_fsync(descriptor)

        with mock.patch("olympus.global_cli.os.fsync", side_effect=fail_data_root_sync):
            with self.assertRaisesRegex(global_cli.GlobalCliError, "activation is unconfirmed"):
                global_cli.update(second, version=self.v2, commit=self.commit2)

        self.assertTrue(failed)
        current_marker = (data_root / "current").read_text(encoding="ascii").splitlines()
        self.assertEqual([self.v2, self.commit2], current_marker[:2])

        synced = []

        def observe_data_root_sync(descriptor):
            metadata = os.fstat(descriptor)
            if (metadata.st_dev, metadata.st_ino) == data_identity:
                synced.append(True)
            return real_fsync(descriptor)

        with mock.patch("olympus.global_cli.os.fsync", side_effect=observe_data_root_sync):
            outcome = global_cli.update(second, version=self.v2, commit=self.commit2)
        self.assertEqual("no_changes", outcome.result)
        self.assertTrue(synced, "same-version retry must durably sync the active current marker")
        self.assertEqual("verified", global_cli.verify(
            version=self.v2, commit=self.commit2,
        ).result)

    def test_current_durable_sync_rejects_wrong_selected_identity_before_sync(self):
        first = self._source("source-v1", self.v1)
        self._run(first, self.v1, self.commit1)

        with mock.patch("olympus.global_cli.os.fsync", wraps=os.fsync) as fsync:
            with self.assertRaisesRegex(
                global_cli.GlobalCliError, "differs from the selected release",
            ):
                global_cli._ensure_current_durable(
                    version=self.v2, commit=self.commit2,
                )
        fsync.assert_not_called()

    def test_update_recovery_rejects_source_drift_without_touching_split_state(self):
        first = self._source("source-v1", self.v1)
        second = self._source("source-v2", self.v2, change_kael=True)
        drifted = self._source("source-v2-drifted", self.v2)
        self._run(first, self.v1, self.commit1)
        with mock.patch("olympus.global_cli._activate_current",
                        side_effect=OSError("fixture interruption")):
            with self.assertRaises(global_cli.GlobalCliError):
                global_cli.update(second, version=self.v2, commit=self.commit2)

        before = self._scope_snapshot(
            self.data / "olympus", self.home / ".local/bin", self.global_root,
        )
        with self.assertRaisesRegex(global_cli.GlobalCliError, "differs from the verified source"):
            global_cli.update(drifted, version=self.v2, commit=self.commit2)
        self.assertEqual(
            before,
            self._scope_snapshot(
                self.data / "olympus", self.home / ".local/bin", self.global_root,
            ),
        )
if __name__ == "__main__":
    unittest.main()
