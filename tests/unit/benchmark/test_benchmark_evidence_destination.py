"""The shared evidence-destination contract (#688; private-evidence-repository.md §4-§5, §9).

Hermetic: stub bare repositories only, no network, no model, no live Routine.
"""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_evidence_destination as ed
from runtime_platform.benchmark.scripts import benchmark_seal as seal
from runtime_platform.benchmark.scripts import run_benchmark_routine as routine
from runtime_platform.benchmark.scripts import run_severity_observation as obs
from tests.support.evidence_destination import EVIDENCE, NAMESPACES, SOURCE, manifest_with

HANDOFF = "claude/benchmark-handoff-check-20261010T000000Z-aaaaaaaaaaaa"
FILES = {seal.HANDOFF_CHECK_FILE: b'{"x": 1}\n'}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()


class Stores(unittest.TestCase):
    """A checkout plus a bare 'public' (source) and a bare 'private' (evidence) remote at identity-bearing paths."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.public = base / f"{SOURCE}.git"
        self.private = base / f"{EVIDENCE}.git"
        self.work = base / "work"
        for bare in (self.public, self.private):
            bare.parent.mkdir(parents=True, exist_ok=True)
            _git(base, "init", "--bare", "-q", str(bare))
        _git(base, "init", "-q", str(self.work))
        _git(self.work, "remote", "add", "origin", str(self.public))
        _git(self.work, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "--allow-empty", "-q", "-m", "init")
        env = mock.patch.dict("os.environ", {ed.TEST_LOCAL_REMOTES_ENV: "1"})
        env.start()
        self.addCleanup(env.stop)

    def refs(self, bare: Path) -> list[str]:
        return _git(bare, "for-each-ref", "--format=%(refname)").splitlines()

    def resolve(self, phase: str = "pre_cutover", remote: str | None = None, **kw) -> ed.Destination:
        manifest = manifest_with(phase, kw.pop("repository", None))
        return ed.resolve_destination(manifest, evidence_remote=remote, repo_root=self.work, **kw)


class PhaseMatrixTests(Stores):
    def test_v1_pre_cutover_without_remote_uses_the_proven_checkout_remote(self) -> None:
        dest = self.resolve("pre_cutover")
        self.assertEqual((dest.repository, dest.phase, dest.remote), (SOURCE, "pre_cutover", "origin"))

    def test_v1_pre_cutover_checkout_remote_must_still_prove_the_source(self) -> None:
        _git(self.work, "remote", "set-url", "origin", str(self.private))
        with self.assertRaisesRegex(ed.DestinationMisconfigured, "not the declared evidence repository"):
            self.resolve("pre_cutover")

    def test_v2_pre_cutover_with_another_repository_is_rejected(self) -> None:
        with self.assertRaisesRegex(ed.DestinationMisconfigured, "pre_cutover"):
            self.resolve("pre_cutover", repository=EVIDENCE)

    def test_v3_private_with_proven_remote_is_accepted(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        self.assertEqual((dest.repository, dest.phase), (EVIDENCE, "private"))

    def test_v4_private_naming_the_source_is_rejected(self) -> None:
        with self.assertRaisesRegex(ed.DestinationMisconfigured, "private"):
            self.resolve("private", repository=SOURCE, remote=str(self.public))

    def test_v5_missing_repository_is_rejected(self) -> None:
        manifest = manifest_with()
        del manifest["evidence"]["repository"]
        with self.assertRaises(ed.DestinationMisconfigured):
            ed.resolve_destination(manifest, evidence_remote=None, repo_root=self.work)

    def test_v5_missing_block_is_rejected(self) -> None:
        manifest = manifest_with()
        del manifest["evidence"]
        with self.assertRaises(ed.DestinationMisconfigured):
            ed.resolve_destination(manifest, evidence_remote=None, repo_root=self.work)

    def test_v6_private_without_remote_never_uses_the_checkouts_own(self) -> None:
        with self.assertRaisesRegex(ed.DestinationMisconfigured, "explicit evidence remote"):
            self.resolve("private")
        self.assertEqual(self.refs(self.public) + self.refs(self.private), [])

    def test_v7_missing_or_unknown_phase_is_rejected(self) -> None:
        for phase in (None, "", "public", "Private"):
            manifest = manifest_with()
            if phase is None:
                del manifest["evidence"]["phase"]
            else:
                manifest["evidence"]["phase"] = phase
            with self.assertRaises(ed.DestinationMisconfigured, msg=repr(phase)):
                ed.resolve_destination(manifest, evidence_remote=None, repo_root=self.work)

    def test_v8_identity_mismatch_is_rejected_with_no_retry_elsewhere(self) -> None:
        with self.assertRaisesRegex(ed.DestinationMisconfigured, "not the declared evidence repository"):
            self.resolve("private", remote=str(self.public))

    def test_v9_embedded_credentials_are_rejected_and_never_echoed(self) -> None:
        for url in (f"https://user:tok3n@github.com/{EVIDENCE}.git", f"https://tok3n@github.com/{EVIDENCE}.git"):
            with self.assertRaises(ed.DestinationMisconfigured) as ctx:
                self.resolve("private", remote=url)
            self.assertNotIn("tok3n", str(ctx.exception))

    def test_a_local_path_is_refused_unless_the_test_harness_opts_in(self) -> None:
        with mock.patch.dict("os.environ", {ed.TEST_LOCAL_REMOTES_ENV: ""}):
            with self.assertRaisesRegex(ed.DestinationMisconfigured, "local evidence remote"):
                self.resolve("private", remote=str(self.private))

    def test_ssh_and_https_urls_prove_by_path(self) -> None:
        for url in (f"git@github.com:{EVIDENCE}.git", f"https://github.com/{EVIDENCE}", f"ssh://git@github.com/{EVIDENCE}.git"):
            self.assertEqual(self.resolve("private", remote=url).repository, EVIDENCE)
        with self.assertRaises(ed.DestinationMisconfigured):  # a repo that merely ends with the same text
            self.resolve("private", remote=f"git@github.com:evil/not-{EVIDENCE.split('/')[1]}.git")

    def test_f1_a_foreign_host_or_path_prefix_never_proves_the_identity(self) -> None:
        for url in (
            f"https://evil.example/{EVIDENCE}.git",
            f"https://github.com/x/{EVIDENCE}",
            f"git@evil.example:{EVIDENCE}.git",
            f"ssh://git@github.com.evil.example/{EVIDENCE}.git",
            f"https://github.com/{EVIDENCE}-fork",
        ):
            with self.assertRaises(ed.DestinationMisconfigured, msg=url):
                self.resolve("private", remote=url)

    def test_redaction_hides_userinfo(self) -> None:
        self.assertNotIn("secret", ed.redact("https://u:secret@github.com/a/b"))


class PrivateRoutingTests(Stores):
    def test_seal_lands_only_in_the_private_store(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        commit = dest.seal(HANDOFF, FILES, "check")
        self.assertEqual(self.refs(self.private), [f"refs/heads/{HANDOFF}"])
        self.assertEqual(self.refs(self.public), [])  # nothing is pushed to the source repository
        self.assertEqual(_git(self.private, "rev-parse", f"refs/heads/{HANDOFF}"), commit)

    def test_sealed_content_hash_is_the_same_in_either_store(self) -> None:
        public = self.resolve("pre_cutover", remote=str(self.public))
        private = self.resolve("private", remote=str(self.private))
        a = public.seal(HANDOFF, FILES, "check")
        b = private.seal(HANDOFF, FILES, "check")
        self.assertEqual(
            _git(self.public, "rev-parse", f"{a}^{{tree}}"), _git(self.private, "rev-parse", f"{b}^{{tree}}")
        )  # I3: no storage-location field is sealed

    def test_an_existing_ref_is_a_refusal_and_the_run_unsealed(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        dest.seal(HANDOFF, FILES, "check")
        with self.assertRaises(ed.StoreUnavailable):
            dest.seal(HANDOFF, {seal.HANDOFF_CHECK_FILE: b"other\n"}, "again")

    def test_a_ref_outside_the_registry_is_refused_before_any_push(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        for ref in ("claude/other-thing-1", "claude/benchmark-result-", "main", "benchmark-history"):
            with self.assertRaises(ed.DestinationMisconfigured, msg=ref):
                dest.seal(ref, FILES, "x")
        self.assertEqual(self.refs(self.private), [])

    def test_stop_condition_counts_only_the_resolved_store(self) -> None:
        public = self.resolve("pre_cutover", remote=str(self.public))
        private = self.resolve("private", remote=str(self.private))
        public.seal("claude/severity-observation-20261001T050000Z-aaaaaaaaaaaa", FILES, "p")
        private.seal("claude/severity-observation-20261002T050000Z-bbbbbbbbbbbb", FILES, "q")
        private.seal("claude/severity-trial-20261003T050000Z-cccccccccccc", FILES, "t")
        self.assertEqual(private.list_refs("claude/severity-observation-"), ["claude/severity-observation-20261002T050000Z-bbbbbbbbbbbb"])
        self.assertEqual(len(public.list_refs("claude/severity-observation-")), 1)

    def test_baseline_history_is_read_from_the_destination_branch(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        history = dest.history()
        self.assertEqual((history.remote, history.branch), (str(self.private), "benchmark-history"))

    def test_every_registered_namespace_is_writable(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        for index, ns in enumerate(NAMESPACES):
            dest.seal(f"{ns}2026101{index}T000000Z-aaaaaaaaaaaa", FILES, "n")
        self.assertEqual(len(self.refs(self.private)), len(NAMESPACES))


class FailureTests(Stores):
    def test_v10_unreachable_store_fails_the_preflight_and_writes_nothing(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        _git(self.work, "config", "advice.detachedHead", "false")
        self.private.rename(self.private.with_name("moved.git"))
        with self.assertRaises(ed.StoreUnavailable) as ctx:
            dest.preflight()
        self.assertEqual(ctx.exception.status, ed.STATUS_UNAVAILABLE)
        self.assertEqual(self.refs(self.public), [])

    def test_a_failed_stop_condition_read_is_never_zero_refs(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        self.private.rename(self.private.with_name("moved.git"))
        with self.assertRaises(ed.StoreUnavailable):
            dest.list_refs("claude/severity-observation-")

    def test_an_unconfirmed_readback_is_reported_as_seal_unconfirmed(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        with mock.patch.object(seal, "seal_to_ref", side_effect=seal.SealUnconfirmedError("read-back failed")):
            with self.assertRaises(ed.StoreUnavailable) as ctx:
                dest.seal(HANDOFF, FILES, "x")
        self.assertEqual(ctx.exception.status, ed.STATUS_UNCONFIRMED)

    def test_a_seal_failure_keeps_a_redacted_excerpt_for_the_operator(self) -> None:
        dest = self.resolve("private", remote=str(self.private))
        with mock.patch.object(seal, "seal_to_ref", side_effect=seal.SealError("git push failed: remote rejected https://u:p@h/x")):
            with self.assertRaises(ed.StoreUnavailable) as ctx:
                dest.seal(HANDOFF, FILES, "x")
        self.assertIn("rejected", str(ctx.exception))
        self.assertNotIn("u:p", str(ctx.exception))

    def test_error_classes_carry_no_url_text(self) -> None:
        self.assertEqual(ed.classify_git_error("fatal: Authentication failed for 'https://u:p@h/x'"), "unauthorized")
        self.assertEqual(ed.classify_git_error("! [remote rejected] x (protected branch hook declined)"), "rejected")


class EntrypointExitTests(Stores):
    def _run(self, module, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(module, "REPO_ROOT", self.work), redirect_stdout(out), redirect_stderr(err):
            code = module.main(argv)
        return code, out.getvalue(), err.getvalue()

    def _private_manifest(self, name: str = "m.json") -> list[str]:
        path = Path(self._tmp.name) / name
        path.write_text(json.dumps(manifest_with("private")), encoding="utf-8")
        return ["--manifest", str(path)]

    def test_auth_check_to_a_proven_private_remote_seals_only_there(self) -> None:
        code, out, _ = self._run(routine, [*self._private_manifest(), "--mode", "auth-check", "--evidence-remote", str(self.private)])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["ref"].startswith(seal.HANDOFF_CHECK_REF_PREFIX))
        self.assertEqual(len(self.refs(self.private)), 1)
        self.assertEqual(self.refs(self.public), [])

    def test_private_phase_without_a_remote_exits_2_and_pushes_nothing(self) -> None:
        code, _, err = self._run(routine, [*self._private_manifest(), "--mode", "auth-check"])
        self.assertEqual(code, ed.EXIT_MISCONFIGURED)
        self.assertIn(ed.STATUS_MISCONFIGURED, err)
        self.assertEqual(self.refs(self.public) + self.refs(self.private), [])

    def test_pointing_a_private_run_at_the_source_exits_2(self) -> None:
        code, _, _ = self._run(routine, [*self._private_manifest(), "--mode", "auth-check", "--evidence-remote", str(self.public)])
        self.assertEqual(code, 2)
        self.assertEqual(self.refs(self.public), [])

    def test_unreachable_private_store_exits_3_before_any_push(self) -> None:
        self.private.rename(self.private.with_name("moved.git"))
        code, out, _ = self._run(routine, [*self._private_manifest(), "--mode", "auth-check", "--evidence-remote", str(self.private)])
        self.assertEqual(code, ed.EXIT_UNAVAILABLE)
        self.assertEqual(json.loads(out)["status"], ed.STATUS_UNAVAILABLE)
        self.assertEqual(self.refs(self.public), [])

    def test_pre_cutover_without_a_remote_still_seals_to_the_source(self) -> None:
        code, _, _ = self._run(routine, ["--mode", "auth-check"])  # F9a: existing prompts keep working
        self.assertEqual(code, 0)
        self.assertEqual(len(self.refs(self.public)), 1)

    def test_invalid_evidence_block_in_the_manifest_exits_2(self) -> None:
        bad = manifest_with("private", SOURCE)
        path = Path(self._tmp.name) / "bad.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        code, _, _ = self._run(routine, ["--manifest", str(path), "--mode", "auth-check", "--evidence-remote", str(self.private)])
        self.assertEqual(code, 2)

    def test_the_severity_stop_condition_reads_the_private_store_and_fails_closed(self) -> None:
        argv = [*self._private_manifest(), "--trigger", "scheduled", "--cli", "fake", "--evidence-remote", str(self.private)]
        self.private.rename(self.private.with_name("moved.git"))
        code, _, _ = self._run(obs, argv)
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
