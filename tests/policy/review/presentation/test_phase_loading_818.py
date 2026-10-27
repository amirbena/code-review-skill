"""Phase-aware loading contract for #818.

The finding schema, rendering, summary and remediation files are required for
coverage but opened at the phase that first uses them. The phase may be earlier
than the coverage step, never later, because the `Coverage:` line is derived
from files actually opened. Prose assertions only.
"""

from __future__ import annotations

import re
import unittest

from scripts.validation import context_size_report as report
from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _text

PHASED = {
    "local-code-review": {
        "shared/templates/finding.md",
        "shared/templates/finding-rendering.md",
        "shared/templates/review-summary.md",
        "shared/policies/remediation-guidance.md",
    },
    "github-pr-review": {
        "shared/templates/finding.md",
        "shared/templates/finding-rendering.md",
        "shared/templates/review-summary.md",
        "shared/policies/remediation-guidance.md",
    },
}
# Applied by the coverage, decision and verdict-check Steps, so never deferred.
STAY_BEFORE_STEP_1 = ("severity.md", "review-stopping-criteria.md", "verdict-consistency.md")
RUNBOOK = {
    "local-code-review": "skills/local-code-review/runbooks/local-review.md",
    "github-pr-review": "skills/github-pr-review/runbooks/passive-pr-review.md",
}
COVERAGE_STEP = re.compile(r"^(\d+)([a-z]?)\.\s+\*\*Evaluate review coverage\*\*", re.M)
STEP = re.compile(r"^(\d+)([a-z]?)\.\s", re.M)


def _phased_paragraph(skill: str) -> str:
    text = (REPO_ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    for paragraph in re.split(r"\n\s*\n", text):
        if paragraph.startswith("Always, by phase"):
            return paragraph
    raise AssertionError(f"{skill} has no 'Always, by phase' paragraph")


class PhaseLoadingTests(unittest.TestCase):
    def test_phased_group_is_exactly_the_verified_files(self):
        for skill, expected in PHASED.items():
            data = report.build_skill_report(REPO_ROOT, skill)
            self.assertEqual({f.path for f in data.phased}, expected, skill)

    def test_phased_files_leave_the_before_step_1_set_but_stay_required(self):
        for skill, expected in PHASED.items():
            data = report.build_skill_report(REPO_ROOT, skill)
            before = {f.path for f in data.unconditional}
            self.assertFalse(before & expected, skill)
            built = report.report_dict(data)
            self.assertGreater(built["whole_review_default"]["bytes"], built["before_step_1"]["bytes"])

    def test_coverage_decision_and_verdict_files_stay_before_step_1(self):
        for skill in PHASED:
            before = {f.path for f in report.build_skill_report(REPO_ROOT, skill).unconditional}
            for name in STAY_BEFORE_STEP_1:
                self.assertIn(f"shared/policies/{name}", before, (skill, name))

    def test_phase_never_reaches_past_the_coverage_step(self):
        for skill in PHASED:
            runbook = (REPO_ROOT / RUNBOOK[skill]).read_text(encoding="utf-8")
            coverage = COVERAGE_STEP.search(runbook)
            self.assertIsNotNone(coverage, skill)
            order = [m.group(0).strip() for m in STEP.finditer(runbook)]
            coverage_key = f"{coverage.group(1)}{coverage.group(2)}."
            paragraph = _phased_paragraph(skill)
            self.assertIn("never later than the runbook's coverage step", paragraph)
            self.assertIn("before the coverage step", paragraph)
            for named in re.findall(r"step (\d+)", paragraph):
                self.assertIn(f"{named}.", order, (skill, named))
                self.assertLess(order.index(f"{named}."), order.index(coverage_key), (skill, named))

    def test_stopping_criteria_states_phase_without_a_new_trigger(self):
        text = _text(REPO_ROOT / "shared/policies/review-stopping-criteria.md")
        self.assertIn('"Always, by phase"', text)
        self.assertIn("may be earlier than the coverage step, never later", text)
        self.assertIn("derived from files actually opened", text)

    def test_checkpoint_sentence_excludes_only_the_phase_group(self):
        for skill in PHASED:
            text = _text(REPO_ROOT / "skills" / skill / "SKILL.md")
            self.assertIn("load the unconditional files above, except the phase-loaded group", text)


if __name__ == "__main__":
    unittest.main()
