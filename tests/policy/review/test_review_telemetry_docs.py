#!/usr/bin/env python3
"""Documentation-contract checks for the review execution telemetry model
(Issue #182).

Pins docs/review-telemetry/review-execution-telemetry-model.md, its
navigational README, the JSON Schema file, the packaged boundary paragraph
in shared/policies/review-stopping-criteria.md, and the reference-module
registration. Structural prose checks in the same style as
test_context_evidence_docs.py -- semantic structure and whitespace-
normalized prose, not brittle exact whitespace.

Run with:
    python3 -m unittest tests.policy.review.test_review_telemetry_docs
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

DOCDIR = REPO_ROOT / "docs" / "review-telemetry"
MODEL = DOCDIR / "review-execution-telemetry-model.md"
DIR_README = DOCDIR / "README.md"
SCHEMA = DOCDIR / "review-execution-telemetry.schema.json"
STOPPING_CRITERIA = REPO_ROOT / "shared" / "policies" / "review-stopping-criteria.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
FEATURES_README = REPO_ROOT / "docs" / "features" / "README.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "review" / "review_telemetry.py"
BOUNDARY = REPO_ROOT / "tests" / "integration" / "packaging" / "_shared.py"

METRICS = (
    "Stages completed",
    "Files inspected",
    "Symbols expanded",
    "Repository-intelligence expansions",
    "Runtime validations executed",
    "Partitions used",
    "Deterministic stage timing",
)


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class DesignRecordExistsTests(unittest.TestCase):
    def test_docs_and_schema_exist(self) -> None:
        self.assertTrue(MODEL.is_file())
        self.assertTrue(DIR_README.is_file())
        self.assertTrue(SCHEMA.is_file())

    def test_schema_is_valid_json(self) -> None:
        json.loads(SCHEMA.read_text(encoding="utf-8"))


class NeverDecisionAffectingGuaranteeTests(unittest.TestCase):
    def test_guarantee_is_stated_in_so_many_words(self) -> None:
        t = _norm(MODEL)
        self.assertIn(
            "The review execution telemetry record has no effect, direct or "
            "indirect, on a review's findings, a finding's severity or "
            "confidence, finding suppression, or the review's decision",
            t,
        )

    def test_guarantee_says_it_is_backed_by_a_test(self) -> None:
        t = _norm(MODEL)
        self.assertIn("This is backed by a test, not only by this sentence", t)
        self.assertIn("test_decision_identical_with_and_without_telemetry", t)

    def test_guarantee_distinguishes_from_decision_affecting_coverage(self) -> None:
        t = _norm(MODEL)
        self.assertIn("deliberately different model", t)
        self.assertIn("review-stopping-criteria.md already defines", t)


class MetricCatalogTests(unittest.TestCase):
    def test_every_metric_is_named(self) -> None:
        t = _norm(MODEL)
        for metric in METRICS:
            self.assertIn(metric, t, f"metric {metric!r} missing from the catalog")

    def test_every_metric_documents_an_unavailable_state(self) -> None:
        t = _norm(MODEL)
        # Every metric row states its own null/unavailable rule explicitly.
        self.assertGreaterEqual(t.count("null"), len(METRICS))
        self.assertIn("Unavailable state", t)

    def test_rationale_column_is_present(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Rationale", t)


class NotCollectedListTests(unittest.TestCase):
    def test_not_collected_section_exists(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Explicitly not collected", t)

    def test_not_collected_items_are_named_with_rejection_reason(self) -> None:
        t = _norm(MODEL)
        for item in (
            "Model token usage, latency-as-cost, or dollar cost",
            "Prompt or response text, or any model reasoning trace",
            "Finding counts, severities, or the decision itself",
            "Reviewer/author/committer identity, or any other PII",
            "Repository name, URL, or any other externally-identifying",
            "Benchmark match/fidelity outcomes",
            "Aggregated/historical trend data across multiple reviews",
        ):
            self.assertIn(item, t, f"not-collected item {item!r} missing")


class Boundary131Tests(unittest.TestCase):
    def test_boundary_section_exists(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Boundary with #131", t)
        self.assertIn("not implemented by this issue", t)

    def test_direction_of_dependency_is_stated(self) -> None:
        t = _norm(MODEL)
        self.assertIn(
            "#131 depends on #182 existing first", t
        )
        self.assertIn("never the other way around", t)

    def test_182_is_raw_signal_131_is_aggregation(self) -> None:
        t = _norm(MODEL)
        self.assertIn("#182 (this document) is the observational raw signal", t)
        self.assertIn("#131 (future) is the aggregation/analytics consumer", t)


class PartialRunTests(unittest.TestCase):
    def test_partial_runs_produce_valid_output_is_stated(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Partial runs produce valid output", t)
        self.assertIn("fully schema-valid", t)

    def test_two_worked_examples_present(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Worked examples", t)
        self.assertIn("Example A", t)
        self.assertIn("Example B", t)
        self.assertIn("a partial run", t)


class PackagedBoundaryParagraphTests(unittest.TestCase):
    def test_stopping_criteria_names_the_distinction_without_linking_into_docs(self) -> None:
        t = STOPPING_CRITERIA.read_text(encoding="utf-8")
        self.assertIn("Relationship to review execution telemetry (Issue #182)", t)
        self.assertIn("purely observational", t)
        # Packaged independence: no packaged shared/policies file may link
        # into docs/ -- it names the concept, never links it.
        self.assertNotIn("docs/review-telemetry", t)
        self.assertNotIn("](../../docs/", t)


class ReferenceModuleWiringTests(unittest.TestCase):
    def test_reference_module_exists(self) -> None:
        self.assertTrue(REFERENCE.is_file())

    def test_reference_module_is_registered_in_boundary_guard(self) -> None:
        t = BOUNDARY.read_text(encoding="utf-8")
        self.assertIn('"review_telemetry.py"', t)


class NavigationWiringTests(unittest.TestCase):
    def test_architecture_map_points_at_the_design_record(self) -> None:
        t = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("review-telemetry/README.md", t)
        self.assertIn("#182", t)

    def test_features_readme_lists_telemetry_as_not_a_feature_guide(self) -> None:
        t = FEATURES_README.read_text(encoding="utf-8")
        self.assertIn("Review execution telemetry", t)
        self.assertIn("review-stopping-criteria.md", t)


if __name__ == "__main__":
    unittest.main()
