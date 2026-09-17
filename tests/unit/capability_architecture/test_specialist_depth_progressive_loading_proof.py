"""Unit coverage for the specialist-depth progressive-loading proof
measurement (#411).

Structural invariants only, not pinned word counts or live run results,
mirroring `test_capability_loading_baseline.py`'s own discipline: static
surface totals move with ordinary policy edits, and a live behavioral run
needs a real reviewer runtime this suite must not depend on.
"""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from scripts.capability_architecture import (
    specialist_depth_progressive_loading_proof as proof,
)
from scripts.capability_architecture import capability_loading_baseline as clb


class StaticSurfaceReductionTests(unittest.TestCase):
    def test_every_adapter_is_present_and_internally_consistent(self) -> None:
        reduction = proof.measure_static_surface_reduction()

        self.assertEqual(set(reduction), set(clb.ADAPTER_SECTIONS))
        for adapter, section in reduction.items():
            with self.subTest(adapter=adapter):
                self.assertEqual(
                    section["total_words_when_not_needed"],
                    section["total_words_with_specialist_depth"]
                    - section["specialist_depth_words"],
                )
                self.assertGreater(section["specialist_depth_words"], 0)
                self.assertLess(
                    section["total_words_when_not_needed"],
                    section["total_words_with_specialist_depth"],
                )

    def test_reduction_pct_matches_specialist_depth_share(self) -> None:
        reduction = proof.measure_static_surface_reduction()
        for section in reduction.values():
            expected_pct = round(
                100
                * section["specialist_depth_words"]
                / section["total_words_with_specialist_depth"],
                2,
            )
            self.assertEqual(section["reduction_pct"], expected_pct)


class RequiredCaseIdentityTests(unittest.TestCase):
    """The three required activation cases must resolve to real fixtures
    under their reused/owning corpus directories -- a stale id here would
    silently drop a required case from the proof rather than erroring."""

    def _case_ids(self, corpus_dir) -> set[str]:
        import yaml

        from tests.reference.benchmark import benchmark_fixture as bf

        return {
            bf.parse_case(yaml.safe_load(p.read_text(encoding="utf-8"))).id
            for p in sorted(corpus_dir.glob("*.yaml"))
        }

    def test_case_not_needed_exists_in_composition_corpus(self) -> None:
        self.assertIn(
            proof.CASE_NOT_NEEDED, self._case_ids(proof.COMPOSITION_CORPUS_DIR)
        )

    def test_case_must_activate_exists_in_composition_corpus(self) -> None:
        self.assertIn(
            proof.CASE_MUST_ACTIVATE, self._case_ids(proof.COMPOSITION_CORPUS_DIR)
        )

    def test_case_ambiguous_exists_in_proof_corpus(self) -> None:
        self.assertIn(proof.CASE_AMBIGUOUS, self._case_ids(proof.PROOF_CORPUS_DIR))


class MainExitCodeTests(unittest.TestCase):
    def test_behavioral_mode_exits_non_zero_when_the_run_never_executed(self) -> None:
        with mock.patch.object(
            proof,
            "measure_behavioral_proof",
            side_effect=RuntimeError("claude CLI not found"),
        ):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                exit_code = proof.main(["behavioral"])

        self.assertEqual(exit_code, 1)

    def test_static_mode_still_exits_zero_on_success(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            exit_code = proof.main(["static"])

        self.assertEqual(exit_code, 0)

    def test_behavioral_mode_exits_non_zero_on_a_regression_miss(self) -> None:
        fake_result = {
            "regression_vs_408_baseline": {
                "aggregate": {
                    "total_false_negatives": 1,
                    "total_false_positives": 0,
                }
            },
            "activation_required_cases": {
                "aggregate": {
                    "total_false_negatives": 0,
                    "total_false_positives": 0,
                }
            },
        }
        with mock.patch.object(
            proof, "measure_behavioral_proof", return_value=fake_result
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = proof.main(["behavioral"])

        self.assertEqual(exit_code, 1)

    def test_behavioral_mode_exits_zero_when_everything_matches(self) -> None:
        fake_result = {
            "regression_vs_408_baseline": {
                "aggregate": {
                    "total_false_negatives": 0,
                    "total_false_positives": 0,
                }
            },
            "activation_required_cases": {
                "aggregate": {
                    "total_false_negatives": 0,
                    "total_false_positives": 0,
                }
            },
        }
        with mock.patch.object(
            proof, "measure_behavioral_proof", return_value=fake_result
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = proof.main(["behavioral"])

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
