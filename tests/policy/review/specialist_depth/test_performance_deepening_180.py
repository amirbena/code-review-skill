#!/usr/bin/env python3
"""Pins the performance deepening capability contract (Issue #180).

A domain-specific deepening capability under the composition contract
defined in #82 (`specialist-depth.md`): bounded, evidence-driven tracing of
a performance/scale concern — cardinality analysis, call-path behavior,
batching, hot-path placement, query/network amplification, and
memory/concurrency implications — once base review (#211) has already
identified a materially implicated "Performance / scale" dimension. These
assertions protect the cross-document invariant, not merely that each file
mentions the feature:

1. one canonical shared policy owns the capability; `review-scope.md`'s
   "Performance / scale" dimension routes to it as an additional depth
   owner, the same way it already routes to "Change-risk signals and
   review depth" and `repository-expansion.md`;
2. the capability never decides whether a performance/scale concern is
   considered at all — that stays with #211's base pass, unconditionally,
   and ordinary performance findings remain part of every review whether
   or not this capability engages;
3. activation is evidence-driven, never a file-type/path/framework router
   — superficial filenames, framework names, or "performance-looking" code
   are not by themselves activation evidence;
4. cascading/call-path tracing is bounded by #87's existing
   expansion/stop-condition contract, reused via #82;
5. findings are ordinary findings carrying the optional `capability`
   provenance field, never a new severity/evidence schema;
6. missing call-graph/data-size context fails safe with no invented
   findings;
7. it does not re-trace concurrent-interleaving correctness, which stays
   owned by `distributed-systems-deepening.md`;
8. it is indexed in the shared policy map and packaging manifest.
"""

from __future__ import annotations

import unittest

from tests.support.deepening_contract import DeepeningContractMixin, DeepeningDomain
from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _norm

POLICY = REPO_ROOT / "shared/policies/performance-deepening.md"
DISTRIBUTED_DEEPENING = REPO_ROOT / "shared/policies/distributed-systems-deepening.md"

DOMAIN = DeepeningDomain(
    policy=POLICY,
    dimension="Performance / scale",
    never_decides=(
        "This capability never decides whether a performance/scale "
        "concern is considered at all"
    ),
    implication_without_file=(
        "Conversely, a change with no file conventionally associated "
        "with performance can still satisfy both"
    ),
    concern_areas=(
        "Cardinality analysis",
        "Call-path behavior",
        "Batching",
        "Hot-path placement",
        "Query/network amplification",
        "Memory/concurrency implications",
    ),
    no_unbounded_audit=(
        "never a separate, unbounded audit of every call site or loop "
        "in the repository"
    ),
    no_second_schema="never a second schema",
    generic_advice_rejected=(
        'generic "this could be slow" advice with no traced cost '
        "concern in this change does not meet the evidence bar"
    ),
    review_scope_absent=("Query/network amplification", "PerformanceUtils.java"),
)


class PerformanceDeepeningContractTests(
    DeepeningContractMixin, unittest.TestCase
):
    domain = DOMAIN


class BaseObligationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_ordinary_reasoning_visible_regardless_of_engagement(self) -> None:
        self.assertIn(
            "An obvious N+1, unbounded work, blocking I/O in a hot path, "
            "or accidental complexity amplification is base reasoning's "
            "job on every review, whether or not this capability engages",
            self.text,
        )


class ConcernAreaBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_memory_concurrency_bounded_away_from_interleaving_correctness(
        self,
    ) -> None:
        self.assertIn(
            "not the correctness of a concurrent interleaving", self.text
        )


class FailSafeTests(unittest.TestCase):
    """Missing call-graph/data-size context must not produce invented
    findings, and superficial signals alone must never force deep
    analysis."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_missing_context_section_present(self) -> None:
        self.assertIn("Missing call-graph or data-size context", self.text)

    def test_no_speculation_language(self) -> None:
        self.assertIn(
            "this capability does not speculate about that volume, "
            "invocation count, or downstream behavior",
            self.text,
        )

    def test_superficial_signals_alone_not_sufficient(self) -> None:
        self.assertIn(
            'Superficial filenames, framework names, and "performance-'
            'looking" code are not activation evidence',
            self.text,
        )
        self.assertIn(
            "does not by itself trigger deep analysis", self.text
        )


class NonGoalsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_no_benchmarking_or_profiling(self) -> None:
        self.assertIn("No benchmarking or profiling", self.text)

    def test_not_a_generic_optimization_advisor(self) -> None:
        self.assertIn("Not a generic optimization advisor", self.text)

    def test_defers_interleaving_correctness_to_distributed_deepening(
        self,
    ) -> None:
        self.assertIn(
            "Does not re-trace concurrent-interleaving correctness",
            self.text,
        )
        self.assertIn(
            "[distributed-systems-deepening.md](distributed-systems-"
            "deepening.md)'s question",
            self.text,
        )


class WorkedExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_domain_specific_cases_present(self) -> None:
        self.assertIn("Engages — N+1 call path", self.text)
        self.assertIn("Engages — hot-path placement", self.text)
        self.assertIn("Missing call-graph context — fails safe", self.text)


class DeferralTests(unittest.TestCase):
    def test_defers_interleaving_correctness_mechanics(self) -> None:
        distributed_raw = DISTRIBUTED_DEEPENING.read_text(encoding="utf-8")
        policy_raw = POLICY.read_text(encoding="utf-8")
        self.assertIn("Concurrent interleavings", distributed_raw)
        self.assertNotIn("## Concurrent interleavings", policy_raw)


if __name__ == "__main__":
    unittest.main()
