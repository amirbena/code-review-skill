"""Structural contract checks for the stacked-PR / dependent-change review
design (#119), docs/findings/stacked-pr-review-contract.md.

Contract-only, like its #63/#64 siblings — proves the design record states
the required rules; the runtime stack-detection implementation is a
separate, future issue and is deliberately NOT asserted here.
"""

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "findings" / "stacked-pr-review-contract.md"
README = REPO_ROOT / "docs" / "findings" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REVIEWED_SHA = REPO_ROOT / "docs" / "findings" / "reviewed-sha-state-contract.md"
DELTA_REVIEW = REPO_ROOT / "docs" / "findings" / "delta-re-review-contract.md"
SKILL_DIRS = (
    REPO_ROOT / "skills" / "local-code-review",
    REPO_ROOT / "skills" / "github-pr-review",
)
PACKAGE_SCRIPTS = (
    REPO_ROOT / "scripts" / "package-skills.sh",
    REPO_ROOT / "scripts" / "package-skills.ps1",
)


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw)
    raw = raw.replace("**", "").replace("*", "").replace("`", "")
    # Strip Markdown blockquote markers so a wrapped ">"-prefixed quote
    # reads as continuous prose, matching how a reader sees it.
    raw = re.sub(r"(?m)^>\s?", "", raw)
    return re.sub(r"\s+", " ", raw)


class DocExistsAndScopedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = DOC.read_text(encoding="utf-8")
        self.text = _norm(DOC)

    def test_doc_file_exists(self) -> None:
        self.assertTrue(DOC.is_file())

    def test_declares_itself_contract_only(self) -> None:
        self.assertIn(
            "This document is contract / requirements only", self.text
        )

    def test_declares_itself_repository_development_and_not_packaged(self) -> None:
        self.assertIn("This is a repository-development doc", self.text)
        self.assertIn("not packaged into either Skill archive", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_canonical_invariant_is_stated(self) -> None:
        self.assertIn(
            "A stack layer's review base is its own declared parent, never "
            "an assumed default/target branch",
            self.text,
        )

    def test_reuses_not_redefines_sibling_contracts(self) -> None:
        for issue in ("#43", "#58", "#59", "#60", "#62", "#63", "#64", "#72"):
            self.assertIn(issue, self.raw)
        self.assertIn(
            "This contract reuses, and does not redefine", self.text
        )


class EffectiveBaseSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_effective_base_is_immediate_parent_never_default_branch_assumed(
        self,
    ) -> None:
        self.assertIn(
            "the immediate parent's current head SHA", self.text
        )
        self.assertIn("never the root", self.text)

    def test_non_stacked_pr_falls_back_to_ordinary_review_unchanged(self) -> None:
        self.assertIn(
            "this PR is layer 1 of a one-layer", self.text
        )
        self.assertIn("every existing #63/#64 rule applies unchanged", self.text)


class OwnedVsInheritedDeltaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_owned_delta_is_review_target(self) -> None:
        self.assertIn(
            "Owned delta is the Review Target for layer N", self.text
        )

    def test_inherited_delta_is_repository_context_not_a_finding(self) -> None:
        self.assertIn(
            "Inherited delta is Repository Context", self.text
        )
        self.assertIn(
            "is not a finding this layer's review owns", self.text
        )

    def test_blast_radius_still_applies_across_the_boundary(self) -> None:
        self.assertIn(
            "Blast radius still applies across the boundary", self.text
        )

    def test_worked_three_layer_example_present(self) -> None:
        self.assertIn(
            "Worked example: three-layer stack", self.text
        )


class PersistedShaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_no_new_parallel_record_introduced(self) -> None:
        self.assertIn(
            "This contract does not introduce a second, parallel state "
            "record",
            self.text,
        )

    def test_reuses_existing_63_fields_for_base_branch_and_sha(self) -> None:
        self.assertIn("Base branch name", self.text)
        self.assertIn("Base SHA at review time", self.text)
        self.assertIn("Merge-base SHA at review time", self.text)

    def test_one_additional_stacking_specific_datum_is_named(self) -> None:
        self.assertIn(
            "One additional, stacking-specific datum: effective-base "
            "provenance",
            self.text,
        )
        self.assertIn(
            "an annotation on the existing base-branch-name field", self.text
        )
        self.assertIn("not a new parallel record", self.text)


class LowerLayerChangeTriggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_trigger_condition_is_effective_base_sha_mismatch(self) -> None:
        self.assertIn(
            "The recorded effective-base SHA (§4) for layer N no longer "
            "matches layer N-1's current head SHA",
            self.text,
        )

    def test_no_rereview_when_no_attribution_and_ancestry_intact(self) -> None:
        self.assertIn("No re-review required.", self.text)

    def test_partial_rereview_on_blast_radius_attribution(self) -> None:
        self.assertIn("Partial (bounded delta) re-review", self.text)

    def test_full_escalation_on_broken_ancestry(self) -> None:
        self.assertIn("Escalate to a full review", self.text)
        self.assertIn(
            "mirrors #64 §7's", self.text
        )

    def test_no_numeric_threshold_introduced(self) -> None:
        self.assertIn(
            "No numeric threshold is introduced, matching #64 §7's own "
            "refusal to invent one",
            self.text,
        )


class SafeFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(DOC)
        self.raw = DOC.read_text(encoding="utf-8")

    def test_guiding_principle_prefers_wider_never_narrower_scope(self) -> None:
        self.assertIn(
            "fail closed to a wider, never a narrower, review scope",
            self.text,
        )

    def test_tier_one_single_hop_fallback_named(self) -> None:
        self.assertIn(
            "### Tier 1 — single-hop fallback", self.raw
        )
        self.assertIn(
            "treat this layer as an ordinary, single-hop PR review",
            self.text,
        )

    def test_tier_two_root_fallback_named(self) -> None:
        self.assertIn("### Tier 2 — root fallback", self.raw)

    def test_rebase_of_current_layer_covered(self) -> None:
        self.assertIn(
            "Rebase / force-push on the current layer itself", self.text
        )

    def test_changed_parent_branch_retarget_covered(self) -> None:
        self.assertIn("Changed parent branch (retarget)", self.text)

    def test_closed_or_merged_lower_pr_covered_with_squash_desync(self) -> None:
        self.assertIn("Closed or merged lower PR", self.text)
        self.assertIn(
            "squash or rebase merge", self.text
        )
        self.assertIn(
            "this repository's own default merge strategy", self.text
        )

    def test_cycle_or_malformed_chain_covered(self) -> None:
        self.assertIn(
            "Cycle or otherwise malformed chain", self.text
        )
        self.assertIn("topology undetermined", self.text)

    def test_full_review_against_root_never_hides_a_defect(self) -> None:
        self.assertIn(
            "That is the accepted cost of failing safely: it never "
            "silently drops a defect",
            self.text,
        )


class ReviewOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_output_shows_detected_stack_and_layer_under_review(self) -> None:
        self.assertIn("the detected stack, root to current layer", self.text)
        self.assertIn("which layer is currently under review", self.text)

    def test_output_is_a_contract_requirement_not_a_ui_implementation(self) -> None:
        self.assertIn(
            "not a UI or template implementation", self.text
        )


class RequiredExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = DOC.read_text(encoding="utf-8")

    def test_all_seven_examples_present(self) -> None:
        for heading in (
            "### A. Three-layer stack, owned delta scoped correctly",
            "### B. Lower PR changes after upper PR reviewed — no re-review needed",
            "### C. Lower PR changes after upper PR reviewed — partial re-review",
            "### D. Lower PR rebased after upper PR reviewed — full re-review",
            "### E. Ambiguous merge-base — Tier 1 fallback",
            "### F. Squash-merged lower PR — Tier 2 fallback",
            "### G. Cyclic / malformed chain — Tier 2 fallback",
        ):
            self.assertIn(heading, self.raw)


class StatusAndCanonicalHomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_existing_canonical_contracts_preserved(self) -> None:
        self.assertIn(
            "Existing canonical contracts are unchanged and remain "
            "authoritative for what they already own",
            self.text,
        )

    def test_future_packaged_policy_becomes_normative(self) -> None:
        self.assertIn(
            "that policy becomes the single normative source", self.text
        )


class CrossReferenceConsistencyTests(unittest.TestCase):
    """References to the new contract stay consistent, and it never leaks
    into a packaged Skill resource."""

    def test_findings_readme_links_to_the_contract(self) -> None:
        self.assertIn(
            "stacked-pr-review-contract.md", README.read_text(encoding="utf-8")
        )

    def test_architecture_doc_links_to_the_contract(self) -> None:
        self.assertIn(
            "stacked-pr-review-contract.md",
            ARCHITECTURE.read_text(encoding="utf-8"),
        )

    def test_architecture_doc_lists_it_under_future_work(self) -> None:
        raw = ARCHITECTURE.read_text(encoding="utf-8")
        future_work = raw.split("### Future work (not implemented)", 1)[1]
        self.assertIn("stacked-pr-review-contract.md", future_work)

    def test_no_packaged_resource_markdown_links_to_this_repo_dev_doc(self) -> None:
        packaged_roots = (
            *SKILL_DIRS,
            REPO_ROOT / "shared" / "policies",
            REPO_ROOT / "shared" / "templates",
        )
        offenders = []
        for root in packaged_roots:
            for md in root.rglob("*.md"):
                if md.name == "README.md":
                    continue
                if "stacked-pr-review-contract" in md.read_text(encoding="utf-8"):
                    offenders.append(str(md.relative_to(REPO_ROOT)))
        self.assertEqual(
            offenders,
            [],
            f"packaged resource markdown must not depend on a docs/ file: {offenders}",
        )

    def test_no_package_script_ships_the_doc(self) -> None:
        for script in PACKAGE_SCRIPTS:
            self.assertNotIn(
                "stacked-pr-review-contract",
                script.read_text(encoding="utf-8"),
            )

    def test_sibling_contracts_unchanged_in_substance(self) -> None:
        # #119 must not have edited #63/#64's own normative text — only
        # cross-reference from the new doc, never the reverse redefinition.
        for sibling in (REVIEWED_SHA, DELTA_REVIEW):
            self.assertNotIn(
                "stacked-pr-review-contract",
                sibling.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
