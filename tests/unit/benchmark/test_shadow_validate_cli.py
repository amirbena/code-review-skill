#!/usr/bin/env python3
"""Behavioral coverage for the shadow-validation report CLI entrypoint
(Issue #335). Contract: docs/benchmark/shadow-validation.md §5.

Exercises ``scripts/benchmark/shadow_validate.py`` end to end against a
small synthetic burn-in window file. Proves: the emitted JSON matches
``benchmark_shadow_validation.build_burn_in_report``'s shape exactly (no
second, CLI-local computation), the step-summary file is appended to
(never overwritten), a malformed samples file is rejected, and the
report never carries a pass/fail verdict of its own.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.benchmark import shadow_validate as cli
from tests.reference.benchmark import benchmark_shadow_validation as sv

SAMPLES = [
    {"sample_id": "pr-1", "selected_case_ids": ["case-a", "case-b"], "regressed_case_ids": ["case-b"]},
    {"sample_id": "pr-2", "selected_case_ids": ["case-a"], "regressed_case_ids": ["case-c"]},
]


class LoadSamplesTests(unittest.TestCase):
    def test_loads_a_well_formed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.json"
            path.write_text(json.dumps(SAMPLES), encoding="utf-8")
            samples = cli.load_samples(path)
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0].sample_id, "pr-1")

    def test_rejects_a_non_array_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.json"
            path.write_text(json.dumps({"not": "an array"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                cli.load_samples(path)

    def test_rejects_a_sample_missing_a_required_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.json"
            path.write_text(json.dumps([{"sample_id": "pr-1", "selected_case_ids": []}]), encoding="utf-8")
            with self.assertRaises(ValueError):
                cli.load_samples(path)


class MainCliTests(unittest.TestCase):
    def test_emits_report_json_matching_the_reference_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            samples_path = tmp / "samples.json"
            samples_path.write_text(json.dumps(SAMPLES), encoding="utf-8")
            output_path = tmp / "out.json"

            exit_code = cli.main(
                [
                    "--samples",
                    str(samples_path),
                    "--window-description",
                    "unit test window",
                    "--output",
                    str(output_path),
                ]
            )
            self.assertEqual(exit_code, 0)

            emitted = json.loads(output_path.read_text(encoding="utf-8"))
            expected_samples = cli.load_samples(samples_path)
            expected = json.loads(
                json.dumps(
                    sv.build_burn_in_report(
                        sv.aggregate_burn_in(expected_samples), window_description="unit test window"
                    )
                )
            )
            self.assertEqual(emitted, expected)
            self.assertNotIn("verdict", emitted)
            self.assertNotIn("passed", emitted)

    def test_step_summary_is_appended_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            samples_path = tmp / "samples.json"
            samples_path.write_text(json.dumps(SAMPLES), encoding="utf-8")
            step_summary_path = tmp / "summary.md"
            step_summary_path.write_text("# pre-existing content\n", encoding="utf-8")

            cli.main(
                [
                    "--samples",
                    str(samples_path),
                    "--window-description",
                    "unit test window",
                    "--step-summary",
                    str(step_summary_path),
                    "--output",
                    str(tmp / "out.json"),
                ]
            )

            summary = step_summary_path.read_text(encoding="utf-8")
            self.assertIn("# pre-existing content", summary)
            self.assertIn("Shadow-validation burn-in report (#335)", summary)

    def test_vacuous_window_never_fails_the_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            samples_path = tmp / "samples.json"
            samples_path.write_text(json.dumps([]), encoding="utf-8")

            exit_code = cli.main(
                [
                    "--samples",
                    str(samples_path),
                    "--window-description",
                    "empty window",
                    "--output",
                    str(tmp / "out.json"),
                    "--step-summary",
                    str(tmp / "summary.md"),
                ]
            )
            self.assertEqual(exit_code, 0)
            emitted = json.loads((tmp / "out.json").read_text(encoding="utf-8"))
            self.assertIsNone(emitted["miss_rate"])
            self.assertIsNone(emitted["redundancy_rate"])


if __name__ == "__main__":
    unittest.main()
