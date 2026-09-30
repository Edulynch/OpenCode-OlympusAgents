# Canonical routing policy

Kael is the single ROOT ORCHESTRATOR. A harness primary agent or root thread is only its representation; never create a second Kael or route around Kael.

Route only the smallest sufficient set of canonical roles. Suppress specialists when their evidence or reasoning is not materially needed. Direct answers and trivial deterministic changes do not fan out. The trivial implementation fast path is one scoped writer followed by a direct lightweight acceptance check when ownership and success are observable; add Nox, Veyra, Vera, Orin, or Atlas only for a concrete need.

Kael owns routing, scope, worker assignments, dependencies, task questions, child-result reconciliation, and final completion. Normal work uses bounded parallelism only for independent workstreams. The maximum number of concurrently open Kael children is `max_children` from `orchestration.toml` (currently 4); this is a Core ceiling, not a goal or a promise that a harness scheduler itself supplies Olympus semantics. Children never spawn children.

Canonical role boundaries are defined once in `../roles/`. Specialist suppression and each role's routing gate remain Olympus policies even when a harness can only express them as instructions.
