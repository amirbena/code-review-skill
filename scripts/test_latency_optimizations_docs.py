#!/usr/bin/env python3
"""Coverage for the local-code-review latency-optimization contract:
batched Git/policy retrieval, deduplicated instruction discovery, narrowed
file-reviewability applicability, and the staged-fingerprint short-circuit.

Prose checks only. Every check also pins that the optimization is additive
— it never drops a category, a required policy, the completeness invariant,
or the re-verify-blocking-findings requirement.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / "shared"
LOCAL_SKILL_DIR = REPO_ROOT / "skills/local-code-review"

REPOSITORY_INSTRUCTIONS_POLICY = SHARED_DIR / "policies/repository-instructions.md"
FILE_REVIEWABILITY_POLICY = SHARED_DIR / "policies/file-reviewability.md"
SKILL_MD = LOCAL_SKILL_DIR / "SKILL.md"
RUNBOOK = LOCAL_SKILL_DIR / "runbooks/local-review.md"
REPOSITORY_STATE_POLICY = LOCAL_SKILL_DIR / "policies/repository-state.md"


def _text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class RunbookBatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(RUNBOOK)

    def test_execution_efficiency_note_present(self) -> None:
        self.assertIn("## Execution efficiency", self.text)

    def test_base_resolution_must_precede_base_dependent_commands(self) -> None:
        # The actual dependency: step 3's committed-delta command needs
        # step 2's resolved `<base>` as a literal argument, so the two
        # must never be claimed as batchable with each other.
        self.assertIn(
            "must complete — with <base> actually resolved — before any "
            "command that references <base> is issued",
            self.text,
        )
        self.assertIn(
            "it cannot be batched concurrently with step 2 itself, only "
            "after step 2 completes",
            self.text,
        )

    def test_category_detection_commands_batch_only_after_base_is_known(
        self,
    ) -> None:
        self.assertIn(
            "Once <base> is resolved (after step 2), issue all four "
            "together as a single batched/parallel operation",
            self.text,
        )

    def test_base_independent_steps_are_explicitly_identified(self) -> None:
        # Steps 1, 4, and 5 reference no value resolved by another step,
        # so they (and only they) may be freely batched at any point.
        self.assertIn(
            "reference no value resolved by steps 2 or 3", self.text
        )
        self.assertIn("batch {1, 4, 5} freely at any point", self.text)

    def test_never_batch_a_dependent_command_with_its_resolver(self) -> None:
        self.assertIn(
            "never batch a command concurrently with the command that "
            "resolves a value it needs",
            self.text,
        )

    def test_batching_note_does_not_change_what_is_detected(self) -> None:
        self.assertIn(
            "never which categories are detected, which commands are "
            "used, the order in which a value must be resolved before it "
            "is used, or what is reported",
            self.text,
        )

    def test_all_four_categories_still_individually_detected(self) -> None:
        # The runbook still names all four categories (it orders/gates
        # detection); the full per-category command table is owned by
        # repository-state.md and is not restated here.
        for category in ("committed", "staged", "unstaged", "untracked"):
            self.assertIn(category, self.text.lower())
        for category in ("Committed", "Staged", "Unstaged", "Untracked"):
            self.assertIn(category, _text(REPOSITORY_STATE_POLICY))

    def test_dedup_discovery_reference_present_in_step_6(self) -> None:
        # The runbook points to repository-instructions.md's "Deduplicated
        # discovery" procedure rather than restating its mechanics; the
        # full "compute the union of candidate paths" text lives only in
        # that policy (checked in RepositoryInstructionsDedupPolicyTests
        # below via test_dedup_is_scoped_to_retrieval_order_only).
        self.assertIn("Deduplicated discovery", self.text)
        self.assertIn(
            "compute the union of candidate instruction-file paths across "
            "every changed file's directory ancestry",
            _text(REPOSITORY_INSTRUCTIONS_POLICY),
        )

    def test_dedup_discovery_still_happens_before_review(self) -> None:
        self.assertIn(
            "Do this before reviewing so discovered conventions inform the "
            "review itself, not just a post-hoc check",
            self.text,
        )

    def test_runbook_points_to_repository_state_for_category_detection(self) -> None:
        # The full per-category command table lives only in the policy.
        self.assertIn("Detection commands per category", self.text)
        self.assertIn(
            "git ls-files --others --exclude-standard",
            _text(REPOSITORY_STATE_POLICY),
        )
        self.assertNotIn(
            "git ls-files --others --exclude-standard", self.text
        )

    def test_push_sync_status_section_exists_in_repository_state(self) -> None:
        self.assertIn("## Push / synchronization status", _text(REPOSITORY_STATE_POLICY))


class ReReviewShortCircuitTests(unittest.TestCase):
    """The complete fingerprint precondition/comparison contract is owned
    by repository-state.md (Git-mechanics/state-interpretation policy per
    AGENTS.md's runbook-design rule); the runbook only points to it."""

    def setUp(self) -> None:
        self.policy_text = _text(REPOSITORY_STATE_POLICY)
        self.runbook_text = _text(RUNBOOK)

    def test_fingerprint_match_short_circuit_is_explicit_and_testable(self) -> None:
        self.assertIn(
            "this is a safe, testable short-circuit: skip re-deriving "
            "review reasoning for the staged category from scratch",
            self.policy_text,
        )

    def test_short_circuit_still_requires_blocking_finding_reverification(
        self,
    ) -> None:
        self.assertIn(
            "spend that effort verifying whether each previously reported "
            "blocking finding in the staged delta was actually resolved",
            self.policy_text,
        )

    def test_short_circuit_does_not_suppress_new_findings(self) -> None:
        self.assertIn(
            "a newly discovered P0/P1 in that same staged delta (found "
            "while verifying) is still reported",
            self.policy_text,
        )

    def test_fingerprint_differ_case_still_requires_full_review(self) -> None:
        self.assertIn(
            "the staged delta changed and must be reviewed as new",
            self.policy_text,
        )

    def test_unstaged_untracked_unaffected_by_staged_fingerprint(self) -> None:
        # Pre-existing invariant this optimization must not weaken.
        self.assertIn(
            "The fingerprint must never be used to conclude that unstaged "
            "or untracked state is unchanged",
            self.policy_text,
        )

    def test_content_fingerprint_match_alone_is_explicitly_insufficient(self) -> None:
        # A matching content fingerprint must not, by itself, license
        # reusing prior reasoning if the review standard changed.
        self.assertIn(
            "A matching content fingerprint is not by itself sufficient "
            "to reuse prior reasoning",
            self.policy_text,
        )

    def test_precondition_enumerates_skill_and_shared_policy_surface(self) -> None:
        for surface in (
            "this Skill's own",  # SKILL.md
            "the runbook",
            "this Skill's own policies",
            "the shared review policies",
            "the target repository's own applicable instructions",
        ):
            self.assertIn(surface, self.policy_text)
        for shared_policy in (
            "review-scope.md",
            "severity.md",
            "evidence.md",
            "repository-instructions.md",
            "git-safety.md",
            "file-reviewability.md",
            "review-ownership.md",
        ):
            self.assertIn(shared_policy, self.policy_text)
        self.assertIn("AGENTS.md", self.policy_text)
        self.assertIn("CLAUDE.md", self.policy_text)

    def test_precondition_failure_is_treated_as_a_fingerprint_differ(self) -> None:
        self.assertIn("Precondition not established", self.policy_text)
        self.assertIn(
            "treat this exactly as a fingerprint difference: review the "
            "staged category as new content under the current standard",
            self.policy_text,
        )

    def test_precondition_does_not_require_a_new_persisted_fingerprint(self) -> None:
        # Smallest robust design: this is an orchestrator responsibility,
        # not a new cryptographic mechanism owned by this Skill.
        self.assertIn(
            "This does not require a new persisted cryptographic "
            "fingerprint over those files",
            self.policy_text,
        )

    def test_precondition_does_not_weaken_existing_re_review_guarantees(self) -> None:
        self.assertIn(
            "never substitutes for re-verifying previously reported "
            "blocking findings, discovering new P0/P1s, or independently "
            "(re-)detecting unstaged/untracked state",
            self.policy_text,
        )

    def test_repository_state_policy_is_the_sole_canonical_owner(self) -> None:
        self.assertIn(
            "This policy is the single canonical owner of the complete "
            "fingerprint-comparison contract",
            self.policy_text,
        )
        # The old two-way deferral (policy -> runbook -> policy) must not
        # come back: the runbook must not claim to own this contract.
        self.assertNotIn(
            "single canonical owner of that precondition", self.runbook_text
        )

    def test_runbook_points_to_repository_state_policy_without_restating_it(
        self,
    ) -> None:
        self.assertIn(
            "Fingerprint scope and re-review comparison", self.runbook_text
        )
        self.assertIn(
            "That policy is the single canonical owner of this contract; "
            "this runbook does not duplicate it",
            self.runbook_text,
        )
        # The detailed Match/Differ/precondition-not-established prose
        # itself must live only in the policy, not be copy-pasted here too.
        self.assertNotIn(
            "this is a safe, testable short-circuit", self.runbook_text
        )


class RepositoryInstructionsDedupPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(REPOSITORY_INSTRUCTIONS_POLICY)

    def test_dedup_section_exists(self) -> None:
        self.assertIn("## Deduplicated discovery", self.text)

    def test_dedup_is_scoped_to_retrieval_order_only(self) -> None:
        self.assertIn(
            "This is a pure retrieval-order optimization: it must discover "
            "and apply the identical set of instruction files to the "
            "identical set of changed files as reading per-file would",
            self.text,
        )

    def test_dedup_never_skips_an_unchecked_path(self) -> None:
        self.assertIn(
            "it only removes redundant reads of a path already read for "
            "this invocation, never a path that has not yet been checked",
            self.text,
        )

    def test_directory_scoped_discovery_invariant_still_present(self) -> None:
        # Pre-existing invariant this optimization must not weaken.
        self.assertIn(
            "Do not apply one directory's instructions to files outside "
            "that directory's ancestry",
            self.text,
        )


class FileReviewabilityShortCircuitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(FILE_REVIEWABILITY_POLICY)

    def test_scope_of_applicability_section_exists(self) -> None:
        self.assertIn("## Scope of applicability (safe short-circuit)", self.text)

    def test_short_circuit_condition_is_evidence_based_not_by_extension(self) -> None:
        self.assertIn(
            "per the classification rule above: never by extension alone",
            self.text,
        )

    def test_short_circuit_never_narrows_completeness_invariant(self) -> None:
        self.assertIn(
            "it never narrows the Completeness invariant below, which "
            "still governs every changed file regardless of type",
            self.text,
        )

    def test_snapshots_is_included_in_the_short_circuit_enumeration(self) -> None:
        # F4: the enumerated list must name all six type-specific
        # sections in this file, not just five of them — Snapshots is a
        # real "## Snapshots" section below and must not be silently
        # excluded from (or left ambiguous about) the same short-circuit.
        self.assertIn(
            "Generated files, Vendored dependencies, Manifests and "
            "lockfiles, Minified files and bundles, Binary files, and "
            "Snapshots",
            self.text,
        )
        self.assertIn(
            "All six type-specific sections below are covered by this "
            "same short-circuit",
            self.text,
        )

    def test_snapshots_section_itself_still_exists_and_is_unweakened(self) -> None:
        # Pre-existing invariant this optimization must not weaken: a
        # snapshot file that IS present in the delta still gets the full
        # investigative treatment this section already required.
        self.assertIn("## Snapshots", self.text)
        self.assertIn(
            "Massive or unexplained snapshot churn requires investigation "
            "rather than automatic acceptance",
            self.text,
        )

    def test_completeness_invariant_still_present_and_unweakened(self) -> None:
        # Pre-existing invariant this optimization must not weaken.
        self.assertIn(
            "Every changed file remains in review scope", self.text
        )
        self.assertIn(
            "must not silently omit generated, vendored, minified, "
            "binary, snapshot, lock, documentation, manifest, or "
            "package-artifact changes",
            self.text,
        )


class SkillMdBatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(SKILL_MD)

    def test_parallel_load_note_present(self) -> None:
        self.assertIn(
            "None of the files above depend on another's content to be "
            "read — load them together in a single batched/parallel "
            "operation rather than one at a time in sequence",
            self.text,
        )

    def test_all_required_policies_still_listed(self) -> None:
        for policy in (
            "review-scope.md",
            "severity.md",
            "evidence.md",
            "repository-instructions.md",
            "git-safety.md",
            "file-reviewability.md",
        ):
            self.assertIn(policy, self.text)

    def test_conditional_policies_still_conditional(self) -> None:
        self.assertIn("In orchestrated/ multi-Agent contexts, also", self.text)
        self.assertIn(
            "This policy is never loaded or applied when no PR reference "
            "is supplied",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
