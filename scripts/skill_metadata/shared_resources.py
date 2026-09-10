"""The packaged ``shared/`` runtime that both Skills depend on: the finding
and review-summary templates, and the file-reviewability policy the Skill
entrypoint must reference.
"""

from __future__ import annotations

from pathlib import Path

from ._support import check_markers
from .expectations import (
    FILE_REVIEWABILITY_MARKERS,
    SHARED_FINDING_MARKERS,
    SHARED_FINDING_RENDERING_MARKERS,
    SHARED_REVIEW_SUMMARY_MARKERS,
)


def check_shared_resources(skill_root: Path, containment_root: Path) -> None:
    finding_template = containment_root / "shared" / "templates" / "finding.md"
    if not finding_template.is_file():
        raise SystemExit("error: Skill package missing shared finding template")
    finding_rendering_template = (
        containment_root / "shared" / "templates" / "finding-rendering.md"
    )
    if not finding_rendering_template.is_file():
        raise SystemExit(
            "error: Skill package missing shared finding-rendering template"
        )
    review_summary_template = containment_root / "shared" / "templates" / "review-summary.md"
    if not review_summary_template.is_file():
        raise SystemExit("error: Skill package missing shared review-summary template")
    check_markers(
        finding_template.read_text(encoding="utf-8"),
        SHARED_FINDING_MARKERS,
        "shared finding template",
    )
    check_markers(
        finding_rendering_template.read_text(encoding="utf-8"),
        SHARED_FINDING_RENDERING_MARKERS,
        "shared finding-rendering template",
    )
    check_markers(
        review_summary_template.read_text(encoding="utf-8"),
        SHARED_REVIEW_SUMMARY_MARKERS,
        "shared review-summary template",
    )

    reviewability = containment_root / "shared" / "policies" / "file-reviewability.md"
    if not reviewability.is_file():
        raise SystemExit("error: Skill package missing shared file-reviewability policy")
    skill_md = skill_root / "SKILL.md"
    if "file-reviewability.md" not in skill_md.read_text(encoding="utf-8"):
        raise SystemExit(
            f"error: {skill_md} does not reference file-reviewability policy"
        )
    check_markers(
        reviewability.read_text(encoding="utf-8"),
        FILE_REVIEWABILITY_MARKERS,
        "file-reviewability policy",
    )
