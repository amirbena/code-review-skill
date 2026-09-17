#!/usr/bin/env python3
"""Behavioral coverage for the review execution telemetry model (Issue #182).

Contract: docs/review-telemetry/review-execution-telemetry-model.md and
review-execution-telemetry.schema.json. Regression focus: the two worked
examples (full run, partial run) validate against the schema; a mutated
record that violates the schema is rejected; and -- the acceptance
criterion this file exists to prove -- attaching a telemetry record never
changes the decision or findings the existing decision contract derives.
"""

from __future__ import annotations

import unittest

from tests.reference.review import decision_semantics as ds
from tests.reference.review import review_telemetry as rt


def _full_run_example() -> rt.ReviewExecutionTelemetry:
    return rt.ReviewExecutionTelemetry(
        review_id="local-2026-09-17-0001",
        generated_at="2026-09-17T09:15:00Z",
        stages_completed=(
            "scope_normalization",
            "change_risk_classification",
            "repository_expansion",
            "runtime_validation",
            "stopping_criteria",
        ),
        files_inspected=("src/pay/retry.py", "tests/unit/pay/test_retry.py"),
        symbols_expanded_count=2,
        repository_intelligence_expansions={
            "call_site": 0,
            "interface_contract": 0,
            "migration_schema": 0,
            "config_consumer": 0,
        },
        runtime_validations=(
            rt.RuntimeValidationExecution(outcome="executed", provenance="sandbox"),
        ),
        partitions=None,
        stage_timing_ms={
            "scope_normalization": 120.0,
            "change_risk_classification": 40.0,
            "repository_expansion": 310.0,
            "runtime_validation": 2100.0,
            "stopping_criteria": 15.0,
        },
    )


def _partial_run_example() -> rt.ReviewExecutionTelemetry:
    return rt.ReviewExecutionTelemetry(
        review_id="local-2026-09-17-0002",
        generated_at="2026-09-17T09:20:00Z",
        stages_completed=(
            "scope_normalization",
            "change_risk_classification",
            "stopping_criteria",
        ),
        files_inspected=("README.md",),
        symbols_expanded_count=0,
        repository_intelligence_expansions=None,
        runtime_validations=None,
        partitions=None,
        stage_timing_ms=None,
    )


class SchemaValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = rt.load_schema()

    def test_schema_file_loads_as_json(self) -> None:
        self.assertEqual(self.schema["required"], [
            "schema_version",
            "review_id",
            "generated_at",
            "stages_completed",
        ])

    def test_full_run_example_validates(self) -> None:
        errors = rt.validate_against_schema(_full_run_example().to_dict(), self.schema)
        self.assertEqual(errors, ())

    def test_partial_run_example_validates(self) -> None:
        """Acceptance criterion: a partial run (stages that never ran) still
        produces schema-valid output -- every unavailable field resolves to
        null rather than making the record invalid."""
        errors = rt.validate_against_schema(_partial_run_example().to_dict(), self.schema)
        self.assertEqual(errors, ())

    def test_empty_stages_completed_still_validates(self) -> None:
        """An empty stages_completed array is explicitly valid (Section 6 of
        the model doc): no stage reaching completion is not itself an
        error -- only stages-vs-review-stopping-criteria's own coverage
        computation, unchanged by this record, decides completeness."""
        record = rt.ReviewExecutionTelemetry(
            review_id="local-2026-09-17-0003",
            generated_at="2026-09-17T09:25:00Z",
            stages_completed=(),
        ).to_dict()
        errors = rt.validate_against_schema(record, self.schema)
        self.assertEqual(errors, ())


class MutationRejectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = rt.load_schema()
        self.valid_record = _full_run_example().to_dict()

    def test_missing_required_field_is_rejected(self) -> None:
        mutated = dict(self.valid_record)
        del mutated["review_id"]
        errors = rt.validate_against_schema(mutated, self.schema)
        self.assertTrue(any("review_id" in e for e in errors))

    def test_unknown_stage_name_is_rejected(self) -> None:
        mutated = dict(self.valid_record)
        mutated["stages_completed"] = list(mutated["stages_completed"]) + ["decision_derivation"]
        errors = rt.validate_against_schema(mutated, self.schema)
        self.assertTrue(errors)

    def test_wrong_type_is_rejected(self) -> None:
        mutated = dict(self.valid_record)
        mutated["symbols_expanded_count"] = "two"
        errors = rt.validate_against_schema(mutated, self.schema)
        self.assertTrue(errors)

    def test_unexpected_top_level_field_is_rejected(self) -> None:
        """Findings, severity, or a decision value must never be a valid
        telemetry field -- additionalProperties: false enforces this."""
        mutated = dict(self.valid_record)
        mutated["decision"] = "CHANGES REQUIRED"
        errors = rt.validate_against_schema(mutated, self.schema)
        self.assertTrue(any("decision" in e for e in errors))


class NeverDecisionAffectingGuaranteeTests(unittest.TestCase):
    """The acceptance criterion: a test asserts identical findings/decision
    with telemetry enabled and disabled."""

    def _findings(self) -> tuple[ds.Finding, ...]:
        return (
            ds.Finding(id="F1", severity=ds.Severity.P1),
            ds.Finding(id="F2", severity=ds.Severity.P2),
        )

    def test_decision_identical_with_and_without_telemetry(self) -> None:
        findings = self._findings()
        decision_without = rt.decide_with_telemetry(findings, telemetry=None)
        decision_with = rt.decide_with_telemetry(findings, telemetry=_full_run_example())
        self.assertEqual(decision_without, decision_with)
        self.assertEqual(decision_without, ds.derive_decision(findings))

    def test_findings_list_itself_is_unchanged_by_telemetry_attachment(self) -> None:
        findings = self._findings()
        # Attaching telemetry never mutates, filters, or re-orders findings --
        # the reference model has no code path that could, since
        # decide_with_telemetry never reads `telemetry` at all.
        rt.decide_with_telemetry(findings, telemetry=_full_run_example())
        self.assertEqual(findings, self._findings())

    def test_clean_decision_also_unaffected_by_telemetry(self) -> None:
        clean_findings = (ds.Finding(id="F1", severity=ds.Severity.P2),)
        self.assertEqual(
            rt.decide_with_telemetry(clean_findings, telemetry=None),
            rt.decide_with_telemetry(clean_findings, telemetry=_partial_run_example()),
        )
        self.assertEqual(
            rt.decide_with_telemetry(clean_findings, telemetry=None), ds.Decision.CLEAN
        )

    def test_telemetry_parameter_is_never_forwarded_to_the_decision_contract(self) -> None:
        """Governance guard mirroring decision_semantics.py's own prohibited-
        fragment checks: decide_with_telemetry's only reference to its
        `telemetry` parameter in source is the `del telemetry` no-op line,
        never a branch, attribute read, or forwarded call argument."""
        import inspect

        source = inspect.getsource(rt.decide_with_telemetry)
        self.assertIn("del telemetry", source)
        self.assertNotIn("telemetry.", source)
        self.assertNotIn("if telemetry", source)


if __name__ == "__main__":
    unittest.main()
