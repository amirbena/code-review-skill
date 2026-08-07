# Policy — Review Ownership

## Canonical invariant

```text
One review scope → one Code Review Agent owner
```

If a dedicated Code Review Agent is already assigned to the same task,
branch, PR, or implementation scope, do not launch a second full
reviewer. Return conceptually:

```text
REVIEW ALREADY OWNED
```

when orchestration context indicates that another Code Review Agent owns
the same scope. The runtime determines how ownership metadata is exposed;
this policy does not hardcode a runtime-specific ownership-detection
mechanism.

## Access vs. Ownership

Keep these two concepts strictly separate:

- **Repository review access** — can this authenticated GitHub identity
  actually review this PR? (a GitHub-permissions question — see
  [`github-review.md`](github-review.md))
- **Agent review ownership** — has another Code Review Agent already been
  assigned this review scope? (an orchestration question — this policy)

Both must be respected independently:

- an identity may have GitHub permissions but still not own the Agent
  review scope (defer to the owning Agent);
- an Agent may own the review scope but lack GitHub permissions, in which
  case it can still perform passive review and must degrade gracefully
  rather than fake active review (see `github-review.md`).

## Multi-Agent guard

When a multi-Agent workflow already includes a Code Review Agent,
implementation Agents may test, lint, build, and self-check their own
implementation, but must not independently perform the formal review
responsibility assigned to the Code Review Agent. Avoid duplicate review
findings, duplicate GitHub comments, contradictory severity, contradictory
approval decisions, and multiple reviewers racing against different
HEADs.

## Parallel review scope

Default: one reviewer per PR/task scope. Separate Code Review Agents may
operate concurrently only on independent scopes, e.g.:

```text
PR #10 → Reviewer A
PR #11 → Reviewer B
```

For one very large PR, parallel review is allowed only if ownership is
explicitly partitioned, e.g.:

```text
Reviewer A → backend files
Reviewer B → infrastructure files
```

A coordinating reviewer must own deduplication, consistent severity, and
the final combined decision. Do not automatically parallelize one review.
