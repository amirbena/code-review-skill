#!/usr/bin/env python3
"""Test-only reference for the machine-readable review result (Issue #67).

Not runtime logic, not packaged -- nothing emits a review result yet
(Issues #69/#70). Mirrors docs/review-result/review-result-model.md and
checks a result document in two layers: shape, against
review-result.schema.json, and cross-field consistency, by delegating to
the existing reference models that mirror each canonical owner
(decision_semantics, review_stopping_criteria, finding_confidence).
Consistency is asserted against those owners rather than re-derived here,
so the result format cannot grow a second copy of a rule.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from tests.reference.review import decision_semantics as ds
from tests.reference.review import finding_confidence as fc
from tests.reference.review import review_stopping_criteria as rsc
from tests.reference.review.change_risk_signals import Depth

SCHEMA_VERSION = "1.0.0"
DOCS_DIR = Path(__file__).resolve().parents[3] / "docs" / "review-result"
SCHEMA_PATH = DOCS_DIR / "review-result.schema.json"
EXAMPLE_PATH = DOCS_DIR / "examples" / "review-result.example.json"

# The machine code for each mechanically derived decision. Skill-specific
# labels ("REVIEW CLEAN" / "Approve", ...) are renderings of these values.
DECISION_CODES: dict[ds.Decision, str] = {
    ds.Decision.CLEAN: "clean",
    ds.Decision.CHANGES_REQUIRED: "blocking",
}
INCOMPLETE_OUTCOME = "incomplete"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


# --- Shape: the JSON Schema subset this repository's schema file uses ----


def _is_type(value: Any, json_type: str) -> bool:
    if json_type == "null":
        return value is None
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "boolean":
        return isinstance(value, bool)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "array":
        return isinstance(value, list)
    if json_type == "object":
        return isinstance(value, dict)
    raise AssertionError(f"unsupported JSON type in schema: {json_type}")


def _resolve(ref: str, root: Mapping) -> Mapping:
    if not ref.startswith("#/"):
        raise AssertionError(f"only local $ref is supported, got {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _pattern_matches(pattern: str, text: str) -> bool:
    # ECMA `$` never matches before a trailing newline; Python's does.
    return re.search(re.sub(r"(?<!\\)\$$", r"\\Z", pattern), text) is not None


def _validate(value: Any, node: Mapping, root: Mapping, path: str, errors: list[str]) -> None:
    if "$ref" in node:
        _validate(value, _resolve(node["$ref"], root), root, path, errors)
        return
    if "type" in node:
        allowed = [node["type"]] if isinstance(node["type"], str) else list(node["type"])
        if not any(_is_type(value, t) for t in allowed):
            errors.append(f"{path}: expected type {allowed}, got {value!r}")
            return
    if "const" in node and value != node["const"]:
        errors.append(f"{path}: expected {node['const']!r}, got {value!r}")
    if "enum" in node and value not in node["enum"]:
        errors.append(f"{path}: {value!r} not in enum {node['enum']}")

    if isinstance(value, str):
        if len(value) < node.get("minLength", 0):
            errors.append(f"{path}: shorter than {node['minLength']}")
        if "pattern" in node and not _pattern_matches(node["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {node['pattern']}")
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in node and value < node["minimum"]:
            errors.append(f"{path}: {value} below minimum {node['minimum']}")
    if isinstance(value, list):
        if len(value) < node.get("minItems", 0):
            errors.append(f"{path}: fewer than {node['minItems']} items")
        if "items" in node:
            for index, item in enumerate(value):
                _validate(item, node["items"], root, f"{path}[{index}]", errors)
    if isinstance(value, dict):
        properties = node.get("properties", {})
        for name in node.get("required", ()):
            if name not in value:
                errors.append(f"{path}: missing required property {name!r}")
        for name, sub_value in value.items():
            if name in properties:
                _validate(sub_value, properties[name], root, f"{path}.{name}", errors)
            elif node.get("additionalProperties", True) is False:
                errors.append(f"{path}: unexpected property {name!r}")


def validate_against_schema(result: Any, schema: Mapping | None = None) -> tuple[str, ...]:
    """Shape errors only; an empty tuple means the document matches the schema."""
    schema = schema if schema is not None else load_schema()
    errors: list[str] = []
    _validate(result, schema, schema, "$", errors)
    return tuple(errors)


# --- Consistency: delegated to the canonical owners' reference models ----


def derived_decision_code(severities: Sequence[str]) -> str:
    """The `decision.derived` value severity.md's derivation yields."""
    findings = [ds.Finding(id=f"F{i}", severity=ds.Severity(s)) for i, s in enumerate(severities)]
    return DECISION_CODES[ds.derive_decision(findings)]


def expected_outcome(coverage: str, derived: str) -> str:
    """The primary outcome after review-stopping-criteria.md's coverage
    override, computed by that policy's own reference `decision_label`."""
    result = rsc.CoverageResult(coverage=coverage, depth=Depth.STANDARD, partitioned=False)
    label = rsc.decision_label(result, derived)
    return INCOMPLETE_OUTCOME if label == "REVIEW INCOMPLETE" else derived


def expected_counts(severities: Sequence[str]) -> dict[str, int]:
    return {level.lower(): sum(1 for s in severities if s == level) for level in ("P0", "P1", "P2")}


def _confidence_errors(finding: Mapping, path: str) -> list[str]:
    """`confidence` must not contradict the runtime-validation state that
    feeds it (finding_confidence.from_runtime_state)."""
    contribution = fc.from_runtime_state(finding["runtime_validation"])
    confidence = finding["confidence"]
    if contribution is fc.Confidence.CONFIRMED and confidence != fc.Confidence.CONFIRMED.value:
        return [f"{path}: runtime-confirmed requires confidence 'confirmed', got {confidence!r}"]
    if contribution is fc.Confidence.RUNTIME_VALIDATION_UNAVAILABLE and confidence not in (
        fc.Confidence.CONFIRMED.value,
        fc.Confidence.RUNTIME_VALIDATION_UNAVAILABLE.value,
    ):
        return [
            f"{path}: attempted-inconclusive allows only 'confirmed' or "
            f"'runtime-validation-unavailable', got {confidence!r}"
        ]
    return []


def consistency_errors(result: Mapping) -> tuple[str, ...]:
    """Cross-field errors for a result that already matches the schema."""
    errors: list[str] = []
    findings = result["findings"]
    severities = [f["severity"] for f in findings]

    if dict(result["counts"]) != expected_counts(severities):
        errors.append(f"$.counts: {result['counts']} does not tally findings {expected_counts(severities)}")

    derived = derived_decision_code(severities)
    if result["decision"]["derived"] != derived:
        errors.append(f"$.decision.derived: {result['decision']['derived']!r}, severity tally gives {derived!r}")
    outcome = expected_outcome(result["coverage"], result["decision"]["derived"])
    if result["decision"]["outcome"] != outcome:
        errors.append(
            f"$.decision.outcome: {result['decision']['outcome']!r}, coverage "
            f"{result['coverage']!r} gives {outcome!r}"
        )

    ids = [f["id"] for f in findings]
    if len(set(ids)) != len(ids):
        errors.append("$.findings: finding ids are not unique within the review")
    stable_ids = [f["identity"]["stable_id"] for f in findings]
    if len(set(stable_ids)) != len(stable_ids):
        errors.append("$.findings: stable identities are not unique within the review")

    state = result["reviewed_state"]
    if state["prior_reviewed_sha"] is not None and state["prior_reviewed_sha"] == state["reviewed_head_sha"]:
        errors.append("$.reviewed_state: prior_reviewed_sha must not name the reviewed head itself")

    for index, finding in enumerate(findings):
        errors.extend(_confidence_errors(finding, f"$.findings[{index}]"))
    return tuple(errors)


def validate_review_result(result: Any) -> tuple[str, ...]:
    """Shape errors, then -- only when the shape is sound -- consistency errors."""
    shape = validate_against_schema(result)
    return shape if shape else consistency_errors(result)
