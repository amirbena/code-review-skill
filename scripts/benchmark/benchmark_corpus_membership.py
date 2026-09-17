#!/usr/bin/env python3
"""Execution-mode/lane contract and comprehensive corpus membership (Issue #431).

Single canonical home for two small, closely-related things the two-tier
scheduled benchmark execution model (`docs/benchmark/corpus/README.md`,
`docs/benchmark/nightly-history-and-baseline.md` §2) needs on both the
execution side (`run_benchmark_routine.py`) and the storage side
(`benchmark_history.py`):

1. The **lane** identity — `sentinel` (the 4 permanent canonical cases,
   `docs/benchmark/corpus/*.yaml`, every 3 days) vs. `comprehensive`
   (every `benchmark-case/v2` fixture in the corpus tree, weekly) — and
   `full`'s resolution as a deprecated, fixed synonym for `sentinel`
   (never a second live meaning).
2. **Comprehensive corpus membership**, derived programmatically by
   recursively scanning the corpus tree for `benchmark-case/v2` fixtures
   (`docs/benchmark/fixture-format.md`) rather than a hard-coded count or
   list. A sub-corpus directory that holds zero such fixtures — a
   test-only / reference-model suite consumed only by
   `tests/reference/benchmark/*` (e.g. `mutation-boundary`,
   `reviewer-brief`, `delegation-spawn`, `sandbox-adversarial`,
   `trusted-host-nl-authorization`, `security-events`,
   `publication-mode`, `verdict-consistency`) and never a valid
   `ProductionReviewerAdapter` input — is excluded by construction: it
   contributes nothing to the scan, so there is no denylist to keep in
   sync as those suites grow.

Both lanes stay Cloud-Routine-scheduled, maintainer-controlled, and never
a contributor/PR/merge/deployment gate — this module computes membership
and lane identity only; it never schedules, executes, or persists
anything itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FORMAT_V2 = "benchmark-case/v2"

SENTINEL_LANE = "sentinel"
COMPREHENSIVE_LANE = "comprehensive"

# `full` predates the explicit sentinel/comprehensive contract (#338/#415)
# and, before this issue, ambiguously meant "the whole default --corpus-dir
# glob" — which in practice only ever resolved to the 4 top-level canonical
# cases because that glob is non-recursive. Resolved here, once: `full` is
# a deprecated, fixed synonym for `sentinel` — it never gains a second live
# meaning, and it is never made to mean "comprehensive".
LEGACY_MODE_ALIASES = {"full": SENTINEL_LANE}

DEFAULT_LANE = SENTINEL_LANE


def canonical_lane(mode: str) -> str:
    """Resolve a `--mode` value to its canonical lane identity.

    `sentinel` and `comprehensive` map to themselves; the deprecated
    `full` alias maps to `sentinel`. Any other value (`smoke`, `selected`,
    `auth-check`) is not a scheduled lane and is returned unchanged — the
    caller is expected to only use this for the two scheduled-lane modes.
    """
    return LEGACY_MODE_ALIASES.get(mode, mode)


@dataclass(frozen=True)
class ComprehensiveFixture:
    """One `benchmark-case/v2` fixture eligible for the comprehensive lane.

    `corpus_dir` is the directory `run_benchmark.py --corpus-dir` must be
    pointed at to find this fixture by `--case-id` — `run_benchmark.py`'s
    own corpus loading is a non-recursive `*.yaml` glob (unchanged by this
    issue), so a fixture living in a sub-corpus directory is only visible
    when `--corpus-dir` is that sub-directory itself.
    """

    case_id: str
    corpus_dir: Path
    fixture_path: Path


def discover_comprehensive_fixtures(corpus_root: Path) -> list[ComprehensiveFixture]:
    """Recursively derive comprehensive lane membership from the corpus tree.

    Every `*.yaml` file anywhere under `corpus_root` whose top-level
    `format` is exactly `benchmark-case/v2` is included, keyed by its own
    `id`. This is the only membership rule — no case count, path, or name
    is hard-coded. A file that fails to parse as YAML, is not a mapping,
    or lacks a non-empty string `id` is skipped rather than raising, since
    a malformed or unrelated file (e.g. a future non-fixture YAML dropped
    into the tree) must not abort corpus discovery; a duplicate `id`
    across two fixtures *is* a hard error, since that would make case
    identity ambiguous for history/baseline joins.
    """
    import yaml

    fixtures: list[ComprehensiveFixture] = []
    seen: dict[str, Path] = {}
    for path in sorted(corpus_root.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or data.get("format") != FORMAT_V2:
            continue
        case_id = data.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            continue
        if case_id in seen:
            raise ValueError(
                f"duplicate comprehensive case id {case_id!r}: {seen[case_id]} vs {path}"
            )
        seen[case_id] = path
        fixtures.append(ComprehensiveFixture(case_id=case_id, corpus_dir=path.parent, fixture_path=path))
    return sorted(fixtures, key=lambda fx: fx.case_id)


def comprehensive_case_ids(corpus_root: Path) -> list[str]:
    return [fx.case_id for fx in discover_comprehensive_fixtures(corpus_root)]
