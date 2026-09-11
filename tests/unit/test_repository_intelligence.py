#!/usr/bin/env python3
"""Behavioral coverage for the repository-intelligence model (Issue #129).

Contract: docs/repository-intelligence/repository-intelligence-model.md.
Regression focus: the entity/relationship model stays closed and typed;
retrieval never exceeds the ring #87 already authorizes; a snapshot
mismatch is a hard reject, never a silent continuation; an
`influential_relationships` entry must already be a resolved edge; an
ambiguous/unsupported/missing-data candidate never becomes a resolved edge,
never becomes influential, and never supports a finding; retrieving a
compatible relationship successfully does not by itself create influence.

Five worked examples mirror "Worked example 1-5" in the design record and
the five corresponding fixtures in
docs/benchmark/corpus/repository-intelligence/.
"""

from __future__ import annotations

import unittest

from tests.reference import repository_intelligence as ri

SNAPSHOT_A = "commit:aaaa000"
SNAPSHOT_B = "commit:bbbb111"


def _entity(kind: ri.EntityKind, name: str, path: str) -> ri.Entity:
    return ri.Entity(kind=kind, qualified_name=name, path=path)


class ChangeRiskRingCeilingTests(unittest.TestCase):
    def test_ring_ceiling_matches_repository_expansion_table(self) -> None:
        self.assertEqual(ri.ring_ceiling_for(ri.ChangeRiskDepth.STANDARD), 1)
        self.assertEqual(ri.ring_ceiling_for(ri.ChangeRiskDepth.ELEVATED), 2)
        self.assertEqual(ri.ring_ceiling_for(ri.ChangeRiskDepth.DEEP), 3)


class EntityRelationshipModelTests(unittest.TestCase):
    def test_relationship_rejects_a_kind_trigger_pairing_outside_the_closed_set(
        self,
    ) -> None:
        source = _entity(ri.EntityKind.FUNCTION, "make_slug", "app/text/slugify.py")
        target = _entity(
            ri.EntityKind.FUNCTION, "normalize_whitespace", "app/text/normalize.py"
        )
        with self.assertRaises(ValueError):
            ri.Relationship(
                kind=ri.RelationshipKind.IMPLEMENTS,
                trigger=ri.Trigger.CALL_SITE,
                source=source,
                target=target,
                ring=1,
                provenance=ri.Provenance(path="app/text/slugify.py", line=4),
            )

    def test_relationship_rejects_a_ring_outside_one_to_three(self) -> None:
        source = _entity(ri.EntityKind.FUNCTION, "a", "a.py")
        target = _entity(ri.EntityKind.FUNCTION, "b", "b.py")
        with self.assertRaises(ValueError):
            ri.Relationship(
                kind=ri.RelationshipKind.CALLS,
                trigger=ri.Trigger.CALL_SITE,
                source=source,
                target=target,
                ring=4,
                provenance=ri.Provenance(path="a.py", line=1),
            )


class SnapshotIdentityTests(unittest.TestCase):
    """The five required states: current, stale, missing data, ambiguous,
    unsupported language."""

    def _index(self, edges=(), unresolved=()) -> ri.SnapshotIndex:
        return ri.SnapshotIndex(
            snapshot_id=SNAPSHOT_A, edges=edges, unresolved=unresolved
        )

    def test_current_matching_snapshot_retrieval_proceeds(self) -> None:
        index = self._index()
        result = ri.retrieve(
            index=index, reviewed_snapshot_id=SNAPSHOT_A, ring_ceiling=1
        )
        self.assertEqual(result.snapshot_id, SNAPSHOT_A)
        self.assertEqual(result.resolved_edges, ())

    def test_stale_mismatched_snapshot_is_rejected_not_silently_continued(
        self,
    ) -> None:
        index = self._index()
        with self.assertRaises(ri.StaleIndexError):
            ri.retrieve(index=index, reviewed_snapshot_id=SNAPSHOT_B, ring_ceiling=1)

    def test_missing_relationship_data_is_a_diagnostic_not_a_resolved_edge(
        self,
    ) -> None:
        missing = ri.UnresolvedCandidate(
            reason=ri.UnresolvedReason.MISSING_DATA, note="no index data for this ring"
        )
        index = self._index(unresolved=(missing,))
        result = ri.retrieve(
            index=index, reviewed_snapshot_id=SNAPSHOT_A, ring_ceiling=1
        )
        self.assertEqual(result.resolved_edges, ())
        self.assertIn(missing, result.unresolved)
        self.assertTrue(ri.is_safe_failure(result))

    def test_ambiguous_resolution_is_a_diagnostic_not_a_resolved_edge(self) -> None:
        ambiguous = ri.UnresolvedCandidate(
            reason=ri.UnresolvedReason.AMBIGUOUS,
            note="string-keyed dynamic dispatch, external request data",
        )
        index = self._index(unresolved=(ambiguous,))
        result = ri.retrieve(
            index=index, reviewed_snapshot_id=SNAPSHOT_A, ring_ceiling=1
        )
        self.assertEqual(result.resolved_edges, ())
        self.assertIn(ambiguous, result.unresolved)
        self.assertEqual(result.influential_relationships, ())

    def test_unsupported_language_is_a_diagnostic_not_a_resolved_edge(self) -> None:
        unsupported = ri.UnresolvedCandidate(
            reason=ri.UnresolvedReason.UNSUPPORTED_LANGUAGE,
            note="no extractor for this language shape",
        )
        index = self._index(unresolved=(unsupported,))
        result = ri.retrieve(
            index=index, reviewed_snapshot_id=SNAPSHOT_A, ring_ceiling=1
        )
        self.assertEqual(result.resolved_edges, ())
        self.assertTrue(ri.is_safe_failure(result))


class RetrievalBoundTests(unittest.TestCase):
    def test_retrieval_never_exceeds_the_ring_ceiling(self) -> None:
        source = _entity(ri.EntityKind.FUNCTION, "caller", "caller.py")
        target = _entity(ri.EntityKind.FUNCTION, "callee", "callee.py")
        ring1_edge = ri.Relationship(
            kind=ri.RelationshipKind.CALLS,
            trigger=ri.Trigger.CALL_SITE,
            source=source,
            target=target,
            ring=1,
            provenance=ri.Provenance(path="caller.py", line=3),
        )
        ring3_edge = ri.Relationship(
            kind=ri.RelationshipKind.CALLS,
            trigger=ri.Trigger.CALL_SITE,
            source=source,
            target=target,
            ring=3,
            provenance=ri.Provenance(path="caller.py", line=9),
        )
        index = ri.SnapshotIndex(
            snapshot_id=SNAPSHOT_A, edges=(ring1_edge, ring3_edge)
        )
        result = ri.retrieve(
            index=index, reviewed_snapshot_id=SNAPSHOT_A, ring_ceiling=1
        )
        self.assertIn(ring1_edge, result.resolved_edges)
        self.assertNotIn(ring3_edge, result.resolved_edges)

    def test_invalid_ring_ceiling_is_rejected(self) -> None:
        index = ri.SnapshotIndex(snapshot_id=SNAPSHOT_A)
        with self.assertRaises(ValueError):
            ri.retrieve(index=index, reviewed_snapshot_id=SNAPSHOT_A, ring_ceiling=0)


class InfluentialRelationshipsTests(unittest.TestCase):
    def test_influential_must_already_be_a_resolved_edge(self) -> None:
        source = _entity(ri.EntityKind.FUNCTION, "caller", "caller.py")
        target = _entity(ri.EntityKind.FUNCTION, "callee", "callee.py")
        edge = ri.Relationship(
            kind=ri.RelationshipKind.CALLS,
            trigger=ri.Trigger.CALL_SITE,
            source=source,
            target=target,
            ring=2,
            provenance=ri.Provenance(path="caller.py", line=3),
        )
        index = ri.SnapshotIndex(snapshot_id=SNAPSHOT_A, edges=(edge,))
        with self.assertRaises(ValueError):
            # ring_ceiling=1 excludes the ring-2 edge from the resolved set,
            # so it cannot legally be named influential.
            ri.retrieve(
                index=index,
                reviewed_snapshot_id=SNAPSHOT_A,
                ring_ceiling=1,
                influential=(edge,),
            )

    def test_retrieved_but_immaterial_edge_is_resolved_but_not_influential(
        self,
    ) -> None:
        source = _entity(ri.EntityKind.FUNCTION, "make_slug", "app/text/slugify.py")
        target = _entity(
            ri.EntityKind.FUNCTION, "normalize_whitespace", "app/text/normalize.py"
        )
        edge = ri.Relationship(
            kind=ri.RelationshipKind.CALLS,
            trigger=ri.Trigger.CALL_SITE,
            source=source,
            target=target,
            ring=1,
            provenance=ri.Provenance(path="app/text/slugify.py", line=4),
        )
        index = ri.SnapshotIndex(snapshot_id=SNAPSHOT_A, edges=(edge,))
        result = ri.retrieve(
            index=index, reviewed_snapshot_id=SNAPSHOT_A, ring_ceiling=1
        )
        self.assertIn(edge, result.resolved_edges)
        self.assertEqual(result.influential_relationships, ())
        self.assertFalse(result.is_influential(edge))


class WorkedExampleTests(unittest.TestCase):
    """Each case mirrors a "Worked example N" block in the design record and
    the matching fixture in
    docs/benchmark/corpus/repository-intelligence/."""

    def test_example_1_call_site_caller_null_deref(self) -> None:
        get_user = _entity(ri.EntityKind.FUNCTION, "get_user", "app/users/lookup.py")
        charge_user = _entity(
            ri.EntityKind.FUNCTION, "charge_user", "app/billing/charge.py"
        )
        edge = ri.Relationship(
            kind=ri.RelationshipKind.CALLS,
            trigger=ri.Trigger.CALL_SITE,
            source=charge_user,
            target=get_user,
            ring=1,
            provenance=ri.Provenance(path="app/billing/charge.py", line=7),
        )
        index = ri.SnapshotIndex(snapshot_id=SNAPSHOT_A, edges=(edge,))
        result = ri.retrieve(
            index=index,
            reviewed_snapshot_id=SNAPSHOT_A,
            ring_ceiling=ri.ring_ceiling_for(ri.ChangeRiskDepth.STANDARD),
            influential=(edge,),
        )
        self.assertEqual(result.resolved_edges, (edge,))
        self.assertEqual(result.influential_relationships, (edge,))
        self.assertEqual(edge.provenance.location(), "app/billing/charge.py:7")

    def test_example_2_interface_contract_sibling_implementer(self) -> None:
        cache = _entity(ri.EntityKind.CLASS, "Cache", "src/cache/Cache.ts")
        in_memory = _entity(
            ri.EntityKind.CLASS, "InMemoryCache", "src/cache/InMemoryCache.ts"
        )
        edge = ri.Relationship(
            kind=ri.RelationshipKind.IMPLEMENTS,
            trigger=ri.Trigger.INTERFACE_CONTRACT,
            source=in_memory,
            target=cache,
            ring=2,
            provenance=ri.Provenance(path="src/cache/InMemoryCache.ts", line=3),
        )
        index = ri.SnapshotIndex(snapshot_id=SNAPSHOT_A, edges=(edge,))
        result = ri.retrieve(
            index=index,
            reviewed_snapshot_id=SNAPSHOT_A,
            ring_ceiling=ri.ring_ceiling_for(ri.ChangeRiskDepth.ELEVATED),
            influential=(edge,),
        )
        self.assertEqual(result.resolved_edges, (edge,))
        self.assertEqual(result.influential_relationships, (edge,))

    def test_example_3_config_consumer_stale_import(self) -> None:
        config_key = _entity(ri.EntityKind.SYMBOL, "MAX_UPLOAD_MB", "app/settings.py")
        uploads = _entity(ri.EntityKind.MODULE, "app.uploads", "app/uploads.py")
        edge = ri.Relationship(
            kind=ri.RelationshipKind.REFERENCES,
            trigger=ri.Trigger.CONFIG_CONSUMER,
            source=uploads,
            target=config_key,
            ring=1,
            provenance=ri.Provenance(path="app/uploads.py", line=1),
        )
        index = ri.SnapshotIndex(snapshot_id=SNAPSHOT_A, edges=(edge,))
        result = ri.retrieve(
            index=index,
            reviewed_snapshot_id=SNAPSHOT_A,
            ring_ceiling=ri.ring_ceiling_for(ri.ChangeRiskDepth.STANDARD),
            influential=(edge,),
        )
        self.assertEqual(result.influential_relationships, (edge,))

    def test_example_4_dynamic_dispatch_is_safe_failure(self) -> None:
        ambiguous = ri.UnresolvedCandidate(
            reason=ri.UnresolvedReason.AMBIGUOUS,
            note="HANDLERS[kind] keyed by external request data",
        )
        index = ri.SnapshotIndex(snapshot_id=SNAPSHOT_A, unresolved=(ambiguous,))
        result = ri.retrieve(
            index=index,
            reviewed_snapshot_id=SNAPSHOT_A,
            ring_ceiling=ri.ring_ceiling_for(ri.ChangeRiskDepth.STANDARD),
        )
        self.assertEqual(result.resolved_edges, ())
        self.assertEqual(result.influential_relationships, ())
        self.assertTrue(ri.is_safe_failure(result))

    def test_example_5_control_compatible_caller_no_influence(self) -> None:
        make_slug = _entity(ri.EntityKind.FUNCTION, "make_slug", "app/text/slugify.py")
        normalize = _entity(
            ri.EntityKind.FUNCTION, "normalize_whitespace", "app/text/normalize.py"
        )
        edge = ri.Relationship(
            kind=ri.RelationshipKind.CALLS,
            trigger=ri.Trigger.CALL_SITE,
            source=make_slug,
            target=normalize,
            ring=1,
            provenance=ri.Provenance(path="app/text/slugify.py", line=4),
        )
        index = ri.SnapshotIndex(snapshot_id=SNAPSHOT_A, edges=(edge,))
        result = ri.retrieve(
            index=index,
            reviewed_snapshot_id=SNAPSHOT_A,
            ring_ceiling=ri.ring_ceiling_for(ri.ChangeRiskDepth.STANDARD),
            # Retrieved successfully, with provenance -- but deliberately
            # not passed as influential: the relationship is compatible.
        )
        self.assertEqual(result.resolved_edges, (edge,))
        self.assertEqual(result.influential_relationships, ())
        self.assertFalse(ri.is_safe_failure(result))


class GovernanceTests(unittest.TestCase):
    def test_no_public_callable_carries_a_prohibited_capability_fragment(self) -> None:
        for name in ri.public_callables():
            for fragment in ri.PROHIBITED_CAPABILITY_NAME_FRAGMENTS:
                self.assertNotIn(fragment, name, (name, fragment))

    def test_persistence_and_cross_repo_fragments_are_prohibited(self) -> None:
        for fragment in ("persist", "graph_db", "cross_repo", "invent_relationship"):
            self.assertIn(fragment, ri.PROHIBITED_CAPABILITY_NAME_FRAGMENTS)


if __name__ == "__main__":
    unittest.main()
