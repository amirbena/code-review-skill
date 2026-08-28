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


def command(comment_id: int, body: str, actor: str, association: str = "NONE") -> dict[str, object]:
    return {
        "id": comment_id,
        "body": body,
        "user": {"login": actor, "type": "User"},
        "author_association": association,
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
        result = ci.reconcile(issue("help wanted"), [command(10, "/claim", "alice")])
        self.assertEqual(result["claimant"], "alice")
        self.assertEqual(result["add_label"], "claimed")
        self.assertIn("claimant=alice through=10", result["comment"])

    def test_ineligible_and_closed_issues_are_not_claimed(self) -> None:
        ineligible = ci.reconcile(issue("bug"), [command(10, "/claim", "alice")])
        closed = ci.reconcile(
            issue("help wanted", state="closed"), [command(10, "/claim", "alice")]
        )
        self.assertIsNone(ineligible["claimant"])
        self.assertIn("not open for direct claiming", ineligible["comment"])
        self.assertIsNone(closed["claimant"])
        self.assertIn("closed", closed["comment"])

    def test_malformed_commands_are_not_replayed(self) -> None:
        malformed = ["/claim please", "please /claim", "/CLAIM", "/claim\nsomething"]
        comments = [command(index, body, "alice") for index, body in enumerate(malformed, 1)]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["through"], 0)

    def test_second_and_duplicate_claim_preserve_first_claimant(self) -> None:
        comments = [
            command(10, "/claim", "alice"),
            command(11, "/claim", "alice"),
            command(12, "/claim", "bob"),
        ]
        result = ci.reconcile(issue("good first issue"), comments)
        self.assertEqual(result["claimant"], "alice")
        self.assertIn("already claimed by @alice", result["comment"])

    def test_claimant_and_collaborator_can_unclaim(self) -> None:
        claimed = marker(20, "active", "alice", 10)
        claimant_release = ci.reconcile(
            issue("help wanted", "claimed"), [claimed, command(21, "/unclaim", "alice")]
        )
        maintainer_release = ci.reconcile(
            issue("help wanted", "claimed"),
            [claimed, command(21, "/unclaim", "maint", "COLLABORATOR")],
        )
        self.assertIsNone(claimant_release["claimant"])
        self.assertEqual(claimant_release["remove_label"], "claimed")
        self.assertIsNone(maintainer_release["claimant"])

    def test_unrelated_user_cannot_unclaim(self) -> None:
        result = ci.reconcile(
            issue("help wanted", "claimed"),
            [marker(20, "active", "alice", 10), command(21, "/unclaim", "bob")],
        )
        self.assertEqual(result["claimant"], "alice")
        self.assertIn("Only @alice or a maintainer", result["comment"])

    def test_claim_unclaim_claim_burst_converges_to_last_claim(self) -> None:
        comments = [
            command(10, "/claim", "alice"),
            command(11, "/unclaim", "alice"),
            command(12, "/claim", "bob"),
        ]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertEqual(result["claimant"], "bob")
        self.assertEqual(result["through"], 12)

    def test_competing_claim_then_claimant_unclaim_is_available(self) -> None:
        comments = [
            command(10, "/claim", "alice"),
            command(11, "/claim", "bob"),
            command(12, "/unclaim", "alice"),
        ]
        result = ci.reconcile(issue("help wanted", "claimed"), comments)
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["remove_label"], "claimed")

    def test_multiple_competing_claims_have_one_owner(self) -> None:
        comments = [command(i, "/claim", actor) for i, actor in enumerate(("a", "b", "c"), 10)]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertEqual(result["claimant"], "a")

    def test_repeated_unclaim_is_idempotent(self) -> None:
        comments = [
            command(10, "/claim", "alice"),
            command(11, "/unclaim", "alice"),
            command(12, "/unclaim", "alice"),
        ]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["remove_label"], "")
        self.assertIn("already available", result["comment"])

    def test_label_only_partial_claim_recovers_on_repeat_claim(self) -> None:
        result = ci.reconcile(
            issue("help wanted", "claimed"),
            [command(10, "/claim", "alice"), command(11, "/claim", "alice")],
        )
        self.assertEqual(result["claimant"], "alice")
        self.assertEqual(result["add_label"], "")
        self.assertIn("status=active", result["comment"])

    def test_failed_claim_label_mutation_is_retried_before_checkpoint(self) -> None:
        result = ci.reconcile(
            issue("help wanted"),
            [command(10, "/claim", "alice")],
        )
        self.assertEqual(result["add_label"], "claimed")
        self.assertIn("status=active", result["comment"])

    def test_label_only_partial_claim_can_be_released_by_claimant(self) -> None:
        result = ci.reconcile(
            issue("help wanted", "claimed"),
            [command(10, "/claim", "alice"), command(11, "/unclaim", "alice")],
        )
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["remove_label"], "claimed")

    def test_marker_only_partial_release_does_not_block_next_claim(self) -> None:
        comments = [
            marker(20, "active", "alice", 10),
            command(21, "/unclaim", "alice"),
            command(22, "/claim", "bob"),
        ]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertEqual(result["claimant"], "bob")
        self.assertEqual(result["add_label"], "claimed")

    def test_marker_only_partial_release_repeat_is_idempotent(self) -> None:
        comments = [
            marker(20, "active", "alice", 10),
            command(21, "/unclaim", "alice"),
            command(22, "/unclaim", "alice"),
        ]
        result = ci.reconcile(issue("help wanted"), comments)
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["remove_label"], "")

    def test_failed_unclaim_label_mutation_is_retried_before_checkpoint(self) -> None:
        result = ci.reconcile(
            issue("help wanted", "claimed"),
            [marker(20, "active", "alice", 10), command(21, "/unclaim", "alice")],
        )
        self.assertEqual(result["remove_label"], "claimed")
        self.assertIn("status=available", result["comment"])

    def test_untrusted_marker_is_ignored(self) -> None:
        forged = marker(20, "active", "mallory", 999)
        forged["user"] = {"login": "other-bot[bot]", "type": "Bot"}
        result = ci.reconcile(
            issue("help wanted"), [forged, command(10, "/claim", "alice")]
        )
        self.assertEqual(result["claimant"], "alice")

    def test_checkpoint_prevents_replaying_old_commands(self) -> None:
        comments = [
            command(10, "/claim", "alice"),
            marker(20, "active", "alice", 10),
            command(21, "/unclaim", "alice"),
        ]
        result = ci.reconcile(issue("help wanted", "claimed"), [comments])
        self.assertIsNone(result["claimant"])
        self.assertEqual(result["through"], 21)


class MainContractTests(unittest.TestCase):
    def test_trigger_comment_is_reconciled_when_api_page_has_not_caught_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            issue_path = temp_path / "issue.json"
            comments_path = temp_path / "comments.json"
            output_path = temp_path / "output.txt"
            response_path = temp_path / "response.md"
            issue_path.write_text(json.dumps(issue("help wanted")), encoding="utf-8")
            comments_path.write_text("[]", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                return_code = ci.main(
                    [
                        "--issue-json",
                        str(issue_path),
                        "--comments-json",
                        str(comments_path),
                        "--event-comment-id",
                        "42",
                        "--command",
                        "/claim",
                        "--actor",
                        "alice",
                        "--association",
                        "NONE",
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
            self.assertIn(
                "claimant=alice through=42",
                response_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
