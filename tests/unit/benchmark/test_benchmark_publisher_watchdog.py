#!/usr/bin/env python3
"""`publish_benchmark.py watchdog`: missed-run issues and the health-status comment (Issue #472).

Contract: runtime_platform/benchmark/publication-cli.md §7; rules:
runtime_platform/benchmark/scheduled-operations/drift-issue-lifecycle-and-recovery.md §5, §6 (cases 6, 7, 12).
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from runtime_platform.benchmark.publisher import cli, github_api, markers
from runtime_platform.benchmark.publisher.layout import receipt_path, record_path
from runtime_platform.benchmark.publisher.ports import FatalPublicationError, PublicationFailure
from tests.support.benchmark_publisher_fakes import IDENTITY, REPOSITORY, SLUG, World, make_record
from tests.support.paths import REPO_ROOT
from tests.unit.benchmark.test_benchmark_publisher_github_api import REPO, client

SENTINEL_FINISHED = datetime(2026, 9, 16, 1, 1, tzinfo=timezone.utc)
COMPREHENSIVE_FINISHED = datetime(2026, 9, 14, 1, 1, tzinfo=timezone.utc)
MAX_GAP = {"sentinel": 96, "comprehensive": 192}
SHA = {"sentinel": "5a" * 6, "comprehensive": "5b" * 6, "manual": "5c" * 6, "fresh": "5d" * 6}


def _after(finished: datetime, hours: float) -> datetime:
    return finished + timedelta(hours=hours)


class WatchdogCase(unittest.TestCase):
    """A world in which both lanes have one published, verified, scheduled record."""

    def setUp(self) -> None:
        self.world = World()
        self.sentinel = self.publish("sentinel", SENTINEL_FINISHED - timedelta(minutes=1), SHA["sentinel"])
        self.comprehensive = self.publish("comprehensive", COMPREHENSIVE_FINISHED - timedelta(minutes=1), SHA["comprehensive"])

    def publish(self, lane: str, start: datetime, sha: str, **kwargs: Any) -> dict[str, Any]:
        record = make_record(lane=lane, start=start, sha=sha, **kwargs)
        self.world.seal(record)
        self.world.now = start + timedelta(minutes=5)
        report = self.world.sweep()
        self.assertTrue(report.ok, report.as_dict())
        return record

    def watch(self, hours_after_sentinel: float, **overrides: Any) -> Any:
        self.world.now = _after(SENTINEL_FINISHED, hours_after_sentinel)
        report = self.world.watchdog(**overrides)
        self.assertTrue(report.ok, report.aborted)
        return report

    def lane(self, report: Any, lane: str = "sentinel") -> dict[str, Any]:
        return next(row for row in report.lanes if row["lane"] == lane)

    def issues_of(self, lane: str, state: str = "open") -> list[Any]:
        return [i for i in self.world.missed_run_issues(state) if markers.lane_of_missed_run_issue(i.body) == lane]


class GapRuleTests(WatchdogCase):
    def test_a_stale_but_not_yet_overdue_lane_takes_no_action(self) -> None:
        report = self.watch(72)
        self.assertEqual(self.lane(report)["action"], "on-schedule")
        self.assertEqual(self.world.missed_run_issues(), [])

    def test_exactly_at_the_gap_is_not_overdue(self) -> None:
        self.watch(MAX_GAP["sentinel"])
        self.assertEqual(self.world.missed_run_issues(), [])
        self.watch(MAX_GAP["sentinel"] + 0.01)
        self.assertEqual(len(self.world.missed_run_issues()), 1)

    def test_an_overdue_lane_opens_one_publisher_authored_issue_with_the_marker(self) -> None:
        report = self.watch(107)
        (issue,) = self.world.missed_run_issues()
        self.assertEqual((issue.author, issue.labels), (IDENTITY, ("benchmark-missed-run",)))
        self.assertEqual(issue.body.split("\n", 1)[0], "<!-- benchmark-missed-run:sentinel -->")
        self.assertIn(self.sentinel["run_id"], issue.body)
        self.assertIn("107 h ago; the limit is 96 h", issue.body)
        self.assertEqual((self.lane(report)["action"], self.lane(report)["missed_run_issue"]), ("opened", issue.number))
        self.assertEqual(self.lane(report, "comprehensive")["action"], "on-schedule")

    def test_each_lane_uses_its_own_gap(self) -> None:
        self.watch(200)
        lanes = {markers.lane_of_missed_run_issue(i.body) for i in self.world.missed_run_issues()}
        self.assertEqual(lanes, {"sentinel", "comprehensive"})

    def test_a_manual_run_never_satisfies_the_gap(self) -> None:
        start = _after(SENTINEL_FINISHED, 90)
        self.publish("sentinel", start, SHA["manual"], trigger="manual")
        report = self.watch(107)
        self.assertEqual(self.lane(report)["latest_run_id"], self.sentinel["run_id"])
        self.assertEqual(len(self.world.missed_run_issues()), 1)

    def test_an_unverified_record_in_history_never_satisfies_the_gap(self) -> None:
        forged = make_record(start=_after(SENTINEL_FINISHED, 90), sha=SHA["fresh"], verified=False)
        self.world.store.files[record_path(forged["run_id"])] = json.dumps(forged).encode()
        self.world.store.files[receipt_path(forged["run_id"])] = b"{}"
        report = self.watch(107)
        self.assertEqual(self.lane(report)["latest_run_id"], self.sentinel["run_id"])


EXPECTED = datetime(2026, 9, 18, 1, 0, tzinfo=timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class BootstrapTests(unittest.TestCase):
    """A lane with no published scheduled record is judged from the manifest's `expected_from`, never a guess."""

    def setUp(self) -> None:
        self.world = World()

    def activate(self, sentinel: datetime | None = EXPECTED, comprehensive: datetime | None = None) -> None:
        manifest = json.loads(json.dumps(self.world.manifest))
        for lane, moment in (("sentinel", sentinel), ("comprehensive", comprehensive)):
            manifest["lanes"][lane]["expected_from"] = _stamp(moment) if moment else None
        self.world.manifest = manifest

    def watch(self, hours: float) -> dict[str, dict[str, Any]]:
        self.world.now = EXPECTED + timedelta(hours=hours)
        report = self.world.watchdog()
        self.assertTrue(report.ok, report.aborted)
        return {row["lane"]: row for row in report.lanes}

    def state_row(self, lane: str = "sentinel") -> str:
        return next(line for line in self.world.health_comments()[0].body.splitlines() if line.startswith(f"| `{lane}` |"))

    def publish(self, start: datetime, sha: str, **kwargs: Any) -> dict[str, Any]:
        record = make_record(start=start, sha=sha, **kwargs)
        self.world.seal(record)
        self.world.now = start + timedelta(minutes=5)
        self.assertTrue(self.world.sweep().ok)
        return record

    def test_an_unset_expected_from_means_not_activated_and_nothing_is_judged(self) -> None:
        self.activate(sentinel=None)
        lanes = self.watch(10_000)
        self.assertEqual({row["action"] for row in lanes.values()}, {"not-activated"})
        self.assertEqual(self.world.missed_run_issues(), [])
        self.assertIn("not activated (`expected_from` unset)", self.state_row())

    def test_before_the_gap_elapses_the_lane_is_awaiting_its_first_run(self) -> None:
        self.activate()
        row = self.watch(96)["sentinel"]
        self.assertEqual((row["action"], row["overdue"]), ("awaiting-first-run", False))
        self.assertEqual(self.world.missed_run_issues(), [])
        self.assertIn(f"awaiting first scheduled run (expected from {_stamp(EXPECTED)})", self.state_row())

    def test_a_lane_broken_since_its_first_expected_run_opens_a_missed_run_issue(self) -> None:
        self.activate()
        row = self.watch(96.01)["sentinel"]
        (issue,) = self.world.missed_run_issues()
        self.assertEqual((row["action"], row["missed_run_issue"]), ("opened", issue.number))
        self.assertIn(f"published no verified scheduled record since its expected start {_stamp(EXPECTED)}", issue.body)
        self.assertIn("96 h ago; the limit is 96 h", issue.body)
        self.assertIn("OVERDUE", self.state_row())
        self.assertEqual(self.watch(96.02)["comprehensive"]["action"], "not-activated")

    def test_a_persisting_first_run_failure_is_commented_at_the_manifest_interval(self) -> None:
        self.activate()
        self.watch(100)
        self.watch(101)
        (issue,) = self.world.missed_run_issues()
        self.assertEqual(self.world.tracker.comments.get(issue.number, []), [])
        self.assertEqual(self.watch(124.1)["sentinel"]["action"], "commented")
        self.assertIn("Still overdue (`sentinel`): it has published no verified scheduled record", self.world.tracker.comments[issue.number][0].body)

    def test_the_first_published_scheduled_record_recovers_the_lane_and_closes_the_issue(self) -> None:
        self.activate()
        self.watch(100)
        (issue,) = self.world.missed_run_issues()
        first = self.publish(EXPECTED + timedelta(hours=110), "6a" * 6)
        self.world.now = EXPECTED + timedelta(hours=111)
        row = {r["lane"]: r for r in self.world.watchdog().lanes}["sentinel"]
        self.assertEqual((row["action"], row["missed_run_issue"]), ("closed", None))
        self.assertEqual(self.world.tracker.get_issue(issue.number).state, "closed")
        self.assertIn(markers.missed_run_resolved("sentinel", first["run_id"]), self.world.tracker.comments[issue.number][-1].body)
        self.assertIn("on schedule", self.state_row())

    def test_a_manual_run_never_ends_a_first_run_failure(self) -> None:
        self.activate()
        self.publish(EXPECTED + timedelta(hours=50), "6b" * 6, trigger="manual")
        row = self.watch(100)["sentinel"]
        self.assertEqual(row["action"], "opened")
        self.assertIsNone(row["latest_run_id"])

    def test_a_record_from_before_activation_neither_alarms_nor_recovers(self) -> None:
        self.publish(EXPECTED - timedelta(hours=200), "6c" * 6)
        self.activate()
        row = self.watch(50)["sentinel"]
        self.assertEqual((row["action"], row["overdue"]), ("awaiting-first-run", False))
        self.assertEqual(self.watch(97)["sentinel"]["action"], "opened")
        self.publish(EXPECTED + timedelta(hours=98), "6d" * 6)
        self.assertEqual(self.watch(99)["sentinel"]["action"], "closed")

    def test_moving_expected_from_later_leaves_an_open_issue_untouched(self) -> None:
        self.activate()
        self.watch(100)
        (issue,) = self.world.missed_run_issues()
        self.activate(sentinel=EXPECTED + timedelta(hours=90))
        row = self.watch(101)["sentinel"]
        self.assertEqual((row["action"], row["missed_run_issue"]), ("awaiting-first-run", issue.number))
        self.assertEqual(self.world.tracker.get_issue(issue.number).state, "open")

    def test_each_lane_is_activated_independently(self) -> None:
        self.activate(sentinel=EXPECTED, comprehensive=EXPECTED)
        lanes = self.watch(193)
        self.assertEqual({lane: row["action"] for lane, row in lanes.items()}, {"sentinel": "opened", "comprehensive": "opened"})
        self.activate(sentinel=EXPECTED)
        self.assertEqual(self.watch(194)["comprehensive"]["action"], "not-activated")

    def test_an_unparsable_expected_from_is_never_read_as_not_activated(self) -> None:
        from unittest import mock

        from runtime_platform.benchmark.publisher import watchdog

        self.activate()
        self.world.manifest["lanes"]["sentinel"]["expected_from"] = "2026-9-25T1:00:00Z"
        with mock.patch.object(watchdog, "preflight"):  # what a validator gap would let through
            report = self.world.watchdog()
        self.assertFalse(report.ok)
        self.assertIn("refusing to treat the lane as not activated", report.aborted)
        self.assertEqual((self.world.missed_run_issues(), self.world.health_comments()), ([], []))

    def test_an_invalid_expected_from_aborts_before_any_write(self) -> None:
        self.activate()
        self.world.manifest["lanes"]["sentinel"]["expected_from"] = "2026-09-18 01:00"
        report = self.world.watchdog()
        self.assertIn("expected_from", report.aborted)
        self.assertEqual((self.world.tracker.issues, self.world.tracker.comments), ({}, {}))


class LifecycleTests(WatchdogCase):
    def test_a_persisting_overdue_lane_is_commented_at_most_once_per_interval(self) -> None:
        self.watch(107)
        (issue,) = self.world.missed_run_issues()
        comments = lambda: self.world.tracker.comments.get(issue.number, [])  # noqa: E731
        self.watch(108)
        self.assertEqual(len(comments()), 0)
        self.assertEqual(self.lane(self.watch(130))["action"], "overdue")
        self.assertEqual(self.lane(self.watch(131))["action"], "commented")
        self.assertEqual(len(comments()), 1)
        self.assertIn("Still overdue", comments()[0].body)
        self.watch(132)
        self.assertEqual(len(comments()), 1)
        self.watch(155.1)
        self.assertEqual(len(comments()), 2)
        self.assertEqual(len(self.issues_of("sentinel")), 1)

    def test_the_comment_interval_comes_from_the_manifest(self) -> None:
        manifest = json.loads(json.dumps(self.world.manifest))
        manifest["watchdog"]["missed_run_comment_interval_hours"] = 2
        self.world.manifest = manifest
        self.watch(107)
        self.watch(108)
        self.watch(109.5)
        (issue,) = self.world.missed_run_issues()
        self.assertEqual(len(self.world.tracker.comments[issue.number]), 1)

    def test_a_recovered_lane_closes_its_issue_once_a_new_verified_record_is_published(self) -> None:
        self.watch(107)
        (issue,) = self.world.missed_run_issues()
        fresh = self.publish("sentinel", _after(SENTINEL_FINISHED, 108), SHA["fresh"])
        report = self.watch(109)
        self.assertEqual((self.lane(report)["action"], self.lane(report)["missed_run_issue"]), ("closed", None))
        self.assertEqual(self.world.missed_run_issues(), [])
        self.assertEqual(self.world.tracker.get_issue(issue.number).state, "closed")
        resolution = self.world.tracker.comments[issue.number][-1]
        self.assertEqual(resolution.author, IDENTITY)
        self.assertIn(markers.missed_run_resolved("sentinel", fresh["run_id"]), resolution.body)

    def test_a_failed_close_is_retried_without_a_second_resolution_comment(self) -> None:
        self.watch(107)
        (issue,) = self.world.missed_run_issues()
        self.publish("sentinel", _after(SENTINEL_FINISHED, 108), SHA["fresh"])

        def fail(method: str, *args: Any) -> None:
            if method == "close_issue":
                raise FatalPublicationError("HTTP 403")

        self.world.tracker.hook = fail
        self.world.now = _after(SENTINEL_FINISHED, 109)
        self.assertFalse(self.world.watchdog().ok)
        self.world.tracker.hook = None
        self.watch(110)
        self.assertEqual(self.world.tracker.get_issue(issue.number).state, "closed")
        self.assertEqual(len(self.world.tracker.comments[issue.number]), 1)

    def test_a_new_overdue_period_after_closure_opens_a_new_issue(self) -> None:
        self.watch(107)
        self.publish("sentinel", _after(SENTINEL_FINISHED, 108), SHA["fresh"])
        self.watch(109)
        report = self.watch(108 + 97)
        self.assertEqual(self.lane(report)["action"], "opened")
        self.assertEqual(len(self.issues_of("sentinel", "closed")), 1)
        self.assertEqual(len(self.issues_of("sentinel")), 1)

    def test_at_most_one_open_issue_per_lane(self) -> None:
        self.watch(107)
        (first,) = self.world.missed_run_issues()
        duplicate = self.world.tracker.seed_issue(
            first.number + 10, author=IDENTITY, body=first.body, labels=first.labels
        )
        report = self.watch(108)
        self.assertEqual([i.number for i in self.world.missed_run_issues()], [first.number])
        self.assertEqual(self.lane(report)["missed_run_issue"], first.number)
        self.assertIn(f"Duplicate of #{first.number}", self.world.tracker.comments[duplicate.number][0].body)

    def test_a_failed_duplicate_close_is_retried_without_a_second_pointer_comment(self) -> None:
        self.watch(107)
        (first,) = self.world.missed_run_issues()
        duplicate = self.world.tracker.seed_issue(first.number + 10, author=IDENTITY, body=first.body, labels=first.labels)

        def fail(method: str, *args: Any) -> None:
            if method == "close_issue":
                raise PublicationFailure("HTTP 502")

        self.world.tracker.hook = fail
        self.world.now = _after(SENTINEL_FINISHED, 108)
        self.assertFalse(self.world.watchdog().ok)
        self.world.tracker.hook = None
        self.watch(109)
        self.assertEqual(self.world.tracker.get_issue(duplicate.number).state, "closed")
        pointers = [c for c in self.world.tracker.comments[duplicate.number] if f"Duplicate of #{first.number}" in c.body]
        self.assertEqual(len(pointers), 1)
        self.assertIn(markers.missed_run_duplicate(first.number), pointers[0].body)

    def test_an_issue_carrying_the_marker_from_another_author_is_ignored(self) -> None:
        self.world.tracker.seed_issue(
            900, author="someone-else", labels=("benchmark-missed-run",),
            body=markers.missed_run_marker("sentinel") + "\n" + markers.missed_run_notice("sentinel", "2026-09-20T11:00:00Z"),
        )
        report = self.watch(107)
        self.assertEqual(self.lane(report)["action"], "opened")
        self.assertEqual([i.author for i in self.world.missed_run_issues() if i.number != 900], [IDENTITY])
        self.assertEqual(self.world.tracker.comments.get(900), None)

    def test_a_foreign_notice_stamp_does_not_suppress_the_comment(self) -> None:
        self.watch(107)
        (issue,) = self.world.missed_run_issues()
        self.world.tracker.seed_comment(
            issue.number, author="someone-else", body=markers.missed_run_notice("sentinel", "2026-09-20T13:00:00Z")
        )
        self.assertEqual(self.lane(self.watch(131))["action"], "commented")

    def test_a_missed_run_post_refused_under_another_identity_stops_the_pass(self) -> None:
        self.world.tracker.identity = "the-maintainer"
        self.world.now = _after(SENTINEL_FINISHED, 107)
        report = self.world.watchdog()
        self.assertFalse(report.ok)
        self.assertIn("not the publisher identity", report.aborted)


class HealthStatusTests(WatchdogCase):
    def status(self) -> str:
        (comment,) = self.world.health_comments()
        return comment.body

    def test_first_pass_creates_one_publisher_authored_comment_with_every_checklist_field(self) -> None:
        report = self.watch(72)
        (comment,) = self.world.health_comments()
        self.assertEqual((comment.author, report.health["action"]), (IDENTITY, "created"))
        body = comment.body
        self.assertEqual(body.split("\n", 1)[0], markers.HEALTH_MARKER)
        for lane, record in (("sentinel", self.sentinel), ("comprehensive", self.comprehensive)):
            row = next(line for line in body.splitlines() if line.startswith(f"| `{lane}` |"))
            for expected in (record["run_id"], record["finished_at"], "claude-sonnet-5", "not evaluated", f"{MAX_GAP[lane]} h", "on schedule"):
                self.assertIn(expected, row)
        for line in (
            "- Open drift issues: 0",
            "- Open missed-run issues: 0",
            "- Sealed but unpublished handoffs: none",
            "- Last successful publication sweep: not reported",
        ):
            self.assertIn(line, body)

    def test_an_unchanged_state_is_never_edited(self) -> None:
        self.watch(72)
        edits: list[Any] = []
        self.world.tracker.hook = lambda method, *args: edits.append(method) if method in ("create_comment", "update_comment") else None
        report = self.watch(73)
        self.assertEqual((report.health["action"], edits), ("unchanged", []))

    def test_a_changed_fact_edits_the_same_comment_in_place(self) -> None:
        self.watch(72)
        (before,) = self.world.health_comments()
        report = self.watch(107)
        (after,) = self.world.health_comments()
        self.assertEqual((report.health["action"], after.id), ("edited", before.id))
        self.assertIn("OVERDUE", after.body)
        self.assertIn("- Open missed-run issues: 1", after.body)
        (issue,) = self.world.missed_run_issues()
        self.assertIn(f"#{issue.number}", after.body)

    def test_open_drift_issues_are_counted_from_publisher_authored_issues_only(self) -> None:
        marker = markers.regression_marker("ab" * 32)
        self.world.tracker.seed_issue(700, author=IDENTITY, body=marker, labels=("benchmark-regression",))
        self.world.tracker.seed_issue(701, author="someone-else", body=marker, labels=("benchmark-regression",))
        self.world.tracker.seed_issue(702, author=IDENTITY, body=marker, labels=("benchmark-regression",), state="closed")
        self.watch(72)
        self.assertIn("- Open drift issues: 1", self.status())

    def test_a_foreign_comment_imitating_the_status_comment_is_ignored_and_never_edited(self) -> None:
        issue = self.world.manifest["health_issue"]
        foreign = self.world.tracker.seed_comment(issue, author="someone-else", body=markers.HEALTH_MARKER + "\n\nall fine")
        self.watch(72)
        self.watch(107)
        comments = self.world.health_comments()
        self.assertEqual([c.author for c in comments], ["someone-else", IDENTITY])
        self.assertEqual(comments[0].body, foreign.body)
        self.assertIn("OVERDUE", comments[1].body)

    def test_a_status_comment_refused_under_another_identity_stops_the_pass(self) -> None:
        self.world.tracker.identity = "the-maintainer"
        self.world.now = _after(SENTINEL_FINISHED, 72)
        report = self.world.watchdog()
        self.assertIn("not the publisher identity", report.aborted or "")

    def test_a_sealed_but_unpublished_handoff_is_counted_with_its_age(self) -> None:
        pending = make_record(start=_after(SENTINEL_FINISHED, 60), sha=SHA["fresh"])
        self.world.seal(pending)
        report = self.watch(72)
        self.assertEqual(report.health["pending_handoffs"], 1)
        sealed = pending["sealed_at"]
        self.assertIn(f"- Sealed but unpublished handoffs: 1 — oldest sealed {sealed} (11 h ago)", self.status())

    def test_an_unreadable_handoff_counts_as_pending_with_no_age(self) -> None:
        self.world.seal(make_record(start=_after(SENTINEL_FINISHED, 60), sha=SHA["fresh"]), data=b"{not json")
        self.watch(72)
        self.assertIn("- Sealed but unpublished handoffs: 1 — 1 with no readable seal time", self.status())

    def test_published_runs_awaiting_staging_retention_are_not_pending(self) -> None:
        report = self.watch(72)
        self.assertEqual(report.health["pending_handoffs"], 0)

    def test_the_last_successful_sweep_advances_only_on_an_ok_report(self) -> None:
        self.watch(72, sweep_succeeded=True)
        self.assertIn("- Last successful publication sweep: 2026-09-19T01:01:00Z", self.status())
        self.watch(80)
        self.assertIn("- Last successful publication sweep: 2026-09-19T01:01:00Z", self.status())
        self.watch(90, sweep_succeeded=True)
        self.assertIn("- Last successful publication sweep: 2026-09-19T19:01:00Z", self.status())


class FailClosedTests(WatchdogCase):
    def test_a_missing_label_aborts_before_any_write(self) -> None:
        world = World(labels=["benchmark-regression", "keep-open", "benchmark-tracking"])
        report = world.watchdog()
        self.assertFalse(report.ok)
        self.assertIn("benchmark-missed-run", report.aborted)
        self.assertEqual((world.tracker.issues, world.tracker.comments), ({}, {}))

    def test_an_unprovisioned_manifest_aborts_before_any_write(self) -> None:
        manifest = json.loads(json.dumps(self.world.manifest))
        manifest["health_issue"] = None
        before = {n: list(c) for n, c in self.world.tracker.comments.items()}
        report = self.world.watchdog(manifest=manifest)
        self.assertIn("not provisioned", report.aborted)
        self.assertEqual(self.world.tracker.comments, before)

    def test_the_watchdog_never_writes_history_or_deletes_a_ref(self) -> None:
        def forbid(method: str, *args: Any) -> None:
            raise AssertionError(f"watchdog called {method}")

        self.world.store.hook = forbid
        self.watch(107)
        self.watch(200)

    def test_a_history_read_failure_aborts_rather_than_opening_an_issue(self) -> None:
        def broken(path: str) -> list[str]:
            raise FatalPublicationError("HTTP 403")

        self.world.store.list_dir = broken  # type: ignore[method-assign]
        self.world.now = _after(SENTINEL_FINISHED, 200)
        report = self.world.watchdog()
        self.assertFalse(report.ok)
        self.assertEqual((self.world.missed_run_issues(), self.world.health_comments()), ([], []))


class NoTimezoneLogicTests(unittest.TestCase):
    """#431: no repository code owns a zone, a DST rule, or a wall-clock slot."""

    MODULES = ("watchdog.py", "health.py")
    BANNED_IMPORTS = ("zoneinfo", "pytz", "dateutil", "tzdata", "calendar", "time")
    BANNED_NAMES = ("timezone", "intended_start", "local_time", "target_completion_local", "weekday", "tzinfo", "ZoneInfo")

    def test_the_gap_rule_uses_elapsed_time_only(self) -> None:
        for name in self.MODULES:
            tree = ast.parse((REPO_ROOT / "runtime_platform/benchmark/publisher" / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    for module in modules:
                        self.assertNotIn(module.split(".")[0], self.BANNED_IMPORTS, f"{name} imports {module}")
                        if isinstance(node, ast.ImportFrom):
                            self.assertFalse({a.name for a in node.names} & set(self.BANNED_NAMES), f"{name} imports a zone name")
                names = [getattr(node, "id", None), getattr(node, "attr", None)]
                for banned in self.BANNED_NAMES:
                    self.assertNotIn(banned, names, f"{name} uses {banned}")


class RestPortTests(unittest.TestCase):
    def test_update_comment_patches_the_comment_by_id(self) -> None:
        item = {"id": 9, "user": {"login": "b[bot]"}, "body": "new", "html_url": "u"}
        c, opener = client({("PATCH", f"/repos/{REPO}/issues/comments/9"): (200, item)})
        comment = github_api.GitHubIssueTracker(c, REPO).update_comment(9, "new")
        self.assertEqual((comment.author, comment.body), ("b[bot]", "new"))
        self.assertEqual((opener.requests[0][0], opener.requests[0][2]), ("PATCH", {"body": "new"}))

    def test_a_refused_edit_stops_the_pass(self) -> None:
        c, _ = client({("PATCH", f"/repos/{REPO}/issues/comments/9"): (403, {"message": "locked"})})
        with self.assertRaises(FatalPublicationError):
            github_api.GitHubIssueTracker(c, REPO).update_comment(9, "new")


def run_cli(argv: list[str], env: dict[str, str], world: World | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    factory = (lambda manifest, identity: world.ports()) if world else None
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv, env=env, ports_factory=factory, clock=(lambda: world.now) if world else None)
    return code, out.getvalue(), err.getvalue()


class CliTests(WatchdogCase):
    ENV = {"BENCHMARK_APP_SLUG": SLUG}

    def test_a_pass_outside_actions_requires_once(self) -> None:
        code, _, err = run_cli(["watchdog"], self.ENV, self.world)
        self.assertEqual((code, "--once" in err), (cli.EXIT_USAGE, True))

    def test_the_acting_identity_must_be_known(self) -> None:
        code, _, err = run_cli(["watchdog", "--once"], {}, self.world)
        self.assertEqual((code, "App slug" in err), (cli.EXIT_USAGE, True))

    def test_once_runs_and_reports_json(self) -> None:
        self.world.now = _after(SENTINEL_FINISHED, 107)
        code, out, err = run_cli(["watchdog", "--once"], self.ENV, self.world)
        self.assertEqual(code, 0, err)
        self.assertIn(f"acting identity: {IDENTITY}", err)
        report = json.loads(out)
        self.assertEqual(report["ok"], True)
        self.assertEqual(next(r for r in report["lanes"] if r["lane"] == "sentinel")["overdue"], True)

    def test_dry_run_reads_and_plans_but_writes_nothing_to_the_real_ports(self) -> None:
        code, out, err = run_cli(["watchdog", "--once", "--dry-run"], self.ENV, self.world)
        self.assertEqual(code, 0, err)
        self.assertIn("dry run", err)
        self.assertEqual((self.world.health_comments(), self.world.missed_run_issues()), ([], []))
        self.assertEqual(json.loads(out)["health"]["action"], "created")

    def test_an_ok_sweep_report_marks_the_sweep_successful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sweep.json"
            path.write_text(json.dumps({"ok": True, "aborted": None, "runs": []}))
            code, out, err = run_cli(["watchdog", "--once", "--sweep-report", str(path)], self.ENV, self.world)
        self.assertEqual(code, 0, err)
        self.assertRegex(json.loads(out)["health"]["last_successful_sweep"], r"^\d{4}-\d\d-\d\dT")

    def test_a_failed_or_unreadable_sweep_report_never_marks_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sweep.json"
            path.write_text(json.dumps({"ok": False, "aborted": "x"}))
            code, out, _ = run_cli(["watchdog", "--once", "--sweep-report", str(path)], self.ENV, self.world)
            self.assertEqual((code, json.loads(out)["health"]["last_successful_sweep"]), (0, None))
            code, _, err = run_cli(["watchdog", "--once", "--sweep-report", str(Path(tmp) / "missing.json")], self.ENV, self.world)
        self.assertEqual((code, "cannot read" in err), (cli.EXIT_USAGE, True))

    def test_the_history_client_carries_the_read_token_alone(self) -> None:
        env = {"BENCHMARK_READ_TOKEN": "ghs_read", "BENCHMARK_ISSUES_TOKEN": "ghs_issues"}
        ports = cli._real_ports(env, REPOSITORY, read_only_history=True)
        self.assertEqual(ports.store._client._token, "ghs_read")
        with self.assertRaises(FatalPublicationError):
            cli._real_ports(env, REPOSITORY)
        both = {**env, "BENCHMARK_CONTENTS_TOKEN": "ghs_contents"}
        self.assertEqual(cli._real_ports(both, REPOSITORY).store._client._token, "ghs_contents")
        self.assertEqual(cli._real_ports(both, REPOSITORY, read_only_history=True).store._client._token, "ghs_read")


class SampleCommentTests(unittest.TestCase):
    """The rendered sample in the contract document is what the renderer produces."""

    def test_the_documented_sample_matches_the_renderer(self) -> None:
        world = World()
        for lane, start, sha in (("sentinel", SENTINEL_FINISHED, SHA["sentinel"]), ("comprehensive", COMPREHENSIVE_FINISHED, SHA["comprehensive"])):
            world.seal(make_record(lane=lane, start=start - timedelta(minutes=1), sha=sha))
            world.now = start + timedelta(minutes=5)
            self.assertTrue(world.sweep().ok)
        world.now = _after(SENTINEL_FINISHED, 72)
        world.watchdog(sweep_succeeded=True)
        doc = (REPO_ROOT / "runtime_platform/benchmark/publication-cli.md").read_text(encoding="utf-8")
        sample = re.search(r"<!-- sample-health-status -->\n````markdown\n(.*?)\n````", doc, re.DOTALL)
        self.assertIsNotNone(sample, "publication-cli.md has no sample health-status comment")
        self.assertEqual(sample.group(1), world.health_comments()[0].body)


if __name__ == "__main__":
    unittest.main()
