"""Handlers for stamping and verifying the Skill frontmatter version."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from release_lib.semver_version import validate_semver
from release_lib.skill_version import stamp_skill_versions, verify_archive_versions


def cmd_stamp_skill_version(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    try:
        validate_semver(args.version)
        changed = stamp_skill_versions(repo_root, args.version)
    except (ValueError, OSError) as exc:
        print(f"::error::{exc}")
        return 1
    for path in changed:
        print(f"Stamped version {args.version} into {path.relative_to(repo_root)}")
    if not changed:
        print(f"Skill frontmatter versions already {args.version}")
    return 0


def cmd_verify_archive_versions(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    dist_dir = repo_root / args.dist
    try:
        validate_semver(args.version)
        problems = verify_archive_versions(repo_root, dist_dir, args.version)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"::error::{exc}")
        return 1
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        return 1
    print(f"Every Skill archive reports version {args.version}")
    return 0
