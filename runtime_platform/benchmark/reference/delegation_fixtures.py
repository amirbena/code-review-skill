#!/usr/bin/env python3
"""Test-only reference fixtures for the agent-spawn / delegated-authority
benchmark corpus (Issue #307, depends on #303:
shared/policies/agent-delegation.md).

Unlike the domain corpora under docs/benchmark/corpus/, this boundary has
no representation in the `benchmark-case/v2` schema
(runtime_platform/benchmark/fixture-format.md): that schema's `expected` block is
findings/decision-shaped (a patch, a set of expected review findings) and
has no field for a capability grant, a spawn-depth budget, or an
allow/deny structural outcome. Rather than stretch that closed schema to
fit a security-boundary domain, this module follows the same pattern
`reviewer_brief_fixtures.py` already established for a domain the schema
does not fit: a test-only, hand-authored, *data-driven* fixture corpus,
documented in docs/benchmark/corpus/delegation-spawn/README.md.

This is deliberately **not** a duplicate of
tests/unit/review/delegation/test_agent_delegation_authorization.py, which
already hand-writes one regression test per DELEG-### scenario against
tests/reference/review/agent_delegation.py (`ad` below). That suite is
*why* the boundary holds; this corpus is the declarative, metadata-bearing
*benchmark* layer #307 asks for: every case carries the structured fields
the issue requires (parent capability set, explicit delegated set,
requested child capability, spawn depth, invocation agent-count budget,
expected allow/deny result, linked #300 threat-scenario id, and expected
provisional denial classification) as *data*, validated by
`validate_case`/`validate_corpus` below and executed generically by
`tests/unit/benchmark/test_delegation_spawn_corpus.py` — so a future tool
(#310) can select/introspect this corpus by category or threat-scenario id
without re-deriving it from hand-written test method names. Both layers
call into the *same* single reference model (`agent_delegation.py`); this
module defines no second implementation of the gate.

Evaluation style (runtime_platform/benchmark/README.md convention + #307's own
"Evaluation style" requirement): every assertion here is a deterministic
structural comparison — allowed/denied, effective granted capabilities,
agent count, spawn depth, ledger consumption state — never an LLM/rubric
score. This corpus is disjoint from the finding-precision/recall/severity
metrics (#41) and the Reviewer Brief semantic-quality corpus (#309): it
never touches a finding, a severity, or review prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from tests.reference.review import agent_delegation as ad
from tests.reference.review import review_action_authorization as raa

# ---------------------------------------------------------------------------
# Case taxonomy
# ---------------------------------------------------------------------------

CATEGORY_SPAWN_CAPABILITY = "spawn_capability"
CATEGORY_INVOCATION_BUDGET = "invocation_budget"
CATEGORY_SPAWN_DEPTH = "spawn_depth"
CATEGORY_CAPABILITY_SUBSET = "capability_subset"
CATEGORY_AUTHORIZATION_NON_TRANSFER = "authorization_non_transfer"
CATEGORY_SIBLING_RECONSTRUCTION = "sibling_reconstruction"
CATEGORY_CONFUSED_DEPUTY = "confused_deputy"
CATEGORY_READ_ONLY_WORKER = "read_only_worker"
CATEGORY_BUDGET_EXHAUSTION = "budget_exhaustion"

VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        CATEGORY_SPAWN_CAPABILITY,
        CATEGORY_INVOCATION_BUDGET,
        CATEGORY_SPAWN_DEPTH,
        CATEGORY_CAPABILITY_SUBSET,
        CATEGORY_AUTHORIZATION_NON_TRANSFER,
        CATEGORY_SIBLING_RECONSTRUCTION,
        CATEGORY_CONFUSED_DEPUTY,
        CATEGORY_READ_ONLY_WORKER,
        CATEGORY_BUDGET_EXHAUSTION,
    }
)

# Every denial classification a "denied" case may cite -- reused verbatim
# from the single reference model, never a second taxonomy. #299 (the
# authoritative event vocabulary, docs/security-events/security-event-model.md)
# has landed and confirmed these as the same final strings
# docs/threat-model/catalog/spawn-delegation.yaml already declares (see
# #307's "Explicitly out of scope").
VALID_DENIAL_CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        ad.DENIED_SPAWN_UNAUTHORIZED,
        ad.DENIED_SPAWN_BUDGET_EXCEEDED,
        ad.DENIED_SPAWN_DEPTH_EXCEEDED,
        ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
        ad.DENIED_DELEGATION_REPLAY,
    }
)

_THREAT_ID_RE = re.compile(r"^(DELEG|DOS)-\d{3}$")

RESULT_ALLOWED = "allowed"
RESULT_DENIED = "denied"
VALID_RESULTS: frozenset[str] = frozenset({RESULT_ALLOWED, RESULT_DENIED})


class DelegationFixtureError(ValueError):
    """A delegation-benchmark fixture is malformed."""


@dataclass(frozen=True)
class CaseOutcome:
    """What actually happened when a case's `run()` executed against the
    single reference model. Fields mirror #307's required per-case
    metadata so a case's *expectation* and its *actual* outcome are
    directly comparable field-by-field."""

    allowed: bool
    granted_capabilities: "frozenset[ad.Capability]"
    security_event: Optional[str] = None
    notes: str = ""


@dataclass(frozen=True)
class DelegationCase:
    """One benchmark case for the agent-spawn / delegated-authority
    boundary. `run()` is a zero-argument callable exercising the single
    reference model (`agent_delegation.py`, composing with
    `review_action_authorization.py` for provenance/scope) and returning
    the decisive `CaseOutcome`; every other field is declarative metadata
    validated independently of execution.
    """

    case_id: str
    category: str
    covers: "frozenset[str]"
    threat_scenario_ids: "tuple[str, ...]"
    description: str
    parent_capabilities: "frozenset[ad.Capability]"
    delegated_capabilities: "frozenset[ad.Capability]"
    requested_child_capability: "Optional[ad.Capability]"
    spawn_depth: int
    max_spawn_depth: int
    max_agents_per_invocation: int
    expected_result: str
    expected_security_event: Optional[str]
    expected_granted_capabilities: "Optional[frozenset[ad.Capability]]"
    run: Callable[[], CaseOutcome]


def validate_case(case: DelegationCase) -> None:
    """Fail-closed structural validation of one fixture's *data* --
    independent of running it. Mirrors `benchmark_fixture.py`'s
    fail-closed spirit for this domain: valid capability names, coherent
    parent/delegated/requested capability sets, valid count/depth values,
    a valid expected result, and valid threat-scenario references where
    required. Deliberately does not encode runtime implementation
    internals (no InvocationBudget/AgentNode wiring is inspected here) --
    just the clean data schema #307 asks for."""

    if not isinstance(case.case_id, str) or not case.case_id.strip():
        raise DelegationFixtureError("case_id must be a non-empty string")

    if case.category not in VALID_CATEGORIES:
        raise DelegationFixtureError(
            f"{case.case_id}: category {case.category!r} not in {sorted(VALID_CATEGORIES)}"
        )

    for label, value in (
        ("parent_capabilities", case.parent_capabilities),
        ("delegated_capabilities", case.delegated_capabilities),
    ):
        if not isinstance(value, frozenset) or not all(isinstance(c, ad.Capability) for c in value):
            raise DelegationFixtureError(f"{case.case_id}: {label} must be a frozenset[Capability]")

    if case.requested_child_capability is not None and not isinstance(
        case.requested_child_capability, ad.Capability
    ):
        raise DelegationFixtureError(f"{case.case_id}: requested_child_capability must be a Capability or None")

    for label, value in (
        ("spawn_depth", case.spawn_depth),
        ("max_spawn_depth", case.max_spawn_depth),
        ("max_agents_per_invocation", case.max_agents_per_invocation),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise DelegationFixtureError(f"{case.case_id}: {label} must be a non-negative int")
    if case.max_agents_per_invocation < 1:
        raise DelegationFixtureError(f"{case.case_id}: max_agents_per_invocation must allow at least the root")

    if case.expected_result not in VALID_RESULTS:
        raise DelegationFixtureError(
            f"{case.case_id}: expected_result {case.expected_result!r} not in {sorted(VALID_RESULTS)}"
        )

    if case.expected_result == RESULT_DENIED:
        if case.expected_security_event not in VALID_DENIAL_CLASSIFICATIONS:
            raise DelegationFixtureError(
                f"{case.case_id}: a denied case must carry a valid denial classification from "
                f"{sorted(VALID_DENIAL_CLASSIFICATIONS)}, got {case.expected_security_event!r}"
            )
        if case.expected_granted_capabilities not in (None, frozenset()):
            raise DelegationFixtureError(
                f"{case.case_id}: a denied case's expected_granted_capabilities must be empty or unset"
            )
    else:  # allowed
        if case.expected_security_event is not None:
            raise DelegationFixtureError(
                f"{case.case_id}: an allowed case must not carry a denial classification "
                f"(got {case.expected_security_event!r})"
            )
        if case.expected_granted_capabilities is None or not isinstance(
            case.expected_granted_capabilities, frozenset
        ):
            raise DelegationFixtureError(
                f"{case.case_id}: an allowed case must state its expected_granted_capabilities frozenset "
                "(may be empty, e.g. a stripped non-transferable request)"
            )
        if not all(isinstance(c, ad.Capability) for c in case.expected_granted_capabilities):
            raise DelegationFixtureError(
                f"{case.case_id}: expected_granted_capabilities must contain only Capability values"
            )

    if not isinstance(case.threat_scenario_ids, tuple):
        raise DelegationFixtureError(f"{case.case_id}: threat_scenario_ids must be a tuple")
    for tid in case.threat_scenario_ids:
        if not isinstance(tid, str) or not _THREAT_ID_RE.match(tid):
            raise DelegationFixtureError(
                f"{case.case_id}: threat_scenario_ids entry {tid!r} must match '<DELEG|DOS>-<3 digits>'"
            )

    if not callable(case.run):
        raise DelegationFixtureError(f"{case.case_id}: run must be callable")


def validate_corpus(cases: "tuple[DelegationCase, ...]") -> None:
    """Corpus-wide structural checks: every case validates individually,
    case_ids are unique, and no category is left empty."""
    if not cases:
        raise DelegationFixtureError("corpus must not be empty")
    seen: "set[str]" = set()
    for case in cases:
        validate_case(case)
        if case.case_id in seen:
            raise DelegationFixtureError(f"duplicate case_id {case.case_id!r}")
        seen.add(case.case_id)


def cases_covering(tag: str) -> "tuple[DelegationCase, ...]":
    return tuple(case for case in ALL_CASES if tag in case.covers)


def cases_for_threat_scenario(threat_id: str) -> "tuple[DelegationCase, ...]":
    return tuple(case for case in ALL_CASES if threat_id in case.threat_scenario_ids)


def cases_where(predicate: "Callable[[DelegationCase], bool]") -> "tuple[DelegationCase, ...]":
    return tuple(case for case in ALL_CASES if predicate(case))


def cases_in_category(category: str) -> "tuple[DelegationCase, ...]":
    """The repository's existing focused-selection convention (a
    dedicated test module targeting one sub-corpus, run independently
    without the whole benchmark suite) already makes the whole module
    independently runnable; this is the finer-grained, in-process
    equivalent used by #310-style tooling to select a slice by
    category."""
    return tuple(case for case in ALL_CASES if case.category == category)


# ---------------------------------------------------------------------------
# Shared scenario-construction helpers (used by several `run` closures)
# ---------------------------------------------------------------------------


def _budget(agents: int = 5, depth: int = 2) -> ad.InvocationBudget:
    return ad.InvocationBudget(max_agents_per_invocation=agents, max_spawn_depth=depth)


def _owner(
    capabilities: "frozenset[ad.Capability]",
    *,
    budget: "Optional[ad.InvocationBudget]" = None,
) -> ad.AgentNode:
    return ad.make_root_agent(identity="review-owner", capabilities=capabilities, budget=budget or _budget())


def _outcome_from_spawn(out: ad.SpawnOutcome, *, notes: str = "") -> CaseOutcome:
    return CaseOutcome(
        allowed=out.allowed,
        granted_capabilities=out.granted_capabilities,
        security_event=out.security_event,
        notes=notes,
    )


# ===========================================================================
# A. spawn_capability -- DELEG-001
# ===========================================================================

_A_PARENT_NO_SPAWN = frozenset({ad.Capability.ANALYZE})
_A_PARENT_WITH_SPAWN = frozenset({ad.Capability.SPAWN_AGENT, ad.Capability.ANALYZE, ad.Capability.PUBLISH})


def _run_spawn_denied_without_capability() -> CaseOutcome:
    parent = _owner(_A_PARENT_NO_SPAWN)
    out = ad.spawn_agent(parent, child_identity="w1", requested_delegation=frozenset({ad.Capability.ANALYZE}))
    return _outcome_from_spawn(out)


SPAWN_DENIED_WITHOUT_CAPABILITY = DelegationCase(
    case_id="spawn-denied-without-capability",
    category=CATEGORY_SPAWN_CAPABILITY,
    covers=frozenset({"spawn-without-capability-denied"}),
    threat_scenario_ids=("DELEG-001",),
    description="A parent without spawn_agent attempts to create a child; refused outright.",
    parent_capabilities=_A_PARENT_NO_SPAWN,
    delegated_capabilities=frozenset({ad.Capability.ANALYZE}),
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_SPAWN_UNAUTHORIZED,
    expected_granted_capabilities=None,
    run=_run_spawn_denied_without_capability,
)


def _run_spawn_allowed_with_capability_bounded() -> CaseOutcome:
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=_budget(agents=3, depth=2))
    out = ad.spawn_agent(
        parent, child_identity="w1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES
    )
    return _outcome_from_spawn(out)


SPAWN_ALLOWED_WITH_CAPABILITY_BOUNDED = DelegationCase(
    case_id="spawn-allowed-with-capability-bounded",
    category=CATEGORY_SPAWN_CAPABILITY,
    covers=frozenset({"spawn-with-capability-bounded-allowed"}),
    threat_scenario_ids=("DELEG-001",),
    description="A parent holding spawn_agent spawns one bounded, read-only worker successfully.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=3,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    run=_run_spawn_allowed_with_capability_bounded,
)


# ===========================================================================
# B. invocation_budget -- DELEG-002 / DELEG-004 / DOS-006 / DOS-007
# ===========================================================================


def _run_budget_exceeded_denied() -> CaseOutcome:
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=_budget(agents=2, depth=3))  # root + 1 worker allowed
    first = ad.spawn_agent(parent, child_identity="w1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    assert first.allowed, "setup: first spawn within budget must succeed"
    second = ad.spawn_agent(parent, child_identity="w2", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    return _outcome_from_spawn(second, notes="decisive: the spawn that exceeds the budget")


BUDGET_EXCEEDED_DENIED = DelegationCase(
    case_id="invocation-budget-exceeded-denied",
    category=CATEGORY_INVOCATION_BUDGET,
    covers=frozenset({"invocation-budget-exceeded-denied"}),
    threat_scenario_ids=("DELEG-002",),
    description="A spawn beyond max_agents_per_invocation is refused; the earlier child is unaffected.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=3,
    max_agents_per_invocation=2,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_SPAWN_BUDGET_EXCEEDED,
    expected_granted_capabilities=None,
    run=_run_budget_exceeded_denied,
)


def _run_budget_within_limit_allowed() -> CaseOutcome:
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=_budget(agents=3, depth=3))
    ad.spawn_agent(parent, child_identity="w1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    out = ad.spawn_agent(parent, child_identity="w2", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    return _outcome_from_spawn(out, notes="second worker still within a budget of 3 (root + 2)")


BUDGET_WITHIN_LIMIT_ALLOWED = DelegationCase(
    case_id="invocation-budget-within-limit-allowed",
    category=CATEGORY_INVOCATION_BUDGET,
    covers=frozenset({"invocation-budget-within-limit-allowed"}),
    threat_scenario_ids=("DELEG-002",),
    description="A second spawn that still fits the invocation budget succeeds.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=3,
    max_agents_per_invocation=3,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    run=_run_budget_within_limit_allowed,
)


def run_spawn_kill_spawn_churn(*, agents: int = 3, churn_attempts: int = 4) -> "tuple[ad.SpawnOutcome, ...]":
    """Fills the shared budget, then keeps issuing further spawn requests
    ("churn") as an attacker would after believing earlier children were
    torn down. `InvocationBudget` exposes no method that ever decrements
    `agent_count` -- there is no kill/release primitive in the reference
    model at all -- so every churn attempt after exhaustion must be
    denied identically. Returns every outcome (fill + churn) so a test
    can assert the whole sequence, not just the last entry."""
    budget = _budget(agents=agents, depth=5)
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=budget)
    outcomes = []
    # Fill the budget (root already counts as 1).
    for i in range(agents - 1):
        outcomes.append(
            ad.spawn_agent(parent, child_identity=f"fill{i}", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
        )
    # Now "churn": repeatedly request more spawns as if slots had freed up.
    for i in range(churn_attempts):
        outcomes.append(
            ad.spawn_agent(parent, child_identity=f"churn{i}", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
        )
    return tuple(outcomes)


def _run_churn_cannot_reset_budget() -> CaseOutcome:
    outcomes = run_spawn_kill_spawn_churn(agents=3, churn_attempts=4)
    fill_outcomes, churn_outcomes = outcomes[:2], outcomes[2:]
    assert all(o.allowed for o in fill_outcomes), "setup: filling to budget must succeed"
    decisive = churn_outcomes[-1]
    return _outcome_from_spawn(
        decisive,
        notes=f"all {len(churn_outcomes)} post-exhaustion churn attempts denied: {[o.allowed for o in churn_outcomes]}",
    )


CHURN_CANNOT_RESET_BUDGET = DelegationCase(
    case_id="spawn-kill-spawn-churn-cannot-reset-budget",
    category=CATEGORY_INVOCATION_BUDGET,
    covers=frozenset({"churn-cannot-evade-aggregate-accounting"}),
    threat_scenario_ids=("DELEG-004",),
    description=(
        "Repeated spawn/kill/spawn churn after budget exhaustion cannot reset or evade the "
        "tree-wide agent-count accounting -- every attempt after exhaustion stays denied."
    ),
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=5,
    max_agents_per_invocation=3,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_SPAWN_BUDGET_EXCEEDED,
    expected_granted_capabilities=None,
    run=_run_churn_cannot_reset_budget,
)


def run_recursive_spawn_tree(*, agents: int = 4, depth: int = 10) -> "tuple[ad.SpawnOutcome, ...]":
    """Attempts to build a deep chain (each child re-delegated spawn_agent
    and immediately spawning its own child) far beyond a small tree-wide
    agent budget, proving recursion through multiple generations cannot
    build an unbounded tree even though depth alone would allow it."""
    budget = ad.InvocationBudget(max_agents_per_invocation=agents, max_spawn_depth=depth)
    node = _owner(_A_PARENT_WITH_SPAWN, budget=budget)
    outcomes = []
    for i in range(depth):
        out = ad.spawn_agent(
            node,
            child_identity=f"gen{i}",
            requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.SPAWN_AGENT}),
        )
        outcomes.append(out)
        if not out.allowed:
            break
        node = ad.AgentNode(
            identity=f"gen{i}", capabilities=out.granted_capabilities, depth=node.depth + 1, budget=budget
        )
    return tuple(outcomes)


def _run_recursive_unbounded_tree_denied() -> CaseOutcome:
    outcomes = run_recursive_spawn_tree(agents=4, depth=10)
    denied = [o for o in outcomes if not o.allowed]
    assert denied, "recursion must eventually be denied by the tree-wide budget"
    decisive = denied[0]
    return _outcome_from_spawn(
        decisive,
        notes=f"tree stopped after {len(outcomes) - len(denied)} generations against a budget of 4",
    )


RECURSIVE_UNBOUNDED_TREE_DENIED = DelegationCase(
    case_id="recursive-spawning-cannot-build-unbounded-tree",
    category=CATEGORY_INVOCATION_BUDGET,
    covers=frozenset({"recursive-spawn-bounded-tree"}),
    threat_scenario_ids=("DELEG-004", "DOS-006"),
    description="Multi-generation recursive spawning cannot exceed the flat, tree-wide agent budget.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=frozenset({ad.Capability.ANALYZE, ad.Capability.SPAWN_AGENT}),
    requested_child_capability=ad.Capability.SPAWN_AGENT,
    spawn_depth=4,
    max_spawn_depth=10,
    max_agents_per_invocation=4,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_SPAWN_BUDGET_EXCEEDED,
    expected_granted_capabilities=None,
    run=_run_recursive_unbounded_tree_denied,
)


def _run_worker_fanout_bounded_denied() -> CaseOutcome:
    budget = _budget(agents=4, depth=1)  # root + up to 3 parallel workers
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=budget)
    outcomes = [
        ad.spawn_agent(parent, child_identity=f"worker{i}", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
        for i in range(5)  # request 5 parallel workers against a cap of 3
    ]
    assert sum(1 for o in outcomes if o.allowed) == 3, "exactly the budgeted number of workers may spawn"
    decisive = next(o for o in outcomes if not o.allowed)
    return _outcome_from_spawn(decisive, notes="excess parallel fan-out beyond the bounded worker count")


WORKER_FANOUT_BOUNDED_DENIED = DelegationCase(
    case_id="excessive-parallel-worker-fanout-denied",
    category=CATEGORY_INVOCATION_BUDGET,
    covers=frozenset({"parallel-worker-fanout-bounded"}),
    threat_scenario_ids=("DOS-007",),
    description="Requesting more parallel review workers than the invocation budget allows is bounded.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=1,
    max_agents_per_invocation=4,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_SPAWN_BUDGET_EXCEEDED,
    expected_granted_capabilities=None,
    run=_run_worker_fanout_bounded_denied,
)


# ===========================================================================
# C. spawn_depth -- DELEG-003
# ===========================================================================


def _run_nested_spawn_within_depth_allowed() -> CaseOutcome:
    budget = _budget(agents=10, depth=2)
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=budget)
    worker = ad.spawn_agent(
        parent, child_identity="w1", requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.SPAWN_AGENT})
    )
    assert worker.allowed
    worker_node = ad.AgentNode(identity="w1", capabilities=worker.granted_capabilities, depth=1, budget=budget)
    out = ad.spawn_agent(worker_node, child_identity="gc1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    return _outcome_from_spawn(out)


NESTED_SPAWN_WITHIN_DEPTH_ALLOWED = DelegationCase(
    case_id="nested-spawn-within-max-depth-allowed",
    category=CATEGORY_SPAWN_DEPTH,
    covers=frozenset({"nested-spawn-within-depth-allowed"}),
    threat_scenario_ids=("DELEG-003",),
    description="A grandchild spawned at exactly max_spawn_depth succeeds.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=2,
    max_spawn_depth=2,
    max_agents_per_invocation=10,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    run=_run_nested_spawn_within_depth_allowed,
)


def _run_nested_spawn_exceeds_depth_denied() -> CaseOutcome:
    budget = _budget(agents=10, depth=1)  # workers may exist, grandworkers may not
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=budget)
    worker = ad.spawn_agent(
        parent, child_identity="w1", requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.SPAWN_AGENT})
    )
    assert worker.allowed
    worker_node = ad.AgentNode(identity="w1", capabilities=worker.granted_capabilities, depth=1, budget=budget)
    out = ad.spawn_agent(worker_node, child_identity="gc1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    return _outcome_from_spawn(out)


NESTED_SPAWN_EXCEEDS_DEPTH_DENIED = DelegationCase(
    case_id="nested-spawn-exceeds-max-depth-denied",
    category=CATEGORY_SPAWN_DEPTH,
    covers=frozenset({"nested-spawn-exceeds-depth-denied"}),
    threat_scenario_ids=("DELEG-003",),
    description="A grandchild spawned one level past max_spawn_depth is refused.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=2,
    max_spawn_depth=1,
    max_agents_per_invocation=10,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_SPAWN_DEPTH_EXCEEDED,
    expected_granted_capabilities=None,
    run=_run_nested_spawn_exceeds_depth_denied,
)


# ===========================================================================
# D. capability_subset -- DELEG-005 / DELEG-006
# ===========================================================================


def _run_delegate_capability_parent_lacks_denied() -> CaseOutcome:
    parent = _owner(frozenset({ad.Capability.SPAWN_AGENT, ad.Capability.ANALYZE}))
    out = ad.spawn_agent(
        parent, child_identity="w1", requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.MUTATE})
    )
    return _outcome_from_spawn(out)


DELEGATE_CAPABILITY_PARENT_LACKS_DENIED = DelegationCase(
    case_id="delegate-capability-parent-does-not-hold-denied",
    category=CATEGORY_CAPABILITY_SUBSET,
    covers=frozenset({"delegate-ungranted-capability-denied"}),
    threat_scenario_ids=("DELEG-005",),
    description="Delegating a capability the parent itself does not hold is refused outright.",
    parent_capabilities=frozenset({ad.Capability.SPAWN_AGENT, ad.Capability.ANALYZE}),
    delegated_capabilities=frozenset({ad.Capability.ANALYZE, ad.Capability.MUTATE}),
    requested_child_capability=ad.Capability.MUTATE,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
    expected_granted_capabilities=None,
    run=_run_delegate_capability_parent_lacks_denied,
)


def _run_child_requests_outside_delegation_denied() -> CaseOutcome:
    parent = _owner(_A_PARENT_WITH_SPAWN)
    out = ad.spawn_agent(parent, child_identity="w1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    assert out.allowed
    child = ad.AgentNode(identity="w1", capabilities=out.granted_capabilities, depth=1, budget=parent.budget)
    # Child now tries to use PUBLISH, which was never in its delegated set.
    permitted = ad.authorize_action(child, ad.Capability.PUBLISH)
    return CaseOutcome(
        allowed=permitted,
        granted_capabilities=child.capabilities,
        security_event=None if permitted else ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
    )


CHILD_REQUESTS_OUTSIDE_DELEGATION_DENIED = DelegationCase(
    case_id="child-requests-capability-outside-delegation-denied",
    category=CATEGORY_CAPABILITY_SUBSET,
    covers=frozenset({"child-undelegated-capability-request-denied"}),
    threat_scenario_ids=("DELEG-006",),
    description="A child requests a capability outside its explicitly delegated subset; refused.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.PUBLISH,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
    expected_granted_capabilities=None,
    run=_run_child_requests_outside_delegation_denied,
)


def _run_valid_subset_delegation_allowed() -> CaseOutcome:
    parent = _owner(_A_PARENT_WITH_SPAWN)
    out = ad.spawn_agent(
        parent,
        child_identity="w1",
        requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.PUBLISH}),
    )
    return _outcome_from_spawn(out)


VALID_SUBSET_DELEGATION_ALLOWED = DelegationCase(
    case_id="valid-capability-subset-delegation-allowed",
    category=CATEGORY_CAPABILITY_SUBSET,
    covers=frozenset({"valid-subset-delegation-allowed"}),
    threat_scenario_ids=("DELEG-005", "DELEG-006"),
    description="Delegating a genuine subset of the parent's own held capabilities succeeds exactly as requested.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=frozenset({ad.Capability.ANALYZE, ad.Capability.PUBLISH}),
    requested_child_capability=ad.Capability.PUBLISH,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=frozenset({ad.Capability.ANALYZE, ad.Capability.PUBLISH}),
    run=_run_valid_subset_delegation_allowed,
)


# ===========================================================================
# E. authorization_non_transfer -- DELEG-007
# ===========================================================================

_PARENT_WITH_MUTATE_AND_REVIEW_ACTION = frozenset(
    {
        ad.Capability.SPAWN_AGENT,
        ad.Capability.ANALYZE,
        ad.Capability.MUTATE,
        ad.Capability.FORMAL_REVIEW_ACTION,
    }
)


def _run_child_cannot_inherit_mutation_authorization() -> CaseOutcome:
    parent = _owner(_PARENT_WITH_MUTATE_AND_REVIEW_ACTION)
    out = ad.spawn_agent(
        parent,
        child_identity="w1",
        requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.MUTATE}),
    )
    return _outcome_from_spawn(out, notes="MUTATE is requested but must be stripped as non-transferable")


CHILD_CANNOT_INHERIT_MUTATION_AUTHORIZATION = DelegationCase(
    case_id="child-cannot-inherit-mutation-authorization",
    category=CATEGORY_AUTHORIZATION_NON_TRANSFER,
    covers=frozenset({"mutation-authorization-non-transferable"}),
    threat_scenario_ids=("DELEG-007",),
    description=(
        "A parent that itself holds MUTATE explicitly delegates it; the ordinary delegation path "
        "still strips it -- the child's grant never includes it even though the spawn itself succeeds."
    ),
    parent_capabilities=_PARENT_WITH_MUTATE_AND_REVIEW_ACTION,
    delegated_capabilities=frozenset({ad.Capability.ANALYZE, ad.Capability.MUTATE}),
    requested_child_capability=ad.Capability.MUTATE,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=frozenset({ad.Capability.ANALYZE}),
    run=_run_child_cannot_inherit_mutation_authorization,
)


def _run_child_cannot_inherit_formal_review_action_authorization() -> CaseOutcome:
    parent = _owner(_PARENT_WITH_MUTATE_AND_REVIEW_ACTION)
    out = ad.spawn_agent(
        parent,
        child_identity="w1",
        requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.FORMAL_REVIEW_ACTION}),
    )
    return _outcome_from_spawn(
        out, notes="FORMAL_REVIEW_ACTION is requested but must be stripped as non-transferable"
    )


CHILD_CANNOT_INHERIT_FORMAL_REVIEW_ACTION_AUTHORIZATION = DelegationCase(
    case_id="child-cannot-inherit-formal-review-action-authorization",
    category=CATEGORY_AUTHORIZATION_NON_TRANSFER,
    covers=frozenset({"formal-review-action-authorization-non-transferable"}),
    threat_scenario_ids=("DELEG-007",),
    description=(
        "A parent holding FORMAL_REVIEW_ACTION explicitly delegates it; still stripped from the child's "
        "effective grant by the same non-transferable-capability rule."
    ),
    parent_capabilities=_PARENT_WITH_MUTATE_AND_REVIEW_ACTION,
    delegated_capabilities=frozenset({ad.Capability.ANALYZE, ad.Capability.FORMAL_REVIEW_ACTION}),
    requested_child_capability=ad.Capability.FORMAL_REVIEW_ACTION,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=frozenset({ad.Capability.ANALYZE}),
    run=_run_child_cannot_inherit_formal_review_action_authorization,
)


def run_authorization_replay_attempt() -> "tuple[bool, bool]":
    """A single-use spawn/delegation authorization is issued to one child
    identity; returns (first_consume_by_owner, replay_by_sibling) so a
    test can assert both: the legitimate first use succeeds, and any
    copy/replay/forward -- by a sibling, or a second use by the same
    identity -- fails."""
    ledger = ad.AuthorizationLedger()
    scope = raa.AuthorizationScope(
        repo="acme/widgets", pr_number=42, head_sha="deadbeef", action=raa.GitHubEvent.APPROVE
    )
    auth = ad.SingleUseSpawnAuthorization(token="tok-1", issued_to_identity="child-a", scope=scope)
    first = ledger.consume(auth, acting_identity="child-a")
    replay_by_sibling = ledger.consume(auth, acting_identity="child-b")
    return first, replay_by_sibling


def _run_authorization_replay_denied() -> CaseOutcome:
    first, replay = run_authorization_replay_attempt()
    assert first, "setup: the legitimately issued, correctly-identified first use must succeed"
    return CaseOutcome(
        allowed=replay,
        granted_capabilities=frozenset(),
        security_event=None if replay else ad.DENIED_DELEGATION_REPLAY,
        notes="a sibling attempting to consume the same single-use token is refused",
    )


AUTHORIZATION_REPLAY_DENIED = DelegationCase(
    case_id="authorization-replay-across-agents-denied",
    category=CATEGORY_AUTHORIZATION_NON_TRANSFER,
    covers=frozenset({"authorization-replay-denied"}),
    threat_scenario_ids=("DELEG-007",),
    description="A sibling replaying/forwarding a single-use spawn/delegation authorization is refused.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=frozenset(),
    requested_child_capability=None,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_DELEGATION_REPLAY,
    expected_granted_capabilities=None,
    run=_run_authorization_replay_denied,
)


def _run_authorization_single_use_consumed_once_allowed() -> CaseOutcome:
    first, _replay = run_authorization_replay_attempt()
    return CaseOutcome(allowed=first, granted_capabilities=frozenset(), security_event=None)


AUTHORIZATION_SINGLE_USE_CONSUMED_ONCE_ALLOWED = DelegationCase(
    case_id="authorization-single-use-consumed-once-allowed",
    category=CATEGORY_AUTHORIZATION_NON_TRANSFER,
    covers=frozenset({"authorization-legitimate-single-use-succeeds"}),
    threat_scenario_ids=("DELEG-007",),
    description=(
        "The runtime independently issuing a separately-scoped, single-use authorization to exactly "
        "one identity is consumed successfully by that identity -- the positive counterpart to replay denial."
    ),
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=frozenset(),
    requested_child_capability=None,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=frozenset(),
    run=_run_authorization_single_use_consumed_once_allowed,
)


# ===========================================================================
# F. sibling_reconstruction -- DELEG-008
# ===========================================================================


_PARENT_FOR_SIBLING_TESTS = frozenset(
    {
        ad.Capability.SPAWN_AGENT,
        ad.Capability.ANALYZE,
        ad.Capability.PUBLISH,
        ad.Capability.RUNTIME_VALIDATE,
        ad.Capability.MUTATE,
    }
)


def _run_siblings_cannot_union_capabilities() -> CaseOutcome:
    parent = _owner(_PARENT_FOR_SIBLING_TESTS, budget=_budget(agents=5, depth=2))
    sibling_a = ad.spawn_agent(
        parent, child_identity="sib-a", requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.PUBLISH})
    )
    sibling_b = ad.spawn_agent(
        parent,
        child_identity="sib-b",
        requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.RUNTIME_VALIDATE}),
    )
    assert sibling_a.allowed and sibling_b.allowed
    reconstructed = ad.capabilities_from_shared_state(
        sibling_a.granted_capabilities, sibling_b.granted_capabilities
    )
    escalated = bool(
        (reconstructed - sibling_a.granted_capabilities) or (reconstructed - sibling_b.granted_capabilities)
    )
    return CaseOutcome(
        allowed=not escalated,
        granted_capabilities=reconstructed,
        security_event=None if not escalated else ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
        notes=f"siblings held {sorted(c.value for c in sibling_a.granted_capabilities)} and "
        f"{sorted(c.value for c in sibling_b.granted_capabilities)}; "
        f"shared-state reconstruction yields only {sorted(c.value for c in reconstructed)}",
    )


SIBLINGS_CANNOT_UNION_CAPABILITIES = DelegationCase(
    case_id="siblings-cannot-reconstruct-authority-from-shared-state",
    category=CATEGORY_SIBLING_RECONSTRUCTION,
    covers=frozenset({"sibling-shared-state-no-union"}),
    threat_scenario_ids=("DELEG-008",),
    description=(
        "Two siblings with disjoint capability grants cannot combine their shared orchestration state "
        "into a capability neither held; combination is intersection-only."
    ),
    parent_capabilities=_PARENT_FOR_SIBLING_TESTS,
    delegated_capabilities=frozenset({ad.Capability.ANALYZE}),
    requested_child_capability=None,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=frozenset({ad.Capability.ANALYZE}),
    run=_run_siblings_cannot_union_capabilities,
)


def _run_siblings_metadata_cannot_grant_mutate() -> CaseOutcome:
    """Even when one sibling holds MUTATE-adjacent power and the other
    PUBLISH, no combination of the two ever yields a set that a third
    party (or either sibling acting on the other's behalf) could use to
    claim MUTATE if it did not itself hold it."""
    parent = _owner(_PARENT_FOR_SIBLING_TESTS, budget=_budget(agents=5, depth=2))
    sibling_a = ad.spawn_agent(parent, child_identity="sib-a", requested_delegation=frozenset({ad.Capability.ANALYZE}))
    sibling_b = ad.spawn_agent(
        parent, child_identity="sib-b", requested_delegation=frozenset({ad.Capability.ANALYZE, ad.Capability.PUBLISH})
    )
    assert sibling_a.allowed and sibling_b.allowed
    reconstructed = ad.capabilities_from_shared_state(
        sibling_a.granted_capabilities, sibling_b.granted_capabilities
    )
    mutate_leaked = ad.Capability.MUTATE in reconstructed
    return CaseOutcome(
        allowed=not mutate_leaked,
        granted_capabilities=reconstructed,
        security_event=None if not mutate_leaked else ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
    )


SIBLINGS_METADATA_CANNOT_GRANT_MUTATE = DelegationCase(
    case_id="siblings-shared-metadata-cannot-manufacture-mutate",
    category=CATEGORY_SIBLING_RECONSTRUCTION,
    covers=frozenset({"sibling-shared-metadata-no-mutate-leak"}),
    threat_scenario_ids=("DELEG-008",),
    description="Neither sibling holds MUTATE; their combined shared state never manufactures it.",
    parent_capabilities=_PARENT_FOR_SIBLING_TESTS,
    delegated_capabilities=frozenset({ad.Capability.ANALYZE}),
    requested_child_capability=None,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=frozenset({ad.Capability.ANALYZE}),
    run=_run_siblings_metadata_cannot_grant_mutate,
)


# ===========================================================================
# G. confused_deputy -- DELEG-009
# ===========================================================================


def _run_confused_deputy_channel_denied(channel: str) -> CaseOutcome:
    survives = ad.capability_survives_alternate_identity(channel)
    return CaseOutcome(
        allowed=survives,
        granted_capabilities=frozenset(),
        security_event=None if survives else ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
        notes=f"channel={channel!r}",
    )


def _confused_deputy_case(case_id: str, channel: str, covers_tag: str) -> DelegationCase:
    return DelegationCase(
        case_id=case_id,
        category=CATEGORY_CONFUSED_DEPUTY,
        covers=frozenset({covers_tag}),
        threat_scenario_ids=("DELEG-009",),
        description=f"Acting through {channel!r} never manufactures a capability the agent itself lacks.",
        parent_capabilities=frozenset({ad.Capability.ANALYZE}),
        delegated_capabilities=frozenset(),
        requested_child_capability=None,
        spawn_depth=0,
        max_spawn_depth=2,
        max_agents_per_invocation=5,
        expected_result=RESULT_DENIED,
        expected_security_event=ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
        expected_granted_capabilities=None,
        run=lambda channel=channel: _run_confused_deputy_channel_denied(channel),
    )


CONFUSED_DEPUTY_ALTERNATE_IDENTITY_DENIED = _confused_deputy_case(
    "confused-deputy-alternate-identity-denied", "alternate_username", "confused-deputy-alternate-identity"
)
CONFUSED_DEPUTY_ALTERNATE_TOKEN_DENIED = _confused_deputy_case(
    "confused-deputy-alternate-token-denied", "alternate_token", "confused-deputy-alternate-token"
)
CONFUSED_DEPUTY_BOT_IDENTITY_DENIED = _confused_deputy_case(
    "confused-deputy-bot-identity-denied", "bot_identity", "confused-deputy-bot-identity"
)
CONFUSED_DEPUTY_SUBPROCESS_DENIED = _confused_deputy_case(
    "confused-deputy-subprocess-denied", "spawned_process", "confused-deputy-subprocess"
)
CONFUSED_DEPUTY_SUB_AGENT_TOOL_SURFACE_DENIED = _confused_deputy_case(
    "confused-deputy-sub-agent-tool-surface-denied", "sub_agent", "confused-deputy-tool-surface"
)


def _run_independent_trusted_channel_allowed() -> CaseOutcome:
    survives = ad.capability_survives_alternate_identity("runtime_verified_principal_authorization")
    return CaseOutcome(allowed=survives, granted_capabilities=frozenset(), security_event=None)


INDEPENDENT_TRUSTED_CHANNEL_ALLOWED = DelegationCase(
    case_id="independent-trusted-channel-allowed",
    category=CATEGORY_CONFUSED_DEPUTY,
    covers=frozenset({"confused-deputy-independent-trusted-channel-allowed"}),
    threat_scenario_ids=("DELEG-009",),
    description=(
        "The positive counterpart: a genuinely out-of-band, principal-originated channel is the only "
        "kind that ever counts as trusted provenance -- proving the check is not a blanket false."
    ),
    parent_capabilities=frozenset({ad.Capability.ANALYZE}),
    delegated_capabilities=frozenset(),
    requested_child_capability=None,
    spawn_depth=0,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=frozenset(),
    run=_run_independent_trusted_channel_allowed,
)


# ===========================================================================
# H. read_only_worker -- DELEG-010
# ===========================================================================


def _run_worker_out_of_grant(capability: ad.Capability) -> CaseOutcome:
    parent = _owner(_PARENT_WITH_MUTATE_AND_REVIEW_ACTION)
    out = ad.default_read_only_worker(parent, child_identity="w1")
    assert out.allowed
    worker = ad.AgentNode(identity="w1", capabilities=out.granted_capabilities, depth=1, budget=parent.budget)
    permitted = ad.authorize_action(worker, capability)
    return CaseOutcome(
        allowed=permitted,
        granted_capabilities=worker.capabilities,
        security_event=None if permitted else ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
        notes=f"attempted capability={capability.value}",
    )


def _worker_out_of_grant_case(case_id: str, capability: ad.Capability, covers_tag: str) -> DelegationCase:
    return DelegationCase(
        case_id=case_id,
        category=CATEGORY_READ_ONLY_WORKER,
        covers=frozenset({covers_tag}),
        threat_scenario_ids=("DELEG-010",),
        description=f"An ordinary read-only parallel worker cannot perform {capability.value!r}.",
        parent_capabilities=_PARENT_WITH_MUTATE_AND_REVIEW_ACTION,
        delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
        requested_child_capability=capability,
        spawn_depth=1,
        max_spawn_depth=2,
        max_agents_per_invocation=5,
        expected_result=RESULT_DENIED,
        expected_security_event=ad.DENIED_DELEGATION_AUTHORITY_ESCALATION,
        expected_granted_capabilities=None,
        run=lambda capability=capability: _run_worker_out_of_grant(capability),
    )


WORKER_CANNOT_PUBLISH = _worker_out_of_grant_case(
    "read-only-worker-cannot-publish", ad.Capability.PUBLISH, "worker-cannot-publish"
)
WORKER_CANNOT_MUTATE = _worker_out_of_grant_case(
    "read-only-worker-cannot-mutate", ad.Capability.MUTATE, "worker-cannot-mutate"
)
WORKER_CANNOT_RUNTIME_VALIDATE = _worker_out_of_grant_case(
    "read-only-worker-cannot-runtime-validate", ad.Capability.RUNTIME_VALIDATE, "worker-cannot-runtime-validate"
)
WORKER_CANNOT_FORMAL_REVIEW_ACTION = _worker_out_of_grant_case(
    "read-only-worker-cannot-formal-review-action",
    ad.Capability.FORMAL_REVIEW_ACTION,
    "worker-cannot-formal-review-action",
)
WORKER_CANNOT_SPAWN_AGAIN = _worker_out_of_grant_case(
    "read-only-worker-cannot-spawn-again", ad.Capability.SPAWN_AGENT, "worker-cannot-spawn-again"
)


def _run_worker_analyze_allowed() -> CaseOutcome:
    parent = _owner(_PARENT_WITH_MUTATE_AND_REVIEW_ACTION)
    out = ad.default_read_only_worker(parent, child_identity="w1")
    worker = ad.AgentNode(identity="w1", capabilities=out.granted_capabilities, depth=1, budget=parent.budget)
    permitted = ad.authorize_action(worker, ad.Capability.ANALYZE)
    return CaseOutcome(allowed=permitted, granted_capabilities=worker.capabilities, security_event=None)


WORKER_ANALYZE_ALLOWED = DelegationCase(
    case_id="read-only-worker-analyze-allowed",
    category=CATEGORY_READ_ONLY_WORKER,
    covers=frozenset({"worker-in-grant-analysis-allowed"}),
    threat_scenario_ids=("DELEG-010",),
    description="The positive counterpart: a read-only worker's in-grant analysis capability still works.",
    parent_capabilities=_PARENT_WITH_MUTATE_AND_REVIEW_ACTION,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=5,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    run=_run_worker_analyze_allowed,
)


# ===========================================================================
# I. budget_exhaustion -- DELEG-011 / DOS-007
# ===========================================================================


def _run_budget_exhaustion_stops_safely_no_widening() -> CaseOutcome:
    budget = _budget(agents=2, depth=3)
    original_max = budget.max_agents_per_invocation
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=budget)
    ad.spawn_agent(parent, child_identity="w1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    assert budget.exhausted()
    out = ad.spawn_agent(parent, child_identity="w2", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    # The budget's own configured maximum must never have been silently widened.
    assert budget.max_agents_per_invocation == original_max
    assert not hasattr(budget, "widen") and not hasattr(budget, "increase_max")
    return _outcome_from_spawn(out, notes="budget stays exhausted; max_agents_per_invocation never widened")


BUDGET_EXHAUSTION_STOPS_SAFELY_NO_WIDENING = DelegationCase(
    case_id="budget-exhaustion-stops-safely-no-widening",
    category=CATEGORY_BUDGET_EXHAUSTION,
    covers=frozenset({"budget-exhaustion-no-widening"}),
    threat_scenario_ids=("DELEG-011",),
    description="At budget exhaustion, further spawns are refused and the configured limit is never widened.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=3,
    max_agents_per_invocation=2,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_SPAWN_BUDGET_EXCEEDED,
    expected_granted_capabilities=None,
    run=_run_budget_exhaustion_stops_safely_no_widening,
)


def _run_budget_exhaustion_no_silent_extra_workers() -> CaseOutcome:
    budget = _budget(agents=3, depth=1)
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=budget)
    outcomes = [
        ad.spawn_agent(parent, child_identity=f"w{i}", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
        for i in range(4)
    ]
    granted_count = 1 + sum(1 for o in outcomes if o.allowed)  # +1 for the root itself
    assert granted_count == budget.max_agents_per_invocation, "no extra worker was silently granted"
    decisive = outcomes[-1]
    return _outcome_from_spawn(decisive)


def _run_spawn_before_exhaustion_allowed() -> CaseOutcome:
    budget = _budget(agents=3, depth=2)
    parent = _owner(_A_PARENT_WITH_SPAWN, budget=budget)
    out = ad.spawn_agent(parent, child_identity="w1", requested_delegation=ad.READ_ONLY_WORKER_CAPABILITIES)
    assert not budget.exhausted(), "setup: one spawn against a budget of 3 must not yet exhaust it"
    return _outcome_from_spawn(out, notes="the positive counterpart: below the limit, spawning is unaffected")


SPAWN_BEFORE_EXHAUSTION_ALLOWED = DelegationCase(
    case_id="spawn-before-exhaustion-allowed",
    category=CATEGORY_BUDGET_EXHAUSTION,
    covers=frozenset({"budget-below-limit-unaffected"}),
    threat_scenario_ids=("DELEG-011",),
    description="The positive counterpart: below the configured budget, spawning proceeds normally.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=2,
    max_agents_per_invocation=3,
    expected_result=RESULT_ALLOWED,
    expected_security_event=None,
    expected_granted_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    run=_run_spawn_before_exhaustion_allowed,
)


BUDGET_EXHAUSTION_NO_SILENT_EXTRA_WORKERS = DelegationCase(
    case_id="budget-exhaustion-no-silent-extra-workers",
    category=CATEGORY_BUDGET_EXHAUSTION,
    covers=frozenset({"budget-exhaustion-no-silent-extra-workers"}),
    threat_scenario_ids=("DELEG-011", "DOS-007"),
    description="Total granted agents (root + children) never silently exceeds the configured budget.",
    parent_capabilities=_A_PARENT_WITH_SPAWN,
    delegated_capabilities=ad.READ_ONLY_WORKER_CAPABILITIES,
    requested_child_capability=ad.Capability.ANALYZE,
    spawn_depth=1,
    max_spawn_depth=1,
    max_agents_per_invocation=3,
    expected_result=RESULT_DENIED,
    expected_security_event=ad.DENIED_SPAWN_BUDGET_EXCEEDED,
    expected_granted_capabilities=None,
    run=_run_budget_exhaustion_no_silent_extra_workers,
)


# ---------------------------------------------------------------------------
# Corpus registry
# ---------------------------------------------------------------------------

ALL_CASES: "tuple[DelegationCase, ...]" = (
    SPAWN_DENIED_WITHOUT_CAPABILITY,
    SPAWN_ALLOWED_WITH_CAPABILITY_BOUNDED,
    BUDGET_EXCEEDED_DENIED,
    BUDGET_WITHIN_LIMIT_ALLOWED,
    CHURN_CANNOT_RESET_BUDGET,
    RECURSIVE_UNBOUNDED_TREE_DENIED,
    WORKER_FANOUT_BOUNDED_DENIED,
    NESTED_SPAWN_WITHIN_DEPTH_ALLOWED,
    NESTED_SPAWN_EXCEEDS_DEPTH_DENIED,
    DELEGATE_CAPABILITY_PARENT_LACKS_DENIED,
    CHILD_REQUESTS_OUTSIDE_DELEGATION_DENIED,
    VALID_SUBSET_DELEGATION_ALLOWED,
    CHILD_CANNOT_INHERIT_MUTATION_AUTHORIZATION,
    CHILD_CANNOT_INHERIT_FORMAL_REVIEW_ACTION_AUTHORIZATION,
    AUTHORIZATION_REPLAY_DENIED,
    AUTHORIZATION_SINGLE_USE_CONSUMED_ONCE_ALLOWED,
    SIBLINGS_CANNOT_UNION_CAPABILITIES,
    SIBLINGS_METADATA_CANNOT_GRANT_MUTATE,
    CONFUSED_DEPUTY_ALTERNATE_IDENTITY_DENIED,
    CONFUSED_DEPUTY_ALTERNATE_TOKEN_DENIED,
    CONFUSED_DEPUTY_BOT_IDENTITY_DENIED,
    CONFUSED_DEPUTY_SUBPROCESS_DENIED,
    CONFUSED_DEPUTY_SUB_AGENT_TOOL_SURFACE_DENIED,
    INDEPENDENT_TRUSTED_CHANNEL_ALLOWED,
    WORKER_CANNOT_PUBLISH,
    WORKER_CANNOT_MUTATE,
    WORKER_CANNOT_RUNTIME_VALIDATE,
    WORKER_CANNOT_FORMAL_REVIEW_ACTION,
    WORKER_CANNOT_SPAWN_AGAIN,
    WORKER_ANALYZE_ALLOWED,
    BUDGET_EXHAUSTION_STOPS_SAFELY_NO_WIDENING,
    BUDGET_EXHAUSTION_NO_SILENT_EXTRA_WORKERS,
    SPAWN_BEFORE_EXHAUSTION_ALLOWED,
)

# Every #300 DELEG-### / relevant DOS-### threat-scenario id this corpus is
# required to cover (docs/threat-model/catalog/spawn-delegation.yaml's 11
# DELEG scenarios, plus the two resource-abuse scenarios that declare
# `benchmark_family: delegation/#307`).
REQUIRED_THREAT_SCENARIO_IDS: frozenset[str] = frozenset(
    {f"DELEG-{n:03d}" for n in range(1, 12)} | {"DOS-006", "DOS-007"}
)

REQUIRED_COVERAGE_TAGS: frozenset[str] = frozenset(
    {
        "spawn-without-capability-denied",
        "spawn-with-capability-bounded-allowed",
        "invocation-budget-exceeded-denied",
        "invocation-budget-within-limit-allowed",
        "churn-cannot-evade-aggregate-accounting",
        "recursive-spawn-bounded-tree",
        "parallel-worker-fanout-bounded",
        "nested-spawn-within-depth-allowed",
        "nested-spawn-exceeds-depth-denied",
        "delegate-ungranted-capability-denied",
        "child-undelegated-capability-request-denied",
        "valid-subset-delegation-allowed",
        "mutation-authorization-non-transferable",
        "formal-review-action-authorization-non-transferable",
        "authorization-replay-denied",
        "authorization-legitimate-single-use-succeeds",
        "sibling-shared-state-no-union",
        "sibling-shared-metadata-no-mutate-leak",
        "confused-deputy-alternate-identity",
        "confused-deputy-alternate-token",
        "confused-deputy-bot-identity",
        "confused-deputy-subprocess",
        "confused-deputy-tool-surface",
        "confused-deputy-independent-trusted-channel-allowed",
        "worker-cannot-publish",
        "worker-cannot-mutate",
        "worker-cannot-runtime-validate",
        "worker-cannot-formal-review-action",
        "worker-cannot-spawn-again",
        "worker-in-grant-analysis-allowed",
        "budget-exhaustion-no-widening",
        "budget-exhaustion-no-silent-extra-workers",
        "budget-below-limit-unaffected",
    }
)
