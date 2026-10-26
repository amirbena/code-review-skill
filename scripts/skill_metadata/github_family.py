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

    # The numbered Steps are the only execution order; the markers below are
    # phrases inside those Steps (the removed Flow diagrams are not consulted).
    active_steps = runbook.split("\n## Steps", 1)[-1]
    passive_steps = passive_runbook.split("\n## Steps", 1)[-1]
    markers = [
        active_steps.find("this invocation is a **self-review**"),
        active_steps.find("Check for an existing Code Review Agent owner"),
        active_steps.find("**Verify repository/review access**"),
        active_steps.find("retrieve the complete paginated changed-file set"),
        active_steps.find("Determine event-specific capability"),
        active_steps.find("**Finalize findings**"),
        active_steps.find("**Submit the one review**"),
    ]
    if not (0 <= markers[0] and markers == sorted(markers) and len(set(markers)) == len(markers)):
        raise SystemExit(
            "error: active review steps must resolve the self-review mutation "
            "boundary (analysis still runs) before ownership, access, or scope; "
            "then establish complete scope and capability, then finalize "
            "findings before submitting a formal review decision"
        )
    passive_self_review = passive_steps.find("this is a **self-review**")
    passive_scope = passive_steps.find("retrieve PR")
    if not (0 <= passive_self_review < passive_scope):
        raise SystemExit(
            "error: passive review steps must resolve the self-review mutation "
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
