# Structured review result

## What it does

When enabled, `local-code-review` appends one **machine-readable JSON
result** after its normal human report — the same findings, coverage, and
`REVIEW CLEAN` / `CHANGES REQUIRED` / `REVIEW INCOMPLETE` decision, in the
schema-versioned shape defined for review results. The document carries
`schema_version` and the reviewed head SHA. It is normalized internally to
the `structured_review_result` option (default `false`).

Without it, the report is exactly the default human report.

## When it is useful

- A script, dashboard, or another agent needs to consume the review
  without parsing prose.

## Which Skill(s)

`local-code-review` only. `github-pr-review` does not emit it yet
(tracked separately).

## Default, conditional, or requested

**Explicitly requested; default off.** Set from the current invocation
only: `structured_review_result=true`, the bare option name, *"include a
structured review result"*, or the fixed phrases *"machine-readable review
result"* / *"review result as JSON"*. Vague wording such as *"give me
JSON"* does not enable it.

## How to invoke it

```text
/local-code-review
structured_review_result=true
```

## Limitations & safety boundaries

- **Output only.** Findings, severities, coverage, and the mechanical
  decision are identical on and off; the human report is unchanged and
  still comes first.
- `reviewed_head_sha` is `null` when the reviewed target includes
  uncommitted changes, because a commit SHA cannot identify them.
- It is not emitted for an ungraded outcome (for example an unresolved
  Jira reference) or when the report itself was withheld.
- Nothing is written to a file or published; it is returned inside the
  one report.

## Canonical semantics

[`shared/policies/structured-output.md`](../../shared/policies/structured-output.md)
· [`shared/policies/invocation-options.md`](../../shared/policies/invocation-options.md)
· schema and versioning: [`../review-result/README.md`](../review-result/README.md).
