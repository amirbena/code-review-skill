"""Mocked-boundary tests for the Commit Status publisher, driven from the #34 reference model."""

from __future__ import annotations

import inspect
import itertools
import json
import unittest

from scripts.github_integration import boundary as b
from scripts.github_integration import status_publisher as sp
from tests.reference.review import review_action_authorization as raa
from tests.reference.review import review_status_enforcement as rse

REPO = "octo/repo"
PR = 42
SHA_A = "a" * 40
SHA_B = "b" * 40


class FakeGitHub:
    """Transport stub that serves the PR HEAD, the combined status, and status writes."""

    def __init__(self, live_head=SHA_A, existing=None, write_errors=()):
        self.live_head = live_head
        self.statuses = list(existing or [])
        self.write_errors = list(write_errors)
        self.calls: list[tuple[str, str, str | None]] = []

    def __call__(self, args, env, stdin):
        method, endpoint = args[1], args[2]
        self.calls.append((method, endpoint, stdin))
        if method == "GET" and endpoint.startswith(f"repos/{REPO}/pulls/"):
            return b.RawResponse(200, json.dumps({"head": {"sha": self.live_head}}))
        if method == "GET" and "/status" in endpoint:
            return b.RawResponse(200, json.dumps({"statuses": self.statuses}))
        if method == "POST" and "/statuses/" in endpoint:
            if self.write_errors:
                return self.write_errors.pop(0)
            payload = json.loads(stdin)
            self.statuses = [s for s in self.statuses if s["context"] != payload["context"]]
            self.statuses.append(payload)
            return b.RawResponse(201, "{}")
        raise AssertionError(f"unexpected call {method} {endpoint}")

    @property
    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]


def run(fake, reasoning=rse.Reasoning.CLEAN, *, head=SHA_A, **kw):
    kw.setdefault("active_mode", True)
    kw.setdefault("reviewer_independent", True)
    req = sp.PublishRequest(
        sp.Reasoning(reasoning.value), REPO, PR, head, **kw
    )
    client = b.GitHubClient(fake, {"GH_TOKEN": "tok"})
    return sp.publish_status(client, req, sleep=lambda _s: None)


class ReferenceModelParity(unittest.TestCase):
    def test_every_mapping_and_authorization_case_matches_reference(self):
        modes = list(raa.PublicationMode)
        independence = list(raa.ReviewerIndependence)
        cases = itertools.product(
            rse.Reasoning, modes, independence, (False, True), (False, True),
            (False, True), (False, True),
        )
        for reasoning, mode, indep, self_rev, same_auth, stale, worker in cases:
            with self.subTest(r=reasoning, m=mode, i=indep, s=self_rev, a=same_auth, st=stale, w=worker):
                expected = rse.resolve_status_publication(
                    rse.StatusPublicationInput(
                        reasoning=reasoning, repo=REPO, pr_number=PR,
                        reviewed_head_sha=SHA_A,
                        current_head_sha=SHA_B if stale else SHA_A,
                        is_parallel_worker=worker, self_review=self_rev,
                        same_controlling_authority_as_author=same_auth,
                        requested_mode=mode, reviewer_independence=indep,
                    )
                )
                fake = FakeGitHub(live_head=SHA_B if stale else SHA_A)
                out = run(
                    fake, reasoning,
                    is_aggregator=not worker,
                    self_review=self_rev or same_auth,
                    active_mode=mode is raa.PublicationMode.ACTIVE,
                    reviewer_independent=indep is raa.ReviewerIndependence.INDEPENDENT,
                )
                self.assertEqual(out.action == "withheld", not expected.published)
                self.assertEqual(len(fake.writes), 1 if expected.published else 0)
                if expected.published:
                    self.assertEqual(out.state, expected.published_state.value)
                if out.state == "success":
                    self.assertEqual(expected.published_state, rse.StatusState.SUCCESS)

    def test_context_matches_reference(self):
        self.assertEqual(sp.STATUS_CONTEXT, rse.STATUS_CONTEXT)

    def test_state_mapping_matches_reference(self):
        for r in rse.Reasoning:
            ref = rse.map_verdict_to_status(r)
            got = sp.map_state(sp.Reasoning(r.value))
            self.assertEqual(got, None if ref is rse.StatusState.NONE else ref.value)


class UpsertTests(unittest.TestCase):
    def test_posts_one_stable_context_on_reviewed_sha(self):
        fake = FakeGitHub()
        out = run(fake)
        self.assertEqual(out.action, "published")
        method, endpoint, body = fake.writes[0]
        self.assertEqual(endpoint, f"repos/{REPO}/statuses/{SHA_A}")
        self.assertEqual(json.loads(body)["context"], sp.STATUS_CONTEXT)

    def test_rerun_same_sha_and_state_is_noop(self):
        fake = FakeGitHub()
        run(fake)
        out = run(fake)
        self.assertEqual(out.action, "noop")
        self.assertEqual(len(fake.writes), 1)
        self.assertEqual(len(fake.statuses), 1)

    def test_state_change_on_same_sha_updates_in_place(self):
        fake = FakeGitHub()
        run(fake, rse.Reasoning.CHANGES_REQUIRED)
        out = run(fake, rse.Reasoning.CLEAN)
        self.assertEqual(out.state, "success")
        self.assertEqual([s["state"] for s in fake.statuses], ["success"])

    def test_new_sha_starts_without_status(self):
        fake = FakeGitHub(live_head=SHA_B)
        self.assertEqual(run(fake, head=SHA_A).action, "withheld")
        self.assertEqual(fake.statuses, [])

    def test_stale_head_message(self):
        out = run(FakeGitHub(live_head=SHA_B))
        self.assertEqual(out.message, "STATUS WITHHELD (HEAD advanced)")

    def test_self_review_clean_withheld_but_blocking_publishes(self):
        fake = FakeGitHub()
        out = run(fake, self_review=True)
        self.assertEqual(out.message, "STATUS WITHHELD (self-review: success not published)")
        self.assertEqual(run(fake, rse.Reasoning.CHANGES_REQUIRED, self_review=True).state, "failure")


class RetryTests(unittest.TestCase):
    def test_transient_failure_retries_without_duplicates(self):
        fake = FakeGitHub(write_errors=[b.RawResponse(502, "bad gateway"), b.RawResponse(0, "net")])
        out = run(fake)
        self.assertEqual(out.action, "published")
        self.assertEqual(len(fake.statuses), 1)

    def test_permanent_failure_not_retried(self):
        fake = FakeGitHub(write_errors=[b.RawResponse(422, "bad")])
        with self.assertRaises(b.GitHubCallError):
            run(fake)
        self.assertEqual(len(fake.writes), 1)

    def test_gives_up_after_attempt_limit(self):
        fake = FakeGitHub(write_errors=[b.RawResponse(503, "x")] * 5)
        with self.assertRaises(b.GitHubCallError):
            run(fake)
        self.assertEqual(len(fake.writes), sp.RETRY_ATTEMPTS)


class PermissionTests(unittest.TestCase):
    def test_missing_statuses_write_is_actionable(self):
        fake = FakeGitHub(write_errors=[b.RawResponse(403, "denied")])
        with self.assertRaisesRegex(sp.StatusPermissionError, "Commit statuses: write"):
            run(fake)


class InputValidationTests(unittest.TestCase):
    def test_rejects_short_sha_and_bad_repo_before_any_call(self):
        for repo, sha in ((REPO, "abc1234"), ("octo", SHA_A), ("a/b/../c", SHA_A)):
            fake = FakeGitHub()
            with self.assertRaises(ValueError):
                sp.publish_status(
                    b.GitHubClient(fake, {}),
                    sp.PublishRequest(sp.Reasoning.CLEAN, repo, PR, sha),
                )
            self.assertEqual(fake.calls, [])


class GovernanceBoundaryTests(unittest.TestCase):
    def test_publisher_has_no_governance_path(self):
        src = inspect.getsource(sp)
        for fragment in ("mutate_governance", "GovernanceAuthorization", "rulesets", "protection"):
            self.assertNotIn(fragment, src)
        for fragment in rse.PROHIBITED_ESCAPE_HATCH_FRAGMENTS:
            for name, fn in inspect.getmembers(sp, inspect.isfunction):
                if fn.__module__ == sp.__name__:
                    sig = " ".join(inspect.signature(fn).parameters)
                    self.assertNotIn(fragment, f"{name} {sig}")

    def test_all_writes_target_statuses_endpoint_only(self):
        fake = FakeGitHub()
        run(fake)
        run(fake, rse.Reasoning.INCOMPLETE)
        for _m, endpoint, _b in fake.writes:
            self.assertRegex(endpoint, r"^repos/[^/]+/[^/]+/statuses/[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
