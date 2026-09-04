# local-code-review

Review the code you have **right now** — committed, staged, unstaged, and
untracked — before it becomes a push or a PR. You get back evidence-backed
`P0` / `P1` / `P2` findings and one `REVIEW CLEAN` / `CHANGES REQUIRED`
verdict. The Skill is read-only: it never edits, commits, pushes, or
touches GitHub.

For an existing GitHub Pull Request, use the sibling
[`github-pr-review`](../github-pr-review/SKILL.md) Skill instead.
[`../../docs/CODE_REVIEW_COMPARISON.md`](../../docs/CODE_REVIEW_COMPARISON.md)
explains why this Skill exists alongside native and third-party reviewers.

## When to use it

- Right before `git push` or opening a PR — a last check on the full
  local delta, not just `HEAD`.
- After applying review fixes locally, to confirm they hold (re-review
  needs its own approval — see below).
- When you want the change checked against a ticket, an ADR, or
  acceptance criteria you can paste in.

## How to invoke it

Ask for it in plain language — there is no required syntax:

```text
review my local changes before I push
run a local code review of the current diff
review the working tree against BILLPAY-1234's acceptance criteria
```

Optionally attach context to focus the review (all optional, any
combination):

```text
/local-code-review

Context: Jira BILLPAY-1234
Acceptance criteria:
- reject unsupported CC + RTP combinations
- validation must run before execution
```

A plain request with no context is fully supported. Optional add-ons,
each with a usage guide under `docs/features/`:
[review context & prior review evidence](../../docs/features/review-context.md)
(requirements, a ticket/Issue, an HLD/ADR, a plan, a Jira key resolved
read-only, or an associated PR's prior findings) focuses the review
without widening the local delta;
[`include_fix_prompt`](../../docs/features/fix-prompt.md) adds a
coding-agent-ready prompt to qualifying findings;
[`human_review_output`](../../docs/features/human-review-output.md) renders
the summary in a concise senior-engineer voice.
[Runtime validation evidence](../../docs/features/runtime-validation.md)
applies automatically when the repository declares a suitable command and
the runtime provides a verified isolation boundary. The
[parallel-review](../../docs/features/parallel-review.md) contract is
shared, but parallel execution is currently wired into `github-pr-review`,
not `local-code-review`.

## What a review looks like

```markdown
## Code Review

**Result: ⚠️ Changes Requested**

Not safe to proceed: the retry path can double-process a payment.

### Findings

#### F1 [P1] Retry can duplicate processing
- **Location:** `src/pay/execute.py:88` _(staged)_
- **Evidence:** the handler re-enters `charge()` on timeout without an
  idempotency key.
- **Impact:** a retried webhook charges the customer twice.
- **Fix:** key the charge on the payment intent id and no-op on repeat.

### Decision
**CHANGES REQUIRED**
```

A clean review is just the result line, an optional one-line change
summary, validation, and `REVIEW CLEAN`. Machine detail (SHAs,
per-category scope, counts) sits in a trailing metadata block.

## Boundaries worth knowing

| Rule | Short version |
| --- | --- |
| **Opt-in only** | Never runs automatically. Every review *and* every re-review needs fresh, explicit approval for that run. |
| **Read-only** | No edits, patches, commits, pushes, branches, PRs, or GitHub writes — ever. |
| **Severity → verdict** | `P0`/`P1` block; `P2` never does. The verdict is derived mechanically, not by judgment. |
| **One owner per scope** | If another Code Review Agent owns this branch, it returns `REVIEW ALREADY OWNED`. |
| **Scope stays local** | A Jira ticket or PR reference focuses the review; it never expands it past the current local delta. |

These are summaries. The binding text lives in
[`SKILL.md`](SKILL.md) and the canonical policies it links —
[`policies/invocation-approval.md`](policies/invocation-approval.md),
[`../../shared/policies/severity.md`](../../shared/policies/severity.md),
[`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md).

## Deeper documentation

- [`SKILL.md`](SKILL.md) — the execution entry contract
- Feature guides — how to use the optional capabilities:
  [review context](../../docs/features/review-context.md),
  [runtime validation](../../docs/features/runtime-validation.md),
  [parallel review](../../docs/features/parallel-review.md),
  [human-style output](../../docs/features/human-review-output.md),
  [fix prompt](../../docs/features/fix-prompt.md)
- [`runbooks/local-review.md`](runbooks/local-review.md) — the full
  numbered procedure
- [`policies/`](policies/repository-state.md) — the rules this Skill owns
  (invocation approval, repository-state categories, optional review
  context, optional PR context)
- [`templates/local-review-report.md`](templates/local-review-report.md)
  — the output contract
- [`../../shared/policies/`](../../shared/policies/review-scope.md) — the
  review standard shared with `github-pr-review`

## Development

```bash
python3 scripts/validate-skill-metadata.py skills/local-code-review --containment-root .
./scripts/package-skills.sh local     # -> dist/local-code-review-skill.zip
python3 -m unittest discover -s tests -t .
```

PowerShell packaging: `./scripts/package-skills.ps1 local`.

This README is onboarding documentation only. It carries no normative
authority — [`SKILL.md`](SKILL.md), this Skill's `policies/`, its runbook,
and the shared policies do.
