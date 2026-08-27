#!/usr/bin/env python3
"""Test-only PR simulation harness.

Two independent, test-only fixtures, neither packaged:
- simulated_pr(): a real-git origin+clone topology so pr_checkout.py can run
  against real git with no GitHub;
- review_history(): in-memory prior-review-activity fixtures (submitted
  reviews and their state, inline comments, threads, resolved/unresolved
  state, comment authorship) for the reconciliation decision-table tests.
Not runtime logic, not packaged. No fake GitHub API — just plain dataclasses.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from tests.reference.pr_checkout import NormalizedPrSource

_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Sim Author",
    "GIT_AUTHOR_EMAIL": "author@example.invalid",
    "GIT_COMMITTER_NAME": "Sim Author",
    "GIT_COMMITTER_EMAIL": "author@example.invalid",
    "GIT_TERMINAL_PROMPT": "0",
}
_PR_NUMBER = 123
_BASE_BRANCH = "main"
_FEATURE_BRANCH = "feature/pr-test"


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={**os.environ, **_GIT_ENV},
        check=True,
    )
    return proc.stdout.strip()


def _commit(work: Path, rel: str, content: str, message: str) -> str:
    (work / rel).parent.mkdir(parents=True, exist_ok=True)
    (work / rel).write_text(content, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", message)
    return _git(work, "rev-parse", "HEAD")


@dataclass(frozen=True)
class SimulatedPr:
    """Everything a checkout/scope test needs about the simulated PR."""

    root: Path
    origin_url: str
    base_sha: str
    head_sha: str
    merge_base: str
    changed_files: tuple[str, ...]
    expected_diff_files: tuple[str, ...]
    pull_ref_published: bool

    def normalized_source(self, *, use_pull_ref: bool = True) -> NormalizedPrSource:
        return NormalizedPrSource(
            repo_url=self.origin_url,
            pr_number=_PR_NUMBER,
            base_ref=f"refs/heads/{_BASE_BRANCH}",
            base_sha=self.base_sha,
            head_ref=f"refs/heads/{_FEATURE_BRANCH}",
            head_sha=self.head_sha,
            pull_ref=(
                f"refs/pull/{_PR_NUMBER}/head"
                if (use_pull_ref and self.pull_ref_published)
                else None
            ),
        )


@contextlib.contextmanager
def simulated_pr(
    *,
    advance_base_after_branch: bool = False,
    publish_pull_ref: bool = True,
    parent: Optional[Path] = None,
) -> Iterator[SimulatedPr]:
    """Yield a SimulatedPr backed by real repos on disk, then remove everything.

    Topology:  origin.git (bare)  <-  author-work/  {main: A-B-C(-F), feature: D-E}
               reviewer-checkout/ is created by the code under test, elsewhere.
    """
    root = Path(tempfile.mkdtemp(prefix="pr-sim-", dir=str(parent) if parent else None))
    try:
        origin = root / "origin.git"
        _git(root, "init", "--bare", "-b", _BASE_BRANCH, str(origin))
        work = root / "author-work"
        _git(root, "clone", str(origin), str(work))
        _git(work, "config", "commit.gpgsign", "false")

        _commit(work, "README.md", "A\n", "A: init")
        _commit(work, "AGENTS.md", "Use repository error conventions.\n", "B: root instructions")
        _commit(work, "services/AGENTS.md", "Service tests stay beside service modules.\n", "B2: service instructions")
        _commit(work, "services/payments/AGENTS.md", "Payment handlers use PaymentError.\n", "B3: payments instructions")
        _commit(work, "services/search/AGENTS.md", "Search handlers use SearchError.\n", "B4: search instructions")
        _commit(work, "src/lib.py", "def area(r):\n    return 3.14 * r * r\n", "B5: add lib")
        base_sha = _commit(work, "docs/design.md", "# Design\nPI is a constant.\n", "C: docs")
        _git(work, "push", "origin", _BASE_BRANCH)

        _git(work, "checkout", "-b", _FEATURE_BRANCH)
        _commit(work, "src/lib.py",
                "import math\n\n\ndef area(r):\n    return math.pi * r * r\n", "D: use math.pi")
        _commit(work, "services/payments/src/handler.py",
                "def handle():\n    return 'paid'\n", "D2: add payment handler")
        head_sha = _commit(work, "tests/test_lib.py",
                           "from src.lib import area\n\n\ndef test_area():\n    assert area(0) == 0\n",
                           "E: add test")
        _git(work, "push", "origin", _FEATURE_BRANCH)

        if advance_base_after_branch:
            _git(work, "checkout", _BASE_BRANCH)
            _commit(work, "CHANGELOG.md", "unrelated main advance\n", "F: advance main")
            _git(work, "push", "origin", _BASE_BRANCH)
            _git(work, "checkout", _FEATURE_BRANCH)

        merge_base = _git(work, "merge-base", base_sha, head_sha)
        changed = tuple(
            line for line in _git(
                work, "diff", "--name-only", f"{merge_base}..{head_sha}"
            ).splitlines() if line
        )

        if publish_pull_ref:
            # A GitHub-style PR ref living inside the bare remote.
            _git(work, "push", "origin", f"{_FEATURE_BRANCH}:refs/pull/{_PR_NUMBER}/head")

        yield SimulatedPr(
            root=root,
            origin_url=str(origin),
            base_sha=base_sha,
            head_sha=head_sha,
            merge_base=merge_base,
            changed_files=changed,
            expected_diff_files=changed,
            pull_ref_published=publish_pull_ref,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def unreadable_source(parent: Optional[Path] = None) -> NormalizedPrSource:
    """A NormalizedPrSource pointing at a path that is not a repository —
    stands in for an auth/clone failure without needing credentials."""
    missing = Path(tempfile.mkdtemp(prefix="pr-sim-missing-", dir=str(parent) if parent else None))
    shutil.rmtree(missing, ignore_errors=True)
    return NormalizedPrSource(
        repo_url=str(missing / "origin.git"),
        pr_number=_PR_NUMBER,
        base_ref=f"refs/heads/{_BASE_BRANCH}",
        base_sha="0" * 40,
        head_ref=f"refs/heads/{_FEATURE_BRANCH}",
        head_sha="0" * 40,
    )


# --- In-memory prior-review-activity fixtures --------------------------
# Consumed by the Existing-Review-Evidence reconciliation tests. Plain
# dataclasses; no HTTP, no fake GitHub. Authorship strings match
# tests/reference/pr_review_evidence.AuthorType values.


@dataclass(frozen=True)
class SimReviewComment:
    path: str
    body: str
    author_type: str = "human_reviewer"
    resolves_thread: bool = False


@dataclass(frozen=True)
class SimReview:
    state: str  # APPROVED | CHANGES_REQUESTED | COMMENTED | DISMISSED
    body: str
    reviewed_sha: str
    author_type: str = "human_reviewer"


@dataclass(frozen=True)
class SimReviewThread:
    path: str
    is_resolved: bool
    comments: tuple[SimReviewComment, ...] = ()


@dataclass(frozen=True)
class SimIssueComment:
    body: str
    author_type: str = "human_reviewer"


@dataclass(frozen=True)
class SimReviewHistory:
    reviews: tuple[SimReview, ...] = ()
    threads: tuple[SimReviewThread, ...] = ()
    issue_comments: tuple[SimIssueComment, ...] = ()
    complete: bool = True  # False models a paginated collection not fully retrieved


def review_history(
    *,
    reviews: tuple[SimReview, ...] = (),
    threads: tuple[SimReviewThread, ...] = (),
    issue_comments: tuple[SimIssueComment, ...] = (),
    complete: bool = True,
) -> SimReviewHistory:
    return SimReviewHistory(tuple(reviews), tuple(threads), tuple(issue_comments), complete)
