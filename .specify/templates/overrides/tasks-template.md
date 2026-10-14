---
description: "Scoped task list for retrospective documentation or authorized implementation"
---

# Tasks: [FEATURE NAME]

**Input**: [spec.md and plan.md links]  
**Documentation Mode**: [Existing (retrospective) / New / Change]  
**Baseline**: [tag, commit, release, or N/A]

## Scope Rules

- **Existing (retrospective)**: Represent the implementation in the spec and plan using evidence. List only authorized documentation work and focused checks needed for those documents. Do not turn existing behavior into implementation tasks, mark it complete without evidence, or create implementation tasks for discovered gaps.
- **New/Change**: List only work remaining within the user's authorized scope. Do not duplicate work already evidenced as complete. Record out-of-scope gaps as observations for separate authorization.
- Use the repository's real paths and preserve ownership, protected-file boundaries, existing mandatory checks, and release requirements.

## Format

`- [ ] T001 [P?] [US1?] Description with exact path`

- **[P]**: Use only when tasks have independent ownership and no dependency.
- **[US#]**: Map to a user story when that traceability is useful; omit otherwise.
- Order tasks by actual dependencies. Add only work groups or phases the feature needs; setup, foundational, polish, or parallel work are not presumed.
- Include focused verification tasks when required by TFR, the user, project, CI, or release contract. Identify the check and expected evidence. Do not impose test-first sequencing, duplicate gates, or a test task for every method.

## Tasks

### [Work group, if useful]

- [ ] T001 [US1] [Action and result] in `[actual/repository/path]`
- [ ] T002 [P] [US1] [Independent action and result] in `[actual/repository/path]`

## Validation Evidence

Record the result of each check when run. Distinguish deterministic, simulated, and real-runtime evidence, and report PASS, FAIL, NOT RUN, BLOCKED, or unknown. Expected results are not execution results.

| Check | Class | Result | Evidence / limitation |
|---|---|---|---|
| [Focused check] | [Deterministic / Simulated / Real runtime] | [PASS / FAIL / NOT RUN / BLOCKED / unknown] | [Command, artifact, and relevant limitation] |

Task completion does not authorize commits, pushes, deployment, release, or changes beyond the stated scope.
