"""The read-only Git/GitHub queries the release CLI depends on.

This module is the boundary between pure planning and the outside world:
everything above it (classification, changelog, SemVer) is
side-effect-free and unit-tested directly; the actual repository-mutating
commands (push, tag, ``gh release create``) live in the workflow, not
here. Tests replace ``_git`` / ``_gh`` on this module with a fake runner.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from release_lib.semver_version import _VERSION_RE


def _git(args: Sequence[str], repo_root: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return result.stdout


def _gh(args: Sequence[str], repo_root: Path) -> str:
    result = subprocess.run(
        ["gh", *args], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return result.stdout


def previous_release_tag(repo_root: Path) -> str | None:
    try:
        out = _git(["describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"], repo_root)
    except subprocess.CalledProcessError:
        return None
    tag = out.strip()
    return tag or None


def latest_release_tag(repo_root: Path) -> str | None:
    """Highest `vMAJOR.MINOR.PATCH` tag by version order, not commit topology.

    This is the version baseline for automatic releases: the accumulated
    release set is everything since this tag, and the next version is
    derived from it.
    """
    try:
        out = _git(
            ["tag", "--list", "--sort=-v:refname", "v[0-9]*.[0-9]*.[0-9]*"], repo_root
        )
    except subprocess.CalledProcessError:
        return None
    for line in out.splitlines():
        tag = line.strip()
        if tag.startswith("v") and _VERSION_RE.match(tag[1:]):
            return tag
    return None


def changed_files(repo_root: Path, base_ref: str | None) -> list[str]:
    """Repository-relative paths changed between `base_ref` (default: previous
    `v*` tag) and HEAD."""
    ref = base_ref or previous_release_tag(repo_root)
    if not ref:
        # No prior release to diff against: treat the whole tree as in scope.
        out = _git(["ls-files"], repo_root)
    else:
        out = _git(["diff", "--name-only", f"{ref}...HEAD"], repo_root)
    return [line for line in out.splitlines() if line.strip()]


def tag_exists(repo_root: Path, tag: str) -> bool:
    """True when `tag` exists locally or on `origin`."""
    local = {line.strip() for line in _git(["tag", "--list", tag], repo_root).splitlines() if line.strip()}
    if tag in local:
        return True
    try:
        remote = _git(["ls-remote", "--tags", "origin", f"refs/tags/{tag}"], repo_root)
    except subprocess.CalledProcessError:
        remote = ""
    return bool(remote.strip())
