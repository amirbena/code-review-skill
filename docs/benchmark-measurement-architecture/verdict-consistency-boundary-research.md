# Verdict-Consistency Boundary — Research Recommendation

Repository-development research for GitHub Issue
[#351](https://github.com/amirbena/code-review-skill/issues/351), part of
the architecture defined in
[`benchmark-measurement-architecture-model.md`](benchmark-measurement-architecture-model.md),
§12.4 ("Verdict integrity: benchmark proof and the consistency-boundary
research," second bullet). Answers whether a deterministic runtime step
should reconcile a live review's rendered findings, its rendered
Result/Decision, and (for `github-pr-review`) its submitted GitHub review
event before or at publication — and if so, what it consumes, where it
lives, and what it does on a detected mismatch.

This document is a research record, like
[`../../runtime_platform/benchmark/claim-correspondence-adequacy.md`](../../runtime_platform/benchmark/claim-correspondence-adequacy.md)
(#343). It recommends, **without implementing**, the smallest deterministic
check that would close the gap §12.4 identifies. It does not redesign
[`shared/policies/severity.md`](../../shared/policies/severity.md)'s
derivation: every recommendation below only ever *checks* that
derivation's output against what was actually rendered and published, and
never recomputes severity or the decision by a second, independent path.

---

## Decision

**Build now, narrowly scoped to the existing fixed-vocabulary markers —
do not wait for #67/#71's machine-readable schema.** The check this
research recommends never needs to parse prose: `severity.md`'s mechanical
derivation already closes over a two-value decision set
(`REVIEW CLEAN`/`CHANGES REQUIRED` locally, `Approve`/`Request Changes` on
GitHub), and a GitHub review event is already a closed three-value API enum
(`APPROVE`/`REQUEST_CHANGES`/`COMMENT`). A comparator that reads "does the
rendered/submitted value match what the finalized findings already
mechanically derive" needs only those literal tokens, not a general
markdown parser and not #67/#71's structured output. Waiting for the
schema would leave the live gap open against two dependencies (#67, #71)
that are open with no committed timeline — exactly the kind of avoidable
delay the canonical design's §12.1 table warns against ("nothing named in
this section is runtime-enforcing by default" is a statement about scope
discipline, not about deferring a narrow, cheap check that is needed
regardless of when the schema lands).

The reconciliation point is **pre-publish, not post-publish**, at four call
sites (one for `local-code-review`, three across `github-pr-review`'s
modes — see "Reconciliation points" below), and the action on a detected
mismatch is **withhold-and-report**, never self-correct.

---

## 1. Build path: MVP-now vs. wait-for-schema

| | MVP-now (parse the existing fixed markers) | Wait-for-schema (#67/#71) |
| --- | --- | --- |
| **What it reads** | The literal decision strings `severity.md` already names verbatim (`REVIEW CLEAN`, `CHANGES REQUIRED`, `Approve`, `Request Changes`), the count of P0/P1-tagged findings in the finalized finding set, and (ACTIVE only) the literal GitHub review `event` value about to be submitted. | Two typed fields the schema would expose directly (`decision`, `findings[].severity`), no token matching. |
| **Availability** | Available today; consumes nothing not already committed. | Blocked on #67 and #71, both open, neither scoped or timelined — #351 explicitly does not decide their scope or timeline. |
| **Robustness** | Anchored to literal strings `severity.md` treats as its own canonical vocabulary (not to surrounding prose), so a wording edit elsewhere in a template does not silently break it; a change to the vocabulary itself is already a `severity.md` change under the same review discipline as everything else in that file. | Immune to prose changes by construction — reads structured data. |
| **Throwaway risk** | The comparator's *logic* (three-way equality between derived decision, rendered label, submitted event) does not change when #67/#71 ships; only its *input adapter* changes, from a literal-token scan to a schema field read. Not wasted work — the risk is a small adapter swap, not a rewrite. | None, but at the cost of leaving the gap open indefinitely. |
| **Recommendation** | **Build this.** | Defer; re-use the same comparator with a swapped input adapter once available. |

Scope the MVP narrowly: a token/marker check over the already-fixed
vocabulary, not a general-purpose markdown parser. General parsing would
both be unnecessary (the only values that matter are already a closed set)
and would itself become a second place that could drift from
`severity.md`, which is exactly the failure mode this research exists to
close, not reintroduce one layer up.

## 2. Mismatch, defined precisely

A **mismatch** exists when `severity.md`'s mechanical derivation —
`blocking_findings = {f : severity(f) in {P0, P1}}`, non-empty →
blocking, empty → clean — applied to the **finalized** finding set
disagrees with either of two independently-observable, already
fixed-vocabulary signals:

- **(a) Rendered Result/Decision label** — the literal decision string
  actually rendered in the report body (`local-code-review`: `REVIEW
  CLEAN`/`CHANGES REQUIRED`; `github-pr-review`, any mode: the summary's
  `Approve`/`Request Changes` wording, or SEMI's `WOULD PUBLISH
  Approve`/`WOULD PUBLISH Request Changes` declaration).
- **(b) Submitted GitHub review event** (`github-pr-review`, ACTIVE mode
  only) — the literal `event` value (`APPROVE`/`REQUEST_CHANGES`/
  `COMMENT`) in the review payload about to be sent to GitHub's API.

Two cases are **not** mismatches, and the check must special-case them
rather than error on them:

- **Coverage-incomplete outcomes.** Per `severity.md`'s own carve-out
  (via [`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md)),
  an incomplete-coverage top-level outcome (`REVIEW INCOMPLETE`) legitimately
  overrides the clean/blocking value the mechanical derivation would
  otherwise produce. This is the one place `severity.md` already
  documents a sanctioned override; the boundary check must recognize it as
  such and pass it through, not flag it as disagreeing with the
  finding-derived value.
- **No formal event submitted.** A self-review (formal `APPROVE`/`REQUEST
  CHANGES` withheld on the reviewer's own work) or PASSIVE mode (no
  GitHub event at all) has nothing to compare against signal (b); the
  check only ever evaluates signal (a) in those cases.

## 3. Reconciliation points, per Skill and mode

Both Skills already finalize findings and derive the decision once,
before any rendering step —
[`shared/policies/severity.md`](../../shared/policies/severity.md),
"Decision derivation (mechanical)," states plainly that this derivation
"runs exactly once per invocation... and produces exactly one decision
value," and that every later rendering "presents that same single value;
none of them re-derives it independently." The boundary check's job is to
confirm that already-established invariant actually held for this run's
own output — it is inserted immediately after the derivation and
immediately before each place that value gets rendered or transmitted:

- **`local-code-review`**
  ([`skills/local-code-review/runbooks/local-review.md`](../../skills/local-code-review/runbooks/local-review.md),
  step 11, "Derive the Decision"): one pre-render check, between Decision
  derivation and the render step. The runbook already states this output
  step "must not alter the finalized findings or Decision" — the check
  enforces that as a precondition of the render actually running, rather
  than trusting it.
- **`github-pr-review`, PASSIVE and SEMI modes**
  ([`skills/github-pr-review/runbooks/passive-pr-review.md`](../../skills/github-pr-review/runbooks/passive-pr-review.md)):
  one pre-render check, after decision derivation and before "construct
  one review: body + inline comments." No live GitHub event exists yet in
  either mode; SEMI's declared `WOULD PUBLISH Approve`/`WOULD PUBLISH
  Request Changes` line is checked as signal (a)'s value, standing in for
  the event that would be submitted if the mode were ACTIVE.
- **`github-pr-review`, ACTIVE mode**
  ([`skills/github-pr-review/runbooks/active-pr-review.md`](../../skills/github-pr-review/runbooks/active-pr-review.md)):
  **two** check points, not one, because the flow's own "HEAD
  revalidation" step already acknowledges a race between rendering and
  submission:
  1. **Pre-render** — identical placement and check to PASSIVE/SEMI,
     immediately before "construct one review: body + inline comments."
  2. **Pre-publish** — immediately before "submit permitted
     Approve/Request Changes," re-checking that the review event object
     about to be sent to GitHub's API (signal (b)) still agrees with the
     same mechanically-derived decision checked at (1). This catches the
     flow's own "re-confirm HEAD == reviewed HEAD" branch introducing a
     second, silently different render between the pre-render check and
     the actual API call, without requiring the boundary check itself to
     know anything about HEAD revalidation.

**Not post-publish.** A post-publish check could only ever detect a
mismatch after an incorrect, irreversible GitHub review event (an
`Approve` on a PR that actually has blocking findings) has already been
submitted — the wrong side of "block" versus "detect after the fact."
Per `severity.md`'s own single-derivation-once rule, the boundary belongs
entirely before the one irreversible action it protects, never after it.

## 4. Action on a detected mismatch

**Withhold-and-report, never self-correct, and never warn-and-render-anyway.**

- **Self-correct is excluded by existing governance, not just by
  preference.** A check that found a mismatch and then silently
  substituted the "right" value before rendering or submitting would
  itself be a second, independent decision path — precisely what
  [`tests/reference/review/decision_semantics.py`](../../tests/reference/review/decision_semantics.py)'s
  `PROHIBITED_CORRECTION_FRAGMENTS` (`correction`, `correct_decision`,
  `provisional`, `supersede`, `resubmit_decision`, `revise_decision`)
  already names as disallowed. Any implementation that "fixes" a mismatch
  by re-rendering a corrected label is, by construction, one of those
  fragments' underlying behavior with a different name.
- **Warn-and-render-anyway is excluded because it defeats the boundary's
  own purpose.** A mismatch is, by definition, evidence that this run's
  rendering is not trustworthy; publishing it with a caveat still
  publishes the untrustworthy artifact (a GitHub `Approve` on blocking
  findings does not become safe because a warning was attached).
- **Withhold-and-report** mirrors the fail-closed pattern
  `active-pr-review.md` already uses elsewhere in the same flow ("withhold
  publication if unresolved," and the HEAD-revalidation branch: "withhold
  the status AND do not submit"):
  - `local-code-review`: stop before the render step; report an
    internal-consistency failure instead of the report body.
  - `github-pr-review`, pre-render (any mode): do not construct/return the
    review body; report the same internal-consistency failure instead of
    ever showing the mismatched render to the user or the PR.
  - `github-pr-review`, pre-publish (ACTIVE only): withhold the actual
    `Approve`/`Request Changes` API submission and report why formal
    submission is unavailable — exactly the existing "report why formal
    submission is unavailable" branch the flow already has for other
    withhold conditions, extended to cover this one.

**Who is authorized to decide this policy:** not the runtime executing the
check, and not a per-invocation parameter. This is a semantic/architectural
contract in the same family `severity.md` and
`decision_semantics.py`'s governance list already are, so it is
maintainer-owned per
[`policies/contribution-ownership-policy.md`](../../policies/contribution-ownership-policy.md)
and decided once, canonically, in `shared/policies/` — never forked
per-Skill and never exposed as a caller-selectable behavior.

## 5. Governance confirmation

The design above introduces no parameter matching
`decision_semantics.py`'s `PROHIBITED_OVERRIDE_PARAM_FRAGMENTS`
(`override`, `force`, `bypass`, `ignore_severity`, `manual_decision`,
`recommend_block`, `should_block`) or `PROHIBITED_CORRECTION_FRAGMENTS`.
The boundary check takes no argument that lets a caller select a
different outcome; its only two output shapes are "consistent — proceed"
and "inconsistent — withhold and report which signal disagreed." It
reads `severity.md`'s already-finalized derivation as the sole source of
truth for what the correct outcome is, and never computes severity or a
decision by any path of its own.

## 6. Follow-on implementation issue (outlined, not filed)

A future implementation issue, out of this research issue's own scope per
its Non-Goals, would cover:

- **In scope:** one small, shared, read-only comparator (a natural sibling
  of `tests/reference/review/decision_semantics.py`, reused by both
  Skills rather than forked per-Skill) taking the finalized findings'
  severities, the about-to-be-rendered/submitted decision value, and
  returning consistent / inconsistent-plus-which-signal; wiring the four
  call sites identified in §3 (`local-code-review` pre-render;
  `github-pr-review` PASSIVE/SEMI pre-render; `github-pr-review` ACTIVE
  pre-render and pre-publish); the withhold-and-report behavior at each
  site per §4; a benchmark fixture proving a deliberately-mismatched
  rendering is caught before publication (a companion to #350's
  benchmark-proof fixture, which proves the mechanical derivation itself
  holds — this follow-on would prove the *boundary* catches a case where
  it does not).
- **Out of scope for the follow-on issue:** redesigning `severity.md`'s
  derivation or the P0/P1/P2 model; the #67/#71 schema itself (only
  consumed once available — the comparator's input adapter is swapped,
  its logic is not re-scoped); any override or correction capability.
- **Dependency ordering:** none of the above blocks on #67/#71 per the
  build-path decision in §1; if the schema lands first, only the input
  adapter changes.

## Non-goals

Restated from #351 itself, and unaffected by this recommendation:

- No implementation in this issue.
- Does not redesign `severity.md`'s derivation or the P0/P1/P2 severity
  model.
- Does not decide #67's or #71's own scope or timeline.
