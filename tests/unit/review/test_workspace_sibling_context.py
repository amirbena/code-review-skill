#!/usr/bin/env python3
"""Behavior with read traces for shared/policies/workspace-sibling-context.md
(Issue #663), for both adapters. Reads use real Git repositories.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.reference.review import workspace_sibling_context as wsc
from tests.unit.review.test_external_contract_context import commit, git

S = wsc.SignalKind
REF = [wsc.Signal(S.API_REF, "billing-service")]


class WorkspaceCase(unittest.TestCase):
    adapter = wsc.Adapter.LOCAL

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name).resolve() / "workspace"
        self.ws.mkdir()
        self.target = self.repo("orders")
        commit(self.target, {"a.txt": "a\n"}, "t")
        self.sibling = self.repo("billing-service")
        self.sha = commit(self.sibling, {"api/status.py": "STATUSES = ['paid']\n"}, "s")

    def repo(self, name: str) -> Path:
        path = self.ws / name
        path.mkdir()
        git(path, "init", "-q", "-b", "main")
        return path

    def review(self, **kw) -> wsc.Review:
        kw.setdefault("grant", self.ws)
        return wsc.Review(self.adapter, [self.target], **kw)


class ActivationTests(WorkspaceCase):
    def test_no_grant_loads_nothing_and_reads_nothing(self) -> None:
        resolver = wsc.Resolver(self.review(grant=None))
        res = resolver.resolve(REF, ["api/status.py"])
        self.assertEqual(res.outcome, wsc.Outcome.NOT_ACTIVATED)
        self.assertEqual(resolver.trace, [])

    def test_should_load_requires_grant_and_question(self) -> None:
        self.assertTrue(wsc.should_load(grant_supplied=True, eligible_question=True))
        self.assertFalse(wsc.should_load(grant_supplied=False, eligible_question=True, ambiguous=True))
        self.assertFalse(wsc.should_load(grant_supplied=True, eligible_question=False))
        self.assertTrue(wsc.should_load(grant_supplied=True, eligible_question=False, ambiguous=True))

    def test_worker_never_loads(self) -> None:
        self.assertFalse(wsc.should_load(grant_supplied=True, eligible_question=True, is_worker=True))
        resolver = wsc.Resolver(self.review(is_worker=True))
        self.assertEqual(resolver.resolve(REF, ["api/status.py"]).outcome, wsc.Outcome.NOT_ACTIVATED)
        self.assertEqual(resolver.trace, [])

    def test_explicit_channel_resolution_skips_workspace(self) -> None:
        resolver = wsc.Resolver(self.review())
        res = resolver.resolve(REF, ["api/status.py"], explicit_resolved=True)
        self.assertEqual(res.outcome, wsc.Outcome.NOT_ACTIVATED)
        self.assertEqual(resolver.trace, [])


class ResolutionTests(WorkspaceCase):
    def test_reads_committed_head_with_provenance_and_trace(self) -> None:
        resolver = wsc.Resolver(self.review())
        res = resolver.resolve(REF, ["api/status.py"])
        self.assertEqual(res.outcome, wsc.Outcome.EVIDENCE_READ)
        self.assertIn("paid", res.files["api/status.py"])
        p = res.provenance
        self.assertEqual((p.resolved_sha, p.selection_basis, p.trust, p.dirty), (self.sha, "workspace-resolved", "workspace-granted-read-only", False))
        self.assertEqual(resolver.trace, [("list", "workspace"), ("read", "billing-service", self.sha, "api/status.py")])
        self.assertEqual(res.finding_location_repo, "review-target")
        self.assertFalse(res.can_confirm_alone)
        self.assertFalse(res.absence_claim_allowed)

    def test_dirty_sibling_is_read_at_commit_and_flagged(self) -> None:
        (self.sibling / "api/status.py").write_text("STATUSES = ['uncommitted']\n")
        (self.sibling / "untracked.txt").write_text("x")
        res = wsc.Resolver(self.review()).resolve(REF, ["api/status.py"])
        self.assertTrue(res.provenance.dirty)
        self.assertIn("paid", res.files["api/status.py"])
        self.assertNotIn("uncommitted", res.files["api/status.py"])

    def test_detached_head_is_unavailable(self) -> None:
        git(self.sibling, "checkout", "-q", "--detach")
        res = wsc.Resolver(self.review()).resolve(REF, ["api/status.py"])
        self.assertEqual(res.outcome, wsc.Outcome.UNAVAILABLE)
        self.assertFalse(res.breakage_claim_allowed)

    def test_unborn_head_is_unavailable(self) -> None:
        import shutil
        shutil.rmtree(self.sibling)
        self.repo("billing-service")
        res = wsc.Resolver(self.review()).resolve(REF, ["api/status.py"])
        self.assertEqual(res.outcome, wsc.Outcome.UNAVAILABLE)

    def test_absent_path_is_unavailable_never_absence(self) -> None:
        res = wsc.Resolver(self.review()).resolve(REF, ["api/missing.py"])
        self.assertEqual(res.outcome, wsc.Outcome.UNAVAILABLE)
        self.assertFalse(res.absence_claim_allowed)
        self.assertFalse(res.review_incomplete)

    def test_conflict_with_target_is_reported(self) -> None:
        res = wsc.Resolver(self.review()).resolve(REF, ["api/status.py"], contradicts_target=True)
        self.assertEqual(res.outcome, wsc.Outcome.CONFLICT)

    def test_reevaluates_only_the_affected_question(self) -> None:
        res = wsc.Resolver(self.review()).resolve(REF, ["api/status.py"])
        self.assertEqual(wsc.reevaluate(res, lambda f: "paid" in f["api/status.py"]), "resolved")
        self.assertEqual(wsc.reevaluate(res, lambda f: "refunded" in f["api/status.py"]), "unresolved")
        missing = wsc.Resolver(self.review()).resolve(REF, ["nope"])
        self.assertEqual(wsc.reevaluate(missing, lambda f: True), "unresolved")


class NominationTests(WorkspaceCase):
    def test_bare_name_match_is_ambiguous_and_reads_nothing(self) -> None:
        resolver = wsc.Resolver(self.review())
        res = resolver.resolve([wsc.Signal(S.NAME_MATCH, "billing-service")], ["api/status.py"])
        self.assertEqual(res.outcome, wsc.Outcome.AMBIGUOUS)
        self.assertEqual([t for t in resolver.trace if t[0] == "read"], [])

    def test_two_plausible_candidates_read_nothing(self) -> None:
        other = self.repo("ledger")
        commit(other, {"api/status.py": "x\n"}, "o")
        resolver = wsc.Resolver(self.review())
        res = resolver.resolve([wsc.Signal(S.API_REF, "billing-service"), wsc.Signal(S.SERVICE_REF, "ledger")], ["api/status.py"])
        self.assertEqual(res.outcome, wsc.Outcome.AMBIGUOUS)
        self.assertIn("ledger", res.context_gap)
        self.assertEqual([t for t in resolver.trace if t[0] == "read"], [])

    def test_undiscovered_name_is_never_nominated(self) -> None:
        res = wsc.Resolver(self.review()).resolve([wsc.Signal(S.API_REF, "ghost")], ["x"])
        self.assertEqual(res.outcome, wsc.Outcome.UNRESOLVED)

    def test_sibling_cap_of_three(self) -> None:
        names = ["s1", "s2", "s3", "s4"]
        for name in names:
            commit(self.repo(name), {"f.txt": name}, name)
        resolver = wsc.Resolver(self.review())
        outcomes = [resolver.resolve([wsc.Signal(S.API_REF, n)], ["f.txt"]).outcome for n in names]
        self.assertEqual(outcomes[:3], [wsc.Outcome.EVIDENCE_READ] * 3)
        self.assertEqual(outcomes[3], wsc.Outcome.CAP_REACHED)

    def test_unavailable_siblings_count_toward_the_cap(self) -> None:
        names = ["u1", "u2", "u3", "u4"]
        for name in names:
            commit(self.repo(name), {"f.txt": name}, name)
            git(self.ws / name, "checkout", "-q", "--detach")
        resolver = wsc.Resolver(self.review())
        outcomes = [resolver.resolve([wsc.Signal(S.API_REF, n)], ["f.txt"]).outcome for n in names]
        self.assertEqual(outcomes, [wsc.Outcome.UNAVAILABLE] * 3 + [wsc.Outcome.CAP_REACHED])

    def test_listing_happens_once_per_review(self) -> None:
        resolver = wsc.Resolver(self.review())
        resolver.resolve(REF, ["api/status.py"])
        resolver.resolve(REF, ["api/status.py"])
        self.assertEqual(len([t for t in resolver.trace if t[0] == "list"]), 1)

    def test_listing_cap_is_reported(self) -> None:
        for i in range(wsc.MAX_LISTING + 5):
            (self.ws / f"d{i:03}").mkdir()
        disc = wsc.discover(self.review())
        self.assertTrue(disc.truncated)


class ConsumerSurfaceTests(WorkspaceCase):
    def test_non_recursive_nested_repository_not_discoverable(self) -> None:
        holder = self.ws / "group"
        holder.mkdir()
        nested = holder / "inner"
        nested.mkdir()
        git(nested, "init", "-q", "-b", "main")
        names = [c.name for c in wsc.discover(self.review()).candidates]
        self.assertNotIn("inner", names)
        self.assertNotIn("group", names)

    def test_linked_worktree_target_needs_explicit_root(self) -> None:
        wt = self.ws.parent / "orders-wt"
        git(self.target, "worktree", "add", "-q", str(wt), "-b", "wt")
        review = wsc.Review(self.adapter, [wt], grant=self.ws)
        excluded = wsc.discover(review).excluded
        self.assertEqual(excluded.get("orders"), "member-or-alias")


class GithubAdapterTests(WorkspaceCase):
    adapter = wsc.Adapter.GITHUB

    def test_api_only_mode_is_unavailable_and_unchanged(self) -> None:
        self.assertFalse(
            wsc.should_load(grant_supplied=True, eligible_question=True, adapter=self.adapter, local_fs_access=False)
        )
        resolver = wsc.Resolver(self.review(local_fs_access=False))
        self.assertEqual(resolver.resolve(REF, ["api/status.py"]).outcome, wsc.Outcome.NOT_ACTIVATED)
        self.assertEqual(resolver.trace, [])

    def test_pr_repository_excluded_by_identity_not_only_path(self) -> None:
        clone = self.repo("orders-clone")
        git(clone, "remote", "add", "origin", "https://github.com/acme/orders.git")
        commit(clone, {"a.txt": "a\n"}, "c")
        pr = wsc.PrIdentity("acme/orders")
        disc = wsc.discover(self.review(pr=pr))
        self.assertEqual(disc.excluded.get("orders-clone"), "pr-repository")
        self.assertNotIn("orders-clone", [c.name for c in disc.candidates])

    def test_pr_repository_excluded_by_commit_identity(self) -> None:
        clone = self.repo("renamed")
        sha = commit(clone, {"a.txt": "a\n"}, "c")
        pr = wsc.PrIdentity("acme/orders", commits=frozenset({sha}))
        self.assertEqual(wsc.discover(self.review(pr=pr)).excluded.get("renamed"), "pr-repository")

    def test_pr_identity_match_is_exact_not_a_suffix(self) -> None:
        near = self.repo("near")
        git(near, "remote", "add", "origin", "https://github.com/other-acme/orders.git")
        commit(near, {"a.txt": "a\n"}, "n")
        ssh = self.repo("ssh")
        git(ssh, "remote", "add", "origin", "git@github.com:Acme/Orders.git")
        commit(ssh, {"a.txt": "a\n"}, "s")
        for url in ("https://github.com/acme/orders/", "https://github.com/acme/orders.git/"):
            self.assertEqual(wsc._owner_name(url), "acme/orders")
        disc = wsc.discover(self.review(pr=wsc.PrIdentity("acme/orders")))
        self.assertIn("near", [c.name for c in disc.candidates])
        self.assertEqual(disc.excluded.get("ssh"), "pr-repository")

    def test_resolution_matches_local_adapter(self) -> None:
        res = wsc.Resolver(self.review()).resolve(REF, ["api/status.py"])
        self.assertEqual(res.outcome, wsc.Outcome.EVIDENCE_READ)
        self.assertEqual(res.provenance.selection_basis, "workspace-resolved")


if __name__ == "__main__":
    unittest.main()
