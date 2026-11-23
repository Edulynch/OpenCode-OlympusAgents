from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import pre_push  # noqa: E402


class PushSelectionTests(unittest.TestCase):
    def test_documentation_classification_is_conservative(self) -> None:
        for path in ("README.md", "docs/guide.md", "specs/feature/brief.md", "docs/assets/diagram.svg"):
            with self.subTest(path=path):
                self.assertTrue(pre_push.is_documentation_path(path))
        for path in (
            "CODEX.md",
            "olympus/policies/routing.md",
            ".opencode/prompts/kael.md",
            ".codex/instructions.md",
            "tests/fixture.md",
            "scripts/check.py",
            "docs/check.py",
        ):
            with self.subTest(path=path):
                self.assertFalse(pre_push.is_documentation_path(path))

    def test_first_push_falls_back_to_all_tracked_files(self) -> None:
        with patch.object(pre_push, "resolve_commit", return_value="a" * 40) as resolve, patch.object(
            pre_push, "tracked_paths", return_value=["README.md", "src/core.py"]
        ) as tracked:
            self.assertEqual(pre_push.paths_for_push("0" * 40, "a" * 40), ["README.md", "src/core.py"])
        self.assertEqual(resolve.call_args_list[0].args, ("a" * 40,))
        self.assertEqual(resolve.call_args_list[1].args, ("HEAD",))
        tracked.assert_called_once_with()

    def test_missing_range_falls_back_to_all_tracked(self) -> None:
        with patch.object(pre_push, "resolve_commit", return_value="a" * 40), patch.object(
            pre_push, "tracked_paths", return_value=["src/core.py"]
        ) as tracked:
            self.assertEqual(pre_push.paths_for_push(None, None), ["src/core.py"])
        tracked.assert_called_once_with()

    def test_all_files_without_local_branch_does_not_invent_a_target(self) -> None:
        with patch.object(pre_push, "resolve_commit", return_value="a" * 40) as resolve, patch.object(
            pre_push, "tracked_paths", return_value=["src/core.py"]
        ) as tracked:
            self.assertEqual(pre_push.paths_for_push(None, None), ["src/core.py"])
        self.assertEqual(resolve.call_args_list[0].args, ("HEAD",))
        self.assertEqual(resolve.call_count, 1)
        tracked.assert_called_once_with()

    def test_incomplete_or_wrong_target_range_fails_closed(self) -> None:
        with self.assertRaises(pre_push.GateError):
            pre_push.paths_for_push("a" * 40, None)
        with patch.object(pre_push, "resolve_commit", side_effect=["b" * 40, "a" * 40]):
            with self.assertRaises(pre_push.GateError):
                pre_push.paths_for_push("a" * 40, "b" * 40)

    def test_diff_disables_rename_detection_and_preserves_deleted_paths(self) -> None:
        changed = b"docs/old.md\0docs/new.md\0src/deleted.py\0"
        with patch.object(pre_push, "resolve_commit", side_effect=["b" * 40, "b" * 40, "a" * 40]), patch.object(
            pre_push, "git_output", return_value=changed
        ) as git:
            self.assertEqual(
                pre_push.paths_for_push("a" * 40, "b" * 40),
                ["docs/old.md", "docs/new.md", "src/deleted.py"],
            )
        self.assertEqual(
            git.call_args.args[0],
            ["diff", "--name-only", "-z", "--no-renames", "a" * 40, "b" * 40, "--"],
        )

    def test_native_update_parser_accepts_sha1_and_sha256_new_refs(self) -> None:
        for size in (40, 64):
            with self.subTest(oid_size=size):
                zero = "0" * size
                oid = "a" * size
                updates = pre_push.parse_push_updates(
                    f"refs/heads/main {oid} refs/heads/main {zero}\n".encode()
                )
                self.assertEqual(updates, [("refs/heads/main", oid, "refs/heads/main", zero)])
                with patch.object(pre_push, "resolve_commit", return_value=oid), patch.object(
                    pre_push, "tracked_paths", return_value=["README.md"]
                ) as tracked:
                    self.assertEqual(pre_push.paths_for_hook_updates(updates), ["README.md"])
                tracked.assert_called_once_with()

    def test_native_update_parser_recognizes_deletion_and_empty_input(self) -> None:
        self.assertEqual(pre_push.parse_push_updates(b""), [])
        updates = pre_push.parse_push_updates(
            f"(delete) {'0' * 40} refs/heads/old {'a' * 40}\n".encode()
        )
        self.assertIsNone(pre_push.paths_for_hook_updates(updates))

    def test_native_update_parser_rejects_malformed_and_inconsistent_records(self) -> None:
        cases = (
            b"refs/heads/main\n",
            f"refs/heads/main {'a' * 40} refs/heads/main {'0' * 64}\n".encode(),
            f"refs/heads/main {'0' * 40} refs/heads/main {'a' * 40}\n".encode(),
            f"(delete) {'a' * 40} refs/heads/main {'b' * 40}\n".encode(),
            f"refs/heads/main {'a' * 40} invalid..ref {'0' * 40}\n".encode(),
            f"refs/heads/main {'a' * 39} refs/heads/main {'0' * 40}\n".encode(),
            f"(delete) {'0' * 40} refs/heads/main {'0' * 40}\n".encode(),
        )
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(pre_push.GateError):
                    pre_push.parse_push_updates(payload)

    def test_multiple_non_deletion_updates_are_rejected(self) -> None:
        oid = "a" * 40
        zero = "0" * 40
        updates = [
            ("refs/heads/main", oid, "refs/heads/main", zero),
            ("refs/heads/side", oid, "refs/heads/side", zero),
        ]
        with self.assertRaisesRegex(pre_push.GateError, "one non-deletion ref"):
            pre_push.paths_for_hook_updates(updates)

    def test_one_update_among_deletions_is_selected(self) -> None:
        oid = "a" * 40
        zero = "0" * 40
        updates = [
            ("(delete)", zero, "refs/heads/old", oid),
            ("refs/heads/main", oid, "refs/heads/main", zero),
        ]
        with patch.object(pre_push, "paths_for_push", return_value=["README.md"]) as paths:
            self.assertEqual(pre_push.paths_for_hook_updates(updates), ["README.md"])
        paths.assert_called_once_with(zero, oid)

    def test_revision_flag_injection_and_git_errors_fail_closed(self) -> None:
        with self.assertRaises(pre_push.GateError):
            pre_push.resolve_commit("--help")
        with patch.object(pre_push, "git_output", side_effect=pre_push.GateError("Git unavailable")):
            with self.assertRaises(pre_push.GateError):
                pre_push.tracked_paths()

    def test_unavailable_remote_object_fails_closed(self) -> None:
        with patch.object(pre_push, "git_output", side_effect=pre_push.GateError("remote object unavailable")):
            with self.assertRaisesRegex(pre_push.GateError, "remote object unavailable"):
                pre_push.resolve_commit("a" * 40)

    def test_tracked_dirty_check_ignores_untracked_but_fails_on_tracked_changes(self) -> None:
        with patch.object(pre_push, "git_output", return_value=b"") as git:
            pre_push.require_clean_tracked_tree()
        self.assertIn("--untracked-files=no", git.call_args.args[0])
        with patch.object(pre_push, "git_output", return_value=b" M tracked.py\0"):
            with self.assertRaises(pre_push.GateError):
                pre_push.require_clean_tracked_tree()

    def test_native_hook_empty_and_deletion_input_skip_checks(self) -> None:
        for payload in (
            b"",
            f"(delete) {'0' * 40} refs/heads/old {'a' * 40}\n".encode(),
        ):
            with self.subTest(payload=payload), patch.object(pre_push, "require_clean_tracked_tree") as clean:
                self.assertEqual(pre_push.main(["--git-hook"], hook_input=payload), 0)
                clean.assert_not_called()


class RunCheckEnvironmentTests(unittest.TestCase):
    def test_run_check_removes_only_git_local_vars_from_child_environment(self) -> None:
        local_vars = b"GIT_DIR\nGIT_WORK_TREE\nGIT_COMMON_DIR\nGIT_INDEX_FILE\nGIT_CONFIG_PARAMETERS\n"
        values = {
            "GIT_DIR": "outer-git-dir",
            "GIT_WORK_TREE": "outer-worktree",
            "GIT_COMMON_DIR": "outer-common-dir",
            "GIT_INDEX_FILE": "outer-index",
            "GIT_CONFIG_PARAMETERS": "'core.bare=true'",
            "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
            "PATH": "fixture-path",
            "OLYMPUS_PUSH_SENTINEL": "preserved",
        }
        with patch.dict(os.environ, values, clear=False):
            parent_before = os.environ.copy()
            with patch.object(pre_push, "git_output", return_value=local_vars) as enumerate_vars, patch.object(
                pre_push.subprocess, "run", return_value=subprocess.CompletedProcess(["check"], 0)
            ) as run:
                pre_push.run_check("fixture", ["check"])

            enumerate_vars.assert_called_once_with(["rev-parse", "--local-env-vars"])
            run.assert_called_once()
            child_env = run.call_args.kwargs["env"]
            self.assertIsNot(child_env, os.environ)
            for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_CONFIG_PARAMETERS"):
                self.assertNotIn(name, child_env)
            for name in ("GIT_SSH_COMMAND", "PATH", "OLYMPUS_PUSH_SENTINEL"):
                self.assertEqual(child_env[name], values[name])
            self.assertEqual(os.environ, parent_before)

    def test_run_check_does_not_launch_child_if_git_env_enumeration_fails(self) -> None:
        with patch.object(pre_push, "git_output", side_effect=pre_push.GateError("Git unavailable")) as enumerate_vars, patch.object(
            pre_push.subprocess, "run"
        ) as run:
            with self.assertRaisesRegex(pre_push.GateError, "Git unavailable"):
                pre_push.run_check("fixture", ["check"])
        enumerate_vars.assert_called_once_with(["rev-parse", "--local-env-vars"])
        run.assert_not_called()

    def test_run_check_isolates_nested_git_fixture_from_outer_repository(self) -> None:
        local_names = pre_push.git_output(["rev-parse", "--local-env-vars"]).decode("ascii").splitlines()
        clean_env = os.environ.copy()
        for name in local_names:
            clean_env.pop(name, None)
        fixture_root = Path(os.environ.get("OLYMPUS_TEST_ROOT", tempfile.gettempdir()))
        self.assertTrue(fixture_root.is_dir())

        with tempfile.TemporaryDirectory(prefix="pre-push-env-", dir=fixture_root) as directory:
            fixture = Path(directory)
            outer = fixture / "outer"
            inner = fixture / "inner"
            outer.mkdir()
            inner.mkdir()
            outer_readme = outer / "README.md"
            outer_readme.write_text("outer sentinel\n", encoding="utf-8")
            outer_readme_bytes = outer_readme.read_bytes()
            (inner / "README.md").write_text("inner sentinel\n", encoding="utf-8")

            for command in (
                ["git", "init", "--quiet", str(outer)],
                ["git", "-C", str(outer), "config", "core.bare", "false"],
                ["git", "-C", str(outer), "add", "--", "README.md"],
                [
                    "git", "-C", str(outer), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid",
                    "commit", "--quiet", "-m", "outer sentinel",
                ],
            ):
                subprocess.run(command, cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            outer_gitdir = Path(
                subprocess.run(
                    ["git", "-C", str(outer), "rev-parse", "--absolute-git-dir"],
                    cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                ).stdout.strip()
            )
            outer_index = Path(
                subprocess.run(
                    ["git", "-C", str(outer), "rev-parse", "--git-path", "index"],
                    cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                ).stdout.strip()
            )
            if not outer_index.is_absolute():
                outer_index = outer / outer_index
            outer_head = subprocess.run(
                ["git", "-C", str(outer), "rev-parse", "HEAD"],
                cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ).stdout.strip()
            outer_index_bytes = outer_index.read_bytes()
            outer_config_bytes = (outer_gitdir / "config").read_bytes()
            outer_status = subprocess.run(
                ["git", "-C", str(outer), "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ).stdout
            outer_entries = subprocess.run(
                ["git", "-C", str(outer), "ls-files", "--stage"],
                cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ).stdout
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(outer), "config", "--local", "--get", "core.bare"],
                    cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                ).stdout.strip(),
                "false",
            )

            child = """
import os
import subprocess
import sys

inner = sys.argv[1]
def git(*args):
    result = subprocess.run(
        ["git", "-C", inner, *args], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise SystemExit(result.stderr.decode("utf-8", errors="replace"))

git("init", "--quiet")
git("add", "--", "README.md")
git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
    "commit", "--quiet", "-m", "inner sentinel")
top = subprocess.run(
    ["git", "-C", inner, "rev-parse", "--show-toplevel"],
    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
).stdout.strip()
assert os.path.samefile(top, inner)
assert os.environ.get("GIT_SSH_COMMAND") == "ssh -o BatchMode=yes"
assert os.environ.get("OLYMPUS_PUSH_SENTINEL") == "preserved"
for name in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
    assert name not in os.environ, name
"""
            controlled_env = clean_env.copy()
            controlled_env.update(
                {
                    "GIT_DIR": str(outer_gitdir),
                    "GIT_COMMON_DIR": str(outer_gitdir),
                    "GIT_WORK_TREE": str(outer),
                    "GIT_INDEX_FILE": str(outer_index),
                    "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
                    "OLYMPUS_PUSH_SENTINEL": "preserved",
                }
            )
            with patch.dict(os.environ, controlled_env, clear=True), patch.object(pre_push, "ROOT", outer):
                parent_before = os.environ.copy()
                pre_push.run_check("nested Git fixture", [sys.executable, "-c", child, str(inner)])
                self.assertEqual(os.environ, parent_before)

            inner_head = subprocess.run(
                ["git", "-C", str(inner), "rev-parse", "HEAD"],
                cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ).stdout.strip()
            self.assertTrue(inner_head)
            self.assertEqual(outer_readme.read_bytes(), outer_readme_bytes)
            self.assertEqual((outer_gitdir / "config").read_bytes(), outer_config_bytes)
            self.assertEqual(outer_index.read_bytes(), outer_index_bytes)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(outer), "rev-parse", "HEAD"],
                    cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                ).stdout.strip(),
                outer_head,
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(outer), "status", "--porcelain=v1", "--untracked-files=all"],
                    cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ).stdout,
                outer_status,
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(outer), "ls-files", "--stage"],
                    cwd=ROOT, env=clean_env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ).stdout,
                outer_entries,
            )


@unittest.skipUnless(
    os.name == "nt" and shutil.which("pwsh") and shutil.which("python"),
    "native hook integration requires the supported Windows Git, Python, and PowerShell environment",
)
class NativeBarePushTests(unittest.TestCase):
    def test_checked_in_native_hook_qualifies_pushes_and_blocks_unsafe_updates(self) -> None:
        temp_base = Path(tempfile.gettempdir()) / "opencode" / "olympus-native-hook-tests"
        temp_base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="fixture-", dir=temp_base) as directory:
            fixture = Path(directory)
            worktree = fixture / "worktree"
            remote = fixture / "remote.git"
            log = fixture / "checks.log"
            env = os.environ.copy()
            env["OLYMPUS_GATE_LOG"] = str(log)
            env["GIT_ALLOW_PROTOCOL"] = "file"

            def run(
                args: list[str],
                cwd: Path | None = None,
                check: bool = True,
                **extra: str,
            ) -> subprocess.CompletedProcess[str]:
                result = subprocess.run(
                    args,
                    cwd=cwd,
                    env={**env, **extra},
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                if check and result.returncode:
                    self.fail(f"Command failed ({result.returncode}): {args}\n{result.stdout}")
                return result

            run(["git", "init", "--bare", str(remote)])
            run(["git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main"])
            run(["git", "--git-dir", str(remote), "config", "receive.denyDeleteCurrent", "ignore"])
            run(["git", "init", str(worktree)])
            run(["git", "-C", str(worktree), "checkout", "-b", "main"])
            run(["git", "-C", str(worktree), "config", "user.name", "Native Hook Test"])
            run(["git", "-C", str(worktree), "config", "user.email", "native-hook@example.invalid"])

            hooks = worktree / ".githooks"
            scripts = worktree / "scripts"
            hooks.mkdir()
            scripts.mkdir()
            (worktree / "docs").mkdir()
            (worktree / "src").mkdir()
            shutil.copyfile(ROOT / ".githooks" / "pre-push", hooks / "pre-push")
            shutil.copyfile(ROOT / ".gitattributes", worktree / ".gitattributes")
            os.chmod(hooks / "pre-push", hooks.joinpath("pre-push").stat().st_mode | stat.S_IXUSR)
            shutil.copyfile(pre_push.__file__, scripts / "pre_push.py")
            (scripts / "check_docs.py").write_text(
                "import os\n"
                "with open(os.environ['OLYMPUS_GATE_LOG'], 'a', encoding='utf-8') as out: out.write('docs\\n')\n"
                "raise SystemExit(int(os.environ.get('OLYMPUS_GATE_DOCS_EXIT', '0')))\n",
                encoding="utf-8",
            )
            (scripts / "qualify.ps1").write_text(
                "Add-Content -LiteralPath $env:OLYMPUS_GATE_LOG -Value 'fast'\n"
                "exit [int]$env:OLYMPUS_GATE_FAST_EXIT\n",
                encoding="utf-8",
            )
            (worktree / "README.md").write_text("# Fixture\n", encoding="utf-8")
            (worktree / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
            (worktree / "src" / "core.py").write_text("value = 1\n", encoding="utf-8")
            run(["git", "-C", str(worktree), "add", "-A"])
            run(["git", "-C", str(worktree), "update-index", "--chmod=+x", ".githooks/pre-push"])
            run(["git", "-C", str(worktree), "commit", "-m", "fixture initial state"])
            run(["git", "-C", str(worktree), "config", "--local", "core.hooksPath", ".githooks"])
            run(["git", "-C", str(worktree), "remote", "add", "origin", str(remote)])
            run(["git", "-C", str(worktree), "push", "--set-upstream", "origin", "main"])
            first_remote = run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"]).stdout.strip()
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs", "fast"])

            log.write_text("", encoding="utf-8")
            run(["git", "-C", str(worktree), "branch", "stale", first_remote])
            (worktree / "src" / "core.py").write_text("value = 2\n", encoding="utf-8")
            run(["git", "-C", str(worktree), "add", "src/core.py"])
            run(["git", "-C", str(worktree), "commit", "-m", "fixture code change"])
            wrong_head = run(
                ["git", "-C", str(worktree), "push", "origin", "stale:refs/heads/stale"],
                check=False,
            )
            self.assertNotEqual(wrong_head.returncode, 0, wrong_head.stdout)
            self.assertIn("not the clean checked-out HEAD", wrong_head.stdout)
            self.assertEqual(log.read_text(encoding="utf-8"), "")

            (worktree / "README.md").write_text("# Dirty fixture\n", encoding="utf-8")
            dirty = run(["git", "-C", str(worktree), "push"], check=False)
            self.assertNotEqual(dirty.returncode, 0, dirty.stdout)
            self.assertIn("Tracked files or the index are dirty", dirty.stdout)
            self.assertEqual(log.read_text(encoding="utf-8"), "")
            (worktree / "README.md").write_text("# Fixture\n", encoding="utf-8")

            blocked = run(["git", "-C", str(worktree), "push"], check=False, OLYMPUS_GATE_FAST_EXIT="23")
            self.assertNotEqual(blocked.returncode, 0, blocked.stdout)
            self.assertIn("FAST failed", blocked.stdout)
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs", "fast"])
            self.assertEqual(
                run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"]).stdout.strip(),
                first_remote,
            )

            log.write_text("", encoding="utf-8")
            run(["git", "-C", str(worktree), "push"])
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs", "fast"])
            run(["git", "-C", str(worktree), "tag", "-a", "v-fixture", "-m", "annotated fixture tag"])
            log.write_text("", encoding="utf-8")
            run(["git", "-C", str(worktree), "push", "origin", "refs/tags/v-fixture"])
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs", "fast"])

            log.write_text("", encoding="utf-8")
            (worktree / "docs" / "guide.md").write_text("# Updated guide\n", encoding="utf-8")
            run(["git", "-C", str(worktree), "add", "docs/guide.md"])
            run(["git", "-C", str(worktree), "commit", "-m", "fixture docs change"])
            run(["git", "-C", str(worktree), "push"])
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs"])

            log.write_text("", encoding="utf-8")
            run(["git", "-C", str(worktree), "rm", "docs/guide.md"])
            run(["git", "-C", str(worktree), "commit", "-m", "fixture deleted documentation"])
            blocked_docs = run(
                ["git", "-C", str(worktree), "push"],
                check=False,
                OLYMPUS_GATE_DOCS_EXIT="17",
            )
            self.assertNotEqual(blocked_docs.returncode, 0, blocked_docs.stdout)
            self.assertIn("Documentation check failed", blocked_docs.stdout)
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs"])
            log.write_text("", encoding="utf-8")
            run(["git", "-C", str(worktree), "push"])
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs"])

            log.write_text("", encoding="utf-8")
            run(["git", "-C", str(worktree), "push", "origin", ":refs/heads/main"])
            self.assertEqual(log.read_text(encoding="utf-8"), "")
            self.assertNotEqual(
                run(["git", "--git-dir", str(remote), "show-ref", "--verify", "--quiet", "refs/heads/main"], check=False).returncode,
                0,
            )

            run(["git", "-C", str(worktree), "branch", "side"])
            multiple = run(["git", "-C", str(worktree), "push", "--all", "origin"], check=False)
            self.assertNotEqual(multiple.returncode, 0, multiple.stdout)
            self.assertIn("one non-deletion ref at a time", multiple.stdout)
            self.assertEqual(log.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
