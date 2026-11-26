---
description: Primary read-only technical analyst and planner; may delegate only bounded evidence and reasoning.
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
    effect: ask
  - action: edit
    resource: "*"
    effect: deny
  - action: write
    resource: "*"
    effect: deny
  # If the host maps Code Mode to execute, native ASK gates the read-only use
  # described in the Atlas prompt; this is not mutation authority.
  - action: execute
    resource: "*"
    effect: ask
  - action: subagent
    resource: "*"
    effect: deny
  - action: subagent
    resource: veyra
    effect: allow
  - action: subagent
    resource: helios
    effect: allow
  - action: subagent
    resource: talos
    effect: allow
  - action: subagent
    resource: thales
    effect: allow
  - action: question
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
  - action: external_directory
    resource: "*"
    effect: ask
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
