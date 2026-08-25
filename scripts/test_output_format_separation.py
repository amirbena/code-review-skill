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

    def test_rules_list_is_not_interrupted_by_relevance_aware_subsection(self) -> None:
        rules_start = self.text.index("## Rules")
        subsection_start = self.text.index(
            "### Relevance-aware metadata rendering"
        )
        # Everything between the start of the Rules list and the
        # subsection heading must be exactly one uninterrupted block —
        # no other heading (of any level) may appear in between, which
        # would otherwise split the bullet list into two disconnected
        # lists under CommonMark.
        between = self.text[rules_start:subsection_start]
        self.assertNotIn("\n## ", between[len("## Rules") :])
        self.assertNotIn("\n### ", between[len("## Rules") :])

    def test_relevance_aware_subsection_follows_the_full_rules_list(self) -> None:
        last_rules_bullet = self.text.index(
            "Return only what the implementing Agent needs to act."
        )
        subsection_start = self.text.index(
            "### Relevance-aware metadata rendering"
        )
        self.assertLess(last_rules_bullet, subsection_start)

    def _relevance_section(self) -> str:
        section = re.search(
            r"### Relevance-aware metadata rendering\n(.*?)(?=\n## |\Z)",
            self.text,
            re.S,
        )
        self.assertIsNotNone(section)
        # Normalize markdown emphasis and line wrapping so assertions on
        # phrasing survive reflow, matching the convention already used
        # by the other doc-pinning test modules in this repository.
        return re.sub(r"\s+", " ", section.group(1).replace("**", "").replace("`", ""))

    def test_relevance_aware_metadata_rendering_section_exists(self) -> None:
        self.assertIn("### Relevance-aware metadata rendering", self.text)

    def test_fingerprint_remains_mandatory_internal_state(self) -> None:
        # Rendering is conditional; computing it never is — see
        # policies/repository-state.md, "Staged delta fingerprint," which
        # this test does not restate, only confirms is still cross-linked.
        body = self._relevance_section()
        self.assertIn("is still always computed", body)
        self.assertIn(
            "nothing here changes what this Skill must determine internally, "
            "only what it prints",
            body,
        )

    def test_fingerprint_display_conditions_are_stated(self) -> None:
        body = self._relevance_section()
        for trigger in (
            "the staged category is non-empty",
            "this is a re-review",
            "the caller supplied a previously reported fingerprint",
            "the fingerprint comparison materially affected review behavior",
        ):
            self.assertIn(trigger, body)

    def test_initial_empty_staged_review_does_not_require_the_fingerprint_line(
        self,
    ) -> None:
        body = self._relevance_section()
        self.assertIn(
            "an initial review with nothing staged, where the fingerprint "
            "is the well-known SHA-256 of empty input and adds no human "
            "value",
            body,
        )

    def test_previously_reviewed_state_is_omitted_not_marked_not_applicable(
        self,
    ) -> None:
        body = self._relevance_section()
        self.assertIn("omit the line entirely", body)
        # The template must not fall back to a fixed not-applicable
        # placeholder anywhere in its rendered examples.
        for block in re.findall(r"```markdown\n(.*?)\n```", self.text, re.S):
            self.assertNotIn("not applicable, initial review", block)

    def test_relevance_gating_never_affects_decision_or_findings(self) -> None:
        body = self._relevance_section()
        self.assertIn(
            "This never affects the Decision, the findings, or any other "
            "internal review requirement",
            body,
        )

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

    def test_not_coupled_to_local_relevance_aware_rendering_change(self) -> None:
        # Cross-Skill distinction: local-code-review's relevance-gated
        # metadata rendering is a local-only presentation choice. This
        # Skill's own template must not have been made to adopt it, and
        # this suite must never assert it should — shared review
        # reasoning does not imply identical human-facing formatting.
        self.assertNotIn("Relevance-aware metadata rendering", self.text)


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

    def test_metadata_section_does_not_prescribe_concrete_markup(self) -> None:
        # The "subordinate, appended last" rule is shared semantics; the
        # concrete rendering (Markdown heading vs. HTML <details>) is
        # each consuming Skill's own choice. If this section hardcoded
        # one fenced example, it would be prescribing a single renderer's
        # presentation onto both Skills again.
        section = re.search(
            r"## Machine metadata is subordinate\n(.*?)(?=\n## |\Z)",
            self.text,
            re.S,
        )
        self.assertIsNotNone(section)
        body = section.group(1)
        self.assertNotIn("```markdown", body)
        # A real rendered wrapper puts the tag alone on its own line
        # (as it must, to open/close an HTML block); prose that merely
        # names the tag as an example does so inline within a sentence,
        # inside single backticks, and never satisfies this pattern.
        live_wrapper = re.compile(r"^\s*</?(?:details|summary)>\s*$", re.M | re.I)
        self.assertIsNone(live_wrapper.search(body))


if __name__ == "__main__":
    unittest.main()
