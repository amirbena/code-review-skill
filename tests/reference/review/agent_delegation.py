#!/usr/bin/env python3
"""Test-only reference for the agent-spawn / delegation capability gate.

Mirrors shared/policies/agent-delegation.md and composes with (never
duplicates) shared/policies/parallel-review.md's worker contract. Not
runtime logic, not packaged.

Core invariant, exactly as the policy states it::

    child_authority  ⊆  parent_authority  ∩  explicit_delegation

Deliberately reuses this repository's existing invocation/capability
identity model instead of inventing a second one:

* ``Provenance`` / ``classify_provenance`` / ``AGENT_CONTROLLED_CHANNELS``
  from :mod:`tests.reference.review.review_action_authorization` classify
  *how* a claimed authorization or identity reached this runtime — the
  same trust classification already used for GitHub mutation authority
  applies unchanged to the agent-spawn boundary.
* ``AuthorizationScope`` from the same module is reused as the narrow
  scope a single-use spawn/delegation authorization is bound to.

Everything here fails closed: any unrecognized, ambiguous, or
agent-controlled input resolves to denial, never to a grant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from tests.reference.review import review_action_authorization as raa


class Capability(str, Enum):
    """The capability vocabulary this gate reasons over. `spawn_agent`
    itself is a capability like any other — see agent-delegation.md,
    "`spawn_agent` is an explicit capability"."""

    SPAWN_AGENT = "spawn_agent"
    ANALYZE = "analyze"
    PUBLISH = "publish"
    MUTATE = "mutate"
    RUNTIME_VALIDATE = "runtime_validate"
    FORMAL_REVIEW_ACTION = "formal_review_action"


CapabilitySet = frozenset  # alias for readability; elements are Capability

# The default shallow-topology worker: analysis only. See
# agent-delegation.md, "Read-only worker capability set."
READ_ONLY_WORKER_CAPABILITIES: "frozenset[Capability]" = frozenset({Capability.ANALYZE})

# Never granted to a child by the ordinary delegation-intersection path,
# regardless of what the parent holds, what is requested, or what runtime
# policy would otherwise permit. "Non-transferable and non-inheritable by
# default" — agent-delegation.md, "Mutation and formal review-action
# authorization are non-transferable". A child that legitimately needs
# one requires a *separately issued* runtime capability (out of scope for
# this gate; see ISSUE_SEPARATE_RUNTIME_CAPABILITY below).
NON_TRANSFERABLE_CAPABILITIES: "frozenset[Capability]" = frozenset(
    {Capability.MUTATE, Capability.FORMAL_REVIEW_ACTION}
)


class SpawnDecision(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"


# Provisional security-event vocabulary, shared with
# docs/threat-model/catalog/spawn-delegation.yaml /
# scripts/security/validate_threat_model.py (#299 owns the authoritative
# taxonomy; these names are the same provisional strings that catalog
# already declares).
DENIED_SPAWN_UNAUTHORIZED = "DENIED_SPAWN_UNAUTHORIZED"
DENIED_SPAWN_BUDGET_EXCEEDED = "DENIED_SPAWN_BUDGET_EXCEEDED"
DENIED_SPAWN_DEPTH_EXCEEDED = "DENIED_SPAWN_DEPTH_EXCEEDED"
DENIED_DELEGATION_AUTHORITY_ESCALATION = "DENIED_DELEGATION_AUTHORITY_ESCALATION"
DENIED_DELEGATION_REPLAY = "DENIED_DELEGATION_REPLAY"


@dataclass(frozen=True)
class SpawnOutcome:
    decision: SpawnDecision
    granted_capabilities: "frozenset[Capability]"
    reason: Optional[str] = None
    security_event: Optional[str] = None

    @property
    def allowed(self) -> bool:
        return self.decision is SpawnDecision.ALLOWED


class InvocationBudget:
    """The one canonical, tree-wide accounting object for an invocation.

    Deliberately **not** re-created per parent: every node in the tree
    shares the same instance (by reference), so a nested spawn decrements
    the same pool the root's first spawn decremented — see
    agent-delegation.md, "One canonical accounting model, tree-wide."
    `max_agents_per_invocation` / `max_spawn_depth` are fixed at
    construction and never raised afterward (no public method mutates
    them) — budget exhaustion fails closed, it is never resolved by
    widening the limit.
    """

    def __init__(self, *, max_agents_per_invocation: int, max_spawn_depth: int) -> None:
        if max_agents_per_invocation < 1:
            raise ValueError("max_agents_per_invocation must allow at least the root")
        if max_spawn_depth < 0:
            raise ValueError("max_spawn_depth must be >= 0")
        self.max_agents_per_invocation = max_agents_per_invocation
        self.max_spawn_depth = max_spawn_depth
        # The root itself counts as one agent against the tree-wide budget.
        self.agent_count = 1

    def exhausted(self) -> bool:
        return self.agent_count >= self.max_agents_per_invocation

    def _record_spawn(self) -> None:
        self.agent_count += 1


@dataclass(frozen=True)
class AgentNode:
    """An agent's fixed, granted identity/capability state. Capabilities
    are frozen at spawn time — nothing recomputes or widens them later
    from shared state, a later request, or a claimed alternate identity.
    """

    identity: str
    capabilities: "frozenset[Capability]"
    depth: int
    budget: InvocationBudget


def make_root_agent(
    *, identity: str, capabilities: "frozenset[Capability]", budget: InvocationBudget
) -> AgentNode:
    return AgentNode(identity=identity, capabilities=frozenset(capabilities), depth=0, budget=budget)


def spawn_agent(
    parent: AgentNode,
    *,
    child_identity: str,
    requested_delegation: "frozenset[Capability]",
    runtime_policy: "frozenset[Capability]" = frozenset(
        {Capability.ANALYZE, Capability.PUBLISH, Capability.RUNTIME_VALIDATE, Capability.SPAWN_AGENT}
    ),
) -> SpawnOutcome:
    """Evaluate a spawn request. Fails closed on every denial path; grants
    exactly the delegation-intersection, minus the never-transferable set,
    on success — never more than that.

    ``runtime_policy`` models what the runtime is willing to permit at
    all, independent of the parent/child relationship (agent-delegation.md's
    third intersection term); its default is deliberately generous so a
    caller narrows it explicitly rather than this default silently hiding
    a real-world restriction.
    """

    # DELEG-001: no spawn_agent capability -> refused outright.
    if Capability.SPAWN_AGENT not in parent.capabilities:
        return SpawnOutcome(
            SpawnDecision.DENIED,
            frozenset(),
            "spawn_agent capability not granted",
            DENIED_SPAWN_UNAUTHORIZED,
        )

    # DELEG-003 / DELEG-004: depth is checked against the shared tree-wide
    # budget, not a per-parent counter, so nested spawning cannot evade it.
    child_depth = parent.depth + 1
    if child_depth > parent.budget.max_spawn_depth:
        return SpawnOutcome(
            SpawnDecision.DENIED,
            frozenset(),
            f"spawn would reach depth {child_depth}, exceeding max_spawn_depth="
            f"{parent.budget.max_spawn_depth}",
            DENIED_SPAWN_DEPTH_EXCEEDED,
        )

    # DELEG-002 / DELEG-004 / DELEG-011: one shared counter for the whole
    # tree; exhaustion always refuses, never auto-widens.
    if parent.budget.exhausted():
        return SpawnOutcome(
            SpawnDecision.DENIED,
            frozenset(),
            f"invocation agent budget exhausted (max_agents_per_invocation="
            f"{parent.budget.max_agents_per_invocation})",
            DENIED_SPAWN_BUDGET_EXCEEDED,
        )

    # DELEG-005: a parent cannot delegate what it does not itself hold.
    ungranted = requested_delegation - parent.capabilities
    if ungranted:
        return SpawnOutcome(
            SpawnDecision.DENIED,
            frozenset(),
            "delegation request includes capability(ies) the parent does not "
            f"hold: {sorted(c.value for c in ungranted)}",
            DENIED_DELEGATION_AUTHORITY_ESCALATION,
        )

    # child_authority = parent_authority ∩ explicit_delegation ∩ runtime_policy
    effective = parent.capabilities & requested_delegation & runtime_policy
    # Absolute strip: never transferable through the ordinary path,
    # regardless of what the three-way intersection above would allow.
    effective = effective - NON_TRANSFERABLE_CAPABILITIES

    parent.budget._record_spawn()
    return SpawnOutcome(SpawnDecision.ALLOWED, effective, None, None)


def default_read_only_worker(parent: AgentNode, *, child_identity: str) -> SpawnOutcome:
    """The default shallow topology's worker: analysis-only, no further
    spawn_agent of its own — agent-delegation.md, "Default topology stays
    shallow" / "Read-only worker capability set."""
    return spawn_agent(
        parent,
        child_identity=child_identity,
        requested_delegation=READ_ONLY_WORKER_CAPABILITIES,
    )


def authorize_action(agent: AgentNode, capability: Capability) -> bool:
    """DELEG-006 / DELEG-010: whether `agent` may perform an action
    requiring `capability`. Consults only the agent's own frozen,
    granted capability set — never a caller-supplied claim about what it
    should be allowed to do."""
    return capability in agent.capabilities


# ---------------------------------------------------------------------------
# Confused-deputy / identity binding (DELEG-009)
# ---------------------------------------------------------------------------
#
# Reuses review_action_authorization's provenance model rather than
# inventing a second one: acting through a bot, alternate account, nested
# agent, sub-agent, spawned process, or other agent-controlled channel is
# never independent/trusted provenance there, and the same channel names
# are never a route to a capability here either. A capability check binds
# to the agent's own AgentNode.capabilities; nothing in this module
# accepts a "claimed identity" or "acting-as" override.


def capability_survives_alternate_identity(channel: Optional[str]) -> bool:
    """True only if `channel` is independent/trusted provenance. Every
    agent-controlled channel (bot identity, alternate token, sub_agent,
    spawned_process, orchestration_metadata, ...) returns False — acting
    through it never manufactures a capability the acting agent's own
    AgentNode does not actually hold."""
    return raa.classify_provenance(channel) is raa.Provenance.INDEPENDENT_TRUSTED


# ---------------------------------------------------------------------------
# Single-use spawn/delegation authorization (DELEG-007) — reuses
# AuthorizationScope from review_action_authorization rather than a
# second token/accounting system.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SingleUseSpawnAuthorization:
    token: str
    issued_to_identity: str
    scope: raa.AuthorizationScope


class AuthorizationLedger:
    """Tracks consumption of single-use spawn/delegation authorizations.
    One instance per invocation, shared (by reference) across the whole
    tree — the same canonical-accounting principle as InvocationBudget,
    so a token consumed by one node is consumed for every node, including
    siblings and later-spawned descendants."""

    def __init__(self) -> None:
        self._consumed: "set[str]" = set()

    def consume(
        self, auth: SingleUseSpawnAuthorization, *, acting_identity: str
    ) -> bool:
        """Returns True only when the authorization is bound to exactly
        this acting identity and has not already been consumed by anyone
        (self, a sibling, or a copy). Replay, forwarding, and cross-agent
        reuse all resolve to False."""
        if auth.token in self._consumed:
            return False
        if auth.issued_to_identity != acting_identity:
            return False
        self._consumed.add(auth.token)
        return True


# ---------------------------------------------------------------------------
# Sibling collusion / authority reconstruction (DELEG-008)
# ---------------------------------------------------------------------------


def capabilities_from_shared_state(
    *sibling_capability_sets: "frozenset[Capability]",
) -> "frozenset[Capability]":
    """There is deliberately no function in this module that unions,
    merges, or otherwise combines two agents' capability sets. This
    helper exists only so a test can assert that fact structurally: the
    only combination operator available is intersection with a shared
    inventory, which can never add a capability neither sibling held."""
    if not sibling_capability_sets:
        return frozenset()
    combined = sibling_capability_sets[0]
    for s in sibling_capability_sets[1:]:
        combined = combined & s  # intersection only — never union
    return combined


# Governance: fragments that, if present in this module's public callable
# signatures, would mean a caller-controlled escape hatch crept into the
# gate (a way to flip a denial into a grant). Mirrors
# review_action_authorization.PROHIBITED_ESCAPE_HATCH_FRAGMENTS.
PROHIBITED_ESCAPE_HATCH_FRAGMENTS: "frozenset[str]" = frozenset(
    {
        "override",
        "force",
        "bypass",
        "skip_gate",
        "trust_caller",
        "assume_authorized",
        "claimed_identity",
        "acting_as",
        "widen_budget",
        "increase_budget",
        "disable_depth_check",
    }
)

# Explicitly out of scope for this gate (see agent-delegation.md,
# "Non-goals"): a child that legitimately needs code-mutation or formal
# review-action authority requires a capability issued through the same
# channel review_action_authorization.MutationAuthorization already
# defines — never through spawn_agent's ordinary delegation path. This
# module intentionally exposes no function that grants
# NON_TRANSFERABLE_CAPABILITIES; ISSUE_SEPARATE_RUNTIME_CAPABILITY is a
# documentation marker, not a callable.
ISSUE_SEPARATE_RUNTIME_CAPABILITY = None
