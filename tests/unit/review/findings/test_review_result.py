#!/usr/bin/env python3
"""Behavioral coverage for the review result schema (Issue #67).

Contract: docs/review-result/review-result-model.md and
review-result.schema.json. Focus: the example validates and is consistent
with the canonical owners; every schema enum and the identity token format
stay pinned to the reference models that mirror those owners; the schema
encodes no decision/identity/finding rule of its own; and each way a result
can be wrong -- shape or cross-field -- is rejected.

Run with:
    python3 -m unittest tests.unit.review.findings.test_review_result
"""

from __future__ import annotations

import copy
import unittest

from tests.reference.review import decision_semantics as ds
from tests.reference.review import finding_confidence as fc
from tests.reference.review import finding_contract as contract
from tests.reference.review import finding_identity as fi
from tests.reference.review import review_result as rr

SCHEMA = rr.load_schema()
FINDING_SCHEMA = SCHEMA["definitions"]["finding"]

# Inputs that reproduce the two identities in the example document.
EXAMPLE_IDENTITY_INPUTS = {
    "F1": dict(
        repository="acme/payments",
        location="src/payments/retry.py:88",
        symbol="charge_with_retry",
        behavioral_claim_text=(
            "the retry loop swallows TimeoutError, so a charge that never "
            "completed is reported as successful"
        ),
        anchor_fragment="except TimeoutError: continue",
        defect_kind_text="swallowed-exception",
    ),
    "F2": dict(
        repository="acme/payments",
        location="tests/unit/payments/test_retry.py",
        behavioral_claim_text="no test covers the timeout path, so the retry regression is not caught",
        anchor_fragment="def test_charge_retries_on_failure",
        defect_kind_text="missing-test-coverage",
    ),
}


def _example() -> dict:
    return copy.deepcopy(rr.load_example())


def _clean_result() -> dict:
    result = _example()
    result["findings"] = []
    result["counts"] = {"p0": 0, "p1": 0, "p2": 0}
    result["decision"] = {"derived": "clean", "outcome": "clean"}
    return result


class ExampleTests(unittest.TestCase):
    def test_example_validates_against_schema_and_owners(self) -> None:
        self.assertEqual(rr.validate_review_result(rr.load_example()), ())

    def test_example_identities_are_the_canonical_minted_values(self) -> None:
        by_id = {f["id"]: f["identity"] for f in rr.load_example()["findings"]}
        for finding_id, inputs in EXAMPLE_IDENTITY_INPUTS.items():
            descriptor = fi.build_descriptor(**inputs)
            with self.subTest(finding=finding_id):
                self.assertEqual(by_id[finding_id]["stable_id"], fi.mint_identity(descriptor))
                self.assertEqual(by_id[finding_id]["matching_eligible"], fi.is_matchable(descriptor))

    def test_clean_review_without_findings_is_valid(self) -> None:
        self.assertEqual(rr.validate_review_result(_clean_result()), ())

    def test_p2_only_review_is_clean_and_keeps_its_finding(self) -> None:
        result = _example()
        result["findings"] = [f for f in result["findings"] if f["severity"] == "P2"]
        result["counts"] = {"p0": 0, "p1": 0, "p2": 1}
        result["decision"] = {"derived": "clean", "outcome": "clean"}
        self.assertEqual(rr.validate_review_result(result), ())

    def test_incomplete_coverage_overrides_a_blocking_outcome(self) -> None:
        result = _example()
        result["coverage"] = "incomplete"
        result["decision"] = {"derived": "blocking", "outcome": "incomplete"}
        self.assertEqual(rr.validate_review_result(result), ())

    def test_uncommitted_local_review_uses_null_reviewed_head(self) -> None:
        result = _clean_result()
        result["skill"] = "local-code-review"
        result["reviewed_state"].update(
            base_sha=None, merge_base_sha=None, reviewed_head_sha=None, reviewer_identity=None
        )
        self.assertEqual(rr.validate_review_result(result), ())

    def test_distinct_findings_may_share_a_minted_identity(self) -> None:
        common = dict(
            repository="acme/payments",
            location="src/payments/retry.py:88",
            anchor_fragment="except TimeoutError: continue",
        )
        first = fi.build_descriptor(**common, behavioral_claim_text="swallows the timeout")
        second = fi.build_descriptor(**common, behavioral_claim_text="logs no error on failure")
        self.assertEqual(fi.mint_identity(first), fi.mint_identity(second))
        self.assertFalse(fi.is_matchable(first) or fi.is_matchable(second))

        result = _example()
        shared = {"stable_id": fi.mint_identity(first), "matching_eligible": False}
        for finding in result["findings"]:
            finding["identity"] = dict(shared)
        self.assertEqual(rr.validate_review_result(result), ())

    def test_escalated_full_review_keeps_its_prior_reviewed_sha(self) -> None:
        result = _example()
        result["reviewed_state"]["prior_reviewed_sha"] = "a" * 40
        self.assertEqual(rr.validate_review_result(result), ())


class SchemaDriftTests(unittest.TestCase):
    """Each schema enum equals the reference model that mirrors its owner."""

    def test_severity_enum(self) -> None:
        self.assertEqual(
            FINDING_SCHEMA["properties"]["severity"]["enum"], [s.value for s in ds.Severity]
        )

    def test_confidence_enum(self) -> None:
        self.assertEqual(
            FINDING_SCHEMA["properties"]["confidence"]["enum"], [c.value for c in fc.Confidence]
        )

    def test_runtime_validation_enum(self) -> None:
        self.assertEqual(
            set(FINDING_SCHEMA["properties"]["runtime_validation"]["enum"]), set(fc.RUNTIME_STATES)
        )

    def test_decision_enums(self) -> None:
        decision = SCHEMA["properties"]["decision"]["properties"]
        self.assertEqual(set(decision["derived"]["enum"]), set(rr.DECISION_CODES.values()))
        self.assertEqual(
            set(decision["outcome"]["enum"]), {*rr.DECISION_CODES.values(), rr.INCOMPLETE_OUTCOME}
        )
        self.assertEqual(set(rr.DECISION_CODES), set(ds.Decision))

    def test_coverage_enum(self) -> None:
        self.assertEqual(SCHEMA["properties"]["coverage"]["enum"], ["complete", "incomplete"])

    def test_mandatory_finding_core_is_required(self) -> None:
        self.assertLessEqual(set(contract.MANDATORY_CORE), set(FINDING_SCHEMA["required"]))

    def test_identity_token_shape_matches_the_minted_identity(self) -> None:
        errors = rr.validate_against_schema(
            fi.mint_identity(fi.build_descriptor(**EXAMPLE_IDENTITY_INPUTS["F1"])),
            FINDING_SCHEMA["properties"]["identity"]["properties"]["stable_id"],
        )
        self.assertEqual(errors, ())

    def test_schema_version_matches_the_reference(self) -> None:
        self.assertEqual(SCHEMA["properties"]["schema_version"]["const"], rr.SCHEMA_VERSION)


class SchemaRestatesNoSemanticsTests(unittest.TestCase):
    """Acceptance: the schema is shape only. Conditional keywords are how a
    derivation rule would be duplicated into it, so none may appear."""

    FORBIDDEN = {"if", "then", "else", "allOf", "anyOf", "oneOf", "not", "dependencies"}

    def _keys(self, node: object) -> set[str]:
        found: set[str] = set()
        if isinstance(node, dict):
            for key, value in node.items():
                found.add(key)
                if key not in ("properties", "definitions"):
                    found |= self._keys(value)
                else:
                    for sub in value.values():
                        found |= self._keys(sub)
        elif isinstance(node, list):
            for item in node:
                found |= self._keys(item)
        return found

    def test_no_conditional_keywords(self) -> None:
        self.assertEqual(self._keys(SCHEMA) & self.FORBIDDEN, set())

    def test_every_object_rejects_unknown_keys(self) -> None:
        def walk(node: object, path: str) -> None:
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False, path)
                for key, value in node.items():
                    walk(value, f"{path}/{key}")

        walk(SCHEMA, "#")


class ShapeRejectionTests(unittest.TestCase):
    def assertRejected(self, result: dict, fragment: str) -> None:
        errors = rr.validate_review_result(result)
        self.assertTrue(errors, f"expected a rejection mentioning {fragment!r}")
        self.assertTrue(any(fragment in e for e in errors), f"{fragment!r} not in {errors}")

    def test_missing_top_level_field(self) -> None:
        result = _example()
        del result["coverage"]
        self.assertRejected(result, "missing required property 'coverage'")

    def test_unknown_top_level_field(self) -> None:
        result = _example()
        result["extra"] = 1
        self.assertRejected(result, "unexpected property 'extra'")

    def test_unknown_finding_field(self) -> None:
        result = _example()
        result["findings"][0]["remediation"] = "x"
        self.assertRejected(result, "unexpected property 'remediation'")

    def test_severity_outside_the_enum(self) -> None:
        result = _example()
        result["findings"][0]["severity"] = "P3"
        self.assertRejected(result, "not in enum")

    def test_numeric_severity_is_not_accepted(self) -> None:
        result = _example()
        result["findings"][0]["severity"] = 1
        self.assertRejected(result, "expected type")

    def test_legacy_decision_label_is_not_a_machine_code(self) -> None:
        result = _example()
        result["decision"]["derived"] = "CHANGES REQUIRED"
        self.assertRejected(result, "not in enum")

    def test_malformed_sha(self) -> None:
        result = _example()
        result["reviewed_state"]["reviewed_head_sha"] = "not-a-sha"
        self.assertRejected(result, "does not match")

    def test_missing_mandatory_finding_field(self) -> None:
        for name in contract.MANDATORY_CORE:
            result = _example()
            del result["findings"][0][name]
            with self.subTest(field=name):
                self.assertRejected(result, f"missing required property {name!r}")

    def test_optional_finding_field_is_omitted_never_null(self) -> None:
        result = _example()
        result["findings"][0]["follow_up"] = None
        self.assertRejected(result, "expected type")

    def test_canonical_defaults_are_explicit(self) -> None:
        for name in ("confidence", "runtime_validation", "fix_location_resolved"):
            result = _example()
            del result["findings"][0][name]
            with self.subTest(field=name):
                self.assertRejected(result, f"missing required property {name!r}")

    def test_review_level_state_fact_cannot_be_omitted(self) -> None:
        result = _example()
        del result["reviewed_state"]["prior_reviewed_sha"]
        self.assertRejected(result, "missing required property 'prior_reviewed_sha'")

    def test_affected_locations_needs_at_least_two_sites(self) -> None:
        result = _example()
        result["findings"][0]["affected_locations"] = [{"location": "a.py:1", "note": "n"}]
        self.assertRejected(result, "fewer than 2 items")

    def test_defect_kind_must_be_kebab_case(self) -> None:
        result = _example()
        result["findings"][0]["defect_kind"] = "Swallowed Exception"
        self.assertRejected(result, "does not match")

    def test_negative_count(self) -> None:
        result = _example()
        result["counts"]["p2"] = -1
        self.assertRejected(result, "below minimum")

    def test_boolean_is_not_an_integer_count(self) -> None:
        result = _example()
        result["counts"]["p0"] = True
        self.assertRejected(result, "expected type")


class ConsistencyRejectionTests(unittest.TestCase):
    def assertRejected(self, result: dict, fragment: str) -> None:
        self.assertEqual(rr.validate_against_schema(result), (), "mutation must stay schema-valid")
        errors = rr.validate_review_result(result)
        self.assertTrue(any(fragment in e for e in errors), f"{fragment!r} not in {errors}")

    def test_counts_must_tally_findings(self) -> None:
        result = _example()
        result["counts"]["p1"] = 0
        self.assertRejected(result, "$.counts")

    def test_clean_decision_cannot_carry_a_blocking_finding(self) -> None:
        result = _example()
        result["decision"] = {"derived": "clean", "outcome": "clean"}
        self.assertRejected(result, "$.decision.derived")

    def test_blocking_decision_cannot_rest_on_p2_alone(self) -> None:
        result = _example()
        result["findings"] = [f for f in result["findings"] if f["severity"] == "P2"]
        result["counts"] = {"p0": 0, "p1": 0, "p2": 1}
        self.assertRejected(result, "$.decision.derived")

    def test_incomplete_coverage_cannot_present_as_clean(self) -> None:
        result = _clean_result()
        result["coverage"] = "incomplete"
        self.assertRejected(result, "$.decision.outcome")

    def test_complete_coverage_cannot_present_as_incomplete(self) -> None:
        result = _example()
        result["decision"]["outcome"] = "incomplete"
        self.assertRejected(result, "$.decision.outcome")

    def test_duplicate_finding_ids(self) -> None:
        result = _example()
        result["findings"][1]["id"] = result["findings"][0]["id"]
        self.assertRejected(result, "finding ids are not unique")

    def test_prior_reviewed_sha_cannot_name_the_head(self) -> None:
        result = _example()
        result["reviewed_state"]["prior_reviewed_sha"] = result["reviewed_state"]["reviewed_head_sha"]
        self.assertRejected(result, "prior_reviewed_sha")

    def test_runtime_confirmed_requires_confirmed_confidence(self) -> None:
        result = _example()
        result["findings"][0]["runtime_validation"] = "runtime-confirmed"
        self.assertRejected(result, "runtime-confirmed requires confidence 'confirmed'")

    def test_attempted_inconclusive_rules_out_credible(self) -> None:
        result = _example()
        result["findings"][0]["runtime_validation"] = "attempted-inconclusive"
        result["findings"][0]["confidence"] = "credible"
        self.assertRejected(result, "attempted-inconclusive allows only")


class SeverityIsTheOnlyDecisionInputTests(unittest.TestCase):
    """Optional provenance never moves the derived decision (finding.md:
    none of these fields is a severity input)."""

    def test_provenance_fields_do_not_change_the_derived_code(self) -> None:
        base = rr.derived_decision_code(["P1", "P2"])
        result = _example()
        for finding in result["findings"]:
            finding["confidence"] = "insufficient-context"
            finding["runtime_validation"] = "reasoned"
            finding["contextual_evidence"] = ["requirement: r"]
            finding["capability"] = "security-deepening"
        self.assertEqual(rr.validate_review_result(result), ())
        self.assertEqual(result["decision"]["derived"], base)


if __name__ == "__main__":
    unittest.main()
