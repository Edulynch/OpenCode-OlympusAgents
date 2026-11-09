---
description: Primary OpenCode V2 orchestrator for direct answers, research, architecture, controlled writing, testing, review, barriers, and bounded parallel execution.
mode: primary
model: "{{opencode_model}}#{{effort}}"
permissions:
  # Direct shell stays available, but tests, generators, and writes need approval.
  # Narrow Git inspection commands can run without interrupting the task.
  - action: shell
    resource: "*"
    effect: ask
  - action: shell
    resource: "git status *"
    effect: allow
  - action: shell
    resource: "git branch --show-current"
    effect: allow
  - action: shell
    resource: "git rev-parse --show-toplevel"
    effect: allow
  - action: shell
    resource: "git diff --check"
    effect: allow
  - action: shell
    resource: "git diff --stat"
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
  - action: edit
    resource: "*"
    effect: allow
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
