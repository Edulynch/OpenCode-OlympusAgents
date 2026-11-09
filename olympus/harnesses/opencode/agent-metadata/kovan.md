---
description: Trusted-project implementer with shell and explicitly scoped source edits.
mode: subagent
model: "{{opencode_model}}#{{effort}}"
permissions:
  - action: shell
    resource: "*"
    effect: allow
  # Serena is limited to read-only semantic navigation; edits use scoped native tools.
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
  - action: subagent
    resource: "*"
    effect: deny
  - action: question
    resource: "*"
    effect: deny
  - action: execute
    resource: "*"
    effect: deny
  - action: edit
    resource: "*"
    effect: allow
  - action: edit
    resource: "*.env"
    effect: deny
  - action: edit
    resource: "*.env.*"
    effect: deny
  - action: edit
    resource: "*.env.example"
    effect: allow
  - action: edit
    resource: ".git"
    effect: deny
  - action: edit
    resource: ".git/*"
    effect: deny
  - action: edit
    resource: ".opencode"
    effect: deny
  - action: edit
    resource: ".opencode/**"
    effect: ask
  - action: edit
    resource: ".opencode/plugins/**"
    effect: ask
  - action: edit
    resource: ".opencode/agents/**"
    effect: deny
  - action: edit
    resource: ".opencode/plugins/olympus-activity/**"
    effect: deny
  # The worktree provisioning script is Olympus-owned, not a project plugin.
  - action: edit
    resource: ".opencode/scripts/worktree-setup.ps1"
    effect: deny
  - action: edit
    resource: ".opencode/orchestrator-install.json"
    effect: deny
  - action: edit
    resource: ".opencode/opencode.json"
    effect: deny
  - action: edit
    resource: ".opencode/opencode.jsonc"
    effect: deny
  - action: edit
    resource: "opencode.json"
    effect: deny
  - action: edit
    resource: "opencode.jsonc"
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
  - action: edit
    resource: ".codex/**"
    effect: deny
  - action: edit
    resource: "CODEX.md"
    effect: deny
---
