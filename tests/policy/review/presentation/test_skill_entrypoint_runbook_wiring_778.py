"""Entrypoint wiring tests for #778: each Skill's SKILL.md must require
reading its runbook and must place conditional rendered-inspection
evaluation in its review flow. Prose assertions only; models no browser."""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _text

LOCAL = REPO_ROOT / "skills/local-code-review/SKILL.md"
GITHUB = REPO_ROOT / "skills/github-pr-review/SKILL.md"
POLICY_LINK = "shared/policies/rendered-inspection.md"


def _flow(path) -> str:
    raw = path.read_text(encoding="utf-8")
    match = re.search(r"## Review flow.*?```text\n(.*?)```", raw, re.S)
    assert match, f"no review-flow block in {path}"
    return re.sub(r"\s+", " ", match.group(1))


class EntrypointWiringTests(unittest.TestCase):
    def test_local_requires_runbook_read(self) -> None:
        text = _text(LOCAL)
        self.assertIn("Read [runbooks/local-review.md](runbooks/local-review.md) in full before starting any review", text)
        self.assertIn("required procedure, not optional background", text)

    def test_github_requires_runbook_read(self) -> None:
        text = _text(GITHUB)
        self.assertIn("Read the runbook for the resolved mode in full before starting any review", text)
        self.assertIn("required, not optional background", text)

    def test_flows_evaluate_rendered_inspection_after_runtime_validation(self) -> None:
        for path in (LOCAL, GITHUB):
            flow = _flow(path)
            self.assertIn("evaluate rendered inspection (conditional)", flow, path)
            self.assertLess(
                flow.index("runtime-validation"),
                flow.index("evaluate rendered inspection"),
                path,
            )

    def test_rendered_inspection_stays_conditional_and_linked(self) -> None:
        for path in (LOCAL, GITHUB):
            text = _text(path)
            self.assertIn(POLICY_LINK, text, path)
            self.assertIn(
                "stays silent (no prompt, no availability check, no browser) "
                "unless the change's UI-impact trigger fires",
                text,
                path,
            )

    def test_entrypoints_do_not_restate_trigger_or_consent_rules(self) -> None:
        for path in (LOCAL, GITHUB):
            text = _text(path)
            for forbidden in ("consent-declined", "session-scoped", "change classes"):
                self.assertNotIn(forbidden, text, (path, forbidden))


if __name__ == "__main__":
    unittest.main()
