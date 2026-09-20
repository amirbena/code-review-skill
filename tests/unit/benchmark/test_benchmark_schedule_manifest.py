"""Unit coverage for the scheduled-benchmark expected-run manifest (#469)."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from runtime_platform.benchmark.scripts import benchmark_schedule_manifest as sm
from tests.support.paths import REPO_ROOT


def _manifest() -> dict:
    return sm.load_manifest()


def _provisioned() -> dict:
    manifest = _manifest()
    manifest["lanes"]["sentinel"]["tracking_issue"] = 1001
    manifest["lanes"]["comprehensive"]["tracking_issue"] = 1002
    manifest["health_issue"] = 1003
    return manifest


def _unprovisioned() -> dict:
    manifest = _manifest()
    manifest["lanes"]["sentinel"]["tracking_issue"] = None
    manifest["lanes"]["comprehensive"]["tracking_issue"] = None
    manifest["health_issue"] = None
    return manifest


class CommittedManifestTests(unittest.TestCase):
    def test_committed_manifest_is_valid(self) -> None:
        self.assertEqual(sm.validate_manifest(_manifest()), [])

    def test_entrypoint_exists(self) -> None:
        self.assertTrue((REPO_ROOT / _manifest()["entrypoint"]).is_file())

    def test_lane_modes_are_scheduled_modes(self) -> None:
        for name, lane in _manifest()["lanes"].items():
            self.assertEqual(lane["mode"], name)

    def test_max_gap_hours_match_amendment_a11(self) -> None:
        lanes = _manifest()["lanes"]
        self.assertEqual(lanes["sentinel"]["max_gap_hours"], 96)
        self.assertEqual(lanes["comprehensive"]["max_gap_hours"], 192)

    def test_comprehensive_weekday_is_named(self) -> None:
        start = _manifest()["lanes"]["comprehensive"]["intended_start"]
        self.assertEqual((start["weekday"], start["local_time"], start["timezone"]), ("Friday", "01:00", "Asia/Jerusalem"))
        self.assertIsNone(_manifest()["lanes"]["sentinel"]["intended_start"]["weekday"])

    def test_confirmation_matches_recommended_parameters(self) -> None:
        self.assertEqual(_manifest()["confirmation"], {"reruns": 2, "threshold": 2, "max_cases": 10})

    def test_label_names_are_the_ones_the_lifecycle_documents(self) -> None:
        names = {label["role"]: label["name"] for label in _manifest()["labels"]}
        self.assertEqual(names, {
            "drift": "benchmark-regression", "keep-open": "keep-open",
            "missed-run": "benchmark-missed-run", "tracking": "benchmark-tracking",
        })

    def test_committed_manifest_is_provisioned(self) -> None:
        self.assertEqual(sm.validate_manifest(_manifest(), require_provisioned=True), [])

    def test_unprovisioned_manifest_fails_closed_only_when_required(self) -> None:
        self.assertEqual(sm.validate_manifest(_unprovisioned()), [])
        errors = sm.validate_manifest(_unprovisioned(), require_provisioned=True)
        self.assertEqual(len(errors), 3)
        self.assertEqual(sm.validate_manifest(_provisioned(), require_provisioned=True), [])


class RejectionTests(unittest.TestCase):
    def assert_rejected(self, mutate, expected_fragment: str) -> None:
        manifest = _manifest()
        mutate(manifest)
        errors = sm.validate_manifest(manifest)
        self.assertTrue(any(expected_fragment in e for e in errors), f"{expected_fragment!r} not in {errors}")

    def test_non_object_manifest(self) -> None:
        self.assertEqual(sm.validate_manifest([]), ["manifest: must be an object"])

    def test_unknown_and_missing_fields(self) -> None:
        self.assert_rejected(lambda m: m.update(extra=1), "unknown field 'extra'")
        self.assert_rejected(lambda m: m.pop("confirmation"), "missing field 'confirmation'")
        self.assert_rejected(lambda m: m["lanes"]["sentinel"].update(cron="0 1 * * *"), "unknown field 'cron'")

    def test_schema_version(self) -> None:
        self.assert_rejected(lambda m: m.update(schema="benchmark-schedule/v2"), "schema")

    def test_lane_set_is_exactly_two(self) -> None:
        self.assert_rejected(lambda m: m["lanes"].pop("comprehensive"), "lanes: must define exactly")
        self.assert_rejected(lambda m: m["lanes"].update(full=copy.deepcopy(m["lanes"]["sentinel"])), "lanes: must define exactly")

    def test_mode_must_equal_lane(self) -> None:
        self.assert_rejected(lambda m: m["lanes"]["sentinel"].update(mode="full"), "lanes.sentinel.mode")

    def test_max_gap_cannot_exceed_ceiling(self) -> None:
        self.assert_rejected(lambda m: m["lanes"]["sentinel"].update(max_gap_hours=97), "<= 96")
        self.assert_rejected(lambda m: m["lanes"]["comprehensive"].update(max_gap_hours=193), "<= 192")

    def test_max_gap_must_be_positive_integer(self) -> None:
        for bad in (0, -1, 1.5, "96", True, None):
            with self.subTest(bad=bad):
                self.assert_rejected(lambda m, b=bad: m["lanes"]["sentinel"].update(max_gap_hours=b), "max_gap_hours")

    def test_weekday_rules(self) -> None:
        self.assert_rejected(lambda m: m["lanes"]["comprehensive"]["intended_start"].update(weekday=None), "weekday")
        self.assert_rejected(lambda m: m["lanes"]["comprehensive"]["intended_start"].update(weekday="Fri"), "weekday")
        self.assert_rejected(lambda m: m["lanes"]["sentinel"]["intended_start"].update(weekday="Friday"), "weekday-anchored")

    def test_time_format(self) -> None:
        self.assert_rejected(lambda m: m["lanes"]["sentinel"]["intended_start"].update(local_time="1:00"), "local_time")
        self.assert_rejected(lambda m: m["lanes"]["sentinel"].update(target_completion_local="24:00"), "target_completion_local")

    def test_confirmation_bounds(self) -> None:
        self.assert_rejected(lambda m: m["confirmation"].update(threshold=1), "threshold")
        self.assert_rejected(lambda m: m["confirmation"].update(threshold=4), "cannot exceed")
        self.assert_rejected(lambda m: m["confirmation"].update(reruns=0), "reruns")
        self.assert_rejected(lambda m: m["confirmation"].update(max_cases=0), "max_cases")

    def test_staging_ref_must_be_under_claude(self) -> None:
        self.assert_rejected(lambda m: m["publication"].update(staging_ref_pattern="main"), "staging_ref_pattern")
        self.assert_rejected(lambda m: m["publication"].update(staging_ref_pattern="benchmark/*"), "staging_ref_pattern")

    def test_staging_ref_cannot_widen_to_other_claude_refs(self) -> None:
        for wide in ("claude/*", "claude/", "claude/issue-1", "claude/benchmark-result"):
            with self.subTest(pattern=wide):
                self.assert_rejected(lambda m, p=wide: m["publication"].update(staging_ref_pattern=p), "staging_ref_pattern")

    def test_pusher_allowlist(self) -> None:
        self.assert_rejected(lambda m: m["publication"].update(pusher_allowlist=[]), "pusher_allowlist")
        self.assert_rejected(lambda m: m["publication"].update(pusher_allowlist=["-bad"]), "invalid GitHub login")
        self.assert_rejected(lambda m: m["publication"].update(pusher_allowlist=["a", "a"]), "duplicate")

    def test_label_set_is_exactly_the_four_roles(self) -> None:
        self.assert_rejected(lambda m: m["labels"].pop(), "exactly one label per role")
        self.assert_rejected(lambda m: m["labels"].append(dict(m["labels"][0])), "exactly one label per role")

    def test_label_shape(self) -> None:
        self.assert_rejected(lambda m: m["labels"][0].update(color="#b60205"), "color")
        self.assert_rejected(lambda m: m["labels"][0].update(color="B60205"), "color")
        self.assert_rejected(lambda m: m["labels"][0].update(description="x" * 101), "description")
        self.assert_rejected(lambda m: m["labels"][1].update(name=m["labels"][0]["name"]), "duplicate label names")

    def test_issue_numbers(self) -> None:
        self.assert_rejected(lambda m: m["lanes"]["sentinel"].update(tracking_issue=0), "tracking_issue")
        self.assert_rejected(lambda m: m.update(health_issue="7"), "health_issue")
        manifest = _provisioned()
        manifest["health_issue"] = 1001
        self.assertIn("tracking/health issue numbers must be distinct", sm.validate_manifest(manifest))


class CliTests(unittest.TestCase):
    def _run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = sm.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_validate_committed_manifest(self) -> None:
        code, out, _ = self._run("validate")
        self.assertEqual(code, 0)
        self.assertIn("valid", out)

    def test_require_provisioned_passes_on_committed_manifest(self) -> None:
        code, out, _ = self._run("validate", "--require-provisioned")
        self.assertEqual(code, 0)
        self.assertIn("valid", out)

    def test_require_provisioned_exits_nonzero_on_unprovisioned_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps(_unprovisioned()), encoding="utf-8")
            code, _, err = self._run("validate", "--manifest", str(path), "--require-provisioned")
        self.assertEqual(code, 1)
        self.assertIn("not provisioned", err)

    def test_unreadable_manifest_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text("{not json", encoding="utf-8")
            code, _, err = self._run("validate", "--manifest", str(path))
        self.assertEqual(code, 1)
        self.assertIn("cannot read manifest", err)

    def test_invalid_manifest_reports_every_problem(self) -> None:
        manifest = _manifest()
        manifest["confirmation"]["threshold"] = 1
        manifest["lanes"]["sentinel"]["max_gap_hours"] = 200
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            code, _, err = self._run("validate", "--manifest", str(path))
        self.assertEqual(code, 1)
        self.assertEqual(err.count("error:"), 2)


if __name__ == "__main__":
    unittest.main()
