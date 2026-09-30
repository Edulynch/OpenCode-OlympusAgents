# Harness adapter sources

Adapter source files contain only runtime-specific representation and prompt translation. The canonical role responsibilities, model intent, and cross-harness policies live under `../roles/`, `../core/`, and `../policies/`. OpenCode is the fuller supported adapter. Codex is supported with explicit per-capability `ADAPTABLE`, `PARTIAL`, and `GAP` declarations; a gap never deletes a Core guarantee.
