"""Guard against silent drift between REPO_ROOT_ONLY_DOC_BASENAMES and its
documentation in policies/README.md. If this test breaks, update the
documented list to match the constant, or vice-versa."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.skill_metadata.expectations import REPO_ROOT_ONLY_DOC_BASENAMES
from tests.support.paths import REPO_ROOT

POLICIES_README = REPO_ROOT / "policies" / "README.md"
_SECTION_RE = re.compile(
    r"^## Prohibited repository-only dependencies\n(.*?)(?=\n## |\Z)",
    re.MULTILINE | re.DOTALL,
)
_BULLET_RE = re.compile(r"^- `(?!REPO_ROOT_ONLY_DOC_BASENAMES)(\S+)`", re.MULTILINE)


class ProhibitedRepositoryDocDriftTests(unittest.TestCase):
    def test_documented_basenames_match_the_constant(self) -> None:
        text = POLICIES_README.read_text(encoding="utf-8")
        match = _SECTION_RE.search(text)
        self.assertTrue(
            match, "policies/README.md must contain a '## Prohibited repository-only dependencies' section"
        )
        section = match.group(1)
        documented = {_BULLET_RE.match(line).group(1) for line in section.splitlines() if _BULLET_RE.match(line)}
        self.assertEqual(
            documented,
            REPO_ROOT_ONLY_DOC_BASENAMES,
            "policies/README.md documented list and REPO_ROOT_ONLY_DOC_BASENAMES are out of sync",
        )
