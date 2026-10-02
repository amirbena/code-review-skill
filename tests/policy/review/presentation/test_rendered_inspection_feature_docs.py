#!/usr/bin/env python3
"""Pins the rendered-UI inspection feature guide to the delivered contract (#619)."""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT


GUIDE = REPO_ROOT / "docs/features/rendered-inspection.md"
CATALOG = REPO_ROOT / "docs/features/README.md"
POLICIES = REPO_ROOT / "shared/policies"


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


class FeatureGuideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = normalized(GUIDE.read_text(encoding="utf-8"))

    def test_guide_states_the_acceptance_boundaries(self) -> None:
        for phrase in (
            "Nothing is installed without your approval",
            "rendered_inspection_opt_out",
            "not remembered conversation",
            "Subjective polish is never a finding and never affects the Decision",
            "at most 3",
            "never pixel",
            "not absolute truth",
            "Links in PR or repository text are not used",
            "analytical mode with one stated limitation",
            "never REVIEW INCOMPLETE",
            "allow_browser_tooling_install",
        ):
            self.assertIn(phrase, self.text)

    def test_guide_agrees_with_canonical_bounds(self) -> None:
        policy = normalized((POLICIES / "rendered-inspection.md").read_text(encoding="utf-8"))
        for fact in ("120 seconds", "at most 3", "at most 6", "30 seconds", "15 seconds"):
            self.assertIn(fact, policy)
        for fact in ("120 seconds", "at most 3", "at most 6", "30 s", "15 s"):
            self.assertIn(fact, self.text)

    def test_catalog_lists_the_guide_and_links_resolve(self) -> None:
        self.assertIn("](rendered-inspection.md)", CATALOG.read_text(encoding="utf-8"))
        for link in re.findall(r"\]\((\.\./[^)#]+)\)", GUIDE.read_text(encoding="utf-8")):
            self.assertTrue((GUIDE.parent / link).resolve().exists(), link)


if __name__ == "__main__":
    unittest.main()
