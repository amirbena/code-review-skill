# Shared Policy — Evidence

Every finding, in either Skill, must be supported by concrete repository
evidence: changed lines, surrounding code, tests, repository
instructions, contracts, schemas, configuration, architecture
documentation, or CI behavior.

## Required distinctions

Every finding must be labeled, implicitly or explicitly, as one of:

- **confirmed defect** — the evidence directly demonstrates incorrect
  behavior;
- **credible engineering risk** — the evidence supports a plausible
  failure mode, but is not a certainty;
- **optional improvement** — a valid but non-blocking engineering
  suggestion.

## Rules

- Do not present speculation as certainty.
- Do not manufacture findings to appear thorough (see
  [`review-scope.md`](review-scope.md)).
- Passing validation (tests, lint, CI, type checks) does not by itself
  prove correctness — do not claim validation passed without evidence,
  and do not treat green checks as a substitute for review.
- A missing validation step may itself be a finding where materially
  relevant.

## Findings beyond the changed lines

Changed lines are the starting point of review, not necessarily its complete
boundary — relevant surrounding or dependent code may need examination to
judge a change correctly. A finding located outside the changed lines is
valid only when the reviewed change introduces, activates, exposes, breaks,
or materially affects it — never merely because a pre-existing, unrelated
defect was noticed while reading nearby or dependent code. Do not turn
impact/dependency reasoning into an unrelated audit of the existing
codebase.

When the evidence for a finding sits at one location but the change that
resolves it belongs at another (or vice versa), the finding distinguishes
the evidence/detection location from the canonical fix/action location per
[`../templates/finding.md`](../templates/finding.md), "Fix/action location,
evidence location, publication." A Skill that anchors findings to a review
surface prefers the resolved fix/action location; when that location
cannot be confidently determined, the finding states so explicitly rather
than treating the evidence location as the fix.

Scale this to the change: a small, clearly isolated change needs little or
no dependency exploration beyond confirming it doesn't affect anything else;
a change with a wide realistic blast radius (a shared contract, schema, or
widely depended-on symbol) warrants more. This invariant applies identically
to any Code Review Skill built on this policy, local or PR-based, and
regardless of which review engine or model executes it.

This same scaling — investigate no further than the change's own realistic
blast radius — governs the targeted searches in
[`review-scope.md`](review-scope.md), "Existing behavior ownership,"
"Failure state, retry safety, and recovery," and "Architectural placement
and execution-lifecycle fidelity" (its bounded caller/callee/owning-boundary
context expansion), and in its two extracted sub-policies —
[`root-cause-consolidation.md`](root-cause-consolidation.md), "Root-cause
and model-completeness pass," and
[`affected-test-analysis.md`](affected-test-analysis.md), "Affected-test /
test-impact analysis" (tracing a behavioral change into the existing tests
that depend on it) — identically to
any other cross-file reasoning: none is a license for a repository-wide
audit, and a finding under any of them still requires the same
confirmed-defect / credible-risk / optional-improvement evidence labeling
above.

The deterministic `standard` / `elevated` / `deep` review-depth
classification in
[`change-risk-signals.md`](change-risk-signals.md) is the inspectable
form of this same "scale to the change" idea: it tunes how much effort a
review spends looking, never the evidence bar a finding must clear. A
`deep` classification does not lower the labeling requirement above, and a
`standard` one does not excuse missing a finding the evidence supports.

[`repository-expansion.md`](repository-expansion.md) makes the "scale
dependency exploration to blast radius" instruction above concrete for a
fixed set of triggers (a changed call site, interface/contract,
migration/schema, or config consumer): a bounded, ring-based procedure
for how far each trigger is followed, with its maximum ring scaled by the
change-risk depth. It governs only where an investigation looks, never
what counts as a finding or how a finding is labeled.

When a change's diff size crosses a fixed threshold,
[`large-pr-partitioning.md`](large-pr-partitioning.md) partitions it into
coherent review units, each reviewed against this same evidence standard,
with findings aggregated and de-duplicated — including across partitions
— before any decision is derived. It changes how a large diff is
organized for review, never what counts as a finding, its evidence label,
or its severity.

[`review-stopping-criteria.md`](review-stopping-criteria.md) defines when
all of the above is actually done: complete coverage requires every pass
the classified depth activates, and every partition when partitioning
activated, to have reached its own stop condition. An incomplete review
still reports every finding it actually gathered with the same evidence
standard as a complete one; incompleteness only changes the review's
top-level outcome label, never a finding's evidence bar.

The repository-intelligence model design record (a repository-development
document, not a packaged resource, so it is named here, not linked) types
what a fired [`repository-expansion.md`](repository-expansion.md) trigger
resolves inside its authorized ring — entities, relationships, provenance,
snapshot identity and staleness, and relationship-influence attribution —
without changing this section's evidence bar or that policy's ring
ceiling.
