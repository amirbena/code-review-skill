"""The publisher addresses only `evidence.repository` and logs no evidence content (#688; F6, F11, F12)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.publisher import cli, github_api
from tests.support.benchmark_publisher_fakes import SLUG, World, make_record
from tests.support.evidence_destination import EVIDENCE, SOURCE, manifest_with
from tests.unit.benchmark.test_benchmark_publisher_github_api import ScriptedOpener

TOKENS = {"BENCHMARK_CONTENTS_TOKEN": "ghs_c", "BENCHMARK_ISSUES_TOKEN": "ghs_i", "BENCHMARK_READ_TOKEN": "ghs_r"}


def _run(argv: list[str], env: dict[str, str], ports=None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv, env=env, ports_factory=(lambda m, i: ports) if ports else None)
    return code, out.getvalue(), err.getvalue()


class _Manifest(unittest.TestCase):
    def write(self, phase: str, repository: str | None = None) -> str:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "manifest.json"
        path.write_text(json.dumps(manifest_with(phase, repository)), encoding="utf-8")
        return str(path)


class TargetRepositoryTests(_Manifest):
    def test_private_phase_builds_every_port_for_the_evidence_repository_only(self) -> None:
        seen: list[str] = []
        real = cli._real_ports

        def spy(env, repository, **kw):
            seen.append(repository)
            return real(env, repository, **kw)

        env = {**TOKENS, "BENCHMARK_APP_SLUG": SLUG, "GITHUB_REPOSITORY": SOURCE, "GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "9"}
        with mock.patch.object(cli, "_real_ports", side_effect=spy), mock.patch.object(cli, "_sweep", return_value=0):
            code, _, _ = _run(["sweep", "--manifest", self.write("private")], env)
        self.assertEqual((code, seen), (0, [EVIDENCE]))  # never GITHUB_REPOSITORY or the top-level repository

    def test_every_request_is_addressed_to_the_evidence_repository(self) -> None:
        opener = ScriptedOpener({})
        ports = cli._real_ports(TOKENS, EVIDENCE)
        for port in (ports.reader, ports.store, ports.tracker):
            port._client._opener = opener
        for call in (
            lambda: ports.reader.list_staging_refs("claude/benchmark-result-"),
            lambda: ports.store.head() if hasattr(ports.store, "head") else ports.store.read_text("baselines/sentinel.json"),
            lambda: ports.tracker.get_issue(1),
        ):
            with contextlib.suppress(Exception):
                call()
        self.assertTrue(opener.requests)
        for _, path, *_ in opener.requests:
            self.assertTrue(path.startswith(f"/repos/{EVIDENCE}/"), path)

    def test_an_unreachable_evidence_repository_fails_the_job_without_a_write(self) -> None:
        opener = ScriptedOpener({})  # every route 404s
        ports = cli._real_ports(TOKENS, EVIDENCE)
        for port in (ports.reader, ports.store, ports.tracker):
            port._client._opener = opener
        manifest = World().manifest
        manifest["evidence"] = manifest_with("private")["evidence"]
        from runtime_platform.benchmark.publisher.model import SweepConfig
        from runtime_platform.benchmark.publisher.sweep import run_sweep

        report = run_sweep(ports, SweepConfig(manifest=manifest, identity="x[bot]", run_url="https://example.invalid/run"))
        self.assertFalse(report.ok)
        self.assertEqual([m for m, *_ in opener.requests if m != "GET"], [])


class FailClosedTests(_Manifest):
    def test_invalid_evidence_blocks_exit_2_before_any_token_is_used(self) -> None:
        env = {**TOKENS, "BENCHMARK_APP_SLUG": SLUG, "GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "1"}
        for phase, repository in (("private", SOURCE), ("pre_cutover", EVIDENCE), ("bogus", None)):
            with mock.patch.object(cli, "_real_ports") as ports:
                code, _, err = _run(["sweep", "--manifest", self.write(phase, repository)], env)
            self.assertEqual(code, cli.EXIT_USAGE, phase)
            self.assertIn("evidence", err)
            ports.assert_not_called()

    def test_resolve_evidence_prints_only_the_repository_name_for_the_owner(self) -> None:
        code, out, _ = _run(["resolve-evidence", "--manifest", self.write("private"), "--owner", "amirbena"], {"BENCHMARK_APP_SLUG": SLUG})
        self.assertEqual((code, out.strip()), (0, "name=code-review-skill-evidence"))
        code, _, err = _run(["resolve-evidence", "--manifest", self.write("private"), "--owner", "someone-else"], {"BENCHMARK_APP_SLUG": SLUG})
        self.assertEqual(code, cli.EXIT_USAGE)


class LogHygieneTests(unittest.TestCase):
    def test_refusal_detail_that_quotes_record_content_never_reaches_the_log(self) -> None:
        secret = "SENTINEL-RECORD-CONTENT"
        world = World()
        record = make_record()
        world.seal(record, data=json.dumps({"schema": secret, "case": secret}).encode())
        env = {"BENCHMARK_APP_SLUG": SLUG}
        code, out, err = _run(["sweep", "--once", "--dry-run"], env, world.ports())
        self.assertNotEqual(code, 0)  # refused
        self.assertNotIn(secret, err)
        self.assertIn("[schema]", err)  # the gate code stays visible


if __name__ == "__main__":
    unittest.main()
