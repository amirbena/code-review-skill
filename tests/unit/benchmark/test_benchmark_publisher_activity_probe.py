"""The read-only X3 activity probe (issue #714; ADR §12): fail-closed outcomes, pinned target, and public-log safety."""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from runtime_platform.benchmark.publisher import activity_probe as probe
from runtime_platform.benchmark.publisher import cli
from runtime_platform.benchmark.publisher.ports import RefActivity
from tests.support.evidence_destination import manifest_with
from tests.unit.benchmark.test_benchmark_publisher_github_api import ScriptedOpener

ALLOW = ["amirbena"]
WANTED = f"refs/heads/{probe.PROBE_REF}"
TIP = "c" * 40
ACTOR_SENTINEL = "SENTINEL-actor-7f3a"
TOKEN = "ghs_SENTINELtokenvalue"
TIP_PATH = f"/repos/{probe.PROBE_REPOSITORY}/git/ref/heads/{probe.PROBE_REF}"
ACTIVITY_PATH = f"/repos/{probe.PROBE_REPOSITORY}/activity"


def _creation(actor: str = "amirbena", after: str = TIP) -> RefActivity:
    return RefActivity("branch_creation", WANTED, actor, after)


class FakeReader:
    def __init__(self, tip: str | None = TIP, activities: list[RefActivity] | None = None) -> None:
        self.tip, self.activities, self.calls = tip, activities, []

    def ref_tip(self, ref_name: str) -> str | None:
        self.calls.append(("tip", ref_name))
        return self.tip

    def ref_activities(self, ref_name: str) -> list[RefActivity] | None:
        self.calls.append(("activity", ref_name))
        return self.activities


def _run_cli(env: dict[str, str], reader: Any = None, phase: str = "pre_cutover", factory: Any = None) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "manifest.json"
        manifest.write_text(json.dumps(manifest_with(phase)), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["probe-activity", "--manifest", str(manifest)], env=env, probe_reader=factory or (lambda token: reader))
    return code, out.getvalue(), err.getvalue()


class ProbeOutcomeTests(unittest.TestCase):
    def test_an_allowlisted_creation_at_the_tip_is_attributed(self) -> None:
        result = probe.run_probe(FakeReader(activities=[_creation()]), ALLOW)
        self.assertEqual(result.positive, probe.ATTRIBUTED)
        self.assertTrue(result.passed)

    def test_unavailable_activity_fails_closed(self) -> None:
        result = probe.run_probe(FakeReader(activities=None), ALLOW)
        self.assertEqual(result.positive, probe.ACTIVITY_UNAVAILABLE)
        self.assertFalse(result.passed)

    def test_an_unreadable_ref_fails_closed_without_asking_for_activity(self) -> None:
        reader = FakeReader(tip=None, activities=[_creation()])
        result = probe.run_probe(reader, ALLOW)
        self.assertEqual(result.positive, probe.REF_UNREADABLE)
        self.assertEqual([c[0] for c in reader.calls], ["tip"])
        self.assertFalse(result.passed)

    def test_empty_activity_is_refused_never_accepted_as_unattributed(self) -> None:
        result = probe.run_probe(FakeReader(activities=[]), ALLOW)
        self.assertEqual(result.positive, probe.REFUSED)
        self.assertFalse(result.passed)

    def test_the_wrong_actor_is_refused(self) -> None:
        result = probe.run_probe(FakeReader(activities=[_creation(actor="someone-else")]), ALLOW)
        self.assertEqual(result.positive, probe.REFUSED)

    def test_a_creation_at_another_sha_is_refused(self) -> None:
        result = probe.run_probe(FakeReader(activities=[_creation(after="d" * 40)]), ALLOW)
        self.assertEqual(result.positive, probe.REFUSED)

    def test_only_the_pinned_ref_is_requested(self) -> None:
        reader = FakeReader(activities=[_creation()])
        probe.run_probe(reader, ALLOW)
        self.assertEqual({ref for _, ref in reader.calls}, {probe.PROBE_REF})


class NegativeCaseTests(unittest.TestCase):
    def test_wrong_actor_missing_activity_and_wrong_sha_are_all_rejected(self) -> None:
        self.assertEqual(probe.negative_cases(ALLOW), {case: probe.REJECTED for case in probe.NEGATIVE_CASES})

    def test_the_negatives_do_not_depend_on_the_live_answer(self) -> None:
        for reader in (FakeReader(activities=None), FakeReader(tip=None), FakeReader(activities=[_creation()])):
            self.assertEqual(probe.run_probe(reader, ALLOW).negatives, probe.negative_cases(ALLOW))

    def test_the_wrong_sha_case_is_not_vacuous(self) -> None:
        # The same synthetic activity at the matching SHA would be accepted: only the SHA makes it a rejection.
        ref = probe.StagingRef(probe.PROBE_REF, "a" * 40)
        self.assertIsNone(probe.attest_origin(ref, [RefActivity("branch_creation", WANTED, ALLOW[0], "a" * 40)], ALLOW, accept_unattributed=False))


class PinnedTargetTests(unittest.TestCase):
    def _reader(self, routes: dict[tuple[str, str], Any]) -> tuple[probe.GitHubProbeReader, ScriptedOpener]:
        opener = ScriptedOpener(routes)
        return probe.GitHubProbeReader(TOKEN, opener=opener), opener

    def _routes(self) -> dict[tuple[str, str], Any]:
        return {
            ("GET", TIP_PATH): (200, {"object": {"sha": TIP}}),
            ("GET", ACTIVITY_PATH): (200, [{"activity_type": "branch_creation", "ref": WANTED, "actor": {"login": "amirbena"}, "after": TIP}]),
        }

    def test_the_real_reader_only_gets_and_only_from_the_pinned_repository(self) -> None:
        reader, opener = self._reader(self._routes())
        result = probe.run_probe(reader, ALLOW)
        self.assertTrue(result.passed)
        self.assertEqual(opener.methods(), [f"GET {TIP_PATH}", f"GET {ACTIVITY_PATH}"])
        for method, path, body, headers, _ in opener.requests:
            self.assertEqual(method, "GET")
            self.assertIsNone(body)
            self.assertTrue(path.startswith(f"/repos/{probe.PROBE_REPOSITORY}/"), path)
            self.assertEqual(headers["Authorization"], f"Bearer {TOKEN}")

    def test_the_manifest_repository_cannot_redirect_the_probe(self) -> None:
        reader, opener = self._reader(self._routes())
        for phase in ("pre_cutover", "private"):
            code, out, _ = _run_cli({"BENCHMARK_READ_TOKEN": TOKEN}, phase=phase, factory=lambda token: reader)
            self.assertEqual(code, 0, out)
        self.assertEqual({p.split("/")[2] + "/" + p.split("/")[3] for _, p, *_ in opener.requests}, {probe.PROBE_REPOSITORY})

    def test_a_hidden_activity_endpoint_and_a_missing_ref_fail_closed(self) -> None:
        for status in (403, 404, 422, 500):
            routes = self._routes() | {("GET", ACTIVITY_PATH): (status, {"message": ACTOR_SENTINEL})}
            reader, _ = self._reader(routes)
            result = probe.run_probe(reader, ALLOW)
            self.assertEqual(result.positive, probe.ACTIVITY_UNAVAILABLE, status)
        reader, _ = self._reader({})
        self.assertEqual(probe.run_probe(reader, ALLOW).positive, probe.REF_UNREADABLE)
        reader, _ = self._reader(self._routes() | {("GET", TIP_PATH): (403, {"message": "x"})})
        self.assertEqual(probe.run_probe(reader, ALLOW).positive, probe.REF_UNREADABLE)


class PublicLogSafetyTests(unittest.TestCase):
    def _assert_fixed(self, text: str) -> None:
        lines = [line for line in text.splitlines() if line]
        pattern = r"^x3-probe: (positive=(attributed|refused|ref-unreadable|activity-unavailable)|negative-(wrong-actor|missing-activity|wrong-sha)=(rejected|accepted)|verdict=(pass|fail))$"
        for line in lines:
            self.assertRegex(line, pattern)
        self.assertEqual(len(lines), 5)

    def test_a_pass_prints_fixed_codes_only_in_both_phases(self) -> None:
        for phase in ("pre_cutover", "private"):
            code, out, err = _run_cli({"BENCHMARK_READ_TOKEN": TOKEN}, FakeReader(activities=[_creation(actor=ACTOR_SENTINEL)]), phase=phase)
            self.assertEqual(code, 1)  # the sentinel actor is not allowlisted
            self._assert_fixed(out)
            code, out, err = _run_cli({"BENCHMARK_READ_TOKEN": TOKEN}, FakeReader(activities=[_creation()]), phase=phase)
            self.assertEqual(code, 0)
            self._assert_fixed(out)
            self.assertIn("verdict=pass", out)
            self.assertEqual(err, "")

    def test_no_token_actor_sha_or_repository_reaches_a_log(self) -> None:
        for reader in (FakeReader(activities=[_creation(actor=ACTOR_SENTINEL)]), FakeReader(activities=None), FakeReader(tip=None)):
            _, out, err = _run_cli({"BENCHMARK_READ_TOKEN": TOKEN}, reader, phase="private")
            for text in (out, err):
                for secret in (TOKEN, ACTOR_SENTINEL, TIP, probe.PROBE_REPOSITORY, probe.PROBE_REF, "amirbena"):
                    self.assertNotIn(secret, text)

    def test_a_missing_or_personal_token_stops_before_any_request(self) -> None:
        calls: list[str] = []
        for env in ({}, {"BENCHMARK_READ_TOKEN": "ghp_personal"}, {"GH_TOKEN": "ghs_x", "GITHUB_TOKEN": "ghs_x"}):
            code, out, err = _run_cli(env, factory=lambda token: calls.append(token) or FakeReader())
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            self.assertNotIn("ghp_personal", err)
        self.assertEqual(calls, [])

    def test_the_probe_failure_codes_are_fixed_in_the_private_phase(self) -> None:
        code, out, err = _run_cli({}, phase="private")
        self.assertEqual((code, out, err.strip()), (2, "", "error: evidence-unavailable"))


class IsolationTests(unittest.TestCase):
    def test_the_probe_command_does_not_touch_the_publisher_ports(self) -> None:
        def explode(manifest: Any, identity: str) -> Any:
            raise AssertionError("the probe must not open sweep ports")

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "m.json"
            manifest.write_text(json.dumps(manifest_with()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(
                    ["probe-activity", "--manifest", str(manifest)], env={"BENCHMARK_READ_TOKEN": TOKEN},
                    ports_factory=explode, probe_reader=lambda token: FakeReader(activities=[_creation()]),
                )
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
