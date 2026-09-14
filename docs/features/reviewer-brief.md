# Reviewer Brief

## What it does

Every `github-pr-review` result — passive report or active publication —
includes a compact, **private, caller-facing** `Reviewer Brief` in
addition to the public GitHub-shaped review:

```markdown
## Reviewer Brief

- **What changed:** <1-3 sentence synthesis of the actual change>
- **User-provided focus:** <trusted caller focus, or `none provided`>
- **Manual review focus:**
  - <highest-value area to inspect manually>
  - <second area when materially useful>
- **Open questions / assumptions:** <only when unresolved human judgment remains>
```

It gives the human caller a fast mental model of the PR and a focused
checklist for their own manual review, synthesized from the reviewed
diff, repository context, any trusted user-provided focus, and areas the
reviewer independently infers as worth attention.

## When it is useful

- You still intend to do a human review after the Skill's analysis
  finishes, and want a compact starting point instead of re-deriving one
  from the findings list.
- You told the Skill what to focus on and want confirmation it was heard
  — plus what it noticed beyond that.

## Which Skill(s)

`github-pr-review` only (explicit non-goal for `local-code-review`).

## Default, conditional, or requested

**Always on** — every result includes it; there is no opt-out. Only its
wording/compactness changes under
[human-style output](human-review-output.md).

## Limitations & safety boundaries

- **Never published to GitHub.** Not the review body, not an inline
  comment, not part of an Approve / Request Changes / informational
  COMMENT submission — under any mode, in any invocation.
- **Presentation, not analysis.** Composed only after findings, severity,
  coverage, and the verdict are already finalized; it never changes any
  of them.
- **User-provided focus is an attention signal only.** It shapes what the
  brief highlights and how it is worded; it cannot force a finding, lower
  the evidence bar, change severity, change coverage accounting, or
  change verdict derivation.
- Identical semantics in passive vs. active review and self-review vs.
  independent review. Delta re-review summarizes the reviewed delta;
  stacked PRs summarize the effective reviewed layer; a partitioned
  large PR gets one brief over the final aggregated result.

## Canonical semantics

[`skills/github-pr-review/policies/reviewer-brief.md`](../../skills/github-pr-review/policies/reviewer-brief.md) ·
[`skills/github-pr-review/templates/reviewer-brief.md`](../../skills/github-pr-review/templates/reviewer-brief.md) ·
[`skills/github-pr-review/policies/review-output.md`](../../skills/github-pr-review/policies/review-output.md),
"Private Reviewer Brief (never published)".
