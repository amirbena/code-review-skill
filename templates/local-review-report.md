# Template — Local Review Report

Returned to the implementing Agent after a passive local review (see
[`../runbooks/passive-local-review.md`](../runbooks/passive-local-review.md)).
This is **not** a GitHub review event — it never gets published anywhere
by itself.

```markdown
## Local Review Report

### Review State
- base branch: <name>
- base SHA: <sha>
- local HEAD: <sha>
- remote HEAD: <sha | none>
- committed delta: <base..HEAD summary>
- uncommitted state: staged=<yes/no>, unstaged=<yes/no>, untracked=<relevant files or none>
- synchronization status: <in sync | local ahead | local behind | diverged | no tracking branch>

### Findings
- P0: <list or none>
- P1: <list or none>
- P2: <list or none>

### Result
REVIEW CLEAN | CHANGES REQUIRED

### Loop State
- iteration: <n>
- configured maximum: <review.max_loops from review-config.yaml>
- another iteration allowed: <yes/no>
```

## Rules

- Result is exactly `REVIEW CLEAN` or `CHANGES REQUIRED` — see
  [`../policies/local-review.md`](../policies/local-review.md).
- Loop State always reflects the actual configured maximum from
  [`../review-config.yaml`](../review-config.yaml), never a hardcoded
  number.
- When the loop limit is reached with blocking findings still open, the
  Result stays `CHANGES REQUIRED` and the report states explicitly that
  the review-loop limit was reached (see
  [`../runbooks/review-loop.md`](../runbooks/review-loop.md)).
