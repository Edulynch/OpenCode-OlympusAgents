from __future__ import annotations

import importlib.util
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
            self.assertEqual(pre_push.paths_for_push(None, None, "main"), ["src/core.py"])
        tracked.assert_called_once_with()

    def test_all_files_without_local_branch_does_not_invent_a_target(self) -> None:
        with patch.object(pre_push, "resolve_commit", return_value="a" * 40) as resolve, patch.object(
            pre_push, "tracked_paths", return_value=["src/core.py"]
        ) as tracked:
            self.assertEqual(pre_push.paths_for_push(None, None), ["src/core.py"])
        self.assertEqual(resolve.call_args_list[0].args, ("HEAD",))
        self.assertEqual(resolve.call_count, 1)
        tracked.assert_called_once_with()

    def test_missing_range_rejects_local_branch_that_is_not_head(self) -> None:
        with patch.object(pre_push, "resolve_commit", side_effect=["a" * 40, "b" * 40]) as resolve, patch.object(
            pre_push, "tracked_paths"
        ) as tracked:
            with self.assertRaises(pre_push.GateError):
                pre_push.paths_for_push(None, None, "other-branch")
        self.assertEqual(resolve.call_args_list[0].args, ("HEAD",))
        self.assertEqual(resolve.call_args_list[1].args, ("other-branch",))
        tracked.assert_not_called()

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

    def test_revision_flag_injection_and_git_errors_fail_closed(self) -> None:
        with self.assertRaises(pre_push.GateError):
            pre_push.resolve_commit("--help")
        with patch.object(pre_push, "git_output", side_effect=pre_push.GateError("Git unavailable")):
            with self.assertRaises(pre_push.GateError):
                pre_push.tracked_paths()

    def test_tracked_dirty_check_ignores_untracked_but_fails_on_tracked_changes(self) -> None:
        with patch.object(pre_push, "git_output", return_value=b"") as git:
            pre_push.require_clean_tracked_tree()
        self.assertIn("--untracked-files=no", git.call_args.args[0])
        with patch.object(pre_push, "git_output", return_value=b" M tracked.py\0"):
            with self.assertRaises(pre_push.GateError):
                pre_push.require_clean_tracked_tree()


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
            "PRE_COMMIT_FROM_REF": "from-sentinel",
            "PRE_COMMIT_TO_REF": "to-sentinel",
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
            for name in ("GIT_SSH_COMMAND", "PATH", "PRE_COMMIT_FROM_REF", "PRE_COMMIT_TO_REF"):
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
assert os.environ.get("PRE_COMMIT_FROM_REF") == "from-sentinel"
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
                    "PRE_COMMIT_FROM_REF": "from-sentinel",
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


@unittest.skipUnless(importlib.util.find_spec("pre_commit"), "pre-commit is not installed in this Python")
class LocalBarePushTests(unittest.TestCase):
    def test_installed_gate_blocks_failed_fast_without_updating_local_bare_remote(self) -> None:
        temp_base = Path(tempfile.gettempdir()) / "opencode" / "olympus-pre-push-qualification"
        temp_base.mkdir(parents=True, exist_ok=True)
        fixture = Path(tempfile.mkdtemp(prefix="run-", dir=temp_base))
        worktree = fixture / "worktree"
        remote = fixture / "remote.git"
        log = fixture / "checks.log"
        cache = fixture / "pre-commit-home"
        env = os.environ.copy()
        env["OLYMPUS_GATE_LOG"] = str(log)
        env["PRE_COMMIT_HOME"] = str(cache)
        env["GIT_ALLOW_PROTOCOL"] = "file"

        def run(args: list[str], cwd: Path | None = None, check: bool = True, **extra: str) -> subprocess.CompletedProcess[str]:
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

        try:
            run(["git", "init", "--bare", str(remote)])
            run(["git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main"])
            run(["git", "init", str(worktree)])
            run(["git", "checkout", "-b", "main"], cwd=worktree)
            run(["git", "config", "user.name", "Gate Test"], cwd=worktree)
            run(["git", "config", "user.email", "gate@example.invalid"], cwd=worktree)

            scripts = worktree / "scripts"
            scripts.mkdir()
            (worktree / "docs").mkdir()
            (worktree / "src").mkdir()
            (worktree / ".pre-commit-config.yaml").write_text(
                "repos:\n"
                "  - repo: local\n"
                "    hooks:\n"
                "      - id: olympus-pre-push-gate\n"
                "        name: Olympus FAST and documentation pre-push gate\n"
                "        entry: python -B scripts/pre_push.py\n"
                "        language: system\n"
                "        stages: [pre-push]\n"
                "        always_run: true\n"
                "        pass_filenames: false\n",
                encoding="utf-8",
            )
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

            self.assertFalse(cache.exists(), "pre-commit cache must start empty")
            run([sys.executable, "-m", "pre_commit", "install", "--hook-type", "pre-push", "--allow-missing-config"], cwd=worktree)
            run(["git", "add", "-A"], cwd=worktree)
            run(["git", "commit", "-m", "fixture initial state"], cwd=worktree)
            run(["git", "remote", "add", "origin", str(remote)], cwd=worktree)
            run(["git", "push", "--set-upstream", "origin", "main"], cwd=worktree)
            first_remote = run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"]).stdout.strip()
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs", "fast"])

            (worktree / "src" / "core.py").write_text("value = 2\n", encoding="utf-8")
            run(["git", "add", "src/core.py"], cwd=worktree)
            run(["git", "commit", "-m", "fixture code change"], cwd=worktree)
            blocked = run(["git", "push"], cwd=worktree, check=False, OLYMPUS_GATE_FAST_EXIT="23")
            self.assertNotEqual(blocked.returncode, 0, blocked.stdout)
            self.assertIn("FAST failed", blocked.stdout)
            self.assertEqual(
                run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"]).stdout.strip(),
                first_remote,
            )

            run(["git", "push"], cwd=worktree)
            log.write_text("", encoding="utf-8")
            (worktree / "docs" / "guide.md").write_text("# Updated guide\n", encoding="utf-8")
            run(["git", "add", "docs/guide.md"], cwd=worktree)
            run(["git", "commit", "-m", "fixture docs change"], cwd=worktree)
            run(["git", "push"], cwd=worktree)
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs"])

            log.write_text("", encoding="utf-8")
            before_delete_push = run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"]).stdout.strip()
            run(["git", "rm", "docs/guide.md"], cwd=worktree)
            run(["git", "commit", "-m", "fixture deleted documentation"], cwd=worktree)
            blocked_docs = run(["git", "push"], cwd=worktree, check=False, OLYMPUS_GATE_DOCS_EXIT="17")
            self.assertNotEqual(blocked_docs.returncode, 0, blocked_docs.stdout)
            self.assertIn("Documentation check failed", blocked_docs.stdout)
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs"])
            self.assertEqual(
                run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"]).stdout.strip(),
                before_delete_push,
            )

            log.write_text("", encoding="utf-8")
            run(["git", "push"], cwd=worktree)
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["docs"])
            self.assertFalse(
                cache.exists() and any(path.name.startswith("repo") for path in cache.iterdir()),
                "local hook fixture must not clone a remote hook repository",
            )
        finally:
            def retry_readonly_removal(function, path, _error) -> None:
                os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
                function(path)

            shutil.rmtree(fixture, onerror=retry_readonly_removal)


if __name__ == "__main__":
    unittest.main()
