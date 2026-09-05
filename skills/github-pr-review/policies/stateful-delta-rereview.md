# Policy — Stateful Delta Re-Review Execution

Installs, as packaged runtime behavior, the orchestration Issue #64's
semantic contract (§9 there) assigns to Issue #65: *"Orchestrating the
load → classify → invoke-#59 → apply-#62 sequence at runtime, or any
GitHub/local publication plumbing."* This policy is the single normative
source for that orchestration. It implements #64's semantics; it does
not redefine them, and it does not redefine the finding-identity/matching
contracts (#58/#59/#60) or the lifecycle contract (#62) it invokes — see
"Reuse, do not redefine" below. Section references below (`#58 §n`, `#64
§n`, and similar) cite this repository's own unpackaged design-record
history for traceability only; this policy never depends on any such
record being present at runtime — every rule this policy actually
applies is stated here in full.

Canonical index: [`github-review.md`](github-review.md). Runs immediately
after [`reviewer-delta-review.md`](reviewer-delta-review.md) has resolved
*which* delta this invocation reviews (same-reviewer identity check,
delta boundary `previously reviewed SHA → current PR HEAD`, or `NO NEW
DELTA`/full-review fallback). This policy governs *what a delta
re-review does with that boundary* once it is set: whether reliable prior
finding/lifecycle state exists to reconcile against, and, when it does,
how findings from the current pass are reconciled with it.

```text
reviewer-delta-review.md resolves the delta boundary
        ↓
this policy: is reliable prior finding/lifecycle state available?
   ├─ no  → proceed as a normal full review of the resolved scope
   │        (no reconciliation state; every current-pass finding is a
   │        first `DETECTED`, exactly as any first review)
   └─ yes → load it, classify each identity/candidate (#64 §2),
            invoke #58/#59/#60 matching, apply #62 lifecycle transitions,
            watch the #64 §7 escalation triggers throughout
        ↓
review-output.md — Final decision (severity/verdict unaffected by any of
the above) and exact-HEAD binding
```

## 1. Reuse, do not redefine

This policy adds no second identity system, no second matching
algorithm, no second lifecycle model, and no second reviewed-state
schema. It orchestrates the existing ones:

- **Reviewed state** (#63) — repository identity, base branch/SHA,
  merge-base, reviewed head SHA, reviewer identity, review result,
  completeness, prior reviewed SHA, provenance, optional evidence
  reference. For `github-pr-review` this record is reconstructed from
  GitHub-native evidence already in scope: the immediately preceding
  **completed** review (identity, reviewed commit) per
  [`reviewer-delta-review.md`](reviewer-delta-review.md), any published
  SHA-bound status per
  [`review-status-enforcement.md`](review-status-enforcement.md), and
  prior review/issue comments per
  [`review-evidence.md`](review-evidence.md). There is no separate
  on-disk store — the strongest available GitHub evidence *is* the
  record.
- **Finding identity / matching** (#58/#59/#60) — `MATCH`, `NO MATCH`,
  `AMBIGUOUS` exactly as this repository's identity and matching design
  records define them, using the same stable-identity construction
  discipline: a prior finding continues under the same identity only on
  a definite `MATCH`; `NO MATCH` mints (or keeps) an independent
  identity; `AMBIGUOUS` authorizes no transition at all (§3 below). This
  policy does not add a fourth outcome, a confidence score, or a
  heuristic shortcut around any of the three.
- **Lifecycle** (#62) — states `OPEN`/`RESOLVED` and events `DETECTED`,
  `STILL_PRESENT`, `RESOLVED`, `REOPENED`, `UNCERTAIN` exactly as this
  repository's lifecycle design record defines them, including its §5
  resolution evidence bar and §6 reopen/recurrence handshake. This
  policy supplies the coverage and delta-attribution inputs those bars
  require (§3, §4 below); it does not loosen either bar.
- **Delta semantics** (#64) — the six change classes, blast-radius rule,
  settled-assumption rule, and escalation triggers this repository's
  delta re-review design record defines, consumed verbatim below.

Where this policy appears to add detail beyond those semantics, it is
*execution* detail (when to load state, in what order to invoke the
above, what to do when a step cannot complete) — never a new semantic
rule about identity, matching, or lifecycle.

## 2. Eligibility — reliable prior state, fail closed

Stateful delta re-review over prior findings/lifecycle state is available
for this invocation only when **all** of the following hold. This is in
addition to, not a replacement for, `reviewer-delta-review.md`'s own
same-reviewer/reviewed-SHA gate — that gate decides the delta *boundary*;
this gate decides whether prior *finding/lifecycle* state may be
reconciled within it.

1. **Repository identity** — the immediately preceding completed review
   and the current invocation target the same repository.
2. **PR/review scope** — the preceding review's base branch, base SHA,
   and merge-base SHA at that time are recorded or reliably
   reconstructable, so this invocation can detect base movement rather
   than assume none occurred.
3. **Same reviewer identity** — resolved exactly as
   [`reviewer-delta-review.md`](reviewer-delta-review.md), "Reviewer
   identity" requires: the strongest available authenticated-identity
   evidence on both sides, never inferred from task wording, branch
   name, commit author, or the mere existence of a prior review.
4. **A reliable previously reviewed SHA** — it still exists and is an
   ancestor of the current HEAD (not merely "the last commit
   mentioned"); a rebase or force-push that breaks ancestry disqualifies
   it.
5. **Trustworthy prior finding/evidence state** — the preceding review's
   findings are recoverable from authoritative provenance (a submitted
   GitHub review by the same reviewer identity, a published SHA-bound
   status per
   [`review-status-enforcement.md`](review-status-enforcement.md), or
   directly-quoted prior review/issue comments) — never inferred from
   ambiguous or partial signals.

**Fail closed.** If any precondition cannot be established with
confidence — missing, ambiguous, contradictory, or only weakly
evidenced — do not infer, do not guess a boundary, and do not partially
reconcile. Proceed as a normal review of the scope `reviewer-delta-review.md`
already resolved (full review if that policy's own gate already selected
full; otherwise a delta-boundary review with no reconciliation state,
where every current-pass observation is a first `DETECTED`). This mirrors
this repository's reviewed-state design record's (#63) §7 "fail
conservative" table and
[`reviewer-delta-review.md`](reviewer-delta-review.md)'s "fail
conservative — an uncertain match must never unlock delta-only
re-review." A missing *optional* evidence reference alone is never a
disqualifier; a missing required field is.

Report which path was used exactly as
[`reviewer-delta-review.md`](reviewer-delta-review.md), "Reporting the
mode" already requires; this policy adds no second reporting format.

## 3. Reconciliation — the #64 change classes, operationally

When eligibility (§2) holds, reconcile the current pass against prior
state in this order, for every prior finding identity and every current
candidate observation:

1. **Establish coverage.** Confirm the prior finding's logical site (or
   its blast-radius extension, §4) was actually re-inspected in this
   pass — the #62 §5 "verified relevant coverage" input. A site never
   opened during this pass cannot be classified `Fixed`; it can only be
   `Unchanged` (§2 of #64, "Unchanged is a re-analysis-scope conclusion,
   not a lifecycle event").
2. **Run identity matching (#58/#59/#60).** For each prior identity
   against current candidates at or near its site (or, for a
   `RESOLVED` prior identity, against a recurrence-candidate observation
   per #62 §6), obtain `MATCH`, `NO MATCH`, or `AMBIGUOUS`. This policy
   never substitutes a proximity or line-number heuristic for this step.
3. **Classify the change class**, per #64 §2:

   | Matching/coverage outcome | Change class | Lifecycle event applied |
   |---|---|---|
   | Not touched by the delta, no blast-radius attribution reaches it | Unchanged | none — prior state carried forward as-is |
   | `MATCH`, current evidence meets the full #62 §5 resolution bar | Fixed | `RESOLVED` |
   | `MATCH`, defect-bearing condition persists at a new site | Moved | `STILL_PRESENT`, stays `OPEN` |
   | Prior `RESOLVED` identity, recurrence-candidate evidence, `MATCH` under the #62 §6 recurrence exception | Reopened | `REOPENED`, becomes `OPEN` |
   | No `MATCH` to any prior identity, independently meets the finding evidence bar | Newly introduced | `DETECTED` |
   | `AMBIGUOUS` for the relationship under consideration | Ambiguous | `UNCERTAIN`, prior state preserved |

4. **Apply the #62 transition**, never a shortcut around its evidence
   bars. In particular:
   - **`AMBIGUOUS` never becomes a confident transition.** An `AMBIGUOUS`
     matching outcome is reported as `UNCERTAIN` with the prior state
     preserved — never inferred into `Fixed`, `Moved`, or `Reopened`
     however plausible the inference looks (#64 §8).
   - **A resolved prior finding never implies a clean fix.** The lines
     that resolve a prior identity are newly written code in this
     pass's own delta and are evaluated for new findings using the same
     evidence/severity model as any other code (#64 §3, §5) — a
     `RESOLVED` event on one identity has no bearing on whether the same
     lines, or lines reachable from them, introduce an unrelated defect.
   - **File/line movement is never, by itself, a new-finding signal.**
     A `MATCH` after a refactor/rename/extraction is `Moved`
     (`STILL_PRESENT`), not `DETECTED` (#64 §8, "Moved code ≠ a new
     finding").
   - **Disappearance from the diff is never, by itself, resolution.** A
     prior finding not visible in the literal changed lines is
     `Unchanged`, not `Fixed`, unless the #62 §5 resolution bar is
     actually met (#64 §2, "Unchanged" notes).

## 4. Blast radius and regressions

A regression or a newly introduced defect need not sit on the exact
lines the delta changed to be in scope.

- **Evidence-based attribution only.** A location is in scope via blast
  radius only when a concrete causal path connects it to a changed
  line/behavior — a caller of changed logic, a shared
  type/schema/contract the change alters, a config value it repurposes,
  a test/caller relying on removed behavior, or a broken
  interface/implementation pairing. Same file or "nearby" is not
  attribution (#64 §4).
- **Bounded, not repository-wide.** Follow the evidenced causal chain
  outward from the delta until it runs out, then stop. A candidate with
  no statable mechanism connecting it to the delta is out of scope for
  this delta re-review (it may still merit a separate task).
- **A blast-radius finding is a normal finding.** It uses the same
  evidence/severity model as anything else and is classified `Newly
  introduced` unless it independently matches a prior identity (§3).

## 5. Previously settled non-findings and assumptions

A completed prior review's conclusion that something is *not* a finding,
or that an assumption holds, is reusable evidence per
[`review-evidence.md`](../../../shared/policies/review-evidence.md)
("prior review conclusions are reusable evidence, not immutable truth")
— never a fact this pass must take on faith:

- **Remains settled** while the delta leaves its basis, and that basis's
  blast radius (§4), untouched.
- **Reconsidered** — using the same evidence bar as any other
  determination — when the delta changes code, configuration, or context
  the conclusion depended on, directly or via an attributable
  blast-radius path. "The delta touched the same file" alone is not
  sufficient; name the concrete causal/structural connection.
- A reconsidered assumption that no longer holds becomes a normal finding
  (§4 above); there is no separate "formerly settled, now a defect"
  path (#64 §6).

## 6. Escalation to a broader/full review

Stop treating the review as safely bounded — and fall back to a normal
full review of the current PR state, superseding the delta boundary
entirely — whenever the delta materially invalidates enough of the
following that reconciliation can no longer produce a trustworthy
result. These are the four semantic triggers #64 §7 defines; this policy
invents no numeric threshold (file/line/finding counts) beyond them:

- **Prior assumptions invalidated** — the delta changes an architectural
  or behavioral premise multiple settled conclusions (§5) or prior
  findings depended on, such that re-validating them piecemeal would not
  reconstruct a coherent picture of the current state.
- **Blast radius cannot be bounded** — the delta is large, structurally
  different, or distant enough from the originally reviewed shape that
  its causal chains (§4) become too numerous or too uncertain to trace
  individually.
- **Matching is broadly unreliable** — `AMBIGUOUS` outcomes (§3 step 2)
  are persistent or pervasive across a meaningful share of the prior
  finding set, not merely a single ambiguous identity.
- **Reviewed-state preconditions are violated** — any §2 eligibility
  condition fails for a way that §2's fail-closed path alone does not
  already cover (for example, base movement whose interaction with the
  delta cannot be reconciled from recorded state).

When in doubt, escalate. Escalating is not a failure outcome: a delta
re-review that escalates and completes as a full review still supersedes
the same-reviewer predecessor it started from (this repository's
reviewed-state design record's (#63) §5 `completeness = full`, `prior`
still recorded). An escalated review is reported as the full review it
became — never as a partial delta result presented as complete.

## 7. Exact-HEAD safety

This policy adds no new HEAD-safety mechanism and never weakens the
existing one. The final result — findings, per-finding lifecycle state,
and the overall decision — is bound to the exact PR HEAD actually
reviewed, exactly as
[`review-output.md`](review-output.md), "HEAD revalidation" and
"Submission ordering," and
[`review-status-enforcement.md`](review-status-enforcement.md), "Exact
reviewed-HEAD binding," already require. In particular, when HEAD
advances during this policy's own load → classify → reconcile →
escalate sequence:

- do not publish findings, a `REVIEW CLEAN` decision, machine-readable
  status, or a GitHub review submission computed against the
  now-superseded HEAD;
- re-run HEAD revalidation per `review-output.md` before any
  publication step, exactly as for a normal review; and
- if HEAD advanced, treat this as a fresh delta re-review of the new
  boundary (`this invocation's original reviewed SHA seed → new HEAD`),
  or, if `reviewer-delta-review.md`'s own boundary re-resolution or this
  policy's §6 escalation triggers now apply, follow those paths instead.

A per-finding lifecycle state is never published for a HEAD other than
the one it was actually evaluated against.

## 8. Normal finding semantics remain authoritative

Every finding surfaced through this policy — reconciled, blast-radius, or
newly introduced — uses the unchanged evidence requirements
([`evidence.md`](../../../shared/policies/evidence.md)) and P0/P1/P2
severity model
([`severity.md`](../../../shared/policies/severity.md)). There is no
separate re-review severity scale and no down-weighting merely because a
finding surfaced during a bounded pass. The mechanical decision
derivation in `severity.md`, "Decision derivation (mechanical)," runs
unchanged: a newly introduced P1 remains a P1, and blocks the decision,
even when every prior finding resolved to `RESOLVED` in the same pass
(#64 §5).

## 9. Output — per-finding lifecycle state and re-review summary

When eligibility (§2) held for this invocation, the human-facing review
additionally states, for each finding carried forward or newly reported,
its lifecycle event from §3's table (`DETECTED`, `STILL_PRESENT`,
`RESOLVED`, `REOPENED`, or `UNCERTAIN`) alongside its normal severity and
evidence — never in place of them. When eligibility did not hold (§2
fail-closed) or this pass escalated (§6), state that plainly (for
example, "no prior reviewed state was available; every finding below is
a first detection" or "escalated to a full review: <trigger>") rather
than silently proceeding as if it were a bounded delta re-review. This is
additive to, not a replacement for, `reviewer-delta-review.md`'s existing
"Reporting the mode" contract and `review-output.md`'s "Final decision"
contract.

## 10. Scope boundaries

This policy governs orchestration only. It explicitly does **not**
define, and must not be read as redefining:

| Not defined here | Owner (Issue) |
|---|---|
| What makes two findings "the same"; the matching algorithm and its proof gates | #59 |
| Stable finding ID construction | #60 |
| Lifecycle states, events, and the resolution/reopen evidence bars themselves | #62 |
| The reviewed-SHA state record's fields and authoritative-SHA rule | #63 |
| Change-class semantics, blast-radius/settled-assumption rules, and escalation triggers themselves | #64 |
| P0/P1/P2 meanings and mechanical decision derivation | [`severity.md`](../../../shared/policies/severity.md) |
| Which commits the delta covers, `NO NEW DELTA`, and mode reporting | [`reviewer-delta-review.md`](reviewer-delta-review.md) |
| HEAD revalidation mechanics and exact-HEAD status binding themselves | [`review-output.md`](review-output.md), [`review-status-enforcement.md`](review-status-enforcement.md) |
| The comprehensive delta/regression fixture matrix and executable scenario histories | [#66](https://github.com/amirbena/code-review-skill/issues/66) |

`local-code-review` does not load this policy: it is architecturally
stateless (`skills/local-code-review/SKILL.md`, "Statelessness and
Orchestration Boundary") and has no persisted reviewed-state analogue to
reconcile against between invocations. Its own re-review-adjacent
behavior — the staged-delta fingerprint short-circuit
(`policies/repository-state.md` in that Skill's own package) and
PR-reference reconciliation (`policies/pr-context.md` in that Skill's
own package) — is unchanged by this policy.
