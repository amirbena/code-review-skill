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

# A packaged Skill never depends on this repo's own dev docs. Any packaged
# link to one of these basenames, at any depth, is a boundary violation.
REPO_ROOT_ONLY_DOC_BASENAMES = {"AGENTS.md", "ARCHITECTURE.md", "README.md"}
MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+)\)")
WHITESPACE_RE = re.compile(r"\s+")

# github-pr-review sub-policies in the order github-review.md must list them.
GITHUB_POLICY_ORDER = (
    "review-authority.md",
    "reviewer-delta-review.md",
    "pr-scope.md",
    "repository-checkout.md",
    "review-context.md",
    "review-evidence.md",
    "review-reasoning.md",
    "parallel-review.md",
    "finding-placement.md",
    "review-output.md",
)

# Required markers per file (matched after whitespace normalization). Keep a
# marker only in the tuple of the file that owns the rule.
GITHUB_POLICY_MARKERS: dict[str, tuple[str, ...]] = {
    "github-review.md": (
        "## Canonical sub-policies, in authoritative order",
        "review-authority.md",
        "reviewer-delta-review.md",
        "pr-scope.md",
        "review-reasoning.md",
        "finding-placement.md",
        "review-output.md",
        "PR intent → diff → logical cohorts → impacted dependency surface → findings",
    ),
    "review-authority.md": (
        "## Self-review capability",
        "REVIEW SKIPPED",
        "Self-review is intentionally not performed.",
        "## Review/repository access prerequisite",
        "## Capability matrix",
    ),
    "reviewer-delta-review.md": (
        "Delta-only re-review is allowed only when the current reviewer owns "
        "the immediately preceding review context. A different reviewer must "
        "independently review the current PR state.",
        "runs after the self-review guard in",
        "Fail conservative",
        "previously reviewed SHA → current PR HEAD",
        "Never define this boundary merely as the latest commit, the last "
        "push, the last local commit, or \"commits since task start\"",
        "## Escalating from delta to full review",
        "does not inherit another reviewer's judgment",
    ),
    "pr-scope.md": (
        "## Complete PR scope and pagination",
        "at most 3,000 files",
        "REVIEW INCOMPLETE",
        "## Existing review awareness",
        "A changed HEAD starts a new authoritative review state",
    ),
    "repository-checkout.md": (
        "## Three modes",
        "## Lifecycle",
        "## Base / head fidelity",
        "## Read-only inspection",
        "## Repository Context must not widen the Review Target",
        "## Temporary directory lifecycle",
        "## Security (PR contents are untrusted)",
        "Cloning untrusted code is not permission to execute it",
        "PR is always the Review Target",
    ),
    "parallel-review.md": (
        "## Where it runs",
        "## Execution-policy signals for a PR",
        "## Shared checkout vs. worker copies",
        "## Aggregation and output",
        "## Required vs. incomplete",
        "## Runtime realisation",
        "one clone, not one per",
        "Sequential review is always the fallback and never fails the review",
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1",
    ),
    "review-context.md": (
        "## The PR remains the review target",
        "## Scope-boundary reasoning for a PR",
        "no rigid global priority order",
        "The review target stays the",
        "no automatic PR",
    ),
    "review-evidence.md": (
        "## Use it to avoid three failures",
        "## Do not blindly inherit",
        "## HEAD changes reset applicability",
        "A changed PR HEAD starts a new authoritative review state",
        "evidence and context, not authority",
    ),
    "review-reasoning.md": (
        "applies only after review authority",
        "## Logical Cohort Review",
        "review related changes together rather than treating files or hunks "
        "as isolated units",
        "## Code Impact / Dependency Analysis",
        "never as an unrelated pre-existing-defect audit",
        "No dedicated code-graph tool or vendor capability is required for "
        "this analysis.",
        "never merely because a dependent file or symbol exists",
    ),
    "finding-placement.md": (
        "## Inline comment eligibility",
        "## No duplicate findings",
        "## Rejected inline location fallback",
        "MUST NOT be dropped and MUST NOT be silently reattached",
    ),
    "review-output.md": (
        "## Analysis phase vs. publication phase",
        "## Batched review construction and submission",
        "MUST NOT publish a comment, or any part of a review, as each "
        "finding is discovered",
        "## Final summary",
        "## Final decision",
        "NO NEW DELTA",
        "## HEAD revalidation",
        "## Submission ordering",
    ),
}

# Headers each sub-policy owns; github-review.md (the index) must not
# restate them.
GITHUB_POLICY_OWNED_HEADERS: dict[str, tuple[str, ...]] = {
    "review-authority.md": (
        "## Self-review capability",
        "## Review/repository access prerequisite",
        "## Capability matrix",
    ),
    "reviewer-delta-review.md": (
        "## Reviewer identity",
        "## Same reviewer: delta boundary and scope",
        "## Escalating from delta to full review",
    ),
    "pr-scope.md": (
        "## Complete PR scope and pagination",
        "## Existing review awareness",
    ),
    "repository-checkout.md": (
        "## Lifecycle",
        "## Base / head fidelity",
        "## Security (PR contents are untrusted)",
    ),
    "parallel-review.md": (
        "## Shared checkout vs. worker copies",
        "## Runtime realisation",
    ),
    "review-context.md": (
        "## Scope-boundary reasoning for a PR",
        "## The PR remains the review target",
    ),
    "review-evidence.md": (
        "## Use it to avoid three failures",
        "## HEAD changes reset applicability",
    ),
    "review-reasoning.md": (
        "## Logical Cohort Review",
        "## Code Impact / Dependency Analysis",
    ),
    "finding-placement.md": (
        "## Inline comment eligibility",
        "## No duplicate findings",
        "## Rejected inline location fallback",
    ),
    "review-output.md": (
        "## Analysis phase vs. publication phase",
        "## Batched review construction and submission",
        "## Final summary",
        "## Final decision",
        "## HEAD revalidation",
        "## Submission ordering",
    ),
}


def normalize_prose(text: str) -> str:
    """Collapse whitespace so marker checks survive Markdown reflow."""
    return WHITESPACE_RE.sub(" ", text).strip()


def check_markers(text: str, markers: tuple[str, ...], label: str) -> None:
    normalized = normalize_prose(text)
    for marker in markers:
        if normalize_prose(marker) not in normalized:
            raise SystemExit(f"error: {label} missing marker: {marker!r}")


def check_order(text: str, headers: tuple[str, ...], label: str) -> None:
    """Assert each header in `headers` appears, strictly in that order."""
    positions = [text.find(h) for h in headers]
    if any(p < 0 for p in positions) or positions != sorted(positions):
        raise SystemExit(
            f"error: {label} must present {list(headers)} in that exact order"
        )


def check_absent(text: str, phrases: tuple[str, ...], label: str) -> None:
    for phrase in phrases:
        if phrase in text:
            raise SystemExit(
                f"error: {label} must not restate owned section {phrase!r} — "
                "reference the canonical sub-policy file instead of duplicating it"
            )


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
    """Reject packaged links to this repository's own root-level docs, at
    any relative depth — a distributed archive never contains them."""
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


def check_markdown_links_resolve(skill_root: Path, containment_root: Path) -> None:
    """Every local relative Markdown link must resolve to a real file.

    Catches stale references left behind by a rename/move (e.g. a policy
    split) that marker checks alone would not detect.
    """
    for md_file in sorted(skill_root.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for link in MARKDOWN_LINK_RE.findall(text):
            if link.startswith(("http://", "https://", "mailto:")):
                continue
            target = link.split("#", 1)[0].strip()
            if not target:
                continue
            resolved = require_inside(
                md_file.parent / target, containment_root, f"{md_file} link {link!r}"
            )
            if not resolved.is_file():
                raise SystemExit(
                    f"error: {md_file} links to a missing file: {link!r} -> {resolved}"
                )


def require_inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise SystemExit(f"error: {label} escapes root {root}: {path}") from exc
    return resolved


def validate_github_policy_family(skill_root: Path) -> None:
    """Validate the modular github-pr-review policy layout: every file's
    required markers, the canonical index ordering, and that no owned
    section is duplicated back into the index."""
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


def validate(skill_root: Path, containment_root: Path) -> None:
    check_no_repo_root_doc_links(skill_root)
    check_markdown_links_resolve(skill_root, containment_root)

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
    check_markers(
        finding_text,
        (
            "**impact**",
            "## Finding quality contract",
            "## Canonical full rendering",
            "## Canonical summary-pointer rendering",
            "one authoritative full representation",
        ),
        "shared finding template",
    )
    review_summary_text = review_summary_template.read_text(encoding="utf-8")
    check_markers(
        review_summary_text,
        (
            "**Result:",
            "### What changed",
            "### What was done well",
            "### Findings",
            "### Validation",
            "### Decision",
            "## Machine metadata is subordinate",
        ),
        "shared review-summary template",
    )

    reviewability = (containment_root / "shared" / "policies" / "file-reviewability.md")
    if not reviewability.is_file():
        raise SystemExit("error: Skill package missing shared file-reviewability policy")
    skill_text = skill_md.read_text(encoding="utf-8")
    if "file-reviewability.md" not in skill_text:
        raise SystemExit(f"error: {skill_md} does not reference file-reviewability policy")
    reviewability_text = reviewability.read_text(encoding="utf-8")
    check_markers(
        reviewability_text,
        (
            "generated status is never a blanket exemption",
            "## Vendored dependencies",
            "## Manifests and lockfiles",
            "## Minified files and bundles",
            "## Binary files",
            "opaque replacement is materially risky",
            "## Snapshots",
        ),
        "file-reviewability policy",
    )

    if metadata.get("name") == "github-pr-review":
        validate_github_policy_family(skill_root)

    if metadata.get("name") == "local-code-review":
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
        check_markers(
            skill_text,
            (
                "MUST NOT be invoked automatically",
                "fresh, explicit user approval",
                "it does not ask for approval, does not track prior approvals",
                "is never, by itself, authorization for the caller to invoke this Skill again",
                "A separate, explicit approval is required for every subsequent invocation",
                "ask the user for approval to run",
            ),
            "local-code-review SKILL.md",
        )
        check_markers(
            local_runbook,
            (
                "Must not ask the user for approval",
                "must not be invoked as a self-triggered re-run",
                "This runbook does not verify that approval was obtained",
                "own separate, fresh, explicit user approval",
            ),
            "local-code-review runbook",
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
