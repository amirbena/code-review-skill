# Finding Lifecycle Contract

Repository-development contract for GitHub Issue
[#62](https://github.com/amirbena/code-review-skill/issues/62). It defines the
state of one stable finding identity across completed reviews. It consumes the
identity and matching contracts without redefining them, and gives #64 and #65
one lifecycle model to apply.

This is authoritative until #65 installs equivalent runtime behavior in a
packaged shared policy. That policy then becomes the single normative source
and this document becomes its design record.

## Decision

Persist only two lifecycle states:

```text
OPEN  <-------------------->  RESOLVED
      RESOLVED      REOPENED
```

`NEW`, `STILL_PRESENT` / `UNCHANGED`, and `REOPENED` describe how a review
reached a state; they are not additional states. `AMBIGUOUS` / `UNKNOWN`
describes insufficient transition evidence, not the defect's state.
`SUPERSEDED` and `NO_LONGER_APPLICABLE` are reasons an identity may enter
`RESOLVED`, not independently live states.

```text
DETECTED       STILL_PRESENT       RESOLVED       REOPENED
   ↓                  ↓                 ↓              ↓
 OPEN       →        OPEN       →    RESOLVED    →    OPEN
```

An uncertain observation records `UNCERTAIN` and preserves the last established
state. It never fills an evidence gap with a transition.

## 1. Terminology and ownership

- **Finding identity** — the stable logical defect identity owned by #60 under
  [`finding-identity-requirements.md`](finding-identity-requirements.md).
- **Matching outcome** — `MATCH`, `NO MATCH`, or `AMBIGUOUS`, exactly as
  selected by [`finding-matching-strategy.md`](finding-matching-strategy.md).
  Matching answers whether a current observation continues a prior identity.
- **Lifecycle state** — the last established current truth for one identity:
  `OPEN` or `RESOLVED`.
- **Lifecycle event** — the evidence-backed explanation for a review's effect
  on that state: `DETECTED`, `STILL_PRESENT`, `RESOLVED`, `REOPENED`, or
  `UNCERTAIN`.
- **Positive resolution evidence** — affirmative proof that a successfully
  completed review covered and re-evaluated the prior defect-bearing condition
  and established that it is absent.
- **Current observation** — evidence from the later review. Merely failing to
  emit a finding is not an observation of absence.

Identity/matching and lifecycle are separate decisions. A `MATCH` can authorize
a transition; it does not choose the transition. `NO MATCH` says only that no
current finding inherited the old identity. `AMBIGUOUS` authorizes no lifecycle
transition.

## 2. Persistent states

| State | Meaning | Entry evidence | Exit evidence | Terminal? |
|---|---|---|---|---|
| `OPEN` | The defect represented by this identity is established to exist in the current reviewed state. | First supported detection, a definite matched continuation, or a definite recurrence of a resolved identity. | Positive resolution evidence from a completed review. | No. |
| `RESOLVED` | The defect represented by this identity is established not to exist in the current reviewed state. | Positive resolution evidence; never non-emission alone. | A definite `MATCH` plus positive current evidence that the same defect exists again. | No. |

There is deliberately no terminal state. Code, requirements, and behavior can
change again. A deleted site, superseded obligation, or no-longer-applicable
condition may make recurrence unlikely, but a later definite continuation can
still reopen the identity.

### Why the other candidate states are not persisted

| Candidate | Classification | Reason |
|---|---|---|
| `NEW` | `DETECTED` event leading to `OPEN` | Derivable from “no prior identity + supported current finding”; it stops describing current truth after the first review. |
| `UNCHANGED` / `STILL_OPEN` | `STILL_PRESENT` event, state remains `OPEN` | Describes an `OPEN → OPEN` transition. “Still present” is the existing repository term. |
| `REOPENED` | `REOPENED` event leading from `RESOLVED` to `OPEN` | The current condition is open; history records how it became open. |
| `AMBIGUOUS` / `UNKNOWN` | `UNCERTAIN` event with state preservation | Uncertainty about new evidence must not overwrite established truth. |
| `SUPERSEDED` | `RESOLVED` reason | A newer explicit obligation can prove the old defect no longer applies. |
| `NO_LONGER_APPLICABLE` | `RESOLVED` reason | Applicability is a resolution reason, not a third live condition. |

The original Issue #62 list of `new`, `open`, `resolved`, `superseded`, and
`no longer applicable` is represented without five redundant persistent
values: `new` is an event; `open` and `resolved` are states; the last two are
resolution reasons.

## 3. Events and provenance

| Event | Meaning | Required evidence |
|---|---|---|
| `DETECTED` | A supported current defect begins an identity's history in `OPEN`. | No prior identity is assigned, and current evidence independently satisfies the finding evidence bar. |
| `STILL_PRESENT` | A prior `OPEN` identity remains `OPEN`. | Definite `MATCH` and positive current evidence that the same defect-bearing condition remains, including after a partial modification. |
| `RESOLVED` | A prior `OPEN` identity enters `RESOLVED`. | Every resolution requirement in §5. |
| `REOPENED` | A prior `RESOLVED` identity returns to `OPEN`. | Definite `MATCH` and positive current evidence that the same logical defect exists again. |
| `UNCERTAIN` | The review cannot safely establish a transition. | Ambiguous matching, insufficient coverage, incomplete review, or another explicit evidence gap; preserve prior state. |

Each applied event needs enough provenance to reconstruct the chain: prior
identity, prior state, matching outcome, reviewed-state boundary, review
completion, coverage/evidence conclusion, event, resulting state, and any
resolution reason. This is a semantic requirement, not a storage schema; #65
owns representation and persistence.

`NO TRANSITION` in tables means no event is required. It is not a sixth event.

## 4. Matching-to-lifecycle boundary

### `MATCH`

A definite logical continuation exists. Prior `OPEN` plus evidence that the
defect remains produces `STILL_PRESENT` and `OPEN`; prior `RESOLVED` plus
evidence that it exists again produces `REOPENED` and `OPEN`. A material code
change, move, partial fix, wording change, or severity change does not alter
this rule if #59 still returns `MATCH`.

### `NO MATCH`

No current finding inherited the prior identity. This does **not** establish
that the prior identity is resolved. For that identity, verified coverage plus
positive evidence of absence may produce `RESOLVED`; missing coverage or mere
non-emission produces `UNCERTAIN` and preserves the prior state. An already
resolved identity normally needs no transition when absence remains verified.

A supported current finding with no inherited identity begins its own chain as
`OPEN` via `DETECTED`. That chain does not modify the old identity.

### `AMBIGUOUS`

Do not infer resolved, reopened, detected-as-distinct, or still present for the
relationship under consideration. Record `UNCERTAIN` for each affected prior
identity and preserve its established state. Split (one-to-many) and collapse
(many-to-one) components receive the same treatment; this contract creates no
parent/child identity or lifecycle transition.

#59/#60 may assign fresh identities to current candidates because ambiguous
evidence cannot transfer an old identity. If those candidates independently
satisfy the finding evidence bar, they can be `OPEN` in their own chains, but
`DETECTED` there means only “first observation under this identity.” It must not
be presented as proof they are logically new rather than ambiguous
continuations.

## 5. Resolution evidence

An `OPEN → RESOLVED` transition requires **all** of the following:

1. **Valid prior identity and state.** The trusted prior identity is `OPEN` and
   belongs to the reviewed-state chain being advanced.
2. **Completed review.** The later review completed successfully for the
   relevant target. An aborted or incomplete review cannot resolve a finding.
3. **Verified relevant coverage.** The prior logical site and behavior needed
   to evaluate the defect were in valid scope and actually re-evaluated. #64
   computes this; this contract requires its affirmative result.
4. **Positive absence evidence.** Current code/behavior demonstrates that the
   defect-bearing cause is absent: fixed, deleted, or made inapplicable by an
   explicit newer requirement.
5. **No continuity ambiguity.** Matching, moves, splits, collapses, or competing
   candidates leave no uncertainty about whether the defect persists.
6. **Evidence trace.** Concrete coverage and absence evidence is retained with
   a reason when relevant: `FIXED`, `CODE_REMOVED`, `SUPERSEDED`, or
   `NO_LONGER_APPLICABLE`.

“The later review did not emit it,” “no `MATCH` was found,” a clean overall
decision, and a changed line outside the relevant behavior are each
insufficient. Deletion resolves only when the review verifies that the deleted
code carried the defect and no matched continuation exists elsewhere.
Supersession/no-longer-applicable requires explicit current requirements or
settled design evidence, not reviewer preference.

Resolution is per finding and independent of the overall review result. One
finding may become `RESOLVED` while other P0/P1 findings make the same review
`CHANGES REQUIRED` or `Request Changes`.

## 6. Reopen evidence

`RESOLVED → OPEN` is `REOPENED` only when a stable prior identity is
`RESOLVED`, #59 establishes one definite `MATCH`, and positive current evidence
establishes that the same defect-bearing condition exists again.

Similarity elsewhere is not reopening. With `NO MATCH`, a similar defect gets
its own identity and `DETECTED`. With `AMBIGUOUS`, the old identity remains
`RESOLVED` with `UNCERTAIN`; no reopen is fabricated.

## 7. State-transition table

| Prior state | Matching outcome | Coverage / current evidence | Event | Resulting state |
|---|---|---|---|---|
| none | not applicable | Supported current finding; no prior identity assigned | `DETECTED` | `OPEN` |
| `OPEN` | `MATCH` | Same defect positively shown still present | `STILL_PRESENT` | `OPEN` |
| `OPEN` | `MATCH` | Current defect evidence is missing or contradictory | `UNCERTAIN`; re-evaluate inputs | `OPEN` preserved |
| `OPEN` | `NO MATCH` | Completed review, verified relevant coverage, positive absence evidence, no ambiguity | `RESOLVED` | `RESOLVED` |
| `OPEN` | `NO MATCH` | No verified coverage or only non-emission | `UNCERTAIN` | `OPEN` preserved |
| `OPEN` | `AMBIGUOUS` | Any coverage | `UNCERTAIN` | `OPEN` preserved |
| `RESOLVED` | `MATCH` | Same defect positively shown to exist again | `REOPENED` | `OPEN` |
| `RESOLVED` | `MATCH` | Current defect evidence insufficient or contradictory | `UNCERTAIN`; re-evaluate inputs | `RESOLVED` preserved |
| `RESOLVED` | `NO MATCH` | Verified absence remains consistent | `NO TRANSITION` | `RESOLVED` |
| `RESOLVED` | `NO MATCH` | Coverage unavailable | `UNCERTAIN` only if the gap is material | `RESOLVED` preserved |
| `RESOLVED` | `AMBIGUOUS` | Any coverage | `UNCERTAIN` | `RESOLVED` preserved |
| `OPEN` or `RESOLVED` | any | Review aborts/incomplete before sufficient evaluation | `UNCERTAIN` | prior state preserved |

Impossible or unsupported transitions:

- `AMBIGUOUS → RESOLVED`, `AMBIGUOUS → REOPENED`, or
  `AMBIGUOUS → STILL_PRESENT`;
- `OPEN → RESOLVED` from non-emission, `NO MATCH` alone, or overall
  `REVIEW CLEAN`;
- `RESOLVED → OPEN` from similarity, severity change, or `NO MATCH`;
- a split/collapse creating parent, child, merged, or superseded relationships;
- `OPEN → NEW` or `RESOLVED → NEW`; `NEW` is not a state;
- any transition written by an aborted/incomplete review.

## 8. Severity and review-result independence

Severity is not identity or lifecycle. It remains governed solely by
[`../shared/policies/severity.md`](../shared/policies/severity.md).

An `OPEN` finding may change P2 → P1 or P1 → P2 while retaining identity and
producing `STILL_PRESENT`. Severity change alone cannot produce `DETECTED`,
`RESOLVED`, or `REOPENED`. Lifecycle events do not dictate severity; a reopened
finding is classified from its current impact.

The overall review result neither proves nor blocks a per-finding transition.
If the review is globally incomplete, no transitions are committed from that
attempted review.

## 9. Required scenario matrix

| # | Scenario | Prior state | #59 outcome | Required coverage / evidence | Event | Resulting state |
|---:|---|---|---|---|---|---|
| 1 | First detection | none | n/a | Current finding independently meets evidence bar | `DETECTED` | `OPEN` |
| 2 | Unchanged on next review | `OPEN` | `MATCH` | Current defect positively still present | `STILL_PRESENT` | `OPEN` |
| 3 | Partial fix; same defect remains | `OPEN` | `MATCH` | Current cause → faulty behavior remains demonstrable | `STILL_PRESENT` | `OPEN` |
| 4 | Definite fix with verified coverage | `OPEN` | `NO MATCH` | Completed review; site/behavior covered; condition absent; no ambiguity | `RESOLVED` (`FIXED`) | `RESOLVED` |
| 5 | Absent, but prior site outside scope | `OPEN` | `NO MATCH` | Relevant coverage is not established | `UNCERTAIN` | `OPEN` preserved |
| 6 | Absent with ambiguous matching | `OPEN` | `AMBIGUOUS` | Ambiguity forbids transition | `UNCERTAIN` | `OPEN` preserved |
| 7 | Resolved finding returns at same site | `RESOLVED` | `MATCH` | Positive evidence of same defect | `REOPENED` | `OPEN` |
| 8 | Similar defect elsewhere after resolution | `RESOLVED` | `NO MATCH` | Old remains resolved; new site independently meets evidence bar | old: no transition; new: `DETECTED` | old `RESOLVED`; new `OPEN` |
| 9 | Severity increases while open | `OPEN` | `MATCH` | Defect still present; current impact classified independently | `STILL_PRESENT` | `OPEN` |
| 10 | Severity decreases while open | `OPEN` | `MATCH` | Defect still present; current impact classified independently | `STILL_PRESENT` | `OPEN` |
| 11 | One prior finding splits into two candidates | `OPEN` | `AMBIGUOUS` | One-to-many cannot transfer identity | `UNCERTAIN` | `OPEN` preserved |
| 12 | Two prior findings collapse into one candidate | `OPEN` for both | `AMBIGUOUS` | Many-to-one cannot transfer either identity | `UNCERTAIN` each | both `OPEN` preserved |
| 13 | Review aborts before sufficient coverage | either | any/unavailable | Completion requirement fails | `UNCERTAIN` | prior state preserved |
| 14 | Code containing finding is deleted | `OPEN` | `NO MATCH` | Completed review verifies covered deletion and no continuation | `RESOLVED` (`CODE_REMOVED`) | `RESOLVED` |
| 15 | Site moves/refactors and matches definitively | `OPEN` | `MATCH` | Unique site/defect continuity; defect remains | `STILL_PRESENT` | `OPEN` |

For scenarios 11 and 12, fresh identities assigned to independently supported
current candidates do not prove those candidates logically new; their
ambiguous relationship to preserved prior identities remains in provenance.

## 10. Downstream boundaries

- **#59 — matching strategy:** owns proof gates, matching outcomes, and
  split/collapse ambiguity. This contract consumes them unchanged.
- **#60 — stable IDs:** owns identity/descriptor construction, serialization,
  propagation, and fresh-ID assignment. This contract defines none of those.
- **#64 — review delta semantics:** owns scope, coverage, change classes, and
  re-surface/suppress behavior. It must supply affirmative relevant coverage
  before this contract permits resolution.
- **#65 — stateful implementation:** owns loading, application, persistence,
  output fields, fallback, and provenance representation. It must not add
  lifecycle semantics.
- **#66 — regression fixtures:** owns executable histories. Its fixtures must
  inherit the fifteen scenarios in §9 and assert state plus event.

This document does not change the current finding schema, output rendering,
same-HEAD de-duplication, reviewed-state storage, matching algorithm, severity
policy, or decision derivation.
