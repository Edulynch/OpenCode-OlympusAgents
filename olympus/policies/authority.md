# Canonical authority semantics

- **ALLOW** — the exact operation is already authorized inside the current task's scope and applicable Olympus boundaries. Proceed without duplicate textual pre-approval.
- **ASK** — the operation is legitimate but requires the runtime/user's approval. Approval is the consent point, not advance authorization; refusal or cancellation stops the operation without fallback or bypass.
- **DENY** — the operation crosses a protected Olympus, user-prohibition, or otherwise non-elevatable boundary. Ordinary grants, approvals, role prompts, retries, or harness adaptation cannot elevate it.

These meanings are Core policy, not OpenCode permission syntax. In OpenCode, the
effective native rule governs whether the exact operation can proceed, requests
approval, or is refused; Core separately governs Olympus task scope, consent, and
non-elevatable boundaries. A task grant or approval cannot override an effective
native DENY or weaken Core DENY. Historical Codex deny assertions remain
defensive checks only; they do not declare Codex a currently supported adapter.
