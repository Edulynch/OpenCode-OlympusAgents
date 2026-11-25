"""Fixture-only tests for the PowerShell-free local global installer backend."""

from __future__ import annotations

import errno
import json
import contextlib
import io
import os
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympus import config_apply_transaction, global_install, global_readonly, source_edit, user_config
from olympus.cli import load_renderer, main


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


class LinuxGlobalBackend(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="olympus-global-linux-")
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.root = self.sandbox / "opencode"
        self.preferences = self.sandbox / "preferences" / "config.json"
        self.env = mock.patch.dict(os.environ, {
            "OPENCODE_CONFIG_DIR": str(self.root),
            "OLYMPUS_CONFIG_FILE": str(self.preferences),
            "OLYMPUS_CONFIG_HOME": "",
            "APPDATA": str(self.sandbox / "inherited-appdata"),
            "XDG_CONFIG_HOME": str(self.sandbox / "xdg"),
            "HOME": str(self.sandbox / "home"),
            "USERPROFILE": str(self.sandbox / "profile"),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def _source(self, name: str, *, change_kael: bool = False) -> Path:
        source = self.sandbox / name
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        shutil.copytree(ROOT / "olympus", source / "olympus", ignore=ignore)
        shutil.copytree(ROOT / ".opencode", source / ".opencode", ignore=ignore)
        (source / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/render_harnesses.py", source / "scripts/render_harnesses.py")
        if change_kael:
            path = source / "olympus/core/models.toml"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("[roles.kael]\nfamily = \"sol\"",
                                         "[roles.kael]\nfamily = \"luna\"", 1), encoding="utf-8")
        return source

    def _files(self) -> dict[str, tuple[bytes, int]]:
        if not self.root.exists():
            return {}
        return {
            path.relative_to(self.root).as_posix():
            (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }

    def _require_acl_free_fixture(self, *roots: Path) -> None:
        if not hasattr(os, "listxattr"):
            self.skipTest("force ACL regression requires Linux ACL xattr inspection")
        unsupported = {
            getattr(errno, name, None) for name in ("ENOTSUP", "EOPNOTSUPP", "ENOSYS")
        } - {None}
        for root in roots:
            for path in (root, *root.rglob("*")):
                try:
                    attributes = set(os.listxattr(path))
                except OSError as error:
                    if error.errno in unsupported:
                        self.skipTest("fixture storage does not support POSIX ACL xattr inspection")
                    raise
                if attributes & {"system.posix_acl_access", "system.posix_acl_default"}:
                    self.skipTest("ACL regression fixture already has POSIX ACL policy")

    def _safe_user_config(self, default_agent: str = "other") -> bytes:
        return (
            '{\n  // keep this comment and all unrelated preferences\n'
            f'  "default_agent": "{default_agent}",\n'
            '  "permissions": [\n'
            '    {"action": "external_directory", "resource": "*", "effect": "ask"},\n'
            '  ],\n'
            '  "user_setting": {"theme": "dark",},\n'
            '}\n'
        ).encode("utf-8")

    def _set_prior_kael_receipt(self) -> None:
        path = self.root / "olympus/orchestrator-install.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        receipt = manifest["default_agent_receipt"]
        receipt.update({
            "previous_present": True,
            "previous_value_json": json.dumps("kael"),
            "restore_action": "remove",
        })
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_absent_config_install_verify_and_same_source_no_rewrites(self):
        installed = global_install.install(ROOT, version="local", commit="fixture-local")
        self.assertEqual("committed", installed.result)
        manifest_path = self.root / "olympus/orchestrator-install.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(16, len(manifest["managed_files"]))
        self.assertIn("opencode.jsonc", {item["path"] for item in manifest["managed_files"]})
        self.assertEqual("committed", manifest["default_agent_receipt"]["state"])
        guard = (self.root / "opencode.jsonc").read_bytes()
        self.assertIn(b'"default_agent": "kael"', guard)

        verified = global_install.verify(ROOT, version="local", commit="fixture-local")
        self.assertEqual("verified", verified.result)
        before = self._files()
        self.assertEqual("no_changes", global_install.install(
            ROOT, version="local", commit="fixture-local",
        ).result)
        self.assertEqual("no_changes", global_install.update(
            ROOT, version="local", commit="fixture-local",
        ).result)
        self.assertEqual(before, self._files())

        expected = global_readonly._expected(
            ROOT, load_renderer(ROOT), ("opencode",), include_default_agent=True,
        )["opencode"]
        state, _, issue, code = global_readonly._python_verify(
            ROOT, self.root, "local", expected,
        )
        self.assertEqual(("verified", None, 0), (state, issue, code))

    def test_existing_jsonc_splices_only_default_agent_and_restores_exact_bytes(self):
        self.root.mkdir()
        original = self._safe_user_config()
        (self.root / "opencode.jsonc").write_bytes(original)

        global_install.install(ROOT, version="local", commit="fixture-local")
        installed = (self.root / "opencode.jsonc").read_bytes()
        self.assertEqual(original.replace(b'"other"', b'"kael"', 1), installed)
        manifest = json.loads((self.root / "olympus/orchestrator-install.json").read_text(encoding="utf-8"))
        self.assertEqual(15, len(manifest["managed_files"]))
        self.assertNotIn("opencode.jsonc", {item["path"] for item in manifest["managed_files"]})
        self.assertIn(b"keep this comment and all unrelated preferences", installed)
        self.assertIn(b'"user_setting": {"theme": "dark",}', installed)
        self.assertEqual("verified", global_install.verify(ROOT, version="local").result)

        removed = global_install.uninstall(ROOT)
        self.assertEqual("committed", removed.result)
        self.assertEqual(original, (self.root / "opencode.jsonc").read_bytes())
        self.assertFalse((self.root / "olympus/orchestrator-install.json").exists())

    def test_prior_kael_restore_action_removes_field_and_rollback_keeps_original_bytes(self):
        self.root.mkdir()
        config_path = self.root / "opencode.jsonc"
        config_path.write_bytes(self._safe_user_config("other"))
        global_install.install(ROOT, version="local", commit="fixture-local")
        self._set_prior_kael_receipt()
        installed_bytes = config_path.read_bytes()

        global_install.uninstall(ROOT)
        self.assertEqual(global_install._splice_default_agent(installed_bytes, None),
                         config_path.read_bytes())
        self.assertNotIn(b'"default_agent"', config_path.read_bytes())

        self.root.mkdir(exist_ok=True)
        config_path.write_bytes(self._safe_user_config("other"))
        global_install.install(ROOT, version="local", commit="fixture-local")
        self._set_prior_kael_receipt()
        rollback_bytes = config_path.read_bytes()

        def interrupt_after_config_restore(path: Path):
            if Path(path) == self.root and b'"default_agent": "kael"' not in config_path.read_bytes():
                raise KeyboardInterrupt()

        with mock.patch("olympus.global_install.source_edit._sync_directory",
                        side_effect=interrupt_after_config_restore):
            with self.assertRaises(KeyboardInterrupt):
                global_install.uninstall(ROOT)
        self.assertNotIn(b'"default_agent"', config_path.read_bytes())
        self.assertTrue(config_apply_transaction.pending(self.root))
        recovered = global_install.recover(ROOT)
        self.assertEqual("rolled_back", recovered.result)
        self.assertEqual(rollback_bytes, config_path.read_bytes())
        self.assertIn(b'"default_agent": "kael"', config_path.read_bytes())

    def test_newer_staged_source_updates_manifest_last_and_same_version_mismatch_is_not_repaired(self):
        first = self._source("source-v1")
        second = self._source("source-v2", change_kael=True)
        global_install.install(first, version="v1.0.0", commit="source-one")
        before_kael = (self.root / "agents/kael.md").read_bytes()
        result = global_install.update(second, version="v1.1.0", commit="source-two")
        self.assertEqual("committed", result.result)
        after_kael = (self.root / "agents/kael.md").read_bytes()
        self.assertNotEqual(before_kael, after_kael)
        self.assertIn(b"openai/gpt-6-luna#high", after_kael)
        manifest = json.loads((self.root / "olympus/orchestrator-install.json").read_text(encoding="utf-8"))
        self.assertEqual(("v1.1.0", "source-two"),
                         (manifest["installed_version"], manifest["installed_from_commit"]))
        self.assertEqual("verified", global_install.verify(
            second, version="v1.1.0", commit="source-two",
        ).result)

        before = self._files()
        with self.assertRaisesRegex(global_install.GlobalInstallError, "Same-version"):
            global_install.update(first, version="v1.1.0", commit="changed-source")
        with self.assertRaisesRegex(global_install.GlobalInstallError, "downgrade"):
            global_install.update(first, version="v1.0.0", commit="source-one")
        self.assertEqual(before, self._files())

    def test_force_same_version_repairs_only_manifest_owned_files_and_preserves_user_config(self):
        self.root.mkdir()
        config_path = self.root / "opencode.jsonc"
        config_path.write_bytes(self._safe_user_config())
        global_install.install(ROOT, version="local", commit="fixture-local")
        if sys.platform.startswith("linux"):
            self._require_acl_free_fixture(self.root)

        user_config = config_path.read_bytes().replace(b'"theme": "dark"', b'"theme": "light"')
        config_path.write_bytes(user_config)
        managed = self.root / "agents/kael.md"
        if sys.platform.startswith("linux"):
            try:
                self.assertNotIn("system.posix_acl_access", os.listxattr(managed))
                self.assertNotIn("system.posix_acl_default", os.listxattr(self.root))
            except OSError as error:
                unsupported = {
                    getattr(errno, name, None) for name in ("ENOTSUP", "EOPNOTSUPP", "ENOSYS")
                } - {None}
                if error.errno in unsupported:
                    self.skipTest("mode-only force repair requires ACL-capable fixture storage")
                raise
        damaged = b"damaged managed resource\n"
        managed.write_bytes(damaged)
        missing = self.root / "commands/olympus.ultra.md"
        expected_missing = missing.read_bytes()
        missing.unlink()

        with self.assertRaisesRegex(global_install.GlobalInstallError, "drifted"):
            global_install.update(ROOT, version="local", commit="fixture-local")
        self.assertEqual(damaged, managed.read_bytes())
        self.assertFalse(missing.exists())

        real_replace = os.replace
        interrupted = False

        def interrupt_owned_replace(source, destination):
            nonlocal interrupted
            if Path(destination) == managed and not interrupted:
                interrupted = True
                raise OSError("fixture force-repair interruption")
            return real_replace(source, destination)

        with mock.patch("olympus.global_install.os.replace", side_effect=interrupt_owned_replace):
            with self.assertRaisesRegex(global_install.GlobalInstallError, "rollback was confirmed"):
                global_install.update(
                    ROOT, version="local", commit="fixture-local", force=True,
                )
        self.assertTrue(interrupted)
        self.assertEqual(damaged, managed.read_bytes())
        self.assertFalse(config_apply_transaction.pending(self.root))

        result = global_install.update(
            ROOT, version="local", commit="fixture-local", force=True,
        )
        self.assertEqual("committed", result.result)
        self.assertNotEqual(b"damaged managed resource\n", managed.read_bytes())
        self.assertEqual(expected_missing, missing.read_bytes())
        self.assertEqual(user_config, config_path.read_bytes())
        self.assertEqual("verified", global_install.verify(
            ROOT, version="local", commit="fixture-local",
        ).result)
        no_op = global_install.update(ROOT, version="local", commit="fixture-local", force=True)
        self.assertEqual(("no_changes", ()), (no_op.result, no_op.changed_paths))

    @unittest.skipUnless(sys.platform.startswith("linux"), "native POSIX ACL xattrs require Linux.")
    def test_force_acl_preflights_all_global_targets_before_any_write(self):
        self.root.mkdir()
        global_install.install(ROOT, version="local", commit="fixture-local")
        self._require_acl_free_fixture(self.root)
        earlier = self.root / "commands/olympus.ultra.md"
        later = self.root / "agents/veyra.md"
        earlier.write_bytes(b"earlier managed drift\n")
        later.write_bytes(b"later managed drift\n")
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
        before = self._files()
        old_manifest = (self.root / global_readonly._MANIFEST).read_bytes()

        with self.assertRaisesRegex(global_install.GlobalInstallError, "access-ACL-bearing"):
            global_install.update(ROOT, version="local", commit="fixture-local", force=True)

        self.assertEqual(before, self._files())
        self.assertEqual(b"earlier managed drift\n", earlier.read_bytes())
        self.assertEqual(b"later managed drift\n", later.read_bytes())
        self.assertEqual(old_manifest, (self.root / global_readonly._MANIFEST).read_bytes())
        self.assertIn("system.posix_acl_access", os.listxattr(later))

    @unittest.skipUnless(sys.platform.startswith("linux"), "native POSIX ACL xattrs require Linux.")
    def test_force_rollback_preserves_journal_when_replaced_target_gains_acl(self):
        self.root.mkdir()
        global_install.install(ROOT, version="local", commit="fixture-local")
        self._require_acl_free_fixture(self.root)
        first = self.root / "agents/kael.md"
        second = self.root / "commands/olympus.ultra.md"
        first.write_bytes(b"first managed drift\n")
        second.write_bytes(b"second managed drift\n")
        real_replace = os.replace
        replaced = []

        def add_acl_then_interrupt(source, destination):
            target = Path(destination)
            if target == first:
                result = real_replace(source, destination)
                os.setxattr(target, "system.posix_acl_access", _extended_posix_acl_xattr())
                replaced.append(target)
                return result
            if target == second:
                raise OSError("fixture interruption after first global replacement")
            return real_replace(source, destination)

        with mock.patch(
            "olympus.global_install.os.replace", side_effect=add_acl_then_interrupt,
        ):
            with self.assertRaisesRegex(
                global_install.GlobalInstallError, "recovery is unconfirmed",
            ):
                global_install.update(
                    ROOT, version="local", commit="fixture-local", force=True,
                )

        self.assertEqual([first], replaced)
        self.assertNotEqual(b"first managed drift\n", first.read_bytes())
        self.assertEqual(b"second managed drift\n", second.read_bytes())
        self.assertIn("system.posix_acl_access", os.listxattr(first))
        self.assertTrue(config_apply_transaction.pending(self.root))

    @unittest.skipUnless(sys.platform.startswith("linux"), "native POSIX ACL xattrs require Linux.")
    def test_force_rejects_default_acl_on_global_staging_parent_before_write(self):
        self.root.mkdir()
        global_install.install(ROOT, version="local", commit="fixture-local")
        self._require_acl_free_fixture(self.root)
        earlier = self.root / "commands/olympus.ultra.md"
        earlier.write_bytes(b"managed drift\n")
        try:
            os.setxattr(self.root, "system.posix_acl_default", _extended_posix_acl_xattr())
        except OSError as error:
            unsupported = {
                getattr(errno, name, None) for name in ("ENOTSUP", "EOPNOTSUPP", "ENOSYS", "EPERM")
            } - {None}
            if error.errno in unsupported:
                self.skipTest("fixture storage/user cannot create POSIX default ACL xattrs")
            raise
        self.assertIn("system.posix_acl_default", os.listxattr(self.root))
        before = self._files()
        old_manifest = (self.root / global_readonly._MANIFEST).read_bytes()

        with self.assertRaisesRegex(global_install.GlobalInstallError, "default-ACL-bearing"):
            global_install.update(ROOT, version="local", commit="fixture-local", force=True)

        self.assertEqual(before, self._files())
        self.assertEqual(b"managed drift\n", earlier.read_bytes())
        self.assertEqual(old_manifest, (self.root / global_readonly._MANIFEST).read_bytes())

    @unittest.skipUnless(sys.platform.startswith("linux"), "native POSIX ACL xattrs require Linux.")
    def test_force_acl_probe_errors_fail_closed_before_any_write(self):
        self.root.mkdir()
        global_install.install(ROOT, version="local", commit="fixture-local")
        managed = self.root / "agents/kael.md"
        managed.write_bytes(b"managed drift\n")
        before = self._files()
        unsupported = getattr(errno, "ENOTSUP", getattr(errno, "EOPNOTSUPP", 95))
        with mock.patch.object(
            global_install.os, "listxattr",
            side_effect=OSError(unsupported, "fixture unsupported ACL probe"),
            create=True,
        ):
            with self.assertRaisesRegex(
                global_install.GlobalInstallError, "Cannot establish Linux ACL state",
            ):
                global_install.update(ROOT, version="local", commit="fixture-local", force=True)
        self.assertEqual(before, self._files())
        self.assertEqual(b"managed drift\n", managed.read_bytes())

    def test_force_update_rejects_unowned_or_unsafe_owned_nodes(self):
        global_install.install(ROOT, version="local", commit="fixture-local")
        package_note = self.root / "user-owned-note"
        package_note.write_bytes(b"keep\n")
        before = package_note.read_bytes()
        global_install.update(ROOT, version="local", commit="fixture-local", force=True)
        self.assertEqual(before, package_note.read_bytes())
        package_note.unlink()

        managed = self.root / "agents/kael.md"
        outside = self.sandbox / "outside.txt"
        outside.write_bytes(b"outside\n")
        managed.unlink()
        managed.symlink_to(outside)
        with self.assertRaises(global_install.GlobalInstallError):
            global_install.update(ROOT, version="local", commit="fixture-local", force=True)
        self.assertTrue(managed.is_symlink())
        self.assertEqual(b"outside\n", outside.read_bytes())

    def test_user_default_change_or_deletion_survives_update_verify_drift_and_uninstall(self):
        first = self._source("preferences-v1")
        second = self._source("preferences-v2")
        self.root.mkdir(exist_ok=True)
        initial = self._safe_user_config()
        config_path = self.root / "opencode.jsonc"
        config_path.write_bytes(initial)
        global_install.install(first, version="v1.0.0", commit="source-one")

        user_choice = config_path.read_bytes().replace(b'"kael"', b'"manual-choice"', 1)
        config_path.write_bytes(user_choice)
        global_install.update(second, version="v1.1.0", commit="source-two")
        with self.assertRaises(global_install.GlobalInstallError):
            global_install.verify(second, version="v1.1.0", commit="source-two")
        global_install.uninstall(second)
        self.assertEqual(user_choice, config_path.read_bytes())

        self.root.mkdir(exist_ok=True)
        config_path = self.root / "opencode.jsonc"
        config_path.write_bytes(initial)
        global_install.install(first, version="v1.0.0", commit="source-one")
        config_path.unlink()
        global_install.update(second, version="v1.1.0", commit="source-two")
        with self.assertRaises(global_install.GlobalInstallError):
            global_install.verify(second, version="v1.1.0", commit="source-two")
        global_install.uninstall(second)
        self.assertFalse(config_path.exists())

    def test_collisions_unsafe_configs_and_foreign_pending_state_fail_closed(self):
        self.root.mkdir()
        collision = self.root / "agents/kael.md"
        collision.parent.mkdir()
        collision.write_bytes(b"user-owned collision\n")
        with self.assertRaisesRegex(global_install.GlobalInstallError, "Unowned global destination"):
            global_install.install(ROOT)
        self.assertEqual(b"user-owned collision\n", collision.read_bytes())
        self.assertFalse((self.root / "olympus/orchestrator-install.json").exists())

        shutil.rmtree(self.root / "agents")
        (self.root / "opencode.json").write_bytes(self._safe_user_config())
        (self.root / "opencode.jsonc").write_bytes(self._safe_user_config())
        with self.assertRaisesRegex(global_install.GlobalInstallError, "Both OpenCode"):
            global_install.install(ROOT)

        (self.root / "opencode.json").unlink()
        (self.root / "opencode.jsonc").unlink()
        foreign = self.root / ".olympus-cli-config-apply"
        foreign.mkdir()
        (foreign / "foreign-note").write_bytes(b"preserve\n")
        with self.assertRaisesRegex(global_install.GlobalInstallError, "pending"):
            global_install.verify(ROOT)
        expected = global_readonly._expected(
            ROOT, load_renderer(ROOT), ("opencode",), include_default_agent=True,
        )["opencode"]
        state, _, issue, code = global_readonly._python_verify(ROOT, self.root, "local", expected)
        self.assertEqual(("recovery_pending", "global_apply_recovery_pending", 3),
                         (state, issue, code))
        lock = source_edit._acquire_lock(self.root, create=True)
        source_edit._release_lock(lock)
        with self.assertRaises(global_install.GlobalInstallError):
            global_install.recover(ROOT)
        self.assertEqual(b"preserve\n", (foreign / "foreign-note").read_bytes())

    def test_pending_manifest_receipt_blocks_all_lifecycle_mutations(self):
        global_install.install(ROOT, version="local", commit="fixture-local")
        manifest_path = self.root / "olympus/orchestrator-install.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["default_agent_receipt"]["state"] = "pending_set"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        before = self._files()
        expected = global_readonly._expected(
            ROOT, load_renderer(ROOT), ("opencode",), include_default_agent=True,
        )["opencode"]
        state, _, issue, code = global_readonly._python_verify(
            ROOT, self.root, "local", expected,
        )
        self.assertEqual(("recovery_pending", "global_default_agent_recovery_pending", 3),
                         (state, issue, code))

        for operation in (
            lambda: global_install.install(ROOT, version="local", commit="fixture-local"),
            lambda: global_install.update(ROOT, version="v1.0.0", commit="next"),
            lambda: global_install.uninstall(ROOT),
        ):
            with self.assertRaisesRegex(global_install.GlobalInstallError, "pending_set"):
                operation()
        self.assertEqual(before, self._files())

    def test_noop_reuses_existing_lock_and_missing_lock_is_never_created(self):
        global_install.install(ROOT, version="local", commit="fixture-local")
        lock_path = self.root / source_edit._LOCK_NAME
        self.assertTrue(lock_path.is_file())
        before = self._files()
        acquire = source_edit._acquire_lock
        with mock.patch("olympus.global_install.source_edit._acquire_lock", wraps=acquire) as mocked:
            commit = global_install._commit
            with mock.patch("olympus.global_install._commit", wraps=commit) as committed:
                self.assertEqual("no_changes", global_install.install(
                    ROOT, version="local", commit="fixture-local",
                ).result)
            committed.assert_called_once()
        self.assertTrue(any(call.kwargs.get("create") is False for call in mocked.call_args_list))
        self.assertEqual(before, self._files())

        lock_path.unlink()
        before = self._files()
        with self.assertRaisesRegex(global_install.GlobalInstallError, "no stable writer lock"):
            global_install.install(ROOT, version="local", commit="fixture-local")
        self.assertFalse(lock_path.exists())
        self.assertEqual(before, self._files())

    def test_missing_lock_still_checks_root_identity_on_both_sides(self):
        self.root.mkdir()
        identity = (self.root.stat().st_dev, self.root.stat().st_ino)
        verify = global_install._verify_root
        with mock.patch("olympus.global_install._verify_root", wraps=verify) as checked:
            self.assertIsNone(global_install._existing_lock(self.root, identity))
        self.assertEqual(2, checked.call_count)

    def test_absent_uninstall_noop_does_not_create_a_lock(self):
        self.root.mkdir()
        before = self._files()
        self.assertEqual("no_changes", global_install.uninstall(ROOT).result)
        self.assertEqual(before, self._files())
        self.assertFalse((self.root / source_edit._LOCK_NAME).exists())

    def test_uninstall_without_manifest_fails_closed_on_pending_scratch_and_bad_locks(self):
        self.root.mkdir()
        scratch = self.root / ".olympus-cli-config-apply"
        scratch.mkdir()
        note = scratch / "foreign-note"
        note.write_bytes(b"preserve\n")
        lock_path = self.root / source_edit._LOCK_NAME
        before = self._files()

        with self.assertRaisesRegex(global_install.GlobalInstallError, "no stable writer lock"):
            global_install.uninstall(ROOT)
        self.assertEqual(before, self._files())
        self.assertFalse(lock_path.exists())

        lock_path.mkdir()
        before = self._files()
        with self.assertRaisesRegex(global_install.GlobalInstallError, "existing stable global writer lock"):
            global_install.uninstall(ROOT)
        self.assertEqual(before, self._files())
        lock_path.rmdir()

        stable_lock = source_edit._acquire_lock(self.root, create=True)
        source_edit._release_lock(stable_lock)
        before = self._files()
        with self.assertRaisesRegex(global_install.GlobalInstallError, "pending"):
            global_install.uninstall(ROOT)
        self.assertEqual(before, self._files())

        shutil.rmtree(scratch)
        before = self._files()
        commit = global_install._commit
        with mock.patch("olympus.global_install._commit", wraps=commit) as committed:
            self.assertEqual("no_changes", global_install.uninstall(ROOT).result)
        committed.assert_called_once()
        self.assertEqual(before, self._files())

    def test_interrupted_first_publish_recovers_to_the_old_state(self):
        original_sync = source_edit._sync_directory
        interrupted = False

        def stop_after_first_published_file(path: Path):
            nonlocal interrupted
            if Path(path) == self.root / "agents" and not interrupted:
                interrupted = True
                raise KeyboardInterrupt()
            original_sync(path)

        with mock.patch("olympus.global_install.source_edit._sync_directory",
                        side_effect=stop_after_first_published_file):
            with self.assertRaises(KeyboardInterrupt):
                global_install.install(ROOT, version="local", commit="fixture-local")
        self.assertTrue((self.root / ".olympus-cli-config-apply").exists())
        self.assertTrue(config_apply_transaction.pending(self.root))
        self.assertTrue((self.root / "agents/argus.md").exists())

        if sys.platform.startswith("linux"):
            outcome = config_apply_transaction.recover_global(
                self.root, ROOT, load_renderer=load_renderer,
            )
        else:
            outcome = global_install.recover(ROOT).result
        self.assertEqual("rolled_back", outcome)
        self.assertFalse((self.root / "agents/argus.md").exists())
        self.assertFalse((self.root / "olympus/orchestrator-install.json").exists())
        self.assertFalse((self.root / ".olympus-cli-config-apply").exists())
        self.assertFalse(config_apply_transaction.pending(self.root))

    def test_preparing_journal_with_existing_config_recovers_without_user_byte_changes(self):
        self.root.mkdir()
        original = self._safe_user_config()
        (self.root / "opencode.jsonc").write_bytes(original)
        make_directory = source_edit._make_directory

        def interrupt_before_staging(path, *args, **kwargs):
            if Path(path) == self.root / ".olympus-cli-config-apply/backups":
                raise KeyboardInterrupt()
            return make_directory(path, *args, **kwargs)

        with mock.patch("olympus.global_install.source_edit._make_directory",
                        side_effect=interrupt_before_staging):
            with self.assertRaises(KeyboardInterrupt):
                global_install.install(ROOT, version="local", commit="fixture-local")
        self.assertTrue((self.root / ".olympus-cli-config-apply/record.json").exists())

        outcome = global_install.recover(ROOT)
        self.assertEqual("discarded_incomplete_prepare", outcome.result)
        self.assertEqual(original, (self.root / "opencode.jsonc").read_bytes())
        self.assertFalse((self.root / "olympus/orchestrator-install.json").exists())
        self.assertFalse((self.root / ".olympus-cli-config-apply").exists())

    def test_recovery_preserves_foreign_bytes_and_pending_evidence(self):
        original_sync = source_edit._sync_directory
        interrupted = False

        def stop_after_first_published_file(path: Path):
            nonlocal interrupted
            if Path(path) == self.root / "agents" and not interrupted:
                interrupted = True
                raise KeyboardInterrupt()
            original_sync(path)

        with mock.patch("olympus.global_install.source_edit._sync_directory",
                        side_effect=stop_after_first_published_file):
            with self.assertRaises(KeyboardInterrupt):
                global_install.install(ROOT, version="local", commit="fixture-local")
        target = self.root / "agents/argus.md"
        target.write_bytes(b"changed outside the pending lifecycle\n")
        before = self._files()

        with self.assertRaisesRegex(global_install.GlobalInstallError, "preserve"):
            global_install.recover(ROOT)
        self.assertEqual(before, self._files())
        self.assertTrue((self.root / ".olympus-cli-config-apply/record.json").exists())

    def test_linux_user_config_ignores_inherited_appdata(self):
        values = {
            "APPDATA": str(self.sandbox / "appdata"),
            "XDG_CONFIG_HOME": str(self.sandbox / "xdg"),
            "HOME": str(self.sandbox / "home"),
            "USERPROFILE": str(self.sandbox / "profile"),
        }
        with mock.patch.dict(os.environ, values, clear=True):
            expected = (Path(values["APPDATA"]) / "Olympus/config.json" if os.name == "nt"
                        else Path(values["XDG_CONFIG_HOME"]) / "olympus/config.json")
            self.assertEqual(expected, user_config.config_path())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux directory-descriptor checks require Linux.")
    def test_linux_root_walk_uses_no_follow_directory_descriptors(self):
        target = self.sandbox / "secure-parent" / "opencode"
        real_open = os.open
        real_mkdir = os.mkdir
        with mock.patch("olympus.global_readonly.os.open", wraps=real_open) as opened:
            with mock.patch("olympus.global_readonly.os.mkdir", wraps=real_mkdir) as made:
                result_path, identity = global_readonly._ensure_linux_directory(target, create=True)
        self.assertEqual(target, result_path)
        self.assertTrue(target.is_dir())
        self.assertEqual(identity, (target.stat().st_dev, target.stat().st_ino))
        flags = [call.args[1] for call in opened.call_args_list]
        self.assertTrue(flags)
        self.assertTrue(all(flag & os.O_DIRECTORY and flag & os.O_NOFOLLOW for flag in flags))
        self.assertTrue(made.call_args_list)
        self.assertTrue(all(isinstance(call.args[0], str) and "dir_fd" in call.kwargs
                            for call in made.call_args_list))
        before = sorted(item.name for item in target.parent.iterdir())
        global_readonly._verify_linux_directory(target, identity)
        self.assertEqual(before, sorted(item.name for item in target.parent.iterdir()))
        with self.assertRaises(global_readonly.GlobalFault):
            global_readonly._verify_linux_directory(target, (identity[0], identity[1] + 1))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Global setter root checks require Linux.")
    def test_global_setters_use_the_secure_root_helper_on_fixture_only_paths(self):
        ensure = global_readonly._ensure_linux_directory
        with mock.patch("olympus.global_readonly._ensure_linux_directory", wraps=ensure) as secured:
            override_path, applied = user_config.set_override(ROOT, "kael", "effort", "high")
            children_path, updated = user_config.set_max_children(ROOT, 3)
        self.assertEqual(user_config.config_path(), override_path)
        self.assertEqual(user_config.config_path(), children_path)
        self.assertFalse(applied)
        self.assertFalse(updated)
        self.assertGreaterEqual(
            sum(call.kwargs.get("create") is True for call in secured.call_args_list), 2,
        )
        self.assertTrue((self.root / source_edit._LOCK_NAME).is_file())
        self.assertFalse((self.root / ".olympus-cli-config-apply").exists())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux global settings recovery requires Linux.")
    def test_global_user_settings_recovery_rolls_back_interrupted_setters(self):
        self.assertEqual("committed", global_install.install(ROOT, version="local", commit="fixture-local").result)
        settings = user_config.config_path()
        nox = self.root / "agents/nox.md"
        manifest = self.root / "olympus/orchestrator-install.json"
        publish = config_apply_transaction._settings_publish

        for change, stop_path, role_path, commit_point in (
            ("override", "agents/nox.md", nox, False),
            ("max_children", "@global-user-config", self.root / "agents/kael.md", True),
        ):
            with self.subTest(change=change):
                before_agent = role_path.read_bytes()
                before_manifest = manifest.read_bytes()

                if commit_point:
                    commit = config_apply_transaction._settings_commit_preferences

                    def stop_after_publish(*args, **kwargs):
                        commit(*args, **kwargs)
                        raise KeyboardInterrupt("fixture interruption after preference commit")

                    attempt = mock.patch(
                        "olympus.config_apply_transaction._settings_commit_preferences",
                        side_effect=stop_after_publish,
                    )
                else:
                    def stop_after_publish(*args, **kwargs):
                        result = publish(*args, **kwargs)
                        if args[4] == stop_path:
                            raise KeyboardInterrupt("fixture process interruption")
                        return result

                    attempt = mock.patch(
                        "olympus.config_apply_transaction._settings_publish",
                        side_effect=stop_after_publish,
                    )
                with attempt:
                    with self.assertRaises(KeyboardInterrupt):
                        if change == "override":
                            user_config.set_override(ROOT, "nox", "effort", "high")
                        else:
                            user_config.set_max_children(ROOT, 3)

                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main([
                        "--source", str(ROOT), "config", "recover", "--scope", "global",
                        "--harness", "opencode",
                    ])
                self.assertEqual(0, code, output.getvalue())
                if commit_point:
                    self.assertIn("Recovery: committed_cleanup", output.getvalue())
                    self.assertNotEqual(before_agent, role_path.read_bytes())
                    self.assertIn(b"MAX_ACTIVE_CHILDREN = 3", role_path.read_bytes())
                    self.assertTrue(settings.exists())
                    self.assertNotEqual(before_manifest, manifest.read_bytes())
                else:
                    self.assertIn("Recovery: rolled_back", output.getvalue())
                    self.assertEqual(before_agent, role_path.read_bytes())
                    self.assertEqual(before_manifest, manifest.read_bytes())
                    self.assertFalse(settings.exists())
                self.assertFalse((self.root / ".olympus-cli-config-apply").exists())


    @unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "POSIX launcher checks require sh.")
    def test_posix_launcher_python_default_minimum_missing_and_override(self):
        launcher_dir = self.sandbox / "launcher"
        launcher_dir.mkdir()
        launcher = launcher_dir / "olympus"
        shutil.copy2(ROOT / "scripts/olympus", launcher)
        (launcher_dir / "olympus_cli.py").write_text("print('LAUNCH_OK')\n", encoding="utf-8")

        def run(env):
            return subprocess.run(
                ["sh", str(launcher)], env=env, capture_output=True, text=True,
                encoding="utf-8", timeout=15, check=False,
            )

        default = os.environ.copy()
        default.pop("OLYMPUS_PYTHON", None)
        actual_python3 = shutil.which("python3")
        if actual_python3:
            result = run(default)
            version = subprocess.run(
                [actual_python3, "-c", "import sys; print(sys.version_info >= (3, 11))"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if version.returncode == 0 and version.stdout.strip() == "True":
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("LAUNCH_OK", result.stdout)
            else:
                self.assertEqual(3, result.returncode)
                self.assertIn("Python 3.11 or newer", result.stderr)
        else:
            self.skipTest("No stock python3 interpreter is available for the default-selection check.")

        missing = {**default, "OLYMPUS_PYTHON": str(self.sandbox / "missing-python")}
        missing_result = run(missing)
        self.assertEqual(3, missing_result.returncode)
        self.assertIn("Python 3.11 or newer", missing_result.stderr)

        fake_bin = self.sandbox / "fake-bin"
        fake_bin.mkdir()
        too_old = fake_bin / "python-too-old"
        too_old.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"-c\" ]; then exit 1; fi\n"
            f"exec {json.dumps(sys.executable)} \"$@\"\n",
            encoding="utf-8",
        )
        too_old.chmod(0o755)
        old_result = run({**default, "OLYMPUS_PYTHON": str(too_old)})
        self.assertEqual(3, old_result.returncode)
        self.assertIn("Python 3.11 or newer", old_result.stderr)

        override = fake_bin / "python-override"
        override.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"-c\" ]; then exit 0; fi\n"
            f"exec {json.dumps(sys.executable)} \"$@\"\n",
            encoding="utf-8",
        )
        override.chmod(0o755)
        override_result = run({
            **default, "OLYMPUS_PYTHON": str(override),
            "PATH": str(fake_bin) + os.pathsep + default.get("PATH", ""),
        })
        self.assertEqual(0, override_result.returncode, override_result.stderr)
        self.assertIn("LAUNCH_OK", override_result.stdout)


if __name__ == "__main__":
    unittest.main()
