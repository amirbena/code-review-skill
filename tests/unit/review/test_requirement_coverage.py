"""Behavioral fixtures for requirement coverage (Issue #176)."""

from __future__ import annotations

import unittest

from tests.reference.review import requirement_coverage as rc


SOURCE = rc.RequirementSource(
    evidence_type="acceptance_criteria",
    name="Issue #176",
    citation="Acceptance Criteria",
)


def row(
    requirement_id: str,
    status: rc.RequirementStatus,
    *,
    evidence: tuple[str, ...] = ("src/writes.py:42",),
    ambiguity: str | None = None,
) -> rc.RequirementCoverage:
    return rc.RequirementCoverage(
        requirement_id=requirement_id,
        requirement=f"Requirement {requirement_id}",
        source=SOURCE,
        status=status,
        evidence=evidence,
        explanation=f"Evidence assessment for {requirement_id}",
        ambiguity=ambiguity,
    )


class ActivationTests(unittest.TestCase):
    def test_no_contract_is_inert(self) -> None:
        self.assertFalse(rc.coverage_is_active([]))
        self.assertFalse(rc.coverage_is_active(["informal_discussion"]))
        self.assertIsNone(rc.completeness([]))
        self.assertIsNone(rc.to_machine_model([]))

    def test_only_authoritative_task_contract_types_activate(self) -> None:
        self.assertTrue(rc.coverage_is_active(["requirement"]))
        self.assertTrue(rc.coverage_is_active(["acceptance_criteria"]))
        self.assertFalse(rc.coverage_is_active(["accepted_decision"]))


class CoverageFixtureTests(unittest.TestCase):
    def test_partial_fixture_derives_missing_requirement_from_evidence(self) -> None:
        requirements = (
            rc.RequirementAssessment(
                "R1",
                "Validate create and update writes before persistence.",
                SOURCE,
                ("create", "update"),
                (
                    rc.ObligationEvidence(
                        "create",
                        ("src/writes.py:42 — create calls validate",),
                        ("tests/test_writes.py:18 — create validation",),
                    ),
                ),
                test_required=True,
            ),
            rc.RequirementAssessment(
                "R2",
                "Reject writes while the record is locked.",
                SOURCE,
                ("lock-rejection",),
                (),
                test_required=True,
                inspection_evidence=(
                    "src/writes.py:20-70 — no lock-state rejection branch",
                ),
            ),
        )
        rows = tuple(rc.classify(requirement) for requirement in requirements)
        model = rc.to_machine_model(rows)
        self.assertEqual(model["requirement_coverage"]["status"], "incomplete")
        self.assertEqual(
            [item["status"] for item in model["requirement_coverage"]["requirements"]],
            ["partially_evidenced", "not_evidenced"],
        )

        self.assertIn("update", rows[0].explanation)
        self.assertIn("lock-rejection", rows[1].explanation)

    def test_full_fixture_derives_complete_with_citations(self) -> None:
        requirements = (
            rc.RequirementAssessment(
                "R1",
                "Validate create and update writes before persistence.",
                SOURCE,
                ("create", "update"),
                (
                    rc.ObligationEvidence("create", ("src/writes.py:42",), ("tests/test_writes.py:18",)),
                    rc.ObligationEvidence("update", ("src/writes.py:57",), ("tests/test_writes.py:31",)),
                ),
                test_required=True,
            ),
        )
        rows = tuple(rc.classify(requirement) for requirement in requirements)
        model = rc.to_machine_model(rows)
        self.assertEqual(model["requirement_coverage"]["status"], "complete")
        for item in model["requirement_coverage"]["requirements"]:
            self.assertTrue(item["source"]["citation"])
            self.assertTrue(item["evidence"])

    def test_ambiguous_requirement_is_retained_explicitly(self) -> None:
        assessment = rc.RequirementAssessment(
            "R1",
            "Support legacy mode where relevant.",
            SOURCE,
            ("legacy-mode",),
            (),
            applicability=rc.Applicability.AMBIGUOUS,
            ambiguity="The contract does not define legacy mode.",
        )
        rows = (rc.classify(assessment),)
        model = rc.to_machine_model(rows)
        item = model["requirement_coverage"]["requirements"][0]
        self.assertEqual(model["requirement_coverage"]["status"], "incomplete")
        self.assertEqual(item["status"], "not_applicable")
        self.assertIn("ambiguity", item)

    def test_genuinely_inapplicable_requirement_can_be_complete(self) -> None:
        assessment = rc.RequirementAssessment(
            "R1",
            "Exercise the Windows-only write path.",
            SOURCE,
            ("windows-write",),
            (),
            applicability=rc.Applicability.NOT_APPLICABLE,
            applicability_evidence=(
                "Issue scope explicitly limits this target to Linux.",
            ),
        )
        rows = (rc.classify(assessment),)
        model = rc.to_machine_model(rows)
        self.assertEqual(model["requirement_coverage"]["status"], "complete")
        self.assertEqual(len(model["requirement_coverage"]["requirements"]), 1)
        self.assertNotIn("ambiguity", model["requirement_coverage"]["requirements"][0])


class ModelInvariantTests(unittest.TestCase):
    def test_all_four_states_are_machine_readable(self) -> None:
        self.assertEqual(
            {status.value for status in rc.RequirementStatus},
            {"implemented", "partially_evidenced", "not_evidenced", "not_applicable"},
        )

    def test_only_ambiguous_not_applicable_allows_no_evidence(self) -> None:
        for status in (
            rc.RequirementStatus.IMPLEMENTED,
            rc.RequirementStatus.PARTIALLY_EVIDENCED,
            rc.RequirementStatus.NOT_EVIDENCED,
        ):
            with self.subTest(status=status), self.assertRaises(ValueError):
                rc.validate((row("R1", status, evidence=()),))
        with self.assertRaises(ValueError):
            rc.validate((row("R1", rc.RequirementStatus.NOT_APPLICABLE, evidence=()),))
        rc.validate(
            (
                row(
                    "R1",
                    rc.RequirementStatus.NOT_APPLICABLE,
                    evidence=(),
                    ambiguity="Applicability unresolved.",
                ),
            )
        )

    def test_serialization_preserves_preclassified_rows(self) -> None:
        model = rc.to_machine_model(
            (row("R1", rc.RequirementStatus.PARTIALLY_EVIDENCED),)
        )
        self.assertEqual(
            model["requirement_coverage"]["requirements"][0]["status"],
            "partially_evidenced",
        )

    def test_completeness_does_not_contain_severity_or_decision(self) -> None:
        model = rc.to_machine_model((row("R1", rc.RequirementStatus.NOT_EVIDENCED),))
        serialized = repr(model).lower()
        self.assertNotIn("severity", serialized)
        self.assertNotIn("decision", serialized)


if __name__ == "__main__":
    unittest.main()
