"""The modular ``github-pr-review`` policy layout: every sub-policy file's
required markers, the canonical index ordering in ``github-review.md``,
that the index does not restate an owned section, the active/passive
runbook step ordering around the self-review mutation boundary, and the
external review-summary template shape.
"""

from __future__ import annotations

from pathlib import Path

from ._support import check_absent, check_markers, check_order
from .expectations import (
    GITHUB_POLICY_MARKERS,
    GITHUB_POLICY_ORDER,
    GITHUB_POLICY_OWNED_HEADERS,
)


def validate_github_policy_family(skill_root: Path) -> None:
    policies_dir = skill_root / "policies"
    texts: dict[str, str] = {}
    for filename, markers in GITHUB_POLICY_MARKERS.items():
        path = policies_dir / filename
        if not path.is_file():
            raise SystemExit(f"error: required github-pr-review policy file missing: {path}")
        text = path.read_text(encoding="utf-8")
        texts[filename] = text
        check_markers(text, markers, str(path))

    index_text = texts["github-review.md"]
    check_order(index_text, GITHUB_POLICY_ORDER, "github-review.md canonical ordering")
    for filename, headers in GITHUB_POLICY_OWNED_HEADERS.items():
        check_absent(index_text, headers, "github-review.md")

    runbook = (skill_root / "runbooks" / "active-pr-review.md").read_text(encoding="utf-8")
    passive_runbook = (skill_root / "runbooks" / "passive-pr-review.md").read_text(encoding="utf-8")
    summary_template_path = skill_root / "templates" / "external-review-summary.md"
    if not summary_template_path.is_file():
        raise SystemExit(
            "error: github-pr-review package missing required runtime "
            f"template: {summary_template_path}"
        )
    summary_template = summary_template_path.read_text(encoding="utf-8")

    author_step = runbook.find("resolve authenticated identity, PR author, and controlling authority")
    self_review_step = runbook.find("self-review: analysis runs in full")
    ownership_step = runbook.find("check review ownership")
    access_step = runbook.find("verify repository/review access")
    scope_step = runbook.find("retrieve complete paginated PR scope")
    capability_step = runbook.find("determine event-specific review capability")
    dedupe_step = runbook.find("deduplicate same-HEAD findings")
    finalize_step = runbook.find("finalize findings and resolve inline eligibility")
    construct_step = runbook.find("construct one review: body + inline comments")
    decision_step = runbook.find("submit permitted Approve/Request Changes")
    if not (
        0 <= author_step < self_review_step < ownership_step < access_step < scope_step
        < capability_step < dedupe_step < finalize_step < construct_step < decision_step
    ):
        raise SystemExit(
            "error: active review flow must resolve the self-review mutation "
            "boundary (analysis still runs) before ownership, access, or scope; "
            "then establish complete scope and capability, then deduplicate and "
            "finalize findings, then construct one review before submitting a "
            "formal review decision"
        )
    passive_author_step = passive_runbook.find("resolve authenticated identity, PR author, and controlling authority")
    passive_self_review_step = passive_runbook.find("self-review: run the full analysis")
    passive_scope_step = passive_runbook.find("resolve changed files")
    if not (0 <= passive_author_step < passive_self_review_step < passive_scope_step):
        raise SystemExit(
            "error: passive review flow must resolve the self-review mutation "
            "boundary (analysis still runs) before retrieving PR scope"
        )

    # The self-review resolution must NOT terminate either flow: authorship
    # withholds the formal GitHub event, it does not skip analysis.
    for name, text in (("active", runbook), ("passive", passive_runbook)):
        if "REVIEW SKIPPED → stop" in text or "terminate\n   immediately with `REVIEW SKIPPED`" in text:
            raise SystemExit(
                f"error: {name} review flow must not terminate with REVIEW "
                "SKIPPED for a self-review — analysis runs and only the formal "
                "GitHub review event is withheld"
            )

    if "**Result:" not in summary_template:
        raise SystemExit(
            "error: external-review-summary.md must lead with a human-facing Result"
        )
    if "### Decision" not in summary_template:
        raise SystemExit(
            "error: external-review-summary.md must contain a Decision section"
        )
