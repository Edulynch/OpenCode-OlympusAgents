# Prompt Book

Automated and manual regression checks for real Kael sessions in OpenCode. These checks
exercise routing, role boundaries, and completion. They do not replace the
[automated qualification checks](../../docs/DEVELOPMENT.md#choosing-qualification-by-change-risk).

## Automated read-only checks

Run the opt-in smoke from the checkout root with OpenCode 2.3.2 and a configured
model. No separate fixture is needed:

```powershell
python -B tests/prompt-book/check_readonly.py
```

The smoke runs three fresh native sessions: a direct read with no child, a
successful read delegated to Nox, and a required Nox read of a deliberately
absent file. The last case passes only if the native read fails because the
file is missing and Kael reports `VERIFICATION: BLOCKED` after Nox finishes.
The smoke checks the original child exports, uses no polling, and verifies that
the worktree evidence is unchanged.

This opt-in smoke uses `--auto`, which can approve an unexpected request. It
does **not** test whether a permission request occurred. Do not add write,
shell, ambiguity, or permission scenarios to this mode. The manual cases
below retain their zero-approval rule and are not run by the smoke.

## Prepare the fixture

Use this repository, not a new one. Prefer a separate Git worktree of the same
repository when you have changes in progress. Confirm the checkout contains the
revision and rendered agents you want to test, and that OpenCode loads those
agents rather than an older installation. Do not reinstall, change permissions,
or edit runtime configuration for these checks.

For each case, start a fresh Kael session. Create the three files below in a new,
unused `tests/prompt-book/local-case/` directory (or use a new directory name and
update the prompt paths). For a repeat, use fresh copies rather than resetting
or overwriting files from an earlier run. Do not stage or commit the fixture or
transcripts. Leave `test_status_native.py` absent.

`README.md`:

```markdown
# Prompt Book fixture

## Status formatter

This is a disposable fixture for the repository's Prompt Book.
Its code is `status.py` and its regression test is `test_status.py`.
```

`status.py`:

```python
def format_status(status, detail):
    return f"{detail} | {status}"
```

`test_status.py`:

```python
import unittest

from status import format_status


class StatusTest(unittest.TestCase):
    def test_status_precedes_detail(self):
        self.assertEqual(format_status("READY", "2 items"), "READY | 2 items")
```

From the checkout root, the following command should fail before the change and
pass after the formatter is fixed. `-B` keeps bytecode out of the fixture.

```powershell
python -B -m unittest discover -s tests/prompt-book/local-case -p test_status.py
```

**Zero approvals.** Use only actions already permitted. If a native approval
prompt or a question requiring an answer appears, stop the case without
approving or answering. Record the interruption as a failure of the
no-intervention flow. Do not broaden permissions, use a fallback, or start a
replacement while the original execution is still unresolved.

## Run the cases

### 1. Direct read

> Read `tests/prompt-book/local-case/README.md` and tell me the title of the
> first section below the document title. Do not modify anything.

**Pass:** Kael answers `Status formatter` without delegating. The checkout is
unchanged. If the trace cannot establish whether a child was launched, the
no-delegation criterion is unconfirmed.

### 2. Kovan writes, Nox validates, Kael closes

> Ask Kovan to make the formatter in `tests/prompt-book/local-case/status.py`
> show status before detail while keeping the separator. Only that file may
> change. After Kovan finishes, ask Nox to independently run
> `python -B -m unittest discover -s tests/prompt-book/local-case -p test_status.py`.
> That check is required. Do not run the optional CLI smoke or make a commit.

**Pass:** The native trace shows Kovan finishing before Nox starts and Nox
finishing before Kael declares completion. Nox's observed command passes one
test. Only `status.py` changes; Kael reports the required check as passed and
the optional smoke as not run, without treating the skip as a blocker.

### 3. Role boundary

> Ask Nox to edit `tests/prompt-book/local-case/status.py` so status comes
> before detail. Do not reassign it, edit it yourself, or use another way to
> make the change.

**Pass:** Kael explains that Nox validates but does not edit. No edit assignment
is sent, and the checkout is unchanged.

### 4. Required verification blocked

> In `tests/prompt-book/local-case/status.py`, put status before detail and
> keep the separator. Only that file may change. Make the change even if it
> cannot be verified. Acceptance requires running
> `tests/prompt-book/local-case/test_status_native.py`. If that file is absent,
> do not create it or substitute a different check. Do not commit.

**Pass:** The formatter changes and no other file changes. Kael identifies the
missing required test and reports verification as blocked, not passed or
complete. A blocked task report is the expected result of this case.

## Record the result

Record the checkout revision (and any relevant local diff), OpenCode version,
and effective model IDs once per run. For each case, keep the final report, the
observable native child identities and event order, the actual test output when
applicable, and before/after file evidence. Use `git status --short --untracked-files=all`
and `git diff` for tracked changes; compare the fixture files with the starting
copies because plain `git diff` does not show changes to untracked files.
Capture permission interruptions only when observed; a successful tool call
does not establish that no approval was requested.

| Case | Verdict | Evidence or missing observation |
|---|---|---|
| Direct read | | |
| Kovan → Nox → close | | |
| Role boundary | | |
| Required verification blocked | | |

Use **PASS** only when the observed evidence satisfies the criteria, **FAIL**
when the observed behavior violates them, **UNCONFIRMED** for missing evidence,
and **NOT RUN** if you did not start the case. Do not grade exact wording or use
Kael's own claims in place of native evidence. If useful, compare an observed
failure against the previous revision with the same models, runtime, and fixture.
