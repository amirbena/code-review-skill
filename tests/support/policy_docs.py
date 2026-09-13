"""Generic support for policy/runbook prose assertions.

Shared by the ``tests/policy/review/`` modules that assert on the literal
prose of a Markdown policy or runbook file (rather than executing any
production code) — see ``policies/skill-development-policy.md``, "Runbook
Design", for why those assertions deliberately have no second
implementation to diverge from.

This module holds two things:

- ``load_normalized_text`` / ``extract_section``: generic text-loading
  helpers, not coupled to any one policy.
- the small set of hub document paths (the shared review-scope/evidence
  contract, both Skills' entrypoints, and their always-loaded runbooks)
  that most policy-document tests need regardless of which extracted pass
  they cover. Paths specific to a single extracted policy (e.g. one
  domain-specific deepening pass) belong in the test module that owns
  that policy, not here.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.support.paths import REPO_ROOT

SHARED_DIR = REPO_ROOT / "shared"
LOCAL_SKILL_DIR = REPO_ROOT / "skills/local-code-review"
GITHUB_SKILL_DIR = REPO_ROOT / "skills/github-pr-review"

REVIEW_SCOPE = SHARED_DIR / "policies/review-scope.md"
EVIDENCE = SHARED_DIR / "policies/evidence.md"
LOCAL_SKILL_MD = LOCAL_SKILL_DIR / "SKILL.md"
LOCAL_RUNBOOK = LOCAL_SKILL_DIR / "runbooks/local-review.md"
GITHUB_SKILL_MD = GITHUB_SKILL_DIR / "SKILL.md"
GITHUB_REASONING = GITHUB_SKILL_DIR / "policies/review-reasoning.md"
GITHUB_ACTIVE_RUNBOOK = GITHUB_SKILL_DIR / "runbooks/active-pr-review.md"
GITHUB_PASSIVE_RUNBOOK = GITHUB_SKILL_DIR / "runbooks/passive-pr-review.md"
GITHUB_REVIEW_INDEX = GITHUB_SKILL_DIR / "policies/github-review.md"
PARALLEL_REVIEW = SHARED_DIR / "policies/parallel-review.md"


def load_normalized_text(path: Path) -> str:
    """Read ``path`` and collapse Markdown emphasis/code markup and
    whitespace so substring assertions are robust to reflow and styling."""
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


def extract_section(text: str, heading: str, next_heading: str | None = None) -> str:
    """Return the slice of ``text`` from ``heading`` up to (but excluding)
    ``next_heading``, or to the end of ``text`` when ``next_heading`` is
    ``None``."""
    start = text.index(heading)
    if next_heading is None:
        return text[start:]
    return text[start : text.index(next_heading, start)]
