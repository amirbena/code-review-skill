"""Pure comparisons over the text that ``git`` / ``gh`` commands print.

These functions take command *output*, not a repository — the workflow
runs the commands, this code decides whether the observed state matches
the release commit. Keeping the parsing here (side-effect-free) is what
lets release verification re-read live tag / branch / release state and
compare it, rather than trusting the exit codes of the steps that created
it.
"""

from __future__ import annotations

import re
from typing import Sequence

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def parse_ref_lines(text: str) -> dict[str, str]:
    """Parse `git ls-remote` output into {ref: sha}. Keeps peeled `^{}` refs."""
    refs: dict[str, str] = {}
    for line in text.splitlines():
        if "\t" not in line:
            continue
        sha, ref = line.split("\t", 1)
        refs[ref.strip()] = sha.strip()
    return refs


def resolved_tag_commit(ls_remote_text: str, version: str) -> str | None:
    """The commit a `v<version>` tag points at, dereferencing an annotated tag.

    Prefers the peeled `refs/tags/v<version>^{}` entry (annotated tag → commit);
    falls back to the bare ref (lightweight tag → commit).
    """
    refs = parse_ref_lines(ls_remote_text)
    return refs.get(f"refs/tags/v{version}^{{}}") or refs.get(f"refs/tags/v{version}")


def release_assets_present(release_json: dict, expected: Sequence[str]) -> bool:
    """True when every expected asset filename is attached to the release."""
    names = {asset.get("name") for asset in release_json.get("assets", [])}
    return set(expected).issubset(names)
