---
description: Primary OpenCode V2 orchestrator for direct answers, research, architecture, controlled writing, testing, review, barriers, and bounded parallel execution.
mode: primary
model: "{{opencode_model}}#{{effort}}"
permissions:
  - action: external_directory
    resource: "*"
    effect: ask
  - action: shell
    resource: "*"
    effect: deny
  - action: serena_*
    resource: "*"
    effect: deny
  - action: edit
    resource: "*"
    effect: deny
  - action: subagent
    resource: "*"
    effect: deny
  - action: subagent
    resource: veyra
    effect: allow
  - action: subagent
    resource: orin
    effect: allow
  - action: subagent
    resource: kovan
    effect: allow
  - action: subagent
    resource: nox
    effect: allow
  - action: subagent
    resource: vera
    effect: allow
  - action: subagent
    resource: thales
    effect: allow
  - action: subagent
    resource: atlas
    effect: allow
  - action: subagent
    resource: argus
    effect: allow
  - action: subagent
    resource: talos
    effect: allow
  - action: subagent
    resource: helios
    effect: allow
  - action: edit
    resource: "olympus/**"
    effect: deny
  - action: edit
    resource: ".codex/**"
    effect: deny
  - action: edit
    resource: "CODEX.md"
    effect: deny
  - action: edit
    resource: "scripts/render_harnesses.py"
    effect: deny
---
