---
description: Primary OpenCode V2 orchestrator for authority, scoped delegation, questions, and result reconciliation; no direct repository tools.
mode: primary
model: "{{opencode_model}}#{{effort}}"
permissions:
  - action: automation_*
    resource: "*"
    effect: deny
  - action: browser
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: deny
  - action: execute
    resource: "*"
    effect: deny
  - action: write
    resource: "*"
    effect: deny
  - action: read
    resource: "*"
    effect: deny
  - action: glob
    resource: "*"
    effect: deny
  - action: grep
    resource: "*"
    effect: deny
  - action: list
    resource: "*"
    effect: deny
  - action: lsp
    resource: "*"
    effect: deny
  - action: webfetch
    resource: "*"
    effect: deny
  - action: websearch
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
    resource: kovan
    effect: allow
  - action: subagent
    resource: nox
    effect: allow
  - action: subagent
    resource: vera
    effect: allow
  - action: subagent
    resource: talos
    effect: allow
  - action: subagent
    resource: helios
    effect: allow
  - action: subagent
    resource: thales
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
    resource: ".opencode/commands/olympus.performance-ultra.md"
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
