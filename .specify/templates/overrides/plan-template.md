# Implementation Plan: [FEATURE]

**Branch**: [branch name or N/A] | **Date**: [DATE] | **Spec**: [link]  
**Documentation Mode**: [Existing (retrospective) / New / Change]  
**Baseline**: [tag, commit, release, or N/A]

**Input**: Feature specification for `[FEATURE NAME]`

## Summary

For Existing, summarize the evidenced design and implementation as built. For New/Change, summarize the authorized behavior and the simplest suitable technical approach. Separate known facts, proposed design, and unresolved questions.

## Technical Context

Record only details relevant to this feature and supported by repository or runtime evidence. Use `N/A` where a dimension does not apply and `Unknown` where evidence is missing; do not infer project-wide architecture from a narrow change.

**Affected language/platform**: [Relevant versions or N/A]  
**Dependencies and integrations**: [Relevant items or N/A]  
**Data and storage**: [Relevant behavior or N/A]  
**Existing test and verification tools**: [Relevant tools or Unknown]  
**Constraints and compatibility**: [Relevant constraints or N/A]  
**Scale or performance targets**: [Only documented or authorized targets; otherwise N/A]

## Constitution Check

This is a traceability record, not an added approval gate. Note applicable principles, evidence, and any known limitation. Do not claim runtime enforcement or adapter parity without evidence.

| Principle or constraint | Plan alignment and evidence | Open limitation |
|---|---|---|
| [Applicable principle] | [Evidence or planned handling] | [None / specific unknown] |

## Design

Describe the existing design for Existing, or the proposed design for New/Change.

## Project Structure

List only actual repository paths involved in the authorized scope; do not create a standard `src/`, `services/`, or `tests/` structure by template convention.

```text
[Relevant existing paths and their role]
```

**Structure decision**: [Why this scope fits the existing architecture and ownership boundaries.]

### Supporting Design Artifacts

Include research, data models, contracts, quickstarts, or other artifacts only when they answer a concrete question or document a material boundary. Reference canonical Olympus/Core documents instead of copying their role, model, policy, capability, installer, or release details.

## Dependencies and Risks

- **Dependencies**: [Required existing component or external dependency, with evidence; otherwise None identified.]
- **Risks**: [Relevant functional, compatibility, authority, installation, or runtime risks; otherwise None identified.]
- **Mitigation**: [Smallest justified response or N/A.]

## Validation Strategy

Select focused checks using TFR and the risks in the spec. Preserve applicable project and release gates. Classify every check as deterministic, simulated, or real runtime. Keep planned checks distinct from executed results; a fixture or static inspection does not establish live runtime behavior.

| Behavior / boundary | Check and reason | Class | Expected outcome | Executed status and evidence |
|---|---|---|---|---|
| [Relevant behavior] | [Existing check or focused command/action] | [Deterministic / Simulated / Real runtime] | [Expected observable outcome] | [NOT RUN until executed; then PASS / FAIL / BLOCKED / unknown with evidence] |

## Complexity Tracking

Record only a concrete added dependency, abstraction, service, agent, or layer that needs justification. Omit this section's table when there is no such decision.

| Addition | Concrete need | Simpler option considered and evidence |
|---|---|---|
| [Item] | [Need] | [Why simpler option does not meet it] |
