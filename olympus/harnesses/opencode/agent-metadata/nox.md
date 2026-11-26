---
description: Trusted-project validation and measurement specialist; test-only writes require exact task scope.
mode: subagent
model: "{{opencode_model}}#{{effort}}"
permissions:
  - action: automation_*
    resource: "*"
    effect: deny
  - action: browser
    resource: "*"
    effect: deny
  - action: edit
    resource: "*"
    effect: deny
  - action: shell
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
  - action: serena_*
    resource: "*"
    effect: deny
  - action: webfetch
    resource: "*"
    effect: deny
  - action: websearch
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
  # Role prompts require an exact task TEST_WRITE_SCOPE; this native allow is
  # only the maximum test-source boundary, not task ownership or a source sandbox.
  - action: edit
    resource: "tests/**"
    effect: allow
---
