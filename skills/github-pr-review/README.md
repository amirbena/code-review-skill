# github-pr-review

Review an existing GitHub Pull Request the way a strong senior reviewer
would: repository-aware reasoning, evidence-backed `P0` / `P1` / `P2`
findings, and one clear verdict. **Passively** it returns a report;
**actively**, with authenticated GitHub access, it publishes inline
comments and one consolidated review, and — only under independently
trusted authorization — submits Approve / Request Changes.

For local changes that aren't a PR yet, use the sibling
[`local-code-review`](../local-code-review/SKILL.md) Skill.
[`../../docs/CODE_REVIEW_COMPARISON.md`](../../docs/CODE_REVIEW_COMPARISON.md)
explains where each fits.

## When to use it

- Review someone's open PR by URL or number — as a passive report, or
  actively with published comments.
- Re-review after a push: same reviewer + a reliable previous SHA ⇒ a
  bounded delta re-review; otherwise a full review.
- Review **your own** PR — see "Self-review" below.

## How to invoke it

Plain language; the phrasing you use also sets how far it may go:

```text
review PR https://github.com/acme/app/pull/812
just review PR #812 and tell me what you find        → report only
review #812; block it if there are serious issues     → may Request Changes
review #812 and approve it if it's clean              → Approve only if
                                                        independently authorized
```

Optionally attach context (a pasted ticket/Issue/ADR, an implementation
plan, or a bare Jira key resolved read-only) to focus the review and
enable scope-boundary reasoning. It never becomes a second review target
and never widens the PR delta.

## What a review looks like

**Clean** — a few lines:

```markdown
## Code Review

**Result: ✅ REVIEW CLEAN**

No blocking findings at `a1b2c3d`.

Validation passed: 761 tests and repository checks.

### Decision
**APPROVE**
```

**With findings** — one scannable line per finding; the detail lives in
the inline comments:

```markdown
## Code Review

**Result: ⚠️ CHANGES REQUIRED**

Not safe to merge at `a1b2c3d` yet; see the inline comments for detail.

### Findings

- **P1 — Pagination can stop after page one and pass a false clean review**
  `src/reviews/scan.py:84`
- **P2 — Validation output hides the failing check name**
  `scripts/validate.py:117`

Validation passed: 761 tests and repository checks.

### Decision
**REQUEST CHANGES**
```

The final body never repeats a finding's evidence, impact, or fix when
that finding already has an inline comment. Machine/process state (SHAs,
counts, review mode, action mode, mutation outcome) sits in a small
trailing `<details>` block — never in the body.

## Self-review

You **may** point this Skill at your own PR. Analysis is never gated by
authorship — the full review runs and produces a real verdict.

What changes is publication: a self-review submits **no** formal
`APPROVE` / `REQUEST_CHANGES` on your own work — `APPROVE` on your own PR
is always forbidden, and `REQUEST_CHANGES` is not submitted as a formal
self-review action either. The result is published as an informational
GitHub review **`COMMENT`** with a one-line disclosure:

```markdown
### Decision
**REVIEW CLEAN** — GitHub review mutation withheld: reviewer is the PR author

_Self-review: formal approval was withheld by policy._
```

An alternate account, token, bot, service account, GitHub App identity,
or nested agent under the same controlling authority as the author is
treated as a self-review too — it never unlocks a formal self-approval.

## Publication at a glance

| Situation | What gets published |
| --- | --- |
| Passive review | Nothing — a report is returned to you |
| Self-review | Informational `COMMENT` + disclosure line; no formal event |
| External review, no trusted authorization | Findings + verdict, **no** GitHub mutation (the safe default) |
| External review, blocking, `block-only` | `REQUEST_CHANGES` (with reviewer independence + GitHub permission) |
| External review, `explicitly-authorized auto-action` | The permitted `APPROVE` **or** `REQUEST_CHANGES` |

"Trusted authorization" means a signal from a principal **independent of
the agent doing the review**, through a channel that agent cannot author,
forge, or replay, scoped to this exact PR + HEAD + action. A flag,
prompt, env var, alternate token, or "approve if clean" text the agent
controls never counts. Anything ambiguous fails closed to a non-mutating
review. This Skill never merges, and `APPROVE` is never merge authority.

## Boundaries worth knowing

| Rule | Short version |
| --- | --- |
| **Analysis ≠ mutation authority** | The verdict always exists; submitting it to GitHub is a separate, authorized step. Default: recommendation-only. |
| **Self-review ≠ self-approval** | Analysis always runs; no formal event on your own work; informational `COMMENT` instead. |
| **Independence is authority, not username** | A different login under the author's controlling authority is the same reviewer. |
| **HEAD safety** | The reviewed HEAD is revalidated before the decision; a stale HEAD is never approved; authorization is bound to the exact HEAD. |
| **Severity → verdict** | `P0`/`P1` block; `P2` never does; derived mechanically. |
| **One owner per scope** | Another Code Review Agent already on this PR ⇒ `REVIEW ALREADY OWNED`. |

Binding text: [`SKILL.md`](SKILL.md) section 7 and the canonical policies —
[`policies/review-action-authorization.md`](policies/review-action-authorization.md),
[`policies/review-authority.md`](policies/review-authority.md),
[`policies/review-output.md`](policies/review-output.md).

## Deeper documentation

- [`SKILL.md`](SKILL.md) — the execution entry contract
- [`policies/github-review.md`](policies/github-review.md) — the canonical
  policy index (identity, authorization, delta re-review, PR scope,
  repository checkout, context, evidence, reasoning, parallelism,
  placement, output)
- [`runbooks/passive-pr-review.md`](runbooks/passive-pr-review.md) /
  [`runbooks/active-pr-review.md`](runbooks/active-pr-review.md) — the
  full procedures
- [`templates/`](templates/external-review-summary.md) — the review body
  and inline-comment output contracts
- [`../../shared/policies/`](../../shared/policies/severity.md) — the
  review standard shared with `local-code-review`

## Development

```bash
python3 scripts/validate-skill-metadata.py skills/github-pr-review --containment-root .
./scripts/package-skills.sh github     # -> dist/github-pr-review-skill.zip
python3 -m unittest discover -s tests -t .
```

PowerShell packaging: `./scripts/package-skills.ps1 github`.

This README is onboarding documentation only. It carries no normative
authority — [`SKILL.md`](SKILL.md), the `policies/`, and the shared
policies do.
