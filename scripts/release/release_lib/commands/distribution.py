"""Handlers for publishing and verifying the distribution tree (#509)."""

from __future__ import annotations

import argparse
from pathlib import Path

from release_lib import distribution
from release_lib.remote_state import _FULL_SHA_RE
from release_lib.semver_version import validate_semver


def _build(args: argparse.Namespace) -> distribution.Build:
    validate_semver(args.version)
    if not _FULL_SHA_RE.match(args.source_commit):
        raise distribution.DistributionError(
            f"--source-commit must be a full 40-hex SHA, got {args.source_commit!r}"
        )
    repo_root = Path(args.repo_root).resolve()
    dist = Path(args.dist)
    build = distribution.build_distribution(
        repo_root, dist, args.version, args.source_repository, args.source_commit
    )
    distribution.verify_zips(repo_root, dist, build)
    return build


def _run(args: argparse.Namespace, action) -> int:
    try:
        action(_build(args))
    except (distribution.DistributionError, ValueError, OSError) as exc:
        print(f"::error::{exc}")
        return 1
    return 0


def cmd_distribution_publish(args: argparse.Namespace) -> int:
    def act(build: distribution.Build) -> None:
        outcome = distribution.publish(
            build, args.remote, args.version, args.source_repository, (args.git_name, args.git_email)
        )
        print(f"distribution v{args.version}: {outcome} (content {build.content_hash()})")

    return _run(args, act)


def cmd_distribution_verify(args: argparse.Namespace) -> int:
    def act(build: distribution.Build) -> None:
        distribution.verify(build, args.remote, args.version, args.source_repository)
        print(f"Verified: distribution v{args.version} equals the build (content {build.content_hash()})")

    return _run(args, act)
