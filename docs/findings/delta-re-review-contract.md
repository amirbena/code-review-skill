# Delta Re-Review — Semantic Contract

Repository-development contract for GitHub Issue
[#64](https://github.com/amirbena/code-review-skill/issues/64). It defines
the semantics of computing and evaluating a **review delta** relative to a
prior reviewed state — the change classes a re-review must be able to
recognize, how each maps to the [`finding-lifecycle-contract.md`](finding-lifecycle-contract.md)
transitions, which prior findings re-surface vs. suppress, and when bounded
delta re-review must escalate to a broader/full review.

This is authoritative until [#65](https://github.com/amirbena/code-review-skill/issues/65)
installs equivalent runtime behavior in a packaged shared policy. That
policy then becomes the single normative source and this document becomes
its design record, exactly as
[`finding-identity-requirements.md`](finding-identity-requirements.md) and
[`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) already
describe for themselves.

## Canonical invariant

> **Delta re-review is an optimization of re-analysis scope, not a restriction on what may become a finding.**

Bounding re-analysis to the delta exists to reduce redundant re-inspection
of unchanged, still-settled code. It must never suppress a defect
attributable to the new delta. Every rule in this document is an
elaboration of that one sentence; where a rule below appears to narrow
what may be reported, re-read it as a scoping-of-effort rule, never as a
finding-eligibility rule. A defect the reviewer becomes aware of, however
it was noticed, is reportable — this contract only bounds where the
reviewer is obligated to *look*.

## 1. Terminology and ownership

- **Reviewed state** — the Reviewed State Record defined by
  [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md)
  (#63): repository identity, base branch/SHA, merge-base, reviewed head
  SHA, reviewer identity, review result, completeness, prior reviewed SHA,
  provenance, and an optional evidence reference. This contract consumes
  that record; it does not redefine any field in it.
- **The delta** — the change under evaluation by a re-review: at minimum
  the commit range `recorded merge-base .. current head` (or, for local
  review, the analogous carried-forward committed/staged/untracked change
  set per
  [`../../skills/local-code-review/policies/repository-state.md`](../../skills/local-code-review/policies/repository-state.md)),
  together with any base-branch movement §3 of #63 makes detectable. The
  delta is a *scope-of-effort* boundary, never a *scope-of-eligibility*
  boundary (Canonical invariant, above).
- **Finding identity / matching outcome** — exactly as defined by
  [`finding-identity-requirements.md`](finding-identity-requirements.md)
  (#58) and [`finding-matching-strategy.md`](finding-matching-strategy.md)
  (#59): `MATCH`, `NO MATCH`, `AMBIGUOUS`. This contract invokes those
  outcomes; it does not add a second identity or matching system.
- **Lifecycle state / event** — exactly as defined by
  [`finding-lifecycle-contract.md`](finding-lifecycle-contract.md) (#62):
  states `OPEN` / `RESOLVED`; events `DETECTED`, `STILL_PRESENT`,
  `RESOLVED`, `REOPENED`, `UNCERTAIN`. This contract supplies the
  **coverage** and **delta-attribution** evidence §5 of #62 requires
  before a transition may be applied; it does not add a state or event.
- **Blast radius** — any location, component, or behavior other than the
  exact prior finding location that is causally reachable from the new
  delta: a caller, callee, shared data structure, configuration consumer,
  interface implementer, or otherwise coupled unit whose behavior can
  change as a result of the changed code. "Reachable" here means
  evidence-based attribution (§4), not proximity or guesswork.
- **Settled non-finding / settled assumption** — a conclusion a completed
  prior review reached and did not report as a finding: "this pattern is
  safe here," "this invariant holds," "this is dead code," "this input is
  already validated upstream." Reusable evidence (§6), not immutable
  truth.
- **Escalation** — abandoning bounded delta re-review in favor of a
  broader or full review of the current state, per §7.

## 2. Change classes

A re-review must be able to classify each prior finding identity, and
each current candidate observation, into one of the following classes.
Each class name is descriptive of *how the delta relates to a prior
identity or a current observation*; it is not itself a lifecycle state —
lifecycle state and event ownership stays with #62 (§2 there already
establishes this same discipline for `NEW`/`STILL_PRESENT`/`REOPENED`).

| Change class | Meaning | Required evidence to classify | Maps to (#62) |
|---|---|---|---|
| **Unchanged** | The prior finding's logical site and surrounding code are outside the delta and outside any established blast radius; nothing observed changes its status. | The site was not touched by the delta and no blast-radius attribution (§4) reaches it. | No event is required; the prior lifecycle state is carried forward as-is. This is *not* `STILL_PRESENT` — that event requires positive current evidence (#62 §3) that this contract does not manufacture merely from "not in the delta." |
| **Fixed** | The delta changes the prior finding's logical site (or a matched continuation of it) in a way current evidence shows removes the defect-bearing condition. | Completed review, verified relevant coverage of the site, positive absence evidence, no continuity ambiguity — the full #62 §5 resolution bar. | `RESOLVED` (`FIXED`) event on the matched prior identity. |
| **Moved** | The delta relocates the prior defect-bearing condition (refactor, rename, file move, extraction) without resolving it; a definite #59 `MATCH` still holds. | Definite `MATCH` at the new location and positive evidence the same defect-bearing condition remains. | `STILL_PRESENT`, state stays `OPEN`. A move is never, by itself, a `NO MATCH` — see §6 of #59's discipline and §8 below. |
| **Reopened** | A `RESOLVED` prior identity has positive current recurrence evidence and a definite #59 `MATCH` under the recurrence exception. | The canonical recurrence handshake in #62 §6: prior `RESOLVED` state, positive recurrence-candidate evidence, `MATCH` under the recurrence exception. | `REOPENED`, state becomes `OPEN`. |
| **Newly introduced** | A current observation attributable to the delta (directly or via blast radius, §4) has no inherited prior identity and independently satisfies the finding evidence bar. | No `MATCH` to any prior identity; the observation stands on its own evidence. | `DETECTED`, state `OPEN`, exactly as any first detection. |
| **Ambiguous** | Matching cannot establish a definite relationship between a prior identity and a current candidate (split, collapse, insufficient identity evidence, or contested continuity). | #59 returns `AMBIGUOUS` for the relationship under consideration. | `UNCERTAIN`, prior state preserved (#62 §4, §7). Never resolved into a confident transition by this contract or by lower confidence heuristics. |

Notes:

- **Unchanged is a re-analysis-scope conclusion, not a lifecycle event.**
  It says only "this contract found no reason to re-open this identity's
  evidence." It never overrides a lifecycle transition that other
  evidence (e.g. a base-branch interaction, or a blast-radius finding
  that happens to touch the same identity) independently establishes.
- **A change class is not a promise of a favorable outcome.** "Moved" and
  "Reopened" both keep or return the identity to `OPEN`; classifying a
  finding into a class never itself resolves it. Only #62's evidence bar
  resolves anything.
- These six classes are the ones #64's Issue body and #62's downstream
  boundary require; this contract does not mint additional persisted
  classes. Where a class's evidence bar is unmet, the outcome is
  `Ambiguous`/`UNCERTAIN`, never a fabricated class of its own.

## 3. Delta is an optimization, not a finding boundary

Restating the canonical invariant operationally:

- The delta bounds where a re-review is **obligated to re-inspect** for
  the purpose of confirming prior findings' status. It does not bound
  where a defect may be **reported from**.
- A defect discovered anywhere in the reviewed state during a bounded
  delta re-review — including in code the reviewer opened only to
  understand the delta's context, or in a location surfaced by blast-radius
  attribution (§4) — is reportable through the normal finding path. The
  delta boundary is never cited as a reason to withhold a well-evidenced
  finding.
- Conversely, the delta boundary **is** a legitimate reason to *not*
  perform exhaustive re-analysis of code the delta does not touch and
  that has no attributable blast radius into it. Delta re-review is
  permitted to trust §6 settled evidence for that code; it is not
  required to re-derive it from scratch. That trust is conditional,
  not absolute — see §6.
- **A prior finding becoming resolved does not make the fix delta
  automatically clean.** The change that resolves a prior finding is
  itself newly written code and is in scope for new findings using the
  same evidence/severity model as any other code in the delta (§5). A
  `RESOLVED` event on one identity has no bearing on whether the same
  lines, or lines reachable from them, introduce an unrelated defect.

## 4. Blast radius

A regression need not occur on the exact lines of a prior finding, and a
newly introduced defect need not occur on lines the delta literally
edited, to be in scope.

- **Attribution must be evidence-based.** A location is in the delta's
  blast radius only when the reviewer can trace a concrete causal path
  from a changed line/behavior to the affected location — a call site
  invoking changed logic, a shared type/schema/contract the change
  alters, a config value the change repurposes, a test or caller relying
  on behavior the change removed, or an interface/implementation pairing
  broken by one side changing. "It's nearby" or "it's the same file" is
  not attribution.
- **Blast radius is not unrestricted speculative re-analysis.** This
  contract does not authorize re-auditing the whole repository "just in
  case." It authorizes following an evidenced causal chain outward from
  the delta until that chain runs out, and stopping there. If a reviewer
  cannot state a mechanism connecting the delta to a candidate location,
  that candidate is out of scope for this delta re-review (it may still
  be worth a separate task, but it is not a #64 finding).
- **Transitively broken behavior is in scope.** A component that calls
  into changed code, or that depends on an invariant the change altered,
  is a legitimate blast-radius target even when its own source lines are
  untouched by the diff.
- A finding surfaced via blast radius is a normal finding: it goes
  through the same evidence and severity model as any other (§5), and it
  is classified `Newly introduced` (§2) unless it independently matches a
  prior identity.

## 5. Mechanical review semantics are unchanged

Delta re-review changes **where** the reviewer looks and **why** a
finding is or is not re-surfaced. It changes nothing about **how** a
finding, once identified, is evidenced, classified, or turned into a
decision:

- Every finding discovered during delta re-review — `Fixed`-adjacent,
  blast-radius, or otherwise — uses the same evidence requirements as a
  full review; there is no reduced or heightened evidence bar for delta
  re-review.
- Severity uses the same P0/P1/P2 model
  ([`../../shared/policies/severity.md`](../../shared/policies/severity.md))
  unchanged. There is no separate "re-review severity" scale, and no
  down-weighting of a finding merely because it was found during a
  bounded pass.
- The overall decision is still derived mechanically from the findings
  valid for the reviewed state, per the existing decision-derivation
  rule. A prior `REVIEW CLEAN` result, or a specific prior finding
  becoming `RESOLVED`, never suppresses a newly valid P0/P1/P2 discovered
  in the same delta — consistent with #62 §8 ("The overall review result
  neither proves nor blocks a per-finding transition").
- Re-surfacing a prior finding (`Unchanged`/`Moved`/`Reopened`) reports it
  with its existing identity and current severity classification (#62
  §8: severity is reclassified from current impact, not carried forward
  blindly). Suppressing a prior finding (folding it into `Fixed`) requires
  the full #62 §5 resolution bar — nothing here weakens that bar.

## 6. Previously settled non-findings and assumptions

A completed prior review's conclusion that something is *not* a finding,
or that an architectural/behavioral assumption holds, is reusable
evidence (per
[`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md),
"prior review conclusions are reusable evidence, not immutable truth") —
never a fact a later delta re-review is required to take on faith
indefinitely.

- **Remains settled while its basis is intact.** A settled non-finding or
  assumption may be treated as still valid, without re-derivation, for as
  long as the delta leaves the evidence or assumptions that made it
  settled unchanged and outside its blast radius (§4).
- **Reconsidered when the delta invalidates that basis.** When the new
  delta changes code, configuration, or context that the settled
  conclusion depended on — directly, or via an attributable blast-radius
  path — that conclusion is no longer trusted as-is. The reviewer
  re-evaluates it against the current delta using the same evidence bar
  as any other finding determination. It may still hold after
  re-evaluation; the point is that the delta earns re-evaluation, not
  that it must overturn the conclusion.
- **Invalidation is itself evidence-based**, mirroring §4: the reviewer
  must be able to name what changed and why it bears on the settled
  conclusion. "The delta touched the same file" is not, by itself,
  sufficient to invalidate an unrelated settled conclusion in that file;
  a concrete causal or structural connection is.
- A settled non-finding that is reconsidered and found to no longer hold
  becomes a normal finding (§5) — there is no separate path for
  "formerly settled, now a defect."

## 7. Escalation to a broader/full review

Bounded delta re-review is a *fail-safe optimization*: it is valid only
while its own preconditions hold. Escalation is the safety valve when
they stop holding, mirroring the existing "fail conservative" discipline
in
[`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) (§7,
"when prior reviewed state cannot be established safely, fall back to a
fresh full review") and in
[`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md)
("Escalating from delta to full review").

**Escalate to a broader or full review of the current state whenever the
new delta materially invalidates enough of the following that a bounded
delta re-review can no longer produce a trustworthy result:**

- **Prior assumptions.** The delta changes an architectural or behavioral
  premise that multiple settled conclusions (§6) or prior findings
  depended on, such that re-validating them piecemeal would not
  reconstruct a coherent picture of the current state.
- **Context.** The delta is large enough, structurally different enough,
  or touches areas distant enough from the originally reviewed shape that
  the reviewer can no longer bound its blast radius (§4) with confidence
  — the causal chains needed for attribution become too numerous or too
  uncertain to trace individually.
- **Identity evidence.** Matching produces persistent or pervasive
  `AMBIGUOUS` outcomes (§2) across a meaningful share of prior findings,
  such that the reviewer cannot tell, for most of the prior finding set,
  whether it is `Unchanged`, `Moved`, `Fixed`, or superseded by something
  new. A single ambiguous identity does not trigger escalation; a
  delta that makes matching broadly unreliable does.
- **Review boundaries.** The reviewed-state preconditions from
  [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) §2/§7
  are violated for the region under evaluation (e.g. base movement whose
  interaction with the delta cannot be reconciled from recorded state) —
  that document already requires a full review in that case; this
  contract does not weaken it.

This contract deliberately does **not** invent a numeric threshold (a
count of changed files, lines, or findings) for escalation, because
neither Issue #64 nor an existing canonical policy defines one. The
trigger is semantic: *bounded delta re-review can no longer produce a
trustworthy result*, judged against the four bullets above. When in
doubt, escalate — the same "when in doubt, it escalates" default already
stated for SHA-bound delta re-review in
[`../features/delta-re-review.md`](../features/delta-re-review.md).

Escalating is not a failure outcome. A delta re-review that escalates and
completes as a full review still supersedes the same-reviewer predecessor
it started from — the reviewed-state chain in
[`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) §5
already models exactly this shape (`completeness = full`, `prior` still
recorded).

## 8. Identity integration — reuse, do not re-derive

This contract consumes #58/#59/#60 unchanged and adds no second identity
or matching system. In particular, this contract is careful not to equate
the following pairs, each of which is a distinct, previously-established
concept it must not collapse:

| Not the same as | Because |
|---|---|
| Same line ≠ same finding | Identity is descriptor-based (#60), not line-based; two different defects can share a line, and the same defect can move off its original line (`Moved`, §2). |
| Moved code ≠ a new finding | A definite `MATCH` after a move produces `STILL_PRESENT` (#62 §4, "`MATCH`"), not `DETECTED`. Treating every move as new would silently manufacture false resolutions and false detections. |
| Resolved identity ≠ a clean fix | `RESOLVED` says one identity's defect is gone (#62 §5); it says nothing about whether the resolving change introduced a different defect (§3, §5 above). |
| Ambiguity ≠ a confident lifecycle transition | `AMBIGUOUS` authorizes no transition (#62 §4, §7); this contract's change classes never convert an `AMBIGUOUS` #59 outcome into `Fixed`, `Moved`, or `Reopened` by inference, however plausible the inference looks. |

Every change class in §2 is defined in terms of a #58/#59/#60/#62 concept
(a matching outcome, an evidence bar, a lifecycle event) — never as an
independent judgment this contract makes on its own about identity or
continuity.

## 9. Scope boundaries

This document defines semantics only. It explicitly does **not** define,
and a downstream implementation must not treat it as defining:

| Not defined here | Owner |
|---|---|
| Loading, persisting, or reconstructing prior reviewed/lifecycle state at runtime | [#65](https://github.com/amirbena/code-review-skill/issues/65) |
| Orchestrating the load → classify → invoke-#59 → apply-#62 sequence at runtime, or any GitHub/local publication plumbing | [#65](https://github.com/amirbena/code-review-skill/issues/65) |
| The comprehensive delta/regression fixture matrix and its executable histories | [#66](https://github.com/amirbena/code-review-skill/issues/66) |
| What makes two findings "the same"; the matching algorithm and its proof gates | [#58](https://github.com/amirbena/code-review-skill/issues/58) / [#59](https://github.com/amirbena/code-review-skill/issues/59) |
| Stable finding ID construction | [#60](https://github.com/amirbena/code-review-skill/issues/60) |
| Lifecycle states, events, and the resolution/reopen evidence bars | [#62](https://github.com/amirbena/code-review-skill/issues/62) |
| The reviewed-SHA state record, its fields, authoritative-SHA rule, and reviewer ownership | [#63](https://github.com/amirbena/code-review-skill/issues/63) |
| P0/P1/P2 meanings and mechanical decision derivation | [`../../shared/policies/severity.md`](../../shared/policies/severity.md) |
| Review authorization, GitHub mutation behavior, and HEAD safety | [`../../skills/github-pr-review/policies/review-action-authorization.md`](../../skills/github-pr-review/policies/review-action-authorization.md), [`../../skills/github-pr-review/policies/review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md) |
| SHA-bound delta re-review's existing runtime behavior (`NO NEW DELTA`, reporting the mode used) | [`../../skills/github-pr-review/policies/reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md), [`../features/delta-re-review.md`](../features/delta-re-review.md) |

If work needed for one of those Issues is discovered while building #64,
document the dependency here rather than absorbing it.

## Status and canonical home

Until [#65](https://github.com/amirbena/code-review-skill/issues/65)
implements stateful re-review, **this document is the contract record**
for delta re-review semantics. Once #65 establishes the canonical runtime
rule in a packaged resource, that policy becomes the single normative
source and this document becomes a historical contract record that links
to it — the same lifecycle already described in
[`finding-identity-requirements.md`](finding-identity-requirements.md)
and [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md).

This is a repository-development doc, like its siblings in this
directory: **not** packaged into either Skill archive, and no packaged
Skill resource depends on it (see [`../../AGENTS.md`](../../AGENTS.md),
"Packaged Skills are independent of repository-level instructions").
