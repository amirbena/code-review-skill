"""Tests for scripts/release_worthiness.py path-classification helpers."""

from __future__ import annotations

import unittest
import json

from tests.unit.release._shared import rw

class ClassifyPathTests(unittest.TestCase):
    def test_skill_content_is_release_worthy(self) -> None:
        for path in (
            "skills/local-code-review/SKILL.md",
            "skills/github-pr-review/policies/github-review.md",
            "skills/local-code-review/runbooks/local-review.md",
            "skills/github-pr-review/metadata/skill.yaml",
        ):
            self.assertEqual(rw.classify_path(path), "skill-content", path)

    def test_skill_readme_is_not_release_worthy(self) -> None:
        self.assertEqual(rw.classify_path("skills/local-code-review/README.md"), "docs")

    def test_packaged_shared_is_release_worthy(self) -> None:
        self.assertEqual(rw.classify_path("shared/policies/severity.md"), "shared-runtime")
        self.assertEqual(rw.classify_path("shared/templates/finding.md"), "shared-runtime")

    def test_shared_readme_is_not_release_worthy(self) -> None:
        self.assertEqual(rw.classify_path("shared/policies/README.md"), "docs")

    def test_packaging_files_are_release_worthy(self) -> None:
        for path in (
            "scripts/package-skills.sh",
            "scripts/package-skills.ps1",
            "scripts/package-manifest.json",
            "scripts/package_manifest.py",
            "scripts/validate-skill-metadata.py",
        ):
            self.assertEqual(rw.classify_path(path), "packaging", path)

    def test_skill_metadata_validator_package_is_release_worthy(self) -> None:
        # The validator behind scripts/validate-skill-metadata.py is a
        # package; editing any of its modules stays release-worthy.
        for path in (
            "scripts/skill_metadata/expectations.py",
            "scripts/skill_metadata/orchestrator.py",
            "scripts/skill_metadata/github_family.py",
        ):
            self.assertEqual(rw.classify_path(path), "packaging", path)

    def test_non_packaging_scripts_are_maintenance(self) -> None:
        self.assertEqual(rw.classify_path("scripts/claim_issue.py"), "repo-maintenance")
        self.assertEqual(rw.classify_path("scripts/release_worthiness.py"), "repo-maintenance")
        # CI-only release automation helper — never shipped in an archive.
        self.assertEqual(
            rw.classify_path("scripts/release/verify-skill-archives.sh"), "repo-maintenance"
        )

    def test_docs_tests_ci_policy_are_not_release_worthy(self) -> None:
        for path, category in (
            ("docs/ARCHITECTURE.md", "docs"),
            ("docs/RELEASE.md", "docs"),
            ("tests/unit/test_release_worthiness.py", "tests"),
            (".github/workflows/validate.yml", "ci"),
            (".github/workflows/release-worthiness.yml", "ci"),
            ("policies/git-pr-merge-policy.md", "repo-policy"),
        ):
            self.assertEqual(rw.classify_path(path), category, path)

    def test_root_maintenance_files(self) -> None:
        for path, category in (
            ("CHANGELOG.md", "changelog"),
            ("README.md", "docs"),
            ("AGENTS.md", "repo-policy"),
            ("CONTRIBUTING.md", "docs"),
            ("LICENSE", "repo-maintenance"),
            ("requirements-dev.txt", "repo-maintenance"),
        ):
            self.assertEqual(rw.classify_path(path), category, path)

    def test_unknown_path(self) -> None:
        self.assertEqual(rw.classify_path("weird/thing.txt"), "unknown")

    def test_normalizes_separators_and_prefix(self) -> None:
        self.assertEqual(rw.classify_path("./skills/local-code-review/SKILL.md"), "skill-content")
        self.assertEqual(rw.classify_path("skills\\github-pr-review\\SKILL.md"), "skill-content")


class ClassifyPathsTests(unittest.TestCase):
    def test_skill_change_is_release_worthy(self) -> None:
        c = rw.classify_paths(["skills/local-code-review/SKILL.md"])
        self.assertTrue(c.release_worthy)
        self.assertEqual([p for p, _ in c.triggering], ["skills/local-code-review/SKILL.md"])

    def test_packaging_change_is_release_worthy(self) -> None:
        c = rw.classify_paths(["scripts/package-skills.ps1"])
        self.assertTrue(c.release_worthy)

    def test_docs_only_is_not_release_worthy(self) -> None:
        c = rw.classify_paths(["docs/ARCHITECTURE.md", "README.md", "skills/github-pr-review/README.md"])
        self.assertFalse(c.release_worthy)
        self.assertEqual(c.triggering, ())

    def test_tests_and_maintenance_only_is_not_release_worthy(self) -> None:
        c = rw.classify_paths(
            ["tests/unit/test_x.py", "scripts/claim_issue.py", ".github/workflows/validate.yml"]
        )
        self.assertFalse(c.release_worthy)

    def test_mixed_set_with_one_skill_file_is_release_worthy(self) -> None:
        c = rw.classify_paths(["docs/ARCHITECTURE.md", "skills/local-code-review/policies/pr-context.md"])
        self.assertTrue(c.release_worthy)
        self.assertEqual(len(c.triggering), 1)
        self.assertEqual(len(c.other), 1)

    def test_empty_set_is_not_release_worthy(self) -> None:
        self.assertFalse(rw.classify_paths([]).release_worthy)
        self.assertFalse(rw.classify_paths(["", "  "]).release_worthy)

    def test_reason_mentions_a_triggering_path(self) -> None:
        c = rw.classify_paths(["skills/local-code-review/SKILL.md"])
        self.assertIn("skills/local-code-review/SKILL.md", c.reason)


if __name__ == "__main__":
    unittest.main()
