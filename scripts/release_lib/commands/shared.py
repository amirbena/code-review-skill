"""Shared path, GitHub-output, and step-summary helpers for release commands."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Sequence


def resolve_changelog(args: argparse.Namespace, repo_root: Path) -> Path:
    return Path(args.changelog) if args.changelog else repo_root / "CHANGELOG.md"


def emit_output(path: str | None, **pairs: str) -> None:
    target = path or os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        for key, value in pairs.items():
            handle.write(f"{key}={value}\n")


def fenced(lines: Sequence[str], info: str = "markdown") -> list[str]:
    """`lines` inside a code fence no backtick run in them can close early."""
    longest = max((len(run) for run in re.findall(r"`+", "\n".join(lines))), default=0)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}{info}", *lines, fence]


def write_step_summary(path: str | None, lines: Sequence[str]) -> None:
    """Append Markdown to an explicitly named step-summary file (never implied from env)."""
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
