"""Issue #788: the human renderings live in a conditionally loaded file.

`finding-rendering-human.md` is opened only when `human_review_output` /
`human_inline_findings` is in effect, fail-closed on ambiguity, before the
first decision it governs. The structured renderings stay unconditional.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _text

LOCAL = REPO_ROOT / "skills/local-code-review/SKILL.md"
GITHUB = REPO_ROOT / "skills/github-pr-review/SKILL.md"
STRUCTURED = REPO_ROOT / "shared/templates/finding-rendering.md"
HUMAN = REPO_ROOT / "shared/templates/finding-rendering-human.md"

HUMAN_HEADINGS = (
    "## Senior voice contract",
    "## Canonical human inline rendering",
    "## Canonical human full rendering",
)
STRUCTURED_HEADINGS = (
    "## Canonical full rendering",
    "## Canonical inline rendering",
    "## Canonical summary-pointer rendering",
    "## Rules",
)
PREDICATE = {
    LOCAL: "when `human_review_output` resolves `true` or its status is ambiguous",
    GITHUB: "when `human_review_output` or `human_inline_findings` resolves `true` or either status is ambiguous",
}
RETARGETED = (
    "shared/policies/invocation-options.md",
    "shared/templates/review-summary.md",
    "shared/templates/finding.md",
    "skills/github-pr-review/policies/finding-placement.md",
    "skills/github-pr-review/policies/review-output.md",
    "skills/github-pr-review/runbooks/active-pr-review.md",
    "skills/github-pr-review/runbooks/passive-pr-review.md",
    "skills/github-pr-review/templates/external-review-summary.md",
    "skills/github-pr-review/templates/inline-finding.md",
    "docs/features/human-review-output.md",
)
_LINK = re.compile(r"\]\((?:\.\./)+shared/templates/([\w-]+\.md)\)")


def _section(path, start: str, end: str) -> str:
    raw = path.read_text(encoding="utf-8")
    begin = raw.index(start)
    return raw[begin : raw.index(end, begin)]


class SplitShapeTests(unittest.TestCase):
    def test_each_file_owns_its_sections_once(self) -> None:
        structured = STRUCTURED.read_text(encoding="utf-8")
        human = HUMAN.read_text(encoding="utf-8")
        for heading in HUMAN_HEADINGS:
            self.assertIn(heading + "\n", human)
            self.assertNotIn(heading + "\n", structured)
        for heading in STRUCTURED_HEADINGS:
            self.assertIn(heading + "\n", structured)
            self.assertNotIn(heading + "\n", human)

    def test_no_link_to_the_structured_file_names_a_human_section(self) -> None:
        pattern = re.compile(
            r"finding-rendering\.md`?\]\([^)]*\)[\s,—-]*(?:in\s+)?\"?(?:Senior\s+voice|Canonical\s+human)"
        )
        for relative in RETARGETED:
            path = REPO_ROOT / relative
            self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), relative)


class ConditionalLoadingTests(unittest.TestCase):
    def test_human_file_is_not_in_the_unconditional_set(self) -> None:
        for path, start in ((LOCAL, "Always, in bounded resumable groups:"), (GITHUB, "Shared, always")):
            always = set(_LINK.findall(_section(path, start, "Conditionally")))
            self.assertIn("finding-rendering.md", always, path)
            self.assertNotIn("finding-rendering-human.md", always, path)

    def test_predicate_fires_stays_off_and_fails_closed(self) -> None:
        for path, predicate in PREDICATE.items():
            block = _section(path, "Conditionally, by review evidence", "Required material,")
            self.assertIn("finding-rendering-human.md", set(_LINK.findall(block)), path)
            self.assertIn(predicate, block, path)  # fires (true) and ambiguous
            flat = re.sub(r"\s+", " ", block)
            self.assertIn("stays unopened", flat, path)  # does not fire
            self.assertIn("fail-closed", flat, path)
            self.assertIn("before the first decision it governs", flat, path)

    def test_a_fired_but_unloaded_file_is_incomplete(self) -> None:
        for path in (LOCAL, GITHUB):
            text = _text(path)
            self.assertIn("a fired conditional file included", text, path)
            self.assertIn("REVIEW INCOMPLETE", text, path)

    def test_structured_file_points_at_the_conditional_one(self) -> None:
        text = _text(STRUCTURED)
        self.assertIn("loaded only when human_review_output or human_inline_findings is in effect", text)


if __name__ == "__main__":
    unittest.main()
