# Phase 12 — Cross-Harness Comparison Plan

**Status: PLAN PREPARED · EVALUATION: NOT RUN**

This document defines a future, controlled comparison protocol only. No harness
was run, profiled, ranked, or newly inspected to prepare it. In particular, no
performance baseline or winner is claimed here.

## Preconditions

Begin evaluation only after Phase 11 defects are fixed or explicitly accepted,
there is no material Core routing defect, the user initiates the required fresh
isolated roots and capabilities, and protocol, fixtures, baselines, and
acceptance criteria are frozen. The plan may be prepared while Phase 11 remains
partial or manual-runtime-only; that does not authorize evaluation. Any
interactive need for fresh roots or capabilities is `HUMAN_ACTION_REQUIRED`.

## Ordered protocol

1. **Freeze the comparison contract.** Use identical protocol and task text,
   fixture contents and hashes, baseline IDs and hashes, shared acceptance
   criteria, allowed operations, stop limits, and intervention rules in both
   harnesses. Record the frozen versions before any trial.
2. **Record harness conditions.** Capture harness and model versions,
   configuration, observable capabilities and limitations, and the current
   active-child ceiling (**4**). FAST6 is neither approved nor measured; do not
   raise the ceiling or assume six-way concurrency.
3. **Prepare isolated starts.** For each future authorized run, use fresh,
   isolated roots containing identical copies; reset source and state to the
   frozen baseline. Do not transfer solutions, generated outputs, or other
   trial state between harnesses.
4. **Freeze workload order and repeats.** Use a recorded random seed and
   counterbalanced harness order. Define the repeat policy up front. A retry
   remains part of its original trial, with its reason and actions recorded;
   it must not be relabeled as an independent clean trial.
5. **Run only authorized matched trials.** Collect actual evidence against the
   shared criteria. Mark incomplete, blocked, unconfirmed, unavailable, and
   capability-gap results honestly; never simulate success or silently
   equalize capabilities. Do not run a workload or operation outside the
   authorization and stop limits.
6. **Validate before bounded comparison.** Nox validates matched before/after
   outputs and checks; Vera reviews source/result/session consistency and
   provenance. Compare only evidence that passes review, state limitations,
   and make no unsupported winner claim.

## Capability asymmetries to preserve

These are known capability limits, not merely missing test evidence:

| Capability | OpenCode | Codex |
| --- | --- | --- |
| DENY | Supported | GAP |
| Aegis | Supported | GAP |
| Global runtime discovery | GAP | Supported |

Record each applicable limitation explicitly in trial results. A gap is not a
pass, an inferred equivalent, or proof that an unmeasured feature is absent.
Apply the same shared functional acceptance criteria to both harnesses where
the task is executable; separately report capabilities that cannot be tested
or matched.

## Workloads and shared acceptance

Use four to six workload classes, with their fixtures, exact requests, expected
outputs, checks, and baselines frozen before trials:

1. **Trivial edit:** make exactly the requested change; verify relevant checks
   and that unrelated files remain unchanged; require no gratuitous delegation.
2. **Normal feature:** satisfy specified behavior, pass regression checks, and
   complete the required implementation and validation handoffs.
3. **Functional bug:** reproduce the seeded failure before the change, pass
   after the correction, pass regression checks, and support the cause with
   evidence.
4. **Architecture-heavy task:** meet explicit boundary/interface and behavior
   invariants; use Orin/planning where justified and record why.
5. **Hard diagnosis:** identify the seeded cause using discriminating evidence,
   perform required correction checks, and escalate through the defined gate.
6. **FAST independent tasks:** check each task individually and the combined
   result; require conflict-free changes and observed independence/concurrency
   within the current ceiling. Six-way execution is not presumed or approved.

For every applicable criterion, record `verified`, `incomplete`, `blocked`, or
`unconfirmed`, with evidence. Record unrelated changes and failed checks; do
not count unverified claims as completion.

## Evidence and metrics to record

For each trial retain:

- **Identity/provenance:** fixture and baseline hashes; harness, model, and
  configuration versions; trial ID; order seed; isolated root; and root/child
  session and result IDs.
- **Observed work:** routes, tools, handoffs, consultations, intervention
  counts/reasons/actions, and intervention wait time when known. Distinguish
  observed behavior from model or harness claims.
- **Outcomes:** criterion-level status and evidence, checks, incomplete or
  blocked work, unrelated changes, and capability gaps or `N/A` with source
  evidence links.
- **Time and resources:** defined start/end events and elapsed time; child
  total and peak active count only when observable; consultations and retries.
  Record tokens/context only when exposed, otherwise mark them unavailable.
  Keep intervention wait time separate from elapsed time when measurable.

Do not fabricate numeric baselines or infer unexposed telemetry. As optional
future OpenCode telemetry references, the public [V2 API
docs](https://opencode.ai/v2/docs/api) and [OpenAPI
schema](https://opencode.ai/v2/openapi.json) describe `Session.Info` fields
including `id`, `parentID`, `agent`, `outcome`, `tokens`, `cost`, and `time`;
`TokenUsage.Info` includes input, output, reasoning, cache-read, and cache-write
usage. Experimental aggregate statistics are not proof of any one trial's
numbers. No Codex telemetry format is assumed. These references describe
possible future evidence only; no telemetry was collected for this plan.

## Validation, stop conditions, and human action

Before accepting a matched result, verify identical starts, inputs, and resets;
correlate before/after source and checks with the correct session and result;
and distinguish observations from claims. Stop on a Core defect,
unauthorized scope, fixture/configuration drift, contamination, missing
baseline, or ambiguous provenance. A protected-maintenance record gap or
human-required action is a stop, not a bypass. If explicit user-authorized
maintenance is actually needed, handle it separately; do not automatically
route to `/maintain` or trigger maintenance. Fresh roots and capabilities
require future user initiation (`HUMAN_ACTION_REQUIRED`).
