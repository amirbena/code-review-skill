#!/usr/bin/env python3
"""Test-only reference for the benchmark finding match criteria (Issue #54).

Test-only: not runtime logic, not packaged — the packaged Skills are
Markdown/YAML only. This module mirrors
``docs/benchmark/match-criteria.md``: the two match axes (location
correspondence, defect correspondence), the three-valued pairwise result
(MATCH / NEAR_MISS / NO_MATCH), and how the fixture format's
allowed-alternative constructs (``alternatives``, ``any_of``,
``match: optional``, ``severity`` lists) resolve into an entry outcome.

It is a *matcher*, not a metric: it decides pairing only. Counting misses
and false positives (#55), severity accuracy (#56), and duplicate noise
(#57) are downstream and out of scope, as is the cross-revision stable
finding identity relation (#42 / #59).

The contract is the *criteria and their determinism*; this module is one
executable projection so a test can prove every §8 worked example
classifies as documented and that two runs agree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from tests.reference import benchmark_fixture as bf
from tests.reference import benchmark_runner as br

# ── fixed tolerances (match-criteria.md §3, §4, §7) ───────────────────────
PROXIMITY_LINES = 3
CLAIM_CORRESPONDS_SIM = 0.5
CLAIM_RELATED_SIM = 0.25

_STOPWORDS = frozenset(
    {"the", "and", "that", "this", "from", "with", "into", "for", "not", "are", "was", "its", "has"}
)


class LocationMatch(Enum):
    EXACT = "exact"
    NEAR = "near"
    NONE = "none"


class DefectMatch(Enum):
    CORRESPONDS = "corresponds"
    RELATED = "related"
    UNRELATED = "unrelated"


class MatchResult(Enum):
    MATCH = "match"
    NEAR_MISS = "near_miss"
    NO_MATCH = "no_match"

    @property
    def rank(self) -> int:  # MATCH is best
        return {"match": 2, "near_miss": 1, "no_match": 0}[self.value]


# §5 combination table.
_COMBINE: dict[tuple[LocationMatch, DefectMatch], MatchResult] = {
    (LocationMatch.EXACT, DefectMatch.CORRESPONDS): MatchResult.MATCH,
    (LocationMatch.EXACT, DefectMatch.RELATED): MatchResult.NEAR_MISS,
    (LocationMatch.EXACT, DefectMatch.UNRELATED): MatchResult.NO_MATCH,
    (LocationMatch.NEAR, DefectMatch.CORRESPONDS): MatchResult.NEAR_MISS,
    (LocationMatch.NEAR, DefectMatch.RELATED): MatchResult.NEAR_MISS,
    (LocationMatch.NEAR, DefectMatch.UNRELATED): MatchResult.NO_MATCH,
    (LocationMatch.NONE, DefectMatch.CORRESPONDS): MatchResult.NO_MATCH,
    (LocationMatch.NONE, DefectMatch.RELATED): MatchResult.NO_MATCH,
    (LocationMatch.NONE, DefectMatch.UNRELATED): MatchResult.NO_MATCH,
}


# ── normalized descriptors ───────────────────────────────────────────────


def _norm_path(path: str) -> str:
    p = path.replace("\\", "/").strip()
    return p[2:] if p.startswith("./") else p


def _claim_tokens(claim: str | None) -> frozenset[str]:
    if not claim:
        return frozenset()
    raw = re.split(r"[^0-9a-zA-Z]+", claim.lower())
    return frozenset(t for t in raw if len(t) > 2 and t not in _STOPWORDS)


def _line_span(value: Any) -> tuple[int, int] | None:
    """Accept {'start','end'} | {'line': n} | int | [a, b]."""
    if isinstance(value, Mapping):
        if "start" in value and "end" in value:
            return int(value["start"]), int(value["end"])
        if "line" in value:
            n = int(value["line"])
            return n, n
        return None
    if isinstance(value, int):
        return value, value
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    return None


@dataclass(frozen=True)
class Descriptor:
    """The subset of a finding's location/defect fields the criteria read."""

    intent: str | None
    path: str | None
    symbol: str | None
    anchor: str | None
    lines: tuple[int, int] | None
    defect_kind: str | None
    claim: str | None

    @staticmethod
    def from_expected(entry_or_spec: Any) -> "Descriptor":
        """From a bf.ExpectedFinding (single spec) or a plain sub-spec dict."""
        if isinstance(entry_or_spec, bf.ExpectedFinding):
            loc = entry_or_spec.location or {}
            claim = entry_or_spec.claim
            defect_kind = entry_or_spec.defect_kind
        else:  # sub-spec dict from _subspecs()
            loc = entry_or_spec.get("location") or {}
            claim = entry_or_spec.get("claim")
            defect_kind = entry_or_spec.get("defect_kind")
        return Descriptor(
            intent=loc.get("location_intent"),
            path=_norm_path(loc["path"]) if loc.get("path") else None,
            symbol=loc.get("symbol"),
            anchor=loc.get("anchor"),
            lines=_line_span(loc.get("lines")),
            defect_kind=defect_kind,
            claim=claim,
        )

    @staticmethod
    def from_produced(finding: br.ProducedFinding) -> "Descriptor":
        loc = finding.location
        extra = dict(finding.extra or {})
        path = symbol = anchor = intent = None
        lines = None
        if isinstance(loc, Mapping):
            intent = loc.get("location_intent")
            if loc.get("path"):
                path = _norm_path(str(loc["path"]))
            symbol = loc.get("symbol")
            anchor = loc.get("anchor")
            lines = _line_span(loc.get("lines")) or _line_span(loc.get("line"))
        elif isinstance(loc, str) and loc.strip():
            # "path:line" or "path" — best effort, never invents a path
            head = loc.split(":", 1)[0].strip()
            if "/" in head or head.endswith(".py") or head.endswith(".md"):
                path = _norm_path(head)
        return Descriptor(
            intent=intent or extra.get("location_intent"),
            path=path or (extra.get("path") and _norm_path(str(extra["path"]))) or None,
            symbol=symbol or extra.get("symbol"),
            anchor=anchor or extra.get("anchor"),
            lines=lines or _line_span(extra.get("lines")) or _line_span(extra.get("line")),
            defect_kind=extra.get("defect_kind"),
            claim=finding.claim,
        )


# ── the two axes (match-criteria.md §3, §4) ──────────────────────────────


def _within_window(a: tuple[int, int], b: tuple[int, int], window: int) -> bool:
    """Ranges overlap, or their nearest endpoints are <= window apart."""
    if a[0] <= b[1] and b[0] <= a[1]:
        return True
    gap = b[0] - a[1] if b[0] > a[1] else a[0] - b[1]
    return gap <= window


def location_match(expected: Descriptor, produced: Descriptor, *, post_image: str | None = None) -> LocationMatch:
    if expected.intent == "repository":
        return LocationMatch.EXACT if not produced.path else LocationMatch.NEAR
    if not expected.path:  # non-repository intent must carry a path (fixture-format §8.3)
        return LocationMatch.NEAR if produced.path else LocationMatch.NONE
    if not produced.path:
        return LocationMatch.NONE
    if produced.path != expected.path:
        return LocationMatch.NONE

    # same path — apply the finer signals in the documented order
    if expected.symbol and produced.symbol and expected.symbol != produced.symbol:
        return LocationMatch.NEAR
    if expected.anchor and post_image is not None and produced.lines is not None:
        if not _anchor_near(expected.anchor, post_image, produced.lines):
            return LocationMatch.NEAR
    if expected.lines is not None and produced.lines is not None:
        if not _within_window(expected.lines, produced.lines, PROXIMITY_LINES):
            return LocationMatch.NEAR
    return LocationMatch.EXACT


def _anchor_near(anchor: str, post_image: str, produced_lines: tuple[int, int]) -> bool:
    rows = post_image.splitlines()
    lo = max(1, produced_lines[0] - PROXIMITY_LINES)
    hi = min(len(rows), produced_lines[1] + PROXIMITY_LINES)
    return any(anchor in rows[i - 1] for i in range(lo, hi + 1))


def defect_match(expected: Descriptor, produced: Descriptor) -> DefectMatch:
    if expected.defect_kind and produced.defect_kind:
        return (
            DefectMatch.CORRESPONDS
            if expected.defect_kind == produced.defect_kind
            else DefectMatch.UNRELATED
        )
    e, p = _claim_tokens(expected.claim), _claim_tokens(produced.claim)
    if not e or not p:
        return DefectMatch.UNRELATED
    if e <= p or p <= e:
        return DefectMatch.CORRESPONDS
    sim = len(e & p) / len(e | p)
    if sim >= CLAIM_CORRESPONDS_SIM:
        return DefectMatch.CORRESPONDS
    if sim >= CLAIM_RELATED_SIM:
        return DefectMatch.RELATED
    return DefectMatch.UNRELATED


# ── pairwise + entry-level API (match-criteria.md §5, §6) ────────────────


@dataclass(frozen=True)
class PairOutcome:
    result: MatchResult
    location: LocationMatch
    defect: DefectMatch

    def as_dict(self) -> dict[str, str]:
        return {"result": self.result.value, "location": self.location.value, "defect": self.defect.value}


def match_pair(
    expected_spec: Any, produced: br.ProducedFinding, *, post_image: str | None = None
) -> PairOutcome:
    """One produced finding vs one expected spec (a bf.ExpectedFinding
    single spec, or a sub-spec dict)."""
    e = Descriptor.from_expected(expected_spec)
    p = Descriptor.from_produced(produced)
    loc = location_match(e, p, post_image=post_image)
    dfx = defect_match(e, p)
    return PairOutcome(_COMBINE[(loc, dfx)], loc, dfx)


def _subspecs(entry: bf.ExpectedFinding) -> list[dict[str, Any]]:
    """Primary spec plus one variant per `alternatives` entry, each variant
    the primary with the alternative's narrowed fields substituted in
    (match-criteria.md §6)."""
    primary = {"location": entry.location, "claim": entry.claim, "defect_kind": entry.defect_kind}
    specs = [primary]
    for alt in entry.alternatives:
        merged = dict(primary)
        for k in ("location", "claim", "defect_kind"):
            if k in alt and alt[k] is not None:
                merged[k] = alt[k]
        specs.append(merged)
    return specs


@dataclass(frozen=True)
class EntryOutcome:
    key: str
    required: bool
    result: MatchResult
    produced_index: int | None          # which produced finding achieved `result`
    via: str | None                     # "primary" | "alternative:<n>" | "any_of:<member key>"
    member_results: Mapping[str, MatchResult] = field(default_factory=dict)  # any_of only

    @property
    def is_missed_required(self) -> bool:
        """A `required` entry with no MATCH. #55 owns turning this into a
        count; it is exposed here only as a convenience predicate."""
        return self.required and self.result is not MatchResult.MATCH

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "key": self.key,
            "required": self.required,
            "result": self.result.value,
            "produced_index": self.produced_index,
            "via": self.via,
        }
        if self.member_results:
            out["member_results"] = {k: v.value for k, v in sorted(self.member_results.items())}
        return out


def evaluate_entry(
    entry: bf.ExpectedFinding,
    produced_findings: Sequence[br.ProducedFinding],
    *,
    post_image: str | None = None,
) -> EntryOutcome:
    """Best pairwise result for a whole `expected.findings` entry, resolving
    `alternatives` / `any_of` and carrying the `required` flag through
    (match-criteria.md §6)."""
    best = MatchResult.NO_MATCH
    best_idx: int | None = None
    best_via: str | None = None
    member_results: dict[str, MatchResult] = {}

    if entry.is_any_of:
        for member in entry.members:
            sub = evaluate_entry(member, produced_findings, post_image=post_image)
            member_results[member.key] = sub.result
            if _beats(sub.result, sub.produced_index, best, best_idx):
                best, best_idx, best_via = sub.result, sub.produced_index, f"any_of:{member.key}"
    else:
        for spec_n, spec in enumerate(_subspecs(entry)):
            via = "primary" if spec_n == 0 else f"alternative:{spec_n - 1}"
            for idx, produced in enumerate(produced_findings):
                outcome = match_pair(spec, produced, post_image=post_image)
                if _beats(outcome.result, idx, best, best_idx):
                    best, best_idx, best_via = outcome.result, idx, via

    return EntryOutcome(
        key=entry.key,
        required=entry.required,
        result=best,
        produced_index=best_idx if best is not MatchResult.NO_MATCH else None,
        via=best_via if best is not MatchResult.NO_MATCH else None,
        member_results=member_results,
    )


def _beats(
    result: MatchResult, idx: int | None, best: MatchResult, best_idx: int | None
) -> bool:
    """Higher rank wins; on a tie the lower produced index wins
    (deterministic tie-break, match-criteria.md §7)."""
    if result.rank != best.rank:
        return result.rank > best.rank
    if result is MatchResult.NO_MATCH:
        return False
    if best_idx is None:
        return idx is not None
    return idx is not None and idx < best_idx
