#!/usr/bin/env python3
"""Plan safe issue claim and release actions from GitHub event state."""

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
MARKER_RE = re.compile(
    r"<!-- issue-claim:(active|released) claimant=([A-Za-z0-9-]+) -->"
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


def current_claimant(comments: Iterable[Any]) -> str | None:
    """Return the claimant from the latest trusted claim-state marker."""
    state: tuple[str, str] | None = None
    for comment in _flatten_comments(comments):
        user = comment.get("user") or {}
        if user.get("login") != BOT_LOGIN or user.get("type") != "Bot":
            continue
        match = MARKER_RE.search(comment.get("body") or "")
        if match:
            state = (match.group(1), match.group(2))
    if state and state[0] == "active":
        return state[1]
    return None


def _response(message: str, *, action: str = "comment") -> dict[str, Any]:
    return {"action": action, "comment": message}


def plan(
    *,
    command: str,
    actor: str,
    association: str,
    issue: dict[str, Any],
    comments: Iterable[Any],
) -> dict[str, Any]:
    """Return the mutation and response for one exact slash command."""
    normalized = command.strip()
    if normalized not in {"/claim", "/unclaim"}:
        return {"action": "ignore"}

    labels = _label_names(issue)
    claimant = current_claimant(comments)
    is_maintainer = association.upper() in MAINTAINER_ASSOCIATIONS

    if normalized == "/claim":
        if issue.get("state") != "open":
            return _response("This issue is closed and cannot be claimed.")
        if not labels.intersection(ELIGIBLE_LABELS):
            return _response(
                "This issue is not open for direct claiming. A maintainer can add "
                "`help wanted` or `good first issue` when it is contribution-ready."
            )
        if claimant:
            return _response(f"This issue is already claimed by @{claimant}.")
        if CLAIMED_LABEL in labels:
            return _response(
                "This issue is already marked `claimed`; a maintainer should verify "
                "the existing claim before releasing it."
            )
        return {
            "action": "claim",
            "add_label": CLAIMED_LABEL,
            "comment": (
                f"Claimed by @{actor}. Thanks for contributing! Please open a pull "
                "request or share meaningful progress within seven days.\n\n"
                f"<!-- issue-claim:active claimant={actor} -->"
            ),
        }

    if claimant == actor or is_maintainer:
        if not claimant and CLAIMED_LABEL not in labels:
            return _response("This issue is already available.")
        released_claimant = claimant or actor
        return {
            "action": "unclaim",
            "remove_label": CLAIMED_LABEL,
            "comment": (
                f"Claim released by @{actor}. This issue is available again.\n\n"
                f"<!-- issue-claim:released claimant={released_claimant} -->"
            ),
        }
    if claimant:
        return _response(
            f"Only @{claimant} or a maintainer can release this claim."
        )
    return _response("This issue is already available.")


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit_outputs(result: dict[str, Any], output_path: str, comment_path: str) -> None:
    Path(comment_path).write_text(result.get("comment", ""), encoding="utf-8")
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"action={result['action']}\n")
        output.write(f"add_label={result.get('add_label', '')}\n")
        output.write(f"remove_label={result.get('remove_label', '')}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-json", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--association", required=True)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    parser.add_argument("--comment-file", required=True)
    args = parser.parse_args(argv)

    result = plan(
        command=args.command,
        actor=args.actor,
        association=args.association,
        issue=_load(args.issue_json),
        comments=_load(args.comments_json),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.github_output:
        _emit_outputs(result, args.github_output, args.comment_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
