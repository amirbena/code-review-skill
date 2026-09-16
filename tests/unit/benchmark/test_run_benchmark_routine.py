#!/usr/bin/env python3
"""Wiring coverage for the Cloud Routine entrypoint (Issue #415).

Never invokes a real review CLI or real ``gh``: ``run_benchmark.py`` and
``gh`` are both replaced with subprocess stubs, so this proves the
entrypoint's own logic — fail-closed on an unverified run, evidence
persisted only on a verified run, and the auth-check mode posts
independently of any benchmark run.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from scripts.benchmark import run_benchmark_routine as routine


def _completed(stdout: str, returncode: int = 0) -> mock.Mock:
    result = mock.Mock()
    result.stdout = stdout
    result.stderr = ""
    result.returncode = returncode
    return result


class RunBenchmarkRoutineTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(routine, "_git_sha", return_value="deadbeef" * 5)
        self.addCleanup(patcher.stop)
        patcher.start()
        version_patcher = mock.patch.object(routine, "_runtime_version", return_value="1.0.0")
        self.addCleanup(version_patcher.stop)
        version_patcher.start()

    def test_fail_closed_never_posts_evidence_on_unverified_run(self) -> None:
        bad_output = json.dumps({"run": {"ok": False, "cases": [{"id": "c", "status": "error", "error": "x"}]}})
        with mock.patch("subprocess.run", return_value=_completed(bad_output, returncode=1)), mock.patch.object(
            routine, "_post_evidence"
        ) as post:
            exit_code = routine.main(
                ["--mode", "smoke", "--case-id", "c", "--evidence-issue", "1"]
            )
            self.assertEqual(exit_code, 1)
            post.assert_not_called()

    def test_verified_run_posts_evidence_with_metadata(self) -> None:
        good_output = json.dumps(
            {
                "run": {
                    "ok": True,
                    "cases": [
                        {"id": "c", "input_kind": "diff", "status": "executed", "produced_findings": []}
                    ],
                }
            }
        )
        with mock.patch("subprocess.run", return_value=_completed(good_output, returncode=0)), mock.patch.object(
            routine, "_post_evidence", return_value=42
        ) as post:
            exit_code = routine.main(
                [
                    "--mode",
                    "smoke",
                    "--case-id",
                    "c",
                    "--evidence-issue",
                    "1",
                    "--model-id",
                    "claude-opus-5",
                ]
            )
            self.assertEqual(exit_code, 0)
            post.assert_called_once()
            _, _, title, body = post.call_args.args
            self.assertIn("smoke", title)
            self.assertIn("claude-opus-5", body)

    def test_auth_check_mode_posts_independently_of_benchmark_run(self) -> None:
        with mock.patch("subprocess.run") as run, mock.patch.object(
            routine, "_post_evidence", return_value=7
        ) as post:
            exit_code = routine.main(["--mode", "auth-check", "--evidence-issue", "7"])
            self.assertEqual(exit_code, 0)
            post.assert_called_once()
            run.assert_not_called()

    def test_selected_mode_requires_case_id(self) -> None:
        exit_code = routine.main(["--mode", "selected"])
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
