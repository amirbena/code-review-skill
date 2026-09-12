#!/usr/bin/env python3
"""Behavioral coverage for the contextual-evidence model (Issue #118).

Contract: docs/review-context/contextual-evidence-model.md. Regression
focus: every evidence type keeps its authoritative/informational marking;
an informational source can never override an explicit requirement or an
approved decision; the resolution table stays deterministic and matches the
design record's five outcomes; introduced-vs-pre-existing attribution does
not let an uncorroborated note excuse a defect the change introduced; the
finding-provenance shape carries no severity and renders nothing when empty.
Includes an induced-regression / mutation check in the style of
tests/unit/review/test_finding_identity_regression.py.
"""

from __future__ import annotations

import unittest

from tests.reference.review import context_evidence as ce

T = ce.ContextualEvidenceType
R = ce.Resolution


# --- The five design-record worked examples, as an asserted corpus -------
# Each row mirrors a "Worked example N" block in
# docs/review-context/contextual-evidence-model.md and must classify as
# documented there.
WORKED_EXAMPLES = (
    {
        "name": "1 — acceptance criterion unmet",
        "resolve_kwargs": {"supporting_types": [T.ACCEPTANCE_CRITERIA]},
        "expected_resolution": R.USE_AUTHORITATIVE,
        "can_establish_finding": True,
    },
    {
        "name": "2 — informal discussion contradicts an accepted decision",
        "resolve_kwargs": {
            "supporting_types": [T.ACCEPTED_DECISION, T.INFORMAL_DISCUSSION]
        },
        "expected_resolution": R.USE_AUTHORITATIVE,
        "can_establish_finding": True,
        "override_check": (T.INFORMAL_DISCUSSION, T.ACCEPTED_DECISION, False),
    },
    {
        "name": "3 — risk that pre-dates the change",
        "resolve_kwargs": {"supporting_types": [T.PRE_EXISTING_RISK_NOTE]},
        "expected_resolution": R.TREAT_AS_INFORMATIONAL_ONLY,
        "can_establish_finding": False,
        "origin": {
            "kwargs": {
                "note_type": T.PRE_EXISTING_RISK_NOTE,
                "corroborated_by_pre_change_code": True,
                "change_introduces_or_activates": False,
            },
            "expected": ce.FindingOrigin.PRE_EXISTING,
        },
    },
    {
        "name": "4 — requirement vs repository policy, contract settles it",
        "resolve_kwargs": {
            "supporting_types": [T.REQUIREMENT, T.REPOSITORY_POLICY],
            "requirement_vs_repo_policy_conflict": True,
            "existing_contract_settles_it": True,
        },
        "expected_resolution": R.USE_AUTHORITATIVE,
        "can_establish_finding": True,
    },
    {
        "name": "5 — unratified implementation feedback",
        "resolve_kwargs": {"supporting_types": [T.IMPLEMENTATION_FEEDBACK]},
        "expected_resolution": R.TREAT_AS_INFORMATIONAL_ONLY,
        "can_establish_finding": False,
    },
    {
        "name": "6 — two authoritative sources genuinely contradict",
        "resolve_kwargs": {
            "supporting_types": [T.ACCEPTANCE_CRITERIA, T.ACCEPTED_DECISION],
            "contradicting_authoritative": True,
        },
        "expected_resolution": R.REPORT_CONFLICT,
        "can_establish_finding": False,
    },
    {
        "name": "7 — authoritative source too vague to decide the point",
        "resolve_kwargs": {
            "supporting_types": [T.REQUIREMENT],
            "authoritative_source_is_vague": True,
        },
        "expected_resolution": R.REPORT_AMBIGUITY,
        "can_establish_finding": False,
    },
    {
        "name": "8 — accepted decision superseded by newer maintainer clarification",
        "resolve_kwargs": {
            "supporting_types": [T.ACCEPTED_DECISION],
            "superseded_by_newer_maintainer_clarification": True,
        },
        "expected_resolution": R.DISREGARD_STALE,
        "can_establish_finding": False,
    },
)


class TypedEvidenceModelTests(unittest.TestCase):
    def test_every_type_is_marked_exactly_once(self) -> None:
        self.assertEqual(
            ce.AUTHORITATIVE | ce.INFORMATIONAL, set(ce.ContextualEvidenceType)
        )
        self.assertEqual(ce.AUTHORITATIVE & ce.INFORMATIONAL, set())

    def test_authoritative_set_is_exactly_the_four_documented_types(self) -> None:
        self.assertEqual(
            ce.AUTHORITATIVE,
            frozenset(
                {
                    T.REQUIREMENT,
                    T.ACCEPTANCE_CRITERIA,
                    T.ACCEPTED_DECISION,
                    T.REPOSITORY_POLICY,
                }
            ),
        )

    def test_informal_discussion_and_feedback_are_informational(self) -> None:
        self.assertIs(ce.authority_of(T.INFORMAL_DISCUSSION), ce.Authority.INFORMATIONAL)
        self.assertIs(
            ce.authority_of(T.IMPLEMENTATION_FEEDBACK), ce.Authority.INFORMATIONAL
        )


class NonOverrideRuleTests(unittest.TestCase):
    def test_informational_source_never_overrides_anything(self) -> None:
        for source in ce.INFORMATIONAL:
            for target in ce.ContextualEvidenceType:
                self.assertFalse(
                    ce.can_override(source, target), (source, target)
                )

    def test_no_source_silently_overrides_an_explicit_requirement_or_decision(
        self,
    ) -> None:
        for source in ce.ContextualEvidenceType:
            for target in (
                T.REQUIREMENT,
                T.ACCEPTANCE_CRITERIA,
                T.ACCEPTED_DECISION,
            ):
                self.assertFalse(ce.can_override(source, target), (source, target))

    def test_feedback_only_authoritative_once_ratified(self) -> None:
        self.assertFalse(
            ce.feedback_is_authoritative(ratified_into_accepted_decision=False)
        )
        self.assertTrue(
            ce.feedback_is_authoritative(ratified_into_accepted_decision=True)
        )


class ResolutionTableTests(unittest.TestCase):
    def test_five_outcomes_exist(self) -> None:
        self.assertEqual(
            {r.value for r in ce.Resolution},
            {
                "USE_AUTHORITATIVE",
                "REPORT_CONFLICT",
                "REPORT_AMBIGUITY",
                "TREAT_AS_INFORMATIONAL_ONLY",
                "DISREGARD_STALE",
            },
        )

    def test_authoritative_support_uses_it(self) -> None:
        self.assertIs(
            ce.resolve(supporting_types=[T.REQUIREMENT]), R.USE_AUTHORITATIVE
        )

    def test_only_informational_support_is_informational_only(self) -> None:
        self.assertIs(
            ce.resolve(supporting_types=[T.INFORMAL_DISCUSSION, T.HISTORICAL_CONTEXT]),
            R.TREAT_AS_INFORMATIONAL_ONLY,
        )

    def test_contradicting_authoritative_sources_report_conflict(self) -> None:
        self.assertIs(
            ce.resolve(
                supporting_types=[T.REQUIREMENT], contradicting_authoritative=True
            ),
            R.REPORT_CONFLICT,
        )

    def test_requirement_vs_repo_policy_reports_conflict_unless_a_contract_settles_it(
        self,
    ) -> None:
        self.assertIs(
            ce.resolve(
                supporting_types=[T.REQUIREMENT, T.REPOSITORY_POLICY],
                requirement_vs_repo_policy_conflict=True,
            ),
            R.REPORT_CONFLICT,
        )
        self.assertIs(
            ce.resolve(
                supporting_types=[T.REQUIREMENT, T.REPOSITORY_POLICY],
                requirement_vs_repo_policy_conflict=True,
                existing_contract_settles_it=True,
            ),
            R.USE_AUTHORITATIVE,
        )

    def test_vague_or_missing_requirement_reports_ambiguity(self) -> None:
        self.assertIs(
            ce.resolve(
                supporting_types=[T.REQUIREMENT], authoritative_source_is_vague=True
            ),
            R.REPORT_AMBIGUITY,
        )
        self.assertIs(
            ce.resolve(supporting_types=[], expected_requirement_missing=True),
            R.REPORT_AMBIGUITY,
        )

    def test_superseded_authoritative_source_is_stale(self) -> None:
        self.assertIs(
            ce.resolve(
                supporting_types=[T.ACCEPTED_DECISION],
                superseded_by_newer_maintainer_clarification=True,
            ),
            R.DISREGARD_STALE,
        )

    def test_only_use_authoritative_can_establish_a_finding(self) -> None:
        self.assertTrue(ce.can_establish_finding(R.USE_AUTHORITATIVE))
        for r in ce.Resolution:
            if r is not R.USE_AUTHORITATIVE:
                self.assertFalse(ce.can_establish_finding(r), r)


class AttributionTests(unittest.TestCase):
    def test_change_that_introduces_is_always_introduced(self) -> None:
        self.assertIs(
            ce.attribute_finding_origin(
                note_type=T.PRE_EXISTING_RISK_NOTE,
                corroborated_by_pre_change_code=True,
                change_introduces_or_activates=True,
            ),
            ce.FindingOrigin.INTRODUCED,
        )

    def test_corroborated_note_supports_pre_existing(self) -> None:
        self.assertIs(
            ce.attribute_finding_origin(
                note_type=T.PRE_EXISTING_RISK_NOTE,
                corroborated_by_pre_change_code=True,
                change_introduces_or_activates=False,
            ),
            ce.FindingOrigin.PRE_EXISTING,
        )

    def test_uncorroborated_note_is_unclear_not_pre_existing(self) -> None:
        self.assertIs(
            ce.attribute_finding_origin(
                note_type=T.PRE_EXISTING_RISK_NOTE,
                corroborated_by_pre_change_code=False,
                change_introduces_or_activates=False,
            ),
            ce.FindingOrigin.UNCLEAR,
        )


class FindingProvenanceShapeTests(unittest.TestCase):
    def _entry(self) -> ce.ContextualEvidenceEntry:
        return ce.ContextualEvidenceEntry(
            evidence_type=T.ACCEPTANCE_CRITERIA,
            source_name="Jira PROJECT-1234 acceptance criteria",
            note="a record is validated before every write path",
        )

    def test_no_context_evidence_renders_nothing(self) -> None:
        p = ce.FindingProvenance(code_evidence="bulk_update() persists without validate()")
        self.assertFalse(p.renders_context_evidence())
        self.assertEqual(p.render_context_evidence_field(), "")

    def test_context_evidence_renders_the_finding_template_line(self) -> None:
        p = ce.FindingProvenance(
            code_evidence="bulk_update() persists without validate()",
            context_evidence=(self._entry(),),
        )
        self.assertTrue(p.renders_context_evidence())
        rendered = p.render_context_evidence_field()
        self.assertTrue(rendered.startswith("- **Contextual evidence:** "))
        self.assertIn("acceptance_criteria", rendered)
        self.assertIn("Jira PROJECT-1234", rendered)

    def test_provenance_shape_carries_no_severity(self) -> None:
        self.assertNotIn("severity", ce.FindingProvenance.__dataclass_fields__)
        self.assertNotIn("severity", ce.ContextualEvidenceEntry.__dataclass_fields__)


class GovernanceTests(unittest.TestCase):
    def test_no_public_callable_carries_a_prohibited_capability_fragment(self) -> None:
        for name in ce.public_callables():
            for fragment in ce.PROHIBITED_CAPABILITY_NAME_FRAGMENTS:
                self.assertNotIn(fragment, name, (name, fragment))

    def test_retrieval_and_severity_fragments_are_prohibited(self) -> None:
        for fragment in ("fetch", "retrieve", "ingest", "auto_attach", "raise_severity"):
            self.assertIn(fragment, ce.PROHIBITED_CAPABILITY_NAME_FRAGMENTS)


class WorkedExampleCorpusTests(unittest.TestCase):
    def test_corpus_covers_every_resolution_outcome(self) -> None:
        covered = {ce.resolve(**c["resolve_kwargs"]) for c in WORKED_EXAMPLES}
        self.assertEqual(
            covered,
            set(ce.Resolution),
            "the worked-example corpus must exercise every resolution outcome so "
            "the induced-regression check is sensitive to each",
        )

    def test_every_design_record_example_classifies_as_documented(self) -> None:
        for case in WORKED_EXAMPLES:
            with self.subTest(case=case["name"]):
                got = ce.resolve(**case["resolve_kwargs"])
                self.assertIs(got, case["expected_resolution"])
                self.assertEqual(
                    ce.can_establish_finding(got), case["can_establish_finding"]
                )
                if "override_check" in case:
                    src, tgt, expected = case["override_check"]
                    self.assertEqual(ce.can_override(src, tgt), expected)
                if "origin" in case:
                    self.assertIs(
                        ce.attribute_finding_origin(**case["origin"]["kwargs"]),
                        case["origin"]["expected"],
                    )


class InducedRegressionTests(unittest.TestCase):
    """Mutating the model's core rules must break the corpus above — the
    corpus is only meaningful if it is sensitive to the behavior it pins."""

    def _corpus_holds(self) -> bool:
        for case in WORKED_EXAMPLES:
            got = ce.resolve(**case["resolve_kwargs"])
            if got is not case["expected_resolution"]:
                return False
            if ce.can_establish_finding(got) != case["can_establish_finding"]:
                return False
            if "override_check" in case:
                src, tgt, expected = case["override_check"]
                if ce.can_override(src, tgt) != expected:
                    return False
            if "origin" in case:
                if ce.attribute_finding_origin(
                    **case["origin"]["kwargs"]
                ) is not case["origin"]["expected"]:
                    return False
        return True

    def test_baseline_corpus_holds(self) -> None:
        self.assertTrue(self._corpus_holds())

    def test_mutant_can_override_always_true_is_caught(self) -> None:
        original = ce.can_override
        ce.can_override = lambda source, target: True  # type: ignore[assignment]
        try:
            self.assertFalse(self._corpus_holds())
        finally:
            ce.can_override = original  # type: ignore[assignment]

    def test_mutant_authority_all_authoritative_is_caught(self) -> None:
        original = ce.authority_of
        ce.authority_of = lambda t: ce.Authority.AUTHORITATIVE  # type: ignore[assignment]
        try:
            self.assertFalse(self._corpus_holds())
        finally:
            ce.authority_of = original  # type: ignore[assignment]

    def test_mutant_resolve_conflict_becomes_use_authoritative_is_caught(self) -> None:
        # Worked example 6 is a REPORT_CONFLICT corpus row, so collapsing
        # REPORT_CONFLICT into USE_AUTHORITATIVE (silently siding with the
        # higher-ranked source) must break the corpus.
        original = ce.resolve

        def mutant(**kwargs):
            got = original(**kwargs)
            return R.USE_AUTHORITATIVE if got is R.REPORT_CONFLICT else got

        ce.resolve = mutant  # type: ignore[assignment]
        try:
            self.assertFalse(self._corpus_holds())
        finally:
            ce.resolve = original  # type: ignore[assignment]

    def test_mutant_resolve_drops_stale_check_is_caught(self) -> None:
        # Worked example 8 is a DISREGARD_STALE corpus row.
        original = ce.resolve

        def mutant(**kwargs):
            kwargs = dict(kwargs)
            kwargs["superseded_by_newer_maintainer_clarification"] = False
            kwargs["contradicted_by_repo_architecture_it_predates"] = False
            return original(**kwargs)

        ce.resolve = mutant  # type: ignore[assignment]
        try:
            self.assertFalse(self._corpus_holds())
        finally:
            ce.resolve = original  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
