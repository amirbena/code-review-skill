"""Isolation, namespace, stop-condition and failure guarantees of the temporary concurrency experiment (Issue #681).

Every run drives a stub review CLI; no live model call is made.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_concurrency_workers as workers
from runtime_platform.benchmark.scripts import benchmark_schedule_manifest as manifest_mod
from runtime_platform.benchmark.scripts import benchmark_seal as seal
from runtime_platform.benchmark.scripts import run_concurrency_experiment as exp
from runtime_platform.benchmark.scripts.benchmark_lane_run import RoutineExecutionError

SCRIPT = Path(exp.__file__)
WORKERS_SCRIPT = Path(workers.__file__)
STUB = (
    "#!/usr/bin/env python3\n"
    "import sys, time\n"
    "prompt = sys.argv[sys.argv.index('-p') + 1] if '-p' in sys.argv else ''\n"
    "{extra}"
    "print('**Result:** No findings.' if 'local-code-review' in prompt else 'ok')\n"
)


def write_stub(directory: Path, extra: str = "") -> Path:
    path = directory / "stub-review-cli.py"
    path.write_text(STUB.format(extra=extra), encoding="utf-8")
    path.chmod(0o755)
    return path


def small_spec(directory: Path, **stop) -> Path:
    spec = exp.load_spec()
    spec["subset"] = {**spec["subset"], "size": 4, "case_ids": spec["subset"]["case_ids"][:4], "strata": None, "subset_id": None}
    spec["stop_condition"] = {**spec["stop_condition"], **stop}
    path = directory / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def activated(**overrides) -> dict:
    spec = exp.load_spec()
    spec["stop_condition"] = {
        **spec["stop_condition"],
        "window_end": "2026-11-05",
        "experiments": [{"date": d, "arms": a} for d, a in zip(("2026-10-27", "2026-10-29", "2026-11-03", "2026-11-05"), ([1, 2], [2, 4], [2, 1], [4, 2]))],
        **overrides,
    }
    return spec


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, cwd=str(exp.REPO_ROOT))


class NamespaceTest(unittest.TestCase):
    def test_not_in_manifest_lanes_and_prefixes_are_outside_the_result_namespace(self):
        manifest = manifest_mod.load_manifest(manifest_mod.MANIFEST_PATH)
        self.assertNotIn("concurrency-experiment", manifest["lanes"])
        for prefix in (exp.EXPERIMENT_REF_PREFIX, exp.TRIAL_REF_PREFIX):
            self.assertTrue(prefix.startswith(seal.CONFINED_REF_PREFIX))
            self.assertFalse(prefix.startswith(seal.STAGING_REF_PREFIX))
            self.assertFalse(prefix.startswith(seal.HANDOFF_CHECK_REF_PREFIX))
        self.assertFalse(exp.TRIAL_REF_PREFIX.startswith(exp.EXPERIMENT_REF_PREFIX))

    def test_only_scheduled_runs_use_the_counted_prefix(self):
        self.assertTrue(exp.experiment_ref("x", "scheduled").startswith(exp.EXPERIMENT_REF_PREFIX))
        for trigger in ("manual", "api"):
            self.assertTrue(exp.experiment_ref("x", trigger).startswith(exp.TRIAL_REF_PREFIX))

    def test_confined_ref_refuses_result_baseline_and_arbitrary_refs(self):
        for ref in ("claude/benchmark-result-1", "claude/benchmark-baseline-1", "main", "claude/severity-observation-1", "claude/concurrency-other"):
            with self.assertRaises(RoutineExecutionError, msg=ref):
                exp.confined_ref(ref)
        self.assertEqual(exp.confined_ref("claude/concurrency-trial-1"), "claude/concurrency-trial-1")

    def test_no_lane_baseline_publication_or_github_code_path(self):
        forbidden_modules = ("publish_benchmark", "benchmark_baseline", "benchmark_drift", "benchmark_history", "benchmark_result", "benchmark_run_record")
        for path in (SCRIPT, WORKERS_SCRIPT):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            imported = {
                n.module if isinstance(n, ast.ImportFrom) else a.name
                for n in ast.walk(tree)
                if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in (n.names if isinstance(n, ast.Import) else [None])
            }
            for module in forbidden_modules:
                self.assertFalse([m for m in imported if m and module in m], f"{path.name} imports {module}")
            for token in ('"gh"', "api.github.com", "GH_TOKEN", "GITHUB_TOKEN", "tracking"):
                self.assertNotIn(token, source, path.name)

    def test_dry_run_writes_only_experiment_files_and_pushes_nothing(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(exp.seal, "seal_to_ref") as push:
            stub, spec, out = write_stub(Path(t)), small_spec(Path(t)), Path(t) / "out"
            argv = ["--arms", "1,2", "--cli", str(stub), "--runtime-version", "v1", "--spec", str(spec), "--seal-dir", str(out)]
            self.assertEqual(exp.main(argv), 0)
            self.assertEqual({p.name for p in out.iterdir()}, {exp.EXPERIMENT_FILE, exp.RAW_FILE})
            push.assert_not_called()

    def test_push_targets_only_the_trial_ref_for_a_manual_run_and_never_lists_experiments(self):
        with tempfile.TemporaryDirectory() as t:
            stub, spec = write_stub(Path(t)), small_spec(Path(t))
            argv = ["--arms", "1", "--cli", str(stub), "--runtime-version", "v1", "--spec", str(spec)]
            with mock.patch.object(exp, "prior_experiment_refs") as listing, mock.patch.object(exp.seal, "seal_to_ref", return_value="c" * 40) as push:
                self.assertEqual(exp.main(argv), 0)
            listing.assert_not_called()
            self.assertTrue(push.call_args.args[2].startswith(exp.TRIAL_REF_PREFIX))
            self.assertEqual(set(push.call_args.args[3]), {exp.EXPERIMENT_FILE, exp.RAW_FILE})

    def test_every_parent_subprocess_is_plain_git(self):
        calls: list[list[str]] = []
        real = subprocess.run

        def recorder(argv, **kwargs):
            calls.append([str(a) for a in argv])
            if argv[0] == "git" and argv[1] in {"hash-object", "mktree", "commit-tree", "push", "ls-remote"}:
                out = {"hash-object": "a" * 40, "mktree": "b" * 40, "commit-tree": "c" * 40}.get(argv[1], "")
                if argv[1] == "ls-remote":
                    out = f"{'c' * 40}\t{argv[3]}\n"
                return mock.Mock(returncode=0, stdout=out.encode(), stderr=b"")
            return real(argv, **kwargs)

        with tempfile.TemporaryDirectory() as t:
            stub, spec = write_stub(Path(t)), small_spec(Path(t))
            with mock.patch("subprocess.run", side_effect=recorder):
                code = exp.main(["--arms", "1", "--cli", str(stub), "--runtime-version", "v1", "--spec", str(spec)])
        self.assertEqual(code, 0)
        pushes = [c for c in calls if c[:2] == ["git", "push"]]
        self.assertEqual(len(pushes), 1)
        self.assertTrue(pushes[0][3].split(":", 1)[1].startswith(f"refs/heads/{exp.TRIAL_REF_PREFIX}"))
        for token in ("gh", "issue", "comment", "benchmark-history", "benchmark-result"):
            self.assertFalse([c for c in calls if c[0] == token or token in " ".join(c[:3])], token)


class StopConditionTest(unittest.TestCase):
    def test_refuses_before_activation(self):
        inactive = exp.load_spec()
        inactive["stop_condition"] = {**inactive["stop_condition"], "window_end": None, "experiments": []}
        self.assertEqual(exp.skip_reason(inactive, [], "2026-10-27", "2026-10-27"), "not-activated")

    def test_runs_only_on_a_listed_day(self):
        spec = activated()
        self.assertIsNone(exp.skip_reason(spec, [], "2026-10-27", "2026-10-27"))
        self.assertEqual(exp.skip_reason(spec, [], "2026-10-28", "2026-10-28"), "not-an-experiment-day")
        self.assertEqual(exp.scheduled_arms(spec, "2026-10-29"), [2, 4])

    def test_refuses_after_the_fourth_experiment_even_on_a_listed_day(self):
        refs = [f"{exp.EXPERIMENT_REF_PREFIX}2026102{i}T090000Z-x" for i in range(4)]
        self.assertEqual(exp.skip_reason(activated(), refs, "2026-11-05", "2026-11-05"), "stop-condition-reached")

    def test_a_failed_experiment_still_counts_and_makes_up_nothing(self):
        refs = [f"{exp.EXPERIMENT_REF_PREFIX}20261027T090000Z-x"]
        self.assertEqual(exp.skip_reason(activated(), refs, "2026-10-27", "2026-10-27"), "already-experimented-today")
        self.assertEqual(exp.skip_reason(activated(), refs, "2026-10-28", "2026-10-28"), "not-an-experiment-day")

    def test_refuses_after_the_window_end_even_with_runs_left(self):
        self.assertEqual(exp.skip_reason(activated(), [], "2026-11-06", "2026-11-06"), "window-ended")
        spec = activated(window_end="2026-10-28")
        self.assertEqual(exp.skip_reason(spec, [], "2026-10-29", "2026-10-29"), "window-ended")

    def test_main_runs_nothing_once_the_campaign_is_spent(self):
        refs = [f"{exp.EXPERIMENT_REF_PREFIX}2026102{i}T090000Z-x" for i in range(4)]
        with mock.patch.object(exp, "prior_experiment_refs", return_value=refs), mock.patch.object(exp.workers_mod, "run_arm") as arm, mock.patch.object(
            exp, "load_spec", return_value=activated()
        ):
            self.assertEqual(exp.main(["--cli", "fake", "--trigger", "scheduled"]), 0)
        arm.assert_not_called()

    def test_main_runs_nothing_when_listing_refs_fails(self):
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 1)), mock.patch.object(exp.workers_mod, "run_arm") as arm:
            self.assertEqual(exp.main(["--cli", "fake", "--trigger", "scheduled"]), 1)
        arm.assert_not_called()

    def test_scheduled_run_refuses_cli_arms(self):
        with mock.patch.object(exp, "prior_experiment_refs", return_value=[]):
            self.assertEqual(exp.main(["--cli", "fake", "--trigger", "scheduled", "--arms", "4"]), 1)

    def test_spec_is_temporary_and_has_a_removal_path(self):
        spec = exp.load_spec()
        self.assertTrue(spec["temporary"])
        self.assertEqual(spec["allowed_workers"], [1, 2, 4])
        self.assertEqual(spec["stop_condition"]["max_experiments"], 4)
        self.assertEqual(spec["intended_start"]["weekdays"], ["Tuesday", "Thursday"])
        self.assertEqual(spec["intended_start"]["timezone"], "Asia/Jerusalem")
        self.assertTrue(spec["removal_path"])
        self.assertTrue(spec["failure_policy"])


class SubsetTest(unittest.TestCase):
    def test_selection_is_deterministic_and_records_identity(self):
        spec = exp.load_spec()
        first, manifest = exp.select_subset(spec, str(exp.rb.DEFAULT_CORPUS_DIR))
        second, again = exp.select_subset(spec, str(exp.rb.DEFAULT_CORPUS_DIR))
        self.assertEqual([f.case_id for f in first], [f.case_id for f in second])
        self.assertEqual(manifest, again)
        self.assertEqual(len(first), spec["subset"]["size"])
        self.assertEqual([f.case_id for f in first], sorted(f.case_id for f in first))
        self.assertTrue(manifest["corpus_id"] and manifest["subset_id"])
        self.assertTrue(all(e["fixture_digest"] for e in manifest["fixtures"]))

    def test_an_explicit_subset_must_exist_in_the_corpus(self):
        spec = exp.load_spec()
        spec["subset"] = {**spec["subset"], "case_ids": ["no-such-case"]}
        with self.assertRaises(RoutineExecutionError):
            exp.select_subset(spec, str(exp.rb.DEFAULT_CORPUS_DIR))

    def test_arms_are_bounded_to_the_allowed_worker_counts(self):
        self.assertEqual(exp.parse_arms("1,2,4", [1, 2, 4]), [1, 2, 4])
        for bad in ("3", "8", "0", "x", ""):
            with self.assertRaises(RoutineExecutionError, msg=bad):
                exp.parse_arms(bad, [1, 2, 4])


class ExecutionTest(unittest.TestCase):
    def _run(self, t: str, arms: str, extra: str = "") -> tuple[subprocess.CompletedProcess, dict, dict]:
        stub, spec, out = write_stub(Path(t), extra), small_spec(Path(t)), Path(t) / "out"
        proc = run_cli("--arms", arms, "--cli", str(stub), "--runtime-version", "v1", "--model-id", "m1", "--spec", str(spec), "--seal-dir", str(out))
        record = json.loads((out / exp.EXPERIMENT_FILE).read_text()) if (out / exp.EXPERIMENT_FILE).exists() else {}
        raw = json.loads((out / exp.RAW_FILE).read_text()) if (out / exp.RAW_FILE).exists() else {}
        return proc, record, raw

    def test_runs_each_arm_over_the_same_subset_and_records_diagnostics(self):
        with tempfile.TemporaryDirectory() as t:
            proc, record, raw = self._run(t, "1,2,4")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(record["status"], "complete")
        self.assertEqual([a["workers"] for a in record["arms"]], [1, 2, 4])
        ids = [f["case_id"] for f in record["manifest"]["fixtures"]]
        self.assertEqual(len(ids), 4)
        for arm in record["arms"]:
            self.assertEqual((arm["planned"], arm["completed"], arm["errors"], arm["timeouts"]), (4, 4, 0, 0))
            self.assertEqual([f["case_id"] for f in arm["fixtures"]], ids)
            self.assertLessEqual(len({f["worker"] for f in arm["fixtures"]}), arm["workers"])
            for key in ("wall_s", "rate_limit_hits", "contention", "fixture_seconds_sum"):
                self.assertIn(key, arm)
            for fixture in arm["fixtures"]:
                self.assertIsNotNone(fixture["probe_s"])
                self.assertIsNotNone(fixture["review_s"])
        self.assertEqual(sorted(raw["2"]), sorted(ids))
        self.assertEqual(record["runtime"]["model_id"], "m1")
        self.assertEqual(record["runtime"]["runtime_version"], "v1")
        self.assertEqual(len(record["provenance"]["repo_sha"]), 40)
        self.assertFalse(record["diagnostics"]["tokens"]["available"])
        self.assertTrue(record["temporary"])
        self.assertTrue(record["ref"].startswith(exp.TRIAL_REF_PREFIX))
        self.assertTrue(record["isolation"]["passed"])

    def test_four_workers_use_four_distinct_scratch_slots(self):
        with tempfile.TemporaryDirectory() as t:
            _, record, _ = self._run(t, "4", extra="time.sleep(0.5)\n")
        slots = {f["worker"] for f in record["arms"][0]["fixtures"]}
        self.assertEqual(slots, {0, 1, 2, 3})

    def test_a_workspace_left_behind_is_an_isolation_violation_that_fails_the_run(self):
        with tempfile.TemporaryDirectory() as t:
            leaker = "import os, tempfile\nopen(os.path.join(tempfile.gettempdir(), 'leak-' + str(os.getpid())), 'w').close()\n"
            proc, record, _ = self._run(t, "2", extra=leaker)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(record["status"], "incomplete")
        self.assertIn("isolation", record["failure_classes"])
        self.assertIn("workspace-not-cleaned", {v["kind"] for v in record["isolation"]["violations"]})

    def test_two_children_cannot_share_a_slot(self):
        barrier = threading.Barrier(2, timeout=5)

        def gated(fixture, **kwargs):
            barrier.wait()  # both children are running at once, so a repeated slot is a real overlap
            return workers.FixtureOutcome(fixture.case_id, kwargs["worker"], 0.0, 0.0, 0, "ok")

        with tempfile.TemporaryDirectory() as t, mock.patch.object(workers, "run_fixture_child", side_effect=gated), mock.patch.object(
            workers.queue, "Queue"
        ) as pool:
            pool.return_value.get.return_value = 0  # a broken pool handing slot 0 to both tasks
            arm = workers.run_arm(
                2, [workers.Fixture(f"c{i}", t) for i in range(2)], executable="x", timeout=1, scratch_root=Path(t),
                log=lambda m: None, cancel=threading.Event(), children=workers.LiveChildren(),
            )
        self.assertIn("slot-shared", {v.kind for v in arm.violations})
        self.assertFalse(arm.complete)

    def test_a_child_that_ran_the_wrong_case_is_flagged(self):
        audit = exp.isolation_audit(
            [workers.ArmResult(1, 2, 0.0, [workers.FixtureOutcome("a", 0, 0.0, 0.0, 0, "ok")])],
            [workers.Fixture("a", "d"), workers.Fixture("b", "d")],
            repo_before=1, repo_after=1, config_before={}, config_after={}, strays=[], cli_before={}, cli_after={},
        )
        self.assertFalse(audit["passed"])
        self.assertEqual(audit["violations"][0]["kind"], "coverage")

    def test_source_repo_config_and_stray_temp_mutations_are_violations(self):
        audit = exp.isolation_audit(
            [], [], repo_before=1, repo_after=2, config_before={"g": "a"}, config_after={"g": "b"}, strays=["benchmark-x"],
            cli_before={}, cli_after={},
        )
        self.assertEqual({v["kind"] for v in audit["violations"]}, {"source-repo-mutated", "git-config-mutated", "shared-temp-workspace"})


class FailureTest(unittest.TestCase):
    def _run(self, t: str, extra: str) -> tuple[subprocess.CompletedProcess, dict, dict]:
        return ExecutionTest()._run(t, "1,2", extra)

    def test_a_crashing_review_cli_is_not_retried_and_keeps_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            counter = Path(t) / "calls"
            proc, record, raw = self._run(
                t, f"if 'local-code-review' in prompt:\n    open({str(counter)!r}, 'a').write('x')\n    sys.exit(3)\n"
            )
            calls = len(counter.read_text())
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(record["status"], "incomplete")
        self.assertEqual(calls, 4 * 2)  # one review attempt per fixture per arm; nothing re-run
        arm = record["arms"][0]
        self.assertEqual((arm["completed"], arm["errors"]), (0, 4))
        self.assertEqual({f["adapter_category"] for f in arm["fixtures"]}, {"cli-exit-3"})
        self.assertTrue(all(c["stderr_tail"] for c in raw["1"].values()))
        self.assertIn("benchmark", record["failure_classes"])

    def test_rate_limit_and_timeout_evidence_patterns(self):
        for text in ("HTTP 429", "Rate limit reached", "rate_limit_error", "API overloaded", "throttled", "Too Many Requests"):
            self.assertTrue(workers.RATE_LIMIT_RE.search(text), text)
        self.assertFalse(workers.RATE_LIMIT_RE.search("[case 1/1] DONE x 1.2s findings=0"))
        self.assertEqual(workers.CATEGORY_RE.findall("ERROR a 1s stage=review category=timeout"), ["timeout"])

    def test_an_unavailable_runtime_is_an_infrastructure_failure(self):
        with tempfile.TemporaryDirectory() as t:
            spec, out = small_spec(Path(t)), Path(t) / "out"
            proc = run_cli("--arms", "1", "--cli", "no-such-review-cli-xyz", "--runtime-version", "v", "--spec", str(spec), "--seal-dir", str(out))
            record = json.loads((out / exp.EXPERIMENT_FILE).read_text())
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(record["status"], "incomplete")
        self.assertEqual(record["failure_classes"], ["infrastructure"])

    def test_an_unexpected_worker_fault_still_seals_the_partial_evidence(self):
        real = workers.run_fixture_child
        seen = []

        def flaky(fixture, **kwargs):
            seen.append(fixture.case_id)
            if len(seen) == 3:
                raise OSError("fork failed")
            return real(fixture, **kwargs)

        with tempfile.TemporaryDirectory() as t, mock.patch.object(workers, "run_fixture_child", side_effect=flaky):
            stub, spec, out = write_stub(Path(t)), small_spec(Path(t)), Path(t) / "out"
            code = exp.main(["--arms", "1,2", "--cli", str(stub), "--runtime-version", "v1", "--spec", str(spec), "--seal-dir", str(out)])
            record = json.loads((out / exp.EXPERIMENT_FILE).read_text())
        self.assertNotEqual(code, 0)
        self.assertEqual(record["status"], "aborted")
        self.assertEqual(record["abort"]["error"], "OSError")
        self.assertIn("infrastructure", record["failure_classes"])
        self.assertEqual([a["workers"] for a in record["arms"]], [1])  # the second arm never started
        self.assertEqual(record["arms"][0]["completed"], 2)  # what finished before the fault is kept
        faulted = [f for f in record["arms"][0]["fixtures"] if f["status"] == "failed"]
        self.assertEqual(len(faulted), 1)
        self.assertEqual(faulted[0]["failure_class"], "infrastructure")
        self.assertIn("OSError", faulted[0]["failure_reason"])
        self.assertEqual(faulted[0]["case_id"], seen[2])
        self.assertEqual(record["arms"][0]["status"], "incomplete")
        self.assertNotIn("coverage", {v["kind"] for v in record["isolation"]["violations"]})

    def test_a_signal_before_any_arm_starts_still_seals(self):
        with tempfile.TemporaryDirectory() as t:
            stub, spec, out = write_stub(Path(t)), small_spec(Path(t)), Path(t) / "out"
            terminated = exp.Terminated(15, "init")
            with mock.patch.object(exp, "ArmResult", side_effect=terminated):
                code = exp.main(["--arms", "1", "--cli", str(stub), "--runtime-version", "v1", "--spec", str(spec), "--seal-dir", str(out)])
            record = json.loads((out / exp.EXPERIMENT_FILE).read_text())
        self.assertEqual((code, record["status"], record["arms"]), (143, "terminated", []))

    def test_termination_stops_children_and_seals_partial_evidence_as_terminated(self):
        with tempfile.TemporaryDirectory() as t:
            stub, spec, out = write_stub(Path(t), "time.sleep(60)\n"), small_spec(Path(t)), Path(t) / "out"
            proc = subprocess.Popen(
                [sys.executable, str(SCRIPT), "--arms", "2", "--cli", str(stub), "--runtime-version", "v", "--spec", str(spec), "--seal-dir", str(out)],
                stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=str(exp.REPO_ROOT),
            )
            for line in proc.stderr:
                if "stage=review START" in line or "[w1] START" in line:
                    break
            proc.terminate()
            proc.communicate(timeout=60)
            record = json.loads((out / exp.EXPERIMENT_FILE).read_text())
        self.assertEqual(proc.returncode, 143)
        self.assertEqual(record["status"], "terminated")


if __name__ == "__main__":
    unittest.main()
