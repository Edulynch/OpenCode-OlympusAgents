"""Synthetic canary tests for the local Gitleaks boundary."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import secrets
import string
import subprocess
import sys
import tempfile
import unittest
import urllib.error
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
            # Ignore a warm CI cache here: the test must exercise rejection of
            # the mocked network payload, not reuse a trusted earlier archive.
            with mock.patch.dict(os.environ, {secret_gate.CACHE_DIR_ENV: ""}), mock.patch.object(
                secret_gate.platform, "system", return_value="Windows"
            ), mock.patch.object(
                secret_gate.platform, "machine", return_value="AMD64"
            ), mock.patch.object(secret_gate.urllib.request, "urlopen", return_value=io.BytesIO(b"tampered archive")):
                with self.assertRaisesRegex(secret_gate.GateError, "SHA-256"):
                    secret_gate.ensure_binary(Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])


class GitleaksAcquisitionTests(unittest.TestCase):
    """Check network and cache failures without downloading or running Gitleaks."""

    @staticmethod
    def expected_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def test_transient_download_retries_then_verifies_archive(self) -> None:
        payload = b"synthetic Gitleaks archive"
        with mock.patch.dict(os.environ, {secret_gate.CACHE_DIR_ENV: ""}), mock.patch.object(
            secret_gate.urllib.request, "urlopen",
            side_effect=[urllib.error.URLError("temporary connection error"), io.BytesIO(payload)],
        ) as download, mock.patch.object(secret_gate.time, "sleep") as pause:
            result = secret_gate._download_asset("linux_x64.tar.gz", self.expected_hash(payload))
        self.assertEqual(result, payload)
        self.assertEqual(download.call_count, 2)
        pause.assert_called_once_with(1)

    def test_permanent_http_failure_does_not_retry(self) -> None:
        missing = urllib.error.HTTPError("https://example.invalid", 404, "missing", None, None)
        with mock.patch.dict(os.environ, {secret_gate.CACHE_DIR_ENV: ""}), mock.patch.object(
            secret_gate.urllib.request, "urlopen", side_effect=missing,
        ) as download, mock.patch.object(secret_gate.time, "sleep") as pause:
            with self.assertRaisesRegex(secret_gate.GateError, "HTTP 404"):
                secret_gate._download_asset("linux_x64.tar.gz", self.expected_hash(b"unused"))
        download.assert_called_once()
        pause.assert_not_called()

    def test_network_retries_are_bounded_and_redacted(self) -> None:
        # The underlying transport error might contain sensitive URL details;
        # the gate only reports a short, fixed failure description.
        with mock.patch.dict(os.environ, {secret_gate.CACHE_DIR_ENV: ""}), mock.patch.object(
            secret_gate.urllib.request, "urlopen", side_effect=urllib.error.URLError("token=synthetic-secret"),
        ) as download, mock.patch.object(secret_gate.time, "sleep") as pause:
            with self.assertRaises(secret_gate.GateError) as caught:
                secret_gate._download_asset("linux_x64.tar.gz", self.expected_hash(b"unused"))
        self.assertNotIn("synthetic-secret", str(caught.exception))
        self.assertEqual(download.call_count, secret_gate.DOWNLOAD_ATTEMPTS)
        self.assertEqual([call.args[0] for call in pause.call_args_list], [1, 3])

    def test_verified_cache_is_reused_without_network(self) -> None:
        payload = b"synthetic verified release archive"
        with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-cache-test-") as directory:
            with mock.patch.dict(os.environ, {secret_gate.CACHE_DIR_ENV: directory}), mock.patch.object(
                secret_gate.urllib.request, "urlopen", return_value=io.BytesIO(payload),
            ) as download:
                first = secret_gate._download_asset("linux_x64.tar.gz", self.expected_hash(payload))
                second = secret_gate._download_asset("linux_x64.tar.gz", self.expected_hash(payload))
            self.assertEqual((first, second), (payload, payload))
            # Only a verified artifact may be published to the on-disk cache.
            self.assertEqual(download.call_count, 1)
            cache = Path(directory) / f"gitleaks_{secret_gate.VERSION}_linux_x64.tar.gz"
            self.assertEqual(cache.read_bytes(), payload)

    def test_tampered_cache_fails_closed_without_network(self) -> None:
        payload = b"original synthetic release archive"
        with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-tamper-test-") as directory:
            cache = Path(directory) / f"gitleaks_{secret_gate.VERSION}_linux_x64.tar.gz"
            cache.write_bytes(b"modified archive")
            with mock.patch.dict(os.environ, {secret_gate.CACHE_DIR_ENV: directory}), mock.patch.object(
                secret_gate.urllib.request, "urlopen",
            ) as download:
                with self.assertRaisesRegex(secret_gate.GateError, "SHA-256"):
                    secret_gate._download_asset("linux_x64.tar.gz", self.expected_hash(payload))
            download.assert_not_called()

    def test_cache_symlink_is_never_followed(self) -> None:
        payload = b"synthetic trusted archive"
        with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-link-test-") as directory:
            target = Path(directory) / "outside-cache"
            target.write_bytes(payload)
            cache = Path(directory) / f"gitleaks_{secret_gate.VERSION}_linux_x64.tar.gz"
            try:
                cache.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("local filesystem does not permit symlink fixtures")
            with mock.patch.dict(os.environ, {secret_gate.CACHE_DIR_ENV: directory}), mock.patch.object(
                secret_gate.urllib.request, "urlopen",
            ) as download:
                with self.assertRaisesRegex(secret_gate.GateError, "cache"):
                    secret_gate._download_asset("linux_x64.tar.gz", self.expected_hash(payload))
            download.assert_not_called()

    def test_uncontained_cache_path_is_rejected(self) -> None:
        with mock.patch.dict(os.environ, {secret_gate.CACHE_DIR_ENV: "relative/../cache"}):
            with self.assertRaisesRegex(secret_gate.GateError, "absolute, contained"):
                secret_gate._download_asset("linux_x64.tar.gz", self.expected_hash(b"unused"))

    def test_mismatched_download_cannot_seed_cache(self) -> None:
        with tempfile.TemporaryDirectory(prefix="olympus-gitleaks-invalid-test-") as directory:
            with mock.patch.dict(os.environ, {secret_gate.CACHE_DIR_ENV: directory}), mock.patch.object(
                secret_gate.urllib.request, "urlopen", return_value=io.BytesIO(b"unexpected payload"),
            ):
                with self.assertRaisesRegex(secret_gate.GateError, "SHA-256"):
                    secret_gate._download_asset("linux_x64.tar.gz", self.expected_hash(b"trusted payload"))
            self.assertEqual(list(Path(directory).iterdir()), [])


class LocalHookConfigTests(unittest.TestCase):
    def test_opt_in_hook_pins_official_gitleaks_and_preserves_ci(self) -> None:
        hook = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "secrets.yml").read_text(encoding="utf-8")
        self.assertIn("repo: https://github.com/gitleaks/gitleaks", hook)
        self.assertIn("rev: 83d9cd684c87d95d656c1458ef04895a7f1cbd8e", hook)
        self.assertIn("- id: gitleaks", hook)
        # An optional commit-time check cannot silently replace the history
        # and current-file security scan that already runs on CI.
        self.assertIn("python -B scripts/secret_gate.py", workflow)
        self.assertIn("OLYMPUS_GITLEAKS_CACHE_DIR", workflow)
        self.assertIn("actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9", workflow)


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
