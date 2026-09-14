#!/usr/bin/env python3
"""Regression coverage for the agent-spawn / delegation capability gate.

Mirrors shared/policies/agent-delegation.md and the DELEG-### scenarios in
docs/threat-model/catalog/spawn-delegation.yaml (canonical source: issue
#300). Each test class is named after, and asserts, one DELEG-### scenario's
`expected_safe_outcome`; the class docstring cites the scenario id so
mapping tests -> catalog stays mechanical.

Core invariant under test everywhere: `child_authority ⊆ parent_authority ∩
explicit_delegation`, enforced by denial the test actually exercises the
code path for — never by asserting that a model "should" refuse.

Run with:
    python3 -m unittest tests.unit.review.delegation.test_agent_delegation_authorization
"""

from __future__ import annotations

import inspect
import unittest

from tests.reference.review import agent_delegation as ad
from tests.reference.review import review_action_authorization as raa


def _budget(agents: int = 5, depth: int = 1) -> ad.InvocationBudget:
    return ad.InvocationBudget(max_agents_per_invocation=agents, max_spawn_depth=depth)


def _root(
    capabilities: "frozenset[ad.Capability]" = frozenset(
        {ad.Capability.SPAWN_AGENT, ad.Capability.ANALYZE, ad.Capability.PUBLISH}
    ),
    *,
    budget: "ad.InvocationBudget | None" = None,
) -> ad.AgentNode:
    return ad.make_root_agent(
        identity="review-owner", capabilities=capabilities, budget=budget or _budget()
    )


# --------------------------------------------------------------------------
# DELEG-001: spawn without spawn_agent capability is refused
# --------------------------------------------------------------------------
class SpawnWithoutCapability(unittest.TestCase):
    def test_spawn_refused_when_capability_absent(self) -> None:
        parent = _root(capabilities=frozenset({ad.Capability.ANALYZE}))
        out = ad.spawn_agent(
            parent, child_identity="w1", requested_delegation=frozenset({ad.Capability.ANALYZE})
        )
        self.assertFalse(out.allowed)
        self.assertEqual(out.security_event, ad.DENIED_SPAWN_UNAUTHORIZED)
        self.assertEqual(out.granted_capabilities, frozenset())
        # the parent continues to exist / hold what it already had
        self.assertNotIn(ad.Capability.SPAWN_AGENT, parent.capabilities)

    def test_absent_by_default_for_a_freshly_constructed_agent(self) -> None:
        # spawn_agent = absent unless explicitly granted (agent-delegation.md).
        parent = ad.make_root_agent(
            identity="plain", capabilities=frozenset({ad.Capability.ANALYZE}), budget=_budget()
        )
        self.assertFalse(ad.authorize_action(parent, ad.Capability.SPAWN_AGENT))


# --------------------------------------------------------------------------
# DELEG-002: parent exceeds the invocation-level max agent count
# --------------------------------------------------------------------------
class ExceedMaxTotalAgents(unittest.TestCase):
    def test_spawn_beyond_budget_is_refused_existing_children_unaffected(self) -> None:
        budget = _budget(agents=2, depth=3)  # root + 1 worker allowed
        parent = _root(budget=budget)
        first = ad.spawn_agent(
            parent, child_identity="w1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES
        )
        self.assertTrue(first.allowed)
        second = ad.spawn_agent(
            parent, child_identity="w2", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES
        )
        self.assertFalse(second.allowed)
        self.assertEqual(second.security_event, ad.DENIED_SPAWN_BUDGET_EXCEEDED)
        # the first (already-spawned) child's grant is untouched
        self.assertEqual(first.granted_capabilities, ad.READ_ONLY_WORKER_CAPABILITIES)


# --------------------------------------------------------------------------
# DELEG-003: child exceeds the configured maximum spawn depth
# --------------------------------------------------------------------------
class ExceedMaxSpawnDepth(unittest.TestCase):
    def test_nested_spawn_beyond_max_depth_is_refused(self) -> None:
        budget = _budget(agents=10, depth=1)  # workers may exist, grandworkers may not
        parent = _root(budget=budget)
        worker = ad.spawn_agent(
            parent,
            child_identity="w1",
            requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.SPAWN_AGENT}),
        )
        self.assertTrue(worker.allowed)
        worker_node = ad.AgentNode(
            identity="w1", capabilities=worker.granted_capabilities, depth=parent.depth + 1, budget=budget
        )
        grandchild = ad.spawn_agent(
            worker_node, child_identity="gc1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES
        )
        self.assertFalse(grandchild.allowed)
        self.assertEqual(grandchild.security_event, ad.DENIED_SPAWN_DEPTH_EXCEEDED)


# --------------------------------------------------------------------------
# DELEG-004: recursive spawning cannot evade a flat, tree-wide budget
# --------------------------------------------------------------------------
class RecursiveSpawnCannotEvadeFlatBudget(unittest.TestCase):
    def test_budget_is_one_shared_pool_not_one_per_parent(self) -> None:
        budget = ad.InvocationBudget(max_agents_per_invocation=3, max_spawn_depth=5)
        root = _root(budget=budget)  # agent_count = 1 (root)

        w1 = ad.spawn_agent(
            root,
            child_identity="w1",
            requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.SPAWN_AGENT}),
        )
        self.assertTrue(w1.allowed)  # agent_count = 2
        w1_node = ad.AgentNode(identity="w1", capabilities=w1.granted_capabilities, depth=1, budget=budget)

        w2 = ad.spawn_agent(
            root,
            child_identity="w2",
            requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.SPAWN_AGENT}),
        )
        self.assertTrue(w2.allowed)  # agent_count = 3, budget now exhausted

        # w1 attempting to spawn its own child does NOT get a fresh
        # independent allowance just because it spawns from a different
        # node than the root did.
        nested = ad.spawn_agent(
            w1_node, child_identity="gc1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES
        )
        self.assertFalse(nested.allowed)
        self.assertEqual(nested.security_event, ad.DENIED_SPAWN_BUDGET_EXCEEDED)
        self.assertEqual(budget.agent_count, 3)

    def test_one_counter_object_is_shared_by_every_node_in_the_tree(self) -> None:
        budget = _budget(agents=100, depth=5)
        root = _root(budget=budget)
        w = ad.spawn_agent(
            root,
            child_identity="w1",
            requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.SPAWN_AGENT}),
        )
        w_node = ad.AgentNode(identity="w1", capabilities=w.granted_capabilities, depth=1, budget=budget)
        self.assertIs(w_node.budget, root.budget)


# --------------------------------------------------------------------------
# DELEG-005: parent delegates a capability it does not itself hold
# --------------------------------------------------------------------------
class DelegateCapabilityParentLacks(unittest.TestCase):
    def test_delegation_beyond_parents_own_set_is_refused(self) -> None:
        parent = _root(capabilities=frozenset({ad.Capability.SPAWN_AGENT, ad.Capability.ANALYZE}))
        out = ad.spawn_agent(
            parent,
            child_identity="w1",
            requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.PUBLISH}),
        )
        self.assertFalse(out.allowed)
        self.assertEqual(out.security_event, ad.DENIED_DELEGATION_AUTHORITY_ESCALATION)
        self.assertEqual(out.granted_capabilities, frozenset())

    def test_copying_parent_state_is_not_a_substitute_for_explicit_delegation(self) -> None:
        # Holding a capability is necessary but requesting it explicitly is
        # still required — spawn_agent never implicitly grants "whatever
        # the parent has" without it appearing in requested_delegation.
        parent = _root(
            capabilities=frozenset(
                {ad.Capability.SPAWN_AGENT, ad.Capability.ANALYZE, ad.Capability.PUBLISH}
            )
        )
        out = ad.spawn_agent(parent, child_identity="w1", requested_delegation=frozenset())
        self.assertTrue(out.allowed)
        self.assertEqual(out.granted_capabilities, frozenset())


# --------------------------------------------------------------------------
# DELEG-006: child requests a capability outside the delegated subset
# --------------------------------------------------------------------------
class ChildRequestsUndelegatedCapability(unittest.TestCase):
    def test_child_capability_set_is_exactly_the_delegated_subset(self) -> None:
        parent = _root(
            capabilities=frozenset(
                {ad.Capability.SPAWN_AGENT, ad.Capability.ANALYZE, ad.Capability.PUBLISH}
            )
        )
        out = ad.spawn_agent(
            parent, child_identity="w1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES
        )
        child = ad.AgentNode(identity="w1", capabilities=out.granted_capabilities, depth=1, budget=parent.budget)
        self.assertTrue(ad.authorize_action(child, ad.Capability.ANALYZE))
        self.assertFalse(ad.authorize_action(child, ad.Capability.PUBLISH))


# --------------------------------------------------------------------------
# DELEG-007: mutation / formal review-action authorization never
# inherited, copied, forwarded, or replayed across an agent-spawn boundary
# --------------------------------------------------------------------------
class ChildCannotInheritMutationAuthorization(unittest.TestCase):
    def test_mutate_never_granted_even_when_parent_holds_and_requests_it(self) -> None:
        parent = _root(
            capabilities=frozenset(
                {ad.Capability.SPAWN_AGENT, ad.Capability.ANALYZE, ad.Capability.MUTATE}
            )
        )
        out = ad.spawn_agent(
            parent,
            child_identity="w1",
            requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.MUTATE}),
            runtime_policy=frozenset(
                {ad.Capability.ANALYZE, ad.Capability.MUTATE, ad.Capability.SPAWN_AGENT}
            ),
        )
        self.assertTrue(out.allowed)  # spawn itself succeeds
        self.assertNotIn(ad.Capability.MUTATE, out.granted_capabilities)


class ChildCannotInheritFormalReviewActionAuthorization(unittest.TestCase):
    def test_formal_review_action_never_granted_even_when_requested(self) -> None:
        parent = _root(
            capabilities=frozenset(
                {
                    ad.Capability.SPAWN_AGENT,
                    ad.Capability.ANALYZE,
                    ad.Capability.FORMAL_REVIEW_ACTION,
                }
            )
        )
        out = ad.spawn_agent(
            parent,
            child_identity="w1",
            requested_delegation=frozenset(
                {ad.Capability.ANALYZE, ad.Capability.FORMAL_REVIEW_ACTION}
            ),
            runtime_policy=frozenset(
                {ad.Capability.ANALYZE, ad.Capability.FORMAL_REVIEW_ACTION, ad.Capability.SPAWN_AGENT}
            ),
        )
        self.assertTrue(out.allowed)
        self.assertNotIn(ad.Capability.FORMAL_REVIEW_ACTION, out.granted_capabilities)

    def test_no_capability_combination_ever_yields_a_non_transferable_grant(self) -> None:
        for cap in ad.Capability:
            all_caps = frozenset(ad.Capability)
            parent = _root(capabilities=all_caps | {ad.Capability.SPAWN_AGENT})
            out = ad.spawn_agent(
                parent, child_identity="w", requested_delegation=all_caps, runtime_policy=all_caps
            )
            self.assertTrue(out.allowed)
            for forbidden in ad.NON_TRANSFERABLE_CAPABILITIES:
                self.assertNotIn(forbidden, out.granted_capabilities)


class SingleUseAuthorizationReplayAcrossAgentBoundaries(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = raa.AuthorizationScope(
            repo="octo/repo", pr_number=1, head_sha="deadbeef", action=raa.GitHubEvent.APPROVE
        )
        self.auth = ad.SingleUseSpawnAuthorization(
            token="tok-1", issued_to_identity="review-owner", scope=self.scope
        )

    def test_consumed_once_then_replay_fails(self) -> None:
        ledger = ad.AuthorizationLedger()
        self.assertTrue(ledger.consume(self.auth, acting_identity="review-owner"))
        self.assertFalse(ledger.consume(self.auth, acting_identity="review-owner"))

    def test_cannot_be_forwarded_to_a_different_acting_identity(self) -> None:
        ledger = ad.AuthorizationLedger()
        self.assertFalse(ledger.consume(self.auth, acting_identity="spawned-worker-w1"))

    def test_ledger_is_shared_across_the_whole_tree_not_per_node(self) -> None:
        # A sibling cannot replay a token the ledger already saw, even
        # though each node otherwise has independent state.
        ledger = ad.AuthorizationLedger()
        sibling_a_auth = ad.SingleUseSpawnAuthorization(
            token="shared-tok", issued_to_identity="w1", scope=self.scope
        )
        sibling_b_auth = ad.SingleUseSpawnAuthorization(
            token="shared-tok", issued_to_identity="w2", scope=self.scope
        )
        self.assertTrue(ledger.consume(sibling_a_auth, acting_identity="w1"))
        # w2 presenting the same token string (reconstructed/observed from
        # shared state) is refused — both by identity mismatch and by the
        # token already being consumed.
        self.assertFalse(ledger.consume(sibling_b_auth, acting_identity="w2"))


# --------------------------------------------------------------------------
# DELEG-008: siblings cannot reconstruct authority via shared state
# --------------------------------------------------------------------------
class SiblingsCannotReconstructAuthorityFromSharedState(unittest.TestCase):
    def test_shared_state_combination_is_intersection_only_never_union(self) -> None:
        sibling_a = frozenset({ad.Capability.ANALYZE})
        sibling_b = frozenset({ad.Capability.PUBLISH})
        combined = ad.capabilities_from_shared_state(sibling_a, sibling_b)
        # Neither sibling holds both; no combination yields a capability
        # neither held individually.
        self.assertEqual(combined, frozenset())
        self.assertNotIn(ad.Capability.PUBLISH, sibling_a)
        self.assertNotIn(ad.Capability.ANALYZE, sibling_b)

    def test_no_function_in_the_module_unions_capability_sets(self) -> None:
        # Governance sweep: "|" (union) must not appear as the combinator
        # in the one shared-state helper this module exposes; only "&".
        src = inspect.getsource(ad.capabilities_from_shared_state)
        self.assertIn("&", src)
        self.assertNotIn(" | ", src.split("def ", 1)[-1].split("\n", 1)[-1].replace("frozenset", ""))

    def test_two_workers_spawned_independently_never_see_each_others_grant(self) -> None:
        budget = _budget(agents=5, depth=2)
        parent = _root(
            capabilities=frozenset(
                {ad.Capability.SPAWN_AGENT, ad.Capability.ANALYZE, ad.Capability.PUBLISH}
            ),
            budget=budget,
        )
        w1 = ad.spawn_agent(
            parent, child_identity="w1", requested_delegation=frozenset({ad.Capability.ANALYZE})
        )
        w2 = ad.spawn_agent(
            parent, child_identity="w2", requested_delegation=frozenset({ad.Capability.PUBLISH})
        )
        self.assertNotIn(ad.Capability.PUBLISH, w1.granted_capabilities)
        self.assertNotIn(ad.Capability.ANALYZE, w2.granted_capabilities)


# --------------------------------------------------------------------------
# DELEG-009: alternate identity / bot / subprocess / tool confused deputy
# --------------------------------------------------------------------------
class ConfusedDeputyAlternateIdentity(unittest.TestCase):
    CHANNELS = (
        "alternate_token",
        "alternate_username",
        "bot_identity",
        "service_account",
        "github_app_identity",
        "nested_agent_instruction",
        "sub_agent",
        "spawned_process",
        "orchestration_metadata",
    )

    def test_every_agent_controlled_channel_never_survives_the_identity_check(self) -> None:
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                self.assertFalse(ad.capability_survives_alternate_identity(channel))

    def test_independent_trusted_channel_is_the_only_one_that_can(self) -> None:
        self.assertTrue(
            ad.capability_survives_alternate_identity("human_principal_out_of_band")
        )
        self.assertTrue(
            ad.capability_survives_alternate_identity(
                "runtime_verified_principal_authorization"
            )
        )

    def test_unknown_or_missing_channel_never_trusted(self) -> None:
        self.assertFalse(ad.capability_survives_alternate_identity(None))
        self.assertFalse(ad.capability_survives_alternate_identity("mystery_channel"))

    def test_capability_check_has_no_claimed_identity_override_parameter(self) -> None:
        params = " ".join(inspect.signature(ad.authorize_action).parameters).lower()
        self.assertNotIn("claimed", params)
        self.assertNotIn("acting_as", params)


# --------------------------------------------------------------------------
# DELEG-010: read-only worker attempts publication / mutation / runtime
# validation / formal review action / further spawn
# --------------------------------------------------------------------------
class ReadOnlyWorkerOutOfGrantActions(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = _root(
            capabilities=frozenset(
                {
                    ad.Capability.SPAWN_AGENT,
                    ad.Capability.ANALYZE,
                    ad.Capability.PUBLISH,
                    ad.Capability.MUTATE,
                    ad.Capability.RUNTIME_VALIDATE,
                    ad.Capability.FORMAL_REVIEW_ACTION,
                }
            )
        )
        out = ad.default_read_only_worker(self.parent, child_identity="worker-1")
        self.assertTrue(out.allowed)
        self.worker = ad.AgentNode(
            identity="worker-1", capabilities=out.granted_capabilities, depth=1, budget=self.parent.budget
        )

    def test_worker_cannot_publish(self) -> None:
        self.assertFalse(ad.authorize_action(self.worker, ad.Capability.PUBLISH))

    def test_worker_cannot_run_runtime_validation(self) -> None:
        self.assertFalse(ad.authorize_action(self.worker, ad.Capability.RUNTIME_VALIDATE))

    def test_worker_cannot_mutate(self) -> None:
        self.assertFalse(ad.authorize_action(self.worker, ad.Capability.MUTATE))

    def test_worker_cannot_submit_a_formal_review_action(self) -> None:
        self.assertFalse(ad.authorize_action(self.worker, ad.Capability.FORMAL_REVIEW_ACTION))

    def test_worker_cannot_spawn_further_children(self) -> None:
        self.assertFalse(ad.authorize_action(self.worker, ad.Capability.SPAWN_AGENT))
        out = ad.spawn_agent(
            self.worker, child_identity="gc1", requested_delegation=frozenset({ad.Capability.ANALYZE})
        )
        self.assertFalse(out.allowed)
        self.assertEqual(out.security_event, ad.DENIED_SPAWN_UNAUTHORIZED)

    def test_worker_still_holds_its_in_grant_analysis_capability(self) -> None:
        # A denied out-of-grant action does not discard the worker's
        # otherwise-valid analysis capability.
        self.assertTrue(ad.authorize_action(self.worker, ad.Capability.ANALYZE))


# --------------------------------------------------------------------------
# DELEG-011: budget exhaustion degrades safely, never widens authority
# --------------------------------------------------------------------------
class BudgetExhaustionNeverWidensAuthority(unittest.TestCase):
    def test_exhaustion_refuses_further_spawns_but_leaves_existing_work_intact(self) -> None:
        budget = ad.InvocationBudget(max_agents_per_invocation=2, max_spawn_depth=3)
        parent = _root(budget=budget)
        first = ad.spawn_agent(
            parent, child_identity="w1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES
        )
        self.assertTrue(first.allowed)
        self.assertTrue(budget.exhausted())

        for i in range(5):
            out = ad.spawn_agent(
                parent,
                child_identity=f"w{i + 2}",
                requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES,
            )
            self.assertFalse(out.allowed)
            self.assertEqual(out.security_event, ad.DENIED_SPAWN_BUDGET_EXCEEDED)

        # The limits themselves never change as a side effect of repeated
        # refused attempts.
        self.assertEqual(budget.max_agents_per_invocation, 2)
        self.assertEqual(budget.max_spawn_depth, 3)
        self.assertEqual(budget.agent_count, 2)

    def test_budget_object_exposes_no_public_widening_method(self) -> None:
        public_methods = {
            name
            for name, obj in vars(ad.InvocationBudget).items()
            if callable(obj) and not name.startswith("_")
        }
        for fragment in ("increase", "widen", "raise_limit", "reset", "extend"):
            for name in public_methods:
                self.assertNotIn(fragment, name.lower())


# --------------------------------------------------------------------------
# Governance sweeps
# --------------------------------------------------------------------------
class GovernanceSweeps(unittest.TestCase):
    def test_no_public_signature_has_an_escape_hatch_parameter(self) -> None:
        for name, obj in vars(ad).items():
            if not callable(obj) or name.startswith("_"):
                continue
            try:
                params = " ".join(inspect.signature(obj).parameters).lower()
            except (TypeError, ValueError):
                continue
            for fragment in ad.PROHIBITED_ESCAPE_HATCH_FRAGMENTS:
                self.assertNotIn(
                    fragment, params, f"{name} exposes an escape hatch: {fragment}"
                )

    def test_module_grants_no_non_transferable_capability_anywhere(self) -> None:
        # Exhaustive: no combination of capability inputs to spawn_agent
        # ever yields MUTATE or FORMAL_REVIEW_ACTION in the result.
        all_caps = frozenset(ad.Capability)
        import itertools

        for size in range(len(all_caps) + 1):
            for combo in itertools.combinations(all_caps, size):
                requested = frozenset(combo)
                parent = _root(capabilities=all_caps, budget=_budget(agents=1000, depth=5))
                out = ad.spawn_agent(
                    parent, child_identity="x", requested_delegation=requested, runtime_policy=all_caps
                )
                if out.allowed:
                    for forbidden in ad.NON_TRANSFERABLE_CAPABILITIES:
                        self.assertNotIn(forbidden, out.granted_capabilities)

    def test_child_capability_set_is_always_a_subset_of_parent_and_request(self) -> None:
        import itertools

        all_caps = list(ad.Capability)
        for p_size in range(len(all_caps) + 1):
            for parent_combo in itertools.combinations(all_caps, p_size):
                parent_caps = frozenset(parent_combo) | {ad.Capability.SPAWN_AGENT}
                parent = _root(capabilities=parent_caps, budget=_budget(agents=1000, depth=5))
                out = ad.spawn_agent(
                    parent,
                    child_identity="x",
                    requested_delegation=parent_caps,
                    runtime_policy=frozenset(all_caps),
                )
                if out.allowed:
                    self.assertTrue(out.granted_capabilities.issubset(parent_caps))


if __name__ == "__main__":
    unittest.main()
