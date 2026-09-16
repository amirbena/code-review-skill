# Verdict-Consistency Benchmark

Repository-development artifact for GitHub Issue
[#378](https://github.com/amirbena/code-review-skill/issues/378), depends
on [#377](https://github.com/amirbena/code-review-skill/issues/377) (the
shared verdict-consistency comparator,
[`../../../../shared/policies/verdict-consistency.md`](../../../../shared/policies/verdict-consistency.md)),
which in turn implements the design record for
[#351](https://github.com/amirbena/code-review-skill/issues/351)
([`../../../benchmark-measurement-architecture/verdict-consistency-boundary-research.md`](../../../benchmark-measurement-architecture/verdict-consistency-boundary-research.md)).

[#350](https://github.com/amirbena/code-review-skill/issues/350) proves
the normal mechanical severity → decision path: when a real review
produces a P0/P1 finding, the rendered verdict must not be clean. That is
necessary but does not prove the runtime boundary #351 researched and
#377 implemented actually catches a *corrupted or inconsistent*
downstream surface. This corpus is deliberately adversarial: every case
starts from an already-finalized mechanical decision and then
deliberately drifts the about-to-be-rendered or about-to-be-submitted
signal away from it, proving that the real comparator withholds the
mismatched artifact and reports an internal-consistency failure — never
silently skipping the check and never self-correcting the drifted signal.
This corpus does not re-prove #350's normal-path derivation and does not
duplicate #377's own unit suite (see "Why this isn't a
`benchmark-case/v1` corpus" below).

## Why this isn't a `benchmark-case/v1` corpus

Every corpus under [`../`](../README.md) that reviews a code change (each
a self-contained inline patch plus expected review *findings*) uses the
`benchmark-case/v1` fixture format
([`../../fixture-format.md`](../../fixture-format.md)). This domain has no
patch and no finding: its input is an already-finalized mechanical
decision plus a deliberately drifted rendered/submitted signal, and its
expectation is a withhold-and-report outcome (or, for the control cases, a
genuinely consistent pass-through). Rather than stretch the finding-shaped
schema to also carry consistency-boundary semantics, this corpus follows
the same test-only, data-driven reference-fixture pattern
[`../publication-mode/README.md`](../publication-mode/README.md) already
established for the structurally analogous publication-boundary domain:

- [`../../../../tests/reference/benchmark/verdict_consistency_fixtures.py`](../../../../tests/reference/benchmark/verdict_consistency_fixtures.py) —
  one `VerdictConsistencyCase` per required outcome shape, each a
  zero-argument `run()` closure that exercises the *single* real
  comparator,
  [`../../../../tests/reference/review/verdict_consistency.py`](../../../../tests/reference/review/verdict_consistency.py)
  (`check_rendered_signal` / `check_submitted_event`), through the
  runbook-shaped wrappers `render_or_withhold` / `publish_or_withhold`,
  which mirror each Skill's actual reconciliation step: construct the
  protected report/event artifact on a consistent signal, or withhold it
  and report an internal-consistency failure in its place — never both,
  mirroring `verdict-consistency.md`'s own "On a detected mismatch:
  withhold-and-report".
- [`../../../../tests/unit/benchmark/test_verdict_consistency_corpus.py`](../../../../tests/unit/benchmark/test_verdict_consistency_corpus.py) —
  runs every case's `run()`, validates the returned `Observed` shape
  (exactly one of a rendered artifact, a published artifact, or a
  withheld artifact — never two at once, which would mean a self-
  correction, and never zero, which would mean a silent skip), and
  asserts the withhold-vs-emit outcome matches its declared expectation,
  plus corpus-completeness checks (every reconciliation point, the
  required highest-risk shape, malformed-fixture rejection, and
  governance-vocabulary checks reused from
  [`../../../../tests/reference/review/decision_semantics.py`](../../../../tests/reference/review/decision_semantics.py)).

This corpus is **not** a duplicate of
[`../../../../tests/unit/review/test_verdict_consistency.py`](../../../../tests/unit/review/test_verdict_consistency.py),
which #377 already landed as an extensive unit suite proving the raw
comparator functions mechanically, in isolation, returning only a
`Verdict` enum member. That suite is *why* the boundary holds; this
corpus is the declarative, metadata-bearing **benchmark** layer #378
asks for, and it is the only place that inspects the actual
withheld-or-emitted *artifact* a reconciliation point would construct —
proving enforcement of the boundary, not merely the comparator's return
value.

## Evaluation style

Every comparison in this corpus is a **deterministic structural
assertion** — the returned `Observed`'s `rendered` / `published` /
`withheld` fields, and the withheld artifact's `reason` classification —
never an LLM/rubric score. This corpus is disjoint from the
finding-precision/recall/severity metrics
([#41](https://github.com/amirbena/code-review-skill/issues/41)) and from
every other domain corpus; it never touches a finding's content beyond
the closed P0/P1/P2 severity already used to derive the mechanical
decision each case starts from.

## Categories and required outcome shapes

| Category | Required shapes |
| --- | --- |
| `local_pre_render` | reconciliation point 1 (`local-code-review` pre-render): a blocking-to-clean and a clean-to-blocking mismatch, both withheld |
| `passive_semi_pre_render` | reconciliation point 2 (`github-pr-review` PASSIVE/SEMI pre-render): same two mismatch directions, both withheld |
| `active_pre_render` | reconciliation point 3 (`github-pr-review` ACTIVE pre-render, before the review body/inline comments are constructed): same two mismatch directions, both withheld |
| `active_pre_publish` | reconciliation point 4 (`github-pr-review` ACTIVE pre-publish, against the literal GitHub review API `event`): the highest-risk blocking-findings → `APPROVE` shape, the inverse clean → `REQUEST_CHANGES` shape, and the no-formal-event carve-out (never withheld) |
| `silent_drift_after_prerender` | a case whose pre-render check (point 3) already passed consistently, but whose submitted event drifts before submission — point 4 must independently catch it; point 3 having passed is never treated as sufficient |
| `incomplete_coverage_mismatch` | a mismatch that happens to involve `REVIEW INCOMPLETE` (a rendered `REVIEW CLEAN` while coverage is incomplete, and a formal event submitted while coverage is incomplete) — the carve-out is for a *correctly* rendered incomplete outcome, never a license to skip checking it |
| `control_consistent` | one genuinely agreeing case per reconciliation point, plus the no-formal-event and correctly-rendered-`REVIEW INCOMPLETE` carve-outs — none of these are ever withheld; this corpus is adversarial, not trigger-happy |

Every case's category, covered requirement tags, and declared
`expect_withheld` live in its `VerdictConsistencyCase` definition in
`verdict_consistency_fixtures.py` — this table is a map, not a second
source of truth.

## The required highest-risk shape

Per #378's acceptance criteria, `vc-local-blocking-to-clean-mismatch`,
`vc-passive-semi-blocking-to-approve-mismatch`,
`vc-active-prerender-blocking-to-approve-mismatch`, and
`vc-active-prepublish-blocking-to-approve-event-mismatch` each cover the
minimum required shape — a finalized blocking-findings decision paired
with a clean/`Approve` rendered or submitted signal — at every
reconciliation point that can express it, tagged `highest-risk`. The
pre-publish shape (a formal `APPROVE` event about to be submitted to
GitHub's API for a blocking-findings review) is the single most severe
case in this corpus, since it is the one step furthest from being
correctable by a later human reviewer.

## Distinguishing this corpus from #350

[#350](https://github.com/amirbena/code-review-skill/issues/350) (open at
the time this corpus was written) proves that a real review, run
end-to-end through the real packaged Skill, correctly *derives* a
blocking `CHANGES REQUIRED` / non-approve outcome from a real P0/P1
finding. This corpus never re-derives a decision from findings at all —
every case starts from an already-finalized decision
(`decision_semantics.derive_decision`) and asks a different question:
does the runtime catch a *downstream* surface that disagrees with that
already-finalized decision? A regression in #350's corpus means the
review got the finding wrong; a regression in this corpus means the
review got the finding right but then rendered or published something
else — the failure mode #351 researched and #377 built the boundary to
close.

## Running just this benchmark

```sh
python3 -m unittest tests.unit.benchmark.test_verdict_consistency_corpus
```

## Validation

Exercised by the repository's normal test run
(`python3 -m unittest discover tests` / `pytest`), alongside every other
corpus under [`../`](../README.md).
