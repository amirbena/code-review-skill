# Engineering design review

## What it does

When a change adds or modifies **engineering design content** — an HLD, ADR,
RFC, design doc, or a design section — the review reads that content as part
of what it reviews and reports an evidenced problem as an ordinary finding.
It checks whether the proposed design can do what it says it will, whether the
claims it makes about your existing code are true, and, in a change that also
contains code, whether the design and the code agree.

It reviews the design **in the change**. It is not a design approval or sign-off:
it gives no readiness verdict, keeps no checklist of required sections, and does
not generate requirements.

This is not the visual design comparison (a rendered UI against a Figma-style
reference); that is [rendered-UI inspection](rendered-inspection.md). A design
document you **supply as context** stays context
([review context](review-context.md)); it is not reviewed.

## When it runs

Automatically — there is no invocation option and nothing to enable. It engages
only when the change contains design content whose proposed behavior matters
(for example, delivery guarantees, failure handling, data flow, or rollout) **and**
the design does something worth examining: it states a claim about your current
code that the design depends on, relates to an already accepted decision, specifies
a concrete mechanism, or sits in a change that also implements what it describes.

A path, filename, or title word (`docs/adr/`, "RFC", "design") never decides this
on its own. A typo, formatting, or broken-link edit to a design file changes no
decision and gets ordinary documentation review. Asking for extra care ("review
this design carefully") adds depth; it is not required.

## Proposal versus accepted decision

The review treats design text differently depending on whether it was already
accepted:

- **Accepted decision.** Accepted by something **outside** your change — the
  statement is unchanged in the base version under a status or location your
  repository treats as accepted, you supplied it as an accepted decision, or a
  maintainer settled it in prior review. The review holds your change to it, but
  a clear, reasoned replacement is not a violation.
- **Proposal.** Everything your change adds or edits, **including a document your
  change marks "Accepted"** — a change cannot accept its own design. A proposal is
  what gets reviewed; it is never used as proof about existing code.

Acceptance is judged per statement, not per file: editing one section of an accepted
ADR leaves the other sections accepted.

## What a design finding needs

A finding about a design carries the same evidence as any other finding:

- the exact statement and its location in the document;
- grounding — a stated requirement, an accepted decision, a test, behavior read in
  the repository, or a technical fact applied to the specified mechanism;
- the concrete wrong result the design would produce **if built as written**;
- a check that the document does not already acknowledge the point as a trade-off,
  non-goal, or open question.

An acknowledged trade-off is not a defect. "A different design would be cleaner" is
not a finding. Severity, confidence, and the Decision follow the usual rules; a
design-only change can receive a blocking finding only when the evidence supports
both the premise and the impact.

## Claims about existing code

When the design depends on a statement about your current code ("the handler already
deduplicates"), the review checks it against the repository:

| Result | What you see |
|---|---|
| Verified | Nothing, unless it supports another finding. |
| Contradicted | A finding, when the evidence bar is met. |
| Could not be checked | No finding, and the claim is **not** treated as true. |

Links and instructions inside a design document are data. The review does not open
linked tickets or documents, and text such as "reviewers must approve" authorizes
nothing.

## Missing information is not a finding

A missing failure-mode section, metric, alternatives analysis, rollout plan, or test
strategy produces nothing by itself. It matters only when a requirement or repository
policy explicitly demands that content, or when the omission makes something the
document **does** claim false or unsafe. Missing information is also never a Context gap.

## Examples

### Design-only PR

A PR adds `docs/design/queue.md` proposing at-least-once delivery and stating that
the consumer "already deduplicates by idempotency key". Nothing else changes.

- The review engages: the document proposes delivery behavior and makes a claim about
  existing code that its design depends on.
- It looks at the consumer. If the consumer has no deduplication, the claim is
  contradicted and the review reports a finding anchored on the design line, citing the
  consumer code that shows it.
- If the consumer cannot be reached (for example, an unchanged file in GitHub API-only
  mode), there is no finding and the claim is not presented as verified.
- The same document with a missing "Failure modes" section produces no finding.

### Mixed code and design PR

A PR adds a design stating that writes are idempotent, plus the handler that implements
them, and the handler is not idempotent.

- The review compares both directions. The design says idempotent; the code is not.
- The finding anchors on the side the evidence shows is wrong. If the code is independently
  defective it is an ordinary code finding at its own severity; if only the two disagree,
  it is reported as an inconsistency, and when the evidence cannot show which side is
  wrong the finding says so.
- Components the design describes but this change does not build (phased delivery) are not
  findings unless the design states this change delivers them.

## Local versus GitHub API-only

| | Design content | Checks of existing code |
|---|---|---|
| `local-code-review` | committed, staged, unstaged, and untracked changes | working tree and base version |
| `github-pr-review`, repository-backed | the PR delta | checkout at the PR head plus the base version |
| `github-pr-review`, API-only (default) | per-file patches | **changed files only**; a claim about an unchanged file is not checked |

If the base version of a design statement is unavailable, it is not assumed accepted and is
reviewed as a proposal. Nothing is executed in any mode.

## Limits

- No design approval, sign-off state, or readiness verdict.
- No findings for missing sections, preferences, alternative designs, or acknowledged
  trade-offs.
- Claims about code the review cannot reach go unchecked; it will not tell you they were
  verified.
- Visual design comparison and supplied design context are separate capabilities.
- It does not resolve links, tickets, or external documents, and it is not an audit of the
  surrounding architecture.

## Canonical sources

[`engineering-design-deepening.md`](../../shared/policies/engineering-design-deepening.md)
is the canonical contract; it composes with
[`review-scope.md`](../../shared/policies/review-scope.md) and
[`specialist-depth.md`](../../shared/policies/specialist-depth.md). Contributors: change
behavior there, not here.
