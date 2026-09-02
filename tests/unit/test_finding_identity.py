#!/usr/bin/env python3
"""Behavioral coverage for stable finding identity (Issue #60).

Contract: docs/finding-stable-identity.md. Focus: deterministic descriptor
construction; the minted identity survives the #59 must-survive scenarios
(line movement, reformatting, reviewer wording) and changes for the
must-change scenarios (distinct defect, different site intent); the
#59 -> #60 hand-off propagates on MATCH and mints fresh on NO MATCH /
AMBIGUOUS; ABSENT and UNCLASSIFIABLE stay distinct and non-wildcard;
fail-closed on a source-less finding. Broad fixtures are #61's.
"""

from __future__ import annotations

import unittest

from tests.reference import finding_identity as fi


def _descriptor(**overrides):
    base = dict(
        repository="github.com/acme/widgets",
        location="src/pay/retry.py:88",
        behavioral_claim_text="the row is re-enqueued before the commit so a retry processes the payment twice",
        anchor_fragment="queue.put(job)",
        mechanism_fragment="queue.put(job)",
        defect_kind_text="lost update",
        symbol="pay.retry.RetryHandler.run",
        construct="call",
        sibling_source="row.status = 'pending'\nqueue.put(job)\nlog.info('queued')",
        predecessor_source="row.status = 'pending'",
        successor_source="log.info('queued')",
    )
    base.update(overrides)
    return fi.build_descriptor(**base)


class DescriptorConstructionTests(unittest.TestCase):
    def test_build_is_deterministic_and_kwarg_order_independent(self) -> None:
        a = fi.build_descriptor(
            repository="r", location="a/b.py:1", anchor_fragment="x = 1",
            mechanism_fragment="x = 1", defect_kind_text="k",
        )
        b = fi.build_descriptor(
            defect_kind_text="k", mechanism_fragment="x = 1",
            anchor_fragment="x = 1", location="a/b.py:1", repository="r",
        )
        self.assertEqual(a, b)
        self.assertEqual(fi.mint_identity(a), fi.mint_identity(b))

    def test_minted_identity_shape(self) -> None:
        value = fi.mint_identity(_descriptor())
        self.assertTrue(value.startswith("fid_v1_"))
        self.assertEqual(len(value), len("fid_v1_") + 32)
        self.assertEqual(value, value.lower())

    def test_volatile_signals_are_ignored(self) -> None:
        plain = _descriptor()
        noisy = _descriptor(
            severity="P0", display_id="F7", head_sha="deadbeef",
            pr_number=42, discovery_order=3, worker_index=1,
            repository_state_annotation="staged",
        )
        self.assertEqual(fi.mint_identity(plain), fi.mint_identity(noisy))

    def test_path_is_stripped_of_line_suffix_and_normalized(self) -> None:
        d = fi.build_descriptor(
            repository="r", location="./src\\pay\\retry.py:88-90",
            anchor_fragment="a", mechanism_fragment="a",
        )
        self.assertEqual(d.path, "src/pay/retry.py")

    def test_repository_intent_has_no_path(self) -> None:
        d = _descriptor(location="repository", path=None)
        self.assertEqual(d.location_intent, "repository")
        self.assertIs(d.path, fi.ABSENT)


class MustSurviveTests(unittest.TestCase):
    """finding-identity-requirements.md §2 — identity stays stable."""

    def test_reformatting_only_change(self) -> None:
        original = _descriptor(anchor_fragment="queue.put(job)")
        reformatted = _descriptor(
            anchor_fragment="queue . put(  job ,  )   // re-enqueue\n",
        )
        self.assertEqual(original.anchor_tokens, reformatted.anchor_tokens)
        self.assertEqual(fi.mint_identity(original), fi.mint_identity(reformatted))

    def test_line_movement_and_nearby_edits(self) -> None:
        # Different line number, different surrounding context -> same identity
        # (context_tokens / neighboring_syntax are excluded from the digest).
        here = _descriptor(location="src/pay/retry.py:88")
        moved = _descriptor(
            location="src/pay/retry.py:141",
            sibling_source="audit.record(row)\nqueue.put(job)\nmetrics.bump()",
            predecessor_source="audit.record(row)",
            successor_source="metrics.bump()",
        )
        self.assertNotEqual(here.context_tokens, moved.context_tokens)
        self.assertEqual(fi.mint_identity(here), fi.mint_identity(moved))

    def test_reviewer_wording_change_keeps_identity(self) -> None:
        # Same extracted cause/behavior/mechanism/anchor, different free prose.
        a = _descriptor(
            behavioral_claim_text="the row is re-enqueued before the commit so a retry processes the payment twice",
        )
        b = _descriptor(
            behavioral_claim_text="the row is re-enqueued before the commit so the delivery is processed again on retry",
        )
        self.assertNotEqual(a.behavioral_claim, b.behavioral_claim)
        self.assertNotEqual(a.behavior_key, b.behavior_key)  # prose feeds only matching evidence
        self.assertEqual(fi.mint_identity(a), fi.mint_identity(b))

    def test_severity_reclassification_keeps_identity(self) -> None:
        self.assertEqual(
            fi.mint_identity(_descriptor(severity="P2")),
            fi.mint_identity(_descriptor(severity="P1")),
        )

    def test_parser_refinement_does_not_change_identity(self) -> None:
        without = _descriptor(diagnostic_symbol=None, diagnostic_construct=None)
        with_parser = _descriptor(
            diagnostic_symbol="pay.retry.RetryHandler.run#L88",
            diagnostic_construct="await_call",
        )
        self.assertEqual(fi.mint_identity(without), fi.mint_identity(with_parser))


class MustChangeTests(unittest.TestCase):
    """finding-identity-requirements.md §3 — a new identity is required."""

    def test_distinct_defect_same_location(self) -> None:
        base = _descriptor()
        other = _descriptor(
            behavioral_claim_text="the amount is read as a float so rounding drifts on large sums",
            mechanism_fragment="total = float(amount)",
            anchor_fragment="total = float(amount)",
            defect_kind_text="precision loss",
        )
        self.assertNotEqual(fi.mint_identity(base), fi.mint_identity(other))

    def test_similar_wording_different_underlying_problem(self) -> None:
        a = _descriptor(
            behavioral_claim_text="the guard is missing so the request is not validated",
            anchor_fragment="handler.dispatch(req)", mechanism_fragment="handler.dispatch(req)",
        )
        b = _descriptor(
            behavioral_claim_text="the guard is missing so the request is not validated",
            anchor_fragment="worker.enqueue(req)", mechanism_fragment="worker.enqueue(req)",
        )
        self.assertNotEqual(fi.mint_identity(a), fi.mint_identity(b))

    def test_same_pattern_different_symbol_is_a_different_minted_identity(self) -> None:
        a = _descriptor(symbol="pay.retry.RetryHandler.run")
        b = _descriptor(symbol="pay.refund.RefundHandler.run")
        self.assertNotEqual(fi.mint_identity(a), fi.mint_identity(b))

    def test_different_location_intent_is_a_different_identity(self) -> None:
        line = _descriptor(location="src/pay/retry.py:88")
        file_level = _descriptor(location="file", path="src/pay/retry.py")
        self.assertNotEqual(fi.mint_identity(line), fi.mint_identity(file_level))

    def test_anchor_token_order_is_significant(self) -> None:
        a = _descriptor(anchor_fragment="a and not b")
        b = _descriptor(anchor_fragment="b and not a")
        self.assertNotEqual(a.anchor_tokens, b.anchor_tokens)
        self.assertNotEqual(fi.mint_identity(a), fi.mint_identity(b))


class HandoffTests(unittest.TestCase):
    """docs/finding-stable-identity.md §6.4 — identity vs. matching."""

    def test_match_propagates_prior_identity(self) -> None:
        current = _descriptor(symbol="pay.retry.RetryHandler.retry")  # moved/renamed
        prior_identity = "fid_v1_" + "0" * 32
        self.assertEqual(
            fi.effective_identity(current, matched_prior_identity=prior_identity),
            prior_identity,
        )

    def test_no_match_and_ambiguous_mint_fresh(self) -> None:
        current = _descriptor()
        minted = fi.mint_identity(current)
        # NO MATCH / AMBIGUOUS both arrive as matched_prior_identity=None.
        self.assertEqual(fi.effective_identity(current), minted)
        self.assertEqual(
            fi.effective_identity(current, matched_prior_identity=None), minted
        )

    def test_ambiguous_never_inherits_a_candidate(self) -> None:
        current = _descriptor()
        candidate = "fid_v1_" + "a" * 32
        # The contract models AMBIGUOUS as None; a fresh mint must result.
        self.assertNotEqual(fi.effective_identity(current), candidate)


class SentinelTests(unittest.TestCase):
    """docs/finding-stable-identity.md §4 — absent vs. unclassifiable."""

    def test_absent_and_unclassifiable_are_distinct(self) -> None:
        self.assertIsNot(fi.ABSENT, fi.UNCLASSIFIABLE)
        self.assertNotEqual(fi.ABSENT, fi.UNCLASSIFIABLE)

    def test_missing_symbol_is_absent_not_guessed(self) -> None:
        d = fi.build_descriptor(
            repository="r", location="a/b.py:1", anchor_fragment="x=1",
            mechanism_fragment="x=1", symbol=None,
        )
        self.assertIs(d.symbol, fi.ABSENT)

    def test_unseparable_claim_yields_unclassifiable_keys(self) -> None:
        d = _descriptor(behavioral_claim_text="payment processed twice on retry")
        self.assertIs(d.cause_key, fi.UNCLASSIFIABLE)
        self.assertIs(d.behavior_key, fi.UNCLASSIFIABLE)

    def test_absent_symbol_still_discriminates_by_other_fields(self) -> None:
        a = fi.build_descriptor(
            repository="r", location="a/b.py:1", anchor_fragment="x = 1",
            mechanism_fragment="x = 1", symbol=None,
        )
        b = fi.build_descriptor(
            repository="r", location="a/b.py:1", anchor_fragment="y = 2",
            mechanism_fragment="y = 2", symbol=None,
        )
        self.assertNotEqual(fi.mint_identity(a), fi.mint_identity(b))

    def test_sentinels_serialize_to_distinct_markers(self) -> None:
        self.assertNotEqual(fi._encode(fi.ABSENT), fi._encode(fi.UNCLASSIFIABLE))


class FailClosedTests(unittest.TestCase):
    """docs/finding-stable-identity.md §7."""

    def test_source_less_finding_is_not_matchable_but_still_minted(self) -> None:
        d = fi.build_descriptor(
            repository="r", location="repository",
            behavioral_claim_text="architecture is unclear", anchor_fragment=None,
            mechanism_fragment=None,
        )
        self.assertFalse(fi.is_matchable(d))
        self.assertTrue(fi.mint_identity(d).startswith("fid_v1_"))

    def test_unresolvable_repository_is_not_matchable(self) -> None:
        self.assertFalse(fi.is_matchable(_descriptor(repository="")))

    def test_unclassifiable_location_is_not_matchable(self) -> None:
        d = _descriptor(location="somewhere in the payments area")
        self.assertIs(d.location_intent, fi.UNCLASSIFIABLE)
        self.assertFalse(fi.is_matchable(d))

    def test_source_backed_finding_is_matchable(self) -> None:
        self.assertTrue(fi.is_matchable(_descriptor()))


class OfflineDeterminismTests(unittest.TestCase):
    def test_identity_is_reproducible_across_fresh_descriptor_instances(self) -> None:
        values = {fi.mint_identity(_descriptor()) for _ in range(25)}
        self.assertEqual(len(values), 1)

    def test_serialization_is_pure_text_over_the_discriminating_subset(self) -> None:
        blob = fi.canonical_serialization(_descriptor())
        self.assertTrue(blob.startswith("v1\x1e"))
        for name in fi.DISCRIMINATING_FIELDS:
            self.assertIn(name, blob)
        self.assertNotIn("context_tokens", blob)
        self.assertNotIn("neighboring_syntax", blob)


if __name__ == "__main__":
    unittest.main()
