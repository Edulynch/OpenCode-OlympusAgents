# Install entrypoints

- Keep compatibility entrypoints under `global/`; `global/opencode.ps1` forwards the Windows install request. The public bootstrap scripts stay at the repository root.
- Keep launchers thin. Put installation, version selection, and ownership logic in the existing engines rather than adding a second implementation here. Do not add project-selection behavior to a global entrypoint.
- Use the existing isolated installer or release fixtures for behavior changes. Put user instructions in the [installation guide](../docs/INSTALLATION.md).
