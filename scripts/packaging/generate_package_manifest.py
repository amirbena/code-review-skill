#!/usr/bin/env python3
"""Generate `package-manifest.json` from the `capabilities/*/capability.yaml`
declarations (issue #405).

`capability.yaml`'s `files:` list is, per
`docs/capability-architecture/capability-manifest-schema.md`, the
authoritative statement of which shared-policy/template and
`skills/github-pr-review/*` files an *on-activation* capability owns.
`package-manifest.json` additionally carries files no capability manifest
yet owns — `SKILL.md`, `metadata/skill.yaml`, `agents/*.yaml`, runbooks,
and the `always`-resident policies that back `review-kernel`,
`capability-posture`, `review-router`, `review-context-core`, and
`finding-contract` — none of which has a `capability.yaml` yet (schema
doc, "Field: loads"). Those are declared here as `_CORE_*` entries.

This module does not choose the manifest's file *order* — this repo's
`package-manifest.json` order predates capability.yaml and does not
reduce to "core entries, then one contiguous block per capability" (for
example `publication-github`'s and `reviewer-assist`'s `skills/
github-pr-review/policies/*.md` entries interleave). Each section's
`_ORDER` tuple below is that existing, hand-curated presentation order.
What this module generates is the *membership* check: every path in an
`_ORDER` tuple must be exactly the core entries plus the current union of
every relevant capability's declared `files:` — so a `capability.yaml`
edit that isn't mirrored into the matching `_ORDER` tuple (or vice versa)
raises here, which is what makes CI fail on divergence
(`tests/integration/packaging/test_generated_package_manifest.py`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPABILITIES_DIR = REPO_ROOT / "capabilities"
MANIFEST_PATH = REPO_ROOT / "scripts" / "packaging" / "package-manifest.json"


class Entry(NamedTuple):
    source: str
    capability: str | None  # None means the entry is core (not yet capability-owned)


# Core shared files: not yet owned by any capability.yaml (the `always`-resident
# capabilities' manifests haven't been authored — see module docstring).
_CORE_SHARED = (
    "shared/policies/review-scope.md",
    "shared/policies/change-risk-signals.md",
    "shared/policies/review-stopping-criteria.md",
    "shared/policies/severity.md",
    "shared/policies/verdict-consistency.md",
    "shared/policies/evidence.md",
    "shared/policies/repository-instructions.md",
    "shared/policies/review-base-policy.md",
    "shared/policies/git-safety.md",
    "shared/policies/mutation-authority.md",
    "shared/policies/review-ownership.md",
    "shared/policies/file-reviewability.md",
    "shared/policies/review-context.md",
    "shared/policies/invocation-options.md",
    "shared/templates/finding-rendering.md",
    "shared/templates/review-summary.md",
    "LICENSE",
)

# The declared shared_files order (source == destination for every entry).
_SHARED_ORDER: tuple[Entry, ...] = (
    Entry("shared/policies/review-scope.md", None),
    Entry("shared/policies/change-risk-signals.md", None),
    Entry("shared/policies/repository-expansion.md", "scale"),
    Entry("shared/policies/large-pr-partitioning.md", "scale"),
    Entry("shared/policies/review-stopping-criteria.md", None),
    Entry("shared/policies/root-cause-consolidation.md", "conditional-passes"),
    Entry("shared/policies/affected-test-analysis.md", "conditional-passes"),
    Entry("shared/policies/null-absence-risk.md", "conditional-passes"),
    Entry("shared/policies/failure-retry-recovery.md", "conditional-passes"),
    Entry("shared/policies/architectural-placement.md", "conditional-passes"),
    Entry("shared/policies/api-contract-compatibility.md", "conditional-passes"),
    Entry("shared/policies/severity.md", None),
    Entry("shared/policies/verdict-consistency.md", None),
    Entry("shared/policies/evidence.md", None),
    Entry("shared/policies/repository-instructions.md", None),
    Entry("shared/policies/review-base-policy.md", None),
    Entry("shared/policies/runtime-validation.md", "runtime-execution"),
    Entry("shared/policies/trusted-host-execution.md", "runtime-execution"),
    Entry("shared/policies/git-safety.md", None),
    Entry("shared/policies/mutation-authority.md", None),
    Entry("shared/policies/review-ownership.md", None),
    Entry("shared/policies/file-reviewability.md", None),
    Entry("shared/policies/review-context.md", None),
    Entry("shared/policies/requirement-coverage.md", "context-resolution"),
    Entry("shared/policies/jira-context.md", "context-resolution"),
    Entry("shared/policies/review-evidence.md", "context-resolution"),
    Entry("shared/policies/parallel-review.md", "parallel-execution"),
    Entry("shared/policies/agent-delegation.md", "parallel-execution"),
    Entry("shared/policies/invocation-options.md", None),
    Entry("shared/policies/remediation-guidance.md", "remediation"),
    Entry("shared/policies/remediation-scope-boundary.md", "remediation"),
    Entry("shared/policies/specialist-depth.md", "specialist-depth"),
    Entry("shared/policies/security-deepening.md", "specialist-depth"),
    Entry("shared/policies/distributed-systems-deepening.md", "specialist-depth"),
    Entry("shared/policies/database-migration-deepening.md", "specialist-depth"),
    Entry("shared/policies/performance-deepening.md", "specialist-depth"),
    Entry("shared/templates/finding.md", "finding-placement-derivation"),
    Entry("shared/templates/finding-rendering.md", None),
    Entry("shared/templates/review-summary.md", None),
    Entry("LICENSE", None),
)

# Core local-code-review files: no capability.yaml owns any
# skills/local-code-review/* file yet.
_CORE_LOCAL = (
    "skills/local-code-review/SKILL.md",
    "skills/local-code-review/agents/openai.yaml",
    "skills/local-code-review/metadata/skill.yaml",
    "skills/local-code-review/policies/invocation-approval.md",
    "skills/local-code-review/policies/repository-state.md",
    "skills/local-code-review/policies/review-context.md",
    "skills/local-code-review/policies/pr-context.md",
    "skills/local-code-review/runbooks/local-review.md",
    "skills/local-code-review/templates/local-review-report.md",
)

_LOCAL_ORDER: tuple[Entry, ...] = tuple(Entry(source, None) for source in _CORE_LOCAL)

_CORE_GITHUB = (
    "skills/github-pr-review/SKILL.md",
    "skills/github-pr-review/agents/openai.yaml",
    "skills/github-pr-review/metadata/skill.yaml",
    "skills/github-pr-review/policies/github-review.md",
    "skills/github-pr-review/policies/pr-scope.md",
    "skills/github-pr-review/policies/review-context.md",
    "skills/github-pr-review/policies/review-evidence.md",
    "skills/github-pr-review/policies/review-reasoning.md",
    "skills/github-pr-review/policies/parallel-review.md",
    "skills/github-pr-review/runbooks/passive-pr-review.md",
    "skills/github-pr-review/runbooks/active-pr-review.md",
)

_GITHUB_ORDER: tuple[Entry, ...] = (
    Entry("skills/github-pr-review/SKILL.md", None),
    Entry("skills/github-pr-review/agents/openai.yaml", None),
    Entry("skills/github-pr-review/metadata/skill.yaml", None),
    Entry("skills/github-pr-review/policies/github-review.md", None),
    Entry("skills/github-pr-review/policies/review-authority.md", "authorization-github"),
    Entry("skills/github-pr-review/policies/review-action-authorization.md", "authorization-github"),
    Entry("skills/github-pr-review/policies/reviewer-delta-review.md", "stateful-review"),
    Entry("skills/github-pr-review/policies/stateful-delta-rereview.md", "stateful-review"),
    Entry("skills/github-pr-review/policies/stacked-pr-review.md", "stateful-review"),
    Entry("skills/github-pr-review/policies/pr-scope.md", None),
    Entry("skills/github-pr-review/policies/repository-checkout.md", "repository-checkout"),
    Entry("skills/github-pr-review/policies/review-context.md", None),
    Entry("skills/github-pr-review/policies/review-evidence.md", None),
    Entry("skills/github-pr-review/policies/review-reasoning.md", None),
    Entry("skills/github-pr-review/policies/parallel-review.md", None),
    Entry("skills/github-pr-review/policies/finding-placement.md", "finding-placement-derivation"),
    Entry("skills/github-pr-review/policies/review-output.md", "publication-github"),
    Entry("skills/github-pr-review/policies/reviewer-brief.md", "reviewer-assist"),
    Entry("skills/github-pr-review/policies/review-status-enforcement.md", "publication-github"),
    Entry("skills/github-pr-review/runbooks/passive-pr-review.md", None),
    Entry("skills/github-pr-review/runbooks/active-pr-review.md", None),
    Entry("skills/github-pr-review/templates/inline-finding.md", "publication-github"),
    Entry("skills/github-pr-review/templates/external-review-summary.md", "publication-github"),
    Entry("skills/github-pr-review/templates/reviewer-brief.md", "reviewer-assist"),
)


def _load_capability_manifests() -> dict[str, dict]:
    manifests: dict[str, dict] = {}
    for manifest_path in sorted(CAPABILITIES_DIR.glob("*/capability.yaml")):
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifests[manifest["capability"]] = manifest
    return manifests


def _load_capability_files() -> dict[str, list[str]]:
    return {
        capability: list(manifest["files"])
        for capability, manifest in _load_capability_manifests().items()
    }


def derive_adapter_subsets(
    capability_manifests: dict[str, dict] | None = None,
) -> dict[str, set[str]]:
    """Derive, per adapter, the capability-owned files (issue #407) that
    adapter's declared `capability.yaml` `adapters:` lists make it
    responsible for.

    A `skills/local-code-review/*` or `skills/github-pr-review/*` file is
    already adapter-scoped by its directory — deriving its adapter here
    (rather than trusting the directory) is what lets this raise the
    moment a capability's `adapters:` list omits the adapter its own
    files actually require. A `shared/*` file is attributed to every
    adapter listed in its owning capability's `adapters:`.
    """
    if capability_manifests is None:
        capability_manifests = _load_capability_manifests()
    subsets: dict[str, set[str]] = {"local": set(), "github": set()}
    for capability, manifest in capability_manifests.items():
        adapters = manifest["adapters"]
        for source in manifest["files"]:
            if source.startswith("skills/local-code-review/"):
                if "local" not in adapters:
                    raise ValueError(
                        f"capabilities/{capability}/capability.yaml owns "
                        f"{source!r} under skills/local-code-review/ but its "
                        f"adapters list {adapters!r} omits 'local'"
                    )
                subsets["local"].add(source)
            elif source.startswith("skills/github-pr-review/"):
                if "github" not in adapters:
                    raise ValueError(
                        f"capabilities/{capability}/capability.yaml owns "
                        f"{source!r} under skills/github-pr-review/ but its "
                        f"adapters list {adapters!r} omits 'github'"
                    )
                subsets["github"].add(source)
            elif source.startswith("shared/"):
                for adapter in adapters:
                    subsets[adapter].add(source)
            else:
                raise ValueError(f"unexpected capability file root: {source!r}")
    return subsets


def _resolve_section(
    order: tuple[Entry, ...],
    core: tuple[str, ...],
    capability_files: dict[str, list[str]],
    prefix: str,
) -> list[str]:
    """Validate `order` against `core` plus every capability's declared
    files under `prefix`, and return the ordered list of sources.

    Raises ValueError the moment a capability.yaml's declared files under
    this section's root diverge from what `order` expects — a file added
    to (or dropped from) a capability without updating the matching
    `_ORDER` tuple here, or a file claimed by more than one owner (two
    capabilities, or a capability and the core list) at once.
    """
    core_set = set(core)
    expected: set[str] = set(core_set)
    owning_capabilities: dict[str, list[str]] = {}
    for capability, files in capability_files.items():
        for source in files:
            if source.startswith(prefix):
                expected.add(source)
                owning_capabilities.setdefault(source, []).append(capability)

    for source, owners in owning_capabilities.items():
        if len(owners) > 1:
            raise ValueError(
                f"{source!r} is declared in more than one capability.yaml's "
                f"files list: {sorted(owners)}"
            )
        if source in core_set:
            raise ValueError(
                f"{source!r} is declared both in the core file list and in "
                f"capabilities/{owners[0]}/capability.yaml's files list — "
                "update the manifest order table to credit the capability, "
                "not core"
            )

    seen: set[str] = set()
    sources: list[str] = []
    for entry in order:
        if entry.source in seen:
            raise ValueError(f"duplicate entry in manifest order: {entry.source}")
        seen.add(entry.source)
        sources.append(entry.source)

        if entry.capability is None:
            if entry.source not in core_set:
                raise ValueError(
                    f"{entry.source!r} is declared core but is not in the core file list"
                )
            continue

        owned = capability_files.get(entry.capability)
        if owned is None:
            raise ValueError(
                f"{entry.source!r} claims capability {entry.capability!r}, "
                "but no such capabilities/*/capability.yaml exists"
            )
        if entry.source not in owned:
            raise ValueError(
                f"{entry.source!r} is not declared in "
                f"capabilities/{entry.capability}/capability.yaml's files list "
                "(capability.yaml and package-manifest.json have diverged)"
            )

    missing = expected - seen
    if missing:
        raise ValueError(
            "capability.yaml declares files not represented in the generated "
            f"manifest order for prefix {prefix!r}: {sorted(missing)}"
        )
    extra = seen - expected
    if extra:
        raise ValueError(
            f"manifest order for prefix {prefix!r} declares files no longer "
            f"owned by any capability or the core list: {sorted(extra)}"
        )

    return sources


def _skill_entries(sources: list[str], skill_root: str) -> list[dict[str, str]]:
    prefix = f"{skill_root}/"
    entries = []
    for source in sources:
        if not source.startswith(prefix):
            raise ValueError(f"{source!r} does not start with {prefix!r}")
        entries.append({"source": source, "destination": source[len(prefix):]})
    return entries


def build_manifest() -> dict:
    capability_files = _load_capability_files()

    shared_sources = _resolve_section(
        _SHARED_ORDER, _CORE_SHARED, capability_files, prefix="shared/"
    )
    # LICENSE lives outside shared/ but is core-only; already validated by
    # the exact-membership check in _resolve_section (it's part of _CORE_SHARED).
    shared_files = [{"source": s, "destination": s} for s in shared_sources]

    local_sources = _resolve_section(
        _LOCAL_ORDER,
        _CORE_LOCAL,
        capability_files,
        prefix="skills/local-code-review/",
    )
    github_sources = _resolve_section(
        _GITHUB_ORDER,
        _CORE_GITHUB,
        capability_files,
        prefix="skills/github-pr-review/",
    )

    return {
        "schema_version": 1,
        "shared_files": shared_files,
        "skills": {
            "local": {
                "name": "local-code-review",
                "archive": "local-code-review-skill.zip",
                "files": _skill_entries(local_sources, "skills/local-code-review"),
                "required_entries": ["SKILL.md", "LICENSE"],
            },
            "github": {
                "name": "github-pr-review",
                "archive": "github-pr-review-skill.zip",
                "files": _skill_entries(github_sources, "skills/github-pr-review"),
                "required_entries": [
                    "SKILL.md",
                    "LICENSE",
                    "templates/external-review-summary.md",
                ],
            },
        },
    }


def _render_file_entry(entry: dict[str, str]) -> str:
    return f'{{ "source": "{entry["source"]}", "destination": "{entry["destination"]}" }}'


def _render_file_list(entries: list[dict[str, str]], indent: str) -> str:
    lines = [_render_file_entry(entry) for entry in entries]
    joined = f",\n{indent}".join(lines)
    return f"{indent}{joined}"


def _render_required_entries(required_entries: list[str]) -> str:
    rendered = ", ".join(f'"{value}"' for value in required_entries)
    return f"[{rendered}]"


def render_manifest(manifest: dict) -> str:
    shared_block = _render_file_list(manifest["shared_files"], "    ")

    skill_blocks = []
    for key in ("local", "github"):
        skill = manifest["skills"][key]
        files_block = _render_file_list(skill["files"], "        ")
        required = _render_required_entries(skill["required_entries"])
        skill_blocks.append(
            f'    "{key}": {{\n'
            f'      "name": "{skill["name"]}",\n'
            f'      "archive": "{skill["archive"]}",\n'
            f'      "files": [\n{files_block}\n'
            f"      ],\n"
            f'      "required_entries": {required}\n'
            f"    }}"
        )
    skills_block = ",\n".join(skill_blocks)

    return (
        "{\n"
        f'  "schema_version": {manifest["schema_version"]},\n'
        f'  "shared_files": [\n{shared_block}\n'
        "  ],\n"
        '  "skills": {\n'
        f"{skills_block}\n"
        "  }\n"
        "}\n"
    )


def generate() -> str:
    return render_manifest(build_manifest())


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the generated manifest differs from the committed file",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the generated manifest to scripts/packaging/package-manifest.json",
    )
    args = parser.parse_args()

    rendered = generate()

    if args.write:
        MANIFEST_PATH.write_text(rendered, encoding="utf-8")
        return 0

    if args.check:
        current = MANIFEST_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print(
                f"error: {MANIFEST_PATH} is stale relative to capabilities/*/capability.yaml; "
                "run `python3 scripts/packaging/generate_package_manifest.py --write`"
            )
            return 1
        return 0

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
