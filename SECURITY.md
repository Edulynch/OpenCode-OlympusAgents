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
