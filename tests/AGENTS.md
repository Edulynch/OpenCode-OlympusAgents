# Tests and qualification

- Add regression tests to the existing suite for the behavior: Python `unittest` modules belong in the relevant `test_*.py` suite (shared CLI/Core coverage is under `harness-core/`), while Windows-specific integration belongs in the existing PowerShell or `.cmd` checks.
- Keep small deterministic fixtures next to the suite that owns them. Use disposable paths for writable state; never reuse a real OpenCode profile, credentials, or a published release when a fixture can establish the contract.
- Run the smallest affected check first. Preserve CI-required test names and selectors, and distinguish mock and static results from actual native execution. See the [qualification guide](../docs/DEVELOPMENT.md#choosing-qualification-by-change-risk).
