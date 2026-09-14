#!/usr/bin/env python3
"""Validate the canonical threat-scenario catalog (docs/threat-model/catalog/*.yaml).

See docs/threat-model/catalog/README.md for the format contract.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_FORMATS: frozenset[str] = frozenset({"threat-scenario-catalog/v1"})

GAP = "COVERAGE_GAP"
NOT_APPLICABLE = "NOT_APPLICABLE"

# The seven canonical threat domains from issue #300. The ID namespace prefix is
# derived mechanically from this table — never hand-duplicated per scenario.
CATEGORIES: frozenset[str] = frozenset(
    {"AUTH", "SBOX", "DELEG", "INJECT", "GIT", "SCOPE", "DOS"}
)

# The six adversary/failure models #300 requires every scenario to be expressed in
# terms of (never "the model should behave" — always an actor or a condition).
ATTACKER_MODELS: frozenset[str] = frozenset(
    {
        "malicious_contributor",
        "prompt_injected_context",
        "compromised_agent",
        "confused_deputy",
        "runtime_misconfiguration",
        "resource_abuse",
    }
)

# Threat-scenario severity is a deliberately separate closed set from the
# review-finding P0/P1/P2 severity owned by shared/policies/severity.md. This
# catalog must never redefine or be confused with that scale.
THREAT_SEVERITIES: frozenset[str] = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})
REVIEW_FINDING_SEVERITIES: frozenset[str] = frozenset({"P0", "P1", "P2"})

# Benchmark families a scenario can declare itself covered by. "none" is valid only
# with a justification recorded in `benchmark_reference` (checked below).
BENCHMARK_FAMILIES: frozenset[str] = frozenset(
    {"mutation/#305", "sandbox/#306", "delegation/#307", "security-event/#308", "none"}
)

# Provisional denied-capability event-class vocabulary. #299 owns the real,
# authoritative taxonomy; every name here is explicitly provisional and this
# validator only checks that scenarios draw from one stable, spelled-out set
# rather than inventing a fresh string per scenario.
PROVISIONAL_EVENT_CLASSES: frozenset[str] = frozenset(
    {
        "DENIED_MUTATION_UNAUTHORIZED",
        "DENIED_MUTATION_CAPABILITY_ABSENT",
        "DENIED_MUTATION_STALE_APPROVAL",
        "DENIED_MUTATION_SCOPE_ESCAPE",
        "DENIED_MUTATION_AUTHORIZATION_REPLAY",
        "DENIED_SPAWN_UNAUTHORIZED",
        "DENIED_SPAWN_BUDGET_EXCEEDED",
        "DENIED_SPAWN_DEPTH_EXCEEDED",
        "DENIED_DELEGATION_AUTHORITY_ESCALATION",
        "DENIED_DELEGATION_REPLAY",
        "DENIED_SANDBOX_NETWORK_ACCESS",
        "DENIED_SANDBOX_CREDENTIAL_ACCESS",
        "DENIED_SANDBOX_FILESYSTEM_ACCESS",
        "DENIED_SANDBOX_RESOURCE_EXHAUSTION",
        "DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE",
        "DENIED_GIT_UNSAFE_CONFIG",
        "DENIED_GIT_PATH_ESCAPE",
        NOT_APPLICABLE,
    }
)

_ID_RE = re.compile(r"^(?P<category>[A-Z]+)-(?P<number>\d{3})$")

_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "title",
        "category",
        "attacker_model",
        "attacker_controlled_inputs",
        "assumed_attacker_capabilities",
        "trusted_inputs",
        "protected_asset",
        "required_capability_state",
        "enforcement_owner",
        "enforcement_point",
        "expected_safe_outcome",
        "expected_security_event",
        "benchmark_family",
        "benchmark_reference",
        "regression_evidence",
        "threat_severity",
    }
)
_OPTIONAL_KEYS: frozenset[str] = frozenset({"notes"})
_ALL_KEYS: frozenset[str] = _REQUIRED_KEYS | _OPTIONAL_KEYS

# A reference field is either the literal gap token or must look like a real
# pointer: a file path under this repository (tests/, docs/, shared/, skills/,
# scripts/) or an issue reference (#123). This is deliberately syntactic —
# "well-formed, not necessarily resolvable yet" per #300's own constraint — so it
# catches an invented-looking string without requiring the target to exist.
_REAL_PATH_PREFIXES = ("tests/", "docs/", "shared/", "skills/", "scripts/")
_ISSUE_REF_RE = re.compile(r"#\d+")


class ThreatModelFormatError(ValueError):
    """A catalog file or scenario does not conform to threat-scenario-catalog/v1."""


@dataclass(frozen=True)
class ThreatScenario:
    id: str
    title: str
    category: str
    attacker_model: str
    attacker_controlled_inputs: tuple[str, ...]
    assumed_attacker_capabilities: tuple[str, ...]
    trusted_inputs: tuple[str, ...]
    protected_asset: str
    required_capability_state: str
    enforcement_owner: str
    enforcement_point: str
    expected_safe_outcome: str
    expected_security_event: str
    benchmark_family: tuple[str, ...]
    benchmark_reference: str
    regression_evidence: str
    threat_severity: str
    notes: str = ""
    source_file: str = field(default="", compare=False)

    @property
    def is_enforcement_gap(self) -> bool:
        return self.enforcement_point == GAP

    @property
    def is_benchmark_gap(self) -> bool:
        return self.benchmark_reference == GAP

    @property
    def is_regression_gap(self) -> bool:
        return self.regression_evidence == GAP


def _require_str(obj: dict, key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ThreatModelFormatError(f"{obj.get('id', '<unknown>')}: {key!r} must be a non-empty string")
    return value


def _require_str_list(obj: dict, key: str, *, allow_empty: bool) -> tuple[str, ...]:
    value = obj.get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ThreatModelFormatError(f"{obj.get('id', '<unknown>')}: {key!r} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise ThreatModelFormatError(f"{obj.get('id', '<unknown>')}: {key!r} must not be empty")
    return tuple(value)


def _check_reference(scenario_id: str, field_name: str, value: str) -> None:
    if value == GAP:
        return
    if any(value.startswith(p) for p in _REAL_PATH_PREFIXES):
        return
    if _ISSUE_REF_RE.search(value):
        return
    if value.startswith("existing:"):
        return
    raise ThreatModelFormatError(
        f"{scenario_id}: {field_name}={value!r} is neither {GAP!r}, a repository path "
        "(tests/docs/shared/skills/scripts...), an 'existing: ...' citation, nor an issue reference (#NNN)"
    )


def parse_scenario(raw: dict, *, source_file: str = "") -> ThreatScenario:
    if not isinstance(raw, dict):
        raise ThreatModelFormatError(f"scenario entry must be a mapping, got {type(raw).__name__}")

    unknown = set(raw) - _ALL_KEYS
    if unknown:
        raise ThreatModelFormatError(f"{raw.get('id', '<unknown>')}: unknown field(s) {sorted(unknown)}")
    missing = _REQUIRED_KEYS - set(raw)
    if missing:
        raise ThreatModelFormatError(f"{raw.get('id', '<unknown>')}: missing required field(s) {sorted(missing)}")

    scenario_id = _require_str(raw, "id")
    id_match = _ID_RE.match(scenario_id)
    if not id_match:
        raise ThreatModelFormatError(f"{scenario_id!r}: id must match '<CATEGORY>-<3 digits>' (e.g. AUTH-001)")

    category = _require_str(raw, "category")
    if category not in CATEGORIES:
        raise ThreatModelFormatError(f"{scenario_id}: category {category!r} not in {sorted(CATEGORIES)}")
    if id_match.group("category") != category:
        raise ThreatModelFormatError(
            f"{scenario_id}: id prefix {id_match.group('category')!r} does not match category {category!r}"
        )

    attacker_model = _require_str(raw, "attacker_model")
    if attacker_model not in ATTACKER_MODELS:
        raise ThreatModelFormatError(
            f"{scenario_id}: attacker_model {attacker_model!r} not in {sorted(ATTACKER_MODELS)}"
        )

    title = _require_str(raw, "title")
    attacker_controlled_inputs = _require_str_list(raw, "attacker_controlled_inputs", allow_empty=False)
    assumed_attacker_capabilities = _require_str_list(raw, "assumed_attacker_capabilities", allow_empty=False)
    trusted_inputs = _require_str_list(raw, "trusted_inputs", allow_empty=True)
    protected_asset = _require_str(raw, "protected_asset")
    required_capability_state = _require_str(raw, "required_capability_state")
    enforcement_owner = _require_str(raw, "enforcement_owner")
    enforcement_point = _require_str(raw, "enforcement_point")
    expected_safe_outcome = _require_str(raw, "expected_safe_outcome")

    expected_security_event = _require_str(raw, "expected_security_event")
    if expected_security_event not in PROVISIONAL_EVENT_CLASSES:
        raise ThreatModelFormatError(
            f"{scenario_id}: expected_security_event {expected_security_event!r} not in the provisional "
            f"event-class vocabulary {sorted(PROVISIONAL_EVENT_CLASSES)}"
        )

    benchmark_family_raw = _require_str(raw, "benchmark_family")
    benchmark_family = tuple(part.strip() for part in benchmark_family_raw.split(","))
    for part in benchmark_family:
        if part not in BENCHMARK_FAMILIES:
            raise ThreatModelFormatError(
                f"{scenario_id}: benchmark_family part {part!r} not in {sorted(BENCHMARK_FAMILIES)}"
            )
    if "none" in benchmark_family and len(benchmark_family) > 1:
        raise ThreatModelFormatError(f"{scenario_id}: benchmark_family cannot combine 'none' with a real family")

    benchmark_reference = _require_str(raw, "benchmark_reference")
    if benchmark_family == ("none",):
        if benchmark_reference == GAP:
            raise ThreatModelFormatError(
                f"{scenario_id}: benchmark_family is 'none' but benchmark_reference is {GAP!r}; "
                "'none' requires a stated justification, not a gap"
            )
    else:
        _check_reference(scenario_id, "benchmark_reference", benchmark_reference)

    regression_evidence = _require_str(raw, "regression_evidence")
    _check_reference(scenario_id, "regression_evidence", regression_evidence)

    enforcement_owner_ok = (
        enforcement_owner == GAP
        or enforcement_owner.startswith("existing:")
        or _ISSUE_REF_RE.search(enforcement_owner)
    )
    if not enforcement_owner_ok:
        raise ThreatModelFormatError(
            f"{scenario_id}: enforcement_owner={enforcement_owner!r} is neither {GAP!r}, an 'existing: ...' "
            "citation, nor an issue reference (#NNN)"
        )
    enforcement_point_ok = enforcement_point == GAP or len(enforcement_point) > 0
    if not enforcement_point_ok:
        raise ThreatModelFormatError(f"{scenario_id}: enforcement_point must be {GAP!r} or a description")
    # A gap in enforcement ownership but a non-gap enforcement point (or vice versa)
    # is a drift the catalog must catch, not silently tolerate.
    if enforcement_owner == GAP and enforcement_point != GAP:
        raise ThreatModelFormatError(
            f"{scenario_id}: enforcement_owner is {GAP!r} but enforcement_point is not; both must agree "
            "on whether this scenario has a real enforcement owner"
        )

    threat_severity = _require_str(raw, "threat_severity")
    if threat_severity not in THREAT_SEVERITIES:
        raise ThreatModelFormatError(
            f"{scenario_id}: threat_severity {threat_severity!r} not in {sorted(THREAT_SEVERITIES)}"
        )
    if threat_severity in REVIEW_FINDING_SEVERITIES:
        raise ThreatModelFormatError(
            f"{scenario_id}: threat_severity {threat_severity!r} collides with a review-finding P0/P1/P2 "
            "severity token; threat-scenario severity must stay a visibly distinct scale"
        )

    notes = raw.get("notes", "")
    if notes is not None and not isinstance(notes, str):
        raise ThreatModelFormatError(f"{scenario_id}: notes must be a string when present")

    # Never let this catalog redefine review verdict semantics.
    for banned in ("REVIEW CLEAN", "REVIEW INCOMPLETE", "CHANGES REQUIRED", "decision:"):
        for text_field in (expected_safe_outcome, required_capability_state, notes or ""):
            if banned in text_field:
                raise ThreatModelFormatError(
                    f"{scenario_id}: field text contains {banned!r} — this catalog must never redefine "
                    "review decision/verdict semantics owned by shared/policies/severity.md and "
                    "shared/policies/review-scope.md"
                )

    return ThreatScenario(
        id=scenario_id,
        title=title,
        category=category,
        attacker_model=attacker_model,
        attacker_controlled_inputs=attacker_controlled_inputs,
        assumed_attacker_capabilities=assumed_attacker_capabilities,
        trusted_inputs=trusted_inputs,
        protected_asset=protected_asset,
        required_capability_state=required_capability_state,
        enforcement_owner=enforcement_owner,
        enforcement_point=enforcement_point,
        expected_safe_outcome=expected_safe_outcome,
        expected_security_event=expected_security_event,
        benchmark_family=benchmark_family,
        benchmark_reference=benchmark_reference,
        regression_evidence=regression_evidence,
        threat_severity=threat_severity,
        notes=notes or "",
        source_file=source_file,
    )


def parse_catalog_file(raw_doc: dict, *, source_file: str = "") -> list[ThreatScenario]:
    if not isinstance(raw_doc, dict):
        raise ThreatModelFormatError(f"{source_file}: catalog file must be a mapping")
    fmt = raw_doc.get("format")
    if fmt not in SUPPORTED_FORMATS:
        raise ThreatModelFormatError(f"{source_file}: unsupported format {fmt!r}, expected one of {sorted(SUPPORTED_FORMATS)}")
    file_category = raw_doc.get("category")
    if file_category not in CATEGORIES:
        raise ThreatModelFormatError(f"{source_file}: file-level category {file_category!r} not in {sorted(CATEGORIES)}")
    scenarios_raw = raw_doc.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise ThreatModelFormatError(f"{source_file}: 'scenarios' must be a non-empty list")

    scenarios = [parse_scenario(item, source_file=source_file) for item in scenarios_raw]
    for sc in scenarios:
        if sc.category != file_category:
            raise ThreatModelFormatError(
                f"{source_file}: scenario {sc.id} has category {sc.category!r}, "
                f"but this file declares category {file_category!r}"
            )
    return scenarios


def load_catalog(catalog_dir: Path) -> list[ThreatScenario]:
    files = sorted(catalog_dir.glob("*.yaml"))
    if not files:
        raise ThreatModelFormatError(f"no catalog files found under {catalog_dir}")
    all_scenarios: list[ThreatScenario] = []
    for path in files:
        with open(path, encoding="utf-8") as handle:
            raw_doc = yaml.safe_load(handle)
        all_scenarios.extend(parse_catalog_file(raw_doc, source_file=str(path)))

    # Cross-file invariants: catalog-wide id uniqueness and category coverage.
    ids = [sc.id for sc in all_scenarios]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ThreatModelFormatError(f"duplicate scenario id(s) across the catalog: {sorted(duplicates)}")

    present_categories = {sc.category for sc in all_scenarios}
    missing_categories = CATEGORIES - present_categories
    if missing_categories:
        raise ThreatModelFormatError(
            f"catalog is missing every scenario in the required categories {sorted(missing_categories)} — "
            "a category silently disappearing from the index is treated as an error, not an empty result"
        )

    # IDs are numbered per-category; a gap or duplicate number within a category is
    # allowed (stability across rewording matters more than density), but every
    # number must actually parse as declared.
    return all_scenarios


def validate(catalog_dir: Path) -> list[ThreatScenario]:
    return load_catalog(catalog_dir)


def _default_catalog_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "threat-model" / "catalog"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-dir",
        type=Path,
        default=None,
        help="directory containing threat-scenario-catalog/v1 YAML files (default: docs/threat-model/catalog)",
    )
    args = parser.parse_args(argv)
    catalog_dir = args.catalog_dir or _default_catalog_dir()

    try:
        scenarios = validate(catalog_dir)
    except ThreatModelFormatError as exc:
        print(f"::error::threat-model catalog validation failed: {exc}", file=sys.stderr)
        return 1

    by_category: dict[str, int] = {}
    gaps = {"enforcement": 0, "benchmark": 0, "regression": 0}
    for sc in scenarios:
        by_category[sc.category] = by_category.get(sc.category, 0) + 1
        gaps["enforcement"] += sc.is_enforcement_gap
        gaps["benchmark"] += sc.is_benchmark_gap
        gaps["regression"] += sc.is_regression_gap

    print(f"OK: {len(scenarios)} scenarios across {len(by_category)} categories")
    for cat in sorted(by_category):
        print(f"  {cat}: {by_category[cat]}")
    print(
        f"coverage gaps -> enforcement: {gaps['enforcement']}, "
        f"benchmark: {gaps['benchmark']}, regression: {gaps['regression']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
