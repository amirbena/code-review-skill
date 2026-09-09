"""``local-code-review`` specifics: the review-report template leads with a
human Result and keeps machine metadata in a trailing plain-Markdown
section (no HTML disclosure widget — that is github-pr-review-only), and
the opt-in / no-persistent-approval invariant appears in both the Skill
entrypoint and its runbook.
"""

from __future__ import annotations

from pathlib import Path

from ._support import check_markers
from .expectations import LOCAL_RUNBOOK_MARKERS, LOCAL_SKILL_MARKERS


def validate_local_policy_family(skill_root: Path) -> None:
    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    local_runbook = (skill_root / "runbooks" / "local-review.md").read_text(encoding="utf-8")
    local_report_template = (
        skill_root / "templates" / "local-review-report.md"
    ).read_text(encoding="utf-8")
    result_index = local_report_template.find("**Result:")
    metadata_index = local_report_template.find("### Review Metadata")
    if result_index < 0 or metadata_index < 0 or not (result_index < metadata_index):
        raise SystemExit(
            "error: local-review-report.md must lead with a human-facing Result "
            "and keep machine metadata subordinate inside a trailing "
            "'### Review Metadata' plain-Markdown section"
        )
    # The local report is plain Markdown — no HTML disclosure widget for
    # metadata (that is github-pr-review-only). Match the tag on its own
    # line, not the substring inside prose documenting this rule.
    if "\n<details>\n" in local_report_template.replace("\r\n", "\n"):
        raise SystemExit(
            "error: local-review-report.md must not render metadata as an "
            "HTML <details> block — that presentation is github-pr-review-"
            "specific; local-code-review must use plain Markdown"
        )
    check_markers(skill_text, LOCAL_SKILL_MARKERS, "local-code-review SKILL.md")
    check_markers(local_runbook, LOCAL_RUNBOOK_MARKERS, "local-code-review runbook")
