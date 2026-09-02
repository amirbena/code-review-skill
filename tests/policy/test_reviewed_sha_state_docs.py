#!/usr/bin/env python3
"""Prose / cross-reference checks pinning the reviewed-SHA state contract
(Issue #63) in docs/findings/reviewed-sha-state-contract.md.

Contract invariants only — this is a repository-development requirements
doc like docs/findings/finding-identity-requirements.md, not runtime logic. The
delta computation, finding lifecycle, and stateful-re-review implementation
belong to #64 / #62 / #65 and are deliberately NOT asserted here.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs/findings/reviewed-sha-state-contract.md"
ARCHITECTURE = REPO_ROOT / "docs/ARCHITECTURE.md"
FINDING_IDENTITY = REPO_ROOT / "docs/findings/finding-identity-requirements.md"
SKILL_DIRS = (
    REPO_ROOT / "skills/local-code-review",
    REPO_ROOT / "skills/github-pr-review",
)
PACKAGE_SCRIPTS = (
    REPO_ROOT / "scripts/package-skills.sh",
    REPO_ROOT / "scripts/package-skills.ps1",
)


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    # Render Markdown links to their visible text ([label](url) -> label),
    # then drop emphasis/code markers and collapse whitespace so assertions
    # match what a reader sees, not the source markup.
    raw = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw)
    raw = raw.replace("**", "").replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class DocExistsAndScopedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_doc_file_exists(self) -> None:
        self.assertTrue(DOC.is_file())

    def test_declares_itself_contract_only(self) -> None:
        self.assertIn("This file is contract / requirements only", self.text)

    def test_declares_itself_repository_development_and_not_packaged(self) -> None:
        self.assertIn("This is a repository-development doc", self.text)
        self.assertIn("not packaged into either Skill archive", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_defers_downstream_work_explicitly(self) -> None:
        # The four Issues #63 must not absorb.
        for issue in ("#62", "#64", "#65", "#66"):
            self.assertIn(issue, self.text)


class ReviewedStateRecordFieldsTests(unittest.TestCase):
    """Question 1 — minimal but sufficient recorded state."""

    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_all_record_fields_are_named(self) -> None:
        for field in (
            "Repository identity",
            "Base branch name",
            "Base SHA at review time",
            "Merge-base SHA at review time",
            "Reviewed head SHA",
            "Reviewer identity",
            "Review result",
            "Review completeness",
            "Prior reviewed SHA",
            "Provenance marker",
            "Associated review evidence reference",
        ):
            self.assertIn(field, self.text)

    def test_associated_review_evidence_reference_is_optional_and_storage_neutral(
        self,
    ) -> None:
        # P2-3: not a hard prerequisite, and worded as a reference/association
        # rather than an embedded payload.
        self.assertIn("Associated review evidence reference", self.text)
        self.assertIn("Optional (recommended)", self.text)
        self.assertIn("opaque reference / association", self.text)
        # storage-neutral: the record points at the evidence, does not embed it
        self.assertIn("it does not have to embed it", self.text)
        # explicitly listed among the fields the record does NOT carry
        self.assertIn("any embedded findings payload or serialization format", self.text)

    def test_missing_associated_reference_does_not_invalidate_state(self) -> None:
        # P2-3: absence limits finding-level reconciliation only; a
        # commit-range re-review stays available.
        self.assertIn(
            "A missing Associated review evidence reference (§1) is not an "
            "incompleteness condition",
            self.text,
        )
        self.assertIn(
            "a commit-range re-review is still available", self.text
        )

    def test_field_preamble_marks_only_the_last_field_optional(self) -> None:
        self.assertIn(
            "All are required to establish trustworthy reviewed-SHA state "
            "except the last",
            self.text,
        )

    def test_local_review_statelessness_asymmetry_is_documented(self) -> None:
        self.assertIn("Local review is stateless", self.text)
        self.assertIn(
            "the Reviewed State Record is the prior review's reported output "
            "as carried forward by the orchestrator",
            self.text,
        )
        self.assertIn("There is no on-disk store", self.text)


class AuthoritativeShaTests(unittest.TestCase):
    """Question 2 — which SHA is authoritative when history moves."""

    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_authoritative_sha_is_the_recorded_head_not_the_tip(self) -> None:
        self.assertIn(
            "The authoritative reviewed state is the reviewed head SHA "
            "recorded in the Reviewed State Record",
            self.text,
        )
        self.assertIn(
            "never the current branch tip, the latest commit, the last push, "
            "or a SHA inferred from a ref name",
            self.text,
        )

    def test_reviewed_sha_not_equated_with_head_just_because_branch_advanced(
        self,
    ) -> None:
        # The core regression guard for #63: a branch advancing never makes
        # its new HEAD "reviewed".
        self.assertIn(
            "A request to treat C as reviewed because the branch moved is "
            "refused",
            self.text,
        )
        self.assertIn(
            "the branch advancing never updates the reviewed SHA", self.text
        )

    def test_added_commit_case_keeps_prior_reviewed_sha(self) -> None:
        self.assertIn(
            "C is not reviewed until a new review completes and writes a new "
            "record",
            self.text,
        )

    def test_all_question2_situations_are_covered(self) -> None:
        for situation in (
            "Working tree clean",
            "Commits added after the review",
            "Remote branch ref moved",
            "PR head changed",
            "Base branch advanced",
            "Branch rebased",
            "Branch force-pushed",
        ):
            self.assertIn(situation, self.text)

    def test_usability_rule_conditions_are_explicit(self) -> None:
        self.assertIn("The usability rule", self.text)
        self.assertIn("still exists in the repository and is an ancestor", self.text)

    def test_no_new_delta_is_the_only_legit_sha_equals_head_case(self) -> None:
        self.assertIn(
            "The one case where \"reviewed SHA equals the current head\" is "
            "legitimate is NO NEW DELTA",
            self.text,
        )
        self.assertIn(
            "an established record, not a branch that happens to sit at that "
            "commit",
            self.text,
        )


class BaseBranchRelationshipTests(unittest.TestCase):
    """Question 3 — what base state is recorded."""

    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_records_all_three_base_signals(self) -> None:
        self.assertIn(
            "stores all three of: the base branch name, the base SHA at "
            "review time, and the merge-base SHA at review time",
            self.text,
        )
        self.assertIn("None alone is sufficient", self.text)

    def test_downstream_can_infer_without_guessing(self) -> None:
        self.assertIn("What downstream may infer without guessing", self.text)
        self.assertIn(
            "the commit range the previous review covered: recorded "
            "merge-base .. recorded reviewed head",
            self.text,
        )

    def test_merge_base_is_recorded_without_defining_the_future_delta_range(
        self,
    ) -> None:
        # P2-2: no "the re-review extends its delta from the merge-base".
        self.assertNotIn("a re-review extends its delta from", self.text)
        self.assertNotIn("which a re-review's delta computation extends from", self.text)
        self.assertIn(
            "the observed lower bound of the range the previous review "
            "actually covered",
            self.text,
        )
        self.assertIn(
            "This contract does not say how a re-review's delta uses it",
            self.text,
        )

    def test_delta_computation_is_left_to_issue_64(self) -> None:
        self.assertIn(
            "How a re-review turns it into a delta", self.text
        )
        self.assertIn("which commit range it re-reviews", self.text)
        self.assertIn("is #64's to define", self.text)


class ReviewerOwnershipTests(unittest.TestCase):
    """Question 4 — reviewer-owned, non-transferable state."""

    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_reviewed_state_is_reviewer_specific(self) -> None:
        self.assertIn("Reviewed-SHA state is reviewer-specific", self.text)

    def test_state_is_not_transferable_between_reviewers(self) -> None:
        self.assertIn("Not transferable.", self.text)
        self.assertIn(
            "A different reviewer does not inherit another reviewer's "
            "reviewed state as a delta base",
            self.text,
        )

    def test_reusable_only_when_identity_reliably_established_both_sides(
        self,
    ) -> None:
        self.assertIn(
            "Reusable only when reviewer identity is reliably established on "
            "both sides",
            self.text,
        )

    def test_unestablished_prior_reviewer_falls_back_to_full_review(self) -> None:
        self.assertIn(
            "Prior reviewer identity cannot be established", self.text
        )
        self.assertIn("fall back to a normal full review", self.text)

    def test_aligns_with_existing_reviewer_delta_policy(self) -> None:
        self.assertIn(
            "skills/github-pr-review/policies/reviewer-delta-review.md",
            self.text,
        )
        self.assertIn(
            "Never infer reviewer ownership from task wording, branch name, "
            "commit author, or the mere existence of a prior review",
            self.text,
        )


class FullVsReReviewChainTests(unittest.TestCase):
    """Question 5 — reconstructing the supersession chain, including an
    escalated-to-full re-review (P2-1)."""

    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_completeness_and_prior_sha_are_independent(self) -> None:
        # P2-1: the two properties must not track each other.
        self.assertIn("review completeness ∈ {full, delta-re-review}", self.text)
        self.assertIn("Two independent properties, not one", self.text)
        self.assertIn("These do not track each other", self.text)

    def test_full_review_may_carry_a_prior_reviewed_sha(self) -> None:
        # P2-1 core invariant: an escalated-to-full re-review still records
        # the predecessor it superseded.
        self.assertIn(
            "completes as full and still records the same-reviewer "
            "predecessor it superseded",
            self.text,
        )
        self.assertIn(
            "Recorded whenever such a predecessor exists — including when "
            "this review is full",
            self.text,
        )

    def test_chain_root_is_not_equated_with_every_full_review(self) -> None:
        # P2-1: chain root == "no established same-reviewer predecessor",
        # not "is a full review".
        self.assertIn(
            "the chain root is the record with no established same-reviewer "
            "predecessor",
            self.text,
        )
        self.assertIn(
            "a full record that superseded an earlier same-reviewer review "
            "is not the root",
            self.text,
        )

    def test_at_most_one_prior_sha_regardless_of_completeness(self) -> None:
        self.assertIn(
            "each record names at most one prior reviewed SHA", self.text
        )
        self.assertIn("regardless of its own completeness", self.text)
        self.assertIn("must not name itself as its prior", self.text)

    def test_escalation_algorithm_itself_is_deferred(self) -> None:
        # State model represents the result; it does not define escalation.
        self.assertIn(
            "it does not define the escalation decision itself", self.text
        )
        self.assertIn("Escalating from delta to full review", self.text)

    def test_both_chain_shapes_are_shown(self) -> None:
        raw = DOC.read_text(encoding="utf-8")
        self.assertIn("full → delta → delta", raw)
        self.assertIn("full → delta → escalated-full → delta", raw)

    def test_prior_sha_must_be_ancestor_of_own_head(self) -> None:
        self.assertIn(
            "must be an ancestor of that record's own reviewed head SHA",
            self.text,
        )

    def test_broken_chain_falls_back_to_full_review(self) -> None:
        self.assertIn(
            "treats the prior state as unusable and falls back to a full "
            "review",
            self.text,
        )


class PersistenceAndProvenanceTests(unittest.TestCase):
    """Question 6 — trust tiers, no new persistence service."""

    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_no_new_persistence_service(self) -> None:
        self.assertIn("introduces no new persistence service", self.text)

    def test_all_four_trust_tiers_named(self) -> None:
        for tier in (
            "Authoritative / trusted state",
            "User-supplied state",
            "Inferred state",
            "Unavailable / ambiguous state",
        ):
            self.assertIn(tier, self.text)

    def test_inferred_state_never_seeds_a_delta(self) -> None:
        self.assertIn("Inferred state", self.text)
        self.assertIn("never a delta seed", self.text)

    def test_user_supplied_state_requires_validation(self) -> None:
        self.assertIn("only after validation", self.text)
        self.assertIn("Never trusted blindly", self.text)

    def test_authoritative_sources_are_existing_mechanisms(self) -> None:
        self.assertIn("submitted GitHub review", self.text)
        self.assertIn("exact-HEAD machine-readable status", self.text)
        self.assertIn(
            "skills/github-pr-review/policies/review-status-enforcement.md",
            self.text,
        )
        self.assertIn(
            "skills/local-code-review/policies/repository-state.md", self.text
        )


class InvalidOrAmbiguousStateTests(unittest.TestCase):
    """Question 7 — safe fallback to a fresh full review."""

    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_guiding_principle_is_stated_verbatim(self) -> None:
        self.assertIn(
            "when prior reviewed state cannot be established safely, fall "
            "back to a fresh full review rather than silently constructing "
            "an unsafe delta",
            self.text,
        )

    def test_ambiguity_never_unlocks_a_delta(self) -> None:
        self.assertIn("ambiguity never unlocks a delta", self.text)

    def test_all_invalid_conditions_resolve_to_full_review(self) -> None:
        for condition in (
            "no longer exists in the repository",
            "not an ancestor",
            "Repository identity differs",
            "Base context is incompatible",
            "Reviewer ownership cannot be verified",
            "Multiple plausible prior reviewed SHAs",
            "Stored state is incomplete",
        ):
            self.assertIn(condition, self.text)

    def test_full_review_fallback_is_not_a_failure(self) -> None:
        self.assertIn(
            "Falling back to a full review is not a failure outcome", self.text
        )


class FindingIdentityBoundaryTests(unittest.TestCase):
    """Question 8 — keep #63 independent from #58/#59/#60/#62."""

    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_findings_held_as_opaque_reference_not_embedded_payload(self) -> None:
        self.assertIn(
            "may hold an opaque reference / association to the prior "
            "review's findings",
            self.text,
        )
        self.assertIn("it never has to embed a findings payload", self.text)
        self.assertIn("this contract defines no serialization for it", self.text)

    def test_does_not_define_identity_matching_or_lifecycle(self) -> None:
        for owned_elsewhere in (
            "how a finding acquires a stable identity across revisions",
            "how findings are matched between the prior payload",
            "what finding lifecycle states exist or how they transition",
            "which findings re-surface vs. suppress",
        ):
            self.assertIn(owned_elsewhere, self.text)

    def test_record_job_is_only_to_anchor_findings(self) -> None:
        self.assertIn("The record's only job with respect to findings is to "
                      "anchor them", self.text)


class RequiredExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = DOC.read_text(encoding="utf-8")

    def test_all_six_examples_present(self) -> None:
        for heading in (
            "### A. Normal re-review",
            "### B. Additional commit after review",
            "### C. Base branch advances",
            "### D. Rebase / rewritten history",
            "### E. Reviewer mismatch",
            "### F. Missing or ambiguous state",
        ):
            self.assertIn(heading, self.raw)

    def test_example_c_does_not_solve_issue_64(self) -> None:
        text = _norm(DOC)
        self.assertIn(
            "This example deliberately does not resolve the delta", text
        )

    def test_example_d_shows_rebase_invalidates_delta_seed(self) -> None:
        text = _norm(DOC)
        self.assertIn("no longer a safe delta seed", text)
        self.assertIn("A force-push that leaves B unreachable", text)


class StatusAndCanonicalHomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(DOC)

    def test_existing_canonical_contracts_are_preserved(self) -> None:
        self.assertIn(
            "Existing canonical contracts are unchanged and remain "
            "authoritative for what they already own",
            self.text,
        )

    def test_future_packaged_policy_becomes_normative(self) -> None:
        self.assertIn(
            "that policy becomes the single normative source", self.text
        )
        self.assertIn(
            "the same lifecycle as", self.text
        )


class CrossReferenceConsistencyTests(unittest.TestCase):
    """References to the canonical reviewed-SHA contract stay consistent."""

    def test_architecture_doc_links_to_the_contract(self) -> None:
        self.assertIn(
            "reviewed-sha-state-contract.md",
            ARCHITECTURE.read_text(encoding="utf-8"),
        )

    def test_finding_identity_doc_links_to_the_contract(self) -> None:
        self.assertIn(
            "reviewed-sha-state-contract.md",
            FINDING_IDENTITY.read_text(encoding="utf-8"),
        )

    def test_no_packaged_resource_markdown_links_to_this_repo_dev_doc(self) -> None:
        # A repository-development doc must not be depended on by any
        # PACKAGED resource — both Skills' shipped Markdown *and* the
        # packaged shared/ Markdown (shared/policies/, shared/templates/).
        # README.md is never packaged (see shared/policies/README.md,
        # "Packaging"), so it is excluded from the scan.
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
                if "reviewed-sha-state-contract" in md.read_text(encoding="utf-8"):
                    offenders.append(str(md.relative_to(REPO_ROOT)))
        self.assertEqual(
            offenders,
            [],
            f"packaged resource markdown must not depend on a docs/ file: {offenders}",
        )

    def test_scan_covers_the_packaged_shared_directories(self) -> None:
        # Guard the P2-5 fix itself: the scan must actually reach shared/.
        for d in (
            REPO_ROOT / "shared" / "policies",
            REPO_ROOT / "shared" / "templates",
        ):
            self.assertTrue(d.is_dir(), f"expected packaged dir missing: {d}")
            self.assertTrue(
                any(p.name != "README.md" for p in d.rglob("*.md")),
                f"no packaged markdown found under {d}",
            )

    def test_no_package_script_ships_the_doc(self) -> None:
        for script in PACKAGE_SCRIPTS:
            self.assertNotIn(
                "reviewed-sha-state-contract",
                script.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
