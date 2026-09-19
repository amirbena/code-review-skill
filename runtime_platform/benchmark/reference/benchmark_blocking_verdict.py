#!/usr/bin/env python3
"""Test-only check that a P0/P1 finding never renders a clean verdict (Issue #350)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from tests.reference.review import decision_semantics as ds


class RenderedKind(str, Enum):
    CLEAN = "clean"
    BLOCKING = "blocking"
    INCOMPLETE = "incomplete"
    INFORMATIONAL = "informational"
    UNRECOGNIZED = "unrecognized"


# Local, GitHub (incl. `REQUEST_CHANGES` / `COMMENT` events) and Result-line
# wordings, matched after lowercasing and stripping punctuation.
_BLOCKING_RE = re.compile(r"\bchanges (required|requested)\b|\brequest(ed)? changes\b")
_CLEAN_RE = re.compile(r"\bclean\b|\bapprove[ds]?\b")
_INCOMPLETE_RE = re.compile(r"\bincomplete\b")
_INFORMATIONAL_RE = re.compile(r"\bcomment\b")

_KIND_PATTERNS = (
    (RenderedKind.BLOCKING, _BLOCKING_RE),
    (RenderedKind.CLEAN, _CLEAN_RE),
    (RenderedKind.INCOMPLETE, _INCOMPLETE_RE),
    (RenderedKind.INFORMATIONAL, _INFORMATIONAL_RE),
)

# Sanctioned outcomes that are neither clean nor the blocking value.
_NON_CLEAN_NON_BLOCKING = frozenset({RenderedKind.INCOMPLETE, RenderedKind.INFORMATIONAL})


def classify_rendered_label(label: str | None) -> RenderedKind:
    """A label matching zero or several kinds is UNRECOGNIZED, never a guess."""
    if label is None:
        return RenderedKind.UNRECOGNIZED
    normalized = re.sub(r"[^a-z]+", " ", label.lower()).strip()
    matched = [kind for kind, pattern in _KIND_PATTERNS if pattern.search(normalized)]
    return matched[0] if len(matched) == 1 else RenderedKind.UNRECOGNIZED


@dataclass(frozen=True)
class BlockingVerdictCheck:
    blocking_produced: bool
    violations: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.violations


def check_blocking_verdict(
    severities: Sequence[str],
    *,
    result_label: str | None,
    decision_label: str | None,
    require_blocking: bool = False,
) -> BlockingVerdictCheck:
    """Once a P0/P1 is produced neither surface may render clean; `require_blocking`
    demands the blocking value itself. Vacuously ok without a P0/P1."""
    findings = tuple(ds.Finding(id=str(i), severity=ds.Severity(s)) for i, s in enumerate(severities))
    if ds.derive_decision(findings) is ds.Decision.CLEAN:
        return BlockingVerdictCheck(blocking_produced=False, violations=())

    accepted = {RenderedKind.BLOCKING} if require_blocking else {RenderedKind.BLOCKING, *_NON_CLEAN_NON_BLOCKING}
    violations = []
    for surface, label in (("Result", result_label), ("Decision", decision_label)):
        kind = classify_rendered_label(label)
        if kind not in accepted:
            violations.append(
                f"{surface} rendered {kind.value} ({label!r}) although a P0/P1 finding was produced"
            )
    return BlockingVerdictCheck(blocking_produced=True, violations=tuple(violations))
