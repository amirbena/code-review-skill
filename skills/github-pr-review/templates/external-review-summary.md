# Template — External Review Summary

Published once, after all inline findings, before the final Approve /
Request Changes decision (see
[`../policies/github-review.md`](../policies/github-review.md)).
Human-readable content always precedes any machine-oriented metadata —
see [`../SKILL.md`](../SKILL.md), "Output Contract."

```markdown
## Code Review Summary

### What changed
<concise summary of what the Pull Request appears to implement>

### What was done well
<concrete, evidence-backed strengths only — do not invent praise;
omit this subsection's bullets if nothing specific stands out>

### What needs improvement
- P0: <count or none>
- P1: <count or none>
- P2: <count or none>

<optionally, one or two lines naming the dominant themes rather than
repeating every inline comment verbatim>

### Decision
Approve | Request Changes
```

## Optional extended metadata

If structured metadata is useful for orchestration/automation, append it
**after** the human-readable review, clearly separated:

```markdown
---
<!-- extended metadata (machine-oriented; not required reading) -->
reviewed_head: <sha>
p0_count: <n>
p1_count: <n>
p2_count: <n>
decision: approve | request_changes
```

## Rules

- "What was done well" only mentions strengths actually supported by the
  PR — never invented.
- "What needs improvement" summarizes findings; it does not repeat every
  inline comment verbatim.
- The Decision line is unambiguous and matches the actual GitHub review
  action submitted.
- Keep the visible section concise — this is read by a person, not
  parsed by a machine.
