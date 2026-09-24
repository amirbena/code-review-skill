"""When a source release is official, and whether the latest one got there (#528).

A version becomes an official source GitHub Release only after its
distribution commit and tag are published and verified. The release
commit and the source tag come first — they are the provenance anchors the
distribution names — and the GitHub Release comes last. These helpers
decide, from observed Git/GitHub state, whether the latest version finished
that sequence, and compare an existing GitHub Release against the build so
finalization can create, complete, or no-op without ever overwriting.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from release_lib import gitgh
from release_lib.skill_version import skill_targets

# The first version the `distribute` job published (docs/RELEASE.md,
# "Authority boundary"). Earlier source releases were never distributed and
# are exempt from the finalization check.
FIRST_DISTRIBUTED_VERSION = "1.56.0"
DISTRIBUTION_REMOTE = "https://github.com/amirbena/code-review-skills"
RECOVERY_HINT = "run the 'Release publish' workflow via workflow_dispatch on main (docs/RELEASE.md, 'Recovery')"
_RELEASE_SUBJECT_RE = re.compile(r"^chore\(release\): v(\d+\.\d+\.\d+) \[skip ci\]$")


@dataclass(frozen=True)
class Unfinished:
    """The latest version stopped before finalization.

    ``stage`` is ``tag`` (release commit on main, source tag missing) or
    ``finalize`` (source tag exists; distribution tag or GitHub Release missing).
    """

    stage: str
    version: str
    sha: str
    detail: str


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def requires_finalization(version: str) -> bool:
    return _key(version) >= _key(FIRST_DISTRIBUTED_VERSION)


def release_subject(version: str) -> str:
    return f"chore(release): v{version} [skip ci]"


def pending_release_commit(commits: Sequence[tuple[str, str]], baseline_version: str) -> tuple[str, str] | None:
    """``(version, sha)`` of a release commit newer than the baseline tag, if one landed untagged."""
    for sha, subject in commits:
        match = _RELEASE_SUBJECT_RE.match(subject)
        if match and _key(match.group(1)) > _key(baseline_version):
            return match.group(1), sha
    return None


def unfinished_release(repo_root: Path, baseline: str, distribution_remote: str) -> Unfinished | None:
    """Whether the latest version stopped short of an official, distributed release."""
    pending = pending_release_commit(gitgh.first_parent_commits(repo_root, baseline), baseline[1:])
    if pending:
        version, sha = pending
        return Unfinished(
            "tag", version, sha, f"release commit {sha[:12]} is on main but source tag v{version} does not exist"
        )
    version = baseline[1:]
    if not requires_finalization(version):
        return None
    sha = gitgh.rev_parse_commit(repo_root, baseline) or ""
    missing = []
    if gitgh.remote_tag_commit(repo_root, distribution_remote, baseline) is None:
        missing.append("distribution tag")
    release = gitgh.release_view(repo_root, baseline)
    names = {asset.get("name") for asset in (release or {}).get("assets", [])}
    expected = {archive for _, archive in skill_targets(repo_root)}
    if release is None or release.get("isDraft") or not expected <= names:
        missing.append("published GitHub Release with every Skill archive")
    if not missing:
        return None
    return Unfinished("finalize", version, sha, f"{baseline} has no {' and no '.join(missing)}")


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def release_mismatches(
    release: Mapping, tag: str, expected_sha: str, want: Mapping[str, str]
) -> tuple[list[str], list[str]]:
    """``(problems, missing)`` for an existing Release against the build's ``{name: digest}``.

    Any problem means the Release is not this build's and must not be
    touched; ``missing`` names assets a partial create left out, which may
    be uploaded to complete it.
    """
    problems: list[str] = []
    if release.get("tagName") != tag:
        problems.append(f"GitHub Release tag is {release.get('tagName')!r}, expected {tag}")
    if release.get("isPrerelease"):
        problems.append(f"GitHub Release {tag} is a prerelease")
    target = str(release.get("targetCommitish", ""))
    if re.fullmatch(r"[0-9a-f]{40}", target) and target != expected_sha:
        problems.append(f"GitHub Release target is {target}, expected {expected_sha}")
    have = {asset.get("name"): asset for asset in release.get("assets", [])}
    for name in sorted(set(have) - set(want)):
        problems.append(f"GitHub Release has unexpected asset {name}")
    missing = []
    for name, digest in sorted(want.items()):
        asset = have.get(name)
        if asset is None:
            missing.append(name)
        elif asset.get("state", "uploaded") != "uploaded":
            problems.append(f"GitHub Release asset {name} is in state {asset.get('state')!r}, not uploaded")
        elif asset.get("digest") != digest:
            problems.append(
                f"GitHub Release asset {name} has digest {asset.get('digest') or 'none'}, the build has {digest}"
            )
    return problems, missing
