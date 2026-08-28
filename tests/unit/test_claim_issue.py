#!/usr/bin/env python3
"""Tests for issue claim planning."""

from __future__ import annotations

import sys
import unittest

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import claim_issue as ci  # noqa: E402


def issue(*labels: str, state: str = "open") -> dict[str, object]:
    return {"state": state, "labels": [{"name": label} for label in labels]}


def marker(status: str, claimant: str, *, login: str = ci.BOT_LOGIN) -> dict[str, object]:
    return {
        "user": {"login": login, "type": "Bot"},
        "body": f"response\n<!-- issue-claim:{status} claimant={claimant} -->",
    }


class ClaimPlanTests(unittest.TestCase):
    def test_available_eligible_issue_can_be_claimed(self) -> None:
        result = ci.plan(
            command="/claim",
            actor="alice",
            association="NONE",
            issue=issue("help wanted"),
            comments=[],
        )
        self.assertEqual(result["action"], "claim")
        self.assertEqual(result["add_label"], "claimed")
        self.assertIn("claimant=alice", result["comment"])

    def test_second_claim_preserves_current_claimant(self) -> None:
        result = ci.plan(
            command="/claim",
            actor="bob",
            association="NONE",
            issue=issue("good first issue", "claimed"),
            comments=[marker("active", "alice")],
        )
        self.assertEqual(result["action"], "comment")
        self.assertIn("@alice", result["comment"])

    def test_claimant_can_unclaim(self) -> None:
        result = ci.plan(
            command="/unclaim",
            actor="alice",
            association="NONE",
            issue=issue("help wanted", "claimed"),
            comments=[marker("active", "alice")],
        )
        self.assertEqual(result["action"], "unclaim")
        self.assertEqual(result["remove_label"], "claimed")

    def test_unrelated_user_cannot_unclaim(self) -> None:
        result = ci.plan(
            command="/unclaim",
            actor="bob",
            association="CONTRIBUTOR",
            issue=issue("help wanted", "claimed"),
            comments=[marker("active", "alice")],
        )
        self.assertEqual(result["action"], "comment")
        self.assertIn("Only @alice or a maintainer", result["comment"])

    def test_maintainer_can_release_someone_elses_claim(self) -> None:
        result = ci.plan(
            command="/unclaim",
            actor="maintainer",
            association="OWNER",
            issue=issue("help wanted", "claimed"),
            comments=[marker("active", "alice")],
        )
        self.assertEqual(result["action"], "unclaim")

    def test_non_eligible_issue_is_not_claimed(self) -> None:
        result = ci.plan(
            command="/claim",
            actor="alice",
            association="NONE",
            issue=issue("bug"),
            comments=[],
        )
        self.assertEqual(result["action"], "comment")
        self.assertIn("not open for direct claiming", result["comment"])

    def test_untrusted_marker_is_ignored(self) -> None:
        result = ci.plan(
            command="/claim",
            actor="alice",
            association="NONE",
            issue=issue("help wanted"),
            comments=[marker("active", "mallory", login="other-bot[bot]")],
        )
        self.assertEqual(result["action"], "claim")

    def test_latest_trusted_marker_controls_state(self) -> None:
        comments = [marker("active", "alice"), marker("released", "alice")]
        self.assertIsNone(ci.current_claimant([comments]))

    def test_non_command_is_ignored(self) -> None:
        result = ci.plan(
            command="please /claim this",
            actor="alice",
            association="NONE",
            issue=issue("help wanted"),
            comments=[],
        )
        self.assertEqual(result, {"action": "ignore"})


if __name__ == "__main__":
    unittest.main()
