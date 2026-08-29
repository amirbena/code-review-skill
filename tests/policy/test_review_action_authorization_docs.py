#!/usr/bin/env python3
"""Documentation-contract coverage for Issue #101: separating review
analysis from GitHub mutation authority in `github-pr-review`.

Pins the canonical policy (`review-action-authorization.md`) and its
wire-in points (the policy index, `review-authority.md`,
`review-output.md`, `SKILL.md`, both runbooks, package metadata, and the
packaging / validation scripts) so a later edit cannot quietly drop the
security boundary.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

GITHUB = REPO_ROOT / "skills" / "github-pr-review"
POLICY = GITHUB / "policies" / "review-action-authorization.md"
INDEX = GITHUB / "policies" / "github-review.md"
AUTHORITY = GITHUB / "policies" / "review-authority.md"
OUTPUT = GITHUB / "policies" / "review-output.md"
SKILL = GITHUB / "SKILL.md"
ACTIVE_RUNBOOK = GITHUB / "runbooks" / "active-pr-review.md"
PASSIVE_RUNBOOK = GITHUB / "runbooks" / "passive-pr-review.md"
METADATA = GITHUB / "metadata" / "skill.yaml"
SUMMARY_TEMPLATE = GITHUB / "templates" / "external-review-summary.md"
PKG_SH = REPO_ROOT / "scripts" / "package-skills.sh"
PKG_PS1 = REPO_ROOT / "scripts" / "package-skills.ps1"
VALIDATOR = REPO_ROOT / "scripts" / "validate-skill-metadata.py"


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class CanonicalPolicyExists(unittest.TestCase):
    def test_file_exists_and_is_the_canonical_owner(self) -> None:
        self.assertTrue(POLICY.is_file())
        t = _norm(POLICY)
        self.assertIn("Canonical index", t)
        self.assertIn("review analysis", t)
        self.assertIn("GitHub mutation authority", t)


class SecurityPrinciplesStated(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_all_seven_principles_present(self) -> None:
        for phrase in (
            "A review verdict is not authorization.",
            "REVIEW CLEAN must not automatically mean GitHub APPROVE",
            "Approval is not merge authority.",
            "APPROVE must not automatically mean MERGE",
            "Agent-controlled input cannot establish mutation authority.",
            "Reviewer independence requires authority separation, not only identity separation.",
            "An implementation agent cannot manufacture its own reviewer.",
            "Ambiguous authorization or reviewer provenance must fail closed.",
            "Existing review-integrity guarantees remain intact",
        ):
            self.assertIn(phrase, self.t, phrase)

    def test_existing_guarantees_enumerated(self) -> None:
        for phrase in (
            "exact reviewed-HEAD validation",
            "stale-review protection",
            "reviewer ownership",
            "delta re-review semantics",
            "unresolved blocking-finding handling",
        ):
            self.assertIn(phrase, self.t, phrase)


class ReviewActionModes(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_three_modes_defined(self) -> None:
        self.assertIn("recommendation-only (default)", self.t)
        self.assertIn("block-only", self.t)
        self.assertIn("explicitly-authorized auto-action", self.t)

    def test_recommendation_only_is_the_default_and_non_mutating(self) -> None:
        self.assertIn("The default mode is recommendation-only", self.t)
        self.assertIn("Passive PR review is always recommendation-only", self.t)
        self.assertIn("Performs no GitHub review mutation", self.t)

    def test_block_only_never_approves_a_clean_result(self) -> None:
        self.assertIn("must never submit APPROVE for a clean result", self.t)

    def test_auto_action_requires_trusted_authorization_and_independence(self) -> None:
        self.assertIn(
            "trusted mutation authorization is established for this exact action",
            self.t,
        )
        self.assertIn("trusted reviewer independence is established", self.t)

    def test_no_flag_alone_is_sufficient(self) -> None:
        self.assertIn("supplied by the agent is not sufficient", self.t)
        self.assertIn("A caller does not need to pass anything", self.t)
        self.assertIn('say "do not approve"', self.t)


class AuthorizationProvenanceTrustBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_agent_controlled_channels_can_never_authorize(self) -> None:
        for phrase in (
            "a review-action-mode flag, CLI argument, or option value the agent set",
            'agent-generated text such as "approve if clean"',
            "a nested Skill invocation, a nested agent, a sub-agent, or a spawned process",
            "environment variables, config files, or orchestration metadata",
            "alternate GitHub credentials, tokens, usernames, bot identities, "
            "service accounts, or GitHub App identities",
            "the review's own verdict, a prior review's approval, a resolved review thread",
        ):
            self.assertIn(phrase, self.t, phrase)

    def test_structural_limitation_is_documented_honestly(self) -> None:
        self.assertIn("Structural limitation", self.t)
        self.assertIn("has no runtime of its own", self.t)
        self.assertIn("cannot cryptographically verify", self.t)
        self.assertIn("This policy therefore does not pretend to perform such verification", self.t)
        self.assertIn("runtime / orchestration layer", self.t)
        self.assertIn("a runtime which cannot furnish one simply never unlocks auto-action", self.t)

    def test_authorization_is_scoped_and_not_replayable(self) -> None:
        for phrase in (
            "the specific review invocation it was issued for",
            "the specific repository",
            "the specific PR number",
            "the exact reviewed HEAD SHA at submission time",
            "the single permitted action",
            "It is consumed once.",
            "not a standing or reusable approval capability",
            "does not carry to another PR, another repository, a later invocation, or a new HEAD",
        ):
            self.assertIn(phrase, self.t, phrase)


class ReviewerIndependenceIsAuthoritySeparation(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_identity_difference_is_necessary_but_not_sufficient(self) -> None:
        self.assertIn("necessary but not sufficient", self.t)
        self.assertIn(
            "A different identity under the same controlling authority is the "
            "same reviewer",
            self.t,
        )

    def test_manufactured_reviewer_vectors_enumerated(self) -> None:
        for phrase in (
            "switching to another GitHub account the agent controls",
            "selecting or presenting another token or credential",
            "using a bot account, a service account, or a CI identity",
            "using a GitHub App identity the agent can act as",
            "invoking a nested agent, sub-agent, or \"reviewer\" role the agent spawns",
            "spawning another process under the same controlling authority",
            "forwarding the review task, with instructions, to another agent",
        ):
            self.assertIn(phrase, self.t, phrase)

    def test_self_review_guard_preserved_as_defense_in_depth(self) -> None:
        self.assertIn("remains in force as defense in depth", self.t)
        self.assertIn("REVIEW SKIPPED hard stop is authoritative and runs first", self.t)

    def test_ambiguous_reviewer_provenance_fails_closed(self) -> None:
        self.assertIn("treat it as not independent and fail closed", self.t)


class MergeBoundaryUnchanged(unittest.TestCase):
    def test_merge_authority_never_inferred(self) -> None:
        t = _norm(POLICY)
        self.assertIn("This Skill never merges, and this policy adds no merge capability", t)
        self.assertIn(
            "Merge authority is never inferred from a clean verdict, from "
            "holding APPROVE authorization, or from having submitted APPROVE",
            t,
        )


class ComposesWithExistingGates(unittest.TestCase):
    def test_gate_is_additive_not_a_replacement(self) -> None:
        t = _norm(POLICY)
        self.assertIn("The gate is applied in addition to, and after", t)
        self.assertIn("If this gate withholds a mutation, the earlier reasoning result still stands", t)

    def test_reporting_separates_verdict_from_mutation(self) -> None:
        t = _norm(POLICY)
        self.assertIn("Report the review verdict and the mutation outcome", t)
        self.assertIn("Action mode:", t)
        self.assertIn("Mutation:", t)
        self.assertIn("WITHHELD", t)
        self.assertIn('It is never rendered as "approved."', t)


class WiredIntoPolicyIndex(unittest.TestCase):
    def test_index_lists_it_in_canonical_order(self) -> None:
        raw = INDEX.read_text(encoding="utf-8")
        self.assertIn("review-action-authorization.md", raw)
        pos_authority = raw.index("review-authority.md")
        pos_new = raw.index("review-action-authorization.md")
        pos_delta = raw.index("reviewer-delta-review.md")
        self.assertLess(pos_authority, pos_new)
        self.assertLess(pos_new, pos_delta)

    def test_index_points_enforcement_at_review_output(self) -> None:
        t = _norm(INDEX)
        self.assertIn("its gate is enforced at submission time in", t)
        self.assertIn("Review-action authorization gate", t)


class WiredIntoReviewAuthority(unittest.TestCase):
    def test_authority_separation_subsection_present(self) -> None:
        raw = AUTHORITY.read_text(encoding="utf-8")
        self.assertIn("### Authority separation, not just identity separation", raw)
        t = _norm(AUTHORITY)
        self.assertIn(
            "does not, on its own, prove the reviewer is independent of the "
            "change's author",
            t,
        )
        self.assertIn("none of these manufacture an independent reviewer", t)
        self.assertIn("This REVIEW SKIPPED guard runs first and is authoritative", t)


class WiredIntoReviewOutput(unittest.TestCase):
    def test_authorization_gate_subsection_present(self) -> None:
        raw = OUTPUT.read_text(encoding="utf-8")
        self.assertIn("### Review-action authorization gate", raw)
        t = _norm(OUTPUT)
        self.assertIn("The default is recommendation-only", t)
        self.assertIn(
            "APPROVE is submitted only in explicitly-authorized auto-action mode",
            t,
        )
        self.assertIn("Ambiguity in mode, authorization provenance", t)
        self.assertIn("fails closed", t)
        self.assertIn("Mutation: SUBMITTED (<event>) | WITHHELD (<reason>) | NOT REQUESTED", t)

    def test_decision_derivation_still_described_as_mechanical_and_unchanged(self) -> None:
        t = _norm(OUTPUT)
        self.assertIn("This mechanical derivation is owned by", t)
        self.assertIn("unchanged by anything in this section", t)


class WiredIntoSkillMd(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = SKILL.read_text(encoding="utf-8")
        self.t = _norm(SKILL)

    def test_section_covers_review_action_authority(self) -> None:
        self.assertIn("## 7. Review Action Authority and Mutation Boundary", self.raw)
        self.assertIn("Review analysis is separate from GitHub mutation authority", self.t)
        self.assertIn("A review verdict is not authorization.", self.t)
        self.assertIn("The default is non-mutating (recommendation-only).", self.t)
        self.assertIn("APPROVE is submitted only in explicitly-authorized auto-action mode", self.t)

    def test_existing_mutation_boundary_language_preserved(self) -> None:
        self.assertIn("must never: edit implementation files", self.t)
        self.assertIn("merge, delete branches", self.t)
        self.assertIn("Maximum positive action is Approve", self.t)

    def test_policy_loading_lists_the_new_policy(self) -> None:
        self.assertIn("review-action-authorization.md", self.raw)

    def test_head_safety_binds_authorization_to_reviewed_head(self) -> None:
        self.assertIn(
            "Any trusted mutation authorization is bound to the exact reviewed HEAD",
            self.t,
        )

    def test_description_reflects_the_separation(self) -> None:
        self.assertIn("Review analysis is separate from GitHub mutation authority", self.t)
        self.assertIn("the default is a non-mutating recommendation", self.t)


class WiredIntoRunbooks(unittest.TestCase):
    def test_active_runbook_resolves_mode_and_gates_submission(self) -> None:
        raw = ACTIVE_RUNBOOK.read_text(encoding="utf-8")
        t = _norm(ACTIVE_RUNBOOK)
        self.assertIn("Resolve the review-action mode and mutation authorization", t)
        self.assertIn("Apply the review-action authorization gate", t)
        # ordering: capability -> resolve mode -> ... -> gate -> submit
        self.assertLess(
            raw.index("resolve review-action mode + mutation authorization"),
            raw.index("apply the review-action authorization gate"),
        )
        self.assertLess(
            raw.index("apply the review-action authorization gate"),
            raw.index("submit permitted Approve/Request Changes"),
        )

    def test_passive_runbook_is_inherently_recommendation_only(self) -> None:
        t = _norm(PASSIVE_RUNBOOK)
        self.assertIn("Passive review is inherently recommendation-only", t)
        self.assertIn("no review-action mode, flag, prompt, authorization", t)
        self.assertIn("A review verdict is not authorization", t)


class WiredIntoMetadataAndTemplate(unittest.TestCase):
    def test_metadata_declares_default_mode_and_capability(self) -> None:
        raw = METADATA.read_text(encoding="utf-8")
        self.assertIn("default_review_action_mode: recommendation-only", raw)
        self.assertIn("review_action_authorization:", raw)
        self.assertIn("can_merge: false", raw)
        self.assertIn("can_approve: conditional", raw)

    def test_summary_template_reports_mode_and_mutation_separately(self) -> None:
        raw = SUMMARY_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("action_mode:", raw)
        self.assertIn("mutation:", raw)
        self.assertIn("Review-action authority.", raw)


class WiredIntoScripts(unittest.TestCase):
    def test_both_package_scripts_ship_the_policy(self) -> None:
        for script in (PKG_SH, PKG_PS1):
            self.assertIn(
                "policies/review-action-authorization.md",
                script.read_text(encoding="utf-8"),
                script.name,
            )

    def test_validator_orders_the_policy_after_review_authority(self) -> None:
        raw = VALIDATOR.read_text(encoding="utf-8")
        order_block = raw.split("GITHUB_POLICY_ORDER", 1)[1].split(")", 1)[0]
        self.assertIn('"review-authority.md"', order_block)
        self.assertIn('"review-action-authorization.md"', order_block)
        self.assertLess(
            order_block.index('"review-authority.md"'),
            order_block.index('"review-action-authorization.md"'),
        )
        self.assertLess(
            order_block.index('"review-action-authorization.md"'),
            order_block.index('"reviewer-delta-review.md"'),
        )


if __name__ == "__main__":
    unittest.main()
