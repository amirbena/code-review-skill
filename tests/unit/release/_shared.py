"""Shared fixtures for the release-worthiness test submodules split out of
the former tests/unit/test_release_worthiness.py (issue #217): the fake
Git/GitHub runner and the two representative CHANGELOG.md fixtures.
"""

from __future__ import annotations

import subprocess
import sys

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import release_worthiness as rw  # noqa: E402


PLACEHOLDER_CHANGELOG = """\
# Changelog

## Unreleased

_Nothing yet. New entries land here and move under a version heading at
release time._

## v1.0.2 — 2026-08-29

### Changed

- Something shipped earlier.
"""


COVERED_CHANGELOG = """\
# Changelog

## Unreleased

### Changed

- Add release-worthiness automation (#104).

## v1.0.2 — 2026-08-29

- Something shipped earlier.
"""


VERSIONED_CHANGELOG = """\
# Changelog

## Unreleased

_Nothing yet._

## v1.0.3 — 2026-09-01

### Added

- Release-worthiness automation (#104).

### Changed

- Tightened packaging checks.

## v1.0.2 — 2026-08-29

- Something shipped earlier.
"""


def _unreleased(*body: str) -> str:
    return "# Changelog\n\n## Unreleased\n\n" + "\n".join(body) + "\n\n## v1.0.2 — 2026-08-29\n\n- old\n"


class _FakeGit:
    """Stand-in for rw.gitgh._git dispatching on the leading git args."""

    def __init__(
        self,
        *,
        describe: str = "v1.0.2\n",
        diff: str = "",
        tag_list: str = "",
        sorted_tags: str | None = None,
        ls_remote_tags: str = "",
        ls_remote_main: str = "",
        rev_parse: str | None = None,
        merge_base: str | None = None,
        log: str = "",
    ) -> None:
        self.describe = describe
        self.diff = diff
        self.merge_base = merge_base
        self.log = log
        self.tag_list = tag_list
        # `git tag --list --sort=-v:refname <glob>` output; defaults to the
        # exact-match tag_list when the test does not distinguish them.
        self.sorted_tags = tag_list if sorted_tags is None else sorted_tags
        self.ls_remote_tags = ls_remote_tags
        self.ls_remote_main = ls_remote_main
        self.rev_parse = rev_parse
        self.calls: list[list[str]] = []

    def __call__(self, args, repo_root):  # noqa: ANN001 - test shim
        a = list(args)
        self.calls.append(a)
        if a[:1] == ["log"]:
            return self.log
        if a[:1] == ["describe"]:
            return self.describe
        if a[:2] == ["diff", "--name-only"]:
            return self.diff
        if a[:2] == ["tag", "--list"]:
            if any(part.startswith("--sort") for part in a):
                return self.sorted_tags
            pattern = a[-1]
            names = [line.strip() for line in self.tag_list.splitlines() if line.strip()]
            return f"{pattern}\n" if pattern in names else ""
        if a[:1] == ["rev-parse"]:
            if self.rev_parse is None:
                raise subprocess.CalledProcessError(128, ["git", *a])
            return self.rev_parse
        if a[:1] == ["merge-base"]:
            if self.merge_base is None:
                raise subprocess.CalledProcessError(1, ["git", *a])
            return self.merge_base
        if a[:1] == ["ls-remote"]:
            return self.ls_remote_tags if "--tags" in a else self.ls_remote_main
        raise AssertionError(f"unexpected git call: {a}")
