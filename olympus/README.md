# Olympus Core and generated surfaces

Olympus Core defines **what Olympus means**: the canonical roles, display identities, model-family intent, routing and lifecycle policies, authority semantics, and maintenance plane. `harnesses/opencode/` and `harnesses/codex/` define **how each supported runtime expresses that same Core**.

Edit Core or the applicable harness adapter source, then render. Never hand-edit generated root runtime outputs. Renderer commands and output inventory are in `../docs/HARNESSES.md`; `python scripts/render_harnesses.py check --harness all` is read-only and detects missing or drifted output.

Officially supported harnesses are OpenCode and Codex only. Capability gaps remain gaps; do not claim or synthesize an unsupported guarantee.
