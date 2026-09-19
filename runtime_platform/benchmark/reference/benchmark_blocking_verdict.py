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
    UNRECOGNIZED = "unrecognized"


# Local (`REVIEW CLEAN` / `CHANGES REQUIRED`), GitHub (`Approve` / `Request
# Changes`, `APPROVE` / `REQUEST_CHANGES`) and Result-line (`Changes
# Requested`) wordings, matched after lowercasing and stripping punctuation.
_BLOCKING_RE = re.compile(r"\bchanges (required|requested)\b|\brequest(ed)? changes\b")
_CLEAN_RE = re.compile(r"\bclean\b|\bapprove[ds]?\b")
_INCOMPLETE_RE = re.compile(r"\bincomplete\b")

_KIND_PATTERNS = (
    (RenderedKind.BLOCKING, _BLOCKING_RE),
    (RenderedKind.CLEAN, _CLEAN_RE),
    (RenderedKind.INCOMPLETE, _INCOMPLETE_RE),
)


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
) -> BlockingVerdictCheck:
    """When any produced severity is P0/P1, both the Result and the Decision
    must render the blocking value. Vacuously ok otherwise — callers that
    need the check exercised assert ``blocking_produced`` themselves."""
    findings = tuple(ds.Finding(id=str(i), severity=ds.Severity(s)) for i, s in enumerate(severities))
    if ds.derive_decision(findings) is ds.Decision.CLEAN:
        return BlockingVerdictCheck(blocking_produced=False, violations=())

    violations = []
    for surface, label in (("Result", result_label), ("Decision", decision_label)):
        kind = classify_rendered_label(label)
        if kind is not RenderedKind.BLOCKING:
            violations.append(
                f"{surface} rendered {kind.value} ({label!r}) although a P0/P1 finding was produced"
            )
    return BlockingVerdictCheck(blocking_produced=True, violations=tuple(violations))
