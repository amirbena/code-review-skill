#!/usr/bin/env python3
"""Contract coverage for the denied-capability security-event benchmark
corpus (Issue #308, depends on #299 and the relevant enforced denial from
#301/#302/#303).

The corpus is
`runtime_platform/benchmark/reference/security_event_fixtures.py`: a focused,
data-driven set of `SecurityEventCase` fixtures, one per representative
enforced denial across the mutation, sandbox, agent-spawn/delegation, and
GitHub review-action-mutation families, each constructing the
`SecurityEvent` a real denial in that family reports. Every comparison
here is a deterministic structural assertion -- event-type, classification,
correlation-field presence, and redaction-pattern absence -- never an
LLM/rubric score, per the issue's own "Do not reuse ordinary
review-quality precision/recall metrics for this corpus."

Run this module alone to exercise the whole security-event corpus
independently of the rest of the benchmark suite::

    python3 -m unittest tests.unit.benchmark.test_security_event_corpus
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from runtime_platform.benchmark.reference import security_event_fixtures as sef

MIN_CASES = 15
MAX_CASES = 40


class CorpusPresenceTests(unittest.TestCase):
    def test_corpus_is_non_trivial_and_bounded(self) -> None:
        n = len(sef.ALL_CASES)
        self.assertGreaterEqual(n, MIN_CASES, "a required case went missing")
        self.assertLessEqual(n, MAX_CASES, "corpus is growing into a bulk library")

    def test_every_case_id_is_unique(self) -> None:
        ids = [c.case_id for c in sef.ALL_CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_corpus_validates_as_a_whole(self) -> None:
        sef.validate_corpus(sef.ALL_CASES)  # must not raise


class RequiredFamilyCoverageTests(unittest.TestCase):
    """Acceptance criterion: 'Every major #299 event family has at least
    one benchmark case.'"""

    def test_every_scope_family_has_at_least_one_case(self) -> None:
        for family in sef.REQUIRED_FAMILIES:
            with self.subTest(family=family):
                self.assertTrue(sef.cases_in_family(family), f"no case in family {family!r}")


class EventTypeClosedVocabularyTests(unittest.TestCase):
    """The corpus's own closed set must not silently drift from the
    authoritative #299 taxonomy mirrored by
    scripts/security/validate_threat_model.py's PROVISIONAL_EVENT_CLASSES."""

    def test_closed_event_types_match_the_governance_script(self) -> None:
        from scripts.security import validate_threat_model as vtm

        self.assertEqual(sef.CLOSED_EVENT_TYPES, vtm.PROVISIONAL_EVENT_CLASSES)


class PerCaseOutcomeTests(unittest.TestCase):
    """For every case: the built event matches its declared expectation
    field-by-field, is individually valid (closed vocabulary, redaction),
    and every correlation-tagged case actually carries a correlation id."""

    def test_every_case_builds_a_valid_matching_event(self) -> None:
        for case in sef.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                event = case.build()
                sef.validate_event(event)  # must not raise
                self.assertEqual(event.event_type, case.expected_event_type)
                self.assertEqual(event.classification, case.expected_classification)
                self.assertEqual(event.invocation_id, sef._INVOCATION_ID)

    def test_correlation_tagged_cases_carry_a_correlation_id(self) -> None:
        for case in sef.ALL_CASES:
            if not case.requires_parent_child_correlation:
                continue
            with self.subTest(case_id=case.case_id):
                event = case.build()
                self.assertTrue(
                    event.parent_agent_id or event.child_agent_id,
                    f"{case.case_id}: declares parent/child correlation but carries neither field",
                )

    def test_non_correlation_cases_carry_no_agent_correlation(self) -> None:
        for case in sef.ALL_CASES:
            if case.requires_parent_child_correlation:
                continue
            with self.subTest(case_id=case.case_id):
                event = case.build()
                self.assertIsNone(event.parent_agent_id)
                self.assertIsNone(event.child_agent_id)


class DeterminismTests(unittest.TestCase):
    """Acceptance criterion: 'Same enforced denial produces the same
    event type/classification deterministically.' Building a case twice
    (or in a different corpus-iteration order) must yield a byte-for-byte
    identical event -- no wall-clock timestamp, random id, or hidden
    global state may leak in."""

    def test_building_a_case_twice_is_byte_for_byte_identical(self) -> None:
        for case in sef.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                self.assertEqual(case.build(), case.build())

    def test_building_every_case_twice_in_reverse_order_is_still_identical(self) -> None:
        forward = [case.build() for case in sef.ALL_CASES]
        backward = [case.build() for case in reversed(sef.ALL_CASES)]
        backward.reverse()
        self.assertEqual(forward, backward)


class RedactionTests(unittest.TestCase):
    """Acceptance criterion: 'Event payload redaction is asserted.' No
    field may ever carry a raw prompt, token, secret, credential value,
    full patch body, or unnecessary repository content."""

    def test_no_case_event_contains_forbidden_content(self) -> None:
        for case in sef.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                event = case.build()
                sef.validate_event(event)  # redaction check lives here; must not raise

    def test_the_schema_has_no_field_for_a_secret_or_patch_body(self) -> None:
        forbidden_field_names = {
            "secret",
            "token",
            "credential",
            "password",
            "prompt",
            "patch_body",
            "full_patch",
            "file_contents",
        }
        actual_field_names = {f for f in sef.SecurityEvent.__dataclass_fields__}
        self.assertFalse(
            forbidden_field_names & actual_field_names,
            "SecurityEvent must never grow a field shaped like a secret or a full payload",
        )


class ObservationalOnlyTests(unittest.TestCase):
    """Acceptance criterion: 'Event recording is proven observational
    only: review findings/severity/verdict are unchanged.' Recording a
    real event, recording no event, and disabling recording altogether
    must all leave a review outcome byte-for-byte identical."""

    def _sample_outcome(self) -> sef.ReviewOutcome:
        return sef.ReviewOutcome(
            findings=("P1: missing null check", "P2: duplicated branch logic"),
            severity_summary="1xP1, 1xP2",
            verdict="CHANGES REQUIRED",
        )

    def test_recording_enabled_vs_disabled_never_changes_the_outcome(self) -> None:
        outcome = self._sample_outcome()
        for case in sef.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                event = case.build()
                enabled = sef.record_event(outcome, event, recording_enabled=True)
                disabled = sef.record_event(outcome, event, recording_enabled=False)
                self.assertEqual(outcome, enabled)
                self.assertEqual(outcome, disabled)
                self.assertEqual(enabled, disabled)

    def test_recording_no_event_at_all_never_changes_the_outcome(self) -> None:
        outcome = self._sample_outcome()
        self.assertEqual(outcome, sef.record_event(outcome, None, recording_enabled=True))
        self.assertEqual(outcome, sef.record_event(outcome, None, recording_enabled=False))


class ThreatScenarioAndEnforcementOwnerTraceabilityTests(unittest.TestCase):
    """Acceptance criterion: 'Cases reference the corresponding #300
    threat scenario and #301/#302/#303 enforcement owner.' The GitHub
    review-action-authorization boundary (AUTH-014) pre-dates the #298
    epic and is owned by none of #301/#302/#303 (see AUTH-014's own
    catalog entry, "not part of #301/#305's code-mutation scope"), so its
    cases cite the literal 'existing' instead."""

    def test_every_case_cites_at_least_one_threat_scenario(self) -> None:
        for case in sef.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                self.assertTrue(case.threat_scenario_ids)

    def test_every_case_cites_a_real_enforcement_owner(self) -> None:
        for case in sef.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                self.assertIn(case.enforcement_owner, {"#301", "#302", "#303", "existing"})

    def test_lookup_by_threat_scenario_finds_the_case(self) -> None:
        cases = sef.cases_for_threat_scenario("AUTH-001")
        self.assertTrue(cases)
        self.assertTrue(all("AUTH-001" in c.threat_scenario_ids for c in cases))


class MalformedFixtureRejectionTests(unittest.TestCase):
    """`validate_case`/`validate_event`/`validate_corpus` fail closed on
    a deliberately broken fixture, built from a real, passing case via
    `dataclasses.replace`."""

    def setUp(self) -> None:
        self.base_case = sef.ALL_CASES[0]
        self.base_event = self.base_case.build()

    def test_rejects_unknown_event_type(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_case(replace(self.base_case, expected_event_type="DENIED_MADE_UP"))

    def test_rejects_unknown_classification(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_case(replace(self.base_case, expected_classification="somewhat_denied"))

    def test_rejects_unknown_family(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_case(replace(self.base_case, family="not_a_real_family"))

    def test_rejects_empty_threat_scenario_ids(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_case(replace(self.base_case, threat_scenario_ids=()))

    def test_accepts_an_existing_policy_citation_in_place_of_a_catalog_id(self) -> None:
        sef.validate_case(
            replace(
                self.base_case,
                threat_scenario_ids=("existing:shared/policies/runtime-validation.md",),
            )
        )  # must not raise -- SEC-EVT-010/012 use exactly this form

    def test_rejects_a_malformed_existing_citation(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_case(replace(self.base_case, threat_scenario_ids=("existing:",)))

    def test_rejects_malformed_threat_scenario_id(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_case(replace(self.base_case, threat_scenario_ids=("NOT-A-VALID-ID",)))

    def test_rejects_unrecognized_enforcement_owner(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_case(replace(self.base_case, enforcement_owner="issue 301"))

    def test_rejects_duplicate_case_ids(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_corpus((self.base_case, self.base_case))

    def test_rejects_corpus_missing_a_required_family(self) -> None:
        only_one_family = tuple(c for c in sef.ALL_CASES if c.family == sef.ALL_CASES[0].family)
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_corpus(only_one_family)

    def test_rejects_event_with_unknown_event_type(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_event(replace(self.base_event, event_type="DENIED_MADE_UP"))

    def test_rejects_event_with_unknown_classification(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_event(replace(self.base_event, classification="somewhat_denied"))

    def test_rejects_event_with_empty_invocation_id(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_event(replace(self.base_event, invocation_id=""))

    def test_rejects_event_with_negative_sequence_position(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_event(replace(self.base_event, sequence_position=-1))

    def test_rejects_event_carrying_a_credential_looking_value(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_event(replace(self.base_event, denial_reason="leaked token=ghp_abcdef1234567890"))

    def test_rejects_event_carrying_an_oversized_field(self) -> None:
        with self.assertRaises(sef.SecurityEventFixtureError):
            sef.validate_event(replace(self.base_event, denial_reason="x" * 500))


if __name__ == "__main__":
    unittest.main()
