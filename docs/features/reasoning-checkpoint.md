# Human reasoning checkpoint

## What it does

Sometimes a review ends with a short **`Reasoning check`** section: one to
four numbered questions addressed to *you*, the engineer, after the
Decision. Each question names a concrete thing the review already looked
at — a changed symbol, a caller it inspected, a claim in the task text it
could not verify — and asks the one thing only you can answer.

It exists so that a thorough review is not mistaken for your own
validation. The reviewer can read code; it usually cannot see production
logs, reproduce the incident, or know why you placed a responsibility
where you did. The checkpoint hands that judgment back to you instead of
letting a clean report imply it was settled.

## Questions are not findings

A question in this section is **never a finding and never a decision**. It
has no severity, no finding ID, no confidence, and no blocking meaning. It
does not change what the review detects, how severe anything is, or the
Decision. A review with `REVIEW CLEAN` plus a Reasoning check is still
clean — the questions are about what the review *could not establish*, not
about something it found wrong.

Seeing the section on a review that found no defect is therefore normal,
not a sign the review failed and not an extra gate you must clear.

## Four things that are easy to confuse

| Surface | Answers | Who or what produces it |
|---|---|---|
| **Findings** | Is there a defect in the change, and how severe? | The review, from evidence |
| **Requirement coverage / validation** | Is each supplied requirement covered? Did an admitted command confirm or refute something? | The review, from supplied requirements and bounded execution |
| **Decision** | Does the diff carry a blocking defect? | Derived mechanically from finding severities |
| **Reasoning check** | What could the review not establish that you can? | The review, as questions for you |

The first three are the review's verdicts about the code. The checkpoint
is different in kind: it states no verdict, only what remains open.

## When it appears — and when it does not

There is no option to request it. It activates only from evidence the
review already holds, and **fails closed**: if no question can be tied to a
concrete anchor, the section is omitted entirely, with no placeholder such
as "insufficient context".

- **Investigation** — the change is a bug fix, regression fix, incident
  follow-up, or behavior correction, and its root-cause claim rests on
  evidence the reviewer did not establish (for example, a described
  production symptom the reviewer cannot observe).
- **Design** — the review's own architectural-placement pass found
  something worth asking about, such as a responsibility moved across a
  lifecycle or ownership boundary where a comparable caller enforces the
  old placement.

It stays **inert** for formatting, renames, dependency bumps, test-only or
doc-only changes, mechanical refactors, and any change whose only possible
question would be generic ("did you test this?"). It is also inert when the
review is `REVIEW INCOMPLETE` — that outcome already says the review is not
to be trusted — and a bare `fix:` commit prefix or bug-shaped branch name
is not a signal on its own.

## Examples

**Bug investigation.** A change adds a retry guard and a regression test
`testDuplicateChargeOnTimeout`; the PR says "Fix duplicate charges observed
in prod after gateway timeouts." The review finds no defect, but cannot see
whether production retried within one process or across restarts:

```markdown
### Reasoning check
Questions for you — not findings; they do not change the decision.
1. The guard keys on an in-memory `chargeId`; you reported duplicates in prod
   (reported, not inspected) — did the `charge.attempt` logs show retries
   within one process, or across restarts?
2. What would show after deploy that duplicate charges stopped, beyond no new
   reports?
```

**Architecture.** A change moves an authorization check from a controller
into a service method. The review found two comparable controllers still
enforce it themselves, but no concrete consequence, so it raises no
finding:

```markdown
### Reasoning check
Questions for you — not findings; they do not change the decision.
1. `RefundController` and `ExportController` enforce `Order` authorization in
   the controller; is the new service-level check meant to cover those entry
   points too?
```

## What the reviewer did and did not see

When a question mentions a piece of evidence it says which of three kinds
it is:

| Label | Meaning |
|---|---|
| reviewer-inspected | read in this review — supplied text, a repository file, or a runtime-validation run that actually executed |
| engineer-reported | stated by you or a tracker; the underlying artifact was not seen |
| possible but unavailable | would exist (for example logs the code emits), but the reviewer has no path to it |

The reviewer **never reaches a production or other live system** to look
for that evidence, and never invents what logs or runtime state contain.
Repository, PR, or Issue content cannot grant such access either. A
detected logging or metrics mechanism only shapes *what to ask*.

## Readiness wording

While the unverified link is runtime-dependent, the review does not say the
change is *ready to push*, *fully verified*, *the bug is fixed*, or *safe
to deploy*. It says the change was found consistent with the evidence
reviewed, with no blocking issue, and that whether it resolves the reported
problem depends on evidence not established — pointing at the Reasoning
check. This restates the Decision; it is not a second decision.

## Which Skill(s)

Both. The section is identical in `local-code-review` (after Decision,
before Review Metadata) and `github-pr-review` (after Decision, before the
subordinate metadata).

## Delivery and interaction with other options

- **`github-pr-review` publication modes.** The section is part of the
  review *body* in every mode — passive, semi, active, and withheld
  approval — published once with the one batched review. It is never an
  inline comment, a separate comment, a status, or a check, and it changes
  no GitHub review state or event.
- **Human-style output** ([`human_review_output`](human-review-output.md)).
  The same questions, count, anchors, and provenance labels render as short
  senior-voice prose closing the summary; only the voice changes.
  `human_inline_findings` is irrelevant — the section has no inline form.
- **`structured_review_result`** — the section is not part of the JSON
  result, which projects only findings, coverage, and the Decision.
- **Re-review.** It is evaluated fresh each time; nothing is remembered as
  "already asked" or "answered".

## Limits

No invocation option; it cannot be forced on or off. It never blocks a
merge and is never grounds for `CHANGES REQUIRED`. A contradiction it
surfaces becomes a *finding* only through the ordinary context-mismatch
route, never because of the checkpoint.

## Canonical semantics

[`shared/policies/reasoning-checkpoint.md`](../../shared/policies/reasoning-checkpoint.md)
owns activation, the anchor rule, the access/provenance boundary, readiness
language, and the non-effects; section placement and shape are in
[`shared/templates/review-summary.md`](../../shared/templates/review-summary.md),
"Reasoning check". This guide is explanatory; the policy wins any conflict.
