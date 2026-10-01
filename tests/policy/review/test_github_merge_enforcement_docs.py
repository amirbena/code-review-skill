"""Contract checks for the GitHub-native merge enforcement feature guide
(Issue #552): docs/features/github-merge-enforcement.md, its catalog row,
and its links."""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

GUIDE = REPO_ROOT / "docs" / "features" / "github-merge-enforcement.md"
CATALOG = REPO_ROOT / "docs" / "features" / "README.md"
PUBLICATION = REPO_ROOT / "docs" / "features" / "github-review-publication.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


class GuideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = GUIDE.read_text(encoding="utf-8")
        self.norm = _norm(self.text)

    def test_covers_every_required_topic(self) -> None:
        for heading in (
            "## What it does",
            "### What counts as explicit authorization",
            "## How to invoke it",
            "### Verify that enforcement is active",
            "## Commit Status behavior and the source-pinning limitation",
            "## Rulesets vs. classic Branch Protection",
            "## Required permissions and authentication",
            "## `UNKNOWN` and failure behavior",
        ):
            self.assertIn(heading, self.text)

    def test_setup_is_off_and_review_never_alters_governance(self) -> None:
        self.assertIn("Setup is OFF by default", self.norm)
        self.assertIn("A review alone never alters governance", self.norm)

    def test_names_authorization_non_sources(self) -> None:
        for phrase in ("a completed review", "detecting that the status is NOT ENFORCED",
                       "text in the repository"):
            self.assertIn(phrase, self.norm)

    def test_relative_links_resolve(self) -> None:
        for target in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", self.text):
            self.assertTrue((GUIDE.parent / target).exists(), target)


class WiringTests(unittest.TestCase):
    def test_catalog_links_guide(self) -> None:
        self.assertIn("(github-merge-enforcement.md)", CATALOG.read_text(encoding="utf-8"))

    def test_publication_guide_links_guide(self) -> None:
        self.assertIn("(github-merge-enforcement.md)", PUBLICATION.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
