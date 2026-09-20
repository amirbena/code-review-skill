"""The seal transport (#470; execution-publication-boundary.md §4)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_seal as seal

REF = "claude/benchmark-result-sentinel-20260920T010000Z-aaaaaaaaaaaa"
FILES = {seal.RAW_FILE: b'{"raw": true}\n', seal.RECORD_FILE: b'{"record": true}\n'}


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return proc.stdout.strip()


class SealToRefTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.remote, self.work = base / "remote.git", base / "work"
        _git(base, "init", "--bare", "-q", str(self.remote))
        _git(base, "init", "-q", str(self.work))
        _git(self.work, "remote", "add", "origin", str(self.remote))

    def test_creates_an_orphan_ref_holding_exactly_the_files(self) -> None:
        commit = seal.seal_to_ref(self.work, "origin", REF, FILES, "seal")
        self.assertEqual(_git(self.remote, "rev-parse", f"refs/heads/{REF}"), commit)
        self.assertEqual(_git(self.remote, "rev-list", "--parents", "-n1", commit), commit)  # no parent
        self.assertEqual(sorted(_git(self.remote, "ls-tree", "--name-only", commit).split()), sorted(FILES))
        self.assertEqual(_git(self.remote, "show", f"{commit}:{seal.RECORD_FILE}"), '{"record": true}')

    def test_leaves_the_working_tree_and_local_refs_untouched(self) -> None:
        seal.seal_to_ref(self.work, "origin", REF, FILES, "seal")
        self.assertEqual(_git(self.work, "status", "--porcelain"), "")
        self.assertEqual(_git(self.work, "for-each-ref", "refs/heads", "refs/tags"), "")

    def test_an_existing_ref_is_never_overwritten(self) -> None:
        first = seal.seal_to_ref(self.work, "origin", REF, FILES, "seal")
        with self.assertRaises(seal.SealError):
            seal.seal_to_ref(self.work, "origin", REF, {seal.RECORD_FILE: b"different\n"}, "seal again")
        self.assertEqual(_git(self.remote, "rev-parse", f"refs/heads/{REF}"), first)

    def test_a_ref_outside_claude_is_refused_before_any_push(self) -> None:
        for ref in ("main", "benchmark-history", "benchmark-result-x", "refs/tags/v1"):
            with self.assertRaises(seal.SealError):
                seal.seal_to_ref(self.work, "origin", ref, FILES, "seal")
        self.assertEqual(_git(self.remote, "for-each-ref"), "")

    def test_a_stalled_git_call_times_out_as_a_seal_error(self) -> None:
        with mock.patch.object(seal.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 1)):
            with self.assertRaisesRegex(seal.SealError, "timed out"):
                seal.seal_to_ref(self.work, "origin", REF, FILES, "seal")

    def test_git_never_prompts_for_credentials_and_is_bounded(self) -> None:
        with mock.patch.object(seal.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=b"x\n", stderr=b"")) as run:
            seal._git(self.work, "status")
        self.assertEqual(run.call_args.kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(run.call_args.kwargs["timeout"], seal.GIT_TIMEOUT_S)

    def test_an_unreachable_remote_fails_closed(self) -> None:
        with self.assertRaises(seal.SealError):
            seal.seal_to_ref(self.work, "nowhere", REF, FILES, "seal")


class SealToDirectoryTests(unittest.TestCase):
    def test_the_commit_file_is_written_last(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            order: list[str] = []
            original = Path.write_bytes

            def spy(self: Path, data: bytes) -> int:
                order.append(self.name)
                return original(self, data)

            Path.write_bytes = spy  # type: ignore[method-assign]
            try:
                seal.seal_to_directory(Path(tmp) / "out", FILES, seal.RECORD_FILE)
            finally:
                Path.write_bytes = original  # type: ignore[method-assign]
            self.assertEqual(order[-1], seal.RECORD_FILE)
            self.assertEqual(json.loads((Path(tmp) / "out" / seal.RECORD_FILE).read_text()), {"record": True})


class NamingTests(unittest.TestCase):
    def test_refs_stay_under_claude(self) -> None:
        self.assertTrue(seal.staging_ref("x").startswith("claude/"))
        self.assertTrue(seal.HANDOFF_CHECK_REF_PREFIX.startswith("claude/"))

    def test_handoff_check_never_matches_the_publisher_sweep_pattern(self) -> None:
        self.assertFalse(seal.HANDOFF_CHECK_REF_PREFIX.startswith(seal.STAGING_REF_PREFIX))


if __name__ == "__main__":
    unittest.main()
