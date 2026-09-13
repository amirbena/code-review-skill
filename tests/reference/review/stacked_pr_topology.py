#!/usr/bin/env python3
"""Test-only reference for stacked/dependent PR review topology (Issue #119).

Not runtime logic, not packaged — the packaged Skills are Markdown/YAML
only, matching tests/reference/review/delta_re_review.py's own framing. No
packaged Skill resource depends on this module or on
docs/findings/stacked-pr-review-contract.md.

Mirrors docs/findings/stacked-pr-review-contract.md: effective review-base
selection (contract §2), owned-vs-inherited delta classification (§3),
the partial-vs-full re-review trigger for a lower-layer change (§5), and
the two-tier safe-failure fallback for ambiguous/broken topology (§6).

Consumes the #64 blast-radius vocabulary (BlastRadiusClaim / is_attributable
from delta_re_review.py) rather than re-deriving it — this module adds no
second blast-radius model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from tests.reference.review.delta_re_review import BlastRadiusClaim, is_attributable


class SafeFailureTier(Enum):
    """Contract §6: the two-tier safe-failure fallback. ``NONE`` means the
    stack resolved cleanly and no fallback is needed."""

    NONE = "none"
    TIER1_SINGLE_HOP = "tier1_single_hop"
    TIER2_ROOT_FALLBACK = "tier2_root_fallback"


class ReReviewTrigger(Enum):
    """Contract §5: the outcome of a lower-layer change on the upper
    layer's reviewed state."""

    NONE = "none"
    PARTIAL_BLAST_RADIUS = "partial_blast_radius"
    FULL_ESCALATION = "full_escalation"


@dataclass(frozen=True)
class StackLayer:
    """One PR in a candidate stack, as declared (not yet validated).

    ``base_is_root`` is true only for the layer whose declared base is the
    repository's default/target branch (contract §1, "Root").
    """

    identity: str
    base_identity: Optional[str]  # None only when base_is_root
    head_sha: str
    base_is_root: bool = False


@dataclass(frozen=True)
class TopologyResolution:
    """Contract §2/§6: the outcome of resolving one layer's effective base."""

    tier: SafeFailureTier
    chain: tuple = field(default_factory=tuple)  # root -> ... -> layer identities
    effective_base_identity: Optional[str] = None
    effective_base_head: Optional[str] = None
    note: str = ""


def resolve_stack(
    layers: dict,
    *,
    start: str,
    root_identity: str = "main",
    ambiguous_merge_base: bool = False,
    cyclic: bool = False,
    unresolved_chain_hop: bool = False,
) -> TopologyResolution:
    """Contract §2 (effective base selection) and §6 (safe-failure tiers).

    ``layers`` maps identity -> StackLayer. ``start`` is the layer under
    review. Returns the resolved chain and which safe-failure tier (if any)
    applied. This function only classifies a synthetic topology description
    — it makes no GitHub API calls and detects nothing about a real
    repository.
    """
    if cyclic:
        return TopologyResolution(
            tier=SafeFailureTier.TIER2_ROOT_FALLBACK,
            chain=(),
            effective_base_identity=root_identity,
            note="topology undetermined: cyclic chain",
        )

    if ambiguous_merge_base:
        current = layers[start]
        return TopologyResolution(
            tier=SafeFailureTier.TIER1_SINGLE_HOP,
            chain=(start,),
            effective_base_identity=current.base_identity,
            effective_base_head=(
                layers[current.base_identity].head_sha
                if current.base_identity in layers
                else None
            ),
            note="single-hop fallback: merge-base ambiguous beyond immediate base",
        )

    if unresolved_chain_hop:
        current = layers[start]
        return TopologyResolution(
            tier=SafeFailureTier.TIER1_SINGLE_HOP,
            chain=(start,),
            effective_base_identity=current.base_identity,
            effective_base_head=(
                layers[current.base_identity].head_sha
                if current.base_identity in layers
                else None
            ),
            note="single-hop fallback: could not confirm parent is an open PR",
        )

    # Walk the declared chain upward from `start` to the root.
    chain: list = []
    node = layers[start]
    visited = set()
    while True:
        chain.append(node.identity)
        if node.identity in visited:
            return TopologyResolution(
                tier=SafeFailureTier.TIER2_ROOT_FALLBACK,
                chain=(),
                effective_base_identity=root_identity,
                note="topology undetermined: cyclic chain",
            )
        visited.add(node.identity)
        if node.base_is_root:
            break
        if node.base_identity not in layers:
            # Base branch does not correspond to a known open PR: treat it
            # as the effective base without walking further (§2 step 3).
            break
        node = layers[node.base_identity]

    chain.reverse()
    current = layers[start]
    effective_base_identity = current.base_identity if not current.base_is_root else root_identity
    effective_base_head = (
        layers[current.base_identity].head_sha
        if (not current.base_is_root and current.base_identity in layers)
        else None
    )
    return TopologyResolution(
        tier=SafeFailureTier.NONE,
        chain=tuple(chain),
        effective_base_identity=effective_base_identity,
        effective_base_head=effective_base_head,
    )


def squash_merge_desync(
    *, lower_pr_merged: bool, lower_pr_merge_strategy: str
) -> SafeFailureTier:
    """Contract §6, "Closed or merged lower PR": a squash/rebase merge of
    the lower layer breaks the upper layer's ancestor relationship to the
    root; an ordinary/fast-forward merge does not."""
    if not lower_pr_merged:
        return SafeFailureTier.NONE
    if lower_pr_merge_strategy in ("squash", "rebase"):
        return SafeFailureTier.TIER2_ROOT_FALLBACK
    return SafeFailureTier.NONE


def owned_delta_range(effective_base_head: str, layer_head: str) -> tuple:
    """Contract §3: the owned delta is ordinary PR-delta math anchored on
    the effective base, never the root."""
    return (effective_base_head, layer_head)


def inherited_delta_is_context_only(*, causal_attribution: Optional[BlastRadiusClaim]) -> bool:
    """Contract §3: inherited-delta content is Repository Context, never a
    finding this layer owns, unless a #64 blast-radius attribution reaches
    it. Reuses delta_re_review.is_attributable rather than re-deriving it."""
    if causal_attribution is None:
        return True
    return not is_attributable(causal_attribution)


def classify_lower_layer_change(
    *,
    ancestry_broken: bool,
    blast_radius_attributable: bool,
) -> ReReviewTrigger:
    """Contract §5: partial vs. full re-review when a lower layer changes
    after the upper layer was reviewed."""
    if ancestry_broken:
        return ReReviewTrigger.FULL_ESCALATION
    if blast_radius_attributable:
        return ReReviewTrigger.PARTIAL_BLAST_RADIUS
    return ReReviewTrigger.NONE
