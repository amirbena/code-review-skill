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
# Issue #198 split the canonical rendering exemplars out of finding.md into a
# sibling; finding.md keeps the field/quality contract, the renderings live
# here. The two are cross-linked.
SHARED_FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"
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
        # The rendering exemplars moved to finding-rendering.md (Issue #198).
        self.rendering = SHARED_FINDING_RENDERING.read_text(encoding="utf-8")
        self.rnorm = _norm(self.rendering)

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
            r"## Canonical full rendering\n(.*?)\n## ", self.rendering, re.S
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

    def test_details_field_follows_problem_impact_fix(self) -> None:
        details_block = next(
            (
                b
                for b in re.findall(r"```markdown\n(.*?)\n```", self.rendering, re.S)
                if "**Details:**" in b
            ),
            None,
        )
        self.assertIsNotNone(
            details_block, "finding.md has no rendered example containing a Details field"
        )
        self.assertLess(details_block.index("**Evidence:**"), details_block.index("**Impact:**"))
        self.assertLess(details_block.index("**Impact:**"), details_block.index("**Fix:**"))
        self.assertLess(details_block.index("**Fix:**"), details_block.index("**Details:**"))

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

    def test_three_location_concepts_are_distinct(self) -> None:
        # Issue #164: evidence/detection vs canonical fix/action vs
        # publication anchor stay separate; commentability never sets it.
        self.assertIn(
            "## Fix/action location, evidence location, publication", self.text
        )
        section = re.search(
            r"## Fix/action location, evidence location, publication\n(.*?)\n## ",
            self.text,
            re.S,
        )
        self.assertIsNotNone(section)
        body = _norm(section.group(1))
        self.assertIn("Evidence / detection location", body)
        self.assertIn("Canonical fix / action location", body)
        self.assertIn("Publication anchor", body)
        self.assertIn(
            "evidence location → canonical fix/action location → publication anchor",
            body,
        )
        self.assertIn("never rewrites the location value", body)
        self.assertIn("No silent promotion", body)
        self.assertIn(
            "evidence location; fix/action location unresolved", body
        )
        self.assertIn(
            "never labeled or consumed as a resolved fix/action location", body
        )

    def test_location_field_is_the_canonical_fix_action_location(self) -> None:
        norm = self.norm
        self.assertIn("the finding's canonical location: the fix/action location", norm)
        self.assertIn(
            "never set from where a review platform happens to allow a comment", norm
        )
        # and the rules restate the no-promotion invariant
        self.assertIn(
            "an evidence location is never relabeled as a resolved fix/action location",
            norm,
        )

    def test_full_rendering_shows_optional_evidence_location_line(self) -> None:
        block = re.search(
            r"## Canonical full rendering\n(.*?)\n## ", self.rendering, re.S
        )
        self.assertIsNotNone(block)
        body = block.group(1)
        self.assertIn("**Evidence location:**", body)
        # it sits between Location and Evidence in the variant that shows it
        variant = next(
            b
            for b in re.findall(r"```markdown\n(.*?)\n```", body, re.S)
            if "**Evidence location:**" in b
        )
        self.assertLess(
            variant.index("**Location:**"), variant.index("**Evidence location:**")
        )
        self.assertLess(
            variant.index("**Evidence location:**"), variant.index("**Evidence:**")
        )

    def test_optional_fields_never_render_as_empty_boilerplate(self) -> None:
        self.assertIn("## Optional and surface-specific fields", self.text)
        self.assertIn("only when they add information", self.norm)
        self.assertIn(
            "An empty or placeholder field is never rendered", self.norm
        )
        # id/location dropped only on the GitHub inline surface
        self.assertIn("omitted on a GitHub inline comment", self.norm)

    def test_consolidated_finding_carries_an_affected_locations_field(self) -> None:
        # Issue #177: one shared cause reaching >=2 sites -> one finding
        # plus a required, exhaustive affected-locations list.
        self.assertIn("affected locations", self.norm)
        self.assertIn("It never replaces location", self.norm)
        self.assertIn(
            "## Affected locations on a consolidated finding", self.text
        )
        section = re.search(
            r"## Affected locations on a consolidated finding\n(.*?)\n## ",
            self.text,
            re.S,
        )
        self.assertIsNotNone(section)
        body = _norm(section.group(1))
        self.assertIn("reaches at least two sites", body)
        self.assertIn(
            "the list is required on such a finding and part of its mandatory core",
            body,
        )
        self.assertIn(
            "a consolidated finding rendered without it, or with fewer than two "
            "entries, is not publishable",
            body,
        )
        self.assertIn("it is exhaustive for the manifestation sites the review found", body)
        self.assertIn(
            "rendered on every surface that renders the finding", body
        )
        self.assertIn(
            "does not change the finding's identity, severity, evidence bar, "
            "canonical location",
            body,
        )
        self.assertIn(
            "never used to pack unrelated findings into one entry", body
        )

    def test_affected_locations_field_is_not_both_optional_and_required(self) -> None:
        # F2: the contract must not describe the field as simultaneously
        # optional and required.
        self.assertIn(
            "conditionally required", _norm(self.text)
        )
        # the Fields entry names it required-on-consolidated / absent otherwise
        self.assertIn("required, on every consolidated root-cause finding", self.norm)
        self.assertIn(
            "absent on every ordinary single-site finding", self.norm
        )
        # the "Optional and surface-specific fields" entry explicitly says it is
        # not optional on a consolidated finding
        opt = re.search(
            r"## Optional and surface-specific fields\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(opt)
        opt_body = _norm(opt.group(1))
        self.assertIn("affected locations", opt_body)
        self.assertIn("It is **not optional**".replace("**", ""), opt_body)
        self.assertIn("listed here only for its surface-specific", opt_body)
        # the mandatory-core section carries the consolidated addition
        qc = re.search(
            r"## Finding quality contract\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(qc)
        qc_body = _norm(qc.group(1))
        self.assertIn(
            "not publishable without an exhaustive affected-locations list of "
            "at least two known manifestation sites",
            qc_body,
        )

    def test_full_rendering_has_a_consolidated_variant_with_affected_locations(self) -> None:
        block = re.search(
            r"## Canonical full rendering\n(.*?)\n## ", self.rendering, re.S
        )
        self.assertIsNotNone(block)
        body = block.group(1)
        self.assertIn("**Affected locations:**", body)
        variant = next(
            b
            for b in re.findall(r"```markdown\n(.*?)\n```", body, re.S)
            if "**Affected locations:**" in b
        )
        self.assertLess(
            variant.index("- **Location:**"), variant.index("**Affected locations:**")
        )
        self.assertLess(
            variant.index("**Affected locations:**"), variant.index("**Evidence:**")
        )

    def test_contextual_evidence_provenance_field_is_documented(self) -> None:
        # Issue #118: optional provenance field, evidence-gated, never a
        # severity input, folds into evidence prose on the inline surface.
        self.assertIn("## Contextual evidence and provenance", self.text)
        section = re.search(
            r"## Contextual evidence and provenance\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(section)
        body = _norm(section.group(1))
        self.assertIn("A finding is always attributable to code evidence", body)
        self.assertIn("Optional and evidence-gated", body)
        self.assertIn("Provenance is not a severity input", body)
        self.assertIn(
            "never calculates, raises, lowers, or overrides severity", body
        )
        self.assertIn(
            "never changes the finding's identity, its deduplication, or the "
            "mechanical decision derivation",
            body,
        )
        self.assertIn("folds into evidence prose", body)
        # the rendering exemplar carries the optional line
        self.assertIn("**Contextual evidence:**", self.rendering)
        variant = next(
            b
            for b in re.findall(r"```markdown\n(.*?)\n```", self.rendering, re.S)
            if "**Contextual evidence:**" in b
        )
        self.assertLess(
            variant.index("**Evidence:**"), variant.index("**Contextual evidence:**")
        )
        self.assertLess(
            variant.index("**Contextual evidence:**"), variant.index("**Impact:**")
        )

    def test_contextual_evidence_is_optional_not_mandatory_core(self) -> None:
        opt = re.search(
            r"## Optional and surface-specific fields\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(opt)
        opt_body = _norm(opt.group(1))
        self.assertIn("contextual evidence", opt_body)
        self.assertIn("Absent on a finding that rests on code evidence alone", opt_body)
        # not added to the mandatory-core question
        self.assertIn("What? Where? Evidence? Impact? Fix?", self.norm)
        self.assertNotIn("What? Where? Evidence? Contextual", self.norm)

    def test_inline_rendering_drops_id_and_location(self) -> None:
        block = re.search(
            r"## Canonical inline rendering\n(.*?)\n## ", self.rendering, re.S
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
        for path in (
            LOCAL_REPORT,
            GITHUB_BODY,
            GITHUB_INLINE,
            SHARED_FINDING,
            SHARED_FINDING_RENDERING,
        ):
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

    def test_all_three_surfaces_expose_the_affected_locations_rendering(self) -> None:
        # F3 (#177): consolidated findings must retain affected locations on
        # each delivery surface, deferring to the shared contract.
        for path in (LOCAL_REPORT, GITHUB_BODY, GITHUB_INLINE):
            text = path.read_text(encoding="utf-8")
            self.assertIn("consolidated root-cause finding", text, path.name)
            self.assertIn(
                "Affected locations on a consolidated finding", text, path.name
            )
        # the two full-rendering surfaces show the structured list
        for path in (LOCAL_REPORT, GITHUB_BODY):
            examples = self._rendered_examples(path)
            self.assertIn("**Affected locations:**", examples, path.name)
        # the inline surface routes it to the body, never one comment per site
        inline = _norm(GITHUB_INLINE.read_text(encoding="utf-8"))
        self.assertIn("never split into one inline comment per affected call path", inline)

    def test_github_body_places_consolidated_findings_in_the_body(self) -> None:
        body = _norm(GITHUB_BODY.read_text(encoding="utf-8"))
        self.assertIn(
            "A consolidated root-cause finding (one shared cause reaching at "
            "least two sites) always renders in the body",
            body,
        )
        self.assertIn("it is one body finding, never one inline comment per affected call path", body)

    def test_per_skill_detail_defaults_and_github_override_are_explicit(self) -> None:
        local = _norm(LOCAL_REPORT.read_text(encoding="utf-8"))
        github = _norm(GITHUB_BODY.read_text(encoding="utf-8"))
        self.assertIn("include_finding_details defaults to true", local)
        self.assertIn("include_finding_details defaults to false", github)
        self.assertIn("finding-level decision", github)


class ReviewSummaryAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.norm = _norm(SHARED_SUMMARY.read_text(encoding="utf-8"))

    def test_summary_defers_finding_rendering_to_the_compact_contract(self) -> None:
        self.assertIn(
            "rendered with the compact, field-oriented finding contract", self.norm
        )
        self.assertIn("read as one coherent contract", self.norm)

    def test_clean_review_omits_findings_section(self) -> None:
        self.assertIn("Omit the section completely on a clean review", self.norm)


if __name__ == "__main__":
    unittest.main()
