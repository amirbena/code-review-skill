# Published review

## Inline comment

```text
[<severity>] <title>

Evidence: <evidence>

Impact: <impact>

Fix: <fix>
```

The file and line are the comment's own anchor, so no `Location` line.
Write it as a senior engineer would, with no mention of the review process
and no mention of which tool or model produced it.

## Summary

```text
## Review: <decision>

<one or two sentences: what the change does and the decision's reason>

Event: <COMMENT | APPROVE | REQUEST_CHANGES><, and why it is COMMENT when it
is not the decision's natural event>
Reviewed commit: <short HEAD SHA>

### Findings
- [<severity>] <title> (<path:line>), inline
- ...

### Findings without an inline anchor
**F<n> [<severity>] <title>** (<location>)
Evidence: ...
Impact: ...
Fix: ...

### Not reviewed
<`REVIEW INCOMPLETE` triggers, skipped files and concerns not investigated,
exactly as the `review-core` report states them, or omit the section>

Skipped as already raised: <n>
```

Omit an empty section. The decision line states the decision as
`review-core` produced it.
