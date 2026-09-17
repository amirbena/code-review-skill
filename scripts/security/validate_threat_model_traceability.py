#!/usr/bin/env python3
"""Threat-scenario traceability validator (Issue #310).

Cross-references the canonical `#300` threat-scenario catalog
(`docs/threat-model/catalog/*.yaml`, parsed by `validate_threat_model.py`)
against the benchmark corpora that claim to exercise it —
`tests/reference/benchmark/mutation_fixtures.py` (#305),
`tests/reference/benchmark/delegation_fixtures.py` (#307),
`tests/reference/benchmark/security_event_fixtures.py` (#308), and the
`## Coverage` table in
`docs/benchmark/corpus/sandbox-adversarial/README.md` (#306, a real-runner
suite with no data-driven fixture module) — and reports a compact
per-scenario coverage-state rollup: `covered`, `partial`,
`not-applicable-to-benchmark`, or `gap`.

This module deliberately consumes rather than duplicates: the catalog
schema/parser is owned by `validate_threat_model.py`, and each benchmark
family's actual case data lives in its own corpus. Nothing here redefines
a scenario, a benchmark case, or an enforcement/regression reference — it
only computes a derived rollup and detects drift between the two sides:

- a benchmark corpus case citing a `threat_scenario_ids` entry that does
  not exist in the catalog (a stale/nonexistent scenario id reference);
- a catalog scenario declaring a `benchmark_family` that no case in that
  family's corpus actually references back (a claimed-but-missing
  benchmark case reference — #310's "no silent covered by design");
- a `CRITICAL`/`HIGH` scenario left `gap` or `partial` with no `notes`
  rationale explaining why (the compact traceability layer #310 asks for
  a "short rationale for `partial` / `not-applicable` / `gap`" on).

`coverage_state` is always *derived* from the catalog's own required
reference fields (`enforcement_owner`, `benchmark_reference`,
`regression_evidence`), never stored as a separate YAML field: storing it
separately would create a second, driftable copy of information the
catalog schema already requires every scenario to carry, exactly what
`#310`'s guardrails forbid ("no silent `covered by design`
classification without executable evidence"). A newly added scenario
therefore cannot lack a coverage classification: the existing
`validate_threat_model.py` schema already requires the underlying fields,
and this script derives and prints the classification for every scenario
on every run.

Usage::

    python3 scripts/security/validate_threat_model_traceability.py
    python3 scripts/security/validate_threat_model_traceability.py --scenario AUTH-001

or through the test suite:
`python3 -m unittest tests.unit.security.test_validate_threat_model_traceability`.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.security import validate_threat_model as vtm  # noqa: E402
from tests.reference.benchmark import delegation_fixtures as deleg_fixtures  # noqa: E402
from tests.reference.benchmark import mutation_fixtures as mut_fixtures  # noqa: E402
from tests.reference.benchmark import security_event_fixtures as sec_fixtures  # noqa: E402

GAP = vtm.GAP

COVERAGE_STATES: frozenset[str] = frozenset(
    {"covered", "partial", "not-applicable-to-benchmark", "gap"}
)

# Scenarios at this severity may not sit at `gap`/`partial` without a `notes`
# rationale explaining why — the same "high-impact gaps stay visible" bar #310
# sets. `not-applicable-to-benchmark` is exempt: its rationale already lives in
# `benchmark_reference`, required non-`COVERAGE_GAP` text by the catalog schema
# itself whenever `benchmark_family` is `none`.
_RATIONALE_REQUIRED_SEVERITIES: frozenset[str] = frozenset({"CRITICAL", "HIGH"})

_DEFAULT_SANDBOX_README = (
    REPO_ROOT / "docs" / "benchmark" / "corpus" / "sandbox-adversarial" / "README.md"
)
_SBOX_ID_RE = re.compile(r"\bSBOX-\d{3}\b")


class TraceabilityError(ValueError):
    """A drift between the catalog and a benchmark corpus, or an unrationalized gap."""


def sandbox_readme_scenario_ids(readme_path: Path = _DEFAULT_SANDBOX_README) -> frozenset[str]:
    """`SBOX-###` ids the #306 real-runner suite's own `## Coverage` table claims.

    #306 has no `benchmark-case/v2`-shaped fixture module (see that README's "Why
    this isn't a benchmark-case/v2 corpus"): the maintained coverage table is the
    only structured pointer from `SBOX-###` ids to real test methods. Only the
    `## Coverage` table is scanned, not the whole document, so an incidental
    `SBOX-###` mention in prose elsewhere in the file can't manufacture coverage.
    """
    text = readme_path.read_text(encoding="utf-8")
    marker = "## Coverage"
    if marker not in text:
        raise TraceabilityError(f"{readme_path}: no {marker!r} section found")
    table_text = text[text.index(marker):]
    next_heading = table_text.find("\n## ", len(marker))
    if next_heading != -1:
        table_text = table_text[:next_heading]
    return frozenset(_SBOX_ID_RE.findall(table_text))


_SCENARIO_ID_RE = re.compile(r"^[A-Z]+-\d{3}$")


def _corpus_scenario_ids(cases) -> frozenset[str]:
    """Real `<CATEGORY>-###` scenario ids a corpus's cases cite.

    A `threat_scenario_ids` entry may also be an `existing:<policy-path>`
    citation (`security_event_fixtures.py`'s own `_is_valid_threat_reference`
    allows this "no catalog scenario exists yet" escape hatch) — that is not a
    scenario id and must never be compared against the catalog's id set.
    """
    ids: set[str] = set()
    for case in cases:
        ids.update(tid for tid in case.threat_scenario_ids if _SCENARIO_ID_RE.match(tid))
    return frozenset(ids)


def _family_corpus_ids() -> dict[str, frozenset[str]]:
    """Map each `benchmark_family` token to the scenario ids its real corpus cites."""
    return {
        "mutation/#305": _corpus_scenario_ids(mut_fixtures.ALL_CASES),
        "delegation/#307": _corpus_scenario_ids(deleg_fixtures.ALL_CASES),
        "security-event/#308": _corpus_scenario_ids(sec_fixtures.ALL_CASES),
        "sandbox/#306": sandbox_readme_scenario_ids(),
    }


def coverage_state(scenario: "vtm.ThreatScenario") -> str:
    """Derive the #310 rollup state from the catalog's own reference fields.

    Never stored — always recomputed from `enforcement_owner`,
    `benchmark_family`/`benchmark_reference`, and `regression_evidence`, the
    same fields `validate_threat_model.py` already requires every scenario to
    carry, so a scenario cannot end up with a stale or hand-typed rollup.
    """
    if scenario.enforcement_owner == GAP:
        return "gap"
    regression_ok = scenario.regression_evidence != GAP
    if scenario.benchmark_family == ("none",):
        return "not-applicable-to-benchmark" if regression_ok else "partial"
    benchmark_ok = scenario.benchmark_reference != GAP
    return "covered" if benchmark_ok and regression_ok else "partial"


@dataclass(frozen=True)
class TraceabilityRow:
    scenario_id: str
    title: str
    category: str
    threat_severity: str
    coverage_state: str
    enforcement_owner: str
    benchmark_family: tuple[str, ...]
    regression_evidence: str
    rationale: str


def build_traceability(
    scenarios: list["vtm.ThreatScenario"],
    *,
    family_corpus_ids: dict[str, frozenset[str]] | None = None,
) -> tuple[list[TraceabilityRow], list[str]]:
    """Compute the per-scenario rollup and collect every drift finding.

    Returns `(rows, drift)`. `drift` is empty exactly when every declared
    benchmark claim is backed by a real corpus case, every corpus case points
    at a real scenario id, and every unrationalized high-severity gap/partial
    carries a `notes` explanation.
    """
    if family_corpus_ids is None:
        family_corpus_ids = _family_corpus_ids()

    catalog_ids = {sc.id for sc in scenarios}
    drift: list[str] = []

    for family, corpus_ids in sorted(family_corpus_ids.items()):
        for stale_id in sorted(corpus_ids - catalog_ids):
            drift.append(
                f"stale scenario id {stale_id!r}: referenced by the {family!r} benchmark corpus "
                "but absent from the threat-scenario catalog"
            )

    rows: list[TraceabilityRow] = []
    for sc in scenarios:
        state = coverage_state(sc)

        # Only a scenario that actually *claims* real benchmark coverage
        # (`benchmark_reference != COVERAGE_GAP`) can be cross-checked against
        # the corpus — a scenario that honestly declares `benchmark_family`
        # as its intended future owner while `benchmark_reference` is still
        # `COVERAGE_GAP` is not lying about existing coverage, so it is not
        # drift for that family's corpus not to reference it yet.
        if sc.benchmark_reference != GAP:
            for family in sc.benchmark_family:
                if family == "none":
                    continue
                corpus_ids = family_corpus_ids.get(family)
                if corpus_ids is None:
                    drift.append(
                        f"{sc.id}: declares benchmark_family {family!r}, which this validator does not "
                        "know how to cross-reference (add it to _family_corpus_ids)"
                    )
                elif sc.id not in corpus_ids:
                    drift.append(
                        f"{sc.id}: claims benchmark_reference {sc.benchmark_reference!r} under family "
                        f"{family!r} but no case in that corpus's threat_scenario_ids references this "
                        "scenario id back"
                    )

        if (
            state in ("gap", "partial")
            and sc.threat_severity in _RATIONALE_REQUIRED_SEVERITIES
            and not sc.notes.strip()
        ):
            drift.append(
                f"{sc.id}: {sc.threat_severity} severity scenario is {state!r} but carries no `notes` "
                "rationale explaining why (#310 requires a short rationale for partial/gap high-impact "
                "scenarios, never a silently absent one)"
            )

        rows.append(
            TraceabilityRow(
                scenario_id=sc.id,
                title=sc.title,
                category=sc.category,
                threat_severity=sc.threat_severity,
                coverage_state=state,
                enforcement_owner=sc.enforcement_owner,
                benchmark_family=sc.benchmark_family,
                regression_evidence=sc.regression_evidence,
                rationale=sc.notes.strip(),
            )
        )

    return rows, drift


def _default_catalog_dir() -> Path:
    return REPO_ROOT / "docs" / "threat-model" / "catalog"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-dir",
        type=Path,
        default=None,
        help="directory containing threat-scenario-catalog/v1 YAML files (default: docs/threat-model/catalog)",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="print only the traceability row for this scenario id (e.g. AUTH-001)",
    )
    args = parser.parse_args(argv)
    catalog_dir = args.catalog_dir or _default_catalog_dir()

    try:
        scenarios = vtm.load_catalog(catalog_dir)
        rows, drift = build_traceability(scenarios)
    except (vtm.ThreatModelFormatError, TraceabilityError) as exc:
        print(f"::error::threat-model traceability validation failed: {exc}", file=sys.stderr)
        return 1

    if args.scenario:
        rows = [r for r in rows if r.scenario_id == args.scenario]
        if not rows:
            print(f"::error::no scenario {args.scenario!r} in the catalog", file=sys.stderr)
            return 1

    by_state: dict[str, int] = {}
    for row in rows:
        by_state[row.coverage_state] = by_state.get(row.coverage_state, 0) + 1
        print(
            f"{row.scenario_id:10} {row.coverage_state:26} {row.threat_severity:8} {row.title}"
        )

    print()
    print(f"OK: {len(rows)} scenarios")
    for state in sorted(COVERAGE_STATES):
        print(f"  {state}: {by_state.get(state, 0)}")

    if drift:
        print(f"\n{len(drift)} traceability drift finding(s):", file=sys.stderr)
        for finding in drift:
            print(f"::error::{finding}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
