#!/usr/bin/env python3
"""Behavioral coverage for the deterministic Top-K benchmark selector
(Issue #334). Contract: runtime_platform/benchmark/selection.md.

Exercised against small, synthetic inverted indexes (the same shape
``build_benchmark_index.py`` produces), never the live corpus — this
module never defines a second scoring/selection implementation and always
consumes ``runtime_platform.benchmark.reference.benchmark_selection``.
"""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.reference import benchmark_selection as sel


def _index(**dims: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    """Build a synthetic ``{dimension: {value: [case_id, ...]}}`` index,
    filling in any dimension not passed as empty."""
    base = {dim: {} for dim in sel.CASE_RELEVANCE_WEIGHTS}
    base.update(dims)
    return base


class RelevanceScoreTests(unittest.TestCase):
    def test_full_overlap_on_every_dimension_scores_100(self) -> None:
        case_taxonomy = {
            "capability": ("security-boundary",),
            "policy_contract": ("review-scope",),
            "risk_mode": ("security",),
            "affected_surface": ("shared-policy",),
        }
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": ("review-scope",),
            "risk_mode": ("security",),
            "affected_surface": ("shared-policy",),
        }
        score, matched = sel.relevance_score(case_taxonomy, pr)
        self.assertEqual(score, 100)
        self.assertEqual(
            set(matched), {"capability", "policy_contract", "risk_mode", "affected_surface"}
        )

    def test_no_overlap_scores_zero(self) -> None:
        case_taxonomy = {
            "capability": ("performance",),
            "policy_contract": ("unclassified",),
            "risk_mode": ("performance",),
            "affected_surface": ("unclassified",),
        }
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": ("review-scope",),
            "risk_mode": ("security",),
            "affected_surface": ("shared-policy",),
        }
        score, matched = sel.relevance_score(case_taxonomy, pr)
        self.assertEqual(score, 0)
        self.assertEqual(matched, ())

    def test_capability_only_overlap_scores_its_weight(self) -> None:
        case_taxonomy = {"capability": ("security-boundary",)}
        pr = {"capability": ("security-boundary",), "policy_contract": (), "risk_mode": (), "affected_surface": ()}
        score, matched = sel.relevance_score(case_taxonomy, pr)
        self.assertEqual(score, sel.CASE_RELEVANCE_WEIGHTS["capability"])
        self.assertEqual(matched, ("capability",))

    def test_unclassified_never_counts_as_overlap(self) -> None:
        case_taxonomy = {"capability": ("unclassified",)}
        pr = {"capability": ("unclassified",), "policy_contract": (), "risk_mode": (), "affected_surface": ()}
        score, matched = sel.relevance_score(case_taxonomy, pr)
        self.assertEqual(score, 0)
        self.assertEqual(matched, ())

    def test_bands_match_documented_thresholds(self) -> None:
        self.assertEqual(sel.relevance_band(100), sel.BAND_PRIMARY)
        self.assertEqual(sel.relevance_band(60), sel.BAND_PRIMARY)
        self.assertEqual(sel.relevance_band(59), sel.BAND_SECONDARY)
        self.assertEqual(sel.relevance_band(40), sel.BAND_SECONDARY)
        self.assertEqual(sel.relevance_band(39), sel.BAND_NOT_ELIGIBLE)
        self.assertEqual(sel.relevance_band(0), sel.BAND_NOT_ELIGIBLE)

    def test_weights_sum_to_one_hundred(self) -> None:
        self.assertEqual(sum(sel.CASE_RELEVANCE_WEIGHTS.values()), 100)


class ImplicatedPairsTests(unittest.TestCase):
    def test_single_value_per_dimension_sums_to_100(self) -> None:
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": ("review-scope",),
            "risk_mode": ("security",),
            "affected_surface": ("shared-policy",),
        }
        pairs = sel.implicated_pairs(pr)
        self.assertAlmostEqual(sum(pairs.values()), 100.0)
        self.assertEqual(
            pairs[("capability", "security-boundary")], sel.CASE_RELEVANCE_WEIGHTS["capability"]
        )

    def test_multiple_values_share_the_dimension_weight(self) -> None:
        pr = {
            "capability": ("security-boundary", "performance"),
            "policy_contract": (),
            "risk_mode": (),
            "affected_surface": (),
        }
        pairs = sel.implicated_pairs(pr)
        expected_share = sel.CASE_RELEVANCE_WEIGHTS["capability"] / 2
        self.assertAlmostEqual(pairs[("capability", "security-boundary")], expected_share)
        self.assertAlmostEqual(pairs[("capability", "performance")], expected_share)

    def test_wholly_unclassified_dimension_contributes_no_pairs(self) -> None:
        pr = {
            "capability": ("unclassified",),
            "policy_contract": ("review-scope",),
            "risk_mode": (),
            "affected_surface": (),
        }
        pairs = sel.implicated_pairs(pr)
        self.assertNotIn(("capability", "unclassified"), pairs)
        self.assertAlmostEqual(sum(pairs.values()), sel.CASE_RELEVANCE_WEIGHTS["policy_contract"])


class SelectionCoverageTests(unittest.TestCase):
    def test_uncovered_when_no_case_selected(self) -> None:
        pairs = {("capability", "security-boundary"): 40.0, ("risk_mode", "security"): 20.0}
        coverage, uncovered = sel.selection_coverage({}, pairs)
        self.assertEqual(coverage, 0.0)
        self.assertEqual(set(uncovered), set(pairs))

    def test_covered_once_any_selected_case_matches(self) -> None:
        pairs = {("capability", "security-boundary"): 40.0, ("risk_mode", "security"): 20.0}
        selected = {"case-a": {"capability": ("security-boundary",), "risk_mode": ("correctness",)}}
        coverage, uncovered = sel.selection_coverage(selected, pairs)
        self.assertEqual(coverage, 40.0)
        self.assertEqual(uncovered, (("risk_mode", "security"),))


class SelectCasesTests(unittest.TestCase):
    def test_greedy_selection_prefers_coverage_over_pure_relevance(self) -> None:
        # case-a is highly relevant but redundant with case-b on the same
        # single pair; case-c is lower-relevance but the only case that
        # covers the PR's second implicated dimension. Coverage-maximizing
        # selection must prefer covering both dimensions over stacking
        # redundant high-relevance picks.
        index = _index(
            capability={"security-boundary": ["case-a", "case-b", "case-c"]},
            risk_mode={"concurrency": ["case-c"]},
        )
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": (),
            "risk_mode": ("concurrency",),
            "affected_surface": (),
        }
        result = sel.select_cases(index, pr, k=2)
        self.assertIn("case-c", result["selected"])
        self.assertEqual(result["outcome"], sel.OUTCOME_SUFFICIENT_COVERAGE)
        self.assertGreaterEqual(result["selection_coverage"], sel.SELECTION_COVERAGE_THRESHOLD)

    def test_stops_once_coverage_threshold_reached_even_with_top_k_headroom(self) -> None:
        # Three dimensions implicated (weight 40+25+20=85, already >= the
        # 60% threshold on their own) and two identical candidates: greedy
        # selection must stop after the first pick even though k leaves
        # plenty of headroom and a second, equally-relevant case exists.
        index = _index(
            capability={"security-boundary": ["case-a", "case-b"]},
            policy_contract={"review-scope": ["case-a", "case-b"]},
            risk_mode={"security": ["case-a", "case-b"]},
        )
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": ("review-scope",),
            "risk_mode": ("security",),
            "affected_surface": (),
        }
        result = sel.select_cases(index, pr, k=sel.K_MAX)
        self.assertEqual(len(result["selected"]), 1)
        self.assertEqual(result["outcome"], sel.OUTCOME_SUFFICIENT_COVERAGE)

    def test_top_k_bound_is_respected(self) -> None:
        index = _index(
            capability={"a": ["case-1"], "b": ["case-2"], "c": ["case-3"], "d": ["case-4"]}
        )
        pr = {
            "capability": ("a", "b", "c", "d"),
            "policy_contract": (),
            "risk_mode": (),
            "affected_surface": (),
        }
        result = sel.select_cases(index, pr, k=2)
        self.assertLessEqual(len(result["selected"]), 2)

    def test_k_is_clamped_to_k_max(self) -> None:
        index = _index(capability={"security-boundary": ["case-a"]})
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": (),
            "risk_mode": (),
            "affected_surface": (),
        }
        result = sel.select_cases(index, pr, k=999)
        self.assertEqual(result["top_k_bound"], sel.K_MAX)

    def test_insufficient_coverage_is_explicit_and_reports_uncovered_pairs(self) -> None:
        # Nothing in the index matches the PR's classification at all, so
        # the candidate pool (and therefore the eligible pool) is empty.
        index = _index()
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": ("review-scope",),
            "risk_mode": ("security",),
            "affected_surface": ("shared-policy",),
        }
        result = sel.select_cases(index, pr)
        self.assertEqual(result["outcome"], sel.OUTCOME_INSUFFICIENT_COVERAGE)
        self.assertEqual(result["selected"], ())
        self.assertEqual(result["selection_coverage"], 0.0)
        self.assertEqual(len(result["uncovered_pairs"]), 4)

    def test_not_eligible_band_case_is_never_selected(self) -> None:
        # case-a only overlaps on affected_surface (weight 15, below the
        # secondary band floor of 40), so it must never be selected even
        # though it is the only candidate available.
        index = _index(affected_surface={"shared-policy": ["case-a"]})
        pr = {
            "capability": (),
            "policy_contract": (),
            "risk_mode": (),
            "affected_surface": ("shared-policy",),
        }
        result = sel.select_cases(index, pr)
        self.assertEqual(result["selected"], ())
        self.assertEqual(result["outcome"], sel.OUTCOME_INSUFFICIENT_COVERAGE)

    def test_wholly_unclassified_pr_is_vacuously_sufficient(self) -> None:
        index = _index(capability={"security-boundary": ["case-a"]})
        pr = {
            "capability": ("unclassified",),
            "policy_contract": ("unclassified",),
            "risk_mode": ("unclassified",),
            "affected_surface": ("unclassified",),
        }
        result = sel.select_cases(index, pr)
        self.assertEqual(result["selected"], ())
        self.assertEqual(result["selection_coverage"], 100.0)
        self.assertEqual(result["outcome"], sel.OUTCOME_SUFFICIENT_COVERAGE)

    def test_deterministic_tie_break_is_lexicographic_case_id(self) -> None:
        index = _index(capability={"security-boundary": ["case-z", "case-a"]})
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": (),
            "risk_mode": (),
            "affected_surface": (),
        }
        result = sel.select_cases(index, pr, k=1)
        self.assertEqual(result["selected"], ("case-a",))

    def test_same_inputs_always_yield_the_same_selection(self) -> None:
        index = _index(
            capability={"security-boundary": ["case-a", "case-b"]},
            risk_mode={"security": ["case-b"]},
        )
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": (),
            "risk_mode": ("security",),
            "affected_surface": (),
        }
        first = sel.select_cases(index, pr, k=3)
        second = sel.select_cases(index, pr, k=3)
        self.assertEqual(first, second)

    def test_candidate_pool_size_reflects_index_narrowing_not_full_corpus(self) -> None:
        index = _index(
            capability={"security-boundary": ["case-a"], "performance": ["case-unrelated"]}
        )
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": (),
            "risk_mode": (),
            "affected_surface": (),
        }
        result = sel.select_cases(index, pr)
        self.assertEqual(result["candidate_pool_size"], 1)


class ExplainabilityTests(unittest.TestCase):
    def test_build_explainability_has_every_documented_field(self) -> None:
        index = _index(capability={"security-boundary": ["case-a"]})
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": (),
            "risk_mode": (),
            "affected_surface": (),
        }
        result = sel.select_cases(index, pr)
        explainability = sel.build_explainability(result)
        for field in (
            "resolved_taxonomy_classification",
            "candidate_pool_size",
            "selected_cases",
            "selection_coverage",
            "coverage_threshold",
            "top_k_bound",
            "uncovered_pairs",
            "outcome",
        ):
            self.assertIn(field, explainability)
        self.assertEqual(explainability["selected_cases"][0]["case_id"], "case-a")
        self.assertIn("marginal_coverage_gain", explainability["selected_cases"][0])

    def test_explainability_is_json_serializable(self) -> None:
        import json

        index = _index(capability={"security-boundary": ["case-a"]})
        pr = {
            "capability": ("security-boundary",),
            "policy_contract": (),
            "risk_mode": (),
            "affected_surface": (),
        }
        result = sel.select_cases(index, pr)
        json.dumps(sel.build_explainability(result))


if __name__ == "__main__":
    unittest.main()
