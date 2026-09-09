"""Handlers for preparing and reading changelog sections."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from release_lib.changelog import extract_version_section, roll_unreleased
from release_lib.commands.shared import resolve_changelog
from release_lib.semver_version import validate_semver


def cmd_prepare_changelog(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = resolve_changelog(args, repo_root)
    today = args.date or dt.date.today().isoformat()
    text = changelog_path.read_text(encoding="utf-8")
    try:
        updated = roll_unreleased(text, args.version, today)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1
    if args.check:
        print(updated)
        return 0
    changelog_path.write_text(updated, encoding="utf-8")
    print(f"Rolled '## Unreleased' into '## v{args.version} — {today}' in {changelog_path}")
    return 0


def cmd_changelog_section(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = resolve_changelog(args, repo_root)
    try:
        validate_semver(args.version)
        section = extract_version_section(changelog_path.read_text(encoding="utf-8"), args.version)
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(section)
    return 0
