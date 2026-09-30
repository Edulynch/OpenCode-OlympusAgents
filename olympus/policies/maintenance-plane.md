# Canonical Olympus maintenance plane

Aegis is Olympus's privileged maintenance executor, outside normal Kael routing. The only admitted entry is explicit user authorization through the harness's `/maintain` surface for Olympus development, maintenance/configuration/installation, framework bug/gap repair, or an explicitly requested Olympus escape hatch blocked by such a gap. Ordinary project work and Git administration stay in the normal Kael plane. Kael cannot route to Aegis, and Aegis cannot self-activate or delegate.

The maintenance authority boundary belongs to Olympus Core. OpenCode implements it with the explicit `/maintain` command and hidden Aegis agent. Codex currently declares `AEGIS = GAP`; no Codex Aegis is generated or invented.
