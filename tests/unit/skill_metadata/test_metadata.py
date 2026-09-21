"""Tests for scripts/skill_metadata/metadata.py's ``check_skill_metadata`` --
the SKILL.md frontmatter contract (issue #439): required ``name``/
``version``/``description``, in that order, with ``version`` a strict
``x.y.z`` string that is intentionally NOT synced against
``metadata/skill.yaml``'s own (independent) ``version`` field.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import tests.unit.skill_metadata._shared  # noqa: F401 - sys.path wiring

from skill_metadata.metadata import check_skill_metadata


class CheckSkillMetadataFrontmatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.skill_root = Path(self._tmpdir.name)
        (self.skill_root / "metadata").mkdir()
        (self.skill_root / "entry.md").write_text("entry\n", encoding="utf-8")
        self._write_metadata_yaml()

    def _write_metadata_yaml(
        self, name: str = "example-skill", description: str = "Example."
    ) -> None:
        (self.skill_root / "metadata" / "skill.yaml").write_text(
            f"name: {name}\n"
            f"description: {description}\n"
            "entrypoint: entry.md\n",
            encoding="utf-8",
        )

    def _write_skill_md(self, frontmatter_lines: list[str]) -> None:
        body = "\n".join(frontmatter_lines)
        (self.skill_root / "SKILL.md").write_text(
            f"---\n{body}\n---\nBody.\n", encoding="utf-8"
        )

    def test_valid_frontmatter_passes_and_version_is_not_synced(self) -> None:
        # metadata/skill.yaml intentionally has no version field at all,
        # and SKILL.md's version must not be compared against it.
        self._write_skill_md(
            [
                "name: example-skill",
                "version: 1.50.2",
                "description: Example.",
            ]
        )
        metadata = check_skill_metadata(self.skill_root, self.skill_root)
        self.assertNotIn("version", metadata)

    def test_missing_version_is_rejected(self) -> None:
        self._write_skill_md(["name: example-skill", "description: Example."])
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_version_with_v_prefix_is_rejected(self) -> None:
        self._write_skill_md(
            ["name: example-skill", "version: v1.50.2", "description: Example."]
        )
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_version_with_leading_zero_is_rejected(self) -> None:
        self._write_skill_md(
            ["name: example-skill", "version: 1.05.2", "description: Example."]
        )
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_version_with_two_segments_is_rejected(self) -> None:
        self._write_skill_md(
            ["name: example-skill", "version: 1.50", "description: Example."]
        )
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_bare_zero_segments_are_accepted(self) -> None:
        self._write_skill_md(
            ["name: example-skill", "version: 0.0.0", "description: Example."]
        )
        check_skill_metadata(self.skill_root, self.skill_root)

    def test_wrong_field_order_is_rejected(self) -> None:
        self._write_skill_md(
            ["version: 1.50.2", "name: example-skill", "description: Example."]
        )
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_missing_name_is_still_rejected(self) -> None:
        self._write_skill_md(["version: 1.50.2", "description: Example."])
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_unexpected_frontmatter_field_is_rejected(self) -> None:
        self._write_skill_md(
            [
                "name: example-skill",
                "version: 1.50.2",
                "description: Example.",
                "extra: nope",
            ]
        )
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_name_still_synced_to_metadata_yaml(self) -> None:
        self._write_skill_md(
            ["name: different-name", "version: 1.50.2", "description: Example."]
        )
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_block_scalar_description_is_rejected(self) -> None:
        self._write_metadata_yaml(description="Line one. Line two.")
        self._write_skill_md(
            [
                "name: example-skill",
                "version: 1.50.2",
                "description: >-",
                "  Line one. Line two.",
            ]
        )
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_literal_block_scalar_description_is_rejected(self) -> None:
        self._write_metadata_yaml(description="Line one.")
        self._write_skill_md(
            [
                "name: example-skill",
                "version: 1.50.2",
                "description: |",
                "  Line one.",
            ]
        )
        with self.assertRaises(SystemExit):
            check_skill_metadata(self.skill_root, self.skill_root)

    def test_single_line_description_passes(self) -> None:
        self._write_skill_md(
            ["name: example-skill", "version: 1.50.2", "description: Example."]
        )
        check_skill_metadata(self.skill_root, self.skill_root)


class RealSkillFrontmatterVersionTests(unittest.TestCase):
    """Both published Skills carry the same normalized version; the release flow owns its value."""

    def test_both_skills_declare_the_same_semver_version(self) -> None:
        from tests.support.paths import REPO_ROOT
        from skill_metadata._support import load_frontmatter

        versions = set()
        for skill_name in ("local-code-review", "github-pr-review"):
            skill_md = REPO_ROOT / "skills" / skill_name / "SKILL.md"
            frontmatter = load_frontmatter(skill_md)
            self.assertEqual(list(frontmatter), ["name", "version", "description"])
            self.assertRegex(frontmatter["version"], r"^\d+\.\d+\.\d+$")
            versions.add(frontmatter["version"])
        self.assertEqual(len(versions), 1, versions)

    def test_both_skills_have_single_line_description(self) -> None:
        from tests.support.paths import REPO_ROOT

        expected = {
            "local-code-review": (
                "Review local Git changes and return evidence-backed "
                "P0/P1/P2 code-review findings."
            ),
            "github-pr-review": (
                "Review an existing GitHub pull request and return or "
                "publish evidence-backed P0/P1/P2 findings."
            ),
        }
        for skill_name, expected_description in expected.items():
            skill_md = REPO_ROOT / "skills" / skill_name / "SKILL.md"
            lines = skill_md.read_text(encoding="utf-8").splitlines()
            closing = lines.index("---", 1)
            body_lines = lines[1:closing]
            self.assertEqual(body_lines[-1], f"description: {expected_description}")


if __name__ == "__main__":
    unittest.main()
