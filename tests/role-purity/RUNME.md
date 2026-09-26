# Final Phase 3 — USER MANUAL LIVE QUALIFICATION

Candidate: `feature/role-purity-iterative-evidence-final`. Fixture:
`$env:TEMP\opencode\olympus-phase3-final-live`. The fixture is installed
from the **committed candidate HEAD**, not from a development worktree.
OpenCode v2.0.18 read-only schema smoke passed; **no Phase 3 live case has run**.
Evidence for these cases is `NOT_EXECUTED` until the user runs them. The earlier
Issue #2 evidence is `USER_EXECUTED_LIVE_EVIDENCE`, not a task-executed test.

Run these commands in PowerShell 7 **from the candidate repository root**.
Run each `opencode run` in the foreground, then inspect its original root and
whole family. Never substitute an idle root, CLI exit, missing parent result,
or an early assistant reply for terminal, consumed evidence. Do not blindly
repeat a root after an indeterminate outcome. Retain session IDs for review.

```powershell
$source = (Get-Location).Path
$fixture = Join-Path $env:TEMP 'opencode/olympus-phase3-final-live'
$expected = (git rev-parse HEAD).Trim()
if ((Get-Content (Join-Path $fixture 'SOURCE_HEAD') -Raw).Trim() -ne $expected) { throw 'Fixture is not installed from this candidate HEAD' }
if ((opencode --version | Out-String).Trim() -ne 'opencode v2.0.18') { throw 'Revalidate observer for the current version first' }
pwsh -NoProfile -File (Join-Path $source 'tests/completion-gates/live-family.ps1') -SchemaSmoke -SmokeSession ses_f312f7e87ffeeJxE1dEVfZTbVz
if ($LASTEXITCODE -ne 0) { throw 'Observer preflight failed: do not launch live cases' }
Set-Location $fixture
```

The historical smoke session ID above is a read-only schema example from the
installed runtime. If it is no longer accessible, use an existing completed
Kael root with terminal child and two assistant responses; do **not** launch
an agent merely to satisfy schema smoke. Record any preflight limitation.

## Case A — high uncertainty, one evidence round

```powershell
$promptA = @'
Read-only deep diagnosis. The complete incident evidence is: expected ROUTE=BLUE for the same input; trace A observed ROUTE=RED; trace B observed ROUTE=BLUE; neither trace recorded the selector value. The cause is genuinely unknown from this packet alone. Consult Sorin under the existing Diagnostic Gate to identify the smallest discriminating fact; do not read observations/decision.txt yourself. If Sorin requests bounded evidence, validate its role/scope/value, route ONE direct Veyra evidence worker for observations/decision.txt, reconcile the ORIGINAL worker's actual terminal result, then continue the SAME Sorin session with that evidence for a final advisory result. Do not implement, edit, run unrelated tests, add a third automatic Sorin consultation, route Maintenance, or broaden outside observations/. Synthesize only after all required results are terminal, reconciled, collected and consumed. Report the Sorin ID and worker ID, plus any uncertainty rather than claiming completion prematurely.
'@
$titleA = 'phase3-final-A-' + [guid]::NewGuid().ToString('N')
$eventsA = @(opencode run --agent kael --title $titleA --format json $promptA)
if ($LASTEXITCODE -ne 0) { Write-Warning 'CLI failed: do not launch a replacement; reconcile original session first' }
$idsA = @($eventsA | ForEach-Object { try { ($_ | ConvertFrom-Json).sessionID } catch { $null } } | Where-Object { $_ } | Select-Object -Unique)
if ($idsA.Count -ne 1) { throw 'Root identity uncertain; do not retry or mark complete' }
$rootA = $idsA[0]
pwsh -NoProfile -File (Join-Path $source 'tests/completion-gates/live-family.ps1') -InspectSession $rootA -InspectCase A -TimeoutSeconds 1200
if ($LASTEXITCODE -ne 0) { throw 'Case A family unresolved/failed; do not claim live PASS or auto-retry' }
opencode api GET "/api/session/$rootA/message"
opencode api GET "/api/session?parentID=$rootA&limit=100"
```

Manually inspect child messages using
`opencode api GET "/api/session/<CHILD_ID>/message"` for **each** observed
Sorin/worker ID. Require a true `STATUS: EVIDENCE_REQUEST` with all five fields,
one direct Veyra evidence child, material selector evidence, the **same Sorin
session** returning final `ADVICE` after that evidence, two actual consultations
not three, and Kael's subsequent synthesis consuming both results. Inspect root
tool chronology: Kael coordinates; Sorin reasons; Veyra reads the decision file.
If Kael reads it instead, Sorin spawns a child, or the worker fails without a
reconciled result, FAIL. Structural observer pass alone is **not** live PASS.
Record family complete, unresolved=0, unknown=0 and IDs/roles/parentIDs.

## Case B — deterministic negative control

```powershell
$promptB = 'Read-only straightforward defect check of simple/header.txt: required value READY; identify its actual spelling and report the one bounded correction without editing. This is not deep diagnosis. Use normal bounded worker evidence where useful; do not consult Sorin or Maintenance. Reconcile all original children and synthesize only after family completion.'
$titleB = 'phase3-final-B-' + [guid]::NewGuid().ToString('N')
$eventsB = @(opencode run --agent kael --title $titleB --format json $promptB)
if ($LASTEXITCODE -ne 0) { Write-Warning 'CLI failed: reconcile original; do not blindly retry' }
$idsB = @($eventsB | ForEach-Object { try { ($_ | ConvertFrom-Json).sessionID } catch { $null } } | Where-Object { $_ } | Select-Object -Unique)
if ($idsB.Count -ne 1) { throw 'Root identity uncertain; do not retry' }
$rootB = $idsB[0]
pwsh -NoProfile -File (Join-Path $source 'tests/completion-gates/live-family.ps1') -InspectSession $rootB -InspectCase B -TimeoutSeconds 1200
if ($LASTEXITCODE -ne 0) { throw 'Case B family unresolved/failed; do not claim PASS' }
opencode api GET "/api/session/$rootB/message"
opencode api GET "/api/session?parentID=$rootB&limit=100"
```

Require zero Sorin sessions and zero Sorin consultations, normal bounded worker
flow, full family reconciliation, no Maintenance and no unrelated edits. User
review of the messages is required; `STRUCTURAL_PASS_REVIEW_REQUIRED` is not a
policy PASS or evidence that any of these agent cases ran during preparation.
