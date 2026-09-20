#!/usr/bin/env python3
"""`publish_benchmark.py sweep` against in-memory GitHub fakes (Issue #471).

Contract: runtime_platform/benchmark/publication-cli.md; failure table:
runtime_platform/benchmark/scheduled-operations/drift-issue-lifecycle-and-recovery.md §6.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any

from unittest import mock

from runtime_platform.benchmark.publisher import lifecycle, markers
from runtime_platform.benchmark.publisher import sweep as sweep_module
from runtime_platform.benchmark.publisher.validation import Refusal
from runtime_platform.benchmark.publisher.layout import encode_json, receipt_path, record_path, staging_ref_name
from runtime_platform.benchmark.publisher.ports import FatalPublicationError, PublicationFailure, RefActivity
from runtime_platform.benchmark.scripts import benchmark_result as res
from tests.support.benchmark_publisher_fakes import CASES, IDENTITY, World, drift_item, make_record

C0, C1, C2, S0, S1, S2, S3 = ("c0" * 6, "c1" * 6, "c2" * 6, "50" * 6, "51" * 6, "52" * 6, "53" * 6)


def _at(day: int, hour: int = 1) -> datetime:
    return datetime(2026, 9, day, hour, 0, tzinfo=timezone.utc)


def _sentinel_pair(**drift: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    base = make_record(start=_at(16), sha=S0)
    return base, make_record(start=_at(19), sha=S1, baseline=base, **drift)


def _outcome(report: Any, run_id: str) -> Any:
    return next(o for o in report.outcomes if o.run_id == run_id)


class GateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.record = make_record(start=_at(16), sha=S0)

    def assertRefused(self, gate: str) -> None:
        report = self.world.sweep()
        self.assertFalse(report.ok)
        self.assertEqual([o.gate for o in report.outcomes], [gate])
        self.assertEqual(self.world.store.files, {})
        self.assertEqual(self.world.tracker.comments, {})

    def test_unknown_schema_version(self) -> None:
        self.world.seal(self.record, data=encode_json({**self.record, "schema": "benchmark-result/v9"}))
        self.assertRefused("schema")

    def test_schema_violation(self) -> None:
        broken = {k: v for k, v in self.record.items() if k != "lane"}
        self.world.seal(self.record, data=encode_json(broken))
        self.assertRefused("schema")

    def test_unreadable_handoff(self) -> None:
        self.world.seal(self.record, data=b"{not json")
        self.assertRefused("schema")

    def test_tampered_body_fails_the_content_hash(self) -> None:
        tampered = copy.deepcopy(self.record)
        tampered["execution"]["duration_s"] = 999.0
        self.world.seal(self.record, data=encode_json(tampered))
        self.assertRefused("content-hash")

    def test_unverified_run_is_never_published(self) -> None:
        self.world.seal(make_record(start=_at(16), sha=S0, verified=False))
        self.assertRefused("verification")

    def test_staging_ref_must_encode_the_run_id(self) -> None:
        self.world.handoff.add("claude/benchmark-result-sentinel-20200101T000000Z-" + "0" * 12, encode_json(self.record), sha="a" * 40, activities=None)
        self.assertRefused("provenance")

    def test_pusher_outside_the_allowlist_is_refused(self) -> None:
        self.world.seal(self.record, actor="someone-else")
        self.assertRefused("origin")

    def test_creation_at_a_different_sha_is_refused(self) -> None:
        name = staging_ref_name(self.record["run_id"])
        self.world.seal(self.record, activities=[RefActivity("branch_creation", f"refs/heads/{name}", "amirbena", "f" * 40)])
        self.assertRefused("origin")

    def test_unavailable_attribution_fails_closed(self) -> None:
        self.world.seal(self.record, activities=None)
        self.assertRefused("origin")

    def test_dispatch_can_accept_only_unavailable_attribution(self) -> None:
        self.world.seal(self.record, activities=None)
        report = self.world.sweep(only_run_id=self.record["run_id"], accept_unattributed=True)
        self.assertTrue(report.ok)
        self.assertIn("origin-accepted-by-dispatch", self.world.stored(receipt_path(self.record["run_id"]))["steps_done"])

    def test_dispatch_never_accepts_contradicting_attribution(self) -> None:
        self.world.seal(self.record, actor="someone-else")
        report = self.world.sweep(only_run_id=self.record["run_id"], accept_unattributed=True)
        self.assertEqual([o.gate for o in report.outcomes], ["origin"])

    def test_a_refusal_does_not_block_the_next_result(self) -> None:
        self.world.seal(self.record, actor="someone-else")
        good = make_record(start=_at(17), sha=S1)
        self.world.seal(good)
        report = self.world.sweep()
        self.assertEqual({o.run_id: o.status for o in report.outcomes}, {self.record["run_id"]: "refused", good["run_id"]: "published"})

    def test_compared_record_needs_its_baseline_in_history(self) -> None:
        _, compared = _sentinel_pair()
        self.world.seal(compared)
        self.assertRefused("baseline")


    def test_a_baseline_from_the_other_lane_is_refused(self) -> None:
        other = make_record(lane="comprehensive", start=_at(11), sha=C0)
        cross = make_record(start=_at(19), sha=S1, baseline=other)
        self.assertEqual(res.validate_record(cross), [], "the record schema alone does not catch it")
        self.world.seal(other)
        self.world.seal(cross)
        report = self.world.sweep()
        self.assertEqual({o.run_id: o.gate for o in report.outcomes}, {other["run_id"]: None, cross["run_id"]: "baseline"})
        self.assertNotIn(record_path(cross["run_id"]), self.world.store.files)


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.base, self.compared = _sentinel_pair(confirmed=[drift_item(CASES[0])])

    def test_publication_writes_record_receipt_and_bootstrap_pointer(self) -> None:
        self.world.seal(self.base)
        self.assertTrue(self.world.sweep().ok)
        run_id = self.base["run_id"]
        self.assertEqual(set(self.world.store.files), {record_path(run_id), receipt_path(run_id), "baselines/sentinel.json"})
        pointer = self.world.stored("baselines/sentinel.json")
        self.assertEqual((pointer["source"], pointer["run_id"], pointer["promoted_by"]), ("bootstrap", run_id, IDENTITY))
        self.assertEqual(res.validate_receipt(self.world.stored(receipt_path(run_id))), [])
        self.assertEqual(res.validate_record(self.world.stored(record_path(run_id))), [])

    def test_a_second_bootstrap_never_overwrites_the_lane_baseline(self) -> None:
        self.world.seal(self.base)
        self.world.sweep()
        later = make_record(start=_at(17), sha=S2)
        self.world.seal(later)
        self.world.sweep()
        self.assertEqual(self.world.stored("baselines/sentinel.json")["run_id"], self.base["run_id"])

    def test_identical_duplicate_run_is_a_noop_success(self) -> None:
        self.world.seal(self.base)
        self.world.sweep()
        commits, comments = len(self.world.store.commits), len(self.world.tracking_comments())
        report = self.world.sweep()
        self.assertTrue(report.ok)
        self.assertEqual(report.outcomes[0].status, "already-published")
        self.assertEqual((len(self.world.store.commits), len(self.world.tracking_comments())), (commits, comments))

    def test_same_run_id_with_a_different_hash_is_a_refused_conflict(self) -> None:
        self.world.seal(self.base)
        self.world.sweep()
        stored = self.world.store.files[record_path(self.base["run_id"])]
        altered = copy.deepcopy(self.base)
        altered["execution"]["duration_s"] = 12.5
        self.world.seal(self.base, data=encode_json(res.seal_record({k: v for k, v in altered.items() if k != "content_sha256"})))
        report = self.world.sweep()
        self.assertEqual([(o.status, o.gate) for o in report.outcomes], [("refused", "conflict")])
        self.assertEqual(self.world.store.files[record_path(self.base["run_id"])], stored)

    def test_conflict_is_also_refused_before_a_receipt_exists(self) -> None:
        self.world.seal(self.base)
        self.world.sweep()
        del self.world.store.files[receipt_path(self.base["run_id"])]
        altered = copy.deepcopy(self.base)
        altered["execution"]["duration_s"] = 12.5
        self.world.seal(self.base, data=encode_json(res.seal_record({k: v for k, v in altered.items() if k != "content_sha256"})))
        self.assertEqual([o.gate for o in self.world.sweep().outcomes], ["conflict"])

    def test_results_publish_in_ascending_sealed_order(self) -> None:
        later = make_record(start=_at(17), sha=S2)
        self.world.seal(later)
        self.world.seal(self.base)
        report = self.world.sweep()
        self.assertEqual([o.run_id for o in report.outcomes], [self.base["run_id"], later["run_id"]])

    def test_fractional_second_seals_publish_in_time_order(self) -> None:
        def sealed(sha: str, stamp: str) -> dict[str, Any]:
            record = make_record(start=_at(17), sha=sha)
            body = {k: v for k, v in record.items() if k != "content_sha256"}
            return res.seal_record({**body, "sealed_at": stamp})

        later, earlier = sealed(S2, "2026-09-17T01:02:00.5Z"), sealed(S3, "2026-09-17T01:02:00Z")
        for record in (later, earlier):
            self.world.seal(record)
        self.assertEqual([o.run_id for o in self.world.sweep().outcomes], [earlier["run_id"], later["run_id"]])

    def test_a_malformed_seal_never_stops_the_sweep(self) -> None:
        good = make_record(start=_at(17), sha=S2)
        self.world.seal(good)
        nested = ("[" * 100_000 + "]" * 100_000).encode()
        for index, stamp in enumerate(("2026-09-16", "2026-09-16T01:01:01", "not-a-date", 123)):
            bad = {**make_record(start=_at(18), sha=f"{index:02d}" * 6), "sealed_at": stamp}
            self.world.seal(bad, data=encode_json(bad))
        self.world.seal(make_record(start=_at(19), sha=S3), data=nested)
        report = self.world.sweep()
        statuses = [o.status for o in report.outcomes]
        self.assertEqual((statuses.count("published"), statuses.count("refused")), (1, 5))
        self.assertEqual(_outcome(report, good["run_id"]).status, "published")

    def test_an_unexpected_error_on_one_ref_is_contained(self) -> None:
        first, second = make_record(start=_at(16), sha=S0), make_record(start=_at(17), sha=S2)
        for record in (first, second):
            self.world.seal(record)
        real = sweep_module.check_record

        def flaky(record: Any, *args: Any) -> Any:
            if record["run_id"] == first["run_id"]:
                raise RuntimeError("boom")
            return real(record, *args)

        with mock.patch.object(sweep_module, "check_record", side_effect=flaky):
            report = self.world.sweep()
        self.assertEqual({o.run_id: o.status for o in report.outcomes}, {first["run_id"]: "failed", second["run_id"]: "published"})
        self.assertIn("unexpected RuntimeError", _outcome(report, first["run_id"]).detail)

    def test_a_receipted_run_is_not_regated_by_later_validation_changes(self) -> None:
        self.world.seal(self.base)
        self.world.sweep()
        fresh = make_record(start=_at(17), sha=S2)
        self.world.seal(fresh)
        refusal = Refusal("conflict", "a stricter validator")
        with mock.patch.object(sweep_module, "check_record", return_value=refusal):
            report = self.world.sweep()
        self.assertEqual({o.run_id: o.status for o in report.outcomes}, {self.base["run_id"]: "already-published", fresh["run_id"]: "refused"})

    def test_only_run_id_publishes_just_that_run(self) -> None:
        other = make_record(start=_at(17), sha=S2)
        self.world.seal(self.base)
        self.world.seal(other)
        report = self.world.sweep(only_run_id=other["run_id"])
        self.assertEqual([o.run_id for o in report.outcomes], [other["run_id"]])

    def test_local_once_is_marked_in_the_receipt(self) -> None:
        self.world.seal(self.base)
        self.world.sweep(local_once=True)
        self.assertIn("local-once", self.world.stored(receipt_path(self.base["run_id"]))["steps_done"])

    def test_staging_ref_is_deleted_only_after_the_retention_period(self) -> None:
        self.world.seal(self.base)
        self.world.sweep()
        self.world.now += timedelta(days=29)
        self.world.sweep()
        self.assertEqual(self.world.store.deleted_refs, [])
        self.world.now += timedelta(days=2)
        report = self.world.sweep()
        self.assertEqual(self.world.store.deleted_refs, [staging_ref_name(self.base["run_id"])])
        self.assertEqual(report.outcomes[0].status, "already-published")

    def test_an_unpublished_ref_is_never_deleted(self) -> None:
        self.world.seal(self.base, actor="someone-else")
        self.world.now += timedelta(days=90)
        self.world.sweep()
        self.assertEqual(self.world.store.deleted_refs, [])

    def test_malformed_staging_ref_names_are_reported(self) -> None:
        self.world.handoff.add("claude/benchmark-result-not-a-run", b"{}", sha="a" * 40, activities=None)
        report = self.world.sweep()
        self.assertEqual([(o.status, o.gate) for o in report.outcomes], [("refused", "provenance")])


class PreflightTests(unittest.TestCase):
    def test_missing_label_fails_closed_before_any_write(self) -> None:
        world = World(labels=["benchmark-regression"])
        world.seal(make_record(start=_at(16), sha=S0))
        report = world.sweep()
        self.assertIn("benchmark-tracking", report.aborted or "")
        self.assertEqual((report.outcomes, world.store.files, world.tracker.comments), ([], {}, {}))

    def test_unprovisioned_manifest_fails_closed(self) -> None:
        world = World()
        world.manifest = {**world.manifest, "health_issue": None}
        world.seal(make_record(start=_at(16), sha=S0))
        report = world.sweep()
        self.assertIn("not provisioned", report.aborted or "")
        self.assertEqual(world.store.files, {})


class LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.base = make_record(start=_at(16), sha=S0)
        self.world.seal(self.base)
        self.world.sweep()
        self.x = drift_item(CASES[0])

    def publish(self, record: dict[str, Any]) -> Any:
        self.world.seal(record)
        report = self.world.sweep()
        self.assertTrue(report.ok, report.as_dict())
        return _outcome(report, record["run_id"])

    def sentinel(self, day: int, sha: str, *confirmed: dict[str, str], comparable: Any = CASES[:3], **kw: Any) -> dict[str, Any]:
        return make_record(start=_at(day), sha=sha, baseline=self.base, confirmed=confirmed, comparable=comparable, **kw)

    def test_confirmed_drift_opens_one_labelled_issue_with_provenance(self) -> None:
        outcome = self.publish(self.sentinel(19, S1, self.x))
        (issue,) = self.world.regression_issues()
        self.assertEqual(issue.author, IDENTITY)
        self.assertEqual(markers.fingerprint_of_issue_body(issue.body), self.x["fingerprint"])
        self.assertIn(self.base["run_id"], issue.body)
        self.assertIn("/blob/", issue.body)
        self.assertEqual([a["action"] for a in outcome.actions], ["opened"])
        receipt = self.world.stored(receipt_path(outcome.run_id))
        self.assertEqual(receipt["issue_links"], [{"fingerprint": self.x["fingerprint"], "issue": issue.number, "action": "opened"}])

    def test_recurrence_while_open_comments_once_per_run(self) -> None:
        self.publish(self.sentinel(19, S1, self.x))
        second = self.sentinel(20, S2, self.x)
        outcome = self.publish(second)
        (issue,) = self.world.regression_issues()
        self.assertEqual([a["action"] for a in outcome.actions], ["commented"])
        applied = markers.applied_marker(second["run_id"], self.x["fingerprint"])
        self.assertEqual(sum(applied in c.body for c in self.world.tracker.comments[issue.number]), 1)

    def test_distinct_runs_confirming_the_same_drift_share_one_issue(self) -> None:
        self.publish(self.sentinel(19, S1, self.x))
        self.publish(self.sentinel(20, S2, self.x))
        self.assertEqual(len(self.world.regression_issues()), 1)

    def test_resolution_closes_with_a_comment(self) -> None:
        self.publish(self.sentinel(19, S1, self.x))
        outcome = self.publish(self.sentinel(20, S2))
        self.assertEqual([a["action"] for a in outcome.actions], ["closed"])
        self.assertEqual(self.world.regression_issues(), [])
        (closed,) = self.world.regression_issues("closed")
        self.assertIn("No longer reproduces", self.world.tracker.comments[closed.number][-1].body)

    def test_an_issue_no_lane_currently_covers_is_left_as_is(self) -> None:
        self.publish(self.sentinel(19, S1, self.x))
        outcome = self.publish(self.sentinel(20, S2, comparable=CASES[1:3]))
        self.assertEqual(outcome.actions, [])
        self.assertEqual(len(self.world.regression_issues()), 1)

    def test_recurrence_after_closure_opens_a_new_linked_issue(self) -> None:
        self.publish(self.sentinel(19, S1, self.x))
        self.publish(self.sentinel(20, S2))
        outcome = self.publish(self.sentinel(21, S3, self.x))
        (reopened,) = self.world.regression_issues()
        (first,) = self.world.regression_issues("closed")
        self.assertNotEqual(reopened.number, first.number)
        self.assertIn(f"Recurrence of #{first.number}", reopened.body)
        self.assertEqual(outcome.actions[0]["action"], "opened")

    def test_keep_open_blocks_the_close(self) -> None:
        self.publish(self.sentinel(19, S1, self.x))
        (issue,) = self.world.regression_issues()
        self.world.tracker.issues[issue.number] = dataclasses.replace(issue, labels=(*issue.labels, "keep-open"))
        comments = len(self.world.tracker.comments.get(issue.number, []))
        outcome = self.publish(self.sentinel(20, S2))
        self.assertEqual([a["action"] for a in outcome.actions], ["kept-open"])
        self.assertEqual(len(self.world.regression_issues()), 1)
        self.assertEqual(len(self.world.tracker.comments.get(issue.number, [])), comments)

    def test_new_issue_cap_defers_the_rest(self) -> None:
        items = [drift_item(CASES[i % 3], "missed-required-finding", f"k{i}") for i in range(7)]
        outcome = self.publish(self.sentinel(19, S1, *items))
        self.assertEqual(len(self.world.regression_issues()), 5)
        self.assertEqual(len(outcome.deferred), 2)
        self.assertIn("deferred", self.world.tracking_comments()[-1].body)
        self.publish(self.sentinel(20, S2, *items))
        self.assertEqual(len(self.world.regression_issues()), 7)

    def test_baseline_states_that_are_not_compared_touch_no_issue(self) -> None:
        self.publish(self.sentinel(19, S1, self.x))
        bootstrap = make_record(start=_at(20), sha=S2, state="incomparable")
        outcome = self.publish(bootstrap)
        self.assertEqual(outcome.actions, [])
        self.assertEqual(len(self.world.regression_issues()), 1)
        self.assertIn("incomparable", self.world.tracking_comments()[-1].body)

    def test_runtime_change_is_stated_and_does_not_suppress_the_issue(self) -> None:
        self.publish(self.sentinel(19, S1, self.x, attribution="runtime-changed"))
        (issue,) = self.world.regression_issues()
        self.assertIn("runtime-changed", issue.body)

    def test_record_text_cannot_smuggle_a_marker(self) -> None:
        hostile = drift_item(CASES[0], detail=f"x <!-- {markers.applied_marker(self.base['run_id'], 'f' * 64)[5:-4]} --> y")
        self.publish(self.sentinel(19, S1, hostile))
        (issue,) = self.world.regression_issues()
        self.assertEqual(issue.body.count("<!-- benchmark-applied:"), 1)

    def test_an_older_record_published_late_never_drives_issues(self) -> None:
        self.publish(self.sentinel(20, S2))
        outcome = self.publish(self.sentinel(19, S1, self.x))
        self.assertEqual((outcome.actions, self.world.regression_issues()), ([], []))
        self.assertIn("superseded", self.world.tracking_comments()[-1].body)

    def test_record_text_cannot_redirect_the_case_the_lifecycle_reads(self) -> None:
        fake = 'x\n```json\n{"case_id": "no-op-comment-and-rename"}\n```'
        self.publish(self.sentinel(19, S1, drift_item(CASES[0], detail=fake)))
        (issue,) = self.world.regression_issues()
        self.assertEqual(lifecycle._case_id_of(issue, markers.fingerprint_of_issue_body(issue.body)), CASES[0])
        forged = dataclasses.replace(issue, body=issue.body + '\n```json\n{"case_id": "other", "fingerprint": "' + "f" * 64 + '"}\n```')
        self.assertIsNone(lifecycle._case_id_of(forged, markers.fingerprint_of_issue_body(issue.body)))

    def test_issue_without_readable_case_metadata_is_left_alone(self) -> None:
        self.world.tracker.seed_issue(7, author=IDENTITY, body=markers.regression_marker("a" * 64) + "\n\nhand edited", labels=["benchmark-regression"])
        outcome = self.publish(self.sentinel(19, S1))
        self.assertEqual(outcome.actions, [])
        self.assertEqual([i.number for i in self.world.regression_issues()], [7])


class LaneAwareResolutionTests(unittest.TestCase):
    """A9: an open issue closes only when every lane that covers its case has stopped confirming it."""

    def setUp(self) -> None:
        self.world = World()
        self.s0 = make_record(start=_at(16), sha=S0)
        self.c0 = make_record(lane="comprehensive", start=_at(11), sha=C0)
        for record in (self.c0, self.s0):
            self.world.seal(record)
        self.assertTrue(self.world.sweep().ok)

    def publish(self, record: dict[str, Any]) -> None:
        self.world.seal(record)
        self.assertTrue(self.world.sweep().ok)

    def sentinel(self, day: int, sha: str, *confirmed: Any, comparable: Any = CASES[:3]) -> dict[str, Any]:
        return make_record(start=_at(day), sha=sha, baseline=self.s0, confirmed=confirmed, comparable=comparable)

    def comprehensive(self, day: int, sha: str, *confirmed: Any) -> dict[str, Any]:
        return make_record(lane="comprehensive", start=_at(day), sha=sha, baseline=self.c0, confirmed=confirmed, comparable=CASES)

    def test_sentinel_only_sweep_never_closes_a_comprehensive_only_regression(self) -> None:
        only_comprehensive = drift_item(CASES[3])
        self.publish(self.comprehensive(18, C1, only_comprehensive))
        self.assertEqual(len(self.world.regression_issues()), 1)
        self.publish(self.sentinel(19, S1, comparable=CASES[:3]))
        self.publish(self.sentinel(22, S2, comparable=CASES[:3]))
        self.assertEqual(len(self.world.regression_issues()), 1)
        self.publish(self.comprehensive(25, C2))
        self.assertEqual(self.world.regression_issues(), [])

    def test_a_canonical_case_stays_open_until_both_lanes_stop_reproducing_it(self) -> None:
        shared = drift_item(CASES[0])
        self.publish(self.comprehensive(18, C1, shared))
        self.publish(self.sentinel(19, S1, shared))
        self.assertEqual(len(self.world.regression_issues()), 1)
        self.publish(self.sentinel(20, S2))
        self.assertEqual(len(self.world.regression_issues()), 1, "the comprehensive lane still confirms it")
        self.publish(self.comprehensive(25, C2))
        self.assertEqual(self.world.regression_issues(), [])

    def test_an_unloadable_lane_record_disables_closing(self) -> None:
        shared = drift_item(CASES[0])
        self.publish(self.sentinel(19, S1, shared))
        self.world.store.files[record_path(self.c0["run_id"])] = b"{}"
        del self.world.handoff.refs[staging_ref_name(self.c0["run_id"])]
        self.publish(self.sentinel(20, S2))
        self.assertEqual(len(self.world.regression_issues()), 1)
        self.assertIn("could not be loaded", self.world.tracking_comments()[-1].body)


class RecoveryTests(unittest.TestCase):
    """Failure-table cases 3-5 and 7-12."""

    def setUp(self) -> None:
        self.world = World()
        self.base = make_record(start=_at(16), sha=S0)
        self.world.seal(self.base)
        self.world.sweep()
        self.x = drift_item(CASES[0])
        self.compared = make_record(start=_at(19), sha=S1, baseline=self.base, confirmed=[self.x])
        self.tracking = self.world.manifest["lanes"]["sentinel"]["tracking_issue"]

    def fail_once(self, method: str, *, when: Any = lambda *a: True, error: type = PublicationFailure) -> None:
        state = {"armed": True}

        def hook(name: str, *args: Any) -> None:
            if name == method and state["armed"] and when(*args):
                state["armed"] = False
                raise error(f"injected {method} failure")

        for target in (self.world.store, self.world.tracker):
            target.hook = hook

    def test_case3_publication_failure_is_retried_from_the_handoff(self) -> None:
        self.fail_once("commit_files")
        self.world.seal(self.compared)
        report = self.world.sweep()
        self.assertEqual(_outcome(report, self.compared["run_id"]).status, "failed")
        self.assertNotIn(receipt_path(self.compared["run_id"]), self.world.store.files)
        self.assertTrue(self.world.sweep().ok)
        self.assertIn(receipt_path(self.compared["run_id"]), self.world.store.files)

    def test_case4_evidence_post_failure_retries_without_duplicates(self) -> None:
        self.fail_once("create_comment", when=lambda issue, body: issue == self.tracking)
        self.world.seal(self.compared)
        self.assertEqual(_outcome(self.world.sweep(), self.compared["run_id"]).status, "failed")
        self.assertIn(record_path(self.compared["run_id"]), self.world.store.files)
        self.assertFalse([c for c in self.world.tracking_comments() if self.compared["run_id"] in c.body])
        self.assertTrue(self.world.sweep().ok)
        self.assertTrue(self.world.sweep().ok)
        self.assertEqual(sum(markers.run_marker(self.compared["run_id"]) in c.body for c in self.world.tracking_comments()), 1)

    def test_case5_issue_created_then_a_later_step_fails(self) -> None:
        self.fail_once("create_comment", when=lambda issue, body: issue == self.tracking)
        self.world.seal(self.compared)
        self.world.sweep()
        (issue,) = self.world.regression_issues()
        self.assertTrue(self.world.sweep().ok)
        self.assertEqual([i.number for i in self.world.regression_issues()], [issue.number])
        self.assertEqual(self.world.tracker.comments.get(issue.number, []), [], "the created body already carries the run's marker")
        receipt = self.world.stored(receipt_path(self.compared["run_id"]))
        self.assertEqual([link["action"] for link in receipt["issue_links"]], ["opened"])

    def test_case5_close_comment_then_failed_close_completes_on_retry(self) -> None:
        self.world.seal(self.compared)
        self.world.sweep()
        clean = make_record(start=_at(20), sha=S2, baseline=self.base)
        self.fail_once("close_issue")
        self.world.seal(clean)
        self.assertEqual(_outcome(self.world.sweep(), clean["run_id"]).status, "failed")
        (issue,) = self.world.regression_issues()
        self.assertTrue(self.world.sweep().ok)
        self.assertEqual(self.world.regression_issues(), [])
        marker = markers.applied_marker(clean["run_id"], self.x["fingerprint"])
        self.assertEqual(sum(marker in c.body for c in self.world.tracker.comments[issue.number]), 1)

    def test_case8_credential_failure_stops_the_sweep_with_no_fallback(self) -> None:
        self.fail_once("commit_files", error=FatalPublicationError)
        later = make_record(start=_at(20), sha=S2, baseline=self.base)
        self.world.seal(self.compared)
        self.world.seal(later)
        report = self.world.sweep()
        self.assertEqual([o.status for o in report.outcomes], ["already-published", "failed"])
        self.assertIn("injected", report.aborted or "")
        self.assertNotIn(record_path(later["run_id"]), self.world.store.files)

    def test_writes_attributed_to_another_identity_are_refused(self) -> None:
        world = World(identity="amirbena")
        world.seal(self.base)
        report = world.sweep()
        self.assertIn("not the publisher identity", report.aborted or "")
        self.assertNotIn(receipt_path(self.base["run_id"]), world.store.files)

    def test_case9_duplicate_open_issue_keeps_the_lowest_number(self) -> None:
        tracker = self.world.tracker
        tracker._next_number = 50
        create = tracker.create_issue

        def racing_create(*, title: str, body: str, labels: Any) -> Any:
            created = create(title=title, body=body, labels=labels)
            tracker.seed_issue(40, author=IDENTITY, body=markers.regression_marker(self.x["fingerprint"]) + "\n\nother pass", labels=labels)
            return created

        tracker.create_issue = racing_create  # type: ignore[method-assign]
        self.world.seal(self.compared)
        self.assertTrue(self.world.sweep().ok)
        self.assertEqual([i.number for i in self.world.regression_issues()], [40])
        self.assertIn("Duplicate of #40", tracker.comments[50][-1].body)

    def test_case12_foreign_run_marker_neither_suppresses_the_post_nor_is_edited(self) -> None:
        marker = markers.run_marker(self.compared["run_id"])
        foreign = self.world.tracker.seed_comment(self.tracking, author="amirbena", body=marker + "\nforged")
        self.world.seal(self.compared)
        self.assertTrue(self.world.sweep().ok)
        posted = [c for c in self.world.tracking_comments() if c.author == IDENTITY and marker in c.body]
        self.assertEqual(len(posted), 1)
        self.assertIn(foreign, self.world.tracking_comments())
        receipt = self.world.stored(receipt_path(self.compared["run_id"]))
        self.assertEqual(receipt["evidence_comment_url"], posted[0].url)

    def test_case12_foreign_applied_marker_does_not_suppress_a_recurrence_comment(self) -> None:
        self.world.seal(self.compared)
        self.world.sweep()
        (issue,) = self.world.regression_issues()
        second = make_record(start=_at(20), sha=S2, baseline=self.base, confirmed=[self.x])
        forged = self.world.tracker.seed_comment(issue.number, author="amirbena", body=markers.applied_marker(second["run_id"], self.x["fingerprint"]))
        self.world.seal(second)
        self.assertTrue(self.world.sweep().ok)
        genuine = [c for c in self.world.tracker.comments[issue.number] if c.author == IDENTITY]
        self.assertEqual(len(genuine), 1)
        self.assertIn(forged, self.world.tracker.comments[issue.number])

    def test_case12_a_foreign_issue_carrying_a_marker_is_data(self) -> None:
        self.world.tracker.seed_issue(9, author="mallory", body=markers.regression_marker(self.x["fingerprint"]), labels=["benchmark-regression"])
        self.world.seal(self.compared)
        self.assertTrue(self.world.sweep().ok)
        mine = [i for i in self.world.regression_issues() if i.author == IDENTITY]
        self.assertEqual(len(mine), 1)
        self.assertEqual(self.world.tracker.issues[9].state, "open")
        self.assertEqual(self.world.tracker.comments.get(9, []), [])


if __name__ == "__main__":
    unittest.main()
