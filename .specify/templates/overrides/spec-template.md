# Feature Specification: [FEATURE NAME]

**Feature Branch**: [branch name or N/A]  
**Created**: [DATE]  
**Status**: Draft  
**Documentation Mode**: [Existing (retrospective) / New / Change]  
**Baseline**: [tag, commit, release, or N/A]  
**User Constraints**: [Explicit constraints and boundaries, or "None stated"]  
**Evidence Reviewed**: [repository paths, canonical documents, or runtime evidence; include revision/date]

**Input**: User description: "$ARGUMENTS"

## Scope and Interpretation

- **Existing (retrospective)**: Describe behavior supported by the implementation and cited evidence. Record uncertainty as unknown or unverified. Do not infer missing requirements from templates, prompts, or intended behavior. Keep gaps as observations; they are not authorized implementation work.
- **New**: State the user-authorized new behavior and its boundaries.
- **Change**: State the evidenced current behavior and the user-authorized delta separately.

For New and Change, list what is in and out of the authorized scope and preserve the stated user constraints. For Existing, use the evidenced implementation as the scope and avoid proposing changes.

## User Scenarios & Testing

Use only scenarios relevant to this feature. Priorities help order work; a fixed number of stories or independent deployment of every story is not required.

### User Story 1 - [Brief Title] (Priority: P1)

[Describe the observed workflow for Existing, or the authorized outcome for New/Change.]

**Why this priority**: [Value or N/A when documenting an existing behavior]

**Independent Test**: [Focused observable check for this scenario, or evidence source for Existing; deployment independence is not required.]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [observable outcome]

[Add scenarios or stories only when they add distinct, evidenced or authorized behavior.]

### Edge Cases

- [Relevant boundary, error, or unavailable evidence; omit unrelated generic cases.]

## Requirements

### Functional Requirements

For Existing, write only implementation-backed behavior statements. For New/Change, write testable acceptance requirements for the authorized scope. Number only requirements that exist; do not fill a quota.

- **FR-001**: [Observable behavior or authorized requirement, with evidence or acceptance source where useful]

### Key Entities *(include only if relevant)*

- **[Entity]**: [Meaning and evidenced or required relationships; omit implementation details already defined by canonical sources.]

## Success Criteria

### Measurable Outcomes

For Existing, report measurable outcomes only when evidence supports them; otherwise state the observable outcome or mark it unknown. For New/Change, define observable acceptance outcomes without inventing performance or business targets.

- **SC-001**: [Observable, measurable outcome or explicit unknown]

## Dependencies and Risks

- **Dependencies**: [Relevant existing component, canonical source, or external dependency; otherwise None identified.]
- **Risks**: [Relevant compatibility, authority, installation, or behavior risk; otherwise None identified.]

## Verification Scope

Identify only checks relevant to the behavior and risk. Classify each as **deterministic**, **simulated**, or **real runtime**. This section records evidence available for Existing or focused checks expected for New/Change; it does not claim that a check ran. Record executed outcomes separately in the plan or task results.

| Behavior / boundary | Evidence or focused check | Class | Status (if executed) |
|---|---|---|---|
| [Relevant behavior] | [Path, command, or runtime action] | [Deterministic / Simulated / Real runtime] | [PASS / FAIL / NOT RUN / BLOCKED / unknown] |

## Assumptions

- [Only evidence-backed assumptions or explicitly unverified points; otherwise None identified.]
