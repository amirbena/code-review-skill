#!/usr/bin/env python3
"""`publish_benchmark.py sweep` command line: identity, credentials, `--once`, `--dry-run` (Issue #471)."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from typing import Mapping

from runtime_platform.benchmark.publisher import cli, github_api
from runtime_platform.benchmark.publisher.layout import receipt_path
from runtime_platform.benchmark.publisher.ports import FatalPublicationError
from tests.support.benchmark_publisher_fakes import EXAMPLES, IDENTITY, REPOSITORY, SLUG, World, make_record
from tests.unit.benchmark.test_benchmark_publisher_sweep import S0, _at

ACTIONS_ENV = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "7", "GITHUB_REPOSITORY": REPOSITORY, "BENCHMARK_APP_SLUG": SLUG}


def run_cli(argv: list[str], env: Mapping[str, str], world: World | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    factory = (lambda manifest, identity: world.ports()) if world else None
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv, env=env, ports_factory=factory)
    return code, out.getvalue(), err.getvalue()


class CredentialTests(unittest.TestCase):
    def test_the_acting_identity_must_be_known(self) -> None:
        code, _, err = run_cli(["sweep", "--once"], {})
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("App slug", err)

    def test_missing_app_tokens_never_fall_back_to_a_personal_identity(self) -> None:
        env = {"BENCHMARK_APP_SLUG": SLUG, "GH_TOKEN": "ghp_personal", "GITHUB_TOKEN": "ghs_workflow_token"}
        code, _, err = run_cli(["sweep", "--once"], env)
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("never falls back to a personal identity", err)

    def test_a_personal_token_is_refused_as_an_app_token(self) -> None:
        env = {"BENCHMARK_APP_SLUG": SLUG, "BENCHMARK_CONTENTS_TOKEN": "ghp_personal", "BENCHMARK_ISSUES_TOKEN": "ghs_ok"}
        code, _, err = run_cli(["sweep", "--once"], env)
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("not a GitHub App installation token", err)

    def test_app_tokens_build_the_real_ports_without_touching_the_network(self) -> None:
        env = {"BENCHMARK_CONTENTS_TOKEN": "ghs_contents", "BENCHMARK_ISSUES_TOKEN": "ghs_issues"}
        ports = cli._real_ports(env, REPOSITORY)
        self.assertIsInstance(ports.tracker, github_api.GitHubIssueTracker)
        with self.assertRaises(FatalPublicationError):
            cli._real_ports({"BENCHMARK_CONTENTS_TOKEN": "ghs_contents"}, REPOSITORY)


class ModeTests(unittest.TestCase):
    def test_a_pass_outside_actions_requires_once(self) -> None:
        code, _, err = run_cli(["sweep"], {"BENCHMARK_APP_SLUG": SLUG}, World())
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("--once", err)

    def test_accept_unattributed_requires_a_run_id(self) -> None:
        code, _, err = run_cli(["sweep", "--once", "--accept-unattributed"], {"BENCHMARK_APP_SLUG": SLUG}, World())
        self.assertEqual((code, "--run-id" in err), (cli.EXIT_USAGE, True))

    def test_run_id_is_pattern_validated(self) -> None:
        code, _, err = run_cli(["sweep", "--once", "--run-id", "x; rm -rf /"], {"BENCHMARK_APP_SLUG": SLUG}, World())
        self.assertEqual((code, "not a valid run_id" in err), (cli.EXIT_USAGE, True))

    def test_once_prints_the_acting_identity_and_records_the_local_run(self) -> None:
        world = World()
        record = make_record(start=_at(16), sha=S0)
        world.seal(record)
        code, out, err = run_cli(["sweep", "--once"], {"BENCHMARK_APP_SLUG": SLUG}, world)
        self.assertEqual(code, 0, err)
        self.assertIn(f"acting identity: {IDENTITY}", err)
        receipt = world.stored(receipt_path(record["run_id"]))
        self.assertIn("local-once", receipt["steps_done"])
        self.assertEqual(receipt["publisher_run_url"], f"https://github.com/{REPOSITORY}")
        self.assertTrue(json.loads(out)["ok"])

    def test_actions_run_url_is_recorded_in_the_receipt(self) -> None:
        world = World()
        record = make_record(start=_at(16), sha=S0)
        world.seal(record)
        code, _, _ = run_cli(["sweep"], ACTIONS_ENV, world)
        self.assertEqual(code, 0)
        self.assertEqual(world.stored(receipt_path(record["run_id"]))["publisher_run_url"], f"https://github.com/{REPOSITORY}/actions/runs/7")

    def test_a_refusal_is_reported_and_exits_nonzero(self) -> None:
        world = World()
        world.seal(make_record(start=_at(16), sha=S0), actor="someone-else")
        code, out, err = run_cli(["sweep", "--once"], {"BENCHMARK_APP_SLUG": SLUG}, world)
        self.assertEqual(code, 1)
        self.assertIn("[origin]", err)
        self.assertFalse(json.loads(out)["ok"])


class DryRunTests(unittest.TestCase):
    """Evidence: a `--once --dry-run` over the reference sealed records plans record, receipt, and issue actions."""

    def test_dry_run_over_reference_fixtures_plans_everything_and_writes_nothing(self) -> None:
        world = World()
        for name in ("sentinel-bootstrap", "sentinel-compared-drift"):
            record = json.loads((EXAMPLES / f"{name}.record.json").read_text(encoding="utf-8"))
            world.seal(record)
        code, out, err = run_cli(["sweep", "--once", "--dry-run"], {"BENCHMARK_APP_SLUG": SLUG}, world)
        self.assertEqual(code, 0, err)
        self.assertIn("dry run", err)
        runs = json.loads(out)["runs"]
        self.assertEqual([r["status"] for r in runs], ["published", "published"])
        self.assertEqual(sorted(a["action"] for a in runs[1]["actions"]), ["opened", "opened"])
        self.assertEqual(world.store.files, {})
        self.assertEqual((world.store.commits, world.tracker.issues, world.tracker.comments), ([], {}, {}))


if __name__ == "__main__":
    unittest.main()
