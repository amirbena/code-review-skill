#!/usr/bin/env python3
"""Measure and enforce the useful-content length of a pull-request body."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

PR_BODY_HARD_LIMIT = 6_000

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def useful_content(body: str | None) -> str:
    """Return normalized Markdown content after removing HTML comments."""
    normalized = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    return _HTML_COMMENT_RE.sub("", normalized).strip()


def measure_body(body: str | None) -> int:
    """Count Unicode code points in normalized useful content."""
    return len(useful_content(body))


@dataclass(frozen=True)
class ValidationResult:
    measured: int
    limit: int

    @property
    def over_by(self) -> int:
        return max(0, self.measured - self.limit)

    @property
    def passes(self) -> bool:
        return self.over_by == 0


def validate_body(body: str | None, limit: int = PR_BODY_HARD_LIMIT) -> ValidationResult:
    return ValidationResult(measured=measure_body(body), limit=limit)


def body_from_event(path: Path) -> str | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict) or "body" not in pull_request:
        raise ValueError("event payload does not contain pull_request.body")
    body = pull_request["body"]
    if body is not None and not isinstance(body, str):
        raise ValueError("pull_request.body must be a string or null")
    return body


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enforce the PR body useful-content hard limit from a GitHub event payload."
    )
    parser.add_argument("--event-path", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        body = body_from_event(args.event_path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"::error title=Cannot validate PR description::{error}")
        return 2

    result = validate_body(body)
    if result.passes:
        print(
            "PR description useful-content length is "
            f"{result.measured:,} code points; hard limit is {result.limit:,}."
        )
        return 0

    print(
        "::error title=PR description exceeds hard limit::"
        f"Measured {result.measured:,} useful-content code points; "
        f"hard limit is {result.limit:,}; {result.over_by:,} over. "
        "Summarize the change and link to canonical Issues, docs, policies, or "
        "runbooks instead of duplicating detailed requirements or semantics."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
