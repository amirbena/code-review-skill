#!/usr/bin/env python3
"""Tests for durable issue claim-state reconciliation."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import claim_issue as ci  # noqa: E402


def issue(*labels: str, state: str = "open") -> dict[str, object]:
    return {"state": state, "labels": [{"name": label} for label in labels]}


def user_comment(comment_id: int, body: str, actor: str) -> dict[str, object]:
    return {"id": comment_id, "body": body, "user": {"login": actor, "type": "User"}}


def receipt(
    command_id: int,
    command: str,
    actor: str,
    association: str = "NONE",
    *,
    comment_id: int | None = None,
    state: str = "open",
    eligible: bool = True,
) -> dict[str, object]:
    return {
        "id": comment_id or command_id + 1000,
        "user": {"login": ci.BOT_LOGIN, "type": "Bot"},
        "body": (
            f"Command `{command}` accepted from @{actor}.\n\n"
            "<!-- issue-claim-command "
            f"id={command_id} command={command.removeprefix('/')} "
            f"actor={actor} association={association} state={state} "
            f"eligible={str(eligible).lower()} -->"
        ),
    }


def marker(comment_id: int, status: str, claimant: str, through: int) -> dict[str, object]:
    return {
        "id": comment_id,
        "user": {"login": ci.BOT_LOGIN, "type": "Bot"},
        "body": (
            f"response\n<!-- issue-claim-state status={status} "
            f"claimant={claimant} through={through} -->"
        ),
    }


def bot_history(comment_id: int, body: str, at: int) -> dict[str, object]:
    return {
        "id": comment_id,
        "created_at": datetime.fromtimestamp(at, timezone.utc).isoformat(),
        "user": {"login": ci.BOT_LOGIN, "type": "Bot"},
        "body": body,
    }


def transition(comment_id: int, actor: str, command: str, at: int) -> dict[str, object]:
    return bot_history(
        comment_id,
        f"<!-- issue-claim-transition id={comment_id} actor={actor} command={command} -->",
        at,
    )


def restriction(
    comment_id: int, actor: str, until: int, *, notified: bool = False
) -> dict[str, object]:
    return bot_history(
        comment_id,
        (
            f"<!-- issue-claim-restriction actor={actor} until={until} "
            f"notified={str(notified).lower()} -->"
        ),
        until - 10,
    )


class ClaimReconciliationTests(unittest.TestCase):
    def test_available_eligible_issue_can_be_claimed(self) -> None:
        result = ci.reconcile(issue("help wanted"), [receipt(10, "/claim", "alice")])
        self.assertEqual(result["claimant"], "alice")
        self.assertEqual(result["add_label"], "claimed")
        self.assertIn("claimant=alice through=10", result["comment"])

    def test_ineligible_and_closed_issues_are_not_claimed(self) -> None:
        ineligible = ci.reconcile(
            issue("bug"), [receipt(10, "/claim", "alice", eligible=False)]
        )
        closed = ci.reconcile(
            issue("help wanted", state="closed"),
            [receipt(10, "/claim", "alice", state="closed")],
        )
        self.assertIsNone(ineligible["claimant"])
        self.assertIn("not open for direct claiming", ineligible["comment"])
        self.assertIsNone(closed["claimant"])
        self.assertIn("closed", closed["comment"])

    def test_later_eligibility_does_not_reauthorize_old_claim(self) -> None:
        comments = [
            receipt(10, "/claim", "alice", eligible=False),
            receipt(11, "/claim", "bob"),
        ]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertEqual(result["claimant"], "bob")

    def test_contributor_commands_and_receipt_lookalikes_are_ignored(self) -> None:
        fake = receipt(9, "/claim", "mallory")
        fake["user"] = {"login": "mallory", "type": "User"}
        comments = [user_comment(10, "/claim", "alice"), fake]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["through"], 0)

    def test_malformed_trusted_receipt_fails_closed(self) -> None:
        malformed = receipt(10, "/claim", "alice")
        malformed["body"] = "<!-- issue-claim-command id=10 command=/claim actor=alice -->"
        result = ci.reconcile(issue("help wanted"), [malformed])
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["through"], 0)

        malformed = receipt(10, "/claim", "alice")
        malformed["body"] = f"{malformed['body']} unexpected"
        result = ci.reconcile(issue("help wanted"), [malformed])
        self.assertIsNone(result["claimant"])

    def test_duplicate_receipts_are_one_semantic_command(self) -> None:
        comments = [
            receipt(10, "/claim", "alice", comment_id=100),
            receipt(10, "/claim", "alice", comment_id=101),
            receipt(11, "/unclaim", "alice", comment_id=102),
        ]
        result = ci.reconcile(issue("help wanted", "claimed"), comments)
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["through"], 11)

    def test_conflicting_trusted_receipts_fail_closed(self) -> None:
        comments = [receipt(10, "/claim", "alice"), receipt(10, "/claim", "bob")]
        with self.assertRaisesRegex(ValueError, "conflicting trusted receipts"):
            ci.reconcile(issue("help wanted"), comments)

    def test_same_id_in_receipt_and_user_history_is_not_double_counted(self) -> None:
        comments = [
            user_comment(10, "/unclaim", "mallory"),
            receipt(10, "/claim", "alice"),
        ]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertEqual(result["claimant"], "alice")

    def test_edited_or_deleted_claim_comment_does_not_change_receipt(self) -> None:
        accepted = receipt(10, "/claim", "alice")
        edited = ci.reconcile(
            issue("help wanted"), [user_comment(10, "not a command", "alice"), accepted]
        )
        deleted = ci.reconcile(issue("help wanted"), [accepted])
        self.assertEqual(edited["claimant"], "alice")
        self.assertEqual(deleted["claimant"], "alice")

    def test_edited_or_deleted_unclaim_comment_does_not_change_receipt(self) -> None:
        comments = [receipt(10, "/claim", "alice"), receipt(11, "/unclaim", "alice")]
        edited = ci.reconcile(
            issue("help wanted", "claimed"),
            [*comments, user_comment(11, "not a command", "alice")],
        )
        deleted = ci.reconcile(issue("help wanted", "claimed"), comments)
        self.assertIsNone(edited["claimant"])
        self.assertIsNone(deleted["claimant"])
        self.assertEqual(deleted["remove_label"], "claimed")

    def test_second_and_duplicate_claim_preserve_first_claimant(self) -> None:
        comments = [
            receipt(10, "/claim", "alice"),
            receipt(11, "/claim", "alice"),
            receipt(12, "/claim", "bob"),
        ]
        result = ci.reconcile(issue("good first issue"), comments)
        self.assertEqual(result["claimant"], "alice")

    def test_claimant_and_collaborator_can_unclaim(self) -> None:
        claimed = marker(20, "active", "alice", 10)
        claimant_release = ci.reconcile(
            issue("help wanted", "claimed"), [claimed, receipt(21, "/unclaim", "alice")]
        )
        maintainer_release = ci.reconcile(
            issue("help wanted", "claimed"),
            [claimed, receipt(21, "/unclaim", "maint", "COLLABORATOR")],
        )
        self.assertEqual(claimant_release["remove_label"], "claimed")
        self.assertIsNone(maintainer_release["claimant"])

    def test_unrelated_user_cannot_unclaim(self) -> None:
        result = ci.reconcile(
            issue("help wanted", "claimed"),
            [marker(20, "active", "alice", 10), receipt(21, "/unclaim", "bob")],
        )
        self.assertEqual(result["claimant"], "alice")
        self.assertIn("Only @alice or a maintainer", result["comment"])

    def test_orphan_label_cannot_be_released_by_unrelated_user(self) -> None:
        result = ci.reconcile(
            issue("help wanted", "claimed"), [receipt(21, "/unclaim", "bob")]
        )
        self.assertEqual(result["remove_label"], "")

    def test_label_only_claim_survives_original_comment_deletion(self) -> None:
        comments = [receipt(10, "/claim", "alice"), receipt(11, "/unclaim", "bob")]
        result = ci.reconcile(issue("help wanted", "claimed"), comments)
        self.assertEqual(result["claimant"], "alice")
        self.assertEqual(result["remove_label"], "")

    def test_claim_unclaim_claim_with_deleted_middle_comment(self) -> None:
        comments = [
            receipt(10, "/claim", "alice"),
            receipt(11, "/unclaim", "alice"),
            receipt(12, "/claim", "bob"),
        ]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertEqual(result["claimant"], "bob")
        self.assertEqual(result["through"], 12)

    def test_competing_claim_and_edited_pending_command_keep_order(self) -> None:
        comments = [
            receipt(10, "/claim", "alice"),
            user_comment(11, "edited", "bob"),
            receipt(11, "/claim", "bob"),
            receipt(12, "/unclaim", "alice"),
        ]
        result = ci.reconcile(issue("help wanted", "claimed"), comments)
        self.assertIsNone(result["claimant"])

    def test_receipt_order_uses_original_comment_id(self) -> None:
        comments = [
            receipt(12, "/claim", "bob", comment_id=100),
            receipt(10, "/claim", "alice", comment_id=102),
            receipt(11, "/unclaim", "alice", comment_id=101),
        ]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertEqual(result["claimant"], "bob")

    def test_repeated_unclaim_is_idempotent(self) -> None:
        comments = [
            receipt(10, "/claim", "alice"),
            receipt(11, "/unclaim", "alice"),
            receipt(12, "/unclaim", "alice"),
        ]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["remove_label"], "")

    def test_claim_partial_mutations_recover_from_receipt(self) -> None:
        missing_label = ci.reconcile(issue("help wanted"), [receipt(10, "/claim", "alice")])
        missing_checkpoint = ci.reconcile(
            issue("help wanted", "claimed"), [receipt(10, "/claim", "alice")]
        )
        self.assertEqual(missing_label["add_label"], "claimed")
        self.assertEqual(missing_checkpoint["claimant"], "alice")
        self.assertEqual(missing_checkpoint["add_label"], "")

    def test_unclaim_partial_mutations_recover_from_receipt(self) -> None:
        comments = [marker(20, "active", "alice", 10), receipt(21, "/unclaim", "alice")]
        label_present = ci.reconcile(issue("help wanted", "claimed"), comments)
        label_absent = ci.reconcile(issue("help wanted"), comments)
        self.assertEqual(label_present["remove_label"], "claimed")
        self.assertEqual(label_absent["remove_label"], "")
        self.assertIsNone(label_absent["claimant"])

    def test_lower_checkpoint_never_moves_receipt_watermark_backward(self) -> None:
        comments = [
            receipt(10, "/claim", "alice"),
            receipt(11, "/unclaim", "alice"),
            marker(200, "active", "wrong", 10),
        ]
        result = ci.reconcile(issue("help wanted", "claimed"), comments)
        self.assertEqual(result["through"], 11)
        self.assertIsNone(result["claimant"])

    def test_untrusted_checkpoint_is_ignored(self) -> None:
        forged = marker(20, "active", "mallory", 999)
        forged["user"] = {"login": "other-bot[bot]", "type": "Bot"}
        result = ci.reconcile(
            issue("help wanted"), [forged, receipt(10, "/claim", "alice")]
        )
        self.assertEqual(result["claimant"], "alice")


class ClaimChurnProtectionTests(unittest.TestCase):
    NOW = 10_000

    def reconcile(
        self,
        current_comments: list[dict[str, object]],
        history: list[dict[str, object]] | None = None,
        *,
        current_issue: dict[str, object] | None = None,
        threshold: int = 4,
        now: int | None = None,
    ) -> dict[str, object]:
        return ci.reconcile(
            current_issue or issue("help wanted"),
            current_comments,
            history or [],
            now=self.NOW if now is None else now,
            churn_threshold=threshold,
            churn_window_seconds=100,
            cooldown_seconds=300,
        )

    def test_normal_claim_and_one_claim_unclaim_cycle_remain_allowed(self) -> None:
        claimed = self.reconcile([receipt(10, "/claim", "alice")])
        self.assertEqual(claimed["claimant"], "alice")
        self.assertNotIn("issue-claim-restriction", claimed["comment"])

        released = self.reconcile(
            [marker(20, "active", "alice", 10), receipt(21, "/unclaim", "alice")],
            [transition(1, "alice", "claim", self.NOW - 10)],
            current_issue=issue("help wanted", "claimed"),
        )
        self.assertIsNone(released["claimant"])
        self.assertNotIn("issue-claim-restriction", released["comment"])

    def test_activity_below_threshold_remains_allowed(self) -> None:
        history = [
            transition(1, "alice", "claim", self.NOW - 30),
            transition(2, "alice", "unclaim", self.NOW - 20),
        ]
        result = self.reconcile([receipt(10, "/claim", "alice")], history)
        self.assertEqual(result["claimant"], "alice")
        self.assertNotIn("issue-claim-restriction", result["comment"])

    def test_threshold_transition_activates_repository_wide_restriction(self) -> None:
        history = [
            transition(1, "alice", "claim", self.NOW - 30),
            transition(2, "alice", "unclaim", self.NOW - 20),
            transition(3, "alice", "claim", self.NOW - 10),
        ]
        result = self.reconcile(
            [marker(20, "active", "alice", 9), receipt(10, "/unclaim", "alice")],
            history,
            current_issue=issue("help wanted", "claimed"),
        )
        self.assertIsNone(result["claimant"])
        self.assertIn("actor=alice until=10300 notified=false", result["comment"])
        self.assertIn("temporarily unavailable", result["comment"])

    def test_retained_receipts_reconstruct_state_without_reemitting_transitions(self) -> None:
        first = self.reconcile([receipt(10, "/claim", "alice")], threshold=6)
        first_checkpoint = bot_history(5010, first["comment"], self.NOW - 20)

        second = self.reconcile(
            [
                receipt(10, "/claim", "alice"),
                first_checkpoint,
                receipt(20, "/unclaim", "alice"),
            ],
            [first_checkpoint],
            current_issue=issue("help wanted", "claimed"),
            threshold=6,
        )
        self.assertNotIn("issue-claim-transition id=10", second["comment"])
        self.assertEqual(second["comment"].count("issue-claim-transition"), 1)
        self.assertIn("issue-claim-transition id=20", second["comment"])

        second_checkpoint = bot_history(5020, second["comment"], self.NOW - 10)
        third = self.reconcile(
            [
                receipt(20, "/unclaim", "alice"),
                second_checkpoint,
                receipt(10, "/claim", "alice"),
                first_checkpoint,
                receipt(30, "/claim", "alice"),
            ],
            [second_checkpoint, first_checkpoint],
            threshold=6,
        )
        self.assertEqual(third["comment"].count("issue-claim-transition"), 1)
        self.assertIn("issue-claim-transition id=30", third["comment"])

    def test_duplicate_transition_identity_counts_once_at_exact_threshold(self) -> None:
        duplicate_a = transition(10, "alice", "claim", self.NOW - 30)
        duplicate_b = transition(10, "alice", "claim", self.NOW - 20)
        duplicate_b["id"] = 110
        history = [
            duplicate_b,
            transition(11, "alice", "unclaim", self.NOW - 15),
            duplicate_a,
        ]
        below = self.reconcile([receipt(12, "/claim", "alice")], history, threshold=4)
        self.assertNotIn("issue-claim-restriction", below["comment"])

        checkpoint = bot_history(5012, below["comment"], self.NOW - 5)
        exact = self.reconcile(
            [
                receipt(10, "/claim", "alice"),
                receipt(11, "/unclaim", "alice"),
                receipt(12, "/claim", "alice"),
                checkpoint,
                receipt(13, "/unclaim", "alice"),
            ],
            [*history, checkpoint],
            current_issue=issue("help wanted", "claimed"),
            threshold=4,
        )
        self.assertIn("issue-claim-restriction", exact["comment"])
        self.assertEqual(exact["comment"].count("issue-claim-transition"), 1)

    def test_legacy_and_malformed_transition_markers_are_ignored(self) -> None:
        malformed = bot_history(
            1,
            "<!-- issue-claim-transition id=bad actor=alice command=claim -->",
            self.NOW - 10,
        )
        legacy = bot_history(
            2,
            "<!-- issue-claim-transition actor=alice command=claim -->",
            self.NOW - 10,
        )
        result = self.reconcile(
            [receipt(10, "/claim", "alice")],
            [malformed, legacy],
            threshold=2,
        )
        self.assertNotIn("issue-claim-restriction", result["comment"])

    def test_conflicting_trusted_transition_identity_fails_closed(self) -> None:
        conflicting = transition(10, "bob", "claim", self.NOW - 10)
        conflicting["id"] = 110
        with self.assertRaisesRegex(ValueError, "conflicting trusted transitions"):
            self.reconcile(
                [receipt(12, "/claim", "alice")],
                [
                    transition(10, "alice", "claim", self.NOW - 20),
                    conflicting,
                ],
            )

    def test_restricted_actor_cannot_claim_same_or_different_issue(self) -> None:
        active = [restriction(1, "alice", self.NOW + 100)]
        for labels in (("help wanted",), ("good first issue",)):
            with self.subTest(labels=labels):
                result = self.reconcile(
                    [receipt(10, "/claim", "alice")],
                    active,
                    current_issue=issue(*labels),
                )
                self.assertIsNone(result["claimant"])
                self.assertFalse(result["persist_receipt"])
                self.assertTrue(result["post_comment"])
                self.assertIn("temporarily unavailable", result["comment"])

    def test_restriction_is_isolated_per_actor(self) -> None:
        result = self.reconcile(
            [receipt(10, "/claim", "bob")],
            [restriction(1, "alice", self.NOW + 100)],
        )
        self.assertEqual(result["claimant"], "bob")

    def test_cooldown_expiry_restores_claiming_without_extending_it(self) -> None:
        active = restriction(1, "alice", self.NOW + 100)
        first = self.reconcile([receipt(10, "/claim", "alice")], [active])
        self.assertIn("until=10100", first["comment"])

        notified = restriction(2, "alice", self.NOW + 100, notified=True)
        retry = self.reconcile([receipt(11, "/claim", "alice")], [active, notified])
        self.assertFalse(retry["post_comment"])
        self.assertFalse(retry["persist_receipt"])
        self.assertNotIn("until=10400", retry["comment"])

        expired = self.reconcile(
            [receipt(12, "/claim", "alice")], [active, notified], now=self.NOW + 100
        )
        self.assertEqual(expired["claimant"], "alice")

    def test_stale_activity_outside_window_does_not_count(self) -> None:
        history = [
            transition(1, "alice", "claim", self.NOW - 101),
            transition(2, "alice", "unclaim", self.NOW - 100),
            transition(3, "alice", "claim", self.NOW - 10),
        ]
        result = self.reconcile(
            [marker(20, "active", "alice", 9), receipt(10, "/unclaim", "alice")],
            history,
            current_issue=issue("help wanted", "claimed"),
        )
        self.assertNotIn("issue-claim-restriction", result["comment"])

    def test_failed_noop_and_unauthorized_commands_do_not_count(self) -> None:
        cases = [
            (issue("bug"), [receipt(10, "/claim", "alice", eligible=False)]),
            (issue("help wanted", state="closed"), [receipt(10, "/claim", "alice", state="closed")]),
            (issue("help wanted", "claimed"), [marker(20, "active", "bob", 9), receipt(10, "/claim", "alice")]),
            (issue("help wanted", "claimed"), [marker(20, "active", "bob", 9), receipt(10, "/unclaim", "alice")]),
        ]
        history = [
            transition(1, "alice", "claim", self.NOW - 30),
            transition(2, "alice", "unclaim", self.NOW - 20),
            transition(3, "alice", "claim", self.NOW - 10),
        ]
        for current_issue, comments in cases:
            with self.subTest(current_issue=current_issue, comments=comments):
                result = self.reconcile(comments, history, current_issue=current_issue)
                self.assertNotIn("issue-claim-restriction", result["comment"])

    def test_restricted_actor_can_still_unclaim(self) -> None:
        result = self.reconcile(
            [marker(20, "active", "alice", 9), receipt(10, "/unclaim", "alice")],
            [restriction(1, "alice", self.NOW + 100)],
            current_issue=issue("help wanted", "claimed"),
        )
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["remove_label"], "claimed")

    def test_churn_guard_precedes_existing_claim_errors_to_close_spam_bypasses(self) -> None:
        active = [restriction(1, "alice", self.NOW + 100)]
        ineligible = self.reconcile(
            [receipt(10, "/claim", "alice", eligible=False)],
            active,
            current_issue=issue("bug"),
        )
        claimed = self.reconcile(
            [marker(20, "active", "bob", 9), receipt(10, "/claim", "alice")],
            active,
            current_issue=issue("help wanted", "claimed"),
        )
        self.assertIn("temporarily unavailable", ineligible["comment"])
        self.assertIn("temporarily unavailable", claimed["comment"])
        self.assertFalse(ineligible["persist_receipt"])
        self.assertFalse(claimed["persist_receipt"])

    def test_invalid_configuration_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be positive"):
            ci.reconcile(issue("help wanted"), [], now=self.NOW, churn_threshold=0)

    def test_default_configuration_is_documented_and_conservative(self) -> None:
        self.assertEqual(ci.DEFAULT_CHURN_THRESHOLD, 6)
        self.assertEqual(ci.DEFAULT_CHURN_WINDOW_SECONDS, 600)
        self.assertEqual(ci.DEFAULT_CLAIM_COOLDOWN_SECONDS, 1800)

        workflow = yaml.safe_load(
            (REPO_ROOT / ".github/workflows/claim-issue.yml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            workflow["env"],
            {
                "CLAIM_CHURN_THRESHOLD": ci.DEFAULT_CHURN_THRESHOLD,
                "CLAIM_CHURN_WINDOW_SECONDS": ci.DEFAULT_CHURN_WINDOW_SECONDS,
                "CLAIM_COOLDOWN_SECONDS": ci.DEFAULT_CLAIM_COOLDOWN_SECONDS,
            },
        )
        contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        normalized_contributing = " ".join(contributing.split())
        self.assertIn(
            "Six such changes by one actor within ten minutes temporarily disable "
            "that actor's repository-wide claim ability for thirty minutes",
            normalized_contributing,
        )


class MainContractTests(unittest.TestCase):
    def test_reconciliation_uses_persisted_receipt_when_user_comment_api_lags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            issue_path = temp_path / "issue.json"
            comments_path = temp_path / "comments.json"
            output_path = temp_path / "output.txt"
            response_path = temp_path / "response.md"
            issue_path.write_text(json.dumps(issue("help wanted")), encoding="utf-8")
            comments_path.write_text(json.dumps([receipt(42, "/claim", "alice")]), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                return_code = ci.main(
                    [
                        "--issue-json",
                        str(issue_path),
                        "--comments-json",
                        str(comments_path),
                        "--github-output",
                        str(output_path),
                        "--comment-file",
                        str(response_path),
                    ]
                )

            self.assertEqual(return_code, 0)
            outputs = dict(
                line.split("=", 1)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual(outputs["add_label"], "claimed")
            self.assertIn("claimant=alice through=42", response_path.read_text(encoding="utf-8"))

    def test_workflow_serializes_repository_and_suppresses_repeat_rejections(self) -> None:
        workflow_path = REPO_ROOT / ".github/workflows/claim-issue.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        parsed_workflow = yaml.safe_load(workflow)
        concurrency = parsed_workflow["jobs"]["reconcile"]["concurrency"]
        self.assertEqual(concurrency["group"], "claim-issue-${{ github.repository_id }}")
        self.assertFalse(concurrency["cancel-in-progress"])
        self.assertEqual(concurrency["queue"], "max")
        self.assertIn("repository-comments-json", workflow)
        self.assertIn("outputs.persist_receipt == 'true'", workflow)
        self.assertIn("outputs.post_comment == 'true'", workflow)
        self.assertIn("github.event.comment.id", workflow)
        self.assertIn("github.event.comment.user.login", workflow)
        self.assertIn("github.event.comment.author_association", workflow)
        checkpoint = workflow.index("- name: Checkpoint reconciled state")
        add_label = workflow.index("- name: Apply claim state")
        remove_label = workflow.index("- name: Apply released state")
        self.assertLess(checkpoint, add_label)
        self.assertLess(checkpoint, remove_label)


if __name__ == "__main__":
    unittest.main()
