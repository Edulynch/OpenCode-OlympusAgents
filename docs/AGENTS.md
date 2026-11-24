# Working in `docs/`

Start with the [documentation index](README.md). Keep the public READMEs focused on first use and link to the full explanation here.

## Where files belong

| Location | Put here |
| --- | --- |
| `docs/guide/` | Task-oriented Markdown for users: installation, workflows, and setup. |
| `docs/reference/` | Lookup-oriented Markdown: supported behavior, configuration, command reference, and limits. |
| `docs/assets/` | Images and diagrams referenced by the docs. |
| `docs/` | The index and repository-wide pages such as the development guide and roadmap. Keep existing release records at their current paths. |

Use the [index](README.md) to find existing guides and references that still live directly under `docs/`. Do not move a page until its inbound links, anchors, CI references, and any generated paths are accounted for. Create areas such as `examples/`, `templates/`, or `troubleshooting/` only when there is content that needs them. Feature specifications and test evidence stay under [`specs/`](../specs/README.md); link to historical records in Git rather than duplicating them.

## How to write and check docs

- Check for an existing page before creating one. Use lowercase kebab-case for new topics (`configure-worktrees.md`); keep established filenames and anchors unless explicitly migrating them.
- Use one descriptive H1, short sections, descriptive link text, relative links for current repository files, and a language label on command blocks. Use a tag or commit for historical evidence.
- Keep product behavior in its canonical source. For generated docs, edit the source and follow the [renderer workflow](HARNESSES.md) rather than editing the output.
- Add new Markdown pages to [the index](README.md). Keep the English and Spanish root READMEs aligned when changing shared first-run instructions.
- Keep release promotion, hosted branch-protection prerequisites, and endpoint evidence in [the development guide](DEVELOPMENT.md); never describe an opt-in or mocked workflow as a completed publication or live install.
- Run `python -B scripts/check_docs.py` and `git diff --check` from the repository root. The docs checker does not fetch external URLs.
