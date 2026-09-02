"""Structural contract checks for the stable finding identity derivation (#60).

Pins docs/finding-stable-identity.md so the canonical descriptor-primitive
construction, the minted-identity derivation, the fail-closed rule, and the
#59 / #62 boundaries cannot drift silently. Prose assertions are
whitespace-normalized; structural ones target headings and literal terms.
"""

import unittest

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "finding-stable-identity.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REQUIREMENTS = REPO_ROOT / "docs" / "finding-identity-requirements.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "finding_identity.py"


class StableFindingIdentityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("not** packaged into either Skill archive", self.text)

    def test_names_issue_60_and_its_governing_sources(self) -> None:
        for token in ("#60", "#58", "#59", "finding-identity-requirements.md",
                      "finding-matching-strategy.md"):
            self.assertIn(token, self.raw)

    def test_two_layers_descriptor_then_minted_identity(self) -> None:
        self.assertIn("## 1. Two layers", self.raw)
        self.assertIn("canonical finding descriptor", self.text)
        self.assertIn("minted stable identity", self.text)

    def test_every_descriptor_primitive_has_one_documented_derivation(self) -> None:
        for primitive in (
            "`location_intent`", "`path`", "`symbol`", "`construct`",
            "`anchor_tokens`", "`context_tokens`", "`neighboring_syntax`",
            "`behavioral_claim`", "`cause_key`", "`behavior_key`",
            "`mechanism_key`", "`defect_kind`",
        ):
            self.assertIn(primitive, self.raw)
        self.assertIn("## 3. Descriptor primitives — canonical construction", self.raw)
        self.assertIn("### 3.1 Token normalization", self.raw)

    def test_absent_vs_unclassifiable_are_explicit_and_distinct(self) -> None:
        self.assertIn("## 4. Absent vs. unclassifiable", self.raw)
        self.assertIn("Neither sentinel compares equal to any real value", self.text)
        self.assertIn("Neither sentinel compares equal to the other", self.text)
        self.assertIn("act as a wildcard", self.text)

    def test_determinism_offline_and_portability_are_required(self) -> None:
        self.assertIn("## 5. Determinism, offline reproducibility, portability", self.raw)
        for forbidden in ("wall-clock time", "random seeds", "review workers or shards",
                          "discovery or emission order", "`severity`", "display ordinal",
                          "HEAD SHA", "PR number", "repository-state annotation"):
            self.assertIn(forbidden, self.text)
        self.assertIn("identical whether it was produced by", self.text)

    def test_minted_identity_is_a_versioned_digest_over_a_discriminating_subset(self) -> None:
        self.assertIn("### 6.1 Discriminating subset", self.raw)
        self.assertIn("SHA-256", self.raw)
        self.assertIn("fid_", self.raw)
        self.assertIn("`v1`", self.raw)
        # cause_key / behavior_key ARE hashed (false-merge protection); the
        # hashed list is quoted verbatim in the doc.
        self.assertIn(
            "repository, location_intent, path, symbol, construct, anchor_tokens, mechanism_key, cause_key, behavior_key",
            self.text,
        )
        # occurrence context, raw prose, and the free-form defect_kind slug are excluded
        self.assertIn("deliberately excluded", self.text)
        self.assertIn("`context_tokens` and `neighboring_syntax`", self.raw)
        self.assertIn("Free-form wording is not a stable hash discriminator", self.text)

    def test_defect_kind_is_not_a_hash_discriminator(self) -> None:
        self.assertIn("`defect_kind` is not hashed", self.text)
        self.assertIn("still built and still consumed by #59", self.text)

    def test_identity_handoff_keeps_matching_and_lifecycle_separate(self) -> None:
        self.assertIn("### 6.4 Hand-off with #59", self.raw)
        self.assertIn("#60 owns identity; #59 owns whether a current finding", self.text)
        self.assertIn("AMBIGUOUS` never inherits", self.text)
        self.assertIn("propagated unchanged", self.text)
        self.assertIn(
            "cannot broaden #59's equivalence or change its supported / ambiguity / no-edge results",
            self.text,
        )

    def test_handoff_enforces_fail_closed(self) -> None:
        # F3: a non-matchable descriptor mints fresh even when a prior identity is offered.
        self.assertIn("provided the current descriptor is itself eligible for automatic matching", self.text)
        self.assertIn("a caller cannot bypass fail-closed at the hand-off", self.text)

    def test_fail_closed_conditions_are_explicit(self) -> None:
        self.assertIn("## 7. Fail-closed conditions", self.raw)
        self.assertIn("**not eligible for automatic matching**", self.text)
        self.assertIn("**no source-backed discriminator**", self.text)
        self.assertIn("When in doubt, split", self.text)

    def test_fail_closed_on_repo_path_anchor_only(self) -> None:
        # F1: discrimination reducing to repository/path/anchor is non-matchable.
        self.assertIn("reduces to repository / path /", self.text)
        self.assertIn(
            "none of `symbol`, `mechanism_key`, `cause_key`, or `behavior_key` is classified",
            self.text,
        )

    def test_serialization_collision_freedom_is_attributed_to_framing(self) -> None:
        # F4: not universal control-character stripping.
        self.assertIn("Collision-freedom comes from this framing", self.text)
        self.assertIn("length/count prefix on every value", self.text)
        self.assertIn("`repository`, `path`, and `symbol` are hashed as-is", self.text)

    def test_comment_normalization_is_string_and_operator_safe(self) -> None:
        # F2
        self.assertIn("Outside string literals", self.raw)
        self.assertIn("ambiguous with floor division", self.text)
        self.assertIn("Quoted string literals are copied verbatim", self.text)

    def test_scope_boundaries_defer_downstream_work(self) -> None:
        self.assertIn("## 8. Scope boundaries", self.raw)
        boundary = " ".join(self.raw.split("## 8. Scope boundaries", 1)[1].split())
        for issue in ("#59", "#62", "#63", "#64", "#65", "#61", "#44"):
            self.assertIn(issue, boundary)
        self.assertIn("The `F1` / `F2` display ordinals are unchanged", self.text)
        self.assertIn("does not add a rendered field or change any template", self.text)

    def test_status_defers_packaged_policy_to_issue_65(self) -> None:
        tail = " ".join(self.raw.split("## Status and canonical home", 1)[1].split())
        self.assertIn("#65", tail)
        self.assertIn("that policy becomes the single normative source", tail)


class CrossReferenceConsistencyTests(unittest.TestCase):
    def test_architecture_links_to_the_contract(self) -> None:
        self.assertIn("finding-stable-identity.md", ARCHITECTURE.read_text(encoding="utf-8"))

    def test_requirements_doc_links_to_the_derivation_contract(self) -> None:
        self.assertIn("finding-stable-identity.md", REQUIREMENTS.read_text(encoding="utf-8"))

    def test_reference_model_is_declared_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())


if __name__ == "__main__":
    unittest.main()
