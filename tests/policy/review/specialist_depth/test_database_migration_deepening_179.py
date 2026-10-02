#!/usr/bin/env python3
"""Pins the database/migration deepening capability contract (Issue #179).

A domain-specific deepening capability under the composition contract
defined in #82 (`specialist-depth.md`): bounded, evidence-driven tracing
of a schema-evolution/migration concern — destructive/online migrations,
backfills, nullable-to-non-null transitions, expand/contract sequencing,
old/new application coexistence, rollback safety, locking/table rewrites,
large data movement, and transactional boundaries — once base review
(#211) has already identified a materially implicated "Data / persistence"
dimension. These assertions protect the cross-document invariant, not
merely that each file mentions the feature:

1. one canonical shared policy owns the capability; `review-scope.md`'s
   "Data / persistence" dimension routes to it as an additional depth
   owner, the same way it already routes to "Existing behavior ownership"
   and "Findings beyond the changed lines";
2. the capability never decides whether a data/persistence concern is
   considered at all — that stays with #211's base pass, unconditionally;
3. activation is evidence-driven, never a file-type/path/tool-name router;
4. cascading/rollout tracing is bounded by #87's existing
   expansion/stop-condition contract, reused via #82;
5. findings are ordinary findings carrying the optional `capability`
   provenance field, never a new severity/evidence schema;
6. unrecognized migration tooling/dialect fails safe with no invented
   findings, and migration-file presence alone never forces deep analysis;
7. it is indexed in the shared policy map and packaging manifest.
"""

from __future__ import annotations

import unittest

from tests.support.deepening_contract import DeepeningContractMixin, DeepeningDomain
from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _norm

POLICY = REPO_ROOT / "shared/policies/database-migration-deepening.md"

DOMAIN = DeepeningDomain(
    policy=POLICY,
    dimension="Data / persistence",
    never_decides=(
        "This capability never decides whether a schema-evolution/"
        "migration concern is considered at all"
    ),
    implication_without_file=(
        "no file conventionally associated with migrations can still "
        "satisfy both"
    ),
    concern_areas=(
        "Destructive and online migrations",
        "Backfills",
        "Nullable-to-non-null transitions",
        "Expand/contract sequencing",
        "Old/new application coexistence",
        "Rollback safety",
        "Locking and table rewrites",
        "Large data movement",
        "Transactional boundaries",
    ),
    no_unbounded_audit=(
        "never a separate, unbounded audit of every migration or "
        "table in the repository"
    ),
    no_second_schema="No new finding/severity/evidence schema",
    generic_advice_rejected=(
        "generic database style advice with no traced schema-"
        "evolution risk in this change does not meet the evidence "
        "bar"
    ),
    review_scope_absent=(
        "expand/contract sequencing",
        "old/new application coexistence",
    ),
)


class DatabaseMigrationDeepeningContractTests(
    DeepeningContractMixin, unittest.TestCase
):
    domain = DOMAIN


class FailSafeTests(unittest.TestCase):
    """Unrecognized migration tooling/dialect must not produce invented
    findings, and migration-file presence alone must never force deep
    analysis."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_unrecognized_tooling_section_present(self) -> None:
        self.assertIn("Unrecognized tooling or storage technology", self.text)

    def test_no_speculation_language(self) -> None:
        self.assertIn(
            "this capability does not speculate about that tool's or "
            "storage system's specific locking, online-DDL, "
            "transactional, or consistency guarantees",
            self.text,
        )

    def test_migration_file_presence_alone_not_sufficient(self) -> None:
        self.assertIn(
            "Migration-file presence alone is not sufficient", self.text
        )
        self.assertIn(
            "does not by itself trigger maximum-depth analysis",
            self.text,
        )


class NonGoalsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_no_migration_execution(self) -> None:
        self.assertIn(
            "No migration execution or database connection", self.text
        )

    def test_not_a_generic_orm_linter(self) -> None:
        self.assertIn(
            "Not a generic ORM/ODM/query style linter, for any storage "
            "model",
            self.text,
        )


class WorkedExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_domain_specific_cases_present(self) -> None:
        self.assertIn(
            "Engages — online migration against a live table", self.text
        )
        self.assertIn(
            "Engages — old/new application coexistence", self.text
        )
        self.assertIn("Unrecognized tooling — fails safe", self.text)


if __name__ == "__main__":
    unittest.main()
