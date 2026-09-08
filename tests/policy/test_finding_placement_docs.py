#!/usr/bin/env python3
"""Documentation-contract checks for fix/action-location anchoring (Issue #164).

Pins the rule that `github-pr-review` anchors an inline review comment at
the finding's canonical fix/action location — not merely where the
problem is observable, and not a line chosen because GitHub allows a
comment there — plus the deterministic candidate-resolution order, the
not-inline-commentable and unresolved fallbacks, and the invariant that
publication placement never mutates finding identity/severity/dedup.

Assertions target whitespace-normalized prose and named sections, not
brittle exact whitespace, matching the other doc-pinning modules here.
"""

from __future__ import annotations

import re
import unittest

from tests.reference import finding_contract as fc
from tests.support.paths import REPO_ROOT

PLACEMENT = REPO_ROOT / "skills/github-pr-review/policies/finding-placement.md"
PR_SCOPE = REPO_ROOT / "skills/github-pr-review/policies/pr-scope.md"
INLINE = REPO_ROOT / "skills/github-pr-review/templates/inline-finding.md"
SUMMARY = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
RUNBOOK = REPO_ROOT / "skills/github-pr-review/runbooks/active-pr-review.md"
SHARED_FINDING = REPO_ROOT / "shared/templates/finding.md"
SHARED_EVIDENCE = REPO_ROOT / "shared/policies/evidence.md"
SHARED_REMEDIATION = REPO_ROOT / "shared/policies/remediation-guidance.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


class AnchorAtFixLocationSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = PLACEMENT.read_text(encoding="utf-8")
        self.norm = _norm(self.text)
        section = re.search(
            r"## Anchor at the fix/action location\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(section, "finding-placement.md missing the anchor section")
        self.section = _norm(section.group(1))

    def test_section_exists(self) -> None:
        self.assertIn("## Anchor at the fix/action location", self.text)

    def test_anchor_is_the_canonical_fix_action_location(self) -> None:
        self.assertIn(
            "publication anchor is its canonical fix/action location", self.section
        )
        self.assertIn("the line an author changes to resolve the finding", self.section)
        self.assertIn("not a line merely where the problem is observable", self.section)

    def test_commentability_is_not_a_semantic_anchor(self) -> None:
        self.assertIn("Commentable in the GitHub diff", self.section)
        self.assertIn("is a publication constraint", self.section)
        self.assertIn("never evidence that a line is the correct semantic anchor", self.section)
        self.assertIn("never discovers or overrides the fix/action location", self.section)

    def test_semantic_selection_precedes_deterministic_tiebreak(self) -> None:
        # order: identify semantic candidates -> drop evidence-only ->
        # deterministic tie-break -> only then GitHub commentability.
        order_markers = [
            "Identify the semantically valid fix/action candidate",
            "Discard candidates that are only evidence/observation locations",
            "select deterministically",
            "Only now evaluate GitHub inline-commentability",
        ]
        positions = [self.section.index(m) for m in order_markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("narrowest changed range enclosing the", self.section)
        self.assertIn("lowest changed line number", self.section)
        self.assertIn("lexical order", self.section)
        self.assertIn(
            "never outranks a semantically better fix/action location", self.section
        )
        self.assertIn(
            "never sends the selection back to a candidate discarded", self.section
        )

    def test_evidence_and_fix_differ_anchors_at_fix(self) -> None:
        self.assertIn(
            "anchor the inline comment at the fix/action location", self.section
        )
        self.assertIn("may reference the evidence/source location", self.section)
        self.assertIn("including one in another file", self.section)

    def test_fix_location_not_commentable_goes_to_body_not_a_nearby_line(self) -> None:
        self.assertIn(
            "Fix/action location resolved but not inline-commentable", self.section
        )
        self.assertIn("the canonical fix/action location is unchanged", self.section)
        self.assertIn("Move the finding's full representation into the review body", self.section)
        self.assertIn(
            "Do not attach it to an unrelated or merely-nearby line", self.section
        )
        self.assertIn("clearly non-authoritative", self.section)

    def test_unresolved_fix_location_is_explicit_not_promoted(self) -> None:
        self.assertIn("Fix/action location unresolved", self.section)
        self.assertIn(
            "no actionable fix/action location can be confidently determined",
            self.section,
        )
        self.assertIn(
            "never anchored to the evidence line as though that were the fix",
            self.section,
        )

    def test_placement_never_mutates_identity(self) -> None:
        self.assertIn("What anchor selection does not change", self.section)
        self.assertIn("never change the finding's Location", self.section)
        self.assertIn("its identity, its severity, deduplication", self.section)
        self.assertIn(
            "keyed on the canonical semantic fix/action location, "
            "not on the GitHub publication anchor",
            self.section,
        )

    def test_reactive_and_proactive_fallbacks_converge(self) -> None:
        self.assertIn(
            "reactive fallback and the proactive", self.norm
        )
        self.assertIn("GitHub rejection never rewrites either", self.norm)


class IdentityUsesSemanticLocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.norm = _norm(PR_SCOPE.read_text(encoding="utf-8"))

    def test_identity_keyed_on_fix_action_location_not_publication_anchor(self) -> None:
        self.assertIn("canonical semantic fix/action location where one is resolved", self.norm)
        self.assertIn("never the eventual GitHub publication anchor", self.norm)

    def test_inline_to_body_switch_does_not_change_identity(self) -> None:
        self.assertIn(
            "inline→review-body switch, a GitHub API rejection, or a diff limitation "
            "therefore does not change a finding's identity",
            self.norm,
        )

    def test_unresolved_case_is_deterministic_without_relabeling_evidence(self) -> None:
        self.assertIn("use the best-known (evidence-scoped) coordinate marked as unresolved", self.norm)
        self.assertIn("never matched as equal to a resolved fix/action location", self.norm)
        self.assertIn("evidence location is not reclassified as a fix/action location", self.norm)


class WiringTests(unittest.TestCase):
    def test_inline_template_anchors_at_fix_location(self) -> None:
        norm = _norm(INLINE.read_text(encoding="utf-8"))
        self.assertIn("anchor at the finding's canonical fix/action location", norm)
        self.assertIn("not merely where the problem is observable", norm)
        self.assertIn("Anchor at the fix/action location", norm)

    def test_summary_template_covers_the_new_fallbacks(self) -> None:
        norm = _norm(SUMMARY.read_text(encoding="utf-8"))
        self.assertIn("fix/action location is outside the PR diff / not inline-commentable", norm)
        self.assertIn("fix/action location is unresolved", norm)
        self.assertIn("non-authoritative navigation aid", norm)

    def test_runbook_step_11_orders_semantics_before_commentability(self) -> None:
        norm = _norm(RUNBOOK.read_text(encoding="utf-8"))
        self.assertIn(
            "Anchor each inline-eligible finding at its canonical fix/action location",
            norm,
        )
        self.assertIn("semantic candidate resolution before GitHub commentability", norm)
        self.assertIn(
            "canonical location and identity are not altered", norm
        )

    def test_shared_evidence_policy_points_at_the_distinction(self) -> None:
        norm = _norm(SHARED_EVIDENCE.read_text(encoding="utf-8"))
        self.assertIn(
            "distinguishes the evidence/detection location from the "
            "canonical fix/action location",
            norm,
        )
        self.assertIn("prefers the resolved fix/action location", norm)

    def test_shared_remediation_policy_defers_placement(self) -> None:
        norm = _norm(SHARED_REMEDIATION.read_text(encoding="utf-8"))
        self.assertIn("Fix direction targets or describes the finding's canonical", norm)
        self.assertIn("does not by itself decide publication placement", norm)
        self.assertIn("remains its canonical owner", norm)


class ReferenceModelInvariantTests(unittest.TestCase):
    """Reference-model behavior backing the doc rules (Issue #164)."""

    def _f(self, **kw) -> fc.Finding:
        base = dict(
            id="F1",
            severity=fc.Severity.P1,
            title="Missing idempotency guard",
            location="src/pay/handler.py:42",
            evidence="The side effect runs before the dedupe check.",
            impact="A retried event double-charges.",
            fix="Move the dedupe check before the side effect.",
        )
        base.update(kw)
        return fc.Finding(**base)

    def test_evidence_location_equal_to_location_renders_nothing_extra(self) -> None:
        f = self._f(evidence_location="src/pay/handler.py:42")
        self.assertFalse(fc.renders_evidence_location(f))
        self.assertNotIn("Evidence location", fc.render_full(f))

    def test_distinct_evidence_location_renders(self) -> None:
        f = self._f(evidence_location="src/pay/gateway.py:9")
        self.assertTrue(fc.renders_evidence_location(f))
        self.assertIn("- **Evidence location:** src/pay/gateway.py:9", fc.render_full(f))

    def test_unresolved_fix_location_never_promotes_the_evidence_location(self) -> None:
        f = self._f(
            location="src/pay/gateway.py:9",
            evidence_location="src/pay/gateway.py:9",
            fix_location_resolved=False,
        )
        self.assertFalse(fc.renders_evidence_location(f))
        self.assertIn(
            "_(evidence location; fix/action location unresolved)_", fc.render_full(f)
        )

    def test_summary_pointer_and_inline_use_the_canonical_location_only(self) -> None:
        f = self._f(evidence_location="src/pay/gateway.py:9")
        self.assertIn("`src/pay/handler.py:42`", fc.render_summary_pointer(f))
        self.assertNotIn("gateway.py", fc.render_summary_pointer(f))
        self.assertNotIn("Evidence location:", fc.render_inline(f))


if __name__ == "__main__":
    unittest.main()
