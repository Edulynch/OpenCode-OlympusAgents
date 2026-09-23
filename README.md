<div align="center">

# 🏛️ OpenCode Olympus Agents

### Give OpenCode a team — not one giant prompt.

**One task ≠ one model doing everything.**

<p>
  <img src="https://img.shields.io/badge/OpenCode-V2-F97316?style=flat-square" alt="OpenCode V2" />
  <img src="https://img.shields.io/badge/Master-GPT--6%20Sol%20High-7C3AED?style=flat-square" alt="GPT-6 Sol High" />
  <img src="https://img.shields.io/badge/Workers-GPT--6%20Luna%20Max-2563EB?style=flat-square" alt="GPT-6 Luna Max" />
  <img src="https://img.shields.io/badge/Sorin-GPT--6%20Sol%20XHigh-B91C1C?style=flat-square" alt="GPT-6 Sol XHigh" />
  <img src="https://img.shields.io/badge/Validation-zero--prompt-16A34A?style=flat-square" alt="Zero-prompt validation" />
  <img src="https://img.shields.io/badge/Phase%204C-14%2F14%20PASS-059669?style=flat-square" alt="Phase 4C 14/14 PASS" />
  <img src="https://img.shields.io/badge/Windows-PowerShell%207-0078D4?style=flat-square&logo=powershell&logoColor=white" alt="Windows PowerShell 7" />
</p>

A thin orchestration layer for **OpenCode V2** that coordinates specialized agents, bounded writes, real validation, review, parallel work, and deep diagnostic escalation.

No custom scheduler. No agent database. No fake runtime inside the runtime.  
**OpenCode executes. The orchestrator decides who should do what.**

<p>
  <a href="#-quick-start">🚀 Quick Start</a> •
  <a href="#-meet-the-team">🤖 Agents</a> •
  <a href="#-zero-prompt-validation">⚡ Validation</a> •
  <a href="#-safety-model">🛡️ Safety</a> •
  <a href="#-project-bootstrap">📦 Bootstrap</a> •
  <a href="#-qualification-status">🧪 Qualification</a>
</p>

</div>

---

## 💥 The Problem

A single coding agent can do a lot.

It can also become the researcher, architect, programmer, tester, reviewer, debugger, project manager, and shell operator **all at once**. 😵‍💫

That often becomes one of these:

~~~text
"Do everything."

→ giant context
→ mixed responsibilities
→ unclear ownership
→ hard-to-review changes
~~~

or:

~~~text
"Can I run this?"
"Can I edit that?"
"Can I run the test?"
"Can I run the same test again?"

→ human becomes the approval button 🤦
~~~

The OpenCode Olympus Agents team takes another route:

> **Delegate narrowly, write inside explicit scope, validate with evidence, and escalate only when the problem is actually hard.**

---

## 🧠 The Solution

Give each role one job.

~~~text
You
 │
 ▼
👑 Kael — Master Orchestrator
 │
 ├── 🔭 Veyra — Researcher      → discover evidence
 ├── 📐 Orin — Architect       → define boundaries
 ├── 🔨 Kovan — Implementer     → write inside WRITE_SCOPE
 ├── 👁️ Nox — Tester          → run approved validation
 ├── ⚖️ Vera — Reviewer        → review without rewriting
 └── 🧭 Sorin — Deep Diagnostician → advise through the Diagnostic Gate
~~~

The normal path stays intentionally boring:

~~~text
request
  ↓
Kael
  ↓
Kovan
  ↓
Nox
  ↓
Vera
  ↓
DONE ✅
~~~

Research, architecture, background work, retries, and Sorin are used **only when they add value**.

---

## 🔧 Maintainer Plane

Olympus has **seven normal operational agents**. `maintenance` is a hidden internal
control plane for **explicit user-authorized repository administration**, not an
eighth team member or a normal feature-routing option.

~~~text
User → /maintain → hidden Maintenance child → result back to Kael
~~~

~~~text
/maintain prepare the repository for release
/maintain rewrite the requested Git history
/maintain run repository qualification and report findings
~~~

Only the user opens this path with `/maintain`. Kael cannot invoke Maintenance;
it may relay a completed result but cannot automatically expand the task.

---

## 🤖 Meet the Team

| Role | Current qualified model | What it owns |
|---|---|---|
| 👑 **Kael — Master Orchestrator** | GPT-6 Sol High | Routing, contracts, barriers, retries, completion |
| 🔭 **Veyra — Researcher** | GPT-6 Luna Max | Read-only discovery and evidence |
| 📐 **Orin — Architect** | GPT-6 Luna Max | Read-only design, boundaries and decomposition |
| 🔨 **Kovan — Implementer** | GPT-6 Luna Max | The only normal repository writer |
| 👁️ **Nox — Tester** | GPT-6 Luna Max | Read-only source + exact validation commands |
| ⚖️ **Vera — Reviewer** | GPT-6 Luna Max | Correctness, scope, security and regression review |
| 🧭 **Sorin — Deep Diagnostician** | GPT-6 Sol XHigh | Exceptional deep diagnosis and execution advice |

> 🧩 The roles are the architecture. The model IDs are configuration.

The current GPT-6 mapping is the **qualified baseline**, not a permanent architectural dependency on those names.

---

## 🚀 Quick Start

### 1. Requirements

- Git
- OpenCode V2
- PowerShell 7 on Windows
- Access to the configured OpenAI models

### 2. Preview installation

From this repository:

~~~powershell
pwsh ./scripts/bootstrap.ps1 `
  -Target "C:\path\to\your-project" `
  -DryRun
~~~

Dry run reports the target, detected stacks, validation policy, planned files, warnings, conflicts, and status.

No project files are installed during DryRun.

### 3. Bootstrap the project

~~~powershell
pwsh ./scripts/bootstrap.ps1 `
  -Target "C:\path\to\your-project"
~~~

Running bootstrap is the explicit trust action for that repository.

No extra approval loop:

~~~text
"Do you trust this project? Y/N"
~~~

### 4. Open the target repository

~~~powershell
cd C:\path\to\your-project
opencode
~~~

Then ask for real work normally:

~~~text
Add pagination to the users endpoint.

Keep the existing response contract.
Add tests for the new pagination behavior.
~~~

The orchestration layer decides the smallest useful execution path.

---

## 💬 Show Me the Flow

A normal feature:

~~~text
You:
"Add validation for duplicate usernames."

Master:
→ defines a bounded implementation contract

Implementer:
→ changes only the authorized files

Tester:
→ runs the exact project validation commands

Reviewer:
→ checks correctness, scope and regressions

Master:
→ verifies evidence
→ DONE ✅
~~~

A harder failure:

~~~text
Tester:      ❌ failure
Implementer: 🔁 bounded retry
Tester:      ❌ same unexplained symptom
Master:      root cause still unclear
Sorin:      🧭 diagnostic advisory
Master:      RETRY / ESCALATE / BLOCKED
~~~

Sorin does not take over the workflow.

It advises.  
**Master remains the coordinator.**

---

## ⚡ Zero-Prompt Validation

The Tester can execute known validation commands without turning the user into a human CAPTCHA.

~~~text
known validation command
        ↓
      ALLOW ✅
        ↓
execute without permission prompt
~~~

Unknown or dangerous command:

~~~text
unknown / unsafe command
        ↓
      DENY ⛔
        ↓
no execution
no interactive ASK
~~~

### Examples

~~~text
npm test        ✅
npm run lint    ✅
pytest          ✅
flutter test    ✅
cargo test      ✅
go test ./...   ✅

npm install     ⛔
git clean       ⛔
rm -rf ...      ⛔
cmd /c *        ⛔
pwsh -Command * ⛔
~~~

The generated Tester policy is:

~~~text
safe Git baseline
+
detected relevant validation commands
+
DENY everything else
~~~

No broad shell wildcard allow.  
No shell ASK fallback.  
No dependency installation.

---

## 🛡️ Safety Model

Security is layered.

### 🎛️ Master is read-only

~~~text
edit   → DENY
shell  → DENY
~~~

Master coordinates. It does not secretly become the implementer.

### 🔨 Kovan — Implementer

Each write task requires an explicit scope:

~~~text
WRITE_SCOPE:
src/users/UserService.java
src/users/UserServiceTest.java
~~~

Native edit capability is the outer repository boundary.

**WRITE_SCOPE is the task-level ownership boundary.**

### 🔒 Protected paths

The Implementer cannot normally modify:

~~~text
.git/
.opencode/
opencode.json
opencode.jsonc
*.env
*.env.*
~~~

The env example exception remains available for documentation/example configuration.

### 🧹 No mystery cleanup

The runtime does not solve problems by reaching for:

~~~text
git clean
git reset --hard
rm -rf
rd /s /q
Remove-Item -Recurse <mystery path>
~~~

Validation may leave normal ignored build/cache output behind.

That is preferable to a "helpful" cleanup destroying user work. 🙂

---

## ✍️ WRITE_SCOPE

Repository-wide native writer access does **not** mean task-wide ownership.

A writer contract must be:

- repository-relative;
- explicit;
- non-empty;
- non-absolute;
- non-traversing;
- outside protected paths;
- compatible with DO_NOT_TOUCH;
- available under the writer ownership ledger.

Example:

~~~text
TASK_ID: user-validation-01
ROLE: kovan

WRITE_SCOPE:
src/users/UserValidator.ts
tests/users/UserValidator.test.ts

DO_NOT_TOUCH:
package.json
database/**
.opencode/**
~~~

If another writer already owns an overlapping or ambiguous scope, concurrent writing is denied.

Only proven **DISJOINT** writers may run concurrently.

---

## ⚙️ Parallel Work & Barriers

Independent tasks can run in parallel through native OpenCode child sessions.

~~~text
        ┌─ Research A ─┐
Master ─┤              ├─ barrier → continue
        └─ Research B ─┘
~~~

Disjoint writers:

~~~text
writer A → src/a/**     ┐
                        ├─ parallel ✅
writer B → src/b/**     ┘
~~~

Overlapping writers:

~~~text
writer A → src/**
writer B → src/a/file.ts

→ overlap ⛔
→ serialize
~~~

The project does not build its own scheduler, daemon, mailbox, session database, or polling runtime.

**OpenCode V2 remains the runtime.**

---

## 🧭 Sorin — Deep Diagnostician

Sorin is not "the smart model for big tasks."

It exists for evidence-backed uncertainty:

- 🕵️ root cause unknown;
- ⚔️ conflicting evidence;
- 🔁 repeated bounded failures;
- 🖥️ CI/local mismatch;
- 🎲 intermittent or flaky behavior;
- 🤔 retry vs escalation ambiguity;
- ⚠️ high-risk execution ambiguity;
- 🧑‍💻 explicit deep-diagnosis request.

A big feature alone is **not** a reason to invoke Sorin.

Sorin stays:

~~~text
read-only
shell denied
edit denied
subagent denied
~~~

It recommends the next bounded action. It does not implement the fix.

---

## 📦 Project Bootstrap

The PowerShell bootstrap installs a project-specific orchestration setup and selects validation from repository evidence.

Supported detection currently includes:

| Stack | Evidence examples |
|---|---|
| 🟢 Node | package.json, lockfiles |
| 🐍 Python | pyproject.toml, pytest.ini, related config |
| ☕ Maven | pom.xml, Maven wrapper |
| 🐘 Gradle | build.gradle, build.gradle.kts, Gradle wrapper |
| 🦋 Flutter / Dart | pubspec.yaml |
| 🦀 Rust | Cargo.toml |
| 🐹 Go | go.mod |

### Node scripts are intentionally selective

Given:

~~~json
{
  "scripts": {
    "test": "...",
    "lint": "...",
    "build": "...",
    "deploy": "...",
    "banana": "..."
  }
}
~~~

Bootstrap may authorize:

~~~text
npm test
npm run lint
npm run build
~~~

It does **not** automatically authorize:

~~~text
npm run deploy
npm run banana
~~~

just because those scripts exist. 🍌

---

## 🧭 Package Manager Detection

Node package-manager evidence includes:

~~~text
package-lock.json  → npm
pnpm-lock.yaml     → pnpm
yarn.lock          → yarn
bun.lock / bun.lockb → bun
packageManager     → declared manager
~~~

Conflicting evidence fails safely:

~~~text
AMBIGUOUS_PACKAGE_MANAGER
~~~

It does not flip a coin and hope for the best. 🎲❌

---

## 🧾 Managed Installation

Bootstrap creates a small project-local installation manifest under:

~~~text
.opencode/orchestrator-install.json
~~~

It records installation ownership, source commit, managed-file hashes, detected stacks, package manager, and generated validation commands.

### ♻️ Idempotency

~~~text
bootstrap
bootstrap again

→ NO_CHANGES ✅
~~~

### 🚨 Drift detection

If a managed installed file was manually changed:

~~~text
MANAGED_FILE_DRIFT
~~~

Bootstrap stops instead of silently replacing it.

The hidden maintenance agent and `/maintain` command are managed installation
assets too: their hashes are recorded in the same manifest and drift blocks
reinstallation. Existing managed installations receive them on safe update.

---

## ☁️ OneDrive / Reparse-Point Safety

Windows cloud folders can carry reparse metadata even when they do **not** redirect outside the repository.

Qualification verified the distinction between:

~~~text
OneDrive / cloud-files reparse metadata
→ containment preserved
→ allowed ✅
~~~

and:

~~~text
junction / redirect escaping target
→ rejected before installation ⛔
~~~

Because on Windows, "ReparsePoint" does not automatically mean "dangerous symlink."

---

## 🧪 Qualification Status

The current baseline has been qualified in stages.

| Phase | Focus | Result |
|---|---|---:|
| 3A | Model + orchestration baseline | ✅ PASS |
| 3B | Diagnostic escalation | ✅ PASS |
| 4A | Generic real-repository writes | ✅ 10/10 |
| 4B | Zero-prompt safe validation | ✅ 12/12 |
| 4C | Bootstrap + stack-aware installation | ✅ 14/14 |

Latest Phase 4C qualification environment:

~~~text
OpenCode   v2.0.14
PowerShell 7.6.6
Windows
~~~

Run the qualification harness:

~~~powershell
pwsh ./tests/phase4c/qualify.ps1
~~~

Phase 4C covers:

- ✅ dry run;
- ✅ fresh install;
- ✅ idempotency;
- ✅ Node script selection;
- ✅ package-manager ambiguity;
- ✅ multi-stack projects;
- ✅ foreign config conflicts;
- ✅ dirty worktrees;
- ✅ unsafe paths and escaping junctions;
- ✅ unavailable validation tools;
- ✅ generated Tester policy;
- ✅ effective model mapping;
- ✅ managed-file drift;
- ✅ target security.

The Maintainer Plane extension checks installation, effective agent permissions,
Kael's routing boundary, command definition, idempotency, safe managed upgrades,
and drift. Interactive command dispatch is **not** certified by the PowerShell
harness. In a normal Kael UI session, check it separately:

~~~text
/maintain report the current branch, HEAD, origin URL, and tags. Do not modify anything.
Delegate specifically to agent ID "maintenance" and report the current branch.
~~~

The first should run a hidden child with native shell, no permission prompt,
return its result, and leave Kael as parent; the second must be denied. Record
the interaction result separately rather than counting static checks as a pass.

---

## ✅ Completion Gate

"Agent finished typing" is not DONE.

~~~text
IMPLEMENTED
+
VALIDATION PASSED
+
NO BLOCKING / MATERIAL REVIEW FINDINGS
+
ACCEPTANCE VERIFIED
=
DONE ✅
~~~

Master returns the smallest evidence-backed decision:

~~~text
ACCEPT
RETRY
ESCALATE
BLOCKED
~~~

Worker recommendations are evidence.

**Master owns completion.**

---

## 🔁 Bounded Retries

A corrective retry requires:

- concrete new evidence;
- same role/task/scope;
- a bounded defect.

Whenever possible, the same Implementer session continues.

The orchestrator does not keep sending the same prompt and hoping the universe feels different this time. 😅

If bounded retries stop explaining the problem, that can become evidence for Sorin.

---

## 🧬 How It Works

~~~mermaid
flowchart TD
    U[🧑 Developer request] --> M[👑 Kael — Master Orchestrator]
    M -->|when useful| R[🔭 Veyra — Researcher]
    M -->|when useful| A[📐 Orin — Architect]
    R --> M
    A --> M
    M --> I[🔨 Kovan — Implementer]
    I --> T[👁️ Nox — Tester]
    I --> V[⚖️ Vera — Reviewer]
    T --> M
    V --> M
    M -->|Diagnostic Gate| S[🧭 Sorin]
    S --> M
    M --> D{Completion Gate}
    D -->|pass| DONE[✅ DONE]
    D -->|bounded defect| RETRY[🔁 RETRY]
    D -->|authority or uncertainty| ESC[🚨 ESCALATE / BLOCKED]
~~~

---

## 🧩 Responsibility Boundaries

OpenCode Olympus Agents owns **coordination**, not the entire software lifecycle.

~~~text
EvoDriven        → decide WHY / WHAT
EvoSpec          → define + track specifications
ChangeBudget     → govern allowed change
ProjectMemory    → remember durable project knowledge
OpenCode
Orchestrator     → coordinate execution
~~~

**One noun → one authority.**

This repository does not try to absorb product strategy, specification authority, persistent project memory, or change-budget governance.

---

## 🚫 Deliberate Non-Goals

This project does **not** want to become:

- ❌ another coding-agent runtime;
- ❌ a scheduler or daemon;
- ❌ a session database;
- ❌ an agent mailbox;
- ❌ a workflow DSL;
- ❌ a custom runtime replacing OpenCode permissions;
- ❌ a persistent memory database;
- ❌ a product-management framework;
- ❌ an automatic dependency installer;
- ❌ a sandbox for arbitrary untrusted repositories;
- ❌ a "give every agent shell access and pray" framework.

The orchestration layer should stay **thin**.

---

## 🗂️ Project Structure

~~~text
.
├── opencode.jsonc
├── .opencode/
│   └── agents/
│       ├── kael.md
│       ├── veyra.md
│       ├── orin.md
│       ├── kovan.md
│       ├── nox.md
│       ├── vera.md
│       ├── sorin.md
│       └── maintenance.md  (hidden; /maintain only)
│   └── commands/
│       └── maintain.md
├── scripts/
│   └── bootstrap.ps1
└── tests/
    ├── fixtures/
    └── phase4c/
        └── qualify.ps1
~~~

---

## 🛠️ Development

Inspect effective agents:

~~~powershell
opencode debug agents
~~~

Inspect effective config:

~~~powershell
opencode debug config
~~~

Run bootstrap qualification:

~~~powershell
pwsh ./tests/phase4c/qualify.ps1
~~~

Preview a target installation:

~~~powershell
pwsh ./scripts/bootstrap.ps1 `
  -Target "C:\path\to\project" `
  -DryRun
~~~

---

## 🚦 Current Status

### ✅ Qualified

Core orchestration, generic writing, zero-prompt validation, diagnostic escalation, and project bootstrap are qualified.

### 🐕 Next: real-world dogfood

The next milestone is deliberately **not another architecture phase**.

~~~text
bootstrap a real project
        ↓
give it a real feature
        ↓
watch the full workflow
        ↓
fix only problems reality exposes
~~~

The real success metric is not "how many agents can run."

It is:

> **Can you give the system meaningful work and mostly leave it alone?** 🚀

---

<div align="center">

### 🎛️ Coordinate narrowly. Validate for real. Escalate only when necessary.

**OpenCode runs the agents. The orchestrator keeps them from becoming a committee meeting.** 😄

</div>
