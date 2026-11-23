#!/usr/bin/env python3
"""Fail-closed metadata and public-release checks for the trusted release workflow."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPOSITORY = "Edulynch/OpenCode-OlympusAgents"
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
ASSET_PATHS = {
    "install-olympus.ps1": "install-olympus.ps1",
    "install-olympus.sh": "install-olympus.sh",
}
STABLE_VERSION = re.compile(
    r"\Av(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z"
)
SHA = re.compile(r"\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class ReleaseError(RuntimeError):
    """A fail-closed release-policy rejection with a stable reason code."""


class ApiError(ReleaseError):
    def __init__(self, status: int, path: str):
        super().__init__(f"GITHUB_API_{status}: request failed for {path}")
        self.status = status


def reject(code: str, detail: str) -> None:
    raise ReleaseError(f"{code}: {detail}")


def version_key(version: str) -> tuple[int, int, int]:
    match = STABLE_VERSION.fullmatch(version)
    if not match:
        reject("RELEASE_VERSION_INVALID", f"{version!r} is not stable vX.Y.Z")
    return tuple(int(value) for value in match.groups())


def extract_release_version(installer: str, source: str) -> str:
    defaults = re.findall(
        r"(?m)^\s*\[string\]\$Version\s*=\s*'([^']+)'\s*,?\s*$", installer
    )
    markers = re.findall(
        r"(?m)^\s*\$ReleaseVersion\s*=\s*'([^']+)'\s*(?:#.*)?$", installer
    )
    if len(defaults) != 1 or len(markers) != 1 or defaults[0] != markers[0]:
        reject("RELEASE_MARKERS_MISMATCH", f"{source} installer markers must agree")
    version_key(defaults[0])
    return defaults[0]


def validate_promotion(
    event: dict,
    repository: str,
    sha: str,
    parents: list[str],
    associated_prs: list[dict],
    current_master_sha: str,
) -> dict:
    """Validate the exact canonical develop -> master merge push."""
    if not isinstance(repository, str) or repository.casefold() != REPOSITORY.casefold():
        reject("REPOSITORY_MISMATCH", "release runs only in the canonical repository")
    event_repository = event.get("repository") or {}
    event_full_name = event_repository.get("full_name") if isinstance(event_repository, dict) else None
    if not isinstance(event_full_name, str) or event_full_name.casefold() != REPOSITORY.casefold():
        reject("EVENT_REPOSITORY_MISMATCH", "push payload repository is not canonical")
    if event.get("ref") != "refs/heads/master":
        reject("PUSH_REF_INVALID", "event ref must be refs/heads/master")
    if event.get("deleted") is not False or event.get("forced") is not False:
        reject("PUSH_NOT_FAST_FORWARD", "deleted or forced pushes are not releases")
    if event.get("created") is not False:
        reject("PUSH_CREATED_REF", "creating a branch is not a promotion")
    before, after = event.get("before"), event.get("after")
    if not isinstance(before, str) or not SHA.fullmatch(before) or set(before) == {"0"}:
        reject("PUSH_BEFORE_INVALID", "push must identify a nonzero previous master SHA")
    if not isinstance(after, str) or not SHA.fullmatch(after) or after != sha:
        reject("PUSH_SHA_MISMATCH", "event after SHA must equal the workflow SHA")
    if current_master_sha != sha:
        reject("STALE_MASTER_SHA", "event SHA is not the current master tip")
    if (
        not isinstance(parents, list)
        or len(parents) != 2
        or any(not isinstance(parent, str) or not SHA.fullmatch(parent) for parent in parents)
        or parents[0] != before
        or parents[1] == parents[0]
    ):
        reject("MERGE_PARENTS_INVALID", "merge commit must have first parent equal to push before")

    exact = [
        pr for pr in associated_prs
        if isinstance(pr, dict) and pr.get("merge_commit_sha") == sha
    ]
    if len(exact) != 1:
        reject("PROMOTION_PR_AMBIGUOUS", "expected exactly one associated PR for this merge SHA")
    pr = exact[0]
    base, head = pr.get("base") or {}, pr.get("head") or {}
    base_repo_data = base.get("repo") or {} if isinstance(base, dict) else {}
    head_repo_data = head.get("repo") or {} if isinstance(head, dict) else {}
    base_repo = base_repo_data.get("full_name", "") if isinstance(base_repo_data, dict) else ""
    head_repo = head_repo_data.get("full_name", "") if isinstance(head_repo_data, dict) else ""
    if (
        pr.get("state") != "closed"
        or not pr.get("merged_at")
        or base_repo.casefold() != REPOSITORY.casefold()
        or base.get("ref") != "master"
        or head_repo.casefold() != REPOSITORY.casefold()
        or head.get("ref") != "develop"
        or not isinstance(head.get("sha"), str)
        or head.get("sha") != parents[1]
    ):
        reject(
            "PROMOTION_SOURCE_INVALID",
            "the associated merged PR must be canonical develop -> master with the exact second parent",
        )
    return pr


def tag_message(version: str, sha: str) -> str:
    return f"Olympus automatic release\nversion: {version}\ncommit: {sha}\n"


def check_immutable_setting(status: int, response: object, confirmed: str) -> str:
    """Use the authenticated setting endpoint or an explicit owner attestation."""
    if status == 200:
        if not isinstance(response, dict) or response.get("enabled") is not True:
            reject("IMMUTABILITY_DISABLED", "GitHub reports immutable releases disabled")
        return "api"
    if status in (401, 403) and confirmed == "true":
        return "owner-precondition"
    if status == 404:
        reject("IMMUTABILITY_DISABLED", "GitHub reports no immutable-release policy")
    reject(
        "IMMUTABILITY_UNVERIFIED",
        "setting endpoint was unavailable and the explicit owner precondition was not satisfied",
    )


def _require_tag(tag_ref: dict, tag_object: dict, version: str, sha: str) -> None:
    expected_message = tag_message(version, sha)
    ref_object = tag_ref.get("object") or {}
    target = tag_object.get("object") or {}
    tagger = tag_object.get("tagger") or {}
    if (
        tag_ref.get("ref") != f"refs/tags/{version}"
        or ref_object.get("type") != "tag"
        or tag_object.get("tag") != version
        or target.get("type") != "commit"
        or target.get("sha") != sha
        or tag_object.get("message") != expected_message
        or tagger.get("name") != BOT_NAME
        or tagger.get("email") != BOT_EMAIL
    ):
        reject("TAG_CONFLICT", "existing tag is not the exact workflow-owned annotated tag")


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _validate_release_identity(
    release: dict,
    version: str,
    body: str,
    expected_assets: dict[str, str],
) -> dict[str, dict]:
    if (
        release.get("tag_name") != version
        or release.get("name") != version
        or release.get("body") != body
        or release.get("prerelease") is not False
        or (release.get("author") or {}).get("login") != BOT_NAME
    ):
        reject("RELEASE_OWNERSHIP_OR_IDENTITY_CONFLICT", "existing release identity/body/owner differs")
    assets = release.get("assets")
    if not isinstance(assets, list):
        reject("RELEASE_ASSETS_INVALID", "release assets are missing or malformed")
    by_name: dict[str, dict] = {}
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("name"), str):
            reject("RELEASE_ASSETS_INVALID", "release contains a malformed asset")
        name = asset["name"]
        if name in by_name or name not in expected_assets:
            reject("RELEASE_ASSET_CONFLICT", f"unexpected or duplicate asset {name!r}")
        digest = asset.get("digest")
        if digest != f"sha256:{expected_assets[name]}":
            reject("RELEASE_ASSET_CONFLICT", f"asset {name!r} digest does not match the tag")
        by_name[name] = asset
    return by_name


def classify_existing_release(
    *,
    version_before: str,
    version_after: str,
    latest_release: dict | None,
    tag_ref: dict | None,
    tag_object: dict | None,
    release: dict | None,
    sha: str,
    body: str,
    expected_assets: dict[str, str],
) -> str:
    """Return noop/create/resume/published, rejecting any conflicting state."""
    before_key = version_key(version_before)
    after_key = version_key(version_after)
    if version_after == version_before:
        return "noop"
    if after_key <= before_key:
        reject("RELEASE_VERSION_NOT_INCREASING", "candidate must exceed the previous master version")

    latest_tag = None
    if latest_release is not None:
        latest_tag = latest_release.get("tag_name")
        if not isinstance(latest_tag, str):
            reject("LATEST_RELEASE_INVALID", "latest release metadata has no stable tag")
        latest_key = version_key(latest_tag)
        if latest_key > after_key:
            reject("RELEASE_VERSION_NOT_LATEST", "candidate must exceed the latest public release")

    if tag_ref is None:
        if release is not None:
            reject("RELEASE_WITHOUT_TAG", "release exists without its exact tag ref")
        if latest_tag == version_after:
            reject("LATEST_RELEASE_TAG_MISSING", "latest release tag ref is missing")
        return "create"
    if tag_object is None:
        reject("TAG_OBJECT_MISSING", "annotated tag object cannot be resolved")
    _require_tag(tag_ref, tag_object, version_after, sha)
    if release is None:
        reject("ORPHAN_TAG_CONFLICT", "existing tag has no matching owned draft or public release")

    by_name = _validate_release_identity(release, version_after, body, expected_assets)
    if release.get("draft") is True:
        if release.get("published_at") is not None:
            reject("DRAFT_STATE_INVALID", "draft release unexpectedly has a publication timestamp")
        return "resume"
    if release.get("draft") is not False:
        reject("RELEASE_STATE_INVALID", "existing release draft state is malformed")
    if (
        release.get("immutable") is not True
        or not _valid_timestamp(release.get("published_at"))
        or set(by_name) != set(expected_assets)
        or latest_tag != version_after
    ):
        reject("PUBLISHED_RELEASE_CONFLICT", "published release is mutable, incomplete, or not latest")
    return "published"


def extract_release_notes(changelog: str, version: str) -> str:
    version_key(version)
    matches = list(re.finditer(r"(?m)^## " + re.escape(version) + r"[ \t]*$", changelog))
    if len(matches) != 1:
        reject("RELEASE_NOTES_SECTION_INVALID", f"expected one changelog section for {version}")
    start = matches[0].start()
    tail = changelog[matches[0].end():]
    next_section = re.search(r"(?m)^## v(?:0|[1-9][0-9]*)\.", tail)
    body = tail[:next_section.start()] if next_section else tail
    section = changelog[start:matches[0].end()] + body
    for heading in ("### Highlights", "### Capability limits", "## Installation", "## Verify installation"):
        if heading not in section:
            reject("RELEASE_NOTES_SECTION_INVALID", f"{version} notes lack {heading}")
    return section.rstrip() + "\n"


class GitHub:
    def __init__(self, token: str, repository: str):
        self.token = token
        self.repository = repository
        self.root = f"https://api.github.com/repos/{repository}"

    def request(self, method: str, path: str, body: dict | None = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.root + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "Olympus-release-workflow",
                "X-GitHub-Api-Version": "2022-11-28",
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                if not payload:
                    return response.status, None
                return response.status, json.loads(payload)
        except urllib.error.HTTPError as error:
            # Do not print response bodies; API errors can contain user-supplied data.
            raise ApiError(error.code, path) from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            reject("GITHUB_API_UNAVAILABLE", f"request failed for {path}")

    def get(self, path: str, *, optional: bool = False):
        try:
            return self.request("GET", path)[1]
        except ApiError as error:
            if optional and error.status == 404:
                return None
            raise


def git_bytes(revision: str, path: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "show", f"{revision}:{path}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout
    except subprocess.CalledProcessError:
        reject("SOURCE_FILE_MISSING", f"{path} is unavailable at exact commit {revision}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_output(values: dict[str, str]) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with open(output, "a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                reject("WORKFLOW_OUTPUT_INVALID", f"{key} must be a single line")
            stream.write(f"{key}={value}\n")


def prepare(args: argparse.Namespace) -> None:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "").lower()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        reject("GITHUB_TOKEN_MISSING", "read-only metadata token is required")
    with open(args.event, encoding="utf-8") as stream:
        event = json.load(stream)
    if repository.casefold() != REPOSITORY.casefold() or os.environ.get("GITHUB_REF") != "refs/heads/master":
        reject("RELEASE_EVENT_INVALID", "release workflow accepts only the canonical master push")
    if os.environ.get("OLYMPUS_RELEASE_ENABLED") != "true":
        reject("RELEASE_OPT_IN_DISABLED", "OLYMPUS_RELEASE_ENABLED must be exactly true")
    if not SHA.fullmatch(sha):
        reject("RELEASE_SHA_INVALID", "workflow SHA must be a full Git object ID")

    api = GitHub(token, repository)
    checked_out_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout.strip()
    if checked_out_sha != sha:
        reject("CHECKOUT_SHA_MISMATCH", "candidate checkout must equal the push SHA")
    current_master = api.get("/git/ref/heads/master")
    current_master_sha = (current_master.get("object") or {}).get("sha", "")
    parent_text = subprocess.run(
        ["git", "show", "-s", "--format=%P", sha],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout.strip()
    parents = parent_text.split() if parent_text else []
    associated = api.get(f"/commits/{sha}/pulls?per_page=100")
    if not isinstance(associated, list):
        reject("PROMOTION_PR_METADATA_INVALID", "associated PR response is malformed")
    validate_promotion(event, repository, sha, parents, associated, current_master_sha)

    before_installer = git_bytes(event["before"], "install.ps1").decode("utf-8-sig")
    candidate_installer = git_bytes(sha, "install.ps1").decode("utf-8-sig")
    version_before = extract_release_version(before_installer, "previous")
    version_after = extract_release_version(candidate_installer, "candidate")
    if version_before == version_after:
        print(f"RELEASE_NOOP: {version_after} unchanged from previous master; no tag or release mutation")
        write_output({"mode": "noop", "version": version_after, "sha": sha})
        return

    latest = api.get("/releases/latest", optional=True)
    if latest is not None:
        latest_tag = latest.get("tag_name")
        if not isinstance(latest_tag, str):
            reject("LATEST_RELEASE_INVALID", "latest release has no tag_name")
        latest_key = version_key(latest_tag)
        if latest_key > version_key(version_after):
            reject("RELEASE_VERSION_NOT_LATEST", "candidate is not newer than latest public release")

    try:
        immutable_status, immutable_body = api.request("GET", "/immutable-releases")
    except ApiError as error:
        immutable_status, immutable_body = error.status, None
    immutability_evidence = check_immutable_setting(
        immutable_status,
        immutable_body,
        os.environ.get("OLYMPUS_RELEASE_IMMUTABILITY_CONFIRMED", ""),
    )

    changelog = git_bytes(sha, "CHANGELOG.md").decode("utf-8-sig")
    body = extract_release_notes(changelog, version_after)
    assets = {name: git_bytes(sha, path) for name, path in ASSET_PATHS.items()}
    expected_assets = {name: sha256(data) for name, data in assets.items()}
    tag_path = "/git/ref/tags/" + urllib.parse.quote(version_after, safe="")
    tag_ref = api.get(tag_path, optional=True)
    release_path = "/releases/tags/" + urllib.parse.quote(version_after, safe="")
    release = api.get(release_path, optional=True)
    if release is not None and not isinstance(release, dict):
        reject("RELEASE_METADATA_INVALID", "release-by-tag response is malformed")
    tag_object = None
    if tag_ref is not None:
        ref_object = tag_ref.get("object") or {}
        if ref_object.get("type") == "tag" and isinstance(ref_object.get("sha"), str):
            tag_object = api.get("/git/tags/" + urllib.parse.quote(ref_object["sha"], safe=""))
    mode = classify_existing_release(
        version_before=version_before,
        version_after=version_after,
        latest_release=latest,
        tag_ref=tag_ref,
        tag_object=tag_object,
        release=release,
        sha=sha,
        body=body,
        expected_assets=expected_assets,
    )
    if mode == "published":
        print(f"RELEASE_ALREADY_PUBLISHED: {version_after}; read-only public verification required")
        write_output({
            "mode": mode,
            "version": version_after,
            "sha": sha,
            "body_b64": base64.b64encode(body.encode("utf-8")).decode("ascii"),
            "body_sha256": sha256(body.encode("utf-8")),
            "ps1_sha256": expected_assets["install-olympus.ps1"],
            "sh_sha256": expected_assets["install-olympus.sh"],
            "immutability_evidence": immutability_evidence,
        })
        return

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in assets.items():
        (out_dir / name).write_bytes(data)
    (out_dir / "release-notes.md").write_text(body, encoding="utf-8", newline="\n")
    body_hash = sha256(body.encode("utf-8"))
    manifest = {
        "version": version_after,
        "sha": sha,
        "body_sha256": body_hash,
        "assets": expected_assets,
        "immutability_evidence": immutability_evidence,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    output = {
        "mode": mode,
        "version": version_after,
        "sha": sha,
        "body_b64": base64.b64encode(body.encode("utf-8")).decode("ascii"),
        "body_sha256": body_hash,
        "ps1_sha256": expected_assets["install-olympus.ps1"],
        "sh_sha256": expected_assets["install-olympus.sh"],
        "immutability_evidence": immutability_evidence,
    }
    write_output(output)
    print(
        f"RELEASE_PLAN: mode={mode} version={version_after} sha={sha} "
        f"immutability={immutability_evidence}"
    )


def _download_public_asset(url: str) -> bytes:
    if not isinstance(url, str) or not url.startswith("https://"):
        reject("PUBLIC_ASSET_UNAVAILABLE", "latest-release asset URL is missing or not HTTPS")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Olympus-release-verification"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if urllib.parse.urlparse(response.geturl()).scheme != "https":
                reject("PUBLIC_ASSET_UNAVAILABLE", "asset download left HTTPS")
            content = response.read(8 * 1024 * 1024 + 1)
            if len(content) > 8 * 1024 * 1024:
                reject("PUBLIC_ASSET_TOO_LARGE", "installer asset exceeds the 8 MiB verification limit")
            return content
    except (urllib.error.URLError, TimeoutError):
        reject("PUBLIC_ASSET_UNAVAILABLE", "latest-release asset could not be downloaded")


def _verify_release_assets(
    release: dict,
    expected: dict[str, str],
    *,
    public: bool,
    version: str,
) -> None:
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != len(expected):
        reject("PUBLIC_ASSET_SET_INVALID", "release must contain exactly the two expected installer assets")
    found: set[str] = set()
    for asset in assets:
        name = asset.get("name") if isinstance(asset, dict) else None
        if name not in expected or name in found:
            reject("PUBLIC_ASSET_SET_INVALID", "release contains an unexpected or duplicate asset")
        found.add(name)
        digest = asset.get("digest")
        expected_digest = f"sha256:{expected[name]}"
        if digest is not None and digest != expected_digest:
            reject("PUBLIC_ASSET_DIGEST_MISMATCH", f"{name} API digest does not match the tagged source")
        if public:
            url = asset.get("browser_download_url", "")
            parsed = urllib.parse.urlparse(url)
            expected_path = f"/{REPOSITORY}/releases/download/{version}/{name}"
            if parsed.netloc.casefold() != "github.com" or parsed.path != expected_path:
                reject("PUBLIC_ASSET_URL_INVALID", f"{name} is not the exact canonical release asset URL")
            content = _download_public_asset(url)
            if sha256(content) != expected[name]:
                reject("PUBLIC_ASSET_BYTES_MISMATCH", f"{name} public bytes do not match the tagged source")
    if found != set(expected):
        reject("PUBLIC_ASSET_SET_INVALID", "one or more required installer assets are absent")


def verify_public(args: argparse.Namespace) -> None:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if repository.casefold() != REPOSITORY.casefold() or not token:
        reject("PUBLIC_VERIFY_CONTEXT_INVALID", "canonical repository read token is required")
    version_key(args.version)
    if not SHA.fullmatch(args.sha):
        reject("PUBLIC_VERIFY_INPUT_INVALID", "expected commit SHA is malformed")
    if not re.fullmatch(r"[0-9a-f]{64}", args.body_sha256):
        reject("PUBLIC_VERIFY_INPUT_INVALID", "expected release-notes SHA-256 is malformed")
    expected_assets = {
        "install-olympus.ps1": args.ps1_sha256,
        "install-olympus.sh": args.sh_sha256,
    }
    for digest in expected_assets.values():
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            reject("PUBLIC_VERIFY_INPUT_INVALID", "expected asset SHA-256 is malformed")
    api = GitHub(token, repository)
    current_master = api.get("/git/ref/heads/master")
    if (current_master.get("object") or {}).get("sha") != args.sha:
        reject("PUBLIC_VERIFY_STALE_SHA", "the published release SHA is no longer current master")
    latest = api.get("/releases/latest")
    release = api.get("/releases/tags/" + urllib.parse.quote(args.version, safe=""))
    if latest.get("tag_name") != args.version:
        reject("PUBLIC_LATEST_MISMATCH", "the exact candidate is not the latest public release")
    body = release.get("body")
    if (
        release.get("tag_name") != args.version
        or release.get("draft") is not False
        or release.get("prerelease") is not False
        or release.get("immutable") is not True
        or not _valid_timestamp(release.get("published_at"))
        or (release.get("author") or {}).get("login") != BOT_NAME
        or not isinstance(body, str)
        or sha256(body.encode("utf-8")) != args.body_sha256
    ):
        reject("PUBLIC_RELEASE_STATE_INVALID", "published release identity or immutable state is invalid")
    published_at = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
    if published_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        reject("PUBLIC_RELEASE_STATE_INVALID", "publication timestamp is more than five minutes in the future")
    tag_ref = api.get("/git/ref/tags/" + urllib.parse.quote(args.version, safe=""))
    ref_object = tag_ref.get("object") or {}
    if ref_object.get("type") != "tag" or not isinstance(ref_object.get("sha"), str):
        reject("PUBLIC_TAG_INVALID", "published release must reference an annotated tag")
    tag_object = api.get("/git/tags/" + urllib.parse.quote(ref_object["sha"], safe=""))
    _require_tag(tag_ref, tag_object, args.version, args.sha)
    _verify_release_assets(release, expected_assets, public=True, version=args.version)
    print(
        f"PUBLIC_RELEASE_VERIFIED: {args.version} immutable=true "
        "latest=true exact PS1/sh asset bytes verified"
    )
    print("PUBLIC_INSTALL_LIFECYCLE: PENDING (this workflow does not equate mock qualification with endpoint install)")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--event", required=True)
    prepare_parser.add_argument("--out-dir", required=True)
    prepare_parser.set_defaults(function=prepare)
    verify_parser = subparsers.add_parser("verify-public")
    verify_parser.add_argument("--version", required=True)
    verify_parser.add_argument("--sha", required=True)
    verify_parser.add_argument("--body-sha256", required=True)
    verify_parser.add_argument("--ps1-sha256", required=True)
    verify_parser.add_argument("--sh-sha256", required=True)
    verify_parser.set_defaults(function=verify_public)
    args = parser.parse_args()
    try:
        args.function(args)
    except (ReleaseError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        message = str(error)
        if not re.match(r"^[A-Z][A-Z0-9_]+:", message):
            message = "RELEASE_INTERNAL_ERROR: release gate failed closed"
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
