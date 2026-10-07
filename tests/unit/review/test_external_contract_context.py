#!/usr/bin/env python3
"""Contract: revision selection, bounded read, provenance, and failure mapping
for skills/local-code-review/policies/external-contract-context.md (Issue #133).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tests.reference.review import external_contract_context as ecc

_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, env=_ENV, check=True
    )
    return done.stdout.strip()


def commit(repo: Path, files: dict[str, str], message: str) -> str:
    for rel, content in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


class _RepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name).resolve()
        self.target = self._init("target")
        commit(self.target, {"a.txt": "a\n"}, "target")
        self.ext = self._init("billing-contracts")
        self.pinned = commit(self.ext, {"schema.json": '{"user_id": 1}\n'}, "pinned")
        git(self.ext, "tag", "v1")
        self.head = commit(self.ext, {"schema.json": '{"account_id": 1}\n'}, "later")

    def _init(self, name: str) -> Path:
        repo = self.tmp / name
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        return repo


class RevisionSelectionTests(_RepoCase):
    def test_full_sha_resolves_and_records_full_sha(self) -> None:
        res = ecc.resolve_revision(self.ext, self.pinned)
        self.assertEqual((res.sha, res.basis), (self.pinned, ecc.Basis.SHA))

    def test_abbreviated_sha_resolves_to_full_sha(self) -> None:
        res = ecc.resolve_revision(self.ext, self.pinned[:10])
        self.assertEqual(res.sha, self.pinned)

    def test_tag_resolves_to_its_commit(self) -> None:
        res = ecc.resolve_revision(self.ext, "v1")
        self.assertEqual((res.sha, res.basis), (self.pinned, ecc.Basis.TAG))

    def test_annotated_tag_is_peeled_to_commit(self) -> None:
        git(self.ext, "tag", "-a", "v2", "-m", "annotated", self.pinned)
        self.assertEqual(ecc.resolve_revision(self.ext, "v2").sha, self.pinned)

    def test_head_and_branch_are_not_pinned_revisions(self) -> None:
        for revision in ("HEAD", "main", "FETCH_HEAD", "HEAD~1", "main^", "@{u}", "a..b", "-x"):
            with self.subTest(revision=revision):
                res = ecc.resolve_revision(self.ext, revision)
                self.assertEqual(res.outcome, ecc.Outcome.UNAVAILABLE)
                self.assertIsNone(res.sha)

    def test_pinned_revision_wins_over_repository_head(self) -> None:
        read = ecc.read_contract_files(self.ext, self.pinned, ["schema.json"])
        self.assertIn("user_id", read.files["schema.json"])
        self.assertNotIn("account_id", read.files["schema.json"])
        self.assertNotEqual(self.pinned, self.head)

    def test_working_tree_is_never_read(self) -> None:
        (self.ext / "schema.json").write_text("dirty\n", encoding="utf-8")
        read = ecc.read_contract_files(self.ext, self.pinned, ["schema.json"])
        self.assertIn("user_id", read.files["schema.json"])

    def test_absent_revision_is_unavailable_not_fetched(self) -> None:
        res = ecc.resolve_revision(self.ext, "0" * 40)
        self.assertEqual(res.outcome, ecc.Outcome.UNAVAILABLE)

    def test_too_short_abbreviation_is_not_a_pinned_revision(self) -> None:
        res = ecc.resolve_revision(self.ext, self.pinned[:4])
        self.assertEqual(res.outcome, ecc.Outcome.UNAVAILABLE)
        self.assertIsNone(res.sha)

    def test_tag_that_is_also_a_hex_object_prefix_is_ambiguous(self) -> None:
        git(self.ext, "tag", self.head[:8], self.pinned)
        res = ecc.resolve_revision(self.ext, self.head[:8])
        self.assertEqual(res.outcome, ecc.Outcome.AMBIGUOUS)


class BoundedReadTests(_RepoCase):
    def test_absent_contract_path_is_reported_missing(self) -> None:
        read = ecc.read_contract_files(self.ext, self.pinned, ["nope.json"])
        self.assertEqual((dict(read.files), read.missing), ({}, ("nope.json",)))

    def test_path_escapes_are_refused(self) -> None:
        read = ecc.read_contract_files(self.ext, self.pinned, ["../target/a.txt", "/etc/passwd", "-p"])
        self.assertEqual(dict(read.files), {})
        self.assertEqual(len(read.missing), 3)

    def test_file_count_cap_truncates(self) -> None:
        names = [f"f{i}.txt" for i in range(ecc.MAX_FILES + 3)]
        sha = commit(self.ext, {n: "x\n" for n in names}, "many")
        read = ecc.read_contract_files(self.ext, sha, names)
        self.assertTrue(read.truncated)
        self.assertEqual(len(read.files), ecc.MAX_FILES)

    def test_oversized_file_is_not_read_and_marks_truncation(self) -> None:
        sha = commit(self.ext, {"big.json": "x" * (ecc.MAX_FILE_BYTES + 1)}, "big")
        read = ecc.read_contract_files(self.ext, sha, ["big.json"])
        self.assertEqual((dict(read.files), read.truncated), ({}, True))


class ProvenanceTests(_RepoCase):
    def test_every_required_field_is_recorded(self) -> None:
        now = datetime(2026, 10, 7, 12, 0, 5, tzinfo=timezone.utc)
        prov = ecc.build_provenance(self.ext, self.pinned, ecc.Basis.SHA, now=now)
        self.assertEqual(prov.repository, "billing-contracts")
        self.assertEqual(prov.resolved_sha, self.pinned)
        self.assertEqual(prov.selection_basis, "caller-pinned-sha")
        self.assertEqual(prov.retrieval_time, "2026-10-07T12:00:05Z")
        self.assertEqual(prov.trust, "caller-supplied-read-only")

    def test_tag_basis_is_recorded_with_resolved_commit(self) -> None:
        res = ecc.resolve_revision(self.ext, "v1")
        prov = ecc.build_provenance(self.ext, res.sha, res.basis)
        self.assertEqual((prov.selection_basis, prov.resolved_sha), ("caller-pinned-tag", self.pinned))


class FailureMappingTests(_RepoCase):
    def assess(self, **kw):
        base = dict(
            target_members=[self.target],
            path=self.ext,
            revision=self.pinned,
            contract_paths=["schema.json"],
        )
        base.update(kw)
        return ecc.assess(**base)

    def assertNoClaims(self, result: ecc.Assessment) -> None:
        self.assertFalse(result.breakage_claim_allowed)
        self.assertFalse(result.no_consumers_statement_allowed)
        self.assertFalse(result.review_incomplete)
        self.assertEqual(result.finding_location_repo, "review-target")
        self.assertIsNotNone(result.context_gap)

    def test_pinned_contract_proving_incompatibility_is_a_confirmed_claim(self) -> None:
        result = self.assess(expectation_violated=True)
        self.assertEqual(result.outcome, ecc.Outcome.EVIDENCE_READ)
        self.assertTrue(result.breakage_claim_allowed)
        self.assertEqual(result.confidence, ecc.Confidence.CONFIRMED)
        self.assertEqual(result.provenance.resolved_sha, self.pinned)
        self.assertEqual(result.finding_location_repo, "review-target")

    def test_read_without_violation_makes_no_breakage_claim(self) -> None:
        result = self.assess()
        self.assertFalse(result.breakage_claim_allowed)
        self.assertFalse(result.no_consumers_statement_allowed)

    def test_missing_repository_fails_closed_for_the_claim_only(self) -> None:
        result = self.assess(path=self.tmp / "missing")
        self.assertEqual(result.outcome, ecc.Outcome.UNAVAILABLE)
        self.assertEqual(result.confidence, ecc.Confidence.EXTERNAL_CONTRACT_UNVALIDATED)
        self.assertNoClaims(result)

    def test_non_git_directory_is_unavailable(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertNoClaims(self.assess(path=plain))

    def test_absent_revision_is_unavailable(self) -> None:
        result = self.assess(revision="f" * 40)
        self.assertEqual(result.outcome, ecc.Outcome.UNAVAILABLE)
        self.assertNoClaims(result)

    def test_absent_contract_path_is_unavailable_not_no_consumers(self) -> None:
        result = self.assess(contract_paths=["gone.json"])
        self.assertEqual(result.outcome, ecc.Outcome.UNAVAILABLE)
        self.assertNoClaims(result)

    def test_branch_name_revision_is_unavailable(self) -> None:
        self.assertNoClaims(self.assess(revision="main"))

    def test_ambiguous_revision_maps_to_insufficient_context(self) -> None:
        git(self.ext, "tag", self.head[:8], self.pinned)
        result = self.assess(revision=self.head[:8])
        self.assertEqual(result.outcome, ecc.Outcome.AMBIGUOUS)
        self.assertEqual(result.confidence, ecc.Confidence.INSUFFICIENT_CONTEXT)
        self.assertNoClaims(result)

    def test_conflict_with_target_evidence_is_reported_not_ranked(self) -> None:
        result = self.assess(contradicts_target=True, expectation_violated=True)
        self.assertEqual(result.outcome, ecc.Outcome.CONFLICT)
        self.assertFalse(result.breakage_claim_allowed)


if __name__ == "__main__":
    unittest.main()
