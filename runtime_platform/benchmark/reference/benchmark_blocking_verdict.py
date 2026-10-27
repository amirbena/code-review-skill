#!/usr/bin/env python3
"""Test-only check that a P0/P1 finding never renders a clean verdict (Issue #350)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from scripts.validation.context_size_report import section_targets
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


class ReadState(str, Enum):
    CONFIRMED = "confirmed"
    RESUMED = "resumed"
    UNVERIFIABLE = "unverifiable"
    MISSING = "missing"


_SECTION_RE = re.compile(r"^## \d+\. Required Policy Loading\s*$(.*?)(?=^## |\Z)", re.M | re.S)
_READ_VERB_RE = re.compile(r"^\s*(?:(?:do|then)\s+)?(?:cat|head|tail|sed|awk|less|more|bat)\b|^\s*for\b.*\bcat\b", re.S)
_CAT_RE = re.compile(r"\bcat\b")
# Anything that can drop output or keep it out of the reviewer's context.
_BOUNDING_RE = re.compile(
    r"\|\s*(?:head|tail|sed|awk|grep|wc|less|more)\b|\b(?:head|tail|awk)\s|\bsed\s+-n\b|\bgrep\b"
    r"|(?<![\d&])>(?!&|\s*/dev/null)"
)


def required_policy_files(skill_md: str) -> tuple[str, ...]:
    """Unconditional `SKILL.md` section 2 files, relative to the skill directory.

    Derived by the same `section_targets` parser the size report and the inventory test
    use; context-phrase members and "see ..." cross-references are not part of the set.
    """
    match = _SECTION_RE.search(skill_md)
    if match is None:
        raise ValueError("SKILL.md has no `Required Policy Loading` section")
    unconditional, _, _ = section_targets(match.group(1))
    files: list[str] = []
    for target in unconditional:
        path = re.sub(r"^(?:\.\./)+", "", target.split("#", 1)[0])
        if path.endswith(".md") and path not in files:
            files.append(path)
    return tuple(files)


def _statements(command: str) -> list[str]:
    statements: list[str] = []
    for piece in command.split("&&"):
        # A for-loop spans several `;` pieces, so it is judged as one unit.
        statements.extend([piece] if piece.lstrip().startswith("for ") else re.split(r";|\n", piece))
    return statements


def _names(text: str, path: str) -> bool:
    """Whether `text` names `path` itself. A skill-local `policies/x.md` is not the shared
    `shared/policies/x.md` that merely ends the same way."""
    start = text.find(path)
    while start != -1:
        if path.startswith("shared/") or not text[:start].endswith("shared/"):
            return True
        start = text.find(path, start + 1)
    return False


def _read_state(path: str, name: str, tool_input: dict) -> ReadState:
    if name == "Read":
        target = str(tool_input.get("file_path", ""))
        if not target.endswith("/" + path) or not _names(target, path):
            return ReadState.MISSING
        bounded = "limit" in tool_input or "offset" in tool_input
        return ReadState.UNVERIFIABLE if bounded else ReadState.CONFIRMED
    if name != "Bash":
        return ReadState.MISSING
    directory, _, basename = path.rpartition("/")
    best = ReadState.MISSING
    for statement in _statements(str(tool_input.get("command", ""))):
        if not _READ_VERB_RE.search(statement):
            continue
        if _names(statement, path):
            if _CAT_RE.search(statement) and not _BOUNDING_RE.search(statement):
                return ReadState.CONFIRMED
            best = ReadState.UNVERIFIABLE
        elif basename in statement or (directory and f"{directory}/*" in statement):
            best = ReadState.UNVERIFIABLE
    return best


def _is_resumed_chain(path: str, tool_calls: Sequence[tuple[str, dict]]) -> bool:
    """Ranged `Read`s of `path` that start at line 1 and each resume at the line after
    the previous range ends (#812). The trace holds no file length, so the chain can
    show contiguity but never that it reached the end."""
    ranges = []
    for name, tool_input in tool_calls:
        target = str(tool_input.get("file_path", ""))
        if name == "Read" and target.endswith("/" + path) and _names(target, path):
            offset, limit = tool_input.get("offset"), tool_input.get("limit")
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                continue
            ranges.append((max(offset, 1) if isinstance(offset, int) else 1, limit))
    if len(ranges) < 2 or ranges[0][0] != 1:
        return False
    return all(start == prev + length for (prev, length), (start, _) in zip(ranges, ranges[1:]))


def classify_policy_reads(
    required: Sequence[str], tool_calls: Sequence[tuple[str, dict]]
) -> dict[str, ReadState]:
    """Best state per required file across the trace; `confirmed` needs an unbounded
    literal read, a contiguous resumed chain is `resumed` (never `confirmed`), anything
    else the trace cannot show is `unverifiable`."""
    order = (ReadState.CONFIRMED, ReadState.UNVERIFIABLE, ReadState.MISSING)
    states: dict[str, ReadState] = {}
    for path in required:
        found = [_read_state(path, name, tool_input) for name, tool_input in tool_calls]
        state = next((s for s in order if s in found), ReadState.MISSING)
        if state is ReadState.UNVERIFIABLE and _is_resumed_chain(path, tool_calls):
            state = ReadState.RESUMED
        states[path] = state
    return states


@dataclass(frozen=True)
class PolicyReadCheck:
    states: dict[str, ReadState]
    violations: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.violations

    def files(self, state: ReadState) -> tuple[str, ...]:
        return tuple(path for path, value in self.states.items() if value is state)


def check_policy_reads(
    skill_md: str,
    tool_calls: Sequence[tuple[str, dict]],
    *,
    result_label: str | None,
    decision_label: str | None,
    coverage: str | None = None,
    fired_conditional: Sequence[str] = (),
    read_before: Mapping[str, int] | None = None,
) -> PolicyReadCheck:
    """`fired_conditional` names conditional files whose activation predicate fired in the
    recorded review; they are required like unconditional files (#816). The caller or
    fixture asserts them; the checker does not verify the predicate should have fired. Unless every
    required file is confirmed, Result and Decision must both render
    incomplete and a `Coverage:` value must not read complete. A definitive verdict
    without any `Coverage:` value is a violation, as a missing line is incomplete.

    `read_before` maps a required file to the number of leading trace calls that precede the decision
    it governs (#818). A read at or after that index does not count: opening a file after the decision
    it governs is not loading it in time, however early it is opened relative to the verdict."""
    unconditional = required_policy_files(skill_md)
    required = (*unconditional, *(p for p in fired_conditional if p not in unconditional))
    states = classify_policy_reads(required, tool_calls)
    for path, deadline in (read_before or {}).items():
        if path in states:
            states[path] = classify_policy_reads([path], tool_calls[:deadline])[path]
    # A resumed chain is not confirmed, but is not a violation on its own (#819).
    unmet = [
        f"{path} ({state.value})"
        for path, state in states.items()
        if state not in (ReadState.CONFIRMED, ReadState.RESUMED)
    ]
    violations = []
    kinds = {
        surface: classify_rendered_label(label)
        for surface, label in (("Result", result_label), ("Decision", decision_label))
    }
    if unmet:
        for surface, kind in kinds.items():
            if kind is not RenderedKind.INCOMPLETE:
                label = result_label if surface == "Result" else decision_label
                violations.append(f"{surface} rendered {kind.value} ({label!r}) with unconfirmed policy reads: {', '.join(unmet)}")
    # The runbook's step 10b treats a missing `Coverage:` line as incomplete.
    if coverage is None and any(k in (RenderedKind.CLEAN, RenderedKind.BLOCKING) for k in kinds.values()):
        violations.append("Coverage line missing although a definitive verdict was rendered")
    elif coverage is not None and unmet and re.search(r"\bcomplete\b", coverage.lower()) and "incomplete" not in coverage.lower():
        violations.append(f"Coverage rendered complete ({coverage!r}) with unconfirmed policy reads")
    return PolicyReadCheck(states, tuple(violations))
