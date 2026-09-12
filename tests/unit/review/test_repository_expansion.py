"""Behavioral fixtures for repository expansion (Issue #87)."""

from __future__ import annotations

import unittest

from tests.reference.review import repository_expansion as rex
from tests.reference.review.change_risk_signals import Depth
from tests.reference.review.repository_expansion import FiredTrigger, Ring


def trigger(name: str, ring: Ring, *locations: str) -> FiredTrigger:
    return FiredTrigger(
        trigger=name,
        source=f"{name} source",
        resolved_at_ring=ring,
        locations=locations or (f"{name}.py:1",),
    )


class CatalogAndCeilingTests(unittest.TestCase):
    def test_every_catalog_trigger_is_known(self) -> None:
        for name in (
            "call_site",
            "interface_contract",
            "migration_schema",
            "config_consumer",
        ):
            self.assertIn(name, rex.CATALOG_TRIGGERS)

    def test_unknown_trigger_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            rex.resolve([trigger("not_a_real_trigger", Ring.RING_1)], Depth.DEEP)

    def test_max_ring_scales_with_depth(self) -> None:
        self.assertEqual(rex.max_ring_for_depth(Depth.STANDARD), Ring.RING_1)
        self.assertEqual(rex.max_ring_for_depth(Depth.ELEVATED), Ring.RING_2)
        self.assertEqual(rex.max_ring_for_depth(Depth.DEEP), Ring.RING_3)


class NoTriggerFiredTests(unittest.TestCase):
    def test_no_candidates_is_reported_as_none(self) -> None:
        result = rex.resolve([], Depth.DEEP)
        self.assertEqual(result.fired, ())
        self.assertEqual(rex.rationale_lines(result), ["Repository expansion: none"])


class CeilingIsACapNotATargetTests(unittest.TestCase):
    def test_standard_depth_caps_expansion_at_ring_1(self) -> None:
        candidate = trigger("call_site", Ring.RING_3)
        result = rex.resolve([candidate], Depth.STANDARD)
        self.assertEqual(result.fired[0].resolved_at_ring, Ring.RING_1)

    def test_elevated_depth_caps_expansion_at_ring_2(self) -> None:
        candidate = trigger("interface_contract", Ring.RING_3)
        result = rex.resolve([candidate], Depth.ELEVATED)
        self.assertEqual(result.fired[0].resolved_at_ring, Ring.RING_2)

    def test_deep_depth_permits_ring_3(self) -> None:
        candidate = trigger("migration_schema", Ring.RING_3)
        result = rex.resolve([candidate], Depth.DEEP)
        self.assertEqual(result.fired[0].resolved_at_ring, Ring.RING_3)

    def test_ceiling_never_expands_a_trigger_resolved_earlier(self) -> None:
        # A trigger resolved at ring 1 stays at ring 1 even though `deep`
        # would permit ring 3 — the ceiling is a cap, never a forced target.
        candidate = trigger("config_consumer", Ring.RING_1)
        result = rex.resolve([candidate], Depth.DEEP)
        self.assertEqual(result.fired[0].resolved_at_ring, Ring.RING_1)


class MultipleTriggersAndRationaleTests(unittest.TestCase):
    def test_multiple_fired_triggers_are_each_reported(self) -> None:
        candidates = [
            trigger("call_site", Ring.RING_1, "a.py:10"),
            trigger("migration_schema", Ring.RING_2, "b.sql:1"),
        ]
        result = rex.resolve(candidates, Depth.DEEP)
        self.assertEqual(len(result.fired), 2)
        lines = rex.rationale_lines(result)
        self.assertEqual(len(lines), 2)
        self.assertIn("call_site (ring 1) — a.py:10", lines[0])
        self.assertIn("migration_schema (ring 2) — b.sql:1", lines[1])

    def test_machine_model_shape(self) -> None:
        candidate = trigger("call_site", Ring.RING_1, "a.py:10")
        result = rex.resolve([candidate], Depth.STANDARD)
        model = result.to_machine_model()
        self.assertEqual(
            model["repository_expansion"]["triggers"][0]["trigger"], "call_site"
        )
        self.assertEqual(
            model["repository_expansion"]["triggers"][0]["ring_reached"], 1
        )


if __name__ == "__main__":
    unittest.main()
