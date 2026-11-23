# Release tests and qualification

- Keep release policy unit tests offline, deterministic, and standard-library-only. Use fake push/PR/tag/release metadata; never query or mutate GitHub from the unit suite.
- Candidate qualification uses `qualify.ps1 -ExpectedVersion`; when OpenCode is mocked, label it as mocked and do not claim native runtime evidence.
- `verify-public-install.ps1` fetches only the exact canonical annotated tag into a disposable local ref, checks its peeled commit, and runs the tagged tree with isolated temporary roots. It does not run with a write token or touch a real profile.
- Public latest-endpoint install/VerifyOnly/uninstall is a separate acceptance gate. Do not replace it with local-source, dry-run, or mock evidence.
- Run the focused Python unit contract, `tag-transition-stability.ps1`, docs checker, and `git diff --check` when their acceptance criteria are changed. Hosted workflow/status attribution remains a separate gate.
