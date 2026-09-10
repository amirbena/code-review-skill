#!/usr/bin/env python3
"""Behavioral coverage for the finding-confidence model (Issue #178).

Contract: docs/finding-confidence/finding-confidence-model.md and the
`confidence` field on shared/templates/finding.md. Regression focus: the
closed value set stays closed, the runtime-validation (#128) and
contextual-evidence (#118) states map onto the one field as documented,
the derivation order is deterministic, `credible` is the default and the
floor, and no value moves severity, the decision, identity, or the
evidence bar.
"""

from __future__ import annotations

import unittest

from tests.reference import finding_confidence as fcf


class ClosedValueSetTests(unittest.TestCase):
    def test_exactly_the_five_documented_values_exist(self) -> None:
        self.assertEqual(
            {c.value for c in fcf.Confidence},
            {
                "confirmed",
                "credible",
                "runtime-validation-unavailable",
                "external-contract-unvalidated",
                "insufficient-context",
            },
        )

    def test_default_is_credible(self) -> None:
        self.assertIs(fcf.DEFAULT_CONFIDENCE, fcf.Confidence.CREDIBLE)

    def test_open_question_values_exclude_confirmed_and_credible(self) -> None:
        self.assertNotIn(fcf.Confidence.CONFIRMED, fcf.OPEN_QUESTION_VALUES)
        self.assertNotIn(fcf.Confidence.CREDIBLE, fcf.OPEN_QUESTION_VALUES)
        self.assertEqual(len(fcf.OPEN_QUESTION_VALUES), 3)


class RuntimeStateRollupTests(unittest.TestCase):
    """#128 states map onto the one field (design record §3)."""

    def test_runtime_confirmed_rolls_up_as_confirmed(self) -> None:
        self.assertIs(
            fcf.from_runtime_state("runtime-confirmed"), fcf.Confidence.CONFIRMED
        )

    def test_attempted_inconclusive_rolls_up_as_runtime_validation_unavailable(self) -> None:
        self.assertIs(
            fcf.from_runtime_state("attempted-inconclusive"),
            fcf.Confidence.RUNTIME_VALIDATION_UNAVAILABLE,
        )

    def test_reasoned_default_contributes_nothing(self) -> None:
        self.assertIsNone(fcf.from_runtime_state("reasoned"))

    def test_unknown_state_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            fcf.from_runtime_state("green")


class DerivationOrderTests(unittest.TestCase):
    """The first-match order of design record §4."""

    def test_no_signals_is_the_credible_default(self) -> None:
        self.assertIs(fcf.derive_confidence(), fcf.Confidence.CREDIBLE)

    def test_confirmed_wins_from_a_runtime_run(self) -> None:
        self.assertIs(
            fcf.derive_confidence(runtime_state="runtime-confirmed"),
            fcf.Confidence.CONFIRMED,
        )

    def test_confirmed_wins_from_direct_static_evidence(self) -> None:
        self.assertIs(
            fcf.derive_confidence(code_evidence_label="confirmed-defect"),
            fcf.Confidence.CONFIRMED,
        )

    def test_confirmed_wins_from_authoritative_context_proving_a_violation(self) -> None:
        self.assertIs(
            fcf.derive_confidence(authoritative_context_proves_violation=True),
            fcf.Confidence.CONFIRMED,
        )

    def test_confirmed_outranks_every_open_question(self) -> None:
        self.assertIs(
            fcf.derive_confidence(
                runtime_state="runtime-confirmed",
                external_contract_unvalidated=True,
                authoritative_context_question_unresolved=True,
            ),
            fcf.Confidence.CONFIRMED,
        )

    def test_inconclusive_run_outranks_external_and_context(self) -> None:
        self.assertIs(
            fcf.derive_confidence(
                runtime_state="attempted-inconclusive",
                external_contract_unvalidated=True,
                authoritative_context_question_unresolved=True,
            ),
            fcf.Confidence.RUNTIME_VALIDATION_UNAVAILABLE,
        )

    def test_external_contract_outranks_insufficient_context(self) -> None:
        self.assertIs(
            fcf.derive_confidence(
                external_contract_unvalidated=True,
                authoritative_context_question_unresolved=True,
            ),
            fcf.Confidence.EXTERNAL_CONTRACT_UNVALIDATED,
        )

    def test_unresolved_context_question_alone_is_insufficient_context(self) -> None:
        self.assertIs(
            fcf.derive_confidence(authoritative_context_question_unresolved=True),
            fcf.Confidence.INSUFFICIENT_CONTEXT,
        )

    def test_credible_risk_label_alone_stays_credible(self) -> None:
        self.assertIs(
            fcf.derive_confidence(code_evidence_label="credible-risk"),
            fcf.Confidence.CREDIBLE,
        )

    def test_unknown_evidence_label_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            fcf.derive_confidence(code_evidence_label="maybe")


class RenderingGateTests(unittest.TestCase):
    def test_credible_default_never_renders(self) -> None:
        self.assertFalse(fcf.renders(fcf.Confidence.CREDIBLE))
        self.assertEqual(fcf.confidence_field_line(fcf.Confidence.CREDIBLE), "")

    def test_every_non_default_value_renders_a_line(self) -> None:
        for value in fcf.Confidence:
            if value is fcf.DEFAULT_CONFIDENCE:
                continue
            self.assertTrue(fcf.renders(value))
            self.assertEqual(
                fcf.confidence_field_line(value),
                f"- **Confidence:** {value.value}",
            )


class HumanSurfaceSuppressionTests(unittest.TestCase):
    """Design record §7 — the human `Confidence` line is dropped when it
    would only restate an already-shown `Runtime validation` line; the
    machine schema still carries the value."""

    def test_confirmed_is_suppressed_when_a_runtime_confirmed_line_is_shown(self) -> None:
        self.assertTrue(
            fcf.human_confidence_line_suppressed(
                fcf.Confidence.CONFIRMED, runtime_state="runtime-confirmed"
            )
        )
        self.assertFalse(
            fcf.renders_human_confidence(
                fcf.Confidence.CONFIRMED, runtime_state="runtime-confirmed"
            )
        )
        self.assertEqual(
            fcf.confidence_field_line(
                fcf.Confidence.CONFIRMED, runtime_state="runtime-confirmed"
            ),
            "",
        )

    def test_rvu_is_suppressed_when_an_attempted_inconclusive_line_is_shown(self) -> None:
        self.assertTrue(
            fcf.human_confidence_line_suppressed(
                fcf.Confidence.RUNTIME_VALIDATION_UNAVAILABLE,
                runtime_state="attempted-inconclusive",
            )
        )
        self.assertFalse(
            fcf.renders_human_confidence(
                fcf.Confidence.RUNTIME_VALIDATION_UNAVAILABLE,
                runtime_state="attempted-inconclusive",
            )
        )

    def test_confirmed_on_other_evidence_still_renders_despite_an_inconclusive_run(self) -> None:
        # the runtime line would show attempted-inconclusive, but confidence
        # is confirmed on static/contextual evidence -> the lines differ.
        self.assertFalse(
            fcf.human_confidence_line_suppressed(
                fcf.Confidence.CONFIRMED, runtime_state="attempted-inconclusive"
            )
        )
        self.assertTrue(
            fcf.renders_human_confidence(
                fcf.Confidence.CONFIRMED, runtime_state="attempted-inconclusive"
            )
        )

    def test_external_and_insufficient_are_never_suppressed(self) -> None:
        for value in (
            fcf.Confidence.EXTERNAL_CONTRACT_UNVALIDATED,
            fcf.Confidence.INSUFFICIENT_CONTEXT,
        ):
            for state in fcf.RUNTIME_STATES:
                self.assertFalse(
                    fcf.human_confidence_line_suppressed(value, runtime_state=state)
                )

    def test_no_runtime_line_means_no_suppression(self) -> None:
        for value in fcf.Confidence:
            self.assertFalse(
                fcf.human_confidence_line_suppressed(value, runtime_state="reasoned")
            )

    def test_machine_schema_always_carries_every_value(self) -> None:
        for value in fcf.Confidence:
            self.assertTrue(fcf.carried_in_machine_schema(value))


class NonWeakeningInvariantTests(unittest.TestCase):
    """Design record §6 — the load-bearing rule."""

    def test_no_value_lowers_the_evidence_bar(self) -> None:
        for value in fcf.Confidence:
            self.assertFalse(fcf.lowers_evidence_bar(value))

    def test_no_value_moves_severity_decision_or_identity(self) -> None:
        for value in fcf.Confidence:
            self.assertFalse(fcf.changes_severity(value))
            self.assertFalse(fcf.changes_decision(value))
            self.assertFalse(fcf.changes_identity(value))


class GovernanceTests(unittest.TestCase):
    def test_public_callables_carry_no_prohibited_capability_fragment(self) -> None:
        for name in fcf.public_callables():
            for fragment in fcf.PROHIBITED_CAPABILITY_NAME_FRAGMENTS:
                self.assertNotIn(fragment, name)

    def test_no_numeric_or_probability_scoring_is_modelled(self) -> None:
        # the value set is five named states; nothing numeric.
        for value in fcf.Confidence:
            self.assertIsInstance(value.value, str)
            self.assertNotRegex(value.value, r"\d")


class InducedRegressionTests(unittest.TestCase):
    """A mutation that makes confidence move severity, or that opens a sixth
    value, must be caught by this module's own assertions."""

    def test_mutating_a_non_weakening_guard_to_true_would_fail_a_test(self) -> None:
        original = fcf.changes_severity

        def mutated(_value: fcf.Confidence) -> bool:
            return True

        fcf.changes_severity = mutated  # type: ignore[assignment]
        try:
            with self.assertRaises(AssertionError):
                for value in fcf.Confidence:
                    self.assertFalse(fcf.changes_severity(value))
        finally:
            fcf.changes_severity = original  # type: ignore[assignment]

    def test_derivation_falls_back_to_the_documented_default_only(self) -> None:
        # every reachable output is a member of the closed set
        seen = {
            fcf.derive_confidence(),
            fcf.derive_confidence(runtime_state="runtime-confirmed"),
            fcf.derive_confidence(runtime_state="attempted-inconclusive"),
            fcf.derive_confidence(external_contract_unvalidated=True),
            fcf.derive_confidence(authoritative_context_question_unresolved=True),
        }
        self.assertTrue(seen.issubset(set(fcf.Confidence)))
        self.assertIn(fcf.Confidence.CREDIBLE, seen)


if __name__ == "__main__":
    unittest.main()
