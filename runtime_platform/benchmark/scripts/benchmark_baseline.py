#!/usr/bin/env python3
"""Read-only access to a lane's pinned baseline on `benchmark-history`.

Contract: `runtime_platform/benchmark/scheduled-operations/canonical-result-and-persistence.md` §5.
Only git reads (`ls-remote`, `fetch`, `show`); never writes to GitHub.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts import benchmark_result as res  # noqa: E402

HISTORY_BRANCH = "benchmark-history"
GIT_TIMEOUT_S = 120
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class BaselineError(RuntimeError):
    """The history could not be read (unreachable, or a read failed)."""


class HistorySource(Protocol):
    def read_text(self, path: str) -> str | None:
        """File content at a history-relative path, or None when it does not exist."""


class DirectoryHistory:
    """A local checkout of `benchmark-history`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def read_text(self, path: str) -> str | None:
        target = self.root / path
        return target.read_text(encoding="utf-8") if target.is_file() else None


class GitRefHistory:
    """`benchmark-history` on a remote, fetched read-only through the checkout's own git."""

    def __init__(self, repo_root: Path, remote: str = "origin", branch: str = HISTORY_BRANCH) -> None:
        self.repo_root, self.remote, self.branch = repo_root, remote, branch
        self._tip: str | None | bool = False  # False = not resolved yet

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                timeout=GIT_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired as exc:
            raise BaselineError(f"git {' '.join(args)} timed out after {GIT_TIMEOUT_S}s") from exc

    def _resolve_tip(self) -> str | None:
        ref = f"refs/heads/{self.branch}"
        listing = self._git("ls-remote", self.remote, ref)
        if listing.returncode != 0:
            raise BaselineError(f"cannot list {self.remote} {ref}: {listing.stderr.strip()}")
        if not listing.stdout.strip():
            return None
        fetched = self._git("fetch", "--no-tags", "--quiet", self.remote, ref)
        if fetched.returncode != 0:
            raise BaselineError(f"cannot fetch {self.remote} {ref}: {fetched.stderr.strip()}")
        return self._git("rev-parse", "FETCH_HEAD").stdout.strip()

    def read_text(self, path: str) -> str | None:
        if self._tip is False:
            self._tip = self._resolve_tip()
        if self._tip is None:
            return None
        spec = f"{self._tip}:{path}"
        if self._git("cat-file", "-e", spec).returncode != 0:
            return None
        shown = self._git("show", spec)
        if shown.returncode != 0:
            raise BaselineError(f"cannot read {spec}: {shown.stderr.strip()}")
        return shown.stdout


@dataclass(frozen=True)
class BaselineLookup:
    """`bootstrap` (no pointer), `compared` (usable record), or `incomparable` (unusable, with a reason)."""

    state: str
    record: dict[str, Any] | None = None
    reason: str | None = None


def _incomparable(reason: str) -> BaselineLookup:
    return BaselineLookup("incomparable", reason=reason)


def _safe_relative(path: object) -> bool:
    return isinstance(path, str) and bool(path) and not PurePosixPath(path).is_absolute() and ".." not in PurePosixPath(path).parts


def load_baseline(source: HistorySource, lane: str) -> BaselineLookup:
    """The lane's pinned baseline record, verified; anything unusable is `incomparable`, never a guess."""
    try:
        pointer_text = source.read_text(f"baselines/{lane}.json")
        if pointer_text is None:
            return BaselineLookup("bootstrap")
        pointer = json.loads(pointer_text)
        if not isinstance(pointer, dict) or not _safe_relative(pointer.get("record_path")):
            return _incomparable("baseline pointer is malformed")
        if pointer.get("lane") != lane:
            return _incomparable(f"lane-identity mismatch: pointer names lane {pointer.get('lane')!r}, not {lane!r}")
        if not isinstance(pointer.get("record_sha256"), str) or not _SHA256_RE.match(pointer["record_sha256"]):
            return _incomparable("baseline pointer has no valid record_sha256")
        record_text = source.read_text(pointer["record_path"])
        if record_text is None:
            return _incomparable(f"baseline record {pointer['record_path']} is missing")
        record = json.loads(record_text)
    except BaselineError as exc:
        return _incomparable(f"baseline history unreachable: {exc}")
    except (json.JSONDecodeError, OSError) as exc:
        return _incomparable(f"baseline is unreadable: {exc}")

    errors = res.validate_record(record)
    if errors:
        return _incomparable(f"baseline record is invalid: {errors[0]}")
    if record["content_sha256"] != pointer["record_sha256"] or record["run_id"] != pointer.get("run_id"):
        return _incomparable("baseline record does not match its pointer")
    if record["lane"] != lane:
        return _incomparable(f"lane-identity mismatch: baseline record is lane {record['lane']!r}, not {lane!r}")
    return BaselineLookup("compared", record=record)
