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

    @staticmethod
    def _fake_result(
        *,
        regression_fn: int = 0,
        regression_fp: int = 0,
        not_needed_fn: int = 0,
        not_needed_fp: int = 0,
        must_activate_fn: int = 0,
        must_activate_fp: int = 0,
        ambiguous_fn: int = 0,
        ambiguous_fp: int = 0,
    ) -> dict:
        return {
            "regression_vs_408_baseline": {
                "aggregate": {
                    "total_false_negatives": regression_fn,
                    "total_false_positives": regression_fp,
                }
            },
            "activation_required_cases": {
                "cases": [
                    {
                        "id": proof.CASE_NOT_NEEDED,
                        "false_negatives": not_needed_fn,
                        "false_positives": not_needed_fp,
                    },
                    {
                        "id": proof.CASE_MUST_ACTIVATE,
                        "false_negatives": must_activate_fn,
                        "false_positives": must_activate_fp,
                    },
                    {
                        "id": proof.CASE_AMBIGUOUS,
                        "false_negatives": ambiguous_fn,
                        "false_positives": ambiguous_fp,
                    },
                ]
            },
        }

    def test_behavioral_mode_exits_non_zero_on_a_regression_miss(self) -> None:
        with mock.patch.object(
            proof,
            "measure_behavioral_proof",
            return_value=self._fake_result(regression_fn=1),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = proof.main(["behavioral"])

        self.assertEqual(exit_code, 1)

    def test_behavioral_mode_exits_non_zero_on_an_ambiguous_case_miss(self) -> None:
        # CASE_AMBIGUOUS is this issue's own, not-yet-pinned fixture -- a
        # miss here is a real regression, unlike the known-fragile reused
        # cases below.
        with mock.patch.object(
            proof,
            "measure_behavioral_proof",
            return_value=self._fake_result(ambiguous_fp=1),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = proof.main(["behavioral"])

        self.assertEqual(exit_code, 1)

    def test_behavioral_mode_stays_zero_on_known_fragile_reused_case_mismatch(
        self,
    ) -> None:
        # CASE_NOT_NEEDED/CASE_MUST_ACTIVATE are reused, already-pinned
        # specialist-depth-composition fixtures with a documented
        # defect_kind-wording matcher fragility
        # (specialist-depth-progressive-loading-proof.md §4) -- a mismatch
        # there must not fail this issue's own proof run.
        with mock.patch.object(
            proof,
            "measure_behavioral_proof",
            return_value=self._fake_result(
                not_needed_fn=1, not_needed_fp=1, must_activate_fn=1, must_activate_fp=2
            ),
        ):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                exit_code = proof.main(["behavioral"])

        self.assertEqual(exit_code, 0)

    def test_behavioral_mode_exits_zero_when_everything_matches(self) -> None:
        with mock.patch.object(
            proof, "measure_behavioral_proof", return_value=self._fake_result()
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = proof.main(["behavioral"])

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
