# GitHub Issue / PR Authoring Policy

Canonical rules for the **content of agent-authored GitHub Issues and Pull
Requests** for this repository — how much detail belongs in the
GitHub-visible body, and what belongs in a linked document instead.

This is a repository-development policy. It is **not** packaged into either
Skill archive, and no packaged Skill resource may depend on it. It governs
the body an agent writes for an Issue or PR here. It does not
change the Issue Form fields in
[`../.github/ISSUE_TEMPLATE/engineering-task.yml`](../.github/ISSUE_TEMPLATE/engineering-task.yml)
or the checklist in
[`../.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md),
and it never overrides the mechanics in
[`git-pr-merge-policy.md`](git-pr-merge-policy.md) (assignment, squash,
merge safety) or the documentation reading-experience rules in
[`documentation-policy.md`](documentation-policy.md). See
[`../AGENTS.md`](../AGENTS.md) for global invariants and routing.

## Principle

**Agent-complete internally, human-scannable externally.** An agent may
reason as deeply as the task needs; the Issue or PR body is a briefing for
a human, not a transcript of that reasoning.

## When this applies

This policy applies whenever an agent **creates, updates, rewrites, or
materially expands** a GitHub Issue or Pull Request body — not only at
first creation.

When updating an existing Issue or PR, preserve the context that is still
useful but compress or replace redundant prose instead of appending
another full status report, so the body does not grow indefinitely across
iterations.

## Prefer / avoid

**Prefer:** short sections; bullets; a table where it clarifies; links to
the canonical doc / Issue / ADR / policy; concrete evidence; explicit
decisions.

**Avoid:** long narrative; repeated context; restating repository policy;
a step-by-step execution log or implementation diary; verbose validation
output; large requirement text copied from another source;
**historical/predecessor narration** — commit SHAs, a merged PR narrated
in prose ("shipped via PR #N"), or "this follows the precedent set by
#X/#Y/#Z" framing — recounting how the repository arrived at a
constraint, rather than just stating the constraint, unless the exact
version or precedent itself materially constrains the new work.

## Necessary vs. unnecessary context

This distinction applies equally to implementation and benchmark Issues.
An agent may read predecessor Issues, PRs, commits, and decision records
as deeply as the task needs while drafting — but only the resulting
constraint, not the research trail that produced it, goes into the final
body. Research is not carried into the artifact by default.

Context an Issue body may reference falls into three buckets:

1. **Required architectural context** — a predecessor's contract whose
   semantics the new work must preserve (e.g. "must preserve #302's
   fail-closed sandbox invariant"). State the constraint itself, in
   present tense, not how or when it was established.
2. **Concise dependency/reference context** — a bare relation (`Builds on
   #367`, `Benchmark depends on #369`) that the `Dependencies` field
   already models well. A reference number plus a few words of relation
   is enough; do not expand it into prose.
3. **Unnecessary historical narration** — chronology, PR/commit
   provenance, or "precedent" framing that doesn't change what an
   implementer must do or prove. This belongs in the linked Issue, PR, or
   decision record, not restated here.

## Engineering Task Issues

A normal Engineering Task Issue body (fields from the Issue Form) is
usually:

| Field | Usual size |
| --- | --- |
| Problem | 1–3 short paragraphs |
| Goal | 1–2 sentences |
| Scope | 3–6 bullets |
| Non-Goals | 0–3 bullets |
| Acceptance Criteria | 3–6 checkboxes |
| Dependencies | short references — provenance goes here as a bare reference (`Depends on: #367`), never restated as prose elsewhere in the body |
| Validation | 2–5 bullets |

When the task genuinely needs more, link a design document, research
artifact, ADR, canonical repository policy, or parent Epic — do not paste
those into the Issue.

## Parent / Epic Issues

Shorter still: a one-paragraph goal, short context, a child-issue
checklist, and the key dependencies. Detailed implementation requirements
live in the child Issues, not the parent. As with any Dependencies field,
a closed predecessor Epic or issue is cited as a bare reference — not
re-summarized.

## Pull Requests

A PR description is a concise change summary and navigation surface, not a
second specification. It answers: **what changed and why**, **where the
canonical detail lives**, **how the change was validated**, and **the review
state when a review occurred**.

### Start from the canonical PR template

An agent that **creates** a Pull Request, or **materially updates** one,
starts from
[`../.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)
— the repository's single canonical source for the PR body's structure —
fills its intended fields and sections with real content, and removes or
replaces every placeholder and HTML-comment guidance block. An agent never
invents an independent PR-body structure instead of the template's. The
template's own fields, sections, and placeholders are defined and maintained
there, not restated here.

This is a structural contract, not a prose-matching one: the author writes
their own sentences within each field, but the section/field structure must
come from the template. Keep the Issue-closing reference and link to the
smallest canonical source that owns detailed behavior or decisions rather
than duplicating it into the field.

This authoring rule is distinct from, but backed by, deterministic
validation that a PR body's structure matches the template — see
"Validate PR-template structure before opening or updating a PR" below.

### Validate PR-template structure before opening or updating a PR

Before running `gh pr create` or `gh pr edit`, validate the drafted body
locally and offline against the same deterministic structure checker CI
runs — rather than waiting for CI to catch a missing section, an
unfilled required field, an unresolved `Fixes #` placeholder, or an
invented body shape (such as a different tool's default `## Summary` /
`## Test plan` pattern) that never came from
`.github/PULL_REQUEST_TEMPLATE.md`:

```bash
PR_BODY="$(cat pr-body.md)" python3 scripts/validation/pr_description_length.py --pr-body-env PR_BODY
```

Pass the drafted body through the named environment variable, never as a
literal CLI argument. This calls the exact same `validate_structure()`
(and `validate_body()` length check) that
[`../.github/workflows/pr-description-length.yml`](../.github/workflows/pr-description-length.yml)
runs from the GitHub event payload — see
`scripts/validation/pr_description_length.py`'s module docstring. Treat
this as a pre-mutation gate, the same as the release-intent check below:
if it fails, fix the draft and re-run it before calling `gh pr create` /
`gh pr edit` — do not open or update the PR on a failing check, and do
not reimplement structure validation elsewhere.

### Validate release intent before opening or updating a PR

`Release category:` must be one of `Added`, `Changed`, `Deprecated`, `Fixed`,
`Security`, `Removed`, `Breaking`, or `none` — see
[`release-changelog-policy.md`](release-changelog-policy.md) for the
category-to-SemVer contract. The template's `Release category:` /
`Release entry:` fields, filled in, look like:

```text
Release category: Fixed
Release entry: Short one-line CHANGELOG entry describing the fix.
```

Before running `gh pr create` or `gh pr edit`,
validate the drafted body locally and offline against the existing,
deterministic checker — the same one CI runs — rather than waiting for CI to
catch an invalid or missing category:

```bash
PR_BODY="$(cat pr-body.md)" python3 scripts/release/release_worthiness.py assess \
  --base-ref <base> --pr-body-env PR_BODY --require-release-intent
```

Pass the drafted body through the named environment variable, never as a
literal CLI argument. Treat this as a pre-mutation gate: if it fails, fix the
`Release category:` / `Release entry:` lines in the draft and re-run it before
calling `gh pr create` / `gh pr edit` — do not open or update the PR on a
failing check. This reuses `scripts/release/release_worthiness.py`'s existing
`assess --require-release-intent` contract; do not reimplement category
validation elsewhere.

Summarize; do not reproduce Issue acceptance criteria, complete policy or
runbook semantics, large schemas or matrices, fixture catalogs, implementation
reports, architecture already documented elsewhere, code visible in the diff,
or a chronology of the work. Detailed design belongs in Issues, docs, policies,
or runbooks. Detailed findings belong in the review artifact, not copied
wholesale into the PR description. Prefer one sentence or bullet plus a link.

### Enforced useful-content limit

The repository GitHub Actions check measures the actual current
`pull_request.body` by invoking
[`../scripts/validation/pr_description_length.py`](../scripts/validation/pr_description_length.py).
That module's `PR_BODY_HARD_LIMIT` constant is the sole authoritative numeric
limit; workflow YAML, policy, and tests must reuse it rather than implement
another counter.

Template structure/completeness and useful-content length are separate
contracts. They may share workflow infrastructure, but the length validator
does not define required headings or placeholder completeness, and a structural
validator must not introduce a second body-measurement implementation.

The canonical metric normalizes CRLF and bare CR line endings to LF, removes
HTML comments (including template guidance), trims leading and trailing
whitespace, and counts Unicode code points in the remaining Markdown. Internal
Markdown syntax, links, whitespace, and line breaks count. Diff size, commit
messages, and generated GitHub metadata outside the PR body do not.

The current 6,000-code-point limit was selected from a recent representative
sample measured with that exact algorithm:

| PR | Character of change | Useful code points | Result |
|---|---|---:|---|
| #127 | small automation hardening | 2,037 | pass |
| #144 | documentation-heavy refactor | 3,197 | pass |
| #146 | medium/complex runtime policy | 3,885 | pass |
| #114 | complex release automation | 5,428 | pass |
| #112 | complex review-status enforcement | 5,971 | pass |
| #147 | unusually detailed regression-fixture report | 6,158 | fail |
| #148 | motivating duplicate-specification outlier | 6,543 | fail |
| #136 | unusually detailed identity-contract report | 6,745 | fail |

This places the hard limit just above the observed legitimate complex range
while catching the recent outlier band, including #148. If the constant changes,
this evidence and its drift test must change with it.

## Validation reporting

Summarize:

```text
564 tests passed
skill metadata validation passed
git diff --check clean
```

Paste detailed output only when a specific failure or result is materially
useful to the reviewer.

## Research Issues

A research Issue may run a little longer, but the body stays focused on the
**questions**, the **scope**, the **evidence required**, and the **expected
decision / output**. The detailed findings belong in the research artifact
the Issue produces, not in the Issue body.

## When longer content is the point

Longer GitHub content is acceptable when the body itself is the artifact
under review — an RFC / discussion Issue, an incident postmortem, a formal
design proposal. That is a deliberate choice for that Issue, not the
default for routine agent-authored Issues and PRs.

## Length and clarity

Issue sizes above remain guidance rather than mechanical limits. PR bodies have
the deterministic useful-content limit defined above, but authors should not
game it or trim below clarity: summarize the change and move detail into a
linked canonical document.
