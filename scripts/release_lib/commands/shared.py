"""Shared path and GitHub-output helpers for release commands."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def resolve_changelog(args: argparse.Namespace, repo_root: Path) -> Path:
    return Path(args.changelog) if args.changelog else repo_root / "CHANGELOG.md"


def emit_output(path: str | None, **pairs: str) -> None:
    target = path or os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        for key, value in pairs.items():
            handle.write(f"{key}={value}\n")
