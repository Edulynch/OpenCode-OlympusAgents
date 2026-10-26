"""Synthetic canary tests for the local Gitleaks boundary."""

from __future__ import annotations

import contextlib
import io
import json
import secrets
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import secret_gate  # noqa: E402
import check_docs  # noqa: E402


class SecretGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binary_dir = tempfile.TemporaryDirectory(prefix="olympus-gitleaks-test-bin-")
        cls.binary = secret_gate.ensure_binary(Path(cls.binary_dir.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.binary_dir.cleanup()

    def setUp(self) -> None:
        self.work = tempfile.TemporaryDirectory(prefix="olympus-gitleaks-test-repo-")
        self.repo = Path(self.work.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.config = self.repo / "gitleaks-test.toml"
        self.config.write_text('[extend]\nuseDefault = true\n', encoding="utf-8")
        self.ignore_file = self.repo / ".gitleaksignore"
        self.ignore_file.write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self.work.cleanup()

    def git(self, *args: str) -> str:
        result = subprocess.run(["git", *args], cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(result.returncode, 0, "synthetic Git fixture setup failed")
        return result.stdout.decode("utf-8").strip()

    def commit(self, message: str) -> str:
        self.git("add", "--all")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    @staticmethod
    def canary() -> str:
        # A synthetic-format marker; never sent to or checked against a provider.
        alphabet = string.ascii_letters + string.digits
        return "ghp_" + "".join(secrets.choice(alphabet) for _ in range(36))

    def gitleaks_result(self, command: str, source: Path, *, all_history: bool = False) -> subprocess.CompletedProcess[bytes]:
        args = [str(self.binary), command, "--config", str(self.config), "--gitleaks-ignore-path", str(self.ignore_file), "--ignore-gitleaks-allow", "--no-banner", "--redact=100", "--report-format", "json", "--report-path", "-", "--log-level", "fatal"]
        if command == "git":
            args.append("--log-opts=--all" if all_history else "--log-opts=HEAD")
        args.append(str(source))
        return secret_gate.quiet_run(args, cwd=self.repo)

    def test_positive_canary_is_detected_and_fully_redacted(self) -> None:
        canary = self.canary()
        (self.repo / "docs-canary.md").write_text(f"synthetic_key={canary}\n", encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-positive-stage-") as stage_name:
            staged = Path(stage_name)
            count = secret_gate.current_files(self.repo, staged)
            self.assertGreater(count, 0)
            result = self.gitleaks_result("dir", staged)
        self.assertEqual(result.returncode, 1, "the positive synthetic canary must fail the scan")
        self.assertGreater(secret_gate._result_count(result), 0)
        self.assertNotIn(canary.encode(), result.stdout)
        self.assertNotIn(canary.encode(), result.stderr)
        decoded = json.loads(result.stdout)
        self.assertTrue(all(canary not in str(finding.get("Match", "")) for finding in decoded))
        self.assertTrue(all(canary not in str(finding.get("Secret", "")) for finding in decoded))

    def test_negative_canary_passes_files_scan(self) -> None:
        (self.repo / "readme.txt").write_text("GITLEAKS_SYNTHETIC_NEGATIVE_MARKER\n", encoding="utf-8")
        self.commit("negative synthetic fixture")
        with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-stage-") as stage_name:
            staged = Path(stage_name)
            count = secret_gate.current_files(self.repo, staged)
            self.assertGreater(count, 0)
            status, findings = secret_gate.scan_files(self.binary, staged, cwd=self.repo, config=self.config, ignore_file=self.ignore_file)
        self.assertEqual((status, findings), (0, 0))

    def test_current_files_accepts_a_canonical_nested_path_alias(self) -> None:
        nested = self.repo / "nested"
        nested.mkdir()
        alias = nested / ".."
        with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-alias-stage-") as stage_name:
            count = secret_gate.current_files(alias, Path(stage_name))
        self.assertGreater(count, 0)

    def test_canary_in_removed_commit_is_detected_by_history_scan(self) -> None:
        canary = self.canary()
        target = self.repo / "historical.txt"
        target.write_text(f"synthetic_key={canary}\n", encoding="utf-8")
        self.commit("synthetic canary commit")
        target.write_text("removed synthetic canary\n", encoding="utf-8")
        self.commit("remove synthetic canary from current tree")
        result = self.gitleaks_result("git", self.repo, all_history=True)
        self.assertEqual(result.returncode, 1, "the synthetic historical canary must fail the history scan")
        self.assertGreater(secret_gate._result_count(result), 0)
        self.assertNotIn(canary.encode(), result.stdout)
        self.assertNotIn(canary.encode(), result.stderr)

    def test_gate_output_never_contains_canary(self) -> None:
        canary = self.canary()
        (self.repo / "public.md").write_text(f"synthetic_key={canary}\n", encoding="utf-8")
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status = secret_gate.run_gate(self.repo, self.binary, all_history=True)
        self.assertEqual(status, 1)
        self.assertNotIn(canary, stream.getvalue())
        self.assertIn("output was redacted and discarded", stream.getvalue())

    def test_bad_history_base_fails_closed(self) -> None:
        self.commit("empty baseline")
        with self.assertRaises(secret_gate.GateError):
            secret_gate.resolve_base(self.repo, "not-a-real-commit")

    def test_download_integrity_mismatch_is_rejected_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-bad-archive-") as directory:
            with mock.patch.object(secret_gate.platform, "system", return_value="Windows"), mock.patch.object(
                secret_gate.platform, "machine", return_value="AMD64"
            ), mock.patch.object(secret_gate.urllib.request, "urlopen", return_value=io.BytesIO(b"tampered archive")):
                with self.assertRaisesRegex(secret_gate.GateError, "SHA-256"):
                    secret_gate.ensure_binary(Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])


class DocumentationLinkGateTests(unittest.TestCase):
    def test_only_the_six_known_history_attachments_are_notices(self) -> None:
        with tempfile.TemporaryDirectory(prefix="olympus-doc-link-test-") as temporary:
            root = Path(temporary)
            report = root / "specs" / "001-portable-olympus-cli" / "evidence" / "r49-20261014-c30a19d" / "report.md"
            report.parent.mkdir(parents=True)
            source_name = "specs/001-portable-olympus-cli/evidence/r49-20261014-c30a19d/report.md"
            attachments = sorted(target for source, target in check_docs.KNOWN_UNVERSIONED_ATTACHMENTS if source == source_name)
            self.assertEqual(len(attachments), 6)
            for target in attachments:
                (report.parent / target).write_text("synthetic empty attachment\n", encoding="utf-8")
            refs = " ".join(f"[historical]({target})" for target in attachments)
            # The seventh missing target is in the same evidence report and must fail.
            report.write_text(f"{refs} [new file](newly-missing.json)\n", encoding="utf-8")
            with mock.patch.object(check_docs, "ROOT", root):
                failures, notices = check_docs.check_links([report])
        self.assertEqual(len(notices), 6)
        self.assertEqual(len(failures), 1)
        self.assertIn("missing local link target", failures[0])


if __name__ == "__main__":
    unittest.main()
