#!/usr/bin/env python3
"""Regression coverage for local vs. GitHub output-format separation.

`local-code-review`'s final report is native Markdown, read directly in
a terminal/chat surface — it must never carry GitHub-oriented HTML
presentation wrappers (e.g. `<details>`/`<summary>`). `github-pr-review`
renders a GitHub review body and may keep using GitHub-compatible
collapsible sections. This test pins that boundary so a future edit
that reintroduces HTML into the local template, or drops it from the
GitHub template, fails loudly. See
shared/templates/review-summary.md, "Machine metadata is subordinate."

Run with:
    python3 scripts/test_output_format_separation.py
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_TEMPLATE = (
    REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
)
GITHUB_TEMPLATE = (
    REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
)
SHARED_SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"

# GitHub-oriented HTML presentation constructs that must never appear in
# the local Markdown-only report body.
HTML_WRAPPER_PATTERN = re.compile(r"<details>|</details>|<summary>|</summary>")


class LocalReportIsPlainMarkdown(unittest.TestCase):
    def setUp(self) -> None:
        self.text = LOCAL_TEMPLATE.read_text(encoding="utf-8")

    def test_no_github_html_wrappers_in_rendered_examples(self) -> None:
        # Scoped to the fenced example bodies actually rendered by this
        # Skill, not prose elsewhere in the file that documents (in
        # words) that these wrappers must not be used.
        for block in re.findall(r"```markdown\n(.*?)\n```", self.text, re.S):
            matches = HTML_WRAPPER_PATTERN.findall(block)
            self.assertEqual(
                matches,
                [],
                f"local-review-report.md must not contain GitHub HTML wrappers, found: {matches}",
            )

    def test_no_stray_html_tags(self) -> None:
        # Broader guard than the exact-string check above: catches any
        # real HTML element (angle brackets immediately around a bare
        # tag name, e.g. `<details ...>` or `</summary>`), while
        # ignoring placeholder text like `<sha>` or `<base>` used
        # throughout the template's fill-in-the-blank examples.
        known_html_tags = {"details", "summary"}
        for block in re.findall(r"```markdown\n(.*?)\n```", self.text, re.S):
            tags = [
                t
                for t in re.findall(r"</?([a-zA-Z][a-zA-Z0-9]*)[^>]*>", block)
                if t.lower() in known_html_tags
            ]
            self.assertEqual(
                tags, [], f"unexpected HTML tag(s) in local report body: {tags}"
            )

    def test_has_markdown_review_metadata_heading(self) -> None:
        self.assertIn("### Review Metadata", self.text)

    def test_has_markdown_headings_and_lists(self) -> None:
        self.assertIn("## Code Review", self.text)
        self.assertIn("### Findings", self.text)
        self.assertIn("### Decision", self.text)
        self.assertRegex(self.text, r"\n- .+")

    def test_preserves_metadata_fields(self) -> None:
        for field in (
            "Base branch",
            "Base SHA",
            "Local HEAD",
            "Remote HEAD",
            "Synchronization status",
            "P0",
            "P1",
            "P2",
        ):
            self.assertIn(field, self.text)

    def test_preserves_review_scope_contract_fields(self) -> None:
        for field in (
            "Committed delta relative to base",
            "Staged",
            "Unstaged",
            "Untracked",
            "Staged-delta fingerprint",
            "Review kind",
            "Previously reviewed state changed",
        ):
            self.assertIn(field, self.text)

    def test_preserves_decision_semantics(self) -> None:
        self.assertIn("REVIEW CLEAN", self.text)
        self.assertIn("CHANGES REQUIRED", self.text)

    def test_preserves_finding_severity_and_evidence_fields(self) -> None:
        for field in ("[P1]", "**Evidence**", "**Impact**", "**Recommended direction**"):
            self.assertIn(field, self.text)


class GithubReportKeepsHtmlPresentation(unittest.TestCase):
    def setUp(self) -> None:
        self.text = GITHUB_TEMPLATE.read_text(encoding="utf-8")

    def test_still_offers_details_wrapper(self) -> None:
        self.assertIn("<details>", self.text)
        self.assertIn("<summary>", self.text)
        self.assertIn("</details>", self.text)

    def test_preserves_decision_semantics(self) -> None:
        self.assertIn("APPROVE", self.text)
        self.assertIn("REQUEST CHANGES", self.text)


class SharedTemplateDefersPresentationChoice(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SHARED_SUMMARY.read_text(encoding="utf-8")

    def test_no_hardcoded_html_in_shared_canonical_shape(self) -> None:
        canonical_shape = re.search(
            r"## Canonical shape\n\n```markdown\n(.*?)\n```", self.text, re.S
        )
        self.assertIsNotNone(canonical_shape)
        known_html_tags = {"details", "summary"}
        tags = [
            t
            for t in re.findall(
                r"</?([a-zA-Z][a-zA-Z0-9]*)[^>]*>", canonical_shape.group(1)
            )
            if t.lower() in known_html_tags
        ]
        self.assertEqual(tags, [])

    def test_explains_presentation_is_per_skill(self) -> None:
        self.assertIn("local-review-report.md", self.text)
        self.assertIn("external-review-summary.md", self.text)


if __name__ == "__main__":
    unittest.main()
