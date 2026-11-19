# Uninstall entrypoints

- Keep compatibility entrypoints under `global/`; `global/opencode.ps1` forwards to the installed Olympus CLI. Keep removal and recovery logic in the existing engines.
- Preserve the ownership boundary: the uninstall command must not remove unrelated files or override later user preferences. Do not add a recursive cleanup fallback to an entrypoint.
- Verify removal behavior with the disposable fixtures described in the [development guide](../docs/DEVELOPMENT.md), not against a real user profile. Put user instructions in the [installation guide](../docs/INSTALLATION.md).
