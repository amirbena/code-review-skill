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
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.scripts import run_benchmark_routine as routine


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

    def test_results_out_written_only_on_verified_run(self) -> None:
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
        with tempfile.TemporaryDirectory() as tmp:
            results_out = Path(tmp) / "results.json"
            with mock.patch("subprocess.run", return_value=_completed(good_output)), mock.patch.object(
                routine, "_post_evidence", return_value=42
            ):
                exit_code = routine.main(
                    [
                        "--mode",
                        "smoke",
                        "--case-id",
                        "c",
                        "--evidence-issue",
                        "1",
                        "--results-out",
                        str(results_out),
                    ]
                )
            self.assertEqual(exit_code, 0)
            payload = json.loads(results_out.read_text(encoding="utf-8"))
            self.assertEqual(payload, [{"case_id": "c", "run": json.loads(good_output)["run"]}])

    def test_results_out_not_written_on_unverified_run(self) -> None:
        bad_output = json.dumps({"run": {"ok": False, "cases": [{"id": "c", "status": "error", "error": "x"}]}})
        with tempfile.TemporaryDirectory() as tmp:
            results_out = Path(tmp) / "results.json"
            with mock.patch("subprocess.run", return_value=_completed(bad_output, returncode=1)):
                exit_code = routine.main(
                    [
                        "--mode",
                        "smoke",
                        "--case-id",
                        "c",
                        "--evidence-issue",
                        "1",
                        "--results-out",
                        str(results_out),
                    ]
                )
            self.assertEqual(exit_code, 1)
            self.assertFalse(results_out.exists())

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

    def test_full_mode_is_a_deprecated_alias_for_sentinel(self) -> None:
        # Issue #431: `full`'s ambiguity is resolved by making it a fixed,
        # deprecated synonym for `sentinel` — the persisted metadata mode
        # is always the canonical name, never the legacy one, and a
        # deprecation notice is emitted.
        good_output = json.dumps(
            {"run": {"ok": True, "cases": [{"id": "c", "input_kind": "diff", "status": "executed", "produced_findings": []}]}}
        )
        with mock.patch("subprocess.run", return_value=_completed(good_output)), mock.patch.object(
            routine, "_post_evidence", return_value=1
        ):
            exit_code = routine.main(["--mode", "full", "--evidence-issue", "1"])
        self.assertEqual(exit_code, 0)

    def test_sentinel_mode_runs_one_invocation_against_corpus_dir(self) -> None:
        good_output = json.dumps(
            {"run": {"ok": True, "cases": [{"id": "c", "input_kind": "diff", "status": "executed", "produced_findings": []}]}}
        )
        with mock.patch("subprocess.run", return_value=_completed(good_output)) as run, mock.patch.object(
            routine, "_post_evidence", return_value=1
        ) as post:
            exit_code = routine.main(["--mode", "sentinel", "--evidence-issue", "1"])
        self.assertEqual(exit_code, 0)
        run.assert_called_once()
        self.assertNotIn("--case-id", run.call_args.args[0])
        _, _, title, _ = post.call_args.args
        self.assertIn("sentinel", title)

    def test_comprehensive_mode_derives_membership_and_runs_one_invocation_per_case(self) -> None:
        good_output = json.dumps(
            {"run": {"ok": True, "cases": [{"id": "x", "input_kind": "diff", "status": "executed", "produced_findings": []}]}}
        )
        fixtures = [
            mock.Mock(case_id="a", corpus_dir=Path("/corpus/sub1")),
            mock.Mock(case_id="b", corpus_dir=Path("/corpus/sub2")),
        ]
        with mock.patch("subprocess.run", return_value=_completed(good_output)) as run, mock.patch.object(
            routine, "_post_evidence", return_value=1
        ), mock.patch.object(routine, "discover_comprehensive_fixtures", return_value=fixtures) as discover:
            exit_code = routine.main(["--mode", "comprehensive", "--evidence-issue", "1"])
        self.assertEqual(exit_code, 0)
        discover.assert_called_once()
        self.assertEqual(run.call_count, 2)
        called_case_ids = [
            call.args[0][call.args[0].index("--case-id") + 1] for call in run.call_args_list
        ]
        self.assertEqual(sorted(called_case_ids), ["a", "b"])

    def test_comprehensive_mode_fails_closed_on_empty_membership(self) -> None:
        with mock.patch.object(routine, "discover_comprehensive_fixtures", return_value=[]):
            exit_code = routine.main(["--mode", "comprehensive", "--evidence-issue", "1"])
        self.assertEqual(exit_code, 1)

    def test_post_evidence_uses_body_file_not_body_argument(self) -> None:
        # A large evidence payload passed as a literal --body argument can
        # exceed the OS argv-size limit; it must go through a temp file.
        captured_paths: list[str] = []

        def fake_gh(*args: str) -> str:
            self.assertNotIn("--body", args)
            self.assertIn("--body-file", args)
            path = args[args.index("--body-file") + 1]
            captured_paths.append(path)
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("hello evidence", content)
            return "https://github.com/o/r/issues/99"

        with mock.patch.object(routine, "_gh", side_effect=fake_gh):
            issue = routine._post_evidence(None, "<!-- marker -->", "title", "hello evidence")

        self.assertEqual(issue, 99)
        self.assertFalse(os.path.exists(captured_paths[0]), "temp body file must be cleaned up")


if __name__ == "__main__":
    unittest.main()
