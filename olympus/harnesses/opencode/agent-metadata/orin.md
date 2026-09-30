---
description: Read-only architect worker for bounded architecture, interfaces, boundaries, and implementation decomposition.
mode: subagent
model: "{{opencode_model}}#{{effort}}"
permissions:
  - action: external_directory
    resource: "*"
    effect: ask
  - action: edit
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: deny
  - action: serena_*
    resource: "*"
    effect: deny
  - action: subagent
    resource: "*"
    effect: deny
  - action: question
    resource: "*"
    effect: deny
  - action: execute
    resource: "*"
    effect: deny
  - action: read
    resource: "*"
    effect: allow
  - action: glob
    resource: "*"
    effect: allow
  - action: grep
    resource: "*"
    effect: allow
  - action: list
    resource: "*"
    effect: allow
  - action: lsp
    resource: "*"
    effect: allow
  - action: webfetch
    resource: "*"
    effect: allow
  - action: websearch
    resource: "*"
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
