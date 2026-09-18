#!/usr/bin/env python3
"""Behavioral coverage for the canonical benchmark candidate taxonomy
(Issue #333). Contract: runtime_platform/benchmark/taxonomy.md.

Three things are proven here, against synthetic fixture metadata — never
the live corpus (tests/unit/benchmark/test_benchmark_corpus.py and the
per-domain corpus tests already walk every real case):

1. ``validate_taxonomy`` is fail-closed: an unknown dimension key, a
   missing dimension, an unknown value, a duplicate value, or an empty
   value list is rejected with ``TaxonomyError`` — never silently
   accepted or coerced.
2. every dimension's ``unclassified`` value is legal and does not need to
   be combined with anything else.
3. ``classify_affected_surfaces`` is fully deterministic and bounded by
   the four named surfaces plus ``unclassified`` — never a guess.
"""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.reference import benchmark_taxonomy as tax


def _valid_taxonomy() -> dict:
    return {
        "capability": ["security-boundary"],
        "policy_contract": ["security-deepening"],
        "risk_mode": ["security"],
        "affected_surface": ["unclassified"],
    }


class ValidateTaxonomyTests(unittest.TestCase):
    def test_a_well_formed_taxonomy_validates(self) -> None:
        result = tax.validate_taxonomy(_valid_taxonomy())
        self.assertEqual(result["capability"], ("security-boundary",))
        self.assertEqual(result["affected_surface"], ("unclassified",))

    def test_unclassified_alone_is_legal_for_every_dimension(self) -> None:
        data = {dim: ["unclassified"] for dim in tax.DIMENSIONS}
        result = tax.validate_taxonomy(data)
        for dim in tax.DIMENSIONS:
            self.assertEqual(result[dim], ("unclassified",))

    def test_a_dimension_may_carry_more_than_one_value(self) -> None:
        data = _valid_taxonomy()
        data["capability"] = ["security-boundary", "core"]
        result = tax.validate_taxonomy(data)
        self.assertEqual(result["capability"], ("security-boundary", "core"))

    def test_not_a_mapping_is_rejected(self) -> None:
        with self.assertRaises(tax.TaxonomyError):
            tax.validate_taxonomy(["capability"])

    def test_unknown_dimension_key_is_rejected(self) -> None:
        data = _valid_taxonomy()
        data["authz"] = ["unclassified"]
        with self.assertRaisesRegex(tax.TaxonomyError, "unknown dimension"):
            tax.validate_taxonomy(data)

    def test_missing_dimension_is_rejected(self) -> None:
        data = _valid_taxonomy()
        del data["risk_mode"]
        with self.assertRaisesRegex(tax.TaxonomyError, "missing dimension"):
            tax.validate_taxonomy(data)

    def test_unknown_value_is_rejected(self) -> None:
        data = _valid_taxonomy()
        data["capability"] = ["not-a-real-capability"]
        with self.assertRaisesRegex(tax.TaxonomyError, "unknown value"):
            tax.validate_taxonomy(data)

    def test_duplicate_value_is_rejected(self) -> None:
        data = _valid_taxonomy()
        data["risk_mode"] = ["security", "security"]
        with self.assertRaisesRegex(tax.TaxonomyError, "duplicate value"):
            tax.validate_taxonomy(data)

    def test_empty_value_list_is_rejected(self) -> None:
        data = _valid_taxonomy()
        data["risk_mode"] = []
        with self.assertRaisesRegex(tax.TaxonomyError, "non-empty list"):
            tax.validate_taxonomy(data)

    def test_non_string_value_is_rejected(self) -> None:
        data = _valid_taxonomy()
        data["risk_mode"] = [1]
        with self.assertRaisesRegex(tax.TaxonomyError, "must be a string"):
            tax.validate_taxonomy(data)

    def test_non_list_value_is_rejected(self) -> None:
        data = _valid_taxonomy()
        data["risk_mode"] = "security"
        with self.assertRaisesRegex(tax.TaxonomyError, "non-empty list"):
            tax.validate_taxonomy(data)


class SanitizeTaxonomyResponseTests(unittest.TestCase):
    """The untrusted-input side (§4): a model's raw response is never
    trusted to raise cleanly — it must be sanitized, never rejected
    outright, and an invented key/value never survives."""

    def test_well_formed_response_passes_through(self) -> None:
        raw = {
            "capability": ["security-boundary"],
            "policy_contract": ["security-deepening"],
            "risk_mode": ["security"],
            "affected_surface": ["shared-policy"],
        }
        result = tax.sanitize_taxonomy_response(raw)
        self.assertEqual(result["capability"], ("security-boundary",))
        self.assertEqual(result["affected_surface"], ("shared-policy",))

    def test_invented_value_is_dropped_not_accepted(self) -> None:
        raw = {"capability": ["quantum-networking"]}
        result = tax.sanitize_taxonomy_response(raw)
        self.assertEqual(result["capability"], (tax.UNCLASSIFIED,))

    def test_invented_dimension_key_is_dropped(self) -> None:
        raw = {"capability": ["core"], "authz": ["admin-only"]}
        result = tax.sanitize_taxonomy_response(raw)
        self.assertNotIn("authz", result)
        self.assertEqual(result["capability"], ("core",))

    def test_missing_dimension_resolves_to_unclassified(self) -> None:
        raw = {"capability": ["core"]}
        result = tax.sanitize_taxonomy_response(raw)
        self.assertEqual(result["policy_contract"], (tax.UNCLASSIFIED,))
        self.assertEqual(result["risk_mode"], (tax.UNCLASSIFIED,))
        self.assertEqual(result["affected_surface"], (tax.UNCLASSIFIED,))

    def test_non_mapping_response_resolves_every_dimension_to_unclassified(self) -> None:
        for adversarial in ("not json", None, 42, ["capability", "core"]):
            with self.subTest(raw=adversarial):
                result = tax.sanitize_taxonomy_response(adversarial)
                for dim in tax.DIMENSIONS:
                    self.assertEqual(result[dim], (tax.UNCLASSIFIED,))

    def test_mixed_valid_and_invented_values_keeps_only_the_valid_ones(self) -> None:
        raw = {"capability": ["core", "made-up-value", "security-boundary"]}
        result = tax.sanitize_taxonomy_response(raw)
        self.assertEqual(result["capability"], ("core", "security-boundary"))

    def test_duplicate_values_in_response_are_deduplicated(self) -> None:
        raw = {"risk_mode": ["security", "security"]}
        result = tax.sanitize_taxonomy_response(raw)
        self.assertEqual(result["risk_mode"], ("security",))

    def test_never_raises_on_arbitrary_adversarial_input(self) -> None:
        adversarial_inputs = [
            {},
            {"capability": None},
            {"capability": "core"},  # string, not a list
            {"capability": [None, 1, {}]},
            {"capability": ["core"], "policy_contract": ["../../etc/passwd"]},
        ]
        for raw in adversarial_inputs:
            with self.subTest(raw=raw):
                result = tax.sanitize_taxonomy_response(raw)
                self.assertEqual(set(result), tax.DIMENSION_NAMES)


class ClassifyAffectedSurfaceTests(unittest.TestCase):
    def test_shared_policy_path(self) -> None:
        self.assertEqual(
            tax.classify_affected_surface("shared/policies/severity.md"), "shared-policy"
        )

    def test_skill_instructions_path(self) -> None:
        self.assertEqual(
            tax.classify_affected_surface("skills/local-code-review/SKILL.md"),
            "skill-instructions",
        )

    def test_runtime_adapter_exact_file(self) -> None:
        self.assertEqual(
            tax.classify_affected_surface("runtime_platform/benchmark/scripts/run_benchmark.py"),
            "runtime-adapter",
        )
        self.assertEqual(
            tax.classify_affected_surface("runtime_platform/benchmark/scripts/benchmark_review_adapter.py"),
            "runtime-adapter",
        )

    def test_benchmark_tooling_path_that_is_not_the_runtime_adapter(self) -> None:
        self.assertEqual(
            tax.classify_affected_surface("runtime_platform/benchmark/scripts/build_benchmark_index.py"),
            "benchmark-corpus-or-tooling",
        )
        self.assertEqual(
            tax.classify_affected_surface("runtime_platform/benchmark/taxonomy.md"),
            "benchmark-corpus-or-tooling",
        )

    def test_unrelated_path_is_unclassified(self) -> None:
        self.assertEqual(
            tax.classify_affected_surface("scripts/release/release_worthiness.py"),
            tax.UNCLASSIFIED,
        )

    def test_empty_path_is_unclassified(self) -> None:
        self.assertEqual(tax.classify_affected_surface(""), tax.UNCLASSIFIED)

    def test_classify_affected_surfaces_unions_and_sorts(self) -> None:
        result = tax.classify_affected_surfaces(
            ["shared/policies/severity.md", "skills/local-code-review/SKILL.md"]
        )
        self.assertEqual(result, ("shared-policy", "skill-instructions"))

    def test_classify_affected_surfaces_empty_input_is_unclassified(self) -> None:
        self.assertEqual(tax.classify_affected_surfaces([]), (tax.UNCLASSIFIED,))

    def test_classify_affected_surfaces_all_unrelated_paths_is_unclassified(self) -> None:
        result = tax.classify_affected_surfaces(["README.md", "scripts/release/x.py"])
        self.assertEqual(result, (tax.UNCLASSIFIED,))


class RiskModeReusesMetadataTagsTests(unittest.TestCase):
    """risk_mode 'reuses metadata.tags' existing enum unchanged' (#333)."""

    def test_risk_mode_values_equal_metadata_tags_plus_unclassified(self) -> None:
        from runtime_platform.benchmark.reference import benchmark_fixture as bf

        self.assertEqual(
            tax.RISK_MODE_VALUES, bf.METADATA_TAGS | {tax.UNCLASSIFIED}
        )


if __name__ == "__main__":
    unittest.main()
