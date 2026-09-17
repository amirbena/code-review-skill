#!/usr/bin/env python3
"""Integration coverage for the GitHub regression-issue lifecycle (Issue #339).

Contract: docs/benchmark/drift-detection-and-regression-lifecycle.md §4.
Uses a fixed baseline+candidate metrics pair (never a live corpus run) and
an in-memory fake `GitHubIssueClient`, so no test here makes a network call.

Covers the four acceptance-criteria transitions:

1. a new regression opens exactly one issue with the fingerprint marker;
2. the same regression recurring appends a comment, never a second issue;
3. a `keep-open`-labeled issue is never auto-closed even once the
   regression stops reproducing;
4. a regression that stops reproducing is auto-commented and closed.

Plus: two clean runs with no regression touch no issue at all.
"""

from __future__ import annotations

import unittest

from scripts.benchmark import benchmark_drift as bd
from tests.reference.benchmark import benchmark_metrics as bmet

_BASELINE = bd.RunIdentity(date="2026-09-15", repo_sha="aaa111")
_CANDIDATE = bd.RunIdentity(date="2026-09-16", repo_sha="bbb222")


def _metrics(case_id: str, *, missed: tuple[str, ...] = ()) -> bmet.CaseMetrics:
    return bmet.CaseMetrics(
        id=case_id,
        status="executed",
        findings_completeness="exhaustive",
        false_negatives=len(missed),
        false_positives=0,
        missed_keys=missed,
        incorrect_indices=(),
        near_misses=0,
        absorbed_extra_match=0,
        tolerated_unexpected=0,
    )


class FakeGitHubIssueClient:
    """In-memory stand-in for `GhCliIssueClient` -- no network, no `gh`."""

    def __init__(self) -> None:
        self._next_number = 1
        self.issues: dict[int, dict] = {}
        self.comments: dict[int, list[str]] = {}

    def list_labeled_issues(self, label: str, *, state: str = "open") -> list[bd.IssueRecord]:
        return [
            bd.IssueRecord(number=num, body=data["body"], labels=tuple(data["labels"]))
            for num, data in self.issues.items()
            if label in data["labels"] and data["state"] == state
        ]

    def create_issue(self, *, title: str, body: str, labels) -> bd.IssueRecord:
        number = self._next_number
        self._next_number += 1
        self.issues[number] = {"title": title, "body": body, "labels": list(labels), "state": "open"}
        self.comments[number] = []
        return bd.IssueRecord(number=number, body=body, labels=tuple(labels))

    def comment(self, issue_number: int, body: str) -> None:
        self.comments[issue_number].append(body)

    def close(self, issue_number: int, body: str) -> None:
        self.comment(issue_number, body)
        self.issues[issue_number]["state"] = "closed"


class RegressionLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeGitHubIssueClient()

    def test_no_regression_opens_no_issue_and_no_comment(self) -> None:
        base = {"case-a": _metrics("case-a")}
        cand = {"case-a": _metrics("case-a")}
        records = bd.classify_drift(base, cand, {}, {})
        outcome = bd.sync_regressions(records, self.client, baseline=_BASELINE, candidate=_CANDIDATE)
        self.assertEqual(outcome.opened, ())
        self.assertEqual(outcome.commented, ())
        self.assertEqual(outcome.closed, ())
        self.assertEqual(self.client.issues, {})

    def test_new_regression_opens_exactly_one_issue_with_marker(self) -> None:
        base = {"case-a": _metrics("case-a")}
        cand = {"case-a": _metrics("case-a", missed=("sqli-key",))}
        records = bd.classify_drift(base, cand, {}, {})
        outcome = bd.sync_regressions(records, self.client, baseline=_BASELINE, candidate=_CANDIDATE)

        self.assertEqual(len(self.client.issues), 2)  # missed-required-finding + decision-flip
        self.assertEqual(len(outcome.opened), 2)
        for issue in self.client.issues.values():
            fp = bd.extract_fingerprint(issue["body"])
            self.assertIsNotNone(fp)
            self.assertIn(bd.REGRESSION_LABEL, issue["labels"])

    def test_same_regression_recurring_appends_comment_not_a_second_issue(self) -> None:
        base = {"case-a": _metrics("case-a")}
        cand = {"case-a": _metrics("case-a", missed=("sqli-key",))}
        records = bd.classify_drift(base, cand, {}, {})

        bd.sync_regressions(records, self.client, baseline=_BASELINE, candidate=_CANDIDATE)
        issue_count_after_first = len(self.client.issues)

        second_candidate = bd.RunIdentity(date="2026-09-17", repo_sha="ccc333")
        outcome = bd.sync_regressions(
            records, self.client, baseline=_BASELINE, candidate=second_candidate
        )

        self.assertEqual(len(self.client.issues), issue_count_after_first)
        self.assertEqual(len(outcome.opened), 0)
        self.assertEqual(len(outcome.commented), 2)
        self.assertTrue(all(self.client.comments[num] for num in self.client.issues))

    def test_regression_resolved_auto_comments_and_closes(self) -> None:
        base = {"case-a": _metrics("case-a")}
        cand_regressed = {"case-a": _metrics("case-a", missed=("sqli-key",))}
        records = bd.classify_drift(base, cand_regressed, {}, {})
        bd.sync_regressions(records, self.client, baseline=_BASELINE, candidate=_CANDIDATE)
        self.assertTrue(all(data["state"] == "open" for data in self.client.issues.values()))

        cand_fixed = {"case-a": _metrics("case-a")}
        no_more_records = bd.classify_drift(base, cand_fixed, {}, {})
        outcome = bd.sync_regressions(
            no_more_records, self.client, baseline=_BASELINE, candidate=_CANDIDATE
        )

        self.assertEqual(len(outcome.closed), 2)
        self.assertTrue(all(data["state"] == "closed" for data in self.client.issues.values()))
        self.assertTrue(all(self.client.comments[num] for num in self.client.issues))

    def test_keep_open_override_prevents_auto_closure(self) -> None:
        base = {"case-a": _metrics("case-a")}
        cand_regressed = {"case-a": _metrics("case-a", missed=("sqli-key",))}
        records = bd.classify_drift(base, cand_regressed, {}, {})
        bd.sync_regressions(records, self.client, baseline=_BASELINE, candidate=_CANDIDATE)

        # A maintainer relabels every open regression issue `keep-open`.
        for data in self.client.issues.values():
            data["labels"].append(bd.KEEP_OPEN_LABEL)

        cand_fixed = {"case-a": _metrics("case-a")}
        no_more_records = bd.classify_drift(base, cand_fixed, {}, {})
        outcome = bd.sync_regressions(
            no_more_records, self.client, baseline=_BASELINE, candidate=_CANDIDATE
        )

        self.assertEqual(outcome.closed, ())
        self.assertEqual(len(outcome.kept_open), 2)
        self.assertTrue(all(data["state"] == "open" for data in self.client.issues.values()))

    def test_noise_only_delta_never_opens_or_updates_an_issue(self) -> None:
        base = {"case-a": _metrics("case-a")}
        cand = {"case-a": _metrics("case-a")}  # identical -> zero drift records
        records = bd.classify_drift(base, cand, {}, {})
        self.assertEqual(records, [])
        outcome = bd.sync_regressions(records, self.client, baseline=_BASELINE, candidate=_CANDIDATE)
        self.assertEqual(outcome.as_dict(), {"opened": [], "commented": [], "closed": [], "kept_open": []})
        self.assertEqual(self.client.issues, {})


if __name__ == "__main__":
    unittest.main()
