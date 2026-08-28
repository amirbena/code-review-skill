#!/usr/bin/env python3
"""Documentation-contract checks for the canonical finding contract (Issue #37).

Pins shared/templates/finding.md and both Skills' finding renderings to
the one compact, field-oriented shape so accidental format drift fails a
test rather than shipping. Assertions target semantic structure (field
labels, ordering, named sections) and whitespace-normalized prose, not
brittle exact whitespace — matching the convention in the other
doc-pinning modules in this suite.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

SHARED_FINDING = REPO_ROOT / "shared/templates/finding.md"
SHARED_SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
LOCAL_REPORT = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
GITHUB_BODY = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
GITHUB_INLINE = REPO_ROOT / "skills/github-pr-review/templates/inline-finding.md"

COMPACT_FULL_LABELS = ("**Location:**", "**Evidence:**", "**Impact:**", "**Fix:**")
OLD_BLOCK_HEADERS = ("\n**Evidence**\n", "\n**Impact**\n", "\n**Recommended direction**\n")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def _md_blocks(text: str) -> list[str]:
    return re.findall(r"```(?:markdown|text)\n(.*?)\n```", text, re.S)


class SharedFindingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SHARED_FINDING.read_text(encoding="utf-8")
        self.norm = _norm(self.text)

    def test_contract_vs_rendering_boundary_is_documented(self) -> None:
        # review reasoning -> canonical finding contract -> rendering, and
        # a future renderer must not require redesigning the semantics.
        self.assertIn("## Contract vs. rendering", self.text)
        self.assertIn("The fields are the contract", self.norm)
        self.assertIn(
            "A future additional renderer (for example a machine-readable one)",
            self.norm,
        )
        self.assertIn(
            "Do not make the human-facing review a machine-only format", self.norm
        )

    def test_canonical_full_rendering_is_the_compact_field_block(self) -> None:
        block = re.search(
            r"## Canonical full rendering\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(block)
        body = block.group(1)
        for label in COMPACT_FULL_LABELS:
            self.assertIn(label, body)
        # order: Location -> Evidence -> Impact -> Fix
        positions = [body.index(label) for label in COMPACT_FULL_LABELS]
        self.assertEqual(positions, sorted(positions))
        # the essay-style block headers are gone from the rendered examples
        for header in OLD_BLOCK_HEADERS:
            self.assertNotIn(header, body)

    def test_severity_semantics_are_deferred_not_redefined(self) -> None:
        self.assertIn("policies/severity.md", self.text)
        self.assertIn("[P0] / [P1] / [P2]", self.norm)
        self.assertIn(
            "the mechanical severity → decision derivation are unchanged by "
            "this template",
            self.norm,
        )

    def test_mandatory_core_preserved_and_not_reducible_for_length(self) -> None:
        self.assertIn("## Finding quality contract", self.text)
        self.assertIn("What? Where? Evidence? Impact? Fix?", self.norm)
        self.assertIn("This is the mandatory core", self.norm)
        self.assertIn(
            "It is never reduced to hit a length target", self.norm
        )

    def test_conciseness_contract_section_exists_without_a_line_target(self) -> None:
        self.assertIn("## Conciseness contract", self.text)
        self.assertIn("field-oriented and concise by default", self.norm)
        self.assertIn("there is no line-count target", self.norm)
        self.assertIn(
            "never from dropping evidence", self.norm
        )

    def test_longer_explanation_is_a_controlled_exception_with_named_cases(self) -> None:
        self.assertIn("## When a longer explanation is justified", self.text)
        section = re.search(
            r"## When a longer explanation is justified\n(.*?)\n## ",
            self.text,
            re.S,
        )
        self.assertIsNotNone(section)
        body = _norm(section.group(1))
        self.assertIn("controlled exception", body)
        self.assertIn("not the default", body)
        for case in (
            "cross-file",
            "concurrency, ordering, or race condition",
            "security implication",
            "complex invariant violation",
            "cannot be understood without brief context",
        ):
            self.assertIn(case, body)
        self.assertIn("single optional Details field", body)
        self.assertIn("still not an open-ended essay", body)

    def test_optional_fields_never_render_as_empty_boilerplate(self) -> None:
        self.assertIn("## Optional and surface-specific fields", self.text)
        self.assertIn("only when they add information", self.norm)
        self.assertIn(
            "An empty or placeholder field is never rendered", self.norm
        )
        # id/location dropped only on the GitHub inline surface
        self.assertIn("omitted on a GitHub inline comment", self.norm)

    def test_inline_rendering_drops_id_and_location(self) -> None:
        block = re.search(
            r"## Canonical inline rendering\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(block)
        body = block.group(1)
        self.assertIn("[<severity>]", body)
        self.assertIn("Evidence:", body)
        self.assertIn("Fix:", body)
        self.assertNotIn("Location:", body)
        self.assertNotIn("<id>", body)


class SkillRenderingsAlignTests(unittest.TestCase):
    """Both Skills render the one compact contract — no silently divergent
    per-Skill finding shape."""

    def _rendered_examples(self, path) -> str:
        return "\n\n".join(_md_blocks(path.read_text(encoding="utf-8")))

    def test_local_report_uses_the_compact_labels_not_block_headers(self) -> None:
        examples = self._rendered_examples(LOCAL_REPORT)
        for label in ("Location:", "Evidence:", "Impact:", "Fix:"):
            self.assertIn(label, examples)
        for header in OLD_BLOCK_HEADERS:
            self.assertNotIn(header, examples)

    def test_github_body_uses_the_compact_labels_not_block_headers(self) -> None:
        examples = self._rendered_examples(GITHUB_BODY)
        for label in ("Location:", "Evidence:", "Impact:", "Fix:"):
            self.assertIn(label, examples)
        for header in OLD_BLOCK_HEADERS:
            self.assertNotIn(header, examples)

    def test_github_inline_is_severity_first_evidence_impact_fix(self) -> None:
        examples = self._rendered_examples(GITHUB_INLINE)
        for token in ("[P1]", "Evidence:", "Impact:", "Fix:"):
            self.assertIn(token, examples)
        self.assertNotIn("Recommended direction:", examples)
        # inline never repeats an id/location machine field
        self.assertNotIn("Location:", examples)

    def test_no_skill_makes_json_the_primary_finding_shape(self) -> None:
        for path in (LOCAL_REPORT, GITHUB_BODY, GITHUB_INLINE, SHARED_FINDING):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("```json", text)

    def test_all_three_surfaces_reference_the_shared_contract(self) -> None:
        for path in (LOCAL_REPORT, GITHUB_BODY, GITHUB_INLINE):
            self.assertIn(
                "shared/templates/finding.md",
                path.read_text(encoding="utf-8"),
            )

    def test_all_three_surfaces_point_at_the_longer_explanation_rule(self) -> None:
        for path in (LOCAL_REPORT, GITHUB_BODY, GITHUB_INLINE):
            self.assertIn(
                "When a longer explanation is justified",
                path.read_text(encoding="utf-8"),
            )


class ReviewSummaryAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.norm = _norm(SHARED_SUMMARY.read_text(encoding="utf-8"))

    def test_summary_defers_finding_rendering_to_the_compact_contract(self) -> None:
        self.assertIn(
            "rendered with the compact, field-oriented finding contract", self.norm
        )
        self.assertIn("read as one coherent contract", self.norm)

    def test_clean_review_no_findings_line_is_preserved(self) -> None:
        self.assertIn("No P0, P1, or P2 findings.", self.norm)


if __name__ == "__main__":
    unittest.main()
