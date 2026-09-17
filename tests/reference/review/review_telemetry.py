#!/usr/bin/env python3
"""Test-only reference for the review execution telemetry record (Issue #182).

Mirrors docs/review-telemetry/review-execution-telemetry-model.md and its
JSON Schema (review-execution-telemetry.schema.json): the record shape,
each metric's unavailable state, and a small hand-rolled validator so
worked examples are checked against the one schema file rather than a
re-derived copy. Not runtime logic, not packaged -- no code path here is
wired into a live review; see the model doc's Section 8.

`decide_with_telemetry` exists only to prove, by construction, that a
telemetry value has no path into the existing decision contract
(tests/reference/review/decision_semantics.py) -- the guarantee test in
tests/unit/review/observability/test_review_telemetry.py relies on its signature never
forwarding `telemetry` into `derive_decision`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple

from tests.reference.review import decision_semantics as ds

SCHEMA_VERSION = "1.0.0"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "review-telemetry"
    / "review-execution-telemetry.schema.json"
)

# The fixed, closed catalog of review passes a telemetry record can name as
# completed. Mirrors review-stopping-criteria.md's own per-depth pass list.
STAGES: Tuple[str, ...] = (
    "scope_normalization",
    "change_risk_classification",
    "repository_expansion",
    "large_pr_partitioning",
    "runtime_validation",
    "stopping_criteria",
)

# repository-expansion.md's fixed trigger catalog (Issue #87).
EXPANSION_TRIGGERS: Tuple[str, ...] = (
    "call_site",
    "interface_contract",
    "migration_schema",
    "config_consumer",
)

RUNTIME_VALIDATION_OUTCOMES: Tuple[str, ...] = ("executed", "failed", "skipped", "unavailable")
RUNTIME_VALIDATION_PROVENANCES: Tuple[str, ...] = ("sandbox", "trusted_host")


@dataclass(frozen=True)
class RuntimeValidationExecution:
    outcome: str
    provenance: Optional[str] = None

    def to_dict(self) -> dict:
        return {"outcome": self.outcome, "provenance": self.provenance}


@dataclass(frozen=True)
class PartitionUsage:
    partition_count: int
    partition_ids: Tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "partition_count": self.partition_count,
            "partition_ids": list(self.partition_ids),
        }


@dataclass(frozen=True)
class ReviewExecutionTelemetry:
    """One review run's observational execution record.

    Every metric field defaults to its documented "stage did not run"
    unavailable state (None), per the model doc's Section 3 table -- a
    partial run is constructed the same way as a full one, just with more
    fields left at their default.
    """

    review_id: str
    generated_at: str
    stages_completed: Tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION
    files_inspected: Optional[Tuple[str, ...]] = None
    symbols_expanded_count: Optional[int] = None
    repository_intelligence_expansions: Optional[Mapping[str, Optional[int]]] = None
    runtime_validations: Optional[Tuple[RuntimeValidationExecution, ...]] = None
    partitions: Optional[PartitionUsage] = None
    stage_timing_ms: Optional[Mapping[str, Optional[float]]] = None

    def to_dict(self) -> dict:
        record: dict = {
            "schema_version": self.schema_version,
            "review_id": self.review_id,
            "generated_at": self.generated_at,
            "stages_completed": list(self.stages_completed),
        }
        if self.files_inspected is not None:
            record["files_inspected"] = list(self.files_inspected)
        else:
            record["files_inspected"] = None
        record["symbols_expanded_count"] = self.symbols_expanded_count
        record["repository_intelligence_expansions"] = (
            dict(self.repository_intelligence_expansions)
            if self.repository_intelligence_expansions is not None
            else None
        )
        record["runtime_validations"] = (
            [rv.to_dict() for rv in self.runtime_validations]
            if self.runtime_validations is not None
            else None
        )
        record["partitions"] = (
            self.partitions.to_dict() if self.partitions is not None else None
        )
        record["stage_timing_ms"] = (
            dict(self.stage_timing_ms) if self.stage_timing_ms is not None else None
        )
        return record


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _type_matches(value, json_type: str) -> bool:
    if json_type == "null":
        return value is None
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "array":
        return isinstance(value, list)
    if json_type == "object":
        return isinstance(value, dict)
    raise AssertionError(f"unsupported JSON type in schema: {json_type}")


def _matches_any_type(value, json_types) -> bool:
    types = [json_types] if isinstance(json_types, str) else list(json_types)
    return any(_type_matches(value, t) for t in types)


def _validate_node(value, node: Mapping, path: str, errors: list) -> None:
    """Minimal recursive validator covering the subset of JSON Schema this
    repository's schema file actually uses: type (incl. null-union),
    const, enum, required, properties, additionalProperties, items,
    minItems, uniqueItems. No external dependency -- see the model doc's
    Section 8 for why one was not added."""
    if "type" in node and not _matches_any_type(value, node["type"]):
        errors.append(f"{path}: expected type {node['type']}, got {value!r}")
        return
    if "const" in node and value != node["const"]:
        errors.append(f"{path}: expected const {node['const']!r}, got {value!r}")
    if "enum" in node and value not in node["enum"]:
        errors.append(f"{path}: {value!r} not in enum {node['enum']}")

    if isinstance(value, dict):
        required = node.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        properties = node.get("properties", {})
        additional_allowed = node.get("additionalProperties", True)
        for key, sub_value in value.items():
            if key in properties:
                _validate_node(sub_value, properties[key], f"{path}.{key}", errors)
            elif additional_allowed is False:
                errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(additional_allowed, dict):
                _validate_node(sub_value, additional_allowed, f"{path}.{key}", errors)

    if isinstance(value, list):
        items_schema = node.get("items")
        if items_schema:
            for i, item in enumerate(value):
                _validate_node(item, items_schema, f"{path}[{i}]", errors)
        min_items = node.get("minItems")
        if min_items is not None and len(value) < min_items:
            errors.append(f"{path}: expected at least {min_items} items, got {len(value)}")
        if node.get("uniqueItems") and len(value) != len(set(value)):
            errors.append(f"{path}: items are not unique")


def validate_against_schema(record: Mapping, schema: Mapping) -> Tuple[str, ...]:
    """Returns a tuple of validation error strings; empty means valid."""
    errors: list = []
    _validate_node(dict(record), schema, "$", errors)
    return tuple(errors)


def decide_with_telemetry(
    findings: Sequence[ds.Finding],
    telemetry: Optional[ReviewExecutionTelemetry],
) -> ds.Decision:
    """Derives the decision exactly as `ds.derive_decision` would, ignoring
    `telemetry` entirely. Kept as a distinct wrapper (rather than calling
    `ds.derive_decision` directly at every call site) so a test can assert,
    by construction, that supplying vs. omitting telemetry cannot change the
    result -- the parameter is accepted and never read."""
    del telemetry  # never forwarded into the decision contract -- by design
    return ds.derive_decision(findings)
