# Phase 3 v2 manual live qualification — NOT executed by Maintenance

Source: candidate `feature/role-purity-iterative-evidence-v2` at the recorded
`SOURCE_HEAD` only. Target: fresh disposable trusted Git project in
`$env:TEMP\opencode\olympus-phase3-v2-live`. Never treat static qualification as
proof of interactive routing. Do not change the installed release or run this
against the development repository.

Use the previously qualified dedicated `opencode serve` with process-local auth
and the known-good native session API parser/family observer in
`tests/completion-gates/live-family.ps1` (its `-ParserTests` can be run without
launching sessions). That observer enforces v2.0.15; the fixture installer on
Sep 26 detected **opencode v2.0.18**. Before any live root, revalidate its
read-only list/get/message/inbox/active/wait API schema and adjust the version
precondition only on evidence; do not simply remove the guard. If preflight or
owned lifecycle observation fails, BLOCK the live test without launching. The
script's default launch scenario is **not** this test:
do not invoke its launch mode against this fixture. Adapt its *inspection*
sequence, not its six-Veyra scenario; do not invent an alternative lifecycle
observer. Ensure the controller can own the server/roots/descendants through
terminal outcomes, collect stdout/stderr and exit codes, and terminate safely
on timeout **before** starting any root. No detached runs. The inspector uses
paginated `session.list(parentID)`, recursive family discovery, per-session
`experimental.session.wait` (idle alone is insufficient), `session.get` outcome
and time.idle, `session.message.list`/export, `session.inbox.list`, and
`session.active`. Re-enumerate the family after joins; verify the Kael final
message consumed both the worker evidence and Sorin's final result. If a
missing parent result occurs, wait for the original known child; unknown child
execution is COMPLETION_UNCONFIRMED, not a retry or fabricated evidence.

## Case A — high-uncertainty, one focused evidence follow-up

Fixture contains `observations/incident.txt` (two conflicting outputs, no
established cause) and `observations/decision.txt` (one narrowly discriminating
fact); the user prompt deliberately supplies only the incident. Request:

> Explicit deep diagnosis, read-only. The attached incident has two conflicting
> observations for the same input and the cause is unknown. Consult Sorin under
> the Diagnostic Gate. Have Sorin decide the *smallest* discriminating fact it
> needs before concluding. Route that evidence through the appropriate direct
> Kael child, then continue the SAME Sorin session with the collected evidence.
> Do not implement, edit, run unrelated tests, or expand beyond observations/.
> Conclude only when the entire required session family is accounted for. The
> incident contents are: expected ROUTE=BLUE, observed ROUTE=RED in trace A,
> observed ROUTE=BLUE in trace B; neither trace has a recorded selector value.

`decision.txt` supplies the missing selector values for the two traces. A
valid Sorin EVIDENCE_REQUEST names Veyra and ONLY that bounded path (or Nox if
it explains a focused runtime discriminating experiment). Kael must validate
the request, not read the file or execute the experiment itself. A direct answer
from Sorin without a request is **not** a Case A pass. The first consultation
and follow-up are the two allowed consultations; same Sorin session ID required.
If evidence is indeterminate, do not send fake results or re-consult Sorin yet.

Expected chain: Kael → Sorin(EVIDENCE_REQUEST) → Kael → Veyra(evidence) →
Kael → same Sorin(ADVICE/diagnostic conclusion) → Kael(final synthesis).
No implementation. Inspect tool calls to verify Kael did **not** do Veyra's
repository reading or Nox's test execution; classify purity PASS / QUESTIONABLE
/ FAIL with specific evidence. Verify worker.parentID = Kael root ID, Sorin
parentID = Kael root ID; no grandchildren. Require terminal reconciled children,
consumed results, family complete, unresolved=0, unknown=0.

## Case B — deterministic negative control

Use a fresh root in the same disposable fixture: ask for the obvious spelling
defect in `simple/header.txt` (actual `REEDY`, expected `READY`), read-only,
without requesting deep diagnosis. Normal bounded handling, Sorin count **0**.
Do not reinterpret task size or the presence of Phase 3 policy as a Diagnostic
Gate condition.

## Case C — role-purity observation

Inspect Case A tool/result chronology. Worker gathers scoped evidence; Sorin
interprets it; Kael coordinates and synthesizes. If Kael reads the requested
file itself or runs the requested test, FAIL. If the exact actor cannot be
determined from available messages/tools, QUESTIONABLE; never infer PASS from a
plausible final answer alone.

## Record (fill only after live execution)

`SOURCE_HEAD`; fixture path/installed-from commit; server/controller identity
and exit; root IDs; Sorin ID; worker IDs/agent/parentIDs; Sorin consultation
count; same Sorin yes/no; original EVIDENCE_REQUEST fields; actual worker
evidence; final Sorin result; final Kael synthesis and consumption evidence;
family complete; unresolved; unknown; Kael purity PASS/QUESTIONABLE/FAIL;
Case B Sorin count; wall-clock; setup/runtime failures and skipped checks.

**Budget boundary:** a synthetic *second* Sorin evidence request on consultation
two cannot also be followed by a final Sorin response without a third call.
The current conservative budget forbids a third **automatic** consultation;
the longer flow can complete only after a separate explicit user-authorized
continuation on terminal/reconciled second evidence. Case A deliberately
requires exactly one follow-up; an unapproved third call
or fabricated terminal result is a failure, not a way to make that separate
two-evidence-round scenario pass.
