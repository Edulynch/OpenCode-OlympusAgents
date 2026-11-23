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

The smoke runs three fresh native sessions: closed arithmetic with zero root
tools or children, a successful read delegated to Nox, and a required Nox read
of a deliberately absent file. The last case passes only if the native read
fails because the file is missing and Kael reports `VERIFICATION: BLOCKED`
after Nox finishes. The smoke checks the original child exports, uses no
polling, and verifies that the worktree evidence is unchanged.

The two Nox read cases use `--auto`, which can approve an unexpected request. The smoke
does **not** test whether a permission request occurred. It does not run the
write comparison below. The manual cases retain their zero-approval rule and
are not run by the smoke.

### Before/after native routing comparison

Use the same checkout, OpenCode version, and configured default model for both
commands. First run the baseline against the unchanged generated agents; then
render the candidate agents outside this runner and run the candidate command:

```powershell
python -B tests/prompt-book/check_readonly.py --compare baseline
python -B tests/prompt-book/check_readonly.py --compare candidate
```

Both commands use the same three prompts and session titles, with no `--auto`,
permission override, cache manipulation, or Git mutation. The runner does not
render agents. Baseline output records the observed topology and violations;
it is an observation, **not** a candidate `PASS`. A nonzero command or
unrecognized trace leaves that case unconfirmed. Permission UI or a user's
decision is not inferred from an exit status; record those only when directly
observed.

The comparison recognizes a permission-request notice on either stdout or
stderr, a `permission.rejected` marker in the run trace, and the same marker in
original session exports. An observed no-auto request/rejection fails candidate
acceptance; the runner never approves it. `not-observed` means only that these
evidence channels contained no marker, not that no permission UI appeared.

The three comparison prompts are:

1. Compute `19 + 23`; the expected final field is `ANSWER: 42`, with no root
   tool calls or child.
2. Find the next level-two section heading after `Automated read-only checks`
   in this version-controlled README. The prompt does not give the answer or
   prescribe a role. The candidate expects one original Veyra child to read this
   file, with no root technical search; at most one exact root-only probe may
   precede dispatch. The original child must be terminal before Kael's final
   answer. Baseline reports whether the correct answer came from the previous
   root read or from Veyra, plus the observed tool counts.
3. Replace the contents of the exclusively created
   `tests/prompt-book/.routing-fixture/status.txt` with exactly
   `READY | 2 items` and a newline. The candidate expects permitted exact
   ownership/manifest preflight reads, one original Kovan, a focused Kovan read
   after the edit, a successful child terminal, and only this fixture effect.
   The runner checks exact LF bytes, refuses parent escapes, reparse points,
   hardlinks, and unexpected entries, and removes only the safe fixture in its
   exclusively created directory after terminal results are confirmed. It then
   compares repository evidence by naming changed `git status`, `git diff`, or
   README-byte channels; this does not attribute a cause or print the worktree.
   If the fixture path already exists, the runner refuses to inspect or alter
   it. If execution is uncertain or safety checks fail, it retains the fixture
   for reconciliation rather than deleting unexpected state.

Each comparison prints one `USAGE` JSON line per task with per-session and
summed counters: `input`, `cache_read`, `cache_write`, `output`, and `reasoning`.
The runner reads each known original session export once in memory and prints
the tool names, model IDs, and counts, not the transcript. Compare matching
cases and model configurations. `null` means not exposed; a zero cost from
OpenCode is not proof of zero billing or of savings.

## Prepare the fixture

Use this repository, not a new one. Prefer a separate Git worktree of the same
repository when you have changes in progress. Confirm the checkout contains the
revision and rendered agents you want to test, and that OpenCode loads those
agents rather than an older installation. Do not reinstall, change permissions,
or edit runtime configuration for these checks.

For each case, start a fresh Kael session. Create the three files in a new,
unused `tests/prompt-book/local-case/` directory (or use a new directory name and
update the prompt paths). For a repeat, use fresh copies rather than resetting
or overwriting files from an earlier run. Do not stage or commit the generated
case or transcripts. Leave `test_status_native.py` absent.

From the checkout root, copy the versioned templates into the new directory.
The `.py.template` suffix is removed for the two Python files:

```powershell
$fixture = "tests/prompt-book/local-case"
if (Test-Path -LiteralPath $fixture) { throw "$fixture already exists; choose a fresh directory" }
New-Item -ItemType Directory -Path $fixture | Out-Null
Copy-Item -LiteralPath tests/prompt-book/templates/README.md -Destination "$fixture/README.md"
Copy-Item -LiteralPath tests/prompt-book/templates/status.py.template -Destination "$fixture/status.py"
Copy-Item -LiteralPath tests/prompt-book/templates/test_status.py.template -Destination "$fixture/test_status.py"
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

### 1. Closed arithmetic routing

> Compute 19 + 23. In your final response include the field `ANSWER` with the
> value `42`.

**Pass:** Kael returns `ANSWER: 42` with no root tool calls or child. The
checkout is unchanged. If the native trace is missing or incomplete, zero
tool calls are unconfirmed.

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
| Closed arithmetic routing | | |
| Kovan → Nox → close | | |
| Role boundary | | |
| Required verification blocked | | |

Use **PASS** only when the observed evidence satisfies the criteria, **FAIL**
when the observed behavior violates them, **UNCONFIRMED** for missing evidence,
and **NOT RUN** if you did not start the case. Do not grade exact wording or use
Kael's own claims in place of native evidence. If useful, compare an observed
failure against the previous revision with the same models, runtime, and fixture.
