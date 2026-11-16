# Olympus Core and generated surfaces

Olympus Core defines **what Olympus means**: the canonical roles, display identities, model-family intent, routing and lifecycle policies, authority semantics, and contextual maintenance policy. `harnesses/opencode/` is the supported runtime representation.

Edit Core or the OpenCode adapter source, then render. Never hand-edit generated root runtime outputs. Renderer commands and output inventory are in `../docs/HARNESSES.md`; `python scripts/render_harnesses.py check --harness opencode` is read-only and detects missing or drifted output.

OpenCode is the only currently supported Olympus harness.
