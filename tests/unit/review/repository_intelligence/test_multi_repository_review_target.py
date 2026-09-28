"""Regression tests for the #556 multi-repository Review Target
composition reference model.

Exercises tests/reference/review/multi_repository_review_target.py against
skills/local-code-review/policies/multi-repository-review-target.md's
contract: root validation/normalization (including fail-closed
duplicate/alias detection), independent per-member resolution and
composition, unresolved-member narrowing, instruction isolation, sibling-
member ring-expansion admission, and repository-qualified location
rendering.
"""

from __future__ import annotations

import unittest

from tests.reference.review.multi_repository_review_target import (
    DuplicateRootConflict,
    MemberResolution,
    MemberUnresolvedReason,
    RootFact,
    RootRejectionReason,
    compose_review_target,
    derive_aliases,
    instruction_applies_to_file,
    render_location,
    resolve_effective_membership,
    ring_expansion_target_is_admitted,
    validate_and_normalize_roots,
)


class RootValidationTests(unittest.TestCase):
    """§"Validation and normalization of supplied roots"."""

    def test_two_clean_roots_both_validate(self) -> None:
        facts = [
            RootFact("../a", exists=True, is_git_repository=True, normalized_root="/repos/a"),
            RootFact("../b", exists=True, is_git_repository=True, normalized_root="/repos/b"),
        ]
        result = validate_and_normalize_roots(facts)
        self.assertTrue(result.ok)
        self.assertEqual(result.valid_roots, ("/repos/a", "/repos/b"))
        self.assertEqual(result.rejected_roots, ())

    def test_nonexistent_root_is_rejected_not_a_whole_input_failure(self) -> None:
        facts = [
            RootFact("../a", exists=True, is_git_repository=True, normalized_root="/repos/a"),
            RootFact("../missing", exists=False, is_git_repository=False),
        ]
        result = validate_and_normalize_roots(facts)
        self.assertTrue(result.ok)
        self.assertEqual(result.valid_roots, ("/repos/a",))
        self.assertEqual(len(result.rejected_roots), 1)
        self.assertEqual(result.rejected_roots[0].reason, RootRejectionReason.DOES_NOT_EXIST)

    def test_non_git_directory_is_rejected(self) -> None:
        facts = [RootFact("../not-a-repo", exists=True, is_git_repository=False)]
        result = validate_and_normalize_roots(facts)
        self.assertTrue(result.ok)
        self.assertEqual(result.valid_roots, ())
        self.assertEqual(result.rejected_roots[0].reason, RootRejectionReason.NOT_A_GIT_REPOSITORY)

    def test_duplicate_normalized_root_fails_the_whole_input_closed(self) -> None:
        facts = [
            RootFact("./a", exists=True, is_git_repository=True, normalized_root="/repos/a"),
            RootFact("a/../a", exists=True, is_git_repository=True, normalized_root="/repos/a"),
        ]
        result = validate_and_normalize_roots(facts)
        self.assertFalse(result.ok)
        self.assertEqual(result.valid_roots, ())
        self.assertEqual(result.rejected_roots, ())
        self.assertEqual(len(result.duplicate_conflicts), 1)
        conflict = result.duplicate_conflicts[0]
        self.assertIsInstance(conflict, DuplicateRootConflict)
        self.assertEqual(conflict.supplied_paths, ("./a", "a/../a"))

    def test_two_worktrees_of_one_repository_are_a_duplicate_via_common_dir(self) -> None:
        # Distinct normalized roots (two worktree checkouts) but the same
        # Git common directory — still one repository, still fail closed.
        facts = [
            RootFact(
                "../a-worktree-1",
                exists=True,
                is_git_repository=True,
                normalized_root="/repos/a-1",
                git_common_dir="/repos/a/.git",
            ),
            RootFact(
                "../a-worktree-2",
                exists=True,
                is_git_repository=True,
                normalized_root="/repos/a-2",
                git_common_dir="/repos/a/.git",
            ),
        ]
        result = validate_and_normalize_roots(facts)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.duplicate_conflicts), 1)

    def test_unrelated_repositories_with_the_same_common_dir_shape_do_not_collide(self) -> None:
        facts = [
            RootFact("../a", exists=True, is_git_repository=True, normalized_root="/repos/a", git_common_dir="/repos/a/.git"),
            RootFact("../b", exists=True, is_git_repository=True, normalized_root="/repos/b", git_common_dir="/repos/b/.git"),
        ]
        result = validate_and_normalize_roots(facts)
        self.assertTrue(result.ok)
        self.assertEqual(result.valid_roots, ("/repos/a", "/repos/b"))


class AliasDerivationTests(unittest.TestCase):
    def test_distinct_basenames_get_their_basename(self) -> None:
        aliases = derive_aliases(["/repos/backend", "/repos/frontend"])
        self.assertEqual(aliases, {"/repos/backend": "backend", "/repos/frontend": "frontend"})

    def test_colliding_basenames_are_disambiguated_never_identical(self) -> None:
        aliases = derive_aliases(["/org-a/service", "/org-b/service"])
        self.assertEqual(len(set(aliases.values())), 2)
        self.assertNotEqual(aliases["/org-a/service"], aliases["/org-b/service"])


class ComposeReviewTargetTests(unittest.TestCase):
    """§"Composition into one combined Review Target" and
    §"Unresolved-member narrowing"."""

    def test_all_members_resolved(self) -> None:
        resolutions = [
            MemberResolution("/repos/a", resolved=True, base="main", branch="feat/x"),
            MemberResolution("/repos/b", resolved=True, base="main", branch="feat/x"),
        ]
        combined = compose_review_target(resolutions)
        self.assertEqual(len(combined.resolved_members), 2)
        self.assertEqual(combined.unresolved_members, ())
        self.assertFalse(combined.is_empty)

    def test_unresolved_member_narrows_never_fails_whole_review(self) -> None:
        resolutions = [
            MemberResolution("/repos/a", resolved=True, base="main"),
            MemberResolution(
                "/repos/b",
                resolved=False,
                unresolved_reason=MemberUnresolvedReason.BASE_UNRESOLVED,
            ),
        ]
        combined = compose_review_target(resolutions)
        self.assertEqual(len(combined.resolved_members), 1)
        self.assertEqual(combined.resolved_members[0].root, "/repos/a")
        self.assertEqual(len(combined.unresolved_members), 1)
        self.assertEqual(
            combined.unresolved_members[0].unresolved_reason,
            MemberUnresolvedReason.BASE_UNRESOLVED,
        )

    def test_no_synthetic_shared_base_across_members(self) -> None:
        resolutions = [
            MemberResolution("/repos/a", resolved=True, base="main"),
            MemberResolution("/repos/b", resolved=True, base="develop"),
        ]
        combined = compose_review_target(resolutions)
        bases = {member.base for member in combined.resolved_members}
        # Each member keeps its own base; nothing collapses them into one.
        self.assertEqual(bases, {"main", "develop"})

    def test_member_with_no_delta_is_reported_clean_not_dropped(self) -> None:
        resolutions = [
            MemberResolution("/repos/a", resolved=True, base="main"),
            MemberResolution("/repos/b", resolved=True, base="main"),  # clean member
        ]
        combined = compose_review_target(resolutions)
        self.assertEqual(len(combined.resolved_members), 2)

    def test_n_equals_one_regression_single_member_behaves_as_before(self) -> None:
        # A single supplied member composes to exactly one resolved member
        # and no unresolved entries — the N=1 shape this module never
        # activates for in practice (the policy is not even loaded), but
        # the composition function itself degrades cleanly.
        resolutions = [MemberResolution("/repos/only", resolved=True, base="main")]
        combined = compose_review_target(resolutions)
        self.assertEqual(len(combined.resolved_members), 1)
        self.assertEqual(combined.unresolved_members, ())


class InstructionIsolationTests(unittest.TestCase):
    """§"Instruction isolation"."""

    def test_instructions_apply_within_owning_member(self) -> None:
        self.assertTrue(
            instruction_applies_to_file(
                instruction_owner_root="/repos/a", file_member_root="/repos/a"
            )
        )

    def test_instructions_never_apply_to_a_sibling_member(self) -> None:
        self.assertFalse(
            instruction_applies_to_file(
                instruction_owner_root="/repos/a", file_member_root="/repos/b"
            )
        )


class RingExpansionAdmissionTests(unittest.TestCase):
    """§"Ring expansion into a sibling member"."""

    def test_sibling_member_is_an_admitted_investigation_target(self) -> None:
        self.assertTrue(
            ring_expansion_target_is_admitted(
                target_root="/repos/b", admitted_member_roots=("/repos/a", "/repos/b")
            )
        )

    def test_non_member_repository_is_never_admitted(self) -> None:
        self.assertFalse(
            ring_expansion_target_is_admitted(
                target_root="/repos/unrelated", admitted_member_roots=("/repos/a", "/repos/b")
            )
        )


class LocationRenderingTests(unittest.TestCase):
    """§"Finding location with structural repository identity"."""

    def test_multi_repository_location_carries_leading_alias(self) -> None:
        self.assertEqual(
            render_location(repo_alias="backend", path="src/app.py", line_or_range="12"),
            "backend:src/app.py:12",
        )

    def test_single_repository_location_is_unchanged(self) -> None:
        self.assertEqual(
            render_location(repo_alias=None, path="src/app.py", line_or_range="12"),
            "src/app.py:12",
        )


class MembershipAuthorizationTests(unittest.TestCase):
    """§"Security: membership cannot be expanded from inside" — see also
    tests/unit/security/test_multi_repository_membership.py for the
    dedicated security-boundary suite."""

    def test_only_explicit_roots_become_members(self) -> None:
        members = resolve_effective_membership(
            explicit_supplied_roots=("/repos/a", "/repos/b")
        )
        self.assertEqual(members, ("/repos/a", "/repos/b"))

    def test_content_suggested_roots_are_ignored(self) -> None:
        members = resolve_effective_membership(
            explicit_supplied_roots=("/repos/a",),
            content_suggested_roots=("/repos/attacker-controlled",),
        )
        self.assertEqual(members, ("/repos/a",))
        self.assertNotIn("/repos/attacker-controlled", members)


if __name__ == "__main__":
    unittest.main()
