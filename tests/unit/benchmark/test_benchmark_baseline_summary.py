"""Tests for the read-only benchmark baseline summary."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from runtime_platform.benchmark.scripts import benchmark_baseline_summary as summary
from tests.support.benchmark_records import make_case, sealed_record, write_history


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def history(self, *records):
        for record in records:
            write_history(self.root, record, pointer_lane=record["lane"])
        return summary.DirectorySource(self.root)

    def test_lane_without_records_is_reported_as_having_none(self):
        source = self.history(sealed_record("sentinel", [make_case("a", matched=1, exact=1)]))
        text = summary.render_markdown(summary.summary_dict(source, ["comprehensive", "sentinel"]))
        self.assertIn("### Lane `comprehensive`\n\nNo sealed record exists for this lane.", text)

    def test_records_are_ordered_oldest_first_with_model_and_runtime(self):
        old = sealed_record("sentinel", [make_case("a", matched=1, exact=1)], started_at="2026-09-01T01:00:00Z", model_id="m-old")
        new = sealed_record("sentinel", [make_case("a", matched=1, exact=0)], started_at="2026-09-04T01:00:00Z", model_id="m-new", runtime_version="cli-2")
        data = summary.summary_dict(self.history(new, old), ["sentinel"])
        records = data["lanes"]["sentinel"]["records"]
        self.assertEqual([r["runtime"]["model_id"] for r in records], ["m-old", "m-new"])
        text = summary.render_markdown(data)
        self.assertIn("| 1 |", text)
        self.assertIn("cli-2", text)

    def test_invalid_record_is_rejected_and_listed_not_summarized(self):
        good = sealed_record("sentinel", [make_case("a", matched=1, exact=1)])
        source = self.history(good)
        bad_path = self.root / "records" / "sentinel" / "2026" / "bad.json"
        bad_path.write_text(json.dumps({"schema": "benchmark-result/v1"}), encoding="utf-8")
        data = summary.summary_dict(source, ["sentinel"])
        self.assertEqual(len(data["lanes"]["sentinel"]["records"]), 1)
        self.assertEqual([r["path"] for r in data["rejected"]], ["records/sentinel/2026/bad.json"])
        self.assertIn("### Rejected records", summary.render_markdown(data))

    def test_missing_provenance_field_is_named(self):
        record = sealed_record("sentinel", [make_case("a", matched=1, exact=1)])
        record["runtime"]["model_id"] = ""
        self.assertEqual(summary.provenance_gaps(record), ["runtime.model_id"])

    def test_complete_provenance_reports_no_gaps(self):
        record = sealed_record("sentinel", [make_case("a", matched=1, exact=1)])
        self.assertEqual(summary.provenance_gaps(record), [])

    def test_summary_never_writes_to_the_history(self):
        source = self.history(sealed_record("sentinel", [make_case("a", matched=1, exact=1)]))
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())
        summary.render_markdown(summary.summary_dict(source, ["sentinel"]))
        after = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())
        self.assertEqual(before, after)

    def test_declared_lanes_come_from_the_schedule_manifest(self):
        self.assertEqual(summary.declared_lanes(), ["comprehensive", "sentinel"])

    def test_unreachable_ref_exits_nonzero(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = summary.main(["--ref", "refs/does/not/exist"])
        self.assertEqual(code, 1)
        self.assertIn("error:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
