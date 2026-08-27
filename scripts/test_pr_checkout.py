#!/usr/bin/env python3
"""Repository-backed PR checkout, exercised with real git against a local
bare-repo simulation (no GitHub).

Contract: skills/github-pr-review/policies/repository-checkout.md.
"""

from __future__ import annotations

import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

import pr_checkout as co
import pr_simulation as sim
from pr_checkout import (
    CheckoutError,
    InvalidShaError,
    NormalizedPrSource,
    RefNotFoundError,
    RemoteUnavailableError,
    RepositoryAccessMode,
    RepositoryAccessOutcome,
    prepare_repository_checkout,
    run_with_repository_access,
)


class NormalizedPrSourceTests(unittest.TestCase):
    def test_real_and_simulated_metadata_produce_the_same_shape(self) -> None:
        with sim.simulated_pr() as pr:
            src = pr.normalized_source()
        self.assertIsInstance(src, NormalizedPrSource)
        for field in ("repo_url", "pr_number", "base_ref", "base_sha", "head_ref", "head_sha"):
            self.assertTrue(getattr(src, field) not in (None, ""))

    def test_malformed_sha_is_rejected_at_construction(self) -> None:
        with self.assertRaises(InvalidShaError):
            NormalizedPrSource(
                repo_url="x", pr_number=1, base_ref="b", base_sha="not-a-sha",
                head_ref="h", head_sha="deadbeef",
            )


class HappyPathTests(unittest.TestCase):
    def test_clone_fetch_checkout_delta_and_cleanup(self) -> None:
        with sim.simulated_pr() as pr:
            src = pr.normalized_source()
            with prepare_repository_checkout(src) as handle:
                checkout_path = handle.path
                self.assertTrue(checkout_path.is_dir())
                # exact base/head + base...head delta
                self.assertEqual(handle.head_sha, pr.head_sha)
                self.assertEqual(handle.merge_base(), pr.merge_base)
                self.assertEqual(sorted(handle.changed_files()), sorted(pr.changed_files))
                # detached HEAD, not on a branch
                branch = subprocess.run(
                    ["git", "-C", str(checkout_path), "symbolic-ref", "-q", "HEAD"],
                    capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(branch.returncode, 0)
                # surrounding repository files (not in the delta) are readable
                self.assertIn("PI is a constant", handle.read_file("docs/design.md"))
                self.assertIn("math.pi", handle.read_file("src/lib.py"))
            # cleaned up after the context exits
            self.assertFalse(checkout_path.exists())
            self.assertFalse(checkout_path.parent.exists())

    def test_base_advanced_after_branch_still_scopes_to_pr_delta(self) -> None:
        with sim.simulated_pr(advance_base_after_branch=True) as pr:
            with prepare_repository_checkout(pr.normalized_source()) as handle:
                # unrelated later main commit (CHANGELOG.md) must not appear
                self.assertNotIn("CHANGELOG.md", handle.changed_files())
                self.assertEqual(sorted(handle.changed_files()), sorted(pr.changed_files))
                self.assertEqual(handle.merge_base(), pr.merge_base)

    def test_missing_pull_ref_falls_back_to_branch_and_sha(self) -> None:
        with sim.simulated_pr(publish_pull_ref=False) as pr:
            src = pr.normalized_source()  # pull_ref is None
            self.assertIsNone(src.pull_ref)
            with prepare_repository_checkout(src) as handle:
                self.assertEqual(handle.head_sha, pr.head_sha)


class FailureTests(unittest.TestCase):
    def test_inaccessible_remote_raises_and_cleans_up(self) -> None:
        src = sim.unreadable_source()
        created: list[Path] = []
        # capture the scratch dir mkdtemp will make
        real_mkdtemp = tempfile.mkdtemp

        def spy(*a, **k):
            d = real_mkdtemp(*a, **k)
            created.append(Path(d))
            return d

        tempfile.mkdtemp = spy
        try:
            with self.assertRaises(RemoteUnavailableError):
                with prepare_repository_checkout(src):
                    pass
        finally:
            tempfile.mkdtemp = real_mkdtemp
        self.assertTrue(created)
        for d in created:
            self.assertFalse(d.exists(), f"scratch dir left behind: {d}")

    def test_invalid_head_sha_fails_safely(self) -> None:
        with sim.simulated_pr() as pr:
            good = pr.normalized_source()
            bad = NormalizedPrSource(
                repo_url=good.repo_url, pr_number=good.pr_number,
                base_ref=good.base_ref, base_sha=good.base_sha,
                head_ref=good.head_ref,
                head_sha="0" * 40,           # syntactically valid, absent
                pull_ref=None,
            )
            with self.assertRaises((InvalidShaError, RefNotFoundError, CheckoutError)):
                with prepare_repository_checkout(bad):
                    pass

    def test_cleanup_after_inspection_failure(self) -> None:
        with sim.simulated_pr() as pr:
            captured: dict[str, Path] = {}
            with self.assertRaises(RuntimeError):
                with prepare_repository_checkout(pr.normalized_source()) as handle:
                    captured["path"] = handle.path
                    raise RuntimeError("simulated review failure after checkout")
            self.assertIn("path", captured)
            self.assertFalse(captured["path"].exists())
            self.assertFalse(captured["path"].parent.exists())


class RepositoryAccessModeTests(unittest.TestCase):
    def test_api_only_never_prepares_checkout(self) -> None:
        calls = []
        result = run_with_repository_access(
            sim.unreadable_source(), RepositoryAccessMode.API_ONLY, calls.append
        )
        self.assertEqual(result.outcome, RepositoryAccessOutcome.API_ONLY)
        self.assertEqual(calls, [None])

    def test_optional_success_and_visible_degradation(self) -> None:
        calls = []
        with sim.simulated_pr() as pr:
            result = run_with_repository_access(
                pr.normalized_source(), RepositoryAccessMode.OPTIONAL, calls.append
            )
        self.assertEqual(result.outcome, RepositoryAccessOutcome.REPOSITORY_BACKED)
        self.assertEqual(len(calls), 1)
        calls.clear()
        degraded = run_with_repository_access(
            sim.unreadable_source(), RepositoryAccessMode.OPTIONAL, calls.append
        )
        self.assertEqual(degraded.outcome, RepositoryAccessOutcome.API_ONLY_DEGRADED)
        self.assertIn("repository context unavailable", degraded.detail)
        self.assertEqual(calls, [None])

    def test_required_failure_is_incomplete_and_does_not_start_review(self) -> None:
        calls = []
        result = run_with_repository_access(
            sim.unreadable_source(), RepositoryAccessMode.REQUIRED, calls.append
        )
        self.assertEqual(result.outcome, RepositoryAccessOutcome.INCOMPLETE)
        self.assertFalse(result.callback_called)
        self.assertEqual(calls, [])

    def test_required_sha_mismatch_is_incomplete(self) -> None:
        calls = []
        with sim.simulated_pr() as pr:
            good = pr.normalized_source()
            bad = NormalizedPrSource(
                good.repo_url, good.pr_number, good.base_ref, good.base_sha,
                good.head_ref, "0" * 40, None,
            )
            result = run_with_repository_access(
                bad, RepositoryAccessMode.REQUIRED, calls.append
            )
        self.assertEqual(result.outcome, RepositoryAccessOutcome.INCOMPLETE)
        self.assertEqual(calls, [])


class SecurityTests(unittest.TestCase):
    def test_hooks_are_disabled_in_the_checkout(self) -> None:
        with sim.simulated_pr() as pr:
            with prepare_repository_checkout(pr.normalized_source()) as handle:
                hooks_path = subprocess.run(
                    ["git", "-C", str(handle.path), "config", "--get", "core.hooksPath"],
                    capture_output=True, text=True, check=False,
                ).stdout.strip()
                self.assertEqual(hooks_path, "/dev/null")

    def test_no_target_repository_code_is_executed(self) -> None:
        # An executable pre-commit hook + a marker file. Nothing in the
        # checkout path may run it.
        with sim.simulated_pr() as pr:
            with prepare_repository_checkout(pr.normalized_source()) as handle:
                marker = handle.path / "HOOK_RAN"
                hook = handle.path / ".git" / "hooks" / "pre-commit"
                hook.parent.mkdir(parents=True, exist_ok=True)
                hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
                hook.chmod(0o755)
                # read-only inspection commands only
                handle.changed_files()
                handle.diff()
                handle.read_file("src/lib.py")
                self.assertFalse(marker.exists())

    def test_read_file_cannot_escape_the_checkout(self) -> None:
        with sim.simulated_pr() as pr:
            with prepare_repository_checkout(pr.normalized_source()) as handle:
                with self.assertRaises(CheckoutError):
                    handle.read_file("../../../etc/hostname")

    def test_cleanup_refuses_a_directory_without_the_ownership_marker(self) -> None:
        scratch = Path(tempfile.mkdtemp(prefix="pr-guard-"))
        try:
            victim = scratch / "not-ours"
            victim.mkdir()
            (victim / "keep.txt").write_text("important\n", encoding="utf-8")
            with self.assertRaises(CheckoutError):
                co._safe_rmtree(victim, scratch)
            self.assertTrue((victim / "keep.txt").exists())
        finally:
            import shutil
            shutil.rmtree(scratch, ignore_errors=True)


class RepositoryContextDoesNotWidenTargetTests(unittest.TestCase):
    def test_delta_is_bounded_to_merge_base_to_head(self) -> None:
        with sim.simulated_pr(advance_base_after_branch=True) as pr:
            with prepare_repository_checkout(pr.normalized_source()) as handle:
                delta = set(handle.changed_files())
                # design.md exists in the repo and is inspectable as context,
                # but it is NOT part of the PR delta.
                self.assertIn("PI is a constant", handle.read_file("docs/design.md"))
                self.assertNotIn("docs/design.md", delta)
                self.assertNotIn("README.md", delta)
                self.assertEqual(delta, set(pr.changed_files))


class ConcurrentCheckoutTests(unittest.TestCase):
    def test_two_simultaneous_checkouts_are_isolated_and_clean_up(self) -> None:
        results: dict[str, object] = {}
        errors: list[BaseException] = []

        def run(tag: str) -> None:
            try:
                with sim.simulated_pr() as pr:
                    with prepare_repository_checkout(pr.normalized_source()) as h:
                        results[tag + "_path"] = h.path
                        results[tag + "_files"] = sorted(h.changed_files())
                        results[tag + "_head"] = h.head_sha
                    results[tag + "_exists_after"] = h.path.exists()
            except BaseException as exc:  # noqa: BLE001 - surface in the assert
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(t,)) for t in ("a", "b")]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        self.assertEqual(errors, [])
        self.assertNotEqual(results["a_path"], results["b_path"])
        self.assertEqual(results["a_files"], results["b_files"])   # same fixture shape
        self.assertFalse(results["a_exists_after"])
        self.assertFalse(results["b_exists_after"])


class GitHubBoundaryTests(unittest.TestCase):
    """The checkout consumes a NormalizedPrSource only — a simulated one here,
    a GitHub-adapter one in production. No `if simulation` in the checkout."""

    def test_checkout_has_no_simulation_or_github_dependency(self) -> None:
        import ast

        src = Path(co.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import pr_simulation", src)
        # walk real code (docstrings excluded) for any simulation special-casing
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                seg = ast.get_source_segment(src, node.test) or ""
                self.assertNotIn("simul", seg.lower())


if __name__ == "__main__":
    unittest.main()
