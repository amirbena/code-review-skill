"""Read-only baseline lookup (#470; canonical-result-and-persistence.md §5)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from runtime_platform.benchmark.scripts import benchmark_result as res
from runtime_platform.benchmark.scripts.benchmark_baseline import (
    DirectoryHistory,
    GitRefHistory,
    load_baseline,
)
from tests.support.benchmark_records import make_case, sealed_record, write_history


class DirectoryBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.record = sealed_record("sentinel", [make_case("a")])

    def lookup(self, lane: str = "sentinel"):
        return load_baseline(DirectoryHistory(self.root), lane)

    def test_no_pointer_is_bootstrap(self) -> None:
        self.assertEqual(self.lookup().state, "bootstrap")

    def test_valid_pointer_is_compared_with_its_record(self) -> None:
        write_history(self.root, self.record)
        found = self.lookup()
        self.assertEqual((found.state, found.record["run_id"]), ("compared", self.record["run_id"]))

    def test_other_lane_pointer_is_not_read(self) -> None:
        write_history(self.root, self.record)
        self.assertEqual(self.lookup("comprehensive").state, "bootstrap")

    def test_pointer_naming_another_lane_is_a_lane_identity_mismatch(self) -> None:
        write_history(self.root, self.record, lane="comprehensive")
        found = self.lookup()
        self.assertEqual(found.state, "incomparable")
        self.assertIn("lane-identity mismatch", found.reason)

    def test_record_of_another_lane_is_a_lane_identity_mismatch(self) -> None:
        write_history(self.root, sealed_record("comprehensive", [make_case("a")]))
        found = self.lookup()
        self.assertEqual(found.state, "incomparable")
        self.assertIn("lane-identity mismatch", found.reason)

    def test_hash_mismatch_is_incomparable(self) -> None:
        write_history(self.root, self.record, record_sha256="f" * 64)
        self.assertEqual(self.lookup().state, "incomparable")

    def test_tampered_record_is_incomparable(self) -> None:
        write_history(self.root, self.record)
        path = self.root / "records" / "sentinel" / "2026" / f"{self.record['run_id']}.json"
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["runtime"]["model_id"] = "swapped"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        found = self.lookup()
        self.assertEqual(found.state, "incomparable")
        self.assertIn("invalid", found.reason)

    def test_missing_record_is_incomparable(self) -> None:
        write_history(self.root, self.record)
        (self.root / "records" / "sentinel" / "2026" / f"{self.record['run_id']}.json").unlink()
        self.assertEqual(self.lookup().state, "incomparable")

    def test_pointer_path_cannot_escape_the_history(self) -> None:
        write_history(self.root, self.record, record_path="../outside.json")
        self.assertEqual(self.lookup().state, "incomparable")

    def test_malformed_pointer_is_incomparable(self) -> None:
        (self.root / "baselines").mkdir()
        (self.root / "baselines" / "sentinel.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.lookup().state, "incomparable")

    def test_fixture_record_is_accepted(self) -> None:
        example = Path(res.RESULT_SCHEMA_PATH).parent / "examples" / "sentinel-bootstrap.record.json"
        write_history(self.root, json.loads(example.read_text(encoding="utf-8")))
        self.assertEqual(self.lookup().state, "compared")


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return proc.stdout.strip()


class GitRefBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.remote, self.work, self.publisher = base / "remote.git", base / "work", base / "publisher"
        _git(base, "init", "--bare", "-q", str(self.remote))
        for path in (self.work, self.publisher):
            _git(base, "init", "-q", str(path))
            _git(path, "remote", "add", "origin", str(self.remote))

    def publish(self, record: dict) -> None:
        write_history(self.publisher, record)
        _git(self.publisher, "checkout", "-q", "-B", "benchmark-history")
        _git(self.publisher, "add", "-A")
        _git(self.publisher, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "publish")
        _git(self.publisher, "push", "-q", "origin", "benchmark-history")

    def test_absent_branch_is_bootstrap(self) -> None:
        self.assertEqual(load_baseline(GitRefHistory(self.work), "sentinel").state, "bootstrap")

    def test_published_baseline_is_read_from_the_remote_ref(self) -> None:
        record = sealed_record("sentinel", [make_case("a")])
        self.publish(record)
        found = load_baseline(GitRefHistory(self.work), "sentinel")
        self.assertEqual((found.state, found.record["content_sha256"]), ("compared", record["content_sha256"]))

    def test_branch_without_this_lane_is_bootstrap(self) -> None:
        self.publish(sealed_record("sentinel", [make_case("a")]))
        self.assertEqual(load_baseline(GitRefHistory(self.work), "comprehensive").state, "bootstrap")

    def test_unreachable_remote_is_incomparable_never_bootstrap(self) -> None:
        found = load_baseline(GitRefHistory(self.work, remote="nowhere"), "sentinel")
        self.assertEqual(found.state, "incomparable")
        self.assertIn("unreachable", found.reason)


if __name__ == "__main__":
    unittest.main()
