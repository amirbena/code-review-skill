"""Handlers that finish a source release after its distribution is verified (#528).

* ``release-finalize`` — create, complete, or no-op the GitHub Release for
  the source tag from the build's archives. Runs only after
  ``distribution-verify`` succeeded. It never overwrites: an existing
  Release whose tag, target, or asset digests differ from the build fails
  closed with nothing changed.
* ``recover-release-tag`` — recovery for a release commit that reached
  ``main`` while its source tag push failed. The tags ruleset lets only the
  release App create tags, so this runs in the release App's job; it tags
  exactly that commit and never moves an existing tag.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from release_lib import gitgh
from release_lib.commands.release import build_digests, source_failures, validated_request
from release_lib.finalization import release_mismatches, release_subject


def _report(failures: list[str]) -> int:
    for failure in failures:
        print(f"::error::{failure}")
    return 1


def cmd_release_finalize(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    tag = f"v{args.version}"
    expected = args.expected_sha.strip()
    problem = validated_request(args.version, expected)
    if problem:
        return _report([problem])
    if not args.asset:
        return _report(["at least one --asset is required"])
    try:
        want = build_digests(args.asset)
    except OSError as exc:
        return _report([f"cannot read a build archive: {exc}"])

    failures = source_failures(repo_root, tag, expected, main_ancestor=True)
    if failures:
        return _report([*failures, "the source tag is not this release's; nothing was published"])

    try:
        release = gitgh.release_view(repo_root, tag)
        if release is None:
            gitgh._gh(
                ["release", "create", tag, "--verify-tag", "--title", tag, "--notes-file", args.notes_file,
                 *args.asset],
                repo_root,
            )
            outcome = "created"
        else:
            problems, missing = release_mismatches(release, tag, expected, want)
            if problems:
                return _report([*problems, f"GitHub Release {tag} does not match this build; nothing was changed"])
            outcome = "unchanged"
            if missing:
                paths = [path for path in args.asset if Path(path).name in missing]
                gitgh._gh(["release", "upload", tag, *paths], repo_root)
                outcome = "completed"
            if release.get("isDraft"):
                gitgh._gh(["release", "edit", tag, "--draft=false"], repo_root)
                outcome = "completed"
    except (subprocess.CalledProcessError, ValueError) as exc:
        detail = getattr(exc, "stderr", None) or exc
        return _report([f"GitHub Release {tag} could not be finalized: {detail}; re-run the recovery"])
    print(f"GitHub Release {tag}: {outcome}")
    return 0


def cmd_recover_release_tag(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    tag = f"v{args.version}"
    expected = args.expected_sha.strip()
    problem = validated_request(args.version, expected)
    if problem:
        return _report([problem])

    if gitgh.tag_exists(repo_root, tag):
        failures = source_failures(repo_root, tag, expected, main_ancestor=True)
        if failures:
            return _report([*failures, f"{tag} already exists elsewhere; it is never moved"])
        print(f"Source tag {tag}: unchanged")
        return 0

    try:
        subject = gitgh._git(["log", "-1", "--format=%s", expected], repo_root).strip()
    except subprocess.CalledProcessError:
        subject = ""
    if subject != release_subject(args.version):
        return _report([f"{expected} is not the release commit {release_subject(args.version)!r} (got {subject!r})"])

    try:
        gitgh._git(["fetch", "--quiet", "origin", "refs/heads/main"], repo_root)
        main_ok = gitgh.is_ancestor(repo_root, expected, "FETCH_HEAD")
    except subprocess.CalledProcessError as exc:
        return _report([f"could not fetch origin/main: {exc}"])
    if not main_ok:
        return _report([f"release commit {expected} is not in origin/main's history"])

    try:
        gitgh._git(["tag", "-a", tag, expected, "-m", f"Release {tag}"], repo_root)
        gitgh._git(["push", "origin", f"refs/tags/{tag}"], repo_root)
    except subprocess.CalledProcessError as exc:
        return _report([f"could not create source tag {tag}: {exc.stderr or exc}"])
    failures = source_failures(repo_root, tag, expected, main_ancestor=True)
    if failures:
        return _report(failures)
    print(f"Source tag {tag}: created at {expected}")
    return 0
