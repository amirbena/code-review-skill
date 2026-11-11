---
name: review-deep-investigation
version: 3.3.0
description: Lifts review-core's investigation bound with multi-hop tracing, root cause, affected tests and failure and null paths. Use when a suspicion needs more than one hop to settle.
---

# review-deep-investigation

Lifts `review-core`'s investigation bound for the suspicions it could not
settle in one hop. It adds findings and a list of what it traced. It never
changes severity, the decision rule, the `REVIEW INCOMPLETE` triggers or
S1–S5 and S10; those are `review-core`'s.

**Requires `review-core`.** Install it alongside this Skill; without it, stop and ask the user to install it.

## Entry contract

- Runs only after `review-core` has run on the same target in this run, and
  only when selected under `review-core`'s "Mode" (S6, stated there):
  from the request, on a yes to the Core's ask, or on evidence in `auto`.
- Needs no input beyond the target and the Core's findings and "Not
  investigated" concerns.
- Read-only, by `review-core`'s S1 and S10. It uses Git and grep only:
  `git grep`, `git log -S`/`-G`, `git show`, `git blame`, and file reads. It
  builds no graph, index, AST or cache, and runs no project code.

## Files

Read in full before step 1.

- [`rules/investigation.md`](rules/investigation.md) — the investigation
  types and how far tracing goes.

## Procedure

1. **Collect the open questions:** the Core's "Not investigated" concerns
   marked beyond the bound, plus any suspicion from reading the change that
   one hop does not settle.
2. **Investigate each** under
   [`rules/investigation.md`](rules/investigation.md). Stop each one on
   confirm or dismiss.
3. **Add the findings.** A confirmed defect is a finding in `review-core`'s
   shape and severity scale, deduplicated with the Core's findings by root
   cause. A dismissed suspicion adds nothing.
4. **Report what was traced.** Add the "Investigation" section to the
   report after "Findings", and remove from "Not investigated" every concern
   this run settled.
