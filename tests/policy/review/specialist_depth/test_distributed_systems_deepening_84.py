#!/usr/bin/env python3
"""Pins the distributed systems deepening capability contract (Issue #84).

A domain-specific deepening capability under the composition contract
defined in #82 (`specialist-depth.md`): bounded, evidence-driven tracing
of a concurrency/distributed-system concern — ordering guarantees, retry
interaction, idempotency boundaries, concurrent interleavings, ownership/
coordination assumptions, and partial failure — once base review (#211)
has already identified a materially implicated "Concurrency /
distributed-system semantics" dimension. These assertions protect the
cross-document invariant, not merely that each file mentions the feature:

1. one canonical shared policy owns the capability; `review-scope.md`'s
   "Concurrency / distributed-system semantics" dimension routes to it as
   an additional depth owner, the same way it already routes to
   "Architectural placement and execution-lifecycle fidelity" and
   "Failure state, retry safety, and recovery";
2. the capability never decides whether a concurrency/distributed-system
   concern is considered at all — that stays with #211's base pass,
   unconditionally;
3. activation is evidence-driven, never a file-type/path/keyword router;
4. cascading/interleaving tracing is bounded by #87's existing
   expansion/stop-condition contract, reused via #82;
5. findings are ordinary findings carrying the optional `capability`
   provenance field, never a new severity/evidence schema;
6. it is not formal verification/trace analysis or an unconditional
   checklist over every shared-state operation or message handler;
7. it is indexed in the shared policy map and packaging manifest.
"""

from __future__ import annotations

import unittest

from tests.support.deepening_contract import DeepeningContractMixin, DeepeningDomain
from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _norm

POLICY = REPO_ROOT / "shared/policies/distributed-systems-deepening.md"

DOMAIN = DeepeningDomain(
    policy=POLICY,
    dimension="Concurrency / distributed-system semantics",
    never_decides=(
        "This capability never decides whether a concurrency/"
        "distributed-system concern is considered at all"
    ),
    implication_without_file=(
        "no file conventionally associated with concurrency or "
        "messaging can still satisfy both"
    ),
    concern_areas=(
        "Ordering guarantees",
        "Retry interaction",
        "Idempotency boundaries",
        "Concurrent interleavings",
        "Ownership/coordination assumptions",
        "Partial failure",
    ),
    no_unbounded_audit=(
        "never a separate, unbounded audit of every caller in the "
        "repository"
    ),
    no_second_schema="No new finding/severity/evidence schema",
    generic_advice_rejected=(
        "generic distributed-systems advice with no traced flow in "
        "this change does not meet the evidence bar"
    ),
    review_scope_absent=(
        "confused-deputy behavior",
        "ownership/coordination assumptions",
    ),
)


class DistributedSystemsDeepeningContractTests(
    DeepeningContractMixin, unittest.TestCase
):
    domain = DOMAIN


class NonGoalsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_no_formal_verification(self) -> None:
        self.assertIn(
            "No formal verification or trace analysis", self.text
        )

    def test_not_an_unconditional_checklist(self) -> None:
        self.assertIn(
            "Not a generic checklist over every shared-state operation "
            "or message handler",
            self.text,
        )


class WorkedExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_domain_specific_cases_present(self) -> None:
        self.assertIn("Engages — retry interaction", self.text)
        self.assertIn("Engages — concurrent interleaving", self.text)


if __name__ == "__main__":
    unittest.main()
