"""The private-phase public-log allowlist (ADR §5.4; F12, F13; issue #704).

Every key and line the sweep and the watchdog write to stdout or stderr is collected for fixtures carrying sentinel
strings, and each must belong to the allowed classes and none to the field policy's prohibited table.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from runtime_platform.benchmark.publisher import cli
from runtime_platform.benchmark.publisher.layout import encode_json
from runtime_platform.benchmark.publisher.ports import FatalPublicationError
from runtime_platform.benchmark.scripts import benchmark_result as res
from tests.support.benchmark_publisher_fakes import SLUG, World, make_record
from tests.support.evidence_destination import manifest_with
from tests.unit.benchmark.test_benchmark_publisher_sweep import S0, S1, S2, _at

SENTINEL = "SENTINEL-7f3a-private-content"
ENV = {"BENCHMARK_APP_SLUG": SLUG, "GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "9", "GITHUB_REPOSITORY": "amirbena/code-review-skill"}
SWEEP_KEYS = {"identity", "ok", "aborted", "scope", "dry_run", "runs", "counts"}
RUN_KEYS = {"ref", "run_id", "status", "gate"}
WATCHDOG_KEYS = {"identity", "ok", "aborted", "lanes", "pending_handoffs"}
LANE_KEYS = {"lane", "expected_from"}
PROHIBITED_KEYS = {
    "finished_at", "overdue", "action", "last_successful_sweep", "missed_run_issue", "open_drift_issues",
    "open_missed_run_issues", "commit", "detail", "actions", "deferred", "health", "latest_run_id",
}
ALLOWED_LINES = (
    re.compile(r"^acting identity: [a-z0-9-]+\[bot\] \(GitHub App installation tokens only; no personal identity is used\)$"),
    re.compile(r"^(refused|failed): claude/benchmark-result-(sentinel|comprehensive)-\d{8}T\d{6}Z-[0-9a-f]{12}: \[[a-z-]+\]$"),
    re.compile(r"^(refused|failed): withheld: \[[a-z-]+\]$"),
    re.compile(r"^aborted: publication-aborted$"),
    re.compile(r"^error: [a-z-]+$"),
    re.compile(r"^dry run: nothing is written to GitHub$"),
)
PRIVATE_VALUE = re.compile(r"[0-9a-f]{40}|https?://|/issues/|Traceback")


def _run(argv: list[str], world: World | None, phase: str, **extra) -> tuple[int, str, str]:
    tmp = tempfile.TemporaryDirectory()
    manifest = Path(tmp.name) / "manifest.json"
    manifest.write_text(json.dumps(manifest_with(phase)), encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    factory = extra.pop("factory", (lambda m, i: world.ports()) if world else None)
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([*argv, "--manifest", str(manifest)], env=ENV, ports_factory=factory)
    tmp.cleanup()
    return code, out.getvalue(), err.getvalue()


def _world() -> World:
    world = World()
    world.seal(make_record(start=_at(16), sha=S0))  # published: the evidence commit SHA must stay private
    tampered = {**make_record(start=_at(17), sha=S1), "schema": SENTINEL}
    world.seal(make_record(start=_at(17), sha=S1), data=encode_json(tampered))  # refused: its detail can quote the record
    world.seal(make_record(start=_at(18), sha=S2), data=b"{" + SENTINEL.encode())  # refused: invalid JSON quoting content
    world.tracker.seed_issue(900, author="someone", body="body " + SENTINEL, labels=["benchmark-regression"])
    return world


def _assert_allowlisted(test: unittest.TestCase, out: str, err: str, keys: set[str], nested: dict[str, set[str]]) -> None:
    for text in (out, err):
        test.assertNotIn(SENTINEL, text)
        test.assertIsNone(PRIVATE_VALUE.search(text), text)
    for line in err.splitlines():
        test.assertTrue(any(p.match(line) for p in ALLOWED_LINES), f"line outside the allowlist: {line!r}")
    if not out.strip():
        return
    report = json.loads(out)
    test.assertLessEqual(set(report), keys)
    for key, allowed in nested.items():
        for row in report.get(key) or []:
            test.assertLessEqual(set(row), allowed)
    test.assertFalse(PROHIBITED_KEYS & _all_keys(report), PROHIBITED_KEYS & _all_keys(report))


def _all_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _all_keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _all_keys(v)}
    return set()


class F12SweepTests(unittest.TestCase):
    def test_the_sweep_emits_only_allowlisted_keys_and_lines(self) -> None:
        code, out, err = _run(["sweep", "--once"], _world(), "private")
        self.assertEqual(code, 1)  # two refused runs
        _assert_allowlisted(self, out, err, SWEEP_KEYS, {"runs": RUN_KEYS})
        report = json.loads(out)
        self.assertEqual(report["counts"], {"published": 1, "refused": 2})
        self.assertTrue(all(run["gate"] for run in report["runs"]))

    def test_a_dry_run_is_allowlisted_too(self) -> None:
        code, out, err = _run(["sweep", "--once", "--dry-run"], _world(), "private")
        _assert_allowlisted(self, out, err, SWEEP_KEYS, {"runs": RUN_KEYS})

    def test_the_public_pre_cutover_output_is_unchanged(self) -> None:
        _, out, _ = _run(["sweep", "--once"], _world(), "pre_cutover")
        self.assertIn("detail", out)  # the legacy full report is kept under pre_cutover
        self.assertIn(SENTINEL, out)  # ...which is why the fixture is potent: only the allowlist keeps it out


class F12WatchdogTests(unittest.TestCase):
    def test_the_watchdog_emits_only_allowlisted_keys_and_lines(self) -> None:
        world = _world()
        report = Path(tempfile.mkdtemp()) / "sweep.json"
        _, sweep_out, _ = _run(["sweep", "--once"], world, "private")
        report.write_text(sweep_out, encoding="utf-8")
        for flag in ([], ["--sweep-report", str(report)]):
            code, out, err = _run(["watchdog", "--once", *flag], world, "private")
            self.assertEqual(code, 0)
            _assert_allowlisted(self, out, err, WATCHDOG_KEYS, {"lanes": LANE_KEYS})
            for record in world.store.files.values():  # a record's own timestamps never reach the log
                for stamp in re.findall(r'"(?:finished_at|started_at|sealed_at)": "([^"]+)"', record.decode("utf-8")):
                    self.assertNotIn(stamp, out + err)
        self.assertEqual({row["lane"] for row in json.loads(out)["lanes"]}, set(world.manifest["lanes"]))

    def test_a_private_phase_sweep_report_still_drives_the_watchdog(self) -> None:
        world = World()
        world.seal(make_record(start=_at(16), sha=S0))
        _, sweep_out, _ = _run(["sweep", "--once"], world, "private")
        self.assertTrue(cli._sweep_succeeded(self._write(sweep_out)) is True)

    @staticmethod
    def _write(text: str) -> Path:
        path = Path(tempfile.mkdtemp()) / "r.json"
        path.write_text(text, encoding="utf-8")
        return path


class F13FailureTests(unittest.TestCase):
    def test_an_uncaught_exception_reaches_the_log_only_as_a_fixed_code(self) -> None:
        def boom(manifest, identity):
            raise RuntimeError(f"GET /repos/private/x/issues/5: {SENTINEL}")

        code, out, err = _run(["sweep", "--once"], None, "private", factory=boom)
        self.assertEqual((code, out, err), (1, "", "error: internal-error\n"))

    def test_a_fatal_port_error_is_a_fixed_code(self) -> None:
        def fatal(manifest, identity):
            raise FatalPublicationError(f"GET /repos/amirbena/private: 404 {SENTINEL}")

        code, out, err = _run(["watchdog", "--once"], None, "private", factory=fatal)
        self.assertEqual((code, out, err), (cli.EXIT_USAGE, "", "error: evidence-unavailable\n"))

    def test_an_aborted_pass_prints_a_fixed_code_not_the_reason(self) -> None:
        world = World()
        world.tracker.labels = set()  # preflight fails: a missing label is quoted in the reason
        code, out, err = _run(["sweep", "--once"], world, "private")
        self.assertEqual(code, 1)
        self.assertIn("aborted: publication-aborted", err)
        _assert_allowlisted(self, out, err, SWEEP_KEYS, {"runs": RUN_KEYS})

    def test_withholding_never_changes_the_exit_status(self) -> None:
        for argv in (["sweep", "--once"], ["sweep", "--once", "--dry-run"]):
            private = _run(argv, _world(), "private")[0]
            legacy = _run(argv, _world(), "pre_cutover")[0]
            self.assertEqual(private, legacy, argv)

    def test_errors_are_codes_in_private_and_messages_in_pre_cutover(self) -> None:
        self.assertEqual(_run(["sweep", "--run-id", SENTINEL], World(), "private")[1:], ("", "error: usage\n"))
        self.assertIn("not a valid run_id", _run(["sweep", "--run-id", "bad"], World(), "pre_cutover")[2])
        self.assertEqual(_run(["watchdog", "--once", "--sweep-report", "/nonexistent-" + SENTINEL], World(), "private")[1:], ("", "error: invalid-sweep-report\n"))

    def test_errors_before_the_phase_is_known_are_fixed_codes(self) -> None:
        for argv in (["sweep", "--once", "--manifest", f"/nonexistent/{SENTINEL}.json"], ["sweep", "--once", "--manifest", __file__]):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(argv, env=ENV)
            self.assertEqual((code, out.getvalue(), err.getvalue()), (cli.EXIT_USAGE, "", "error: invalid-manifest\n"))

    def test_an_argparse_error_never_echoes_the_argument(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            cli.main(["sweep", f"--{SENTINEL}"], env=ENV)
        self.assertEqual((raised.exception.code, err.getvalue()), (cli.EXIT_USAGE, "error: usage\n"))

    def test_an_unknown_phase_fails_closed(self) -> None:
        from runtime_platform.benchmark.publisher.public_log import is_private

        self.assertTrue(is_private({"evidence": {"phase": "bogus"}}))
        self.assertFalse(is_private({"evidence": {"phase": "pre_cutover"}}))


class WriterTests(unittest.TestCase):
    def test_every_value_is_validated_before_it_is_written(self) -> None:
        from runtime_platform.benchmark.publisher import public_log as pl
        from runtime_platform.benchmark.publisher.model import RunOutcome, SweepReport

        report = SweepReport(identity=f"x {SENTINEL}", aborted=f"detail {SENTINEL}")
        report.outcomes.append(RunOutcome(f"claude/{SENTINEL}", SENTINEL, f"weird {SENTINEL}", SENTINEL, f"gate {SENTINEL}", "a" * 40))
        text = json.dumps(pl.sweep_view(report, manifest_with("private")))
        self.assertNotIn(SENTINEL, text)
        self.assertNotIn("a" * 40, text)
        self.assertEqual(text.count(pl.WITHHELD), 6)  # identity, ref, run_id, status, gate, and ok-independent scope stays valid


if __name__ == "__main__":
    unittest.main()
