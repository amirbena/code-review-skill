"""The compatibility and validation gate for private evidence publication (#689).

Validates the #688 destination contract against stub bare repositories only: no network,
no model, no real private repository. Each test names the ADR invariant it checks; the
gate checklist (`private-evidence-validation-gate.md`) maps every scenario to its test.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.publisher import cli as publisher_cli
from runtime_platform.benchmark.scripts import benchmark_evidence_destination as ed
from runtime_platform.benchmark.scripts import benchmark_lane_run as lane_run
from runtime_platform.benchmark.scripts import benchmark_result as res
from runtime_platform.benchmark.scripts import benchmark_schedule_manifest as sm
from runtime_platform.benchmark.scripts import benchmark_seal as seal
from runtime_platform.benchmark.scripts import run_benchmark_routine as routine
from runtime_platform.benchmark.scripts import run_concurrency_experiment as exp
from runtime_platform.benchmark.scripts import run_severity_observation as obs
from runtime_platform.benchmark.scripts.benchmark_termination import Terminated
from tests.support.benchmark_publisher_fakes import SLUG, World, make_record
from tests.support.benchmark_records import make_case, run_output
from tests.support.evidence_destination import EVIDENCE, NAMESPACES, SOURCE, evidence_block, manifest_with
from tests.support.paths import REPO_ROOT
from tests.unit.benchmark.test_benchmark_evidence_destination import FILES, HANDOFF, Stores, _git
from tests.unit.benchmark.test_benchmark_publisher_github_api import ScriptedOpener
from tests.unit.benchmark.test_run_concurrency_experiment import small_spec, write_stub

SNAPSHOT = REPO_ROOT / "tests" / "support" / "pre_688_sentinel_record.json"
TOKENS = {"BENCHMARK_CONTENTS_TOKEN": "ghs_c", "BENCHMARK_ISSUES_TOKEN": "ghs_i", "BENCHMARK_READ_TOKEN": "ghs_r"}
NOW = "2026-09-20T01:00:00Z"


class GateStores(Stores):
    def setUp(self) -> None:
        super().setUp()
        self.tmp = Path(self._tmp.name)

    def private_dest(self) -> ed.Destination:
        return self.resolve("private", remote=str(self.private))

    def manifest_path(self, phase: str = "private") -> str:
        path = self.tmp / f"manifest-{phase}.json"
        path.write_text(json.dumps(manifest_with(phase)), encoding="utf-8")
        return str(path)

    def reject_pushes(self, bare: Path, message: str) -> None:
        hook = bare / "hooks" / "pre-receive"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text(f"#!/bin/sh\necho 'remote: {message}' >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

    def run_main(self, module, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "REPO_ROOT", self.work), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = module.main(argv)
        return code, out.getvalue(), err.getvalue()

    def assert_nothing_written(self) -> None:
        self.assertEqual(self.refs(self.public), [])
        self.assertEqual(self.refs(self.private), [])


class PrivatePublicationTests(GateStores):
    def test_private_reads_and_ref_discovery_see_only_the_private_store(self) -> None:
        dest = self.private_dest()
        decoy = ed.Destination(**{**dest.__dict__, "remote": str(self.public), "repository": SOURCE, "phase": "pre_cutover"})
        decoy.seal(f"{obs.OBSERVATION_REF_PREFIX}20261001T010000Z-aaaaaaaaaaaa", FILES, "decoy")
        for day in ("20261002", "20261003"):
            dest.seal(f"{obs.OBSERVATION_REF_PREFIX}{day}T010000Z-bbbbbbbbbbbb", FILES, day)
        found = dest.list_refs(obs.OBSERVATION_REF_PREFIX)
        self.assertEqual(sorted(found), [f"{obs.OBSERVATION_REF_PREFIX}{d}T010000Z-bbbbbbbbbbbb" for d in ("20261002", "20261003")])

    def test_f7_the_severity_stop_condition_counts_the_private_store_only(self) -> None:
        dest = self.private_dest()
        public = ed.Destination(**{**dest.__dict__, "remote": str(self.public), "repository": SOURCE, "phase": "pre_cutover"})
        public.seal(f"{obs.OBSERVATION_REF_PREFIX}20261001T010000Z-aaaaaaaaaaaa", FILES, "x")
        target = 1
        self.assertIsNone(obs.skip_reason(obs.prior_observation_refs(dest), target, "20261001"))  # a decoy on origin never counts
        dest.seal(f"{obs.OBSERVATION_REF_PREFIX}20261001T020000Z-cccccccccccc", FILES, "y")
        self.assertEqual(obs.skip_reason(obs.prior_observation_refs(dest), target, "20261001"), "stop-condition-reached")

    def test_f7_the_experiment_stop_condition_counts_the_private_store_only(self) -> None:
        spec = exp.load_spec()
        limit = spec["stop_condition"]["max_experiments"]
        dest = self.private_dest()
        public = ed.Destination(**{**dest.__dict__, "remote": str(self.public), "repository": SOURCE, "phase": "pre_cutover"})
        for i in range(limit):
            public.seal(exp.experiment_ref(exp.make_run_id(f"2026-10-0{i + 1}T01:00:00Z", "a" * 40)), FILES, "x")
        self.assertNotEqual(exp.skip_reason(spec, exp.prior_experiment_refs(dest), "2020-01-01", "2020-01-01"), "stop-condition-reached")
        for i in range(limit):
            dest.seal(exp.experiment_ref(exp.make_run_id(f"2026-10-1{i}T01:00:00Z", "b" * 40)), FILES, "y")
        self.assertEqual(exp.skip_reason(spec, exp.prior_experiment_refs(dest), "2020-01-01", "2020-01-01"), "stop-condition-reached")

    def test_duplicate_run_prevention_end_to_end_skips_on_a_private_observation(self) -> None:
        dest = self.private_dest()
        dest.seal(f"{obs.OBSERVATION_REF_PREFIX}20261011T000500Z-aaaaaaaaaaaa", FILES, "today")
        before = self.refs(self.private)
        with mock.patch.object(obs, "utc_now", return_value="2026-10-11T01:00:00Z"):
            code, out, _ = self.run_main(obs, ["--manifest", self.manifest_path(), "--trigger", "scheduled", "--cli", "unused", "--evidence-remote", str(self.private)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["skipped"], "already-observed-today")
        self.assertEqual(self.refs(self.private), before)
        self.assertEqual(self.refs(self.public), [])

    def test_i1_a_retry_of_a_sealed_ref_is_refused_and_the_first_seal_stays_intact(self) -> None:
        dest = self.private_dest()
        first = dest.seal(HANDOFF, FILES, "first")
        with self.assertRaises(ed.StoreUnavailable) as ctx:
            dest.seal(HANDOFF, {seal.HANDOFF_CHECK_FILE: b'{"x": 2}\n'}, "retry")
        self.assertEqual(ctx.exception.error_class, "rejected")
        self.assertEqual(_git(self.private, "rev-parse", f"refs/heads/{HANDOFF}"), first)
        self.assertEqual(self.refs(self.public), [])

    def test_f4a_an_unconfirmed_push_leaves_one_ref_in_the_private_store_and_a_retry_cannot_double_it(self) -> None:
        dest = self.private_dest()
        real = seal._git

        def fail_readback(repo_root, *args, **kw):
            if args and args[0] == "ls-remote":
                raise seal.SealError("git ls-remote failed: connection reset")
            return real(repo_root, *args, **kw)

        with mock.patch.object(seal, "_git", side_effect=fail_readback):
            with self.assertRaises(ed.StoreUnavailable) as ctx:
                dest.seal(HANDOFF, FILES, "x")
        self.assertEqual(ctx.exception.status, ed.STATUS_UNCONFIRMED)
        self.assertNotIn(str(self.private), str(ctx.exception))  # the unconfirmed branch redacts the remote too
        self.assertEqual(self.refs(self.private), [f"refs/heads/{HANDOFF}"])
        self.assertEqual(self.refs(self.public), [])
        with self.assertRaises(ed.StoreUnavailable):
            dest.seal(HANDOFF, FILES, "retry")
        self.assertEqual(self.refs(self.private), [f"refs/heads/{HANDOFF}"])

    def test_i4_copying_a_ref_between_stores_preserves_the_commit_and_its_content_hash(self) -> None:
        source = ed.Destination(**{**self.private_dest().__dict__, "remote": str(self.public), "repository": SOURCE, "phase": "pre_cutover"})
        ref = f"{seal.STAGING_REF_PREFIX}sentinel-20261010T010000Z-aaaaaaaaaaaa"
        sha = source.seal(ref, {seal.RECORD_FILE: b'{"k": 1}\n'}, "record")
        _git(self.work, "push", "-q", str(self.private), f"{sha}:refs/heads/{ref}")
        self.assertEqual(_git(self.private, "rev-parse", f"refs/heads/{ref}"), sha)
        shown = lambda bare: subprocess.run(["git", "show", f"{sha}:{seal.RECORD_FILE}"], cwd=str(bare), capture_output=True).stdout  # noqa: E731
        self.assertEqual(res.sha256_hex(shown(self.public).decode()), res.sha256_hex(shown(self.private).decode()))


class FailureModeTests(GateStores):
    def test_permission_failure_is_classified_unauthorized_and_leaves_no_ref(self) -> None:
        self.reject_pushes(self.private, "Permission denied to the evidence deploy key")
        with self.assertRaises(ed.StoreUnavailable) as ctx:
            self.private_dest().seal(HANDOFF, FILES, "x")
        self.assertEqual((ctx.exception.status, ctx.exception.error_class), (ed.STATUS_UNAVAILABLE, "unauthorized"))
        self.assert_nothing_written()

    def test_f4_a_rejected_push_keeps_the_would_be_files_locally_and_exits_3(self) -> None:
        self.reject_pushes(self.private, "protected branch hook declined")
        files = {"raw-bundle.json": b"[]\n", seal.RECORD_FILE: b'{"run": 1}\n'}
        err_out, out = io.StringIO(), io.StringIO()
        with self.assertRaises(ed.StoreUnavailable) as ctx:
            self.private_dest().seal(HANDOFF, files, "x")
        with mock.patch("tempfile.gettempdir", return_value=str(self.tmp)), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err_out):
            code = ed.exit_for(ctx.exception, run_id="r1", destination=self.private_dest(), files=files, commit_file=seal.RECORD_FILE)
        status = json.loads(out.getvalue())
        self.assertEqual((code, status["status"], status["sealed"], status["destination"]), (3, ed.STATUS_UNAVAILABLE, False, EVIDENCE))
        kept = Path(status["diagnostics"])
        self.assertEqual({name: (kept / name).read_bytes() for name in files}, files)  # partial evidence preserved, byte for byte
        self.assertEqual(len(list(kept.glob("*.json"))), len(files))
        self.assertNotIn(str(self.private), out.getvalue() + err_out.getvalue())
        self.assert_nothing_written()

    def test_missing_credentials_fail_closed_as_unauthorized_without_echoing_the_url(self) -> None:
        url = f"https://github.com/{EVIDENCE}.git"
        dest = ed.Destination(repository=EVIDENCE, phase="private", remote=url, namespaces=NAMESPACES, history_branch="benchmark-history", repo_root=self.work)
        denied = subprocess.CompletedProcess([], 128, "", f"fatal: could not read Username for 'https://github.com': terminal prompts disabled\n")
        with mock.patch.object(ed.subprocess, "run", return_value=denied):
            with self.assertRaises(ed.StoreUnavailable) as ctx:
                dest.preflight()
        self.assertEqual(ctx.exception.error_class, "unauthorized")
        self.assertNotIn("github.com", str(ctx.exception))

    def test_the_remote_is_replaced_whole_and_before_truncation(self) -> None:
        url = f"https://github.com/{EVIDENCE}.git"
        dest = ed.Destination(repository=EVIDENCE, phase="private", remote=url, namespaces=NAMESPACES, history_branch="b", repo_root=self.work)
        scrubbed = dest._scrub("x " * 90 + f"git push {url} abc")
        self.assertNotIn("github.com", scrubbed)
        for message in (f"fatal: unable to access '{url}/': Could not resolve host", f"fatal: repository '{url}/info/refs' not found"):
            self.assertNotIn("github.com", dest._scrub(message), message)  # git quotes the URL with a path suffix
        named = ed.Destination(repository=EVIDENCE, phase="private", remote="evidence", namespaces=NAMESPACES, history_branch="b", repo_root=self.work)
        self.assertEqual(named._scrub("evidence-store evidence"), f"evidence-store {EVIDENCE}")

    def test_a_missing_private_repository_is_not_found_not_empty(self) -> None:
        self.assertEqual(ed.classify_git_error("remote: Repository not found.\nfatal: repository 'https://github.com/x/y.git/' not found"), "not-found")

    def test_wrong_remote_configuration_exits_2_for_every_entrypoint_and_writes_nothing(self) -> None:
        other = self.tmp / "amirbena" / "unrelated-evidence.git"
        other.parent.mkdir(exist_ok=True)
        _git(self.tmp, "init", "--bare", "-q", str(other))
        _git(self.work, "remote", "add", "evidence", str(other))
        manifest = self.manifest_path()
        for remote in (str(other), "evidence", "origin", str(self.public)):
            for module, extra in (
                (routine, ["--mode", "auth-check"]),
                (obs, ["--trigger", "scheduled", "--cli", "unused"]),
                (exp, ["--trigger", "scheduled", "--cli", "unused"]),
            ):
                with self.subTest(remote=remote, entrypoint=module.__name__):
                    code, _, err = self.run_main(module, ["--manifest", manifest, *extra, "--evidence-remote", remote])
                    self.assertEqual(code, ed.EXIT_MISCONFIGURED, err)
                    self.assertIn(ed.STATUS_MISCONFIGURED, err)
        self.assertEqual(self.refs(self.public) + self.refs(self.private) + self.refs(other), [])

    def test_an_unavailable_private_store_never_falls_back_to_the_populated_public_origin(self) -> None:
        self.resolve("pre_cutover").seal(HANDOFF, FILES, "preexisting")
        before = self.refs(self.public)
        self.private.rename(self.private.with_name("moved.git"))
        manifest = self.manifest_path()
        for module, extra in (
            (routine, ["--mode", "auth-check"]),
            (obs, ["--trigger", "scheduled", "--cli", "unused"]),
            (exp, ["--trigger", "scheduled", "--cli", "unused"]),
        ):
            with self.subTest(entrypoint=module.__name__):
                code, out, _ = self.run_main(module, ["--manifest", manifest, *extra, "--evidence-remote", str(self.private)])
                self.assertEqual(code, ed.EXIT_UNAVAILABLE)
                self.assertEqual(json.loads(out)["status"], ed.STATUS_UNAVAILABLE)
                self.assertEqual(self.refs(self.public), before)

    def test_a_terminated_run_against_a_private_destination_seals_nothing_and_writes_no_results(self) -> None:
        results = self.tmp / "results.json"
        argv = ["--mode", "sentinel", "--cli", "stub", "--runtime-version", "v", "--results-out", str(results), "--evidence-remote", str(self.private), "--manifest", self.manifest_path()]
        inv = mock.Mock(output={"run": {}}, verification={}, timing=None)
        plan = routine.Plan("sentinel", [(None, str(self.tmp))], mock.Mock())
        with (
            mock.patch.object(routine, "_plan", return_value=plan),
            mock.patch.object(routine, "_load_manifest", return_value={}),
            mock.patch.object(routine, "_destination", return_value=self.private_dest()),
            mock.patch.object(routine, "_history_source", return_value=mock.Mock()),
            mock.patch.object(routine, "spec_sha256", return_value="x"),
            mock.patch.object(routine, "_git_sha", return_value="sha"),
            mock.patch.object(routine, "_git_ref", return_value="HEAD"),
            mock.patch.object(routine, "invoke", return_value=inv),
            mock.patch.object(routine, "build_sealed_run", side_effect=Terminated(15, "drift-confirmation", None)),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = routine.main(argv)
        self.assertNotEqual(code, 0)  # Issue #660: fail closed, never a success line
        self.assertFalse(results.exists())
        self.assert_nothing_written()


    def test_a_terminated_concurrency_experiment_seals_its_partial_evidence_to_the_private_store_only(self) -> None:
        stub, spec = write_stub(self.tmp), small_spec(self.tmp)
        argv = ["--arms", "1", "--cli", str(stub), "--runtime-version", "v", "--spec", str(spec), "--manifest", self.manifest_path(), "--evidence-remote", str(self.private)]
        with mock.patch.object(exp, "ArmResult", side_effect=exp.Terminated(15, "init")):
            code, _, _ = self.run_main(exp, argv)
        self.assertEqual(code, 143)
        self.assertEqual(self.refs(self.public), [])
        (ref,) = self.refs(self.private)
        self.assertTrue(ref.startswith(f"refs/heads/{exp.TRIAL_REF_PREFIX}"))
        record = json.loads(_git(self.private, "show", f"{ref}:{exp.EXPERIMENT_FILE}"))
        self.assertEqual(record["status"], "terminated")


class BenchmarkCompatibilityTests(GateStores):
    def sealed_record(self, manifest: str) -> dict:
        """One deterministic sentinel run sealed to a directory under the given manifest; the Routine and its runner are stubbed."""

        def runner(executable, timeout, case_id, corpus_dir):
            ids = [case_id] if case_id else sorted(p.stem for p in Path(corpus_dir).glob("*.yaml"))
            verification = {"passed": True, "reason": "verified", "case_count": len(ids), "case_ids": ids}
            return lane_run.Invocation(verification, run_output([make_case(c, missed=[]) for c in ids]), 2.0)

        seal_dir = self.tmp / f"sealed-{Path(manifest).stem}"
        with (
            mock.patch("time.monotonic", return_value=100.0),
            mock.patch.object(routine, "_git_sha", return_value="a" * 40),
            mock.patch.object(routine, "_git_ref", return_value="refs/heads/main"),
            mock.patch.object(routine, "utc_now", return_value=NOW),
            mock.patch.object(lane_run, "utc_now", side_effect=lambda: NOW),
            mock.patch.object(routine, "invoke", runner),
            mock.patch.object(lane_run, "invoke", runner),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = routine.main(["--cli", "stub", "--runtime-version", "cli-1", "--history-root", str(self.tmp / "no-history"), "--mode", "sentinel", "--manifest", manifest, "--seal-dir", str(seal_dir)])
        self.assertEqual(code, 0)
        return json.loads((seal_dir / seal.RECORD_FILE).read_text(encoding="utf-8"))

    @staticmethod
    def comparable(record: dict) -> dict:
        """Everything except the wall-clock stamps, the interpreter version and the two digests that cover the amended spec."""
        kept = {k: v for k, v in record.items() if k not in ("content_sha256", "finished_at", "sealed_at")}
        kept["provenance"] = {k: v for k, v in record["provenance"].items() if k != "spec_sha256"}
        for section in kept.values():
            if isinstance(section, dict):
                section.pop("python_version", None)  # the interpreter of the machine that ran the test
        return kept

    def test_unchanged_inputs_seal_a_record_identical_to_the_pre_688_snapshot(self) -> None:
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        for phase in ("pre_cutover", "private"):
            with self.subTest(phase=phase):
                self.assertEqual(self.comparable(self.sealed_record(self.manifest_path(phase))), snapshot)

    def test_p1_p2_provenance_names_the_source_in_both_phases_and_never_the_evidence_store(self) -> None:
        for phase in ("pre_cutover", "private"):
            record = self.sealed_record(self.manifest_path(phase))
            self.assertEqual(record["provenance"]["repo"], SOURCE)
            self.assertEqual(record["provenance"]["repo_sha"], "a" * 40)
            self.assertNotIn(EVIDENCE, json.dumps(record))

    def test_the_corpus_and_expected_baselines_do_not_go_through_the_evidence_destination(self) -> None:
        scripts = REPO_ROOT / "runtime_platform" / "benchmark" / "scripts"
        for name in ("benchmark_corpus_membership.py", "select_benchmark_cases.py", "build_benchmark_index.py", "benchmark_fixture.py"):
            path = scripts / name if (scripts / name).exists() else REPO_ROOT / "runtime_platform" / "benchmark" / "reference" / name
            if path.exists():
                self.assertNotIn("evidence_destination", path.read_text(encoding="utf-8"), name)
        self.assertTrue(next((REPO_ROOT / "benchmark" / "corpus").rglob("*.yaml"), None), "the corpus (fixtures and expected findings) stays in the public source repository")


class PublisherPrivateStoreTests(unittest.TestCase):
    def private_world(self) -> World:
        world = World()
        world.manifest["evidence"] = evidence_block("private")
        return world

    def test_sweep_and_watchdog_run_over_the_private_phase_manifest(self) -> None:
        world = self.private_world()
        world.seal(make_record())
        report = world.sweep()
        self.assertEqual([o.status for o in report.outcomes], ["published"])
        self.assertTrue(world.watchdog(sweep_succeeded=True).ok)

    def test_i2_publishing_the_same_run_again_is_a_no_op(self) -> None:
        world = self.private_world()
        record = make_record()
        world.seal(record)
        world.sweep()
        files, comments = dict(world.store.files), len(world.tracking_comments())
        world.seal(record)
        again = world.sweep()
        self.assertEqual([o.status for o in again.outcomes], ["already-published"])
        self.assertEqual((dict(world.store.files), len(world.tracking_comments())), (files, comments))

    def test_every_sweep_and_watchdog_request_targets_the_evidence_repository_and_none_writes_on_failure(self) -> None:
        manifest = self.private_world().manifest
        opener = ScriptedOpener({})
        ports = publisher_cli._real_ports(TOKENS, EVIDENCE)
        for port in (ports.reader, ports.store, ports.tracker):
            port._client._opener = opener
        from runtime_platform.benchmark.publisher.model import SweepConfig, WatchdogConfig
        from runtime_platform.benchmark.publisher.sweep import run_sweep
        from runtime_platform.benchmark.publisher.watchdog import run_watchdog

        with contextlib.suppress(Exception):
            run_sweep(ports, SweepConfig(manifest=manifest, identity=f"{SLUG}[bot]", run_url="https://example.invalid/run"))
        with contextlib.suppress(Exception):
            run_watchdog(ports, WatchdogConfig(manifest=manifest, identity=f"{SLUG}[bot]"))
        self.assertTrue(opener.requests)
        for method, path, *_ in opener.requests:
            self.assertTrue(path.startswith(f"/repos/{EVIDENCE}/"), path)  # never the public source repository (F6, R3)
            self.assertEqual(method, "GET", path)


if __name__ == "__main__":
    unittest.main()
