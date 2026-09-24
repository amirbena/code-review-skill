"""Tests for the #528 finalization gate: the GitHub Release is created only
after distribution, idempotently, and the plan refuses to move past an
unfinalized version."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.unit.release._shared import COVERED_CHANGELOG, _FakeGit, rw

SHA = "a" * 40
VERSION = "1.60.0"
TAG = f"v{VERSION}"
ASSETS = ("local-code-review-skill.zip", "github-pr-review-skill.zip")


def _tag_refs(sha: str = SHA, tag: str = TAG) -> str:
    return f"tagobj\trefs/tags/{tag}\n{sha}\trefs/tags/{tag}^{{}}\n"


class _FakeGh:
    """Stand-in for gitgh._gh: a scripted Release (or none) plus a call log."""

    def __init__(self, release: dict | None = None, *, error: str | None = None) -> None:
        self.release = release
        self.error = error
        self.mutations: list[list[str]] = []

    def __call__(self, args, repo_root):  # noqa: ANN001 - test shim
        a = list(args)
        if a[:2] == ["release", "view"]:
            if self.error:
                raise subprocess.CalledProcessError(1, ["gh", *a], stderr=self.error)
            if self.release is None:
                raise subprocess.CalledProcessError(1, ["gh", *a], stderr="release not found")
            return json.dumps(self.release)
        if a[:1] == ["release"] and a[1] in ("create", "upload", "edit"):
            self.mutations.append(a)
            return ""
        raise AssertionError(f"unexpected gh call: {a}")


class _Case(unittest.TestCase):
    def setUp(self) -> None:
        real_git, real_gh = rw.gitgh._git, rw.gitgh._gh
        self.addCleanup(setattr, rw.gitgh, "_git", real_git)
        self.addCleanup(setattr, rw.gitgh, "_gh", real_gh)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.paths = []
        for name in ASSETS:
            path = self.tmp / name
            path.write_bytes(f"zip:{name}".encode())
            self.paths.append(str(path))
        (self.tmp / "notes.md").write_text("notes\n")

    def digest(self, name: str, body: str | None = None) -> str:
        return "sha256:" + hashlib.sha256((body or f"zip:{name}").encode()).hexdigest()

    def release(self, **overrides) -> dict:
        data = {
            "tagName": TAG,
            "targetCommitish": SHA,
            "isDraft": False,
            "isPrerelease": False,
            "assets": [{"name": n, "digest": self.digest(n), "state": "uploaded"} for n in ASSETS],
        }
        data.update(overrides)
        return data

    def good_git(self, **overrides) -> _FakeGit:
        base = dict(
            rev_parse=SHA + "\n",
            ls_remote_tags=_tag_refs(),
            ls_remote_main="c" * 40 + "\trefs/heads/main\n",
        )
        base.update(overrides)
        return _FakeGit(**base)

    def run_cli(self, git, gh, *argv: str) -> tuple[int, str]:
        rw.gitgh._git, rw.gitgh._gh = git, gh
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = rw.main(list(argv))
        return code, out.getvalue()

    def assets(self) -> list[str]:
        return [arg for path in self.paths for arg in ("--asset", path)]


class ReleaseFinalizeTests(_Case):
    def finalize(self, git, gh) -> tuple[int, str]:
        return self.run_cli(
            git, gh, "release-finalize", "--version", VERSION, "--expected-sha", SHA,
            "--notes-file", str(self.tmp / "notes.md"), *self.assets(),
        )

    def test_creates_the_release_from_the_existing_tag_with_the_build(self) -> None:
        gh = _FakeGh(None)
        code, out = self.finalize(self.good_git(), gh)
        self.assertEqual(code, 0, out)
        self.assertIn("created", out)
        [create] = gh.mutations
        self.assertEqual(create[:3], ["release", "create", TAG])
        self.assertIn("--verify-tag", create)
        self.assertEqual(create[-2:], self.paths)

    def test_existing_matching_release_is_a_no_op(self) -> None:
        gh = _FakeGh(self.release())
        code, out = self.finalize(self.good_git(), gh)
        self.assertEqual(code, 0, out)
        self.assertIn("unchanged", out)
        self.assertEqual(gh.mutations, [])

    def test_digest_mismatch_fails_without_mutation(self) -> None:
        release = self.release()
        release["assets"][0]["digest"] = self.digest(ASSETS[0], "other bytes")
        gh = _FakeGh(release)
        code, out = self.finalize(self.good_git(), gh)
        self.assertEqual(code, 1)
        self.assertIn("digest", out)
        self.assertEqual(gh.mutations, [])

    def test_target_or_extra_asset_mismatch_fails_without_mutation(self) -> None:
        for release in (
            self.release(targetCommitish="b" * 40),
            self.release(assets=self.release()["assets"] + [{"name": "x.zip", "digest": "sha256:0"}]),
            self.release(isPrerelease=True),
        ):
            with self.subTest(release=release):
                gh = _FakeGh(release)
                code, _ = self.finalize(self.good_git(), gh)
                self.assertEqual(code, 1)
                self.assertEqual(gh.mutations, [])

    def test_partial_release_is_completed_with_only_the_missing_asset(self) -> None:
        release = self.release(isDraft=True)
        release["assets"] = release["assets"][:1]
        gh = _FakeGh(release)
        code, out = self.finalize(self.good_git(), gh)
        self.assertEqual(code, 0, out)
        self.assertIn("completed", out)
        self.assertEqual(gh.mutations[0], ["release", "upload", TAG, self.paths[1]])
        self.assertEqual(gh.mutations[1], ["release", "edit", TAG, "--draft=false"])

    def test_source_tag_not_at_the_release_commit_publishes_nothing(self) -> None:
        gh = _FakeGh(None)
        code, out = self.finalize(self.good_git(ls_remote_tags=_tag_refs("b" * 40)), gh)
        self.assertEqual(code, 1)
        self.assertIn("nothing was published", out)
        self.assertEqual(gh.mutations, [])

    def test_release_commit_dropped_from_main_publishes_nothing(self) -> None:
        gh = _FakeGh(None)
        code, _ = self.finalize(self.good_git(is_ancestor=False), gh)
        self.assertEqual(code, 1)
        self.assertEqual(gh.mutations, [])

    def test_unreadable_release_is_not_mistaken_for_a_missing_one(self) -> None:
        gh = _FakeGh(error="HTTP 502")
        code, _ = self.finalize(self.good_git(), gh)
        self.assertEqual(code, 1)
        self.assertEqual(gh.mutations, [])


class ReleaseVerifyReleaseStageTests(_Case):
    def verify(self, gh, git=None) -> tuple[int, str]:
        return self.run_cli(
            git or self.good_git(), gh, "release-verify", "--version", VERSION, "--expected-sha", SHA,
            "--main-ancestor", *self.assets(),
        )

    def test_matching_release_passes_with_main_advanced(self) -> None:
        code, out = self.verify(_FakeGh(self.release()))
        self.assertEqual(code, 0, out)

    def test_missing_draft_or_mismatched_release_fails(self) -> None:
        mismatched = self.release()
        mismatched["assets"][1]["digest"] = "sha256:" + "0" * 64
        for gh in (_FakeGh(None), _FakeGh(self.release(isDraft=True)), _FakeGh(mismatched)):
            with self.subTest(release=gh.release):
                self.assertEqual(self.verify(gh)[0], 1)


class RecoverReleaseTagTests(_Case):
    class _TaggingGit(_FakeGit):
        """The tag appears on origin once it is pushed."""

        def __call__(self, args, repo_root):  # noqa: ANN001 - test shim
            a = list(args)
            if a[:1] == ["push"]:
                self.ls_remote_tags = _tag_refs()
                self.rev_parse = SHA + "\n"
            return super().__call__(a, repo_root)

    def recover(self, git) -> tuple[int, str]:
        return self.run_cli(git, _FakeGh(), "recover-release-tag", "--version", VERSION, "--expected-sha", SHA)

    def untagged(self, **overrides) -> _FakeGit:
        base = dict(
            log=f"chore(release): {TAG} [skip ci]\n",
            ls_remote_main="c" * 40 + "\trefs/heads/main\n",
        )
        base.update(overrides)
        return self._TaggingGit(**base)

    def test_tags_the_release_commit_and_verifies(self) -> None:
        git = self.untagged()
        code, out = self.recover(git)
        self.assertEqual(code, 0, out)
        self.assertIn(["tag", "-a", TAG, SHA, "-m", f"Release {TAG}"], git.calls)
        self.assertIn(["push", "origin", f"refs/tags/{TAG}"], git.calls)

    def test_refuses_a_commit_that_is_not_the_release_commit(self) -> None:
        git = self.untagged(log="Some merge (#12)\n")
        code, out = self.recover(git)
        self.assertEqual(code, 1)
        self.assertIn("is not the release commit", out)
        self.assertFalse(any(c[:2] == ["tag", "-a"] for c in git.calls))

    def test_refuses_a_commit_outside_main(self) -> None:
        git = self.untagged(is_ancestor=False)
        self.assertEqual(self.recover(git)[0], 1)
        self.assertFalse(any(c[:1] == ["push"] for c in git.calls))

    def test_existing_tag_is_never_moved(self) -> None:
        at_release = self.good_git(tag_list=f"{TAG}\n")
        self.assertEqual(self.recover(at_release)[0], 0)
        elsewhere = self.good_git(tag_list=f"{TAG}\n", rev_parse="b" * 40 + "\n", ls_remote_tags=_tag_refs("b" * 40))
        code, out = self.recover(elsewhere)
        self.assertEqual(code, 1)
        self.assertIn("never moved", out)
        for git in (at_release, elsewhere):
            self.assertFalse(any(c[:1] == ["push"] or c[:2] == ["tag", "-a"] for c in git.calls))


class PlanRefusesUnfinalizedVersionTests(_Case):
    def plan(self, git, gh, event: str = "push") -> tuple[int, dict, str]:
        changelog = self.tmp / "CHANGELOG.md"
        changelog.write_text(COVERED_CHANGELOG)
        out = self.tmp / "gh-out.txt"
        out.unlink(missing_ok=True)
        code, text = self.run_cli(
            git, gh, "--changelog", str(changelog), "auto-release-plan",
            "--event-name", event, "--github-output", str(out),
        )
        outputs = dict(line.split("=", 1) for line in out.read_text().splitlines()) if out.is_file() else {}
        return code, outputs, text

    def git(self, **overrides) -> _FakeGit:
        base = dict(sorted_tags=f"{TAG}\n", rev_parse=SHA + "\n", ls_remote_dist=_tag_refs(), diff="")
        base.update(overrides)
        return _FakeGit(**base)

    def test_finalized_latest_version_plans_normally(self) -> None:
        code, outputs, _ = self.plan(self.git(), _FakeGh(self.release()))
        self.assertEqual(code, 0)
        self.assertNotIn("recover", outputs)
        self.assertIn("no release-worthy changes", outputs["reason"])

    def test_push_with_no_release_fails_closed_and_names_recovery(self) -> None:
        code, outputs, text = self.plan(self.git(), _FakeGh(None))
        self.assertEqual(code, 1)
        self.assertEqual(outputs["should_release"], "false")
        self.assertNotIn("version", outputs)
        self.assertIn("workflow_dispatch", text)
        self.assertIn(TAG, outputs["reason"])

    def test_push_with_no_distribution_tag_fails_closed(self) -> None:
        code, outputs, _ = self.plan(self.git(ls_remote_dist=""), _FakeGh(self.release()))
        self.assertEqual(code, 1)
        self.assertIn("distribution tag", outputs["reason"])

    def test_push_with_a_release_missing_an_archive_fails_closed(self) -> None:
        release = self.release()
        release["assets"] = release["assets"][:1]
        self.assertEqual(self.plan(self.git(), _FakeGh(release))[0], 1)

    def test_dispatch_hands_the_same_version_to_recovery(self) -> None:
        code, outputs, _ = self.plan(self.git(), _FakeGh(None), event="workflow_dispatch")
        self.assertEqual(code, 0)
        self.assertEqual(outputs["should_release"], "false")
        self.assertEqual(outputs["recover"], "finalize")
        self.assertEqual(outputs["recover_version"], VERSION)
        self.assertEqual(outputs["recover_sha"], SHA)
        self.assertNotIn("version", outputs)

    def test_unreadable_state_fails_closed(self) -> None:
        code, outputs, _ = self.plan(self.git(), _FakeGh(error="HTTP 502"))
        self.assertEqual(code, 1)
        self.assertEqual(outputs["should_release"], "false")

    def test_pre_distribution_releases_are_exempt(self) -> None:
        git = self.git(sorted_tags="v1.55.0\n", ls_remote_dist="")
        code, outputs, _ = self.plan(git, _FakeGh(error="must not be read"))
        self.assertEqual(code, 0)
        self.assertNotIn("recover", outputs)


if __name__ == "__main__":
    unittest.main()
