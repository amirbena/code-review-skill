"""Entrypoint loading contract for #782 and the coverage invariant of #808.

Conditional policies are opened only when their predicate fires, each before
the first decision it governs and fail-closed; required material that is not
loaded in time can never end in a clean or approving outcome; and the
always-emitted repository-expansion metadata survives not opening its policy.
Prose assertions only; policy membership is matched on exact link targets.
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
    "finding.md",
    "finding-rendering.md",
    "review-summary.md",
)
NONE_FIELD = {LOCAL: "Repository expansion: metadata line", GITHUB: "repository_expansion_triggers metadata field"}

_SHARED_LINK = re.compile(r"\]\((?:\.\./)+shared/(?:policies|templates)/([\w-]+\.md)\)")


def _raw_section(path, start: str, end: str) -> str:
    raw = path.read_text(encoding="utf-8")
    begin = raw.index(start)
    return raw[begin : raw.index(end, begin)]


def _linked(path, start: str, end: str) -> set[str]:
    """Exact shared-file names linked inside one section (never substrings)."""
    return set(_SHARED_LINK.findall(_raw_section(path, start, end)))


def _always(path) -> set[str]:
    start = "Always, in bounded resumable groups:" if path == LOCAL else "Shared, always"
    return _linked(path, start, "Conditionally")


def _conditional_block(path) -> str:
    return _raw_section(path, "Conditionally, by review evidence", "Conditionally, by the review")


class ConditionalLoadingTests(unittest.TestCase):
    def test_conditional_files_leave_the_unconditional_list(self) -> None:
        for path, names in CONDITIONAL.items():
            always = _always(path)
            for name in names:
                self.assertNotIn(name, always, (path.name, name))

    def test_conditional_files_are_linked_with_fail_closed_before_decision(self) -> None:
        for path, names in CONDITIONAL.items():
            block = _conditional_block(path)
            linked = set(_SHARED_LINK.findall(block))
            for name in names:
                self.assertIn(name, linked, (path.name, name))
            flat = re.sub(r"\s+", " ", block)
            self.assertIn("before the first decision it governs", flat, path)
            self.assertIn("fail-closed", flat, path)

    def test_review_wide_policies_stay_unconditional(self) -> None:
        for path in (LOCAL, GITHUB):
            always = _always(path)
            for name in STILL_ALWAYS:
                self.assertIn(name, always, (path.name, name))

    def test_local_review_context_loads_only_with_its_input(self) -> None:
        self.assertNotIn("review-context.md", _always(LOCAL))
        own_input = _linked(LOCAL, "Conditionally, only when its own input", "Conditionally, by review evidence")
        self.assertIn("review-context.md", own_input)


class ExpansionNoneStaysEmittedTests(unittest.TestCase):
    """Not opening repository-expansion.md must not drop its always-on `none`."""

    def test_entrypoints_keep_the_none_clause(self) -> None:
        for path, field in NONE_FIELD.items():
            flat = re.sub(r"\s+", " ", _conditional_block(path).replace("`", ""))
            self.assertIn(f"the {field} still reads none when nothing fires", flat, path)
            self.assertIn("without opening either file", flat, path)

    def test_runbooks_record_none_without_opening_the_policy(self) -> None:
        for path in RUNBOOKS:
            flat = _text(path)
            self.assertRegex(flat, r"none\"? (?:when nothing fired, )?(?:recorded )?without opening the policy", path)


class IncompleteLoadingTests(unittest.TestCase):
    def test_trigger_one_distinguishes_timely_late_and_missing_loads(self) -> None:
        text = _text(STOPPING)
        self.assertIn("must be loaded before the first decision it governs", text)
        self.assertIn("Loaded before that decision, it is the ordinary case", text)
        self.assertIn("Loaded only after that decision, or still unloaded when coverage is evaluated", text)
        self.assertIn("coverage is incomplete, never complete", text)
        self.assertIn("names the material", text)
        self.assertIn("re-made after loading, which counts as loaded before it", text)
        self.assertIn("gaps only: a self-reported load is not proof", text)

    def test_incomplete_trigger_set_stays_closed(self) -> None:
        text = STOPPING.read_text(encoding="utf-8")
        self.assertIn("## Incomplete triggers (closed set, evaluated per-pass)", text)
        self.assertEqual(len(re.findall(r"^\d\. \*\*", text, re.M)), 4)
        self.assertIn("trigger: required-pass-not-produced | partition-not-completed |", text)

    def test_entrypoints_route_incomplete_loading_to_the_canonical_owner(self) -> None:
        for path in (LOCAL, GITHUB):
            text = _text(path)
            self.assertIn("REVIEW INCOMPLETE, never a definitive verdict", text, path)
            self.assertIn('"Coverage invariant" and "Labeling."', text, path)
            self.assertNotIn("was loaded only after the decision it governs", text, path)

    def test_runbooks_open_conditional_policies_fail_closed(self) -> None:
        for path in RUNBOOKS:
            text = _text(path)
            self.assertIn("fail-closed", text, path)
            self.assertIn("section 2", text, path)
            self.assertIn(
                "Required material from SKILL.md section 2 that was not loaded before the decision it governs is an incomplete",
                text,
                path,
            )


class CoverageInvariantTests(unittest.TestCase):
    """#808: one canonical invariant, restated as a pointer only."""

    def test_policy_owns_the_invariant_for_both_definitive_verdicts(self) -> None:
        text = _text(STOPPING)
        self.assertIn("Coverage invariant. Neither definitive verdict (REVIEW CLEAN, CHANGES REQUIRED)", text)
        self.assertIn("Coverage is derived from the files actually opened, never from memory", text)
        self.assertIn("A missing Coverage field, or a report that states unloaded required policies", text)
        self.assertIn("a definitive verdict never coexists with such a statement", text)
        self.assertIn("an obligation on the reviewer, not a technical guarantee", text)

    def test_policy_counts_an_unprovable_read_as_not_loaded(self) -> None:
        text = _text(STOPPING)
        self.assertIn("A file counts as loaded only when its complete content was read", text)
        self.assertIn("a read the reviewer cannot show to have been complete counts as not loaded", text)

    def test_entrypoints_state_the_invariant_without_claiming_enforcement(self) -> None:
        for path in (LOCAL, GITHUB):
            text = _text(path)
            self.assertIn('"Coverage invariant" and "Labeling."', text, path)
            self.assertIn("review-stopping-criteria.md", text, path)
            self.assertNotIn("Coverage invariant (mandatory)", text, path)
            self.assertNotIn("is valid unless every required policy was loaded in full", text, path)

    def test_safety_bullets_cover_both_verdicts(self) -> None:
        self.assertIn("either verdict additionally requires complete coverage", _text(LOCAL))
        self.assertIn("Either verdict also requires complete coverage", _text(GITHUB))
        for path in (LOCAL, GITHUB):
            self.assertNotIn("REVIEW CLEAN additionally requires complete coverage", _text(path), path)

    def test_runbooks_point_at_the_invariant_instead_of_restating_it(self) -> None:
        fields = {RUNBOOKS[0]: "Coverage: line", RUNBOOKS[1]: "metadata block's coverage field", RUNBOOKS[2]: "metadata block's coverage field"}
        for path in RUNBOOKS:
            text = _text(path)
            self.assertIn(f"Set the Coverage field (the {fields[path]}) from the files actually opened, never from memory", text, path)
            self.assertIn('(../../../shared/policies/review-stopping-criteria.md), "Labeling") to the rendered report', text, path)
            self.assertNotIn("states unloaded required policies", text, path)

    def test_conditional_set_and_ranking_are_untouched(self) -> None:
        text = _text(STOPPING)
        self.assertIn("ranked REVIEW INCOMPLETE > CHANGES REQUIRED > REVIEW CLEAN", text)
        for path, names in CONDITIONAL.items():
            always = _always(path)
            for name in names:
                self.assertNotIn(name, always, path)


if __name__ == "__main__":
    unittest.main()
