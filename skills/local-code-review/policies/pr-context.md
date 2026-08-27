# Policy — Optional PR Context (local application)

This Skill's **local application** of the shared Existing Review Evidence
model. The canonical semantics — what counts as existing review evidence,
"evidence and context, not authority," the still-relevant / resolved / stale
/ duplicate / settled-decision / speculative-discussion classification, the
settled-decision bar, and the read-only / decision-ownership / target
boundaries — are owned by
[`review-evidence.md`](../../../shared/policies/review-evidence.md) and are
not restated here. This file adds only what is specific to `local-code-review`:
the caller optionally supplies **a reference to an existing GitHub Pull
Request**, and its relevant prior findings, prior review comments, and settled
decisions are reconciled against the **local delta**, which always remains the
review target. [`../SKILL.md`](../SKILL.md) and
[`../runbooks/local-review.md`](../runbooks/local-review.md) state the
concise behavioral consequence and reference this file rather than
redefining it.

**If no PR reference is supplied, this file does not apply and nothing
in this Skill's behavior changes.** Everything below is additive and
strictly conditional on the caller providing one.

## Why this exists

An implementation branch often already carries relevant review history —
reviewer findings and settled architectural/design decisions from an
associated PR. Re-deriving all of that from a cold read of the code
wastes effort and risks silently contradicting a decision that was
already made deliberately. This policy lets `local-code-review` consume
that history as **context**, not as a second authority, so the local
delta stays the actual object of review.

```text
Local Delta
  +
Relevant PR Findings
  +
Relevant Settled Decisions
      ↓
 Reconciliation
      ↓
Remaining Local Review
      ↓
Final local-code-review decision
```

This is not a second complete review pass over the PR. It is a targeted
reconciliation step that narrows and informs the one local review this
Skill always performs.

## Input form

A PR reference may be:

- a full PR URL, or
- a PR number, when the target repository can be inferred unambiguously
  (for example, from a single configured `origin` remote).

If a bare PR number is given and the repository cannot be inferred
unambiguously (no remote, multiple plausible remotes, or an unclear
mapping), do not guess — treat the PR reference as unresolved per
"Unavailable or unresolved PR context" below.

## Capability

Reading PR review context requires read-only access to the relevant
GitHub data (PR conversation, review threads, review comments) through
whatever GitHub integration is available in the environment. This Skill
never gains, and must never exercise, any GitHub **write** capability
through this policy — see "Boundary with `github-pr-review`" below.

## Unavailable or unresolved PR context

If the PR reference cannot be resolved, the referenced PR does not
exist or is inaccessible, or no GitHub read capability is available:
note the limitation briefly in the report and proceed with the normal
local review exactly as if no PR reference had been supplied. A missing
or broken PR reference is never a reason to fail, block, or degrade the
local review itself.

## Ordering: local scope first

Establish the current local review scope/delta
([`../runbooks/local-review.md`](../runbooks/local-review.md), steps
1–4) **before** reading any PR context. The PR reference narrows and
informs the review of that already-established delta — it never expands
review scope to the PR's full historical diff, unrelated files, or
unrelated commits. A local delta review is never skipped or replaced
because a PR was supplied.

## Targeted retrieval

Retrieve only what is relevant to the current local delta:

- review threads and comments touching files, hunks, or symbols that
  overlap the current local delta, or that discuss design/architecture
  governing an area the local delta touches;
- enough surrounding thread context to understand whether a comment was
  resolved, superseded, or still stands.

Do not pull in, or reason over, irrelevant PR metadata: labels,
assignees, unrelated CI status, unrelated file comments, or discussion
about parts of the PR that do not overlap the current local delta. Do
not re-read the PR's full historical diff — the current local delta,
established per [`repository-state.md`](repository-state.md), is what
is actually reviewed.

### Retrieval (integration example)

Retrieval uses whatever authenticated GitHub read integration the
environment provides; what to do with the result is the shared Existing
Review Evidence model, not redefined here. One executable implementation:

```text
gh api --paginate repos/{owner}/{repo}/pulls/{pr}/reviews
gh api --paginate repos/{owner}/{repo}/pulls/{pr}/comments
gh api --paginate repos/{owner}/{repo}/issues/{pr}/comments
```

Keep only the reviews, comments, and threads that touch files, hunks, or
symbols in the current local delta, or that record a design decision
governing an area it touches; discard the rest unread. Review-thread
resolution state, where needed, comes from a GraphQL
`reviewThreads { isResolved }` query. An equivalent authenticated GitHub
integration is valid — this Skill is not bound to `gh`. If retrieval
returns nothing, is incomplete, or no integration is available, apply
"Unavailable or unresolved PR context" below.

### Authorship and resolved threads

Per the shared
[`review-evidence.md`](../../../shared/policies/review-evidence.md),
"Comment authorship: human review vs. automation output," automated / bot
comments provide observations only and never by themselves settle a design
decision. A resolved thread is evidence of a past conclusion, not proof the
current local delta is correct: if the delta reintroduces the defect a
resolved thread described, that is a **still present** finding, reported
with fresh evidence — the historical resolution does not suppress it.

## Classifying PR review context

Classify each relevant thread/comment into one category:

- **actionable defect/finding** — a reviewer identified a concrete
  problem;
- **architectural/design decision** — a design choice was explicitly
  discussed and a conclusion was reached;
- **implementation preference/suggestion** — a reviewer's stylistic or
  non-blocking preference, not agreed as a requirement;
- **informational comment** — explanation, context, or non-actionable
  remark;
- **resolved or obsolete feedback** — already addressed, retracted, or
  superseded by later discussion.

Not every PR comment is a finding. Reason over each thread as a whole —
a conversation's conclusion governs, not any single comment read in
isolation. When a thread contains exploratory back-and-forth followed by
an explicit resolution or agreed conclusion, the resolution/conclusion
governs; earlier exploratory comments in the same thread are context for
it, not independent findings.

## Reconciling existing reviewer findings

For each relevant actionable finding from PR context, determine its
status against the **current local delta** (never against the
historical PR state at the time the comment was made):

- **still present** — the condition the finding described still holds
  in the current local delta;
- **resolved** — the current local delta no longer exhibits it;
- **requires re-evaluation** — the surrounding code changed enough that
  the original finding's applicability is no longer clear from the PR
  context alone;
- **outside the current local review scope** — relevant to the PR but
  not to any part of the current local delta.

Reuse the existing reviewer's evidence where it still applies instead of
re-deriving the same observation from scratch. Do not automatically
inherit their conclusion, severity, or decision — this Skill still
independently applies [`severity.md`](../../../shared/policies/severity.md)
and [`evidence.md`](../../../shared/policies/evidence.md) to reach its own
finding. **Existing reviewer findings are evidence and context, not
authority.**

### Avoiding duplicate findings

- A still-valid existing finding that maps onto the current local delta
  is reconciled/referenced in this Skill's own finding for that issue —
  it is not additionally reported as a separate, newly discovered
  finding for the same underlying problem.
- A materially different issue discovered in the same file/area is
  reported as its own separate finding.
- Do not create two findings for one underlying issue merely because
  both the PR reviewer and this review independently noticed it.

## Architectural/design decisions

A settled architectural/design decision found in PR context is **decision
context**, not an unresolved finding to reopen.

A decision is settled only when the PR context provides sufficient
evidence it was actually agreed upon — an explicit conclusion, an
accepted/resolved thread, or an unambiguous resulting direction. A
single reviewer's stated opinion, an unresolved suggestion, or one side
of an unfinished disagreement is not a settled decision; treat it as an
implementation preference/suggestion instead (see "Classifying PR review
context" above).

For each settled decision relevant to the current local delta, determine
whether the delta:

- **follows** the decision — no finding, no note needed beyond what the
  report already says;
- **intentionally supersedes** it with newer explicit evidence — no
  finding; briefly note the supersession only if it materially affects
  the reasoning shown in the report;
- **accidentally violates or regresses** it — report this as a finding,
  per the severity that violation actually warrants.

Do not reopen a settled decision merely because this review would
personally have preferred a different design. A settled decision may
only be challenged when the current local delta carries concrete new
evidence, such as: changed requirements, a correctness or reliability
problem, an invalidated assumption, a newly discovered dependency or
constraint, a material security/performance concern, or a newer explicit
architectural decision found in the same PR context. Absent such
evidence, an accidental violation of a settled decision is reported as a
finding; a considered, evidenced departure from it is not.

Do not treat every reviewer opinion as an architectural constraint —
only conclusions that meet the "settled" bar above.

### Decision provenance

When reporting on a settled decision (only when doing so is materially
relevant — see "Output" below), preserve enough to be useful:

- what was decided;
- which part of the code/design it governs;
- why, if the rationale is available in the thread;
- that it was explicitly accepted/resolved;
- whether the current local delta still falls under it.

This is provenance sufficient to avoid contradicting the decision by
accident — not an instruction to produce standing architecture
documentation from PR history.

## Output

Do not add output noise. Resolved findings and preserved (followed or
intentionally superseded) decisions are not listed individually unless
they materially affect the reasoning, scope, or final decision shown in
the report. When PR context materially shaped the review, state it
concisely — which existing findings were reconciled as still valid
(referenced from this review's own findings, not duplicated), and
whether any architectural decision was violated (reported as a finding)
or superseded (briefly noted). The report's existing shape and decision
labels (`REVIEW CLEAN` / `CHANGES REQUIRED`) are unchanged by this
policy — see
[`../templates/local-review-report.md`](../templates/local-review-report.md).

## Boundary with `github-pr-review`

This policy adds **read-only context retrieval** to `local-code-review`.
It does not turn this Skill into a PR reviewer:

- no inline PR comments, no GitHub review submission, no Approve/Request
  Changes decision, no PR-level GitHub mutation of any kind — this
  Skill's [mutation boundary](../SKILL.md) is unchanged;
- the review scope remains the current local delta, never the PR's
  complete historical diff;
- this Skill's own final severity and `REVIEW CLEAN` /
  `CHANGES REQUIRED` decision for the current local delta remains this
  Skill's own — reconciled PR findings and decisions inform it, they
  never substitute for it;
- [`invocation-approval.md`](invocation-approval.md) is unchanged and
  fully in force: supplying a PR reference is never itself approval to
  invoke this Skill, and never bypasses the per-invocation,
  current-interaction, explicit-approval requirement.

If genuine PR-level review (publishing findings, an Approve/Request
Changes decision, or reviewing another author's full PR) is what's
actually wanted, that is the sibling `github-pr-review` Skill's
responsibility, not this policy's.
