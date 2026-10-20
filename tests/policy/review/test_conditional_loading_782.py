"""Entrypoint loading contract for #782.

Conditional policies are opened only when their predicate fires, each before
the first decision it governs and fail-closed, and knowingly unloaded required
material can never end in a clean or approving outcome. Prose assertions only.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _text

LOCAL = REPO_ROOT / "skills/local-code-review/SKILL.md"
GITHUB = REPO_ROOT / "skills/github-pr-review/SKILL.md"
STOPPING = REPO_ROOT / "shared/policies/review-stopping-criteria.md"
RUNBOOKS = (
    REPO_ROOT / "skills/local-code-review/runbooks/local-review.md",
    REPO_ROOT / "skills/github-pr-review/runbooks/passive-pr-review.md",
    REPO_ROOT / "skills/github-pr-review/runbooks/active-pr-review.md",
)

CONDITIONAL = {
    LOCAL: ("repository-expansion.md", "large-pr-partitioning.md", "invocation-options.md"),
    GITHUB: (
        "repository-expansion.md",
        "large-pr-partitioning.md",
        "requirement-coverage.md",
        "invocation-options.md",
    ),
}
# Policies whose passes run in every review stay in the unconditional set.
STILL_ALWAYS = (
    "review-scope.md",
    "change-risk-signals.md",
    "review-stopping-criteria.md",
    "severity.md",
    "evidence.md",
    "runtime-validation.md",
    "finding.md",
    "finding-rendering.md",
    "review-summary.md",
)


def _section(path, start: str, end: str) -> str:
    text = _text(path)
    begin = text.index(start)
    return text[begin : text.index(end, begin)]


def _always(path) -> str:
    start = "Always, as one batched operation:" if path == LOCAL else "Shared, always"
    return _section(path, start, "Conditionally")


def _conditional_by_evidence(path) -> str:
    return _section(path, "Conditionally, by review evidence", "Knowingly unloaded")


class ConditionalLoadingTests(unittest.TestCase):
    def test_conditional_files_leave_the_unconditional_list(self) -> None:
        for path, names in CONDITIONAL.items():
            always = _always(path)
            for name in names:
                self.assertNotIn(name, always, (path.name, name))

    def test_conditional_files_are_named_with_fail_closed_before_decision(self) -> None:
        for path, names in CONDITIONAL.items():
            block = _conditional_by_evidence(path)
            for name in names:
                self.assertIn(name, block, (path.name, name))
            self.assertIn("before the first decision it governs", block, path)
            self.assertIn("fail-closed", block, path)

    def test_review_wide_policies_stay_unconditional(self) -> None:
        for path in (LOCAL, GITHUB):
            always = _always(path)
            for name in STILL_ALWAYS:
                self.assertIn(name, always, (path.name, name))

    def test_local_review_context_loads_only_with_its_input(self) -> None:
        text = _text(LOCAL)
        self.assertNotIn("shared/policies/review-context.md`](../../shared/policies/review-context.md) (its", text)
        self.assertNotIn("review-context.md", _always(LOCAL))
        self.assertRegex(text, r"review context or a Jira/GitHub Issue reference; also loaded with a PR reference")


class KnownIncompleteLoadingTests(unittest.TestCase):
    def test_stopping_criteria_names_knowingly_unloaded_material(self) -> None:
        text = _text(STOPPING)
        self.assertIn("Knowingly unloaded required material is the same case", text)
        self.assertIn("a conditionally loaded file whose predicate fired included", text)
        self.assertIn("coverage is incomplete, never complete", text)
        self.assertIn("names the missing material", text)
        self.assertIn("gaps only: a self-reported load is not proof", text)

    def test_incomplete_trigger_set_stays_closed(self) -> None:
        text = STOPPING.read_text(encoding="utf-8")
        self.assertIn("## Incomplete triggers (closed set, evaluated per-pass)", text)
        triggers = re.findall(r"^\d\. \*\*", text, re.M)
        self.assertEqual(len(triggers), 4)
        self.assertIn(
            "trigger: required-pass-not-produced | partition-not-completed |", text
        )

    def test_entrypoints_route_to_the_canonical_trigger(self) -> None:
        for path, outcome in ((LOCAL, "never REVIEW CLEAN"), (GITHUB, "never an approving outcome")):
            text = _text(path)
            self.assertIn("Knowingly unloaded required material", text, path)
            self.assertIn("REVIEW INCOMPLETE", text, path)
            self.assertIn(outcome, text, path)
            self.assertIn("review-stopping-criteria.md", text, path)
            self.assertIn("Incomplete triggers", text, path)

    def test_runbooks_open_conditional_policies_fail_closed(self) -> None:
        for path in RUNBOOKS:
            text = _text(path)
            self.assertIn("fail-closed", text, path)
            self.assertIn("section 2", text, path)
            self.assertIn(
                "Required material from SKILL.md section 2 that was knowingly not loaded is an incomplete",
                text.replace("`", ""),
                path,
            )


if __name__ == "__main__":
    unittest.main()
