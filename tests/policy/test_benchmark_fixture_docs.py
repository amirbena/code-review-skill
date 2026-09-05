#!/usr/bin/env python3
"""Structural contract checks for the benchmark fixture format (#50).

Pins docs/benchmark/fixture-format.md and its directory README so the
canonical invariant, the schema/versioning fail-closed rule, the four typed
variance constructs, the reused shared vocabulary, and the deferred-scope
boundaries cannot drift silently. Prose assertions are whitespace-normalized;
structural ones target headings and literal terms.
"""

import unittest

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "benchmark" / "fixture-format.md"
README = REPO_ROOT / "docs" / "benchmark" / "README.md"
EXAMPLE = REPO_ROOT / "docs" / "benchmark" / "examples" / "example-case.yaml"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "benchmark_fixture.py"
UNIT_TEST = REPO_ROOT / "tests" / "unit" / "test_benchmark_fixture.py"


class FixtureFormatContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("not** packaged into either Skill archive", self.text)

    def test_names_issue_50_and_its_neighbours(self) -> None:
        for token in ("#50", "#40", "#51", "#52", "#53"):
            self.assertIn(token, self.raw)

    def test_canonical_invariant_is_stated_verbatim(self) -> None:
        self.assertIn(
            "A benchmark fixture describes what a correct review of one input "
            "must contain — never how a runner executes it, and never how "
            "results are scored.",
            self.text,
        )

    def test_representation_is_one_yaml_document_per_case_no_new_dependency(self) -> None:
        self.assertIn("## 2. Representation", self.raw)
        self.assertIn("One benchmark case is one YAML document", self.text)
        self.assertIn("no new dependency is introduced", self.text)
        self.assertIn("schema is **strict**", self.text)

    def test_schema_versioning_is_fail_closed(self) -> None:
        self.assertIn("## 3. Schema identity and versioning", self.raw)
        self.assertIn("benchmark-case/v1", self.raw)
        self.assertIn("Fail closed", self.text)
        self.assertIn("before any other field is read", self.text)
        self.assertIn("MUST NOT parse an unrecognized version", self.text)

    def test_stable_case_identity_is_the_join_key_and_immutable(self) -> None:
        self.assertIn("## 5. Case identity", self.raw)
        self.assertIn("stable join key", self.text)
        self.assertIn("immutable once assigned", self.text)

    def test_input_is_exactly_one_of_patch_or_repo_ref(self) -> None:
        self.assertIn("## 6. Benchmark input", self.raw)
        self.assertIn("MUST contain **exactly one** of", self.text)
        for token in ("`patch`", "`repo_ref`", "`base`"):
            self.assertIn(token, self.raw)

    def test_expected_findings_may_be_empty_for_a_clean_case(self) -> None:
        self.assertIn("MAY be empty", self.raw)
        self.assertIn("no-op / clean case", self.text)

    def test_decision_is_optional_and_derivable_from_severity_policy(self) -> None:
        self.assertIn("`decision` is **derivable**", self.text)
        self.assertIn("shared/policies/severity.md", self.raw)
        self.assertIn("An inconsistent `decision` is a rejection", self.text)

    def test_location_reuses_the_shared_location_intent_enum(self) -> None:
        self.assertIn("finding-matching-strategy.md", self.raw)
        for member in ("`line`", "`symbol`", "`file`", "`cross-file`", "`repository`"):
            self.assertIn(member, self.raw)
        self.assertIn("does not define a parallel review model", self.text)

    def test_advisory_lines_are_not_binding_identity(self) -> None:
        self.assertIn("Advisory only", self.raw)
        self.assertIn("finding-identity-requirements.md", self.raw)
        self.assertIn("line numbers move", self.text)

    def test_anchor_is_the_measurable_hook_without_implementing_matching(self) -> None:
        self.assertIn("measurable hook", self.text)
        self.assertIn("without** this contract implementing matching", self.text)

    def test_issue_59_is_only_closed_identity_prior_art_not_benchmark_owner(self) -> None:
        # F1: #59 is completed stateful-re-review finding-identity research and
        # is never presented as future ownership for benchmark matching.
        self.assertIn("completed stateful-re-review finding-*identity* research", self.text)
        self.assertIn("Issue [#59](https://github.com/amirbena/code-review-skill/issues/59), closed", self.text)
        self.assertIn("It is **not** the owner of benchmark *expected-vs-produced* matching", self.text)
        self.assertIn("borrows only its vocabulary and its defect-continuity + site-continuity discipline", self.text)
        # The stale phrasings the review flagged must be gone.
        self.assertNotIn("any future matcher\n  ([#59]", self.raw)
        self.assertNotIn("issues/59) (matching)", self.raw)

    def test_benchmark_matcher_ownership_routes_to_52_and_41(self) -> None:
        # F1: result capture/comparison -> #52; the match relation + FP/FN
        # metrics -> #41; a dedicated matcher stays unassigned, no new issue.
        boundary = " ".join(self.raw.split("## 13. Scope boundaries", 1)[1].split())
        self.assertIn("per-case expected-vs-produced comparison structure", boundary)
        self.assertIn("expected-vs-produced **match relation**", boundary)
        self.assertIn("false-positive / false-negative accounting", boundary)
        self.assertIn("issues/52", boundary)
        self.assertIn("issues/41", boundary)
        # The "On the benchmark matcher" note: unassigned, no new issue needed.
        self.assertIn("not separately assigned", boundary)
        self.assertIn("none is required today", boundary)
        self.assertIn("is **closed", boundary)
        self.assertIn("stateful-re-review finding-*identity* research", boundary)

    def test_any_of_member_match_prohibition_is_documented(self) -> None:
        # F3: members do not carry their own `match`; it is entry/group level.
        self.assertIn("Entry-level only** — an `any_of` member is not itself an entry", self.text)
        self.assertIn("does not carry its own `match`", self.text)
        self.assertIn("mutually acceptable defect outcomes, not independently opt-in/opt-out", self.text)

    def test_all_four_variance_constructs_are_defined_in_one_table(self) -> None:
        self.assertIn("## 9. Representing acceptable variance", self.raw)
        self.assertIn("no free-text escape hatch", self.text)
        for construct in ("`alternatives`", "`any_of`", "`match: optional`", "severity` as a list"):
            self.assertIn(construct, self.raw)

    def test_arbitrary_output_is_bounded_by_findings_completeness(self) -> None:
        self.assertIn("`findings_completeness: exhaustive` (**default**)", self.raw)
        self.assertIn("`findings_completeness: at-least`", self.raw)
        self.assertIn("only** knob that loosens", self.text)
        self.assertIn("never downgrades a `required` entry to optional", self.text)

    def test_metadata_is_closed_with_concrete_purposes_only(self) -> None:
        self.assertIn("## 10. Optional metadata", self.raw)
        self.assertIn("closed** mapping", self.text)
        for key in ("`source`", "`tags`", "`rationale`"):
            self.assertIn(key, self.raw)
        self.assertIn("No field for scoring weights", self.text)

    def test_fail_closed_validation_rules_are_representative_not_exhaustive(self) -> None:
        # F2: §11 must not claim to be the complete rejection list.
        self.assertIn("## 11. Fail-closed validation", self.raw)
        self.assertIn("rejects the whole fixture", self.text)
        self.assertIn("no partial acceptance, no coercion", self.text)
        self.assertIn("on any violation of this contract", self.text)
        self.assertIn("the **representative** set", self.text)
        self.assertIn("this list is not exhaustive", self.text)
        self.assertIn("Those sections remain authoritative", self.text)
        self.assertIn("it never falls back to `v1` parsing", self.text)

    def test_worked_example_is_linked_and_described(self) -> None:
        self.assertIn("## 12. Worked example", self.raw)
        self.assertIn("](examples/example-case.yaml)", self.raw)
        self.assertIn("](../../tests/unit/test_benchmark_fixture.py)", self.raw)
        self.assertIn("](../../tests/reference/benchmark_fixture.py)", self.raw)

    def test_scope_boundaries_defer_runner_corpus_and_metrics(self) -> None:
        self.assertIn("## 13. Scope boundaries", self.raw)
        boundary = " ".join(self.raw.split("## 13. Scope boundaries", 1)[1].split())
        for token in ("#51", "#52", "#53", "#59", "#41", "#47", "#48", "#40"):
            self.assertIn(token, boundary)
        self.assertIn("retrieval thresholds", boundary)
        self.assertIn("aggregate quality metrics", boundary)

    def test_status_defers_to_an_eventual_canonical_home(self) -> None:
        tail = " ".join(self.raw.split("## Status and canonical home", 1)[1].split())
        self.assertIn("becomes the design record", tail)
        self.assertIn("MUST NOT keep evolving the format independently", tail)


class DirectoryNavigationTests(unittest.TestCase):
    def test_readme_is_navigational_and_maps_the_contract(self) -> None:
        raw = README.read_text(encoding="utf-8")
        self.assertIn("](fixture-format.md)", raw)
        self.assertIn("](examples/example-case.yaml)", raw)
        self.assertIn("not** packaged", raw)
        self.assertIn("#50", raw)

    def test_architecture_links_to_the_benchmark_directory(self) -> None:
        raw = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("benchmark/fixture-format.md", raw)
        self.assertIn("](benchmark/README.md)", raw)
        self.assertIn("nothing benchmark", " ".join(raw.split()))

    def test_reference_model_is_declared_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_unit_test_consumes_the_single_reference_validator(self) -> None:
        raw = UNIT_TEST.read_text(encoding="utf-8")
        self.assertIn("from tests.reference import benchmark_fixture as bf", raw)
        self.assertIn("never defines a second one", raw)


class WorkedExampleFileTests(unittest.TestCase):
    def test_example_declares_the_v1_format_and_is_not_a_corpus_case(self) -> None:
        raw = EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("format: benchmark-case/v1", raw)
        self.assertIn("NOT part of the benchmark corpus", raw)


if __name__ == "__main__":
    unittest.main()
