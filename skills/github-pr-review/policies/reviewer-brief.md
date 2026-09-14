# Policy — Reviewer Brief

Canonical semantics for the private, caller-facing `Reviewer Brief` every
`github-pr-review` result includes. Canonical index:
[`github-review.md`](github-review.md), which places this file
immediately after [`review-output.md`](review-output.md): the brief is
composed only once that file's "Analysis phase vs. publication phase" has
already produced the finalized findings, severity, coverage, and verdict.
Rendering shape: [`../templates/reviewer-brief.md`](../templates/reviewer-brief.md).

## What this is

A compact, private handoff so the human caller gets a fast mental model
of the PR and a focused checklist for manual review, in addition to the
public GitHub review surface. It is **not** another GitHub review body,
not review metadata, and not another verdict mode.

## Never published to GitHub

The Reviewer Brief is caller-facing only. It is never submitted as a
GitHub review body, inline comment, or Approve / Request Changes / COMMENT
event — under any active-mode path, any mode, any natural-language
request, or any authorization.

This is a **structural boundary, not a textual filter**: the publication
payload constructed by
[`review-output.md`](review-output.md), "Batched review construction and
submission," is built exclusively from
[`../templates/external-review-summary.md`](../templates/external-review-summary.md)
(the review body) and
[`../templates/inline-finding.md`](../templates/inline-finding.md)
(inline comments), plus the permitted event resolved by
[`review-action-authorization.md`](review-action-authorization.md).
[`../templates/reviewer-brief.md`](../templates/reviewer-brief.md) is
never one of those inputs, is never referenced by
`review-output.md`'s publication sections, and is never passed into the
"construct one review" step of either runbook
([`../runbooks/active-pr-review.md`](../runbooks/active-pr-review.md),
step 13; [`../runbooks/passive-pr-review.md`](../runbooks/passive-pr-review.md)
publishes nothing at all). The brief lives in a distinct part of the
returned result — appended to the caller-facing report after the
GitHub-shaped content, never merged into it — that the publication code
path never reads. No lint, redaction, or textual scrub is what keeps it
off GitHub; the publication construction step simply has no input that
could carry it there.

## Presentation over already-completed analysis

The brief is a **private presentation artifact over already-completed
review analysis** — it is not a new analysis or decision phase. It is
composed after findings, severity, coverage, and the verdict are already
finalized: it reads the finalized analysis result; it never influences
it. Composing the brief changes no finding, no severity, no coverage
signal, and no verdict, and it runs whether or not GitHub publication
ever happens.

## Required fields

```text
## Reviewer Brief

- What changed
- User-provided focus
- Manual review focus (2-4 bullets)
- Open questions / assumptions (only when useful — omit if empty)
```

- **What changed** — a 1-3 sentence synthesis grounded in the actual
  reviewed diff and repository context, not merely copied from the PR
  description. Concrete and specific: what a caller needs to build a
  mental model before reading the rest of the review.
- **User-provided focus** — the trusted caller-supplied review focus for
  this invocation, represented faithfully, or `none provided` when the
  caller supplied none. See "User-provided focus is an attention signal"
  below.
- **Manual review focus** — 2-4 high-value bullets naming code paths,
  architectural seams, invariants, compatibility surfaces, or runtime
  behavior that deserve human attention next. It **must not simply
  restate the findings list** — a bullet that only repeats a finding
  already reported adds nothing here.
- **Open questions / assumptions** — only when unresolved human judgment
  genuinely remains; omit the field entirely when there is nothing
  useful to say, never render it as an empty or placeholder line.

Keep it compact — a handoff, not a second report. Do not duplicate full
finding evidence/impact/fix blocks, and do not introduce `P0`/`P1`/`P2`
labels in this section unless referring to an actual finalized finding
already reported elsewhere.

## Synthesis sources

The brief synthesizes from:

1. the actual reviewed diff / change;
2. repository context discovered during review;
3. trusted user-provided review focus for the invocation (see
   [`review-context.md`](review-context.md) and the shared
   [`review-context.md`](../../../shared/policies/review-context.md));
   and
4. review-focus areas the reviewer independently infers from the diff and
   repository context, even when the caller did not mention them.

## User-provided focus is an attention signal, not authority over review truth

Trusted caller-supplied focus (natural-language instructions, a pasted
requirement, a Jira/Issue reference resolved per
[`review-context.md`](review-context.md)) shapes **attention and
wording** in the brief only. It:

- **cannot force a finding** into existence;
- **cannot lower the evidence bar** [`evidence.md`](../../../shared/policies/evidence.md)
  requires;
- **cannot change a finding's severity**
  [`severity.md`](../../../shared/policies/severity.md) derives;
- **cannot change coverage accounting**
  [`review-stopping-criteria.md`](../../../shared/policies/review-stopping-criteria.md)
  computes;
- **cannot change verdict derivation**
  [`review-output.md`](review-output.md), "Final decision," derives.

Caller focus that the code does not support is never blindly repeated as
if it were confirmed; the brief represents the actual change faithfully.
The reviewer independently adds important focus areas it derives from the
diff/repository even when the caller did not ask for them — the third
bullet in an example brief is often reviewer-derived, not caller-supplied,
and stays useful precisely because it goes beyond what the caller
mentioned. If caller focus conflicts with repository evidence, the
conflict stays out of finding/decision mechanics unless it independently
creates a defect (in which case it is a normal finding, not a Reviewer
Brief artifact).

## No leakage of hidden state

The brief must never expose:

- scratchpad or chain-of-thought reasoning;
- machine-only authorization state, secrets, or hidden runtime metadata;
- unpublished review internals beyond the compact fields above.

## Composition with invocation modes

- **Passive vs. active publication** — the same private brief semantics
  apply either way; passive review already publishes nothing, so the
  never-published guarantee is automatically satisfied there, and active
  review enforces it structurally as described above.
- **Self-review vs. independent review** — unchanged; the brief is
  produced identically regardless of review-action authorization mode.
- **`human_review_output` / senior rendering** — per
  [`review-output.md`](review-output.md), "Concise human-style summary
  (opt-in)," this option, and its companion `human_inline_findings`, may
  adjust the brief's **wording and compactness only** — never whether the
  brief exists, its required fields, or any boundary in this file. The
  same finalized brief semantics render either way; only prose changes.
- **Delta re-review** — per
  [`reviewer-delta-review.md`](reviewer-delta-review.md), the brief
  summarizes the reviewed delta, not the entire review history, and may
  note the previous-review context when materially relevant (e.g. what
  the prior review flagged and whether this delta addresses it). It is
  never a re-synthesis of the full PR history that was out of scope for
  this delta.
- **Stacked PRs** — per
  [`stacked-pr-review.md`](stacked-pr-review.md), the brief summarizes
  the effective reviewed layer — this PR's owned delta against the
  effective review base — not the entire stack. The lower stack remains
  read-only Repository Context for the brief exactly as it is for
  findings.
- **Large-PR partitioning** — per
  [`../../../shared/policies/large-pr-partitioning.md`](../../../shared/policies/large-pr-partitioning.md),
  the brief is synthesized **once**, over the final aggregated review
  target, after cross-partition aggregation and de-duplication complete —
  never once per partition, and never a dump of partition-level notes.

## Clean reviews still get a useful brief

A clean review (no findings) still renders a complete Reviewer Brief —
`What changed`, `User-provided focus`, and `Manual review focus` remain
populated with the reviewer's independently derived attention points.
The brief never implies a false positive by inventing a finding-shaped
concern; `Manual review focus` on a clean review still names concrete
code paths, seams, or invariants worth a human's attention, phrased as
areas to look at, not defects.

## Rendering

The exact shape, and worked examples for a clean review, a review with
findings, delta re-review, a stacked PR, and a partitioned large PR, are
owned by
[`../templates/reviewer-brief.md`](../templates/reviewer-brief.md).
