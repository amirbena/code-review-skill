"""Regression tests for the #119 stacked-PR review reference model.

Exercises tests/reference/review/stacked_pr_topology.py against
docs/findings/stacked-pr-review-contract.md's acceptance criteria and
required examples (A-G): owned-vs-inherited delta scoping in a multi-layer
stack, the partial-vs-full re-review decision when a lower layer changes,
and the two-tier safe-failure fallback for ambiguous/broken topology.
"""

import unittest

from tests.reference.review.delta_re_review import BlastRadiusClaim
from tests.reference.review.stacked_pr_topology import (
    ReReviewTrigger,
    SafeFailureTier,
    StackLayer,
    classify_lower_layer_change,
    inherited_delta_is_context_only,
    owned_delta_range,
    resolve_stack,
    squash_merge_desync,
)


def _three_layer_stack() -> dict:
    """root(main) -> PR A -> PR B -> PR C, per contract §3's worked example."""
    return {
        "A": StackLayer(identity="A", base_identity=None, head_sha="A0", base_is_root=True),
        "B": StackLayer(identity="B", base_identity="A", head_sha="B0"),
        "C": StackLayer(identity="C", base_identity="B", head_sha="C0"),
    }


class EffectiveBaseSelectionTests(unittest.TestCase):
    """Contract §2: effective base is the declared parent, never the root
    merely by default."""

    def test_layer_one_base_is_root(self) -> None:
        layers = _three_layer_stack()
        resolution = resolve_stack(layers, start="A")
        self.assertEqual(resolution.tier, SafeFailureTier.NONE)
        self.assertEqual(resolution.effective_base_identity, "main")
        self.assertIsNone(resolution.effective_base_head)

    def test_layer_two_effective_base_is_layer_one_head_not_root(self) -> None:
        layers = _three_layer_stack()
        resolution = resolve_stack(layers, start="B")
        self.assertEqual(resolution.tier, SafeFailureTier.NONE)
        self.assertEqual(resolution.effective_base_identity, "A")
        self.assertEqual(resolution.effective_base_head, "A0")
        self.assertNotEqual(resolution.effective_base_identity, "main")

    def test_layer_three_chain_walks_to_root(self) -> None:
        layers = _three_layer_stack()
        resolution = resolve_stack(layers, start="C")
        self.assertEqual(resolution.tier, SafeFailureTier.NONE)
        self.assertEqual(resolution.chain, ("A", "B", "C"))
        self.assertEqual(resolution.effective_base_identity, "B")
        self.assertEqual(resolution.effective_base_head, "B0")


class OwnedVsInheritedDeltaTests(unittest.TestCase):
    """Contract §3: owned delta uses the effective base; inherited delta is
    context-only unless a blast-radius attribution reaches it. Example A."""

    def test_owned_delta_range_uses_effective_base_not_root(self) -> None:
        layers = _three_layer_stack()
        resolution = resolve_stack(layers, start="B")
        rng = owned_delta_range(resolution.effective_base_head, layers["B"].head_sha)
        self.assertEqual(rng, ("A0", "B0"))

    def test_inherited_content_is_context_only_absent_attribution(self) -> None:
        self.assertTrue(inherited_delta_is_context_only(causal_attribution=None))
        self.assertTrue(
            inherited_delta_is_context_only(
                causal_attribution=BlastRadiusClaim(causal_mechanism=None, source_changed=False)
            )
        )

    def test_inherited_content_becomes_reportable_with_attribution(self) -> None:
        claim = BlastRadiusClaim(
            causal_mechanism="B's new code calls A's helper through a new path",
            source_changed=True,
        )
        self.assertFalse(inherited_delta_is_context_only(causal_attribution=claim))


class LowerLayerChangeTriggerTests(unittest.TestCase):
    """Contract §5. Examples B, C, D."""

    def test_no_interaction_no_ancestry_break_requires_no_rereview(self) -> None:
        # Example B: A advances, B's owned delta has no blast-radius link.
        trigger = classify_lower_layer_change(
            ancestry_broken=False, blast_radius_attributable=False
        )
        self.assertEqual(trigger, ReReviewTrigger.NONE)

    def test_blast_radius_interaction_triggers_partial_rereview(self) -> None:
        # Example C: A's new commits touch a shared interface B calls.
        trigger = classify_lower_layer_change(
            ancestry_broken=False, blast_radius_attributable=True
        )
        self.assertEqual(trigger, ReReviewTrigger.PARTIAL_BLAST_RADIUS)

    def test_ancestry_break_escalates_to_full_review_regardless_of_blast_radius(
        self,
    ) -> None:
        # Example D: A rebased; recorded head no longer an ancestor.
        trigger = classify_lower_layer_change(
            ancestry_broken=True, blast_radius_attributable=False
        )
        self.assertEqual(trigger, ReReviewTrigger.FULL_ESCALATION)
        trigger_both = classify_lower_layer_change(
            ancestry_broken=True, blast_radius_attributable=True
        )
        self.assertEqual(trigger_both, ReReviewTrigger.FULL_ESCALATION)


class SafeFailureTierTests(unittest.TestCase):
    """Contract §6. Examples E, F, G."""

    def test_ambiguous_merge_base_is_tier_one(self) -> None:
        # Example E.
        layers = _three_layer_stack()
        resolution = resolve_stack(layers, start="B", ambiguous_merge_base=True)
        self.assertEqual(resolution.tier, SafeFailureTier.TIER1_SINGLE_HOP)
        self.assertEqual(resolution.effective_base_identity, "A")

    def test_unresolved_chain_hop_is_tier_one(self) -> None:
        layers = _three_layer_stack()
        resolution = resolve_stack(layers, start="C", unresolved_chain_hop=True)
        self.assertEqual(resolution.tier, SafeFailureTier.TIER1_SINGLE_HOP)
        # Still resolves the immediate base correctly, just does not walk
        # further up the chain.
        self.assertEqual(resolution.effective_base_identity, "B")

    def test_cyclic_topology_is_tier_two_root_fallback(self) -> None:
        # Example G.
        layers = {
            "X": StackLayer(identity="X", base_identity="Y", head_sha="X0"),
            "Y": StackLayer(identity="Y", base_identity="X", head_sha="Y0"),
        }
        resolution = resolve_stack(layers, start="X", cyclic=True)
        self.assertEqual(resolution.tier, SafeFailureTier.TIER2_ROOT_FALLBACK)
        self.assertEqual(resolution.effective_base_identity, "main")
        self.assertIn("cyclic", resolution.note)

    def test_self_referential_chain_detected_without_explicit_flag(self) -> None:
        # A malformed chain that cycles even when the caller did not
        # pre-flag it: the walker itself must detect the revisit.
        layers = {
            "X": StackLayer(identity="X", base_identity="Y", head_sha="X0"),
            "Y": StackLayer(identity="Y", base_identity="X", head_sha="Y0"),
        }
        resolution = resolve_stack(layers, start="X")
        self.assertEqual(resolution.tier, SafeFailureTier.TIER2_ROOT_FALLBACK)

    def test_ordinary_merge_of_lower_pr_is_not_a_desync(self) -> None:
        tier = squash_merge_desync(lower_pr_merged=True, lower_pr_merge_strategy="merge")
        self.assertEqual(tier, SafeFailureTier.NONE)

    def test_unmerged_lower_pr_is_not_a_desync(self) -> None:
        tier = squash_merge_desync(lower_pr_merged=False, lower_pr_merge_strategy="squash")
        self.assertEqual(tier, SafeFailureTier.NONE)

    def test_squash_merged_lower_pr_is_tier_two(self) -> None:
        # Example F.
        tier = squash_merge_desync(lower_pr_merged=True, lower_pr_merge_strategy="squash")
        self.assertEqual(tier, SafeFailureTier.TIER2_ROOT_FALLBACK)

    def test_rebase_merged_lower_pr_is_tier_two(self) -> None:
        tier = squash_merge_desync(lower_pr_merged=True, lower_pr_merge_strategy="rebase")
        self.assertEqual(tier, SafeFailureTier.TIER2_ROOT_FALLBACK)


if __name__ == "__main__":
    unittest.main()
