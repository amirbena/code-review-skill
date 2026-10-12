"""The temporary P7 comment-lifecycle probe (issue #719): lifecycle, targeting, identity, cleanup and public-log safety."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from typing import Any

from runtime_platform.benchmark.publisher import cli, comment_probe as probe, github_api
from tests.support.evidence_destination import manifest_with
from tests.unit.benchmark.test_benchmark_publisher_github_api import _Response

SLUG = "benchmark-publication"
BOT = f"{SLUG}[bot]"
TOKEN = "ghs_SENTINELtokenvalue"
SENTINEL_ID = 987654321
SENTINEL_LOGIN = "SENTINEL-login-7f3a"
SENTINEL_BODY = "SENTINEL-private-issue-content"
ERROR_SENTINEL = "SENTINEL-raw-error-body"
COMMENTS = f"/repos/{probe.PROBE_REPOSITORY}/issues/{probe.PROBE_ISSUE}/comments"
ONE = f"/repos/{probe.PROBE_REPOSITORY}/issues/comments/{SENTINEL_ID}"
ISSUE_URL = f"https://api.github.com/repos/{probe.PROBE_REPOSITORY}/issues/{probe.PROBE_ISSUE}"


class FakeGitHub:
    """A stateful stand-in for the comments API; `fail` maps (method, path-kind, nth) to a status, `tweak` edits a GET answer."""

    def __init__(self, *, fail: dict[tuple[str, int], int] | None = None, login: str = BOT, user_type: str = "Bot",
                 issue_url: str = ISSUE_URL, read_id: int = SENTINEL_ID, delete_leaves_comment: bool = False) -> None:
        self.comment: dict[str, Any] | None = None
        self.fail, self.login, self.user_type, self.issue_url = fail or {}, login, user_type, issue_url
        self.read_id, self.delete_leaves_comment = read_id, delete_leaves_comment
        self.requests: list[tuple[str, str, Any, str]] = []
        self.counts: dict[str, int] = {}

    def _view(self, **extra: Any) -> dict[str, Any]:
        assert self.comment is not None
        return {"id": self.read_id, "body": self.comment["body"], "issue_url": self.issue_url,
                "user": {"login": self.login, "type": self.user_type}, "html_url": "https://example.invalid/x", **extra}

    def __call__(self, request: Any, timeout: float = 0) -> _Response:
        method, path = request.get_method(), request.full_url.split("?")[0].removeprefix(github_api.API)
        body = json.loads(request.data) if request.data else None
        self.requests.append((method, path, body, dict(request.header_items()).get("Authorization", "")))
        self.counts[method] = n = self.counts.get(method, 0) + 1
        status = self.fail.get((method, n))
        if status is not None:
            raise urllib.error.HTTPError(request.full_url, status, "err", {}, io.BytesIO(ERROR_SENTINEL.encode()))  # type: ignore[arg-type]
        if method == "POST" and path == COMMENTS:
            self.comment = {"body": body["body"]}
            return _Response(201, json.dumps(self._view()).encode())
        if path == ONE and method == "GET":
            if self.comment is None:
                raise urllib.error.HTTPError(request.full_url, 404, "nf", {}, io.BytesIO(b"{}"))  # type: ignore[arg-type]
            return _Response(200, json.dumps(self._view()).encode())
        if path == ONE and method == "PATCH":
            self.comment = {"body": body["body"]}
            return _Response(200, json.dumps(self._view()).encode())
        if path == ONE and method == "DELETE":
            if not self.delete_leaves_comment:
                self.comment = None
            return _Response(204, b"")
        raise AssertionError(f"unexpected request {method} {path}")

    def kinds(self) -> list[str]:
        return [f"{m} {'comments' if p == COMMENTS else 'one'}" for m, p, _, _ in self.requests]


def _run(fake: FakeGitHub) -> probe.ProbeResult:
    return probe.run_probe(github_api.GitHubClient(TOKEN, opener=fake), SLUG)


class LifecycleTests(unittest.TestCase):
    def test_the_exact_lifecycle_passes(self) -> None:
        fake = FakeGitHub()
        result = _run(fake)
        self.assertTrue(result.passed)
        self.assertEqual(set(result.steps.values()), {probe.OK})
        self.assertEqual(result.cleanup, probe.NOT_NEEDED)
        self.assertEqual(fake.kinds(), ["POST comments", "GET one", "PATCH one", "GET one", "DELETE one", "GET one"])
        self.assertIsNone(fake.comment)

    def test_the_comment_is_recognizable_and_edited_in_place(self) -> None:
        fake = FakeGitHub()
        _run(fake)
        self.assertIn("p7-probe", fake.requests[0][2]["body"])
        self.assertIn("p7-probe", fake.requests[2][2]["body"])
        self.assertNotEqual(fake.requests[0][2]["body"], fake.requests[2][2]["body"])

    def test_only_the_pinned_repository_and_issue_are_addressed_and_the_supplied_token_is_used(self) -> None:
        fake = FakeGitHub()
        _run(fake)
        for method, path, _, auth in fake.requests:
            self.assertTrue(path.startswith(f"/repos/{probe.PROBE_REPOSITORY}/issues/"), path)
            self.assertIn(method, {"GET", "POST", "PATCH", "DELETE"})
            self.assertEqual(auth, f"Bearer {TOKEN}")
        self.assertEqual({p for _, p, _, _ in fake.requests}, {COMMENTS, ONE})
        self.assertEqual(probe.PROBE_ISSUE, 1)
        self.assertEqual(probe.PROBE_REPOSITORY, "amirbena/code-review-skill-evidence")

    def test_only_the_comment_the_run_created_is_ever_modified(self) -> None:
        fake = FakeGitHub()
        _run(fake)
        modified = {p for m, p, _, _ in fake.requests if m in {"PATCH", "DELETE"}}
        self.assertEqual(modified, {ONE})


class IdentityAndIntegrityTests(unittest.TestCase):
    def assertFails(self, fake: FakeGitHub, step: str) -> probe.ProbeResult:
        result = _run(fake)
        self.assertFalse(result.passed)
        self.assertEqual(result.steps[step], probe.FAIL)
        return result

    def test_a_comment_authored_by_someone_else_fails_and_is_cleaned_up(self) -> None:
        fake = FakeGitHub(login="amirbena", user_type="User")
        result = self.assertFails(fake, "read-back")
        self.assertEqual(result.cleanup, probe.CLEANED)
        self.assertEqual(result.steps["patch"], probe.SKIPPED)
        self.assertIsNone(fake.comment)

    def test_a_bot_login_that_is_not_the_publication_app_fails(self) -> None:
        self.assertFails(FakeGitHub(login="other-app[bot]"), "read-back")

    def test_a_non_bot_user_type_fails(self) -> None:
        self.assertFails(FakeGitHub(user_type="User"), "read-back")

    def test_a_changed_comment_id_fails(self) -> None:
        self.assertFails(FakeGitHub(read_id=SENTINEL_ID + 1), "read-back")

    def test_a_comment_on_another_issue_fails(self) -> None:
        self.assertFails(FakeGitHub(issue_url=ISSUE_URL.replace("/issues/1", "/issues/2")), "read-back")


class FailureAndCleanupTests(unittest.TestCase):
    def test_a_refused_post_fails_with_nothing_to_clean(self) -> None:
        fake = FakeGitHub(fail={("POST", 1): 403})
        result = _run(fake)
        self.assertEqual(result.steps["post"], probe.FAIL)
        self.assertEqual(set(list(result.steps.values())[1:]), {probe.SKIPPED})
        self.assertEqual(result.cleanup, probe.NOT_NEEDED)
        self.assertEqual(fake.kinds(), ["POST comments"])
        self.assertFalse(result.passed)

    def test_a_failing_patch_deletes_the_created_comment(self) -> None:
        fake = FakeGitHub(fail={("PATCH", 1): 500})
        result = _run(fake)
        self.assertEqual(result.steps["patch"], probe.FAIL)
        self.assertEqual(result.cleanup, probe.CLEANED)
        self.assertIsNone(fake.comment)
        self.assertFalse(result.passed)

    def test_a_failed_cleanup_is_reported_and_never_a_pass(self) -> None:
        fake = FakeGitHub(fail={("PATCH", 1): 500, ("DELETE", 1): 500})
        result = _run(fake)
        self.assertEqual(result.cleanup, probe.CLEANUP_FAILED)
        self.assertFalse(result.passed)

    def test_a_failed_delete_is_retried_as_cleanup(self) -> None:
        fake = FakeGitHub(fail={("DELETE", 1): 500})
        result = _run(fake)
        self.assertEqual(result.steps["delete"], probe.FAIL)
        self.assertEqual(result.cleanup, probe.CLEANED)
        self.assertIsNone(fake.comment)

    def test_a_comment_that_survives_delete_fails_the_deleted_check_and_is_cleaned(self) -> None:
        fake = FakeGitHub(delete_leaves_comment=True)
        result = _run(fake)
        self.assertEqual(result.steps["deleted"], probe.FAIL)
        self.assertEqual(result.cleanup, probe.CLEANED)
        self.assertFalse(result.passed)

    def test_a_network_error_is_a_failure_code_not_an_exception(self) -> None:
        def opener(request: Any, timeout: float = 0) -> Any:
            raise urllib.error.URLError(ERROR_SENTINEL)

        result = probe.run_probe(github_api.GitHubClient(TOKEN, opener=opener), SLUG)
        self.assertEqual(result.steps["post"], probe.FAIL)
        self.assertFalse(result.passed)


def _cli(env: dict[str, str], fake: FakeGitHub | None = None, phase: str = "pre_cutover", argv: list[str] | None = None) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "manifest.json"
        manifest.write_text(json.dumps(manifest_with(phase)), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        factory = (lambda token: github_api.GitHubClient(token, opener=fake)) if fake is not None else None
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv or ["probe-comment-lifecycle", "--manifest", str(manifest)], env=env, comment_client=factory)
    return code, out.getvalue(), err.getvalue()


ENV = {"BENCHMARK_ISSUES_TOKEN": TOKEN, "BENCHMARK_APP_SLUG": SLUG}


class PublicLogTests(unittest.TestCase):
    def test_a_pass_prints_only_fixed_codes(self) -> None:
        code, out, err = _cli(ENV, FakeGitHub())
        self.assertEqual(code, 0)
        self.assertEqual(
            out.splitlines(),
            [f"p7-probe: {s}=ok" for s in probe.STEPS] + ["p7-probe: cleanup=not-needed", "p7-probe: verdict=pass"],
        )
        self.assertEqual(err, "")

    def test_nothing_from_github_or_the_credentials_reaches_either_stream_in_any_phase(self) -> None:
        sentinels = (TOKEN, str(SENTINEL_ID), SENTINEL_LOGIN, SENTINEL_BODY, ERROR_SENTINEL, probe.PROBE_REPOSITORY, BOT)
        for phase in ("pre_cutover", "private"):
            for fake in (FakeGitHub(), FakeGitHub(login=SENTINEL_LOGIN, user_type="User"), FakeGitHub(fail={("POST", 1): 403}),
                         FakeGitHub(fail={("PATCH", 1): 500, ("DELETE", 1): 500})):
                _, out, err = _cli(ENV, fake, phase)
                for sentinel in sentinels:
                    self.assertNotIn(sentinel, out + err, (phase, sentinel))
                for line in out.splitlines():
                    self.assertRegex(line, r"^p7-probe: [a-z-]+=[a-z-]+$")

    def test_a_failure_exits_one_with_a_fail_verdict(self) -> None:
        code, out, _ = _cli(ENV, FakeGitHub(login="x[bot]"))
        self.assertEqual(code, 1)
        self.assertIn("p7-probe: verdict=fail", out)

    def test_a_missing_or_personal_token_is_refused_before_any_request(self) -> None:
        for token in (None, "", "ghp_personaltoken", "github_pat_x"):
            fake = FakeGitHub()
            env = {"BENCHMARK_APP_SLUG": SLUG, **({"BENCHMARK_ISSUES_TOKEN": token} if token is not None else {})}
            code, out, err = _cli(env, fake)
            self.assertEqual(code, 2)
            self.assertEqual(fake.requests, [])
            self.assertNotIn("p7-probe", out)
            self.assertNotIn("ghp_personaltoken", out + err)

    def test_a_missing_app_slug_is_refused_before_any_request(self) -> None:
        fake = FakeGitHub()
        code, _, _ = _cli({"BENCHMARK_ISSUES_TOKEN": TOKEN}, fake)
        self.assertEqual(code, 2)
        self.assertEqual(fake.requests, [])

    def test_the_probe_ignores_every_other_credential(self) -> None:
        fake = FakeGitHub()
        env = {**ENV, "BENCHMARK_CONTENTS_TOKEN": "ghs_other", "BENCHMARK_READ_TOKEN": "ghs_other", "GH_TOKEN": "ghp_personal"}
        _cli(env, fake)
        self.assertEqual({a for *_, a in fake.requests}, {f"Bearer {TOKEN}"})


class NoPermanentBehaviorChangeTests(unittest.TestCase):
    def test_existing_commands_are_unchanged_and_the_manifest_is_still_pre_cutover(self) -> None:
        parser = cli.build_arg_parser()
        for command in ("sweep", "watchdog", "resolve-evidence"):
            self.assertIn(command, parser._subparsers._group_actions[0].choices)  # noqa: SLF001
        manifest = json.loads((Path(cli.__file__).parents[1] / "schedule" / "expected-run-manifest.json").read_text())
        self.assertEqual(manifest["evidence"]["phase"], "pre_cutover")

    def test_the_probe_never_builds_publication_ports(self) -> None:
        called: list[Any] = []
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "m.json"
            manifest.write_text(json.dumps(manifest_with("private")), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["probe-comment-lifecycle", "--manifest", str(manifest)], env=ENV,
                         ports_factory=lambda *a: called.append(a),  # type: ignore[arg-type,return-value]
                         comment_client=lambda t: github_api.GitHubClient(t, opener=FakeGitHub()))
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
