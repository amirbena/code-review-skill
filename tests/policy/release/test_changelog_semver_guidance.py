#!/usr/bin/env python3
"""Contracts for CHANGELOG category selection and SemVer guidance."""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

AGENTS = REPO_ROOT / "AGENTS.md"
POLICY = REPO_ROOT / "policies" / "release-changelog-policy.md"
RELEASE_DOC = REPO_ROOT / "docs" / "RELEASE.md"
TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


def _normalized(path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


class ReleaseGuidanceTests(unittest.TestCase):
    def test_release_doc_keeps_deterministic_category_mapping(self) -> None:
        text = _normalized(RELEASE_DOC)
        for categories, bump in (
            ("`Added`, `Changed`, `Deprecated`", "minor"),
            ("`Fixed`, `Security`", "patch"),
            ("`Removed`, `Breaking` (`Breaking Changes`)", "major"),
        ):
            self.assertRegex(text, rf"{re.escape(categories)}\s*\|\s*\*\*{bump}\*\*")

    def test_release_doc_distinguishes_changed_from_fixed_by_intent(self) -> None:
        text = _normalized(RELEASE_DOC).lower()
        self.assertIn("intentional backward-compatible behavior or capability change", text)
        self.assertIn("compatible correction or refinement", text)
        self.assertIn("if users receive a new or intentionally changed capability", text)
        self.assertIn("if the change corrects, cleans up, or restores intended compatible behavior", text)

    def test_canonical_policy_owns_the_same_semantic_boundary(self) -> None:
        text = _normalized(POLICY).lower()
        self.assertIn("intentional backward-compatible change to user-visible behavior or capability", text)
        self.assertIn("compatible correction or refinement", text)
        self.assertIn("decision rule:", text)
        self.assertIn("classify_semver_impact()", text)

    def test_agents_is_a_thin_route_without_the_full_mapping(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn("](policies/release-changelog-policy.md)", text)
        self.assertIn("Compatible corrections and", text)
        self.assertNotIn("`Fixed`, `Security`", text)
        self.assertNotIn("`Removed`, `Breaking`", text)

    def test_pr_template_keeps_changed_and_fixed_guidance_aligned(self) -> None:
        text = _normalized(TEMPLATE).lower()
        self.assertIn("`fixed` = compatible correction/refinement", text)
        self.assertIn(
            "`changed` = intentional backward-compatible behavior/capability change",
            text,
        )


if __name__ == "__main__":
    unittest.main()
