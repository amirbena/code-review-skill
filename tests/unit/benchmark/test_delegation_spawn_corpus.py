#!/usr/bin/env python3
"""Contract coverage for the agent-spawn / delegated-authority benchmark
corpus (Issue #307, depends on #303).

The corpus is `tests/reference/benchmark/delegation_fixtures.py`: a
focused, data-driven set of `DelegationCase` fixtures pinning every
allowed/denied outcome shape #307's scope requires, executed against the
*single* reference model `tests/reference/review/agent_delegation.py`
(never a second implementation of the gate). Each fixture's declared
metadata (parent/delegated/requested capability sets, spawn depth,
invocation agent-count budget, expected allow/deny result, linked
DELEG-###/DOS-### threat-scenario id, expected provisional denial
classification) is validated structurally by `validate_case`/
`validate_corpus`, then the fixture's own `run()` is executed and its
*actual* outcome is compared against that same declared expectation --
every comparison here is a deterministic structural assertion (allowed/
denied, effective granted capabilities, security-event classification),
never an LLM/rubric score, matching docs/benchmark/README.md's convention
and this domain's own "Evaluation style" requirement.

This is the "focused benchmark selection" surface for #307: run this
module alone (`python3 -m unittest
tests.unit.benchmark.test_delegation_spawn_corpus`) to exercise the whole
delegation/spawn corpus independently of the rest of the benchmark suite,
exactly like every other `test_*_corpus.py` module under this directory
(e.g. `test_security_deepening_corpus.py`).
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from tests.reference.benchmark import delegation_fixtures as df
from tests.reference.review import agent_delegation as ad

MIN_CASES = 20
MAX_CASES = 60


class CorpusPresenceTests(unittest.TestCase):
    def test_corpus_is_non_trivial_and_bounded(self) -> None:
        n = len(df.ALL_CASES)
        self.assertGreaterEqual(n, MIN_CASES, "a required case went missing")
        self.assertLessEqual(n, MAX_CASES, "corpus is growing into a bulk library")

    def test_every_case_id_is_unique(self) -> None:
        ids = [c.case_id for c in df.ALL_CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_corpus_validates_as_a_whole(self) -> None:
        df.validate_corpus(df.ALL_CASES)  # must not raise


class RequiredCategoryCoverageTests(unittest.TestCase):
    """#307's scope: fixtures must cover count, depth, capability-subset,
    authorization-transfer, and confused-deputy boundaries, plus the
    read-only-worker and budget-exhaustion requirements."""

    def test_every_category_has_at_least_one_case(self) -> None:
        for category in df.VALID_CATEGORIES:
            with self.subTest(category=category):
                self.assertTrue(df.cases_in_category(category), f"no case in category {category!r}")

    # sibling_reconstruction is exempt: the reference model
    # (`capabilities_from_shared_state`) combines sibling grants by
    # intersection only and simply has no code path that ever produces an
    # escalation to deny -- every real case in this category is,
    # correctly, `allowed` (no escalation occurred). Its detective power
    # over a real regression (a combinator that started unioning) is
    # proven instead by `SiblingReconstructionCanaryTests` below, mirroring
    # `out_of_scope_terms_present()`'s negative-canary pattern in
    # reviewer_brief_fixtures.py rather than forcing an artificial
    # `denied` case that does not reflect real system behavior.
    _CATEGORIES_EXEMPT_FROM_BOTH_OUTCOMES = frozenset({df.CATEGORY_SIBLING_RECONSTRUCTION})

    def test_every_category_has_both_an_allowed_and_a_denied_case(self) -> None:
        # Confused-deputy is otherwise almost entirely negative by nature,
        # but it too carries the positive "independent trusted channel"
        # counterpart -- checked here like every other non-exempt category.
        for category in df.VALID_CATEGORIES - self._CATEGORIES_EXEMPT_FROM_BOTH_OUTCOMES:
            with self.subTest(category=category):
                results = {c.expected_result for c in df.cases_in_category(category)}
                self.assertIn(df.RESULT_DENIED, results, f"{category} has no denied case")
                self.assertIn(df.RESULT_ALLOWED, results, f"{category} has no allowed (positive) case")


class RequiredThreatScenarioCoverageTests(unittest.TestCase):
    """Cases map to #300 threat scenarios: every DELEG-### scenario from
    the canonical catalog (docs/threat-model/catalog/spawn-delegation.yaml)
    and the two delegation-tagged DOS-### scenarios are covered by at
    least one case."""

    def test_every_required_threat_scenario_id_is_covered(self) -> None:
        covered: set[str] = set()
        for case in df.ALL_CASES:
            covered.update(case.threat_scenario_ids)
        missing = df.REQUIRED_THREAT_SCENARIO_IDS - covered
        self.assertFalse(missing, f"threat scenario id(s) with no covering fixture: {sorted(missing)}")

    def test_catalog_declares_exactly_the_deleg_ids_this_corpus_expects(self) -> None:
        """Cross-check against the real catalog file rather than a second
        hand-maintained id list, so a catalog addition/removal is caught
        here too."""
        import yaml

        from tests.support.paths import REPO_ROOT

        catalog_path = REPO_ROOT / "docs" / "threat-model" / "catalog" / "spawn-delegation.yaml"
        doc = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        catalog_ids = {sc["id"] for sc in doc["scenarios"]}
        expected_deleg_ids = {tid for tid in df.REQUIRED_THREAT_SCENARIO_IDS if tid.startswith("DELEG-")}
        self.assertEqual(catalog_ids, expected_deleg_ids)

    def test_no_case_cites_an_unknown_threat_scenario_id(self) -> None:
        for case in df.ALL_CASES:
            for tid in case.threat_scenario_ids:
                with self.subTest(case=case.case_id, threat_id=tid):
                    self.assertIn(tid, df.REQUIRED_THREAT_SCENARIO_IDS)


class RequiredCoverageTagCompletenessTests(unittest.TestCase):
    def test_every_required_coverage_tag_has_a_case(self) -> None:
        covered: set[str] = set()
        for case in df.ALL_CASES:
            covered.update(case.covers)
        missing = df.REQUIRED_COVERAGE_TAGS - covered
        self.assertFalse(missing, f"coverage tag(s) with no case: {sorted(missing)}")

    def test_every_case_covers_at_least_one_required_tag(self) -> None:
        for case in df.ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertTrue(case.covers & df.REQUIRED_COVERAGE_TAGS, "case covers no required tag")


class StructuralOutcomeAssertionTests(unittest.TestCase):
    """The heart of the benchmark: run every case's real scenario against
    the single reference model and assert the actual outcome matches the
    fixture's own declared expectation -- never merely that the fixture
    parses."""

    def test_every_case_actual_outcome_matches_its_declared_expectation(self) -> None:
        for case in df.ALL_CASES:
            with self.subTest(case=case.case_id):
                outcome = case.run()
                self.assertEqual(
                    outcome.allowed,
                    case.expected_result == df.RESULT_ALLOWED,
                    f"{case.case_id}: allowed={outcome.allowed} but expected_result={case.expected_result}",
                )
                if case.expected_result == df.RESULT_DENIED:
                    self.assertEqual(outcome.security_event, case.expected_security_event)
                    # A denied case's *decisive* action never actually holds
                    # the capability it was denied -- whether that means an
                    # empty spawn grant (spawn itself refused) or an
                    # already-spawned agent whose existing grant still
                    # excludes the specific capability it tried to use.
                    if case.requested_child_capability is not None:
                        self.assertNotIn(case.requested_child_capability, outcome.granted_capabilities)
                    if case.category in (
                        df.CATEGORY_SPAWN_CAPABILITY,
                        df.CATEGORY_INVOCATION_BUDGET,
                        df.CATEGORY_SPAWN_DEPTH,
                    ):
                        # For these categories the spawn call itself is
                        # refused, so the grant is unconditionally empty.
                        self.assertEqual(outcome.granted_capabilities, frozenset())
                else:
                    self.assertIsNone(outcome.security_event)
                    self.assertEqual(outcome.granted_capabilities, case.expected_granted_capabilities)

    def test_every_denied_case_declares_a_recognized_denial_classification(self) -> None:
        for case in df.cases_where(lambda c: c.expected_result == df.RESULT_DENIED):
            with self.subTest(case=case.case_id):
                self.assertIn(case.expected_security_event, df.VALID_DENIAL_CLASSIFICATIONS)

    def test_no_allowed_case_ever_grants_a_non_transferable_capability(self) -> None:
        """Structural proof, over the whole corpus, that no fixture's
        *expectation itself* accidentally claims MUTATE/FORMAL_REVIEW_ACTION
        survives ordinary delegation -- the malformed-fixture guard this
        corpus's own validator does not (and should not) special-case."""
        for case in df.cases_where(lambda c: c.expected_result == df.RESULT_ALLOWED):
            with self.subTest(case=case.case_id):
                self.assertFalse(
                    case.expected_granted_capabilities & ad.NON_TRANSFERABLE_CAPABILITIES,
                    f"{case.case_id} expects a non-transferable capability to be granted",
                )


class ChurnAndRecursionSequenceTests(unittest.TestCase):
    """Deeper, whole-sequence assertions for the two scenarios a single
    allowed/denied fixture cannot fully capture: churn (every attempt
    after exhaustion must be denied, not just the last one) and
    recursion (the tree must stop, not merely the final generation)."""

    def test_every_post_exhaustion_churn_attempt_is_denied(self) -> None:
        outcomes = df.run_spawn_kill_spawn_churn(agents=3, churn_attempts=5)
        fill, churn = outcomes[:2], outcomes[2:]
        self.assertTrue(all(o.allowed for o in fill))
        self.assertTrue(all(not o.allowed for o in churn))
        self.assertTrue(all(o.security_event == ad.DENIED_SPAWN_BUDGET_EXCEEDED for o in churn))

    def test_invocation_budget_exposes_no_reset_or_release_primitive(self) -> None:
        """There is no kill/release/reset method at all in the reference
        model -- the structural reason churn can never evade the budget.
        A future addition of one would be a real regression, not a stylistic
        nit, so this is asserted directly against the class surface."""
        forbidden_method_names = {
            "reset",
            "release",
            "release_slot",
            "decrement",
            "free",
            "kill",
            "remove_agent",
            "widen",
            "increase_max",
        }
        public_methods = {name for name in dir(ad.InvocationBudget) if not name.startswith("_")}
        overlap = public_methods & forbidden_method_names
        self.assertFalse(overlap, f"InvocationBudget exposes a budget-reset-shaped method: {overlap}")

    def test_recursive_tree_is_stopped_well_short_of_the_requested_depth(self) -> None:
        outcomes = df.run_recursive_spawn_tree(agents=4, depth=10)
        allowed = [o for o in outcomes if o.allowed]
        denied = [o for o in outcomes if not o.allowed]
        # root + 3 generations allowed (budget=4), the 4th generation denied,
        # and generations 5..10 are never even attempted (loop breaks).
        self.assertEqual(len(allowed), 3)
        self.assertGreaterEqual(len(denied), 1)
        self.assertTrue(all(o.security_event == ad.DENIED_SPAWN_BUDGET_EXCEEDED for o in denied))
        self.assertLess(len(outcomes), 10, "recursion must stop, not merely have its last hop denied")


class SiblingReconstructionCanaryTests(unittest.TestCase):
    """Proves the sibling-reconstruction check has genuine detection
    power: a deliberately broken, union-based stand-in combinator *would*
    be caught by the same assertion the real corpus cases use, so their
    uniform `allowed` outcome above is not merely a check that can never
    fail. Mirrors `ScopeDisciplineCheckerCatchesViolationTests` in
    `test_reviewer_brief_publication_isolation.py`."""

    @staticmethod
    def _broken_union_combinator(*sibling_sets: "frozenset[ad.Capability]") -> "frozenset[ad.Capability]":
        combined: "frozenset[ad.Capability]" = frozenset()
        for s in sibling_sets:
            combined = combined | s  # the regression this canary catches
        return combined

    def test_canary_union_combinator_is_flagged_as_an_escalation(self) -> None:
        sibling_a = frozenset({ad.Capability.ANALYZE, ad.Capability.PUBLISH})
        sibling_b = frozenset({ad.Capability.ANALYZE, ad.Capability.RUNTIME_VALIDATE})
        reconstructed = self._broken_union_combinator(sibling_a, sibling_b)
        escalated = bool((reconstructed - sibling_a) or (reconstructed - sibling_b))
        self.assertTrue(escalated, "the canary combinator must be caught by the escalation check")

    def test_real_combinator_never_triggers_the_same_check(self) -> None:
        sibling_a = frozenset({ad.Capability.ANALYZE, ad.Capability.PUBLISH})
        sibling_b = frozenset({ad.Capability.ANALYZE, ad.Capability.RUNTIME_VALIDATE})
        reconstructed = ad.capabilities_from_shared_state(sibling_a, sibling_b)
        escalated = bool((reconstructed - sibling_a) or (reconstructed - sibling_b))
        self.assertFalse(escalated)


class AuthorizationReplayLedgerTests(unittest.TestCase):
    def test_first_use_succeeds_replay_by_sibling_fails(self) -> None:
        first, replay = df.run_authorization_replay_attempt()
        self.assertTrue(first)
        self.assertFalse(replay)


# ---------------------------------------------------------------------------
# Malformed-fixture rejection -- the corpus validator itself, exercised
# against deliberately broken fixtures it must reject.
# ---------------------------------------------------------------------------


def _valid_template() -> df.DelegationCase:
    # Every field on a real, passing case -- mutated per-test via `replace`.
    return df.SPAWN_DENIED_WITHOUT_CAPABILITY


class MalformedFixtureRejectionTests(unittest.TestCase):
    def test_rejects_unknown_category(self) -> None:
        bad = replace(_valid_template(), category="not_a_real_category")
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_empty_case_id(self) -> None:
        bad = replace(_valid_template(), case_id="")
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_non_capability_element_in_parent_capabilities(self) -> None:
        bad = replace(_valid_template(), parent_capabilities=frozenset({"spawn_agent"}))
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_non_capability_element_in_delegated_capabilities(self) -> None:
        bad = replace(_valid_template(), delegated_capabilities=frozenset({"analyze"}))
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_negative_spawn_depth(self) -> None:
        bad = replace(_valid_template(), spawn_depth=-1)
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_negative_max_spawn_depth(self) -> None:
        bad = replace(_valid_template(), max_spawn_depth=-1)
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_zero_agent_budget(self) -> None:
        bad = replace(_valid_template(), max_agents_per_invocation=0)
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_invalid_expected_result_token(self) -> None:
        bad = replace(_valid_template(), expected_result="maybe")
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_denied_case_with_no_denial_classification(self) -> None:
        bad = replace(_valid_template(), expected_result=df.RESULT_DENIED, expected_security_event=None)
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_denied_case_with_unrecognized_denial_classification(self) -> None:
        bad = replace(_valid_template(), expected_security_event="DENIED_SOMETHING_MADE_UP")
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_denied_case_that_also_claims_granted_capabilities(self) -> None:
        bad = replace(_valid_template(), expected_granted_capabilities=frozenset({ad.Capability.ANALYZE}))
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_allowed_case_that_still_carries_a_denial_classification(self) -> None:
        bad = replace(
            df.SPAWN_ALLOWED_WITH_CAPABILITY_BOUNDED,
            expected_security_event=ad.DENIED_SPAWN_UNAUTHORIZED,
        )
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_allowed_case_missing_expected_granted_capabilities(self) -> None:
        bad = replace(df.SPAWN_ALLOWED_WITH_CAPABILITY_BOUNDED, expected_granted_capabilities=None)
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_malformed_threat_scenario_id(self) -> None:
        bad = replace(_valid_template(), threat_scenario_ids=("not-an-id",))
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_threat_scenario_id_with_wrong_digit_count(self) -> None:
        bad = replace(_valid_template(), threat_scenario_ids=("DELEG-1",))
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_rejects_non_callable_run(self) -> None:
        bad = replace(_valid_template(), run="not-callable")  # type: ignore[arg-type]
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_case(bad)

    def test_corpus_validation_rejects_duplicate_case_ids(self) -> None:
        dup = replace(df.SPAWN_ALLOWED_WITH_CAPABILITY_BOUNDED, case_id=df.SPAWN_DENIED_WITHOUT_CAPABILITY.case_id)
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_corpus((df.SPAWN_DENIED_WITHOUT_CAPABILITY, dup))

    def test_corpus_validation_rejects_empty_corpus(self) -> None:
        with self.assertRaises(df.DelegationFixtureError):
            df.validate_corpus(())

    def test_a_genuinely_valid_case_still_passes(self) -> None:
        # Negative-canary guard: the template itself must not be broken,
        # or every rejection test above would be vacuous.
        df.validate_case(_valid_template())


class SelectionHelperTests(unittest.TestCase):
    """The in-module equivalent of this repository's focused-selection
    convention: a case can be found by category, by covered requirement
    tag, or by threat-scenario id, so future tooling (#310) can slice the
    corpus without re-deriving it."""

    def test_cases_in_category_returns_only_that_category(self) -> None:
        for category in df.VALID_CATEGORIES:
            for case in df.cases_in_category(category):
                self.assertEqual(case.category, category)

    def test_cases_covering_returns_only_cases_with_that_tag(self) -> None:
        tag = next(iter(df.REQUIRED_COVERAGE_TAGS))
        for case in df.cases_covering(tag):
            self.assertIn(tag, case.covers)

    def test_cases_for_threat_scenario_returns_only_matching_cases(self) -> None:
        for case in df.cases_for_threat_scenario("DELEG-001"):
            self.assertIn("DELEG-001", case.threat_scenario_ids)
        self.assertTrue(df.cases_for_threat_scenario("DELEG-001"))


if __name__ == "__main__":
    unittest.main()
