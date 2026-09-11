# Template — Local Review Report

Returned by every invocation of `local-code-review`. This is **not** a
GitHub review event and is never published anywhere by the Skill itself
— it is handed back to the caller, once, as a single organized review
(never streamed finding-by-finding as they are discovered — see
[`../SKILL.md`](../SKILL.md), "Statelessness and Orchestration
Boundary"). It follows the shared human-facing shape in
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md);
findings use the shared shape in
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md).
This Skill has no GitHub inline-comment surface, so every finding always
uses the **full rendering** — there is no other delivery location a
finding could already be published to.

```markdown
## Code Review

**Result: ⚠️ Changes Requested**

Not safe to proceed: <highest-priority concern and concrete impact>.
<Optional short attention point; detailed scope stays in Review Metadata.>

### What changed
<concise, concrete implementation summary>

### What was done well
- **<theme>:** <concrete, evidence-backed strength>

### Context
<only present when review context was supplied AND it materially shaped
this review — see
[`../policies/review-context.md`](../policies/review-context.md),
"Output"; omitted entirely otherwise, including whenever no review
context was supplied>
- Reviewed against supplied context`<: source-name, if given>`.
- Focus areas it identified: `<concrete list, e.g. "validation ordering
  on the record-write path">`.
- Non-goals it stated: `<n>` (kept out of scope) — omit this line if none
  apply.
- Mismatches noted: `<n>` (context appears stale/conflicting; flagged
  rather than assumed — see the policy's "Context mismatch vs.
  implementation defect") — omit this line if none apply.

### PR Context
<only present when a PR reference was supplied AND it materially shaped
this review — see
[`../policies/pr-context.md`](../policies/pr-context.md), "Output";
omitted entirely otherwise, including whenever no PR reference was
supplied>
- Reconciled against PR `<url-or-#number>`.
- Existing reviewer findings: `<n>` still valid (reflected in Findings
  below), `<n>` resolved, `<n>` required re-evaluation (reflected below).
- Architectural decisions: `<n>` violated/regressed (reported as a
  finding below) | `<n>` intentionally superseded with new evidence
  (briefly noted here) — omit this line if none apply.

### Findings

#### F1 [P1] Retry can duplicate processing

- **Location:** `src/...:<line>` _(staged)_
- **Evidence:** <concrete evidence, concise>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
- **Implementation prompt:** <only when `include_fix_prompt=true` and a
  full prompt is justified; an evidence-supported coding-agent task
  covering root cause, affected components, required behavior, canonical
  owner, invariants, regression scenarios, non-goals, and validation as
  applicable>
- **Details:** <only when populated and selected by the detail-precedence rule;
  supporting technical context, concise>

A finding that meets
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"When a longer explanation is justified" (non-obvious cross-file
behavior, a concurrency/ordering bug, a security implication, a complex
invariant violation, or evidence that needs brief context) adds one
`- **Details:** <short paragraph>` after `Fix` when
`include_finding_details` resolves true (default `true`) or a finding-level
decision enables it. An ordinary finding does not.

A **consolidated root-cause finding** — one finding standing in for one
shared defect-bearing element that reaches at least two sites, per
[`../../../shared/policies/review-scope.md`](../../../shared/policies/review-scope.md),
"The authoritative consolidated finding" — renders an
`- **Affected locations:**` list directly after `Location`, per
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Affected locations on a consolidated finding":

```markdown
#### F2 [P1] `is_valid_email` accepts partial matches

- **Location:** `app/validators.py:7` _(committed)_
- **Affected locations:**
  - `app/accounts.py:register` — rejects nothing a prefix-match passes
  - `app/newsletter.py:subscribe` — same weakened check
- **Evidence:** <the shared cause, concise>
- **Impact:** <combined engineering consequence across the affected sites>
- **Fix:** <one correction direction at the shared cause / canonical owner>
```

The list is required on such a finding, exhaustive for the sites the
review found, and carries at least two entries; an ordinary single-site
finding never renders it.

### Requirement coverage
**Overall: `<complete | incomplete>`**

- **R1 — `<implemented | partially_evidenced | not_evidenced | not_applicable>`**
  `<source citation>`
  - Evidence: `<code/test/validation evidence>`
  - Explanation: `<status justification; include ambiguity when applicable>`

<Omit this entire section unless authoritative requirements or acceptance
criteria activated
[`requirement-coverage.md`](../../../shared/policies/requirement-coverage.md).
When active, retain every requirement and place this section before
Validation.>

### Validation
- <one record per selected command, or an explicit no-command record, per
  [`../../../shared/policies/runtime-validation.md`](../../../shared/policies/runtime-validation.md):
  `executed`, `skipped`, `failed`, or `unavailable`, with command, source,
  scope/justification, evidence, and reason>

### Decision
**CHANGES REQUIRED**

1 P1 finding must be addressed before this implementation should
proceed.

### Review Metadata

- Base branch: `<name>`
- Base SHA: `<sha>`
- Local HEAD: `<sha>`
- Remote HEAD: `<sha | none>`
- Synchronization status: <in sync | local ahead | local behind | diverged | no tracking branch>
- P0: <n>, P1: <n>, P2: <n>
- Change-risk depth: <standard | elevated | deep>
- Change-risk signals: <none | comma-separated `signal (tier) — evidence` entries, one per resolved occurrence>
- Repository expansion: <none | comma-separated `trigger (ring N) — locations` entries, one per fired trigger>

**Review scope contract** (per
[`../policies/repository-state.md`](../policies/repository-state.md)) —
states plainly what was inspected; a category marked "excluded" is a
deliberate, stated exclusion, never a silent omission:

- Committed delta relative to base: <included, `<base>..HEAD` summary | excluded, reason>
- Staged: <included, files/delta summary | excluded, reason>
- Unstaged: <included, files/delta summary | excluded, reason>
- Untracked: <included, files | excluded, reason>
- Review kind: <initial review | re-review>
- Staged-delta fingerprint (SHA-256 of `git diff --cached --raw -M -z`): `<hex digest>` — shown when relevant per "Relevance-aware metadata rendering" below; omitted otherwise
- Previously reviewed state changed: <staged: unchanged/changed — fingerprint compared; unstaged: unchanged/changed — re-detected; untracked: unchanged/changed — re-detected> — re-review only; omitted entirely for an initial review
```

or, when clean:

```markdown
**Result: ✅ Review Clean**

Safe to proceed: no blocking or non-blocking findings were identified.

<optional concise What changed and Validation sections; omit Findings when
empty. When requirement coverage was active, include the full conditional
Requirement coverage section before Validation; omit it only when inert.>

### Decision
**REVIEW CLEAN**

No P0, P1, or P2 findings were identified in the reviewed implementation
state.
```

or, clean while still preserving a non-blocking P2 (a P2 finding never
by itself changes the decision — see
[`../../../shared/policies/severity.md`](../../../shared/policies/severity.md),
"Decision derivation (mechanical)"):

```markdown
**Result: ✅ Review Clean**

...

### Findings

#### F1 [P2] Repository style convention violation

- **Location:** `src/...:<line>` _(staged)_
- **Evidence:** <concrete evidence, e.g. the target repository's
  `AGENTS.md` states the convention and the staged delta violates it>
- **Impact:** <concrete engineering consequence — maintainability/
  consistency, not a correctness or safety defect>
- **Fix:** <concrete correction direction>

### Decision
**REVIEW CLEAN**

No P0 or P1 (blocking) findings were identified; the P2 finding above is
a non-blocking recommendation and does not change this decision, however
strongly it is recommended before commit.
```

## Rules

These are the report's **rendering** rules; the review semantics they
serve are owned by the linked policies and are not restated here.

- The human-facing body (Result → What changed → What was done well →
  [Context] → [PR Context] → [Findings] → Validation → Decision) is
  primary and always appears first — see
  [`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md).
- **Unresolved supplied Jira reference** — the report is not graded: it
  leads with `**Result: ⚠️ Jira context unresolved**`, names the
  reference and integration(s) attempted, uses no key/branch/PR-title
  inference, omits Findings and Decision, and its machine outcome is
  `JIRA CONTEXT UNRESOLVED`. Canonical:
  [`../../../shared/policies/review-context.md`](../../../shared/policies/review-context.md),
  "Jira context resolution".
- **Context** and **PR Context** are optional pointer sections, each
  rendered only when the corresponding input was supplied and materially
  shaped the review, and omitted completely otherwise — no placeholder,
  no empty section. For `Context` this is the default backward-compatible
  case; for `PR Context`, this is the no-PR backward-compatible case and
  the default. A context- or PR-derived finding's provenance belongs in
  that finding's own **Evidence** field, never as a second listing here.
  Canonical: [`../policies/review-context.md`](../policies/review-context.md),
  "Output"; [`../policies/pr-context.md`](../policies/pr-context.md),
  "Output".
- **Decision** is exactly `REVIEW CLEAN` or `CHANGES REQUIRED`, derived
  mechanically per
  [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md),
  "Decision derivation (mechanical)"; any number of P2 findings never
  produce `CHANGES REQUIRED`. The one-sentence rationale explains that
  mechanical result and never contradicts it.
- Every finding uses the compact full rendering in
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
  (stable `F<n>` id + `[severity]` heading, then
  `Location` / `Evidence` / `Impact` / `Fix`), each field concise but
  never dropping evidence, impact, or fix. A `Details` field is added
  only for a finding that satisfies that contract's "When a longer
  explanation is justified"; a consolidated root-cause finding renders
  the required `Affected locations` list after `Location`. The `Location`
  value also carries this Skill's local trailing source-category
  annotation — `(committed)` / `(staged)` / `(unstaged)` / `(untracked)`
  — per that contract's "Location source annotation" and
  [`../policies/repository-state.md`](../policies/repository-state.md),
  "Attribution in findings"; when the shared unresolved-fix marker also
  applies, the source-category annotation comes first.
- **Validation** records `executed` / `skipped` / `failed` /
  `unavailable` explicitly per the shared
  [`runtime-validation.md`](../../../shared/policies/runtime-validation.md)
  contract; non-execution is never implied to have passed.
- **Remediation rendering.** Apply
  [`../../../shared/policies/remediation-guidance.md`](../../../shared/policies/remediation-guidance.md).
  `include_fix_prompt` defaults to `false` (omit the **Implementation
  prompt** field entirely); when explicitly true, at most one prompt per
  root-cause finding, after the concise `Fix`. The flag is output-only:
  findings, severities, evidence, reconciliation, and Decision are
  identical on and off.
- **Finding details.** Apply
  [`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
  "Finding-detail precedence." `include_finding_details` defaults to `true`.
- **Concise human-style output (opt-in).** When the invocation selects
  `human_review_output` (natural language only — per
  [`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
  "`human_review_output` phrasings"; default `false`), render the
  human-facing body in the concise senior-engineer voice from
  [`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
  "Concise human-style summary (opt-in)". It re-renders only that body —
  the trailing "Review Metadata" and "Review scope contract" sections
  still follow it, subordinate and unchanged, and nothing else is
  appended after the summary. The option is output-only: findings,
  severities, evidence, reconciliation, source attribution, and the
  mechanical Decision are identical on and off.
  Active requirement coverage also remains visible with its overall signal
  and every requirement/status; its wording may be condensed, but it is
  omitted only when coverage analysis was inert.
- **Review State** (base/HEAD SHAs, synchronization status, raw counts)
  is subordinate machine detail — it appears only inside the trailing
  "Review Metadata" section as plain Markdown, never ahead of the
  human-facing review and never wrapped in GitHub-oriented HTML
  (`<details>` / `<summary>`), which adds nothing for a report read in a
  terminal. This is a Skill-specific presentation choice; shared review
  reasoning does not imply identical human-facing formatting, so
  `github-pr-review`'s template legitimately uses a collapsible block —
  see
  [`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
  "Machine metadata is subordinate".
- **Review scope contract** is required in every report: state plainly
  whether committed/staged/unstaged/untracked state was included and
  whether this is an initial review or a re-review. An excluded category
  is stated as excluded with a reason, never silently dropped.
- **Change-risk depth** (`standard` / `elevated` / `deep`) and its
  activating signals are always rendered in "Review Metadata" per
  [`../../../shared/policies/change-risk-signals.md`](../../../shared/policies/change-risk-signals.md),
  "Rationale emission" — including `standard` with no signals. It is
  subordinate metadata, never a finding, and never changes the Decision.
- **Repository expansion** — the fired expansion triggers, the ring each
  reached, and the locations inspected are always rendered in "Review
  Metadata" per
  [`../../../shared/policies/repository-expansion.md`](../../../shared/policies/repository-expansion.md),
  "Expansion decisions are reported" — including "none" when no trigger
  fired. It is subordinate metadata, never a finding, and never changes
  the Decision.
- **No loop/orchestration metadata.** This report never tracks review
  iteration count, a configured maximum, or whether another iteration is
  allowed — that belongs to the orchestrator (see
  [`../SKILL.md`](../SKILL.md)).
- Return only what the implementing Agent needs to act.

### Relevance-aware metadata rendering

Every value in "Review Metadata" — including the staged-delta fingerprint
and the previously-reviewed-state comparison — is still **always
computed** exactly as [`../policies/repository-state.md`](../policies/repository-state.md)
requires; nothing here changes what this Skill must determine internally,
only what it prints. The fingerprint remains mandatory internal state
because a future re-review needs the *current* value to compare against
regardless of whether it was rendered this time, and because "previously
reviewed state changed" cannot be answered without it having been
computed.

Rendering the two fields below is relevance-gated rather than
unconditional, so an initial review of an empty staged delta doesn't pad
the report with a fixed, information-free hash:

- **Staged-delta fingerprint** — render it when it is operationally
  relevant: the staged category is non-empty, this is a re-review, the
  caller supplied a previously reported fingerprint for comparison, or
  the fingerprint comparison materially affected review behavior (the
  short-circuit in
  [`../policies/repository-state.md`](../policies/repository-state.md),
  "Fingerprint scope and re-review comparison," was actually used or
  explicitly did not apply). Omit it when none of these hold — most
  commonly, an initial review with nothing staged, where the fingerprint
  is the well-known SHA-256 of empty input and adds no human value.
- **Previously reviewed state changed** — render it only for a re-review,
  where a previous invocation's reported state is the actual comparison
  baseline. For an initial review, omit the line entirely rather than
  printing a fixed not-applicable placeholder — "Review kind: initial
  review" already says everything a reader needs to know about why no
  comparison is shown.

This never affects the Decision, the findings, or any other internal
review requirement — it is a rendering choice applied after every
required value has already been determined.
