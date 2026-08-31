#!/usr/bin/env python3
"""Reconcile issue claim state from trusted command receipts."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable

CLAIMED_LABEL = "claimed"
MAINTAINER_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
BOT_LOGIN = "github-actions[bot]"
DEFAULT_CHURN_THRESHOLD = 6
DEFAULT_CHURN_WINDOW_SECONDS = 10 * 60
DEFAULT_CLAIM_COOLDOWN_SECONDS = 30 * 60
MARKER_RE = re.compile(
    r"<!-- issue-claim-state status=(active|available) "
    r"claimant=([A-Za-z0-9-]+|none) through=([0-9]+) -->"
)
RECEIPT_RE = re.compile(
    r"<!-- issue-claim-command id=([0-9]+) command=(claim|unclaim) "
    r"actor=([A-Za-z0-9-]+) association=([A-Z_]+) "
    r"state=(open|closed) eligible=(true|false) -->"
)
TRANSITION_RE = re.compile(
    r"<!-- issue-claim-transition id=([0-9]+) actor=([A-Za-z0-9-]+) "
    r"command=(claim|unclaim) -->"
)
RESTRICTION_RE = re.compile(
    r"<!-- issue-claim-restriction actor=([A-Za-z0-9-]+) "
    r"until=([0-9]+) notified=(true|false) -->"
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


def _created_at(comment: dict[str, Any]) -> int:
    value = comment.get("created_at")
    if not value:
        return 0
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


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


def _repository_history(
    comments: Iterable[Any],
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    transitions: dict[int, dict[str, Any]] = {}
    restrictions: list[dict[str, Any]] = []
    seen: set[int] = set()
    for comment in _flatten_comments(comments):
        comment_id = _comment_id(comment)
        if comment_id in seen or not _trusted_bot_comment(comment):
            continue
        seen.add(comment_id)
        body = comment.get("body") or ""
        created_at = _created_at(comment)
        for match in TRANSITION_RE.finditer(body):
            transition_id = int(match.group(1))
            candidate = {
                "id": transition_id,
                "actor": match.group(2),
                "command": match.group(3),
                "at": created_at,
            }
            existing = transitions.get(transition_id)
            if existing is not None and (
                existing["actor"] != candidate["actor"]
                or existing["command"] != candidate["command"]
            ):
                raise ValueError(f"conflicting trusted transitions for command {transition_id}")
            if existing is None or candidate["at"] < existing["at"]:
                transitions[transition_id] = candidate
        for match in RESTRICTION_RE.finditer(body):
            restrictions.append(
                {
                    "actor": match.group(1),
                    "until": int(match.group(2)),
                    "notified": match.group(3) == "true",
                    "comment_id": comment_id,
                }
            )
    return transitions, restrictions


def _active_restriction(
    actor: str, restrictions: Iterable[dict[str, Any]], now: int
) -> dict[str, Any] | None:
    active = [
        item
        for item in restrictions
        if item["actor"] == actor and item["until"] > now
    ]
    return max(active, key=lambda item: (item["until"], item["comment_id"]), default=None)


def reconcile(
    issue: dict[str, Any],
    comments: Iterable[Any],
    repository_comments: Iterable[Any] = (),
    *,
    now: int | None = None,
    churn_threshold: int = DEFAULT_CHURN_THRESHOLD,
    churn_window_seconds: int = DEFAULT_CHURN_WINDOW_SECONDS,
    cooldown_seconds: int = DEFAULT_CLAIM_COOLDOWN_SECONDS,
) -> dict[str, Any]:
    """Replay trusted receipts and reconcile the label projection."""
    if churn_threshold < 1 or churn_window_seconds < 1 or cooldown_seconds < 1:
        raise ValueError("churn threshold, window, and cooldown must be positive")
    now = int(time.time()) if now is None else now
    all_comments = _flatten_comments(comments)
    receipts = _receipts(all_comments)
    claimant, through, trusted_state = _replay_anchor(_checkpoints(all_comments), receipts)
    transitions, restrictions = _repository_history(
        [*all_comments, *_flatten_comments(repository_comments)]
    )
    message = "Claim state checked."
    release_authorized = trusted_state and claimant is None
    new_transitions: list[tuple[int, str, str]] = []
    restriction: dict[str, Any] | None = None
    post_comment = True
    blocked_claim = False

    for receipt in receipts:
        if receipt["id"] <= through:
            continue
        command = receipt["command"]
        actor = receipt["actor"]
        through = receipt["id"]
        blocked_claim = False
        post_comment = True

        if command == "/claim":
            if active := _active_restriction(actor, restrictions, now):
                message = (
                    "Claiming is temporarily unavailable because of excessive recent "
                    "claim/unclaim activity. Please try again after the cooldown."
                )
                restriction = {**active, "notified": True}
                post_comment = not active["notified"]
                blocked_claim = True
            elif not receipt["issue_open"]:
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
                if receipt["id"] not in transitions:
                    new_transitions.append((receipt["id"], actor, "claim"))
                message = (
                    f"Claimed by @{actor}. Thanks for contributing! Please open a pull "
                    "request or share meaningful progress within seven days."
                )
            continue

        if claimant == actor or _is_maintainer(receipt):
            release_authorized = True
            if claimant:
                claimant = None
                if receipt["id"] not in transitions:
                    new_transitions.append((receipt["id"], actor, "unclaim"))
                message = f"Claim released by @{actor}. This issue is available again."
            else:
                message = "This issue is already available."
        elif claimant:
            message = f"Only @{claimant} or a maintainer can release this claim."
        else:
            message = "This issue is already available."

    for _, actor, _ in new_transitions:
        recent_count = sum(
            transition["actor"] == actor
            and transition["at"] >= now - churn_window_seconds
            for transition in transitions.values()
        )
        recent_count += sum(
            item_actor == actor for _, item_actor, _ in new_transitions
        )
        if recent_count >= churn_threshold and not _active_restriction(actor, restrictions, now):
            restriction = {
                "actor": actor,
                "until": now + cooldown_seconds,
                "notified": False,
                "comment_id": 0,
            }
            restrictions.append(restriction)
            message += (
                " Claiming is temporarily unavailable; please try again after the "
                "cooldown."
            )

    labels = _label_names(issue)
    desired_claimed = claimant is not None
    marker_status = "active" if desired_claimed else "available"
    marker_claimant = claimant or "none"
    markers = [
        f"<!-- issue-claim-transition id={transition_id} actor={actor} "
        f"command={command} -->"
        for transition_id, actor, command in new_transitions
    ]
    if restriction:
        markers.append(
            f"<!-- issue-claim-restriction actor={restriction['actor']} "
            f"until={restriction['until']} "
            f"notified={str(restriction['notified']).lower()} -->"
        )
    comment_parts = [
        message,
        (
            f"<!-- issue-claim-state status={marker_status} "
            f"claimant={marker_claimant} through={through} -->"
        ),
        *markers,
    ]
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
        "post_comment": post_comment,
        "persist_receipt": not blocked_claim,
        "comment": "\n\n".join(comment_parts),
    }


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit_outputs(result: dict[str, Any], output_path: str, comment_path: str) -> None:
    Path(comment_path).write_text(result["comment"], encoding="utf-8")
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"action={result['action']}\n")
        output.write(f"add_label={result['add_label']}\n")
        output.write(f"remove_label={result['remove_label']}\n")
        output.write(f"post_comment={str(result['post_comment']).lower()}\n")
        output.write(f"persist_receipt={str(result['persist_receipt']).lower()}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-json", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--repository-comments-json")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    parser.add_argument("--comment-file", required=True)
    parser.add_argument(
        "--churn-threshold", type=int, default=DEFAULT_CHURN_THRESHOLD
    )
    parser.add_argument(
        "--churn-window-seconds", type=int, default=DEFAULT_CHURN_WINDOW_SECONDS
    )
    parser.add_argument(
        "--cooldown-seconds", type=int, default=DEFAULT_CLAIM_COOLDOWN_SECONDS
    )
    parser.add_argument("--now", type=int)
    args = parser.parse_args(argv)

    repository_comments = (
        _load(args.repository_comments_json) if args.repository_comments_json else []
    )
    result = reconcile(
        _load(args.issue_json),
        _load(args.comments_json),
        repository_comments,
        now=args.now,
        churn_threshold=args.churn_threshold,
        churn_window_seconds=args.churn_window_seconds,
        cooldown_seconds=args.cooldown_seconds,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.github_output:
        _emit_outputs(result, args.github_output, args.comment_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
