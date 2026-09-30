# Canonical authority semantics

- **ALLOW** — the exact operation is already authorized inside the current task's scope and applicable Olympus boundaries. Proceed without duplicate textual pre-approval.
- **ASK** — the operation is legitimate but requires the runtime/user's approval. Approval is the consent point, not advance authorization; refusal or cancellation stops the operation without fallback or bypass.
- **DENY** — the operation crosses a protected Olympus, user-prohibition, or otherwise non-elevatable boundary. Ordinary grants, approvals, role prompts, retries, or harness adaptation cannot elevate it.

These meanings are Core policy, not OpenCode permission syntax. OpenCode expresses supported ALLOW/ASK/DENY with native permission rules. Codex expresses ALLOW and native ASK through an adaptable profile/approval path, but equivalent hard DENY protection is a declared GAP. Core DENY is retained; never weaken it for parity.
