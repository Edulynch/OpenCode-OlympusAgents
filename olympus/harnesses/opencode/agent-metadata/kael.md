---
description: Primary OpenCode V2 orchestrator for minimal repository preflight, questions, scoped delegation, and result reconciliation.
mode: primary
model: "{{opencode_model}}#{{effort}}"
permissions:
  - action: automation_*
    resource: "*"
    effect: deny
  - action: browser
    resource: "*"
    effect: deny
  # Kael needs shell only for the exact repository-root probe.
  - action: shell
    resource: "*"
    effect: deny
  - action: shell
    resource: "git rev-parse --show-toplevel"
    effect: allow
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
    resource: ".opencode/agents/**"
    effect: deny
  - action: edit
    resource: ".opencode/plugins/olympus-activity/**"
    effect: deny
  - action: edit
    resource: ".opencode/commands/olympus.ultra.md"
    effect: deny
  - action: edit
    resource: ".opencode/commands/olympus.performance.md"
    effect: deny
  - action: edit
    resource: ".opencode/scripts/worktree-setup.ps1"
    effect: deny
  - action: edit
    resource: ".opencode/orchestrator-install.json"
    effect: deny
  - action: edit
    resource: "opencode.jsonc"
    effect: deny
  - action: edit
    resource: ".codex/**"
    effect: deny
  - action: edit
    resource: "CODEX.md"
    effect: deny
---
