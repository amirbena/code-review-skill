#!/usr/bin/env python3
"""Validate Skill discovery metadata and declared package resources."""

from __future__ import annotations

import argparse
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


def require_inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise SystemExit(f"error: {label} escapes root {root}: {path}") from exc
    return resolved


def validate(skill_root: Path, containment_root: Path) -> None:
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
        required_policy = (
            "## Self-review capability",
            "REVIEW SKIPPED",
            "Self-review is intentionally not performed.",
            "## Capability matrix",
            "## Complete PR scope and pagination",
            "same identity for the same PR and HEAD",
            "A changed HEAD starts a new authoritative review state",
            "at\nmost 3,000 files",
            "REVIEW INCOMPLETE",
        )
        for marker in required_policy:
            if marker not in policy:
                raise SystemExit(f"error: GitHub review policy missing marker: {marker!r}")
        author_step = runbook.find("resolve authenticated identity and PR author")
        skip_step = runbook.find("REVIEW SKIPPED")
        ownership_step = runbook.find("check review ownership")
        access_step = runbook.find("verify repository/review access")
        scope_step = runbook.find("retrieve complete paginated PR scope")
        capability_step = runbook.find("determine event-specific review capability")
        dedupe_step = runbook.find("deduplicate same-HEAD findings")
        decision_step = runbook.find("submit permitted Approve/Request Changes")
        if not (
            0 <= author_step < skip_step < ownership_step < access_step < scope_step
            < capability_step < dedupe_step < decision_step
        ):
            raise SystemExit(
                "error: active review flow must resolve the self-review guard before "
                "ownership, access, or scope; then establish complete scope and "
                "capability, then deduplicate before a formal review decision"
            )
        passive_author_step = passive_runbook.find("resolve authenticated identity and PR author")
        passive_skip_step = passive_runbook.find("REVIEW SKIPPED")
        passive_scope_step = passive_runbook.find("resolve changed files")
        if not (0 <= passive_author_step < passive_skip_step < passive_scope_step):
            raise SystemExit(
                "error: passive review flow must resolve the self-review guard before "
                "retrieving PR scope"
            )

    if metadata.get("name") == "local-code-review":
        local_runbook = (skill_root / "runbooks" / "local-review.md").read_text(encoding="utf-8")
        required_skill_markers = (
            "MUST NOT be invoked automatically",
            "fresh, explicit user approval",
            "it does not ask for approval, does not track\nprior approvals",
            "is never, by\nitself, authorization for the caller to invoke this Skill again",
            "A separate, explicit approval is required for every\nsubsequent invocation",
            "ask the user for approval to run",
        )
        for marker in required_skill_markers:
            if marker not in skill_text:
                raise SystemExit(
                    f"error: local-code-review SKILL.md missing marker: {marker!r}"
                )
        required_runbook_markers = (
            "Must not ask the user for approval",
            "must not be invoked as a\n  self-triggered re-run",
            "This runbook does not\n  verify that approval was obtained",
            "own separate, fresh, explicit user approval",
        )
        for marker in required_runbook_markers:
            if marker not in local_runbook:
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
