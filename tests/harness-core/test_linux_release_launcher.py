"""Offline trust-boundary tests for the Linux immutable-release coordinator."""

from __future__ import annotations

import base64
from contextlib import nullcontext
import gzip
import hashlib
import importlib.util
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "olympus_linux_release_launcher", ROOT / "scripts/launch-latest.py",
)
LAUNCHER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAUNCHER
SPEC.loader.exec_module(LAUNCHER)


class FakeTransport:
    def __init__(self, documents=None, blobs=None):
        self.documents = documents or {}
        self.blobs = blobs or {}
        self.urls = []

    def get(self, url: str, *, limit: int):
        self.urls.append(url)
        if url in self.documents:
            raw = self.documents[url]
        elif url in self.blobs:
            raw = self.blobs[url]
        else:
            raise AssertionError(f"Unexpected release request: {url}")
        if len(raw) > limit:
            raise AssertionError("Test fixture unexpectedly exceeds transport bound.")
        return url, raw


class LinuxReleaseLauncher(unittest.TestCase):
    def setUp(self):
        self.version = "v1.2.3"
        self.commit = "a" * 40
        self.tree_sha = "b" * 40
        self.release = LAUNCHER.Release(
            self.version, self.commit, self.tree_sha, "2020-01-01T00:00:00Z",
        )
        self.files = {}
        for path in LAUNCHER._RELEASE_FILES:
            if path == "install.ps1":
                content = (
                    f"[string]$Version = '{self.version}'\n"
                    f"$ReleaseVersion = '{self.version}'\n"
                ).encode()
            else:
                content = ("fixture payload: " + path + "\n").encode()
            self.files[path] = content
        self.hashes = {
            path: LAUNCHER._git_blob_sha(raw) for path, raw in self.files.items()
        }

    def _documents(self, *, release_changes=None, commit=None):
        release_value = {
            "immutable": True, "draft": False, "prerelease": False,
            "tag_name": self.version, "published_at": "2020-01-01T00:00:00Z",
        }
        release_value.update(release_changes or {})
        commit_value = {
            "sha": commit or self.commit,
            "commit": {"tree": {"sha": self.tree_sha}},
        }
        return {
            f"{LAUNCHER._API}/releases/latest": json.dumps(release_value).encode(),
            f"{LAUNCHER._API}/commits/{self.version}": json.dumps(commit_value).encode(),
        }

    def _tree_document(self):
        entries = [
            {"path": path, "type": "blob", "mode": "100644", "sha": digest}
            for path, digest in sorted(self.hashes.items())
        ]
        entries.append({
            "path": "README.md", "type": "blob", "mode": "100644", "sha": "c" * 40,
        })
        return json.dumps({
            "sha": self.tree_sha, "truncated": False, "tree": entries,
        }).encode()

    def _archive(self, *, extra=None, changes=None):
        root_name = f"{LAUNCHER._OWNER}-{LAUNCHER._REPOSITORY}-{self.commit[:7]}"
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            root = tarfile.TarInfo(root_name + "/")
            root.type = tarfile.DIRTYPE
            root.mode = 0o755
            archive.addfile(root)
            directories = set()
            for name in self.files:
                parts = name.split("/")[:-1]
                for index in range(1, len(parts) + 1):
                    directories.add("/".join(parts[:index]))
            for name in sorted(directories):
                entry = tarfile.TarInfo(root_name + "/" + name + "/")
                entry.type = tarfile.DIRTYPE
                entry.mode = 0o755
                archive.addfile(entry)
            contents = dict(self.files)
            contents.update(changes or {})
            for name, raw in sorted(contents.items()):
                entry = tarfile.TarInfo(root_name + "/" + name)
                entry.size = len(raw)
                entry.mode = 0o644
                archive.addfile(entry, io.BytesIO(raw))
            if extra is not None:
                archive.addfile(extra)
        return stream.getvalue()

    def _bootstrap_transport(self, *, include_tree=False, archive=False):
        self.files["scripts/launch-latest.py"] = (
            ROOT / "scripts" / "launch-latest.py"
        ).read_bytes()
        self.hashes = {
            path: LAUNCHER._git_blob_sha(raw) for path, raw in self.files.items()
        }
        documents = self._documents()
        launcher = self.files["scripts/launch-latest.py"]
        blob_sha = LAUNCHER._git_blob_sha(launcher)
        documents[f"{LAUNCHER._API}/contents/scripts/launch-latest.py?ref={self.commit}"] = json.dumps({
            "type": "file", "path": "scripts/launch-latest.py", "encoding": "base64",
            "size": len(launcher), "sha": blob_sha, "content": base64.b64encode(launcher).decode(),
            "html_url": (
                f"https://github.com/{LAUNCHER._OWNER}/{LAUNCHER._REPOSITORY}"
                f"/blob/{self.commit}/scripts/launch-latest.py"
            ),
        }).encode()
        blobs = {}
        if include_tree:
            documents[f"{LAUNCHER._API}/git/trees/{self.tree_sha}?recursive=1"] = self._tree_document()
        if archive:
            _, archive_url = LAUNCHER._archive_root_name(self.commit)
            blobs[archive_url] = self._archive()
        return FakeTransport(documents, blobs), (self.version, self.commit, blob_sha)

    def _write_current_package(self, home: Path):
        data_root = home / "data" / "olympus"
        package_root = data_root / "versions" / self.version
        package_root.mkdir(parents=True)
        for name, raw in self.files.items():
            path = package_root.joinpath(*name.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o444)
        receipt = b"fixture receipt\n"
        receipt_path = package_root / "olympus-cli-package.json"
        receipt_path.write_bytes(receipt)
        receipt_path.chmod(0o444)
        for directory in sorted(
            (path for path in package_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts), reverse=True,
        ):
            directory.chmod(0o555)
        package_root.chmod(0o555)
        current = (
            f"{self.version}\n{self.commit}\n{hashlib.sha256(receipt).hexdigest()}\n"
        ).encode()
        (data_root / "current").write_bytes(current)
        (data_root / "current").chmod(0o600)
        bin_root = home / ".local" / "bin"
        bin_root.mkdir(parents=True)
        (bin_root / "olympus").write_bytes(b"fixture launcher\n")
        (bin_root / "olympus").chmod(0o755)
        return data_root, package_root

    def _public_script_path(self, temporary: Path) -> Path:
        path = temporary / "launch-latest.py"
        path.write_bytes((ROOT / "scripts" / "launch-latest.py").read_bytes())
        return path

    def test_release_selection_requires_immutable_published_stable_identity(self):
        transport = FakeTransport(self._documents())
        self.assertEqual(self.release, LAUNCHER._select_latest(transport))
        self.assertEqual([
            f"{LAUNCHER._API}/releases/latest",
            f"{LAUNCHER._API}/commits/{self.version}",
        ], transport.urls)

        for changes in (
            {"immutable": False},
            {"draft": True},
            {"prerelease": True},
            {"tag_name": "v1.2.3-rc.1"},
            {"tag_name": "v01.2.3"},
            {"published_at": "2099-01-01T00:00:00Z"},
        ):
            with self.subTest(changes=changes):
                transport = FakeTransport(self._documents(release_changes=changes))
                with self.assertRaises(LAUNCHER.ReleaseError):
                    LAUNCHER._select_latest(transport)
                self.assertEqual(1, len(transport.urls), "invalid release must not resolve or fetch source")

        transport = FakeTransport(self._documents(commit="not-a-commit"))
        with self.assertRaisesRegex(LAUNCHER.ReleaseError, "full commit SHA"):
            LAUNCHER._select_latest(transport)

    def test_launcher_contents_are_bound_to_official_path_commit_and_git_blob(self):
        raw = b"official launcher fixture\n"
        blob_sha = LAUNCHER._git_blob_sha(raw)
        response = {
            "type": "file", "path": "scripts/launch-latest.py", "encoding": "base64",
            "size": len(raw), "sha": blob_sha, "content": base64.b64encode(raw).decode(),
            "html_url": (
                f"https://github.com/{LAUNCHER._OWNER}/{LAUNCHER._REPOSITORY}"
                f"/blob/{self.commit}/scripts/launch-latest.py"
            ),
        }
        url = f"{LAUNCHER._API}/contents/scripts/launch-latest.py?ref={self.commit}"
        transport = FakeTransport({url: json.dumps(response).encode()})
        self.assertEqual((raw, blob_sha), LAUNCHER._fetch_launcher(transport, self.release))

        response["path"] = "scripts/side-loaded.py"
        transport = FakeTransport({url: json.dumps(response).encode()})
        with self.assertRaisesRegex(LAUNCHER.ReleaseError, "expected launcher file"):
            LAUNCHER._fetch_launcher(transport, self.release)

    def test_bootstrap_transfer_rechecks_release_tuple_and_executing_blob(self):
        raw = b"isolated official launcher bytes\n"
        blob_sha = LAUNCHER._git_blob_sha(raw)
        url = f"{LAUNCHER._API}/contents/scripts/launch-latest.py?ref={self.commit}"
        metadata = {
            "type": "file", "path": "scripts/launch-latest.py", "encoding": "base64",
            "size": len(raw), "sha": blob_sha, "content": base64.b64encode(raw).decode(),
            "html_url": (
                f"https://github.com/{LAUNCHER._OWNER}/{LAUNCHER._REPOSITORY}"
                f"/blob/{self.commit}/scripts/launch-latest.py"
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "launch-latest.py"
            script.write_bytes(raw)
            transport = FakeTransport({url: json.dumps(metadata).encode()})
            LAUNCHER._verify_bootstrap(
                transport, self.release,
                (self.version, self.commit, blob_sha), script,
            )
            with self.assertRaisesRegex(LAUNCHER.ReleaseError, "changed after"):
                LAUNCHER._verify_bootstrap(
                    transport, self.release,
                    ("v9.9.9", self.commit, blob_sha), script,
                )
        self.assertEqual([url], transport.urls)

    def test_archive_stages_only_tree_verified_allowlisted_files(self):
        tree_url = f"{LAUNCHER._API}/git/trees/{self.tree_sha}?recursive=1"
        archive_url = (
            f"https://codeload.github.com/{LAUNCHER._OWNER}/{LAUNCHER._REPOSITORY}"
            f"/legacy.tar.gz/{self.commit}"
        )
        transport = FakeTransport(
            {tree_url: self._tree_document()},
            {archive_url: self._archive()},
        )
        tree = LAUNCHER._fetch_tree(transport, self.release)
        with tempfile.TemporaryDirectory() as temporary:
            source = LAUNCHER._download_source(
                transport, self.release, tree, Path(temporary),
            )
            files = {
                path.relative_to(source).as_posix()
                for path in source.rglob("*") if path.is_file()
            }
            self.assertEqual(LAUNCHER._RELEASE_FILES, files)
            self.assertEqual(self.files["install.ps1"], (source / "install.ps1").read_bytes())
            self.assertFalse((source / "README.md").exists())

    def test_archive_rejects_escape_links_and_git_tree_byte_mismatch(self):
        tree = dict(self.hashes)
        with tempfile.TemporaryDirectory() as temporary:
            for name, member in (
                ("escape", tarfile.TarInfo("../escape")),
                ("link", tarfile.TarInfo(
                    f"{LAUNCHER._OWNER}-{LAUNCHER._REPOSITORY}-{self.commit[:7]}/foreign-link"
                )),
            ):
                with self.subTest(member=name):
                    if name == "link":
                        member.type = tarfile.SYMTYPE
                        member.linkname = "outside"
                    else:
                        member.name = (
                            f"{LAUNCHER._OWNER}-{LAUNCHER._REPOSITORY}-{self.commit[:7]}/../escape"
                        )
                    raw = self._archive(extra=member)
                    with self.assertRaises(LAUNCHER.ReleaseError):
                        LAUNCHER._extract_archive(
                            raw, self.release, tree, Path(temporary) / name,
                        )

            changed = dict(self.files)
            changed["olympus/global_cli.py"] = b"tampered but parseable\n"
            with self.assertRaisesRegex(LAUNCHER.ReleaseError, "immutable Git tree"):
                LAUNCHER._extract_archive(
                    self._archive(changes=changed), self.release, tree,
                    Path(temporary) / "mismatch",
                )

    def test_release_inventory_matches_global_cli_allowlist_and_renderer_outputs(self):
        from olympus import global_cli
        from olympus.cli import load_renderer

        generated = global_cli._generated_paths(
            ROOT, load_renderer(ROOT), {Path(item).stem for item in global_cli._ROLE_INPUTS},
        )
        expected = set(global_cli._PACKAGE_INPUTS) | set(generated)
        self.assertEqual(expected, LAUNCHER._RELEASE_FILES)

    def test_update_current_identity_does_not_fetch_archive_or_tree(self):
        from olympus import global_cli

        version = __import__("olympus.cli", fromlist=["release_version"]).release_version(ROOT)
        commit = "d" * 40
        release_data = {
            f"{LAUNCHER._API}/releases/latest": json.dumps({
                "immutable": True, "draft": False, "prerelease": False,
                "tag_name": version, "published_at": "2020-01-01T00:00:00Z",
            }).encode(),
            f"{LAUNCHER._API}/commits/{version}": json.dumps({
                "sha": commit, "commit": {"tree": {"sha": self.tree_sha}},
            }).encode(),
        }
        transport = FakeTransport(release_data)
        identity = SimpleNamespace(version=version, commit=commit, package_root=ROOT)
        with (
            mock.patch.object(global_cli, "recorded_identity", return_value=identity),
            mock.patch.object(global_cli, "verify") as verify,
        ):
            response, code = LAUNCHER.run_action(
                "update", source_root=ROOT, transport=transport,
            )
        self.assertEqual(0, code)
        self.assertEqual("ok", response["result"])
        self.assertEqual([f"{LAUNCHER._API}/releases/latest",
                          f"{LAUNCHER._API}/commits/{version}"], transport.urls)
        verify.assert_called_once_with(version=version, commit=commit)

    def test_public_bootstrap_install_current_verified_identity_skips_archive(self):
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                transport, bootstrap = self._bootstrap_transport(include_tree=True)
                with tempfile.TemporaryDirectory() as temporary:
                    temporary_path = Path(temporary)
                    home = Path(temporary) / "home"
                    home.mkdir()
                    launcher_path = self._public_script_path(temporary_path)
                    _, package_root = self._write_current_package(home)
                    identity = SimpleNamespace(
                        version=self.version, commit=self.commit,
                        package_root=package_root, receipt_sha256="fixture",
                    )
                    global_cli = SimpleNamespace(
                        recorded_identity=mock.Mock(return_value=identity),
                        verify=mock.Mock(),
                    )
                    with (
                        mock.patch.object(Path, "home", return_value=home),
                        mock.patch.dict(os.environ, {
                            "XDG_DATA_HOME": str(home / "data"),
                            "OPENCODE_CONFIG_DIR": str(home / "config"),
                        }),
                        mock.patch.object(LAUNCHER, "__file__", str(launcher_path)),
                        mock.patch.object(
                            LAUNCHER, "_load_lifecycle", return_value=(global_cli, None, None),
                        ),
                    ):
                        response, code = LAUNCHER.run_action(
                            "install", dry_run=dry_run, bootstrap=bootstrap, transport=transport,
                        )
                self.assertEqual(0, code, response["data"]["native_stderr"])
                self.assertEqual("preview" if dry_run else "ok", response["result"])
                self.assertEqual("installed", response["data"]["installation_state"])
                self.assertIn(f"{LAUNCHER._API}/git/trees/{self.tree_sha}?recursive=1", transport.urls)
                self.assertFalse(any("codeload.github.com" in url for url in transport.urls))
                global_cli.recorded_identity.assert_called_once_with()
                global_cli.verify.assert_called_once_with(version=self.version, commit=self.commit)

    def test_public_bootstrap_install_mismatched_identity_blocks_before_tree_or_archive(self):
        transport, bootstrap = self._bootstrap_transport()
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            home = temporary_path / "home"
            data_root = home / "data" / "olympus"
            data_root.mkdir(parents=True)
            launcher_path = self._public_script_path(temporary_path)
            current = data_root / "current"
            current.write_text(
                f"v1.0.0\n{'e' * 40}\n{'f' * 64}\n", encoding="ascii",
            )
            current.chmod(0o600)
            bin_launcher = home / ".local" / "bin" / "olympus"
            bin_launcher.parent.mkdir(parents=True)
            bin_launcher.write_text("fixture\n", encoding="ascii")
            with (
                mock.patch.object(Path, "home", return_value=home),
                mock.patch.dict(os.environ, {
                    "XDG_DATA_HOME": str(home / "data"),
                    "OPENCODE_CONFIG_DIR": str(home / "config"),
                }),
                mock.patch.object(LAUNCHER, "__file__", str(launcher_path)),
                mock.patch.object(LAUNCHER, "_download_source") as download,
            ):
                response, code = LAUNCHER.run_action(
                    "install", bootstrap=bootstrap, transport=transport,
                )
        self.assertNotEqual(0, code)
        self.assertEqual("blocked", response["result"])
        self.assertFalse(any("/git/trees/" in url or "codeload.github.com" in url
                             for url in transport.urls))
        download.assert_not_called()

    def test_public_bootstrap_install_does_not_import_package_from_marker_alone(self):
        transport, bootstrap = self._bootstrap_transport(include_tree=True)
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            home = temporary_path / "home"
            home.mkdir()
            _, package_root = self._write_current_package(home)
            module = package_root / "olympus" / "global_cli.py"
            module.chmod(0o644)
            module.write_bytes(b"untrusted local module\n")
            module.chmod(0o444)
            launcher_path = self._public_script_path(temporary_path)
            with (
                mock.patch.object(Path, "home", return_value=home),
                mock.patch.dict(os.environ, {
                    "XDG_DATA_HOME": str(home / "data"),
                    "OPENCODE_CONFIG_DIR": str(home / "config"),
                }),
                mock.patch.object(LAUNCHER, "__file__", str(launcher_path)),
                mock.patch.object(LAUNCHER, "_load_lifecycle") as load_lifecycle,
                mock.patch.object(LAUNCHER, "_download_source") as download,
            ):
                response, code = LAUNCHER.run_action(
                    "install", bootstrap=bootstrap, transport=transport,
                )
        self.assertNotEqual(0, code)
        self.assertEqual("blocked", response["result"])
        self.assertIn("pinned Git tree", response["data"]["native_stderr"])
        self.assertFalse(any("codeload.github.com" in url for url in transport.urls))
        load_lifecycle.assert_not_called()
        download.assert_not_called()

    def test_public_bootstrap_install_partial_data_without_current_blocks(self):
        transport, bootstrap = self._bootstrap_transport()
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            home = temporary_path / "home"
            data_root = home / "data" / "olympus"
            data_root.mkdir(parents=True)
            (data_root / "uninstall-pending.json").write_text("pending", encoding="ascii")
            launcher_path = self._public_script_path(temporary_path)
            with (
                mock.patch.object(Path, "home", return_value=home),
                mock.patch.dict(os.environ, {
                    "XDG_DATA_HOME": str(home / "data"),
                    "OPENCODE_CONFIG_DIR": str(home / "config"),
                }),
                mock.patch.object(LAUNCHER, "__file__", str(launcher_path)),
            ):
                response, code = LAUNCHER.run_action(
                    "install", bootstrap=bootstrap, transport=transport,
                )
        self.assertNotEqual(0, code)
        self.assertEqual("blocked", response["result"])
        self.assertFalse(any("/git/trees/" in url or "codeload.github.com" in url
                             for url in transport.urls))

    def test_public_bootstrap_install_clean_absence_keeps_staged_dry_run(self):
        from olympus import cli

        self.version = cli.release_version(ROOT)
        self.commit = "d" * 40
        self.files = {
            path: (ROOT / Path(path)).read_bytes()
            for path in LAUNCHER._RELEASE_FILES
        }
        self.hashes = {
            path: LAUNCHER._git_blob_sha(raw) for path, raw in self.files.items()
        }
        transport, bootstrap = self._bootstrap_transport(include_tree=True, archive=True)
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            home = temporary_path / "home"
            home.mkdir()
            launcher_path = self._public_script_path(temporary_path)
            source_validation = (
                nullcontext() if hasattr(os, "geteuid")
                else mock.patch.object(LAUNCHER, "_validate_source")
            )
            with (
                mock.patch.object(Path, "home", return_value=home),
                mock.patch.dict(os.environ, {
                    "XDG_DATA_HOME": str(home / "data"),
                    "OPENCODE_CONFIG_DIR": str(home / "config"),
                }),
                mock.patch.object(LAUNCHER, "__file__", str(launcher_path)),
                mock.patch.object(LAUNCHER, "_change_plan", return_value=[]),
                source_validation,
            ):
                response, code = LAUNCHER.run_action(
                    "install", dry_run=True, bootstrap=bootstrap, transport=transport,
                    temp_parent=Path(temporary),
                )
        self.assertEqual(0, code, response["data"]["native_stderr"])
        self.assertEqual("preview", response["result"])
        self.assertIn(f"{LAUNCHER._API}/git/trees/{self.tree_sha}?recursive=1", transport.urls)
        self.assertTrue(any("codeload.github.com" in url for url in transport.urls))


if __name__ == "__main__":
    unittest.main()
