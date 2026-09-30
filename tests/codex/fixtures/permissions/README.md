# Disposable permissions smoke fixture

This directory contains synthetic protected-path names only. Copy this fixture,
the project `.codex/config.toml`, `.codex/agents/`, and a disposable `CODEX.md`
into a new temporary Git repository before running a permission smoke. Never
run a negative permission test against the Olympus worktree. Expected cases:

- edit `editable.txt`: ALLOW inside the project profile;
- edit the `opencode.jsonc` decoy: DENY by the project profile;
- write outside the fixture root with `on-request`: ASK only when an interactive
  approval surface can be observed; a non-interactive failure is not proof that
  no approval prompt existed.
