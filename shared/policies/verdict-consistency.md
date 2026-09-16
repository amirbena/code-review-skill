# Shared Policy — Verdict-Consistency Boundary

Applies identically to `local-code-review` and `github-pr-review`, across
`PASSIVE`, `SEMI`, and `ACTIVE` delivery. This policy defines **one**
read-only comparator, reused by both Skills rather than forked per-Skill,
that checks the already-finalized mechanical decision from
[`severity.md`](severity.md), "Decision derivation (mechanical)," against
the fixed-vocabulary decision signal a runbook is about to render or
submit, immediately before that render or submission. It introduces no
second decision path: it never derives a decision itself, never
overrides `severity.md`'s or
[`review-stopping-criteria.md`](review-stopping-criteria.md)'s already-
finalized outcome, and never lets a caller select, force, or correct its
result. This repository's own
`docs/benchmark-measurement-architecture/` design record for issue #351
is the research background this policy implements — explanatory only,
and not part of the packaged Skills.

## Why this exists

`severity.md`'s single-derivation invariant already requires that a
decision, once derived, renders identically everywhere it appears. That
invariant is a rule about how a report must be composed; it does not by
itself catch a runtime that composes a rendering (or, in
`github-pr-review` `ACTIVE` mode, a GitHub review event) that quietly
disagrees with the decision it was supposed to carry — for example a
`Request Changes` label built for a review whose finalized findings
contain no blocking severity, or an `APPROVE` event about to be
submitted for a review whose finalized findings do. This policy is the
runtime check that a rendered or submitted decision signal actually
matches the one mechanical derivation, sitting immediately before the
one irreversible action each reconciliation point protects.

## Inputs

The comparator consumes exactly two already-finalized values — it
computes neither:

1. **The mechanically-derived decision**, from `severity.md`'s
   "Decision derivation (mechanical)" over the already-finalized finding
   set, as overridden (or not) by `review-stopping-criteria.md`'s
   coverage-incomplete outcome. This is the sole source of truth; the
   comparator never re-derives it from findings itself.
2. **The decision signal about to be rendered or submitted** — one of
   the existing fixed-vocabulary markers already defined elsewhere in
   this repository: `REVIEW CLEAN` / `CHANGES REQUIRED` (local report),
   `Approve` / `Request Changes` (GitHub-facing report wording,
   including a `SEMI`-mode `WOULD PUBLISH (<event>)` line), or the
   literal GitHub review API `event` value about to be submitted
   (`APPROVE` / `REQUEST_CHANGES`) in `ACTIVE` mode.

The comparator is read-only: given these two already-finalized values, it
returns **consistent** or **inconsistent**, and nothing else. It does not
accept, and must never gain, an override, force, bypass, or
manual-decision parameter, nor a correction, provisional, or resubmit
parameter — see "Governance" below.

## Non-mismatch carve-outs

Two situations are sanctioned pass-throughs, not mismatches, and the
comparator must not flag either:

- **`REVIEW INCOMPLETE` / coverage-incomplete.** When
  `review-stopping-criteria.md`'s coverage evaluation has already
  overridden the mechanical clean/blocking derivation with the
  incomplete/ungraded outcome, the comparator checks the rendered signal
  against that incomplete outcome, not against the clean/blocking value
  the finding set alone would otherwise have produced. This policy does
  not change, restate, or re-decide when coverage is incomplete; it only
  consumes that already-finalized outcome as the value to check against.
- **No formal event exists.** `PASSIVE` mode publishes no GitHub review
  event, and `github-pr-review`'s own review-action-authorization policy
  withholds a self-review's formal `APPROVE` / `REQUEST_CHANGES` event
  regardless of the finalized decision (an informational `COMMENT` is
  published instead). In both cases the comparator evaluates only the
  rendered report signal (input 2 above, first form); it never requires,
  fabricates, or waits for a formal event that this run does not and
  will not produce.

## Reconciliation points

The comparator runs at exactly four points, each immediately before the
one render or publication action it protects — never after:

1. **`local-code-review`, pre-render** — between decision derivation and
   composing the human-facing report body.
2. **`github-pr-review` `PASSIVE` / `SEMI`, pre-render** — between
   decision derivation (finding finalization and coverage evaluation)
   and composing the returned report body.
3. **`github-pr-review` `ACTIVE`, pre-render** — identical placement to
   (2), immediately before constructing the review body and inline
   comments. `SEMI` shares this same construction step.
4. **`github-pr-review` `ACTIVE`, pre-publish** — immediately before
   submitting the review, re-checking the literal `event` value about to
   be sent to GitHub's API against the same mechanically-derived decision
   checked at (3). This catches a second, silent rendering introduced
   between the pre-render check and the actual submission (for example
   by the flow's own HEAD-revalidation branch).

Each Skill's runbook names the exact step this check sits at; this policy
owns only the check's semantics, not its placement prose, which is not
restated here.

## On a detected mismatch: withhold-and-report

A detected mismatch is handled exactly one way, at every reconciliation
point: **withhold the protected render or publication action, and report
an internal-consistency failure in its place.** Specifically:

- At a pre-render point (1, 2, or 3), the runbook does not construct or
  return the report/review body at all; it reports that an internal
  consistency check failed instead of the report.
- At the pre-publish point (4), the runbook withholds the formal
  `APPROVE` / `REQUEST_CHANGES` submission and reports why no final
  formal review was submitted, reusing the same "no final formal review
  was submitted" reporting path already used when GitHub itself
  disallows the event.

The comparator never self-corrects the mismatched signal, never
re-renders a "fixed" version, and never warns and proceeds anyway. A
self-correction would itself be a second, independent decision path —
exactly what `severity.md`'s single-derivation invariant already
forbids. There is no partial-credit outcome: a mismatch always withholds
the full protected action, never a "best effort" partial render or
partial submission.

## Governance

This comparator is maintainer-owned: its semantics are decided once,
canonically, in this file, and are never a per-invocation parameter, a
caller-selectable behavior, or a per-Skill fork. Consistent with this
repository's existing governance invariant for the severity → decision
contract, no function implementing this policy may accept a parameter
whose name contains any fragment in
`PROHIBITED_OVERRIDE_PARAM_FRAGMENTS` (`override`, `force`, `bypass`,
`ignore_severity`, `manual_decision`, `recommend_block`, `should_block`)
or `PROHIBITED_CORRECTION_FRAGMENTS` (`correction`, `correct_decision`,
`provisional`, `supersede`, `resubmit_decision`, `revise_decision`).

## Non-goals

- Does not redesign `severity.md`'s P0/P1/P2 model or its mechanical
  derivation — it only compares against that derivation's already-
  finalized output.
- Does not redesign `review-stopping-criteria.md`'s coverage/incomplete
  semantics — it only recognizes that outcome as a non-mismatch.
- Not a general-purpose Markdown or API-payload parser: it matches the
  existing closed set of fixed-vocabulary markers named above, nothing
  else. A future structured decision schema (tracked separately) may
  change how the rendered/submitted signal is read; this comparator's
  contract — two already-finalized inputs in, consistent/inconsistent
  out — does not need to change when that happens.
- Does not add a benchmark or corpus proof; that is tracked as a
  separate, dedicated issue.

This is the single canonical verdict-consistency comparator. Neither
Skill defines its own copy, and no reconciliation point re-implements
this check independently — all four call the same comparator semantics
defined here.
