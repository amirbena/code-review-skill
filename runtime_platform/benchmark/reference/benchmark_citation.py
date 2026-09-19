#!/usr/bin/env python3
"""Test-only reference for the benchmark citation-existence check (Issue #349).

Test-only: not runtime logic, not packaged — the packaged Skills are
Markdown/YAML only. This module mirrors
``runtime_platform/benchmark/citation-fidelity.md``: for each produced
finding, whether the file/line/symbol it cites exists in the reviewed tree
and whether its quoted evidence appears near that location, reported per
case and in aggregate as its own metric category.

It is a *mechanical existence check*, not a matcher and not a grader: it
never reads a fixture's ``expected`` block, never pairs findings (#55),
never compares severity (#56) or clusters duplicates (#57), and never
proves a citation was *inspected* — existence only. Location fields are
read through the matcher's ``Descriptor.from_produced`` normalizer (#54)
so no second location parser exists; no match relation is evaluated. The
reviewed tree's file text is captured by the runner
(``CaseResult.cited_sources``) before workspace cleanup; this module is
pure over that captured text.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping, Sequence

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_match as bm
from runtime_platform.benchmark.reference import benchmark_runner as br

_EXECUTED = "executed"
_ERRORED = "errored"

# Per-finding statuses (citation-fidelity.md §3).
VERIFIED = "verified"
FABRICATED = "fabricated"
UNVERIFIABLE = "unverifiable"

# Fabrication reasons, in the fixed order they are reported (§3).
FILE_MISSING = "file-missing"
LINE_OUT_OF_RANGE = "line-out-of-range"
SYMBOL_ABSENT = "symbol-absent"
SNIPPET_ABSENT = "snippet-absent"

# Fixed tolerances (citation-fidelity.md §4), exact rationals like #54's.
SNIPPET_WINDOW_LINES = 10
SNIPPET_TOKEN_COVERAGE = Fraction(3, 4)
MIN_QUOTE_CHARS = 6

# A backticked span that is a `path:line[-line]` locator, not quoted code.
_LOCATOR_QUOTE_RE = re.compile(r":\d+(-\d+)?$")
# A symbol worth searching for: a bare identifier, optionally qualified
# (`Class.method`, `mod::fn`, `Cls#m`) and optionally called (`fn()`).
_IDENT_SYMBOL_RE = re.compile(r"^[A-Za-z_]\w*(?:(?:\.|::|#)[A-Za-z_]\w*)*(?:\(\))?$", re.ASCII)
_WORD_SPLIT_RE = re.compile(r"[^0-9A-Za-z_]+")


# ── the three checks (citation-fidelity.md §3, §4) ──────────────────────


def _symbol_leaf(symbol: str) -> str | None:
    """The identifier to search for, or ``None`` when ``symbol`` is a
    prose 'narrow section' (finding.md allows one) rather than code."""
    symbol = symbol.strip()
    if not _IDENT_SYMBOL_RE.match(symbol):
        return None
    return re.split(r"\.|::|#", symbol.removesuffix("()"))[-1]


def _quotes(finding: br.ProducedFinding) -> list[str]:
    """Quotable evidence spans: the finding's backticked ``Evidence`` spans
    minus ``path:line`` locators and trivially short spans (§4)."""
    raw = (finding.extra or {}).get("evidence_quotes") or ()
    kept = []
    for span in raw:
        squashed = "".join(str(span).split())
        if len(squashed) >= MIN_QUOTE_CHARS and not _LOCATOR_QUOTE_RE.search(squashed):
            kept.append(str(span))
    return kept


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD_SPLIT_RE.split(text) if t]


def _lcs_len(a: Sequence[str], b: Sequence[str]) -> int:
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def _quote_present(quote: str, window: str) -> bool:
    """Whitespace-insensitive substring, else in-order token coverage >= 3/4
    within one line-contiguous segment of the window (§4)."""
    if "".join(quote.split()) in "".join(window.split()):
        return True
    wanted = _tokens(quote)
    if not wanted:
        return False
    need = math.ceil(SNIPPET_TOKEN_COVERAGE * len(wanted))
    counts = Counter(wanted)
    rows = [_tokens(line) for line in window.splitlines()]
    span = len(quote.strip().splitlines()) or 1
    for start in range(max(len(rows) - span + 1, 1)):
        seg = [t for row in rows[start : start + span] for t in row]
        if sum((counts & Counter(seg)).values()) >= need and _lcs_len(wanted, seg) >= need:
            return True
    return False


def check_finding(
    finding: br.ProducedFinding,
    cited_sources: Mapping[str, str | None],
    pre_images: Mapping[str, str] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """``(status, reasons)`` for one produced finding (§3). ``reasons`` is
    non-empty exactly when the status is ``fabricated``."""
    path = br.cited_path(finding.location)
    if path is None or path not in cited_sources:
        # No cited file, or the runner could not decide its existence:
        # nothing checkable, never an existence claim (§3).
        return UNVERIFIABLE, ()
    pre = (pre_images or {}).get(path)
    text = cited_sources[path]
    if text is None:
        if pre is None:
            return FABRICATED, (FILE_MISSING,)
        text = pre  # deleted by the patch: it still existed in the reviewed change
    desc = bm.Descriptor.from_produced(finding)
    lines = text.splitlines()
    reasons: list[str] = []

    if desc.lines is not None and not (1 <= desc.lines[0] <= desc.lines[1] <= len(lines)):
        reasons.append(LINE_OUT_OF_RANGE)

    leaf = _symbol_leaf(desc.symbol) if desc.symbol else None
    if leaf is not None and leaf not in set(_WORD_SPLIT_RE.split(text)):
        reasons.append(SYMBOL_ABSENT)

    quotes = _quotes(finding)
    if quotes:
        in_range = desc.lines is not None and LINE_OUT_OF_RANGE not in reasons
        if in_range:
            lo = max(desc.lines[0] - 1 - SNIPPET_WINDOW_LINES, 0)
            window = "\n".join(lines[lo : desc.lines[1] + SNIPPET_WINDOW_LINES])
        else:
            window = text
        if not any(_quote_present(q, window) or (pre is not None and _quote_present(q, pre)) for q in quotes):
            reasons.append(SNIPPET_ABSENT)

    return (FABRICATED, tuple(reasons)) if reasons else (VERIFIED, ())


# ── per-case metric (citation-fidelity.md §5) ───────────────────────────


@dataclass(frozen=True)
class CaseCitationFidelity:
    id: str
    status: str  # "executed" | "errored"
    produced: int
    verified: int
    fabricated: int
    unverifiable: int
    fabricated_findings: tuple[dict[str, Any], ...]

    @property
    def fabrication_rate(self) -> Fraction | None:
        checkable = self.verified + self.fabricated
        return Fraction(self.fabricated, checkable) if checkable else None

    def as_dict(self) -> dict[str, Any]:
        rate = self.fabrication_rate
        return {
            "id": self.id,
            "status": self.status,
            "produced": self.produced,
            "verified": self.verified,
            "fabricated": self.fabricated,
            "unverifiable": self.unverifiable,
            "fabrication_rate": None if rate is None else str(rate),
            "fabricated_findings": [dict(f) for f in self.fabricated_findings],
        }


def compute_case_citation_fidelity(
    case: bf.BenchmarkCase, case_result: br.CaseResult
) -> CaseCitationFidelity:
    """Existence counts for one case (citation-fidelity.md §3–§5)."""
    if case_result.status != _EXECUTED:
        # §5: an errored case produced nothing — nothing to check.
        return CaseCitationFidelity(case.id, _ERRORED, 0, 0, 0, 0, ())

    verified = unverifiable = 0
    flagged: list[dict[str, Any]] = []
    for index, finding in enumerate(case_result.produced_findings):
        status, reasons = check_finding(finding, case_result.cited_sources, case_result.pre_images)
        if status == VERIFIED:
            verified += 1
        elif status == UNVERIFIABLE:
            unverifiable += 1
        else:
            flagged.append(
                {
                    "index": index,
                    "path": br.cited_path(finding.location),
                    "reasons": list(reasons),
                }
            )
    return CaseCitationFidelity(
        id=case.id,
        status=_EXECUTED,
        produced=len(case_result.produced_findings),
        verified=verified,
        fabricated=len(flagged),
        unverifiable=unverifiable,
        fabricated_findings=tuple(flagged),
    )


# ── aggregate (§5) ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AggregateCitationFidelity:
    total_produced: int
    total_verified: int
    total_fabricated: int
    total_unverifiable: int
    cases_with_fabricated_citations: int

    @property
    def fabrication_rate(self) -> Fraction | None:
        checkable = self.total_verified + self.total_fabricated
        return Fraction(self.total_fabricated, checkable) if checkable else None

    def as_dict(self) -> dict[str, Any]:
        rate = self.fabrication_rate
        return {
            "total_produced": self.total_produced,
            "total_verified": self.total_verified,
            "total_fabricated": self.total_fabricated,
            "total_unverifiable": self.total_unverifiable,
            "fabrication_rate": None if rate is None else str(rate),
            "cases_with_fabricated_citations": self.cases_with_fabricated_citations,
        }


def aggregate(cases: Sequence[CaseCitationFidelity]) -> AggregateCitationFidelity:
    """Sums only (§5) — the sole ratio is ``fabrication_rate``."""
    return AggregateCitationFidelity(
        total_produced=sum(c.produced for c in cases),
        total_verified=sum(c.verified for c in cases),
        total_fabricated=sum(c.fabricated for c in cases),
        total_unverifiable=sum(c.unverifiable for c in cases),
        cases_with_fabricated_citations=sum(1 for c in cases if c.fabricated > 0),
    )


@dataclass(frozen=True)
class RunCitationFidelity:
    per_case: tuple[CaseCitationFidelity, ...]
    aggregate: AggregateCitationFidelity

    def by_id(self) -> dict[str, CaseCitationFidelity]:
        return {c.id: c for c in self.per_case}

    def as_dict(self) -> dict[str, Any]:
        return {
            "cases": [c.as_dict() for c in sorted(self.per_case, key=lambda c: c.id)],
            "aggregate": self.aggregate.as_dict(),
        }


def compute_run_citation_fidelity(
    cases: Sequence[bf.BenchmarkCase],
    run: br.RunResult | Sequence[br.CaseResult],
) -> RunCitationFidelity:
    """Per-case + aggregate citation fidelity for a whole run. A case with
    no result is treated as errored (nothing produced)."""
    results = run.case_results if isinstance(run, br.RunResult) else tuple(run)
    result_by_id = {r.id: r for r in results}

    per_case: list[CaseCitationFidelity] = []
    for case in cases:
        result = result_by_id.get(case.id)
        if result is None:
            result = br.CaseResult(case.id, case.input_kind, "error", error="no-result-for-case")
        per_case.append(compute_case_citation_fidelity(case, result))
    return RunCitationFidelity(tuple(per_case), aggregate(per_case))


# ── rendering alongside the regression report (§6) ─────────────────────


def _delta_row(baseline: int, candidate: int) -> dict[str, int]:
    return {"baseline": baseline, "candidate": candidate, "delta": candidate - baseline}


def citation_fidelity_section(
    candidate: RunCitationFidelity,
    *,
    baseline: RunCitationFidelity | None = None,
) -> dict[str, Any]:
    """The optional ``citation_fidelity`` section rendered beside a run
    (citation-fidelity.md §6). Deterministic: cases ordered by ``id``.
    Never influences ``has_regressions`` or any match/severity outcome."""
    if baseline is None:
        return {"candidate": candidate.as_dict()}

    base_by_id = baseline.by_id()
    cand_by_id = candidate.by_id()
    common = sorted(set(base_by_id) & set(cand_by_id))
    ba, ca = baseline.aggregate, candidate.aggregate
    return {
        "candidate": candidate.as_dict(),
        "cases": [
            {
                "id": cid,
                "fabricated": _delta_row(base_by_id[cid].fabricated, cand_by_id[cid].fabricated),
            }
            for cid in common
        ],
        "aggregate": {
            "total_fabricated": _delta_row(ba.total_fabricated, ca.total_fabricated),
            "fabrication_rate": {
                "baseline": None if ba.fabrication_rate is None else str(ba.fabrication_rate),
                "candidate": None if ca.fabrication_rate is None else str(ca.fabrication_rate),
            },
        },
        "added_case_ids": sorted(set(cand_by_id) - set(base_by_id)),
        "removed_case_ids": sorted(set(base_by_id) - set(cand_by_id)),
    }
