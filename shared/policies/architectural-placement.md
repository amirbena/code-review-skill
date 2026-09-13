# Shared Policy — Architectural Placement and Execution-Lifecycle Fidelity

Applies identically to `local-code-review` and `github-pr-review`. It owns
bounded reasoning about whether changed code is correctly *placed* within
the surrounding execution lifecycle: the semantic-risk trigger vocabulary,
bounded ring-by-ring context expansion, stop conditions, the
ineligible-versus-must-execute-and-fail distinction, the guardrails, and
the evidence requirement for a placement finding.

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
