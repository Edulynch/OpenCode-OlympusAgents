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


def extract_release_job_script(name):
    text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    job = re.search(rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-z][a-z-]*:\n|\Z)", text)
    if job is None:
        raise AssertionError(f"release {name} job is missing")
    script = re.search(
        r"(?ms)^          python3 - <<'PY'\r?\n(?P<body>.*?)^          PY[ \t]*\r?$",
        job.group("body"),
    )
    if script is None:
        raise AssertionError(f"release {name} heredoc is missing")
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

    def test_conflicting_tag_target_fails_and_hidden_draft_is_provisional(self):
        wrong_tag = {**self.tag_object, "object": {"type": "commit", "sha": "d" * 40}}
        assert_reason(
            self,
            "TAG_CONFLICT",
            lambda: self.classify(tag_object=wrong_tag),
        )
        self.assertEqual(self.classify(release=None), "provisional")

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
                "id": 123,
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
        self.response_counts = {}
        self.response_overrides = {}

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
        count = self.response_counts.get(route, 0) + 1
        self.response_counts[route] = count
        payload = self.response_overrides.get(
            (route, count), self.responses[route]
        )
        return FakeResponse(payload)

    def run_qualification(self, env=None):
        output = io.StringIO()
        with (
            mock.patch.dict(os.environ, self.env() if env is None else env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=self.fake_urlopen),
            redirect_stdout(output),
        ):
            release.qualify_hosted_readonly(argparse.Namespace())
        return output.getvalue()

    def assert_revalidation_failure(self, route, response, reason):
        self.calls.clear()
        self.response_counts.clear()
        self.response_overrides.clear()
        self.response_overrides[(route, 2)] = response
        output = io.StringIO()
        with (
            mock.patch.dict(os.environ, self.env(), clear=True),
            mock.patch("urllib.request.urlopen", side_effect=self.fake_urlopen),
            redirect_stdout(output),
        ):
            with self.assertRaisesRegex(release.ReleaseError, reason):
                release.qualify_hosted_readonly(argparse.Namespace())
        self.assertEqual(output.getvalue(), "")
        self.assertTrue(self.calls)
        self.assertTrue(all(method == "GET" and body is None for method, body, _ in self.calls))

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
        self.assertIn("not an atomic snapshot", output)
        self.assertTrue(self.calls)
        self.assertTrue(all(method == "GET" and body is None for method, body, _ in self.calls))
        for route in (
            "/git/ref/heads/develop",
            "/git/ref/heads/master",
            "/releases/latest",
            f"/git/ref/tags/{self.version}",
            f"/git/tags/{self.tag_object_sha}",
        ):
            self.assertEqual(self.response_counts.get(route), 2, route)

    def test_stale_refs_and_moved_release_or_tag_fail_before_success(self):
        scenarios = (
            (
                "/git/ref/heads/develop",
                {"object": {"sha": "f" * 40}},
                "STALE_DEVELOP_SHA",
            ),
            (
                "/git/ref/heads/master",
                {"object": {"sha": "f" * 40}},
                "STALE_MASTER_SHA",
            ),
            (
                "/releases/latest",
                {
                    "id": 124,
                    "tag_name": self.version,
                    "draft": False,
                    "prerelease": False,
                },
                "HOSTED_RELEASE_IDENTITY_CHANGED",
            ),
            (
                f"/git/ref/tags/{self.version}",
                {
                    "ref": f"refs/tags/{self.version}",
                    "object": {"type": "tag", "sha": "f" * 40},
                },
                "HOSTED_TAG_IDENTITY_CHANGED",
            ),
            (
                f"/git/tags/{self.tag_object_sha}",
                {
                    **self.responses[f"/git/tags/{self.tag_object_sha}"],
                    "object": {"type": "commit", "sha": "f" * 40},
                },
                "HOSTED_TAG_IDENTITY_CHANGED",
            ),
        )
        for route, response, reason in scenarios:
            with self.subTest(route=route):
                self.assert_revalidation_failure(route, response, reason)

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
                    if (method, path) == ("GET", f"/releases/tags/{version_after}"):
                        return 200, {"tag_name": version_after, "draft": True}
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

    def test_prepare_marks_matching_tag_without_public_release_as_provisional(self):
        event, sha, before, head_sha, pr = promotion_fixture()
        version_before, version_after = "v1.2.2", "v1.2.3"
        tag_ref = {
            "ref": f"refs/tags/{version_after}",
            "object": {"type": "tag", "sha": "f" * 40},
        }
        tag_object = {
            "tag": version_after,
            "message": release.tag_message(version_after, sha),
            "tagger": {"name": release.BOT_NAME, "email": release.BOT_EMAIL},
            "object": {"type": "commit", "sha": sha},
        }
        with tempfile.TemporaryDirectory() as temp:
            event_path = Path(temp) / "event.json"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            out_dir = Path(temp) / "plan"
            output_path = Path(temp) / "github-output"

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
                        return tag_ref
                    if path == f"/git/tags/{'f' * 40}":
                        return tag_object
                    if path == f"/releases/tags/{version_after}":
                        return None
                    raise AssertionError(f"unexpected API read: {path}")

                def request(self, method, path):
                    self.reads.append(path)
                    if (method, path) == ("GET", "/immutable-releases"):
                        return 200, {"enabled": True}
                    if (method, path) == ("GET", f"/releases/tags/{version_after}"):
                        raise release.ApiError(404, path)
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
                "GITHUB_OUTPUT": str(output_path),
                "OLYMPUS_RELEASE_ENABLED": "true",
            }
            with (
                mock.patch.dict(os.environ, env, clear=True),
                mock.patch.object(release, "GitHub", return_value=api),
                mock.patch.object(release.subprocess, "run", side_effect=fake_git),
                mock.patch.object(release, "git_bytes", side_effect=fake_git_bytes),
            ):
                release.prepare(
                    argparse.Namespace(event=str(event_path), out_dir=str(out_dir))
                )

            outputs = dict(
                line.split("=", 1)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual(outputs["mode"], "provisional")
            self.assertNotIn("release_id", outputs)
            self.assertIn(f"/releases/tags/{version_after}", api.reads)

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


class FakeDraftApi:
    def __init__(self, version, sha, body, contents, *, existing_release=None, list_pages=None):
        self.version = version
        self.sha = sha
        self.body = body
        self.contents = contents
        self.tag_sha = "f" * 40
        self.tag_target_sha = sha
        self.master_sha = sha
        self.release = existing_release
        self.list_pages = list_pages
        self.calls = []
        self.patch_ids = []

    def response(self, payload):
        return FakeResponse(payload)

    def not_found(self, request):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, None)

    def urlopen(self, request, timeout):
        parsed = urllib.parse.urlparse(request.full_url)
        prefix = f"/repos/{release.REPOSITORY}"
        route = parsed.path.removeprefix(prefix)
        query = urllib.parse.parse_qs(parsed.query)
        method = request.get_method()
        self.calls.append((method, parsed.netloc, route, query, request.data))

        if parsed.netloc == "api.github.com":
            if method == "GET" and route == "/immutable-releases":
                return self.response({"enabled": True})
            if method == "GET" and route == "/git/ref/heads/master":
                return self.response({"object": {"sha": self.master_sha}})
            if method == "GET" and route == f"/git/ref/tags/{self.version}":
                return self.response({
                    "ref": f"refs/tags/{self.version}",
                    "object": {"type": "tag", "sha": self.tag_sha},
                })
            if method == "GET" and route == f"/git/tags/{self.tag_sha}":
                return self.response({
                    "tag": self.version,
                    "message": release.tag_message(self.version, self.sha),
                    "tagger": {"name": release.BOT_NAME, "email": release.BOT_EMAIL},
                    "object": {"type": "commit", "sha": self.tag_target_sha},
                })
            if method == "GET" and route.startswith("/contents/"):
                name = urllib.parse.unquote(route.rsplit("/", 1)[-1])
                if query.get("ref") != [self.sha] or name not in self.contents:
                    raise AssertionError(f"unexpected content request: {route} {query}")
                return self.response({
                    "type": "file",
                    "encoding": "base64",
                    "content": base64.b64encode(self.contents[name]).decode("ascii"),
                })
            if method == "GET" and route == f"/releases/tags/{self.version}":
                return self.not_found(request)
            if method == "GET" and route == "/releases":
                page = int(query["page"][0])
                if self.list_pages is not None:
                    return self.response(self.list_pages.get(page, []))
                return self.response([self.release] if self.release is not None else [])
            if method == "POST" and route == "/releases":
                if self.release is not None:
                    raise AssertionError("draft create would duplicate an existing release")
                payload = json.loads(request.data)
                self.release = {
                    "id": 456,
                    **payload,
                    "author": {"login": release.BOT_NAME},
                    "published_at": None,
                    "assets": [],
                    "upload_url": (
                        f"https://uploads.github.com/repos/{release.REPOSITORY}"
                        "/releases/456/assets{?name,label}"
                    ),
                }
                return self.response(self.release)
            if method == "GET" and route == "/releases/latest":
                if self.release is not None and self.release.get("draft") is False:
                    return self.response(self.release)
                return self.not_found(request)
            if method == "GET" and re.fullmatch(r"/releases/[0-9]+", route):
                if self.release is None:
                    return self.not_found(request)
                return self.response(self.release)
            if method == "PATCH" and re.fullmatch(r"/releases/[0-9]+", route):
                requested_id = int(route.rsplit("/", 1)[-1])
                self.patch_ids.append(requested_id)
                if self.release is None or requested_id != self.release.get("id"):
                    return self.not_found(request)
                payload = json.loads(request.data)
                if payload != {"draft": False, "make_latest": "true"}:
                    raise AssertionError(f"unexpected publish payload: {payload}")
                self.release.update({
                    "draft": False,
                    "immutable": True,
                    "published_at": "2026-01-01T00:00:00Z",
                })
                return self.response(self.release)

        if parsed.netloc == "uploads.github.com" and method == "POST":
            match = re.fullmatch(r"/releases/([0-9]+)/assets", route)
            if match is None or self.release is None or int(match.group(1)) != self.release.get("id"):
                return self.not_found(request)
            name = query.get("name", [None])[0]
            if name not in self.contents or request.data != self.contents[name]:
                raise AssertionError(f"unexpected upload: {name}")
            asset = {
                "name": name,
                "digest": "sha256:" + release.sha256(request.data),
                "size": len(request.data),
            }
            self.release["assets"].append(asset)
            return self.response(asset)

        raise AssertionError(f"unexpected API operation: {method} {parsed.netloc}{route} {query}")


class DraftReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.version = "v1.2.3"
        self.sha = "a" * 40
        self.body = "reviewed release notes\n"
        self.contents = {
            "install-olympus.ps1": b"windows installer",
            "install-olympus.sh": b"linux installer",
        }
        self.expected = {
            name: {
                "sha256": release.sha256(content),
                "size": len(content),
            }
            for name, content in self.contents.items()
        }
        self.draft_script = extract_release_job_script("draft")
        self.publish_script = extract_release_job_script("publish")

    def make_draft(self, *, release_id=456, target_sha=None, assets=None):
        return {
            "id": release_id,
            "tag_name": self.version,
            "target_commitish": self.sha if target_sha is None else target_sha,
            "name": self.version,
            "body": self.body,
            "draft": True,
            "prerelease": False,
            "author": {"login": release.BOT_NAME},
            "published_at": None,
            "assets": list(assets or []),
            "upload_url": (
                f"https://uploads.github.com/repos/{release.REPOSITORY}"
                f"/releases/{release_id}/assets{{?name,label}}"
            ),
        }

    def env(self, output=None, *, mode="provisional", release_id="456"):
        values = {
            "REPOSITORY": release.REPOSITORY,
            "GITHUB_TOKEN": "offline-test-token",
            "RELEASE_VERSION": self.version,
            "RELEASE_SHA": self.sha,
            "RELEASE_MODE": mode,
            "RELEASE_BODY_B64": base64.b64encode(self.body.encode()).decode(),
            "RELEASE_BODY_SHA256": release.sha256(self.body.encode()),
            "RELEASE_PS1_SHA256": self.expected["install-olympus.ps1"]["sha256"],
            "RELEASE_SH_SHA256": self.expected["install-olympus.sh"]["sha256"],
            "RELEASE_PS1_SIZE": str(self.expected["install-olympus.ps1"]["size"]),
            "RELEASE_SH_SIZE": str(self.expected["install-olympus.sh"]["size"]),
            "OLYMPUS_RELEASE_ENABLED": "true",
            "OLYMPUS_RELEASE_IMMUTABILITY_CONFIRMED": "true",
            "RELEASE_ID": release_id,
        }
        if output is not None:
            values["GITHUB_OUTPUT"] = str(output)
        return values

    def run_script(self, script, api, env):
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=api.urlopen),
            redirect_stdout(io.StringIO()),
        ):
            exec(compile(script, "release.yml:embedded-job", "exec"), {})

    def assert_no_release_writes(self, api):
        writes = [
            (method, route)
            for method, _, route, _, _ in api.calls
            if method in ("POST", "PATCH", "DELETE")
        ]
        self.assertEqual(writes, [])

    def test_first_run_hands_off_numeric_id_and_publishes_by_id(self):
        api = FakeDraftApi(self.version, self.sha, self.body, self.contents)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "github-output"
            self.run_script(self.draft_script, api, self.env(output, mode="create"))
            self.assertEqual(output.read_text(encoding="utf-8"), "release_id=456\n")
            self.assertEqual(api.release["target_commitish"], self.sha)
            self.assertEqual(
                {(asset["name"], asset["size"], asset["digest"]) for asset in api.release["assets"]},
                {
                    (name, item["size"], f"sha256:{item['sha256']}")
                    for name, item in self.expected.items()
                },
            )
            self.assertEqual(
                [route for method, _, route, _, _ in api.calls if method == "POST"],
                ["/releases", "/releases/456/assets", "/releases/456/assets"],
            )
            before_publish = len(api.calls)
            self.run_script(
                self.publish_script,
                api,
                self.env(release_id=output.read_text(encoding="utf-8").split("=", 1)[1].strip()),
            )
            publish_calls = api.calls[before_publish:]
            self.assertEqual(api.patch_ids, [456])
            self.assertFalse(
                any(route.startswith("/releases/tags/") for _, _, route, _, _ in publish_calls)
            )
            self.assertEqual(api.release["draft"], False)
            self.assertEqual(api.release["immutable"], True)
            self.assertEqual(api.release["id"], 456)

    def test_same_sha_resume_finds_hidden_draft_and_reuses_its_id(self):
        first_asset = {
            "name": "install-olympus.ps1",
            "digest": f"sha256:{self.expected['install-olympus.ps1']['sha256']}",
            "size": self.expected["install-olympus.ps1"]["size"],
        }
        api = FakeDraftApi(
            self.version,
            self.sha,
            self.body,
            self.contents,
            existing_release=self.make_draft(assets=[first_asset]),
        )
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "github-output"
            self.run_script(self.draft_script, api, self.env(output, mode="provisional"))
            self.assertEqual(output.read_text(encoding="utf-8"), "release_id=456\n")
            self.assertFalse(any(method == "POST" and route == "/releases" for method, _, route, _, _ in api.calls))
            self.assertEqual(
                [route for method, _, route, _, _ in api.calls if method == "POST"],
                ["/releases/456/assets"],
            )
            by_tag_reads = len([
                call for call in api.calls if call[0] == "GET" and call[2].startswith("/releases/tags/")
            ])
            before_publish = len(api.calls)
            self.run_script(
                self.publish_script,
                api,
                self.env(release_id=output.read_text(encoding="utf-8").split("=", 1)[1].strip()),
            )
            publish_calls = api.calls[before_publish:]
            self.assertEqual(api.patch_ids, [456])
            self.assertFalse(
                any(route.startswith("/releases/tags/") for _, _, route, _, _ in publish_calls)
            )
            self.assertEqual(
                len([
                    call for call in api.calls if call[0] == "GET" and call[2].startswith("/releases/tags/")
                ]),
                by_tag_reads,
            )

    def test_missing_or_ambiguous_draft_fails_before_any_write(self):
        no_draft = FakeDraftApi(self.version, self.sha, self.body, self.contents)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(SystemExit, "ORPHAN_TAG_CONFLICT"):
                self.run_script(
                    self.draft_script,
                    no_draft,
                    self.env(Path(temp) / "out", mode="provisional"),
                )
        self.assert_no_release_writes(no_draft)

        first = self.make_draft()
        fillers = [
            {"id": 1000 + index, "tag_name": f"v9.{index}.0", "draft": True}
            for index in range(99)
        ]
        second = self.make_draft(release_id=457)
        duplicate_pages = {1: fillers + [first], 2: [second]}
        duplicate = FakeDraftApi(
            self.version,
            self.sha,
            self.body,
            self.contents,
            existing_release=first,
            list_pages=duplicate_pages,
        )
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(SystemExit, "DRAFT_RELEASE_AMBIGUOUS"):
                self.run_script(
                    self.draft_script,
                    duplicate,
                    self.env(Path(temp) / "out", mode="provisional"),
                )
        pages = [query["page"][0] for method, _, route, query, _ in duplicate.calls if method == "GET" and route == "/releases"]
        self.assertEqual(pages, ["1", "2"])
        self.assert_no_release_writes(duplicate)

    def test_unusable_bounded_pagination_fails_closed(self):
        full_pages = {
            page: [
                {"id": page * 100 + index, "tag_name": f"v9.{page}.{index}", "draft": True}
                for index in range(100)
            ]
            for page in range(1, 11)
        }
        api = FakeDraftApi(
            self.version,
            self.sha,
            self.body,
            self.contents,
            list_pages=full_pages,
        )
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(SystemExit, "RELEASE_LIST_INCOMPLETE"):
                self.run_script(
                    self.draft_script,
                    api,
                    self.env(Path(temp) / "out", mode="provisional"),
                )
        pages = [query["page"][0] for method, _, route, query, _ in api.calls if method == "GET" and route == "/releases"]
        self.assertEqual(pages, [str(page) for page in range(1, 11)])
        self.assert_no_release_writes(api)

    def test_wrong_id_body_or_asset_fails_before_draft_writes(self):
        cases = (
            (
                self.make_draft(release_id=457),
                [{"id": 456, "tag_name": self.version, "draft": True}],
                "DRAFT_RELEASE_IDENTITY_INVALID",
            ),
            (
                {**self.make_draft(), "body": "different notes"},
                None,
                "DRAFT_RELEASE_CONFLICT",
            ),
            (
                self.make_draft(assets=[{
                    "name": "install-olympus.ps1",
                    "digest": "sha256:" + "0" * 64,
                    "size": self.expected["install-olympus.ps1"]["size"],
                }]),
                None,
                "DRAFT_ASSET_CONFLICT",
            ),
        )
        for draft, list_page, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                pages = None if list_page is None else {1: list_page}
                api = FakeDraftApi(
                    self.version,
                    self.sha,
                    self.body,
                    self.contents,
                    existing_release=draft,
                    list_pages=pages,
                )
                with tempfile.TemporaryDirectory() as temp:
                    with self.assertRaisesRegex(SystemExit, expected_error):
                        self.run_script(
                            self.draft_script,
                            api,
                            self.env(Path(temp) / "out", mode="provisional"),
                        )
                self.assert_no_release_writes(api)

        wrong_tag = FakeDraftApi(
            self.version,
            self.sha,
            self.body,
            self.contents,
            existing_release=self.make_draft(),
        )
        wrong_tag.tag_target_sha = "d" * 40
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(SystemExit, "TAG_CONFLICT"):
                self.run_script(
                    self.draft_script,
                    wrong_tag,
                    self.env(Path(temp) / "out", mode="provisional"),
                )
        self.assert_no_release_writes(wrong_tag)

    def test_publisher_rejects_bad_id_or_asset_without_patch(self):
        api = FakeDraftApi(
            self.version,
            self.sha,
            self.body,
            self.contents,
            existing_release=self.make_draft(assets=[
                {
                    "name": name,
                    "digest": f"sha256:{item['sha256']}",
                    "size": item["size"],
                }
                for name, item in self.expected.items()
            ]),
        )
        with self.assertRaisesRegex(SystemExit, "DRAFT_RELEASE_ID_INVALID"):
            self.run_script(self.publish_script, api, self.env(release_id="0"))
        self.assertEqual(api.calls, [])

        api.release["assets"][0]["size"] += 1
        with self.assertRaisesRegex(SystemExit, "DRAFT_ASSET_CONFLICT"):
            self.run_script(self.publish_script, api, self.env(release_id="456"))
        self.assertEqual(api.patch_ids, [])
        self.assert_no_release_writes(api)


class TagDraftDiscoveryTests(unittest.TestCase):
    def test_create_does_not_write_tag_when_authenticated_list_has_hidden_draft(self):
        version = "v1.2.3"
        sha = "a" * 40
        calls = []
        root = f"/repos/{release.REPOSITORY}"

        def fake_urlopen(request, timeout):
            parsed = urllib.parse.urlparse(request.full_url)
            route = parsed.path.removeprefix(root)
            method = request.get_method()
            calls.append((method, route))
            if (method, route) == ("GET", "/immutable-releases"):
                return FakeResponse({"enabled": True})
            if (method, route) == ("GET", "/git/ref/heads/master"):
                return FakeResponse({"object": {"sha": sha}})
            if (method, route) in (
                ("GET", f"/git/ref/tags/{version}"),
                ("GET", f"/releases/tags/{version}"),
            ):
                raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, None)
            if method == "GET" and route == "/releases":
                return FakeResponse([{"tag_name": version, "draft": True}])
            raise AssertionError(f"unexpected API operation: {method} {route}")

        env = {
            "REPOSITORY": release.REPOSITORY,
            "GITHUB_TOKEN": "offline-test-token",
            "RELEASE_VERSION": version,
            "RELEASE_SHA": sha,
            "RELEASE_MODE": "create",
            "OLYMPUS_RELEASE_ENABLED": "true",
            "OLYMPUS_RELEASE_IMMUTABILITY_CONFIRMED": "true",
        }
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("urllib.request.urlopen", side_effect=fake_urlopen),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaisesRegex(SystemExit, "RELEASE_STATE_CONFLICT"):
                exec(compile(extract_tag_guard_script(), "release.yml:tag-guard", "exec"), {})

        self.assertTrue(calls)
        self.assertTrue(all(method == "GET" for method, _ in calls))


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
        self.assertIn("release_id: ${{ steps.attach.outputs.release_id }}", text)
        self.assertIn("RELEASE_ID: ${{ needs.draft.outputs.release_id }}", text)
        self.assertIn("ps1_size: ${{ steps.plan.outputs.ps1_size }}", text)
        self.assertNotIn("/releases/tags/", extract_release_job_script("publish"))
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
