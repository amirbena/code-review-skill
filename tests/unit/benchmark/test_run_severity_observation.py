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
SCRIPT = Path(obs.__file__)


def _invocation(**case_kwargs) -> lane_run.Invocation:
    case = make_case(CASE, matched=1, exact=1, **case_kwargs)
    return lane_run.Invocation({"passed": True}, run_output([case]), 3.0)


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
            obs, "_git_sha", return_value="b" * 40
        ), mock.patch.object(obs, "seal") as sealed:
            sealed.encode_json = seal.encode_json
            sealed.seal_to_directory = seal.seal_to_directory
            self.assertEqual(obs.main(_args(Path(t))), 0)
            self.assertFalse(sealed.seal_to_ref.called)
            self.assertEqual({p.name for p in Path(t).iterdir()}, {obs.OBSERVATION_FILE, obs.RAW_FILE})

    def test_push_targets_only_observation_ref(self):
        with mock.patch.object(obs, "invoke", return_value=_invocation()), mock.patch.object(obs, "_git_sha", return_value="b" * 40), mock.patch.object(
            obs, "prior_observation_count", return_value=0
        ), mock.patch.object(obs.seal, "seal_to_ref", return_value="c" * 40) as push:
            self.assertEqual(obs.main(["--cli", "fake", "--runtime-version", "v1"]), 0)
        ref = push.call_args.args[2]
        self.assertTrue(ref.startswith(obs.OBSERVATION_REF_PREFIX))
        self.assertEqual(set(push.call_args.args[3]), {obs.OBSERVATION_FILE, obs.RAW_FILE})


class EvidenceTest(unittest.TestCase):
    def test_observation_has_required_fields_and_is_addressable_by_run_id(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(obs, "invoke", return_value=_invocation()), mock.patch.object(
            obs, "_git_sha", return_value="b" * 40
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

    def test_mismatch_and_not_produced_states(self):
        out = run_output([make_case(CASE, matched=1, exact=0)])
        out["severity"]["cases"][0]["mismatches"] = [{"key": "k", "produced": "P2", "expected": ["P1"], "direction": "under"}]
        corpus = str(obs.rb.DEFAULT_CORPUS_DIR)
        self.assertEqual(obs.resolved_severity(CASE, out, corpus)["severity"], "P2")
        none = run_output([make_case(CASE)])
        self.assertEqual(obs.resolved_severity(CASE, none, corpus)["state"], "not-produced")

    def test_stop_condition_runs_nothing(self):
        with mock.patch.object(obs, "prior_observation_count", return_value=14), mock.patch.object(obs, "invoke") as inv:
            self.assertEqual(obs.main(["--cli", "fake"]), 0)
        inv.assert_not_called()

    def test_spec_marks_temporary_with_stop_and_removal(self):
        spec = obs.load_spec()
        self.assertTrue(spec["temporary"])
        self.assertEqual(spec["case_id"], CASE)
        self.assertEqual(spec["stop_condition"]["target_observations"], 14)
        self.assertTrue(spec["removal_path"])
        self.assertTrue((obs.REPO_ROOT / "benchmark" / "corpus" / f"{CASE}.yaml").exists())


if __name__ == "__main__":
    unittest.main()
