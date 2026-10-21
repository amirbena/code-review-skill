"""Rendering-level fail-closed verdict checks (Issue #784).

Canonical behavior: ``shared/policies/review-stopping-criteria.md``,
"Labeling". A report whose Metadata says coverage is incomplete must render
``REVIEW INCOMPLETE`` in both Result and Decision, and a hybrid such as
``✅ Review Clean (coverage incomplete, see Metadata)`` is never valid.

Every check runs over shipped text — the packaged report templates and the
per-mode structured-output samples (local, GitHub passive, GitHub active) —
or over mutations of that text. The reference model only supplies the expected
label; no report is composed by the test itself.
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
LOCAL_TEMPLATE = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
GITHUB_TEMPLATE = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"

_RESULT = re.compile(r"^\*\*Result:[^\n]*\*\*", re.M)
_DECISION_BLOCK = re.compile(r"(### Decision\n)\*\*[A-Z ]+\*\*", re.M)
_DECISION = re.compile(
    r"^\*\*(REVIEW CLEAN|CHANGES REQUIRED|REVIEW INCOMPLETE|APPROVE|REQUEST CHANGES)\*\*\s*$", re.M
)
# GitHub reports render the same three outcomes with Approve / Request Changes wording.
CANONICAL = {"APPROVE": "REVIEW CLEAN", "REQUEST CHANGES": "CHANGES REQUIRED"}
_COVERAGE = re.compile(r"^(\s*-?\s*[Cc]overage:\s*`?)(complete|incomplete)([^\n]*)$", re.M)
_BLOCK = re.compile(r"```markdown\n(.*?)```", re.S)

INCOMPLETE_RESULT = "**Result: ⚠️ Review Incomplete**"
HYBRIDS = (
    "**Result: ✅ Review Clean (coverage incomplete, see Metadata)**",
    "**Result: ✅ REVIEW CLEAN (coverage: incomplete)**",
)


def report_violations(text: str) -> list[str]:
    """Result, Decision, and Metadata coverage must agree; empty means valid."""
    result = _RESULT.search(text)
    if not result:
        return ["missing Result"]
    decision = _DECISION.search(text)
    coverage = _COVERAGE.search(text)
    result_text = result.group(0).lower()
    clean_reading = "clean" in result_text or "✅" in result_text
    outcome = CANONICAL.get(decision.group(1), decision.group(1)) if decision else (
        "REVIEW INCOMPLETE" if "incomplete" in result_text else "other"
    )
    problems: list[str] = []
    if clean_reading and "incomplete" in result_text:
        problems.append("hybrid success rendering")
    if coverage and coverage.group(2) == "incomplete":
        if clean_reading:
            problems.append("clean-reading Result with incomplete coverage")
        if outcome != "REVIEW INCOMPLETE":
            problems.append("Decision is not REVIEW INCOMPLETE with incomplete coverage")
    elif outcome == "REVIEW INCOMPLETE" or "incomplete" in result_text:
        problems.append("incomplete outcome without incomplete coverage")
    return problems


def with_result(text: str, result: str) -> str:
    return _RESULT.sub(lambda _m: result, text, count=1)


def with_decision(text: str, label: str) -> str:
    return _DECISION_BLOCK.sub(lambda m: f"{m.group(1)}**{label}**", text, count=1)


def with_coverage(text: str, value: str, reason: str = "") -> str:
    if _COVERAGE.search(text):
        return _COVERAGE.sub(lambda m: f"{m.group(1)}{value}{reason}", text, count=1)
    return text.rstrip("\n") + f"\n\n- Coverage: {value}{reason}\n"


def as_incomplete(text: str, reason: str = " — evidence.md was not loaded") -> str:
    """The correct rendering of the same review under incomplete coverage."""
    return with_decision(with_result(with_coverage(text, "incomplete", reason), INCOMPLETE_RESULT), "REVIEW INCOMPLETE")


def label_of(text: str) -> str:
    raw = _DECISION.search(text).group(1)
    return CANONICAL.get(raw, raw)


def shipped_samples() -> list:
    return sorted(SAMPLES.glob("*/*.md"))


def template_reports(path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    return [b for b in _BLOCK.findall(raw) if _RESULT.search(b)]


class ShippedSampleTests(unittest.TestCase):
    def test_every_sample_agrees_across_result_decision_and_metadata(self) -> None:
        samples = shipped_samples()
        self.assertGreaterEqual(len(samples), 6)
        for path in samples:
            with self.subTest(sample=path.relative_to(SAMPLES).as_posix()):
                self.assertEqual(report_violations(path.read_text(encoding="utf-8")), [])

    def test_samples_cover_local_and_both_github_publication_modes(self) -> None:
        modes = {p.parent.name for p in shipped_samples()}
        self.assertEqual(modes, {"local-code-review", "github-pr-review"})
        github = "".join(p.read_text(encoding="utf-8") for p in (SAMPLES / "github-pr-review").glob("*.md"))
        self.assertIn("publication_mode: `passive`", github)
        self.assertIn("publication_mode: `active`", github)

    def test_both_skills_ship_an_incomplete_sample(self) -> None:
        for skill in ("local-code-review", "github-pr-review"):
            self.assertTrue(list((SAMPLES / skill).glob("incomplete*.md")), skill)


class ShippedTemplateTests(unittest.TestCase):
    def test_template_examples_are_internally_consistent(self) -> None:
        for path in (LOCAL_TEMPLATE, GITHUB_TEMPLATE):
            blocks = template_reports(path)
            self.assertTrue(blocks, path.name)
            for block in blocks:
                with self.subTest(template=path.name, result=_RESULT.search(block).group(0)):
                    self.assertEqual(report_violations(block), [])

    def test_local_template_ships_an_incomplete_example_with_metadata(self) -> None:
        incomplete = [b for b in template_reports(LOCAL_TEMPLATE) if "REVIEW INCOMPLETE" in b]
        self.assertEqual(len(incomplete), 1)
        self.assertIn("- Coverage: incomplete", incomplete[0])
        self.assertIn(INCOMPLETE_RESULT, incomplete[0])

    def test_templates_state_the_no_hybrid_rule(self) -> None:
        local = re.sub(r"\s+", " ", LOCAL_TEMPLATE.read_text(encoding="utf-8"))
        github = re.sub(r"\s+", " ", GITHUB_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("No hybrid", local)
        self.assertIn("Review Clean (coverage incomplete, see Metadata)", local)
        self.assertIn("No hybrid", github)
        self.assertIn("never a clean-reading `Result`", github)


class HybridRejectionTests(unittest.TestCase):
    def test_hybrid_result_is_rejected_on_every_shipped_sample(self) -> None:
        for path in shipped_samples():
            base = as_incomplete(path.read_text(encoding="utf-8"))
            self.assertEqual(report_violations(base), [], path.name)
            for hybrid in HYBRIDS:
                with self.subTest(sample=path.name, hybrid=hybrid):
                    problems = report_violations(with_result(base, hybrid))
                    self.assertIn("hybrid success rendering", problems)
                    self.assertIn("clean-reading Result with incomplete coverage", problems)

    def test_the_reported_regression_is_rejected_verbatim(self) -> None:
        clean = (SAMPLES / "local-code-review/clean-p2-uncommitted.md").read_text(encoding="utf-8")
        text = with_result(with_coverage(clean, "incomplete", " — evidence.md not loaded"), HYBRIDS[0])
        problems = report_violations(text)
        self.assertIn("hybrid success rendering", problems)
        self.assertIn("Decision is not REVIEW INCOMPLETE with incomplete coverage", problems)

    def test_template_incomplete_example_rejects_a_hybrid_rewrite(self) -> None:
        block = next(b for b in template_reports(LOCAL_TEMPLATE) if "REVIEW INCOMPLETE" in b)
        self.assertEqual(report_violations(block), [])
        self.assertTrue(report_violations(with_result(block, HYBRIDS[0])))
        self.assertTrue(report_violations(with_decision(block, "REVIEW CLEAN")))


class ConsistencyAcrossModesTests(unittest.TestCase):
    """Result, Decision and Metadata, for incomplete and complete coverage, over
    the local, GitHub passive and GitHub active shipped samples."""

    def test_incomplete_coverage_requires_incomplete_result_and_decision(self) -> None:
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            with self.subTest(sample=path.name, case="incomplete rendering is valid"):
                self.assertEqual(report_violations(as_incomplete(text)), [])
            with self.subTest(sample=path.name, case="incomplete metadata, kept outcome"):
                kept = with_coverage(text, "incomplete", " — evidence.md was not loaded")
                if label_of(text) != "REVIEW INCOMPLETE":
                    self.assertTrue(report_violations(kept))

    def test_missing_mandatory_policy_with_zero_blockers_is_not_clean(self) -> None:
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            if label_of(text) != "REVIEW CLEAN":
                continue
            with self.subTest(sample=path.name):
                stale = with_coverage(text, "incomplete", " — required policy review-stopping-criteria.md not loaded")
                self.assertIn("clean-reading Result with incomplete coverage", report_violations(stale))
                self.assertEqual(report_violations(as_incomplete(text)), [])

    def test_blocking_findings_do_not_outrank_incomplete_coverage(self) -> None:
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            if label_of(text) != "CHANGES REQUIRED":
                continue
            with self.subTest(sample=path.name):
                stale = with_coverage(text, "incomplete", " — partition not completed")
                self.assertIn(
                    "Decision is not REVIEW INCOMPLETE with incomplete coverage",
                    report_violations(stale),
                )
                self.assertEqual(report_violations(as_incomplete(text)), [])

    def test_complete_coverage_keeps_the_clean_and_blocking_verdicts(self) -> None:
        seen = set()
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            label = label_of(text)
            if label == "REVIEW INCOMPLETE":
                continue
            seen.add(label)
            with self.subTest(sample=path.name):
                complete = with_coverage(text, "complete")
                self.assertEqual(report_violations(complete), [])
                self.assertEqual(label_of(complete), label)
        self.assertEqual(seen, {"REVIEW CLEAN", "CHANGES REQUIRED"})

    def test_incomplete_outcome_requires_incomplete_metadata(self) -> None:
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            if label_of(text) != "REVIEW INCOMPLETE":
                continue
            with self.subTest(sample=path.name):
                self.assertIn(
                    "incomplete outcome without incomplete coverage",
                    report_violations(with_coverage(text, "complete")),
                )


class ReferenceModelAgreementTests(unittest.TestCase):
    """The reference model's expected label must equal the label of the shipped
    sample rendered for the same situation."""

    def _sample(self, rel: str) -> str:
        return (SAMPLES / rel).read_text(encoding="utf-8")

    def test_expected_label_matches_the_shipped_rendering(self) -> None:
        clean = self._sample("local-code-review/clean-p2-uncommitted.md")
        blocking = self._sample("local-code-review/blocking-committed.md")
        incomplete_cov = evaluate_coverage(Depth.STANDARD, passes=(PassResult("evidence.md loaded", False),))
        complete_cov = evaluate_coverage(Depth.STANDARD, passes=(PassResult("evidence.md loaded", True),))
        cases = (
            (complete_cov, "REVIEW CLEAN", clean, clean),
            (complete_cov, "CHANGES REQUIRED", blocking, blocking),
            (incomplete_cov, "REVIEW CLEAN", clean, as_incomplete(clean)),
            (incomplete_cov, "CHANGES REQUIRED", blocking, as_incomplete(blocking)),
        )
        for coverage, mechanical, _source, rendered in cases:
            with self.subTest(coverage=coverage.coverage, mechanical=mechanical):
                self.assertEqual(label_of(rendered), decision_label(coverage, mechanical))
                self.assertEqual(report_violations(rendered), [])


if __name__ == "__main__":
    unittest.main()
