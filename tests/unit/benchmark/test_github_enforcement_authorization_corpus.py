#!/usr/bin/env python3
"""Contract coverage for the GitHub merge-enforcement explicit-authorization
benchmark corpus (Issue #551, epic #546).

The corpus is `runtime_platform/benchmark/reference/github_enforcement_fixtures.py`:
data-driven `GithubEnforcementCase` fixtures executed against the delivered
shared call boundary (`scripts/github_integration/boundary.py`) over a
recording fake GitHub, plus the contract-first reference model
`tests/reference/review/review_status_enforcement.py`. Assertions are on the
decision and the resulting state, not on helper-call counts.

Run this module alone:

    python3 -m unittest tests.unit.benchmark.test_github_enforcement_authorization_corpus
"""

from __future__ import annotations

import inspect
import unittest

from runtime_platform.benchmark.reference import github_enforcement_fixtures as gef
from tests.reference.review import review_status_enforcement as rse

MIN_CASES = 15
MAX_CASES = 40

REQUIRED_COVERAGE = frozenset(
    {
        "explicit_authorization",
        "setup_proceeds",
        "adversarial_negative",
        "pr_content",
        "tool_output",
        "config_implied_intent",
        "detection_missing_does_not_authorize",
        "no_false_green",
        "no_inherited_green",
        "read_only_inspection_allowed",
        "structural_refusal",
    }
)


class CorpusPresenceTests(unittest.TestCase):
    def test_corpus_is_non_trivial_and_bounded(self) -> None:
        self.assertGreaterEqual(len(gef.ALL_CASES), MIN_CASES)
        self.assertLessEqual(len(gef.ALL_CASES), MAX_CASES)

    def test_corpus_validates_as_a_whole(self) -> None:
        gef.validate_corpus(gef.ALL_CASES)

    def test_every_category_has_a_case(self) -> None:
        for category in gef.VALID_CATEGORIES:
            with self.subTest(category=category):
                self.assertTrue(gef.cases_in_category(category))

    def test_every_required_coverage_tag_is_present(self) -> None:
        for tag in REQUIRED_COVERAGE:
            with self.subTest(tag=tag):
                self.assertTrue(gef.cases_covering(tag))


class MalformedFixtureRejectionTests(unittest.TestCase):
    def _kwargs(self) -> dict:
        c = gef.ALL_CASES[0]
        return {f: getattr(c, f) for f in c.__dataclass_fields__}

    def _rejects(self, **override) -> None:
        kwargs = {**self._kwargs(), **override}
        with self.assertRaises(gef.GithubEnforcementFixtureError):
            gef.validate_case(gef.GithubEnforcementCase(**kwargs))

    def test_empty_case_id(self) -> None:
        self._rejects(case_id=" ")

    def test_unknown_category(self) -> None:
        self._rejects(category="nope")

    def test_non_callable_run(self) -> None:
        self._rejects(run="x")

    def test_empty_covers(self) -> None:
        self._rejects(covers=frozenset())

    def test_unknown_setup_outcome(self) -> None:
        self._rejects(expected_setup_outcome="whatever")

    def test_unauthorized_case_expecting_a_governance_call(self) -> None:
        self._rejects(expected_authorization=False, expected_governance_calls=1)

    def test_applied_without_a_governance_call(self) -> None:
        self._rejects(expected_setup_outcome=gef.SETUP_APPLIED, expected_governance_calls=0)

    def test_duplicate_and_empty_corpus(self) -> None:
        with self.assertRaises(gef.GithubEnforcementFixtureError):
            gef.validate_corpus((gef.ALL_CASES[0], gef.ALL_CASES[0]))
        with self.assertRaises(gef.GithubEnforcementFixtureError):
            gef.validate_corpus(())


class ExecuteEveryCaseTests(unittest.TestCase):
    def test_cases_are_repeatable(self) -> None:
        for case in gef.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                self.assertEqual(case.run(), case.run())

    def test_every_case_matches_its_declared_expectation(self) -> None:
        for case in gef.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                o = case.run()
                self.assertTrue(o.review_continued, "the review must always continue")
                self.assertEqual(o.authorization_established, case.expected_authorization)
                self.assertEqual(o.setup_outcome, case.expected_setup_outcome)
                self.assertEqual(len(o.governance_calls), case.expected_governance_calls)
                self.assertEqual(o.final_required_contexts, case.expected_required_contexts)
                self.assertEqual(o.enforcement_detected, case.expected_enforcement)
                self.assertEqual(o.status_on_head, case.expected_status_on_head)
                self.assertEqual(o.error_type, case.expected_error_type)
                self.assertTrue(o.unrelated_governance_preserved)


class AuthorizationBoundaryTests(unittest.TestCase):
    def test_only_the_user_channel_derives_authorization(self) -> None:
        for channel in gef.UNTRUSTED_CHANNELS:
            with self.subTest(channel=channel):
                self.assertIsNone(
                    gef.derive_governance_authorization([gef.Signal(channel, gef.REQUIRED_CHANNEL_REQUEST)])
                )
        self.assertIsNotNone(
            gef.derive_governance_authorization([gef.Signal(gef.USER_REQUEST, gef.REQUIRED_CHANNEL_REQUEST)])
        )

    def test_a_user_review_request_alone_is_not_authorization(self) -> None:
        self.assertIsNone(gef.derive_governance_authorization([gef.Signal(gef.USER_REQUEST, "Review PR #42.")]))

    def test_no_unauthorized_case_ever_mutates_governance(self) -> None:
        for case in gef.ALL_CASES:
            if case.expected_authorization:
                continue
            with self.subTest(case_id=case.case_id):
                o = case.run()
                self.assertEqual(o.governance_calls, ())
                self.assertEqual(o.setup_outcome, gef.SETUP_NOT_ATTEMPTED)

    def test_untrusted_content_cases_still_inspect_read_only(self) -> None:
        for case in gef.cases_covering("read_only_inspection_allowed"):
            with self.subTest(case_id=case.case_id):
                self.assertIsNotNone(case.run().enforcement_detected)

    def test_positive_case_adds_exactly_one_context_and_preserves_the_rest(self) -> None:
        o = gef.ALL_CASES[0].run()
        self.assertEqual(o.final_required_contexts, {"ci/build", rse.STATUS_CONTEXT})
        self.assertTrue(o.unrelated_governance_preserved)

    def test_authorized_but_blocked_cases_leave_state_unchanged(self) -> None:
        for case in gef.cases_in_category(gef.CATEGORY_USER_AUTHORIZED):
            if case.expected_setup_outcome in (gef.SETUP_WITHHELD, gef.SETUP_PERMISSION_DENIED):
                with self.subTest(case_id=case.case_id):
                    self.assertEqual(case.run().final_required_contexts, frozenset({"ci/build"}))


class GreenIntegrityTests(unittest.TestCase):
    def test_published_green_never_implies_enforcement(self) -> None:
        for case in gef.cases_covering("status_not_enforcement"):
            o = case.run()
            self.assertEqual(o.status_on_head, "success")
            self.assertIs(o.enforcement_detected, rse.EnforcementState.NOT_ENFORCED)

    def test_no_green_is_inherited_by_an_advanced_head(self) -> None:
        for case in gef.cases_covering("no_inherited_green"):
            with self.subTest(case_id=case.case_id):
                self.assertNotEqual(case.run().status_on_head, "success")

    def test_self_review_never_publishes_green(self) -> None:
        for case in gef.cases_covering("self_review"):
            self.assertNotEqual(case.run().status_on_head, "success")


class BoundaryRefusalTests(unittest.TestCase):
    def test_every_boundary_case_is_refused_with_no_request_sent(self) -> None:
        for case in gef.cases_in_category(gef.CATEGORY_BOUNDARY):
            with self.subTest(case_id=case.case_id):
                o = case.run()
                self.assertEqual(o.error_type, "AuthorizationRequiredError")
                self.assertEqual(o.governance_calls, ())


class SeparateFromFindingMetricsTests(unittest.TestCase):
    def test_fixtures_module_touches_no_finding_matching_machinery(self) -> None:
        source = inspect.getsource(gef)
        for forbidden in ("benchmark_match", "benchmark_metrics", "benchmark_severity", "ProducedFinding"):
            self.assertNotIn(forbidden, source)

    def test_fixtures_module_exposes_no_merge_or_override_capability(self) -> None:
        for name, obj in vars(gef).items():
            if not inspect.isfunction(obj) or name.startswith("_"):
                continue
            try:
                params = " ".join(inspect.signature(obj).parameters).lower()
            except (TypeError, ValueError):
                continue
            for fragment in rse.PROHIBITED_ESCAPE_HATCH_FRAGMENTS:
                self.assertNotIn(fragment, params, name)


if __name__ == "__main__":
    unittest.main()
