---
description: Read-only researcher worker for bounded repository and documentation exploration.
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
  - action: subagent
    resource: "*"
    effect: deny
  - action: question
    resource: "*"
    effect: deny
  - action: execute
    resource: "*"
    effect: deny
  # Read-only symbol tools support bounded repository evidence gathering.
  - action: serena_get_symbols_overview
    resource: "*"
    effect: allow
  - action: serena_find_symbol
    resource: "*"
    effect: allow
  - action: serena_find_referencing_symbols
    resource: "*"
    effect: allow
  - action: serena_find_implementations
    resource: "*"
    effect: allow
  - action: serena_find_declaration
    resource: "*"
    effect: allow
  - action: serena_get_diagnostics_for_file
    resource: "*"
    effect: allow
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
