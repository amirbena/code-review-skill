"""Rendering-level fail-closed verdict checks (Issue #784).

Canonical behavior: ``shared/policies/review-stopping-criteria.md``,
"Labeling". A report whose Metadata says ``Coverage: incomplete`` must render
``REVIEW INCOMPLETE`` in both Result and Decision, and a hybrid such as
``✅ Review Clean (coverage incomplete, see Metadata)`` is never valid.
"""

from __future__ import annotations

import re
import unittest

from tests.reference.review.change_risk_signals import Depth
from tests.reference.review.review_stopping_criteria import (
    PassResult,
    decision_label,
    evaluate_coverage,
)
from tests.support.paths import REPO_ROOT

SAMPLES = REPO_ROOT / "tests/unit/review/findings/structured_output_samples"
_RESULT = re.compile(r"^\*\*Result:[^\n]*\*\*", re.M)
_DECISION = re.compile(r"^\*\*(REVIEW CLEAN|CHANGES REQUIRED|REVIEW INCOMPLETE)\*\*\s*$", re.M)
_COVERAGE = re.compile(r"^\s*-?\s*[Cc]overage:\s*`?(complete|incomplete)\b", re.M)


def report_violations(text: str) -> list[str]:
    """Result, Decision, and Metadata coverage must agree; empty means valid."""
    problems: list[str] = []
    result = _RESULT.search(text)
    decision = _DECISION.search(text)
    coverage = _COVERAGE.search(text)
    if not result:
        return ["missing Result"]
    result_text = result.group(0).lower()
    outcome = decision.group(1) if decision else (
        "REVIEW INCOMPLETE" if "incomplete" in result_text else "other"
    )
    clean_reading = "clean" in result_text or "✅" in result_text
    if clean_reading and "incomplete" in result_text:
        problems.append("hybrid success rendering")
    if coverage and coverage.group(1) == "incomplete":
        if clean_reading:
            problems.append("clean-reading Result with incomplete coverage")
        if outcome != "REVIEW INCOMPLETE":
            problems.append("Decision is not REVIEW INCOMPLETE with incomplete coverage")
    elif outcome == "REVIEW INCOMPLETE" or "incomplete" in result_text:
        problems.append("incomplete outcome without incomplete coverage")
    return problems


def render(coverage, p1: int = 0) -> str:
    """Compose a minimal report from the reference model's verdict."""
    mechanical = "CHANGES REQUIRED" if p1 else "REVIEW CLEAN"
    label = decision_label(coverage, mechanical)
    marker = {"REVIEW CLEAN": "✅ Review Clean", "CHANGES REQUIRED": "❌ Changes Required"}
    result = marker.get(label, "⚠️ Review Incomplete")
    return (
        f"**Result: {result}**\n\n### Decision\n**{label}**\n\n"
        f"### Review Metadata\n\n- P0: 0, P1: {p1}, P2: 0\n- Coverage: {coverage.coverage}\n"
    )


class ScenarioTests(unittest.TestCase):
    def test_missing_mandatory_policy_with_zero_blockers_is_incomplete(self) -> None:
        coverage = evaluate_coverage(
            Depth.STANDARD, passes=(PassResult("evidence.md loaded", False),)
        )
        text = render(coverage)
        self.assertEqual(coverage.coverage, "incomplete")
        self.assertIn("**REVIEW INCOMPLETE**", text)
        self.assertEqual(report_violations(text), [])

    def test_incomplete_scope_with_zero_blockers_is_incomplete(self) -> None:
        coverage = evaluate_coverage(Depth.STANDARD, passes=(), review_target_established=False)
        self.assertEqual(report_violations(render(coverage)), [])
        self.assertIn("**REVIEW INCOMPLETE**", render(coverage))

    def test_incomplete_coverage_never_renders_clean_even_with_blockers(self) -> None:
        coverage = evaluate_coverage(Depth.STANDARD, passes=(), review_target_established=False)
        text = render(coverage, p1=1)
        self.assertNotIn("Review Clean", text)
        self.assertEqual(report_violations(text), [])

    def test_complete_coverage_with_zero_blockers_remains_clean(self) -> None:
        text = render(evaluate_coverage(Depth.STANDARD, passes=(PassResult("evidence.md loaded", True),)))
        self.assertIn("**REVIEW CLEAN**", text)
        self.assertEqual(report_violations(text), [])

    def test_complete_coverage_with_a_blocker_is_changes_required(self) -> None:
        text = render(evaluate_coverage(Depth.STANDARD, passes=()), p1=1)
        self.assertIn("**CHANGES REQUIRED**", text)
        self.assertEqual(report_violations(text), [])


class HybridRejectionTests(unittest.TestCase):
    def test_reported_hybrid_line_is_rejected(self) -> None:
        text = (
            "**Result: ✅ Review Clean (coverage incomplete, see Metadata)**\n\n"
            "### Decision\n**REVIEW CLEAN**\n\n### Review Metadata\n\n- Coverage: incomplete — evidence.md not loaded\n"
        )
        problems = report_violations(text)
        self.assertIn("hybrid success rendering", problems)
        self.assertIn("Decision is not REVIEW INCOMPLETE with incomplete coverage", problems)

    def test_clean_result_with_incomplete_metadata_is_rejected(self) -> None:
        text = render(evaluate_coverage(Depth.STANDARD, passes=())).replace(
            "Coverage: complete", "Coverage: incomplete — x"
        )
        self.assertTrue(report_violations(text))


class SampleParityTests(unittest.TestCase):
    def test_every_packaged_sample_agrees_across_result_decision_and_metadata(self) -> None:
        samples = sorted(SAMPLES.glob("*/*.md"))
        self.assertGreaterEqual(len(samples), 6)
        for path in samples:
            with self.subTest(sample=path.relative_to(SAMPLES).as_posix()):
                self.assertEqual(report_violations(path.read_text(encoding="utf-8")), [])

    def test_both_skills_ship_an_incomplete_sample(self) -> None:
        for skill in ("local-code-review", "github-pr-review"):
            names = [p.name for p in (SAMPLES / skill).glob("incomplete*.md")]
            self.assertTrue(names, skill)


if __name__ == "__main__":
    unittest.main()
