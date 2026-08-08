# Policy — Reviewer Delta Re-Review

Governs *review-mode* selection (delta re-review vs. normal review) for a
single already-owned PR review. Canonical index:
[`github-review.md`](github-review.md). Distinct from the Agent-level
`One review scope → one Code Review Agent owner` invariant in the shared
[`review-ownership.md`](../../../shared/policies/review-ownership.md)
policy.

Delta-only re-review is allowed only when the current reviewer owns the
immediately preceding review context. A different reviewer must
independently review the current PR state.

This check runs after the self-review guard in
[`review-authority.md`](review-authority.md), "Self-review capability"
(which remains authoritative and terminates first, before this check
ever runs) and before this invocation's review scope is established, so
the outcome determines *how much* of the PR this invocation reviews —
never *whether* it reviews at all, and never a bypass of the self-review
guard.

```text
Resolve current reviewer
        ↓
Apply self-review guard
        ↓
Inspect previous completed review
        ↓
Same reviewer?
   ├─ yes → delta re-review
   └─ no  → normal PR review
```

## Reviewer identity

Use the strongest repository/GitHub evidence available: the
authenticated GitHub identity for the current invocation, and the
reviewer identity recorded on the immediately preceding **completed**
review of this same PR (a submitted GitHub review, not a draft/pending
review, a general issue comment, or an inline comment alone). Never
infer reviewer ownership from task wording, branch name, commit author,
local Git identity, the mere presence of prior comments, or the fact
that a prior review exists at all — none of these establish that the
*current* authenticated reviewer is the same identity as the *previous*
reviewer.

If the current or previous reviewer identity cannot be established with
confidence, or the mapping is ambiguous (for example, more than one
plausible "immediately preceding" review, or an identity that cannot be
resolved to a concrete account), default to normal full review. Fail
conservative — an uncertain match must never unlock delta-only
re-review.

## Selecting the immediately preceding review

When multiple prior reviews exist, use only the immediately preceding
completed review in this PR's review sequence — never an arbitrary
earlier review merely because its author happens to match the current
reviewer. A review still in draft/pending state is not a completed
review for this purpose.

## No previous review

If this PR has no previous completed review, perform a normal full
review. There is no prior reviewer context to own.

## Same reviewer: delta boundary and scope

When the current reviewer is the same identity as the immediately
preceding completed review's reviewer, and that review's reviewed commit
SHA can be established reliably, the delta this invocation reviews is:

```text
previously reviewed SHA → current PR HEAD
```

Never define this boundary merely as the latest commit, the last push,
the last local commit, or "commits since task start" — it must come from
the previous review's own recorded state. Review that delta, plus enough
surrounding context to confirm the requested fix is correct, no
regression was introduced, and the previous review's assumptions still
hold. A delta re-review does not require repeating the full-PR retrieval
described in [`pr-scope.md`](pr-scope.md), "Complete PR scope and
pagination" — that requirement governs a normal full review's scope, not
a bounded delta re-review's.

If the previously reviewed SHA cannot be established reliably (missing,
ambiguous, or not resolvable to a real commit in this PR's history),
perform a normal full review instead of guessing a boundary.

If the previously reviewed SHA equals the current PR HEAD, there is no
new delta to review: do not manufacture a new review. This is the `NO
NEW DELTA` outcome in [`review-output.md`](review-output.md), "Final
decision" — this Skill does not resubmit a duplicate review for a HEAD
this same reviewer already completed.

## Escalating from delta to full review

A delta re-review is not automatically the complete review. Escalate to
a normal full review of the current PR state when the delta:

- materially changes the implementation from what the previous review
  assessed;
- expands scope beyond what the previous review covered;
- invalidates assumptions the previous review relied on;
- introduces substantial new behavior; or
- otherwise makes the previous review no longer representative of the
  current PR.

When in doubt, escalate — a missed full review is recoverable; a delta
review that silently inherited invalid assumptions is not.

## Different reviewer: normal review, no inherited judgment

When the current reviewer did not perform the immediately preceding
review, this invocation is a normal review of the current PR state, not
delta-only re-review. The current reviewer inherits PR state, repository
state, prior discussion, and resolved/unresolved review context — all
ordinary, already-established inputs to this Skill's review (see
[`pr-scope.md`](pr-scope.md), "Existing review awareness"). The current
reviewer does not inherit another reviewer's judgment: previous findings
and conclusions are not already-verified facts merely because a prior
review exists. Independently inspect the full relevant PR change and
reach independent conclusions; prior reviews may inform investigation but
never substitute for it.

## Reporting the mode

State which mode was used concisely in the human-facing review, per
[`../templates/external-review-summary.md`](../templates/external-review-summary.md):

```text
Review mode: Full review
Reason: current reviewer differs from previous reviewer
```

or

```text
Review mode: Delta re-review
Previous reviewed SHA: abc1234
Current HEAD: def5678
```

Keep this concise and human-facing; do not expose additional internal
identity/matching machinery as primary output — machine metadata about
review mode follows the same "Machine metadata is subordinate" rule as
the rest of the review body.
