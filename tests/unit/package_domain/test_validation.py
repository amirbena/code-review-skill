"""Tests for scripts/packaging/package_domain/validation.py — the canonical
SKILL.md frontmatter structural validation shared by both platform
packaging scripts (issue #266)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import tests.unit.package_domain._shared  # noqa: F401 - sys.path wiring

from package_domain.validation import SkillFrontmatterError, validate_skill_frontmatter


class ValidateSkillFrontmatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.skill_md = Path(self._tmpdir.name) / "SKILL.md"

    def _write(self, content: str) -> None:
        self.skill_md.write_text(content, encoding="utf-8")

    def test_valid_frontmatter_passes(self) -> None:
        self._write(
            "---\nname: local-code-review\nversion: 1.50.2\n"
            "description: Reviews local changes.\n---\nBody.\n"
        )
        validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_missing_opening_delimiter_is_rejected(self) -> None:
        self._write("name: local-code-review\nversion: 1.50.2\ndescription: x\n---\nBody.\n")
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_missing_closing_delimiter_is_rejected(self) -> None:
        self._write("---\nname: local-code-review\nversion: 1.50.2\ndescription: x\nBody.\n")
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_missing_name_is_rejected(self) -> None:
        self._write("---\nversion: 1.50.2\ndescription: x\n---\nBody.\n")
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_missing_version_is_rejected(self) -> None:
        self._write("---\nname: local-code-review\ndescription: x\n---\nBody.\n")
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_version_with_v_prefix_is_rejected(self) -> None:
        self._write(
            "---\nname: local-code-review\nversion: v1.50.2\ndescription: x\n---\nBody.\n"
        )
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_version_with_leading_zero_is_rejected(self) -> None:
        self._write(
            "---\nname: local-code-review\nversion: 1.05.2\ndescription: x\n---\nBody.\n"
        )
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_version_with_non_numeric_segment_is_rejected(self) -> None:
        self._write(
            "---\nname: local-code-review\nversion: 1.50.x\ndescription: x\n---\nBody.\n"
        )
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_missing_description_is_rejected(self) -> None:
        self._write("---\nname: local-code-review\nversion: 1.50.2\n---\nBody.\n")
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_name_mismatch_is_rejected(self) -> None:
        self._write(
            "---\nname: github-pr-review\nversion: 1.50.2\ndescription: x\n---\nBody.\n"
        )
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_folded_block_scalar_description_is_rejected(self) -> None:
        self._write(
            "---\nname: local-code-review\nversion: 1.50.2\n"
            "description: >-\n  Line one. Line two.\n---\nBody.\n"
        )
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")

    def test_literal_block_scalar_description_is_rejected(self) -> None:
        self._write(
            "---\nname: local-code-review\nversion: 1.50.2\n"
            "description: |\n  Line one.\n---\nBody.\n"
        )
        with self.assertRaises(SkillFrontmatterError):
            validate_skill_frontmatter(self.skill_md, "local-code-review")


if __name__ == "__main__":
    unittest.main()
