"""Static regression checks for multi-repository task authority.

These tests verify the source/generated policy contract and native boundaries.
They do not simulate OpenCode's permission UI or an interactive agent run.
"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    """Keep each assertion tied to the files installed by the real renderer."""
    return (ROOT / relative).read_text(encoding="utf-8")


class ScopeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kael = read("olympus/harnesses/opencode/agent-prompts/kael.md")
        self.kovan = read("olympus/harnesses/opencode/agent-prompts/kovan.md")
        self.docs = read("docs/DEVELOPMENT.md")

    def test_task_root_is_not_implicitly_olympusagents(self) -> None:
        # An installed Olympus agent must be able to work on the user's project.
        self.assertIn("do not assume that it is the OlympusAgents source checkout", self.kael)
        self.assertIn("The active repository is the verified target of the task", self.docs)
        self.assertNotIn("Master verifies every requested target is within the active repository", self.kael)

    def test_each_source_repository_needs_its_own_scope(self) -> None:
        # A matching relative path in a sibling repository is not the same grant.
        self.assertRegex(
            self.kael,
            r"For each repository receiving source edits, WRITE_SCOPE must be explicit,\s+"
            r"non-empty, relative to that repository's declared canonical root",
        )
        self.assertIn("One repository's WRITE_SCOPE never authorizes another root", self.kael)
        self.assertIn("Do not source-edit another repository", self.kovan)
        self.assertRegex(self.docs, r"a scope for one\s+root cannot grant access to another")

    def test_external_effects_are_separate_and_do_not_override_deny(self) -> None:
        # Temporary fixtures and local hooks need explicit authority of their own.
        self.assertRegex(self.kael, r"(?s)Non-source external operations.*?declared exact target, operation, effect")
        self.assertIn("Native DENY remains final", self.kael)
        self.assertIn("separately assigned non-source external effect", self.kovan)
        self.assertIn("native DENY", self.docs)

    def test_external_directory_ask_does_not_override_project_deny(self) -> None:
        # The project supplies the default ASK; a later role wildcard would
        # downgrade a more-specific DENY supplied by the user or task runtime.
        config = read("olympus/harnesses/opencode/config.jsonc")
        self.assertRegex(
            config,
            r'"action":\s*"external_directory"\s*,\s*'
            r'"resource":\s*"\*"\s*,\s*"effect":\s*"ask"',
        )
        metadata_dir = ROOT / "olympus/harnesses/opencode/agent-metadata"
        for path in sorted(metadata_dir.glob("*.md")):
            with self.subTest(agent=path.stem):
                metadata = path.read_text(encoding="utf-8")
                self.assertNotRegex(metadata, r"(?m)^\s+- action:\s*external_directory\b")

    def test_generated_agents_contain_the_contract(self) -> None:
        # Source edits are only effective after the harness outputs are rendered.
        for role in ("kael", "kovan"):
            canonical = read(f"olympus/harnesses/opencode/agent-prompts/{role}.md")
            generated = read(f".opencode/agents/{role}.md")
            if role == "kael":
                marker = "One repository's WRITE_SCOPE never authorizes another root"
            else:
                marker = "separately assigned non-source external effect"
            self.assertIn(marker, canonical)
            self.assertIn(marker, generated)


if __name__ == "__main__":
    unittest.main()
