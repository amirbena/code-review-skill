# Shared Policy — Architectural Placement and Execution-Lifecycle Fidelity

Applies identically to `local-code-review` and `github-pr-review`. It owns
bounded reasoning about whether changed code is correctly *placed* within
the surrounding execution lifecycle: the semantic-risk trigger vocabulary,
bounded ring-by-ring context expansion, stop conditions, the
ineligible-versus-must-execute-and-fail distinction, the guardrails, and
the evidence requirement for a placement finding. It also owns a second,
independently gated trigger class — "Analogue-based responsibility/
placement pattern inference" below — for undocumented *structural/
organizational* responsibility placement, reusing the same bounded
analogue-inspection mechanism rather than defining a new one.

This is a sub-domain of [`review-scope.md`](review-scope.md), which owns
base review scope and routes here. It introduces no second scope model or
second evidence standard: blast radius, evidence labeling (confirmed
defect / credible engineering risk / optional improvement), and the
no-repository-wide-audit boundary in [`evidence.md`](evidence.md) govern
here exactly as they do everywhere else.

## Architectural placement and execution-lifecycle fidelity

Local functional correctness is often insufficient to determine whether a
change is correctly *placed*. A changed method or file can be internally
correct — it computes the right value, guards the right condition, returns
the right result — while sitting at the wrong point in the surrounding
execution flow: a decision made after the lifecycle phase that owns it, a
check duplicated below the layer that already performs it, a mutation done
before the precondition that should gate it. This section is how a review
recognizes that "should this run *here*, in *this form*, at *this point in
the lifecycle*" question and expands context just far enough to answer it.

This is one concrete application of the proportional-scope and
evidence-labeling rules this repository already defines — "Related changes
as one unit" and "Existing behavior ownership" in
[`review-scope.md`](review-scope.md), and
[`evidence.md`](evidence.md), "Findings beyond the changed lines." It does
**not** introduce a second scope model or a second evidence standard:
blast radius, evidence labeling (confirmed defect / credible engineering
risk / optional improvement), and the no-repository-wide-audit boundary are
unchanged. It adds only the trigger vocabulary and stop conditions specific
to placement problems.

### When to expand context — semantic risk triggers

Expand beyond the changed method/file only when the change plausibly
affects one of the following **semantic** categories. The list is
illustrative of the kind of effect that matters, not a keyword or
method-name list:

- control flow / whether downstream code executes at all;
- externally visible or otherwise irreversible side effects;
- retry, exception, fallback, or error-propagation behavior;
- transaction boundaries or transactional ordering;
- authorization, permission, or policy enforcement;
- routing, dispatch, handler/strategy selection, or orchestration;
- idempotency or duplicate suppression;
- state-mutation ordering;
- lifecycle bookkeeping (what is recorded as done, attempted, or skipped);
- resource ownership or cleanup;
- concurrency or ordering guarantees;
- behavior whose correctness depends on a caller or callee contract.

Do **not** expand context merely because a method is large, a file
changed, an early return exists, or a particular framework, base class, or
method name appears. Structural shape is never itself the trigger — the
trigger is a plausible effect on one of the categories above. This is
**not** a fixed-vocabulary detector: names such as `shouldHandleEvent`,
`handle`, `supports`, `canHandle`, or `matches` carry no special meaning
here and may appear only in fixtures or examples. The reasoning is about
responsibility boundaries and lifecycle evidence found in the repository,
never about matching a name.

Representative pattern families — illustrative, not individually mandatory
rules, and not something to flag everywhere the shape superficially
appears:

- dispatcher / handler eligibility decided inside execution rather than in
  the eligibility phase that precedes it;
- router / consumer filtering placed below the routing decision;
- controller-versus-service/domain validation ownership;
- retry logic duplicated inside a component that already runs beneath an
  existing retry or orchestration layer;
- an authorization check first performed, or redundantly re-performed,
  below an established authorization boundary;
- an idempotency or duplicate-suppression check occurring after a side
  effect rather than before it;
- transaction-sensitive logic placed outside the intended transaction
  boundary;
- strategy or fallback selection implemented inside execution rather than
  in the selection step;
- state mutation occurring before a precondition or eligibility decision;
- error handling that locally looks safe but violates the caller's retry
  or error contract.

### Bounded context expansion

Investigate minimum-context-first, expanding one ring at a time and only as
far as needed:

```text
changed behavior
→ direct caller / callee
→ owning abstraction / interface / orchestrator / lifecycle boundary
→ sibling implementation or repository contract only if still necessary
```

Stop at the first ring that establishes or disproves the relevant
architectural contract. Do not default to repository-wide exploration.
Investigation depth stays proportional to semantic risk, uncertainty,
blast radius, and available repository evidence — the same scaling
[`evidence.md`](evidence.md) already applies to any other cross-file
reasoning.

### Stop conditions

Stop expanding as soon as any of these holds:

1. the relevant responsibility/lifecycle contract is established with
   enough repository evidence to support a finding;
2. the surrounding architecture establishes that the changed behavior is
   correctly placed;
3. additional context would not materially change the review conclusion;
4. repository evidence is insufficient or ambiguous — fail closed, do not
   invent the architecture;
5. continuing would require unrelated repository-wide exploration
   disproportionate to the changed behavior.

**"Insufficient evidence" is a valid terminal outcome** — it is not a
reason to speculate or to keep searching indefinitely.

### Investigation heuristic

1. Start from the changed behavior.
2. Identify whether its correctness depends on surrounding lifecycle or
   ownership at all; if not, this section does not apply.
3. Inspect the minimum relevant architectural context: direct callers and
   callees, the owning interface or orchestrator, dispatcher/router code,
   sibling implementations, or a repository-defined contract.
4. Establish the intended responsibility boundary from repository
   evidence.
5. Compare the changed placement/behavior against that boundary.
6. Emit a finding only with concrete evidence of a meaningful
   correctness, lifecycle, or maintainability impact — for example that an
   eligibility decision moved into execution now causes `handle()` to run,
   a side effect to occur, or an action to be recorded as taken for an
   input the surrounding design treats as ineligible.
7. Do **not** emit a finding solely because another location would be
   cleaner or the reviewer prefers a different design.

### Ineligible versus must-execute-and-fail

A check that filters out an *ineligible* input belongs in the eligibility
phase; a check whose job is to let an operation *execute and then fail* so
an exception or retry contract is honored must stay on the execution path.
The distinction is drawn from repository evidence about what the
surrounding lifecycle expects — for example, a missing-entity or `null`
case that must still flow into execution so a `NotFoundException` is raised
and existing retry semantics are preserved is **not** a misplacement, even
though it is structurally an early check. Reason about this from the
lifecycle contract, not from a special-cased rule.

### Guardrails

- Do not turn a review into repository-wide exploration; expansion stays
  proportional to blast radius and uncertainty.
- Do not infer an architectural boundary from naming alone — a predicate
  or boundary-looking symbol with unrelated semantics is not evidence of
  ownership.
- Do not flag an alternative design merely because the reviewer prefers
  it.
- Preserve intentional execution-time validation, retry/error semantics,
  transaction semantics, and other required lifecycle behavior.
- If repository evidence cannot establish ownership or the contract, do
  not invent it — no finding.

### Evidence

A placement finding requires concrete repository evidence of **both** the
changed code's actual placement **and** the responsibility boundary it
allegedly violates — the caller, interface, orchestrator, lifecycle phase,
or repository contract that owns the decision. Naming similarity alone is
insufficient. The finding is labeled confirmed defect / credible
engineering risk / optional improvement per [`evidence.md`](evidence.md)
like any other finding, and unresolvable ambiguity yields no finding.

This bounded caller/callee/owning-boundary reasoning is itself reused,
not redefined, by
[`../templates/finding.md`](../templates/finding.md), "Deriving the
fix/action location," to decide *which* of the sites a placement (or any
other) finding touches is its canonical fix/action location — precondition
violation versus contract violation versus a pre-existing callee bug
merely exposed, extended there to validation, state-transition, lifecycle,
authorization, encoding, and synchronization boundaries alongside
caller/callee. That section governs location selection; it does not
change whether a placement finding is raised in the first place.

## Analogue-based responsibility/placement pattern inference

This is a second, independently gated trigger class alongside "When to
expand context — semantic risk triggers" above. It leaves that trigger
vocabulary, its bounded ring-by-ring expansion, its stop conditions, its
ineligible-versus-must-execute-and-fail distinction, and its guardrails
exactly as defined above — this section adds a second trigger class, it
does not modify the first. It answers a different, narrower question:
whether a change's *structural/organizational* placement of a
responsibility — how many services or classes it is split across, how a
test file/class is organized, which package or module owns a piece of
logic, and similar shapes — deviates from a pattern the repository has
already established for that same responsibility, when the question is
not already settled by an explicit repository instruction or by the
lifecycle-semantic trigger vocabulary above.

This is **not** a generic style-consistency checker, and it does not
encode any specific preferred structure ("prefer one service," "prefer
one integration-test class," "match the majority structure") as a rule.
Different repositories can legitimately choose opposite structural
conventions for the same shape of responsibility. Repeated structure
alone is never proof that a new, differently organized implementation is
wrong.

### When this trigger applies

This trigger applies only when **all** of the following hold:

- the change introduces, moves, or reorganizes a responsibility in a way
  that has a structural/organizational shape — for example, one service
  versus several, one test file/class versus several, or which
  package/module owns a piece of logic;
- no instruction discovered per
  [`repository-instructions.md`](repository-instructions.md)
  (`AGENTS.md`/`CLAUDE.md`) already states the convention for that
  responsibility — see "Explicit instructions versus inferred patterns"
  below;
- the change does not already trip one of the semantic-risk triggers
  above under its own vocabulary — this trigger covers structural
  placement questions that vocabulary does not reach; it is never a
  second route to the same lifecycle-semantic findings.

When any of these does not hold, this trigger does not apply and this
section requires no action — the same "does not apply" posture the
semantic-risk trigger vocabulary above uses when no category matches.

### Reasoning sequence

When this trigger applies, reason in this order:

1. Identify the specific responsibility the change introduces, moves, or
   reorganizes.
2. Inspect the nearest meaningful analogous implementations of that same
   responsibility elsewhere in the repository, reusing the same
   minimum-context-first, one-ring-at-a-time investigation model as
   "Bounded context expansion" above rather than defining a new one — do
   not default to a repository-wide search for every superficially
   similar shape.
3. Distinguish a pattern that reflects a meaningful architectural,
   ownership, lifecycle, or integration boundary (for example, a split
   that consistently lines up with a deployment, ownership, or contract
   boundary) from cosmetic repetition (files that merely happen to be
   organized the same way with no evidenced boundary behind it). Only the
   former is evidence of an established pattern; the latter is not.
4. Compare the change against that evidence.
5. When the change deviates, investigate whether the deviation is
   intentional or otherwise justified by evidence in the change or the
   repository — a stated reason, a different context, a boundary the
   analogues do not share — before treating it as a candidate finding.
6. Require a concrete architectural, ownership, lifecycle, or integration
   consequence of the deviation before emitting any finding. The
   structural difference or the repetition alone is never sufficient.

### Guardrail: repetition is evidence, never authority

Frequency or repetition of a structural pattern across the repository is,
at most, evidence that a convention may exist. It is never authority, and
never by itself proof that a differently organized implementation is
defective. A pattern repeated many times without an evidenced
architectural, ownership, lifecycle, or integration boundary behind it
remains cosmetic repetition per step 3 above, however many times it
recurs.

### Explicit instructions versus inferred patterns

Explicit repository instructions discovered per
[`repository-instructions.md`](repository-instructions.md)
(`AGENTS.md`/`CLAUDE.md`) remain the authoritative source on any question
they answer. An inferred structural pattern from analogous implementations
supplies additional architectural evidence only for questions no explicit
instruction already governs, and never overrides or contradicts an
explicit instruction that does. When an explicit instruction and an
inferred pattern would point to different conclusions, the explicit
instruction governs and this trigger raises no competing finding.

### Bounded, not an unbounded search

Analogue inspection reuses "Bounded context expansion" and "Stop
conditions" above without modification: investigate the nearest
meaningful analogues first, expand one ring at a time only as far as
needed, and stop — including at "insufficient evidence" as a valid
terminal outcome — under the same conditions that already govern the
lifecycle-semantic trigger vocabulary. This trigger is never license to
enumerate every file in the repository with a superficially similar
shape.

### Interaction with root-cause consolidation

When several changed locations deviate from the same established pattern
for the same underlying reason, this trigger's reasoning establishes the
pattern and the deviation; whether those locations are then reported as
one consolidated finding or as independent findings is governed entirely
by [`root-cause-consolidation.md`](root-cause-consolidation.md) — this
section documents the interaction, it does not redefine that policy's
clustering model. In practice, one inferred pattern violated identically
at multiple sites for the same underlying reason is the kind of shared
mechanism "Shared root cause versus independent findings" there already
asks the reviewer to recognize, subject to that same evidence bar; it is
never automatically split into one finding per site merely because the
same deviation surfaced at more than one location, and it is never
consolidated merely because several sites share a theme without a
positively established shared cause.

### Guardrails

Every guardrail in "Guardrails" above applies unchanged to this trigger.
In addition, specific to this trigger:

- Do not treat naming similarity, coincidental structural resemblance, or
  a shared framework/base class as evidence of an established pattern by
  itself — the pattern must reflect the architectural, ownership,
  lifecycle, or integration boundary described in step 3 above.
- Do not flag a deviation merely because the reviewer prefers the
  repository's more common shape, or because the new implementation
  "looks different" — a concrete consequence is required, never
  aesthetic or stylistic preference.
- Do not enforce any specific structural shape (one service vs. several,
  one test file/class vs. several, a particular package placement) as a
  mandatory convention wherever it superficially appears; this trigger
  detects and reports a deviation with a concrete consequence, it never
  prescribes, mandates, or auto-corrects a preferred structure.
- Never manufacture a finding under this trigger to appear thorough —
  "insufficient evidence" is a valid terminal outcome, exactly as the
  lifecycle-semantic trigger vocabulary above.
- The source of a convention — whether stated explicitly or inferred from
  analogues — never itself raises the severity of a resulting finding;
  severity is governed only by [`severity.md`](severity.md), based on the
  consequence, exactly as for any other finding.
- Insufficient or ambiguous evidence of either the pattern or the boundary
  behind it is a valid terminal outcome — fail closed; do not invent an
  established convention from a handful of coincidentally similar files.

### Non-goals

- A generic style-consistency checker, or any rule that encodes a
  specific preferred structure as mandatory wherever it superficially
  appears.
- Automatically refactoring or moving a deviating implementation — this
  trigger is detection/finding only.
- Redefining [`repository-expansion.md`](repository-expansion.md)'s fixed
  trigger catalog or ring-ceiling table, or
  [`evidence.md`](evidence.md)'s evidence-labeling and
  no-repository-wide-audit boundary.
- Redefining [`root-cause-consolidation.md`](root-cause-consolidation.md)'s
  clustering criteria — see "Interaction with root-cause consolidation"
  above.
- Redefining the bounded context-expansion model this file owns — the
  candidate-finding validation model (a repository-development document,
  not a packaged resource, so it is named here, not linked) reuses it
  directly for a candidate's blast-radius investigation, rather than
  defining a second one.
