# Review context & prior review evidence

## What it does

Lets you point a review at the *intent* behind a change, not just its
diff. You can supply, in any combination:

- **Review context** — free-form requirements or instructions, a pasted
  ticket or acceptance criteria, a pasted GitHub Issue, an HLD/ADR, an
  implementation plan, or a PR/task description. A bare **Jira key/URL**
  or **GitHub Issue reference** is also accepted — it is resolved
  read-only before the review, never treated as if the identifier itself
  carried the requirements.
- **Prior review evidence** — for `github-pr-review`, the PR's own prior
  reviews, review comments, and issue comments; for `local-code-review`,
  the prior findings and settled decisions of an **associated PR
  reference** you supply.

The reviewer uses context to focus attention and to reason about scope
boundaries (missing required behavior, contradicted acceptance criteria,
unrelated scope expansion, repository-policy violations). Prior evidence
is reconciled against the *current* target — a resolved thread is
evidence of a past conclusion, not proof the current code is correct, and
a reintroduced defect is a fresh finding.

## When it is useful

- The change implements a ticket or acceptance criteria you can paste in.
- A design decision lives in an ADR/HLD the diff alone does not explain.
- You want the review to respect what a previous reviewer already settled
  instead of re-litigating it.

## Which Skill(s)

Both. The model is defined once in
[`shared/policies/review-context.md`](../../shared/policies/review-context.md)
and
[`shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md);
each Skill keeps a thin application naming its own target
([`local`](../../skills/local-code-review/policies/review-context.md) ·
[`github`](../../skills/github-pr-review/policies/review-context.md), and
[`pr-context.md`](../../skills/local-code-review/policies/pr-context.md)
for the local Skill's PR reference).

## Default, conditional, or requested

**Optional.** When you supply nothing, each Skill behaves exactly as if
the input did not exist and never asks for it. Jira is never mandatory.

## How to invoke it

`local-code-review` — attach context after the request:

```text
/local-code-review

Context source: Jira PROJECT-1234
Acceptance criteria:
- reject unsupported CC + RTP combinations
- validation must occur before execution
```

```text
review the working tree against PROJECT-1234's acceptance criteria
review my local changes; the design is in docs/adr/0007-idempotency.md
review these changes and reconcile against PR #812's earlier findings
```

`github-pr-review` — same idea, alongside the PR:

```text
review PR https://github.com/acme/app/pull/812 against the plan in the description
review #812; context is Jira ACME-42
```

## Limitations & safety boundaries

- Context **never widens the review target** — the local delta / the PR
  delta stays the scope. It is never a second thing being reviewed.
- Context never overrides the code: actual code/tests/config win on *what
  the change does*; context informs *what it was supposed to do*.
- A supplied **Jira reference that cannot be resolved** stops the
  Jira-scoped path with `JIRA CONTEXT UNRESOLVED` — the reviewer does not
  guess the ticket from its key, the branch, or the PR title. Re-invoke
  without the reference for a normal unscoped review.
- All context handling is **read-only** — no Jira mutation, no GitHub
  mutation, and supplying context is never itself approval to run a
  Skill.

## Canonical semantics

[`shared/policies/review-context.md`](../../shared/policies/review-context.md)
· [`shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md)
· architecture context in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §2.
