"""Handlers for generating, preparing, and reading changelog sections."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from release_lib import gitgh
from release_lib.changelog import extract_version_section, roll_unreleased
from release_lib.changelog_generation import ChangelogGenerationError, generate_changelog
from release_lib.commands.shared import resolve_changelog
from release_lib.semver_policy import AmbiguousReleaseImpact
from release_lib.semver_version import validate_semver

# Each problem above names its own fix — a missing/invalid PR description
# (edit the PR, then re-run via workflow_dispatch) or an unparseable commit
# subject on `main` (the commit itself needs correcting, not a PR
# description). This is a neutral pointer, not a one-size-fits-all fix.
INTENT_FIX_HINT = "See docs/RELEASE.md, 'The global changelog model', for how to resolve each problem above."


def cmd_generate_changelog(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = resolve_changelog(args, repo_root)
    baseline = args.base_ref or gitgh.latest_release_tag(repo_root)
    if not baseline:
        print("::error::no valid vX.Y.Z release tag to generate '## Unreleased' from")
        return 1
    text = changelog_path.read_text(encoding="utf-8")
    try:
        updated = generate_changelog(repo_root, baseline, text)
    except ChangelogGenerationError as exc:
        for problem in exc.problems:
            print(f"::error::{problem}")
        print(INTENT_FIX_HINT)
        return 1
    except AmbiguousReleaseImpact as exc:
        print(f"::error::{exc}")
        return 1
    if args.check:
        sys.stdout.write(updated)
        return 0
    changelog_path.write_text(updated, encoding="utf-8")
    print(f"Generated '## Unreleased' from merged pull requests since {baseline} in {changelog_path}")
    return 0


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
