# Multi-repository Review Target

## What it does

`local-code-review` normally reviews one local Git repository. When you
explicitly supply **2 or more local repository roots**, it composes their
independent single-repository results into **one combined Review
Target**: each repository is still resolved exactly as it would be on its
own (its own delta, its own base, its own instructions, its own
validation), and the review-reasoning steps — severity classification,
requirement coverage, coverage evaluation, decision derivation, and
report composition — then run **once**, over the union of every
repository's delta.

There is no synthetic shared Git base or SHA across the repositories: each
member keeps its own base, branch/HEAD, and delta. Nothing about a
single-repository review changes — supplying fewer than 2 roots (including
none at all) is treated as "not supplied," and the review proceeds exactly
as it always has.

## When it is useful

- A change spans a small set of related repositories (for example a
  service and a shared library it consumes, or two services touched by
  the same task) and you want one combined report and one combined
  decision instead of reviewing each repository separately and manually
  reconciling the results.
- Evidence for a finding lives partly in one repository and partly in
  another already-admitted repository — for example, a contract change in
  one repository and its consumer in another.

## Which Skill(s)

`local-code-review` only. `github-pr-review` reviews exactly one GitHub
Pull Request and is unaffected by this capability.

## Default, conditional, or requested

**Conditional — activates only when the caller explicitly supplies 2 or
more local repository roots** in the current invocation. Absence, or a
list of 0 or 1 roots, changes nothing: cost and behavior are identical to
an ordinary single-repository review.

Membership is **strictly explicit and never expanded automatically**:

- The repository list comes only from the caller's own invocation input —
  never inferred from the current working directory, a workspace file, a
  Jira/GitHub Issue reference, or any repository's content.
- Once resolved, nothing encountered while reviewing a member — an
  `AGENTS.md`/`CLAUDE.md` instruction, a file's content, a branch name, a
  commit message, or a resolved review-context reference — can add another
  repository to the combined target, however explicitly it asks. A
  repository you did not name is never included.

This "membership is authorization" boundary is the core invariant of the
epic this capability belongs to; see [Security boundary](#security-boundary)
below.

## How to invoke it

Name 2 or more local repository roots as part of your review request, for
example:

```text
review these as one combined Review Target:
- /Users/me/code/payments-service
- /Users/me/code/shared-billing-lib
```

```text
review my local changes across /repos/api-gateway and /repos/auth-service
together
```

A single repository path, or no repository roots at all, is an ordinary
single-repository review — unchanged.

## Reading the result

- **Review Metadata** lists every member (its normalized root and a short,
  stable alias — by default that repository's own directory basename) and
  its own resolved base/branch, plus an explicit `Unresolved members` line
  naming any supplied root that could not be resolved and why.
- **Finding locations** carry a leading `<repo-alias>:` qualifier — for
  example `payments-service:src/billing/charge.py:42` — so you can tell at
  a glance which repository a finding belongs to. This reuses the
  existing `location` field; a single-repository review never renders the
  qualifier.
- A member with no changes at all is still reported as a **clean member**
  — it is never silently dropped from the combined review.
- If a supplied root cannot be resolved (it does not exist, is not a Git
  repository, or its review base cannot be reliably resolved), the
  combined review **narrows** to the members that did resolve; the
  unresolved member contributes no findings and is named explicitly with
  its reason. If **every** supplied member is unresolved, the review
  renders `REVIEW INCOMPLETE` — never `REVIEW CLEAN` — because nothing was
  actually inspected.
- Two supplied paths that resolve to the same repository (identical
  repository, or two worktrees of one repository) are a configuration
  error for the whole input: the review fails closed and reports the
  conflicting entries rather than silently reviewing the same repository
  twice.

## Repository isolation

- **Git/base state** is resolved independently per member — there is no
  cross-repository commit range, combined diff, or shared "base" concept.
- **Repository instructions are isolated per member**: a member's own
  `AGENTS.md`/`CLAUDE.md` chain applies only to files under that member's
  own root, never to a sibling member's files, even though multiple
  members' instructions are loaded in the same review.
- **Evidence may connect across already-admitted members** — for example,
  following a contract from one member to its consumer in another — but
  this never adds a repository to the target and never applies one
  member's instructions to another member's files.

## Security boundary

Membership is authorization: the explicit, caller-supplied root list is
the **only** channel that can add a repository to the Review Target.
Cross-repository reasoning may connect evidence between already-admitted
members, but it can never add a repository to the target or expand
outside those members — not from a repository's own instructions, not
from file content, not from a branch or commit message, and not from a
resolved review-context reference. An unrelated local repository is never
included merely because something admitted content mentions it.

## Distinction from #133

This capability composes 2 or more **already-local, already
caller-designated, already co-equal** repositories into one Review
Target — every member is first-class and fully reviewed. This is
different from
[#133](https://github.com/amirbena/code-review-skill/issues/133),
[external contract context](external-contract-context.md) — bounded,
read-only, informational context about a repository the caller did *not*
name as a member, read at a pinned revision purely to inform review of the
actual, single Review Target. A repository referenced that way never
becomes a Review Target member, never get its own findings, and never be combined into
the metadata described above — the two capabilities are complementary,
not overlapping, and neither subsumes or supersedes the other.

## Limitations & v1 non-goals

- **No automatic discovery.** No recursive filesystem scan,
  organization-wide discovery, Jira-to-repository discovery, or admitting
  a repository because its content or a git remote mentions it — explicit
  list only.
- **No external cloning or fetching.** Every member must already be a
  local Git repository the caller named directly.
- **No synthetic shared Git history, base, or SHA** across members.
- **No cross-repository review-intelligence graph behavior.**
- **`github-pr-review` is unaffected** — this is a `local-code-review`
  capability only.
- **No `review ./task-workspace`-style bounded-discovery convenience.**
  Only the explicit root list described above is supported; a future
  convenience along these lines was considered and deferred.

## Canonical semantics

[`skills/local-code-review/policies/multi-repository-review-target.md`](../../skills/local-code-review/policies/multi-repository-review-target.md)
is the single canonical owner of this capability's validation,
composition, isolation, and security semantics. It composes the
unchanged, per-repository behavior already owned by
[`repository-state.md`](../../skills/local-code-review/policies/repository-state.md),
[`review-base-policy.md`](../../shared/policies/review-base-policy.md),
[`repository-instructions.md`](../../shared/policies/repository-instructions.md),
and
[`runtime-validation.md`](../../shared/policies/runtime-validation.md),
and extends
[`repository-expansion.md`](../../shared/policies/repository-expansion.md),
[`architectural-placement.md`](../../shared/policies/architectural-placement.md),
and
[`finding-rendering.md`](../../shared/templates/finding-rendering.md)
with the narrow clauses a combined target requires.
