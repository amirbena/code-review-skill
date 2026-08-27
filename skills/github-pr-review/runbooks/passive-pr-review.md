# Runbook — Passive PR Review

Reviews an existing GitHub Pull Request **without publishing anything**.
Applies shared policies:
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md),
[`evidence.md`](../../../shared/policies/evidence.md),
[`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
[`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
plus this Skill's own policy family starting at
[`github-review.md`](../policies/github-review.md).

## Flow

```text
resolve PR
    ↓
resolve authenticated identity and PR author
    ↓
same identity? → yes → REVIEW SKIPPED → stop
    ↓ no
resolve review mode (delta re-review vs. normal review)
    ↓
resolve optional supplied review context / GitHub Issue (if any)
    ↓
resolve changed files (incl. prior reviews / comments as Existing Review Evidence)
    ↓
discover applicable AGENTS.md / CLAUDE.md
    ↓
inspect diff and surrounding code (incl. scope-boundary reasoning)
    ↓
apply repository conventions
    ↓
produce findings
    ↓
return human-readable report
```

## Steps

1. Resolve the repository and PR from the given input (PR URL, PR number
   + repository context, or repository + PR number).
2. **Before any other step**, resolve the authenticated GitHub identity and
   the PR author and compare them, per
   [`../policies/review-authority.md`](../policies/review-authority.md),
   "Self-review capability." If they are the same account, terminate
   immediately with `REVIEW SKIPPED` — do not retrieve the diff, discover
   repository instructions, produce findings, or return a report. This
   applies to passive review exactly as it does to active review.
3. **Resolve review mode** per
   [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md),
   when prior review history is available to this invocation. If the
   current authenticated identity matches the reviewer of the immediately
   preceding completed review of this PR, and that review's reviewed SHA
   can be established reliably, this is a **delta re-review** bounded by
   that SHA and the current PR HEAD; otherwise (no previous completed
   review, a different reviewer, or any ambiguity in reviewer identity or
   the reviewed SHA) it is a **normal review**. If the previously reviewed
   SHA already equals the current PR HEAD, report `NO NEW DELTA` and stop
   rather than producing a redundant report.

   **If the caller supplied review context** (requirements, explicit user
   instructions, a Jira ticket, an explicitly supplied GitHub Issue, an
   HLD/ADR, an implementation plan) — or to use the PR description as intent
   — resolve and normalize it now per
   [`../policies/review-context.md`](../policies/review-context.md) and the
   shared [`review-context.md`](../../../shared/policies/review-context.md).
   Optional; absence changes nothing; it never changes the review mode,
   never widens the PR delta, and never adds a review target. No automatic
   PR↔Issue discovery.
4. Through an available authenticated GitHub integration, retrieve PR
   metadata and base/head SHA. For a normal review, retrieve the complete
   paginated changed-file set and a complete diff per
   [`../policies/pr-scope.md`](../policies/pr-scope.md), "Complete PR scope
   and pagination." For a delta re-review, retrieve the bounded delta
   between the previously reviewed SHA and the current PR HEAD, plus
   enough surrounding context to confirm the requested fix, absence of
   regression, and continued validity of the previous review's
   assumptions — escalating to a normal review and retrieving the
   remaining full scope if the delta meets any
   [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md)
   "Escalating from delta to full review" condition. If completeness
   cannot be established for the scope this mode requires, return an
   incomplete review state rather than claiming the full PR was reviewed.
   Where prior reviews, review comments, and issue comments on this PR are
   available, classify each relevant one as **Existing Review Evidence** per
   [`../policies/review-evidence.md`](../policies/review-evidence.md) and the
   shared [`review-evidence.md`](../../../shared/policies/review-evidence.md)
   — still-relevant, resolved, stale, duplicate, settled decision, or
   speculative discussion — without blindly inheriting it. Absent prior
   activity changes nothing.
5. **Discover applicable repository-local instructions** per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md):
   for each file in this invocation's scope, look for `AGENTS.md` /
   `CLAUDE.md` at the target repository root and along that file's
   directory ancestry, plus other relevant surrounding context (tests,
   contracts, schemas, architecture docs). Do this before reviewing so
   discovered conventions inform the review itself.
6. Review the diff against
   [`review-scope.md`](../../../shared/policies/review-scope.md) and the
   file-treatment rules in
   [`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
   applying the instructions discovered in step 5. When this invocation's
   scope contains multiple related changes, reason about them per
   [`../policies/review-reasoning.md`](../policies/review-reasoning.md),
   "Logical Cohort Review," and inspect the relevant dependency surface
   per "Code Impact / Dependency Analysis" in the same file. Target-repository
   instructions refine how the code is evaluated; they never override this
   Skill's own safety boundaries (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Instruction precedence"). When review context is available, also apply
   the shared
   [`review-context.md`](../../../shared/policies/review-context.md),
   "Scope-boundary reasoning," to the PR: detect required behavior missing
   from the PR, the PR contradicting acceptance criteria, unrelated scope
   expansion, a valid-but-out-of-scope finding, and repository-policy
   violations that hold regardless of the ticket's stated scope — using that
   policy's precedence notes, not a rigid priority order. Use the prior
   Existing Review Evidence classified in step 4 to avoid repeating a
   settled finding, contradicting a settled decision without concrete new
   evidence, or missing an unresolved previously identified issue that still
   holds against the current PR HEAD. For a delta re-review, if what is
   found here meets any "Escalating from delta to full review" condition in
   [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md),
   switch this invocation to a normal review and retrieve the remaining full
   scope before continuing.
7. Classify findings per
   [`severity.md`](../../../shared/policies/severity.md) with evidence per
   [`evidence.md`](../../../shared/policies/evidence.md), using the shared
   finding shape in
   [`finding.md`](../../../shared/templates/finding.md).
8. Finalize the complete set of findings before composing the report —
   do not report findings piecemeal as they are discovered. Render one
   human-readable report using the shared shape in
   [`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
   the same structure
   [`../templates/external-review-summary.md`](../templates/external-review-summary.md)
   uses for active review (as a plain-text/return-value report, not
   published to GitHub), with findings rendered per
   [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
   stating the review mode used per
   [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md),
   "Reporting the mode."

## Constraints

- No inline comments, Approve, Request Changes, or PR metadata mutation
  of any kind.
- If no available integration can retrieve the required PR state, report
  the missing capability explicitly rather than inventing PR state (see
  [`../policies/github-review.md`](../policies/github-review.md)).

This runbook is the safe default for inspecting a PR when active
publication is unnecessary, unavailable, or not yet authorized — see
[`active-pr-review.md`](active-pr-review.md) for when publication is
required.
