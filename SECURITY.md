# Security Policy

## Supported versions

Security fixes are prioritized for the **latest stable GitHub Release**. Older releases may be affected by issues already addressed in a newer version; update when possible. The `master` branch is development code, not a separate supported release.

## Report a vulnerability

**Do not post exploit details, tokens, private paths, ACL descriptors, or proof-of-concept payloads in a public issue.**

1. Open the repository's [Security page](https://github.com/Edulynch/OpenCode-OlympusAgents/security). If **Report a vulnerability** is available, use it for a private report.
2. If private reporting is not available, [open a public issue](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/new) **without sensitive details** and ask the maintainer for a private reporting channel.

Useful private-report information: affected Olympus release, OpenCode/Codex version and OS, expected authorization boundary, actual behavior, minimal reproducible conditions, impact, and whether an unrelated user's files or credentials were affected. Redact identifiers and confidential data.

The maintainer will triage and coordinate disclosure when a supported fix is available. No response time is guaranteed.

## Security boundaries

Olympus agents can run commands when explicitly authorized. **Task scope is not an OS sandbox.** The OpenCode and Codex harnesses have different permission and enforcement capabilities; consult [the capability matrix](docs/HARNESS-CAPABILITIES.md) before treating a prompt as a security boundary.

Use only trusted repositories, review permission requests, and do not publish secrets in diagnostic traces.

## Secret scanning and handling evidence

This repository uses the open-source, [MIT-licensed Gitleaks CLI](https://github.com/gitleaks/gitleaks/blob/v8.30.1/LICENSE) **v8.30.1**. The local gate downloads a platform-specific asset from the official [Gitleaks release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), verifies its pinned SHA-256 before extraction, and checks the executable's reported version. The current Windows/Linux x64 and ARM64 archive hashes are kept beside the downloader in `scripts/secret_gate.py`. No Gitleaks Action, SaaS scanner, credential, or provider validation is used.

Run the gate explicitly from the repository root:

```powershell
python -B scripts/secret_gate.py --base origin/master
```

The base must resolve to a commit connected to `HEAD`; this scans commits in `base..HEAD`. To scan every ref and commit present in the local clone, run `python -B scripts/secret_gate.py --all-history`. Both invocations also scan current tracked files and non-ignored untracked files. Git-ignored files, submodule contents, and symlink targets are outside the declared scan scope; symlink text is scanned. History scope is limited to the selected range or refs available in the clone.

The gate pins Gitleaks configuration to its built-in default rules, uses an empty ignore file, ignores `gitleaks:allow` annotations, and passes `--redact=100`. It captures the JSON report in memory, prints only a pass/fail status and finding count, and discards the report. It does not write a report artifact. Downloads, staging copies, and the executable live only in temporary directories that are removed after each run. A finding or scanner/tool error fails the gate closed. Do not add broad path exclusions or upload scan reports to Actions artifacts, pull requests, issues, or logs.

GitHub Actions runs the same gate on pull requests to `master`, pushes to `master`, and manual runs, alongside positive and negative synthetic canaries. It uses standard GitHub-hosted Linux and Windows runners, the repository's existing SHA-pinned checkout and Python setup actions, read-only `contents` permission, and no persisted checkout credential. The current repository is public; standard hosted runner use is within GitHub's public-repository allowance. Private forks or changes to runner visibility/plan can have different quotas and should be checked against [GitHub Actions billing rules](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

A scanner result is only a finding count and pass/fail signal, not a safe report for triage. If a possible real credential is detected, stop publication of the affected content and evidence. Keep investigation local and restricted, retain only safe metadata such as the repository revision, scan scope, and finding count, and rotate/revoke through the credential owner's authorized process. Never paste or echo the match, value, filename, or raw report into a public issue, PR, CI log, or agent context. Synthetic test markers are generated at runtime and are never checked against a provider.

### Tool outputs and logs are a separate boundary

Gitleaks scans repository files and Git patches. It cannot prevent or detect a secret delivered directly by a tool, endpoint, runtime environment, or command output before that content is saved as a scanned file. Do not query or dump credential endpoints such as `/api/credential`, token stores, process environments, or authentication headers into logs or evidence. Request only the minimum structured fields needed; keep **raw** outputs local and restricted, derive and redact any shareable evidence, and block publication until the derived material has been checked for sensitive values. File scanning is not protection for secrets already emitted to a model context or terminal log.
