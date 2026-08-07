# Runbook — Local Review Loop

Wraps [`passive-local-review.md`](passive-local-review.md) into an
iterative review/fix cycle with an implementing Agent, bounded by
[`../review-config.yaml`](../review-config.yaml) (`review.max_loops`,
default `3`).

## Flow

```text
implementation
    ↓
review iteration 1
    ↓
findings?
    ├── no  → REVIEW CLEAN → stop (see local-pr-completion.md)
    └── yes
         ↓
implementing Agent fixes
         ↓
review iteration 2
         ↓
...
         ↓
iteration == review.max_loops and blocking findings remain?
    → REVIEW LOOP LIMIT REACHED → stop
```

## Rules

- Read `review.max_loops` from `review-config.yaml` at the start of the
  loop; never hardcode the limit.
- Stop **immediately** the first time review becomes clean — never run
  additional iterations merely because the configured maximum has not
  been reached.
- On each iteration, run
  [`passive-local-review.md`](passive-local-review.md) in full; do not
  reuse stale findings from a previous iteration.

## Loop exhaustion

When the configured maximum is reached and blocking (P0/P1) findings
remain:

```text
REVIEW LOOP LIMIT REACHED
```

Return, via [`../templates/local-review-report.md`](../templates/local-review-report.md):

- unresolved P0 findings;
- unresolved P1 findings;
- relevant P2 findings;
- the current implementation state;
- an explicit statement that the implementation is not review-clean.

Do not hide findings, falsely report success, push merely to escape the
loop, or open a PR as if review passed. The implementing/orchestrating
Agent decides what happens next — the Code Review Agent's responsibility
ends at reporting the exhausted loop state.
