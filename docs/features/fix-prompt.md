# Coding-agent fix prompt

## What it does

When enabled, `local-code-review` appends a **ready-to-run implementation
prompt** to each qualifying actionable finding — a coding-agent-ready
description of the change that addresses the evidenced root cause. It is
normalized internally to the `include_fix_prompt` option (default
`false`).

Without it, every finding still carries the mandatory concise `Fix`
direction; the option only adds the fuller prompt on top.

## When it is useful

- You plan to hand the findings straight to a coding agent and want an
  actionable prompt per root-cause finding rather than writing one
  yourself.

## Which Skill(s)

`local-code-review` only. `github-pr-review` stays reviewer-facing and
emits concise `Fix` directions only — it never produces the full
implementation prompt. (`github-pr-review` recognises the option name for
mediation parity but keeps it local-only.)

## Default, conditional, or requested

**Explicitly requested; default off.** It is normalized from the current
invocation only, from explicit wording — the canonical assignment
`include_fix_prompt=true`, the bare option name, or an explicit
affirmative request such as *"include a fix prompt"* / *"give me a fix
prompt"*. It is **not** inferred from urgency, severity, branch name, or
sentiment.

## How to invoke it

```text
/local-code-review
include_fix_prompt=true
```

```text
review my local changes and include a fix prompt for each finding
```

## Limitations & safety boundaries

- **Output only.** It never changes the Review Target, inspection,
  evidence, finding identity, severity, deduplication, PR-context
  reconciliation, or the mechanical decision — a review with the option
  on and one with it off find the same issues at the same severities.
- It **grants no mutation capability** and does not authorize an
  autonomous fix workflow — `local-code-review` still never edits,
  patches, commits, or pushes.
- A clean review never manufactures implementation work.
- One structural finding gets one coherent prompt, not one per
  manifestation.

## Canonical semantics

[`shared/policies/remediation-guidance.md`](../../shared/policies/remediation-guidance.md),
"Skill-specific detail" ·
[`shared/policies/invocation-options.md`](../../shared/policies/invocation-options.md)
· [`skills/local-code-review/SKILL.md`](../../skills/local-code-review/SKILL.md) §1.
