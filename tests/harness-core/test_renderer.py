"""Focused tests for detached OpenCode renderer candidates."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("candidate_renderer", ROOT / "scripts/render_harnesses.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class CandidateRendererTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(tempfile.gettempdir())
        preferred_temp = temp_root / "opencode"
        if preferred_temp.is_dir():
            temp_root = preferred_temp
        self.temporary = tempfile.TemporaryDirectory(prefix="olympus-renderer-", dir=temp_root)
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.source = self.sandbox / "source fixture"
        self.destination = self.sandbox / "candidate fixture"
        shutil.copytree(
            ROOT / "olympus",
            self.source / "olympus",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        self.expected = renderer.outputs_for(self.source, "opencode")
        capabilities = renderer.checked_sources(self.source)[2]
        self.expected[self.source / "docs" / "HARNESS-CAPABILITIES.md"] = renderer.capability_doc(capabilities)

    def invoke(self, *arguments: str):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = renderer.main(["--root", str(self.source), *arguments])
        return code, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def snapshot(root: Path):
        if not root.exists():
            return {}
        inventory = {}
        for path in root.rglob("*"):
            metadata = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISLNK(metadata.st_mode):
                inventory[relative] = ("symlink", os.readlink(path))
            elif stat.S_ISDIR(metadata.st_mode):
                inventory[relative] = ("directory", metadata.st_mtime_ns)
            elif stat.S_ISREG(metadata.st_mode):
                inventory[relative] = ("file", path.read_bytes(), metadata.st_mtime_ns)
            else:
                inventory[relative] = ("other", metadata.st_mode)
        return inventory

    def assert_source_outputs_absent(self):
        self.assertTrue(all(not path.exists() for path in self.expected))

    def test_detached_render_check_drift_and_idempotence(self):
        managed_count = len(self.expected)
        self.assert_source_outputs_absent()
        code, stdout, stderr = self.invoke("render", "--output-root", str(self.destination))
        self.assertEqual(0, code, stderr)
        self.assertIn(f"wrote {managed_count} changed output(s), 0 unchanged", stdout)
        expected_paths = {path.relative_to(self.source).as_posix() for path in self.expected}
        actual_paths = {
            path.relative_to(self.destination).as_posix()
            for path in self.destination.rglob("*")
            if path.is_file()
        }
        self.assertEqual(expected_paths, actual_paths)
        self.assert_source_outputs_absent()

        before_check = self.snapshot(self.destination)
        code, stdout, stderr = self.invoke("check", "--output-root", str(self.destination))
        self.assertEqual(0, code, stderr)
        self.assertIn(f"{managed_count} managed output(s); read-only", stdout)
        self.assertEqual(before_check, self.snapshot(self.destination))

        drifted = self.destination / ".opencode" / "agents" / "kael.md"
        drifted.write_text(drifted.read_text(encoding="utf-8") + "\nfixture drift\n", encoding="utf-8")
        before_drift_check = self.snapshot(self.destination)
        code, stdout, stderr = self.invoke("check", "--output-root", str(self.destination))
        self.assertEqual(1, code, stderr)
        self.assertIn("DRIFT drift: .opencode/agents/kael.md", stdout)
        self.assertEqual(before_drift_check, self.snapshot(self.destination))

        code, stdout, stderr = self.invoke("render", "--output-root", str(self.destination))
        self.assertEqual(0, code, stderr)
        self.assertIn(f"wrote 1 changed output(s), {managed_count - 1} unchanged", stdout)
        code, stdout, stderr = self.invoke("render", "--output-root", str(self.destination))
        self.assertEqual(0, code, stderr)
        self.assertIn(f"wrote 0 changed output(s), {managed_count} unchanged", stdout)
        self.assert_source_outputs_absent()

    def test_overlapping_roots_are_rejected_before_writing(self):
        for destination in (self.source, self.source / "nested", self.source.parent):
            with self.subTest(destination=destination):
                before = self.snapshot(self.sandbox)
                code, stdout, stderr = self.invoke("render", "--output-root", str(destination))
                self.assertEqual(2, code)
                self.assertIn("--output-root must not overlap", stderr)
                self.assert_source_outputs_absent()
                self.assertEqual(before, self.snapshot(self.sandbox))

    def test_prunes_only_stale_generated_headers_in_managed_namespaces(self):
        destination = str(self.destination)
        code, _, stderr = self.invoke("render", "--output-root", destination)
        self.assertEqual(0, code, stderr)
        marker = renderer.GENERATED
        stale = {
            ".opencode/agents/retired.md": (
                f"---\n# {marker} Canonical Olympus role: olympus/roles/retired.md (Retired).\n---\n"
            ),
            ".opencode/commands/olympus.retired.md": f"---\ndescription: Retired\n---\n<!-- {marker} -->\n",
            ".opencode/plugins/olympus-activity/retired.ts": f"// {marker}\n",
            ".opencode/scripts/retired.ps1": f"# {marker}\n",
        }
        preserved = {
            ".opencode/agents/custom.md": f"---\ndescription: Custom\n---\nNotes mention {marker}\n",
            ".opencode/commands/olympus.custom.md": f"---\ndescription: Custom\n---\n<!-- {marker} (example) -->\n",
            ".opencode/agents/nested/retired.md": stale[".opencode/agents/retired.md"],
            ".opencode/plugins/custom/retired.ts": stale[".opencode/plugins/olympus-activity/retired.ts"],
            "scripts/retired.ps1": stale[".opencode/scripts/retired.ps1"],
        }
        for relative, content in (stale | preserved).items():
            target = self.destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        before = self.snapshot(self.destination)
        code, stdout, stderr = self.invoke("check", "--output-root", destination)
        self.assertEqual(1, code, stderr)
        self.assertEqual(set(stale), set(re.findall(r"^DRIFT obsolete: (.+)$", stdout, re.M)))
        self.assertEqual(before, self.snapshot(self.destination))
        code, stdout, stderr = self.invoke("render", "--output-root", destination)
        self.assertEqual(0, code, stderr)
        self.assertIn(f"pruned {len(stale)} obsolete output(s)", stdout)
        after = self.snapshot(self.destination)
        self.assertFalse(set(stale) & after.keys())
        self.assertEqual({path: before[path] for path in preserved}, {path: after[path] for path in preserved})
        code, stdout, stderr = self.invoke("render", "--output-root", destination)
        self.assertEqual(0, code, stderr)
        self.assertIn("wrote 0 changed output(s)", stdout)
        self.assertIn("pruned 0 obsolete output(s)", stdout)
        self.assertEqual(after, self.snapshot(self.destination))
        self.assertEqual(0, self.invoke("check", "--output-root", destination)[0])
        self.assert_source_outputs_absent()

    def test_symlinked_output_parent_is_rejected_before_writing(self):
        self.destination.mkdir()
        redirected = self.sandbox / "redirected"
        redirected.mkdir()
        link = self.destination / ".opencode"
        try:
            os.symlink(redirected, link, target_is_directory=True)
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"directory symlink creation unavailable: {error}")

        before_redirect = self.snapshot(redirected)
        code, stdout, stderr = self.invoke("render", "--output-root", str(self.destination))
        self.assertEqual(2, code)
        self.assertIn("symlink or reparse point", stderr)
        self.assertEqual(before_redirect, self.snapshot(redirected))
        self.assertEqual([link], list(self.destination.iterdir()))
        self.assert_source_outputs_absent()

    def test_pruning_does_not_follow_or_remove_unexpected_file_symlink(self):
        sentinel = self.sandbox / "linked-sentinel.md"
        sentinel.write_text(f"---\n# {renderer.GENERATED}\n---\n", encoding="utf-8")
        target = self.destination / ".opencode/agents/custom-link.md"
        target.parent.mkdir(parents=True)
        try:
            target.symlink_to(sentinel)
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"file symlink creation unavailable: {error}")
        before = sentinel.read_bytes()
        for action in ("render", "check"):
            code, stdout, stderr = self.invoke(action, "--output-root", str(self.destination))
            self.assertEqual(0, code, stderr)
            self.assertNotIn("custom-link", stdout)
            self.assertTrue(target.is_symlink())
            self.assertEqual(before, sentinel.read_bytes())

    def test_hardlinked_output_is_rejected_before_render_or_check(self):
        target = self.destination / ".opencode" / "agents" / "kael.md"
        target.parent.mkdir(parents=True)
        sentinel = self.sandbox / "external-sentinel.txt"
        sentinel.write_text("preserve", encoding="utf-8")
        try:
            os.link(sentinel, target)
        except (NotImplementedError, OSError) as error:
            self.skipTest(f"hardlink creation unavailable: {error}")

        before = sentinel.read_bytes()
        for action in ("render", "check"):
            with self.subTest(action=action):
                code, stdout, stderr = self.invoke(action, "--output-root", str(self.destination))
                self.assertEqual(2, code)
                self.assertIn("hardlinked candidate output", stderr)
                self.assertEqual(before, sentinel.read_bytes())
                self.assertEqual(before, target.read_bytes())
                self.assert_source_outputs_absent()

    def test_legacy_source_output_and_kael_behavior_without_output_root(self):
        managed_count = len(self.expected)
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = renderer.run(self.source, "render", "opencode")
        self.assertEqual(0, code)
        self.assertIn(f"wrote {managed_count} changed output(s), 0 unchanged", stdout.getvalue())
        for path, content in self.expected.items():
            self.assertEqual(content, path.read_text(encoding="utf-8"))

        code, kael, stderr = self.invoke("kael", "--max-children", "4")
        self.assertEqual(0, code, stderr)
        self.assertEqual(renderer.rendered_kael(self.source, 4), kael)
        with redirect_stderr(StringIO()) as error:
            with self.assertRaises(SystemExit) as raised:
                renderer.main([
                    "kael", "--root", str(self.source), "--max-children", "4",
                    "--output-root", str(self.destination),
                ])
        self.assertEqual(2, raised.exception.code)
        self.assertIn("--output-root is only supported with render/check", error.getvalue())

    def test_shared_primary_ceiling_and_three_current_primary_commands(self):
        outputs = renderer.outputs_for(self.source, "opencode", 7)
        for role in ("kael", "atlas"):
            prompt = outputs[self.source / ".opencode" / "agents" / f"{role}.md"]
            self.assertIn("MAX_ACTIVE_CHILDREN = 7", prompt)
            if role == "kael":
                self.assertIn("adapt from zero to seven children", prompt)

        command_paths = {
            path.name: content
            for path, content in outputs.items()
            if path.parent == self.source / ".opencode" / "commands"
        }
        self.assertEqual(
            set(command_paths),
            {"olympus.ultra.md", "olympus.performance.md", "olympus.performance-ultra.md"},
        )
        for name, content in command_paths.items():
            frontmatter = content.split("\n---\n", 1)[0]
            self.assertRegex(frontmatter, r"(?m)^subagent: false$")
            self.assertNotRegex(frontmatter, r"(?m)^agent:")
            self.assertIn(f"Usage: /{name.removesuffix('.md')} <prompt>", content)
            self.assertIn("Do not call tools or launch agents.", content)
            self.assertIn("Kael or Atlas primary session", content)
        self.assertIn("ULTRA_CEILING", command_paths["olympus.ultra.md"])
        self.assertIn("READY_WORKSTREAMS", command_paths["olympus.ultra.md"])
        self.assertIn("TARGET_ACTIVE", command_paths["olympus.ultra.md"])
        self.assertIn("CURRENT_ACTIVE", command_paths["olympus.ultra.md"])
        self.assertIn("DOMAIN_MODE: PERFORMANCE", command_paths["olympus.performance-ultra.md"])
        self.assertIn("EXECUTION_MODE: ULTRA", command_paths["olympus.performance-ultra.md"])

        rendered_primaries = renderer.rendered_primaries(self.source, 7)
        self.assertEqual(set(rendered_primaries), {"kael", "atlas"})
        self.assertTrue(all("MAX_ACTIVE_CHILDREN = 7" in prompt for prompt in rendered_primaries.values()))

        code, stdout, stderr = self.invoke("primaries", "--max-children", "6")
        self.assertEqual(0, code, stderr)
        primaries = json.loads(stdout)
        self.assertEqual(set(primaries), {"kael", "atlas"})
        self.assertTrue(all("MAX_ACTIVE_CHILDREN = 6" in prompt for prompt in primaries.values()))


if __name__ == "__main__":
    unittest.main()
