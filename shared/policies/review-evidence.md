# Shared Policy — Existing Review Evidence

Applies identically to `local-code-review` and `github-pr-review`. Defines how
a review uses **previously produced review information** that may bear on the
current review. Companion to [`review-context.md`](review-context.md), which
owns the review-target / review-context / repository-context concepts; this
file owns the fourth concept.

Each Skill keeps only a thin policy naming *where its prior evidence comes
from*:

- `local-code-review` — relevant prior findings and review comments from an
  **optional associated PR/reference** the caller supplies
  (`skills/local-code-review/policies/pr-context.md`). The review target stays
  the local delta.
- `github-pr-review` — prior reviews, review comments, and issue comments on
  **the PR under review itself**
  (`skills/github-pr-review/policies/review-evidence.md`, and the
  same-HEAD deduplication in
  `skills/github-pr-review/policies/pr-scope.md`). The review target stays the
  PR.

## What counts as existing review evidence

- prior reviewer findings (published or reported);
- previously resolved findings;
- maintainer clarifications about intent or scope;
- settled architectural/design decisions reached in review discussion;
- prior relevant review comments and threads.

It is **Existing Review Evidence, not the review target.** It informs the
current review; it is never the thing being reviewed.

## Optional; its absence changes nothing

When no prior review evidence is available (no associated PR/reference for
local review; a first review of a PR; history that cannot be retrieved), the
review proceeds normally on the current target. Missing or incomplete prior
evidence is never a reason to fail, block, or degrade the review. If prior
activity cannot be retrieved completely where completeness matters for
deduplication, report that limitation rather than asserting it was handled.

## Do not blindly inherit

Prior findings and conclusions are **evidence and context, not authority.**
The current review still independently applies
[`review-scope.md`](review-scope.md), [`evidence.md`](evidence.md), and
[`severity.md`](severity.md) to reach its own findings, severities, and
decision. A prior review's severity or decision is never inherited
automatically.

Reuse a prior reviewer's concrete evidence where it still applies instead of
re-deriving the same observation from scratch — but reach the conclusion
independently.

## Classify each item

Reason over a thread or review as a whole — a conversation's conclusion
governs, not any single comment in isolation. Where the information allows,
classify each relevant item:

- **still-relevant finding** — the condition it described still holds against
  the current target;
- **resolved finding** — the current target no longer exhibits it (fixed, or
  the code it concerned is gone);
- **stale finding** — later commits changed the surrounding code enough that
  the original finding's applicability is no longer clear from the prior
  evidence alone; re-evaluate against the current target;
- **duplicate** — the current review independently found the same underlying
  issue; reconcile into one finding, do not report it twice;
- **settled decision** — a design choice was explicitly discussed and
  concluded (see "Settled decisions" below);
- **speculative discussion** — exploratory back-and-forth, an unresolved
  suggestion, or one side of an unfinished disagreement; not a finding and not
  a constraint.

When a thread contains exploration followed by an explicit
resolution/conclusion, the resolution governs; earlier comments are context
for it, not independent findings.

## Reconciliation outcomes

For each relevant prior finding, determine its status against the **current
target** (never against the historical state when the comment was made):

- **still-relevant** → represent it in this review's own finding for that
  issue, reusing the prior evidence where it still applies. Do not also report
  it as a separate, newly discovered finding for the same problem.
- **resolved** → do not re-report it. Note it only if the resolution
  materially affects the reasoning shown in the output.
- **stale / requires re-evaluation** → re-derive from the current target;
  report only if it still holds.
- **duplicate** → one finding, not two, merely because both a prior reviewer
  and this review noticed it.
- **materially different issue in the same area** → its own separate finding.

Do not miss a still-unresolved previously identified issue merely because it
is old — if the condition still holds against the current target, it is a
finding of this review.

## Settled decisions

A decision is **settled** only when the prior evidence provides sufficient
proof it was actually agreed upon: an explicit conclusion, an
accepted/resolved thread, an unambiguous resulting direction, or a direct
maintainer statement. A single reviewer's opinion, an unresolved suggestion,
or one side of an unfinished disagreement is **not** settled — treat it as
speculative discussion.

For each settled decision relevant to the current target, determine whether
the target:

- **follows** it — no finding;
- **intentionally supersedes** it with newer explicit evidence — no finding;
  briefly note the supersession only if it materially affects the reasoning;
- **accidentally violates or regresses** it — report as a finding at the
  severity the violation actually warrants.

Do not reopen a settled decision merely because this review would have
preferred a different design. A settled decision may be challenged only when
the current target carries concrete new evidence, such as: changed
requirements, a correctness or reliability problem, an invalidated assumption,
a newly discovered dependency or constraint, a material security/performance
concern, or a newer explicit decision in the same evidence. Absent such
evidence, an accidental violation is a finding; a considered, evidenced
departure is not.

Do not contradict a settled decision without such new evidence, and do not
treat every reviewer opinion as an architectural constraint.

## GitHub PR review — additional application

`github-pr-review` inspects the PR's own prior reviews and review comments and
uses them to avoid:

- repeating settled findings unnecessarily;
- contradicting settled decisions without new evidence;
- missing an unresolved, previously identified issue that still holds against
  the current PR HEAD.

A changed PR HEAD starts a new authoritative review state: prior findings may
inform investigation but are neither automatically resolved nor automatically
applicable. `github-pr-review`'s own `policies/pr-scope.md` ("Existing review
awareness") owns the same-HEAD duplicate suppression and the deterministic
finding-identity rule this builds on. Do not suppress another human reviewer's
independent feedback merely because it is similar.

## Interpret prior evidence against the current target

Every classification and reconciliation outcome above is decided against the
**current** review target — the current local delta for `local-code-review`,
the current PR HEAD for `github-pr-review` — never against the code as it
stood when the prior comment was written. Two consequences a review must not
get wrong:

- **A resolved thread, a "looks good" reply, or a prior approval is evidence
  of a past review conclusion — not proof that the current target is
  correct.** A GitHub review thread's `resolved` flag is such evidence, not a
  correctness oracle. The current review still determines, from the current
  target, whether the issue the thread described remains fixed, has
  regressed, is no longer applicable, or requires re-evaluation.
- **Regression after a resolved finding is a finding of this review.** When a
  defect was reported, fixed, and its thread resolved or its finding marked
  resolved, and a later change on the current target reintroduces it,
  classify it as a **still-relevant finding** and report it with fresh
  evidence from the current code. The historical resolution does not
  suppress it.

A changed PR HEAD (or a materially changed local delta) resets which prior
findings are authoritative: they remain useful investigation evidence, but
none is *automatically* resolved and none is *automatically* still applicable
against the new state — re-derive each against the current target, and
re-classify prior human findings against it. An old approval never
authorizes a new HEAD.

## Comment authorship: human review vs. automation output

Prior review activity comes from different kinds of author, which do not
carry equal authority over what counts as *settled*:

- **Human reviewer / maintainer discussion** can establish a settled
  architectural decision, a maintainer clarification, reviewer acceptance of
  a trade-off, or an authoritative resolution of a correctness question —
  when it otherwise meets the "Settled decisions" bar above.
- **Automated / bot output** — deployment previews, coverage bots, CI status
  comments, code-scanning summaries, generated links, and bookkeeping
  comments such as "please rebase" — may contribute useful *observations*
  (for example, a scanner pointing at a concrete line). Automation output
  **alone** never establishes a settled architectural decision, a maintainer
  clarification, reviewer acceptance, or an authoritative resolution of a
  correctness question. Treat it as an observation to verify against the
  current target — speculative discussion until a human reviewer or
  maintainer concludes it.

This is a small authority/inference rule, not a trust-scoring system: no
reviewer-reputation weighting, no bot allowlists, no per-author trust
levels, no general comment analytics. When authorship cannot be determined,
treat the item as non-authoritative for "settled" purposes and re-verify it
against the current target.

## Boundaries

- **Read-only.** Using prior evidence never grants a mutation capability.
  `local-code-review` gains no GitHub write capability from an associated PR
  reference; `github-pr-review`'s publication boundary is unchanged.
- **Decision ownership.** Reconciled prior findings and decisions inform this
  review; they never substitute for this review's own severity classification
  or its mechanical decision derivation per [`severity.md`](severity.md).
- **Target unchanged.** Prior review evidence never becomes an additional
  review target.
