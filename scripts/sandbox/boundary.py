"""Request/result types for a sandboxed run.

Outcome vocabulary matches shared/policies/runtime-validation.md exactly
(executed / failed / skipped / unavailable) so a caller can carry a
SandboxResult straight into a Validation-section entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Outcome(Enum):
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SandboxLimits:
    wall_clock_seconds: float = 120.0
    cpu_seconds: int = 60
    memory_bytes: int = 1_536 * 1024 * 1024
    max_processes: int = 64
    max_output_bytes: int = 1_000_000
    max_filesystem_growth_bytes: int = 512 * 1024 * 1024


@dataclass(frozen=True)
class SandboxRequest:
    """One explicitly admitted validation command/reproduction.

    ``source_dir`` is the bounded reviewed work copy; it is never opened by
    the sandboxed process directly — the runner works on a disposable copy
    of it. ``read_only_inputs`` are additional host paths explicitly
    required by the command and exposed read-only only.
    """

    argv: tuple[str, ...]
    source_dir: Path
    read_only_inputs: tuple[Path, ...] = ()
    cwd_relative: str = "."
    limits: SandboxLimits = field(default_factory=SandboxLimits)


@dataclass(frozen=True)
class SandboxResult:
    outcome: Outcome
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    reason: str = ""
    duration_seconds: float = 0.0
    primitive: str = ""
    source_integrity_verified: bool = False
    output_truncated: bool = False

    @property
    def evidence(self) -> str:
        return self.stdout if self.outcome is Outcome.EXECUTED else self.stderr
