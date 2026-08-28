#!/usr/bin/env python3
"""Map Engineering Task issue-form fields to managed repository labels.

Parsing and mapping are pure and GitHub-free so they can be unit tested;
the workflow (.github/workflows/sync-issue-labels.yml) applies the result.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Iterable

# The automation owns exactly these label namespaces and nothing else.
MANAGED_PREFIXES = ("type:", "priority:", "area:")

TYPE_LABELS = {
    "Feature": "type:feature",
    "Refactor": "type:refactor",
    "Quality": "type:quality",
    "Research": "type:research",
    "Documentation": "type:documentation",
    "Infrastructure": "type:infrastructure",
}

# Keyed by a dash-normalized form value; the form emits an en/em dash that
# varies, so lookups normalize the same way before matching.
PRIORITY_LABELS = {
    "P1 - High": "priority:P1",
    "P2 - Medium": "priority:P2",
    "P3 - Low": "priority:P3",
}

AREA_LABELS = {
    "Review Quality": "area:review-quality",
    "Stateful Re-review": "area:stateful-re-review",
    "Platform Contracts": "area:platform-contracts",
    "Specialist Profiles": "area:specialist-profiles",
    "Risk / Large PR": "area:risk-large-pr",
    "GitHub Integration": "area:github-integration",
    "Packaging / Portability": "area:packaging-portability",
    "Documentation": "area:documentation",
    "Instruction Architecture": "area:instruction-architecture",
    "Research": "area:research",
}

MANAGED_FIELDS = ("Type", "Area", "Priority")
# U+2010..U+2015 (hyphen, figure/en/em dashes, horizontal bar) and U+2212 minus.
_DASH_RE = re.compile("[‐-―−]")
_NO_RESPONSE = "_No response_"


class UnknownFieldValue(ValueError):
    """A managed field held a value outside its allowlisted mapping."""

    def __init__(self, field: str, value: str) -> None:
        super().__init__(f"{field!r} has unmapped value {value!r}")
        self.field = field
        self.value = value


def _normalize_dashes(text: str) -> str:
    return _DASH_RE.sub("-", text)


def parse_issue_fields(body: str) -> dict[str, str]:
    """Return {field: value} for whichever of Type/Area/Priority are present.

    Only the known heading form produced by the issue form is read; prose is
    never guessed at. A field rendered as "_No response_" is treated as absent.
    """
    if not body:
        return {}
    text = body.replace("\r\n", "\n").replace("\r", "\n")
    found: dict[str, str] = {}
    for field in MANAGED_FIELDS:
        match = re.search(
            rf"^#{{1,6}}[ \t]+{re.escape(field)}[ \t]*$\n+(.+?)(?:\n[ \t]*\n|\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        if not match:
            continue
        value = match.group(1).strip()
        if value and value != _NO_RESPONSE:
            found[field] = value
    return found


def map_labels(fields: dict[str, str]) -> set[str]:
    """Resolve parsed fields to managed labels via the allowlisted mappings."""
    tables = {"Type": TYPE_LABELS, "Area": AREA_LABELS, "Priority": PRIORITY_LABELS}
    labels: set[str] = set()
    for field, table in tables.items():
        if field not in fields:
            continue
        raw = fields[field]
        key = _normalize_dashes(raw).strip() if field == "Priority" else raw
        if key not in table:
            raise UnknownFieldValue(field, raw)
        labels.add(table[key])
    return labels


def reconcile(current: Iterable[str], desired: set[str]) -> tuple[list[str], list[str]]:
    """Additions and removals confined to the managed namespaces.

    Unrelated labels are never touched, and an already-correct label set
    yields empty lists (idempotent).
    """
    current_set = set(current)
    add = sorted(desired - current_set)
    managed_current = {c for c in current_set if c.startswith(MANAGED_PREFIXES)}
    remove = sorted(managed_current - desired)
    return add, remove


def plan(body: str, current_labels: Iterable[str]) -> dict[str, object]:
    """Full decision: skip a non-form issue, error on malformed input, else apply."""
    fields = parse_issue_fields(body)
    if not fields:
        return {"action": "skip", "reason": "no Type/Area/Priority fields; not an Engineering Task issue body"}
    missing = [f for f in MANAGED_FIELDS if f not in fields]
    if missing:
        return {"action": "skip", "reason": f"incomplete managed fields, missing {', '.join(missing)}; not mutating"}
    try:
        desired = map_labels(fields)
    except UnknownFieldValue as exc:
        return {"action": "error", "reason": str(exc)}
    add, remove = reconcile(current_labels, desired)
    return {"action": "apply", "add": add, "remove": remove, "desired": sorted(desired)}


def _load_current_labels(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    return []


def _emit_github_output(result: dict[str, object], path: str) -> None:
    add = ",".join(result.get("add", []) or [])
    remove = ",".join(result.get("remove", []) or [])
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"action={result['action']}\n")
        handle.write(f"add={add}\n")
        handle.write(f"remove={remove}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-env", default="ISSUE_BODY", help="env var holding the issue body")
    parser.add_argument("--current-labels-env", default="CURRENT_LABELS", help="env var holding current labels (JSON array or CSV)")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"), help="path to write action/add/remove outputs")
    args = parser.parse_args(argv)

    body = os.environ.get(args.body_env, "")
    current_labels = _load_current_labels(os.environ.get(args.current_labels_env, ""))
    result = plan(body, current_labels)

    print(json.dumps(result, indent=2, sort_keys=True))
    if result["action"] == "apply":
        print(f"::notice::label sync add={result['add']} remove={result['remove']}")
    elif result["action"] == "skip":
        print(f"::notice::label sync skipped: {result['reason']}")
    else:
        print(f"::error::label sync failed: {result['reason']}")

    if args.github_output:
        _emit_github_output(result, args.github_output)

    return 1 if result["action"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
