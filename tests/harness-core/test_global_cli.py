"""Focused issue #128 checks: offline models, user overrides, and safe updates."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT
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

from olympus import (config_apply, config_apply_transaction, global_readonly, models_catalog, source_edit,
                     user_config)
from olympus.cli import load_renderer, main


def _iter_tests(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from _iter_tests(test)
        else:
            yield test


def load_tests(loader, standard_tests, pattern):
    shard = os.environ.get("OLYMPUS_GLOBAL_CLI_SHARD")
    if shard is None:
        return standard_tests
    if shard not in {"1", "2", "3"}:
        raise ValueError(f"OLYMPUS_GLOBAL_CLI_SHARD must be 1, 2, or 3; got {shard!r}")

    tests = sorted(_iter_tests(standard_tests), key=lambda test: test.id())
    selected = [test for index, test in enumerate(tests) if index % 3 == int(shard) - 1]
    if not selected:
        raise ValueError(f"OLYMPUS_GLOBAL_CLI_SHARD={shard} selected no tests")
    return loader.suiteClass(selected)


def _render_global_source(source: Path) -> None:
    expected = global_readonly._expected(
        source, load_renderer(source), ("opencode",), max_children=4,
    )["opencode"]
    generated_paths = {f".opencode/{relative}" for relative in expected}
    for path in (source / ".opencode").rglob("*"):
        if path.is_file() and path.relative_to(source).as_posix() not in generated_paths:
            path.unlink()
    for relative, content in expected.items():
        path = source / ".opencode" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))


def _render_project_source(source: Path) -> None:
    for path, content in load_renderer(source).outputs_for(source, "opencode").items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))


class GlobalCli(unittest.TestCase):
    _TIMING_PHASES = (
        "sandbox_setup", "clean_seed_install", "global_install", "update",
        "verify", "uninstall", "cli_installer",
    )

    @classmethod
    def setUpClass(cls):
        global ROOT

        cls._timing_enabled = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
        cls._phase_timings = {phase: [0, 0.0] for phase in cls._TIMING_PHASES}
        cls.pwsh = shutil.which("pwsh")
        if os.name != "nt" or cls.pwsh is None:
            raise unittest.SkipTest("The global CLI installer is qualified on Windows with PowerShell 7.")
        preferred = os.environ.get("OLYMPUS_TEST_ROOT")
        if preferred:
            cls.test_root = Path(preferred)
        else:
            cls.test_root = Path(os.environ.get("TEMP", Path.home())) / "opencode"
        cls.test_root.mkdir(parents=True, exist_ok=True)
        cls.source_root = cls.test_root / ("global-cli-source-" + uuid.uuid4().hex)
        cls.source_root.mkdir()
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for directory in ("olympus", "scripts", ".opencode"):
            shutil.copytree(SOURCE_ROOT / directory, cls.source_root / directory, ignore=ignore)
        for filename in ("install.ps1", "opencode.jsonc"):
            shutil.copy2(SOURCE_ROOT / filename, cls.source_root / filename)
        _render_global_source(cls.source_root)
        cls.project_source_root = cls.test_root / ("global-cli-project-source-" + uuid.uuid4().hex)
        cls.project_source_root.mkdir()
        for directory in ("olympus", "scripts", ".opencode"):
            shutil.copytree(SOURCE_ROOT / directory, cls.project_source_root / directory, ignore=ignore)
        for filename in ("install.ps1", "opencode.jsonc"):
            shutil.copy2(SOURCE_ROOT / filename, cls.project_source_root / filename)
        _render_project_source(cls.project_source_root)
        ROOT = cls.project_source_root

    @classmethod
    def tearDownClass(cls):
        if cls._timing_enabled:
            # These scoped intervals intentionally do not sum to unittest wall time.
            phases = []
            for phase in cls._TIMING_PHASES:
                count, seconds = cls._phase_timings[phase]
                elapsed = f"{seconds:.3f}" if count else "unverified"
                phases.append(f"{phase} count={count} total_seconds={elapsed}")
            print("OLYMPUS_TEST_PHASE_TIMING " + "; ".join(phases), file=sys.stderr, flush=True)
        shutil.rmtree(cls.source_root, ignore_errors=True)
        shutil.rmtree(cls.project_source_root, ignore_errors=True)

    @contextlib.contextmanager
    def _measure_phase(self, phase: str):
        started = time.perf_counter() if self._timing_enabled else None
        try:
            yield
        finally:
            if started is not None:
                count, seconds = self._phase_timings[phase]
                self._phase_timings[phase] = [count + 1, seconds + time.perf_counter() - started]

    def setUp(self):
        self.source_root = type(self).source_root
        self.project_source_root = type(self).project_source_root
        with self._measure_phase("sandbox_setup"):
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
                "HOME": str(self.profile), "XDG_CONFIG_HOME": str(self.sandbox / "xdg"),
                "OLYMPUS_CONFIG_FILE": str(self.appdata / "Olympus" / "config.json"),
                "OLYMPUS_CLI_ROOT": str(self.sandbox / "cli"),
                "OLYMPUS_CLI_PATH_STORE": str(self.sandbox / "cli" / "path-store.txt"),
            })
            environment = mock.patch.dict(os.environ, self.env)
            environment.start()
            self.addCleanup(environment.stop)
            self.script = self.source_root / "scripts/global-install.ps1"
        initial = self._engine(update=False, timing_phase="clean_seed_install")
        self.assertEqual(0, initial.returncode, initial.stdout + initial.stderr)
        self.manifest_path = self.root / "olympus/orchestrator-install.json"

    def tearDown(self):
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def _engine(self, *, update: bool, answer: str | None = None, noninteractive: bool = False,
                env: dict[str, str] | None = None, source_root: Path | None = None,
                timing_phase: str | None = None):
        source_root = self.source_root if source_root is None else source_root
        base = [self.pwsh, "-NoProfile"]
        arguments = ["-Harness", "opencode", "-SourceVersion", RELEASE_VERSION]
        if update:
            arguments.append("-Update")
        script = source_root / "scripts/global-install.ps1"
        if answer is None:
            command = base + (["-NonInteractive"] if noninteractive else []) + ["-File", str(script), *arguments]
        else:
            escaped = str(script).replace("'", "''")
            body = (
                "function global:Read-Host { param([string]$Prompt); Write-Host 'OLYMPUS_TEST_PROMPT'; Write-Host $Prompt; return $env:OLYMPUS_TEST_ANSWER }; "
                f"& '{escaped}' " + " ".join(arguments)
            )
            command = base + ["-Command", body]
        env = (self.env if env is None else env).copy()
        if answer is not None:
            env["OLYMPUS_TEST_ANSWER"] = answer
        phase = timing_phase or ("update" if update else "global_install")
        with self._measure_phase(phase):
            return subprocess.run(command, cwd=source_root, env=env, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=60, check=False)

    def _verify_global(self, env: dict[str, str] | None = None, *, source_root: Path | None = None):
        source_root = self.source_root if source_root is None else source_root
        with self._measure_phase("verify"):
            return subprocess.run(
                [self.pwsh, "-NoProfile", "-NonInteractive", "-File", str(source_root / "scripts/global-install.ps1"),
                 "-Harness", "opencode", "-SourceVersion", RELEASE_VERSION, "-VerifyOnly"],
                cwd=source_root, env=self.env if env is None else env, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=60, check=False,
            )

    def _uninstall_global(self, env: dict[str, str], *, source_root: Path | None = None):
        source_root = self.source_root if source_root is None else source_root
        with self._measure_phase("uninstall"):
            return subprocess.run(
                [self.pwsh, "-NoProfile", "-NonInteractive", "-File", str(source_root / "scripts/global-install.ps1"),
                 "-Harness", "opencode", "-SourceVersion", RELEASE_VERSION, "-Uninstall"],
                cwd=source_root, env=env, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60, check=False,
            )

    def _run_global_operation(self, arguments: list[str], env: dict[str, str]):
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-NonInteractive", "-File", str(self.script),
             "-Harness", "opencode", "-SourceVersion", RELEASE_VERSION, *arguments],
            cwd=self.source_root, env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60, check=False,
        )

    def _downgrade_global_to_v010(self, root: Path):
        manifest_path = root / "olympus/orchestrator-install.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        legacy_commands = {
            "commands/olympus.ultra.md", "commands/olympus.performance.md",
            "commands/olympus.performance-ultra.md",
        }
        manifest["managed_files"] = [
            item for item in manifest["managed_files"] if item["path"] not in legacy_commands
        ]
        for relative in legacy_commands:
            (root / relative).unlink()
        manifest["installed_version"] = "v0.10.0"
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        return manifest

    def _copy_global_source(self, destination: Path):
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for directory in ("olympus", "scripts", ".opencode"):
            shutil.copytree(ROOT / directory, destination / directory, ignore=ignore)
        for filename in ("install.ps1", "opencode.jsonc"):
            shutil.copy2(ROOT / filename, destination / filename)
        _render_global_source(destination)

    def _start_global_lock_owner(self, root: Path):
        helper = self.source_root / "scripts/target-writer-lock.ps1"
        quote = lambda value: str(value).replace("'", "''")
        body = (
            f". '{quote(helper)}'; $lock = Enter-OlympusTargetWriterLock '{quote(root)}'; "
            "[Console]::Out.WriteLine('LOCKED'); [Console]::Out.Flush(); "
            "[Console]::In.ReadLine() | Out-Null; Exit-OlympusTargetWriterLock $lock"
        )
        process = subprocess.Popen(
            [self.pwsh, "-NoProfile", "-NonInteractive", "-Command", body],
            cwd=self.source_root, env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        ready = queue.Queue()
        reader = threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            line = ready.get(timeout=15)
        except queue.Empty:
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
            self.fail(f"PowerShell global lock owner did not acquire: {stdout!r} {stderr!r}")
        if line.strip() != "LOCKED":
            stdout, stderr = process.communicate(timeout=10)
            self.fail(f"PowerShell global lock owner failed: {line!r} {stdout!r} {stderr!r}")
        return process

    def _stop_global_lock_owner(self, process):
        if process.poll() is None:
            process.stdin.write("release\n")
            process.stdin.flush()
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(0, process.returncode, f"PowerShell global lock owner failed: {stdout!r} {stderr!r}")

    def _global_files(self, root: Path | None = None):
        root = self.root if root is None else root
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file() and path.relative_to(root).as_posix() != source_edit._LOCK_NAME
        }

    def _agent(self, role: str) -> Path:
        return self.root / "agents" / f"{role}.md"

    def _manifest(self):
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _force_global_kael_crlf(self):
        agent = self._agent("kael")
        content = agent.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        agent.write_bytes(content)
        manifest = self._manifest()
        entry = next(item for item in manifest["managed_files"] if item["path"] == "agents/kael.md")
        entry["sha256"] = hashlib.sha256(content).hexdigest()
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )

        expected = global_readonly._expected

        def crlf_expected(*args, **kwargs):
            outputs = expected(*args, **kwargs)
            relative = "agents/kael.md"
            outputs["opencode"][relative] = (
                outputs["opencode"][relative].replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            )
            return outputs

        patcher = mock.patch.object(global_readonly, "_expected", side_effect=crlf_expected)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _cli_installer(self, action: str, install_root: Path, path_store: Path,
                       *, source_root: Path | None = None):
        source_root = self.project_source_root if source_root is None else source_root
        source = install_root / "versions" / RELEASE_VERSION if action == "uninstall" else source_root
        with self._measure_phase("cli_installer"):
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
            if (not (relative.startswith(".opencode/") or relative == "opencode.jsonc")
                    or relative.startswith(".opencode/commands/")):
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
        sol = models_catalog.validate_assignment("openai/gpt-6.2-sol", "high", ROOT)
        self.assertTrue(sol["tool_call"])
        self.assertTrue(sol["reasoning"])
        self.assertEqual(["low", "medium", "high", "xhigh", "max"], sol["efforts"])
        self.assertEqual(sol, models_catalog.validate_assignment("openai/gpt-6.2-sol", "xhigh", ROOT))
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
        expected_cli_commands = {
            ".opencode/commands/olympus.ultra.md",
            ".opencode/commands/olympus.performance.md",
            ".opencode/commands/olympus.performance-ultra.md",
        }
        expected_cli_agents = {
            f".opencode/agents/{role}.md"
            for role in ("atlas", "helios", "kael", "kovan", "nox", "talos", "thales", "vera", "veyra")
        }
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
                                 ".opencode/scripts/worktree-setup.ps1", "opencode.jsonc"}.issubset(package_paths))
                self.assertEqual(expected_cli_commands, {
                    path for path in package_paths if path.startswith(".opencode/commands/")
                })
                self.assertEqual(expected_cli_agents, {
                    path for path in package_paths if path.startswith(".opencode/agents/")
                })
                self.assertFalse(any(path.startswith(".codex/") or path == "CODEX.md"
                                     for path in package_paths))
                ownership = install_root / "path-entry.txt"
                self.assertEqual(should_own, ownership.exists())
                if should_own:
                    self.assertEqual(bin_path.resolve(), Path(ownership.read_text(encoding="utf-8")).resolve())

                user_command = current / ".opencode/commands/user-owned.md"
                user_command.parent.mkdir(parents=True, exist_ok=True)
                user_command.write_bytes(b"user-owned CLI data\n")
                modified_owned = current / "olympus/global_cli.py"
                modified_owned.write_bytes(modified_owned.read_bytes() + b"\n# local edit\n")
                removed = self._cli_installer("uninstall", install_root, path_store)
                self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
                self.assertEqual(expected_after_uninstall.format(bin=str(bin_path)),
                                 path_store.read_text(encoding="utf-8"))
                self.assertTrue(all(not (current / command).exists() for command in expected_cli_commands))
                self.assertEqual(b"user-owned CLI data\n", user_command.read_bytes())
                self.assertTrue(modified_owned.is_file())
                self.assertTrue(modified_owned.read_bytes().endswith(b"\n# local edit\n"))
                self.assertFalse(ownership.exists())
                self.assertEqual(not should_own, bin_path.exists())

        source = self.sandbox / "cli-source-with-python-cache"
        source.mkdir()
        ignore_cache = shutil.ignore_patterns("__pycache__", "*.pyc")
        for directory in ("olympus", "scripts"):
            shutil.copytree(ROOT / directory, source / directory, ignore=ignore_cache)
        shutil.copyfile(ROOT / "install.ps1", source / "install.ps1")
        generated = "# GENERATED BY scripts/render_harnesses.py\n"
        for relative in expected_cli_agents:
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        for relative in (*expected_cli_commands, ".opencode/commands/user-owned.md"):
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(generated, encoding="utf-8")
        for relative in (".opencode/plugins/olympus-activity/activity.ts", ".opencode/plugins/olympus-activity/tui.tsx",
                         ".opencode/scripts/worktree-setup.ps1", "opencode.jsonc"):
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(generated, encoding="utf-8")
        bytecode = source / "olympus/__pycache__/qualification.cpython-312.pyc"
        bytecode.parent.mkdir(parents=True)
        bytecode.write_bytes(b"synthetic bytecode")

        install_root = self.sandbox / "cli-python-cache"
        install_root.mkdir()
        path_store = install_root / "path-store.txt"
        user_file = install_root / "user-note.txt"
        user_bytes = b"user-owned CLI data\n"
        user_file.write_bytes(user_bytes)
        version_root = install_root / "versions" / RELEASE_VERSION
        installed = self._cli_installer("install", install_root, path_store, source_root=source)
        self.assertEqual(0, installed.returncode, installed.stdout + installed.stderr)
        manifest = json.loads((version_root / "olympus-cli-manifest.json").read_text(encoding="utf-8"))
        package_paths = {entry["path"] for entry in manifest["files"]}
        self.assertEqual(expected_cli_commands, {
            path for path in package_paths if path.startswith(".opencode/commands/")
        })
        self.assertFalse((version_root / ".opencode/commands/user-owned.md").exists())
        self.assertFalse(any("__pycache__" in path or path.endswith(".pyc") for path in package_paths))
        self.assertFalse((version_root / "olympus/__pycache__").exists())
        self.assertEqual(user_bytes, user_file.read_bytes())

        removed = self._cli_installer("uninstall", install_root, path_store)
        self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
        self.assertFalse(version_root.exists())
        self.assertEqual(user_bytes, user_file.read_bytes())

        reinstalled = self._cli_installer("install", install_root, path_store, source_root=source)
        self.assertEqual(0, reinstalled.returncode, reinstalled.stdout + reinstalled.stderr)
        manifest = json.loads((version_root / "olympus-cli-manifest.json").read_text(encoding="utf-8"))
        package_paths = {entry["path"] for entry in manifest["files"]}
        self.assertEqual(expected_cli_commands, {
            path for path in package_paths if path.startswith(".opencode/commands/")
        })
        self.assertFalse((version_root / ".opencode/commands/user-owned.md").exists())
        self.assertFalse(any("__pycache__" in path or path.endswith(".pyc") for path in package_paths))
        self.assertFalse((version_root / "olympus/__pycache__").exists())
        final_removed = self._cli_installer("uninstall", install_root, path_store)
        self.assertEqual(0, final_removed.returncode, final_removed.stdout + final_removed.stderr)
        self.assertFalse(version_root.exists())
        self.assertEqual(user_bytes, user_file.read_bytes())
        self.assertEqual(b"synthetic bytecode", bytecode.read_bytes())

    def test_cli_package_uninstall_refuses_reparse_redirects_before_local_mutations(self):
        user_config = self.appdata / "Olympus/config.json"
        user_config.parent.mkdir(parents=True, exist_ok=True)
        user_config_bytes = b'{"user_owned":true}\n'
        user_config.write_bytes(user_config_bytes)

        def quote(path: Path) -> str:
            return "'" + str(path).replace("'", "''") + "'"

        def make_junction(link: Path, target: Path):
            command = (
                f"$ErrorActionPreference='Stop'; "
                f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(target)} | Out-Null"
            )
            result = subprocess.run(
                [self.pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False,
            )
            if result.returncode:
                self.skipTest("Windows junction creation unavailable; containment cases NOT RUN: "
                              + result.stdout + result.stderr)

        def remove_junction(link: Path):
            try:
                os.rmdir(link)
            except FileNotFoundError:
                pass

        def installed_fixture(name: str):
            install_root = self.sandbox / ("cli-containment-" + name)
            install_root.mkdir()
            path_store = install_root / "path-store.txt"
            path_store.write_text("C:\\user-tools", encoding="utf-8")
            installed = self._cli_installer("install", install_root, path_store)
            self.assertEqual(0, installed.returncode, installed.stdout + installed.stderr)
            package = install_root / "versions" / RELEASE_VERSION
            bin_path = install_root / "bin"
            state = {
                "current": (install_root / "current.txt").read_bytes(),
                "manifest": (package / "olympus-cli-manifest.json").read_bytes(),
                "owned_file": (package / "olympus/global_cli.py").read_bytes(),
                "wrapper": (bin_path / "olympus.cmd").read_bytes(),
                "path_receipt": (install_root / "path-entry.txt").read_bytes(),
                "path_store": path_store.read_bytes(),
                "user_config": user_config.read_bytes(),
            }
            return install_root, path_store, package, bin_path, state

        def assert_refused(install_root: Path, path_store: Path, package: Path, bin_path: Path,
                           state: dict[str, bytes], sentinel: Path):
            result = self._cli_installer("uninstall", install_root, path_store)
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("CLI_PATH_UNSAFE", result.stdout + result.stderr)
            self.assertEqual(b"harmless redirect sentinel\n", sentinel.read_bytes())
            self.assertEqual(state["current"], (install_root / "current.txt").read_bytes())
            self.assertEqual(state["manifest"], (package / "olympus-cli-manifest.json").read_bytes())
            self.assertEqual(state["owned_file"], (package / "olympus/global_cli.py").read_bytes())
            self.assertEqual(state["wrapper"], (bin_path / "olympus.cmd").read_bytes())
            self.assertEqual(state["path_receipt"], (install_root / "path-entry.txt").read_bytes())
            self.assertEqual(state["path_store"], path_store.read_bytes())
            self.assertEqual(state["user_config"], user_config.read_bytes())

        # Redirect the install root itself to its ordinary fixture installation.
        root, path_store, package, bin_path, state = installed_fixture("root")
        alias = self.sandbox / "cli-root-alias"
        sentinel = root / "containment-sentinel.txt"
        sentinel.write_bytes(b"harmless redirect sentinel\n")
        make_junction(alias, root)
        try:
            assert_refused(alias, alias / "path-store.txt", package, bin_path, state, sentinel)
        finally:
            remove_junction(alias)

        # Manifest-listed package and cleanup destinations must be checked
        # before any of their owned files, PATH, or receipts are changed.
        for name, relative in (("nested", ".opencode"), ("cleanup", "scripts")):
            with self.subTest(path=relative):
                root, path_store, package, bin_path, state = installed_fixture(name)
                link = package / relative
                saved = package / (relative.replace("/", "-") + "-saved")
                target = self.sandbox / ("cli-redirect-target-" + name)
                target.mkdir()
                sentinel = target / "sentinel.txt"
                sentinel.write_bytes(b"harmless redirect sentinel\n")
                os.rename(link, saved)
                try:
                    make_junction(link, target)
                    assert_refused(root, path_store, package, bin_path, state, sentinel)
                finally:
                    remove_junction(link)
                    if saved.exists():
                        os.rename(saved, link)

        # The redirected versions target contains only an empty fake release
        # directory; no deletion-eligible package file is outside the fixture.
        root, path_store, package, bin_path, state = installed_fixture("versions")
        versions = root / "versions"
        saved_versions = root / "versions-saved"
        target_versions = self.sandbox / "cli-redirect-target-versions"
        (target_versions / RELEASE_VERSION).mkdir(parents=True)
        sentinel = target_versions / "sentinel.txt"
        sentinel.write_bytes(b"harmless redirect sentinel\n")
        os.rename(versions, saved_versions)
        try:
            make_junction(versions, target_versions)
            assert_refused(root, path_store, saved_versions / RELEASE_VERSION, bin_path, state, sentinel)
        finally:
            remove_junction(versions)
            if saved_versions.exists():
                os.rename(saved_versions, versions)

        # A redirected bin directory is rejected before PATH or receipt updates.
        root, path_store, package, bin_path, state = installed_fixture("bin")
        saved_bin = root / "bin-saved"
        target_bin = self.sandbox / "cli-redirect-target-bin"
        target_bin.mkdir()
        sentinel = target_bin / "sentinel.txt"
        sentinel.write_bytes(b"harmless redirect sentinel\n")
        os.rename(bin_path, saved_bin)
        try:
            make_junction(bin_path, target_bin)
            assert_refused(root, path_store, package, saved_bin, state, sentinel)
        finally:
            remove_junction(bin_path)
            if saved_bin.exists():
                os.rename(saved_bin, bin_path)

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
        original_project_agent = (project / ".opencode/agents/nox.md").read_bytes()
        env_patch = {"APPDATA": str(self.appdata), "LOCALAPPDATA": str(self.localappdata),
                     "USERPROFILE": str(self.profile), "OPENCODE_CONFIG_DIR": str(self.root),
                     "OLYMPUS_CONFIG_FILE": str(self.appdata / "Olympus/config.json")}
        with mock.patch.dict(os.environ, env_patch):
            self.assertEqual(0, main(["--source", str(ROOT), "nox", "set-model", "openai/gpt-6.1-sol", "--scope", "global"]))
            self.assertEqual(0, main(["--source", str(ROOT), "nox", "set-effort", "high", "--scope", "global"]))
            global_nox = next(row for row in user_config.effective_roles(ROOT) if row["role"] == "nox")
            self.assertNotIn(
                f'model: "{global_nox["model"]}#{global_nox["effort"]}"',
                original_project_agent.decode("utf-8"),
            )
            pending_marker = project / "olympus/opencode-guard-pending.json"
            pending_marker.parent.mkdir(parents=True, exist_ok=True)
            pending_marker.write_bytes(b"unrelated project-local marker")
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
        self.assertEqual(b"unrelated project-local marker", pending_marker.read_bytes())
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

        inconsistent = self._create_project()
        inconsistent_agent = inconsistent / ".opencode/agents/nox.md"
        inconsistent_manifest = inconsistent / ".opencode/orchestrator-install.json"
        inconsistent_preferences = inconsistent / ".opencode/olympus-config.json"
        inconsistent_preferences.write_text(json.dumps({
            "schema_version": 1, "overrides": {"nox": {"model": "openai/gpt-6.1-sol"}},
        }) + "\n", encoding="utf-8")
        inconsistent_before = (
            inconsistent_preferences.read_bytes(), inconsistent_agent.read_bytes(),
            inconsistent_manifest.read_bytes(),
        )
        with mock.patch.dict(os.environ, env_patch), contextlib.redirect_stdout(io.StringIO()):
            code = main(["--source", str(ROOT), "nox", "set-effort", "high",
                         "--scope", "project", "--target", str(inconsistent)])
        self.assertNotEqual(0, code)
        self.assertEqual(inconsistent_before, (
            inconsistent_preferences.read_bytes(), inconsistent_agent.read_bytes(),
            inconsistent_manifest.read_bytes(),
        ))

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

    def test_override_rejects_incomplete_and_wrong_current_inventories_without_writes(self):
        project = self._create_project()
        for scope, root, manifest_path in (
            ("global", self.root, self.manifest_path),
            ("project", project, project / ".opencode/orchestrator-install.json"),
        ):
            original = manifest_path.read_bytes()
            for mutation in ("missing", "unexpected"):
                with self.subTest(scope=scope, mutation=mutation):
                    manifest = json.loads(original)
                    if mutation == "missing":
                        manifest["managed_files"].pop()
                    else:
                        manifest["managed_files"][-1]["path"] = "user-note.txt"
                    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
                    before = {path.relative_to(root): path.read_bytes()
                              for path in root.rglob("*") if path.is_file()}
                    config = user_config.config_path()
                    config_before = config.read_bytes() if config.exists() else None
                    with self.assertRaises(user_config.UserConfigError):
                        user_config.set_override(ROOT, "nox", "effort", "high", scope,
                                                 project if scope == "project" else None)
                    self.assertEqual(before, {path.relative_to(root): path.read_bytes()
                                              for path in root.rglob("*") if path.is_file()})
                    self.assertEqual(config_before, config.read_bytes() if config.exists() else None)
            manifest_path.write_bytes(original)

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
        global_before = self._global_files()
        settings = self.appdata / "Olympus/config.json"
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
        self.assertEqual({"schema_version": 1, "overrides": {"nox": {"model": "openai/gpt-6.1-sol", "effort": "high"}}},
                         json.loads(settings.read_text(encoding="utf-8")))
        self.assertEqual(
            {"agents/nox.md", "olympus/orchestrator-install.json"},
            {relative for relative, content in self._global_files().items()
             if global_before.get(relative) != content},
        )
        self.assertEqual(
            {relative: content for relative, content in global_before.items()
             if relative not in {"agents/nox.md", "olympus/orchestrator-install.json"}},
            {relative: content for relative, content in self._global_files().items()
             if relative not in {"agents/nox.md", "olympus/orchestrator-install.json"}},
        )
        self.assertTrue(settings.is_file())
        self.assertEqual(15, len(self._manifest()["managed_files"]))
        self.assertIn('model: "openai/gpt-6.1-sol#high"', self._agent("nox").read_text(encoding="utf-8"))
        manifest = self._manifest()
        entry = next(item for item in manifest["managed_files"] if item["path"] == "agents/nox.md")
        self.assertEqual(hashlib.sha256(self._agent("nox").read_bytes()).hexdigest(), entry["sha256"])
        self.assertEqual(models_before, (ROOT / "olympus/core/models.toml").read_bytes())
        self.assertIn("openai/gpt-6.1-sol", output.getvalue())
        self.assertIn(str(settings.resolve()), output.getvalue())
        self.assertTrue(output.getvalue().rstrip().endswith("Next step: run 'olympus doctor' after manual edits."))

        with mock.patch.dict(os.environ, env_patch):
            expected = global_readonly._expected(
                ROOT, __import__("olympus.cli", fromlist=["load_renderer"]).load_renderer(ROOT), ("opencode",),
            )
            user_config.apply_to_expected(ROOT, expected["opencode"])
        self.assertIn(b'model: "openai/gpt-6.1-sol#high"', expected["opencode"]["agents/nox.md"])

    def test_global_override_recovery_rolls_back_each_interrupted_destination(self):
        settings = self.appdata / "Olympus/config.json"
        before_agent = self._agent("nox").read_bytes()
        before_manifest = self.manifest_path.read_bytes()
        publish = config_apply_transaction._settings_publish

        for stop_path in ("agents/nox.md", "olympus/orchestrator-install.json"):
            with self.subTest(destination=stop_path):
                interrupted = False

                def stop_after_publish(*args, **kwargs):
                    nonlocal interrupted
                    result = publish(*args, **kwargs)
                    if not interrupted and args[4] == stop_path:
                        interrupted = True
                        raise KeyboardInterrupt("fixture process interruption")
                    return result

                with mock.patch("olympus.config_apply_transaction._settings_publish",
                                side_effect=stop_after_publish):
                    with self.assertRaises(KeyboardInterrupt):
                        user_config.set_override(ROOT, "nox", "effort", "high")
                self.assertTrue(interrupted)
                self.assertTrue((self.root / ".olympus-cli-config-apply/record.json").is_file())

                output = io.StringIO()
                with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
                    code = main([
                        "--source", str(ROOT), "config", "recover", "--scope", "global",
                        "--harness", "opencode",
                    ])
                self.assertEqual(0, code, output.getvalue())
                self.assertIn("Recovery: rolled_back", output.getvalue())
                self.assertEqual(before_agent, self._agent("nox").read_bytes())
                self.assertEqual(before_manifest, self.manifest_path.read_bytes())
                self.assertFalse(settings.exists())
                self.assertFalse((self.root / ".olympus-cli-config-apply").exists())

        commit = config_apply_transaction._settings_commit_preferences

        def stop_after_preferences(*args, **kwargs):
            result = commit(*args, **kwargs)
            raise KeyboardInterrupt("fixture process interruption after preference commit")

        with mock.patch("olympus.config_apply_transaction._settings_commit_preferences",
                        side_effect=stop_after_preferences):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_override(ROOT, "nox", "effort", "high")
        committed_preferences = settings.read_bytes()
        committed_preference_identity = settings.stat()
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("Recovery: committed_cleanup", output.getvalue())
        self.assertEqual(committed_preferences, settings.read_bytes())
        self.assertEqual(
            (committed_preference_identity.st_dev, committed_preference_identity.st_ino,
             committed_preference_identity.st_mtime_ns),
            (settings.stat().st_dev, settings.stat().st_ino, settings.stat().st_mtime_ns),
        )
        self.assertEqual({"schema_version": 1, "overrides": {"nox": {"effort": "high"}}},
                         json.loads(committed_preferences))
        self.assertIn(b'model: "openai/gpt-6-luna#high"', self._agent("nox").read_bytes())
        self.assertFalse((self.root / ".olympus-cli-config-apply").exists())

    def test_global_max_parallel_recovery_and_config_only_stays_atomic(self):
        self._force_global_kael_crlf()
        settings = self.appdata / "Olympus/config.json"
        before_agents = {role: self._agent(role).read_bytes() for role in ("kael", "atlas")}
        before_manifest = self.manifest_path.read_bytes()
        commit = config_apply_transaction._settings_commit_preferences

        def stop_after_preferences(*args, **kwargs):
            commit(*args, **kwargs)
            raise KeyboardInterrupt("fixture process interruption")

        with mock.patch("olympus.config_apply_transaction._settings_commit_preferences",
                        side_effect=stop_after_preferences):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_max_children(ROOT, 3)
        committed_preferences = settings.read_bytes()
        committed_preference_identity = settings.stat()
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("Recovery: committed_cleanup", output.getvalue())
        for role in ("kael", "atlas"):
            agent = self._agent(role).read_bytes()
            self.assertNotEqual(before_agents[role], agent)
            self.assertIn(b"MAX_ACTIVE_CHILDREN = 3", agent)
            receipt = next(
                item for item in self._manifest()["managed_files"] if item["path"] == f"agents/{role}.md"
            )
            self.assertEqual(hashlib.sha256(agent).hexdigest(), receipt["sha256"])
        self.assertNotEqual(before_manifest, self.manifest_path.read_bytes())
        self.assertEqual(committed_preferences, settings.read_bytes())
        self.assertEqual(
            (committed_preference_identity.st_dev, committed_preference_identity.st_ino,
             committed_preference_identity.st_mtime_ns),
            (settings.stat().st_dev, settings.stat().st_ino, settings.stat().st_mtime_ns),
        )
        self.assertEqual({"schema_version": 1, "overrides": {}, "orchestration": {"max_children": 3}},
                         json.loads(committed_preferences))
        self.assertFalse((self.root / ".olympus-cli-config-apply").exists())

        absent_root = self.sandbox / "atomic-config-only" / "opencode"
        atomic_settings = self.sandbox / "atomic-user-config" / "Olympus/config.json"
        env = self.env.copy()
        env.update({"OPENCODE_CONFIG_DIR": str(absent_root), "OLYMPUS_CONFIG_FILE": str(atomic_settings)})
        with mock.patch.dict(os.environ, env, clear=True):
            user_config.set_override(ROOT, "nox", "effort", "high")
        self.assertEqual([".olympus-cli-edit.lock"], sorted(item.name for item in absent_root.iterdir()))
        self.assertTrue(atomic_settings.is_file())

    def test_legacy_single_agent_max_parallel_journal_is_preserved(self):
        prepare = user_config._prepare_installed_update
        validate = config_apply_transaction._settings_validate_record
        agent_paths = config_apply_transaction._settings_agent_paths

        def prepare_single_agent(*args, **kwargs):
            agent_updates, manifest_path, manifest_old, manifest_new = prepare(*args, **kwargs)
            kael_update = next(item for item in agent_updates if item[0] == self._agent("kael"))
            old_manifest = json.loads(manifest_old)
            new_manifest = json.loads(manifest_new)
            atlas_receipt = next(item for item in old_manifest["managed_files"]
                                 if item["path"] == "agents/atlas.md")
            next(item for item in new_manifest["managed_files"]
                 if item["path"] == "agents/atlas.md")["sha256"] = atlas_receipt["sha256"]
            legacy_manifest_new = (
                json.dumps(new_manifest, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            return (kael_update,), manifest_path, manifest_old, legacy_manifest_new

        def legacy_agent_paths(record):
            if record["change"].get("kind") == "max_children":
                return (record["agent_path"],)
            return agent_paths(record)

        def legacy_validate(target, source, lock, record, scope):
            # Model the previous validator only while creating this historical fixture.
            if (record.get("change", {}).get("kind") == "max_children"
                    and isinstance(record.get("files"), list) and len(record["files"]) == 3):
                return {entry["path"]: entry for entry in record["files"]}
            return validate(target, source, lock, record, scope)

        with mock.patch.object(user_config, "_prepare_installed_update", side_effect=prepare_single_agent), \
                mock.patch.object(config_apply_transaction, "_settings_agent_paths",
                                  side_effect=legacy_agent_paths), \
                mock.patch.object(config_apply_transaction, "_settings_validate_record",
                                  side_effect=legacy_validate), \
                mock.patch("olympus.config_apply_transaction._settings_cleanup",
                           side_effect=KeyboardInterrupt("leave committed legacy journal")):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_max_children(ROOT, 3)

        scratch = self.root / ".olympus-cli-config-apply"
        record_path = scratch / "record.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual("COMMITTED", record["state"])
        self.assertEqual(3, len(record["files"]))
        self.assertEqual({"max_children": 3},
                         json.loads((self.appdata / "Olympus/config.json").read_text(encoding="utf-8"))[
                             "orchestration"
                         ])
        self.assertIn(b"MAX_ACTIVE_CHILDREN = 3", self._agent("kael").read_bytes())
        self.assertIn(b"MAX_ACTIVE_CHILDREN = 4", self._agent("atlas").read_bytes())
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()
        }

        output = io.StringIO()
        errors = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(errors):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        diagnostic = output.getvalue() + errors.getvalue()
        self.assertNotEqual(0, code, diagnostic)
        self.assertIn("preserve its evidence", diagnostic)
        self.assertIn("source version that created it", diagnostic)
        self.assertEqual(before, {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()
        })
        self.assertTrue(record_path.is_file())

    def test_global_max_parallel_rejects_legacy_manifest_before_lock_or_settings(self):
        self._downgrade_global_to_v010(self.root)
        lock_path = self.root / source_edit._LOCK_NAME
        lock_path.unlink(missing_ok=True)
        before_root = self._global_files()
        settings = self.appdata / "Olympus/config.json"
        self.assertFalse(settings.exists())

        with self.assertRaisesRegex(user_config.UserConfigError, "historically unsupported"):
            user_config.set_max_children(ROOT, 3)

        self.assertEqual(before_root, self._global_files())
        self.assertFalse(lock_path.exists())
        self.assertFalse(settings.exists())
        self.assertFalse(settings.parent.exists())

    def test_project_override_recovery_and_project_writers_guard_pending_settings(self):
        project = self._create_project()
        agent = project / ".opencode/agents/nox.md"
        manifest = project / ".opencode/orchestrator-install.json"
        preferences = project / ".opencode/olympus-config.json"
        before_agent, before_manifest = agent.read_bytes(), manifest.read_bytes()
        publish = config_apply_transaction._settings_publish

        def stop_after_manifest(*args, **kwargs):
            result = publish(*args, **kwargs)
            if args[4] == ".opencode/orchestrator-install.json":
                raise KeyboardInterrupt("fixture process interruption")
            return result

        with mock.patch("olympus.config_apply_transaction._settings_publish", side_effect=stop_after_manifest):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_override(ROOT, "nox", "effort", "high", "project", project)
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "project", "--target", str(project),
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("config recover: rolled_back", output.getvalue())
        self.assertEqual(before_agent, agent.read_bytes())
        self.assertEqual(before_manifest, manifest.read_bytes())
        self.assertFalse(preferences.exists())
        self.assertFalse((project / ".olympus-cli-config-apply").exists())

        commit = config_apply_transaction._settings_commit_preferences

        def stop_after_preferences(*args, **kwargs):
            commit(*args, **kwargs)
            raise KeyboardInterrupt("fixture interruption after project preference commit")

        with mock.patch("olympus.config_apply_transaction._settings_commit_preferences",
                        side_effect=stop_after_preferences):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_override(ROOT, "nox", "effort", "high", "project", project)
        committed_preferences = preferences.read_bytes()
        preference_metadata = preferences.stat()
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "project", "--target", str(project),
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("config recover: committed_cleanup", output.getvalue())
        self.assertEqual(committed_preferences, preferences.read_bytes())
        self.assertEqual(
            (preference_metadata.st_dev, preference_metadata.st_ino, preference_metadata.st_mtime_ns),
            (preferences.stat().st_dev, preferences.stat().st_ino, preferences.stat().st_mtime_ns),
        )
        self.assertIn(b'model: "openai/gpt-6-luna#high"', agent.read_bytes())
        self.assertFalse((project / ".olympus-cli-config-apply").exists())

        for operation in ("bootstrap", "uninstall"):
            with self.subTest(writer=operation):
                blocked_project = self._create_project(version="unknown")
                pending = blocked_project / ".olympus-cli-config-apply"
                pending.mkdir()
                (pending / "preserve.txt").write_bytes(b"pending user-settings evidence\n")
                managed_agent = blocked_project / ".opencode/agents/nox.md"
                managed_manifest = blocked_project / ".opencode/orchestrator-install.json"
                before = managed_agent.read_bytes(), managed_manifest.read_bytes()
                if operation == "bootstrap":
                    result = self._project_update(blocked_project)
                else:
                    result = subprocess.run(
                        [self.pwsh, "-NoProfile", "-NonInteractive", "-File",
                         str(ROOT / "scripts/project-uninstall.ps1"), "-Target", str(blocked_project),
                         "-Harness", "opencode"],
                        cwd=ROOT, env=self.env, capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=60, check=False,
                    )
                output = result.stdout + result.stderr
                self.assertNotEqual(0, result.returncode, output)
                self.assertIn("CONFIG_RECOVERY_PENDING", output)
                self.assertEqual(before, (managed_agent.read_bytes(), managed_manifest.read_bytes()))
                self.assertEqual(b"pending user-settings evidence\n", (pending / "preserve.txt").read_bytes())

    def test_project_recovery_uses_captured_global_fallback(self):
        global_model = "openai/gpt-6.1-sol"
        user_config.set_override(ROOT, "nox", "model", global_model)
        project = self._create_project()
        agent = project / ".opencode/agents/nox.md"
        manifest_path = project / ".opencode/orchestrator-install.json"
        original = user_config._replace_agent_model(agent.read_bytes(), global_model, "max", "nox")
        agent.write_bytes(original)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        next(item for item in manifest["managed_files"] if item["path"] == ".opencode/agents/nox.md")[
            "sha256"
        ] = hashlib.sha256(original).hexdigest()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before_agent, before_manifest = agent.read_bytes(), manifest_path.read_bytes()
        publish = config_apply_transaction._settings_publish

        def stop_after_agent(*args, **kwargs):
            result = publish(*args, **kwargs)
            if args[4] == ".opencode/agents/nox.md":
                raise KeyboardInterrupt("fixture process interruption")
            return result

        with mock.patch("olympus.config_apply_transaction._settings_publish", side_effect=stop_after_agent):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_override(ROOT, "nox", "effort", "high", "project", project)
        record = json.loads((project / ".olympus-cli-config-apply/record.json").read_text(encoding="utf-8"))
        self.assertEqual({"model": global_model, "effort": "max"}, record["project_fallback"])

        user_config.set_override(ROOT, "nox", "model", "openai/gpt-6-luna")
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "project", "--target", str(project),
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("config recover: rolled_back", output.getvalue())
        self.assertEqual(before_agent, agent.read_bytes())
        self.assertEqual(before_manifest, manifest_path.read_bytes())
        self.assertFalse((project / ".olympus-cli-config-apply").exists())

    def test_user_settings_recovery_handles_unchanged_preferences_by_record_state(self):
        self._force_global_kael_crlf()
        settings = self.appdata / "Olympus/config.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps({
            "schema_version": 1, "overrides": {}, "orchestration": {"max_children": 3},
        }, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        settings.write_bytes(encoded)
        unchanged_metadata = settings.stat()
        before_agents = {role: self._agent(role).read_bytes() for role in ("kael", "atlas")}
        before_manifest = self.manifest_path.read_bytes()
        with mock.patch("olympus.config_apply_transaction._settings_cleanup",
                        side_effect=KeyboardInterrupt("stop before committed cleanup")):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_max_children(ROOT, 3)
        self.assertTrue((self.root / ".olympus-cli-config-apply/record.json").is_file())
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("Recovery: committed_cleanup", output.getvalue())
        self.assertEqual(encoded, settings.read_bytes())
        self.assertEqual(
            (unchanged_metadata.st_dev, unchanged_metadata.st_ino, unchanged_metadata.st_mtime_ns),
            (settings.stat().st_dev, settings.stat().st_ino, settings.stat().st_mtime_ns),
        )
        for role in ("kael", "atlas"):
            self.assertNotEqual(before_agents[role], self._agent(role).read_bytes())
        self.assertNotEqual(before_manifest, self.manifest_path.read_bytes())

        for role, content in before_agents.items():
            self._agent(role).write_bytes(content)
        self.manifest_path.write_bytes(before_manifest)
        publish = config_apply_transaction._settings_publish

        def stop_after_manifest(*args, **kwargs):
            result = publish(*args, **kwargs)
            if args[4] == "olympus/orchestrator-install.json":
                raise KeyboardInterrupt("stop before unchanged-preference commit")
            return result

        with mock.patch("olympus.config_apply_transaction._settings_publish", side_effect=stop_after_manifest):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_max_children(ROOT, 3)
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("Recovery: rolled_back", output.getvalue())
        self.assertEqual(encoded, settings.read_bytes())
        self.assertEqual(
            (unchanged_metadata.st_dev, unchanged_metadata.st_ino, unchanged_metadata.st_mtime_ns),
            (settings.stat().st_dev, settings.stat().st_ino, settings.stat().st_mtime_ns),
        )
        self.assertEqual(before_agents, {role: self._agent(role).read_bytes() for role in before_agents})
        self.assertEqual(before_manifest, self.manifest_path.read_bytes())

    def test_user_settings_recovery_resumes_cleanup_after_backup_removal(self):
        safe_remove = config_apply_transaction._safe_remove
        publish = config_apply_transaction._settings_publish

        def stop_after_agent(*args, **kwargs):
            result = publish(*args, **kwargs)
            if args[4] == "agents/nox.md":
                raise KeyboardInterrupt("interrupted before preference commit")
            return result

        with mock.patch("olympus.config_apply_transaction._settings_publish", side_effect=stop_after_agent):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_override(ROOT, "nox", "effort", "high")

        def stop_after_backup(*args, **kwargs):
            result = safe_remove(*args, **kwargs)
            if args[1] == ".olympus-cli-config-apply/backups/file-0000.old":
                raise KeyboardInterrupt("interrupted during rollback cleanup")
            return result

        output = io.StringIO()
        with mock.patch("olympus.config_apply_transaction._safe_remove", side_effect=stop_after_backup):
            with mock.patch.dict(os.environ, self.env):
                with self.assertRaises(KeyboardInterrupt):
                    config_apply_transaction.recover_global(self.root, ROOT, load_renderer=load_renderer)
        self.assertEqual(
            b'model: "openai/gpt-6-luna#max"',
            next(line for line in self._agent("nox").read_bytes().splitlines() if line.startswith(b"model:")),
        )
        self.assertFalse((self.appdata / "Olympus/config.json").exists())
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("Recovery: discarded_uncommitted", output.getvalue())
        self.assertFalse((self.root / ".olympus-cli-config-apply").exists())

        def stop_committed_cleanup(*args, **kwargs):
            result = safe_remove(*args, **kwargs)
            if args[1] == ".olympus-cli-config-apply/backups/file-0000.old":
                raise KeyboardInterrupt("interrupted during committed cleanup")
            return result

        with mock.patch("olympus.config_apply_transaction._safe_remove", side_effect=stop_committed_cleanup):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_override(ROOT, "nox", "effort", "high")
        settings = self.appdata / "Olympus/config.json"
        committed_agent = self._agent("nox").read_bytes()
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("Recovery: committed_cleanup", output.getvalue())
        self.assertEqual(committed_agent, self._agent("nox").read_bytes())
        self.assertEqual("high", json.loads(settings.read_text(encoding="utf-8"))["overrides"]["nox"]["effort"])
        self.assertFalse((self.root / ".olympus-cli-config-apply").exists())

    def test_user_settings_recovery_promotes_only_valid_prepublication_record(self):
        replace = config_apply_transaction.os.replace

        def interrupt_initial_record(source, destination):
            if Path(source).name == ".record.json.tmp" and Path(destination).name == "record.json":
                raise KeyboardInterrupt("stop before initial journal publication")
            return replace(source, destination)

        with mock.patch("olympus.config_apply_transaction.os.replace", side_effect=interrupt_initial_record):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_override(ROOT, "nox", "effort", "high")
        scratch = self.root / ".olympus-cli-config-apply"
        temporary = scratch / ".record.json.tmp"
        self.assertTrue(temporary.is_file())
        self.assertFalse((scratch / "record.json").exists())
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("Recovery: discarded_incomplete_prepare", output.getvalue())
        self.assertFalse(scratch.exists())

        with mock.patch("olympus.config_apply_transaction.os.replace", side_effect=interrupt_initial_record):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_override(ROOT, "nox", "effort", "high")
        temporary = self.root / ".olympus-cli-config-apply/.record.json.tmp"
        temporary.write_bytes(b'{"kind":"user_config"}\n')
        preserved = temporary.read_bytes()
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertNotEqual(0, code, output.getvalue())
        self.assertEqual(preserved, temporary.read_bytes())
        self.assertFalse((self.root / ".olympus-cli-config-apply/record.json").exists())
        temporary.unlink()
        scratch.rmdir()
        scratch.mkdir()
        (scratch / "backups").mkdir()
        (scratch / "staged").mkdir()
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertNotEqual(0, code, output.getvalue())
        self.assertTrue((scratch / "backups").is_dir())
        self.assertTrue((scratch / "staged").is_dir())

    def test_global_recovery_preserves_changed_preference_path_and_third_state(self):
        settings = self.appdata / "Olympus/config.json"
        before_agent = self._agent("nox").read_bytes()
        publish = config_apply_transaction._settings_publish

        def stop_after_agent(*args, **kwargs):
            result = publish(*args, **kwargs)
            if args[4] == "agents/nox.md":
                raise KeyboardInterrupt("fixture process interruption")
            return result

        with mock.patch("olympus.config_apply_transaction._settings_publish", side_effect=stop_after_agent):
            with self.assertRaises(KeyboardInterrupt):
                user_config.set_override(ROOT, "nox", "effort", "high")
        after_agent = self._agent("nox").read_bytes()
        pending = self.root / ".olympus-cli-config-apply"
        alternate = self.sandbox / "alternate-preferences/config.json"
        changed_env = self.env.copy()
        changed_env["OLYMPUS_CONFIG_FILE"] = str(alternate)
        output = io.StringIO()
        with mock.patch.dict(os.environ, changed_env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertNotEqual(0, code, output.getvalue())
        self.assertTrue(pending.joinpath("record.json").is_file())
        self.assertEqual(after_agent, self._agent("nox").read_bytes())
        self.assertFalse(alternate.exists())

        unrelated = b'{"schema_version":1,"overrides":{"argus":{"effort":"high"}}}\n'
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_bytes(unrelated)
        before_root = self._global_files()
        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertNotEqual(0, code, output.getvalue())
        self.assertEqual(before_root, self._global_files())
        self.assertEqual(unrelated, settings.read_bytes())
        self.assertTrue(pending.joinpath("record.json").is_file())
        settings.unlink()

        output = io.StringIO()
        with mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(ROOT), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("Recovery: rolled_back", output.getvalue())
        self.assertEqual(before_agent, self._agent("nox").read_bytes())
        self.assertFalse(pending.exists())

    def test_global_command_destinations_are_hash_owned_and_removed_on_uninstall(self):
        manifest = self._manifest()
        entries = {item["path"]: item["sha256"] for item in manifest["managed_files"]}
        for command in ("olympus.ultra", "olympus.performance", "olympus.performance-ultra"):
            relative = f"commands/{command}.md"
            raw = (self.root / relative).read_bytes()
            self.assertEqual((ROOT / ".opencode" / relative).read_bytes(), raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entries[relative])

        removed = self._uninstall_global(self.env)
        self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
        self.assertFalse(self.manifest_path.exists())
        for command in ("olympus.ultra", "olympus.performance", "olympus.performance-ultra"):
            self.assertFalse((self.root / f"commands/{command}.md").exists())

    def test_v010_global_inventories_are_rejected_before_lock_or_mutation(self):
        original_user_config = (
            b'{"default_agent":"other","permissions":[{"action":"external_directory",'
            b'"resource":"*","effect":"ask"}]}\n'
        )
        current_roles = ("kael", "atlas", "veyra", "kovan", "nox", "vera", "helios", "talos", "thales")
        current_commands = ("olympus.ultra", "olympus.performance", "olympus.performance-ultra")
        for owns_guard in (True, False):
            with self.subTest(owns_guard=owns_guard):
                root = self.sandbox / ("legacy-owned" if owns_guard else "legacy-user-config")
                root.mkdir()
                env = self.env.copy()
                env["OPENCODE_CONFIG_DIR"] = str(root)
                user_config_path = root / "opencode.json"
                if not owns_guard:
                    user_config_path.write_bytes(original_user_config)

                installed = self._engine(update=False, env=env)
                self.assertEqual(0, installed.returncode, installed.stdout + installed.stderr)
                current_manifest_path = root / "olympus/orchestrator-install.json"
                current_manifest = json.loads(current_manifest_path.read_text(encoding="utf-8"))
                user_config_after_install = user_config_path.read_bytes() if user_config_path.exists() else None
                expected_paths = {
                    *(f"agents/{role}.md" for role in current_roles),
                    "plugins/olympus-activity/activity.ts",
                    "plugins/olympus-activity/tui.tsx",
                    *(f"commands/{command}.md" for command in current_commands),
                }
                if owns_guard:
                    expected_paths.add("opencode.jsonc")
                self.assertEqual(expected_paths, {item["path"] for item in current_manifest["managed_files"]})
                self.assertEqual(15 if owns_guard else 14, len(current_manifest["managed_files"]))
                verified = self._verify_global(env)
                self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)

                legacy = self._downgrade_global_to_v010(root)
                self.assertEqual(12 if owns_guard else 11, len(legacy["managed_files"]))
                lock_path = root / source_edit._LOCK_NAME
                lock_path.unlink(missing_ok=True)
                before_rejection = self._global_files(root)
                self.assertFalse(lock_path.exists())

                for arguments in ([], ["-Update"], ["-Force"], ["-Uninstall"], ["-VerifyOnly"]):
                    with self.subTest(arguments=arguments):
                        rejected = self._run_global_operation(arguments, env)
                        output = rejected.stdout + rejected.stderr
                        self.assertNotEqual(0, rejected.returncode, output)
                        self.assertIn("GLOBAL_MANIFEST_INVALID", output)
                        self.assertIn(
                            "Uninstall it with the Olympus version that created this installation, "
                            "then install the current version",
                            output,
                        )
                        self.assertEqual(before_rejection, self._global_files(root))
                        self.assertFalse(lock_path.exists(), "Rejected historical state must not create the stable lock.")
                        if not owns_guard:
                            self.assertEqual(user_config_after_install, user_config_path.read_bytes())

    def test_global_unowned_command_collision_blocks_install_without_writes(self):
        root = self.sandbox / "command-collision"
        root.mkdir()
        env = self.env.copy()
        env["OPENCODE_CONFIG_DIR"] = str(root)
        command = root / "commands/olympus.ultra.md"
        command.parent.mkdir()
        command.write_bytes(b"user-owned command bytes\n")
        before = self._global_files(root)

        result = self._engine(update=False, env=env)
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("GLOBAL_INSTALL_CONFLICT", result.stdout + result.stderr)
        self.assertEqual(before, self._global_files(root))
        self.assertFalse((root / "olympus/orchestrator-install.json").exists())

    def test_global_max_parallel_updates_only_global_kael_and_survives_update_verify(self):
        project = self._create_project()
        project_before = {
            path.relative_to(project).as_posix(): path.read_bytes()
            for path in project.rglob("*") if path.is_file()
        }
        env_patch = {"APPDATA": str(self.appdata), "LOCALAPPDATA": str(self.localappdata),
                     "USERPROFILE": str(self.profile), "OPENCODE_CONFIG_DIR": str(self.root),
                     "OLYMPUS_CONFIG_FILE": str(self.appdata / "Olympus/config.json")}
        with mock.patch.dict(os.environ, env_patch), contextlib.redirect_stdout(io.StringIO()):
            kael = next(row for row in user_config.effective_roles(ROOT) if row["role"] == "kael")
            self.assertEqual(0, main(["--source", str(ROOT), "config", "set-max-parallel", "2"]))
            self.assertEqual(0, main(["--source", str(ROOT), "kael", "set-model", kael["model"],
                                      "--scope", "global"]))
            self.assertEqual(0, main(["--source", str(ROOT), "kael", "set-effort", kael["effort"],
                                      "--scope", "global"]))

            settings = json.loads((self.appdata / "Olympus/config.json").read_text(encoding="utf-8"))
            self.assertEqual({"model": kael["model"], "effort": kael["effort"]}, settings["overrides"]["kael"])
            self.assertEqual({"max_children": 2}, settings["orchestration"])
            for role in ("kael", "atlas"):
                rendered = self._agent(role).read_text(encoding="utf-8")
                self.assertIn("MAX_ACTIVE_CHILDREN = 2", rendered)
                if role == "kael":
                    self.assertIn("adapt from zero to two children", rendered)
                    self.assertIn(f'model: "{kael["model"]}#{kael["effort"]}"', rendered)

        self.assertEqual(project_before, {
            path.relative_to(project).as_posix(): path.read_bytes()
            for path in project.rglob("*") if path.is_file()
        })
        updated = self._engine(update=True)
        self.assertEqual(0, updated.returncode, updated.stdout + updated.stderr)
        verified = self._verify_global()
        self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)
        self.assertIn("OLYMPUS_GLOBAL_VERIFY: opencode", verified.stdout)
        entries = {item["path"]: item["sha256"] for item in self._manifest()["managed_files"]}
        for role in ("kael", "atlas"):
            self.assertEqual(
                hashlib.sha256(self._agent(role).read_bytes()).hexdigest(), entries[f"agents/{role}.md"],
            )

        with mock.patch.dict(os.environ, env_patch):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--source", str(ROOT), "config", "apply", "--scope", "project",
                             "--target", str(project), "--harness", "opencode", "--dry-run", "--json"])
            self.assertEqual(0, code, output.getvalue())
            preview = json.loads(output.getvalue())
            self.assertEqual([".opencode/agents/atlas.md", ".opencode/agents/kael.md"],
                             [item["path"] for item in preview["data"]["changes"]])
            code = main(["--source", str(ROOT), "config", "apply", "--scope", "project",
                         "--target", str(project), "--harness", "opencode", "--execute"])
            self.assertEqual(0, code, output.getvalue())
        project_manifest = json.loads((project / ".opencode/orchestrator-install.json").read_text(encoding="utf-8"))
        project_entries = {item["path"]: item["sha256"] for item in project_manifest["managed_files"]}
        for role in ("kael", "atlas"):
            project_agent = project / f".opencode/agents/{role}.md"
            rendered = project_agent.read_text(encoding="utf-8")
            self.assertIn("MAX_ACTIVE_CHILDREN = 2", rendered)
            self.assertEqual(
                hashlib.sha256(project_agent.read_bytes()).hexdigest(),
                project_entries[f".opencode/agents/{role}.md"],
            )
            if role == "kael":
                self.assertIn("adapt from zero to two children", rendered)

    def test_global_max_parallel_primary_endpoints_and_partial_recovery_are_atomic(self):
        source = self.sandbox / "parallel-source"
        self._copy_global_source(source)

        global_root = self.sandbox / "parallel-global"
        global_root.mkdir()
        settings = self.sandbox / "parallel-appdata" / "Olympus" / "config.json"
        env = self.env.copy()
        env.update({
            "OPENCODE_CONFIG_DIR": str(global_root),
            "OLYMPUS_CONFIG_FILE": str(settings),
            "OLYMPUS_PYTHON": sys.executable,
        })
        installed = self._engine(update=False, env=env, source_root=source)
        self.assertEqual(0, installed.returncode, installed.stdout + installed.stderr)

        for value in (1, 8):
            output = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
                self.assertEqual(
                    0, main(["--source", str(source), "config", "set-max-parallel", str(value)]),
                    output.getvalue(),
                )
            preferences = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual({"max_children": value}, preferences["orchestration"])
            manifest = json.loads((global_root / "olympus/orchestrator-install.json").read_text(encoding="utf-8"))
            entries = {item["path"]: item["sha256"] for item in manifest["managed_files"]}
            for role in ("kael", "atlas"):
                agent = (global_root / f"agents/{role}.md").read_bytes()
                self.assertIn(f"MAX_ACTIVE_CHILDREN = {value}".encode(), agent)
                self.assertEqual(hashlib.sha256(agent).hexdigest(), entries[f"agents/{role}.md"])

        with mock.patch.dict(os.environ, env, clear=True):
            expected = global_readonly._expected(source, load_renderer(source), ("opencode",))
            user_config.apply_to_expected(source, expected["opencode"])
            for role in ("kael", "atlas"):
                self.assertEqual(
                    expected["opencode"][f"agents/{role}.md"],
                    (global_root / f"agents/{role}.md").read_bytes(),
                )

        before_root = self._global_files(global_root)
        before_settings = settings.read_bytes()
        for value in (0, 9):
            with self.subTest(invalid_value=value):
                with mock.patch.dict(os.environ, env, clear=True):
                    with self.assertRaisesRegex(user_config.UserConfigError, "integer from 1 to 8"):
                        user_config.set_max_children(source, value)
                self.assertEqual(before_root, self._global_files(global_root))
                self.assertEqual(before_settings, settings.read_bytes())

        publish = config_apply_transaction._settings_publish

        def stop_after_kael(*args, **kwargs):
            result = publish(*args, **kwargs)
            if args[4] == "agents/kael.md":
                raise KeyboardInterrupt("fixture interruption after first primary agent")
            return result

        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch("olympus.config_apply_transaction._settings_publish", side_effect=stop_after_kael):
                with self.assertRaises(KeyboardInterrupt):
                    user_config.set_max_children(source, 3)
        self.assertIn(b"MAX_ACTIVE_CHILDREN = 3", (global_root / "agents/kael.md").read_bytes())
        self.assertIn(b"MAX_ACTIVE_CHILDREN = 8", (global_root / "agents/atlas.md").read_bytes())
        self.assertEqual(before_settings, settings.read_bytes())
        self.assertTrue((global_root / ".olympus-cli-config-apply/record.json").is_file())

        output = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
            code = main([
                "--source", str(source), "config", "recover", "--scope", "global", "--harness", "opencode",
            ])
        self.assertEqual(0, code, output.getvalue())
        self.assertIn("Recovery: rolled_back", output.getvalue())
        self.assertEqual(before_root, self._global_files(global_root))
        self.assertEqual(before_settings, settings.read_bytes())
        self.assertFalse((global_root / ".olympus-cli-config-apply").exists())

    def test_global_nondefault_cap_preserves_lf_and_crlf_with_python_and_native_verification(self):
        source = self.sandbox / "newline-source"
        self._copy_global_source(source)
        kael_source = source / ".opencode/agents/kael.md"
        canonical_kael = kael_source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")

        for name, newline in (("lf", "\n"), ("crlf", "\r\n")):
            with self.subTest(newline=name):
                kael_source.write_bytes(canonical_kael.replace("\n", newline).encode("utf-8"))
                global_root = self.sandbox / f"newline-{name}" / "opencode"
                global_root.mkdir(parents=True)
                settings = self.sandbox / f"newline-{name}" / "Olympus/config.json"
                settings.parent.mkdir(parents=True)
                settings_bytes = (json.dumps({
                    "schema_version": 1,
                    "overrides": {"nox": {"model": "openai/gpt-6.1-sol", "effort": "high"}},
                    "orchestration": {"max_children": 2},
                }, indent=2) + "\n").encode("utf-8")
                settings.write_bytes(settings_bytes)
                env = self.env.copy()
                env.update({
                    "OPENCODE_CONFIG_DIR": str(global_root),
                    "OLYMPUS_CONFIG_FILE": str(settings),
                    "OLYMPUS_PYTHON": sys.executable,
                })

                installed = self._engine(update=False, env=env, source_root=source)
                self.assertEqual(0, installed.returncode, installed.stdout + installed.stderr)
                verified = self._verify_global(env, source_root=source)
                self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)

                with mock.patch.dict(os.environ, env, clear=True):
                    user_config.set_max_children(source, 2)
                with mock.patch.dict(os.environ, env, clear=True):
                    renderer = load_renderer(source)
                    default = global_readonly._expected(
                        source, renderer, ("opencode",), include_default_agent=True, max_children=4,
                    )
                    self.assertEqual(kael_source.read_bytes(), default["opencode"]["agents/kael.md"])
                    expected = global_readonly._expected(
                        source, renderer, ("opencode",), include_default_agent=True,
                    )
                    user_config.apply_to_expected(source, expected["opencode"])

                    installed_kael = (global_root / "agents/kael.md").read_bytes()
                    self.assertEqual(expected["opencode"]["agents/kael.md"], installed_kael)
                    self.assertIn(b"MAX_ACTIVE_CHILDREN = 2", installed_kael)
                    installed_atlas = (global_root / "agents/atlas.md").read_bytes()
                    self.assertEqual(expected["opencode"]["agents/atlas.md"], installed_atlas)
                    self.assertIn(b"MAX_ACTIVE_CHILDREN = 2", installed_atlas)
                    if newline == "\r\n":
                        self.assertIn(b"\r\n", installed_kael)
                        self.assertNotIn(b"\r\r\n", installed_kael)
                        self.assertNotIn(b"\n", installed_kael.replace(b"\r\n", b""))
                    else:
                        self.assertNotIn(b"\r\n", installed_kael)
                    installed_nox = (global_root / "agents/nox.md").read_bytes()
                    self.assertEqual(expected["opencode"]["agents/nox.md"], installed_nox)
                    self.assertIn(b'model: "openai/gpt-6.1-sol#high"', installed_nox)
                    self.assertEqual(settings_bytes, settings.read_bytes())
                    manifest = json.loads(
                        (global_root / "olympus/orchestrator-install.json").read_text(encoding="utf-8")
                    )
                for relative, raw in (
                    ("agents/kael.md", installed_kael),
                    ("agents/atlas.md", installed_atlas),
                    ("agents/nox.md", installed_nox),
                ):
                    entry = next(item for item in manifest["managed_files"] if item["path"] == relative)
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"])

    def test_global_max_parallel_refuses_pending_lock_and_managed_drift(self):
        settings = self.appdata / "Olympus/config.json"
        pending = self.root / ".olympus-cli-config-apply"
        pending.write_bytes(b"preserve pending evidence")
        before_root = self._global_files()
        with self.assertRaisesRegex(user_config.UserConfigError, "pending Olympus global"):
            user_config.set_max_children(ROOT, 2)
        self.assertEqual(before_root, self._global_files())
        self.assertFalse(settings.exists())
        pending.unlink()

        guard_intent = self.root / global_readonly._OPENCODE_GUARD_INTENT
        guard_intent.parent.mkdir(parents=True, exist_ok=True)
        guard_intent.write_bytes(b"{preserve guard intent")
        before_root = self._global_files()
        with self.assertRaisesRegex(user_config.UserConfigError, "OpenCode guard transaction is pending"):
            user_config.set_max_children(ROOT, 2)
        self.assertEqual(before_root, self._global_files())
        self.assertFalse(settings.exists())
        guard_intent.unlink()

        owner = self._start_global_lock_owner(self.root)
        try:
            before_root = self._global_files()
            with self.assertRaisesRegex(user_config.UserConfigError, "Stable lock is owned by another process"):
                user_config.set_max_children(ROOT, 2)
            self.assertEqual(before_root, self._global_files())
            self.assertFalse(settings.exists())
        finally:
            self._stop_global_lock_owner(owner)

        agent = self._agent("kael")
        original = agent.read_bytes()
        agent.write_bytes(original + b"\n# preserve drift\n")
        drifted = agent.read_bytes()
        before_manifest = self.manifest_path.read_bytes()
        with self.assertRaisesRegex(user_config.UserConfigError, "changed outside Olympus"):
            user_config.set_max_children(ROOT, 2)
        self.assertEqual(drifted, agent.read_bytes())
        self.assertEqual(before_manifest, self.manifest_path.read_bytes())
        self.assertFalse(settings.exists())

        agent.write_bytes(original)
        atlas = self._agent("atlas")
        atlas_original = atlas.read_bytes()
        atlas.write_bytes(atlas_original + b"\n# preserve Atlas drift\n")
        atlas_drifted = atlas.read_bytes()
        with self.assertRaisesRegex(user_config.UserConfigError, "changed outside Olympus"):
            user_config.set_max_children(ROOT, 2)
        self.assertEqual(original, agent.read_bytes())
        self.assertEqual(atlas_drifted, atlas.read_bytes())
        self.assertEqual(before_manifest, self.manifest_path.read_bytes())
        self.assertFalse(settings.exists())

    def test_global_max_parallel_rejects_junctioned_preferences_parent_on_single_file_writes(self):
        def quote(path: Path) -> str:
            return "'" + str(path).replace("'", "''") + "'"

        def make_junction(link: Path, target: Path) -> None:
            command = (
                f"$ErrorActionPreference='Stop'; "
                f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(target)} | Out-Null"
            )
            result = subprocess.run(
                [self.pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False,
            )
            if result.returncode:
                self.skipTest("Windows junction creation unavailable; linked-parent checks NOT RUN: "
                              + result.stdout + result.stderr)

        def remove_junction(link: Path) -> None:
            try:
                os.rmdir(link)
            except FileNotFoundError:
                pass

        config_only_root = self.sandbox / "single-file-config-only" / "opencode"
        config_only_parent = self.sandbox / "single-file-config-only-settings" / "Olympus"
        config_only_parent.parent.mkdir()
        config_only_target = self.sandbox / "single-file-config-only-target"
        config_only_target.mkdir()
        config_only_sentinel = config_only_target / "sentinel.txt"
        config_only_sentinel.write_bytes(b"harmless redirect sentinel\n")
        config_only_settings = config_only_parent / "config.json"
        make_junction(config_only_parent, config_only_target)
        config_only_env = self.env.copy()
        config_only_env.update({
            "OPENCODE_CONFIG_DIR": str(config_only_root),
            "OLYMPUS_CONFIG_FILE": str(config_only_settings),
        })
        try:
            with mock.patch.dict(os.environ, config_only_env, clear=True):
                with self.assertRaisesRegex(user_config.UserConfigError, "Global user configuration parent"):
                    user_config.set_max_children(ROOT, 3)
            self.assertFalse((config_only_target / "config.json").exists())
            self.assertEqual(b"harmless redirect sentinel\n", config_only_sentinel.read_bytes())
        finally:
            remove_junction(config_only_parent)

        aligned_parent = self.sandbox / "single-file-aligned-settings" / "Olympus"
        aligned_parent.parent.mkdir()
        aligned_target = self.sandbox / "single-file-aligned-target"
        aligned_target.mkdir()
        aligned_sentinel = aligned_target / "sentinel.txt"
        aligned_sentinel.write_bytes(b"harmless redirect sentinel\n")
        aligned_settings = aligned_parent / "config.json"
        make_junction(aligned_parent, aligned_target)
        aligned_env = self.env.copy()
        aligned_env["OLYMPUS_CONFIG_FILE"] = str(aligned_settings)
        agent, manifest = self._agent("nox"), self.manifest_path
        nox = next(row for row in user_config.effective_roles(ROOT) if row["role"] == "nox")
        aligned_agent = user_config._replace_agent_model(agent.read_bytes(), nox["model"], nox["effort"], "nox")
        agent.write_bytes(aligned_agent)
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        nox_receipt = next(item for item in manifest_data["managed_files"] if item["path"] == "agents/nox.md")
        nox_receipt["sha256"] = hashlib.sha256(aligned_agent).hexdigest()
        manifest.write_bytes((json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        before_agent, before_manifest = agent.read_bytes(), manifest.read_bytes()
        self.assertEqual(aligned_agent, user_config._replace_agent_model(
            agent.read_bytes(), nox["model"], nox["effort"], "nox",
        ))
        try:
            with mock.patch.dict(os.environ, aligned_env, clear=True):
                with self.assertRaisesRegex(user_config.UserConfigError, "Global user configuration parent"):
                    user_config.set_override(ROOT, "nox", "effort", nox["effort"])
            self.assertFalse((aligned_target / "config.json").exists())
            self.assertEqual(b"harmless redirect sentinel\n", aligned_sentinel.read_bytes())
            self.assertEqual(before_agent, agent.read_bytes())
            self.assertEqual(before_manifest, manifest.read_bytes())
        finally:
            remove_junction(aligned_parent)

        with mock.patch.dict(os.environ, aligned_env, clear=True):
            user_config.set_override(ROOT, "nox", "effort", nox["effort"])
        self.assertTrue(aligned_settings.is_file())
        self.assertEqual(before_agent, agent.read_bytes())
        self.assertEqual(before_manifest, manifest.read_bytes())

    def test_global_max_parallel_config_only_root_and_strict_global_project_schema(self):
        absent_root = self.sandbox / "config-only" / "opencode"
        settings = self.sandbox / "config-only-user" / "Olympus" / "config.json"
        env = self.env.copy()
        env.update({"OPENCODE_CONFIG_DIR": str(absent_root), "OLYMPUS_CONFIG_FILE": str(settings)})
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(4, user_config.max_children(ROOT))
            for value in (1, 4, 8):
                path, applied = user_config.set_max_children(ROOT, value)
                self.assertEqual(value, user_config.max_children(ROOT))
            self.assertEqual(settings.resolve(), path)
            self.assertFalse(applied)
        self.assertEqual([".olympus-cli-edit.lock"], sorted(item.name for item in absent_root.iterdir()))
        self.assertEqual({"max_children": 8}, json.loads(settings.read_text(encoding="utf-8"))["orchestration"])
        self.assertFalse((absent_root / "olympus/orchestrator-install.json").exists())

        valid = {"schema_version": 1, "overrides": {}, "orchestration": {"max_children": 1}}
        settings.write_text(json.dumps(valid), encoding="utf-8")
        with mock.patch.dict(os.environ, env, clear=True):
            listing = user_config.config_listing(ROOT, "project", self._create_project())
            diagnosis = user_config.diagnose(ROOT)
        self.assertEqual({"max_children": 1, "source": "GLOBAL", "path": str(settings.resolve())},
                         listing["max_parallel"])
        self.assertEqual(listing["max_parallel"], diagnosis["max_parallel"])

        invalid = (
            {"max_children": True}, {"max_children": "2"}, {"max_children": 2.0},
            {"max_children": 0}, {"max_children": 9}, {"max_children": 2, "extra": 1},
        )
        original = settings.read_bytes()
        for orchestration in invalid:
            with self.subTest(orchestration=orchestration):
                settings.write_text(json.dumps({**valid, "orchestration": orchestration}), encoding="utf-8")
                invalid_bytes = settings.read_bytes()
                with mock.patch.dict(os.environ, env, clear=True):
                    with self.assertRaises(user_config.UserConfigError):
                        user_config.max_children(ROOT)
                self.assertEqual(invalid_bytes, settings.read_bytes())
        settings.write_bytes(original)

        before_root = {path.relative_to(self.root).as_posix(): path.read_bytes()
                       for path in self.root.rglob("*") if path.is_file()}
        before_settings = settings.read_bytes()
        for invalid_value in ("0", "9", "2.0", "not-a-number"):
            output = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
                self.assertEqual(2, main(["--source", str(ROOT), "config", "set-max-parallel", invalid_value]))
            self.assertEqual(before_settings, settings.read_bytes())
            self.assertEqual(before_root, {
                path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()
            })

        project_config = self.sandbox / "strict-project" / ".opencode" / "olympus-config.json"
        project_config.parent.mkdir(parents=True)
        project_config.write_text(json.dumps(valid), encoding="utf-8")
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(user_config.UserConfigError):
                user_config.read_config(ROOT, "project", project_config.parent.parent)

        unsafe_env = env.copy()
        unsafe_env["OPENCODE_CONFIG_DIR"] = str(Path(self.sandbox.anchor))
        with mock.patch.dict(os.environ, unsafe_env, clear=True):
            with self.assertRaises(user_config.UserConfigError):
                user_config.set_max_children(ROOT, 3)
        self.assertEqual(original, settings.read_bytes())
        self.assertEqual([".olympus-cli-edit.lock"], sorted(item.name for item in absent_root.iterdir()))

    def test_global_override_preserves_current_fifteen_resource_user_config(self):
        root = self.sandbox / "global-user-config"
        root.mkdir()
        (root / "opencode.json").write_text(
            '{\n  "permissions": [\n'
            '    {"action": "external_directory", "resource": "*", "effect": "ask"}\n'
            '  ],\n  "user_setting": true\n}\n',
            encoding="utf-8",
        )
        settings = self.sandbox / "user-config-15" / "Olympus" / "config.json"
        env = self.env.copy()
        env.update({"OPENCODE_CONFIG_DIR": str(root), "OLYMPUS_CONFIG_FILE": str(settings)})
        installed = self._engine(update=False, env=env)
        self.assertEqual(0, installed.returncode, installed.stdout + installed.stderr)
        original_config = (root / "opencode.json").read_bytes()
        manifest_path = root / "olympus/orchestrator-install.json"
        manifest_before = manifest_path.read_bytes()
        manifest = json.loads(manifest_before)
        self.assertEqual(14, len(manifest["managed_files"]))
        self.assertNotIn("opencode.jsonc", {item["path"] for item in manifest["managed_files"]})

        with mock.patch.dict(os.environ, env, clear=True):
            path, applied = user_config.set_override(ROOT, "nox", "effort", "high")

        self.assertTrue(applied)
        self.assertEqual(settings.resolve(), path)
        self.assertEqual(original_config, (root / "opencode.json").read_bytes())
        self.assertIn(b'model: "openai/gpt-6-luna#high"', (root / "agents/nox.md").read_bytes())
        self.assertNotEqual(manifest_before, manifest_path.read_bytes())
        self.assertEqual({"schema_version": 1, "overrides": {"nox": {"effort": "high"}}},
                         json.loads(settings.read_text(encoding="utf-8")))

    def test_global_override_creates_only_lock_root_when_safe_root_is_absent(self):
        root = self.sandbox / "new-global" / "nested" / "opencode"
        settings = self.sandbox / "new-override" / "Olympus" / "config.json"
        env = self.env.copy()
        env.update({"OPENCODE_CONFIG_DIR": str(root), "OLYMPUS_CONFIG_FILE": str(settings)})
        with mock.patch.dict(os.environ, env, clear=True):
            path, applied = user_config.set_override(ROOT, "nox", "effort", "high")

        self.assertFalse(applied)
        self.assertEqual(settings.resolve(), path)
        self.assertEqual([".olympus-cli-edit.lock"], sorted(item.name for item in root.iterdir()))
        self.assertEqual(0, (root / ".olympus-cli-edit.lock").stat().st_size)
        self.assertFalse((root / "olympus/orchestrator-install.json").exists())
        self.assertEqual({"schema_version": 1, "overrides": {"nox": {"effort": "high"}}},
                         json.loads(settings.read_text(encoding="utf-8")))

    def test_global_override_fails_closed_for_unresolved_or_unsafe_root(self):
        settings = self.sandbox / "unresolved-override" / "Olympus" / "config.json"
        env = self.env.copy()
        env.pop("OPENCODE_CONFIG_DIR", None)
        env["OLYMPUS_CONFIG_FILE"] = str(settings)
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("olympus.global_readonly.shutil.which", return_value=None):
            with self.assertRaisesRegex(user_config.UserConfigError, "Cannot safely resolve the global OpenCode root"):
                user_config.set_override(ROOT, "nox", "effort", "high")
        self.assertFalse(settings.exists())

        blocker = self.sandbox / "not-a-directory"
        blocker.write_bytes(b"preserve")
        unsafe_root = blocker / "opencode"
        unsafe_settings = self.sandbox / "unsafe-override" / "Olympus" / "config.json"
        unsafe_env = self.env.copy()
        unsafe_env.update({"OPENCODE_CONFIG_DIR": str(unsafe_root),
                           "OLYMPUS_CONFIG_FILE": str(unsafe_settings)})
        with mock.patch.dict(os.environ, unsafe_env, clear=True):
            with self.assertRaisesRegex(user_config.UserConfigError, "Cannot safely resolve the global OpenCode root"):
                user_config.set_override(ROOT, "nox", "effort", "high")
        self.assertEqual(b"preserve", blocker.read_bytes())
        self.assertFalse(unsafe_settings.exists())
        self.assertFalse(unsafe_root.exists())

    def test_global_override_refuses_shared_powershell_lock_before_read_or_write(self):
        settings = self.appdata / "Olympus/config.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_bytes(b"{invalid user override")
        before_root = self._global_files()
        before_settings = settings.read_bytes()
        owner = self._start_global_lock_owner(self.root)
        try:
            with self.assertRaisesRegex(
                    user_config.UserConfigError,
                    "Cannot safely lock the global OpenCode root.*Stable lock is owned by another process"):
                user_config.set_override(ROOT, "nox", "effort", "high")
            self.assertEqual(before_root, self._global_files())
            self.assertEqual(before_settings, settings.read_bytes())
            self.assertTrue((self.root / source_edit._LOCK_NAME).is_file())
        finally:
            self._stop_global_lock_owner(owner)

    def test_global_override_refuses_pending_journals_and_unreadable_inspection(self):
        settings = self.appdata / "Olympus/config.json"
        for name in (".olympus-cli-config-apply", ".olympus-cli-edit"):
            with self.subTest(pending=name):
                pending = self.root / name
                pending.write_bytes(b"corrupt pending evidence")
                before_root, before_settings = self._global_files(), settings.read_bytes() if settings.exists() else None
                with self.assertRaisesRegex(user_config.UserConfigError, "pending Olympus global"):
                    user_config.set_override(ROOT, "nox", "effort", "high")
                self.assertEqual(before_root, self._global_files())
                self.assertEqual(before_settings, settings.read_bytes() if settings.exists() else None)
                self.assertEqual(b"corrupt pending evidence", pending.read_bytes())
                lock = source_edit._acquire_lock(self.root, create=False)
                source_edit._release_lock(lock)
                pending.unlink()

        unreadable = self.root / ".olympus-cli-config-apply"
        original_lstat = os.lstat

        def fail_pending_inspection(path, *args, **kwargs):
            if Path(path) == unreadable:
                raise PermissionError("controlled journal inspection failure")
            return original_lstat(path, *args, **kwargs)

        before_root, before_settings = self._global_files(), settings.read_bytes() if settings.exists() else None
        with mock.patch("olympus.config_apply_transaction.os.lstat", side_effect=fail_pending_inspection):
            with self.assertRaisesRegex(user_config.UserConfigError, "pending Olympus global"):
                user_config.set_override(ROOT, "nox", "effort", "high")
        self.assertEqual(before_root, self._global_files())
        self.assertEqual(before_settings, settings.read_bytes() if settings.exists() else None)
        self.assertFalse(unreadable.exists())

    def test_global_override_refuses_guard_intent_and_unreadable_marker(self):
        marker = self.root / global_readonly._OPENCODE_GUARD_INTENT
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_bytes(b"{corrupt guard intent")
        before_root = self._global_files()
        with self.assertRaisesRegex(user_config.UserConfigError, "OpenCode guard transaction is pending"):
            user_config.set_override(ROOT, "nox", "effort", "high")
        self.assertEqual(before_root, self._global_files())
        self.assertEqual(b"{corrupt guard intent", marker.read_bytes())
        marker.unlink()

        original_read = config_apply._read_target_file

        def fail_marker_read(root, relative, **kwargs):
            if relative == global_readonly._OPENCODE_GUARD_INTENT:
                return None, "controlled marker inspection failure"
            return original_read(root, relative, **kwargs)

        before_root = self._global_files()
        with mock.patch("olympus.config_apply._read_target_file", side_effect=fail_marker_read):
            with self.assertRaisesRegex(user_config.UserConfigError, "controlled marker inspection failure"):
                user_config.set_override(ROOT, "nox", "effort", "high")
        self.assertEqual(before_root, self._global_files())
        self.assertFalse(marker.exists())

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
        # Resolve the existing root before appending the journal path; Windows may expand an 8.3 alias.
        env["OLYMPUS_TEST_FAIL_INSPECTION"] = str(self.root.resolve(strict=True) / ".olympus-cli-config-apply")
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
