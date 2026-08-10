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

Scale this to the change: a small, clearly isolated change needs little or
no dependency exploration beyond confirming it doesn't affect anything else;
a change with a wide realistic blast radius (a shared contract, schema, or
widely depended-on symbol) warrants more. This invariant applies identically
to any Code Review Skill built on this policy, local or PR-based, and
regardless of which review engine or model executes it.
