# Code hygiene review

## What it does

When a change adds or edits an issue-tracker reference in a comment, or
introduces or renames a variable whose name may hide its intent, the review
checks it against two narrow hygiene categories:

1. **Issue-tracker references** — a comment citing a tracker key (`#75`,
   `PROJ-456`, `issue 75`) that is uninformative, redundant, or obsolete.
2. **Variable naming** — a name that hides intent where the surrounding code
   supports exactly one clearer name.

It is not a linter. Dead code, magic numbers, comment density, formatting,
and style are out of scope, and it never looks at lines the change did not
add or modify.

## When it is useful

You want a reviewer to notice `// fix for #75` after the workaround is gone,
or `tmp` standing in for an `expiresAt` timestamp — without the review
blocking your merge over it.

## Which Skill(s)

Both. `local-code-review` and `github-pr-review` read the same shared policy,
so the same change gets the same hygiene result in either Skill. Only the
delivery differs: the observations section appears in the local report, and
in the `github-pr-review` review **body** only — never as an inline comment
or a GitHub review event, in any publication mode.

## Default, conditional, or requested

**Conditional and automatic.** There is no invocation option. It activates
only when the changed delta contains a tracker-reference comment or a
possibly unclear variable name, and is silent otherwise.

## Examples and counterexamples

**Issue-tracker references**

| Change | Result |
|---|---|
| `// see #75` — only the key; a reader cannot tell what it means | observation: rewrite to state the fact, or delete |
| `// handle null (JIRA-1234)` directly above `if (x == null)` — the code already says it | observation: delete the comment |
| `// workaround for #75` where the workaround code is demonstrably gone | observation: obsolete, delete |
| `// retry required: upstream rate-limits at 5 rps (#75)` — documents a live constraint | **kept — nothing reported** |
| `// ADR-12 #75: contract frozen for v2 clients` — decision or external contract | **kept — nothing reported** |
| a reference the repository's own instructions require for traceability | **kept — nothing reported** |

**Variable naming**

| Change | Result |
|---|---|
| `const tmp = user.sessionExpiry` used only as the cutoff in `if (now > tmp)` | observation: rename to `sessionExpiry` / `expiresAt` |
| `for (let i = 0; …)`, comprehension variables, short names with clear local meaning | **not reported** |
| `ctx`, `id`, `url` and other standard domain abbreviations; names following a project convention | **not reported** |
| a poor name where context supports no single better name | **not reported** |

A rename is suggested only with one concrete replacement, never as generic
criticism.

## Severity and the Decision

| Tier | When | Effect on the Decision |
|---|---|---|
| **Observation** (default) | the pattern is confirmed from local context | none — no severity, ID, or confidence; at most 3 per review; never a finding |
| **P2 finding** | only with causal evidence the issue carries real maintainability or change-risk cost (e.g. a name two call sites already use with opposite meanings) | none by itself — P2 is non-blocking |
| **P0 / P1** | never, for hygiene alone | — |

Observations are not counted toward the Decision, coverage, or finding
identity. A genuine correctness or security problem found nearby is judged
under its own rules; hygiene never lowers or raises it. When all that
remains is cosmetic taste, the review reports an observation or nothing,
not a P2.

## How a pattern becomes a report

A pattern match (a bare key, a short name, `tmp`, `data`) is only a
**candidate**. It is reported only after the surrounding code, the comment
text, supplied context, or PR/commit context supports it; otherwise it is
dropped.

## Limits and expected false positives

- **No tracker lookup.** The review never calls an issue tracker or API.
  Staleness is judged from local evidence only, and unknown tracker state is
  never treated as proof a reference is stale. A reference whose live
  relevance is only visible in the tracker can therefore be flagged as an
  observation when it should have been kept; treat an observation as a
  prompt to check, not a verdict.
- **Naming is judgment.** Domain vocabulary the reviewer cannot see from the
  change and its neighbors can produce a suggestion you reasonably decline.
- **Cap and ordering.** Beyond 3 qualifying observations, the extras (in
  files with smaller changed deltas) are dropped silently.
- A `TODO` marking a real defect is reviewed as that defect, not as hygiene.

## Relationship to other review behavior

Hygiene reuses the existing evidence bar, severity definitions, and
mechanical Decision derivation, and it defers to a repository's own naming
and traceability conventions. It adds no finding category and no severity
value. See [Severity and decision model](../../shared/policies/severity.md)
and [`evidence.md`](../../shared/policies/evidence.md).

## Canonical semantics

[`shared/policies/code-hygiene.md`](../../shared/policies/code-hygiene.md)
owns the scope, trigger, evaluation rules, severity representation, and
exclusions; the observations section's position and shape are in
[`shared/templates/review-summary.md`](../../shared/templates/review-summary.md),
"Code hygiene observations". This guide is explanatory; the policy wins any
conflict.
