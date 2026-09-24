"""Handlers for release preflight and source-tag / GitHub Release verification."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from release_lib import gitgh
from release_lib.changelog import unreleased_has_coverage
from release_lib.classification import classify_paths
from release_lib.commands.shared import resolve_changelog
from release_lib.finalization import file_digest, release_mismatches
from release_lib.remote_state import _FULL_SHA_RE, parse_ref_lines
from release_lib.semver_version import validate_semver


def cmd_release_preflight(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = resolve_changelog(args, repo_root)

    try:
        validate_semver(args.version)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1
    tag = f"v{args.version}"

    if gitgh.tag_exists(repo_root, tag):
        print(f"::error::tag {tag} already exists (locally or on origin); choose a new version")
        return 1

    paths = gitgh.changed_files(repo_root, args.base_ref)
    classification = classify_paths(paths)
    if not classification.release_worthy:
        print(
            "::error::no release-worthy changes since the previous tag "
            f"({gitgh.previous_release_tag(repo_root) or 'none'}); nothing to release"
        )
        return 1

    changelog_text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    if not unreleased_has_coverage(changelog_text):
        print("::error::'## Unreleased' has no release notes; add them before releasing")
        return 1

    print(f"Preflight OK: {tag} is new; {classification.reason}; '## Unreleased' has notes")
    return 0


def source_failures(repo_root: Path, tag: str, expected: str, *, main_ancestor: bool) -> list[str]:
    """Tag (local and origin) resolves to ``expected``; origin/main is, or descends from, it.

    Right after the release commit is pushed, main must be exactly that
    commit. Later stages (distribution, finalization, recovery) accept a
    main that has legitimately advanced, as long as the release commit is
    still in its history.
    """
    failures: list[str] = []
    local_commit = gitgh.rev_parse_commit(repo_root, tag)
    if local_commit != expected:
        failures.append(f"local tag {tag} resolves to {local_commit or 'nothing'}, expected {expected}")

    remote_commit = gitgh.remote_tag_commit(repo_root, "origin", tag)
    if remote_commit != expected:
        failures.append(f"origin tag {tag} resolves to {remote_commit or 'nothing'}, expected {expected}")

    main_refs = parse_ref_lines(gitgh._git(["ls-remote", "origin", "refs/heads/main"], repo_root))
    main_commit = main_refs.get("refs/heads/main")
    if not main_ancestor:
        if main_commit != expected:
            failures.append(f"origin/main is at {main_commit or 'nothing'}, expected {expected}")
    elif main_commit is None:
        failures.append("origin/main could not be read")
    else:
        try:
            gitgh._git(["fetch", "--quiet", "origin", "refs/heads/main"], repo_root)
        except subprocess.CalledProcessError as exc:
            failures.append(f"could not fetch origin/main: {exc}")
        else:
            if not gitgh.is_ancestor(repo_root, expected, main_commit):
                failures.append(f"release commit {expected} is not in origin/main's history ({main_commit})")
    return failures


def validated_request(version: str, expected: str) -> str | None:
    """An error message for a malformed version or SHA, else ``None``."""
    try:
        validate_semver(version)
    except ValueError as exc:
        return str(exc)
    if not _FULL_SHA_RE.match(expected):
        return f"--expected-sha must be a full 40-hex commit SHA, got {expected!r}"
    return None


def build_digests(paths: list[str]) -> dict[str, str]:
    """``{asset name: sha256 digest}`` for the build's archives (name = file name)."""
    return {Path(path).name: file_digest(Path(path)) for path in paths}


def cmd_release_verify(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    tag = f"v{args.version}"
    expected = args.expected_sha.strip()
    problem = validated_request(args.version, expected)
    if problem:
        print(f"::error::{problem}")
        return 1
    try:
        want = build_digests(args.asset)
    except OSError as exc:
        print(f"::error::cannot read a build archive: {exc}")
        return 1

    failures = source_failures(repo_root, tag, expected, main_ancestor=args.main_ancestor)
    if want:
        try:
            release = gitgh.release_view(repo_root, tag)
        except (subprocess.CalledProcessError, ValueError) as exc:
            failures.append(f"could not read GitHub Release {tag}: {exc}")
        else:
            if release is None:
                failures.append(f"GitHub Release {tag} does not exist")
            else:
                problems, missing = release_mismatches(release, tag, expected, want)
                failures.extend(problems)
                failures.extend(f"GitHub Release asset {name} is missing" for name in missing)
                if release.get("isDraft"):
                    failures.append(f"GitHub Release {tag} is still a draft")

    if failures:
        for failure in failures:
            print(f"::error::{failure}")
        return 1
    main = "contains" if args.main_ancestor else "is at"
    released = f"; GitHub Release carries exactly {sorted(want)} with matching digests" if want else ""
    print(f"Verified: {tag} → {expected}; origin/main {main} {expected}{released}")
    return 0
