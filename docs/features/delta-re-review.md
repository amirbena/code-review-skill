# Delta & SHA-aware re-review

## What it does

When the **same reviewer** re-reviews a PR after a push, and the exact
SHA of that reviewer's immediately preceding completed review can be
established reliably, `github-pr-review` scopes the new pass to:

```text
previously reviewed SHA → current PR HEAD
```

plus enough surrounding context to confirm the fix is correct, no
regression was introduced, and the previous review's assumptions still
hold. If the previously reviewed SHA already equals the current HEAD, the
Skill returns `NO NEW DELTA` instead of manufacturing a duplicate review.

`local-code-review` has no GitHub review history to key off; its
analogues are the **staged-delta fingerprint** short-circuit (a
re-invocation with an unchanged staged delta is recognised) and
reconciliation against a supplied **PR reference**'s prior findings.

## When it is useful

- You reviewed a PR, the author pushed a small fix, and you want to check
  just that fix rather than re-reading the whole PR.
- You want to avoid emitting a second, redundant review for a HEAD you
  already reviewed.

## Which Skill(s)

`github-pr-review` (SHA-bound delta re-review, `NO NEW DELTA`,
escalation-to-full). `local-code-review` covers the local equivalents via
[`repository-state.md`](../../skills/local-code-review/policies/repository-state.md)
and [`pr-context.md`](../../skills/local-code-review/policies/pr-context.md).

## Default, conditional, or requested

**Conditional and automatic.** You do not request it. It applies only
when the current authenticated reviewer is the *same identity* as the
immediately preceding completed review **and** that review's reviewed SHA
resolves to a real commit in the PR's history. A different reviewer, no
prior review, or any ambiguity → a normal full review. It fails
conservative: an uncertain match never unlocks delta-only re-review.

## How to invoke it

Just re-run the review as the same reviewer:

```text
re-review PR #812
```

The Skill reports which mode it used — `Review mode: Delta re-review`
(with the previous and current SHAs) or `Review mode: Full review` (with
the reason).

## Limitations & safety boundaries

- A delta re-review **escalates to a full review** when the delta
  materially changes the implementation, expands scope, invalidates prior
  assumptions, or adds substantial new behavior. When in doubt, it
  escalates.
- A different reviewer **inherits PR/repository state and prior
  discussion, but never another reviewer's judgment** — prior findings
  are investigation evidence, not verified facts.
- This is distinct from Agent review *ownership*
  (`One review scope → one Code Review Agent owner`); both must hold
  independently.
- A changed HEAD re-classifies every prior human finding; an old approval
  never authorizes a new HEAD.

## Canonical semantics

[`skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md)
· `NO NEW DELTA` in
[`review-output.md`](../../skills/github-pr-review/policies/review-output.md),
"Final decision" ·
[`shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md)
· future stateful re-review work in
[`../findings/README.md`](../findings/README.md).
