"""Contained tests for the reversible global OpenCode default_agent receipt."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "install.ps1"
RELEASE = re.search(
    r"(?m)^\s*\[string\]\$Version\s*=\s*'([^']+)'",
    INSTALLER.read_text(encoding="utf-8"),
).group(1)
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from olympus.global_readonly import _default_agent_status, _jsonc_without_comments


def _iter_tests(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from _iter_tests(test)
        else:
            yield test


def load_tests(loader, standard_tests, pattern):
    shard = os.environ.get("OLYMPUS_DEFAULT_AGENT_SHARD")
    if shard is None:
        return standard_tests
    if shard not in {"1", "2"}:
        raise ValueError(f"OLYMPUS_DEFAULT_AGENT_SHARD must be 1 or 2; got {shard!r}")

    tests = sorted(_iter_tests(standard_tests), key=lambda test: test.id())
    selected = [test for index, test in enumerate(tests) if index % 2 == int(shard) - 1]
    if not selected:
        raise ValueError(f"OLYMPUS_DEFAULT_AGENT_SHARD={shard} selected no tests")
    return loader.suiteClass(selected)


BASE_CONFIG = (
    "{\n"
    "  // User comment with Unicode: snowman ☃\n"
    '  "user_note": "quoted \\"value\\" and ☃",\n'
    '  "permissions": [\n'
    '    {"action":"external_directory","resource":"*","effect":"ask"},\n'
    "  ],\n"
    "}\n"
)


def snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class DefaultAgentLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pwsh = shutil.which("pwsh")
        if os.name != "nt" or cls.pwsh is None:
            raise unittest.SkipTest("The global installer requires Windows and PowerShell 7.")
        preferred = os.environ.get("OLYMPUS_TEST_ROOT")
        if not preferred:
            raise RuntimeError("OLYMPUS_TEST_ROOT must point to the approved contained test root.")
        cls.test_root = Path(preferred)
        cls.test_root.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.sandbox = Path(tempfile.mkdtemp(prefix="default-agent-", dir=self.test_root))
        self.root = self.sandbox / "opencode"
        self.cli_root = self.sandbox / "cli"
        self.path_store = self.cli_root / "path-store.txt"
        self.root.mkdir()
        (self.root / ".olympus-cli-edit.lock").write_bytes(b"")
        self.user_file = self.sandbox / "olympus-config" / "config.json"
        self.appdata = self.sandbox / "appdata"
        self.localappdata = self.sandbox / "localappdata"
        self.profile = self.sandbox / "profile"
        for directory in (self.user_file.parent, self.appdata, self.localappdata, self.profile):
            directory.mkdir(parents=True)
        self.env = os.environ.copy()
        self.env.update({
            "OPENCODE_CONFIG_DIR": str(self.root),
            "CODEX_HOME": str(self.sandbox / "codex"),
            "OLYMPUS_CONFIG_FILE": str(self.user_file),
            "APPDATA": str(self.appdata),
            "LOCALAPPDATA": str(self.localappdata),
            "USERPROFILE": str(self.profile),
            "HOME": str(self.profile),
            "XDG_CONFIG_HOME": str(self.sandbox / "xdg"),
            "OLYMPUS_CLI_ROOT": str(self.cli_root),
            "OLYMPUS_CLI_PATH_STORE": str(self.path_store),
            "TEMP": str(self.test_root),
            "TMP": str(self.test_root),
            "TMPDIR": str(self.test_root),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        self.manifest = self.root / "olympus" / "orchestrator-install.json"

    def tearDown(self):
        shutil.rmtree(self.sandbox)

    def write_config(self, text: str = BASE_CONFIG, encoding: str = "utf-8") -> bytes:
        raw = text.encode(encoding)
        (self.root / "opencode.jsonc").write_bytes(raw)
        return raw

    def run_installer(self, *flags: str, source_archive: Path | None = None) -> subprocess.CompletedProcess[str]:
        command = [
            self.pwsh, "-NoProfile", "-NonInteractive", "-File", str(INSTALLER),
            *(["-SourceArchive", str(source_archive)] if source_archive else ["-SourceRoot", str(ROOT)]),
            "-Version", RELEASE,
            "-Scope", "global", "-Harness", "opencode",
            "-CliInstallRoot", str(self.cli_root), "-CliPathStorePath", str(self.path_store),
            *flags,
        ]
        return subprocess.run(
            command, cwd=ROOT, env=self.env, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=180, check=False,
        )

    def receipt(self) -> dict:
        return json.loads(self.manifest.read_text(encoding="utf-8"))["default_agent_receipt"]

    def config_object(self) -> dict:
        return json.loads(_jsonc_without_comments((self.root / "opencode.jsonc").read_bytes()))

    def install_ok(self):
        result = self.run_installer()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result

    def test_fresh_install_config_apply_preserves_receipted_config_and_verifies(self):
        self.install_ok()
        config = (self.root / "opencode.jsonc").read_bytes()
        receipt = self.receipt()
        entry = next(item for item in json.loads(self.manifest.read_bytes())["managed_files"]
                     if item["path"] == "opencode.jsonc")
        for mode in ("--dry-run", "--execute"):
            result = subprocess.run(
                [os.sys.executable, "-B", "-m", "olympus", "config", "apply",
                 "--scope", "global", "--harness", "opencode", mode, "--json"],
                cwd=ROOT, env=self.env, capture_output=True, text=True,
                encoding="utf-8", timeout=60, check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertNotIn("opencode.jsonc", {
                item["path"] for item in json.loads(result.stdout)["data"]["changes"]
            })
            self.assertEqual(config, (self.root / "opencode.jsonc").read_bytes())
            self.assertEqual(receipt, self.receipt())
            self.assertEqual(entry, next(item for item in json.loads(self.manifest.read_bytes())["managed_files"]
                                         if item["path"] == "opencode.jsonc"))
        before = snapshot(self.root)
        verified = self.run_installer("-VerifyOnly")
        self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)
        self.assertEqual(before, snapshot(self.root))

    def test_editor_interleaving_preserves_changes_during_set_and_restore(self):
        # Extract production functions only; the editor hook is deterministic,
        # not a claim about a timed race or an actual OpenCode runtime.
        script = r'''
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$ManifestRelative = 'olympus/orchestrator-install.json'
$OpenCodeConfigRelative = 'opencode.jsonc'
$DefaultAgentReceiptProperty = 'default_agent_receipt'
$OpenCodeGuardIntentRelative = 'olympus/opencode-guard-pending.json'
$GlobalApplyScratch = '.olympus-cli-config-apply'
$SourceVersion = 'local'
$Harness = 'opencode'
$DryRun = $false; $Force = $false; $VerifyOnly = $false; $Uninstall = $false; $Update = $false
$ProjectTarget = $env:USERPROFILE
$script:ModifiedManagedAgents = @(); $script:ConfirmedModifiedAgentPaths = @()
. (Join-Path $SourceRoot 'scripts/target-writer-lock.ps1')
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $SourceRoot 'scripts/global-install.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'FIXTURE_PARSE_FAILED' }
foreach ($node in $ast.EndBlock.Statements) {
    if ($node -is [Management.Automation.Language.FunctionDefinitionAst]) {
        . ([scriptblock]::Create($node.Extent.Text))
    }
}
$root = Join-Path $env:OPENCODE_CONFIG_DIR $env:OLYMPUS_EDITOR_CASE
$env:OPENCODE_CONFIG_DIR = $root
[IO.Directory]::CreateDirectory($root) | Out-Null
$config = Join-Path $root 'opencode.jsonc'
$before = '{"permissions":[{"action":"external_directory","resource":"*","effect":"ask"}]}'
if ($env:OLYMPUS_EDITOR_CASE -notin @('set-absent','restore-remove')) {
    $before = $before.Insert(1, '"default_agent":"before",')
}
[IO.File]::WriteAllText($config, $before, $Utf8NoBom)
$script:OriginalManifestWriter = (Get-Command Write-GlobalManifestObject).ScriptBlock
$script:Interleaved = $false
$script:ArmEditor = $true
function Write-GlobalManifestObject([string]$Path, [System.Collections.IDictionary]$Manifest) {
    & $script:OriginalManifestWriter $Path $Manifest
    if ($script:ArmEditor -and -not $script:Interleaved -and $env:OLYMPUS_EDITOR_CASE -like 'set-*' -and
        $Manifest.default_agent_receipt.state -ceq 'pending_set') {
        $during = $before.Insert(1, '"editor_note":true,')
        if ($env:OLYMPUS_EDITOR_CASE -eq 'set-absent') {
            $during = $during.Insert(1, '"default_agent":"user-during-install",')
        } elseif ($env:OLYMPUS_EDITOR_CASE -eq 'set-present') {
            $during = $during.Replace('"before"', '"user-during-install"')
        }
        [IO.File]::WriteAllText($config, $during, $Utf8NoBom)
        $script:Interleaved = $true
    }
}
if ($env:OLYMPUS_EDITOR_CASE -like 'restore-*') {
    Invoke-OneHarness 'opencode'
    $script:OriginalReader = (Get-Command Read-OpenCodeConfig).ScriptBlock
    $script:Reads = 0
    function Read-OpenCodeConfig([string]$Path) {
        $script:Reads++
        if ($script:Reads -eq 2) {
            $during = [IO.File]::ReadAllText($Path).Replace('"kael"', '"user-during-restore"')
            [IO.File]::WriteAllText($Path, $during, $Utf8NoBom)
            $script:Interleaved = $true
        }
        & $script:OriginalReader $Path
    }
    try {
        Restore-OpenCodeDefaultAgent $root ([pscustomobject](New-DefaultAgentReceipt 'opencode.jsonc' `
            ($env:OLYMPUS_EDITOR_CASE -eq 'restore-set') '"before"' 'pending_uninstall'))
        throw 'EXPECTED_CONFLICT'
    } catch {
        if ($_.Exception.Message -notmatch 'GLOBAL_DEFAULT_AGENT_RECOVERY_CONFLICT') { throw }
    }
    if (([IO.File]::ReadAllText($config) | ConvertFrom-Json).default_agent -cne 'user-during-restore') {
        throw 'RESTORE_LOST_EDITOR_CHANGE'
    }
} elseif ($env:OLYMPUS_EDITOR_CASE -eq 'set-unrelated') {
    Invoke-OneHarness 'opencode'
    $text = [IO.File]::ReadAllText($config) | ConvertFrom-Json
    if (-not $text.editor_note -or $text.default_agent -cne 'kael') { throw 'UNRELATED_EDIT_LOST' }
} else {
    try { Invoke-OneHarness 'opencode'; throw 'EXPECTED_CONFLICT' }
    catch {
        if ($_.Exception.Message -notmatch 'GLOBAL_DEFAULT_AGENT_RECOVERY_CONFLICT') { throw }
    }
    $text = [IO.File]::ReadAllText($config) | ConvertFrom-Json
    $receipt = ([IO.File]::ReadAllText((Join-Path $root $ManifestRelative)) | ConvertFrom-Json).default_agent_receipt
    if ($text.default_agent -cne 'user-during-install' -or $receipt.state -cne 'pending_set') {
        throw 'SET_LOST_EDITOR_CHANGE'
    }
    $Uninstall = $true
    Invoke-OneHarness 'opencode'
    if (([IO.File]::ReadAllText($config) | ConvertFrom-Json).default_agent -cne 'user-during-install') {
        throw 'UNINSTALL_RESTORED_STALE_VALUE'
    }
}
if (-not $script:Interleaved) { throw 'EDITOR_HOOK_NOT_REACHED' }
Write-Output 'EDITOR_INTERLEAVING_PASS'
'''
        for case in ("set-present", "set-absent", "set-unrelated", "restore-set", "restore-remove"):
            with self.subTest(case=case):
                result = subprocess.run(
                    [self.pwsh, "-NoProfile", "-NonInteractive", "-Command", script],
                    cwd=ROOT, env={**self.env, "OLYMPUS_EDITOR_CASE": case},
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=60, check=False,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("EDITOR_INTERLEAVING_PASS", result.stdout)

    def test_existing_jsonc_bytes_restore_and_verifyonly_is_read_only(self):
        original = self.write_config(encoding="utf-8-sig")
        self.install_ok()
        installed = (self.root / "opencode.jsonc").read_bytes()
        self.assertNotEqual(original, installed)
        self.assertTrue(installed.startswith(b"\xef\xbb\xbf"))
        self.assertIn("User comment with Unicode: snowman ☃".encode(), installed)
        self.assertIn(b'"default_agent":"kael"', installed)
        self.assertEqual("kael", self.config_object()["default_agent"])
        self.assertEqual('quoted "value" and ☃', self.config_object()["user_note"])
        self.assertEqual("ask", self.config_object()["permissions"][0]["effect"])
        receipt = self.receipt()
        self.assertEqual("committed", receipt["state"])
        self.assertEqual("opencode.jsonc", receipt["config_path"])
        self.assertFalse(receipt["previous_present"])
        self.assertIsNone(receipt["previous_value_json"])
        self.assertEqual("remove", receipt["restore_action"])
        self.assertNotIn("opencode.jsonc", {item["path"] for item in json.loads(self.manifest.read_text())["managed_files"]})

        before_root, before_cli = snapshot(self.root), snapshot(self.cli_root)
        verified = self.run_installer("-VerifyOnly")
        self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)
        self.assertEqual(before_root, snapshot(self.root))
        self.assertEqual(before_cli, snapshot(self.cli_root))

        repeated = self.run_installer()
        self.assertEqual(0, repeated.returncode, repeated.stdout + repeated.stderr)
        self.assertEqual(installed, (self.root / "opencode.jsonc").read_bytes())
        removed = self.run_installer("-Uninstall")
        self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
        self.assertEqual(original, (self.root / "opencode.jsonc").read_bytes())
        self.assertFalse(self.manifest.exists())
        self.assertEqual([], list((self.root / "agents").glob("*.md")))

    def test_previous_value_and_user_changed_value_are_preserved(self):
        text = BASE_CONFIG.replace(
            "{\n", '{\n  "default_agent": "other",\n', 1,
        )
        original = self.write_config(text)
        self.install_ok()
        receipt = self.receipt()
        self.assertEqual('"other"', receipt["previous_value_json"])
        self.assertEqual("set", receipt["restore_action"])
        removed = self.run_installer("-Uninstall")
        self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
        self.assertEqual(original, (self.root / "opencode.jsonc").read_bytes())
        self.install_ok()
        installed = (self.root / "opencode.jsonc").read_bytes()
        self.assertIn("User comment with Unicode: snowman ☃".encode(), installed)

        changed = re.sub(
            rb'("default_agent"\s*:\s*)"kael"',
            rb'\1"user-selected"',
            installed,
            count=1,
        )
        (self.root / "opencode.jsonc").write_bytes(changed)
        removed = self.run_installer("-Uninstall")
        self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
        config = self.config_object()
        self.assertEqual("user-selected", config["default_agent"])
        self.assertTrue((self.root / "opencode.jsonc").is_file())
        self.assertFalse(self.manifest.exists())
        self.assertNotEqual(original, changed)

    def test_fresh_config_is_managed_and_uninstalled_and_deleted_user_config_is_not_recreated(self):
        self.install_ok()
        config = self.root / "opencode.jsonc"
        self.assertEqual("kael", self.config_object()["default_agent"])
        entries = {item["path"] for item in json.loads(self.manifest.read_text())["managed_files"]}
        self.assertIn("opencode.jsonc", entries)
        self.assertFalse(self.receipt()["previous_present"])
        removed = self.run_installer("-Uninstall")
        self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
        self.assertFalse(config.exists())

        self.write_config()
        self.install_ok()
        config.unlink()
        updated = self.run_installer("-Update")
        self.assertEqual(0, updated.returncode, updated.stdout + updated.stderr)
        self.assertFalse(config.exists())

    def test_unowned_and_receiptless_kael_are_refused_without_adoption(self):
        original = self.write_config(BASE_CONFIG.replace("{\n", '{\n  "default_agent": "kael",\n', 1))
        before = snapshot(self.root)
        refused = self.run_installer()
        self.assertNotEqual(0, refused.returncode)
        self.assertIn("GLOBAL_DEFAULT_AGENT_OWNERSHIP_UNKNOWN", refused.stdout + refused.stderr)
        self.assertEqual(before, snapshot(self.root))
        self.assertFalse(self.manifest.exists())
        self.assertFalse(self.cli_root.exists())
        (self.root / "opencode.jsonc").write_bytes(original)

        self.write_config()
        self.install_ok()
        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record.pop("default_agent_receipt")
        self.manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        before_root, before_cli = snapshot(self.root), snapshot(self.cli_root)
        refused = self.run_installer("-Update")
        self.assertNotEqual(0, refused.returncode, refused.stdout + refused.stderr)
        self.assertIn("GLOBAL_DEFAULT_AGENT_RECEIPT_MISSING", refused.stdout + refused.stderr)
        self.assertEqual(before_root, snapshot(self.root))
        self.assertEqual(before_cli, snapshot(self.cli_root))

    def test_pending_set_recovery_conflict_and_pending_uninstall_resume(self):
        original = self.write_config(
            BASE_CONFIG.replace("{\n", '{\n  "default_agent": "other",\n', 1),
        )
        self.install_ok()

        committed = json.loads(self.manifest.read_text(encoding="utf-8"))
        for state in ("pending_set", "pending_uninstall"):
            with self.subTest(verify_pending=state):
                record = json.loads(json.dumps(committed))
                record["default_agent_receipt"]["state"] = state
                self.manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
                before_root, before_cli = snapshot(self.root), snapshot(self.cli_root)
                verified = self.run_installer("-VerifyOnly")
                self.assertNotEqual(0, verified.returncode)
                self.assertEqual(before_root, snapshot(self.root))
                self.assertEqual(before_cli, snapshot(self.cli_root))
        self.manifest.write_text(json.dumps(committed, indent=2) + "\n", encoding="utf-8")

        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record["default_agent_receipt"]["state"] = "pending_set"
        self.manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        (self.root / "opencode.jsonc").write_bytes(original)
        resumed_before_set = self.run_installer()
        self.assertEqual(0, resumed_before_set.returncode, resumed_before_set.stdout + resumed_before_set.stderr)
        self.assertEqual("kael", self.config_object()["default_agent"])
        self.assertEqual("committed", self.receipt()["state"])

        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record["default_agent_receipt"]["state"] = "pending_set"
        self.manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        resumed_after_set = self.run_installer()
        self.assertEqual(0, resumed_after_set.returncode, resumed_after_set.stdout + resumed_after_set.stderr)
        self.assertEqual("committed", self.receipt()["state"])

        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record["default_agent_receipt"]["state"] = "pending_set"
        self.manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        third = re.sub(rb'("default_agent"\s*:\s*)"kael"', rb'\1"third-value"', (self.root / "opencode.jsonc").read_bytes(), count=1)
        (self.root / "opencode.jsonc").write_bytes(third)
        before = snapshot(self.root)
        conflicted = self.run_installer()
        self.assertNotEqual(0, conflicted.returncode)
        self.assertIn("GLOBAL_DEFAULT_AGENT_RECOVERY_CONFLICT", conflicted.stdout + conflicted.stderr)
        self.assertEqual(before, snapshot(self.root))

        # Re-establish a valid committed receipt, then resume uninstall on each
        # side of the field restoration. The second pass also tolerates one
        # already-removed managed agent under pending_uninstall.
        (self.root / "opencode.jsonc").write_bytes(original)
        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record["default_agent_receipt"]["state"] = "pending_set"
        self.manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        self.install_ok()
        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record["default_agent_receipt"]["state"] = "pending_uninstall"
        self.manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        interrupted = self.run_installer("-Uninstall")
        self.assertEqual(0, interrupted.returncode, interrupted.stdout + interrupted.stderr)
        self.assertEqual(original, (self.root / "opencode.jsonc").read_bytes())
        self.assertFalse(self.manifest.exists())

        self.install_ok()
        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record["default_agent_receipt"]["state"] = "pending_uninstall"
        self.manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        (self.root / "opencode.jsonc").write_bytes(original)
        (self.root / "agents" / "atlas.md").unlink()
        resumed_uninstall = self.run_installer("-Uninstall")
        self.assertEqual(0, resumed_uninstall.returncode, resumed_uninstall.stdout + resumed_uninstall.stderr)
        self.assertEqual(original, (self.root / "opencode.jsonc").read_bytes())
        self.assertFalse(self.manifest.exists())

    def test_malformed_duplicate_both_configs_and_pending_journal_fail_closed(self):
        cases = (
            ("malformed", '{"permissions":[', None),
            ("duplicate-root", '{"default_agent":"one","default_agent":"two","permissions":[{"action":"external_directory","resource":"*","effect":"ask"}]}', None),
            ("both-formats", BASE_CONFIG, BASE_CONFIG),
        )
        for name, jsonc_text, json_text in cases:
            with self.subTest(name=name):
                for child in self.root.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                self.root.mkdir(exist_ok=True)
                (self.root / ".olympus-cli-edit.lock").write_bytes(b"")
                (self.root / "opencode.jsonc").write_text(jsonc_text, encoding="utf-8")
                if json_text is not None:
                    (self.root / "opencode.json").write_text(json_text, encoding="utf-8")
                before = snapshot(self.root)
                result = self.run_installer()
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(before, snapshot(self.root))
                self.assertFalse(self.manifest.exists())
        for child in self.root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        (self.root / ".olympus-cli-edit.lock").write_bytes(b"")
        self.write_config()
        (self.root / ".olympus-cli-config-apply").mkdir()
        before = snapshot(self.root)
        blocked = self.run_installer()
        self.assertNotEqual(0, blocked.returncode)
        self.assertIn("GLOBAL_APPLY_RECOVERY_PENDING", blocked.stdout + blocked.stderr)
        self.assertEqual(before, snapshot(self.root))

    def test_utf16_json_preserves_nested_default_comments_and_actual_prior_value(self):
        text = (
            '{\r\n  "nested": {"default_agent": "nested-choice"},\r\n'
            '  "default\\u005fagent": "\\u006fther", /* keep this comment */\r\n'
            '  "permissions": [{"action":"external_directory","resource":"*","effect":"ask"}]\r\n}\r\n'
        )
        config = self.root / "opencode.json"
        original = text.encode("utf-16")
        config.write_bytes(original)
        self.install_ok()
        raw = config.read_bytes()
        self.assertEqual(original, raw.replace('"kael"'.encode("utf-16-le"),
                                              '"\\u006fther"'.encode("utf-16-le"), 1))
        self.assertEqual('"\\u006fther"', self.receipt()["previous_value_json"])
        self.assertEqual("kael", _default_agent_status(
            self.root, json.loads(self.manifest.read_text(encoding="utf-8"))))
        removed = self.run_installer("-Uninstall")
        self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
        self.assertEqual(original, config.read_bytes())

    def test_archive_root_version_and_release_marker_are_checked_before_dispatch(self):
        cases = (
            ("OpenCode-OlympusAgents-master", RELEASE, RELEASE, "SOURCE_VERSION_MISMATCH"),
            (f"OpenCode-OlympusAgents-{RELEASE}", "v0.6.0", "v0.6.0", "SOURCE_VERSION_MISMATCH"),
            (f"OpenCode-OlympusAgents-{RELEASE}", RELEASE, "v0.6.0", "SOURCE_VERSION_MISMATCH"),
        )
        before = snapshot(self.root)
        for index, (root, version, marker, reason) in enumerate(cases):
            with self.subTest(root=root, version=version, marker=marker):
                archive = self.sandbox / f"invalid-{index}.zip"
                with zipfile.ZipFile(archive, "w") as zipped:
                    zipped.writestr(f"{root}/install.ps1",
                                    f"[string]$Version = '{version}'\n$ReleaseVersion = '{marker}'\n")
                    zipped.writestr(f"{root}/scripts/global-install.ps1", "throw 'MUST_NOT_DISPATCH'")
                result = self.run_installer(source_archive=archive)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(reason, result.stdout + result.stderr)
                self.assertNotIn("MUST_NOT_DISPATCH", result.stdout + result.stderr)
                self.assertEqual(before, snapshot(self.root))
                self.assertFalse(self.cli_root.exists())

    def test_owned_config_pending_uninstall_resumes_and_receiptless_uninstall_is_refused(self):
        self.install_ok()
        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record["default_agent_receipt"]["state"] = "pending_uninstall"
        self.manifest.write_text(json.dumps(record), encoding="utf-8")
        (self.root / "agents" / "atlas.md").unlink()
        removed = self.run_installer("-Uninstall")
        self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
        self.assertFalse((self.root / "opencode.jsonc").exists())

        self.write_config()
        self.install_ok()
        record = json.loads(self.manifest.read_text(encoding="utf-8"))
        record.pop("default_agent_receipt")
        self.manifest.write_text(json.dumps(record), encoding="utf-8")
        before_root, before_cli = snapshot(self.root), snapshot(self.cli_root)
        removed = self.run_installer("-Uninstall")
        self.assertNotEqual(0, removed.returncode, removed.stdout + removed.stderr)
        self.assertIn("GLOBAL_DEFAULT_AGENT_RECEIPT_MISSING", removed.stdout + removed.stderr)
        self.assertEqual(before_root, snapshot(self.root))
        self.assertEqual(before_cli, snapshot(self.cli_root))


if __name__ == "__main__":
    unittest.main()
