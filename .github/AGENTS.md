# GitHub configuration

- Keep GitHub Actions workflow YAML in `workflows/` and dependency-update settings in `dependabot.yml`. Put contributor explanations in the [development guide](../docs/DEVELOPMENT.md), not in workflow comments.
- Use the existing runner and job that own the changed check. Keep `FAST / Windows` stable: it is a required check. Do not broaden workflow permissions or change release triggers as part of an unrelated edit.
- Keep path filters and runner-specific commands aligned with the checked-in source and tests. Report a local YAML or script check separately from a hosted workflow result.
- For promotion and release workflows, follow the [workflow instructions](workflows/AGENTS.md).
- For changes affecting CI selection or test runtime, compare hosted before/after critical-job wall time and queue delay separately. The current <3-minute goal and <=2-minute ideal are targets, not blocking gates; preserve required check names.
