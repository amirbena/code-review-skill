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
output; large requirement text copied from another source.

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
| Dependencies | short references |
| Validation | 2–5 bullets |

When the task genuinely needs more, link a design document, research
artifact, ADR, canonical repository policy, or parent Epic — do not paste
those into the Issue.

## Parent / Epic Issues

Shorter still: a one-paragraph goal, short context, a child-issue
checklist, and the key dependencies. Detailed implementation requirements
live in the child Issues, not the parent.

## Pull Requests

The body answers four questions: **what changed**, **why**, **how it was
validated**, and **anything a reviewer should look at closely**. A typical
shape:

```markdown
## What changed
- ...

## Why
Short explanation.

## Validation
- `command` — pass

## Review notes
Only when something is non-obvious.
```

Keep the structured traceability sections of
[`../.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)
(change surface, behavioral change, governance impact, contract / packaging
impact, reviewer focus): fill the ones that apply and mark the rest
`None` / `N/A`. Brevity means not padding those sections — never dropping
required review or traceability information.

Do not include: a full chronology of the work; every command run; full
test output; the Issue's requirements restated; architecture already
documented elsewhere; large code already visible in the diff; filler such
as "carefully reviewed all files". Link the Issue or the document instead.

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

## Not a character limit

This policy targets cognitive load and scanability, not a line or
character count. The sizes in the table above are typical ranges, not
thresholds to game, and nothing here licenses trimming a body below the
point of clarity. Preserve required review and traceability information;
move detail into a linked document rather than deleting it.
