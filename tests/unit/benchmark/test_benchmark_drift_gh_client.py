#!/usr/bin/env python3
"""Coverage for `GhCliIssueClient.list_labeled_issues`'s pagination loop
(Issue #339). Contract: runtime_platform/benchmark/drift-detection-and-regression-lifecycle.md
§4.2.

`gh issue list --limit N` fetches up to N results *total*, not N per page,
so a single fixed-limit call silently truncates once more matching issues
exist than the limit. These tests mock `subprocess.run` (never invoking a
real `gh`) to prove the doubling-limit retry loop keeps re-fetching until a
response returns fewer items than requested, both when the first page
already covers everything and when it does not.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_drift as bd


def _issue(number: int) -> dict:
    return {"number": number, "body": f"<!-- benchmark-regression:{number:064x} -->", "labels": []}


def _completed(items: list[dict]) -> mock.Mock:
    return mock.Mock(returncode=0, stdout=json.dumps(items), stderr="")


class GhCliIssueClientPaginationTests(unittest.TestCase):
    def test_single_call_when_first_page_is_not_full(self) -> None:
        items = [_issue(1), _issue(2)]
        with mock.patch("subprocess.run", return_value=_completed(items)) as run:
            result = bd.GhCliIssueClient().list_labeled_issues("benchmark-regression")

        self.assertEqual([r.number for r in result], [1, 2])
        self.assertEqual(run.call_count, 1)
        first_args = run.call_args_list[0].args[0]
        self.assertIn("--limit", first_args)
        self.assertEqual(first_args[first_args.index("--limit") + 1], "200")

    def test_retries_with_doubled_limit_when_first_page_is_full(self) -> None:
        # First call requests 200 and gets exactly 200 back (looks
        # truncated); second call requests 400 and gets the true, smaller
        # full set back.
        full_page = [_issue(i) for i in range(200)]
        true_set = [_issue(i) for i in range(250)]
        responses = [_completed(full_page), _completed(true_set)]
        with mock.patch("subprocess.run", side_effect=responses) as run:
            result = bd.GhCliIssueClient().list_labeled_issues("benchmark-regression")

        self.assertEqual(len(result), 250)
        self.assertEqual(run.call_count, 2)
        limits_requested = [
            call.args[0][call.args[0].index("--limit") + 1] for call in run.call_args_list
        ]
        self.assertEqual(limits_requested, ["200", "400"])

    def test_no_open_issues_returns_empty_list_in_one_call(self) -> None:
        with mock.patch("subprocess.run", return_value=_completed([])) as run:
            result = bd.GhCliIssueClient().list_labeled_issues("benchmark-regression")

        self.assertEqual(result, [])
        self.assertEqual(run.call_count, 1)

    def test_pathological_always_full_response_raises_past_the_safety_ceiling(self) -> None:
        # A response that keeps returning exactly `limit` items would double
        # forever; the ceiling must fail loudly instead of looping forever.
        with mock.patch("subprocess.run") as run:
            run.side_effect = lambda args, **_: _completed(
                [_issue(i) for i in range(int(args[args.index("--limit") + 1]))]
            )
            with self.assertRaises(RuntimeError):
                bd.GhCliIssueClient().list_labeled_issues("benchmark-regression")

        limits_requested = [
            int(call.args[0][call.args[0].index("--limit") + 1]) for call in run.call_args_list
        ]
        self.assertEqual(limits_requested[-1], bd.MAX_ISSUE_LIST_LIMIT)


if __name__ == "__main__":
    unittest.main()
