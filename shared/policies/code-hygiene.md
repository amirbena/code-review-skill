# Shared Policy — Code Hygiene Review

Applies identically to `local-code-review` and `github-pr-review`. It is
the sole owner of the code hygiene pass: the two categories it covers,
its trigger conditions, how each category is evaluated, the evidence bar,
the severity bounds, the false-positive exclusions, and the "candidate,
not proof" rule.

This is a sub-domain of [`review-scope.md`](review-scope.md), which routes
here from its "Code hygiene review" section. It reuses, and does not
restate, [`evidence.md`](evidence.md) (evidence bar),
[`severity.md`](severity.md) (definitions and mechanical Decision
derivation), [`remediation-guidance.md`](remediation-guidance.md), and
[`repository-instructions.md`](repository-instructions.md) (a project's
own naming and traceability conventions win).

## Scope and trigger

Exactly two categories, both **only on the changed delta** (lines the
change adds or modifies, and names it introduces or renames):

1. an issue-tracker reference in a comment that is uninformative,
   redundant, or obsolete;
2. a variable name that hides intent where the surrounding code supports a
   clearer one.

No other hygiene category (dead code, magic numbers, comment density,
formatting, style) is in scope; this is not a linter-like pass and it
introduces no pass runner or script. Pre-existing references and names the
change does not touch are not reviewed.

## Candidate, not proof

A pattern match — a bare `#75`, `JIRA-1234`, `PROJ-456`, `issue 75`, a
`TODO` with a key, a one- or two-letter name, `tmp`, `data` — only makes a
**candidate**. It is never itself a finding. A candidate is reported only
after surrounding code, the comment text, supplied review context, or
PR/commit context supports the conclusion. If it cannot be confirmed, drop
it.

## Issue-tracker references

Keep a reference — report nothing — when it documents an active
workaround, a known limitation, an architectural decision, an external
contract, a compatibility constraint, or project-required traceability
(including a convention stated in repository instructions).

Recommend removal or rewrite when the reference is **obsolete**
(the workaround, limitation, or code it described is demonstrably gone),
**redundant** (the code or an adjacent comment already says it), or
**uninformative** (the comment is only the reference and a reader cannot
tell what it means or why it matters). The recommendation is concrete:
state the rewrite that preserves the useful fact, or say the comment can
be deleted.

Staleness is judged from **local evidence only**. Never look the tracker
up, never call an issue-tracker API, and never treat unknown tracker state
as proof a reference is stale. A `TODO` that marks a real defect is
reviewed as that defect under the normal rules, not as hygiene.

## Variable naming

Suggest a rename only when the name hides intent **and** the surrounding
code supports exactly one concrete better name (from the assigned value,
the consuming expression, adjacent identifiers, or the domain vocabulary
the file already uses). The finding or observation states the suggested
name. Prefer one concrete suggestion over generic criticism.

Never report: conventional loop indices and comprehension variables; short
names with clear local meaning; standard domain abbreviations; names that
follow an existing project convention; names that cannot be improved
confidently from available context.

## Severity representation (decided)

`severity.md` defines only P0/P1/P2 and the structured-result severity
enum is closed, so no literal `P3` value exists. The "P3" tier is therefore
represented as a severity-less **code hygiene observation**, following the
precedent of "Subjective polish: rendered observations" in
[`rendered-inspection.md`](rendered-inspection.md). P2 is the only finding
severity hygiene can reach. Adding a literal `P3` value would be a schema
change and needs an explicit maintainer decision.

- **Observation (default tier).** Non-blocking, no severity, ID,
  `confidence`, or blocking meaning. Not part of the finding set, never
  an input to the Decision tally or coverage, never changes a finding's
  identity, never rendered inline or published as a review event. At most
  **3** per review; when more qualify, keep those in files with the
  larger changed delta, then path order. Dropped observations are not
  reported.
- **P2 finding.** Only with causal evidence, stated in the finding, that
  the issue carries real maintainability, comprehension, or change-risk
  cost — for example a misleading name that two call sites already use
  with the opposite meaning, or a reference that sends a maintainer to the
  wrong place for a still-live constraint. It then follows the normal
  finding rules, including the evidence bar.
- **Never P0/P1** for hygiene alone: a tracker reference, `TODO`, short
  name, or naming style never blocks. A genuine correctness or security
  concern found nearby is assessed under its own rules; this policy
  changes none of them.
- If cosmetic taste is all that remains, `severity.md` forbids P2; it is an
  observation or nothing.

Observation placement and shape are owned by
[`../templates/review-summary.md`](../templates/review-summary.md),
"Code hygiene observations."

## Relationship to other passes

No tracker integration, no network access, and no repository-wide hygiene
audit: the pass is bounded to the changed delta per
[`evidence.md`](evidence.md), "Findings beyond the changed lines." It is
not a second scope model and does not alter the correctness or security
behavior of any other pass.
