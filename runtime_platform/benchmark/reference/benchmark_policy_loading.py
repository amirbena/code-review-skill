#!/usr/bin/env python3
"""Test-only model of bounded, resumable policy loading (Issue #812)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping, Sequence

# (path, first_line, max_lines) -> the lines the runtime delivered; max_lines None means "to the end".
Reader = Callable[[str, int, "int | None"], Sequence[str]]


class LoadState(str, Enum):
    LOADED = "loaded"
    UNRECOVERABLE = "unrecoverable"


@dataclass(frozen=True)
class Read:
    first_line: int
    max_lines: int | None
    delivered: int


@dataclass(frozen=True)
class FileLoad:
    path: str
    state: LoadState
    verified_through: int
    extent: int | None
    reads: tuple[Read, ...]
    reason: str = ""
    learned_bound: int | None = None

    @property
    def loaded(self) -> bool:
        return self.state is LoadState.LOADED

    @property
    def detail(self) -> str:
        of = f" of {self.extent}" if self.extent is not None else ""
        return f"{self.path} verified through line {self.verified_through}{of}: {self.reason}"


@dataclass(frozen=True)
class LoadReport:
    files: tuple[FileLoad, ...]
    incomplete_reasons: tuple[str, ...] = field(default=())

    @property
    def coverage(self) -> str:
        return "complete" if not self.incomplete_reasons else "incomplete"


def load_file(read: Reader, path: str, extent: int | None, bound: int | None = None) -> FileLoad:
    """Load one file, resuming from the verified line after any shortfall.

    `extent` is the independently obtained line count, or None to use an end-of-file probe.
    `bound` caps the first request; it is None until a read has been seen to fall short.
    """
    verified, reads, learned = 0, [], None
    request = bound

    def fail(reason: str) -> FileLoad:
        return FileLoad(path, LoadState.UNRECOVERABLE, verified, extent, tuple(reads), reason, learned)

    while True:
        outstanding = None if extent is None else extent - verified
        if outstanding == 0:
            return FileLoad(path, LoadState.LOADED, verified, extent, tuple(reads), learned_bound=learned)
        asked = request if outstanding is None else (outstanding if request is None else min(request, outstanding))
        lines = read(path, verified + 1, asked)
        delivered = len(lines)
        reads.append(Read(verified + 1, asked, delivered))
        if (asked is not None and delivered > asked) or (outstanding is not None and delivered > outstanding):
            return fail("lines received disagree with the extent")
        if extent is None and delivered == 0 and verified == 0:
            return fail("nothing was delivered, so end of file cannot be told from a failed read")
        if extent is None and delivered == 0:
            return FileLoad(path, LoadState.LOADED, verified, extent, tuple(reads), learned_bound=learned)
        if delivered == 0:
            if asked == 1:
                return fail("a single-line read from the verified position returned nothing")
            request = max(1, (asked or 2) // 2)
            continue
        verified += delivered
        if asked is None or delivered < asked:
            request = delivered if request is None else min(request, delivered)
            if extent is not None and verified < extent:
                learned = max(learned or 0, delivered)


def load_required(read: Reader, extents: Mapping[str, int | None]) -> LoadReport:
    """Load files in sequence; a bound learned from a shortfall carries to later files."""
    loads, bound = [], None
    for path, extent in extents.items():
        load = load_file(read, path, extent, bound)
        loads.append(load)
        if load.learned_bound is not None:
            bound = load.learned_bound if bound is None else min(bound, load.learned_bound)
    reasons = tuple(f.detail for f in loads if not f.loaded)
    return LoadReport(tuple(loads), reasons)
