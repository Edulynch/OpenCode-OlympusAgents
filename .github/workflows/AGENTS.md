# Workflow trust and release boundaries

- Contributor workflows retain `FAST / Windows` and cover PRs to `develop` and `master`; keep each workflow's existing push/manual triggers and read-only permissions unless the accepted task explicitly changes them.
- `pull_request_target` is base-owned metadata-only work. Never check out, fetch, execute, or artifact-load PR code there; avoid secrets and interpolate no event values directly into shell. A commit status name does not establish source-app attribution by itself.
- The automatic release workflow accepts only an exact canonical `master` push and the exact `OLYMPUS_RELEASE_ENABLED=true` opt-in. Keep provenance, stale-SHA, version, tag, release, asset, and immutable-state checks fail closed.
- Keep tag creation, draft/asset writes, and publication in isolated `contents: write` jobs. Do not add checkout, project scripts, tests, generated artifacts, PATs, package publication, or external release bots to those jobs.
- Read-only qualification must use the exact candidate or annotated tag and clearly label mocked evidence. Local workflow checks do not prove hosted PR/status identity, repository settings, or public endpoint lifecycle; document those gates in the [development guide](../../docs/DEVELOPMENT.md#promotion-and-automatic-releases).
