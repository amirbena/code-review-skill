"""Genuine end-to-end stacked-PR review scenario (#119).

Unlike test_stacked_pr_topology.py (pure-function reference-model
regression tests over synthetic StackLayer descriptions), this exercises
the real mechanics `github-pr-review`'s packaged runtime uses: an actual
`main -> PR A -> PR B` git topology (tests/support/pr_simulation.py), the
same repository-backed checkout lifecycle
(tests/reference/review/pr_checkout.py, mirroring
skills/github-pr-review/policies/repository-checkout.md) that produces the
owned delta a real review scopes findings to, and the stack-topology
classification (tests/reference/review/stacked_pr_topology.py, mirroring
skills/github-pr-review/policies/stacked-pr-review.md).

This is the "real main -> PR A -> PR B stacked-review path" required by
Issue #119's runtime acceptance criteria: it proves that scoping PR B's
review against the effective base (PR A's head) — not the root — actually
changes what a real git checkout's owned delta contains, and that a
PR based directly on the root (PR A itself) takes the byte-for-byte
unchanged, non-stacked path.
"""

import unittest

from tests.reference.review.pr_checkout import prepare_repository_checkout
from tests.reference.review.stacked_pr_topology import (
    SafeFailureTier,
    StackLayer,
    resolve_stack,
)
from tests.support.pr_simulation import simulated_stacked_pr


class StackedReviewEndToEndTests(unittest.TestCase):
    """A real `main -> PR A -> PR B` stack, checked out with the same
    lifecycle the packaged Skill's repository-checkout policy specifies."""

    def test_owned_delta_for_pr_b_excludes_pr_a_when_scoped_to_effective_base(
        self,
    ) -> None:
        """The #119 fix: PR B's owned delta, computed against the effective
        review base (PR A's head), contains only PR B's own commit."""
        with simulated_stacked_pr() as stack:
            source = stack.pr_b_source_against_effective_base()
            with prepare_repository_checkout(source) as handle:
                changed = handle.changed_files()
                self.assertEqual(tuple(sorted(changed)), stack.pr_b_files)
                self.assertNotIn("a.txt", changed)

    def test_owned_delta_for_pr_b_wrongly_includes_pr_a_when_scoped_to_root(
        self,
    ) -> None:
        """Regression guard for the bug Issue #119 describes: scoping PR B
        against the repository root instead of the effective base inflates
        the delta with PR A's already-reviewed changes — proving the fix
        in the previous test actually matters, not merely a no-op
        alternate code path."""
        with simulated_stacked_pr() as stack:
            source = stack.pr_b_source_against_root_bug()
            with prepare_repository_checkout(source) as handle:
                changed = handle.changed_files()
                self.assertIn("a.txt", changed)
                self.assertIn("b.txt", changed)
                self.assertEqual(len(changed), 2)

    def test_non_stacked_pr_a_checkout_is_unaffected(self) -> None:
        """PR A itself is based directly on the root: its owned delta is
        exactly its own commit, computed exactly as any ordinary,
        non-stacked PR — proving the non-stacked path stays unchanged."""
        with simulated_stacked_pr() as stack:
            source = stack.pr_a_source()
            with prepare_repository_checkout(source) as handle:
                changed = handle.changed_files()
                self.assertEqual(tuple(changed), stack.pr_a_files)

    def test_topology_classification_agrees_with_the_real_git_shape(self) -> None:
        """The pure-function topology classifier (stacked_pr_topology.py),
        fed the real SHAs from this real git topology, resolves PR B's
        effective base to PR A's head — not main — matching the checkout
        behavior proven above. This ties the reference model's
        classification to the same real repository state the checkout
        mechanics operate on, rather than only a synthetic description."""
        with simulated_stacked_pr() as stack:
            layers = {
                "pr-a": StackLayer(
                    identity="pr-a",
                    base_identity=None,
                    head_sha=stack.pr_a_head_sha,
                    base_is_root=True,
                ),
                "pr-b": StackLayer(
                    identity="pr-b",
                    base_identity="pr-a",
                    head_sha=stack.pr_b_head_sha,
                ),
            }
            resolution = resolve_stack(layers, start="pr-b", root_identity="main")
            self.assertEqual(resolution.tier, SafeFailureTier.NONE)
            self.assertEqual(resolution.chain, ("pr-a", "pr-b"))
            self.assertEqual(resolution.effective_base_identity, "pr-a")
            self.assertEqual(resolution.effective_base_head, stack.pr_a_head_sha)
            self.assertNotEqual(resolution.effective_base_head, stack.main_sha)

    def test_inherited_delta_from_pr_a_is_readable_as_context_from_pr_b_checkout(
        self,
    ) -> None:
        """PR A's file is still present and readable in PR B's checkout —
        available as Repository Context (readable for understanding) even
        though it is excluded from PR B's owned delta/findings scope."""
        with simulated_stacked_pr() as stack:
            source = stack.pr_b_source_against_effective_base()
            with prepare_repository_checkout(source) as handle:
                # a.txt (PR A's owned delta) is absent from PR B's changed
                # files (it is not PR B's finding scope) ...
                self.assertNotIn("a.txt", handle.changed_files())
                # ... but still readable in the checkout as Repository
                # Context, per stacked-pr-review.md §3 / review-context.md.
                self.assertEqual(handle.read_file("a.txt"), "A's change\n")
                self.assertEqual(handle.read_file("b.txt"), "B's change\n")


if __name__ == "__main__":
    unittest.main()
