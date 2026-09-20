#!/usr/bin/env python3
"""GitHub REST ports: request shapes, error classification, and create-only commits (Issue #471)."""

from __future__ import annotations

import io
import json
import unittest
import urllib.error
import urllib.parse
from typing import Any

from runtime_platform.benchmark.publisher import github_api
from runtime_platform.benchmark.publisher.ports import FatalPublicationError, PathExistsError, PublicationFailure, StagingRef

REPO = "amirbena/code-review-skill"


class _Response:
    def __init__(self, status: int, payload: bytes) -> None:
        self.status, self._payload = status, payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class ScriptedOpener:
    """Answers requests from a route table keyed by (method, path); records every request."""

    def __init__(self, routes: dict[tuple[str, str], Any]) -> None:
        self.routes, self.requests = routes, []

    def __call__(self, request: Any, timeout: float = 0) -> _Response:
        method, path = request.get_method(), request.full_url.split("?")[0].removeprefix(github_api.API)
        body = json.loads(request.data) if request.data else None
        self.requests.append((method, path, body, dict(request.header_items()), request.full_url))
        status, payload = self.routes.get((method, path), (404, {"message": "Not Found"}))
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "err", {}, io.BytesIO(raw))  # type: ignore[arg-type]
        return _Response(status, raw)

    def methods(self) -> list[str]:
        return [f"{m} {p}" for m, p, *_ in self.requests]


def client(routes: dict[tuple[str, str], Any]) -> tuple[github_api.GitHubClient, ScriptedOpener]:
    opener = ScriptedOpener(routes)
    return github_api.GitHubClient("ghs_test", opener=opener), opener


class ClientTests(unittest.TestCase):
    def test_requests_carry_only_the_supplied_bearer_token(self) -> None:
        c, opener = client({("GET", "/x"): (200, {"ok": True})})
        c.call("GET", "/x")
        self.assertEqual(opener.requests[0][3]["Authorization"], "Bearer ghs_test")

    def test_auth_refusals_are_fatal_and_server_errors_are_not(self) -> None:
        c, _ = client({("POST", "/a"): (403, {"message": "locked"}), ("GET", "/b"): (500, {}), ("GET", "/c"): (404, {})})
        with self.assertRaises(FatalPublicationError):
            c.call("POST", "/a", body={})
        with self.assertRaises(github_api.GitHubError) as caught:
            c.call("GET", "/b")
        self.assertNotIsInstance(caught.exception, FatalPublicationError)
        self.assertEqual(c.call("GET", "/c", tolerate=(404,)), (404, None))

    def test_network_failure_is_a_retryable_failure(self) -> None:
        def broken(request: Any, timeout: float = 0) -> Any:
            raise urllib.error.URLError("down")

        with self.assertRaises(PublicationFailure):
            github_api.GitHubClient("ghs_x", opener=broken).call("GET", "/x")

    def test_pagination_reads_every_page(self) -> None:
        pages = {"1": list(range(100)), "2": [100, 101]}
        seen: list[str] = []

        def opener(request: Any, timeout: float = 0) -> _Response:
            page = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)["page"][0]
            seen.append(page)
            return _Response(200, json.dumps(pages[page]).encode())

        rows = list(github_api.GitHubClient("ghs_x", opener=opener).paginate("/items"))
        self.assertEqual((len(rows), seen), (102, ["1", "2"]))

    def test_installation_token_guard(self) -> None:
        for bad in (None, "", "ghp_personal", "github_pat_x", "gho_oauth"):
            with self.assertRaises(FatalPublicationError):
                github_api.require_installation_token("T", bad)
        self.assertEqual(github_api.require_installation_token("T", "ghs_ok"), "ghs_ok")


class HandoffReaderTests(unittest.TestCase):
    def test_lists_staging_refs_and_reads_the_sealed_file_at_the_sha(self) -> None:
        c, opener = client({
            ("GET", f"/repos/{REPO}/git/matching-refs/heads/claude/benchmark-result-"): (200, [{"ref": "refs/heads/claude/benchmark-result-a", "object": {"sha": "s1"}}]),
            ("GET", f"/repos/{REPO}/contents/benchmark-result.json"): (200, b"{}"),
        })
        reader = github_api.GitHubHandoffReader(c, REPO)
        refs = reader.list_staging_refs("claude/benchmark-result-")
        self.assertEqual(refs, [StagingRef("claude/benchmark-result-a", "s1")])
        self.assertEqual(reader.read_handoff(refs[0]), b"{}")
        self.assertIn("ref=s1", opener.requests[-1][4])

    def test_unavailable_attribution_is_none_not_fatal(self) -> None:
        c, _ = client({("GET", f"/repos/{REPO}/activity"): (403, {"message": "denied"})})
        self.assertIsNone(github_api.GitHubHandoffReader(c, REPO).ref_activities("claude/benchmark-result-a"))

    def test_activities_are_parsed(self) -> None:
        item = {"activity_type": "branch_creation", "ref": "refs/heads/x", "actor": {"login": "amirbena"}, "after": "abc"}
        c, _ = client({("GET", f"/repos/{REPO}/activity"): (200, [item])})
        (activity,) = github_api.GitHubHandoffReader(c, REPO).ref_activities("x") or []
        self.assertEqual((activity.actor_login, activity.after), ("amirbena", "abc"))


class HistoryStoreTests(unittest.TestCase):
    def routes(self, *, head: bool) -> dict[tuple[str, str], Any]:
        base = f"/repos/{REPO}"
        routes: dict[tuple[str, str], Any] = {
            ("POST", f"{base}/git/blobs"): (201, {"sha": "blob1"}),
            ("POST", f"{base}/git/trees"): (201, {"sha": "tree2"}),
            ("POST", f"{base}/git/commits"): (201, {"sha": "commit3"}),
            ("POST", f"{base}/git/refs"): (201, {}),
            ("PATCH", f"{base}/git/refs/heads/benchmark-history"): (200, {}),
        }
        if head:
            routes[("GET", f"{base}/git/ref/heads/benchmark-history")] = (200, {"object": {"sha": "head0"}})
            routes[("GET", f"{base}/git/commits/head0")] = (200, {"tree": {"sha": "tree0"}})
        return routes

    def test_first_commit_creates_an_orphan_branch(self) -> None:
        c, opener = client(self.routes(head=False))
        sha = github_api.GitHubHistoryStore(c, REPO).commit_files({"records/a.json": b"{}"}, "Record a")
        self.assertEqual(sha, "commit3")
        commit = next(b for m, p, b, *_ in opener.requests if p.endswith("/git/commits"))
        tree = next(b for m, p, b, *_ in opener.requests if p.endswith("/git/trees"))
        ref = next(b for m, p, b, *_ in opener.requests if m == "POST" and p.endswith("/git/refs"))
        self.assertEqual((commit["parents"], "base_tree" in tree, ref["ref"]), ([], False, "refs/heads/benchmark-history"))

    def test_later_commits_extend_the_head_without_forcing(self) -> None:
        c, opener = client(self.routes(head=True))
        github_api.GitHubHistoryStore(c, REPO).commit_files({"receipts/a.json": b"{}"}, "Receipt a")
        commit = next(b for m, p, b, *_ in opener.requests if p.endswith("/git/commits"))
        patch = next(b for m, p, b, *_ in opener.requests if m == "PATCH")
        self.assertEqual((commit["parents"], patch["force"]), (["head0"], False))

    def test_create_only_refuses_an_existing_path_before_any_write(self) -> None:
        routes = self.routes(head=True)
        routes[("GET", f"/repos/{REPO}/contents/records/a.json")] = (200, b"{}")
        c, opener = client(routes)
        with self.assertRaises(PathExistsError):
            github_api.GitHubHistoryStore(c, REPO).commit_files({"records/a.json": b"{}"}, "Record a")
        self.assertFalse([r for r in opener.requests if r[0] in ("POST", "PATCH")])

    def test_missing_files_and_directories_read_as_absent(self) -> None:
        c, _ = client({})
        store = github_api.GitHubHistoryStore(c, REPO)
        self.assertEqual((store.read_file("a"), store.list_dir("d"), store.last_commit_for("a")), (None, [], None))

    def test_only_staging_refs_can_be_deleted(self) -> None:
        c, opener = client({("DELETE", f"/repos/{REPO}/git/refs/heads/claude/benchmark-result-a"): (204, b"")})
        store = github_api.GitHubHistoryStore(c, REPO)
        with self.assertRaises(PublicationFailure):
            store.delete_staging_ref("main")
        self.assertEqual(opener.requests, [])
        store.delete_staging_ref("claude/benchmark-result-a")
        self.assertEqual(len(opener.requests), 1)


class IssueTrackerTests(unittest.TestCase):
    def test_listing_skips_pull_requests_and_respects_the_limit(self) -> None:
        def item(n: int, pr: bool = False) -> dict[str, Any]:
            data = {"number": n, "user": {"login": "b[bot]"}, "body": "", "labels": [{"name": "l"}], "state": "open", "html_url": f"u{n}"}
            return {**data, "pull_request": {}} if pr else data

        c, _ = client({("GET", f"/repos/{REPO}/issues"): (200, [item(3), item(2, pr=True), item(1)])})
        tracker = github_api.GitHubIssueTracker(c, REPO)
        self.assertEqual([i.number for i in tracker.list_issues("l", state="open")], [3, 1])
        self.assertEqual([i.number for i in tracker.list_issues("l", state="open", limit=1)], [3])

    def test_missing_labels_are_reported(self) -> None:
        c, _ = client({("GET", f"/repos/{REPO}/labels/present"): (200, {"name": "present"})})
        self.assertEqual(github_api.GitHubIssueTracker(c, REPO).missing_labels(["present", "absent"]), ["absent"])

    def test_close_marks_the_issue_completed(self) -> None:
        c, opener = client({("PATCH", f"/repos/{REPO}/issues/5"): (200, {})})
        github_api.GitHubIssueTracker(c, REPO).close_issue(5)
        self.assertEqual(opener.requests[0][2], {"state": "closed", "state_reason": "completed"})


if __name__ == "__main__":
    unittest.main()
