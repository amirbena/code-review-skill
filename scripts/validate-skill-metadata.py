#!/usr/bin/env python3
"""Validate Skill discovery metadata and declared package resources."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment prerequisite
    raise SystemExit("error: PyYAML is required for Skill metadata validation") from exc


RESOURCE_FIELDS = ("shared", "resources", "config")
PORTABLE_FRONTMATTER_FIELDS = {"name", "description"}
OPENAI_INTERFACE_FIELDS = {
    "display_name",
    "short_description",
    "default_prompt",
}

# A packaged Skill archive never contains this source repository's own
# development documentation (see AGENTS.md, "Runtime Neutrality" /
# ARCHITECTURE.md packaging boundary). Any packaged Markdown link whose
# target resolves to one of these basenames is, by construction, a
# reference that escapes the distributed package — regardless of how
# many "../" segments it takes to get there. This is deliberately
# depth-agnostic: it must catch "../AGENTS.md", "../../AGENTS.md",
# "../../../AGENTS.md", and any deeper form the same way.
REPO_ROOT_ONLY_DOC_BASENAMES = {"AGENTS.md", "ARCHITECTURE.md", "README.md"}
MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+)\)")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_prose(text: str) -> str:
    """Collapse whitespace runs (including newlines) to a single space.

    Required-marker checks that span more than a few words must not
    depend on exactly where the source Markdown happens to wrap a line —
    reflowing a sentence is not a semantic change. Comparing both the
    marker and the source text through this normalization makes such
    checks reflow-insensitive while still requiring the full wording to
    be present, so a real regression that actually removes or contradicts
    the required semantics still fails validation.
    """
    return WHITESPACE_RE.sub(" ", text).strip()


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise SystemExit(f"error: cannot parse YAML {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: expected a YAML mapping in {path}")
    return data


def load_frontmatter(skill_md: Path) -> dict:
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise SystemExit(f"error: {skill_md} must start with YAML frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise SystemExit(f"error: {skill_md} has no closing frontmatter delimiter") from exc
    try:
        data = yaml.safe_load("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f"error: cannot parse frontmatter in {skill_md}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: expected a frontmatter mapping in {skill_md}")
    return data


def iter_paths(value: object, field: str):
    if isinstance(value, str):
        yield field, value
    elif isinstance(value, list):
        for item in value:
            yield from iter_paths(item, field)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_paths(item, f"{field}.{key}")
    elif value is not None:
        raise SystemExit(f"error: metadata resource field {field} must contain paths")


def check_no_repo_root_doc_links(skill_root: Path) -> None:
    """Reject packaged Markdown links to this source repository's own
    root-level development documentation (AGENTS.md, ARCHITECTURE.md,
    README.md). A distributed Skill archive never contains these files,
    so any link to one — at any relative depth — is a packaging-boundary
    violation, not merely a broken link."""
    for md_file in sorted(skill_root.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for link in MARKDOWN_LINK_RE.findall(text):
            if link.startswith(("http://", "https://")):
                continue
            target = link.split("#", 1)[0].strip()
            if not target:
                continue
            basename = Path(target).name
            if basename in REPO_ROOT_ONLY_DOC_BASENAMES:
                raise SystemExit(
                    f"error: {md_file} contains a packaged link to "
                    f"repository-root {basename!r} ({link!r}); a distributed "
                    "Skill must be self-contained and must not depend on "
                    "source-repository documentation"
                )


def require_inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise SystemExit(f"error: {label} escapes root {root}: {path}") from exc
    return resolved


def validate(skill_root: Path, containment_root: Path) -> None:
    check_no_repo_root_doc_links(skill_root)

    skill_md = skill_root / "SKILL.md"
    metadata_path = skill_root / "metadata" / "skill.yaml"
    frontmatter = load_frontmatter(skill_md)
    metadata = load_yaml(metadata_path)

    unexpected_frontmatter = set(frontmatter) - PORTABLE_FRONTMATTER_FIELDS
    if unexpected_frontmatter:
        unexpected = ", ".join(sorted(unexpected_frontmatter))
        raise SystemExit(
            f"error: {skill_md} has non-portable frontmatter field(s): {unexpected}"
        )

    for field in ("name", "description"):
        if not frontmatter.get(field):
            raise SystemExit(f"error: {skill_md} frontmatter missing {field!r}")
        if metadata.get(field) != frontmatter[field]:
            raise SystemExit(
                f"error: {metadata_path} {field} does not exactly match SKILL.md frontmatter"
            )

    adapter_path = skill_root / "agents" / "openai.yaml"
    if adapter_path.exists():
        adapter = load_yaml(adapter_path)
        if set(adapter) != {"interface"}:
            raise SystemExit(
                f"error: {adapter_path} must contain only optional UI interface metadata"
            )
        interface = adapter.get("interface")
        if not isinstance(interface, dict) or set(interface) != OPENAI_INTERFACE_FIELDS:
            raise SystemExit(
                f"error: {adapter_path} interface must contain exactly "
                "display_name, short_description, and default_prompt"
            )
        for field in OPENAI_INTERFACE_FIELDS:
            if not isinstance(interface[field], str) or not interface[field]:
                raise SystemExit(
                    f"error: {adapter_path} interface.{field} must be a string"
                )
        short_description = interface["short_description"]
        if not 25 <= len(short_description) <= 64:
            raise SystemExit(
                f"error: {adapter_path} interface.short_description must be 25-64 characters"
            )
        if f"${frontmatter['name']}" not in interface["default_prompt"]:
            raise SystemExit(
                f"error: {adapter_path} interface.default_prompt must mention "
                f"${frontmatter['name']}"
            )

    entrypoint = metadata.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint:
        raise SystemExit(f"error: {metadata_path} missing string entrypoint")
    entrypoint_path = require_inside(skill_root / entrypoint, containment_root, "entrypoint")
    if not entrypoint_path.is_file():
        raise SystemExit(f"error: metadata entrypoint does not exist: {entrypoint_path}")

    for field in RESOURCE_FIELDS:
        if field not in metadata:
            continue
        for nested_field, declared in iter_paths(metadata[field], field):
            target = require_inside(metadata_path.parent / declared, containment_root, nested_field)
            if not target.exists():
                raise SystemExit(
                    f"error: metadata path {nested_field} does not exist: {declared}"
                )

    finding_template = (containment_root / "shared" / "templates" / "finding.md")
    if not finding_template.is_file():
        raise SystemExit("error: Skill package missing shared finding template")
    review_summary_template = (containment_root / "shared" / "templates" / "review-summary.md")
    if not review_summary_template.is_file():
        raise SystemExit("error: Skill package missing shared review-summary template")
    finding_text = finding_template.read_text(encoding="utf-8")
    for marker in (
        "**impact**",
        "## Finding quality contract",
        "## Canonical full rendering",
        "## Canonical summary-pointer rendering",
        "one authoritative full representation",
    ):
        if marker not in finding_text:
            raise SystemExit(f"error: shared finding template missing marker: {marker!r}")
    review_summary_text = review_summary_template.read_text(encoding="utf-8")
    for marker in (
        "**Result:",
        "### What changed",
        "### What was done well",
        "### Findings",
        "### Validation",
        "### Decision",
        "## Machine metadata is subordinate",
    ):
        if marker not in review_summary_text:
            raise SystemExit(
                f"error: shared review-summary template missing marker: {marker!r}"
            )

    reviewability = (containment_root / "shared" / "policies" / "file-reviewability.md")
    if not reviewability.is_file():
        raise SystemExit("error: Skill package missing shared file-reviewability policy")
    skill_text = skill_md.read_text(encoding="utf-8")
    if "file-reviewability.md" not in skill_text:
        raise SystemExit(f"error: {skill_md} does not reference file-reviewability policy")
    reviewability_text = reviewability.read_text(encoding="utf-8")
    for marker in (
        "generated status is never a blanket exemption",
        "## Vendored dependencies",
        "## Manifests and lockfiles",
        "## Minified files and bundles",
        "## Binary files",
        "opaque replacement is materially risky",
        "## Snapshots",
    ):
        if marker not in reviewability_text:
            raise SystemExit(f"error: file-reviewability policy missing marker: {marker!r}")

    if metadata.get("name") == "github-pr-review":
        policy = (skill_root / "policies" / "github-review.md").read_text(encoding="utf-8")
        runbook = (skill_root / "runbooks" / "active-pr-review.md").read_text(encoding="utf-8")
        passive_runbook = (skill_root / "runbooks" / "passive-pr-review.md").read_text(encoding="utf-8")
        # external-review-summary.md is a required runtime asset of the
        # bundled Skill (referenced by SKILL.md and both runbooks), not
        # merely repository documentation — check it explicitly, with a
        # clear packaging error, rather than let a missing file surface
        # as an unguarded FileNotFoundError.
        summary_template_path = skill_root / "templates" / "external-review-summary.md"
        if not summary_template_path.is_file():
            raise SystemExit(
                "error: github-pr-review package missing required runtime "
                f"template: {summary_template_path}"
            )
        summary_template = summary_template_path.read_text(encoding="utf-8")
        required_policy = (
            "## Self-review capability",
            "REVIEW SKIPPED",
            "Self-review is intentionally not performed.",
            "## Capability matrix",
            "## Complete PR scope and pagination",
            "same identity for the same PR and HEAD",
            "A changed HEAD starts a new authoritative review state",
            "at most 3,000 files",
            "REVIEW INCOMPLETE",
            "## Analysis phase vs. publication phase",
            "## Batched review construction and submission",
            "## Rejected inline location fallback",
            "## No duplicate findings",
            "MUST NOT publish a comment, or any part of a review, as each finding is discovered",
            "## Reviewer ownership and delta re-review",
            "Delta-only re-review is allowed only when the current reviewer owns "
            "the immediately preceding review context. A different reviewer must "
            "independently review the current PR state.",
            "Fail conservative",
            "previously reviewed SHA → current PR HEAD",
            "Never define this boundary merely as the latest commit, the last "
            "push, the last local commit, or \"commits since task start\"",
            "### Escalating from delta to full review",
            "does not inherit another reviewer's judgment",
            "NO NEW DELTA",
            "## Review reasoning flow",
            "PR intent → diff → logical cohorts → impacted dependency surface → findings",
            "resolve first, before this reasoning flow begins",
            "this reasoning flow applies to the reviewed delta and any "
            "surrounding context required to validate it",
            "## Logical Cohort Review",
            "group related changed files and hunks into logical cohorts when useful",
            "file-by-file review is not the primary reasoning model",
            "Do not label output `Cohort 1`, `Cohort 2`, etc. unless exposing "
            "the grouping materially improves the clarity of the review",
            "A small or single-purpose change needs only one cohort and no "
            "added ceremony",
            "## Code Impact / Dependency Analysis",
            "inspect relevant dependency paths beyond the raw diff",
            "no dedicated code-graph tool or vendor is required for this analysis",
            "### Impact exploration boundaries",
            "Stop exploring once the realistic blast radius is sufficiently "
            "understood to evaluate the correctness of the PR",
            "Do not recursively traverse dependencies merely because more "
            "references exist",
            "### Unchanged code as evidence, not automatic scope",
            "Unchanged code is an evidence source, not automatic scope expansion",
            "Do not report unrelated legacy problems merely because they were "
            "encountered while following dependencies",
            "### Findings still require concrete evidence",
            "Do not create a finding merely because another dependent file or "
            "symbol exists",
            "### Small and isolated changes",
            "trivial/single-purpose PRs are not forced into unnecessary "
            "cohort or graph-analysis ceremony",
        )
        # Compared through normalize_prose() rather than as raw substrings:
        # a marker's presence must not depend on exactly where the source
        # Markdown wraps a line. Ordinary reflow of policy prose is not a
        # semantic change and must not fail packaging; a marker that is
        # genuinely missing or altered in meaning still fails.
        policy_normalized = normalize_prose(policy)
        for marker in required_policy:
            if normalize_prose(marker) not in policy_normalized:
                raise SystemExit(f"error: GitHub review policy missing marker: {marker!r}")
        self_review_index = policy.find("## Self-review capability")
        reviewer_ownership_index = policy.find("## Reviewer ownership and delta re-review")
        if not (0 <= self_review_index < reviewer_ownership_index):
            raise SystemExit(
                "error: GitHub review policy must define the self-review guard "
                "before reviewer ownership and delta re-review, so the "
                "self-review guard remains authoritative and unbypassable by "
                "review-mode resolution"
            )
        cohort_index = policy.find("## Logical Cohort Review")
        impact_index = policy.find("## Code Impact / Dependency Analysis")
        if not (0 <= reviewer_ownership_index < cohort_index < impact_index):
            raise SystemExit(
                "error: GitHub review policy must define logical cohort review "
                "and code impact/dependency analysis after reviewer ownership "
                "and delta re-review, so review-mode resolution remains "
                "authoritative before this reasoning flow begins"
            )
        author_step = runbook.find("resolve authenticated identity and PR author")
        skip_step = runbook.find("REVIEW SKIPPED")
        ownership_step = runbook.find("check review ownership")
        access_step = runbook.find("verify repository/review access")
        scope_step = runbook.find("retrieve complete paginated PR scope")
        capability_step = runbook.find("determine event-specific review capability")
        dedupe_step = runbook.find("deduplicate same-HEAD findings")
        finalize_step = runbook.find("finalize findings and resolve inline eligibility")
        construct_step = runbook.find("construct one review: body + inline comments")
        decision_step = runbook.find("submit permitted Approve/Request Changes")
        if not (
            0 <= author_step < skip_step < ownership_step < access_step < scope_step
            < capability_step < dedupe_step < finalize_step < construct_step < decision_step
        ):
            raise SystemExit(
                "error: active review flow must resolve the self-review guard before "
                "ownership, access, or scope; then establish complete scope and "
                "capability, then deduplicate and finalize findings, then construct "
                "one review before submitting a formal review decision"
            )
        passive_author_step = passive_runbook.find("resolve authenticated identity and PR author")
        passive_skip_step = passive_runbook.find("REVIEW SKIPPED")
        passive_scope_step = passive_runbook.find("resolve changed files")
        if not (0 <= passive_author_step < passive_skip_step < passive_scope_step):
            raise SystemExit(
                "error: passive review flow must resolve the self-review guard before "
                "retrieving PR scope"
            )
        if "**Result:" not in summary_template:
            raise SystemExit(
                "error: external-review-summary.md must lead with a human-facing Result"
            )
        if "### Decision" not in summary_template:
            raise SystemExit(
                "error: external-review-summary.md must contain a Decision section"
            )

    if metadata.get("name") == "local-code-review":
        local_runbook = (skill_root / "runbooks" / "local-review.md").read_text(encoding="utf-8")
        local_report_template = (
            skill_root / "templates" / "local-review-report.md"
        ).read_text(encoding="utf-8")
        result_index = local_report_template.find("**Result:")
        details_index = local_report_template.find("<details>")
        if result_index < 0 or details_index < 0 or not (result_index < details_index):
            raise SystemExit(
                "error: local-review-report.md must lead with a human-facing Result "
                "and keep machine metadata subordinate inside a trailing <details> block"
            )
        required_skill_markers = (
            "MUST NOT be invoked automatically",
            "fresh, explicit user approval",
            "it does not ask for approval, does not track prior approvals",
            "is never, by itself, authorization for the caller to invoke this Skill again",
            "A separate, explicit approval is required for every subsequent invocation",
            "ask the user for approval to run",
        )
        # Compared through normalize_prose(), matching the github-pr-review
        # policy checks above: a marker's presence must not depend on
        # exactly where the source Markdown wraps a line.
        skill_text_normalized = normalize_prose(skill_text)
        for marker in required_skill_markers:
            if normalize_prose(marker) not in skill_text_normalized:
                raise SystemExit(
                    f"error: local-code-review SKILL.md missing marker: {marker!r}"
                )
        required_runbook_markers = (
            "Must not ask the user for approval",
            "must not be invoked as a self-triggered re-run",
            "This runbook does not verify that approval was obtained",
            "own separate, fresh, explicit user approval",
        )
        local_runbook_normalized = normalize_prose(local_runbook)
        for marker in required_runbook_markers:
            if normalize_prose(marker) not in local_runbook_normalized:
                raise SystemExit(
                    f"error: local-code-review runbook missing marker: {marker!r}"
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_root", type=Path)
    parser.add_argument("--containment-root", type=Path)
    args = parser.parse_args()
    root = args.skill_root.resolve()
    containment = (args.containment_root or root).resolve()
    validate(root, containment)


if __name__ == "__main__":
    main()
