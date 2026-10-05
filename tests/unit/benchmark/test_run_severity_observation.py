"""Isolation and evidence-format guarantees of the temporary severity observation (Issue #652)."""

from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_lane_run as lane_run
from runtime_platform.benchmark.scripts import benchmark_schedule_manifest as manifest_mod
from runtime_platform.benchmark.scripts import benchmark_seal as seal
from runtime_platform.benchmark.scripts import run_severity_observation as obs
from tests.support.benchmark_records import make_case, run_output

CASE = "correctness-off-by-one-pagination"
KEY = "page-end-off-by-one"
SCRIPT = Path(obs.__file__)


def _invocation(**case_kwargs) -> lane_run.Invocation:
    case = make_case(CASE, matched=1, exact=1, **case_kwargs)
    output = run_output([case])
    output["run"]["cases"][0]["produced_findings"] = [{"severity": "P1"}]
    return lane_run.Invocation({"passed": True}, output, 3.0)


def _args(tmp: Path) -> list[str]:
    return ["--seal-dir", str(tmp), "--cli", "fake", "--runtime-version", "v1", "--model-id", "m1", "--trigger", "scheduled"]


class IsolationTest(unittest.TestCase):
    def test_not_in_manifest_lanes_and_prefix_is_outside_staging_pattern(self):
        manifest = manifest_mod.load_manifest(manifest_mod.MANIFEST_PATH)
        self.assertNotIn(CASE, manifest["lanes"])
        self.assertNotIn("severity-observation", manifest["lanes"])
        self.assertFalse(obs.OBSERVATION_REF_PREFIX.startswith(seal.STAGING_REF_PREFIX))
        self.assertFalse(obs.observation_ref("x").startswith("claude/benchmark-result-"))

    def test_no_publication_baseline_or_github_code_path(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = {
            n.module if isinstance(n, ast.ImportFrom) else a.name
            for n in ast.walk(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom))
            for a in (n.names if isinstance(n, ast.Import) else [None])
        }
        for forbidden in ("publish_benchmark", "benchmark_baseline", "benchmark_drift", "benchmark_history", "benchmark_result"):
            self.assertFalse([m for m in imported if m and forbidden in m], forbidden)
        source = SCRIPT.read_text(encoding="utf-8")
        for token in ('"gh"', "api.github.com", "GH_TOKEN", "GITHUB_TOKEN"):
            self.assertNotIn(token, source)

    def test_dry_run_writes_only_observation_files(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(obs, "invoke", return_value=_invocation()), mock.patch.object(
            obs, "git_sha", return_value="b" * 40
        ), mock.patch.object(obs, "seal") as sealed:
            sealed.encode_json = seal.encode_json
            sealed.seal_to_directory = seal.seal_to_directory
            self.assertEqual(obs.main(_args(Path(t))), 0)
            self.assertFalse(sealed.seal_to_ref.called)
            self.assertEqual({p.name for p in Path(t).iterdir()}, {obs.OBSERVATION_FILE, obs.RAW_FILE})

    def test_push_targets_only_observation_ref(self):
        with mock.patch.object(obs, "invoke", return_value=_invocation()), mock.patch.object(obs, "git_sha", return_value="b" * 40), mock.patch.object(
            obs, "prior_observation_refs", return_value=[]
        ), mock.patch.object(obs.seal, "seal_to_ref", return_value="c" * 40) as push:
            self.assertEqual(obs.main(["--cli", "fake", "--runtime-version", "v1", "--trigger", "scheduled"]), 0)
        ref = push.call_args.args[2]
        self.assertTrue(ref.startswith(obs.OBSERVATION_REF_PREFIX))
        self.assertEqual(set(push.call_args.args[3]), {obs.OBSERVATION_FILE, obs.RAW_FILE})

    def test_every_process_and_push_is_confined_end_to_end(self):
        """Run `main` with only `invoke` faked: every subprocess is plain git, and the only push is the observation ref."""
        calls: list[list[str]] = []

        def recorder(argv, **kwargs):
            calls.append([str(a) for a in argv])
            out = {"hash-object": "a" * 40, "mktree": "b" * 40, "commit-tree": "c" * 40, "rev-parse": "d" * 40}.get(argv[1], "")
            if argv[1] == "ls-remote" and argv[3].startswith("refs/heads/claude/severity-observation-") is False:
                out = f"{'c' * 40}\t{argv[3]}\n"
            return mock.Mock(returncode=0, stdout=out.encode() if kwargs.get("input") is not None or not kwargs.get("text") else out, stderr=b"")

        with mock.patch.object(obs, "invoke", return_value=_invocation()), mock.patch("subprocess.run", side_effect=recorder):
            obs.main(["--cli", "fake", "--runtime-version", "v1", "--trigger", "scheduled"])
        self.assertTrue(calls and all(c[0] == "git" for c in calls), calls)
        pushes = [c for c in calls if c[1] == "push"]
        self.assertEqual(len(pushes), 1)
        self.assertTrue(pushes[0][3].split(":", 1)[1].startswith(f"refs/heads/{obs.OBSERVATION_REF_PREFIX}"))
        for forbidden in ("gh", "issue", "comment", "benchmark-history", "benchmark-result"):
            self.assertFalse([c for c in calls if forbidden in " ".join(c)], forbidden)

    def test_non_scheduled_run_pushes_an_uncounted_trial_ref_and_skips_the_count(self):
        with mock.patch.object(obs, "invoke", return_value=_invocation()), mock.patch.object(obs, "git_sha", return_value="b" * 40), mock.patch.object(
            obs, "prior_observation_refs"
        ) as listing, mock.patch.object(obs.seal, "seal_to_ref", return_value="c" * 40) as push:
            obs.main(["--cli", "fake", "--runtime-version", "v1"])
        listing.assert_not_called()
        ref = push.call_args.args[2]
        self.assertTrue(ref.startswith(obs.TRIAL_REF_PREFIX))
        self.assertFalse(ref.startswith(obs.OBSERVATION_REF_PREFIX))

    def test_skip_reason_covers_target_and_same_day(self):
        pre = obs.OBSERVATION_REF_PREFIX
        self.assertEqual(obs.skip_reason([f"{pre}2026100{i}T010000Z-x" for i in range(1, 10)] + [f"{pre}2026101{i}T010000Z-x" for i in range(5)], 14, "20261101"), "stop-condition-reached")
        self.assertEqual(obs.skip_reason([f"{pre}20261005T050000Z-x"], 14, "20261005"), "already-observed-today")
        self.assertIsNone(obs.skip_reason([f"{pre}20261004T050000Z-x"], 14, "20261005"))


class EvidenceTest(unittest.TestCase):
    def test_observation_has_required_fields_and_is_addressable_by_run_id(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(obs, "invoke", return_value=_invocation()), mock.patch.object(
            obs, "git_sha", return_value="b" * 40
        ):
            obs.main(_args(Path(t)))
            record = json.loads((Path(t) / obs.OBSERVATION_FILE).read_text())
        self.assertEqual(record["schema"], obs.OBSERVATION_SCHEMA)
        self.assertTrue(record["temporary"])
        self.assertEqual(record["resolved"]["severity"], "P1")
        self.assertEqual(record["runtime"]["model_id"], "m1")
        self.assertEqual(record["runtime"]["runtime_version"], "v1")
        self.assertEqual(record["provenance"]["repo_sha"], "b" * 40)
        self.assertEqual(record["ref"], obs.observation_ref(record["run_id"]))
        for section in ("metrics", "severity", "duplicate_noise"):
            self.assertEqual(record["evidence"][section]["id"], CASE)
        self.assertTrue(record["started_at"] and record["finished_at"])

    def _resolve(self, produced, *, missed=(), mismatch=None, matched=1):
        out = run_output([make_case(CASE, missed=missed, matched=matched, exact=0 if mismatch else matched)])
        out["run"]["cases"][0]["produced_findings"] = [{"severity": s} for s in produced]
        if mismatch:
            out["severity"]["cases"][0]["mismatches"] = [{"key": KEY, "produced": mismatch[0], "expected": ["P1"], "direction": mismatch[1]}]
        return obs.resolved_severity(CASE, out, str(obs.rb.DEFAULT_CORPUS_DIR))

    def test_recorded_severity_is_the_produced_severity(self):
        exact = self._resolve(["P1"])
        self.assertEqual((exact["severity"], exact["state"]), ("P1", "exact"))
        over = self._resolve(["P0"], mismatch=("P0", "over"))
        self.assertEqual((over["severity"], over["state"]), ("P0", "over"))
        under = self._resolve(["P2"], mismatch=("P2", "under"))
        self.assertEqual((under["severity"], under["state"]), ("P2", "under"))
        missing = self._resolve([], missed=[KEY], matched=0)
        self.assertEqual((missing["severity"], missing["state"]), (None, "not-produced"))

    def test_optional_only_match_is_not_reported_as_the_required_severity(self):
        # matched == 1 can be the optional entry alone; the required finding is still missed.
        result = self._resolve(["P2"], missed=[KEY], matched=1)
        self.assertEqual((result["severity"], result["state"]), (None, "not-produced"))

    def test_exact_invariant_is_cross_checked_against_raw_output(self):
        with self.assertRaises(lane_run.RoutineExecutionError):
            self._resolve(["P2"])  # claims exact P1 but the raw run produced only P2

    def test_stop_condition_runs_nothing(self):
        refs = [f"{obs.OBSERVATION_REF_PREFIX}202610{d:02d}T050000Z-x" for d in range(1, 15)]
        with mock.patch.object(obs, "prior_observation_refs", return_value=refs), mock.patch.object(obs, "invoke") as inv:
            self.assertEqual(obs.main(["--cli", "fake", "--trigger", "scheduled"]), 0)
        inv.assert_not_called()

    def test_failures_are_reported_as_errors_not_tracebacks(self):
        import subprocess

        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 1)):
            self.assertEqual(obs.main(["--cli", "fake", "--trigger", "scheduled"]), 1)
        out = run_output([make_case(CASE)])
        out["run"]["cases"] = []
        with self.assertRaises(lane_run.RoutineExecutionError):
            obs.resolved_severity(CASE, out, str(obs.rb.DEFAULT_CORPUS_DIR))

    def test_spec_marks_temporary_with_stop_and_removal(self):
        spec = obs.load_spec()
        self.assertTrue(spec["temporary"])
        self.assertEqual(spec["case_id"], CASE)
        self.assertEqual(spec["stop_condition"]["target_observations"], 14)
        self.assertTrue(spec["removal_path"])
        self.assertTrue((obs.REPO_ROOT / "benchmark" / "corpus" / f"{CASE}.yaml").exists())


if __name__ == "__main__":
    unittest.main()
