"""Wiring for #784: a clean verdict requires complete coverage.

Prose assertions on the canonical stopping-criteria policy, both entrypoints,
all three runbooks, and both report templates.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _text

STOPPING = REPO_ROOT / "shared/policies/review-stopping-criteria.md"
SKILLS = (
    REPO_ROOT / "skills/local-code-review/SKILL.md",
    REPO_ROOT / "skills/github-pr-review/SKILL.md",
)
RUNBOOKS = (
    REPO_ROOT / "skills/local-code-review/runbooks/local-review.md",
    REPO_ROOT / "skills/github-pr-review/runbooks/passive-pr-review.md",
    REPO_ROOT / "skills/github-pr-review/runbooks/active-pr-review.md",
)
TEMPLATES = (
    REPO_ROOT / "skills/local-code-review/templates/local-review-report.md",
    REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md",
)
CHECKPOINT = "Mandatory-loading checkpoint and pre-verdict recheck"


class CanonicalPolicyTests(unittest.TestCase):
    def test_checkpoint_section_has_both_points_and_adds_no_trigger(self) -> None:
        raw = STOPPING.read_text(encoding="utf-8")
        self.assertIn(f"## {CHECKPOINT}", raw)
        text = _text(STOPPING)
        self.assertIn("Before review execution", text)
        self.assertIn("Immediately before the Decision is derived", text)
        self.assertIn("never makes a required file optional", text)
        self.assertIn("every unconditional mandatory file", text)
        self.assertIn("with parallel workers", text)
        self.assertIn("orchestrated/ multi-Agent contexts", text)
        self.assertIn("never requires a context-conditional file whose predicate has not fired", text)
        self.assertIn("after any re-review, finding re-finalization, or change of the reviewed HEAD or delta", text)
        self.assertIn("every conditionally loaded file whose predicate fired", text)
        triggers = raw.split("## Incomplete triggers", 1)[1].split("## Mandatory-loading", 1)[0]
        self.assertEqual(len(re.findall(r"^\d\. \*\*", triggers, re.M)), 4)

    def test_three_outcomes_are_exclusive_and_hybrids_are_forbidden(self) -> None:
        text = _text(STOPPING)
        self.assertIn("ranked REVIEW INCOMPLETE > CHANGES REQUIRED > REVIEW CLEAN", text)
        self.assertIn("overrides a blocking finding, which is still reported in full", text)
        self.assertIn("REVIEW CLEAN requires complete coverage and no blocking (P0/P1) finding", text)
        self.assertIn("P0 = 0 and P1 = 0 alone never imply REVIEW CLEAN", text)
        self.assertIn("There is no hybrid rendering", text)
        self.assertIn("cannot excuse or replace the Result", text)


class EntrypointTests(unittest.TestCase):
    def test_entrypoints_name_all_outcomes_and_the_checkpoint(self) -> None:
        for path in SKILLS:
            text = _text(path)
            self.assertIn("P0 = 0 and P1 = 0 alone never imply", text, path)
            self.assertIn("REVIEW INCOMPLETE", text, path)
            self.assertIn(CHECKPOINT, text, path)
            self.assertIn("never a hybrid", text, path)
            self.assertIn("REVIEW INCOMPLETE", text, path)
            self.assertRegex(text, r"REVIEW INCOMPLETE[^.]*> CHANGES REQUIRED[^.]*> REVIEW CLEAN", path)
            self.assertIn("counts only when that context holds", text, path)
            self.assertIn("Before step 1 of the runbook", text, path)

    def test_entrypoints_no_longer_derive_clean_from_severity_alone(self) -> None:
        self.assertNotIn(
            "a Decision of `REVIEW CLEAN` or `CHANGES REQUIRED` derived mechanically",
            _text(SKILLS[0]),
        )


class RunbookTests(unittest.TestCase):
    def test_every_review_mode_has_the_checkpoint_and_the_recheck(self) -> None:
        for path in RUNBOOKS:
            text = _text(path)
            self.assertIn("Mandatory-loading checkpoint (runs before step 1)", text, path)
            self.assertIn("an unfired one is never required", text, path)
            self.assertIn("counts only when that context holds", text, path)
            self.assertIn("record an unloadable one as an incomplete trigger naming it", text, path)
            self.assertIn("also the pre-verdict recheck", text, path)
            self.assertIn("carry no earlier value forward", text, path)
            self.assertEqual(text.count(CHECKPOINT), 2, path)


class GithubRunbookOrderingTests(unittest.TestCase):
    def test_first_step_wording_defers_to_the_checkpoint(self) -> None:
        for path in RUNBOOKS[1:]:
            self.assertIn("Before any other step (after the checkpoint above)", _text(path), path)

    def test_active_review_recomputes_coverage_after_re_finalization(self) -> None:
        text = _text(RUNBOOKS[2])
        self.assertIn("then re-run step 11b over the new state", text)
        self.assertIn("is never reused", text)
        self.assertIn("Step 11b's coverage must be the one just recomputed", text)
        self.assertIn("no review, delta change, or re-finalization after it", text)


class StaleStatementAndReadmeTests(unittest.TestCase):
    def test_stopping_criteria_no_longer_says_local_lacks_the_outcome(self) -> None:
        text = _text(STOPPING)
        self.assertNotIn("does not yet have an equivalent labeled outcome", text)
        self.assertIn("whose report template renders the same REVIEW INCOMPLETE outcome", text)

    def test_local_readme_names_all_three_outcomes(self) -> None:
        text = _text(REPO_ROOT / "skills/local-code-review/README.md")
        self.assertIn("REVIEW CLEAN / CHANGES REQUIRED / REVIEW INCOMPLETE verdict", text)
        self.assertIn("Incomplete coverage always renders REVIEW INCOMPLETE instead", text)


class TemplateTests(unittest.TestCase):
    def test_templates_forbid_hybrid_success_renderings(self) -> None:
        for path in TEMPLATES:
            text = _text(path)
            self.assertIn("No hybrid", text, path)
            self.assertIn("coverage qualifier" if "external" in path.name else "coverage incomplete, see Metadata", text, path)


if __name__ == "__main__":
    unittest.main()
