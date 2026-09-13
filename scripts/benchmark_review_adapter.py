#!/usr/bin/env python3
"""Production reviewer adapter for the benchmark runner (Issue #250).

The benchmark runner (``tests/reference/benchmark/benchmark_runner.py``,
contract: ``docs/benchmark/runner-contract.md``) is built around a pluggable
``ReviewerAdapter`` — "a runtime reading a Skill, a recorded transcript, a
stub in tests" (runner-contract.md §1/§9). Every adapter that existed before
this module was a deterministic test stub. This module is the first
*production* adapter: it drives the real Claude Code CLI, non-interactively,
to actually invoke the packaged ``local-code-review`` Skill against the
isolated workspace the runner hands it, and normalizes the Skill's Markdown
report back into ``ProducedFinding`` objects.

Explicit-approval note (see ``skills/local-code-review/SKILL.md``, "Safety
boundaries"): that Skill must never be invoked automatically and requires
"fresh, explicit user approval scoped to that one run" for every invocation.
This adapter's prompt (``_REVIEW_PROMPT`` below) itself states that fresh,
scoped authorization for the one review it is requesting — this is a
repository-development/QA tool deliberately invoking the Skill once per
benchmark case on synthetic fixtures it constructed itself, not an
autonomous or hidden invocation against a real user's repository. This is a
factual reading of the existing policy, not a new policy decision.

Two independent failure modes matter here, and this module keeps them
distinct on purpose:

- **Runtime unavailable** (the configured CLI executable cannot be found at
  all) is a *run-level* configuration failure. It must be detected by a
  preflight check (:func:`check_runtime_available`) *before* the corpus, any
  workspace, or the matcher/metrics are touched — never surfaced as a
  per-case error, and never silently treated as "no findings" / a clean
  review.
- **A single case's review failing** (the CLI exits non-zero, or its stdout
  cannot be parsed as a review report at all) is exactly the kind of
  per-case failure ``run_case`` already handles by catching the adapter's
  exception and recording ``status: error`` / ``error:
  reviewer-adapter-raised`` (see ``benchmark_runner.run_case``). This module
  raises in both of those situations and lets that existing handling do its
  job — it does not duplicate or reimplement it.

Nothing here changes the ``ReviewerAdapter`` type or ``ProducedFinding``'s
fields; this module only ever returns
``tests.reference.benchmark.benchmark_runner.ProducedFinding`` instances.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from tests.reference.benchmark.benchmark_runner import ProducedFinding

# --------------------------------------------------------------------------
# Configuration (environment-overridable so this works across environments,
# and so tests can point it at a stub executable instead of the real CLI).
# --------------------------------------------------------------------------

CLI_ENV_VAR = "BENCHMARK_REVIEW_CLI"
CLI_ARGS_ENV_VAR = "BENCHMARK_REVIEW_CLI_ARGS"
DEFAULT_CLI = "claude"
DEFAULT_TIMEOUT_SECONDS = 300.0


class RuntimeUnavailableError(RuntimeError):
    """The configured review runtime executable could not be found.

    Raised only by the preflight check, before any corpus/workspace/case
    work happens — never raised mid-run and never caught by
    ``run_case``'s per-case ``reviewer-adapter-raised`` handling.
    """


def resolve_cli_executable(env: Mapping[str, str] | None = None) -> str:
    """The configured review CLI executable name/path.

    ``BENCHMARK_REVIEW_CLI`` overrides the default (``"claude"``, the
    Claude Code CLI) so this works in environments where the binary has a
    different name or path, without a code change.
    """
    env = env if env is not None else os.environ
    return env.get(CLI_ENV_VAR) or DEFAULT_CLI


def resolve_cli_extra_args(env: Mapping[str, str] | None = None) -> list[str]:
    """Extra CLI args from ``BENCHMARK_REVIEW_CLI_ARGS`` (shell-quoted),
    empty when unset."""
    env = env if env is not None else os.environ
    raw = env.get(CLI_ARGS_ENV_VAR, "")
    return shlex.split(raw) if raw.strip() else []


def check_runtime_available(executable: str | None = None) -> str:
    """Preflight check: is the review runtime actually usable?

    Returns the resolved absolute path when it is. Raises
    :class:`RuntimeUnavailableError` with an actionable message when it is
    not — the caller (the CLI entrypoint) must call this *before* touching
    the corpus, any workspace, or the matcher/metrics, and must exit
    non-zero on failure rather than running anything.
    """
    exe = executable or resolve_cli_executable()
    found = shutil.which(exe)
    if not found:
        raise RuntimeUnavailableError(
            f"review runtime executable {exe!r} was not found on PATH. "
            "Install Claude Code (https://claude.com/claude-code) so the "
            f"'{exe}' command is available, or point {CLI_ENV_VAR} at the "
            "correct executable name/path."
        )
    return found


# --------------------------------------------------------------------------
# The prompt that drives the real Skill invocation.
# --------------------------------------------------------------------------

_REVIEW_PROMPT = (
    "This is an explicit, single-purpose, repository-development benchmark "
    "invocation (see docs/benchmark/runner-contract.md) of the packaged "
    "local-code-review Skill, freshly authorized right now and scoped to "
    "this one run only — this message itself is that explicit approval, "
    "satisfying local-code-review's SKILL.md 'Safety boundaries' opt-in "
    "requirement. It is not an automatic or hidden invocation.\n\n"
    "Invoke the local-code-review Skill now to review the current Git "
    "delta (committed, staged, unstaged, and untracked changes) present in "
    "this workspace directory. Reply with only the Skill's finished "
    "Markdown review report and nothing else: no preamble, no commentary "
    "before or after it. The report must use the canonical full finding "
    "rendering for every finding — a `#### <id> [<severity>] <title>` "
    "heading immediately followed by a `- **Location:** "
    "`<path>:<line-or-range>`` line — and must end with the report's "
    "`**Result: ...**` verdict line."
)


# --------------------------------------------------------------------------
# Normalization: CLI stdout -> ProducedFinding objects.
# --------------------------------------------------------------------------

_VALID_SEVERITIES = {"P0", "P1", "P2"}

# `#### F1 [P2] Repository style convention violation` (or `###`, per
# shared/templates/finding-rendering.md, "Canonical full rendering" —
# local-code-review's own template uses `####`; both are accepted).
_HEADING_RE = re.compile(r"^#{3,4}\s+(?P<id>\S+)\s+\[(?P<severity>[^\]]+)\]\s+(?P<title>.+?)\s*$")

# `- **Location:** \`app/pagination.py:12\`` — an optional trailing
# annotation like `_(staged)_` may follow the backticked value; only the
# backticked value is used.
_LOCATION_RE = re.compile(r"^-\s*\*\*Location:\*\*\s*`(?P<loc>[^`]+)`")

# Any `**Result: ...**` line marks the output as a well-formed report (clean
# or not) — used to distinguish a genuinely clean/no-findings report from
# stdout that isn't a review report at all.
_RESULT_RE = re.compile(r"\*\*Result:", re.IGNORECASE)


def _parse_location(raw: str) -> dict:
    raw = raw.strip()
    if ":" not in raw:
        return {"path": raw}
    path, _, tail = raw.rpartition(":")
    tail = tail.strip()
    if "-" in tail:
        start_s, _, end_s = tail.partition("-")
        if start_s.strip().isdigit() and end_s.strip().isdigit():
            return {"path": path, "lines": {"start": int(start_s), "end": int(end_s)}}
        return {"path": raw}
    if tail.isdigit():
        return {"path": path, "line": int(tail)}
    return {"path": raw}


def parse_review_output(text: str) -> list[ProducedFinding]:
    """Pure normalizer: a review report's Markdown text -> ``ProducedFinding``
    objects.

    - A genuine clean/no-findings report (a ``**Result:**`` line, no finding
      headings) returns ``[]``.
    - A finding heading with an unrecognized severity token, or with no
      ``Location`` line found before the next heading, is skipped — a
      single anomalous finding never fails the whole parse.
    - Text that is not a review report at all (no ``**Result:**`` line and
      no recognizable finding headings) raises ``ValueError`` — the caller
      (the adapter) lets this propagate so the runner's existing per-case
      ``reviewer-adapter-raised`` handling takes over; it must never be
      swallowed into an empty/clean result.
    """
    lines = text.splitlines()
    has_result_line = any(_RESULT_RE.search(line) for line in lines)

    findings: list[ProducedFinding] = []
    n = len(lines)
    i = 0
    while i < n:
        heading = _HEADING_RE.match(lines[i])
        if heading:
            severity = heading.group("severity").strip().upper()
            title = heading.group("title").strip()
            location: dict | None = None
            j = i + 1
            while j < n and not _HEADING_RE.match(lines[j]):
                loc_match = _LOCATION_RE.match(lines[j].strip())
                if loc_match:
                    location = _parse_location(loc_match.group("loc"))
                    break
                j += 1
            if severity in _VALID_SEVERITIES and location is not None:
                findings.append(ProducedFinding(severity=severity, location=location, claim=title))
            # else: parse anomaly for this one finding — skip it, do not
            # fail the whole parse.
        i += 1

    if not findings and not has_result_line:
        raise ValueError(
            "could not parse a review report from the review CLI's output: "
            "no '**Result:**' line and no finding headings were found"
        )
    return findings


# --------------------------------------------------------------------------
# The adapter itself.
# --------------------------------------------------------------------------


class ProductionReviewerAdapter:
    """A ``ReviewerAdapter`` that drives a real runtime reading the packaged
    ``local-code-review`` Skill.

    Constructed with the executable, extra CLI args, timeout, and
    environment so all of them are injectable (a fake stub executable in
    tests, the real ``claude`` binary in production). Calling an instance
    with a workspace ``Path`` matches ``ReviewerAdapter`` exactly.
    """

    def __init__(
        self,
        *,
        executable: str | None = None,
        extra_args: Sequence[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.executable = executable or resolve_cli_executable(env)
        self.extra_args = list(extra_args) if extra_args is not None else resolve_cli_extra_args(env)
        self.timeout = timeout
        self.env = dict(env) if env is not None else dict(os.environ)

    def __call__(self, workspace: Path) -> list[ProducedFinding]:
        command = [
            self.executable,
            "-p",
            _REVIEW_PROMPT,
            "--output-format",
            "text",
            *self.extra_args,
        ]
        completed = subprocess.run(
            command,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=self.timeout,
            env=self.env,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"review CLI {self.executable!r} exited {completed.returncode}: "
                f"{completed.stderr.strip()[:2000]}"
            )
        return parse_review_output(completed.stdout)


def make_production_adapter(
    *,
    executable: str | None = None,
    extra_args: Sequence[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> ProductionReviewerAdapter:
    """Factory form of :class:`ProductionReviewerAdapter`."""
    return ProductionReviewerAdapter(executable=executable, extra_args=extra_args, timeout=timeout, env=env)
