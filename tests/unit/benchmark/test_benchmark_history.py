#!/usr/bin/env python3
"""Coverage for nightly history persistence and baseline policy (Issue #338).

Proves: bootstrap (first run auto-becomes the baseline), later runs never
move the baseline on their own, retention prunes old entries but never the
one backing the current baseline, and `promote-baseline` is the only other
way the baseline changes.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.benchmark import benchmark_history as history


def _entry(*, date: str, repo_sha: str, corpus_id: str = "corpus-abc") -> history.HistoryEntry:
    return history.HistoryEntry(
        date=date,
        repo_sha=repo_sha,
        corpus_id=corpus_id,
        adapter_id=repo_sha,
        recorded_at=f"{date}T00:00:00+00:00",
        routine_metadata={"mode": "full", "repo_sha": repo_sha},
        results=({"id": "case-1", "input_kind": "patch", "status": "executed", "produced_findings": []},),
    )


class RecordRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_first_run_bootstraps_the_baseline(self) -> None:
        outcome = history.record_run(self.root, _entry(date="2026-09-01", repo_sha="a" * 40))

        self.assertTrue(outcome.is_bootstrap)
        baseline = history.load_baseline(self.root)
        self.assertIsNotNone(baseline)
        self.assertEqual(baseline["corpus_id"], "corpus-abc")
        self.assertEqual(baseline["source_entry"], f"history/{outcome.entry_path.name}")

    def test_second_run_does_not_move_the_baseline(self) -> None:
        history.record_run(self.root, _entry(date="2026-09-01", repo_sha="a" * 40))
        baseline_after_first = history.load_baseline(self.root)

        outcome = history.record_run(self.root, _entry(date="2026-09-02", repo_sha="b" * 40))

        self.assertFalse(outcome.is_bootstrap)
        self.assertEqual(history.load_baseline(self.root), baseline_after_first)

    def test_duplicate_entry_refuses_to_overwrite(self) -> None:
        history.record_run(self.root, _entry(date="2026-09-01", repo_sha="a" * 40))
        with self.assertRaises(history.HistoryError):
            history.record_run(self.root, _entry(date="2026-09-01", repo_sha="a" * 40))

    def test_retention_prunes_oldest_entries_but_keeps_baseline_source(self) -> None:
        history.record_run(self.root, _entry(date="2026-01-01", repo_sha="a" * 40), retention=2)
        for day, sha in [("2026-01-02", "b"), ("2026-01-03", "c"), ("2026-01-04", "d")]:
            history.record_run(self.root, _entry(date=day, repo_sha=sha * 40), retention=2)

        remaining = sorted(p.name for p in (self.root / "history").glob("*.json"))
        # Newest 2 entries (01-03, 01-04) plus the bootstrap baseline source (01-01).
        self.assertEqual(len(remaining), 3)
        self.assertTrue(any(name.startswith("2026-01-01") for name in remaining))
        self.assertTrue(any(name.startswith("2026-01-03") for name in remaining))
        self.assertTrue(any(name.startswith("2026-01-04") for name in remaining))
        self.assertFalse(any(name.startswith("2026-01-02") for name in remaining))


class PromoteBaselineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_promote_requires_existing_history(self) -> None:
        with self.assertRaises(history.HistoryError):
            history.promote_baseline(self.root)

    def test_promote_latest_by_default(self) -> None:
        history.record_run(self.root, _entry(date="2026-09-01", repo_sha="a" * 40))
        history.record_run(self.root, _entry(date="2026-09-02", repo_sha="b" * 40, corpus_id="corpus-xyz"))

        artifact = history.promote_baseline(self.root)

        self.assertEqual(artifact["corpus_id"], "corpus-xyz")
        self.assertEqual(history.load_baseline(self.root)["corpus_id"], "corpus-xyz")

    def test_promote_explicit_entry(self) -> None:
        history.record_run(self.root, _entry(date="2026-09-01", repo_sha="a" * 40))
        history.record_run(self.root, _entry(date="2026-09-02", repo_sha="b" * 40, corpus_id="corpus-xyz"))
        first_entry_path = self.root / "history" / f"2026-09-01-{'a' * 12}.json"

        artifact = history.promote_baseline(self.root, first_entry_path)

        self.assertEqual(artifact["corpus_id"], "corpus-abc")

    def test_promote_never_runs_implicitly_from_record(self) -> None:
        history.record_run(self.root, _entry(date="2026-09-01", repo_sha="a" * 40))
        baseline_before = history.load_baseline(self.root)
        history.record_run(self.root, _entry(date="2026-09-02", repo_sha="b" * 40, corpus_id="corpus-xyz"))
        self.assertEqual(history.load_baseline(self.root), baseline_before)


class LoadRawCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _write(self, payload: object) -> Path:
        path = self.root / "results.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_flattens_cases_across_invocations(self) -> None:
        path = self._write(
            [
                {"case_id": "c1", "run": {"ok": True, "cases": [{"id": "c1", "status": "executed"}]}},
                {"case_id": "c2", "run": {"ok": True, "cases": [{"id": "c2", "status": "executed"}]}},
            ]
        )
        cases = history.load_raw_cases(path)
        self.assertEqual([c["id"] for c in cases], ["c1", "c2"])

    def test_rejects_empty_payload(self) -> None:
        path = self._write([])
        with self.assertRaises(history.HistoryError):
            history.load_raw_cases(path)

    def test_rejects_malformed_invocation(self) -> None:
        path = self._write([{"case_id": "c1", "run": "not-a-dict"}])
        with self.assertRaises(history.HistoryError):
            history.load_raw_cases(path)


class ShowBaselineCliTest(unittest.TestCase):
    def test_reports_no_baseline_before_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exit_code = history.main(["show-baseline", "--history-root", str(root)])
            self.assertEqual(exit_code, 0)

    def test_record_cli_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results_file = root / "results.json"
            results_file.write_text(
                json.dumps(
                    [
                        {
                            "case_id": None,
                            "run": {
                                "ok": True,
                                "cases": [
                                    {
                                        "id": "case-1",
                                        "input_kind": "patch",
                                        "status": "executed",
                                        "produced_findings": [],
                                    }
                                ],
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )
            metadata_file = root / "metadata.json"
            metadata_file.write_text(
                json.dumps({"metadata": {"mode": "full", "repo_sha": "c" * 40}}), encoding="utf-8"
            )
            corpus_dir = root / "corpus"
            corpus_dir.mkdir()

            history_root = root / "history-checkout"
            exit_code = history.main(
                [
                    "record",
                    "--history-root",
                    str(history_root),
                    "--results-file",
                    str(results_file),
                    "--routine-metadata-file",
                    str(metadata_file),
                    "--corpus-dir",
                    str(corpus_dir),
                ]
            )
            self.assertEqual(exit_code, 0)
            baseline = history.load_baseline(history_root)
            self.assertIsNotNone(baseline)
            self.assertEqual(baseline["adapter_id"], "c" * 40)


if __name__ == "__main__":
    unittest.main()
