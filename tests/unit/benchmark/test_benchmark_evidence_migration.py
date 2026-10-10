#!/usr/bin/env python3
"""Coverage for the read-only evidence inventory and reconciliation (Issue #690)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from runtime_platform.benchmark.scripts import benchmark_evidence_migration as mig

NS = ["claude/benchmark-result-"]
HIST = "benchmark-history"


def _git(cwd: Path, *args: str) -> str:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *args], cwd=cwd, env={**env, "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
                          capture_output=True, text=True, check=True).stdout


class MigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _store(self, name: str) -> Path:
        path = self.root / name
        path.mkdir()
        _git(path, "init", "-q", "--bare")
        return path

    def _seed(self, store: Path, branch: str, text: str) -> None:
        work = self.root / f"w-{store.name}-{branch.replace('/', '_')}"
        _git(self.root, "clone", "-q", str(store), str(work))
        _git(work, "checkout", "-q", "-b", branch)
        (work / "r.json").write_text(text)
        _git(work, "add", "r.json")
        _git(work, "commit", "-q", "-m", "seal")
        _git(work, "push", "-q", "origin", branch)

    def test_inventory_lists_only_in_scope_branches_with_integrity(self) -> None:
        store = self._store("src.git")
        self._seed(store, "claude/benchmark-result-a", "1")
        self._seed(store, HIST, "h")
        self._seed(store, "feature/other", "x")
        doc = mig.inventory(str(store), NS, HIST)
        self.assertEqual(sorted(doc["refs"]), ["refs/heads/benchmark-history", "refs/heads/claude/benchmark-result-a"])
        self.assertEqual(len(doc["refs"]["refs/heads/claude/benchmark-result-a"]["tree"]), 40)

    def test_a_copy_by_sha_reconciles_and_extra_refs_do_not_fail(self) -> None:
        src = self._store("src.git")
        self._seed(src, "claude/benchmark-result-a", "1")
        dst = self._store("dst.git")
        _git(src, "push", "-q", str(dst), "refs/heads/claude/benchmark-result-a:refs/heads/claude/benchmark-result-a")
        self._seed(dst, "claude/benchmark-result-new", "2")
        report = mig.reconcile(mig.inventory(str(src), NS, HIST), mig.inventory(str(dst), NS, HIST))
        self.assertTrue(report["reconciled"])
        self.assertEqual(report["extra_in_target"], ["refs/heads/claude/benchmark-result-new"])

    def test_missing_and_rewritten_refs_are_mismatches(self) -> None:
        src = self._store("src.git")
        self._seed(src, "claude/benchmark-result-a", "1")
        self._seed(src, "claude/benchmark-result-b", "2")
        dst = self._store("dst.git")
        self._seed(dst, "claude/benchmark-result-a", "rewritten")
        report = mig.reconcile(mig.inventory(str(src), NS, HIST), mig.inventory(str(dst), NS, HIST))
        self.assertFalse(report["reconciled"])
        self.assertEqual(report["missing_in_target"], ["refs/heads/claude/benchmark-result-b"])
        self.assertEqual(report["differing"], ["refs/heads/claude/benchmark-result-a"])

    def test_reset_refs_are_not_inputs_and_are_never_restored(self) -> None:
        src = self._store("src.git")
        self._seed(src, "claude/benchmark-result-a", "1")
        self._seed(src, HIST, "h")
        dst = self._store("dst.git")
        _git(src, "push", "-q", str(dst), "--all")
        a, b = mig.inventory(str(src), NS, HIST), mig.inventory(str(dst), NS, HIST)
        gone = "refs/heads/claude/benchmark-result-reset"
        # a ref deleted by the maintainer is absent from both stores: nothing to restore, still reconciled
        self.assertTrue(mig.reconcile(a, b, frozenset({gone}))["reconciled"])
        # a reset ref that was copied anyway is a forbidden restoration
        b["refs"][gone] = {"commit": "c" * 40, "tree": "d" * 40}
        report = mig.reconcile(a, b, frozenset({gone}))
        self.assertEqual(report["reset_refs_restored_in_target"], [gone])
        self.assertFalse(report["reconciled"])

    def test_history_branch_must_be_identical_and_forbid_extra_flags_new_refs(self) -> None:
        src = self._store("src.git")
        self._seed(src, HIST, "h")
        dst = self._store("dst.git")
        self._seed(dst, HIST, "other-history")
        a, b = mig.inventory(str(src), NS, HIST), mig.inventory(str(dst), NS, HIST)
        self.assertEqual(mig.reconcile(a, b)["differing"], ["refs/heads/benchmark-history"])
        later = {**a, "refs": {**a["refs"], "refs/heads/claude/benchmark-result-new": {"commit": "e" * 40, "tree": "f" * 40}}}
        self.assertTrue(mig.reconcile(a, later)["reconciled"])
        self.assertFalse(mig.reconcile(a, later, forbid_extra=True)["reconciled"])

    def test_cli_exit_codes_and_no_write_to_the_stores(self) -> None:
        src = self._store("src.git")
        self._seed(src, "claude/benchmark-result-a", "1")
        before = _git(src, "for-each-ref")
        manifest = self.root / "m.json"
        manifest.write_text(json.dumps({"evidence": {"namespaces": NS, "history_branch": HIST}}))
        a, b = self.root / "a.json", self.root / "b.json"
        for out in (a, b):
            self.assertEqual(mig.main(["inventory", "--remote", str(src), "--manifest", str(manifest), "--out", str(out)]), 0)
        self.assertEqual(mig.main(["reconcile", "--source", str(a), "--target", str(b)]), 0)
        self.assertEqual(mig.main(["reconcile", "--source", str(a), "--target", str(self.root / "none.json")]), 2)
        self.assertEqual(_git(src, "for-each-ref"), before)


if __name__ == "__main__":
    unittest.main()
