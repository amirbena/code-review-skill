"""Execution-side entrypoint (Issues #415, #431, #470).

`run_benchmark.py` is replaced by a fake runner, so this proves the entrypoint's own logic:
fail-closed before any seal, in-run confirmation, and sealing without any GitHub write.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Callable
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_lane_run as lane_run
from runtime_platform.benchmark.scripts import benchmark_result as res
from runtime_platform.benchmark.scripts import benchmark_seal as seal
from runtime_platform.benchmark.scripts import run_benchmark_routine as routine
from tests.support.benchmark_records import make_case, run_output, write_history

NOW = "2026-09-20T01:00:00Z"


class FakeRunner:
    """Stands in for `run_benchmark.py`; `missed(case_id, call_index)` scripts each case's outcome."""

    def __init__(self, missed: Callable[[str, int], list[str]] = lambda case_id, n: []) -> None:
        self.missed = missed
        self.calls: list[str | None] = []
        self._seen: dict[str, int] = {}

    def __call__(self, executable: str, timeout: float, case_id: str | None, corpus_dir: str) -> lane_run.Invocation:
        self.calls.append(case_id)
        ids = [case_id] if case_id else sorted(p.stem for p in Path(corpus_dir).glob("*.yaml"))
        cases = []
        for cid in ids:
            n = self._seen.get(cid, 0)
            self._seen[cid] = n + 1
            cases.append(make_case(cid, missed=self.missed(cid, n)))
        verification = {"passed": True, "reason": "verified", "case_count": len(ids), "case_ids": ids}
        return lane_run.Invocation(verification, run_output(cases), 2.0)


def _failing(*_: object) -> lane_run.Invocation:
    raise lane_run.RoutineExecutionError("fail-closed: not verified")


def _corpus(root: Path, ids: list[str], *, v2: bool = False) -> Path:
    for cid in ids:
        directory = root / cid if v2 else root
        directory.mkdir(parents=True, exist_ok=True)
        header = "format: benchmark-case/v2\n" if v2 else ""
        (directory / f"{cid}.yaml").write_text(f"{header}id: {cid}\n", encoding="utf-8")
    return root


class EntrypointTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.seal_dir = self.tmp / "sealed"
        for target, value in (
            (routine, {"_git_sha": "a" * 40, "_git_ref": "refs/heads/main", "utc_now": NOW}),
            (lane_run, {"utc_now": NOW}),
        ):
            for name, result in value.items():
                patcher = mock.patch.object(target, name, return_value=result) if name != "utc_now" else mock.patch.object(
                    target, name, side_effect=lambda: NOW
                )
                patcher.start()
                self.addCleanup(patcher.stop)

    def run_main(self, runner: Callable, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(routine, "invoke", runner), mock.patch.object(lane_run, "invoke", runner):
            with redirect_stdout(out), redirect_stderr(err):
                code = routine.main(["--cli", "stub", "--runtime-version", "cli-1", "--history-root", str(self.tmp / "no-history"), *argv])
        return code, out.getvalue(), err.getvalue()

    def sealed(self, seal_dir: Path | None = None) -> dict:
        return json.loads(((seal_dir or self.seal_dir) / seal.RECORD_FILE).read_text(encoding="utf-8"))


class FailClosedTests(EntrypointTestCase):
    def test_unverified_invocation_seals_nothing(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a"])
        code, _, err = self.run_main(_failing, "--mode", "sentinel", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir))
        self.assertEqual(code, 1)
        self.assertIn("fail-closed", err)
        self.assertFalse(self.seal_dir.exists())

    def test_seal_failure_is_a_failed_run(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a"])
        with mock.patch.object(seal, "seal_to_ref", side_effect=seal.SealError("push refused")):
            code, _, err = self.run_main(FakeRunner(), "--mode", "sentinel", "--corpus-dir", str(corpus))
        self.assertEqual(code, 1)
        self.assertIn("push refused", err)

    def test_partial_coverage_is_never_sealed(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a", "b"])
        runner = FakeRunner()

        def partial(executable: str, timeout: float, case_id: str | None, corpus_dir: str) -> lane_run.Invocation:
            inv = runner(executable, timeout, "a", corpus_dir)
            return inv

        code, _, err = self.run_main(partial, "--mode", "sentinel", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir))
        self.assertEqual(code, 1)
        self.assertIn("exactly the lane's membership", err)
        self.assertFalse(self.seal_dir.exists())

    def test_invalid_manifest_fails_before_any_invocation(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a"])
        bad = self.tmp / "manifest.json"
        bad.write_text("{}", encoding="utf-8")
        runner = FakeRunner()
        code, _, err = self.run_main(runner, "--mode", "sentinel", "--corpus-dir", str(corpus), "--manifest", str(bad))
        self.assertEqual(code, 1)
        self.assertIn("invalid manifest", err)
        self.assertEqual(runner.calls, [])

    def test_a_broken_prompt_template_fails_before_any_invocation(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a"])
        doc = self.tmp / "doc.md"
        doc.write_text("no template block\n", encoding="utf-8")
        runner = FakeRunner()
        with mock.patch.object(lane_run, "ROUTINE_DOC", doc):
            code, _, err = self.run_main(runner, "--mode", "sentinel", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir))
        self.assertEqual(code, 1)
        self.assertIn("prompt template", err)
        self.assertEqual(runner.calls, [])
        self.assertFalse(self.seal_dir.exists())

    def test_a_lane_with_no_fixtures_fails_closed(self) -> None:
        empty = self.tmp / "empty"
        empty.mkdir()
        code, _, err = self.run_main(FakeRunner(), "--mode", "comprehensive", "--corpus-dir", str(empty))
        self.assertEqual(code, 1)
        self.assertIn("no benchmark-case fixtures", err)

    def test_selected_mode_requires_case_id(self) -> None:
        self.assertEqual(self.run_main(FakeRunner(), "--mode", "selected")[0], 1)


class NonLaneModeTests(EntrypointTestCase):
    def test_smoke_prints_verified_metadata_and_seals_nothing(self) -> None:
        code, out, _ = self.run_main(
            FakeRunner(), "--mode", "smoke", "--case-id", "c", "--model-id", "claude-opus-5", "--seal-dir", str(self.seal_dir)
        )
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual((payload["metadata"]["mode"], payload["metadata"]["model_id"]), ("smoke", "claude-opus-5"))
        self.assertTrue(payload["overall_verified"])
        self.assertNotIn("evidence_issue", payload)
        self.assertFalse(self.seal_dir.exists())

    def test_results_out_written_only_on_a_verified_run(self) -> None:
        results = self.tmp / "results.json"
        self.run_main(_failing, "--mode", "smoke", "--case-id", "c", "--results-out", str(results))
        self.assertFalse(results.exists())
        self.run_main(FakeRunner(), "--mode", "smoke", "--case-id", "c", "--results-out", str(results))
        payload = json.loads(results.read_text(encoding="utf-8"))
        self.assertEqual(payload[0]["case_id"], "c")

    def test_auth_check_seals_a_handoff_marker_and_runs_no_benchmark(self) -> None:
        runner = FakeRunner()
        code, out, _ = self.run_main(runner, "--mode", "auth-check", "--seal-dir", str(self.seal_dir))
        self.assertEqual(code, 0)
        self.assertEqual(runner.calls, [])
        self.assertTrue(json.loads(out)["ref"].startswith(seal.HANDOFF_CHECK_REF_PREFIX))
        self.assertEqual([p.name for p in self.seal_dir.iterdir()], [seal.HANDOFF_CHECK_FILE])

    def test_auth_check_pushes_only_a_claude_ref(self) -> None:
        with mock.patch.object(seal, "seal_to_ref", return_value="c0ffee") as push:
            code, _, _ = self.run_main(FakeRunner(), "--mode", "auth-check")
        self.assertEqual(code, 0)
        _, remote, ref, files, _ = push.call_args.args
        self.assertEqual(remote, "origin")
        self.assertTrue(ref.startswith("claude/"))
        self.assertEqual(list(files), [seal.HANDOFF_CHECK_FILE])


class SealedLaneTests(EntrypointTestCase):
    def test_sentinel_runs_one_invocation_and_seals_a_valid_record(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a", "b"])
        runner = FakeRunner()
        code, out, _ = self.run_main(
            runner, "--mode", "sentinel", "--trigger", "scheduled", "--model-id", "m", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir)
        )
        record = self.sealed()
        self.assertEqual(code, 0)
        self.assertEqual(runner.calls, [None])
        self.assertEqual(res.validate_record(record), [])
        self.assertEqual((record["lane"], record["mode"], record["trigger"]), ("sentinel", "sentinel", "scheduled"))
        self.assertEqual(record["runtime"]["model_id"], "m")
        self.assertEqual(record["baseline"]["state"], "bootstrap")
        self.assertEqual(json.loads(out)["run_id"], record["run_id"])
        self.assertEqual(sorted(p.name for p in self.seal_dir.iterdir()), sorted([seal.RAW_FILE, seal.RECORD_FILE]))

    def test_trigger_defaults_to_manual(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a"])
        self.run_main(FakeRunner(), "--mode", "sentinel", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir))
        self.assertEqual(self.sealed()["trigger"], "manual")

    def test_full_is_sealed_as_sentinel_with_a_warning(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a"])
        code, _, err = self.run_main(FakeRunner(), "--mode", "full", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir))
        record = self.sealed()
        self.assertEqual((code, record["lane"], record["mode"]), (0, "sentinel", "full"))
        self.assertEqual(res.validate_record(record), [])
        self.assertIn("deprecated", err)
        self.assertTrue(record["execution"]["warnings"])

    def test_comprehensive_runs_one_invocation_per_case(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a", "b", "c"], v2=True)
        runner = FakeRunner()
        code, _, _ = self.run_main(runner, "--mode", "comprehensive", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir))
        self.assertEqual(code, 0)
        self.assertEqual(sorted(runner.calls), ["a", "b", "c"])
        self.assertEqual(res.validate_record(self.sealed()), [])

    def test_the_raw_bundle_is_hashed_into_the_record(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a"])
        self.run_main(FakeRunner(), "--mode", "sentinel", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir))
        record = self.sealed()
        raw = (self.seal_dir / seal.RAW_FILE).read_bytes()
        self.assertEqual(record["raw"]["bundle_sha256"], res.sha256_hex(raw.decode("utf-8")))
        self.assertEqual(record["raw"]["location"], f"{seal.staging_ref(record['run_id'])}:{seal.RAW_FILE}")

    def test_default_hand_off_pushes_one_staging_ref(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a"])
        with mock.patch.object(seal, "seal_to_ref", return_value="c0ffee") as push:
            code, out, _ = self.run_main(FakeRunner(), "--mode", "sentinel", "--corpus-dir", str(corpus), "--history-root", str(self.tmp))
        self.assertEqual(code, 0)
        _, remote, ref, files, _ = push.call_args.args
        self.assertEqual(remote, "origin")
        self.assertRegex(ref, r"^claude/benchmark-result-sentinel-\d{8}T\d{6}Z-[0-9a-f]{12}$")
        self.assertEqual(sorted(files), sorted([seal.RAW_FILE, seal.RECORD_FILE]))
        self.assertIn(f"origin:{ref}@c0ffee", json.loads(out)["handoff"])


class DriftConfirmationTests(EntrypointTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.corpus = _corpus(self.tmp / "corpus", ["a", "b"])
        self.history = self.tmp / "history"
        baseline_dir = self.tmp / "baseline-seal"
        self.run_main(FakeRunner(), "--mode", "sentinel", "--corpus-dir", str(self.corpus), "--seal-dir", str(baseline_dir))
        write_history(self.history, self.sealed(baseline_dir))

    def second_run(self, runner: FakeRunner) -> dict:
        code, _, _ = self.run_main(
            runner, "--mode", "sentinel", "--corpus-dir", str(self.corpus), "--history-root", str(self.history), "--seal-dir", str(self.seal_dir)
        )
        self.assertEqual(code, 0)
        return self.sealed()

    def test_a_clean_run_against_the_baseline_runs_no_confirmation(self) -> None:
        runner = FakeRunner()
        record = self.second_run(runner)
        self.assertEqual(runner.calls, [None])
        self.assertEqual(record["baseline"]["state"], "compared")
        self.assertEqual(record["drift"]["outcome"], {"status": "none", "reason": None})
        self.assertEqual(record["execution"]["confirmation_reruns"], 0)

    def test_reproduced_drift_is_confirmed_by_rerunning_only_that_case(self) -> None:
        runner = FakeRunner(lambda cid, n: ["k"] if cid == "a" else [])
        record = self.second_run(runner)
        self.assertEqual(runner.calls, [None, "a", "a"])
        self.assertEqual(record["execution"]["confirmation_reruns"], 2)
        self.assertEqual(record["drift"]["outcome"]["status"], "drift")
        self.assertEqual({d["case_id"] for d in record["drift"]["confirmed"]}, {"a"})
        self.assertEqual(list(record["drift"]["evidence"]), ["a"])
        self.assertEqual(res.validate_record(record), [])
        bundle = json.loads((self.seal_dir / seal.RAW_FILE).read_text(encoding="utf-8"))
        self.assertEqual(len(bundle["confirmation_reruns"]), 2)

    def test_a_flake_is_recorded_unconfirmed_and_not_drift(self) -> None:
        runner = FakeRunner(lambda cid, n: ["k"] if cid == "a" and n == 0 else [])
        record = self.second_run(runner)
        self.assertEqual(record["drift"]["outcome"]["status"], "none")
        self.assertEqual(record["drift"]["confirmed"], [])
        self.assertEqual({u["reason"] for u in record["drift"]["unconfirmed"]}, {"not-reproduced"})
        self.assertEqual(res.validate_record(record), [])

    def test_an_unverifiable_confirmation_rerun_seals_nothing(self) -> None:
        runner = FakeRunner(lambda cid, n: ["k"] if cid == "a" else [])

        def flaky(executable: str, timeout: float, case_id: str | None, corpus_dir: str) -> lane_run.Invocation:
            if runner.calls:
                raise lane_run.RoutineExecutionError("fail-closed: rerun not verified")
            return runner(executable, timeout, case_id, corpus_dir)

        code, _, err = self.run_main(
            flaky, "--mode", "sentinel", "--corpus-dir", str(self.corpus), "--history-root", str(self.history), "--seal-dir", str(self.tmp / "other")
        )
        self.assertEqual(code, 1)
        self.assertIn("rerun not verified", err)
        self.assertFalse((self.tmp / "other").exists())

    def test_an_exhausted_budget_records_unconfirmed_timeout(self) -> None:
        runner = FakeRunner(lambda cid, n: ["k"] if cid == "a" else [])
        code, _, _ = self.run_main(
            runner,
            "--mode", "sentinel", "--corpus-dir", str(self.corpus), "--history-root", str(self.history),
            "--confirmation-budget-s", "0", "--seal-dir", str(self.seal_dir),
        )
        record = self.sealed()
        self.assertEqual(code, 0)
        self.assertEqual(runner.calls, [None])
        self.assertEqual({u["reason"] for u in record["drift"]["unconfirmed"]}, {"unconfirmed-timeout"})


class RetiredGitHubPathTests(unittest.TestCase):
    def test_gh_helpers_are_gone(self) -> None:
        for name in ("_gh", "_post_evidence", "EVIDENCE_MARKER", "AUTH_CHECK_MARKER"):
            self.assertFalse(hasattr(routine, name), name)

    def test_evidence_issue_is_no_longer_an_argument(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            routine.build_arg_parser().parse_args(["--mode", "smoke", "--evidence-issue", "1"])


if __name__ == "__main__":
    unittest.main()
