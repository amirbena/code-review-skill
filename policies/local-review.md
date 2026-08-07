# Policy — Local Review

Governs review of a local implementation, independent of the specific
runbook in use (see
[`../runbooks/passive-local-review.md`](../runbooks/passive-local-review.md)).

## Complete implementation state

Local review inspects the *complete* implementation state, not only
`HEAD`:

- the committed branch delta relative to base;
- local-only commits (not yet pushed);
- staged modifications;
- unstaged modifications;
- relevant untracked files.

```text
base         = A
local HEAD   = B
working tree = C

Review: A → B + C
```

Do not assume local `HEAD` contains the whole task.

## Local/remote gap detection

Detect and report:

- local commits not pushed;
- remote commits missing locally;
- a local branch diverged from its tracking branch;
- uncommitted staged work;
- uncommitted unstaged work;
- a PR HEAD behind local HEAD;
- a PR HEAD ahead of local HEAD;
- a PR state that does not represent the full local implementation.

When a mismatch exists:

1. report it;
2. review the relevant local implementation state;
3. do not pretend GitHub is authoritative;
4. return findings to the implementing Agent;
5. require synchronization;
6. re-review the authoritative state before any final GitHub decision.

The reviewer itself does not silently push implementation changes — see
[`../AGENTS.md`](../AGENTS.md) section 11, "Skill Consumer Branch Policy."

## Output

Local review returns exactly one of:

```text
CHANGES REQUIRED      -- blocking (P0/P1) findings exist
REVIEW CLEAN            -- no blocking findings remain
```

using [`../templates/local-review-report.md`](../templates/local-review-report.md).
It never mutates GitHub state.
