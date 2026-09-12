"""Structural contract checks for the delta re-review design (#64)."""

import unittest

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "findings" / "delta-re-review-contract.md"
README = REPO_ROOT / "docs" / "findings" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
LIFECYCLE = REPO_ROOT / "docs" / "findings" / "finding-lifecycle-contract.md"
REVIEWED_SHA = REPO_ROOT / "docs" / "findings" / "reviewed-sha-state-contract.md"
FEATURE = REPO_ROOT / "docs" / "features" / "delta-re-review.md"


class DeltaReReviewContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_canonical_invariant_is_stated_verbatim(self) -> None:
        self.assertIn(
            "Delta re-review is an optimization of re-analysis scope, not a "
            "restriction on what may become a finding.",
            self.text,
        )

    def test_all_six_change_classes_are_defined(self) -> None:
        for change_class in (
            "**Unchanged**",
            "**Fixed**",
            "**Moved**",
            "**Reopened**",
            "**Newly introduced**",
            "**Ambiguous**",
        ):
            self.assertIn(change_class, self.raw)
        # consolidation is NOT a seventh change class
        self.assertIn("### Consolidation is not a change class", self.raw)
        self.assertNotIn("**Consolidated**", self.raw)

    def test_consolidation_is_a_lifecycle_disposition_not_a_change_class(self) -> None:
        section = " ".join(
            self.raw.split("### Consolidation is not a change class", 1)[1]
            .split("## 3.", 1)[0]
            .split()
        )
        self.assertIn("does **not** add a seventh change class", section)
        self.assertIn(
            "this contract's classifier still calls that **`Ambiguous`**", section
        )
        self.assertIn("split/collapse is a #59 disqualifier, unchanged", section)
        # default vs positively-established
        self.assertIn("`Ambiguous` → `UNCERTAIN`, every prior identity and its state", section)
        self.assertIn(
            "Consolidation is never inferred from the `N→1` matching topology of "
            "the prior finding set, from descriptor similarity, or from a bare "
            "`AMBIGUOUS` result.",
            section,
        )
        self.assertIn("prior identities receive #62's **`CONSOLIDATED`** disposition", section)
        self.assertIn("each still `OPEN` — consolidation resolves nothing", section)
        self.assertIn("The classifier is unchanged", section)
        # §8: reviewer-established consolidation is not the matcher's collapse
        self.assertIn("Reviewer-established consolidation ≠ matcher collapse", self.raw)
        self.assertIn("`CONSOLIDATED` (#62 §4) is not a change class", self.raw)

    def test_ambiguous_row_states_consolidated_is_not_an_inference(self) -> None:
        """The §2 `Ambiguous` "Maps to" cell must not read as offering
        `CONSOLIDATED` and then denying it — it explicitly frames the
        "never a confident transition" rule as an anti-inference rule and
        `CONSOLIDATED` as its evidence-gated exception, not a heuristic."""
        row = next(
            line
            for line in self.raw.splitlines()
            if line.startswith("| **Ambiguous** |")
        )
        self.assertIn("`UNCERTAIN`, prior state preserved (#62 §4, §7).", row)
        self.assertIn(
            "never **inferred** into a confident "
            "`Fixed`/`Moved`/`Reopened`/resolution transition",
            row,
        )
        self.assertIn(
            "The one non-`UNCERTAIN` outcome is the #62 **`CONSOLIDATED`** "
            "disposition — and it is not such an inference",
            row,
        )
        self.assertIn("it resolves nothing", row)
        self.assertIn("each folded prior identity stays `OPEN`", row)

    def test_change_classes_map_to_lifecycle_events(self) -> None:
        for event in ("`RESOLVED`", "`STILL_PRESENT`", "`REOPENED`", "`DETECTED`", "`UNCERTAIN`"):
            self.assertIn(event, self.raw)

    def test_fix_delta_remains_in_scope_for_new_findings(self) -> None:
        self.assertIn(
            "A prior finding becoming resolved does not make the fix delta",
            self.text,
        )

    def test_blast_radius_is_evidence_based_not_speculative(self) -> None:
        self.assertIn("Attribution must be evidence-based", self.text)
        self.assertIn(
            "not unrestricted speculative re-analysis", self.text.replace("**", "")
        )

    def test_settled_assumptions_reconsidered_when_basis_invalidated(self) -> None:
        self.assertIn("Remains settled while its basis is intact", self.text)
        self.assertIn("Reconsidered when the delta invalidates that basis", self.text)

    def test_escalation_section_names_four_semantic_triggers_no_numeric_threshold(self) -> None:
        section = self.raw.split("## 7. Escalation", 1)[1].split("## 8.", 1)[0]
        for trigger in (
            "**Prior assumptions.**",
            "**Context.**",
            "**Identity evidence.**",
            "**Review boundaries.**",
        ):
            self.assertIn(trigger, section)
        self.assertIn("does **not** invent a numeric threshold", section)

    def test_mechanical_severity_and_decision_derivation_unchanged(self) -> None:
        self.assertIn("no reduced or heightened evidence bar", self.text)
        self.assertIn("no separate", self.text)
        self.assertIn("re-review severity", self.text)
        self.assertIn(
            "never suppresses a newly valid P0/P1/P2", self.text
        )

    def test_identity_integration_names_the_four_forbidden_equivalences(self) -> None:
        for pair in (
            "Same line ≠ same finding",
            "Moved code ≠ a new finding",
            "Resolved identity ≠ a clean fix",
            "Ambiguity ≠ a confident lifecycle transition",
        ):
            self.assertIn(pair, self.raw)

    def test_scope_boundaries_exclude_65_and_66(self) -> None:
        section = self.raw.split("## 9. Scope boundaries", 1)[1]
        self.assertIn("[#65](https://github.com/amirbena/code-review-skill/issues/65)", section)
        self.assertIn("[#66](https://github.com/amirbena/code-review-skill/issues/66)", section)
        self.assertIn("comprehensive delta/regression fixture matrix", section)
        self.assertIn("Orchestrating the load", section)

    def test_status_section_names_65_as_installed_canonical_home(self) -> None:
        self.assertIn("## Status and canonical home", self.raw)
        self.assertIn(
            "this document is now a historical design record", self.text
        )
        self.assertIn("stateful-delta-rereview.md", self.raw)

    def test_not_packaged_into_either_skill(self) -> None:
        self.assertIn("not** packaged into either Skill archive", self.text)


class CrossLinkTests(unittest.TestCase):
    def test_readme_links_new_contract(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("delta-re-review-contract.md", text)
        self.assertIn("#64", text)

    def test_architecture_links_new_contract(self) -> None:
        text = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("findings/delta-re-review-contract.md", text)

    def test_lifecycle_contract_links_forward_to_delta_contract(self) -> None:
        text = LIFECYCLE.read_text(encoding="utf-8")
        self.assertIn("delta-re-review-contract.md", text)

    def test_reviewed_sha_state_contract_links_forward_to_delta_contract(self) -> None:
        text = REVIEWED_SHA.read_text(encoding="utf-8")
        self.assertIn("delta-re-review-contract.md", text)

    def test_feature_doc_links_to_semantic_contract(self) -> None:
        text = FEATURE.read_text(encoding="utf-8")
        self.assertIn("findings/delta-re-review-contract.md", text)


if __name__ == "__main__":
    unittest.main()
