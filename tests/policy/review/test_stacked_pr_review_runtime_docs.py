"""Structural contract checks for the packaged runtime installation of
stacked/dependent-PR review (#119),
skills/github-pr-review/policies/stacked-pr-review.md.

Mirrors the assertion style of test_stacked_pr_review_docs.py (the
contract, PR #253) and test_stateful_delta_rereview_docs.py (the sibling
runtime installation, #65 relative to #64), but targets the *packaged*
policy this issue installs and its wiring into the Skill's runbooks,
canonical index, SKILL.md, output templates, and package manifest — not
merely that the design-record doc states the rules.
"""

import unittest

from tests.support.paths import REPO_ROOT

POLICY = (
    REPO_ROOT / "skills" / "github-pr-review" / "policies" / "stacked-pr-review.md"
)
SKILL = REPO_ROOT / "skills" / "github-pr-review" / "SKILL.md"
INDEX = REPO_ROOT / "skills" / "github-pr-review" / "policies" / "github-review.md"
REPOSITORY_CHECKOUT = (
    REPO_ROOT / "skills" / "github-pr-review" / "policies" / "repository-checkout.md"
)
STATEFUL_DELTA = (
    REPO_ROOT
    / "skills"
    / "github-pr-review"
    / "policies"
    / "stateful-delta-rereview.md"
)
PR_SCOPE = REPO_ROOT / "skills" / "github-pr-review" / "policies" / "pr-scope.md"
REVIEW_CONTEXT = (
    REPO_ROOT / "skills" / "github-pr-review" / "policies" / "review-context.md"
)
REVIEW_OUTPUT = (
    REPO_ROOT / "skills" / "github-pr-review" / "policies" / "review-output.md"
)
EXTERNAL_SUMMARY = (
    REPO_ROOT
    / "skills"
    / "github-pr-review"
    / "templates"
    / "external-review-summary.md"
)
ACTIVE_RUNBOOK = (
    REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "active-pr-review.md"
)
PASSIVE_RUNBOOK = (
    REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "passive-pr-review.md"
)
LOCAL_SKILL = REPO_ROOT / "skills" / "local-code-review" / "SKILL.md"
PACKAGE_MANIFEST = REPO_ROOT / "scripts" / "packaging" / "package-manifest.json"
PACKAGE_SH = REPO_ROOT / "scripts" / "packaging" / "package-skills.sh"


class StackedPrReviewPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = POLICY.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_policy_file_exists(self) -> None:
        self.assertTrue(POLICY.is_file())

    def test_reuses_not_redefines_sibling_policies(self) -> None:
        for reused in (
            "repository-checkout.md",
            "stateful-delta-rereview.md",
            "review-context.md",
            "review-ownership.md",
        ):
            self.assertIn(reused, self.raw)

    def test_terminology_defines_stack_layer_owned_and_inherited_delta(self) -> None:
        section = self.raw.split("## 1. Terminology", 1)[1].split("## 2.", 1)[0]
        for term in (
            "**Stack**",
            "**Layer**",
            "**Effective review base**",
            "**Owned delta**",
            "**Inherited delta**",
            "**Root**",
        ):
            self.assertIn(term, section)

    def test_effective_base_never_assumed_to_be_root(self) -> None:
        section = " ".join(
            self.raw.split("## 2. Detecting a stack", 1)[1]
            .split("## 3.", 1)[0]
            .split()
        )
        self.assertIn("never the root", section)
        self.assertIn("immediate parent's **current head SHA**", section)
        self.assertIn(
            "this PR is an ordinary, non-stacked review", section
        )

    def test_owned_vs_inherited_delta_and_blast_radius(self) -> None:
        section = self.raw.split(
            "## 3. Owned vs. inherited delta", 1
        )[1].split("## 4.", 1)[0]
        self.assertIn("Owned delta is the Review Target", section)
        self.assertIn("Inherited delta is Repository Context", section)
        self.assertIn(
            "not** a finding this layer's review reports", section
        )
        self.assertIn(
            "Blast radius still applies across the layer boundary", section
        )

    def test_safe_failure_defines_both_tiers(self) -> None:
        section = " ".join(
            self.raw.split("## 4. Safe failure", 1)[1]
            .split("## 5.", 1)[0]
            .split()
        )
        self.assertIn("### Tier 1 — single-hop fallback", self.raw)
        self.assertIn("### Tier 2 — root fallback", self.raw)
        self.assertIn("wider", section)
        self.assertIn("never a narrower", section)
        for case in (
            "Rebase / force-push on the current layer itself",
            "Changed parent branch (retarget)",
            "Closed or merged lower PR",
            "squash or rebase merge",
            "Cycle or otherwise malformed chain",
        ):
            self.assertIn(case, section)

    def test_lower_layer_trigger_table_has_three_outcomes(self) -> None:
        section = self.raw.split(
            "## 5. A lower PR changes", 1
        )[1].split("## 6.", 1)[0]
        self.assertIn("No re-review required", section)
        self.assertIn("Partial (bounded delta) re-review", section)
        self.assertIn("Escalate to a full review", section)
        self.assertIn("No numeric threshold is introduced", section)

    def test_persisted_state_is_one_annotation_not_a_new_record(self) -> None:
        section = self.raw.split(
            "## 6. Persisted state", 1
        )[1].split("## 7.", 1)[0]
        self.assertIn("no** second, parallel state record", section)
        self.assertIn(
            "Effective-base provenance (new annotation, not a new field)",
            section,
        )
        self.assertIn("Base branch name", section)
        self.assertIn("Base SHA at review time", section)
        self.assertIn("Merge-base SHA at review time", section)

    def test_review_output_section_states_stack_layer_and_base(self) -> None:
        section = self.raw.split("## 7. Review output", 1)[1].split("## 8.", 1)[0]
        self.assertIn("the detected stack", section)
        self.assertIn("which layer is currently under review", section)
        self.assertIn("the effective review base actually used", section)

    def test_non_stacked_prs_provably_unaffected_section_exists(self) -> None:
        section = " ".join(
            self.raw.split("## 8. Non-stacked PRs are provably unaffected", 1)[1]
            .split("## 9.", 1)[0]
            .split()
        )
        self.assertIn(
            "exactly the same policies, in exactly the same order", section
        )
        self.assertIn("no new finding", section)
        self.assertIn("no new severity rule", section)

    def test_scope_boundaries_defers_to_owners_and_excludes_local_code_review(
        self,
    ) -> None:
        section = self.raw.split("## 9. Scope boundaries", 1)[1]
        self.assertIn("Explicitly a non-goal", section)
        self.assertIn("does not load this policy", section)

    def test_does_not_link_the_unpackaged_contract_doc(self) -> None:
        self.assertNotIn("stacked-pr-review-contract", self.raw)


class WiringTests(unittest.TestCase):
    """The policy must actually be loaded and referenced, not merely exist."""

    def test_canonical_index_lists_it_after_stateful_delta_rereview_and_before_pr_scope(
        self,
    ) -> None:
        raw = INDEX.read_text(encoding="utf-8")
        self.assertIn("stacked-pr-review.md", raw)
        pos_stateful = raw.index("stateful-delta-rereview.md")
        pos_stacked = raw.index("stacked-pr-review.md")
        pos_pr_scope = raw.index("pr-scope.md")
        self.assertLess(pos_stateful, pos_stacked)
        self.assertLess(pos_stacked, pos_pr_scope)

    def test_repository_checkout_cross_references_effective_base(self) -> None:
        raw = REPOSITORY_CHECKOUT.read_text(encoding="utf-8")
        self.assertIn("stacked-pr-review.md", raw)
        self.assertIn("effective review base", raw)

    def test_stateful_delta_rereview_extends_escalation_and_reviewed_state(
        self,
    ) -> None:
        raw = STATEFUL_DELTA.read_text(encoding="utf-8")
        self.assertIn("stacked-pr-review.md", raw)
        self.assertIn("Stacked-PR lower-layer trigger", raw)
        self.assertIn("effective-base provenance", raw)

    def test_pr_scope_clarifies_base_means_effective_base_for_a_stack_layer(
        self,
    ) -> None:
        raw = PR_SCOPE.read_text(encoding="utf-8")
        self.assertIn("stacked-pr-review.md", raw)
        self.assertIn("effective review base", raw)

    def test_review_context_notes_owned_vs_inherited_delta(self) -> None:
        raw = REVIEW_CONTEXT.read_text(encoding="utf-8")
        self.assertIn("stacked-pr-review.md", raw)
        self.assertIn("owned delta", raw)
        self.assertIn("inherited delta", raw)

    def test_review_output_defines_stacked_pr_context_section(self) -> None:
        raw = REVIEW_OUTPUT.read_text(encoding="utf-8")
        self.assertIn("## Stacked-PR context", raw)
        self.assertIn("stacked-pr-review.md", raw)

    def test_external_summary_template_renders_stacked_pr_field(self) -> None:
        raw = EXTERNAL_SUMMARY.read_text(encoding="utf-8")
        self.assertIn("## Stacked-PR context", raw)
        self.assertIn("stacked_pr:", raw)
        self.assertIn("none detected", raw)

    def test_active_runbook_resolves_topology_before_scope_retrieval(self) -> None:
        raw = ACTIVE_RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("stacked-pr-review.md", raw)
        pos_topology = raw.index("resolve stack topology")
        pos_scope = raw.index("retrieve complete paginated PR scope")
        self.assertLess(pos_topology, pos_scope)
        self.assertIn(
            "Before computing\n   any delta, resolve stack topology",
            raw.replace("**", ""),
        )

    def test_passive_runbook_resolves_topology_before_scope_retrieval(self) -> None:
        raw = PASSIVE_RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("stacked-pr-review.md", raw)
        pos_topology = raw.index("resolve stack topology")
        pos_resolve_files = raw.index("resolve changed files")
        self.assertLess(pos_topology, pos_resolve_files)

    def test_skill_md_references_the_policy(self) -> None:
        text = " ".join(SKILL.read_text(encoding="utf-8").split())
        self.assertIn("policies/stacked-pr-review.md", text)
        self.assertIn("Stacked/dependent PRs.", text)

    def test_local_code_review_skill_is_not_modified_to_load_it(self) -> None:
        text = LOCAL_SKILL.read_text(encoding="utf-8")
        self.assertNotIn("stacked-pr-review.md", text)

    def test_package_manifest_declares_the_new_policy_file(self) -> None:
        self.assertIn(
            "policies/stacked-pr-review.md",
            PACKAGE_MANIFEST.read_text(encoding="utf-8"),
        )

    def test_no_package_script_hardcodes_the_file_list(self) -> None:
        # package-skills.sh is manifest-driven; it must not need a source
        # edit merely because a new packaged file was added.
        raw = PACKAGE_SH.read_text(encoding="utf-8")
        self.assertNotIn("stacked-pr-review.md", raw)


if __name__ == "__main__":
    unittest.main()
