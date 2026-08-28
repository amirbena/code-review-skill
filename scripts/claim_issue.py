#!/usr/bin/env python3
"""Reconcile issue claim state from trusted checkpoints and command comments."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

ELIGIBLE_LABELS = frozenset({"help wanted", "good first issue"})
CLAIMED_LABEL = "claimed"
MAINTAINER_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
BOT_LOGIN = "github-actions[bot]"
COMMANDS = frozenset({"/claim", "/unclaim"})
MARKER_RE = re.compile(
    r"<!-- issue-claim-state status=(active|available) "
    r"claimant=([A-Za-z0-9-]+|none) through=([0-9]+) -->"
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


def _checkpoint(comments: Iterable[Any]) -> tuple[str | None, int]:
    claimant: str | None = None
    through = 0
    for comment in sorted(_flatten_comments(comments), key=_comment_id):
        user = comment.get("user") or {}
        if user.get("login") != BOT_LOGIN or user.get("type") != "Bot":
            continue
        match = MARKER_RE.search(comment.get("body") or "")
        if not match:
            continue
        marker_through = int(match.group(3))
        if marker_through < through:
            continue
        claimant = match.group(2) if match.group(1) == "active" else None
        through = marker_through
    return claimant, through


def _command_comments(comments: Iterable[Any], through: int) -> list[dict[str, Any]]:
    return sorted(
        (
            comment
            for comment in _flatten_comments(comments)
            if _comment_id(comment) > through and comment.get("body") in COMMANDS
        ),
        key=_comment_id,
    )


def _is_maintainer(comment: dict[str, Any]) -> bool:
    return str(comment.get("author_association", "")).upper() in MAINTAINER_ASSOCIATIONS


def reconcile(issue: dict[str, Any], comments: Iterable[Any]) -> dict[str, Any]:
    """Replay uncheckpointed commands and reconcile the label projection."""
    all_comments = _flatten_comments(comments)
    claimant, through = _checkpoint(all_comments)
    message = "Claim state checked."

    for comment in _command_comments(all_comments, through):
        command = comment["body"]
        actor = str((comment.get("user") or {}).get("login", ""))
        through = _comment_id(comment)

        if command == "/claim":
            if issue.get("state") != "open":
                message = "This issue is closed and cannot be claimed."
            elif not _label_names(issue).intersection(ELIGIBLE_LABELS):
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

        if claimant == actor or _is_maintainer(comment):
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
        "remove_label": CLAIMED_LABEL if not desired_claimed and CLAIMED_LABEL in labels else "",
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
    parser.add_argument("--event-comment-id", required=True, type=int)
    parser.add_argument("--command", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--association", required=True)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    parser.add_argument("--comment-file", required=True)
    args = parser.parse_args(argv)

    comments = _flatten_comments(_load(args.comments_json))
    if not any(_comment_id(comment) == args.event_comment_id for comment in comments):
        comments.append(
            {
                "id": args.event_comment_id,
                "body": args.command,
                "user": {"login": args.actor, "type": "User"},
                "author_association": args.association,
            }
        )
    result = reconcile(_load(args.issue_json), comments)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.github_output:
        _emit_outputs(result, args.github_output, args.comment_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
