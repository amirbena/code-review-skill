#!/usr/bin/env python3
"""Reconcile issue claim state from trusted command receipts."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

CLAIMED_LABEL = "claimed"
MAINTAINER_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
BOT_LOGIN = "github-actions[bot]"
MARKER_RE = re.compile(
    r"<!-- issue-claim-state status=(active|available) "
    r"claimant=([A-Za-z0-9-]+|none) through=([0-9]+) -->"
)
RECEIPT_RE = re.compile(
    r"<!-- issue-claim-command id=([0-9]+) command=(claim|unclaim) "
    r"actor=([A-Za-z0-9-]+) association=([A-Z_]+) "
    r"state=(open|closed) eligible=(true|false) -->"
)


def _label_names(issue: dict[str, Any]) -> set[str]:
    return {
        label["name"] if isinstance(label, dict) else str(label)
        for label in issue.get("labels", [])
    }


def _flatten_comments(comments: Iterable[Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for item in comments:
        if isinstance(item, list):
            flattened.extend(comment for comment in item if isinstance(comment, dict))
        elif isinstance(item, dict):
            flattened.append(item)
    return flattened


def _comment_id(comment: dict[str, Any]) -> int:
    try:
        return int(comment.get("id", 0))
    except (TypeError, ValueError):
        return 0


def _trusted_bot_comment(comment: dict[str, Any]) -> bool:
    user = comment.get("user") or {}
    return user.get("login") == BOT_LOGIN and user.get("type") == "Bot"


def _checkpoints(comments: Iterable[Any]) -> list[tuple[int, str | None, int]]:
    checkpoints: list[tuple[int, str | None, int]] = []
    for comment in _flatten_comments(comments):
        if not _trusted_bot_comment(comment):
            continue
        match = MARKER_RE.search(comment.get("body") or "")
        if not match:
            continue
        claimant = match.group(2) if match.group(1) == "active" else None
        checkpoints.append((_comment_id(comment), claimant, int(match.group(3))))
    return sorted(checkpoints)


def _receipts(comments: Iterable[Any]) -> list[dict[str, Any]]:
    receipts: dict[int, dict[str, Any]] = {}
    for comment in sorted(_flatten_comments(comments), key=_comment_id):
        if not _trusted_bot_comment(comment):
            continue
        match = RECEIPT_RE.search(comment.get("body") or "")
        if not match:
            continue
        receipt = {
            "id": int(match.group(1)),
            "command": f"/{match.group(2)}",
            "actor": match.group(3),
            "association": match.group(4),
            "issue_open": match.group(5) == "open",
            "eligible": match.group(6) == "true",
        }
        expected_body = (
            f"Command `{receipt['command']}` accepted from @{receipt['actor']}.\n\n"
            f"<!-- issue-claim-command id={receipt['id']} "
            f"command={receipt['command'].removeprefix('/')} actor={receipt['actor']} "
            f"association={receipt['association']} "
            f"state={'open' if receipt['issue_open'] else 'closed'} "
            f"eligible={str(receipt['eligible']).lower()} -->"
        )
        if (comment.get("body") or "").rstrip("\n") != expected_body:
            continue
        existing = receipts.get(receipt["id"])
        if existing is not None and existing != receipt:
            raise ValueError(f"conflicting trusted receipts for comment {receipt['id']}")
        receipts[receipt["id"]] = receipt
    return [receipts[comment_id] for comment_id in sorted(receipts)]


def _replay_anchor(
    checkpoints: list[tuple[int, str | None, int]], receipts: list[dict[str, Any]]
) -> tuple[str | None, int, bool]:
    if not receipts:
        if not checkpoints:
            return None, 0, False
        _, claimant, through = max(checkpoints, key=lambda checkpoint: checkpoint[2])
        return claimant, through, True

    first_receipt_id = receipts[0]["id"]
    anchors = [checkpoint for checkpoint in checkpoints if checkpoint[2] < first_receipt_id]
    if not anchors:
        return None, 0, False
    _, claimant, through = max(anchors, key=lambda checkpoint: checkpoint[2])
    return claimant, through, True


def _is_maintainer(receipt: dict[str, Any]) -> bool:
    return receipt["association"] in MAINTAINER_ASSOCIATIONS


def reconcile(issue: dict[str, Any], comments: Iterable[Any]) -> dict[str, Any]:
    """Replay trusted receipts and reconcile the label projection."""
    all_comments = _flatten_comments(comments)
    receipts = _receipts(all_comments)
    claimant, through, trusted_state = _replay_anchor(_checkpoints(all_comments), receipts)
    message = "Claim state checked."
    release_authorized = trusted_state and claimant is None

    for receipt in receipts:
        if receipt["id"] <= through:
            continue
        command = receipt["command"]
        actor = receipt["actor"]
        through = receipt["id"]

        if command == "/claim":
            if not receipt["issue_open"]:
                message = "This issue is closed and cannot be claimed."
            elif not receipt["eligible"]:
                message = (
                    "This issue is not open for direct claiming. A maintainer can add "
                    "`help wanted` or `good first issue` when it is contribution-ready."
                )
            elif claimant:
                message = f"This issue is already claimed by @{claimant}."
            else:
                claimant = actor
                message = (
                    f"Claimed by @{actor}. Thanks for contributing! Please open a pull "
                    "request or share meaningful progress within seven days."
                )
            continue

        if claimant == actor or _is_maintainer(receipt):
            release_authorized = True
            if claimant:
                claimant = None
                message = f"Claim released by @{actor}. This issue is available again."
            else:
                message = "This issue is already available."
        elif claimant:
            message = f"Only @{claimant} or a maintainer can release this claim."
        else:
            message = "This issue is already available."

    labels = _label_names(issue)
    desired_claimed = claimant is not None
    marker_status = "active" if desired_claimed else "available"
    marker_claimant = claimant or "none"
    return {
        "action": "reconcile",
        "add_label": CLAIMED_LABEL if desired_claimed and CLAIMED_LABEL not in labels else "",
        "remove_label": (
            CLAIMED_LABEL
            if not desired_claimed and CLAIMED_LABEL in labels and release_authorized
            else ""
        ),
        "claimant": claimant,
        "through": through,
        "comment": (
            f"{message}\n\n"
            f"<!-- issue-claim-state status={marker_status} "
            f"claimant={marker_claimant} through={through} -->"
        ),
    }


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit_outputs(result: dict[str, Any], output_path: str, comment_path: str) -> None:
    Path(comment_path).write_text(result["comment"], encoding="utf-8")
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"action={result['action']}\n")
        output.write(f"add_label={result['add_label']}\n")
        output.write(f"remove_label={result['remove_label']}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-json", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    parser.add_argument("--comment-file", required=True)
    args = parser.parse_args(argv)

    result = reconcile(_load(args.issue_json), _load(args.comments_json))
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.github_output:
        _emit_outputs(result, args.github_output, args.comment_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
