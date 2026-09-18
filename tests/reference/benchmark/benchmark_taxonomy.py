#!/usr/bin/env python3
"""Canonical benchmark candidate taxonomy and its validation (Issue #333).

Test-only reference, like ``benchmark_fixture.py`` alongside it: not
runtime logic, not packaged — the packaged Skills stay Markdown/YAML only.
Mirrors ``docs/benchmark/taxonomy.md``, the canonical, alias-free contract
for four closed dimensions:

- ``capability`` — canonical name per existing corpus domain directory.
- ``policy_contract`` — a maintained closed list of ``shared/policies/*.md``
  stems.
- ``risk_mode`` — reuses ``benchmark_fixture.METADATA_TAGS`` unchanged.
- ``affected_surface`` — the four named surfaces this repository's own
  changes can land on, refined from the boolean applicability check that
  used to live in the retired Issue #255 ``benchmark_ci_classifier.py``
  (Issue #420).

Every dimension carries an explicit ``unclassified`` value as a first-class
member, never an error state. This module owns two distinct validation
modes, deliberately kept separate:

- :func:`validate_taxonomy` — **fail-closed**, for hand-authored corpus
  case metadata (``docs/benchmark/fixture-format.md`` §10). A human
  mistake (unknown key, unknown value, missing dimension) is a hard
  rejection, exactly like the rest of the fixture format.
- :func:`sanitize_taxonomy_response` — **fail-open into ``unclassified``**,
  for the one bounded, schema-constrained PR-diff classification model
  call. A model may only select from the canonical enum; anything else
  (an invented key, an invented value, malformed JSON, a missing
  dimension) never raises and never causes a full-index scan — it is
  dropped, and the affected dimension resolves to ``unclassified``,
  because the model is untrusted input while a corpus author is not.
"""

from __future__ import annotations

from typing import Any

UNCLASSIFIED = "unclassified"

# --------------------------------------------------------------------------
# capability — canonical name per existing corpus domain directory
# (docs/benchmark/corpus/*/), plus "core" for the four loose root-level
# cases that predate sub-directory organization. Directory names carrying a
# "-deepening" suffix are normalized to their bare capability (e.g.
# "database-migration-deepening" -> "database-migration") so the taxonomy
# names the *capability*, not the corpus's incidental directory-naming
# history; "security-deepening" is additionally renamed to
# "security-boundary" to stay vocabulary-consistent with the "Security /
# trust boundaries" dimension in shared/policies/review-scope.md (#211),
# per this taxonomy's own non-goal of naming consistency without a shared
# artifact.
# --------------------------------------------------------------------------
CAPABILITY_VALUES: frozenset[str] = frozenset(
    {
        "analogue-placement-pattern",
        "api-compatibility",
        "candidate-finding-validation",
        "consolidation",
        "core",
        "database-migration",
        "decision-derivation",
        "delegation-spawn",
        "dependency-supply-chain",
        "distributed-systems",
        "mutation-boundary",
        "null-absence-risk",
        "performance",
        "publication-mode",
        "repository-intelligence",
        "reviewer-brief",
        "risk-depth",
        "sandbox-adversarial",
        "security-boundary",
        "security-events",
        "semantic-implication",
        "specialist-depth-composition",
        "trusted-host-nl-authorization",
        "verdict-consistency",
        UNCLASSIFIED,
    }
)

# Maps each real corpus domain directory (docs/benchmark/corpus/<dir>/) and
# the loose root-level cases to its canonical capability value. Single
# source of truth for the normalization described above; the inverted-index
# builder and the backfill of existing corpus metadata both key off this.
CAPABILITY_BY_CORPUS_DIRECTORY: dict[str, str] = {
    "analogue-placement-pattern": "analogue-placement-pattern",
    "api-compatibility": "api-compatibility",
    "candidate-finding-validation": "candidate-finding-validation",
    "consolidation": "consolidation",
    "database-migration-deepening": "database-migration",
    "decision-derivation": "decision-derivation",
    "delegation-spawn": "delegation-spawn",
    "dependency-supply-chain-deepening": "dependency-supply-chain",
    "distributed-systems-deepening": "distributed-systems",
    "mutation-boundary": "mutation-boundary",
    "null-absence-risk": "null-absence-risk",
    "performance-deepening": "performance",
    "publication-mode": "publication-mode",
    "repository-intelligence": "repository-intelligence",
    "reviewer-brief": "reviewer-brief",
    "risk-depth": "risk-depth",
    "sandbox-adversarial": "sandbox-adversarial",
    "security-deepening": "security-boundary",
    "security-events": "security-events",
    "semantic-implication": "semantic-implication",
    "specialist-depth-composition": "specialist-depth-composition",
    "trusted-host-nl-authorization": "trusted-host-nl-authorization",
    "verdict-consistency": "verdict-consistency",
}

# --------------------------------------------------------------------------
# policy_contract — a maintained closed list of shared/policies/*.md stems.
# Extended deliberately when a new policy file is added; the same
# hand-maintained-list-not-a-filesystem-scan style as the retired
# benchmark_ci_classifier.py's APPLICABLE_PREFIXES (Issue #420), so an
# accidental new file never silently widens the taxonomy.
# --------------------------------------------------------------------------
POLICY_CONTRACT_VALUES: frozenset[str] = frozenset(
    {
        "affected-test-analysis",
        "agent-delegation",
        "api-contract-compatibility",
        "architectural-placement",
        "change-risk-signals",
        "database-migration-deepening",
        "distributed-systems-deepening",
        "evidence",
        "failure-retry-recovery",
        "file-reviewability",
        "git-safety",
        "invocation-options",
        "jira-context",
        "large-pr-partitioning",
        "mutation-authority",
        "null-absence-risk",
        "parallel-review",
        "performance-deepening",
        "remediation-guidance",
        "remediation-scope-boundary",
        "repository-expansion",
        "repository-instructions",
        "requirement-coverage",
        "review-context",
        "review-evidence",
        "review-ownership",
        "review-scope",
        "review-stopping-criteria",
        "root-cause-consolidation",
        "runtime-validation",
        "security-deepening",
        "severity",
        "specialist-depth",
        "trusted-host-execution",
        "verdict-consistency",
        UNCLASSIFIED,
    }
)

# --------------------------------------------------------------------------
# risk_mode — reuses metadata.tags' existing enum unchanged (fixture-format
# .md §10 / benchmark_fixture.METADATA_TAGS). Duplicated here, not imported,
# to keep this module importable standalone by non-test tooling
# (scripts/benchmark/) without pulling in the fixture parser; a policy test
# pins the two frozensets equal so they can never drift apart.
# --------------------------------------------------------------------------
RISK_MODE_VALUES: frozenset[str] = frozenset(
    {
        "correctness",
        "security",
        "quality",
        "no-op",
        "regression",
        "concurrency",
        "performance",
        UNCLASSIFIED,
    }
)

# --------------------------------------------------------------------------
# affected_surface — derived from #255's classifier
# (scripts/benchmark/benchmark_ci_classifier.py, retired by #420). That
# classifier was a flat applicable/not-applicable boolean over path
# prefixes; this taxonomy refines the same prefix set into four named
# surfaces. Deliberately never imported from benchmark_ci_classifier.py,
# mirroring that module's own documented independence from other
# classifiers (it must not become a second place a change to one module
# ripples into the other's behavior) — this module needed no change when
# the classifier was retired.
# --------------------------------------------------------------------------
AFFECTED_SURFACE_VALUES: frozenset[str] = frozenset(
    {
        "shared-policy",
        "skill-instructions",
        "runtime-adapter",
        "benchmark-corpus-or-tooling",
        UNCLASSIFIED,
    }
)

# The two exact files #255 calls out as the benchmark runtime driver.
_RUNTIME_ADAPTER_EXACT_FILES: frozenset[str] = frozenset(
    {
        "scripts/benchmark/run_benchmark.py",
        "scripts/benchmark/benchmark_review_adapter.py",
    }
)

# Checked after the exact-file set above, so the two runtime-adapter files
# (which live under scripts/benchmark/) are not shadowed by the broader
# benchmark-corpus-or-tooling prefix below.
_SURFACE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("shared/", "shared-policy"),
    ("skills/", "skill-instructions"),
    ("docs/benchmark/", "benchmark-corpus-or-tooling"),
    ("tests/reference/benchmark/", "benchmark-corpus-or-tooling"),
    ("tests/unit/benchmark/", "benchmark-corpus-or-tooling"),
    ("tests/policy/benchmark/", "benchmark-corpus-or-tooling"),
    ("scripts/benchmark/", "benchmark-corpus-or-tooling"),
)

DIMENSIONS: dict[str, frozenset[str]] = {
    "capability": CAPABILITY_VALUES,
    "policy_contract": POLICY_CONTRACT_VALUES,
    "risk_mode": RISK_MODE_VALUES,
    "affected_surface": AFFECTED_SURFACE_VALUES,
}

DIMENSION_NAMES: frozenset[str] = frozenset(DIMENSIONS)


class TaxonomyError(ValueError):
    """A taxonomy mapping does not conform to the closed dimension/value
    contract — an unknown dimension, an unknown value, a missing dimension,
    or a malformed value list. Used only by :func:`validate_taxonomy`'s
    fail-closed path; :func:`sanitize_taxonomy_response` never raises."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TaxonomyError(message)


def normalize_path(path: str) -> str:
    p = path.strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def classify_affected_surface(path: str) -> str:
    """Deterministic, non-LLM ``affected_surface`` classification for one
    repository-relative path. Returns ``unclassified`` for anything outside
    the four named surfaces — never a guess."""
    p = normalize_path(path)
    if not p:
        return UNCLASSIFIED
    if p in _RUNTIME_ADAPTER_EXACT_FILES:
        return "runtime-adapter"
    for prefix, surface in _SURFACE_PREFIXES:
        if p.startswith(prefix):
            return surface
    return UNCLASSIFIED


def classify_affected_surfaces(paths: Any) -> tuple[str, ...]:
    """The set of ``affected_surface`` values touched by ``paths``, sorted.
    Empty input (or input that touches nothing classifiable) yields
    ``(unclassified,)`` — a dimension is never left with zero values."""
    _require(
        isinstance(paths, (list, tuple, set, frozenset)),
        "affected_surface: paths must be a list of strings",
    )
    surfaces = {classify_affected_surface(p) for p in paths}
    surfaces.discard(UNCLASSIFIED)
    if not surfaces:
        return (UNCLASSIFIED,)
    return tuple(sorted(surfaces))


def _validate_dimension_values(dim: str, values: Any, allowed: frozenset[str]) -> tuple[str, ...]:
    _require(
        isinstance(values, list) and bool(values),
        f"taxonomy.{dim}: must be a non-empty list",
    )
    _require(
        all(isinstance(v, str) for v in values),
        f"taxonomy.{dim}: every value must be a string",
    )
    bad = sorted(v for v in values if v not in allowed)
    _require(not bad, f"taxonomy.{dim}: unknown value(s) {bad}")
    _require(len(set(values)) == len(values), f"taxonomy.{dim}: duplicate value")
    return tuple(values)


def validate_taxonomy(raw: Any) -> dict[str, tuple[str, ...]]:
    """Fail-closed validation of a corpus case's ``metadata.taxonomy``.

    ``raw`` must be a mapping with **exactly** the four dimension keys,
    each a non-empty list of unique values drawn from that dimension's
    closed enum. Any violation raises :class:`TaxonomyError` — no partial
    acceptance, mirroring ``benchmark_fixture.py``'s ``_parse_metadata``.
    """
    _require(isinstance(raw, dict), "taxonomy: must be a mapping")
    unknown = sorted(set(raw) - DIMENSION_NAMES)
    _require(not unknown, f"taxonomy: unknown dimension(s) {unknown}")
    missing = sorted(DIMENSION_NAMES - set(raw))
    _require(not missing, f"taxonomy: missing dimension(s) {missing}")
    return {
        dim: _validate_dimension_values(dim, raw[dim], allowed)
        for dim, allowed in DIMENSIONS.items()
    }


def sanitize_taxonomy_response(raw: Any) -> dict[str, tuple[str, ...]]:
    """Fail-open-into-``unclassified`` validation of the model's raw
    PR-diff classification response.

    This is the one place adversarial/untrusted model output is accepted
    as input: a response that is not a mapping, carries an invented
    dimension key, an invented value, a non-list value, or is simply
    absent for a dimension is never rejected outright and never lets an
    invented key or value survive — the affected dimension silently
    resolves to ``(unclassified,)`` instead. This function never raises.
    """
    result: dict[str, tuple[str, ...]] = {}
    raw_map = raw if isinstance(raw, dict) else {}
    for dim, allowed in DIMENSIONS.items():
        values = raw_map.get(dim)
        cleaned: tuple[str, ...] = ()
        if isinstance(values, list):
            seen: list[str] = []
            for v in values:
                if isinstance(v, str) and v in allowed and v not in seen:
                    seen.append(v)
            cleaned = tuple(seen)
        result[dim] = cleaned if cleaned else (UNCLASSIFIED,)
    return result
