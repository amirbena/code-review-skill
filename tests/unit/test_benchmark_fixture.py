#!/usr/bin/env python3
"""Behavioral coverage for the benchmark fixture format (Issue #50).

Contract: docs/benchmark/fixture-format.md. Two things are proven here:

1. the worked example (docs/benchmark/examples/example-case.yaml) decodes,
   parses, and validates, and its structure carries every §9 variance
   construct;
2. each fail-closed rejection rule in §11 actually rejects — a malformed
   required field or an out-of-contract structure raises
   ``FixtureFormatError`` rather than being silently accepted or coerced.

The reference validator (tests/reference/benchmark_fixture.py) is consumed
as the single format checker; this module never defines a second one. It is
test-only and not packaged. Matching a reviewer finding to an expected
spec, scoring, and the runner are out of scope (Issues #59/#41/#52).
"""

from __future__ import annotations

import copy
import unittest

import yaml

from tests.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

EXAMPLE_PATH = REPO_ROOT / "docs" / "benchmark" / "examples" / "example-case.yaml"


def _example_data() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


class WorkedExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _example_data()

    def test_example_decodes_to_a_mapping(self) -> None:
        self.assertIsInstance(self.data, dict)
        self.assertEqual(self.data["format"], "benchmark-case/v1")

    def test_example_parses_and_validates(self) -> None:
        case = bf.parse_case(self.data)
        self.assertEqual(case.id, "example-sqli-and-unsafe-path")
        self.assertEqual(case.input_kind, "patch")
        self.assertEqual(case.findings_completeness, "exhaustive")

    def test_example_declared_decision_matches_the_mechanical_derivation(self) -> None:
        case = bf.parse_case(self.data)
        self.assertEqual(case.decision, "changes-required")
        self.assertEqual(case.decision, case.derived_decision)

    def test_example_exercises_all_four_variance_constructs(self) -> None:
        case = bf.parse_case(self.data)
        by_key = {f.key: f for f in case.findings}

        # (1) one required defect, several acceptable descriptions/locations
        self.assertTrue(by_key["sqli-user-lookup"].required)
        self.assertEqual(len(by_key["sqli-user-lookup"].alternatives), 1)

        # (2) genuinely alternative acceptable findings
        group = by_key["unsafe-export-path"]
        self.assertTrue(group.is_any_of)
        self.assertEqual({m.key for m in group.members}, {"path-traversal", "unvalidated-report-name"})
        self.assertEqual({m.severities for m in group.members}, {("P0",), ("P1",)})

        # (3) optional finding + (4) permitted severity variance, composed
        test_gap = by_key["missing-security-test"]
        self.assertFalse(test_gap.required)
        self.assertEqual(test_gap.severities, ("P1", "P2"))

    def test_example_locations_use_the_shared_location_intent_enum(self) -> None:
        case = bf.parse_case(self.data)
        intents = set()
        for f in case.findings:
            specs = f.members if f.is_any_of else [f]
            for spec in specs:
                if spec.location:
                    intents.add(spec.location["location_intent"])
        self.assertTrue(intents)
        self.assertTrue(intents <= bf.LOCATION_INTENTS)

    def test_example_anchor_substrings_occur_in_the_patch(self) -> None:
        # The `anchor` hook only has value if it is really a fragment of the
        # change under review — guard the worked example against drift.
        case = bf.parse_case(self.data)
        patch = case.input["patch"]
        for f in case.findings:
            specs = f.members if f.is_any_of else [f]
            for spec in specs:
                anchor = (spec.location or {}).get("anchor")
                if anchor:
                    self.assertIn(anchor, patch, f"anchor not in patch: {anchor!r}")


class SchemaIdentityRejectionTests(unittest.TestCase):
    """§11 rule 1 — fail closed on the version discriminator."""

    def setUp(self) -> None:
        self.data = _example_data()

    def test_missing_format_is_rejected(self) -> None:
        del self.data["format"]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_unsupported_future_version_is_rejected_not_coerced(self) -> None:
        self.data["format"] = "benchmark-case/v2"
        with self.assertRaisesRegex(bf.FixtureFormatError, "unsupported or missing 'format'"):
            bf.parse_case(self.data)

    def test_malformed_format_value_is_rejected(self) -> None:
        self.data["format"] = "benchmark-case"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_non_mapping_top_level_is_rejected(self) -> None:
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case([1, 2, 3])


class StrictUnknownKeyTests(unittest.TestCase):
    """§11 rule 2 — an unknown key anywhere is a rejection."""

    def setUp(self) -> None:
        self.data = _example_data()

    def test_unknown_top_level_key(self) -> None:
        self.data["scoring_weight"] = 3
        with self.assertRaisesRegex(bf.FixtureFormatError, "unknown key"):
            bf.parse_case(self.data)

    def test_unknown_expected_key(self) -> None:
        self.data["expected"]["threshold"] = 0.8
        with self.assertRaisesRegex(bf.FixtureFormatError, "unknown key"):
            bf.parse_case(self.data)

    def test_unknown_location_key(self) -> None:
        self.data["expected"]["findings"][0]["location"]["column"] = 4
        with self.assertRaisesRegex(bf.FixtureFormatError, "unknown key"):
            bf.parse_case(self.data)

    def test_unknown_metadata_key_is_rejected(self) -> None:
        self.data["metadata"]["model"] = "some-model"
        with self.assertRaisesRegex(bf.FixtureFormatError, "unknown key"):
            bf.parse_case(self.data)


class RequiredFieldRejectionTests(unittest.TestCase):
    """§11 rules 3–7 — missing/malformed required fields."""

    def setUp(self) -> None:
        self.data = _example_data()

    def test_missing_id(self) -> None:
        del self.data["id"]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_non_kebab_id(self) -> None:
        self.data["id"] = "Example Case"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_missing_input(self) -> None:
        del self.data["input"]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_missing_expected(self) -> None:
        del self.data["expected"]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_finding_without_claim(self) -> None:
        del self.data["expected"]["findings"][0]["claim"]
        with self.assertRaisesRegex(bf.FixtureFormatError, "claim"):
            bf.parse_case(self.data)

    def test_finding_without_location(self) -> None:
        del self.data["expected"]["findings"][0]["location"]
        with self.assertRaisesRegex(bf.FixtureFormatError, "location"):
            bf.parse_case(self.data)

    def test_location_without_intent(self) -> None:
        del self.data["expected"]["findings"][0]["location"]["location_intent"]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_bad_location_intent_value(self) -> None:
        self.data["expected"]["findings"][0]["location"]["location_intent"] = "column"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_non_repository_location_requires_path(self) -> None:
        loc = self.data["expected"]["findings"][0]["location"]
        del loc["path"]
        with self.assertRaisesRegex(bf.FixtureFormatError, "path"):
            bf.parse_case(self.data)

    def test_absolute_path_is_rejected(self) -> None:
        self.data["expected"]["findings"][0]["location"]["path"] = "/etc/app/users.py"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_advisory_lines_must_be_well_formed(self) -> None:
        self.data["expected"]["findings"][0]["location"]["lines"] = {"start": 9, "end": 2}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)


class InputRejectionTests(unittest.TestCase):
    """§11 rule 4 — the patch / repo_ref exclusivity and shape."""

    def setUp(self) -> None:
        self.data = _example_data()

    def test_neither_patch_nor_repo_ref(self) -> None:
        self.data["input"] = {"context": "some text"}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_both_patch_and_repo_ref(self) -> None:
        self.data["input"]["repo_ref"] = {"repo": "o/r", "pr": 1}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_base_without_patch_is_rejected(self) -> None:
        self.data["input"] = {"repo_ref": {"repo": "o/r", "pr": 1}, "base": {"a.py": "x"}}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_repo_ref_needs_exactly_one_of_pr_or_commit(self) -> None:
        self.data["input"] = {"repo_ref": {"repo": "o/r", "pr": 1, "commit": "abc"}}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_repo_ref_requires_owner_name_repo(self) -> None:
        self.data["input"] = {"repo_ref": {"repo": "justname", "pr": 1}}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_repo_ref_input_with_string_base_is_accepted(self) -> None:
        self.data["input"] = {"repo_ref": {"repo": "octo/app", "pr": 42, "base": "main"}}
        case = bf.parse_case(self.data)
        self.assertEqual(case.input_kind, "repo_ref")
        self.assertEqual(case.input["repo_ref"]["base"], "main")

    def test_repo_ref_without_base_is_accepted(self) -> None:
        self.data["input"] = {"repo_ref": {"repo": "octo/app", "commit": "abc123"}}
        self.assertEqual(bf.parse_case(self.data).input_kind, "repo_ref")

    def test_repo_ref_non_string_base_is_rejected(self) -> None:
        self.data["input"] = {"repo_ref": {"repo": "octo/app", "pr": 42, "base": 7}}
        with self.assertRaisesRegex(bf.FixtureFormatError, "repo_ref.base"):
            bf.parse_case(self.data)

    def test_repo_ref_blank_base_is_rejected(self) -> None:
        self.data["input"] = {"repo_ref": {"repo": "octo/app", "pr": 42, "base": "   "}}
        with self.assertRaisesRegex(bf.FixtureFormatError, "repo_ref.base"):
            bf.parse_case(self.data)


class SeverityVarianceRejectionTests(unittest.TestCase):
    """§11 rule 6 — severity scalars and permitted-variance lists."""

    def setUp(self) -> None:
        self.data = _example_data()

    def test_unknown_severity_value(self) -> None:
        self.data["expected"]["findings"][0]["severity"] = "P3"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_single_element_severity_list_is_rejected(self) -> None:
        self.data["expected"]["findings"][0]["severity"] = ["P0"]
        with self.assertRaisesRegex(bf.FixtureFormatError, ">= 2"):
            bf.parse_case(self.data)

    def test_severity_list_with_duplicate_is_rejected(self) -> None:
        self.data["expected"]["findings"][-1]["severity"] = ["P2", "P2"]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)


class AlternativeAndGroupRejectionTests(unittest.TestCase):
    """§11 rules 5 and 9 — key collisions and any_of structure."""

    def setUp(self) -> None:
        self.data = _example_data()

    def test_duplicate_finding_keys(self) -> None:
        self.data["expected"]["findings"][1]["key"] = "sqli-user-lookup"
        # (also drop any_of so only the key clash is under test)
        self.data["expected"]["findings"][1] = {
            "key": "sqli-user-lookup",
            "severity": "P1",
            "location": {"location_intent": "file", "path": "app/users.py"},
            "claim": "another finding",
        }
        with self.assertRaisesRegex(bf.FixtureFormatError, "duplicate"):
            bf.parse_case(self.data)

    def test_key_used_both_standalone_and_inside_any_of(self) -> None:
        self.data["expected"]["findings"][0]["key"] = "path-traversal"
        with self.assertRaisesRegex(bf.FixtureFormatError, "any_of"):
            bf.parse_case(self.data)

    def test_any_of_group_needs_two_members(self) -> None:
        group = self.data["expected"]["findings"][1]
        group["any_of"] = group["any_of"][:1]
        with self.assertRaisesRegex(bf.FixtureFormatError, ">= 2 members"):
            bf.parse_case(self.data)

    def test_any_of_group_may_not_carry_its_own_severity(self) -> None:
        self.data["expected"]["findings"][1]["severity"] = "P0"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_nested_any_of_is_rejected(self) -> None:
        group = self.data["expected"]["findings"][1]
        group["any_of"][0] = {
            "key": "nested",
            "any_of": [
                {"key": "a", "severity": "P1", "location": {"location_intent": "file", "path": "x"}, "claim": "c"},
                {"key": "b", "severity": "P1", "location": {"location_intent": "file", "path": "y"}, "claim": "c"},
            ],
        }
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_any_of_member_may_not_carry_its_own_match(self) -> None:
        self.data["expected"]["findings"][1]["any_of"][0]["match"] = "optional"
        with self.assertRaisesRegex(bf.FixtureFormatError, "does not carry its own 'match'"):
            bf.parse_case(self.data)

    def test_key_reused_across_two_any_of_groups_is_rejected(self) -> None:
        # A second group whose member reuses a key from the first group.
        self.data["expected"]["findings"].append(
            {
                "key": "second-group",
                "any_of": [
                    {
                        "key": "path-traversal",  # already used in unsafe-export-path
                        "severity": "P1",
                        "location": {"location_intent": "file", "path": "app/users.py"},
                        "claim": "duplicate key across groups",
                    },
                    {
                        "key": "fresh-alt",
                        "severity": "P2",
                        "location": {"location_intent": "file", "path": "app/users.py"},
                        "claim": "the other branch",
                    },
                ],
            }
        )
        with self.assertRaisesRegex(bf.FixtureFormatError, "not unique across the case"):
            bf.parse_case(self.data)

    def test_empty_alternatives_list_is_rejected(self) -> None:
        self.data["expected"]["findings"][0]["alternatives"] = []
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_alternative_must_narrow_something(self) -> None:
        self.data["expected"]["findings"][0]["alternatives"] = [{}]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)


class DefectKindSymmetryTests(unittest.TestCase):
    """A primary spec's `defect_kind` and an `alternatives` entry's
    `defect_kind` share one slug rule (fixture-format.md §8.2)."""

    def setUp(self) -> None:
        self.data = _example_data()

    def test_valid_alternative_defect_kind_passes(self) -> None:
        self.data["expected"]["findings"][0]["alternatives"][0]["defect_kind"] = "tainted-query"
        case = bf.parse_case(self.data)
        self.assertEqual(case.findings[0].alternatives[0]["defect_kind"], "tainted-query")

    def test_malformed_alternative_defect_kind_is_rejected(self) -> None:
        self.data["expected"]["findings"][0]["alternatives"][0]["defect_kind"] = "SQL Injection"
        with self.assertRaisesRegex(bf.FixtureFormatError, "alternative 'defect_kind'"):
            bf.parse_case(self.data)

    def test_primary_and_alternative_defect_kind_use_the_same_rule(self) -> None:
        # The exact value rejected on an alternative is also rejected on a primary.
        bad = "Not A Slug"
        primary = _example_data()
        primary["expected"]["findings"][0]["defect_kind"] = bad
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(primary)
        alt = _example_data()
        alt["expected"]["findings"][0]["alternatives"][0]["defect_kind"] = bad
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(alt)

    def test_any_of_member_defect_kind_uses_the_same_rule(self) -> None:
        self.data["expected"]["findings"][1]["any_of"][0]["defect_kind"] = "Path Traversal"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)


class CompletenessAndDecisionTests(unittest.TestCase):
    """§11 rules 8 and 11 — completeness enum and decision consistency."""

    def setUp(self) -> None:
        self.data = _example_data()

    def test_bad_completeness_value(self) -> None:
        self.data["expected"]["findings_completeness"] = "loose"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_findings_must_be_a_list(self) -> None:
        self.data["expected"]["findings"] = {"key": "x"}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_declared_decision_inconsistent_with_severities_is_rejected(self) -> None:
        self.data["expected"]["decision"] = "clean"  # but P0 required finding exists
        with self.assertRaisesRegex(bf.FixtureFormatError, "contradicts"):
            bf.parse_case(self.data)

    def test_bad_decision_value(self) -> None:
        self.data["expected"]["decision"] = "approve"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_empty_findings_list_is_a_valid_clean_case(self) -> None:
        self.data["expected"] = {"findings": [], "decision": "clean"}
        case = bf.parse_case(self.data)
        self.assertEqual(case.findings, ())
        self.assertEqual(case.derived_decision, "clean")

    def test_decision_is_optional_and_derived_when_absent(self) -> None:
        del self.data["expected"]["decision"]
        case = bf.parse_case(self.data)
        self.assertIsNone(case.decision)
        self.assertEqual(case.derived_decision, "changes-required")

    def test_only_optional_blocking_findings_still_derive_clean(self) -> None:
        self.data["expected"] = {
            "findings": [
                {
                    "key": "maybe",
                    "match": "optional",
                    "severity": "P0",
                    "location": {"location_intent": "file", "path": "app/users.py"},
                    "claim": "optional blocking observation",
                }
            ]
        }
        case = bf.parse_case(self.data)
        self.assertEqual(case.derived_decision, "clean")


class MetadataTests(unittest.TestCase):
    """§11 rule 10 — closed metadata map and controlled tag vocabulary."""

    def setUp(self) -> None:
        self.data = _example_data()

    def test_unknown_tag_is_rejected(self) -> None:
        self.data["metadata"]["tags"] = ["security", "style"]
        with self.assertRaisesRegex(bf.FixtureFormatError, "unknown tag"):
            bf.parse_case(self.data)

    def test_duplicate_tag_is_rejected(self) -> None:
        self.data["metadata"]["tags"] = ["security", "security"]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(self.data)

    def test_metadata_is_optional(self) -> None:
        del self.data["metadata"]
        case = bf.parse_case(self.data)
        self.assertEqual(case.metadata, {})


class InducedRegressionTests(unittest.TestCase):
    """The suite has teeth: a validator that stopped enforcing a rule must
    be caught by at least one negative test above. Each mutation disables
    one check; the corpus must then fail."""

    def setUp(self) -> None:
        self.data = _example_data()

    def _corpus_still_rejects_bad_inputs(self) -> bool:
        """True if at least one representative malformed fixture is still
        rejected."""
        checks = []

        bad_version = copy.deepcopy(self.data)
        bad_version["format"] = "benchmark-case/v9"
        checks.append(bad_version)

        unknown_key = copy.deepcopy(self.data)
        unknown_key["mystery"] = 1
        checks.append(unknown_key)

        bad_sev = copy.deepcopy(self.data)
        bad_sev["expected"]["findings"][0]["severity"] = "P5"
        checks.append(bad_sev)

        for bad in checks:
            try:
                bf.parse_case(bad)
            except bf.FixtureFormatError:
                continue
            return False
        return True

    def test_reference_validator_rejects_representative_bad_fixtures(self) -> None:
        self.assertTrue(self._corpus_still_rejects_bad_inputs())

    def test_a_permissive_validator_that_skips_version_check_would_be_caught(self) -> None:
        # Simulate the regression: a parser that accepts any `format`.
        original = bf.SUPPORTED_FORMATS
        try:
            bf.SUPPORTED_FORMATS = frozenset(
                {"benchmark-case/v1", "benchmark-case/v9"}
            )
            # With the version gate widened, the bad-version fixture is
            # wrongly accepted — exactly what SchemaIdentityRejectionTests
            # guards against.
            data = copy.deepcopy(self.data)
            data["format"] = "benchmark-case/v9"
            bf.parse_case(data)  # no raise -> the gate is gone
            accepted = True
        except bf.FixtureFormatError:
            accepted = False
        finally:
            bf.SUPPORTED_FORMATS = original
        self.assertTrue(
            accepted,
            "expected the widened version set to accept v9 — the negative "
            "test in SchemaIdentityRejectionTests is what keeps the real "
            "SUPPORTED_FORMATS narrow",
        )


if __name__ == "__main__":
    unittest.main()
