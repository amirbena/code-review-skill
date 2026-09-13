"""Handlers for release preflight and published-release verification."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from release_lib import gitgh
from release_lib.changelog import unreleased_has_coverage
from release_lib.classification import classify_paths
from release_lib.commands.shared import resolve_changelog
from release_lib.remote_state import (
    _FULL_SHA_RE,
    parse_ref_lines,
    release_assets_present,
    resolved_tag_commit,
)
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


def cmd_release_verify(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    tag = f"v{args.version}"
    expected = args.expected_sha.strip()
    failures: list[str] = []

    try:
        validate_semver(args.version)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1
    if not _FULL_SHA_RE.match(expected):
        print(f"::error::--expected-sha must be a full 40-hex commit SHA, got {expected!r}")
        return 1

    try:
        local_commit = gitgh._git(["rev-parse", f"{tag}^{{commit}}"], repo_root).strip()
    except subprocess.CalledProcessError:
        local_commit = None
    if local_commit != expected:
        failures.append(f"local tag {tag} resolves to {local_commit or 'nothing'}, expected {expected}")

    remote_tags = gitgh._git(
        ["ls-remote", "--tags", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"], repo_root
    )
    remote_commit = resolved_tag_commit(remote_tags, args.version)
    if remote_commit != expected:
        failures.append(f"origin tag {tag} resolves to {remote_commit or 'nothing'}, expected {expected}")

    main_refs = parse_ref_lines(gitgh._git(["ls-remote", "origin", "refs/heads/main"], repo_root))
    main_commit = main_refs.get("refs/heads/main")
    if main_commit != expected:
        failures.append(f"origin/main is at {main_commit or 'nothing'}, expected {expected}")

    try:
        release_json = json.loads(
            gitgh._gh(["release", "view", tag, "--json", "tagName,targetCommitish,assets"], repo_root)
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        failures.append(f"could not read GitHub Release {tag}: {exc}")
        release_json = None

    if release_json is not None:
        if release_json.get("tagName") != tag:
            failures.append(f"GitHub Release tagName is {release_json.get('tagName')!r}, expected {tag}")
        target = str(release_json.get("targetCommitish", ""))
        if _FULL_SHA_RE.match(target) and target != expected:
            failures.append(f"GitHub Release target is {target}, expected {expected}")
        if not release_assets_present(release_json, args.asset):
            have = sorted(asset.get("name") for asset in release_json.get("assets", []))
            failures.append(f"GitHub Release assets {have} are missing one of {list(args.asset)}")

    if failures:
        for failure in failures:
            print(f"::error::{failure}")
        return 1
    print(
        f"Verified: {tag} → {expected}; origin/main → {expected}; "
        f"GitHub Release published with assets {list(args.asset)}"
    )
    return 0
