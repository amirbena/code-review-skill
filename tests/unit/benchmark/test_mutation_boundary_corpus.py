#!/usr/bin/env python3
"""Contract coverage for the mutation-capability-boundary benchmark corpus
(Issue #305, depends on #301).

The corpus is `tests/reference/benchmark/mutation_fixtures.py`: a focused,
data-driven set of `MutationCase` fixtures pinning every allowed/denied
outcome shape #305's scope requires, executed against the *single*
reference model `tests/reference/review/mutation_authority.py` (never a
second implementation of the gate) in a real, disposable temporary Git
repository per case. Each fixture's declared metadata (requested
capability, authorization scope/state, expected allow/deny result, linked
AUTH-### threat-scenario id, expected provisional denial classification,
expected repository/Git state after the case) is validated structurally
by `validate_case`/`validate_corpus`, then the fixture's own `run()` is
executed and its *actual* outcome is compared against that same declared
expectation -- every comparison here is a deterministic structural
assertion (allowed/denied, denial classification, repository/Git state
preserved or not, the exact paths an allowed apply touched), never an
LLM/rubric score, matching docs/benchmark/README.md's convention and
#307's precedent for this kind of capability-boundary corpus.

This is the "focused benchmark selection" surface for #305: run this
module alone (`python3 -m unittest
tests.unit.benchmark.test_mutation_boundary_corpus`) to exercise the whole
mutation-boundary corpus independently of the rest of the benchmark
suite, exactly like every other `test_*_corpus.py` module under this
directory (e.g. `test_delegation_spawn_corpus.py`).
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from tests.reference.benchmark import mutation_fixtures as mf

MIN_CASES = 20
MAX_CASES = 50


class CorpusPresenceTests(unittest.TestCase):
    def test_corpus_is_non_trivial_and_bounded(self) -> None:
        n = len(mf.ALL_CASES)
        self.assertGreaterEqual(n, MIN_CASES, "a required case went missing")
        self.assertLessEqual(n, MAX_CASES, "corpus is growing into a bulk library")

    def test_every_case_id_is_unique(self) -> None:
        ids = [c.case_id for c in mf.ALL_CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_corpus_validates_as_a_whole(self) -> None:
        mf.validate_corpus(mf.ALL_CASES)  # must not raise


class RequiredCategoryCoverageTests(unittest.TestCase):
    """#305's scope: fixtures must cover default read-only, repository-text
    non-authorization, proposal advisory-ness, apply authorization, stale
    approval, scope enforcement, capability independence, replay
    protection, child non-inheritance, and github-pr-review posture."""

    def test_every_category_has_at_least_one_case(self) -> None:
        for category in mf.VALID_CATEGORIES:
            with self.subTest(category=category):
                self.assertTrue(mf.cases_in_category(category), f"no case in category {category!r}")

    def test_every_category_has_both_an_allowed_and_a_denied_case(self) -> None:
        for category in mf.VALID_CATEGORIES:
            with self.subTest(category=category):
                results = {c.expected_result for c in mf.cases_in_category(category)}
                self.assertIn(mf.RESULT_DENIED, results, f"{category} has no denied case")
                self.assertIn(mf.RESULT_ALLOWED, results, f"{category} has no allowed (positive) case")


class RequiredThreatScenarioCoverageTests(unittest.TestCase):
    """Cases map to #300 threat scenarios: every AUTH-### scenario from the
    canonical catalog (docs/threat-model/catalog/mutation-authority.yaml),
    excluding AUTH-014, is covered by at least one case."""

    def test_every_required_threat_scenario_id_is_covered(self) -> None:
        covered: set[str] = set()
        for case in mf.ALL_CASES:
            covered.update(case.threat_scenario_ids)
        missing = mf.REQUIRED_THREAT_SCENARIO_IDS - covered
        self.assertFalse(missing, f"threat scenario id(s) with no covering fixture: {sorted(missing)}")

    def test_catalog_declares_exactly_the_auth_ids_this_corpus_expects(self) -> None:
        """Cross-check against the real catalog file rather than a second
        hand-maintained id list, so a catalog addition/removal is caught
        here too."""
        import yaml

        from tests.support.paths import REPO_ROOT

        catalog_path = REPO_ROOT / "docs" / "threat-model" / "catalog" / "mutation-authority.yaml"
        doc = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        catalog_ids = {sc["id"] for sc in doc["scenarios"]}
        expected_auth_ids = mf.REQUIRED_THREAT_SCENARIO_IDS | {"AUTH-014"}
        self.assertEqual(catalog_ids, expected_auth_ids)

    def test_no_case_cites_an_unknown_threat_scenario_id(self) -> None:
        for case in mf.ALL_CASES:
            for tid in case.threat_scenario_ids:
                with self.subTest(case=case.case_id, threat_id=tid):
                    self.assertIn(tid, mf.REQUIRED_THREAT_SCENARIO_IDS)

    def test_no_case_ever_cites_auth_014(self) -> None:
        """AUTH-014 is a distinct, already-covered GitHub formal
        review-action authority domain -- not this corpus's or #301/#305's
        code-mutation scope (see module docstring)."""
        for case in mf.ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertNotIn("AUTH-014", case.threat_scenario_ids)


class RequiredCoverageTagCompletenessTests(unittest.TestCase):
    def test_every_required_coverage_tag_has_a_case(self) -> None:
        covered: set[str] = set()
        for case in mf.ALL_CASES:
            covered.update(case.covers)
        missing = mf.REQUIRED_COVERAGE_TAGS - covered
        self.assertFalse(missing, f"coverage tag(s) with no case: {sorted(missing)}")

    def test_every_case_covers_at_least_one_required_tag(self) -> None:
        for case in mf.ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertTrue(case.covers & mf.REQUIRED_COVERAGE_TAGS, "case covers no required tag")


class StructuralOutcomeAssertionTests(unittest.TestCase):
    """The heart of the benchmark: run every case's real scenario, in a
    real disposable Git repository, against the single reference model and
    assert the actual outcome matches the fixture's own declared
    expectation -- never merely that the fixture parses."""

    def test_every_case_actual_outcome_matches_its_declared_expectation(self) -> None:
        for case in mf.ALL_CASES:
            with self.subTest(case=case.case_id):
                outcome = case.run()
                self.assertEqual(
                    outcome.allowed,
                    case.expected_result == mf.RESULT_ALLOWED,
                    f"{case.case_id}: allowed={outcome.allowed} but expected_result={case.expected_result}",
                )
                if case.expected_result == mf.RESULT_DENIED:
                    self.assertEqual(outcome.security_event, case.expected_security_event)
                    self.assertEqual(
                        outcome.repo_state_unchanged,
                        case.expected_repo_state_unchanged,
                        f"{case.case_id}: repo_state_unchanged={outcome.repo_state_unchanged} but "
                        f"expected {case.expected_repo_state_unchanged}",
                    )
                else:
                    self.assertIsNone(outcome.security_event)
                    self.assertEqual(outcome.repo_state_unchanged, case.expected_repo_state_unchanged)
                    if case.expected_authorized_scope is not None:
                        self.assertEqual(outcome.applied_paths, case.expected_authorized_scope)

    def test_every_denied_case_declares_a_recognized_denial_classification(self) -> None:
        for case in mf.cases_where(lambda c: c.expected_result == mf.RESULT_DENIED):
            with self.subTest(case=case.case_id):
                self.assertIn(case.expected_security_event, mf.VALID_DENIAL_CLASSIFICATIONS)

    def test_almost_every_denied_case_declares_repo_state_preserved(self) -> None:
        """A structural proof, over the whole corpus, that denial precedes
        any write in nearly every case. Exactly one documented exception is
        permitted: a scope-escape violation detected only *after*
        `git apply` has already written to the working tree (AUTH-009/016)
        -- everywhere else, denial must be declared to precede any write."""
        denied = mf.cases_where(lambda c: c.expected_result == mf.RESULT_DENIED)
        not_preserved = [c.case_id for c in denied if not c.expected_repo_state_unchanged]
        self.assertEqual(
            not_preserved,
            ["out-of-scope-file-mutation-denied"],
            "only the documented post-apply scope-escape case may declare repo state changed",
        )


class DeniedCasesLeaveStateUnchangedTests(unittest.TestCase):
    """#305's own validation requirement, run directly: every denied case
    that declares expected_repo_state_unchanged=True actually leaves
    repository/Git state unchanged (working tree, refs, HEAD). The single
    documented exception (a scope-escape violation only detectable after
    `git apply` already wrote to disk) is checked separately below: its
    ref/HEAD state -- the actual Git-level repository state, as opposed to
    an uncommitted working-tree scratch write -- must still never move."""

    def test_every_ordinary_denied_case_actually_preserves_repo_state(self) -> None:
        for case in mf.cases_where(
            lambda c: c.expected_result == mf.RESULT_DENIED and c.expected_repo_state_unchanged
        ):
            with self.subTest(case=case.case_id):
                outcome = case.run()
                self.assertTrue(
                    outcome.repo_state_unchanged,
                    f"{case.case_id}: a denied case must leave repository/Git state unchanged",
                )

    def test_documented_exception_still_never_advances_refs_or_head(self) -> None:
        case = mf.OUT_OF_SCOPE_FILE_DENIED
        outcome = case.run()
        self.assertFalse(outcome.allowed)
        self.assertFalse(
            outcome.repo_state_unchanged,
            "this case's working tree is genuinely left with git apply's raw write",
        )
        self.assertEqual(outcome.security_event, mf.DENIED_MUTATION_SCOPE_ESCAPE)


class AllowedApplyChangesOnlyAuthorizedScopeTests(unittest.TestCase):
    """#305's own validation requirement, run directly: the allowed apply
    case(s) modify only the exact authorized scope."""

    def test_every_allowed_case_with_a_declared_scope_touches_exactly_that_scope(self) -> None:
        cases = mf.cases_where(
            lambda c: c.expected_result == mf.RESULT_ALLOWED and c.expected_authorized_scope is not None
        )
        self.assertTrue(cases, "at least one allowed case must declare an authorized scope")
        for case in cases:
            with self.subTest(case=case.case_id):
                outcome = case.run()
                self.assertEqual(outcome.applied_paths, case.expected_authorized_scope)


# ---------------------------------------------------------------------------
# Malformed-fixture rejection -- the corpus validator itself, exercised
# against deliberately broken fixtures it must reject.
# ---------------------------------------------------------------------------


def _valid_denied_template() -> mf.MutationCase:
    return mf.READ_ONLY_CANNOT_BE_AUTHORIZED_DENIED


def _valid_allowed_template() -> mf.MutationCase:
    return mf.PROPOSE_PATCH_IMPLICIT_CAPABILITY_ALLOWED


class MalformedFixtureRejectionTests(unittest.TestCase):
    def test_rejects_unknown_category(self) -> None:
        bad = replace(_valid_denied_template(), category="not_a_real_category")
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_empty_case_id(self) -> None:
        bad = replace(_valid_denied_template(), case_id="")
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_empty_requested_capability(self) -> None:
        bad = replace(_valid_denied_template(), requested_capability="")
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_empty_authorization_state(self) -> None:
        bad = replace(_valid_denied_template(), authorization_state="")
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_invalid_expected_result_token(self) -> None:
        bad = replace(_valid_denied_template(), expected_result="maybe")
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_denied_case_with_no_denial_classification(self) -> None:
        bad = replace(_valid_denied_template(), expected_security_event=None)
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_denied_case_with_unrecognized_denial_classification(self) -> None:
        bad = replace(_valid_denied_template(), expected_security_event="DENIED_SOMETHING_MADE_UP")
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_denied_case_with_non_bool_repo_state_expectation(self) -> None:
        bad = replace(_valid_denied_template(), expected_repo_state_unchanged=None)
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)
        bad2 = replace(_valid_denied_template(), expected_repo_state_unchanged="yes")  # type: ignore[arg-type]
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad2)

    def test_rejects_denied_case_that_also_declares_an_authorized_scope(self) -> None:
        bad = replace(_valid_denied_template(), expected_authorized_scope=frozenset({"x"}))
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_allowed_case_that_still_carries_a_denial_classification(self) -> None:
        bad = replace(_valid_allowed_template(), expected_security_event=mf.DENIED_MUTATION_UNAUTHORIZED)
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_allowed_case_missing_repo_state_expectation(self) -> None:
        bad = replace(_valid_allowed_template(), expected_repo_state_unchanged=None)
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_malformed_threat_scenario_id(self) -> None:
        bad = replace(_valid_denied_template(), threat_scenario_ids=("not-an-id",))
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_threat_scenario_id_with_wrong_digit_count(self) -> None:
        bad = replace(_valid_denied_template(), threat_scenario_ids=("AUTH-1",))
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_auth_014_as_a_threat_scenario_id(self) -> None:
        bad = replace(_valid_denied_template(), threat_scenario_ids=("AUTH-014",))
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_rejects_non_callable_run(self) -> None:
        bad = replace(_valid_denied_template(), run="not-callable")  # type: ignore[arg-type]
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_case(bad)

    def test_corpus_validation_rejects_duplicate_case_ids(self) -> None:
        dup = replace(_valid_allowed_template(), case_id=_valid_denied_template().case_id)
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_corpus((_valid_denied_template(), dup))

    def test_corpus_validation_rejects_empty_corpus(self) -> None:
        with self.assertRaises(mf.MutationFixtureError):
            mf.validate_corpus(())

    def test_a_genuinely_valid_denied_case_still_passes(self) -> None:
        # Negative-canary guard: the template itself must not be broken, or
        # every rejection test above would be vacuous.
        mf.validate_case(_valid_denied_template())

    def test_a_genuinely_valid_allowed_case_still_passes(self) -> None:
        mf.validate_case(_valid_allowed_template())


class SelectionHelperTests(unittest.TestCase):
    """The in-module equivalent of this repository's focused-selection
    convention: a case can be found by category, by covered requirement
    tag, or by threat-scenario id, so future tooling (#310) can slice the
    corpus without re-deriving it."""

    def test_cases_in_category_returns_only_that_category(self) -> None:
        for category in mf.VALID_CATEGORIES:
            for case in mf.cases_in_category(category):
                self.assertEqual(case.category, category)

    def test_cases_covering_returns_only_cases_with_that_tag(self) -> None:
        tag = next(iter(mf.REQUIRED_COVERAGE_TAGS))
        for case in mf.cases_covering(tag):
            self.assertIn(tag, case.covers)

    def test_cases_for_threat_scenario_returns_only_matching_cases(self) -> None:
        for case in mf.cases_for_threat_scenario("AUTH-005"):
            self.assertIn("AUTH-005", case.threat_scenario_ids)
        self.assertTrue(mf.cases_for_threat_scenario("AUTH-005"))


if __name__ == "__main__":
    unittest.main()
