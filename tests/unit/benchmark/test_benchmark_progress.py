"""Progress, heartbeat, and child-timing observability for benchmark runs (Issue #611); no live model."""

from __future__ import annotations

import io
import json
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_lane_run as lane_run
from runtime_platform.benchmark.scripts import benchmark_progress as prog
from runtime_platform.benchmark.scripts import run_benchmark as rb
from runtime_platform.benchmark.scripts import run_benchmark_routine as routine
from tests.unit.benchmark.test_run_benchmark_routine import EntrypointTestCase, FakeRunner, _corpus


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class ProgressLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.out = io.StringIO()
        self.log = prog.ProgressLog(self.out, clock=self.clock, heartbeat_interval_s=0.01)
        self.log.total = 2

    def test_item_logs_start_and_pass_with_duration_and_cumulative_clock(self) -> None:
        self.clock.now = 65.0

        def run() -> str:
            self.clock.now += 16.7
            return "ok"

        self.assertEqual(self.log.item("[1/2]", "case-a", run), "ok")
        lines = self.out.getvalue().splitlines()
        self.assertEqual(lines[0], "[+01:05] [1/2] START case-a")
        self.assertEqual(lines[-1], "[+01:21] [1/2] PASS case-a 16.7s")
        self.assertEqual(self.log.completed, 1)

    def test_failure_is_logged_with_reason_then_reraised_uncounted(self) -> None:
        def boom() -> None:
            raise lane_run.RoutineExecutionError("fail-closed:\n  not verified")

        with self.assertRaises(lane_run.RoutineExecutionError):
            self.log.item("[1/2]", "case-a", boom)
        self.assertIn("[1/2] FAIL case-a 0.0s reason=fail-closed: not verified", self.out.getvalue())
        self.assertEqual(self.log.completed, 0)

    def test_heartbeat_names_the_running_fixture_and_progress(self) -> None:
        release = threading.Event()

        def run() -> None:
            self.clock.now = 41.0
            release.wait(timeout=5)

        worker = threading.Thread(target=lambda: self.log.item("[1/2]", "slow-case", run))
        worker.start()
        deadline = time.monotonic() + 5
        while "[heartbeat]" not in self.out.getvalue() and time.monotonic() < deadline:
            time.sleep(0.005)
        release.set()
        worker.join()
        beat = next(line for line in self.out.getvalue().splitlines() if "[heartbeat]" in line)
        self.assertIn("completed=0/2 current=slow-case fixture_elapsed=41s total=00:41", beat)

    def test_phase_logs_duration_and_marks_failures(self) -> None:
        with self.log.phase("fixtures"):
            self.clock.now = 3.0
        with self.assertRaises(ValueError), self.log.phase("seal-handoff"):
            raise ValueError("x")
        text = self.out.getvalue()
        self.assertIn("[phase] fixtures DONE 3.0s", text)
        self.assertIn("[phase] seal-handoff FAILED after 0.0s", text)


class ChildTimingTests(unittest.TestCase):
    def test_round_trip_and_missing_line(self) -> None:
        line = prog.child_timing_line(1.25, 14.0, 16.7)
        self.assertEqual(prog.parse_child_timing(f"noise\n{line}\n"), {"probe": 1.2, "review": 14.0, "total": 16.7})
        self.assertIsNone(prog.parse_child_timing("no timing here"))

    def test_run_benchmark_emits_timing_on_stderr_and_keeps_stdout_json(self) -> None:
        class Result:
            exit_code = 0

            def as_dict(self) -> dict:
                return {"cases": []}

            case_results: list = []

        def run_corpus(_corpus_dir, adapter, **_kwargs):
            adapter(None)
            return Result()

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(rb, "check_runtime_available"), mock.patch.object(
            rb, "ProductionReviewerAdapter", return_value=lambda workspace: []
        ), mock.patch.object(rb.br, "run_corpus", run_corpus), mock.patch.object(
            rb, "_load_cases_for_metrics", return_value=[]
        ):
            with redirect_stdout(out), redirect_stderr(err):
                code = rb.main(["--cli", "stub"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue()), {"run": {"cases": []}})
        timing = prog.parse_child_timing(err.getvalue())
        self.assertEqual(set(timing), {"probe", "review", "total"})


class InvokeStderrTests(unittest.TestCase):
    def _invoke(self, stdout: str, stderr: str, returncode: int = 0):
        proc = mock.Mock(stdout=io.StringIO(stdout), stderr=io.StringIO(stderr), wait=lambda: returncode)
        with mock.patch.object(lane_run.subprocess, "Popen", return_value=proc), redirect_stderr(io.StringIO()):
            return lane_run.invoke("stub", 5.0, "a", "corpus")

    def test_passing_invocation_carries_the_child_timing(self) -> None:
        run = {"run": {"cases": [], "exit_code": 0}}
        verified = mock.Mock(passed=True, reason="verified", as_dict=lambda: {"passed": True})
        with mock.patch.object(lane_run, "verify_benchmark_output", return_value=verified):
            inv = self._invoke(json.dumps(run), f"warn\n{prog.child_timing_line(1.0, 9.0, 11.0)}\n")
        self.assertEqual(inv.timing, {"probe": 1.0, "review": 9.0, "total": 11.0})

    def test_failed_verification_includes_the_child_stderr_tail(self) -> None:
        failed = mock.Mock(passed=False, reason="exit 2")
        with mock.patch.object(lane_run, "verify_benchmark_output", return_value=failed):
            with self.assertRaises(lane_run.RoutineExecutionError) as ctx:
                self._invoke("", "line one\nTraceback boom", returncode=2)
        self.assertIn("exit 2", str(ctx.exception))
        self.assertIn("child stderr tail: line one Traceback boom", str(ctx.exception))


class ComprehensiveProgressTests(EntrypointTestCase):
    def run_comprehensive(self, runner) -> tuple[int, str]:
        corpus = _corpus(self.tmp / "corpus", ["a", "b"], v2=True)
        code, _, err = self.run_main(
            runner, "--mode", "comprehensive", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir)
        )
        return code, err

    def test_discovery_start_pass_and_phases_are_logged_in_order(self) -> None:
        code, err = self.run_comprehensive(FakeRunner())
        self.assertEqual(code, 0)
        positions = [
            err.index(text)
            for text in (
                "[comprehensive] discovered 2 fixtures",
                "[1/2] START a",
                "[1/2] PASS a",
                "[2/2] START b",
                "[2/2] PASS b",
                "[phase] drift-confirmation START",
                "[phase] seal-handoff DONE",
            )
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("[phase] fixtures DONE", err)

    def test_child_timing_split_is_surfaced_after_completion(self) -> None:
        runner = FakeRunner()

        def timed(*args):
            inv = runner(*args)
            return lane_run.Invocation(inv.verification, inv.output, inv.duration_s, {"probe": 1.0, "review": 9.0, "total": 11.0})

        _, err = self.run_comprehensive(timed)
        self.assertIn("PASS a", err)
        self.assertIn("(probe=1.0s review=9.0s other=1.0s)", err)

    def test_failure_names_the_fixture_before_failing_fast(self) -> None:
        runner = FakeRunner()

        def fail_second(executable, timeout, case_id, corpus_dir):
            if case_id == "b":
                raise lane_run.RoutineExecutionError("fail-closed: not verified")
            return runner(executable, timeout, case_id, corpus_dir)

        code, err = self.run_comprehensive(fail_second)
        self.assertEqual(code, 1)
        self.assertIn("[2/2] FAIL b", err)
        self.assertIn("reason=fail-closed: not verified", err)
        self.assertLess(err.index("[2/2] FAIL b"), err.index("error: fail-closed"))
        self.assertFalse(self.seal_dir.exists())

    def test_progress_never_reaches_stdout(self) -> None:
        corpus = _corpus(self.tmp / "corpus", ["a"], v2=True)
        _, out, _ = self.run_main(
            FakeRunner(), "--mode", "comprehensive", "--corpus-dir", str(corpus), "--seal-dir", str(self.seal_dir)
        )
        self.assertNotIn("START", out)
        self.assertIn("run_id", json.loads(out))


if __name__ == "__main__":
    unittest.main()


class BrokenStreamTests(unittest.TestCase):
    def test_a_failing_stream_never_raises_from_log_or_main(self) -> None:
        class Broken:
            def write(self, _s: str) -> int:
                raise BrokenPipeError

            def flush(self) -> None:
                raise BrokenPipeError

        prog.ProgressLog(stream=Broken()).log("hello")
        out = io.StringIO()
        with mock.patch.object(rb, "check_runtime_available"), mock.patch.object(
            rb, "ProductionReviewerAdapter", return_value=lambda workspace: []
        ), mock.patch.object(rb, "_load_cases_for_metrics", return_value=[]), mock.patch.object(
            rb.br, "run_corpus", lambda *_a, **_k: mock.Mock(as_dict=lambda: {"cases": []}, exit_code=0, case_results=())
        ):
            with redirect_stdout(out), mock.patch.object(rb.sys, "stderr", Broken()):
                code = rb.main(["--cli", "stub"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue()), {"run": {"cases": []}})
