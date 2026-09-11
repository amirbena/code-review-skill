"""Compose ``## Unreleased`` from the release intent of merged pull requests.

Runs only in the trusted ``plan`` / ``publish`` jobs on ``main``. Each
first-parent commit since the baseline tag that is release-worthy on its
own must be a merged PR — squash subject ``… (#N)`` whose GitHub merge
commit is that exact commit — carrying valid release intent; anything else
fails closed. Bullets a maintainer curated by hand under ``## Unreleased``
are kept, and a PR already referenced by one is not generated twice. The
result depends only on the commit list, the PR descriptions, and
CHANGELOG.md, so the same repository state always yields the same bytes.
Contract: docs/RELEASE.md.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from release_lib import gitgh
from release_lib.changelog import _BULLET_RE, _UNRELEASED_HEADING_RE, _unreleased_body
from release_lib.classification import classify_paths
from release_lib.release_intent import (
    CATEGORY_NAMES,
    CATEGORY_ORDER,
    NO_RELEASE,
    ReleaseIntentError,
    parse_release_intent,
    render_bullet,
)
from release_lib.semver_policy import AmbiguousReleaseImpact

_SUBSECTION_RE = re.compile(r"^###\s+(.+?)\s*$")
# Trailing punctuation (a maintainer's edit to the squash-merge title box,
# e.g. adding a period) must not defeat detection.
_SQUASH_REF_RE = re.compile(r"\(#(\d+)\)[.!?:;,]*\s*$")
_MERGE_REF_RE = re.compile(r"^Merge pull request #(\d+)\b")


class ChangelogGenerationError(ValueError):
    """One or more merged release-worthy changes have no usable release intent."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


@dataclass(frozen=True)
class GeneratedEntry:
    pr_number: int
    category: str
    bullet: str


def pr_number_from_subject(subject: str) -> int | None:
    match = _SQUASH_REF_RE.search(subject) or _MERGE_REF_RE.match(subject)
    return int(match.group(1)) if match else None


def collect_entries(repo_root: Path, baseline: str) -> list[GeneratedEntry]:
    """Generated entries for every release-worthy merged PR since `baseline`, oldest first."""
    entries: list[GeneratedEntry] = []
    problems: list[str] = []
    for sha, subject in gitgh.first_parent_commits(repo_root, baseline):
        if not classify_paths(gitgh.commit_paths(repo_root, sha)).release_worthy:
            continue
        number = pr_number_from_subject(subject)
        if number is None:
            # Not fixable by editing a PR description: the commit subject on
            # `main` itself does not name a merged pull request.
            problems.append(
                f"release-worthy commit {sha[:12]} has no '(#N)' pull request reference in its subject; "
                "the commit itself needs correcting, not any PR description"
            )
            continue
        try:
            pr = gitgh.pull_request(repo_root, number)
        except (subprocess.CalledProcessError, ValueError):
            problems.append(f"PR #{number}: could not be read from the GitHub API")
            continue
        if not pr.get("merged_at") or pr.get("merge_commit_sha") != sha:
            problems.append(f"PR #{number}: is not the merged pull request behind commit {sha[:12]}")
            continue
        try:
            intent = parse_release_intent(pr.get("body"))
        except ReleaseIntentError as exc:
            problems.append(f"PR #{number}: {exc}")
            continue
        if not intent.ships_entry:
            problems.append(f"PR #{number}: is release-worthy but declares 'Release category: none'")
            continue
        entries.append(GeneratedEntry(number, intent.category, render_bullet(intent, number)))
    if problems:
        raise ChangelogGenerationError(problems)
    return entries


def _curated_items(body: list[str]) -> dict[str, list[list[str]]]:
    """Hand-written `## Unreleased` bullets (with continuation lines) by canonical category."""
    sections: dict[str, list[list[str]]] = {}
    current: str | None = None
    item: list[str] | None = None
    blanks = 0
    for line in body:
        if not line.strip():
            blanks += 1
            continue
        heading = _SUBSECTION_RE.match(line)
        if heading:
            name = CATEGORY_NAMES.get(heading.group(1).strip().lower())
            if name is None or name == NO_RELEASE:
                raise AmbiguousReleaseImpact(
                    f"unrecognized '## Unreleased' category '### {heading.group(1).strip()}'"
                )
            current, item = name, None
            sections.setdefault(current, [])
        elif item is not None and (line[:1] in " \t" or blanks == 0):
            item.extend([""] * blanks)
            item.append(line.rstrip())
        elif _BULLET_RE.match(line):
            if current is None:
                raise AmbiguousReleaseImpact("'## Unreleased' has an entry outside any '### <Category>' heading")
            item = [line.rstrip()]
            sections[current].append(item)
        else:
            # Prose outside any bullet (e.g. the empty-section placeholder) is not an entry.
            item = None
        blanks = 0
    return sections


def compose_unreleased(changelog_text: str, entries: Sequence[GeneratedEntry]) -> str:
    """CHANGELOG.md with `entries` merged into `## Unreleased` under canonical headings."""
    body = _unreleased_body(changelog_text)
    if body is None:
        raise AmbiguousReleaseImpact("CHANGELOG.md has no '## Unreleased' section")
    sections = _curated_items(body)
    curated = "\n".join(line for items in sections.values() for item in items for line in item)
    for entry in entries:
        if f"(#{entry.pr_number})" not in curated:
            sections.setdefault(entry.category, []).append([entry.bullet])
    if not any(sections.values()):
        return changelog_text

    new_body = [""]
    for category in CATEGORY_ORDER:
        items = sections.get(category)
        if not items:
            continue
        new_body += [f"### {category}", ""]
        for item in items:
            new_body += item
        new_body.append("")

    lines = changelog_text.splitlines()
    heading_idx = next(i for i, line in enumerate(lines) if _UNRELEASED_HEADING_RE.match(line))
    body_end = heading_idx + 1 + len(body)
    text = "\n".join(lines[: heading_idx + 1] + new_body + lines[body_end:])
    if changelog_text.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text


def generate_changelog(repo_root: Path, baseline: str, changelog_text: str) -> str:
    """`compose_unreleased` over the entries collected since `baseline`."""
    return compose_unreleased(changelog_text, collect_entries(repo_root, baseline))
