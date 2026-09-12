#!/usr/bin/env python3
"""Test-only reference for the benchmark fixture format (Issue #50).

Test-only: not runtime logic, not packaged — the packaged Skills are
Markdown/YAML only. This module mirrors
``docs/benchmark/fixture-format.md``: the ``benchmark-case/v1`` schema for a
single benchmark case, its required/optional fields, the four typed variance
constructs, and the fail-closed validation rules. It is a *parser and
validator*, not a matcher and not a runner — Issue #52 owns the real parser,
Issue #51 the corpus, Issue #41 scoring.

The contract is the *fields and rules*; this module is one executable
projection of them so a test can prove the worked example conforms and that
malformed cases are rejected rather than silently reinterpreted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------
# Schema identity. A validator implements a fixed set of major versions and
# refuses everything else — it never coerces an unknown version into a known
# one (fail-closed, docs/benchmark/fixture-format.md §3).
# --------------------------------------------------------------------------

SUPPORTED_FORMATS: frozenset[str] = frozenset({"benchmark-case/v1"})

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

SEVERITIES: frozenset[str] = frozenset({"P0", "P1", "P2"})
BLOCKING_SEVERITIES: frozenset[str] = frozenset({"P0", "P1"})

# Reused verbatim from docs/findings/finding-matching-strategy.md §2
# (the `location_intent` descriptor facet) so the benchmark does not invent
# a parallel location model.
LOCATION_INTENTS: frozenset[str] = frozenset(
    {"line", "symbol", "file", "cross-file", "repository"}
)

DECISIONS: frozenset[str] = frozenset({"clean", "changes-required"})
COMPLETENESS: frozenset[str] = frozenset({"exhaustive", "at-least"})
MATCH_KINDS: frozenset[str] = frozenset({"required", "optional"})

# `metadata` is a closed map: every key has a concrete downstream purpose.
METADATA_KEYS: frozenset[str] = frozenset({"source", "tags", "rationale"})
METADATA_TAGS: frozenset[str] = frozenset(
    {
        "correctness",
        "security",
        "quality",
        "no-op",
        "regression",
        "concurrency",
        "performance",
    }
)

_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {"format", "id", "title", "input", "expected", "metadata"}
)
_INPUT_KEYS: frozenset[str] = frozenset({"patch", "repo_ref", "base", "context"})
_REPO_REF_KEYS: frozenset[str] = frozenset({"repo", "pr", "commit", "base"})
_EXPECTED_KEYS: frozenset[str] = frozenset(
    {"decision", "findings", "findings_completeness"}
)
_FINDING_KEYS: frozenset[str] = frozenset(
    {"key", "severity", "location", "claim", "defect_kind", "match", "alternatives", "any_of"}
)
_ALT_KEYS: frozenset[str] = frozenset({"location", "claim", "defect_kind"})
_LOCATION_KEYS: frozenset[str] = frozenset(
    {"location_intent", "path", "symbol", "anchor", "lines"}
)


class FixtureFormatError(ValueError):
    """A fixture does not conform to the benchmark fixture format.

    Raised for every rejection reason in fixture-format.md §11 — an
    unsupported version, a missing/mistyped required field, an unknown key,
    or an out-of-contract structure. Callers never receive a partially
    accepted fixture.
    """


@dataclass(frozen=True)
class ExpectedFinding:
    key: str
    severities: tuple[str, ...]  # 1 value = exact; 2+ = permitted variance
    required: bool
    # Exactly one of (location/claim) or members is populated:
    location: dict[str, Any] | None = None
    claim: str | None = None
    defect_kind: str | None = None
    alternatives: tuple[dict[str, Any], ...] = ()
    members: tuple["ExpectedFinding", ...] = ()  # non-empty => an any_of group

    @property
    def is_any_of(self) -> bool:
        return bool(self.members)

    @property
    def can_block(self) -> bool:
        """True if satisfying this entry forces a blocking (P0/P1) severity.

        An ``any_of`` group can block only when *every* member can only be
        satisfied at a blocking severity; a single spec blocks when none of
        its permitted severities is P2.
        """
        if self.is_any_of:
            return all(m.can_block for m in self.members)
        return all(s in BLOCKING_SEVERITIES for s in self.severities)


@dataclass(frozen=True)
class BenchmarkCase:
    format: str
    id: str
    title: str
    input: dict[str, Any]
    decision: str | None
    findings_completeness: str
    findings: tuple[ExpectedFinding, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def input_kind(self) -> str:
        return "patch" if "patch" in self.input else "repo_ref"

    @property
    def derived_decision(self) -> str:
        """The mechanical decision for a fully-correct review of this case.

        Mirrors shared/policies/severity.md: any required finding that can
        only be satisfied at P0/P1 makes the decision ``changes-required``;
        otherwise ``clean``. Optional findings never move the decision.
        """
        for f in self.findings:
            if f.required and f.can_block:
                return "changes-required"
        return "clean"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureFormatError(message)


def _no_unknown_keys(mapping: dict[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    _require(not unknown, f"{where}: unknown key(s) {unknown}")


def _parse_severity(raw: Any, where: str) -> tuple[str, ...]:
    if isinstance(raw, str):
        _require(raw in SEVERITIES, f"{where}: severity {raw!r} is not one of P0/P1/P2")
        return (raw,)
    _require(
        isinstance(raw, list) and len(raw) >= 2,
        f"{where}: a severity list expresses permitted variance and needs >= 2 values",
    )
    _require(
        all(isinstance(s, str) and s in SEVERITIES for s in raw),
        f"{where}: severity list has a value outside P0/P1/P2",
    )
    _require(len(set(raw)) == len(raw), f"{where}: severity list has a duplicate")
    return tuple(raw)


def _parse_location(raw: Any, where: str) -> dict[str, Any]:
    _require(isinstance(raw, dict), f"{where}: location must be a mapping")
    _no_unknown_keys(raw, _LOCATION_KEYS, f"{where}.location")
    intent = raw.get("location_intent")
    _require(
        intent in LOCATION_INTENTS,
        f"{where}.location: location_intent {intent!r} is not one of {sorted(LOCATION_INTENTS)}",
    )
    if intent != "repository":
        path = raw.get("path")
        _require(
            isinstance(path, str) and path.strip() != "",
            f"{where}.location: 'path' is required unless location_intent is 'repository'",
        )
        _require(
            not path.startswith("/") and "\\" not in path,
            f"{where}.location: 'path' must be a repo-relative POSIX path",
        )
    lines = raw.get("lines")
    if lines is not None:
        _require(
            isinstance(lines, dict) and set(lines) == {"start", "end"},
            f"{where}.location.lines: must be a mapping with exactly 'start' and 'end'",
        )
        _require(
            isinstance(lines["start"], int)
            and isinstance(lines["end"], int)
            and 1 <= lines["start"] <= lines["end"],
            f"{where}.location.lines: start/end must be ints with 1 <= start <= end",
        )
    for opt in ("symbol", "anchor"):
        if opt in raw:
            _require(
                isinstance(raw[opt], str) and raw[opt].strip() != "",
                f"{where}.location: {opt!r} must be a non-empty string when present",
            )
    return raw


def _parse_alternative(raw: Any, where: str) -> dict[str, Any]:
    _require(isinstance(raw, dict), f"{where}: an alternative must be a mapping")
    _no_unknown_keys(raw, _ALT_KEYS, where)
    _require(
        bool(raw),
        f"{where}: an alternative must narrow at least one of location/claim/defect_kind",
    )
    if "location" in raw:
        _parse_location(raw["location"], where)
    if "claim" in raw:
        _require(
            isinstance(raw["claim"], str) and raw["claim"].strip() != "",
            f"{where}: alternative 'claim' must be a non-empty string",
        )
    if "defect_kind" in raw:
        # Same schema as a primary spec's defect_kind (fixture-format.md
        # §8.2 "same sub-schemas and validation as the primary").
        _require(
            isinstance(raw["defect_kind"], str) and bool(_SLUG_RE.match(raw["defect_kind"])),
            f"{where}: alternative 'defect_kind' must be a kebab-case slug",
        )
    return raw


def _parse_finding(raw: Any, where: str, *, nested: bool = False) -> ExpectedFinding:
    _require(isinstance(raw, dict), f"{where}: an expected finding must be a mapping")
    _no_unknown_keys(raw, _FINDING_KEYS, where)

    key = raw.get("key")
    _require(
        isinstance(key, str) and bool(_SLUG_RE.match(key or "")),
        f"{where}: 'key' must be a kebab-case slug",
    )
    where = f"{where}[{key}]"

    match_kind = raw.get("match", "required")
    _require(
        match_kind in MATCH_KINDS,
        f"{where}: 'match' must be 'required' or 'optional'",
    )
    # `match` governs the whole entry; an any_of member's optionality is
    # meaningless (the group is satisfied by exactly one member).
    _require(
        not (nested and "match" in raw),
        f"{where}: an 'any_of' member does not carry its own 'match'",
    )
    required = match_kind == "required"

    if "any_of" in raw:
        _require(not nested, f"{where}: 'any_of' groups do not nest")
        _require(
            "location" not in raw and "claim" not in raw and "severity" not in raw,
            f"{where}: an 'any_of' group carries its members, not its own location/claim/severity",
        )
        members_raw = raw["any_of"]
        _require(
            isinstance(members_raw, list) and len(members_raw) >= 2,
            f"{where}: an 'any_of' group needs >= 2 members",
        )
        members = tuple(
            _parse_finding(m, f"{where}.any_of", nested=True) for m in members_raw
        )
        member_keys = [m.key for m in members]
        _require(
            len(set(member_keys)) == len(member_keys),
            f"{where}: 'any_of' member keys must be unique",
        )
        return ExpectedFinding(key=key, severities=(), required=required, members=members)

    severities = _parse_severity(raw.get("severity"), where)
    _require("location" in raw, f"{where}: 'location' is required")
    location = _parse_location(raw["location"], where)
    claim = raw.get("claim")
    _require(
        isinstance(claim, str) and claim.strip() != "",
        f"{where}: 'claim' is required and must be a non-empty string",
    )
    if "defect_kind" in raw:
        _require(
            isinstance(raw["defect_kind"], str) and bool(_SLUG_RE.match(raw["defect_kind"])),
            f"{where}: 'defect_kind' must be a kebab-case slug when present",
        )
    alternatives = tuple(
        _parse_alternative(a, f"{where}.alternatives")
        for a in raw.get("alternatives", [])
    )
    if "alternatives" in raw:
        _require(
            isinstance(raw["alternatives"], list) and bool(raw["alternatives"]),
            f"{where}: 'alternatives' must be a non-empty list when present",
        )
    return ExpectedFinding(
        key=key,
        severities=severities,
        required=required,
        location=location,
        claim=claim,
        defect_kind=raw.get("defect_kind"),
        alternatives=alternatives,
    )


def _parse_input(raw: Any) -> dict[str, Any]:
    _require(isinstance(raw, dict), "input: must be a mapping")
    _no_unknown_keys(raw, _INPUT_KEYS, "input")
    has_patch = "patch" in raw
    has_ref = "repo_ref" in raw
    _require(
        has_patch != has_ref,
        "input: exactly one of 'patch' or 'repo_ref' must be present",
    )
    if has_patch:
        _require(
            isinstance(raw["patch"], str) and raw["patch"].strip() != "",
            "input.patch: must be a non-empty unified-diff string",
        )
        if "base" in raw:
            base = raw["base"]
            _require(
                isinstance(base, dict)
                and all(isinstance(k, str) and isinstance(v, str) for k, v in base.items()),
                "input.base: must be a mapping of repo-relative path -> file contents",
            )
    else:
        _require("base" not in raw, "input.base: only valid alongside 'patch'")
        ref = raw["repo_ref"]
        _require(isinstance(ref, dict), "input.repo_ref: must be a mapping")
        _no_unknown_keys(ref, _REPO_REF_KEYS, "input.repo_ref")
        _require(
            isinstance(ref.get("repo"), str) and "/" in ref.get("repo", ""),
            "input.repo_ref.repo: must be an 'owner/name' string",
        )
        _require(
            ("pr" in ref) != ("commit" in ref),
            "input.repo_ref: exactly one of 'pr' or 'commit' must be present",
        )
        if "pr" in ref:
            _require(
                isinstance(ref["pr"], int) and ref["pr"] > 0,
                "input.repo_ref.pr: must be a positive integer",
            )
        else:
            _require(
                isinstance(ref["commit"], str) and ref["commit"].strip() != "",
                "input.repo_ref.commit: must be a non-empty string",
            )
        if "base" in ref:
            _require(
                isinstance(ref["base"], str) and ref["base"].strip() != "",
                "input.repo_ref.base: must be a non-empty string when present",
            )
    if "context" in raw:
        _require(
            isinstance(raw["context"], str) and raw["context"].strip() != "",
            "input.context: must be a non-empty string when present",
        )
    return raw


def _parse_metadata(raw: Any) -> dict[str, Any]:
    _require(isinstance(raw, dict), "metadata: must be a mapping")
    _no_unknown_keys(raw, METADATA_KEYS, "metadata")
    if "source" in raw:
        _require(
            isinstance(raw["source"], str) and raw["source"].strip() != "",
            "metadata.source: must be a non-empty string",
        )
    if "rationale" in raw:
        _require(
            isinstance(raw["rationale"], str) and raw["rationale"].strip() != "",
            "metadata.rationale: must be a non-empty string",
        )
    if "tags" in raw:
        tags = raw["tags"]
        _require(
            isinstance(tags, list) and bool(tags),
            "metadata.tags: must be a non-empty list when present",
        )
        bad = sorted(t for t in tags if t not in METADATA_TAGS)
        _require(not bad, f"metadata.tags: unknown tag(s) {bad}")
        _require(len(set(tags)) == len(tags), "metadata.tags: duplicate tag")
    return raw


def parse_case(data: Any) -> BenchmarkCase:
    """Validate ``data`` (already YAML/JSON-decoded) as one benchmark case.

    Returns a :class:`BenchmarkCase` or raises :class:`FixtureFormatError`.
    Fail-closed: an unsupported ``format`` is rejected before any other
    field is read, so an old case is never reinterpreted under new rules.
    """
    _require(isinstance(data, dict), "fixture: top level must be a mapping")

    fmt = data.get("format")
    _require(
        isinstance(fmt, str) and fmt in SUPPORTED_FORMATS,
        f"fixture: unsupported or missing 'format' {fmt!r}; "
        f"this validator implements {sorted(SUPPORTED_FORMATS)}",
    )
    _no_unknown_keys(data, _TOP_LEVEL_KEYS, "fixture")

    case_id = data.get("id")
    _require(
        isinstance(case_id, str) and bool(_SLUG_RE.match(case_id or "")),
        "fixture: 'id' must be a kebab-case slug",
    )
    title = data.get("title")
    _require(
        isinstance(title, str) and title.strip() != "",
        "fixture: 'title' is required and must be a non-empty string",
    )
    _require("input" in data, "fixture: 'input' is required")
    _require("expected" in data, "fixture: 'expected' is required")

    parsed_input = _parse_input(data["input"])

    expected = data["expected"]
    _require(isinstance(expected, dict), "expected: must be a mapping")
    _no_unknown_keys(expected, _EXPECTED_KEYS, "expected")

    completeness = expected.get("findings_completeness", "exhaustive")
    _require(
        completeness in COMPLETENESS,
        f"expected.findings_completeness: must be one of {sorted(COMPLETENESS)}",
    )

    raw_findings = expected.get("findings")
    _require(isinstance(raw_findings, list), "expected.findings: must be a list (possibly empty)")
    findings = tuple(
        _parse_finding(f, "expected.findings") for f in raw_findings
    )
    entry_keys = [f.key for f in findings]
    _require(
        len(set(entry_keys)) == len(entry_keys),
        "expected.findings: duplicate finding 'key'",
    )
    nested_keys = [m.key for f in findings if f.is_any_of for m in f.members]
    clash = sorted(set(nested_keys) & set(entry_keys))
    _require(
        not clash,
        f"expected.findings: key(s) used both standalone and inside any_of: {clash}",
    )
    # Every finding is addressable as (case id, key), so a key is unique
    # across the whole case — entries and any_of members together (§5, §8).
    all_keys = entry_keys + nested_keys
    dupes = sorted({k for k in all_keys if all_keys.count(k) > 1})
    _require(not dupes, f"expected.findings: finding 'key' is not unique across the case: {dupes}")

    decision = expected.get("decision")
    if decision is not None:
        _require(
            decision in DECISIONS,
            f"expected.decision: must be one of {sorted(DECISIONS)} when present",
        )

    metadata = _parse_metadata(data["metadata"]) if "metadata" in data else {}

    case = BenchmarkCase(
        format=fmt,
        id=case_id,
        title=title,
        input=parsed_input,
        decision=decision,
        findings_completeness=completeness,
        findings=findings,
        metadata=metadata,
    )

    if decision is not None:
        _require(
            decision == case.derived_decision,
            f"expected.decision {decision!r} contradicts the required findings' "
            f"severities (mechanically derived: {case.derived_decision!r})",
        )
    return case
