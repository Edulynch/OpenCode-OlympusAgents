import argparse
import base64
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
import re
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock
import urllib.error
import urllib.parse


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("olympus_release", ROOT / ".github/release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def promotion_fixture():
    sha = "a" * 40
    before = "b" * 40
    head_sha = "c" * 40
    event = {
        "repository": {"full_name": release.REPOSITORY},
        "ref": "refs/heads/master",
        "before": before,
        "after": sha,
        "created": False,
        "deleted": False,
        "forced": False,
    }
    pr = {
        "number": 12,
        "state": "closed",
        "merged_at": "2026-01-01T00:00:00Z",
        "merge_commit_sha": sha,
        "base": {
            "ref": "master",
            "repo": {"full_name": release.REPOSITORY},
        },
        "head": {
            "ref": "develop",
            "sha": head_sha,
            "repo": {"full_name": release.REPOSITORY},
        },
    }
    return event, sha, before, head_sha, pr


def assert_reason(test, reason, callback):
    with test.assertRaisesRegex(release.ReleaseError, reason):
        callback()


def extract_tag_guard_script():
    text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    job = re.search(r"(?ms)^  tag:\n(?P<body>.*?)(?=^  [a-z][a-z-]*:\n|\Z)", text)
    if job is None:
        raise AssertionError("release tag job is missing")
    script = re.search(
        r"(?ms)^          python3 - <<'PY'\r?\n(?P<body>.*?)^          PY[ \t]*\r?$",
        job.group("body"),
    )
    if script is None:
        raise AssertionError("release tag guard heredoc is missing")
    return textwrap.dedent(script.group("body"))


def extract_promotion_guard_script():
    text = (ROOT / ".github/workflows/promotion-guard.yml").read_text(encoding="utf-8")
    script = re.search(
        r"(?ms)^          python3 - <<'PY'\r?\n(?P<body>.*?)^          PY[ \t]*\r?$",
        text,
    )
    if script is None:
        raise AssertionError("promotion guard heredoc is missing")
    return textwrap.dedent(script.group("body"))


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.payload


class PromotionSourceTests(unittest.TestCase):
    def test_exact_same_repository_develop_merge_is_accepted(self):
        event, sha, before, head_sha, pr = promotion_fixture()
        accepted = release.validate_promotion(
            event, release.REPOSITORY, sha, [before, head_sha], [pr], sha
        )
        self.assertEqual(accepted["number"], 12)

    def test_rejects_wrong_repository_ref_and_push_flags(self):
        event, sha, before, head_sha, pr = promotion_fixture()
        assert_reason(
            self,
            "REPOSITORY_MISMATCH",
            lambda: release.validate_promotion(event, "attacker/fork", sha, [before, head_sha], [pr], sha),
        )
        wrong_ref = {**event, "ref": "refs/heads/develop"}
        assert_reason(
            self,
            "PUSH_REF_INVALID",
            lambda: release.validate_promotion(wrong_ref, release.REPOSITORY, sha, [before, head_sha], [pr], sha),
        )
        forced = {**event, "forced": True}
        assert_reason(
            self,
            "PUSH_NOT_FAST_FORWARD",
            lambda: release.validate_promotion(forced, release.REPOSITORY, sha, [before, head_sha], [pr], sha),
        )
        deleted = {**event, "deleted": True}
        assert_reason(
            self,
            "PUSH_NOT_FAST_FORWARD",
            lambda: release.validate_promotion(deleted, release.REPOSITORY, sha, [before, head_sha], [pr], sha),
        )
        created = {**event, "created": True}
        assert_reason(
            self,
            "PUSH_CREATED_REF",
            lambda: release.validate_promotion(created, release.REPOSITORY, sha, [before, head_sha], [pr], sha),
        )
        wrong_after = {**event, "after": "d" * 40}
        assert_reason(
            self,
            "PUSH_SHA_MISMATCH",
            lambda: release.validate_promotion(wrong_after, release.REPOSITORY, sha, [before, head_sha], [pr], sha),
        )

    def test_rejects_fork_source_wrong_pr_sha_and_parent_order(self):
        event, sha, before, head_sha, pr = promotion_fixture()
        fork_pr = {**pr, "head": {**pr["head"], "repo": {"full_name": "other/fork"}}}
        assert_reason(
            self,
            "PROMOTION_SOURCE_INVALID",
            lambda: release.validate_promotion(event, release.REPOSITORY, sha, [before, head_sha], [fork_pr], sha),
        )
        wrong_pr = {**pr, "merge_commit_sha": "d" * 40}
        assert_reason(
            self,
            "PROMOTION_PR_AMBIGUOUS",
            lambda: release.validate_promotion(event, release.REPOSITORY, sha, [before, head_sha], [wrong_pr], sha),
        )
        assert_reason(
            self,
            "MERGE_PARENTS_INVALID",
            lambda: release.validate_promotion(event, release.REPOSITORY, sha, [head_sha, before], [pr], sha),
        )
        assert_reason(
            self,
            "STALE_MASTER_SHA",
            lambda: release.validate_promotion(event, release.REPOSITORY, sha, [before, head_sha], [pr], "e" * 40),
        )

    def test_rejects_ambiguous_exact_merge_prs(self):
        event, sha, before, head_sha, pr = promotion_fixture()
        assert_reason(
            self,
            "PROMOTION_PR_AMBIGUOUS",
            lambda: release.validate_promotion(event, release.REPOSITORY, sha, [before, head_sha], [pr, pr], sha),
        )


class CandidatePolicyTests(unittest.TestCase):
    def setUp(self):
        self.version = "v1.2.3"
        self.sha = "a" * 40
        self.body = "reviewed notes"
        self.assets = {
            "install-olympus.ps1": "1" * 64,
            "install-olympus.sh": "2" * 64,
        }
        self.tag_ref = {
            "ref": f"refs/tags/{self.version}",
            "object": {"type": "tag", "sha": "f" * 40},
        }
        self.tag_object = {
            "tag": self.version,
            "message": release.tag_message(self.version, self.sha),
            "tagger": {"name": release.BOT_NAME, "email": release.BOT_EMAIL},
            "object": {"type": "commit", "sha": self.sha},
        }
        self.draft = {
            "tag_name": self.version,
            "name": self.version,
            "body": self.body,
            "draft": True,
            "prerelease": False,
            "author": {"login": release.BOT_NAME},
            "published_at": None,
            "assets": [
                {"name": name, "digest": f"sha256:{digest}"}
                for name, digest in self.assets.items()
            ],
        }

    def classify(self, **updates):
        values = {
            "version_before": "v1.2.2",
            "version_after": self.version,
            "latest_release": {"tag_name": "v1.2.2"},
            "tag_ref": self.tag_ref,
            "tag_object": self.tag_object,
            "release": self.draft,
            "sha": self.sha,
            "body": self.body,
            "expected_assets": self.assets,
        }
        values.update(updates)
        return release.classify_existing_release(**values)

    def test_unchanged_version_is_noop_even_with_historical_tag(self):
        self.assertEqual(
            self.classify(
                version_before=self.version,
                latest_release={"tag_name": "v9.9.9"},
                tag_ref={"ref": "refs/tags/v1.2.3", "object": {"type": "commit", "sha": "d" * 40}},
            ),
            "noop",
        )

    def test_requires_increasing_version_and_newer_than_latest(self):
        assert_reason(
            self,
            "RELEASE_VERSION_NOT_INCREASING",
            lambda: self.classify(version_before="v1.2.4"),
        )
        assert_reason(
            self,
            "RELEASE_VERSION_NOT_LATEST",
            lambda: self.classify(latest_release={"tag_name": "v1.2.4"}),
        )
        self.assertEqual(self.classify(tag_ref=None, tag_object=None, release=None), "create")

    def test_conflicting_tag_target_and_orphan_tag_fail_closed(self):
        wrong_tag = {**self.tag_object, "object": {"type": "commit", "sha": "d" * 40}}
        assert_reason(
            self,
            "TAG_CONFLICT",
            lambda: self.classify(tag_object=wrong_tag),
        )
        assert_reason(
            self,
            "ORPHAN_TAG_CONFLICT",
            lambda: self.classify(release=None),
        )

    def test_matching_draft_resumes_but_wrong_asset_digest_does_not(self):
        self.assertEqual(self.classify(), "resume")
        bad_draft = {**self.draft, "assets": [
            {"name": "install-olympus.ps1", "digest": "sha256:" + "0" * 64}
        ]}
        assert_reason(
            self,
            "RELEASE_ASSET_CONFLICT",
            lambda: self.classify(release=bad_draft),
        )

    def test_published_release_requires_immutable_complete_latest_state(self):
        public = {
            **self.draft,
            "draft": False,
            "immutable": True,
            "published_at": "2026-01-01T00:00:00Z",
        }
        self.assertEqual(self.classify(release=public, latest_release={"tag_name": self.version}), "published")
        assert_reason(
            self,
            "PUBLISHED_RELEASE_CONFLICT",
            lambda: self.classify(
                release={**public, "immutable": False},
                latest_release={"tag_name": self.version},
            ),
        )

    def test_immutability_setting_uses_explicit_fallback_only_on_auth_denial(self):
        self.assertEqual(release.check_immutable_setting(200, {"enabled": True}, ""), "api")
        self.assertEqual(release.check_immutable_setting(403, None, "true"), "owner-precondition")
        assert_reason(
            self,
            "IMMUTABILITY_DISABLED",
            lambda: release.check_immutable_setting(200, {"enabled": False}, "true"),
        )
        assert_reason(
            self,
            "IMMUTABILITY_DISABLED",
            lambda: release.check_immutable_setting(404, None, "true"),
        )
        assert_reason(
            self,
            "IMMUTABILITY_UNVERIFIED",
            lambda: release.check_immutable_setting(403, None, ""),
        )

    def test_markers_and_notes_are_candidate_specific(self):
        installer = "[string]$Version = 'v1.2.3'\n$ReleaseVersion = 'v1.2.3'\n"
        self.assertEqual(release.extract_release_version(installer, "test"), "v1.2.3")
        assert_reason(
            self,
            "RELEASE_MARKERS_MISMATCH",
            lambda: release.extract_release_version(installer.replace("$ReleaseVersion = 'v1.2.3'", "$ReleaseVersion = 'v1.2.4'"), "test"),
        )
        notes = (
            "# Release notes\n\n## v1.2.3\n\n### Highlights\nok\n\n"
            "### Capability limits\nok\n\n## Installation\nok\n\n"
            "## Verify installation\nok\n\n## v1.2.2\nold\n"
        )
        self.assertIn("## v1.2.3", release.extract_release_notes(notes, "v1.2.3"))


class HostedReadOnlyQualificationTests(unittest.TestCase):
    def setUp(self):
        self.develop_sha = "a" * 40
        self.master_sha = "b" * 40
        self.previous_sha = "c" * 40
        self.source_sha = "d" * 40
        self.tag_object_sha = "e" * 40
        self.version = "v1.2.3"
        self.pr = {
            "number": 42,
            "state": "closed",
            "merged_at": "2026-01-01T00:00:00Z",
            "merge_commit_sha": self.master_sha,
            "base": {
                "ref": "master",
                "repo": {"full_name": release.REPOSITORY},
            },
            "head": {
                "ref": "develop",
                "sha": self.source_sha,
                "repo": {"full_name": release.REPOSITORY},
            },
        }
        installer = (
            f"[string]$Version = '{self.version}'\n"
            f"$ReleaseVersion = '{self.version}'\n"
        ).encode()
        content = base64.b64encode(installer).decode()
        self.responses = {
            "/git/ref/heads/develop": {"object": {"sha": self.develop_sha}},
            "/git/ref/heads/master": {"object": {"sha": self.master_sha}},
            f"/commits/{self.master_sha}": {
                "sha": self.master_sha,
                "parents": [
                    {"sha": self.previous_sha},
                    {"sha": self.source_sha},
                ],
            },
            f"/commits/{self.master_sha}/pulls?per_page=100": [self.pr],
            f"/contents/install.ps1?ref={self.previous_sha}": {
                "type": "file",
                "encoding": "base64",
                "content": content,
            },
            f"/contents/install.ps1?ref={self.master_sha}": {
                "type": "file",
                "encoding": "base64",
                "content": content,
            },
            "/releases/latest": {
                "tag_name": self.version,
                "draft": False,
                "prerelease": False,
            },
            f"/git/ref/tags/{self.version}": {
                "ref": f"refs/tags/{self.version}",
                "object": {"type": "tag", "sha": self.tag_object_sha},
            },
            f"/git/tags/{self.tag_object_sha}": {
                "tag": self.version,
                "message": release.tag_message(self.version, self.previous_sha),
                "tagger": {"name": release.BOT_NAME, "email": release.BOT_EMAIL},
                "object": {"type": "commit", "sha": self.previous_sha},
            },
        }
        self.calls = []

    def env(self):
        return {
            "GITHUB_REPOSITORY": release.REPOSITORY,
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/develop",
            "GITHUB_WORKFLOW_REF": (
                f"{release.REPOSITORY}/.github/workflows/"
                "release-qualification.yml@refs/heads/develop"
            ),
            "GITHUB_SHA": self.develop_sha,
            "GITHUB_TOKEN": "offline-test-token",
            "OLYMPUS_RELEASE_ENABLED": "false",
        }

    def fake_urlopen(self, request, timeout):
        self.calls.append((request.get_method(), request.data, request.full_url))
        if request.get_method() != "GET" or request.data is not None:
            raise AssertionError("read-only client attempted a non-GET or request body")
        if timeout != 30:
            raise AssertionError(f"unexpected API timeout: {timeout}")
        parsed = urllib.parse.urlparse(request.full_url)
        route = parsed.path.removeprefix(f"/repos/{release.REPOSITORY}")
        if parsed.query:
            route += "?" + parsed.query
        if route not in self.responses:
            raise AssertionError(f"unexpected API read: {route}")
        return FakeResponse(self.responses[route])

    def run_qualification(self, env=None):
        output = io.StringIO()
        with (
            mock.patch.dict(os.environ, self.env() if env is None else env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=self.fake_urlopen),
            redirect_stdout(output),
        ):
            release.qualify_hosted_readonly(argparse.Namespace())
        return output.getvalue()

    def test_mocked_master_noop_and_existing_tag_conflict_use_get_only_client(self):
        client = release.ReadOnlyGitHub("offline-test-token")
        self.assertFalse(hasattr(client, "request"))
        self.assertFalse(hasattr(client, "post"))

        output = self.run_qualification()

        self.assertIn(
            f"HOSTED_READ_ONLY_NOOP: master_sha={self.master_sha} "
            f"version={self.version} previous_version={self.version} promotion_pr=#42",
            output,
        )
        self.assertIn(
            f"HOSTED_TAG_CONFLICT_CONFIRMED: tag={self.version} "
            f"target={self.previous_sha} current_master={self.master_sha} "
            "predicate=TAG_CONFLICT",
            output,
        )
        self.assertIn("draft write visibility", output)
        self.assertTrue(self.calls)
        self.assertTrue(all(method == "GET" and body is None for method, body, _ in self.calls))

    def test_changed_master_version_is_not_reported_as_noop_or_tag_conflict(self):
        content = base64.b64encode(
            b"[string]$Version = 'v1.2.4'\n$ReleaseVersion = 'v1.2.4'\n"
        ).decode()
        self.responses[f"/contents/install.ps1?ref={self.master_sha}"]["content"] = content
        output = io.StringIO()
        with (
            mock.patch.dict(os.environ, self.env(), clear=True),
            mock.patch("urllib.request.urlopen", side_effect=self.fake_urlopen),
            redirect_stdout(output),
        ):
            with self.assertRaisesRegex(
                release.ReleaseError, "HOSTED_RELEASE_NOOP_NOT_CONFIRMED"
            ):
                release.qualify_hosted_readonly(argparse.Namespace())
        self.assertEqual(output.getvalue(), "")
        self.assertFalse(any("/releases/latest" in url for _, _, url in self.calls))
        self.assertTrue(all(method == "GET" and body is None for method, body, _ in self.calls))

    def test_tag_matching_master_fails_closed_as_not_evaluated(self):
        tag_object = self.responses[f"/git/tags/{self.tag_object_sha}"]
        tag_object["object"]["sha"] = self.master_sha
        tag_object["message"] = release.tag_message(self.version, self.master_sha)
        output = io.StringIO()
        with (
            mock.patch.dict(os.environ, self.env(), clear=True),
            mock.patch("urllib.request.urlopen", side_effect=self.fake_urlopen),
            redirect_stdout(output),
        ):
            with self.assertRaisesRegex(
                release.ReleaseError, "TAG_CONFLICT_NOT_EVALUATED"
            ):
                release.qualify_hosted_readonly(argparse.Namespace())
        self.assertEqual(output.getvalue(), "")
        self.assertTrue(all(method == "GET" and body is None for method, body, _ in self.calls))

    def test_release_opt_in_must_be_false_before_api_access(self):
        env = self.env()
        env["OLYMPUS_RELEASE_ENABLED"] = "true"
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("urllib.request.urlopen") as urlopen,
        ):
            with self.assertRaisesRegex(
                release.ReleaseError, "RELEASE_OPT_IN_NOT_DISABLED"
            ):
                release.qualify_hosted_readonly(argparse.Namespace())
        urlopen.assert_not_called()


class PreTagReleaseConflictTests(unittest.TestCase):
    def test_prepare_queries_release_without_tag_and_refuses_before_planning(self):
        event, sha, before, head_sha, pr = promotion_fixture()
        version_before, version_after = "v1.2.2", "v1.2.3"
        with tempfile.TemporaryDirectory() as temp:
            event_path = Path(temp) / "event.json"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            out_dir = Path(temp) / "plan"

            class FakeReadApi:
                def __init__(self):
                    self.reads = []

                def get(self, path, *, optional=False):
                    self.reads.append(path)
                    if path == "/git/ref/heads/master":
                        return {"object": {"sha": sha}}
                    if path == f"/commits/{sha}/pulls?per_page=100":
                        return [pr]
                    if path == "/releases/latest":
                        return {"tag_name": version_before}
                    if path == f"/git/ref/tags/{version_after}":
                        return None
                    if path == f"/releases/tags/{version_after}":
                        return {"tag_name": version_after, "draft": True}
                    raise AssertionError(f"unexpected API read: {path}")

                def request(self, method, path):
                    self.reads.append(path)
                    if (method, path) == ("GET", "/immutable-releases"):
                        return 200, {"enabled": True}
                    raise AssertionError(f"unexpected API request: {method} {path}")

            api = FakeReadApi()

            def fake_git(command, **_):
                if command[1:] == ["rev-parse", "HEAD"]:
                    stdout = f"{sha}\n"
                elif command[1:] == ["show", "-s", "--format=%P", sha]:
                    stdout = f"{before} {head_sha}\n"
                else:
                    raise AssertionError(f"unexpected git command: {command}")
                return type("Result", (), {"stdout": stdout})()

            def fake_git_bytes(revision, path):
                if path == "install.ps1":
                    version = version_before if revision == before else version_after
                    return (
                        f"[string]$Version = '{version}'\n"
                        f"$ReleaseVersion = '{version}'\n"
                    ).encode()
                if path == "CHANGELOG.md":
                    return (
                        f"# Release notes\n## {version_after}\n"
                        "### Highlights\nok\n### Capability limits\nok\n"
                        "## Installation\nok\n## Verify installation\nok\n"
                    ).encode()
                if path in release.ASSET_PATHS.values():
                    return b"candidate installer"
                raise AssertionError(f"unexpected source read: {revision}:{path}")

            env = {
                "GITHUB_REPOSITORY": release.REPOSITORY,
                "GITHUB_SHA": sha,
                "GITHUB_REF": "refs/heads/master",
                "GITHUB_TOKEN": "offline-test-token",
                "GITHUB_OUTPUT": "",
                "OLYMPUS_RELEASE_ENABLED": "true",
            }
            with (
                mock.patch.dict(os.environ, env),
                mock.patch.object(release, "GitHub", return_value=api),
                mock.patch.object(release.subprocess, "run", side_effect=fake_git),
                mock.patch.object(release, "git_bytes", side_effect=fake_git_bytes),
            ):
                assert_reason(
                    self,
                    "RELEASE_WITHOUT_TAG",
                    lambda: release.prepare(
                        argparse.Namespace(event=str(event_path), out_dir=str(out_dir))
                    ),
                )

            self.assertIn(f"/releases/tags/{version_after}", api.reads)
            self.assertFalse(out_dir.exists())

    def test_write_enabled_tag_guard_refuses_release_without_ref_before_any_write(self):
        version = "v1.2.3"
        sha = "a" * 40
        root_path = f"/repos/{release.REPOSITORY}"
        tag_path = f"/git/ref/tags/{version}"
        release_path = f"/releases/tags/{version}"
        calls = []

        def fake_urlopen(request, timeout):
            path = urllib.parse.urlparse(request.full_url).path.removeprefix(root_path)
            method = request.get_method()
            calls.append((method, path))
            if (method, path) == ("GET", "/immutable-releases"):
                return FakeResponse({"enabled": True})
            if (method, path) == ("GET", "/git/ref/heads/master"):
                return FakeResponse({"object": {"sha": sha}})
            if (method, path) == ("GET", tag_path):
                raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, None)
            if (method, path) == ("GET", release_path):
                return FakeResponse({"tag_name": version, "draft": True})
            raise AssertionError(f"unexpected API operation: {method} {path}")

        env = {
            "REPOSITORY": release.REPOSITORY,
            "GITHUB_TOKEN": "offline-test-token",
            "RELEASE_VERSION": version,
            "RELEASE_SHA": sha,
            "RELEASE_MODE": "create",
            "OLYMPUS_RELEASE_ENABLED": "true",
            "OLYMPUS_RELEASE_IMMUTABILITY_CONFIRMED": "",
        }
        with mock.patch.dict(os.environ, env), mock.patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            with self.assertRaisesRegex(SystemExit, "RELEASE_WITHOUT_TAG"):
                exec(compile(extract_tag_guard_script(), "release.yml:tag-guard", "exec"), {})

        self.assertIn(("GET", release_path), calls)
        self.assertLess(calls.index(("GET", tag_path)), calls.index(("GET", release_path)))
        self.assertFalse(any(method == "POST" for method, _ in calls), calls)


class PublicAssetVerificationTests(unittest.TestCase):
    def setUp(self):
        self.version = "v1.2.3"
        self.contents = {
            "install-olympus.ps1": b"windows installer",
            "install-olympus.sh": b"linux installer",
        }
        self.expected = {name: release.sha256(content) for name, content in self.contents.items()}
        self.assets = [
            {
                "name": name,
                "digest": f"sha256:{self.expected[name]}",
                "browser_download_url": (
                    f"https://github.com/{release.REPOSITORY}/releases/download/"
                    f"{self.version}/{name}"
                ),
            }
            for name in self.contents
        ]

    def test_exact_canonical_asset_urls_and_bytes_are_required(self):
        with mock.patch.object(
            release, "_download_public_asset", side_effect=lambda url: self.contents[url.rsplit("/", 1)[-1]]
        ) as download:
            release._verify_release_assets(
                {"assets": self.assets}, self.expected, public=True, version=self.version
            )
        self.assertEqual(download.call_count, 2)

        wrong_url_assets = [dict(asset) for asset in self.assets]
        wrong_url_assets[0]["browser_download_url"] = (
            "https://example.invalid/" + wrong_url_assets[0]["name"]
        )
        with mock.patch.object(release, "_download_public_asset") as download:
            assert_reason(
                self,
                "PUBLIC_ASSET_URL_INVALID",
                lambda: release._verify_release_assets(
                    {"assets": wrong_url_assets}, self.expected, public=True, version=self.version
                ),
            )
            download.assert_not_called()

        with mock.patch.object(release, "_download_public_asset", return_value=b"modified bytes"):
            assert_reason(
                self,
                "PUBLIC_ASSET_BYTES_MISMATCH",
                lambda: release._verify_release_assets(
                    {"assets": self.assets}, self.expected, public=True, version=self.version
                ),
            )


class PromotionGuardEventPathTests(unittest.TestCase):
    def test_runner_event_path_is_read_and_workflow_ref_is_logged_without_api_use(self):
        with tempfile.TemporaryDirectory() as temp:
            event_path = Path(temp) / "event.json"
            event_path.write_text(
                json.dumps({"pull_request": {"head": {"sha": "invalid"}}}),
                encoding="utf-8",
            )
            output = io.StringIO()
            env = {
                "GITHUB_EVENT_PATH": str(event_path),
                "GITHUB_WORKFLOW_REF": (
                    "Edulynch/OpenCode-OlympusAgents/"
                    ".github/workflows/promotion-guard.yml@refs/heads/master"
                ),
            }
            with (
                mock.patch.dict(os.environ, env, clear=True),
                mock.patch("urllib.request.urlopen") as urlopen,
                redirect_stdout(output),
            ):
                with self.assertRaisesRegex(SystemExit, "PROMOTION_HEAD_SHA_INVALID"):
                    exec(compile(extract_promotion_guard_script(), "promotion-guard.yml", "exec"), {})

            self.assertIn("PROMOTION_WORKFLOW_REF: " + env["GITHUB_WORKFLOW_REF"], output.getvalue())
            urlopen.assert_not_called()

    def test_missing_or_unreadable_runner_event_path_fails_closed_without_api_use(self):
        with tempfile.TemporaryDirectory() as temp:
            missing_file = str(Path(temp) / "missing-event.json")
            for env, reason in (
                ({"GITHUB_WORKFLOW_REF": "workflow-ref"}, "PROMOTION_EVENT_PATH_MISSING"),
                (
                    {
                        "GITHUB_EVENT_PATH": missing_file,
                        "GITHUB_WORKFLOW_REF": "workflow-ref",
                    },
                    "PROMOTION_EVENT_PATH_UNREADABLE",
                ),
            ):
                with (
                    self.subTest(reason=reason),
                    mock.patch.dict(os.environ, env, clear=True),
                    mock.patch("urllib.request.urlopen") as urlopen,
                    redirect_stdout(io.StringIO()),
                ):
                    with self.assertRaisesRegex(SystemExit, reason):
                        exec(compile(extract_promotion_guard_script(), "promotion-guard.yml", "exec"), {})
                    urlopen.assert_not_called()


class WorkflowBoundaryTests(unittest.TestCase):
    def test_contributor_workflows_cover_both_bases_without_losing_master_pushes(self):
        workflows = {
            name: (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            for name in ("fast.yml", "secrets.yml", "native-permission-api.yml")
        }
        for name, text in workflows.items():
            self.assertRegex(text, r"pull_request:\s*\n\s+branches:\s+\[develop, master\]", name)
        self.assertRegex(workflows["fast.yml"], r"push:\s*\n\s+branches:\s+\[master\]")
        self.assertRegex(workflows["secrets.yml"], r"push:\s*\n\s+branches:\s+\[master\]")
        self.assertIn("name: FAST / Windows", workflows["fast.yml"])
        self.assertIn("test_release_workflow.py", workflows["fast.yml"])

    def test_pull_request_target_guard_is_metadata_only_and_sets_exact_head_status(self):
        text = (ROOT / ".github/workflows/promotion-guard.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request_target:", text)
        self.assertIn("branches: [master]", text)
        self.assertIn("statuses: write", text)
        self.assertIn('"context": "Promotion source"', text)
        self.assertIn('event_path = os.environ.get("GITHUB_EVENT_PATH")', text)
        self.assertNotIn("github.event_path", text)
        self.assertIn("PROMOTION_WORKFLOW_REF:", text)
        self.assertNotIn("actions/checkout", text)
        self.assertNotRegex(text, r"\$\{\{\s*github\.event\.pull_request\.(?:head|base)")

    def test_release_workflow_is_opt_in_serial_exact_master_and_token_isolated(self):
        text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertRegex(text, r"push:\s*\n\s+branches:\s+\[master\]")
        self.assertNotIn("workflow_dispatch:", text)
        self.assertIn("vars.OLYMPUS_RELEASE_ENABLED == 'true'", text)
        self.assertIn("group: olympus-release-master", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("ref: ${{ github.sha }}", text)
        self.assertIn("pull-requests: read", text)
        self.assertIn("contents: write", text)
        for job in ("tag", "draft", "publish"):
            block = re.search(rf"(?ms)^  {job}:\n(?P<body>.*?)(?=^  [a-z][a-z-]*:\n|\Z)", text)
            self.assertIsNotNone(block, job)
            body = block.group("body")
            self.assertIn("contents: write", body)
            self.assertNotIn("actions/checkout", body)
            self.assertNotIn("qualify.ps1", body)
            self.assertNotIn("release.py", body)
        self.assertIn("verify-public-install.ps1", text)
        self.assertIn("PUBLIC_INSTALL_LIFECYCLE: PENDING", (ROOT / ".github/release.py").read_text(encoding="utf-8"))

    def test_hosted_qualification_is_separate_and_read_only(self):
        text = (ROOT / ".github/workflows/release-qualification.yml").read_text(encoding="utf-8")
        self.assertRegex(text, r"on:\s*\n\s+workflow_dispatch:")
        self.assertIn("permissions: {}", text)
        self.assertIn("contents: read", text)
        self.assertIn("pull-requests: read", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("secrets.", text)
        self.assertIn("vars.OLYMPUS_RELEASE_ENABLED == 'false'", text)
        self.assertIn("github.ref == 'refs/heads/develop'", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", text)
        self.assertIn("qualify-hosted-readonly", text)

    def test_release_helper_does_not_publish_and_checks_public_bytes(self):
        helper = (ROOT / ".github/release.py").read_text(encoding="utf-8")
        self.assertIn('"/releases/latest"', helper)
        self.assertIn("PUBLIC_ASSET_BYTES_MISMATCH", helper)
        self.assertIn("immutable", helper)
        self.assertIn("contents", (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
