"""Focused issue #128 checks: offline models, user overrides, and safe updates."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
# Read the candidate's declared identity instead of pinning an older release;
# reject inconsistent markers before exercising the installer and CLI.
_installer_text = (ROOT / "install.ps1").read_text(encoding="utf-8")
_default_version = re.search(r"(?m)^\s*\[string\]\$Version\s*=\s*'(v\d+\.\d+\.\d+)'", _installer_text)
_release_marker = re.search(r"(?m)^\s*\$ReleaseVersion\s*=\s*'(v\d+\.\d+\.\d+)'", _installer_text)
if not _default_version or not _release_marker or _default_version.group(1) != _release_marker.group(1):
    raise RuntimeError("Installer release identity is unavailable or inconsistent.")
RELEASE_VERSION = _default_version.group(1)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olympus import global_readonly, models_catalog, user_config
from olympus.cli import main


class GlobalCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pwsh = shutil.which("pwsh")
        if os.name != "nt" or cls.pwsh is None:
            raise unittest.SkipTest("The global CLI installer is qualified on Windows with PowerShell 7.")
        preferred = os.environ.get("OLYMPUS_TEST_ROOT")
        if preferred:
            cls.test_root = Path(preferred)
        else:
            cls.test_root = Path(os.environ.get("TEMP", Path.home())) / "opencode"
        cls.test_root.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.sandbox = self.test_root / ("global-cli-" + uuid.uuid4().hex)
        self.sandbox.mkdir()
        self.root = self.sandbox / "opencode"
        self.appdata = self.sandbox / "appdata"
        self.localappdata = self.sandbox / "localappdata"
        self.profile = self.sandbox / "profile"
        for directory in (self.root, self.appdata, self.localappdata, self.profile):
            directory.mkdir()
        self.env = os.environ.copy()
        self.env.update({
            "OPENCODE_CONFIG_DIR": str(self.root), "APPDATA": str(self.appdata),
            "LOCALAPPDATA": str(self.localappdata), "USERPROFILE": str(self.profile),
            "PYTHONDONTWRITEBYTECODE": "1", "OLYMPUS_TEST_ROOT": str(self.test_root),
        })
        self.script = ROOT / "scripts/global-install.ps1"
        initial = self._engine(update=False)
        self.assertEqual(0, initial.returncode, initial.stdout + initial.stderr)
        self.manifest_path = self.root / "olympus/orchestrator-install.json"

    def tearDown(self):
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def _engine(self, *, update: bool, answer: str | None = None, noninteractive: bool = False):
        base = [self.pwsh, "-NoProfile"]
        arguments = ["-Harness", "opencode", "-SourceVersion", RELEASE_VERSION]
        if update:
            arguments.append("-Update")
        if answer is None:
            command = base + (["-NonInteractive"] if noninteractive else []) + ["-File", str(self.script), *arguments]
        else:
            escaped = str(self.script).replace("'", "''")
            body = (
                "function global:Read-Host { param([string]$Prompt); Write-Host 'OLYMPUS_TEST_PROMPT'; Write-Host $Prompt; return $env:OLYMPUS_TEST_ANSWER }; "
                f"& '{escaped}' " + " ".join(arguments)
            )
            command = base + ["-Command", body]
        env = self.env.copy()
        if answer is not None:
            env["OLYMPUS_TEST_ANSWER"] = answer
        return subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60, check=False)

    def _agent(self, role: str) -> Path:
        return self.root / "agents" / f"{role}.md"

    def _manifest(self):
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _cli_installer(self, action: str, install_root: Path, path_store: Path):
        source = install_root / "versions" / RELEASE_VERSION if action == "uninstall" else ROOT
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "scripts/install-cli.ps1"),
             "-Action", action, "-Version", RELEASE_VERSION, "-SourceRoot", str(source),
             "-InstallRoot", str(install_root), "-PathStorePath", str(path_store)],
            cwd=ROOT, env=self.env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60, check=False,
        )

    def _create_project(self, *, version: str = RELEASE_VERSION) -> Path:
        project = self.sandbox / ("project-" + uuid.uuid4().hex)
        project.mkdir()
        subprocess.run(["git", "init", "--quiet", str(project)], check=True,
                       capture_output=True, text=True, encoding="utf-8", timeout=15)
        renderer = __import__("olympus.cli", fromlist=["load_renderer"]).load_renderer(ROOT)
        entries = []
        for path, content in renderer.outputs_for(ROOT, "opencode").items():
            relative = path.relative_to(ROOT).as_posix()
            if not (relative.startswith(".opencode/") or relative == "opencode.jsonc"):
                continue
            raw = content.encode("utf-8")
            destination = project / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            entries.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest()})
        manifest = {
            "schema_version": 1, "scope": "project", "installed_version": version,
            "installed_from_commit": "unknown", "installed_harnesses": ["opencode"],
            "managed_files": sorted(entries, key=lambda item: item["path"]),
        }
        (project / ".opencode/orchestrator-install.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8",
        )
        return project

    def _project_update(self, project: Path, *, answer: str | None = None, noninteractive: bool = False):
        script = ROOT / "scripts/bootstrap.ps1"
        arguments = ["-Target", str(project), "-Harness", "opencode", "-SourceVersion", RELEASE_VERSION, "-Update"]
        if answer is None:
            command = [self.pwsh, "-NoProfile"] + (["-NonInteractive"] if noninteractive else []) + ["-File", str(script), *arguments]
        else:
            escaped = str(script).replace("'", "''")
            body = (
                "function global:Read-Host { param([string]$Prompt); Write-Host 'OLYMPUS_TEST_PROMPT'; "
                "Write-Host $Prompt; return $env:OLYMPUS_TEST_ANSWER }; "
                f"& '{escaped}' " + " ".join(item if item.startswith("-") else
                    f"'{item.replace(chr(39), chr(39) * 2)}'" for item in arguments)
            )
            command = [self.pwsh, "-NoProfile", "-Command", body]
        env = self.env.copy()
        if answer is not None:
            env["OLYMPUS_TEST_ANSWER"] = answer
        mock_bin = self.sandbox / "mock-opencode"
        mock_bin.mkdir(exist_ok=True)
        generated = []
        for file in sorted((ROOT / ".opencode/agents").glob("*.md")):
            text = file.read_text(encoding="utf-8")
            model = __import__("re").search(r'(?m)^model:\s*"?([^"\s#]+)#([^"\s]+)"?\s*$', text)
            mode = __import__("re").search(r"(?m)^mode:\s*(primary|subagent)\s*$", text)
            self.assertIsNotNone(model)
            self.assertIsNotNone(mode)
            provider, model_id = model.group(1).split("/", 1)
            generated.append({"id": file.stem, "model": {"providerID": provider, "id": model_id,
                                                           "variant": model.group(2)},
                              "mode": mode.group(1)})
        agents_json = self.sandbox / "mock-agents.json"
        agents_json.write_text(json.dumps(generated), encoding="utf-8")
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
        env["PATH"] = str(mock_bin) + os.pathsep + env.get("PATH", "")
        env["OLYMPUS_TEST_AGENTS"] = str(agents_json)
        return subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=90, check=False)

    def _change_two_agents(self):
        originals = {}
        for role in ("kael", "thales"):
            path = self._agent(role)
            originals[role] = path.read_bytes()
            path.write_bytes(originals[role] + b"\n# locally changed\n")
        return originals

    def test_catalog_accepts_declared_model_effort_and_rejects_unknown(self):
        luna = models_catalog.validate_assignment("openai/gpt-6-luna", "max", ROOT)
        self.assertTrue(luna["tool_call"])
        self.assertEqual(["none", "low", "medium", "high", "xhigh", "max"], luna["efforts"])
        warnings = io.StringIO()
        with contextlib.redirect_stderr(warnings):
            unknown = models_catalog.validate_assignment("custom/new-model", "high", ROOT)
        self.assertEqual("unverified", unknown["catalog_status"])
        self.assertIn("compatibility are unverified", warnings.getvalue())
        with self.assertRaisesRegex(models_catalog.CatalogError, "does not declare"):
            models_catalog.validate_assignment("openai/gpt-6.1-sol", "none", ROOT)

    def test_custom_model_override_warns_and_persists_without_provider_probe(self):
        # Unknown-but-well-formed models are the user's choice, not an access check.
        env_patch = {"APPDATA": str(self.appdata), "LOCALAPPDATA": str(self.localappdata),
                     "USERPROFILE": str(self.profile), "OPENCODE_CONFIG_DIR": str(self.root)}
        warnings = io.StringIO()
        with mock.patch.dict(os.environ, env_patch), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(warnings):
            code = main(["--source", str(ROOT), "nox", "set-model", "custom/new-model", "--scope", "global"])
        self.assertEqual(0, code)
        self.assertIn("compatibility are unverified", warnings.getvalue())
        self.assertIn('model: "custom/new-model#', self._agent("nox").read_text(encoding="utf-8"))
        updated = self._engine(update=True)
        self.assertEqual(0, updated.returncode, updated.stdout + updated.stderr)
        self.assertIn("compatibility are unverified", updated.stdout + updated.stderr)

    def test_cli_package_owns_generated_inventory_and_only_removes_its_path_entry(self):
        for name, initial_path, expected_after_uninstall, should_own in (
                ("preexisting", "{bin}", "{bin}", False),
                ("added", "C:\\user-tools", "C:\\user-tools", True)):
            with self.subTest(name=name):
                install_root = self.sandbox / ("cli-" + name)
                install_root.mkdir()
                bin_path = install_root / "bin"
                bin_path.mkdir()
                path_store = install_root / "path-store.txt"
                initial = initial_path.format(bin=str(bin_path))
                path_store.write_text(initial, encoding="utf-8")

                installed = self._cli_installer("install", install_root, path_store)
                self.assertEqual(0, installed.returncode, installed.stdout + installed.stderr)
                current = install_root / "versions" / RELEASE_VERSION
                manifest = json.loads((current / "olympus-cli-manifest.json").read_text(encoding="utf-8"))
                package_paths = {entry["path"] for entry in manifest["files"]}
                self.assertTrue({".opencode/agents/kael.md", ".opencode/plugins/olympus-activity/activity.ts",
                                 ".opencode/scripts/worktree-setup.ps1", ".codex/agents/veyra.toml",
                                 ".codex/config.toml", "CODEX.md", "opencode.jsonc"}.issubset(package_paths))
                self.assertFalse(any(path.startswith(".opencode/commands/") for path in package_paths))
                ownership = install_root / "path-entry.txt"
                self.assertEqual(should_own, ownership.exists())
                if should_own:
                    self.assertEqual(bin_path.resolve(), Path(ownership.read_text(encoding="utf-8")).resolve())

                removed = self._cli_installer("uninstall", install_root, path_store)
                self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
                self.assertEqual(expected_after_uninstall.format(bin=str(bin_path)),
                                 path_store.read_text(encoding="utf-8"))
                self.assertFalse(ownership.exists())
                self.assertEqual(not should_own, bin_path.exists())

    def test_windows_launcher_self_uninstall_retains_python_status(self):
        launcher = self.sandbox / "launcher"
        launcher.mkdir()
        (launcher / "olympus_cli.py").write_text(
            'import pathlib, sys\npathlib.Path(__file__).with_name("olympus.cmd").unlink()\n'
            'sys.exit(int(sys.argv[1]))\n', encoding="utf-8",
        )
        env = {**self.env, "OLYMPUS_PYTHON": sys.executable}
        for code in (0, 1, 2):
            wrapper = launcher / "olympus.cmd"
            shutil.copyfile(ROOT / "scripts/olympus.cmd", wrapper)
            result = subprocess.run([str(wrapper), str(code)], env=env, capture_output=True,
                                    text=True, timeout=15, check=False)
            self.assertEqual(code, result.returncode, result.stderr)
            self.assertFalse(wrapper.exists())
            self.assertEqual("", result.stderr)

    def test_project_override_persists_with_field_precedence_and_rejects_drift_before_config_write(self):
        project = self._create_project()
        env_patch = {"APPDATA": str(self.appdata), "LOCALAPPDATA": str(self.localappdata),
                     "USERPROFILE": str(self.profile), "OPENCODE_CONFIG_DIR": str(self.root)}
        with mock.patch.dict(os.environ, env_patch):
            self.assertEqual(0, main(["--source", str(ROOT), "nox", "set-model", "openai/gpt-6.1-sol", "--scope", "global"]))
            self.assertEqual(0, main(["--source", str(ROOT), "nox", "set-effort", "high", "--scope", "global"]))
            self.assertEqual(0, main(["--source", str(ROOT), "nox", "set-model", "openai/gpt-6-luna",
                                      "--scope", "project", "--target", str(project)]))
            rows = user_config.effective_roles(ROOT, "project", project)
            nox = next(row for row in rows if row["role"] == "nox")
            self.assertEqual("openai/gpt-6-luna", nox["model"])
            self.assertEqual("high", nox["effort"])
            self.assertEqual(str((project / ".opencode/olympus-config.json").resolve()), nox["model_source"])
            self.assertEqual(str((self.appdata / "Olympus/config.json").resolve()), nox["effort_source"])
            self.assertEqual(0, main(["--source", str(ROOT), "nox", "set-effort", "max",
                                      "--scope", "project", "--target", str(project)]))
            listed = user_config.config_listing(ROOT, "project", project)
            final_nox = next(row for row in listed["roles"] if row["role"] == "nox")
            self.assertEqual(("openai/gpt-6-luna", "max"), (final_nox["model"], final_nox["effort"]))
            self.assertEqual("project", listed["scope"])
            self.assertEqual(str((project / ".opencode/olympus-config.json").resolve()), listed["sources"][0]["path"])
            self.assertEqual("Run 'olympus doctor' after manual edits.", listed["manual_edit_reminder"])
        project_config = json.loads((project / ".opencode/olympus-config.json").read_text(encoding="utf-8"))
        self.assertEqual({"model": "openai/gpt-6-luna", "effort": "max"}, project_config["overrides"]["nox"])
        agent = project / ".opencode/agents/nox.md"
        self.assertIn('model: "openai/gpt-6-luna#max"', agent.read_text(encoding="utf-8"))
        manifest_path = project / ".opencode/orchestrator-install.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(item for item in manifest["managed_files"] if item["path"] == ".opencode/agents/nox.md")
        self.assertEqual(hashlib.sha256(agent.read_bytes()).hexdigest(), entry["sha256"])

        drifted = self._create_project()
        drifted_agent = drifted / ".opencode/agents/nox.md"
        original_manifest = (drifted / ".opencode/orchestrator-install.json").read_bytes()
        drifted_agent.write_bytes(drifted_agent.read_bytes() + b"\n# user change\n")
        before = drifted_agent.read_bytes()
        with mock.patch.dict(os.environ, env_patch), contextlib.redirect_stdout(io.StringIO()):
            code = main(["--source", str(ROOT), "nox", "set-model", "openai/gpt-6-luna",
                         "--scope", "project", "--target", str(drifted)])
        self.assertNotEqual(0, code)
        self.assertFalse((drifted / ".opencode/olympus-config.json").exists())
        self.assertEqual(before, drifted_agent.read_bytes())
        self.assertEqual(original_manifest, (drifted / ".opencode/orchestrator-install.json").read_bytes())

        # The fixture renderer normalizes source newlines; VerifyOnly compares
        # the installed bytes with the PowerShell installer's raw source text.
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest["managed_files"]:
            content = (ROOT / item["path"]).read_bytes()
            if item["path"] == ".opencode/agents/nox.md":
                content = user_config._replace_agent_model(content, "openai/gpt-6-luna", "max", "nox")
            (project / item["path"]).write_bytes(content)
            item["sha256"] = hashlib.sha256(content).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        original_cwd = Path.cwd()
        try:
            os.chdir(project)
            output = io.StringIO()
            with mock.patch.dict(os.environ, env_patch), contextlib.redirect_stdout(output):
                code = main(["--source", str(ROOT), "doctor", "--json"])
            self.assertEqual(0, code, output.getvalue())
            diagnosis = json.loads(output.getvalue())
            self.assertEqual("project", diagnosis["context"]["scope"])
            self.assertEqual("valid", diagnosis["data"]["user_configuration"]["state"])
            self.assertFalse(diagnosis["data"]["user_configuration"]["provider_access_checked"])

            project_config_path = project / ".opencode/olympus-config.json"
            project_config_path.write_text("{invalid", encoding="utf-8")
            output = io.StringIO()
            with mock.patch.dict(os.environ, env_patch), contextlib.redirect_stdout(output):
                code = main(["--source", str(ROOT), "doctor", "--json"])
            self.assertNotEqual(0, code, output.getvalue())
            self.assertEqual("invalid_user_configuration", json.loads(output.getvalue())["issues"][0]["code"])
        finally:
            os.chdir(original_cwd)

    def test_project_update_changed_agents_confirmation_outcomes(self):
        unchanged = self._create_project()
        result = self._project_update(unchanged)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("OLYMPUS_TEST_PROMPT", result.stdout)

        for answer, accepted in (("y", True), ("n", False), ("", False)):
            with self.subTest(answer=answer):
                project = self._create_project(version="unknown")
                originals = {}
                for role in ("kael", "thales"):
                    path = project / f".opencode/agents/{role}.md"
                    originals[role] = path.read_bytes()
                    path.write_bytes(originals[role] + b"\n# locally changed\n")
                before_manifest = (project / ".opencode/orchestrator-install.json").read_bytes()
                result = self._project_update(project, answer=answer)
                output = result.stdout + result.stderr
                self.assertEqual(0 if accepted else 1, result.returncode, output)
                self.assertIn("Hay 2 agentes de Olympus modificados en este proyecto", output)
                self.assertIn("- Kael", output)
                self.assertIn("- Thales", output)
                self.assertEqual(1, output.count("OLYMPUS_TEST_PROMPT"))
                if accepted:
                    for role, content in originals.items():
                        self.assertEqual(content.decode("utf-8").replace("\r\n", "\n"),
                                         (project / f".opencode/agents/{role}.md").read_text(encoding="utf-8"))
                    self.assertIn(f'"installed_version": "{RELEASE_VERSION}"',
                                  (project / ".opencode/orchestrator-install.json").read_text(encoding="utf-8"))
                else:
                    self.assertEqual(before_manifest, (project / ".opencode/orchestrator-install.json").read_bytes())
                    for role, content in originals.items():
                        self.assertEqual(content + b"\n# locally changed\n",
                                         (project / f".opencode/agents/{role}.md").read_bytes())

        noninteractive = self._create_project(version="unknown")
        originals = {}
        for role in ("kael", "thales"):
            path = noninteractive / f".opencode/agents/{role}.md"
            originals[role] = path.read_bytes()
            path.write_bytes(originals[role] + b"\n# locally changed\n")
        before_manifest = (noninteractive / ".opencode/orchestrator-install.json").read_bytes()
        result = self._project_update(noninteractive, noninteractive=True)
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("MODIFIED_AGENT_CONFIRMATION_REQUIRED", output)
        self.assertNotIn("OLYMPUS_TEST_PROMPT", output)
        self.assertEqual(before_manifest, (noninteractive / ".opencode/orchestrator-install.json").read_bytes())
        for role, content in originals.items():
            self.assertEqual(content + b"\n# locally changed\n",
                             (noninteractive / f".opencode/agents/{role}.md").read_bytes())

    def test_global_override_persists_and_updates_only_managed_agent(self):
        models_before = (ROOT / "olympus/core/models.toml").read_bytes()
        env_patch = {"APPDATA": str(self.appdata), "LOCALAPPDATA": str(self.localappdata),
                     "USERPROFILE": str(self.profile), "OPENCODE_CONFIG_DIR": str(self.root)}
        output = io.StringIO()
        with mock.patch.dict(os.environ, env_patch), contextlib.redirect_stdout(output):
            code = main(["--source", str(ROOT), "nox", "set-model", "openai/gpt-6.1-sol"])
            self.assertEqual(0, code, output.getvalue())
            code = main(["--source", str(ROOT), "nox", "set-effort", "high"])
            self.assertEqual(0, code, output.getvalue())
            code = main(["--source", str(ROOT), "agents", "list"])
            self.assertEqual(0, code, output.getvalue())
            code = main(["--source", str(ROOT), "config", "list"])
            self.assertEqual(0, code, output.getvalue())
        settings = self.appdata / "Olympus/config.json"
        self.assertEqual({"schema_version": 1, "overrides": {"nox": {"model": "openai/gpt-6.1-sol", "effort": "high"}}},
                         json.loads(settings.read_text(encoding="utf-8")))
        self.assertIn('model: "openai/gpt-6.1-sol#high"', self._agent("nox").read_text(encoding="utf-8"))
        manifest = self._manifest()
        entry = next(item for item in manifest["managed_files"] if item["path"] == "agents/nox.md")
        self.assertEqual(hashlib.sha256(self._agent("nox").read_bytes()).hexdigest(), entry["sha256"])
        self.assertEqual(models_before, (ROOT / "olympus/core/models.toml").read_bytes())
        self.assertIn("model=openai/gpt-6.1-sol", output.getvalue())
        self.assertIn(str(settings.resolve()), output.getvalue())
        self.assertTrue(output.getvalue().rstrip().endswith("Run 'olympus doctor' after manual edits."))

        with mock.patch.dict(os.environ, env_patch):
            expected = global_readonly._expected(
                ROOT, __import__("olympus.cli", fromlist=["load_renderer"]).load_renderer(ROOT), ("opencode",),
            )
            user_config.apply_to_expected(ROOT, expected["opencode"])
        self.assertIn(b'model: "openai/gpt-6.1-sol#high"', expected["opencode"]["agents/nox.md"])

    def test_doctor_reports_invalid_user_json_without_provider_checks(self):
        settings = self.appdata / "Olympus/config.json"
        settings.parent.mkdir()
        settings.write_text('{invalid', encoding="utf-8")
        with mock.patch.dict(os.environ, {"APPDATA": str(self.appdata)}):
            with self.assertRaisesRegex(user_config.UserConfigError, "not valid JSON"):
                user_config.diagnose(ROOT)

    def test_update_without_managed_changes_does_not_prompt(self):
        result = self._engine(update=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("¿Quieres sobrescribirlos", result.stdout)
        self.assertIn("OLYMPUS_GLOBAL_INSTALL:", result.stdout)

    def test_global_installer_refuses_a_pending_python_apply_journal(self):
        agent = self._agent("kael")
        before_agent, before_manifest = agent.read_bytes(), self.manifest_path.read_bytes()
        pending = self.root / ".olympus-cli-config-apply"
        pending.mkdir()
        (pending / "unconfirmed-fixture.txt").write_bytes(b"preserve pending evidence")
        result = self._engine(update=False)
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("GLOBAL_APPLY_RECOVERY_PENDING", output)
        self.assertEqual(before_agent, agent.read_bytes())
        self.assertEqual(before_manifest, self.manifest_path.read_bytes())
        self.assertEqual(b"preserve pending evidence", (pending / "unconfirmed-fixture.txt").read_bytes())

    def test_global_installer_fails_closed_when_journal_inspection_errors(self):
        agent = self._agent("kael")
        before_agent, before_manifest = agent.read_bytes(), self.manifest_path.read_bytes()
        env = self.env.copy()
        env["OLYMPUS_TEST_FAIL_INSPECTION"] = str(self.root / ".olympus-cli-config-apply")
        escaped = str(self.script).replace("'", "''")
        body = (
            "function global:Get-Item { param([string]$LiteralPath,[switch]$Force,"
            "[Alias('ErrorAction')][string]$Action = 'Continue'); "
            "if ($LiteralPath -eq $env:OLYMPUS_TEST_FAIL_INSPECTION) { "
            "throw [IO.IOException]::new('controlled inspection failure') }; "
            "Microsoft.PowerShell.Management\\Get-Item -LiteralPath $LiteralPath "
            "-Force:$Force -ErrorAction $Action }; "
            f"& '{escaped}' -Harness opencode -SourceVersion '{RELEASE_VERSION}'"
        )
        result = subprocess.run([self.pwsh, "-NoProfile", "-NonInteractive", "-Command", body],
                                cwd=ROOT, env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60, check=False)
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("GLOBAL_PATH_INSPECTION_FAILED", output)
        self.assertIn("controlled inspection failure", output)
        self.assertEqual(before_agent, agent.read_bytes())
        self.assertEqual(before_manifest, self.manifest_path.read_bytes())
        self.assertFalse((self.root / ".olympus-cli-config-apply").exists())

    def test_update_two_changed_agents_yes_overwrites_only_after_one_confirmation(self):
        originals = self._change_two_agents()
        result = self._engine(update=True, answer="y")
        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output)
        self.assertIn("Hay 2 agentes de Olympus modificados", output)
        self.assertIn("- Kael", output)
        self.assertIn("- Thales", output)
        self.assertEqual(1, output.count("OLYMPUS_TEST_PROMPT"))
        for role, content in originals.items():
            self.assertEqual(content, self._agent(role).read_bytes())

    def test_update_two_changed_agents_no_or_enter_preserves_them(self):
        for answer in ("n", ""):
            with self.subTest(answer=answer):
                originals = self._change_two_agents()
                changed = {role: self._agent(role).read_bytes() for role in originals}
                before_manifest = self.manifest_path.read_bytes()
                result = self._engine(update=True, answer=answer)
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("Update cancelled", result.stdout + result.stderr)
                self.assertEqual(before_manifest, self.manifest_path.read_bytes())
                for role in changed:
                    self.assertEqual(changed[role], self._agent(role).read_bytes())

    def test_update_two_changed_agents_noninteractive_stops_without_writing(self):
        self._change_two_agents()
        before_agents = {role: self._agent(role).read_bytes() for role in ("kael", "thales")}
        before_manifest = self.manifest_path.read_bytes()
        result = self._engine(update=True, noninteractive=True)
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, output)
        self.assertIn("interactive PowerShell 7", output)
        self.assertEqual(before_manifest, self.manifest_path.read_bytes())
        for role, content in before_agents.items():
            self.assertEqual(content, self._agent(role).read_bytes())


if __name__ == "__main__":
    unittest.main()
