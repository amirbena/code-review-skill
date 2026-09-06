#!/usr/bin/env python3
"""Architectural-placement regression fixtures (Issue #153).

`shared/policies/review-scope.md`, "Architectural placement and
execution-lifecycle fidelity" teaches both review Skills *when to expand
review context* beyond the changed method/file to detect behavior that is
locally correct but architecturally misplaced, and *when to stop*. This
module encodes **paired local-only vs. bounded-context-expansion outcomes**
across structurally different pattern families and asserts, per fixture,
the machine-checkable decisions that section requires:

* whether a **semantic-risk trigger** fires at all (structural shape —
  a large method, a changed file, an early return, a framework/method name
  — never triggers on its own);
* how far the **bounded ladder** expands
  (`changed behavior → direct caller/callee → owning
  abstraction/interface/orchestrator → sibling/contract only if
  necessary`);
* which **stop condition** (1-5) terminates the expansion, including
  "insufficient evidence" as a valid *terminal* outcome (condition 4);
* the resulting **finding vs. no-finding**, and — for the two
  outcome-based fixtures the issue mandates — that this differs from what
  changed-method-only reasoning would have concluded.

The only logic in this module is ``_evaluate`` — a direct transcription of
that policy section's trigger list, ladder, and stop conditions, cited
inline. It is deliberately **not** a reusable reference model: there is no
``tests/reference`` module and no second definition of the review rule (see
`tests/policy/test_review_scope_behavioral_heuristics.py`,
`NoSecondSourceOfTruthTests`). Two runs of the same corpus, exactly as the
#61 / #66 regression suites:

1. ``ArchitecturalPlacementFixtureTests`` — the transcription must satisfy
   every fixture;
2. ``InducedRegressionTests`` — each representative "reasoned too locally"
   or "over-expanded" mutation must be caught by at least one fixture,
   proving the corpus bites.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Trigger(Enum):
    """Semantic-risk categories from review-scope.md, "When to expand
    context — semantic risk triggers". ``NONE`` means the change touches no
    such category: the section "does not apply" and no expansion occurs."""

    CONTROL_FLOW = "control flow / whether downstream code executes"
    SIDE_EFFECT = "externally visible or irreversible side effects"
    RETRY_ERROR = "retry, exception, fallback, or error-propagation"
    TRANSACTION = "transaction boundaries or transactional ordering"
    AUTHORIZATION = "authorization, permission, or policy enforcement"
    ROUTING_DISPATCH = "routing, dispatch, handler/strategy selection"
    IDEMPOTENCY = "idempotency or duplicate suppression"
    STATE_ORDERING = "state-mutation ordering"
    LIFECYCLE_BOOKKEEPING = "lifecycle bookkeeping"
    RESOURCE_OWNERSHIP = "resource ownership or cleanup"
    CONCURRENCY = "concurrency or ordering guarantees"
    CALLER_CALLEE_CONTRACT = "correctness depends on a caller/callee contract"
    NONE = "no semantic-risk category"


# Stop conditions, numbered exactly as review-scope.md lists them.
STOP_NOT_TRIGGERED = 0  # no semantic trigger — the section does not apply
STOP_CONTRACT_ESTABLISHED = 1  # evidence supports a finding
STOP_CORRECTLY_PLACED = 2  # architecture shows the placement is correct
STOP_NO_MATERIAL_CHANGE = 3  # more context would not change the conclusion
STOP_INSUFFICIENT_EVIDENCE = 4  # fail closed; terminal, not speculative
STOP_DISPROPORTIONATE = 5  # would need unrelated repo-wide exploration


@dataclass(frozen=True)
class Boundary:
    """A candidate owning abstraction discovered during expansion."""

    location: str
    kind: str  # e.g. "dispatcher predicate", "retry orchestrator", "middleware"
    owns_this_decision: bool  # False → predicate/boundary with unrelated semantics
    evidence_sufficient: bool  # False → repo evidence cannot establish ownership


@dataclass(frozen=True)
class Fixture:
    name: str
    family: str
    changed_behavior: str
    trigger: Trigger
    # Structural-only signals present in the diff. Per the policy these must
    # NEVER by themselves cause context expansion.
    structural_signals: tuple[str, ...] = ()
    boundary: Optional[Boundary] = None
    # The changed code sits where `boundary` should own the decision.
    placement_conflicts_with_boundary: bool = False
    # Negative: the check must stay on the execution path so an
    # exception/retry contract is honored (missing-entity / NotFoundException).
    must_execute_and_fail: bool = False
    cross_file: bool = False
    # Output is functionally identical either way, but lifecycle / side-effect
    # semantics differ (handler still runs, action still recorded, ...).
    lifecycle_semantics_differ: bool = False
    # What changed-method-only / diff-only reasoning concludes.
    local_only_conclusion: str = "NO_FINDING"  # "NO_FINDING" | "FINDING"
    # Expected results of the bounded mechanism.
    expected_expansion: bool = True
    expected_stop: int = STOP_CONTRACT_ESTABLISHED
    expected_outcome: str = "FINDING"  # "FINDING" | "NO_FINDING"
    notes: str = ""


@dataclass
class Result:
    expanded: bool
    stop: int
    outcome: str


def _evaluate(fx: Fixture, *, mutation: str | None = None) -> Result:
    """Transcription of review-scope.md, "Architectural placement and
    execution-lifecycle fidelity": trigger gate → bounded ladder → stop
    conditions. ``mutation`` injects one representative reasoning bug for
    the induced-regression run; ``None`` is the faithful implementation."""

    # --- Trigger gate -----------------------------------------------------
    # "Do not expand context merely because a method is large, a file
    # changed, an early return exists, or a particular framework/method
    # name appears. Structural shape is never itself the trigger."
    triggered = fx.trigger is not Trigger.NONE
    if mutation == "structural_triggers":
        # Bug: treat any structural signal as a reason to expand.
        triggered = triggered or bool(fx.structural_signals)
    if not triggered:
        return Result(expanded=False, stop=STOP_NOT_TRIGGERED, outcome="NO_FINDING")

    # --- Bounded context expansion --------------------------------------
    # We expand ring by ring: caller/callee → owning boundary. The fixture
    # already carries what that expansion would find.
    boundary = fx.boundary

    # Stop condition 4 — "repository evidence is insufficient or ambiguous
    # — fail closed, do not invent the architecture." No owning boundary
    # found at all, OR a boundary whose semantics are unrelated, OR
    # evidence that cannot establish ownership.
    if boundary is None:
        if mutation == "invent_architecture":
            # Bug: assume an owner must exist and flag anyway.
            return Result(True, STOP_CONTRACT_ESTABLISHED, "FINDING")
        return Result(True, STOP_INSUFFICIENT_EVIDENCE, "NO_FINDING")

    if not boundary.owns_this_decision:
        if mutation == "naming_is_enough":
            # Bug: infer ownership from a boundary-looking name.
            return Result(True, STOP_CONTRACT_ESTABLISHED, "FINDING")
        return Result(True, STOP_INSUFFICIENT_EVIDENCE, "NO_FINDING")

    if not boundary.evidence_sufficient:
        if mutation == "evidence_optional":
            # Bug: emit despite unresolvable ambiguity.
            return Result(True, STOP_CONTRACT_ESTABLISHED, "FINDING")
        return Result(True, STOP_INSUFFICIENT_EVIDENCE, "NO_FINDING")

    # --- Ineligible versus must-execute-and-fail ------------------------
    # "a missing-entity / null case that must still flow into execution so
    # a NotFoundException is raised and existing retry semantics are
    # preserved is not a misplacement." The boundary establishes the
    # execution-path placement is correct → stop condition 2.
    if fx.must_execute_and_fail and mutation != "ignore_retry_contract":
        return Result(True, STOP_CORRECTLY_PLACED, "NO_FINDING")

    # Stop condition 2 — "the surrounding architecture establishes that the
    # changed behavior is correctly placed." Nothing to report.
    if not fx.placement_conflicts_with_boundary:
        if mutation == "prefer_cleaner":
            # Bug: flag because another location looks aesthetically cleaner.
            return Result(True, STOP_CONTRACT_ESTABLISHED, "FINDING")
        return Result(True, STOP_CORRECTLY_PLACED, "NO_FINDING")

    # Stop condition 1 — "the relevant responsibility/lifecycle contract is
    # established with enough repository evidence to support a finding."
    # This holds even when the final output is functionally identical but
    # lifecycle / side-effect semantics differ.
    return Result(True, STOP_CONTRACT_ESTABLISHED, "FINDING")


# --------------------------------------------------------------------------
# The corpus — structurally different pattern families (issue #153 list).
# --------------------------------------------------------------------------
FIXTURES: tuple[Fixture, ...] = (
    # 1. Positive — dispatcher/handler eligibility decided inside execution,
    #    strategy-style `supports()` naming variant. OUTCOME-BASED (a):
    #    local-only reasoning sees a correct early return and passes;
    #    expansion finds the eligibility phase that owns the decision.
    Fixture(
        name="eligibility_check_inside_execution",
        family="dispatcher/handler eligibility",
        changed_behavior="funding-source guard added inside execute(); dispatcher "
        "already calls an eligibility predicate before execute()",
        trigger=Trigger.CONTROL_FLOW,
        structural_signals=("early return", "large method"),
        boundary=Boundary(
            location="dispatcher.select()",
            kind="strategy eligibility predicate",
            owns_this_decision=True,
            evidence_sufficient=True,
        ),
        placement_conflicts_with_boundary=True,
        lifecycle_semantics_differ=True,
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_CONTRACT_ESTABLISHED,
        expected_outcome="FINDING",
        notes="outcome-based: diff-only reasoning would produce REVIEW CLEAN",
    ),
    # 2. Positive — retry loop added below an existing orchestration layer.
    Fixture(
        name="retry_duplicated_below_orchestrator",
        family="retry duplicated below retry/orchestration layer",
        changed_behavior="per-call while-retry loop added inside a worker the "
        "job orchestrator already retries with backoff",
        trigger=Trigger.RETRY_ERROR,
        structural_signals=("nested loop",),
        boundary=Boundary(
            location="JobOrchestrator.run_with_retry()",
            kind="retry orchestrator",
            owns_this_decision=True,
            evidence_sufficient=True,
        ),
        placement_conflicts_with_boundary=True,
        cross_file=True,
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_CONTRACT_ESTABLISHED,
        expected_outcome="FINDING",
    ),
    # 3. Positive — authorization first/again below an established boundary.
    Fixture(
        name="authz_below_middleware_boundary",
        family="authorization below an established authorization boundary",
        changed_behavior="role check added inside service method already gated "
        "by route middleware; service is only reachable through that route",
        trigger=Trigger.AUTHORIZATION,
        boundary=Boundary(
            location="middleware/authorize.py",
            kind="authorization middleware",
            owns_this_decision=True,
            evidence_sufficient=True,
        ),
        placement_conflicts_with_boundary=True,
        cross_file=True,
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_CONTRACT_ESTABLISHED,
        expected_outcome="FINDING",
    ),
    # 4. Positive — idempotency check after the side effect.
    Fixture(
        name="idempotency_after_side_effect",
        family="idempotency check after a side effect instead of before",
        changed_behavior="dedupe-key lookup added after the outbound charge call "
        "rather than before it",
        trigger=Trigger.IDEMPOTENCY,
        structural_signals=("early return",),
        boundary=Boundary(
            location="PaymentHandler.charge()",
            kind="side-effect ordering contract",
            owns_this_decision=True,
            evidence_sufficient=True,
        ),
        placement_conflicts_with_boundary=True,
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_CONTRACT_ESTABLISHED,
        expected_outcome="FINDING",
    ),
    # 5. Positive — transaction-sensitive logic outside the boundary.
    Fixture(
        name="write_outside_transaction_boundary",
        family="transaction-sensitive logic outside the intended boundary",
        changed_behavior="ledger write moved out of the @transactional service "
        "method into an after-commit callback",
        trigger=Trigger.TRANSACTION,
        boundary=Boundary(
            location="LedgerService.post() @transactional",
            kind="transaction boundary",
            owns_this_decision=True,
            evidence_sufficient=True,
        ),
        placement_conflicts_with_boundary=True,
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_CONTRACT_ESTABLISHED,
        expected_outcome="FINDING",
    ),
    # 6. Negative — local code looks suspicious but is correctly placed.
    #    OUTCOME-BASED (b): local-only reasoning flags the in-method check;
    #    expansion finds the real eligibility phase and confirms it owns a
    #    *different* concern, so the changed check belongs where it is.
    Fixture(
        name="in_method_validation_is_correctly_placed",
        family="negative: locally suspicious but correctly placed",
        changed_behavior="amount-range validation added at the top of execute(); "
        "the dispatcher predicate exists but owns event-type routing only",
        trigger=Trigger.CONTROL_FLOW,
        structural_signals=("early return", "large method"),
        boundary=Boundary(
            location="dispatcher.select()",
            kind="event-type eligibility predicate",
            owns_this_decision=True,  # genuinely owns routing decisions...
            evidence_sufficient=True,
        ),
        placement_conflicts_with_boundary=False,  # ...but not amount validation
        local_only_conclusion="FINDING",
        expected_stop=STOP_CORRECTLY_PLACED,
        expected_outcome="NO_FINDING",
        notes="outcome-based: local-only reasoning would raise a false positive",
    ),
    # 7. Negative — missing-entity / NotFoundException retry edge case.
    Fixture(
        name="missing_entity_must_reach_handler",
        family="negative: must-execute-and-fail preserves retry semantics",
        changed_behavior="null-entity branch kept inside handle() so a "
        "NotFoundException is raised and the queue redelivers",
        trigger=Trigger.RETRY_ERROR,
        structural_signals=("early return",),
        boundary=Boundary(
            location="EventsDispatcher.shouldHandle()",
            kind="eligibility predicate",
            owns_this_decision=True,
            evidence_sufficient=True,
        ),
        placement_conflicts_with_boundary=True,  # structurally looks movable
        must_execute_and_fail=True,  # ...but moving it suppresses the retry
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_CORRECTLY_PLACED,
        expected_outcome="NO_FINDING",
    ),
    # 8. Negative — no separate owning boundary exists at all.
    Fixture(
        name="no_owning_boundary_in_repo",
        family="negative: no owning boundary exists",
        changed_behavior="feature-flag guard added in the only place the "
        "feature is invoked; no router, dispatcher, or policy layer exists",
        trigger=Trigger.CONTROL_FLOW,
        boundary=None,
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_INSUFFICIENT_EVIDENCE,
        expected_outcome="NO_FINDING",
    ),
    # 9a. Negative — a boundary-looking symbol with unrelated semantics.
    Fixture(
        name="predicate_has_unrelated_semantics",
        family="negative: apparent predicate, unrelated semantics",
        changed_behavior="tax rule added inside compute(); a nearby "
        "currency-narrowing predicate does not own tax-rule selection",
        trigger=Trigger.CONTROL_FLOW,
        boundary=Boundary(
            location="CurrencyStrategy.accepts()",
            kind="currency predicate",
            owns_this_decision=False,
            evidence_sufficient=True,
        ),
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_INSUFFICIENT_EVIDENCE,
        expected_outcome="NO_FINDING",
    ),
    # 9b. Negative — an owning boundary plausibly exists but repository
    #     evidence cannot establish that it owns this decision. Fail closed.
    Fixture(
        name="ownership_evidence_is_ambiguous",
        family="negative: insufficient evidence to establish ownership",
        changed_behavior="capacity guard added inside reserve(); a scheduler "
        "layer might own admission, but the repo has no wiring proving it does",
        trigger=Trigger.CONTROL_FLOW,
        boundary=Boundary(
            location="scheduler/admission.py",
            kind="admission-control layer (suspected)",
            owns_this_decision=True,
            evidence_sufficient=False,  # no call path / contract proving it
        ),
        placement_conflicts_with_boundary=True,
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_INSUFFICIENT_EVIDENCE,
        expected_outcome="NO_FINDING",
    ),
    # 10. Positive — cross-file: boundary and changed code in different modules.
    Fixture(
        name="cross_file_owning_boundary",
        family="cross-file owning boundary",
        changed_behavior="consumer-side filter added in consumers/orders.py; the "
        "routing key that owns this selection lives in messaging/router.py",
        trigger=Trigger.ROUTING_DISPATCH,
        boundary=Boundary(
            location="messaging/router.py bind()",
            kind="broker routing binding",
            owns_this_decision=True,
            evidence_sufficient=True,
        ),
        placement_conflicts_with_boundary=True,
        cross_file=True,
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_CONTRACT_ESTABLISHED,
        expected_outcome="FINDING",
    ),
    # 11. Positive — identical output, different lifecycle/side-effect semantics.
    Fixture(
        name="identical_output_different_lifecycle",
        family="functionally identical output, lifecycle semantics differ",
        changed_behavior="skip decision moved into handle(); the event is still "
        "not published, but handle() now runs, marks the action taken, and logs",
        trigger=Trigger.LIFECYCLE_BOOKKEEPING,
        structural_signals=("early return",),
        boundary=Boundary(
            location="EventsDispatcher.shouldHandle()",
            kind="eligibility predicate",
            owns_this_decision=True,
            evidence_sufficient=True,
        ),
        placement_conflicts_with_boundary=True,
        lifecycle_semantics_differ=True,
        local_only_conclusion="NO_FINDING",
        expected_stop=STOP_CONTRACT_ESTABLISHED,
        expected_outcome="FINDING",
    ),
    # 12. Negative — structural shape only, no semantic-risk trigger.
    Fixture(
        name="structural_shape_only_no_trigger",
        family="negative: structural shape is not a trigger",
        changed_behavior="a 300-line pure formatting helper gained another "
        "early return; no control-flow, side-effect, or contract impact",
        trigger=Trigger.NONE,
        structural_signals=("large method", "early return", "framework base class"),
        boundary=None,
        local_only_conclusion="NO_FINDING",
        expected_expansion=False,
        expected_stop=STOP_NOT_TRIGGERED,
        expected_outcome="NO_FINDING",
    ),
)


OUTCOME_BASED_LOCAL_WRONGLY_CLEAN = "eligibility_check_inside_execution"
OUTCOME_BASED_LOCAL_WRONGLY_FLAGS = "in_method_validation_is_correctly_placed"


class ArchitecturalPlacementFixtureTests(unittest.TestCase):
    """(1) The faithful transcription satisfies every fixture."""

    def test_every_fixture_matches_the_policy_transcription(self) -> None:
        for fx in FIXTURES:
            with self.subTest(fixture=fx.name):
                res = _evaluate(fx)
                self.assertEqual(res.expanded, fx.expected_expansion)
                self.assertEqual(res.stop, fx.expected_stop)
                self.assertEqual(res.outcome, fx.expected_outcome)

    def test_structural_signals_alone_never_expand_context(self) -> None:
        for fx in FIXTURES:
            if fx.trigger is Trigger.NONE:
                with self.subTest(fixture=fx.name):
                    self.assertTrue(fx.structural_signals)
                    self.assertFalse(_evaluate(fx).expanded)

    def test_insufficient_evidence_is_a_terminal_no_finding(self) -> None:
        seen = [f for f in FIXTURES if f.expected_stop == STOP_INSUFFICIENT_EVIDENCE]
        self.assertGreaterEqual(len(seen), 3)  # cases 6, 8, 9 at least
        for fx in seen:
            self.assertEqual(_evaluate(fx).outcome, "NO_FINDING")

    def test_must_execute_and_fail_negative_is_not_a_misplacement(self) -> None:
        fx = next(f for f in FIXTURES if f.must_execute_and_fail)
        res = _evaluate(fx)
        self.assertEqual(res.outcome, "NO_FINDING")
        self.assertEqual(res.stop, STOP_CORRECTLY_PLACED)

    def test_corpus_has_several_structurally_different_positive_families(self) -> None:
        positive_families = {f.family for f in FIXTURES if f.expected_outcome == "FINDING"}
        self.assertGreaterEqual(len(positive_families), 6)

    def test_cross_file_fixture_present_and_produces_a_finding(self) -> None:
        fx = next(f for f in FIXTURES if f.name == "cross_file_owning_boundary")
        self.assertTrue(fx.cross_file)
        self.assertEqual(_evaluate(fx).outcome, "FINDING")

    def test_identical_output_but_different_lifecycle_still_finds(self) -> None:
        fx = next(f for f in FIXTURES if f.name == "identical_output_different_lifecycle")
        self.assertTrue(fx.lifecycle_semantics_differ)
        self.assertEqual(_evaluate(fx).outcome, "FINDING")

    def test_no_production_class_names_are_asserted_as_rules(self) -> None:
        # The motivating example's names may appear only as fixture data,
        # never as something the evaluator keys on.
        import inspect

        src = inspect.getsource(_evaluate)
        for banned in (
            "EventsDispatcherService",
            "ScheduledStatusChangeEventHandler",
            "shouldHandleEvent",
            "canHandle",
            "supports",
        ):
            self.assertNotIn(banned, src)


class OutcomeBasedValidationTests(unittest.TestCase):
    """The issue requires both directions: expansion must be shown to
    *change* the review outcome, not merely inspect extra files."""

    def test_local_only_would_wrongly_pass_but_expansion_finds_the_bug(self) -> None:
        fx = next(f for f in FIXTURES if f.name == OUTCOME_BASED_LOCAL_WRONGLY_CLEAN)
        self.assertEqual(fx.local_only_conclusion, "NO_FINDING")
        res = _evaluate(fx)
        self.assertEqual(res.outcome, "FINDING")
        self.assertNotEqual(res.outcome, fx.local_only_conclusion)

    def test_local_only_would_wrongly_flag_but_expansion_suppresses_it(self) -> None:
        fx = next(f for f in FIXTURES if f.name == OUTCOME_BASED_LOCAL_WRONGLY_FLAGS)
        self.assertEqual(fx.local_only_conclusion, "FINDING")
        res = _evaluate(fx)
        self.assertEqual(res.outcome, "NO_FINDING")
        self.assertNotEqual(res.outcome, fx.local_only_conclusion)


class InducedRegressionTests(unittest.TestCase):
    """(2) Each representative reasoning bug is caught by >=1 fixture."""

    MUTATIONS: tuple[str, ...] = (
        "structural_triggers",  # expands on structural shape alone
        "invent_architecture",  # invents an owner when none exists
        "naming_is_enough",  # infers ownership from a boundary-looking name
        "evidence_optional",  # emits despite unresolvable ambiguity
        "ignore_retry_contract",  # ignores must-execute-and-fail
        "prefer_cleaner",  # flags a correctly-placed check as "cleaner elsewhere"
    )

    def test_each_mutation_is_caught_by_at_least_one_fixture(self) -> None:
        for mutation in self.MUTATIONS:
            caught = []
            for fx in FIXTURES:
                faithful = _evaluate(fx)
                mutated = _evaluate(fx, mutation=mutation)
                if (faithful.expanded, faithful.stop, faithful.outcome) != (
                    mutated.expanded,
                    mutated.stop,
                    mutated.outcome,
                ):
                    caught.append(fx.name)
            with self.subTest(mutation=mutation):
                self.assertTrue(
                    caught, f"mutation {mutation!r} slipped past every fixture"
                )

    def test_faithful_implementation_passes_the_whole_corpus(self) -> None:
        for fx in FIXTURES:
            res = _evaluate(fx)
            self.assertEqual(
                (res.expanded, res.stop, res.outcome),
                (fx.expected_expansion, fx.expected_stop, fx.expected_outcome),
                fx.name,
            )


if __name__ == "__main__":
    unittest.main()
