---
description: Trusted-project implementer with shell and explicitly scoped source edits.
mode: subagent
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
    resource: ".opencode"
    effect: deny
  - action: edit
    resource: ".opencode/**"
    effect: ask
  # Path eligibility is not proof of ownership or task authority.
  - action: edit
    resource: ".opencode/skills/**"
    effect: allow
  - action: edit
    resource: ".opencode/plugins/**"
    effect: allow
  - action: edit
    resource: ".opencode/agents/**"
    effect: allow
  - action: edit
    resource: ".opencode/commands/**"
    effect: allow
  # These rules concern project config only. Manifest ownership is checked by
  # contract before delegation: identical filenames can be user- or installer-owned.
  - action: edit
    resource: ".opencode/opencode.json"
    effect: ask
  - action: edit
    resource: ".opencode/opencode.jsonc"
    effect: ask
  - action: edit
    resource: "opencode.json"
    effect: ask
  - action: edit
    resource: "opencode.jsonc"
    effect: ask
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
  # Reserve the Activity plugin namespace, including files outside today's inventory.
  - action: edit
    resource: ".opencode/plugins/olympus-activity"
    effect: deny
  - action: edit
    resource: ".opencode/plugins/olympus-activity/**"
    effect: deny
  - action: edit
    resource: ".opencode/orchestrator-install.json"
    effect: deny
  - action: edit
    resource: ".opencode/olympus-config.json"
    effect: deny
  # Defense in depth for standard profile paths and credential files. Custom
  # profile roots must also be excluded by the ownership and effect contract.
  - action: edit
    resource: "*/.config/opencode/*"
    effect: deny
  - action: edit
    resource: "*/.local/share/opencode/*"
    effect: deny
  - action: edit
    resource: "*/AppData/*/opencode/*"
    effect: deny
  - action: edit
    resource: "auth.json"
    effect: deny
  - action: edit
    resource: "*/auth.json"
    effect: deny
  # Keep these exact denials after the project namespace rules.
{{managed_edit_denies}}
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
