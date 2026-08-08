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
