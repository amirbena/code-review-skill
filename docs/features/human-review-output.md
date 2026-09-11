# Human-style review output

## What it does

Renders the **final human-facing summary** in a concise senior-engineer
voice instead of the default structured shape: a short opening on merge
safety and the top concern, then *what's good / what's concerning / what
to change* in prose, each referenced finding keeping its `P0` / `P1` /
`P2` label, an intentional trade-off optionally raised as a question, and
no review-process or machine metadata.

It is normalized internally to the `human_review_output` option (default
`false`).

## When it is useful

- You want a short, readable verdict to paste into a chat or a PR
  description rather than a full report.
- You are skimming many reviews and want each one to lead with the
  bottom line.

## Which Skill(s)

Both. `local-code-review` re-renders the returned report's summary body;
`github-pr-review` re-renders the final review summary comment (and the
self-review informational `COMMENT`). Inline comments still carry each
finding's full detail — in the structured `Evidence` / `Impact` / `Fix`
shape, or in the same senior voice when the companion option below is on.

For `github-pr-review` specifically, `human_review_output` also re-voices
any finding that is rendered **in full in the review body** rather than
inline — every finding in a passive review (passive has no inline
surface), and an active-review finding with no valid inline anchor. This
keeps a senior-mode review coherent across passive and active alike: a
finding never reads structured on one surface and senior on another. See
[`shared/templates/finding-rendering.md`](../../shared/templates/finding-rendering.md),
"Canonical human full rendering."

## Companion option: `human_inline_findings`

`human_inline_findings` extends the senior-engineer voice to
`github-pr-review`'s **inline** review comments, so a senior-mode review
reads coherently end to end. A human-rendered inline finding is a short
heading that keeps the `P0` / `P1` / `P2` severity and names the concrete
finding, followed by compact prose that carries the evidence, the
engineering consequence, and the correction direction — without the
`Evidence:` / `Impact:` / `Fix:` labels:

```text
P2: Retry eligibility logic is duplicated

The same eligibility decision is implemented in both flows, so the
behaviour can drift when one path changes and the other is missed. I'd
centralise it behind one helper and have both flows call that.
```

Its default is **derived** — `explicit_value ?? human_review_output` — so
enabling senior mode enables it too; you only state it explicitly to opt
out or to opt in on its own:

| Invocation | Summary | Inline findings |
| --- | --- | --- |
| default | structured | structured template |
| `human_review_output` on, no inline override | senior voice | senior voice |
| `human_review_output` on + `human_inline_findings=false` | senior voice | structured template |
| `human_review_output` off + `human_inline_findings=true` | structured | senior voice |

It is presentation-only in exactly the same way: finding detection,
severity, identity, deduplication, evidence and remediation, the
mechanical decision, the GitHub review state, the batched single
submission, the canonical fix/action anchor, and the `#164` / `#165`
body-fallback behaviour are all unchanged — structured and human are two
renderings of one semantic finding.  `local-code-review` has no
inline-comment surface, so it is inert there.

## Default, conditional, or requested

**Explicitly requested, in natural language — there is no CLI flag.** It
is recognised from a small, fixed vocabulary of phrases, for example:

- affirmative: *"make the review shorter and more human"*, *"review it
  like a senior engineer"*, *"use concise review comments"*, *"senior
  review"*, *"senior code review"*, *"senior PR review"*, *"review this
  as a senior"*;
- negative: *"keep the full summary"*, *"do not shorten the review"*,
  *"structured format"*.

The complete authoritative phrase set lives in
[`shared/policies/invocation-options.md`](../../shared/policies/invocation-options.md),
"`human_review_output` phrasings". Anything outside that vocabulary —
"make it nicer", "be brief", a question about the option — is ambiguous
and does **not** set it. A forwarded canonical
`human_review_output=true|false` assignment is also honored.

## How to invoke it

```text
review my local changes and keep the summary short and more human
review PR #812 like a senior engineer
review #812 and use concise review comments
```

The option is normalized from the **current invocation only** — it never
carries over to a later review or re-review in the same conversation.

**Publishing a previously produced passive review.** If you ask
`github-pr-review` to publish or post a review it already produced
passively (e.g. "publish it" after seeing a passive result), and that
publish request doesn't itself state a presentation, it asks once —
Senior/human or Structured — before publishing, offering whichever
presentation the passive result was actually shown in as the recommended
choice, but never applying it silently. State the presentation directly
in the same request (`review #123 and publish it like a senior
engineer`, or `... in structured format`) to skip the question. See
[`skills/github-pr-review/policies/review-output.md`](../../skills/github-pr-review/policies/review-output.md),
"Publishing a previously produced passive review."

## Limitations & safety boundaries

- **Presentation only.** Mode on and mode off produce identical findings,
  severities, finding identity, deduplication, the mechanically derived
  verdict, the GitHub review state (`APPROVE` / `REQUEST_CHANGES` /
  `COMMENT`), canonical fix/action anchors, placement (inline vs. body),
  any machine-readable status, and the publication order. Only wording
  changes — the final summary always, any `github-pr-review` body/fallback
  finding when `human_review_output` is on, and (under
  `human_inline_findings`) the inline comments.
- `human_review_output` alone does not alter *inline* comments; that is
  the companion `human_inline_findings` (on by default under senior
  mode), which is scoped to the inline surface only and never governs a
  body/fallback finding's wording. Neither removes the trailing
  machine-metadata block from the local report — that block still
  follows the summary unchanged.

## Canonical semantics

[`shared/policies/invocation-options.md`](../../shared/policies/invocation-options.md),
"`human_review_output` phrasings" ·
[`shared/templates/review-summary.md`](../../shared/templates/review-summary.md),
"Concise human-style summary (opt-in)" ·
[`skills/github-pr-review/policies/review-output.md`](../../skills/github-pr-review/policies/review-output.md),
"Concise human-style summary (opt-in)".
