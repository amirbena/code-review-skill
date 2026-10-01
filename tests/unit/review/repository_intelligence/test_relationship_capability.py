#!/usr/bin/env python3
"""Behavioral coverage for the relationship capability contract (Issue #603).

Contract: docs/repository-intelligence/relationship-capability-contract.md.
Regression focus: a stale answer is rejected whole, never partially used; a
host answer is a claim whose `path:line` must verify; absence is accepted only
when attested complete; an absent capability falls back to repository search
for every question; an ambiguous candidate is never an edge; an analogue
answer is advisory and never a Context gap. Worked examples 1-7 mirror the
design record.
"""

from __future__ import annotations

import unittest

from tests.reference.review import relationship_capability as rc
from tests.reference.review import repository_intelligence as ri

SNAP = "commit:aaaa000"
OTHER = "commit:bbbb111"


def _fn(name: str, path: str) -> ri.Entity:
    return ri.Entity(ri.EntityKind.FUNCTION, name, path)


def _edge(
    kind: ri.RelationshipKind,
    trigger: ri.Trigger | None,
    ring: int | None,
    path: str = "app/billing/charge.py",
    line: int = 12,
) -> ri.Relationship:
    return ri.Relationship(
        kind=kind,
        trigger=trigger,
        source=_fn("src", path),
        target=_fn("dst", "app/users/lookup.py"),
        ring=ring,
        provenance=ri.Provenance(path=path, line=line),
    )


CALL = _edge(ri.RelationshipKind.CALLS, ri.Trigger.CALL_SITE, 1)
TEST_EDGE = _edge(
    ri.RelationshipKind.TESTED_BY, None, None, path="tests/test_totals.py", line=30
)
ANALOGUE = _edge(
    ri.RelationshipKind.ANALOGUE_OF, None, None, path="app/export/csv.py", line=8
)


def _ok(_: ri.Provenance) -> bool:
    return True


def _consume(answer, question=rc.Question.CONSUMERS_OF, ring=1, verify=_ok):
    return rc.consume(
        answer,
        question=question,
        subject="get_user",
        reviewed_snapshot_id=SNAP,
        ring_ceiling=ring,
        verify=verify,
    )


def _answer(question=rc.Question.CONSUMERS_OF, **kw):
    kw.setdefault("snapshot_id", SNAP)
    return rc.CapabilityAnswer(question=question, subject="get_user", **kw)


class ModelExtensionTests(unittest.TestCase):
    def test_extension_kinds_have_no_trigger_and_no_ring(self) -> None:
        self.assertIsNone(TEST_EDGE.ring)
        with self.assertRaises(ValueError):
            _edge(ri.RelationshipKind.TESTED_BY, None, 1, path="t.py")

    def test_extension_kinds_cannot_take_an_expansion_trigger(self) -> None:
        with self.assertRaises(ValueError):
            _edge(ri.RelationshipKind.TESTED_BY, ri.Trigger.CALL_SITE, 1)

    def test_every_question_has_a_fallback_and_a_kind_set(self) -> None:
        for q in rc.Question:
            self.assertIn(q, rc.FALLBACK_PROCEDURE)
            self.assertTrue(rc.QUESTION_KINDS[q])

    def test_retrieve_keeps_ringless_edges_under_any_ceiling(self) -> None:
        index = ri.SnapshotIndex(snapshot_id=SNAP, edges=(TEST_EDGE, CALL))
        result = ri.retrieve(index=index, reviewed_snapshot_id=SNAP, ring_ceiling=1)
        self.assertIn(TEST_EDGE, result.resolved_edges)


class ConsumptionTests(unittest.TestCase):
    def test_1_verified_edge_is_resolved_relevant(self) -> None:
        got = _consume(_answer(edges=(CALL,), complete=True))
        self.assertIs(got.outcome, rc.Outcome.RESOLVED_RELEVANT)
        self.assertEqual(got.used_edges, (CALL,))
        self.assertFalse(got.fallback_required)
        self.assertFalse(got.has_context_gap())

    def test_2_attested_empty_answer_is_resolved_none(self) -> None:
        got = _consume(
            _answer(rc.Question.TESTS_EXERCISING, complete=True),
            question=rc.Question.TESTS_EXERCISING,
            ring=None,
        )
        self.assertIs(got.outcome, rc.Outcome.RESOLVED_NONE)
        self.assertFalse(got.has_context_gap())

    def test_empty_answer_without_attestation_is_unresolved_not_none(self) -> None:
        got = _consume(_answer())
        self.assertIs(got.outcome, rc.Outcome.UNRESOLVED)
        self.assertTrue(got.fallback_required)
        self.assertTrue(got.has_context_gap())
        self.assertEqual(got.unresolved, (rc.UnresolvedReason.INCOMPLETE_SEARCH,))

    def test_3_stale_answer_is_rejected_whole(self) -> None:
        got = _consume(_answer(snapshot_id=OTHER, edges=(CALL,), complete=True))
        self.assertEqual(got.used_edges, ())
        self.assertIsNone(got.outcome)
        self.assertTrue(got.fallback_required)
        self.assertEqual(got.unresolved, (rc.UnresolvedReason.STALE_SNAPSHOT,))
        self.assertFalse(got.has_context_gap(rc.Outcome.RESOLVED_RELEVANT))
        self.assertTrue(got.has_context_gap(None))

    def test_4_absent_capability_falls_back_for_every_question(self) -> None:
        for q in rc.Question:
            with self.subTest(question=q):
                got = _consume(None, question=q)
                self.assertTrue(got.fallback_required)
                self.assertIsNone(got.outcome)
                self.assertEqual(got.unresolved, (rc.UnresolvedReason.CAPABILITY_ABSENT,))
                self.assertFalse(got.has_context_gap(rc.Outcome.RESOLVED_NONE))
                if rc.QUESTION_CLASS[q] is not None:
                    self.assertTrue(got.has_context_gap(None))

    def test_5_ambiguous_candidate_is_unresolved_never_an_edge(self) -> None:
        got = _consume(_answer(candidates=(rc.AmbiguousCandidate(),), complete=True))
        self.assertIs(got.outcome, rc.Outcome.UNRESOLVED)
        self.assertEqual(got.used_edges, ())
        self.assertTrue(got.has_context_gap())

    def test_ambiguity_beside_an_edge_keeps_the_gap_visible(self) -> None:
        got = _consume(_answer(edges=(CALL,), candidates=(rc.AmbiguousCandidate(),)))
        self.assertIs(got.outcome, rc.Outcome.RESOLVED_RELEVANT)
        self.assertEqual(got.used_edges, (CALL,))
        self.assertTrue(got.has_context_gap())

    def test_6_unverifiable_edge_is_dropped_and_not_trusted(self) -> None:
        got = _consume(_answer(edges=(CALL,), complete=True), verify=lambda _: False)
        self.assertEqual(got.used_edges, ())
        self.assertIs(got.outcome, rc.Outcome.UNRESOLVED)
        self.assertEqual(got.unresolved, (rc.UnresolvedReason.UNVERIFIABLE_PROVENANCE,))
        self.assertTrue(got.fallback_required)

    def test_dropped_edge_never_reads_as_resolved_none(self) -> None:
        bad = _edge(ri.RelationshipKind.CALLS, ri.Trigger.CALL_SITE, 1, path="../x.py")
        got = _consume(_answer(edges=(bad,), complete=True))
        self.assertIsNot(got.outcome, rc.Outcome.RESOLVED_NONE)

    def test_paths_outside_the_repository_are_dropped(self) -> None:
        for path in ("/etc/passwd", "../other/x.py", "C:/x.py", ""):
            with self.subTest(path=path):
                edge = _edge(ri.RelationshipKind.CALLS, ri.Trigger.CALL_SITE, 1, path=path)
                got = _consume(_answer(edges=(edge,), complete=True))
                self.assertEqual(got.used_edges, ())

    def test_edge_beyond_the_ring_ceiling_is_dropped(self) -> None:
        deep = _edge(ri.RelationshipKind.CALLS, ri.Trigger.CALL_SITE, 3)
        got = _consume(_answer(edges=(deep,), complete=True), ring=1)
        self.assertEqual(got.used_edges, ())
        self.assertIs(got.outcome, rc.Outcome.UNRESOLVED)

    def test_ring_bearing_question_requires_a_ring_ceiling(self) -> None:
        for q in (rc.Question.CONSUMERS_OF, rc.Question.IMPLEMENTERS_OF):
            with self.subTest(question=q):
                with self.assertRaises(ValueError):
                    _consume(_answer(q, edges=(CALL,)), question=q, ring=None)
                with self.assertRaises(ValueError):
                    _consume(None, question=q, ring=None)

    def test_edge_kind_outside_the_question_is_dropped(self) -> None:
        got = _consume(_answer(edges=(TEST_EDGE,), complete=True))
        self.assertEqual(got.used_edges, ())

    def test_answer_to_another_question_or_subject_is_rejected(self) -> None:
        got = _consume(_answer(rc.Question.IMPLEMENTERS_OF, edges=(CALL,)))
        self.assertTrue(got.fallback_required)
        self.assertEqual(got.used_edges, ())
        self.assertEqual(got.unresolved, (rc.UnresolvedReason.MISMATCHED_ANSWER,))
        other = rc.CapabilityAnswer(
            question=rc.Question.CONSUMERS_OF, subject="other", snapshot_id=SNAP, edges=(CALL,)
        )
        self.assertEqual(_consume(other).used_edges, ())

    def test_oversize_answer_cannot_claim_completeness(self) -> None:
        many = tuple(
            _edge(ri.RelationshipKind.CALLS, ri.Trigger.CALL_SITE, 1, line=n + 1)
            for n in range(rc.MAX_EDGES_PER_ANSWER + 1)
        )
        got = _consume(_answer(edges=many, complete=True))
        self.assertEqual(got.used_edges, ())
        self.assertTrue(got.fallback_required)

    def test_7_analogue_answer_is_advisory_with_no_gap_and_no_outcome(self) -> None:
        q = rc.Question.ANALOGUES_OF
        got = _consume(_answer(q, edges=(ANALOGUE,)), question=q, ring=None)
        self.assertEqual(got.used_edges, (ANALOGUE,))
        absent = _consume(None, question=q, ring=None)
        self.assertFalse(absent.has_context_gap())
        self.assertIsNone(rc.finalize(absent, None))
        ambiguous = _consume(
            _answer(q, edges=(ANALOGUE,), candidates=(rc.AmbiguousCandidate(),)),
            question=q,
            ring=None,
        )
        self.assertFalse(ambiguous.has_context_gap())


class FinalizeTests(unittest.TestCase):
    def test_capability_decision_stands_when_no_fallback_needed(self) -> None:
        got = _consume(_answer(edges=(CALL,)))
        self.assertIs(rc.finalize(got, None), rc.Outcome.RESOLVED_RELEVANT)

    def test_fallback_outcome_applies_when_capability_absent(self) -> None:
        got = _consume(None)
        self.assertIs(rc.finalize(got, rc.Outcome.RESOLVED_NONE), rc.Outcome.RESOLVED_NONE)

    def test_fallback_that_cannot_answer_leaves_the_question_unresolved(self) -> None:
        self.assertIs(rc.finalize(_consume(None), None), rc.Outcome.UNRESOLVED)

    def test_stale_capability_never_yields_resolved_none(self) -> None:
        got = _consume(_answer(snapshot_id=OTHER, complete=True))
        self.assertIs(rc.finalize(got, None), rc.Outcome.UNRESOLVED)


class DeclarationAndGovernanceTests(unittest.TestCase):
    def test_no_public_callable_carries_a_prohibited_capability_fragment(self) -> None:
        for name in rc.public_callables():
            for fragment in rc.PROHIBITED_CAPABILITY_NAME_FRAGMENTS:
                self.assertNotIn(fragment, name)

    def test_declaration_forbids_being_required_and_mutating(self) -> None:
        never = " ".join(rc.DECLARATION["never"])
        self.assertIn("required", never)
        self.assertIn("mutate", never)
        self.assertIn("another repository", never)


if __name__ == "__main__":
    unittest.main()
