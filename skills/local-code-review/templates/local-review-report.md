# Template — Local Review Report

Returned by every invocation of `local-code-review`. This is **not** a
GitHub review event and is never published anywhere by the Skill itself
— it is handed back to the caller. Findings use the shared shape in
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md).

```markdown
## Local Code Review

### Review State
- base branch: <name>
- base SHA: <sha>
- local HEAD: <sha>
- remote HEAD: <sha | none>
- committed delta: <base..HEAD summary>
- uncommitted state: staged=<yes/no>, unstaged=<yes/no>, untracked=<relevant files or none>
- synchronization status: <in sync | local ahead | local behind | diverged | no tracking branch>

### Blocking Findings
F1 [P1] Retry can duplicate processing
file: src/...
line: <n>
evidence: <concrete evidence>
recommended: <recommended direction>

### Non-Blocking Findings
F2 [P2] ...

### Result
CHANGES REQUIRED
```

or, when clean:

```markdown
### Result
REVIEW CLEAN
```

## Rules

- Result is exactly `REVIEW CLEAN` or `CHANGES REQUIRED` — `REVIEW CLEAN`
  only when no `Blocking Findings` (P0/P1) remain; `P2`s alone never
  block it (see
  [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md)).
- Every finding has a stable ID (`F1`, `F2`, ...), a severity, a short
  title, a file/line where available, concrete evidence, and a
  recommended correction — see
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md).
- **No loop/orchestration metadata.** This report does not track review
  iteration count, a configured maximum, or whether another iteration is
  allowed — that information belongs to the orchestrator, never to this
  Skill (see [`../SKILL.md`](../SKILL.md)).
- Return only what the implementing Agent needs to act.
