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
finding's full detail.

## Default, conditional, or requested

**Explicitly requested, in natural language — there is no CLI flag.** It
is recognised from a small, fixed vocabulary of phrases, for example:

- affirmative: *"make the review shorter and more human"*, *"review it
  like a senior engineer"*, *"use concise review comments"*;
- negative: *"keep the full summary"*, *"do not shorten the review"*.

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

## Limitations & safety boundaries

- **Presentation only.** Mode on and mode off produce byte-identical
  findings, severities, deduplication, the mechanically derived verdict,
  the GitHub review state (`APPROVE` / `REQUEST_CHANGES` / `COMMENT`),
  inline comments, any machine-readable status, and the publication
  order. Only the wording of the final summary changes.
- It does not shorten or alter inline comments, and it does not remove
  the trailing machine-metadata block from the local report — that block
  still follows the summary unchanged.

## Canonical semantics

[`shared/policies/invocation-options.md`](../../shared/policies/invocation-options.md),
"`human_review_output` phrasings" ·
[`shared/templates/review-summary.md`](../../shared/templates/review-summary.md),
"Concise human-style summary (opt-in)" ·
[`skills/github-pr-review/policies/review-output.md`](../../skills/github-pr-review/policies/review-output.md),
"Concise human-style summary (opt-in)".
