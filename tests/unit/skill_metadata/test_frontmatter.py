"""Tests for scripts/skill_metadata/frontmatter.py: the v3 SKILL.md
frontmatter contract (name equals folder name, one-line description,
optional strict x.y.z version)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import tests.unit.skill_metadata._shared  # noqa: F401 - sys.path wiring

from skill_metadata.frontmatter import check_frontmatter
from skill_metadata.orchestrator import validate
from tests.support.paths import REPO_ROOT


class CheckFrontmatterTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "example-skill"
        self.root.mkdir()

    def _write(self, *lines: str) -> None:
        body = "\n".join(lines)
        (self.root / "SKILL.md").write_text(f"---\n{body}\n---\nBody.\n", encoding="utf-8")

    def test_valid_without_version(self) -> None:
        self._write("name: example-skill", "description: Example.")
        self.assertEqual(check_frontmatter(self.root)["name"], "example-skill")

    def test_valid_with_version(self) -> None:
        self._write("name: example-skill", "description: Example.", "version: 3.0.0")
        check_frontmatter(self.root)

    def test_rejects_bad_input(self) -> None:
        cases = {
            "name differs from folder": ["name: other", "description: Example."],
            "missing description": ["name: example-skill"],
            "unknown field": ["name: example-skill", "description: Example.", "metadata: x"],
            "bad version": ["name: example-skill", "description: Example.", "version: v3.0"],
            "block scalar": ["name: example-skill", "description: >-", "  Example."],
        }
        for label, lines in cases.items():
            with self.subTest(label):
                self._write(*lines)
                with self.assertRaises(SystemExit):
                    check_frontmatter(self.root)

    def test_missing_skill_md(self) -> None:
        with self.assertRaises(SystemExit):
            check_frontmatter(self.root)


class RepositorySkillsTests(unittest.TestCase):
    def test_every_skill_validates(self) -> None:
        skills = sorted(p for p in (REPO_ROOT / "skills").iterdir() if p.is_dir())
        self.assertTrue(skills)
        for skill in skills:
            with self.subTest(skill.name):
                validate(skill, REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
