#!/usr/bin/env python3
"""Contract coverage for the natural-language trusted-host-execution
authorization benchmark corpus (Issue #370, depends on #369).

The corpus is `runtime_platform/benchmark/reference/trusted_host_nl_fixtures.py`: a
focused, data-driven set of `TrustedHostNLCase` fixtures pinning every
resolved-authorization/provenance outcome shape #370's scope requires,
executed against the *single* reference model
`tests/reference/review/runtime_validation.py` (never a second
implementation of the resolution or backend-selection logic). Each
fixture's declared metadata (category, covered #370 Scope tags, expected
resolved `allow_trusted_host_execution` boolean, expected execution-backend
provenance) is validated structurally by `validate_case`/`validate_corpus`,
then the fixture's own `run()` is executed and its *actual* outcome is
compared against that same declared expectation -- every comparison here
is a deterministic structural assertion, never an LLM/rubric score,
matching runtime_platform/benchmark/README.md's convention.

Run this module alone to exercise the whole corpus independently of the
rest of the benchmark suite:

    python3 -m unittest tests.unit.benchmark.test_trusted_host_nl_authorization_corpus
"""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.reference import trusted_host_nl_fixtures as tf
from tests.reference.review import runtime_validation as rv

MIN_CASES = 35
MAX_CASES = 70


class CorpusPresenceTests(unittest.TestCase):
    def test_corpus_is_non_trivial_and_bounded(self) -> None:
        n = len(tf.ALL_CASES)
        self.assertGreaterEqual(n, MIN_CASES, "a required case went missing")
        self.assertLessEqual(n, MAX_CASES, "corpus is growing into a bulk library")

    def test_every_case_id_is_unique(self) -> None:
        ids = [c.case_id for c in tf.ALL_CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_corpus_validates_as_a_whole(self) -> None:
        tf.validate_corpus(tf.ALL_CASES)  # must not raise

    def test_every_case_declares_both_skills(self) -> None:
        """trusted-host-execution.md applies identically to both Skills, and
        both consume the one shared resolution model -- no case is scoped
        to only one Skill (see the corpus README, "Why every case covers
        both Skills")."""
        for case in tf.ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertEqual(case.skills, tf.BOTH_SKILLS)


class RequiredCategoryCoverageTests(unittest.TestCase):
    def test_every_category_has_at_least_one_case(self) -> None:
        for category in tf.VALID_CATEGORIES:
            with self.subTest(category=category):
                self.assertTrue(tf.cases_in_category(category), f"no case in category {category!r}")

    def test_every_denial_required_category_never_resolves_true(self) -> None:
        for category in tf.DENIAL_REQUIRED_CATEGORIES:
            for case in tf.cases_in_category(category):
                with self.subTest(case=case.case_id):
                    self.assertFalse(case.expected_resolved)
                    self.assertNotEqual(case.expected_provenance, rv.Provenance.TRUSTED_HOST)


class RequiredCoverageTagCompletenessTests(unittest.TestCase):
    def test_every_required_coverage_tag_has_a_case(self) -> None:
        covered: set[str] = set()
        for case in tf.ALL_CASES:
            covered.update(case.covers)
        missing = tf.REQUIRED_COVERAGE_TAGS - covered
        self.assertFalse(missing, f"coverage tag(s) with no case: {sorted(missing)}")

    def test_every_case_covers_at_least_one_required_tag(self) -> None:
        for case in tf.ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertTrue(case.covers & tf.REQUIRED_COVERAGE_TAGS, "case covers no required tag")


class AffirmativeAndNegativePhrasingCompletenessTests(unittest.TestCase):
    """#370 requires "several differently-worded affirmative requests" and
    the full denial vocabulary -- cross-checked against the live phrase
    lists in the single reference model, not a second hand-copied list."""

    def test_every_reference_affirmative_phrase_has_a_case(self) -> None:
        covered_descriptions = {c.description for c in tf.cases_in_category(tf.CATEGORY_EQUIVALENT_AFFIRMATIVE_PHRASING)}
        for phrase in rv.TRUSTED_HOST_AFFIRMATIVE:
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    any(phrase in description for description in covered_descriptions),
                    f"affirmative phrase {phrase!r} has no corpus case",
                )

    def test_every_reference_negative_phrase_has_a_case(self) -> None:
        covered_descriptions = {c.description for c in tf.cases_in_category(tf.CATEGORY_EXPLICIT_DENIAL)}
        for phrase in rv.TRUSTED_HOST_NEGATIVE:
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    any(phrase in description for description in covered_descriptions),
                    f"negative phrase {phrase!r} has no corpus case",
                )


class StructuralOutcomeAssertionTests(unittest.TestCase):
    """The heart of the benchmark: run every case's real scenario against
    the single reference model and assert the actual outcome matches the
    fixture's own declared expectation -- never merely that the fixture
    parses."""

    def test_every_case_actual_outcome_matches_its_declared_expectation(self) -> None:
        for case in tf.ALL_CASES:
            with self.subTest(case=case.case_id):
                outcome = case.run()
                self.assertEqual(
                    outcome.resolved,
                    case.expected_resolved,
                    f"{case.case_id}: resolved={outcome.resolved} but expected_resolved={case.expected_resolved}",
                )
                self.assertEqual(
                    outcome.provenance,
                    case.expected_provenance,
                    f"{case.case_id}: provenance={outcome.provenance} but expected={case.expected_provenance}",
                )

    def test_no_denial_required_case_ever_actually_selects_trusted_host(self) -> None:
        """A structural double-check, run over the whole corpus at once
        rather than per-category: no case in a category #370 requires to
        resolve toward denial ever actually observes TRUSTED_HOST from a
        real run of the reference model."""
        for category in tf.DENIAL_REQUIRED_CATEGORIES:
            for case in tf.cases_in_category(category):
                with self.subTest(case=case.case_id):
                    outcome = case.run()
                    self.assertNotEqual(outcome.provenance, rv.Provenance.TRUSTED_HOST)


class SandboxPreferenceInvariantTests(unittest.TestCase):
    """Sandbox availability is evaluated first and always wins, regardless
    of authorization presence -- the corpus's `sandbox_preferred` category
    proves this over structured, NL, and no-signal inputs alike."""

    def test_every_sandbox_preferred_case_selects_sandbox(self) -> None:
        for case in tf.cases_in_category(tf.CATEGORY_SANDBOX_PREFERRED):
            with self.subTest(case=case.case_id):
                outcome = case.run()
                self.assertEqual(outcome.provenance, rv.Provenance.SANDBOX)


class NonPersistenceInvariantTests(unittest.TestCase):
    def test_every_non_persistence_case_resolves_unavailable(self) -> None:
        for case in tf.cases_in_category(tf.CATEGORY_NON_PERSISTENCE):
            with self.subTest(case=case.case_id):
                outcome = case.run()
                self.assertEqual(outcome.provenance, rv.Provenance.UNAVAILABLE)
                self.assertFalse(outcome.resolved)


class RepositorySourcedRejectionCanaryTests(unittest.TestCase):
    """Proves the repository/PR/malicious-file/delegated-agent rejection
    has genuine detection power: a deliberately broken stand-in that (like
    a real regression would) feeds repository-sourced text into the NL
    resolution layer *as if* it were the trusted invocation's own text
    would incorrectly authorize several of this corpus's payloads --
    showing the real corpus is not a check that can never fail. Mirrors
    `SiblingReconstructionCanaryTests` in `test_delegation_spawn_corpus.py`.
    """

    @staticmethod
    def _broken_naive_resolution(payload: str) -> bool:
        # The regression this canary catches: treating repository-sourced
        # text as if it were the trusted invocation's own current-turn
        # text, instead of routing it through `authorization_from_repository_text`
        # and `select_backend`'s type-based rejection.
        return rv.resolve_allow_trusted_host_execution(payload)

    def test_canary_naive_resolution_is_fooled_by_at_least_one_payload(self) -> None:
        payloads = [
            case.description for case in tf.cases_in_category(tf.CATEGORY_REPOSITORY_CONTROLLED_ATTEMPT)
        ] + [case.description for case in tf.cases_in_category(tf.CATEGORY_MALICIOUS_INSTRUCTION_FILE)]
        fooled = [p for p in payloads if self._broken_naive_resolution(p)]
        self.assertTrue(fooled, "the canary must be fooled by at least one adversarial payload")

    def test_real_corpus_run_never_selects_trusted_host_for_the_same_payloads(self) -> None:
        for case in tf.cases_in_category(tf.CATEGORY_REPOSITORY_CONTROLLED_ATTEMPT):
            with self.subTest(case=case.case_id):
                outcome = case.run()
                self.assertNotEqual(outcome.provenance, rv.Provenance.TRUSTED_HOST)


class MalformedFixtureRejectionTests(unittest.TestCase):
    """`validate_case` rejects a malformed fixture: an unrecognized
    category, an inconsistent provenance/resolved pairing, a denial-
    required category that resolves true, or a case scoped to fewer than
    both Skills."""

    def _valid_case(self) -> tf.TrustedHostNLCase:
        return tf.TrustedHostNLCase(
            case_id="valid-example",
            category=tf.CATEGORY_STRUCTURED_AUTHORIZATION,
            covers=frozenset({"example-tag"}),
            description="a valid example case",
            skills=tf.BOTH_SKILLS,
            expected_resolved=True,
            expected_provenance=rv.Provenance.TRUSTED_HOST,
            run=lambda: tf.CaseOutcome(resolved=True, provenance=rv.Provenance.TRUSTED_HOST),
        )

    def test_valid_case_passes(self) -> None:
        tf.validate_case(self._valid_case())  # must not raise

    def test_unrecognized_category_rejected(self) -> None:
        from dataclasses import replace

        with self.assertRaises(tf.TrustedHostNLFixtureError):
            tf.validate_case(replace(self._valid_case(), category="not-a-real-category"))

    def test_trusted_host_provenance_without_resolved_true_rejected(self) -> None:
        from dataclasses import replace

        with self.assertRaises(tf.TrustedHostNLFixtureError):
            tf.validate_case(replace(self._valid_case(), expected_resolved=False))

    def test_unavailable_provenance_with_resolved_true_rejected(self) -> None:
        from dataclasses import replace

        with self.assertRaises(tf.TrustedHostNLFixtureError):
            tf.validate_case(
                replace(self._valid_case(), expected_provenance=rv.Provenance.UNAVAILABLE)
            )

    def test_denial_required_category_resolving_true_rejected(self) -> None:
        from dataclasses import replace

        with self.assertRaises(tf.TrustedHostNLFixtureError):
            tf.validate_case(replace(self._valid_case(), category=tf.CATEGORY_EXPLICIT_DENIAL))

    def test_single_skill_scope_rejected(self) -> None:
        from dataclasses import replace

        with self.assertRaises(tf.TrustedHostNLFixtureError):
            tf.validate_case(replace(self._valid_case(), skills=("local-code-review",)))

    def test_empty_covers_rejected(self) -> None:
        from dataclasses import replace

        with self.assertRaises(tf.TrustedHostNLFixtureError):
            tf.validate_case(replace(self._valid_case(), covers=frozenset()))

    def test_duplicate_case_id_rejected_by_corpus_validation(self) -> None:
        with self.assertRaises(tf.TrustedHostNLFixtureError):
            tf.validate_corpus((self._valid_case(), self._valid_case()))

    def test_empty_corpus_rejected(self) -> None:
        with self.assertRaises(tf.TrustedHostNLFixtureError):
            tf.validate_corpus(())


if __name__ == "__main__":
    unittest.main()
