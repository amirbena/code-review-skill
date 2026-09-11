# Shared Policy — Review Scope

Defines what any Code Review Skill in this repository examines, regardless
of whether it is `local-code-review` or `github-pr-review`.

## What is examined

- changed files
- the full diff (not only a truncated preview)
- relevant surrounding code needed to judge the change fairly
- tests (existing and missing)
- schemas and migrations
- configuration
- infrastructure (Docker, Kubernetes, Helm, Terraform, CI/CD, GitHub
  Actions, etc.)
- documentation
- repository contracts (APIs, interfaces, public behavior)

## Materially relevant concerns

Where applicable to the change: correctness, regressions, architecture
fidelity, contract fidelity, APIs, compatibility, data integrity,
security, concurrency, reliability, error handling, edge cases,
idempotency, database safety, migration safety, deployment safety,
infrastructure behavior, CI/CD behavior, test adequacy, missing regression
tests, operational risk, maintainability, repository conventions, and
documentation correctness.

## Related changes as one unit

Review semantically related changes together rather than treating individual
files or hunks as isolated review units — file-by-file review in isolation is
not the reviewing model this policy expects. When a change spans multiple
files or hunks that together implement one behavioral or architectural
concern — for example, an API contract with its DTO/schema and controller, a
producer with its consumer, a persistence model with its repository and
migration, or an implementation with its corresponding tests — reason about
that group as a single unit and check for cross-file consistency, not just
each file on its own. This includes following a changed return value,
exception, status/state value, or event/message to its actual callers or
consumers within the diff's blast radius — including whether an exception is
now swallowed, translated/wrapped, or replaced with a fallback value that can
present failure as apparent success — rather than judging producer and
consumer as independently correct in isolation.

This invariant applies identically to any Code Review Skill built on this
policy, local or PR-based, and regardless of which review engine or model
executes it. The examples above are illustrative, not a required checklist; a
reviewer capable of holding related changes in view needs no further
prescribed procedure, and a small, single-purpose change needs no grouping
ceremony at all.

## Existing behavior ownership

When a change introduces or reimplements meaningful behavior — a
business/domain rule, validation logic, a calculation, a state-transition
rule, integration or side-effect handling, or helper/service logic that
looks like it represents shared semantics — perform a targeted search,
scoped to the current delta's realistic blast radius, for an existing
canonical owner of that behavior: a shared helper, domain method, service,
or validation path already performing the same responsibility elsewhere.
Distinguish harmless local similarity and a legitimate independent
implementation from a new implementation that duplicates ownership of
shared behavior or business semantics — creating a second,
independently-evolving source of truth for something that should have one
owner. Raise a finding only when the evidence supports a real consistency,
correctness, or maintainability risk, classified under
[`severity.md`](severity.md) like any other finding. This is not generic
DRY commentary and never a license to demand refactoring merely because
superficial code similarity exists, and it is not a repository-wide
duplication audit — the search stays targeted to what the current change's
own shape suggests already has an owner.

## Root-cause and model-completeness pass

When several observed failures may be manifestations of one underlying
mechanism, this pass participates instead of enumerating symptom
permutations. The trigger signals, the consolidate-vs-keep-separate
evidence bar, the affected-locations requirement on a consolidated
finding, the canonical-owner / external-dependency rules, and re-review
reconciliation are owned by
[`root-cause-consolidation.md`](root-cause-consolidation.md) and are not
restated here.

This is not a second scope model: findings, labels, severity, and the
mechanical decision derivation are unchanged; it only determines whether
related manifestations are consolidated into one authoritative finding or
kept separate.

## Failure state, retry safety, and recovery

Treat this as one reasoning move, not three separate checklist items. It
triggers on a concrete signal in the diff: more than one side-effecting
step (for example, a persisted write followed by another operation), an
entry point that can plausibly run again for the same logical operation
(retry, redelivery, resubmission, at-least-once processing, queue/event/
webhook handling), or an external call combined with a state mutation —
payment and similarly sensitive workflows are a common case, not the only
one. Absent such a signal, this section does not apply and requires no
action.

When triggered, reason about: what state is left if the flow fails
partway; which side effects may already have happened by that point;
whether the logical operation can safely run again from that state
without duplicating work or external effects; and, when the code or
surrounding context claims another process reconciles the stranded state,
whether that recovery/reconciliation path actually exists in the
repository and actually covers this new state — never accepted merely
because "another process will eventually fix it," with no evidence that
such a process exists or handles this case.

### Observability is applicability-gated, not universal

Where this reasoning surfaces a meaningful, hard-to-detect failure mode,
weigh whether it would be operationally visible — but only after first
asking whether the change actually has a production-operational failure
mode for which detection or diagnosis is materially relevant. Observability
is not equally important for every kind of change:

- **Commonly relevant**: backend/service runtime behavior, payments or
  other high-impact business operations, queues/events/webhooks, external
  integrations, asynchronous processing, persistence combined with side
  effects, retries/redelivery, background jobs, and production
  orchestration.
- **Conditionally relevant for frontend/client changes**: only when the
  application already has an established client telemetry/error-reporting
  convention, the change introduces an operationally important runtime
  failure, and that failure would otherwise be materially difficult to
  diagnose. Do not turn an ordinary frontend review into a search for
  backend-style metrics.
- **Usually secondary or not applicable**: changes primarily to agent
  instructions, prompts, review Skills, policy Markdown, static docs, or
  non-runtime configuration — unless the changed system actually has
  runtime behavior of its own (agent orchestration, tool-invocation
  failures, persistent execution state, retries, scheduled/background
  execution, production telemetry), in which case the reasoning below
  applies to that runtime behavior specifically, not to the surrounding
  static content.

Concretely: does this diff introduce or modify a production-operational
failure mode for which detection or diagnosis is materially relevant? Only
when the answer is yes does the hierarchy below apply, preferring the
repository's own established mechanism over inventing a new one:

- If the surrounding system already uses metrics, counters,
  failure-reason classifications, or alerts for comparable flows, check
  only that the changed or new failure path participates in that existing
  mechanism consistently — it is not silently bypassed, misclassified, or
  invisible to an alert that depends on it.
- If the surrounding code relies primarily on logs, check only whether
  the existing logging convention still lets an operator distinguish the
  meaningful cases this change affects — success vs. failure, retryable
  vs. terminal, partial failure/stranded state, an important state
  transition, recovery triggered vs. failed, and enough identifying
  context to trace one instance. This is about fitting the existing
  convention, never a generic "add more logs" recommendation.
- Absent any established observability precedent, a missing signal is a
  finding only when the diff introduces or materially changes a
  high-impact failure mode that would otherwise be effectively
  undiagnosable through anything already in the repository — the concern
  is that the failure is undetectable, not merely that a particular
  metric is absent.

This does not require enumerating every failure point in every review;
apply it where the diff's own shape makes it relevant, and scale depth to
actual risk exactly as [`evidence.md`](evidence.md) already scales
dependency exploration to blast radius.

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
as one unit" and "Existing behavior ownership" above, and
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

## Affected-test / test-impact analysis

When a change alters observable production behavior, this pass traces the
change into existing tests that encode or depend on that behavior —
frequently tests not in the diff — rather than only checking whether the
changed code itself has tests. The signal-triggered scope (which changes
qualify and which do not), the location/re-validation/coverage procedure,
the finding bar, and the read-only boundaries are owned by
[`affected-test-analysis.md`](affected-test-analysis.md) and are not
restated here.

This is not a second scope model: it is bounded to the change's realistic
blast radius per [`evidence.md`](evidence.md), "Findings beyond the
changed lines," and is never a "did the PR add tests?" check or a
repository-wide test audit.

## Change-risk signals and review depth

Every review classifies its change into a deterministic review-depth
level — `standard`, `elevated`, or `deep` — from a fixed catalog of
change-risk signals (auth/access-control, migration/schema, concurrency,
public API contract, sensitive path, infra/config, and diff size). The
signal catalog, the exact classification ordering, the authoritative
diff-size thresholds, and the requirement that the level and its
activating signals are emitted with the review are owned by
[`change-risk-signals.md`](change-risk-signals.md) and are not restated
here.

This is not a second scope model. Blast radius is still scoped per
[`evidence.md`](evidence.md), "Findings beyond the changed lines";
findings, labels, severity, and the mechanical decision are unchanged;
the depth level never becomes a finding and is never a merge gate. It
only makes the "scale the review to the change" guidance already in this
policy and [`evidence.md`](evidence.md) explicit and inspectable.

## Repository expansion

Every review evaluates a fixed catalog of **expansion triggers** — a
changed call site's public symbol, a changed interface/contract, a
changed migration/schema, or a changed config consumer — and, for any
trigger that fires, follows it through a bounded, ring-based procedure
whose maximum ring is scaled by the change-risk depth above. Which
triggers fired, how far each was followed, and the concrete locations
inspected are emitted with the review. The fixed trigger catalog, the
ring procedure, the depth-scaled ceiling, and the reporting requirement
are owned by [`repository-expansion.md`](repository-expansion.md) and
are not restated here.

This is not a second scope model either: it governs only *how far* an
investigation looks beyond the diff to gather evidence, never what counts
as a finding, its evidence label, or its severity — and it never replaces
the signal-specific bounded expansion already defined above for
architectural-placement questions, or the test-tracing procedure in
[`affected-test-analysis.md`](affected-test-analysis.md).

## Large-change partitioning

When a change's diff size reaches a fixed, deterministic threshold, it is
partitioned into coherent review units — built by directory seeding, then
an evidence-based merge of units this policy's "Related changes as one
unit" already requires reviewing together, then capped to a reviewable
per-unit size — and each unit is reviewed against this same policy before
all units' findings are aggregated and de-duplicated (including across
units, per [`root-cause-consolidation.md`](root-cause-consolidation.md))
into the one final review. A change under the threshold is reviewed as a
single unit exactly as before. The threshold, the partition-construction
procedure, per-partition review, and cross-partition aggregation are owned
by [`large-pr-partitioning.md`](large-pr-partitioning.md) and are not
restated here.

This is not a second scope model: every partition is scoped, evidenced,
and labeled exactly as an unpartitioned review would be; partitioning only
changes how an unusually large diff is organized for review, never what
counts as a finding or its severity.

## Review stopping criteria

Every review evaluates whether it reached **complete coverage** — every
pass required by the change's classified depth above (and, when
[`large-pr-partitioning.md`](large-pr-partitioning.md) activated, every
partition) actually reached its own already-defined stop condition, not
merely attempted. Coverage, complete or not, is emitted with the review.
When coverage is `incomplete`, the review's primary outcome renders the
incomplete state instead of a clean or blocking decision, no matter what
[`severity.md`](severity.md)'s mechanical derivation would otherwise
produce from the findings gathered so far. The coverage definition, the
closed set of incomplete triggers, and the labeling requirement are owned
by [`review-stopping-criteria.md`](review-stopping-criteria.md) and are
not restated here.

This is not a second scope model either: coverage never changes what
counts as a finding, its evidence label, or its severity — it only states
plainly whether the review that produced those findings actually finished,
and ensures an unfinished review is never mistaken for a clean one.

## Technology neutrality

Every Skill built on this policy must remain technology-neutral. It must
not require a specific language, framework, architecture, repository
layout, deployment model, or infrastructure platform. It supports mixed
changes across arbitrary stacks (application code, tests, SQL, IaC,
CI/CD, YAML/JSON, Markdown, Agent/Skill instructions, and other
repository files). File extensions alone are never authoritative — the
reviewer reasons from code and context.

## Restraint

Do not manufacture findings merely to appear thorough. A clean review
with zero findings is a valid, complete outcome.
