#!/usr/bin/env python3
"""Tests for durable issue claim-state reconciliation."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_workflow_persists_receipt_before_replaceable_reconciliation(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/claim-issue.yml").read_text(
            encoding="utf-8"
        )
        acceptance = workflow.index("accept-command:")
        reconciliation = workflow.index("reconcile:")
        self.assertLess(acceptance, reconciliation)
        self.assertNotIn("concurrency:", workflow[acceptance:reconciliation])
        self.assertIn("needs: accept-command", workflow[reconciliation:])
        self.assertIn("github.event.comment.id", workflow[acceptance:reconciliation])
        self.assertIn("github.event.comment.user.login", workflow[acceptance:reconciliation])
        self.assertIn("github.event.comment.author_association", workflow[acceptance:reconciliation])


if __name__ == "__main__":
    unittest.main()
